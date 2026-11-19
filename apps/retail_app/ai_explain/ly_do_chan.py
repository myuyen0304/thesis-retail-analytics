"""Dịch lời kiểm sang lời cho người đọc; giữ nguyên lời gốc cho vòng sửa và chẩn đoán."""
import re


ERROR_MESSAGES = {
    'xep_hang': 'Câu trả lời có nói "cao nhất / thấp nhất / nhiều nhất" nhưng chưa dẫn đúng bảng xếp hạng đủ các nhóm để kiểm chứng điều đó.',
    'so_tu_viet': 'Câu trả lời có con số không lấy từ kết quả tra kho của chính câu hỏi này.',
    'chieu_sai': 'Câu trả lời nói tăng / giảm ngược với số trong kho.',
    'tu_so_sanh': 'Câu trả lời tự so sánh các con số với nhau, trong khi kho chưa tính sẵn phần chênh lệch đó.',
    'ky': 'Câu trả lời dùng số của năm / kỳ khác với kỳ bạn hỏi, hoặc không ghi rõ kỳ.',
    'nam_du_bao': 'Câu hỏi dự báo chưa nêu rõ năm, nên hệ thống không tự chọn năm thay bạn.',
    'du_bao_thuc_te': 'Câu trả lời lẫn số dự báo với số thực tế.',
    'du_bao_pham_vi': 'Câu trả lời về dự báo dùng sai mô hình, sai thước đo sai số, hoặc nói tới chỉ tiêu / kỳ chưa có dự báo.',
    'nhom': 'Câu trả lời bỏ qua nhóm (ngành hàng / khu vực / kênh) bạn hỏi, hoặc nêu tên nhóm không kèm số từ kho.',
    'phan_ra': 'Câu trả lời diễn giải phần phân rã vượt quá điều số liệu cho phép (ví dụ coi phân rã là nguyên nhân, hoặc gộp "các nhóm còn lại" không có số).',
    'dinh_nghia': 'Chỉ tiêu bạn hỏi chưa có định nghĩa trong danh mục, hoặc câu trả lời dùng định nghĩa khác.',
    'khac': 'Câu trả lời có chỗ chưa khớp với số liệu trong kho, nên hệ thống không hiện để tránh nói sai.',
}
GUIDANCE = ('Bảng số ở mục **Bằng chứng** vẫn lấy thẳng từ kho và đọc được. '
         'Bạn có thể hỏi lại cụ thể hơn: nêu rõ năm, chỉ tiêu, nhóm.')

RANK_GUIDANCE = 'Muốn biết nhóm tăng / giảm nhiều nhất, hãy hỏi theo mức thay đổi so với năm trước.'

# So dấu hiệu cụ thể trước; không lấy chính câu văn đang bị kiểm làm dấu hiệu lỗi.
_PATTERNS = [(code, re.compile(pattern, re.I)) for code, pattern in [
    ('nam_du_bao', r'chưa có năm do người dùng chọn|phải ghi rõ năm'),
    ('dinh_nghia', r'basket size|get_metric_definition|định nghĩa|\bAOV\b'),
    ('ky', r'không ghi rõ kỳ|ghi .+ cho .+ nhưng|kỳ không hợp lệ|khác kỳ|kỳ / grain khác|dùng số của .+ cho câu hỏi về khoảng|không kiểm được kỳ'),
    ('phan_ra', r'nguyên nhân|còn lại/khác|khác/còn lại|small_groups|phân rã G|số phân rã G|model chính|nhân với nhau|vế câu gọi tên|vế câu nói về|contrib_|các nhóm khác|các nhóm còn lại|phân rã không chứng minh'),
    ('nhom', r'tên nhóm .+ không gắn|tên nhóm .+ mà không gắn|lọc nhóm .+ theo tháng|nêu nhóm .+ không có số'),
    ('du_bao_thuc_te', r'thực tế'),
    ('du_bao_pham_vi', r'chưa có dự báo chỉ tiêu này|kỳ ngoài vùng|nêu đích danh model|thước|MAPE|điểm ngày|nêu model'),
    ('chieu_sai', r'sign chỉ nhận|nói .+ nhưng .+ thật là|câu nói .+ nhưng .+ ='),
    ('tu_so_sanh', r'tự so sánh các số'),
    ('xep_hang', r'xếp hạng|nói "(?:nhiều nhất|nhỏ nhất|cao nhất|thấp nhất)|nhóm phân rã (?:nói|nêu)|chỗ đặt trỏ vào phía'),
    ('so_tu_viet', r'số tự viết|tự viết số|claim sai dạng|không có claim hợp lệ|là NULL|là một ngày|không có trường'),
]]


