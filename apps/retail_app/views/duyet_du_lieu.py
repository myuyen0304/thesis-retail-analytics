"""DE duyệt và chạy; chỉ Admin được công bố vào registry local của tính năng."""
import pandas as pd
import streamlit as st

from ui import roles, nhap_runner
from ui.nhap_store import RequestStore, LABELS, nhap_kha_dung
from scripts.ingest import approval
from ui.form_duyet import form_duyet, form_nang

if not roles.allowed(roles.current_role(), 'duyet_du_lieu'):
    st.error('Bạn không có quyền xem trang này.')
    st.stop()
from ui.common import backend
from ui.kho_dot import configured_store, mode, KhongCo, DaCo, TrangThaiDaDoi
from ui.trang_thai_dot import request_path
from ui.nhap_dot import DotStore, tao_anh_chup
from ui.theo_doi_dot import theo_doi_dot

local_available = nhap_kha_dung()
dot_mode = mode()
if not local_available and dot_mode == 'tat':
    if backend() == 'databricks' and roles.current_role() == 'admin':
        st.info('Công bố dashboard trên bản này cần kho đợt (Volume)')
    else:
        st.info('Chức năng nhập dữ liệu trên bản web đang được phát triển. Hiện chạy ở bản nội bộ.')
    st.stop()
