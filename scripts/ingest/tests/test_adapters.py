"""U1–U6: đọc dữ liệu ngoài, giữ nguyên giá trị và báo lỗi rõ."""
import codecs
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.ingest.adapters import read_file, quote


@pytest.mark.parametrize('bom', [True, False])
def test_u1_u2_bom_metadata(tmp_path, bom):
    path = tmp_path / 'file.csv'
    raw = (codecs.BOM_UTF8 if bom else b'') + b'id,value\n1,  a  \n'
    path.write_bytes(raw)
    with read_file(path) as table:
        assert table.has_bom is bom
        assert table.encoding == ('utf-8-sig' if bom else 'utf-8')
        assert table.columns == ['id', 'value']
        assert table.name == path.name and table.path == path
        assert table.format == 'csv' and table.n_rows == 1
        assert table.sha256 == hashlib.sha256(raw).hexdigest()
        assert table.con.execute(f'select * from {quote(table.table)}').fetchall() == [('1', '  a  ')]
        assert [r[1] for r in table.con.execute(f'describe {quote(table.table)}').fetchall()] == ['VARCHAR'] * 2


def test_u3_non_utf8_even_after_sample(tmp_path):
    path = tmp_path / 'bad.csv'
    path.write_bytes(b'id\n' + b'a\n' * 600000 + b'\xff\n')
    with pytest.raises(ValueError, match='bad.csv.*UTF-8.*1200003'):
        read_file(path)


@pytest.mark.parametrize('raw', [b'id\n\xe2', b'id\n\xc0\xaf'])
def test_incomplete_or_invalid_utf8(tmp_path, raw):
    path = tmp_path / 'bad.csv'
    path.write_bytes(raw)
    with pytest.raises(ValueError, match='UTF-8'):
        read_file(path)


def test_u4_u5_json_preserves_values_and_union(tmp_path):
    path = tmp_path / 'nested.json'
    path.write_text(json.dumps([{'s': '  a  ', 'n': 12, 'b': True, 'obj': {'a': [1, False]}},
                               {'s': '', 'n': None, 'new': 2.5}, {'s': None, 'b': False}]), encoding='utf-8')
    with read_file(path) as table:
        assert table.columns == ['s', 'n', 'b', 'obj', 'new']
        assert table.n_rows == 3
        assert [r[1] for r in table.con.execute(f'describe {quote(table.table)}').fetchall()] == ['VARCHAR'] * 5
        rows = table.con.execute(f'select * from {quote(table.table)}').fetchall()
        assert rows == [('  a  ', '12', 'true', '{"a":[1,false]}', None),
                        ('', None, None, None, '2.5'), (None, None, 'false', None, None)]


@pytest.mark.parametrize('value', [{'a': 1}, [1, 2], [None], [{'a': 1}, False]])
def test_u6_reject_non_object_array(tmp_path, value):
    path = tmp_path / 'bad.json'
    path.write_text(json.dumps(value), encoding='utf-8')
    with pytest.raises(ValueError, match='mảng đối tượng'):
        read_file(path)


@pytest.mark.parametrize('value,n', [([], 0), ([{}, {}], 2)])
def test_json_empty_objects(tmp_path, value, n):
    path = tmp_path / 'empty.json'
    path.write_text(json.dumps(value), encoding='utf-8')
    with read_file(path) as table:
        assert table.columns == [] and table.n_rows == n


def test_csv_empty_values(tmp_path):
    path = tmp_path / 'empty.csv'
    path.write_text('a,b,c\n1,,""\n', encoding='utf-8')
    with read_file(path) as table:
        assert table.con.execute(f'select * from {quote(table.table)}').fetchall() == [('1', None, None)]


@pytest.mark.parametrize('header', ['id, ID ', ',id'])
def test_reject_ambiguous_headers(tmp_path, header):
    path = tmp_path / 'bad.csv'
    path.write_text(header + '\n1,2\n', encoding='utf-8')
    with pytest.raises(ValueError, match='Tên cột'):
        read_file(path)


def test_unsupported_extension(tmp_path):
    with pytest.raises(ValueError, match='CSV hoặc JSON'):
        read_file(tmp_path / 'outside.py')


@pytest.mark.parametrize('content,key', [
    ('[{"a": "y", "a": "x"}]', 'a'),
    ('[{"o": {"k": 1, "k": 2}}]', 'k'),
])
def test_json_reject_duplicate_keys(tmp_path, content, key):
    path = tmp_path / 'duplicate.json'
    path.write_text(content, encoding='utf-8')
    with pytest.raises(ValueError) as exc:
        with read_file(path):
            pass
    assert path.name in str(exc.value)
    assert repr(key) in str(exc.value)
