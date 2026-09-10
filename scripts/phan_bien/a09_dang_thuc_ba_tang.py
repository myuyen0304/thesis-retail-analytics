# -*- coding: utf-8 -*-
"""A9 — Dang thuc phan ra ba tang: tung thanh phan, kiem so, AOV va "gianh lai"."""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
D = 'data/'
od = pd.read_csv(D+'orders.csv', parse_dates=['order_date'])
oi = pd.read_csv(D+'order_items.csv', low_memory=False)
oi['gross'] = oi.quantity*oi.unit_price
rev_o = oi.groupby('order_id').gross.sum()
live = od[od.order_status != 'cancelled'].copy()
live['nam'] = live.order_date.dt.year
live['rev'] = live.order_id.map(rev_o)
f = live.groupby('customer_id').order_date.min()
live['cohort'] = live.customer_id.map(f.dt.year)
def td(s): print(); print('='*78); print(s); print('='*78)

td('1. TUNG THANH PHAN CHO 2013 VA 2022')
r = {}
for y in (2013, 2022):
    d = live[live.nam == y]
    kh = d.customer_id.nunique()
    don = len(d)
    rev = d.rev.sum()
    moi = d[d.cohort == y].customer_id.nunique()
    giu = kh - moi
    r[y] = dict(don=don, kh=kh, ts=don/kh, aov=rev/don, rev=rev, moi=moi, giu=giu)
print(f'  {"Thanh phan":<22} {"2013":>14} {"2022":>14} {"Thay doi":>10}')
print('  ' + '-'*64)
for k, ten in [('rev','Doanh thu'),('don','So don'),('kh','Khach hoat dong'),
               ('ts','Tan suat'),('aov','AOV'),('moi','Khach moi'),('giu','Khach giu lai')]:
    a, b = r[2013][k], r[2022][k]
    fm = ',.0f' if k in ('rev','don','kh','moi','giu','aov') else '.4f'
    print(f'  {ten:<22} {a:>14{fm}} {b:>14{fm}} {(b/a-1)*100:>+9.1f}%')

td('2. KIEM BA DONG DANG THUC')
for y in (2013, 2022):
    x = r[y]
    print(f'  Nam {y}:')
    print(f'    Dong 1: {x["don"]:,} x {x["aov"]:,.2f} = {x["don"]*x["aov"]:,.0f}'
          f'  | that {x["rev"]:,.0f}  -> {"KHOP" if abs(x["don"]*x["aov"]-x["rev"])<1 else "LECH"}')
    print(f'    Dong 2: ({x["kh"]:,} x {x["ts"]:.4f}) x {x["aov"]:,.2f} = '
          f'{x["kh"]*x["ts"]*x["aov"]:,.0f}  -> '
          f'{"KHOP" if abs(x["kh"]*x["ts"]*x["aov"]-x["rev"])<1 else "LECH"}')
    print(f'    Dong 3: ({x["moi"]:,} + {x["giu"]:,}) x {x["ts"]:.4f} x {x["aov"]:,.2f} = '
          f'{(x["moi"]+x["giu"])*x["ts"]*x["aov"]:,.0f}  -> '
          f'{"KHOP" if abs((x["moi"]+x["giu"])*x["ts"]*x["aov"]-x["rev"])<1 else "LECH"}')
print()
print('  -> Dang thuc dung vi DINH NGHIA (tan suat := don/khach, AOV := rev/don),')
print('     khong phai vi du lieu. No la mot dong nhat thuc, khong the sai.')

td('3. KIEM DONG BA BANG DUONG DOC LAP')
for y in (2013, 2022):
    d = live[live.nam == y]
    kh = d.customer_id.nunique()
    moi = d[d.cohort == y].customer_id.nunique()
    # duong doc lap: dem truc tiep khach co first_order_date < y va co don nam y
    dl = d[d.customer_id.map(f.dt.year) < y].customer_id.nunique()
    print(f'  {y}: {kh:,} = {moi:,} + ?')
    print(f'       phan du tu dang thuc  : {kh-moi:,}')
    print(f'       dem truc tiep doc lap : {dl:,}')
    print(f'       -> {"KHOP" if kh-moi == dl else "LECH"}')

td('4. "GIANH LAI" — trong khach hoat dong 2022, bao nhieu KHONG hoat dong 2021?')
h22 = set(live[live.nam == 2022].customer_id)
h21 = set(live[live.nam == 2021].customer_id)
moi22 = set(live[(live.nam == 2022) & (live.cohort == 2022)].customer_id)
giu_that = h22 & h21
gianh_lai = h22 - h21 - moi22
print(f'  Khach hoat dong 2022        : {len(h22):,}')
print(f'    Khach moi (cohort 2022)   : {len(moi22):,}  ({len(moi22)/len(h22)*100:.1f}%)')
print(f'    Giu lai (co don ca 2021)  : {len(giu_that):,}  ({len(giu_that)/len(h22)*100:.1f}%)')
print(f'    GIANH LAI (nghi >=1 nam)  : {len(gianh_lai):,}  ({len(gianh_lai)/len(h22)*100:.1f}%)')
print(f'  Kiem tong: {len(moi22):,} + {len(giu_that):,} + {len(gianh_lai):,} = '
      f'{len(moi22)+len(giu_that)+len(gianh_lai):,} -> '
      f'{"KHOP" if len(moi22)+len(giu_that)+len(gianh_lai)==len(h22) else "LECH"}')
print()
print(f'  -> Nhom "gianh lai" chiem {len(gianh_lai)/len(h22)*100:.1f}% — DANG KE.')
print(f'     Dang thuc hai so hang khong the hien duoc nhom nay.')

td('5. AOV DI DAU?')
print(f'  AOV 2013 -> 2022: {r[2013]["aov"]:,.0f} -> {r[2022]["aov"]:,.0f} '
      f'({(r[2022]["aov"]/r[2013]["aov"]-1)*100:+.1f}%)')
print('  Sau BTN khong co cai nao ve AOV:')
for i, t in enumerate(['trang thai tap khach','mat khach hay mua thua',
                       'kich hoat hay giu chan','co che o don dau',
                       'nen khach do noi 2023-24','ngan sach di dau'], 1):
    print(f'    BTN{i}: {t}')
print('  -> AOV la thanh phan DUY NHAT trong dang thuc khong co bai toan nho phu trach.')
