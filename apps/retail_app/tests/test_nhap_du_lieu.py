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
import streamlit as st
from streamlit.testing.v1 import AppTest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from ui import roles, nhap_store as ns, nhap_runner as nr
from scripts.ingest import auto_mapping, approval, extension_contract
from scripts.pipeline.state import atomic_json, writer_lock

VIEWS = Path(__file__).resolve().parents[1] / 'views'


@pytest.fixture
def store(tmp_path):
    return ns.RequestStore(tmp_path)


@pytest.fixture
def identity(monkeypatch):
    events = []
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
    r = store.transition(r['id'], r['revision'], 'da_duyet', 'de', ten_mo_rong='orders_enriched')
    request_contract(store, r)
    return r


def request_contract(store, record):
    doc = extension_contract.load(record['ten_mo_rong'])
    doc['file'] = f"ui_nhap/{record['id']}/{record['ten_file']}"
    folder = store.folder(record['id']) / 'hop_dong'
    folder.mkdir(exist_ok=True)
    (folder / (doc['ten'] + '.yml')).write_text(yaml.safe_dump(doc), encoding='utf-8')


def active_extensions(store, names, rid='a' * 24):
    """Bản active giả có context và hợp đồng thật, không chạm registry của repo."""
    run_id = 'ui-active-' + rid[:1]
    directory = store.base / 'contracts' / rid
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        doc = extension_contract.load(name)
        doc['file'] = f'fixture/{rid}/{name}.csv'
        data = store.base / 'data' / doc['file']
        data.parent.mkdir(parents=True, exist_ok=True)
        data.write_text('order_id\n1\n', encoding='utf-8')
        (directory / (name + '.yml')).write_text(yaml.safe_dump(doc), encoding='utf-8')
    atomic_json(nr.context_path(store, run_id), {'run_id': run_id, 'release_id': rid,
        'target': 'duckdb', 'stage': 'published', 'extensions': names, 'extension_dir': str(directory)})
    state = store.pipeline_state()
    state.setdefault('releases', {})[rid] = {'run_id': run_id, 'status': 'ready'}
    state['active'] = rid
    atomic_json(store.base / nr.PIPELINE_ROOT / 'state.json', {'version': 'test', 'payload': state})
    return directory


def shipment_request(store):
    r = ready(store)
    r['ten_mo_rong'] = 'shipments_realistic'
    request_contract(store, r)
    return store.save(r)


@pytest.mark.parametrize('route', ['tay', 'tu_dong', 'nap_bu'])
def test_b4_start_unions_active_and_refreshes_for_retry(store, monkeypatch, route):
    r = shipment_request(store)
    r['duong'] = 'tu_dong' if route != 'tay' else 'tay'
    if route == 'nap_bu':
        r['nap_bu_tu'] = 'source-request'
    store.save(r)
    request_dir = store.folder(r['id']) / 'hop_dong'
    request_bytes = {p.name: p.read_bytes() for p in request_dir.iterdir()}
    active_extensions(store, [], 'b' * 24)
    # Active xuất hiện sau lúc duyệt: phải lấy lúc bắt đầu.
    directory = active_extensions(store, ['orders_enriched'])
    monkeypatch.setattr(nr, 'has_dbt_model', lambda *a: True)
    monkeypatch.setattr(nr.subprocess, 'Popen', lambda *a, **kw: SimpleNamespace(pid=123))
    started = nr._start_locked(store, r['id'], r['revision'], 'he_thong')
    assert started['mo_rong_chay'] == ['orders_enriched', 'shipments_realistic']
    dest = store.folder(r['id']) / 'chay' / started['run_id'] / 'hop_dong/orders_enriched.yml'
    assert dest.read_bytes() == (directory / 'orders_enriched.yml').read_bytes()
    before = dest.read_bytes()
    old_bytes = {p.name: p.read_bytes() for p in dest.parent.iterdir()}
    state = store.pipeline_state()
    state['active'] = 'b' * 24
    atomic_json(store.base / nr.PIPELINE_ROOT / 'state.json', {'payload': state})
    failed = store.transition(r['id'], started['revision'], 'loi', 'he_thong')
    retried = nr._start_locked(store, r['id'], failed['revision'], 'de')
    assert retried['mo_rong_chay'] == ['shipments_realistic']
    assert dest.read_bytes() == before
    assert {p.name: p.read_bytes() for p in dest.parent.iterdir()} == old_bytes
    commands = []
    def stage(cmd, **kw):
        commands.append(cmd)
        atomic_json(nr.context_path(store, retried['run_id']), {'target': 'duckdb', 'stage': 'prepared'})
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(nr.subprocess, 'run', stage)
    nr._stage(store, retried, 'prepare', io.BytesIO())
    cmd, = commands
    assert [cmd[i + 1] for i, arg in enumerate(cmd) if arg == '--extension'] == retried['mo_rong_chay']
    assert Path(cmd[cmd.index('--extension-dir') + 1]) == store.folder(r['id']) / 'chay' / retried['run_id'] / 'hop_dong'
    assert {p.name: p.read_bytes() for p in request_dir.iterdir()} == request_bytes


