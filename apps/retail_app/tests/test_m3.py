"""M3: trang PS3 (docs/gd2_app_plan.md §6).

Tiêu chí: tháng 8 năm lẻ/chẵn = −37,7%; mức dồn cuối tháng (eom_excess) > 0, trên cả hai backend.
Số trên trang là cột của rpt_august_parity / rpt_revenue_total / rpt_revenue_yearly / rpt_revenue_monthly.
"""
import json
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from dwh import queries
from ui.fmt import num, pct, pp

APP = Path(__file__).resolve().parents[1] / 'app.py'
BACKENDS = ['postgres', 'duckdb']


def _ps3(monkeypatch, backend):
    monkeypatch.setenv('RETAIL_BACKEND', backend)
    st.cache_data.clear()
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    at.switch_page('views/ps3_nhip_lich.py').run()
    assert not at.exception and not at.error
    return at


@pytest.mark.parametrize('backend', BACKENDS)
def test_the_kpi_dung_tieu_chi_m3(monkeypatch, backend):
    the = [(m.label, m.value) for m in _ps3(monkeypatch, backend).metric]
    # PM 2026-09-28: thẻ 2 cũ ("−39,1% đến −36,2%") bị cắt chữ → mỗi thẻ một số ngắn, khoảng bỏ-từng-năm vào ô "?"
    assert the == [('Tháng 8 năm lẻ / chẵn (2013–2022)', '−37,7%'),
                   ('Chênh mùa cao / thấp (2013–2022)', '3,39 lần'),
                   ('Mức dồn về cuối tháng (2013–2022)', '+7,2 điểm %')]
    assert all(len(v) <= 12 for _, v in the)                     # số ngắn, không bị cắt ở màn hình hẹp
    assert the[1][1] == num(queries.calendar_stability(backend).set_index('rhythm_code').loc['mua_vu', 'metric_value'],
                            2) + ' lần'
    ky = queries.revenue_total(backend).set_index('period_code').loc['2013-2022']
    assert ky['eom_excess'] > 0                                  # tiêu chí M3
    assert the[2][1] == pp(ky['eom_excess'])


@pytest.mark.parametrize('backend', BACKENDS)
def test_bang_nam_doc_tu_rpt(monkeypatch, backend):
    tb = _ps3(monkeypatch, backend).dataframe[2].value      # [0] độ ổn định, [1] giai đoạn, [2] theo năm
    assert tb['Năm'].tolist() == list(range(2013, 2023))
    # PM 2026-09-28: ghi giai đoạn PS2 cạnh mỗi năm; năm ranh giới thuộc cả hai giai đoạn
    assert tb['Giai đoạn'].tolist() == ['A', 'A', 'A', 'A/B', 'B', 'B/C', 'C/D', 'D', 'D', 'D']
    y = queries.revenue_yearly(backend).set_index('year').loc[2013:2022]
    assert tb['Chênh mùa cao / thấp'].tolist() == [num(v, 2) + ' lần' for v in y['season_peak_trough_ratio']]
    assert tb['Tỷ trọng ngày ≥ 26'].tolist() == [pct(v) for v in y['eom_share']]
    assert tb['Mức dồn cuối tháng'].tolist() == [pp(v) for v in y['eom_excess']]
    assert all(v > 0 for v in y['eom_excess'])                  # năm nào cũng dồn về cuối tháng
    m = queries.revenue_monthly(backend)
    t8 = m[(m['month'] == 8) & m['is_analysis_period']]
    assert tb['Chỉ số tháng 8'].tolist() == [num(v, 2) for v in t8['month_index']]
    assert tb['Chỉ số tháng 8'].tolist() == ['0,88', '1,32', '0,79', '1,36', '0,76', '1,33', '0,89', '1,45', '0,83', '1,21']


def test_thang_8_nam_le_luon_thap_hon(monkeypatch):
    cap = ' '.join(c.value for c in _ps3(monkeypatch, 'duckdb').caption)
    assert 'Năm lẻ cao nhất 0,89, năm chẵn thấp nhất 1,21: năm lẻ nào cũng thấp hơn mọi năm chẵn.' in cap


def test_bang_nhiet_co_nhan_giai_doan(monkeypatch):
    at = _ps3(monkeypatch, 'duckdb')
    assert any('Cạnh mỗi năm là giai đoạn ở trang PS2' in c.value for c in at.caption)


@pytest.mark.parametrize('backend', BACKENDS)
def test_do_on_dinh_ca_ba_nhip(monkeypatch, backend):
    # góp ý M3 (2026-09-28): kiểm độ ổn định cho cả 3 nhịp, không chỉ tháng 8
    ts = _ps3(monkeypatch, backend).dataframe[0].value
    assert ts['Cả 10 năm'].tolist() == ['3,39 lần', '+7,2 điểm %', '−37,7%']
    assert ts['Bỏ lần lượt từng năm'].tolist() == ['3,22 lần đến 3,49 lần', '+7,1 điểm % đến +7,3 điểm %',
                                                   '−39,1% đến −36,2%']
    assert ts['Số năm tự có nhịp'].tolist() == ['10/10'] * 3
    s = queries.calendar_stability(backend)
    assert ts['Cả 10 năm'].tolist()[1] == pp(s['metric_value'][1])


