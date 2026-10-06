import pandas as pd
import streamlit as st

from ui.common import BACKEND_LABEL, LOCAL_TZ, backend, kpi, load_or_stop, notes, page_header
from ui.fmt import num

page_header('Sức khỏe dữ liệu', 'Số trên app có đáng tin không: lần nạp gần nhất, số dòng, kết quả test?')

LOADER = {'postgres': 'ingest_raw.py', 'databricks': 'ingest_databricks.py'}   # script nạp của từng kho có log nạp

s = load_or_stop('health_summary').iloc[0]
tests = load_or_stop('health_test', allow_empty=True)
ingest = load_or_stop('health_ingest', allow_empty=True)
runs = load_or_stop('health_run', allow_empty=True)


def gio(ts, fmt='%H:%M %d/%m/%Y') -> str:
    """Giờ UTC trong kho → giờ Việt Nam."""
    if pd.isna(ts):
        return '–'
    return pd.Timestamp(ts).tz_localize('UTC').tz_convert(LOCAL_TZ).strftime(fmt)


# --- Trạng thái chung: rpt_health_summary.status_code, app chỉ đổi mã sang câu ---
lan_kiem = gio(s['tests_started_at_utc'])
dung_kho = gio(s['built_at_utc'])
lenh = f'`dbt {s["test_command"]}`'
if s['status_code'] == 'tot':
    st.success(f'**Kho đạt:** {num(s["n_tests_pass"])}/{num(s["n_tests_run"])} test đạt ở lần kiểm lúc {lan_kiem} '
               f'({lenh}), đúng bản kho app đang đọc.')
elif s['status_code'] == 'loi_test':
    st.error(f'**{num(s["n_tests_not_pass"])} test không đạt** ở lần kiểm lúc {lan_kiem} ({lenh}). '
             'Số trên app có thể sai ở phần các test đó kiểm; xem danh sách bên dưới (lỗi xếp lên đầu).')
elif s['status_code'] == 'loi_build':
    st.error(f'**Lần chạy lúc {lan_kiem} ({lenh}) có bước lỗi:** {num(s["n_models_not_ok"])} model dựng lỗi, '
             f'{num(s["n_tests_skipped"])} test bị bỏ qua. Số trên app có thể chưa được dựng lại hoặc chưa được kiểm.')
elif s['status_code'] == 'kiem_cu':
    st.warning(f'**Kết quả test có thể đã cũ:** kho được dựng lại lúc {dung_kho}, sau lần kiểm cuối ({lan_kiem}). '
               'Chạy `dbt build` (hoặc `dbt test`) rồi bấm **Đọc lại dữ liệu**.')
elif s['status_code'] == 'kiem_thieu':
    st.warning(f'**Lần kiểm gần nhất chỉ chạy một phần:** {num(s["n_tests_run"])}/{num(s["n_tests_in_project"])} test '
               f'({lenh}, lúc {lan_kiem}). Muốn kiểm đủ thì chạy `dbt build`.')
elif s['status_code'] == 'nguon_moi_hon':
    st.warning(f'**Nguồn mới hơn kho:** nguồn được nạp lại lúc {gio(s["last_ingest_at_utc"])}, sau lần dựng kho '
               f'({dung_kho}). Số trên app chưa theo nguồn mới; chạy `dbt build`.')
else:  # chua_kiem
    st.warning('**Chưa có kết quả test trên kho này.** Kho được dựng trước khi có nhật ký test (M5). Chạy `dbt build` '
               'rồi bấm **Đọc lại dữ liệu**.')

c1, c2, c3, c4 = st.columns(4)
if pd.notna(s['test_invocation_id']):
    kpi(c1, 'Test đạt', f'{num(s["n_tests_pass"])}/{num(s["n_tests_run"])}',
        f'Lần kiểm gần nhất: {lenh}, lúc {lan_kiem}. Dự án có {num(s["n_tests_in_project"])} test.')
    kpi(c2, 'Test không đạt', num(s['n_tests_not_pass']),
        f'Không đạt {num(s["n_tests_fail"])}, lỗi chạy {num(s["n_tests_error"])}, cảnh báo {num(s["n_tests_warn"])}, '
        f'bỏ qua {num(s["n_tests_skipped"])}.')
    kpi(c3, 'Kiểm lúc', gio(s['tests_started_at_utc'], '%H:%M %d/%m'), f'{lan_kiem}, giờ Việt Nam.')
