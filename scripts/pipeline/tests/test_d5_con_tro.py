"""D5a: con trỏ và lệnh dùng dữ liệu giả, không chạy pipeline/cloud."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'apps/retail_app'))
from scripts.pipeline import cli
from scripts.pipeline.state import Registry, atomic_json

A, B, C = (x * 24 for x in 'abc')


def record(rid, synthetic=False):
    row = dict(release_id=rid, status='ready', snapshot_id='d' * 12, code_version='code',
               run_id='batch', schema=f'r_{rid}_reporting', duckdb_path='/unused')
    if synthetic:
        row['co_du_lieu_tong_hop'] = True
    return row


@pytest.fixture
def registry(tmp_path):
    reg = Registry(tmp_path)
    reg.initialize()
    for rid, synthetic in [(A, False), (B, True), (C, False)]:
        reg.register(record(rid, synthetic))
    reg.publish(A, None)
    return reg


def test_t1_lifecycle_and_active_rollback(registry):
    active = registry.read()['payload']['active_since']
    registry.publish_dashboard(B, None)
    assert registry.read()['payload']['active_since'] == active
    registry.publish(C, A)
    registry.publish(A, C)
    assert registry.read()['payload']['dashboard'] == B
    assert registry.clear_dashboard(B)
    state = registry.read()['payload']
    assert 'dashboard' not in state and 'dashboard_since' not in state
    raw = registry.path.read_bytes()
    assert not registry.clear_dashboard(None)
    assert registry.path.read_bytes() == raw


@pytest.mark.parametrize('damage', ['plain', 'not_ready', 'expected', 'active'])
def test_t1_rejected_no_write(registry, damage):
    if damage == 'not_ready':
        before = registry.read()
        before['payload']['releases'][B]['status'] = 'draft'
        registry.save(before, before['payload'])
    raw = registry.path.read_bytes()
    with pytest.raises((RuntimeError, ValueError)):
        if damage == 'active':
            registry.publish(B, A)
        else:
            registry.publish_dashboard(A if damage == 'plain' else B, C if damage == 'expected' else None)
    assert registry.path.read_bytes() == raw


def test_t1_sql_compare_and_swap(registry):
    data = registry.read()
    statements = []
    def sql(query, params=None):
        statements.append((query, params))
        if query.startswith('select'):
            return [], [(data['version'], json.dumps(data['payload']))]
        assert "where name = 'main' and version = ?" in query
        assert params[2] == data['version']
        data.update(version=params[0], payload=json.loads(params[1]))
    reg = Registry(registry.path.parent, sql)
    reg.publish_dashboard(B, None)
    assert data['payload']['dashboard'] == B and data['payload']['active'] == A
    reg.clear_dashboard(B)
    assert 'dashboard' not in data['payload']
    assert len([s for s, _ in statements if s.startswith('update')]) == 2
    # Writer khác thắng CAS: không có ACK hợp lệ.
    reg.sql = lambda query, params=None: ([], [('other', json.dumps(data['payload']))])
    with pytest.raises(RuntimeError):
        reg.publish_dashboard(B, None)


def invoke(monkeypatch, *args):
    monkeypatch.setattr(sys, 'argv', ['cli', *map(str, args)])
    return cli.main()


@pytest.mark.parametrize('batch', [False, True])
def test_t2_run_arguments_and_stop(monkeypatch, batch):
    calls = []
    def execute(stage, **kwargs):
        calls.append((stage, kwargs))
        return dict(run_id='run', release_id=B, snapshot_id='s', stage=stage, **({'dot': [{}]} if batch else {}))
    monkeypatch.setattr(cli, 'execute', execute)
    args = ['run', '--run-id', 'run', '--extension', 'orders_enriched', '--force']
    invoke(monkeypatch, *args, *(['--dot', 'demo', '--du-bao-tu', A] if batch else []))
    assert [s for s, _ in calls] == list(cli.STAGES[:4] if batch else cli.STAGES)
    for stage, kw in calls:
        assert kw == dict(run_id='run', target='duckdb', root='warehouse/pipeline', data='data',
                         snapshot_id=None, force=True, extensions=['orders_enriched'], extension_directory=None,
                         dots=['demo'] if batch and stage == 'prepare' else [],
                         du_bao_tu=A if batch and stage == 'forecast' else None)


def test_t2_missing_source_before_prepare(monkeypatch):
    monkeypatch.setattr(cli, 'execute', lambda *a, **kw: pytest.fail('Không được prepare'))
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, 'run', '--run-id', 'r', '--dot', 'demo')
    assert error.value.code == 2


@pytest.fixture
def context(registry, monkeypatch):
    root = registry.path.parent
    ctx = {**record(B, True), 'target': 'duckdb', 'stage': 'validated', 'expected_active': A,
           'dot': [{'ma_dot': 'demo'}], 'snapshot_path': str(root / 'snapshots' / ('d' * 12))}
    path = root / 'runs/batch/context.json'
    atomic_json(path, ctx)
    atomic_json(Path(ctx['snapshot_path']) / 'manifest.json', {'dot': ctx['dot']})
    monkeypatch.setattr(cli, 'code_version', lambda: 'code')
    monkeypatch.setattr(cli.snapshot, 'validate', lambda *a, **kw: {'dot': ctx.get('dot', [])})
    monkeypatch.setattr(cli, 'verify_consumers', lambda *a: None)
    monkeypatch.setattr(cli, 'validate_data', lambda *a: {'ok': True})
    return root, ctx, path


def test_t3_publish_confirmation_and_history(registry, context):
    root, ctx, path = context
    raw = registry.path.read_bytes()
    with pytest.raises(ValueError, match='--xac-nhan-tong-hop'):
        cli.execute('publish', root=root, run_id='batch')
    assert registry.path.read_bytes() == raw
    before = registry.read()['payload']
    result = cli.execute('publish', root=root, run_id='batch', confirm_synthetic=True)
    after = registry.read()['payload']
    assert result['stage'] == 'published_dashboard'
    assert after['dashboard'] == B
    assert after['active'] == before['active'] == A and after['active_since'] == before['active_since']
    assert cli.read_history(root)[0]['stage'] == 'publish_dashboard'
    # Retry cũng phải xác nhận; bản đã công bố không được lách qua nhánh trả sớm.
    with pytest.raises(ValueError, match='--xac-nhan-tong-hop'):
        cli.execute('publish', root=root, run_id='batch')
    registry.clear_dashboard(B)
    cli.execute('publish', root=root, run_id='batch', confirm_synthetic=True)
    assert registry.read()['payload']['dashboard'] == B


@pytest.mark.parametrize('damage', ['plain', 'cloud'])
def test_t3_wrong_flag_or_cloud(registry, context, damage):
    root, ctx, path = context
    if damage == 'plain':
        ctx.pop('dot')
    else:
        ctx['target'] = 'databricks'
    atomic_json(path, ctx)
    raw = registry.path.read_bytes()
    with pytest.raises(ValueError):
        cli.execute('publish', root=root, run_id='batch', target=ctx['target'], confirm_synthetic=True)
    assert registry.path.read_bytes() == raw


def test_t4_clear_cli_and_rollback_block(registry, context, monkeypatch):
    root, ctx, path = context
    registry.publish_dashboard(B, None)
    invoke(monkeypatch, 'tra-dashboard', '--run-id', 'clear', '--root', root, '--release-id', 'ignored')
    raw = registry.path.read_bytes()
    invoke(monkeypatch, 'tra-dashboard', '--run-id', 'clear2', '--root', root)
    assert registry.path.read_bytes() == raw
    assert [r['result'] for r in cli.read_history(root)][:2] == ['bo_qua', 'dat']
    with pytest.raises(ValueError, match='Bản có đợt'):
        invoke(monkeypatch, 'rollback', '--run-id', 'bad', '--root', root, '--release-id', B)
    assert registry.path.read_bytes() == raw
    assert not (root / 'rollbacks').exists()


@pytest.mark.parametrize('batch', [False, True])
def test_t5_registry_flag(context, registry, batch):
    root, ctx, path = context
    before = registry.read()
    before['payload']['releases'].pop(B)
    registry.save(before, before['payload'])
    ctx['stage'] = 'built'
    if not batch:
        ctx.pop('dot')
    atomic_json(path, ctx)
    cli.execute('validate', root=root, run_id='batch')
    row = registry.read()['payload']['releases'][B]
    if batch:
        assert row['co_du_lieu_tong_hop'] is True
    else:
        assert 'co_du_lieu_tong_hop' not in row
        assert set(row) == {'release_id', 'snapshot_id', 'code_version', 'run_id', 'schema', 'duckdb_path', 'artifact_path', 'status'}


def load_dag(monkeypatch, name):
    tasks, config = [], {}
    class DAG:
        def __init__(self, **kw):
            config.update(kw)
        def __enter__(self): return self
        def __exit__(self, *a): return False
    class Param:
        def __init__(self, default=None, **schema):
            self.default, self.schema = default, schema
    class Task:
        def override(self, **kw): return self
        def __call__(self, name, *a):
            tasks.append(name)
            return self
        def __rshift__(self, other): return other
    sdk = ModuleType('airflow.sdk')
    sdk.DAG, sdk.Param, sdk.task, sdk.get_current_context = DAG, Param, lambda fn: Task(), lambda: {}
    exc, pendulum = ModuleType('airflow.exceptions'), ModuleType('pendulum')
    exc.AirflowFailException, pendulum.datetime = RuntimeError, lambda *a, **kw: None
    for key, module in {'airflow': ModuleType('airflow'), 'airflow.sdk': sdk, 'airflow.exceptions': exc, 'pendulum': pendulum}.items():
        monkeypatch.setitem(sys.modules, key, module)
    spec = importlib.util.spec_from_file_location('dag_test', ROOT / 'deploy/airflow/dags' / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, tasks, config


def test_t10_dag_only_four_stages(monkeypatch):
    monkeypatch.setenv('RETAIL_PIPELINE_DEFAULT_TARGET', 'databricks')
    module, tasks, config = load_dag(monkeypatch, 'retail_dot_pipeline.py')
    assert tasks == ['prepare', 'forecast', 'build', 'validate']
    assert config['schedule'] is None and config['is_paused_upon_creation'] and config['max_active_runs'] == 1
    ctx = {'run_id': 'abc', 'params': {'dot': 'demo', 'du_bao_tu': A, 'force': True,
                                     'target': 'databricks', 'extensions': ['shipments_realistic', 'orders_enriched']}}
    for stage in tasks:
        expected = ['/opt/pipeline/bin/python', '-m', 'scripts.pipeline.cli', stage,
                    '--run-id', 'ba7816bf8f01cfea414140de', '--target', 'duckdb', '--root', 'warehouse/pipeline/docker', '--force']
        if stage == 'prepare':
            expected += ['--dot', '/opt/retail/data_demo/demo', '--extension', 'orders_enriched', '--extension', 'shipments_realistic']
        if stage == 'forecast': expected += ['--du-bao-tu', A]
        assert module.command(stage, ctx) == expected
    for bad in ('..', '../demo', 'a/b', 'a\\b', 'a..b'):
        assert re.fullmatch(config['params']['dot'].schema['pattern'], bad) is None
        ctx['params']['dot'] = bad
        with pytest.raises(ValueError): module.command('prepare', ctx)


@pytest.mark.parametrize('force', [False, True])
@pytest.mark.parametrize('snapshot', [None, 'd' * 12])
@pytest.mark.parametrize('extensions', [[], ['orders_enriched'], ['shipments_realistic', 'orders_enriched']])
def test_t11_old_dag_commands_unchanged(monkeypatch, force, snapshot, extensions):
    module, tasks, config = load_dag(monkeypatch, 'retail_batch_pipeline.py')
    path = 'deploy/airflow/dags/retail_batch_pipeline.py'
    old = subprocess.run(['git', 'show', '20bce05:' + path], cwd=ROOT, capture_output=True, check=True).stdout
    assert (ROOT / path).read_bytes().replace(b'\r\n', b'\n') == old.replace(b'\r\n', b'\n')
    for stage in tasks:
        args = module.command(stage, {'run_id': 'abc', 'params': dict(target='databricks', force=force, snapshot_id=snapshot, extensions=extensions)})
        expected = ['/opt/pipeline/bin/python', '-m', 'scripts.pipeline.cli', stage, '--run-id', 'ba7816bf8f01cfea414140de',
                    '--target', 'databricks', '--root', 'warehouse/pipeline/docker']
        if snapshot: expected += ['--snapshot-id', snapshot]
        if force: expected += ['--force']
        if stage == 'prepare':
            for name in sorted(set(extensions)): expected += ['--extension', name]
        assert args == expected


@pytest.mark.parametrize('synthetic', [False, True])
def test_t3_cli_exit_two_without_registry_change(registry, context, synthetic):
    root, ctx, path = context
    if not synthetic:
        ctx.pop('dot')
        atomic_json(path, ctx)
    raw = registry.path.read_bytes()
    command = [sys.executable, '-B', '-m', 'scripts.pipeline.cli', 'publish', '--run-id', 'batch', '--root', str(root)]
    if not synthetic:
        command.append('--xac-nhan-tong-hop')
    result = subprocess.run(command, cwd=ROOT, capture_output=True, encoding='utf-8')
    assert result.returncode == 2
    assert ('--xac-nhan-tong-hop' if synthetic else 'Cờ chỉ dùng') in result.stderr
    assert registry.path.read_bytes() == raw


@pytest.fixture
def dashboard_artifact(registry, monkeypatch):
    import duckdb
    path = registry.path.parent / 'releases' / 'demo.duckdb'
    path.parent.mkdir()
    schema = f'r_{B}_reporting'
    app, ai = cli.consumers()
    with duckdb.connect(str(path)) as con:
        con.execute(f'create schema {schema}')
        for relation in sorted(set(app + ai)):
            con.execute(f'create table {schema}.{relation.split(".")[1]} as select 1 as sample')
    state = registry.read()
    state['payload']['releases'][B].update(artifact_path='releases/demo.duckdb',
        duckdb_path='/opt/retail/warehouse/demo.duckdb', code_version='image-cu')
    registry.save(state, state['payload'])
    # Cấm cả các đường đọc cũ; phép thử kho bên dưới vẫn dùng DuckDB thật trong tmp_path.
    def forbidden(*args, **kwargs):
        pytest.fail('dat-dashboard không được đọc context, snapshot, code_version hoặc cloud')
    monkeypatch.setattr(cli, '_read_json', forbidden)
    monkeypatch.setattr(cli, 'code_version', forbidden)
    monkeypatch.setattr(cli.snapshot, 'validate', forbidden)
    monkeypatch.setattr(cli, 'Databricks', forbidden)
    return path


@pytest.mark.parametrize('has_context', [False, True])
def test_t13_registry_only_publish(registry, dashboard_artifact, monkeypatch, has_context):
    root = registry.path.parent
    if has_context:
        atomic_json(root / 'runs' / 'ui-test' / 'context.json', {
            'snapshot_path': '/opt/retail/warehouse/snapshots/old',
            'duckdb_path': '/opt/retail/warehouse/old.duckdb', 'code_version': 'image-cu'})
    before = registry.read()['payload']
    args = ('dat-dashboard', '--run-id', 'ui-test', '--root', root,
            '--release-id', B, '--xac-nhan-tong-hop')
    invoke(monkeypatch, *args)
    after = registry.read()['payload']
    assert after['dashboard'] == B and after['dashboard_since']['release_id'] == B
    assert {k: v for k, v in after.items() if k not in ('dashboard', 'dashboard_since')} == before
    history = cli.read_history(root)
    assert len(history) == 1 and history[0]['stage'] == 'publish_dashboard'
    assert history[0]['release_id'] == B and history[0]['result'] == 'dat'
    raw = registry.path.read_bytes()
    invoke(monkeypatch, *args)
    assert registry.path.read_bytes() == raw
    assert [r['result'] for r in cli.read_history(root)] == ['bo_qua', 'dat']


@pytest.mark.parametrize('damage', ['flag', 'cloud', 'id', 'absent', 'plain', 'not_ready', 'missing_file', 'missing_table'])
def test_t13_rejected_preserves_registry(registry, dashboard_artifact, monkeypatch, damage):
    import duckdb
    root = registry.path.parent
    rid = B
    if damage == 'id': rid = '../bad'
    if damage == 'absent': rid = 'f' * 24
    if damage == 'plain': rid = A
    if damage == 'not_ready':
        state = registry.read()
        state['payload']['releases'][B]['status'] = 'draft'
        registry.save(state, state['payload'])
    if damage == 'missing_file': dashboard_artifact.unlink()
    if damage == 'missing_table':
        required = sorted(set(sum(cli.consumers(), [])) - cli.optional_relations())[0]
        with duckdb.connect(str(dashboard_artifact)) as con:
            con.execute(f'drop table r_{B}_reporting.{required.split(".")[1]}')
    raw = registry.path.read_bytes()
    args = ['dat-dashboard', '--run-id', 'ui-test', '--root', root, '--release-id', rid,
            '--target', 'databricks' if damage == 'cloud' else 'duckdb']
    if damage != 'flag': args.append('--xac-nhan-tong-hop')
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, *args)
    assert error.value.code == 2
    assert registry.path.read_bytes() == raw
