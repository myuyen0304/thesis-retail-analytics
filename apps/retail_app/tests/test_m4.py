"""M4: trang PS4 + PS5 (docs/gd2_app_plan.md §6).

Tiêu chí: thác 2019 contrib_n = −572,4 triệu; ba phần cộng lại = ΔR; PS5 không có chỗ nào cộng 3 chiều.
Plan §3 tiêu chí 4: PS4, PS5 có câu cảnh báo lấy từ slide 10 và 12.
Số trên trang là cột của rpt_driver_period / rpt_driver_bridge / rpt_revenue_segment_yearly / rpt_revenue_yearly.
"""
import json
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from dwh import queries
from ui.fmt import num, pct, trieu

APP = Path(__file__).resolve().parents[1] / 'app.py'
BACKENDS = ['postgres', 'duckdb']


def _page(monkeypatch, backend, page):
    monkeypatch.setenv('RETAIL_BACKEND', backend)
    st.cache_data.clear()
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    at.switch_page(page).run()
    assert not at.exception and not at.error
    return at


def _ps4(monkeypatch, backend='duckdb'):
    return _page(monkeypatch, backend, 'views/ps4_don_mon_gia.py')


def _ps5(monkeypatch, backend='duckdb'):
    return _page(monkeypatch, backend, 'views/ps5_nhom.py')


def _chieu(at):
    return next(r for r in at.radio if r.label.startswith('Chiều'))


# ---------------- PS4 ----------------

@pytest.mark.parametrize('backend', BACKENDS)
def test_ps4_the_2019_dung_tieu_chi_m4(monkeypatch, backend):
    at = _ps4(monkeypatch, backend)
    the = [(m.label, m.value) for m in at.metric]
    assert the == [('Thay đổi doanh thu R', '−554,9 triệu'), ('Tác động của số đơn N', '−572,4 triệu'),
                   ('Tác động của số món/đơn U', '+2,6 triệu'), ('Tác động của giá/món P', '+14,9 triệu')]
    d = queries.driver_period(backend).set_index('period_code').loc['2019']
    assert [v for _, v in the] == [trieu(d[c], 1, signed=True) for c in ['delta_r', 'contrib_n', 'contrib_u', 'contrib_p']]
    # dòng nhỏ dưới số: % đổi của chính yếu tố (cột dbt *_change_rate) và giá trị đầu → cuối
    phu = [(m.proto.delta, m.proto.delta_description) for m in at.metric]
    # dòng phụ ghi tên yếu tố (R/N/U/P) để % đọc ra là % đổi của chính yếu tố đó
    assert phu == [('−39,1%', 'R: 1.419 → 864 triệu'), ('−40,3%', 'N: 55.740 → 33.259 đơn'),
                   ('+0,3%', 'U: 4,85 → 4,87 món/đơn'), ('+1,8%', 'P: 5.249 → 5.341 mỗi món')]
    assert [a for a, _ in phu] == [pct(d[c], 1, signed=True) for c in ['r_change_rate', 'n_change_rate', 'u_change_rate',
                                                                         'p_change_rate']]
    assert at.title[0].value == 'PS4 · Số đơn, số món và giá'
    assert any('Đang so sánh: Năm 2019 so với 2018' in c.value for c in at.caption)
    assert any('không phải tỷ trọng đóng góp' in c.value for c in at.caption)
    assert any('có thể lệch 0,1 triệu' in c.value for c in at.caption)
    assert any('**R giảm:** 554,9 triệu (−39,1%)' in m.value for m in at.markdown)
    assert any('**Giảm lớn nhất:** số đơn N (giảm 40,3%, làm R −572,4 triệu)' in m.value
               for m in at.markdown)
    assert any('**Phần tăng/bù đắp:** giá mỗi món P (tăng 1,8%, làm R +14,9 triệu)' in m.value
               for m in at.markdown)
    assert [t.label for t in at.tabs] == ['So sánh theo năm', 'So sánh theo giai đoạn', 'Chỉ số N/U/P/AOV']
    assert any(e.label == 'Xem số liệu làm căn cứ' for e in at.expander)
    # ba phần cộng lại = ΔR: kiểm trên cột dbt, không cộng số đã làm tròn trên trang
    assert abs(d['contrib_n'] + d['contrib_u'] + d['contrib_p'] - float(d['delta_r'])) < 0.01
    y = queries.revenue_yearly(backend).set_index('year').loc[2019]
    assert abs(float(d['delta_r']) - float(y['delta_r'])) < 0.005


