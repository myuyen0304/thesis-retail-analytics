"""Yêu cầu đợt và lệnh dashboard: chỉ ghi kho, không chạy pipeline trên web."""
from datetime import datetime, timezone
import hashlib
import json
import re
from uuid import uuid4

from ui import roles
from ui.nhap_store import actor, safe_filename
from ui.kho_dot import KhongCo, TrangThaiDaDoi, sequence_names, relative_path

TRANSITIONS_DOT = {
    'da_gui': {'dang_kiem', 'loi_file'},
    'dang_kiem': {'cho_chay', 'sai_hop_dong', 'het_cho'},
    'het_cho': {'cho_chay'}, 'cho_chay': {'dang_chay'},
    'dang_chay': {'da_kiem', 'loi'}, 'loi': {'cho_chay', 'huy'},
    'da_kiem': {'tren_dashboard'}, 'tren_dashboard': {'da_tra'},
    'da_tra': set(), 'sai_hop_dong': set(), 'loi_file': set(), 'huy': set(),
}
LABELS_DOT = dict(zip(
    ('da_gui', 'dang_kiem', 'cho_chay', 'dang_chay', 'da_kiem', 'cho_dashboard', 'tren_dashboard',
     'da_tra', 'sai_hop_dong', 'loi_file', 'het_cho', 'loi', 'huy', 'hong'),
    ('Đã gửi', 'Đang kiểm tra file', 'Chờ chạy', 'Đang chạy', 'Đã kiểm tra', 'Chờ đưa lên dashboard',
     'Đang trên dashboard', 'Đã trả dashboard', 'Sai hợp đồng dữ liệu', 'Không đọc được file',
     'Hết chỗ lưu trữ', 'Lỗi khi chạy', 'Đã hủy', 'Dữ liệu trạng thái hỏng')))
ID_PATTERN = re.compile(r'[0-9]{8}T[0-9]{6}Z_[a-f0-9]{6}_dot')
MAX_FILE_BYTES = 200 * 1024 * 1024
MAX_TOTAL_BYTES = 100 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024


def request_path(request_id):
    if not isinstance(request_id, str) or not ID_PATTERN.fullmatch(request_id):
        raise ValueError('Mã yêu cầu đợt không hợp lệ.')
    return 'yeu_cau/' + request_id


def phat_lai(su_kien):
    """Nhận các cặp (số thứ tự, sự kiện); hỏng một bước thì không cho thao tác."""
    result = {'trang_thai': 'hong', 'lich_su': []}
    state = None
    try:
        for expected, (number, event) in enumerate(su_kien, 1):
            if number != expected:
                raise ValueError('Số thứ tự sự kiện không liền nhau từ 1.')
            target = event['toi']
            if (state is None and target != 'da_gui') or (state is not None and target not in TRANSITIONS_DOT[state]):
                raise ValueError('Bước chuyển trạng thái không hợp lệ.')
            state = target
            result['lich_su'].append(event)
            for key in ('release_id', 'ma_loi', 'thong_bao'):
                if key in event:
                    result[key] = event[key]
        if state is None:
            raise ValueError('Chưa có sự kiện đầu tiên.')
        result['trang_thai'] = state
    except (KeyError, TypeError, ValueError) as error:
        result.update(trang_thai='hong', thong_bao='Dữ liệu trạng thái hỏng: ' + str(error))
    return result


