"""Tạo tài khoản admin đầu tiên của app, hoặc đặt lại mật khẩu admin (docs/phan_quyen.md §5). PM tự chạy ở máy.

Các tài khoản khác do admin tạo trên trang Phân quyền của app; script này chỉ để có admin đầu tiên hoặc cứu admin quên
mật khẩu. Mật khẩu nhập qua getpass (không hiện, không nằm trong lịch sử lệnh).

    # DB tài khoản của bản public (Neon): dán chuỗi kết nối vào biến môi trường, không dán vào lệnh
    $env:RETAIL_APP_DB_URL = '<chuỗi kết nối Neon>'
    .venv/Scripts/python.exe scripts/ops/tao_admin.py --username uyen
    # Postgres Docker local
    .venv/Scripts/python.exe scripts/ops/tao_admin.py --username uyen --local
    # admin quên mật khẩu
    .venv/Scripts/python.exe scripts/ops/tao_admin.py --username uyen --dat-lai
"""
import argparse
import getpass
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps' / 'retail_app'))

from psycopg.conninfo import conninfo_to_dict  # noqa: E402

from ui import auth_store  # noqa: E402

LOCAL = (f"postgresql://{os.environ.get('PG_USER', 'retail')}:{os.environ.get('PG_PASSWORD', 'retail')}"
         f"@{os.environ.get('PG_HOST', 'localhost')}:{os.environ.get('PG_PORT', '5433')}"
         f"/{os.environ.get('PG_DATABASE', 'retail')}")


def run(store: auth_store.Store, username: str, password: str, dat_lai: bool) -> str | None:
    """Lỗi (câu tiếng Việt) hoặc None nếu xong. Không đặt lại được tài khoản không phải admin."""
    store.init()
    u = store.get(username)
    if dat_lai:
        if u is None or u['role'] != 'admin':
            return f'Không có admin {auth_store.normalize(username)!r} để đặt lại.'
        err = store.reset_password(username, password, 'tao_admin.py', must_change=False)
        return err or (store.set_disabled(username, False, 'tao_admin.py') if u['disabled'] else None)
    if store.count_admins():
        return 'Đã có admin. Tạo thêm tài khoản trên trang Phân quyền; quên mật khẩu admin thì chạy lại với --dat-lai.'
    if u is not None:
        return 'Tên đăng nhập đã có (không phải admin). Chọn tên khác.'
    return store.create(username, 'admin', password, 'tao_admin.py', must_change=False)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--username', required=True)
    p.add_argument('--dat-lai', action='store_true', help='đặt lại mật khẩu cho admin đã có')
    p.add_argument('--local', action='store_true', help='dùng Postgres Docker local thay cho RETAIL_APP_DB_URL')
    args = p.parse_args(argv)

    url = LOCAL if args.local else os.environ.get('RETAIL_APP_DB_URL', '').strip()
    if not url:
        p.error('chưa đặt biến môi trường RETAIL_APP_DB_URL (hoặc thêm --local)')
    if err := auth_store.check_username(args.username):
        p.error(err)
    print(f'DB tài khoản: {conninfo_to_dict(url).get("host")} (schema app_auth)')    # chỉ in host, không in mật khẩu DB

    pw = getpass.getpass('Mật khẩu admin: ')
    if err := auth_store.check_password(pw, args.username):
        print(err, file=sys.stderr)
        return 1
    if getpass.getpass('Nhập lại: ') != pw:
        print('Hai lần nhập không khớp.', file=sys.stderr)
        return 1
    if err := run(auth_store.Store(url), args.username, pw, args.dat_lai):
        print(err, file=sys.stderr)
        return 1
    print(f'Xong: admin {auth_store.normalize(args.username)!r} đăng nhập được trên app.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
