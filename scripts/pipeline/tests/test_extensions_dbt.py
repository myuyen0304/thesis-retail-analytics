"""D1–D8: truyền biến dbt và cổng hiển thị theo hợp đồng, không cần dữ liệu thật."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import duckdb
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.pipeline import cli
from scripts.ingest import extension_contract


@pytest.fixture
def case(tmp_path, monkeypatch):
    context = dict(release_id='x', snapshot_id='snapshot', code_version='code',
                   snapshot_path=str(tmp_path), directory=str(tmp_path),
                   duckdb_path=str(tmp_path / 'scratch.duckdb'), target='duckdb')
    calls = []
    columns = [('r_x_marts', 'dim_sales_employee', col) for col in
               ('sales_employee_sk', 'sales_employee_id', 'sales_employee_name', 'years_experience')]

    class Connection:
        description = [('value',)]

        def execute(self, sql):
            calls.append(sql)
            if 'read_parquet' in sql:
                self.rows = [('2022-01-01', '10', '5')]
            elif 'fact_daily_sales' in sql:
                self.rows = [(20220101, '10', '5')]
            elif 'rpt_health_summary' in sql:
                self.rows = [('tot',)]
            elif 'information_schema.columns' in sql:
                assert "'r_x_marts'" in sql and "'r_x_reporting'" in sql
                self.rows = columns
            else:
                raise AssertionError(sql)
            return self

        def fetchall(self):
            return self.rows

        def close(self):
            pass

    monkeypatch.setattr(duckdb, 'connect', lambda *a, **k: Connection())
    monkeypatch.setattr(cli, 'verify_artifacts', lambda *a: {'nodes': {}})
    return SimpleNamespace(context=context, columns=columns, calls=calls)


def build_vars(case, monkeypatch):
    commands = []
    monkeypatch.setattr(cli.subprocess, 'run', lambda cmd, **kw:
                        commands.append(cmd) or SimpleNamespace(returncode=0))
    cli.dbt_build(case.context, 'duckdb')
    assert len(commands) == 1
    return json.loads(commands[0][commands[0].index('--vars') + 1])


@pytest.mark.parametrize('forecast', [False, True])
def test_d1_disabled_vars(case, monkeypatch, forecast):
    keys = ['release_id', 'snapshot_id', 'code_version', 'snapshot_path']
    if forecast:
        case.context['forecast_path'] = 'forecast'
        keys.append('forecast_path')
    assert build_vars(case, monkeypatch) == {k: case.context[k] for k in keys}


def test_d2_enabled_vars(case, monkeypatch):
    case.context['extensions'] = ['orders_enriched']
    assert build_vars(case, monkeypatch)['extensions'] == ['orders_enriched']


def test_d3_silver_in_marts(case):
    case.context['extensions'] = ['orders_enriched']
    case.columns.append(('r_x_marts', 'dim_sales_employee', 'marital_status'))
    with pytest.raises(ValueError, match='marital_status.*r_x_marts.dim_sales_employee'):
        cli.validate_data(case.context)


def test_d4_silver_in_reporting_case_insensitive(case):
    case.context['extensions'] = ['orders_enriched']
    case.columns.append(('r_x_reporting', 'rpt_employee', 'MARITAL_STATUS'))
    with pytest.raises(ValueError, match='marital_status.*r_x_reporting.rpt_employee'):
        cli.validate_data(case.context)


def test_d5_missing_mart_column(case):
    case.context['extensions'] = ['orders_enriched']
    case.columns[:] = [r for r in case.columns if r[2] != 'sales_employee_name']
    with pytest.raises(ValueError, match='sales_employee_name'):
        cli.validate_data(case.context)


def test_d6_visibility_pass(case):
    case.context['extensions'] = ['orders_enriched']
    result = cli.validate_data(case.context)
    assert result == dict(daily_rows=1, relations_checked=0, cloud_parity=False,
                          hidden_columns_checked=3, mart_columns_checked=3)
    assert sum('information_schema.columns' in q for q in case.calls) == 1


def test_d7_disabled_gate(case):
    case.columns.append(('r_x_reporting', 'legacy', 'marital_status'))
    assert cli.validate_data(case.context) == dict(daily_rows=1, relations_checked=0, cloud_parity=False)
    assert not any('information_schema.columns' in q for q in case.calls)


def test_d8_visibility_follows_contract(case, tmp_path, monkeypatch):
    doc = yaml.safe_load((extension_contract.CONTRACT_DIR / 'orders_enriched.yml').read_text(encoding='utf-8'))
    for col in doc['cot']:
        if col['ten'] == 'years_experience':
            col['hien_thi'] = 'silver'
    (tmp_path / 'orders_enriched.yml').write_text(yaml.safe_dump(doc, allow_unicode=True), encoding='utf-8')
    monkeypatch.setattr(extension_contract, 'CONTRACT_DIR', tmp_path)
    case.context['extensions'] = ['orders_enriched']
    with pytest.raises(ValueError, match='years_experience.*r_x_marts.dim_sales_employee'):
        cli.validate_data(case.context)


@pytest.mark.parametrize('visibility', [None, 'Silver'], ids=['missing', 'wrong_case'])
def test_d9_invalid_visibility(case, tmp_path, monkeypatch, visibility):
    doc = yaml.safe_load((extension_contract.CONTRACT_DIR / 'orders_enriched.yml').read_text(encoding='utf-8'))
    for col in doc['cot']:
        if col['ten'] == 'marital_status':
            if visibility is None:
                col.pop('hien_thi')
            else:
                col['hien_thi'] = visibility
    (tmp_path / 'orders_enriched.yml').write_text(yaml.safe_dump(doc, allow_unicode=True), encoding='utf-8')
    monkeypatch.setattr(extension_contract, 'CONTRACT_DIR', tmp_path)
    case.context['extensions'] = ['orders_enriched']
    case.columns.append(('r_x_marts', 'dim_sales_employee', 'marital_status'))
    with pytest.raises(ValueError, match='hien_thi'):
        cli.validate_data(case.context)


def test_d5_mart_column_only_in_reporting(case):
    case.context['extensions'] = ['orders_enriched']
    case.columns[:] = [r for r in case.columns if r[2] != 'sales_employee_name']
    case.columns.append(('r_x_reporting', 'rpt_employee', 'sales_employee_name'))
    with pytest.raises(ValueError, match='sales_employee_name'):
        cli.validate_data(case.context)
