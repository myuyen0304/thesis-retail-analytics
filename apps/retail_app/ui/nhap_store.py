"""Yêu cầu nhập local: file bất biến, khóa liên tiến trình và cập nhật nguyên tử."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import uuid

import yaml

from scripts.ingest import auto_mapping, approval, extension_contract
from scripts.pipeline.state import atomic_json, writer_lock

ROOT = Path(__file__).resolve().parents[3]
MAX_BYTES = 200 * 1024 * 1024
TRANSITIONS = {
    'da_gui': {'cho_duyet', 'loi_de_xuat'},
    'cho_duyet': {'da_duyet', 'cho_model_dbt', 'tu_choi'},
    'da_duyet': {'dang_chay'}, 'dang_chay': {'da_kiem', 'loi', 'da_cong_bo'},
    'loi': {'dang_chay'}, 'da_kiem': {'da_cong_bo'}, 'da_cong_bo': {'dang_chay'},
    'cho_model_dbt': set(), 'tu_choi': set(), 'loi_de_xuat': set(),
}
LABELS = {'da_gui': 'Đã gửi', 'cho_duyet': 'Chờ duyệt', 'loi_de_xuat': 'Không đọc được file',
          'da_duyet': 'Đã duyệt', 'cho_model_dbt': 'Chờ model dbt', 'tu_choi': 'Từ chối',
          'dang_chay': 'Đang chạy', 'da_kiem': 'Đã kiểm tra', 'loi': 'Lỗi khi chạy', 'da_cong_bo': 'Đã cập nhật'}


def utc():
    return datetime.now(timezone.utc).isoformat()


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


class RequestStore:
    def __init__(self, base=ROOT):
        self.base = Path(base).resolve()
        self.root = self.base / 'warehouse/ui_nhap'
        self.requests = self.root / 'yeu_cau'

    def folder(self, request_id):
        if not re.fullmatch(r'[0-9]{8}T[0-9]{6}Z_[a-f0-9]{6}', request_id):
            raise ValueError('Mã yêu cầu không hợp lệ.')
        return self.requests / request_id

    def read(self, request_id):
        return json.loads((self.folder(request_id) / 'yeu_cau.json').read_text(encoding='utf-8'))

    @contextmanager
    def locked(self, request_id, revision):
        try:
            with writer_lock(self.folder(request_id)):
                record = self.read(request_id)
                if record['revision'] != revision:
                    raise ValueError('Trạng thái đã đổi; tải lại yêu cầu.')
                yield record
        except OSError as error:
            raise ValueError('Yêu cầu đang được xử lý; trạng thái đã đổi, vui lòng tải lại.') from error

    def save(self, record):
        record['revision'] += 1
        atomic_json(self.folder(record['id']) / 'yeu_cau.json', record)
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
        try:
            audit.log(username, 'nhap_gui', {'id': record['id'], 'sha256': record['sha256']})
            proposal = auto_mapping.propose(self.base / 'data/ui_nhap' / record['id'] / record['ten_file'], self.base / 'data')
            auto_mapping.write_proposal(proposal, self.folder(record['id']) / 'de_xuat')
        except Exception as error:
            return self.transition(record['id'], record['revision'], 'loi_de_xuat', username,
                'Chưa đọc được file hoặc chưa ghi được nhật ký. Kiểm tra định dạng CSV/JSON và mã hóa UTF-8; liên hệ đội dữ liệu nếu vẫn lỗi.',
                loi_ky_thuat=f'{type(error).__name__}: {error}')
        return self.transition(record['id'], record['revision'], 'cho_duyet', username)

    def proposal(self, request_id):
        return yaml.safe_load((self.folder(request_id) / 'de_xuat/mapping_de_xuat.yml').read_text(encoding='utf-8'))

    def approve(self, request_id, revision, decisions, name):
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
            state = 'da_duyet' if approval.has_dbt_model(name, self.base / 'retail_dbt/models') else 'cho_model_dbt'
            return self.change(record, state, username, ten_mo_rong=name)

    def reject(self, request_id, revision, reason):
        username, audit = actor('tu_choi')
        if not reason.strip():
            raise ValueError('Từ chối phải ghi lý do.')
        with self.locked(request_id, revision) as record:
            if record['trang_thai'] != 'cho_duyet':
                raise ValueError('Trạng thái đã đổi; yêu cầu không còn chờ duyệt.')
            audit.log(username, 'nhap_tu_choi', {'id': request_id, 'ly_do': reason.strip()})
            return self.change(record, 'tu_choi', username, reason.strip())
