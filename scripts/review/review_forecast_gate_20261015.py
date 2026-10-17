"""Review cổng chất lượng dự báo bằng bản sao trong RAM; không sửa bản đã publish.

Chạy từ root: .venv/Scripts/python.exe scripts/review/review_forecast_gate_20261015.py
Thực thi SQL test thật với các macro thuần được render cho DuckDB. Không chạy pipeline hay gọi cloud.
"""
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import duckdb
from jinja2 import Environment, StrictUndefined
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.pipeline import cli


def main():
    state_path = ROOT / 'warehouse/pipeline/state.json'
    state = json.loads(state_path.read_text(encoding='utf-8'))['payload']
    record = state['releases'][state['active']]
    folder = state_path.parent / 'runs' / record['run_id'] / 'forecast'
    daily = pd.read_parquet(folder / 'forecast_daily.parquet')
    backtest = pd.read_parquet(folder / 'forecast_backtest.parquet')
    sales = pd.read_csv(ROOT / 'data/sales.csv')
    actual = pd.DataFrame(dict(date_sk=pd.to_datetime(sales.Date).dt.strftime('%Y%m%d').astype(int),
                               revenue=sales.Revenue, cogs=sales.COGS, is_actual=True))
    source = ROOT / 'retail_dbt/tests/assert_rpt_forecast.sql'
    env = Environment(undefined=StrictUndefined)
    sql = env.from_string(source.read_text(encoding='utf-8')).render(
        ref=lambda name: name, type_double=lambda: 'DOUBLE',
        date_sk=lambda expr: f"cast(strftime({expr}, '%Y%m%d') as integer)",
        dbt=SimpleNamespace(datediff=lambda start, end, unit: f"date_diff('{unit}', {start}, {end})"))
    outcomes = []

    def check(name, d, b, should_pass=False):
        with duckdb.connect(':memory:') as con:
            con.register('rpt_forecast_daily', d)
            con.register('rpt_forecast_backtest', b)
            con.register('fact_daily_sales', actual)
            violations = con.execute(sql).fetchall()
        outcomes.append(dict(case=name, expected_pass=should_pass, accepted=not violations,
                             finding=not violations and not should_pass, violations=violations))
        if should_pass and violations:
            raise RuntimeError(f'Bản đối chứng không đạt: {violations}')

    check('CONTROL', daily, backtest, True)
    d = daily.copy()
    d.loc[d.is_primary, 'lower'] = float('nan')
    d.loc[d.is_primary, 'upper'] = float('nan')
    check('Q01_null_intervals', d, backtest)
    d = daily.copy()
    d.loc[d.is_primary, 'interval_level'] = 0.5
    check('Q02_wrong_interval_level', d, backtest)
    b = backtest.copy()
    b.loc[(b.model == 'sarimax_full') & (b.cogs_method == 'ratio') & (b.metric == 'score'), 'value'] = 1.0
    check('Q03_score_disagrees_with_mae', daily, b)
    d = daily.copy()
    d.loc[d.is_primary, 'selection_step'] = 'buoc_1_khong_ung_vien_nao_qua_san'
    check('Q04_wrong_selection_reason', d, backtest)

    _, ai = cli.consumers()
    optional = {'reporting.rpt_forecast_daily', 'reporting.rpt_forecast_backtest'}
    payload = dict(release_id=record['release_id'], source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                   cases=outcomes, pipeline_missing_forecast_relations=sorted(optional - set(ai)),
                   note='Không gọi Databricks; kiểm danh sách cấp quyền từ code pipeline hiện tại.')
    out = ROOT / 'warehouse/reviews/ai_gd2_20261015'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'quality_gate.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return int(any(x['finding'] for x in outcomes) or bool(payload['pipeline_missing_forecast_relations']))


if __name__ == '__main__':
    raise SystemExit(main())
