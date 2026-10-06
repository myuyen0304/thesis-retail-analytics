import altair as alt
import pandas as pd
import streamlit as st

from ui.common import GIOI_HAN_CHUNG, kpi, load_or_stop, need, need_keys, notes, page_header
from ui.fmt import AXIS_PCT1, AXIS_TY, num, pct, trieu, ty

page_header('PS2: Xu hướng doanh thu', 'Doanh thu tăng hay giảm, giai đoạn nào đổi hướng?')

# Giai đoạn và điểm đổi hướng lấy từ seed ps2_phases do BA chốt (plan §3, tiêu chí 5): app không gõ năm nào.
phase = load_or_stop('revenue_phase')
turn = load_or_stop('revenue_turning_point')
monthly = load_or_stop('revenue_monthly')
yearly = load_or_stop('revenue_yearly')
change = load_or_stop('direction_change')     # tháng đổi hướng do dữ liệu tự tìm (deck slide 6 yêu cầu 4)
rule = load_or_stop('direction_rule')

TREND = {'tang': 'tăng', 'giam': 'giảm', 'giam_manh': 'giảm mạnh', 'di_ngang': 'đi ngang'}
TREND_COLOR = {'tang': '#2a9d8f', 'giam': '#e9a23b', 'giam_manh': '#d1495b', 'di_ngang': '#8d99ae'}
phase['ten'] = phase['phase_code'] + '. ' + phase['phase_name']
phase['nam'] = phase['start_year'].astype(str) + '→' + phase['end_year'].astype(str)
name_of = dict(zip(phase['phase_code'], phase['ten']))
need_keys([*turn['from_phase_code'], *turn['to_phase_code']], phase.set_index('phase_code'), 'revenue_phase',
          'của giai đoạn mà bảng điểm đổi hướng nhắc tới')

# --- Thẻ KPI: CAGR từng giai đoạn ---
# Feedback 2026-10-01 (F02): ghi rõ số lớn là CAGR (%/năm), tách khỏi tổng thay đổi cả giai đoạn (dòng màu).
# Nhãn chỉ giữ tên giai đoạn, khoảng năm nằm ở dòng phụ: 4 thẻ một hàng, nhãn dài bị cắt mất năm khi màn 1280 px mở sidebar.
st.markdown('**CAGR: tăng trưởng trung bình mỗi năm của R** (số lớn, **%/năm**). '
            'Dòng màu: **tổng thay đổi** của R cả giai đoạn, từ năm đầu tới năm cuối.')
for col, p in zip(st.columns(len(phase)), phase.itertuples()):
    kpi(col, p.ten, pct(p.cagr, 2, signed=True),
        f'CAGR: tốc độ tăng trung bình mỗi năm từ R {p.start_year} tới R {p.end_year} ({p.n_years} năm). '
        f'Tổng thay đổi cả giai đoạn: {pct(p.total_change_rate, 1, signed=True)}.',
        delta=pct(p.total_change_rate, 1, signed=True), delta_sign=p.total_change_rate,
        delta_desc=f'tổng {p.nam}')

right = st.column_config.TextColumn(alignment='right')

# --- Đường R 12 tháng, tô nền giai đoạn, đánh dấu điểm đổi hướng ---
st.subheader('R 12 tháng gần nhất: 4 giai đoạn và các điểm đổi hướng')
line_df = need(monthly[monthly['r_12m'].notna()], 'revenue_monthly', 'có R 12 tháng')[['month_start_date', 'r_12m']].copy()
line_df['Tháng'] = line_df['month_start_date'].dt.strftime('%m/%Y')
line_df['R 12 tháng'] = line_df['r_12m'].map(lambda v: num(v, 2))
t = turn.copy()
t['nhan'] = [f'Cuối {y}: {pct(m, 1, signed=True)}' + (f' ({n})' if isinstance(n, str) and n else '')
             for y, m, n in zip(t['turning_year'], t['magnitude'], t['turn_note'])]
t['Điểm'] = 'Cuối ' + t['turning_year'].astype(str)
t['Độ lớn'] = t['magnitude'].map(lambda v: pct(v, 1, signed=True))

x = alt.X('month_start_date:T', title=None, axis=alt.Axis(format='%Y', tickCount='year'))
bands = alt.Chart(phase).mark_rect(opacity=0.14).encode(
    x=alt.X('band_start_date:T'), x2='band_end_date:T',
    color=alt.Color('ten:N', title=None, sort=list(phase['ten']),
                    scale=alt.Scale(domain=list(phase['ten']), range=[TREND_COLOR[v] for v in phase['trend']]),
                    legend=alt.Legend(orient='top', symbolOpacity=0.5)),
    tooltip=[alt.Tooltip('ten:N', title='Giai đoạn'), alt.Tooltip('nam:N', title='Năm')])
