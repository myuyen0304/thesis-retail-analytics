"""Dữ liệu nhỏ tự dựng; không đọc kho thật hay kết nối dịch vụ ngoài."""
import calendar
import csv
from datetime import date, timedelta
from decimal import Decimal
import json
from pathlib import Path
import random
import sys

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.demo import sinh_dot_2023 as demo
from scripts.ingest.source_contract import SOURCES


@pytest.fixture
def inputs(tmp_path):
    student, goc = tmp_path / 'student', tmp_path / 'goc'
    student.mkdir()
    goc.mkdir()
    tables = {name: [] for name in demo.CSV_FILES}
    order_header = SOURCES['orders'][0] + ['sales_employee_id', 'sales_employee_name', 'years_experience', 'comment']
    shipment_header = SOURCES['shipments'][0] + ['join_date', 'shipper_name', 'shipper_phone']
    headers = {name: SOURCES[name][0] for name in demo.CSV_FILES if name in SOURCES}
    headers.update(orders_enriched=order_header, shipments_realistic=shipment_header)
    masters = {'customers': {'customer_id': '0001', 'zip': '00001'},
               'products': {'product_id': '0002', 'cogs': '0.104'}, 'geography': {'zip': '00001'}}
    for name, values in masters.items():
        tables[name].append({**{key: '  giữ nguyên  ' for key in headers[name]}, **values})
    original_sales = []
    current = date(2019, 1, 1)
    number = 0
    while current < date(2023, 1, 1):
        number += 1
        order = str(number)
        promo = f'PROMO-{current.year - 2018:04d}'
        tables['orders_enriched'].append(dict(zip(order_header, [order, str(current), '0001', '00001', 'cancelled',
            'cash', 'mobile', 'shop', 'EMP-001', 'Tên giả', '1e3', '  ghi chú  '])))
        quantity = current.year - 2018
        items = [quantity, 1] if number % 10 == 0 else [quantity]
        for index, qty in enumerate(items):
            tables['order_items'].append(dict(zip(headers['order_items'],
                [order, '0002', str(qty), '10.10', '0.10', promo, promo if index else ''])))
        tables['payments'].append(dict(zip(headers['payments'], [order, 'cash', '1e3', '1'])))
        tables['shipments_realistic'].append(dict(zip(shipment_header,
            [order, str(current + timedelta(days=1)), str(current + timedelta(days=3)), '0.10', '2010-01-01', 'Tên giả', '  001  '])))
        tables['returns'].append(dict(zip(headers['returns'], [f'RET-{number:06d}', order, '0002',
            str(current + timedelta(days=4)), '  lý do  ', '1', '0.10'])))
        tables['reviews'].append(dict(zip(headers['reviews'], [f'REV-{number:07d}', order, '0002', '0001',
            str(current + timedelta(days=5)), '5', '  nhận xét  '])))
        tables['web_traffic'].append(dict(zip(headers['web_traffic'], [str(current), '100', '80', '200', '0.10', '10.0', 'Direct'])))
        original_sales.append([str(current), str(sum(items) * Decimal('10.10')),
                               str((sum(items) * Decimal('0.104')).quantize(Decimal('0.01')))])
        current += timedelta(days=1)
    for year in range(2019, 2023):
        tables['promotions'].append(dict(zip(headers['promotions'], [f'PROMO-{year - 2018:04d}',
            f'Urban Blowout {year}', 'percent', '0.10', f'{year - 1}-12-30', f'{year}-12-31', '', 'Online', '1', '1e3'])))
        for month in range(1, 13):
            row = {key: '0.10' for key in headers['inventory']}
            row.update(snapshot_date=str(date(year, month, calendar.monthrange(year, month)[1])),
                       product_id='0002', year=str(year), month=f'{month:02d}')
            tables['inventory'].append(row)
    for name, rows in tables.items():
        formatting = ('utf-8-sig', '\n') if name == 'orders_enriched' else ('utf-8', '\r\n')
        demo.write_csv(student / (name + '.csv'), headers[name], ([row[key] for key in headers[name]] for row in rows), formatting)
    demo.write_csv(goc / 'sales.csv', ['Date', 'Revenue', 'COGS'], original_sales)
    demo.write_json(student / 'tf.json', [{'date': '2019-01-01', 'sessions': 100}])
    demo.write_json(student / 'epd.json', [{'product_id': '  0002 ', 'price': 'giá lạ'}])
    promotions = [{'promo_id': f' {i} ', 'discount_value': 'twenty percent' if i % 2 else '30%%',
                   'start_date': '2020-02-29', 'end_date': '2020-03-01'} for i in range(1000)]
    promotions[1].update(start_date='not_a_date', end_date='2020-01-01')
    promotions[2].update(start_date='2023-01-01', end_date='2023-02-01')
    promotions[3].update(start_date='2020-01-01', end_date='not_a_date')
    demo.write_json(student / 'eprom.json', promotions)
    return student, goc


