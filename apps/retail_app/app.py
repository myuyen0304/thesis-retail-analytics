"""App phân tích doanh thu (GĐ 2, docs/gd2_app_plan.md).

Chạy từ root repo:
    .venv/Scripts/streamlit.exe run apps/retail_app/app.py
Chọn backend mặc định bằng biến môi trường RETAIL_BACKEND=postgres|duckdb|databricks (đổi được ở thanh bên).
"""
import streamlit as st

from ui.common import report_reads, sidebar

st.set_page_config(page_title='Doanh thu bán lẻ', layout='wide')

pages = [
    st.Page('views/tong_quan.py', title='Tổng quan', default=True),
    st.Page('views/ps1_do_dung.py', title='PS1: Đo đúng doanh thu'),
    st.Page('views/ps2_xu_huong.py', title='PS2: Xu hướng'),
    st.Page('views/ps3_nhip_lich.py', title='PS3: Nhịp lịch'),
    st.Page('views/ps4_don_mon_gia.py', title='PS4: Số đơn, số món, giá'),
    st.Page('views/ps5_nhom.py', title='PS5: Nhóm kéo lên/xuống'),
    st.Page('views/suc_khoe_du_lieu.py', title='Sức khỏe dữ liệu'),
]
nav = st.navigation(pages)
sidebar()
top = st.container()      # chỗ trống ở đầu trang cho thông báo "Đọc lại thành công"
nav.run()
report_reads(top)         # trang lỗi thì đã st.stop() trước khi tới đây
