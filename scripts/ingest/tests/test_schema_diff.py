"""U7–U8: thứ tự tương đối và ứng viên đổi tên không thay thế quyết định BA."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.ingest.adapters import read_file
from scripts.ingest.schema_diff import compare_columns, infer_types


@pytest.mark.parametrize('columns,kind,changed,added,missing', [
    (['a', 'b'], 'khop', False, [], []),
    (['a', 'b', 'c'], 'additive', False, ['c'], []),
    (['a', 'c', 'b'], 'additive', False, ['c'], []),
    (['b', 'a'], 'additive', True, [], []),
    (['a'], 'breaking', False, [], ['b']),
    (['\ufeff A ', ' B'], 'khop', False, [], []),
])
def test_u7_relative_order(columns, kind, changed, added, missing):
    result = compare_columns(columns, ['a', 'b'])
    assert (result['kind'], result['order_changed']) == (kind, changed)
    assert result['added'] == added and result['missing'] == missing
    assert result['matched'] == [c for c in columns if c not in added]


def test_u8_rename_requires_compatible_type(tmp_path):
    path = tmp_path / 'orders.csv'
    path.write_text('orderdate,order_date_text,unknown\n2022-01-01,no,\n2022-02-01,no,\n', encoding='utf-8')
    with read_file(path) as data:
        types = infer_types(data, data.columns)
        assert types == {'orderdate': 'date', 'order_date_text': 'string', 'unknown': 'unknown'}
        result = compare_columns(data.columns, ['order_date'], types, {'order_date': ('date', False)})
    assert result['kind'] == 'breaking' and result['missing'] == ['order_date']
    assert result['matched'] == []
    assert result['rename_candidates'] == [{'cot_thieu': 'order_date', 'ung_vien': 'orderdate',
                                          'diem': 0.9474, 'kieu_suy_duoc': 'date', 'trang_thai': 'de_xuat'}]


def test_inferred_numeric_types(tmp_path):
    path = tmp_path / 'numbers.csv'
    path.write_text('i,f,s\n1,1.2,word\n2,3.1,42\n', encoding='utf-8')
    with read_file(path) as data:
        assert infer_types(data, data.columns) == {'i': 'integer', 'f': 'double', 's': 'string'}
