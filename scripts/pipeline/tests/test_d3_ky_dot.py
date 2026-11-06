"""D3: SQL biên dịch thật của dbt. Không đợt thì giống hệt commit gốc; có đợt thì kỳ mở tới năm mới. Không cần dữ liệu."""
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[3]
DBT = str(Path(sys.executable).with_name('dbt.exe' if os.name == 'nt' else 'dbt'))
GOC = '49d3454'   # commit ngay trước khi sửa D3
BUILT_AT = re.compile(rb"cast\('[0-9: -]+' as timestamp\) as built_at_utc")
DOT = {'co_dot': True, 'analysis_end_year': 2023, 'last_actual_date': '2023-12-31', 'forecast_trained_through': '2022-12-31',
       'dot_so_dong': {'orders': 7, 'order_items': 9, 'promotions': 2}}


def compile_project(project, out, extra):
    out.mkdir(parents=True)
    variables = {'release_id': 'a' * 24, 'snapshot_id': 'a' * 12, 'code_version': 'kiem',
                 'snapshot_path': (out.parent / 'gia').as_posix(), 'forecast_path': (out.parent / 'gia_fc').as_posix(), **extra}
    result = subprocess.run([DBT, 'compile', '--project-dir', str(project), '--profiles-dir', str(project), '--target', 'duckdb',
                             '--target-path', str(out), '--log-path', str(out / 'logs'), '--no-partial-parse',
                             '--vars', json.dumps(variables)], cwd=project.parent, capture_output=True, text=True,
                            env={**os.environ, 'PYTHONUTF8': '1', 'RETAIL_DUCKDB_BUILD_PATH': str(out.parent / 'kho.duckdb')})
    assert result.returncode == 0, result.stdout[-2000:]
    folder = out / 'compiled' / 'retail_dbt'
    return {p.relative_to(folder).as_posix(): BUILT_AT.sub(b'GIO', p.read_bytes().replace(b'\r\n', b'\n'))
            for p in folder.rglob('*') if p.is_file()}


@pytest.fixture(scope='module')
def compiled(tmp_path_factory):
    return compile_project(ROOT / 'retail_dbt', tmp_path_factory.mktemp('dot') / 'c', DOT)


def text(compiled, name):
    found = [v for k, v in compiled.items() if k.endswith('/' + name + '.sql')]
    assert len(found) == 1, name
    return re.sub(r'"kho"\."[^"]+"\."(\w+)"', r'"\1"', found[0].decode('utf-8'))


def test_no_batch_sql_is_byte_identical(tmp_path):
    if subprocess.run(['git', 'cat-file', '-e', GOC + '^{commit}'], cwd=ROOT, capture_output=True).returncode:
        pytest.skip('Không còn commit gốc trong lịch sử')
    raw = subprocess.run(['git', 'archive', GOC, 'retail_dbt'], cwd=ROOT, capture_output=True, check=True).stdout
    (tmp_path / 'goc').mkdir()
    tarfile.open(fileobj=io.BytesIO(raw)).extractall(tmp_path / 'goc', filter='data')
    old = compile_project(tmp_path / 'goc' / 'retail_dbt', tmp_path / 'cu', {})
    new = compile_project(ROOT / 'retail_dbt', tmp_path / 'moi', {})
    assert sorted(old) == sorted(new)
    assert [k for k in old if old[k] != new[k]] == []


def test_batch_test_enabled_only_with_batch(compiled):
    assert any(k.endswith('/assert_ky_dot.sql') for k in compiled)


def test_forecast_rows_stop_at_last_actual(compiled):
    con = duckdb.connect()
    con.execute("""create table fact_order_item as select 20231231 as date_sk, 5.0 as gross_amount, 3.0 as cogs_amount""")
    con.execute("""create table stg_sample_submission as select cast(d as date) as sales_date, 1.0 as revenue, 1.0 as cogs
                   from generate_series(date '2023-01-01', date '2024-07-01', interval 1 day) t(d)""")
    rows = con.execute('select count(*) filter (where not is_actual), min(date_sk) filter (where not is_actual), '
                       'max(date_sk) filter (where not is_actual), count(*) filter (where is_actual) from ('
                       + text(compiled, 'fact_daily_sales') + ')').fetchone()
    assert rows == (183, 20240101, 20240701, 1)


def test_forecast_period_flag_moves(compiled):
    con = duckdb.connect()
    flags = con.execute('select full_date, is_forecast_period from (' + text(compiled, 'dim_date') + ") "
                        "where full_date in (date '2022-12-31', date '2023-12-31', date '2024-01-01')").fetchall()
    assert [f[1] for f in sorted(flags)] == [False, False, True]


def test_last_phase_extends_without_touching_earlier(compiled):
    sql = text(compiled, 'rpt_revenue_phase')
    start = sql.index('(select phase_code, phase_name')
    end = sql.index(') p', start) + 1
    con = duckdb.connect()
    con.execute("""create table ps2_phases as select * from (values
        ('A', 'a', 2013, 2016, 'x', 'y'), ('B', 'b', 2016, 2018, 'x', 'y'),
        ('C', 'c', 2018, 2019, 'x', 'y'), ('D', 'd', 2019, 2022, 'x', 'y'))
        t(phase_code, phase_name, start_year, end_year, trend, end_turn_note)""")
    rows = con.execute('select phase_code, start_year, end_year from ' + sql[start:end] + ' order by 1').fetchall()
    assert rows == [('A', 2013, 2016), ('B', 2016, 2018), ('C', 2018, 2019), ('D', 2019, 2023)]


def test_period_totals_three_rows(compiled):
    sql = text(compiled, 'rpt_revenue_total')
    assert "'2013-2023', 2013, 2023, true" in sql and "'2013-2022', 2013, 2022, false" in sql


def test_reporting_year_ends_follow_period(compiled):
    for name in ('rpt_revenue_monthly', 'rpt_revenue_yearly', 'rpt_revenue_segment_yearly'):
        assert 'year between 2013 and 2023' in text(compiled, name)
    assert re.search(r'2023\s+as analysis_end_year', text(compiled, 'rpt_build_info'))


def test_forecast_actual_stops_at_trained_through(compiled):
    assert "d.full_date <= cast('2022-12-31' as date)" in text(compiled, 'rpt_forecast_actual')


def test_row_count_test_adds_batch_rows(compiled):
    sql = text(compiled, 'assert_row_counts')
    assert "'fact_order', 646952" in sql and "'fact_order_item', 714678" in sql and "'dim_promotion', 52" in sql
    assert "'fact_daily_sales', 4381" in sql and '276522' not in sql


def test_stability_counts_years_of_period(compiled):
    sql = text(compiled, 'assert_rpt_calendar_phase')
    assert 's.n_years <> 11' in sql and 's.n_years <> 10' not in sql


def test_direct_split_keeps_threshold_except_extended_phase(compiled):
    sql = text(compiled, 'assert_rpt_driver')
    assert "where (period_code <> 'D' and (abs(contrib_n - dn) >= 5e6" in sql
    assert 'coalesce(top_up_driver, \'-\') <> coalesce(case when greatest(dn, du, dq)' in sql   # D vẫn phải cùng kết luận
