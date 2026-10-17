"""Kiểm số dự báo được dẫn trong câu trả lời trạng thái no_data."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/retail_app'))
from ai_explain import service
from dwh import releases
from tests.test_ai_chat import FakeProvider, call, final


def main():
    os.environ['RETAIL_RELEASE_MODE'] = 'versioned'
    os.environ['RETAIL_RELEASE_STATE'] = str(ROOT / 'warehouse/pipeline/state.json')
    releases.reset()
    question = 'Dự báo doanh thu năm 2025?'
    tool = call('get_forecast', metric='G', period='month', year=2023, month=8)
    cases = [
        ('CONTROL_alternative_labeled',
         'Chưa có dự báo năm 2025. Riêng tháng 8/2023, dự báo G là {c1}.', True),
        ('N06_forecast_2023_as_2025', 'Dự báo G năm 2025 là {c1}.', False),
    ]
    outcomes = []
    for name, answer, valid in cases:
        reply = final('no_data', answer, [{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}])
        turn = service.run_turn(question, [], 'duckdb', FakeProvider(tool, reply, reply))
        outcomes.append(dict(case=name, expected_valid=valid, status=turn.status, answer=turn.answer_md,
                             errors=turn.validation_errors,
                             finding=(turn.status == 'no_data' and bool(turn.answer_md)) != valid))
    payload = dict(provider='FakeProvider; không phải live LLM eval', cases=outcomes)
    out = ROOT / 'warehouse/reviews/ai_gd2_20261015/nonok_period.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return int(any(x['finding'] for x in outcomes))


if __name__ == '__main__':
    raise SystemExit(main())
