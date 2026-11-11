"""Tự kiểm lại trạng thái đợt, để trang hiện có vẽ lại khi có thay đổi."""
from ui import roles
from ui.nhap_dot import can_theo_doi


def theo_doi_dot(store, username, role, anh_dau):
    import streamlit as st

    # Lượt vẽ trang đã có ảnh đầu; chỉ đọc kho từ nhịp fragment kế tiếp.
    first_poll = [True]

    @st.fragment(run_every='30s' if can_theo_doi(anh_dau) else None)
    def poll():
        if first_poll[0]:
            first_poll[0] = False
            return
        user = roles.logged_in_user()
        if not user or user['username'] != username or roles.current_role() != role:
            st.rerun(scope='app')
        try:
            current = store.anh_chup(username, role)
        except Exception:
            # Files API có thể lỗi tạm thời; giữ trang và thử lại ở nhịp sau.
            return
        if current != anh_dau:
            st.rerun(scope='app')

    poll()
