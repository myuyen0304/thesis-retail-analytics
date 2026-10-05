import altair as alt
import streamlit as st

from ui.common import GIOI_HAN_CHUNG, kpi, load_or_stop, need, need_keys, notes, page_header, pick
from ui.fmt import num, pct, pp

page_header('PS3: Nhịp lịch', 'Doanh thu dồn vào tháng nào, ngày nào, và có lặp lại qua các năm không?')

monthly = load_or_stop('revenue_monthly')
yearly = load_or_stop('revenue_yearly')
total = load_or_stop('revenue_total')
ap = load_or_stop('august_parity')
stab = load_or_stop('calendar_stability')         # độ ổn định 3 nhịp (deck slide 8 yêu cầu 5)
cp = load_or_stop('calendar_phase')               # so sánh giữa các giai đoạn PS2 (slide 8 yêu cầu 2)
cpm = load_or_stop('calendar_phase_month')
aug = ap.iloc[0]
n_le, n_chan = int(aug['n_odd_years']), int(aug['n_even_years'])   # 1 dòng nhiều kiểu cột: iloc đổi số đếm thành float

# Chỉ số tháng chỉ có ở năm đủ 12 tháng (2012 để NULL), nên mọi phần dưới đây dùng kỳ phân tích
m = need(monthly[monthly['is_analysis_period']], 'revenue_monthly', 'của kỳ phân tích').copy()
yr = yearly[yearly['is_analysis_period']].copy()
ky = need(total[total['is_analysis_period']], 'revenue_total', 'của kỳ phân tích').iloc[0]
need_keys(m['year'], yr.set_index('year'), 'revenue_yearly', 'của năm có trong bảng tháng')
ky_label = f'{ky["start_year"]}–{ky["end_year"]}'
m['nam'] = m['year'].astype(str)
# nhãn giai đoạn PS2 cạnh mỗi năm (cột ps2_phase_codes của rpt_revenue_yearly; năm ranh giới thuộc hai giai đoạn: 'A/B')
phase_of = dict(zip(yr['year'], yr['ps2_phase_codes']))
m['nam_gd'] = m['nam'] + ' · ' + m['year'].map(phase_of)
m['thang'] = 'T' + m['month'].astype(str)
THANG = [f'T{i}' for i in range(1, 13)]

# Feedback 2026-10-01 (F04): hai bảng nhiệt chỉ số tháng (tháng × năm, tháng × giai đoạn) dùng CHUNG một thang màu:
# cùng giá trị → cùng màu. Miền đối xứng quanh 1, lấy từ cực trị của cả hai bảng nên không ô nào bị bão hòa màu.
_lech = max((m['month_index'] - 1).abs().max(), (cpm['month_index'] - 1).abs().max())
THANG_CHI_SO = alt.Scale(scheme='redblue', domain=[1 - _lech, 1 + _lech], domainMid=1)
CHU_TRANG_CHI_SO = f'abs(datum.month_index - 1) > {0.6 * _lech:.4f}'      # ô màu đậm (cả hai đầu thang) → chữ trắng


def chu_giai_chi_so(tieu_de: str) -> alt.Legend:
    return alt.Legend(title=tieu_de, orient='bottom', direction='horizontal', gradientLength=320, titleLimit=600,
                      labelExpr="replace(format(datum.value, '.1f'), '.', ',')")

# --- Thẻ KPI: 3 nhịp của deck slide 8, mỗi thẻ một số ngắn (khoảng bỏ-từng-năm nằm ở bảng độ ổn định) ---
mua = pick(stab.set_index('rhythm_code'), 'mua_vu', 'calendar_stability', 'của nhịp mùa vụ')
c1, c2, c3 = st.columns(3)
kpi(c1, f'Tháng 8 năm lẻ / chẵn ({ky_label})', pct(aug['august_odd_vs_even']),
    f'TB chỉ số tháng 8 của {n_le} năm lẻ ÷ TB của {n_chan} năm chẵn − 1. '
    f'Năm lẻ: {num(aug["august_index_odd"], 2)}; năm chẵn: {num(aug["august_index_even"], 2)}. '
    f'Bỏ lần lượt từng năm, chênh vẫn từ {pct(aug["loo_min_odd_vs_even"])} đến {pct(aug["loo_max_odd_vs_even"])}.')
