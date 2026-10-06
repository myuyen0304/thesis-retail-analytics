"""Đường đọc có kiểm soát cho AI Explain (docs/ai_explain_plan.md §5, §11.3). Tách khỏi `read_sql` của các trang.

Khác `connection.read_sql`:
- giá trị truyền qua tham số của driver, không ghép vào chuỗi SQL; tên bảng/cột do code giữ (ai_explain/tools.py);
- giữ nguyên `Decimal` (tiền) và kiểu gốc, không đổi sang float64;
- giới hạn thời gian thực thi và số dòng: vượt số dòng thì TỪ CHỐI, không cắt bớt;
- mọi câu của một lượt chạy trong CÙNG một kết nối (DuckDB chỉ đọc; PostgreSQL REPEATABLE READ, READ ONLY),
  nên build marker, trạng thái kiểm và dòng số liệu đọc từ cùng một bản dữ liệu;
- PostgreSQL dùng tài khoản riêng PG_AI_USER / PG_AI_PASSWORD và kiểm quyền thật trước khi đọc:
  từ chối superuser, quyền ghi/tạo, hoặc quyền SELECT ngoài danh sách bảng cho phép.
- Databricks dùng service principal riêng RETAIL_AI_DBX_CLIENT_ID / RETAIL_AI_DBX_CLIENT_SECRET (OAuth M2M), KHÔNG
  dùng profile của người, và kiểm quyền Unity Catalog thật trước khi đọc (`_dbx_violations`). Databricks không có
  snapshot xuyên câu: tools.run đọc lại build marker cuối lượt để phát hiện kho dựng lại giữa chừng.
"""
import datetime as dt
import os
import threading
from dataclasses import dataclass

from dwh.connection import ROOT, databricks_config, duckdb_path, env_file_config

DEFAULT_TIMEOUT_S = 5.0
DATABRICKS_TIMEOUT_S = 60.0     # warehouse 2X-Small khởi động nguội: câu đầu đo được 21,8 giây (2026-10-06)
AI_CONFIG = ROOT / '.env.ai.local'
DEFAULT_MAX_ROWS = 200


class GuardError(Exception):
    """Kết nối không đạt điều kiện an toàn (thiếu tài khoản chỉ đọc, role có quyền ghi...). Không đọc gì."""


class QueryTimeout(Exception):
    pass


class RowLimitExceeded(Exception):
    pass


@dataclass(frozen=True)
class Statement:
    """Một câu SELECT cố định. `{p}` là chỗ đặt tham số, đổi thành `?` (DuckDB) hoặc `%s` (psycopg)."""
    sql: str
    params: tuple = ()

    def render(self, backend: str) -> str:
        if '%' in self.sql:
            raise ValueError('SQL cho AI không được chứa ký tự %')  # psycopg coi % là chỗ đặt tham số
        return self.sql.replace('{p}', '%s' if backend == 'postgres' else '?')


@dataclass(frozen=True)
class Fetched:
    columns: list
    rows: list          # list[tuple], kiểu gốc của driver (Decimal, int, date...)

    def records(self) -> list[dict]:
        return [dict(zip(self.columns, r)) for r in self.rows]


# --- DuckDB ---

class _DuckDBSession:
    def __init__(self, timeout_s: float, max_rows: int):
        import duckdb
        self._duckdb = duckdb
        self.con = duckdb.connect(str(duckdb_path()), read_only=True)
        self.timeout_s, self.max_rows = timeout_s, max_rows

    def fetch(self, st: Statement) -> Fetched:
        timer = threading.Timer(self.timeout_s, self.con.interrupt)   # DuckDB không có statement_timeout
        timer.start()
        try:
            cur = self.con.execute(st.render('duckdb'), list(st.params))
            rows = cur.fetchmany(self.max_rows + 1)
        except self._duckdb.InterruptException as e:
            raise QueryTimeout(f'quá {self.timeout_s} giây') from e
        finally:
            timer.cancel()
        if len(rows) > self.max_rows:
            raise RowLimitExceeded(f'kết quả vượt {self.max_rows} dòng')
        return Fetched([d[0].lower() for d in cur.description], rows)

    def close(self):
        self.con.close()


# --- PostgreSQL ---

