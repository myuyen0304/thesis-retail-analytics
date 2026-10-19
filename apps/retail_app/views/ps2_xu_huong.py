import altair as alt
import pandas as pd
import streamlit as st

from ai_explain import page_explain
from ui.ai_panel import ai_panel
from ui.common import GIOI_HAN_CHUNG, hang_the, info_strip, kpi, load_or_stop, need, need_keys
from ui.fmt import AXIS_PCT1, AXIS_TY, num, pct, trieu, ty


st.title('PS2 · Xu hướng doanh thu')
st.markdown('Doanh thu thay đổi thế nào và những giai đoạn nào đáng chú ý?')

# Mốc giai đoạn và thuật toán đều đọc từ reporting; trang chỉ sắp xếp lại cách trình bày.
build = load_or_stop('build_info').iloc[0]
phase = load_or_stop('revenue_phase')
turn = load_or_stop('revenue_turning_point')
monthly = load_or_stop('revenue_monthly')
yearly = load_or_stop('revenue_yearly')
change = load_or_stop('direction_change')
rule = load_or_stop('direction_rule')

TREND = {'tang': 'tăng', 'giam': 'giảm', 'giam_manh': 'giảm mạnh', 'di_ngang': 'đi ngang'}
TREND_COLOR = {'tang': '#2a9d8f', 'giam': '#e9a23b', 'giam_manh': '#d1495b', 'di_ngang': '#8d99ae'}
phase['ten'] = phase['phase_code'] + '. ' + phase['phase_name']      # tên đúng seed BA, như PS4 và chat
phase['nam'] = phase['start_year'].astype(str) + '→' + phase['end_year'].astype(str)
name_of = dict(zip(phase['phase_code'], phase['ten']))
need_keys([*turn['from_phase_code'], *turn['to_phase_code']], phase.set_index('phase_code'), 'revenue_phase',
          'của giai đoạn mà bảng điểm đổi hướng nhắc tới')

st.caption(f'Kỳ phân tích: {build["analysis_start_year"]}–{build["analysis_end_year"]} · '
           'R: doanh thu đơn đã giao · Đơn vị tiền: VND (tỷ = tỷ đồng)')
with st.expander('Định nghĩa & phạm vi dữ liệu'):
    info_strip()
    st.markdown('Đường chính là **tổng R của 12 tháng kết thúc tại mỗi tháng**, tính từ tháng đầu có đủ 12 tháng. '
                'Giai đoạn A–D do BA xác định trên các năm đủ; đỉnh/đáy được thuật toán tìm trên đường 12 tháng.')

# Số lớn là CAGR theo năm; dòng phụ là tỷ lệ đổi giữa hai đầu giai đoạn.
cards = hang_the('the_ps2', len(phase))
for col, p in zip(cards, phase.itertuples()):
    kpi(col, f'{p.ten} ({p.nam})', f'{pct(p.cagr, 2, signed=True)}/năm',
        f'CAGR = (R năm cuối / R năm đầu)^(1/{p.n_years}) − 1 ({p.n_years} năm). '
        f'Thay đổi toàn giai đoạn: {pct(p.total_change_rate, 1, signed=True)}.',
        delta=pct(p.total_change_rate, 1, signed=True), delta_sign=p.total_change_rate,
        delta_desc='Thay đổi toàn giai đoạn')
st.caption('Số lớn: CAGR (%/năm). Dòng nhỏ: thay đổi R của toàn giai đoạn; hai tỷ lệ có mẫu thời gian khác nhau.')

right = st.column_config.TextColumn(alignment='right')

# Đường tổng R 12 tháng, ranh giới BA và đỉnh/đáy thuật toán.
line_df = need(monthly[monthly['r_12m'].notna()], 'revenue_monthly', 'có R 12 tháng')[
    ['month_start_date', 'r_12m']].copy()