kpi(c2, f'Chênh mùa cao / thấp ({ky_label})', num(mua['metric_value'], 2) + ' lần',
    'Chỉ số tháng gộp các năm: R tháng cao nhất ÷ R tháng thấp nhất (cộng các năm). '
    f'Bỏ lần lượt từng năm, vẫn từ {num(mua["loo_min"], 2)} đến {num(mua["loo_max"], 2)} lần.')
kpi(c3, f'Mức dồn về cuối tháng ({ky_label})', pp(ky['eom_excess']),
    f'Tỷ trọng R từ ngày 26 trở đi: {pct(ky["eom_share"])}. Mức so sánh {pct(ky["eom_expected_share"])} = nếu R rải đều '
    'theo ngày trong từng tháng, giữ nguyên doanh thu mỗi tháng (mỗi tháng (D − 25)/D, cộng lại theo trọng số R tháng). '
    'Dương là dồn về cuối tháng.')

# --- Nhịp 1: theo tháng ---
st.subheader('Nhịp 1: tháng nào cao, tháng nào thấp?')
st.caption('Cạnh mỗi năm là giai đoạn ở trang PS2 (A–D); năm ranh giới thuộc cả hai giai đoạn, ví dụ "A/B". '
           'Chỉ số tháng = R tháng ÷ TB 12 tháng cùng năm; 1 = tháng bình thường. Xanh: cao hơn bình thường, '
           'đỏ: thấp hơn. Mỗi ô là một tháng của một năm, không lấy trung bình. Bảng này và bảng theo giai đoạn ở dưới '
           '**dùng chung một thang màu**: cùng chỉ số thì cùng màu.')
m['Chỉ số'] = m['month_index'].map(lambda v: num(v, 2))
m['R'] = m['r'].map(lambda v: num(v, 2))
heat_x = alt.X('thang:O', sort=THANG, title=None, axis=alt.Axis(labelAngle=0, orient='top'))
heat_y = alt.Y('nam_gd:O', title=None)
heat = alt.Chart(m).mark_rect().encode(
    x=heat_x, y=heat_y,
    color=alt.Color('month_index:Q', scale=THANG_CHI_SO,
                    legend=chu_giai_chi_so('Chỉ số tháng (1 = TB tháng của năm đó)')),
    tooltip=[alt.Tooltip('nam', title='Năm'), alt.Tooltip('thang', title='Tháng'), 'Chỉ số', 'R'])
heat_text = alt.Chart(m).mark_text(fontSize=12).encode(
    x=heat_x, y=heat_y, text='Chỉ số:N',
    color=alt.condition(CHU_TRANG_CHI_SO, alt.value('white'), alt.value('black')))
st.altair_chart((heat + heat_text).properties(height=390), width='stretch')

# --- Nhịp 2: cuối tháng ---
st.subheader('Nhịp 2: doanh thu có dồn về cuối tháng không?')
st.caption('Mỗi ô = tỷ trọng R từ ngày 26 trở đi, trừ mức rải đều (D − 25)/D, D = số ngày trong tháng. Đơn vị: điểm %. '
           'Xanh: dồn về cuối tháng; đỏ: ít hơn mức rải đều.')
