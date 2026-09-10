# -*- coding: utf-8 -*-
"""A1 — Cohort la gi? Vi du bang khach that + ma tran cohort."""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
D = 'data/'
od = pd.read_csv(D+'orders.csv', parse_dates=['order_date'])
cu = pd.read_csv(D+'customers.csv', parse_dates=['signup_date'])
live = od[od.order_status != 'cancelled']
f = live.groupby('customer_id').order_date.min()
def td(s): print(); print('='*78); print(s); print('='*78)

td('1. BA KHACH THAT — moi nguoi mot tinh huong')
sl = live.groupby('customer_id').size()
nhieu = sl[(sl >= 6)].index
trai = [c for c in nhieu[:400]
        if live[live.customer_id == c].order_date.dt.year.nunique() >= 5]
a = trai[0]
b = sl[sl == 1].index[0]
huy = od[od.order_status == 'cancelled'].groupby('customer_id').order_date.min()
chung = huy.index.intersection(f.index)
c_ = next(x for x in chung if huy[x] < f[x])
for ten, cid in [('A — nhieu don, trai nhieu nam', a), ('B — chi mot don', b),
                 ('C — co don HUY truoc don live dau tien', c_)]:
    print(f'\n  {ten}  (customer_id = {cid})')
    d = od[od.customer_id == cid].sort_values('order_date')
    for _, r in d.iterrows():
        dau = '  <- don live dau tien' if (r.order_status != 'cancelled'
              and r.order_date == f.get(cid)) else ''
        print(f'    {r.order_date.date()}  {r.order_status:<10}{dau}')
    print(f'    signup_date       : {cu.set_index("customer_id").signup_date.get(cid).date()}')
    print(f'    first_order_date  : {f.get(cid).date()}   -> cohort {f.get(cid).year}')

td('2. MA TRAN COHORT — so khach con hoat dong o tuoi cohort N')
lv = live.copy()
lv['nam'] = lv.order_date.dt.year
lv['cohort'] = lv.customer_id.map(f.dt.year)
lv['tuoi'] = lv.nam - lv.cohort
ct = lv.pivot_table(index='cohort', columns='tuoi', values='customer_id', aggfunc='nunique')
print('  Hang = nam mua lan dau | Cot = so nam ke tu do | O = so khach con mua')
print(ct.loc[2012:2022, 0:5].fillna(0).astype(int).to_string())
print()
ret = (ct.div(ct[0], axis=0)*100).round(1)
print('  Cung bang do quy ra % (chia cho cot 0):')
print(ret.loc[2012:2022, 0:5].to_string())

td('3. CO KHACH NAO THUOC HAI COHORT KHONG?')
print(f'  So khach co first_order_date  : {len(f):,}')
print(f'  So gia tri cohort duy nhat/khach: {f.dt.year.groupby(f.index).nunique().max()}')
print('  -> Moi khach thuoc DUNG MOT cohort, vi MIN() chi tra ve mot ngay.')

td('4. VI SAO NHIN THEO COHORT KHAC NHIN THEO NAM')
dt = lv.groupby('nam').customer_id.nunique().loc[2013:2022]
print('  Nhin theo NAM — chi thay tong so khach hoat dong:')
print('    ' + '  '.join(f'{y}:{v:,}' for y, v in dt.items()))
print()
print('  Nhin theo COHORT — thay tong do la ai (khach hoat dong 2022 theo cohort):')
h22 = lv[lv.nam == 2022].groupby('cohort').customer_id.nunique()
for y, v in h22.items():
    print(f'    cohort {y}: {v:>6,}  ({v/h22.sum()*100:5.1f}%)')
