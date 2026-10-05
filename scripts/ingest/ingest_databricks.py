"""Ingest: snapshot nguồn (scripts/ingest/snapshot.py) -> schema `raw` trong Databricks (lab kiểm chứng DWH/KPI).

Hợp đồng raw và lý do đánh `_src_row` ở máy: xem docstring scripts/ingest/snapshot.py.

Upload Parquet lên Volume <catalog>.<landing_schema>.<landing_volume>/<snapshot_id>/ (mặc định raw.landing),
CREATE OR REPLACE TABLE <catalog>.raw.<nguồn>, kiểm số dòng + _src_row trên Delta. Chỉ khi cả 14 nguồn đúng mới ghi
14 dòng (cùng loaded_at, UTC) vào raw._ingest_log. Chạy lại cùng snapshot thì thay bảng, không nhân dòng.
Không tự tạo catalog (catalog phải có sẵn).

Chạy từ root repo (cần .venv-databricks: databricks-sdk, pyarrow):
  .venv-databricks/Scripts/python.exe scripts/ingest/snapshot.py
  .venv-databricks/Scripts/python.exe scripts/ingest/ingest_databricks.py --snapshot <snapshot_id>
Profile, warehouse, catalog, Volume lấy từ .env.databricks.local (DATABRICKS_CONFIG_PROFILE, DATABRICKS_WAREHOUSE_ID,
RETAIL_DATABRICKS_CATALOG, RETAIL_DATABRICKS_LANDING_SCHEMA/_VOLUME); tham số dòng lệnh cùng tên thì ghi đè.
Xác thực: profile OAuth của Databricks CLI (`databricks auth login`), không dùng PAT.
"""
import argparse
import datetime as dt
import sys
import time

from snapshot import load_manifest, local_config

q = lambda name: '`' + name.replace('`', '``') + '`'   # giữ nguyên tên cột nguồn, kể cả Date / Revenue / COGS


def load(profile, warehouse_id, catalog, landing_schema, landing_volume, snapshot_id):
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.sql import StatementState

    src, manifest = load_manifest(snapshot_id)

    w = WorkspaceClient(profile=profile)

    def sql(stmt):
        r = w.statement_execution.execute_statement(statement=stmt, warehouse_id=warehouse_id, wait_timeout='50s')
        while r.status.state in (StatementState.PENDING, StatementState.RUNNING):
            time.sleep(2)
            r = w.statement_execution.get_statement(r.statement_id)
        if r.status.state != StatementState.SUCCEEDED:
            raise RuntimeError(f'{r.status.state}: {r.status.error.message if r.status.error else ""}\n{stmt[:300]}')
        return r.result.data_array if r.result else None

    sql(f'CREATE SCHEMA IF NOT EXISTS {q(catalog)}.raw')
    sql(f'CREATE SCHEMA IF NOT EXISTS {q(catalog)}.{q(landing_schema)}')
    sql(f'CREATE VOLUME IF NOT EXISTS {q(catalog)}.{q(landing_schema)}.{q(landing_volume)}')
    sql(f"""CREATE TABLE IF NOT EXISTS {q(catalog)}.raw._ingest_log (
              loaded_at timestamp NOT NULL, source string NOT NULL, row_count bigint NOT NULL,
              file_md5 string NOT NULL, seconds double NOT NULL, snapshot_id string)""")
    vol = f'/Volumes/{catalog}/{landing_schema}/{landing_volume}/{snapshot_id}'
    loaded_at = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    log, failed = [], []
    for name, e in manifest['sources'].items():
        t0 = time.time()
        with open(f'{src}/{name}.parquet', 'rb') as f:
            w.files.upload(f'{vol}/{name}.parquet', f, overwrite=True)
        cols = ', '.join(f'cast({q(h)} as string) as {q(h)}' for h in e['header'])
        sql(f"""CREATE OR REPLACE TABLE {q(catalog)}.raw.{name} AS
                SELECT {cols}, cast(_src_row as bigint) as _src_row,
                       cast('{loaded_at}' as timestamp) as _loaded_at
                FROM read_files('{vol}/{name}.parquet', format => 'parquet')""")
        n, n_key, lo, hi = (int(x) for x in sql(
            f'SELECT count(*), count(distinct _src_row), min(_src_row), max(_src_row) FROM {q(catalog)}.raw.{name}')[0])
        ok = n == n_key == hi == e['expected'] and lo == 1   # _src_row đủ 1..n, không trùng
        failed += [] if ok else [name]
        log.append((name, n, e['csv_md5'], round(time.time() - t0, 2)))
        print(f"  {'PASS' if ok else 'FAIL'}  raw.{name:18s} {n:>9,} dòng (kỳ vọng {e['expected']:,}), "
              f"_src_row {lo}..{hi} khác nhau {n_key:,}  {time.time() - t0:5.1f}s")
    if failed:
        print(f'\n{len(failed)} nguồn sai: {failed} — KHÔNG ghi _ingest_log, đừng chạy dbt trên raw này.')
        sys.exit(1)
    values = ', '.join(f"(cast('{loaded_at}' as timestamp), '{n}', {c}, '{m}', {s}, '{snapshot_id}')" for n, c, m, s in log)
    sql(f'INSERT INTO {q(catalog)}.raw._ingest_log VALUES {values}')
    print(f'\nĐã nạp snapshot {snapshot_id} ({len(log)} nguồn) vào {catalog}.raw, loaded_at {loaded_at} UTC.')
    print('Tiếp theo: scripts/databricks/run_dbt.py build')


if __name__ == '__main__':
    c = local_config('.env.databricks.local')
    ap = argparse.ArgumentParser()
    ap.add_argument('--profile', default=c.get('DATABRICKS_CONFIG_PROFILE'))
    ap.add_argument('--warehouse-id', default=c.get('DATABRICKS_WAREHOUSE_ID'))
    ap.add_argument('--catalog', default=c.get('RETAIL_DATABRICKS_CATALOG', 'retail_lab'))
    ap.add_argument('--landing-schema', default=c.get('RETAIL_DATABRICKS_LANDING_SCHEMA', 'raw'))
    ap.add_argument('--landing-volume', default=c.get('RETAIL_DATABRICKS_LANDING_VOLUME', 'landing'))
    ap.add_argument('--snapshot', required=True)
    a = ap.parse_args()
    if not (a.profile and a.warehouse_id):
        sys.exit('Thiếu profile / warehouse id: điền DATABRICKS_CONFIG_PROFILE, DATABRICKS_WAREHOUSE_ID '
                 'trong .env.databricks.local hoặc truyền --profile / --warehouse-id.')
    load(a.profile, a.warehouse_id, a.catalog, a.landing_schema, a.landing_volume, a.snapshot)
