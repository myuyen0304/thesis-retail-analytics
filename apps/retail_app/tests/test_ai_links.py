"""B6 (L2) deep link: nút mở trang từ chat giữ đúng bộ lọc của tool đã chạy. Mô hình giả, không gọi API.

Chứng minh: link dựng từ tham số của lời gọi tool `ok` (không từ câu văn của mô hình); trang mở bằng query params của
link chọn sẵn đúng kỳ / chiều / năm đó (đối chứng bằng chính widget của trang, không bằng hàm dựng link); giá trị lạ
không làm trang văng lỗi; không có link khi trang không giữ được bộ lọc hoặc câu trả lời chưa qua kiểm.
"""
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from ai_explain import links, service
from ai_explain.contracts import ToolResult
from tests.test_ai_chat import FakeProvider, _app, call, final
from tests.test_ai_forecast import ref, versioned          # noqa: F401 (fixture)
from tests.test_smoke import APP

OK = final(answer='Kết quả ở bảng bằng chứng.')


def _turn(q, *steps):
    return service.run_turn(q, [], 'duckdb', FakeProvider(*steps))


def _links(tool, **a):
    t = _turn('?', call(tool, **a), OK)
    assert t.results['T1'].ok, t.results['T1'].message
    return links.page_links(t.calls, t.results)


def _page(path, params):
    st.cache_data.clear()
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    at.query_params.update(params)
    at.switch_page(path).run()
    assert not at.exception, at.exception
    return at


# --- link dựng từ tham số của tool ---

@pytest.mark.parametrize('tool, args, page, params', [
    ('get_segment_contribution', dict(metric='R', dimension='region', year=2019), 'views/ps5_nhom.py',
     {'chieu': 'region', 'nam': '2019'}),
    ('get_segment_contribution', dict(metric='R', dimension='acquisition_channel', year=2016, group='email_campaign'),
     'views/ps5_nhom.py', {'chieu': 'acquisition_channel', 'nam': '2016'}),
    ('get_revenue_drivers', dict(metric='R', year=2017), 'views/ps4_don_mon_gia.py', {'ky': '2017'}),
    ('get_revenue_summary', dict(metric='G', year=2021), 'views/ps1_do_dung.py', {'ky': '2021'}),
    ('get_revenue_monthly', dict(metric='R', year=2018, month=8), 'views/ps1_do_dung.py', {'ky': '2018'}),
    ('get_revenue_gap', dict(period='2013-2022'), 'views/ps1_do_dung.py', {'ky': '2013-2022'}),
    ('get_revenue_gap', dict(period='year', year=2020), 'views/ps1_do_dung.py', {'ky': '2020'}),
    ('get_revenue_trend', dict(view='phases'), 'views/ps2_xu_huong.py', {}),
    ('get_calendar_pattern', dict(pattern='thang_8'), 'views/ps3_nhip_lich.py', {}),
])
def test_link_giu_bo_loc_cua_tool(tool, args, page, params):
    ls = _links(tool, **args)
    assert [(lk.page, lk.query_params, lk.ref) for lk in ls] == [(page, params, 'T1')]


@pytest.mark.parametrize('tool, args', [
    ('get_revenue_summary', dict(metric='R', year=2015, to_year=2022)),              # chuỗi nhiều năm
    ('get_metric_definition', dict(metric='R')),                                     # không có trang
])
def test_khong_co_link_khi_trang_khong_giu_duoc_bo_loc(tool, args):
    assert _links(tool, **args) == []


@pytest.mark.parametrize('tool, args', [
    ('get_segment_contribution', dict(metric='G', dimension='region', year=2019)),   # PS5 chỉ có R
    ('get_revenue_drivers', dict(metric='G', year=2019)),                            # PS4 chỉ có R
    ('get_revenue_drivers', dict(metric='R', year=2019, period_type='phase')),       # PS4 chọn giai đoạn theo mã A–D
])
def test_khong_co_link_cho_to_hop_catalog_chua_mo(tool, args):
    """Hôm nay catalog trả unsupported cho các tổ hợp này; nếu sau này mở, link vẫn không được trỏ sang trang chỉ có R."""
    assert links.page_links([('T1', tool, args)], {'T1': ToolResult('ok', '')}) == []


def test_tool_loi_khong_co_link_va_trung_thi_gop():
    bad = ToolResult('unsupported', 'năm ngoài dữ liệu')
    ok = _turn('?', call('get_segment_contribution', metric='R', dimension='category', year=2019), OK)
    (_, tool, args), = ok.calls
    calls = [('T1', tool, {**args, 'year': 2030}), ('T2', tool, args), ('T3', tool, args)]
    results = {'T1': bad, 'T2': ok.results['T1'], 'T3': ok.results['T1']}
    assert [lk.ref for lk in links.page_links(calls, results)] == ['T2']


