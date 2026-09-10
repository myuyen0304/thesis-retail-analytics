# -*- coding: utf-8 -*-
"""A10 — Hai dinh nghia "quay lai", ba con so "hoat dong"."""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
D = 'data/'
od = pd.read_csv(D+'orders.csv', parse_dates=['order_date'])
cu = pd.read_csv(D+'customers.csv')
live = od[od.order_status != 'cancelled'].copy()
REF = pd.Timestamp('2022-12-31')
live['nam'] = live.order_date.dt.year
f = live.groupby('customer_id').order_date.min()
live['cohort'] = live.customer_id.map(f.dt.year)
def td(s): print(); print('='*78); print(s); print('='*78)

td('1. BA CON SO "HOAT DONG" — tach nguyen nhan chenh')
a = live[live.nam == 2022].customer_id.nunique()
b = od[od.order_date.dt.year == 2022].customer_id.nunique()
rec_all = (REF - od.groupby('customer_id').order_date.max()).dt.days
rec_lv = (REF - live.groupby('customer_id').order_date.max()).dt.days
c_ = int((rec_all <= 365).sum())
d_ = int((rec_lv <= 365).sum())
print(f'  (1) live  + cua so "co don trong nam 2022"      : {a:,}')
print(f'  (2) ALL   + cua so "co don trong nam 2022"      : {b:,}')
print(f'  (3) ALL   + cua so "recency <= 365 tu REF"      : {c_:,}')
print(f'  (4) live  + cua so "recency <= 365 tu REF"      : {d_:,}')
print()
print('  TACH HAI NGUYEN NHAN:')
print(f'    Doi BO LOC (live->ALL), giu cua so nam       : {a:,} -> {b:,}  ({b-a:+,})')
print(f'    Doi CUA SO (nam->recency), giu bo loc ALL    : {b:,} -> {c_:,}  ({c_-b:+,})')
print(f'    Doi CUA SO (nam->recency), giu bo loc live   : {a:,} -> {d_:,}  ({d_-a:+,})')
print()
print(f'  Tai lieu dung: 22.999 (BTN5/BTN6) va 24.753 (BTN1) va 24.696 (Muc 11)')
print(f'  Doi chieu    : {a:,} / {c_:,} / {b:,}')

td('2. HAI DINH NGHIA "QUAY LAI" — tim khach minh hoa')
s = live.sort_values('order_date')
first = s.groupby('customer_id').agg(d1=('order_date','first'))
sec = s[s.duplicated('customer_id', keep='first')].groupby('customer_id').order_date.first()
df = first.copy(); df['d2'] = sec.reindex(df.index)
df = df[df.d2.notna()]
df['cohort'] = df.d1.dt.year
df['nam_d2'] = df.d2.dt.year
# Theo Cox: co su kien. Theo Me5: chi tinh neu d2 roi vao nam cohort+1
ma = df[(df.nam_d2 > df.cohort + 1)]
print(f'  So khach "quay lai theo Cox" nhung KHONG "quay lai nam +1" theo Me5:')
print(f'    {len(ma):,} nguoi = {len(ma)/len(df)*100:.1f}% so khach co don thu hai')
if len(ma):
    r = ma.iloc[0]
    print(f'\n  Vi du: customer_id = {ma.index[0]}')
    print(f'    Don dau : {r.d1.date()}  -> cohort {r.cohort}')
    print(f'    Don hai : {r.d2.date()}  -> nam {r.nam_d2}')
    print(f'    Theo Me5 (nam +1 = {r.cohort+1}): KHONG quay lai')
    print(f'    Theo Cox: CO su kien, thoi gian = {(r.d2-r.d1).days} ngay')

td('3. KHACH "HOAT DONG" THEO RECENCY NHUNG KHONG CO DON NAM 2022')
h22 = set(live[live.nam == 2022].customer_id)
rec_ok = set(rec_lv[rec_lv <= 365].index)
chi_rec = rec_ok - h22
chi_nam = h22 - rec_ok
print(f'  Hoat dong theo recency<=365 nhung khong co don 2022: {len(chi_rec):,}')
print(f'  Co don 2022 nhung recency>365: {len(chi_nam):,}  (khong the xay ra)')
if chi_rec:
    cid = list(chi_rec)[0]
    print(f'\n  Vi du: customer_id = {cid}')
    for _, r in od[od.customer_id == cid].sort_values('order_date').tail(3).iterrows():
        print(f'    {r.order_date.date()}  {r.order_status}')

td('4. "KHACH MOI" — hai nghia')
y = 2022
n_nguoi = live[(live.nam == y) & (live.cohort == y)].customer_id.nunique()
print(f'  Muc 2.2 "khach moi" = co cohort {y}          : {n_nguoi:,} NGUOI')
print(f'  Me7 "khach moi"     = doanh thu cua cohort {y} trong nam {y}')
print(f'    -> mot cai dem NGUOI, mot cai dem TIEN. Cung tu, hai don vi.')
