"""Hợp đồng dữ liệu bản gọn (A3, bước S4, 2026-10-19): kiểm kiểu, not-null và khóa chính trên snapshot ở stage prepare.

Luật kiểm dùng đúng biểu thức của staging: `try_cast(nullif(trim(col), '') as <kiểu>)` chạy bằng DuckDB trên parquet của
snapshot, nên giá trị qua được hợp đồng thì cũng cast được ở staging. Khóa ngoại để dbt test lo như hiện nay.

Gặp dòng sai thì KHÔNG bỏ dòng rồi chạy tiếp (bỏ dòng làm lệch đối soát G/COGS với sales, CLAUDE.md §5 điểm 1) và không sửa
hay khử dòng lỗi (§5 điểm 8): ghi bằng chứng vào thư mục quarantine của run rồi dừng; CLI trả exit 2, Airflow không retry.
"""
import csv
import json
from pathlib import Path

from scripts.ingest.source_contract import COLUMNS, KEYS

SAMPLE = 1000          # số dòng sai ghi vào quarantine cho mỗi lý do; tổng số dòng sai vẫn đếm đủ trong summary.json


def _value(col):
    return f'nullif(trim("{col}"), \'\')'


def _checks(cols, key):
    """[(điều kiện SQL chọn dòng sai, lý do, cột)] cho một nguồn."""
    out = []
    for col, (kind, nullable) in cols.items():
        if not nullable:
            out.append((f'{_value(col)} is null', f'rỗng ở cột không được rỗng {col}', col))
        if kind != 'string':
            out.append((f'{_value(col)} is not null and try_cast({_value(col)} as {kind}) is null',
                        f'không ép được sang {kind}: {col}', col))
    if key:
        out.append((f'count(*) over (partition by {", ".join(_value(c) for c in key)}) > 1',
                    f'trùng khóa chính ({", ".join(key)})', ', '.join(key)))
    return out


def check(snapshot_path, quarantine_dir, columns=None, keys=None) -> dict:
    """{nguồn: {lý do: số dòng sai}}; rỗng là đạt. Có dòng sai thì ghi quarantine_dir/<nguồn>.csv (_src_row, lý do, cột,
    và giá trị gốc của cả dòng; tối đa SAMPLE dòng mỗi lý do) và quarantine_dir/summary.json."""
    import duckdb
    columns = COLUMNS if columns is None else columns
    keys = KEYS if keys is None else keys
    summary, evidence = {}, {}
    con = duckdb.connect()
    try:
        for name, cols in columns.items():
            source = (Path(snapshot_path) / f'{name}.parquet').as_posix().replace("'", "''")
            table = f"(select * from read_parquet('{source}'))"
            for condition, reason, col in _checks(cols, keys.get(name)):
                rows = f'(select *, {condition} as _sai from {table}) where _sai'
                n = con.execute(f'select count(*) from {rows}').fetchone()[0]
                if not n:
                    continue
                summary.setdefault(name, {})[reason] = n
                cur = con.execute(f'select * exclude (_sai) from {rows} order by _src_row limit {SAMPLE}')
                header = [d[0] for d in cur.description]
                evidence.setdefault(name, (header, []))[1].extend((reason, col, r) for r in cur.fetchall())
    finally:
        con.close()
    if summary:
        write_quarantine(quarantine_dir, summary, evidence, snapshot_path)
    return summary


def write_quarantine(quarantine_dir, summary, evidence=None, snapshot_path=None, error=None):
    """Bằng chứng của lần prepare lỗi vì hợp đồng: summary.json (số dòng sai theo nguồn và lý do, hoặc lỗi header / số
    dòng) và mỗi nguồn một CSV dòng sai. Chỉ ghi dữ liệu nguồn và lý do, không ghi đường dẫn bí mật hay token."""
    folder = Path(quarantine_dir)
    folder.mkdir(parents=True, exist_ok=True)
    for name, (header, rows) in (evidence or {}).items():
        values = [h for h in header if h != '_src_row']
        with (folder / f'{name}.csv').open('w', encoding='utf-8', newline='') as f:
            w = csv.writer(f)
            w.writerow(['_src_row', 'ly_do', 'cot', *values])
            for reason, col, r in rows:
                rec = dict(zip(header, r))
                w.writerow([rec['_src_row'], reason, col, *(rec[h] for h in values)])
    body = {'snapshot': Path(snapshot_path).name if snapshot_path else None, 'dong_sai': summary}
    if error is not None:
        body['loi'] = str(error)
    (folder / 'summary.json').write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding='utf-8')
