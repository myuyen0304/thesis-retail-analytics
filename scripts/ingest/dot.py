"""Đợt giao dịch tổng hợp: phân loại, kiểm ngưỡng 0 và nối trong vùng tạm."""
import csv
from datetime import date
import hashlib
import json
from pathlib import Path
import tempfile

import duckdb

from scripts.ingest.adapters import quote
from scripts.ingest.source_contract import SOURCES, COLUMNS, KEYS
from scripts.pipeline.contract import _checks

TRANSACTIONS = ('orders', 'order_items', 'payments', 'shipments', 'returns', 'reviews',
                'promotions', 'inventory', 'web_traffic')
DATES = {'orders': ['order_date'], 'shipments': ['ship_date', 'delivery_date'],
         'returns': ['return_date'], 'reviews': ['review_date'], 'inventory': ['snapshot_date'],
         'web_traffic': ['date']}


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class DotError(ValueError):
    def __init__(self, code, file, column, count):
        message = f'{code}: file={file}; cột={column}; số dòng={count}'
        super().__init__(message)
        self.summary = {file: {f'{code}: {column}': count}}


def fail(code, file, column='-', count=1):
    raise DotError(code, file, column, count)


def identity(files):
    return hashlib.sha256(''.join(f"{f['ten']}:{f['sha256']};" for f in sorted(files, key=lambda f: f['ten'])).encode()).hexdigest()[:12]


def suffix(batches):
    return ''.join(f"dot:{b['ma_dot']};" for b in batches)


