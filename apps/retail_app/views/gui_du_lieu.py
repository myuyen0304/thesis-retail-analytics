"""Gửi file và theo dõi yêu cầu; Quản lý chỉ thấy tóm tắt nghiệp vụ."""
import streamlit as st

from ui import roles, nhap_runner
from ui.nhap_store import RequestStore, LABELS, nhap_kha_dung
from scripts.ingest.approval import tom_tat_nghiep_vu

if not roles.allowed(roles.current_role(), 'gui_du_lieu'):
    st.error('Bạn không có quyền xem trang này.')
    st.stop()
from ui.common import backend
from ui.kho_dot import configured_store, mode
from ui.nhap_dot import DotStore

local_available = nhap_kha_dung()
dot_mode = mode()
if not local_available and dot_mode == 'tat':
    st.info('Chức năng nhập dữ liệu trên bản web đang được phát triển. Hiện chạy ở bản nội bộ.')
    st.stop()
st.title('Gửi dữ liệu')
user = roles.logged_in_user()
if not user:
    st.info('Đăng nhập để gửi và theo dõi dữ liệu.')
    st.stop()
if dot_mode != 'tat':
    st.subheader('Gửi đợt dữ liệu')
    try:
        dots = DotStore(configured_store())
    except (ValueError, OSError) as error:
        st.info(str(error))
    else:
        with st.form('gui_dot', clear_on_submit=True):
            uploads = st.file_uploader('Các file của đợt', type=['csv', 'json'],
                                      accept_multiple_files=True, max_upload_size=200)
            batch_label = st.text_input('Nhãn đợt', max_chars=40)
            batch_description = st.text_area('Mô tả đợt', max_chars=2000)
            send_batch = st.form_submit_button('Gửi đợt dữ liệu')
        if send_batch:
            try:
                row = dots.gui_dot(uploads, batch_label, batch_description)
                st.success(f"Đã gửi đợt {row['nhan']}.")
            except Exception as error:
                st.error(str(error))
        try:
            command = dots.latest_command()
            for row in dots.visible(user['username'], roles.current_role()):
                with st.expander(f"{row['nhan']} · {dots.label(row, command)} · {row['id']}"):
                    st.caption(f"{len(row['files'])} file · {sum(f['so_byte'] for f in row['files']) / 1024**2:.2f} MB · {row['ngay_gui']}")
                    st.text(row.get('mo_ta', ''))
                    if row.get('ma_loi'):
                        st.warning(f"{row['ma_loi']}: {row.get('thong_bao', '')}")
                    elif row.get('thong_bao'):
                        st.info(row['thong_bao'])
                    if row['trang_thai'] in ('dang_chay', 'da_kiem') and row.get('release_id'):
                        st.caption('Bản dữ liệu: ' + row['release_id'][:8])
        except Exception as error:
            st.error('Chưa đọc được yêu cầu đợt; báo kỹ sư dữ liệu.')
if not local_available:
    st.stop()
st.caption('Mỗi yêu cầu nhận một file CSV hoặc JSON, tối đa 200 MB.')
store = RequestStore()
try:
    nhap_runner.recover_queue(store, wait=False)
except (OSError, ValueError):
    pass
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


def requests():
    role = roles.current_role()
    if not roles.allowed(role, 'gui_du_lieu'):
        return
    current = roles.logged_in_user()
    if not current:
        return
    snapshot = nhap_runner.page_snapshot(store, current['username'], role)
    rows = snapshot['rows']
    dang_dung = nhap_runner.nguon_dang_dung(store) if any(r['trang_thai'] == 'da_cong_bo' for r in rows) else None
    st.subheader('Yêu cầu đã gửi')
    if not rows:
        st.info('Chưa có yêu cầu.')
    for row in rows:
        publishing = nhap_runner.awaiting_publish(row, snapshot['busy'])
        label = 'Đang xử lý' if publishing or row['trang_thai'] == 'dang_chay' else LABELS[row['trang_thai']]
        with st.expander(f"{row['ten_file']} · {label} · {row['id']}"):
            st.text(row['mo_ta'])
            if row['trang_thai'] == 'da_gui' and not row.get('duong'):
                st.caption('Đang đọc và hiểu file…')
            else:
                st.caption('Đường xử lý: ' + ('Tự động' if row.get('duong') == 'tu_dong' else 'Chờ đội dữ liệu'))
            for reason in row.get('ly_do', []):
                st.info(reason['nghiep_vu'])
            for column in row.get('phan_loai', {}).get('cot_tuy_chon_thieu', []):
                st.info(f'File không có cột `{column}`; bản dữ liệu này sẽ không có cột đó')
            position = snapshot['positions'][row['id']]
            if position:
                st.info(f'Đang xếp hàng (thứ {position})')
            if snapshot['notices'][row['id']]:
                st.info(snapshot['notices'][row['id']])
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
                stage = row.get('stage')
                if stage in nhap_runner.STAGES:
                    st.info(f'Đang xử lý (bước {nhap_runner.STAGES.index(stage) + 1}/4)')
                else:
                    st.info('Đang xử lý')
            elif publishing:
                st.info('Đang xử lý')
            elif row['trang_thai'] == 'cho_model_dbt':
                st.info('Đã duyệt và lưu file; đội dữ liệu cần bổ sung mô hình trước khi chạy.')
            elif row['trang_thai'] == 'loi':
                st.warning('Xử lý dữ liệu chưa thành công. Đội dữ liệu đang kiểm tra.')
            elif row['trang_thai'] == 'da_cong_bo':
                if dang_dung is None:
                    st.info('Đã xử lý xong; đội dữ liệu đang kiểm tra trạng thái hiện tại.')
                elif dang_dung[0] is None or row.get('ten_mo_rong') in dang_dung[1]:   # chưa có bản nào để so: giữ câu cũ
                    st.success('Đã cập nhật dữ liệu')
                else:
                    st.info('Dữ liệu này đã từng được cập nhật nhưng hiện không nằm trong bản đang dùng.')
    nhap_runner.monitor_page(store, current['username'], role, snapshot, notify=True)


requests()
