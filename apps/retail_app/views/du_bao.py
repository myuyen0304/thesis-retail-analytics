
"""Trang Dự báo (B3b, docs/ke_hoach_ai_gd2.md; hợp đồng docs/hop_dong_du_bao.md §2.2, §6–§8).

Đọc reporting.rpt_forecast_daily / rpt_forecast_backtest của bản dữ liệu đang phục vụ. Trang không train, không chọn
model: ứng viên chính (is_primary) do luật chọn trong pipeline quyết (Q8). Bản dữ liệu không có dự báo (chế độ cũ,
PostgreSQL, bản trước B2b) thì báo trạng thái, không lỗi. Số dự báo chỉ ở trang này, không trộn vào trang PS1–PS5.
Nhãn model / cách COGS / lý do chọn dùng chung với chat (ai_explain/tools.py) để trang và chat nói cùng một câu.
"""
import datetime as dt

import altair as alt
import pandas as pd
import streamlit as st

from ai_explain import metric_catalog as cat
from ai_explain.tools import BACKTEST_NOTE, COGS_LABEL, MODEL_LABEL, SELECTION_REASON
from ai_explain.tools import _missing_relation as thieu_bang
from dwh import forecast_queries as fq
from dwh import releases
from dwh.connection import release_for_read
from ui.common import BACKEND_LABEL, backend, hang_the, kpi, notes, page_header
from ui.fmt import AXIS_TRIEU, num, pct, trieu, ty

START, END = (pd.Timestamp(d) for d in cat.FORECAST_HORIZON)
N_DAYS = (END - START).days + 1
CAU_BACKTEST = 'sai số backtest 2020–2022, không phải độ chính xác 2023–2024'
BUOC = {'buoc_1_khong_ung_vien_nao_qua_san': 'bước 1: không ứng viên nào qua sàn, dùng mốc',
        'buoc_2_diem_thap_nhat': 'bước 2: điểm thấp nhất',
        'buoc_3_hoa_chon_don_gian': 'bước 3: hòa, chọn ứng viên đơn giản hơn'}
MAU = {'thực tế': '#7a8491', 'dự báo': '#e07b39'}
right = st.column_config.TextColumn(alignment='right')


@st.cache_data(ttl=600, show_spinner=False)
def _doc(name: str, backend_name: str, release_id: str = '') -> tuple[pd.DataFrame, dt.datetime]:
    # release_id trong khóa cache: đổi bản dữ liệu thì không lấy số của bản cũ
    return getattr(fq, name)(backend_name), dt.datetime.now()


def doc(name: str) -> pd.DataFrame:
    """Đọc một bảng của trang và ghi lại cho dòng nguồn cuối trang (ui/common.report_reads)."""
    b = backend()
    record = release_for_read(b)
    df, read_at = _doc(name, b, record['release_id'] if record else '')
    st.session_state.setdefault('_reads', {})[name] = (len(df), read_at)
    return df


def ngay(x) -> str:
    return pd.Timestamp(x).strftime('%d/%m/%Y')


def nhan_ung_vien(model: str, cogs: str) -> str:
    return f'{MODEL_LABEL.get(model, model)} · {COGS_LABEL.get(cogs, cogs)}'


def mape(x) -> str:
    return '–' if pd.isna(x) else num(x, 1) + '%'          # mape_g_thang đã nhân 100 (metric_catalog)


def dung(thong_bao: str) -> None:
    st.session_state.pop('reloaded', None)
    st.warning(thong_bao)
    st.stop()


def du_lieu(fc: pd.DataFrame, thuc_te: pd.DataFrame | None, cot_tt: str, cot_db: str) -> pd.DataFrame:
    parts = [pd.DataFrame({'ngay': fc['forecast_date'], 'loai': 'dự báo', 'value': fc[cot_db]})]
    if thuc_te is not None:
        parts.insert(0, pd.DataFrame({'ngay': thuc_te['sale_date'], 'loai': 'thực tế', 'value': thuc_te[cot_tt]}))
    df = pd.concat(parts, ignore_index=True)
    df['nhan'] = df['value'].map(lambda v: trieu(v, 2))
    return df


