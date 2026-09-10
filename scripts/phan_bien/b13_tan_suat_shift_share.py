# -*- coding: utf-8 -*-
"""B13 — Tan suat 1,87 -> 1,42: cung nguoi mua thua di, hay doi thanh phan khach?"""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
D = 'data/'
od = pd.read_csv(D+'orders.csv', parse_dates=['order_date'])
live = od[od.order_status != 'cancelled'].copy()
live['nam'] = live.order_date.dt.year
f = live.groupby('customer_id').order_date.min()
live['cohort'] = live.customer_id.map(f.dt.year)
def td(s): print(); print('='*78); print(s); print('='*78)

td('1. BANG cohort x nam -> tan suat')
g = live.groupby(['nam','cohort']).agg(don=('order_id','size'),
                                       kh=('customer_id','nunique'))
g['ts'] = g.don/g.kh
pv = g.ts.unstack(0)
print('  Tan suat (don/khach hoat dong) theo cohort va nam:')
print(pv.loc[2012:2022, [2013, 2016, 2019, 2022]].round(2).to_string())

td('2. PHAN RA SHIFT-SHARE 2013 -> 2022')
def co_cau(y):
    d = live[live.nam == y]
    kh = d.groupby('cohort').customer_id.nunique()
    don = d.groupby('cohort').size()
    return kh/kh.sum(), don/kh, kh.sum()
w0, t0, n0 = co_cau(2013)
w1, t1, n1 = co_cau(2022)
cs = sorted(set(w0.index) | set(w1.index))
w0, t0, w1, t1 = [x.reindex(cs).fillna(0) for x in (w0, t0, w1, t1)]
TS0, TS1 = (w0*t0).sum(), (w1*t1).sum()
noi = ((t1-t0)*w0).sum()
cc = ((w1-w0)*t0).sum()
tt = TS1 - TS0 - noi - cc
print(f'  Tan suat 2013 = {TS0:.4f}   2022 = {TS1:.4f}   thay doi {TS1-TS0:+.4f}')
print(f'    Noi cohort (cung cohort mua thua di) : {noi:+.4f}  -> {noi/(TS1-TS0)*100:6.1f}%')
print(f'    Co cau     (doi ty trong cohort)     : {cc:+.4f}  -> {cc/(TS1-TS0)*100:6.1f}%')
print(f'    Tuong tac                            : {tt:+.4f}  -> {tt/(TS1-TS0)*100:6.1f}%')
print()
print('  Luu y: 2013 chi co cohort <= 2013, 2022 co cohort <= 2022.')
print('  Cohort chi xuat hien o 2022 duoc gan w0 = 0 (khong ton tai nam 2013).')

td('3. NHIN RIENG TUNG COHORT — ho co mua thua di khong?')
print(f'  {"Cohort":>7} {"TS 2013":>9} {"TS 2022":>9} {"Thay doi":>10}')
print('  ' + '-'*40)
for c in sorted(cs):
    a = pv.loc[c, 2013] if (c in pv.index and 2013 in pv.columns) else np.nan
    b = pv.loc[c, 2022] if (c in pv.index and 2022 in pv.columns) else np.nan
    if not (np.isnan(a) or np.isnan(b)):
        print(f'  {c:>7} {a:>9.3f} {b:>9.3f} {(b/a-1)*100:>+9.1f}%')
