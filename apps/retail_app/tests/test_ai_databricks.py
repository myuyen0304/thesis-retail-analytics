"""Đường đọc chỉ-đọc của chat AI trên Databricks (dwh/guarded.py `_DatabricksSession`, `_dbx_violations`).

Phần lớn chạy không cần cloud: luật guard là hàm thuần trên các dòng quyền/owner, mỗi luật có ca bị chặn và ca đạt.
Phần cần cloud chỉ chạy khi RETAIL_TEST_DATABRICKS=1 (như tests/test_databricks.py):
- tài khoản đăng nhập của PM (profile retail-dev) phải bị guard TỪ CHỐI;
- service principal AI (RETAIL_AI_DBX_CLIENT_ID / _SECRET) đọc ra đúng số như DuckDB ở mọi tổ hợp tool đang mở.
"""
import datetime as dt
import os

import pytest

from ai_explain import tools
from dwh import guarded
from dwh.connection import databricks_config
from dwh.guarded import _dbx_violations
from tests.test_ai_tools import _PG_CALLS, _giong_nhau

ALLOWED = tools.ALLOWED_RELATIONS
CAT = 'retail_lab'
SP = '6f1c0d2e-0000-4000-8000-00000000a1a1'      # application id giả của SP AI
WS_USERS = '_workspace_users_workspace_7474650611714585'
PU = 'account users'

cloud = pytest.mark.skipif(os.environ.get('RETAIL_TEST_DATABRICKS') != '1',
                           reason='đặt RETAIL_TEST_DATABRICKS=1 để chạy test cần Databricks')


def _g(lvl, cat, sch, name, grantee, priv, member=False):
    return (lvl, cat, sch, name, grantee, priv, member)


def _t(cat, sch, name, owner='pm@example.com', member=False):
    return ('table', cat, sch, name, owner, member)


# Quyền đúng như thiết kế: SELECT 14 bảng + USE trên đường đi, cộng 7 ngoại lệ nền tảng dò được ngày 2026-10-06.
BASE_GRANTS = (
    [_g('catalog', CAT, None, None, SP, 'USE_CATALOG'), _g('schema', CAT, 'reporting', None, SP, 'USE_SCHEMA')]
    + [_g('table', CAT, r.split('.')[0], r.split('.')[1], SP, 'SELECT') for r in sorted(ALLOWED)]
    + [_g(lvl, 'samples', sch, n, PU, p) for lvl, sch, n in [('catalog', None, None), ('schema', 'tpch', None),
                                                           ('table', 'tpch', 'orders')]
       for p in ('USE_CATALOG', 'USE_SCHEMA', 'SELECT', 'EXECUTE', 'READ_VOLUME')]                      # (a)
    + [_g('catalog', 'system', None, None, PU, 'USE_CATALOG')]                                          # (b)
    + [_g('catalog', 'workspace', None, None, WS_USERS, 'USE_CATALOG')]
    + [_g('schema', 'workspace', 'default', None, WS_USERS, p) for p in sorted(guarded._SANDBOX_CREATE)]  # (c)
    + [_g('schema', 'system', 'ai', None, PU, p) for p in ('USE_SCHEMA', 'SELECT', 'EXECUTE', 'READ_VOLUME')]  # (d)
    + [_g('metastore', None, None, None, PU, 'USE_MARKETPLACE_ASSETS')]                                 # (e)
    + [_g('external_location', '__databricks_managed_storage_location', None, None, PU,
          'CREATE_MANAGED_STORAGE')]                                                                     # (f)
    + [_g('table', c, 'information_schema', 'tables', PU, 'SELECT') for c in (CAT, 'system', 'workspace')]
    + [_g('schema', c, 'information_schema', None, PU, 'USE_SCHEMA') for c in (CAT, 'system')]          # (g)
    # quyền của nhóm mà SP KHÔNG thuộc: không áp dụng
    + [_g('catalog', CAT, None, None, 'DB - RESERVED - account admins', 'ALL_PRIVILEGES', False)]
)
BASE_OBJECTS = (
    [('catalog', CAT, None, None, 'pm@example.com', False), ('schema', CAT, 'reporting', None, 'pm@example.com', False)]
    + [_t(CAT, *r.split('.')) for r in sorted(ALLOWED)]
    + [_t(CAT, 'information_schema', 'tables', 'System user'), _t('samples', 'tpch', 'orders', 'System user'),
       _t('system', 'ai', 'models', 'System user')]
)


