"""Phân quyền theo role (docs/phan_quyen.md §3.1, §5, §7): hàm thuần, fail closed, và menu thật của app theo từng role."""
import logging
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import conftest
from ui import roles

APP = Path(__file__).resolve().parents[1] / 'app.py'
VIEWS = Path(__file__).resolve().parents[1] / 'views'
BANG = {'admin': ['Admin@Shop.vn'], 'quan_ly': ['ql@shop.vn', 'hai@shop.vn'], 'phan_tich': ['hai@shop.vn'],
        'ky_su': [' de@shop.vn '], 'giam_doc': ['gd@shop.vn']}
AUTH = {'redirect_uri': 'http://localhost:8501/oauth2callback', 'cookie_secret': 'x' * 32, 'client_id': 'id',
        'client_secret': 'secret', 'server_metadata_url': 'https://accounts.google.com/.well-known/openid-configuration'}


# --- Hàm thuần ---

@pytest.mark.parametrize('email, role', [
    ('admin@shop.vn', 'admin'),                  # không phân biệt hoa thường
    ('de@shop.vn', 'ky_su'),                     # bỏ khoảng trắng thừa trong secrets
    ('hai@shop.vn', 'quan_ly'),                  # có ở hai role → lấy role thấp hơn
    ('gd@shop.vn', 'khach'),                     # tên role lạ trong secrets bị bỏ qua
    ('la@shop.vn', 'khach'), (None, 'khach'), ('', 'khach'),
])
def test_role_for(email, role):
    assert roles.role_for(email, BANG) == role


def test_ma_tran_trang(monkeypatch):
    monkeypatch.setattr(roles, 'DEFAULT_PAGE', conftest.DEFAULT_PAGE)
    assert roles.DEFAULT_PAGE == {'khach': 'tong_quan', 'quan_ly': 'tong_quan', 'phan_tich': 'ps1_do_dung',
                                  'ky_su': 'suc_khoe_du_lieu', 'admin': 'suc_khoe_du_lieu'}
    chi = lambda key: [r for r in roles.ROLES if roles.allowed(r, key)]
    assert chi('ai_explain') == ['quan_ly', 'phan_tich', 'ky_su', 'admin']      # khách không có chat
    assert chi('suc_khoe_du_lieu') == ['phan_tich', 'ky_su', 'admin']
    assert chi('phan_quyen') == ['admin']
    for key in ['tong_quan', 'ps1_do_dung', 'ps2_xu_huong', 'ps3_nhip_lich', 'ps4_don_mon_gia', 'ps5_nhom', 'du_bao']:
        assert chi(key) == list(roles.ROLES), key
    assert roles.BACKEND_ROLES == ('ky_su', 'admin')
    assert not roles.allowed('vai_tro_la', 'tong_quan')
    for role in roles.ROLES:
        assert roles.allowed(role, roles.DEFAULT_PAGE[role]), role


def test_moi_trang_deu_khai_bao():
    """Trang mới trong views/ phải có trong roles.PAGES, và mọi key của ma trận phải là trang có thật."""
    assert {Path(p).name for p, _ in roles.PAGES.values()} == {f.name for f in VIEWS.glob('*.py')}
    assert {k for keys in roles.PAGES_BY_ROLE.values() for k in keys} <= set(roles.PAGES)
    assert set(roles.PAGES_BY_ROLE) == set(roles.ROLES) == set(roles.DEFAULT_PAGE)


def test_muc_nhay_cam():
    view = {(r, lv): roles.column_view(r, lv) for r in roles.ROLES for lv in roles.LEVELS + ('khong_ro',)}
    assert all(view[r, 'cong_khai'] == 'du' for r in roles.ROLES)
    assert all(view[r, 'cam'] == 'an' and view[r, 'khong_ro'] == 'an' for r in roles.ROLES)
    assert [view[r, 'noi_bo'] for r in roles.ROLES] == ['an', 'du', 'du', 'du', 'du']
    assert [view[r, 'lien_he'] for r in roles.ROLES] == ['an', 'che', 'du', 'du', 'du']


@pytest.mark.parametrize('raw, masked', [('0901234567', '*******567'), ('+84 90 123 4567', '********567'),
                                         ('123', '***'), (None, None), (float('nan'), None)])
def test_che_so_lien_lac(raw, masked):
    assert roles.mask_contact(raw) == masked


def test_apply_levels():
    df = pd.DataFrame({'ten': ['An'], 'sdt': ['0901234567'], 'hoc_van': ['DH'], 'cot_moi': [1], 'doanh_thu': [5.0]})
    levels = {'ten': 'cong_khai', 'sdt': 'lien_he', 'hoc_van': 'cam', 'doanh_thu': 'cong_khai'}
    out, shown = roles.apply_levels(df, levels, 'khach')
    assert list(out.columns) == ['ten', 'doanh_thu'] and shown == set()        # cột chưa gán mức bị bỏ
    out, shown = roles.apply_levels(df, levels, 'quan_ly')
    assert out['sdt'].tolist() == ['*******567'] and shown == {'lien_he'}
    out, shown = roles.apply_levels(df, levels, 'admin')
    assert out['sdt'].tolist() == ['0901234567'] and 'hoc_van' not in out and 'cot_moi' not in out


