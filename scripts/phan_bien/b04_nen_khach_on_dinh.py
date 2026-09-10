# -*- coding: utf-8 -*-
"""B4 — Nen khach "on dinh" 23.000 nguoi gom nhung ai?"""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
D = 'data/'
od = pd.read_csv(D+'orders.csv', parse_dates=['order_date'])
oi = pd.read_csv(D+'order_items.csv', low_memory=False)
oi['gross'] = oi.quantity * oi.unit_price
rev_o = oi.groupby('order_id').gross.sum()
live = od[od.order_status != 'cancelled'].copy()
live['nam'] = live.order_date.dt.year
live['rev'] = live.order_id.map(rev_o)
f = live.groupby('customer_id').order_date.min()
live['cohort'] = live.customer_id.map(f.dt.year)
def td(s): print(); print('='*78); print(s); print('='*78)

td('1. BOC 22.999 KHACH HOAT DONG 2022 THEO COHORT')
h = live[live.nam == 2022]
g = h.groupby('cohort').agg(khach=('customer_id','nunique'), rev=('rev','sum'))
g['% khach'] = (g.khach/g.khach.sum()*100).round(1)
g['% doanh thu'] = (g.rev/g.rev.sum()*100).round(1)
g['tham nien'] = 2022 - g.index
g['rev'] = (g.rev/1e6).round(1)
print(g[['khach','% khach','rev','% doanh thu','tham nien']].to_string())
print(f'\n  Tong: {g.khach.sum():,} khach  |  {g.rev.sum():,.1f} trieu dvtt')

td('2. THAM NIEN')
tn = 2022 - h.groupby('customer_id').cohort.first()
print(f'  Trung vi tham nien : {tn.median():.0f} nam')
print(f'  Trung binh         : {tn.mean():.2f} nam')
print(f'  Phan vi: ' + '  '.join(f'p{q}={tn.quantile(q/100):.0f}' for q in (25,50,75,90)))

td('3. DONG RIENG COHORT 2012 VA COHORT <= 2015')
c12 = g.loc[2012] if 2012 in g.index else None
if c12 is not None:
    print(f'  Cohort 2012        : {c12.khach:>6,.0f} khach ({c12["% khach"]:.1f}%)  '
          f'{c12["% doanh thu"]:.1f}% doanh thu 2022')
s15 = g.loc[g.index <= 2015]
print(f'  Cohort <= 2015     : {s15.khach.sum():>6,.0f} khach '
      f'({s15["% khach"].sum():.1f}%)  {s15["% doanh thu"].sum():.1f}% doanh thu 2022')
s19 = g.loc[g.index >= 2019]
print(f'  Cohort >= 2019     : {s19.khach.sum():>6,.0f} khach '
      f'({s19["% khach"].sum():.1f}%)  {s19["% doanh thu"].sum():.1f}% doanh thu 2022')

td('4. CHE DO ON DINH HAY DUOI PHAN RA? — nhin ba nam lien')
for y in (2020, 2021, 2022):
    hh = live[live.nam == y]
    gg = hh.groupby('cohort').customer_id.nunique()
    cu_ = gg[gg.index <= 2015].sum(); moi_ = gg[gg.index > 2015].sum()
    print(f'  {y}: tong {gg.sum():>6,}  |  cohort<=2015 {cu_:>6,} ({cu_/gg.sum()*100:4.1f}%)'
          f'  |  cohort>2015 {moi_:>5,} ({moi_/gg.sum()*100:4.1f}%)')

td('5. MO PHONG 2023-2024 — chieu ty le giu chan theo tuoi cohort')
ct = live.pivot_table(index='cohort', columns=live.nam - live.cohort,
                      values='customer_id', aggfunc='nunique')
# ty le song sot tu tuoi t sang t+1, trung binh tren cac cohort co du lieu
ss = {}
for t in range(0, 11):
    if t in ct.columns and (t+1) in ct.columns:
        v = (ct[t+1] / ct[t]).dropna()
        if len(v): ss[t] = v.mean()
print('  Ty le song sot tu tuoi t sang t+1 (trung binh moi cohort):')
for t, v in ss.items():
    print(f'    tuoi {t:>2} -> {t+1:<2}: {v:.3f}')
h22 = h.groupby('cohort').customer_id.nunique()
for nam_du in (2023, 2024):
    du = 0
    for c, n in h22.items():
        t = nam_du - 1 - c
        r = 1.0
        for k in range(nam_du - 2022):
            r *= ss.get(t + k, list(ss.values())[-1])
        du += n * r
    print(f'\n  Du bao khach hoat dong {nam_du}: {du:,.0f}  (2022 that = {h22.sum():,})')
    print(f'    thay doi so 2022: {(du/h22.sum()-1)*100:+.1f}%')
print('\n  Luu y: mo phong nay CHUA cong them cohort moi cua 2023/2024.')
print(f'  Neu them ~1.300 khach moi/nam (muc 2022) thi cong them {1328:,} moi nam.')
