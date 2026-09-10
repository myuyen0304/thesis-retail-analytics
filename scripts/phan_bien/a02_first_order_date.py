# -*- coding: utf-8 -*-
"""A2 — first_order_date nam o dau, tinh the nao, vi sao khong dung signup_date."""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
D = 'data/'
od = pd.read_csv(D+'orders.csv', parse_dates=['order_date'])
cu = pd.read_csv(D+'customers.csv', parse_dates=['signup_date'])
live = od[od.order_status != 'cancelled']
def td(s): print(); print('='*78); print(s); print('='*78)

td('1. NO CO SAN TRONG FILE NAO KHONG?')
print('  customers.csv:', list(cu.columns))
print('  orders.csv   :', list(od.columns))
print()
print(f'  "first_order_date" trong customers.csv: {"first_order_date" in cu.columns}')
print(f'  "first_order_date" trong orders.csv   : {"first_order_date" in od.columns}')
print('  -> KHONG co san o dau ca. Phai tu tinh.')

td('2. TINH THEO HAI BO LOC — khac nhau cho nao?')
f_live = live.groupby('customer_id').order_date.min()
f_all = od.groupby('customer_id').order_date.min()
chi_all = set(f_all.index) - set(f_live.index)
chung = f_live.index.intersection(f_all.index)
khac = (f_live[chung] != f_all[chung]).sum()
print(f'  Co first_order_date theo ALL : {len(f_all):,} khach')
print(f'  Co first_order_date theo live: {len(f_live):,} khach')
print(f'  Chi co o ALL (toan don huy)  : {len(chi_all):,} khach')
print(f'  Co ca hai nhung NGAY KHAC NHAU: {khac:,} khach')
print(f'  -> Tong chenh: {len(chi_all):,} + {khac:,} = {len(chi_all)+khac:,} khach bi anh huong')

td('3. VI DU — khach co don HUY truoc don hop le')
huy = od[od.order_status == 'cancelled'].groupby('customer_id').order_date.min()
cand = [c for c in huy.index.intersection(f_live.index) if huy[c] < f_live[c]]
cid = cand[0]
print(f'  customer_id = {cid}')
d = od[od.customer_id == cid].sort_values('order_date')
for _, r in d.iterrows():
    print(f'    {r.order_date.date()}  {r.order_status}')
print(f'\n    first_order_date theo ALL : {f_all[cid].date()}  -> cohort {f_all[cid].year}')
print(f'    first_order_date theo live: {f_live[cid].date()}  -> cohort {f_live[cid].year}')

td('4. VI SAO KHONG DUNG signup_date — tinh lai ba con so')
m = live[['customer_id','order_date']].merge(cu[['customer_id','signup_date']], on='customer_id')
tl_don = (m.order_date < m.signup_date).mean()*100
print(f'  (a) Ty le DON dat truoc ngay dang ky (grain: moi don, live):')
print(f'      {(m.order_date < m.signup_date).sum():,} / {len(m):,} = {tl_don:.1f}%')
print(f'      Tai lieu ghi 73,8% -> {"KHOP" if abs(tl_don-73.8)<0.1 else "LECH"}')
tre = (f_live - cu.set_index('customer_id').signup_date.reindex(f_live.index)).dt.days
print(f'\n  (b) Ty le KHACH co do tre am (grain: moi khach):')
print(f'      {(tre<0).sum():,} / {len(tre):,} = {(tre<0).mean()*100:.1f}%')
print(f'      Tai lieu ghi 89,1% -> {"KHOP" if abs((tre<0).mean()*100-89.1)<0.1 else "LECH"}')
print(f'\n  (c) Trung vi do tre: {tre.median():,.0f} ngay')
print(f'      Tai lieu ghi -1.820 -> {"KHOP" if abs(tre.median()+1820)<1 else "LECH"}')
print(f'\n  Phan vi do tre: ' + '  '.join(
    f'p{q}={tre.quantile(q/100):,.0f}' for q in (5,25,50,75,95)))

td('5. CHO NAO VAN DUNG signup_date DUOC?')
dk = cu.signup_date.dt.year.value_counts().sort_index()
print('  Muc 3 dung chuoi so tai khoan dang ky moi nam:')
print('    ' + '  '.join(f'{y}:{v:,}' for y, v in dk.items()))
print(f'\n  Dung duoc vi cho do chi dung signup_date de DEM SO LUONG theo nam,')
print(f'  khong dung de XEP THU TU voi order_date. Sai lech nam o QUAN HE giua')
print(f'  hai cot, khong nam o phan bo cua rieng signup_date.')
