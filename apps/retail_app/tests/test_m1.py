"""M1: trang Tổng quan + PS1 (docs/gd2_app_plan.md §6).

Tiêu chí: app hiện đúng G = 16.430.476.585,53; R = 12.518.175.957,20; R/G = 76,2% (deck slide 4, gộp 2012–2022).
Số trên app phải là cột của rpt_* (không tự cộng): so thẻ KPI / thác với bảng đọc thẳng từ DB, trên cả hai backend.
"""
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from dwh import queries
from ui.fmt import num, pct, trieu, ty

APP = Path(__file__).resolve().parents[1] / 'app.py'
DECK = {'G: tiền hàng mọi đơn': '16.430.476.585,53', 'R: tiền thực nhận': '12.518.175.957,20',
        'Tỷ lệ thực nhận R/G': '76,2%'}
# feedback PM 2026-10-02: thẻ ghi gọn theo tỷ; số đầy đủ của deck nằm trong tooltip (?) của thẻ
THE_DECK = [('G: tiền hàng mọi đơn', '16,43 tỷ'), ('R: tiền thực nhận', '12,52 tỷ'), ('Tỷ lệ thực nhận R/G', '76,2%')]
BACKENDS = ['postgres', 'duckdb']


def _run(monkeypatch, backend, page=None):
    monkeypatch.setenv('RETAIL_BACKEND', backend)
    st.cache_data.clear()
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    if page:
        at.switch_page(page).run()
    assert not at.exception and not at.error
    return at


def _metrics(at) -> list[tuple[str, str]]:
    return [(m.label, m.value) for m in at.metric]


@pytest.mark.parametrize('backend', BACKENDS)
def test_bang_toan_ky_dung_so_deck(backend):
    t = queries.revenue_total(backend).set_index('period_code')
    assert list(t.index) == ['2012-2022', '2013-2022']
    assert num(t.loc['2012-2022', 'g'], 2) == '16.430.476.585,53'
    assert num(t.loc['2012-2022', 'r'], 2) == '12.518.175.957,20'
    assert pct(t.loc['2012-2022', 'capture_rate']) == '76,2%'
    assert num(t.loc['2013-2022', 'g'], 2) == '15.688.978.837,51'


@pytest.mark.parametrize('backend', BACKENDS)
def test_tong_quan_hien_dung_so_deck(monkeypatch, backend):
    at = _run(monkeypatch, backend)
    m = _metrics(at)
    assert m[:3] == THE_DECK                            # hàng thẻ đầu = 2012–2022, đúng số deck (làm tròn)
    _so_day_du_trong_help(at)
    t = queries.revenue_total(backend).set_index('period_code').loc['2013-2022']
    assert m[3:6] == [('G: tiền hàng mọi đơn', ty(t['g'], 2)), ('R: tiền thực nhận', ty(t['r'], 2)),
                      ('Tỷ lệ thực nhận R/G', pct(t['capture_rate']))]
    assert at.dataframe[0].value['R (đơn đã giao)'].tolist() == [ty(v, 2) for v in queries.revenue_yearly(backend)['r']]


def _so_day_du_trong_help(at):
    """Tiêu chí M1 (số đầy đủ của deck) vẫn kiểm được: rê chuột vào (?) của thẻ G, R."""
    assert f"Số đầy đủ: {DECK['G: tiền hàng mọi đơn']}." in at.metric[0].help
    assert f"Số đầy đủ: {DECK['R: tiền thực nhận']}." in at.metric[1].help


@pytest.mark.parametrize('backend', BACKENDS)
def test_ps1_mac_dinh_la_ky_cua_deck(monkeypatch, backend):
    at = _run(monkeypatch, backend, 'views/ps1_do_dung.py')
    assert at.selectbox[0].value == '2012-2022'
    assert _metrics(at)[:3] == THE_DECK
    _so_day_du_trong_help(at)
    # thác: 6 bước, cột đầu = G, cột cuối = R, đúng số của rpt_revenue_bridge
    thac = at.dataframe[0].value
    assert thac['Bước'].tolist() == ['G: tiền hàng mọi đơn', 'Đơn hủy', 'Đơn trả', 'Đơn chưa giao',
                                     'Chiết khấu đơn đã giao', 'R: thực nhận']
    b = queries.revenue_bridge(backend)
    b = b[b['period_code'] == '2012-2022']
    assert thac['Số tiền'].tolist() == [ty(a, 2, signed=a < 0) for a in b['amount']]   # cùng đơn vị nhãn cột
    assert thac['Số tiền'].iloc[0] == '16,43 tỷ' and thac['Số tiền'].iloc[-1] == '12,52 tỷ'


