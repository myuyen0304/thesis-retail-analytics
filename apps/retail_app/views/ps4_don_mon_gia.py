import altair as alt
import streamlit as st

from ui.common import GIOI_HAN_CHUNG, hang_the, kpi, load_or_stop, need, notes, page_header
from ui.fmt import AXIS_TRIEU, num, pct, trieu

page_header('PS4: Số đơn, số món, giá', 'Doanh thu đổi vì số đơn (N), số món mỗi đơn (U) hay giá mỗi món (P)?')

dp = load_or_stop('driver_period')       # 1 dòng = 1 năm hoặc 1 giai đoạn PS2
br = load_or_stop('driver_bridge')
yearly = load_or_stop('revenue_yearly')
rule = load_or_stop('driver_rule').iloc[0]
nguong = pct(rule['min_abs_delta_rate'], 0)

# Cảnh báo lấy từ deck slide 10 (plan §3, tiêu chí 4)
st.warning('**Thứ tự tách (N → U → P) ảnh hưởng kết quả. Đây là phép chia số học, chưa chứng minh nguyên nhân.**')

PHAN = {'n': 'số đơn N', 'u': 'số món mỗi đơn U', 'p': 'giá mỗi món P'}
dp['nam'] = dp['start_year'].astype(str) + '→' + dp['end_year'].astype(str)
dp['ten'] = [f'Giai đoạn {c}. {n} ({k})' if t == 'phase' else f'Năm {e} so với {s}'
             for t, c, n, k, s, e in zip(dp['period_type'], dp['period_code'], dp['phase_name'], dp['nam'],
                                         dp['start_year'], dp['end_year'])]
ten_of = dict(zip(dp['period_code'], dp['ten']))

# --- Chọn kỳ: 4 giai đoạn PS2 + từng năm 2014–2022 (mặc định 2019, năm sập) ---
codes = list(dp['period_code'])
code = st.selectbox('Kỳ', codes, index=codes.index('2019') if '2019' in codes else 0, format_func=ten_of.get)
row = dp.set_index('period_code').loc[code]
s0, s1 = int(row['start_year']), int(row['end_year'])

# Feedback 2026-10-01 (F01): số lớn của thẻ đầu là MỨC ĐỔI R, không phải mức R → nhãn "Thay đổi R"; kỳ ghi ngay trên hàng thẻ.
# Feedback PM 2026-10-02: số lớn có đơn vị; 4 thẻ một hàng, đều nhau (ui.common.hang_the).
st.markdown(f'**{s0} → {s1}: doanh thu đổi bao nhiêu, do đâu.** '
            'Dòng màu: % đổi của **chính yếu tố** ghi ở dòng dưới.')
c0, c1, c2, c3 = hang_the('the_ps4', 4)
kpi(c0, 'Thay đổi R', trieu(row['delta_r'], 1, signed=True),
    f'R {s0}: {num(row["r_start"], 2)}; R {s1}: {num(row["r_end"], 2)}. Ba thẻ bên cạnh cộng lại đúng bằng số này.',
    delta=pct(row['r_change_rate'], 1, signed=True), delta_sign=row['r_change_rate'],
    delta_desc=f'R: {num(row["r_start"] / 1e6)} → {num(row["r_end"] / 1e6)} triệu')
kpi(c1, 'Do số đơn N', trieu(row['contrib_n'], 1, signed=True),
    '(N₁ − N₀) × U₀ × P₀: doanh thu đổi bao nhiêu nếu chỉ số đơn đổi, số món mỗi đơn và giá mỗi món giữ như năm đầu.',
    delta=pct(row['n_change_rate'], 1, signed=True), delta_sign=row['n_change_rate'],
    delta_desc=f'N: {num(row["n_start"])} → {num(row["n_end"])} đơn')
kpi(c2, 'Do số món/đơn U', trieu(row['contrib_u'], 1, signed=True),
    'N₁ × (U₁ − U₀) × P₀: phần doanh thu đổi do số món mỗi đơn đổi (số đơn năm cuối, giá năm đầu).',
    delta=pct(row['u_change_rate'], 1, signed=True), delta_sign=row['u_change_rate'],
    delta_desc=f'U: {num(row["u_start"], 2)} → {num(row["u_end"], 2)} món/đơn')
