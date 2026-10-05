"""Phần dùng chung giữa các trang: chọn backend, đọc có cache, dải thông tin chung, thẻ KPI, ghi chú."""
import datetime as dt
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from dwh import queries
from dwh.connection import BACKENDS, default_backend, describe
from ui.fmt import num, pct, ty

BACKEND_LABEL = {'postgres': 'PostgreSQL (Docker)', 'duckdb': 'DuckDB (file, dự phòng)',
                 'databricks': 'Databricks (cloud, lab)'}
LOCAL_TZ = ZoneInfo('Asia/Ho_Chi_Minh')


def backend() -> str:
    """Backend đang chọn ở thanh bên. Mặc định lấy từ biến môi trường RETAIL_BACKEND."""
    if 'backend' not in st.session_state:
        st.session_state.backend = default_backend()
    return st.session_state.backend


def sidebar() -> None:
    backend()
    st.session_state._reads = {}          # bảng đã đọc trong lượt chạy này (report_reads liệt kê lại)
    st.sidebar.radio('Nguồn dữ liệu', BACKENDS, key='backend', format_func=BACKEND_LABEL.get)
    if st.sidebar.button('Đọc lại dữ liệu'):
        st.cache_data.clear()
        st.session_state.reloaded = True   # report_reads sẽ báo thành công sau khi trang đọc xong


@st.cache_data(ttl=600, show_spinner=False)
def load(query_name: str, backend_name: str) -> tuple[pd.DataFrame, dt.datetime]:
    # backend_name là tham số tường minh → cache tách riêng từng backend.
    # Trả kèm thời điểm truy vấn DB thật (không phải lúc lấy từ cache).
    return getattr(queries, query_name)(backend_name), dt.datetime.now()


def load_or_stop(query_name: str, allow_empty: bool = False) -> pd.DataFrame:
    """Đọc 1 bảng; lỗi kết nối hoặc bảng rỗng thì báo cách xử lý rồi dừng trang (không vẽ số sai hay văng lỗi).
    allow_empty=True cho bảng được phép rỗng (vd. log nạp trên DuckDB), trang tự xử lý."""
    b = backend()
    try:
        df, read_at = load(query_name, b)
    except Exception as e:  # lỗi kết nối: báo rõ để người demo chuyển backend
        st.session_state.pop('reloaded', None)
        st.error(f'Không đọc được `{query_name}` từ {BACKEND_LABEL[b]}: {type(e).__name__}.')
        if b == 'postgres':
            st.info('Docker/Postgres có thể chưa chạy. Chọn **DuckDB** ở thanh bên để tiếp tục.')
        elif b == 'databricks':
            st.info('Chưa đăng nhập hoặc phiên đăng nhập Databricks đã hết hạn: chạy '
                    '`databricks auth login --profile retail-dev` rồi bấm **Đọc lại dữ liệu**. Cần điền '
                    '`.env.databricks.local` (profile, warehouse). Chọn **DuckDB** ở thanh bên để tiếp tục.')
        else:
            st.info('Chưa có `warehouse/dbt.duckdb`, hoặc `dbt build --target duckdb` đang ghi file '
                    '(DuckDB khóa file khi ghi). Đợi build xong rồi bấm **Đọc lại dữ liệu**.')
        st.stop()
    st.session_state.setdefault('_reads', {})[query_name] = (len(df), read_at)
    if df.empty and not allow_empty:
        st.session_state.pop('reloaded', None)
        st.warning(f'Bảng `{queries.SOURCE[query_name]}` trên {BACKEND_LABEL[b]} không có dòng nào, nên trang không có số '
                   'để hiện. Kho có thể đang dựng dở: chạy xong `dbt build` rồi bấm **Đọc lại dữ liệu**.')
        st.stop()
    return df


def _stop_lech(query_name: str, what: str) -> None:
    st.session_state.pop('reloaded', None)
    st.warning(f'Bảng `{queries.SOURCE[query_name]}` trên {BACKEND_LABEL[backend()]} **thiếu dòng** {what}, nên trang '
               'không hiện tiếp. Các bảng reporting đang lệch nhau (thường do `dbt build` chạy dở hoặc chỉ dựng một phần). '
               'Xem trang **Sức khỏe dữ liệu**, chạy `dbt build` đầy đủ rồi bấm **Đọc lại dữ liệu**.')
    st.stop()


def need(df: pd.DataFrame, query_name: str, what: str) -> pd.DataFrame:
    """Phần đã lọc của bảng query_name mà trang cần có ít nhất 1 dòng. Rỗng (bảng lệch nhau) → cảnh báo rồi dừng trang,
    không để .iloc[0] văng lỗi. Bình thường dbt giữ các bảng khớp nhau (test assert_rpt_*), nên chỗ này không hiện."""
    if df.empty:
        _stop_lech(query_name, what)
    return df