line = alt.Chart(line_df).mark_line(color='#1f5f8b', strokeWidth=2.5).encode(
    x=x, y=alt.Y('r_12m:Q', title=None, scale=alt.Scale(zero=False), axis=alt.Axis(labelExpr=AXIS_TY)),
    tooltip=['Tháng', 'R 12 tháng'])
rules = alt.Chart(t).mark_rule(color='#444', strokeDash=[4, 3]).encode(x='turning_month_date:T')
points = alt.Chart(t).mark_point(color='#d1495b', filled=True, size=90).encode(
    x='turning_month_date:T', y='r_12m_before:Q', tooltip=['Điểm', 'Độ lớn'])
labels = alt.Chart(t).mark_text(align='left', dx=8, dy=-12, fontSize=12, color='#d1495b', fontWeight='bold').encode(
    x='turning_month_date:T', y='r_12m_before:Q', text='nhan:N')
# đỉnh / đáy mà dữ liệu tự tìm (khoảng so chính): tam giác đen, nhãn nằm dưới
main = change[change['is_main_window']].copy()
main['nhan'] = [('Đỉnh ' if d == 'xuong' else 'Đáy ') + f'{e:%m/%Y}'
                for d, e in zip(main['direction_after'], main['extreme_month_date'])]
main['Tháng phát hiện'] = main['change_month_date'].dt.strftime('%m/%Y')
tri = alt.Chart(main).mark_point(shape='triangle-down', color='#222', filled=True, size=110).encode(
    x='extreme_month_date:T', y='extreme_r_12m:Q',
    tooltip=[alt.Tooltip('nhan:N', title='Dữ liệu tự tìm'), 'Tháng phát hiện'])
tri_text = alt.Chart(main).mark_text(dy=18, fontSize=12, color='#222').encode(
    x='extreme_month_date:T', y='extreme_r_12m:Q', text='nhan:N')
st.altair_chart((bands + line + rules + points + labels + tri + tri_text).properties(height=400), width='stretch')
first = line_df.iloc[0]['month_start_date']
st.caption(f'Mỗi điểm trên đường = tổng R của 12 tháng tính tới tháng đó; tại tháng 12 đúng bằng R cả năm. '
           f'Đường bắt đầu từ {first:%m/%Y} (12 tháng đủ đầu tiên). Nền màu = giai đoạn, từ tháng 12 năm đầu tới '
           f'tháng 12 năm cuối, nên đoạn trước {phase["band_start_date"].min():%m/%Y} không thuộc giai đoạn nào. '
           'Chấm đỏ = điểm đổi hướng BA chốt. Tam giác đen = đỉnh/đáy mà dữ liệu tự tìm (mục dưới). '
           'Rê chuột lên đường để xem số đầy đủ.')

# --- Dữ liệu tự tìm tháng đổi hướng (deck slide 6 yêu cầu 4; cách làm theo ghi chú slide 7) ---
st.subheader('Dữ liệu tự tìm: đường R 12 tháng đổi hướng ở tháng nào, có kéo dài không?')
k_main = int(need(rule[rule['is_main_window']], 'direction_rule', 'của khoảng so chính')['window_months'].iloc[0])
k_all = ', '.join(str(k) for k in rule['window_months'])
min_run = int(rule['min_run_months'].iloc[0])
st.caption(f'Mỗi tháng so R 12 tháng với chính nó {k_main} tháng trước: lớn hơn là đang lên, nhỏ hơn là đang xuống. '
           f'Hướng mới phải giữ ít nhất {min_run} tháng liền mới tính; đoạn ngắn hơn coi là nhiễu. Thử các khoảng so '
           f'{k_all} tháng để xem kết quả có đổi không. Cách này chỉ xét lên hay xuống, không xét tốc độ.')
DIR = {'len': 'lên', 'xuong': 'xuống', 'ngang': 'ngang'}
tc = change[['window_months']].copy()
tc['Khoảng so'] = [f'{k} tháng' + (' (chính)' if m else '')
                   for k, m in zip(change['window_months'], change['is_main_window'])]
tc['Chuyển'] = [f'{DIR[a]} → {DIR[b]}' for a, b in zip(change['direction_before'], change['direction_after'])]
tc['Đỉnh / đáy R 12 tháng'] = [('đỉnh ' if d == 'xuong' else 'đáy ') + f'{e:%m/%Y}'
                               for d, e in zip(change['direction_after'], change['extreme_month_date'])]
