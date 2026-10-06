import altair as alt
import streamlit as st

from ui.common import GIOI_HAN_CHUNG, kpi, kpi_revenue, load_or_stop, notes, page_header, period_label, pick
from ui.fmt import AXIS_PCT1, AXIS_TRIEU, AXIS_TY, num, pct, pp, trieu, ty

page_header('PS1: Đo đúng doanh thu', 'Mỗi tháng, mỗi năm công ty thực nhận bao nhiêu tiền?')

bridge = load_or_stop('revenue_bridge')
total = load_or_stop('revenue_total').set_index('period_code')
yearly = load_or_stop('revenue_yearly')
monthly = load_or_stop('revenue_monthly')

# --- Chọn kỳ: 2 kỳ gộp + từng năm, lấy từ rpt_revenue_bridge ---
periods = bridge.drop_duplicates('period_code')
labels = {r.period_code: period_label(r.period_code, r.period_type, bool(r.is_analysis_period))
          for r in periods.itertuples()}
code = st.selectbox('Kỳ', list(labels), format_func=labels.get)
kind = periods.set_index('period_code').loc[code, 'period_type']
row = (pick(total, code, 'revenue_total', f'của kỳ {code}') if kind == 'total'
       else pick(yearly.set_index(yearly['year'].astype(str)), code, 'revenue_yearly', f'của năm {code}'))

# --- Thẻ KPI của kỳ đã chọn ---
kpi_revenue(row)
c1, c2, _ = st.columns(3)
kpi(c1, 'Tỷ lệ tiền hàng bị hủy', pct(row['cancelled_rate']),
    'Tiền hàng đơn cancelled / G. Càng thấp càng tốt.')
kpi(c2, 'Tỷ lệ chiết khấu', pct(row['discount_rate']),
    'Chiết khấu / tiền hàng của đơn đã giao. Khác % G ở bước chiết khấu của thác (mẫu số là G).')

# --- Thác G → R ---
st.subheader('Từ G xuống R: phần chênh nằm ở đâu?')
# Feedback PM 2026-10-02: số gọn 2–3 chữ số. Kỳ nhiều năm: tỷ, 2 số lẻ (16,43 tỷ). Một năm: các phần bị trừ chỉ vài chục
# triệu, theo tỷ chỉ còn 1 chữ số (−0,04 tỷ) → ghi theo triệu, 1 số lẻ, như bảng tháng bên dưới.
if kind == 'total':
    gon, don_vi, truc = (lambda a: ty(a, 2, signed=a < 0)), 'tỷ, 2 số lẻ', AXIS_TY
else:
    gon, don_vi, truc = (lambda a: trieu(a, 1, signed=a < 0)), 'triệu, 1 số lẻ', AXIS_TRIEU
st.caption(f'Kỳ: {labels[code]}. Nhãn trên cột và bảng: số tiền ({don_vi}) và % so với G. '
           'Rê chuột lên cột để xem số đầy đủ.')
STEP = {'g': 'G: tiền hàng mọi đơn', 'cancelled': 'Đơn hủy', 'returned': 'Đơn trả',
        'undelivered': 'Đơn chưa giao', 'discount': 'Chiết khấu đơn đã giao', 'r': 'R: thực nhận'}
w = bridge[bridge['period_code'] == code].copy()
w['Bước'] = w['step_code'].map(STEP)
w['loai'] = w['step_code'].map(lambda s: 'Tổng' if s in ('g', 'r') else 'Bị trừ')
w['Số tiền'] = w['amount'].map(gon)      # cùng số với nhãn cột
w['Số đầy đủ'] = w['amount'].map(lambda x: num(x, 2, signed=x < 0))
w['% G'] = w['share_of_g'].map(pct)
w['nhan'] = [f'{gon(a)} ({s})' for a, s in zip(w['amount'], w['% G'])]
order = list(w['Bước'])
x = alt.X('Bước:N', sort=order, title=None, axis=alt.Axis(labelAngle=0, labelLimit=160))
bars = alt.Chart(w).mark_bar(size=60).encode(
    x=x,
    y=alt.Y('bar_start:Q', title=None, axis=alt.Axis(labelExpr=truc)),
    y2='bar_end:Q',
    color=alt.Color('loai:N', scale=alt.Scale(domain=['Tổng', 'Bị trừ'], range=['#1f5f8b', '#d1495b']),
                    legend=alt.Legend(title=None, orient='top')),
    tooltip=['Bước', 'Số đầy đủ', '% G'],
)
text = alt.Chart(w).transform_calculate(top='max(datum.bar_start, datum.bar_end)').mark_text(dy=-8, fontSize=12).encode(x=x, y='top:Q', text='nhan:N')   # nhãn đặt trên đỉnh cột
st.altair_chart((bars + text).properties(height=360), width='stretch')
right = st.column_config.TextColumn(alignment='right')
st.dataframe(w[['Bước', 'Số tiền', '% G']], hide_index=True, column_config={'Số tiền': right, '% G': right})