def pick(df: pd.DataFrame, key, query_name: str, what: str) -> pd.Series:
    """Một dòng theo nhãn index. Không có dòng đó (bảng lệch nhau) → cảnh báo rồi dừng trang."""
    if key not in df.index:
        _stop_lech(query_name, what)
    return df.loc[key]


def need_keys(keys, df: pd.DataFrame, query_name: str, what: str) -> None:
    """Mọi khóa trong keys phải có trong index của df (vd. năm của bảng này phải có ở bảng kia)."""
    thieu = [k for k in dict.fromkeys(keys) if k not in df.index]
    if thieu:
        _stop_lech(query_name, f'{what} ({", ".join(map(str, thieu[:5]))})')


def report_reads(top) -> None:
    """Gọi sau khi trang chạy xong (app.py). Bấm "Đọc lại" → thông báo thành công ở đầu trang; không bấm → dòng nguồn ở cuối."""
    reads = st.session_state.get('_reads', {})
    if not reads:
        return
    b = backend()
    tables = ', '.join(f'`{queries.SOURCE[q]}` ({num(n)} dòng)' for q, (n, _) in reads.items())
    times = [t for _, t in reads.values()]
    if st.session_state.pop('reloaded', False):
        when = max(times).strftime('%H:%M:%S %d/%m/%Y')
        top.success(f'Đã đọc lại dữ liệu thành công từ **{describe(b)}**, lúc {when}: {tables}.')
        st.toast(f'Đọc từ {BACKEND_LABEL[b]} thành công', icon='✅')
    else:
        when = min(times).strftime('%H:%M:%S %d/%m/%Y')
        st.divider()
        st.caption(f'Nguồn: {tables} trên **{describe(b)}**. '
                   f'Truy vấn DB lúc {when} (giữ trong bộ nhớ đệm 10 phút; bấm **Đọc lại dữ liệu** để lấy mới).')


def _d(x) -> str:
    return x.strftime('%d/%m/%Y')


def info_strip() -> None:
    """Dải thông tin chung ở đầu mọi trang (docs/gd2_app_plan.md §3, tiêu chí 3). Mọi mốc thời gian đọc từ rpt_build_info."""
    i = load_or_stop('build_info').iloc[0]
    built = i['built_at_utc'].tz_localize('UTC').tz_convert(LOCAL_TZ)
    first_year = i['data_start_date'].year
    ref = (f'; năm {first_year} chưa đủ năm (từ {_d(i["data_start_date"])}), chỉ để tham khảo'
           if first_year < i['analysis_start_year'] else '')
    with st.container(border=True):
        st.markdown(
            f'**Kỳ phân tích:** {i["analysis_start_year"]}–{i["analysis_end_year"]}{ref}; '
            f'tăng trưởng năm tính từ {i["growth_start_year"]}.  \n'
            '**R** = tiền thực nhận: chỉ đơn đã giao, đã trừ chiết khấu. '
            '**G** = tiền hàng của mọi đơn (kể cả hủy, trả, chưa giao), chưa trừ chiết khấu; G chính là `sales.csv`. '
            'Mọi số gom theo ngày đặt hàng.  \n'
            f'**Trạng thái snapshot:** trạng thái đơn lúc trích dữ liệu (đơn cuối cùng ngày {_d(i["data_end_date"])}), '
            'không phải sổ kế toán từng thời điểm.  \n'
            f'**Refresh:** DWH dựng lại (`dbt build`) lúc {built.strftime("%H:%M %d/%m/%Y")}; '
            f'app đang đọc từ **{describe(backend())}**.'
        )


def page_header(title: str, question: str) -> None:
    st.title(title)
    st.markdown(f'**Câu hỏi:** {question}')
    info_strip()


def kpi(col, label: str, value: str, help: str | None = None,
        delta: str | None = None, delta_sign: float | None = None, delta_desc: str | None = None) -> None:
    """Thẻ KPI. delta: dòng nhỏ dưới số lớn. Màu lấy từ delta_sign (số thật), vì Streamlit chỉ nhận '-' ASCII là âm
    mà num() in dấu '−' (U+2212): để Streamlit tự đoán thì số âm sẽ tô xanh."""
    if delta is None:
        col.metric(label, value, help=help, border=True, delta_description=delta_desc)
        return
    color = 'off' if delta_sign is None or pd.isna(delta_sign) or delta_sign == 0 else ('green' if delta_sign > 0 else 'red')
    col.metric(label, value, delta, delta_color=color, delta_arrow='off', delta_description=delta_desc,
               help=help, border=True)


