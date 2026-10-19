"""S3 (A4, 2026-10-19): thẻ "bản đang phục vụ" trên trang Sức khỏe dữ liệu và giờ công bố lưu cạnh con trỏ registry.

Kiểm hai chiều tương thích, vì pipeline có thể ghi payload mới lên cloud trước khi PM kịp Reboot bản public:
- code app MỚI đọc registry CŨ (chưa có `active_since`) vẫn chạy, thẻ ghi "chưa ghi";
- code app CŨ (dwh/releases.py và dwh/guarded.py ở commit `e7c17aa`, trước S3) đọc payload MỚI vẫn chạy.
"""
import datetime as dt
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from ai_explain.tools import ALLOWED_RELATIONS
from dwh import releases

ROOT = Path(__file__).resolve().parents[3]
APP = Path(__file__).resolve().parents[1] / 'app.py'
PAGE = 'views/suc_khoe_du_lieu.py'
OLD = 'e7c17aa'                       # HEAD trước S3: code app đang chạy ở bản public tới khi PM Reboot
RID = 'a' * 24


def _rec(rid=RID):
    return {'release_id': rid, 'snapshot_id': 's', 'code_version': 'c' * 40, 'run_id': 'r', 'schema': f'r_{rid}_reporting',
            'duckdb_path': '/x', 'status': 'ready'}


def _payload(since=True, since_rid=RID):
    p = {'active': RID, 'releases': {RID: _rec(), 'b' * 24: _rec('b' * 24)}}
    if since:
        p['active_since'] = {'release_id': since_rid, 'at': '2026-10-19T01:02:03Z'}
    return p


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    def write(payload):
        path = tmp_path / 'state.json'
        path.write_text(json.dumps({'version': 'v', 'payload': payload}), encoding='utf-8')
        monkeypatch.setenv('RETAIL_RELEASE_MODE', 'versioned')
        monkeypatch.setenv('RETAIL_RELEASE_STATE', str(path))
        releases.reset()
        return path
    yield write
    releases.reset()


@pytest.mark.parametrize('payload,expected', [
    (_payload(), '2026-10-19T01:02:03Z'),
    (_payload(since=False), None),                          # registry cũ chưa có trường mới
    (_payload(since_rid='b' * 24), None),                   # code cũ đổi con trỏ mà không ghi giờ: không hiện giờ sai
])
def test_gio_cong_bo_doc_cung_lan_pin_ban(state_file, payload, expected):
    state_file(payload)
    assert releases.resolve('duckdb')['release_id'] == RID
    assert releases.published_at() == expected
    releases.reset()
    assert releases.published_at() is None


# --- code app CŨ đọc payload MỚI ---

def _old_module(name, rel_path, **override):
    try:
        src = subprocess.run(['git', 'show', f'{OLD}:{rel_path}'], cwd=ROOT, capture_output=True, text=True,
                             encoding='utf-8', check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip(f'không đọc được {rel_path} ở commit {OLD} (cần git và lịch sử repo)')
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = str(ROOT / rel_path)
    exec(compile(src, mod.__file__, 'exec'), mod.__dict__)
    mod.__dict__.update(override)
    return mod


class _Cursor:
    """Cursor giả: registry thấy được và trả payload MỚI (như test_releases._RegistryCursor)."""

    def __init__(self, payload):
        self.payload = payload

    def execute(self, sql, params=None):
        self._rows = [(1,)] if 'information_schema.tables' in sql else [(json.dumps(self.payload),)]

    def fetchone(self):
        return self._rows[0]

    def fetchall(self):
        return self._rows


def test_code_app_cu_doc_payload_registry_moi(state_file, monkeypatch):
    old = _old_module('releases_truoc_s3', 'apps/retail_app/dwh/releases.py')
    assert not hasattr(old, 'published_at')                  # đúng là code trước S3
    new = _payload()
    state_file(new)
    assert old.resolve('duckdb')['release_id'] == RID         # DuckDB: đọc state.json mới
    assert old.allowed_versions(new, ALLOWED_RELATIONS) >= {f'r_{RID}_reporting.rpt_build_info'}
    old_guard = _old_module('guarded_truoc_s3', 'apps/retail_app/dwh/guarded.py', releases=old)
    old.reset()                                               # Databricks: guard cũ đọc registry mới qua cursor
    allowed, required = old_guard._release_scope(_Cursor(new), ALLOWED_RELATIONS, 'retail_lab')
    assert old.current()['release_id'] == RID and f'r_{RID}_reporting.rpt_build_info' in allowed
    monkeypatch.delenv('RETAIL_RELEASE_MODE')                 # chế độ cũ của guard cũ
    old.reset()
    allowed, _ = old_guard._release_scope(_Cursor(new), ALLOWED_RELATIONS, 'retail_lab')
    assert old.current() is None and f'r_{RID}_reporting.rpt_build_info' in allowed


# --- AppTest trang Sức khỏe ---

def _open(monkeypatch, backend='duckdb'):
    monkeypatch.setenv('RETAIL_BACKEND', backend)
    st.cache_data.clear()
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    at.switch_page(PAGE).run()
    assert not at.exception, at.exception
    return at


def _metrics(at) -> dict:
    return {m.label: m.value for m in at.metric}


def test_trang_suc_khoe_che_do_cu_ghi_khong_ap_dung(monkeypatch):
    monkeypatch.delenv('RETAIL_RELEASE_MODE', raising=False)
    releases.reset()
    at = _open(monkeypatch)
    assert any('Không áp dụng' in c.value for c in at.caption)
    assert 'Mã bản' not in _metrics(at)


@pytest.fixture
def ban_that(state_file):
    """Bản active của pipeline local (artifact thật), ghi vào state tạm; duckdb_path tuyệt đối thay artifact_path."""
    path = ROOT / 'warehouse/pipeline/state.json'
    if not path.exists():
        pytest.skip('chưa có bản dữ liệu do pipeline publish (warehouse/pipeline/state.json)')
    payload = json.loads(path.read_text(encoding='utf-8'))['payload']
    rec = dict(payload['releases'][payload['active']])
    if rec.get('artifact_path'):
        rec['duckdb_path'] = str((path.parent / rec.pop('artifact_path')).resolve())
    if not Path(rec['duckdb_path']).exists():
        pytest.skip('artifact của bản active không có trên máy')

    def write(since):
        p = {'active': rec['release_id'], 'releases': {rec['release_id']: rec}}
        if since is not None:
            p['active_since'] = {'release_id': rec['release_id'], 'at': since}
        state_file(p)
        return rec
    return write


def test_trang_suc_khoe_versioned_registry_moi_hien_tuoi_ban(monkeypatch, ban_that):
    hai_gio_truoc = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2, minutes=5)).strftime('%Y-%m-%dT%H:%M:%SZ')
    rec = ban_that(hai_gio_truoc)
    m = _metrics(_open(monkeypatch))
    assert m['Mã bản'] == rec['release_id'][:12] and m['Snapshot nguồn'] == rec['snapshot_id']
    assert m['Tuổi của bản'] == '2 giờ' and m['Công bố lúc'] != 'chưa ghi'


def test_trang_suc_khoe_versioned_registry_cu_van_chay(monkeypatch, ban_that):
    rec = ban_that(None)                                      # registry cũ: chưa có active_since
    m = _metrics(_open(monkeypatch))
    assert m['Mã bản'] == rec['release_id'][:12]
    assert m['Công bố lúc'] == 'chưa ghi' and m['Tuổi của bản'] == '–'