def _v(me=SP, grants=None, objects=None, expected=SP):
    return _dbx_violations(me, expected, BASE_GRANTS if grants is None else grants,
                           BASE_OBJECTS if objects is None else objects, ALLOWED, CAT)


def test_quyen_dung_thiet_ke_va_7_ngoai_le_nen_tang_thi_dat():
    assert _v() == []


def test_luat_1_danh_tinh_khac_sp_da_cau_hinh_bi_chan():
    # vd. app lỡ kết nối bằng tài khoản người hoặc SP của app
    assert 'không phải service principal AI' in _v(me='pm@example.com')[0]
    assert _v(me=SP.upper()) == []                       # so không phân biệt hoa thường


@pytest.mark.parametrize('obj', [
    ('table', CAT, 'reporting', 'rpt_revenue_yearly', SP, False),
    ('schema', CAT, 'reporting', None, 'nhom-ai', True),           # owner là nhóm mà SP thuộc về
    ('catalog', 'workspace', None, None, SP, False),               # owner ở catalog khác cũng chặn
], ids=['bang', 'schema-qua-nhom', 'catalog-khac'])
def test_luat_2_sp_la_owner_bi_chan(obj):
    assert any('owner' in w for w in _v(objects=BASE_OBJECTS + [obj]))


def test_luat_2_owner_la_nhom_sp_khong_thuoc_thi_dat():
    assert _v(objects=BASE_OBJECTS + [('schema', CAT, 'marts', None, 'nhom-khac', False)]) == []


@pytest.mark.parametrize('grant', [
    _g('schema', CAT, 'reporting', None, SP, 'SELECT'),                       # thừa kế xuống MỌI bảng reporting
    _g('catalog', CAT, None, None, SP, 'SELECT'),
    _g('table', CAT, 'reporting', 'rpt_revenue_yearly', SP, 'MODIFY'),
    _g('table', CAT, 'reporting', 'rpt_revenue_yearly', SP, 'ALL_PRIVILEGES'),
    _g('table', CAT, 'reporting', 'ps2_direction_rule', SP, 'SELECT'),        # bảng ngoài 14 bảng
    _g('table', CAT, 'marts', 'fct_order_line', SP, 'SELECT'),
    _g('schema', CAT, 'reporting', None, SP, 'CREATE_TABLE'),
    _g('schema', CAT, 'reporting', None, 'nhom-ai', 'MODIFY', True),          # qua nhóm SP thuộc về
    _g('schema', 'workspace', 'default', None, SP, 'CREATE_TABLE'),           # ngoại lệ (c) chỉ cho nhóm nền tảng
    _g('schema', 'workspace', 'other', None, WS_USERS, 'CREATE_TABLE'),       # (c) chỉ đúng schema default
    _g('catalog', 'workspace', None, None, WS_USERS, 'CREATE_SCHEMA'),
    _g('catalog', 'samples', None, None, PU, 'ALL_PRIVILEGES'),               # (a) chỉ quyền đọc
    _g('schema', 'system', 'billing', None, PU, 'SELECT'),                    # (d) chỉ system.ai
    _g('metastore', None, None, None, PU, 'CREATE_CATALOG'),                  # (e) chỉ marketplace
    _g('external_location', 'loc_khac', None, None, PU, 'CREATE_MANAGED_STORAGE'),   # (f) chỉ vị trí quản lý
    _g('external_location', '__databricks_managed_storage_location', None, None, PU, 'WRITE_FILES'),
    _g('table', CAT, 'information_schema', 'tables', SP, 'MODIFY'),           # (g) chỉ USE_SCHEMA/SELECT
    _g('volume', 'workspace', 'default', 'v', SP, 'WRITE_VOLUME'),
    _g('connection', 'pg', None, None, SP, 'USE_CONNECTION'),
], ids=lambda g: f'{g[5]}@{g[0]}:{g[1]}.{g[2]}.{g[3]}:{g[4][:8]}')
def test_luat_3_quyen_thua_bi_chan(grant):
    assert any('ngoài phạm vi chỉ đọc' in w for w in _v(grants=BASE_GRANTS + [grant]))


