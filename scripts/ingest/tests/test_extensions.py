"""E1–E10: hợp đồng duyệt, cách ly và định danh snapshot mở rộng trên fixture nhỏ."""
import copy
import csv
import hashlib
import json
from pathlib import Path
import sys

import duckdb
import pyarrow.parquet as pq
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.ingest import extension_contract as ec, extension_prepare as ep
from scripts.ingest.source_contract import SOURCES, COLUMNS
from scripts.pipeline import snapshot


@pytest.fixture
def extension_case(tmp_path, monkeypatch):
    """Hợp đồng trong tmp_path; dữ liệu lõi và mở rộng chỉ 200 dòng."""
    doc = ec.load('orders_enriched')
    doc.pop('hop_dong_sha256')
    folder = tmp_path / 'contracts'
    folder.mkdir()
    monkeypatch.setattr(ec, 'CONTRACT_DIR', folder)
    data = tmp_path / 'data'
    (data / 'student_data').mkdir(parents=True)
    core_header = SOURCES['orders'][0]
    core = [[str(i), '2022-01-01', '1', '1', 'Delivered', 'Card', 'Web', 'Direct'] for i in range(1, 201)]
    rows = []
    for i, row in enumerate(core):
        values = dict(zip(core_header, row))
        values.update(city='City', region='Region', district='District',
                      sales_employee_id='EMP' + str(max(i, 1)), sales_employee_name='Tên',
                      marital_status='Single', education_level='College', years_experience='5', comment='')
        rows.append([values[c] for c in doc['header']])
    class Case:
        landing = tmp_path / 'landing'
        contract = {'orders': (core_header, len(core))}
        def write(self, header=None):
            self.contract_path.write_text(yaml.safe_dump(self.doc, allow_unicode=True, sort_keys=False), encoding='utf-8')
            for path, hdr, body in [(data / 'orders.csv', core_header, self.core),
                                    (data / self.doc['file'], header or self.doc['header'], self.rows)]:
                with path.open('w', encoding='utf-8', newline='') as stream:
                    csv.writer(stream).writerows([hdr, *body])
        def set(self, row, column, value):
            self.rows[row][self.doc['header'].index(column)] = value
        def run(self, extensions=('orders_enriched',)):
            return snapshot.prepare(data, self.landing, self.contract, extensions, folder)
        def entry(self, path):
            return json.loads((path / 'manifest.json').read_text(encoding='utf-8'))['sources']['orders_enriched']
    case = Case()
    case.doc, case.rows, case.core, case.data = doc, rows, core, data
    case.contract_path = folder / 'orders_enriched.yml'
    case.folder = folder
    case.write()
    return case


@pytest.mark.parametrize('change,field', [
    (lambda d: d['cot'][0].update(trang_thai='de_xuat'), 'trang_thai'),
    (lambda d: d.update(trang_thai='de_xuat'), 'trang_thai'),
    (lambda d: d['thuc_the'][0].update(trang_thai='de_xuat'), 'trang_thai'),
    (lambda d: d.pop('ngay_duyet'), 'ngay_duyet'),
    (lambda d: d.pop('duyet_boi'), 'duyet_boi'),
    (lambda d: d['cot'][1].update(xu_ly='unknown'), 'xu_ly'),
    (lambda d: d.update(ten='orders'), 'ten'),
    (lambda d: d['khoa_noi'].update(nguon='unknown'), 'khoa_noi'),
    (lambda d: d['cot'].pop(), 'header'),
    (lambda d: d.update(nguong_cach_ly=1.5), 'nguong'),
    (lambda d: d['cot'][-1].update(kieu='blob'), 'kieu'),
    (lambda d: next(c for c in d['cot'] if c['ten'] == 'city').update(xu_ly='doi_chieu_loi'), 'doi_chieu_loi'),
])
def test_e1_contract_rejects(extension_case, change, field):
    c = extension_case
    change(c.doc)
    c.write()
    with pytest.raises(ValueError, match=field) as error:
        ec.load('orders_enriched', c.folder)
    assert 'orders_enriched.yml' in str(error.value)