kpi(c3, 'Do giá/món P', trieu(row['contrib_p'], 1, signed=True),
    'N₁ × U₁ × (P₁ − P₀): phần doanh thu đổi do giá mỗi món (sau chiết khấu) đổi, với số đơn và số món năm cuối.',
    delta=pct(row['p_change_rate'], 1, signed=True), delta_sign=row['p_change_rate'],
    delta_desc=f'P: {num(row["p_start"])} → {num(row["p_end"])} mỗi món')
st.caption('**Cách đọc thẻ.** Số lớn = doanh thu đổi bao nhiêu triệu (tiền), ở thẻ đầu là cả mức đổi R, ở ba thẻ sau là '
           'phần do từng yếu tố; ba thẻ N + U + P cộng lại bằng thẻ Thay đổi R (số đã làm tròn có thể lệch 0,1 triệu; '
           'số gốc khớp chính xác, dbt test assert_rpt_decomposition_additive). Dòng màu nhỏ = chính R, N, U hay P '
           'tăng / giảm bao nhiêu % (năm đầu → năm cuối kỳ); các % này **không** cộng lại được thành % đổi của R.')
if row['period_type'] == 'phase':
    st.caption(f'Giai đoạn: số lớn = cộng phần góp của từng năm {s0 + 1}–{s1} (mỗi năm so với năm trước), nên cộng lại đúng '
               f'bằng mức đổi R của giai đoạn ở trang PS2. Dòng % so thẳng năm {s1} với năm {s0}.')


def cau_keo(r) -> str:
    """Câu "kéo xuống / kéo lên" ghép từ cột top_up_driver, top_down_driver, *_change_rate (dbt tính sẵn).
    Phần nào làm R đổi nhiều tiền hơn thì nói trước."""
    parts = []
    for k, chieu in ((r['top_down_driver'], 'kéo xuống'), (r['top_up_driver'], 'kéo lên')):
        if isinstance(k, str):
            rate = r[k + '_change_rate']
            parts.append((abs(r['contrib_' + k]),
                          f'{chieu} nhiều nhất là {PHAN[k]} ({"tăng" if rate > 0 else "giảm"} {pct(abs(rate), 1)}, '
                          f'làm R {trieu(r["contrib_" + k], 1, signed=True)})'))
    return '; '.join(t for _, t in sorted(parts, key=lambda x: -x[0]))


cau = cau_keo(row)
st.markdown(f'**{ten_of[code]}:** doanh thu {"tăng" if row["delta_r"] > 0 else "giảm"} '
            f'{trieu(abs(row["delta_r"]), 1)} ({pct(row["r_change_rate"], 1, signed=True)}); {cau}.')
if row['delta_r_is_small']:
    st.info(f'Mức đổi R của kỳ này nhỏ hơn {nguong} R đầu kỳ: các phần lớn ngược dấu bù trừ nhau. '
            'Đọc số tiền của từng phần, không đọc % đóng góp.')

# --- Thác R đầu → N → U → P → R cuối ---
st.subheader('Từ R đầu kỳ tới R cuối kỳ')
BUOC = {'n': 'Số đơn N', 'u': 'Số món mỗi đơn U', 'p': 'Giá mỗi món P'}
w = need(br[(br['period_code'] == code) & (br['bridge_code'] == 'r_nup')], 'driver_bridge',
         f'của thác doanh thu kỳ {code}').copy()
w['Cột'] = [f'R {int(y)}' if c in ('r_start', 'r_end') else BUOC[c] for c, y in zip(w['step_code'], w['step_year'])]
w['loai'] = ['Tổng' if c in ('r_start', 'r_end') else ('Tăng' if a >= 0 else 'Giảm')
             for c, a in zip(w['step_code'], w['amount'])]