def bieu_do(df: pd.DataFrame, ten: str, khoang: pd.DataFrame | None = None) -> alt.LayerChart:
    x = alt.X('ngay:T', title=None, axis=alt.Axis(format='%m/%Y', labelAngle=0))
    mau = alt.Color('loai:N', title=None, scale=alt.Scale(domain=list(MAU), range=list(MAU.values())),
                    legend=alt.Legend(orient='top', labelExpr=f"'{ten} ' + datum.label"))
    tip = [alt.Tooltip('ngay:T', title='Ngày', format='%d/%m/%Y'), alt.Tooltip('loai:N', title='Loại'),
           alt.Tooltip('nhan:N', title=ten)]
    lop = []
    if khoang is not None:
        lop.append(alt.Chart(khoang).mark_area(color=MAU['dự báo'], opacity=0.22).encode(
            x=x, y='lower:Q', y2='upper:Q',
            tooltip=[alt.Tooltip('ngay:T', title='Ngày', format='%d/%m/%Y'),
                     alt.Tooltip('duoi:N', title='Cận dưới 80%'), alt.Tooltip('tren:N', title='Cận trên 80%')]))
    lop.append(alt.Chart(df).mark_line(strokeWidth=1.1).encode(
        x=x, y=alt.Y('value:Q', title=None, axis=alt.Axis(labelExpr=AXIS_TRIEU)), color=mau, tooltip=tip))
    moc = pd.DataFrame({'ngay': [START], 'chu': ['bắt đầu dự báo']})
    lop.append(alt.Chart(moc).mark_rule(color='#444', strokeDash=[4, 3]).encode(x='ngay:T'))
    lop.append(alt.Chart(moc).mark_text(align='left', dx=4, dy=-6, color='#444').encode(
        x='ngay:T', y=alt.value(8), text='chu:N'))
    return alt.layer(*lop).properties(height=300)


def chua_co_du_bao(b: str, e: Exception) -> None:
    """Bản dữ liệu không có rpt_forecast_*: báo trạng thái rồi kết thúc trang bình thường (dòng nguồn cuối trang vẫn hiện).
    Lỗi khác (kết nối, quyền) thì cảnh báo và dừng như các trang khác."""
    if not thieu_bang(e):
        dung(f'Không đọc được bảng dự báo từ {BACKEND_LABEL[b]}: {type(e).__name__}. Bấm **Đọc lại dữ liệu**; '
             'lỗi còn thì xem trang **Sức khỏe dữ liệu**.')
    record = releases.current() if releases.enabled(b) else None
    vi_sao = (f'Bản dữ liệu đang phục vụ (`{record["release_id"]}`, lần chạy `{record.get("run_id", "?")}`) không có '
              'bảng dự báo, thường vì bản này dựng trước bước B2b.' if record else
              f'App đang đọc **{BACKEND_LABEL[b]}** ở chế độ cũ (không theo bản dữ liệu). Dự báo chỉ có trong bản dữ '
              'liệu do pipeline dựng từ bước B2b: chế độ versioned, DuckDB trên máy.')
    st.info(f'**Chưa có dự báo để hiện.** {vi_sao} Trang không lấy số ở nguồn khác thay vào.  \n'
            'Cách mở bản có dự báo: `docs/dwh_huong_dan_pm_ba.md` §9, mục trang Dự báo.')


