import altair as alt
import pandas as pd
import streamlit as st

from ui.common import GIOI_HAN_CHUNG, hang_the, kpi, load_or_stop, need, need_keys, notes, page_header, pick
from ui.fmt import AXIS_PCT1, AXIS_TRIEU, num, pct, pp, trieu

page_header('PS5: Nhóm kéo lên/xuống', 'Ngành hàng, khu vực, kênh nào kéo doanh thu lên hoặc xuống?')

seg = load_or_stop('segment_yearly')     # 1 dòng = 1 nhóm của MỘT chiều × 1 năm
yearly = load_or_stop('revenue_yearly')
dp = load_or_stop('driver_period')
br = load_or_stop('driver_bridge')
rule = load_or_stop('driver_rule').iloc[0]
nguong = pct(rule['min_abs_delta_rate'], 0)

# Cảnh báo lấy từ deck slide 12 và ghi chú slide 13 (plan §3, tiêu chí 4)
st.warning('**Mỗi chiều (ngành hàng, khu vực, kênh) là một cách chia riêng của cùng một R: không cộng đóng góp giữa các '
           'chiều. Tách số đơn thành số khách C và tần suất F là phép chia số học, chưa phải nguyên nhân.** '
           'Region chỉ là 3 nhãn Central / East / West của dữ liệu mô phỏng. Ít khách mua hơn chưa chắc là khách bỏ đi.')

DIM = {'category': 'Ngành hàng', 'region': 'Khu vực', 'acquisition_channel': 'Kênh thu hút khách'}
c_dim, c_nam = st.columns([2, 1])
dim = c_dim.radio('Chiều (mỗi lần xem một chiều)', [d for d in DIM if d in set(seg['dimension_name'])],
                  format_func=DIM.get, horizontal=True)
nams = sorted(seg.loc[seg['delta_r_rank'].notna(), 'year'].unique().tolist())
nam = c_nam.selectbox('Năm (so với năm trước)', nams, index=nams.index(2019) if 2019 in nams else len(nams) - 1)
ten_chieu = DIM[dim].lower()
y = pick(yearly.set_index('year'), nam, 'revenue_yearly', f'của năm {nam}')
s = need(seg[(seg['dimension_name'] == dim) & (seg['year'] == nam)], 'segment_yearly',
         f'của {ten_chieu} năm {nam}').sort_values('delta_r_rank')
nho = bool(s['delta_r_is_small'].iloc[0])
giam = y['delta_r'] < 0

# --- Thẻ KPI ---
# Feedback 2026-10-01 (F03): thẻ nhóm trả lời thêm "bao nhiêu": tên nhóm (số lớn), số tiền đổi (dòng màu),
# % đóng góp vào mức đổi của cả công ty (dòng phụ). % giữ nguyên dấu, không ép về 0–100%.
dau, cuoi = s.iloc[0], s.iloc[-1]
huong_ct = 'giảm' if giam else 'tăng'


def dong_gop(r) -> str:
    """Dòng phụ dưới số tiền của thẻ nhóm. Chỉ ghép chữ từ contribution_to_delta / delta_r_is_small (dbt tính sẵn)."""
    c = r['contribution_to_delta']
    if pd.isna(c):                   # NULL: ΔR cả công ty = 0, không chia được
        return '% góp không xác định'
    if nho:
        return '% góp không ổn định'
    return f'{pct(c)} tổng mức {huong_ct}'


def the_nhom(col, label: str, r, co: bool, khong_co: str, khong_co_ngan: str, so_nhom: str) -> None:
    if co:
        kpi(col, label, r['dimension_value'],
            f'{r["dimension_value"]}: R {nam - 1} {trieu(r["r_prior_year"], 1)} → R {nam} {trieu(r["r"], 1)}. '
            '% đóng góp = số tiền đổi của nhóm ÷ số tiền đổi của cả công ty (dòng phụ: % của tổng mức tăng / giảm toàn '
            'công ty); âm là nhóm đi ngược chiều cả công ty. "Không xác định": R cả công ty không đổi, không chia được. '
            f'"Không ổn định": R cả công ty đổi dưới {nguong} R năm trước, đọc số tiền.',
            delta=trieu(r['delta_r'], 1, signed=True), delta_sign=r['delta_r'], delta_desc=dong_gop(r))
    else:
        # cùng khuôn với thẻ có nhóm: ô xám (số nhóm tăng/giảm, cột dbt n_groups_*) + dòng xám
        kpi(col, label, 'Không có', khong_co, delta=so_nhom, delta_sign=None, delta_desc=khong_co_ngan)


