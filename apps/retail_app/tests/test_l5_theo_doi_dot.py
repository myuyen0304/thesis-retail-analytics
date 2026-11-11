"""B1: ảnh trạng thái, nhịp dò giả và trang thật qua AppTest; không gọi cloud."""
import json
import sys
from types import SimpleNamespace

import pytest
import streamlit as st
from databricks.sdk.errors import PermissionDenied
from streamlit.testing.v1 import AppTest

from ui import roles, nhap_dot as nd, theo_doi_dot as td, kho_dot as kd
from test_l1_dot_web import store, Upload, advance, RID, APP


WAITING = ('da_gui', 'dang_kiem', 'het_cho', 'cho_chay', 'dang_chay')
FINISHED = ('da_kiem', 'tren_dashboard', 'da_tra', 'loi', 'sai_hop_dong', 'loi_file', 'huy', 'hong')


def command(store, kind='dat'):
    store.kho.ghi_moi('lenh/000001.json', json.dumps({
        'loai': kind, 'release_id': RID}).encode())


def finish(store):
    store.kho.ghi_moi('lenh/000001.ket_qua.json',
                     b'{"ket_qua":"dat","thong_bao":"ok"}')


@pytest.fixture
def timer(monkeypatch):
    timer = SimpleNamespace(polls=[], intervals=[])

    def fragment(*, run_every):
        timer.intervals.append(run_every)

        def register(fn):
            timer.polls.append(fn)
            return fn
        return register

    monkeypatch.setattr(st, 'fragment', fragment)
    return timer


class RerunRequested(BaseException):
    pass


def catch_rerun(monkeypatch):
    scopes = []

    def rerun(*, scope):
        scopes.append(scope)
        raise RerunRequested()
    monkeypatch.setattr(st, 'rerun', rerun)
    return scopes


@pytest.mark.parametrize('state', WAITING)
def test_can_theo_doi_waiting(state):
    assert nd.can_theo_doi(nd.tao_anh_chup([{'trang_thai': state}], None)) is True


@pytest.mark.parametrize('state', FINISHED)
@pytest.mark.parametrize('result', [None, {'ket_qua': 'dat'}, {'ket_qua': 'loi'}])
def test_can_theo_doi_finished(state, result):
    cmd = None if result is None else {'so': 1, 'loai': 'dat', 'ket_qua': result}
    assert nd.can_theo_doi(nd.tao_anh_chup([{'trang_thai': state}], cmd)) is False


@pytest.mark.parametrize('kind', ['dat', 'tra'])
def test_can_theo_doi_pending_command(kind):
    assert nd.can_theo_doi(nd.tao_anh_chup([], {'so': 1, 'loai': kind, 'ket_qua': None})) is True


def test_snapshot_command_result_and_event(store):
    row = store.gui_dot([Upload()], 'batch', '')
    initial = store.anh_chup('admin1', 'admin')
    assert initial == store.anh_chup('admin1', 'admin')
    advance(store, row, ['dang_kiem'])
    event = store.anh_chup('admin1', 'admin')
    assert event != initial
    command(store)
    pending = store.anh_chup('admin1', 'admin')
    finish(store)
    assert store.anh_chup('admin1', 'admin') != pending


@pytest.mark.parametrize('key,value', [
    ('id', 'other'), ('trang_thai', 'loi'), ('release_id', RID),
    ('ma_loi', 'D2-0'), ('thong_bao', 'Thông báo mới')])
def test_snapshot_row_fields(key, value):
    row = dict(id='request', trang_thai='da_gui')
    initial = nd.tao_anh_chup([row], None)
    row[key] = value
    assert nd.tao_anh_chup([row], None) != initial


@pytest.mark.parametrize('key,value', [('so', 2), ('loai', 'tra'), ('ket_qua', {'ket_qua': 'dat'})])
def test_snapshot_command_fields(key, value):
    cmd = dict(so=1, loai='dat', ket_qua=None)
    initial = nd.tao_anh_chup([], cmd)
    cmd[key] = value
    assert nd.tao_anh_chup([], cmd) != initial


def test_snapshot_copies_result():
    cmd = dict(so=1, loai='dat', ket_qua={'ket_qua': 'dat'})
    initial = nd.tao_anh_chup([], cmd)
    cmd['ket_qua']['ket_qua'] = 'loi'
    assert nd.tao_anh_chup([], cmd) != initial


def test_snapshot_visibility(store, monkeypatch):
    row = store.gui_dot([Upload()], 'own', '')
    monkeypatch.setattr(roles, 'logged_in_user', lambda: {'username': 'other'})
    store.gui_dot([Upload()], 'other', '')
    own = store.anh_chup('admin1', 'quan_ly')
    assert [r[0] for r in own['rows']] == [row['id']]
    assert len(store.anh_chup('admin1', 'admin')['rows']) == 2
    assert not store.anh_chup('admin1', 'public')['rows']


