"""Sinh dữ liệu tổng hợp 2023 để demo; không nạp vào kho hay sửa nguồn."""
import argparse
import calendar
import csv
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import random
import re
import shutil
import sys
import tempfile

import duckdb


CSV_FILES = ('orders_enriched', 'order_items', 'payments', 'shipments_realistic',
             'returns', 'reviews', 'promotions', 'inventory', 'web_traffic',
             'customers', 'products', 'geography')
COPIES = ('epd.json', 'customers.csv', 'products.csv', 'geography.csv')
CHILDREN = ('order_items', 'payments', 'shipments_realistic', 'returns', 'reviews')
DATES = {'orders_enriched': ('order_date',), 'shipments_realistic': ('ship_date', 'delivery_date'),
         'returns': ('return_date',), 'reviews': ('review_date',), 'promotions': ('start_date', 'end_date'),
         'inventory': ('snapshot_date',), 'web_traffic': ('date',)}


class CheckError(ValueError):
    pass


def require(code, condition, detail):
    if not condition:
        raise CheckError(f'{code}: {detail}')


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def style(path):
    with Path(path).open('rb') as stream:
        sample = stream.read(65536)
    return ('utf-8-sig' if sample.startswith(b'\xef\xbb\xbf') else 'utf-8',
            '\r\n' if b'\r\n' in sample else '\n')


