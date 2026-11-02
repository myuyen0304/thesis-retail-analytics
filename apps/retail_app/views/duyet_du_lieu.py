"""DE duyệt và chạy; chỉ Admin được công bố vào registry local của tính năng."""
import pandas as pd
import streamlit as st
import yaml

from ui import roles, nhap_runner
from ui.nhap_store import RequestStore, LABELS
from scripts.ingest import approval
from scripts.ingest.source_contract import SOURCES

if not roles.allowed(roles.current_role(), 'duyet_du_lieu'):
    st.error('Bạn không có quyền xem trang này.')
    st.stop()
st.title('Duyệt dữ liệu')
st.caption('Chỉ chạy DuckDB local. Công bố tại đây cập nhật kho nhập dữ liệu; kho báo cáo của app giữ cấu hình hiện tại.')
st.info('Hiện chỉ orders_enriched có model dbt. Phần mở rộng khác dừng ở “Chờ model dbt” sau khi duyệt.')
store = RequestStore()


@st.fragment(run_every='5s')
def running_status(request_id):
    nhap_runner.busy_reason(store)
    record = store.read(request_id)
    if record['trang_thai'] != 'dang_chay':
        st.rerun(scope='app')
    st.info(f"Đang chạy {record.get('stage', 'prepare')} · {nhap_runner.elapsed(record)} giây. Có thể tải lại trang.")
    log = store.folder(request_id) / 'chay' / f"{record['run_id']}.log"
    if log.exists():
        with st.expander('Log lượt chạy (4 KB cuối)'):
            with log.open('rb') as stream:
                stream.seek(max(0, log.stat().st_size - 4096))
                st.code(stream.read().decode('utf-8', errors='replace'), language=None)


