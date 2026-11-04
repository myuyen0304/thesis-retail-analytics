import altair as alt
import pandas as pd
import streamlit as st

from ai_explain import page_explain
from ui import bi
from ui.ai_panel import ai_panel
from ui.common import GIOI_HAN_CHUNG, hang_the, kpi, load_or_stop, need, url_choice
from ui.fmt import num, pct, trieu

bi.nap_css()
c_ten, c_ky = bi.hang_doi('dau', (3, 2))
c_ten.title('PS4 · Số đơn, số món và giá')

dp = load_or_stop('driver_period')       # 1 dòng = 1 năm hoặc 1 giai đoạn PS2
br = load_or_stop('driver_bridge')
yearly = load_or_stop('revenue_yearly')
rule = load_or_stop('driver_rule').iloc[0]
# Xác nhận metadata có dữ liệu trước khi vẽ KPI; phần trình bày nguồn đặt ở cuối trang.
load_or_stop('build_info')
nguong = pct(rule['min_abs_delta_rate'], 0)

PHAN = {'n': 'số đơn N', 'u': 'số món mỗi đơn U', 'p': 'giá mỗi món P'}
dp['nam'] = dp['start_year'].astype(str) + '→' + dp['end_year'].astype(str)
dp['ten'] = [f'Giai đoạn {c}. {n} ({k})' if t == 'phase' else f'Năm {e} so với {s}'
             for t, c, n, k, s, e in zip(dp['period_type'], dp['period_code'], dp['phase_name'], dp['nam'],
                                         dp['start_year'], dp['end_year'])]
ten_of = dict(zip(dp['period_code'], dp['ten']))

# --- Chọn kỳ: 4 giai đoạn PS2 + từng năm 2014–2022 (mặc định 2019, năm sập) ---
codes = list(dp['period_code'])
code = c_ky.selectbox('Kỳ', codes, index=url_choice('ky', codes, codes.index('2019') if '2019' in codes else 0, 'kỳ'),
                      format_func=ten_of.get)
row = dp.set_index('period_code').loc[code]
s0, s1 = int(row['start_year']), int(row['end_year'])
st.session_state._collapse_source = True


def mo_ta_phan(r, key: str) -> str:
    rate = r[key + '_change_rate']
    return (f'{PHAN[key]} ({"tăng" if rate > 0 else "giảm"} {pct(abs(rate), 1)}, '
            f'làm R {trieu(r["contrib_" + key], 1, signed=True)})')


def cau_keo(r) -> str:
    """Câu "kéo xuống / kéo lên" ghép từ cột top_up_driver, top_down_driver, *_change_rate (dbt tính sẵn).
    Phần nào làm R đổi nhiều tiền hơn thì nói trước."""
    parts = []
    for k, chieu in ((r['top_down_driver'], 'kéo xuống'), (r['top_up_driver'], 'kéo lên')):
        if isinstance(k, str):
            parts.append((abs(r['contrib_' + k]), f'{chieu} nhiều nhất là {mo_ta_phan(r, k)}'))
    return '; '.join(t for _, t in sorted(parts, key=lambda x: -x[0]))


def hoa_dau(t: str) -> str:
    return t[0].upper() + t[1:]         # str.capitalize() hạ chữ N, U, P về thường


def phan_chinh(r) -> str | None:
    """Phần dbt đánh dấu kéo mạnh nhất theo đúng chiều đổi của R; không có thì lấy phần còn lại."""
    chinh = r['top_down_driver'] if r['delta_r'] < 0 else r['top_up_driver']
    if not isinstance(chinh, str):
        chinh = r['top_up_driver'] if r['delta_r'] < 0 else r['top_down_driver']
    return chinh if isinstance(chinh, str) else None


def mau_tien(v) -> str:
    """Số tiền kèm dấu, tô theo chiều tăng/giảm."""
    return bi.mau(trieu(v, 1, signed=True), v)