def test_ps4_canh_bao_slide_10(monkeypatch):
    at = _ps4(monkeypatch)
    assert any('Phân rã theo thứ tự N → U → P; thể hiện đóng góp số học, chưa chứng minh nguyên nhân.'
               in w.value for w in at.warning)


@pytest.mark.parametrize('backend', BACKENDS)
def test_ps4_thac_doc_tu_bridge(monkeypatch, backend):
    tb = _ps4(monkeypatch, backend).dataframe[0].value
    assert tb['Cột'].tolist() == ['R 2018', 'Số đơn N', 'Số món mỗi đơn U', 'Giá mỗi món P', 'R 2019']
    b = queries.driver_bridge(backend)
    b = b[(b['period_code'] == '2019') & (b['bridge_code'] == 'r_nup')]
    # feedback PM 2026-10-02: bảng ghi gọn (triệu, 1 số lẻ), cùng số với nhãn cột
    assert tb['Số tiền'].tolist() == [trieu(a, 1, signed=c not in ('r_start', 'r_end')) for c, a in zip(b['step_code'], b['amount'])]
    assert tb['Số tiền'].tolist() == ['1.419,3 triệu', '−572,4 triệu', '+2,6 triệu', '+14,9 triệu', '864,3 triệu']


def test_ps4_chon_giai_doan(monkeypatch):
    at = _ps4(monkeypatch)
    at.selectbox[0].select('A').run()
    assert not at.exception
    assert at.dataframe[0].value['Cột'].tolist() == ['R 2013', 'Số đơn N', 'Số món mỗi đơn U', 'Giá mỗi món P', 'R 2016']
    assert [(m.label, m.value, m.proto.delta) for m in at.metric][:2] == [('Thay đổi doanh thu R', '+360,3 triệu', '+28,6%'),
                                                                          ('Tác động của số đơn N', '+94,0 triệu', '+7,3%')]
    assert at.metric[1].proto.delta_description == 'N: 61.588 → 66.067 đơn'
    assert any('Đang so sánh: Giai đoạn A.' in c.value for c in at.caption)
    assert any('**R tăng:** 360,3 triệu (+28,6%)' in m.value for m in at.markdown)
    assert any('Với giai đoạn, phần góp là tổng phần góp của từng năm' in m.value for m in at.markdown)


@pytest.mark.parametrize('backend', BACKENDS)
def test_ps4_so_sanh_giai_doan(monkeypatch, backend):
    at = _ps4(monkeypatch, backend)
    tp = at.dataframe[2].value
    assert tp['Giai đoạn'].tolist() == ['Giai đoạn A. Tăng trưởng (2013→2016)', 'Giai đoạn B. Chững, giảm nhẹ (2016→2018)',
                                        'Giai đoạn C. Sập (2018→2019)', 'Giai đoạn D. Đi ngang mức thấp (2019→2022)']
    assert tp['Kéo lên nhiều nhất'].tolist() == ['P', 'P', 'P', 'P']
    assert tp['Kéo xuống nhiều nhất'].tolist() == ['U', 'N', 'N', 'N']
    ph = queries.revenue_phase(backend)
    assert tp['R đổi'].tolist() == [trieu(v, 1, signed=True) for v in ph['delta_r']]   # khớp mức đổi R ở PS2
    nx = ' '.join(m.value for m in at.markdown if 'Nhận xét so sánh' in m.value)
    assert '- D: kéo lên nhiều nhất là giá mỗi món P (tăng 22,6%, làm R +160,3 triệu); kéo xuống nhiều nhất là số đơn N '            '(giảm 16,8%, làm R −145,8 triệu). ' \
           'Mức đổi R chỉ −3,7 triệu (dưới 1% R đầu giai đoạn) vì hai phần lớn bù trừ nhau.' in nx


