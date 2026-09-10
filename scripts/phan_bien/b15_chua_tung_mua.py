# -*- coding: utf-8 -*-
"""B15 — "Chua tung mua" la 26,0% hay 27,7%? Khach chi co don cancelled dung o dau?

Chay:  .venv/Scripts/python.exe scripts/phan_bien/b15_chua_tung_mua.py
"""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')

D = 'data/'
od = pd.read_csv(D + 'orders.csv', parse_dates=['order_date'])
cu = pd.read_csv(D + 'customers.csv')
oi = pd.read_csv(D + 'order_items.csv', low_memory=False)
sh = pd.read_csv(D + 'shipments.csv', parse_dates=['ship_date', 'delivery_date'])

live = od[od.order_status != 'cancelled']
ALL = od
REF = pd.Timestamp('2022-12-31')
M1 = len(cu)

def td(s):
    print(); print('=' * 78); print(s); print('=' * 78)

td('1. HAI MAU NGUOI MUA — code dang dung cai nao?')
buyers_all = ALL.customer_id.nunique()
buyers_live = live.customer_id.nunique()
print('  Nguyen van trong kiem_chung_D2.py:')
print('      buyers      = ALL.customer_id.nunique()      <- Me8a dung dong nay')
print('      buyers_live = live.customer_id.nunique()')
print()
print(f'  buyers (ALL)  = {buyers_all:,}   -> Me8a = (M1 - buyers)/M1 = '
      f'{(M1-buyers_all)/M1*100:.2f}%')
print(f'  buyers (live) = {buyers_live:,}   -> neu dung live      = '
      f'{(M1-buyers_live)/M1*100:.2f}%')
print()
print('  Muc 7 khai M2 la `live`, nhung code tinh Me8a bang `ALL`.')
print(f'  -> LECH: cong thuc khai 27,73%, so dang in ra 26,00%.')

td('2. NHOM CHENH — khach CHI co don cancelled')
chi_huy = set(ALL.customer_id) - set(live.customer_id)
print(f'  So khach: {len(chi_huy):,}  ( = {buyers_all:,} - {buyers_live:,} )')
print(f'  Chiem {len(chi_huy)/M1*100:.2f}% tap dang ky')
print()
d = ALL[ALL.customer_id.isin(chi_huy)]
print(f'  So don cua nhom nay: {len(d):,}  (toan bo deu cancelled)')
print(f'  So don/khach: min {d.groupby("customer_id").size().min()}  '
      f'max {d.groupby("customer_id").size().max()}  '
      f'trung vi {d.groupby("customer_id").size().median():.0f}')

td('3. HO DUNG O DAU TRONG BA CAU HOI CUA TAI LIEU?')

# (a) Bang ba trang thai o Muc 3 — dung ALL
recency_all = (REF - ALL.groupby('customer_id').order_date.max()).dt.days
rec_nhom = recency_all[recency_all.index.isin(chi_huy)]
print('  (a) Bang ba trang thai Muc 3 (tinh tren ALL):')
print(f'      Ho CO recency (vi ALL tinh ca don cancelled) -> KHONG nam o nhom "chua mua"')
print(f'      Ngu dong >365 ngay : {(rec_nhom > 365).sum():,}')
print(f'      Hoat dong <=365    : {(rec_nhom <= 365).sum():,}')
print(f'      -> Ho bi xep vao nhom DA MUA, du chua tung co giao dich hop le.')

# (b) Ro M13 — dung live
f_live = live.groupby('customer_id').order_date.min()
print()
print('  (b) Ro M13 (khach mua lan dau theo first_order_date, live):')
print(f'      So khach nhom nay co first_order_date theo live: '
      f'{len(set(chi_huy) & set(f_live.index)):,}')
print(f'      -> Ho KHONG bi tru khoi ro. Ro van coi ho la "chua mua".')