line_df['Tháng'] = line_df['month_start_date'].dt.strftime('%m/%Y')
line_df['R 12 tháng (VND)'] = line_df['r_12m'].map(lambda v: num(v, 2))
t = turn.copy()
t['Điểm'] = 'Cuối ' + t['turning_year'].astype(str)
t['Độ lớn'] = t['magnitude'].map(lambda v: pct(v, 1, signed=True))
t['Ghi chú BA'] = t['turn_note'].fillna('')
main = change[change['is_main_window']].copy()
main['Đỉnh/đáy R 12 tháng'] = [('Đỉnh ' if d == 'xuong' else 'Đáy ') + f'{e:%m/%Y}'
                              for d, e in zip(main['direction_after'], main['extreme_month_date'])]
main['Tháng phát hiện'] = main['change_month_date'].dt.strftime('%m/%Y')
main['R 12 tháng (VND)'] = main['extreme_r_12m'].map(lambda v: num(v, 2))

x = alt.X('month_start_date:T', title=None, axis=alt.Axis(format='%Y', tickCount='year'))
bands = alt.Chart(phase).mark_rect(opacity=0.08).encode(
    x=alt.X('band_start_date:T'), x2='band_end_date:T',
    color=alt.Color('ten:N', title=None, sort=list(phase['ten']),
                    scale=alt.Scale(domain=list(phase['ten']), range=[TREND_COLOR[v] for v in phase['trend']]),
                    legend=None),
    tooltip=[alt.Tooltip('ten:N', title='Giai đoạn'), alt.Tooltip('nam:N', title='Năm')])
line = alt.Chart(line_df).mark_line(color='#1f5f8b', strokeWidth=2.5).encode(
    x=x, y=alt.Y('r_12m:Q', title=None, scale=alt.Scale(zero=False), axis=alt.Axis(labelExpr=AXIS_TY)),
    tooltip=['Tháng', 'R 12 tháng (VND)'])
rules = alt.Chart(t).mark_rule(color='#d1495b', strokeDash=[4, 3]).encode(x='turning_month_date:T')
points = alt.Chart(t).mark_point(color='#d1495b', filled=True, size=80).encode(
    x='turning_month_date:T', y='r_12m_before:Q', tooltip=['Điểm', 'Độ lớn', 'Ghi chú BA'])
tri = alt.Chart(main).mark_point(shape='triangle-down', color='#222', filled=True, size=110).encode(
    x='extreme_month_date:T', y='extreme_r_12m:Q',
    tooltip=['Đỉnh/đáy R 12 tháng', 'Tháng phát hiện', 'R 12 tháng (VND)'])

st.subheader('Tổng R trượt 12 tháng')
left, side = st.columns([2, 1], gap='medium')
with left:
    with st.expander('Tùy chọn lớp đánh dấu'):
        layers = st.multiselect('Hiện trên biểu đồ', ['Mốc BA', 'Đỉnh/đáy dữ liệu'],
                                default=['Mốc BA', 'Đỉnh/đáy dữ liệu'], key='ps2_layers')
    marks = ([rules, points] if 'Mốc BA' in layers else []) + ([tri] if 'Đỉnh/đáy dữ liệu' in layers else [])
    st.altair_chart(alt.layer(bands, line, *marks).properties(height=420), width='stretch')
    st.caption('Mỗi điểm là tổng R của 12 tháng kết thúc tại tháng đó.')
    legend = ['đường xanh = R 12 tháng', 'nền nhạt = giai đoạn BA']
    if 'Mốc BA' in layers:
        legend.append('nét đứt và chấm đỏ = mốc BA')
    if 'Đỉnh/đáy dữ liệu' in layers:
        legend.append('tam giác đen = đỉnh/đáy thuật toán')
    st.caption('Chú giải: ' + '; '.join(legend) + '.')
