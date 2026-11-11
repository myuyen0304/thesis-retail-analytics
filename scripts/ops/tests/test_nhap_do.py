"""L2: thử poller bằng KhoDia, quota và SQL giả; không kết nối cloud."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.ops import nhap_do as poll
from ui.kho_dot import KhoDia
from scripts.pipeline.state import Registry

R1 = '20261109T010000Z_abcdef_dot'
R2 = '20261109T010001Z_abcdef_dot'
RID = 'a' * 24
BASE = b'file,content\n1,2\n'


class FakeCatalog:
    def __init__(self, count=317):
        self.count = count
        self.schemas = SimpleNamespace(list=self.schema_list)
        self.tables = SimpleNamespace(list=self.table_list)
        self.calls = []

    def schema_list(self, *, catalog_name):
        self.calls.append(('schemas', catalog_name))
        return [SimpleNamespace(name='reporting')]

    def table_list(self, *, catalog_name, schema_name):
        self.calls.append(('tables', catalog_name, schema_name))
        return [SimpleNamespace(table_type='VIEW' if i % 2 else 'MANAGED') for i in range(self.count)]


class FakeCloud:
    def __init__(self, state):
        self.state = state
        self.closed = False
        self.calls = []

    def query(self, sql, params=()):
        self.calls.append(sql)
        assert sql.startswith('select version, payload from retail_control.state')
        return [], [('version', json.dumps(self.state))]

    def close(self):
        self.closed = True


@pytest.fixture
def env(tmp_path, monkeypatch):
    root = tmp_path / 'pipeline'
    kho = KhoDia(tmp_path / 'volume')
    catalog = FakeCatalog()
    monkeypatch.setattr(poll.dot, 'classify', lambda folder, data: ({'ma_dot': 'd' * 12, 'files': []}, {}))
    return SimpleNamespace(root=root, kho=kho, catalog=catalog, calls=[])


def request(env, rid=R1, content=BASE, *, files=None, status='da_gui', ma=None):
    files = files if files is not None else [{'ten': 'orders.csv', 'so_byte': len(content),
                                               'sha256': hashlib.sha256(content).hexdigest()}]
    folder = poll.request_path(rid)
    env.kho.ghi_moi(folder + '/file/orders.csv', content)
    env.kho.ghi_moi(folder + '/yeu_cau.json', json.dumps({'id': rid, 'loai': 'dot',
        'files': files, 'nguoi_gui': 'owner'}).encode())
    env.kho.ghi_json_so_tiep(folder + '/su_kien', {'toi': 'da_gui', 'ai': 'owner'})
    for state in {'dang_kiem': ['dang_kiem'], 'cho_chay': ['dang_kiem', 'cho_chay'], 'het_cho': ['dang_kiem', 'het_cho'],
                  'dang_chay': ['dang_kiem', 'cho_chay', 'dang_chay'],
                  'da_kiem': ['dang_kiem', 'cho_chay', 'dang_chay', 'da_kiem'],
                  'tren_dashboard': ['dang_kiem', 'cho_chay', 'dang_chay', 'da_kiem', 'tren_dashboard']} .get(status, []):
        extra = {}
        if state in ('cho_chay', 'het_cho'):
            extra['ma_dot'] = ma or 'd' * 12
        if state == 'dang_chay':
            extra.update(airflow_run_id='dot_' + rid + '_1', pipeline_run_id='dot_' + rid + '_1',
                         conf={'request_id': rid})
        if state == 'da_kiem':
            extra['release_id'] = RID
        env.kho.ghi_json_so_tiep(folder + '/su_kien', {'toi': state, 'ai': 'airflow', **extra})
    return rid


def state(env, rid=R1):
    return poll._requests(env.kho)[rid]


def test_upload_then_classify_and_quota_boundary(env):
    request(env)
    env.kho.ghi_moi(poll.request_path(R1) + '/file/stray.csv', b'not listed')
    result = poll.quet(env.kho, env.catalog, root=env.root)
    assert result == {'dang_chay': []}
    assert state(env)['trang_thai'] == 'cho_chay'
    assert poll._ma_dot(state(env)) == 'd' * 12
    assert list((env.root / 'nhap' / R1 / 'file').iterdir())[0].name == 'orders.csv'
    assert env.catalog.calls[0] == ('schemas', 'retail_lab')


@pytest.mark.parametrize('used,expected', [(317, 'cho_chay'), (318, 'het_cho')])
def test_quota_boundary_and_recheck(env, used, expected):
    request(env, status='dang_kiem')
    env.catalog.count = used
    poll.quet(env.kho, env.catalog, root=env.root)
    assert state(env)['trang_thai'] == expected
    if expected == 'het_cho':
        env.catalog.count = 317
        poll.quet(env.kho, env.catalog, root=env.root)
        assert state(env)['trang_thai'] == 'cho_chay'


@pytest.mark.parametrize('fault', ['hash', 'size', 'missing', 'name'])
def test_bad_files_do_not_escape_nhap(env, fault):
    files = None
    if fault == 'hash':
        files = [{'ten': 'orders.csv', 'so_byte': len(BASE), 'sha256': '0' * 64}]
    if fault == 'size':
        files = [{'ten': 'orders.csv', 'so_byte': len(BASE) + 1,
                  'sha256': hashlib.sha256(BASE).hexdigest()}]
    if fault == 'name':
        files = [{'ten': '../orders.csv', 'so_byte': len(BASE),
                  'sha256': hashlib.sha256(BASE).hexdigest()}]
    request(env, files=files)
    if fault == 'missing':
        (env.kho.root / poll.request_path(R1) / 'file/orders.csv').unlink()
    poll.quet(env.kho, env.catalog, root=env.root)
    assert state(env)['trang_thai'] == 'loi_file'
    assert not env.catalog.calls
    assert not list(env.root.rglob('orders.csv'))


def test_duplicate_in_ledger_or_other_pending(env):
    request(env, R1, status='da_kiem')
    request(env, R2, status='dang_kiem')
    poll.quet(env.kho, env.catalog, root=env.root)
    assert state(env, R2)['ma_loi'] == 'D2-7'
    assert not env.catalog.calls
    # Bỏ đợt khỏi sổ: yêu cầu mới có thể chạy lại.
    env2 = SimpleNamespace(root=env.root, kho=KhoDia(env.root / 'second'), catalog=FakeCatalog())
    request(env2, R2, status='dang_kiem')
    env2.kho.ghi_json_so_tiep('so_dot', {'loai': 'vao_so', 'ma_dot': 'd' * 12, 'files': []})
    env2.kho.ghi_json_so_tiep('so_dot', {'loai': 'bo', 'ma_dot': 'd' * 12})
    poll.quet(env2.kho, env2.catalog, root=env2.root)
    assert state(env2, R2)['trang_thai'] == 'cho_chay'


def test_two_new_requests_for_same_batch_in_one_poll(env):
    request(env, R2)
    request(env, R1)
    poll.quet(env.kho, env.catalog, root=env.root)
    assert state(env, R1)['trang_thai'] == 'cho_chay'
    assert state(env, R2)['trang_thai'] == 'sai_hop_dong'
    assert state(env, R2)['ma_loi'] == 'D2-7'


def test_download_replace_failure_keeps_temporary_outside_batch(env, monkeypatch):
    request(env)
    original = poll.os.replace
    temporary_paths = []

    def fail_once(source, target):
        temporary_paths.append((Path(source), Path(target)))
        raise OSError('replace-failed-sample')

    with monkeypatch.context() as patch:
        patch.setattr(poll.os, 'replace', fail_once)
        poll.quet(env.kho, env.catalog, root=env.root)
    folder = env.root / 'nhap' / R1 / 'file'
    assert len(temporary_paths) == 1
    assert temporary_paths[0][0].parent == folder.parent / '.tam'
    assert temporary_paths[0][1] == folder / 'orders.csv'
    assert list(folder.iterdir()) == []
    assert state(env)['trang_thai'] == 'da_gui'
    assert poll.os.replace is original

    def classify(batch_folder, data):
        assert batch_folder == folder
        assert [path.name for path in batch_folder.iterdir()] == ['orders.csv']
        return {'ma_dot': 'd' * 12, 'files': []}, {}

    monkeypatch.setattr(poll.dot, 'classify', classify)
    poll.quet(env.kho, env.catalog, root=env.root)
    assert state(env)['trang_thai'] == 'cho_chay'


def test_quota_ignores_information_schema(env, monkeypatch):
    request(env, status='dang_kiem')
    original_list = env.catalog.schema_list
    monkeypatch.setattr(env.catalog.schemas, 'list', lambda **kwargs: [
        *original_list(**kwargs), SimpleNamespace(name='information_schema')])
    poll.quet(env.kho, env.catalog, root=env.root)
    assert state(env)['trang_thai'] == 'cho_chay'
    assert ('tables', 'retail_lab', 'information_schema') not in env.catalog.calls


def test_idle_and_running_never_open_sql(env):
    assert poll.quet(env.kho, env.catalog, root=env.root) == {'dang_chay': []}
    request(env, status='dang_chay')
    opened = []
    assert poll.ket_thuc(env.kho, {'dot_' + R1 + '_1': 'running'}, root=env.root,
                          cloud_factory=lambda: opened.append(1)) == {'trigger': []}
    assert not opened
    assert poll.quet(env.kho, env.catalog, root=env.root)['dang_chay'][0]['request_id'] == R1


def test_trigger_reads_active_once_and_writes_event_first(env):
    request(env, R2, status='cho_chay')
    request(env, R1, status='cho_chay')
    snapshot = env.root / 'snapshots' / ('s' * 12)
    snapshot.mkdir(parents=True)
    (snapshot / 'manifest.json').write_text(json.dumps({'sources': {'a': {'mo_rong': True},
        'b': {'mo_rong': False}}}), encoding='utf-8')
    cloud = FakeCloud({'active': RID, 'releases': {RID: {'snapshot_id': 's' * 12}}})
    result = poll.ket_thuc(env.kho, {}, root=env.root, cloud_factory=lambda: cloud)
    assert len(result['trigger']) == 1 and cloud.closed and len(cloud.calls) == 1
    conf = result['trigger'][0]['conf']
    assert conf['request_id'] == R1 and conf['extensions'] == ['a'] and conf['du_bao_tu'] == RID
    assert state(env, R1)['trang_thai'] == 'dang_chay'
    assert state(env, R2)['trang_thai'] == 'cho_chay'
    again = poll.ket_thuc(env.kho, {}, root=env.root, cloud_factory=lambda: 1)
    assert again['trigger'] == result['trigger']


def test_follow_success_and_failure_are_sanitized(env):
    request(env, status='dang_chay')
    run_id = 'dot_' + R1 + '_1'
    folder = env.root / 'runs' / run_id
    folder.mkdir(parents=True)
    (folder / 'context.json').write_text(json.dumps({'stage': 'validated',
        'co_du_lieu_tong_hop': True, 'release_id': RID}), encoding='utf-8')
    poll.ket_thuc(env.kho, {run_id: 'success'}, root=env.root, cloud_factory=lambda: 1)
    assert state(env)['trang_thai'] == 'da_kiem' and state(env)['release_id'] == RID
    env2 = SimpleNamespace(root=env.root / 'second', kho=KhoDia(env.root / 'second_volume'))
    request(env2, status='dang_chay')
    folder = env2.root / 'runs' / run_id
    folder.mkdir(parents=True)
    (folder / 'failure.json').write_text(json.dumps({'stage': 'prepare', 'ma_loi': 'D2-1',
        'secret': 'must-not-leak'}), encoding='utf-8')
    poll.ket_thuc(env2.kho, {run_id: 'failed'}, root=env2.root, cloud_factory=lambda: 1)
    row = state(env2)
    assert row['trang_thai'] == 'loi' and row['ma_loi'] == 'D2-1'
    assert 'must-not-leak' not in row['thong_bao']


def test_dashboard_retries_after_ledger_write(env, monkeypatch):
    request(env, status='da_kiem')
    env.kho.ghi_json_so_tiep('lenh', {'loai': 'dat', 'request_id': R1, 'release_id': RID})
    calls = []
    original = poll._event
    failed = []

    def interrupt(kho, row, target, **extra):
        if target == 'tren_dashboard' and not failed:
            failed.append(True)
            raise RuntimeError('power loss')
        return original(kho, row, target, **extra)

    monkeypatch.setattr(poll, '_event', interrupt)
    poll.quet(env.kho, env.catalog, root=env.root, call=lambda args: calls.append(args) or 0)
    assert len(env.kho.liet_ke('so_dot')) == 1
    assert not env.kho.liet_ke('lenh/000001.ket_qua.json')
    monkeypatch.setattr(poll, '_event', original)
    poll.quet(env.kho, env.catalog, root=env.root, call=lambda args: calls.append(args) or 0)
    assert state(env)['trang_thai'] == 'tren_dashboard'
    assert len(env.kho.liet_ke('so_dot')) == 1
    assert json.loads(env.kho.doc('lenh/000001.ket_qua.json'))['ket_qua'] == 'dat'
    assert all('--target' in call and 'databricks' in call for call in calls)


@pytest.mark.parametrize('code,expected', [(75, None), (2, 'Bản không đạt điều kiện đưa lên dashboard.'),
                                           (1, 'Chưa đổi được dashboard; thử lại sau ít phút.')])
def test_dashboard_exit_codes(env, code, expected):
    request(env, status='da_kiem')
    env.kho.ghi_json_so_tiep('lenh', {'loai': 'dat', 'request_id': R1, 'release_id': RID})
    poll.quet(env.kho, env.catalog, root=env.root, call=lambda args: code)
    try:
        result = json.loads(env.kho.doc('lenh/000001.ket_qua.json'))
    except FileNotFoundError:
        result = None
    assert (result or {}).get('thong_bao') == expected
    assert not env.kho.liet_ke('so_dot')


def test_duplicate_recorded_batch_and_broken_request_isolation(env):
    request(env, R1, status='dang_kiem')
    request(env, R2, status='dang_kiem')
    # Yêu cầu hỏng bị bỏ qua, yêu cầu tốt vẫn được phân loại.
    (env.kho.root / poll.request_path(R1) / 'yeu_cau.json').write_text('{broken', encoding='utf-8')
    env.kho.ghi_json_so_tiep('so_dot', {'loai': 'vao_so', 'ma_dot': 'd' * 12, 'files': []})
    poll.quet(env.kho, env.catalog, root=env.root)
    assert state(env, R2)['ma_loi'] == 'D2-7'
    assert not env.catalog.calls


def test_broken_ledger_blocks_batches_but_allows_clear(env):
    request(env, status='dang_kiem')
    env.kho.ghi_moi('so_dot/000001.json', b'{broken')
    env.kho.ghi_json_so_tiep('lenh', {'loai': 'tra'})
    calls = []
    poll.quet(env.kho, env.catalog, root=env.root, call=lambda args: calls.append(args) or 0)
    assert state(env)['trang_thai'] == 'dang_kiem'
    assert len(calls) == 1 and calls[0][0] == 'tra-dashboard'
    assert json.loads(env.kho.doc('lenh/000001.ket_qua.json'))['ket_qua'] == 'dat'
    assert not env.catalog.calls


@pytest.mark.parametrize('status', ['da_gui', 'het_cho'])
def test_broken_ledger_does_not_advance_request(env, status):
    request(env, status=status)
    env.kho.ghi_moi('so_dot/000001.json', b'{broken')
    poll.quet(env.kho, env.catalog, root=env.root)
    assert state(env)['trang_thai'] == status
    assert not env.catalog.calls


def test_broken_ledger_does_not_execute_dashboard_command(env):
    request(env, status='da_kiem')
    env.kho.ghi_moi('so_dot/000001.json', b'{broken')
    env.kho.ghi_json_so_tiep('lenh', {'loai': 'dat', 'request_id': R1, 'release_id': RID})
    calls = []
    poll.quet(env.kho, env.catalog, root=env.root, call=lambda args: calls.append(args) or 0)
    assert not calls
    assert not env.kho.liet_ke('lenh/000001.ket_qua.json')
    assert state(env)['trang_thai'] == 'da_kiem'


@pytest.mark.parametrize('body', [b'{broken', b'{"loai":"unknown"}', b'{}'])
def test_bad_command_never_calls_cli(env, body):
    env.kho.ghi_moi('lenh/000001.json', body)
    calls = []
    poll.quet(env.kho, env.catalog, root=env.root, call=lambda args: calls.append(args) or 0)
    assert not calls
    assert json.loads(env.kho.doc('lenh/000001.ket_qua.json'))['ket_qua'] == 'loi'


def test_mismatched_release_never_calls_cli(env):
    request(env, status='da_kiem')
    env.kho.ghi_json_so_tiep('lenh', {'loai': 'dat', 'request_id': R1,
                                      'release_id': 'b' * 24})
    calls = []
    poll.quet(env.kho, env.catalog, root=env.root, call=lambda args: calls.append(args) or 0)
    assert not calls and not env.kho.liet_ke('so_dot')
    assert json.loads(env.kho.doc('lenh/000001.ket_qua.json'))['ket_qua'] == 'loi'


def test_clear_keeps_ledger_and_returns_dashboard_request(env):
    request(env, status='tren_dashboard')
    env.kho.ghi_json_so_tiep('so_dot', {'loai': 'vao_so', 'ma_dot': 'd' * 12,
                                      'request_id': R1, 'files': []})
    before = env.kho.liet_ke('so_dot')
    env.kho.ghi_json_so_tiep('lenh', {'loai': 'tra'})
    poll.quet(env.kho, env.catalog, root=env.root, call=lambda args: 0)
    assert state(env)['trang_thai'] == 'da_tra'
    assert env.kho.liet_ke('so_dot') == before


def test_success_without_validated_context_is_error(env):
    request(env, status='dang_chay')
    run_id = 'dot_' + R1 + '_1'
    poll.ket_thuc(env.kho, {run_id: 'success'}, root=env.root, cloud_factory=lambda: 1)
    assert state(env)['trang_thai'] == 'loi'
    assert 'exception' not in state(env)['thong_bao'].lower()


@pytest.mark.parametrize('context', [
    {'stage': 'prepared', 'co_du_lieu_tong_hop': True, 'release_id': RID},
    {'stage': 'validated', 'co_du_lieu_tong_hop': False, 'release_id': RID},
])
def test_success_requires_validated_stage_and_synthetic_flag(env, context):
    request(env, status='dang_chay')
    run_id = 'dot_' + R1 + '_1'
    folder = env.root / 'runs' / run_id
    folder.mkdir(parents=True)
    (folder / 'context.json').write_text(json.dumps(context), encoding='utf-8')
    poll.ket_thuc(env.kho, {run_id: 'success'}, root=env.root,
                  cloud_factory=lambda: pytest.fail('Không mở cloud'))
    assert state(env)['trang_thai'] == 'loi'


def test_log_prints_error_type_without_error_content(capsys):
    poll._log('sample', ValueError('private-error-sample'))
    captured = capsys.readouterr()
    assert 'ValueError' in captured.err
    assert 'private-error-sample' not in captured.err


def test_race_before_running_event_does_not_trigger(env, monkeypatch):
    request(env, status='cho_chay')
    folder = env.root / 'snapshots' / ('s' * 12)
    folder.mkdir(parents=True)
    (folder / 'manifest.json').write_text(json.dumps({'sources': {}}), encoding='utf-8')
    cloud = FakeCloud({'active': RID, 'releases': {RID: {'snapshot_id': 's' * 12}}})
    original = poll._event

    def race(kho, row, target, **extra):
        if target == 'dang_chay':
            raise poll.TrangThaiDaDoi()
        return original(kho, row, target, **extra)

    monkeypatch.setattr(poll, '_event', race)
    assert poll.ket_thuc(env.kho, {}, root=env.root, cloud_factory=lambda: cloud) == {'trigger': []}
    assert state(env)['trang_thai'] == 'cho_chay'


def test_missing_failure_code_is_not_fabricated(env):
    request(env, status='dang_chay')
    run_id = 'dot_' + R1 + '_1'
    poll.ket_thuc(env.kho, {run_id: 'failed'}, root=env.root, cloud_factory=lambda: 1)
    assert state(env)['trang_thai'] == 'loi'
    assert 'ma_loi' not in state(env)


def test_retry_after_failed_run_increments_lan(env):
    request(env, status='cho_chay')
    folder = env.root / 'snapshots' / ('s' * 12)
    folder.mkdir(parents=True)
    (folder / 'manifest.json').write_text(json.dumps({'sources': {}}), encoding='utf-8')
    cloud = FakeCloud({'active': RID, 'releases': {RID: {'snapshot_id': 's' * 12}}})
    row = state(env)
    poll._event(env.kho, row, 'dang_chay', lan=1, airflow_run_id='dot_' + R1 + '_1',
                pipeline_run_id='dot_' + R1 + '_1', conf={})
    row = state(env)
    poll._event(env.kho, row, 'loi')
    row = state(env)
    poll._event(env.kho, row, 'cho_chay')
    result = poll.ket_thuc(env.kho, {}, root=env.root, cloud_factory=lambda: cloud)
    assert result['trigger'][0]['airflow_run_id'] == 'dot_' + R1 + '_2'
    assert state(env)['lich_su'][-1]['lan'] == 2


def test_missing_manifest_keeps_waiting(env):
    request(env, status='cho_chay')
    cloud = FakeCloud({'active': RID, 'releases': {RID: {'snapshot_id': 'missing'}}})
    assert poll.ket_thuc(env.kho, {}, root=env.root, cloud_factory=lambda: cloud) == {'trigger': []}
    assert state(env)['trang_thai'] == 'cho_chay' and cloud.closed


def test_ledger_order_and_hash_check_before_trigger(env):
    request(env, R1, status='da_kiem', ma='c' * 12)
    request(env, R2, status='cho_chay')
    env.kho.ghi_json_so_tiep('so_dot', {'loai': 'vao_so', 'ma_dot': 'c' * 12,
        'request_id': R1, 'files': [{'ten': 'orders.csv', 'so_byte': len(BASE),
        'sha256': hashlib.sha256(BASE).hexdigest()}]})
    folder = env.root / 'snapshots' / ('s' * 12)
    folder.mkdir(parents=True)
    (folder / 'manifest.json').write_text(json.dumps({'sources': {'ext_a': {'mo_rong': True}}}), encoding='utf-8')
    cloud = FakeCloud({'active': RID, 'releases': {RID: {'snapshot_id': 's' * 12}}})
    result = poll.ket_thuc(env.kho, {}, root=env.root, cloud_factory=lambda: cloud)
    dots = result['trigger'][0]['conf']['dots']
    assert R1 in dots[0] and R2 in dots[1]
    assert result['trigger'][0]['conf']['extensions'] == ['ext_a']
    (env.kho.root / poll.request_path(R1) / 'file/orders.csv').write_bytes(b'corrupt')
    (env.root / 'nhap' / R1 / 'file/orders.csv').unlink()
    row = state(env, R2)
    poll._event(env.kho, row, 'loi')
    row = state(env, R2)
    poll._event(env.kho, row, 'cho_chay')
    assert poll.ket_thuc(env.kho, {}, root=env.root, cloud_factory=lambda: cloud) == {'trigger': []}
    assert state(env, R2)['trang_thai'] == 'cho_chay'


def test_missing_transaction_table_is_contract_error_without_cloud(env, monkeypatch):
    request(env, status='dang_kiem')
    def missing(*args):
        raise poll.dot.DotError('D2-missing', 'orders.csv', 'transactions', 1)
    monkeypatch.setattr(poll.dot, 'classify', missing)
    poll.quet(env.kho, env.catalog, root=env.root)
    assert state(env)['trang_thai'] == 'sai_hop_dong'
    assert state(env)['ma_loi'] == 'D2-missing'
    assert not env.catalog.calls


@pytest.mark.parametrize('interruption', ['after_cli', 'after_ledger', 'after_other', 'after_current', 'after_result'])
def test_dashboard_resume_after_each_step(env, monkeypatch, interruption):
    request(env, R1, status='tren_dashboard', ma='c' * 12)
    request(env, R2, status='da_kiem')
    env.kho.ghi_json_so_tiep('lenh', {'loai': 'dat', 'request_id': R2, 'release_id': RID})
    cli_calls = []
    def call(args):
        cli_calls.append(args)
        return 0

    with monkeypatch.context() as patch:
        if interruption == 'after_cli':
            original = poll._run_cli
            def interrupt_cli(*args, **kwargs):
                original_call = original(*args, **kwargs)
                raise KeyboardInterrupt('power loss')
            patch.setattr(poll, '_run_cli', interrupt_cli)
        elif interruption == 'after_ledger':
            original = env.kho.ghi_json_so_tiep
            def interrupt_ledger(path, *args, **kwargs):
                result = original(path, *args, **kwargs)
                if path == 'so_dot':
                    raise KeyboardInterrupt('power loss')
                return result
            patch.setattr(env.kho, 'ghi_json_so_tiep', interrupt_ledger)
        elif interruption in ('after_other', 'after_current'):
            original = poll._event
            target = 'da_tra' if interruption == 'after_other' else 'tren_dashboard'
            def interrupt_event(kho, row, state_name, **kwargs):
                result = original(kho, row, state_name, **kwargs)
                if state_name == target:
                    raise KeyboardInterrupt('power loss')
                return result
            patch.setattr(poll, '_event', interrupt_event)
        else:
            original = poll._command_result
            def interrupt_result(*args, **kwargs):
                original(*args, **kwargs)
                raise KeyboardInterrupt('power loss')
            patch.setattr(poll, '_command_result', interrupt_result)
        with pytest.raises(KeyboardInterrupt):
            poll.quet(env.kho, env.catalog, root=env.root, call=call)

    poll.quet(env.kho, env.catalog, root=env.root, call=call)
    assert state(env, R1)['trang_thai'] == 'da_tra'
    assert state(env, R2)['trang_thai'] == 'tren_dashboard'
    assert len(env.kho.liet_ke('so_dot')) == 1
    assert json.loads(env.kho.doc('lenh/000001.ket_qua.json'))['ket_qua'] == 'dat'
    assert sum(e['toi'] == 'da_tra' for e in state(env, R1)['lich_su']) == 1
    assert sum(e['toi'] == 'tren_dashboard' for e in state(env, R2)['lich_su']) == 1
    assert len(cli_calls) == (1 if interruption == 'after_result' else 2)


def test_dashboard_processes_latest_command_without_result(env):
    request(env, status='tren_dashboard')
    env.kho.ghi_json_so_tiep('lenh', {'loai': 'tra'})
    env.kho.ghi_json_so_tiep('lenh', {'loai': 'tra'})
    env.kho.ghi_moi('lenh/000002.ket_qua.json', b'{"ket_qua":"dat"}')
    calls = []
    poll.quet(env.kho, env.catalog, root=env.root, call=lambda args: calls.append(args) or 0)
    assert len(calls) == 1
    assert json.loads(env.kho.doc('lenh/000001.ket_qua.json'))['ket_qua'] == 'dat'
    assert state(env)['trang_thai'] == 'da_tra'


def test_malformed_running_event_does_not_stop_other_requests(env, capsys):
    request(env, R1, status='dang_chay', ma='c' * 12)
    request(env, R2, status='dang_kiem')
    event_path = env.kho.root / poll.request_path(R1) / 'su_kien/000004.json'
    broken = json.loads(event_path.read_text(encoding='utf-8'))
    broken.pop('conf')
    event_path.write_text(json.dumps(broken), encoding='utf-8')
    assert state(env, R1)['trang_thai'] == 'dang_chay'
    result = poll.quet(env.kho, env.catalog, root=env.root)
    assert result == {'dang_chay': []}
    assert state(env, R2)['trang_thai'] == 'cho_chay'
    assert poll.ket_thuc(env.kho, {}, root=env.root, cloud_factory=lambda: pytest.fail('Không mở cloud')) == {'trigger': []}
    captured = capsys.readouterr()
    assert R1 in captured.err and 'KeyError' not in captured.err


def test_full_volume_flow_and_reactivate_dashboard(env):
    request(env)
    assert state(env)['trang_thai'] == 'da_gui'
    poll.quet(env.kho, env.catalog, root=env.root)
    assert [e['toi'] for e in state(env)['lich_su']] == ['da_gui', 'dang_kiem', 'cho_chay']
    snapshot = env.root / 'snapshots' / ('s' * 12)
    snapshot.mkdir(parents=True)
    (snapshot / 'manifest.json').write_text(json.dumps({'sources': {}}), encoding='utf-8')
    cloud = FakeCloud({'active': RID, 'releases': {RID: {'snapshot_id': 's' * 12}}})
    triggered = poll.ket_thuc(env.kho, {}, root=env.root, cloud_factory=lambda: cloud)['trigger']
    assert len(triggered) == 1 and cloud.closed
    assert state(env)['trang_thai'] == 'dang_chay'
    run_id = triggered[0]['airflow_run_id']
    context = env.root / 'runs' / run_id / 'context.json'
    context.parent.mkdir(parents=True)
    context.write_text(json.dumps({'stage': 'validated', 'release_id': RID,
                                   'co_du_lieu_tong_hop': True}), encoding='utf-8')
    assert poll.ket_thuc(env.kho, {run_id: 'success'}, root=env.root,
                        cloud_factory=lambda: pytest.fail('Không mở lại cloud')) == {'trigger': []}
    assert state(env)['trang_thai'] == 'da_kiem'
    for kind, expected in [('dat', 'tren_dashboard'), ('tra', 'da_tra'),
                           ('dat', 'tren_dashboard')]:
        body = {'loai': kind}
        if kind == 'dat':
            body.update(request_id=R1, release_id=RID)
        env.kho.ghi_json_so_tiep('lenh', body)
        poll.quet(env.kho, env.catalog, root=env.root, call=lambda args: 0)
        assert state(env)['trang_thai'] == expected
    assert len(env.kho.liet_ke('so_dot')) == 1
    assert [e['toi'] for e in state(env)['lich_su']][-3:] == [
        'tren_dashboard', 'da_tra', 'tren_dashboard']
