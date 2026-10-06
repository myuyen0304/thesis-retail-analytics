"""Smoke test: mở từng trang ở chế độ không giao diện (streamlit.testing), không được có lỗi."""
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from ui.fmt import num, pct

APP = Path(__file__).resolve().parents[1] / 'app.py'
PAGES = ['views/tong_quan.py', 'views/ps1_do_dung.py', 'views/ps2_xu_huong.py', 'views/ps3_nhip_lich.py',
         'views/ps4_don_mon_gia.py', 'views/ps5_nhom.py', 'views/suc_khoe_du_lieu.py', 'views/ai_explain.py']


@pytest.mark.parametrize('backend', ['postgres', 'duckdb'])
@pytest.mark.parametrize('page', PAGES)
def test_trang_chay_khong_loi(monkeypatch, backend, page):
    monkeypatch.setenv('RETAIL_BACKEND', backend)
    st.cache_data.clear()
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    if page != PAGES[0]:
        at.switch_page(page).run()
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]
    assert at.main.children, 'trang không vẽ gì'
    # Thanh bên vẽ ở app.py phải còn trên mọi trang. (Thư mục trang tên `views/`, không phải `pages/`:
    # tên `pages/` làm AppTest chạy thẳng file trang theo kiểu multipage cũ, bỏ qua app.py.)
    assert at.sidebar.radio[0].value == backend
    # Dải thông tin chung (plan §3, tiêu chí 3) có ở mọi trang, đủ 4 mục
    strip = [m.value for m in at.markdown if 'Kỳ phân tích:' in m.value]
    assert len(strip) == 1, 'thiếu dải thông tin chung'
    for muc in ['Kỳ phân tích:', '**R** =', '**G** =', 'Trạng thái snapshot:', 'Refresh:']:
        assert muc in strip[0], muc
    assert at.title, 'trang không có tiêu đề'


def test_thanh_ben_co_chon_backend():
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert at.sidebar.radio[0].options == ['PostgreSQL (Docker)', 'DuckDB (file, dự phòng)', 'Databricks (cloud, production)']


def test_retail_backends_gioi_han_thanh_ben(monkeypatch):
    # App deploy trên Databricks Apps chỉ bật databricks (deploy/databricks_app/app.yaml); ở đây thử với duckdb
    from dwh import connection
    monkeypatch.setenv('RETAIL_BACKENDS', 'duckdb')
    monkeypatch.setenv('RETAIL_BACKEND', 'duckdb')
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception and at.sidebar.radio[0].options == ['DuckDB (file, dự phòng)']
    monkeypatch.setenv('RETAIL_BACKEND', 'postgres')           # backend mặc định phải nằm trong danh sách bật
    with pytest.raises(ValueError):
        connection.default_backend()
    monkeypatch.setenv('RETAIL_BACKENDS', 'duckdb,snowflake')
    with pytest.raises(ValueError):
        connection.enabled_backends()


def test_tong_quan_doc_du_11_nam():
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception
    assert len(at.dataframe[0].value) == 11
    assert at.dataframe[0].value['Năm'].tolist() == list(range(2012, 2023))


def test_dinh_dang_so_kieu_viet():
    assert num(16430476585.53, 2) == '16.430.476.585,53'
    assert pct(0.7619, 1) == '76,2%'
    assert num(float('nan')) == '–'


def test_postgres_khong_chay_thi_bao_loi_ro(monkeypatch):
    # giả lập Docker tắt: trỏ sai cổng → trang báo lỗi + gợi ý chuyển DuckDB, không văng exception
    monkeypatch.setenv('RETAIL_BACKEND', 'postgres')
    monkeypatch.setenv('PG_PORT', '5999')
    st.cache_data.clear()
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception
    assert 'Không đọc được' in at.error[0].value
    assert 'DuckDB' in at.info[0].value


@pytest.mark.parametrize('backend, noi_doc', [('postgres', 'PostgreSQL localhost:5433/retail'),
                                              ('duckdb', 'DuckDB warehouse/dbt.duckdb')])
def test_bam_doc_lai_thi_bao_thanh_cong(monkeypatch, backend, noi_doc):
    monkeypatch.setenv('RETAIL_BACKEND', backend)
    st.cache_data.clear()
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.success                              # chưa bấm: chỉ có dòng "Nguồn: ..."
    assert any(noi_doc in c.value for c in at.caption)
    at.sidebar.button[0].click().run()
    assert not at.exception and not at.error
    msg = at.success[0].value
    assert 'thành công' in msg and noi_doc in msg
    # liệt kê MỌI bảng trang Tổng quan đã đọc, kèm số dòng
    for bang in ['rpt_build_info` (1 dòng)', 'rpt_revenue_total` (2 dòng)', 'rpt_revenue_yearly` (11 dòng)']:
        assert bang in msg, bang
    at.run()                                           # lần chạy sau (không bấm) thì thông báo biến mất
    assert not at.success


def test_bam_doc_lai_khi_postgres_tat_thi_khong_bao_thanh_cong(monkeypatch):
    monkeypatch.setenv('RETAIL_BACKEND', 'postgres')
    monkeypatch.setenv('PG_PORT', '5999')
    st.cache_data.clear()
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    at.sidebar.button[0].click().run()
    assert not at.success
    assert 'Không đọc được' in at.error[0].value
