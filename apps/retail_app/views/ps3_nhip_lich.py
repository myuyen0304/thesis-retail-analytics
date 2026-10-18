import altair as alt
import pandas as pd
import streamlit as st

from ai_explain import page_explain
from ui.ai_panel import ai_panel
from ui.common import GIOI_HAN_CHUNG, hang_the, kpi, load_or_stop, need, need_keys, pick
from ui.fmt import num, pct, pp


st.title('PS3 · Nhịp lịch doanh thu')
st.markdown('Doanh thu phân bố theo tháng và thời điểm trong tháng như thế nào?')

# Trang chỉ đổi cách trình bày; ba nhịp và phép kiểm vẫn đọc từ reporting.
build = load_or_stop('build_info').iloc[0]
monthly = load_or_stop('revenue_monthly')
yearly = load_or_stop('revenue_yearly')
total = load_or_stop('revenue_total')
ap = load_or_stop('august_parity')
stab = load_or_stop('calendar_stability')
cp = load_or_stop('calendar_phase')
cpm = load_or_stop('calendar_phase_month')

aug = ap.iloc[0]
n_odd, n_even = int(aug['n_odd_years']), int(aug['n_even_years'])
m = need(monthly[monthly['is_analysis_period']], 'revenue_monthly', 'của kỳ phân tích').copy()
yr = yearly[yearly['is_analysis_period']].copy()
period = need(total[total['is_analysis_period']], 'revenue_total', 'của kỳ phân tích').iloc[0]
need_keys(m['year'], yr.set_index('year'), 'revenue_yearly', 'của năm có trong bảng tháng')
period_label = f'{period["start_year"]}–{period["end_year"]}'

st.caption(f'Kỳ phân tích: {period_label} · R: doanh thu đơn đã giao · Đơn vị tiền: VND')
with st.expander('Định nghĩa & phạm vi dữ liệu'):
    st.markdown('**R** là doanh thu đơn đã giao sau chiết khấu, gom theo ngày đặt hàng; '
                'không phải dòng tiền thanh toán. Tiền tính bằng VND. '
                'Chỉ số tháng so R của một tháng với R bình quân 12 tháng cùng năm; '
                'mốc **1** là mức bình quân, không phải số tiền. Năm '
                f'{build["data_start_date"].year} chưa đủ 12 tháng nên không dùng để so nhịp năm. '
                'Các chỉ số trong ba thẻ đại diện cho toàn kỳ phân tích. '
                f'Snapshot có đơn cuối cùng ngày {build["data_end_date"]:%d/%m/%Y}; '
                'trạng thái đơn là trạng thái lúc trích dữ liệu.')
st.session_state._collapse_source = True

season = pick(stab.set_index('rhythm_code'), 'mua_vu', 'calendar_stability', 'của nhịp mùa vụ')
end_month = pick(stab.set_index('rhythm_code'), 'cuoi_thang', 'calendar_stability', 'của nhịp cuối tháng')
august = pick(stab.set_index('rhythm_code'), 'thang_8', 'calendar_stability', 'của nhịp tháng 8')

c1, c2, c3 = hang_the('the_ps3', 3)
kpi(c1, f'Chênh chỉ số T8: lẻ / chẵn ({period_label})', pct(aug['august_odd_vs_even']),
    f'TB chỉ số tháng 8 của {n_odd} năm lẻ ÷ TB của {n_even} năm chẵn − 1. '
    f'Năm lẻ: {num(aug["august_index_odd"], 2)}; năm chẵn: {num(aug["august_index_even"], 2)}. '
    'Đây là tỷ lệ chênh chỉ số đã chuẩn hóa, không phải chênh doanh thu VND.')
kpi(c2, f'Tỷ số tháng cao / thấp ({period_label})', num(season['metric_value'], 2) + ' lần',
    'Gộp R của cùng tháng qua các năm trong kỳ; lấy R tháng cao nhất ÷ R tháng thấp nhất. '
    'Đây là tỷ số, không phải phần trăm hay chênh tiền.')
