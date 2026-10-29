"""Trang Phân quyền, chỉ admin (docs/phan_quyen.md §3.1). Không in bảng email → role, chỉ đếm số email mỗi role."""
import pandas as pd
import streamlit as st

from ui import roles

if roles.current_role() != 'admin':      # navigation đã chặn; chặn thêm ở đây cho chắc
    st.error('Trang này chỉ dành cho admin.')
    st.stop()

st.title('Phân quyền')
st.markdown('Ma trận quyền theo `docs/phan_quyen.md`. Đổi role của một người: sửa mục `[roles]` trong secrets của bản deploy.')

st.subheader('Tài khoản đang dùng')
if roles.auth_configured():
    bang = roles.role_table()
    st.markdown(f'Đăng nhập: **{roles.logged_in_email()}**, role **{roles.LABEL[roles.current_role()]}**.')
    st.dataframe(pd.DataFrame({'Role': [roles.LABEL[r] for r in roles.ROLES[1:]],
                               'Số email': [len(bang.get(r) or ()) for r in roles.ROLES[1:]]}), hide_index=True)
    la = sorted(set(bang) - set(roles.ROLES[1:]))
    if la:
        st.warning(f'Mục `[roles]` có tên role không nhận ra, bị bỏ qua: {", ".join(la)}.')
else:
    st.info('Bản này chưa cấu hình đăng nhập (`[auth]` trong secrets), nên role lấy từ biến môi trường `RETAIL_APP_ROLE`. '
            'Chỉ dùng khi chạy local.')

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
