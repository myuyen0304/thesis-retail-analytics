# -*- coding: utf-8 -*-
"""Bo sung: doanh thu khach moi/cu, recency, va chat luong cohort."""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
D = 'data/'

o = pd.read_csv(D + 'orders.csv', usecols=['order_id', 'customer_id', 'order_date'],
                parse_dates=['order_date'])
oi = pd.read_csv(D + 'order_items.csv', usecols=['order_id', 'quantity', 'unit_price'])
c = pd.read_csv(D + 'customers.csv', usecols=['customer_id', 'acquisition_channel'])

lan_dau = o.groupby('customer_id').order_date.min()
o['nam'] = o.order_date.dt.year
o['cohort_nam'] = o.customer_id.map(lan_dau.dt.year)
rev = oi.assign(r=oi.quantity * oi.unit_price).groupby('order_id').r.sum()
o['rev'] = o.order_id.map(rev)
o['moi'] = (o.nam == o.cohort_nam)

print('=' * 72)
print('6. DOANH THU: KHACH MOI vs KHACH CU  (don vi: nghin ty)')
print('=' * 72)
dt = o.groupby(['nam', 'moi']).rev.sum().unstack().loc[2013:2022]
dt.columns = ['cu', 'moi']
out = pd.DataFrame({
    'Khach cu': (dt.cu / 1e9).round(2),
    'Khach moi': (dt.moi / 1e9).round(2),
    '% tu khach moi': (dt.moi / (dt.cu + dt.moi) * 100).round(1),
})
print(out.to_string())

print()
print('=' * 72)
print('7. RECENCY tinh den 31/12/2022')
print('=' * 72)
tong_kh, da_mua = len(c), o.customer_id.nunique()
moc = pd.Timestamp('2022-12-31')
rec = (moc - o.groupby('customer_id').order_date.max()).dt.days
bins = [-1, 90, 180, 365, 730, 100000]
nhan = ['0-90 ngay', '91-180 ngay', '181-365 ngay', '1-2 nam', 'tren 2 nam']
pb = pd.cut(rec, bins=bins, labels=nhan).value_counts().reindex(nhan)
for k, v in pb.items():
    print(f'  {k:<14} {v:>7,}  ({v/tong_kh*100:>5.1f}% tong dang ky)')
print(f'  {"Chua mua bao gio":<14} {tong_kh-da_mua:>7,}  ({(tong_kh-da_mua)/tong_kh*100:>5.1f}%)')
ngu = int(pb['1-2 nam'] + pb['tren 2 nam']) + (tong_kh - da_mua)
print(f'\n  Khong giao dich >1 nam HOAC chua mua: {ngu:,} = {ngu/tong_kh*100:.1f}% tap dang ky')

print()
print('=' * 72)
print('8. CHAT LUONG COHORT: gia tri tron doi trong 3 nam dau')
print('=' * 72)
o['tuoi'] = o.nam - o.cohort_nam
kt = o[o.tuoi == 0].groupby('cohort_nam').customer_id.nunique()
r3 = o[o.tuoi <= 2].groupby('cohort_nam').rev.sum()
d3 = o[o.tuoi <= 2].groupby('cohort_nam').size()
bang = pd.DataFrame({
    'So khach': kt,
    'Don/khach 3 nam': (d3 / kt).round(2),
    'Doanh thu/khach 3 nam': (r3 / kt).round(0),
}).loc[2013:2020]
print(bang.to_string())
v0, v1 = bang['Doanh thu/khach 3 nam'].loc[2013], bang['Doanh thu/khach 3 nam'].loc[2020]
print(f'\n2013 -> 2020: {v0:,.0f} -> {v1:,.0f}  ({(v1/v0-1)*100:+.1f}%)')

print()
print('=' * 72)
print('9. KENH THU NAP: quy mo va chat luong')
print('=' * 72)
kh = pd.DataFrame({'customer_id': lan_dau.index, 'cohort_nam': lan_dau.dt.year.values})
kh = kh.merge(c, on='customer_id', how='left')
tong_rev = o.groupby('customer_id').rev.sum()
kh['ltv'] = kh.customer_id.map(tong_rev)
k = kh.groupby('acquisition_channel').agg(
    so_khach=('customer_id', 'size'), ltv_tb=('ltv', 'mean')).sort_values('so_khach', ascending=False)
k['ltv_tb'] = k.ltv_tb.round(0)
k['% khach'] = (k.so_khach / k.so_khach.sum() * 100).round(1)
print(k.to_string())