def cau_tra_loi(r) -> str:
    """Một câu trả lời thẳng câu hỏi của trang, ghép từ cột dbt; không do AI viết."""
    up, down = r['top_up_driver'], r['top_down_driver']
    if r['delta_r_is_small'] and isinstance(up, str) and isinstance(down, str):
        return (f'R gần như không đổi ({mau_tien(r["delta_r"])}): {PHAN[down]} {mau_tien(r["contrib_" + down])} '
                f'và {PHAN[up]} {mau_tien(r["contrib_" + up])} bù trừ nhau')
    chinh = phan_chinh(r)
    if chinh is None:
        return f'R đổi {mau_tien(r["delta_r"])}'
    return f'R đổi {mau_tien(r["delta_r"])}; {PHAN[chinh]} góp nhiều nhất: {mau_tien(r["contrib_" + chinh])}'


def cau_hoi_tiep(r) -> list[bi.CauHoi]:
    """Ba câu theo kỳ đang xem, nối PS4 với PS5, PS2, PS3. Chỉ mở bằng tham số trang đọc được (PS5: chieu, nam; PS2, PS3
    không có bộ lọc); nút ghi rõ trang hiện gì. Phần "chính" là phần dbt đánh dấu cùng chiều với mức đổi R."""
    nam, la_gd = int(r['end_year']), r['period_type'] == 'phase'
    pham_vi = f'năm {nam} so với {nam - 1}' + (' (năm cuối giai đoạn; PS5 so từng năm)' if la_gd else '')
    chinh = phan_chinh(r)
    if r['delta_r_is_small']:
        cau_5 = bi.CauHoi('R đổi rất ít: ngành hàng nào bù trừ?', 'ps5_nhom',
                          f'ngành hàng, {pham_vi}', {'chieu': 'category', 'nam': nam})
    elif chinh == 'n':
        cau_5 = bi.CauHoi(f'{hoa_dau(PHAN["n"])} đổi {pct(r["n_change_rate"], 1, signed=True)}: số khách hay tần suất?',
                          'ps5_nhom', f'tab Khách hàng & tần suất, {pham_vi}', {'nam': nam})
    else:
        cau_5 = bi.CauHoi(f'{hoa_dau(PHAN[chinh])} đổi {pct(r[chinh + "_change_rate"], 1, signed=True)}: ngành hàng nào?',
                          'ps5_nhom', f'ngành hàng, {pham_vi}', {'chieu': 'category', 'nam': nam})
    cau_2 = (f'Giai đoạn {r["phase_code"]} so với trước và sau?' if la_gd else f'Năm {nam} trong xu hướng dài hạn?')
    cau_3 = (f'Năm lẻ {nam}: tháng 8 năm lẻ có thấp hơn?' if not la_gd and nam % 2 else 'Nhịp lịch có lặp lại không?')
    return [cau_5, bi.CauHoi(cau_2, 'ps2_xu_huong', 'mọi năm, trang không lọc theo kỳ'),
            bi.CauHoi(cau_3, 'ps3_nhip_lich', 'mọi năm, trang không lọc theo kỳ')]


# --- Thác R đầu → N → U → P → R cuối ---
BUOC = {'n': 'Số đơn N', 'u': 'Số món mỗi đơn U', 'p': 'Giá mỗi món P'}
NHAN_TRUC = {'n': 'Số đơn N', 'u': 'Món/đơn U', 'p': 'Giá/món P'}
w = need(br[(br['period_code'] == code) & (br['bridge_code'] == 'r_nup')], 'driver_bridge',
         f'của thác doanh thu kỳ {code}').copy()
w['Cột'] = [f'R {int(y)}' if c in ('r_start', 'r_end') else BUOC[c] for c, y in zip(w['step_code'], w['step_year'])]
w['Nhãn'] = [f'R {int(y)}' if c in ('r_start', 'r_end') else NHAN_TRUC[c] for c, y in zip(w['step_code'], w['step_year'])]
w['loai'] = ['Tổng' if c in ('r_start', 'r_end') else ('Tăng' if a >= 0 else 'Giảm')
             for c, a in zip(w['step_code'], w['amount'])]
