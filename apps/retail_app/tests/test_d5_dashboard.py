"""D5a: kho DuckDB nhỏ tự dựng, AppTest và subprocess giả; không đọc dữ liệu thật."""
import json
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from ai_explain import tools
from dwh import releases, connection, guarded
from ui import common, roles, nhap_runner as nr, nhap_store as ns, ai_panel
from scripts.pipeline.state import Registry, atomic_json

APP = Path(__file__).resolve().parents[1] / 'app.py'
A, B = 'a' * 24, 'b' * 24


@pytest.fixture
def warehouse(tmp_path, monkeypatch):
    registry = Registry(tmp_path)
    registry.initialize()
    for rid, synthetic, amount in [(A, False, 10), (B, True, 90)]:
        schema = f'r_{rid}_reporting'
        path = tmp_path / (rid + '.duckdb')
        with duckdb.connect(str(path)) as con:
            con.execute(f'create schema {schema}')
            con.execute(f'set schema={schema!r}')
            end = 2023 if synthetic else 2022
            con.execute(f"""create table rpt_build_info as select timestamp '2026-01-01' built_at_utc,
                date '2012-07-04' data_start_date, date '{end}-12-31' data_end_date,
                2013 analysis_start_year, {end} analysis_end_year, 2014 growth_start_year""")
            con.execute("""create table rpt_health_summary as select 'tot' status_code, timestamp '2026-01-01' built_at_utc,
                true tests_are_current, true tests_are_complete, 1 n_tests_in_project, 1 n_tests_run,
                0 n_tests_not_pass, 'test' test_invocation_id, timestamp '2026-01-01' tests_started_at_utc""")
            con.execute(f"""create table rpt_revenue_yearly as select 2022 as year, true is_analysis_period,
                {amount}.0 r, {amount*2}.0 g, 0.5 capture_rate, 2 n, 0.1 yoy_rate""")
            con.execute("""create table rpt_revenue_total (
                period_code varchar, start_year integer, end_year integer, is_analysis_period boolean,
                r double, g double, capture_rate double)""")
            # Đặt kỳ gốc trước kỳ deck để phát hiện iloc[0] sai.
            con.execute("insert into rpt_revenue_total values ('2013-2022',2013,2022,?,10,20,0.5), ('2012-2022',2012,2022,false,30,60,0.5)", [not synthetic])
            if synthetic:
                con.execute("insert into rpt_revenue_total values ('2013-2023',2013,2023,true,90,180,0.5)")
        row = dict(release_id=rid, schema=schema, status='ready', snapshot_id='d'*12,
                   code_version='code', run_id='batch', duckdb_path=str(path))
        if synthetic: row['co_du_lieu_tong_hop'] = True
        registry.register(row)
    registry.publish(A, None)
    registry.publish_dashboard(B, None)
    monkeypatch.setenv('RETAIL_RELEASE_MODE', 'versioned')
    monkeypatch.setenv('RETAIL_RELEASE_STATE', str(registry.path))
    monkeypatch.setenv('RETAIL_BACKEND', 'duckdb')
    monkeypatch.setenv('RETAIL_BACKENDS', 'duckdb')
    st.cache_data.clear()
    releases.reset()
    yield registry
    releases.reset()
    st.cache_data.clear()


def test_t7_real_tool_sql_active_and_pin_restored(warehouse):
    releases.resolve('duckdb', pointer='dashboard')
    pin = releases.current()
    result = tools.run({'tool': 'get_revenue_summary', 'arguments': {'metric': 'R', 'year': 2022}}, 'duckdb')
    assert result.ok, result.message
    assert result.rows[0]['r'] == 10
    assert result.evidence.data_version['release_id'] == A
    assert result.evidence.queries
    for query in result.evidence.queries:
        assert f'r_{A}_reporting.' in query.sql
        assert f'r_{B}_reporting.' not in query.sql
    assert releases.current() == pin and pin['release_id'] == B


def test_t7_direct_guard_reads_active(warehouse):
    releases.resolve('duckdb', pointer='dashboard')
    session = guarded._DuckDBSession(5, 100)
    try:
        assert session.fetch(guarded.Statement('select r from reporting.rpt_revenue_yearly')).rows == [(10,)]
        assert releases.current()['release_id'] == B
    finally:
        session.close()


