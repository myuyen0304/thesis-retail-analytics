import altair as alt
import streamlit as st

from ui.common import GIOI_HAN_CHUNG, kpi_revenue, load_or_stop, need, notes, page_header
from ui.fmt import AXIS_TY, num, pct, ty

page_header('Tổng quan doanh thu', 'Công ty bán được bao nhiêu, và thực nhận bao nhiêu?')

total = load_or_stop('revenue_total').set_index('period_code')
yearly = load_or_stop('revenue_yearly')
# kỳ toàn bộ dữ liệu (số của deck slide 4), dùng ở phần Cách đọc
deck = need(total[~total['is_analysis_period']], 'revenue_total', 'của kỳ toàn bộ dữ liệu').iloc[0]

# --- Thẻ KPI: toàn bộ dữ liệu (số của deck slide 4) và kỳ phân tích ---
for code, row in total.iterrows():
    kind = 'kỳ phân tích' if row['is_analysis_period'] else 'toàn bộ dữ liệu'
    st.markdown(f'**{row["start_year"]}–{row["end_year"]} ({kind})**')
    kpi_revenue(row)

# --- R và G theo năm ---
st.subheader('G và R theo năm')
chart_df = yearly[['year', 'g', 'r', 'is_analysis_period']].copy()
chart_df['nam'] = chart_df['year'].astype(str)
chart_df['G'] = chart_df['g'].map(lambda x: num(x, 2))
chart_df['R'] = chart_df['r'].map(lambda x: num(x, 2))
chart_df['R/G'] = yearly['capture_rate'].map(pct)
tooltip = ['nam', 'G', 'R', 'R/G']
opacity = alt.condition('datum.is_analysis_period', alt.value(1.0), alt.value(0.4))
base = alt.Chart(chart_df).encode(x=alt.X('nam:O', title=None, axis=alt.Axis(labelAngle=0)), tooltip=tooltip)
bars_g = base.mark_bar(color='#c9ced6', size=34).encode(
    y=alt.Y('g:Q', title=None, axis=alt.Axis(labelExpr=AXIS_TY)), opacity=opacity)
bars_r = base.mark_bar(color='#1f5f8b', size=20).encode(y='r:Q', opacity=opacity)
st.altair_chart((bars_g + bars_r).properties(height=320), width='stretch')
first = yearly.iloc[0]
st.caption(f'Cột xám nhạt: G (mọi đơn). Cột xanh: R (đơn đã giao, đã trừ chiết khấu). '
           f'Năm {first["year"]} tô nhạt: chưa đủ năm, chỉ để tham khảo. Rê chuột lên cột để xem số đầy đủ.')

# --- Bảng theo năm (cột số canh phải) ---
show = yearly[['year']].rename(columns={'year': 'Năm'})
show['G (mọi đơn)'] = yearly['g'].map(lambda x: ty(x, 2))
show['R (đơn đã giao)'] = yearly['r'].map(lambda x: ty(x, 2))
show['R/G'] = yearly['capture_rate'].map(pct)
show['N (số đơn)'] = yearly['n'].map(num)
show['Tăng trưởng R'] = yearly['yoy_rate'].map(lambda x: pct(x, 1, signed=True))
right = st.column_config.TextColumn(alignment='right')
st.dataframe(
    show, hide_index=True, height='content',   # đủ 11 năm, không cuộn (mặc định chỉ hiện 10 dòng)
    column_config={'Năm': st.column_config.NumberColumn(format='%d'),
                   **{c: right for c in show.columns if c != 'Năm'}},
)

# --- Lối sang 5 trang PS ---
st.subheader('Đi tiếp theo 5 câu hỏi')
st.page_link('views/ps1_do_dung.py', label='PS1: Mỗi tháng, mỗi năm công ty thực nhận bao nhiêu tiền?')
st.page_link('views/ps2_xu_huong.py', label='PS2: Doanh thu tăng hay giảm, giai đoạn nào đổi hướng?')
st.page_link('views/ps3_nhip_lich.py', label='PS3: Doanh thu dồn vào tháng nào, ngày nào?')
st.page_link('views/ps4_don_mon_gia.py', label='PS4: Đổi vì số đơn, số món mỗi đơn hay giá mỗi món?')
st.page_link('views/ps5_nhom.py', label='PS5: Ngành hàng, khu vực, kênh nào kéo lên hoặc xuống?')

notes(
    cach_doc=[
        f'G cộng cả đơn hủy, đơn trả, đơn chưa giao và chưa trừ chiết khấu nên cao hơn số tiền thật nhận được: '
        f'gộp {deck["start_year"]}–{deck["end_year"]}, G là {ty(deck["g"])}, R chỉ {ty(deck["r"])} '
        f'({pct(deck["capture_rate"])}). Phần chênh nằm ở đâu: xem trang PS1.',
        'Tăng trưởng R = R năm nay / R năm trước − 1; để trống ở những năm chưa có năm trước đủ 12 tháng.',
    ],
    gioi_han=GIOI_HAN_CHUNG,
)
