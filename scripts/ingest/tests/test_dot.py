"""D2: fixture nhỏ, mỗi luật có ca hỏng riêng; không đọc dữ liệu thật."""
import csv
from datetime import date, timedelta
import json
from pathlib import Path
import shutil
import sys

import pyarrow.parquet as pq
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.ingest import dot, extension_contract, extension_prepare
from scripts.ingest.source_contract import SOURCES, COLUMNS
from scripts.pipeline import snapshot, contract


def read(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write(path, rows, header=None):
    header = header or list(rows[0])
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, header)
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def case(tmp_path):
    class Case:
        data = tmp_path / 'data'
        batch = tmp_path / 'batch'
        landing = tmp_path / 'snapshots'
        contracts = tmp_path / 'contracts'

        def build(self, folder, start, first, core=False):
            folder.mkdir()
            for name in SOURCES if core else dot.TRANSACTIONS:
                rows = []
                for i in range(2 if name not in ('customers', 'geography', 'products', 'promotions') else 1):
                    day = str(date.fromisoformat(start) + timedelta(days=i))
                    row = {c: ('' if nullable else 'text' if kind == 'string' else day if kind == 'date' else '1')
                           for c, (kind, nullable) in COLUMNS[name].items()}
                    for col in ('product_id', 'customer_id', 'zip'):
                        if col in row:
                            row[col] = '1'
                    if 'order_id' in row:
                        row['order_id'] = str(first + i)
                    for key in ('return_id', 'review_id', 'promo_id'):
                        if key in row and name != 'order_items':
                            row[key] = f'{key}-{first + i}'
                    if name == 'orders':
                        row['order_status'] = 'cancelled'
                    if name == 'order_items':
                        row.update(unit_price='0.10', discount_amount='99.00', quantity='1')
                    if name == 'products':
                        row['cogs'] = '0.104'
                    if name == 'promotions':
                        row.update(start_date='2020-01-01', end_date='2030-01-01')
                    rows.append(row)
                if name == 'order_items':
                    rows = [r for row in rows for r in (dict(row), dict(row))]
                write(folder / (name + '.csv'), rows, SOURCES[name][0])

        def run(self, batches=None, extensions=()):
            return snapshot.prepare(self.data, self.landing, self.spec, extensions,
                                    self.contracts if extensions else None,
                                    dots=[self.batch] if batches is None else batches)

        def change(self, name, column, value, index=0, folder=None):
            path = (folder or self.batch) / (name + '.csv')
            rows = read(path)
            rows[index][column] = value
            write(path, rows)

        def extension(self, tolerance=0.01):
            self.contracts.mkdir(exist_ok=True)
            doc = extension_contract.load('orders_enriched')
            doc.pop('hop_dong_sha256')
            doc['nguong_cach_ly'] = tolerance
            (self.contracts / 'orders_enriched.yml').write_text(yaml.safe_dump(doc, allow_unicode=True), encoding='utf-8')
            (self.data / 'student_data').mkdir(exist_ok=True)
            for folder, target in [(self.data, self.data / doc['file']), (self.batch, self.batch / 'orders.csv')]:
                rows = read(folder / 'orders.csv')
                for row in rows:
                    row.update(city='City', region='Region', district='District', sales_employee_id='EMP1',
                               sales_employee_name='PII_NAME_SENTINEL', marital_status='Single', education_level='College',
                               years_experience='5', comment='')
                write(target, rows, doc['header'])
            return doc

    c = Case()
    c.build(c.data, '2022-12-30', 1, core=True)
    for path in c.data.glob('*.csv'):
        path.write_bytes(path.read_bytes().removeprefix(b'\xef\xbb\xbf'))
    c.build(c.batch, '2023-01-01', 11)
    c.spec = {n: (header, len(read(c.data / (n + '.csv')))) for n, (header, _) in SOURCES.items()}
    return c


def rejected(c, code, batches=None):
    with pytest.raises(dot.DotError, match='^' + code + ':') as caught:
        c.run(batches)
    assert caught.value.summary
    assert not c.landing.exists() or not list(c.landing.iterdir())
    return caught.value