with side:
    with st.container(border=True):
        st.markdown('**Tóm tắt từ số liệu**')
        st.caption('Câu viết sẵn theo quy tắc từ số liệu, không do AI viết')
        first_phase, last_phase = phase.iloc[0], phase.iloc[-1]
        steepest = phase.loc[phase['cagr'].idxmin()]
        st.markdown(f'- **Đầu và cuối kỳ:** {first_phase["ten"]} ({first_phase["nam"]}) '
                    f'CAGR {pct(first_phase["cagr"], 2, signed=True)}/năm; '
                    f'{last_phase["ten"]} ({last_phase["nam"]}) '
                    f'{pct(last_phase["cagr"], 2, signed=True)}/năm.')
        st.markdown(f'- **Giảm mạnh nhất:** {steepest["ten"]} ({steepest["nam"]}), '
                    f'R đổi {pct(steepest["total_change_rate"], 1, signed=True)} cả giai đoạn.')
        st.markdown(f'- **Điểm đổi hướng:** {len(t)} mốc BA; dữ liệu tìm được {len(main)} '
                    'đỉnh/đáy trên đường R 12 tháng. Xem tháng phát hiện và độ nhạy ở tab bên dưới.')
        st.markdown('- **Giới hạn:** ranh giới BA là quy ước phân tích; đỉnh/đáy chỉ được xác định '
                    'khi nhìn lại đủ dữ liệu và không chứng minh nguyên nhân kinh doanh.')
    ai_panel(page_explain.request_ps2())

first = line_df.iloc[0]['month_start_date']
st.caption(f'Đường bắt đầu từ {first:%m/%Y} (đủ 12 tháng); đoạn trước '
           f'{phase["band_start_date"].min():%m/%Y} không thuộc giai đoạn BA nào. '
           'Đỉnh/đáy của tổng R 12 tháng có thể khác doanh thu riêng từng tháng.')

tab_turn, tab_growth, tab_phase = st.tabs(['Điểm đổi hướng', 'Tăng trưởng năm / tháng', 'So sánh giai đoạn'])

# Bảng thuật toán: giữ từng dòng 3/6/9 tháng và tháng phát hiện như báo cáo.
k_main = int(need(rule[rule['is_main_window']], 'direction_rule', 'của khoảng so chính')['window_months'].iloc[0])
k_all = ', '.join(str(k) for k in rule['window_months'])
min_run = int(rule['min_run_months'].iloc[0])
DIR = {'len': 'lên', 'xuong': 'xuống', 'ngang': 'ngang'}
tc = change[['window_months']].copy()
tc['Khoảng so'] = [f'{k} tháng' + (' (chính)' if m else '')
                   for k, m in zip(change['window_months'], change['is_main_window'])]
tc['Chuyển'] = [f'{DIR[a]} → {DIR[b]}' for a, b in zip(change['direction_before'], change['direction_after'])]
tc['Đỉnh / đáy R 12 tháng'] = [('đỉnh ' if d == 'xuong' else 'đáy ') + f'{e:%m/%Y}'
                               for d, e in zip(change['direction_after'], change['extreme_month_date'])]
tc['R 12 tháng tại đó'] = change['extreme_r_12m'].map(lambda v: ty(v, 2))
tc['Tháng phát hiện'] = change['change_month_date'].dt.strftime('%m/%Y')
tc['Hướng mới giữ'] = [f'{n} tháng' + (' (tới hết dữ liệu)' if e else '')
                       for n, e in zip(change['months_held'], change['held_to_end_of_data'])]

sensitivity = []
for k in rule['window_months']:
    subset = change[change['window_months'] == k]
    result = {'Khoảng so': f'{k} tháng' + (' (chính)' if k == k_main else '')}
    for direction, title in [('xuong', 'Đỉnh → phát hiện'), ('len', 'Đáy → phát hiện')]:
        found = subset[subset['direction_after'] == direction]
        result[title] = ('; '.join(f'{r.extreme_month_date:%m/%Y} → {r.change_month_date:%m/%Y}'
                                   for r in found.itertuples()) if not found.empty else '–')
    sensitivity.append(result)

