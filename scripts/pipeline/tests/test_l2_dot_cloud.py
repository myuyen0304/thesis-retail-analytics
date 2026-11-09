"""L2: CLI Databricks và quyền reader với cloud giả, không mở workspace."""
import json
import os
import subprocess
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from scripts.pipeline import cli, du_bao_dot
from scripts.pipeline.state import Registry, atomic_json

RID = 'a' * 24
ROOT = Path(__file__).resolve().parents[3]


class FakeCloud:
    def __init__(self):
        self.queries = []
        self.closed = False
        self.catalog = 'retail_lab'
        self.auth = SimpleNamespace(host='https://fake.invalid')

    def query(self, sql, params=()):
        self.queries.append(sql)
        if sql.startswith('select version, payload'):
            return [], [('v', json.dumps({'active': 'b' * 24, 'dashboard': None,
                'releases': {RID: {'release_id': RID, 'status': 'ready', 'co_du_lieu_tong_hop': True}}}))]
        return [], []

    def close(self):
        self.closed = True


@pytest.mark.parametrize('raises', [False, True])
def test_dat_dashboard_uses_cloud_registry_and_closes(tmp_path, monkeypatch, raises):
    cloud = FakeCloud()
    called = []
    monkeypatch.setattr(cli, 'Databricks', lambda: cloud)
    monkeypatch.setattr(cli, 'record_history', lambda *a: None)
    def verify(record, registry, target):
        called.append((record, registry, target))
        if raises:
            raise ValueError('unreadable')
    monkeypatch.setattr(cli, 'verify_consumers', verify)
    monkeypatch.setattr(Registry, 'publish_dashboard', lambda self, *a: called.append(('publish', self.sql)))
    monkeypatch.setattr(sys, 'argv', ['cli', 'dat-dashboard', '--run-id', 'test', '--target', 'databricks',
                                    '--root', str(tmp_path), '--release-id', RID, '--xac-nhan-tong-hop'])
    if raises:
        with pytest.raises(SystemExit) as error:
            cli.main()
        assert error.value.code == 2
    else:
        cli.main()
        assert any(x[0] == 'publish' for x in called)
    assert cloud.closed and cloud.queries and called[0][2] is cloud


def test_forecast_passes_sql_registry_only_for_cloud(tmp_path, monkeypatch):
    root = tmp_path / 'root'
    run = root / 'runs' / 'dot_1'
    run.mkdir(parents=True)
    atomic_json(run / 'context.json', {'run_id': 'dot_1', 'target': 'databricks',
        'stage': 'prepared', 'code_version': 'same', 'snapshot_path': 'unused',
        'directory': str(run), 'release_id': RID})
    monkeypatch.setattr(cli, 'code_version', lambda: 'same')
    monkeypatch.setattr(cli.snapshot, 'validate', lambda *a, **kw: {'dot': [{'ma_dot': 'x'}]})
    cloud = FakeCloud()
    monkeypatch.setattr(cli, 'Databricks', lambda: cloud)
    from scripts.pipeline import du_bao_dot
    captured = []
    monkeypatch.setattr(du_bao_dot, 'dung_lai', lambda context, root, rid, *, registry:
                        captured.append((rid, registry.sql)) or ('forecast', {}))
    result = cli._execute('forecast', run_id='dot_1', target='databricks', root=root, du_bao_tu=RID)
    assert result['stage'] == 'forecasted' and captured == [(RID, cloud.query)] and cloud.closed