def test_clean_core_order_sales_and_contract(case):
    path = case.run()
    manifest = snapshot.validate(path, case.spec)
    assert not contract.check(path, case.landing.parent / 'quarantine')
    for name, (_, count) in case.spec.items():
        table = pq.read_table(path / (name + '.parquet')).to_pylist()
        expected = [{k: v or None for k, v in r.items()} for r in read(case.data / (name + '.csv'))]
        if name in dot.TRANSACTIONS:
            expected += [{k: v or None for k, v in r.items()} for r in read(case.batch / (name + '.csv'))]
        elif name == 'sales':
            expected += [{'Date': d, 'Revenue': '0.20', 'COGS': '0.21'} for d in ('2023-01-01', '2023-01-02')]
        assert table == [dict(r, _src_row=i) for i, r in enumerate(expected, 1)]
    assert manifest['dot'][0]['Revenue'] == '0.40'
    assert manifest['dot'][0]['COGS'] == '0.42'
    assert case.run() == path


def test_sales_keeps_day_without_items(case):
    path = case.batch / 'order_items.csv'
    write(path, [r for r in read(path) if r['order_id'] == '11'])
    snapshot_path = case.run()
    sales = pq.read_table(snapshot_path / 'sales.parquet').to_pylist()
    assert sales[-1] == {'Date': '2023-01-02', 'Revenue': '0.00', 'COGS': '0.00', '_src_row': 4}


@pytest.mark.parametrize('damage,code', [('missing', 'D2-missing'), ('duplicate', 'D2-duplicate-source'),
    ('ambiguous', 'D2-match'), ('unknown', 'D2-match'), ('master', 'D2-master'),
    ('sales', 'D2-file'), ('sample_submission', 'D2-file'), ('suffix', 'D2-file'),
    ('directory', 'D2-file'), ('empty_csv', 'D2-empty'), ('empty_json', 'D2-empty'),
    ('duplicate_header', 'D2-header'), ('fields', 'D2-field')])
def test_classification_errors(case, damage, code):
    if damage == 'missing':
        (case.batch / 'reviews.csv').unlink()
    elif damage == 'duplicate':
        shutil.copyfile(case.batch / 'orders.csv', case.batch / 'another.csv')
    elif damage == 'ambiguous':
        rows = read(case.batch / 'orders.csv')
        for row in rows:
            row.update(payment_value='1', installments='1')
        write(case.batch / 'orders.csv', rows)
    elif damage in ('unknown', 'master'):
        rows = read(case.data / 'products.csv') if damage == 'master' else [{'unknown': '1'}]
        if damage == 'master':
            rows[0]['product_name'] = 'changed'
        write(case.batch / 'other.csv', rows)
    elif damage in ('sales', 'sample_submission', 'suffix'):
        (case.batch / (damage + ('.txt' if damage == 'suffix' else '.csv'))).write_text('x')
    elif damage == 'directory':
        (case.batch / 'child').mkdir()
    elif damage == 'empty_json':
        (case.batch / 'proposal.json').write_text('[]')
    else:
        path = case.batch / 'reviews.csv'
        if damage == 'empty_csv':
            write(path, [], SOURCES['reviews'][0])
        elif damage == 'duplicate_header':
            path.write_text('x,x\n1,2\n')
        else:
            with path.open('a') as stream:
                stream.write('1,2\n')
    rejected(case, code)


@pytest.mark.parametrize('name,col,bad', [('order_items', 'quantity', 'N/A'), ('order_items', 'unit_price', 'N/A'),
    ('orders', 'order_date', ''), ('orders', 'order_date', 'not_a_date')])
def test_d20_types(case, name, col, bad):
    case.change(name, col, bad)
    rejected(case, 'D2-0')


@pytest.mark.parametrize('name,key', [('orders', 'order_id'), ('returns', 'return_id'),
    ('reviews', 'review_id'), ('promotions', 'promo_id')])
@pytest.mark.parametrize('mode', ['within', 'base'])
def test_d21_ids(case, name, key, mode):
    path = case.batch / (name + '.csv')
    rows = read(path)
    if mode == 'within':
        rows.append(dict(rows[0]))
    else:
        rows[0][key] = read(case.data / (name + '.csv'))[0][key]
    write(path, rows)
    rejected(case, 'D2-1')


@pytest.mark.parametrize('name,col', [('orders', 'order_date'), ('shipments', 'ship_date'),
    ('shipments', 'delivery_date'), ('returns', 'return_date'), ('reviews', 'review_date'),
    ('inventory', 'snapshot_date'), ('web_traffic', 'date')])
def test_d22_each_date(case, name, col):
    case.change(name, col, '2022-12-31')
    rejected(case, 'D2-2')


def test_d23_gap(case):
    case.change('orders', 'order_date', '2023-01-03', 1)
    rejected(case, 'D2-3')