@pytest.fixture
def generated(inputs, tmp_path):
    student, goc = inputs
    output, control = tmp_path / 'output', tmp_path / 'control'
    manifest = demo.generate(student, goc, output, control)
    return student, goc, output, control, manifest


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def rewrite(path, rows):
    columns = demo.header(path)
    demo.write_csv(path, columns, ([row[column] for column in columns] for row in rows), demo.style(path))


def test_deterministic_bytes_and_seed(generated, tmp_path):
    student, goc, output, control, manifest = generated
    output2, control2 = tmp_path / 'second', tmp_path / 'second_check'
    demo.generate(student, goc, output2, control2)
    for left, right in [(output, output2), (control, control2)]:
        assert {p.name: p.read_bytes() for p in left.iterdir()} == {p.name: p.read_bytes() for p in right.iterdir()}
    assert demo.day_mapping(random.Random(2023)) != demo.day_mapping(random.Random(2024))
    assert manifest['co_du_lieu_tong_hop'] is True and manifest['kiem'] == {f'K{i}': 'dat' for i in range(1, 9)}
    assert str(tmp_path) not in (control / 'manifest.json').read_text(encoding='utf-8')
    assert {p.name for p in output.iterdir()} == {name + '.csv' for name in demo.CSV_FILES} | {'tf.json', 'epd.json', 'eprom.json'}


def test_odd_windows_and_leap_offsets():
    mapping = demo.day_mapping(random.Random(2023))
    assert len(mapping) == len({row[0] for row in mapping}) == 365
    for target, sample, delta in mapping:
        day = date.fromisoformat(target)
        if date(2023, 1, 30) <= day <= date(2023, 3, 1) or date(2023, 7, 30) <= day <= date(2023, 9, 2):
            assert date.fromisoformat(sample).year in (2019, 2021)
        assert demo.shifted(sample, delta) == target
    assert demo.shifted('2020-01-15', 1096) == '2023-01-15'
    assert demo.shifted('2020-03-15', 1095) == '2023-03-15'
    assert demo.shifted('', 1095) == ''


def test_promotions_pairs_and_previous_year(generated):
    _, _, output, control, _ = generated
    promotions = csv_rows(output / 'promotions.csv')
    mapping = csv_rows(control / 'anh_xa_ngay.csv')
    expected = {(int(row['ngay_mau'][:4]), int(row['lech'])) for row in mapping}
    assert len(promotions) == len(expected)
    assert len([row for row in promotions if row['promo_name'].endswith('2020')]) == 2
    assert min(row['start_date'] for row in promotions).startswith('2022')
    assert promotions[0]['promo_id'] == 'PROMO-0051'
    assert all(row['promo_name'].startswith('Urban Blowout 2023 mau ') for row in promotions)
    assert all(row['discount_value'] == '0.10' and row['min_order_value'] == '1e3' for row in promotions)