with tab_turn:
    st.markdown('**Mốc do BA xác định**')
    st.caption('Ranh giới giai đoạn: ' + ', '.join(t['Điểm']) + '. '
               'Các mốc đổi tốc độ vẫn là mốc BA, kể cả khi thuật toán không ghi nhận đảo hướng.')
    st.markdown('**Đỉnh/đáy do dữ liệu tìm được**')
    st.caption(f'Khoảng so chính: {k_main} tháng; hướng mới phải duy trì ít nhất {min_run} tháng. '
               f'Kiểm độ nhạy với các khoảng {k_all} tháng.')
    for _, r in main.iterrows():
        st.markdown(f'- **{r["Đỉnh/đáy R 12 tháng"]}:** tháng phát hiện '
                    f'{r["change_month_date"]:%m/%Y}; hướng mới giữ {r["months_held"]} tháng' +
                    (' tới hết dữ liệu.' if r['held_to_end_of_data'] else '.'))
    st.dataframe(pd.DataFrame(sensitivity), hide_index=True, height='content', width='stretch')
    st.caption('Tháng đỉnh/đáy có trước tháng phát hiện. Mốc phát hiện được gán hồi cứu '
               'sau khi hướng mới giữ đủ số tháng quy định; đó không phải tín hiệu đã biết ngay tại đỉnh/đáy.')
    with st.expander('Xem bảng chi tiết & phương pháp phát hiện'):
        st.dataframe(tc.drop(columns='window_months'), hide_index=True, height='content', width='stretch',
                     column_config={c: right for c in ['R 12 tháng tại đó', 'Hướng mới giữ']})
        st.markdown('Mỗi tháng so tổng R 12 tháng với chính nó `k` tháng trước: lớn hơn là lên, '
                    'nhỏ hơn là xuống. Chỉ đoạn giữ hướng ít nhất `min_run_months` mới được tính; '
                    'đoạn ngắn hơn coi là nhiễu. Cách này xét hướng, không xét tốc độ. '
                    'Đổi khoảng so có thể làm tháng phát hiện xê dịch.')

# Hai chế độ tăng trưởng dùng cùng cột yoy_rate reporting ở đúng grain.
y = yearly[yearly['yoy_rate'].notna()][['year', 'r', 'yoy_rate']].copy()
y['nam'] = y['year'].astype(str)
y['R (VND)'] = y['r'].map(lambda v: num(v, 2))
y['Tăng trưởng'] = y['yoy_rate'].map(lambda v: pct(v, 1, signed=True))
y['chieu'] = y['yoy_rate'].map(lambda v: 'tăng' if v >= 0 else 'giảm')
yx = alt.X('nam:O', title=None, axis=alt.Axis(labelAngle=0))
year_bars = alt.Chart(y).mark_bar(size=34).encode(
    x=yx, y=alt.Y('yoy_rate:Q', title=None, axis=alt.Axis(labelExpr=AXIS_PCT1)),
    color=alt.Color('chieu:N', legend=None, scale=alt.Scale(domain=['tăng', 'giảm'], range=['#2a9d8f', '#d1495b'])),
    tooltip=['nam', 'R (VND)', 'Tăng trưởng'])
up = alt.Chart(y[y['yoy_rate'] >= 0]).mark_text(fontSize=11, dy=-8).encode(x=yx, y='yoy_rate:Q', text='Tăng trưởng:N')
down = alt.Chart(y[y['yoy_rate'] < 0]).mark_text(fontSize=11, dy=12).encode(x=yx, y='yoy_rate:Q', text='Tăng trưởng:N')

