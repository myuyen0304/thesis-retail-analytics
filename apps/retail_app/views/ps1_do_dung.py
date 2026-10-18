import altair as alt
import streamlit as st

from ui.common import GIOI_HAN_CHUNG, info_strip, kpi, load_or_stop, need, period_label, pick, url_choice
from ui.fmt import AXIS_PCT1, AXIS_TRIEU, AXIS_TY, num, pct, pp, trieu, ty

st.title('PS1 · Từ tổng tiền hàng đến doanh thu')
st.markdown('Phần chênh giữa G và R đến từ đâu?')

bridge = load_or_stop('revenue_bridge')
total = load_or_stop('revenue_total').set_index('period_code')
yearly = load_or_stop('revenue_yearly')
monthly = load_or_stop('revenue_monthly')

# --- Chọn kỳ: 2 kỳ gộp + từng năm, lấy từ rpt_revenue_bridge ---
periods = bridge.drop_duplicates('period_code')
labels = {r.period_code: period_label(r.period_code, r.period_type, bool(r.is_analysis_period))
          for r in periods.itertuples()}
code = st.selectbox('Kỳ', list(labels), index=url_choice('ky', list(labels), 0, 'kỳ'), format_func=labels.get)
kind = periods.set_index('period_code').loc[code, 'period_type']
row = (pick(total, code, 'revenue_total', f'của kỳ {code}') if kind == 'total'
       else pick(yearly.set_index(yearly['year'].astype(str)), code, 'revenue_yearly', f'của năm {code}'))
st.caption(f'Đang xem: {labels[code]} · Đơn vị tiền: VND (tỷ = tỷ đồng, triệu = triệu đồng)')

with st.expander('Định nghĩa & phạm vi dữ liệu'):
    info_strip()
    st.markdown(
        '**Cách đọc:** R/G là tỷ lệ doanh thu đơn đã giao trên tiền hàng mọi đơn. '
        'G−R gồm hủy, trả, chưa giao và chiết khấu; không đồng nhất với thất thoát. '
        'Bốn khoản trên thác cộng lại đúng bằng G−R (dbt test `assert_rpt_total`); '
        'số làm tròn có thể lệch ở chữ số cuối.\n\n'
        'Cột đỏ là phần bị trừ khỏi G. Tỷ lệ hủy càng thấp càng tốt; đây là tỷ trọng **giá trị**, '
        'khác tỷ lệ số đơn hủy. '
        'Chiết khấu trên thác chia cho G, còn tỷ lệ chiết khấu chia cho tiền hàng đơn đã giao. '
        'Tăng trưởng R = R năm nay / R năm trước − 1, dương là tăng; '
        'tính từ năm có năm trước đủ 12 tháng.'
    )
    st.markdown('**Giới hạn:**')
    st.markdown('\n'.join(f'- {item}' for item in [
        'R khớp 100% số tiền khách thanh toán (`payment_value`) của đơn đã giao (dbt test `assert_rpt_reconciles`).',
        'Không trừ thêm tiền hoàn (`refund`) vì đơn returned đã bị loại hẳn khỏi R.',
        'Chiết khấu (`discount_amount`) tính cho cả dòng hàng (deck slide 3).',
        *GIOI_HAN_CHUNG,
    ]))

# --- Bốn số chính của kỳ đã chọn ---
c1, c2, c3, c4 = st.columns(4)
kpi(c1, 'G: tiền hàng mọi đơn', ty(row['g'], 2),
    f'Mọi đơn, chưa trừ chiết khấu (= sales.csv). Số đầy đủ: {num(row["g"], 2)}.')
kpi(c2, 'R: doanh thu đơn đã giao', ty(row['r'], 2),
    f'Chỉ đơn đã giao, sau chiết khấu, theo ngày đặt hàng. Số đầy đủ: {num(row["r"], 2)}.')
kpi(c3, 'Chênh lệch G − R', ty(row['g'] - row['r'], 2),
    f'G trừ R cùng kỳ; gồm bốn khoản trên thác. Số đầy đủ: {num(row["g"] - row["r"], 2)}.')
kpi(c4, 'Tỷ lệ R/G', pct(row['capture_rate'], 1),
    'Doanh thu đơn đã giao chia cho tiền hàng mọi đơn cùng kỳ.')

# --- Thác G → R ---
st.subheader('Từ G đến R')
# Feedback PM 2026-10-02: số gọn 2–3 chữ số. Kỳ nhiều năm: tỷ, 2 số lẻ (16,43 tỷ). Một năm: các phần bị trừ chỉ vài chục
# triệu, theo tỷ chỉ còn 1 chữ số (−0,04 tỷ) → ghi theo triệu, 1 số lẻ, như bảng tháng bên dưới.
if kind == 'total':
    gon, don_vi, truc = (lambda a: ty(a, 2, signed=a < 0)), 'tỷ, 2 số lẻ', AXIS_TY
else:
    gon, don_vi, truc = (lambda a: trieu(a, 1, signed=a < 0)), 'triệu, 1 số lẻ', AXIS_TRIEU
