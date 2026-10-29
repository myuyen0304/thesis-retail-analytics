"""Tài khoản đăng nhập của app (docs/phan_quyen.md §5): username + mật khẩu do admin tạo.

Lưu ở Postgres riêng của app, schema `app_auth`: bản public dùng Neon, local dùng Postgres Docker. Đây không phải DWH,
Databricks vẫn là kho dữ liệu duy nhất. Module này không import streamlit để script `scripts/ops/tao_admin.py` dùng lại được.

Mật khẩu chỉ lưu dạng băm scrypt (thư viện chuẩn), salt riêng từng tài khoản. Không hàm nào trả hash ra ngoài module;
nhật ký không bao giờ chứa mật khẩu hay hash.
"""
import datetime as dt
import hashlib
import hmac
import re
import secrets

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

ROLES = ('quan_ly', 'phan_tich', 'ky_su', 'admin')   # role gán được cho tài khoản; khách là người không đăng nhập
MIN_LEN = 10
MAX_FAIL = 5                                        # sai liên tiếp từng này lần thì khóa
LOCK = dt.timedelta(minutes=15)
SAI = 'Sai tên đăng nhập hoặc mật khẩu.'            # cùng một câu cho username lạ và sai mật khẩu: không dò được ai có thật
_USERNAME = re.compile(r'^[a-z0-9._-]{3,32}$')
_N, _R, _P = 2 ** 14, 8, 1
_PUBLIC = 'username, role, must_change, disabled, locked_until, last_login, created_at, created_by'   # không có pw_hash

_DDL = """
create schema if not exists {s};
create table if not exists {s}.users (
    username text primary key,
    role text not null,
    pw_hash text not null,
    must_change boolean not null default true,
    disabled boolean not null default false,
    failed integer not null default 0,
    locked_until timestamptz,
    last_login timestamptz,
    created_at timestamptz not null default now(),
    created_by text,
    updated_at timestamptz not null default now()
);
create table if not exists {s}.audit (
    id bigserial primary key,
    ts timestamptz not null default now(),
    username text,
    event text not null,
    detail jsonb
);
"""


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P)
    return f'scrypt${_N}${_R}${_P}${salt.hex()}${h.hex()}'


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, h = stored.split('$')
        if algo != 'scrypt':
            return False
        got = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(got, bytes.fromhex(h))
    except (ValueError, AttributeError):
        return False


_DUMMY = hash_password(secrets.token_urlsafe(16))    # username lạ vẫn tốn một lần băm, thời gian trả lời như username thật


def normalize(username: str) -> str:
    return (username or '').strip().lower()


def check_username(username: str) -> str | None:
    if not _USERNAME.match(normalize(username)):
        return 'Tên đăng nhập 3–32 ký tự, chỉ gồm chữ thường không dấu, số, dấu chấm, gạch dưới, gạch ngang.'
    return None


def check_password(password: str, username: str) -> str | None:
    if len(password or '') < MIN_LEN:
        return f'Mật khẩu phải có ít nhất {MIN_LEN} ký tự.'
    if normalize(username) in password.lower():
        return 'Mật khẩu không được chứa tên đăng nhập.'
    return None


