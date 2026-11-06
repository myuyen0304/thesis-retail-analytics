"""DE duyệt và chạy; chỉ Admin được công bố vào registry local của tính năng."""
import pandas as pd
import streamlit as st

from ui import roles, nhap_runner
from ui.nhap_store import RequestStore, LABELS, nhap_kha_dung
from scripts.ingest import approval
from scripts.ingest.source_contract import SOURCES

if not roles.allowed(roles.current_role(), 'duyet_du_lieu'):
    st.error('Bạn không có quyền xem trang này.')
    st.stop()
if not nhap_kha_dung():
    st.info('Chức năng nhập dữ liệu trên bản web đang được phát triển. Hiện chạy ở bản nội bộ.')
    st.stop()
import yaml
from scripts.ingest import extension_contract
st.title('Duyệt dữ liệu')
st.caption('Chỉ chạy DuckDB local. Công bố tại đây cập nhật kho nhập dữ liệu; kho báo cáo của app giữ cấu hình hiện tại.')
st.info('Đã có model dbt cho orders_enriched và shipments_realistic. Phần mở rộng khác cần DE bổ sung model trước khi chạy.')
store = RequestStore()
try:
    nhap_runner.recover_queue(store, wait=False)
    pending = store.sync_events()
    if pending:
        st.warning(f'{pending} dòng nhật ký chờ đồng bộ')
except (OSError, ValueError) as error:
    st.warning(str(error))


