"""Phân quyền theo role trong app (docs/phan_quyen.md §3.1, §5, §7).

Role xác định một lần mỗi lượt chạy, theo thứ tự (fail closed, §4 mục 7):
- có `[auth]` trong secrets: đã đăng nhập (st.login, OIDC) → tra email trong `[roles]`; chưa đăng nhập, email lạ,
  email chưa xác minh → khách. Lúc này biến môi trường RETAIL_APP_ROLE không có tác dụng;
- không có `[auth]` (chạy local để dev): đọc RETAIL_APP_ROLE, mặc định khách.

Bảng email → role chỉ nằm trong secrets của bản deploy, không nằm trong repo:
    [roles]
    admin = ["a@example.com"]
    quan_ly = ["b@example.com", "c@example.com"]
Một email có ở nhiều role thì lấy role thấp nhất. Admin chọn được "Xem như role" ở thanh bên (chỉ hạ quyền).
"""
import datetime as dt
import json
import logging
import os
import re

import pandas as pd
import streamlit as st

ROLES = ('khach', 'quan_ly', 'phan_tich', 'ky_su', 'admin')          # thấp → cao
LABEL = {'khach': 'Khách', 'quan_ly': 'Quản lý', 'phan_tich': 'DA/BI', 'ky_su': 'Data engineer', 'admin': 'Admin'}

# key → (file trang, tiêu đề); thứ tự này là thứ tự trên menu
PAGES = {
    'tong_quan': ('views/tong_quan.py', 'Tổng quan'),
    'ps1_do_dung': ('views/ps1_do_dung.py', 'PS1: Đo đúng doanh thu'),
    'ps2_xu_huong': ('views/ps2_xu_huong.py', 'PS2: Xu hướng'),
    'ps3_nhip_lich': ('views/ps3_nhip_lich.py', 'PS3: Nhịp lịch'),
    'ps4_don_mon_gia': ('views/ps4_don_mon_gia.py', 'PS4: Số đơn, số món, giá'),
    'ps5_nhom': ('views/ps5_nhom.py', 'PS5: Nhóm kéo lên/xuống'),
    'du_bao': ('views/du_bao.py', 'Dự báo'),
    'suc_khoe_du_lieu': ('views/suc_khoe_du_lieu.py', 'Sức khỏe dữ liệu'),
    'ai_explain': ('views/ai_explain.py', 'Hỏi dữ liệu (AI)'),
    'phan_quyen': ('views/phan_quyen.py', 'Phân quyền'),
}

# Ma trận §3.1. Trang mới phải thêm vào đây, chưa thêm thì không role nào thấy.
_KHACH = ('tong_quan', 'ps1_do_dung', 'ps2_xu_huong', 'ps3_nhip_lich', 'ps4_don_mon_gia', 'ps5_nhom', 'du_bao')
PAGES_BY_ROLE = {
    'khach': _KHACH,
    'quan_ly': _KHACH + ('ai_explain',),
    'phan_tich': _KHACH + ('suc_khoe_du_lieu', 'ai_explain'),
    'ky_su': _KHACH + ('suc_khoe_du_lieu', 'ai_explain'),
    'admin': _KHACH + ('suc_khoe_du_lieu', 'ai_explain', 'phan_quyen'),
}
DEFAULT_PAGE = {'khach': 'tong_quan', 'quan_ly': 'tong_quan', 'phan_tich': 'ps1_do_dung',
                'ky_su': 'suc_khoe_du_lieu', 'admin': 'suc_khoe_du_lieu'}
BACKEND_ROLES = ('ky_su', 'admin')       # được đổi backend ở thanh bên
PREVIEW_KEY = 'xem_nhu_role'             # session_state của ô "Xem như role" (chỉ admin)

# Mức nhạy cảm của cột (§7.1). Cột không có mức coi như 'cam'.
LEVELS = ('cong_khai', 'noi_bo', 'lien_he', 'cam')
LEVEL_LABEL = {'cong_khai': 'Công khai', 'noi_bo': 'Nội bộ', 'lien_he': 'Liên hệ', 'cam': 'Cấm'}
_LEVEL_FULL = {'cong_khai': 'khach', 'noi_bo': 'quan_ly', 'lien_he': 'phan_tich'}   # role thấp nhất thấy đủ
_LEVEL_MASKED = {'lien_he': 'quan_ly'}                                              # role thấp nhất thấy bản che

_audit = logging.getLogger('retail.audit')


def _rank(role: str) -> int:
    return ROLES.index(role)


def role_for(email: str | None, table) -> str:
    """Role của một email theo bảng {role: [email, ...]}. Không phân biệt hoa thường; email lạ → khách."""
    if not email:
        return 'khach'
    e = email.strip().lower()
    for role in ROLES[1:]:                        # thấp → cao: email có ở nhiều role thì lấy role thấp nhất
        if any(e == str(x).strip().lower() for x in (table.get(role) or ())):
            return role
    return 'khach'


def allowed(role: str, key: str) -> bool:
    return key in PAGES_BY_ROLE.get(role, ())


def auth_configured() -> bool:
    """Bản deploy có cấu hình đăng nhập không. Không có file secrets thì Streamlit raise, coi như không có."""
    try:
        return 'auth' in st.secrets
    except Exception:
        return False


