# -*- coding: utf-8 -*-
"""B6 — Sao hai tang phan ra dung hai phuong phap khac nhau?"""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
D = 'data/'
od = pd.read_csv(D+'orders.csv', parse_dates=['order_date'])
live = od[od.order_status != 'cancelled'].copy()
live['nam'] = live.order_date.dt.year
g = live.groupby('nam').agg(don=('order_id','size'), kh=('customer_id','nunique'))
def td(s): print(); print('='*78); print(s); print('='*78)

K0, K1 = g.kh[2013], g.kh[2022]
D0, D1 = g.don[2013], g.don[2022]
T0, T1 = D0/K0, D1/K1

td('1. DAU VAO')
print(f'  {"":12} {"2013":>10} {"2022":>10}')
print(f'  {"So don":12} {D0:>10,} {D1:>10,}')
print(f'  {"Khach":12} {K0:>10,} {K1:>10,}')
print(f'  {"Tan suat":12} {T0:>10.4f} {T1:>10.4f}')

td('2. CACH SO HOC — co so hang tuong tac (tai lieu dang dung)')
dK = (K1-K0)*T0
dT = (T1-T0)*K0
tt = (D1-D0) - dK - dT
print(f'  Tong thay doi: {D1-D0:+,} don')
print(f'    do so khach : {dK:+12,.0f}  -> {dK/(D1-D0)*100:6.1f}%')
print(f'    do tan suat : {dT:+12,.0f}  -> {dT/(D1-D0)*100:6.1f}%')
print(f'    tuong tac   : {tt:+12,.0f}  -> {tt/(D1-D0)*100:6.1f}%')
print(f'  Tai lieu ghi: 72,2% / 45,2% / -17,4%')

td('3. CACH LOGARIT — khong co so hang tuong tac')
tot = np.log(D1/D0); lK = np.log(K1/K0); lT = np.log(T1/T0)
print(f'  ln(don)      = {tot:+.4f}')
print(f'    ln(khach)  = {lK:+.4f}  -> {lK/tot*100:6.1f}%')
print(f'    ln(tan suat)= {lT:+.4f}  -> {lT/tot*100:6.1f}%')
print(f'  Kiem tong: {lK+lT:+.4f} vs {tot:+.4f}  sai so {abs(lK+lT-tot):.2e}')

td('4. DOI CHIEU — ket luan H1 co doi khong?')
print(f'  {"Phuong phap":<14} {"Mat khach":>12} {"Giam tan suat":>15} {"Tuong tac":>12}')
print('  ' + '-'*56)
print(f'  {"So hoc":<14} {dK/(D1-D0)*100:>11.1f}% {dT/(D1-D0)*100:>14.1f}% {tt/(D1-D0)*100:>11.1f}%')
print(f'  {"Logarit":<14} {lK/tot*100:>11.1f}% {lT/tot*100:>14.1f}% {"—":>12}')
print()
print(f'  H1 = "mat khach dong gop lon hon giam tan suat"')
# So sanh phai dat tren TY TRONG (deu duong), khong dat tren gia tri ln (deu am).
sh_K, sh_T = lK/tot*100, lT/tot*100
h1_so_hoc = dK/(D1-D0) > dT/(D1-D0)
h1_logarit = sh_K > sh_T
print(f'    Theo so hoc : {dK/(D1-D0)*100:.1f}% > {dT/(D1-D0)*100:.1f}%  '
      f'-> H1 {"DUNG" if h1_so_hoc else "SAI"}')
print(f'    Theo logarit: {sh_K:.1f}% > {sh_T:.1f}%  -> H1 {"DUNG" if h1_logarit else "SAI"}')
print(f'  -> Ket luan dinh tinh {"KHONG doi" if h1_so_hoc == h1_logarit else "DOI"}, '
      f'nhung ty trong khac han.')

td('5. VI SAO SO HOC CO TUONG TAC MA LOGARIT THI KHONG')
print('  So hoc:  D = K x T')
print('           dD = K1.T1 - K0.T0')
print('              = (K0+dK)(T0+dT) - K0.T0')
print('              = K0.dT + T0.dK + dK.dT      <- so hang cuoi la TUONG TAC')
print('           Ba so hang, khong the bo cai nao.')
print()
print('  Logarit: ln(D) = ln(K) + ln(T)   <- DANG THUC, dung tuyet doi')
print('           dln(D) = dln(K) + dln(T)')
print('           Chi hai so hang. Khong con du gi.')
print()
print('  -> Logarit khong "tot hon", no chi TRANH duoc so hang tuong tac bang cach')
print('     doi don vi do tu "so don" sang "ty le thay doi".')
