"""Kiểm đường tự động và nạp bù bằng file nhỏ, worker/Neon giả."""
import csv
from contextlib import contextmanager
from copy import deepcopy
import io
import json
import os
import subprocess
from pathlib import Path
import sys
import threading
import time
import re
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'apps/retail_app'))
from ui import nhap_store as ns, nhap_runner as nr, roles
from scripts.ingest import auto_mapping, approval
from scripts.ingest.adapters import read_file
from scripts.ingest.contract_registry import ContractRegistry
from scripts.pipeline.state import Registry, atomic_json, writer_lock
from streamlit.testing.v1 import AppTest

REAL_KICK = nr._kick_locked


def upload(header, bonus='1'):
    body = ','.join(header) + '\n' + ','.join(bonus if name == 'bonus' else '1' for name in header) + '\n'
    stream = io.BytesIO(body.encode('utf-8'))
    stream.name = 'fresh.csv'
    stream.size = len(stream.getvalue())
    return stream


@pytest.fixture
def context(tmp_path, monkeypatch):
    repo = tmp_path / 'scripts/ingest/extensions'
    repo.mkdir(parents=True)
    (repo / 'orders_enriched.yml').write_bytes((ROOT / 'scripts/ingest/extensions/orders_enriched.yml').read_bytes())
    store = ns.RequestStore(tmp_path)
    registry = ContractRegistry(tmp_path)
    _, contract = registry.current('orders_enriched')
    events = []
    audit = SimpleNamespace(log=lambda *args: events.append(args))
    monkeypatch.setattr(roles, 'store', lambda: audit)
    monkeypatch.setattr(ns, 'actor', lambda action: ('de1' if action == 'duyet' else 'manager', audit))
    monkeypatch.setattr(approval, 'has_dbt_model', lambda *args: True)
    queued = []
    monkeypatch.setattr(nr, '_kick_locked', lambda store: None)
    original_add = store.queue_add

    def add(record):
        queued.append(record['id'])
        original_add(record)

    monkeypatch.setattr(store, 'queue_add', add)

    def fake_propose(path, data_dir):
        with Path(path).open(encoding='utf-8') as stream:
            header = next(csv.reader(stream))
        return {'nguon': {'de_xuat': 'orders'},
                'cot': [{'ten_trong_file': name, 'loai': 'thuoc_tinh_le', 'khong_ep_duoc': 0}
                        for name in header],
                'xung_dot_khoa': {'da_kiem': True, 'id_trung_khac_noi_dung': 0},
                'tham_chieu_thieu': [], 'file': {'ten': Path(path).name}}

    def fake_write(body, folder):
        folder.mkdir(parents=True)
        (folder / 'mapping_de_xuat.yml').write_text(yaml.safe_dump(body), encoding='utf-8')
        (folder / 'bao_cao_mapping.md').write_text('Giả lập', encoding='utf-8')

    monkeypatch.setattr(auto_mapping, 'propose', fake_propose)
    monkeypatch.setattr(auto_mapping, 'write_proposal', fake_write)
    return store, registry, contract, events, queued


def source(store, header, bonus, published_at=None):
    record = store.create(upload(header, bonus), '', 'manager')
    body = auto_mapping.propose(store.base / 'data/ui_nhap' / record['id'] / record['ten_file'], store.base / 'data')
    auto_mapping.write_proposal(body, store.folder(record['id']) / 'de_xuat')
    record['trang_thai'] = 'da_cong_bo' if published_at else 'da_duyet'
    record['duong'] = 'tu_dong'
    record['ten_mo_rong'] = 'orders_enriched'
    record['hop_dong'] = {'ten': 'orders_enriched', 'phien_ban': 1, 'sha256': 'a' * 64}
    record['cot_moi'] = ['bonus']
    if published_at:
        record['lich_su'].append({'luc': published_at, 'ai': 'he_thong', 'tu': 'da_kiem',
                                  'toi': 'da_cong_bo', 'ghi_chu': ''})
        release_id = record['sha256'][:24]
        atomic_json(store.folder(record['id']) / 'chay/published.context.json',
                    {'stage': 'published', 'release_id': release_id})
        atomic_json(store.base / nr.PIPELINE_ROOT / 'state.json',
                    {'version': 'test', 'payload': {'active': release_id, 'releases': {}}})
    return store.save(record)


def bonus_decision():
    return [{'ten': 'bonus', 'xu_ly': 'nap', 'kieu': 'integer', 'duoc_rong': False,
             'hien_thi': 'silver'}]


def test_auto_submit_no_de_and_manual_cannot_auto_approve(context):
    store, registry, doc, events, queued = context
    record = store.submit(upload(doc['header']), '')
    assert record['trang_thai'] == 'da_duyet' and record['duong'] == 'tu_dong'
    assert record['hop_dong']['phien_ban'] == 1 and queued == [record['id']]
    assert any(event[1] == 'nhap_tu_duyet' and event[0] == 'he_thong' for event in events)
    manual = store.create(upload(['alien']), '', 'manager')
    manual = store.transition(manual['id'], manual['revision'], 'cho_duyet', 'manager',
                              phan_loai={'ket_qua': 'can_nguoi'})
    with pytest.raises(ValueError, match='không thuộc đường tự động'):
        store.auto_approve(manual['id'], manual['revision'])


def test_upgrade_uses_latest_published_b_not_proposal_a(context):
    store, registry, doc, events, queued = context
    header = [*doc['header'], 'bonus']
    a = source(store, header, '1', '2026-11-01T00:00:00Z')
    b = source(store, header, '2', '2026-11-02T00:00:00Z')
    before_a = (store.folder(a['id']) / 'yeu_cau.json').read_bytes()
    before_b = (store.folder(b['id']) / 'yeu_cau.json').read_bytes()
    result = store.upgrade_contract(a['id'], bonus_decision())
    created = store.read(result['nap_bu'])
    assert result['phien_ban'] == 2 and created['nap_bu_tu'] == b['id']
    assert created['sha256'] == b['sha256'] != a['sha256']
    assert created['duong'] == 'tu_dong' and created['hop_dong']['phien_ban'] == 2
    assert queued == [created['id']]
    assert (store.folder(a['id']) / 'yeu_cau.json').read_bytes() == before_a
    assert (store.folder(b['id']) / 'yeu_cau.json').read_bytes() == before_b


def test_upgrade_without_new_columns_in_latest_file_keeps_v2(context):
    store, registry, doc, events, queued = context
    a = source(store, [*doc['header'], 'bonus'], '1', '2026-11-01T00:00:00Z')
    source(store, doc['header'], '2', '2026-11-02T00:00:00Z')
    count = len(list(store.requests.glob('*/yeu_cau.json')))
    result = store.upgrade_contract(a['id'], bonus_decision())
    assert result['nap_bu'] is None and 'thiếu bonus' in result['thong_bao']
    assert registry.current('orders_enriched')[0]['phien_ban'] == 2
    assert len(list(store.requests.glob('*/yeu_cau.json'))) == count
    assert registry.upgrade_notice('orders_enriched', 2) == result['thong_bao']


def test_upgrade_without_published_request_keeps_v2(context):
    store, registry, doc, events, queued = context
    a = source(store, [*doc['header'], 'bonus'], '1')
    result = store.upgrade_contract(a['id'], bonus_decision())
    assert result['nap_bu'] is None and 'không tìm được yêu cầu đã công bố' in result['thong_bao']
    assert registry.current('orders_enriched')[0]['phien_ban'] == 2


def test_reject_upgrade_suppresses_exact_column_set(context):
    store, registry, doc, events, queued = context
    a = source(store, [*doc['header'], 'bonus'], '1')
    assert a in store.pending_upgrades()
    store.reject_upgrade(a['id'], 'Chưa cần cột này')
    assert registry.rejected('orders_enriched', ['bonus'])
    rejected = json.loads((registry.folder('orders_enriched') / 'tu_choi.json').read_text(encoding='utf-8'))
    assert rejected[0]['ly_do'] == 'Chưa cần cột này' and rejected[0]['cot'] == ['bonus']
    assert a not in store.pending_upgrades()