def nhom_loi(err: str) -> str:
    text = re.sub(r'^\s*c\d+:\s*', '', err)
    # Bỏ câu bị trích trong lời kiểm: câu đó có thể chứa bất kỳ từ khóa nào.
    text = re.sub(r'^câu ".*?" ', 'câu ', text)
    return next((code for code, pattern in _PATTERNS if pattern.search(text)), 'khac')


def _is_level_ranking(err: str) -> bool:
    text = re.sub(r'^\s*c\d+:\s*', '', err)
    if text.startswith('xếp hạng mức R'):
        return True
    sentence = re.match(r'^câu "(.*?)" ', text)
    return bool(sentence and re.search(r'cao nhất|thấp nhất|lớn nhất|nhỏ nhất', sentence[1], re.I)
                and not re.search(r'tăng|giảm|sụt|kéo lên|kéo xuống|ΔR|thay đổi', sentence[1], re.I))


def giai_thich(errors: list[str]) -> list[str]:
    groups = dict.fromkeys(nhom_loi(err) for err in errors)
    messages = [ERROR_MESSAGES[code] for code in groups] + [GUIDANCE]
    if any(nhom_loi(err) == 'xep_hang' and not _is_level_ranking(err) for err in errors):
        messages.append(RANK_GUIDANCE)
    return messages


STATUS_MESSAGES = {
    'query_error': 'Không đọc được số liệu cho câu này từ kho. Bạn thử lại sau hoặc hỏi cách khác.',
    'quality_blocked': 'Kho dữ liệu đang chưa qua bước kiểm chất lượng, nên tạm chưa trả lời bằng số.',
    'provider_error': 'Chưa gọi được mô hình AI. Bạn thử lại sau ít phút.',
    'budget_exceeded': 'Phiên chat đã dùng hết hạn mức. Bấm **Xóa hội thoại** để bắt đầu phiên mới.',
    'no_data': 'Kho không có số liệu cho năm / nhóm bạn hỏi.',
    'unsupported': 'Câu hỏi này nằm ngoài phạm vi trợ lý đang hỗ trợ (xem mục Cách đọc).',
    'needs_clarification': 'Trợ lý cần bạn nói rõ hơn (năm, chỉ tiêu hoặc nhóm).',
    'answer_validation_failed': 'Chưa tạo được lời diễn giải khớp với số liệu. Bạn vẫn có thể xem bảng số ở mục Bằng chứng.',
}
_TECHNICAL = re.compile(r'[`{}]|\b\w+_\w+\b|\b(?:derived|rpt|n_groups|claim|claims|tool|path|status|rank|metric|year|month|day|dimension|group|model|schema|backend|HTTP|SQL|API|JSON|NULL|Traceback)\b|\b\w+(?:Error|Exception)\b|\bT\d+\.(?:rows|derived)\b|\b(?:reporting|marts|staging)\.', re.I)


def status_message(status: str, text: str) -> tuple[str, bool]:
    """Trả lời hiển thị và dấu hiệu cần giữ bản gốc trong ô kỹ thuật."""
    technical = bool(_TECHNICAL.search(text))
    return (STATUS_MESSAGES.get(status, ERROR_MESSAGES['khac']) if technical else text), technical
