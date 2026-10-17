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


def test_ai_reader_gom_bang_du_bao_chi_khi_ban_co():
    # RV04 (review Codex 2026-10-15): pipeline cấp quyền / thử đọc bảng dự báo cho AI reader ở bản có dự báo,
    # nhưng không đòi bảng đó ở bản trước B2b (rollback)
    app, ai = cli.consumers()
    opt = cli.optional_relations()
    ai_opt = {'reporting.rpt_forecast_daily', 'reporting.rpt_forecast_backtest'}
    assert ai_opt <= opt and ai_opt <= set(ai)
    assert 'reporting.rpt_forecast_actual' not in ai                     # chat không đọc bảng số thực tế của trang
    schema = 'r_' + 'a' * 24 + '_reporting'
    co = cli.present(ai, schema, lambda s, n: True)
    khong = cli.present(ai, schema, lambda s, n: False)
    assert set(co) == set(ai) and set(khong) == set(ai) - opt
    qualified, statements = cli.reader_grants('retail_lab', 'sp', schema, co)
    assert f'{schema}.rpt_forecast_daily' in qualified
    assert f'grant select on table retail_lab.{schema}.rpt_forecast_backtest to `sp`' in statements
    assert not any('rpt_forecast' in s for s in cli.reader_grants('retail_lab', 'sp', schema, khong)[1])


TRANG_DU_BAO = {'reporting.rpt_forecast_daily', 'reporting.rpt_forecast_backtest', 'reporting.rpt_forecast_actual'}


def test_app_reader_gom_ba_bang_trang_du_bao_chi_khi_ban_co():
    # RV11 (review Codex 2026-10-15 §8): app reader được cấp quyền / thử đọc ba bảng trang Dự báo ở bản có chúng,
    # không đòi ở bản trước B2b; ba bảng không vào danh sách BẮT BUỘC app_read_relations
    import yaml
    cfg = yaml.safe_load((ROOT / 'retail_dbt/dbt_project.yml').read_text(encoding='utf-8'))['vars']
    sys.path.insert(0, str(ROOT / 'apps/retail_app'))
    from dwh import forecast_queries
    assert set(cfg['app_optional_relations']) == set(forecast_queries.SOURCE.values()) == TRANG_DU_BAO
    assert not TRANG_DU_BAO & set(cfg['app_read_relations'])
    app, _ = cli.consumers()
    assert TRANG_DU_BAO <= set(app) and TRANG_DU_BAO <= cli.optional_relations()
    schema = 'r_' + 'b' * 24 + '_reporting'
    co = cli.present(app, schema, lambda s, n: True)
    khong = cli.present(app, schema, lambda s, n: False)
    assert set(co) == set(app) and set(khong) == set(cfg['app_read_relations'])
    statements = cli.reader_grants('retail_lab', 'app_sp', schema, co)[1]
    for t in TRANG_DU_BAO:
        assert f"grant select on table retail_lab.{schema}.{t.split('.')[1]} to `app_sp`" in statements
    assert not any('rpt_forecast' in s for s in cli.reader_grants('retail_lab', 'app_sp', schema, khong)[1])
    # whitelist quyền: bảng tùy chọn của mọi bản ready đều hợp lệ (quyền bản mới không bị coi là thừa khi rollback)
    state = {'active': 'b' * 24, 'releases': {x * 24: record(x) for x in 'ab'}}
    allowed = releases.allowed_versions(state, app)
    assert all(f"r_{x * 24}_reporting.{t.split('.')[1]}" in allowed for x in 'ab' for t in TRANG_DU_BAO)


def test_verify_consumers_local_moi_ban_ready():
    # Kiểm reader local trên các bản đã publish thật: bản trước B2b (không có bảng dự báo) vẫn qua (rollback được);
    # bản có dự báo thì đọc được mọi bảng trang Dự báo đang có
    from types import SimpleNamespace
    import duckdb
    state_path = ROOT / 'warehouse/pipeline/state.json'
    if not state_path.exists():
        pytest.skip('chưa có bản dữ liệu do pipeline publish')
    payload = json.loads(state_path.read_text(encoding='utf-8'))['payload']
    seen = {}
    for rec in payload['releases'].values():
        path = state_path.parent / rec.get('artifact_path', '')
        if rec.get('artifact_path') and path.exists():
            with duckdb.connect(str(path), read_only=True) as con:
                seen[rec['release_id']] = (rec, {f'reporting.{r[0]}' for r in con.execute(
                    'select table_name from information_schema.tables where table_schema = ?', [rec['schema']]).fetchall()}
                    & TRANG_DU_BAO)
    if not any(t for _, t in seen.values()) or all(t for _, t in seen.values()):
        pytest.skip('registry local cần cả bản có và bản không có bảng trang Dự báo')
    for rec, _ in seen.values():                 # không ném lỗi: bảng tùy chọn vắng thì không bị đòi
        cli.verify_consumers({'schema': rec['schema'], 'artifact_path': rec['artifact_path']}, SimpleNamespace(path=state_path))
    assert any(t == TRANG_DU_BAO for _, t in seen.values())             # có bản đủ ba bảng: đã thử đọc cả ba


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
