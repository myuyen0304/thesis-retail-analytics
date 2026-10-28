"""So cấu trúc cột; ứng viên đổi tên luôn cần BA duyệt."""
from difflib import SequenceMatcher

from scripts.ingest.adapters import normalize, quote

# Chỉ đưa tên khá gần nhau vào danh sách; không tự áp ứng viên dù điểm cao.
RENAME_MIN_SCORE = 0.6


def infer_types(data, columns):
    """Suy kiểu trên toàn cột không rỗng; cột toàn rỗng chưa đủ bằng chứng."""
    out = {}
    for col in columns:
        value = f"nullif(trim({quote(col)}), '')"
        n, integers, numbers, dates = data.con.execute(
            f"select count({value}), count(*) filter(where regexp_full_match({value}, '[+-]?[0-9]+')), "
            f'count(try_cast({value} as double)), count(try_cast({value} as date)) '
            f'from {quote(data.table)}').fetchone()
        out[col] = ('unknown' if not n else 'integer' if integers == n else 'double' if numbers == n
                    else 'date' if dates == n else 'string')
    return out


def compare_columns(columns, expected, inferred_types=None, contract_types=None):
    """Giữ tên gốc ở matched/added, chỉ chuẩn hóa để so khớp."""
    expected_names = {normalize(c): c for c in expected}
    present = {normalize(c) for c in columns}
    matched = [c for c in columns if normalize(c) in expected_names]
    added = [c for c in columns if normalize(c) not in expected_names]
    missing = [c for c in expected if normalize(c) not in present]
    order_changed = [normalize(c) for c in matched] != [normalize(c) for c in expected if normalize(c) in present]
    candidates = []
    for target in missing:
        expected_type = (contract_types or {}).get(target)
        if isinstance(expected_type, tuple):
            expected_type = expected_type[0]
        for col in added:
            inferred = (inferred_types or {}).get(col)
            compatible = inferred == expected_type or (inferred in ('integer', 'double') and
                         (expected_type == 'double' or str(expected_type).startswith('decimal(')))
            score = SequenceMatcher(None, normalize(target), normalize(col)).ratio()
            if expected_type and compatible and score >= RENAME_MIN_SCORE:
                candidates.append({'cot_thieu': target, 'ung_vien': col, 'diem': round(score, 4),
                                   'kieu_suy_duoc': inferred, 'trang_thai': 'de_xuat'})
    candidates.sort(key=lambda c: (-c['diem'], c['ung_vien'], c['cot_thieu']))
    return {'matched': matched, 'added': added, 'missing': missing, 'order_changed': order_changed,
            'kind': 'breaking' if missing else 'additive' if added or order_changed else 'khop',
            'rename_candidates': candidates}