@pytest.mark.parametrize('mode', ['within', 'base'])
def test_s2_order_ids_use_integer_identity(case, mode):
    path = case.batch / 'orders.csv'
    rows = read(path)
    if mode == 'within':
        rows.append(dict(rows[0], order_id='011'))
    else:
        rows[0]['order_id'] = '01'
        for name in ('order_items', 'payments', 'shipments', 'returns', 'reviews'):
            child = case.batch / (name + '.csv')
            children = read(child)
            for row in children:
                if row['order_id'] == '11':
                    row['order_id'] = '01'
            write(child, children)
    write(path, rows)
    rejected(case, 'D2-1')


def test_s3_date_keys_use_date_identity(case):
    path = case.batch / 'web_traffic.csv'
    rows = read(path)
    write(path, rows + [dict(rows[0], date='2023-1-1')])
    rejected(case, 'D2-8')


@pytest.mark.parametrize('price', ['0.105', '0.100', '1.5E-2'])
def test_s4_unit_price_excess_scale(case, price):
    case.change('order_items', 'unit_price', price)
    rejected(case, 'D2-0')


def test_s5_gap_reports_missing_day_count(case):
    case.change('orders', 'order_date', '2023-01-03', 1)
    error = rejected(case, 'D2-3')
    assert error.summary == {'orders.csv': {'D2-3: order_date': 1}}


@pytest.mark.parametrize('name', ['order_items', 'payments', 'shipments', 'returns', 'reviews'])
@pytest.mark.parametrize('key', ['1', '9999'])
def test_d24_child_must_belong_to_batch(case, name, key):
    case.change(name, 'order_id', key)
    rejected(case, 'D2-4')


@pytest.mark.parametrize('name,col', [('order_items', 'product_id'), ('orders', 'customer_id'), ('orders', 'zip'),
    ('returns', 'product_id'), ('reviews', 'product_id'), ('reviews', 'customer_id'), ('inventory', 'product_id')])
def test_d25_masters(case, name, col):
    case.change(name, col, '9999')
    rejected(case, 'D2-5')


@pytest.mark.parametrize('col', ['promo_id', 'promo_id_2'])
@pytest.mark.parametrize('mode', ['missing', 'expired'])
def test_d26_promotions(case, col, mode):
    case.change('order_items', col, 'missing' if mode == 'missing' else 'promo_id-11')
    if mode == 'expired':
        case.change('promotions', 'end_date', '2022-12-31')
    rejected(case, 'D2-6')


def test_d27_duplicate_batch(case):
    rejected(case, 'D2-7', [case.batch, case.batch])


@pytest.mark.parametrize('name', ['payments', 'shipments', 'inventory', 'web_traffic'])
def test_d28_primary_keys(case, name):
    path = case.batch / (name + '.csv')
    rows = read(path)
    write(path, rows + [dict(rows[0])])
    rejected(case, 'D2-8')


def second_batch(c):
    path = c.batch.parent / 'second'
    c.build(path, '2023-01-03', 21)
    return path


def test_two_batches_delivery_does_not_set_cutoff(case):
    case.change('shipments', 'delivery_date', '2023-02-01')
    second = second_batch(case)
    path = case.run([case.batch, second])
    assert snapshot.validate(path, case.spec)['dot'][1]['moc'] == '2023-01-02'
    assert dot.suffix([{'ma_dot': 'a'}, {'ma_dot': 'b'}]) != dot.suffix([{'ma_dot': 'b'}, {'ma_dot': 'a'}])


def test_reversed_batches(case):
    rejected(case, 'D2-3', [second_batch(case), case.batch])


def test_new_ids_same_period_rejected(case):
    second = second_batch(case)
    for name, columns in dot.DATES.items():
        rows = read(second / (name + '.csv'))
        for row in rows:
            for col in columns:
                row[col] = str(date.fromisoformat(row[col]) - timedelta(days=2))
        write(second / (name + '.csv'), rows)
    rejected(case, 'D2-2', [case.batch, second])


def test_traffic_duplicate_across_batches(case):
    case.change('web_traffic', 'date', '2023-01-03')
    rejected(case, 'D2-8', [case.batch, second_batch(case)])