def test_nhat_ky_khong_ghi_gia_tri(monkeypatch):
    rows = []
    h = logging.Handler()
    h.emit = lambda rec: rows.append(rec.getMessage())
    monkeypatch.setattr(roles._audit, 'handlers', [h])
    monkeypatch.setenv('RETAIL_APP_ROLE', 'quan_ly')
    df = pd.DataFrame({'ten': ['An'], 'sdt': ['0901234567']})
    out = roles.view_frame(df, {'ten': 'cong_khai', 'sdt': 'lien_he'}, 'trang_thu')
    assert out['sdt'].tolist() == ['*******567']
    assert len(rows) == 1 and '"page": "trang_thu"' in rows[0] and '"levels": ["lien_he"]' in rows[0]
    assert '0901234567' not in rows[0] and '567' not in rows[0]
    roles.view_frame(df[['ten']], {'ten': 'cong_khai'}, 'trang_thu')          # chỉ cột công khai → không ghi
    assert len(rows) == 1


# --- Xác định role: fail closed ---

@pytest.mark.parametrize('env, role', [('admin', 'admin'), ('phan_tich', 'phan_tich'), ('Admin', 'khach'),
                                       ('root', 'khach'), (None, 'khach')])
def test_khong_auth_doc_bien_moi_truong(monkeypatch, env, role):
    if env is None:
        monkeypatch.delenv('RETAIL_APP_ROLE')
    else:
        monkeypatch.setenv('RETAIL_APP_ROLE', env)
    assert roles.current_role() == role


class _SecretsHong:
    def __contains__(self, key):
        raise FileNotFoundError('không có secrets.toml')

    def __getitem__(self, key):
        raise FileNotFoundError('không có secrets.toml')


def test_khong_co_file_secrets_thi_khong_auth(monkeypatch):
    monkeypatch.setattr(roles.st, 'secrets', _SecretsHong())
    assert conftest.AUTH_CONFIGURED() is False
    monkeypatch.setattr(roles, 'auth_configured', conftest.AUTH_CONFIGURED)
    assert roles.role_table() == {} and roles.current_role() == 'admin'       # env của conftest, vì không có [auth]


@pytest.mark.parametrize('user, role', [
    ({}, 'khach'),                                                              # chưa đăng nhập
    ({'is_logged_in': True, 'email': 'ADMIN@shop.vn', 'email_verified': True}, 'admin'),
    ({'is_logged_in': True, 'email': 'admin@shop.vn', 'email_verified': False}, 'khach'),   # email chưa xác minh
    ({'is_logged_in': True, 'email': 'la@gmail.com', 'email_verified': True}, 'khach'),
    ({'is_logged_in': True, 'email': 'ql@shop.vn'}, 'quan_ly'),
])
def test_co_auth_env_khong_nang_quyen(monkeypatch, user, role):
    monkeypatch.setattr(roles, 'auth_configured', lambda: True)
    monkeypatch.setattr(roles, 'role_table', lambda: BANG)
    monkeypatch.setattr(roles.st, 'user', user)
    monkeypatch.setenv('RETAIL_APP_ROLE', 'admin')                             # env admin không có tác dụng
    assert roles.current_role() == role


# --- App thật theo từng role ---

def _pages(at) -> set:
    """Trang có trong navigation: switch_page sang trang không đăng ký thì AppTest raise."""
    co = set()
    for key, (path, _) in roles.PAGES.items():
        try:
            at.switch_page(path)
            co.add(key)
        except ValueError:
            pass
    return co


@pytest.mark.parametrize('role', roles.ROLES)
def test_menu_theo_role(monkeypatch, role):
    monkeypatch.setattr(roles, 'DEFAULT_PAGE', conftest.DEFAULT_PAGE)         # trang mặc định thật, không phải bản của conftest
    monkeypatch.setenv('RETAIL_BACKEND', 'duckdb')
    monkeypatch.setenv('RETAIL_APP_ROLE', role)
    st.cache_data.clear()
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception, at.exception
    assert _pages(at) == set(roles.PAGES_BY_ROLE[role])
    assert at.title[0].value.startswith(roles.PAGES[roles.DEFAULT_PAGE[role]][1].split(':')[0])
    assert (len(at.sidebar.radio) == 1) == (role in roles.BACKEND_ROLES)
    assert f'**{roles.LABEL[role]}**' in at.sidebar.caption[-1].value
    at.switch_page('views/ps1_do_dung.py').run()                               # khung AI diễn giải có cho mọi role
    assert not at.exception, at.exception
    links = [p.proto.label for p in at.get('page_link')]
    assert ('Muốn hỏi câu khác? Mở trang Hỏi dữ liệu (AI)' in links) == (role != 'khach')
    if role == 'admin':
        at.switch_page('views/phan_quyen.py').run()
        assert not at.exception and at.title[0].value == 'Phân quyền'


def test_role_khong_ky_thuat_doc_backend_mac_dinh(monkeypatch):
    monkeypatch.setenv('RETAIL_BACKEND', 'duckdb')
    monkeypatch.setenv('RETAIL_APP_ROLE', 'quan_ly')
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.session_state['backend'] = 'postgres'                                    # còn sót từ phiên trước
    at.run()
    assert not at.exception and at.session_state['backend'] == 'duckdb'


def test_ban_deploy_co_auth_chua_dang_nhap_la_khach(monkeypatch):
    monkeypatch.setenv('RETAIL_BACKEND', 'duckdb')
    monkeypatch.setattr(roles, 'auth_configured', conftest.AUTH_CONFIGURED)   # đọc [auth] thật từ at.secrets
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.secrets['auth'] = AUTH
    at.secrets['roles'] = BANG
    at.run()                                                                    # env RETAIL_APP_ROLE=admin từ conftest
    assert not at.exception, at.exception
    assert _pages(at) == set(roles.PAGES_BY_ROLE['khach'])
    assert not at.sidebar.radio
    assert [b.label for b in at.sidebar.button] == ['Đọc lại dữ liệu', 'Đăng nhập bằng Google']