def test_ps4_bang_nam_ghi_chu_nam_nho(monkeypatch):
    tn = _ps4(monkeypatch).dataframe[1].value
    assert tn['Năm'].tolist() == [str(y) for y in range(2014, 2023)]
    assert [n for n, g in zip(tn['Năm'], tn['Ghi chú']) if g] == ['2015']
    assert tn['Giai đoạn'].tolist() == ['A', 'A', 'A', 'B', 'B', 'C', 'D', 'D', 'D']   # năm Y thuộc giai đoạn có đầu < Y ≤ cuối


def test_ps4_doi_ky_cap_nhat_thac_va_giai_thich(monkeypatch):
    at = _ps4(monkeypatch)
    for code in ['D', '2017']:
        at.selectbox[0].select(code).run()
        assert not at.exception
        row = queries.driver_period('duckdb').set_index('period_code').loc[code]
        assert [m.value for m in at.metric] == [
            trieu(row[c], 1, signed=True) for c in ['delta_r', 'contrib_n', 'contrib_u', 'contrib_p']]
        tb = at.dataframe[0].value
        assert tb.iloc[0]['Số tiền'] == trieu(row['r_start'], 1)
        assert tb.iloc[-1]['Số tiền'] == trieu(row['r_end'], 1)
        text = ' '.join(m.value for m in at.markdown)
        assert f'**R {"tăng" if row["delta_r"] > 0 else "giảm"}:** {trieu(abs(row["delta_r"]), 1)}' in text
        if row['delta_r_is_small']:
            assert 'các phần ngược dấu bù trừ' in text
        if not isinstance(row['top_up_driver'], str):
            assert '**Phần tăng/bù đắp:**' not in text


@pytest.mark.parametrize('backend', BACKENDS)
def test_ps4_moi_ky_giu_dung_tong_phan_gop(monkeypatch, backend):
    periods = queries.driver_period(backend)
    for row in periods.itertuples():
        assert abs(row.contrib_n + row.contrib_u + row.contrib_p - row.delta_r) < 0.01


# ---------------- PS5 ----------------

def test_ps5_canh_bao_slide_12(monkeypatch):
    at = _ps5(monkeypatch)
    captions = ' '.join(x.value for x in at.caption)
    markdown = ' '.join(x.value for x in at.markdown)
    assert 'không cộng đóng góp giữa các chiều' in captions
    assert 'C giảm chưa đủ kết luận khách hàng rời bỏ' in captions
    assert 'Region là nhãn Central / East / West' in markdown
    assert 'chỉ là số học' in markdown


@pytest.mark.parametrize('backend', BACKENDS)
def test_ps5_moi_lan_mot_chieu(monkeypatch, backend):
    # tiêu chí M4: không có chỗ nào cộng 3 chiều. Mỗi lựa chọn chỉ hiện đúng các nhóm của chiều đó, không có dòng "Tổng".
    at = _ps5(monkeypatch, backend)
    seg = queries.segment_yearly(backend)
    for dim in ['category', 'region', 'acquisition_channel']:
        _chieu(at).set_value(dim).run()
        assert not at.exception
        nhom = at.dataframe[0].value['Nhóm'].tolist()
        assert sorted(nhom) == sorted(seg[(seg['dimension_name'] == dim) & (seg['year'] == 2019)]['dimension_value'])
        assert not any('tổng' in str(n).lower() for n in nhom)
        chart = json.loads(at.get('vega_lite_chart')[0].proto.spec)
        assert set(chart['layer'][1]['encoding']['y']['sort']) == set(nhom)
        name = {'category': 'Ngành hàng', 'region': 'Khu vực', 'acquisition_channel': 'Kênh thu hút khách'}[dim]
        assert any(f'R · {name}' in c.value for c in at.caption)
        assert seg[(seg['dimension_name'] == dim) & (seg['year'] == 2019)]['delta_r'].sum() == pytest.approx(
            queries.revenue_yearly(backend).set_index('year').loc[2019, 'delta_r'], abs=1e-5)


