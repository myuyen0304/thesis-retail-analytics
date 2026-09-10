# -*- coding: utf-8 -*-
"""B17 — Doi HR ra diem phan tram."""
import sys, os, numpy as np, pandas as pd, warnings
sys.path.insert(0, os.path.dirname(__file__))
warnings.filterwarnings('ignore')
from _cox_chung import bang_cox, ma_tran
from lifelines import CoxPHFitter
def td(s): print(); print('='*78); print(s); print('='*78)

df = bang_cox(); X, m = ma_tran(df)
c = CoxPHFitter(penalizer=0).fit(X, 'thoi_gian', 'su_kien')
cov = [k for k in X.columns if k not in ('thoi_gian','su_kien')]
tb = X[cov].mean()

def quay_lai(ho, t):
    s = c.predict_survival_function(pd.DataFrame([ho])[cov], times=[t])
    return float(1 - s.iloc[0, 0])

td('1. promo_first — hai ho so giong het tru bien nay')
r = {}
for v in (0, 1):
    h = tb.copy(); h['promo_first'] = v
    r[v] = {t: quay_lai(h, t)*100 for t in (365, 730)}
print(f'  {"":<22} {"365 ngay":>10} {"730 ngay":>10}')
print(f'  {"KHONG promo":<22} {r[0][365]:>9.1f}% {r[0][730]:>9.1f}%')
print(f'  {"CO promo":<22} {r[1][365]:>9.1f}% {r[1][730]:>9.1f}%')
print(f'  {"Chenh (diem %)":<22} {r[1][365]-r[0][365]:>+9.1f}  {r[1][730]-r[0][730]:>+9.1f}')
print(f'\n  So voi chenh THO o Muc 9.2: 10,0 diem tai 365 ngay')
print(f'  -> Sau khi kiem soat, chenh chi con {abs(r[1][365]-r[0][365]):.1f} diem')

td('2. cohort_year — cohort 2013 so cohort 2018')
moc = int(m.cohort_year.min())
r2 = {}
for nam in (2013, 2018):
    h = tb.copy(); h['cohort_year'] = nam - moc
    r2[nam] = {t: quay_lai(h, t)*100 for t in (365, 730)}
print(f'  {"":<22} {"365 ngay":>10} {"730 ngay":>10}')
for nam in (2013, 2018):
    print(f'  {"cohort " + str(nam):<22} {r2[nam][365]:>9.1f}% {r2[nam][730]:>9.1f}%')
print(f'  {"Chenh (diem %)":<22} {r2[2018][365]-r2[2013][365]:>+9.1f}  '
      f'{r2[2018][730]-r2[2013][730]:>+9.1f}')

td('3. DO LON TUONG DOI — de so sanh hai bien')
print(f'  promo_first (0->1)      : {abs(r[1][365]-r[0][365]):>5.1f} diem tai 365 ngay')
print(f'  cohort_year (2013->2018): {abs(r2[2018][365]-r2[2013][365]):>5.1f} diem tai 365 ngay')
print(f'  -> cohort_year manh hon '
      f'{abs(r2[2018][365]-r2[2013][365])/abs(r[1][365]-r[0][365]):.1f} lan')

td('4. QUY DOI RA SO NGUOI')
n_promo = int((df.promo_first == 1).sum())
print(f'  So khach co don dau kem khuyen mai: {n_promo:,}')
print(f'  Neu ho khong co khuyen mai, so nguoi quay lai trong 1 nam se nhieu hon:')
print(f'    {n_promo * abs(r[1][365]-r[0][365])/100:,.0f} nguoi')