kpi(c3, f'Mức dồn cuối tháng ({period_label})', pp(period['eom_excess']),
    f'Tỷ trọng R từ ngày 26 trở đi: {pct(period["eom_share"])}. Mức so sánh {pct(period["eom_expected_share"])} '
    '= nếu R rải đều theo ngày trong từng tháng, giữ nguyên doanh thu mỗi tháng '
    '(mỗi tháng (D − 25)/D, cộng lại theo trọng số R tháng). '
    'Hiệu hai tỷ trọng có đơn vị điểm phần trăm; không phải tốc độ tăng R.')
st.caption('Ba KPI tính cho toàn kỳ phân tích; lựa chọn nhịp bên dưới chỉ thay biểu đồ và phần giải thích.')

# Bảng nhiệt theo năm và giai đoạn dùng chung thang màu đối xứng quanh mốc chỉ số 1.
m['nam'] = m['year'].astype(str)
phase_of = dict(zip(yr['year'], yr['ps2_phase_codes']))
m['nam_gd'] = m['nam'] + ' · ' + m['year'].map(phase_of)
m['thang'] = 'T' + m['month'].astype(str)
m['Chỉ số'] = m['month_index'].map(lambda v: num(v, 2))
m['Nhãn chỉ số'] = m['month_index'].map(lambda v: num(v, 1))
m['R (VND)'] = m['r'].map(lambda v: num(v, 2))
m['Tỷ trọng ngày ≥ 26'] = m['eom_share'].map(pct)
m['Mức rải đều'] = m['eom_expected_share'].map(pct)
m['Mức dồn'] = m['eom_excess'].map(pp)
m['nhan_eom'] = m['eom_excess'].map(lambda v: num(v * 100, 0, signed=True))
months = [f'T{i}' for i in range(1, 13)]
color_extent = max((m['month_index'] - 1).abs().max(), (cpm['month_index'] - 1).abs().max())
index_scale = alt.Scale(scheme='redblue', domain=[1 - color_extent, 1 + color_extent], domainMid=1)
white_text = f'abs(datum.month_index - 1) > {0.6 * color_extent:.4f}'


def index_legend(title: str) -> alt.Legend:
    return alt.Legend(title=title, orient='bottom', direction='horizontal', gradientLength=240, titleLimit=600,
                      labelExpr="replace(format(datum.value, '.1f'), '.', ',')")


heat_x = alt.X('thang:O', sort=months, title=None, axis=alt.Axis(labelAngle=0, orient='top'))
heat_y = alt.Y('nam_gd:O', title=None, sort=list(m['nam_gd'].drop_duplicates()))
heat = alt.Chart(m).mark_rect().encode(
    x=heat_x, y=heat_y,
    color=alt.Color('month_index:Q', scale=index_scale,
                    legend=index_legend('Chỉ số tháng (1 = TB tháng của năm đó)')),
    tooltip=[alt.Tooltip('nam', title='Năm'), alt.Tooltip('thang', title='Tháng'), 'Chỉ số', 'R (VND)'])
heat_text = alt.Chart(m).mark_text(fontSize=10).encode(
    x=heat_x, y=heat_y, text='Nhãn chỉ số:N',
    color=alt.condition(white_text, alt.value('white'), alt.value('black')))

eom = alt.Chart(m).mark_rect().encode(
    x=heat_x, y=heat_y,
    color=alt.Color('eom_excess:Q', scale=alt.Scale(scheme='redblue', domainMid=0),
                    legend=alt.Legend(title='Mức dồn cuối tháng (điểm %, 0 = rải đều)', orient='bottom',
                                      direction='horizontal', gradientLength=240, titleLimit=600,
                                      labelExpr="replace(format(datum.value * 100, '.0f'), '-', '−')")),
    tooltip=[alt.Tooltip('nam', title='Năm'), alt.Tooltip('thang', title='Tháng'),
             'Tỷ trọng ngày ≥ 26', 'Mức rải đều', 'Mức dồn'])
eom_text = alt.Chart(m).mark_text(fontSize=10).encode(
    x=heat_x, y=heat_y, text='nhan_eom:N',
    color=alt.condition('datum.eom_excess > 0.11 || datum.eom_excess < -0.02',
                        alt.value('white'), alt.value('black')))

