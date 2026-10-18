import altair as alt
import pandas as pd
import streamlit as st

from ai_explain import page_explain
from ui.ai_panel import ai_panel
from ui.common import GIOI_HAN_CHUNG, hang_the, kpi, load_or_stop, need, need_keys, pick, url_choice
from ui.fmt import AXIS_PCT1, AXIS_TRIEU, num, pct, trieu


st.title('PS5 · Nhóm đóng góp vào biến động doanh thu')
st.markdown('Ngành hàng, khu vực hoặc kênh nào đóng góp nhiều nhất vào mức tăng/giảm?')

seg = load_or_stop('segment_yearly')  # Một nhóm của một chiều trong một năm
yearly = load_or_stop('revenue_yearly')
dp = load_or_stop('driver_period')
br = load_or_stop('driver_bridge')
rule = load_or_stop('driver_rule').iloc[0]
load_or_stop('build_info')
nguong = pct(rule['min_abs_delta_rate'], 0)

DIM = {'category': 'Ngành hàng', 'region': 'Khu vực', 'acquisition_channel': 'Kênh thu hút khách'}
dims = [d for d in DIM if d in set(seg['dimension_name'])]
# Bảng lệch (chỉ còn năm đầu, chưa có xếp hạng đóng góp): không có năm nào để chọn → cảnh báo rồi dừng.
nams = sorted(need(seg[seg['delta_r_rank'].notna()], 'segment_yearly',
                   'có xếp hạng đóng góp so với năm trước')['year'].unique().tolist())
c_dim, c_nam = st.columns([2, 1], gap='medium')
dim = c_dim.radio('Chiều phân tích', dims, index=url_choice('chieu', dims, 0, 'chiều'),
                  format_func=DIM.get, horizontal=True)
nam = c_nam.selectbox('Năm so với năm trước', nams,
                      index=url_choice('nam', nams, nams.index(2019) if 2019 in nams else len(nams) - 1, 'năm'))
ten_chieu = DIM[dim].lower()
st.caption(f'Đang xem: R · {DIM[dim]} · {nam - 1} → {nam} · Đơn vị tiền: VND (triệu = triệu đồng)')
st.caption('Mỗi chiều là một cách phân chia cùng doanh thu R; không cộng đóng góp giữa các chiều.')
with st.expander('Định nghĩa & phạm vi dữ liệu'):
    # Dải thông tin chung do report_reads vẽ trong "Nguồn dữ liệu & kết nối" (_collapse_source bên dưới), như PS3/PS4.
    st.markdown('**R** là doanh thu đơn đã giao sau chiết khấu, gom theo ngày đặt hàng. '
                'Mỗi nhóm trong một chiều cộng thành R toàn công ty cùng năm. '
                'Chiều khu vực dùng nhãn Central / East / West của dữ liệu mô phỏng; '
                'kênh thu hút khách gắn với khách hàng, không phải nguồn của từng đơn.')
st.session_state._collapse_source = True

y = pick(yearly.set_index('year'), nam, 'revenue_yearly', f'của năm {nam}')
s = need(seg[(seg['dimension_name'] == dim) & (seg['year'] == nam)], 'segment_yearly',
         f'của {ten_chieu} năm {nam}').sort_values('delta_r_rank').copy()
nho = bool(s['delta_r_is_small'].iloc[0])
giam = y['delta_r'] < 0
huong_ct = 'giảm' if giam else 'tăng'
dau, cuoi = s.iloc[0], s.iloc[-1]
so_tang, so_giam, so_nhom = (int(dau[k]) for k in ('n_groups_up', 'n_groups_down', 'n_groups'))


def dong_gop(r) -> str:
    """Giữ đúng tỷ lệ do reporting tính; không dùng tỷ lệ khi mẫu số quá nhỏ."""
    c = r['contribution_to_delta']
    if pd.isna(c):
        return '% góp không xác định'
    if nho:
        return '% góp không ổn định'
    return f'{pct(c)} tổng mức {huong_ct}'


def hien_ty_le_dong_gop(c) -> str:
    if pd.isna(c):
        return 'Không xác định'
    return pct(c) + (' (không ổn định)' if nho else '')