def test_b4_no_active_and_same_name_request_wins(store):
    r = shipment_request(store)
    assert nr._extensions_for_run(store, r)[0] == ['shipments_realistic']
    active_extensions(store, ['orders_enriched', 'shipments_realistic'])
    own = store.folder(r['id']) / 'hop_dong/shipments_realistic.yml'
    before = own.read_bytes()
    names, copies = nr._extensions_for_run(store, r)
    assert names == ['orders_enriched', 'shipments_realistic']
    assert copies['shipments_realistic'] == before
    assert own.read_bytes() == before


@pytest.mark.parametrize('initial', ['loi', 'da_cong_bo'])
def test_b6_new_run_adds_new_active_extension_and_preserves_old_bytes(store, monkeypatch, initial):
    r = ready(store)
    request_dir = store.folder(r['id']) / 'hop_dong'
    original = {p.name: p.read_bytes() for p in request_dir.iterdir()}
    monkeypatch.setattr(nr, 'has_dbt_model', lambda *a: True)
    monkeypatch.setattr(nr.subprocess, 'Popen', lambda *a, **kw: SimpleNamespace(pid=123))
    first = nr._start_locked(store, r['id'], r['revision'], 'de')
    old_dir = store.folder(r['id']) / 'chay' / first['run_id'] / 'hop_dong'
    old_bytes = {p.name: p.read_bytes() for p in old_dir.iterdir()}
    # Active có chính yêu cầu này và một phần mới; hợp đồng own của active khác byte.
    active_dir = active_extensions(store, ['orders_enriched', 'shipments_realistic'])
    active_bytes = {p.name: p.read_bytes() for p in active_dir.iterdir()}
    first['trang_thai'] = initial
    store.save(first)
    second = nr._start_locked(store, r['id'], first['revision'], 'de')
    assert second['lan_chay'] == first['lan_chay'] + 1
    assert second['mo_rong_chay'] == ['orders_enriched', 'shipments_realistic']
    new_dir = store.folder(r['id']) / 'chay' / second['run_id'] / 'hop_dong'
    assert {p.name: p.read_bytes() for p in new_dir.iterdir()} == {
        'orders_enriched.yml': original['orders_enriched.yml'],
        'shipments_realistic.yml': active_bytes['shipments_realistic.yml']}
    assert {p.name: p.read_bytes() for p in old_dir.iterdir()} == old_bytes
    assert {p.name: p.read_bytes() for p in request_dir.iterdir()} == original
    assert {p.name: p.read_bytes() for p in active_dir.iterdir()} == active_bytes
    # Active đổi giữa các stage không đổi bộ đã chốt của lượt đang chạy.
    active_extensions(store, [], 'b' * 24)
    commands = []
    def run(cmd, **kwargs):
        commands.append(cmd)
        atomic_json(nr.context_path(store, second['run_id']), {'target': 'duckdb', 'stage': 'prepared'})
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(nr.subprocess, 'run', run)
    nr._stage(store, second, 'prepare', io.BytesIO())
    cmd = commands[0]
    assert [cmd[i + 1] for i, arg in enumerate(cmd) if arg == '--extension'] == second['mo_rong_chay']
    assert Path(cmd[cmd.index('--extension-dir') + 1]) == new_dir


