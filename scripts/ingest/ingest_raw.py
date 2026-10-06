"""Ingest: 14 CSV nguồn (data/) -> schema `raw` trong PostgreSQL local.

Tầng RAW giữ nguyên nguồn: MỌI cột kiểu TEXT, tên cột đúng như header CSV, KHÔNG làm sạch
(làm sạch/ép kiểu là việc của dbt staging). Thêm 2 cột kỹ thuật:
- `_src_row`   : số thứ tự dòng trong file — line_number của dòng hàng phải theo thứ tự nguồn
                 (docs/star_schema.md §5.1), SQL không tự có thứ tự.
- `_loaded_at` : thời điểm nạp.
Mỗi lần chạy nạp lại toàn bộ (full refresh) và ghi 1 dòng/file vào `raw._ingest_log`.

Contract nguồn: header + số dòng phải đúng như scripts/build/build_silver.py; sai thì dừng, không commit transaction.

Cần: `docker compose up -d` (docker-compose.yml ở root).
Chạy từ root repo:  .venv/Scripts/python.exe scripts/ingest/ingest_raw.py
Kết nối lấy từ biến môi trường PG_HOST/PG_PORT/PG_DATABASE/PG_USER/PG_PASSWORD (mặc định khớp compose).
"""
import csv
import hashlib
import os
import sys
import time

import psycopg

DATA = 'data'
SOURCES = {  # tên file: số dòng dữ liệu kỳ vọng (không tính header) — cùng số với scripts/build/build_silver.py
    'geography': 39_948, 'customers': 121_930, 'products': 2_412, 'promotions': 50,
    'orders': 646_945, 'order_items': 714_669, 'payments': 646_945, 'shipments': 566_067,
    'returns': 39_939, 'reviews': 113_551, 'inventory': 60_247, 'web_traffic': 3_652,
    'sales': 3_833, 'sample_submission': 548,
}

conninfo = psycopg.conninfo.make_conninfo(
    host=os.getenv('PG_HOST', 'localhost'), port=os.getenv('PG_PORT', '5433'),
    dbname=os.getenv('PG_DATABASE', 'retail'), user=os.getenv('PG_USER', 'retail'),
    password=os.getenv('PG_PASSWORD', 'retail'))
q = lambda name: '"' + name.replace('"', '""') + '"'   # giữ nguyên tên cột nguồn, kể cả "Date"

with psycopg.connect(conninfo) as con:        # 1 transaction: lỗi ở đâu thì rollback toàn bộ
    con.execute('CREATE SCHEMA IF NOT EXISTS raw')
    con.execute("""CREATE TABLE IF NOT EXISTS raw._ingest_log (
                       loaded_at timestamptz NOT NULL, source text NOT NULL,
                       row_count bigint NOT NULL, file_md5 text NOT NULL, seconds numeric NOT NULL)""")
    failed = []
    for name, expected in SOURCES.items():
        t0 = time.time()
        path = f'{DATA}/{name}.csv'
        with open(path, 'rb') as f:
            md5 = hashlib.md5(f.read()).hexdigest()
        with open(path, newline='', encoding='utf-8') as f:
            header = next(csv.reader(f))
        cols = ', '.join(f'{q(c)} text' for c in header)
        # CASCADE: view staging.* của dbt phụ thuộc bảng raw; nạp lại thì bỏ view, `dbt build` ngay sau sẽ dựng lại
        con.execute(f'DROP TABLE IF EXISTS raw.{name} CASCADE')
        # identity cấp theo thứ tự COPY ghi dòng = thứ tự trong file
        con.execute(f'CREATE TABLE raw.{name} ({cols}, '
                    f'_src_row bigint GENERATED ALWAYS AS IDENTITY, _loaded_at timestamptz DEFAULT now())')
        with con.cursor() as cur, open(path, 'rb') as f:
            with cur.copy(f"COPY raw.{name} ({', '.join(q(c) for c in header)}) "
                          f"FROM STDIN WITH (FORMAT csv, HEADER true)") as cp:
                while chunk := f.read(1 << 20):
                    cp.write(chunk)
        n = con.execute(f'SELECT count(*) FROM raw.{name}').fetchone()[0]
        ok = n == expected
        failed += [] if ok else [name]
        con.execute('INSERT INTO raw._ingest_log VALUES (now(), %s, %s, %s, %s)',
                    (name, n, md5, round(time.time() - t0, 2)))
        print(f"  {'PASS' if ok else 'FAIL'}  raw.{name:18s} {n:>9,} dòng (kỳ vọng {expected:,})  {time.time() - t0:5.1f}s")
    if failed:
        con.rollback()
        print(f'\n{len(failed)} nguồn sai số dòng: {failed} — rollback, schema raw giữ nguyên như trước.')
        sys.exit(1)
print(f'\nĐã nạp {len(SOURCES)} nguồn vào schema raw. Tiếp theo: dbt build --target postgres')