w['Số đầy đủ'] = [num(a, 2) if c in ('r_start', 'r_end') else num(a, 2, signed=True) for c, a in zip(w['step_code'], w['amount'])]
w['nhan'] = [num(a / 1e6, 1) if c in ('r_start', 'r_end') else num(a / 1e6, 1, signed=True)
             for c, a in zip(w['step_code'], w['amount'])]
w['Số tiền'] = [trieu(a, 1) if c in ('r_start', 'r_end') else trieu(a, 1, signed=True)
                for c, a in zip(w['step_code'], w['amount'])]
thu_tu = list(w['Nhãn'])
x = alt.X('Nhãn:N', sort=thu_tu, title=None,
          axis=alt.Axis(labelAngle=0, labelLimit=80, labelFontSize=11, labelOverlap=False))
# Đường nối mức R sau mỗi bước sang cột kế tiếp; bar_end là cột dbt, không tính lại trên trang.
# Lớp này phải dùng đúng trục x của cột (cùng field, cùng sort): khác field thì Vega-Lite bỏ sort, cột xếp theo ABC.
noi = alt.Chart(pd.DataFrame({'Nhãn': thu_tu[:-1], 'den': thu_tu[1:], 'muc': list(w['bar_end'])[:-1]})).mark_rule(
    color=bi.MAU_NOI, strokeDash=[3, 3]).encode(x=x, x2='den:N', y='muc:Q')
bars = alt.Chart(w).mark_bar(cornerRadius=3).encode(
    x=x,
    y=alt.Y('bar_start:Q', title=None, axis=alt.Axis(labelExpr=bi.AXIS_SO_TRIEU, tickCount=5)),
    y2='bar_end:Q',
    color=alt.Color('loai:N', scale=alt.Scale(domain=['Tổng', 'Tăng', 'Giảm'], range=[bi.MAU_TONG, bi.MAU_TANG, bi.MAU_GIAM]),
                    legend=alt.Legend(title=None, orient='top', direction='horizontal')),
    tooltip=['Cột', 'Số đầy đủ'],
)
text = alt.Chart(w).transform_calculate(top='max(datum.bar_start, datum.bar_end)').mark_text(dy=-9, fontSize=12, fontWeight=600, color=bi.mau_chu()).encode(
    x=x, y='top:Q', text='nhan:N')
right = st.column_config.TextColumn(alignment='right')

xu_huong = yearly[yearly['is_analysis_period']].sort_values('year')


def duong(cot: str) -> list[float]:
    """Đường nhỏ trong thẻ: chính cột của rpt_revenue_yearly theo năm, không tính thêm."""
    return xu_huong[cot].astype(float).tolist()


# --- 01 Nhận định: một câu trả lời và bốn thẻ ---
with bi.khoi('01', 'Doanh thu thay đổi chủ yếu ở thành phần nào?'):
    st.markdown(f'#### {cau_tra_loi(row)}')
    # Feedback 2026-10-01 (F01): số lớn của thẻ đầu là MỨC ĐỔI R, không phải mức R → nhãn "Thay đổi R".
    # Feedback PM 2026-10-02: số lớn có đơn vị; 4 thẻ một hàng, đều nhau (ui.common.hang_the).
    c0, c1, c2, c3 = hang_the('the_ps4', 4)
    kpi(c0, 'Thay đổi doanh thu R', trieu(row['delta_r'], 1, signed=True),
        f'R {s0}: {num(row["r_start"], 2)}; R {s1}: {num(row["r_end"], 2)}. Ba thẻ bên cạnh cộng lại đúng bằng số này.',
        delta=pct(row['r_change_rate'], 1, signed=True), delta_sign=row['r_change_rate'],
        delta_desc=f'R: {num(row["r_start"] / 1e6)} → {num(row["r_end"] / 1e6)} triệu', chart=duong('r'))
    kpi(c1, 'Tác động của số đơn N', trieu(row['contrib_n'], 1, signed=True),
        '(N₁ − N₀) × U₀ × P₀: doanh thu đổi bao nhiêu nếu chỉ số đơn đổi, số món mỗi đơn và giá mỗi món giữ như năm đầu.',
        delta=pct(row['n_change_rate'], 1, signed=True), delta_sign=row['n_change_rate'],
        delta_desc=f'N: {num(row["n_start"])} → {num(row["n_end"])} đơn', chart=duong('n'))
    kpi(c2, 'Tác động của số món/đơn U', trieu(row['contrib_u'], 1, signed=True),
        'N₁ × (U₁ − U₀) × P₀: phần doanh thu đổi do số món mỗi đơn đổi (số đơn năm cuối, giá năm đầu).',
        delta=pct(row['u_change_rate'], 1, signed=True), delta_sign=row['u_change_rate'],
        delta_desc=f'U: {num(row["u_start"], 2)} → {num(row["u_end"], 2)} món/đơn', chart=duong('u'))
    kpi(c3, 'Tác động của giá/món P', trieu(row['contrib_p'], 1, signed=True),
        'N₁ × U₁ × (P₁ − P₀): phần doanh thu đổi do giá mỗi món (sau chiết khấu) đổi, với số đơn và số món năm cuối.',
        delta=pct(row['p_change_rate'], 1, signed=True), delta_sign=row['p_change_rate'],
        delta_desc=f'P: {num(row["p_start"])} → {num(row["p_end"])} mỗi món', chart=duong('p'))

