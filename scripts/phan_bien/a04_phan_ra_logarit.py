# -*- coding: utf-8 -*-
"""A4 — Phan ra logarit: y nghia, gia tri, va vi du hai lan."""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
D = 'data/'
od = pd.read_csv(D+'orders.csv', parse_dates=['order_date'])
cu = pd.read_csv(D+'customers.csv')
live = od[od.order_status != 'cancelled']
M1 = len(cu)
f = live.groupby('customer_id').order_date.min()
newy = f.dt.year.value_counts().sort_index()
def td(s): print(); print('='*78); print(s); print('='*78)

td('1. VI SAO PHAN TRAM KHONG CONG DUOC')
x = 100.0
print(f'  Bat dau      : {x:.0f}')
x1 = x*2;  print(f'  Tang 100%    : {x:.0f} x 2 = {x1:.0f}')
x2 = x1*0.5; print(f'  Giam 50%     : {x1:.0f} x 0,5 = {x2:.0f}   <- ve dung cho cu')
print(f'  Cong phan tram: +100% + (-50%) = +50%  -> du doan {x*1.5:.0f}  <- SAI')
print()
print(f'  Bang logarit : ln(2) = {np.log(2):+.4f}, ln(0,5) = {np.log(0.5):+.4f}')
print(f'                 tong  = {np.log(2)+np.log(0.5):+.4f}  -> dung bang 0')

td('2. VI DU LAN 1 — so tron, tinh tay duoc')
P0, P1, h0, h1 = 1000, 500, 0.20, 0.10
m0, m1 = P0*h0, P1*h1
print(f'  {"":14} {"Nam dau":>10} {"Nam sau":>10}')
print(f'  {"Pool":14} {P0:>10,} {P1:>10,}')
print(f'  {"Ty le hut":14} {h0*100:>9.0f}% {h1*100:>9.0f}%')
print(f'  {"Khach moi":14} {m0:>10,.0f} {m1:>10,.0f}')
print()
tot = np.log(m1/m0); dP = np.log(P1/P0); dh = np.log(h1/h0)
print(f'  ln(khach moi) = ln({m1:.0f}/{m0:.0f}) = ln({m1/m0:.2f}) = {tot:+.4f}')
print(f'  ln(Pool)      = ln({P1}/{P0}) = ln({P1/P0:.2f}) = {dP:+.4f}')
print(f'  ln(ty le hut) = ln({h1}/{h0}) = ln({h1/h0:.2f}) = {dh:+.4f}')
print(f'  Cong lai      : {dP:+.4f} + {dh:+.4f} = {dP+dh:+.4f}   sai so {abs(dP+dh-tot):.1e}')
print(f'  Ty trong      : Pool {dP/tot*100:.1f}%  |  ty le hut {dh/tot*100:.1f}%')

td('3. VI DU LAN 2 — so that, day Pool DA SUA theo B1')
def pool(y): return M1 - int(newy[newy.index < y].sum())
P0, P1 = pool(2013), pool(2022)
m0, m1 = int(newy[2013]), int(newy[2022])
h0, h1 = m0/P0, m1/P1
print(f'  {"":16} {"2013":>10} {"2022":>10}')
print(f'  {"Pool dau nam":16} {P0:>10,} {P1:>10,}')
print(f'  {"Khach mua lan dau":16} {m0:>10,} {m1:>10,}')
print(f'  {"Ty le hut":16} {h0*100:>9.2f}% {h1*100:>9.2f}%')
print()
tot = np.log(m1/m0); dP = np.log(P1/P0); dh = np.log(h1/h0)
print(f'  ln tong       = {tot:+.4f}')
print(f'  ln Pool       = {dP:+.4f}  ->  {dP/tot*100:5.1f}%')
print(f'  ln ty le hut  = {dh:+.4f}  ->  {dh/tot*100:5.1f}%')
print(f'  Kiem tong     : {dP+dh:+.4f}  sai so {abs(dP+dh-tot):.2e}')
print()
print(f'  Tai lieu ghi  : 26,9% / 73,1%')
print(f'  Tinh lai      : {dP/tot*100:.1f}% / {dh/tot*100:.1f}%   -> LECH (xem B1)')

td('4. PHAN RA NAY KHONG NOI DUOC GI')
print('  - Khong chung minh nhan qua: no chi CHIA con so, khong noi cai nao GAY RA cai nao.')
print('  - Khong tu noi nen lam gi: biet ty le hut chiem 63,6% khong tuong duong')
print('    voi biet phai lam gi de nang no len.')
print('  - Khong kiem duoc du lieu dung hay sai: dang thuc luon dung (xem B2).')