mo = monthly[monthly['yoy_rate'].notna()][['month_start_date', 'r', 'r_same_month_prior_year', 'yoy_rate']].copy()
mo['Tháng'] = mo['month_start_date'].dt.strftime('%m/%Y')
mo['R (VND)'] = mo['r'].map(lambda v: num(v, 2))
mo['R cùng tháng năm trước (VND)'] = mo['r_same_month_prior_year'].map(lambda v: num(v, 2))
mo['Tăng trưởng'] = mo['yoy_rate'].map(lambda v: pct(v, 1, signed=True))
mo['chieu'] = mo['yoy_rate'].map(lambda v: 'tăng' if v >= 0 else 'giảm')
month_bars = alt.Chart(mo).mark_bar().encode(
    x=x, y=alt.Y('yoy_rate:Q', title=None, axis=alt.Axis(labelExpr=AXIS_PCT1)),
    color=alt.Color('chieu:N', legend=None, scale=alt.Scale(domain=['tăng', 'giảm'], range=['#2a9d8f', '#d1495b'])),
    tooltip=['Tháng', 'R (VND)', 'R cùng tháng năm trước (VND)', 'Tăng trưởng'])
zero = alt.Chart(pd.DataFrame({'zero': [0]})).mark_rule(color='#667085', strokeDash=[3, 3]).encode(y='zero:Q')

with tab_growth:
    mode = st.segmented_control('Kiểu so sánh', ['Năm trước', 'Cùng tháng năm trước'],
                                default='Năm trước', required=True, wrap=True, key='ps2_growth_mode')
    if mode == 'Năm trước':
        st.subheader('Tăng trưởng R theo năm so với năm trước')
        st.altair_chart((year_bars + up + down + zero).properties(height=300), width='stretch')
        st.caption(f'R năm / R năm trước − 1; tính từ {y["year"].min()} vì năm 2012 chưa đủ 12 tháng. '
                   'Nét đứt là mốc 0%; màu xanh là tăng, đỏ là giảm.')
    else:
        st.subheader('Tăng trưởng R theo tháng so với cùng tháng năm trước')
        st.altair_chart((bands + month_bars + zero).resolve_scale(color='independent').properties(height=300),
                       width='stretch')
        st.caption(f'R tháng / R cùng tháng năm trước − 1; tính từ {mo["month_start_date"].min():%m/%Y} '
                   '(cùng kỳ đầu tiên đủ dữ liệu). Đây là so với cùng tháng năm trước, không phải tháng liền trước. '
                   'Nét đứt là 0%; xanh là tăng, đỏ là giảm; nền nhạt là giai đoạn BA.')
        st.caption('Nhịp tháng 8 chẵn/lẻ được phân tích thêm ở PS3; biểu đồ này không tự chứng minh nguyên nhân '
                   'và không phải mốc đổi hướng của đường R 12 tháng.')

# So sánh giai đoạn và độ lớn mốc BA: mỗi bảng chỉ xuất hiện một lần.
tb = phase[['ten', 'nam']].rename(columns={'ten': 'Giai đoạn', 'nam': 'Năm'})
tb['Xu hướng'] = phase['trend'].map(TREND)
tb['R năm đầu'] = phase['r_start'].map(lambda v: ty(v, 2))
tb['R năm cuối'] = phase['r_end'].map(lambda v: ty(v, 2))
tb['Chênh R'] = phase['delta_r'].map(lambda v: trieu(v, 1, signed=True))
tb['Tổng thay đổi'] = phase['total_change_rate'].map(lambda v: pct(v, 1, signed=True))
tb['CAGR'] = phase['cagr'].map(lambda v: pct(v, 2, signed=True))
td = t[['Điểm']].copy()
td['Từ → sang'] = [f'{name_of[a]} → {name_of[b]}' for a, b in zip(t['from_phase_code'], t['to_phase_code'])]
td['Xu hướng'] = [f'{TREND[a]} → {TREND[b]}' for a, b in zip(t['trend_before'], t['trend_after'])]
td['R 12 tháng trước'] = t['r_12m_before'].map(lambda v: ty(v, 2))
td['R 12 tháng sau'] = t['r_12m_after'].map(lambda v: ty(v, 2))
td['Chênh R'] = t['delta_r'].map(lambda v: trieu(v, 1, signed=True))
td['Độ lớn'] = t['Độ lớn']
td['Ghi chú của BA'] = t['turn_note'].fillna('')
td['Dữ liệu tự tìm thấy?'] = [f'{e:%m/%Y} (phát hiện {c:%m/%Y})' if not pd.isna(e) else 'không'
                              for e, c in zip(t['data_extreme_month_date'], t['data_change_month_date'])]
