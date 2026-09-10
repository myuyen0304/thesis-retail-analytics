# -*- coding: utf-8 -*-
"""B9 — H4: buoc gay 2019 co phai he qua tre cua suy giam cohort khong?
Mo phong doanh thu tu cohort roi so voi doanh thu that."""
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
live['tuoi'] = live.nam - live.cohort
def td(s): print(); print('='*78); print(s); print('='*78)

td('1. DOANH THU THAT THEO NAM (live)')
that = live.groupby('nam').rev.sum().loc[2012:2022]
for y, v in that.items():
    tt = (v/that.get(y-1)-1)*100 if y-1 in that.index else np.nan
    print(f'  {y}: {v/1e9:6.3f} ty' + (f'   ({tt:+6.2f}%)' if not np.isnan(tt) else ''))

td('2. DONG GOP CUA TUNG COHORT THEO NAM (ty dvtt)')
pv = live.pivot_table(index='cohort', columns='nam', values='rev', aggfunc='sum')/1e9
print(pv.loc[2012:2022, 2012:2022].round(3).fillna(0).to_string())

td('3. MO PHONG — chieu doanh thu/khach theo TUOI cohort')
# Doanh thu trung binh moi khach theo tuoi cohort, trung binh tren cac cohort <= 2015
rpk = live.groupby(['cohort','tuoi']).agg(rev=('rev','sum'),
                                          kh=('customer_id','nunique'))
rpk['tren_khach'] = rpk.rev / rpk.kh
mau = rpk.loc[rpk.index.get_level_values(0) <= 2015].groupby('tuoi').tren_khach.mean()
print('  Doanh thu trung binh moi khach theo tuoi cohort (mau: cohort <= 2015):')
for t, v in mau.items():
    if t <= 10: print(f'    tuoi {t:>2}: {v:>10,.0f} dvtt')

co_size = live[live.tuoi == 0].groupby('cohort').customer_id.nunique()
mp = {}
for y in range(2012, 2023):
    s = 0
    for c, n in co_size.items():
        t = y - c
        if 0 <= t and t in mau.index:
            s += n * mau[t]
    mp[y] = s
mp = pd.Series(mp)

td('4. SO SANH MO PHONG VOI THAT')
print(f'  {"Nam":>5} {"That (ty)":>11} {"Mo phong (ty)":>15} {"Chenh %":>9}')
print('  ' + '-'*44)
for y in range(2012, 2023):
    print(f'  {y:>5} {that[y]/1e9:>11.3f} {mp[y]/1e9:>15.3f} '
          f'{(mp[y]/that[y]-1)*100:>+8.1f}%')

td('5. MO PHONG CO TAI TAO DUOC BUOC GAY 2019 KHONG?')
g_that = (that[2019]/that[2018]-1)*100
g_mp = (mp[2019]/mp[2018]-1)*100
print(f'  Tang truong 2018 -> 2019:')
print(f'    That     : {g_that:+.2f}%')
print(f'    Mo phong : {g_mp:+.2f}%')
print(f'    -> Mo phong giai thich duoc {g_mp/g_that*100:.0f}% muc giam')
print()
print('  Tang truong tung nam, that vs mo phong:')
print(f'  {"Nam":>5} {"That %":>9} {"Mo phong %":>12}')
for y in range(2013, 2023):
    print(f'  {y:>5} {(that[y]/that[y-1]-1)*100:>+8.2f}% {(mp[y]/mp[y-1]-1)*100:>+11.2f}%')
