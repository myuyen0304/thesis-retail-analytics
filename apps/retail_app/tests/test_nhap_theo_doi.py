"""Kiểm vòng dò chung, thông báo cho người gửi và chọn bản khôi phục."""
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from test_nhap_tu_dong import context, source, bonus_decision, queued_record, runner_setup, ROOT
from ui import nhap_runner as nr, nhap_store as ns, roles
from scripts.pipeline.state import atomic_json


@pytest.mark.parametrize('state,route,actor,busy,queued,expected', [
    ('dang_chay', 'tu_dong', 'he_thong', True, False, True),
    ('da_duyet', 'tu_dong', 'he_thong', False, True, True),
    ('da_kiem', 'tu_dong', 'he_thong', True, False, True),
    ('da_kiem', 'tu_dong', 'he_thong', False, False, False),
    ('da_kiem', 'tay', 'de1', True, False, False),
    ('da_kiem', 'tu_dong', 'de1', True, False, False),
    ('da_cong_bo', 'tu_dong', 'he_thong', False, False, False),
])
def test_page_poll_only_for_unfinished_requests(tmp_path, monkeypatch, state, route, actor, busy, queued, expected):
    store = ns.RequestStore(tmp_path)
    row = queued_record(store, state=state, route=route)
    row['nguoi_chay'] = actor
    store.save(row)
    if queued:
        store.queue_add(row)
    monkeypatch.setattr(nr, 'page_busy', lambda _: busy)
    snapshot = nr.page_snapshot(store, 'manager', 'quan_ly')
    assert snapshot['pending'] is expected


@pytest.mark.parametrize('terminal', ['da_cong_bo', 'loi'])
def test_one_page_timer_reruns_and_toasts_once_without_changing_login(tmp_path, monkeypatch, terminal):
    store = ns.RequestStore(tmp_path)
    row = queued_record(store, state='dang_chay')
    row['nguoi_chay'] = 'he_thong'
    store.save(row)
    monkeypatch.setattr(nr, 'page_busy', lambda _: True)
    monkeypatch.setattr(roles, 'logged_in_user', lambda: {'username': 'manager'})
    monkeypatch.setattr(roles, 'current_role', lambda: 'quan_ly')
    session = {'login_token': 'unchanged'}
    timers, callbacks, toasts, reruns = [], [], [], []

    def fragment(*, run_every):
        timers.append(run_every)
        def wrap(fn):
            callbacks.append(fn)
            return lambda: None
        return wrap

    class Rerun(Exception):
        pass

    def rerun(**kwargs):
        reruns.append(kwargs)
        raise Rerun()

    monkeypatch.setattr(st, 'fragment', fragment)
    monkeypatch.setattr(st, 'session_state', session)
    monkeypatch.setattr(st, 'toast', toasts.append)
    monkeypatch.setattr(st, 'rerun', rerun)

    def render():
        snap = nr.page_snapshot(store, 'manager', 'quan_ly')
        nr.monitor_page(store, 'manager', 'quan_ly', snap, notify=True)
        callbacks[-1]()

    render()
    assert timers == ['5s'] and not toasts
    row.update(trang_thai='da_kiem')
    store.save(row)
    with pytest.raises(Rerun):
        callbacks[-1]()
    render()
    assert timers[-1] == '5s' and not toasts
    row.update(trang_thai=terminal)
    store.save(row)
    with pytest.raises(Rerun):
        callbacks[-1]()
    render()
    assert timers[-1] is None and len(toasts) == 1
    assert row['ten_file'] in toasts[0]
    render()
    assert len(toasts) == 1 and len(reruns) == 2
    assert session['login_token'] == 'unchanged'