m['Tỷ trọng ngày ≥ 26'] = m['eom_share'].map(pct)
m['Mức rải đều'] = m['eom_expected_share'].map(pct)
m['Mức dồn'] = m['eom_excess'].map(pp)
m['nhan_eom'] = m['eom_excess'].map(lambda v: num(v * 100, 1, signed=True))
eom = alt.Chart(m).mark_rect().encode(
    x=heat_x, y=heat_y,
    # thang riêng theo điểm %, tâm 0 (không dùng chung với chỉ số tháng)
    color=alt.Color('eom_excess:Q', scale=alt.Scale(scheme='redblue', domainMid=0),
                    legend=alt.Legend(title='Mức dồn cuối tháng (điểm %, 0 = rải đều)', orient='bottom',
                                      direction='horizontal', gradientLength=320, titleLimit=600,
                                      labelExpr="replace(format(datum.value * 100, '.0f'), '-', '−')")),
    tooltip=[alt.Tooltip('nam', title='Năm'), alt.Tooltip('thang', title='Tháng'),
             'Tỷ trọng ngày ≥ 26', 'Mức rải đều', 'Mức dồn'])
eom_text = alt.Chart(m).mark_text(fontSize=12).encode(
    x=heat_x, y=heat_y, text='nhan_eom:N',
    color=alt.condition('datum.eom_excess > 0.11 || datum.eom_excess < -0.02', alt.value('white'), alt.value('black')))
st.altair_chart((eom + eom_text).properties(height=390), width='stretch')

# --- Nhịp 3: tháng 8 năm lẻ ---
st.subheader('Nhịp 3: tháng 8 năm lẻ thấp hơn năm chẵn')
a8 = m[m['month'] == 8].copy()
a8['loai'] = a8['is_odd_year'].map({True: 'năm lẻ', False: 'năm chẵn'})
ax = alt.X('nam:O', title=None, axis=alt.Axis(labelAngle=0))
bars = alt.Chart(a8).mark_bar(size=34).encode(
    x=ax, y=alt.Y('month_index:Q', title=None, axis=alt.Axis(labelExpr="replace(format(datum.value, '.1f'), '.', ',')")),
    color=alt.Color('loai:N', title=None, scale=alt.Scale(domain=['năm chẵn', 'năm lẻ'], range=['#1f5f8b', '#d1495b']),
                    legend=alt.Legend(orient='top')),
    tooltip=[alt.Tooltip('nam', title='Năm'), alt.Tooltip('Chỉ số', title='Chỉ số tháng 8'), 'R'])
bar_text = alt.Chart(a8).mark_text(dy=-8, fontSize=12).encode(x=ax, y='month_index:Q', text='Chỉ số:N')
# đường TB năm lẻ / năm chẵn: 2 cột của rpt_august_parity
avg_le = alt.Chart(ap).mark_rule(color='#d1495b', strokeDash=[4, 3]).encode(y='august_index_odd:Q')
avg_chan = alt.Chart(ap).mark_rule(color='#1f5f8b', strokeDash=[4, 3]).encode(y='august_index_even:Q')
one = alt.Chart(ap).mark_rule(color='#888').encode(y=alt.datum(1))
st.altair_chart((bars + bar_text + avg_le + avg_chan + one).properties(height=300), width='stretch')
tach = (': năm lẻ nào cũng thấp hơn mọi năm chẵn.' if aug['max_index_odd'] < aug['min_index_even']
        else ': có năm lẻ cao hơn năm chẵn, nhịp này không đều.')
st.caption(f'Cột = chỉ số tháng 8 của từng năm. Đường gạch = TB năm lẻ ({num(aug["august_index_odd"], 2)}) và năm chẵn '
           f'({num(aug["august_index_even"], 2)}); đường xám = 1. Năm lẻ cao nhất {num(aug["max_index_odd"], 2)}, '
           f'năm chẵn thấp nhất {num(aug["min_index_even"], 2)}{tach}')

right = st.column_config.TextColumn(alignment='right')

# --- Độ ổn định của 3 nhịp (deck slide 8 yêu cầu 5) ---
st.subheader('Ba nhịp có ổn định không, hay do vài năm kéo?')
NHIP = {'mua_vu': ('Nhịp 1: mùa cao T4–T6, thấp T12–T1', 'Chênh mùa cao / thấp (gộp các năm)',
                   lambda v: num(v, 2) + ' lần', 'tháng cao nhất thuộc T4–T6 và thấp nhất thuộc T12–T1'),
        'cuoi_thang': ('Nhịp 2: dồn về cuối tháng', 'Mức dồn cuối tháng', pp, 'mức dồn của năm > 0'),
        'thang_8': ('Nhịp 3: tháng 8 năm lẻ thấp', 'Chênh tháng 8 lẻ / chẵn', pct,
                    'năm lẻ thấp hơn mọi năm chẵn, năm chẵn cao hơn mọi năm lẻ')}