# (c) Mau Cox
s = live.sort_values('order_date')
first = s.groupby('customer_id').agg(oid1=('order_id', 'first'), d1=('order_date', 'first'))
sec = s[s.duplicated('customer_id', keep='first')].groupby('customer_id').order_date.first()
df = first.copy()
df['d2'] = sec.reindex(df.index)
df['su_kien'] = df.d2.notna().astype(int)
df['thoi_gian'] = np.where(df.su_kien == 1, (df.d2 - df.d1).dt.days, (REF - df.d1).dt.days)
df = df[df.thoi_gian > 0]
print()
print('  (c) Mau Cox o Muc 9:')
print(f'      Co {len(df):,} khach (dung tu live)')
print(f'      So khach nhom nay co trong mau: {len(set(chi_huy) & set(df.index)):,}')
print(f'      -> Ho KHONG vao mau Cox.')

td('4. MAU THUAN — cung mot nhom, ba cau tra loi khac nhau')
print(f'  {len(chi_huy):,} khach chi co don cancelled duoc doi xu:')
print('    Bang ba trang thai (Muc 3) : DA MUA      (vi dung ALL)')
print('    Ro M13 (Muc 2.2)           : CHUA MUA    (vi dung live)')
print('    Mau Cox (Muc 9)            : CHUA MUA    (vi dung live)')
print()
print('  -> Cung mot nhom nguoi, hai quy uoc khac nhau trong cung mot tai lieu.')

td('5. NEU CHON MOT QUY UOC DUY NHAT: "da mua" = co it nhat mot don LIVE')
chua_mua = M1 - buyers_live
recency_live = (REF - live.groupby('customer_id').order_date.max()).dt.days
ngu = int((recency_live > 365).sum())
hd = int((recency_live <= 365).sum())
print(f'  Chua tung mua          : {chua_mua:>7,}   {chua_mua/M1*100:5.2f}%')
print(f'  Da mua, ngu >365 ngay  : {ngu:>7,}   {ngu/M1*100:5.2f}%')
print(f'  Dang hoat dong <=365   : {hd:>7,}   {hd/M1*100:5.2f}%')
print('  ' + '-' * 40)
tong = chua_mua + ngu + hd
print(f'  TONG                   : {tong:>7,}   {tong/M1*100:5.2f}%')
print(f'  Kiem tong voi M1 = {M1:,} -> {"KHOP" if tong == M1 else "LECH"}')
print()
print('  So sanh voi bang hien tai trong tai lieu (dung ALL):')
recency_a = recency_all
print(f'    Chua mua  {M1-buyers_all:>7,} -> {chua_mua:>7,}   ({chua_mua-(M1-buyers_all):+,})')
print(f'    Ngu dong  {int((recency_a>365).sum()):>7,} -> {ngu:>7,}   '
      f'({ngu-int((recency_a>365).sum()):+,})')
print(f'    Hoat dong {int((recency_a<=365).sum()):>7,} -> {hd:>7,}   '
      f'({hd-int((recency_a<=365).sum()):+,})')

td('6. ME1 VA ME8A TINH LAI')
print(f'  Me1  ty le kich hoat  = M2/M1')
print(f'       theo ALL  : {buyers_all/M1*100:.2f}%   (tai lieu Muc 7 ghi 72,3% — khong khop)')
print(f'       theo live : {buyers_live/M1*100:.2f}%   <- khop 72,3%')
print(f'  Me8a ty le chua kich hoat = (M1-M2)/M1')
print(f'       theo ALL  : {(M1-buyers_all)/M1*100:.2f}%   <- so dang in trong tai lieu')
print(f'       theo live : {(M1-buyers_live)/M1*100:.2f}%   <- dung cong thuc khai')
print()
print(f'  -> Me1 dang dung live, Me8a dang dung ALL. Hai chi so bo doi nhau')
print(f'     ma khong cong lai bang 100%: {buyers_live/M1*100:.2f}% + '
      f'{(M1-buyers_all)/M1*100:.2f}% = {buyers_live/M1*100 + (M1-buyers_all)/M1*100:.2f}%')
