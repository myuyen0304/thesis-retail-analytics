# -*- coding: utf-8 -*-
"""B2 — Kiem 2 co the that bai khong?"""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
D = 'data/'
od = pd.read_csv(D+'orders.csv', parse_dates=['order_date'])
cu = pd.read_csv(D+'customers.csv')
live = od[od.order_status != 'cancelled']
M1 = len(cu)
f = live.groupby('customer_id').order_date.min()
newy = f.dt.year.value_counts().sort_index()
m0, m1 = int(newy[2013]), int(newy[2022])
def td(s): print(); print('='*78); print(s); print('='*78)

td('1. KHAI TRIEN DAI SO')
print('  Dat: P = Pool, m = khach moi, h = ty le hut = m / P')
print()
print('    d_ln(P) + d_ln(h)')
print('  = [ln(P1) - ln(P0)] + [ln(h1) - ln(h0)]')
print('  = [ln(P1) - ln(P0)] + [ln(m1/P1) - ln(m0/P0)]')
print('  = ln(P1) - ln(P0) + ln(m1) - ln(P1) - ln(m0) + ln(P0)')
print('  =                  + ln(m1)          - ln(m0)')
print('  = ln(m1) - ln(m0)  = d_ln(m)')
print()
print('  -> Moi so hang chua P deu TRIET TIEU. Dang thuc dung voi MOI gia tri P.')

td('2. THU BANG SO — thay Pool bang ba bo khac nhau')
bo = [('So tai lieu (sai)', 121930, 55738),
      ('So dung theo M13 ', M1 - int(newy[newy.index < 2013].sum()),
                            M1 - int(newy[newy.index < 2022].sum())),
      ('Cap bia 7 va 3   ', 7, 3),
      ('Cap bia 999 va 1 ', 999, 1)]
tot = np.log(m1/m0)
print(f'  Khach moi 2013 = {m0:,} | 2022 = {m1:,} | ln tong = {tot:+.6f}')
print()
print(f'  {"Bo Pool":<18} {"P0":>8} {"P1":>8} {"ln P":>10} {"ln h":>10} {"Tong":>10} {"Khop?":>7}')
print('  ' + '-'*68)
for ten, P0, P1 in bo:
    dP = np.log(P1/P0); dh = np.log((m1/P1)/(m0/P0))
    print(f'  {ten:<18} {P0:>8,} {P1:>8,} {dP:>+10.4f} {dh:>+10.4f} {dP+dh:>+10.6f} '
          f'{"KHOP" if abs(dP+dh-tot)<1e-9 else "vo":>7}')
print()
print('  -> Ca bon bo deu KHOP tuyet doi. Kiem 2 khong rang buoc Pool.')

td('3. NGHIEM THU D2 SO ME11 VOI CAI GI?')
print('  Nguyen van trong nghiem_thu_D2.py:')
print('      ("Me11  hut tu pool 2013", new_by_year[2013]/M13[2013]*100, 20.02),')
print('      ("Me11  hut tu pool 2022", new_by_year[2022]/M13[2022]*100,  2.38),')
print()
print('  -> No so gia tri tinh duoc voi HAI SO CUNG HARDCODE 20,02 va 2,38,')
print('     tuc so cua chinh lan chay truoc. Neu vong lap Pool sai thi ca hai')
print('     ben deu sai giong nhau va van in "OK".')
print('  -> Tieu chi nghiem thu do KHONG phat hien duoc sai so o B1.')

td('4. PHEP KIEM THAY THE — co the vo')
print('  De xuat: kiem tinh DONG CUA cua danh sach khach hang.')
print()
print('      Pool(Y) - Pool(Y+1)  ==  so khach mua lan dau trong nam Y')
print()
print('  Day khong phai hang dung: no rang buoc day Pool phai khop voi day cohort.')
rows = []
for y in range(2012, 2022):
    P0 = M1 - int(newy[newy.index < y].sum())
    P1 = M1 - int(newy[newy.index < y+1].sum())
    rows.append([y, P0-P1, int(newy.get(y,0)), P0-P1 == int(newy.get(y,0))])
print()
print(f'  {"Nam":>5} {"Pool(Y)-Pool(Y+1)":>18} {"Khach moi(Y)":>14} {"Khop":>6}')
for y, d, n, ok in rows:
    print(f'  {y:>5} {d:>18,} {n:>14,} {"OK" if ok else "VO":>6}')
print()
print('  Voi day Pool SAI cua tai lieu (bat dau 2013 khong tru cohort 2012):')
pool_cu, p = {}, M1
for y in range(2013, 2023):
    pool_cu[y] = p; p -= int(newy.get(y, 0))
print(f'    Pool(2013) - Pool(2014) = {pool_cu[2013]-pool_cu[2014]:,}')
print(f'    Khach moi 2013          = {int(newy[2013]):,}')
print(f'    -> {"KHOP" if pool_cu[2013]-pool_cu[2014]==int(newy[2013]) else "VO"}')
print()
print('  Phep kiem nay KHOP ca voi day sai, vi day sai chi lech mot HANG SO.')
print('  Muon bat duoc B1 phai them mot neo tuyet doi:')
print()
print('      Pool(nam dau tien co du lieu) == M1')
print(f'      Pool(2012) = {M1 - int(newy[newy.index < 2012].sum()):,} vs M1 = {M1:,}  '
      f'-> {"OK" if M1 - int(newy[newy.index<2012].sum())==M1 else "VO"}')
print(f'      Day cu bat dau tu 2013 nen KHONG co diem neo nay -> loi lot qua.')