a8 = m[m['month'] == 8].copy()
a8['loai'] = a8['is_odd_year'].map({True: 'năm lẻ', False: 'năm chẵn'})
aug_x = alt.X('nam:O', title=None, axis=alt.Axis(labelAngle=0))
bars = alt.Chart(a8).mark_bar(size=28).encode(
    x=aug_x, y=alt.Y('month_index:Q', title=None,
                   axis=alt.Axis(labelExpr="replace(format(datum.value, '.1f'), '.', ',')")),
    color=alt.Color('loai:N', title=None,
                    scale=alt.Scale(domain=['năm chẵn', 'năm lẻ'], range=['#1f5f8b', '#d1495b']),
                    legend=alt.Legend(orient='top')),
    tooltip=[alt.Tooltip('nam', title='Năm'), alt.Tooltip('loai:N', title='Nhóm'),
             alt.Tooltip('Chỉ số', title='Chỉ số tháng 8'), 'R (VND)'])
bar_text = alt.Chart(a8).mark_text(dy=-8, fontSize=11).encode(x=aug_x, y='month_index:Q', text='Chỉ số:N')
odd_avg = alt.Chart(ap).mark_rule(color='#d1495b', strokeDash=[4, 3]).encode(y='august_index_odd:Q')
even_avg = alt.Chart(ap).mark_rule(color='#1f5f8b', strokeDash=[4, 3]).encode(y='august_index_even:Q')
one = alt.Chart(ap).mark_rule(color='#888').encode(y=alt.datum(1))

# Tháng cao / thấp cả kỳ đọc từ rpt_calendar_stability (cột thêm 2026-10-18, test assert_rpt_gap_peak), không gộp lại
# trong app. Bản dữ liệu dựng trước đó chưa có cột này thì câu tóm tắt không nêu tên tháng; bảng nhiệt vẫn cho thấy.
peak_month, trough_month = (int(v) if v is not None and pd.notna(v) else None
                            for v in (season.get('peak_month'), season.get('trough_month')))
distinct_august = pd.notna(aug['max_index_odd']) and pd.notna(aug['min_index_even'])
august_separated = distinct_august and aug['max_index_odd'] < aug['min_index_even']

rhythm = st.segmented_control('Chọn nhịp lịch',
                              ['Tháng cao / thấp', 'Dồn cuối tháng', 'Tháng 8: năm lẻ / chẵn'],
                              default='Tháng cao / thấp', required=True, wrap=True, key='ps3_rhythm')
if rhythm == 'Tháng cao / thấp':
    chart_title = 'Tháng nào cao, tháng nào thấp?'
    chart = (heat + heat_text).properties(height=390)
    chart_note = ('Chỉ số tháng = R tháng ÷ R bình quân 12 tháng cùng năm; 1 = bình quân. '
                  'Xanh là trên mốc 1, đỏ là dưới mốc 1. Mỗi ô là một tháng của một năm, không phải VND. '
                  'Số trong ô làm tròn một chữ số; tooltip giữ hai chữ số và R đầy đủ.')
    explanation = [
        (f'**Mẫu quan sát:** gộp {int(season["n_years"])} năm, T{peak_month} có R cao nhất; T{trough_month} thấp nhất.'
         if peak_month and trough_month else
         f'**Mẫu quan sát:** gộp {int(season["n_years"])} năm; tháng cao và thấp xem trên bảng nhiệt.'),
        f'**Căn cứ:** tháng cao nhất gấp {num(season["metric_value"], 2)} lần tháng thấp nhất; '
        f'bỏ bớt bất kỳ một năm nào vẫn gấp {num(season["loo_min"], 2)}–{num(season["loo_max"], 2)} lần.',
        f'**Độ lặp lại:** {int(season["n_years_with_pattern"])}/{int(season["n_years"])} năm '
        'đạt điều kiện kiểm tháng cao T4–T6 và thấp T12–T1.',
        '**Giới hạn:** chuẩn hóa theo bình quân năm chưa loại hết xu hướng trong năm; mẫu này chưa giải thích nguyên nhân.',
    ]
