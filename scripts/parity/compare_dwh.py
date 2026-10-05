"""Đối soát DWH trên cloud (Snowflake / Databricks) với bản DuckDB local (warehouse/dbt.duckdb), từng dòng, mọi bảng
marts + reporting (kể cả seed). Bỏ qua rpt_health_* và rpt_build_info: nhật ký chạy, khác nhau theo bản chất.

Cách so mỗi bảng:
  1. Số dòng, tập cột (tên cột chuẩn hóa chữ thường — Snowflake trả CHỮ HOA).
  2. Sắp hai bên theo "khóa" = các cột không phải số thực ở cả hai bên; báo nếu khóa không duy nhất trong baseline.
  3. So từng ô:
     - hai bên decimal/integer/chuỗi/ngày/bool: phải bằng CHÍNH XÁC (decimal so theo giá trị, bỏ khác biệt scale 1.50 = 1.5);
     - một bên decimal, một bên float (vd. phép chia: DuckDB ra DOUBLE, Snowflake ra NUMBER scale ≥ 6): lệch ≤ 1 đơn vị
       ở chữ số cuối của bên decimal — đúng bằng sai số làm tròn của bên đó;
     - hai bên float: lệch tương đối ≤ 1e-12 — chỉ cho phép khác thứ tự cộng khi engine chạy song song.
  Không làm tròn số để "cho khớp"; mọi lệch đều in ra cột, số ô lệch và ví dụ.

Chạy từ root repo (baseline phải build từ đúng revision code đang deploy):
  .venv/Scripts/python.exe scripts/parity/compare_dwh.py snowflake
  .venv-databricks/Scripts/python.exe scripts/parity/compare_dwh.py databricks   (cần duckdb trong .venv-databricks)
  .venv/Scripts/python.exe scripts/parity/compare_dwh.py postgres   (kiểm chéo hai engine local, PG_* như ingest_raw.py)
  .venv/Scripts/python.exe scripts/parity/compare_dwh.py duckdb --path <bản sao .duckdb>   (tự kiểm script)
Thoát mã 1 nếu có bảng lệch.
"""
import argparse
import datetime as dt
import decimal
import math
import os
import sys

import duckdb

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ingest'))
from snapshot import local_config  # noqa: E402

BASELINE = 'warehouse/dbt.duckdb'
SCHEMAS = ('marts', 'reporting')
SKIP = lambda t: t.startswith('rpt_health_') or t == 'rpt_build_info'


def tables(con):
    return con.execute(f"""select table_schema, table_name from information_schema.tables
                           where table_schema in {SCHEMAS} order by 1, 2""").fetchall()


def duckdb_fetch(path):
    con = duckdb.connect(path, read_only=True)

    def fetch(schema, table):
        cur = con.execute(f'select * from {schema}.{table}')
        return [d[0].lower() for d in cur.description], cur.fetchall()
    return fetch


def snowflake_fetch():
    import snowflake.connector
    c = local_config('.env.snowflake.local')
    con = snowflake.connector.connect(
        account=c['SNOWFLAKE_ACCOUNT'], user=c.get('SNOWFLAKE_USER', 'RETAIL_DBT'),
        private_key_file=os.path.expanduser(c['SNOWFLAKE_PRIVATE_KEY_PATH']),
        role=c.get('SNOWFLAKE_ROLE', 'TRANSFORMER'), warehouse=c.get('SNOWFLAKE_WAREHOUSE', 'TRANSFORM_WH'),
        database=c.get('SNOWFLAKE_DATABASE', 'RETAIL'), session_parameters={'TIMEZONE': 'UTC'})

    def fetch(schema, table):
        cur = con.cursor().execute(f'select * from {schema}.{table}')
        return [d[0].lower() for d in cur.description], cur.fetchall()
    return fetch


def databricks_fetch():
    from databricks import sql as dbsql
    from databricks.sdk.core import Config
    c = local_config('.env.databricks.local')
    cfg = Config(profile=c['DATABRICKS_CONFIG_PROFILE'])
    token = cfg.authenticate()['Authorization'].removeprefix('Bearer ')
    con = dbsql.connect(server_hostname=cfg.host.removeprefix('https://').rstrip('/'),
                        http_path=f"/sql/1.0/warehouses/{c['DATABRICKS_WAREHOUSE_ID']}", access_token=token)
    catalog = c.get('RETAIL_DATABRICKS_CATALOG', 'retail_lab')

    def fetch(schema, table):
        cur = con.cursor()
        cur.execute(f'select * from `{catalog}`.`{schema}`.`{table}`')
        return [d[0].lower() for d in cur.description], [tuple(r) for r in cur.fetchall()]
    return fetch


def postgres_fetch():
    import psycopg
    con = psycopg.connect(host=os.getenv('PG_HOST', 'localhost'), port=os.getenv('PG_PORT', '5433'),
                          dbname=os.getenv('PG_DATABASE', 'retail'), user=os.getenv('PG_USER', 'retail'),
                          password=os.getenv('PG_PASSWORD', 'retail'))

    def fetch(schema, table):
        cur = con.execute(f'select * from {schema}.{table}')
        return [d.name.lower() for d in cur.description], cur.fetchall()
    return fetch


def is_float(v):
    return isinstance(v, float)


def key_value(v):
    """Giá trị dùng để sắp: cùng kiểu so được giữa hai engine."""
    if v is None:
        return (0, '')
    if isinstance(v, bool):
        return (1, int(v))
    if isinstance(v, (int, decimal.Decimal)):
        return (2, decimal.Decimal(v).normalize())
    if isinstance(v, dt.datetime):
        return (3, v.replace(tzinfo=None).isoformat())
    if isinstance(v, dt.date):
        return (3, v.isoformat())
    return (4, str(v))


