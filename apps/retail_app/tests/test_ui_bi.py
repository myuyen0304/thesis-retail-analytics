"""Khung giao diện ui/bi.py trên các trang PS1–PS5: phần test cũ (test_m1–m4, test_b8_ai_trang) chưa phủ.

Số kỳ vọng đọc từ query reporting (dwh/queries.py), không ghi cứng. Không gọi mô hình AI thật.
"""
import json
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from dwh import queries
from ui import roles
from ui.fmt import num, pct, trieu

APP = Path(__file__).resolve().parents[1] / 'app.py'
PS4 = 'views/ps4_don_mon_gia.py'


def _ps4(monkeypatch):
    monkeypatch.setenv('RETAIL_BACKEND', 'duckdb')
    st.cache_data.clear()
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    at.switch_page(PS4).run()
    assert not at.exception and not at.error
    return at


def _links(at) -> dict:
    return {pl.proto.label: pl.proto.page for pl in at.get('page_link')}


def _thac(at) -> dict:
    """Spec Vega-Lite của biểu đồ thác: biểu đồ đầu tiên của trang."""
    return json.loads(at.get('vega_lite_chart')[0].proto.spec)


def test_truc_thac_dung_thu_tu_moi_lop(monkeypatch):
    # Bản đầu có lớp đường nối dùng field riêng: Vega-Lite bỏ sort, cột xếp theo ABC (P, U, R 2018, R 2019, N).
    # Test số liệu không thấy lỗi này, chỉ lộ khi chụp màn hình, nên khóa ngay trên spec.
    spec = _thac(_ps4(monkeypatch))
    thu_tu = ['R 2018', 'Số đơn N', 'Món/đơn U', 'Giá/món P', 'R 2019']
    assert len(spec['layer']) == 3
    for lop in spec['layer']:
        assert lop['encoding']['x']['field'] == 'Nhãn' and lop['encoding']['x']['sort'] == thu_tu


def test_thac_giu_goc_0_cho_cot_tong(monkeypatch):
    # Ảnh tham chiếu cắt trục ở 1.000, làm mức đổi trông lớn hơn thật; trang giữ cột tổng từ 0 như cột dbt.
    b = queries.driver_bridge('duckdb')
    b = b[(b['period_code'] == '2019') & (b['bridge_code'] == 'r_nup')]
    tong = b[b['step_code'].isin(['r_start', 'r_end'])]
    assert (tong['bar_start'] == 0).all()
    spec = _thac(_ps4(monkeypatch))
    assert 'scale' not in spec['layer'][1]['encoding']['y']        # không đặt domain riêng


@pytest.mark.parametrize('code', ['2019', '2015', '2017', 'A', 'D'])
def test_bang_doi_chung_dung_so_kho_theo_ky(monkeypatch, code):
    at = _ps4(monkeypatch)
    at.selectbox[0].select(code).run()
    assert not at.exception
    d = queries.driver_period('duckdb').set_index('period_code').loc[code]
    t = at.table[0].value
    s0, s1 = str(int(d['start_year'])), str(int(d['end_year']))
    assert list(t.columns) == ['Thành phần', s0, s1, 'Tác động lên R', 'Biến động yếu tố']
    assert t[s0].tolist() == [num(d['r_start'] / 1e6, 1), num(d['n_start']), num(d['u_start'], 2), num(d['p_start'])]
    assert t[s1].tolist() == [num(d['r_end'] / 1e6, 1), num(d['n_end']), num(d['u_end'], 2), num(d['p_end'])]
    assert t['Tác động lên R'].tolist() == [trieu(d[c], 1, signed=True) for c in ['delta_r', 'contrib_n', 'contrib_u', 'contrib_p']]
    assert t['Biến động yếu tố'].tolist() == [pct(d[c], 1, signed=True) for c in ['r_change_rate', 'n_change_rate',
                                                                                  'u_change_rate', 'p_change_rate']]


def test_doi_chieu_ba_phan_cong_bang_delta_r():
    b = queries.driver_bridge('duckdb')
    p = queries.driver_period('duckdb').set_index('period_code')
    for code, g in b[b['bridge_code'] == 'r_nup'].groupby('period_code'):
        phan = g[g['step_code'].isin(['n', 'u', 'p'])]['amount'].sum()
        assert abs(phan - p.loc[code, 'delta_r']) < 0.01, code


