"""App phân tích doanh thu (GĐ 2, docs/gd2_app_plan.md).

Chạy từ root repo:
    .venv/Scripts/streamlit.exe run apps/retail_app/app.py
Chọn backend mặc định bằng biến môi trường RETAIL_BACKEND=postgres|duckdb|databricks (role kỹ thuật đổi được ở thanh bên).
Role (docs/phan_quyen.md): bản deploy đăng nhập bằng tài khoản admin tạo (ui/roles.py, DB tài khoản [app_db]);
chạy local không có DB tài khoản thì đặt RETAIL_APP_ROLE=khach|quan_ly|phan_tich|ky_su|admin.
"""
import streamlit as st

from ui import roles
from ui.common import report_reads, sidebar

st.set_page_config(page_title='Doanh thu bán lẻ', layout='wide')

# Chỉ trang role được xem mới có trong navigation: mở thẳng URL trang khác cũng không vào được.
role = roles.current_role()
pages = [st.Page(path, title=title, default=key == roles.DEFAULT_PAGE[role])
         for key, (path, title) in roles.PAGES.items() if roles.allowed(role, key)]
nav = st.navigation(pages)
sidebar(role)
top = st.container()      # chỗ trống ở đầu trang cho thông báo "Đọc lại thành công"
nav.run()
report_reads(top)         # trang lỗi thì đã st.stop() trước khi tới đây
