"""Trạng thái đợt thuần Python, dùng được trong tiến trình Airflow không có Streamlit."""
import re

TRANSITIONS_DOT = {
    'da_gui': {'dang_kiem', 'loi_file'},
    'dang_kiem': {'cho_chay', 'sai_hop_dong', 'het_cho'},
    'het_cho': {'cho_chay'}, 'cho_chay': {'dang_chay'},
    'dang_chay': {'da_kiem', 'loi'}, 'loi': {'cho_chay', 'huy'},
    'da_kiem': {'tren_dashboard'}, 'tren_dashboard': {'da_tra'},
    'da_tra': {'tren_dashboard'}, 'sai_hop_dong': set(), 'loi_file': set(), 'huy': set(),
}
TRANSITIONS_MOT = {
    'da_gui': {'dang_doc', 'loi_file'},
    'dang_doc': {'cho_duyet', 'da_duyet', 'loi_de_xuat'},
    'cho_duyet': {'da_duyet', 'cho_model_dbt', 'tu_choi'},
    # Kiểm lại hợp đồng trước chạy có thể thất bại (§5.3).
    'da_duyet': {'cho_chay', 'het_cho', 'khong_moi', 'loi'},
    'het_cho': {'cho_chay', 'loi', 'khong_moi'},
    'cho_chay': {'dang_chay', 'loi'}, 'dang_chay': {'da_kiem', 'loi'},
    'loi': {'cho_chay', 'huy'}, 'da_kiem': {'tren_dashboard'},
    'tren_dashboard': {'da_tra'}, 'da_tra': {'tren_dashboard'},
    **{name: set() for name in ('loi_file', 'loi_de_xuat', 'cho_model_dbt', 'tu_choi', 'huy', 'khong_moi')},
}
ID_PATTERN = re.compile(r'[0-9]{8}T[0-9]{6}Z_[a-f0-9]{6}_(?:dot|mot)')


def loai_cua(request_id):
    request_path(request_id)
    return 'mot_file' if request_id.endswith('_mot') else 'dot'

def request_path(request_id):
    if not isinstance(request_id, str) or not ID_PATTERN.fullmatch(request_id):
        raise ValueError('Mã yêu cầu đợt không hợp lệ.')
    return 'yeu_cau/' + request_id


def phat_lai(su_kien, loai='dot'):
    """Nhận các cặp (số thứ tự, sự kiện); hỏng một bước thì không cho thao tác."""
    result = {'trang_thai': 'hong', 'lich_su': []}
    state = None
    try:
        transitions = {'dot': TRANSITIONS_DOT, 'mot_file': TRANSITIONS_MOT}[loai]
        for expected, (number, event) in enumerate(su_kien, 1):
            if number != expected:
                raise ValueError('Số thứ tự sự kiện không liền nhau từ 1.')
            target = event['toi']
            if (state is None and target != 'da_gui') or (state is not None and target not in transitions[state]):
                raise ValueError('Bước chuyển trạng thái không hợp lệ.')
            state = target
            result['lich_su'].append(event)
            fields = ('release_id', 'ma_loi', 'thong_bao')
            if loai == 'mot_file':
                fields += ('duong', 'ten_mo_rong', 'hop_dong_sha256', 'chu_ky_nghiep_vu')
            for key in fields:
                if key in event:
                    if not isinstance(event[key], str):
                        raise TypeError('Trường trạng thái phải là chuỗi.')
                    result[key] = event[key]
            if loai == 'mot_file' and 'duong' in event and event['duong'] not in ('tu_dong', 'tay'):
                raise ValueError('Đường xử lý không hợp lệ.')
            if loai == 'mot_file' and 'ly_do' in event:
                reasons = event['ly_do']
                if not isinstance(reasons, list) or any(
                    not isinstance(reason, dict) or any(not isinstance(reason.get(key), str)
                    for key in ('ma', 'nghiep_vu', 'ky_thuat')) for reason in reasons):
                    raise TypeError('Danh sách lý do không hợp lệ.')
                result['ly_do'] = reasons
            if loai == 'mot_file' and 'cot_moi' in event:
                if not isinstance(event['cot_moi'], list) or any(not isinstance(c, str) for c in event['cot_moi']):
                    raise TypeError('Danh sách cột mới không hợp lệ.')
                result['cot_moi'] = event['cot_moi']
        if state is None:
            raise ValueError('Chưa có sự kiện đầu tiên.')
        result['trang_thai'] = state
    except (KeyError, TypeError, ValueError) as error:
        result.update(trang_thai='hong', thong_bao='Dữ liệu trạng thái hỏng: ' + str(error))
    return result