def test_b6_core_active_without_extension_directory_starts(store, monkeypatch):
    r = shipment_request(store)
    active_extensions(store, [])
    path = nr.context_path(store, 'ui-active-a')
    context = json.loads(path.read_text(encoding='utf-8'))
    context.pop('extension_dir')
    atomic_json(path, context)
    monkeypatch.setattr(nr, 'has_dbt_model', lambda *a: True)
    monkeypatch.setattr(nr.subprocess, 'Popen', lambda *a, **kw: SimpleNamespace(pid=123))
    started = nr._start_locked(store, r['id'], r['revision'], 'de')
    assert started['mo_rong_chay'] == ['shipments_realistic']
    directory = store.folder(r['id']) / 'chay' / started['run_id'] / 'hop_dong'
    assert [p.name for p in directory.iterdir()] == ['shipments_realistic.yml']


def test_b4_rollback_uses_rolled_back_release_not_latest_contract(store):
    r = shipment_request(store)
    old = active_extensions(store, ['orders_enriched'])
    active_extensions(store, ['orders_enriched', 'shipments_realistic'], 'b' * 24)
    state = store.pipeline_state()
    state['active'] = 'a' * 24
    atomic_json(store.base / nr.PIPELINE_ROOT / 'state.json', {'payload': state})
    # Registry hiện hành khác bản active, không được đọc vào lượt chạy.
    registry = store.base / 'scripts/ingest/extensions'
    registry.mkdir(parents=True)
    (registry / 'orders_enriched.yml').write_text('broken', encoding='utf-8')
    _, copies = nr._extensions_for_run(store, r)
    assert copies['orders_enriched'] == (old / 'orders_enriched.yml').read_bytes()


@pytest.mark.parametrize('damage', ['context', 'contract', 'file', 'extension_dir', 'release_id', 'target', 'extensions'])
def test_b4_missing_active_inputs_stops_before_worker(store, monkeypatch, damage):
    r = shipment_request(store)
    directory = active_extensions(store, ['orders_enriched'])
    if damage == 'contract':
        (directory / 'orders_enriched.yml').unlink()
    elif damage == 'file':
        doc = extension_contract.load('orders_enriched', directory)
        (store.base / 'data' / doc['file']).unlink()
    else:
        path = nr.context_path(store, 'ui-active-a')
        if damage == 'context':
            path.write_text('{broken', encoding='utf-8')
        else:
            body = json.loads(path.read_text(encoding='utf-8'))
            if damage == 'extension_dir':
                body.pop('extension_dir')
            else:
                body[damage] = {'release_id': 'wrong', 'target': 'postgres', 'extensions': 'orders_enriched'}[damage]
            atomic_json(path, body)
    state = store.base / nr.PIPELINE_ROOT / 'state.json'
    before = state.read_bytes()
    monkeypatch.setattr(nr, 'has_dbt_model', lambda *a: True)
    monkeypatch.setattr(nr.subprocess, 'Popen', lambda *a, **kw: pytest.fail('Không được khởi động worker'))
    with pytest.raises(nr.WorkerStartError, match='Không giữ được'):
        nr._start_locked(store, r['id'], r['revision'], 'he_thong')
    assert state.read_bytes() == before
    failed = store.read(r['id'])
    assert failed['trang_thai'] == 'loi' and 'Không giữ được' in failed['thong_bao']
    failed['thong_bao'] = 'old error'
    store.save(failed)
    with pytest.raises(nr.WorkerStartError, match='Không giữ được'):
        nr._start_locked(store, r['id'], failed['revision'], 'he_thong')
    assert store.read(r['id'])['thong_bao'] != 'old error'


@pytest.mark.parametrize('names', [[], ['../orders'], ['orders_enriched', 'BAD'], [None]])
def test_b4_commands_validate_each_name(tmp_path, names):
    with pytest.raises(ValueError, match='Tên phần mở rộng'):
        nr.lenh('prepare', 'ui-demo-1', names, tmp_path)


