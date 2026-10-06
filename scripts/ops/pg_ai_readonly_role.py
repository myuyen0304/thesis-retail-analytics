"""Tạo/cập nhật role PostgreSQL chỉ đọc cho AI Explain (docs/ai_explain_plan.md §0.1, §5).

Chạy từ root, bằng tài khoản quản trị của Postgres Docker local (PG_USER/PG_PASSWORD, mặc định retail/retail):

    .venv/Scripts/python.exe scripts/ops/pg_ai_readonly_role.py            # tạo role + cấp quyền
    .venv/Scripts/python.exe scripts/ops/pg_ai_readonly_role.py --check    # chỉ kiểm quyền bằng guard của app

PHẢI chạy lại sau mỗi `dbt build --target postgres`: dbt dựng lại bảng/view nên quyền SELECT cấp theo từng bảng mất.
Không dùng ALTER DEFAULT PRIVILEGES cho cả schema reporting, vì như thế role AI đọc được cả int_reporting_order_items
(dòng hàng có customer_sk, order_id). Role chỉ được SELECT đúng ai_explain.tools.ALLOWED_RELATIONS.

Tên/mật khẩu role: PG_AI_USER / PG_AI_PASSWORD; mặc định retail_ai_ro/retail_ai_ro CHỈ cho Docker local
(giống retail/retail của docker-compose.yml). Môi trường khác phải đặt biến môi trường, không dùng mặc định.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps' / 'retail_app'))

import psycopg                                   # noqa: E402
from psycopg import sql                          # noqa: E402

from ai_explain.tools import ALLOWED_RELATIONS   # noqa: E402
from dwh import guarded                          # noqa: E402

AI_USER = os.environ.get('PG_AI_USER', 'retail_ai_ro')
AI_PASSWORD = os.environ.get('PG_AI_PASSWORD', 'retail_ai_ro')


def _admin():
    return psycopg.connect(host=os.environ.get('PG_HOST', 'localhost'), port=int(os.environ.get('PG_PORT', '5433')),
                           dbname=os.environ.get('PG_DATABASE', 'retail'), user=os.environ.get('PG_USER', 'retail'),
                           password=os.environ.get('PG_PASSWORD', 'retail'), connect_timeout=5)


def apply() -> None:
    role = sql.Identifier(AI_USER)
    with _admin() as conn, conn.cursor() as cur:
        cur.execute('select 1 from pg_roles where rolname = %s', (AI_USER,))
        verb = 'alter' if cur.fetchone() else 'create'
        cur.execute(sql.SQL(verb + ' role {} login nosuperuser nocreatedb nocreaterole noinherit nobypassrls '
                            'password {}').format(role, sql.Literal(AI_PASSWORD)))
        # phòng thủ thêm ở DB; app vẫn tự đặt READ ONLY + statement_timeout cho mỗi phiên
        cur.execute(sql.SQL('alter role {} set default_transaction_read_only = on').format(role))
        cur.execute(sql.SQL("alter role {} set statement_timeout = '5s'").format(role))
        # gỡ mọi quyền bảng cũ trong reporting rồi chỉ cấp SELECT cho danh sách cho phép
        cur.execute(sql.SQL('revoke all on all tables in schema reporting from {}').format(role))
        cur.execute(sql.SQL('grant usage on schema reporting to {}').format(role))
        for rel in sorted(ALLOWED_RELATIONS):
            schema, name = rel.split('.')
            cur.execute(sql.SQL('grant select on {}.{} to {}').format(sql.Identifier(schema), sql.Identifier(name), role))
        conn.commit()
    print(f'{verb} role {AI_USER}: SELECT trên {len(ALLOWED_RELATIONS)} bảng/view reporting')


def check() -> None:
    os.environ['PG_AI_USER'], os.environ['PG_AI_PASSWORD'] = AI_USER, AI_PASSWORD
    sess = guarded.open_session('postgres', ALLOWED_RELATIONS)   # raise GuardError nếu quyền vượt
    sess.close()
    print(f'{AI_USER}: guard đạt (không superuser, không quyền ghi/tạo, chỉ SELECT danh sách cho phép)')


if __name__ == '__main__':
    # console Windows mặc định cp1252, không in được tiếng Việt (cả thông báo lỗi GuardError)
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    if '--check' not in sys.argv:
        apply()
    check()