def the_nhom(col, label: str, r, co: bool, khong_co: str, so: int, huong: str) -> None:
    if co:
        kpi(col, label, r['dimension_value'],
            f'R {nam - 1}: {trieu(r["r_prior_year"], 1)}; R {nam}: {trieu(r["r"], 1)}. '
            f'Mức đổi của nhóm: {trieu(r["delta_r"], 1, signed=True)}. '
            f'% đóng góp = mức đổi nhóm ÷ mức đổi R toàn công ty; âm khi ngược chiều. '
            f'Không xác định nếu R không đổi; không ổn định nếu R đổi dưới {nguong} R năm trước.',
            delta=trieu(r['delta_r'], 1, signed=True), delta_sign=r['delta_r'], delta_desc=dong_gop(r))
    else:
        kpi(col, label, 'Không có',
            khong_co, delta=f'{so}/{so_nhom} nhóm {huong}', delta_sign=None,
            delta_desc=f'Không có nhóm {huong}')


# Bốn số chính cùng kỳ và cùng chiều. Thẻ C/F nằm trong tab vì chỉ có phạm vi toàn công ty.
c1, c2, c3, c4 = hang_the('the_ps5', 4)
kpi(c1, 'Thay đổi R toàn công ty', trieu(y['delta_r'], 1, signed=True),
    f'R {nam - 1}: {num(y["r_prior_year"], 2)}; R {nam}: {num(y["r"], 2)}. '
    'Tổng mức đổi của các nhóm trong một chiều bằng mức này.',
    delta=pct(y['yoy_rate'], 1, signed=True), delta_sign=y['yoy_rate'],
    delta_desc=f'R: {num(y["r_prior_year"] / 1e6)} → {num(y["r"] / 1e6)} triệu')
the_nhom(c2, f'{DIM[dim]} tăng nhiều nhất', dau, dau['delta_r'] > 0,
         f'Năm {nam} không có {ten_chieu} tăng.', so_tang, 'tăng')
the_nhom(c3, f'{DIM[dim]} giảm nhiều nhất', cuoi, cuoi['delta_r'] < 0,
         f'Năm {nam} không có {ten_chieu} giảm.', so_giam, 'giảm')
kpi(c4, 'Số nhóm tăng / giảm', f'{so_tang} tăng / {so_giam} giảm',
    f'Trong {so_nhom} {ten_chieu}; nhóm có mức đổi bằng 0 không tính là tăng hoặc giảm.',
    delta=f'{so_nhom} nhóm', delta_sign=None,
    delta_desc=f'{so_nhom - so_tang - so_giam} không đổi')

# Số nhóm là biến động R bằng tiền; hạng trong bảng reporting xếp từ tăng nhiều nhất đến giảm nhiều nhất.
s['Nhóm'] = s['dimension_value']
s['Hướng'] = s['delta_r'].map(lambda v: 'Tăng' if v > 0 else ('Giảm' if v < 0 else 'Không đổi'))
s['Đổi'] = s['delta_r'].map(lambda v: trieu(v, 1, signed=True))
chart_data = s.sort_values('delta_r', key=lambda v: v.abs(), ascending=False)
chart_data['moc_nhan'] = 0  # Nhãn phần giảm đặt sát mốc 0 để không đè tên nhóm trên màn hình hẹp.
order = chart_data['Nhóm'].tolist()
peak = max(float(s['delta_r'].abs().max()), 1)
axis = alt.X('delta_r:Q', title='Thay đổi R (triệu đồng)', axis=alt.Axis(labelExpr=AXIS_TRIEU),
             scale=alt.Scale(domain=[-peak * 1.28, peak * 1.28]))
group = alt.Y('Nhóm:N', sort=order, title=None,
              axis=alt.Axis(labelLimit=140, labelFontSize=11))
bars = alt.Chart(chart_data).mark_bar(size=24).encode(
    x=axis, y=group,
    color=alt.Color('Hướng:N', scale=alt.Scale(domain=['Tăng', 'Giảm', 'Không đổi'],
                                            range=['#2a9d8f', '#d1495b', '#8d99a6']),
                    legend=alt.Legend(title=None, orient='top')),
    tooltip=[alt.Tooltip('Nhóm:N'), alt.Tooltip('Hướng:N'),
             alt.Tooltip('Đổi:N', title='Thay đổi R')])
zero = alt.Chart(pd.DataFrame({'moc': [0]})).mark_rule(color='#687480', strokeWidth=1.5).encode(x='moc:Q')
positive = alt.Chart(chart_data[chart_data['delta_r'] >= 0]).mark_text(
    align='left', dx=5, fontSize=11).encode(x=axis, y=group, text='Đổi:N')
negative = alt.Chart(chart_data[chart_data['delta_r'] < 0]).mark_text(
    align='left', dx=5, fontSize=11).encode(
        x=alt.X('moc_nhan:Q', axis=None, scale=alt.Scale(domain=[-peak * 1.28, peak * 1.28])),
        y=group, text='Đổi:N')