kpi(c4, 'Dữ liệu tới ngày', s['data_end_date'].strftime('%d/%m/%Y'),
    'Đơn cuối cùng trong nguồn. Đây là bản chụp lịch sử, không cập nhật theo thời gian thực.')

# --- 1. Kết quả test ---
st.subheader('1. Kết quả test của lần kiểm gần nhất')
KET_QUA = {'pass': 'Đạt', 'fail': 'Không đạt', 'error': 'Lỗi chạy', 'warn': 'Cảnh báo', 'skipped': 'Bỏ qua'}
LOAI = {'unique': 'Không trùng', 'not_null': 'Không rỗng', 'relationships': 'Khóa ngoại có thật',
        'accepted_values': 'Giá trị hợp lệ'}


def ket_qua(r) -> str:
    kq = KET_QUA.get(r['status'], r['status'])
    return f'{kq} ({num(r["failures"])} dòng lệch)' if r['status'] == 'fail' and pd.notna(r['failures']) else kq


def to_mau(col: pd.Series) -> list[str]:
    return ['' if v == 'Đạt' else 'color: #c0392b; font-weight: 600' for v in col]


if tests.empty:
    st.info('Chưa có kết quả test để hiện.')
else:
    st.caption(f'Lần kiểm: {lenh}, từ {lan_kiem} tới {gio(s["tests_finished_at_utc"], "%H:%M")}. '
               f'Gồm {num(s["n_singular_run"])} test nghiệp vụ và {num(s["n_generic_run"])} test ràng buộc cột.')
    nv = tests[tests['test_group'] == 'nghiep_vu']
    st.markdown(f'**Test nghiệp vụ ({num(s["n_singular_run"])})**: tính lại số theo đường độc lập rồi so, '
                'hoặc khóa các con số đã chốt (deck, nhật ký nghiệm thu).')
    bang = pd.DataFrame({'Test': nv['test_name'], 'Kết quả': nv.apply(ket_qua, axis=1),
                         'Kiểm gì': nv['description'].fillna('–'), 'Tầng': nv['layer']}).set_index('Test')
    st.table(bang.style.apply(to_mau, subset=['Kết quả']))   # st.table: mô tả dài tự xuống dòng, không bị cắt
    rb = tests[tests['test_group'] == 'rang_buoc']
    with st.expander(f'Test ràng buộc cột ({num(s["n_generic_run"])}): khóa không trùng, không rỗng, '
                     'khóa ngoại có thật, giá trị hợp lệ', expanded=bool((rb['status'] != 'pass').any())):
        bang = pd.DataFrame({'Kết quả': rb.apply(ket_qua, axis=1), 'Bảng': rb['tested_model'],
                             'Cột': rb['column_name'].fillna('–'), 'Loại kiểm': rb['test_kind'].map(LOAI).fillna(rb['test_kind']),
                             'Tầng': rb['layer']})
        st.dataframe(bang.style.apply(to_mau, subset=['Kết quả']), hide_index=True)
    loi = tests[tests['status'] != 'pass']
    if not loi.empty:
        st.markdown('**Chi tiết test không đạt**')
        st.dataframe(pd.DataFrame({'Test': loi['test_name'], 'Kết quả': loi.apply(ket_qua, axis=1),
                                   'Thông báo của dbt': loi['message'].fillna('–')}), hide_index=True)

# --- 2. Nguồn dữ liệu ---
st.subheader('2. Nguồn dữ liệu: lần nạp gần nhất')
if s['ingest_mode'] == 'doc_csv':
    st.info('Kho DuckDB **không có bước nạp riêng**: mỗi lần `dbt build`, dbt đọc thẳng 14 file `data/*.csv`, nên '
            'không có log nạp. Số dòng từ nguồn sang kho vẫn được kiểm bằng test `assert_every_source_row_lands` '
            'và `assert_row_counts` ở mục 1. Muốn xem log nạp thì chọn **PostgreSQL** ở thanh bên.')
