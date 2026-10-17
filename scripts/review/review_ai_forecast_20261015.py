"""Tái hiện review Codex của B3: tool đọc kho thật, provider giả cố tình trả sai.

Chạy từ root: .venv/Scripts/python.exe scripts/review/review_ai_forecast_20261015.py
Không gọi LLM/API, không sửa kho hay huấn luyện model. Exit 1 nếu còn câu sai được chấp nhận.
"""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps' / 'retail_app'))

from ai_explain import service
from dwh import releases
from tests.test_ai_chat import FakeProvider, call, final


def main():
    os.environ['RETAIL_RELEASE_MODE'] = 'versioned'
    os.environ['RETAIL_RELEASE_STATE'] = str(ROOT / 'warehouse/pipeline/state.json')
    releases.reset()
    month = dict(metric='G_and_COGS', period='month', year=2023, month=8)
    cases = [
        ('CONTROL', 'Dự báo doanh thu tháng 8/2023?', month,
         'Dự báo G tháng 8/2023 là {c1}.', 'T1.rows[0].g_forecast', True),
        ('R01_wrong_period', 'Dự báo doanh thu tháng 8/2023?',
         dict(metric='G', period='year', year=2023),
         'Dự báo G tháng 8/2023 là {c1}.', 'T1.rows[0].g_forecast', False),
        ('R02_actual_as_forecast', 'Doanh thu thực tế tháng 8/2023 là bao nhiêu?', month,
         'Doanh thu thực tế tháng 8/2023 là {c1}.', 'T1.rows[0].g_forecast', False),
        ('R03_g_as_cogs', 'Dự báo giá vốn COGS tháng 8/2023?', month,
         'Dự báo COGS tháng 8/2023 là {c1}.', 'T1.rows[0].g_forecast', False),
        ('R04_cogs_as_g', 'Dự báo G tháng 8/2023?', month,
         'Dự báo G tháng 8/2023 là {c1}.', 'T1.rows[0].cogs_forecast', False),
        ('R05_outside_horizon', 'Dự báo doanh thu năm 2025?',
         dict(metric='G', period='year', year=2023),
         'Dự báo doanh thu năm 2025 là {c1}.', 'T1.rows[0].g_forecast', False),
        ('R06_ignored_model', 'Dùng SARIMAX toàn chuỗi, COGS qua tỷ lệ, dự báo tháng 8/2023?', month,
         'Dự báo G tháng 8/2023 là {c1}.', 'T1.rows[0].g_forecast', False),
        ('R07_ranking_metric', 'Theo MAPE G tháng, model nào chính xác nhất?', {},
         'Theo MAPE G tháng, model chính xác nhất là {c1}.',
         'T1.derived.lowest_score.candidates', False),
    ]
    outcomes = []
    for cid, question, args, answer, path, should_pass in cases:
        tool = 'get_forecast_backtest' if cid.startswith('R07') else 'get_forecast'
        reply = final(answer=answer, claims=[{'id': 'c1', 'path': path}])
        turn = service.run_turn(question, [], 'duckdb', FakeProvider(call(tool, **args), reply, reply))
        outcomes.append(dict(case=cid, question=question, tool=tool, arguments=args, path=path,
                             expected_ok=should_pass, status=turn.status,
                             finding=turn.status == 'ok' and not should_pass,
                             answer=turn.answer_md, errors=turn.validation_errors,
                             tool_statuses={k: v.status for k, v in turn.results.items()},
                             release_ids=[r.evidence.data_version.get('release_id')
                                          for r in turn.results.values() if r.evidence]))
    paths = ['apps/retail_app/ai_explain/' + f for f in
             ('service.py', 'evidence.py', 'tools.py', 'metric_catalog.py')]
    payload = dict(provider='FakeProvider; không phải live LLM eval',
                   sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}, cases=outcomes)
    out = ROOT / 'warehouse/reviews/ai_gd2_20261015'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'adversarial.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return int(any(x['finding'] or (x['expected_ok'] and x['status'] != 'ok') for x in outcomes))


if __name__ == '__main__':
    raise SystemExit(main())