def role_table() -> dict:
    try:
        return {k: list(v) for k, v in st.secrets['roles'].items()}
    except Exception:
        return {}


def logged_in_email() -> str | None:
    """Email đã xác minh của người đang đăng nhập; chưa đăng nhập hoặc nhà cung cấp báo email chưa xác minh → None."""
    if not auth_configured() or not st.user.get('is_logged_in'):
        return None
    if st.user.get('email_verified') is False:
        return None
    return st.user.get('email')


def real_role() -> str:
    """Role thật của người đang xem, theo đăng nhập (có [auth]) hoặc RETAIL_APP_ROLE (chạy local)."""
    if auth_configured():
        return role_for(logged_in_email(), role_table())
    r = os.environ.get('RETAIL_APP_ROLE', 'khach').strip()
    return r if r in ROLES else 'khach'


def current_role() -> str:
    """Role dùng để hiện app: role thật, trừ khi admin chọn "Xem như" một role khác. Admin là role cao nhất nên ô này chỉ
    hạ quyền; role khác chọn gì (session_state còn sót sau khi đăng xuất...) cũng bị bỏ qua."""
    real = real_role()
    xem = st.session_state.get(PREVIEW_KEY)
    return xem if real == 'admin' and xem in ROLES else real


def account_box(role: str) -> None:
    """Ô tài khoản ở thanh bên: đăng nhập/đăng xuất khi có [auth], còn chạy local thì ghi role đang dùng.
    Admin có thêm ô "Xem như role" để kiểm hoặc demo app dưới mắt từng role bằng một tài khoản."""
    box = st.sidebar.container(border=True)
    real = real_role()
    if not auth_configured():
        box.caption(f'Role: **{LABEL[real]}** (chạy local, đặt bằng `RETAIL_APP_ROLE`)')
    elif email := logged_in_email():
        box.caption(f'{email}  \nRole: **{LABEL[real]}**')
        if box.button('Đăng xuất', icon=':material/logout:'):
            st.logout()
    else:
        box.caption('Bạn đang xem với quyền **Khách**. Đăng nhập để dùng thêm chức năng theo role.')
        if box.button('Đăng nhập bằng Google', icon=':material/login:'):
            st.login()
    if real == 'admin':
        box.selectbox('Xem như role', ROLES[::-1], key=PREVIEW_KEY, format_func=LABEL.get,
                      help='Chỉ đổi cách app hiện ra cho bạn trong phiên này, không đổi quyền của ai.')
        if role != real:
            box.caption(f'Đang xem như **{LABEL[role]}**. Chọn lại Admin để về đủ quyền.')


def column_view(role: str, level: str) -> str:
    """Role thấy một cột ở mức level thế nào: 'du' (đầy đủ), 'che' (che bớt) hay 'an' (không thấy)."""
    if level in _LEVEL_FULL and _rank(role) >= _rank(_LEVEL_FULL[level]):
        return 'du'
    if level in _LEVEL_MASKED and _rank(role) >= _rank(_LEVEL_MASKED[level]):
        return 'che'
    return 'an'


def mask_contact(value) -> str | None:
    """Che số liên lạc, chỉ giữ 3 chữ số cuối: '0901234567' → '*******567'."""
    if value is None or pd.isna(value):
        return None
    digits = re.sub(r'\D', '', str(value))
    return '*' * max(len(digits) - 3, 4) + digits[-3:] if len(digits) >= 7 else '***'


def apply_levels(df: pd.DataFrame, levels: dict, role: str) -> tuple[pd.DataFrame, set]:
    """Bỏ hoặc che cột theo mức (§7.1). Cột không có trong levels bị bỏ (fail closed).
    Trả kèm các mức nhạy cảm (từ Nội bộ trở lên) mà role vừa được xem, để ghi nhật ký."""
    out, shown = {}, set()
    for col in df.columns:
        level = levels.get(col, 'cam')
        view = column_view(role, level if level in LEVELS else 'cam')
        if view == 'an':
            continue
        out[col] = df[col] if view == 'du' else df[col].map(mask_contact)
        if level != 'cong_khai':
            shown.add(level)
    return pd.DataFrame(out, index=df.index), shown


def audit(page: str, levels) -> None:
    """Nhật ký xem dữ liệu nhạy cảm (§7.4): ai, lúc nào, trang nào, mức nào. Không ghi giá trị của cột."""
    if not _audit.handlers:                     # stderr: Streamlit Cloud / Databricks Apps giữ trong log của bản deploy
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter('%(name)s %(message)s'))
        _audit.addHandler(h)
        _audit.propagate = False
    _audit.setLevel(logging.INFO)
    _audit.info(json.dumps({'ts': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                            'email': logged_in_email(), 'role': real_role(), 'xem_nhu': current_role(), 'page': page,
                            'levels': sorted(levels)}, ensure_ascii=False))


def view_frame(df: pd.DataFrame, levels: dict, page: str) -> pd.DataFrame:
    """Bảng đã lọc theo role hiện tại; có cột nhạy cảm được hiện thì ghi nhật ký. Trang hiện cột cá nhân phải đi qua đây."""
    out, shown = apply_levels(df, levels, current_role())
    if shown:
        audit(page, shown)
    return out