def test_raw_values_order_bom_json_and_inventory(generated):
    student, _, output, _, manifest = generated
    orders = csv_rows(output / 'orders_enriched.csv')
    items = csv_rows(output / 'order_items.csv')
    assert (output / 'orders_enriched.csv').read_bytes().startswith(b'\xef\xbb\xbf')
    assert all(row['years_experience'] == '1e3' and row['comment'] == '  ghi chú  ' for row in orders)
    assert len({row['loyalty_tier'] for row in orders}) == 1 and orders[0]['loyalty_tier'] in ('Bronze', 'Silver', 'Gold', 'Platinum')
    assert [int(row['order_id']) for row in orders] == list(range(1462, 1827))
    assert all(row['unit_price'] == '10.10' for row in items)
    assert all(row['payment_value'] == '1e3' for row in csv_rows(output / 'payments.csv'))
    shipments = csv_rows(output / 'shipments_realistic.csv')
    assert all(row['join_date'] == '2010-01-01' and row['shipper_phone'] == '  001  ' for row in shipments)
    assert max(row['delivery_date'] for row in shipments).startswith('2024')
    for name in demo.CSV_FILES:
        assert demo.style(output / (name + '.csv')) == demo.style(student / (name + '.csv'))
    for name in demo.COPIES:
        assert (output / name).read_bytes() == (student / name).read_bytes()
    eprom = json.loads((output / 'eprom.json').read_text())
    original = json.loads((student / 'eprom.json').read_text())
    assert len(eprom) == 1000
    assert eprom[0]['start_date'] == '2023-02-28' and eprom[0]['end_date'] == '2023-03-01'
    assert eprom[1] == original[1] and eprom[2] == original[2]
    assert eprom[3]['start_date'] == '2023-01-01' and eprom[3]['end_date'] == 'not_a_date'
    assert [{k: v for k, v in row.items() if k not in ('start_date', 'end_date')} for row in eprom] == [
        {k: v for k, v in row.items() if k not in ('start_date', 'end_date')} for row in original]
    inventory = csv_rows(output / 'inventory.csv')
    assert len(inventory) == 12
    for row in inventory:
        month = int(row['month'])
        assert row['month'] == f'{month:02d}' and row['year'] == '2023'
        assert row['snapshot_date'] == str(date(2023, month, calendar.monthrange(2023, month)[1]))
    tf = json.loads((output / 'tf.json').read_text())
    planted = manifest['gia_tri_cay']
    assert len(tf) == 365 and len({row['dong'] for row in planted}) == 3
    assert sum(row['date'] == 'not_a_date' for row in tf) == 1
    assert sum(row['sessions'] == 'N/A' for row in tf) == 1
    assert sum(row['sessions'] == -100 for row in tf) == 1
    assert all(len(row) == 7 for row in tf)


@pytest.mark.parametrize('code', ['K1', 'K2', 'K3', 'K4', 'K5', 'K6', 'K7', 'K8'])
def test_each_gate_catches_corruption(generated, code):
    student, goc, output, control, manifest = generated
    if code == 'K1':
        path = output / 'orders_enriched.csv'
        path.write_bytes(path.read_bytes().replace(b'loyalty_tier', b'wrong_column', 1))
    elif code == 'K8':
        body = json.loads((output / 'tf.json').read_text())
        body[0]['unique_visitors'] = -1
        demo.write_json(output / 'tf.json', body)
    else:
        filename = {'K2': 'orders_enriched.csv', 'K3': 'reviews.csv', 'K4': 'payments.csv',
                    'K5': 'sales_doi_chung.csv', 'K6': 'promotions.csv', 'K7': 'payments.csv'}[code]
        path = (control if code == 'K5' else output) / filename
        rows = csv_rows(path)
        if code == 'K2':
            rows[1]['order_id'] = rows[0]['order_id']
        elif code == 'K3':
            rows[0]['review_date'] = '2022-12-31'
        elif code == 'K4':
            rows[0]['order_id'] = '99999999'
        elif code == 'K5':
            rows[0]['Revenue'] = '999.99'
        elif code == 'K6':
            rows[0]['start_date'] = '2024-01-01'
        elif code == 'K7':
            rows.pop()
        rewrite(path, rows)
    with duckdb.connect(config={'threads': 2, 'memory_limit': '2GB'}) as con:
        demo.read_sources(con, student)
        # Ánh xạ kiểm dòng con dựng độc lập từ ngày mẫu và mã nối tiếp.
        mapping = demo.day_mapping(random.Random(2023))
        con.execute('create table order_map(old_id varchar,new_id varchar)')
        original = {row['order_date']: row['order_id'] for row in csv_rows(student / 'orders_enriched.csv')}
        con.executemany('insert into order_map values (?,?)', [(original[sample], str(1462 + i)) for i, (_, sample, _) in enumerate(mapping)])
        with pytest.raises(demo.CheckError, match='^' + code + ':'):
            demo.validate(con, student, goc, output, control, mapping, manifest['gia_tri_cay'])


