"""Phân quyền theo role trong app (docs/phan_quyen.md §3.1, §5, §7).

Tài khoản là username + mật khẩu do admin tạo, lưu ở Postgres riêng của app (ui/auth_store.py). Chuỗi kết nối:
biến môi trường RETAIL_APP_DB_URL, hoặc secrets
    [app_db]
    url = "postgresql://..."

Role xác định một lần mỗi lượt chạy, theo thứ tự (fail closed, §4 mục 7):
- có chuỗi kết nối: đã đăng nhập trong phiên này → role của tài khoản, đọc lại từ DB (cache 30 giây); chưa đăng nhập,
  tài khoản bị khóa / không còn, chưa đổi mật khẩu tạm, DB lỗi → khách. Lúc này RETAIL_APP_ROLE không có tác dụng;
- không có (chạy local để dev): đọc RETAIL_APP_ROLE, mặc định khách.

Phiên chỉ nằm trong session_state trên server: tải lại trang (F5) là phải đăng nhập lại (PM chấp nhận 2026-10-29).
Admin chọn được "Xem như role" ở thanh bên (chỉ hạ quyền).
"""
from collections.abc import Mapping
import datetime as dt
import json
import logging
import os
import re
import time

import pandas as pd
import streamlit as st

from ui import auth_store

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
    'gui_du_lieu': ('views/gui_du_lieu.py', 'Gửi dữ liệu'),
    'duyet_du_lieu': ('views/duyet_du_lieu.py', 'Duyệt dữ liệu'),
}

# Ma trận §3.1. Trang mới phải thêm vào đây, chưa thêm thì không role nào thấy.
_KHACH = ('tong_quan', 'ps1_do_dung', 'ps2_xu_huong', 'ps3_nhip_lich', 'ps4_don_mon_gia', 'ps5_nhom', 'du_bao')
_PAGE_CHOICES = {
    'khach': _KHACH,
    'quan_ly': _KHACH + ('ai_explain', 'gui_du_lieu'),
    'phan_tich': _KHACH + ('suc_khoe_du_lieu', 'ai_explain', 'gui_du_lieu'),
    'ky_su': _KHACH + ('suc_khoe_du_lieu', 'ai_explain', 'gui_du_lieu', 'duyet_du_lieu'),
    'admin': _KHACH + ('suc_khoe_du_lieu', 'ai_explain', 'phan_quyen', 'gui_du_lieu', 'duyet_du_lieu'),
}


class _RolePages(Mapping):
    """Ma trận luôn phản ánh cờ hiện tại, kể cả khi phiên Streamlit tải lại."""
    def __getitem__(self, role):
        pages = _PAGE_CHOICES[role]
        if os.getenv('RETAIL_APP_NHAP_DU_LIEU') != '1':
            return tuple(k for k in pages if k not in ('gui_du_lieu', 'duyet_du_lieu'))
        return pages

    def __iter__(self):
        return iter(_PAGE_CHOICES)

    def __len__(self):
        return len(_PAGE_CHOICES)


PAGES_BY_ROLE = _RolePages()
DEFAULT_PAGE = {'khach': 'tong_quan', 'quan_ly': 'tong_quan', 'phan_tich': 'ps1_do_dung',
                'ky_su': 'suc_khoe_du_lieu', 'admin': 'suc_khoe_du_lieu'}
BACKEND_ROLES = ('ky_su', 'admin')       # được đổi backend ở thanh bên
PREVIEW_KEY = 'xem_nhu_role'             # session_state của ô "Xem như role" (chỉ admin)
SESSION_KEY = 'tai_khoan'                # session_state: username đã đăng nhập trong phiên này

# Mức nhạy cảm của cột (§7.1). Cột không có mức coi như 'cam'.
LEVELS = ('cong_khai', 'noi_bo', 'lien_he', 'cam')
LEVEL_LABEL = {'cong_khai': 'Công khai', 'noi_bo': 'Nội bộ', 'lien_he': 'Liên hệ', 'cam': 'Cấm'}
_LEVEL_FULL = {'cong_khai': 'khach', 'noi_bo': 'quan_ly', 'lien_he': 'phan_tich'}   # role thấp nhất thấy đủ
_LEVEL_MASKED = {'lien_he': 'quan_ly'}                                              # role thấp nhất thấy bản che

