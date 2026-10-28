"""Fixture nhỏ không phụ thuộc data/; dữ liệu thật chỉ dùng ở nhóm tích hợp."""
import csv
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def write_csv(path, columns, rows, encoding='utf-8'):
    with path.open('w', encoding=encoding, newline='') as stream:
        csv.writer(stream).writerows([columns, *rows])
    return path


@pytest.fixture
def enriched(tmp_path):
    from scripts.ingest.source_contract import SOURCES
    data_dir = tmp_path / 'refs'
    data_dir.mkdir()
    write_csv(data_dir / 'geography.csv', ['zip', 'city', 'region', 'district'],
              [['10', 'A', 'R1', 'D1'], ['20', 'B', 'R2', 'D2']])
    write_csv(data_dir / 'customers.csv', SOURCES['customers'][0],
              [[str(i + 1), str(10 * (i % 2 + 1)), 'AB'[i % 2], '2020-01-01', 'F', 'adult', 'web'] for i in range(30)])
    columns = SOURCES['orders'][0] + ['city', 'region', 'district', 'employee_id', 'employee_name',
                                     'level', 'comment', 'marital_status', 'education_level', 'years_experience']
    rows = [[str(i + 1), '2022-01-01', str(i + 1), str(10 * (i % 2 + 1)), 'delivered', 'card', 'mobile', 'web',
             'AB'[i % 2], 'R' + str(i % 2 + 1), 'D' + str(i % 2 + 1), str(i % 3), 'Tên ' + str(i % 3),
             'L' + str(i % 3), 'note ' + str(i % 5), 'single', 'college', str(i % 3 + 1)] for i in range(30)]
    path = write_csv(tmp_path / 'orders_enriched.csv', columns, rows, 'utf-8-sig')
    return path, data_dir, columns, rows
