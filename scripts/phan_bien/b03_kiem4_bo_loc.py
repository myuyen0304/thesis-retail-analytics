# -*- coding: utf-8 -*-
"""B3 — Kiem 4 khop sales.csv bang bo loc nao?"""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
D = 'data/'
od = pd.read_csv(D+'orders.csv', parse_dates=['order_date'])
oi = pd.read_csv(D+'order_items.csv', low_memory=False)
sa = pd.read_csv(D+'sales.csv', parse_dates=['Date'])
oi['gross'] = oi.quantity * oi.unit_price
live = od[od.order_status != 'cancelled']
def td(s): print(); print('='*78); print(s); print('='*78)

td('1. DOI CHIEU sales.csv VOI CA HAI BO LOC')
for ten, don in [('ALL ', od), ('live', live)]:
    j = oi.merge(don[['order_id','order_date']], on='order_id')
    agg = j.groupby('order_date').gross.sum()
    k = sa.set_index('Date').join(agg.rename('tinh'))
    ty = k.tinh / k.Revenue
    print(f'  [{ten}] so ngay {len(k):,} | ty le min {ty.min():.6f} max {ty.max():.6f} '
          f'| sai so tuyet doi max {(k.tinh-k.Revenue).abs().max():,.2f}')
    print(f'         tong doanh thu {k.tinh.sum()/1e9:.2f} ty vs sales.csv {k.Revenue.sum()/1e9:.2f} ty')

td('2. KET LUAN')
j_all = oi.merge(od[['order_id','order_date']], on='order_id')
j_lv = oi.merge(live[['order_id','order_date']], on='order_id')
k_all = sa.set_index('Date').join(j_all.groupby('order_date').gross.sum().rename('t'))
k_lv = sa.set_index('Date').join(j_lv.groupby('order_date').gross.sum().rename('t'))
e_all = (k_all.t - k_all.Revenue).abs().max()
e_lv = (k_lv.t - k_lv.Revenue).abs().max()
print(f'  sales.csv ung voi bo loc: {"ALL" if e_all < e_lv else "live"}')
print(f'    sai so ALL  = {e_all:,.4f}')
print(f'    sai so live = {e_lv:,.4f}')
thieu = k_all.Revenue.sum() - k_lv.t.sum()
print(f'\n  Phan chenh (don cancelled): {thieu/1e9:.2f} ty dvtt '
      f'= {thieu/k_all.Revenue.sum()*100:.2f}% doanh thu')

td('3. CHI SO DOANH THU TRONG TAI LIEU DUNG BO LOC NAO')
bang = [
    ('M4  Doanh thu gross', 'live', 'Muc 6 khai ro'),
    ('M8  Doanh thu tron doi', 'live', 'Muc 6 khai ro'),
    ('Me6 Gia tri cohort 3 nam', 'live', 'tinh tu M4'),
    ('Me7 Ty trong doanh thu khach moi', 'live', 'tinh tu M4'),
    ('K5  Gia tri cohort 3 nam', 'live', 'tinh tu Me6'),
    ('K6  Do phu thuoc khach cu', 'live', 'tinh tu Me7'),
    ('Muc 9 aov_first', 'live', 'btn4_survival.py dung live'),
    ('sales.csv (muc tieu chuong du bao)', 'ALL', 'do o buoc 1'),
]
print(f'  {"Chi so":<36} {"Bo loc":<6} {"Can cu"}')
print('  ' + '-'*70)
for a, b, c in bang:
    print(f'  {a:<36} {b:<6} {c}')
print()
print('  -> Chuong khach hang do bang live, chuong du bao nham vao sales.csv (ALL).')
print(f'     Hai chuong lech nhau {thieu/k_all.Revenue.sum()*100:.2f}% doanh thu — phai noi ro cho noi.')