def _check_pg_role(cur, allowed_relations: frozenset[str]) -> None:
    """Đọc quyền THẬT của tài khoản đang kết nối. Code chỉ chứa SELECT chưa chứng minh DB đã giới hạn quyền."""
    cur.execute('select rolsuper, rolcreaterole, rolcreatedb, rolbypassrls from pg_roles where rolname = current_user')
    flags = cur.fetchone()
    if flags is None or any(flags):
        raise GuardError('tài khoản AI là superuser hoặc có quyền quản trị (createrole/createdb/bypassrls)')
    cur.execute("select has_database_privilege(current_database(), 'CREATE')")
    if cur.fetchone()[0]:
        raise GuardError('tài khoản AI có quyền CREATE trên database')
    cur.execute("""
        select n.nspname from pg_namespace n
        where n.nspname not in ('pg_catalog', 'information_schema') and n.nspname not like 'pg_toast%%'
          and n.nspname not like 'pg_temp%%' and has_schema_privilege(n.oid, 'CREATE')""")
    if (bad := [r[0] for r in cur.fetchall()]):
        raise GuardError(f'tài khoản AI có quyền CREATE trên schema {bad}')
    cur.execute("""
        select n.nspname || '.' || c.relname,
               has_table_privilege(c.oid, 'INSERT') or has_table_privilege(c.oid, 'UPDATE')
               or has_table_privilege(c.oid, 'DELETE') or has_table_privilege(c.oid, 'TRUNCATE'),
               has_table_privilege(c.oid, 'SELECT')
        from pg_class c join pg_namespace n on n.oid = c.relnamespace
        where c.relkind in ('r', 'v', 'm', 'p', 'f')
          and n.nspname not in ('pg_catalog', 'information_schema') and n.nspname not like 'pg_toast%%'""")
    rels = cur.fetchall()
    if (bad := [r[0] for r in rels if r[1]]):
        raise GuardError(f'tài khoản AI có quyền ghi trên {bad[:5]}')
    if (extra := sorted(r[0] for r in rels if r[2] and r[0] not in allowed_relations)):
        raise GuardError(f'tài khoản AI đọc được bảng ngoài danh sách cho phép: {extra[:5]}')


class _PostgresSession:
    def __init__(self, timeout_s: float, max_rows: int, allowed_relations: frozenset[str]):
        import psycopg
        self._psycopg = psycopg
        user, password = os.environ.get('PG_AI_USER'), os.environ.get('PG_AI_PASSWORD')
        if not user or password is None:
            raise GuardError('chưa cấu hình PG_AI_USER / PG_AI_PASSWORD (tài khoản chỉ đọc riêng cho AI)')
        self.conn = psycopg.connect(
            host=os.environ.get('PG_HOST', 'localhost'), port=int(os.environ.get('PG_PORT', '5433')),
            dbname=os.environ.get('PG_DATABASE', 'retail'), user=user, password=password, connect_timeout=5,
        )
        self.max_rows = max_rows
        try:
            self.conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
            self.conn.read_only = True
            self.cur = self.conn.cursor()
            # SET LOCAL chỉ sống trong transaction này; mọi câu sau dùng cùng snapshot REPEATABLE READ
            self.cur.execute(f'set local statement_timeout = {int(timeout_s * 1000)}')
            _check_pg_role(self.cur, allowed_relations)
        except Exception:
            self.conn.close()
            raise

    def fetch(self, st: Statement) -> Fetched:
        try:
            self.cur.execute(st.render('postgres'), st.params)
            rows = self.cur.fetchmany(self.max_rows + 1)
        except self._psycopg.errors.QueryCanceled as e:
            raise QueryTimeout(str(e)) from e
        if len(rows) > self.max_rows:
            raise RowLimitExceeded(f'kết quả vượt {self.max_rows} dòng')
        return Fetched([d.name.lower() for d in self.cur.description], rows)

    def close(self):
        try:
            self.conn.rollback()     # chỉ đọc: không có gì để commit
        finally:
            self.conn.close()


# --- Databricks (Unity Catalog) ---