# --- G và R theo tháng, trong kỳ đang chọn (chỉ lọc dòng của rpt_revenue_monthly, không tính lại) ---
st.subheader('G và R theo tháng')
if kind == 'total':
    months = monthly[monthly['year'].between(row['start_year'], row['end_year'])]
else:
    months = monthly[monthly['year'] == int(code)]
mm = months[['month_start_date', 'month', 'g', 'r', 'capture_rate']].copy()
mm['Tháng'] = mm['month_start_date'].dt.strftime('%m/%Y')
mm['thang'] = 'T' + mm['month'].astype(str)
mm['G'] = mm['g'].map(lambda v: num(v, 2))
mm['R'] = mm['r'].map(lambda v: num(v, 2))
mm['R/G'] = mm['capture_rate'].map(pct)
tooltip = ['Tháng', 'G', 'R', 'R/G']
if kind == 'total':
    st.caption(f'Kỳ: {labels[code]}, {len(mm)} tháng. Chọn một năm ở ô **Kỳ** để xem từng tháng trong năm đó.')
    base = alt.Chart(mm).encode(
        x=alt.X('month_start_date:T', title=None, axis=alt.Axis(format='%Y', tickCount='year')), tooltip=tooltip)
    chart = (base.mark_line(color='#c9ced6').encode(y=alt.Y('g:Q', title=None, axis=alt.Axis(labelExpr=AXIS_TRIEU)))
             + base.mark_line(color='#1f5f8b').encode(y='r:Q'))
else:
    first, last = mm['month'].min(), mm['month'].max()
    note = f' Dữ liệu năm này chỉ có từ T{first} đến T{last}.' if len(mm) < 12 else ''
    st.caption(f'Kỳ: {labels[code]}.{note}')
    base = alt.Chart(mm).encode(
        x=alt.X('thang:N', sort=list(mm['thang']), title=None, axis=alt.Axis(labelAngle=0)), tooltip=tooltip)
    chart = (base.mark_bar(color='#c9ced6', size=34).encode(y=alt.Y('g:Q', title=None, axis=alt.Axis(labelExpr=AXIS_TRIEU)))
             + base.mark_bar(color='#1f5f8b', size=20).encode(y='r:Q'))
st.altair_chart(chart.properties(height=300), width='stretch')
st.caption('Xám: G (mọi đơn). Xanh: R (thực nhận). Rê chuột để xem số đầy đủ.')
if kind == 'year':   # một năm: kèm bảng 12 tháng
    tbl = mm[['thang', 'R/G']].rename(columns={'thang': 'Tháng'})
    tbl.insert(1, 'G', mm['g'].map(lambda v: trieu(v, 1)))     # feedback PM 2026-10-02: bảng ghi gọn theo triệu
    tbl.insert(2, 'R', mm['r'].map(lambda v: trieu(v, 1)))
    tbl['Tỷ lệ hủy'] = months['cancelled_rate'].map(pct).values
    tbl['N (số đơn)'] = months['n'].map(num).values
    tbl['R so cùng tháng năm trước'] = months['yoy_rate'].map(lambda v: pct(v, 1, signed=True)).values
    st.dataframe(tbl, hide_index=True, height='content',
                 column_config={c: right for c in tbl.columns if c != 'Tháng'})