def temp_password() -> str:
    """Mật khẩu tạm admin gửi cho người dùng; người dùng phải đổi ở lần đăng nhập đầu."""
    return secrets.token_urlsafe(9)                   # 12 ký tự


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Store:
    """Mỗi thao tác mở một kết nối ngắn (Neon tự ngủ khi không ai dùng, giữ kết nối lâu sẽ bị cắt)."""

    def __init__(self, url: str, schema: str = 'app_auth'):
        self.url = url
        self.schema = schema

    def _run(self, query: str, params=(), *, fetch: str | None = None):
        with psycopg.connect(self.url, connect_timeout=5, autocommit=True, row_factory=dict_row) as conn:
            cur = conn.execute(sql.SQL(query).format(s=sql.Identifier(self.schema)), params)
            if fetch == 'one':
                return cur.fetchone()
            if fetch == 'all':
                return cur.fetchall()
            return None

    def init(self) -> None:
        self._run(_DDL)

    # --- đọc ---

    def get(self, username: str) -> dict | None:
        return self._run(f'select {_PUBLIC} from {{s}}.users where username = %s', (normalize(username),), fetch='one')

    def list_users(self) -> list[dict]:
        return self._run(f'select {_PUBLIC} from {{s}}.users order by role desc, username', fetch='all')

    def count_admins(self) -> int:
        row = self._run("select count(*) as n from {s}.users where role = 'admin' and not disabled", fetch='one')
        return row['n']

    def recent_log(self, limit: int = 50) -> list[dict]:
        return self._run('select ts, username, event, detail from {s}.audit order by id desc limit %s', (limit,),
                         fetch='all')

    def log(self, username: str | None, event: str, detail: dict | None = None) -> None:
        self._run('insert into {s}.audit (username, event, detail) values (%s, %s, %s)',
                  (username, event, Jsonb(detail or {})))

    # --- đăng nhập ---

    def login(self, username: str, password: str, now: dt.datetime | None = None) -> tuple[dict | None, str | None]:
        """(tài khoản, None) nếu đúng; (None, câu báo lỗi) nếu sai. Sai MAX_FAIL lần liên tiếp thì khóa LOCK."""
        now = now or _now()
        u = normalize(username)[:64]
        row = self._run('select pw_hash, failed, locked_until, disabled from {s}.users where username = %s', (u,),
                        fetch='one')
        if row is None:
            verify_password(password, _DUMMY)
            self.log(u, 'login_fail', {'ly_do': 'khong_co'})
            return None, SAI
        if row['locked_until'] and row['locked_until'] > now:
            verify_password(password, _DUMMY)
            phut = max(1, round((row['locked_until'] - now).total_seconds() / 60))
            self.log(u, 'login_fail', {'ly_do': 'dang_khoa'})
            return None, f'Tài khoản tạm khóa vì nhập sai nhiều lần. Thử lại sau khoảng {phut} phút.'
        if not verify_password(password, row['pw_hash']):
            failed = row['failed'] + 1
            if failed >= MAX_FAIL:
                self._run('update {s}.users set failed = 0, locked_until = %s where username = %s', (now + LOCK, u))
                self.log(u, 'locked', {'so_lan_sai': failed})
            else:
                self._run('update {s}.users set failed = %s where username = %s', (failed, u))
                self.log(u, 'login_fail', {'ly_do': 'sai_mat_khau'})
            return None, SAI
        if row['disabled']:                       # chỉ báo bị khóa khi mật khẩu đúng: người lạ không biết tài khoản có thật
            self.log(u, 'login_fail', {'ly_do': 'vo_hieu'})
            return None, 'Tài khoản đã bị admin khóa. Liên hệ admin.'
        self._run('update {s}.users set failed = 0, locked_until = null, last_login = %s where username = %s', (now, u))
        self.log(u, 'login_ok')
        return self.get(u), None

    def change_password(self, username: str, old: str, new: str) -> str | None:
        u = normalize(username)
        row = self._run('select pw_hash from {s}.users where username = %s', (u,), fetch='one')
        if row is None or not verify_password(old, row['pw_hash']):
            return 'Mật khẩu hiện tại không đúng.'
        if old == new:
            return 'Mật khẩu mới phải khác mật khẩu hiện tại.'
        if err := check_password(new, u):
            return err
        self._run('update {s}.users set pw_hash = %s, must_change = false, updated_at = now() where username = %s',
                  (hash_password(new), u))
        self.log(u, 'doi_mk')
        return None

    # --- admin ---

    def create(self, username: str, role: str, password: str, by: str | None, *, must_change: bool = True) -> str | None:
        u = normalize(username)
        if err := check_username(u) or check_password(password, u):
            return err
        if role not in ROLES:
            return f'Role không hợp lệ: {role!r}.'
        row = self._run('insert into {s}.users (username, role, pw_hash, must_change, created_by) values (%s, %s, %s, %s, %s) '
                        'on conflict (username) do nothing returning username',
                        (u, role, hash_password(password), must_change, by), fetch='one')
        if row is None:
            return 'Tên đăng nhập đã có.'
        self.log(by, 'tao_tk', {'tai_khoan': u, 'role': role})
        return None

    def _guard(self, username: str, by: str | None, *, drops_admin: bool) -> str | None:
        """Admin không tự khóa/tự hạ mình, và không bao giờ để hệ thống hết admin còn hoạt động."""
        target = self.get(username)
        if target is None:
            return 'Không có tài khoản này.'
        if normalize(by or '') == target['username']:
            return 'Không tự khóa hay tự đổi role của chính mình.'
        if drops_admin and target['role'] == 'admin' and not target['disabled'] and self.count_admins() <= 1:
            return 'Đây là admin cuối cùng còn hoạt động.'
        return None

    def set_role(self, username: str, role: str, by: str | None) -> str | None:
        if role not in ROLES:
            return f'Role không hợp lệ: {role!r}.'
        u = normalize(username)
        if err := self._guard(u, by, drops_admin=role != 'admin'):
            return err
        self._run('update {s}.users set role = %s, updated_at = now() where username = %s', (role, u))
        self.log(by, 'doi_role', {'tai_khoan': u, 'role': role})
        return None

    def set_disabled(self, username: str, disabled: bool, by: str | None) -> str | None:
        u = normalize(username)
        if err := self._guard(u, by, drops_admin=disabled):
            return err
        self._run('update {s}.users set disabled = %s, failed = 0, locked_until = null, updated_at = now() '
                  'where username = %s', (disabled, u))
        self.log(by, 'khoa' if disabled else 'mo_khoa', {'tai_khoan': u})
        return None

    def reset_password(self, username: str, password: str, by: str | None, *, must_change: bool = True) -> str | None:
        """Đặt mật khẩu mới (mật khẩu tạm; must_change=False chỉ dùng cho scripts/ops/tao_admin.py), mở khóa do nhập sai."""
        u = normalize(username)
        if self.get(u) is None:
            return 'Không có tài khoản này.'
        if err := check_password(password, u):
            return err
        self._run('update {s}.users set pw_hash = %s, must_change = %s, failed = 0, locked_until = null, updated_at = now() '
                  'where username = %s', (hash_password(password), must_change, u))
        self.log(by, 'dat_lai_mk', {'tai_khoan': u})
        return None
