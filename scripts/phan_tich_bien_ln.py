# -*- coding: utf-8 -*-
"""Kiem chung so lieu: cau truc danh muc va tinh bat on cua bien loi nhuan."""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
D = 'data/'

oi = pd.read_csv(D+'order_items.csv', usecols=['order_id','product_id','quantity','unit_price','discount_amount'])
o  = pd.read_csv(D+'orders.csv', usecols=['order_id','order_date','order_status'], parse_dates=['order_date'])
p  = pd.read_csv(D+'products.csv', usecols=['product_id','category','price','cogs'])
r  = pd.read_csv(D+'returns.csv', usecols=['order_id','product_id','return_quantity'])
s  = pd.read_csv(D+'sales.csv', parse_dates=['Date'])

t = oi.merge(o, on='order_id').merge(p, on='product_id')
t['rev'] = t.quantity*t.unit_price
t['cog'] = t.quantity*t.cogs
t['nam'] = t.order_date.dt.year
t['quy'] = t.order_date.dt.quarter

print('='*74); print('1. BIEN LOI NHUAN TOAN HE THONG THEO NAM'); print('='*74)
n = t.groupby('nam')[['rev','cog']].sum()
n['bien'] = (n.rev-n.cog)/n.rev*100
nn = n.loc[2013:2022]
print(nn[['bien']].round(2).to_string())
print(f'\nThap nhat {nn.bien.min():.2f}% ({nn.bien.idxmin()})  |  Cao nhat {nn.bien.max():.2f}% ({nn.bien.idxmax()})')
print(f'Bien do dao dong: {nn.bien.max()-nn.bien.min():.2f} diem phan tram')
print(f'Do lech chuan   : {nn.bien.std():.2f} diem phan tram')

print(); print('='*74); print('2. TY SO COGS/REVENUE THEO QUY x NAM CHAN LE'); print('='*74)
q = t.groupby(['nam','quy'])[['rev','cog']].sum()
q['ty_so'] = q.cog/q.rev
pv = q.ty_so.unstack().loc[2013:2022]
print(pv.round(3).to_string())
print()
for quy in [1,2,3,4]:
    le = pv.loc[[y for y in pv.index if y%2==1], quy]
    chan = pv.loc[[y for y in pv.index if y%2==0], quy]
    print(f'  Q{quy}: nam le TB {le.mean():.3f}  |  nam chan TB {chan.mean():.3f}  |  chenh {le.mean()-chan.mean():+.3f}')

print(); print('='*74); print('3. CAU TRUC DANH MUC: ty trong vs bien'); print('='*74)
c = t.groupby('category')[['rev','cog']].sum()
c['tt'] = c.rev/c.rev.sum()*100
c['bien'] = (c.rev-c.cog)/c.rev*100
print(c[['tt','bien']].round(2).sort_values('tt', ascending=False).to_string())

print(); print('='*74); print('4. PHAN RA THAY DOI BIEN 2013->2022: MIX vs NOI TAI'); print('='*74)
def w_b(nam):
    g = t[t.nam==nam].groupby('category')[['rev','cog']].sum()
    return g.rev/g.rev.sum(), (g.rev-g.cog)/g.rev
w0, b0 = w_b(2013); w1, b1 = w_b(2022)
cats = sorted(set(w0.index)|set(w1.index))
w0, b0, w1, b1 = [x.reindex(cats).fillna(0) for x in (w0,b0,w1,b1)]
mix  = ((w1-w0)*b0).sum()*100
noi  = (w0*(b1-b0)).sum()*100
tuong= ((w1-w0)*(b1-b0)).sum()*100
tong = (w1*b1).sum()*100 - (w0*b0).sum()*100
print(f'  Bien 2013: {(w0*b0).sum()*100:.2f}%   ->   Bien 2022: {(w1*b1).sum()*100:.2f}%')
print(f'  Thay doi tong                 : {tong:+.2f} diem phan tram')
print(f'    Do DICH CHUYEN CO CAU (mix) : {mix:+.2f} dpt  ({mix/tong*100 if tong else 0:.0f}%)')
print(f'    Do BIEN NOI TAI tung nhom   : {noi:+.2f} dpt  ({noi/tong*100 if tong else 0:.0f}%)')
print(f'    Tuong tac                   : {tuong:+.2f} dpt')

print(); print('='*74); print('5. TAP TRUNG SAN PHAM (Pareto)'); print('='*74)
ban = t.groupby('product_id').rev.sum().sort_values(ascending=False)
cum = ban.cumsum()/ban.sum()*100
for m in (5,10,20,50):
    k = int(len(p)*m/100)
    print(f'  Top {m:>2}% ma hang ({k:>4} ma) -> {cum.iloc[min(k,len(cum))-1]:>5.1f}% doanh thu')
chet = len(p) - t.product_id.nunique()
print(f'  Chua tung ban: {chet:,}/{len(p):,} = {chet/len(p)*100:.1f}%')

print(); print('='*74); print('6. TY LE TRA HANG THEO DANH MUC'); print('='*74)
rm = r.merge(p[['product_id','category']], on='product_id')
tra = rm.groupby('category').return_quantity.sum()
sl  = t.groupby('category').quantity.sum()
tl = (tra/sl*100).round(2).sort_values(ascending=False)
for k, v in tl.items():
    print(f'  {k:<14} {v:>5.2f}%')
print(f'  {"TOAN HE THONG":<14} {r.return_quantity.sum()/t.quantity.sum()*100:>5.2f}%')

print(); print('='*74); print('7. GIA GIAO DICH so voi GIA NIEM YET'); print('='*74)
t['ty_gia'] = t.unit_price/t.price
print(f'  Trung vi unit_price/price: {t.ty_gia.median():.4f}')
g = t.groupby('nam').ty_gia.median().loc[2013:2022]
print(f'  2013: {g.loc[2013]:.4f}  ->  2022: {g.loc[2022]:.4f}')
print(f'  Ty le dong hang ban duoi gia von: {(t.unit_price < t.cogs).mean()*100:.2f}%')
