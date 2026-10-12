"""Snapshot bất biến: kiểm hợp đồng trước khi ghi, công bố thư mục bằng rename."""
import csv
import hashlib
import json
import os
from pathlib import Path
import tempfile

from scripts.ingest.source_contract import SOURCES


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def validate(path, contract=None):
    import pyarrow.parquet as pq
    contract = SOURCES if contract is None else contract
    path = Path(path)
    manifest = json.loads((path / 'manifest.json').read_text(encoding='utf-8'))
    if set(manifest['sources']) != set(contract):
        raise ValueError('Snapshot thiếu/thừa nguồn')
    for name, (header, count) in contract.items():
        entry = manifest['sources'][name]
        table = pq.read_table(path / f'{name}.parquet')
        if (entry['header'] != header or entry['rows'] != count
                or table.column_names != header + ['_src_row'] or table.num_rows != count
                or table['_src_row'].to_pylist() != list(range(1, count + 1))
                or digest(path / f'{name}.parquet') != entry['parquet_sha256']):
            raise ValueError(f'{name}: snapshot không khớp hợp đồng/hash/định danh dòng')
    identity = hashlib.sha256(''.join(f"{n}:{manifest['sources'][n]['csv_sha256']};"
                                    for n in sorted(contract)).encode()).hexdigest()[:12]
    if manifest['snapshot_id'] != identity or path.name != identity:
        raise ValueError('snapshot_id không khớp nguồn')
    return manifest


def prepare(data='data', landing='warehouse/landing', contract=None):
    import pyarrow as pa
    import pyarrow.parquet as pq
    contract = SOURCES if contract is None else contract
    data, landing = Path(data), Path(landing)
    entries = {}
    # Kiểm toàn bộ trước; hash lại sau khi đọc để phát hiện nguồn bị thay giữa chừng.
    for name, (header, count) in contract.items():
        source = data / f'{name}.csv'
        sha = digest(source)
        with source.open('rb') as f:
            md5 = hashlib.file_digest(f, 'md5').hexdigest()
        with source.open(encoding='utf-8', newline='') as f:
            reader = csv.reader(f)
            if next(reader, None) != header:
                raise ValueError(f'{name}: header sai hợp đồng')
            rows = list(reader)
        if len(rows) != count or any(len(r) != len(header) for r in rows) or digest(source) != sha:
            raise ValueError(f'{name}: số dòng/field sai hoặc nguồn đổi trong lúc đọc')
        table = pa.table({**{h: pa.array([r[j] or None for r in rows], pa.string()) for j, h in enumerate(header)},
                          '_src_row': pa.array(range(1, count + 1), pa.int64())})
        entries[name] = {'header': header, 'rows': count, 'csv_sha256': sha, 'csv_md5': md5, 'table': table}
    sid = hashlib.sha256(''.join(f"{n}:{entries[n]['csv_sha256']};" for n in sorted(entries)).encode()).hexdigest()[:12]
    out = landing / sid
    if out.exists():
        validate(out, contract)
        return out
    landing.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='prepare-', dir=landing) as temporary:
        ready = Path(temporary) / sid
        ready.mkdir()
        for name, entry in entries.items():
            pq.write_table(entry.pop('table'), ready / f'{name}.parquet')
            entry['parquet_sha256'] = digest(ready / f'{name}.parquet')
        (ready / 'manifest.json').write_text(json.dumps({'snapshot_id': sid, 'sources': entries},
                                                       ensure_ascii=False, indent=2), encoding='utf-8')
        os.rename(ready, out)
    return out