# Feedback PM 2026-10-02: 3 thẻ cao bằng nhau, cùng một khuôn (số lớn + ô màu cạnh số + dòng xám), có câu dẫn nói thẻ trả lời gì
st.markdown(f'**{nam - 1} → {nam}: R cả công ty đổi bao nhiêu, {ten_chieu} nào kéo nhiều nhất.** '
            f'Dòng màu: số tiền đổi (thẻ đầu: % đổi của R). Dòng xám: nhóm chiếm bao nhiêu % tổng mức {huong_ct} của cả công ty.')
c1, c2, c3 = hang_the('the_ps5', 3)
kpi(c1, f'R cả công ty đổi ({nam - 1}→{nam})', trieu(y['delta_r'], 1, signed=True),
    f'R {nam - 1}: {num(y["r_prior_year"], 2)}; R {nam}: {num(y["r"], 2)} (rpt_revenue_yearly). '
    'Các nhóm của một chiều cộng lại đúng bằng số này.',
    delta=pct(y['yoy_rate'], 1, signed=True), delta_sign=y['yoy_rate'],
    delta_desc=f'R: {num(y["r_prior_year"] / 1e6)} → {num(y["r"] / 1e6)} triệu')
the_nhom(c2, f'{DIM[dim]} tăng nhiều nhất', dau, dau['delta_r'] > 0,
         f'Năm {nam} không nhóm nào tăng; giảm ít nhất là {dau["dimension_value"]} '
         f'({trieu(dau["delta_r"], 1, signed=True)}).', f'Mọi {ten_chieu} đều giảm',
         f'{int(dau["n_groups_up"])}/{int(dau["n_groups"])} nhóm tăng')
the_nhom(c3, f'{DIM[dim]} giảm nhiều nhất', cuoi, cuoi['delta_r'] < 0,
         f'Năm {nam} không nhóm nào giảm; tăng ít nhất là {cuoi["dimension_value"]} '
         f'({trieu(cuoi["delta_r"], 1, signed=True)}).', f'Mọi {ten_chieu} đều tăng',
         f'{int(cuoi["n_groups_down"])}/{int(cuoi["n_groups"])} nhóm giảm')

# --- Xếp hạng nhóm theo số tiền đổi ---
st.subheader(f'Xếp hạng {ten_chieu} theo số tiền đổi, {nam} so với {nam - 1}')
s['Nhóm'] = s['dimension_value']
s['chieu'] = ['tăng' if v >= 0 else 'giảm' for v in s['delta_r']]
s['Đổi'] = s['delta_r'].map(lambda v: trieu(v, 1, signed=True))
bar = alt.Chart(s).mark_bar().encode(
    y=alt.Y('Nhóm:N', sort=list(s['Nhóm']), title=None),
    x=alt.X('delta_r:Q', title=None, axis=alt.Axis(labelExpr=AXIS_TRIEU)),
    color=alt.Color('chieu:N', legend=None, scale=alt.Scale(domain=['tăng', 'giảm'], range=['#2a9d8f', '#d1495b'])),
    tooltip=['Nhóm', 'Đổi'])
# nhãn ở đầu cột: cột dương ghi bên phải, cột âm ghi bên trái
nhan = [alt.Chart(s[s['delta_r'] >= 0]).mark_text(align='left', dx=4, fontSize=12),
        alt.Chart(s[s['delta_r'] < 0]).mark_text(align='right', dx=-4, fontSize=12)]
nhan = [c.encode(y=alt.Y('Nhóm:N', sort=list(s['Nhóm'])), x='delta_r:Q', text='Đổi:N') for c in nhan]
st.altair_chart(alt.layer(bar, *nhan).properties(height=40 * len(s) + 30), width='stretch')

gop = s['contribution_to_delta'].map(pct)
tb = s[['delta_r_rank', 'Nhóm']].rename(columns={'delta_r_rank': 'Hạng'})
tb['Hạng'] = tb['Hạng'].astype(int)
tb[f'R {nam - 1}'] = s['r_prior_year'].map(lambda v: trieu(v, 1))
tb[f'R {nam}'] = s['r'].map(lambda v: trieu(v, 1))
tb['Đổi (tiền)'] = s['Đổi']
tb['Đổi (%)'] = s['yoy_rate'].map(lambda v: pct(v, 1, signed=True))
tb[f'Tỷ trọng {nam}'] = s['share'].map(pct)
tb['Dịch chuyển tỷ trọng'] = s['share_shift_pp'].map(lambda v: num(v, 2, signed=True) + ' điểm %')
tb['% đóng góp vào mức đổi tổng'] = gop + (' (không ổn định)' if nho else '')
right = st.column_config.TextColumn(alignment='right')
st.dataframe(tb, hide_index=True, height='content',
             column_config={c: right for c in tb.columns if c not in ('Hạng', 'Nhóm')})