# --- 02 Bằng chứng: thác và bảng đối chứng ---
with bi.khoi('02', f'Từ R {s0} đến R {s1} (triệu đồng)'):
    c_thac, c_bang = bi.hang_doi('bang_chung', (7, 5))
    with c_thac:
        st.altair_chart(bi.dinh_dang_bieu_do((noi + bars + text).properties(height=270, padding={'top': 20})), width='stretch')
    with c_bang:
        bi.bang_doi_chung(pd.DataFrame({
            'Thành phần': ['Doanh thu R (triệu)', 'Số đơn N', 'Số món/đơn U', 'Giá/món P (VND)'],
            str(s0): [num(row['r_start'] / 1e6, 1), num(row['n_start']), num(row['u_start'], 2), num(row['p_start'])],
            str(s1): [num(row['r_end'] / 1e6, 1), num(row['n_end']), num(row['u_end'], 2), num(row['p_end'])],
            'Tác động lên R': [trieu(row[c], 1, signed=True) for c in ['delta_r', 'contrib_n', 'contrib_u', 'contrib_p']],
            'Biến động yếu tố': [pct(row[c], 1, signed=True) for c in ['r_change_rate', 'n_change_rate', 'u_change_rate',
                                                                        'p_change_rate']],
        }), 'Tác động lên R', [row[c] for c in ['delta_r', 'contrib_n', 'contrib_u', 'contrib_p']])
        with st.expander('Xem số liệu làm căn cứ'):
            st.dataframe(w[['Cột', 'Số tiền']], hide_index=True, width='stretch', column_config={'Số tiền': right})
            st.caption('Cột đóng góp nhỏ vẫn có nhãn; số gốc xem qua tooltip. Số làm tròn có thể lệch 0,1 triệu.')

# --- 03 AI (chỉ chạy khi bấm nút, xem ui/ai_panel.py) và 04 câu hỏi kiểm tra tiếp ---
c_ai, c_tiep = bi.hang_doi('ai_tiep', (5, 7))
with c_ai:
    with bi.khoi('03', 'AI giải thích'):
        ai_panel(page_explain.request_ps4(code, row['period_type'], s0, s1, ten_of[code]))
with c_tiep:
    with bi.khoi('04', 'Kiểm tra tiếp'):
        bi.hoi_tiep(cau_hoi_tiep(row))

# --- Phân tích sâu: dữ liệu và cách cộng phần góp giữ theo reporting hiện có ---
o_sau = bi.khoi('', 'Phân tích sâu')
tab_year, tab_phase, tab_indices = o_sau.tabs(['So sánh theo năm', 'So sánh theo giai đoạn', 'Chỉ số N/U/P/AOV'])

yr = dp[dp['period_type'] == 'year'].copy()
long = yr.melt(id_vars=['period_code', 'phase_code'], value_vars=['contrib_n', 'contrib_u', 'contrib_p'],
               var_name='phan', value_name='v')