ts = stab[['rhythm_code']].copy()
ts['Nhịp'] = [NHIP[c][0] for c in stab['rhythm_code']]
ts['Chỉ số'] = [NHIP[c][1] for c in stab['rhythm_code']]
ts['Cả 10 năm'] = [NHIP[c][2](v) for c, v in zip(stab['rhythm_code'], stab['metric_value'])]
ts['Bỏ lần lượt từng năm'] = [f'{NHIP[c][2](a)} đến {NHIP[c][2](b)}'
                              for c, a, b in zip(stab['rhythm_code'], stab['loo_min'], stab['loo_max'])]
ts['Số năm tự có nhịp'] = [f'{int(k)}/{int(n)}' for k, n in zip(stab['n_years_with_pattern'], stab['n_years'])]
st.dataframe(ts.drop(columns='rhythm_code'), hide_index=True, height='content',
             column_config={c: right for c in ['Cả 10 năm', 'Bỏ lần lượt từng năm', 'Số năm tự có nhịp']})
st.caption('Hai cách kiểm: (1) tính lại chỉ số 10 lần, mỗi lần bỏ một năm, xem một năm bất thường kéo được bao nhiêu; '
           '(2) xét riêng từng năm xem năm đó có nhịp không. Năm "có nhịp": '
           + '; '.join(f'nhịp {i} = {NHIP[c][3]}' for i, c in enumerate(stab['rhythm_code'], 1))
           + '. Nhịp có ở gần hết các năm thì không thể do vài năm tạo ra. '
           'Giới hạn: chỉ có 10 năm, và cách (1) chỉ bỏ một năm mỗi lần.')

# --- So sánh giữa các giai đoạn PS2 (deck slide 8 yêu cầu 2) ---
st.subheader('So sánh nhịp lịch giữa các giai đoạn')
cp['ten'] = [f'{c}. {n} ({a}–{b})' if a != b else f'{c}. {n} ({a})'
             for c, n, a, b in zip(cp['phase_code'], cp['phase_name'], cp['first_year'], cp['last_year'])]
ten_of = dict(zip(cp['phase_code'], cp['ten']))
st.caption('**Quy ước riêng của phần so sánh này (chưa được BA chốt):** PS3 gom doanh thu theo năm lịch, nên mỗi năm chỉ '
           'được tính cho một giai đoạn: **năm ranh giới tính cho giai đoạn kết thúc ở năm đó** (năm "A/B" tính cho A, '
           '"B/C" cho B, "C/D" cho C), năm đầu tiên tính cho giai đoạn đầu. Nền màu ở trang PS2 là mốc trên đường R 12 '
           'tháng, không phải cách chia năm này. Kết quả: '
           + '; '.join(cp['ten']) + '. Chỉ số tháng của giai đoạn = R tháng đó cộng các năm ÷ TB tháng của giai đoạn '
           '(tính lại từ tổng, không lấy trung bình chỉ số các năm).')
cpm['ten'] = cpm['phase_code'].map(ten_of)
# nhãn ngắn cho trục bảng nhiệt (tên đầy đủ trong tooltip và bảng dưới)
cp['nhan'] = [f'{c} ({a}–{b})' if a != b else f'{c} ({a})'
              for c, a, b in zip(cp['phase_code'], cp['first_year'], cp['last_year'])]
