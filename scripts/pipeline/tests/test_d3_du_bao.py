"""D3: dự báo đứng yên cho bản có đợt và các cổng CLI. Không train, không chạy dbt."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.forecast import stage as forecast_stage
from scripts.ingest.tests.test_dot import case, second_batch  # noqa: F401
from scripts.pipeline import cli, du_bao_dot, snapshot
from scripts.pipeline.state import Registry

RID = 'a' * 24
GOC = dt.date(2022, 12, 31)


def write_sales(path, start, end, offset=0.0):
    path.mkdir(parents=True, exist_ok=True)
    duckdb.sql(f"""copy (select strftime(d, '%Y-%m-%d') as "Date", cast(100 + {offset} as varchar) as "Revenue",
                   '80' as "COGS", row_number() over () as _src_row
                   from generate_series(date '{start}', date '{end}', interval 1 day) t(d))
                   to '{(path / 'sales.parquet').as_posix()}' (format parquet)""")


def hash_of(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rewrite_daily(base, select):
    daily = base.folder / 'forecast_daily.parquet'
    duckdb.sql(f"copy ({select}) to '{daily.as_posix()}' (format parquet)")
    base.meta['sha256'][daily.name] = hash_of(daily)
    (base.folder / 'forecast_meta.json').write_text(json.dumps(base.meta), encoding='utf-8')


@pytest.fixture
def base(tmp_path, monkeypatch):
    """Kho có một bản gốc đã kiểm và một lượt đợt 2023; snapshot.validate đọc manifest thay cho hash đầy đủ."""
    root = tmp_path / 'kho'
    registry = Registry(root)
    registry.initialize()
    source = root / 'snapshots' / 'bbbbbbbbbbbb'
    write_sales(source, '2012-07-04', GOC)
    (source / 'manifest.json').write_text(json.dumps({'snapshot_id': source.name}), encoding='utf-8')
    run = root / 'runs' / 'goc'
    folder = run / 'forecast'
    folder.mkdir(parents=True)
    duckdb.sql(f"""copy (select cast(d as date) as forecast_date, date '{GOC}' as trained_through, 1.0 as yhat
                   from generate_series(date '2023-01-01', date '2024-07-01', interval 1 day) t(d))
                   to '{(folder / 'forecast_daily.parquet').as_posix()}' (format parquet)""")
    for name in forecast_stage.FILES[1:]:
        (folder / name).write_bytes(b'noi dung ' + name.encode())
    meta = {'snapshot_id': source.name, 'model_version': forecast_stage.model_version(), 'run_id': 'goc',
            'primary': ['m', 'ratio'], 'selection_step': 'b', 'fits': 1, 'seconds': 399, 'versions': {'python': 'x'},
            'sha256': {name: hash_of(folder / name) for name in forecast_stage.FILES}}
    (folder / 'forecast_meta.json').write_text(json.dumps(meta), encoding='utf-8')
    (run / 'context.json').write_text(json.dumps({'target': 'duckdb', 'release_id': RID}), encoding='utf-8')
    registry.register({'release_id': RID, 'snapshot_id': source.name, 'run_id': 'goc', 'status': 'ready'})
    target = tmp_path / 'dot_snapshot'
    write_sales(target, '2012-07-04', '2023-12-31')
    directory = root / 'runs' / 'dot'
    directory.mkdir(parents=True)
    monkeypatch.setattr(snapshot, 'validate',
                        lambda path, **_: json.loads((Path(path) / 'manifest.json').read_text(encoding='utf-8')))
    context = {'run_id': 'dot', 'target': 'duckdb', 'snapshot_id': 'cccccccccccc', 'snapshot_path': target.as_posix(),
               'directory': directory.as_posix()}
    return SimpleNamespace(root=root, source=source, folder=folder, meta=meta, target=target, context=context,
                           run=run, registry=registry)


def test_copies_bytes_and_records_source(base):
    path, summary = du_bao_dot.dung_lai(base.context, base.root, RID)
    out = Path(path)
    for name in forecast_stage.FILES:
        assert (out / name).read_bytes() == (base.folder / name).read_bytes()
    meta = json.loads((out / 'forecast_meta.json').read_text(encoding='utf-8'))
    assert meta['snapshot_id'] == 'cccccccccccc' and meta['run_id'] == 'dot'
    assert meta['model_version'] == forecast_stage.model_version()
    expected = {'release_id': RID, 'snapshot_id': 'bbbbbbbbbbbb', 'run_id': 'goc', 'trained_through': '2022-12-31'}
    assert meta['nguon_du_bao'] == expected and summary['nguon_du_bao'] == expected
    cli.check_forecast({**base.context, 'forecast_path': path})   # đi qua đúng cổng build


def test_rerun_keeps_files(base):
    path, _ = du_bao_dot.dung_lai(base.context, base.root, RID)
    meta_path = Path(path) / 'forecast_meta.json'
    before = meta_path.read_bytes()
    du_bao_dot.dung_lai(base.context, base.root, RID)
    assert meta_path.read_bytes() == before


def test_rerun_detects_damage(base):
    path, _ = du_bao_dot.dung_lai(base.context, base.root, RID)
    (Path(path) / 'forecast_explain.parquet').write_bytes(b'hong')
    with pytest.raises(ValueError, match='hỏng hoặc thiếu'):
        du_bao_dot.dung_lai(base.context, base.root, RID)


def test_no_partial_output_when_rejected(base):
    (base.folder / forecast_stage.FILES[1]).write_bytes(b'hong')
    with pytest.raises(ValueError):
        du_bao_dot.dung_lai(base.context, base.root, RID)
    assert not (Path(base.context['directory']) / 'forecast').exists()


def test_rejects_unknown_release(base):
    with pytest.raises(ValueError, match='không có trong registry'):
        du_bao_dot.dung_lai(base.context, base.root, 'f' * 24)


def test_rejects_not_ready(base):
    before = base.registry.read()
    payload = json.loads(json.dumps(before['payload']))
    payload['releases'][RID]['status'] = 'failed'
    base.registry.save(before, payload)
    with pytest.raises(ValueError, match='chưa sẵn sàng'):
        du_bao_dot.dung_lai(base.context, base.root, RID)


def test_rejects_cloud_source(base):
    (base.run / 'context.json').write_text(json.dumps({'target': 'databricks', 'release_id': RID}), encoding='utf-8')
    with pytest.raises(ValueError, match='bản DuckDB'):
        du_bao_dot.dung_lai(base.context, base.root, RID)


def test_rejects_source_with_batch(base):
    (base.source / 'manifest.json').write_text(json.dumps({'dot': [{'ma_dot': 'x'}]}), encoding='utf-8')
    with pytest.raises(ValueError, match='dự báo phải lấy từ bản gốc'):
        du_bao_dot.dung_lai(base.context, base.root, RID)


@pytest.mark.parametrize('name', forecast_stage.FILES)
def test_rejects_damaged_file(base, name):
    (base.folder / name).write_bytes(b'hong')
    with pytest.raises(ValueError, match='hỏng hoặc thiếu'):
        du_bao_dot.dung_lai(base.context, base.root, RID)


def test_rejects_missing_meta(base):
    (base.folder / 'forecast_meta.json').unlink()
    with pytest.raises(ValueError, match='chưa có kết quả dự báo'):
        du_bao_dot.dung_lai(base.context, base.root, RID)


def test_rejects_other_model_version(base):
    base.meta['model_version'] = 'khac'
    (base.folder / 'forecast_meta.json').write_text(json.dumps(base.meta), encoding='utf-8')
    with pytest.raises(ValueError, match='code dự báo khác'):
        du_bao_dot.dung_lai(base.context, base.root, RID)


def test_rejects_history_change(base):
    write_sales(base.target, '2012-07-04', '2023-12-31', offset=1.0)
    with pytest.raises(ValueError, match='khác bản nguồn ở kỳ gốc'):
        du_bao_dot.dung_lai(base.context, base.root, RID)


def test_rejects_extra_day_in_source(base):
    write_sales(base.source, '2012-07-04', '2023-01-01')
    with pytest.raises(ValueError, match='không kết thúc đúng ở trained_through'):
        du_bao_dot.dung_lai(base.context, base.root, RID)


def test_rejects_two_trained_through(base):
    rewrite_daily(base, """select cast(d as date) as forecast_date, cast(d as date) as trained_through
                           from generate_series(date '2023-01-01', date '2023-01-03', interval 1 day) t(d)""")
    with pytest.raises(ValueError, match='đúng một trained_through'):
        du_bao_dot.dung_lai(base.context, base.root, RID)


def test_rejects_gap_after_trained_through(base):
    duckdb.sql(f"""copy (select strftime(d, '%Y-%m-%d') as "Date", '100.0' as "Revenue", '80' as "COGS"
                   from generate_series(date '2012-07-04', date '2023-12-31', interval 1 day) t(d)
                   where d <> date '2023-01-01') to '{(base.target / 'sales.parquet').as_posix()}' (format parquet)""")
    with pytest.raises(ValueError, match='nối liền'):
        du_bao_dot.dung_lai(base.context, base.root, RID)


def test_rejects_no_forecast_left(base):
    rewrite_daily(base, f"""select cast(d as date) as forecast_date, date '{GOC}' as trained_through
                            from generate_series(date '2023-01-01', date '2023-12-31', interval 1 day) t(d)""")
    with pytest.raises(ValueError, match='Không còn ngày dự báo'):
        du_bao_dot.dung_lai(base.context, base.root, RID)


def test_rejects_cloud_run(base):
    with pytest.raises(ValueError, match='chỉ chạy local'):
        du_bao_dot.dung_lai({**base.context, 'target': 'databricks'}, base.root, RID)


# Cổng CLI, trên snapshot đợt thật của D2
@pytest.fixture
def cli_case(case, monkeypatch):  # noqa: F811
    monkeypatch.setattr(snapshot, 'SOURCES', case.spec)
    case.root = case.landing.parent / 'pipeline'
    case.prepare = lambda run='batch', **kw: cli.execute('prepare', run_id=run, root=case.root, data=case.data, **kw)
    return case


def test_forecast_requires_source(cli_case):
    ctx = cli_case.prepare(dots=[cli_case.batch])
    with pytest.raises(ValueError, match='cần --du-bao-tu'):
        cli.execute('forecast', run_id=ctx['run_id'], root=cli_case.root)


def test_forecast_reaches_reuse_with_source(cli_case):
    # Đợt mẫu 2 ngày: tới được du_bao_dot và bị chặn vì chưa đủ năm, không train
    ctx = cli_case.prepare(dots=[cli_case.batch])
    with pytest.raises(ValueError, match='chưa đủ năm'):
        cli.execute('forecast', run_id=ctx['run_id'], root=cli_case.root, du_bao_tu=RID)


def test_source_rejected_without_batch(cli_case, monkeypatch):
    monkeypatch.setattr(cli, 'forecast_stage', lambda c: pytest.fail('Không được train'))
    ctx = cli_case.prepare()
    with pytest.raises(ValueError, match='chỉ dùng cho snapshot có đợt'):
        cli.execute('forecast', run_id=ctx['run_id'], root=cli_case.root, du_bao_tu=RID)


def test_plain_snapshot_still_trains(cli_case, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, 'forecast_stage', lambda c: calls.append(c['run_id']) or ('x', {'seconds': 0}))
    ctx = cli_case.prepare()
    assert cli.execute('forecast', run_id=ctx['run_id'], root=cli_case.root)['stage'] == 'forecasted'
    assert calls == [ctx['run_id']]


def test_batch_variables(tmp_path):
    write_sales(tmp_path / 'snap', '2012-07-04', '2023-12-31')
    (tmp_path / 'fc').mkdir()
    (tmp_path / 'fc' / 'forecast_meta.json').write_text(
        json.dumps({'nguon_du_bao': {'trained_through': '2022-12-31'}}), encoding='utf-8')
    manifest = {'dot': [{'files': [{'nguon': 'orders', 'nhom': 'loi_kem_cot_them', 'so_dong': 5},
                                   {'nguon': 'orders', 'nhom': 'khop_loi', 'so_dong': 2},
                                   {'nguon': 'products', 'nhom': 'master_khong_doi', 'so_dong': 9},
                                   {'nguon': 'x', 'nhom': 'chi_de_xuat', 'so_dong': 9}]}]}
    got = du_bao_dot.bien_dbt({'forecast_path': (tmp_path / 'fc').as_posix(),
                               'snapshot_path': (tmp_path / 'snap').as_posix()}, manifest)
    assert got == {'co_dot': True, 'analysis_end_year': 2023, 'last_actual_date': '2023-12-31',
                   'forecast_trained_through': '2022-12-31', 'dot_so_dong': {'orders': 7}}


def test_vars_unchanged_without_batch(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(cli.subprocess, 'run',
                        lambda cmd, **kw: seen.append(json.loads(cmd[cmd.index('--vars') + 1])) or SimpleNamespace(returncode=0))
    monkeypatch.setattr(cli, 'verify_artifacts', lambda *a: None)
    context = dict(release_id='x', snapshot_id='s', code_version='c', snapshot_path='p',
                   directory=str(tmp_path), duckdb_path='d')
    cli.dbt_build(context, 'duckdb')
    assert seen[0] == {'release_id': 'x', 'snapshot_id': 's', 'code_version': 'c', 'snapshot_path': 'p'}
    cli.dbt_build({**context, 'bien_dot': {'co_dot': True, 'analysis_end_year': 2023}}, 'duckdb')
    assert seen[1]['co_dot'] is True and seen[1]['analysis_end_year'] == 2023


@pytest.mark.parametrize('day,message', [('2023-06-30', 'chưa đủ năm'), ('2024-12-31', 'vượt lịch')])
def test_period_guard(tmp_path, day, message):
    write_sales(tmp_path, '2023-01-01', day)
    with pytest.raises(ValueError, match=message):
        du_bao_dot.ky_cua_ban(tmp_path)


def test_period_from_data(tmp_path):
    write_sales(tmp_path, '2023-01-01', '2023-12-31')
    assert du_bao_dot.ky_cua_ban(tmp_path) == {'analysis_end_year': 2023, 'last_actual_date': '2023-12-31'}


def test_flag_only_with_forecast(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'argv', ['cli', 'build', '--run-id', 'x', '--root', str(tmp_path), '--du-bao-tu', RID])
    with pytest.raises(SystemExit):
        cli.main()


@pytest.mark.parametrize('stage', ['build', 'validate', 'publish', 'run'])
def test_execute_rejects_flag_for_other_stage(tmp_path, stage):
    with pytest.raises(ValueError, match='chỉ dùng với stage forecast'):
        cli._execute(stage, run_id='x', root=tmp_path / 'p', du_bao_tu=RID)


def test_publish_still_blocked(cli_case):
    ctx = cli_case.prepare(dots=[cli_case.batch])
    with pytest.raises(ValueError, match='--xac-nhan-tong-hop'):
        cli.execute('publish', run_id=ctx['run_id'], root=cli_case.root)


def rollback(root, release, monkeypatch):
    monkeypatch.setattr(cli, 'checked', lambda record: record)
    monkeypatch.setattr(cli, 'verify_consumers', lambda *a: None)
    monkeypatch.setattr(sys, 'argv', ['cli', 'rollback', '--run-id', 'lui', '--root', str(root), '--release-id', release])
    cli.main()


def test_rollback_blocked_for_batch(cli_case, monkeypatch):
    ctx = cli_case.prepare(dots=[cli_case.batch])
    registry = Registry(cli_case.root)
    registry.register({'release_id': RID, 'snapshot_id': ctx['snapshot_id'], 'run_id': ctx['run_id'], 'status': 'ready'})
    before = registry.read()['payload']['active']
    with pytest.raises(ValueError, match='Bản có đợt'):
        rollback(cli_case.root, RID, monkeypatch)
    assert registry.read()['payload']['active'] == before
    assert not (cli_case.root / 'rollbacks').exists()


def test_rollback_allowed_without_batch(cli_case, monkeypatch):
    ctx = cli_case.prepare()
    registry = Registry(cli_case.root)
    registry.register({'release_id': RID, 'snapshot_id': ctx['snapshot_id'], 'run_id': ctx['run_id'], 'status': 'ready'})
    rollback(cli_case.root, RID, monkeypatch)
    assert registry.read()['payload']['active'] == RID


# Lỗi tồn từ D2: chạy lại prepare cùng run_id trên snapshot có đợt
def test_retry_by_snapshot_id_returns_same(cli_case):
    first = cli_case.prepare(dots=[cli_case.batch])
    again = cli_case.prepare('by-id', snapshot_id=first['snapshot_id'])
    assert cli_case.prepare('by-id', snapshot_id=first['snapshot_id']) == again


def test_retry_rejects_other_snapshot(cli_case):
    first = cli_case.prepare(dots=[cli_case.batch])
    other = cli_case.prepare('other', dots=[cli_case.batch, second_batch(cli_case)])
    assert first['snapshot_id'] != other['snapshot_id']
    with pytest.raises(ValueError, match='run_id đã dùng cho snapshot khác'):
        cli_case.prepare('batch', snapshot_id=other['snapshot_id'])


def test_retry_with_batches_still_compares(cli_case):
    cli_case.prepare(dots=[cli_case.batch])
    with pytest.raises(ValueError, match='danh sách --dot khác'):
        cli_case.prepare()


def test_plain_run_rejects_new_batches(cli_case):
    cli_case.prepare()
    with pytest.raises(ValueError, match='danh sách --dot khác'):
        cli_case.prepare(dots=[cli_case.batch])


def test_d3_leaves_protected_code():
    goc = subprocess.run(['git', 'cat-file', '-e', '49d3454^{commit}'], cwd=ROOT, capture_output=True)
    if goc.returncode:
        pytest.skip('Không còn commit gốc 49d3454 trong lịch sử')
    changed = subprocess.run(['git', 'diff', '--name-only', '49d3454', '--', 'scripts/forecast', 'scripts/ingest/source_contract.py',
                              'scripts/ingest/dot.py', 'scripts/ingest/extensions', 'retail_dbt/seeds'],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert changed == ''
