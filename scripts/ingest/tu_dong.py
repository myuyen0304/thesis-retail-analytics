"""Quyết định đường nhập và hợp đồng của một lượt, không truy cập đĩa."""
from copy import deepcopy


def normalize(name):
    return name.replace('\ufeff', '').strip().lower()


def _reason(code, business, technical):
    return {'ma': code, 'nghiep_vu': business, 'ky_thuat': technical}


def phan_loai(de_xuat, ung_vien, co_model):
    source = (de_xuat.get('nguon') or {}).get('de_xuat')
    candidates = list(ung_vien)
    complete = [item for item in candidates if not item[3]]
    reasons = []
    if not source or source == 'chua_ro':
        reasons.append(_reason('chua_ro_nguon', 'Chưa xác định được nguồn dữ liệu.',
                               'auto mapping chưa chọn được nguồn logic.'))
    if not candidates:
        reasons.append(_reason('chua_co_hop_dong', 'Nguồn này chưa có hợp đồng đã duyệt.',
                               f'Không có hợp đồng hiện hành cho nguồn {source}.'))
    elif not complete:
        best = min(candidates, key=lambda item: len(item[3]))
        missing = ', '.join(best[3])
        reasons.append(_reason('thieu_cot', f'File thiếu cột {missing}.',
                               f'File thiếu cột {missing} so với hợp đồng {best[0]} v{best[1]}.'))
    elif len(complete) > 1:
        reasons.append(_reason('nhieu_hop_dong', 'File khớp nhiều hợp đồng; đội dữ liệu cần chọn.',
                               'Các hợp đồng cùng khớp: ' + ', '.join(item[0] for item in complete)))
    if any(col.get('loai') == 'khop' and col.get('khong_ep_duoc', 0) > 0
           for col in de_xuat.get('cot', [])):
        reasons.append(_reason('doi_kieu', 'Có cột đổi kiểu dữ liệu.',
                               'Cột khớp hợp đồng có giá trị không ép được kiểu.'))
    conflict = de_xuat.get('xung_dot_khoa') or {}
    if conflict.get('da_kiem') is not True or conflict.get('id_trung_khac_noi_dung', 0) > 0:
        reasons.append(_reason('xung_dot_khoa', 'Khóa dữ liệu cần đội dữ liệu kiểm tra.',
                               'Xung đột khóa hoặc chưa kiểm xong khóa.'))
    if de_xuat.get('tham_chieu_thieu'):
        reasons.append(_reason('tham_chieu_thieu', 'Thiếu dữ liệu tham chiếu để đối chiếu.',
                               'Thiếu tham chiếu: ' + ', '.join(de_xuat['tham_chieu_thieu'])))
    if len(complete) == 1 and not co_model:
        reasons.append(_reason('chua_co_model', 'Nguồn này chưa có mô hình báo cáo.',
                               'Chưa có model dbt cho phần mở rộng.'))
    selected = complete[0] if len(complete) == 1 else None
    new_columns = []
    missing_optional = []
    if selected:
        existing = {normalize(name) for name in selected[2]['header']}
        new_columns = [col['ten_trong_file'] for col in de_xuat.get('cot', [])
                       if normalize(col['ten_trong_file']) not in existing]
        header = {normalize(col['ten_trong_file']) for col in de_xuat.get('cot', [])}
        missing_optional = [col['ten'] for col in selected[2]['cot']
                            if col.get('tuy_chon') is True and normalize(col['ten']) not in header]
    return {'ket_qua': 'can_nguoi' if reasons else 'tu_dong',
            'ten': selected[0] if selected else None,
            'phien_ban': selected[1] if selected else None,
            'cot_moi': new_columns, 'cot_tuy_chon_thieu': missing_optional, 'ly_do': reasons}


def hop_dong_cua_luot(hop_dong_hien_hanh, header_file, file_rel, phien_ban, ngay):
    doc = deepcopy(hop_dong_hien_hanh)
    doc.pop('hop_dong_sha256', None)
    by_name = {normalize(col['ten']): col for col in doc['cot']}
    columns = []
    for name in header_file:
        old = by_name.get(normalize(name))
        if old is None:
            columns.append({'ten': name, 'xu_ly': 'bo', 'ly_do': 'cột mới, chờ duyệt nâng hợp đồng',
                            'trang_thai': 'da_duyet'})
        else:
            column = deepcopy(old)
            column['ten'] = name
            columns.append(column)
    doc.update(header=list(header_file), cot=columns, file=file_rel, phien_ban=phien_ban,
               duyet_boi=f"he_thong (hợp đồng {doc['ten']} v{phien_ban}, sha256 {hop_dong_hien_hanh.get('hop_dong_sha256', '')[:8]})",
               ngay_duyet=ngay)
    if 'khoa_noi' in doc:
        link = doc['khoa_noi']
        key = next((name for name in header_file if normalize(name) == normalize(link['cot'])), None)
        if key:
            link['cot'] = key
    return doc