@pytest.mark.parametrize('mode', ['added', 'missing', 'reordered'])
def test_e2_header(extension_case, mode):
    c = extension_case
    header = c.doc['header'][:]
    if mode == 'added':
        header.append('extra')
        c.rows = [r + ['x'] for r in c.rows]
    elif mode == 'missing':
        header.pop()
        c.rows = [r[:-1] for r in c.rows]
    else:
        header[0], header[1] = header[1], header[0]
    c.write(header)
    with pytest.raises(ValueError, match='scripts.ingest.auto_mapping'):
        c.run()
    assert not list(c.landing.glob('*/manifest.json'))


def test_e3_e10_clean_manifest_runtime(extension_case):
    c = extension_case
    path = c.run()
    entry = c.entry(path)
    selected = ['order_id', 'sales_employee_id', 'sales_employee_name', 'marital_status',
                'education_level', 'years_experience', 'comment']
    assert entry['header'] == selected
    assert entry['so_dong_cach_ly'] == 0 and entry['rows'] == entry['so_dong_file'] == 200
    assert {'header', 'rows', 'csv_sha256', 'csv_md5', 'parquet_sha256'} <= entry.keys()
    table = pq.read_table(path / 'orders_enriched.parquet')
    assert table.column_names == selected + ['_src_row', '_dong_goc']
    assert all(str(table[c].type) == 'string' for c in selected)
    assert table['comment'].null_count == 200
    with duckdb.connect(config={'threads': 4}) as con:
        stats = con.execute('select count(*), count(distinct _src_row), min(_src_row), max(_src_row) '
                            'from read_parquet(?)', [str(path / 'orders_enriched.parquet')]).fetchone()
    assert stats == (200, 200, 1, 200)
    assert snapshot.validate(path, c.contract, c.folder)
    assert c.run() == path


@pytest.mark.parametrize('reason,changes,removed', [
    (ep.R1, [(0, 'order_id', 'abc')], [1]),
    (ep.R2, [(1, 'order_id', '1')], [1, 2]),
    (ep.R3, [(0, 'order_id', '999')], [1]),
    (ep.R4, [(0, 'order_status', 'Other')], [1]),
    (ep.R5, [(0, 'years_experience', 'abc')], [1]),
    (ep.R6, [(0, 'years_experience', '7')], [1, 2]),
])
def test_e4_reasons(extension_case, reason, changes, removed):
    c = extension_case
    for row, col, value in changes:
        c.set(row, col, value)
    c.write()
    path = c.run()
    entry = c.entry(path)
    assert entry['cach_ly'] == {reason: len(removed)}
    assert entry['so_dong_cach_ly'] == len(removed)
    table = pq.read_table(path / 'orders_enriched.parquet')
    assert table['_src_row'].to_pylist() == list(range(1, 201 - len(removed)))
    assert table['_dong_goc'].to_pylist() == [i for i in range(1, 201) if i not in removed]
    with (path / 'cach_ly/orders_enriched.csv').open(encoding='utf-8') as stream:
        evidence = list(csv.DictReader(stream))
    assert {int(r['_dong_goc']) for r in evidence} == set(removed)
    assert all(r['ly_do'] == reason and set(c.doc['header']) <= r.keys() for r in evidence)


def test_e5_bad_type_does_not_cascade(extension_case):
    c = extension_case
    c.set(0, 'years_experience', 'abc')
    c.write()
    path = c.run()
    assert c.entry(path)['cach_ly'] == {ep.R5: 1}
    assert pq.read_table(path / 'orders_enriched.parquet')['_dong_goc'][0].as_py() == 2


def test_e6_multiple_reasons_count_once(extension_case):
    c = extension_case
    c.doc['nguong_cach_ly'] = .005
    c.set(0, 'order_status', 'Other')
    c.set(0, 'years_experience', 'abc')
    c.write()
    path = c.run()
    assert c.entry(path)['so_dong_cach_ly'] == 1
    assert c.entry(path)['cach_ly'] == {ep.R4: 1, ep.R5: 1}
    with (path / 'cach_ly/orders_enriched.csv').open(encoding='utf-8') as stream:
        assert {r['ly_do'] for r in csv.DictReader(stream)} == {ep.R4, ep.R5}


