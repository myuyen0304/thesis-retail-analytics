# pytest đặt thư mục chứa file này vào sys.path → test import được `dwh`, `ui` giống lúc chạy app.
import os
import uuid

import psycopg
import pytest
import streamlit as st

from ui import auth_store, roles

AUTH_CONFIGURED = roles.auth_configured      # bản thật, cho test cần kiểm nhánh có DB tài khoản (test_roles.py)
DEFAULT_PAGE = dict(roles.DEFAULT_PAGE)      # bản thật, test_roles.py kiểm trang mở mặc định của từng role
PG_URL = (f"postgresql://{os.environ.get('PG_USER', 'retail')}:{os.environ.get('PG_PASSWORD', 'retail')}"
          f"@{os.environ.get('PG_HOST', 'localhost')}:{os.environ.get('PG_PORT', '5433')}"
          f"/{os.environ.get('PG_DATABASE', 'retail')}")


@pytest.fixture(autouse=True)
def _role_admin(monkeypatch):
    """Test cũ kiểm mọi trang và radio backend nên chạy với role admin (docs/phan_quyen.md §5), mở đầu ở Tổng quan như
    trước khi có role. Tắt đăng nhập (DB tài khoản trong secrets.toml / RETAIL_APP_DB_URL của máy, nếu có), để kết quả
    test không phụ thuộc cấu hình local."""
    monkeypatch.setenv('RETAIL_APP_ROLE', 'admin')
    monkeypatch.delenv('RETAIL_APP_DB_URL', raising=False)
    monkeypatch.setattr(roles, 'auth_configured', lambda: False)
    monkeypatch.setitem(roles.DEFAULT_PAGE, 'admin', 'tong_quan')


@pytest.fixture
def kho_tai_khoan():
    """Kho tài khoản trên Postgres Docker, schema tạm xóa sau test. Postgres không chạy thì FAIL (quy ước test_backends.py)."""
    s = auth_store.Store(PG_URL, schema=f'app_auth_test_{uuid.uuid4().hex[:8]}')
    s.init()
    st.cache_data.clear()                    # roles._account cache theo (url, username), không theo schema
    yield s
    st.cache_data.clear()
    with psycopg.connect(PG_URL, autocommit=True) as c:
        c.execute(psycopg.sql.SQL('drop schema {} cascade').format(psycopg.sql.Identifier(s.schema)))