_audit = logging.getLogger('retail.audit')


def _rank(role: str) -> int:
    return ROLES.index(role)


def allowed(role: str, key: str) -> bool:
    return key in PAGES_BY_ROLE.get(role, ())


def db_url() -> str | None:
    """Chuỗi kết nối DB tài khoản: RETAIL_APP_DB_URL, hoặc [app_db] url trong secrets. Không có file secrets thì Streamlit
    raise, coi như không có."""
    url = os.environ.get('RETAIL_APP_DB_URL', '').strip()
    if url:
        return url
    try:
        return str(st.secrets['app_db']['url']).strip() or None
    except Exception:
        return None


def auth_configured() -> bool:
    """Bản deploy có bật đăng nhập không (có DB tài khoản)."""
    return bool(db_url())


@st.cache_resource(show_spinner=False)
def _store(url: str) -> auth_store.Store:
    s = auth_store.Store(url)
    s.init()                                    # tạo schema/bảng nếu chưa có; lỗi thì không cache, lượt sau thử lại
    return s


_db_down_until = 0.0     # DB vừa lỗi thì 60 giây không thử lại: khách không phải chờ timeout kết nối ở mỗi lượt bấm


def store() -> auth_store.Store | None:
    """Kho tài khoản; None khi chưa cấu hình hoặc không kết nối được (khi đó mọi người là khách)."""
    global _db_down_until
    url = db_url()
    if not url or time.monotonic() < _db_down_until:
        return None
    try:
        return _store(url)
    except Exception:
        _db_down_until = time.monotonic() + 60
        return None


@st.cache_data(ttl=30, show_spinner=False)
def _account(url: str, username: str) -> dict | None:
    s = store()
    if s is None:
        raise RuntimeError('không kết nối được DB tài khoản')    # raise để không cache
    return s.get(username)


def logged_in_user() -> dict | None:
    """Tài khoản đang đăng nhập trong phiên, đọc lại từ DB mỗi 30 giây: admin khóa hay đổi role thì có hiệu lực nhanh.
    Tài khoản không còn / bị khóa / role lạ → bỏ phiên. DB lỗi → None (khách) nhưng giữ phiên, DB lên lại thì dùng tiếp."""
    name = st.session_state.get(SESSION_KEY)
    if not name or not auth_configured():
        return None
    try:
        u = _account(db_url(), name)
    except Exception:
        return None
    if not u or u['disabled'] or u['role'] not in ROLES[1:]:
        logout()
        return None
    return u


def logout() -> None:
    st.session_state.pop(SESSION_KEY, None)
    st.session_state.pop(PREVIEW_KEY, None)


def real_role() -> str:
    """Role thật của người đang xem, theo tài khoản đăng nhập (có DB tài khoản) hoặc RETAIL_APP_ROLE (chạy local).
    Tài khoản còn mật khẩu tạm (must_change) là khách tới khi đổi xong."""
    if auth_configured():
        u = logged_in_user()
        return u['role'] if u and not u['must_change'] else 'khach'
    r = os.environ.get('RETAIL_APP_ROLE', 'khach').strip()
    return r if r in ROLES else 'khach'


def current_role() -> str:
    """Role dùng để hiện app: role thật, trừ khi admin chọn "Xem như" một role khác. Admin là role cao nhất nên ô này chỉ
    hạ quyền; role khác chọn gì (session_state còn sót sau khi đăng xuất...) cũng bị bỏ qua."""
    real = real_role()
    xem = st.session_state.get(PREVIEW_KEY)
    return xem if real == 'admin' and xem in ROLES else real