def test_t6_total_full_page_and_return(warehouse):
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception and not at.error
    assert any(w.value == 'Dữ liệu tổng hợp – chỉ để demo' for w in at.warning)
    assert any('kỳ gốc, số thật' in m.value for m in at.markdown)
    assert any('2013–2023 (kỳ phân tích)' in m.value for m in at.markdown)
    # Cách đọc phải lấy kỳ deck, dù SQL trả kỳ gốc trước.
    assert any('gộp 2012–2022' in m.value for m in at.markdown)
    assert at.dataframe[0].value['R (đơn đã giao)'].tolist() == ['0,00 tỷ']
    warehouse.clear_dashboard(B)
    at.run()
    assert not at.exception and not at.error and not at.warning
    assert not any('kỳ gốc, số thật' in m.value for m in at.markdown)


@pytest.mark.parametrize('page', ['ps1_do_dung', 'ps2_xu_huong', 'ps3_nhip_lich', 'ps4_don_mon_gia', 'ps5_nhom', 'suc_khoe_du_lieu', 'du_bao', 'ai_explain'])
def test_t6_each_page_selects_correct_schema(warehouse, monkeypatch, page):
    # Kiểm biên đọc của từng trang bằng kho nhỏ: dừng sau build_info, trước phần metric ngoài phạm vi fixture.
    seen = []
    original = common.load_or_stop
    def read(name, *args, **kwargs):
        data = original('build_info')
        seen.append((releases.current()['release_id'], int(data.iloc[0]['analysis_end_year'])))
        if name != 'build_info':
            st.stop()
        return data
    monkeypatch.setattr(common, 'load_or_stop', read)
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    seen.clear()
    at.switch_page(f'views/{page}.py').run()
    assert not at.exception and not at.error
    expected = A if page in ('du_bao', 'ai_explain') else B
    assert seen and all(rid == expected for rid, _ in seen)
    assert all(year == (2022 if expected == A else 2023) for _, year in seen)
    banners = [w for w in at.warning if w.value == 'Dữ liệu tổng hợp – chỉ để demo']
    assert len(banners) == (0 if expected == A else 1)
    if page == 'ai_explain':
        assert any('31/12/2022' in item.value and 'bản số thật' in item.value for item in at.info)

    warehouse.clear_dashboard(B)
    seen.clear()
    at.run()
    assert not at.exception and not at.error
    assert seen and all(rid == A and year == 2022 for rid, year in seen)
    assert not any(w.value == 'Dữ liệu tổng hợp – chỉ để demo' for w in at.warning)


def test_t6_panel_hidden_only_when_pointers_differ(warehouse):
    releases.resolve('duckdb', pointer='dashboard')
    from ai_explain.page_explain import request_ps1
    assert ai_panel.ai_unavailable('duckdb', object(), req=request_ps1('2019', 'year')) is None
    assert 'dữ liệu demo' in ai_panel.ai_unavailable('duckdb', object(), req=request_ps1('2023', 'year'))
    assert 'tạm ẩn' in ai_panel.ai_unavailable('duckdb', object())
    assert ai_panel.ai_unavailable('duckdb', object(), chat=True) is None
    warehouse.clear_dashboard(B)
    releases.reset('dashboard')
    releases.resolve('duckdb')
    assert ai_panel.ai_unavailable('duckdb', object()) is None


@pytest.mark.parametrize('pointer', ['active', 'dashboard'])
def test_t11_old_registry_same_record(warehouse, pointer):
    warehouse.clear_dashboard(B)
    expected = warehouse.read()['payload']['releases'][A]
    assert releases.resolve('duckdb', pointer=pointer) == expected
    assert 'co_du_lieu_tong_hop' not in expected
    assert common.period_label('2013-2022', 'total', True) == '2013–2022 (kỳ phân tích)'
    assert common.period_label('2012-2022', 'total', False) == '2012–2022 (toàn bộ dữ liệu)'


def test_t8_period_label_scoped_to_synthetic(warehouse):
    releases.resolve('duckdb', pointer='dashboard')
    assert common.period_label('2013-2022', 'total', False) == '2013–2022 (kỳ gốc, số thật)'
    assert common.period_label('2012-2022', 'total', False) == '2012–2022 (kỳ gốc, số thật)'
    with releases.active_scope():
        releases.resolve('duckdb')
        assert common.period_label('2013-2022', 'total', False) == '2013–2022 (toàn bộ dữ liệu)'


def test_t11_cache_follows_pointer(warehouse):
    releases.reset('dashboard')
    rec = connection.release_for_read('duckdb')
    demo = common.load('revenue_yearly', 'duckdb', rec['release_id'])[0]
    warehouse.clear_dashboard(B)
    releases.reset('dashboard')
    rec = connection.release_for_read('duckdb')
    real = common.load('revenue_yearly', 'duckdb', rec['release_id'])[0]
    assert demo.iloc[0]['r'] == 90 and real.iloc[0]['r'] == 10