if nho:
    st.info(f'Năm {nam}, R cả công ty chỉ đổi {trieu(y["delta_r"], 1, signed=True)}, dưới {nguong} R năm trước: '
            '% đóng góp chia cho một số rất nhỏ nên rất lớn và đổi dấu thất thường. Đọc cột số tiền.')

# Nhận xét: chỉ ghép chữ từ các cột (hạng, % đóng góp, dịch chuyển tỷ trọng, số nhóm tăng/giảm tính sẵn trong dbt)
huong = 'giảm' if giam else 'tăng'
chinh = cuoi if giam else dau
nx = [f'{chinh["dimension_value"]} {huong} nhiều nhất ({trieu(chinh["delta_r"], 1, signed=True)}), góp '
      f'{pct(chinh["contribution_to_delta"])} mức {huong} của cả công ty; tỷ trọng của nhóm đổi '
      f'{num(chinh["share_shift_pp"], 2, signed=True)} điểm %.',
      f'Số nhóm {huong}: {int(dau["n_groups_down" if giam else "n_groups_up"])}/{int(dau["n_groups"])}.']
if nho:
    nx[0] = (f'{chinh["dimension_value"]} {huong} nhiều nhất ({trieu(chinh["delta_r"], 1, signed=True)}); '
             f'% đóng góp không ổn định vì R cả công ty gần như không đổi.')
st.markdown('**Nhận xét:**\n' + '\n'.join(f'- {x}' for x in nx))
st.caption('Cách đọc: % đóng góp lớn mà tỷ trọng gần như không đổi nghĩa là nhóm đó đổi cùng nhịp với cả công ty (nhóm lớn '
           'thì góp nhiều). Nhóm có tỷ trọng dịch chuyển nhiều mới là nhóm đi lệch khỏi xu hướng chung.')

# --- Tỷ trọng qua các năm ---
st.subheader(f'Tỷ trọng doanh thu theo {ten_chieu} qua các năm')
sh = seg[(seg['dimension_name'] == dim) & seg['is_analysis_period']].copy()
sh['Nhóm'] = sh['dimension_value']
sh['Năm'] = sh['year'].astype(str)
sh['Tỷ trọng'] = sh['share'].map(pct)
line = alt.Chart(sh).mark_line(point=True).encode(
    x=alt.X('Năm:O', title=None, axis=alt.Axis(labelAngle=0)),
    y=alt.Y('share:Q', title=None, axis=alt.Axis(labelExpr=AXIS_PCT1)),
    color=alt.Color('Nhóm:N', legend=alt.Legend(title=None, orient='top')),
    tooltip=['Năm', 'Nhóm', 'Tỷ trọng'])
st.altair_chart(line.properties(height=300), width='stretch')
st.caption('Tỷ trọng = R của nhóm ÷ R cả công ty cùng năm; các nhóm của một chiều cộng lại 100%.')

# --- C / F: số đơn đổi vì số khách hay vì tần suất mua ---
st.subheader(f'Số đơn toàn công ty, năm {nam}: đổi vì số khách (C) hay vì tần suất mua (F)?')
st.caption(f'Phần này tính trên **toàn công ty**, không chia theo {ten_chieu} đang chọn ở trên '
           '(rpt_driver_period chỉ có số cả công ty).')
d = pick(dp.set_index('period_code'), str(nam), 'driver_period', f'của năm {nam}')
k1, k2, k3 = st.columns(3)
kpi(k1, f'Số đơn toàn công ty đổi ({nam - 1}→{nam})', num(d['delta_n'], 0, signed=True) + ' đơn',
    f'N {nam - 1}: {num(d["n_start"])}; N {nam}: {num(d["n_end"])}. Hai phần bên cạnh cộng lại đúng bằng số này.')
kpi(k2, 'Phần do số khách C', num(d['contrib_c'], 0, signed=True) + ' đơn',
    '(C₁ − C₀) × F₀: số khách có đơn đã giao đổi, giữ số đơn mỗi khách như năm trước.')