long['Phần'] = long['phan'].map({'contrib_n': 'Số đơn N', 'contrib_u': 'Số món mỗi đơn U', 'contrib_p': 'Giá mỗi món P'})
long['Số tiền'] = long['v'].map(lambda v: trieu(v, 1, signed=True))
long['Năm'] = long['period_code']
# Năm thuộc kỳ đang chọn đậm, năm khác mờ: chọn năm thì một cột, chọn giai đoạn thì các năm có phase_code đó.
long['chon'] = long['period_code'].eq(code) | long['phase_code'].eq(code)
bar_nam = alt.Chart(long).mark_bar(stroke=bi.mau_nen(), strokeWidth=1).encode(
    x=alt.X('Năm:O', title=None, axis=alt.Axis(labelAngle=0)),
    y=alt.Y('v:Q', title=None, stack='zero', axis=alt.Axis(labelExpr=bi.AXIS_SO_TRIEU, tickCount=5)),
    color=alt.Color('Phần:N', sort=['Số đơn N', 'Số món mỗi đơn U', 'Giá mỗi món P'],
                    scale=alt.Scale(range=bi.MAU_NUP),
                    legend=alt.Legend(title=None, orient='top', direction='horizontal')),
    opacity=alt.condition('datum.chon', alt.value(1), alt.value(0.38)),
    order=alt.Order('phan:N'),
    tooltip=['Năm', 'Phần', 'Số tiền'],
)
yr['Năm'] = yr['period_code']
yr['R đổi'] = yr['delta_r'].map(lambda v: trieu(v, 1, signed=True))
# Hình thoi tối viền trắng: thấy được trên nền trắng và khi đè lên cột.
diem = alt.Chart(yr).mark_point(shape='diamond', size=110, filled=True, color=bi.mau_chu(), stroke=bi.mau_nen(), strokeWidth=1).encode(
    x='Năm:O', y='delta_r:Q', tooltip=['Năm', 'R đổi'])
tn = yr[['period_code']].rename(columns={'period_code': 'Năm'})
tn['Giai đoạn'] = yr['phase_code']
tn['R đổi'] = yr['R đổi']
tn['Phần N'] = yr['contrib_n'].map(lambda v: trieu(v, 1, signed=True))
tn['Phần U'] = yr['contrib_u'].map(lambda v: trieu(v, 1, signed=True))
tn['Phần P'] = yr['contrib_p'].map(lambda v: trieu(v, 1, signed=True))
tn['Kéo lên nhiều nhất'] = yr['top_up_driver'].map(lambda k: k.upper() if isinstance(k, str) else '–')
tn['Kéo xuống nhiều nhất'] = yr['top_down_driver'].map(lambda k: k.upper() if isinstance(k, str) else '–')
tn['Ghi chú'] = yr['delta_r_is_small'].map(lambda b: 'R đổi rất nhỏ' if b else '')
with tab_year:
    st.altair_chart(bi.dinh_dang_bieu_do((bar_nam + diem).properties(height=250)), width='stretch')
    st.caption('Triệu đồng · Năm thuộc kỳ đang chọn tô đậm · Hình thoi = mức đổi R, bằng tổng ba phần')
    with st.expander('Xem bảng đóng góp theo năm'):
        st.dataframe(tn, hide_index=True, height='content', width='stretch',
                     column_config={c: right for c in ['R đổi', 'Phần N', 'Phần U', 'Phần P']})
        st.caption(f'"R đổi rất nhỏ": mức đổi R dưới {nguong} R năm trước; đọc số tiền từng phần.')

