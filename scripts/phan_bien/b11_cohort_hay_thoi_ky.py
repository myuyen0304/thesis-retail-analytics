# -*- coding: utf-8 -*-
"""B11 — HR 0,7478 la hieu ung COHORT hay hieu ung THOI KY?"""
import sys, os, numpy as np, pandas as pd, warnings
sys.path.insert(0, os.path.dirname(__file__))
warnings.filterwarnings('ignore')
from _cox_chung import bang_cox, ma_tran, nap
from lifelines import CoxPHFitter
def td(s): print(); print('='*78); print(s); print('='*78)

od, oi, p_, sh, rt, live = nap()
lv = live.copy(); lv['nam'] = lv.order_date.dt.year
f = live.groupby('customer_id').order_date.min()
lv['cohort'] = lv.customer_id.map(f.dt.year)

td('1. CHI SO KHONG PHU THUOC COHORT — ty le khach nam Y-1 mua tiep nam Y')
hd = {y: set(lv[lv.nam == y].customer_id) for y in range(2012, 2023)}
print(f'  {"Nam":>5} {"Hoat dong Y-1":>14} {"Mua tiep nam Y":>15} {"Ty le":>8}')
print('  ' + '-'*46)
chuoi = {}
for y in range(2013, 2023):
    tr = hd[y-1]
    tiep = len(tr & hd[y])
    chuoi[y] = tiep/len(tr)*100
    print(f'  {y:>5} {len(tr):>14,} {tiep:>15,} {chuoi[y]:>7.1f}%')

td('2. SO VOI RETENTION NAM +1 THEO COHORT')
ct = lv.pivot_table(index='cohort', columns=lv.nam-lv.cohort,
                    values='customer_id', aggfunc='nunique')
ret1 = (ct[1]/ct[0]*100).round(1)
print(f'  {"":>6} {"Theo COHORT":>13} {"Theo THOI KY":>14}')
print('  ' + '-'*36)
for c in range(2012, 2022):
    tk = chuoi.get(c+1, np.nan)
    print(f'  {c:>6} {ret1.get(c, np.nan):>12.1f}% {tk:>13.1f}%')
print()
print('  Neu chuoi THOI KY cung roi manh -> phan lon la hieu ung thoi ky.')

td('3. CHI TRONG COHORT 2013 — ho co cham lai sau 2019 khong?')
c13 = lv[lv.cohort == 2013]
hd13 = {y: set(c13[c13.nam == y].customer_id) for y in range(2013, 2023)}
print(f'  {"Nam":>5} {"Hoat dong Y-1":>14} {"Mua tiep":>10} {"Ty le":>8}')
print('  ' + '-'*42)
for y in range(2014, 2023):
    tr = hd13[y-1]
    if not tr: continue
    print(f'  {y:>5} {len(tr):>14,} {len(tr & hd13[y]):>10,} '
          f'{len(tr & hd13[y])/len(tr)*100:>7.1f}%')
print('\n  Cung MOT nhom nguoi. Neu ho cung cham lai sau 2019 -> THOI KY.')

td('4. COX THEM BIEN THOI KY')
df = bang_cox()
X1, m = ma_tran(df)
c1 = CoxPHFitter(penalizer=0).fit(X1, 'thoi_gian', 'su_kien')
hr_truoc = c1.summary.loc['cohort_year','exp(coef)']
print(f'  Mo hinh goc      : HR cohort_year = {hr_truoc:.4f}')

# Bien thoi ky: ty le thoi gian theo doi roi vao giai doan sau 2019
m2 = m.copy()
moc = pd.Timestamp('2019-01-01')
ket = m2.d1 + pd.to_timedelta(m2.thoi_gian, unit='D')
sau = (ket - m2.d1.clip(lower=moc)).dt.days.clip(lower=0)
m2['ty_le_sau_2019'] = (sau / m2.thoi_gian).clip(0, 1)
X2 = X1.copy(); X2['ty_le_sau_2019'] = m2['ty_le_sau_2019'].values
c2 = CoxPHFitter(penalizer=0).fit(X2, 'thoi_gian', 'su_kien')
print(f'  Them ty_le_sau_2019: HR cohort_year = {c2.summary.loc["cohort_year","exp(coef)"]:.4f}')
print(f'                       HR ty_le_sau_2019 = {c2.summary.loc["ty_le_sau_2019","exp(coef)"]:.4f}'
      f'  (p = {c2.summary.loc["ty_le_sau_2019","p"]:.2e})')
print()
print(f'  Thay doi HR cohort_year: {hr_truoc:.4f} -> {c2.summary.loc["cohort_year","exp(coef)"]:.4f}'
      f'  ({(c2.summary.loc["cohort_year","exp(coef)"]/hr_truoc-1)*100:+.1f}%)')
