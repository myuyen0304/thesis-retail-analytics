"""A1–A5: gọi command thật, thay riêng thư viện Airflow để không cần scheduler."""
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType

import pytest

DAG_PATH = Path(__file__).resolve().parents[3] / 'deploy/airflow/dags/retail_batch_pipeline.py'
STAGES = ('prepare', 'forecast', 'build', 'validate', 'publish')


class FakeDAG:
    def __init__(self, **kwargs):
        self.params = kwargs['params']

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeParam:
    def __init__(self, default, **schema):
        self.default, self.schema = default, schema


class FakeTask:
    def override(self, **kwargs):
        return self

    def __call__(self, *args, **kwargs):
        return self

    def __rshift__(self, other):
        return other


@pytest.fixture
def load_dag(monkeypatch):
    monkeypatch.delenv('RETAIL_PIPELINE_DEFAULT_EXTENSIONS', raising=False)
    sdk = ModuleType('airflow.sdk')
    sdk.DAG, sdk.Param = FakeDAG, FakeParam
    sdk.get_current_context = lambda: {}
    sdk.task = lambda fn: FakeTask()
    exceptions = ModuleType('airflow.exceptions')
    exceptions.AirflowFailException = type('AirflowFailException', (Exception,), {})
    pendulum = ModuleType('pendulum')
    pendulum.datetime = lambda *args, **kwargs: None
    for name, module in {'airflow': ModuleType('airflow'), 'airflow.sdk': sdk,
                         'airflow.exceptions': exceptions, 'pendulum': pendulum}.items():
        monkeypatch.setitem(sys.modules, name, module)

    def load():
        spec = importlib.util.spec_from_file_location('retail_dag_under_test', DAG_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return load


def context(**params):
    return {'run_id': 'abc', 'params': {'target': 'databricks', **params}}


def baseline(stage):
    # Danh sách viết tay từ code trước lát 4, gồm SHA-256('abc') rút 24 ký tự.
    return ['/opt/pipeline/bin/python', '-m', 'scripts.pipeline.cli', stage,
            '--run-id', 'ba7816bf8f01cfea414140de', '--target', 'databricks',
            '--root', 'warehouse/pipeline/docker']


@pytest.mark.parametrize('params', [{}, {'extensions': []}], ids=['missing', 'empty'])
def test_a1_no_extensions(load_dag, params):
    dag = load_dag()
    for stage in STAGES:
        actual = dag.command(stage, context(**params))
        assert actual == baseline(stage)
        print(json.dumps({'A1': stage, 'command': actual}))


def test_a2_prepare_only(load_dag):
    dag = load_dag()
    for stage in STAGES:
        actual = dag.command(stage, context(extensions=['orders_enriched']))
        expected = baseline(stage) + (['--extension', 'orders_enriched'] if stage == 'prepare' else [])
        assert actual == expected
        print(json.dumps({'A2': stage, 'command': actual}))


def test_a3_sorted_unique_with_options(load_dag):
    dag = load_dag()
    actual = dag.command('prepare', context(extensions=['z_extra', 'orders_enriched', 'z_extra'],
                                            snapshot_id='47e7cbe765d9', force=True))
    assert actual == baseline('prepare') + ['--snapshot-id', '47e7cbe765d9', '--force',
                                           '--extension', 'orders_enriched', '--extension', 'z_extra']


@pytest.mark.parametrize('raw,expected', [(None, []), ('', []), (' orders_enriched , ', ['orders_enriched'])],
                         ids=['unset', 'empty', 'configured'])
def test_a4_environment_default(load_dag, monkeypatch, raw, expected):
    if raw is not None:
        monkeypatch.setenv('RETAIL_PIPELINE_DEFAULT_EXTENSIONS', raw)
    param = load_dag().dag.params['extensions']
    assert param.default == expected
    assert param.schema == {'type': 'array', 'items': {'type': 'string', 'pattern': '^[a-z][a-z0-9_]*$'}}


@pytest.mark.parametrize('raw', ['Orders', 'a b'])
def test_a5_invalid_default(load_dag, monkeypatch, raw):
    monkeypatch.setenv('RETAIL_PIPELINE_DEFAULT_EXTENSIONS', raw)
    with pytest.raises(ValueError, match='RETAIL_PIPELINE_DEFAULT_EXTENSIONS'):
        load_dag()