# --- So sánh giữa các giai đoạn PS2 ---
ph = dp[dp['period_type'] == 'phase'].copy()
tp = ph[['ten']].rename(columns={'ten': 'Giai đoạn'})
tp['R đổi'] = ph['delta_r'].map(lambda v: trieu(v, 1, signed=True))
tp['Phần N'] = ph['contrib_n'].map(lambda v: trieu(v, 1, signed=True))
tp['Phần U'] = ph['contrib_u'].map(lambda v: trieu(v, 1, signed=True))
tp['Phần P'] = ph['contrib_p'].map(lambda v: trieu(v, 1, signed=True))
tp['Kéo lên nhiều nhất'] = ph['top_up_driver'].map(lambda k: k.upper() if isinstance(k, str) else '–')
tp['Kéo xuống nhiều nhất'] = ph['top_down_driver'].map(lambda k: k.upper() if isinstance(k, str) else '–')
with tab_phase:
    st.dataframe(tp, hide_index=True, height='content', width='stretch',
                 column_config={c: right for c in ['R đổi', 'Phần N', 'Phần U', 'Phần P']})
    st.markdown('**Nhận xét so sánh:**\n' + '\n'.join(
        f'- {c}: {cau_keo(r)}.' + (f' Mức đổi R chỉ {trieu(r["delta_r"], 1, signed=True)} (dưới {nguong} R đầu giai đoạn) '
                                   'vì hai phần lớn bù trừ nhau.' if r['delta_r_is_small'] else '')
        for c, (_, r) in zip(ph['period_code'], ph.iterrows())))
    st.caption('Phần của giai đoạn = cộng phần của từng năm trong giai đoạn '
               '(năm Y thuộc giai đoạn có năm đầu < Y ≤ năm cuối, như PS2). '
               'Tách thẳng từ năm đầu đến năm cuối cho số hơi khác, nhưng cùng phần kéo lên/xuống '
               '(dbt test assert_rpt_driver).')

# --- Chỉ số theo năm ---
y = yearly[yearly['is_analysis_period']].copy()
ti = y[['year']].rename(columns={'year': 'Năm'})
ti['N (số đơn)'] = y['n'].map(num)
ti['U (món / đơn)'] = y['u'].map(lambda v: num(v, 2))
ti['P (giá / món)'] = y['p'].map(lambda v: num(v, 0))
ti['AOV (giá trị / đơn)'] = y['aov'].map(lambda v: num(v, 0))
ti['Tăng N'] = y['yoy_n'].map(lambda v: pct(v, 1, signed=True))
ti['Tăng U'] = y['yoy_u'].map(lambda v: pct(v, 1, signed=True))
ti['Tăng P'] = y['yoy_p'].map(lambda v: pct(v, 1, signed=True))
ti['Tăng R'] = y['yoy_rate'].map(lambda v: pct(v, 1, signed=True))
with tab_indices:
    st.dataframe(ti, hide_index=True, height='content', width='stretch',
                 column_config={'Năm': st.column_config.NumberColumn(format='%d'),
                                **{c: right for c in ti.columns if c != 'Năm'}})
    st.caption('N: đơn; U: món/đơn; P: VND/món sau chiết khấu; AOV: VND/đơn. '
               'Tăng N/U/P/R là biến động so năm trước; R = N × U × P.')

