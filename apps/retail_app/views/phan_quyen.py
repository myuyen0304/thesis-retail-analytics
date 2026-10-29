"""Trang Phân quyền, chỉ admin (docs/phan_quyen.md §3.1, §5): quản lý tài khoản, nhật ký, ma trận quyền.
Không bao giờ hiện mật khẩu đã băm; mật khẩu tạm chỉ hiện một lần ngay sau khi tạo / đặt lại."""
import pandas as pd
import streamlit as st

from ui import auth_store, roles

if roles.current_role() != 'admin':      # navigation đã chặn; chặn thêm ở đây cho chắc
    st.error('Trang này chỉ dành cho admin.')
    st.stop()

st.title('Phân quyền')
st.markdown('Ma trận quyền theo `docs/phan_quyen.md`. Tài khoản do admin tạo ở mục dưới; khách không cần tài khoản.')


def _mat_khau_tam(ten: str, mk: str) -> None:
    st.success(f'Mật khẩu tạm của **{ten}** (chỉ hiện lần này, gửi riêng cho người dùng; họ phải đổi ở lần đăng nhập đầu):')
    st.code(mk, language=None)


st.subheader('Tài khoản')
s = roles.store()
me = (roles.logged_in_user() or {}).get('username')
if not roles.auth_configured():
    st.info('Bản này chưa cấu hình DB tài khoản (`[app_db]` trong secrets hoặc `RETAIL_APP_DB_URL`), nên role lấy từ biến '
            'môi trường `RETAIL_APP_ROLE`. Chỉ dùng khi chạy local.')
elif s is None:
    st.error('Không kết nối được DB tài khoản.')
else:
    users = s.list_users()
    now = pd.Timestamp.now(tz='UTC')

    def _trang_thai(u: dict) -> str:
        if u['disabled']:
            return 'Bị khóa'
        if u['locked_until'] is not None and u['locked_until'] > now:
            return 'Tạm khóa (sai mật khẩu nhiều lần)'          # Khóa → Mở khóa hoặc Đặt lại mật khẩu thì mở ngay
        return 'Chưa đổi mật khẩu tạm' if u['must_change'] else 'Đang dùng'

    st.dataframe(pd.DataFrame({
        'Tên đăng nhập': [u['username'] for u in users],
        'Role': [roles.LABEL[u['role']] for u in users],
        'Trạng thái': [_trang_thai(u) for u in users],
        'Đăng nhập gần nhất': [u['last_login'] for u in users],
        'Tạo bởi': [u['created_by'] for u in users],
    }), hide_index=True)

    c_tao, c_sua = st.columns(2)
    with c_tao, st.form('tao_tai_khoan', clear_on_submit=True):
        st.markdown('**Tạo tài khoản**')
        ten = st.text_input('Tên đăng nhập', placeholder='vd. de1')
        role = st.selectbox('Role', auth_store.ROLES, format_func=roles.LABEL.get)
        if st.form_submit_button('Tạo'):
            mk = auth_store.temp_password()
            err = s.create(ten, role, mk, me)
            if err:
                st.error(err)
            else:
                _mat_khau_tam(auth_store.normalize(ten), mk)

    khac = [u['username'] for u in users if u['username'] != me]
    with c_sua:
        st.markdown('**Sửa tài khoản**')
        if not khac:
            st.caption('Chưa có tài khoản nào khác tài khoản của bạn.')
        else:
            ten = st.selectbox('Tài khoản', khac, key='pq_sua_ten')
            u = next(x for x in users if x['username'] == ten)
            role = st.selectbox('Role mới', auth_store.ROLES, index=auth_store.ROLES.index(u['role']),
                                format_func=roles.LABEL.get, key='pq_sua_role')
            b1, b2, b3 = st.columns(3)
            err, mk = None, None
            if b1.button('Đổi role', disabled=role == u['role']):
                err = s.set_role(ten, role, me) or 'ok'
            if b2.button('Mở khóa' if u['disabled'] else 'Khóa'):
                err = s.set_disabled(ten, not u['disabled'], me) or 'ok'
            if b3.button('Đặt lại mật khẩu'):
                mk = auth_store.temp_password()
                err = s.reset_password(ten, mk, me)
            if err == 'ok':
                roles._account.clear()
                st.rerun()
            elif err:
                st.error(err)
            elif mk:
                roles._account.clear()
                _mat_khau_tam(ten, mk)

    with st.expander('Nhật ký 50 dòng gần nhất'):
        log = s.recent_log(50)
        st.dataframe(pd.DataFrame({'Lúc': [r['ts'] for r in log], 'Tài khoản': [r['username'] for r in log],
                                   'Việc': [r['event'] for r in log], 'Chi tiết': [str(r['detail']) for r in log]}),
                     hide_index=True)

st.subheader('Trang theo role')
st.dataframe(pd.DataFrame({roles.LABEL[r]: ['✓' if roles.allowed(r, k) else '–' for k in roles.PAGES]
                           for r in roles.ROLES}, index=[t for _, t in roles.PAGES.values()]))
st.caption('Đổi backend ở thanh bên: ' + ', '.join(roles.LABEL[r] for r in roles.BACKEND_ROLES) + '.')

st.subheader('Cột theo mức nhạy cảm')
xem = {'du': '✓', 'che': 'che bớt', 'an': '–'}
st.dataframe(pd.DataFrame({roles.LABEL[r]: [xem[roles.column_view(r, lv)] for lv in roles.LEVELS] for r in roles.ROLES},
                          index=[roles.LEVEL_LABEL[lv] for lv in roles.LEVELS]))
st.caption('Cột chưa gán mức coi như Cấm. Mỗi lần ai đó xem cột từ mức Nội bộ trở lên, app ghi một dòng `retail.audit` '
           'vào log của bản deploy (email, thời điểm, trang, mức; không ghi giá trị).')