cpm['nhan'] = cpm['phase_code'].map(dict(zip(cp['phase_code'], cp['nhan'])))
cpm['thang'] = 'T' + cpm['month'].astype(str)
cpm['Chỉ số'] = cpm['month_index'].map(lambda v: num(v, 2))
py = alt.Y('nhan:O', title=None, sort=list(cp['nhan']))
ph_heat = alt.Chart(cpm).mark_rect().encode(
    x=heat_x, y=py,
    color=alt.Color('month_index:Q', scale=THANG_CHI_SO,
                    legend=chu_giai_chi_so('Chỉ số tháng (1 = TB tháng của giai đoạn đó)')),
    tooltip=[alt.Tooltip('ten', title='Giai đoạn'), alt.Tooltip('thang', title='Tháng'), 'Chỉ số'])
ph_text = alt.Chart(cpm).mark_text(fontSize=12).encode(
    x=heat_x, y=py, text='Chỉ số:N',
    color=alt.condition(CHU_TRANG_CHI_SO, alt.value('white'), alt.value('black')))
st.altair_chart((ph_heat + ph_text).properties(height=260), width='stretch')
st.caption('Cùng thang màu với bảng nhiệt theo năm ở Nhịp 1, nên so màu được giữa hai bảng. Mẫu số khác nhau: ở đây 1 = '
           'TB tháng của cả giai đoạn; ở Nhịp 1, 1 = TB tháng của từng năm.')

tp = cp[['ten']].rename(columns={'ten': 'Giai đoạn'})
tp['Số năm'] = cp['n_years']
tp['Tháng cao nhất'] = [f'T{m} ({num(v, 2)})' for m, v in zip(cp['peak_month'], cp['peak_index'])]
tp['Tháng thấp nhất'] = [f'T{m} ({num(v, 2)})' for m, v in zip(cp['trough_month'], cp['trough_index'])]
tp['Chênh mùa cao / thấp'] = cp['season_peak_trough_ratio'].map(lambda v: num(v, 2) + ' lần')
tp['Mức dồn cuối tháng'] = cp['eom_excess'].map(pp)
tp['Chỉ số T8 năm lẻ'] = cp['august_index_odd'].map(lambda v: num(v, 2))
tp['Chỉ số T8 năm chẵn'] = cp['august_index_even'].map(lambda v: num(v, 2))
tp['Chênh T8 lẻ / chẵn'] = cp['august_odd_vs_even'].map(pct)
st.dataframe(tp, hide_index=True, height='content',
             column_config={c: right for c in tp.columns if c not in ('Giai đoạn', 'Số năm')})

# Nhận xét so sánh: chỉ ghép chữ từ các cột (thứ hạng tính sẵn trong dbt), không tự tính
cao = cp.sort_values('season_ratio_rank')
don = cp.sort_values('eom_excess_rank')
thieu = cp[cp['august_odd_vs_even'].isna()]
co_t8 = cp[cp['august_odd_vs_even'].notna()]
nhan_xet = [
    'Tháng cao nhất: ' + ', '.join(f'{c} T{m}' for c, m in zip(cp['phase_code'], cp['peak_month']))
    + '; thấp nhất: ' + ', '.join(f'{c} T{m}' for c, m in zip(cp['phase_code'], cp['trough_month'])) + '.',
    f'Mùa vụ mạnh nhất ở {cao.iloc[0]["phase_code"]} ({num(cao.iloc[0]["season_peak_trough_ratio"], 2)} lần), '
    f'yếu nhất ở {cao.iloc[-1]["phase_code"]} ({num(cao.iloc[-1]["season_peak_trough_ratio"], 2)} lần).',
    'Dồn cuối tháng ở mọi giai đoạn: ' + ', '.join(f'{c} {pp(v)}' for c, v in zip(cp['phase_code'], cp['eom_excess']))
    + f'; cao nhất ở {don.iloc[0]["phase_code"]}, thấp nhất ở {don.iloc[-1]["phase_code"]}.'
    if (cp['eom_excess'] > 0).all() else
    'Mức dồn cuối tháng: ' + ', '.join(f'{c} {pp(v)}' for c, v in zip(cp['phase_code'], cp['eom_excess'])) + '.',
    'Tháng 8 năm lẻ so với năm chẵn: ' + ', '.join(f'{c} {pct(v)}' for c, v in zip(co_t8['phase_code'],
                                                                              co_t8['august_odd_vs_even']))
    + ''.join(f'; {c} không so được vì chỉ có năm {"lẻ" if o > 0 else "chẵn"}'
              for c, o in zip(thieu['phase_code'], thieu['n_odd_years']))
    + '.',
]
st.markdown('**Nhận xét so sánh:**\n' + '\n'.join(f'- {x}' for x in nhan_xet))
st.caption('Giai đoạn ngắn (1–2 năm) cho kết quả kém chắc hơn giai đoạn dài. Năm doanh thu đang giảm trong năm thì các '
           'tháng cuối năm thấp hơn một phần vì xu hướng, làm chênh mùa lớn hơn: xem cột "Chênh mùa cao / thấp" ở bảng '
           'theo năm bên dưới trước khi kết luận giai đoạn nào có mùa vụ mạnh hơn.')