# Quyền bản Free cấp sẵn cho MỌI tài khoản (dò 2026-10-06), PM duyệt giữ làm 7 ngoại lệ có tên; không chạm dữ liệu retail:
#   (a) đọc catalog `samples` (dữ liệu mẫu)          (b) USE_CATALOG `system`
#   (c) nhóm _workspace_users_*: USE_CATALOG `workspace`, USE_SCHEMA + CREATE_* trên `workspace.default` (sandbox)
#   (d) đọc/chạy `system.ai`                         (e) USE_MARKETPLACE_ASSETS (metastore)
#   (f) CREATE_MANAGED_STORAGE trên `__databricks_managed_storage_location` (không kèm CREATE_CATALOG thì không tạo được gì)
#   (g) USE_SCHEMA/SELECT trên `information_schema` của mọi catalog (chỉ hiện đối tượng tài khoản vốn đã có quyền)
# Ngoài 7 ngoại lệ này mọi quyền đều bị chặn; trong catalog của kho (retail_lab) không có ngoại lệ nào ngoài (g).
PLATFORM_GROUP = 'account users'
WORKSPACE_USERS_PREFIX = '_workspace_users_'     # nhóm cục bộ của workspace: is_member() không trả đúng (dò 2026-10-06)
_PLATFORM_READ = frozenset({'USE_CATALOG', 'USE_SCHEMA', 'SELECT', 'EXECUTE', 'READ_VOLUME'})
_SANDBOX_CREATE = frozenset({'USE_SCHEMA', 'CREATE_FUNCTION', 'CREATE_MATERIALIZED_VIEW', 'CREATE_MODEL', 'CREATE_TABLE',
                             'CREATE_VOLUME'})

_NULL = 'cast(null as string)'
_MEMBER = '(is_account_group_member({c}) or is_member({c}))'
# Các view *_privileges của Unity Catalog liệt kê cả quyền THỪA KẾ từ catalog/schema (cột inherited_from),
# nên SELECT cấp ở catalog cũng hiện ra ở mức catalog và ở từng bảng.
_DBX_GRANTS = ' union all '.join(
    f"select '{lvl}' as lvl, {c} as cat, {s} as sch, {n} as name, grantee, privilege_type as priv, "
    f"{_MEMBER.format(c='grantee')} as member "
    f'from system.information_schema.{view}'
    for lvl, view, c, s, n in [
        ('metastore', 'metastore_privileges', _NULL, _NULL, _NULL),
        ('catalog', 'catalog_privileges', 'catalog_name', _NULL, _NULL),
        ('schema', 'schema_privileges', 'catalog_name', 'schema_name', _NULL),
        ('table', 'table_privileges', 'table_catalog', 'table_schema', 'table_name'),
        ('volume', 'volume_privileges', 'volume_catalog', 'volume_schema', 'volume_name'),
        ('routine', 'routine_privileges', 'specific_catalog', 'specific_schema', 'specific_name'),
        ('connection', 'connection_privileges', 'connection_name', _NULL, _NULL),
        ('external_location', 'external_location_privileges', 'external_location_name', _NULL, _NULL),
        ('storage_credential', 'storage_credential_privileges', 'storage_credential_name', _NULL, _NULL),
    ])
_DBX_OBJECTS = ' union all '.join(
    f"select '{kind}' as kind, {c} as cat, {s} as sch, {n} as name, {owner} as owner, "
    f"{_MEMBER.format(c=owner)} as member from system.information_schema.{view}"
    for kind, view, c, s, n, owner in [
        ('catalog', 'catalogs', 'catalog_name', _NULL, _NULL, 'catalog_owner'),
        ('schema', 'schemata', 'catalog_name', 'schema_name', _NULL, 'schema_owner'),
        ('table', 'tables', 'table_catalog', 'table_schema', 'table_name', 'table_owner'),
        ('volume', 'volumes', 'volume_catalog', 'volume_schema', 'volume_name', 'volume_owner'),
    ])


def _dbx_grant_ok(lvl, cat, sch, name, grantee, priv, allowed_relations, catalog) -> bool:
    if sch == 'information_schema' and priv in ('USE_SCHEMA', 'SELECT'):
        return True                     # view metadata hệ thống: chỉ hiện đối tượng tài khoản vốn đã có quyền
    if cat == catalog:
        if lvl == 'catalog':
            return priv == 'USE_CATALOG'
        if lvl == 'schema':
            return priv == 'USE_SCHEMA' and sch in {r.split('.')[0] for r in allowed_relations}
        return lvl == 'table' and priv == 'SELECT' and f'{sch}.{name}' in allowed_relations
    if grantee == PLATFORM_GROUP:
        if lvl == 'metastore':
            return priv == 'USE_MARKETPLACE_ASSETS'
        if lvl == 'external_location':
            return cat == '__databricks_managed_storage_location' and priv == 'CREATE_MANAGED_STORAGE'
        if cat == 'samples':                                          # dữ liệu mẫu công khai của Databricks
            return priv in _PLATFORM_READ
        if cat == 'system':
            return (lvl == 'catalog' and priv == 'USE_CATALOG') or (sch == 'ai' and priv in _PLATFORM_READ)
    if grantee.startswith(WORKSPACE_USERS_PREFIX) and cat == 'workspace':   # sandbox mặc định của workspace
        return (lvl == 'catalog' and priv == 'USE_CATALOG') or (lvl == 'schema' and sch == 'default'
                                                                  and priv in _SANDBOX_CREATE)
    return False


