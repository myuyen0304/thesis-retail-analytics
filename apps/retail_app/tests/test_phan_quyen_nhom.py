"""scripts/ops/phan_quyen_nhom.py: câu GRANT cho group người dùng theo bản (docs/phan_quyen.md §3.2)."""
import pytest

from scripts.ops import phan_quyen_nhom as pq

RID, OLD = '03ad08c0ddbf4ce1848a1447', 'ccde5a5e21c54e9e9054066f'


def test_cau_grant_dung_ma_tran():
    sql = pq.statements(RID, 'retail-ky-su')
    ks = [s for s in sql if s.endswith('to `retail-ky-su`;')]
    assert {s.split('.r_')[1].split(' ')[0] for s in ks if '.r_' in s} == {
        f'{RID}_{x}' for x in ('raw', 'staging', 'intermediate', 'marts', 'reporting')}
    assert all(s.endswith('to `retail-ky-su`;') for s in sql if s.startswith('grant '))
    assert 'grant select on table retail_lab.retail_control.run_history to `retail-ky-su`;' in ks
    assert not any(s.lower().startswith(('revoke', 'drop', 'alter', 'create')) for s in sql)
    assert not any('grant all' in s.lower() or 'modify' in s.lower() for s in sql)


def test_thu_quyen_ban_cu():
    sql = pq.statements(RID, 'b', OLD)
    rv = [s for s in sql if s.startswith('revoke')]
    assert all(s.endswith('from `b`;') for s in rv)
    assert len(rv) == 5 and all(f'r_{OLD}_' in s for s in rv)
    assert not any(f'r_{OLD}_' in s for s in sql if s.startswith('grant'))


@pytest.mark.parametrize('argv', [
    ['--release', 'abc'],                                                       # mã bản sai dạng
    ['--release', RID, '--nhom-ky-su', 'account users'],                    # group toàn workspace
    ['--release', RID, '--nhom-ky-su', '_workspace_users_123'],
    ['--release', RID, '--bo-ban-cu', RID],
    ['--release', f'{RID}; drop table x'],
])
def test_tu_choi_dau_vao_nguy_hiem(argv):
    with pytest.raises(SystemExit):
        pq.main(argv)


def test_in_ra_khong_chay(capsys):
    pq.main(['--release', RID])
    out = capsys.readouterr().out
    assert out.count('grant ') == 9 and 'revoke' not in out