def hien_du_bao(fc: pd.DataFrame, bt: pd.DataFrame) -> None:
    ung_vien = fc[['model', 'cogs_method']].drop_duplicates()
    if (len(ung_vien) != 1 or len(fc) != N_DAYS or not fc['forecast_date'].is_unique
            or fc['forecast_date'].min() != START or fc['forecast_date'].max() != END):
        dung(f'Bảng `{fq.SOURCE["forecast_daily"]}` của bản này không có đúng một ứng viên chính đủ {N_DAYS} ngày '
             f'({len(ung_vien)} ứng viên, {len(fc)} dòng), nên trang không hiện số. Quality gate của pipeline lẽ ra đã chặn '
             'bản này: xem trang **Sức khỏe dữ liệu**.')
    p = fc.iloc[0]
    key = (p['model'], p['cogs_method'])
    ten_chinh = nhan_ung_vien(*key)

    # --- Backtest: trung bình 3 fold mỗi ứng viên; thắng mốc sàn = điểm thấp hơn mốc ở cả 3 fold (luật bước 1) ---
    diem = bt[bt['metric'] == 'score'].pivot_table(index=['model', 'cogs_method'], columns='fold_origin', values='value')
    tb = bt.pivot_table(index=['model', 'cogs_method'], columns='metric', values='value', aggfunc='mean')
    vai_tro = bt.groupby(['model', 'cogs_method'])['role'].first()
    san = vai_tro[vai_tro == 'floor'].index
    if len(san) != 1 or diem.shape[1] != 3 or diem.isna().any().any() or key not in tb.index:
        dung(f'Bảng `{fq.SOURCE["forecast_backtest"]}` thiếu điểm của mốc sàn, của model chính hoặc của một fold, nên trang '
             'không so sánh ứng viên trên tập thiếu. Xem trang **Sức khỏe dữ liệu**.')
    thang_san = diem.lt(diem.loc[san[0]], axis=1).all(axis=1) & (vai_tro != 'floor')
    chinh = tb.loc[key]

    # --- Nhãn bắt buộc (hợp đồng §8) ---
    with st.container(border=True):
        st.markdown(
            f'**Đây là số dự báo, không phải số thực tế.** Chỉ tiêu: **{cat.G_LABEL}** và **COGS — giá vốn**, theo ngày, '
            f'toàn công ty. Kỳ dự báo {ngay(START)} → {ngay(END)} ({num(N_DAYS)} ngày).  \n'
            f'**Model chính:** {ten_chinh} (`{key[0]} / {key[1]}`). '
            f'{SELECTION_REASON.get(p["selection_step"], "Bước luật: " + str(p["selection_step"]) + ".")}  \n'
            f'**model_version** `{p["model_version"]}` · **trained_through** {ngay(p["trained_through"])} (số thực tế '
            f'dùng để train dừng ở ngày này) · **run_id** `{p["run_id"]}` · khoảng dự báo {pct(p["interval_level"], 0)} '
            'theo ngày; tháng không có khoảng (Q7).  \n'
            f'**Độ tin cậy:** {CAU_BACKTEST[0].upper() + CAU_BACKTEST[1:]}. Điểm của model chính là lạc quan vì được chọn '
            'từ nhiều ứng viên trên cùng 3 fold.')

    g_ky, cogs_ky = fc['yhat'].sum(), fc['cogs_yhat'].sum()
    c1, c2, c3, c4 = hang_the('the_du_bao', 4)
    kpi(c1, f'G dự báo cả kỳ ({num(N_DAYS)} ngày)', ty(g_ky, 2),
        f'Cộng G dự báo từng ngày {ngay(START)} → {ngay(END)} của model chính. Số đầy đủ: {num(g_ky, 2)}.')
    kpi(c2, 'COGS dự báo cả kỳ', ty(cogs_ky, 2), f'Cộng COGS dự báo từng ngày của model chính. Số đầy đủ: {num(cogs_ky, 2)}.')
    kpi(c3, 'COGS/G dự báo cả kỳ', num(cogs_ky / g_ky, 3), 'Tổng COGS ÷ tổng G của cả kỳ, không lấy trung bình tỷ lệ ngày.')
    kpi(c4, 'Sai số tháng điển hình', mape(chinh.get('mape_g_thang')),
        'MAPE G tháng của model chính: trung bình |G tháng dự báo − thực tế| ÷ thực tế, trên các tháng đủ ngày, trung bình '
        f'3 fold backtest. Đây là {CAU_BACKTEST}. Dùng thay cho khoảng dự báo tháng (Q7).')

    # --- Theo ngày: thực tế 2021–2022 nối với dự báo ---
    st.subheader('Theo ngày: thực tế 2021–2022 nối với dự báo')
    try:
        thuc_te = doc('actual_daily')
    except Exception as e:
        thuc_te = None
        if thieu_bang(e):    # bản B2b đầu tiên có dự báo nhưng chưa có bảng số thực tế
            st.info(f'Bản dữ liệu này chưa có bảng số thực tế theo ngày (`{fq.SOURCE["actual_daily"]}`, có từ các bản '
                    'dựng sau 15/10/2026), nên biểu đồ chỉ hiện phần dự báo.')
        else:
            st.warning(f'Không đọc được số thực tế G, COGS theo ngày (`{fq.SOURCE["actual_daily"]}`): '
                       f'{type(e).__name__}. Biểu đồ chỉ hiện phần dự báo.')


    khoang = pd.DataFrame({'ngay': fc['forecast_date'], 'lower': fc['lower'], 'upper': fc['upper'],
                           'duoi': fc['lower'].map(lambda v: trieu(v, 2)), 'tren': fc['upper'].map(lambda v: trieu(v, 2))})
    st.markdown(f'**{cat.G_LABEL}**')
    st.altair_chart(bieu_do(du_lieu(fc, thuc_te, 'g', 'yhat'), 'G', khoang), width='stretch')
    st.caption(f'Dải cam nhạt: khoảng dự báo {pct(p["interval_level"], 0)} theo ngày của model chính. Trên backtest, dải '
               f'này chứa trung bình {pct(chinh.get("coverage_80"))} số ngày thực tế (3 fold). G thực tế = `sales.csv`, '
               'cùng tập đơn với G dự báo (gồm cả đơn hủy); không phải R của trang PS1–PS5.')
    st.markdown('**COGS — giá vốn**')
    st.altair_chart(bieu_do(du_lieu(fc, thuc_te, 'cogs', 'cogs_yhat'), 'COGS'), width='stretch')
    st.caption(f'COGS dự báo của model chính ({COGS_LABEL.get(key[1], key[1])}). Kho dự báo chỉ có khoảng 80% cho G, '
               'không có cho COGS.')

    # --- Tổng tháng (hợp đồng §2.2): cộng các ngày; COGS/G = ΣCOGS / ΣG; không có khoảng tháng (Q7) ---
    st.subheader('Tổng tháng')
    fc['thang'] = fc['forecast_date'].dt.to_period('M')
    m = fc.groupby('thang').agg(g=('yhat', 'sum'), cogs=('cogs_yhat', 'sum'), n=('yhat', 'size')).reset_index()
    m['du'] = m['thang'].dt.days_in_month
    m['Tháng'] = m['thang'].dt.strftime('%m/%Y')
    m['Số ngày có dự báo'] = m['n'].astype(str) + '/' + m['du'].astype(str)
    m['Ghi chú'] = ['Tháng thiếu, không so với tháng đủ' if n < d else '' for n, d in zip(m['n'], m['du'])]
    bang = pd.DataFrame({'Tháng': m['Tháng'], 'G dự báo': m['g'].map(lambda v: trieu(v, 1)),
                         'COGS dự báo': m['cogs'].map(lambda v: trieu(v, 1)),
                         'COGS/G': (m['cogs'] / m['g']).map(lambda v: num(v, 3)),
                         'Số ngày có dự báo': m['Số ngày có dự báo'], 'Ghi chú': m['Ghi chú']})
    st.dataframe(bang, hide_index=True, height='content',
                 column_config={**{c: st.column_config.TextColumn(alignment='right', width='small')
                                   for c in ('G dự báo', 'COGS dự báo', 'COGS/G', 'Số ngày có dự báo')},
                                'Ghi chú': st.column_config.TextColumn(width='large')})
    st.caption(f'Tháng không có khoảng dự báo (Q7). Thay vào đó: **sai số tháng điển hình** của model chính là '
               f'{mape(chinh.get("mape_g_thang"))} (MAPE G tháng, trung bình 3 fold): trên backtest, G tháng dự báo lệch '
               f'trung bình chừng đó so với G tháng thực tế. Đây là {CAU_BACKTEST}.')
    with st.expander('Số đầy đủ của bảng tháng (2 chữ số thập phân)'):
        st.dataframe(pd.DataFrame({'Tháng': m['Tháng'], 'G dự báo': m['g'].map(lambda v: num(v, 2)),
                                   'COGS dự báo': m['cogs'].map(lambda v: num(v, 2)),
                                   'Số ngày có dự báo': m['Số ngày có dự báo']}),
                     hide_index=True, height='content', column_config={'G dự báo': right, 'COGS dự báo': right})

    # --- So sánh ứng viên (rpt_forecast_backtest) ---
    st.subheader('Các model đã thi: sai số backtest 2020–2022')
    ss = tb.join(vai_tro).assign(thang_san=thang_san).reset_index()
    ss = ss.sort_values('score', kind='stable')
    ss['hang_mape'] = ss['mape_g_thang'].rank(method='min').astype('Int64')
    la_chinh = (ss['model'] == key[0]) & (ss['cogs_method'] == key[1])
    so_sanh = pd.DataFrame({
        'Model': [('★ ' if c else '') + MODEL_LABEL.get(a, a) + (' (mốc sàn)' if r == 'floor' else '')
                  for a, r, c in zip(ss['model'], ss['role'], la_chinh)],
        'Cách tính COGS': ss['cogs_method'].map(lambda c: COGS_LABEL.get(c, c)),
        'Điểm ngày': ss['score'].map(lambda v: trieu(v, 3)),
        'Thắng sàn cả 3 fold': [('–' if r == 'floor' else ('Có' if t else 'Không')) for r, t in zip(ss['role'], ss['thang_san'])],
        'MAPE G tháng': ss['mape_g_thang'].map(mape),
        'Hạng MAPE': ss['hang_mape'],
    })
    st.dataframe(so_sanh, hide_index=True, height='content',
                 column_config={'Model': st.column_config.TextColumn(width='large'),
                                'Điểm ngày': right, 'MAPE G tháng': right})
    # MAPE chỉ đo G nên hai cách tính COGS của cùng model có cùng MAPE: nêu tên model, không nêu cách COGS
    ung = ss[(ss['role'] == 'candidate') & ss['mape_g_thang'].notna()]
    mape_min = ung['mape_g_thang'].min()
    tot_nhat = list(dict.fromkeys(ung.loc[ung['mape_g_thang'] == mape_min, 'model']))
    khac = ('' if ung.empty or key[0] in tot_nhat else
            f' Ở bản này, MAPE G tháng thấp nhất là của {", ".join(MODEL_LABEL.get(x, x) for x in tot_nhat)} '
            f'({mape(mape_min)}), không phải model chính: hai thước xếp hạng khác nhau.')
    st.caption(f'★ = model chính, chọn ở **{BUOC.get(p["selection_step"], p["selection_step"])}** của luật. Bảng xếp theo '
               'điểm ngày, thấp nhất ở trên. '
               '**Điểm ngày** (điểm ngày kết hợp) = (MAE G + MAE COGS) ÷ 2 theo ngày, trung bình 3 fold: đây là thước chọn '
               'model (Q1), thấp hơn là tốt hơn. Luật: (1) thắng mốc sàn seasonal naive 2 năm ở cả 3 fold, (2) điểm thấp '
               'nhất, (3) trong vòng 1% thì chọn ứng viên đơn giản hơn. MAPE G tháng chỉ để tham khảo, không dùng để chọn.'
               + khac)
    with st.expander('Điểm ngày kết hợp từng fold'):
        goc = list(diem.columns)
        tung = diem.loc[ss.set_index(['model', 'cogs_method']).index].reset_index()
        st.dataframe(pd.DataFrame({'Model': so_sanh['Model'].values, 'Cách tính COGS': so_sanh['Cách tính COGS'].values,
                                   **{f'F{i + 1} (train tới {ngay(o)})': tung[o].map(lambda v: trieu(v, 3)).values
                                      for i, o in enumerate(goc)}}),
                     hide_index=True, height='content')
        st.caption('Mỗi fold dự báo 548 ngày ngay sau ngày train cuối, như bài thật. "Thắng mốc sàn" = điểm thấp hơn mốc sàn '
                   'ở cả 3 cột.')

    notes(
        [f'Đường xám là số thực tế 2021–2022, đường cam là dự báo của model chính từ {ngay(START)}. Dải cam nhạt quanh G '
         'là khoảng 80% theo ngày.',
         'Bảng tháng cộng các ngày của cùng model chính; COGS/G tháng = tổng COGS ÷ tổng G của tháng. Tháng 07/2024 chỉ có '
         'ngày 01/07 nên không so với tháng đủ.',
         'Model chính do luật chọn chạy trong pipeline quyết, không phải người chọn tay hay AI chọn. Bảng so sánh cho thấy '
         'mọi model đã thi, cả thước chọn (điểm ngày) và thước tham khảo (MAPE G tháng).'],
        ['Đây là dự báo, không phải số thực tế. G dự báo là doanh thu gộp, gồm cả đơn hủy: không so với R (doanh thu đơn '
         'đã giao) của trang PS1–PS5.',
         f'{BACKTEST_NOTE}',
         'Model chỉ dùng biến suy từ lịch (tháng, ngày trong tháng, năm chẵn/lẻ, đợt khuyến mãi lặp lại...), vì mọi bảng '
         'phụ dừng ở 31/12/2022. Biến động ngoài lịch (giá, tồn kho, kênh mới) không có trong dự báo.',
         'Khoảng 80%: mức do PM chốt (Q6); cách tính (quantile phần dư log trên backtest) là đề xuất của dev.',
         'Dự báo chỉ có trong bản dữ liệu do pipeline dựng (chế độ versioned, DuckDB trên máy). App public chưa có: chờ PM '
         'quyết đường đưa lên.'])


page_header('Dự báo G và COGS', f'G và COGS mỗi ngày từ {ngay(START)} đến {ngay(END)} dự báo là bao nhiêu, '
            'và tin được tới đâu?')
# Kho dự báo chỉ có trong bản dữ liệu của pipeline từ B2b
try:
    fc, bt = doc('forecast_daily'), doc('forecast_backtest')
except Exception as e:
    chua_co_du_bao(backend(), e)
else:
    hien_du_bao(fc, bt)