@pytest.mark.parametrize('role', ['khach', 'quan_ly', 'phan_tich', 'ky_su'])
def test_t9_direct_action_requires_admin(warehouse, monkeypatch, role):
    monkeypatch.setattr(roles, 'current_role', lambda: role)
    monkeypatch.setattr(nr.subprocess, 'run', lambda *a, **kw: pytest.fail('Không được chạy subprocess'))
    with pytest.raises(PermissionError):
        nr.dashboard_action(ns.RequestStore(warehouse.path.parent), 'duckdb', B, confirmed=True)
    with pytest.raises(PermissionError):
        nr.dashboard_action(ns.RequestStore(warehouse.path.parent), 'duckdb')


def identity(monkeypatch, role='admin'):
    monkeypatch.setattr(roles, 'current_role', lambda: role)
    monkeypatch.setattr(roles, 'logged_in_user', lambda: {'username': 'admin1'})
    monkeypatch.setattr(roles, 'store', lambda: SimpleNamespace(log=lambda *a: None))


def test_t9_confirmation_commands_and_rollback_options(warehouse, monkeypatch):
    identity(monkeypatch)
    store = ns.RequestStore(warehouse.path.parent)
    calls = []
    monkeypatch.setattr(nr.subprocess, 'run', lambda args, **kw: calls.append((args, kw)) or SimpleNamespace(returncode=0))
    with pytest.raises(ValueError, match='xác nhận'):
        nr.dashboard_action(store, 'duckdb', B)
    assert not calls
    state = warehouse.read()
    state['payload']['releases'][B].pop('run_id')
    warehouse.save(state, state['payload'])
    nr.dashboard_action(store, 'duckdb', B, confirmed=True)
    args, kw = calls[0]
    assert args[3:5] == ['dat-dashboard', '--run-id']
    assert args[5].startswith('ui-dashboard-') and args[5] != 'batch'
    assert args[6:] == ['--release-id', B, '--xac-nhan-tong-hop', '--target', 'duckdb', '--root', str(warehouse.path.parent)]
    nr.dashboard_action(store, 'duckdb')
    assert calls[1][0][3] == 'tra-dashboard' and '--release-id' not in calls[1][0]
    monkeypatch.setattr(store, 'pipeline_state', lambda: warehouse.read()['payload'])
    monkeypatch.setattr(store, 'release_requests', lambda: {})
    assert B not in nr.rollback_options(store)
    assert nr.rollback_details(store) == []
    assert nr.rollback_command(A, 'ui-rollback-test')[-1] == 'warehouse/pipeline/ui-nhap'


@pytest.mark.parametrize('role', ['admin', 'ky_su'])
def test_t9_buttons_and_checkbox_without_requests(warehouse, monkeypatch, role):
    identity(monkeypatch, role)
    store = ns.RequestStore(warehouse.path.parent)
    monkeypatch.setattr(ns, 'RequestStore', lambda: store)
    monkeypatch.setattr(ns, 'nhap_kha_dung', lambda: True)
    monkeypatch.setattr(nr, 'recover_queue', lambda *a, **kw: None)
    monkeypatch.setattr(store, 'sync_events', lambda: 0)
    calls = []
    monkeypatch.setattr(nr.subprocess, 'run', lambda *a, **kw: calls.append(a) or SimpleNamespace(returncode=0))
    at = AppTest.from_file(str(APP.parent / 'views/duyet_du_lieu.py'), default_timeout=30).run()
    assert not at.exception
    buttons = [b for b in at.button if b.label == 'Đưa bản có đợt lên dashboard (demo)']
    assert len(buttons) == (1 if role == 'admin' else 0)
    if role == 'admin':
        buttons[0].click().run()
        assert not calls and any('xác nhận' in e.value for e in at.error)
        at.checkbox[0].check().run()
        next(b for b in at.button if b.label == 'Đưa bản có đợt lên dashboard (demo)').click().run()
        assert len(calls) == 1 and not at.checkbox[0].value and at.success