STEP = {'g': 'G: tiền hàng mọi đơn', 'cancelled': 'Đơn hủy', 'returned': 'Đơn trả',
        'undelivered': 'Đơn chưa giao', 'discount': 'Chiết khấu đơn đã giao', 'r': 'R: doanh thu đơn đã giao'}
SHORT_STEP = {'g': 'G', 'cancelled': 'Hủy', 'returned': 'Trả', 'undelivered': 'Chưa giao',
              'discount': 'CK', 'r': 'R'}
w = bridge[bridge['period_code'] == code].copy()
# Bảng lệch (chỉ còn dòng G / R của kỳ): không có khoản chênh nào để tìm "khoản lớn nhất" → cảnh báo rồi dừng.
need(w[w['step_code'].isin(['cancelled', 'returned', 'undelivered', 'discount'])], 'revenue_bridge',
     f'các khoản chênh G → R của kỳ {code}')
w['Bước'] = w['step_code'].map(STEP)
w['Nhãn'] = w['step_code'].map(SHORT_STEP)
w['loai'] = w['step_code'].map(lambda s: 'Tổng' if s in ('g', 'r') else 'Bị trừ')
w['Số tiền'] = w['amount'].map(gon)      # cùng số với nhãn cột
w['Số đầy đủ'] = w['amount'].map(lambda x: num(x, 2, signed=x < 0))
w['% G'] = w['share_of_g'].map(pct)
w['nhan'] = (w['amount'].map(lambda a: num(a / 1e9, 2, signed=a < 0)) if kind == 'total'
             else w['amount'].map(lambda a: num(a / 1e6, 1, signed=a < 0)))
order = list(w['Nhãn'])
x = alt.X('Nhãn:N', sort=order, title=None,
          axis=alt.Axis(labelAngle=0, labelLimit=70, labelFontSize=10, labelOverlap=False))
bars = alt.Chart(w).mark_bar().encode(
    x=x,
    y=alt.Y('bar_start:Q', title=None, axis=alt.Axis(labelExpr=truc)),
    y2='bar_end:Q',
    color=alt.Color('loai:N', scale=alt.Scale(domain=['Tổng', 'Bị trừ'], range=['#1f5f8b', '#d1495b']),
                    legend=alt.Legend(title=None, orient='top')),
    tooltip=['Bước', 'Số đầy đủ', '% G'],
)
text = alt.Chart(w).transform_calculate(top='max(datum.bar_start, datum.bar_end)').mark_text(dy=-8, fontSize=10).encode(x=x, y='top:Q', text='nhan:N')
right = st.column_config.TextColumn(alignment='right')
left, side = st.columns([2, 1], gap='medium')
with left:
    st.caption(f'{labels[code]} · Nhãn cột: {don_vi}; CK = chiết khấu. '
               'Rê chuột để xem số đầy đủ và % của G.')
    st.altair_chart((bars + text).properties(height=420), width='stretch')
    with st.expander('Xem số liệu làm căn cứ'):
        st.dataframe(w[['Bước', 'Số tiền', '% G']], hide_index=True, width='stretch',
                     column_config={'Số tiền': right, '% G': right})
        st.caption(f'Tỷ lệ tiền hàng bị hủy: {pct(row["cancelled_rate"])} (đơn hủy / G). '
                   f'Tỷ lệ chiết khấu: {pct(row["discount_rate"])} (chiết khấu / tiền hàng đơn đã giao).')
with side:
    with st.container(border=True):
        st.markdown('**Giải thích kết quả**')
        st.caption('Tóm tắt theo quy tắc từ số liệu kỳ đang chọn')
        parts = w[w['step_code'].isin(['cancelled', 'returned', 'undelivered', 'discount'])]
        largest = parts.loc[parts['amount'].abs().idxmax()]
        st.markdown(f'- **Chênh lệch:** G cao hơn R {ty(row["g"] - row["r"], 2)}; R/G là {pct(row["capture_rate"])}.')
        st.markdown(f'- **Khoản lớn nhất:** {largest["Bước"].lower()} {gon(abs(largest["amount"]))}, '
                    f'bằng {pct(largest["share_of_g"])} của G.')
        st.markdown('- **Giới hạn:** đây là phân rã theo trạng thái đơn và chiết khấu, '
                    'không phải thất thoát hay dòng tiền theo ngày thanh toán.')

# --- Chỉ lọc các dòng reporting theo kỳ đã chọn; không tính lại KPI ---
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
    base = alt.Chart(mm).encode(
        x=alt.X('month_start_date:T', title=None, axis=alt.Axis(format='%Y', tickCount='year')), tooltip=tooltip)
    chart = (base.mark_line(color='#c9ced6').encode(y=alt.Y('g:Q', title=None, axis=alt.Axis(labelExpr=AXIS_TRIEU)))
             + base.mark_line(color='#1f5f8b').encode(y='r:Q'))