@pytest.mark.parametrize('pending', [False, True])
def test_fragment_interval(store, timer, pending):
    if pending:
        command(store)
    td.theo_doi_dot(store, 'admin1', 'admin', store.anh_chup('admin1', 'admin'))
    assert timer.intervals == ['30s' if pending else None]


@pytest.mark.parametrize('error_type', [OSError, ValueError, PermissionDenied])
def test_poll_error_is_silent_and_retries(store, timer, monkeypatch, error_type):
    command(store)
    initial = store.anh_chup('admin1', 'admin')
    td.theo_doi_dot(store, 'admin1', 'admin', initial)
    original = store.anh_chup
    errors = []
    monkeypatch.setattr(st, 'error', lambda *args: errors.append(args))
    monkeypatch.setattr(store, 'anh_chup', lambda *a: (_ for _ in ()).throw(error_type('fake-private-detail')))
    timer.polls[-1]()
    assert not errors
    monkeypatch.setattr(store, 'anh_chup', original)
    finish(store)
    scopes = catch_rerun(monkeypatch)
    with pytest.raises(RerunRequested):
        timer.polls[-1]()
    assert scopes == ['app']


@pytest.mark.parametrize('change', ['role', 'username', 'logout'])
def test_identity_change_reruns_app(store, timer, monkeypatch, change):
    command(store)
    td.theo_doi_dot(store, 'admin1', 'admin', store.anh_chup('admin1', 'admin'))
    if change == 'role':
        monkeypatch.setattr(roles, 'current_role', lambda: 'ky_su')
    else:
        monkeypatch.setattr(roles, 'logged_in_user', lambda: None if change == 'logout' else {'username': 'other'})
    # Kiểm danh tính phải xảy ra trước cả việc đọc Volume.
    monkeypatch.setattr(store, 'anh_chup', lambda *a: pytest.fail('Đã đổi danh tính mà vẫn đọc kho'))
    scopes = catch_rerun(monkeypatch)
    with pytest.raises(RerunRequested):
        timer.polls[-1]()
    assert scopes == ['app']


def page_test(store, timer, monkeypatch, page):
    monkeypatch.setenv('RETAIL_NHAP_DOT', 'volume')
    monkeypatch.setenv('RETAIL_BACKEND', 'databricks')
    monkeypatch.setenv('RETAIL_BACKENDS', 'databricks')
    monkeypatch.setattr(kd, 'configured_store', lambda: store.kho)
    harness = SimpleNamespace(tick=False, draws=0, polls=timer.polls,
                              page=APP / 'views' / (page + '.py'))
    monkeypatch.setitem(sys.modules, '_l5_poll_harness', harness)
    source = """
import _l5_poll_harness as harness
if harness.tick:
    harness.tick = False
    harness.polls[-1]()
harness.draws += 1
exec(compile(harness.page.read_text(encoding='utf-8'), str(harness.page), 'exec'))
"""
    at = AppTest.from_string(source, default_timeout=20).run()
    assert not at.exception and not at.error
    assert harness.draws == 1 and len(timer.polls) == 1
    return at, harness


@pytest.mark.parametrize('kind', ['dat', 'tra'])
def test_dashboard_result_refreshes_page(store, timer, monkeypatch, kind):
    row = store.gui_dot([Upload()], 'batch', '')
    advance(store, row, ['dang_kiem', 'cho_chay', 'dang_chay', 'da_kiem'])
    command(store, kind)
    at, harness = page_test(store, timer, monkeypatch, 'duyet_du_lieu')
    assert any('Đang chờ Airflow xử lý lệnh' in item.value for item in at.info)
    assert timer.intervals == ['30s']
    scopes = []
    real_rerun = st.rerun

    def rerun(*args, **kwargs):
        scopes.append(kwargs.get('scope'))
        return real_rerun(*args, **kwargs)
    monkeypatch.setattr(st, 'rerun', rerun)
    finish(store)
    # Dò ảnh cũ trước khi vẽ trang: chỉ st.rerun(scope='app') mới tới lần vẽ thứ hai.
    harness.tick = True
    at.run()
    assert not at.exception and not at.error
    assert scopes == ['app'] and harness.draws == 2
    assert not any('Đang chờ Airflow xử lý lệnh' in item.value for item in at.info)
    assert timer.intervals[-1] is None


@pytest.mark.parametrize('page', ['gui_du_lieu', 'duyet_du_lieu'])
def test_event_refreshes_each_page(store, timer, monkeypatch, page):
    row = store.gui_dot([Upload()], 'batch', '')
    at, harness = page_test(store, timer, monkeypatch, page)
    assert any('Đã gửi' in item.label for item in at.expander)
    advance(store, row, ['dang_kiem'])
    scopes = []
    real_rerun = st.rerun

    def rerun(*args, **kwargs):
        scopes.append(kwargs.get('scope'))
        return real_rerun(*args, **kwargs)
    monkeypatch.setattr(st, 'rerun', rerun)
    harness.tick = True
    at.run()
    assert not at.exception and not at.error
    assert scopes == ['app'] and harness.draws == 2
    assert any('Đang kiểm tra file' in item.label for item in at.expander)


