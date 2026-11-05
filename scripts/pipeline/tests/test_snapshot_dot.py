"""Tương thích snapshot cũ và cổng CLI của đợt tổng hợp."""
import csv
import hashlib
import json
from pathlib import Path
import sys

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.ingest.tests.test_dot import case, second_batch
from scripts.pipeline import snapshot, cli


def test_legacy_bytes_independent_reference(case, tmp_path):
    # Tái dựng định dạng cũ độc lập, không gọi helper của snapshot mới.
    reference = tmp_path / 'reference'
    reference.mkdir()
    entries = {}
    for name, (header, count) in case.spec.items():
        source = case.data / (name + '.csv')
        # Fixture đường cũ không có BOM, đúng hợp đồng CSV lõi.
        source.write_bytes(source.read_bytes().removeprefix(b'\xef\xbb\xbf'))
        with source.open(encoding='utf-8', newline='') as stream:
            rows = list(csv.reader(stream))[1:]
        table = pa.table({**{h: pa.array([r[j] or None for r in rows], pa.string()) for j, h in enumerate(header)},
                          '_src_row': pa.array(range(1, count + 1), pa.int64())})
        parquet = reference / (name + '.parquet')
        pq.write_table(table, parquet)
        entries[name] = {'header': header, 'rows': count, 'csv_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                         'csv_md5': hashlib.md5(source.read_bytes()).hexdigest(),
                         'parquet_sha256': hashlib.sha256(parquet.read_bytes()).hexdigest()}
    expected_id = hashlib.sha256(''.join(f"{n}:{entries[n]['csv_sha256']};" for n in sorted(entries)).encode()).hexdigest()[:12]
    (reference / 'manifest.json').write_text(json.dumps({'snapshot_id': expected_id, 'sources': entries},
                                                      ensure_ascii=False, indent=2), encoding='utf-8')
    path = case.run([])
    assert path.name == expected_id
    assert {p.name: p.read_bytes() for p in path.iterdir()} == {p.name: p.read_bytes() for p in reference.iterdir()}
    assert 'dot' not in snapshot.validate(path, case.spec)
    assert 'co_du_lieu_tong_hop' not in snapshot.validate(path, case.spec)


@pytest.fixture
def cli_case(case, monkeypatch):
    monkeypatch.setattr(snapshot, 'SOURCES', case.spec)
    return case


def prepare(c, run='batch', **kwargs):
    return cli.execute('prepare', run_id=run, root=c.landing.parent / 'pipeline', data=c.data, **kwargs)


@pytest.mark.parametrize('stage', ['forecast', 'build', 'validate', 'publish'])
@pytest.mark.parametrize('entry', ['direct', 'snapshot_id', 'prepared', 'forecasted', 'built', 'validated'])
def test_stages_blocked_from_manifest(cli_case, stage, entry):
    c = cli_case
    ctx = prepare(c, dots=[c.batch])
    if entry == 'snapshot_id':
        ctx = prepare(c, 'by-id', snapshot_id=ctx['snapshot_id'])
    elif entry != 'direct':
        ctx.pop('dot')
        ctx.pop('co_du_lieu_tong_hop')
        ctx['stage'] = entry
        Path(ctx['directory'], 'context.json').write_text(json.dumps(ctx), encoding='utf-8')
    with pytest.raises(ValueError, match='snapshot có đợt chưa dùng được ở stage này'):
        cli.execute(stage, run_id=ctx['run_id'], root=c.landing.parent / 'pipeline')


@pytest.mark.parametrize('stage', ['forecast', 'build', 'validate', 'publish'])
@pytest.mark.parametrize('status', ['published', 'skipped'])
def test_terminal_context_returns_without_registry_change(cli_case, monkeypatch, stage, status):
    c = cli_case
    ctx = prepare(c, dots=[c.batch])
    ctx.pop('dot')
    ctx.pop('co_du_lieu_tong_hop')
    ctx['stage'] = status
    ctx['code_version'] = 'old-revision'
    context_path = Path(ctx['directory'], 'context.json')
    context_path.write_text(json.dumps(ctx), encoding='utf-8')
    root = c.landing.parent / 'pipeline'
    before = (root / 'state.json').read_bytes()
    context_before = context_path.read_bytes()
    monkeypatch.setattr(snapshot, 'validate', lambda *a, **k: pytest.fail('Không đọc snapshot sau trạng thái cuối'))
    monkeypatch.setattr(cli, 'code_version', lambda: pytest.fail('Không kiểm code sau trạng thái cuối'))
    assert cli.execute(stage, run_id=ctx['run_id'], root=root) == ctx
    assert (root / 'state.json').read_bytes() == before
    assert context_path.read_bytes() == context_before


