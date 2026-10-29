"""Tài khoản username/mật khẩu (docs/phan_quyen.md §5), chạy trên Postgres Docker trong một schema tạm (fixture
`kho_tai_khoan` ở conftest.py), xóa sau khi chạy. Postgres không chạy thì test FAIL, không skip (quy ước test_backends.py)."""
import datetime as dt
import json

import pytest

from ui import auth_store as A

MK = 'mat-khau-dai-1'


@pytest.fixture
def store(kho_tai_khoan):
    kho_tai_khoan.init()                                                        # chạy lại không lỗi
    return kho_tai_khoan


def _hashes(store) -> list[str]:
    return [r['pw_hash'] for r in store._run('select pw_hash from {s}.users', fetch='all')]


def _log_text(store) -> str:
    return json.dumps([{**r, 'ts': str(r['ts'])} for r in store.recent_log(500)], ensure_ascii=False)


# --- Hàm thuần ---

def test_bam_mat_khau():
    h1, h2 = A.hash_password(MK), A.hash_password(MK)
    assert h1 != h2 and h1.startswith('scrypt$')                                 # salt riêng
    assert A.verify_password(MK, h1) and A.verify_password(MK, h2)
    assert not A.verify_password(MK + 'x', h1)
    assert not A.verify_password(MK, 'rac') and not A.verify_password(MK, 'bcrypt$1$2$3$aa$bb')


@pytest.mark.parametrize('username, ok', [('de1', True), ('Nguyen.An_2', True), ('ab', False), ('có dấu', False),
                                          ('a' * 33, False), ('', False)])
def test_ten_dang_nhap(username, ok):
    assert (A.check_username(username) is None) == ok


def test_quy_tac_mat_khau():
    assert A.check_password('ngan', 'de1')
    assert A.check_password('xxDE1xxxxxxx', 'de1')                             # chứa tên đăng nhập
    assert A.check_password(MK, 'de1') is None
    assert len(A.temp_password()) >= 12 and A.check_password(A.temp_password(), 'de1') is None


# --- Store ---

def test_tao_va_dang_nhap(store):
    assert store.create('DE1', 'ky_su', MK, 'admin1') is None
    assert store.create('de1', 'ky_su', MK, 'admin1') == 'Tên đăng nhập đã có.'
    assert store.create('de2', 'giam_doc', MK, 'admin1').startswith('Role không hợp lệ')
    assert store.create('de2', 'ky_su', 'ngan', 'admin1')
    u, err = store.login(' De1 ', MK)
    assert err is None and u['username'] == 'de1' and u['role'] == 'ky_su' and u['must_change'] is True
    assert 'pw_hash' not in u and u['last_login'] is not None
    assert 'pw_hash' not in store.get('de1') and all('pw_hash' not in r for r in store.list_users())


def test_username_la_va_sai_mat_khau_cung_mot_cau(store):
    store.create('de1', 'ky_su', MK, None)
    assert store.login('khong_co', MK) == (None, A.SAI)
    assert store.login('de1', 'sai-mat-khau-1') == (None, A.SAI)


def test_khoa_sau_5_lan_sai(store):
    store.create('de1', 'ky_su', MK, None)
    t0 = dt.datetime(2026, 10, 29, 8, tzinfo=dt.timezone.utc)
    for _ in range(A.MAX_FAIL):
        assert store.login('de1', 'sai-mat-khau-1', now=t0) == (None, A.SAI)
    u, err = store.login('de1', MK, now=t0 + dt.timedelta(minutes=1))           # đúng mật khẩu vẫn bị chặn khi đang khóa
    assert u is None and 'tạm khóa' in err
    u, err = store.login('de1', MK, now=t0 + A.LOCK + dt.timedelta(seconds=1))
    assert err is None and u['username'] == 'de1'
    events = [r['event'] for r in store.recent_log()]
    assert 'locked' in events and events[0] == 'login_ok'


