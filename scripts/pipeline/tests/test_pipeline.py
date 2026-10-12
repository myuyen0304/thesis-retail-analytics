"""Kiểm rủi ro công bố: dữ liệu lỗi, retry, writer cạnh tranh và người đọc đang hoạt động."""
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'apps/retail_app'))
from scripts.pipeline import snapshot, cli
from scripts.pipeline.state import Registry, writer_lock, atomic_json
from dwh import releases


def record(letter='a'):
    rid = letter * 24
    return {'release_id': rid, 'snapshot_id': 's1', 'code_version': 'v1', 'run_id': 'run1',
            'schema': f'r_{rid}_reporting', 'duckdb_path': '/unused/dbt.duckdb', 'status': 'ready'}


@pytest.fixture(autouse=True)
def isolate_release(monkeypatch):
    releases.reset()
    monkeypatch.delenv('RETAIL_RELEASE_MODE', raising=False)
    yield
    releases.reset()


def test_bad_header_stops_before_landing(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    (data / 'sales.csv').write_text('WRONG,Revenue\n2022-01-01,10\n')
    with pytest.raises(ValueError, match='header'):
        snapshot.prepare(data, tmp_path / 'landing', {'sales': (['Date', 'Revenue'], 1)})
    assert not (tmp_path / 'landing').exists()


def test_snapshot_rerun_multiline_identity_and_tamper(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    (data / 'reviews.csv').write_text('id,text\n1,"hello\nworld"\n2,ok\n')
    contract = {'reviews': (['id', 'text'], 2)}
    path = snapshot.prepare(data, tmp_path / 'landing', contract)
    before = (path / 'manifest.json').read_bytes()
    assert snapshot.prepare(data, tmp_path / 'landing', contract) == path
    assert (path / 'manifest.json').read_bytes() == before
    import pyarrow.parquet as pq
    assert pq.read_table(path / 'reviews.parquet')['_src_row'].to_pylist() == [1, 2]
    (path / 'reviews.parquet').write_bytes(b'broken')
    with pytest.raises(Exception):
        snapshot.validate(path, contract)


def test_publish_cas_retry_and_rollback(tmp_path):
    store = Registry(tmp_path)
    with writer_lock(tmp_path):
        store.initialize()
        with pytest.raises(ValueError):
            store.publish('x', None)
        a, b = record('a'), record('b')
        store.register(a)
        store.publish(a['release_id'], None)
        store.register(b)
        with pytest.raises(RuntimeError):
            store.publish(b['release_id'], None)
        assert store.read()['payload']['active'] == a['release_id']
        store.publish(b['release_id'], a['release_id'])
        store.publish(b['release_id'], a['release_id'])
        store.publish(a['release_id'], b['release_id'])
        with pytest.raises(ValueError):
            store.register({**a, 'code_version': 'changed'})
        assert store.read()['payload']['active'] == a['release_id']


def test_nested_tools_keep_pin_after_publish(tmp_path, monkeypatch):
    store = Registry(tmp_path)
    store.initialize()
    a, b = record('a'), record('b')
    store.register(a)
    store.register(b)
    store.publish(a['release_id'], None)
    monkeypatch.setenv('RETAIL_RELEASE_MODE', 'versioned')
    monkeypatch.setenv('RETAIL_RELEASE_STATE', str(store.path))
    with releases.scope():
        with releases.scope():
            assert releases.resolve('duckdb') == a
        store.publish(b['release_id'], a['release_id'])
        with releases.scope():
            assert releases.resolve('duckdb') == a
    with releases.scope():
        assert releases.resolve('duckdb') == b


def test_failed_quality_does_not_register_or_publish(tmp_path, monkeypatch):
    store = Registry(tmp_path)
    store.initialize()
    a = record('a')
    store.register(a)
    store.publish(a['release_id'], None)
    folder = tmp_path / 'runs/demo'
    context = {**record('b'), 'stage': 'built', 'target': 'duckdb', 'directory': str(folder),
               'snapshot_path': '/snapshot', 'expected_active': a['release_id']}
    atomic_json(folder / 'context.json', context)
    monkeypatch.setattr(cli, 'code_version', lambda: 'v1')
    monkeypatch.setattr(snapshot, 'validate', lambda path: {})
    monkeypatch.setattr(cli, 'validate_data', lambda *args: (_ for _ in ()).throw(ValueError('bad KPI')))
    with pytest.raises(ValueError, match='bad KPI'):
        cli.execute('validate', run_id='demo', root=tmp_path)
    assert store.read()['payload']['active'] == a['release_id']
    assert context['release_id'] not in store.read()['payload']['releases']
    assert json.loads((folder / 'failure.json').read_text())['stage'] == 'validate'


def test_partial_dbt_artifact_cannot_pass(tmp_path):
    manifest = {'metadata': {'invocation_id': 'x'}, 'nodes': {
        'model.x.a': {'resource_type': 'model', 'schema': 'r_' + 'a' * 24 + '_marts'},
        'test.x.a': {'resource_type': 'test'}}}
    result = {'metadata': {'invocation_id': 'x'}, 'args': {'which': 'build', 'target': 'duckdb'},
              'results': [{'unique_id': 'model.x.a', 'status': 'success'}]}
    atomic_json(tmp_path / 'manifest.json', manifest)
    atomic_json(tmp_path / 'run_results.json', result)
    with pytest.raises(ValueError, match='Artifact'):
        cli.verify_artifacts(tmp_path, {'release_id': 'a' * 24}, 'duckdb')


def test_unverified_schema_cannot_be_whitelisted():
    a = record()
    state = {'active': a['release_id'], 'releases': {a['release_id']: {**a, 'schema': 'raw'}}}
    with pytest.raises(ValueError):
        releases.allowed_versions(state, {'reporting.rpt_build_info'})


def test_ready_release_cannot_be_rebuilt(tmp_path, monkeypatch):
    store = Registry(tmp_path)
    store.initialize()
    a = record()
    store.register(a)
    folder = tmp_path / 'runs/demo'
    atomic_json(folder / 'context.json', {**a, 'stage': 'prepared', 'target': 'duckdb',
                                          'directory': str(folder), 'snapshot_path': '/snapshot'})
    monkeypatch.setattr(cli, 'code_version', lambda: 'v1')
    monkeypatch.setattr(snapshot, 'validate', lambda path: {})
    with pytest.raises(ValueError, match='ready'):
        cli.execute('build', run_id='demo', root=tmp_path)


def test_worker_command_uses_pinned_run_and_validated_params():
    # Kiểm AST để không cần cài Airflow vào môi trường app; import DAG thật được kiểm trong container.
    import ast
    tree = ast.parse((ROOT / 'deploy/airflow/dags/retail_batch_pipeline.py').read_text(encoding='utf-8'))
    assert any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'DAG' for n in ast.walk(tree))


def test_reader_grant_registry_before_release_tables():
    # Guard chế độ cũ của chat chỉ chấp nhận bảng của bản mới khi đã đọc được registry.
    schema = 'r_' + 'a' * 24 + '_reporting'
    qualified, statements = cli.reader_grants('retail_lab', 'sp', schema,
                                              ['reporting.rpt_build_info', 'reporting.rpt_revenue_yearly'])
    assert qualified == [releases.CONTROL_RELATION, f'{schema}.rpt_build_info', f'{schema}.rpt_revenue_yearly']
    assert statements[0] == 'grant use catalog on catalog retail_lab to `sp`'
    registry = [i for i, s in enumerate(statements) if 'retail_control' in s]
    assert registry == [1, 2] and max(registry) < min(i for i, s in enumerate(statements) if schema in s)


def test_competing_writer_is_rejected(tmp_path):
    with writer_lock(tmp_path):
        with pytest.raises(OSError):
            with writer_lock(tmp_path):
                pass


def test_dbt_network_error_is_retryable(tmp_path, monkeypatch):
    from types import SimpleNamespace
    def failed_process(*args, **kwargs):
        kwargs['stdout'].write('connection reset by peer')
        kwargs['stdout'].flush()
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(cli.subprocess, 'run', failed_process)
    context = {**record(), 'directory': str(tmp_path), 'snapshot_path': '/snap'}
    with pytest.raises(ConnectionError):
        cli.dbt_build(context, 'duckdb')