def test_link_du_bao_chi_khi_la_model_chinh(versioned):
    t = _turn('?', call('get_forecast', metric='G', period='month', year=2023, month=8), OK)
    assert t.results['T1'].derived['selected_is_primary']
    assert [(lk.page, lk.query_params) for lk in links.page_links(t.calls, t.results)] == [('views/du_bao.py', {})]
    t2 = _turn('?', call('get_forecast', metric='G', period='month', year=2023, month=8, model='sarimax_full',
                         cogs_method='direct'), OK)
    assert t2.results['T1'].ok and not t2.results['T1'].derived['selected_is_primary']
    assert links.page_links(t2.calls, t2.results) == []


# --- trang mở bằng query params của link: đối chứng bằng widget của chính trang ---

@pytest.mark.parametrize('tool, args, widgets', [
    ('get_segment_contribution', dict(metric='R', dimension='region', year=2016),
     lambda at: (at.radio[0].value, at.selectbox[0].value) == ('region', 2016)),
    ('get_revenue_drivers', dict(metric='R', year=2021), lambda at: at.selectbox[0].value == '2021'),
    ('get_revenue_gap', dict(period='2013-2022'), lambda at: at.selectbox[0].value == '2013-2022'),
    ('get_revenue_monthly', dict(metric='R', year=2014, month=3), lambda at: at.selectbox[0].value == '2014'),
])
def test_trang_mo_tu_link_chon_san_dung_bo_loc(monkeypatch, tool, args, widgets):
    monkeypatch.setenv('RETAIL_BACKEND', 'duckdb')
    (lk,) = _links(tool, **args)
    at = _page(lk.page, lk.query_params)
    assert widgets(at), [w.value for w in (*at.radio, *at.selectbox)]
    assert not at.info or all('Link mở trang' not in i.value for i in at.info)


def test_trang_khong_co_tham_so_giu_mac_dinh(monkeypatch):
    monkeypatch.setenv('RETAIL_BACKEND', 'duckdb')
    at = _page('views/ps5_nhom.py', {})
    assert (at.radio[0].value, at.selectbox[0].value) == ('category', 2019)


@pytest.mark.parametrize('params', [{'chieu': 'tinh_thanh', 'nam': '2031'}, {'nam': 'x'}, {'chieu': ''}])
def test_tham_so_la_bao_ro_va_dung_mac_dinh(monkeypatch, params):
    monkeypatch.setenv('RETAIL_BACKEND', 'duckdb')
    at = _page('views/ps5_nhom.py', params)
    assert (at.radio[0].value, at.selectbox[0].value) == ('category', 2019)
    assert sum('Link mở trang' in i.value for i in at.info) == len(params)


# --- trang chat ---

SEG = dict(metric='R', dimension='region', year=2019)
SEG_OK = final(answer='R toàn công ty năm 2019 là {c1}.', claims=[{'id': 'c1', 'path': 'T1.rows[0].r_total'}])


def _page_links(at) -> list[tuple[str, str, str]]:
    return [(p.proto.page, p.proto.label, p.proto.query_string) for p in at.get('page_link')]


def test_trang_chat_hien_link_dung_trang_va_bo_loc(monkeypatch):
    fake = FakeProvider(call('get_segment_contribution', **SEG), SEG_OK)
    at = _app(monkeypatch, fake)
    at.chat_input[0].set_value('Khu vực nào kéo giảm R năm 2019?').run()
    assert not at.exception and at.session_state.ai_turns[0].status == 'ok'
    (page, label, qs), = _page_links(at)
    assert page == 'ps5_nhom' and qs == 'chieu=region&nam=2019' and 'khu vực, năm 2019' in label
    at.run()                                                            # rerun: vẽ lại, không gọi lại mô hình
    assert len(_page_links(at)) == 1 and len(fake.seen) == 2


def test_trang_chat_khong_hien_link_khi_cau_tra_loi_bi_chan(monkeypatch):
    lie = final(answer='R toàn công ty năm 2019 là {c1}, khoảng 860 triệu.', claims=[{'id': 'c1', 'path': 'T1.rows[0].r_total'}])
    fake = FakeProvider(call('get_segment_contribution', **SEG), lie, lie)
    at = _app(monkeypatch, fake)
    at.chat_input[0].set_value('Khu vực nào kéo giảm R năm 2019?').run()
    assert not at.exception and at.session_state.ai_turns[0].status != 'ok'
    assert _page_links(at) == []