def test_classify_master_json_and_extra_columns(case):
    shutil.copyfile(case.data / 'products.csv', case.batch / 'renamed.csv')
    (case.batch / 'proposal.json').write_text('[{"private":"PII_EXTRA_SENTINEL"}]')
    rows = read(case.batch / 'orders.csv')
    for row in rows:
        row['loyalty_tier'] = 'PII_EXTRA_SENTINEL'
    header = list(reversed(SOURCES['orders'][0]))
    header.insert(3, 'loyalty_tier')
    write(case.batch / 'orders.csv', rows, header)
    rows = read(case.batch / 'payments.csv')
    write(case.batch / 'payments.csv', rows, list(reversed(list(rows[0]))))
    path = case.run()
    manifest = snapshot.validate(path, case.spec)
    assert 'PII_EXTRA_SENTINEL' not in (path / 'manifest.json').read_text(encoding='utf-8')
    info = {f['ten']: f for f in manifest['dot'][0]['files']}
    assert info['renamed.csv']['nhom'] == 'master_khong_doi'
    assert info['proposal.json']['nhom'] == 'chi_de_xuat'
    assert info['orders.csv']['cot_ngoai'] == ['loyalty_tier']
    assert pq.read_table(path / 'orders.parquet').column_names == SOURCES['orders'][0] + ['_src_row']
    assert 'PII_EXTRA_SENTINEL' not in str(pq.read_table(path / 'orders.parquet').to_pylist())


@pytest.mark.parametrize('target', ['orders.csv', 'proposal.json'])
def test_file_bytes_change_identity(case, target):
    (case.batch / 'proposal.json').write_text('[{}]')
    first = case.run()
    if target.endswith('.csv'):
        case.change('orders', 'order_status', 'delivered')
    else:
        with (case.batch / target).open('a') as stream:
            stream.write('\n')
    assert case.run() != first


@pytest.mark.parametrize('field', ['moc', 'rows', 'dot', 'amount'])
def test_manifest_tamper(case, field):
    path = case.run()
    manifest = json.loads((path / 'manifest.json').read_text(encoding='utf-8'))
    if field == 'rows':
        manifest['sources']['orders']['rows'] += 1
    elif field == 'dot':
        manifest['dot'] = []
    elif field == 'amount':
        manifest['dot'][0]['Revenue'] = '999.99'
    else:
        manifest['dot'][0]['moc'] = '2000-01-01'
    (path / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError):
        snapshot.validate(path, case.spec)


def test_extension_clean_and_no_pii_manifest(case):
    case.extension()
    rows = read(case.batch / 'orders.csv')
    for row in rows:
        row['loyalty_tier'] = 'PII_EXTRA_SENTINEL'
    header = list(rows[0])
    header.remove('loyalty_tier')
    header.insert(3, 'loyalty_tier')
    write(case.batch / 'orders.csv', rows, header)
    path = case.run(extensions=['orders_enriched'])
    manifest = snapshot.validate(path, case.spec, case.contracts)
    entry = manifest['sources']['orders_enriched']
    assert entry['so_dong_cach_ly'] == 0 and entry['rows'] == 4
    assert entry['cach_ly'] == {}
    assert pq.read_table(path / 'orders_enriched.parquet')['_dong_goc'].to_pylist() == [1, 2, 3, 4]
    assert 'PII_NAME_SENTINEL' not in (path / 'manifest.json').read_text(encoding='utf-8')
    assert 'PII_EXTRA_SENTINEL' not in (path / 'manifest.json').read_text(encoding='utf-8')
    assert 'loyalty_tier' not in pq.read_table(path / 'orders_enriched.parquet').column_names


def test_extension_r6_and_private_error(case):
    case.extension()
    case.change('orders', 'years_experience', '6')
    with pytest.raises(extension_prepare.QuarantineError) as caught:
        case.run(extensions=['orders_enriched'])
    assert caught.value.summary['orders_enriched'][extension_prepare.R6] == 4
    assert 'PII_NAME_SENTINEL' not in str(caught.value)
    assert not list(case.landing.iterdir())


@pytest.mark.parametrize('tolerance,passes', [(0.26, True), (0.24, False)])
def test_extension_threshold_uses_combined_total(case, tolerance, passes):
    case.extension(tolerance)
    case.change('orders', 'years_experience', 'invalid')
    if passes:
        path = case.run(extensions=['orders_enriched'])
        entry = snapshot.validate(path, case.spec, case.contracts)['sources']['orders_enriched']
        assert entry['so_dong_file'] == 4 and entry['so_dong_cach_ly'] == 1
        assert entry['cach_ly'] == {extension_prepare.R5: 1}
    else:
        with pytest.raises(extension_prepare.QuarantineError):
            case.run(extensions=['orders_enriched'])


def test_extension_missing_header(case):
    case.extension()
    rows = read(case.batch / 'orders.csv')
    for row in rows:
        row.pop('comment')
    write(case.batch / 'orders.csv', rows)
    with pytest.raises(dot.DotError, match='^D2-extension:') as caught:
        case.run(extensions=['orders_enriched'])
    assert caught.value.summary == {'orders.csv': {'D2-extension: comment': 1}}
    assert not list(case.landing.iterdir())


