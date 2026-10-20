"""B5: bộ truy xuất offline cố định; không đọc DWH, không gọi mô hình."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/retail_app'))
from ai_explain import knowledge  # noqa: E402

# Câu khác chữ anchor của script build; nguồn kỳ vọng viết trước lượt live đầu.
CASES = [
    ('R là doanh thu nào?', 'docs/star_schema.md §3'),
    ('G tính trên những trạng thái đơn nào?', 'docs/star_schema.md §3'),
    ('N đếm đơn hay dòng hàng?', 'docs/star_schema.md §3'),
    ('U số món mỗi đơn tính ra sao?', 'docs/star_schema.md §3'),
    ('P giá bình quân một món là gì?', 'docs/star_schema.md §3'),
    ('C có cộng tùy ý qua nhiều kỳ không?', 'docs/star_schema.md §3'),
    ('PS1 dùng gì để đo phần hụt giữa G và R?', 'docs/star_schema_tu_ps.md §1'),
    ('PS2 phân tích xu hướng và điểm đổi hướng theo lịch nào?', 'docs/star_schema_tu_ps.md §5'),
    ('PS3 xem mùa vụ và nhịp cuối tháng bằng dữ liệu nào?', 'docs/star_schema_tu_ps.md §1'),
    ('PS4 giải thích R bằng số đơn, số món và giá ra sao?', 'docs/star_schema_tu_ps.md §1'),
    ('PS5 so ngành hàng, vùng và kênh thu hút thế nào?', 'docs/star_schema_tu_ps.md §1'),
    ('Quy ước năm ranh giới PS3 đã chốt chưa?', 'docs/ai_explain_plan.md §0.2'),
    ('Ngưỡng đánh dấu biến động R nhỏ có phải kết luận thống kê không?', 'docs/ai_explain_plan.md §0.2'),
    ('Khuyến mãi áp dụng ở dòng hàng hay toàn bộ đơn?', 'docs/data-dictionary.md §1.1'),
    ('Urban Blowout sau thời kỳ dữ liệu có phải lịch khuyến mãi thật không?', 'docs/data-dictionary.md §3.4'),
    ('Kết luận cũ về tháng 8 năm lẻ và Urban Blowout là gì?', 'CLAUDE.md §5'),
    ('Đứt gãy cấu trúc cuối 2018 trong chuỗi doanh thu?', 'CLAUDE.md §5'),
    ('COGS được dự báo trực tiếp hay qua tỷ lệ?', 'docs/hop_dong_du_bao.md §2.3'),
    ('Chỉ số nào dùng để chọn ứng viên dự báo qua backtest?', 'docs/hop_dong_du_bao.md §5'),
    ('Bảng forecast daily lưu is_primary để làm gì?', 'docs/hop_dong_du_bao.md §7'),
]


def set_hash() -> str:
    body = json.dumps(CASES, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(body.encode('utf-8')).hexdigest()[:16]


def main() -> int:
    hit1 = hit3 = 0
    for i, (q, want) in enumerate(CASES, 1):
        got = [r['citation'] for r in knowledge.search(q, 3)]
        one, three = bool(got and got[0] == want), want in got
        hit1 += one
        hit3 += three
        print(f"{'OK' if three else 'MISS'} {i:02d} hit1={int(one)} {q} → {got}")
    print(f"B5 offline: hit@1={hit1}/{len(CASES)}, hit@3={hit3}/{len(CASES)}; "
          f"set_hash={set_hash()}; corpus_version={knowledge.corpus()['corpus_version']}")
    return 0 if hit3 == len(CASES) else 1


if __name__ == '__main__':
    raise SystemExit(main())