def test_bon_khoi_va_cau_hoi_nghiep_vu(monkeypatch):
    at = _ps4(monkeypatch)
    text = ' '.join(s.value for s in at.subheader)
    for so, ten in [('01', 'Doanh thu thay đổi chủ yếu ở thành phần nào?'), ('02', 'Từ R 2018 đến R 2019 (triệu đồng)'),
                    ('03', 'AI giải thích'), ('04', 'Kiểm tra tiếp')]:
        assert f':violet-badge[{so}] {ten}' in text


@pytest.mark.parametrize('code, phan, tong', [('2019', 'contrib_n', 'delta_r'), ('2016', 'contrib_p', 'delta_r')])
def test_cau_tra_loi_dung_phan_chinh_cua_dbt(monkeypatch, code, phan, tong):
    at = _ps4(monkeypatch)
    at.selectbox[0].select(code).run()
    d = queries.driver_period('duckdb').set_index('period_code').loc[code]
    cau = next(m.value for m in at.markdown if m.value.startswith('#### '))
    assert 'nhiều nhất' in cau
    assert trieu(d[phan], 1, signed=True) in cau and trieu(d[tong], 1, signed=True) in cau


def test_cau_tra_loi_khi_r_gan_nhu_khong_doi_noi_bu_tru(monkeypatch):
    at = _ps4(monkeypatch)
    at.selectbox[0].select('D').run()
    d = queries.driver_period('duckdb').set_index('period_code').loc['D']
    cau = next(m.value for m in at.markdown if m.value.startswith('#### '))
    assert 'gần như không đổi' in cau and 'bù trừ' in cau and 'nhiều nhất' not in cau
    assert trieu(d['delta_r'], 1, signed=True) in cau


@pytest.mark.parametrize('code, trang_5, chu', [
    ('2019', 'ps5_nhom', 'Số đơn N đổi'),                     # phần chính là N → hỏi số khách / tần suất
    ('2016', 'ps5_nhom', 'Giá mỗi món P đổi'),                # phần chính là P → hỏi ngành hàng
    ('2015', 'ps5_nhom', 'R đổi rất ít'),                     # ΔR nhỏ → hỏi nhóm bù trừ
    ('D', 'ps5_nhom', 'R đổi rất ít'),
])
def test_cau_hoi_theo_ky(monkeypatch, code, trang_5, chu):
    at = _ps4(monkeypatch)
    at.selectbox[0].select(code).run()
    assert not at.exception
    assert any(chu in m.value for m in at.markdown)
    nhan = [pl.proto.label for pl in at.get('page_link')]
    assert sum(roles.PAGES[trang_5][1] in x for x in nhan) == 1
    assert sum(roles.PAGES['ps2_xu_huong'][1] in x for x in nhan) == 1
    assert sum(roles.PAGES['ps3_nhip_lich'][1] in x for x in nhan) == 1


def test_giai_doan_noi_ro_ps5_chi_so_tung_nam(monkeypatch):
    at = _ps4(monkeypatch)
    at.selectbox[0].select('A').run()
    assert any('năm 2016 so với 2015 (năm cuối giai đoạn; PS5 so từng năm)' in pl.proto.help for pl in at.get('page_link'))


def test_nam_cua_ps4_deu_mo_duoc_o_ps5():
    # Link ?nam= chỉ đúng nhãn khi PS5 có năm đó; url_choice sẽ về mặc định và nhãn thành sai nếu không có.
    seg = queries.segment_yearly('duckdb')
    co_ps5 = set(seg[seg['delta_r_rank'].notna()]['year'].astype(int))
    assert set(queries.driver_period('duckdb')['end_year'].astype(int)) <= co_ps5


def test_tham_so_link_ps5_mo_dung_lua_chon(monkeypatch):
    # Giả lập bấm link: PS5 phải đọc đúng tham số do mục 04 của PS4 đưa sang.
    monkeypatch.setenv('RETAIL_BACKEND', 'duckdb')
    st.cache_data.clear()
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.query_params['nam'] = '2016'
    at.query_params['chieu'] = 'category'
    at.run()
    at.switch_page('views/ps5_nhom.py').run()
    assert not at.exception and not at.error
    assert any('Ngành hàng · 2015 → 2016' in c.value for c in at.caption)