# --- R/G và tỷ lệ hủy theo năm ---
st.subheader('Tỷ lệ thực nhận và tỷ lệ hủy theo năm')
st.caption('Hai biểu đồ và bảng dưới đây luôn hiện mọi năm để so sánh'
           + (f'; đường gạch đứng đánh dấu năm {code} đang chọn.' if kind == 'year' else '.'))
y = yearly.copy()
y['nam'] = y['year'].astype(str)
y['R/G'] = y['capture_rate'].map(pct)
y['Tỷ lệ hủy'] = y['cancelled_rate'].map(pct)
opacity = alt.condition('datum.is_analysis_period', alt.value(1.0), alt.value(0.4))
line_opts = dict(point=True, color='#1f5f8b')
c1, c2 = st.columns(2)
for col, field, title in [(c1, 'capture_rate', 'R/G'), (c2, 'cancelled_rate', 'Tỷ lệ hủy')]:
    # trục 1 chữ số thập phân: tỷ lệ hủy chỉ dao động 9,0–9,6%, làm tròn 0 chữ số thì mọi nhãn đều là 9%
    col.markdown(f'**{title}**')
    line = alt.Chart(y).mark_line(**line_opts).encode(
        x=alt.X('nam:O', title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y(f'{field}:Q', title=None, scale=alt.Scale(zero=False), axis=alt.Axis(labelExpr=AXIS_PCT1)),
        opacity=opacity, tooltip=['nam', title],
    )
    if kind == 'year':
        line += alt.Chart(y[y['nam'] == code]).mark_rule(color='#d1495b', strokeDash=[4, 3]).encode(x='nam:O')
    col.altair_chart(line.properties(height=240), width='stretch')

show = yearly[['year']].rename(columns={'year': 'Năm'})
show['G'] = yearly['g'].map(lambda v: ty(v, 2))     # feedback PM 2026-10-02: ghi gọn theo tỷ
show['R'] = yearly['r'].map(lambda v: ty(v, 2))
show['R/G'] = yearly['capture_rate'].map(pct)
show['Tỷ lệ hủy'] = yearly['cancelled_rate'].map(pct)
show['Tỷ lệ hủy so năm trước'] = yearly['cancelled_rate_change'].map(pp)
show['Tỷ lệ chiết khấu'] = yearly['discount_rate'].map(pct)
show['Tăng trưởng R'] = yearly['yoy_rate'].map(lambda v: pct(v, 1, signed=True))
st.dataframe(show, hide_index=True, height='content',   # đủ 11 năm, không cuộn (mặc định chỉ hiện 10 dòng)
             column_config={'Năm': st.column_config.NumberColumn(format='%d'),
                            **{c: right for c in show.columns if c != 'Năm'}})

notes(
    cach_doc=[
        'Tỷ lệ thực nhận R/G càng gần 100% càng ít thất thoát.',
        'Thác G → R: cột đỏ là phần bị trừ khỏi G (đơn hủy, đơn trả, đơn chưa giao, chiết khấu của đơn đã giao). '
        'Bốn phần cộng lại đúng bằng G − R (dbt test `assert_rpt_total`); số trên bảng đã làm tròn nên cộng lại có thể lệch ở chữ số cuối.',
        'Tỷ lệ tiền hàng bị hủy càng thấp càng tốt. Đây là tỷ trọng **giá trị**, khác tỷ lệ **số đơn** bị hủy.',
        'Chiết khấu có hai con số: thẻ **Tỷ lệ chiết khấu** chia cho tiền hàng của đơn đã giao; '
        'nhãn % trên thác chia cho G. Cùng một khoản tiền, khác mẫu số nên hai số khác nhau.',
        'Tăng trưởng R = R năm nay / R năm trước − 1, dương là tăng; tính từ năm có năm trước đủ 12 tháng.',
    ],
    gioi_han=[
        'R khớp 100% số tiền khách thanh toán (payment_value) của đơn đã giao (dbt test `assert_rpt_reconciles`).',
        'Không trừ thêm tiền hoàn (refund) vì đơn returned đã bị loại hẳn khỏi R.',
        'Chiết khấu (discount_amount) tính cho cả dòng hàng (deck slide 3).',
        *GIOI_HAN_CHUNG,
    ],
)
