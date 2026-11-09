"""L1: kho giả, tranh ghi thật trên đĩa tạm và AppTest; không gọi cloud."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from types import SimpleNamespace

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from ui import roles, nhap_dot as nd, kho_dot as kd, nhap_runner as nr, ai_panel, common
from dwh import releases, connection
from ai_explain import page_explain as pe

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / 'apps/retail_app'
RID = 'b' * 24
REQUEST = '20261108T120000Z_abcdef_dot'


class Upload(io.BytesIO):
    def __init__(self, name='orders.csv', content=b'id,date\n1,2023-01-01\n'):
        super().__init__(content)
        self.name = name
        self.size = 0  # Cố ý nói sai: code phải đếm bytes thật.


class FakeFiles:
    def __init__(self):
        self.data, self.calls = {}, []
        self.fail = None

    def upload(self, path, contents, *, overwrite):
        from databricks.sdk.errors import AlreadyExists
        self.calls.append(('upload', path, overwrite))
        assert overwrite is False
        value = contents.read()
        if self.fail:
            if self.fail == 'same':
                self.data[path] = value
            elif self.fail == 'other':
                self.data[path] = b'{"ma":"nguoi_khac"}'
            raise TypeError("object of type '_io.BytesIO' has no len()")
        if path in self.data:
            raise AlreadyExists('đã có')
        self.data[path] = value

    def download(self, path):
        from databricks.sdk.errors import NotFound
        self.calls.append(('download', path))
        if path not in self.data:
            raise NotFound('không có')
        return SimpleNamespace(contents=io.BytesIO(self.data[path]))

    def list_directory_contents(self, path):
        self.calls.append(('list', path))
        prefix = path + '/'
        return [SimpleNamespace(path=prefix + name) for name in sorted({
            key[len(prefix):].split('/')[0] for key in self.data if key.startswith(prefix)})]


@pytest.fixture
def store(tmp_path, monkeypatch):
    events = []
    monkeypatch.setattr(connection, 'databricks_config', lambda: {'DATABRICKS_HOST': 'https://fake.invalid'})
    from ui import nhap_store
    monkeypatch.setattr(nhap_store, 'nhap_kha_dung', lambda: False)
    monkeypatch.setattr(roles, 'current_role', lambda: 'admin')
    monkeypatch.setattr(roles, 'logged_in_user', lambda: {'username': 'admin1'})
    monkeypatch.setattr(roles, 'store', lambda: SimpleNamespace(log=lambda *args: events.append(args)))
    monkeypatch.setenv('RETAIL_NHAP_DOT', 'tat')
    monkeypatch.setenv('RETAIL_BACKEND', 'duckdb')
    monkeypatch.setenv('RETAIL_BACKENDS', 'duckdb')
    monkeypatch.setenv('RETAIL_RELEASE_MODE', 'legacy')
    monkeypatch.setattr(nr, 'dashboard_state_cloud', lambda: {'releases': {
        RID: {'status': 'ready', 'co_du_lieu_tong_hop': True},
        'c' * 24: {'status': 'building', 'co_du_lieu_tong_hop': True},
        'd' * 24: {'status': 'ready'}}})
    result = nd.DotStore(kd.KhoDia(tmp_path))
    result.audit_events = events
    releases.reset()
    yield result
    releases.reset()


def advance(store, row, states):
    for state in states:
        store.kho.ghi_json_so_tiep(nd.request_path(row['id']) + '/su_kien',
                                 {'toi': state, 'ai': 'airflow', 'release_id': RID})
    return store.read(row['id'])


@pytest.mark.parametrize('factory', ['dia', 'volume'])
def test_storage_and_numbering(tmp_path, factory):
    files = FakeFiles()
    kho = kd.KhoDia(tmp_path) if factory == 'dia' else kd.KhoVolume('/Volumes/test/kho', SimpleNamespace(files=files))
    assert kho.liet_ke('missing') == []
    with pytest.raises(kd.KhongCo):
        kho.doc('missing/file.json')
    kho.ghi_moi('test/first.csv', b'abc')
    with pytest.raises(kd.DaCo):
        kho.ghi_moi('test/first.csv', b'other')
    assert kho.doc('test/first.csv') == b'abc'
    kho.ghi_moi('lenh/999999.ket_qua.json', b'{}')
    body = {'loai': 'tra', 'ma': 'khong_dung', 'luc': 'cu'}
    assert kho.ghi_json_so_tiep('lenh', body) == 1
    row = json.loads(kho.doc('lenh/000001.json'))
    assert len(row['ma']) == 32 and row['ma'] != 'khong_dung' and '+00:00' in row['luc']
    assert body['ma'] == 'khong_dung'
    assert kho.ghi_json_so_tiep('lenh', {'loai': 'tra'}) == 2
    assert kho.liet_ke('lenh') == ['000001.json', '000002.json', '999999.ket_qua.json']


@pytest.mark.parametrize('path', ['/escape', '../escape', 'a/../b', 'a..b', 'a\\b', 'a:b', 'a//b', './a', ''])
def test_paths_cannot_escape(tmp_path, path):
    for kho in (kd.KhoDia(tmp_path), kd.KhoVolume('/Volumes/test/kho', SimpleNamespace(files=FakeFiles()))):
        with pytest.raises(ValueError):
            kho.ghi_moi(path, b'x')
    assert list(tmp_path.iterdir()) == []


def test_uppercase_request_path_approved(store):
    store.kho.ghi_moi(nd.request_path(REQUEST) + '/file/orders.csv', b'x')
    assert store.kho.doc(nd.request_path(REQUEST) + '/file/orders.csv') == b'x'
    for invalid in ('../bad', REQUEST.lower(), REQUEST + '/x'):
        with pytest.raises(ValueError):
            store.read(invalid)
    store.kho.ghi_moi('yeu_cau/invalid/yeu_cau.json', b'{}')
    assert store.visible('admin1', 'admin') == []


@pytest.mark.parametrize('attempt', range(10))
def test_two_real_writers_same_number(tmp_path, attempt):
    barrier = threading.Barrier(2)

    class Racing(kd.KhoDia):
        def ghi_moi(self, path, data):
            barrier.wait(timeout=10)
            return super().ghi_moi(path, data)

    def write(who):
        try:
            return who, Racing(tmp_path).ghi_json_so_tiep('lenh', {'ai': who})
        except kd.TrangThaiDaDoi:
            return who, 'lost'

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ['one', 'two']))
    assert sorted(str(result) for _, result in results) == ['1', 'lost']
    winner = next(who for who, result in results if result == 1)
    assert json.loads((tmp_path / 'lenh/000001.json').read_bytes())['ai'] == winner
    assert sorted(p.name for p in (tmp_path / 'lenh').iterdir()) == ['000001.json']


@pytest.mark.parametrize('failure', ['same', 'other', 'absent'])
def test_volume_typeerror_reads_ma(failure):
    files = FakeFiles()
    files.fail = failure
    kho = kd.KhoVolume('/Volumes/test/kho', SimpleNamespace(files=files))
    if failure == 'same':
        assert kho.ghi_json_so_tiep('lenh', {'loai': 'tra'}) == 1
    else:
        with pytest.raises(kd.TrangThaiDaDoi if failure == 'other' else TypeError):
            kho.ghi_json_so_tiep('lenh', {'loai': 'tra'})
    assert len([call for call in files.calls if call[0] == 'upload']) == 1
    assert any(call[0] == 'download' for call in files.calls)
    assert not any('000002' in call[1] for call in files.calls)


def test_change_between_read_and_append_is_rejected(store, monkeypatch):
    original = store.kho.ghi_json_so_tiep

    def racing(folder, body, **kwargs):
        original('lenh', {'loai': 'tra', 'ai': 'other'})
        return original(folder, body, **kwargs)

    monkeypatch.setattr(store.kho, 'ghi_json_so_tiep', racing)
    with pytest.raises(kd.TrangThaiDaDoi):
        store.dashboard_command()
    assert store.kho.liet_ke('lenh') == ['000001.json']


@pytest.mark.parametrize('states', [
    ['da_gui', 'dang_kiem', 'cho_chay', 'dang_chay', 'da_kiem', 'tren_dashboard', 'da_tra'],
    ['da_gui', 'loi_file'], ['da_gui', 'dang_kiem', 'sai_hop_dong'],
    ['da_gui', 'dang_kiem', 'het_cho', 'cho_chay', 'dang_chay', 'loi', 'huy'],
    ['da_gui', 'dang_kiem', 'cho_chay', 'dang_chay', 'loi', 'cho_chay', 'dang_chay', 'da_kiem'],
])
def test_valid_replay(states):
    events = [(i, {'toi': state, 'release_id': RID, 'ma_loi': 'D2-1', 'thong_bao': 'Lỗi kiểm'})
              for i, state in enumerate(states, 1)]
    result = nd.phat_lai(events)
    assert result['trang_thai'] == states[-1]
    assert result['release_id'] == RID and result['ma_loi'] == 'D2-1'
    assert len(result['lich_su']) == len(states)


@pytest.mark.parametrize('events', [[], [(2, {'toi': 'da_gui'})], [(1, {'toi': 'da_gui'}), (3, {'toi': 'dang_kiem'})],
    [(1, {'toi': 'da_gui'}), (2, {'toi': 'da_kiem'})], [(1, {'toi': 'la'})], [(1, {})], [(1, None)]])
def test_corrupt_replay_does_not_raise(events):
    assert nd.phat_lai(events)['trang_thai'] == 'hong'


@pytest.mark.parametrize('names,label', [
    ([], 'dot'), (['orders.csv'] * 41, 'dot'), (['orders.csv'], ''), (['orders.csv'], 'A'),
    (['orders.csv'], 'a' * 41), (['orders.csv'], 'a b'), (['orders.csv', 'ORDERS.csv'], 'dot'),
    (['orders.csv', 'sales.csv'], 'dot'), (['orders.csv', 'sample_submission.csv'], 'dot'),
    (['items.csv'], 'dot'), (['orders.exe'], 'dot'), (['orders.csv', 'con.csv'], 'dot'),
    (['orders.csv', 'items..csv'], 'dot'),
])
def test_bad_upload_writes_nothing(store, names, label):
    with pytest.raises(ValueError):
        store.gui_dot([Upload(name) for name in names], label, '')
    assert list(store.kho.root.iterdir()) == []


@pytest.mark.parametrize('limit', ['file', 'total'])
def test_actual_bytes_limits_before_write(store, monkeypatch, limit):
    assert nd.MAX_FILE_BYTES == 200 * 1024**2 and nd.MAX_TOTAL_BYTES == 100 * 1024**2
    monkeypatch.setattr(nd, 'MAX_FILE_BYTES', 8 if limit == 'file' else 20)
    monkeypatch.setattr(nd, 'MAX_TOTAL_BYTES', 30 if limit == 'file' else 10)
    uploads = [Upload('orders.csv', b'x' * 9)] if limit == 'file' else [Upload('orders.csv', b'123456'), Upload('items.csv', b'123456')]
    with pytest.raises(ValueError, match='200 MB' if limit == 'file' else '100 MB'):
        store.gui_dot(uploads, 'dot', '')
    assert list(store.kho.root.iterdir()) == []


def test_valid_upload_order_hash_chunks_and_audit(store, monkeypatch):
    paths, reads = [], []
    original = store.kho.ghi_moi
    monkeypatch.setattr(store.kho, 'ghi_moi', lambda path, data: (paths.append(path), original(path, data))[-1])

    class Chunked(Upload):
        def read(self, size=-1):
            reads.append(size)
            return super().read(size)

    content = b'x' * (1024**2 + 9)
    row = store.gui_dot([Chunked('Orders.csv', content), Upload('products.json', b'[]')], 'dot_2023', 'Mẫu')
    prefix = nd.request_path(row['id'])
    assert paths == [prefix + '/file/orders.csv', prefix + '/file/products.json',
                     prefix + '/yeu_cau.json', prefix + '/su_kien/000001.json']
    assert set(reads) == {1024**2} and len(reads) == 3
    assert row['files'][0] == {'ten': 'orders.csv', 'so_byte': len(content), 'sha256': hashlib.sha256(content).hexdigest()}
    assert row['trang_thai'] == 'da_gui' and nd.ID_PATTERN.fullmatch(row['id'])
    assert store.audit_events[-1][1] == 'dot_gui'


def test_second_file_failure_leaves_invisible_orphan(store, monkeypatch):
    original = store.kho.ghi_moi
    def fail(path, data):
        if path.endswith('/items.csv'):
            raise OSError('lỗi ghi thử')
        original(path, data)
    monkeypatch.setattr(store.kho, 'ghi_moi', fail)
    with pytest.raises(OSError):
        store.gui_dot([Upload(), Upload('items.csv')], 'dot', '')
    assert store.visible('admin1', 'admin') == []
    assert not list(store.kho.root.rglob('su_kien'))
    assert not list(store.kho.root.rglob('yeu_cau.json'))


@pytest.mark.parametrize('role', ['khach', 'quan_ly', 'phan_tich', 'ky_su'])
def test_non_admin_cannot_write_command(store, monkeypatch, role):
    monkeypatch.setattr(roles, 'current_role', lambda: role)
    monkeypatch.setattr(roles, 'logged_in_user', lambda: {'username': 'admin1', 'role': 'admin'})
    for rid in (None, RID):
        with pytest.raises(PermissionError):
            store.dashboard_command(rid, confirmed=True)
    assert store.kho.liet_ke('lenh') == []


@pytest.mark.parametrize('target,event', [('cho_chay', 'dot_chay_lai'), ('huy', 'dot_huy')])
def test_engineer_retry_cancel(store, monkeypatch, target, event):
    row = advance(store, store.gui_dot([Upload()], 'dot', ''), ['dang_kiem', 'cho_chay', 'dang_chay', 'loi'])
    monkeypatch.setattr(roles, 'current_role', lambda: 'ky_su')
    store.change(row['id'], target)
    assert store.read(row['id'])['trang_thai'] == target
    assert store.audit_events[-1][1] == event
    with pytest.raises(PermissionError):
        store.dashboard_command()


def test_visibility_and_send_permission(store, monkeypatch):
    first = store.gui_dot([Upload()], 'one', '')
    monkeypatch.setattr(roles, 'logged_in_user', lambda: {'username': 'manager'})
    second = store.gui_dot([Upload()], 'two', '')
    assert [r['id'] for r in store.visible('manager', 'quan_ly')] == [second['id']]
    assert {r['id'] for r in store.visible('manager', 'ky_su')} == {first['id'], second['id']}
    monkeypatch.setattr(roles, 'current_role', lambda: 'khach')
    with pytest.raises(PermissionError):
        store.gui_dot([Upload()], 'three', '')


def test_pending_command_error_result_and_label(store):
    row = advance(store, store.gui_dot([Upload()], 'dot', ''), ['dang_kiem', 'cho_chay', 'dang_chay', 'da_kiem'])
    with pytest.raises(ValueError, match='xác nhận'):
        store.dashboard_command(RID)
    assert store.dashboard_command(RID, confirmed=True) == 1
    latest = store.latest_command()
    assert latest['request_id'] == row['id'] and latest['release_id'] == RID and latest['loai'] == 'dat'
    assert store.label(row, latest) == 'Chờ đưa lên dashboard'
    with pytest.raises(ValueError, match='Đang chờ Airflow'):
        store.dashboard_command()
    store.kho.ghi_moi('lenh/000001.ket_qua.json', json.dumps({'ket_qua': 'loi', 'thong_bao': 'Lỗi thử'}).encode())
    assert store.label(row, store.latest_command()) == 'Đã kiểm tra'
    assert store.dashboard_command() == 2
    assert store.audit_events[-1][1] == 'dashboard_lenh_tra'


def test_ledger_remove_does_not_touch_dashboard(store, monkeypatch):
    store.kho.ghi_json_so_tiep('so_dot', {'loai': 'vao_so', 'ma_dot': 'a'*12, 'release_id': RID, 'request_id': REQUEST})
    monkeypatch.setattr(roles, 'current_role', lambda: 'ky_su')
    with pytest.raises(ValueError):
        store.remove_from_ledger('a'*12, ' ')
    assert len(store.ledger()) == 1
    store.remove_from_ledger('a'*12, 'Không dùng cho lần dựng sau')
    assert store.ledger() == [] and store.kho.liet_ke('lenh') == []
    assert store.audit_events[-1][1] == 'so_dot_bo'


def test_registry_uses_reader_connection(monkeypatch):
    calls = []
    monkeypatch.setattr(connection, '_fetch_databricks', lambda sql, **kw: (calls.append((sql, kw)) or (['payload'], [(json.dumps({'active': 'a'}),)])))
    assert nr.dashboard_state_cloud() == {'active': 'a'}
    assert calls == [("select payload from retail_control.state where name = 'main'", {'resolve_release': False})]


def cloud_page(store, monkeypatch, page='duyet_du_lieu'):
    monkeypatch.setenv('RETAIL_NHAP_DOT', 'volume')
    monkeypatch.setenv('RETAIL_BACKEND', 'databricks')
    monkeypatch.setenv('RETAIL_BACKENDS', 'databricks')
    monkeypatch.setattr(kd, 'configured_store', lambda: store.kho)
    monkeypatch.setattr(nr, 'recover_queue', lambda *a, **kw: pytest.fail('Không chạy hàng đợi local'))
    monkeypatch.setattr(nr, 'dashboard_action', lambda *a, **kw: pytest.fail('Không gọi CLI local'))
    return AppTest.from_file(str(APP / 'views' / (page + '.py')), default_timeout=20).run()


def test_cloud_ui_command_pending_and_error_unlock(store, monkeypatch):
    at = cloud_page(store, monkeypatch)
    assert not at.exception and not at.error
    assert at.selectbox[0].options == [RID]
    at.checkbox[0].check()
    next(b for b in at.button if b.label.startswith('Đưa bản')).click().run()
    assert not at.exception and not at.error
    assert store.kho.liet_ke('lenh') == ['000001.json']
    assert any('Đang chờ Airflow' in item.value for item in at.info)
    assert next(b for b in at.button if b.label.startswith('Đưa bản')).disabled
    store.kho.ghi_moi('lenh/000001.ket_qua.json', json.dumps({'ket_qua': 'loi', 'thong_bao': 'Lỗi từ bộ xử lý'}).encode())
    at.run()
    assert not at.exception and any('Lỗi từ bộ xử lý' in item.value for item in at.error)
    assert not next(b for b in at.button if b.label.startswith('Đưa bản')).disabled


def test_cloud_ui_return_and_roles(store, monkeypatch):
    monkeypatch.setattr(nr, 'dashboard_state_cloud', lambda: {'dashboard': RID, 'dashboard_since': {'release_id': RID, 'at': '2026-11-08T12:00:00Z'}, 'releases': {}})
    at = cloud_page(store, monkeypatch)
    assert any(RID in c.value for c in at.caption)
    assert 'Giờ công bố: 2026-11-08T12:00:00Z' in [c.value for c in at.caption]
    next(b for b in at.button if b.label == 'Trả dashboard về bản số thật').click().run()
    assert store.latest_command()['loai'] == 'tra'
    assert next(b for b in at.button if b.label == 'Trả dashboard về bản số thật').disabled
    monkeypatch.setattr(roles, 'current_role', lambda: 'ky_su')
    at.run()
    assert not any('dashboard' in b.label for b in at.button)


@pytest.mark.parametrize('page', ['gui_du_lieu', 'duyet_du_lieu'])
def test_volume_missing_config_has_no_form(store, monkeypatch, page):
    monkeypatch.setenv('RETAIL_NHAP_DOT', 'volume')
    monkeypatch.setenv('RETAIL_BACKEND', 'databricks')
    monkeypatch.setenv('RETAIL_BACKENDS', 'databricks')
    for key in ('RETAIL_NHAP_DBX_CLIENT_ID', 'RETAIL_NHAP_DBX_CLIENT_SECRET'):
        monkeypatch.delenv(key, raising=False)
    at = AppTest.from_file(str(APP / 'views' / (page + '.py'))).run()
    assert not at.exception and not at.button
    assert any('Chưa cấu hình kho đợt' in item.value for item in [*at.info, *at.error])


def test_cloud_import_in_isolated_process(tmp_path):
    source = r'''import os, sys
from pathlib import Path
from types import SimpleNamespace
sys.path[:0] = [str(Path.cwd()), str(Path.cwd() / 'apps/retail_app')]
for name in ('duckdb', 'scripts.ingest.auto_mapping', 'scripts.ingest.dot'):
    sys.modules[name] = None
os.environ.update(RETAIL_BACKEND='databricks', RETAIL_BACKENDS='databricks', RETAIL_NHAP_DOT='volume')
from ui import kho_dot, nhap_dot, roles, nhap_runner
from streamlit.testing.v1 import AppTest
roles.current_role = lambda: 'admin'
roles.logged_in_user = lambda: {'username': 'test'}
roles.store = lambda: SimpleNamespace(log=lambda *a: None)
kho_dot.configured_store = lambda: kho_dot.KhoDia(sys.argv[1])
nhap_runner.dashboard_state_cloud = lambda: {'releases': {}}
nhap_runner.recover_queue = lambda *a, **kw: (_ for _ in ()).throw(AssertionError('local queue'))
for page in ('gui_du_lieu', 'duyet_du_lieu'):
    at = AppTest.from_file('apps/retail_app/views/' + page + '.py').run(timeout=20)
    assert not at.exception, at.exception
    assert not at.error, at.error
for name in ('duckdb', 'scripts.ingest.auto_mapping', 'scripts.ingest.dot'):
    assert sys.modules[name] is None
'''
    result = subprocess.run([sys.executable, '-I', '-B', '-X', 'utf8', '-c', source, str(tmp_path)],
                            cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=60)
    assert result.returncode == 0, result.stderr[-6000:]


@pytest.mark.parametrize('different', [False, True])
def test_forecast_note_only_when_different(monkeypatch, different):
    monkeypatch.setattr(common, 'info_strip', lambda: None)
    monkeypatch.setattr(releases, 'pointers_differ', lambda: different)
    monkeypatch.setattr(common, 'load_or_stop', lambda *a: pd.DataFrame({'data_end_date': ['2022-12-31']}))
    at = AppTest.from_string("from ui.common import page_header; page_header('Dự báo G và COGS', 'Dự báo?')").run()
    assert not at.exception
    assert bool(at.info) is different
    if different:
        assert 'số tới 2022-12-31' in at.info[0].value


REQUESTS = [pe.request_ps1('2019', 'year'), pe.request_ps4('2019', 'year', 2018, 2019, '2019'),
            pe.request_ps5('category', 2022), pe.request_ps4('2023', 'year', 2022, 2023, '2023'),
            pe.request_ps5('category', 2023), pe.request_ps1('2023', 'year'), pe.request_ps2(),
            pe.request_ps3('mua_vu'), pe.request_ps1('2013-2022', 'period'),
            pe.request_ps4('D', 'phase', 2019, 2022, 'D')]


@pytest.fixture
def ai_context(monkeypatch):
    state = {'active': 'a'*24, 'dashboard': RID, 'releases': {}}
    for rid, end in [('a'*24, 2022), (RID, 2023)]:
        state['releases'][rid] = {'release_id': rid, 'status': 'ready', 'schema': f'r_{rid}_reporting', 'end': end}
    monkeypatch.setenv('RETAIL_RELEASE_MODE', 'versioned')
    monkeypatch.setattr(releases, 'local_state', lambda: state)
    monkeypatch.setattr(ai_panel, 'backend', lambda: 'duckdb')
    monkeypatch.setattr(ai_panel, 'load_or_stop', lambda _: pd.DataFrame({'data_end_date': [f"{releases.resolve('duckdb')['end']}-12-31"]}))
    monkeypatch.setattr(ai_panel.provider, 'from_config', lambda: object())
    monkeypatch.setattr(roles, 'allowed', lambda *a: False)
    monkeypatch.setattr(roles, 'current_role', lambda: 'khach')
    calls = []
    monkeypatch.setattr(pe, 'explain', lambda *a, **kw: (calls.append(a) or SimpleNamespace(tokens=0)))
    monkeypatch.setattr(ai_panel, '_render', lambda *a: None)
    releases.reset('dashboard')
    yield state, calls
    releases.reset()


@pytest.mark.parametrize('index', range(len(REQUESTS)))
def test_ai_years_and_series_gate(ai_context, monkeypatch, index):
    state, calls = ai_context
    monkeypatch.setattr(pe, '_l1_request', REQUESTS[index], raising=False)
    source = "from dwh import releases\nfrom ui.ai_panel import ai_panel\nfrom ai_explain.page_explain import _l1_request\nreleases.resolve('duckdb', pointer='dashboard')\nai_panel(_l1_request)"
    at = AppTest.from_string(source).run()
    assert not at.exception
    allowed = index < 3
    assert bool(at.button) is allowed
    if allowed:
        at.button[0].click().run()
        assert not at.exception and len(calls) == 1
        assert all(key[1] == 'a'*24 for key in at.session_state['ai_page'])
        at.run()
        assert len(calls) == 1
    else:
        expected = 'tới năm 2022' if index < 6 else 'gộp cả dữ liệu demo'
        assert any(expected in caption.value for caption in at.caption)
        assert calls == []
    state['releases'][RID]['end'] = 2099
    at.run()
    assert not at.exception
    assert ('ai_page' in at.session_state) is allowed


@pytest.mark.parametrize('req', REQUESTS)
def test_ai_same_pointers_keeps_old_behavior(ai_context, req):
    state, _ = ai_context
    state['dashboard'] = state['active']
    releases.resolve('duckdb')
    assert ai_panel._demo_reason(req) is None
    assert ai_panel.ai_unavailable('duckdb', object(), req=req) is None
    assert ai_panel.ai_unavailable('duckdb', object(), chat=True) is None


def test_ai_all_calls_must_qualify(ai_context):
    releases.resolve('duckdb', pointer='dashboard')
    for extra in ({'year': 2023}, {'year': 2022, 'view': 'year'}, {'year': 2022, 'period_type': 'phase'}):
        req = pe.PageRequest('ps1', 'hai lời gọi', '', (('x', {'year': 2019}), ('y', extra)))
        assert ai_panel._demo_reason(req) is not None


def test_cloud_send_form_and_invisible_orphan(store, monkeypatch):
    import streamlit as st
    monkeypatch.setattr(st, 'file_uploader', lambda *a, **kw: [Upload()])
    at = cloud_page(store, monkeypatch, 'gui_du_lieu')
    at.text_input[0].set_value('dot_2023')
    at.text_area[0].set_value('Đợt thử')
    next(b for b in at.button if b.label == 'Gửi đợt dữ liệu').click().run()
    assert not at.exception and not at.error
    assert any('Đã gửi đợt dot_2023' in x.value for x in at.success)
    assert any('dot_2023 · Đã gửi' in x.label for x in at.expander)
    assert len(store.visible('admin1', 'admin')) == 1


def test_volume_client_uses_writer_credentials_only(monkeypatch):
    import databricks.sdk
    seen = []
    monkeypatch.setattr(connection, 'databricks_config', lambda: {'DATABRICKS_HOST': 'https://config.invalid', 'DATABRICKS_CLIENT_ID': 'reader-id'})
    for key, value in {'RETAIL_NHAP_DOT': 'volume', 'DATABRICKS_HOST': 'https://fake.invalid',
        'RETAIL_NHAP_DBX_CLIENT_ID': 'writer-id', 'RETAIL_NHAP_DBX_CLIENT_SECRET': 'fake-secret',
        'DATABRICKS_CLIENT_ID': 'reader-id', 'RETAIL_NHAP_VOLUME': '/Volumes/test/input'}.items():
        monkeypatch.setenv(key, value)
    files = FakeFiles()
    monkeypatch.setattr(databricks.sdk, 'WorkspaceClient', lambda **kw: (seen.append(kw) or SimpleNamespace(files=files)))
    kho = kd.configured_store()
    kho.ghi_moi('file/a.csv', b'abc')
    assert seen == [{'host': 'https://config.invalid', 'client_id': 'writer-id', 'client_secret': 'fake-secret', 'auth_type': 'oauth-m2m'}]
    assert list(files.data) == ['/Volumes/test/input/file/a.csv']


def test_corrupt_event_is_visible_as_hong(store):
    row = store.gui_dot([Upload()], 'dot', '')
    store.kho.ghi_moi(nd.request_path(row['id']) + '/su_kien/000003.json', b'{"toi":"dang_kiem"}')
    assert store.visible('admin1', 'admin')[0]['trang_thai'] == 'hong'


def test_pending_is_rechecked_on_click(store, monkeypatch):
    at = cloud_page(store, monkeypatch)
    store.kho.ghi_json_so_tiep('lenh', {'loai': 'tra', 'ai': 'other'})
    # Form đã vẽ khi chưa có lệnh, lệnh xuất hiện trước lúc gửi form.
    at.checkbox[0].check()
    next(b for b in at.button if b.label.startswith('Đưa bản')).click().run()
    assert not at.exception and store.kho.liet_ke('lenh') == ['000001.json']


def test_two_pending_buttons_disabled(store, monkeypatch):
    monkeypatch.setattr(nr, 'dashboard_state_cloud', lambda: {'dashboard': RID, 'releases': {
        RID: {'status': 'ready', 'co_du_lieu_tong_hop': True}}})
    store.kho.ghi_json_so_tiep('lenh', {'loai': 'tra', 'ai': 'other'})
    at = cloud_page(store, monkeypatch)
    assert not at.exception
    buttons = [b for b in at.button if 'dashboard' in b.label]
    assert len(buttons) == 2 and all(b.disabled for b in buttons)


@pytest.mark.parametrize('label,target', [('Chạy lại', 'cho_chay'), ('Hủy', 'huy')])
def test_review_retry_cancel_buttons(store, monkeypatch, label, target):
    row = advance(store, store.gui_dot([Upload()], 'dot', ''), ['dang_kiem', 'cho_chay', 'dang_chay', 'loi'])
    monkeypatch.setattr(roles, 'current_role', lambda: 'ky_su')
    at = cloud_page(store, monkeypatch)
    next(b for b in at.button if b.label == label).click().run()
    assert not at.exception and not at.error
    assert store.read(row['id'])['trang_thai'] == target


def test_review_ledger_reason_required(store, monkeypatch):
    store.kho.ghi_json_so_tiep('so_dot', {'loai': 'vao_so', 'ma_dot': 'a'*12, 'release_id': RID, 'request_id': REQUEST})
    monkeypatch.setattr(roles, 'current_role', lambda: 'ky_su')
    at = cloud_page(store, monkeypatch)
    assert len(at.dataframe[0].value) == 1
    next(b for b in at.button if b.label == 'Bỏ khỏi sổ').click().run()
    assert not at.exception and at.error and len(store.ledger()) == 1
    at.text_area[0].set_value('Loại ở lần dựng sau')
    next(b for b in at.button if b.label == 'Bỏ khỏi sổ').click().run()
    assert not at.exception and not at.error and store.ledger() == []


def test_mode_dia_from_config_and_exact_total_boundary(store, monkeypatch):
    monkeypatch.setenv('RETAIL_NHAP_DOT', 'dia')
    monkeypatch.setenv('RETAIL_NHAP_DIA', str(store.kho.root))
    assert isinstance(kd.configured_store(), kd.KhoDia)
    assert kd.configured_store().root == store.kho.root
    monkeypatch.setattr(nd, 'MAX_TOTAL_BYTES', 10)
    row = store.gui_dot([Upload(content=b'1234567890')], 'dot', '')
    assert row['files'][0]['so_byte'] == 10


def test_return_command_permission_rechecked_after_render(store, monkeypatch):
    monkeypatch.setattr(nr, 'dashboard_state_cloud', lambda: {'dashboard': RID, 'releases': {}})
    at = cloud_page(store, monkeypatch)
    assert any(b.label == 'Trả dashboard về bản số thật' for b in at.button)
    monkeypatch.setattr(roles, 'current_role', lambda: 'quan_ly')
    with pytest.raises(PermissionError):
        store.dashboard_command()
    assert store.kho.liet_ke('lenh') == []


@pytest.mark.skipif(os.name != 'nt', reason='Tiền tố đường dẫn thiết bị của Windows')
def test_windows_device_prefix_keeps_root_boundary(tmp_path, monkeypatch):
    kho = kd.KhoDia(tmp_path)
    original = Path.resolve
    monkeypatch.setattr(Path, 'resolve', lambda self, *a, **kw: Path('//?/' + original(self, *a, **kw).as_posix()))
    kho.ghi_moi('lenh/000001.json', b'{}')
    assert kho.doc('lenh/000001.json') == b'{}'
    assert kd._comparison_path(Path('//?/UNC/server/share/path')) == Path('//server/share/path')


@pytest.mark.parametrize('record', [
    {'status': 'building', 'co_du_lieu_tong_hop': True},
    {'status': 'ready', 'co_du_lieu_tong_hop': False},
    {'status': 'ready', 'co_du_lieu_tong_hop': 1},
    {'status': 'ready'}, {},
])
def test_c2_command_rejects_ineligible_release(store, monkeypatch, record):
    monkeypatch.setattr(nr, 'dashboard_state_cloud', lambda: {'releases': {RID: record}})
    with pytest.raises(ValueError, match='quality gate'):
        store.dashboard_command(RID, confirmed=True)
    assert store.kho.liet_ke('lenh') == []


def test_c5_pending_label_only_for_matching_request(store):
    a = advance(store, store.gui_dot([Upload()], 'a', ''),
                ['dang_kiem', 'cho_chay', 'dang_chay', 'da_kiem'])
    store.dashboard_command(RID, confirmed=True)
    b = advance(store, store.gui_dot([Upload()], 'b', ''),
                ['dang_kiem', 'cho_chay', 'dang_chay', 'da_kiem'])
    command = store.latest_command()
    assert store.label(a, command) == 'Chờ đưa lên dashboard'
    assert store.label(b, command) == 'Đã kiểm tra'


@pytest.mark.parametrize('states', [[], ['dang_kiem', 'cho_chay', 'dang_chay', 'da_kiem']])
@pytest.mark.parametrize('target', ['cho_chay', 'huy'])
def test_c11_change_rejects_non_error_without_event(store, monkeypatch, states, target):
    row = advance(store, store.gui_dot([Upload()], 'a', ''), states)
    folder = nd.request_path(row['id']) + '/su_kien'
    before = {n: store.kho.doc(folder + '/' + n) for n in store.kho.liet_ke(folder)}
    monkeypatch.setattr(roles, 'current_role', lambda: 'ky_su')
    with pytest.raises(ValueError):
        store.change(row['id'], target)
    assert {n: store.kho.doc(folder + '/' + n) for n in store.kho.liet_ke(folder)} == before
    assert store.read(row['id'])['trang_thai'] == row['trang_thai']


def test_single_file_kept_with_databricks_backend(store, monkeypatch):
    from ui import nhap_store
    monkeypatch.setenv('RETAIL_BACKEND', 'databricks')
    monkeypatch.setenv('RETAIL_BACKENDS', 'databricks')
    monkeypatch.setattr(nhap_store, 'nhap_kha_dung', lambda: True)
    monkeypatch.setattr(nhap_store, 'RequestStore', lambda: object())
    monkeypatch.setattr(nr, 'recover_queue', lambda *a, **kw: None)
    monkeypatch.setattr(nr, 'page_snapshot', lambda *a, **kw: {'rows': [], 'busy': False, 'pending': False, 'waiting_columns': False})
    at = AppTest.from_file(str(APP / 'views/gui_du_lieu.py')).run()
    assert not at.exception
    assert any(b.label == 'Gửi dữ liệu' for b in at.button)
    assert not any(b.label == 'Gửi đợt dữ liệu' for b in at.button)


def test_review_single_file_kept_with_databricks_backend(store, monkeypatch):
    from ui import nhap_store
    monkeypatch.setenv('RETAIL_BACKEND', 'databricks')
    monkeypatch.setenv('RETAIL_BACKENDS', 'databricks')
    monkeypatch.setenv('RETAIL_NHAP_DOT', 'tat')
    monkeypatch.setattr(nhap_store, 'nhap_kha_dung', lambda: True)
    monkeypatch.setattr(nhap_store, 'RequestStore',
                        lambda: SimpleNamespace(base=ROOT, sync_events=lambda: 0))
    monkeypatch.setattr(nr, 'recover_queue', lambda *a, **kw: None)
    monkeypatch.setattr(nr, 'page_snapshot', lambda *a, **kw: {'rows': []})
    at = AppTest.from_file(str(APP / 'views/duyet_du_lieu.py')).run()
    assert not at.exception and not at.error
    assert any(c.value.startswith('Chỉ chạy DuckDB local.') for c in at.caption)
    assert any(i.value == 'Chưa có yêu cầu.' for i in at.info)
    assert not any(h.value == 'Đợt dữ liệu' for h in at.subheader)


def test_dashboard_since_other_release_is_hidden(store, monkeypatch):
    monkeypatch.setattr(nr, 'dashboard_state_cloud', lambda: {
        'dashboard': RID, 'dashboard_since': {'release_id': 'a'*24, 'at': '2026-11-08T12:00:00Z'},
        'releases': {}})
    at = cloud_page(store, monkeypatch)
    assert not at.exception and not at.error
    assert not any('Giờ công bố' in c.value for c in at.caption)


@pytest.mark.parametrize('damage', ['json', 'nguoi_gui', 'ngay_gui', 'type', 'files_not_list',
    'file_number', 'file_missing_size', 'file_bool_size', 'file_string_size',
    'file_float_size', 'file_missing_name', 'file_number_name'])
def test_corrupt_metadata_isolated_per_request(store, monkeypatch, damage):
    good = store.gui_dot([Upload()], 'good', '')
    bad = store.gui_dot([Upload()], 'bad', '')
    path = store.kho._path(nd.request_path(bad['id']) + '/yeu_cau.json')
    metadata = json.loads(path.read_bytes())
    if damage == 'json':
        path.write_bytes(b'{')
    else:
        if damage == 'type':
            metadata['ngay_gui'] = None
        elif damage == 'files_not_list':
            metadata['files'] = {}
        elif damage == 'file_number':
            metadata['files'] = [7]
        elif damage == 'file_missing_size':
            metadata['files'][0].pop('so_byte')
        elif damage in ('file_bool_size', 'file_string_size', 'file_float_size'):
            metadata['files'][0]['so_byte'] = {
                'file_bool_size': True, 'file_string_size': '12', 'file_float_size': 1.5}[damage]
        elif damage == 'file_missing_name':
            metadata['files'][0].pop('ten')
        elif damage == 'file_number_name':
            metadata['files'][0]['ten'] = 7
        else:
            metadata.pop(damage)
        path.write_text(json.dumps(metadata), encoding='utf-8')
    for role in ('quan_ly', 'phan_tich'):
        assert [r['id'] for r in store.visible('admin1', role)] == [good['id']]
    for role in ('ky_su', 'admin'):
        rows = {r['id']: r for r in store.visible('admin1', role)}
        assert rows[bad['id']]['trang_thai'] == 'hong'
        assert rows[good['id']]['trang_thai'] == 'da_gui'
    at = cloud_page(store, monkeypatch)
    assert not at.exception and not at.error
    assert any('Dữ liệu trạng thái hỏng' in e.label for e in at.expander)