def seal(batches):
    return hashlib.sha256(json.dumps(batches, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def classify(folder, data):
    folder, data = Path(folder), Path(data)
    masters = {digest(data / (n + '.csv')): n for n in ('customers', 'products', 'geography')}
    files, sources = [], {}
    if not folder.is_dir():
        fail('D2-file', folder.name)
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix.lower() not in ('.csv', '.json') or path.name.lower() in ('sales.csv', 'sample_submission.csv'):
            fail('D2-file', path.name)
        entry = {'ten': path.name, 'sha256': digest(path), 'nguon': None, 'cot_ngoai': [], 'khoang_ngay': {}}
        try:
            if path.suffix.lower() == '.json':
                body = json.loads(path.read_text(encoding='utf-8-sig'))
                if not isinstance(body, list) or not body:
                    fail('D2-empty', path.name, count=0)
                entry.update(nhom='chi_de_xuat', so_dong=len(body))
                for row in body:
                    if not isinstance(row, dict):
                        continue
                    for col, raw in row.items():
                        if col.lower() != 'date' and not col.endswith('_date'):
                            continue
                        try:
                            parsed = str(date.fromisoformat(raw))
                        except (ValueError, TypeError):
                            continue
                        low, high = entry['khoang_ngay'].get(col, [parsed, parsed])
                        entry['khoang_ngay'][col] = [min(low, parsed), max(high, parsed)]
            else:
                with path.open(encoding='utf-8-sig', newline='') as stream:
                    reader = csv.reader(stream)
                    header = next(reader, [])
                    if not header or len(set(c.lower() for c in header)) != len(header) or any(not c or c.startswith('_') for c in header):
                        fail('D2-header', path.name)
                    count = 0
                    for row in reader:
                        count += 1
                        if len(row) != len(header):
                            fail('D2-field', path.name, count=count)
                        for col, value in zip(header, row):
                            if col.lower() == 'date' or col.endswith('_date'):
                                try:
                                    value = str(date.fromisoformat(value.strip()))
                                except ValueError:
                                    continue
                                low, high = entry['khoang_ngay'].get(col, [value, value])
                                entry['khoang_ngay'][col] = [min(low, value), max(high, value)]
                if not count:
                    fail('D2-empty', path.name, count=0)
                entry['so_dong'] = count
                if entry['sha256'] in masters:
                    entry.update(nhom='master_khong_doi', nguon=masters[entry['sha256']])
                else:
                    if any(set(header) == set(SOURCES[n][0]) for n in masters.values()):
                        fail('D2-master', path.name)
                    matches = [n for n in TRANSACTIONS if set(SOURCES[n][0]) <= set(header)]
                    if len(matches) != 1:
                        fail('D2-match', path.name)
                    name = matches[0]
                    if name in sources:
                        fail('D2-duplicate-source', path.name)
                    extra = [c for c in header if c not in SOURCES[name][0]]
                    entry.update(nhom='loi_kem_cot_them' if extra else 'khop_loi', nguon=name, cot_ngoai=extra)
                    sources[name] = path
        except (UnicodeError, csv.Error, json.JSONDecodeError):
            fail('D2-format', path.name)
        files.append(entry)
    if set(sources) != set(TRANSACTIONS):
        fail('D2-missing', folder.name, ','.join(sorted(set(TRANSACTIONS) - set(sources))))
    return {'ma_dot': identity(files), 'files': files}, sources


def classify_all(folders, data):
    batches = [classify(folder, data) for folder in folders]
    seen = set()
    for batch, _ in batches:
        if batch['ma_dot'] in seen:
            fail('D2-7', batch['ma_dot'])
        seen.add(batch['ma_dot'])
    return batches


def value(column, alias='', kind=None):
    expr = f"nullif(trim({alias + '.' if alias else ''}{quote(column)}), '')"
    return f'cast({expr} as {kind})' if kind and kind != 'string' else expr


def check_count(con, query, code, file, column):
    count = con.execute(query).fetchone()[0]
    if count:
        fail(code, file, column, count)


def check_batch(con, sources, cutoff):
    for name in TRANSACTIONS:
        for condition, _, column in _checks(COLUMNS[name], None):
            check_count(con, f'select count(*) from (select *, {condition} as bad from new_{name}) where bad',
                        'D2-0', sources[name].name, column)
    # Đợt không được âm thầm làm tròn giá về decimal(14,2) như đường gốc.
    check_count(con, r"select count(*) from new_order_items where regexp_matches(trim(unit_price), '\.[0-9]{3,}') "
                "or cast(unit_price as decimal(38,16)) != cast(unit_price as decimal(14,2))",
                'D2-0', sources['order_items'].name, 'unit_price')
    for name, key in [('orders', 'order_id'), ('returns', 'return_id'), ('reviews', 'review_id'), ('promotions', 'promo_id')]:
        kind = COLUMNS[name][key][0]
        expr = value(key, kind=kind)
        check_count(con, f'select count(*) from (select count(*) over(partition by {expr}) n from new_{name}) where n>1',
                    'D2-1', sources[name].name, key)
        check_count(con, f'select count(*) from new_{name} n where exists (select 1 from base_{name} b where '
                    f'{value(key, "n", kind)}={value(key, "b", kind)})', 'D2-1', sources[name].name, key)
    for name, columns in DATES.items():
        for col in columns:
            check_count(con, f"select count(*) from new_{name} where {value(col, kind='date')} <= date '{cutoff}'",
                        'D2-2', sources[name].name, col)
    count, last = con.execute('select count(distinct cast(order_date as date)), max(cast(order_date as date)) from new_orders').fetchone()
    if count != (last - cutoff).days:
        fail('D2-3', sources['orders'].name, 'order_date', (last - cutoff).days - count)
    for name in ('order_items', 'payments', 'shipments', 'returns', 'reviews'):
        check_count(con, f'select count(*) from new_{name} n where not exists (select 1 from new_orders o where '
                    f'{value("order_id", "n", "integer")}={value("order_id", "o", "integer")})',
                    'D2-4', sources[name].name, 'order_id')
    for name in TRANSACTIONS:
        for col, master in [('product_id', 'products'), ('customer_id', 'customers'), ('zip', 'geography')]:
            if col in SOURCES[name][0]:
                check_count(con, f'select count(*) from new_{name} n where not exists (select 1 from base_{master} m where '
                            f'{value(col, "n", "integer")}={value(col, "m", "integer")})', 'D2-5', sources[name].name, col)
    for col in ('promo_id', 'promo_id_2'):
        check_count(con, f'''select count(*) from new_order_items i join new_orders o
            on {value('order_id', 'i', 'integer')}={value('order_id', 'o', 'integer')}
            where {value(col, 'i')} is not null and not exists
            (select 1 from (select * from base_promotions union all select * from new_promotions) p
            where {value(col, 'i')}={value('promo_id', 'p')} and cast(o.order_date as date)
            between cast(p.start_date as date) and cast(p.end_date as date))''',
                    'D2-6', sources['order_items'].name, col)
    for name in TRANSACTIONS:
        keys = KEYS[name]
        if keys:
            partition = ', '.join(value(col, kind=COLUMNS[name][col][0]) for col in keys)
            condition = f'count(*) over (partition by {partition}) > 1'
            check_count(con, f'select count(*) from (select *, {condition} as bad from '
                        f'(select * from base_{name} union all select * from new_{name})) where bad',
                        'D2-8', sources[name].name, ', '.join(keys))


def prepare(data, landing, contract, extensions, extension_directory, folders):
    from scripts.pipeline import snapshot
    from scripts.ingest import extension_contract, extension_prepare
    data, landing = Path(data), Path(landing)
    classified = classify_all(folders, data)
    documents = {n: extension_contract.load(n, extension_directory) for n in sorted(set(extensions))}
    landing.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='dot-', dir=landing) as temporary:
        temp = Path(temporary)
        base = snapshot.prepare(data, temp / 'base', contract)
        manifest = snapshot.validate(base, contract)
        entries = manifest['sources']
        ready = temp / 'ready'
        ready.mkdir()
        reports, additions = [], {n: [] for n in documents}
        with duckdb.connect(config={'threads': 2, 'memory_limit': '2GB'}) as con:
            for name, (header, _) in contract.items():
                con.execute(f'create table base_{name} as select * exclude (_src_row) from read_parquet(?) order by _src_row', [str(base / (name + '.parquet'))])
            for report, sources in classified:
                cutoff = con.execute('select max(cast(order_date as date)) from base_orders').fetchone()[0]
                report['moc'] = str(cutoff)
                for name, path in sources.items():
                    columns = ','.join(quote(c) for c in contract[name][0])
                    try:
                        con.execute(f'create or replace table new_{name} as select {columns} from read_csv(?, header=true, all_varchar=true, parallel=false)', [str(path)])
                    except duckdb.Error:
                        fail('D2-format', path.name)
                check_batch(con, sources, cutoff)
                con.execute('''create or replace table new_sales as select cast(cast(o.order_date as date) as varchar) as Date,
                    cast(cast(round(coalesce(sum(cast(i.quantity as decimal(18,0))*cast(i.unit_price as decimal(38,16))),0),2) as decimal(38,2)) as varchar) Revenue,
                    cast(cast(round(coalesce(sum(cast(i.quantity as decimal(18,0))*cast(p.cogs as decimal(38,16))),0),2) as decimal(38,2)) as varchar) COGS
                    from new_orders o left join new_order_items i on cast(o.order_id as integer)=cast(i.order_id as integer)
                    left join base_products p on cast(i.product_id as integer)=cast(p.product_id as integer)
                    group by cast(o.order_date as date) order by cast(o.order_date as date)''')
                revenue, cogs = con.execute('select sum(cast(Revenue as decimal(38,2))),sum(cast(COGS as decimal(38,2))) from new_sales').fetchone()
                report.update(Revenue=str(revenue), COGS=str(cogs), sales_rows=con.execute('select count(*) from new_sales').fetchone()[0])
                for name in (*TRANSACTIONS, 'sales'):
                    con.execute(f'insert into base_{name} select * from new_{name} order by rowid')
                for name, doc in documents.items():
                    source = doc['khoa_noi']['nguon']
                    item = next(f for f in report['files'] if f['nguon'] == source)
                    if item['nhom'] == 'loi_kem_cot_them':
                        path = sources[source]
                        with path.open(encoding='utf-8-sig', newline='') as stream:
                            header = next(csv.reader(stream))
                        missing = set(doc['header']) - set(header)
                        if missing:
                            fail('D2-extension', path.name, ','.join(sorted(missing)))
                        additions[name].append(path)
                reports.append(report)
            for name, entry in entries.items():
                out = ready / (name + '.parquet')
                con.execute(f'copy (select *, row_number() over (order by rowid) as _src_row from base_{name} order by rowid) to ? (format parquet)', [str(out)])
                entry.update(rows=con.execute(f'select count(*) from base_{name}').fetchone()[0], parquet_sha256=digest(out))
        for name, doc in documents.items():
            entries[name] = extension_prepare.prepare(doc, data, ready, additions=additions[name])
        # Băm lại trước công bố, không đưa giá trị nguồn vào thông báo lỗi.
        for (report, _), folder in zip(classified, folders):
            for item in report['files']:
                if digest(Path(folder) / item['ten']) != item['sha256']:
                    fail('D2-changed', item['ten'])
        extended = {n: e for n, e in entries.items() if e.get('mo_rong')}
        sid = hashlib.sha256((''.join(f"{n}:{entries[n]['csv_sha256']};" for n in sorted(contract))
                              + extension_contract.identity_suffix(extended) + suffix(reports)).encode()).hexdigest()[:12]
        manifest.update(snapshot_id=sid, dot=reports, co_du_lieu_tong_hop=True, dot_sha256=seal(reports))
        (ready / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        out = landing / sid
        candidate = temp / sid
        ready.rename(candidate)
        snapshot.validate(candidate, contract, extension_directory)
        if out.exists():
            snapshot.validate(out, contract, extension_directory)
        else:
            candidate.rename(out)
        return out