def test_ps5_bo_cuc_bieu_do_va_bang_chi_tiet(monkeypatch):
    at = _ps5(monkeypatch)
    assert [t.label for t in at.tabs] == ['Tỷ trọng qua năm', 'Khách hàng & tần suất', 'Bảng số liệu']
    assert [e.label for e in at.get('expander')] == [
        'Định nghĩa & phạm vi dữ liệu', 'Xem số liệu làm căn cứ', 'Xem bảng C/F theo năm',
        'Xem bảng chi tiết theo nhóm', 'Cách đọc & phương pháp', 'Giới hạn chi tiết',
        'Nguồn dữ liệu & kết nối']
    assert len(at.get('vega_lite_chart')) == 3
    chart = json.loads(at.get('vega_lite_chart')[0].proto.spec)
    assert chart['layer'][0]['mark']['type'] == 'rule'  # mốc 0
    assert chart['layer'][1]['encoding']['color']['scale']['domain'] == ['Tăng', 'Giảm', 'Không đổi']
    assert chart['layer'][1]['encoding']['y']['sort'] == ['Streetwear', 'Outdoor', 'GenZ', 'Casual']
    assert chart['layer'][3]['encoding']['x']['field'] == 'moc_nhan'  # nhãn âm không đè tên nhóm trên mobile
    assert len(at.dataframe) == 3  # bảng căn cứ ngắn, bảng C/F, bảng nhóm đầy đủ
    assert 'Hạng' not in at.dataframe[0].value
    assert 'Hạng' in at.dataframe[2].value


@pytest.mark.parametrize('backend', BACKENDS)
def test_ps5_doi_soat_tat_ca_chieu_nam_va_c_f(backend):
    seg = queries.segment_yearly(backend).dropna(subset=['delta_r'])
    yearly = queries.revenue_yearly(backend).set_index('year')
    for (_, year), rows in seg.groupby(['dimension_name', 'year']):
        assert rows['delta_r'].sum() == pytest.approx(yearly.loc[year, 'delta_r'], abs=1e-5)
        assert rows['n_groups_up'].iloc[0] == (rows['delta_r'] > 0).sum()
        assert rows['n_groups_down'].iloc[0] == (rows['delta_r'] < 0).sum()
    periods = queries.driver_period(backend)
    periods = periods[periods['period_type'] == 'year']
    for row in periods.itertuples():
        assert row.contrib_c + row.contrib_f == pytest.approx(row.delta_n, abs=1e-6)


@pytest.mark.parametrize('backend', BACKENDS)
def test_ps5_nganh_hang_2019(monkeypatch, backend):
    at = _ps5(monkeypatch, backend)
    assert [(m.label, m.value) for m in at.metric][:3] == [
        ('Thay đổi R toàn công ty', '−554,9 triệu'), ('Ngành hàng tăng nhiều nhất', 'Không có'),
        ('Ngành hàng giảm nhiều nhất', 'Streetwear')]
    # feedback 2026-10-01 (F03): thẻ nhóm có thêm số tiền (dòng màu) và % đóng góp (dòng phụ)
    assert (at.metric[2].proto.delta, at.metric[2].proto.delta_description) == ('−463,9 triệu',
                                                                                '83,6% tổng mức giảm')
    # "Không có" nhóm tăng: không gắn số tiền của nhóm giảm ít nhất. PM 2026-10-02: thẻ cùng khuôn với hai thẻ kia,
    # ô xám = số nhóm tăng (cột dbt n_groups_up / n_groups), dòng xám nói rõ mọi nhóm đều giảm
    assert (at.metric[1].proto.delta, at.metric[1].proto.delta_description) == ('0/4 nhóm tăng', 'Không có nhóm tăng')
    # thẻ đầu cùng khuôn: % đổi của R (cột yoy_rate) và R năm trước → năm nay
    assert (at.metric[0].proto.delta, at.metric[0].proto.delta_description) == ('−39,1%', 'R: 1.419 → 864 triệu')
    assert at.metric[3].value == '0 tăng / 4 giảm'
    tb = at.dataframe[2].value.set_index('Nhóm')
    assert tb.loc['Streetwear', '% đóng góp vào mức đổi tổng'] == '83,6%'
    assert tb.loc['Streetwear', 'Dịch chuyển tỷ trọng'] == '−1,03 điểm %'
    assert tb['Hạng'].tolist() == [1, 2, 3, 4]
    s = queries.segment_yearly(backend)
    s = s[(s['dimension_name'] == 'category') & (s['year'] == 2019)]
    assert tb['% đóng góp vào mức đổi tổng'].tolist() == [pct(v) for v in s['contribution_to_delta']]
    nx = ' '.join(m.value for m in at.markdown)
    assert 'Streetwear giảm 463,9 triệu' in nx
    assert '**R toàn công ty giảm** 554,9 triệu' in nx
    assert (s['n_groups_down'].iloc[0], s['n_groups'].iloc[0]) == (4, 4)      # số đếm đọc từ cột dbt