st.subheader(f'Thay đổi R theo {ten_chieu}')
left, side = st.columns([2, 1], gap='medium')
with left:
    st.caption(f'{nam - 1} → {nam} · Xếp theo độ lớn tuyệt đối của mức đổi R; '
               'thanh xanh tăng, thanh đỏ giảm, đường dọc là 0. Số cạnh thanh: triệu đồng.')
    st.altair_chart(alt.layer(zero, bars, positive, negative).properties(
        height=max(280, 43 * len(s) + 50)), width='stretch')
    if y['delta_r'] == 0:
        st.info('R toàn công ty không đổi; % đóng góp không xác định vì mẫu số bằng 0. Đọc số tiền từng nhóm.')
    elif nho:
        st.info(f'R cả công ty đổi dưới {nguong} R năm trước; % đóng góp không ổn định. Đọc số tiền của từng nhóm.')
    # deck slide 12 (plan §3, tiêu chí 4): luôn hiện ngay dưới biểu đồ, không chỉ trong phần mở rộng
    st.caption('Mức đổi của từng nhóm là phần chia số học của cùng mức đổi R, chưa phải nguyên nhân.')
    if dim == 'region':
        st.caption('Central / East / West chỉ là nhãn khu vực mô phỏng, không phải tỉnh/thành thực.')
    elif dim == 'acquisition_channel':
        st.caption('Kênh thu hút khách gắn với khách hàng, không phải kênh của từng đơn hàng.')
    with st.expander('Xem số liệu làm căn cứ'):
        can_cu = s[['Nhóm', 'Đổi']].rename(columns={'Đổi': 'Thay đổi R'})
        can_cu['% đóng góp vào mức đổi tổng'] = s['contribution_to_delta'].map(hien_ty_le_dong_gop)
        st.dataframe(can_cu, hide_index=True, width='stretch', height='content')
        st.caption('% đóng góp = thay đổi R của nhóm ÷ thay đổi R toàn công ty; '
                   'có thể âm hoặc trên 100% khi các nhóm bù trừ. Mức đổi toàn công ty bằng 0 thì tỷ lệ không xác định.')
with side:
    with st.container(border=True):
        st.markdown('**Tóm tắt từ số liệu**')
        st.caption('Câu viết sẵn theo quy tắc từ số liệu, không do AI viết')
        if y['delta_r'] == 0:
            st.markdown(f'- **R toàn công ty không đổi** từ {nam - 1} đến {nam}.')
        else:
            st.markdown(f'- **R toàn công ty {huong_ct}** {trieu(abs(y["delta_r"]), 1)} '
                        f'({pct(y["yoy_rate"], 1, signed=True)}).')
        if s['delta_r'].abs().max() == 0:
            st.markdown('- **Các nhóm:** không nhóm nào thay đổi R.')
        else:
            main = chart_data.iloc[0]
            contribution = (f' ({pct(main["contribution_to_delta"])} mức {huong_ct} của cả công ty)'
                            if not nho and pd.notna(main['contribution_to_delta']) else '')
            st.markdown(f'- **Đổi nhiều nhất:** {main["dimension_value"]} '
                        f'{"tăng" if main["delta_r"] > 0 else "giảm"} '
                        f'{trieu(abs(main["delta_r"]), 1)}{contribution}.')
            opposite = cuoi if y['delta_r'] > 0 else dau
            if y['delta_r'] == 0:
                st.markdown('- **Bù trừ:** thay đổi giữa các nhóm triệt tiêu nhau trong tổng R.')
            elif opposite['delta_r'] * y['delta_r'] < 0:
                st.markdown(f'- **Bù trừ:** {opposite["dimension_value"]} '
                            f'{"tăng" if opposite["delta_r"] > 0 else "giảm"} '
                            f'{trieu(abs(opposite["delta_r"]), 1)} ngược chiều R toàn công ty.')
        if y['delta_r'] == 0:
            st.markdown('- **Giới hạn:** % đóng góp không xác định khi R toàn công ty không đổi.')
        elif nho:
            st.markdown('- **Giới hạn:** mức đổi R nhỏ làm % đóng góp không ổn định; ưu tiên số tiền.')
        else:
            st.markdown('- **Giới hạn:** đây là phần đóng góp số học, chưa chứng minh nguyên nhân.')
    ai_panel(page_explain.request_ps5(dim, nam))