@pytest.mark.parametrize('backend', BACKENDS)
def test_ps1_chon_mot_nam_thi_doi_theo_rpt_revenue_yearly(monkeypatch, backend):
    at = _run(monkeypatch, backend, 'views/ps1_do_dung.py')
    at.selectbox[0].set_value('2019').run()
    assert not at.exception and not at.error
    y = queries.revenue_yearly(backend).set_index('year').loc[2019]
    assert _metrics(at) == [
        ('G: tiền hàng mọi đơn', ty(y['g'], 2)), ('R: tiền thực nhận', ty(y['r'], 2)),
        ('Tỷ lệ thực nhận R/G', pct(y['capture_rate'])), ('Tỷ lệ tiền hàng bị hủy', pct(y['cancelled_rate'])),
        ('Tỷ lệ chiết khấu', pct(y['discount_rate'])),
    ]
    assert _metrics(at)[0][1] == '1,14 tỷ'
    assert 'Số đầy đủ: 1.136.801.441,51.' in at.metric[0].help     # cùng số với bảng năm ở ảnh M0
    thac = at.dataframe[0].value
    # một năm: phần bị trừ chỉ vài chục triệu → thác ghi theo triệu (theo tỷ chỉ còn 1 chữ số: −0,04 tỷ)
    assert thac['Số tiền'].tolist() == ['1.136,8 triệu', '−106,2 triệu', '−61,3 triệu', '−60,9 triệu', '−44,1 triệu',
                                        '864,3 triệu']
    assert thac['Số tiền'].iloc[-1] == trieu(y['r'], 1)


@pytest.mark.parametrize('backend', BACKENDS)
@pytest.mark.parametrize('year, months', [('2019', list(range(1, 13))), ('2012', list(range(7, 13)))])
def test_ps1_chon_nam_thi_hien_tung_thang_cua_nam_do(monkeypatch, backend, year, months):
    # PM hỏi 2026-09-28: chọn năm thì phần "theo tháng" phải là các tháng của năm đó (2012 chỉ có T7–T12)
    at = _run(monkeypatch, backend, 'views/ps1_do_dung.py')
    at.selectbox[0].set_value(year).run()
    assert not at.exception and not at.error
    thang = at.dataframe[1].value
    assert thang['Tháng'].tolist() == [f'T{m}' for m in months]
    src = queries.revenue_monthly(backend)
    src = src[src['year'] == int(year)]
    assert thang['G'].tolist() == [trieu(v, 1) for v in src['g']]   # feedback PM 2026-10-02: bảng tháng ghi gọn theo triệu
    assert thang['R'].tolist() == [trieu(v, 1) for v in src['r']]
    assert at.dataframe[2].value['Năm'].tolist() == list(range(2012, 2023))   # bảng năm vẫn đủ để so sánh


def test_ps1_ky_gop_thi_bieu_do_thang_theo_dung_ky(monkeypatch):
    at = _run(monkeypatch, 'duckdb', 'views/ps1_do_dung.py')
    assert any('2012–2022 (toàn bộ dữ liệu), 126 tháng' in c.value for c in at.caption)
    at.selectbox[0].set_value('2013-2022').run()
    assert any('2013–2022 (kỳ phân tích), 120 tháng' in c.value for c in at.caption)
    assert len(at.dataframe) == 2   # kỳ gộp: không có bảng tháng (120 dòng quá dài), chỉ thác + bảng năm


def test_ps1_nhan_ky_lay_tu_bang_thac(monkeypatch):
    at = _run(monkeypatch, 'duckdb', 'views/ps1_do_dung.py')
    b = queries.revenue_bridge('duckdb')
    assert at.selectbox[0].options == [
        '2012–2022 (toàn bộ dữ liệu)', '2013–2022 (kỳ phân tích)', '2012 (chưa đủ năm, tham khảo)',
        *[str(y) for y in range(2013, 2023)]]
    assert len(at.selectbox[0].options) == b['period_code'].nunique()


@pytest.mark.parametrize('backend', BACKENDS)
def test_bang_nam_ps1_canh_phai_va_du_cot(monkeypatch, backend):
    at = _run(monkeypatch, backend, 'views/ps1_do_dung.py')
    nam = at.dataframe[1].value
    assert nam['Năm'].tolist() == list(range(2012, 2023))
    assert list(nam.columns) == ['Năm', 'G', 'R', 'R/G', 'Tỷ lệ hủy', 'Tỷ lệ hủy so năm trước',
                                 'Tỷ lệ chiết khấu', 'Tăng trưởng R']
    y = queries.revenue_yearly(backend)
    assert nam['R/G'].tolist() == [pct(v) for v in y['capture_rate']]
    assert nam['G'].tolist() == [ty(v, 2) for v in y['g']] and nam['R'].tolist() == [ty(v, 2) for v in y['r']]
    assert nam['Tăng trưởng R'].iloc[:2].tolist() == ['–', '–']   # 2012, 2013: chưa có năm trước đủ 12 tháng


def test_trang_suc_khoe_bao_doc_lai_thanh_cong(monkeypatch):
    # (trước M5 đây là trang tạm.) Bấm Đọc lại: liệt kê cả bảng rỗng (log nạp trên DuckDB, 0 dòng), không cảnh báo
    at = _run(monkeypatch, 'duckdb', 'views/suc_khoe_du_lieu.py')
    at.sidebar.button[0].click().run()
    msg = at.success[0].value
    assert 'thành công' in msg
    for bang in ['rpt_build_info` (1 dòng)', 'rpt_health_summary` (1 dòng)', 'rpt_health_ingest` (0 dòng)']:
        assert bang in msg, bang
    assert not at.warning
