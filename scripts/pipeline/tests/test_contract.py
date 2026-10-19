"""A3 (bước S4, 2026-10-19): hợp đồng dữ liệu bản gọn ở stage prepare.

Dữ liệu thật có SHA-256 ổn định và luôn đạt hợp đồng, nên test đột biến dùng CSV tạm và hợp đồng tạm. Không sửa data/.
"""
import csv
import json
import re
from pathlib import Path
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'apps/retail_app'))
from scripts.ingest import source_contract
from scripts.ingest.source_contract import COLUMNS, KEYS, SOURCES
from scripts.pipeline import cli, contract, snapshot
from scripts.pipeline.state import Registry

STAGING = ROOT / 'retail_dbt/models/staging'
REAL = ROOT / 'warehouse/pipeline/snapshots/5bd9a84aaf73'


# --- đối chiếu với dbt ---

def test_nguon_cua_hop_dong_khop_sources_yml():
    raw = next(s for s in yaml.safe_load((STAGING / '_sources.yml').read_text(encoding='utf-8'))['sources']
               if s['name'] == 'raw')
    assert {t['name'] for t in raw['tables']} == set(SOURCES) == set(COLUMNS) == set(KEYS)


def _staging_types(name):
    """Kiểu từng cột theo model staging: cast({{ clean('c') }} as T) → T; {{ clean('c') }} không cast → 'string'."""
    sql = (STAGING / f'stg_{name}.sql').read_text(encoding='utf-8')
    sql = '\n'.join(line.split('--')[0] for line in sql.splitlines())
    col = r"clean\((?:adapter\.quote\()?'(\w+)'\)?\)"
    out = {c: 'string' for c in re.findall(r'\{\{\s*' + col + r'\s*\}\}', sql)}
    for c, kind in re.findall(r'cast\(\{\{\s*' + col + r'\s*\}\}\s+as\s+(.+?)\)\s+as\s', sql):
        kind = re.sub(r'\s+', '', kind.replace('{{type_double()}}', 'double').replace('{{ type_double() }}', 'double'))
        out[c] = kind
    return out


@pytest.mark.parametrize('name', sorted(SOURCES))
def test_cot_va_kieu_khop_cast_o_staging(name):
    assert list(COLUMNS[name]) == SOURCES[name][0]                     # đủ cột, đúng thứ tự header
    staging = _staging_types(name)
    assert staging, name
    for col, (kind, _) in COLUMNS[name].items():
        assert kind == staging.get(col, 'string'), (name, col, kind, staging.get(col))
    assert KEYS[name] is None or set(KEYS[name]) <= set(COLUMNS[name])


def test_snapshot_that_dat_hop_dong_va_giu_snapshot_id(tmp_path):
    if not REAL.exists():
        pytest.skip('chưa có snapshot 5bd9a84aaf73 trong warehouse/pipeline/snapshots')
    assert snapshot.validate(REAL)['snapshot_id'] == '5bd9a84aaf73'
    assert contract.check(REAL, tmp_path / 'q') == {}
    assert not (tmp_path / 'q').exists()


# --- đột biến: CSV tạm + hợp đồng tạm, chạy qua stage prepare của CLI ---

HEADER = ['id', 'qty', 'day', 'note']
TMP_COLUMNS = {'items': {'id': ('integer', False), 'qty': ('integer', False), 'day': ('date', False),
                         'note': ('string', True)}}
GOOD = [['1', '5', '2022-01-01', ''], ['2', '7', '2022-01-02', 'x'], ['3', '9', '2022-01-03', '']]


def _prepare(tmp_path, monkeypatch, rows, header=HEADER):
    data = tmp_path / 'data'
    data.mkdir(exist_ok=True)
    with (data / 'items.csv').open('w', encoding='utf-8', newline='') as f:
        csv.writer(f).writerows([header, *rows])
    monkeypatch.setattr(snapshot, 'SOURCES', {'items': (HEADER, len(rows))})
    monkeypatch.setattr(contract, 'COLUMNS', TMP_COLUMNS)
    monkeypatch.setattr(contract, 'KEYS', {'items': ['id']})
    monkeypatch.setattr(cli, 'code_version', lambda: 'v1')
    root = tmp_path / 'root'
    return root, lambda: cli.execute('prepare', run_id='demo', root=root, data=data)