def test_luat_3_quyen_cua_nhom_sp_khong_thuoc_thi_khong_tinh():
    assert _v(grants=BASE_GRANTS + [_g('catalog', CAT, None, None, 'nhom-khac', 'MODIFY', False)]) == []


@pytest.mark.parametrize('obj', [_t(CAT, 'reporting', 'ps2_direction_rule'), _t(CAT, 'marts', 'fct_order_line'),
                                 _t('workspace', 'default', 'ban_nhap'), _t('system', 'billing', 'usage')])
def test_luat_4_nhin_thay_bang_ngoai_danh_sach_bi_chan(obj):
    assert any('nhìn thấy bảng' in w for w in _v(objects=BASE_OBJECTS + [obj]))


class _Cursor:
    """Cursor giả: trả lần lượt kết quả cho 3 câu của _check_dbx_identity."""

    def __init__(self, me, grants, objects):
        self.results, self.sql = [[(me,)], grants, objects], []

    def execute(self, sql, params=None):
        self.sql.append(sql)
        self._cur = self.results[len(self.sql) - 1]

    def fetchone(self):
        return self._cur[0]

    def fetchall(self):
        return self._cur


def test_guard_doc_quyen_that_roi_moi_quyet():
    cur = _Cursor(SP, BASE_GRANTS, BASE_OBJECTS)
    guarded._check_dbx_identity(cur, SP, ALLOWED, CAT)
    assert cur.sql[0] == 'select current_user()' and 'table_privileges' in cur.sql[1] and 'tables' in cur.sql[2]
    with pytest.raises(guarded.GuardError, match='ngoài phạm vi'):
        guarded._check_dbx_identity(_Cursor(SP, BASE_GRANTS + [_g('catalog', CAT, None, None, SP, 'SELECT')],
                                            BASE_OBJECTS), SP, ALLOWED, CAT)


def test_sql_guard_doc_moi_view_quyen_va_co_quyen_thua_ke():
    for view in ('metastore_privileges', 'catalog_privileges', 'schema_privileges', 'table_privileges',
                 'volume_privileges', 'routine_privileges', 'connection_privileges', 'external_location_privileges',
                 'storage_credential_privileges'):
        assert f'system.information_schema.{view}' in guarded._DBX_GRANTS, view
    for view in ('catalogs', 'schemata', 'tables', 'volumes'):
        assert f'system.information_schema.{view} ' in guarded._DBX_OBJECTS + ' ', view
    assert '%' not in guarded._DBX_GRANTS + guarded._DBX_OBJECTS


def test_thieu_sp_ai_thi_tu_choi_khong_dung_profile_nguoi(monkeypatch, tmp_path):
    monkeypatch.setattr(guarded, 'AI_CONFIG', tmp_path / 'khong_co.env')
    for k in ('RETAIL_AI_DBX_CLIENT_ID', 'RETAIL_AI_DBX_CLIENT_SECRET'):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(guarded.GuardError, match='RETAIL_AI_DBX_CLIENT_ID'):
        guarded.open_session('databricks', ALLOWED)
    r = tools.run({'tool': 'get_revenue_summary', 'arguments': {'metric': 'R', 'year': 2019}}, 'databricks')
    assert r.status == 'query_error' and 'chỉ đọc' in r.message and not r.rows


def test_tham_so_databricks_dung_dau_hoi():
    assert guarded.Statement('select 1 where a = {p}', (1,)).render('databricks') == 'select 1 where a = ?'


class _FetchCursor:
    description = [('BUILT_AT_UTC',)]

    def __init__(self, rows=None, err=None):
        self.rows, self.err = rows or [], err

    def execute(self, sql, params):
        if self.err:
            raise self.err

    def fetchmany(self, n):
        return self.rows[:n]


def _sess(cur, max_rows=3):
    s = guarded._DatabricksSession.__new__(guarded._DatabricksSession)
    s.cur, s.max_rows, s.timeout_s = cur, max_rows, 60
    return s