st.title('Duyệt dữ liệu')
dots = None
dot_snapshot = None
if dot_mode != 'tat':
    st.subheader('Đợt dữ liệu')
    try:
        dots = DotStore(configured_store())
        current_user = roles.logged_in_user()
        if current_user:
            command = dots.latest_command()
            dot_rows = dots.visible(current_user['username'], roles.current_role())
            dot_snapshot = tao_anh_chup(dot_rows, command)
            for row in (r for r in dot_rows if r.get('loai') != 'mot_file'):
                with st.expander(f"{row['nhan']} · {dots.label(row, command)} · {row['id']}"):
                    st.caption(f"{len(row['files'])} file · {sum(f['so_byte'] for f in row['files']) / 1024**2:.2f} MB · {row['ngay_gui']}")
                    if row.get('release_id'):
                        st.caption('Bản dữ liệu: ' + row['release_id'][:8])
                    if row.get('ma_loi'):
                        st.warning(f"{row['ma_loi']}: {row.get('thong_bao', '')}")
                    elif row.get('thong_bao'):
                        st.info(row['thong_bao'])
                    if row['trang_thai'] == 'loi':
                        if st.button('Chạy lại', key='dot_retry_' + row['id']):
                            dots.change(row['id'], 'cho_chay')
                            st.rerun()
                        if st.button('Hủy', key='dot_cancel_' + row['id']):
                            dots.change(row['id'], 'huy')
                            st.rerun()
            if dot_mode == 'volume':
                st.subheader('Yêu cầu một file')
                for row in (r for r in dot_rows if r.get('loai') == 'mot_file'):
                    with st.expander(f"{row['nhan']} · {dots.label(row, command)} · {row['id']}"):
                        try:
                            request_id = row['id']
                            folder = request_path(request_id)
                            st.text(row.get('mo_ta', ''))
                            st.caption('Trạng thái: ' + dots.label(row, command))
                            st.caption('Đường xử lý: ' + ('Tự động' if row.get('duong') == 'tu_dong' else 'Chờ đội dữ liệu'))
                            for reason in row.get('ly_do', []):
                                st.warning(reason['ky_thuat'])
                            if row.get('thong_bao'):
                                st.info(row['thong_bao'])
                            notice = dots.notice(request_id)
                            if notice:
                                st.info(notice)
                            if row.get('ten_mo_rong'):
                                st.caption('Hợp đồng ' + row['ten_mo_rong'])
                                st.code(dots.kho.doc(folder + '/hop_dong/' + row['ten_mo_rong'] + '.yml').decode('utf-8'), language='yaml')
                            proposal = None
                            try:
                                proposal = dots.proposal(request_id)
                            except KhongCo:
                                pass
                            if proposal:
                                with st.expander('Báo cáo kỹ thuật đầy đủ'):
                                    st.markdown(dots.kho.doc(folder + '/de_xuat/bao_cao_mapping.md').decode('utf-8'))
                                    st.json(proposal)
                            if row['trang_thai'] == 'cho_duyet' and proposal:
                                result = form_duyet(proposal, row['file']['ten'], request_id)
                                if result:
                                    name, decisions = result
                                    dots.approve(request_id, len(row['lich_su']), decisions, name)
                                    st.rerun()
                                with st.form('tu_choi_' + request_id):
                                    reason = st.text_area('Lý do từ chối (bắt buộc)')
                                    reject = st.form_submit_button('Từ chối')
                                if reject:
                                    dots.reject(request_id, len(row['lich_su']), reason)
                                    st.rerun()
                            if row['trang_thai'] == 'tu_choi':
                                st.warning('Lý do từ chối: ' + row['lich_su'][-1]['ghi_chu'])
                            if row['trang_thai'] == 'cho_model_dbt':
                                st.info('Đã duyệt và lưu file; đội dữ liệu cần bổ sung mô hình trước khi chạy.')
                            if row['trang_thai'] == 'loi':
                                if st.button('Chạy lại', key='mot_retry_' + request_id):
                                    dots.change(request_id, 'cho_chay')
                                    st.rerun()
                                if st.button('Hủy', key='mot_cancel_' + request_id):
                                    dots.change(request_id, 'huy')
                                    st.rerun()
                            current = dots.upgrade_info(request_id)
                            if current and proposal:
                                version = current[0]['phien_ban']
                                name = row['ten_mo_rong']
                                st.subheader(f'Nâng hợp đồng {name} v{version} → v{version + 1}')
                                decisions = form_nang(proposal, row['cot_moi'], request_id)
                                if decisions is not None:
                                    dots.upgrade_contract(request_id, decisions, expected=version)
                                    st.rerun()
                                with st.form('tu_choi_nang_' + request_id):
                                    reason = st.text_area('Lý do từ chối nâng hợp đồng')
                                    reject = st.form_submit_button('Từ chối nâng hợp đồng')
                                if reject:
                                    dots.reject_upgrade(request_id, reason, expected=version)
                                    st.rerun()
                            elif row.get('duong') == 'tu_dong' and row.get('cot_moi'):
                                from ui.kho_hop_dong import KhoHopDong
                                if KhoHopDong(dots.kho).rejected(row['ten_mo_rong'], row['cot_moi']):
                                    st.info('Đã từ chối nâng hợp đồng cho các cột mới.')
                                else:
                                    st.info('Cột mới có hiệu lực từ lần gửi sau; gửi lại file để dựng bản có cột mới')
                            with st.expander('Lịch sử yêu cầu'):
                                st.json(row['lich_su'])
                        except (DaCo, TrangThaiDaDoi):
                            st.warning('Có người vừa thao tác cùng lúc; tải lại trang.')
                        except Exception as error:
                            st.error('Chưa xử lý được yêu cầu một file: ' + type(error).__name__)
            ledger = dots.ledger()
            st.subheader('Sổ đợt')
            st.caption('Chỉ ảnh hưởng lần dựng đợt sau, không đổi dashboard đang hiện.')
            st.dataframe(pd.DataFrame([{'Thứ tự': r['so'], 'Mã đợt': r['ma_dot'][:8],
                'Yêu cầu': r.get('request_id', ''), 'Bản': r.get('release_id', '')[:8]} for r in ledger]), hide_index=True)
            if ledger:
                with st.form('dot_remove'):
                    removed = st.selectbox('Đợt cần bỏ', [r['ma_dot'] for r in ledger], format_func=lambda code: code[:8])
                    reason = st.text_area('Lý do bỏ khỏi sổ (bắt buộc)')
                    remove = st.form_submit_button('Bỏ khỏi sổ')
                if remove:
                    dots.remove_from_ledger(removed, reason)
                    st.rerun()
        else:
            st.info('Cần đăng nhập để duyệt dữ liệu.')
    except Exception as error:
        st.error(str(error) if str(error) in ('Sổ đợt hỏng; báo kỹ sư dữ liệu.', 'Chưa cấu hình kho đợt') else 'Dữ liệu đợt hỏng; báo kỹ sư dữ liệu.')

