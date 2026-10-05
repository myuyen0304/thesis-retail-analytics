"""Nơi DUY NHẤT chọn backend đọc DWH (docs/gd2_app_plan.md §5).

Chỉ đọc, không tính toán. Mọi backend (Postgres, DuckDB, Databricks lab catalog retail_lab) trả DataFrame cùng kiểu dữ liệu
nhờ `_normalize`:
- tên cột chữ thường (Snowflake ở GĐ 3 sẽ viết hoa);
- DECIMAL → float64, số nguyên → Int64, boolean → boolean, ngày → datetime64, NULL → NA.

Mật khẩu mặc định `retail/retail` chỉ dùng cho Postgres Docker trên máy local (docker-compose.yml),
giống retail_dbt/profiles.yml; muốn đổi thì đặt biến môi trường PG_*.
"""
import datetime as dt
import os
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

BACKENDS = ('postgres', 'duckdb', 'databricks')
ROOT = Path(__file__).resolve().parents[3]                 # root repo
DUCKDB_PATH = ROOT / 'warehouse' / 'dbt.duckdb'            # do `dbt build --target duckdb` sinh ra
DATABRICKS_CONFIG = ROOT / '.env.databricks.local'         # file cá nhân (Git ignore), xem docs/dwh_huong_dan_pm_ba.md §9


def duckdb_path() -> Path:
    # RETAIL_DUCKDB_PATH cho phép trỏ sang file khác (test sửa số trên bản sao, xem tests/test_khong_hardcode.py)
    return Path(os.environ.get('RETAIL_DUCKDB_PATH', DUCKDB_PATH))


def databricks_config() -> dict:
    """Giá trị đã điền trong .env.databricks.local; trường trống bị bỏ qua, biến môi trường cùng tên được ưu tiên
    (giống scripts/ingest/snapshot.py:local_config)."""
    cfg = {}
    if DATABRICKS_CONFIG.exists():
        for line in DATABRICKS_CONFIG.read_text(encoding='utf-8').splitlines():
            k, sep, v = line.strip().partition('=')
            if sep and not k.startswith('#'):
                cfg[k.strip()] = v.strip().strip("'\"")
    keys = set(cfg) | {k for k in os.environ if k.startswith(('DATABRICKS_', 'RETAIL_DATABRICKS_'))}
    out = {k: os.environ.get(k) or cfg.get(k) for k in keys}
    return {k: v for k, v in out.items() if v}


def describe(backend: str) -> str:
    """Chỉ ra nơi app đang đọc: máy chủ/cổng/DB của Postgres, catalog Databricks, hoặc đường dẫn file DuckDB."""
    if backend == 'postgres':
        return (f"PostgreSQL {os.environ.get('PG_HOST', 'localhost')}:{os.environ.get('PG_PORT', '5433')}"
                f"/{os.environ.get('PG_DATABASE', 'retail')}")
    if backend == 'databricks':
        c = databricks_config()
        return f"Databricks catalog {c.get('RETAIL_DATABRICKS_CATALOG', 'retail_lab')} (profile {c.get('DATABRICKS_CONFIG_PROFILE', '?')})"
    p = duckdb_path()
    try:
        p = p.relative_to(ROOT)
    except ValueError:
        pass
    return f'DuckDB {p.as_posix()}'


def default_backend() -> str:
    b = os.environ.get('RETAIL_BACKEND', 'postgres').lower()
    if b not in BACKENDS:
        raise ValueError(f'RETAIL_BACKEND phải là một trong {BACKENDS}, nhận được {b!r}')
    return b


def _fetch_postgres(sql: str):
    import psycopg
    with psycopg.connect(
        host=os.environ.get('PG_HOST', 'localhost'),
        port=int(os.environ.get('PG_PORT', '5433')),
        dbname=os.environ.get('PG_DATABASE', 'retail'),
        user=os.environ.get('PG_USER', 'retail'),
        password=os.environ.get('PG_PASSWORD', 'retail'),
        connect_timeout=5,
    ) as conn, conn.cursor() as cur:
        cur.execute(sql)
        return [d.name for d in cur.description], cur.fetchall()