def _dbx_platform(who: str) -> bool:
    return who == PLATFORM_GROUP or who.startswith(WORKSPACE_USERS_PREFIX)


def _dbx_violations(me: str, expected: str, grants: list, objects: list, allowed_relations: frozenset[str],
                    catalog: str) -> list[str]:
    """Lý do từ chối (rỗng = đạt). grants: (mức, catalog, schema, tên, grantee, quyền, là_thành_viên);
    objects: (loại, catalog, schema, tên, owner, là_thành_viên). Hàm thuần để test từng luật không cần cloud.
    Quyền cấp cho nhóm nền tảng luôn tính là áp dụng cho tài khoản AI, không dựa vào is_member()."""
    if (me or '').lower() != expected.lower():
        return [f'danh tính đang kết nối ({me}) không phải service principal AI đã cấu hình']
    applies = lambda who, member: who.lower() == me.lower() or bool(member) or _dbx_platform(who)
    out = []
    if (owned := sorted('.'.join(x for x in (c, s, n) if x) for _, c, s, n, who, m in objects
                        if applies(who, m) and not _dbx_platform(who))):
        out.append(f'tài khoản AI là owner của {owned[:5]}')
    if (extra := sorted({f"{p} trên {lvl} {'.'.join(x for x in (c, s, n) if x)} (cấp cho {g})"
                         for lvl, c, s, n, g, p, m in grants
                         if applies(g, m) and not _dbx_grant_ok(lvl, c, s, n, g, p, allowed_relations, catalog)})):
        out.append(f'tài khoản AI có quyền ngoài phạm vi chỉ đọc: {extra[:5]}')
    if (seen := sorted(f'{c}.{s}.{n}' for kind, c, s, n, _, _ in objects
                       if kind == 'table' and s != 'information_schema'
                       and not (c == catalog and f'{s}.{n}' in allowed_relations)
                       and c != 'samples' and not (c == 'system' and s == 'ai'))):
        out.append(f'tài khoản AI nhìn thấy bảng ngoài danh sách cho phép: {seen[:5]}')
    # Tự kiểm: phải nhận ra quyền cần có của CHÍNH mình. Nếu UC ghi grantee theo dạng khác current_user() (vd. tên hiển
    # thị của SP) thì luật 2–3 âm thầm không áp dụng được; thà từ chối còn hơn đạt nhờ không nhìn thấy quyền.
    mine = {(lvl, c, s, n, p) for lvl, c, s, n, g, p, m in grants if applies(g, m)}
    need = ({('catalog', catalog, None, None, 'USE_CATALOG')}
            | {('schema', catalog, r.split('.')[0], None, 'USE_SCHEMA') for r in allowed_relations}
            | {('table', catalog, *r.split('.'), 'SELECT') for r in allowed_relations})
    if (lack := sorted(f"{p} {'.'.join(x for x in (c, s, n) if x)}" for lvl, c, s, n, p in need - mine)):
        out.append(f'không nhận ra quyền của chính tài khoản AI (thiếu {lack[:5]}): có thể chưa cấp quyền, hoặc '
                   'grantee không ghi theo current_user()')
    return out


def ai_databricks_principal() -> tuple[str | None, str | None]:
    """(application id, OAuth secret) của SP chỉ đọc cho AI: biến môi trường hoặc `.env.ai.local`."""
    a = env_file_config(AI_CONFIG, ('RETAIL_AI_',))
    return a.get('RETAIL_AI_DBX_CLIENT_ID'), a.get('RETAIL_AI_DBX_CLIENT_SECRET')


