# pytest đặt thư mục chứa file này vào sys.path → test import được `dwh`, `ui` giống lúc chạy app.
import pytest

from ui import roles

AUTH_CONFIGURED = roles.auth_configured      # bản thật, cho test cần kiểm nhánh có [auth] (test_roles.py)
DEFAULT_PAGE = dict(roles.DEFAULT_PAGE)      # bản thật, test_roles.py kiểm trang mở mặc định của từng role


@pytest.fixture(autouse=True)
def _role_admin(monkeypatch):
    """Test cũ kiểm mọi trang và radio backend nên chạy với role admin (docs/phan_quyen.md §5), mở đầu ở Tổng quan như
    trước khi có role. Bỏ qua [auth] trong secrets.toml của máy (nếu có), để kết quả test không phụ thuộc cấu hình local."""
    monkeypatch.setenv('RETAIL_APP_ROLE', 'admin')
    monkeypatch.setattr(roles, 'auth_configured', lambda: False)
    monkeypatch.setitem(roles.DEFAULT_PAGE, 'admin', 'tong_quan')