def test_b4_summary_two_extensions(store):
    import duckdb
    r = shipment_request(store)
    rid = 'a' * 24
    path = store.base / nr.PIPELINE_ROOT / 'runs/ui-summary/dbt.duckdb'
    path.parent.mkdir(parents=True)
    with duckdb.connect(str(path)) as con:
        con.execute(f'create schema r_{rid}_marts')
        con.execute(f'create table r_{rid}_marts.dim_sales_employee as select 1')
        con.execute(f'create table r_{rid}_marts.dim_shipper as select 1 union all select 2')
        con.execute(f'create table r_{rid}_marts.fact_order as select 1 as sales_employee_sk, 1 as shipper_sk '
                    'union all select 1, null')
    context = {'stage': 'published', 'run_id': 'ui-summary', 'release_id': rid, 'duckdb_path': str(path),
               'extensions': ['orders_enriched', 'shipments_realistic']}
    atomic_json(store.folder(r['id']) / 'chay/context.json', context)
    result = nr.summary(store, r)
    assert [result[k] for k in ('dim_sales_employee', 'dim_shipper', 'orders_with_employee', 'orders_with_shipper')] == [1, 2, 2, 1]


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
    'da_duyet': {'dang_chay', 'loi'}, 'dang_chay': {'da_kiem', 'loi', 'da_cong_bo'}, 'loi': {'dang_chay', 'cho_duyet'},
    'da_kiem': {'da_cong_bo', 'loi'}, 'da_cong_bo': {'dang_chay', 'loi'}, 'cho_model_dbt': set(), 'tu_choi': set(), 'loi_de_xuat': set()}


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
    with pytest.raises(OSError, match='disk failure'):
        store.transition(r['id'], r['revision'], 'tu_choi', 'de', 'reason')
    assert path.read_bytes() == before


def test_visibility_and_roles(store, monkeypatch):
    r = pending(store)
    for role in roles.ROLES:
        assert roles.allowed(role, 'gui_du_lieu') == (role != 'khach')
        assert roles.allowed(role, 'duyet_du_lieu') == (role in ('ky_su', 'admin'))
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


def test_editor_type_choices_match_contract(store, identity, monkeypatch):
    pending(store)
    monkeypatch.setattr(ns, 'RequestStore', lambda: store)
    seen = []
    original = st.column_config.SelectboxColumn
    def capture(label, **options):
        if label == 'Kiểu':
            seen.append(tuple(options['options']))
        return original(label, **options)
    monkeypatch.setattr(st.column_config, 'SelectboxColumn', capture)
    at = AppTest.from_file(str(VIEWS / 'duyet_du_lieu.py')).run()
    assert not at.exception
    assert seen and all(options == extension_contract.VALID_TYPES for options in seen)


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
def test_pages_visible_without_flag(store, identity, monkeypatch, page):
    monkeypatch.setenv('RETAIL_APP_NHAP_DU_LIEU', '0')
    monkeypatch.setattr(ns, 'RequestStore', lambda: store)
    at = AppTest.from_file(str(VIEWS / f'{page}.py')).run()
    assert not at.exception
    assert not at.error, [item.value for item in at.error]


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


# Phiếu hiển thị sau rollback: đối chiếu chỉ đọc, không đổi trạng thái yêu cầu
A, B, C = 'a' * 24, 'b' * 24, 'c' * 24
GIU = 'Đã cập nhật dữ liệu'
KHONG_CON = 'Dữ liệu này đã từng được cập nhật nhưng hiện không nằm trong bản đang dùng.'


def kho(store, active, releases):
    """releases: {mã bản: danh sách nguồn mở rộng}."""
    root = store.base / nr.PIPELINE_ROOT
    for rid, names in releases.items():
        atomic_json(root / 'runs' / rid / 'context.json', {'release_id': rid, 'target': 'duckdb', 'extensions': names})
    atomic_json(root / 'state.json', {'version': 'test', 'payload': {
        'active': active, 'releases': {rid: {'run_id': rid, 'status': 'ready'} for rid in releases}}})