def test_dang_nhap_dung_thi_dat_lai_dem_sai(store):
    store.create('de1', 'ky_su', MK, None)
    for _ in range(A.MAX_FAIL - 1):
        store.login('de1', 'sai-mat-khau-1')
    assert store.login('de1', MK)[1] is None
    for _ in range(A.MAX_FAIL - 1):
        store.login('de1', 'sai-mat-khau-1')
    assert store.login('de1', MK)[1] is None                                    # chưa tới 5 lần liên tiếp


def test_doi_mat_khau(store):
    store.create('de1', 'ky_su', MK, None)
    assert store.change_password('de1', 'sai-mat-khau-1', 'mat-khau-moi-22') == 'Mật khẩu hiện tại không đúng.'
    assert store.change_password('de1', MK, MK)
    assert store.change_password('de1', MK, 'ngan')
    assert store.change_password('de1', MK, 'mat-khau-moi-22') is None
    assert store.get('de1')['must_change'] is False
    assert store.login('de1', MK) == (None, A.SAI)
    assert store.login('de1', 'mat-khau-moi-22')[1] is None


def test_admin_khoa_doi_role_dat_lai(store):
    store.create('admin1', 'admin', MK, None, must_change=False)
    store.create('de1', 'ky_su', MK, 'admin1')
    assert store.set_disabled('de1', True, 'admin1') is None
    assert store.login('de1', MK) == (None, 'Tài khoản đã bị admin khóa. Liên hệ admin.')
    assert store.login('de1', 'sai-mat-khau-1') == (None, A.SAI)               # sai mật khẩu thì không lộ là bị khóa
    assert store.set_disabled('de1', False, 'admin1') is None
    assert store.set_role('de1', 'phan_tich', 'admin1') is None and store.get('de1')['role'] == 'phan_tich'
    store.change_password('de1', MK, 'mat-khau-moi-22')
    assert store.reset_password('de1', 'mat-khau-tam-333', 'admin1') is None
    u, _ = store.login('de1', 'mat-khau-tam-333')
    assert u['must_change'] is True
    assert store.reset_password('khong_co', 'mat-khau-tam-333', 'admin1') == 'Không có tài khoản này.'


def test_khong_mat_admin_cuoi_cung(store):
    store.create('admin1', 'admin', MK, None, must_change=False)
    store.create('admin2', 'admin', MK, None, must_change=False)
    assert store.set_disabled('admin1', True, 'admin1') == 'Không tự khóa hay tự đổi role của chính mình.'
    assert store.set_role('admin1', 'quan_ly', 'admin1') == 'Không tự khóa hay tự đổi role của chính mình.'
    assert store.set_role('admin1', 'quan_ly', 'admin2') is None                # còn admin2
    assert store.set_disabled('admin2', True, 'nguoi_khac') == 'Đây là admin cuối cùng còn hoạt động.'
    assert store.set_role('admin2', 'ky_su', 'nguoi_khac') == 'Đây là admin cuối cùng còn hoạt động.'
    assert store.count_admins() == 1


def test_nhat_ky_khong_co_mat_khau_hay_hash(store):
    store.create('admin1', 'admin', MK, None, must_change=False)
    store.create('de1', 'ky_su', 'mat-khau-tam-333', 'admin1')
    store.login('de1', 'mat-khau-sai-444')
    store.login('de1', 'mat-khau-tam-333')
    store.change_password('de1', 'mat-khau-tam-333', 'mat-khau-moi-555')
    store.reset_password('de1', 'mat-khau-tam-666', 'admin1')
    text = _log_text(store)
    for secret in (MK, 'mat-khau-tam-333', 'mat-khau-sai-444', 'mat-khau-moi-555', 'mat-khau-tam-666', *_hashes(store)):
        assert secret not in text
    assert {'tao_tk', 'login_fail', 'login_ok', 'doi_mk', 'dat_lai_mk'} <= {r['event'] for r in store.recent_log()}