elif rhythm == 'Dồn cuối tháng':
    chart_title = 'Doanh thu có dồn cuối tháng không?'
    chart = (eom + eom_text).properties(height=390)
    chart_note = ('Mỗi ô = tỷ trọng R từ ngày 26 trở đi trừ mức rải đều (D − 25)/D, với D là số ngày của tháng. '
                  'Đơn vị: điểm %. Mốc 0 = bằng mức rải đều; dương là cao hơn mốc này. '
                  'Số trong ô làm tròn điểm %; tooltip giữ một chữ số thập phân.')
    explanation = [
        f'**Mẫu quan sát:** toàn kỳ, R từ ngày 26 trở đi chiếm {pct(period["eom_share"])}; '
        f'mốc rải đều là {pct(period["eom_expected_share"])}.',
        f'**Căn cứ:** chênh {pp(period["eom_excess"])}; bỏ từng năm, chênh còn '
        f'{pp(end_month["loo_min"])} đến {pp(end_month["loo_max"])}.',
        f'**Độ lặp lại:** {int(end_month["n_years_with_pattern"])}/{int(end_month["n_years"])} '
        'năm có mức dồn dương.',
        '**Giới hạn:** mốc so sánh tính theo số ngày từng tháng nhưng vẫn giả định R rải đều theo ngày; '
        'chênh lệch điểm % này không phải tốc độ tăng doanh thu.',
    ]
else:
    chart_title = 'Tháng 8 năm lẻ / chẵn: có khác biệt không?'
    chart = (bars + bar_text + odd_avg + even_avg + one).properties(height=330)
    chart_note = (f'Cột = chỉ số tháng 8 từng năm; nét đứt đỏ = TB {n_odd} năm lẻ '
                  f'({num(aug["august_index_odd"], 2)}), nét đứt xanh = TB {n_even} năm chẵn '
                  f'({num(aug["august_index_even"], 2)}); nét xám = mốc 1.')
    separation = ('năm lẻ nào cũng thấp hơn mọi năm chẵn.' if august_separated else
                  'có năm lẻ cao hơn năm chẵn, nhịp này không đều.' if distinct_august else
                  'chưa đủ hai nhóm năm để đối chiếu.')
    explanation = [
        f'**Mẫu quan sát:** TB chỉ số tháng 8 năm lẻ là {num(aug["august_index_odd"], 2)}, '
        f'năm chẵn là {num(aug["august_index_even"], 2)}; chênh {pct(aug["august_odd_vs_even"])}.',
        f'**Căn cứ:** {n_odd} năm lẻ, {n_even} năm chẵn; năm lẻ cao nhất '
        f'{num(aug["max_index_odd"], 2)}, năm chẵn thấp nhất {num(aug["min_index_even"], 2)}: {separation}',
        f'**Độ lặp lại:** {int(august["n_years_with_pattern"])}/{int(august["n_years"])} năm '
        f'đạt điều kiện kiểm; bỏ từng năm, chênh {pct(august["loo_min"])} đến {pct(august["loo_max"])}.',
        '**Giới hạn:** đây là chênh chỉ số chuẩn hóa, không phải chênh tiền; quan sát này chưa chứng minh '
        'quy luật dự báo hay nguyên nhân khuyến mãi.',
    ]

st.subheader(chart_title)
left, side = st.columns([2, 1], gap='medium')
with left:
    st.altair_chart(chart, width='stretch')
    st.caption(chart_note)
    if rhythm == 'Tháng cao / thấp':
        st.caption('Cạnh mỗi năm là mã giai đoạn ở PS2; năm ranh giới có thể mang hai mã, ví dụ A/B. '
                   'Bảng nhiệt này và bảng nhiệt theo giai đoạn **dùng chung một thang màu**.')
with side:
    with st.container(border=True):
        st.markdown('**Tóm tắt từ số liệu**')
        st.caption('Câu viết sẵn theo quy tắc từ số liệu, không do AI viết')
        for item in explanation:
            st.markdown(f'- {item}')
    ai_panel(page_explain.request_ps3({'Tháng cao / thấp': 'mua_vu', 'Dồn cuối tháng': 'cuoi_thang',
                                       'Tháng 8: năm lẻ / chẵn': 'thang_8'}[rhythm]))

tab_repeat, tab_phase, tab_year = st.tabs(['Độ lặp lại', 'So sánh giai đoạn', 'Bảng theo năm'])
right = st.column_config.TextColumn(alignment='right')