def _utc_naive(v):
    # TIMESTAMP của Databricks kèm múi giờ UTC; Postgres/DuckDB trả UTC không múi → bỏ múi cho giống (như connection.py)
    return v.astimezone(dt.timezone.utc).replace(tzinfo=None) if isinstance(v, dt.datetime) and v.tzinfo else v


class _DatabricksSession:
    def __init__(self, timeout_s: float, max_rows: int, allowed_relations: frozenset[str]):
        from databricks import sql as dbsql
        from databricks.sdk.core import Config
        client_id, secret = ai_databricks_principal()
        if not (client_id and secret):
            raise GuardError('chưa cấu hình RETAIL_AI_DBX_CLIENT_ID / RETAIL_AI_DBX_CLIENT_SECRET (service principal chỉ '
                             'đọc riêng cho AI)')
        c = databricks_config()
        if not (c.get('DATABRICKS_HOST') and c.get('DATABRICKS_WAREHOUSE_ID')):
            raise GuardError('thiếu DATABRICKS_HOST / DATABRICKS_WAREHOUSE_ID')
        catalog = c.get('RETAIL_DATABRICKS_CATALOG', 'retail_lab')
        # Chỉ OAuth M2M của SP AI: không đọc profile hay biến DATABRICKS_CLIENT_* của người / của app.
        auth = Config(host=c['DATABRICKS_HOST'], client_id=client_id, client_secret=secret, auth_type='oauth-m2m')
        token = auth.authenticate()['Authorization'].removeprefix('Bearer ')
        self.max_rows, self.timeout_s, self.cur = max_rows, timeout_s, None
        self.conn = dbsql.connect(server_hostname=auth.host.removeprefix('https://').rstrip('/'),
                                  http_path=f"/sql/1.0/warehouses/{c['DATABRICKS_WAREHOUSE_ID']}", access_token=token,
                                  catalog=catalog, session_configuration={'STATEMENT_TIMEOUT': str(max(1, int(timeout_s)))})
        try:
            self.cur = self.conn.cursor()
            _check_dbx_identity(self.cur, client_id, allowed_relations, catalog)
        except Exception:
            self.close()
            raise

    def fetch(self, st: Statement) -> Fetched:
        try:
            self.cur.execute(st.render('databricks'), list(st.params))
            rows = self.cur.fetchmany(self.max_rows + 1)
        except Exception as e:
            if 'TIMEOUT' in str(e).upper() or 'TIMED OUT' in str(e).upper():
                raise QueryTimeout(f'quá {self.timeout_s} giây') from e
            raise
        if len(rows) > self.max_rows:
            raise RowLimitExceeded(f'kết quả vượt {self.max_rows} dòng')
        return Fetched([d[0].lower() for d in self.cur.description], [tuple(_utc_naive(v) for v in r) for r in rows])

    def close(self):
        try:
            if self.cur is not None:
                self.cur.close()
        finally:
            self.conn.close()


def _check_dbx_identity(cur, expected: str, allowed_relations: frozenset[str], catalog: str) -> None:
    """Đọc danh tính và quyền THẬT của phiên (như _check_pg_role); vi phạm thì GuardError, không đọc dữ liệu."""
    cur.execute('select current_user()')
    me = cur.fetchone()[0]
    cur.execute(_DBX_GRANTS)
    grants = [tuple(r) for r in cur.fetchall()]
    cur.execute(_DBX_OBJECTS)
    objects = [tuple(r) for r in cur.fetchall()]
    if (why := _dbx_violations(me, expected, grants, objects, allowed_relations, catalog)):
        raise GuardError('; '.join(why))


def open_session(backend: str, allowed_relations: frozenset[str], timeout_s: float | None = None,
                 max_rows: int = DEFAULT_MAX_ROWS):
    """Một phiên đọc cho một lượt gọi tool. Gọi .fetch(Statement) nhiều lần, rồi .close().
    timeout_s=None: mặc định theo backend (Databricks lâu hơn vì warehouse có thể đang khởi động)."""
    if backend == 'duckdb':
        return _DuckDBSession(timeout_s or DEFAULT_TIMEOUT_S, max_rows)
    if backend == 'postgres':
        return _PostgresSession(timeout_s or DEFAULT_TIMEOUT_S, max_rows, allowed_relations)
    if backend == 'databricks':
        return _DatabricksSession(timeout_s or DATABRICKS_TIMEOUT_S, max_rows, allowed_relations)
    raise ValueError(f'Backend không hỗ trợ: {backend!r}')