@pytest.mark.parametrize('damage', ['legacy', 'postgres', 'missing'])
def test_t9_unavailable_conditions(warehouse, monkeypatch, damage):
    if damage == 'legacy': monkeypatch.setenv('RETAIL_RELEASE_MODE', 'legacy')
    if damage == 'missing': monkeypatch.setenv('RETAIL_RELEASE_STATE', str(warehouse.path.parent / 'missing.json'))
    with pytest.raises(ValueError):
        nr.dashboard_state(warehouse.path.parent, 'postgres' if damage == 'postgres' else 'duckdb')



def test_t7_many_tools_keep_active_for_one_turn(warehouse):
    releases.resolve('duckdb', pointer='dashboard')
    old = warehouse.read()
    try:
        @releases.pinned_read
        def turn():
            one = tools.run({'tool': 'get_revenue_summary', 'arguments': {'metric': 'R', 'year': 2022}}, 'duckdb')
            assert one.ok
            # Giả lập registry đổi giữa hai tool: lượt đang đọc vẫn dùng bản đã ghim.
            state = warehouse.read()
            state['payload']['active'] = None
            warehouse.save(state, state['payload'])
            two = tools.run({'tool': 'get_revenue_summary', 'arguments': {'metric': 'R', 'year': 2022}}, 'duckdb')
            assert two.ok and two.evidence.data_version['release_id'] == A
        turn()
        assert releases.current()['release_id'] == B
    finally:
        warehouse.save(warehouse.read(), old['payload'])



def test_t6_hidden_panel_does_not_load_provider(warehouse, monkeypatch):
    monkeypatch.setattr(ai_panel.provider, 'from_config', lambda: pytest.fail('Khung ẩn không được nạp provider'))
    at = AppTest.from_string("""
from types import SimpleNamespace
from ui.common import sidebar
from ui.ai_panel import ai_panel
sidebar('admin')
ai_panel(SimpleNamespace(page='ps1'))
""").run()
    assert not at.exception
    assert any('tạm ẩn' in item.value for item in at.caption)
    assert not any('AI diễn giải' in item.value for item in at.markdown)
    assert not any('AI' in item.label for item in at.button)


def test_t1_null_dashboard_follows_active_and_clear_removes_keys(warehouse):
    state = warehouse.read()
    state['payload']['dashboard'] = None
    warehouse.save(state, state['payload'])
    assert releases.resolve('duckdb', pointer='dashboard')['release_id'] == A
    assert warehouse.clear_dashboard(None)
    assert 'dashboard' not in warehouse.read()['payload']
    assert 'dashboard_since' not in warehouse.read()['payload']


@pytest.mark.parametrize('page', ['du_bao', 'ai_explain'])
def test_t14_default_page_reads_active(warehouse, monkeypatch, page):
    monkeypatch.setattr(roles, 'current_role', lambda: 'phan_tich')
    monkeypatch.setitem(roles.DEFAULT_PAGE, 'phan_tich', page)
    original = common.load_or_stop
    seen = []
    def read(*args, **kwargs):
        data = original('build_info')
        seen.append((releases.current()['release_id'], int(data.iloc[0]['analysis_end_year'])))
        st.stop()
    monkeypatch.setattr(common, 'load_or_stop', read)
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception and not at.error
    assert seen and all(row == (A, 2022) for row in seen)
    assert not any(w.value == 'Dữ liệu tổng hợp – chỉ để demo' for w in at.warning)


@pytest.mark.parametrize('clear', [False, True])
@pytest.mark.parametrize('stderr', ['Kho không đọc được', ''])
def test_t9_dashboard_command_error_visible(warehouse, monkeypatch, clear, stderr):
    identity(monkeypatch)
    store = ns.RequestStore(warehouse.path.parent)
    monkeypatch.setattr(ns, 'RequestStore', lambda: store)
    monkeypatch.setattr(ns, 'nhap_kha_dung', lambda: True)
    monkeypatch.setattr(nr, 'recover_queue', lambda *a, **kw: None)
    monkeypatch.setattr(store, 'sync_events', lambda: 0)
    monkeypatch.setattr(nr.subprocess, 'run', lambda *a, **kw:
                        SimpleNamespace(returncode=2, stderr=stderr, stdout='Thông báo dự phòng'))
    at = AppTest.from_file(str(APP.parent / 'views/duyet_du_lieu.py'), default_timeout=30).run()
    if not clear:
        at.checkbox[0].check().run()
    label = 'Trả dashboard về bản số thật' if clear else 'Đưa bản có đợt lên dashboard (demo)'
    next(b for b in at.button if b.label == label).click().run()
    assert not at.exception
    assert any(e.value == (stderr or 'Thông báo dự phòng') for e in at.error)
    assert not at.success
