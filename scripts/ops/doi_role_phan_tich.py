"""Đếm tài khoản DA/BI cũ; chỉ đổi khi PM truyền --doi-sang (không in danh tính hay kết nối).

Đọc RETAIL_APP_DB_URL từ môi trường. Mặc định chỉ đọc, không khởi tạo bảng.
PM chạy trước khi đưa bản mới lên cloud: --doi-sang quan_ly.
"""
import argparse
import os
from pathlib import Path
import sys

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps' / 'retail_app'))

from ui import auth_store  # noqa: E402

LEGACY_ROLE = 'phan_tich'


def run(store: auth_store.Store, doi_sang: str | None = None) -> int:
    """Trả số tài khoản cũ; cập nhật và audit cùng giao dịch để không có đổi role thiếu nhật ký."""
    if doi_sang is not None and doi_sang not in auth_store.ROLES:
        raise ValueError('Role không hợp lệ.')
    with psycopg.connect(store.url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            if doi_sang is None:
                cur.execute(sql.SQL('select count(*) from {}.users where role = %s').format(
                    sql.Identifier(store.schema)), (LEGACY_ROLE,))
                return cur.fetchone()[0]
            cur.execute(sql.SQL('update {}.users set role = %s, updated_at = now() '
                                'where role = %s returning username').format(sql.Identifier(store.schema)),
                        (doi_sang, LEGACY_ROLE))
            users = cur.fetchall()
            if users:
                cur.executemany(sql.SQL('insert into {}.audit (username, event, detail) values (%s, %s, %s)').format(
                    sql.Identifier(store.schema)),
                    [('script', 'doi_role', Jsonb({'tai_khoan': name, 'role': doi_sang})) for (name,) in users])
            return len(users)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--doi-sang', choices=auth_store.ROLES, help='chỉ ghi khi có cờ này; PM chốt quan_ly')
    args = parser.parse_args(argv)
    url = os.environ.get('RETAIL_APP_DB_URL', '').strip()
    if not url:
        parser.error('Chưa đặt RETAIL_APP_DB_URL.')
    try:
        count = run(auth_store.Store(url), args.doi_sang)
    except (psycopg.Error, ValueError):
        print('Không thực hiện được; kiểm tra kết nối và bảng tài khoản.', file=sys.stderr)
        return 1
    print(f'Số tài khoản còn role cũ: {count}' if args.doi_sang is None else f'Số tài khoản đã đổi role: {count}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