def test_ps5_nam_2015_khong_on_dinh(monkeypatch):
    at = _ps5(monkeypatch)
    at.selectbox[0].select(2015).run()
    assert not at.exception
    gop = at.dataframe[0].value['% đóng góp vào mức đổi tổng'].tolist()
    assert gop and all(g.endswith('(không ổn định)') for g in gop)
    assert any('dưới 1% R năm trước' in i.value for i in at.info)
    # F03: ΔR tổng rất nhỏ → thẻ nhóm vẫn hiện số tiền, nhưng KHÔNG đưa % đóng góp (vd. 400%) lên thẻ
    assert [(m.value, m.proto.delta, m.proto.delta_description) for m in at.metric][1:3] == [
        ('GenZ', '+6,8 triệu', '% góp không ổn định'), ('Outdoor', '−14,4 triệu', '% góp không ổn định')]


@pytest.mark.parametrize('backend', BACKENDS)
def test_ps5_the_nhom_doi_theo_nam_va_chieu(monkeypatch, backend):
    # F03: đổi năm / chiều thì tên nhóm, số tiền và dòng % trên thẻ đổi theo; số lấy từ cột dbt, không gõ tay
    at = _ps5(monkeypatch, backend)
    seg = queries.segment_yearly(backend)
    for nam in [2019, 2021, 2022]:
        at.selectbox[0].select(nam).run()
        for dim in ['category', 'region', 'acquisition_channel']:
            _chieu(at).set_value(dim).run()
            assert not at.exception
            s = seg[(seg['dimension_name'] == dim) & (seg['year'] == nam)].sort_values('delta_r_rank')
            tong = s['delta_r'].sum()
            for m, r, co in [(at.metric[1], s.iloc[0], s.iloc[0]['delta_r'] > 0),
                             (at.metric[2], s.iloc[-1], s.iloc[-1]['delta_r'] < 0)]:
                if not co:
                    huong = 'tăng' if m is at.metric[1] else 'giảm'
                    so = int(r['n_groups_up' if huong == 'tăng' else 'n_groups_down'])
                    assert (m.value, m.proto.delta) == ('Không có', f'{so}/{int(r["n_groups"])} nhóm {huong}')
                    assert m.proto.delta_description == f'Không có nhóm {huong}'
                    assert so == 0 and '%' not in m.proto.delta and 'triệu' not in m.proto.delta
                    continue
                assert m.value == r['dimension_value']
                assert m.proto.delta == trieu(r['delta_r'], 1, signed=True)
                # % giữ dấu: nhóm đi ngược chiều cả công ty có % âm, không ép về 0–100%
                assert m.proto.delta_description == (
                    '% góp không ổn định' if r['delta_r_is_small']
                    else f'{pct(r["contribution_to_delta"])} tổng mức {"giảm" if tong < 0 else "tăng"}')
    # 2021 ngành hàng: cả công ty giảm nhưng Casual tăng → % âm, giữ dấu
    at.selectbox[0].select(2021).run()
    _chieu(at).set_value('category').run()
    assert (at.metric[1].value, at.metric[1].proto.delta, at.metric[1].proto.delta_description) == (
        'Casual', '+6,2 triệu', '−15,3% tổng mức giảm')
    at.selectbox[0].select(2022).run()
    _chieu(at).set_value('acquisition_channel').run()
    # 2022 mọi nhóm đều tăng: thẻ "giảm nhiều nhất" là "Không có"
    assert at.metric[2].value == 'Không có' and at.metric[2].proto.delta_description == 'Không có nhóm giảm'
    assert at.metric[1].value == 'organic_search'
    d = queries.driver_period(backend).set_index('period_code').loc['2022']
    assert at.metric[4].value == num(d['delta_n'], 0, signed=True) + ' đơn'
    bridge = json.loads(at.get('vega_lite_chart')[2].proto.spec)
    assert bridge['layer'][0]['encoding']['x']['sort'][0] == 'N 2021'
    assert bridge['layer'][0]['encoding']['x']['sort'][-1] == 'N 2022'