def header(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return next(csv.reader(stream))


def write_csv(path, columns, rows, formatting=('utf-8', '\n')):
    with Path(path).open('w', encoding=formatting[0], newline='') as stream:
        writer = csv.writer(stream, lineterminator=formatting[1])
        writer.writerow(columns)
        writer.writerows(rows)


def write_json(path, body, formatting=('utf-8', '\n')):
    text = json.dumps(body, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    with Path(path).open('w', encoding=formatting[0], newline='') as stream:
        stream.write(text.replace('\n', formatting[1]))


def shifted(value, days):
    return (date.fromisoformat(value) + timedelta(days=days)).isoformat() if value else value


def day_mapping(rng):
    result = []
    for offset in range(365):
        target = date(2023, 1, 1) + timedelta(days=offset)
        odd = date(2023, 1, 30) <= target <= date(2023, 3, 1) or date(2023, 7, 30) <= target <= date(2023, 9, 2)
        source = target.replace(year=rng.choice((2019, 2021) if odd else (2019, 2020, 2021, 2022)))
        result.append((target.isoformat(), source.isoformat(), (target - source).days))
    return result


def rows_of(con, query, parameters=None):
    cursor = con.execute(query, parameters or [])
    while batch := cursor.fetchmany(4096):
        yield from batch


def load_csv(con, path, table):
    columns = header(path)
    if len(columns) != len(set(columns)) or '_row' in columns:
        raise ValueError('Header không hợp lệ: ' + Path(path).name)
    # parallel=false và preserve_insertion_order giữ số dòng nguồn trước mọi phép nối.
    con.execute(f'create or replace table {quote(table)} as select row_number() over () as _row, * '
                'from read_csv(?, header=true, all_varchar=true, force_not_null=?, parallel=false)',
                [str(path), columns])
    return columns


def read_sources(con, student):
    return {name: load_csv(con, student / (name + '.csv'), 'src_' + name) for name in CSV_FILES}


def output_rows(con, table, columns):
    return rows_of(con, 'select ' + ','.join(map(quote, columns)) + f' from {quote(table)} order by _row')


def max_id(con, table, column, prefix=''):
    values = rows_of(con, f'select {quote(column)} from {quote(table)} order by _row')
    maximum = 0
    for (value,) in values:
        if not re.fullmatch(re.escape(prefix) + r'\d+', value):
            raise ValueError('Dạng mã nguồn không đúng: ' + column)
        maximum = max(maximum, int(value[len(prefix):]))
    return maximum


def generate_csv(con, student, output, mapping, rng, headers):
    con.execute('create table day_map(target varchar, sample varchar, delta integer)')
    con.executemany('insert into day_map values (?,?,?)', mapping)
    missing = con.execute('select count(*) from day_map m where not exists '
                          '(select 1 from src_orders_enriched o where o.order_date=m.sample)').fetchone()[0]
    if missing:
        raise ValueError(f'Có {missing} ngày mẫu không có đơn; cần PM kiểm lại phiếu.')
    maximum = max_id(con, 'src_orders_enriched', 'order_id')
    con.execute('create table order_map as select o.order_id old_id, '
                'cast(? + row_number() over(order by m.target,o._row) as varchar) new_id, '
                'm.target,m.delta,o._row source_row from src_orders_enriched o join day_map m on o.order_date=m.sample', [maximum])
    columns = headers['orders_enriched']
    def orders():
        for values in rows_of(con, 'select ' + ','.join('o.' + quote(c) for c in columns) +
                              ', m.new_id, m.delta from src_orders_enriched o join order_map m '
                              'on o._row=m.source_row order by m.target,o._row'):
            row = dict(zip(columns, values[:-2]))
            row['order_id'], delta = values[-2:]
            row['order_date'] = shifted(row['order_date'], delta)
            tier = ('Bronze', 'Silver', 'Gold', 'Platinum')[int(hashlib.sha256(row['customer_id'].encode()).hexdigest(), 16) % 4]
            yield [row[c] for c in columns] + [tier]
    write_csv(output / 'orders_enriched.csv', columns + ['loyalty_tier'], orders(), style(student / 'orders_enriched.csv'))
    pairs = con.execute("select distinct i.promo_id, m.delta from src_order_items i join order_map m on i.order_id=m.old_id where i.promo_id<>'' "
                        "union select distinct i.promo_id_2,m.delta from src_order_items i join order_map m on i.order_id=m.old_id where i.promo_id_2<>''").fetchall()
    columns = headers['promotions']
    promotions = {row[columns.index('promo_id')]: dict(zip(columns, row))
                  for row in output_rows(con, 'src_promotions', columns)}
    prepared = []
    for old_id, delta in pairs:
        if old_id not in promotions:
            raise ValueError('Khuyến mãi nguồn không có trong master.')
        row = promotions[old_id].copy()
        row['start_date'], row['end_date'] = shifted(row['start_date'], delta), shifted(row['end_date'], delta)
        match = re.fullmatch(r'(.*?)\s+(\d{4})', row['promo_name'])
        if not match:
            raise ValueError('Tên khuyến mãi nguồn không kết thúc bằng năm.')
        row['promo_name'] = match[1] + ' 2023 mau ' + match[2]
        prepared.append((row['start_date'], old_id, delta, row))
    promo_map = {}
    promoted = []
    for number, (_, old_id, delta, row) in enumerate(sorted(prepared, key=lambda x: x[:3]), 51):
        row['promo_id'] = f'PROMO-{number:04d}'
        promo_map[old_id, delta] = row['promo_id']
        promoted.append([row[c] for c in columns])
    write_csv(output / 'promotions.csv', columns, promoted, style(student / 'promotions.csv'))
    for name in CHILDREN:
        columns = headers[name]
        key, prefix, width = ('return_id', 'RET-', 6) if name == 'returns' else ('review_id', 'REV-', 7)
        sequence = max_id(con, 'src_' + name, key, prefix) if name in ('returns', 'reviews') else 0
        def children():
            nonlocal sequence
            query = 'select ' + ','.join('s.' + quote(c) for c in columns) + ',m.new_id,m.delta from src_' + name + \
                    ' s join order_map m on s.order_id=m.old_id order by cast(m.new_id as bigint),s._row'
            for values in rows_of(con, query):
                row = dict(zip(columns, values[:-2]))
                row['order_id'], delta = values[-2:]
                for column in DATES.get(name, ()):
                    row[column] = shifted(row[column], delta)
                if name in ('returns', 'reviews'):
                    sequence += 1
                    row[key] = f'{prefix}{sequence:0{width}d}'
                if name == 'order_items':
                    for column in ('promo_id', 'promo_id_2'):
                        if row[column]:
                            row[column] = promo_map[row[column], delta]
                yield [row[c] for c in columns]
        write_csv(output / (name + '.csv'), columns, children(), style(student / (name + '.csv')))
    months = [(month, rng.choice((2019, 2021) if month in (2, 8) else (2019, 2020, 2021, 2022))) for month in range(1, 13)]
    columns = headers['inventory']
    def inventory():
        for month, year in months:
            target = date(2023, month, calendar.monthrange(2023, month)[1]).isoformat()
            query = 'select ' + ','.join(map(quote, columns)) + ' from src_inventory where substr(snapshot_date,1,7)=? order by _row'
            for values in rows_of(con, query, [f'{year}-{month:02d}']):
                row = dict(zip(columns, values))
                row.update(snapshot_date=target, year='2023')
                yield [row[c] for c in columns]
    write_csv(output / 'inventory.csv', columns, inventory(), style(student / 'inventory.csv'))
    columns = headers['web_traffic']
    def traffic():
        query = 'select m.target,' + ','.join('w.' + quote(c) for c in columns) + \
                ' from src_web_traffic w join day_map m on w.date=m.sample order by m.target,w._row'
        for values in rows_of(con, query):
            row = dict(zip(columns, values[1:]))
            row['date'] = values[0]
            yield [row[c] for c in columns]
    write_csv(output / 'web_traffic.csv', columns, traffic(), style(student / 'web_traffic.csv'))


def generate_json(student, output, rng):
    with (output / 'web_traffic.csv').open(encoding='utf-8-sig', newline='') as stream:
        traffic = list(csv.DictReader(stream))
    require('K8', len(traffic) == 365, 'web_traffic phải có đúng 365 dòng.')
    for index, row in enumerate(traffic, 1):
        for key in ('sessions', 'unique_visitors', 'page_views'):
            row[key] = int(row[key])
        for key in ('bounce_rate', 'avg_session_duration_sec'):
            row[key] = float(row[key])
        if row['traffic_source']:
            row['traffic_source'] += f' Variant {index:04d}'
    planted = []
    for index, (column, value) in zip(rng.sample(range(365), 3), [('date', 'not_a_date'), ('sessions', 'N/A'), ('sessions', -100)]):
        planted.append({'dong': index + 1, 'ngay': traffic[index]['date'], 'cot': column, 'gia_tri': value})
        traffic[index][column] = value
    write_json(output / 'tf.json', traffic, style(student / 'tf.json'))
    body = json.loads((student / 'eprom.json').read_text(encoding='utf-8-sig'))
    if not isinstance(body, list) or len(body) != 1000:
        raise ValueError('eprom.json nguồn phải là mảng 1.000 bản ghi.')
    for row in body:
        try:
            start = date.fromisoformat(row['start_date'])
        except (ValueError, TypeError):
            continue
        if start.year >= 2023:
            continue
        years = 2023 - start.year
        for key in ('start_date', 'end_date'):
            try:
                value = date.fromisoformat(row[key])
            except (ValueError, TypeError):
                continue
            year = value.year + years
            row[key] = value.replace(year=year, day=min(value.day, calendar.monthrange(year, value.month)[1])).isoformat()
    write_json(output / 'eprom.json', body, style(student / 'eprom.json'))
    return planted


def sales_rows(con):
    return rows_of(con, '''select o.order_date,
        cast(round(sum(cast(i.quantity as decimal(18,0))*cast(i.unit_price as decimal(38,16))),2) as decimal(38,2)),
        cast(round(sum(cast(i.quantity as decimal(18,0))*cast(p.cogs as decimal(38,16))),2) as decimal(38,2))
        from out_orders_enriched o join out_order_items i on o.order_id=i.order_id
        join out_products p on i.product_id=p.product_id group by o.order_date order by o.order_date''')


def validate(con, student, goc, output, control, mapping, planted):
    """Đọc lại file đã ghi; mỗi cổng có mã riêng để truy được ca hỏng."""
    headers = {}
    for name in CSV_FILES:
        expected = header(student / (name + '.csv')) + (['loyalty_tier'] if name == 'orders_enriched' else [])
        require('K1', header(output / (name + '.csv')) == expected, 'Sai header: ' + name)
        require('K1', style(output / (name + '.csv')) == style(student / (name + '.csv')), 'Sai BOM/xuống dòng: ' + name)
        headers[name] = load_csv(con, output / (name + '.csv'), 'out_' + name)
    for name, key in [('orders_enriched', 'order_id'), ('returns', 'return_id'), ('reviews', 'review_id'), ('promotions', 'promo_id')]:
        n, unique, blanks = con.execute(f"select count(*),count(distinct {key}),count(*) filter(where {key}='') from out_{name}").fetchone()
        overlap = con.execute(f'select count(*) from out_{name} n join src_{name} s using({key})').fetchone()[0]
        require('K2', n == unique and not blanks and not overlap, 'Trùng/rỗng mã: ' + name)
    for name, columns in DATES.items():
        if name == 'promotions':
            continue
        for column in columns:
            bad = con.execute(f"select count(*) from out_{name} where {column}<>'' and "
                              f"(try_cast({column} as date) is null or cast({column} as date)<=date '2022-12-31')").fetchone()[0]
            require('K3', not bad, 'Ngày sai: ' + name + '.' + column)
    for name, columns in headers.items():
        for key, master in [('order_id', 'orders_enriched'), ('product_id', 'products'), ('customer_id', 'customers'), ('zip', 'geography'),
                            ('promo_id', 'promotions'), ('promo_id_2', 'promotions')]:
            if key not in columns or name == master:
                continue
            master_key = 'promo_id' if key == 'promo_id_2' else key
            allowed_empty = f"c.{key}<>'' and " if key in ('promo_id', 'promo_id_2') else ''
            bad = con.execute(f"select count(*) from out_{name} c where {allowed_empty}not exists "
                              f'(select 1 from out_{master} p where p.{master_key}=c.{key})').fetchone()[0]
            require('K4', not bad, 'Khóa ngoại sai: ' + name + '.' + key)
    load_csv(con, control / 'sales_doi_chung.csv', 'check_sales')
    load_csv(con, goc / 'sales.csv', 'original_sales')
    computed = {day: (str(revenue), str(cogs)) for day, revenue, cogs in sales_rows(con)}
    independent = dict((day, (revenue, cogs)) for day, revenue, cogs in con.execute(
        'select Date,cast(Revenue as decimal(38,2)),cast(COGS as decimal(38,2)) from original_sales order by _row').fetchall())
    actual = list(output_rows(con, 'check_sales', ['Date', 'Revenue', 'COGS']))
    expected = [(target, *map(str, independent.get(sample, (None, None)))) for target, sample, _ in mapping]
    require('K5', actual == expected and all(computed.get(day) == (revenue, cogs) for day, revenue, cogs in actual),
            'G/COGS không khớp ngày mẫu hoặc bộ vừa sinh.')
    for key in ('promo_id', 'promo_id_2'):
        bad = con.execute(f'''select count(*) from out_order_items i join out_orders_enriched o using(order_id)
            join out_promotions p on i.{key}=p.promo_id where not
            (cast(o.order_date as date) between cast(p.start_date as date) and cast(p.end_date as date))''').fetchone()[0]
        require('K6', not bad, 'Khuyến mãi ngoài hiệu lực: ' + key)
    bad = con.execute("select count(*) from out_shipments_realistic s join out_orders_enriched o using(order_id) "
                      "where s.ship_date<>'' and cast(s.ship_date as date)<cast(o.order_date as date)").fetchone()[0]
    require('K7', not bad, 'Ngày giao sớm hơn ngày đặt.')
    for name in CHILDREN:
        expected_counts = con.execute(f'select m.new_id,count(*) from src_{name} s join order_map m on s.order_id=m.old_id group by m.new_id order by m.new_id').fetchall()
        counts = con.execute(f'select order_id,count(*) from out_{name} group by order_id order by order_id').fetchall()
        require('K7', counts == expected_counts, 'Mất/thừa dòng con: ' + name)
    body = json.loads((output / 'tf.json').read_text(encoding='utf-8-sig'))
    original = list(output_rows(con, 'out_web_traffic', headers['web_traffic']))
    require('K8', len(body) == len(original) == 365 and len(planted) == 3 and len({p['dong'] for p in planted}) == 3,
            'Sai số dòng hoặc số ngày cấy.')
    changes = {(p['dong'], p['cot']): p['gia_tri'] for p in planted}
    require('K8', sorted((p['cot'], str(p['gia_tri'])) for p in planted) == [('date', 'not_a_date'), ('sessions', '-100'), ('sessions', 'N/A')], 'Sai giá trị cấy.')
    for index, (row, values) in enumerate(zip(body, original), 1):
        expected_row = dict(zip(headers['web_traffic'], values))
        for key in ('sessions', 'unique_visitors', 'page_views'):
            expected_row[key] = int(expected_row[key])
        for key in ('bounce_rate', 'avg_session_duration_sec'):
            expected_row[key] = float(expected_row[key])
        if expected_row['traffic_source']:
            expected_row['traffic_source'] += f' Variant {index:04d}'
        for key in expected_row:
            if (index, key) in changes:
                expected_row[key] = changes[index, key]
        require('K8', row == expected_row and all(type(row[k]) is type(v) for k, v in expected_row.items()), 'tf.json khác dữ liệu hoặc kiểu đã định.')
    for name in COPIES:
        require('K8', digest(output / name) == digest(student / name), 'File chép bị đổi: ' + name)
    return {f'K{i}': 'dat' for i in range(1, 9)}


def file_info(path):
    info = {'sha256': digest(path)}
    ranges = {}
    if path.suffix == '.csv':
        with path.open(encoding='utf-8-sig', newline='') as stream:
            rows = csv.DictReader(stream)
            count = 0
            for row in rows:
                count += 1
                for key, value in row.items():
                    if key.lower() == 'date' or key.endswith('_date') or key in ('ngay_2023', 'ngay_mau'):
                        try:
                            date.fromisoformat(value)
                        except (ValueError, TypeError):
                            continue
                        low, high = ranges.get(key, (value, value))
                        ranges[key] = (min(low, value), max(high, value))
        info['so_dong'] = count
    else:
        body = json.loads(path.read_text(encoding='utf-8-sig'))
        info['so_dong'] = len(body)
        for row in body:
            for key, value in row.items():
                if key == 'date' or key.endswith('_date'):
                    try:
                        date.fromisoformat(value)
                    except (TypeError, ValueError):
                        continue
                    low, high = ranges.get(key, (value, value))
                    ranges[key] = (min(low, value), max(high, value))
    info['khoang_ngay'] = ranges
    return info


def safe_destinations(output, control):
    paths = []
    for raw in (output, control):
        path = Path(raw).resolve()
        if any(part.casefold() in ('data', 'warehouse') for part in (*Path(raw).absolute().parts, *path.parts)):
            raise ValueError('Đích không được nằm trong data/ hoặc warehouse/.')
        if path.exists() and (not path.is_dir() or any(path.iterdir())):
            raise ValueError('Đích đã có nội dung; không ghi đè.')
        paths.append(path)
    if paths[0] == paths[1] or paths[0] in paths[1].parents or paths[1] in paths[0].parents:
        raise ValueError('Hai thư mục đích phải tách biệt, không lồng nhau.')
    return paths


def generate(student, goc, output='data_demo/dot_2023', control='data_demo/dot_2023_kiem', seed=2023):
    output, control = safe_destinations(output, control)
    student, goc = Path(student).resolve(), Path(goc).resolve()
    inputs = [student / (name + '.csv') for name in CSV_FILES] + [student / name for name in ('tf.json', 'eprom.json', 'epd.json')] + [goc / 'sales.csv']
    for path in inputs:
        if not path.is_file():
            raise ValueError('Thiếu file đầu vào: ' + path.name)
    for destination in (output, control):
        destination.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    mapping = day_mapping(rng)
    with tempfile.TemporaryDirectory(prefix='.dot-2023-', dir=output.parent) as temporary, \
            tempfile.TemporaryDirectory(prefix='.kiem-2023-', dir=control.parent) as checking, \
            duckdb.connect(config={'threads': 2, 'memory_limit': '2GB', 'preserve_insertion_order': True}) as con:
        staged, checks = Path(temporary) / 'files', Path(checking) / 'files'
        staged.mkdir()
        checks.mkdir()
        headers = read_sources(con, student)
        generate_csv(con, student, staged, mapping, rng, headers)
        for name in COPIES:
            shutil.copyfile(student / name, staged / name)
        planted = generate_json(student, staged, rng)
        for name in CSV_FILES:
            load_csv(con, staged / (name + '.csv'), 'out_' + name)
        write_csv(checks / 'anh_xa_ngay.csv', ['ngay_2023', 'ngay_mau', 'lech'], mapping)
        write_csv(checks / 'sales_doi_chung.csv', ['Date', 'Revenue', 'COGS'], sales_rows(con))
        results = validate(con, student, goc, staged, checks, mapping, planted)
        manifest = {'co_du_lieu_tong_hop': True, 'seed': seed,
                    'dau_vao': {('goc/' if path.parent == goc else 'student/') + path.name: digest(path) for path in inputs},
                    'dau_ra': {p.name: file_info(p) for p in sorted(staged.iterdir())},
                    'doi_chung': {p.name: file_info(p) for p in sorted(checks.iterdir())},
                    'gia_tri_cay': planted, 'kiem': results}
        write_json(checks / 'manifest.json', manifest)
        # Kiểm lại ngay trước khi chuyển, không ghi đè file người dùng vừa tạo.
        safe_destinations(output, control)
        for path in (output, control):
            if path.exists():
                path.rmdir()
        staged.rename(output)
        try:
            checks.rename(control)
        except OSError:
            output.rename(staged)
            raise
    return manifest


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--student', required=True)
    parser.add_argument('--goc', required=True)
    parser.add_argument('--ra', default='data_demo/dot_2023')
    parser.add_argument('--kiem', default='data_demo/dot_2023_kiem')
    parser.add_argument('--seed', type=int, default=2023)
    args = parser.parse_args()
    try:
        result = generate(args.student, args.goc, args.ra, args.kiem, args.seed)
    except (ValueError, OSError, duckdb.Error) as error:
        # Chỉ báo mã kiểm/loại lỗi; không đưa giá trị của nhân viên hay shipper ra log.
        print(str(error) if isinstance(error, ValueError) else 'Không tạo được bộ demo: ' + type(error).__name__)
        return 1
    print('Đã sinh bộ tổng hợp 2023: ' + str(result['dau_ra']['orders_enriched.csv']['so_dong']) + ' đơn; K1–K8 đạt.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