# Bảng đầy đủ chỉ xuất hiện một lần; bảng ngắn ở trên là căn cứ trực tiếp cho biểu đồ.
tb = s[['delta_r_rank', 'Nhóm']].rename(columns={'delta_r_rank': 'Hạng'})
tb['Hạng'] = tb['Hạng'].astype(int)
tb[f'R {nam - 1}'] = s['r_prior_year'].map(lambda v: trieu(v, 1))
tb[f'R {nam}'] = s['r'].map(lambda v: trieu(v, 1))
tb['Đổi (tiền)'] = s['Đổi']
tb['Đổi (%)'] = s['yoy_rate'].map(lambda v: pct(v, 1, signed=True))
tb[f'Tỷ trọng {nam}'] = s['share'].map(pct)
tb['Dịch chuyển tỷ trọng'] = s['share_shift_pp'].map(lambda v: num(v, 2, signed=True) + ' điểm %')
tb['% đóng góp vào mức đổi tổng'] = s['contribution_to_delta'].map(hien_ty_le_dong_gop)
right = st.column_config.TextColumn(alignment='right')

tab_share, tab_cf, tab_data = st.tabs(['Tỷ trọng qua năm', 'Khách hàng & tần suất', 'Bảng số liệu'])
with tab_share:
    sh = seg[(seg['dimension_name'] == dim) & seg['is_analysis_period']].copy()
    sh['Nhóm'] = sh['dimension_value']
    sh['Năm'] = sh['year'].astype(str)
    sh['Tỷ trọng'] = sh['share'].map(pct)
    palette = ['#1f5f8b', '#2a9d8f', '#d1495b', '#8e6c8a', '#e9a23b', '#667f3f', '#496e91', '#9c6940']
    names = sorted(sh['Nhóm'].unique())
    line = alt.Chart(sh).mark_line(point=True).encode(
        x=alt.X('Năm:O', title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y('share:Q', title='Tỷ trọng R', axis=alt.Axis(labelExpr=AXIS_PCT1)),
        color=alt.Color('Nhóm:N', scale=alt.Scale(domain=names, range=palette[:len(names)]),
                        legend=alt.Legend(title='Nhóm', orient='bottom', direction='horizontal',
                                          columns=2, labelLimit=140)),
        tooltip=['Năm', 'Nhóm', 'Tỷ trọng'])
    st.altair_chart(line.properties(height=320), width='stretch')
    st.caption('Tỷ trọng = R nhóm ÷ R toàn công ty cùng năm. Tỷ trọng tăng không bảo đảm R của nhóm tăng bằng tiền.')

with tab_cf:
    st.subheader(f'Số đơn toàn công ty, năm {nam}: số khách C và tần suất F')
    st.caption(f'**Phạm vi: Toàn công ty.** Không chia theo {ten_chieu} đang chọn; năm so sánh vẫn là {nam - 1} → {nam}.')
    d = pick(dp.set_index('period_code'), str(nam), 'driver_period', f'của năm {nam}')
    k1, k2, k3 = hang_the('the_ps5_cf', 3)
    kpi(k1, f'Số đơn đổi ({nam - 1}→{nam})', num(d['delta_n'], 0, signed=True) + ' đơn',
        f'Số đơn toàn công ty. N {nam - 1}: {num(d["n_start"])}; N {nam}: {num(d["n_end"])}.')
    kpi(k2, 'Phần do số khách C', num(d['contrib_c'], 0, signed=True) + ' đơn',
        '(C₁ − C₀) × F₀: thay đổi số khách có đơn đã giao, giữ số đơn mỗi khách như năm trước.')
    kpi(k3, 'Phần do tần suất F', num(d['contrib_f'], 0, signed=True) + ' đơn',
        'C₁ × (F₁ − F₀): thay đổi số đơn mỗi khách với số khách năm nay.')
    BUOC = {'c': 'Số khách C', 'f': 'Tần suất F'}
    w = need(br[(br['period_code'] == str(nam)) & (br['bridge_code'] == 'n_cf')], 'driver_bridge',
             f'của thác số đơn năm {nam}').copy()
    w['Cột'] = [f'N {int(v)}' if c in ('n_start', 'n_end') else BUOC[c]
                 for c, v in zip(w['step_code'], w['step_year'])]
    w['loai'] = ['Tổng' if c in ('n_start', 'n_end') else ('Tăng' if a >= 0 else 'Giảm')
                 for c, a in zip(w['step_code'], w['amount'])]
    w['Số đơn'] = [num(a, 0) if c in ('n_start', 'n_end') else num(a, 0, signed=True)
                   for c, a in zip(w['step_code'], w['amount'])]
    x = alt.X('Cột:N', sort=list(w['Cột']), title=None, axis=alt.Axis(labelAngle=0))
    thac = alt.Chart(w).mark_bar(size=60).encode(
        x=x, y=alt.Y('bar_start:Q', title='Số đơn',
                   axis=alt.Axis(labelExpr="replace(format(datum.value, ',.0f'), ',', '.')")),
        y2='bar_end:Q',
        color=alt.Color('loai:N', scale=alt.Scale(domain=['Tổng', 'Tăng', 'Giảm'],
                                                range=['#1f5f8b', '#2a9d8f', '#d1495b']),
                        legend=alt.Legend(title=None, orient='top')),
        tooltip=['Cột', 'Số đơn'])
    chu = alt.Chart(w).transform_calculate(top='max(datum.bar_start, datum.bar_end)').mark_text(
        dy=-8, fontSize=12).encode(x=x, y='top:Q', text='Số đơn:N')
    st.altair_chart((thac + chu).properties(height=320), width='stretch')
    st.caption('N = C × F. C là số khách có đơn đã giao trong năm; C giảm chưa đủ kết luận khách hàng rời bỏ. '
               'Tách số đơn thành số khách và tần suất là phép chia số học, chưa phải nguyên nhân.')
    yr = dp[dp['period_type'] == 'year'].copy()
    yy = yearly.set_index('year')
    need_keys(yr['end_year'], yy, 'revenue_yearly', 'của năm có trong bảng C/F')
    tc = yr[['period_code']].rename(columns={'period_code': 'Năm'})
    tc['C (số khách)'] = [num(yy.loc[e, 'c']) for e in yr['end_year']]
    tc['F (đơn / khách)'] = [num(yy.loc[e, 'f'], 3) for e in yr['end_year']]
    tc['N đổi'] = yr['delta_n'].map(lambda v: num(v, 0, signed=True))
    tc['Phần do C'] = yr['contrib_c'].map(lambda v: num(v, 0, signed=True))
    tc['Phần do F'] = yr['contrib_f'].map(lambda v: num(v, 0, signed=True))
    with st.expander('Xem bảng C/F theo năm'):
        st.dataframe(tc, hide_index=True, height='content', width='stretch',
                     column_config={c: right for c in tc.columns if c != 'Năm'})

with tab_data:
    st.caption(f'{DIM[dim]} · {nam - 1} → {nam}. Hạng reporting từ nhóm tăng nhiều nhất đến nhóm giảm nhiều nhất. '
               'Tỷ trọng và tỷ lệ đóng góp là hai mẫu số khác nhau; dịch chuyển tỷ trọng tính bằng điểm phần trăm.')
    with st.expander('Xem bảng chi tiết theo nhóm'):
        st.dataframe(tb, hide_index=True, height='content', width='stretch',
                     column_config={c: right for c in tb.columns if c not in ('Hạng', 'Nhóm')})
    st.download_button('Tải bảng nhóm (CSV)', data=tb.to_csv(index=False).encode('utf-8-sig'),
                       file_name=f'ps5_{dim}_{nam}.csv', mime='text/csv')

with st.expander('Cách đọc & phương pháp'):
    st.markdown('\n'.join(f'- {item}' for item in [
        'Mỗi lần xem một chiều. Mức đổi R của các nhóm cùng chiều cộng đúng bằng mức đổi R toàn công ty; '
        'không cộng các chiều với nhau.',
        '% đóng góp = mức đổi R của nhóm ÷ mức đổi R toàn công ty; có thể âm hoặc vượt 100% khi các nhóm bù trừ.',
        'Tỷ trọng = R nhóm ÷ R toàn công ty cùng năm. Dịch chuyển tỷ trọng là chênh tỷ trọng giữa hai năm, '
        'đơn vị điểm phần trăm.',
        'N = C × F ở cấp toàn công ty. Phần C = (C₁ − C₀) × F₀; phần F = C₁ × (F₁ − F₀).',
    ]))
with st.expander('Giới hạn chi tiết'):
    st.markdown('\n'.join(f'- {item}' for item in [
        'Region là nhãn Central / East / West của dữ liệu mô phỏng; không ánh xạ thành tỉnh/thành thực.',
        'acquisition_channel là kênh thu hút khách gắn với khách hàng, khác nguồn của từng đơn.',
        'C đếm khách có đơn đã giao trong năm; C giảm chưa đủ kết luận khách hàng rời bỏ (chưa đo churn).',
        f'Khi R đổi dưới {nguong} R năm trước, % đóng góp không ổn định. '
        'Ngưỡng do dev đề xuất, chờ BA chốt (seed driver_rule).',
        'Phân rã và chênh lệch nhóm chỉ là số học; không tự chứng minh tác động marketing, tồn kho hay churn.',
        *GIOI_HAN_CHUNG,
    ]))