tc['R 12 tháng tại đó'] = change['extreme_r_12m'].map(lambda v: ty(v, 2))   # feedback PM 2026-10-02: bảng ghi gọn
tc['Tháng phát hiện'] = change['change_month_date'].dt.strftime('%m/%Y')
tc['Hướng mới giữ'] = [f'{n} tháng' + (' (tới hết dữ liệu)' if e else '')
                       for n, e in zip(change['months_held'], change['held_to_end_of_data'])]
st.dataframe(tc.drop(columns='window_months'), hide_index=True, height='content',
             column_config={c: right for c in ['R 12 tháng tại đó', 'Hướng mới giữ']})
st.caption('Tháng phát hiện muộn hơn đỉnh/đáy vì phải so với nhiều tháng trước. Đổi khoảng so thì tháng phát hiện '
           'xê dịch; so cột đỉnh/đáy giữa các khoảng so để biết kết quả có phụ thuộc lựa chọn khoảng so không.')

# --- Bảng giai đoạn ---
st.subheader('Tăng trưởng trung bình năm (CAGR) theo giai đoạn')
tb = phase[['ten', 'nam']].rename(columns={'ten': 'Giai đoạn', 'nam': 'Năm'})
tb['Xu hướng'] = phase['trend'].map(TREND)
tb['R năm đầu'] = phase['r_start'].map(lambda v: ty(v, 2))
tb['R năm cuối'] = phase['r_end'].map(lambda v: ty(v, 2))
tb['Chênh R'] = phase['delta_r'].map(lambda v: trieu(v, 1, signed=True))   # cùng số với PS4
tb['Tổng thay đổi'] = phase['total_change_rate'].map(lambda v: pct(v, 1, signed=True))
tb['CAGR'] = phase['cagr'].map(lambda v: pct(v, 2, signed=True))
st.dataframe(tb, hide_index=True, height='content',
             column_config={c: right for c in ['R năm đầu', 'R năm cuối', 'Chênh R', 'Tổng thay đổi', 'CAGR']})

# --- Bảng điểm đổi hướng ---
st.subheader('Các điểm đổi hướng lớn cỡ nào?')
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
st.dataframe(td, hide_index=True, height='content',
             column_config={c: right for c in ['R 12 tháng trước', 'R 12 tháng sau', 'Chênh R', 'Độ lớn']})
st.caption('Cột cuối đối chiếu với mục "Dữ liệu tự tìm" ở trên (khoảng so chính): ghi "tháng đỉnh/đáy (tháng phát hiện)" '
           'khi đỉnh/đáy dữ liệu tìm được nằm trong năm ranh giới. "Không": hai phía cùng hướng, chỉ đổi tốc độ; đây là mốc BA chốt, dữ liệu không tự chỉ ra.')

# --- Tăng trưởng R theo năm ---
st.subheader('Tăng trưởng R so với năm trước')
y = yearly[yearly['yoy_rate'].notna()][['year', 'r', 'yoy_rate']].copy()
y['nam'] = y['year'].astype(str)
y['R'] = y['r'].map(lambda v: num(v, 2))
y['Tăng trưởng'] = y['yoy_rate'].map(lambda v: pct(v, 1, signed=True))
y['chieu'] = y['yoy_rate'].map(lambda v: 'tăng' if v >= 0 else 'giảm')
yx = alt.X('nam:O', title=None, axis=alt.Axis(labelAngle=0))
bars = alt.Chart(y).mark_bar(size=34).encode(
    x=yx, y=alt.Y('yoy_rate:Q', title=None, axis=alt.Axis(labelExpr=AXIS_PCT1)),
    color=alt.Color('chieu:N', legend=None, scale=alt.Scale(domain=['tăng', 'giảm'], range=['#2a9d8f', '#d1495b'])),
    tooltip=['nam', 'R', 'Tăng trưởng'])
# nhãn trên đỉnh cột tăng, dưới đáy cột giảm
up = alt.Chart(y[y['yoy_rate'] >= 0]).mark_text(fontSize=12, dy=-8).encode(x=yx, y='yoy_rate:Q', text='Tăng trưởng:N')
down = alt.Chart(y[y['yoy_rate'] < 0]).mark_text(fontSize=12, dy=12).encode(x=yx, y='yoy_rate:Q', text='Tăng trưởng:N')
st.altair_chart((bars + up + down).properties(height=280), width='stretch')
st.caption(f'Tăng trưởng R = R năm nay / R năm trước − 1, tính từ {y["year"].min()} '
           '(năm đầu có năm trước đủ 12 tháng).')

