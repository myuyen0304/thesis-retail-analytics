"""Điều phối subprocess local, đọc trạng thái từ đĩa, không phụ thuộc phiên Streamlit."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / 'apps/retail_app') not in sys.path:
    sys.path.insert(0, str(ROOT / 'apps/retail_app'))
from ui.nhap_store import RequestStore, actor, utc
from scripts.ingest.approval import has_dbt_model
from scripts.pipeline.state import atomic_json, writer_lock

PIPELINE_ROOT = 'warehouse/pipeline/ui-nhap'
STAGES = ('prepare', 'forecast', 'build', 'validate')


def lenh(stage, run_id, ten, extension_dir):
    if stage not in (*STAGES, 'publish') or not re.fullmatch(r'ui-[A-Za-z0-9_-]+', run_id):
        raise ValueError('Stage hoặc run_id không hợp lệ.')
    if not re.fullmatch(r'[a-z][a-z0-9_]*', ten):
        raise ValueError('Tên phần mở rộng không hợp lệ.')
    # Giới hạn này phải còn đúng ngay cả khi hằng số bị thay đổi nhầm.
    if PIPELINE_ROOT != 'warehouse/pipeline/ui-nhap':
        raise ValueError('Root nhập dữ liệu không hợp lệ.')
    cmd = [sys.executable, '-m', 'scripts.pipeline.cli', stage, '--run-id', run_id,
           '--target', 'duckdb', '--root', PIPELINE_ROOT]
    if stage == 'prepare':
        cmd += ['--extension', ten, '--extension-dir', str(Path(extension_dir).resolve())]
    return cmd


def _pid_alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == 'nt':
        import ctypes
        kernel = ctypes.windll.kernel32
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
        if not handle:
            return False
        try:
            return kernel.WaitForSingleObject(handle, 0) == 0x102  # WAIT_TIMEOUT
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _active_busy(store):
    """Gọi khi đã giữ dispatch; marker chỉ che khe hở lúc worker đang khởi động."""
    try:
        with writer_lock(store.root / 'worker'):
            active = store.root / 'active.json'
            if not active.exists():
                return False
            marker = json.loads(active.read_text(encoding='utf-8'))
            # Worker có tối đa 10 giây chờ dispatch; sau 30 giây không có khóa thì đã treo.
            if time.time() - marker.get('started_at', 0) < 30 and _pid_alive(marker.get('worker_pid')):
                return True
            record = store.read(marker['id'])
            if record['trang_thai'] == 'dang_chay' and record.get('run_id') == marker['run_id']:
                store.transition(record['id'], record['revision'], 'loi', 'he_thong',
                    'worker dừng bất thường', thong_bao='worker dừng bất thường')
            active.unlink(missing_ok=True)
            return False
    except OSError:
        return True


def _finish_worker(store, request_id, run_id):
    """Dọn marker khi worker kết thúc; giữ lại nếu chưa thể đối soát trạng thái."""
    active = store.root / 'active.json'
    try:
        if not active.exists():
            return
        marker = json.loads(active.read_text(encoding='utf-8'))
        if marker.get('id') != request_id or marker.get('run_id') != run_id:
            return
        record = store.read(request_id)
        if record['trang_thai'] == 'dang_chay' and record.get('run_id') == run_id:
            store.transition(request_id, record['revision'], 'loi', 'he_thong',
                'worker dừng bất thường', thong_bao='worker dừng bất thường')
        active.unlink(missing_ok=True)
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        # busy_reason sẽ đối soát lại khi khóa OS đã được nhả.
        pass


def _busy_reason_locked(store):
    if _active_busy(store):
        return 'Đang có một lượt nhập dữ liệu chạy hoặc công bố; chờ lượt đó hoàn tất.'
    try:
        with writer_lock(store.base / PIPELINE_ROOT):
            pass
    except OSError:
        return 'writer.lock đang được lượt khác giữ; chờ lượt đó hoàn tất.'
    return ''


def busy_reason(store):
    try:
        with dispatch_lock(store):
            return _busy_reason_locked(store)
    except ValueError:
        return 'Đang có một phiên xử lý yêu cầu; chờ lượt đó hoàn tất.'


def context_path(store, run_id):
    return store.base / PIPELINE_ROOT / 'runs' / run_id / 'context.json'


def read_context(store, run_id):
    return json.loads(context_path(store, run_id).read_text(encoding='utf-8'))


def save_context(store, record, context):
    folder = store.folder(record['id']) / 'chay'
    atomic_json(folder / 'context.json', context)
    if context['stage'] == 'published':
        atomic_json(folder / 'published.context.json', context)
    atomic_json(folder / f"{record['run_id']}.context.json", context)


@contextmanager
def dispatch_lock(store):
    lock = writer_lock(store.root / 'dispatch')
    try:
        lock.__enter__()
    except OSError as error:
        raise ValueError('Trạng thái đã đổi; phiên khác đang xử lý, vui lòng tải lại.') from error
    try:
        yield
    finally:
        lock.__exit__(None, None, None)


@contextmanager
def worker_slot(store):
    """Đợi khóa ngắn do fragment/phiên khác đang kiểm tra; không để worker chết oan."""
    for attempt in range(100):
        lock = writer_lock(store.root / 'worker')
        try:
            lock.__enter__()
        except OSError as error:
            if attempt == 99:
                raise RuntimeError('Không lấy được khóa worker sau 10 giây.') from error
            time.sleep(0.1)
        else:
            break
    try:
        yield
    finally:
        lock.__exit__(None, None, None)


def start(store, request_id, revision):
    username, audit = actor('chay')
    with dispatch_lock(store):
        reason = _busy_reason_locked(store)
        if reason:
            raise ValueError(reason)
        with store.locked(request_id, revision) as record:
            if record['trang_thai'] not in ('da_duyet', 'loi', 'da_cong_bo'):
                raise ValueError('Trạng thái đã đổi; yêu cầu chưa thể chạy.')
            if not has_dbt_model(record['ten_mo_rong'], store.base / 'retail_dbt/models'):
                raise ValueError('Cần DE viết model dbt trước khi chạy.')
            run_number = record.get('lan_chay', 0) + 1
            run_id = f'ui-{request_id}-{run_number}'
            folder = store.folder(request_id) / 'chay'
            folder.mkdir(exist_ok=True)
            audit.log(username, 'nhap_chay', {'id': request_id, 'run_id': run_id})
            before = record['trang_thai']
            store.change(record, 'dang_chay', username, run_id=run_id, lan_chay=run_number,
                         truoc_chay=before, bat_dau=utc(), stage='prepare', thong_bao='', nguoi_chay=username)
            active = store.root / 'active.json'
            atomic_json(active, {'id': request_id, 'run_id': run_id, 'started_at': time.time()})
            options = {'creationflags': subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS} if os.name == 'nt' else {'start_new_session': True}
            try:
                with (folder / f'{run_id}.log').open('ab') as output:
                    process = subprocess.Popen([sys.executable, '-m', 'apps.retail_app.ui.nhap_runner', request_id, run_id],
                        cwd=store.base, env={**os.environ, 'PYTHONUTF8': '1'}, stdin=subprocess.DEVNULL,
                        stdout=output, stderr=subprocess.STDOUT, close_fds=True, **options)
                record['worker_pid'] = process.pid
                store.save(record)
                atomic_json(active, {'id': request_id, 'run_id': run_id,
                                     'started_at': time.time(), 'worker_pid': process.pid})
            except Exception as error:
                (store.root / 'active.json').unlink(missing_ok=True)
                store.change(record, 'loi', username, str(error), thong_bao=str(error))
                raise
    return record


def _stage(store, record, stage, output):
    cmd = lenh(stage, record['run_id'], record['ten_mo_rong'], store.folder(record['id']) / 'hop_dong')
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    result = subprocess.run(cmd, cwd=store.base, env={**os.environ, 'PYTHONUTF8': '1'},
                            stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT, timeout=3600, **options)
    if result.returncode:
        # Log chỉ cho DE/Admin; lấy đuôi để có lỗi CLI, không đưa mẫu dữ liệu vào trang người gửi.
        output.flush()
        log = store.folder(record['id']) / 'chay' / f"{record['run_id']}.log"
        with log.open('rb') as stream:
            stream.seek(max(0, log.stat().st_size - 4000))
            tail = stream.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'Stage {stage} thất bại (mã {result.returncode}). ' + tail)
    context = read_context(store, record['run_id'])
    if context['target'] != 'duckdb':
        raise ValueError('Context không phải DuckDB local.')
    save_context(store, record, context)
    return context


def run_worker(store, request_id, run_id):
    with worker_slot(store):
        try:
            # Chờ thao tác tạo worker ghi xong PID rồi mới lấy revision mới nhất.
            for attempt in range(100):
                try:
                    with writer_lock(store.root / 'dispatch'):
                        record = store.read(request_id)
                    break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError('Không lấy được khóa khởi động worker.')
            if record['trang_thai'] != 'dang_chay' or record['run_id'] != run_id:
                raise ValueError('Lượt chạy không còn hiệu lực.')
            username = record['nguoi_chay']
            log = store.folder(request_id) / 'chay' / f'{run_id}.log'
            try:
                with log.open('ab') as output:
                    for stage in STAGES:
                        with store.locked(request_id, record['revision']) as record:
                            record['stage'] = stage
                            store.save(record)
                        context = _stage(store, record, stage, output)
                        if context['stage'] == 'skipped':
                            if record['truoc_chay'] != 'da_cong_bo':
                                raise ValueError('Pipeline bỏ qua nhưng yêu cầu chưa có bản công bố để giữ lại.')
                            return store.transition(request_id, record['revision'], 'da_cong_bo', username,
                                'Không có gì mới, bỏ qua', thong_bao='Không có gì mới, bỏ qua')
                return store.transition(request_id, record['revision'], 'da_kiem', username)
            except Exception as error:
                return store.transition(request_id, record['revision'], 'loi', username, str(error), thong_bao=str(error))
        finally:
            _finish_worker(store, request_id, run_id)


def publish(store, request_id, revision):
    username, audit = actor('cong_bo')
    with dispatch_lock(store):
        reason = _busy_reason_locked(store)
        if reason:
            raise ValueError(reason)
        with store.locked(request_id, revision) as record:
            if record['trang_thai'] != 'da_kiem':
                raise ValueError('Trạng thái đã đổi; phải kiểm tra thành công trước công bố.')
            audit.log(username, 'nhap_cong_bo', {'id': request_id, 'run_id': record['run_id']})
            log = store.folder(request_id) / 'chay' / f"{record['run_id']}.log"
            with log.open('ab') as output:
                context = _stage(store, record, 'publish', output)
            if context['stage'] != 'published':
                raise ValueError('Pipeline chưa xác nhận công bố.')
            return store.change(record, 'da_cong_bo', username, thong_bao='Đã cập nhật bản dữ liệu local.')


def summary(store, record):
    context = json.loads((store.folder(record['id']) / 'chay/context.json').read_text(encoding='utf-8'))
    if context['stage'] == 'skipped':
        context = json.loads((store.folder(record['id']) / 'chay/published.context.json').read_text(encoding='utf-8'))
    result = {k: context.get(k) for k in ('release_id', 'snapshot_id', 'so_dong_cach_ly', 'quality')}
    if record['ten_mo_rong'] == 'orders_enriched' and context['stage'] in ('validated', 'published'):
        import duckdb
        rid = context['release_id']
        if not re.fullmatch(r'[a-f0-9]{24}', rid):
            raise ValueError('release_id không hợp lệ.')
        expected = store.base / PIPELINE_ROOT / 'runs' / context['run_id'] / 'dbt.duckdb'
        if Path(context['duckdb_path']).resolve() != expected.resolve():
            raise ValueError('Đường dẫn kho không thuộc lượt nhập này.')
        with duckdb.connect(str(expected), read_only=True) as con:
            result['dim_sales_employee'] = con.execute(f'select count(*) from r_{rid}_marts.dim_sales_employee').fetchone()[0]
            result['orders_with_employee'] = con.execute(
                f'select count(*) from r_{rid}_marts.fact_order where sales_employee_sk is not null').fetchone()[0]
    return result


def elapsed(record):
    return max(0, int((datetime.now(timezone.utc) - datetime.fromisoformat(record['bat_dau'])).total_seconds()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request_id')
    parser.add_argument('run_id')
    args = parser.parse_args()
    run_worker(RequestStore(), args.request_id, args.run_id)
