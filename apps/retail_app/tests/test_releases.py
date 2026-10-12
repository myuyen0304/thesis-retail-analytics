"""Cách ly cache và kiểm quyền khi phục vụ nhiều phiên bản DWH."""
import json
import pytest
from ai_explain.tools import ALLOWED_RELATIONS
from dwh import guarded, releases
from dwh.guarded import _dbx_violations
from ui import common


def test_cache_key_includes_release(monkeypatch):
    common.load.clear()
    called = []
    monkeypatch.setattr(common.queries, 'build_info', lambda backend: called.append(backend) or 'data')
    common.load('build_info', 'duckdb', 'a')
    common.load('build_info', 'duckdb', 'a')
    common.load('build_info', 'duckdb', 'b')
    assert len(called) == 2
    common.load.clear()


def test_pin_rejects_draft_and_invalid_identifier():
    with pytest.raises(ValueError):
        releases.pin({'release_id': 'x;drop table x', 'status': 'ready', 'schema': 'reporting'})
    with pytest.raises(ValueError):
        releases.pin({'release_id': 'a' * 24, 'status': 'building', 'schema': 'r_' + 'a' * 24 + '_reporting'})


def test_required_privileges_are_for_selected_version_only():
    sch = 'r_' + 'a' * 24 + '_reporting'
    allowed = frozenset({'reporting.rpt_build_info', sch + '.rpt_build_info', releases.CONTROL_RELATION})
    required = frozenset({sch + '.rpt_build_info', releases.CONTROL_RELATION})
    grants = [('catalog', 'retail_lab', None, None, 'reader', 'USE_CATALOG', False)]
    for schema, table in (r.split('.') for r in required):
        grants.extend([('schema', 'retail_lab', schema, None, 'reader', 'USE_SCHEMA', False),
                       ('table', 'retail_lab', schema, table, 'reader', 'SELECT', False)])
    assert not _dbx_violations('reader', 'reader', grants, [], allowed, 'retail_lab', required)
    grants.append(('table', 'retail_lab', 'raw', 'orders', 'reader', 'SELECT', False))
    assert _dbx_violations('reader', 'reader', grants, [], allowed, 'retail_lab', required)


# --- Chế độ cũ trong lúc chuyển đổi: pipeline đã cấp quyền bản mới cho SP AI, app public chưa bật versioned ---

CAT, SP, RID = 'retail_lab', 'ai-sp', 'a' * 24
NEW = {f'r_{RID}_reporting.' + r.split('.')[1] for r in ALLOWED_RELATIONS}
AFTER_PIPELINE = set(ALLOWED_RELATIONS) | NEW | {releases.CONTROL_RELATION}   # quyền SP AI sau stage validate


class _RegistryCursor:
    """Cursor giả cho _release_scope: registry có hiện với SP hay không, và payload đọc được."""

    def __init__(self, visible, rows=()):
        self.visible, self.rows, self.sql = visible, list(rows), []

    def execute(self, sql, params=None):
        self.sql.append(sql)
        self._cur = [(int(self.visible),)] if 'information_schema.tables' in sql else self.rows

    def fetchone(self):
        return self._cur[0]

    def fetchall(self):
        return self._cur


def _ready(rid, status='ready'):
    return {'release_id': rid, 'snapshot_id': 's', 'code_version': 'c', 'run_id': 'r',
            'schema': f'r_{rid}_reporting', 'duckdb_path': '/x', 'status': status}


def _registry(*records):
    return [(json.dumps({'active': records[0]['release_id'], 'releases': {r['release_id']: r for r in records}}),)]


def _violations(cur, relations):
    grants, objects = [('catalog', CAT, None, None, SP, 'USE_CATALOG', False)], []
    for r in relations:
        s, t = r.split('.')
        grants += [('schema', CAT, s, None, SP, 'USE_SCHEMA', False), ('table', CAT, s, t, SP, 'SELECT', False)]
        objects.append(('table', CAT, s, t, 'writer', False))
    allowed, required = guarded._release_scope(cur, ALLOWED_RELATIONS, CAT)
    return _dbx_violations(SP, SP, grants, objects, allowed, CAT, required)


@pytest.fixture
def legacy(monkeypatch):
    monkeypatch.delenv('RETAIL_RELEASE_MODE', raising=False)
    releases.reset()
    yield
    releases.reset()


def test_che_do_cu_chua_co_registry_giu_nguyen_luat(legacy):
    assert _violations(_RegistryCursor(False), ALLOWED_RELATIONS) == []
    # Không thấy registry mà có quyền trên bản mới thì vẫn khóa: code này phải lên bản public TRƯỚC lần chạy cloud đầu.
    assert _violations(_RegistryCursor(False), AFTER_PIPELINE)


def test_che_do_cu_chap_nhan_ban_da_qua_gate_khong_pin(legacy):
    assert _violations(_RegistryCursor(True, _registry(_ready(RID))), AFTER_PIPELINE) == []
    assert releases.current() is None          # SQL vẫn đọc reporting.*, evidence không được gắn release_id
    thieu = AFTER_PIPELINE - {sorted(ALLOWED_RELATIONS)[0]}
    assert any('thiếu' in v for v in _violations(_RegistryCursor(True, _registry(_ready(RID))), thieu))


def test_che_do_cu_ban_ngoai_registry_van_la_quyen_thua(legacy):
    la = AFTER_PIPELINE | {'r_' + 'b' * 24 + '_reporting.rpt_build_info'}
    assert _violations(_RegistryCursor(True, _registry(_ready(RID))), la)


@pytest.mark.parametrize('rows', [[], [('{hỏng',)], _registry(_ready(RID, status='building'))])
def test_registry_hong_thi_guard_tu_choi(legacy, rows):
    with pytest.raises(guarded.GuardError):
        guarded._release_scope(_RegistryCursor(True, rows), ALLOWED_RELATIONS, CAT)


def test_che_do_versioned_pin_va_bat_buoc_quyen_ban_dang_doc(legacy, monkeypatch):
    monkeypatch.setenv('RETAIL_RELEASE_MODE', 'versioned')
    allowed, required = guarded._release_scope(_RegistryCursor(True, _registry(_ready(RID))), ALLOWED_RELATIONS, CAT)
    assert releases.current()['release_id'] == RID
    assert required == NEW | {releases.CONTROL_RELATION} and AFTER_PIPELINE <= allowed