def _fetch_duckdb(sql: str):
    import duckdb
    # Mở chỉ-đọc rồi đóng ngay sau mỗi câu: giữ kết nối lâu sẽ khóa file, `dbt build --target duckdb` không ghi được.
    con = duckdb.connect(str(duckdb_path()), read_only=True)
    try:
        cur = con.execute(sql)
        return [d[0] for d in cur.description], cur.fetchall()
    finally:
        con.close()


_databricks_auth = None   # Config của databricks-sdk, giữ lại giữa các câu: SDK tự làm mới token OAuth khi hết hạn


def _fetch_databricks(sql: str):
    # Đăng nhập bằng profile OAuth của Databricks CLI (`databricks auth login --profile retail-dev`), không dùng PAT.
    # Catalog mặc định của phiên = retail_lab nên câu `reporting.rpt_*` dùng y như Postgres/DuckDB.
    global _databricks_auth
    from databricks import sql as dbsql
    from databricks.sdk.core import Config
    c = databricks_config()
    if not (c.get('DATABRICKS_CONFIG_PROFILE') and c.get('DATABRICKS_WAREHOUSE_ID')):
        raise RuntimeError('Thiếu DATABRICKS_CONFIG_PROFILE / DATABRICKS_WAREHOUSE_ID trong .env.databricks.local')
    if _databricks_auth is None or _databricks_auth.profile != c['DATABRICKS_CONFIG_PROFILE']:
        _databricks_auth = Config(profile=c['DATABRICKS_CONFIG_PROFILE'])
    token = _databricks_auth.authenticate()['Authorization'].removeprefix('Bearer ')
    with dbsql.connect(server_hostname=_databricks_auth.host.removeprefix('https://').rstrip('/'),
                       http_path=f"/sql/1.0/warehouses/{c['DATABRICKS_WAREHOUSE_ID']}", access_token=token,
                       catalog=c.get('RETAIL_DATABRICKS_CATALOG', 'retail_lab')) as conn, conn.cursor() as cur:
        cur.execute(sql)
        # TIMESTAMP của Databricks về Python kèm múi giờ (UTC); Postgres/DuckDB trả giờ UTC không múi → bỏ múi cho giống
        utc = lambda v: v.astimezone(dt.timezone.utc).replace(tzinfo=None) \
            if isinstance(v, dt.datetime) and v.tzinfo else v
        return [d[0] for d in cur.description], [tuple(utc(v) for v in r) for r in cur.fetchall()]


def _normalize_column(values: list) -> pd.Series:
    present = [v for v in values if v is not None]
    if not present:
        return pd.Series(values, dtype='float64')
    kinds = {type(v) for v in present}
    if kinds <= {bool}:
        return pd.Series(values, dtype='boolean')
    if kinds <= {int}:
        return pd.Series(values, dtype='Int64')
    if kinds <= {int, float, Decimal}:
        return pd.Series([np.nan if v is None else float(v) for v in values], dtype='float64')
    if kinds <= {dt.date}:
        return pd.to_datetime(pd.Series(values))
    if kinds <= {dt.datetime} and all(v.tzinfo is None for v in present):   # timestamp không múi giờ (rpt_build_info)
        return pd.to_datetime(pd.Series(values))
    if kinds <= {str}:
        return pd.Series(values, dtype='str')
    raise TypeError(f'Kiểu chưa hỗ trợ: {kinds}')


def _normalize(cols: list[str], rows: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame({
        c.lower(): _normalize_column([r[i] for r in rows]) for i, c in enumerate(cols)
    })


def read_sql(sql: str, backend: str) -> pd.DataFrame:
    if backend == 'postgres':
        cols, rows = _fetch_postgres(sql)
    elif backend == 'duckdb':
        cols, rows = _fetch_duckdb(sql)
    elif backend == 'databricks':
        cols, rows = _fetch_databricks(sql)
    else:
        raise ValueError(f'Backend không hỗ trợ: {backend!r}')
    return _normalize(cols, rows)