# Dùng nguyên chỉ số và phép bỏ từng năm do rpt_calendar_stability tính.
rhythm_names = {
    'mua_vu': ('Tháng cao / thấp', 'Tỷ số tháng cao / thấp', lambda v: num(v, 2) + ' lần',
               'tháng cao nhất thuộc T4–T6 và thấp nhất thuộc T12–T1'),
    'cuoi_thang': ('Dồn cuối tháng', 'Mức dồn cuối tháng', pp, 'mức dồn của năm > 0'),
    'thang_8': ('Tháng 8: lẻ / chẵn', 'Chênh chỉ số tháng 8', pct,
                'năm lẻ thấp hơn mọi năm chẵn, năm chẵn cao hơn mọi năm lẻ'),
}
ts = stab[['rhythm_code']].copy()
ts['Nhịp'] = [rhythm_names[c][0] for c in stab['rhythm_code']]
ts['Chỉ số'] = [rhythm_names[c][1] for c in stab['rhythm_code']]
years_label = f'Cả {int(stab["n_years"].max())} năm'
ts[years_label] = [rhythm_names[c][2](v) for c, v in zip(stab['rhythm_code'], stab['metric_value'])]
ts['Bỏ lần lượt từng năm'] = [f'{rhythm_names[c][2](a)} đến {rhythm_names[c][2](b)}'
                              for c, a, b in zip(stab['rhythm_code'], stab['loo_min'], stab['loo_max'])]
ts['Số năm tự có nhịp'] = [f'{int(k)}/{int(n)}' for k, n in zip(stab['n_years_with_pattern'], stab['n_years'])]
with tab_repeat:
    st.caption('Hai cách kiểm mô tả: xét từng năm và tính lại chỉ số sau khi bỏ lần lượt một năm. '
               'Chưa có kiểm định để kết luận “có ý nghĩa thống kê”.')
    st.dataframe(ts[['Nhịp', 'Số năm tự có nhịp', 'Bỏ lần lượt từng năm']],
                 hide_index=True, height='content', width='stretch')
    with st.expander('Xem bảng đầy đủ & điều kiện kiểm'):
        st.dataframe(ts.drop(columns='rhythm_code'), hide_index=True, height='content', width='stretch',
                     column_config={c: right for c in [years_label, 'Bỏ lần lượt từng năm', 'Số năm tự có nhịp']})
        st.markdown('Năm được tính là “có nhịp” khi ' + '; '.join(
            f'{rhythm_names[c][0]}: {rhythm_names[c][3]}' for c in stab['rhythm_code']) + '. '
            'Phép bỏ từng năm chỉ kiểm độ nhạy với **một năm** tại một lần bỏ.')

# Giữ nguyên quy ước gán năm và cách chuẩn hóa của rpt_calendar_phase_month.
need_keys(cpm['phase_code'], cp.set_index('phase_code'), 'calendar_phase',
          'của giai đoạn có trong bảng tháng')
cp['ten'] = [f'{c}. {n} ({a}–{b})' if a != b else f'{c}. {n} ({a})'      # tên đúng seed BA, như PS4 và chat
             for c, n, a, b in zip(cp['phase_code'], cp['phase_name'], cp['first_year'], cp['last_year'])]
name_of = dict(zip(cp['phase_code'], cp['ten']))
cpm['ten'] = cpm['phase_code'].map(name_of)
cp['nhan'] = [f'{c} ({a}–{b})' if a != b else f'{c} ({a})'
              for c, a, b in zip(cp['phase_code'], cp['first_year'], cp['last_year'])]
cpm['nhan'] = cpm['phase_code'].map(dict(zip(cp['phase_code'], cp['nhan'])))
cpm['thang'] = 'T' + cpm['month'].astype(str)
cpm['Chỉ số'] = cpm['month_index'].map(lambda v: num(v, 2))
cpm['Nhãn chỉ số'] = cpm['month_index'].map(lambda v: num(v, 1))
phase_y = alt.Y('nhan:O', title=None, sort=list(cp['nhan']))
phase_heat = alt.Chart(cpm).mark_rect().encode(
    x=heat_x, y=phase_y,
    color=alt.Color('month_index:Q', scale=index_scale,
                    legend=index_legend('Chỉ số tháng (1 = TB tháng của giai đoạn đó)')),
    tooltip=[alt.Tooltip('ten', title='Giai đoạn'), alt.Tooltip('thang', title='Tháng'), 'Chỉ số'])