kpi(k3, 'Phần do tần suất F', num(d['contrib_f'], 0, signed=True) + ' đơn',
    'C₁ × (F₁ − F₀): số đơn mỗi khách đổi, với số khách năm nay.')
BUOC = {'c': 'Số khách C', 'f': 'Tần suất F'}
w = need(br[(br['period_code'] == str(nam)) & (br['bridge_code'] == 'n_cf')], 'driver_bridge',
         f'của thác số đơn năm {nam}').copy()
w['Cột'] = [f'N {int(v)}' if c in ('n_start', 'n_end') else BUOC[c] for c, v in zip(w['step_code'], w['step_year'])]
w['loai'] = ['Tổng' if c in ('n_start', 'n_end') else ('Tăng' if a >= 0 else 'Giảm')
             for c, a in zip(w['step_code'], w['amount'])]
w['Số đơn'] = [num(a, 0) if c in ('n_start', 'n_end') else num(a, 0, signed=True)
               for c, a in zip(w['step_code'], w['amount'])]
x = alt.X('Cột:N', sort=list(w['Cột']), title=None, axis=alt.Axis(labelAngle=0))
thac = alt.Chart(w).mark_bar(size=60).encode(
    x=x, y=alt.Y('bar_start:Q', title=None, axis=alt.Axis(labelExpr="replace(format(datum.value, ',.0f'), ',', '.')")),
    y2='bar_end:Q',
    color=alt.Color('loai:N', scale=alt.Scale(domain=['Tổng', 'Tăng', 'Giảm'], range=['#1f5f8b', '#2a9d8f', '#d1495b']),
                    legend=alt.Legend(title=None, orient='top')),
    tooltip=['Cột', 'Số đơn'])
chu = alt.Chart(w).transform_calculate(top='max(datum.bar_start, datum.bar_end)').mark_text(dy=-8, fontSize=12).encode(
    x=x, y='top:Q', text='Số đơn:N')
st.altair_chart((thac + chu).properties(height=300), width='stretch')

yr = dp[dp['period_type'] == 'year'].copy()
yy = yearly.set_index('year')
need_keys(yr['end_year'], yy, 'revenue_yearly', 'của năm có trong bảng C/F')
tc =yr[['period_code']].rename(columns={'period_code': 'Năm'})
tc['C (số khách)'] = [num(yy.loc[e, 'c']) for e in yr['end_year']]
tc['F (đơn / khách)'] = [num(yy.loc[e, 'f'], 3) for e in yr['end_year']]
tc['N đổi'] = yr['delta_n'].map(lambda v: num(v, 0, signed=True))
tc['Phần do C'] = yr['contrib_c'].map(lambda v: num(v, 0, signed=True))
tc['Phần do F'] = yr['contrib_f'].map(lambda v: num(v, 0, signed=True))
st.dataframe(tc, hide_index=True, height='content', column_config={c: right for c in tc.columns if c != 'Năm'})

notes(
    cach_doc=[
        'Mỗi lần chỉ xem một chiều. Các nhóm trong một chiều cộng lại đúng bằng R cả công ty (kiểm trong dbt); '
        'ba chiều là ba cách chia khác nhau của cùng một R nên không cộng với nhau.',
        '% đóng góp = số tiền đổi của nhóm ÷ số tiền đổi của cả công ty. Có thể âm (nhóm đi ngược chiều cả công ty) '
        'hoặc trên 100% (nhóm khác bù lại).',
        'Dịch chuyển tỷ trọng tính bằng điểm %: tỷ trọng năm nay trừ tỷ trọng năm trước.',
        'Số đơn N = số khách C × số đơn mỗi khách F. Phần do C là do số khách có đơn đã giao đổi; phần do F là do mỗi '
        'khách mua nhiều hay ít đơn hơn.',
    ],
    gioi_han=[
        'Region chỉ là 3 nhãn Central / East / West của dữ liệu mô phỏng, không tự ánh xạ thành vùng thật.',
        'acquisition_channel là kênh thu hút khách (gắn với khách), khác nguồn của từng đơn.',
        'C đếm khách có đơn đã giao trong năm: ít khách mua hơn chưa chắc là khách bỏ đi (chưa đo churn).',
        f'Năm có mức đổi R dưới {nguong} R năm trước: % đóng góp không ổn định. Ngưỡng do dev đề xuất, chờ BA chốt '
        '(seed driver_rule).',
        *GIOI_HAN_CHUNG,
    ],
)
