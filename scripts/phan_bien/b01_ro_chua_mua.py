# -*- coding: utf-8 -*-
"""B1 — Ro chua mua (M13) lay o dau ra?

Cong thuc da khai o Muc 6:  M13(Y) = M1 - (tong khach mua lan dau CAC NAM TRUOC Y)
Cau hoi: ap dung dung cong thuc do co ra day 121.930 / 55.738 nhu tai lieu ghi khong?

Chay:  .venv/Scripts/python.exe scripts/phan_bien/b01_ro_chua_mua.py
"""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')

D = 'data/'
od = pd.read_csv(D + 'orders.csv', parse_dates=['order_date'])
cu = pd.read_csv(D + 'customers.csv')

live = od[od.order_status != 'cancelled']       # bo loc chuan
M1 = len(cu)                                     # grain: moi khach dang ky

# Khach mua lan dau moi nam — grain: moi khach; nguon: orders.order_date; bo loc: live
f = live.groupby('customer_id').order_date.min()
newy = f.dt.year.value_counts().sort_index()

def td(s):
    print(); print('=' * 78); print(s); print('=' * 78)

td('0. DAU VAO')
print(f'  M1  tong tai khoan dang ky (customers.csv, grain: moi khach) : {M1:,}')
print(f'  Bo loc: live = {len(live):,} don  (ALL = {len(od):,}, loai {len(od)-len(live):,} cancelled)')
print()
print('  Khach mua lan dau theo nam (first_order_date, live, grain: moi khach):')
for y, v in newy.items():
    print(f'    {y}: {v:>7,}')
print(f'    {"TONG":>4}: {newy.sum():>7,}')

td('1. DAY POOL — CACH CU (vong lap trong kiem_chung_D2.py va nghiem_thu_D2.py)')
print('  Nguyen van vong lap:')
print('      pool, p = {}, len(cu)')
print('      for y in range(2013, 2023):')
print('          pool[y] = p')
print('          p -= newy.get(y, 0)')
print()
pool_cu, p = {}, M1
for y in range(2013, 2023):
    pool_cu[y] = p
    p -= newy.get(y, 0)

td('2. DAY POOL — DUNG CONG THUC M13 DA KHAI')
print('  M13(Y) = M1 - tong khach mua lan dau cac nam TRUOC Y')
print('  -> nam dau tien co du lieu la 2012, nen pool dau nam 2013 phai tru cohort 2012.')
print()
pool_moi = {}
for y in range(2012, 2023):
    truoc = int(newy[newy.index < y].sum())
    pool_moi[y] = M1 - truoc

td('3. DOI CHIEU HAI DAY')
print(f'  {"Nam":>5} | {"Cach cu":>9} | {"Cong thuc M13":>13} | {"Chenh":>8}')
print('  ' + '-' * 46)
for y in range(2012, 2023):
    cu_ = pool_cu.get(y)
    moi_ = pool_moi[y]
    if cu_ is None:
        print(f'  {y:>5} | {"(khong co)":>9} | {moi_:>13,} | {"—":>8}')
    else:
        print(f'  {y:>5} | {cu_:>9,} | {moi_:>13,} | {moi_-cu_:>+8,}')

td('4. HE QUA — TY LE HUT VA PHAN RA LOGARIT')

def phan_ra(pool, ten):
    r13 = newy[2013] / pool[2013]
    r22 = newy[2022] / pool[2022]
    tot = np.log(newy[2022] / newy[2013])
    d_pool = np.log(pool[2022] / pool[2013])
    d_rate = np.log(r22 / r13)
    print(f'  [{ten}]')
    print(f'    Pool 2013 = {pool[2013]:>8,}   Pool 2022 = {pool[2022]:>8,}')
    print(f'    Ty le hut 2013 = {r13*100:6.2f}%   2022 = {r22*100:5.2f}%')
    print(f'    ln tong = {tot:+.4f}')
    print(f'      ro can    ln = {d_pool:+.4f}  -> {d_pool/tot*100:5.1f}%')
    print(f'      ty le hut ln = {d_rate:+.4f}  -> {d_rate/tot*100:5.1f}%')
    print(f'    Kiem tong: {d_pool + d_rate:+.4f} vs {tot:+.4f}  sai so {abs(d_pool+d_rate-tot):.2e}')
    print()
    return r13*100, r22*100, d_pool/tot*100, d_rate/tot*100

a = phan_ra(pool_cu, 'CACH CU — so tai lieu dang dung')
b = phan_ra(pool_moi, 'CONG THUC M13 — tinh lai')

td('5. KET LUAN')
print(f'  Tai lieu ghi : ro can 26,9%  /  ty le hut 73,1%')
print(f'  Cach cu      : ro can {a[2]:.1f}%  /  ty le hut {a[3]:.1f}%   -> khop tai lieu')
print(f'  Cong thuc M13: ro can {b[2]:.1f}%  /  ty le hut {b[3]:.1f}%')
print()
chenh = pool_moi[2013] - pool_cu[2013]
print(f'  Dong code gay lech: "pool[y] = p" duoc gan TRUOC khi tru, va vong lap bat dau')
print(f'  tu 2013 chu khong phai 2012. Nen pool[2013] = M1 nguyen ven = {M1:,},')
print(f'  chua tru {int(newy.get(2012,0)):,} khach da mua lan dau trong nam 2012.')
print(f'  Chenh o moc dau: {chenh:+,} khach.')
print()
print(f'  Ty le hut 2013: {a[0]:.2f}% (cach cu)  ->  {b[0]:.2f}% (M13)')
print(f'  Ty le hut 2022: {a[1]:.2f}% (cach cu)  ->  {b[1]:.2f}% (M13)')