def test_ps5_the_nhom_mau_so_0(monkeypatch):
    # F03: ΔR cả công ty = 0 → % đóng góp NULL (dbt) → thẻ ghi "không xác định", không in "–" hay 0%
    goc = queries.segment_yearly

    def sua(backend):
        s = goc(backend)
        o = (s['dimension_name'] == 'category') & (s['year'] == 2019)
        s.loc[o, 'contribution_to_delta'] = float('nan')
        return s

    monkeypatch.setattr(queries, 'segment_yearly', sua)
    at = _ps5(monkeypatch)
    assert at.metric[2].proto.delta_description == '% góp không xác định'
    assert 'Không xác định nếu R không đổi' in at.metric[2].help


def test_ps5_khong_nhom_nao_doi(monkeypatch):
    """Mẫu không đổi phải cho cả hai thẻ nhóm trạng thái rỗng, không chọn sai cực trị."""
    old_seg, old_yearly = queries.segment_yearly, queries.revenue_yearly

    def zero_seg(backend):
        s = old_seg(backend)
        mask = (s['dimension_name'] == 'category') & (s['year'] == 2019)
        s.loc[mask, 'r'] = s.loc[mask, 'r_prior_year']
        s.loc[mask, 'delta_r'] = 0.0
        s.loc[mask, 'contribution_to_delta'] = float('nan')
        s.loc[mask, 'n_groups_up'] = 0
        s.loc[mask, 'n_groups_down'] = 0
        s.loc[mask, 'delta_r_is_small'] = True
        return s

    def zero_yearly(backend):
        y = old_yearly(backend)
        mask = y['year'] == 2019
        y.loc[mask, 'r'] = y.loc[mask, 'r_prior_year']
        y.loc[mask, 'delta_r'] = 0.0
        y.loc[mask, 'yoy_rate'] = 0.0
        return y

    monkeypatch.setattr(queries, 'segment_yearly', zero_seg)
    monkeypatch.setattr(queries, 'revenue_yearly', zero_yearly)
    at = _ps5(monkeypatch)
    assert [m.value for m in at.metric[:4]] == [
        '+0,0 triệu', 'Không có', 'Không có', '0 tăng / 0 giảm']
    assert [m.proto.delta_description for m in at.metric[1:3]] == ['Không có nhóm tăng', 'Không có nhóm giảm']
    assert 'không nhóm nào thay đổi R' in ' '.join(m.value for m in at.markdown)
    assert set(at.dataframe[0].value['Thay đổi R']) == {'+0,0 triệu'}
    assert set(at.dataframe[0].value['% đóng góp vào mức đổi tổng']) == {'Không xác định'}


@pytest.mark.parametrize('backend', BACKENDS)
def test_ps5_c_f_2019(monkeypatch, backend):
    at = _ps5(monkeypatch, backend)
    assert [m.value for m in at.metric][4:] == ['−22.481 đơn', '−16.578 đơn', '−5.903 đơn']
    # review 2026-09-29: phần C/F là số toàn công ty, không theo chiều đang chọn → nhãn phải nói rõ phạm vi
    # PM 2026-10-09: nhãn dài bị cắt "…" → nhãn thẻ rút gọn; phạm vi toàn công ty ở tiêu đề, chú thích và help
    assert at.metric[4].label == 'Số đơn đổi (2018→2019)'
    assert 'Số đơn toàn công ty' in at.metric[4].help
    assert any(s.value.startswith('Số đơn toàn công ty, năm 2019') for s in at.subheader)
    assert any('Không chia theo ngành hàng đang chọn' in c.value for c in at.caption)
    d = queries.driver_period(backend).set_index('period_code').loc['2019']
    assert abs(d['contrib_c'] + d['contrib_f'] - d['delta_n']) < 1e-6          # C + F = ΔN, trên cột dbt
    tc = at.dataframe[1].value
    assert tc['Năm'].tolist() == [str(y) for y in range(2014, 2023)]