def review():
    if not roles.allowed(roles.current_role(), 'duyet_du_lieu'):
        return
    user = roles.logged_in_user()
    if not user:
        st.info('Cần đăng nhập để duyệt dữ liệu.')
        return
    rows = store.visible(user['username'], roles.current_role())
    if not rows:
        st.info('Chưa có yêu cầu.')
        return
    selected = st.selectbox('Yêu cầu', [r['id'] for r in rows],
        format_func=lambda key: next(f"{r['ten_file']} · {r['nguoi_gui']} · {LABELS[r['trang_thai']]}" for r in rows if r['id'] == key))
    record = store.read(selected)
    st.text(record['mo_ta'])
    st.caption('Trạng thái: ' + LABELS[record['trang_thai']])
    if record.get('loi_ky_thuat'):
        st.error(record['loi_ky_thuat'])
    proposal = None
    if (store.folder(selected) / 'de_xuat/mapping_de_xuat.yml').exists():
        proposal = store.proposal(selected)
        conflict = proposal.get('xung_dot_khoa', {})
        if conflict.get('danh_lai_khoa', 0) or conflict.get('id_trung_khac_noi_dung', 0):
            st.error('Xung đột khóa: cần quyết định của người duyệt trước khi sử dụng dữ liệu.')
        with st.expander('Báo cáo kỹ thuật đầy đủ'):
            st.markdown((store.folder(selected) / 'de_xuat/bao_cao_mapping.md').read_text(encoding='utf-8'))
            st.json(proposal)
    if record['trang_thai'] == 'cho_duyet' and proposal:
        defaults = approval.default_decisions(proposal)
        with st.form('duyet_' + selected):
            name = st.text_input('Tên phần mở rộng', approval.extension_name(record['ten_file']))
            st.caption('PII mặc định chỉ ở silver. Chọn mart là quyết định chủ động cho phép xuất hiện trên báo cáo.')
            frame = pd.DataFrame(defaults['cot'])
            for col, value in [('kieu', 'string'), ('duoc_rong', False), ('hien_thi', 'silver'), ('ly_do', '')]:
                if col not in frame:
                    frame[col] = value
                frame[col] = frame[col].fillna(value)
            edited = st.data_editor(frame, disabled=['ten'], hide_index=True, key='cot_' + selected,
                column_config={'xu_ly': st.column_config.SelectboxColumn('Xử lý', options=['khoa_noi', 'doi_chieu_loi', 'bo', 'nap'], required=True),
                               'kieu': st.column_config.TextColumn('Kiểu'),
                               'duoc_rong': st.column_config.CheckboxColumn('Được rỗng'),
                               'hien_thi': st.column_config.SelectboxColumn('Hiển thị', options=['silver', 'mart']),
                               'ly_do': st.column_config.TextColumn('Lý do')})
            source = st.selectbox('Nguồn nối', list(SOURCES), index=list(SOURCES).index(defaults['khoa_noi']['nguon']) if defaults['khoa_noi']['nguon'] in SOURCES else 0)
            source_key = st.text_input('Cột khóa trong nguồn', defaults['khoa_noi']['cot_nguon'])
            entities = st.text_area('Thực thể đã duyệt (YAML; [] nếu không duyệt thực thể)',
                yaml.safe_dump(defaults['thuc_the'], allow_unicode=True, sort_keys=False), height=180)
            tolerance = st.number_input('Ngưỡng cách ly (tỷ lệ)', min_value=0.0, max_value=0.99, value=0.01, step=0.01)
            approve = st.form_submit_button('Duyệt', type='primary')
        if approve:
            try:
                cols = []
                for row in edited.to_dict('records'):
                    fields = ['ten', 'xu_ly']
                    if row['xu_ly'] in ('nap', 'khoa_noi'):
                        fields += ['kieu', 'duoc_rong']
                    if row['xu_ly'] == 'nap':
                        fields += ['hien_thi']
                    if row['xu_ly'] == 'bo':
                        fields += ['ly_do']
                    cols.append({k: row[k] for k in fields})
                decisions = {'cot': cols, 'thuc_the': yaml.safe_load(entities), 'nguong_cach_ly': tolerance,
                             'khoa_noi': {'nguon': source, 'cot_nguon': source_key,
                                'cot': next((r['ten'] for r in cols if r['xu_ly'] == 'khoa_noi'), '')}}
                store.approve(selected, record['revision'], decisions, name)
                st.rerun()
            except Exception as error:
                st.error(str(error))
        with st.form('tu_choi_' + selected):
            reason = st.text_area('Lý do từ chối (bắt buộc)')
            reject = st.form_submit_button('Từ chối')
        if reject:
            try:
                store.reject(selected, record['revision'], reason)
                st.rerun()
            except Exception as error:
                st.error(str(error))
    state = record['trang_thai']
    if state == 'cho_model_dbt':
        st.warning('Đã duyệt và land; cần DE viết model dbt trước khi chạy.')
        st.button('Chạy', disabled=True)
    if state in ('da_duyet', 'loi', 'da_cong_bo', 'da_kiem'):
        reason = nhap_runner.busy_reason(store)
        if reason:
            st.info(reason)
        try:
            if state != 'da_kiem' and st.button('Chạy lại để kiểm' if state == 'da_cong_bo' else 'Chạy', disabled=bool(reason)):
                nhap_runner.start(store, selected, record['revision'])
                st.rerun()
            if state == 'da_kiem' and roles.current_role() == 'admin' and st.button('Công bố', disabled=bool(reason), type='primary'):
                with st.spinner('Đang công bố…'):
                    nhap_runner.publish(store, selected, record['revision'])
                st.rerun()
        except Exception as error:
            st.error(str(error))
    if state == 'dang_chay':
        running_status(selected)
    if record.get('thong_bao'):
        st.text(record['thong_bao'])
    if state in ('da_kiem', 'da_cong_bo'):
        try:
            st.json(nhap_runner.summary(store, record))
        except Exception as error:
            st.warning('Chưa đọc được tóm tắt lượt chạy: ' + str(error))
    if record.get('run_id') and state != 'dang_chay':
        log = store.folder(selected) / 'chay' / f"{record['run_id']}.log"
        if log.exists():
            with st.expander('Log lượt chạy (4 KB cuối)'):
                with log.open('rb') as stream:
                    stream.seek(max(0, log.stat().st_size - 4096))
                    st.code(stream.read().decode('utf-8', errors='replace'), language=None)
    with st.expander('Lịch sử yêu cầu'):
        st.json(record['lich_su'])


review()