def hang_the(key: str, n: int) -> list:
    """Hàng n thẻ KPI đều nhau (feedback PM 2026-10-02). Streamlit không có tùy chọn này nên dùng CSS, chỉ áp trong
    st.container(key=key) (class st-key-<key>):
    - mọi thẻ cùng khuôn: nhãn / số lớn / ô màu / dòng xám, mỗi phần một dòng (dòng xám không lúc nằm cạnh ô màu, lúc bị
      đẩy xuống tùy độ dài chữ);
    - các thẻ cao bằng thẻ cao nhất;
    - cỡ chữ số lớn = 11% bề rộng thẻ (container query), tối đa bằng cỡ mặc định, nên thẻ hẹp vẫn không cắt số;
    - dòng xám dài thì xuống dòng thay vì bị cắt "…"."""
    k = f'.st-key-{key}'
    css = (f'{k} [data-testid="stHorizontalBlock"] {{align-items: stretch;}}'
           f'{k} [data-testid="stColumn"] > [data-testid="stVerticalBlock"], '
           f'{k} [data-testid="stElementContainer"]:has([data-testid="stMetric"]) {{height: 100%;}}'
           f'{k} [data-testid="stMetric"] {{height: 100%; box-sizing: border-box; container-type: inline-size;}}'
           f'{k} [data-testid="stMetricValue"] {{font-size: clamp(1.1rem, 11cqi, 2.25rem);}}'
           f'{k} div:has(> [data-testid="stMetricDeltaDescription"]) '
           '{flex-direction: column; align-items: flex-start; gap: 0.3rem;}'
           f'{k} [data-testid="stMetricDeltaDescription"], {k} [data-testid="stMetricDeltaDescription"] * '
           '{white-space: normal; overflow: visible; text-overflow: clip; margin-left: 0;}')
    st.html(f'<style>{css}</style>')
    return st.container(key=key).columns(n)


def kpi_revenue(row: pd.Series) -> None:
    """3 thẻ G, R, R/G của một dòng rpt_revenue_total / rpt_revenue_yearly.
    Feedback PM 2026-10-02: thẻ ghi gọn theo tỷ (2 số lẻ); số đầy đủ 2 chữ số thập phân để trong tooltip (?) để đối chiếu."""
    c1, c2, c3 = st.columns(3)
    kpi(c1, 'G: tiền hàng mọi đơn', ty(row['g'], 2),
        f'Mọi đơn, chưa trừ chiết khấu (= sales.csv). Số đầy đủ: {num(row["g"], 2)}.')
    kpi(c2, 'R: tiền thực nhận', ty(row['r'], 2), f'Chỉ đơn đã giao, đã trừ chiết khấu. Số đầy đủ: {num(row["r"], 2)}.')
    kpi(c3, 'Tỷ lệ thực nhận R/G', pct(row['capture_rate'], 1), 'Càng gần 100% càng ít thất thoát.')


def notes(cach_doc: list[str], gioi_han: list[str]) -> None:
    st.subheader('Cách đọc')
    st.markdown('\n'.join(f'- {x}' for x in cach_doc))
    st.subheader('Giới hạn')
    st.markdown('\n'.join(f'- {x}' for x in gioi_han))


# Giới hạn chung, lấy từ deck slide 15 (Phạm vi và giới hạn)
GIOI_HAN_CHUNG = [
    'Số theo trạng thái đơn lúc trích dữ liệu, không phải sổ sách kế toán từng thời điểm.',
    'Bỏ hẳn đơn returned khỏi R, kể cả đơn chỉ trả lại một phần hàng.',
    'Chưa rõ đơn vị tiền tệ. Chỉ nói về doanh thu, chưa đánh giá lợi nhuận hay sức khỏe tài chính.',
    'Chưa có chỉ tiêu kế hoạch nên chỉ so với năm trước. Các mối liên hệ chưa phải là nguyên nhân.',
]


def period_label(code: str, period_type: str, is_analysis: bool) -> str:
    """Nhãn kỳ cho người xem. Chỉ ghép chữ từ các cột của rpt_revenue_bridge."""
    text = code.replace('-', '–')
    if period_type == 'total':
        return f'{text} (kỳ phân tích)' if is_analysis else f'{text} (toàn bộ dữ liệu)'
    return text if is_analysis else f'{text} (chưa đủ năm, tham khảo)'


def under_construction(milestone: str) -> None:
    st.info(f'Trang này làm ở mốc **{milestone}** (docs/gd2_app_plan.md §6).')