w['Số đầy đủ'] = [num(a, 2) if c in ('r_start', 'r_end') else num(a, 2, signed=True) for c, a in zip(w['step_code'], w['amount'])]
w['nhan'] = [trieu(a, 1) if c in ('r_start', 'r_end') else trieu(a, 1, signed=True)
             for c, a in zip(w['step_code'], w['amount'])]
w['Số tiền'] = w['nhan']    # feedback PM 2026-10-02: bảng ghi gọn, cùng số với nhãn cột
x = alt.X('Cột:N', sort=list(w['Cột']), title=None, axis=alt.Axis(labelAngle=0, labelLimit=160))
bars = alt.Chart(w).mark_bar(size=60).encode(
    x=x,
    y=alt.Y('bar_start:Q', title=None, axis=alt.Axis(labelExpr=AXIS_TRIEU)),
    y2='bar_end:Q',
    color=alt.Color('loai:N', scale=alt.Scale(domain=['Tổng', 'Tăng', 'Giảm'], range=['#1f5f8b', '#2a9d8f', '#d1495b']),
                    legend=alt.Legend(title=None, orient='top')),
    tooltip=['Cột', 'Số đầy đủ'],
)
text = alt.Chart(w).transform_calculate(top='max(datum.bar_start, datum.bar_end)').mark_text(dy=-8, fontSize=12).encode(
    x=x, y='top:Q', text='nhan:N')
st.altair_chart((bars + text).properties(height=360), width='stretch')
right = st.column_config.TextColumn(alignment='right')
st.dataframe(w[['Cột', 'Số tiền']], hide_index=True, column_config={'Số tiền': right})
st.caption('Cột giữa nhỏ so với R nên có thể khó thấy trên biểu đồ; xem số ở bảng trên. Rê chuột lên cột để xem số đầy đủ.')

# --- So sánh giữa các năm (deck slide 10 yêu cầu 5) ---
st.subheader('So sánh giữa các năm')
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
                    scale=alt.Scale(range=['#1f5f8b', '#e9a23b', '#8e6c8a']), legend=alt.Legend(title=None, orient='top')),
    order=alt.Order('phan:N'),
    tooltip=['Năm', 'Phần', 'Số tiền'],
)
yr['Năm'] = yr['period_code']
yr['R đổi'] = yr['delta_r'].map(lambda v: trieu(v, 1, signed=True))
diem = alt.Chart(yr).mark_point(shape='diamond', size=110, filled=True, color='black').encode(
    x='Năm:O', y='delta_r:Q', tooltip=['Năm', 'R đổi'])
st.altair_chart((bar_nam + diem).properties(height=320), width='stretch')
st.caption('Mỗi cột = ba phần góp của một năm so với năm trước (dương nằm trên 0, âm nằm dưới 0). '
           'Hình thoi đen = mức đổi R của năm, đúng bằng tổng ba phần.')

tn = yr[['period_code']].rename(columns={'period_code': 'Năm'})
tn['Giai đoạn'] = yr['phase_code']
tn['R đổi'] = yr['R đổi']
tn['Phần N'] = yr['contrib_n'].map(lambda v: trieu(v, 1, signed=True))
tn['Phần U'] = yr['contrib_u'].map(lambda v: trieu(v, 1, signed=True))
tn['Phần P'] = yr['contrib_p'].map(lambda v: trieu(v, 1, signed=True))
tn['Kéo lên nhiều nhất'] = yr['top_up_driver'].map(lambda k: k.upper() if isinstance(k, str) else '–')
tn['Kéo xuống nhiều nhất'] = yr['top_down_driver'].map(lambda k: k.upper() if isinstance(k, str) else '–')
tn['Ghi chú'] = yr['delta_r_is_small'].map(lambda b: 'R đổi rất nhỏ' if b else '')
st.dataframe(tn, hide_index=True, height='content',
             column_config={c: right for c in ['R đổi', 'Phần N', 'Phần U', 'Phần P']})
st.caption(f'"R đổi rất nhỏ": mức đổi R dưới {nguong} R năm trước, các phần lớn bù trừ nhau; đọc số tiền từng phần.')

