"""scripts/ops/tao_admin.py: tạo admin đầu tiên / đặt lại mật khẩu admin (docs/phan_quyen.md §5)."""
import pytest

from scripts.ops import tao_admin as ta

MK = 'mat-khau-dai-1'


def test_tao_admin_dau_tien_roi_chan_tao_them(kho_tai_khoan):
    assert ta.run(kho_tai_khoan, 'Uyen', MK, dat_lai=False) is None
    u, err = kho_tai_khoan.login('uyen', MK)
    assert err is None and u['role'] == 'admin' and u['must_change'] is False
    assert ta.run(kho_tai_khoan, 'admin2', MK, dat_lai=False).startswith('Đã có admin')


def test_dat_lai_chi_cho_admin(kho_tai_khoan):
    ta.run(kho_tai_khoan, 'uyen', MK, dat_lai=False)
    kho_tai_khoan.create('de1', 'ky_su', MK, 'uyen')
    assert ta.run(kho_tai_khoan, 'de1', 'mat-khau-moi-22', dat_lai=True).startswith('Không có admin')
    for _ in range(5):
        kho_tai_khoan.login('uyen', 'sai-mat-khau-1')                           # đang bị khóa vì nhập sai
    assert ta.run(kho_tai_khoan, 'uyen', 'mat-khau-moi-22', dat_lai=True) is None
    assert kho_tai_khoan.login('uyen', 'mat-khau-moi-22')[1] is None


@pytest.mark.parametrize('argv', [['--username', 'uyen'], ['--username', 'có dấu', '--local']])
def test_tham_so_sai(monkeypatch, argv):
    monkeypatch.delenv('RETAIL_APP_DB_URL', raising=False)
    with pytest.raises(SystemExit):
        ta.main(argv)
