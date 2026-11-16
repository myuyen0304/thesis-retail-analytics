"""Gỡ role DA/BI: DB tạm trên Postgres local, không kết nối Neon hay Databricks."""
from pathlib import Path

import psycopg
import pytest
from streamlit.testing.v1 import AppTest

from scripts.ops import doi_role_phan_tich as migration
from scripts.ops import phan_quyen_nhom as grants
from ui import auth_store, roles, nhap_store, nhap_dot, kho_dot

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / 'apps/retail_app/app.py'
OLD = migration.LEGACY_ROLE
MK = 'mat-khau-dai-1'


@pytest.fixture
def legacy_store(kho_tai_khoan):
    store = kho_tai_khoan
    for name, role in [('admin1', 'admin'), ('worker1', 'ky_su'), ('legacy1', 'quan_ly'), ('legacy2', 'quan_ly')]:
        assert store.create(name, role, MK, None, must_change=False) is None
    store._run('update {s}.users set role = %s where username in (%s, %s)', (OLD, 'legacy1', 'legacy2'))
    store.set_disabled('legacy2', True, 'admin1')
    return store


def test_removed_role_absent_from_code():
    assert roles.ROLES == ('khach', 'quan_ly', 'ky_su', 'admin')
    assert auth_store.ROLES == roles.ROLES[1:]
    exempt = {Path(migration.__file__).resolve(), Path(__file__).resolve()}
    hits = []
    for directory in ('apps', 'scripts'):
        for path in (ROOT / directory).rglob('*.py'):
            if path.resolve() not in exempt and OLD in path.read_text(encoding='utf-8'):
                hits.append(str(path.relative_to(ROOT)))
    assert hits == []
    assert not hasattr(grants, 'PHAN_TICH')


def test_page_matrix_unchanged_for_remaining_roles():
    public = ('tong_quan', 'ps1_do_dung', 'ps2_xu_huong', 'ps3_nhip_lich', 'ps4_don_mon_gia', 'ps5_nhom', 'du_bao')
    assert dict(roles.PAGES_BY_ROLE) == {
        'khach': public,
        'quan_ly': public + ('ai_explain', 'gui_du_lieu'),
        'ky_su': public + ('suc_khoe_du_lieu', 'ai_explain', 'gui_du_lieu', 'duyet_du_lieu'),
        'admin': public + ('suc_khoe_du_lieu', 'ai_explain', 'phan_quyen', 'gui_du_lieu', 'duyet_du_lieu'),
    }
    assert not roles.allowed('quan_ly', 'suc_khoe_du_lieu')


def test_legacy_role_is_guest_from_db_and_env(monkeypatch, legacy_store):
    monkeypatch.setattr(roles, 'auth_configured', lambda: True)
    monkeypatch.setattr(roles, 'db_url', lambda: 'postgresql://local-test')
    monkeypatch.setattr(roles, 'store', lambda: legacy_store)
    state = {roles.SESSION_KEY: 'legacy1', roles.PREVIEW_KEY: 'admin'}
    monkeypatch.setattr(roles.st, 'session_state', state)
    assert roles.current_role() == 'khach'
    assert roles.SESSION_KEY not in state and roles.PREVIEW_KEY not in state
    monkeypatch.setattr(roles, 'auth_configured', lambda: False)
    monkeypatch.setenv('RETAIL_APP_ROLE', OLD)
    assert roles.current_role() == 'khach'


def test_admin_reassigns_legacy_account_without_default(monkeypatch, legacy_store):
    monkeypatch.setattr(roles, 'auth_configured', lambda: True)
    monkeypatch.setattr(roles, 'db_url', lambda: 'postgresql://local-test')
    monkeypatch.setattr(roles, 'store', lambda: legacy_store)
    monkeypatch.setitem(roles.DEFAULT_PAGE, 'admin', 'phan_quyen')
    monkeypatch.setenv('RETAIL_BACKEND', 'duckdb')
    at = AppTest.from_file(str(APP), default_timeout=30)
    at.session_state[roles.SESSION_KEY] = 'admin1'
    at.run()
    assert not at.exception and not at.error
    table = at.main.dataframe[0].value.set_index('Tên đăng nhập')
    assert table.loc['legacy1', 'Role'] == 'Role cũ: phan_tich (cần đổi)'
    account = lambda: next(s for s in at.main.selectbox if s.label == 'Tài khoản')
    new_role = lambda: next(s for s in at.main.selectbox if s.label == 'Role mới')
    # Chuyển từ tài khoản có role hợp lệ sang tài khoản cũ cũng phải bỏ lựa chọn trước.
    account().select('worker1').run()
    assert not at.exception and not at.error
    new_role().select('admin').run()
    account().select('legacy1').run()
    assert not at.exception and not at.error
    assert new_role().value is None
    assert next(b for b in at.main.button if b.label == 'Đổi role').disabled
    assert legacy_store.get('legacy1')['role'] == OLD
    new_role().select('quan_ly').run()
    assert not at.exception and not at.error
    next(b for b in at.main.button if b.label == 'Đổi role').click().run()
    assert not at.exception and not at.error
    assert legacy_store.get('legacy1')['role'] == 'quan_ly'
    assert legacy_store.get('legacy2')['role'] == OLD
    assert legacy_store.recent_log()[0]['event'] == 'doi_role'
    assert legacy_store.recent_log()[0]['username'] == 'admin1'


