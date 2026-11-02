"""Chuyển quyết định của người duyệt thành hợp đồng; không tự phê duyệt."""
from copy import deepcopy
from pathlib import Path
import re

from scripts.ingest.adapters import normalize
from scripts.ingest.source_contract import COLUMNS, KEYS


def extension_name(filename):
    name = re.sub(r'[^a-z0-9_]', '_', Path(filename).stem.lower()).strip('_')
    return name if name and name[0].isalpha() else 'ext_' + name


def default_decisions(proposal):
    source = proposal['nguon']['de_xuat']
    keys = KEYS.get(source) or []
    key = keys[0] if len(keys) == 1 else None
    columns = []
    for col in proposal['cot']:
        name = col['ten_trong_file']
        action = ('khoa_noi' if key is not None and normalize(name) == normalize(key) else 'doi_chieu_loi') if col['loai'] == 'khop' else (
            'bo' if col['loai'] == 'thua' else 'nap')
        decision = {'ten': name, 'xu_ly': action}
        if action in ('nap', 'khoa_noi'):
            decision.update(kieu=COLUMNS[source][key][0] if action == 'khoa_noi' else 'string',
                            duoc_rong=bool(col.get('thong_ke', {}).get('so_rong', 0)))
        if action == 'nap':
            decision['hien_thi'] = 'silver' if col.get('nghi_pii') else 'mart'
        if action == 'bo':
            decision['ly_do'] = 'thừa, suy từ ' + ', '.join(
                f"{p['nguon']} qua {p['khoa_noi']}" for p in col.get('bang_chung', []))
        columns.append(decision)
    entities = [{'ten': e['ten_de_xuat'], 'khoa': e['khoa'], 'thuoc_tinh': list(e['thuoc_tinh'])}
                for e in proposal['thuc_the_moi']]
    return {'cot': columns, 'thuc_the': entities, 'nguong_cach_ly': 0.01,
            'khoa_noi': {'nguon': source, 'cot': next((c['ten'] for c in columns if c['xu_ly'] == 'khoa_noi'), ''),
                         'cot_nguon': key or ''}}


def hop_dong_tu_de_xuat(de_xuat, quyet_dinh, ten, file_rel, nguoi_duyet, ngay):
    """Hàm thuần; bên lưu phải gọi extension_contract.load trước khi chấp nhận."""
    decisions = deepcopy(quyet_dinh)
    cols = decisions['cot']
    for col in cols:
        col['trang_thai'] = 'da_duyet'
        if col.get('xu_ly') == 'nap' and col.get('hien_thi') not in ('mart', 'silver'):
            raise ValueError(f"Cột {col['ten']}: hien_thi phải là mart hoặc silver")
    entities = decisions.get('thuc_the', [])
    for entity in entities:
        entity['trang_thai'] = 'da_duyet'
    return {'phien_ban': 1, 'ten': ten, 'file': file_rel, 'trang_thai': 'da_duyet',
            'duyet_boi': nguoi_duyet, 'ngay_duyet': ngay,
            'header': [c['ten_trong_file'] for c in de_xuat['cot']], 'cot': cols,
            'thuc_the': entities, 'khoa_noi': decisions['khoa_noi'],
            'nguong_cach_ly': decisions.get('nguong_cach_ly', 0.01)}


def has_dbt_model(name, models):
    if not re.fullmatch(r'[a-z][a-z0-9_]*', name):
        return False
    pattern = re.compile(r"extension_enabled\(\s*['\"]" + re.escape(name) + r"['\"]\s*\)")
    return any(pattern.search(p.read_text(encoding='utf-8')) for p in Path(models).rglob('*.sql'))


SOURCE_LABELS = dict(zip(
    ('customers', 'geography', 'products', 'promotions', 'orders', 'order_items', 'payments',
     'shipments', 'returns', 'reviews', 'inventory', 'web_traffic', 'sales', 'sample_submission'),
    ('Khách hàng', 'Địa lý', 'Sản phẩm', 'Khuyến mãi', 'Đơn hàng', 'Chi tiết đơn hàng', 'Thanh toán',
     'Giao hàng', 'Trả hàng', 'Đánh giá', 'Tồn kho', 'Lượt truy cập web', 'Doanh thu theo ngày', 'Mẫu nộp dự báo')))
COLUMN_LABELS = {'sales_employee': 'Nhân viên bán hàng', 'sales_employee_id': 'Mã nhân viên',
                 'sales_employee_name': 'Tên nhân viên', 'marital_status': 'Tình trạng hôn nhân',
                 'education_level': 'Trình độ học vấn', 'years_experience': 'Số năm kinh nghiệm',
                 'comment': 'Ghi chú', 'city': 'Thành phố', 'region': 'Vùng', 'district': 'Quận/huyện'}


def tom_tat_nghiep_vu(de_xuat):
    source = de_xuat['nguon']['de_xuat']
    label = SOURCE_LABELS.get(source, 'Chưa xác định')
    extra = ' (bổ sung thông tin)' if de_xuat['schema_diff']['cot_them'] else ''
    number = lambda value: f'{value:,}'.replace(',', '.')
    out = [f'Hệ thống hiểu file là: {label}{extra}', f"Số dòng: {number(de_xuat['file']['so_dong'])}"]
    conflict = de_xuat.get('xung_dot_khoa', {})
    if conflict.get('da_kiem'):
        overlapping = conflict['id_trung_nguon']
        different = conflict['id_trung_khac_noi_dung']
        rekeyed = conflict['danh_lai_khoa']
        if different:
            out.append(f'{number(different)} mã trùng với {label.lower()} đã có nhưng khác nội dung.')
        elif overlapping and not rekeyed:
            out.append(f'Khớp khóa với {number(overlapping)} {label.lower()} đã có.')
        elif overlapping:
            out.append(f'{number(overlapping)} mã trùng với {label.lower()} đã có; đội dữ liệu cần kiểm tra nội dung.')
        if rekeyed:
            out.append(f'{number(rekeyed)} bản ghi giống {label.lower()} cũ nhưng mang mã khác.')
        if rekeyed or different:
            out.append('Cảnh báo xung đột khóa: có mã trùng nhưng khác nội dung hoặc bản ghi cũ mang mã mới. Đội dữ liệu cần kiểm tra.')
    for entity in de_xuat['thuc_the_moi']:
        out.append('Thông tin mới: ' + COLUMN_LABELS.get(entity['ten_de_xuat'], entity['ten_de_xuat']) + ': ' +
                   ', '.join(COLUMN_LABELS.get(c, c) for c in [entity['khoa'], *entity['thuoc_tinh']]))
    redundant = [COLUMN_LABELS.get(c['ten_trong_file'], c['ten_trong_file']) for c in de_xuat['cot'] if c['loai'] == 'thua']
    if redundant:
        out.append('Thông tin trùng đã có, đề xuất bỏ: ' + ', '.join(redundant))
    if any(c.get('nghi_pii') for c in de_xuat['cot']):
        out.append('Có thông tin cá nhân: sẽ không hiển thị trên báo cáo khi chưa được duyệt.')
    return out
