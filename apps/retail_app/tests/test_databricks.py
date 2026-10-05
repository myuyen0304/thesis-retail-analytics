"""Backend Databricks (lab, catalog retail_lab): app đọc ra đúng số như DuckDB, mọi trang vẽ được.

Khác các test backend khác, phần cần cloud CHỈ chạy khi đặt RETAIL_TEST_DATABRICKS=1 (không thì skip, không FAIL):
máy teammate không có workspace/profile, và mỗi lần chạy tốn quota Databricks Free. Chạy trên máy có profile:
    $env:RETAIL_TEST_DATABRICKS = '1'; .venv/Scripts/python.exe -m pytest apps/retail_app/tests/test_databricks.py
Điều kiện: đã `databricks auth login --profile retail-dev`, `.env.databricks.local` có profile + warehouse, và kho
Databricks dựng từ cùng code với warehouse/dbt.duckdb (scripts/databricks/run_dbt.py build).
Tiêu chí so như test_backends.py: cột, kiểu pandas giống hệt; cột không phải DOUBLE bằng tuyệt đối, DOUBLE rtol 1e-12.
"""
import os
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from dwh import connection, queries
from tests.test_backends import PER_BACKEND, PER_BUILD, _double_columns, assert_same
from tests.test_smoke import APP, PAGES

cloud = pytest.mark.skipif(os.environ.get('RETAIL_TEST_DATABRICKS') != '1',
                           reason='đặt RETAIL_TEST_DATABRICKS=1 để chạy test cần Databricks')


@cloud
@pytest.mark.parametrize('name', [n for n, t in queries.SOURCE.items() if t.split('.')[1] not in PER_BACKEND])
def test_databricks_cung_so_duckdb(name):
    table = queries.SOURCE[name].split('.')[1]
    drop = PER_BUILD.get(table, [])
    db, dk = getattr(queries, name)('databricks'), getattr(queries, name)('duckdb')
    assert_same(db.drop(columns=drop), dk.drop(columns=drop), _double_columns(table))


@cloud
def test_databricks_suc_khoe_tot():
    # nhật ký nạp + test của chính kho Databricks: kho đạt, đủ 14 nguồn trong log nạp
    s = queries.health_summary('databricks').iloc[0]
    assert s['status_code'] == 'tot' and s['ingest_mode'] == 'log' and s['n_sources_ingested'] == 14
    assert len(queries.health_ingest('databricks')) == 14


@cloud
@pytest.mark.parametrize('page', PAGES)
def test_trang_chay_tren_databricks(monkeypatch, page):
    monkeypatch.setenv('RETAIL_BACKEND', 'databricks')
    st.cache_data.clear()
    at = AppTest.from_file(str(APP), default_timeout=120).run()
    if page != PAGES[0]:
        at.switch_page(page).run()
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]
    assert at.sidebar.radio[0].value == 'databricks'
    assert any('Databricks catalog retail_lab' in c.value for c in at.caption)


def test_thieu_cau_hinh_databricks_thi_bao_loi_ro(monkeypatch):
    # không cần cloud: không có .env.databricks.local / biến môi trường → báo cách đăng nhập, không văng exception
    monkeypatch.setenv('RETAIL_BACKEND', 'databricks')
    monkeypatch.setattr(connection, 'DATABRICKS_CONFIG', Path('khong_co_file_nay.env'))
    for k in [k for k in os.environ if k.startswith(('DATABRICKS_', 'RETAIL_DATABRICKS_'))]:
        monkeypatch.delenv(k)
    st.cache_data.clear()
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception
    assert 'Không đọc được' in at.error[0].value
    assert 'databricks auth login' in at.info[0].value
