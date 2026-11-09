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
ID_PATTERN = re.compile(r'[0-9]{8}T[0-9]{6}Z_[a-f0-9]{6}_dot')
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
                    if not isinstance(event[key], str):
                        raise TypeError('Trường trạng thái phải là chuỗi.')
                    result[key] = event[key]
        if state is None:
            raise ValueError('Chưa có sự kiện đầu tiên.')
        result['trang_thai'] = state
    except (KeyError, TypeError, ValueError) as error:
        result.update(trang_thai='hong', thong_bao='Dữ liệu trạng thái hỏng: ' + str(error))
    return result