def test_du_lieu_dung_qua_prepare_khong_co_quarantine(tmp_path, monkeypatch):
    root, run = _prepare(tmp_path, monkeypatch, GOOD)
    assert run()['stage'] == 'prepared'
    assert not (root / 'runs/demo/quarantine').exists()


@pytest.mark.parametrize('row,src_row,reason', [
    (['2', 'abc', '2022-01-02', 'x'], 2, 'không ép được sang integer: qty'),           # sai kiểu
    (['2', '7', '2022-13-40', 'x'], 2, 'không ép được sang date: day'),                # ngày không có thật
    (['2', '7', '', 'x'], 2, 'rỗng ở cột không được rỗng day'),                         # null ở cột not-null
    (['2', '  ', '2022-01-02', 'x'], 2, 'rỗng ở cột không được rỗng qty'),              # chỉ có khoảng trắng = rỗng
    (['1', '7', '2022-01-02', 'x'], 1, 'trùng khóa chính (id)'),                        # khóa trùng
])
def test_dong_sai_dung_truoc_build_co_quarantine_va_lich_su(tmp_path, monkeypatch, row, src_row, reason):
    rows = [GOOD[0], row, GOOD[2]]
    root, run = _prepare(tmp_path, monkeypatch, rows)
    with pytest.raises(ValueError, match='sai hợp đồng'):           # ValueError → __main__ exit 2, Airflow không retry
        run()
    folder = root / 'runs/demo'
    assert not (folder / 'context.json').exists()                   # không có run prepared nên build không chạy được
    summary = json.loads((folder / 'quarantine/summary.json').read_text(encoding='utf-8'))
    assert reason in summary['dong_sai']['items']
    with (folder / 'quarantine/items.csv').open(encoding='utf-8') as f:
        bad = list(csv.DictReader(f))
    assert any(r['_src_row'] == str(src_row) and r['ly_do'] == reason for r in bad)
    assert all(set(HEADER) <= set(r) for r in bad)                  # ghi cả dòng gốc
    assert len([r for r in bad if r['ly_do'] == reason]) == (2 if 'trùng' in reason else 1)  # không bỏ / sửa dòng nào
    assert json.loads((folder / 'failure.json').read_text())['stage'] == 'prepare'
    hist = [json.loads(x) for x in (root / 'history.jsonl').read_text(encoding='utf-8').splitlines()]
    assert [(h['stage'], h['result'], h['error_type']) for h in hist] == [('prepare', 'loi', 'ValueError')]
    assert Registry(root).read()['payload']['active'] is None
    with pytest.raises(FileNotFoundError):
        cli.execute('build', run_id='demo', root=root)


def test_doi_ten_cot_dung_o_header_co_quarantine(tmp_path, monkeypatch):
    root, run = _prepare(tmp_path, monkeypatch, GOOD, header=['id', 'qty2', 'day', 'note'])
    with pytest.raises(ValueError, match='header'):
        run()
    summary = json.loads((root / 'runs/demo/quarantine/summary.json').read_text(encoding='utf-8'))
    assert 'header' in summary['loi'] and summary['dong_sai'] == {}
    assert not (root / 'snapshots').exists() or not any((root / 'snapshots').iterdir())   # không snapshot nào được ghi
    hist = [json.loads(x) for x in (root / 'history.jsonl').read_text(encoding='utf-8').splitlines()]
    assert hist[-1]['result'] == 'loi'


def test_snapshot_id_cu_van_chay_va_duoc_kiem(tmp_path, monkeypatch):
    # --snapshot-id: snapshot có sẵn cũng đi qua hợp đồng (dữ liệu dựng trước khi có hợp đồng mới)
    root, run = _prepare(tmp_path, monkeypatch, GOOD)
    sid = run()['snapshot_id']
    context = cli.execute('prepare', run_id='demo2', root=root, snapshot_id=sid)
    assert context['snapshot_id'] == sid and context['stage'] in ('prepared', 'skipped')
    monkeypatch.setattr(contract, 'KEYS', {'items': ['qty', 'day', 'note', 'id']})   # đổi hợp đồng: vẫn kiểm lại
    monkeypatch.setattr(contract, 'COLUMNS', {'items': {**TMP_COLUMNS['items'], 'note': ('string', False)}})
    with pytest.raises(ValueError, match='sai hợp đồng'):
        cli.execute('prepare', run_id='demo3', root=root, snapshot_id=sid)
    assert source_contract.SOURCES is SOURCES                                        # hợp đồng thật không bị đổi