if backend() == 'databricks' and roles.current_role() == 'admin':
    if dot_mode != 'volume':
        st.info('Công bố dashboard trên bản này cần kho đợt (Volume)')
    elif dots is not None:
        st.subheader('Bản dữ liệu trên dashboard')
        try:
            state = nhap_runner.dashboard_state_cloud()
            command = dots.latest_command()
            if dot_snapshot is not None:
                dot_snapshot = tao_anh_chup(dot_rows, command)
            pending = command is not None and command['ket_qua'] is None
            if pending:
                st.info('Đang chờ Airflow xử lý lệnh (thường dưới 5 phút)')
            elif command and command['ket_qua'].get('ket_qua') == 'loi':
                st.error(command['ket_qua'].get('thong_bao', 'Lệnh dashboard bị lỗi.'))
            st.caption('Bản dashboard: ' + str(state.get('dashboard') or 'Theo bản số thật'))
            since = state.get('dashboard_since')
            if isinstance(since, dict) and since.get('release_id') == state.get('dashboard') and since.get('at'):
                st.caption('Giờ công bố: ' + str(since['at']))
            candidates = sorted(key for key, value in state.get('releases', {}).items()
                                if value.get('status') == 'ready' and
                                ((value.get('co_du_lieu_tong_hop') is True) != (value.get('chi_dashboard') is True)))
            if candidates:
                has_new_source = any(state['releases'][key].get('chi_dashboard') is True for key in candidates)
                def candidate_label(key):
                    record = state['releases'][key]
                    kind = ('Bản có đợt (dữ liệu tổng hợp)' if record.get('co_du_lieu_tong_hop') is True
                            else 'Bản có nguồn mới ' + ', '.join(record.get('nguon_moi') or []))
                    return key + ' · ' + kind if has_new_source else key
                chosen = st.selectbox('Bản dữ liệu', candidates, disabled=pending,
                                      key='cloud_dashboard_release', format_func=candidate_label)
                record = state['releases'][chosen]
                synthetic = record.get('co_du_lieu_tong_hop') is True
                st.caption('Bản có đợt (dữ liệu tổng hợp)' if synthetic else
                           'Bản có nguồn mới ' + ', '.join(record.get('nguon_moi') or []))
                with st.form('cloud_dashboard_publish'):
                    confirmed = (st.checkbox('Đây là dữ liệu tổng hợp, chỉ để demo', disabled=pending)
                                 if synthetic else False)
                    publish = st.form_submit_button(
                        'Đưa bản có đợt lên dashboard (demo)' if synthetic else 'Đưa bản có nguồn mới lên dashboard',
                        disabled=pending)
                if publish:
                    dots.dashboard_command(chosen, confirmed=confirmed)
                    st.rerun()
            if state.get('dashboard') and st.button('Trả dashboard về bản số thật', disabled=pending):
                dots.dashboard_command()
                st.rerun()
        except Exception:
            st.error('Chưa đọc được dashboard; báo kỹ sư dữ liệu.')
if dots is not None and dot_snapshot is not None and current_user:
    theo_doi_dot(dots, current_user['username'], roles.current_role(), dot_snapshot)
if not local_available:
    st.stop()
import yaml
from scripts.ingest import extension_contract
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
        result = form_duyet(proposal, record['ten_file'], selected)
        if result:
            try:
                name, decisions = result
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


# Đợt do DAG dựng không cần có yêu cầu nhập UI; khối này không nằm trong review().
if roles.current_role() == 'admin':
    from ui.common import backend
    try:
        dashboard_root, dashboard_registry = nhap_runner.dashboard_state(store.base, backend())
    except (OSError, ValueError, KeyError) as error:
        st.info(str(error) if isinstance(error, ValueError) else 'Chưa đọc được registry của dashboard.')
    else:
        st.subheader('Bản dữ liệu trên dashboard')
        if st.session_state.pop('dashboard_done', False):
            st.success('Đã cập nhật bản dashboard.')
        candidates = [key for key, value in dashboard_registry.get('releases', {}).items()
                      if value.get('status') == 'ready' and value.get('co_du_lieu_tong_hop') is True]
        action, chosen, confirmed = False, None, False
        if candidates:
            with st.form(f"dashboard_publish_{st.session_state.get('dashboard_count', 0)}"):
                chosen = st.selectbox('Bản có đợt', sorted(candidates))
                confirmed = st.checkbox('Đây là dữ liệu tổng hợp, chỉ để demo')
                action = st.form_submit_button('Đưa bản có đợt lên dashboard (demo)')
        if dashboard_registry.get('dashboard') and st.button('Trả dashboard về bản số thật'):
            action, chosen = True, None
        if action:
            try:
                outcome = nhap_runner.dashboard_action(store, backend(), chosen, confirmed=confirmed)
                if outcome.returncode:
                    st.error(outcome.stderr or outcome.stdout)
                else:
                    st.session_state['dashboard_done'] = True
                    st.session_state['dashboard_count'] = st.session_state.get('dashboard_count', 0) + 1
                    st.rerun()
            except (ValueError, PermissionError) as error:
                st.error(str(error))
