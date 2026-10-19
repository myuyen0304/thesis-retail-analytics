"""Stage dự báo của pipeline (B2b): train từ snapshot, áp luật chọn, ghi parquet cho dbt.

Chạy trong stage `build` của `scripts/pipeline/cli.py`, trước dbt. dbt đọc hai file parquet thành
`reporting.rpt_forecast_daily` và `reporting.rpt_forecast_backtest` của bản dữ liệu (hợp đồng §7).
Kết quả cùng số với notebook `notebooks/04_forecasting/so_sanh_model.ipynb` vì cả hai dùng `scripts/forecast/core.py`.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import tempfile
import time

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
FILES = ('forecast_daily.parquet', 'forecast_backtest.parquet', 'forecast_explain.parquet')

# Chỉ số ghi vào rpt_forecast_backtest, kèm grain (hợp đồng §5, §7)
BACKTEST_METRICS = {'mae_g': 'ngay', 'mae_cogs': 'ngay', 'score': 'ngay', 'rmse_g': 'ngay', 'rmse_cogs': 'ngay',
                    'r2_g': 'ngay', 'r2_cogs': 'ngay', 'mape_g_thang_%': 'thang', 'mae_g_t8_2021': 'thang_8_2021',
                    'tai_tao_bien_do': 'thang_8_2021', 'cogs_g_t8_du_bao': 'thang_8_2021', 'coverage_80': 'ngay'}


def model_version():
    """Hash code dự báo (không tính test): đổi model, biến hay luật thì đổi version."""
    h = hashlib.sha256()
    for p in sorted(HERE.glob('*.py')):
        h.update(p.name.encode())
        h.update(p.read_bytes().replace(b'\r\n', b'\n'))
    return h.hexdigest()[:12]


def _digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def _versions():
    import lightgbm, statsmodels, holidays, scipy
    return {'python': platform.python_version(), 'pandas': pd.__version__, 'numpy': np.__version__,
            'statsmodels': statsmodels.__version__, 'lightgbm': lightgbm.__version__,
            'holidays': holidays.__version__, 'scipy': scipy.__version__}


def daily_table(result, run_id, version):
    out = result['final'].copy()
    out['forecast_date'] = pd.to_datetime(out['forecast_date']).dt.date
    out['model_version'] = version
    out['run_id'] = run_id
    cols = ['forecast_date', 'model', 'cogs_method', 'model_version', 'run_id', 'trained_through', 'is_primary',
            'selection_step', 'yhat', 'lower', 'upper', 'interval_level', 'cogs_ratio_hat', 'cogs_yhat']
    return out[cols]


def backtest_table(result):
    from scripts.forecast import core
    rep = result['report']
    rows = []
    for _, r in rep.iterrows():
        cand = (r.model, r.cogs_method)
        role = 'floor' if r.model == core.FLOOR else ('baseline' if r.model in core.BASELINES else 'candidate')
        for metric, grain in BACKTEST_METRICS.items():
            rows.append(dict(model=r.model, cogs_method=r.cogs_method, role=role, candidate_rank=core.RANK.get(cand),
                             fold_origin=core.FOLDS[r.fold].date(), metric=metric.replace('_%', ''), grain=grain,
                             value=float(r[metric])))
    for (fold, c), w in result['weights'].items():   # trọng số LightGBM của bản gộp, để agent giải thích được
        rows.append(dict(model='blend_full', cogs_method=c, role='candidate', candidate_rank=core.RANK[('blend_full', c)],
                         fold_origin=core.FOLDS[fold].date(), metric='blend_weight_lgbm', grain='fold', value=float(w)))
    out = pd.DataFrame(rows)
    out['candidate_rank'] = out['candidate_rank'].astype('Int64')
    return out


def feature_group(name):
    """Ánh xạ đầy đủ feature của LightGBM; biến mới phải được phân nhóm tường minh."""
    if name.startswith(('sin', 'cos')) or name in ('month', 'doy', 'tet_diff'):
        return 'mua_vu'
    if name in ('dom', 'days_to_eom') or name.startswith(('is_last', 'is_first')):
        return 'dau_cuoi_thang'
    if name.startswith('promo_'):
        return name.removesuffix('_since')
    if name == 'post2019':
        return 'che_do_sau_2018'
    if name == 'is_odd_year':
        return 'nam_chan_le'
    raise ValueError(f'Feature chưa có nhóm giải thích: {name}')


def explain_table(result, run_id, version):
    """Một ngày × nhóm biến; đóng góp cộng trên log(G), hệ số exp để diễn đạt trên thang tiền.

    exp(đóng góp log) là hệ số nhân riêng lẻ, không phải VND hay phần trăm cộng được.
    Nếu model chính không phải LightGBM, để bảng rỗng và không gán giải thích của model khác.
    """
    columns = ['forecast_date', 'model', 'cogs_method', 'model_version', 'run_id', 'trained_through',
               'feature_group', 'expected_groups', 'base_log', 'contribution_log', 'forecast_log', 'multiplier']
    if result['primary'][0] != 'lgbm_full':
        return pd.DataFrame({c: pd.Series(dtype='float64' if c in
                             ('base_log', 'contribution_log', 'forecast_log', 'multiplier') else 'str') for c in columns})
    primary = result['final'].loc[result['final'].is_primary].sort_values('forecast_date')
    dates = pd.DatetimeIndex(primary.forecast_date)
    names, raw, forecast_log = result['forecaster'].explain_log_g('lgbm_full', result['forecaster'].sales.index.max(), dates)
    groups = pd.Series([feature_group(n) for n in names], index=names)
    grouped = pd.DataFrame(raw[:, :-1], columns=names).T.groupby(groups, sort=True).sum().T
    base_log = raw[:, -1]
    if not np.allclose(base_log + grouped.sum(axis=1).to_numpy(), forecast_log, rtol=0, atol=1e-8):
        raise ValueError('Nhóm đóng góp không cộng về log(G) dự báo')
    if not np.allclose(np.exp(forecast_log), primary.yhat.to_numpy(), rtol=1e-10, atol=1e-6):
        raise ValueError('Phân rã log(G) không khớp yhat của ứng viên chính')
    out = grouped.assign(forecast_date=dates.date).melt(id_vars='forecast_date', var_name='feature_group',
                                                         value_name='contribution_log')
    by_date = {d.date(): (float(b), float(y)) for d, b, y in zip(dates, base_log, forecast_log)}
    out['expected_groups'] = len(grouped.columns)
    out['base_log'] = out.forecast_date.map(lambda d: by_date[d][0])
    out['forecast_log'] = out.forecast_date.map(lambda d: by_date[d][1])
    out['multiplier'] = np.exp(out.contribution_log)
    out['model'], out['cogs_method'] = result['primary']
    out['model_version'], out['run_id'] = version, run_id
    out['trained_through'] = result['forecaster'].sales.index.max().date()
    return out[columns]


def run(snapshot_path, out_dir, *, run_id, snapshot_id, progress=None):
    """Ghi ba parquet dự báo và forecast_meta.json vào out_dir.
    Chạy lại trên cùng snapshot và cùng code thì dùng lại kết quả đã kiểm hash, không train lại."""
    from scripts.forecast import core
    snapshot_path, out_dir = Path(snapshot_path), Path(out_dir)
    version = model_version()
    meta_path = out_dir / 'forecast_meta.json'
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        if (meta.get('snapshot_id') == snapshot_id and meta.get('model_version') == version
                and all((out_dir / f).exists() and _digest(out_dir / f) == meta['sha256'][f] for f in FILES)):
            return meta
    started = time.time()
    sales = core.load_sales(pd.read_parquet(snapshot_path / 'sales.parquet'))
    promotions = core.load_promotions(pd.read_parquet(snapshot_path / 'promotions.parquet'))
    horizon = pd.DatetimeIndex(pd.to_datetime(pd.read_parquet(snapshot_path / 'sample_submission.parquet')['Date']))
    expected = pd.date_range(sales.index.max() + pd.Timedelta(days=1), periods=core.H)
    if not horizon.equals(expected):
        raise ValueError('Vùng dự báo trong sample_submission không phải 548 ngày liền sau ngày thực tế cuối')
    result = core.run(sales, promotions, horizon, progress)
    daily = daily_table(result, run_id, version)
    backtest = backtest_table(result)
    explain = explain_table(result, run_id, version)

    out_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='forecast-', dir=out_dir.parent) as tmp:
        tmp = Path(tmp)
        daily.to_parquet(tmp / FILES[0], index=False)
        backtest.to_parquet(tmp / FILES[1], index=False)
        explain.to_parquet(tmp / FILES[2], index=False)
        fits = result['fits']
        meta = {'snapshot_id': snapshot_id, 'model_version': version, 'run_id': run_id,
                'primary': list(result['primary']), 'selection_step': result['step'],
                'use_tet': result['cal'].use_tet, 'use_first': result['cal'].use_first,
                'blend_weights_final': result['final_weights'],
                'fits': int(len(fits)), 'fits_fallback': int(fits.du_phong.sum()) if len(fits) else 0,
                'rows_daily': int(len(daily)), 'rows_backtest': int(len(backtest)),
                'rows_explain': int(len(explain)),
                'seconds': round(time.time() - started), 'versions': _versions(),
                'finished_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                'sha256': {f: _digest(tmp / f) for f in FILES}}
        (tmp / 'forecast_meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
        if out_dir.exists():
            shutil.rmtree(out_dir)
        os.replace(tmp, out_dir)
        tmp.mkdir()   # TemporaryDirectory dọn thư mục trống này
    return meta
