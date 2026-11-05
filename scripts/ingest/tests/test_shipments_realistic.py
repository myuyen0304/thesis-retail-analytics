"""Hợp đồng B2 và phân loại B5; chỉ đọc dữ liệu, output nằm trong tmp_path."""
from copy import deepcopy
from pathlib import Path
import duckdb
import pytest
from scripts.ingest import extension_contract, extension_prepare, auto_mapping, tu_dong

ROOT = Path(__file__).resolve().parents[3]

@pytest.mark.parametrize('relative,expected', [('student_data/shipments_realistic.csv', 566067),
                                             ('student_data/demo_2022/shipments_realistic.csv', 30211)])
def test_b2_real_contract_zero_quarantine(tmp_path, relative, expected):
    if not (ROOT / 'data' / relative).is_file():
        pytest.skip('Thiếu file shipments để kiểm B2')
    doc = extension_contract.load('shipments_realistic')
    doc['file'] = relative
    ready = tmp_path / 'ready'
    ready.mkdir()
    with duckdb.connect() as con:
        con.execute("copy (select * from read_csv($1, header=true, all_varchar=true)) to $2 (format parquet)",
                    [str(ROOT / 'data/shipments.csv'), str(ready / 'shipments.parquet')])
        blank = ' + '.join(f'''sum(case when nullif(trim("{c}"), '') is null then 1 else 0 end)''' for c in doc['header'])
        assert con.execute('select ' + blank + ' from read_csv(?, header=true, all_varchar=true)',
                           [str(ROOT / 'data' / relative)]).fetchone()[0] == 0
    result = extension_prepare.prepare(doc, ROOT / 'data', ready)
    assert result['so_dong_cach_ly'] == 0
    assert result['rows'] == result['so_dong_file'] == expected
    assert len(doc['thuc_the'][0]['thuoc_tinh']) == 17
    assert all(c['duoc_rong'] is False for c in doc['cot'])
    assert len(doc['header']) == 22
    with duckdb.connect() as con:
        assert con.execute('select count(distinct shipper_id) from read_parquet(?)',
                           [str(ready / 'shipments_realistic.parquet')]).fetchone()[0] == 80


def test_b2_explicit_types_and_visibility():
    doc = extension_contract.load('shipments_realistic')
    columns = {c['ten']: c for c in doc['cot']}
    expected = {
        'order_id': 'integer', 'shipper_id': 'string', 'shipper_company': 'string',
        'shipper_vehicle': 'string', 'working_shift': 'string', 'shipper_name': 'string',
        'shipper_phone': 'string', 'city': 'string', 'region': 'string', 'district': 'string',
        'shipper_experience_years': 'integer', 'average_delivery_time': 'integer',
        'shipper_rating': 'double', 'delivery_success_rate': 'double', 'join_date': 'date',
        'shipper_gender': 'string', 'shipper_age': 'integer',
        'shipper_marital_status': 'string', 'shipper_education': 'string',
    }
    assert {n: c['kieu'] for n, c in columns.items() if 'kieu' in c} == expected
    assert doc['nguong_cach_ly'] == 0.01
    assert doc['file'] == 'student_data/shipments_realistic.csv'
    attributes = doc['thuc_the'][0]['thuoc_tinh']
    assert len(attributes) == 17
    assert set(attributes) == set(expected) - {'order_id', 'shipper_id'}
    assert {n for n, c in columns.items() if c.get('hien_thi') == 'silver'} == {
        'shipper_gender', 'shipper_age', 'shipper_marital_status', 'shipper_education'}
    assert {n for n, c in columns.items() if c['xu_ly'] == 'doi_chieu_loi'} == {
        'ship_date', 'delivery_date', 'shipping_fee'}
    assert all(columns[n]['hien_thi'] == 'mart' for n in expected if n != 'order_id'
               and n not in {'shipper_gender', 'shipper_age', 'shipper_marital_status', 'shipper_education'})


def test_b5_shipments_route_and_missing_column(tmp_path):
    from scripts.ingest.contract_registry import ContractRegistry
    file = ROOT / 'data/student_data/demo_2022/shipments_realistic.csv'
    if not file.is_file():
        pytest.skip('Thiếu file shipments để kiểm B5')
    doc = extension_contract.load('shipments_realistic')
    proposal = auto_mapping.propose(file, ROOT / 'data')
    registry = ContractRegistry(tmp_path)
    registry.write('shipments_realistic', doc, 'PM', 'test')
    contracts = registry.ung_vien(proposal)
    assert tu_dong.phan_loai(proposal, contracts, True)['ket_qua'] == 'tu_dong'
    missing = deepcopy(proposal)
    missing['cot'] = [c for c in missing['cot'] if c['ten_trong_file'] != 'shipper_rating']
    result = tu_dong.phan_loai(missing, registry.ung_vien(missing), True)
    assert result['ket_qua'] == 'can_nguoi'
    assert 'thieu_cot' in [r['ma'] for r in result['ly_do']]


@pytest.mark.parametrize('name', ['epd.json', 'tf.json', 'eprom.json'])
def test_b5_other_sources_still_need_review(tmp_path, name):
    from scripts.ingest.contract_registry import ContractRegistry
    file = ROOT / 'data/student_data' / name
    if not file.is_file():
        pytest.skip('Thiếu file đối chứng Phần B')
    registry = ContractRegistry(tmp_path)
    for extension in ('orders_enriched', 'shipments_realistic'):
        registry.write(extension, extension_contract.load(extension), 'PM', 'test')
    proposal = auto_mapping.propose(file, ROOT / 'data')
    result = tu_dong.phan_loai(proposal, registry.ung_vien(proposal), True)
    assert result['ket_qua'] == 'can_nguoi'
    assert 'chua_co_hop_dong' in [r['ma'] for r in result['ly_do']]