def test_auth_store_rejects_legacy_role_without_writes(legacy_store):
    before = legacy_store.list_users(), legacy_store.recent_log()
    assert legacy_store.create('new1', OLD, MK, 'admin1').startswith('Role không hợp lệ')
    assert legacy_store.set_role('worker1', OLD, 'admin1').startswith('Role không hợp lệ')
    assert (legacy_store.list_users(), legacy_store.recent_log()) == before


def test_both_request_stores_reject_legacy_visibility(tmp_path, monkeypatch):
    local = nhap_store.RequestStore(tmp_path)
    monkeypatch.setattr(local, 'read', lambda *a: pytest.fail('Không được đọc yêu cầu với role cũ'))
    cloud = nhap_dot.DotStore(kho_dot.KhoDia(tmp_path / 'volume'))
    monkeypatch.setattr(cloud.kho, 'liet_ke', lambda *a: pytest.fail('Không được liệt kê với role cũ'))
    assert local.visible('legacy1', OLD) == []
    assert cloud.visible('legacy1', OLD) == []


def test_default_only_counts_without_names_or_url(legacy_store, monkeypatch, capsys):
    before = legacy_store.list_users(), legacy_store.recent_log()
    monkeypatch.setenv('RETAIL_APP_DB_URL', 'postgresql://fake-secret-connection')
    monkeypatch.setattr(migration.auth_store, 'Store', lambda url: legacy_store)
    assert migration.main([]) == 0
    captured = capsys.readouterr()
    assert captured.out == 'Số tài khoản còn role cũ: 2\n' and not captured.err
    assert (legacy_store.list_users(), legacy_store.recent_log()) == before


@pytest.mark.parametrize('target', auth_store.ROLES)
def test_migrate_only_old_rows_and_audit_atomically(legacy_store, target):
    before = {u['username']: u for u in legacy_store.list_users()}
    count = len(legacy_store.recent_log(100))
    assert migration.run(legacy_store, target) == 2
    for user in legacy_store.list_users():
        old = before[user['username']]
        assert user == dict(old, role=target) if old['role'] == OLD else user == old
    added = legacy_store.recent_log(100)[:2]
    assert len(legacy_store.recent_log(100)) == count + 2
    assert {r['detail']['tai_khoan'] for r in added} == {'legacy1', 'legacy2'}
    assert all(r['username'] == 'script' and r['event'] == 'doi_role' and r['detail']['role'] == target for r in added)
    assert migration.run(legacy_store, target) == 0
    assert len(legacy_store.recent_log(100)) == count + 2


def test_update_rolls_back_if_audit_fails(legacy_store):
    legacy_store._run("alter table {s}.audit add constraint block_role_change check (event <> 'doi_role')")
    before = legacy_store.list_users(), legacy_store.recent_log()
    with pytest.raises(psycopg.errors.CheckViolation):
        migration.run(legacy_store, 'quan_ly')
    assert (legacy_store.list_users(), legacy_store.recent_log()) == before


def test_cli_update_uses_env_without_disclosing_users(legacy_store, monkeypatch, capsys):
    monkeypatch.setenv('RETAIL_APP_DB_URL', 'postgresql://fake-secret-connection')
    monkeypatch.setattr(migration.auth_store, 'Store', lambda url: legacy_store)
    assert migration.main(['--doi-sang', 'quan_ly']) == 0
    captured = capsys.readouterr()
    assert captured.out == 'Số tài khoản đã đổi role: 2\n' and not captured.err
    assert migration.run(legacy_store) == 0


@pytest.mark.parametrize('target', [OLD, 'khach', 'root', ''])
def test_invalid_target_never_connects(monkeypatch, target):
    monkeypatch.setattr(migration.psycopg, 'connect', lambda *a, **k: pytest.fail('Không được kết nối'))
    with pytest.raises(SystemExit) as exc:
        migration.main(['--doi-sang', target])
    assert exc.value.code == 2
    with pytest.raises(ValueError, match='Role không hợp lệ'):
        migration.run(auth_store.Store('postgresql://unused'), target)


def test_missing_env_and_connection_error_do_not_print_url(monkeypatch, capsys):
    monkeypatch.delenv('RETAIL_APP_DB_URL', raising=False)
    with pytest.raises(SystemExit) as exc:
        migration.main([])
    assert exc.value.code == 2
    capsys.readouterr()
    secret = 'postgresql://fake-secret-connection'
    monkeypatch.setenv('RETAIL_APP_DB_URL', secret)
    def fail(*args, **kwargs):
        raise psycopg.OperationalError(secret)
    monkeypatch.setattr(migration.psycopg, 'connect', fail)
    assert migration.main([]) == 1
    captured = capsys.readouterr()
    assert not captured.out and 'Không thực hiện được' in captured.err
    assert secret not in captured.err


def test_grants_cli_no_longer_accepts_old_group_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        grants.main(['--release', 'a' * 24, '--nhom-phan-tich', 'old-team'])
    assert exc.value.code == 2
    assert not capsys.readouterr().out
