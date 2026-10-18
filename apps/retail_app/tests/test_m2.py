"""M2: trang PS2 (docs/gd2_app_plan.md §6).

Tiêu chí: CAGR A–D và độ lớn 3 điểm đổi hướng trên app = số đã chốt ngày 2026-09-27
(+8,75%, −6,39%, −39,10%, −0,14%; −9,7%, −39,1%, −6,7%), trên cả hai backend.
Giai đoạn đọc từ rpt_revenue_phase / rpt_revenue_turning_point (plan §3, tiêu chí 5): đổi bảng thì app đổi theo,
kiểm ở test_khong_hardcode.py.
"""
import json
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from dwh import queries
from ui.fmt import pct, trieu, ty

APP = Path(__file__).resolve().parents[1] / 'app.py'
PAGE = 'views/ps2_xu_huong.py'
BACKENDS = ['postgres', 'duckdb']
CAGR_CHOT = ['+8,75%', '−6,39%', '−39,10%', '−0,14%']
DO_LON_CHOT = ['−9,7%', '−39,1%', '−6,7%']


def _ps2(monkeypatch, backend):
    monkeypatch.setenv('RETAIL_BACKEND', backend)
    st.cache_data.clear()
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    at.switch_page(PAGE).run()
    assert not at.exception and not at.error
    return at


@pytest.mark.parametrize('backend', BACKENDS)
def test_the_kpi_la_cagr_da_chot(monkeypatch, backend):
    at = _ps2(monkeypatch, backend)
    assert [(m.label, m.value) for m in at.metric] == [
        ('A. Tăng trưởng (2013→2016)', '+8,75%/năm'),
        ('B. Chững/giảm nhẹ (2016→2018)', '−6,39%/năm'),
        ('C. Giảm mạnh (2018→2019)', '−39,10%/năm'),
        ('D. Đi ngang mức thấp (2019→2022)', '−0,14%/năm')]
    assert at.title[0].value == 'PS2 · Xu hướng doanh thu'
    assert any('Số lớn: CAGR (%/năm)' in c.value for c in at.caption)
    src = queries.revenue_phase(backend)
    phu = [(m.proto.delta, m.proto.delta_description) for m in at.metric]
    assert [a for a, _ in phu] == [pct(v, 1, signed=True) for v in src['total_change_rate']]
    assert phu == [(rate, 'Thay đổi toàn giai đoạn') for rate in ['+28,6%', '−12,4%', '−39,1%', '−0,4%']]
    assert all(f'({n} năm)' in m.help for m, n in zip(at.metric, src['n_years']))
    assert [t.label for t in at.tabs] == ['Điểm đổi hướng', 'Tăng trưởng năm / tháng', 'So sánh giai đoạn']


@pytest.mark.parametrize('backend', BACKENDS)
def test_bang_giai_doan_doc_tu_rpt_revenue_phase(monkeypatch, backend):
    tb = _ps2(monkeypatch, backend).dataframe[2].value
    assert tb['CAGR'].tolist() == CAGR_CHOT
    src = queries.revenue_phase(backend)
    # feedback PM 2026-10-02: mức R ghi gọn theo tỷ, mức chênh theo triệu (cùng số với PS4)
    assert tb['R năm đầu'].tolist() == [ty(v, 2) for v in src['r_start']]
    assert tb['R năm cuối'].tolist() == [ty(v, 2) for v in src['r_end']]
    assert tb['Chênh R'].tolist() == [trieu(v, 1, signed=True) for v in src['delta_r']]
    assert tb['Tổng thay đổi'].tolist() == [pct(v, 1, signed=True) for v in src['total_change_rate']]
    assert tb['Năm'].tolist() == ['2013→2016', '2016→2018', '2018→2019', '2019→2022']


@pytest.mark.parametrize('backend', BACKENDS)
def test_ba_diem_doi_huong_dung_so_chot(monkeypatch, backend):
    td = _ps2(monkeypatch, backend).dataframe[3].value
    assert td['Điểm'].tolist() == ['Cuối 2016', 'Cuối 2018', 'Cuối 2019']
    assert td['Độ lớn'].tolist() == DO_LON_CHOT
    # BA 2026-09-27: cuối 2019 "đổi nhịp"; PM 2026-09-28: cuối 2018 "giảm tăng tốc"
    assert td['Ghi chú của BA'].tolist() == ['', 'giảm tăng tốc', 'đổi nhịp']
    # đối chiếu với dữ liệu tự tìm (bổ sung sau góp ý M2): chỉ cuối 2016 là đổi hướng thật; 2018, 2019 là đổi tốc độ
    assert td['Dữ liệu tự tìm thấy?'].tolist() == ['08/2016 (phát hiện 02/2017)', 'không', 'không']
    src = queries.revenue_turning_point(backend)
    assert td['R 12 tháng trước'].tolist() == [ty(v, 2) for v in src['r_12m_before']]
    assert td['R 12 tháng sau'].tolist() == [ty(v, 2) for v in src['r_12m_after']]