@pytest.mark.parametrize('stage', ['forecast', 'build', 'validate', 'publish'])
def test_legacy_skipped_missing_snapshot_returns(cli_case, stage):
    c = cli_case
    ctx = prepare(c)
    ctx.update(stage='skipped', snapshot_path=str(c.landing.parent / 'already-removed'), code_version='old-revision')
    Path(ctx['directory'], 'context.json').write_text(json.dumps(ctx), encoding='utf-8')
    root = c.landing.parent / 'pipeline'
    before = (root / 'state.json').read_bytes()
    assert cli.execute(stage, run_id=ctx['run_id'], root=root) == ctx
    assert (root / 'state.json').read_bytes() == before


def test_code_version_checked_before_snapshot(cli_case, monkeypatch):
    c = cli_case
    ctx = prepare(c)
    ctx['code_version'] = 'old-revision'
    Path(ctx['directory'], 'context.json').write_text(json.dumps(ctx), encoding='utf-8')
    monkeypatch.setattr(snapshot, 'validate', lambda *a, **k: pytest.fail('Phải kiểm code trước snapshot'))
    with pytest.raises(ValueError, match='Code đổi giữa các stage'):
        cli.execute('forecast', run_id=ctx['run_id'], root=c.landing.parent / 'pipeline')


@pytest.mark.parametrize('stage', ['forecast', 'build', 'validate', 'publish', 'run'])
def test_execute_direct_rejects_dots_for_other_stages(tmp_path, stage):
    with pytest.raises(ValueError, match='--dot chỉ dùng với prepare local'):
        cli._execute(stage, run_id='invalid', root=tmp_path / 'pipeline', dots=[tmp_path / 'batch'])
    assert not (tmp_path / 'pipeline').exists()


@pytest.mark.parametrize('mode', ['drop', 'change', 'reorder'])
def test_run_id_cannot_change_batches(cli_case, mode):
    c = cli_case
    second = second_batch(c)
    prepare(c, dots=[c.batch, second])
    requested = [] if mode == 'drop' else [second] if mode == 'change' else [second, c.batch]
    with pytest.raises(ValueError, match='danh sách --dot khác'):
        prepare(c, dots=requested)


def test_run_id_compares_hash_not_path(cli_case, tmp_path):
    import shutil
    c = cli_case
    first = prepare(c, dots=[c.batch])
    renamed = tmp_path / 'same-content'
    shutil.copytree(c.batch, renamed)
    assert prepare(c, dots=[renamed]) == first


@pytest.mark.parametrize('args', [['forecast'], ['build'], ['validate'], ['publish'], ['run'],
    ['prepare', '--target', 'databricks'], ['prepare', '--snapshot-id', 'abcdef123456']])
def test_parser_rejects_invalid_dot_options(monkeypatch, args):
    monkeypatch.setattr(sys, 'argv', ['pipeline', *args, '--run-id', 'x', '--dot', 'unused'])
    monkeypatch.setattr(cli, 'execute', lambda *a, **k: pytest.fail('Không được gọi stage'))
    with pytest.raises(SystemExit) as caught:
        cli.main()
    assert caught.value.code == 2


def test_prepare_error_writes_summary_without_snapshot(cli_case):
    c = cli_case
    c.change('order_items', 'quantity', 'PII_ERROR_SENTINEL')
    with pytest.raises(ValueError, match='D2-0') as caught:
        prepare(c, dots=[c.batch])
    assert 'PII_ERROR_SENTINEL' not in str(caught.value)
    root = c.landing.parent / 'pipeline'
    summary = (root / 'runs/batch/quarantine/summary.json').read_text(encoding='utf-8')
    assert 'D2-0' in summary and 'PII_ERROR_SENTINEL' not in summary
    assert not list((root / 'snapshots').iterdir())
