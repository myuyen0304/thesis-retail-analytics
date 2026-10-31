"""Kiểm local bằng file tạm và CLI giả, không train/build/cloud/Neon thật."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from ui import roles, nhap_store as ns, nhap_runner as nr
from scripts.ingest import auto_mapping, approval
from scripts.pipeline.state import atomic_json, writer_lock

VIEWS = Path(__file__).resolve().parents[1] / 'views'


@pytest.fixture
def store(tmp_path):
    return ns.RequestStore(tmp_path)


@pytest.fixture
def identity(monkeypatch):
    events = []
    monkeypatch.setenv('RETAIL_APP_NHAP_DU_LIEU', '1')
    monkeypatch.setattr(roles, 'current_role', lambda: 'admin')
    monkeypatch.setattr(roles, 'logged_in_user', lambda: {'username': 'admin1'})
    monkeypatch.setattr(roles, 'store', lambda: SimpleNamespace(log=lambda *args: events.append(args)))
    return events


def upload(name='orders_enriched.csv', body=b'order_id,comment\n1,hello\n'):
    f = io.BytesIO(body)
    f.name, f.size = name, len(body)
    return f


def sample():
    return {'nguon': {'de_xuat': 'orders', 'diem': []},
        'file': {'ten': 'orders_enriched.csv', 'so_dong': 1, 'so_cot': 2},
        'schema_diff': {'cot_them': ['comment']}, 'thuc_the_moi': [],
        'cot': [{'ten_trong_file': 'order_id', 'loai': 'khop', 'cot_hop_dong': 'order_id'},
                {'ten_trong_file': 'comment', 'loai': 'thuoc_tinh_le', 'nghi_pii': True,
                 'thong_ke': {'so_rong': 0}}]}


def pending(store):
    r = store.create(upload(), 'Thêm thông tin', 'manager')
    d = store.folder(r['id']) / 'de_xuat'
    d.mkdir()
    (d / 'mapping_de_xuat.yml').write_text(yaml.safe_dump(sample()), encoding='utf-8')
    (d / 'bao_cao_mapping.md').write_text('BÁO CÁO KỸ THUẬT MẪU GIÁ TRỊ', encoding='utf-8')
    return store.transition(r['id'], r['revision'], 'cho_duyet', 'manager')


def ready(store):
    r = pending(store)
    return store.transition(r['id'], r['revision'], 'da_duyet', 'de', ten_mo_rong='orders_enriched')


@pytest.mark.parametrize('name,expected', [('../x.csv', 'x.csv'), ('a\\b.json', 'b.json'), ('A B.CSV', 'a_b.csv')])
def test_filename(store, name, expected):
    r = store.create(upload(name), '', 'manager')
    assert r['ten_file'] == expected
    path = store.base / 'data/ui_nhap' / r['id'] / expected
    assert path.read_bytes() == upload().getvalue()
    assert r['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert path.resolve().is_relative_to(store.base)


@pytest.mark.parametrize('name', ['.exe', 'a.exe', 'CON.csv', '../.csv'])
def test_bad_filename(store, name):
    with pytest.raises(ValueError):
        store.create(upload(name), '', 'x')


def test_size_limit(store, monkeypatch):
    f = upload()
    f.size = ns.MAX_BYTES + 1
    with pytest.raises(ValueError, match='200 MB'):
        store.create(f, '', 'x')
    monkeypatch.setattr(ns, 'MAX_BYTES', 5)
    f = upload()
    f.size = 1
    with pytest.raises(ValueError, match='200 MB'):
        store.create(f, '', 'x')
    assert not list(store.requests.glob('*/yeu_cau.json'))


EXPECTED = {
    'da_gui': {'cho_duyet', 'loi_de_xuat'}, 'cho_duyet': {'da_duyet', 'cho_model_dbt', 'tu_choi'},
    'da_duyet': {'dang_chay'}, 'dang_chay': {'da_kiem', 'loi', 'da_cong_bo'}, 'loi': {'dang_chay'},
    'da_kiem': {'da_cong_bo'}, 'da_cong_bo': {'dang_chay'}, 'cho_model_dbt': set(), 'tu_choi': set(), 'loi_de_xuat': set()}


@pytest.mark.parametrize('before', EXPECTED)
def test_transition_matrix(store, before):
    for after in EXPECTED:
        r = store.create(upload(), '', 'x')
        r['trang_thai'] = before
        atomic_json(store.folder(r['id']) / 'yeu_cau.json', r)
        if after in EXPECTED[before]:
            result = store.transition(r['id'], 0, after, 'de')
            assert result['lich_su'][-1]['tu'] == before
            assert result['lich_su'][-1]['toi'] == after
        else:
            with pytest.raises(ValueError, match='không hợp lệ'):
                store.transition(r['id'], 0, after, 'de')
            assert store.read(r['id']) == r


def test_concurrent_cas(store):
    r = pending(store)
    def attempt():
        try:
            store.transition(r['id'], r['revision'], 'tu_choi', 'de', 'Không phù hợp')
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(lambda _: attempt(), range(2))) == [False, True]
    assert len(store.read(r['id'])['lich_su']) == 3


def test_atomic_failure_keeps_previous(store, monkeypatch):
    r = pending(store)
    path = store.folder(r['id']) / 'yeu_cau.json'
    before = path.read_bytes()
    monkeypatch.setattr('scripts.pipeline.state.os.replace', lambda *args: (_ for _ in ()).throw(OSError('disk failure')))
    with pytest.raises(ValueError):
        store.transition(r['id'], r['revision'], 'tu_choi', 'de', 'reason')
    assert path.read_bytes() == before


def test_visibility_and_roles(store, monkeypatch):
    r = pending(store)
    for flag in ('0', '', '1'):
        monkeypatch.setenv('RETAIL_APP_NHAP_DU_LIEU', flag)
        for role in roles.ROLES:
            assert roles.allowed(role, 'gui_du_lieu') == ('gui_du_lieu' in roles.PAGES_BY_ROLE[role])
            assert roles.allowed(role, 'gui_du_lieu') == (flag == '1' and role != 'khach')
            assert roles.allowed(role, 'duyet_du_lieu') == (flag == '1' and role in ('ky_su', 'admin'))
    assert not store.visible('outsider', 'quan_ly')
    assert not store.visible('outsider', 'phan_tich')
    assert not store.visible('manager', 'khach')
    assert store.visible('outsider', 'ky_su')[0]['id'] == r['id']
    assert store.visible('manager', 'quan_ly')[0]['id'] == r['id']


def test_actor_preview_and_audit(store, identity, monkeypatch):
    r = pending(store)
    monkeypatch.setattr(roles, 'current_role', lambda: 'quan_ly')
    with pytest.raises(PermissionError):
        store.reject(r['id'], r['revision'], 'reason')
    monkeypatch.setattr(roles, 'current_role', lambda: 'ky_su')
    with pytest.raises(PermissionError):
        nr.publish(store, r['id'], r['revision'])
    with pytest.raises(ValueError, match='lý do'):
        store.reject(r['id'], r['revision'], ' ')
    result = store.reject(r['id'], r['revision'], 'Sai khóa')
    assert result['trang_thai'] == 'tu_choi'
    assert identity == [('admin1', 'nhap_tu_choi', {'id': r['id'], 'ly_do': 'Sai khóa'})]


def test_pii_silver_small():
    assert approval.default_decisions(sample())['cot'][1]['hien_thi'] == 'silver'


def test_approval_and_model_gate(store, identity):
    r = pending(store)
    d = approval.default_decisions(sample())
    bad = deepcopy(d)
    bad['cot'].pop()
    with pytest.raises(ValueError, match='header/cot'):
        store.approve(r['id'], r['revision'], bad, 'custom_upload')
    assert not list((store.folder(r['id']) / 'hop_dong').glob('*.yml'))
    result = store.approve(r['id'], r['revision'], d, 'custom_upload')
    assert result['trang_thai'] == 'cho_model_dbt'
    with pytest.raises(ValueError):
        nr.start(store, r['id'], result['revision'])
    assert identity[-1][1] == 'nhap_duyet'


def test_submit_error_and_audit(store, identity, monkeypatch):
    monkeypatch.setattr(auto_mapping, 'propose', lambda *a: (_ for _ in ()).throw(ValueError('CSV hỏng')))
    result = store.submit(upload(), '')
    assert result['trang_thai'] == 'loi_de_xuat'
    assert result['loi_ky_thuat'] == 'ValueError: CSV hỏng'
    assert 'UTF-8' in result['lich_su'][-1]['ghi_chu']
    assert identity[-1][1] == 'nhap_gui'


@pytest.mark.parametrize('stage', [*nr.STAGES, 'publish'])
def test_commands(stage, tmp_path):
    cmd = nr.lenh(stage, 'ui-demo-1', 'orders_enriched', tmp_path)
    assert cmd[:3] == [sys.executable, '-m', 'scripts.pipeline.cli']
    assert cmd[cmd.index('--target') + 1] == 'duckdb'
    assert cmd[cmd.index('--root') + 1] == 'warehouse/pipeline/ui-nhap'
    assert 'databricks' not in cmd and 'warehouse/pipeline/docker' not in cmd
    assert ('--extension-dir' in cmd) == (stage == 'prepare')
    assert ('--extension' in cmd) == (stage == 'prepare')


def test_root_guard(monkeypatch, tmp_path):
    monkeypatch.setattr(nr, 'PIPELINE_ROOT', 'warehouse/pipeline/docker')
    with pytest.raises(ValueError, match='Root'):
        nr.lenh('prepare', 'ui-demo-1', 'orders_enriched', tmp_path)


def test_writer_lock_blocks_start(store, identity, monkeypatch):
    r = ready(store)
    monkeypatch.setattr(nr.subprocess, 'Popen', lambda *a, **kw: pytest.fail('Không được spawn khi khóa đang giữ'))
    with writer_lock(store.base / nr.PIPELINE_ROOT):
        assert 'writer.lock' in nr.busy_reason(store)
        with pytest.raises(ValueError, match='writer.lock'):
            nr.start(store, r['id'], r['revision'])
    assert store.read(r['id'])['trang_thai'] == 'da_duyet'


def test_worker_os_exit_releases_slot(store, identity, monkeypatch):
    old = ready(store)
    new = ready(store)
    monkeypatch.setattr(nr, 'has_dbt_model', lambda *a: True)
    real_popen = subprocess.Popen
    processes = []
    script = (
        'import os, sys\n'
        'from apps.retail_app.ui import nhap_runner as nr\n'
        'from apps.retail_app.ui.nhap_store import RequestStore\n'
        'nr._stage = lambda *args: os._exit(23)\n'
        'nr.run_worker(RequestStore(sys.argv[1]), sys.argv[2], sys.argv[3])\n'
    )
    def spawn(cmd, **kwargs):
        if processes:
            return SimpleNamespace(pid=os.getpid())
        kwargs['cwd'] = nr.ROOT
        kwargs['env'] = {**kwargs['env'], 'PYTHONPATH': str(nr.ROOT)}
        process = real_popen([sys.executable, '-c', script, str(store.base), cmd[-2], cmd[-1]], **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(nr.subprocess, 'Popen', spawn)
    nr.start(store, old['id'], old['revision'])
    assert processes[0].wait(timeout=15) == 23
    assert (store.root / 'active.json').exists()  # os._exit bỏ qua finally.
    assert nr.busy_reason(store) == ''
    assert store.read(old['id'])['trang_thai'] == 'loi'
    current = nr.start(store, new['id'], new['revision'])
    assert current['trang_thai'] == 'dang_chay'
    failed = store.read(old['id'])
    assert failed['trang_thai'] == 'loi'
    assert failed['thong_bao'] == failed['lich_su'][-1]['ghi_chu'] == 'worker dừng bất thường'
    assert nr._pid_alive(processes[0].pid) is False


def test_worker_lock_blocks_without_marker(store):
    with writer_lock(store.root / 'worker'):
        assert 'Đang có một lượt' in nr.busy_reason(store)
    assert nr.busy_reason(store) == ''


def test_worker_waits_for_short_lock_contention(store, identity, monkeypatch):
    record = launch_fake(store, identity, monkeypatch)
    stages = []
    def fake_stage(store, record, stage, output):
        stages.append(stage)
        return {'stage': stage, 'target': 'duckdb'}
    monkeypatch.setattr(nr, '_stage', fake_stage)
    acquired = threading.Event()
    def hold_worker_lock():
        with writer_lock(store.root / 'worker'):
            acquired.set()
            time.sleep(0.5)
    with ThreadPoolExecutor(max_workers=1) as pool:
        holding = pool.submit(hold_worker_lock)
        assert acquired.wait(5)
        result = nr.run_worker(store, record['id'], record['run_id'])
        holding.result(timeout=5)
    assert result['trang_thai'] == 'da_kiem'
    assert stages == list(nr.STAGES)
    assert not (store.root / 'active.json').exists()


def test_worker_early_exit_clears_marker(store, identity, monkeypatch):
    record = ready(store)
    atomic_json(store.root / 'active.json', {'id': record['id'], 'run_id': 'ui-old-1'})
    with pytest.raises(ValueError, match='không còn hiệu lực'):
        nr.run_worker(store, record['id'], 'ui-old-1')
    assert not (store.root / 'active.json').exists()


def test_worker_startup_lock_failure_reconciles(store, identity, monkeypatch):
    record = launch_fake(store, identity, monkeypatch)
    real_lock = nr.writer_lock
    @contextmanager
    def fail_dispatch(root):
        if Path(root).name == 'dispatch':
            raise OSError('khóa bận')
        with real_lock(root):
            yield
    monkeypatch.setattr(nr, 'writer_lock', fail_dispatch)
    monkeypatch.setattr(nr.time, 'sleep', lambda delay: None)
    with pytest.raises(RuntimeError, match='Không lấy được khóa'):
        nr.run_worker(store, record['id'], record['run_id'])
    failed = store.read(record['id'])
    assert failed['trang_thai'] == 'loi'
    assert failed['thong_bao'] == 'worker dừng bất thường'
    assert not (store.root / 'active.json').exists()


def test_stage_hides_windows_console(store, monkeypatch):
    record = ready(store)
    record['run_id'] = 'ui-demo-1'
    monkeypatch.setattr(nr, 'os', SimpleNamespace(name='nt', environ={}))
    def capture(cmd, **kwargs):
        assert kwargs['creationflags'] == subprocess.CREATE_NO_WINDOW
        raise RuntimeError('Đã kiểm creationflags')
    monkeypatch.setattr(nr.subprocess, 'run', capture)
    with pytest.raises(RuntimeError, match='Đã kiểm'):
        nr._stage(store, record, 'prepare', io.BytesIO())


def launch_fake(store, identity, monkeypatch):
    r = ready(store)
    monkeypatch.setattr(nr, 'has_dbt_model', lambda *a: True)
    with monkeypatch.context() as patch:
        patch.setattr(nr.subprocess, 'Popen', lambda *a, **kw: SimpleNamespace(pid=1234))
        return nr.start(store, r['id'], r['revision'])


@pytest.mark.parametrize('failure', [None, 'prepare', 'forecast', 'build', 'validate'])
def test_worker_fake_cli_stops(store, identity, monkeypatch, tmp_path, failure):
    r = launch_fake(store, identity, monkeypatch)
    # Tiến trình CLI giả thực sự chạy; không gọi module pipeline thật.
    fake = tmp_path / 'fake_cli.py'
    fake.write_text("import json,sys\nfrom pathlib import Path\ns= sys.argv[1]\np=Path(sys.argv[2]); p.parent.mkdir(parents=True,exist_ok=True)\nif s==sys.argv[3]: print('Lỗi giả'); sys.exit(7)\np.write_text(json.dumps({'target':'duckdb','stage':{'prepare':'prepared','forecast':'forecasted','build':'built','validate':'validated','publish':'published'}[s]}))\n", encoding='utf-8')
    calls = []
    real_run = subprocess.run
    def fake_run(cmd, **kwargs):
        stage = cmd[3]
        calls.append(stage)
        return real_run([sys.executable, str(fake), stage, str(nr.context_path(store, r['run_id'])), failure or 'none'], **kwargs)
    monkeypatch.setattr(nr.subprocess, 'run', fake_run)
    result = nr.run_worker(store, r['id'], r['run_id'])
    assert calls == list(nr.STAGES[:nr.STAGES.index(failure) + 1] if failure else nr.STAGES)
    assert result['trang_thai'] == ('loi' if failure else 'da_kiem')
    assert not (store.root / 'active.json').exists()
    assert identity[-1][1] == 'nhap_chay'
    if failure:
        assert result['stage'] == failure and 'mã 7' in result['thong_bao']
        with monkeypatch.context() as patch:
            patch.setattr(nr.subprocess, 'Popen', lambda *a, **kw: SimpleNamespace(pid=2345))
            retry = nr.start(store, r['id'], result['revision'])
        assert retry['run_id'] != r['run_id']
    else:
        result = nr.publish(store, r['id'], result['revision'])
        assert result['trang_thai'] == 'da_cong_bo'
        assert calls[-1] == 'publish' and identity[-1][1] == 'nhap_cong_bo'


def test_published_skip_keeps_state(store, identity, monkeypatch):
    r = launch_fake(store, identity, monkeypatch)
    r['truoc_chay'] = 'da_cong_bo'
    store.save(r)
    calls = []
    def skip(*args):
        calls.append(args[2])
        return {'stage': 'skipped', 'target': 'duckdb'}
    monkeypatch.setattr(nr, '_stage', skip)
    result = nr.run_worker(store, r['id'], r['run_id'])
    assert result['trang_thai'] == 'da_cong_bo'
    assert result['thong_bao'] == 'Không có gì mới, bỏ qua'
    assert calls == ['prepare']


@pytest.mark.parametrize('role', ['quan_ly', 'phan_tich', 'ky_su', 'admin'])
def test_sender_page_privacy(store, identity, monkeypatch, role):
    r = pending(store)
    monkeypatch.setattr(roles, 'current_role', lambda: role)
    monkeypatch.setattr(roles, 'logged_in_user', lambda: {'username': 'manager'})
    monkeypatch.setattr(ns, 'RequestStore', lambda: store)
    at = AppTest.from_file(str(VIEWS / 'gui_du_lieu.py')).run()
    assert not at.exception
    report = ' '.join(x.value for x in at.markdown)
    assert ('BÁO CÁO KỸ THUẬT' in report) == (role != 'quan_ly')


def test_review_page_and_reject(store, identity, monkeypatch):
    r = pending(store)
    monkeypatch.setattr(ns, 'RequestStore', lambda: store)
    at = AppTest.from_file(str(VIEWS / 'duyet_du_lieu.py')).run()
    assert not at.exception
    assert any(b.label == 'Duyệt' for b in at.button)
    next(t for t in at.text_area if 'Lý do từ chối' in t.label).set_value('Khóa sai')
    next(b for b in at.button if b.label == 'Từ chối').click().run()
    assert not at.exception
    assert store.read(r['id'])['trang_thai'] == 'tu_choi'


@pytest.mark.parametrize('page', ['gui_du_lieu', 'duyet_du_lieu'])
def test_page_recovers_dead_worker(store, identity, monkeypatch, page):
    record = launch_fake(store, identity, monkeypatch)
    monkeypatch.setattr(nr, '_pid_alive', lambda pid: False)
    monkeypatch.setattr(ns, 'RequestStore', lambda: store)
    at = AppTest.from_file(str(VIEWS / f'{page}.py')).run()
    assert not at.exception
    assert store.read(record['id'])['trang_thai'] == 'loi'
    assert not (store.root / 'active.json').exists()


@pytest.mark.parametrize('page', ['gui_du_lieu', 'duyet_du_lieu'])
def test_pages_feature_off(identity, monkeypatch, page):
    monkeypatch.setenv('RETAIL_APP_NHAP_DU_LIEU', '0')
    at = AppTest.from_file(str(VIEWS / f'{page}.py')).run()
    assert not at.exception
    assert at.error and not at.button


def test_summary_readonly_and_skip(store):
    import duckdb
    r = ready(store)
    r['run_id'] = 'ui-demo-1'
    rid = 'a' * 24
    path = store.base / nr.PIPELINE_ROOT / 'runs/ui-demo-1/dbt.duckdb'
    path.parent.mkdir(parents=True)
    with duckdb.connect(str(path)) as con:
        con.execute(f'create schema r_{rid}_marts')
        con.execute(f'create table r_{rid}_marts.dim_sales_employee as select 1 as id union all select 2')
        con.execute(f'create table r_{rid}_marts.fact_order as select 1 as sales_employee_sk union all select NULL')
    context = {'target': 'duckdb', 'stage': 'published', 'release_id': rid, 'run_id': r['run_id'],
               'duckdb_path': str(path), 'snapshot_id': 's', 'quality': {'daily_rows': 3833}, 'so_dong_cach_ly': {}}
    nr.save_context(store, r, context)
    result = nr.summary(store, r)
    assert result['dim_sales_employee'] == 2 and result['orders_with_employee'] == 1
    nr.save_context(store, r, {'target': 'duckdb', 'stage': 'skipped'})
    assert nr.summary(store, r) == result


def test_worker_survives_session_state(store, identity, monkeypatch):
    r = ready(store)
    monkeypatch.setattr(nr, 'has_dbt_model', lambda *a: True)
    seen = []
    def spawn(cmd, **kwargs):
        seen.append((cmd, kwargs))
        return SimpleNamespace(pid=os.getpid())
    monkeypatch.setattr(nr.subprocess, 'Popen', spawn)
    result = nr.start(store, r['id'], r['revision'])
    fresh = ns.RequestStore(store.base).read(r['id'])
    assert fresh['run_id'] == result['run_id'] and fresh['worker_pid'] == os.getpid()
    assert fresh['trang_thai'] == 'dang_chay'
    cmd, kwargs = seen[0]
    assert cmd[:3] == [sys.executable, '-m', 'apps.retail_app.ui.nhap_runner']
    assert kwargs['stdin'] == subprocess.DEVNULL and kwargs['close_fds']
    with pytest.raises(ValueError, match='Đang có'):
        nr.start(store, r['id'], result['revision'])


@pytest.mark.parametrize('action', ['start', 'publish'])
def test_dispatch_competition_message(store, identity, action):
    r = ready(store)
    with writer_lock(store.root / 'dispatch'):
        with pytest.raises(ValueError, match='Trạng thái đã đổi'):
            getattr(nr, action)(store, r['id'], r['revision'])
    assert store.read(r['id']) == r
