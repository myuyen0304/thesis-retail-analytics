"""Kiểm độc lập sau RV01–RV06: provider giả, tool đọc local; không sửa kho."""
import hashlib
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
    month = dict(metric='G_and_COGS', period='month', year=2023, month=8)
    cases = [
        ('C01_ratio_correct', 'Dự báo tỷ lệ COGS/G tháng 8/2023?',
         'Dự báo tỷ lệ COGS/G tháng 8/2023 là {c1}.', 'cogs_ratio', True),
        ('N01_money_as_ratio', 'Dự báo tỷ lệ COGS/G tháng 8/2023?',
         'Dự báo tỷ lệ COGS/G tháng 8/2023 là {c1}.', 'g_forecast', False),
        ('N02_ratio_as_money', 'Dự báo doanh thu G tháng 8/2023?',
         'Dự báo doanh thu G tháng 8/2023 là {c1}.', 'cogs_ratio', False),
        ('C02_month_in_quarter', 'Dự báo doanh thu quý 3/2023?',
         'Riêng tháng 8/2023, dự báo G là {c1}.', 'g_forecast', True),
        ('N03_month_as_quarter_total', 'Dự báo tổng doanh thu quý 3/2023?',
         'Tổng doanh thu G dự báo quý 3/2023 là {c1}.', 'g_forecast', False),
        ('N04_invalid_quarter', 'Dự báo doanh thu quý 5/2023?',
         'Dự báo G là {c1}.', 'g_forecast', False),
    ]
    outcomes = []
    for name, question, answer, field, expected_ok in cases:
        reply = final(answer=answer, claims=[{'id': 'c1', 'path': 'T1.rows[0].' + field}])
        try:
            turn = service.run_turn(question, [], 'duckdb', FakeProvider(call('get_forecast', **month), reply, reply))
            item = dict(case=name, expected_ok=expected_ok, status=turn.status, answer=turn.answer_md,
                        errors=turn.validation_errors, finding=(turn.status == 'ok') != expected_ok)
        except Exception as exc:
            item = dict(case=name, expected_ok=expected_ok, status='uncaught_exception',
                        error=f'{type(exc).__name__}: {exc}', finding=True)
        outcomes.append(dict(item, question=question, template=answer, field=field))
    # RV09: trạng thái hỏi lại vẫn phải từ chối claim số của kỳ khác khi kỳ người dùng không hợp lệ.
    question = 'Dự báo doanh thu quý 5/2023?'
    answer = 'Bạn muốn hỏi quý nào? Trong lúc chờ, dự báo G tháng 8/2023 là {c1}.'
    reply = final('needs_clarification', answer, [{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}])
    try:
        turn = service.run_turn(question, [], 'duckdb', FakeProvider(call('get_forecast', **month), reply, reply))
        outcomes.append(dict(case='N05_invalid_quarter_with_numeric_clarification', question=question,
                             template=answer, field='g_forecast', expected_ok=False, status=turn.status,
                             answer=turn.answer_md, errors=turn.validation_errors,
                             finding=turn.status == 'needs_clarification' and bool(turn.answer_md)))
    except Exception as exc:
        outcomes.append(dict(case='N05_invalid_quarter_with_numeric_clarification', question=question,
                             expected_ok=False, status='uncaught_exception',
                             error=f'{type(exc).__name__}: {exc}', finding=True))
    payload = dict(provider='FakeProvider; không phải live LLM eval',
                   evidence_sha256=hashlib.sha256((ROOT / 'apps/retail_app/ai_explain/evidence.py').read_bytes()).hexdigest(),
                   cases=outcomes)
    out = ROOT / 'warehouse/reviews/ai_gd2_20261015/rereview_adversarial.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return int(any(item['finding'] for item in outcomes))


if __name__ == '__main__':
    raise SystemExit(main())