def test_trang_khong_thuoc_quyen_thi_bo_ca_cau_hoi(monkeypatch):
    con = tuple(k for k in roles.PAGES_BY_ROLE['admin'] if k != 'ps3_nhip_lich')
    monkeypatch.setitem(roles._PAGE_CHOICES, 'admin', con)
    at = _ps4(monkeypatch)
    assert not any(roles.PAGES['ps3_nhip_lich'][1] in x for x in _links(at))
    assert not any('tháng 8 năm lẻ' in m.value for m in at.markdown)
    assert any(roles.PAGES['ps2_xu_huong'][1] in x for x in _links(at))


def test_khong_quyen_trang_nao_thi_bao_ro(monkeypatch):
    con = tuple(k for k in roles.PAGES_BY_ROLE['admin'] if k not in ('ps2_xu_huong', 'ps3_nhip_lich', 'ps5_nhom'))
    monkeypatch.setitem(roles._PAGE_CHOICES, 'admin', con)
    at = _ps4(monkeypatch)
    assert any('Quyền hiện tại chưa mở trang phân tích liên quan' in c.value for c in at.caption)


def test_khach_khong_co_link_chat_van_co_cau_hoi(monkeypatch):
    monkeypatch.setenv('RETAIL_APP_ROLE', 'khach')
    monkeypatch.setitem(roles.DEFAULT_PAGE, 'khach', 'tong_quan')
    at = _ps4(monkeypatch)
    nhan = list(_links(at))
    assert not any('Hỏi dữ liệu (AI)' in x for x in nhan)
    assert any(roles.PAGES['ps5_nhom'][1] in x for x in nhan)


def test_loi_doc_kho_van_co_tieu_de_va_khong_ve_so(monkeypatch):
    def hong(_backend):
        raise RuntimeError('mất kết nối')
    monkeypatch.setenv('RETAIL_BACKEND', 'duckdb')
    monkeypatch.setattr(queries, 'driver_period', hong)
    st.cache_data.clear()
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    at.switch_page(PS4).run()
    assert not at.exception
    assert at.title[0].value == 'PS4 · Số đơn, số món và giá'
    assert any('Không đọc được `driver_period`' in e.value for e in at.error)
    assert len(at.metric) == 0 and len(at.table) == 0


def test_bang_rong_thi_dung_lai_khong_ve_so(monkeypatch):
    goc = queries.driver_period
    monkeypatch.setenv('RETAIL_BACKEND', 'duckdb')
    monkeypatch.setattr(queries, 'driver_period', lambda b: goc(b).iloc[0:0])
    st.cache_data.clear()
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    at.switch_page(PS4).run()
    assert not at.exception
    assert any('không có dòng nào' in w.value for w in at.warning)
    assert len(at.metric) == 0


# ---------------- PS1, PS2, PS3, PS5 dùng chung khung ----------------

def _trang(monkeypatch, page, **params):
    monkeypatch.setenv('RETAIL_BACKEND', 'duckdb')
    st.cache_data.clear()
    at = AppTest.from_file(str(APP), default_timeout=60)
    for k, v in params.items():
        at.query_params[k] = v
    at.run()
    at.switch_page(page).run()
    assert not at.exception and not at.error
    return at


def _cau_tl(at) -> str:
    return next(m.value for m in at.markdown if m.value.startswith('#### '))


CAC_TRANG = ['views/ps1_do_dung.py', 'views/ps2_xu_huong.py', 'views/ps3_nhip_lich.py', PS4, 'views/ps5_nhom.py']


@pytest.mark.parametrize('page', CAC_TRANG)
def test_moi_trang_co_bon_khoi_va_chu_nam_trong_muc_dong(monkeypatch, page):
    at = _trang(monkeypatch, page)
    tieu_de = ' '.join(s.value for s in at.subheader)
    for so in ['01', '02', '03', '04']:
        assert f':violet-badge[{so}]' in tieu_de
    assert 'Phân tích sâu' in tieu_de
    muc = next(e for e in at.expander if e.label == 'Tóm tắt bằng chữ, định nghĩa và giới hạn')
    assert not muc.proto.expanded                                     # đóng sẵn: người xem không phải đọc mới hiểu trang
    assert any(m.value == '**Tóm tắt từ số liệu**' for m in muc.markdown)
    assert any('không do AI viết' in c.value for c in muc.caption)    # câu viết sẵn vẫn ghi rõ nguồn gốc


