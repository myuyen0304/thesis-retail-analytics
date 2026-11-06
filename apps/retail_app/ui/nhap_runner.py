"""Điều phối subprocess local, đọc trạng thái từ đĩa, không phụ thuộc phiên Streamlit."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
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
from ui.nhap_store import RequestStore, RequestBusyError, FileBusyError, actor, utc, retry_lock, read_json
from scripts.ingest.approval import has_dbt_model
from scripts.pipeline.state import atomic_json, writer_lock

PIPELINE_ROOT = 'warehouse/pipeline/ui-nhap'
STAGES = ('prepare', 'forecast', 'build', 'validate')


class WorkerStartError(RuntimeError):
    """Không tạo được worker; đã thử ghi lỗi, không thử mục kế ngay."""


class StartWriteError(RuntimeError):
    """Đã bắt đầu ghi khi khởi động; dừng lượt, không thử lại cả thao tác."""


class PublishedStateError(RuntimeError):
    """CLI đã công bố; lỗi lưu UI không được diễn giải thành công bố thất bại."""

    def __init__(self, error):
        super().__init__('Dữ liệu đã công bố nhưng chưa ghi được trạng thái yêu cầu. ' + str(error))


def _extension_names(names):
    if isinstance(names, str):
        names = [names]
    if (not isinstance(names, (list, tuple)) or not names
            or any(not isinstance(n, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', n) for n in names)):
        raise ValueError('Tên phần mở rộng không hợp lệ.')
    return sorted(set(names))


def lenh(stage, run_id, names, extension_dir):
    if stage not in (*STAGES, 'publish') or not re.fullmatch(r'ui-[A-Za-z0-9_-]+', run_id):
        raise ValueError('Stage hoặc run_id không hợp lệ.')
    names = _extension_names(names)
    # Giới hạn này phải còn đúng ngay cả khi hằng số bị thay đổi nhầm.
    if PIPELINE_ROOT != 'warehouse/pipeline/ui-nhap':
        raise ValueError('Root nhập dữ liệu không hợp lệ.')
    cmd = [sys.executable, '-m', 'scripts.pipeline.cli', stage, '--run-id', run_id,
           '--target', 'duckdb', '--root', PIPELINE_ROOT]
    if stage == 'prepare':
        for name in names:
            cmd += ['--extension', name]
        cmd += ['--extension-dir', str(Path(extension_dir).resolve())]
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
            marker = read_json(active)
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
        marker = read_json(active)
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
            count = len(_queue_files(store))
            if count:
                return f'Đang có {count} yêu cầu tự động trong hàng đợi.'
            return _busy_reason_locked(store)
    except ValueError:
        return 'Đang có một phiên xử lý yêu cầu; chờ lượt đó hoàn tất.'


def context_path(store, run_id):
    return store.base / PIPELINE_ROOT / 'runs' / run_id / 'context.json'


def read_context(store, run_id):
    return read_json(context_path(store, run_id))


def save_context(store, record, context):
    folder = store.folder(record['id']) / 'chay'
    atomic_json(folder / 'context.json', context)
    if context['stage'] == 'published':
        atomic_json(folder / 'published.context.json', context)
    atomic_json(folder / f"{record['run_id']}.context.json", context)


@contextmanager
def dispatch_lock(store, *, wait=False, allow_busy=False):
    lock = (retry_lock if wait else writer_lock)(store.root / 'dispatch')
    try:
        lock.__enter__()
    except OSError as error:
        if allow_busy:
            yield False
            return
        raise ValueError('Trạng thái đã đổi; phiên khác đang xử lý, vui lòng tải lại.') from error
    try:
        yield True
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


def _queue_files(store):
    return store.queue_files()


def queue_position(store, request_id):
    index = 0
    for path in _queue_files(store):
        try:
            item = read_json(path)
        except (OSError, ValueError):
            continue
        if not isinstance(item, dict) or 'id' not in item:
            continue
        index += 1
        if item['id'] == request_id:
            return index
    return None


def _active_context(store):
    """(mã bản đang xem, context của bản đó); chưa có bản đang xem thì (None, None). Chỉ đọc."""
    state = store.pipeline_state()
    active = state.get('active')
    if not active:
        return None, None
    release = state['releases'][active]
    context = read_context(store, release['run_id'])
    if context['release_id'] != active or context['target'] != 'duckdb':
        raise ValueError('Context active không khớp bản đang phục vụ.')
    if not isinstance(context.get('extensions', []), list):
        raise ValueError('Danh sách phần mở rộng của active không hợp lệ.')
    return active, context


def active_extensions(store):
    """(mã bản đang xem, tập nguồn mở rộng của bản đó). Chỉ đọc; dữ liệu hỏng thì để lỗi."""
    active, context = _active_context(store)
    return active, set(context.get('extensions', [])) if active else set()


def published_release(store, record):
    """Bản mà số trong tóm tắt của yêu cầu thuộc về; chưa công bố lần nào thì None. Chỉ đọc."""
    path = store.folder(record['id']) / 'chay/published.context.json'
    if not path.exists():
        return None
    release = read_json(path)['release_id']
    if not isinstance(release, str):
        raise ValueError('release_id không hợp lệ.')
    return release


READ_ERRORS = (OSError, ValueError, KeyError, TypeError, AttributeError)


def doi_chieu_ban(store, record):
    """Câu báo cho trang Duyệt khi số của yêu cầu không phải bản đang xem: (kiểu st, câu) hoặc None. Chỉ đọc."""
    try:
        published = published_release(store, record)
        if published is None:
            return None
        active, names = active_extensions(store)
    except READ_ERRORS:
        return 'warning', 'Chưa đối chiếu được với bản đang xem.'
    if active is None:
        return 'warning', 'Kho chưa có bản đang xem.'
    if published == active:
        return None
    x, y = published[:8], active[:8]
    if record.get('ten_mo_rong') in names:
        return 'info', f'Số dưới đây là của bản {x}. Bản đang xem là {y}, vẫn có nguồn này.'
    return 'warning', f'Số dưới đây là của bản {x}, không phải bản đang xem ({y}). Nguồn này hiện không có trong bản đang xem.'


def nguon_dang_dung(store):
    """(mã bản đang xem, tập nguồn) cho trang Gửi; đọc lỗi thì None. Chỉ đọc."""
    try:
        return active_extensions(store)
    except READ_ERRORS:
        return None


def _extensions_for_run(store, record):
    """Đọc bộ active cho lượt mới; chưa ghi gì vào hợp đồng của yêu cầu hay lượt cũ."""
    from scripts.ingest import extension_contract
    own = _extension_names([record['ten_mo_rong']])[0]
    request_directory = store.folder(record['id']) / 'hop_dong'
    try:
        active, context = _active_context(store)
        names = [own]
        directory = None
        if active:
            names = _extension_names([own, *context.get('extensions', [])])
            if set(names) != {own}:
                if not context.get('extension_dir'):
                    raise ValueError('Context active thiếu extension_dir.')
                directory = Path(context['extension_dir'])
                if not directory.is_absolute():
                    directory = store.base / directory
        copies = {}
        for name in names:
            source = request_directory if name == own else directory
            doc = extension_contract.load(name, source)
            if not (store.base / 'data' / doc['file']).is_file():
                raise ValueError(f'{name}: thiếu file dữ liệu của phần mở rộng.')
            copies[name] = (source / (name + '.yml')).read_bytes()
        return names, copies
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ValueError('Không giữ được bộ phần mở rộng đang phục vụ: ' + str(error)) from error


def _start_locked(store, request_id, revision, username, audit=None):
    """Gọi khi đã giữ dispatch; khởi động nội bộ không cần phiên đăng nhập."""

    with store.locked(request_id, revision) as record:
        if record['trang_thai'] not in ('da_duyet', 'loi', 'da_cong_bo'):
            raise ValueError('Trạng thái đã đổi; yêu cầu chưa thể chạy.')
        if not has_dbt_model(record['ten_mo_rong'], store.base / 'retail_dbt/models'):
            raise ValueError('Cần DE viết model dbt trước khi chạy.')
        try:
            names, contracts = _extensions_for_run(store, record)
        except ValueError as error:
            try:
                if record['trang_thai'] == 'loi':
                    record['thong_bao'] = str(error)
                    store.save(record)
                else:
                    store.change(record, 'loi', username, str(error), thong_bao=str(error))
            except Exception as write_error:
                raise StartWriteError('Không ghi được lỗi chuẩn bị bộ phần mở rộng: ' + str(write_error)) from write_error
            raise WorkerStartError(str(error)) from error
        run_number = record.get('lan_chay', 0) + 1
        run_id = f'ui-{request_id}-{run_number}'
        folder = store.folder(request_id) / 'chay'
        detail = {'id': request_id, 'run_id': run_id}
        if record.get('hop_dong'):
            detail.update(ten=record['hop_dong']['ten'], phien_ban=record['hop_dong']['phien_ban'])
        try:
            folder.mkdir(exist_ok=True)
            if audit is None:
                store.log_event(username, 'nhap_chay', detail)
            else:
                audit.log(username, 'nhap_chay', detail)
            before = record['trang_thai']
            # Marker chưa có PID được đối soát lại; lỗi ghi marker không được làm mất da_duyet.
            active = store.root / 'active.json'
            atomic_json(active, {'id': request_id, 'run_id': run_id, 'started_at': time.time()})
            store.change(record, 'dang_chay', username, run_id=run_id, lan_chay=run_number,
                         truoc_chay=before, bat_dau=utc(), stage='prepare', thong_bao='', nguoi_chay=username,
                         mo_rong_chay=names)
            options = {'creationflags': subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS} if os.name == 'nt' else {'start_new_session': True}
            process = None
            try:
                # lan_chay đã ghi: nếu chép lỗi, lần thử sau có run_id mới; không ghi đè lượt cũ.
                contract_directory = folder / run_id / 'hop_dong'
                contract_directory.mkdir(parents=True, exist_ok=False)
                for name, content in contracts.items():
                    with (contract_directory / (name + '.yml')).open('xb') as contract_file:
                        contract_file.write(content)
                with (folder / f'{run_id}.log').open('ab') as output:
                    process = subprocess.Popen([sys.executable, '-m', 'apps.retail_app.ui.nhap_runner', request_id, run_id],
                        cwd=store.base, env={**os.environ, 'PYTHONUTF8': '1'}, stdin=subprocess.DEVNULL,
                        stdout=output, stderr=subprocess.STDOUT, close_fds=True, **options)
                record['worker_pid'] = process.pid
                store.save(record)
                atomic_json(active, {'id': request_id, 'run_id': run_id,
                                     'started_at': time.time(), 'worker_pid': process.pid})
            except Exception as error:
                try:
                    store.change(record, 'loi', username, str(error), thong_bao=str(error))
                except Exception:
                    # Giữ marker để lần phục hồi kế đối soát yêu cầu còn dang_chay.
                    pass
                else:
                    try:
                        active.unlink(missing_ok=True)
                    except OSError:
                        pass
                if process is None:
                    raise WorkerStartError('Không khởi động được worker: ' + str(error)) from error
                raise
        except WorkerStartError:
            raise
        except Exception as error:
            raise StartWriteError('Lỗi sau khi bắt đầu ghi khởi động: ' + str(error)) from error
    return record


def start(store, request_id, revision):
    username, audit = actor('chay')
    with dispatch_lock(store):
        if cancelled_backfill(store, store.read(request_id)):
            raise ValueError('Yêu cầu nạp bù đã bị hủy, không chạy')
        count = len(_queue_files(store))
        if count:
            raise ValueError(f'Đang có {count} yêu cầu tự động trong hàng đợi.')
        reason = _busy_reason_locked(store)
        if reason:
            raise ValueError(reason)
        return _start_locked(store, request_id, revision, username, audit)


def cancelled_backfill(store, record):
    return bool(record.get('nap_bu_tu') and record.get('duong') == 'tu_dong'
                and record['trang_thai'] == 'da_duyet'
                and queue_position(store, record['id']) is None)


def _remove_queue_item(store, path):
    """File đang được đọc trên Windows có thể chưa xóa được; dọn ở lượt kế nếu hết hạn."""
    for attempt in range(100):
        try:
            path.unlink(missing_ok=True)
            return True
        except OSError as error:
            sharing = (os.name == 'nt' and isinstance(error, PermissionError)
                       and getattr(error, 'winerror', None) in (5, 32))
            if sharing and attempt < 99:
                time.sleep(0.1)
                continue
            store.log_event('he_thong', 'nhap_xep_hang',
                            {'muc': path.name, 'ly_do': 'Chưa xóa được mục hàng đợi: ' + str(error)})
            return False


def _kick_locked(store):
    if _busy_reason_locked(store):
        return None
    for path in _queue_files(store):
        deadline = time.monotonic() + 10
        for attempt in range(100):
            item = {}
            try:
                item = read_json(path)
                record = store.read(item['id'])
                record['trang_thai'], record['revision'], record['ten_mo_rong']
                if record['trang_thai'] != 'da_duyet' or record.get('duong') != 'tu_dong':
                    raise ValueError('Bỏ mục không còn được duyệt.')
                started = _start_locked(store, item['id'], record['revision'], 'he_thong')
            except WorkerStartError as error:
                _remove_queue_item(store, path)
                store.log_event('he_thong', 'nhap_xep_hang',
                                {'id': item['id'], 'muc': path.name,
                                 'ly_do': 'Bỏ mục do lỗi khởi động worker: ' + str(error)})
                return None
            except StartWriteError as error:
                store.log_event('he_thong', 'nhap_xep_hang',
                                {'id': item['id'], 'muc': path.name,
                                 'ly_do': 'Giữ mục, dừng lượt khởi động: ' + str(error)})
                return None
            except FileNotFoundError as error:
                removed = _remove_queue_item(store, path)
                store.log_event('he_thong', 'nhap_xep_hang',
                                {'muc': path.name, 'ly_do': 'Bỏ mục không đọc được yêu cầu: ' + str(error)})
                if not removed:
                    return None
                break
            except (OSError, RequestBusyError) as error:
                remaining = deadline - time.monotonic()
                if not isinstance(error, FileBusyError) and attempt < 99 and remaining > 0.1:
                    time.sleep(0.1)
                    continue
                store.log_event('he_thong', 'nhap_xep_hang',
                                {'muc': path.name, 'ly_do': 'Giữ mục do lỗi tạm thời: ' + str(error)})
                return None
            except (ValueError, KeyError, TypeError) as error:
                removed = _remove_queue_item(store, path)
                detail = {'muc': path.name, 'ly_do': 'Bỏ mục không đọc được yêu cầu: ' + str(error)}
                if isinstance(item, dict) and 'id' in item:
                    detail['id'] = item['id']
                store.log_event('he_thong', 'nhap_xep_hang', detail)
                if not removed:
                    return None
                break
            else:
                _remove_queue_item(store, path)
                return started
    return None


def recover_queue(store, *, wait=False):
    with dispatch_lock(store, wait=wait, allow_busy=True) as acquired:
        if acquired:
            return _kick_locked(store)


def enqueue(store, request_id):
    with dispatch_lock(store, wait=True, allow_busy=True) as acquired:
        return _enqueue_locked(store, request_id, kick=acquired)


def _enqueue_locked(store, request_id, *, kick=True):
    # Sau hạn chờ, chỉ ghi nguyên tử mục mới; không lấy/xóa hay khởi động ngoài khóa.
    record = store.read(request_id)
    if record['trang_thai'] != 'da_duyet' or record.get('duong') != 'tu_dong':
        raise ValueError('Chỉ yêu cầu tự động đã duyệt mới được xếp hàng.')
    store.queue_add(record)
    store.log_event('he_thong', 'nhap_xep_hang', {'id': request_id,
        'ten': record['ten_mo_rong'], 'phien_ban': record['hop_dong']['phien_ban']})
    if kick:
        return _kick_locked(store)


def _stage(store, record, stage, output):
    cmd = lenh(stage, record['run_id'], record.get('mo_rong_chay', [record['ten_mo_rong']]),
               store.folder(record['id']) / 'chay' / record['run_id'] / 'hop_dong')
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
    try:
        context = read_context(store, record['run_id'])
        if context['target'] != 'duckdb':
            raise ValueError('Context không phải DuckDB local.')
        save_context(store, record, context)
    except Exception as error:
        if stage == 'publish':
            raise PublishedStateError(error) from error
        raise
    return context


def run_worker(store, request_id, run_id):
    try:
        with worker_slot(store):
            return _run_worker_locked(store, request_id, run_id)
    finally:
        # Khóa worker đã nhả; dispatch quyết định có thể khởi động mục kế.
        try:
            recover_queue(store, wait=True)
        except (OSError, ValueError):
            pass


def _run_worker_locked(store, request_id, run_id):
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
            checked = store.transition(request_id, record['revision'], 'da_kiem', username)
            if checked.get('duong') == 'tu_dong' and checked.get('nguoi_chay') == 'he_thong':
                try:
                    return _publish_core(store, request_id, checked['revision'], 'he_thong')
                except PublishedStateError:
                    raise
                except Exception as error:
                    return store.transition(request_id, store.read(request_id)['revision'], 'loi', 'he_thong',
                                            str(error), thong_bao=str(error))
            return checked
        except PublishedStateError:
            raise
        except Exception as error:
            return store.transition(request_id, record['revision'], 'loi', username, str(error), thong_bao=str(error))
    finally:
        _finish_worker(store, request_id, run_id)


def publish_decision(record, context):
    """Quyết định trạng thái công bố không phụ thuộc đĩa hay phiên đăng nhập."""
    if record['trang_thai'] != 'da_kiem':
        raise ValueError('Trạng thái đã đổi; phải kiểm tra thành công trước công bố.')
    if context.get('stage') != 'published':
        raise ValueError('Pipeline chưa xác nhận công bố.')
    return {'trang_thai': 'da_cong_bo', 'thong_bao': 'Đã cập nhật bản dữ liệu local.'}


def _publish_core(store, request_id, revision, username, audit=None):
    with store.locked(request_id, revision) as record:
        if record['trang_thai'] != 'da_kiem':
            raise ValueError('Trạng thái đã đổi; phải kiểm tra thành công trước công bố.')
        detail = {'id': request_id, 'run_id': record['run_id']}
        if record.get('hop_dong'):
            detail.update(ten=record['hop_dong']['ten'], phien_ban=record['hop_dong']['phien_ban'])
        if audit is None:
            store.log_event(username, 'nhap_cong_bo', detail)
        else:
            audit.log(username, 'nhap_cong_bo', detail)
        log = store.folder(request_id) / 'chay' / f"{record['run_id']}.log"
        try:
            with log.open('ab') as output:
                context = _stage(store, record, 'publish', output)
            outcome = publish_decision(record, context)
            try:
                return store.change(record, outcome['trang_thai'], username, thong_bao=outcome['thong_bao'])
            except Exception as error:
                raise PublishedStateError(error) from error
        except PublishedStateError as error:
            # Đọc lại bản đã lưu, không dùng record vừa đổi trong bộ nhớ khi ghi thất bại.
            try:
                pending = store.read(request_id)
                pending['thong_bao'] = str(error)
                store.save(pending)
            except (OSError, ValueError):
                pass
            with log.open('ab') as output:
                output.write((str(error) + '\n').encode('utf-8'))
            raise


def publish(store, request_id, revision):
    username, audit = actor('cong_bo')
    with dispatch_lock(store):
        reason = _busy_reason_locked(store)
        if reason:
            raise ValueError(reason)
        return _publish_core(store, request_id, revision, username, audit)


def rollback_command(release_id, run_id):
    if not re.fullmatch(r'[a-f0-9]{24}', release_id):
        raise ValueError('Mã bản dữ liệu không hợp lệ.')
    if PIPELINE_ROOT != 'warehouse/pipeline/ui-nhap':
        raise ValueError('Root nhập dữ liệu không hợp lệ.')
    if not re.fullmatch(r'ui-rollback-[a-zA-Z0-9_-]{1,88}', run_id):
        raise ValueError('Mã lượt rollback không hợp lệ.')
    return [sys.executable, '-m', 'scripts.pipeline.cli', 'rollback', '--release-id', release_id,
            '--run-id', run_id, '--target', 'duckdb', '--root', PIPELINE_ROOT]


def rollback_details(store):
    state = store.pipeline_state()
    requests = store.release_requests()
    result = []
    for key, value in state.get('releases', {}).items():
        if not re.fullmatch(r'[a-f0-9]{24}', key) or value.get('status') != 'ready' or key == state.get('active'):
            continue
        found = requests.get(key, {})
        row = found.get('record', {})
        published = found.get('published', '')
        version = row.get('hop_dong', {}).get('phien_ban')
        display_time = (datetime.fromisoformat(published).astimezone(timezone(timedelta(hours=7))).strftime('%Y-%m-%d %H:%M')
                        if published else 'Chưa rõ giờ công bố')
        label = ' · '.join([display_time, row.get('ten_file', 'Không tìm được yêu cầu'),
                            row.get('id', '—'), f'v{version}' if version else 'Chưa rõ hợp đồng', key[:8]])
        result.append({'id': key, 'published': published, 'label': label})
    return sorted(result, key=lambda row: (row['published'], row['id']), reverse=True)


def rollback_options(store):
    return [row['id'] for row in rollback_details(store)]


def awaiting_publish(record, busy):
    return (record['trang_thai'] == 'da_kiem' and record.get('duong') == 'tu_dong'
            and record.get('nguoi_chay') == 'he_thong' and bool(busy))


def page_busy(store):
    """Chỉ quan sát worker, độc lập với hàng đợi; lỗi đọc tạm coi là còn bận."""
    active = store.root / 'active.json'
    try:
        marker = read_json(active)
    except FileNotFoundError:
        return False
    except (OSError, ValueError):
        return True
    if marker.get('worker_pid'):
        return _pid_alive(marker['worker_pid'])
    return time.time() - marker.get('started_at', 0) < 30


def page_snapshot(store, username, role):
    worker_alive = page_busy(store)
    busy = worker_alive or bool(store.queue_files())
    rows = store.visible(username, role)
    positions = {row['id']: queue_position(store, row['id']) for row in rows}
    notices = {row['id']: store.column_notice(row, rows) for row in rows}
    pending = any(row['trang_thai'] in ('da_gui', 'dang_chay') or positions[row['id']]
                  or (row['trang_thai'] in ('da_duyet', 'cho_duyet') and row.get('duong') == 'tu_dong')
                  or awaiting_publish(row, busy) for row in rows)
    waiting_columns = any(store.pending_columns(row) for row in rows)
    return {'rows': rows, 'positions': positions, 'notices': notices, 'busy': busy,
            'pending': pending, 'waiting_columns': waiting_columns, 'worker_alive': worker_alive}


def monitor_page(store, username, role, snapshot, *, notify=False, draw=None):
    """Một fragment cho cả trang; đổi dữ liệu thì rerun app trong cùng phiên đăng nhập."""
    import streamlit as st
    from ui import roles
    key = 'nhap_monitor_' + ('gui_' if notify else 'duyet_') + username

    watching = snapshot['pending'] or (notify and snapshot['waiting_columns'])

    @st.fragment(run_every='5s' if watching else None)
    def poll():
        user = roles.logged_in_user()
        if not user or user['username'] != username or roles.current_role() != role:
            st.rerun(scope='app')
        current = page_snapshot(store, username, role)
        states = {row['id']: row['trang_thai'] for row in current['rows']}
        previous = st.session_state.get(key, states)
        messages = st.session_state.pop(key + '_messages', [])
        if notify:
            for row in current['rows']:
                state = row['trang_thai']
                if row['id'] in previous and previous[row['id']] != state and state in ('da_cong_bo', 'loi'):
                    messages.append(row['ten_file'] + ': ' + ('Đã cập nhật' if state == 'da_cong_bo' else 'Lỗi'))
        st.session_state[key] = states
        if current != snapshot:
            st.session_state[key + '_messages'] = messages
            st.rerun(scope='app')
        for message in messages:
            st.toast(message)
        if draw is not None:
            draw(current)

    poll()


def rollback(store, release_id):
    username, audit = actor('cong_bo')
    with dispatch_lock(store):
        if _queue_files(store):
            raise ValueError('Đang có yêu cầu tự động trong hàng đợi.')
        reason = _busy_reason_locked(store)
        if reason:
            raise ValueError(reason)
        run_id = 'ui-rollback-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        command = rollback_command(release_id, run_id)
        audit.log(username, 'nhap_rollback', {'release_id': release_id})
        return subprocess.run(command, cwd=store.base, capture_output=True, text=True, timeout=3600,
                              env={**os.environ, 'PYTHONUTF8': '1'})


def summary(store, record):
    context = read_json(store.folder(record['id']) / 'chay/context.json')
    if context['stage'] == 'skipped':
        context = read_json(store.folder(record['id']) / 'chay/published.context.json')
    result = {k: context.get(k) for k in ('release_id', 'snapshot_id', 'so_dong_cach_ly', 'quality')}
    extensions = context.get('extensions', record.get('mo_rong_chay', [record['ten_mo_rong']]))
    if context['stage'] in ('validated', 'published') and extensions:
        import duckdb
        rid = context['release_id']
        if not re.fullmatch(r'[a-f0-9]{24}', rid):
            raise ValueError('release_id không hợp lệ.')
        expected = store.base / PIPELINE_ROOT / 'runs' / context['run_id'] / 'dbt.duckdb'
        if Path(context['duckdb_path']).resolve() != expected.resolve():
            raise ValueError('Đường dẫn kho không thuộc lượt nhập này.')
        with duckdb.connect(str(expected), read_only=True) as con:
            for name, dimension, key, count_key in (
                ('orders_enriched', 'dim_sales_employee', 'sales_employee_sk', 'orders_with_employee'),
                ('shipments_realistic', 'dim_shipper', 'shipper_sk', 'orders_with_shipper'),
            ):
                if name in extensions:
                    result[dimension] = con.execute(f'select count(*) from r_{rid}_marts.{dimension}').fetchone()[0]
                    result[count_key] = con.execute(
                        f'select count(*) from r_{rid}_marts.fact_order where {key} is not null').fetchone()[0]
    return result


def elapsed(record):
    return max(0, int((datetime.now(timezone.utc) - datetime.fromisoformat(record['bat_dau'])).total_seconds()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request_id')
    parser.add_argument('run_id')
    args = parser.parse_args()
    run_worker(RequestStore(), args.request_id, args.run_id)