# --- So sánh giữa các giai đoạn PS2 ---
st.subheader('So sánh giữa các giai đoạn')
ph = dp[dp['period_type'] == 'phase'].copy()
tp = ph[['ten']].rename(columns={'ten': 'Giai đoạn'})
tp['R đổi'] = ph['delta_r'].map(lambda v: trieu(v, 1, signed=True))
tp['Phần N'] = ph['contrib_n'].map(lambda v: trieu(v, 1, signed=True))
tp['Phần U'] = ph['contrib_u'].map(lambda v: trieu(v, 1, signed=True))
tp['Phần P'] = ph['contrib_p'].map(lambda v: trieu(v, 1, signed=True))
tp['Kéo lên nhiều nhất'] = ph['top_up_driver'].map(lambda k: k.upper() if isinstance(k, str) else '–')
tp['Kéo xuống nhiều nhất'] = ph['top_down_driver'].map(lambda k: k.upper() if isinstance(k, str) else '–')
st.dataframe(tp, hide_index=True, height='content',
             column_config={c: right for c in ['R đổi', 'Phần N', 'Phần U', 'Phần P']})
st.markdown('**Nhận xét so sánh:**\n' + '\n'.join(
    f'- {c}: {cau_keo(r)}.' + (f' Mức đổi R chỉ {trieu(r["delta_r"], 1, signed=True)} (dưới {nguong} R đầu giai đoạn) '
                               'vì hai phần lớn bù trừ nhau.' if r['delta_r_is_small'] else '')
    for c, (_, r) in zip(ph['period_code'], ph.iterrows())))
st.caption('Phần của giai đoạn = cộng phần của từng năm trong giai đoạn (năm Y tính cho giai đoạn có năm đầu < Y ≤ năm cuối, '
           'như mức đổi R ở trang PS2). Tách thẳng một lần từ năm đầu tới năm cuối giai đoạn cho số hơi khác (mỗi phần lệch '
           'dưới 5 triệu) nhưng cùng phần kéo lên, kéo xuống (kiểm trong dbt, test assert_rpt_driver).')

# --- Chỉ số theo năm ---
st.subheader('N, U, P, AOV theo năm')
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
st.dataframe(ti, hide_index=True, height='content',
             column_config={'Năm': st.column_config.NumberColumn(format='%d'),
                            **{c: right for c in ti.columns if c != 'Năm'}})
st.caption('N × U × P = R cho mọi năm (kiểm trong dbt, test assert_rpt_reconciles). Tăng trưởng tính từ 2014: '
           '(1 + tăng N) × (1 + tăng U) × (1 + tăng P) = 1 + tăng R.')

notes(
    cach_doc=[
        'Ba phần cộng lại đúng bằng mức đổi R (kiểm trong dbt, test assert_rpt_decomposition_additive).',
        'Phần dương kéo doanh thu lên, phần âm kéo xuống. Một kỳ có thể có phần lớn ngược dấu bù trừ nhau: xem từng phần, '
        'không chỉ xem tổng.',
        'P là giá bình quân mỗi món sau chiết khấu. P đổi khi giá bán đổi, khi chiết khấu đổi, và khi khách chuyển sang '
        'hàng đắt hơn hay rẻ hơn (cơ cấu sản phẩm).',
        f'Kỳ có mức đổi R dưới {nguong} R đầu kỳ: % đóng góp của từng phần không ổn định, đọc số tiền.',
    ],
    gioi_han=[
        'Thứ tự tách N → U → P ảnh hưởng kết quả: phần tương tác dồn vào phần tách sau. Đây là phép chia số học, '
        'chưa chứng minh nguyên nhân.',
        'Phần của giai đoạn là cộng dồn từng năm (dev đề xuất, chờ BA chốt); tách thẳng từ năm đầu tới năm cuối giai '
        'đoạn cho số hơi khác, cùng kết luận.',
        f'Ngưỡng "mức đổi R nhỏ" {nguong} do dev đề xuất, chờ BA chốt (seed driver_rule).',
        *GIOI_HAN_CHUNG,
    ],
)