with tab_phase:
    st.dataframe(tb, hide_index=True, height='content', width='stretch',
                 column_config={c: right for c in ['R năm đầu', 'R năm cuối', 'Chênh R', 'Tổng thay đổi', 'CAGR']})
    st.caption('CAGR: % mỗi năm; tổng thay đổi: % giữa năm đầu và năm cuối. '
               'Hai giai đoạn kề nhau dùng chung năm ranh giới.')
    with st.expander('Xem độ lớn các mốc BA'):
        st.dataframe(td, hide_index=True, height='content', width='stretch',
                     column_config={c: right for c in ['R 12 tháng trước', 'R 12 tháng sau', 'Chênh R', 'Độ lớn']})
        st.caption('Cột cuối đối chiếu với đỉnh/đáy của thuật toán ở khoảng so chính. '
                   '“Không” nghĩa là mốc BA đổi tốc độ nhưng thuật toán không ghi nhận đảo hướng.')

last_year = yearly.iloc[-1]
last_phase = phase.iloc[-1]
recovery = ([f'Năm {last_year["year"]} R tăng {pct(last_year["yoy_rate"], 1, signed=True)} so với năm trước. '
             f'Mới có 1 năm nên đây là **tín hiệu hồi phục cuối giai đoạn {last_phase["phase_code"]}**, '
             'chưa phải xu hướng tăng; cần thêm dữ liệu năm sau mới kết luận được.']
            if last_year['yoy_rate'] > 0 else [])
with st.expander('Cách đọc & phương pháp'):
    st.markdown('\n'.join(f'- {item}' for item in [
        'CAGR = (R năm cuối / R năm đầu)^(1/n) − 1, n là số năm giai đoạn; '
        'thay đổi toàn giai đoạn là R năm cuối / R năm đầu − 1. Giai đoạn một năm có CAGR bằng tăng trưởng năm đó.',
        'Hai giai đoạn liền nhau dùng chung năm ranh giới. Mốc BA ở cuối năm; '
        'độ lớn mốc = R 12 tháng sau / R 12 tháng trước − 1. Với mốc cuối năm, '
        '12 tháng trước là năm ranh giới, 12 tháng sau là năm kế tiếp.',
        'Tháng 12 của tổng R 12 tháng bằng R cả năm. Đỉnh/đáy trên đường này '
        'có thể khác đỉnh/đáy doanh thu riêng từng tháng.',
        'Điểm đổi hướng thuật toán là kết quả nhìn lại lịch sử sau khi hướng mới duy trì đủ lâu.',
        *recovery,
        'Không gộp cả kỳ thành một tỷ lệ tăng trưởng vì các giai đoạn đi theo hướng khác nhau.',
        'Các giai đoạn mô tả xu hướng, không giải thích nguyên nhân. PS4 và PS5 phân rã biến động theo yếu tố và nhóm.',
    ]))
with st.expander('Giới hạn chi tiết'):
    st.markdown('\n'.join(f'- {item}' for item in [
        'Phân kỳ BA là quy ước đã chốt (`ps2_phases`), không phải kết quả thuật toán. '
        'Thuật toán `ps2_direction_rule` chỉ tìm đổi hướng lên/xuống; mốc đổi tốc độ vẫn do BA đánh giá.',
        'Quy tắc tự tìm là tiêu chí thăm dò, không khẳng định mọi điểm gãy hay nguyên nhân kinh doanh.',
        'Năm 2012 chưa đủ năm, chỉ để tham khảo; tăng trưởng năm bắt đầu khi có năm trước đủ 12 tháng.',
        *GIOI_HAN_CHUNG,
    ]))