with o_sau.expander('Tóm tắt bằng chữ, định nghĩa và giới hạn'):
    # Plan §3 tiêu chí 4: trang phải có câu này. PM 2026-11-01 bỏ dải vàng khỏi màn hình, nên đặt trong mục đóng sẵn.
    st.warning('**Phân rã theo thứ tự N → U → P; thể hiện đóng góp số học, chưa chứng minh nguyên nhân.**')
    st.caption(f'Đang so sánh: {ten_of[code]} · Đơn vị tiền: VND (triệu = triệu đồng)')
    st.markdown('**Tóm tắt từ số liệu**')
    y_tom_tat = [f'**R {"tăng" if row["delta_r"] > 0 else "giảm"}:** {trieu(abs(row["delta_r"]), 1)} '
                 f'({pct(row["r_change_rate"], 1, signed=True)}), từ {trieu(row["r_start"], 1)} đến {trieu(row["r_end"], 1)}.']
    if isinstance(row['top_down_driver'], str):
        y_tom_tat.append(f'**Giảm lớn nhất:** {mo_ta_phan(row, row["top_down_driver"])}.')
    if isinstance(row['top_up_driver'], str):
        y_tom_tat.append(f'**Phần tăng/bù đắp:** {mo_ta_phan(row, row["top_up_driver"])}.')
    y_tom_tat.append(f'**Lưu ý:** ΔR dưới {nguong} R đầu kỳ; các phần ngược dấu bù trừ. Đọc số tiền từng phần, không đọc % '
                     'đóng góp.' if row['delta_r_is_small'] else
                     '**Giới hạn:** thứ tự N → U → P ảnh hưởng phần góp; P còn thay đổi theo chiết khấu và cơ cấu hàng bán.')
    st.markdown('\n'.join(f'- {t}' for t in y_tom_tat))
    st.caption('Câu viết sẵn theo quy tắc từ số liệu, không do AI viết')
    # Bảng năm thiếu kỳ phân tích thì thẻ không có đường nhỏ; câu này cũng không nêu khoảng năm.
    duong_nho = (f' Đường nhỏ: mức R, N, U, P từng năm {int(xu_huong["year"].iloc[0])}–{int(xu_huong["year"].iloc[-1])}.'
                 if not xu_huong.empty else '')
    st.caption('Số lớn là mức thay đổi hoặc đóng góp bằng tiền. Dòng % là biến động của chính R, N, U hoặc P; '
               f'không phải tỷ trọng đóng góp vào thay đổi R.{duong_nho}')
    st.caption('Tác động của N, U, P cộng lại bằng dòng R trên số gốc. Biến động là % đổi của chính yếu tố, không phải '
               'phần chia của mức đổi R.')
    st.markdown('**Định nghĩa & phạm vi dữ liệu**')
    st.markdown(
        '**R = N × U × P**, với N là số đơn đã giao, U là số món mỗi đơn, '
        'P là giá bình quân mỗi món sau chiết khấu. R tính theo ngày đặt hàng, không phải dòng tiền thanh toán.\n\n'
        'Bộ lọc gồm so sánh từng năm và các giai đoạn PS2. Với giai đoạn, phần góp bằng tổng phần góp '
        'của các năm trong giai đoạn; tỷ lệ biến động N/U/P so thẳng năm cuối với năm đầu.'
    )

    st.markdown('**Cách đọc & phương pháp**')
    st.markdown('\n'.join(f'- {item}' for item in [
        'Số lớn ở thẻ là tiền: ΔR và phần góp N/U/P. Ba phần góp cộng bằng ΔR trên số gốc '
        '(dbt test `assert_rpt_decomposition_additive`); số làm tròn có thể lệch 0,1 triệu.',
        'Dòng % dưới thẻ là biến động của chính yếu tố, không phải tỷ trọng đóng góp. '
        'Các tỷ lệ N/U/P không cộng thành tỷ lệ đổi R.',
        'Thác dùng thứ tự N → U → P; phần dương kéo R lên, phần âm kéo R xuống. '
        'Các phần ngược dấu có thể bù trừ nhau.',
        'Với giai đoạn, phần góp là tổng phần góp của từng năm từ năm sau năm đầu đến năm cuối; '
        'dòng % so trực tiếp năm cuối với năm đầu kỳ.',
        'N × U × P = R. Tăng trưởng năm thỏa '
        '(1 + tăng N) × (1 + tăng U) × (1 + tăng P) = 1 + tăng R.',
    ]))

    st.markdown('**Giới hạn chi tiết**')
    st.markdown('\n'.join(f'- {item}' for item in [
        'Thứ tự N → U → P ảnh hưởng kết quả vì phần tương tác dồn vào phần tách sau. '
        'Đây là phân rã số học, chưa chứng minh nguyên nhân.',
        'P là giá bình quân mỗi món sau chiết khấu. P thay đổi do giá bán, chiết khấu hoặc cơ cấu hàng bán; '
        'không thể suy ra doanh nghiệp đã tăng/giảm giá từ P đơn lẻ.',
        'Phần giai đoạn cộng dồn từng năm (dev đề xuất, chờ BA chốt). '
        'Tách thẳng từ năm đầu tới năm cuối giai đoạn cho số hơi khác.',
        f'Ngưỡng "mức đổi R nhỏ" {nguong} do dev đề xuất, chờ BA chốt (seed driver_rule); '
        'khi các phần bù trừ, đọc số tiền thay vì % đóng góp.',
        *GIOI_HAN_CHUNG,
    ]))
