"""Gửi file và theo dõi yêu cầu; Quản lý chỉ thấy tóm tắt nghiệp vụ."""
import streamlit as st

from ui import roles, nhap_runner
from ui.nhap_store import RequestStore, LABELS
from scripts.ingest.approval import tom_tat_nghiep_vu

if not roles.allowed(roles.current_role(), 'gui_du_lieu'):
    st.error('Bạn không có quyền xem trang này.')
    st.stop()

st.title('Gửi dữ liệu')
st.caption('Nhập dữ liệu vào kho local. Mỗi yêu cầu nhận một file CSV hoặc JSON, tối đa 200 MB.')
user = roles.logged_in_user()
if not user:
    st.info('Đăng nhập để gửi và theo dõi dữ liệu.')
    st.stop()
store = RequestStore()
with st.form('gui_du_lieu', clear_on_submit=True):
    upload = st.file_uploader('File dữ liệu', type=['csv', 'json'], accept_multiple_files=False, max_upload_size=200)
    description = st.text_area('Mô tả dữ liệu', max_chars=2000)
    submitted = st.form_submit_button('Gửi dữ liệu', type='primary')
if submitted:
    if upload is None:
        st.error('Chọn một file trước khi gửi.')
    else:
        try:
            with st.spinner('Đang đọc và hiểu file…'):
                record = store.submit(upload, description)
            st.success(f"Đã nhận yêu cầu {record['id']}.")
        except Exception as error:
            st.error(str(error))


@st.fragment(run_every='5s')
def running_request(request_id):
    nhap_runner.busy_reason(store)
    row = store.read(request_id)
    if row['trang_thai'] != 'dang_chay':
        st.rerun(scope='app')
    st.info('Đang chạy ' + row.get('stage', 'prepare') + '. Có thể tải lại trang.')


def requests():
    role = roles.current_role()
    if not roles.allowed(role, 'gui_du_lieu'):
        return
    current = roles.logged_in_user()
    if not current:
        return
    rows = store.visible(current['username'], role)
    st.subheader('Yêu cầu đã gửi')
    if not rows:
        st.info('Chưa có yêu cầu.')
    for row in rows:
        with st.expander(f"{row['ten_file']} · {LABELS[row['trang_thai']]} · {row['id']}"):
            st.text(row['mo_ta'])
            if row['trang_thai'] == 'loi_de_xuat':
                st.error(row['lich_su'][-1]['ghi_chu'])
                if role in ('phan_tich', 'ky_su', 'admin') and row.get('loi_ky_thuat'):
                    st.text(row['loi_ky_thuat'])
            elif (store.folder(row['id']) / 'de_xuat/mapping_de_xuat.yml').exists():
                for line in tom_tat_nghiep_vu(store.proposal(row['id'])):
                    st.text(line)
                if role in ('phan_tich', 'ky_su', 'admin'):
                    st.markdown((store.folder(row['id']) / 'de_xuat/bao_cao_mapping.md').read_text(encoding='utf-8'))
            if row['trang_thai'] == 'tu_choi':
                st.warning('Lý do từ chối: ' + row['lich_su'][-1]['ghi_chu'])
            elif row['trang_thai'] == 'dang_chay':
                running_request(row['id'])
            elif row['trang_thai'] == 'cho_model_dbt':
                st.info('Đã duyệt và lưu file; đội dữ liệu cần bổ sung mô hình trước khi chạy.')
            elif row['trang_thai'] == 'loi':
                st.warning('Xử lý dữ liệu chưa thành công. Đội dữ liệu đang kiểm tra.')
            elif row['trang_thai'] == 'da_cong_bo':
                st.success('Đã cập nhật bản dữ liệu local.')


requests()