@pytest.mark.parametrize('page', ['gui_du_lieu', 'duyet_du_lieu'])
@pytest.mark.parametrize('dot_mode', ['dia', 'volume'])
@pytest.mark.parametrize('pending', [False, True])
def test_initial_snapshot_reuses_rendered_data(store, monkeypatch, page, dot_mode, pending):
    monkeypatch.setenv('RETAIL_NHAP_DOT', dot_mode)
    monkeypatch.setenv('RETAIL_BACKEND', 'databricks')
    monkeypatch.setenv('RETAIL_BACKENDS', 'databricks')
    monkeypatch.setattr(kd, 'configured_store', lambda: store.kho)
    row = store.gui_dot([Upload()], 'batch', '')
    if not pending:
        advance(store, row, ['dang_kiem', 'cho_chay', 'dang_chay', 'da_kiem'])
    calls = {'visible': [], 'latest_command': []}
    original_visible = nd.DotStore.visible
    original_command = nd.DotStore.latest_command
    real_fragment = st.fragment
    intervals = []

    def visible(self, *args):
        calls['visible'].append(args)
        return original_visible(self, *args)

    def latest_command(self, *args, **kwargs):
        calls['latest_command'].append(kwargs)
        return original_command(self, *args, **kwargs)

    def fragment(*args, **kwargs):
        intervals.append(kwargs['run_every'])
        return real_fragment(*args, **kwargs)

    monkeypatch.setattr(nd.DotStore, 'visible', visible)
    monkeypatch.setattr(nd.DotStore, 'latest_command', latest_command)
    # Giữ nguyên theo_doi_dot và thân fragment thật; chỉ đếm đăng ký nhịp.
    monkeypatch.setattr(st, 'fragment', fragment)
    at = AppTest.from_file(str(APP / 'views' / (page + '.py'))).run(timeout=20)
    expected_commands = 2 if page == 'duyet_du_lieu' and dot_mode == 'volume' else 1
    expected_interval = '30s' if pending else None
    assert not at.exception and not at.error
    assert len(calls['visible']) == 1
    assert len(calls['latest_command']) == expected_commands
    assert intervals == [expected_interval]

    # Mỗi lượt vẽ toàn trang tạo closure mới, nên vẫn bỏ lần đọc đầu.
    calls['visible'].clear()
    calls['latest_command'].clear()
    at.run(timeout=20)
    assert not at.exception and not at.error
    assert len(calls['visible']) == 1
    assert len(calls['latest_command']) == expected_commands
    assert intervals == [expected_interval, expected_interval]


@pytest.mark.parametrize('error_type', [OSError, ValueError, PermissionDenied])
def test_command_read_failure_during_poll_is_silent(store, timer, monkeypatch, error_type):
    command(store)
    td.theo_doi_dot(store, 'admin1', 'admin', store.anh_chup('admin1', 'admin'))
    original = store.kho.doc
    errors = []
    monkeypatch.setattr(st, 'error', lambda *a: errors.append(a))
    scopes = catch_rerun(monkeypatch)

    def read(path):
        if path == 'lenh/000001.json':
            raise error_type('fake-private-detail')
        return original(path)
    monkeypatch.setattr(store.kho, 'doc', read)
    timer.polls[-1]()
    assert not errors and not scopes
    monkeypatch.setattr(store.kho, 'doc', original)
    finish(store)
    with pytest.raises(RerunRequested):
        timer.polls[-1]()
    assert scopes == ['app']


@pytest.mark.parametrize('pending', [False, True])
def test_first_poll_skips_identity_and_store(store, timer, monkeypatch, pending):
    cmd = {'so': 1, 'loai': 'dat', 'ket_qua': None} if pending else None
    snapshot = nd.tao_anh_chup([], cmd)
    calls = []

    def logged_in_user():
        calls.append('identity')
        return {'username': 'admin1'}

    def current_role():
        calls.append('role')
        return 'admin'

    def read_snapshot(*args):
        calls.append('snapshot')
        return snapshot

    monkeypatch.setattr(roles, 'logged_in_user', logged_in_user)
    monkeypatch.setattr(roles, 'current_role', current_role)
    monkeypatch.setattr(store, 'anh_chup', read_snapshot)
    td.theo_doi_dot(store, 'admin1', 'admin', snapshot)
    assert calls == []
    assert len(timer.polls) == 1
    assert timer.intervals == ['30s' if pending else None]
    # Nhịp fragment kế tiếp mới kiểm danh tính, rồi đọc kho.
    timer.polls[-1]()
    assert calls == ['identity', 'role', 'snapshot']