def test_ps1_cau_tra_loi_doc_tu_thac(monkeypatch):
    at = _trang(monkeypatch, 'views/ps1_do_dung.py', ky='2019')
    w = queries.revenue_bridge('duckdb')
    w = w[(w['period_code'] == '2019') & w['step_code'].isin(['cancelled', 'returned', 'undelivered', 'discount'])]
    lon = w.loc[w['amount'].abs().idxmax()]
    cau = _cau_tl(at)
    assert trieu(lon['amount'], 1, signed=True) in cau and pct(lon['share_of_g']) in cau
    assert pct(queries.revenue_yearly('duckdb').set_index('year').loc[2019, 'capture_rate']) in cau


def test_ps2_cau_tra_loi_theo_giai_doan_cua_ba(monkeypatch):
    at = _trang(monkeypatch, 'views/ps2_xu_huong.py')
    ph = queries.revenue_phase('duckdb')
    r, cuoi = ph.loc[ph['cagr'].idxmin()], ph.iloc[-1]
    cau = _cau_tl(at)
    assert f'{r["phase_code"]}. {r["phase_name"]}' in cau and pct(r['total_change_rate'], 1, signed=True) in cau
    assert f'{cuoi["phase_code"]}. {cuoi["phase_name"]}' in cau


@pytest.mark.parametrize('nhip, chu', [('Tháng cao / thấp', 'lần'), ('Dồn cuối tháng', 'ngày 26'), ('Tháng 8: năm lẻ / chẵn', 'tháng 8')])
def test_ps3_cau_tra_loi_doi_theo_nhip(monkeypatch, nhip, chu):
    at = _trang(monkeypatch, 'views/ps3_nhip_lich.py')
    at.segmented_control[0].set_value(nhip).run()
    assert not at.exception and chu in _cau_tl(at)


@pytest.mark.parametrize('nam, co_ty_le', [(2019, True), (2015, False)])     # 2015: R đổi rất ít, tỷ lệ không ổn định
def test_ps5_cau_tra_loi_chi_neu_ty_le_khi_on_dinh(monkeypatch, nam, co_ty_le):
    at = _trang(monkeypatch, 'views/ps5_nhom.py', nam=str(nam))
    s = queries.segment_yearly('duckdb')
    s = s[(s['dimension_name'] == 'category') & (s['year'] == nam)]
    r = s.loc[s['delta_r'].abs().idxmax()]
    cau = _cau_tl(at)
    assert r['dimension_value'] in cau and trieu(r['delta_r'], 1, signed=True) in cau
    assert ('mức giảm' in cau or 'mức tăng' in cau) == co_ty_le


def test_ps5_bang_doi_chung_dung_so_kho_va_cong_du(monkeypatch):
    at = _trang(monkeypatch, 'views/ps5_nhom.py', nam='2019')
    bang = at.table[0].value
    y = queries.revenue_yearly('duckdb').set_index('year').loc[2019]
    assert bang.iloc[0].tolist() == ['Toàn công ty', num(y['r_prior_year'] / 1e6, 1), num(y['r'] / 1e6, 1),
                                     num(y['delta_r'] / 1e6, 1, signed=True), pct(y['yoy_rate'], 1, signed=True)]
    s = queries.segment_yearly('duckdb')
    s = s[(s['dimension_name'] == 'category') & (s['year'] == 2019)]
    assert s['delta_r'].sum() == pytest.approx(y['delta_r'])
    assert set(bang['Nhóm'][1:]) == set(s['dimension_value'])


def test_ps5_truc_co_cho_cho_nhan_ca_khi_moi_nhom_cung_chieu(monkeypatch):
    at = _trang(monkeypatch, 'views/ps5_nhom.py', nam='2019')
    lo, hi = json.loads(at.get('vega_lite_chart')[0].proto.spec)['layer'][1]['encoding']['x']['scale']['domain']
    s = queries.segment_yearly('duckdb')
    d = s[(s['dimension_name'] == 'category') & (s['year'] == 2019)]['delta_r']
    assert lo < d.min() and hi > 0.3 * d.abs().max()


