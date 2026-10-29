"""Phân quyền theo role (docs/phan_quyen.md §3.1, §5, §7): hàm thuần, fail closed, và menu thật của app theo từng role."""
import logging
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import conftest
from ui import auth_store, roles

APP = Path(__file__).resolve().parents[1] / 'app.py'
VIEWS = Path(__file__).resolve().parents[1] / 'views'
MK = 'mat-khau-dai-1'


# --- Hàm thuần ---

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
    assert roles.db_url() is None and conftest.AUTH_CONFIGURED() is False
    monkeypatch.setattr(roles, 'auth_configured', conftest.AUTH_CONFIGURED)
    assert roles.store() is None and roles.current_role() == 'admin'           # env của conftest, vì không có DB tài khoản


def test_chuoi_ket_noi_tu_env_hoac_secrets(monkeypatch):
    monkeypatch.setattr(roles.st, 'secrets', {'app_db': {'url': ' postgresql://tu-secrets '}})
    assert roles.db_url() == 'postgresql://tu-secrets'
    monkeypatch.setenv('RETAIL_APP_DB_URL', 'postgresql://tu-env')
    assert roles.db_url() == 'postgresql://tu-env'
    monkeypatch.setattr(roles.st, 'secrets', {'auth': {}, 'roles': {'admin': ['a@b.c']}})    # cấu hình Google cũ: không còn tác dụng
    monkeypatch.delenv('RETAIL_APP_DB_URL')
    assert roles.db_url() is None


@pytest.fixture
def co_auth(monkeypatch, kho_tai_khoan):
    """Bật đăng nhập với kho tài khoản tạm: admin1 (admin), de1 (data engineer, đã đổi mật khẩu), ql1 (quản lý, còn mật khẩu
    tạm). RETAIL_APP_ROLE=admin của conftest vẫn còn để kiểm env không nâng quyền."""
    s = kho_tai_khoan
    s.create('admin1', 'admin', MK, None, must_change=False)
    s.create('de1', 'ky_su', MK, 'admin1', must_change=False)
    s.create('ql1', 'quan_ly', MK, 'admin1')
    monkeypatch.setattr(roles, 'db_url', lambda: 'postgresql://kho-test')
    monkeypatch.setattr(roles, 'store', lambda: s)
    monkeypatch.setattr(roles, 'auth_configured', conftest.AUTH_CONFIGURED)
    return s


@pytest.mark.parametrize('phien, role', [
    ({}, 'khach'),                                # chưa đăng nhập: env admin không có tác dụng
    ({'tai_khoan': 'admin1'}, 'admin'),
    ({'tai_khoan': 'de1'}, 'ky_su'),
    ({'tai_khoan': 'ql1'}, 'khach'),              # còn mật khẩu tạm
    ({'tai_khoan': 'khong_co'}, 'khach'),
])
def test_co_auth_role_theo_tai_khoan(monkeypatch, co_auth, phien, role):
    monkeypatch.setattr(roles.st, 'session_state', dict(phien))
    assert roles.current_role() == role


def test_tai_khoan_bi_khoa_hoac_doi_role_co_hieu_luc(monkeypatch, co_auth):
    phien = {'tai_khoan': 'de1', roles.PREVIEW_KEY: 'admin'}
    monkeypatch.setattr(roles.st, 'session_state', phien)
    assert roles.current_role() == 'ky_su'                                     # Xem như role chỉ có tác dụng với admin thật
    co_auth.set_role('de1', 'phan_tich', 'admin1')
    roles._account.clear()                                                      # trang Phân quyền xóa cache sau mỗi thao tác
    assert roles.current_role() == 'phan_tich'
    co_auth.set_disabled('de1', True, 'admin1')
    roles._account.clear()
    assert roles.current_role() == 'khach' and 'tai_khoan' not in phien        # bỏ phiên


def test_db_loi_la_khach_nhung_giu_phien(monkeypatch, co_auth):
    phien = {'tai_khoan': 'admin1'}
    monkeypatch.setattr(roles.st, 'session_state', phien)
    monkeypatch.setattr(roles, 'store', lambda: None)
    roles._account.clear()
    assert roles.current_role() == 'khach' and phien == {'tai_khoan': 'admin1'}


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


def _app(monkeypatch) -> AppTest:
    monkeypatch.setenv('RETAIL_BACKEND', 'duckdb')
    return AppTest.from_file(str(APP), default_timeout=60)


def _dang_nhap(at, ten, mk):
    o_ten, o_mk = at.sidebar.text_input
    o_ten.input(ten)
    o_mk.input(mk)
    next(b for b in at.sidebar.button if b.label == 'Đăng nhập').click().run()


def test_ban_deploy_chua_dang_nhap_la_khach(monkeypatch, co_auth):
    at = _app(monkeypatch)
    at.session_state[roles.PREVIEW_KEY] = 'admin'                               # còn sót từ phiên admin trước
    at.run()                                                                    # env RETAIL_APP_ROLE=admin từ conftest
    assert not at.exception, at.exception
    assert _pages(at) == set(roles.PAGES_BY_ROLE['khach'])
    assert not at.sidebar.radio and not at.sidebar.selectbox
    assert [t.label for t in at.sidebar.text_input] == ['Tên đăng nhập', 'Mật khẩu']    # form trong expander "Đăng nhập"