def da_cong_bo(store, name, rid):
    record = pending(store)
    record.update(trang_thai='da_cong_bo', ten_mo_rong=name)
    if rid:
        atomic_json(store.folder(record['id']) / 'chay/published.context.json', {'stage': 'published', 'release_id': rid})
    return store.save(record)


def trang_duyet(store, monkeypatch):
    monkeypatch.setattr(ns, 'RequestStore', lambda: store)
    at = AppTest.from_file(str(VIEWS / 'duyet_du_lieu.py')).run()
    assert not at.exception
    return [x.value for x in at.warning], [x.value for x in at.info]


def trang_gui(store, monkeypatch):
    monkeypatch.setattr(roles, 'current_role', lambda: 'quan_ly')
    monkeypatch.setattr(roles, 'logged_in_user', lambda: {'username': 'manager'})
    monkeypatch.setattr(ns, 'RequestStore', lambda: store)
    at = AppTest.from_file(str(VIEWS / 'gui_du_lieu.py')).run()
    assert not at.exception
    return [x.value for x in at.success], [x.value for x in at.info]


def test_notice_none_when_published_is_active(store, identity, monkeypatch):
    kho(store, A, {A: ['orders_enriched']})
    record = da_cong_bo(store, 'orders_enriched', A)
    assert nr.doi_chieu_ban(store, record) is None
    warnings, infos = trang_duyet(store, monkeypatch)
    assert not [w for w in warnings if 'bản đang xem' in w] and not [i for i in infos if 'bản đang xem' in i.lower()]
    assert GIU in trang_gui(store, monkeypatch)[0]


def test_notice_after_rollback_without_source(store, identity, monkeypatch):
    kho(store, A, {A: ['orders_enriched'], B: ['orders_enriched', 'shipments_realistic']})
    da_cong_bo(store, 'shipments_realistic', B)
    warnings, _ = trang_duyet(store, monkeypatch)
    assert f'Số dưới đây là của bản {B[:8]}, không phải bản đang xem ({A[:8]}). Nguồn này hiện không có trong bản đang xem.' in warnings
    success, infos = trang_gui(store, monkeypatch)
    assert GIU not in success and KHONG_CON in infos


def test_notice_when_newer_release_keeps_source(store, identity, monkeypatch):
    kho(store, B, {A: ['orders_enriched'], B: ['orders_enriched', 'shipments_realistic']})
    da_cong_bo(store, 'orders_enriched', A)
    assert f'Số dưới đây là của bản {A[:8]}. Bản đang xem là {B[:8]}, vẫn có nguồn này.' in trang_duyet(store, monkeypatch)[1]
    assert GIU in trang_gui(store, monkeypatch)[0]


def test_rollback_flips_two_requests(store, identity):
    kho(store, A, {A: ['orders_enriched'], B: ['orders_enriched', 'shipments_realistic']})
    first = da_cong_bo(store, 'orders_enriched', A)
    second = da_cong_bo(store, 'shipments_realistic', B)
    assert nr.doi_chieu_ban(store, first) is None
    assert nr.doi_chieu_ban(store, second)[0] == 'warning'
    kho(store, B, {A: ['orders_enriched'], B: ['orders_enriched', 'shipments_realistic']})
    assert nr.doi_chieu_ban(store, first)[0] == 'info'
    assert nr.doi_chieu_ban(store, second) is None


def test_rollback_to_own_older_release(store, identity):
    kho(store, A, {A: ['orders_enriched'], C: ['orders_enriched']})
    record = da_cong_bo(store, 'orders_enriched', C)
    kind, text = nr.doi_chieu_ban(store, record)
    assert kind == 'info' and C[:8] in text and A[:8] in text


def test_notice_without_active_or_published(store, identity):
    record = da_cong_bo(store, 'orders_enriched', A)
    assert nr.doi_chieu_ban(store, record) == ('warning', 'Kho chưa có bản đang xem.')
    assert nr.active_extensions(store) == (None, set())
    assert nr.nguon_dang_dung(store) == (None, set())
    bare = da_cong_bo(store, 'orders_enriched', None)
    kho(store, A, {A: ['orders_enriched']})
    assert nr.published_release(store, bare) is None
    assert nr.doi_chieu_ban(store, bare) is None


