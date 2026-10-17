"""So output stage dự báo của hai lần chạy pipeline (vd. Windows và Airflow Docker, khác bản Python).

Chạy từ root:
    .venv/Scripts/python.exe -m scripts.ops.so_sanh_du_bao warehouse/pipeline/runs/b3b-01 \
        warehouse/pipeline/docker/runs/9aa80137c3adf8d7f1e341e8
In: ứng viên chính, điểm ngày từng ứng viên và % lệch, khoảng cách tới ngưỡng hòa, lệch dự báo theo ngày từng ứng viên,
tổng tháng của ứng viên chính. Không ghi file.
"""
import json
import sys
from pathlib import Path

import pandas as pd

from scripts.forecast import core


def load(run_dir: Path):
    f = run_dir / 'forecast'
    return (pd.read_parquet(f / 'forecast_daily.parquet'), pd.read_parquet(f / 'forecast_backtest.parquet'),
            json.loads((f / 'forecast_meta.json').read_text(encoding='utf-8')))


def main(a: str, b: str) -> int:
    (da, ba, ma), (db, bb, mb) = load(Path(a)), load(Path(b))
    for name, m in (('A', ma), ('B', mb)):
        print(f"{name}: {m['run_id']} · snapshot {m['snapshot_id']} · model_version {m['model_version']} · "
              f"python {m['versions']['python']} · chính {m['primary']} ({m['selection_step']}) · "
              f"fit dự phòng {m['fits_fallback']}/{m['fits']} · {m['seconds']} giây")
    score = lambda bt: bt[bt.metric == 'score'].groupby(['model', 'cogs_method', 'role']).value.mean()
    s = pd.DataFrame({'A': score(ba), 'B': score(bb)})
    s['lech_%'] = (s.B / s.A - 1) * 100
    for col in ('A', 'B'):
        best = s.loc[s.index.get_level_values('role') == 'candidate', col].min()
        s[f'cach_thap_nhat_{col}_%'] = (s[col] / best - 1) * 100
    print(f'\nĐiểm ngày kết hợp (TB 3 fold); ngưỡng hòa {core.TIE * 100:g}% so với ứng viên thấp nhất:')
    print(s.sort_values('A').to_string(float_format=lambda v: f'{v:,.4f}'))
    k = ['forecast_date', 'model', 'cogs_method']
    j = da.merge(db, on=k, suffixes=('_a', '_b'))
    for c in ('yhat', 'lower', 'upper', 'cogs_yhat'):
        j['d_' + c] = (j[c + '_b'] - j[c + '_a']).abs()
    print(f'\nLệch tuyệt đối lớn nhất theo ngày ({len(j)} dòng ghép được / {len(da)} và {len(db)}):')
    print(j.groupby(['model', 'cogs_method'])[['d_yhat', 'd_lower', 'd_upper', 'd_cogs_yhat']].max().round(3).to_string())
    month = lambda d: (d[d.is_primary].assign(m=lambda x: pd.to_datetime(x.forecast_date).dt.to_period('M'))
                       .groupby('m')[['yhat', 'cogs_yhat']].sum())
    ta, tb = month(da), month(db)
    r = (tb / ta - 1).abs() * 100
    print(f'\nTổng tháng của ứng viên chính: lệch % lớn nhất G {r.yhat.max():.6f}, COGS {r.cogs_yhat.max():.6f}')
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))
