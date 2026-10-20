"""Phát lại câu thô của 8 lượt live L4 qua guard nhân quả hiện tại; không gọi mô hình hay DWH."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps' / 'retail_app'))

from ai_explain.evidence import forecast_question_errors  # noqa: E402

LOGS = ROOT / 'warehouse' / 'ai_eval'
CAUSAL_ERROR = 'phân rã model không chứng minh nguyên nhân'


def main() -> int:
    paths = sorted(LOGS.glob('live_20261019T*_l4_*.jsonl'))
    if not paths:
        print('BỎ QUA: không có log live L4 ngày 2026-10-19 trong warehouse/ai_eval.')
        return 0
    if len(paths) != 8:
        print(f'LỖI: cần 8 log L4, tìm thấy {len(paths)}: {[p.name for p in paths]}')
        return 1

    # Chỉ phát lại guard nhân quả: log lưu raw_final, không lưu ToolResult để dựng lại evidence số.
    explain_result = SimpleNamespace(ok=True, evidence=SimpleNamespace(tool='explain_forecast'))
    reviewed = skipped = 0
    failures = []
    for path in paths:
        records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
        if len(records) != 4:
            failures.append(f'{path.name}: cần 4 case L401–L404, có {len(records)}')
        for record in records:
            raw = record.get('raw_final')
            if not raw:
                skipped += 1  # lượt provider_error không có câu để phát lại
                continue
            try:
                answer = json.loads(raw)['answer']
            except (KeyError, TypeError, ValueError) as exc:
                failures.append(f"{path.name}/{record['case_id']}: raw_final không đọc được: {exc}")
                continue
            errors = forecast_question_errors(record['question'], {}, {'T1': explain_result}, answer)
            reviewed += 1
            if any(CAUSAL_ERROR in error for error in errors):
                failures.append(f"{path.name}/{record['case_id']}: {CAUSAL_ERROR}")
    print(f'Phát lại {len(paths)} log L4: {reviewed} raw_final đã kiểm, {skipped} lượt không có raw_final; '
          f'{len(failures)} lỗi nhân quả/cấu trúc log.')
    for failure in failures:
        print(f'LỖI: {failure}')
    return int(bool(failures))


if __name__ == '__main__':
    sys.exit(main())