def test_sales_quantity_greater_than_one(case):
    case.change('order_items', 'quantity', '3')
    path = case.run()
    sales = pq.read_table(path / 'sales.parquet').to_pylist()
    assert sales[-2:] == [
        {'Date': '2023-01-01', 'Revenue': '0.40', 'COGS': '0.42', '_src_row': 3},
        {'Date': '2023-01-02', 'Revenue': '0.20', 'COGS': '0.21', '_src_row': 4}]


@pytest.mark.parametrize('origin', ['base', 'previous', 'current'])
@pytest.mark.parametrize('column', ['promo_id', 'promo_id_2'])
def test_valid_promotions_from_each_period(case, origin, column):
    batches = [case.batch]
    folder = case.batch
    key = 'promo_id-1' if origin == 'base' else 'promo_id-11'
    if origin == 'previous':
        folder = second_batch(case)
        batches.append(folder)
    case.change('order_items', column, key, folder=folder)
    path = case.run(batches)
    snapshot.validate(path, case.spec)
    assert not contract.check(path, case.landing.parent / 'quarantine')


@pytest.mark.parametrize('damage,code', [('json', 'D2-format'), ('encoding', 'D2-format'),
    ('underscore', 'D2-header'), ('directory_csv', 'D2-file')])
def test_specific_classification_errors(case, damage, code):
    if damage == 'json':
        (case.batch / 'proposal.json').write_text('[invalid')
    elif damage == 'encoding':
        (case.batch / 'reviews.csv').write_bytes(b'\xff\xfe')
    elif damage == 'underscore':
        rows = read(case.batch / 'orders.csv')
        for row in rows:
            row['_private'] = 'sentinel'
        write(case.batch / 'orders.csv', rows)
    else:
        (case.batch / 'x.csv').mkdir()
    rejected(case, code)


def test_file_changed_after_classification(case, monkeypatch):
    original = dot.check_batch

    def change_after_checks(con, sources, cutoff):
        original(con, sources, cutoff)
        case.change('orders', 'order_status', 'delivered')

    monkeypatch.setattr(dot, 'check_batch', change_after_checks)
    rejected(case, 'D2-changed')


def test_extension_base_header_order_rejected(case):
    doc = case.extension()
    source = case.data / doc['file']
    write(source, read(source), list(reversed(doc['header'])))
    with pytest.raises(dot.DotError, match='^D2-extension:'):
        case.run(extensions=['orders_enriched'])
    assert not list(case.landing.iterdir())


@pytest.mark.parametrize('field', ['sha256', 'ten'])
def test_manifest_file_identity_even_when_resealed(case, field):
    path = case.run()
    manifest_path = path / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest['dot'][0]['files'][0][field] = '0' * 64 if field == 'sha256' else 'renamed.csv'
    manifest['dot_sha256'] = dot.seal(manifest['dot'])
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError):
        snapshot.validate(path, case.spec)


def test_manifest_synthetic_flag_required(case):
    path = case.run()
    manifest_path = path / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest['co_du_lieu_tong_hop'] = False
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError):
        snapshot.validate(path, case.spec)


def test_prepare_rejects_existing_corrupt_snapshot(case):
    path = case.run()
    (path / 'orders.parquet').write_bytes(b'corrupt')
    with pytest.raises(ValueError):
        case.run()
    assert list(case.landing.iterdir()) == [path]


@pytest.mark.parametrize('reason,column,value', [
    (extension_prepare.R1, 'order_id', 'invalid'),
    (extension_prepare.R2, 'order_id', '2'),
    (extension_prepare.R3, 'order_id', '9999'),
    (extension_prepare.R4, 'order_status', 'different'),
    (extension_prepare.R5, 'years_experience', 'invalid')])
def test_extension_base_rules_still_run_on_combined_input(case, reason, column, value):
    doc = case.extension(0.6)
    source = case.data / doc['file']
    rows = read(source)
    rows[0][column] = value
    if reason == extension_prepare.R2:
        rows[0] = dict(rows[1])
    write(source, rows, doc['header'])
    path = case.run(extensions=['orders_enriched'])
    entry = snapshot.validate(path, case.spec, case.contracts)['sources']['orders_enriched']
    assert entry['cach_ly'] == {reason: 2 if reason == extension_prepare.R2 else 1}
    assert entry['so_dong_file'] == 4
