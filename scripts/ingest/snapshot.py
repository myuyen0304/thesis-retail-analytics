"""Snapshot nguồn dùng chung cho mọi loader cloud (Snowflake, Databricks): 14 CSV (data/) -> Parquet + manifest.json.

Cùng hợp đồng với scripts/ingest/ingest_raw.py (Postgres): MỌI cột kiểu chuỗi, tên cột đúng header CSV, ô rỗng -> NULL,
không làm sạch (việc của dbt staging), thêm `_src_row` = số thứ tự record trong file (bắt đầu từ 1).

Vì sao `_src_row` đánh ở MÁY, không để cloud đánh: line_number của dòng hàng phải theo thứ tự nguồn (star_schema.md §5.1)
và order_items có 16 cặp (order_id, product_id) lặp, nên thứ tự sai là ghép nhầm returns/reviews mà không test nào báo.
Thứ tự đọc song song của Spark / Snowflake không phải thứ tự file; METADATA$FILE_ROW_NUMBER đếm DÒNG vật lý, lệch khi một
record CSV có ô xuống dòng. Hai nền tảng nạp cùng một snapshot nên đối soát so được từng dòng.

Đọc CSV bằng csv.reader (record logic), kiểm header + số field + số record theo contract, ghi vào
warehouse/landing/<snapshot_id>/ (warehouse/ đã gitignore). snapshot_id chỉ phụ thuộc byte 14 file nguồn: cùng data/ thì
cùng id, chạy lại không sinh snapshot mới.

Chạy từ root repo (cần pyarrow):  .venv/Scripts/python.exe scripts/ingest/snapshot.py
"""
import csv
import datetime as dt
import hashlib
import json
import os
import sys

DATA = 'data'
LANDING = 'warehouse/landing'
SOURCES = {  # tên file: số record kỳ vọng (không tính header) — cùng số với scripts/ingest/ingest_raw.py
    'geography': 39_948, 'customers': 121_930, 'products': 2_412, 'promotions': 50,
    'orders': 646_945, 'order_items': 714_669, 'payments': 646_945, 'shipments': 566_067,
    'returns': 39_939, 'reviews': 113_551, 'inventory': 60_247, 'web_traffic': 3_652,
    'sales': 3_833, 'sample_submission': 548,
}


def local_config(path):
    """Giá trị đã điền trong file .env.*.local (file cá nhân, Git ignore). Biến môi trường cùng tên được ưu tiên."""
    cfg = {}
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            k, sep, v = line.strip().partition('=')
            if sep and not k.startswith('#'):
                cfg[k.strip()] = v.strip().strip("'\"")
    return {k: os.environ.get(k) or v for k, v in cfg.items() if os.environ.get(k) or v}


def file_hashes(path):
    md5, sha = hashlib.md5(), hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(1 << 20):
            md5.update(chunk)
            sha.update(chunk)
    return md5.hexdigest(), sha.hexdigest()


def load_manifest(snapshot_id):
    """Manifest của snapshot, sau khi kiểm từng file Parquet còn đúng như lúc prepare."""
    src = f'{LANDING}/{snapshot_id}'
    with open(f'{src}/manifest.json', encoding='utf-8') as f:
        manifest = json.load(f)
    for name, e in manifest['sources'].items():
        if file_hashes(f'{src}/{name}.parquet')[1] != e['parquet_sha256']:
            sys.exit(f'{name}.parquet khác manifest — chạy lại scripts/ingest/snapshot.py.')
    return src, manifest


def prepare():
    import pyarrow as pa
    import pyarrow.parquet as pq

    entries, problems = {}, []
    for name, expected in SOURCES.items():
        path = f'{DATA}/{name}.csv'
        md5, sha = file_hashes(path)
        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            cols = [[] for _ in header]
            n_bad_width = 0
            for rec in reader:
                if len(rec) != len(header):
                    n_bad_width += 1
                    continue
                for c, v in zip(cols, rec):
                    c.append(v if v != '' else None)   # ô rỗng -> NULL, như COPY CSV của Postgres và read_csv của DuckDB
        n = len(cols[0]) if cols else 0
        ok = n == expected and n_bad_width == 0 and len(set(h.lower() for h in header)) == len(header)
        if not ok:
            problems.append(name)
        table = pa.table({**{h: pa.array(c, pa.string()) for h, c in zip(header, cols)},
                          '_src_row': pa.array(range(1, n + 1), pa.int64())})
        entries[name] = {'rows': n, 'expected': expected, 'bad_width': n_bad_width, 'header': header,
                         'csv_md5': md5, 'csv_sha256': sha, 'table': table}
        print(f"  {'PASS' if ok else 'FAIL'}  {name:18s} {n:>9,} record (kỳ vọng {expected:,}), "
              f"{n_bad_width} record sai số field")
    if problems:
        print(f'\n{len(problems)} nguồn sai contract: {problems} — không ghi snapshot.')
        sys.exit(1)

    snapshot_id = hashlib.sha256(''.join(f"{k}:{entries[k]['csv_sha256']};" for k in sorted(entries)).encode()).hexdigest()[:12]
    out = f'{LANDING}/{snapshot_id}'
    os.makedirs(out, exist_ok=True)
    manifest = {'snapshot_id': snapshot_id, 'created_at_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                'n_records': sum(e['rows'] for e in entries.values()), 'sources': {}}
    for name, e in entries.items():
        pq.write_table(e.pop('table'), f'{out}/{name}.parquet')
        e['parquet_sha256'] = file_hashes(f'{out}/{name}.parquet')[1]
        manifest['sources'][name] = e
    with open(f'{out}/manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"\nSnapshot {snapshot_id}: {manifest['n_records']:,} record, ghi ở {out}/")
    print(f'Tiếp theo: ingest_snowflake.py --snapshot {snapshot_id}  hoặc  ingest_databricks.py --snapshot {snapshot_id}')


if __name__ == '__main__':
    prepare()
