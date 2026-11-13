"""Yêu cầu đợt và lệnh dashboard: chỉ ghi kho, không chạy pipeline trên web."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4

from ui import roles
from ui.nhap_store import actor, safe_filename
from ui.kho_dot import KhongCo, TrangThaiDaDoi, sequence_names, relative_path
from ui.trang_thai_dot import TRANSITIONS_DOT, ID_PATTERN, request_path, phat_lai

LABELS_DOT = dict(zip(
    ('da_gui', 'dang_kiem', 'cho_chay', 'dang_chay', 'da_kiem', 'cho_dashboard', 'tren_dashboard',
     'da_tra', 'sai_hop_dong', 'loi_file', 'het_cho', 'loi', 'huy', 'hong'),
    ('Đã gửi', 'Đang kiểm tra file', 'Chờ chạy', 'Đang chạy', 'Đã kiểm tra', 'Chờ đưa lên dashboard',
     'Đang trên dashboard', 'Đã trả dashboard', 'Sai hợp đồng dữ liệu', 'Không đọc được file',
     'Hết chỗ lưu trữ', 'Lỗi khi chạy', 'Đã hủy', 'Dữ liệu trạng thái hỏng')))
LABELS_MOT = dict(LABELS_DOT, dang_doc='Đang đọc file', cho_duyet='Chờ duyệt',
    da_duyet='Đã duyệt', loi_de_xuat='Không đọc được file',
    cho_model_dbt='Chờ đội dữ liệu bổ sung mô hình', tu_choi='Từ chối', khong_moi='Không có gì mới')
MAX_FILE_BYTES = 200 * 1024 * 1024
MAX_TOTAL_BYTES = 100 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024


def chu_duong_xu_ly(row) -> str | None:
    """Chỉ nêu đường xử lý khi đã biết; chưa đọc xong thì báo đang đọc."""
    if row.get('duong') == 'tu_dong':
        return 'Đường xử lý: Tự động'
    if row.get('duong') == 'tay':
        return 'Đường xử lý: Chờ đội dữ liệu'
    if row.get('trang_thai') in ('da_gui', 'dang_doc'):
        return 'Đang đọc và hiểu file…'
    return None


def tao_anh_chup(rows, command):
    """Chụp đúng dữ liệu đã vẽ; không đọc thêm kho để tạo ảnh đầu."""
    return {
        'rows': tuple(tuple(row.get(key) for key in
                           ('id', 'trang_thai', 'release_id', 'ma_loi', 'thong_bao'))
                      for row in rows),
        'lenh': None if command is None else {
            'so': command['so'], 'loai': command.get('loai'),
            # Tách kết quả khỏi đầu vào để ảnh đầu không đổi theo nó.
            'ket_qua': None if command['ket_qua'] is None else dict(command['ket_qua']),
        },
    }


def can_theo_doi(anh):
    """Chỉ dò khi Airflow còn có thể đổi trạng thái hoặc trả kết quả lệnh."""
    command = anh['lenh']
    return (command is not None and command['ket_qua'] is None) or any(
        row[1] in ('da_gui', 'dang_kiem', 'dang_doc', 'da_duyet', 'het_cho', 'cho_chay', 'dang_chay')
        for row in anh['rows'])


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
            replay = phat_lai(events, metadata.get('loai', 'dot'))
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
                if row.get('loai') == 'mot_file':
                    if not request_id.endswith('_mot') or row.get('id') != request_id:
                        raise ValueError('Loại yêu cầu không khớp mã.')
                    item = row['file']
                    if not isinstance(item, dict):
                        raise TypeError('Thông tin file không hợp lệ.')
                    row = dict(row, nhan=item['ten'], files=[item])
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

    def anh_chup(self, username, role):
        return tao_anh_chup(self.visible(username, role), self.latest_command(strict=True))

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

    def gui_mot_file(self, upload, mo_ta):
        username, audit = actor('gui')
        if upload is None:
            raise ValueError('Chọn một file trước khi gửi.')
        name = relative_path(safe_filename(upload.name))
        upload.seek(0)
        content = bytearray()
        digest = hashlib.sha256()
        while block := upload.read(CHUNK_BYTES):
            if len(content) + len(block) > MAX_FILE_BYTES:
                raise ValueError('Mỗi file tối đa 200 MB.')
            digest.update(block)
            content.extend(block)
        request_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_') + uuid4().hex[:6] + '_mot'
        folder = request_path(request_id)
        record = dict(id=request_id, loai='mot_file', nguoi_gui=username,
            vai_tro=roles.current_role(), mo_ta=mo_ta,
            ngay_gui=datetime.now(timezone.utc).isoformat(),
            file={'ten': name, 'so_byte': len(content), 'sha256': digest.hexdigest()})
        self.kho.ghi_moi(folder + '/file/' + name, bytes(content))
        self.kho.ghi_moi(folder + '/yeu_cau.json', json.dumps(record, ensure_ascii=False).encode('utf-8'))
        self.kho.ghi_json_so_tiep(folder + '/su_kien',
            {'toi': 'da_gui', 'ai': username, 'ghi_chu': ''}, expected=0)
        audit.log(username, 'mot_gui', {'id': request_id})
        return self.read(request_id)

    def proposal(self, request_id):
        import yaml
        return yaml.safe_load(self.kho.doc(request_path(request_id) + '/de_xuat/mapping_de_xuat.yml'))

    def notice(self, request_id):
        try:
            doc = self._json(request_path(request_id) + '/thong_bao.json')
            return doc['thong_bao']
        except KhongCo:
            return None

    def _review(self, request_id, expected, status):
        username, audit = actor('duyet')
        row = self.read(request_id)
        if (row.get('loai') != 'mot_file' or row['trang_thai'] not in status
                or len(row['lich_su']) != expected):
            raise TrangThaiDaDoi()
        return username, audit, row

    def approve(self, request_id, expected, decisions, name):
        import yaml
        from scripts.ingest import approval
        from ui.kho_hop_dong import KhoHopDong, load_raw, chu_ky_nghiep_vu
        username, audit, row = self._review(request_id, expected, ('cho_duyet',))
        folder = request_path(request_id)
        doc = approval.hop_dong_tu_de_xuat(self.proposal(request_id), decisions, name,
            f"ui_nhap_cloud/{request_id}/{row['file']['ten']}", username,
            datetime.now(timezone.utc).isoformat())
        raw = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False).encode('utf-8')
        checked = load_raw(name, raw)  # Kiểm toàn bộ trước khi ghi bất kỳ hiện vật đã duyệt nào.
        registry = KhoHopDong(self.kho)
        current = registry.current(name)
        model = approval.has_dbt_model(name, Path(__file__).resolve().parents[3] / 'retail_dbt/models')
        audit.log(username, 'mot_duyet', {'id': request_id, 'ten': name})
        self.kho.ghi_moi(folder + '/hop_dong/' + name + '.yml', raw)
        if current is None:
            registry.write(name, doc, username, 'yeu_cau:' + request_id, expected=0)
        self.kho.ghi_json_so_tiep(folder + '/su_kien', {
            'toi': 'da_duyet' if model else 'cho_model_dbt', 'ai': username, 'ghi_chu': '',
            'duong': 'tay', 'ten_mo_rong': name, 'hop_dong_sha256': checked['hop_dong_sha256'],
            'chu_ky_nghiep_vu': chu_ky_nghiep_vu(checked)}, expected=expected)
        return self.read(request_id)

    def reject(self, request_id, expected, reason):
        username, audit, row = self._review(request_id, expected, ('cho_duyet',))
        if not reason.strip():
            raise ValueError('Từ chối phải ghi lý do.')
        self.kho.ghi_json_so_tiep(request_path(request_id) + '/su_kien',
            {'toi': 'tu_choi', 'ai': username, 'ghi_chu': reason.strip()}, expected=expected)
        audit.log(username, 'mot_tu_choi', {'id': request_id, 'ly_do': reason.strip()})

    def upgrade_info(self, request_id):
        from ui.kho_hop_dong import KhoHopDong, load_raw
        row = self.read(request_id)
        if (row.get('loai') != 'mot_file' or row.get('duong') != 'tu_dong'
                or not row.get('cot_moi') or not row.get('ten_mo_rong')):
            return None
        name = row['ten_mo_rong']
        doc = load_raw(name, self.kho.doc(request_path(request_id) + '/hop_dong/' + name + '.yml'))
        if doc['hop_dong_sha256'] != row.get('hop_dong_sha256'):
            raise ValueError('Hợp đồng của lượt đã đổi.')
        registry = KhoHopDong(self.kho)
        current = registry.current(name)
        if (current is None or current[0]['phien_ban'] != doc.get('phien_ban')
                or registry.rejected(name, row['cot_moi'])):
            return None
        return current

    def upgrade_contract(self, request_id, decisions, *, expected):
        from copy import deepcopy
        from scripts.ingest import approval
        from scripts.ingest.tu_dong import normalize
        from ui.kho_hop_dong import KhoHopDong
        username, audit = actor('duyet')
        current = self.upgrade_info(request_id)
        if current is None or current[0]['phien_ban'] != expected:
            raise TrangThaiDaDoi()
        row = self.read(request_id)
        columns = row['cot_moi']
        if (len(decisions) != len(columns)
                or {normalize(c['ten']) for c in decisions} != {normalize(c) for c in columns}
                or any(c.get('xu_ly') not in ('bo', 'nap') for c in decisions)):
            raise ValueError('Chỉ được duyệt đúng các cột mới của đề xuất.')
        name = row['ten_mo_rong']
        models = Path(__file__).resolve().parents[3] / 'retail_dbt/models'
        if any(c.get('xu_ly') == 'nap' and c.get('hien_thi') == 'mart'
               and not approval.has_dbt_column(name, c['ten'], models) for c in decisions):
            raise ValueError('Model dbt chưa có cột; chọn silver trước khi duyệt.')
        doc = deepcopy(current[1])
        doc['header'].extend(columns)
        doc['cot'].extend([{**c, 'trang_thai': 'da_duyet',
            'tuy_chon': c['xu_ly'] == 'bo' or c.get('hien_thi') == 'silver'} for c in decisions])
        # Chỉ nâng mẫu; không tạo yêu cầu hay ghi lệnh nạp bù.
        meta, checked = KhoHopDong(self.kho).write(name, doc, username,
            'nang_hop_dong:' + request_id, expected=expected)
        audit.log(username, 'mot_nang_hop_dong', {'id': request_id, 'ten': name,
                  'phien_ban': meta['phien_ban']})
        return meta

    def reject_upgrade(self, request_id, reason, *, expected):
        from ui.kho_hop_dong import KhoHopDong
        username, audit = actor('duyet')
        current = self.upgrade_info(request_id)
        if current is None or current[0]['phien_ban'] != expected:
            raise TrangThaiDaDoi()
        row = self.read(request_id)
        KhoHopDong(self.kho).reject(row['ten_mo_rong'], row['cot_moi'], reason, username)
        audit.log(username, 'mot_nang_hop_dong', {'id': request_id, 'ten': row['ten_mo_rong'],
                  'phien_ban': expected, 'tu_choi': True, 'ly_do': reason.strip()})

    def change(self, request_id, target):
        username, audit = actor('duyet')
        if roles.current_role() not in ('ky_su', 'admin'):
            raise PermissionError('Chỉ Kỹ sư dữ liệu hoặc Admin được chạy lại và hủy đợt.')
        row = self.read(request_id)
        if row['trang_thai'] != 'loi' or target not in ('cho_chay', 'huy'):
            raise ValueError('Chỉ được chạy lại hoặc hủy đợt đang lỗi.')
        number = self.kho.ghi_json_so_tiep(request_path(request_id) + '/su_kien',
            {'toi': target, 'ai': username, 'ghi_chu': ''}, expected=len(row['lich_su']))
        prefix = 'mot' if row.get('loai') == 'mot_file' else 'dot'
        audit.log(username, prefix + ('_chay_lai' if target == 'cho_chay' else '_huy'), {'id': request_id, 'so': number})
        return number

    def latest_command(self, *, strict=False):
        names = sequence_names(self.kho.liet_ke('lenh'))
        if not names:
            return None
        name = names[-1]
        command = {'so': int(name[:-5])}
        broken = {'ket_qua': 'loi', 'thong_bao': 'Dữ liệu lệnh hỏng; báo kỹ sư dữ liệu.'}
        try:
            body = self._json('lenh/' + name)
            if not isinstance(body, dict) or body.get('loai') not in ('dat', 'tra'):
                raise ValueError('Lệnh không hợp lệ.')
            command.update(body)
            command['so'] = int(name[:-5])
            try:
                result = self._json('lenh/' + name[:-5] + '.ket_qua.json')
                if not isinstance(result, dict) or result.get('ket_qua') not in ('dat', 'loi'):
                    raise ValueError('Kết quả lệnh không hợp lệ.')
                command['ket_qua'] = result
            except KhongCo:
                command['ket_qua'] = None
        except (ValueError, TypeError, KeyError, KhongCo, OSError):
            if strict:
                # Nhịp dò bỏ qua lỗi đọc, không biến lỗi tạm thời thành kết quả lệnh.
                raise
            command['ket_qua'] = broken
        return command

    def label(self, row, command):
        pending = (row['trang_thai'] == 'da_kiem' and command and command['ket_qua'] is None
                   and command.get('loai') == 'dat' and command.get('request_id') == row['id'])
        labels = LABELS_MOT if row.get('loai') == 'mot_file' else LABELS_DOT
        return labels['cho_dashboard' if pending else row['trang_thai']]

    def dashboard_command(self, release_id=None, *, confirmed=False):
        username, audit = actor('cong_bo')
        body = {'loai': 'tra' if release_id is None else 'dat', 'ai': username}
        if release_id is not None:
            from ui.nhap_runner import dashboard_state_cloud
            state = dashboard_state_cloud()
            record = state.get('releases', {}).get(release_id, {})
            synthetic = record.get('co_du_lieu_tong_hop') is True
            new_source = record.get('chi_dashboard') is True
            if record.get('status') != 'ready' or synthetic == new_source:
                raise ValueError('Bản tổng hợp chưa đạt quality gate.')
            if synthetic and not confirmed:
                raise ValueError('Cần xác nhận dữ liệu tổng hợp, chỉ để demo.')
            body['release_id'] = release_id
            if new_source:
                # Không phụ thuộc danh sách của trang web; chỉ nhận một yêu cầu đã kiểm đúng bản.
                matches = []
                for request_id in self.kho.liet_ke('yeu_cau'):
                    if not ID_PATTERN.fullmatch(request_id) or not request_id.endswith('_mot'):
                        continue
                    try:
                        row = self.read(request_id)
                    except (FileNotFoundError, ValueError, KeyError, TypeError, AttributeError):
                        continue
                    if (row.get('loai') == 'mot_file' and row.get('release_id') == release_id
                            and row.get('trang_thai') in ('da_kiem', 'da_tra', 'tren_dashboard')):
                        matches.append(row)
                if len(matches) != 1:
                    raise ValueError('Chưa xác định được đúng một yêu cầu đã kiểm cho bản nguồn mới.')
                body['request_id'] = matches[0]['id']
            else:
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
        try:
            for name in sequence_names(self.kho.liet_ke('so_dot')):
                event = self._json('so_dot/' + name)
                if event['loai'] == 'vao_so':
                    rows[event['ma_dot']] = dict(event, so=int(name[:-5]))
                elif event['loai'] == 'bo':
                    rows.pop(event['ma_dot'], None)
                else:
                    raise ValueError('Sự kiện không hợp lệ.')
            return sorted(rows.values(), key=lambda row: row['so'])
        except (ValueError, KeyError, TypeError, KhongCo, OSError) as error:
            raise ValueError('Sổ đợt hỏng; báo kỹ sư dữ liệu.') from error

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