def test_fetch_databricks_tu_choi_vuot_so_dong_va_bo_mui_gio():
    with pytest.raises(guarded.RowLimitExceeded):
        _sess(_FetchCursor([(i,) for i in range(4)])).fetch(guarded.Statement('select 1'))
    utc = dt.datetime(2026, 10, 3, 16, 16, 23, tzinfo=dt.timezone.utc)
    f = _sess(_FetchCursor([(utc,)])).fetch(guarded.Statement('select 1'))
    assert f.columns == ['built_at_utc'] and f.rows == [(dt.datetime(2026, 10, 3, 16, 16, 23),)]
    with pytest.raises(guarded.QueryTimeout):
        _sess(_FetchCursor(err=RuntimeError('Query has been timed out'))).fetch(guarded.Statement('select 1'))


class _DoiBuild:
    """Phiên DuckDB thật, nhưng lần đọc lại build marker cuối lượt trả mốc khác (kho vừa dựng lại giữa chừng)."""

    def __init__(self, doi):
        self.inner, self.doi = guarded.open_session('duckdb', ALLOWED), doi

    def fetch(self, st):
        f = self.inner.fetch(st)
        if self.doi and st.sql == 'select built_at_utc from reporting.rpt_build_info':
            return guarded.Fetched(f.columns, [(dt.datetime(2099, 1, 1),)])
        return f

    def close(self):
        self.inner.close()


@pytest.mark.parametrize('doi', [False, True])
def test_kho_dung_lai_giua_chung_thi_khong_tra_so(monkeypatch, doi):
    monkeypatch.setattr(tools, 'open_session', lambda *a, **k: _DoiBuild(doi))
    call = {'tool': 'get_revenue_summary', 'arguments': {'metric': 'R', 'year': 2019}}
    r = tools.run(call, 'databricks')
    if doi:
        assert r.status == 'query_error' and 'dựng lại' in r.message and not r.rows
    else:
        dk = tools.run(call, 'duckdb')
        assert r.status == 'ok' and r.rows == dk.rows


# --- cần cloud ---

def _pm_cursor():
    from databricks import sql as dbsql
    from databricks.sdk.core import Config
    c = databricks_config()
    auth = Config(profile=c['DATABRICKS_CONFIG_PROFILE'])
    token = auth.authenticate()['Authorization'].removeprefix('Bearer ')
    conn = dbsql.connect(server_hostname=auth.host.removeprefix('https://').rstrip('/'),
                         http_path=f"/sql/1.0/warehouses/{c['DATABRICKS_WAREHOUSE_ID']}", access_token=token,
                         catalog=c.get('RETAIL_DATABRICKS_CATALOG', CAT))
    return conn, conn.cursor()


@cloud
def test_tai_khoan_pm_bi_guard_tu_choi():
    """Tài khoản người (owner mọi bảng retail_lab) không bao giờ được dùng làm danh tính AI, kể cả khi cấu hình nhầm."""
    conn, cur = _pm_cursor()
    try:
        cur.execute('select current_user()')
        me = cur.fetchone()[0]
        with pytest.raises(guarded.GuardError, match='không phải service principal'):
            guarded._check_dbx_identity(cur, SP, ALLOWED, CAT)
        with pytest.raises(guarded.GuardError, match='owner'):          # cấu hình nhầm id của SP = email của PM
            guarded._check_dbx_identity(cur, me, ALLOWED, CAT)
    finally:
        cur.close()
        conn.close()


@cloud
@pytest.mark.skipif(not all(guarded.ai_databricks_principal()), reason='chưa cấu hình service principal AI')
@pytest.mark.parametrize('tool,args', _PG_CALLS, ids=lambda x: x if isinstance(x, str) else '-'.join(map(str, x.values())))
def test_databricks_tra_cung_so_duckdb(tool, args):
    # Databricks == DuckDB ở mọi tổ hợp đang mở; DuckDB == CSV ở test_ai_tools*.py. Hai kho phải dựng từ cùng commit.
    db = tools.run({'tool': tool, 'arguments': args}, 'databricks')
    dk = tools.run({'tool': tool, 'arguments': args}, 'duckdb')
    assert db.status == dk.status == 'ok', db.message
    _giong_nhau(db.rows, dk.rows, 'rows')
    _giong_nhau(db.derived, dk.derived, 'derived')
