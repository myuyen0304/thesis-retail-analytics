"""Ingest: snapshot nguồn (scripts/ingest/snapshot.py) -> schema RAW trong Snowflake (đích production / demo khóa luận).

Hợp đồng raw và lý do đánh `_src_row` ở máy: xem docstring scripts/ingest/snapshot.py. Snowflake và Databricks nạp CÙNG
snapshot Parquet nên `_src_row` (và vì vậy line_number) giống hệt local.

Từng nguồn: PUT Parquet lên stage RAW.LANDING/<snapshot_id>/ → CREATE OR REPLACE TABLE RAW.<nguồn> AS SELECT từ stage
(thay cả bảng trong một lệnh, chạy lại không nhân dòng; không dùng COPY INTO vì COPY nhớ file đã nạp và lặng lẽ bỏ qua)
→ kiểm số dòng + _src_row đủ 1..n. Chỉ khi cả 14 nguồn đúng mới ghi 14 dòng (cùng loaded_at, UTC) vào RAW._INGEST_LOG.

Tên cột: Snowflake đổi tên không quote sang CHỮ HOA, tên quote thì phân biệt hoa/thường. Staging gọi `Date`, `Revenue`,
`COGS` (sales, sample_submission) và `date` (web_traffic) qua adapter.quote → tạo ĐÚNG các cột đó có quote; cột khác không
quote để `order_id` trong staging khớp ORDER_ID.

Cần: account đã chạy scripts/snowflake/bootstrap.sql; .env.snowflake.local đã điền SNOWFLAKE_ACCOUNT.
Chạy từ root repo:
  .venv/Scripts/python.exe scripts/ingest/snapshot.py
  .venv/Scripts/python.exe scripts/ingest/ingest_snowflake.py --snapshot <snapshot_id>
"""
import argparse
import datetime as dt
import os
import sys
import time

import snowflake.connector

from snapshot import load_manifest, local_config


def ident(h):
    return f'"{h}"' if h != h.lower() or h == 'date' else h


def connect(c):
    missing = [k for k in ('SNOWFLAKE_ACCOUNT', 'SNOWFLAKE_USER', 'SNOWFLAKE_PRIVATE_KEY_PATH') if not c.get(k)]
    if missing:
        sys.exit(f'Thiếu {missing} trong .env.snowflake.local — chạy scripts/snowflake/bootstrap.py rồi điền.')
    return snowflake.connector.connect(
        account=c['SNOWFLAKE_ACCOUNT'], user=c['SNOWFLAKE_USER'],
        private_key_file=os.path.expanduser(c['SNOWFLAKE_PRIVATE_KEY_PATH']),
        role=c.get('SNOWFLAKE_ROLE', 'TRANSFORMER'), warehouse=c.get('SNOWFLAKE_WAREHOUSE', 'TRANSFORM_WH'),
        database=c.get('SNOWFLAKE_DATABASE', 'RETAIL'), session_parameters={'TIMEZONE': 'UTC'})


def load(c, snapshot_id):
    src, manifest = load_manifest(snapshot_id)
    con = connect(c)
    cur = con.cursor()
    sql = lambda stmt: cur.execute(stmt).fetchall()

    sql('CREATE SCHEMA IF NOT EXISTS RAW')
    sql('CREATE STAGE IF NOT EXISTS RAW.LANDING')
    sql('CREATE FILE FORMAT IF NOT EXISTS RAW.PARQUET_FMT TYPE = PARQUET')
    sql("""CREATE TABLE IF NOT EXISTS RAW._INGEST_LOG (
               loaded_at timestamp_ntz NOT NULL, source varchar NOT NULL, row_count bigint NOT NULL,
               file_md5 varchar NOT NULL, seconds float NOT NULL, snapshot_id varchar)""")
    loaded_at = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    log, failed = [], []
    for name, e in manifest['sources'].items():
        t0 = time.time()
        path = os.path.abspath(f'{src}/{name}.parquet').replace('\\', '/')
        sql(f"PUT 'file://{path}' @RAW.LANDING/{snapshot_id}/ AUTO_COMPRESS = FALSE OVERWRITE = TRUE")
        cols = ', '.join(f'$1:"{h}"::varchar as {ident(h)}' for h in e['header'])
        sql(f"""CREATE OR REPLACE TABLE RAW.{name} AS
                SELECT {cols}, $1:"_src_row"::bigint as _src_row, '{loaded_at}'::timestamp_ntz as _loaded_at
                FROM @RAW.LANDING/{snapshot_id}/{name}.parquet (FILE_FORMAT => 'RAW.PARQUET_FMT')""")
        n, n_key, lo, hi = sql(f'SELECT count(*), count(distinct _src_row), min(_src_row), max(_src_row) FROM RAW.{name}')[0]
        ok = n == n_key == hi == e['expected'] and lo == 1   # _src_row đủ 1..n, không trùng
        failed += [] if ok else [name]
        log.append((name, n, e['csv_md5'], round(time.time() - t0, 2)))
        print(f"  {'PASS' if ok else 'FAIL'}  RAW.{name:18s} {n:>9,} dòng (kỳ vọng {e['expected']:,}), "
              f"_src_row {lo}..{hi} khác nhau {n_key:,}  {time.time() - t0:5.1f}s")
    if failed:
        print(f'\n{len(failed)} nguồn sai: {failed} — KHÔNG ghi _INGEST_LOG, đừng chạy dbt trên raw này.')
        sys.exit(1)
    cur.executemany('INSERT INTO RAW._INGEST_LOG VALUES (%s::timestamp_ntz, %s, %s, %s, %s, %s)',
                    [(loaded_at, name, n, md5, secs, snapshot_id) for name, n, md5, secs in log])
    con.close()
    print(f'\nĐã nạp snapshot {snapshot_id} ({len(log)} nguồn) vào RETAIL.RAW, loaded_at {loaded_at} UTC.')
    print('Tiếp theo: .venv/Scripts/python.exe scripts/snowflake/run_dbt.py build')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--snapshot', required=True)
    load(local_config('.env.snowflake.local'), ap.parse_args().snapshot)
