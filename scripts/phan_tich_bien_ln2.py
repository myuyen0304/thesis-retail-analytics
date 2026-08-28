# -*- coding: utf-8 -*-
"""Truy co che: vi sao thang 8 nam le ban duoi gia von."""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
D = 'data/'
oi = pd.read_csv(D+'order_items.csv', usecols=['order_id','product_id','quantity','unit_price','discount_amount','promo_id'])
o  = pd.read_csv(D+'orders.csv', usecols=['order_id','order_date'], parse_dates=['order_date'])
p  = pd.read_csv(D+'products.csv', usecols=['product_id','category','price','cogs'])
pr = pd.read_csv(D+'promotions.csv', parse_dates=['start_date','end_date'])

t = oi.merge(o, on='order_id').merge(p, on='product_id')
t['rev']=t.quantity*t.unit_price; t['cog']=t.quantity*t.cogs
t['nam']=t.order_date.dt.year; t['thang']=t.order_date.dt.month
t['nam_le'] = (t.nam % 2 == 1)

print('='*74); print('1. THANG 8 QUA TUNG NAM'); print('='*74)
t8 = t[t.thang==8]
g = t8.groupby('nam').agg(rev=('rev','sum'), cog=('cog','sum'), dong=('rev','size'),
                          gia_tb=('unit_price','mean'), von_tb=('cogs','mean'))
g['ts'] = (g.cog/g.rev).round(3)
g['le'] = ['LE' if y%2 else 'chan' for y in g.index]
print(g.loc[2013:2022, ['le','dong','gia_tb','von_tb','ts']].round(1).to_string())

print(); print('='*74); print('2. GIA BAN vs GIA VON TRUNG BINH THANG 8'); print('='*74)
for ten, m in [('Nam LE ', t8[t8.nam_le]), ('Nam chan', t8[~t8.nam_le])]:
    print(f'  {ten}: gia ban TB {m.unit_price.mean():>9,.0f} | gia von TB {m.cogs.mean():>9,.0f} '
          f'| ty le von/gia {m.cogs.mean()/m.unit_price.mean():.3f}')

print(); print('='*74); print('3. CO PHAI DO CO CAU DANH MUC KHONG?'); print('='*74)
for ten, m in [('Nam LE ', t8[t8.nam_le]), ('Nam chan', t8[~t8.nam_le])]:
    tt = (m.groupby('category').rev.sum()/m.rev.sum()*100).round(1)
    print(f'  {ten}: ' + '  '.join(f'{k} {v}%' for k, v in tt.items()))

print(); print('='*74); print('4. BAN DUOI GIA VON'); print('='*74)
t['duoi_von'] = t.unit_price < t.cogs
cua_so = t.nam_le & (t.thang==8)
for ten, m in [('Thang 8 nam LE  ', cua_so), ('Thang 8 nam chan', (~t.nam_le)&(t.thang==8)),
               ('Moi thang khac  ', t.thang!=8)]:
    d = t[m]
    print(f'  {ten}: {d.duoi_von.mean()*100:>5.2f}% dong hang ban duoi gia von '
          f'| {d.rev.sum()/t.rev.sum()*100:>5.2f}% doanh thu he thong')

print(); print('='*74); print('5. TAC DONG LEN BIEN TOAN HE THONG'); print('='*74)
con = t[~cua_so]
b_full = (1-t.cog.sum()/t.rev.sum())*100
b_con  = (1-con.cog.sum()/con.rev.sum())*100
print(f'  Bien nguyen ban              : {b_full:.2f}%')
print(f'  Bien khi bo thang 8 nam le   : {b_con:.2f}%   ({b_con-b_full:+.2f} diem phan tram)')
nl = t.groupby('nam').apply(lambda d:(1-d.cog.sum()/d.rev.sum())*100).loc[2013:2022]
nc = con.groupby('nam').apply(lambda d:(1-d.cog.sum()/d.rev.sum())*100).loc[2013:2022]
print(f'\n  Bien theo nam SAU khi bo cua so:')
print('   ', '  '.join(f'{y}:{v:.1f}' for y, v in nc.items()))
print(f'\n  Do lech chuan bien theo nam: {nl.std():.2f} -> {nc.std():.2f} dpt  '
      f'(giam {(1-nc.std()/nl.std())*100:.0f}%)')
print(f'  Bien do dao dong           : {nl.max()-nl.min():.2f} -> {nc.max()-nc.min():.2f} dpt')

print(); print('='*74); print('6. CUA SO NAY CHIEM BAO NHIEU?'); print('='*74)
d = t[cua_so]
print(f'  Doanh thu : {d.rev.sum()/t.rev.sum()*100:.2f}% he thong')
print(f'  So dong   : {len(d):,} / {len(t):,} = {len(d)/len(t)*100:.2f}%')
print(f'  So ngay   : 5 thang 8 cua nam le trong 11 nam du lieu')
print(f'  Lo gop    : {(d.cog.sum()-d.rev.sum())/1e9:.2f} ty dvtt')