phase_text = alt.Chart(cpm).mark_text(fontSize=11).encode(
    x=heat_x, y=phase_y, text='Nhãn chỉ số:N',
    color=alt.condition(white_text, alt.value('white'), alt.value('black')))

tp = cp[['ten']].rename(columns={'ten': 'Giai đoạn'})
tp['Số năm'] = cp['n_years']
tp['Tháng cao nhất'] = [f'T{m} ({num(v, 2)})' for m, v in zip(cp['peak_month'], cp['peak_index'])]
tp['Tháng thấp nhất'] = [f'T{m} ({num(v, 2)})' for m, v in zip(cp['trough_month'], cp['trough_index'])]
tp['Chênh mùa cao / thấp'] = cp['season_peak_trough_ratio'].map(lambda v: num(v, 2) + ' lần')
tp['Mức dồn cuối tháng'] = cp['eom_excess'].map(pp)
tp['Chỉ số T8 năm lẻ'] = cp['august_index_odd'].map(lambda v: num(v, 2))
tp['Chỉ số T8 năm chẵn'] = cp['august_index_even'].map(lambda v: num(v, 2))
tp['Chênh T8 lẻ / chẵn'] = cp['august_odd_vs_even'].map(pct)

season_rank = cp.sort_values('season_ratio_rank')
end_rank = cp.sort_values('eom_excess_rank')
missing_august = cp[cp['august_odd_vs_even'].isna()]
has_august = cp[cp['august_odd_vs_even'].notna()]
phase_notes = [
    'Tháng cao nhất: ' + ', '.join(f'{c} T{m}' for c, m in zip(cp['phase_code'], cp['peak_month']))
    + '; thấp nhất: ' + ', '.join(f'{c} T{m}' for c, m in zip(cp['phase_code'], cp['trough_month'])) + '.',
    f'Mùa vụ mạnh nhất ở {season_rank.iloc[0]["phase_code"]} '
    f'({num(season_rank.iloc[0]["season_peak_trough_ratio"], 2)} lần), '
    f'yếu nhất ở {season_rank.iloc[-1]["phase_code"]} '
    f'({num(season_rank.iloc[-1]["season_peak_trough_ratio"], 2)} lần).',
    ('Dồn cuối tháng ở mọi giai đoạn: ' + ', '.join(
        f'{c} {pp(v)}' for c, v in zip(cp['phase_code'], cp['eom_excess']))
     + f'; cao nhất ở {end_rank.iloc[0]["phase_code"]}, thấp nhất ở {end_rank.iloc[-1]["phase_code"]}.'
     if (cp['eom_excess'] > 0).all() else
     'Mức dồn cuối tháng: ' + ', '.join(
         f'{c} {pp(v)}' for c, v in zip(cp['phase_code'], cp['eom_excess'])) + '.'),
    'Tháng 8 năm lẻ so với năm chẵn: ' + ', '.join(
        f'{c} {pct(v)}' for c, v in zip(has_august['phase_code'], has_august['august_odd_vs_even']))
    + ''.join(f'; {c} không so được vì chỉ có năm {"lẻ" if o > 0 else "chẵn"}'
              for c, o in zip(missing_august['phase_code'], missing_august['n_odd_years'])) + '.',
]
with tab_phase:
    st.caption('**Quy ước riêng của phần so sánh này (chưa được BA chốt):** năm ranh giới được tính cho '
               'giai đoạn kết thúc ở năm đó. Số năm: '
               + '; '.join(f'{c}: {int(n)}' for c, n in zip(cp['phase_code'], cp['n_years'])) + '. '
               'Giai đoạn một năm không đủ cả nhóm năm lẻ và chẵn để so tháng 8.')
    st.altair_chart((phase_heat + phase_text).properties(height=260), width='stretch')
    st.caption('Bảng nhiệt này và bảng theo năm **dùng chung một thang màu**. '
               'Ở đây 1 = TB tháng của cả giai đoạn, tính từ tổng R; bảng theo năm lấy TB của từng năm.')
    st.markdown('**Nhận xét so sánh:**\n' + '\n'.join(f'- {item}' for item in phase_notes))
    st.caption('Giai đoạn ngắn (1–2 năm) kém chắc hơn. Xu hướng R trong năm có thể làm các tháng cuối thấp hơn; '
               'chênh giữa giai đoạn không chứng minh tác động nhân quả.')
    with st.expander('Xem bảng chỉ số giai đoạn'):
        st.dataframe(tp, hide_index=True, height='content', width='stretch',
                     column_config={c: right for c in tp.columns if c not in ('Giai đoạn', 'Số năm')})

