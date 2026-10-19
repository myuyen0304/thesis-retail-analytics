"""Luật chọn, bảng ghi cho dbt và cách stage dự báo nối vào pipeline. Không train model (chạy nhanh)."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'apps/retail_app'))
from scripts.forecast import core, stage
from scripts.pipeline import cli, snapshot
from scripts.pipeline.state import Registry, atomic_json


def scores(spec):
    """spec: {(model, cogs_method): [điểm F1, F2, F3]}; luôn có mốc sàn 100 ở mọi fold."""
    spec = {(core.FLOOR, 'copy'): [100, 100, 100], **spec}
    return pd.DataFrame([dict(model=m, cogs_method=c, fold=f, score=v)
                         for (m, c), vals in spec.items() for f, v in zip(core.FOLDS, vals)])


@pytest.mark.parametrize('lang', ['C.UTF-8', 'en_US.UTF-8', 'vi_VN.UTF-8'])
def test_tet_dates_do_not_depend_on_locale(monkeypatch, lang):
    """Image Airflow có LANG=C.UTF-8: holidays trả tên tiếng Việt nếu không cố định language (lỗi Docker 2026-10-15)."""
    monkeypatch.setenv('LANG', lang)
    monkeypatch.delenv('LANGUAGE', raising=False)
    monkeypatch.delenv('LC_ALL', raising=False)
    assert core.tet_dates([2023, 2024]) == {2023: pd.Timestamp('2023-01-22'), 2024: pd.Timestamp('2024-02-10')}


def test_lowest_score_wins():
    _, pick, step = core.select(scores({('lgbm_full', 'direct'): [80, 80, 80], ('sarimax_full', 'ratio'): [85, 85, 85]}))
    assert pick == ('lgbm_full', 'direct') and step == 'buoc_2_diem_thap_nhat'


def test_tie_within_one_percent_picks_simpler():
    # bản gộp thấp nhất, LightGBM chỉ kém 0,6% → hòa → LightGBM đơn giản hơn
    _, pick, step = core.select(scores({('lgbm_full', 'direct'): [80, 80, 80], ('blend_full', 'direct'): [79.5, 79.5, 79.5]}))
    assert pick == ('lgbm_full', 'direct') and step == 'buoc_3_hoa_chon_don_gian'


def test_floor_must_be_beaten_in_every_fold():
    # thua mốc ở F2 thì không qua sàn, dù điểm trung bình thấp hơn
    _, pick, step = core.select(scores({('lgbm_full', 'direct'): [50, 101, 50]}))
    assert pick == (core.FLOOR, 'copy') and step == 'buoc_1_khong_ung_vien_nao_qua_san'


def test_sql_rule_uses_same_tie_and_floor():
    sql = (ROOT / 'retail_dbt/tests/assert_rpt_forecast.sql').read_text(encoding='utf-8')
    assert core.TIE == 0.01 and '(1 + 0.01)' in sql
    assert "role = 'floor'" in sql and core.FLOOR == 'naive2y'
    assert list(core.RANK) == core.CANDIDATES and core.RANK[core.CANDIDATES[0]] == 0


def test_backtest_table_has_rule_inputs_for_every_row():
    folds = list(core.FOLDS)
    rows = [dict(model=m, cogs_method=c, fold=f, **{k: 1.0 for k in stage.BACKTEST_METRICS})
            for m, c in [(core.FLOOR, 'copy'), ('naive1y', 'copy'), ('lgbm_full', 'direct')] for f in folds]
    result = {'report': pd.DataFrame(rows), 'weights': {('F1', 'direct'): 1.0}}
    out = stage.backtest_table(result)
    assert set(out.role) == {'floor', 'baseline', 'candidate'}
    assert out[out.model == 'lgbm_full'].candidate_rank.eq(core.RANK[('lgbm_full', 'direct')]).all()
    assert out[out.role != 'candidate'].candidate_rank.isna().all()
    for metric in ('mae_g', 'mae_cogs', 'mape_g_thang'):
        assert len(out[out.metric == metric]) == 9
    assert len(out[out.metric == 'blend_weight_lgbm']) == 1


def test_stage_reuses_output_of_same_snapshot_and_code(tmp_path):
    out = tmp_path / 'forecast'
    out.mkdir()
    for f in stage.FILES:
        (out / f).write_bytes(b'x')
    meta = {'snapshot_id': 'abc', 'model_version': stage.model_version(),
            'sha256': {f: stage._digest(out / f) for f in stage.FILES}}
    (out / 'forecast_meta.json').write_text(json.dumps(meta), encoding='utf-8')
    # snapshot không tồn tại: nếu stage train lại thì sẽ lỗi đọc file
    assert stage.run(tmp_path / 'missing', out, run_id='r', snapshot_id='abc') == meta
    with pytest.raises(FileNotFoundError):
        stage.run(tmp_path / 'missing', out, run_id='r', snapshot_id='khac')


def test_code_version_covers_forecast_code(tmp_path, monkeypatch):
    (tmp_path / 'retail_dbt').mkdir()
    for name in ('dbt_project.yml', 'profiles.yml'):
        (tmp_path / 'retail_dbt' / name).write_text('x', encoding='utf-8')
    code = tmp_path / 'scripts/forecast/core.py'
    code.parent.mkdir(parents=True)
    code.write_text('TIE = 0.01', encoding='utf-8')
    monkeypatch.setattr(cli, 'ROOT', tmp_path)
    before = cli.code_version()
    code.write_text('TIE = 0.02', encoding='utf-8')
    assert cli.code_version() != before


def test_build_runs_forecast_before_dbt(tmp_path, monkeypatch):
    # S2 (2026-10-18): dự báo là stage riêng `forecast` chạy xong trước; build chỉ truyền forecast_path cho dbt, không train
    Registry(tmp_path).initialize()
    folder = tmp_path / 'runs/demo'
    atomic_json(folder / 'context.json', {'run_id': 'demo', 'release_id': 'b' * 24, 'snapshot_id': 's1', 'code_version': 'v1',
                                          'stage': 'prepared', 'target': 'duckdb', 'directory': str(folder),
                                          'snapshot_path': '/snapshot', 'duckdb_path': str(folder / 'dbt.duckdb')})
    monkeypatch.setattr(cli, 'code_version', lambda: 'v1')
    monkeypatch.setattr(snapshot, 'validate', lambda path: {})
    calls = []
    monkeypatch.setattr(cli, 'forecast_stage', lambda ctx: calls.append('forecast') or ('/fc', {'primary': ['lgbm_full', 'direct']}))
    monkeypatch.setattr(cli, 'check_forecast', lambda ctx: calls.append(('check', ctx['forecast_path'])))
    monkeypatch.setattr(cli, 'dbt_build', lambda ctx, target, cloud=None: calls.append(('dbt', ctx['forecast_path'])))
    context = cli.execute('forecast', run_id='demo', root=tmp_path)
    assert calls == ['forecast'] and context['stage'] == 'forecasted'
    assert context['forecast']['primary'] == ['lgbm_full', 'direct']
    context = cli.execute('build', run_id='demo', root=tmp_path)
    assert calls == ['forecast', ('check', '/fc'), ('dbt', '/fc')] and context['stage'] == 'built'


def test_dbt_build_passes_forecast_path_as_var(tmp_path, monkeypatch):
    seen = {}

    def fake_run(args, **kwargs):
        seen['vars'] = json.loads(args[args.index('--vars') + 1])
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(cli.subprocess, 'run', fake_run)
    context = {'directory': str(tmp_path), 'duckdb_path': str(tmp_path / 'x.duckdb'), 'release_id': 'c' * 24,
               'snapshot_id': 's', 'code_version': 'v', 'snapshot_path': '/s', 'forecast_path': '/fc'}
    with pytest.raises(ValueError):
        cli.dbt_build(context, 'duckdb')
    assert seen['vars']['forecast_path'] == '/fc'