@pytest.mark.parametrize('destination', ['data/new', 'warehouse/new', 'DATA/new', 'occupied', 'control_occupied', 'same', 'nested'])
def test_unsafe_destination_writes_nothing(inputs, tmp_path, destination):
    student, goc = inputs
    output, control = tmp_path / destination, tmp_path / 'checks'
    if destination in ('occupied', 'control_occupied'):
        path = output if destination == 'occupied' else control
        path.mkdir()
        (path / 'keep.txt').write_text('giữ lại', encoding='utf-8')
    if destination == 'same':
        control = output
    if destination == 'nested':
        control = output / 'checks'
    before = {str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    with pytest.raises(ValueError):
        demo.generate(student, goc, output, control)
    assert before == {str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}


def test_failed_validation_does_not_publish(inputs, tmp_path, monkeypatch):
    def fail(*args):
        raise demo.CheckError('K5: cố ý làm hỏng')
    monkeypatch.setattr(demo, 'validate', fail)
    with pytest.raises(demo.CheckError, match='K5'):
        demo.generate(*inputs, tmp_path / 'output', tmp_path / 'check')
    assert not (tmp_path / 'output').exists() and not (tmp_path / 'check').exists()
    assert not list(tmp_path.glob('.dot-2023-*')) and not list(tmp_path.glob('.kiem-2023-*'))


def test_original_sales_is_only_independent_check(inputs, tmp_path):
    student, goc = inputs
    rows = csv_rows(goc / 'sales.csv')
    for row in rows:
        row['Revenue'] = '0.00'
    rewrite(goc / 'sales.csv', rows)
    with pytest.raises(demo.CheckError, match='^K5:'):
        demo.generate(student, goc, tmp_path / 'output', tmp_path / 'check')
    assert not (tmp_path / 'output').exists()


def assert_gate(generated, code):
    student, goc, output, control, manifest = generated
    mapping = demo.day_mapping(random.Random(2023))
    original = {row['order_date']: row['order_id'] for row in csv_rows(student / 'orders_enriched.csv')}
    with duckdb.connect(config={'threads': 2, 'memory_limit': '2GB'}) as con:
        demo.read_sources(con, student)
        con.execute('create table order_map(old_id varchar,new_id varchar)')
        con.executemany('insert into order_map values (?,?)',
                       [(original[sample], str(1462 + i)) for i, (_, sample, _) in enumerate(mapping)])
        with pytest.raises(demo.CheckError, match='^' + code + ':'):
            demo.validate(con, student, goc, output, control, mapping, manifest['gia_tri_cay'])


@pytest.mark.parametrize('formatting', ['bom', 'newline'])
def test_k1_rejects_changed_file_style(generated, formatting):
    path = generated[2] / 'orders_enriched.csv'
    body = path.read_bytes()
    path.write_bytes(body[3:] if formatting == 'bom' else body.replace(b'\n', b'\r\n'))
    assert_gate(generated, 'K1')


@pytest.mark.parametrize('table,key', [('orders_enriched', 'order_id'), ('returns', 'return_id'),
                                     ('reviews', 'review_id'), ('promotions', 'promo_id')])
@pytest.mark.parametrize('damage', ['blank', 'duplicate', 'original'])
def test_k2_rejects_invalid_ids_in_each_table(generated, table, key, damage):
    student, _, output, _, _ = generated
    path = output / (table + '.csv')
    rows = csv_rows(path)
    rows[0][key] = {'blank': '', 'duplicate': rows[1][key],
                    'original': csv_rows(student / (table + '.csv'))[0][key]}[damage]
    rewrite(path, rows)
    assert_gate(generated, 'K2')


@pytest.mark.parametrize('table,column', [('orders_enriched', 'order_date'),
    ('shipments_realistic', 'ship_date'), ('shipments_realistic', 'delivery_date'),
    ('returns', 'return_date'), ('reviews', 'review_date'), ('inventory', 'snapshot_date'),
    ('web_traffic', 'date')])
def test_k3_rejects_old_date_in_each_column(generated, table, column):
    path = generated[2] / (table + '.csv')
    rows = csv_rows(path)
    rows[0][column] = '2022-12-31'
    rewrite(path, rows)
    assert_gate(generated, 'K3')


@pytest.mark.parametrize('table,key', [('order_items', 'product_id'), ('orders_enriched', 'customer_id'),
    ('orders_enriched', 'zip'), ('order_items', 'promo_id'), ('order_items', 'promo_id_2')])
def test_k4_rejects_missing_master(generated, table, key):
    path = generated[2] / (table + '.csv')
    rows = csv_rows(path)
    rows[0][key] = 'missing-master'
    rewrite(path, rows)
    assert_gate(generated, 'K4')


def test_k5_recomputes_from_generated_items(generated):
    # Không đổi đối chứng hay sales gốc: chỉ tổng tính từ bộ sinh bị lệch.
    path = generated[2] / 'order_items.csv'
    rows = csv_rows(path)
    rows[0]['unit_price'] = '99.99'
    rewrite(path, rows)
    assert_gate(generated, 'K5')


def test_k6_checks_second_promotion_independently(generated):
    output = generated[2]
    promotions = csv_rows(output / 'promotions.csv')
    expired = dict(promotions[0], promo_id='PROMO-9999', start_date='2022-01-01', end_date='2022-12-31')
    rewrite(output / 'promotions.csv', promotions + [expired])
    rows = csv_rows(output / 'order_items.csv')
    rows[0]['promo_id_2'] = expired['promo_id']
    rewrite(output / 'order_items.csv', rows)
    assert_gate(generated, 'K6')


def test_k7_rejects_shipping_before_order_but_after_2022(generated):
    output = generated[2]
    orders = {row['order_id']: row['order_date'] for row in csv_rows(output / 'orders_enriched.csv')}
    path = output / 'shipments_realistic.csv'
    rows = csv_rows(path)
    row = next(row for row in rows if orders[row['order_id']] >= '2023-06-01')
    row['ship_date'] = str(date.fromisoformat(orders[row['order_id']]) - timedelta(days=1))
    assert '2022-12-31' < row['ship_date'] < orders[row['order_id']]
    rewrite(path, rows)
    assert_gate(generated, 'K7')


@pytest.mark.parametrize('damage', ['rows', 'plant_count', 'plant_days', 'plant_value', 'numeric_type'])
def test_k8_rejects_json_shape_injections_and_types(generated, damage):
    output, manifest = generated[2], generated[4]
    path = output / 'tf.json'
    body = json.loads(path.read_text(encoding='utf-8'))
    planted = manifest['gia_tri_cay']
    if damage == 'rows':
        body.append(dict(body[-1]))
    elif damage == 'plant_count':
        planted.append(dict(planted[0]))
    elif damage == 'plant_days':
        # Hai trường khác nhau cùng một ngày; thân JSON vẫn khớp metadata.
        first, second = planted[:2]
        original = csv_rows(output / 'web_traffic.csv')
        body[second['dong'] - 1][second['cot']] = int(original[second['dong'] - 1][second['cot']])
        second.update(dong=first['dong'], ngay=first['ngay'])
        body[first['dong'] - 1][second['cot']] = second['gia_tri']
    elif damage == 'plant_value':
        planted[0]['gia_tri'] = 'another_bad_date'
        body[planted[0]['dong'] - 1][planted[0]['cot']] = 'another_bad_date'
    else:
        # int == float trong Python: phải kiểm đúng kiểu, không chỉ giá trị.
        body[0]['unique_visitors'] = float(body[0]['unique_visitors'])
    demo.write_json(path, body)
    assert_gate(generated, 'K8')


@pytest.mark.parametrize('name', ['epd.json', 'customers.csv', 'products.csv', 'geography.csv'])
def test_k8_checks_each_copied_file_hash(generated, name):
    # Thêm whitespace cuối file không đổi header, kiểu xuống dòng, khóa hay số liệu.
    path = generated[2] / name
    with path.open('ab') as stream:
        stream.write(b'\r\n' if name.endswith('.csv') else b' ')
    assert_gate(generated, 'K8')


def test_item_order_matches_source_within_each_order(generated):
    student, _, output, control, _ = generated
    source_orders = {row['order_date']: row['order_id'] for row in csv_rows(student / 'orders_enriched.csv')}
    original, actual = {}, {}
    for row in csv_rows(student / 'order_items.csv'):
        original.setdefault(row['order_id'], []).append(row['quantity'])
    for row in csv_rows(output / 'order_items.csv'):
        actual.setdefault(row['order_id'], []).append(row['quantity'])
    multiple_distinct = 0
    for order, day in zip(csv_rows(output / 'orders_enriched.csv'), csv_rows(control / 'anh_xa_ngay.csv')):
        expected = original[source_orders[day['ngay_mau']]]
        assert actual[order['order_id']] == expected
        multiple_distinct += len(set(expected)) > 1
    assert multiple_distinct > 0


def test_orders_same_day_keep_source_order(inputs, tmp_path):
    student, goc = inputs
    path = student / 'orders_enriched.csv'
    rows = csv_rows(path)
    # Thêm đơn không có dòng con vào ngày chắc chắn được lấy mẫu; mã đảo thứ tự số.
    sample = demo.day_mapping(random.Random(2023))[0][1]
    index = next(i for i, row in enumerate(rows) if row['order_date'] == sample)
    rows.insert(index, dict(rows[index], order_id='9999', comment='first-in-source'))
    rows[index + 1]['comment'] = 'second-in-source'
    rewrite(path, rows)
    output = tmp_path / 'same_day'
    demo.generate(student, goc, output, tmp_path / 'same_day_check')
    actual = csv_rows(output / 'orders_enriched.csv')[:2]
    assert [row['order_date'] for row in actual] == ['2023-01-01'] * 2
    assert [row['comment'] for row in actual] == ['first-in-source', 'second-in-source']
    assert [row['order_id'] for row in actual] == ['10000', '10001']


@pytest.mark.parametrize('start', ['2023-01-01', '2024-02-29', '2026-12-31'])
def test_eprom_start_from_2023_keeps_entire_record(inputs, tmp_path, start):
    student, goc = inputs
    path = student / 'eprom.json'
    rows = json.loads(path.read_text(encoding='utf-8'))
    rows[0].update(start_date=start, end_date='2028-02-29', discount_value='30%%')
    demo.write_json(path, rows)
    output = tmp_path / 'future_promo'
    demo.generate(student, goc, output, tmp_path / 'future_promo_check')
    actual = json.loads((output / 'eprom.json').read_text(encoding='utf-8'))
    assert actual[0] == rows[0]
