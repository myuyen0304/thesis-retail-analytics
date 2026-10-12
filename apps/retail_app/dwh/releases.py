"""Một phiên bản bất biến cho toàn bộ lượt đọc; mặc định tương thích kho cũ."""
from contextvars import ContextVar
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re

CONTROL_RELATION = 'retail_control.state'
_pin = ContextVar('retail_release', default=None)
_depth = ContextVar('retail_release_depth', default=0)
_HEX = re.compile(r'[a-f0-9]{24}')


def enabled(backend):
    return os.getenv('RETAIL_RELEASE_MODE', 'legacy') == 'versioned' and backend in ('duckdb', 'databricks')


def checked(record):
    if not isinstance(record, dict) or not _HEX.fullmatch(record.get('release_id', '')):
        raise ValueError('Phiên bản dữ liệu không hợp lệ')
    if record.get('status') != 'ready' or record.get('schema') != f"r_{record['release_id']}_reporting":
        raise ValueError('Phiên bản chưa qua quality gate')
    return record


def local_state():
    path = os.getenv('RETAIL_RELEASE_STATE', 'warehouse/pipeline/state.json')
    return json.loads(Path(path).read_text(encoding='utf-8'))['payload']


def choose(state, requested=None):
    rid = requested or state.get('active')
    if not rid or rid not in state['releases']:
        raise ValueError('Chưa có phiên bản dữ liệu được công bố')
    record = checked(state['releases'][rid])
    if record['release_id'] != rid:
        raise ValueError('Định danh phiên bản không khớp registry')
    return record


def reset():
    _pin.set(None)


@contextmanager
def scope():
    """Giữ pin UI nếu có; xóa pin mới của lượt gọi độc lập khi kết thúc."""
    token = _pin.set(_pin.get()) if _depth.get() == 0 else None
    depth_token = _depth.set(_depth.get() + 1)
    try:
        yield
    finally:
        _depth.reset(depth_token)
        if token is not None:
            _pin.reset(token)


def pinned_read(fn):
    from functools import wraps
    @wraps(fn)
    def wrapped(*args, **kwargs):
        with scope():
            return fn(*args, **kwargs)
    return wrapped


def current():
    return _pin.get()


def pin(record):
    _pin.set(checked(record))
    return record


def resolve(backend, fetch=None):
    if not enabled(backend):
        return None
    if current() is not None:
        return current()
    if backend == 'duckdb':
        state = local_state()
    else:
        if fetch is None:
            raise ValueError('Cần kết nối để xác định phiên bản')
        rows = fetch(f"select payload from {CONTROL_RELATION} where name = 'main'")
        if len(rows) != 1:
            raise ValueError('Registry phải có đúng một dòng main')
        state = json.loads(rows[0][0])
    return pin(choose(state))


def sql_for(sql, record):
    """Chỉ ánh xạ tên relation do code giữ; không nhận SQL do LLM sinh."""
    if record is None:
        return sql
    checked(record)
    return re.sub(r'\breporting\.([a-z_][a-z_0-9]*)\b', lambda m: record['schema'] + '.' + m[1], sql)


def allowed_versions(state, logical):
    """Chỉ cho phép whitelist trong các bản đã qua gate; giữ quyền bản cũ để đọc/rollback."""
    out = set(logical) | {CONTROL_RELATION}  # Giữ kho cũ trong thời gian chuyển đổi.
    for rid, record in state['releases'].items():
        record = choose(state, rid)
        out.update(record['schema'] + '.' + r.split('.')[1] for r in logical)
    return frozenset(out)
