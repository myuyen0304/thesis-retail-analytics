"""M0: Postgres và DuckDB trả về cùng số (docs/gd2_app_plan.md §6, §7 mục 2).

Tiêu chí M0 (rpt_revenue_yearly): giống hệt mọi cột. Khi quét mọi bảng reporting (M1: 10 bảng; M2 bổ sung: 13) thì:
- cột DECIMAL, số nguyên, boolean, chuỗi, ngày: bằng nhau tuyệt đối;
- cột DOUBLE (tỷ số, phân rã…) mỗi engine tự tính: sai số tương đối ≤ 1e-12.
Riêng rpt_build_info bỏ cột built_at_utc (lúc build, mỗi backend một khác).
Postgres không chạy thì test FAIL, không skip.
"""
import duckdb
import numpy as np
import pandas as pd
import pytest

from dwh import queries
from dwh.connection import DUCKDB_PATH, read_sql

RTOL = 1e-12
TABLES = {   # bảng → khóa để xếp thứ tự
    'rpt_revenue_yearly': ['year'],
    'rpt_revenue_monthly': ['month_start_date'],
    'rpt_revenue_segment_yearly': ['dimension_name', 'dimension_value', 'year'],
    'rpt_august_parity': [],
    'rpt_revenue_phase': ['phase_code'],
    'rpt_revenue_turning_point': ['turning_year'],
    'ps2_phases': ['phase_code'],
    'rpt_revenue_total': ['period_code'],
    'rpt_revenue_bridge': ['period_code', 'step_order'],
    'rpt_build_info': [],
    'rpt_revenue_direction': ['window_months', 'month_start_date'],          # M2 bổ sung
    'rpt_revenue_direction_change': ['window_months', 'change_month_date'],
    'ps2_direction_rule': ['window_months'],
    'rpt_calendar_phase': ['phase_code'],                                     # góp ý M3
    'rpt_calendar_phase_month': ['phase_code', 'month'],
    'rpt_calendar_stability': ['rhythm_order'],
    'rpt_driver_period': ['period_code'],                                     # M4
    'rpt_driver_bridge': ['period_code', 'bridge_code', 'step_order'],
    'driver_rule': [],
}
# Cột khác nhau theo lần build (mỗi backend build một lúc) → không so, các cột còn lại vẫn so
PER_BUILD = {'rpt_build_info': ['built_at_utc']}
# M5: view trên nhật ký chạy dbt của CHÍNH từng kho (giờ chạy, số lần chạy, log nạp chỉ có ở Postgres) → cố ý khác nhau
# giữa hai backend, không so. Đúng/sai của các view này kiểm ở assert_rpt_health (dbt) và tests/test_m5.py.
PER_BACKEND = {
    'rpt_health_summary': [],
    'rpt_health_test': ['test_name'],
    'rpt_health_run': ['started_at_utc'],
    'rpt_health_ingest': ['source'],
}


def _double_columns(table: str) -> set[str]:
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        rows = con.execute(
            "select column_name from information_schema.columns "
            "where table_schema = 'reporting' and table_name = ? and data_type = 'DOUBLE'", [table]
        ).fetchall()
    finally:
        con.close()
    return {r[0] for r in rows}


def assert_same(pg: pd.DataFrame, dk: pd.DataFrame, doubles: set[str]) -> None:
    assert list(pg.columns) == list(dk.columns)
    assert len(pg) == len(dk)
    for c in pg.columns:
        assert pg[c].dtype == dk[c].dtype, c
        if c in doubles:
            a, b = pg[c].to_numpy(), dk[c].to_numpy()
            assert np.array_equal(np.isnan(a), np.isnan(b)), c
            np.testing.assert_allclose(a, b, rtol=RTOL, atol=0, equal_nan=True, err_msg=c)
        else:
            pd.testing.assert_series_equal(pg[c], dk[c], check_exact=True, obj=c)


def test_revenue_yearly_hai_backend():
    pg, dk = queries.revenue_yearly('postgres'), queries.revenue_yearly('duckdb')
    assert pg['year'].tolist() == list(range(2012, 2023))
    # tiêu chí M0: giống hệt, kể cả cột DOUBLE (không dùng sai số)
    pd.testing.assert_frame_equal(pg, dk, check_exact=True)


def test_phep_so_bat_duoc_sai_lech():
    # mutation: lệch R 0,01 hoặc U 1e-9 (tương đối) thì phép so hai backend phải FAIL
    pg, dk = queries.revenue_yearly('postgres'), queries.revenue_yearly('duckdb')
    doubles = _double_columns('rpt_revenue_yearly')
    for col, change in [('r', lambda x: x + 0.01), ('u', lambda x: x * (1 + 1e-9))]:
        bad = dk.copy()
        bad.loc[5, col] = change(bad.loc[5, col])
        with pytest.raises(AssertionError):
            assert_same(pg, bad, doubles)


@pytest.mark.parametrize('query_name', queries.SOURCE)
def test_ham_query_dung_bang_goc(query_name):
    # hàm trong queries.py không làm gì ngoài SELECT: so với đọc thẳng bảng ghi trong SOURCE
    table = queries.SOURCE[query_name]
    keys = {**TABLES, **PER_BACKEND}[table.split('.')[1]]
    got = getattr(queries, query_name)('duckdb')
    direct = read_sql(f'select * from {table}', 'duckdb')
    if query_name == 'health_run':   # hàm chỉ lấy 10 lần chạy gần nhất
        direct = direct.sort_values('started_at_utc', ascending=False).head(10)
    if keys:
        got, direct = (d.sort_values(keys, ignore_index=True) for d in (got, direct))
    pd.testing.assert_frame_equal(got, direct, check_exact=True)


@pytest.mark.parametrize('table', TABLES)
def test_moi_bang_reporting_hai_backend(table):
    keys = TABLES[table]
    pg, dk = (read_sql(f'select * from reporting.{table}', b).drop(columns=PER_BUILD.get(table, []))
              for b in ('postgres', 'duckdb'))
    if keys:
        pg, dk = (d.sort_values(keys, ignore_index=True) for d in (pg, dk))
    assert len(pg) > 0
    assert_same(pg, dk, _double_columns(table))


def test_khong_bo_sot_bang_reporting():
    # thêm model rpt_* mới mà quên đưa vào TABLES thì test này FAIL
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    try:
        # cả bảng lẫn view (rpt_august_parity là view)
        rows = con.execute("select table_name from information_schema.tables "
                           "where table_schema = 'reporting'").fetchall()
    finally:
        con.close()
    # int_reporting_order_items là view trung gian (grain dòng hàng), app không đọc
    assert {r[0] for r in rows if not r[0].startswith('int_')} == set(TABLES) | set(PER_BACKEND)
