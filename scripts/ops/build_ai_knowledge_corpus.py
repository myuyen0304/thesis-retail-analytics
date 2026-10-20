"""Tạo bản chụp tri thức B5 từ đúng các đoạn tài liệu đã chọn; chạy tại root repo.

Không lấy file bị ignore/exclude. Bản chụp nằm trong apps/retail_app để cả
Streamlit public và gói Databricks Apps (chỉ chép apps/retail_app) đều đọc được.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'apps/retail_app/ai_explain/knowledge_corpus.json'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# (file, heading nguyên văn, dấu nhận diện đoạn, trạng thái). Mỗi dấu phải khớp đúng một đoạn/dòng.
SOURCES = [
    *[('docs/star_schema.md', '## 3. Hợp đồng KPI: cùng định nghĩa ở mọi công cụ', f'| {m} |', 'đã chốt')
      for m in ('G', 'R', 'Q', 'N', 'C', 'U', 'P', 'F', 'AOV')],
    ('docs/star_schema.md', '## 3. Hợp đồng KPI: cùng định nghĩa ở mọi công cụ',
     'R là định nghĩa phân tích', 'đã chốt'),
    ('docs/star_schema.md', '## 3. Hợp đồng KPI: cùng định nghĩa ở mọi công cụ',
     'Mẫu số bằng 0', 'đã chốt'),
    ('docs/star_schema.md', '## 4. Lớp reporting phục vụ PS1–PS5',
     'Đây là quy tắc phân bổ số học', 'đã chốt'),
    *[('docs/star_schema_tu_ps.md', '## 1. Từ câu hỏi nghiệp vụ tới grain', f'| PS{i}:', 'đã chốt')
      for i in (1, 3, 4, 5)],
    ('docs/star_schema_tu_ps.md', '## 5. Mức hoàn thành so với nghiệp vụ',
     '**Đã làm (2026-09-27):**', 'đã chốt'),
    ('docs/ai_explain_plan.md', '### 0.2. Ba quy ước nghiệp vụ cần ghi đúng trạng thái',
     '| PS4 theo giai đoạn:', 'đề xuất'),
    ('docs/ai_explain_plan.md', '### 0.2. Ba quy ước nghiệp vụ cần ghi đúng trạng thái',
     '| `driver_rule.min_abs_delta_rate', 'đề xuất'),
    ('docs/ai_explain_plan.md', '### 0.2. Ba quy ước nghiệp vụ cần ghi đúng trạng thái',
     '| PS3: năm ranh giới', 'đề xuất'),
    ('docs/data-dictionary.md', '### 1.1 Câu chuyện vận hành',
     'Promotion áp dụng cho dòng hàng', 'đã chốt'),
    ('docs/data-dictionary.md', '### 3.4 `promotions.csv`',
     '**Grain:** một đợt promotion', 'đã chốt'),
    ('docs/data-dictionary.md', '### 3.4 `promotions.csv`',
     'Promotion tương lai sau', 'đã chốt'),
    *[('CLAUDE.md', '## 5. Những gì ĐÃ kết luận — đừng dò lại từ đầu', f'{i}. **', 'đã kiểm chứng')
      for i in range(1, 9)],
    ('CLAUDE.md', '### Ràng buộc chi phối mọi lựa chọn feature',
     '**Mọi bảng phụ', 'đã kiểm chứng'),
    ('docs/hop_dong_du_bao.md', '### 2.1 Hợp đồng metric',
     '| Metric |', 'đã chốt'),
    ('docs/hop_dong_du_bao.md', '### 2.1 Hợp đồng metric',
     '| Tập dữ liệu |', 'đã chốt'),
    ('docs/hop_dong_du_bao.md', '### 2.1 Hợp đồng metric',
     '| Horizon |', 'đã chốt'),
    ('docs/hop_dong_du_bao.md', '### 2.3 COGS',
     '**Chốt 2026-10-14', 'đã chốt'),
    ('docs/hop_dong_du_bao.md', '## 3. Biến ngoại sinh: chỉ suy từ lịch',
     '| Cờ cho cả 6 họ khuyến mãi', 'đã chốt'),
    ('docs/hop_dong_du_bao.md', '## 5. Backtest',
     '**Luật chọn ứng viên**', 'đã chốt'),
    ('docs/hop_dong_du_bao.md', '## 7. Đầu ra cho B2 và B3 (đã có trong code từ 2026-10-15)',
     '**Phục vụ AI agent**', 'đã chốt'),
]


def _tracked(path: str) -> None:
    if not (ROOT / path).is_file() or Path(path).is_absolute() or '..' in Path(path).parts:
        raise ValueError(f'Nguồn không hợp lệ: {path}')
    if subprocess.run(['git', 'ls-files', '--error-unmatch', '--', path], cwd=ROOT,
                      capture_output=True).returncode:
        raise ValueError(f'Nguồn chưa được git theo dõi: {path}')
    # --no-index để phát hiện cả file đã tracked nhưng nay khớp .gitignore/.git/info/exclude.
    if subprocess.run(['git', 'check-ignore', '--no-index', '-q', '--', path], cwd=ROOT).returncode == 0:
        raise ValueError(f'Nguồn bị ignore/exclude: {path}')


def _section(path: str, heading: str) -> str:
    lines = (ROOT / path).read_text(encoding='utf-8').splitlines()
    hits = [i for i, line in enumerate(lines) if line.strip() == heading]
    if len(hits) != 1:
        raise ValueError(f'Không thấy duy nhất mục {path} {heading}')
    start = hits[0] + 1
    level = len(heading) - len(heading.lstrip('#'))
    end = next((i for i in range(start, len(lines))
                if (m := re.match(r'^(#{1,6}) ', lines[i])) and len(m[1]) <= level), len(lines))
    return '\n'.join(lines[start:end])


def build() -> dict:
    cache, records = {}, []
    for path, heading, anchor, status in SOURCES:
        _tracked(path)
        body = cache.setdefault((path, heading), _section(path, heading))
        if anchor.startswith('|'):
            found = [line.strip() for line in body.splitlines() if line.strip().startswith(anchor)]
        else:
            found = [re.sub(r'\s+', ' ', block).strip() for block in re.split(r'\n\s*\n', body)
                     if anchor in block]
        if len(found) != 1:
            raise ValueError(f'{path} {heading} {anchor!r}: cần đúng một đoạn, thấy {len(found)}')
        section = heading.lstrip('#').strip()
        records.append({'source_path': path, 'section': section, 'status': status, 'text': found[0]})
    content = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    version = hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    return {'corpus_version': version, 'records': records}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='so bản chụp với nguồn, không ghi file')
    a = ap.parse_args()
    built = build()
    data = json.dumps(built, ensure_ascii=False, indent=2) + '\n'
    if a.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding='utf-8') != data:
            print('Bản chụp corpus lệch nguồn; chạy lại script để cập nhật.')
            return 1
        print(f"Corpus khớp nguồn: {len(built['records'])} đoạn, version {built['corpus_version']}")
        return 0
    OUTPUT.write_text(data, encoding='utf-8')
    print(f"Đã ghi {OUTPUT.relative_to(ROOT)}: {len(built['records'])} đoạn, version {built['corpus_version']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