else:
    first, last = mm['month'].min(), mm['month'].max()
    note = f' Dữ liệu năm này chỉ có từ T{first} đến T{last}.' if len(mm) < 12 else ''
    base = alt.Chart(mm).encode(
        x=alt.X('thang:N', sort=list(mm['thang']), title=None, axis=alt.Axis(labelAngle=0)), tooltip=tooltip)
    chart = (base.mark_bar(color='#c9ced6').encode(y=alt.Y('g:Q', title=None, axis=alt.Axis(labelExpr=AXIS_TRIEU)))
             + base.mark_bar(color='#1f5f8b', size=12).encode(y='r:Q'))
tbl = mm[['thang', 'R/G']].rename(columns={'thang': 'Tháng'})
if kind == 'total':
    tbl['Tháng'] = mm['Tháng']
tbl.insert(1, 'G', mm['g'].map(lambda v: trieu(v, 1)))
tbl.insert(2, 'R', mm['r'].map(lambda v: trieu(v, 1)))
tbl['Tỷ lệ hủy'] = months['cancelled_rate'].map(pct).values
tbl['N (số đơn)'] = months['n'].map(num).values
tbl['R so cùng tháng năm trước'] = months['yoy_rate'].map(lambda v: pct(v, 1, signed=True)).values

# --- R/G và tỷ lệ hủy theo năm ---
y = yearly.copy()
y['nam'] = y['year'].astype(str)
y['R/G'] = y['capture_rate'].map(pct)
y['Tỷ lệ hủy'] = y['cancelled_rate'].map(pct)
opacity = alt.condition('datum.is_analysis_period', alt.value(1.0), alt.value(0.4))
line_opts = dict(point=True, color='#1f5f8b')
show = yearly[['year']].rename(columns={'year': 'Năm'})
show['G'] = yearly['g'].map(lambda v: ty(v, 2))     # feedback PM 2026-10-02: ghi gọn theo tỷ
show['R'] = yearly['r'].map(lambda v: ty(v, 2))
show['R/G'] = yearly['capture_rate'].map(pct)
show['Tỷ lệ hủy'] = yearly['cancelled_rate'].map(pct)
show['Tỷ lệ hủy so năm trước'] = yearly['cancelled_rate_change'].map(pp)
show['Tỷ lệ chiết khấu'] = yearly['discount_rate'].map(pct)
show['Tăng trưởng R'] = yearly['yoy_rate'].map(lambda v: pct(v, 1, signed=True))

tab_month, tab_year, tab_table = st.tabs(['Theo tháng', 'Tỷ lệ theo năm', 'Bảng số liệu'])
with tab_month:
    st.caption(f'{labels[code]} · {len(mm)} tháng.' + (note if kind == 'year' else ' Chọn một năm để xem từng tháng rõ hơn.'))
    st.altair_chart(chart.properties(height=300), width='stretch')
    st.caption('Xám: G (mọi đơn). Xanh: R (doanh thu đơn đã giao). Rê chuột để xem số đầy đủ.')

with tab_year:
    st.caption('Luôn hiện mọi năm để so sánh; năm 2012 chưa đủ năm.'
               + (f' Đường gạch đứng đánh dấu năm {code} đang chọn.' if kind == 'year' else ''))
    c1, c2 = st.columns(2)
    for col, field, title in [(c1, 'capture_rate', 'R/G'), (c2, 'cancelled_rate', 'Tỷ lệ hủy')]:
        col.markdown(f'**{title}**')
        line = alt.Chart(y).mark_line(**line_opts).encode(
            x=alt.X('nam:O', title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y(f'{field}:Q', title=None, scale=alt.Scale(zero=False), axis=alt.Axis(labelExpr=AXIS_PCT1)),
            opacity=opacity, tooltip=['nam', title],
        )
        if kind == 'year':
            line += alt.Chart(y[y['nam'] == code]).mark_rule(color='#d1495b', strokeDash=[4, 3]).encode(x='nam:O')
        col.altair_chart(line.properties(height=240), width='stretch')
    st.caption('Tỷ lệ hủy là tỷ trọng tiền hàng đơn hủy / G; năm 2012 chỉ để tham khảo.')

with tab_table:
    st.markdown('**Theo tháng trong kỳ đang chọn**')
    st.dataframe(tbl, hide_index=True, height=350, width='stretch',
                 column_config={c: right for c in tbl.columns if c != 'Tháng'})
    st.download_button('Tải bảng tháng (CSV)', tbl.to_csv(index=False).encode('utf-8-sig'),
                       file_name=f'ps1_thang_{code}.csv', mime='text/csv', key='ps1_download_month')
    st.markdown('**Theo năm · toàn bộ dữ liệu để đối chiếu**')
    st.dataframe(show, hide_index=True, height='content', width='stretch',
                 column_config={'Năm': st.column_config.NumberColumn(format='%d'),
                                **{c: right for c in show.columns if c != 'Năm'}})
    st.download_button('Tải bảng năm (CSV)', show.to_csv(index=False).encode('utf-8-sig'),
                       file_name='ps1_nam.csv', mime='text/csv', key='ps1_download_year')
