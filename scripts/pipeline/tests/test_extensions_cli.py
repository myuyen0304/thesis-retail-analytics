"""E7, E11, E12: nối CLI, retry, bằng chứng và giữ ngưỡng 0 của lõi."""
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.ingest.tests.test_extensions import extension_case
from scripts.ingest.source_contract import COLUMNS
from scripts.ingest import extension_prepare as ep
from scripts.pipeline import cli, contract, snapshot


@pytest.fixture
def cli_case(extension_case, monkeypatch, tmp_path):
    c = extension_case
    monkeypatch.setattr(snapshot, 'SOURCES', c.contract)
    monkeypatch.setattr(contract, 'COLUMNS', {'orders': COLUMNS['orders']})
    monkeypatch.setattr(contract, 'KEYS', {'orders': ['order_id']})
    monkeypatch.setattr(cli, 'code_version', lambda: 'fixed-version')
    c.root = tmp_path / 'pipeline'
    c.execute = lambda run_id, extensions=(), **kw: cli.execute(
        'prepare', run_id=run_id, data=c.data, root=c.root, extensions=extensions, **kw)
    return c


def test_e11_disabled_context_unchanged(cli_case):
    c = cli_case
    context = c.execute('disabled')
    assert set(context) == {'run_id', 'target', 'release_id', 'snapshot_id', 'snapshot_path', 'code_version',
                            'directory', 'duckdb_path', 'schema', 'expected_active', 'started_at', 'stage'}
    before = (c.root / 'runs/disabled/context.json').read_bytes()
    assert c.execute('disabled') == context
    assert (c.root / 'runs/disabled/context.json').read_bytes() == before
    with pytest.raises(ValueError, match='extension'):
        c.execute('disabled', ['orders_enriched'])


def test_e11_enabled_context_retry_and_history(cli_case, capsys):
    c = cli_case
    c.set(0, 'years_experience', 'abc')
    c.write()
    context = c.execute('enabled', ['orders_enriched', 'orders_enriched'])
    assert context['extensions'] == ['orders_enriched']
    assert context['so_dong_cach_ly'] == {'orders_enriched': 1}
    assert c.execute('enabled', ['orders_enriched']) == context
    with pytest.raises(ValueError, match='extension'):
        c.execute('enabled')
    cli.print_history(c.root)
    assert 'orders_enriched": 1' in capsys.readouterr().out


@pytest.mark.parametrize('enabled', [False, True])
def test_e11_snapshot_extension_set(cli_case, enabled):
    c = cli_case
    extensions = ['orders_enriched'] if enabled else []
    context = c.execute('first', extensions)
    with pytest.raises(ValueError, match='extension'):
        c.execute('mismatch', [] if enabled else ['orders_enriched'], snapshot_id=context['snapshot_id'])
    assert c.execute('matched', extensions, snapshot_id=context['snapshot_id'])['stage'] == 'prepared'


def test_e7_cli_threshold_evidence(cli_case):
    c = cli_case
    for i in range(3):
        c.set(i, 'years_experience', 'abc')
    c.write()
    with pytest.raises(ValueError, match='3/200'):
        c.execute('bad', ['orders_enriched'])
    folder = c.root / 'runs/bad'
    assert not (folder / 'context.json').exists()
    assert not list((c.root / 'snapshots').glob('*/manifest.json'))
    summary = json.loads((folder / 'quarantine/summary.json').read_text(encoding='utf-8'))
    assert summary['dong_sai'] == {'orders_enriched': {ep.R5: 3}}
    import csv
    with (folder / 'quarantine/orders_enriched.csv').open(encoding='utf-8') as stream:
        evidence = list(csv.DictReader(stream))
    assert {r['_dong_goc'] for r in evidence} == {'1', '2', '3'}
    assert all(r['years_experience'] == 'abc' for r in evidence)


def test_e12_core_type_still_stops(cli_case):
    c = cli_case
    c.core[0][2] = 'abc'
    c.write()
    with pytest.raises(ValueError, match='sai hợp đồng'):
        c.execute('bad-core', ['orders_enriched'])
    summary = json.loads((c.root / 'runs/bad-core/quarantine/summary.json').read_text(encoding='utf-8'))
    assert 'orders' in summary['dong_sai']
    assert not (c.root / 'runs/bad-core/context.json').exists()


def test_cli_parser_extension(cli_case, monkeypatch):
    c = cli_case
    monkeypatch.setattr(sys, 'argv', ['cli', 'prepare', '--run-id', 'parser', '--root', str(c.root),
                                    '--data', str(c.data), '--extension', 'orders_enriched'])
    cli.main()
    context = json.loads((c.root / 'runs/parser/context.json').read_text(encoding='utf-8'))
    assert context['extensions'] == ['orders_enriched']
