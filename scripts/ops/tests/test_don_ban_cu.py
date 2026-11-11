"""Kiểm dọn bản bằng cloud giả và Registry thật trong thư mục tạm."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from scripts.ops import don_ban_cu as don
from scripts.pipeline.state import Registry


ACTIVE, ROLLBACK, OLD, EXTRA = ('a' * 24, 'b' * 24, 'c' * 24, 'd' * 24)


def record(rid, code='code-one'):
    return {'release_id': rid, 'status': 'ready', 'schema': f'r_{rid}_reporting',
            'snapshot_id': f'snapshot-{rid[0]}', 'code_version': code, 'run_id': f'run-{rid[0]}'}


def state():
    return {'active': ACTIVE, 'active_since': {'release_id': ACTIVE, 'at': '2026-11-02T00:00:00Z'},
            'releases': {ACTIVE: record(ACTIVE), ROLLBACK: record(ROLLBACK), OLD: record(OLD)},
            'dich_rollback': {'release_id': ROLLBACK, 'dat_luc': '2026-11-02T00:00:00Z'},
            'da_xoa': {}, 'extension_marker': {'giữ_nguyên': True}}


class FakeCloud:
    catalog = 'retail_lab'

    def __init__(self, releases=(ACTIVE, ROLLBACK, OLD)):
        self.schemas = set().union(*(don.schema_set(rid) for rid in releases))
        self.tables = [(f'r_{rid}_reporting', 'BASE TABLE') for rid in releases]
        self.views, self.sql, self.events = [], [], []
        self.fail_drop_number = None
        self.retain_schema = None
        self.drop_count = 0
        self.quota = (245, 500)
        self.closed = False

    def query(self, statement, params=()):
        self.sql.append(statement)
        if statement.startswith('SHOW SCHEMAS IN '):
            return ['databaseName'], [(name,) for name in sorted(self.schemas)]
        if '.information_schema.tables' in statement:
            return ['table_schema', 'table_type'], list(self.tables)
        if '.information_schema.views' in statement:
            return ['table_schema', 'table_name', 'view_definition'], list(self.views)
        if statement.startswith('DROP SCHEMA IF EXISTS '):
            self.drop_count += 1
            self.events.append('drop')
            if self.fail_drop_number == self.drop_count:
                raise RuntimeError('drop failed')
            name = statement.split()[4].split('.', 1)[1]
            if name != self.retain_schema:
                self.schemas.discard(name)
            self.tables = [row for row in self.tables if row[0] != name]
            self.views = [row for row in self.views if row[0] != name]
            return [], []
        raise AssertionError(f'SQL ngoài hợp đồng: {statement}')

    def quota_info(self):
        return self.quota

    def close(self):
        self.closed = True


def setup(tmp_path, payload=None):
    registry = Registry(tmp_path, sql=None)
    registry.initialize()
    registry.save(registry.read(), payload or state())
    return registry


def run(tmp_path, cloud, *args, registry_factory=None):
    factory = registry_factory or (lambda root, sql: Registry(root, sql=None))
    return don.main(['--root', str(tmp_path), '--catalog', cloud.catalog, *args],
                    cloud_factory=lambda: cloud, registry_factory=factory)


def drops(cloud):
    return [sql for sql in cloud.sql if sql.startswith('DROP SCHEMA')]


def context(tmp_path, rid, stage='built', age_hours=3):
    started = (datetime.now(timezone.utc) - timedelta(hours=age_hours)).isoformat()
    path = tmp_path / 'runs' / f'run-{rid[0]}' / 'context.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'release_id': rid, 'stage': stage, 'started_at': started}), encoding='utf-8')


def assert_blocked(tmp_path, cloud, registry, *args):
    before = registry.read()
    assert run(tmp_path, cloud, *args, '--thuc-hien') == 2
    assert not drops(cloud)
    assert registry.read() == before


def test_chi_doc_va_ke_hoach_khong_ghi(tmp_path, capsys):
    registry, cloud = setup(tmp_path), FakeCloud()
    before = registry.read()
    assert run(tmp_path, cloud) == 0
    assert run(tmp_path, cloud, '--xoa', OLD) == 0
    output = capsys.readouterr().out
    assert f'{ACTIVE} | active' in output
    assert f'{ROLLBACK} | dich_rollback' in output
    assert f'{OLD} | ready' in output
    assert 'Tổng bảng trong catalog: 3' in output
    assert 'Quota metastore: 245/500; chỗ còn lại: 255' in output
    assert 'Không ghi gì' in output
    assert not drops(cloud)
    assert registry.read() == before


def test_bao_cao_quota_khong_doc_duoc_va_canh_bao(tmp_path, capsys):
    setup(tmp_path)
    cloud = FakeCloud()
    cloud.quota = None
    assert run(tmp_path, cloud) == 0
    assert 'Không đọc được quota' in capsys.readouterr().out
    cloud.quota = (450, 500)
    assert run(tmp_path, cloud) == 0
    assert 'CẢNH BÁO: còn dưới 100' in capsys.readouterr().out


def test_bao_cao_vai_tro_mat_schema_mo_coi_dang_do_va_code_khac(tmp_path, capsys):
    payload = state()
    payload['releases'][ROLLBACK]['code_version'] = 'code-two'
    setup(tmp_path, payload)
    cloud = FakeCloud((ACTIVE, ROLLBACK, EXTRA))
    context(tmp_path, EXTRA)
    assert run(tmp_path, cloud) == 0
    output = capsys.readouterr().out
    assert f'{OLD} | mat_schema' in output
    assert f'{EXTRA} | dang_do' in output
    assert 'code_version đích rollback khác active' in output
    (tmp_path / 'runs' / 'run-d' / 'context.json').unlink()
    assert run(tmp_path, cloud) == 0
    assert f'{EXTRA} | mo_coi' in capsys.readouterr().out


def test_dat_dich_rollback_va_tu_choi_dich_khong_hop_le(tmp_path):
    payload = state()
    del payload['dich_rollback']
    registry, cloud = setup(tmp_path, payload), FakeCloud()
    assert run(tmp_path, cloud, '--dat-dich-rollback', ROLLBACK) == 0
    assert registry.read()['payload']['dich_rollback']['release_id'] == ROLLBACK
    before = registry.read()
    assert run(tmp_path, cloud, '--dat-dich-rollback', ACTIVE) == 2
    assert registry.read() == before
    cloud.schemas.remove(f'r_{ROLLBACK}_ops')
    assert run(tmp_path, cloud, '--dat-dich-rollback', ROLLBACK) == 2
    assert registry.read() == before


def test_g1_active_khong_duoc_xoa(tmp_path, capsys):
    registry, cloud = setup(tmp_path), FakeCloud()
    assert_blocked(tmp_path, cloud, registry, '--xoa', ACTIVE)
    assert 'G1' in capsys.readouterr().err
    _, reasons = don.plan_deletion(state(), cloud.schemas, [], [], [ACTIVE], now=datetime.now(timezone.utc))
    assert any(reason.startswith('G1') for reason in reasons)


def test_g1_active_thieu_trong_registry(tmp_path, capsys):
    payload = state()
    payload['active'] = None
    registry, cloud = setup(tmp_path, payload), FakeCloud()
    assert_blocked(tmp_path, cloud, registry, '--xoa', OLD)
    assert 'G1' in capsys.readouterr().err


def test_g2_dich_rollback_khong_duoc_xoa(tmp_path, capsys):
    registry, cloud = setup(tmp_path), FakeCloud()
    assert_blocked(tmp_path, cloud, registry, '--xoa', ROLLBACK)
    assert 'G2' in capsys.readouterr().err
    _, reasons = don.plan_deletion(state(), cloud.schemas, [], [], [ROLLBACK], now=datetime.now(timezone.utc))
    assert any(reason.startswith('G2') for reason in reasons)


def test_g2_chua_co_dich_hop_le(tmp_path, capsys):
    payload = state()
    del payload['dich_rollback']
    registry, cloud = setup(tmp_path, payload), FakeCloud()
    assert_blocked(tmp_path, cloud, registry, '--xoa', OLD)
    assert 'G2' in capsys.readouterr().err


def test_g3_active_thieu_schema(tmp_path, capsys):
    registry, cloud = setup(tmp_path), FakeCloud()
    cloud.schemas.remove(f'r_{ACTIVE}_ops')
    assert_blocked(tmp_path, cloud, registry, '--xoa', OLD)
    assert 'G3' in capsys.readouterr().err


def test_g4_context_moi_chua_ket_thuc(tmp_path, capsys):
    registry, cloud = setup(tmp_path), FakeCloud()
    context(tmp_path, EXTRA, age_hours=0.5)
    assert_blocked(tmp_path, cloud, registry, '--xoa', OLD)
    assert 'G4' in capsys.readouterr().err


def test_g4_khong_the_bo_qua_bang_co_cho_xoa_ban_do(tmp_path, capsys):
    registry, cloud = setup(tmp_path), FakeCloud()
    context(tmp_path, OLD, age_hours=0.5)
    assert_blocked(tmp_path, cloud, registry, '--xoa', OLD, '--cho-xoa-ban-do', OLD)
    assert 'G4' in capsys.readouterr().err


@pytest.mark.parametrize('started', [None, 'khong-phai-ngay-gio'])
def test_g4_started_at_thieu_hoac_hong_chan_xoa(tmp_path, capsys, started):
    registry, cloud = setup(tmp_path), FakeCloud()
    context(tmp_path, EXTRA)
    path = tmp_path / 'runs' / 'run-d' / 'context.json'
    saved = json.loads(path.read_text(encoding='utf-8'))
    if started is None:
        del saved['started_at']
    else:
        saved['started_at'] = started
    path.write_text(json.dumps(saved), encoding='utf-8')
    assert_blocked(tmp_path, cloud, registry, '--xoa', OLD)
    assert 'G4' in capsys.readouterr().err


def test_g4_gio_khong_mui_duoc_hieu_la_utc(monkeypatch):
    now = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)
    context = {'release_id': EXTRA, 'stage': 'built', 'started_at': '2026-11-02 09:30:00'}

    class StrictDatetime(datetime):
        @classmethod
        def fromisoformat(cls, value):
            parsed = datetime.fromisoformat(value)
            return cls(parsed.year, parsed.month, parsed.day, parsed.hour, parsed.minute,
                       parsed.second, tzinfo=parsed.tzinfo)

        def astimezone(self, zone=None):
            if self.tzinfo is None:
                raise AssertionError('Không được chuyển múi giờ của thời điểm không có tzinfo')
            return super().astimezone(zone)

    monkeypatch.setattr(don, 'datetime', StrictDatetime)
    assert list(don.recent_unfinished([context], now)) == [context]


def test_context_da_validated_khong_bi_coi_la_dang_chay(tmp_path):
    registry, cloud = setup(tmp_path), FakeCloud()
    context(tmp_path, OLD, stage='validated', age_hours=0.1)
    assert run(tmp_path, cloud, '--xoa', OLD, '--thuc-hien') == 0
    assert OLD in registry.read()['payload']['da_xoa']


def test_g5_context_cu_can_co_ngoai_le_dung_ma(tmp_path, capsys):
    registry, cloud = setup(tmp_path), FakeCloud()
    context(tmp_path, OLD, age_hours=3)
    assert_blocked(tmp_path, cloud, registry, '--xoa', OLD)
    assert 'G5' in capsys.readouterr().err
    assert run(tmp_path, cloud, '--xoa', OLD, '--cho-xoa-ban-do', OLD, '--thuc-hien') == 0
    assert OLD in registry.read()['payload']['da_xoa']


def test_g5_co_cho_mot_ma_khong_mo_cho_ban_do_khac(tmp_path, capsys):
    payload = state()
    payload['releases'][EXTRA] = record(EXTRA)
    registry, cloud = setup(tmp_path, payload), FakeCloud((ACTIVE, ROLLBACK, OLD, EXTRA))
    context(tmp_path, OLD)
    context(tmp_path, EXTRA)
    assert_blocked(tmp_path, cloud, registry, '--xoa', OLD, '--xoa', EXTRA,
                   '--cho-xoa-ban-do', OLD)
    assert f'G5: context chưa kết thúc tham chiếu bản {EXTRA}' in capsys.readouterr().err


def test_g6_view_ngoai_bo_tham_chieu(tmp_path, capsys):
    registry, cloud = setup(tmp_path), FakeCloud()
    cloud.views.append(('default', 'outside', f'SELECT * FROM retail_lab.r_{OLD}_reporting.fact'))
    assert_blocked(tmp_path, cloud, registry, '--xoa', OLD)
    assert 'G6' in capsys.readouterr().err


def test_g6_view_an_dinh_nghia_thi_chan(tmp_path, capsys):
    registry, cloud = setup(tmp_path), FakeCloud()
    cloud.views.append(('default', 'hidden', None))
    assert_blocked(tmp_path, cloud, registry, '--xoa', OLD)
    assert 'G6' in capsys.readouterr().err


def test_g7_khong_lay_duoc_writer_lock(tmp_path, monkeypatch, capsys):
    registry, cloud = setup(tmp_path), FakeCloud()

    @contextmanager
    def denied(_):
        raise OSError('busy')
        yield

    monkeypatch.setattr(don, 'writer_lock', denied)
    assert_blocked(tmp_path, cloud, registry, '--xoa', OLD)
    assert 'G7' in capsys.readouterr().err


def test_lenh_nhieu_ban_co_mot_ban_bi_chan_khong_xoa_gi(tmp_path):
    registry, cloud = setup(tmp_path), FakeCloud()
    assert_blocked(tmp_path, cloud, registry, '--xoa', OLD, '--xoa', ACTIVE)


@pytest.mark.parametrize('rid', ['r_' + OLD, OLD[:-1], OLD.upper(), 'tat_ca'])
def test_ma_ban_khong_dung_bi_tu_choi(tmp_path, capsys, rid):
    registry, cloud = setup(tmp_path), FakeCloud()
    before = registry.read()
    assert run(tmp_path, cloud, '--xoa', rid, '--thuc-hien') == 1
    assert registry.read() == before
    assert not drops(cloud)
    assert capsys.readouterr().err.strip() == 'Mã bản phải đúng 24 ký tự hex thường, không có tiền tố'


def test_catalog_sai_bi_tu_choi(tmp_path, capsys):
    registry, cloud = setup(tmp_path), FakeCloud()
    before = registry.read()
    assert don.main(['--root', str(tmp_path), '--catalog', 'demo', '--xoa', OLD, '--thuc-hien'],
                    cloud_factory=lambda: cloud,
                    registry_factory=lambda root, sql: Registry(root, sql=None)) == 1
    assert registry.read() == before
    assert cloud.sql == []
    assert capsys.readouterr().err.strip() == '--catalog không khớp catalog của kết nối writer'


def test_loi_dau_vao_in_ly_do_nhung_loi_driver_giu_kin_thong_diep(tmp_path, capsys):
    setup(tmp_path)
    cloud = FakeCloud()
    assert run(tmp_path, cloud, '--thuc-hien') == 1
    assert capsys.readouterr().err.strip() == '--thuc-hien cần --xoa'
    assert don.main(['--root', str(tmp_path), '--catalog', 'sai-ten!'],
                    cloud_factory=lambda: cloud) == 1
    assert capsys.readouterr().err.strip() == 'Tên catalog không hợp lệ'

    class FailingCloud(FakeCloud):
        def query(self, statement, params=()):
            raise ValueError('token-rieng-khong-duoc-in')

    failing = FailingCloud()
    assert run(tmp_path, failing) == 1
    assert capsys.readouterr().err.strip() == 'Lỗi: ValueError'


def test_chi_drop_sau_ten_dung_mau(tmp_path):
    setup(tmp_path)
    cloud = FakeCloud()
    near = {f'r_{OLD}_reporting_tmp', f'r_{OLD}x_raw', 'retail_control',
            'pipeline_landing', 'default', 'information_schema'}
    cloud.schemas |= near
    assert run(tmp_path, cloud, '--xoa', OLD, '--thuc-hien') == 0
    names = {sql.split()[4].split('.', 1)[1] for sql in drops(cloud)}
    assert names == don.schema_set(OLD)
    assert cloud.schemas & near == near
    assert len(drops(cloud)) == 6


def test_drop_truoc_save_va_giu_sau_khi_drop_loi(tmp_path):
    registry, cloud = setup(tmp_path), FakeCloud()
    before = registry.read()
    cloud.fail_drop_number = 3
    assert run(tmp_path, cloud, '--xoa', OLD, '--thuc-hien') == 1
    assert registry.read() == before
    cloud.fail_drop_number = None
    assert run(tmp_path, cloud, '--xoa', OLD, '--thuc-hien') == 0
    assert OLD not in registry.read()['payload']['releases']


def test_drop_thanh_cong_nhung_schema_con_thi_khong_ghi_registry(tmp_path):
    registry, cloud = setup(tmp_path), FakeCloud()
    before = registry.read()
    cloud.retain_schema = f'r_{OLD}_reporting'
    assert run(tmp_path, cloud, '--xoa', OLD, '--thuc-hien') == 1
    assert len(drops(cloud)) == 6
    assert cloud.retain_schema in cloud.schemas
    assert registry.read() == before


def test_moi_drop_xay_ra_truoc_save(tmp_path):
    setup(tmp_path)
    cloud = FakeCloud()

    class LoggedRegistry(Registry):
        def save(self, before, payload):
            cloud.events.append('save')
            return super().save(before, payload)

    assert run(tmp_path, cloud, '--xoa', OLD, '--thuc-hien',
               registry_factory=lambda root, sql: LoggedRegistry(root, sql=None)) == 0
    assert cloud.events == ['drop'] * 6 + ['save']


def test_payload_va_hop_dong_app_sau_xoa(tmp_path, monkeypatch):
    original = state()
    registry, cloud = setup(tmp_path, original), FakeCloud()
    assert run(tmp_path, cloud, '--xoa', OLD, '--thuc-hien') == 0
    payload = registry.read()['payload']
    assert set(payload) == set(original)
    assert payload['active'] == original['active']
    assert payload['active_since'] == original['active_since']
    assert payload['dich_rollback'] == original['dich_rollback']
    assert payload['extension_marker'] == original['extension_marker']
    assert OLD not in payload['releases']
    assert payload['da_xoa'][OLD]['release_id'] == OLD
    assert payload['da_xoa'][OLD]['snapshot_id'] == original['releases'][OLD]['snapshot_id']
    assert payload['da_xoa'][OLD]['schema'] == original['releases'][OLD]['schema']
    assert payload['da_xoa'][OLD]['xoa_luc']
    assert all(rec['status'] == 'ready' for rec in payload['releases'].values())
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / 'apps' / 'retail_app'))
    from dwh import releases

    assert releases.choose(payload)['release_id'] == ACTIVE
    logical = {'reporting.rpt_build_info'}
    allowed = releases.allowed_versions(payload, logical)
    assert f'r_{ACTIVE}_reporting.rpt_build_info' in allowed
    assert f'r_{ROLLBACK}_reporting.rpt_build_info' in allowed
    assert f'r_{OLD}_reporting.rpt_build_info' not in allowed


def test_mat_schema_duoc_xoa_va_lan_sau_idempotent(tmp_path, capsys):
    registry, cloud = setup(tmp_path), FakeCloud((ACTIVE, ROLLBACK))
    assert run(tmp_path, cloud, '--xoa', OLD, '--thuc-hien') == 0
    assert not drops(cloud)
    first = registry.read()
    assert run(tmp_path, cloud, '--xoa', OLD, '--thuc-hien') == 0
    assert registry.read() == first
    assert 'Đã xóa trước đó' in capsys.readouterr().out


def test_ban_da_xoa_truoc_do_luon_la_noop(tmp_path):
    payload = state()
    saved = payload['releases'].pop(OLD)
    payload['da_xoa'][OLD] = {'release_id': OLD, 'snapshot_id': saved['snapshot_id']}
    payload['active'] = None  # Không cần kiểm quy tắc giữ bản khi không có thao tác xóa.
    registry, cloud = setup(tmp_path, payload), FakeCloud((ACTIVE, ROLLBACK))
    before = registry.read()
    assert run(tmp_path, cloud, '--xoa', OLD, '--thuc-hien') == 0
    assert registry.read() == before
    assert not drops(cloud)


def test_compare_and_swap_thu_lai_mot_lan_khong_ghi_de(tmp_path):
    setup(tmp_path)
    cloud = FakeCloud()

    class RacingRegistry(Registry):
        attempts = 0

        def save(self, before, payload):
            type(self).attempts += 1
            if type(self).attempts == 1:
                changed = dict(before['payload'])
                changed['competitor'] = 'giữ nguyên'
                Registry.save(self, before, changed)
                raise RuntimeError('competing writer')
            return super().save(before, payload)

    assert run(tmp_path, cloud, '--xoa', OLD, '--thuc-hien',
               registry_factory=lambda root, sql: RacingRegistry(root, sql=None)) == 0
    assert RacingRegistry.attempts == 2
    payload = Registry(tmp_path).read()['payload']
    assert payload['competitor'] == 'giữ nguyên'
    assert OLD not in payload['releases']


def test_compare_and_swap_kiem_lai_quy_tac_giu_ban_truoc_lan_save_hai(tmp_path, capsys):
    payload = state()
    payload['releases'][EXTRA] = record(EXTRA)
    registry, cloud = setup(tmp_path, payload), FakeCloud()

    class RacingRegistry(Registry):
        attempts = 0

        def save(self, before, updated):
            type(self).attempts += 1
            if type(self).attempts == 1:
                changed = dict(before['payload'])
                changed['active'] = EXTRA  # Bản active mới thiếu sáu schema: G3.
                Registry.save(self, before, changed)
                raise RuntimeError('competing writer')
            return super().save(before, updated)

    assert run(tmp_path, cloud, '--xoa', OLD, '--thuc-hien',
               registry_factory=lambda root, sql: RacingRegistry(root, sql=None)) == 2
    assert RacingRegistry.attempts == 1
    latest = registry.read()['payload']
    assert latest['active'] == EXTRA
    assert OLD in latest['releases']
    assert OLD not in latest['da_xoa']
    assert 'G3' in capsys.readouterr().err


def test_compare_and_swap_doi_hai_lan_tra_ma_mot(tmp_path):
    setup(tmp_path)
    cloud = FakeCloud()

    class RacingRegistry(Registry):
        attempts = 0

        def save(self, before, payload):
            type(self).attempts += 1
            changed = dict(before['payload'])
            changed[f'competitor_{type(self).attempts}'] = True
            Registry.save(self, before, changed)
            raise RuntimeError('competing writer')

    assert run(tmp_path, cloud, '--xoa', OLD, '--thuc-hien',
               registry_factory=lambda root, sql: RacingRegistry(root, sql=None)) == 1
    assert RacingRegistry.attempts == 2
    assert OLD in Registry(tmp_path).read()['payload']['releases']


def test_save_da_thanh_cong_nhung_mat_ack_khong_ghi_de_ban_da_xoa(tmp_path):
    setup(tmp_path)
    cloud = FakeCloud()

    class LostAckRegistry(Registry):
        attempts = 0

        def save(self, before, payload):
            type(self).attempts += 1
            Registry.save(self, before, payload)
            raise RuntimeError('lost ACK')

    assert run(tmp_path, cloud, '--xoa', OLD, '--thuc-hien',
               registry_factory=lambda root, sql: LostAckRegistry(root, sql=None)) == 0
    assert LostAckRegistry.attempts == 1
    deleted = Registry(tmp_path).read()['payload']['da_xoa'][OLD]
    assert deleted['snapshot_id'] == state()['releases'][OLD]['snapshot_id']


def test_invalid_remaining_status_blocks_save_after_drop(tmp_path):
    payload = state()
    payload['releases'][ACTIVE]['status'] = 'other'
    registry, cloud = setup(tmp_path, payload), FakeCloud()
    before = registry.read()
    assert run(tmp_path, cloud, '--xoa', OLD, '--thuc-hien') == 2
    assert registry.read() == before


def test_cloud_gia_duoc_dong_va_khong_in_payload(tmp_path, capsys):
    setup(tmp_path)
    cloud = FakeCloud()
    assert run(tmp_path, cloud, '--xoa', OLD) == 0
    assert cloud.closed
    output = capsys.readouterr().out
    assert 'extension_marker' not in output
    assert 'DATABRICKS_' not in output


def test_goi_y_khoi_phuc_can_hoi_de_cho_tung_schema(tmp_path, capsys):
    setup(tmp_path)
    cloud = FakeCloud()
    assert run(tmp_path, cloud, '--xoa', OLD, '--thuc-hien') == 0
    output = capsys.readouterr().out
    assert 'chưa kiểm chứng sau DROP SCHEMA CASCADE; hỏi DE trước khi làm' in output
    assert 'phải làm cho từng schema' in output
    for suffix in don.SUFFIXES:
        assert f'UNDROP TABLE retail_lab.r_{OLD}_{suffix}.<ten_bang>' in output
    assert output.count('UNDROP TABLE') == 6


def test_g8_dashboard_target_blocks_all_drops(tmp_path, capsys):
    payload = state()
    payload['dashboard'] = OLD
    registry, cloud = setup(tmp_path, payload), FakeCloud((ACTIVE, ROLLBACK, OLD, EXTRA))
    _, reasons = don.plan_deletion(payload, cloud.schemas, [], [], [OLD, EXTRA],
                                   now=datetime.now(timezone.utc))
    assert 'G8: yêu cầu xóa bản đang trên dashboard' in reasons
    assert_blocked(tmp_path, cloud, registry, '--xoa', EXTRA, '--xoa', OLD)
    assert 'G8: yêu cầu xóa bản đang trên dashboard' in capsys.readouterr().err


@pytest.mark.parametrize('pointer', [EXTRA, 'bad', '', 123, [], {}])
def test_g8_invalid_pointer_blocks_every_target(tmp_path, capsys, pointer):
    payload = state()
    payload['dashboard'] = pointer
    registry, cloud = setup(tmp_path, payload), FakeCloud()
    _, reasons = don.plan_deletion(payload, cloud.schemas, [], [], [OLD],
                                   now=datetime.now(timezone.utc))
    reason = 'G8: con trỏ dashboard không trỏ tới bản hợp lệ; trả dashboard trước khi xóa'
    assert reason in reasons
    assert_blocked(tmp_path, cloud, registry, '--xoa', OLD)
    assert reason in capsys.readouterr().err


def test_g8_non_hex_pointer_in_releases_is_invalid(tmp_path):
    payload = state()
    payload['dashboard'] = 'bad'
    payload['releases']['bad'] = record('bad')
    cloud = FakeCloud()
    cloud.schemas |= don.schema_set('bad')
    _, reasons = don.plan_deletion(payload, cloud.schemas, [], [], [OLD],
                                   now=datetime.now(timezone.utc))
    assert reasons == ('G8: con trỏ dashboard không trỏ tới bản hợp lệ; trả dashboard trước khi xóa',)


def test_g8_dashboard_missing_schema_blocks_unrelated_deletion(tmp_path, capsys):
    payload = state()
    payload['dashboard'] = EXTRA
    payload['releases'][EXTRA] = record(EXTRA)
    registry = setup(tmp_path, payload)
    cloud = FakeCloud((ACTIVE, ROLLBACK, OLD, EXTRA))
    cloud.schemas.remove(f'r_{EXTRA}_ops')
    _, reasons = don.plan_deletion(payload, cloud.schemas, [], [], [OLD],
                                   now=datetime.now(timezone.utc))
    assert reasons == ('G8: bản trên dashboard không còn đủ sáu schema',)
    assert_blocked(tmp_path, cloud, registry, '--xoa', OLD)
    assert 'G8: bản trên dashboard không còn đủ sáu schema' in capsys.readouterr().err


@pytest.mark.parametrize('with_none', [False, True])
def test_g8_no_pointer_keeps_old_plan(tmp_path, with_none):
    original = state()
    payload = state()
    if with_none:
        payload['dashboard'] = None
    cloud = FakeCloud()
    now = datetime.now(timezone.utc)
    assert don.plan_deletion(payload, cloud.schemas, [], [], [OLD], now=now) == (
        don.plan_deletion(original, cloud.schemas, [], [], [OLD], now=now))
    don.checked_payload(payload)
    registry = setup(tmp_path, payload)
    assert run(tmp_path, cloud, '--xoa', OLD, '--thuc-hien') == 0
    assert OLD not in registry.read()['payload']['releases']


@pytest.mark.parametrize('pointer', [EXTRA, '', 123, [], {}])
def test_g8_checked_payload_independent_guard(pointer):
    payload = state()
    payload['dashboard'] = pointer
    with pytest.raises(don.Blocked, match='dashboard'):
        don.checked_payload(payload)


def test_g8_deleting_other_release_preserves_dashboard(tmp_path):
    payload = state()
    payload['dashboard'] = ROLLBACK
    payload['dashboard_since'] = {'release_id': ROLLBACK, 'at': '2026-11-10T01:00:00Z'}
    registry, cloud = setup(tmp_path, payload), FakeCloud()
    assert run(tmp_path, cloud, '--xoa', OLD, '--thuc-hien') == 0
    updated = registry.read()['payload']
    assert updated['dashboard'] == ROLLBACK
    assert updated['dashboard_since'] == payload['dashboard_since']
    assert OLD not in updated['releases']
    don.checked_payload(updated)
    remaining = don.removed_payload(payload, [OLD], datetime.now(timezone.utc))
    assert remaining['dashboard'] == ROLLBACK
    assert remaining['dashboard_since'] == payload['dashboard_since']
    with pytest.raises(don.Blocked, match='dashboard'):
        don.removed_payload(payload, [ROLLBACK], datetime.now(timezone.utc))


def test_g8_pointer_changes_while_waiting_for_lock(tmp_path, monkeypatch, capsys):
    registry, cloud = setup(tmp_path), FakeCloud()
    before = registry.read()
    original_read = registry.read
    calls = []
    held = []
    real_lock = don.deletion_lock

    def read():
        calls.append(1)
        if len(calls) == 1:
            return original_read()
        assert held, 'Phải kiểm lại registry trong khóa'
        payload = dict(before['payload'], dashboard=OLD)
        return dict(before, payload=payload)

    @contextmanager
    def lock(root):
        with real_lock(root):
            held.append(True)
            try:
                yield
            finally:
                held.pop()

    monkeypatch.setattr(registry, 'read', read)
    monkeypatch.setattr(don, 'deletion_lock', lock)
    # Ảnh trước khi chờ khóa vẫn cho phép xóa.
    _, reasons = don.plan_deletion(registry.read()['payload'], cloud.schemas, [], [], [OLD],
                                   now=datetime.now(timezone.utc))
    assert not reasons
    assert run(tmp_path, cloud, '--xoa', OLD, '--thuc-hien',
               registry_factory=lambda root, sql: registry) == 2
    assert len(calls) == 2 and not drops(cloud)
    assert original_read() == before
    assert 'G8: yêu cầu xóa bản đang trên dashboard' in capsys.readouterr().err


@pytest.mark.parametrize('pointer', [None, OLD, ROLLBACK, ACTIVE])
def test_g8_report_pointer_and_role_priority(tmp_path, capsys, pointer):
    payload = state()
    payload['dashboard'] = pointer
    setup(tmp_path, payload)
    cloud = FakeCloud()
    assert run(tmp_path, cloud) == 0
    output = capsys.readouterr().out
    lines = output.splitlines()
    total = lines.index('Tổng bảng trong catalog: 3')
    assert lines[total + 1] == 'Con trỏ dashboard: ' + (pointer or 'theo bản số thật')
    assert f'{ACTIVE} | active |' in output
    if pointer and pointer != ACTIVE:
        line = next(line for line in lines if line.startswith(pointer + ' |'))
        assert f'{pointer} | dashboard |' in line
        assert 'G8: yêu cầu xóa bản đang trên dashboard' in line
        if pointer == ROLLBACK:
            assert 'G2: yêu cầu xóa đích rollback' in line
