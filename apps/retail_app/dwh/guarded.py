"""Đường đọc có kiểm soát cho AI Explain (docs/ai_explain_plan.md §5, §11.3). Tách khỏi `read_sql` của các trang.

Khác `connection.read_sql`:
- giá trị truyền qua tham số của driver, không ghép vào chuỗi SQL; tên bảng/cột do code giữ (ai_explain/tools.py);
- giữ nguyên `Decimal` (tiền) và kiểu gốc, không đổi sang float64;
- giới hạn thời gian thực thi và số dòng: vượt số dòng thì TỪ CHỐI, không cắt bớt;
- mọi câu của một lượt chạy trong CÙNG một kết nối (DuckDB chỉ đọc; PostgreSQL REPEATABLE READ, READ ONLY),
  nên build marker, trạng thái kiểm và dòng số liệu đọc từ cùng một bản dữ liệu;
- PostgreSQL dùng tài khoản riêng PG_AI_USER / PG_AI_PASSWORD và kiểm quyền thật trước khi đọc:
  từ chối superuser, quyền ghi/tạo, hoặc quyền SELECT ngoài danh sách bảng cho phép.
"""
import os
import threading
from dataclasses import dataclass

from dwh.connection import duckdb_path

DEFAULT_TIMEOUT_S = 5.0
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
        return self.sql.replace('{p}', '?' if backend == 'duckdb' else '%s')


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


def open_session(backend: str, allowed_relations: frozenset[str], timeout_s: float = DEFAULT_TIMEOUT_S,
                 max_rows: int = DEFAULT_MAX_ROWS):
    """Một phiên đọc cho một lượt gọi tool. Gọi .fetch(Statement) nhiều lần, rồi .close()."""
    if backend == 'duckdb':
        return _DuckDBSession(timeout_s, max_rows)
    if backend == 'postgres':
        return _PostgresSession(timeout_s, max_rows, allowed_relations)
    raise ValueError(f'Backend không hỗ trợ: {backend!r}')