# --- Bảng theo năm ---
st.subheader('Theo năm')
tb = yr[['year']].rename(columns={'year': 'Năm'})
tb['Giai đoạn'] = yr['ps2_phase_codes']
tb['Chênh mùa cao / thấp'] = yr['season_peak_trough_ratio'].map(lambda v: num(v, 2) + ' lần')
tb['Tỷ trọng ngày ≥ 26'] = yr['eom_share'].map(pct)
tb['Mức rải đều'] = yr['eom_expected_share'].map(pct)
tb['Mức dồn cuối tháng'] = yr['eom_excess'].map(pp)
tb['Chỉ số tháng 8'] = yr['year'].map(dict(zip(a8['year'], a8['Chỉ số'])))
st.dataframe(tb, hide_index=True, height='content',
             column_config={'Năm': st.column_config.NumberColumn(format='%d'),
                            **{c: right for c in tb.columns if c not in ('Năm', 'Giai đoạn')}})
st.caption('Chênh mùa cao / thấp = chỉ số tháng cao nhất ÷ thấp nhất trong năm; càng lớn, mùa vụ càng mạnh.')

notes(
    cach_doc=[
        'Tháng có chỉ số thấp theo mùa (cuối năm, đầu năm) không có nghĩa là kinh doanh sa sút: so với cùng tháng các năm khác, '
        'không so với tháng liền trước.',
        'Mức dồn cuối tháng tính theo điểm %: tỷ trọng thực tế trừ mức rải đều. Mức rải đều khác nhau theo tháng '
        '(tháng 2 có 28 ngày thì chỉ 3/28), nên phải trừ theo từng tháng, không so tỷ trọng thô.',
        'Tháng 8 năm lẻ trùng đợt khuyến mãi lớn "Urban Blowout". Tháng 8/2023 là năm lẻ và nằm trong kỳ dự báo.',
        'Mọi con số ở đây chỉ mô tả nhịp lịch, không giải thích vì sao.',
    ],
    gioi_han=[
        'Chỉ số tháng chia cho TB cùng năm nên không loại hết xu hướng trong năm: năm đang giảm thì các tháng '
        'cuối năm thấp hơn một phần vì xu hướng, không chỉ vì mùa.',
        f'Nhịp tháng 8 chỉ dựa trên {n_le} năm lẻ và {n_chan} năm chẵn. Đây là quan sát để '
        'thăm dò, chưa phải quy luật dự báo chắc chắn.',
        'Năm 2012 không có chỉ số tháng vì chỉ có nửa năm.',
        'Kiểm tra độ ổn định chỉ bỏ một năm mỗi lần và chỉ có 10 năm dữ liệu: đủ để nói nhịp không do một năm riêng lẻ '
        'tạo ra, chưa đủ để coi là quy luật chắc chắn cho các năm sau.',
        'So sánh giai đoạn dùng quy ước năm ranh giới riêng của PS3 (chưa được BA chốt); đổi quy ước (vd. tính năm ranh '
        'giới cho giai đoạn sau) thì số của từng giai đoạn sẽ khác.',
        *GIOI_HAN_CHUNG,
    ],
)
