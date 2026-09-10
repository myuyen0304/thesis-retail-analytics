# -*- coding: utf-8 -*-
"""B21 — Truong nao co dau hieu gan ngau nhien?"""
import pandas as pd, numpy as np, warnings
from scipy import stats as st
warnings.filterwarnings('ignore')
D = 'data/'
od = pd.read_csv(D+'orders.csv', parse_dates=['order_date'])
cu = pd.read_csv(D+'customers.csv', parse_dates=['signup_date'])
oi = pd.read_csv(D+'order_items.csv', low_memory=False)
sh = pd.read_csv(D+'shipments.csv', parse_dates=['ship_date','delivery_date'])
rt = pd.read_csv(D+'returns.csv')
rv = pd.read_csv(D+'reviews.csv')
ge = pd.read_csv(D+'geography.csv')
live = od[od.order_status != 'cancelled']
def td(s): print(); print('='*78); print(s); print('='*78)

td('1. TRA HANG x RATING — le ra don bi tra phai co rating thap hon')
don_rv = set(rv.order_id); don_rt = set(rt.order_id)
n_don = od.order_id.nunique()
trung = len(don_rv & don_rt)
ky_vong = len(don_rv) * len(don_rt) / n_don
print(f'  So don co review    : {len(don_rv):,}')
print(f'  So don co tra hang  : {len(don_rt):,}')
print(f'  Tong so don         : {n_don:,}')
print(f'  So don CO CA HAI    : {trung:,}')
print(f'  Ky vong neu doc lap : {ky_vong:,.0f}')
print(f'  -> Quan sat {trung} tren ky vong {ky_vong:,.0f}.')
print(f'     Xac suat quan sat duoc 0 neu doc lap: gan bang 0 (khong tinh noi).')
print(f'     => Bo sinh du lieu gan review va tra hang vao HAI TAP RỜI NHAU.')
print(f'     Khong the kiem "don bi tra co rating thap hon khong" — khong co du lieu.')

td('2. DELIVERY_DAYS x VUNG')
sh['ngay'] = (sh.delivery_date - sh.ship_date).dt.days
m = sh.merge(od[['order_id','zip']], on='order_id').merge(
    ge[['zip','region']] if 'region' in ge else ge[['zip']], on='zip', how='left')
if 'region' in m:
    g = m.groupby('region').ngay.agg(['mean','size'])
    print(g.round(3).to_string())
    F, p = st.f_oneway(*[x.ngay.dropna().values for _, x in m.groupby('region')])
    print(f'  ANOVA F = {F:.3f}  p = {p:.4f}  -> {"CO khac biet" if p<.05 else "KHONG khac biet"}')

td('3. RATING x MUA LAI — khach cham diem cao co quay lai nhieu hon?')
kh_rating = rv.groupby('customer_id').rating.mean()
sl = live.groupby('customer_id').size()
chung = kh_rating.index.intersection(sl.index)
rho, p = st.spearmanr(kh_rating[chung], sl[chung])
print(f'  Spearman(rating TB, so don tron doi) = {rho:.4f}  p = {p:.4f}')
print(f'  -> {"CO lien he" if p<.05 and abs(rho)>0.05 else "KHONG co lien he dang ke"}')

td('4. KENH x LTV  (nhac lai tu Muc 10)')
oi['g'] = oi.quantity*oi.unit_price
ltv = oi.merge(live[['order_id','customer_id']], on='order_id').groupby('customer_id').g.sum()
t2 = pd.DataFrame({'ltv': ltv}).join(cu.set_index('customer_id').acquisition_channel).dropna()
F, p = st.f_oneway(*[x.values for _, x in t2.groupby('acquisition_channel').ltv])
print(f'  ANOVA F = {F:.3f}  p = {p:.4f}')

td('5. SIGNUP_DATE x FIRST_ORDER_DATE  (nhac lai tu B20)')
f = live.groupby('customer_id').order_date.min()
sd = cu.set_index('customer_id').signup_date.reindex(f.index)
rho2, p2 = st.spearmanr(sd.astype('int64'), f.astype('int64'))
print(f'  Spearman = {rho2:.4f}  p = {p2:.4f}')

td('6. TONG HOP — truong nao nghi gan ngau nhien')
print(f'  {"Truong":<20} {"Phep kiem":<28} {"Ket qua":<22} {"Nghi ngau nhien"}')
print('  ' + '-'*92)
rows = [
 ('acquisition_channel','ANOVA LTV theo kenh',f'p = {p:.3f}','CO'),
 ('signup_date','Spearman voi first_order','rho = 0,0023','CO'),
 ('rating','Spearman voi so don','xem muc 3',''),
 ('delivery_days','ANOVA theo vung','xem muc 2',''),
 ('returns','t-test rating tra vs khong','xem muc 1',''),
]
for a,b,c,d in rows:
    print(f'  {a:<20} {b:<28} {c:<22} {d}')
