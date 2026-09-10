# -*- coding: utf-8 -*-
"""B7 — cohort_year vao Cox dang tuyen tinh: da kiem dang ham chua?"""
import sys, os, numpy as np, pandas as pd, warnings
sys.path.insert(0, os.path.dirname(__file__))
warnings.filterwarnings('ignore')
from _cox_chung import bang_cox, ma_tran
from lifelines import CoxPHFitter
from scipy import stats as st

def td(s): print(); print('='*78); print(s); print('='*78)
df = bang_cox()

td('1. MO HINH 1 — cohort_year TUYEN TINH (nhu tai lieu)')
X1, m = ma_tran(df)
c1 = CoxPHFitter(penalizer=0.01).fit(X1, 'thoi_gian', 'su_kien')
hr1 = c1.summary.loc['cohort_year','exp(coef)']
print(f'  n = {len(X1):,}  |  log-likelihood = {c1.log_likelihood_:,.2f}')
print(f'  So tham so = {len(c1.params_)}')
print(f'  HR cohort_year = {hr1:.4f}  (p = {c1.summary.loc["cohort_year","p"]:.2e})')

td('2. MO HINH 2 — cohort_year PHAN LOAI (dummy tung nam)')
m2 = m.copy(); m2['cohort_cat'] = m2.cohort_year.astype(str)
d2 = m2[['thoi_gian','su_kien','promo_first','delivery_days','returned_first',
         'log_aov','category_first','cohort_cat']].copy()
X2 = pd.get_dummies(d2, columns=['category_first','cohort_cat'], drop_first=True, dtype=float)
c2 = CoxPHFitter(penalizer=0.01).fit(X2, 'thoi_gian', 'su_kien')
print(f'  n = {len(X2):,}  |  log-likelihood = {c2.log_likelihood_:,.2f}')
print(f'  So tham so = {len(c2.params_)}')
print()
print('  HR tung nam cohort (moc = cohort som nhat):')
for k in [i for i in c2.summary.index if i.startswith('cohort_cat_')]:
    r = c2.summary.loc[k]
    print(f'    {k.replace("cohort_cat_",""):>6}: HR {r["exp(coef)"]:>7.4f}  '
          f'[{r["exp(coef) lower 95%"]:.4f}, {r["exp(coef) upper 95%"]:.4f}]  p={r["p"]:.2e}')

td('3. LIKELIHOOD RATIO TEST')
print('  LUU Y: penalizer=0.01 lam hong phep so sanh nay — phat L2 danh nang')
print('  hon vao mo hinh nhieu tham so, nen LR co the ra AM (bat kha thi voi')
print('  hai mo hinh long nhau). Phai fit lai voi penalizer=0.')
lr_p = 2*(c2.log_likelihood_ - c1.log_likelihood_)
print(f'\n  [penalizer=0.01] LR = {lr_p:,.2f}  <- am, KHONG dung duoc')

c1b = CoxPHFitter(penalizer=0).fit(X1, 'thoi_gian', 'su_kien')
c2b = CoxPHFitter(penalizer=0).fit(X2, 'thoi_gian', 'su_kien')
lr = 2*(c2b.log_likelihood_ - c1b.log_likelihood_)
bac_tu_do = len(c2b.params_) - len(c1b.params_)
p = st.chi2.sf(lr, bac_tu_do)
print(f'\n  [penalizer=0]')
print(f'    Tuyen tinh : log-lik = {c1b.log_likelihood_:,.2f}  ({len(c1b.params_)} tham so)')
print(f'    Phan loai  : log-lik = {c2b.log_likelihood_:,.2f}  ({len(c2b.params_)} tham so)')
print(f'    LR = {lr:,.2f}   bac tu do = {bac_tu_do}   p = {p:.3e}')
print(f'    -> {"BAC BO dang tuyen tinh" if p < 0.05 else "Khong bac bo duoc dang tuyen tinh"}')
hr1b = c1b.summary.loc['cohort_year','exp(coef)']
print(f'\n    HR cohort_year (penalizer=0): {hr1b:.4f}  (voi 0.01: {hr1:.4f})')

td('4. HINH DANG THEO NAM — tuyen tinh du doan gi vs thuc te')
print(f'  Neu tuyen tinh dung: moi nam muon hon nhan them he so {hr1:.4f}')
print()
print(f'  {"Nam":>6} {"HR tuyen tinh":>15} {"HR phan loai":>14} {"Chenh":>10}')
print('  ' + '-'*50)
moc = int(m.cohort_year.min())
for k in [i for i in c2.summary.index if i.startswith('cohort_cat_')]:
    nam = int(k.replace('cohort_cat_',''))
    tt = hr1 ** (nam - moc)
    pl = c2.summary.loc[k,'exp(coef)']
    print(f'  {nam:>6} {tt:>15.4f} {pl:>14.4f} {pl/tt:>10.2f}x')

td('5. SCHOENFELD KIEM GI?')
print('  Schoenfeld residuals kiem GIA DINH TY LE NGUY CO THEO THOI GIAN:')
print('    "he so cua bien co giu nguyen suot thoi gian theo doi khong?"')
print()
print('  No KHONG kiem DANG HAM cua bien:')
print('    "quan he giua bien va log-hazard co tuyen tinh khong?"')
print()
print('  Day la HAI chuyen khac nhau. Muc 9.5 ghi cohort_year p = 0,269 ->')
print('  "khong vi pham" — dung, nhung do la khong vi pham gia dinh PH,')
print('  KHONG phai bang chung cho dang tuyen tinh.')