def running_status(record):
    request_id = record['id']
    st.info(f"Đang chạy {record.get('stage', 'prepare')} · {nhap_runner.elapsed(record)} giây.")
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
    snapshot = nhap_runner.page_snapshot(store, user['username'], roles.current_role())
    rows = snapshot['rows']
    if not rows:
        st.info('Chưa có yêu cầu.')
        return
    selected = st.selectbox('Yêu cầu', [r['id'] for r in rows], key='nhap_selected_request',
        format_func=lambda key: next(f"{r['ten_file']} · {r['nguoi_gui']} · {r['id']}" for r in rows if r['id'] == key))
    record = store.read(selected)
    st.text(record['mo_ta'])
    st.caption('Trạng thái: ' + LABELS[record['trang_thai']])
    if record['trang_thai'] == 'da_gui' and not record.get('duong'):
        st.caption('Đang đọc và hiểu file…')
    else:
        st.caption('Đường xử lý: ' + ('Tự động' if record.get('duong') == 'tu_dong' else 'Chờ đội dữ liệu'))
    if record.get('hop_dong'):
        st.caption(f"Hợp đồng {record['hop_dong']['ten']} v{record['hop_dong']['phien_ban']}")
    for reason in record.get('ly_do', []):
        st.warning(reason['ky_thuat'])
    for column in record.get('phan_loai', {}).get('cot_tuy_chon_thieu', []):
        st.info(f'File không có cột `{column}`; bản dữ liệu này sẽ không có cột đó')
    position = nhap_runner.queue_position(store, selected)
    if position:
        st.info(f'Đang xếp hàng (thứ {position})')
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
            st.caption('Duyệt tay cho tên đã có hợp đồng chỉ áp dụng với yêu cầu này; hợp đồng hiện hành chỉ đổi qua Nâng hợp đồng.')
            st.caption('PII mặc định chỉ ở silver. Chọn mart là quyết định chủ động cho phép xuất hiện trên báo cáo.')
            frame = pd.DataFrame(defaults['cot'])
            for col, value in [('kieu', 'string'), ('duoc_rong', False), ('hien_thi', 'silver'), ('ly_do', '')]:
                if col not in frame:
                    frame[col] = value
                frame[col] = frame[col].fillna(value)
            edited = st.data_editor(frame, disabled=['ten'], hide_index=True, key='cot_' + selected,
                column_config={'xu_ly': st.column_config.SelectboxColumn('Xử lý', options=['khoa_noi', 'doi_chieu_loi', 'bo', 'nap'], required=True),
                               'kieu': st.column_config.SelectboxColumn('Kiểu', options=extension_contract.VALID_TYPES, required=True),
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
    cancelled = nhap_runner.cancelled_backfill(store, record)
    if cancelled:
        st.warning('Yêu cầu nạp bù đã bị hủy, không chạy')
    if state == 'loi':
        with st.form('duyet_lai_' + selected):
            retry_reason = st.text_area('Lý do duyệt lại (bắt buộc)')
            retry = st.form_submit_button('Duyệt lại')
        if retry:
            try:
                store.retry_review(selected, record['revision'], retry_reason)
                st.rerun()
            except Exception as error:
                st.error(str(error))
    if state == 'cho_model_dbt':
        st.warning('Đã duyệt và land; cần DE viết model dbt trước khi chạy.')
        st.button('Chạy', disabled=True)
    if state in ('da_duyet', 'loi', 'da_cong_bo', 'da_kiem'):
        reason = nhap_runner.busy_reason(store)
        if reason:
            st.info(reason)
        try:
            if state != 'da_kiem' and st.button('Chạy lại để kiểm' if state == 'da_cong_bo' else 'Chạy', disabled=bool(reason) or cancelled):
                nhap_runner.start(store, selected, record['revision'])
                st.rerun()
            if state == 'da_kiem' and roles.current_role() == 'admin' and st.button('Công bố', disabled=bool(reason), type='primary'):
                with st.spinner('Đang công bố…'):
                    nhap_runner.publish(store, selected, record['revision'])
                st.rerun()
        except Exception as error:
            st.error(str(error))
    def draw_running(current):
        latest = next((row for row in current['rows'] if row['id'] == selected), None)
        if latest and latest['trang_thai'] == 'dang_chay':
            running_status(latest)

    nhap_runner.monitor_page(store, user['username'], roles.current_role(), snapshot, draw=draw_running)
    if state == 'da_cong_bo':       # đứng trên thong_bao: dòng đó có thể còn của lượt trước
        notice = nhap_runner.doi_chieu_ban(store, record)
        if notice:
            getattr(st, notice[0])(notice[1])
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

    from scripts.ingest.contract_registry import ContractRegistry
    registry = ContractRegistry(store.base)
    if record.get('hop_dong'):
        version = record['hop_dong']['phien_ban'] + 1
        notice = registry.upgrade_notice(record['hop_dong']['ten'], version)
        if notice:
            st.info(notice)
    if record in store.pending_upgrades():
        name = record['hop_dong']['ten']
        version = record['hop_dong']['phien_ban']
        st.subheader(f'Nâng hợp đồng {name} v{version} → v{version + 1}')
        st.caption('Chỉ các cột mới; mặc định silver. Chọn mart chỉ khi model dbt đã có cột đó.')
        new_columns = set(record['cot_moi'])
        defaults = [c for c in approval.default_decisions(proposal)['cot'] if c['ten'] in new_columns]
        for column in defaults:
            if column['xu_ly'] == 'nap':
                column['hien_thi'] = 'silver'
        with st.form('nang_' + selected):
            frame = pd.DataFrame(defaults)
            for col, value in [('kieu', 'string'), ('duoc_rong', False), ('hien_thi', 'silver'), ('ly_do', '')]:
                if col not in frame:
                    frame[col] = value
                frame[col] = frame[col].fillna(value)
            edited = st.data_editor(frame, disabled=['ten'], hide_index=True, key='cot_nang_' + selected,
                column_config={'xu_ly': st.column_config.SelectboxColumn('Xử lý', options=['bo', 'nap'], required=True),
                               'kieu': st.column_config.SelectboxColumn('Kiểu', options=extension_contract.VALID_TYPES, required=True),
                               'duoc_rong': st.column_config.CheckboxColumn('Được rỗng'),
                               'hien_thi': st.column_config.SelectboxColumn('Hiển thị', options=['silver', 'mart']),
                               'ly_do': st.column_config.TextColumn('Lý do')})
            approve_upgrade = st.form_submit_button('Duyệt nâng hợp đồng')
        missing_mart = [row['ten'] for row in edited.to_dict('records')
                        if row['xu_ly'] == 'nap' and row['hien_thi'] == 'mart'
                        and not store.mart_column_available(name, row['ten'])]
        if missing_mart:
            st.warning('Model dbt chưa có cột ' + ', '.join(missing_mart) +
                       '; chưa thể duyệt nâng hợp đồng với lựa chọn mart.')
        if approve_upgrade:
            try:
                decisions = []
                for row in edited.to_dict('records'):
                    keys = ['ten', 'xu_ly']
                    if row['xu_ly'] == 'nap':
                        keys += ['kieu', 'duoc_rong', 'hien_thi']
                    else:
                        keys += ['ly_do']
                    decisions.append({key: row[key] for key in keys})
                store.upgrade_contract(selected, decisions)
                st.rerun()
            except Exception as error:
                st.error(str(error))
        with st.form('tu_choi_nang_' + selected):
            reject_reason = st.text_area('Lý do từ chối nâng hợp đồng')
            reject_upgrade = st.form_submit_button('Từ chối nâng hợp đồng')
        if reject_upgrade:
            try:
                store.reject_upgrade(selected, reject_reason)
                st.rerun()
            except Exception as error:
                st.error(str(error))

    if roles.current_role() == 'admin':
        st.subheader('Rollback kho nhập dữ liệu')
        try:
            versions = nhap_runner.rollback_options(store)
            labels = {row['id']: row['label'] for row in nhap_runner.rollback_details(store)}
        except nhap_runner.READ_ERRORS:
            versions = []
            st.warning('Chưa đọc được danh sách bản để khôi phục.')
        if (done := st.session_state.pop('rollback_xong', None)):
            st.success(f'Đã khôi phục bản dữ liệu local ({done[:8]}).')
        if versions:
            # Mỗi lần rollback xong form mang khóa mới, nên ô xác nhận về trạng thái chưa tick:
            # bấm thêm một lần không đổi bản tiếp
            with st.form(f"rollback_ui_nhap_{st.session_state.get('rollback_lan', 0)}"):
                release_id = st.selectbox('Bản cần khôi phục', versions, format_func=lambda key: labels.get(key, key))
                confirmed = st.checkbox('Tôi xác nhận khôi phục bản dữ liệu này')
                run_rollback = st.form_submit_button('Rollback')
            if run_rollback and not confirmed:
                st.warning('Cần xác nhận trước khi khôi phục bản dữ liệu.')
            if run_rollback and confirmed:
                result = None
                try:
                    result = nhap_runner.rollback(store, release_id)
                    if result.returncode:
                        st.error(result.stderr or result.stdout)
                except Exception as error:
                    st.error(str(error))
                if result is not None and not result.returncode:
                    # Chạy lại trang: trạng thái yêu cầu, cảnh báo và danh sách bản ở trên đều được đọc trước khi rollback
                    st.session_state['rollback_xong'] = release_id
                    st.session_state['rollback_lan'] = st.session_state.get('rollback_lan', 0) + 1
                    st.rerun()

review()
