"""Yêu cầu nhập local: file bất biến, khóa liên tiến trình và cập nhật nguyên tử."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
import uuid

from scripts.pipeline.state import atomic_json, writer_lock

ROOT = Path(__file__).resolve().parents[3]
MAX_BYTES = 200 * 1024 * 1024
TRANSITIONS = {
    'da_gui': {'cho_duyet', 'loi_de_xuat'},
    'cho_duyet': {'da_duyet', 'cho_model_dbt', 'tu_choi'},
    'da_duyet': {'dang_chay', 'loi'}, 'dang_chay': {'da_kiem', 'loi', 'da_cong_bo'},
    'loi': {'dang_chay', 'cho_duyet'}, 'da_kiem': {'da_cong_bo', 'loi'}, 'da_cong_bo': {'dang_chay', 'loi'},
    'cho_model_dbt': set(), 'tu_choi': set(), 'loi_de_xuat': set(),
}
LABELS = {'da_gui': 'Đã gửi', 'cho_duyet': 'Chờ duyệt', 'loi_de_xuat': 'Không đọc được file',
          'da_duyet': 'Đã duyệt', 'cho_model_dbt': 'Chờ model dbt', 'tu_choi': 'Từ chối',
          'dang_chay': 'Đang chạy', 'da_kiem': 'Đã kiểm tra', 'loi': 'Lỗi khi chạy', 'da_cong_bo': 'Đã cập nhật'}


def utc():
    return datetime.now(timezone.utc).isoformat()


class RequestBusyError(ValueError):
    """Chưa lấy được khóa yêu cầu; hàng đợi phải giữ mục để thử lại."""


class FileBusyError(PermissionError):
    """Đã hết hạn thử đọc; không lồng thêm một lượt chờ ở hàng đợi."""


def read_json(path):
    for attempt in range(100):
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except PermissionError as error:
            if attempt == 99:
                raise FileBusyError(str(error)) from error
            time.sleep(0.1)


@contextmanager
def retry_lock(path):
    """Chờ tối đa 10 giây cho khóa OS; chỉ thử lại lúc lấy khóa."""
    for attempt in range(100):
        lock = writer_lock(path)
        try:
            lock.__enter__()
        except OSError:
            if attempt == 99:
                raise
            time.sleep(0.1)
        else:
            break
    try:
        yield
    finally:
        lock.__exit__(None, None, None)


def actor(action):
    """Kiểm quyền ở biên thao tác, kể cả admin đang xem như role thấp hơn."""
    from ui import roles
    role = roles.current_role()
    page = 'gui_du_lieu' if action == 'gui' else 'duyet_du_lieu'
    if not roles.allowed(role, page) or (action == 'cong_bo' and role != 'admin'):
        raise PermissionError('Bạn không có quyền thực hiện thao tác này.')
    user, audit = roles.logged_in_user(), roles.store()
    if not user or audit is None:
        raise PermissionError('Cần đăng nhập và kết nối kho nhật ký để thực hiện thao tác.')
    return user['username'], audit


def safe_filename(name):
    name = str(name).replace('\\', '/').rsplit('/', 1)[-1].lower()
    if Path(name).suffix not in ('.csv', '.json'):
        raise ValueError('Chỉ nhận một file CSV hoặc JSON.')
    name = re.sub(r'[^a-z0-9_.-]', '_', name).lstrip('.')
    if not name or len(name) > 150 or name.split('.')[0] in {
        'con', 'prn', 'aux', 'nul', *('com' + str(i) for i in range(1, 10)),
        *('lpt' + str(i) for i in range(1, 10))}:
        raise ValueError('Tên file không hợp lệ.')
    return name


def nhap_kha_dung(base=ROOT):
    """Kiểm tra khả năng nhập tại máy mà không tạo file hay import duckdb."""
    import importlib.util
    from scripts.ingest.source_contract import SOURCES

    if importlib.util.find_spec('duckdb') is None:
        return False
    data = Path(base) / 'data'
    return all((data / f'{name}.csv').is_file() for name in SOURCES)


class RequestStore:
    def __init__(self, base=ROOT):
        self.base = Path(base).resolve()
        self.root = self.base / 'warehouse/ui_nhap'
        self.requests = self.root / 'yeu_cau'

    def queue_files(self):
        return sorted((self.root / 'hang_doi').glob('*.json'))

    def queue_add(self, record):
        name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ_') + record['id'] + '_' + uuid.uuid4().hex
        atomic_json(self.root / 'hang_doi' / (name + '.json'), {'id': record['id'], 'luc': utc()})

    def pipeline_state(self):
        path = self.base / 'warehouse/pipeline/ui-nhap/state.json'
        return read_json(path)['payload'] if path.exists() else {}

    def folder(self, request_id):
        if not re.fullmatch(r'[0-9]{8}T[0-9]{6}Z_[a-f0-9]{6}', request_id):
            raise ValueError('Mã yêu cầu không hợp lệ.')
        return self.requests / request_id

    def read(self, request_id):
        return read_json(self.folder(request_id) / 'yeu_cau.json')

    @contextmanager
    def locked(self, request_id, revision):
        lock = writer_lock(self.folder(request_id))
        try:
            lock.__enter__()
        except (PermissionError, BlockingIOError) as error:
            raise RequestBusyError('Yêu cầu đang được xử lý; trạng thái đã đổi, vui lòng tải lại.') from error
        try:
            record = self.read(request_id)
            if record['revision'] != revision:
                raise ValueError('Trạng thái đã đổi; tải lại yêu cầu.')
            yield record
        finally:
            lock.__exit__(None, None, None)

    def save(self, record):
        saved = {**record, 'revision': record['revision'] + 1}
        atomic_json(self.folder(record['id']) / 'yeu_cau.json', saved)
        record.update(saved)
        return record

    def change(self, record, state, username, note='', **updates):
        before = record['trang_thai']
        if state not in TRANSITIONS[before]:
            raise ValueError(f'Chuyển trạng thái không hợp lệ: {before} → {state}')
        record['lich_su'].append({'luc': utc(), 'ai': username, 'tu': before, 'toi': state, 'ghi_chu': note})
        record.update(updates, trang_thai=state)
        return self.save(record)

    def transition(self, request_id, revision, state, username, note='', **updates):
        with self.locked(request_id, revision) as record:
            return self.change(record, state, username, note, **updates)

    def visible(self, username, role):
        if role not in ('quan_ly', 'phan_tich', 'ky_su', 'admin'):
            return []
        rows = [self.read(p.parent.name) for p in self.requests.glob('*/yeu_cau.json')]
        return sorted((r for r in rows if role in ('ky_su', 'admin') or r['nguoi_gui'] == username),
                      key=lambda r: r['ngay_gui'], reverse=True)

    def column_status(self, record):
        """Một cách xét đề xuất cột cho cả hai trang; chỉ đọc kho hợp đồng."""
        import yaml
        from scripts.ingest.contract_registry import ContractRegistry
        from scripts.ingest.adapters import normalize
        columns = record.get('cot_moi') or []
        contract = record.get('hop_dong') or {}
        if not columns or not contract or record.get('duong') != 'tu_dong':
            return None
        folder = ContractRegistry(self.base).folder(contract['ten'])
        pointer = folder / 'hien_hanh.json'
        if not pointer.exists():
            return None
        version = read_json(pointer)['phien_ban']
        wanted = {normalize(column) for column in columns}
        known = set()
        for number in range(contract['phien_ban'], version + 1):
            doc = yaml.safe_load((folder / f'v{number}.yml').read_text(encoding='utf-8'))
            known = {normalize(column) for column in doc['header']}
            if wanted <= known:
                return {'state': 'approved', 'version': number, 'columns': columns}
        rejected = folder / 'tu_choi.json'
        if rejected.exists():
            for decision in read_json(rejected):
                if {normalize(column) for column in decision['cot']} == wanted:
                    return {'state': 'rejected', 'columns': columns, 'reason': decision['ly_do']}
        if version != contract['phien_ban']:
            return {'state': 'expired', 'version': version,
                    'columns': [column for column in columns if normalize(column) not in known]}
        return {'state': 'pending', 'columns': columns}

    def pending_columns(self, record):
        status = self.column_status(record)
        return bool(status and status['state'] == 'pending')

    def column_notice(self, record, visible_rows):
        """Tóm tắt quyết định cột cho người gửi, không đưa thông tin kỹ thuật ra trang."""
        import yaml
        from scripts.ingest.contract_registry import ContractRegistry
        from scripts.ingest.adapters import normalize
        contract = record.get('hop_dong') or {}
        if not contract or not (record.get('cot_moi') or record.get('nap_bu_tu')):
            return ''
        folder = ContractRegistry(self.base).folder(contract['ten'])
        version = contract['phien_ban']

        def header(number):
            path = folder / f'v{number}.yml'
            return yaml.safe_load(path.read_text(encoding='utf-8'))['header'] if path.exists() else []

        if record.get('nap_bu_tu'):
            previous = {normalize(c) for c in header(version - 1)}
            columns = [c for c in header(version) if normalize(c) not in previous]
            return 'Nạp bù sau nâng hợp đồng v' + str(version) + ': ' + ', '.join(columns) + '.'
        status = self.column_status(record)
        if status is None:
            return ''
        names = ', '.join(status['columns'])
        if status['state'] == 'approved':
            number = status['version']
            backfills = [r['id'] for r in visible_rows if r.get('nap_bu_tu') == record['id']
                         or (r.get('nap_bu_tu')
                             and r.get('hop_dong', {}).get('ten') == contract['ten']
                             and r.get('hop_dong', {}).get('phien_ban') == number)]
            detail = ('Yêu cầu nạp bù: ' + ', '.join(backfills) + '.') if backfills else 'Có hiệu lực từ lần gửi sau.'
            return f'Cột {names} đã duyệt trong hợp đồng v{number}. {detail}'
        if status['state'] == 'rejected':
            return f"Không nhận cột {names}: {status['reason']}"
        if status['state'] == 'expired':
            return f"Hợp đồng đã lên v{status['version']}, cột {names} chưa được xét. Gửi lại file để đề xuất."
        return f'Cột {names} chờ đội dữ liệu duyệt; phần đã có vẫn được cập nhật.'

    def release_requests(self):
        """Tra yêu cầu đã công bố để gắn nhãn bản khôi phục; chỉ đọc kho nhập."""
        result = {}
        for path in self.requests.glob('*/yeu_cau.json'):
            row = self.read(path.parent.name)
            context = self.folder(row['id']) / 'chay/published.context.json'
            if not context.exists():
                continue
            release = read_json(context).get('release_id')
            times = [step['luc'] for step in row['lich_su'] if step['toi'] == 'da_cong_bo']
            published = max(times, default='')
            if release and published >= result.get(release, {}).get('published', ''):
                result[release] = {'published': published, 'record': row}
        return result

    def create(self, upload, description, username):
        """Lưu từng khối, kiểm kích thước thật; không tin metadata của trình duyệt."""
        name = safe_filename(upload.name)
        if getattr(upload, 'size', 0) > MAX_BYTES:
            raise ValueError('File vượt giới hạn 200 MB.')
        request_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_') + uuid.uuid4().hex[:6]
        folder = self.folder(request_id)
        folder.mkdir(parents=True, exist_ok=False)
        data = self.base / 'data/ui_nhap' / request_id
        data.mkdir(parents=True, exist_ok=False)
        temp = data / 'upload.tmp'
        digest, size = hashlib.sha256(), 0
        try:
            upload.seek(0)
            with temp.open('xb') as output:
                while chunk := upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise ValueError('File vượt giới hạn 200 MB.')
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temp, data / name)
        except Exception:
            temp.unlink(missing_ok=True)
            raise
        record = {'id': request_id, 'nguoi_gui': username, 'ngay_gui': utc(), 'mo_ta': description,
                  'ten_file': name, 'sha256': digest.hexdigest(), 'so_byte': size,
                  'trang_thai': 'da_gui', 'revision': 0,
                  'lich_su': [{'luc': utc(), 'ai': username, 'tu': None, 'toi': 'da_gui', 'ghi_chu': 'Gửi file'}]}
        atomic_json(folder / 'yeu_cau.json', record)
        return record

    def submit(self, upload, description):
        username, audit = actor('gui')
        record = self.create(upload, description, username)
        return self._process_submission(record, username, audit)

    def _process_submission(self, record, username, audit=None, *, enqueue=True):
        from scripts.ingest import auto_mapping, approval
        from scripts.ingest.contract_registry import ContractRegistry
        from scripts.ingest.tu_dong import phan_loai

        try:
            if audit is not None:
                audit.log(username, 'nhap_gui', {'id': record['id'], 'sha256': record['sha256']})
            elif username == 'he_thong':
                self.log_event(username, 'nhap_gui', {'id': record['id'], 'sha256': record['sha256']})
            proposal = auto_mapping.propose(self.base / 'data/ui_nhap' / record['id'] / record['ten_file'], self.base / 'data')
            auto_mapping.write_proposal(proposal, self.folder(record['id']) / 'de_xuat')
        except Exception as error:
            return self.transition(record['id'], record['revision'], 'loi_de_xuat', username,
                'Chưa đọc được file hoặc chưa ghi được nhật ký. Kiểm tra định dạng CSV/JSON và mã hóa UTF-8; liên hệ đội dữ liệu nếu vẫn lỗi.',
                loi_ky_thuat=f'{type(error).__name__}: {error}')
        registry = ContractRegistry(self.base)
        try:
            candidates = registry.ung_vien(proposal)
        except (OSError, ValueError) as error:
            reason = {'ma': 'hop_dong_khong_hop_le',
                      'nghiep_vu': 'Hợp đồng cần đội dữ liệu kiểm tra.', 'ky_thuat': str(error)}
            result = {'ket_qua': 'can_nguoi', 'ten': None, 'phien_ban': None,
                      'cot_moi': [], 'ly_do': [reason]}
            return self.transition(record['id'], record['revision'], 'cho_duyet', username,
                                   phan_loai=result, duong='tay', ly_do=result['ly_do'])
        complete = [candidate for candidate in candidates if not candidate[3]]
        model = len(complete) == 1 and approval.has_dbt_model(complete[0][0], self.base / 'retail_dbt/models')
        result = phan_loai(proposal, candidates, model)
        record = self.transition(record['id'], record['revision'], 'cho_duyet', username,
                                 phan_loai=result, duong='tu_dong' if result['ket_qua'] == 'tu_dong' else 'tay',
                                 ly_do=result['ly_do'])
        if result['ket_qua'] != 'tu_dong':
            return record
        try:
            record = self.auto_approve(record['id'], record['revision'])
        except ValueError as error:
            reason = {'ma': 'hop_dong_khong_hop_le',
                      'nghiep_vu': 'Hợp đồng cần đội dữ liệu kiểm tra.', 'ky_thuat': str(error)}
            with self.locked(record['id'], record['revision']) as current:
                current['phan_loai']['ket_qua'] = 'can_nguoi'
                current['phan_loai']['ly_do'].append(reason)
                current.update(duong='tay', ly_do=current['phan_loai']['ly_do'])
                return self.save(current)
        from ui import nhap_runner
        if enqueue:
            nhap_runner.enqueue(self, record['id'])
        return self.read(record['id'])

    def auto_approve(self, request_id, revision):
        """Chỉ cho phép yêu cầu đã được submit phân loại tự động."""
        import yaml
        from scripts.ingest import extension_contract
        from scripts.ingest.contract_registry import ContractRegistry
        from scripts.ingest.tu_dong import hop_dong_cua_luot

        with self.locked(request_id, revision) as record:
            result = record.get('phan_loai') or {}
            if (record['trang_thai'] != 'cho_duyet' or result.get('ket_qua') != 'tu_dong'
                    or record.get('duong') != 'tu_dong'):
                raise ValueError('Yêu cầu này không thuộc đường tự động.')
            name = result['ten']
            current = ContractRegistry(self.base).current(name)
            if current is None or current[0]['phien_ban'] != result['phien_ban']:
                raise ValueError('Hợp đồng hiện hành đã thay đổi; cần duyệt lại.')
            meta, approved = current
            header = [col['ten_trong_file'] for col in self.proposal(request_id)['cot']]
            doc = hop_dong_cua_luot(approved, header, f"ui_nhap/{request_id}/{record['ten_file']}",
                                    meta['phien_ban'], utc())
            folder = self.folder(request_id) / 'hop_dong'
            folder.mkdir(exist_ok=True)
            with tempfile.TemporaryDirectory(dir=self.root) as temporary:
                candidate = Path(temporary) / f'{name}.yml'
                candidate.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding='utf-8')
                extension_contract.load(name, temporary)
                os.replace(candidate, folder / f'{name}.yml')
            self.log_event('he_thong', 'nhap_tu_duyet', {'id': request_id, 'ten': name, 'phien_ban': meta['phien_ban']})
            return self.change(record, 'da_duyet', 'he_thong', ten_mo_rong=name,
                               duong='tu_dong', hop_dong={'ten': name, 'phien_ban': meta['phien_ban'],
                                                         'sha256': meta['sha256']}, cot_moi=result['cot_moi'])

    def proposal(self, request_id):
        import yaml
        return yaml.safe_load((self.folder(request_id) / 'de_xuat/mapping_de_xuat.yml').read_text(encoding='utf-8'))

    def approve(self, request_id, revision, decisions, name):
        import yaml
        from scripts.ingest import approval, extension_contract
        from scripts.ingest.contract_registry import ContractRegistry

        username, audit = actor('duyet')
        with self.locked(request_id, revision) as record:
            if record['trang_thai'] != 'cho_duyet':
                raise ValueError('Trạng thái đã đổi; yêu cầu không còn chờ duyệt.')
            if not re.fullmatch(r'[a-z][a-z0-9_]*', name):
                raise ValueError('Tên phần mở rộng phải theo [a-z][a-z0-9_]*.')
            doc = approval.hop_dong_tu_de_xuat(self.proposal(request_id), decisions, name,
                f"ui_nhap/{request_id}/{record['ten_file']}", username, utc())
            folder = self.folder(request_id) / 'hop_dong'
            folder.mkdir(exist_ok=True)
            # Kiểm trên bản tạm; hợp đồng sai không được lưu vào thư mục đã duyệt.
            with tempfile.TemporaryDirectory(dir=self.root) as temporary:
                candidate = Path(temporary) / f'{name}.yml'
                candidate.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding='utf-8')
                extension_contract.load(name, temporary)
                audit.log(username, 'nhap_duyet', {'id': request_id, 'ten': name})
                os.replace(candidate, folder / f'{name}.yml')
            registry = ContractRegistry(self.base)
            if registry.current(name) is None:
                registry.write(name, doc, username, f'yeu_cau:{request_id}')
            state = 'da_duyet' if approval.has_dbt_model(name, self.base / 'retail_dbt/models') else 'cho_model_dbt'
            record.pop('hop_dong', None)
            record.pop('cot_moi', None)
            return self.change(record, state, username, ten_mo_rong=name, duong='tay')

    def retry_review(self, request_id, revision, reason):
        username, audit = actor('duyet')
        if not reason.strip():
            raise ValueError('Duyệt lại phải ghi lý do.')
        with self.locked(request_id, revision) as record:
            if record['trang_thai'] != 'loi':
                raise ValueError('Yêu cầu không ở trạng thái lỗi.')
            detail = {'id': request_id, 'ly_do': reason.strip()}
            if record.get('hop_dong'):
                detail.update(ten=record['hop_dong']['ten'], phien_ban=record['hop_dong']['phien_ban'])
            audit.log(username, 'nhap_duyet_lai', detail)
            return self.change(record, 'cho_duyet', username, reason.strip(), duong='tay')

    def log_event(self, username, event, detail):
        """Worker không có phiên Streamlit vẫn để lại nhật ký khi Neon vắng mặt."""
        from ui import roles
        try:
            audit = roles.store()
            if audit is None:
                raise RuntimeError('Kho nhật ký chưa khả dụng.')
            audit.log(username, event, detail)
        except Exception:
            line = json.dumps({'ai': username, 'su_kien': event, 'detail': detail}, ensure_ascii=False)
            self.root.mkdir(parents=True, exist_ok=True)
            with retry_lock(self.root / 'nhat_ky_cho'):
                with (self.root / 'nhat_ky_cho.jsonl').open('a', encoding='utf-8') as output:
                    output.write(line + '\n')
                    output.flush()
                    os.fsync(output.fileno())

    def sync_events(self):
        from ui import roles
        path = self.root / 'nhat_ky_cho.jsonl'
        if not path.exists():
            return 0
        audit = roles.store()
        # Chỉ tuần tự hóa các lần đồng bộ; worker vẫn ghi được khi Neon chậm.
        with retry_lock(self.root / 'nhat_ky_dong_bo'):
            with retry_lock(self.root / 'nhat_ky_cho'):
                rows = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
            if audit is None:
                return len(rows)
            sent = 0
            for line in rows:
                row = json.loads(line)
                try:
                    audit.log(row['ai'], row['su_kien'], row['detail'])
                except Exception:
                    break
                sent += 1
            with retry_lock(self.root / 'nhat_ky_cho'):
                current = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
                if current[:len(rows)] != rows:
                    raise ValueError('Nhật ký chờ đã đổi trong lúc đồng bộ; giữ lại để kiểm tra.')
                remaining = current[sent:]
                if remaining:
                    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.root, delete=False) as output:
                        output.write('\n'.join(remaining) + '\n')
                        output.flush()
                        os.fsync(output.fileno())
                        temp_path = output.name
                    os.replace(temp_path, path)
                else:
                    path.unlink(missing_ok=True)
                return len(remaining)

    def pending_upgrades(self):
        rows = []
        for path in self.requests.glob('*/yeu_cau.json'):
            record = self.read(path.parent.name)
            status = self.column_status(record)
            if status and status['state'] == 'pending':
                rows.append(record)
        return sorted(rows, key=lambda row: row['ngay_gui'], reverse=True)

    def mart_column_available(self, name, column):
        from scripts.ingest.approval import has_dbt_column
        return has_dbt_column(name, column, self.base / 'retail_dbt/models')

    def _active_published(self, name):
        active = self.pipeline_state().get('active')
        if not active:
            return None
        published = []
        for path in self.requests.glob('*/yeu_cau.json'):
            record = self.read(path.parent.name)
            if record.get('ten_mo_rong') != name:
                continue
            context_path = self.folder(record['id']) / 'chay/published.context.json'
            if not context_path.exists():
                continue
            context = read_json(context_path)
            if context.get('stage') != 'published' or context.get('release_id') != active:
                continue
            times = [step['luc'] for step in record['lich_su'] if step['toi'] == 'da_cong_bo']
            if times:
                published.append((times[-1], record))
        return max(published, default=(None, None), key=lambda item: item[0])[1]

    def upgrade_contract(self, request_id, decisions):
        """Giữ dispatch từ kiểm bận đến xếp hàng nạp bù, tránh chen lượt mới."""
        from ui import nhap_runner
        from scripts.ingest.contract_registry import ContractRegistry
        username, audit = actor('duyet')
        with nhap_runner.dispatch_lock(self, wait=True):
            if self.queue_files() or nhap_runner._busy_reason_locked(self):
                raise ValueError('Chờ lượt đang chạy xong rồi duyệt.')
            result = self._upgrade_locked(request_id, decisions, username, audit)
            if result['nap_bu']:
                try:
                    # enqueue có ngoại lệ ghi ngoài dispatch sau 10 giây: phải kiểm lại.
                    if self.queue_files():
                        raise ValueError('Có yêu cầu mới trong hàng đợi; không nạp lại file cũ.')
                    nhap_runner._enqueue_locked(self, result['nap_bu'])
                except Exception as error:
                    result.update(nap_bu=None,
                                  thong_bao='Cột mới có hiệu lực từ lần gửi sau: ' + str(error))
            try:
                ContractRegistry(self.base).upgrade_notice(result['ten'], result['phien_ban'], result['thong_bao'])
            except Exception as error:
                result['thong_bao'] += ' Chưa lưu được thông báo: ' + str(error)
            return result

    def _upgrade_locked(self, request_id, decisions, username, audit):
        """Nâng hợp đồng và tạo yêu cầu từ đúng bản đang phục vụ, khi đã giữ dispatch."""
        from copy import deepcopy
        import yaml
        from scripts.ingest import extension_contract
        from scripts.ingest.adapters import normalize
        from scripts.ingest.contract_registry import ContractRegistry

        record = self.read(request_id)
        columns = record.get('cot_moi') or []
        contract = record.get('hop_dong') or {}
        if record.get('duong') != 'tu_dong' or not columns or not contract:
            raise ValueError('Yêu cầu không có đề xuất nâng hợp đồng.')
        names = {normalize(col['ten']) for col in decisions}
        if names != {normalize(col) for col in columns} or len(decisions) != len(columns):
            raise ValueError('Chỉ được duyệt đúng các cột mới của đề xuất.')
        registry = ContractRegistry(self.base)
        current = registry.current(contract['ten'])
        if current is None or current[0]['phien_ban'] != contract['phien_ban']:
            raise ValueError('Phiên bản hợp đồng đã đổi; tải lại trang.')
        missing_mart = [col['ten'] for col in decisions
                        if col.get('xu_ly') == 'nap' and col.get('hien_thi') == 'mart'
                        and not self.mart_column_available(contract['ten'], col['ten'])]
        if missing_mart:
            raise ValueError('Model dbt chưa có cột ' + ', '.join(missing_mart) + '; chọn silver trước khi duyệt.')
        doc = deepcopy(current[1])
        doc.pop('hop_dong_sha256', None)
        doc['header'].extend(columns)
        doc['cot'].extend([{**column, 'trang_thai': 'da_duyet',
                            'tuy_chon': column.get('xu_ly') == 'bo' or
                            (column.get('xu_ly') == 'nap' and column.get('hien_thi') == 'silver')}
                           for column in decisions])
        doc['file'] = f"ui_nhap/{request_id}/{record['ten_file']}"
        doc['duyet_boi'] = username
        doc['ngay_duyet'] = utc()
        doc['phien_ban'] = contract['phien_ban'] + 1
        with tempfile.TemporaryDirectory(dir=self.root) as temporary:
            candidate = Path(temporary) / (contract['ten'] + '.yml')
            candidate.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding='utf-8')
            extension_contract.load(contract['ten'], temporary)
        source = self._active_published(contract['ten'])
        notice = None
        if source is None:
            notice = 'Cột mới có hiệu lực từ lần gửi sau: không tìm được yêu cầu đã công bố ra bản đang phục vụ.'
        else:
            source_header = {normalize(col['ten_trong_file']) for col in self.proposal(source['id'])['cot']}
            missing = [col for col in columns if normalize(col) not in source_header]
            if missing:
                notice = 'Cột mới có hiệu lực từ lần gửi sau: file của bản đang phục vụ thiếu ' + ', '.join(missing) + '.'
            origin = self.base / 'data/ui_nhap' / source['id'] / source['ten_file']
            digest = hashlib.sha256()
            with origin.open('rb') as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
            if digest.hexdigest() != source['sha256']:
                raise ValueError('File nguồn đã công bố không khớp sha256 đã lưu.')
        audit.log(username, 'nhap_nang_hop_dong',
                  {'id': request_id, 'ten': contract['ten'], 'phien_ban': doc['phien_ban']})
        meta, _ = registry.write(contract['ten'], doc, username, f'nang_hop_dong:{request_id}',
                                 expected=contract['phien_ban'])
        outcome = {'ten': contract['ten'], 'phien_ban': meta['phien_ban'], 'thong_bao': notice, 'nap_bu': None}
        if notice:
            return outcome
        try:
            if self.queue_files():
                raise ValueError('Có yêu cầu mới trong hàng đợi; không nạp lại file cũ.')
            with origin.open('rb') as upload:
                new_record = self.create(upload, 'Nạp bù sau nâng hợp đồng', source['nguoi_gui'])
            if new_record['sha256'] != source['sha256']:
                raise ValueError('File nạp bù không khớp sha256 của yêu cầu đã công bố.')
            new_record['nap_bu_tu'] = source['id']
            new_record['lich_su'][0]['ai'] = 'he_thong'
            self.save(new_record)
            result = self._process_submission(new_record, 'he_thong', enqueue=False)
            outcome['nap_bu'] = result['id'] if result['trang_thai'] == 'da_duyet' else None
            if outcome['nap_bu']:
                outcome['thong_bao'] = 'Đã tạo yêu cầu nạp bù ' + result['id'] + ' từ yêu cầu đã công bố ' + source['id'] + '.'
            else:
                outcome['thong_bao'] = ('Cột mới có hiệu lực từ lần gửi sau: yêu cầu nạp bù ' +
                                       result['id'] + ' cần đội dữ liệu kiểm tra (' + result['trang_thai'] + ').')
        except Exception as error:
            outcome['thong_bao'] = 'Cột mới có hiệu lực từ lần gửi sau: không tạo được yêu cầu nạp bù. ' + str(error)
        return outcome

    def reject_upgrade(self, request_id, reason):
        from scripts.ingest.contract_registry import ContractRegistry
        username, audit = actor('duyet')
        record = self.read(request_id)
        columns = record.get('cot_moi') or []
        if record.get('duong') != 'tu_dong' or not columns:
            raise ValueError('Yêu cầu không có đề xuất nâng hợp đồng.')
        registry = ContractRegistry(self.base)
        current = registry.current(record['hop_dong']['ten'])
        if current is None or current[0]['phien_ban'] != record['hop_dong']['phien_ban']:
            raise ValueError('Phiên bản hợp đồng đã đổi; tải lại trang.')
        registry.reject(record['hop_dong']['ten'], columns, reason, username)
        audit.log(username, 'nhap_nang_hop_dong', {'id': request_id, 'ten': record['hop_dong']['ten'],
            'phien_ban': record['hop_dong']['phien_ban'], 'tu_choi': True, 'ly_do': reason.strip()})

    def reject(self, request_id, revision, reason):
        username, audit = actor('tu_choi')
        if not reason.strip():
            raise ValueError('Từ chối phải ghi lý do.')
        with self.locked(request_id, revision) as record:
            if record['trang_thai'] != 'cho_duyet':
                raise ValueError('Trạng thái đã đổi; yêu cầu không còn chờ duyệt.')
            audit.log(username, 'nhap_tu_choi', {'id': request_id, 'ly_do': reason.strip()})
            return self.change(record, 'tu_choi', username, reason.strip())