def same(a, b):
    """(khớp?, độ lệch) theo quy tắc ở docstring."""
    if a is None or b is None:
        return a is None and b is None, None
    if is_float(a) or is_float(b):
        if isinstance(a, bool) or isinstance(b, bool):
            return False, None
        fa, fb = float(a), float(b)
        if math.isnan(fa) or math.isnan(fb):
            return math.isnan(fa) and math.isnan(fb), None
        diff = abs(fa - fb)
        if is_float(a) and is_float(b):
            return diff <= 1e-12 * max(abs(fa), abs(fb), 1.0), diff
        d = a if isinstance(a, decimal.Decimal) else b if isinstance(b, decimal.Decimal) else decimal.Decimal(0)
        exp = d.as_tuple().exponent if isinstance(d, decimal.Decimal) else 0
        return diff <= 10.0 ** exp * (1 + 1e-9), diff
    exact = lambda v: isinstance(v, (int, decimal.Decimal)) and not isinstance(v, bool)
    diff = float(abs(decimal.Decimal(a) - decimal.Decimal(b))) if exact(a) and exact(b) else None
    return key_value(a) == key_value(b), diff


def compare(name, base, other):
    (bc, br), (oc, orows) = base, other
    problems = []
    if set(bc) != set(oc):
        return [f'cột khác nhau: thiếu {sorted(set(bc) - set(oc))}, thừa {sorted(set(oc) - set(bc))}']
    if len(br) != len(orows):
        problems.append(f'số dòng {len(orows):,} ≠ baseline {len(br):,}')
    oi = [oc.index(c) for c in bc]
    orows = [tuple(r[i] for i in oi) for r in orows]
    # khóa = cột không phải float ở mọi dòng của cả hai bên
    keys = [j for j in range(len(bc)) if not any(is_float(r[j]) for r in br) and not any(is_float(r[j]) for r in orows)]
    # khóa = tiền tố ngắn nhất của các cột đó đã duy nhất trong baseline (thường là surrogate key / grain ở cột đầu),
    # để ô tiền bị lệch hiện thành "ô lệch" chứ không thành "dòng thiếu + dòng thừa"
    for n in range(1, len(keys) + 1):
        if len({tuple(key_value(r[j]) for j in keys[:n]) for r in br}) == len(br):
            keys = keys[:n]
            break
    sk = lambda r: tuple(key_value(r[j]) for j in keys)
    show = lambda k: {bc[j]: v[1] for j, v in zip(keys[:3], k)}
    bmap, omap = {sk(r): r for r in br}, {sk(r): r for r in orows}
    if len(bmap) == len(br) and len(omap) == len(orows):   # khóa duy nhất: ghép theo khóa, chỉ ra đúng dòng thiếu/thừa
        missing, extra = bmap.keys() - omap.keys(), omap.keys() - bmap.keys()
        if missing:
            problems.append(f'{len(missing):,} dòng thiếu trên cloud, ví dụ {show(min(missing))}')
        if extra:
            problems.append(f'{len(extra):,} dòng thừa trên cloud, ví dụ {show(min(extra))}')
        pairs = [(bmap[k], omap[k]) for k in sorted(bmap.keys() & omap.keys())]
    else:
        problems.append(f'khóa {[bc[j] for j in keys]} không duy nhất — so theo thứ tự sắp, có thể báo lệch giả')
        pairs = list(zip(sorted(br, key=sk), sorted(orows, key=sk)))
    bad = {}
    for rb, ro in pairs:
        for j, c in enumerate(bc):
            ok, diff = same(rb[j], ro[j])
            if not ok:
                n, worst, ex = bad.get(c, (0, 0.0, None))
                bad[c] = (n + 1, max(worst, diff or 0.0), ex or (rb[j], ro[j], {bc[k]: rb[k] for k in keys[:3]}))
    for c, (n, worst, ex) in bad.items():
        problems.append(f'cột {c}: {n:,} ô lệch, lệch lớn nhất {worst:g}; ví dụ baseline={ex[0]!r} cloud={ex[1]!r} tại {ex[2]}')
    return problems


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('target', choices=['snowflake', 'databricks', 'postgres', 'duckdb'])
    ap.add_argument('--path', help='chỉ với target duckdb: file .duckdb cần so')
    ap.add_argument('--baseline', default=BASELINE)
    ap.add_argument('--tables', nargs='*', help='chỉ so các bảng này (tên không kèm schema)')
    a = ap.parse_args()
    base_con = duckdb.connect(a.baseline, read_only=True)
    todo = [(s, t) for s, t in tables(base_con) if not SKIP(t) and (not a.tables or t in a.tables)]
    base_con.close()
    base = duckdb_fetch(a.baseline)
    other = {'snowflake': snowflake_fetch, 'databricks': databricks_fetch, 'postgres': postgres_fetch,
             'duckdb': lambda: duckdb_fetch(a.path)}[a.target]()
    n_bad = 0
    for s, t in todo:
        try:
            problems = compare(f'{s}.{t}', base(s, t), other(s, t))
        except Exception as e:   # bảng thiếu trên cloud, lỗi quyền...
            problems = [f'không đọc được: {type(e).__name__}: {str(e)[:200]}']
        n_bad += bool(problems)
        print(f"  {'PASS' if not problems else 'FAIL'}  {s}.{t}")
        for p in problems:
            print(f'        {p}')
    print(f'\n{len(todo) - n_bad}/{len(todo)} bảng khớp baseline {a.baseline} (target {a.target}).')
    sys.exit(1 if n_bad else 0)