@pytest.mark.parametrize('damage', ['state', 'context', 'mismatch', 'target', 'published', 'no_release', 'release_kind', 'extensions'])
def test_notice_survives_damage(store, identity, monkeypatch, damage):
    kho(store, A, {A: ['orders_enriched']})
    record = da_cong_bo(store, 'orders_enriched', B)
    root = store.base / nr.PIPELINE_ROOT
    context = root / 'runs' / A / 'context.json'
    if damage == 'state':
        (root / 'state.json').write_text('{hong', encoding='utf-8')
    elif damage == 'context':
        context.write_text('{hong', encoding='utf-8')
    elif damage == 'mismatch':
        atomic_json(context, {'release_id': C, 'target': 'duckdb', 'extensions': []})
    elif damage == 'target':
        atomic_json(context, {'release_id': A, 'target': 'databricks', 'extensions': []})
    elif damage == 'extensions':
        atomic_json(context, {'release_id': A, 'target': 'duckdb', 'extensions': 'orders_enriched'})
    elif damage == 'published':
        (store.folder(record['id']) / 'chay/published.context.json').write_text('{hong', encoding='utf-8')
    elif damage == 'release_kind':
        atomic_json(store.folder(record['id']) / 'chay/published.context.json', {'stage': 'published', 'release_id': 123})
    else:
        atomic_json(store.folder(record['id']) / 'chay/published.context.json', {'stage': 'published'})
    assert nr.doi_chieu_ban(store, record) == ('warning', 'Chưa đối chiếu được với bản đang xem.')
    assert 'Chưa đối chiếu được với bản đang xem.' in trang_duyet(store, monkeypatch)[0]
    if damage not in ('published', 'no_release', 'release_kind'):
        assert 'Đã xử lý xong; đội dữ liệu đang kiểm tra trạng thái hiện tại.' in trang_gui(store, monkeypatch)[1]


@pytest.mark.parametrize('state', ['da_kiem', 'dang_chay', 'loi'])
def test_notice_only_for_published_state(store, identity, monkeypatch, state):
    kho(store, A, {A: []})
    record = da_cong_bo(store, 'orders_enriched', B)
    record.update(trang_thai=state, bat_dau='2026-11-05T00:00:00+00:00', run_id='ui-thu', stage='prepare')
    store.save(record)
    monkeypatch.setattr(nr, 'doi_chieu_ban', lambda *a: pytest.fail('Không đối chiếu ở trạng thái này'))
    monkeypatch.setattr(nr, 'nguon_dang_dung', lambda *a: pytest.fail('Không đọc khi chưa công bố'))
    trang_duyet(store, monkeypatch)
    trang_gui(store, monkeypatch)


def test_sender_reads_active_once_per_draw(store, identity, monkeypatch):
    kho(store, A, {A: ['orders_enriched']})
    da_cong_bo(store, 'orders_enriched', A)
    da_cong_bo(store, 'shipments_realistic', A)
    calls = []
    original = nr.nguon_dang_dung
    monkeypatch.setattr(nr, 'nguon_dang_dung', lambda s: calls.append(1) or original(s))
    trang_gui(store, monkeypatch)
    assert len(calls) == 1


def test_comparison_writes_nothing(store, identity):
    kho(store, A, {A: ['orders_enriched'], B: ['shipments_realistic']})
    record = da_cong_bo(store, 'shipments_realistic', B)
    def fingerprint():
        return {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in store.base.rglob('*') if p.is_file()}
    before = fingerprint()
    nr.active_extensions(store), nr.published_release(store, record), nr.doi_chieu_ban(store, record), nr.nguon_dang_dung(store)
    assert fingerprint() == before
    assert store.read(record['id'])['trang_thai'] == 'da_cong_bo' and store.read(record['id'])['revision'] == record['revision']