class DotStore:
    def __init__(self, kho):
        self.kho = kho

    def _json(self, path):
        return json.loads(self.kho.doc(path))

    def read(self, request_id):
        folder = request_path(request_id)
        # Sự kiện 1 là dấu công bố yêu cầu, thư mục dở dang không được nhìn thấy.
        self.kho.doc(folder + '/su_kien/000001.json')
        metadata = self._json(folder + '/yeu_cau.json')
        try:
            events = [(int(n[:-5]), self._json(folder + '/su_kien/' + n))
                      for n in sequence_names(self.kho.liet_ke(folder + '/su_kien'))]
            replay = phat_lai(events)
        except (ValueError, TypeError, KhongCo) as error:
            replay = {'trang_thai': 'hong', 'lich_su': [], 'thong_bao': 'Dữ liệu trạng thái hỏng: ' + str(error)}
        return dict(metadata, **replay)

    def visible(self, username, role):
        if role not in ('quan_ly', 'phan_tich', 'ky_su', 'admin'):
            return []
        rows = []
        for request_id in self.kho.liet_ke('yeu_cau'):
            if not ID_PATTERN.fullmatch(request_id):
                continue
            try:
                row = self.read(request_id)
                for key in ('id', 'nguoi_gui', 'ngay_gui', 'nhan'):
                    if not isinstance(row[key], str):
                        raise TypeError('Trường trạng thái không phải chuỗi.')
                if not isinstance(row['files'], list):
                    raise TypeError('Danh sách file không hợp lệ.')
                for item in row['files']:
                    if (not isinstance(item, dict) or not isinstance(item.get('ten'), str)
                            or type(item.get('so_byte')) is not int):
                        raise TypeError('Thông tin file không hợp lệ.')
            except KhongCo:
                continue
            except (ValueError, KeyError, TypeError):
                if role not in ('ky_su', 'admin'):
                    continue
                # Không dùng lại metadata hỏng để dựng giao diện hoặc xác định chủ sở hữu.
                row = dict(id=request_id, nhan=request_id, nguoi_gui='', ngay_gui='',
                           files=[], trang_thai='hong', lich_su=[],
                           thong_bao='Dữ liệu trạng thái hỏng')
            if role in ('ky_su', 'admin') or row['nguoi_gui'] == username:
                rows.append(row)
        return sorted(rows, key=lambda r: (r['ngay_gui'], r['id']), reverse=True)

    def gui_dot(self, uploads, nhan, mo_ta):
        username, audit = actor('gui')
        if not isinstance(nhan, str) or not re.fullmatch(r'[a-z0-9_-]{1,40}', nhan):
            raise ValueError('Nhãn đợt chỉ gồm a-z, 0-9, gạch dưới, gạch ngang; dài 1–40 ký tự.')
        if not 1 <= len(uploads) <= 40:
            raise ValueError('Mỗi đợt nhận 1–40 file.')
        names = [relative_path(safe_filename(upload.name)) for upload in uploads]
        if len(names) != len(set(names)):
            raise ValueError('Tên file trùng nhau sau khi chuẩn hóa.')
        if set(names) & {'sales.csv', 'sample_submission.csv'}:
            raise ValueError('Không nhận sales.csv hoặc sample_submission.csv trong đợt dữ liệu.')
        if not any(name.startswith('orders') for name in names):
            raise ValueError('Đợt phải có ít nhất một file tên bắt đầu bằng orders.')
        contents, files, total = [], [], 0
        for upload, name in zip(uploads, names):
            upload.seek(0)
            content = bytearray()
            digest = hashlib.sha256()
            while block := upload.read(CHUNK_BYTES):
                total += len(block)
                if len(content) + len(block) > MAX_FILE_BYTES:
                    raise ValueError('Mỗi file tối đa 200 MB.')
                if total > MAX_TOTAL_BYTES:
                    raise ValueError('Tổng dung lượng một đợt tối đa 100 MB.')
                digest.update(block)
                content.extend(block)
            contents.append(content)
            files.append({'ten': name, 'so_byte': len(content), 'sha256': digest.hexdigest()})
        request_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_') + uuid4().hex[:6] + '_dot'
        folder = request_path(request_id)
        record = dict(id=request_id, loai='dot', nhan=nhan, mo_ta=mo_ta, nguoi_gui=username,
                      ngay_gui=datetime.now(timezone.utc).isoformat(), files=files, ma=uuid4().hex)
        for file, content in zip(files, contents):
            self.kho.ghi_moi(folder + '/file/' + file['ten'], bytes(content))
        self.kho.ghi_moi(folder + '/yeu_cau.json', json.dumps(record, ensure_ascii=False).encode('utf-8'))
        self.kho.ghi_json_so_tiep(folder + '/su_kien', {'toi': 'da_gui', 'ai': username, 'ghi_chu': ''}, expected=0)
        audit.log(username, 'dot_gui', {'id': request_id})
        return self.read(request_id)

    def change(self, request_id, target):
        username, audit = actor('duyet')
        if roles.current_role() not in ('ky_su', 'admin'):
            raise PermissionError('Chỉ Kỹ sư dữ liệu hoặc Admin được chạy lại và hủy đợt.')
        row = self.read(request_id)
        if row['trang_thai'] != 'loi' or target not in ('cho_chay', 'huy'):
            raise ValueError('Chỉ được chạy lại hoặc hủy đợt đang lỗi.')
        number = self.kho.ghi_json_so_tiep(request_path(request_id) + '/su_kien',
            {'toi': target, 'ai': username, 'ghi_chu': ''}, expected=len(row['lich_su']))
        audit.log(username, 'dot_chay_lai' if target == 'cho_chay' else 'dot_huy', {'id': request_id, 'so': number})
        return number

    def latest_command(self):
        names = sequence_names(self.kho.liet_ke('lenh'))
        if not names:
            return None
        name = names[-1]
        command = dict(self._json('lenh/' + name), so=int(name[:-5]))
        try:
            command['ket_qua'] = self._json('lenh/' + name[:-5] + '.ket_qua.json')
        except KhongCo:
            command['ket_qua'] = None
        return command

    def label(self, row, command):
        pending = (row['trang_thai'] == 'da_kiem' and command and command['ket_qua'] is None
                   and command['loai'] == 'dat' and command.get('request_id') == row['id'])
        return LABELS_DOT['cho_dashboard' if pending else row['trang_thai']]

    def dashboard_command(self, release_id=None, *, confirmed=False):
        username, audit = actor('cong_bo')
        if release_id is not None and not confirmed:
            raise ValueError('Cần xác nhận dữ liệu tổng hợp, chỉ để demo.')
        body = {'loai': 'tra' if release_id is None else 'dat', 'ai': username}
        if release_id is not None:
            from ui.nhap_runner import dashboard_state_cloud
            state = dashboard_state_cloud()
            record = state.get('releases', {}).get(release_id, {})
            if record.get('status') != 'ready' or record.get('co_du_lieu_tong_hop') is not True:
                raise ValueError('Bản tổng hợp chưa đạt quality gate.')
            body['release_id'] = release_id
            rows = self.visible(username, roles.current_role())
            matching = next((r for r in rows if r.get('release_id') == release_id), None)
            if matching:
                body['request_id'] = matching['id']
        latest = self.latest_command()  # Đọc lại lúc bấm, không dùng dữ liệu lúc vẽ nút.
        if latest and latest['ket_qua'] is None:
            raise ValueError('Đang chờ Airflow xử lý lệnh (thường dưới 5 phút)')
        number = self.kho.ghi_json_so_tiep('lenh', body, expected=latest['so'] if latest else 0)
        audit.log(username, 'dashboard_lenh_' + body['loai'], {'so': number, 'release_id': release_id})
        return number

    def ledger(self):
        rows = {}
        for name in sequence_names(self.kho.liet_ke('so_dot')):
            event = self._json('so_dot/' + name)
            if event['loai'] == 'vao_so':
                rows[event['ma_dot']] = dict(event, so=int(name[:-5]))
            elif event['loai'] == 'bo':
                rows.pop(event['ma_dot'], None)
            else:
                raise ValueError('Sổ đợt có sự kiện không hợp lệ.')
        return sorted(rows.values(), key=lambda row: row['so'])

    def remove_from_ledger(self, ma_dot, reason):
        username, audit = actor('duyet')
        if roles.current_role() not in ('ky_su', 'admin'):
            raise PermissionError('Chỉ Kỹ sư dữ liệu hoặc Admin được bỏ đợt khỏi sổ.')
        if not reason.strip():
            raise ValueError('Cần nhập lý do bỏ khỏi sổ.')
        if not any(row['ma_dot'] == ma_dot for row in self.ledger()):
            raise TrangThaiDaDoi()
        number = self.kho.ghi_json_so_tiep('so_dot', {'loai': 'bo', 'ma_dot': ma_dot, 'ly_do': reason.strip(), 'ai': username})
        audit.log(username, 'so_dot_bo', {'ma_dot': ma_dot, 'so': number})
        return number