tb = yr[['year']].rename(columns={'year': 'Năm'})
tb['Giai đoạn'] = yr['ps2_phase_codes']
tb['Chênh mùa cao / thấp'] = yr['season_peak_trough_ratio'].map(lambda v: num(v, 2) + ' lần')
tb['Tỷ trọng ngày ≥ 26'] = yr['eom_share'].map(pct)
tb['Mức rải đều'] = yr['eom_expected_share'].map(pct)
tb['Mức dồn cuối tháng'] = yr['eom_excess'].map(pp)
tb['Chỉ số tháng 8'] = yr['year'].map(dict(zip(a8['year'], a8['Chỉ số'])))
with tab_year:
    st.dataframe(tb, hide_index=True, height='content', width='stretch',
                 column_config={'Năm': st.column_config.NumberColumn(format='%d'),
                                **{c: right for c in tb.columns if c not in ('Năm', 'Giai đoạn')}})
    st.caption('Chênh tháng cao / thấp là tỷ số lần; mức dồn dùng điểm %; chỉ số tháng 8 không có đơn vị tiền. '
               'Bảng rộng có thể cuộn ngang.')
    st.download_button('Tải bảng theo năm (CSV)', tb.to_csv(index=False).encode('utf-8-sig'),
                       file_name='ps3_bang_theo_nam.csv', mime='text/csv')

with st.expander('Cách đọc & phương pháp'):
    st.markdown('\n'.join(f'- {item}' for item in [
        'Chỉ số tháng = R tháng / bình quân R 12 tháng cùng năm. Tháng có chỉ số thấp không tự chứng minh '
        'kinh doanh sa sút; để xét cùng kỳ, so với chính tháng đó ở các năm khác.',
        'Mức dồn cuối tháng = tỷ trọng R từ ngày 26 trở đi trừ mức rải đều (D − 25)/D của từng tháng; '
        'mức toàn kỳ lấy trọng số theo R tháng. Tháng 2 có ít ngày sau ngày 25 hơn tháng 31 ngày.',
        'So sánh giai đoạn gán năm đầu kỳ cho giai đoạn đầu; năm ranh giới cho giai đoạn kết thúc ở năm đó. '
        'chỉ số tháng giai đoạn = tổng R của tháng qua các năm / bình quân R của 12 tháng giai đoạn, '
        'không phải bình quân chỉ số từng năm.',
        'Tháng 8 năm lẻ trùng thời gian đợt Urban Blowout trong dữ liệu; sự trùng thời gian '
        'không chứng minh tác động khuyến mãi. Nhịp lịch không phải kết quả dự báo.',
    ]))
with st.expander('Giới hạn chi tiết'):
    st.markdown('\n'.join(f'- {item}' for item in [
        'Chuẩn hóa tháng theo bình quân cùng năm chưa loại hết xu hướng trong năm; '
        'năm đang giảm có thể làm các tháng cuối thấp một phần vì xu hướng.',
        f'Đối chiếu tháng 8 dựa trên {n_odd} năm lẻ và {n_even} năm chẵn. '
        'Bỏ từng năm chỉ thử độ nhạy với một năm, chưa đủ để khẳng định quy luật cho các năm sau.',
        f'Năm {build["data_start_date"].year} chưa đủ năm nên không có chỉ số tháng để so nhịp.',
        'Quy ước gán năm ranh giới của PS3 chưa được BA chốt; đổi quy ước thì chỉ số giai đoạn có thể đổi.',
        *GIOI_HAN_CHUNG,
    ]))