def _login_form(box) -> None:
    s = store()
    if s is None:
        box.warning('Đăng nhập tạm không dùng được (không kết nối được cơ sở dữ liệu tài khoản). Bạn vẫn xem được với '
                    'quyền **Khách**.')
        return
    box.caption('Bạn đang xem với quyền **Khách**. Đăng nhập để dùng thêm chức năng theo role.')
    with box.expander('Đăng nhập', icon=':material/login:'):
        with st.form('dang_nhap', border=False, clear_on_submit=True):
            ten = st.text_input('Tên đăng nhập', autocomplete='username')
            mk = st.text_input('Mật khẩu', type='password', autocomplete='current-password')
            gui = st.form_submit_button('Đăng nhập')
        if gui:
            u, err = s.login(ten, mk)
            if u:
                logout()                         # bỏ trạng thái của phiên trước (Xem như role...)
                st.session_state[SESSION_KEY] = u['username']
                _account.clear()
                st.rerun()
            st.error(err)


def _change_password_form(box, username: str, *, expanded: bool) -> None:
    with box.expander('Đổi mật khẩu', icon=':material/key:', expanded=expanded):
        with st.form('doi_mat_khau', border=False, clear_on_submit=True):
            cu = st.text_input('Mật khẩu hiện tại', type='password', autocomplete='current-password')
            moi = st.text_input(f'Mật khẩu mới (ít nhất {auth_store.MIN_LEN} ký tự)', type='password',
                                autocomplete='new-password')
            lai = st.text_input('Nhập lại mật khẩu mới', type='password', autocomplete='new-password')
            gui = st.form_submit_button('Đổi mật khẩu')
        if gui:
            s = store()
            err = ('Hai lần nhập mật khẩu mới không khớp.' if moi != lai else
                   'Không kết nối được cơ sở dữ liệu tài khoản.' if s is None else s.change_password(username, cu, moi))
            if err is None:
                st.session_state['_doi_mk_xong'] = True
                _account.clear()
                st.rerun()
            st.error(err)


def account_box(role: str) -> None:
    """Ô tài khoản ở thanh bên: form đăng nhập / đổi mật khẩu / đăng xuất khi có DB tài khoản, còn chạy local thì ghi role
    đang dùng. Admin có thêm ô "Xem như role" để kiểm hoặc demo app dưới mắt từng role bằng một tài khoản."""
    box = st.sidebar.container(border=True)
    real = real_role()
    if not auth_configured():
        box.caption(f'Role: **{LABEL[real]}** (chạy local, đặt bằng `RETAIL_APP_ROLE`)')
    elif (u := logged_in_user()) is None:
        _login_form(box)
    else:
        box.caption(f'**{u["username"]}**  \nRole: **{LABEL[u["role"]]}**')
        if st.session_state.pop('_doi_mk_xong', False):
            box.success('Đã đổi mật khẩu.')
        if u['must_change']:
            box.warning('Bạn đang dùng mật khẩu tạm. Đổi mật khẩu để dùng chức năng của role.')
        _change_password_form(box, u['username'], expanded=u['must_change'])
        if box.button('Đăng xuất', icon=':material/logout:'):
            logout()
            st.rerun()
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
    u = logged_in_user()
    name = u['username'] if u else None
    _audit.info(json.dumps({'ts': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                            'user': name, 'role': real_role(), 'xem_nhu': current_role(), 'page': page,
                            'levels': sorted(levels)}, ensure_ascii=False))
    s = store()
    if s and name:                              # bản deploy: ghi thêm vào app_auth.audit (trang Phân quyền đọc lại)
        try:
            s.log(name, 'xem_nhay_cam', {'page': page, 'levels': sorted(levels), 'xem_nhu': current_role()})
        except Exception:
            pass                                # đã có dòng stderr ở trên; lỗi DB không làm hỏng trang


def view_frame(df: pd.DataFrame, levels: dict, page: str) -> pd.DataFrame:
    """Bảng đã lọc theo role hiện tại; có cột nhạy cảm được hiện thì ghi nhật ký. Trang hiện cột cá nhân phải đi qua đây."""
    out, shown = apply_levels(df, levels, current_role())
    if shown:
        audit(page, shown)
    return out
