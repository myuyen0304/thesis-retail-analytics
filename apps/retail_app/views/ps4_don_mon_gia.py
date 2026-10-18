import altair as alt
import streamlit as st

from ui.common import GIOI_HAN_CHUNG, hang_the, kpi, load_or_stop, need, url_choice
from ui.fmt import AXIS_TRIEU, num, pct, trieu

st.title('PS4 · Số đơn, số món và giá')
st.markdown('Biến động doanh thu được phân rã theo N, U và P như thế nào?')

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
code = st.selectbox('Kỳ', codes, index=url_choice('ky', codes, codes.index('2019') if '2019' in codes else 0, 'kỳ'),
                    format_func=ten_of.get)
row = dp.set_index('period_code').loc[code]
s0, s1 = int(row['start_year']), int(row['end_year'])
st.caption(f'Đang so sánh: {ten_of[code]} · Đơn vị tiền: VND (triệu = triệu đồng)')
with st.expander('Định nghĩa & phạm vi dữ liệu'):
    st.markdown(
        '**R = N × U × P**, với N là số đơn đã giao, U là số món mỗi đơn, '
        'P là giá bình quân mỗi món sau chiết khấu. R tính theo ngày đặt hàng, không phải dòng tiền thanh toán.\n\n'
        'Bộ lọc gồm so sánh từng năm và các giai đoạn PS2. Với giai đoạn, phần góp bằng tổng phần góp '
        'của các năm trong giai đoạn; tỷ lệ biến động N/U/P so thẳng năm cuối với năm đầu.'
    )
st.warning('**Phân rã theo thứ tự N → U → P; thể hiện đóng góp số học, chưa chứng minh nguyên nhân.**')
st.session_state._collapse_source = True

# Feedback 2026-10-01 (F01): số lớn của thẻ đầu là MỨC ĐỔI R, không phải mức R → nhãn "Thay đổi R"; kỳ ghi ngay trên hàng thẻ.
# Feedback PM 2026-10-02: số lớn có đơn vị; 4 thẻ một hàng, đều nhau (ui.common.hang_the).
c0, c1, c2, c3 = hang_the('the_ps4', 4)
kpi(c0, 'Thay đổi doanh thu R', trieu(row['delta_r'], 1, signed=True),
    f'R {s0}: {num(row["r_start"], 2)}; R {s1}: {num(row["r_end"], 2)}. Ba thẻ bên cạnh cộng lại đúng bằng số này.',
    delta=pct(row['r_change_rate'], 1, signed=True), delta_sign=row['r_change_rate'],
    delta_desc=f'R: {num(row["r_start"] / 1e6)} → {num(row["r_end"] / 1e6)} triệu')
kpi(c1, 'Tác động của số đơn N', trieu(row['contrib_n'], 1, signed=True),
    '(N₁ − N₀) × U₀ × P₀: doanh thu đổi bao nhiêu nếu chỉ số đơn đổi, số món mỗi đơn và giá mỗi món giữ như năm đầu.',
    delta=pct(row['n_change_rate'], 1, signed=True), delta_sign=row['n_change_rate'],
    delta_desc=f'N: {num(row["n_start"])} → {num(row["n_end"])} đơn')
kpi(c2, 'Tác động của số món/đơn U', trieu(row['contrib_u'], 1, signed=True),
    'N₁ × (U₁ − U₀) × P₀: phần doanh thu đổi do số món mỗi đơn đổi (số đơn năm cuối, giá năm đầu).',
    delta=pct(row['u_change_rate'], 1, signed=True), delta_sign=row['u_change_rate'],
    delta_desc=f'U: {num(row["u_start"], 2)} → {num(row["u_end"], 2)} món/đơn')
kpi(c3, 'Tác động của giá/món P', trieu(row['contrib_p'], 1, signed=True),
    'N₁ × U₁ × (P₁ − P₀): phần doanh thu đổi do giá mỗi món (sau chiết khấu) đổi, với số đơn và số món năm cuối.',
    delta=pct(row['p_change_rate'], 1, signed=True), delta_sign=row['p_change_rate'],
    delta_desc=f'P: {num(row["p_start"])} → {num(row["p_end"])} mỗi món')
st.caption('Số lớn là mức thay đổi hoặc đóng góp bằng tiền. Dòng % là biến động của chính R, N, U hoặc P; '
           'không phải tỷ trọng đóng góp vào thay đổi R.')


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


# --- Thác R đầu → N → U → P → R cuối ---
BUOC = {'n': 'Số đơn N', 'u': 'Số món mỗi đơn U', 'p': 'Giá mỗi món P'}
w = need(br[(br['period_code'] == code) & (br['bridge_code'] == 'r_nup')], 'driver_bridge',
         f'của thác doanh thu kỳ {code}').copy()
w['Cột'] = [f'R {int(y)}' if c in ('r_start', 'r_end') else BUOC[c] for c, y in zip(w['step_code'], w['step_year'])]
w['Nhãn'] = [f'R {int(y)}' if c in ('r_start', 'r_end') else c.upper() for c, y in zip(w['step_code'], w['step_year'])]
w['loai'] = ['Tổng' if c in ('r_start', 'r_end') else ('Tăng' if a >= 0 else 'Giảm')
             for c, a in zip(w['step_code'], w['amount'])]
w['Số đầy đủ'] = [num(a, 2) if c in ('r_start', 'r_end') else num(a, 2, signed=True) for c, a in zip(w['step_code'], w['amount'])]
w['nhan'] = [num(a / 1e6, 1) if c in ('r_start', 'r_end') else num(a / 1e6, 1, signed=True)
             for c, a in zip(w['step_code'], w['amount'])]