# --- Tăng trưởng R theo tháng, so cùng tháng năm trước (deck slide 6 yêu cầu 2) ---
st.subheader('Tăng trưởng R theo tháng, so với cùng tháng năm trước')
mo = monthly[monthly['yoy_rate'].notna()][['month_start_date', 'r', 'r_same_month_prior_year', 'yoy_rate']].copy()
mo['Tháng'] = mo['month_start_date'].dt.strftime('%m/%Y')
mo['R'] = mo['r'].map(lambda v: num(v, 2))
mo['R cùng tháng năm trước'] = mo['r_same_month_prior_year'].map(lambda v: num(v, 2))
mo['Tăng trưởng'] = mo['yoy_rate'].map(lambda v: pct(v, 1, signed=True))
mo['chieu'] = mo['yoy_rate'].map(lambda v: 'tăng' if v >= 0 else 'giảm')
mbars = alt.Chart(mo).mark_bar().encode(
    x=x, y=alt.Y('yoy_rate:Q', title=None, axis=alt.Axis(labelExpr="format(datum.value * 100, '.0f') + '%'")),
    color=alt.Color('chieu:N', legend=None, scale=alt.Scale(domain=['tăng', 'giảm'], range=['#2a9d8f', '#d1495b'])),
    tooltip=['Tháng', 'R', 'R cùng tháng năm trước', 'Tăng trưởng'])
# thang màu riêng cho cột (không gộp với màu giai đoạn của nền)
st.altair_chart((bands + mbars).resolve_scale(color='independent').properties(height=300), width='stretch')
st.caption(f'Mỗi cột = R tháng / R cùng tháng năm trước − 1, từ {mo["month_start_date"].min():%m/%Y} (tháng đầu có '
           'cùng tháng năm trước đủ ngày). Nền màu = giai đoạn như biểu đồ trên. Rê chuột lên cột để xem số đầy đủ. '
           'Cột tháng 8 đổi dấu năm chẵn/lẻ là nhịp khuyến mãi 2 năm (trang PS3), không phải đổi hướng.')

last = yearly.iloc[-1]
last_phase = phase.iloc[-1]
recovery = ([f'Năm {last["year"]} R tăng {pct(last["yoy_rate"], 1, signed=True)} so với năm trước. Mới có 1 năm nên đây là '
             f'**tín hiệu hồi phục cuối giai đoạn {last_phase["phase_code"]}**, chưa phải xu hướng tăng; '
             'cần thêm dữ liệu năm sau mới kết luận được.']
            if last['yoy_rate'] > 0 else [])
notes(
    cach_doc=[
        'CAGR = (R năm cuối / R năm đầu)^(1/n) − 1, n = số năm của giai đoạn. Giai đoạn chỉ dài 1 năm thì CAGR trùng '
        'tăng trưởng của năm đó.',
        'Hai giai đoạn liền nhau dùng chung năm ranh giới: năm cuối của giai đoạn trước là năm đầu của giai đoạn sau.',
        'Độ lớn điểm đổi hướng = R 12 tháng sau điểm / R 12 tháng trước điểm − 1. Điểm đặt ở cuối năm ranh giới, '
        'nên "12 tháng trước" là cả năm ranh giới và "12 tháng sau" là cả năm kế tiếp.',
        'Cột "Ghi chú của BA" lấy từ cấu hình giai đoạn. "Giảm tăng tốc": đang giảm nhẹ chuyển sang sập. '
        '"Đổi nhịp": cú sập dừng lại, doanh thu chuyển sang đi ngang; hướng vẫn là giảm nhưng chậm hẳn, nên không gọi là '
        'đảo chiều.',
        *recovery,
        'Không dùng một con số tăng trưởng cho cả 10 năm: con số đó trộn các giai đoạn đi theo hướng khác nhau.',
        'Giai đoạn chỉ **mô tả** doanh thu lên hay xuống, không giải thích vì sao. Muốn biết vì sao, xem PS4 '
        '(số đơn, số món, giá) và PS5 (ngành hàng, khu vực, kênh).',
    ],
    gioi_han=[
        'Mốc giai đoạn do BA chốt (seed `ps2_phases`). Dữ liệu tự tìm (seed `ps2_direction_rule`) chỉ xác nhận được các mốc '
        'đổi **hướng** (lên ↔ xuống); mốc đổi **tốc độ** (vd. giảm nhẹ → sập) là nhận định của BA. Đổi seed thì bảng và '
        'biểu đồ đổi theo.',
        'Cách tự tìm là tiêu chí thăm dò (ghi chú deck slide 7), không khẳng định mọi điểm gãy.',
        'Mốc là năm đủ; không dùng năm 2012 vì chỉ có nửa năm.',
        *GIOI_HAN_CHUNG,
    ],
)