def test_forecast_without_batch_does_not_open_cloud(tmp_path, monkeypatch):
    root = tmp_path / 'root'
    run = root / 'runs' / 'regular'
    run.mkdir(parents=True)
    atomic_json(run / 'context.json', {'run_id': 'regular', 'target': 'databricks',
        'stage': 'prepared', 'code_version': 'same', 'snapshot_path': 'unused',
        'directory': str(run), 'release_id': RID})
    monkeypatch.setattr(cli, 'code_version', lambda: 'same')
    monkeypatch.setattr(cli.snapshot, 'validate', lambda *a, **kw: {'sources': {}})
    monkeypatch.setattr(cli, 'Databricks', lambda: pytest.fail('Forecast không đợt không mở cloud'))
    monkeypatch.setattr(cli, 'forecast_stage', lambda context: ('forecast', {}))
    result = cli._execute('forecast', run_id='regular', target='databricks', root=root)
    assert result['stage'] == 'forecasted'
    assert result['forecast_path'] == 'forecast'


def test_failure_json_keeps_only_d2_code(tmp_path, monkeypatch):
    root = tmp_path / 'root'
    run = root / 'runs' / 'dot_1'
    run.mkdir(parents=True)
    atomic_json(run / 'context.json', {'run_id': 'dot_1', 'target': 'duckdb',
        'stage': 'prepared', 'code_version': 'same', 'snapshot_path': 'unused', 'directory': str(run)})
    monkeypatch.setattr(cli, 'code_version', lambda: 'same')
    monkeypatch.setattr(cli.snapshot, 'validate', lambda *a, **kw: {'dot': [{'ma_dot': 'x'}]})
    monkeypatch.setattr(du_bao_dot, 'dung_lai', lambda *a, **kw:
                        (_ for _ in ()).throw(ValueError('D2-1: secret-probe')))
    with pytest.raises(ValueError):
        cli._execute('forecast', run_id='dot_1', root=root, du_bao_tu=RID)
    failure = json.loads((run / 'failure.json').read_text(encoding='utf-8'))
    assert failure['ma_loi'] == 'D2-1' and 'secret-probe' not in json.dumps(failure)


def test_mismatched_source_target_rejected(tmp_path, monkeypatch):
    registry = Registry(tmp_path)
    registry.initialize()
    registry.register({'release_id': RID, 'status': 'ready', 'run_id': 'source'})
    run = tmp_path / 'runs' / 'source'
    run.mkdir(parents=True)
    atomic_json(run / 'context.json', {'target': 'duckdb', 'release_id': RID})
    with pytest.raises(ValueError, match='cùng target'):
        du_bao_dot._kiem_nguon(tmp_path, RID, 'databricks', registry)


def test_lock_contention_exits_75(tmp_path):
    code = ("import runpy,sys; from scripts.pipeline import state; "
            "state.writer_lock=lambda root: (_ for _ in ()).throw(BlockingIOError('secret-probe')); "
            "sys.argv=['cli','dat-dashboard','--run-id','x','--release-id','" + RID + "',"
            "'--xac-nhan-tong-hop']; "
            "runpy.run_module('scripts.pipeline.cli',run_name='__main__')")
    result = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-c', code],
                            cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 75
    assert result.stderr.strip() == 'writer.lock đang bận'
    assert 'secret-probe' not in result.stderr


