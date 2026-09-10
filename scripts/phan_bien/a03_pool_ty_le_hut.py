# -*- coding: utf-8 -*-
"""A3 — Pool va ty le hut: la gi, y nghia gi, phuc vu muc dich gi.
Dung day Pool DA SUA theo B1."""
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

td('1. BANG POOL / KHACH MOI / TY LE HUT  (day da sua theo B1)')
rows = []
for y in range(2012, 2023):
    pool = M1 - int(newy[newy.index < y].sum())
    moi = int(newy.get(y, 0))
    rows.append([y, pool, moi, moi/pool*100])
b = pd.DataFrame(rows, columns=['Nam','Pool dau nam','Khach mua lan dau','Ty le hut %'])
b['Pool giam so nam truoc'] = b['Pool dau nam'].diff().fillna(0).astype(int)
b['Ty le hut %'] = b['Ty le hut %'].round(2)
print(b.to_string(index=False))

td('2. DANH SACH DONG — Pool chi co the co lai')
print(f'  customers.csv co dung {M1:,} dong, khong bao gio them.')
print(f'  Tong khach da tung mua (live): {len(f):,}')
print(f'  Pool cuoi 2022 = {M1 - len(f):,}  (= {M1:,} - {len(f):,})')
print(f'  Pool giam don dieu: {bool((b["Pool dau nam"].diff().dropna() <= 0).all())}')

td('3. VI DU HAI NAM — hai cach nhin, hai ket luan')
for y in (2016, 2021):
    r = b[b.Nam == y].iloc[0]
    print(f'  Nam {y}: Pool {r["Pool dau nam"]:,} x ty le hut {r["Ty le hut %"]:.2f}% '
          f'= {r["Khach mua lan dau"]:,} khach moi')
r16 = b[b.Nam==2016].iloc[0]; r21 = b[b.Nam==2021].iloc[0]
print()
print(f'  Chi nhin SO KHACH MOI : {r16["Khach mua lan dau"]:,} -> {r21["Khach mua lan dau"]:,}'
      f'  = {(r21["Khach mua lan dau"]/r16["Khach mua lan dau"]-1)*100:.1f}%')
print(f'  Nhin them TY LE HUT   : {r16["Ty le hut %"]:.2f}% -> {r21["Ty le hut %"]:.2f}%'
      f'  = {(r21["Ty le hut %"]/r16["Ty le hut %"]-1)*100:.1f}%')
print(f'  Pool cung ky          : {r16["Pool dau nam"]:,} -> {r21["Pool dau nam"]:,}'
      f'  = {(r21["Pool dau nam"]/r16["Pool dau nam"]-1)*100:.1f}%')

td('4. VI DU NGAN SACH — hai cach nhin dan toi hai quyet dinh')
p22 = b[b.Nam==2022]['Pool dau nam'].iloc[0]
h22 = b[b.Nam==2022]['Ty le hut %'].iloc[0]/100
h13 = b[b.Nam==2013]['Ty le hut %'].iloc[0]/100
print(f'  Neu khoi phuc ty le hut 2022 ve muc 2013 ({h13*100:.2f}%),')
print(f'  giu nguyen Pool {p22:,}:')
print(f'    khach moi se la {p22*h13:,.0f} thay vi {p22*h22:,.0f}')
print(f'    tang them {p22*h13 - p22*h22:,.0f} khach = {(h13/h22-1)*100:.0f}%')
print()
print(f'  Nguoc lai, neu chi dat muc tieu "so khach moi bang nam 2013"')
print(f'  ({int(newy[2013]):,} nguoi) tren Pool {p22:,} thi doi hoi ty le hut')
print(f'  = {newy[2013]/p22*100:.1f}% — cao hon ca muc 2013 ({h13*100:.2f}%).')
print(f'  -> Muc tieu tren SO DEM la bat kha thi; muc tieu tren TY LE thi kha thi.')