def test_cach_doc_theo_quy_tac_ps2(monkeypatch):
    at = _ps2(monkeypatch, 'duckdb')
    text = ' '.join(m.value for m in at.markdown)
    assert 'Năm 2022 R tăng +12,3%' in text and 'tín hiệu hồi phục cuối giai đoạn D' in text   # quy tắc 5
    assert '−4,1' not in text and '−4,14' not in text   # quy tắc 6: không có một con số cho cả 10 năm
    assert 'PS4' in text and 'PS5' in text              # quy tắc 7: giai đoạn không phải nguyên nhân
    cap = ' '.join(c.value for c in at.caption)
    assert 'Đường bắt đầu từ 07/2013' in cap and 'đoạn trước 12/2013 không thuộc giai đoạn BA nào' in cap


@pytest.mark.parametrize('backend', BACKENDS)
def test_du_lieu_tu_tim_thang_doi_huong(monkeypatch, backend):
    # góp ý M2 (2026-09-28), deck slide 6 yêu cầu 4: tìm tháng đường R 12 tháng đổi hướng, hướng mới có kéo dài không
    at = _ps2(monkeypatch, backend)
    tc = at.dataframe[1].value
    assert tc['Khoảng so'].tolist() == ['3 tháng', '3 tháng', '6 tháng (chính)', '6 tháng (chính)', '9 tháng', '9 tháng']
    assert tc['Chuyển'].tolist() == ['lên → xuống', 'xuống → lên'] * 3
    assert tc['Đỉnh / đáy R 12 tháng'].tolist() == ['đỉnh 08/2016', 'đáy 10/2021'] * 3    # không đổi theo khoảng so
    assert tc['Tháng phát hiện'].tolist() == ['11/2016', '12/2021', '02/2017', '02/2022', '05/2017', '05/2022']
    assert tc['Hướng mới giữ'].tolist() == ['61 tháng', '13 tháng (tới hết dữ liệu)', '60 tháng',
                                            '11 tháng (tới hết dữ liệu)', '60 tháng', '8 tháng (tới hết dữ liệu)']
    src = queries.direction_change(backend)
    assert tc['R 12 tháng tại đó'].tolist() == [ty(v, 2) for v in src['extreme_r_12m']]
    summary = at.dataframe[0].value
    assert summary['Khoảng so'].tolist() == ['3 tháng', '6 tháng (chính)', '9 tháng']
    assert summary['Đỉnh → phát hiện'].tolist() == ['08/2016 → 11/2016', '08/2016 → 02/2017', '08/2016 → 05/2017']
    assert any('không phải tín hiệu đã biết ngay tại đỉnh/đáy' in c.value for c in at.caption)


def test_yoy_thang_co_tren_ps2(monkeypatch):
    at = _ps2(monkeypatch, 'duckdb')
    assert any(s.value == 'Tăng trưởng R theo năm so với năm trước' for s in at.subheader)
    year_chart = json.loads(at.get('vega_lite_chart')[1].proto.spec)
    assert year_chart['layer'][0]['encoding']['x']['field'] == 'nam'
    at.segmented_control[0].set_value('Cùng tháng năm trước').run()
    assert not at.exception
    assert any(s.value == 'Tăng trưởng R theo tháng so với cùng tháng năm trước' for s in at.subheader)
    month_chart = json.loads(at.get('vega_lite_chart')[1].proto.spec)
    assert any(layer.get('encoding', {}).get('x', {}).get('field') == 'month_start_date'
               for layer in month_chart['layer'])
    assert any('từ 08/2013' in c.value for c in at.caption)
    assert any('không phải tháng liền trước' in c.value for c in at.caption)
    assert not any(s.value == 'Tăng trưởng R theo năm so với năm trước' for s in at.subheader)
    gioi_han = ' '.join(m.value for m in at.markdown)
    assert 'ps2_direction_rule' in gioi_han and 'đổi tốc độ' in gioi_han


def test_lop_danh_dau_tren_bieu_do_co_the_tat(monkeypatch):
    at = _ps2(monkeypatch, 'duckdb')
    main_chart = json.loads(at.get('vega_lite_chart')[0].proto.spec)
    assert len(main_chart['layer']) == 5  # nền BA, đường R, vạch BA, chấm BA, đỉnh/đáy

    at.multiselect[0].set_value([]).run()
    assert not at.exception and not at.error
    main_chart = json.loads(at.get('vega_lite_chart')[0].proto.spec)
    assert len(main_chart['layer']) == 2  # chỉ còn nền BA và đường R
    assert not any('nét đứt và chấm đỏ = mốc BA' in c.value for c in at.caption)
