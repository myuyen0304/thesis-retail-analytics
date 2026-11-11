"""Thử Files API bằng KhoVolume L1; PM chạy thật, không gửi SQL."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import sys
from threading import Barrier, Lock
from types import SimpleNamespace
from uuid import uuid4

# Cho phép chạy trực tiếp từ root mà không cần cài ứng dụng Streamlit.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'apps' / 'retail_app'))
from ui.kho_dot import DaCo, KhoVolume, TrangThaiDaDoi


DEFAULT_ROOT = '/Volumes/retail_lab/nhap_du_lieu/kho'


def read_credentials(path, identity, host=None):
    """Chỉ lấy ba khóa cho danh tính đã chọn; không nạp vào môi trường."""
    prefix = 'RETAIL_NHAP_DBX' if identity == 'writer' else 'RETAIL_PIPELINE'
    wanted = {prefix + '_CLIENT_ID', prefix + '_CLIENT_SECRET', 'DATABRICKS_HOST'}
    values = {}
    with Path(path).open(encoding='utf-8-sig') as stream:
        for line in stream:
            key, separator, value = line.strip().removeprefix('export ').partition('=')
            key = key.strip()
            if not separator or key not in wanted:
                continue
            value = value.strip()
            if value.startswith(('"', "'")):
                quote = value[0]
                end = value.find(quote, 1)
                if end < 0 or (value[end + 1:].strip() and not value[end + 1:].lstrip().startswith('#')):
                    raise ValueError('Cấu hình không hợp lệ.')
                value = value[1:end]
            else:
                value = re.split(r'\s+#', value, maxsplit=1)[0].strip()
            values[key] = value
    result = dict(host=values.get('DATABRICKS_HOST') or host,
                  client_id=values.get(prefix + '_CLIENT_ID'),
                  client_secret=values.get(prefix + '_CLIENT_SECRET'), auth_type='oauth-m2m')
    if not all(result.values()):
        raise ValueError('Thiếu cấu hình đăng nhập.')
    return result


class ObservedFiles:
    """Ghi nhớ byte gửi để đối chiếu mã do KhoVolume tự sinh, không đổi Files API."""
    def __init__(self, files):
        self.files = files
        self.sent = {}
        self.lock = Lock()
        self.race_folder = None
        self.race_barrier = None

    def __getattr__(self, name):
        return getattr(self.files, name)

    def list_directory_contents(self, path):
        try:
            return list(self.files.list_directory_contents(path))
        finally:
            # Hai luồng đọc xong cùng số hiện tại rồi mới cùng tranh ghi số kế.
            if path == self.race_folder:
                self.race_barrier.wait()

    def upload(self, path, contents, *, overwrite=False):
        data = contents.read()
        contents.seek(0)
        with self.lock:
            self.sent.setdefault(path, []).append(data)
        return self.files.upload(path, contents, overwrite=overwrite)


def checks(store, prefix, observed):
    first = prefix + '/v1/byte.bin'
    payload = bytes(range(256))

    def v1():
        store.ghi_moi(first, payload)
        return store.doc(first) == payload

    def v2():
        try:
            store.ghi_moi(first, b'ban-thu-hai')
        except DaCo:
            return store.doc(first) == payload
        return False

    def v3():
        return (store.liet_ke(prefix + '/v1') == ['byte.bin']
                and store.liet_ke(prefix + '/khong_co') == [])

    def v4():
        folder = prefix + '/v4'
        codes = []
        for expected in (1, 2):
            number = store.ghi_json_so_tiep(folder, {'thu': expected})
            path = f'{folder}/{expected:06d}.json'
            saved = json.loads(store.doc(path))
            sent = json.loads(observed.sent[store.root + '/' + path][0])
            if number != expected or saved != sent or not re.fullmatch('[a-f0-9]{32}', saved['ma']):
                return False
            codes.append(saved['ma'])
        return len(set(codes)) == 2

    def v5():
        passed = True
        for round_number in range(5):
            folder = f'{prefix}/v5/{round_number}'
            barrier = Barrier(2, timeout=30)

            def compete(worker):
                barrier.wait()
                try:
                    number = store.ghi_json_so_tiep(folder, {'luong': worker}, expected=0)
                    return ('thang', number, worker)
                except TrangThaiDaDoi:
                    return ('thua', None, worker)

            observed.race_folder = store.root + '/' + folder
            observed.race_barrier = Barrier(2, timeout=30)
            try:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(compete, (0, 1)))
            finally:
                observed.race_folder = None
                observed.race_barrier = None
            winners = [r for r in results if r[0] == 'thang']
            losers = [r for r in results if r[0] == 'thua']
            valid = len(winners) == len(losers) == 1 and winners[0][1] == 1
            if valid:
                saved = json.loads(store.doc(folder + '/000001.json'))
                valid = saved['luong'] == winners[0][2] and store.liet_ke(folder) == ['000001.json']
            passed = passed and valid
        return passed

    def v6():
        data = bytes(range(256)) * 4096
        path = prefix + '/v6/megabyte.bin'
        store.ghi_moi(path, data)
        return hashlib.sha256(store.doc(path)).digest() == hashlib.sha256(data).digest()

    return [('V1', v1), ('V2', v2), ('V3', v3), ('V4', v4), ('V5', v5), ('V6', v6)]


def cleanup(files, run_root, messages):
    """Chỉ dọn lượt hiện tại; đường dẫn từ API cũng phải kiểm trước khi dùng."""
    from databricks.sdk.errors import NotFound
    visited = set()

    def allowed(path):
        return (isinstance(path, str) and (path == run_root or path.startswith(run_root + '/'))
                and all(part not in ('', '.', '..') for part in path.split('/')[1:]))

    def warning(path, error):
        messages.append(f'Cảnh báo dọn: {path} ({type(error).__name__})')

    def remove(path, directory):
        # Files API có thể trả đường dẫn thư mục kèm đúng một dấu / cuối.
        if directory and isinstance(path, str) and path.endswith('/'):
            path = path[:-1]
        if not allowed(path):
            warning(path, ValueError())
            return
        try:
            if directory:
                if path in visited:
                    return
                visited.add(path)
                try:
                    entries = list(files.list_directory_contents(path))
                except NotFound:
                    return
                for entry in entries:
                    remove(entry.path, entry.is_directory)
                files.delete_directory(path)
            else:
                files.delete(path)
        except Exception as error:
            warning(path, error)

    remove(run_root, True)


def run(client, root, messages):
    from databricks.sdk.errors import Unauthenticated
    if not re.fullmatch(r'/Volumes/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*', root):
        raise ValueError('Gốc Volume không hợp lệ.')
    prefix = 'thu_ket_noi/' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_') + uuid4().hex[:6]
    observed = ObservedFiles(client.files)
    store = KhoVolume(root, SimpleNamespace(files=observed))
    status = 0
    try:
        for code, check in checks(store, prefix, observed):
            try:
                passed = check()
            except Unauthenticated as error:
                messages.append(f'{code}: TRƯỢT')
                messages.append(f'Không đăng nhập được ({type(error).__name__}).')
                return 3
            except Exception as error:
                messages.append(f'{code}: TRƯỢT ({type(error).__name__})')
                status = 1
                continue
            messages.append(f'{code}: ' + ('ĐẠT' if passed else 'TRƯỢT'))
            if not passed:
                status = 1
    finally:
        cleanup(client.files, root + '/' + prefix, messages)
    return status


def main(argv=None, *, client_factory=None):
    parser = argparse.ArgumentParser(description='Thử kho Volume bằng Files API.')
    parser.add_argument('--env-file', required=True)
    parser.add_argument('--danh-tinh', choices=('writer', 'pipeline'), required=True)
    parser.add_argument('--host')
    parser.add_argument('--goc', default=DEFAULT_ROOT)
    args = parser.parse_args(argv)
    messages, credentials = [], {}
    previous_logging = logging.root.manager.disable
    # SDK có thể ghi cấu hình trong lỗi/log; chỉ xuất các thông báo đã kiểm soát.
    with open(os.devnull, 'w', encoding='utf-8') as sink, redirect_stdout(sink), redirect_stderr(sink):
        logging.disable(sys.maxsize)
        try:
            try:
                credentials = read_credentials(args.env_file, args.danh_tinh, args.host)
                if client_factory is None:
                    from databricks.sdk import WorkspaceClient
                    client_factory = WorkspaceClient
                client = client_factory(**credentials)
                client.config.authenticate()
            except Exception as error:
                messages.append(f'Không đăng nhập được ({type(error).__name__}).')
                status = 3
            else:
                try:
                    status = run(client, args.goc.rstrip('/'), messages)
                except Exception as error:
                    messages.append(f'Không thử được kho Volume ({type(error).__name__}).')
                    status = 1
        finally:
            logging.disable(previous_logging)
    for message in messages:
        for key in ('host', 'client_id', 'client_secret'):
            value = credentials.get(key)
            if value:
                message = message.replace(value, '[đã ẩn]')
        print(message)
    return status


if __name__ == '__main__':
    sys.exit(main())