w['Số tiền'] = [trieu(a, 1) if c in ('r_start', 'r_end') else trieu(a, 1, signed=True)
                for c, a in zip(w['step_code'], w['amount'])]
x = alt.X('Nhãn:N', sort=list(w['Nhãn']), title=None,
          axis=alt.Axis(labelAngle=0, labelLimit=80, labelFontSize=10, labelOverlap=False))
bars = alt.Chart(w).mark_bar().encode(
    x=x,
    y=alt.Y('bar_start:Q', title=None, axis=alt.Axis(labelExpr=AXIS_TRIEU)),
    y2='bar_end:Q',
    color=alt.Color('loai:N', scale=alt.Scale(domain=['Tổng', 'Tăng', 'Giảm'], range=['#1f5f8b', '#2a9d8f', '#d1495b']),
                    legend=alt.Legend(title=None, orient='top')),
    tooltip=['Cột', 'Số đầy đủ'],
)
text = alt.Chart(w).transform_calculate(top='max(datum.bar_start, datum.bar_end)').mark_text(dy=-8, fontSize=10).encode(
    x=x, y='top:Q', text='nhan:N')
right = st.column_config.TextColumn(alignment='right')
st.subheader('Từ R đầu kỳ đến R cuối kỳ')
left, side = st.columns([2, 1], gap='medium')
with left:
    st.caption(f'{s0} → {s1} · Nhãn cột: triệu đồng. Rê chuột để xem số đầy đủ; N/U/P là phần đóng góp.')
    st.altair_chart((bars + text).properties(height=420, padding={'top': 24}), width='stretch')
    with st.expander('Xem số liệu làm căn cứ'):
        st.dataframe(w[['Cột', 'Số tiền']], hide_index=True, width='stretch', column_config={'Số tiền': right})
        st.caption('Cột đóng góp nhỏ vẫn có nhãn; số gốc xem qua tooltip. Số làm tròn có thể lệch 0,1 triệu.')
with side:
    with st.container(border=True):
        st.markdown('**Giải thích kết quả**')
        st.caption('Tóm tắt theo quy tắc từ số liệu kỳ đang chọn')
        st.markdown(f'- **R {"tăng" if row["delta_r"] > 0 else "giảm"}:** '
                    f'{trieu(abs(row["delta_r"]), 1)} ({pct(row["r_change_rate"], 1, signed=True)}), '
                    f'từ {trieu(row["r_start"], 1)} đến {trieu(row["r_end"], 1)}.')
        if isinstance(row['top_down_driver'], str):
            st.markdown(f'- **Giảm lớn nhất:** {mo_ta_phan(row, row["top_down_driver"])}.')
        if isinstance(row['top_up_driver'], str):
            st.markdown(f'- **Phần tăng/bù đắp:** {mo_ta_phan(row, row["top_up_driver"])}.')
        if row['delta_r_is_small']:
            st.markdown(f'- **Lưu ý:** ΔR dưới {nguong} R đầu kỳ; các phần ngược dấu bù trừ. '
                        'Đọc số tiền từng phần, không đọc % đóng góp.')
        else:
            st.markdown('- **Giới hạn:** thứ tự N → U → P ảnh hưởng phần góp; P còn thay đổi theo '
                        'chiết khấu và cơ cấu hàng bán.')

# --- Phân tích sâu: dữ liệu và cách cộng phần góp giữ theo reporting hiện có ---
tab_year, tab_phase, tab_indices = st.tabs(['So sánh theo năm', 'So sánh theo giai đoạn', 'Chỉ số N/U/P/AOV'])

yr = dp[dp['period_type'] == 'year'].copy()
long = yr.melt(id_vars=['period_code', 'phase_code'], value_vars=['contrib_n', 'contrib_u', 'contrib_p'],
               var_name='phan', value_name='v')
long['Phần'] = long['phan'].map({'contrib_n': 'Số đơn N', 'contrib_u': 'Số món mỗi đơn U', 'contrib_p': 'Giá mỗi món P'})
long['Số tiền'] = long['v'].map(lambda v: trieu(v, 1, signed=True))
long['Năm'] = long['period_code']
bar_nam = alt.Chart(long).mark_bar().encode(
    x=alt.X('Năm:O', title=None, axis=alt.Axis(labelAngle=0)),
    y=alt.Y('v:Q', title=None, stack='zero', axis=alt.Axis(labelExpr=AXIS_TRIEU)),
    color=alt.Color('Phần:N', sort=['Số đơn N', 'Số món mỗi đơn U', 'Giá mỗi món P'],
                    scale=alt.Scale(range=['#1f5f8b', '#e9a23b', '#8e6c8a']),
                    legend=alt.Legend(title=None, orient='top', direction='vertical', columns=1)),
    order=alt.Order('phan:N'),
    tooltip=['Năm', 'Phần', 'Số tiền'],
)
yr['Năm'] = yr['period_code']
yr['R đổi'] = yr['delta_r'].map(lambda v: trieu(v, 1, signed=True))
diem = alt.Chart(yr).mark_point(shape='diamond', size=110, filled=True, color='black').encode(
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
    st.altair_chart((bar_nam + diem).properties(height=320), width='stretch')
    st.caption('Mỗi cột = ba phần góp của một năm so với năm trước (dương trên 0, âm dưới 0). '
               'Hình thoi đen = mức đổi R, bằng tổng ba phần.')
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

with st.expander('Cách đọc & phương pháp'):
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

with st.expander('Giới hạn chi tiết'):
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