elif ingest.empty:
    st.warning(f'Chưa có log nạp nguồn trên {BACKEND_LABEL[backend()]}. Chạy `scripts/ingest/{LOADER[backend()]}` '
               'rồi `dbt build`.')
else:
    st.caption(f'Nạp lúc {gio(s["last_ingest_at_utc"])} bằng `scripts/ingest/{LOADER[backend()]}`, '
               f'{num(s["n_sources_ingested"])} file. '
               + ('Cả lần nạp là một giao dịch: file nào sai số dòng so với quy định thì hủy cả lần nạp'
                  if backend() == 'postgres' else
                  'Log chỉ được ghi khi **mọi** file đúng số dòng quy định, file nào sai thì cả lần nạp không vào log')
               + ', nên lần nạp có trong log là lần đã qua kiểm số dòng. '
               'Test `assert_rpt_health` đối chiếu số dòng dưới đây với bảng `raw` thật.')
    right = st.column_config.TextColumn(alignment='right')
    st.dataframe(pd.DataFrame({'File nguồn': ingest['source'] + '.csv', 'Số dòng': ingest['row_count'].map(num),
                               'Thời gian nạp (giây)': ingest['seconds'].map(lambda x: num(x, 2)),
                               'Mã MD5 của file': ingest['file_md5']}),
                 hide_index=True, height='content', column_config={'Số dòng': right, 'Thời gian nạp (giây)': right})

# --- 3. Lịch sử ---
st.subheader('3. Các lần chạy dbt gần đây trên kho này')
if runs.empty:
    st.info('Chưa có lần chạy nào được ghi.')
else:
    st.dataframe(pd.DataFrame({
        'Lúc': runs['started_at_utc'].map(gio), 'Lệnh': 'dbt ' + runs['command'],
        'Test đạt': [f'{num(p)}/{num(n)}' if n else '–' for p, n in zip(runs['n_tests_pass'], runs['n_tests_run'])],
        'Test không đạt': runs['n_tests_not_pass'].map(num),
        'Model, seed dựng': runs['n_models_run'].map(num), 'Model lỗi': runs['n_models_not_ok'].map(num),
    }), hide_index=True, height='content')
    st.caption('Tối đa 10 lần gần nhất, mới nhất ở trên. Nhật ký bắt đầu từ M5 (2026-09-29).')

notes(
    cach_doc=[
        'Nhật ký test nằm **trong chính kho đang đọc**: chọn PostgreSQL thì thấy kết quả của lần build Postgres, chọn '
        'DuckDB thì thấy của DuckDB, chọn Databricks thì thấy của Databricks. Mỗi lần dbt chạy xong tự ghi thêm '
        '(schema `ops`).',
        '**Kho đạt** khi lần kiểm gần nhất chạy đủ mọi test, tất cả đạt, và chạy từ lúc dựng kho trở về sau. Kho dựng lại '
        'mà chưa kiểm, hoặc chỉ kiểm một phần, thì trang báo vàng.',
        'Test nghiệp vụ là phần quan trọng: ví dụ doanh thu theo ngày khớp `sales.csv` cả 3.833 ngày, số của app đối soát '
        'với nguồn độc lập từng tháng, các số trong deck được khóa. Test ràng buộc bắt lỗi dựng bảng (trùng khóa, thiếu '
        'giá trị).',
    ],
    gioi_han=[
        'Test chứng minh kho **khớp nguồn CSV** và **đúng công thức**; không chứng minh bản thân CSV đúng với thực tế '
        '(dữ liệu mô phỏng của đề).',
        'Dữ liệu là bản chụp lịch sử tới ngày trong thẻ "Dữ liệu tới ngày", không cập nhật theo thời gian thực. '
        '"Lần nạp" là lúc nạp file vào kho, không phải lúc phát sinh giao dịch.',
        'Lần dbt đang chạy chỉ hiện ở đây sau khi chạy xong. Trên PostgreSQL, trong lúc dựng lại, trang có thể báo '
        'không đọc được bảng; chờ build xong rồi bấm **Đọc lại dữ liệu**.',
    ],
)