def test_link_giua_cac_trang_chi_dung_ky_trang_dich_co():
    # Năm đưa sang PS4 (ky) và PS5 (nam) lấy từ năm có yoy_rate; PS5 đưa sang PS1, PS4 mọi năm của nó.
    y = queries.revenue_yearly('duckdb')
    co_nam_truoc = set(y.loc[y['yoy_rate'].notna(), 'year'].astype(int))
    ky_ps4 = set(queries.driver_period('duckdb')['period_code'])
    s = queries.segment_yearly('duckdb')
    nam_ps5 = set(s.loc[s['delta_r_rank'].notna(), 'year'].astype(int))
    ky_ps1 = set(queries.revenue_bridge('duckdb')['period_code'])
    assert {str(n) for n in co_nam_truoc} <= ky_ps4 and co_nam_truoc <= nam_ps5
    assert {str(n) for n in nam_ps5} <= ky_ps4 and {str(n) for n in nam_ps5} <= ky_ps1


@pytest.mark.parametrize('ky, co_tham_so', [('2019', True), ('2013', False), ('2013-2022', False)])
def test_ps1_chi_noi_nam_khi_trang_dich_so_duoc(monkeypatch, ky, co_tham_so):
    at = _trang(monkeypatch, 'views/ps1_do_dung.py', ky=ky)
    tro_sang = {pl.proto.label: pl.proto.query_string for pl in at.get('page_link')}
    ps4, ps5 = tro_sang[roles.PAGES['ps4_don_mon_gia'][1]], tro_sang[roles.PAGES['ps5_nhom'][1]]
    assert (f'ky={ky}' in ps4) == co_tham_so and (f'nam={ky}' in ps5) == co_tham_so


def test_ps2_noi_dung_giai_doan_dang_noi_toi(monkeypatch):
    at = _trang(monkeypatch, 'views/ps2_xu_huong.py')
    ph = queries.revenue_phase('duckdb')
    r = ph.loc[ph['cagr'].idxmin()]
    tro_sang = {pl.proto.label: pl.proto.query_string for pl in at.get('page_link')}
    assert f'ky={r["phase_code"]}' in tro_sang[roles.PAGES['ps4_don_mon_gia'][1]]
    assert f'nam={int(r["end_year"])}' in tro_sang[roles.PAGES['ps5_nhom'][1]]


@pytest.mark.parametrize('page', ['views/ps1_do_dung.py', 'views/ps2_xu_huong.py', 'views/ps3_nhip_lich.py', 'views/ps5_nhom.py'])
def test_cac_trang_khac_cung_an_link_khong_thuoc_quyen(monkeypatch, page):
    bo = {'ps2_xu_huong', 'ps4_don_mon_gia', 'ps5_nhom', 'ps1_do_dung', 'ps3_nhip_lich'} - {page.split('/')[1][:-3]}
    con = tuple(k for k in roles.PAGES_BY_ROLE['admin'] if k not in bo)
    monkeypatch.setitem(roles._PAGE_CHOICES, 'admin', con)
    at = _trang(monkeypatch, page)
    assert any('Quyền hiện tại chưa mở trang phân tích liên quan' in c.value for c in at.caption)


def test_ps4_canh_bao_chi_nam_trong_muc_dong(monkeypatch):
    at = _trang(monkeypatch, PS4)
    muc = next(e for e in at.expander if e.label == 'Tóm tắt bằng chữ, định nghĩa và giới hạn')
    assert any('chưa chứng minh nguyên nhân' in w.value for w in muc.warning)
    assert len(at.warning) == len(muc.warning)                        # không còn dải vàng nào ngoài mục đóng


@pytest.mark.parametrize('chieu, so_cot', [('category', 4), ('region', 3), ('acquisition_channel', 3)])
def test_ps5_chu_giai_khong_de_nhom_cuoi_rot_dong(monkeypatch, chieu, so_cot):
    at = _trang(monkeypatch, 'views/ps5_nhom.py', chieu=chieu)
    enc = json.loads(at.get('vega_lite_chart')[1].proto.spec)['encoding']
    assert enc['color']['legend']['columns'] == so_cot == enc['shape']['legend']['columns']
    assert len(enc['color']['scale']['domain']) % so_cot == 0         # mọi hàng đủ cột