@pytest.mark.parametrize('backend', BACKENDS)
def test_so_sanh_giai_doan(monkeypatch, backend):
    # góp ý M3: so sánh nhịp giữa các giai đoạn, năm ranh giới tính cho giai đoạn kết thúc ở năm đó
    at = _ps3(monkeypatch, backend)
    tp = at.dataframe[1].value
    assert tp['Giai đoạn'].tolist() == ['A. Tăng trưởng (2013–2016)', 'B. Chững, giảm nhẹ (2017–2018)', 'C. Sập (2019)',
                                        'D. Đi ngang mức thấp (2020–2022)']
    assert tp['Chênh mùa cao / thấp'].tolist() == ['2,91 lần', '4,52 lần', '3,71 lần', '3,54 lần']
    assert tp['Chênh T8 lẻ / chẵn'].tolist() == ['−37,3%', '−43,0%', '–', '−37,6%']
    c = queries.calendar_phase(backend)
    assert tp['Mức dồn cuối tháng'].tolist() == [pp(v) for v in c['eom_excess']]
    nx = ' '.join(m.value for m in at.markdown if 'Nhận xét so sánh' in m.value)
    assert 'Mùa vụ mạnh nhất ở B (4,52 lần), yếu nhất ở A (2,91 lần).' in nx
    assert 'C không so được vì chỉ có năm lẻ' in nx
    # góp ý lần 2: quy ước chia năm là riêng của PS3, chưa chốt, không đồng nhất với nền PS2
    cap = ' '.join(c.value for c in at.caption)
    assert 'Quy ước riêng của phần so sánh này (chưa được BA chốt)' in cap
    assert 'giống nền màu' not in cap


def test_chu_thich_muc_don_cuoi_thang(monkeypatch):
    # góp ý M3: nói rõ mức so sánh = rải đều trong từng tháng, giữ nguyên doanh thu tháng
    help_ = _ps3(monkeypatch, 'duckdb').metric[2].help
    assert 'rải đều theo ngày trong từng tháng, giữ nguyên doanh thu mỗi tháng' in help_


def _thang_mau(at, field):
    """Thang màu (scale) của các lớp bảng nhiệt tô theo `field`, đọc từ spec Vega-Lite mà trang gửi ra trình duyệt."""
    out = []
    for c in at.get('vega_lite_chart'):
        for lop in json.loads(c.proto.spec).get('layer', []):
            mau = lop.get('encoding', {}).get('color', {})
            if mau.get('field') == field:
                out.append(mau)
    return out


@pytest.mark.parametrize('backend', BACKENDS)
def test_hai_bang_nhiet_chi_so_thang_chung_thang_mau(monkeypatch, backend):
    # feedback 2026-10-01 (F04): cùng giá trị month_index phải ra cùng màu ở bảng theo năm và bảng theo giai đoạn
    at = _ps3(monkeypatch, backend)
    nam, gd = _thang_mau(at, 'month_index')
    assert nam['scale'] == gd['scale']                                   # cùng scheme, miền, điểm giữa → cùng màu
    lo, hi = nam['scale']['domain']
    assert nam['scale']['domainMid'] == 1 and abs((1 - lo) - (hi - 1)) < 1e-9     # đối xứng quanh 1
    m = queries.revenue_monthly(backend)
    m = m[m['is_analysis_period']]['month_index']
    p = queries.calendar_phase_month(backend)['month_index']
    assert lo <= min(m.min(), p.min()) and hi >= max(m.max(), p.max())   # không ô nào nằm ngoài miền (bão hòa màu)
    assert hi - 1 == pytest.approx(max((m - 1).abs().max(), (p - 1).abs().max()))   # miền vừa khít, lấy từ dữ liệu
    # chú giải hiện, ghi rõ mẫu số của từng bảng
    assert nam['legend']['title'] == 'Chỉ số tháng (1 = TB tháng của năm đó)'
    assert gd['legend']['title'] == 'Chỉ số tháng (1 = TB tháng của giai đoạn đó)'
    cap = ' '.join(c.value for c in at.caption)
    assert '**dùng chung một thang màu**' in cap and '1 = TB tháng của cả giai đoạn' in cap
    # bảng mức dồn cuối tháng: thang riêng theo điểm %, tâm 0
    (eom,) = _thang_mau(at, 'eom_excess')
    assert eom['scale'] == {'domainMid': 0, 'scheme': 'redblue'} and 'điểm %' in eom['legend']['title']