@pytest.mark.parametrize('synthetic,readers', [(True, ['APP']), (False, ['APP', 'AI'])])
def test_reader_grants_exclude_ai_for_synthetic(monkeypatch, synthetic, readers):
    from databricks import sql
    from databricks.sdk import core
    from dwh import guarded
    app_id, ai_id = 'a' * 36, 'b' * 36
    monkeypatch.setattr(cli, 'consumers', lambda: (['reporting.app'], ['reporting.ai']))
    monkeypatch.setattr(cli, 'present', lambda logical, schema, exists: logical)
    monkeypatch.setattr(cli, 'allowed_versions', lambda state, full: set())
    monkeypatch.setattr(guarded, '_check_dbx_identity', lambda *args: None)
    monkeypatch.setattr(core, 'Config', lambda **kwargs: SimpleNamespace(authenticate=lambda: {}))
    for key, value in {'RETAIL_APP_DBX_CLIENT_ID': app_id, 'RETAIL_APP_DBX_CLIENT_SECRET': 'app-secret',
                       'RETAIL_AI_DBX_CLIENT_ID': ai_id, 'RETAIL_AI_DBX_CLIENT_SECRET': 'ai-secret',
                       'RETAIL_PIPELINE_CLIENT_ID': 'writer-id', 'DATABRICKS_WAREHOUSE_ID': 'warehouse'}.items():
        monkeypatch.setenv(key, value)
    connections = []

    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, sql): pass
        def fetchall(self): return []

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def cursor(self): return Cursor()

    def connect(**kwargs):
        connections.append(kwargs)
        return Connection()

    monkeypatch.setattr(sql, 'connect', connect)
    cloud = FakeCloud()
    cloud.query = lambda statement, params=(): cloud.queries.append(statement) or (
        ([], [(1,)]) if 'information_schema.tables' in statement else ([], []))
    registry = SimpleNamespace(read=lambda: {'payload': {'active': RID, 'releases': {RID: {}}}})
    cli.verify_consumers({'schema': 'r_' + RID + '_reporting',
                          'co_du_lieu_tong_hop': synthetic}, registry, cloud)
    grants = [q for q in cloud.queries if q.startswith('grant')]
    assert any('`' + app_id + '`' in q for q in grants)
    if synthetic:
        assert not any('`' + ai_id + '`' in q for q in grants)
    else:
        assert any('`' + ai_id + '`' in q for q in grants)
    assert len(connections) == len(readers)


def test_guard_requires_only_active_when_dashboard_has_synthetic(monkeypatch):
    from dwh import guarded, releases
    active = 'a' * 24
    dashboard = 'b' * 24
    state = {'active': active, 'dashboard': dashboard, 'releases': {
        rid: {'release_id': rid, 'status': 'ready', 'schema': f'r_{rid}_reporting'}
        for rid in (active, dashboard)}}
    monkeypatch.setenv('RETAIL_RELEASE_MODE', 'versioned')
    monkeypatch.setattr(guarded, '_read_registry', lambda cur: state)
    with releases.active_scope():
        allowed, required = guarded._release_scope(object(), frozenset({'reporting.rpt_sales'}), 'retail_lab')
    assert f'r_{active}_reporting.rpt_sales' in required
    assert f'r_{dashboard}_reporting.rpt_sales' not in required
    assert f'r_{dashboard}_reporting.rpt_sales' in allowed
    assert releases.CONTROL_RELATION in required


def test_prepare_dot_uses_sql_registry_on_databricks(tmp_path, monkeypatch):
    cloud = FakeCloud()
    monkeypatch.setattr(cli, 'Databricks', lambda: cloud)
    seen = []
    class RegistrySpy:
        def __init__(self, root, sql=None):
            seen.append(('registry_sql', sql))
        def initialize(self):
            seen.append(('initialize',))
        def read(self):
            return {'payload': {'active': None, 'releases': {}}}
    monkeypatch.setattr(cli, 'Registry', RegistrySpy)
    monkeypatch.setattr(cli, 'code_version', lambda: 'same')
    monkeypatch.setattr(cli.snapshot, 'prepare', lambda data, landing, **options:
                        seen.append(('prepare', options)) or tmp_path / 'snapshot')
    monkeypatch.setattr(cli.snapshot, 'validate', lambda *args, **kwargs:
                        {'snapshot_id': 'b' * 12, 'sources': {}, 'dot': [{'ma_dot': 'x'}],
                         'co_du_lieu_tong_hop': True})
    monkeypatch.setattr(cli.contract, 'check', lambda *args: {})
    result = cli._execute('prepare', run_id='dot_cloud', target='databricks', root=tmp_path / 'root',
                          dots=['/opt/retail/data_demo/batch'])
    assert result['stage'] == 'prepared' and result['co_du_lieu_tong_hop'] is True
    assert seen[0] == ('registry_sql', cloud.query)
    assert ('prepare', {'extensions': (), 'dots': ['/opt/retail/data_demo/batch']}) in seen
    assert cloud.closed
