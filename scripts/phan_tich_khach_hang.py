# -*- coding: utf-8 -*-
"""Kiem chung so lieu cho problem statement huong Khach hang (D2)."""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
D = 'data/'

o = pd.read_csv(D + 'orders.csv', usecols=['order_id', 'customer_id', 'order_date'],
                parse_dates=['order_date'])
oi = pd.read_csv(D + 'order_items.csv', usecols=['order_id', 'quantity', 'unit_price'])
c = pd.read_csv(D + 'customers.csv', usecols=['customer_id', 'acquisition_channel'])

print('=' * 72)
print('1. QUY MO TAP KHACH HANG')
print('=' * 72)
tong_kh = len(c)
da_mua = o.customer_id.nunique()
chua_mua = tong_kh - da_mua
print(f'Tong khach dang ky      : {tong_kh:,}')
print(f'Da tung dat hang        : {da_mua:,} ({da_mua/tong_kh*100:.1f}%)')
print(f'Chua tung dat hang      : {chua_mua:,} ({chua_mua/tong_kh*100:.1f}%)')
print(f'Tong don hang           : {len(o):,}')
print(f'Don/khach da mua (TB)   : {len(o)/da_mua:.2f}')

print()
print('=' * 72)
print('2. TY LE MUA LAI')
print('=' * 72)
sl = o.groupby('customer_id').size()
print(f'Mua dung 1 lan          : {(sl == 1).sum():,} ({(sl == 1).mean()*100:.1f}% khach da mua)')
print(f'Mua tu 2 lan tro len    : {(sl >= 2).sum():,} ({(sl >= 2).mean()*100:.1f}%)')
print(f'Trung vi so don/khach   : {sl.median():.0f}')
print(f'Phan vi 90 so don/khach : {sl.quantile(.9):.0f}')

print()
print('=' * 72)
print('3. PHAN RA: Don hang = Khach hoat dong x Tan suat')
print('=' * 72)
o['nam'] = o.order_date.dt.year
g = o.groupby('nam').agg(don=('order_id', 'size'), kh=('customer_id', 'nunique'))
g['tan_suat'] = g.don / g.kh
g = g.loc[2013:2022]
print(g.to_string())
d0, d1 = g.don.iloc[0], g.don.iloc[-1]
k0, k1 = g.kh.iloc[0], g.kh.iloc[-1]
f0, f1 = g.tan_suat.iloc[0], g.tan_suat.iloc[-1]
print()
print(f'2013 -> 2022  Don      : {d0:,} -> {d1:,}  ({(d1/d0-1)*100:+.1f}%)')
print(f'2013 -> 2022  Khach HD : {k0:,} -> {k1:,}  ({(k1/k0-1)*100:+.1f}%)')
print(f'2013 -> 2022  Tan suat : {f0:.2f} -> {f1:.2f}  ({(f1/f0-1)*100:+.1f}%)')
print()
# Phan ra dong gop
d_kh = (k1 - k0) * f0
d_ts = (f1 - f0) * k0
d_tt = (k1 - k0) * (f1 - f0)
print('Phan ra thay doi so don:')
print(f'  Do thay doi SO KHACH  : {d_kh:>12,.0f}  ({d_kh/(d1-d0)*100:>6.1f}%)')
print(f'  Do thay doi TAN SUAT  : {d_ts:>12,.0f}  ({d_ts/(d1-d0)*100:>6.1f}%)')
print(f'  Tuong tac             : {d_tt:>12,.0f}  ({d_tt/(d1-d0)*100:>6.1f}%)')
print(f'  Tong                  : {d1-d0:>12,.0f}')

print()
print('=' * 72)
print('4. KHACH MOI THU NAP MOI NAM (theo ngay mua dau tien)')
print('=' * 72)
lan_dau = o.groupby('customer_id').order_date.min()
kh_moi = lan_dau.dt.year.value_counts().sort_index()
kmn = kh_moi.loc[2013:2022]
print(kmn.to_string())
print(f'\n2013 -> 2022: {kmn.iloc[0]:,} -> {kmn.iloc[-1]:,} ({(kmn.iloc[-1]/kmn.iloc[0]-1)*100:+.1f}%)')

print()
print('=' * 72)
print('5. COHORT RETENTION (theo nam thu nap)')
print('=' * 72)
o['cohort_nam'] = o.customer_id.map(lan_dau.dt.year)
o['tuoi'] = o.nam - o.cohort_nam
ct = o.pivot_table(index='cohort_nam', columns='tuoi', values='customer_id',
                   aggfunc='nunique')
kich_thuoc = ct[0]
ret = ct.div(kich_thuoc, axis=0) * 100
print('Ty le % khach cua cohort con quay lai mua o nam thu N:')
print(ret.loc[2013:2021, 0:5].round(1).to_string())
print()
print('Trung binh retention nam +1:', round(ret[1].loc[2013:2021].mean(), 1), '%')
print('Trung binh retention nam +2:', round(ret[2].loc[2013:2020].mean(), 1), '%')

print()
print('=' * 72)
print('6. DOANH THU: KHACH MOI vs KHACH CU')
print('=' * 72)
rev = oi.assign(r=oi.quantity * oi.unit_price).groupby('order_id').r.sum()
o['rev'] = o.order_id.map(rev)
o['la_khach_moi'] = (o.nam == o.cohort_nam).astype(int)
dt = o.groupby(['nam', 'la_khach_moi']).rev.sum().unstack().loc[2013:2022]
dt.columns = ['Khach cu', 'Khach moi']
dt['% tu khach moi'] = dt['Khach moi'] / (dt['Khach moi'] + dt['Khach cu']) * 100
print((dt / 1e9).round(2).to_string())

print()
print('=' * 72)
print('7. RECENCY tinh den 31/12/2022')
print('=' * 72)
moc = pd.Timestamp('2022-12-31')
lan_cuoi = o.groupby('customer_id').order_date.max()
rec = (moc - lan_cuoi).dt.days
bins = [0, 90, 180, 365, 730, 10000]
nhan = ['0-90 ngay', '91-180', '181-365', '1-2 nam', 'tren 2 nam']
pb = pd.cut(rec, bins=bins, labels=nhan, include_lowest=True).value_counts().reindex(nhan)
for k, v in pb.items():
    print(f'  {k:<12} {v:>7,}  ({v/da_mua*100:>5.1f}% khach da mua)')
print(f'  {"Chua mua bao gio":<12} {chua_mua:>7,}  ({chua_mua/tong_kh*100:>5.1f}% tong dang ky)')