def test_queue_runs_second_after_first_finishes(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    events = []
    monkeypatch.setattr(roles, 'store', lambda: SimpleNamespace(log=lambda *args: events.append(args)))
    monkeypatch.setattr(nr, 'has_dbt_model', lambda *args: True)
    monkeypatch.setattr(nr.subprocess, 'Popen', lambda *args, **kwargs: SimpleNamespace(pid=os.getpid()))
    records = []
    for index in range(2):
        record = store.create(upload(['order_id'], str(index)), '', 'manager')
        record = store.transition(record['id'], record['revision'], 'cho_duyet', 'manager')
        record = store.transition(record['id'], record['revision'], 'da_duyet', 'he_thong',
                                  duong='tu_dong', ten_mo_rong='orders_enriched',
                                  hop_dong={'ten': 'orders_enriched', 'phien_ban': 1, 'sha256': 'a' * 64})
        records.append(record)
        nr.enqueue(store, record['id'])
    assert store.read(records[0]['id'])['trang_thai'] == 'dang_chay'
    assert nr.queue_position(store, records[1]['id']) == 1
    monkeypatch.setattr(nr, '_stage', lambda store, record, stage, output:
                        {'stage': 'published' if stage == 'publish' else stage, 'target': 'duckdb'})
    first = store.read(records[0]['id'])
    result = nr.run_worker(store, first['id'], first['run_id'])
    assert result['trang_thai'] == 'da_cong_bo'
    assert store.read(records[1]['id'])['trang_thai'] == 'dang_chay'
    assert not list((store.root / 'hang_doi').glob('*.json'))
    assert any(event[1] == 'nhap_cong_bo' and event[0] == 'he_thong' for event in events)


def test_dead_worker_recovery_starts_next_queued(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    monkeypatch.setattr(roles, 'store', lambda: SimpleNamespace(log=lambda *args: None))
    monkeypatch.setattr(nr, 'has_dbt_model', lambda *args: True)
    monkeypatch.setattr(nr.subprocess, 'Popen', lambda *args, **kwargs: SimpleNamespace(pid=999999999))
    monkeypatch.setattr(nr, '_pid_alive', lambda pid: True)
    items = []
    for _ in range(2):
        record = store.create(upload(['order_id']), '', 'manager')
        record = store.transition(record['id'], record['revision'], 'cho_duyet', 'manager')
        record = store.transition(record['id'], record['revision'], 'da_duyet', 'he_thong',
                                  duong='tu_dong', ten_mo_rong='orders_enriched',
                                  hop_dong={'ten': 'orders_enriched', 'phien_ban': 1, 'sha256': 'a' * 64})
        items.append(record)
        nr.enqueue(store, record['id'])
    monkeypatch.setattr(nr, '_pid_alive', lambda pid: False)
    nr.recover_queue(store)
    assert store.read(items[0]['id'])['trang_thai'] == 'loi'
    assert store.read(items[1]['id'])['trang_thai'] == 'dang_chay'
    assert not list((store.root / 'hang_doi').glob('*.json'))


def test_retry_review_switches_auto_request_to_manual(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    events = []
    monkeypatch.setattr(ns, 'actor', lambda action: ('de1', SimpleNamespace(log=lambda *args: events.append(args))))
    record = store.create(upload(['order_id']), '', 'manager')
    record['trang_thai'] = 'loi'
    record['duong'] = 'tu_dong'
    store.save(record)
    with pytest.raises(ValueError, match='lý do'):
        store.retry_review(record['id'], record['revision'], ' ')
    result = store.retry_review(record['id'], record['revision'], 'Sửa kiểu')
    assert result['trang_thai'] == 'cho_duyet' and result['duong'] == 'tay'
    assert events[0][1] == 'nhap_duyet_lai'


def test_rollback_command_local_only():
    run_id = 'ui-rollback-20261102T120000000000Z'
    command = nr.rollback_command('a' * 24, run_id)
    assert command == nr.rollback_command('a' * 24, run_id)
    assert command[command.index('--target') + 1] == 'duckdb'
    assert command[command.index('--root') + 1] == 'warehouse/pipeline/ui-nhap'
    assert 'databricks' not in command and 'warehouse/pipeline/docker' not in command


def test_rollback_generates_utc_run_id_before_building_command(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    monkeypatch.setattr(nr, 'actor', lambda action: ('admin', SimpleNamespace(log=lambda *args: None)))
    captured = []
    monkeypatch.setattr(nr.subprocess, 'run', lambda cmd, **kwargs:
                        captured.append(cmd) or SimpleNamespace(returncode=0))
    assert nr.rollback(store, 'a' * 24).returncode == 0
    run_id = captured[0][captured[0].index('--run-id') + 1]
    assert re.fullmatch(r'ui-rollback-\d{8}T\d{12}Z', run_id)
    assert captured[0] == nr.rollback_command('a' * 24, run_id)


def test_cloud_import_and_pages_without_duckdb_or_yaml(tmp_path):
    script = r'''
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, str(Path(sys.argv[1]) / 'apps/retail_app'))
sys.modules['duckdb'] = None
sys.modules['yaml'] = None
from ui import roles, nhap_store, nhap_runner
from streamlit.testing.v1 import AppTest
nhap_store.RequestStore = lambda *a, **k: (_ for _ in ()).throw(AssertionError('Không được mở kho dữ liệu'))
views = Path(sys.argv[1]) / 'apps/retail_app/views'
for page, role in [('gui_du_lieu', 'quan_ly'), ('duyet_du_lieu', 'ky_su'), ('duyet_du_lieu', 'admin')]:
    roles.current_role = lambda role=role: role
    roles.logged_in_user = lambda: {'username': 'test'}
    at = AppTest.from_file(str(views / (page + '.py'))).run()
    assert not at.exception, at.exception
    assert any('bản web đang được phát triển' in item.value for item in at.info)
    assert not at.button and not at.get('file_uploader')
roles.current_role = lambda: 'quan_ly'
at = AppTest.from_file(str(views / 'duyet_du_lieu.py')).run()
assert not at.exception and any('không có quyền' in item.value for item in at.error)
'''
    result = subprocess.run([sys.executable, '-B', '-c', script, str(ROOT)],
                            cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert not list(tmp_path.iterdir())


def test_missing_data_shows_unavailable(tmp_path):
    assert ns.nhap_kha_dung(tmp_path) is False


@pytest.mark.parametrize('page,role', [('gui_du_lieu', 'quan_ly'), ('duyet_du_lieu', 'ky_su')])
def test_pages_without_data_only_show_notice(tmp_path, monkeypatch, page, role):
    assert ns.nhap_kha_dung(tmp_path) is False
    availability = ns.nhap_kha_dung
    monkeypatch.setattr(ns, 'nhap_kha_dung', lambda: availability(tmp_path))
    monkeypatch.setattr(ns, 'RequestStore', lambda: pytest.fail('Không được mở kho khi thiếu data'))
    monkeypatch.setattr(roles, 'current_role', lambda: role)
    at = AppTest.from_file(str(ROOT / 'apps/retail_app/views' / f'{page}.py')).run()
    assert not at.exception
    assert any('bản web đang được phát triển' in item.value for item in at.info)
    assert not at.button and not at.get('file_uploader')


def test_integer_suggestion_respects_leading_zero_and_pii(tmp_path):
    path = tmp_path / 'values.csv'
    path.write_text('years_experience,zip,phone,sales_employee_id,comment\n3,01234,0912345678,EMP01,note\n10,12345,0987654321,EMP02,note\n', encoding='utf-8')
    with read_file(path) as data:
        years = auto_mapping.column_profile(data, 'years_experience')
        zip_code = auto_mapping.column_profile(data, 'zip')
        phone = auto_mapping.column_profile(data, 'phone')
        employee = auto_mapping.column_profile(data, 'sales_employee_id')
        comment = auto_mapping.column_profile(data, 'comment')
    assert years['kieu_goi_y'] == 'integer'
    assert zip_code['kieu_goi_y'] == phone['kieu_goi_y'] == 'string'
    assert employee['kieu_goi_y'] == comment['kieu_goi_y'] == 'string'


def test_worker_journal_fallback_and_sync(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    monkeypatch.setattr(roles, 'store', lambda: None)
    store.log_event('he_thong', 'nhap_chay', {'id': 'test'})
    assert store.sync_events() == 1
    path = store.root / 'nhat_ky_cho.jsonl'
    assert json.loads(path.read_text(encoding='utf-8'))['ai'] == 'he_thong'
    events = []
    monkeypatch.setattr(roles, 'store', lambda: SimpleNamespace(log=lambda *args: events.append(args)))
    assert store.sync_events() == 0
    assert not path.exists() and events == [('he_thong', 'nhap_chay', {'id': 'test'})]


def test_publish_decision_requires_validated_and_published():
    with pytest.raises(ValueError):
        nr.publish_decision({'trang_thai': 'da_duyet'}, {'stage': 'published'})
    with pytest.raises(ValueError):
        nr.publish_decision({'trang_thai': 'da_kiem'}, {'stage': 'validated'})
    assert nr.publish_decision({'trang_thai': 'da_kiem'}, {'stage': 'published'})['trang_thai'] == 'da_cong_bo'


def test_rollback_denies_non_admin(tmp_path, monkeypatch):
    monkeypatch.setattr(roles, 'current_role', lambda: 'ky_su')
    with pytest.raises(PermissionError):
        nr.rollback(ns.RequestStore(tmp_path), 'a' * 24)


def test_auto_approve_records_system_identity(context):
    store, _, doc, events, _ = context
    record = store.submit(upload(doc['header']), '')
    assert record['nguoi_gui'] == 'manager'
    assert record['lich_su'][-1]['ai'] == 'he_thong'
    assert record['lich_su'][-1]['toi'] == 'da_duyet'
    saved = yaml.safe_load((store.folder(record['id']) / 'hop_dong/orders_enriched.yml').read_text(encoding='utf-8'))
    assert saved['duyet_boi'].startswith('he_thong (hợp đồng orders_enriched v1, sha256 ')


def waiting_auto(store, doc):
    record = source(store, doc['header'], '1')
    record.update(trang_thai='cho_duyet', phan_loai={'ket_qua': 'tu_dong', 'ten': 'orders_enriched',
                                                   'phien_ban': 1, 'cot_moi': []})
    return store.save(record)


def test_auto_approve_rejects_changed_contract_version(context):
    store, registry, doc, _, _ = context
    record = waiting_auto(store, doc)
    registry.write('orders_enriched', doc, 'de1', 'nang_hop_dong:other', expected=1)
    with pytest.raises(ValueError, match='đã thay đổi'):
        store.auto_approve(record['id'], record['revision'])
    assert store.read(record['id'])['trang_thai'] == 'cho_duyet'
    assert not list((store.folder(record['id']) / 'hop_dong').glob('*.yml'))


def test_auto_approve_validates_before_saving(context, monkeypatch):
    from scripts.ingest import tu_dong
    store, _, doc, _, _ = context
    record = waiting_auto(store, doc)
    build = tu_dong.hop_dong_cua_luot

    def invalid(*args):
        result = build(*args)
        result['nguong_cach_ly'] = 2
        return result

    monkeypatch.setattr(tu_dong, 'hop_dong_cua_luot', invalid)
    with pytest.raises(ValueError, match='nguong_cach_ly'):
        store.auto_approve(record['id'], record['revision'])
    assert store.read(record['id'])['trang_thai'] == 'cho_duyet'
    assert not list((store.folder(record['id']) / 'hop_dong').glob('*.yml'))


def test_manual_review_clears_auto_metadata_and_cannot_auto_approve(context):
    store, registry, doc, _, _ = context
    record = waiting_auto(store, doc)
    record['trang_thai'] = 'loi'
    store.save(record)
    reviewed = store.retry_review(record['id'], record['revision'], 'Sửa quyết định')
    with pytest.raises(ValueError, match='không thuộc đường tự động'):
        store.auto_approve(record['id'], reviewed['revision'])
    result = store.approve(record['id'], reviewed['revision'], doc, 'orders_enriched')
    assert result['duong'] == 'tay' and result['trang_thai'] == 'da_duyet'
    assert 'hop_dong' not in result and 'cot_moi' not in result


@pytest.mark.parametrize('name', ['orders_enriched', 'new_extension'])
def test_manual_approval_seeds_once_without_changing_existing_contract(context, name):
    store, registry, doc, _, _ = context
    meta_before, doc_before = registry.current('orders_enriched')
    record = waiting_auto(store, doc)
    decisions = deepcopy(doc)
    decisions['nguong_cach_ly'] = 0.02
    result = store.approve(record['id'], record['revision'], decisions, name)
    meta, saved = registry.current(name)
    assert result['trang_thai'] == 'da_duyet' and meta['phien_ban'] == 1
    assert result['duong'] == 'tay'
    if name == 'orders_enriched':
        assert (meta, saved) == (meta_before, doc_before)
    else:
        assert meta['nguon_goc'] == 'yeu_cau:' + record['id']
        assert saved['nguong_cach_ly'] == 0.02 and meta['duyet_boi'] == 'de1'


def test_upgrade_after_rollback_uses_active_a_not_latest_b(context):
    store, _, doc, _, _ = context
    a = source(store, [*doc['header'], 'bonus'], '1', '2026-11-01T00:00:00Z')
    source(store, [*doc['header'], 'bonus'], '2', '2026-11-02T00:00:00Z')
    atomic_json(store.base / nr.PIPELINE_ROOT / 'state.json',
                {'version': 'rollback', 'payload': {'active': a['sha256'][:24], 'releases': {}}})
    result = store.upgrade_contract(a['id'], bonus_decision())
    created = store.read(result['nap_bu'])
    assert created['nap_bu_tu'] == a['id'] and created['sha256'] == a['sha256']


@pytest.mark.parametrize('busy', ['queue', 'worker', 'writer'])
def test_upgrade_refuses_busy_before_writing_version(context, busy):
    store, registry, doc, _, _ = context
    record = source(store, [*doc['header'], 'bonus'], '1', '2026-11-01T00:00:00Z')
    before = (registry.folder('orders_enriched') / 'hien_hanh.json').read_bytes()
    if busy == 'queue':
        newer = source(store, [*doc['header'], 'bonus'], '9')
        store.queue_add(newer)
    path = store.root / 'worker' if busy == 'worker' else store.base / nr.PIPELINE_ROOT
    # Ca queue dùng khóa riêng vô hại để giữ chung cấu trúc kiểm thử.
    if busy == 'queue':
        path = store.root / 'test_only'
    with writer_lock(path):
        with pytest.raises(ValueError, match='Chờ lượt đang chạy xong rồi duyệt'):
            store.upgrade_contract(record['id'], bonus_decision())
    assert (registry.folder('orders_enriched') / 'hien_hanh.json').read_bytes() == before
    assert not (registry.folder('orders_enriched') / 'v2.yml').exists()


def test_upgrade_rejects_missing_mart_column_before_writing(context):
    store, registry, doc, _, _ = context
    record = source(store, [*doc['header'], 'bonus'], '1')
    decisions = bonus_decision()
    decisions[0]['hien_thi'] = 'mart'
    with pytest.raises(ValueError, match='bonus'):
        store.upgrade_contract(record['id'], decisions)
    assert registry.current('orders_enriched')[0]['phien_ban'] == 1
    assert not (registry.folder('orders_enriched') / 'v2.yml').exists()


@pytest.mark.parametrize('names', [[], ['other'], ['bonus', 'bonus']])
def test_upgrade_requires_exact_new_columns(context, names):
    store, registry, doc, _, _ = context
    record = source(store, [*doc['header'], 'bonus'], '1')
    decisions = [{**bonus_decision()[0], 'ten': name} for name in names]
    with pytest.raises(ValueError, match='đúng các cột mới'):
        store.upgrade_contract(record['id'], decisions)
    assert registry.current('orders_enriched')[0]['phien_ban'] == 1


def test_upgrade_refuses_stale_version(context):
    store, registry, doc, _, _ = context
    record = source(store, [*doc['header'], 'bonus'], '1')
    registry.write('orders_enriched', doc, 'de1', 'nang_hop_dong:other', expected=1)
    with pytest.raises(ValueError, match='đã đổi'):
        store.upgrade_contract(record['id'], bonus_decision())
    assert registry.current('orders_enriched')[0]['phien_ban'] == 2
    assert not (registry.folder('orders_enriched') / 'v3.yml').exists()


def test_backfill_checks_source_hash_before_copy(context, monkeypatch):
    store, registry, doc, _, _ = context
    record = source(store, [*doc['header'], 'bonus'], '1', '2026-11-01T00:00:00Z')
    path = store.base / 'data/ui_nhap' / record['id'] / record['ten_file']
    path.write_bytes(upload([*doc['header'], 'bonus'], '9').getvalue())
    calls = []
    create = store.create

    def track(*args):
        calls.append(args)
        return create(*args)

    monkeypatch.setattr(store, 'create', track)
    with pytest.raises(ValueError, match='sha256'):
        store.upgrade_contract(record['id'], bonus_decision())
    assert calls == []  # Kiểm trước sao chép không tương đương kiểm sau sao chép.
    assert registry.current('orders_enriched')[0]['phien_ban'] == 1
    assert not (registry.folder('orders_enriched') / 'v2.yml').exists()


def test_backfill_checks_copied_hash_after_source_changes(context, monkeypatch):
    store, _, doc, _, queued = context
    record = source(store, [*doc['header'], 'bonus'], '1', '2026-11-01T00:00:00Z')
    create = store.create

    def changed_during_copy(uploaded, description, username):
        return create(upload([*doc['header'], 'bonus'], '9'), description, username)

    monkeypatch.setattr(store, 'create', changed_during_copy)
    result = store.upgrade_contract(record['id'], bonus_decision())
    assert result['phien_ban'] == 2 and result['nap_bu'] is None
    assert 'File nạp bù không khớp sha256' in result['thong_bao']
    assert queued == []


@contextmanager
def held_briefly(path, seconds=0.3):
    ready = threading.Event()
    failures = []

    def hold():
        try:
            with writer_lock(path):
                ready.set()
                time.sleep(seconds)
        except BaseException as error:
            failures.append(error)
            ready.set()

    thread = threading.Thread(target=hold)
    thread.start()
    assert ready.wait(5)
    try:
        assert not failures
        yield
    finally:
        thread.join(5)
        assert not thread.is_alive() and not failures


@pytest.mark.parametrize('timeout', [False, True])
def test_submit_keeps_queue_item_when_dispatch_busy(context, timeout, monkeypatch):
    store, _, doc, _, _ = context
    kicks = []
    monkeypatch.setattr(nr, '_kick_locked', lambda store: kicks.append(True))
    hold = writer_lock(store.root / 'dispatch') if timeout else held_briefly(store.root / 'dispatch')
    with hold:
        record = store.submit(upload(doc['header']), '')
        assert record['trang_thai'] == 'da_duyet'
        assert nr.queue_position(store, record['id']) == 1
    assert len(store.queue_files()) == 1
    assert len(kicks) == (0 if timeout else 1)
    nr.recover_queue(store)
    assert len(kicks) == (1 if timeout else 2)


def runner_setup(store, monkeypatch):
    events = []
    audit = SimpleNamespace(log=lambda *args: events.append(args))
    monkeypatch.setattr(roles, 'store', lambda: audit)
    monkeypatch.setattr(nr, 'actor', lambda action: ('de1', audit))
    monkeypatch.setattr(nr, 'has_dbt_model', lambda *args: True)
    monkeypatch.setattr(nr.subprocess, 'Popen', lambda *args, **kwargs: SimpleNamespace(pid=os.getpid()))
    monkeypatch.setattr(nr, '_stage', lambda store, record, stage, output:
                        {'stage': 'published' if stage == 'publish' else stage, 'target': 'duckdb'})
    return events


@pytest.mark.parametrize('initial', ['da_cong_bo', 'loi'])
def test_manual_rerun_of_auto_request_waits_for_admin(tmp_path, monkeypatch, initial):
    store = ns.RequestStore(tmp_path)
    events = runner_setup(store, monkeypatch)
    record = store.create(upload(['order_id']), '', 'manager')
    record.update(trang_thai=initial, duong='tu_dong', ten_mo_rong='orders_enriched')
    store.save(record)
    running = nr.start(store, record['id'], record['revision'])
    result = nr.run_worker(store, record['id'], running['run_id'])
    assert result['trang_thai'] == 'da_kiem' and result['nguoi_chay'] == 'de1'
    assert not any(event[1] == 'nhap_cong_bo' for event in events)


def queued_record(store, state='da_duyet', route='tu_dong'):
    record = store.create(upload(['order_id']), '', 'manager')
    record.update(trang_thai=state, duong=route, ten_mo_rong='orders_enriched',
                  hop_dong={'ten': 'orders_enriched', 'phien_ban': 1})
    return store.save(record)


def test_enqueue_refuses_manual_request(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    runner_setup(store, monkeypatch)
    record = queued_record(store, route='tay')
    with pytest.raises(ValueError, match='Chỉ yêu cầu tự động'):
        nr.enqueue(store, record['id'])
    assert store.queue_files() == [] and store.read(record['id'])['trang_thai'] == 'da_duyet'


@pytest.mark.parametrize('operation', ['start', 'rollback'])
def test_manual_operations_cannot_pass_waiting_queue(tmp_path, monkeypatch, operation):
    store = ns.RequestStore(tmp_path)
    runner_setup(store, monkeypatch)
    record = queued_record(store)
    store.queue_add(record)
    monkeypatch.setattr(nr.subprocess, 'run', lambda *a, **kw: pytest.fail('Không được chạy CLI'))
    with pytest.raises(ValueError, match='hàng đợi'):
        if operation == 'start':
            nr.start(store, record['id'], record['revision'])
        else:
            nr.rollback(store, 'a' * 24)
    assert store.read(record['id'])['trang_thai'] == 'da_duyet'


def test_queue_discards_ineligible_item_and_runs_fifo(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    events = runner_setup(store, monkeypatch)
    expired = queued_record(store, state='loi')
    first = queued_record(store)
    second = queued_record(store)
    for record in (expired, first, second):
        store.queue_add(record)
    started = nr.recover_queue(store)
    assert started['id'] == first['id'] and started['nguoi_chay'] == 'he_thong'
    assert store.read(expired['id'])['trang_thai'] == 'loi'
    assert nr.queue_position(store, second['id']) == 1
    assert any(event[2].get('id') == expired['id'] and 'Bỏ mục' in event[2].get('ly_do', '') for event in events)


def test_worker_waits_for_dispatch_at_finish_and_starts_next(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    runner_setup(store, monkeypatch)
    first, second = queued_record(store), queued_record(store)
    nr.enqueue(store, first['id'])
    nr.enqueue(store, second['id'])
    running = store.read(first['id'])
    execute = nr._run_worker_locked
    held = []

    def finish(*args):
        result = execute(*args)
        hold = held_briefly(store.root / 'dispatch')
        hold.__enter__()
        held.append(hold)
        return result

    monkeypatch.setattr(nr, '_run_worker_locked', finish)
    try:
        result = nr.run_worker(store, first['id'], running['run_id'])
    finally:
        for hold in held:
            hold.__exit__(None, None, None)
    assert result['trang_thai'] == 'da_cong_bo'
    assert store.read(second['id'])['trang_thai'] == 'dang_chay'


def test_auto_publish_failure_records_error(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    runner_setup(store, monkeypatch)
    record = queued_record(store)
    nr.enqueue(store, record['id'])
    running = store.read(record['id'])

    def stage(store, record, stage, output):
        if stage == 'publish':
            raise RuntimeError('publish giả thất bại')
        return {'stage': stage, 'target': 'duckdb'}

    monkeypatch.setattr(nr, '_stage', stage)
    result = nr.run_worker(store, record['id'], running['run_id'])
    assert result['trang_thai'] == 'loi' and 'publish giả thất bại' in result['thong_bao']
    assert store.read(record['id'])['trang_thai'] == 'loi'
    assert not (store.root / 'active.json').exists()


def test_journal_append_retries_busy_lock(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    monkeypatch.setattr(roles, 'store', lambda: None)
    with held_briefly(store.root / 'nhat_ky_cho'):
        store.log_event('he_thong', 'nhap_cong_bo', {'id': 'one'})
    assert store.sync_events() == 1


def test_sync_releases_append_lock_and_keeps_new_rows_and_failures(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    monkeypatch.setattr(roles, 'store', lambda: None)
    for name in ('one', 'two'):
        store.log_event('he_thong', 'nhap_chay', {'id': name})
    events = []

    def log(username, event, detail):
        # Mô phỏng Neon chậm: worker phải lấy được khóa ghi trong lúc gửi mạng.
        with writer_lock(store.root / 'nhat_ky_cho'):
            pass
        if detail['id'] == 'two':
            raise OSError('Neon giả mất kết nối')
        events.append(detail['id'])
        with monkeypatch.context() as patch:
            patch.setattr(roles, 'store', lambda: None)
            store.log_event('he_thong', 'nhap_cong_bo', {'id': 'three'})

    monkeypatch.setattr(roles, 'store', lambda: SimpleNamespace(log=log))
    with held_briefly(store.root / 'nhat_ky_cho'):
        assert store.sync_events() == 2
    rows = [json.loads(line) for line in (store.root / 'nhat_ky_cho.jsonl').read_text(encoding='utf-8').splitlines()]
    assert events == ['one'] and [row['detail']['id'] for row in rows] == ['two', 'three']


def test_queue_position_ignores_disappeared_files(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    a, b = queued_record(store), queued_record(store)
    store.queue_add(a)
    store.queue_add(b)
    first = store.queue_files()[0]
    read = Path.read_text

    def removed(path, *args, **kwargs):
        if path == first:
            path.unlink()
        return read(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', removed)
    assert nr.queue_position(store, b['id']) == 1


def test_rollback_real_cli_changes_active_in_temporary_duckdb(tmp_path):
    import duckdb
    store = ns.RequestStore(tmp_path)
    root = tmp_path / nr.PIPELINE_ROOT
    registry = Registry(root)
    registry.initialize()
    config = yaml.safe_load((ROOT / 'retail_dbt/dbt_project.yml').read_text(encoding='utf-8'))['vars']
    relations = set(config['app_read_relations'] + config['ai_readonly_relations'])
    for release in ('a' * 24, 'b' * 24):
        schema = 'r_' + release + '_reporting'
        artifact = release + '.duckdb'
        with duckdb.connect(str(root / artifact)) as con:
            con.execute(f'create schema {schema}')
            for relation in relations:
                con.execute(f'create table {schema}.{relation.split(".")[1]} (id integer)')
        registry.register({'release_id': release, 'status': 'ready', 'schema': schema, 'artifact_path': artifact})
    registry.publish('b' * 24, None)
    assert nr.rollback_options(store) == ['a' * 24]
    command = nr.rollback_command('a' * 24, 'ui-rollback-20261102T120000000000Z')
    assert re.fullmatch(r'ui-rollback-[a-zA-Z0-9_-]+', command[command.index('--run-id') + 1])
    assert len(command[command.index('--run-id') + 1]) <= 100
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, encoding='utf-8', timeout=60,
                            env={**os.environ, 'PYTHONPATH': str(ROOT), 'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1'})
    assert result.returncode == 0, result.stderr
    assert registry.read()['payload']['active'] == 'a' * 24
    assert nr.rollback_options(store) == ['b' * 24]
    history = [json.loads(line) for line in (root / 'history.jsonl').read_text(encoding='utf-8').splitlines()]
    assert history[-1]['stage'] == 'rollback' and history[-1]['result'] == 'dat'


def test_upgrade_missing_current_contract_requires_review(context, monkeypatch):
    store, _, doc, _, _ = context
    record = source(store, [*doc['header'], 'bonus'], '1')
    monkeypatch.setattr(ContractRegistry, 'current', lambda self, name: None)
    with pytest.raises(ValueError, match='đã đổi'):
        store.upgrade_contract(record['id'], bonus_decision())


def test_submit_missing_column_only_reports_missing_column(context):
    store, _, doc, _, queued = context
    record = store.submit(upload([name for name in doc['header'] if name != 'comment']), '')
    assert record['trang_thai'] == 'cho_duyet'
    assert [r['ma'] for r in record['ly_do']] == ['thieu_cot']
    assert 'comment' in record['ly_do'][0]['nghiep_vu'] and not queued


def test_review_handles_journal_oserror_and_rollback_confirmation(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    store.create(upload(['order_id']), '', 'manager')
    monkeypatch.setattr(ns, 'RequestStore', lambda: store)
    monkeypatch.setattr(ns, 'nhap_kha_dung', lambda: True)
    monkeypatch.setattr(roles, 'current_role', lambda: 'admin')
    monkeypatch.setattr(roles, 'logged_in_user', lambda: {'username': 'admin'})
    monkeypatch.setattr(nr, 'recover_queue', lambda store, **kwargs: None)
    monkeypatch.setattr(store, 'sync_events', lambda: (_ for _ in ()).throw(PermissionError('Nhật ký đang bận')))
    monkeypatch.setattr(nr, 'rollback_options', lambda store: ['a' * 24])
    calls = []
    monkeypatch.setattr(nr, 'rollback', lambda store, release:
                        calls.append(release) or SimpleNamespace(returncode=0))
    at = AppTest.from_file(str(ROOT / 'apps/retail_app/views/duyet_du_lieu.py')).run()
    assert not at.exception
    assert any('Nhật ký đang bận' in row.value for row in at.warning)
    button = next(button for button in at.button if button.label == 'Rollback')
    assert not button.disabled
    button.click().run()
    assert not calls and any('Cần xác nhận' in row.value for row in at.warning)
    at.checkbox[0].check()
    next(button for button in at.button if button.label == 'Rollback').click().run()
    assert not at.exception and calls == ['a' * 24]


@pytest.mark.parametrize('column', ['source', 'raw', 'id', 'select', 'integer', 'marital_status'])
def test_upgrade_checks_real_mart_outputs(context, column):
    import shutil
    store, registry, doc, _, _ = context
    shutil.copytree(ROOT / 'retail_dbt/models', store.base / 'retail_dbt/models')
    record = source(store, [*doc['header'], column], '1')
    record['cot_moi'] = [column]
    store.save(record)
    decisions = [{**bonus_decision()[0], 'ten': column, 'hien_thi': 'mart'}]
    with pytest.raises(ValueError, match=column):
        store.upgrade_contract(record['id'], decisions)
    assert registry.current('orders_enriched')[0]['phien_ban'] == 1


def test_upgrade_audit_failure_keeps_old_version(context, monkeypatch):
    store, registry, doc, _, _ = context
    record = source(store, [*doc['header'], 'bonus'], '1')
    audit = SimpleNamespace(log=lambda *args: (_ for _ in ()).throw(RuntimeError('Nhật ký lỗi')))
    monkeypatch.setattr(ns, 'actor', lambda action: ('de1', audit))
    with pytest.raises(RuntimeError, match='Nhật ký lỗi'):
        store.upgrade_contract(record['id'], bonus_decision())
    assert registry.current('orders_enriched')[0]['phien_ban'] == 1
    assert not (registry.folder('orders_enriched') / 'v2.yml').exists()


def test_upgrade_backfill_failure_reports_committed_version(context, monkeypatch):
    store, registry, doc, events, queued = context
    record = source(store, [*doc['header'], 'bonus'], '1', '2026-11-01T00:00:00Z')

    def failed_copy(*args):
        assert registry.current('orders_enriched')[0]['phien_ban'] == 2
        assert any(event[1] == 'nhap_nang_hop_dong' for event in events)
        raise OSError('Không sao chép được file')

    monkeypatch.setattr(store, 'create', failed_copy)
    result = store.upgrade_contract(record['id'], bonus_decision())
    assert result['nap_bu'] is None and not queued
    assert 'Cột mới có hiệu lực từ lần gửi sau' in result['thong_bao']
    assert 'Không sao chép được file' in result['thong_bao']
    assert registry.upgrade_notice('orders_enriched', 2) == result['thong_bao']


def test_upgrade_holds_dispatch_through_checks_write_and_enqueue(context, monkeypatch):
    store, registry, doc, _, queued = context
    record = source(store, [*doc['header'], 'bonus'], '1', '2026-11-01T00:00:00Z')
    checkpoints = []

    def assert_locked(label):
        with pytest.raises(OSError):
            with writer_lock(store.root / 'dispatch'):
                pass
        checkpoints.append(label)

    find = store._active_published
    write = ContractRegistry.write
    enqueue = nr._enqueue_locked

    def find_source(*args):
        assert_locked('source')
        return find(*args)

    def write_version(*args, **kwargs):
        assert_locked('write')
        return write(*args, **kwargs)

    def enqueue_backfill(*args, **kwargs):
        assert_locked('enqueue')
        return enqueue(*args, **kwargs)

    monkeypatch.setattr(store, '_active_published', find_source)
    monkeypatch.setattr(ContractRegistry, 'write', write_version)
    monkeypatch.setattr(nr, '_enqueue_locked', enqueue_backfill)
    result = store.upgrade_contract(record['id'], bonus_decision())
    assert checkpoints == ['source', 'write', 'enqueue'] and queued == [result['nap_bu']]


def test_slow_upgrade_does_not_enqueue_old_file_after_new_arrival(context, monkeypatch):
    store, registry, doc, _, queued = context
    record = source(store, [*doc['header'], 'bonus'], '1', '2026-11-01T00:00:00Z')
    newer = source(store, [*doc['header'], 'bonus'], '9')
    propose = auto_mapping.propose
    failures = []

    def arrive():
        try:
            nr.enqueue(store, newer['id'])
        except BaseException as error:
            failures.append(error)

    def slow_propose(*args):
        # Khóa do nâng hợp đồng giữ; yêu cầu mới phải hết đủ 100 lần chờ mới được ghi.
        thread = threading.Thread(target=arrive)
        started = time.monotonic()
        thread.start()
        thread.join(15)
        assert not thread.is_alive() and not failures
        assert time.monotonic() - started >= 9
        return propose(*args)

    monkeypatch.setattr(auto_mapping, 'propose', slow_propose)
    result = store.upgrade_contract(record['id'], bonus_decision())
    assert result['phien_ban'] == 2 and result['nap_bu'] is None
    assert 'Cột mới có hiệu lực từ lần gửi sau' in result['thong_bao']
    assert 'yêu cầu mới trong hàng đợi' in result['thong_bao']
    assert queued == [newer['id']]
    assert [json.loads(p.read_text(encoding='utf-8'))['id'] for p in store.queue_files()] == [newer['id']]
    assert registry.upgrade_notice('orders_enriched', 2) == result['thong_bao']


def test_backfill_needing_review_is_not_offered_to_enqueue(context, monkeypatch):
    store, registry, doc, _, queued = context
    record = source(store, [*doc['header'], 'bonus'], '1', '2026-11-01T00:00:00Z')
    propose = auto_mapping.propose

    def conflict(*args):
        body = propose(*args)
        body['xung_dot_khoa']['id_trung_khac_noi_dung'] = 1
        return body

    calls = []
    monkeypatch.setattr(auto_mapping, 'propose', conflict)
    monkeypatch.setattr(nr, '_enqueue_locked', lambda *args, **kwargs: calls.append(args))
    result = store.upgrade_contract(record['id'], bonus_decision())
    assert result['nap_bu'] is None and not queued and not calls
    assert 'cần đội dữ liệu kiểm tra' in result['thong_bao']
    assert registry.current('orders_enriched')[0]['phien_ban'] == 2


@pytest.mark.parametrize('kind', ['missing', 'invalid_json', 'missing_field', 'invalid_item', 'no_model'])
def test_queue_discards_broken_head_and_starts_next(tmp_path, monkeypatch, kind):
    store = ns.RequestStore(tmp_path)
    events = runner_setup(store, monkeypatch)
    bad, good = queued_record(store), queued_record(store)
    store.queue_add(bad)
    head = store.queue_files()[0]
    store.queue_add(good)
    record_path = store.folder(bad['id']) / 'yeu_cau.json'
    if kind == 'missing':
        record_path.unlink()
    elif kind == 'invalid_json':
        record_path.write_text('{', encoding='utf-8')
    elif kind == 'invalid_item':
        head.write_text('[]', encoding='utf-8')
    elif kind == 'missing_field':
        bad.pop('revision')
        atomic_json(record_path, bad)
    elif kind == 'no_model':
        bad['ten_mo_rong'] = 'unknown'
        store.save(bad)
        monkeypatch.setattr(nr, 'has_dbt_model', lambda name, _: name != 'unknown')
    result = nr.recover_queue(store)
    assert result['id'] == good['id'] and result['trang_thai'] == 'dang_chay'
    assert not head.exists() and not store.queue_files()
    assert any('Bỏ mục không đọc được' in e[2].get('ly_do', '') for e in events)


@pytest.mark.parametrize('busy', ['worker', 'writer'])
def test_rollback_refuses_running_worker_or_pipeline_writer(tmp_path, monkeypatch, busy):
    store = ns.RequestStore(tmp_path)
    runner_setup(store, monkeypatch)
    calls = []
    monkeypatch.setattr(nr.subprocess, 'run', lambda *args, **kwargs: calls.append(args))
    path = store.root / 'worker' if busy == 'worker' else store.base / nr.PIPELINE_ROOT
    with writer_lock(path):
        with pytest.raises(ValueError):
            nr.rollback(store, 'a' * 24)
    assert not calls


def test_rollback_options_only_ready_nonactive(tmp_path):
    store = ns.RequestStore(tmp_path)
    atomic_json(store.base / nr.PIPELINE_ROOT / 'state.json', {'payload': {
        'active': 'a' * 24, 'releases': {
            'a' * 24: {'status': 'ready'}, 'b' * 24: {'status': 'ready'},
            'c' * 24: {'status': 'building'}, 'd' * 24: {'status': 'failed'}, 'e' * 24: {}}}})
    assert nr.rollback_options(store) == ['b' * 24]


@pytest.mark.parametrize('release', ['', '../outside', 'g' * 24, 'a' * 23, 'a' * 25, '--target'])
def test_rollback_command_rejects_invalid_release(release):
    with pytest.raises(ValueError, match='Mã bản dữ liệu'):
        nr.rollback_command(release, 'ui-rollback-20261102T120000Z')


def test_system_started_manual_route_does_not_auto_publish(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    events = runner_setup(store, monkeypatch)
    record = queued_record(store, route='tay')
    with nr.dispatch_lock(store):
        running = nr._start_locked(store, record['id'], record['revision'], 'he_thong')
    result = nr.run_worker(store, record['id'], running['run_id'])
    assert result['trang_thai'] == 'da_kiem'
    assert not any(event[1] == 'nhap_cong_bo' for event in events)


@pytest.mark.parametrize('action,display,optional', [('nap', 'silver', True), ('bo', 'mart', True), ('nap', 'mart', False)])
def test_upgrade_marks_only_silver_and_ignored_optional(context, monkeypatch, action, display, optional):
    store, registry, doc, _, _ = context
    record = source(store, [*doc['header'], 'bonus'], '1')
    if action == 'nap' and display == 'mart':
        monkeypatch.setattr(store, 'mart_column_available', lambda *args: True)
    decisions = [{**bonus_decision()[0], 'xu_ly': action, 'hien_thi': display,
                  'ly_do': 'Chưa dùng', 'tuy_chon': True}]
    store.upgrade_contract(record['id'], decisions)
    _, upgraded = registry.current('orders_enriched')
    assert upgraded['cot'][:-1] == doc['cot']
    assert upgraded['cot'][-1]['tuy_chon'] is optional
    result = store.submit(upload(doc['header']), '')
    assert result['phan_loai']['ket_qua'] == ('tu_dong' if optional else 'can_nguoi')
    if optional:
        assert result['phan_loai']['cot_tuy_chon_thieu'] == ['bonus']
        assert result['trang_thai'] == 'da_duyet'
    else:
        assert [r['ma'] for r in result['ly_do']] == ['thieu_cot']


@pytest.mark.parametrize('page,role', [('gui_du_lieu', 'quan_ly'), ('duyet_du_lieu', 'ky_su')])
def test_pages_skip_busy_dispatch_and_show_missing_optional(tmp_path, monkeypatch, page, role):
    store = ns.RequestStore(tmp_path)
    record = store.create(upload(['order_id']), '', 'manager')
    record.update(duong='tu_dong', phan_loai={'cot_tuy_chon_thieu': ['bonus']})
    store.save(record)
    monkeypatch.setattr(ns, 'RequestStore', lambda: store)
    monkeypatch.setattr(ns, 'nhap_kha_dung', lambda: True)
    monkeypatch.setattr(roles, 'current_role', lambda: role)
    monkeypatch.setattr(roles, 'logged_in_user', lambda: {'username': 'manager'})
    monkeypatch.setattr(store, 'sync_events', lambda: 0)
    monkeypatch.setattr(nr, '_kick_locked', lambda store: pytest.fail('Không khởi động ngoài khóa'))
    with writer_lock(store.root / 'dispatch'):
        started = time.monotonic()
        at = AppTest.from_file(str(ROOT / f'apps/retail_app/views/{page}.py')).run(timeout=3)
        elapsed = time.monotonic() - started
    assert not at.exception and elapsed < 3
    assert any('File không có cột `bonus`; bản dữ liệu này sẽ không có cột đó' == row.value for row in at.info)


def test_send_page_handles_recovery_oserror(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    monkeypatch.setattr(ns, 'RequestStore', lambda: store)
    monkeypatch.setattr(ns, 'nhap_kha_dung', lambda: True)
    monkeypatch.setattr(roles, 'current_role', lambda: 'quan_ly')
    monkeypatch.setattr(roles, 'logged_in_user', lambda: {'username': 'manager'})
    monkeypatch.setattr(nr, 'recover_queue', lambda *args, **kwargs: (_ for _ in ()).throw(OSError('Đĩa bận')))
    at = AppTest.from_file(str(ROOT / 'apps/retail_app/views/gui_du_lieu.py')).run()
    assert not at.exception and at.button[0].label == 'Gửi dữ liệu'


def test_backfill_same_active_release_uses_latest_request_provenance(context):
    store, _, doc, _, _ = context
    a = source(store, [*doc['header'], 'bonus'], '1', '2026-11-01T00:00:00Z')
    b = source(store, [*doc['header'], 'bonus'], '1', '2026-11-02T00:00:00Z')
    # Cùng nội dung và cùng bản phục vụ; nap_bu_tu vẫn phải giữ đúng nguồn gần nhất.
    assert a['sha256'] == b['sha256']
    result = store.upgrade_contract(a['id'], bonus_decision())
    assert store.read(result['nap_bu'])['nap_bu_tu'] == b['id']


def test_no_active_does_not_read_unrelated_broken_request(context):
    store, registry, doc, _, _ = context
    record = source(store, [*doc['header'], 'bonus'], '1')
    broken = store.create(upload(['order_id']), '', 'manager')
    (store.folder(broken['id']) / 'yeu_cau.json').write_text('{', encoding='utf-8')
    result = store.upgrade_contract(record['id'], bonus_decision())
    assert result['nap_bu'] is None and 'không tìm được yêu cầu đã công bố' in result['thong_bao']
    assert registry.current('orders_enriched')[0]['phien_ban'] == 2


def test_sync_preserves_replaced_prefix_instead_of_deleting_new_event(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    monkeypatch.setattr(roles, 'store', lambda: None)
    store.log_event('he_thong', 'nhap_chay', {'id': 'old'})
    path = store.root / 'nhat_ky_cho.jsonl'
    replacement = json.dumps({'ai': 'he_thong', 'su_kien': 'nhap_cong_bo', 'detail': {'id': 'new'}}) + '\n'

    def external_replacement(*args):
        # Mô phỏng file bị thay trong thời gian gửi mạng; khóa chỉ che các writer tuân thủ giao thức.
        with writer_lock(store.root / 'nhat_ky_cho'):
            path.write_text(replacement, encoding='utf-8')

    monkeypatch.setattr(roles, 'store', lambda: SimpleNamespace(log=external_replacement))
    with pytest.raises(ValueError, match='Nhật ký chờ đã đổi'):
        store.sync_events()
    assert path.read_text(encoding='utf-8') == replacement


@pytest.mark.skipif(os.name != 'nt', reason='Kiểm chia sẻ file thật trên Windows')
def test_save_and_queue_start_wait_for_open_request_file(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    runner_setup(store, monkeypatch)
    record = queued_record(store)
    store.queue_add(record)
    opened = threading.Event()
    path = store.folder(record['id']) / 'yeu_cau.json'

    def reader():
        with path.open(encoding='utf-8'):
            opened.set()
            time.sleep(1)

    thread = threading.Thread(target=reader)
    thread.start()
    assert opened.wait(5)
    try:
        started = time.monotonic()
        result = nr.recover_queue(store)
        assert time.monotonic() - started >= 0.8
    finally:
        thread.join(5)
    assert not thread.is_alive()
    assert result['trang_thai'] == 'dang_chay' and not store.queue_files()
    assert nr.run_worker(store, record['id'], result['run_id'])['trang_thai'] == 'da_cong_bo'


@pytest.mark.parametrize('location', ['request', 'state', 'queue'])
def test_json_reads_retry_permission_error(tmp_path, monkeypatch, location):
    store = ns.RequestStore(tmp_path)
    record = queued_record(store)
    if location == 'request':
        path = store.folder(record['id']) / 'yeu_cau.json'
        operation = lambda: store.read(record['id'])['id']
        expected = record['id']
    elif location == 'state':
        path = store.base / nr.PIPELINE_ROOT / 'state.json'
        atomic_json(path, {'payload': {'active': 'a' * 24}})
        operation = lambda: store.pipeline_state()['active']
        expected = 'a' * 24
    else:
        store.queue_add(record)
        path = store.queue_files()[0]
        operation = lambda: nr.queue_position(store, record['id'])
        expected = 1
    read = Path.read_text
    calls = []

    def busy_once(candidate, *args, **kwargs):
        if candidate == path:
            calls.append(candidate)
            if len(calls) == 1:
                raise PermissionError('Đang thay file')
        return read(candidate, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', busy_once)
    assert operation() == expected and len(calls) == 2


def test_queue_retries_transient_read_once_without_losing_head(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    runner_setup(store, monkeypatch)
    first, second = queued_record(store), queued_record(store)
    store.queue_add(first)
    store.queue_add(second)
    read = store.read
    calls = []

    def busy_once(request_id):
        calls.append(request_id)
        if len(calls) == 1:
            raise PermissionError('Tạm thời')
        return read(request_id)

    monkeypatch.setattr(store, 'read', busy_once)
    result = nr.recover_queue(store)
    assert result['id'] == first['id'] and result['trang_thai'] == 'dang_chay'
    assert nr.queue_position(store, second['id']) == 1
    assert read(second['id'])['trang_thai'] == 'da_duyet'


def test_queue_retries_request_lock_and_starts_head(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    runner_setup(store, monkeypatch)
    record = queued_record(store)
    store.queue_add(record)
    with held_briefly(store.folder(record['id'])):
        result = nr.recover_queue(store)
    assert result['id'] == record['id'] and result['trang_thai'] == 'dang_chay'
    assert not store.queue_files()


@pytest.mark.parametrize('kind', ['request_read', 'request_lock', 'queue_read', 'active_write'])
def test_persistent_transient_error_keeps_fifo_until_next_recovery(tmp_path, monkeypatch, kind):
    store = ns.RequestStore(tmp_path)
    events = runner_setup(store, monkeypatch)
    first, second = queued_record(store), queued_record(store)
    store.queue_add(first)
    store.queue_add(second)
    original_queue = store.queue_files()
    with monkeypatch.context() as patch:
        # Hết đủ số lần thử nhưng không làm test chờ 10 giây cho mỗi loại lỗi.
        patch.setattr(ns.time, 'sleep', lambda _: None)
        if kind == 'request_read':
            read = store.read
            patch.setattr(store, 'read', lambda rid: (_ for _ in ()).throw(PermissionError('Bận'))
                          if rid == first['id'] else read(rid))
        elif kind == 'queue_read':
            read = Path.read_text
            patch.setattr(Path, 'read_text', lambda p, *a, **kw: (_ for _ in ()).throw(PermissionError('Bận'))
                          if p == original_queue[0] else read(p, *a, **kw))
        elif kind == 'active_write':
            write = nr.atomic_json
            patch.setattr(nr, 'atomic_json', lambda p, value: (_ for _ in ()).throw(PermissionError('Bận'))
                          if p == store.root / 'active.json' else write(p, value))
        hold = writer_lock(store.folder(first['id'])) if kind == 'request_lock' else writer_lock(store.root / 'test_only')
        with hold:
            assert nr.recover_queue(store) is None
    assert store.queue_files() == original_queue
    assert store.read(first['id'])['trang_thai'] == store.read(second['id'])['trang_thai'] == 'da_duyet'
    message = 'Giữ mục, dừng lượt khởi động' if kind == 'active_write' else 'Giữ mục do lỗi tạm thời'
    assert any(message in e[2].get('ly_do', '') for e in events)
    result = nr.recover_queue(store)
    assert result['id'] == first['id'] and nr.queue_position(store, second['id']) == 1


def test_locked_distinguishes_lock_contention_from_body_io_error(tmp_path):
    store = ns.RequestStore(tmp_path)
    record = queued_record(store)
    with writer_lock(store.folder(record['id'])):
        with pytest.raises(ns.RequestBusyError):
            with store.locked(record['id'], record['revision']):
                pytest.fail('Không được vào vùng khóa')
    with pytest.raises(FileNotFoundError):
        with store.locked(record['id'], record['revision']):
            raise FileNotFoundError('Lỗi vĩnh viễn trong thân thao tác')


@pytest.mark.parametrize('failure', ['request', 'context'])
def test_post_publish_write_failure_reports_publication_not_pipeline_failure(tmp_path, monkeypatch, failure):
    store = ns.RequestStore(tmp_path)
    runner_setup(store, monkeypatch)
    record = queued_record(store)
    nr.enqueue(store, record['id'])
    running = store.read(record['id'])
    save = store.save
    stages = []

    def stage(store, record, stage, output):
        stages.append(stage)
        if stage == 'publish':
            if failure == 'context':
                raise nr.PublishedStateError(PermissionError('Không ghi được context'))
            monkeypatch.setattr(store, 'save', fail_published)
        return {'stage': 'published' if stage == 'publish' else stage, 'target': 'duckdb'}

    def fail_published(row):
        if row['trang_thai'] == 'da_cong_bo':
            raise PermissionError('Không ghi được yêu cầu')
        return save(row)

    monkeypatch.setattr(nr, '_stage', stage)
    with pytest.raises(nr.PublishedStateError, match='đã công bố nhưng chưa ghi được trạng thái'):
        nr.run_worker(store, record['id'], running['run_id'])
    saved = store.read(record['id'])
    assert stages == [*nr.STAGES, 'publish']
    assert saved['trang_thai'] == 'da_kiem'
    assert 'đã công bố nhưng chưa ghi được trạng thái' in saved['thong_bao']
    assert not any(step['toi'] == 'loi' for step in saved['lich_su'])
    assert not (store.root / 'active.json').exists()


def test_real_stage_wraps_context_write_failure_after_successful_cli(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    record = queued_record(store)
    record['run_id'] = 'ui-test-1'
    monkeypatch.setattr(nr.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=0))
    monkeypatch.setattr(nr, 'read_context', lambda *a: {'stage': 'published', 'target': 'duckdb'})
    monkeypatch.setattr(nr, 'save_context', lambda *a: (_ for _ in ()).throw(PermissionError('File đang bận')))
    with pytest.raises(nr.PublishedStateError, match='đã công bố nhưng chưa ghi được trạng thái'):
        nr._stage(store, record, 'publish', io.BytesIO())


def test_upgrade_rechecks_queue_before_creating_backfill(context, monkeypatch):
    store, registry, doc, events, _ = context
    record = source(store, [*doc['header'], 'bonus'], '1', '2026-11-01T00:00:00Z')
    newer = source(store, [*doc['header'], 'bonus'], '9')

    def log(*args):
        events.append(args)
        store.queue_add(newer)

    monkeypatch.setattr(ns, 'actor', lambda action: ('de1', SimpleNamespace(log=log)))
    monkeypatch.setattr(store, 'create', lambda *a: pytest.fail('Không tạo nạp bù khi đã có mục mới'))
    result = store.upgrade_contract(record['id'], bonus_decision())
    assert result['nap_bu'] is None and 'yêu cầu mới trong hàng đợi' in result['thong_bao']
    assert registry.current('orders_enriched')[0]['phien_ban'] == 2


def test_cancelled_backfill_is_labelled_and_cannot_start(context, monkeypatch):
    store, _, doc, _, _ = context
    origin = source(store, [*doc['header'], 'bonus'], '1', '2026-11-01T00:00:00Z')
    newer = source(store, [*doc['header'], 'bonus'], '9')
    process = store._process_submission

    def arrival(*args, **kwargs):
        result = process(*args, **kwargs)
        store.queue_add(newer)
        return result

    monkeypatch.setattr(store, '_process_submission', arrival)
    result = store.upgrade_contract(origin['id'], bonus_decision())
    assert result['nap_bu'] is None
    backfill = next(store.read(p.parent.name) for p in store.requests.glob('*/yeu_cau.json')
                    if store.read(p.parent.name).get('nap_bu_tu'))
    assert nr.cancelled_backfill(store, backfill)
    monkeypatch.setattr(nr, 'actor', lambda action: ('de1', SimpleNamespace(log=lambda *a: None)))
    with pytest.raises(ValueError, match='Yêu cầu nạp bù đã bị hủy, không chạy'):
        nr.start(store, backfill['id'], backfill['revision'])
    # Không để điều kiện bận hàng đợi che lỗi bỏ khóa nút vì nạp bù bị hủy.
    for path in store.queue_files():
        path.unlink()
    assert nr.busy_reason(store) == ''
    monkeypatch.setattr(ns, 'RequestStore', lambda: store)
    monkeypatch.setattr(ns, 'nhap_kha_dung', lambda: True)
    monkeypatch.setattr(roles, 'current_role', lambda: 'ky_su')
    monkeypatch.setattr(roles, 'logged_in_user', lambda: {'username': 'de1'})
    monkeypatch.setattr(store, 'visible', lambda *a: [backfill])
    at = AppTest.from_file(str(ROOT / 'apps/retail_app/views/duyet_du_lieu.py')).run()
    assert not at.exception
    assert any(row.value == 'Yêu cầu nạp bù đã bị hủy, không chạy' for row in at.warning)
    assert next(button for button in at.button if button.label == 'Chạy').disabled


@pytest.mark.parametrize('state,queued', [('loi', False), ('da_duyet', True)])
def test_backfill_error_or_queued_is_not_cancelled(tmp_path, monkeypatch, state, queued):
    store = ns.RequestStore(tmp_path)
    runner_setup(store, monkeypatch)
    record = queued_record(store, state=state)
    record['nap_bu_tu'] = '20261101T000000Z_abcdef'
    store.save(record)
    if queued:
        store.queue_add(record)
    assert nr.cancelled_backfill(store, record) is False


def test_failed_backfill_reviewed_manually_can_start(context, monkeypatch):
    store, _, doc, _, _ = context
    runner_setup(store, monkeypatch)
    # Fixture thường chặn kích hoạt; ca này dùng luồng hàng đợi thật, chỉ giả CLI/Popen.
    monkeypatch.setattr(nr, '_kick_locked', REAL_KICK)
    record = store.submit(upload(doc['header']), '')
    record = store.read(record['id'])
    record['nap_bu_tu'] = '20261101T000000Z_abcdef'
    store.save(record)
    monkeypatch.setattr(nr, '_stage', lambda *a: (_ for _ in ()).throw(RuntimeError('Lỗi kiểm thử')))
    failed = nr.run_worker(store, record['id'], record['run_id'])
    assert failed['trang_thai'] == 'loi' and not store.queue_files()
    reviewed = store.retry_review(record['id'], failed['revision'], 'Kiểm lại file')
    monkeypatch.setattr(approval, 'hop_dong_tu_de_xuat', lambda *a, **kw: doc)
    approved = store.approve(record['id'], reviewed['revision'], {}, 'orders_enriched')
    assert approved['trang_thai'] == 'da_duyet' and approved['duong'] == 'tay'
    assert approved['nap_bu_tu'] == record['nap_bu_tu']
    assert nr.cancelled_backfill(store, approved) is False
    monkeypatch.setattr(ns, 'RequestStore', lambda: store)
    monkeypatch.setattr(ns, 'nhap_kha_dung', lambda: True)
    monkeypatch.setattr(roles, 'current_role', lambda: 'ky_su')
    monkeypatch.setattr(roles, 'logged_in_user', lambda: {'username': 'de1'})
    at = AppTest.from_file(str(ROOT / 'apps/retail_app/views/duyet_du_lieu.py')).run()
    assert not at.exception
    button = next(button for button in at.button if button.label == 'Chạy')
    assert not button.disabled
    button.click().run()
    assert not at.exception
    running = store.read(record['id'])
    assert running['trang_thai'] == 'dang_chay' and running['nguoi_chay'] == 'de1'
    assert running['nap_bu_tu'] == record['nap_bu_tu']


@pytest.mark.parametrize('entry', ['recover', 'enqueue', 'manual'])
@pytest.mark.parametrize('error_type', [OSError, FileNotFoundError, PermissionError])
def test_worker_spawn_failure_stops_queue_but_manual_start_reports_error(tmp_path, monkeypatch, entry, error_type):
    store = ns.RequestStore(tmp_path)
    events = runner_setup(store, monkeypatch)
    first, second = queued_record(store), queued_record(store)
    calls = []

    def fail(*args, **kwargs):
        calls.append(args)
        error = error_type('Không tạo được tiến trình')
        error.winerror = 1455
        raise error

    with monkeypatch.context() as patch:
        patch.setattr(nr.subprocess, 'Popen', fail)
        if entry == 'manual':
            with pytest.raises(nr.WorkerStartError, match='Không tạo được tiến trình'):
                nr.start(store, first['id'], first['revision'])
        elif entry == 'enqueue':
            assert nr.enqueue(store, first['id']) is None
        else:
            store.queue_add(first)
            store.queue_add(second)
            assert nr.recover_queue(store) is None
    assert len(calls) == 1
    failed = store.read(first['id'])
    assert failed['trang_thai'] == 'loi' and 'Không tạo được tiến trình' in failed['thong_bao']
    assert not (store.root / 'active.json').exists()
    assert nr.queue_position(store, first['id']) is None
    assert store.read(second['id'])['trang_thai'] == 'da_duyet'
    if entry != 'manual':
        assert any(e[1] == 'nhap_xep_hang' and e[2].get('id') == first['id']
                   and 'Bỏ mục do lỗi khởi động worker' in e[2].get('ly_do', '') for e in events)
    if entry == 'recover':
        assert nr.queue_position(store, second['id']) == 1
        assert nr.recover_queue(store)['id'] == second['id']
        assert not store.queue_files()


@pytest.mark.parametrize('persistent', [False, True])
def test_queue_io_error_retries_or_keeps_fifo(tmp_path, monkeypatch, persistent):
    store = ns.RequestStore(tmp_path)
    events = runner_setup(store, monkeypatch)
    first, second = queued_record(store), queued_record(store)
    store.queue_add(first)
    store.queue_add(second)
    original = store.queue_files()
    read = store.read
    calls = []

    def io_error(request_id):
        if request_id == first['id']:
            calls.append(request_id)
            if persistent or len(calls) == 1:
                raise OSError(5, 'EIO')
        return read(request_id)

    with monkeypatch.context() as patch:
        patch.setattr(store, 'read', io_error)
        patch.setattr(nr.time, 'sleep', lambda _: None)
        result = nr.recover_queue(store)
    if persistent:
        assert result is None and len(calls) == 100
        assert store.queue_files() == original
        assert store.read(first['id'])['trang_thai'] == 'da_duyet'
        assert any('Giữ mục do lỗi tạm thời' in e[2].get('ly_do', '') for e in events)
        result = nr.recover_queue(store)
    assert result['id'] == first['id']
    assert store.read(second['id'])['trang_thai'] == 'da_duyet'
    assert nr.queue_position(store, second['id']) == 1


@pytest.mark.skipif(os.name != 'nt', reason='Khóa xóa file đang mở là hành vi Windows')
@pytest.mark.parametrize('broken', [False, True])
def test_open_queue_item_timeout_does_not_escape_or_duplicate_start(tmp_path, monkeypatch, broken):
    store = ns.RequestStore(tmp_path)
    events = runner_setup(store, monkeypatch)
    record = queued_record(store)
    store.queue_add(record)
    path = store.queue_files()[0]
    if broken:
        (store.folder(record['id']) / 'yeu_cau.json').unlink()
    monkeypatch.setattr(nr.time, 'sleep', lambda _: None)
    with path.open('rb'):
        started = nr.recover_queue(store)
    assert path.exists()
    assert any('Chưa xóa được mục hàng đợi' in e[2].get('ly_do', '') for e in events)
    if broken:
        assert started is None
    else:
        assert started['trang_thai'] == 'dang_chay'
        assert nr.run_worker(store, record['id'], started['run_id'])['trang_thai'] == 'da_cong_bo'
        assert store.read(record['id'])['lan_chay'] == 1
    assert nr.recover_queue(store) is None
    assert not path.exists()


@pytest.mark.skipif(os.name != 'nt', reason='Khóa xóa file đang mở là hành vi Windows')
@pytest.mark.parametrize('broken', [False, True])
def test_queue_item_open_for_one_second_is_removed(tmp_path, monkeypatch, broken):
    store = ns.RequestStore(tmp_path)
    runner_setup(store, monkeypatch)
    record = queued_record(store)
    store.queue_add(record)
    path = store.queue_files()[0]
    if broken:
        path.write_text('{', encoding='utf-8')
    opened = threading.Event()

    def reader():
        with path.open('rb'):
            opened.set()
            time.sleep(1)

    thread = threading.Thread(target=reader)
    thread.start()
    try:
        assert opened.wait(5)
        result = nr.recover_queue(store)
        assert not path.exists()
        assert result is None if broken else result['trang_thai'] == 'dang_chay'
    finally:
        thread.join(5)


@pytest.mark.parametrize('platform,kind,winerror,retries', [
    ('nt', PermissionError, 5, 100), ('nt', PermissionError, 32, 100),
    ('posix', PermissionError, 5, 1), ('nt', PermissionError, 13, 1),
    ('nt', OSError, 32, 1),
])
def test_queue_unlink_retries_only_windows_sharing_errors(tmp_path, monkeypatch, platform, kind, winerror, retries):
    store = ns.RequestStore(tmp_path)
    events = runner_setup(store, monkeypatch)
    calls, sleeps = [], []

    def fail(**kwargs):
        calls.append(kwargs)
        error = kind('Lỗi xóa')
        error.winerror = winerror
        raise error

    path = SimpleNamespace(name='queue.json', unlink=fail)
    monkeypatch.setattr(nr, 'os', SimpleNamespace(name=platform))
    monkeypatch.setattr(nr.time, 'sleep', sleeps.append)
    assert nr._remove_queue_item(store, path) is False
    assert len(calls) == retries and sleeps == [0.1] * (retries - 1)
    assert len(events) == 1 and 'Chưa xóa được mục hàng đợi' in events[0][2]['ly_do']


@pytest.mark.parametrize('location', ['log', 'marker', 'state', 'pid', 'pid_marker'])
@pytest.mark.parametrize('error_type', [OSError, FileNotFoundError, ValueError])
def test_start_write_failure_never_retries_or_starts_next(tmp_path, monkeypatch, location, error_type):
    store = ns.RequestStore(tmp_path)
    events = runner_setup(store, monkeypatch)
    first, second = queued_record(store), queued_record(store)
    store.queue_add(first)
    store.queue_add(second)
    original_queue = store.queue_files()
    calls, spawns = [], []
    save, write, log = store.save, nr.atomic_json, store.log_event

    def fail():
        calls.append(location)
        raise error_type('Lỗi ghi khởi động')

    def save_failed(record):
        if record['trang_thai'] == 'dang_chay':
            if location == 'state' or (location == 'pid' and record.get('worker_pid')):
                fail()
        return save(record)

    def write_failed(path, value):
        if path == store.root / 'active.json':
            if location == 'marker' or (location == 'pid_marker' and value.get('worker_pid')):
                fail()
        return write(path, value)

    def log_failed(user, event, detail):
        log(user, event, detail)
        if location == 'log' and event == 'nhap_chay':
            fail()

    def spawn(*args, **kwargs):
        spawns.append(args)
        return SimpleNamespace(pid=999999999)

    monkeypatch.setattr(store, 'save', save_failed)
    monkeypatch.setattr(nr, 'atomic_json', write_failed)
    monkeypatch.setattr(store, 'log_event', log_failed)
    monkeypatch.setattr(nr.subprocess, 'Popen', spawn)
    assert nr.recover_queue(store) is None
    assert calls == [location]
    assert len(spawns) == (1 if location in ('pid', 'pid_marker') else 0)
    assert store.queue_files() == original_queue
    assert store.read(second['id'])['trang_thai'] == 'da_duyet'
    assert [e[2]['id'] for e in events if e[1] == 'nhap_chay'] == [first['id']]
    assert any('dừng lượt khởi động' in e[2].get('ly_do', '') for e in events)


@pytest.mark.parametrize('entry', ['queue', 'manual'])
def test_spawn_failure_preserves_marker_when_error_state_cannot_be_saved(tmp_path, monkeypatch, entry):
    store = ns.RequestStore(tmp_path)
    runner_setup(store, monkeypatch)
    first, second = queued_record(store), queued_record(store)
    if entry == 'queue':
        store.queue_add(first)
        store.queue_add(second)
    active = store.root / 'active.json'
    change = store.change

    def fail_state(record, state, *args, **kwargs):
        if state == 'loi':
            assert active.exists()
            raise OSError(5, 'Không ghi được trạng thái lỗi')
        return change(record, state, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(store, 'change', fail_state)
        patch.setattr(nr.subprocess, 'Popen', lambda *a, **kw: (_ for _ in ()).throw(MemoryError('Hết RAM')))
        if entry == 'queue':
            assert nr.recover_queue(store) is None
        else:
            with pytest.raises(nr.WorkerStartError, match='Hết RAM'):
                nr.start(store, first['id'], first['revision'])
    assert store.read(first['id'])['trang_thai'] == 'dang_chay'
    assert active.exists() and ns.read_json(active)['id'] == first['id']
    assert store.read(second['id'])['trang_thai'] == 'da_duyet'
    nr.recover_queue(store)
    assert store.read(first['id'])['trang_thai'] == 'loi'
    if entry == 'queue':
        assert store.read(second['id'])['trang_thai'] == 'dang_chay'


def test_post_spawn_failure_is_not_worker_start_error(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    runner_setup(store, monkeypatch)
    record = queued_record(store)
    save = store.save

    def fail_pid(row):
        if row.get('worker_pid') and row['trang_thai'] == 'dang_chay':
            raise OSError(5, 'Không ghi được PID')
        return save(row)

    monkeypatch.setattr(store, 'save', fail_pid)
    with pytest.raises(nr.StartWriteError, match='Không ghi được PID') as caught:
        nr.start(store, record['id'], record['revision'])
    assert not isinstance(caught.value, nr.WorkerStartError)
    assert isinstance(caught.value.__cause__, OSError)


@pytest.mark.skipif(os.name != 'nt', reason='Khóa xóa file đang mở là hành vi Windows')
def test_spawn_failure_with_open_marker_stops_then_recovers(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    events = runner_setup(store, monkeypatch)
    first, second = queued_record(store), queued_record(store)
    store.queue_add(first)
    store.queue_add(second)
    active = store.root / 'active.json'
    handles = []

    def fail_spawn(*args, **kwargs):
        handles.append(active.open('rb'))
        raise OSError(22, 'Hết bộ nhớ', None, 1455)

    with monkeypatch.context() as patch:
        patch.setattr(nr.subprocess, 'Popen', fail_spawn)
        try:
            assert nr.recover_queue(store) is None
            assert store.read(first['id'])['trang_thai'] == 'loi'
            assert active.exists()
        finally:
            for handle in handles:
                handle.close()
    assert store.read(second['id'])['trang_thai'] == 'da_duyet'
    assert [e[2]['id'] for e in events if e[1] == 'nhap_chay'] == [first['id']]
    assert nr.queue_position(store, first['id']) is None
    assert nr.recover_queue(store)['id'] == second['id']


@pytest.mark.skipif(os.name != 'nt', reason='Khóa thay file đang mở là hành vi Windows')
def test_marker_held_open_has_one_start_event_and_bounded_wait(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    events = runner_setup(store, monkeypatch)
    first, second = queued_record(store), queued_record(store)
    store.queue_add(first)
    store.queue_add(second)
    active = store.root / 'active.json'
    handles = []
    log = store.log_event

    def hold_marker(user, event, detail):
        log(user, event, detail)
        if event == 'nhap_chay' and not handles:
            active.write_text('{}', encoding='utf-8')
            handles.append(active.open('rb'))

    monkeypatch.setattr(store, 'log_event', hold_marker)
    begin = time.monotonic()
    try:
        assert nr.recover_queue(store) is None
    finally:
        for handle in handles:
            handle.close()
    assert time.monotonic() - begin < 15
    assert [e[2]['id'] for e in events if e[1] == 'nhap_chay'] == [first['id']]
    assert store.read(first['id'])['trang_thai'] == store.read(second['id'])['trang_thai'] == 'da_duyet'
    assert len(store.queue_files()) == 2


def test_prewrite_io_retry_respects_elapsed_deadline(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    runner_setup(store, monkeypatch)
    record = queued_record(store)
    store.queue_add(record)
    calls = []

    def fail_read(request_id):
        calls.append(request_id)
        raise OSError(5, 'EIO')

    clock = iter([0, 11])
    monkeypatch.setattr(nr.time, 'monotonic', lambda: next(clock))
    monkeypatch.setattr(store, 'read', fail_read)
    monkeypatch.setattr(nr.time, 'sleep', lambda _: pytest.fail('Đã hết hạn, không thử lại'))
    assert nr.recover_queue(store) is None
    assert calls == [record['id']] and len(store.queue_files()) == 1


def test_invalid_upgrade_type_fails_before_audit_and_version(context):
    store, registry, doc, events, queued = context
    record = source(store, [*doc['header'], 'bonus'], '1')
    decision = bonus_decision()
    decision[0]['kieu'] = 'int'
    with pytest.raises(ValueError, match='kieu'):
        store.upgrade_contract(record['id'], decision)
    assert registry.current('orders_enriched')[0]['phien_ban'] == 1
    assert not (registry.folder('orders_enriched') / 'v2.yml').exists()
    assert not any(event[1] == 'nhap_nang_hop_dong' for event in events)
    assert not queued


@pytest.mark.parametrize('repeat', [1, 2])
def test_real_workers_finish_three_requests_fifo_with_fake_cli(tmp_path, repeat):
    """Bản sao cô lập: worker và khóa OS thật; CLI và kho nhật ký đều giả."""
    import shutil
    import textwrap
    base = tmp_path / f'round{repeat}'
    for relative in ('apps/retail_app/ui', 'scripts/ingest', 'scripts/pipeline'):
        shutil.copytree(ROOT / relative, base / relative,
                        ignore=shutil.ignore_patterns('__pycache__', 'tests'))
    # Worker không đọc tài khoản, secrets hay kết nối Neon trong phép thử.
    (base / 'apps/retail_app/ui/roles.py').write_text('def store():\n    return None\n', encoding='utf-8')
    models = base / 'retail_dbt/models'
    models.mkdir(parents=True)
    (models / 'fake.sql').write_text("{{ config(enabled=extension_enabled('orders_enriched')) }} select 1", encoding='utf-8')
    (base / 'scripts/pipeline/cli.py').write_text(textwrap.dedent('''\
        import argparse, json, time
        from pathlib import Path
        from scripts.pipeline.state import atomic_json, writer_lock
        parser = argparse.ArgumentParser()
        parser.add_argument('stage')
        for name in ('run-id', 'target', 'root', 'extension', 'extension-dir'):
            parser.add_argument('--' + name)
        args = parser.parse_args()
        assert args.target == 'duckdb' and args.root == 'warehouse/pipeline/ui-nhap'
        root = Path(args.root)
        with writer_lock(root):
            with (root / 'trace.jsonl').open('a', encoding='utf-8') as log:
                log.write(json.dumps([args.run_id, args.stage, 'start']) + '\\n')
            time.sleep(0.05)
            atomic_json(root / 'runs' / args.run_id / 'context.json', {
                'target': args.target, 'stage': 'published' if args.stage == 'publish' else args.stage,
                'run_id': args.run_id, 'release_id': 'a' * 24})
            with (root / 'trace.jsonl').open('a', encoding='utf-8') as log:
                log.write(json.dumps([args.run_id, args.stage, 'end']) + '\\n')
        '''), encoding='utf-8')
    driver = base / 'exercise.py'
    driver.write_text(textwrap.dedent('''\
        import io, json, time
        from pathlib import Path
        from ui import nhap_store as ns, nhap_runner as nr
        store = ns.RequestStore(Path.cwd())
        ids = []
        for i in range(3):
            file = io.BytesIO(b'order_id\\n1\\n')
            file.name = 'fresh.csv'
            record = store.create(file, '', 'manager')
            record = store.transition(record['id'], record['revision'], 'cho_duyet', 'manager')
            record = store.transition(record['id'], record['revision'], 'da_duyet', 'he_thong',
                duong='tu_dong', ten_mo_rong='orders_enriched',
                hop_dong={'ten': 'orders_enriched', 'phien_ban': 1})
            ids.append(record['id'])
            nr.enqueue(store, record['id'])
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            records = [store.read(key) for key in ids]
            if all(r['trang_thai'] in ('loi', 'da_cong_bo') for r in records) and not (store.root / 'active.json').exists():
                break
            time.sleep(0.05)
        trace = [json.loads(line) for line in (store.base / nr.PIPELINE_ROOT / 'trace.jsonl').read_text().splitlines()]
        print(json.dumps({'ids': ids, 'records': records, 'trace': trace, 'queue': len(store.queue_files())}))
        '''), encoding='utf-8')
    result = subprocess.run([sys.executable, '-B', str(driver)], cwd=base, capture_output=True,
                            text=True, encoding='utf-8', timeout=90,
                            env={**os.environ, 'PYTHONPATH': os.pathsep.join([str(base), str(base / 'apps/retail_app')]),
                                 'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1'})
    assert result.returncode == 0, result.stdout + result.stderr
    evidence = json.loads(result.stdout)
    assert [row['trang_thai'] for row in evidence['records']] == ['da_cong_bo'] * 3, evidence
    assert evidence['queue'] == 0
    assert all(row['lan_chay'] == 1 and row['nguoi_chay'] == 'he_thong' for row in evidence['records'])
    assert all(step['ai'] == 'he_thong' for row in evidence['records'] for step in row['lich_su'][2:])
    expected = [[f'ui-{key}-1', stage, event] for key in evidence['ids']
                for stage in (*nr.STAGES, 'publish') for event in ('start', 'end')]
    assert evidence['trace'] == expected