@pytest.mark.parametrize('bad', [1, 2, 3])
def test_e7_threshold(extension_case, bad):
    c = extension_case
    for i in range(bad):
        c.set(i, 'years_experience', 'abc')
    c.write()
    if bad > 2:
        with pytest.raises(ep.QuarantineError, match='3/200.*0.01') as error:
            c.run()
        assert error.value.summary == {'orders_enriched': {ep.R5: 3}}
        assert not list(c.landing.glob('*/manifest.json'))
    else:
        assert c.entry(c.run())['so_dong_cach_ly'] == bad


def test_e8_identity_and_disabled_bytes(extension_case):
    c = extension_case
    old = c.run(())
    sha = snapshot.digest(c.data / 'orders.csv')
    assert old.name == hashlib.sha256(f'orders:{sha};'.encode()).hexdigest()[:12]
    expected = {'snapshot_id': old.name, 'sources': {'orders': {
        'header': c.contract['orders'][0], 'rows': 200, 'csv_sha256': sha,
        'csv_md5': ep.digest(c.data / 'orders.csv', 'md5'),
        'parquet_sha256': ep.digest(old / 'orders.parquet')}}}
    expected_path = c.folder / 'expected.json'
    expected_path.write_text(json.dumps(expected, ensure_ascii=False, indent=2), encoding='utf-8')
    assert (old / 'manifest.json').read_bytes() == expected_path.read_bytes()
    enabled = c.run()
    assert enabled != old
    raw = c.contract_path.read_bytes().replace(b'\r\n', b'\n')
    c.contract_path.write_bytes(raw)
    assert c.run() == enabled
    c.contract_path.write_bytes(raw.replace(b'\n', b'\r\n'))
    assert c.run() == enabled
    c.contract_path.write_bytes(raw + b'# approved annotation\n')
    changed = c.run()
    assert changed != enabled
    c.set(0, 'comment', 'changed')
    c.write()
    assert c.run() != enabled


@pytest.mark.parametrize('damage', ['parquet', 'contract', 'quarantine', 'quarantine_hash',
                                    'src_row', 'original_row', 'counts', 'columns', 'identity'])
def test_e9_validate_tamper(extension_case, damage):
    c = extension_case
    path = c.run()
    manifest_path = path / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    entry = manifest['sources']['orders_enriched']
    parquet = path / 'orders_enriched.parquet'
    if damage == 'parquet':
        raw = bytearray(parquet.read_bytes())
        raw[20] ^= 1
        parquet.write_bytes(raw)
    elif damage == 'contract':
        c.contract_path.write_bytes(c.contract_path.read_bytes() + b'# change\n')
    elif damage == 'quarantine':
        (path / 'cach_ly/orders_enriched.csv').unlink()
    elif damage == 'quarantine_hash':
        (path / 'cach_ly/orders_enriched.csv').write_text('changed', encoding='utf-8')
    elif damage in ('src_row', 'original_row', 'columns'):
        table = pq.read_table(parquet)
        if damage == 'columns':
            table = table.drop(['comment'])
        else:
            col = '_src_row' if damage == 'src_row' else '_dong_goc'
            import pyarrow as pa
            table = table.set_column(table.column_names.index(col), col, pa.array([2] * 200))
        pq.write_table(table, parquet)
        entry['parquet_sha256'] = ep.digest(parquet)
    elif damage == 'counts':
        entry['so_dong_cach_ly'] = 1
    else:
        manifest['snapshot_id'] = '0' * 12
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError):
        snapshot.validate(path, c.contract, c.folder)


def test_empty_file_stops(extension_case):
    c = extension_case
    c.rows = []
    c.write()
    with pytest.raises(ValueError, match='0 dòng'):
        c.run()


def test_r4_typed_normalization_and_null_equality(extension_case):
    c = extension_case
    c.set(0, 'customer_id', ' 01 ')
    c.set(0, 'order_status', '')
    c.core[0][4] = ''
    c.write()
    assert c.entry(c.run())['so_dong_cach_ly'] == 0


def test_r6_null_is_value(extension_case):
    c = extension_case
    next(col for col in c.doc['cot'] if col['ten'] == 'years_experience')['duoc_rong'] = True
    c.set(0, 'years_experience', '')
    c.write()
    assert c.entry(c.run())['cach_ly'] == {ep.R6: 2}
