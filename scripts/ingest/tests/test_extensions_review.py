"""B1–B4: ghim lỗi rà lát 2 và các chốt bổ sung."""
from contextlib import contextmanager
import sys

import pyarrow.parquet as pq
import pytest
import yaml

from scripts.ingest.tests.test_extensions import extension_case
from scripts.ingest import extension_contract as ec, extension_prepare as ep
from scripts.pipeline import cli


def test_b1_invalid_keys_are_not_duplicates(extension_case):
    c = extension_case
    c.set(0, 'order_id', 'abc')
    c.set(1, 'order_id', '')
    c.write()
    assert c.entry(c.run())['cach_ly'] == {ep.R1: 2}


def test_b2_null_differs_from_core_value(extension_case):
    c = extension_case
    c.set(0, 'order_status', '')
    c.write()
    assert c.entry(c.run())['cach_ly'] == {ep.R4: 1}


def test_b3_parquet_preserves_source_spaces(extension_case):
    c = extension_case
    c.set(0, 'sales_employee_id', ' EMP1 ')
    c.set(0, 'years_experience', ' 5 ')
    c.set(0, 'order_status', ' Delivered ')
    c.set(0, 'comment', '   ')
    c.write()
    path = c.run()
    assert c.entry(path)['cach_ly'] == {}
    table = pq.read_table(path / 'orders_enriched.parquet')
    assert table['sales_employee_id'][0].as_py() == ' EMP1 '
    assert table['years_experience'][0].as_py() == ' 5 '
    assert table['comment'][0].as_py() == '   '
    assert table['comment'][1].as_py() is None


@pytest.mark.parametrize('guard', ['threshold', 'file'])
def test_b4_validate_guards(extension_case, guard):
    c = extension_case
    path = c.run()
    entry = c.entry(path)
    if guard == 'threshold':
        # Giữ đúng tổng và parquet; chỉ tỷ lệ cách ly bị vượt.
        entry['so_dong_file'] = 203
        entry['so_dong_cach_ly'] = 3
        match = 'ngưỡng'
    else:
        entry['file'] = 'student_data/other.csv'
        match = 'hợp đồng'
    with pytest.raises(ValueError, match=match):
        ep.validate(path, 'orders_enriched', entry, c.folder)


@pytest.mark.parametrize('guard,field', [
    ('parent_path', 'file'), ('key_type', 'khoa_noi.kieu'),
    ('duplicate_header', 'header'), ('reserved_header', 'header'),
    ('entity_key', 'thuc_the'), ('entity_attribute', 'thuc_the'),
])
def test_b4_contract_guards(extension_case, guard, field):
    c = extension_case
    if guard == 'parent_path':
        c.doc['file'] = '../orders_enriched.csv'
    elif guard == 'key_type':
        c.doc['cot'][0]['kieu'] = 'string'
    elif guard == 'duplicate_header':
        c.doc['header'].append('comment')
        c.doc['cot'].append(dict(c.doc['cot'][-1]))
    elif guard == 'reserved_header':
        c.doc['header'][-1] = '_comment'
        c.doc['cot'][-1]['ten'] = '_comment'
    elif guard == 'entity_key':
        c.doc['thuc_the'][0]['khoa'] = 'order_id'
    else:
        c.doc['thuc_the'][0]['thuoc_tinh'] = ['order_status']
    # Chỉ ghi hợp đồng thử, không đi theo đường dẫn nguồn không hợp lệ.
    c.contract_path.write_text(yaml.safe_dump(c.doc), encoding='utf-8')
    with pytest.raises(ValueError, match=field) as error:
        ec.load('orders_enriched', c.folder)
    assert 'orders_enriched.yml' in str(error.value)


def test_b4_extension_wrong_stage(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(sys, 'argv', ['cli', 'history', '--root', str(tmp_path),
                                    '--extension', 'orders_enriched'])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    assert '--extension chỉ dùng với prepare hoặc run' in capsys.readouterr().err


@pytest.mark.parametrize('phase', ['read', 'prepare'])
def test_b4_source_changes(extension_case, monkeypatch, phase):
    c = extension_case
    source = c.data / c.doc['file']
    if phase == 'read':
        original_read = ep.read_file

        @contextmanager
        def changing_read(path):
            with original_read(path) as table:
                source.write_bytes(source.read_bytes() + b'\n')
                yield table

        monkeypatch.setattr(ep, 'read_file', changing_read)
    else:
        original_prepare = ep.prepare

        def changing_prepare(*args):
            # Đổi sau hash định danh, trước khi adapter đọc: chốt trong adapter không bắt.
            c.set(0, 'comment', 'changed')
            c.write()
            return original_prepare(*args)

        monkeypatch.setattr(ep, 'prepare', changing_prepare)
    with pytest.raises(ValueError, match='nguồn đổi trong lúc ' + ('đọc' if phase == 'read' else phase)):
        c.run()
    assert not list(c.landing.glob('*/manifest.json'))