def test_poll_detects_queue_start_and_new_backfill(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    row = queued_record(store)
    store.queue_add(row)
    monkeypatch.setattr(nr, 'page_busy', lambda _: False)
    before = nr.page_snapshot(store, 'manager', 'quan_ly')
    row['trang_thai'] = 'dang_chay'
    store.save(row)
    store.queue_files()[0].unlink()
    running = nr.page_snapshot(store, 'manager', 'quan_ly')
    assert running != before and running['pending']
    new = queued_record(store)
    new['nap_bu_tu'] = row['id']
    store.save(new)
    after = nr.page_snapshot(store, 'manager', 'quan_ly')
    assert after != running and len(after['rows']) == 2


@pytest.mark.parametrize('decision', ['pending', 'approved', 'rejected'])
def test_column_notice_tracks_contract_decision(context, decision):
    store, _, doc, _, _ = context
    row = source(store, [*doc['header'], 'bonus'], '1', '2026-11-01T00:00:00Z')
    if decision == 'approved':
        outcome = store.upgrade_contract(row['id'], bonus_decision())
    elif decision == 'rejected':
        store.reject_upgrade(row['id'], 'Chưa cần dùng')
    rows = store.visible('manager', 'quan_ly')
    message = store.column_notice(row, rows)
    assert 'bonus' in message
    if decision == 'pending':
        assert 'chờ đội dữ liệu duyệt' in message
    elif decision == 'rejected':
        assert 'Không nhận' in message and 'Chưa cần dùng' in message
    else:
        assert 'đã duyệt' in message and 'v2' in message and outcome['nap_bu'] in message
        assert 'bonus' in store.column_notice(store.read(outcome['nap_bu']), rows)
    assert 'sha' not in message and 'warehouse' not in message


@pytest.mark.parametrize('page', ['gui_du_lieu', 'duyet_du_lieu'])
def test_pages_have_one_timer_for_multiple_requests(tmp_path, monkeypatch, page):
    store = ns.RequestStore(tmp_path)
    runner_setup(store, monkeypatch)
    for _ in range(2):
        row = queued_record(store, state='dang_chay')
        row.update(stage='forecast', run_id='ui-test-1', nguoi_chay='he_thong', bat_dau=ns.utc())
        store.save(row)
    monkeypatch.setattr(ns, 'RequestStore', lambda: store)
    monkeypatch.setattr(ns, 'nhap_kha_dung', lambda: True)
    monkeypatch.setattr(nr, 'recover_queue', lambda *a, **kw: None)
    monkeypatch.setattr(nr, 'page_busy', lambda _: True)
    monkeypatch.setattr(roles, 'current_role', lambda: 'ky_su')
    monkeypatch.setattr(roles, 'logged_in_user', lambda: {'username': 'de1'})
    periods = []
    original = st.fragment

    def fragment(*args, **kwargs):
        periods.append(kwargs['run_every'])
        return original(*args, **kwargs)

    monkeypatch.setattr(st, 'fragment', fragment)
    app = AppTest.from_file(str(ROOT / f'apps/retail_app/views/{page}.py')).run()
    assert not app.exception
    assert periods == ['5s']
    if page == 'gui_du_lieu':
        assert any('bước 2/4' in item.value for item in app.info)
        assert not any('forecast' in item.value or 'local' in item.value for item in [*app.info, *app.caption])
    else:
        assert any('forecast' in item.value for item in app.info)


def test_sender_publish_gap_then_success_and_no_duplicate_toast(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    runner_setup(store, monkeypatch)
    row = queued_record(store, state='da_kiem')
    row['nguoi_chay'] = 'he_thong'
    store.save(row)
    monkeypatch.setattr(ns, 'RequestStore', lambda: store)
    monkeypatch.setattr(ns, 'nhap_kha_dung', lambda: True)
    monkeypatch.setattr(nr, 'recover_queue', lambda *a, **kw: None)
    monkeypatch.setattr(nr, 'page_busy', lambda _: True)
    monkeypatch.setattr(roles, 'current_role', lambda: 'quan_ly')
    monkeypatch.setattr(roles, 'logged_in_user', lambda: {'username': 'manager'})
    app = AppTest.from_file(str(ROOT / 'apps/retail_app/views/gui_du_lieu.py')).run()
    assert not app.exception and 'Đang xử lý' in app.expander[0].label
    row['trang_thai'] = 'da_cong_bo'
    store.save(row)
    app.run()
    assert not app.exception
    assert app.success[0].value == 'Đã cập nhật dữ liệu'
    assert len(app.get('toast')) == 1
    app.run()
    assert not app.get('toast')


def test_rollback_sorted_by_publication_with_full_values(tmp_path):
    store = ns.RequestStore(tmp_path)
    older, newer, unknown, active = 'f' * 24, 'a' * 24, 'b' * 24, 'c' * 24
    for release, published in [(older, '2026-11-01T10:00:00Z'), (newer, '2026-11-02T10:00:00Z')]:
        row = queued_record(store, state='da_cong_bo')
        row['lich_su'].append({'toi': 'da_cong_bo', 'luc': published})
        store.save(row)
        atomic_json(store.folder(row['id']) / 'chay/published.context.json', {'release_id': release})
    atomic_json(store.base / nr.PIPELINE_ROOT / 'state.json', {'payload': {
        'active': active, 'releases': {key: {'status': 'ready'} for key in [older, newer, unknown, active]}}})
    assert nr.rollback_options(store) == [newer, older, unknown]
    details = nr.rollback_details(store)
    assert row['id'] in details[0]['label'] and row['ten_file'] in details[0]['label']
    assert 'v1' in details[0]['label'] and '2026-11-02' in details[0]['label']
    assert 'Không tìm được yêu cầu' in details[-1]['label']


def test_rollback_widget_sends_full_id(tmp_path, monkeypatch):
    from types import SimpleNamespace
    store = ns.RequestStore(tmp_path)
    runner_setup(store, monkeypatch)
    row = queued_record(store, state='loi')
    release = 'a' * 24
    atomic_json(store.base / nr.PIPELINE_ROOT / 'state.json', {'payload': {
        'active': 'b' * 24, 'releases': {release: {'status': 'ready'}}}})
    monkeypatch.setattr(ns, 'RequestStore', lambda: store)
    monkeypatch.setattr(ns, 'nhap_kha_dung', lambda: True)
    monkeypatch.setattr(nr, 'recover_queue', lambda *a, **kw: None)
    monkeypatch.setattr(roles, 'current_role', lambda: 'admin')
    monkeypatch.setattr(roles, 'logged_in_user', lambda: {'username': 'admin'})
    sent = []
    monkeypatch.setattr(nr, 'rollback', lambda _, key: sent.append(key) or SimpleNamespace(returncode=0))
    app = AppTest.from_file(str(ROOT / 'apps/retail_app/views/duyet_du_lieu.py')).run()
    assert not app.exception
    select = next(item for item in app.selectbox if item.label == 'Bản cần khôi phục')
    assert 'Không tìm được yêu cầu' in select.options[0]
    assert select.value == release
    app.checkbox[0].check()
    next(item for item in app.button if item.label == 'Rollback').click().run()
    assert not app.exception and sent == [release]
    # Trang chạy lại sau rollback: báo đúng bản, ô xác nhận bỏ tick, bấm thêm lần nữa không đổi bản
    assert any(release[:8] in row.value for row in app.success)
    assert not app.checkbox[0].value
    next(item for item in app.button if item.label == 'Rollback').click().run()
    assert sent == [release] and any('Cần xác nhận' in row.value for row in app.warning)


@pytest.mark.parametrize('decision', ['approve', 'reject'])
def test_sender_waits_for_column_decision_and_stops_after_backfill(context, monkeypatch, decision):
    store, _, doc, _, _ = context
    row = source(store, [*doc['header'], 'bonus'], '1', '2026-11-01T00:00:00Z')
    monkeypatch.setattr(roles, 'current_role', lambda: 'quan_ly')
    monkeypatch.setattr(roles, 'logged_in_user', lambda: {'username': 'manager'})
    periods, callbacks, reruns = [], [], []

    class Rerun(Exception):
        pass

    def fragment(*, run_every):
        periods.append(run_every)
        def register(fn):
            callbacks.append(fn)
            return lambda: None
        return register

    def rerun(**kwargs):
        reruns.append(kwargs)
        raise Rerun()

    monkeypatch.setattr(st, 'fragment', fragment)
    monkeypatch.setattr(st, 'session_state', {})
    monkeypatch.setattr(st, 'rerun', rerun)
    monkeypatch.setattr(st, 'toast', lambda _: None)

    def render(notify=True):
        snapshot = nr.page_snapshot(store, 'manager', 'quan_ly')
        nr.monitor_page(store, 'manager', 'quan_ly', snapshot, notify=notify)
        callbacks[-1]()
        return snapshot

    initial = render(notify=False)
    assert periods[-1] is None and not initial['pending'] and initial['waiting_columns']
    render()
    assert periods[-1] == '5s'
    callbacks[-1]()
    callbacks[-1]()
    assert not reruns
    if decision == 'approve':
        outcome = store.upgrade_contract(row['id'], bonus_decision())
    else:
        store.reject_upgrade(row['id'], 'Không cần cột thưởng')
    with pytest.raises(Rerun):
        callbacks[-1]()
    updated = render()
    assert len(reruns) == 1 and not updated['waiting_columns']
    if decision == 'reject':
        assert periods[-1] is None
        assert 'Không cần cột thưởng' in updated['notices'][row['id']]
    else:
        assert periods[-1] == '5s' and updated['pending']
        assert 'đã duyệt' in updated['notices'][row['id']]
        assert outcome['nap_bu'] in updated['notices'][row['id']]
        assert any(r['id'] == outcome['nap_bu'] for r in updated['rows'])
        backfill = store.read(outcome['nap_bu'])
        backfill['trang_thai'] = 'da_cong_bo'
        store.save(backfill)
        for path in store.queue_files():
            path.unlink()
        with pytest.raises(Rerun):
            callbacks[-1]()
        finished = render()
        assert periods[-1] is None and not finished['pending'] and not finished['waiting_columns']
    count = len(reruns)
    callbacks[-1]()
    assert len(reruns) == count


@pytest.mark.parametrize('decision', ['approve', 'reject'])
def test_sender_displays_column_decision_and_new_backfill(context, monkeypatch, decision):
    store, _, doc, _, _ = context
    row = source(store, [*doc['header'], 'bonus'], '1', '2026-11-01T00:00:00Z')
    proposal = store.proposal

    def full_proposal(request_id):
        body = proposal(request_id)
        body.update(schema_diff={'cot_them': ['bonus']}, thuc_the_moi=[])
        body['file']['so_dong'] = 1
        body['xung_dot_khoa'].update(id_trung_nguon=0, danh_lai_khoa=0)
        return body

    monkeypatch.setattr(store, 'proposal', full_proposal)
    monkeypatch.setattr(ns, 'RequestStore', lambda: store)
    monkeypatch.setattr(ns, 'nhap_kha_dung', lambda: True)
    monkeypatch.setattr(roles, 'current_role', lambda: 'quan_ly')
    monkeypatch.setattr(roles, 'logged_in_user', lambda: {'username': 'manager'})
    app = AppTest.from_file(str(ROOT / 'apps/retail_app/views/gui_du_lieu.py')).run()
    assert not app.exception
    assert any('chờ đội dữ liệu duyệt' in item.value for item in app.info)
    if decision == 'approve':
        outcome = store.upgrade_contract(row['id'], bonus_decision())
    else:
        store.reject_upgrade(row['id'], 'Không cần cột thưởng')
    app.run()
    assert not app.exception
    assert not any('chờ đội dữ liệu duyệt' in item.value for item in app.info)
    if decision == 'approve':
        assert any('đã duyệt' in item.value and 'v2' in item.value for item in app.info)
        assert any(outcome['nap_bu'] in item.label for item in app.expander)
    else:
        assert any('Không nhận' in item.value and 'Không cần cột thưởng' in item.value for item in app.info)


def test_poll_snapshot_only_reads_and_does_not_recover_worker(context, monkeypatch):
    store, _, doc, _, _ = context
    row = source(store, [*doc['header'], 'bonus'], '1', '2026-11-01T00:00:00Z')
    atomic_json(store.root / 'active.json', {'id': row['id'], 'worker_pid': 999999999, 'started_at': 0})
    before = {p: p.read_bytes() for p in store.base.rglob('*') if p.is_file()}
    monkeypatch.setattr(nr, '_active_busy', lambda _: pytest.fail('Vòng dò không đối soát/ghi trạng thái'))
    monkeypatch.setattr(store, 'save', lambda _: pytest.fail('Vòng dò chỉ đọc'))
    snapshot = nr.page_snapshot(store, 'manager', 'quan_ly')
    assert not snapshot['pending'] and snapshot['waiting_columns'] and not snapshot['busy']
    after = {p: p.read_bytes() for p in store.base.rglob('*') if p.is_file()}
    assert before == after


def review_setup(store, monkeypatch):
    runner_setup(store, monkeypatch)
    monkeypatch.setattr(ns, 'RequestStore', lambda: store)
    monkeypatch.setattr(ns, 'nhap_kha_dung', lambda: True)
    monkeypatch.setattr(nr, 'recover_queue', lambda *a, **kw: None)
    monkeypatch.setattr(roles, 'current_role', lambda: 'ky_su')
    monkeypatch.setattr(roles, 'logged_in_user', lambda: {'username': 'de1'})


@pytest.mark.parametrize('change', ['other_state', 'selected_state', 'new_request'])
def test_review_selection_and_label_survive_poll_rerun(tmp_path, monkeypatch, change):
    store = ns.RequestStore(tmp_path)
    review_setup(store, monkeypatch)
    older = queued_record(store, state='loi')
    newer = queued_record(store, state='loi')
    app = AppTest.from_file(str(ROOT / 'apps/retail_app/views/duyet_du_lieu.py')).run()
    app.selectbox(key='nhap_selected_request').select(older['id']).run()
    assert not app.exception
    label = next(text for text in app.selectbox[0].options if older['id'] in text)
    assert label == f"{older['ten_file']} · {older['nguoi_gui']} · {older['id']}"
    if change == 'new_request':
        queued_record(store, state='loi')
    else:
        changed = newer if change == 'other_state' else older
        changed['trang_thai'] = 'da_kiem'
        store.save(changed)
    app.run()
    assert not app.exception
    assert app.selectbox(key='nhap_selected_request').value == older['id']
    assert next(text for text in app.selectbox[0].options if older['id'] in text) == label


def test_review_running_details_refresh_inside_single_fragment(tmp_path, monkeypatch):
    from contextlib import nullcontext
    from streamlit.runtime.scriptrunner_utils.script_run_context import ThreadState
    store = ns.RequestStore(tmp_path)
    review_setup(store, monkeypatch)
    row = queued_record(store, state='dang_chay')
    row.update(stage='forecast', run_id='ui-clock', bat_dau='2026-11-03T09:00:00+00:00')
    store.save(row)
    log = store.folder(row['id']) / 'chay/ui-clock.log'
    log.parent.mkdir()
    log.write_text('Dòng đầu', encoding='utf-8')
    seconds = [5]
    monkeypatch.setattr(nr, 'elapsed', lambda _: seconds[0])
    callbacks, periods, fragments = [], [], []
    original_fragment, original_info = st.fragment, st.info

    def fragment(*, run_every):
        periods.append(run_every)
        def wrap(fn):
            callbacks.append(fn)
            return original_fragment(run_every=run_every)(fn)
        return wrap

    def info(message, **kwargs):
        if message.startswith('Đang chạy forecast'):
            fragments.append(ThreadState.get().fragment_id)
        return original_info(message, **kwargs)

    monkeypatch.setattr(st, 'fragment', fragment)
    monkeypatch.setattr(st, 'info', info)
    app = AppTest.from_file(str(ROOT / 'apps/retail_app/views/duyet_du_lieu.py')).run()
    assert not app.exception and periods == ['5s']
    assert len(fragments) == 1 and fragments[0]
    assert len([item for item in app.info if 'Đang chạy forecast' in item.value]) == 1
    assert any('5 giây' in item.value for item in app.info)
    assert not any('Có thể tải lại trang' in item.value for item in app.info)
    messages, logs = [], []
    monkeypatch.setattr(st, 'session_state', {})
    monkeypatch.setattr(st, 'info', messages.append)
    monkeypatch.setattr(st, 'code', lambda text, **kw: logs.append(text))
    monkeypatch.setattr(st, 'expander', lambda *a, **kw: nullcontext())
    monkeypatch.setattr(st, 'rerun', lambda **kw: pytest.fail('Đồng hồ/log không được rerun cả trang'))
    for elapsed in (10, 15):
        messages.clear()
        logs.clear()
        seconds[0] = elapsed
        log.write_text(f'Log {elapsed}', encoding='utf-8')
        callbacks[0]()
        assert len(messages) == 1 and f'{elapsed} giây' in messages[0]
        assert logs == [f'Log {elapsed}']
    assert periods == ['5s']


@pytest.mark.parametrize('partial', [False, True])
def test_old_column_proposal_expires_consistently(context, monkeypatch, partial):
    store, _, doc, _, _ = context
    approved = source(store, [*doc['header'], 'bonus'], '1')
    columns = ['bonus', 'thuong_them'] if partial else ['thuong_them']
    expired = source(store, [*doc['header'], *columns], '1')
    expired['cot_moi'] = columns
    # Hai lượt đã kết thúc; ca này chỉ kiểm chờ quyết định cột.
    approved['trang_thai'] = expired['trang_thai'] = 'loi'
    store.save(approved)
    store.save(expired)
    assert {r['id'] for r in store.pending_upgrades()} == {approved['id'], expired['id']}
    store.upgrade_contract(approved['id'], bonus_decision())
    assert store.column_status(approved)['state'] == 'approved'
    assert store.column_status(expired) == {'state': 'expired', 'version': 2, 'columns': ['thuong_them']}
    assert not store.pending_upgrades() and not store.pending_columns(expired)
    message = store.column_notice(expired, store.visible('manager', 'quan_ly'))
    assert message == 'Hợp đồng đã lên v2, cột thuong_them chưa được xét. Gửi lại file để đề xuất.'
    snapshot = nr.page_snapshot(store, 'manager', 'quan_ly')
    assert not snapshot['waiting_columns'] and not snapshot['pending']
    periods = []
    monkeypatch.setattr(st, 'fragment', lambda *, run_every: periods.append(run_every) or (lambda fn: lambda: None))
    nr.monitor_page(store, 'manager', 'quan_ly', snapshot, notify=True)
    assert periods == [None]


def test_rejected_superset_does_not_hide_new_subset(context, monkeypatch):
    store, _, doc, _, _ = context
    rejected = source(store, [*doc['header'], 'bonus', 'thuong_them'], '1')
    rejected['cot_moi'] = ['bonus', 'thuong_them']
    rejected['trang_thai'] = 'loi'
    store.save(rejected)
    store.reject_upgrade(rejected['id'], 'Chưa cần cả hai cột')
    subset = source(store, [*doc['header'], 'bonus'], '1')
    subset['trang_thai'] = 'loi'
    store.save(subset)
    assert store.column_status(rejected)['state'] == 'rejected'
    assert [r['id'] for r in store.pending_upgrades()] == [subset['id']]
    assert store.pending_columns(subset)
    assert 'chờ đội dữ liệu duyệt' in store.column_notice(subset, [subset])
    snapshot = nr.page_snapshot(store, 'manager', 'quan_ly')
    assert not snapshot['pending'] and snapshot['waiting_columns']
    periods = []
    monkeypatch.setattr(st, 'fragment', lambda *, run_every: periods.append(run_every) or (lambda fn: lambda: None))
    nr.monitor_page(store, 'manager', 'quan_ly', snapshot, notify=True)
    assert periods == ['5s']


@pytest.fixture
def poll_capture(monkeypatch):
    from types import SimpleNamespace
    callbacks, toasts, reruns, periods = [], [], [], []

    class Rerun(Exception):
        pass

    def rerun(**kwargs):
        reruns.append(kwargs)
        raise Rerun()

    def fragment(*, run_every):
        periods.append(run_every)
        def wrap(fn):
            callbacks.append(fn)
            return fn
        return wrap

    monkeypatch.setattr(st, 'fragment', fragment)
    monkeypatch.setattr(st, 'session_state', {})
    monkeypatch.setattr(st, 'rerun', rerun)
    monkeypatch.setattr(st, 'toast', toasts.append)
    monkeypatch.setattr(roles, 'current_role', lambda: 'ky_su')
    monkeypatch.setattr(roles, 'logged_in_user', lambda: {'username': 'de1'})
    return SimpleNamespace(callbacks=callbacks, toasts=toasts, reruns=reruns, periods=periods, error=Rerun)


def test_dead_worker_with_queue_triggers_readonly_poll_then_recovers(tmp_path, monkeypatch, poll_capture):
    import os
    store = ns.RequestStore(tmp_path)
    runner_setup(store, monkeypatch)
    running = queued_record(store, state='dang_chay')
    running.update(run_id='ui-dead', nguoi_chay='he_thong')
    store.save(running)
    following = queued_record(store)
    store.queue_add(following)
    atomic_json(store.root / 'active.json', {'id': running['id'], 'run_id': running['run_id'],
                'worker_pid': os.getpid(), 'started_at': nr.time.time()})
    alive = [True]
    monkeypatch.setattr(nr, '_pid_alive', lambda _: alive[0])
    before = nr.page_snapshot(store, 'de1', 'ky_su')
    nr.monitor_page(store, 'de1', 'ky_su', before)
    files = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    alive[0] = False
    after = nr.page_snapshot(store, 'de1', 'ky_su')
    assert before['busy'] and after['busy']
    assert before['worker_alive'] and not after['worker_alive']
    with pytest.raises(poll_capture.error):
        poll_capture.callbacks[-1]()
    assert len(poll_capture.reruns) == 1
    assert files == {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    started = nr.recover_queue(store)
    assert store.read(running['id'])['trang_thai'] == 'loi'
    assert 'worker dừng bất thường' in store.read(running['id'])['thong_bao']
    assert started['id'] == following['id'] and started['trang_thai'] == 'dang_chay'
    assert not store.queue_files()
    alive[0] = True
    nr.monitor_page(store, 'de1', 'ky_su', nr.page_snapshot(store, 'de1', 'ky_su'))
    assert len(poll_capture.reruns) == 1


@pytest.mark.parametrize('error_type', [FileNotFoundError, PermissionError, OSError, ValueError])
def test_poll_tolerates_marker_disappearing_or_busy(tmp_path, monkeypatch, error_type):
    store = ns.RequestStore(tmp_path)
    marker = store.root / 'active.json'
    atomic_json(marker, {'worker_pid': 1})
    read_json = nr.read_json

    def interrupted(path):
        if path == marker:
            if error_type is FileNotFoundError:
                marker.unlink()
            raise error_type('Đọc marker bị gián đoạn')
        return read_json(path)

    monkeypatch.setattr(nr, 'read_json', interrupted)
    snapshot = nr.page_snapshot(store, 'de1', 'ky_su')
    assert snapshot['busy'] is (error_type is not FileNotFoundError)
    assert snapshot['worker_alive'] is snapshot['busy']


@pytest.mark.parametrize('terminal', ['da_cong_bo', 'loi'])
def test_review_never_toasts_on_terminal_change(tmp_path, poll_capture, terminal):
    store = ns.RequestStore(tmp_path)
    row = queued_record(store, state='dang_chay')
    nr.monitor_page(store, 'de1', 'ky_su', nr.page_snapshot(store, 'de1', 'ky_su'))
    row['trang_thai'] = terminal
    store.save(row)
    with pytest.raises(poll_capture.error):
        poll_capture.callbacks[-1]()
    nr.monitor_page(store, 'de1', 'ky_su', nr.page_snapshot(store, 'de1', 'ky_su'))
    poll_capture.callbacks[-1]()
    assert not poll_capture.toasts and len(poll_capture.reruns) == 1


def test_rollback_displays_vietnam_time_of_latest_publication(tmp_path):
    store = ns.RequestStore(tmp_path)
    latest, middle = 'a' * 24, 'f' * 24
    for release, times in [(latest, ['2026-11-03T07:00:00+00:00', '2026-11-03T09:23:18.464138+00:00']),
                           (middle, ['2026-11-03T08:00:00+00:00'])]:
        row = queued_record(store, state='da_cong_bo')
        row['lich_su'].extend({'toi': 'da_cong_bo', 'luc': stamp} for stamp in times)
        store.save(row)
        atomic_json(store.folder(row['id']) / 'chay/published.context.json', {'release_id': release})
    atomic_json(store.base / nr.PIPELINE_ROOT / 'state.json', {'payload': {
        'releases': {key: {'status': 'ready'} for key in (latest, middle)}}})
    details = nr.rollback_details(store)
    assert [item['id'] for item in details] == [latest, middle]
    assert details[0]['published'] == '2026-11-03T09:23:18.464138+00:00'
    assert details[0]['label'].split(' · ')[0] == '2026-11-03 16:23'
    assert details[1]['label'].split(' · ')[0] == '2026-11-03 15:00'


def advance_contract(registry, column):
    """Tạo phiên bản hợp đồng hợp lệ trong kho tạm để kiểm phần đọc trạng thái."""
    from copy import deepcopy
    meta, original = registry.current('orders_enriched')
    doc = deepcopy(original)
    doc.pop('hop_dong_sha256', None)
    doc['header'].append(column)
    doc['cot'].append({**bonus_decision()[0], 'ten': column, 'tuy_chon': True, 'trang_thai': 'da_duyet'})
    doc['phien_ban'] = meta['phien_ban'] + 1
    return registry.write('orders_enriched', doc, 'de1', 'test', expected=meta['phien_ban'])


@pytest.mark.parametrize('state,route', [
    ('da_gui', None), ('da_gui', 'tu_dong'), ('da_gui', 'tay'),
    ('cho_duyet', 'tu_dong'), ('da_duyet', 'tu_dong'),
])
@pytest.mark.parametrize('terminal', ['da_cong_bo', 'loi'])
def test_backfill_before_queue_keeps_polling_until_finished(context, monkeypatch, poll_capture, state, route, terminal):
    store, registry, doc, _, _ = context
    parent = source(store, [*doc['header'], 'bonus'], '1')
    parent['trang_thai'] = 'da_cong_bo'
    store.save(parent)
    advance_contract(registry, 'bonus')
    child = queued_record(store, state=state)
    child.update(nap_bu_tu=parent['id'])
    if route is None:
        child.pop('duong')
    else:
        child['duong'] = route
    if state in ('da_gui', 'cho_duyet'):
        child.pop('hop_dong')
    else:
        child['hop_dong']['phien_ban'] = 2
    store.save(child)
    monkeypatch.setattr(nr, 'recover_queue', lambda *a, **kw: pytest.fail('Vòng dò không phục hồi hàng đợi'))
    monkeypatch.setattr(roles, 'current_role', lambda: 'quan_ly')
    monkeypatch.setattr(roles, 'logged_in_user', lambda: {'username': 'manager'})

    def render():
        snapshot = nr.page_snapshot(store, 'manager', 'quan_ly')
        nr.monitor_page(store, 'manager', 'quan_ly', snapshot, notify=True)
        return snapshot

    files = {p: p.read_bytes() for p in store.base.rglob('*') if p.is_file()}
    before = render()
    assert before['pending'] and not before['waiting_columns']
    assert not any(before['positions'].values()) and not store.queue_files()
    assert poll_capture.periods == ['5s']
    poll_capture.callbacks[-1]()
    assert not poll_capture.reruns
    assert files == {p: p.read_bytes() for p in store.base.rglob('*') if p.is_file()}
    child.update(trang_thai='dang_chay', duong='tu_dong', nguoi_chay='he_thong')
    store.save(child)
    with pytest.raises(poll_capture.error):
        poll_capture.callbacks[-1]()
    assert render()['pending'] and poll_capture.periods[-1] == '5s'
    child['trang_thai'] = terminal
    store.save(child)
    with pytest.raises(poll_capture.error):
        poll_capture.callbacks[-1]()
    assert not render()['pending'] and poll_capture.periods[-1] is None
    assert len(poll_capture.reruns) == 2 and len(poll_capture.toasts) == 1
    poll_capture.callbacks[-1]()
    assert len(poll_capture.reruns) == 2 and len(poll_capture.toasts) == 1


@pytest.mark.parametrize('state', ['cho_duyet', 'da_duyet'])
@pytest.mark.parametrize('route', ['tay', None])
def test_manual_waiting_requests_do_not_keep_timer_alive(tmp_path, poll_capture, state, route):
    store = ns.RequestStore(tmp_path)
    row = queued_record(store, state=state, route=route)
    if route is None:
        row.pop('duong')
        store.save(row)
    snapshot = nr.page_snapshot(store, 'de1', 'ky_su')
    assert not snapshot['pending'] and not snapshot['waiting_columns']
    nr.monitor_page(store, 'de1', 'ky_su', snapshot, notify=True)
    assert poll_capture.periods == [None]


@pytest.mark.parametrize('page', ['gui_du_lieu', 'duyet_du_lieu'])
def test_pages_do_not_call_unclassified_upload_manual(tmp_path, monkeypatch, page):
    store = ns.RequestStore(tmp_path)
    review_setup(store, monkeypatch)
    row = queued_record(store, state='da_gui')
    row.pop('duong')
    row.pop('hop_dong')
    store.save(row)
    app = AppTest.from_file(str(ROOT / f'apps/retail_app/views/{page}.py')).run()
    assert not app.exception
    assert any(item.value == 'Đang đọc và hiểu file…' for item in app.caption)
    assert not any('Chờ đội dữ liệu' in item.value for item in app.caption)
    row.update(trang_thai='cho_duyet', duong='tay')
    store.save(row)
    app.run()
    assert not app.exception
    assert any('Chờ đội dữ liệu' in item.value for item in app.caption)


@pytest.mark.parametrize('direct_child', [True, False])
def test_approved_notice_finds_direct_child_or_same_version_backfill(context, direct_child):
    store, registry, doc, _, _ = context
    parent = source(store, [*doc['header'], 'bonus'], '1')
    sibling = source(store, [*doc['header'], 'bonus'], '1')
    advance_contract(registry, 'bonus')
    child = queued_record(store, state='da_gui')
    child['nap_bu_tu'] = parent['id'] if direct_child else sibling['id']
    if direct_child:
        child.pop('hop_dong')
        child.pop('duong')
    else:
        child['hop_dong']['phien_ban'] = 2
    store.save(child)
    message = store.column_notice(parent, [parent, sibling, child])
    assert 'đã duyệt trong hợp đồng v2' in message and child['id'] in message
    assert 'Có hiệu lực từ lần gửi sau' not in message
    assert 'Có hiệu lực từ lần gửi sau' in store.column_notice(parent, [parent])


def test_review_does_not_draw_other_running_request(tmp_path, monkeypatch):
    store = ns.RequestStore(tmp_path)
    review_setup(store, monkeypatch)
    idle = queued_record(store, state='loi')
    running = queued_record(store, state='dang_chay')
    running.update(stage='forecast', run_id='ui-other', bat_dau=ns.utc())
    store.save(running)
    app = AppTest.from_file(str(ROOT / 'apps/retail_app/views/duyet_du_lieu.py')).run()
    app.selectbox(key='nhap_selected_request').select(idle['id']).run()
    assert not app.exception and app.selectbox[0].value == idle['id']
    assert not any('Đang chạy forecast' in item.value for item in app.info)
    assert not any('Log lượt chạy' in item.label for item in app.expander)


def test_rejected_column_remains_rejected_after_unrelated_upgrade(context):
    store, registry, doc, _, _ = context
    row = source(store, [*doc['header'], 'bonus'], '1')
    store.reject_upgrade(row['id'], 'Chưa cần thưởng')
    advance_contract(registry, 'hoa_hong')
    assert store.column_status(row)['state'] == 'rejected'
    assert store.column_notice(row, [row]) == 'Không nhận cột bonus: Chưa cần thưởng'
    assert not store.pending_columns(row) and not store.pending_upgrades()


def test_manual_route_with_old_columns_is_not_an_upgrade(context):
    store, _, doc, _, _ = context
    row = source(store, [*doc['header'], 'bonus'], '1')
    row.update(trang_thai='loi')
    store.save(row)
    assert [item['id'] for item in store.pending_upgrades()] == [row['id']]
    row = store.retry_review(row['id'], row['revision'], 'Sửa lại hợp đồng của lượt')
    assert row['duong'] == 'tay' and row['cot_moi'] == ['bonus']
    assert not store.pending_upgrades() and not store.pending_columns(row)
    assert store.column_notice(row, [row]) == ''


def test_approved_notice_keeps_original_version_and_backfill_after_v3(context):
    store, registry, doc, _, _ = context
    row = source(store, [*doc['header'], 'bonus'], '1')
    origin = source(store, [*doc['header'], 'bonus'], '1')
    advance_contract(registry, 'bonus')
    child = queued_record(store, state='da_cong_bo')
    child['nap_bu_tu'] = origin['id']
    child['hop_dong']['phien_ban'] = 2
    store.save(child)
    before = store.column_notice(row, [row, child])
    advance_contract(registry, 'hoa_hong')
    later = queued_record(store, state='da_cong_bo')
    later['nap_bu_tu'] = origin['id']
    later['hop_dong']['phien_ban'] = 3
    store.save(later)
    after = store.column_notice(row, [row, child, later])
    assert before == after
    assert 'đã duyệt trong hợp đồng v2' in after and child['id'] in after
    assert later['id'] not in after and 'v3' not in after


def test_new_upload_without_route_or_backfill_keeps_polling(tmp_path, poll_capture):
    from test_nhap_tu_dong import upload
    store = ns.RequestStore(tmp_path)
    row = store.create(upload(['order_id']), '', 'manager')
    assert row['trang_thai'] == 'da_gui'
    assert all(key not in row for key in ('nap_bu_tu', 'duong', 'hop_dong'))
    snapshot = nr.page_snapshot(store, 'de1', 'ky_su')
    assert snapshot['positions'][row['id']] is None
    assert not snapshot['waiting_columns'] and not snapshot['busy']
    assert snapshot['pending'] is True
    nr.monitor_page(store, 'de1', 'ky_su', snapshot, notify=True)
    assert poll_capture.periods == ['5s']