def test_dang_nhap_sai_roi_dung(monkeypatch, co_auth):
    at = _app(monkeypatch).run()
    _dang_nhap(at, 'admin1', 'sai-mat-khau-1')
    assert not at.exception and [e.value for e in at.sidebar.error] == [auth_store.SAI]
    assert _pages(at) == set(roles.PAGES_BY_ROLE['khach'])
    _dang_nhap(at, 'khong_co', MK)
    assert [e.value for e in at.sidebar.error] == [auth_store.SAI]              # cùng một câu: không dò được tài khoản
    _dang_nhap(at, 'Admin1', MK)
    assert not at.exception, at.exception
    assert _pages(at) == set(roles.PAGES_BY_ROLE['admin']) and at.session_state['tai_khoan'] == 'admin1'
    assert at.sidebar.selectbox[0].label == 'Xem như role'
    next(b for b in at.sidebar.button if b.label == 'Đăng xuất').click().run()
    assert _pages(at) == set(roles.PAGES_BY_ROLE['khach'])


def test_mat_khau_tam_phai_doi_moi_co_quyen(monkeypatch, co_auth):
    at = _app(monkeypatch).run()
    _dang_nhap(at, 'ql1', MK)
    assert _pages(at) == set(roles.PAGES_BY_ROLE['khach'])                      # còn mật khẩu tạm
    assert any('mật khẩu tạm' in w.value for w in at.sidebar.warning)
    cu, moi, lai = at.sidebar.text_input
    cu.input(MK)
    moi.input('mat-khau-moi-22')
    lai.input('mat-khau-moi-22')
    next(b for b in at.sidebar.button if b.label == 'Đổi mật khẩu').click().run()
    assert not at.exception, at.exception
    assert _pages(at) == set(roles.PAGES_BY_ROLE['quan_ly'])
    assert [s.value for s in at.sidebar.success] == ['Đã đổi mật khẩu.']


def test_admin_tao_tai_khoan_tren_trang_phan_quyen(monkeypatch, co_auth):
    at = _app(monkeypatch).run()
    _dang_nhap(at, 'admin1', MK)
    at.switch_page('views/phan_quyen.py').run()
    assert not at.exception, at.exception
    ten = next(t for t in at.main.text_input if t.label == 'Tên đăng nhập')
    ten.input('de2')
    next(s for s in at.main.selectbox if s.label == 'Role').select('ky_su')
    next(b for b in at.main.button if b.label == 'Tạo').click().run()
    assert not at.exception, at.exception
    (mk,) = at.main.code
    u, err = co_auth.login('de2', mk.value)
    assert err is None and u['role'] == 'ky_su' and u['must_change'] is True and u['created_by'] == 'admin1'
    assert mk.value not in str(co_auth.recent_log(100))


def test_admin_khoa_tai_khoan_dang_dung(monkeypatch, co_auth):
    at = _app(monkeypatch).run()
    _dang_nhap(at, 'de1', MK)
    assert _pages(at) == set(roles.PAGES_BY_ROLE['ky_su'])
    assert co_auth.set_disabled('de1', True, 'admin1') is None
    roles._account.clear()
    at.run()
    assert _pages(at) == set(roles.PAGES_BY_ROLE['khach']) and 'tai_khoan' not in at.session_state


def test_db_khong_ket_noi_duoc_van_xem_nhu_khach(monkeypatch):
    monkeypatch.setenv('RETAIL_APP_DB_URL', 'postgresql://khong-co:1/x?connect_timeout=1')
    monkeypatch.setattr(roles, 'auth_configured', conftest.AUTH_CONFIGURED)
    monkeypatch.setattr(roles, '_db_down_until', 0.0)                          # monkeypatch trả lại giá trị cũ sau test
    at = _app(monkeypatch).run()
    assert not at.exception, at.exception
    assert _pages(at) == set(roles.PAGES_BY_ROLE['khach'])
    assert any('tạm không dùng được' in w.value for w in at.sidebar.warning)
    assert roles._db_down_until > 0                                              # lượt sau không thử kết nối lại ngay


# --- Admin "Xem như role" ---

def test_admin_xem_nhu_tung_role(monkeypatch):
    monkeypatch.setenv('RETAIL_BACKEND', 'duckdb')
    at = AppTest.from_file(str(APP), default_timeout=60).run()                 # role admin từ conftest
    (chon,) = at.sidebar.selectbox
    assert chon.label == 'Xem như role' and chon.value == 'admin'
    for role in roles.ROLES:
        chon.set_value(role).run()
        assert not at.exception, at.exception
        assert _pages(at) == set(roles.PAGES_BY_ROLE[role]), role
        assert (len(at.sidebar.radio) == 1) == (role in roles.BACKEND_ROLES), role
        (chon,) = at.sidebar.selectbox                                          # ô chọn vẫn còn để quay về admin
        assert ('Đang xem như' in at.sidebar.caption[-1].value) == (role != 'admin'), role


@pytest.mark.parametrize('role', [r for r in roles.ROLES if r != 'admin'])
def test_khong_phai_admin_khong_nang_quyen_bang_xem_nhu(monkeypatch, role):
    monkeypatch.setenv('RETAIL_BACKEND', 'duckdb')
    monkeypatch.setenv('RETAIL_APP_ROLE', role)
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.session_state[roles.PREVIEW_KEY] = 'admin'
    at.run()
    assert not at.exception, at.exception
    assert _pages(at) == set(roles.PAGES_BY_ROLE[role])
    assert not at.sidebar.selectbox


def test_nhat_ky_ghi_ca_role_that_va_role_dang_xem(monkeypatch):
    rows = []
    h = logging.Handler()
    h.emit = lambda rec: rows.append(rec.getMessage())
    monkeypatch.setattr(roles._audit, 'handlers', [h])
    monkeypatch.setattr(roles, 'current_role', lambda: 'quan_ly')
    roles.audit('trang_thu', {'lien_he'})
    assert '"role": "admin"' in rows[0] and '"xem_nhu": "quan_ly"' in rows[0]
