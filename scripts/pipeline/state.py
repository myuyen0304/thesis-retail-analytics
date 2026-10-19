"""Registry và con trỏ công bố: một payload được cập nhật bằng compare-and-swap."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import uuid


@contextmanager
def writer_lock(root):
    """Một writer trên volume local dùng chung bởi CLI và Airflow LocalExecutor."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'writer.lock').open('a+b') as lock:
        lock.seek(0)
        if os.name == 'nt':
            import msvcrt
            if not lock.read(1):
                lock.write(b'0')
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == 'nt':
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    try:
        os.replace(f.name, path)
    finally:
        if Path(f.name).exists():
            Path(f.name).unlink()


class Registry:
    def __init__(self, root, sql=None):
        self.path, self.sql = Path(root) / 'state.json', sql

    def initialize(self):
        empty = {'version': uuid.uuid4().hex, 'payload': {'active': None, 'releases': {}}}
        if self.sql:
            self.sql('create schema if not exists retail_control')
            self.sql('create table if not exists retail_control.state (name string, version string, payload string) using delta')
            self.sql("merge into retail_control.state t using (select 'main' as name, ? as version, ? as payload) s "
                     'on t.name = s.name when not matched then insert *',
                     [empty['version'], json.dumps(empty['payload'])])
        elif not self.path.exists():
            atomic_json(self.path, empty)

    def read(self):
        if not self.sql:
            return json.loads(self.path.read_text(encoding='utf-8'))
        _, rows = self.sql("select version, payload from retail_control.state where name = 'main'")
        if len(rows) != 1:
            raise ValueError('Registry không có đúng một dòng main')
        return {'version': rows[0][0], 'payload': json.loads(rows[0][1])}

    def save(self, before, payload):
        version = uuid.uuid4().hex
        if self.sql:
            self.sql("update retail_control.state set version = ?, payload = ? where name = 'main' and version = ?",
                     [version, json.dumps(payload), before['version']])
            if self.read()['version'] != version:
                raise RuntimeError('Writer khác đã cập nhật registry; dừng công bố')
        else:
            if self.read()['version'] != before['version']:
                raise RuntimeError('Registry đã thay đổi')
            atomic_json(self.path, {'version': version, 'payload': payload})

    def register(self, record):
        before = self.read()
        state = before['payload']
        rid = record['release_id']
        if rid in state['releases'] and state['releases'][rid] != record:
            raise ValueError('Không được sửa bản đã qua quality gate')
        state['releases'][rid] = record
        self.save(before, state)

    def publish(self, rid, expected):
        before = self.read()
        state = before['payload']
        if rid not in state['releases'] or state['releases'][rid]['status'] != 'ready':
            raise ValueError('Bản chưa đạt quality gate')
        if state['active'] == rid:
            return  # Retry sau khi commit thành công nhưng mất ACK.
        if state['active'] != expected:
            raise RuntimeError('Phiên bản đang phục vụ đã đổi; không ghi đè kết quả mới hơn')
        state['active'] = rid
        # Giờ công bố nằm cạnh con trỏ, không trong bản ghi release (register() cấm sửa bản đã qua gate). Ghi kèm release_id:
        # code trước S3 đổi con trỏ (rollback) mà không ghi giờ thì app thấy giờ không khớp bản và không hiện giờ sai.
        state['active_since'] = {'release_id': rid,
                                 'at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
        self.save(before, state)
