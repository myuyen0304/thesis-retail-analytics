# -*- coding: utf-8 -*-
"""A7 — Vi sao moc so sanh la 2013, khong phai 2012?"""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
D = 'data/'
od = pd.read_csv(D+'orders.csv', parse_dates=['order_date'])
cu = pd.read_csv(D+'customers.csv', parse_dates=['signup_date'])
oi = pd.read_csv(D+'order_items.csv', low_memory=False)
oi['gross'] = oi.quantity * oi.unit_price
rev_o = oi.groupby('order_id').gross.sum()
live = od[od.order_status != 'cancelled'].copy()
live['nam'] = live.order_date.dt.year
live['rev'] = live.order_id.map(rev_o)
f = live.groupby('customer_id').order_date.min()
live['cohort'] = live.customer_id.map(f.dt.year)
def td(s): print(); print('='*78); print(s); print('='*78)

td('1. DO DAI KY THAT CUA 2012 — hai cach dem')
o12 = live[live.nam == 2012]
n_co_su_kien = o12.order_date.dt.date.nunique()
n_phu = (o12.order_date.max() - o12.order_date.min()).days + 1
print(f'  orders bat dau : {live.order_date.min().date()}')
print(f'  orders ket thuc: {live.order_date.max().date()}')
print()
print(f'  Cach 1  .nunique() tren ngay  : {n_co_su_kien:>3} ngay CO don hang')
print(f'  Cach 2  (max-min).days + 1    : {n_phu:>3} ngay duoc PHU')
print(f'  Lech: {n_phu - n_co_su_kien} ngay -> {"co ngay trong" if n_phu>n_co_su_kien else "khong co ngay trong"}')
print(f'  Nam 2012 co 366 ngay -> phu {n_phu/366*100:.1f}% nam')
print()
print('  -> Cau hoi "ky dai bao nhieu" phai tra loi bang CACH 2.')
print('     Cach 1 tra loi cau khac: "co bao nhieu ngay phat sinh don".')

td('2. KY NGAN HAY KINH DOANH YEU? — doanh thu/ngay')
for y in (2012, 2013):
    d = live[live.nam == y]
    sn = (d.order_date.max()-d.order_date.min()).days + 1
    print(f'  {y}: tong {d.rev.sum()/1e9:.3f} ty | {sn} ngay phu | '
          f'{d.rev.sum()/sn/1e6:.3f} trieu/ngay')
d12, d13 = live[live.nam==2012], live[live.nam==2013]
s12 = (d12.order_date.max()-d12.order_date.min()).days+1
s13 = (d13.order_date.max()-d13.order_date.min()).days+1
r12, r13 = d12.rev.sum()/s12, d13.rev.sum()/s13
print(f'\n  Ty le muc/ngay 2012 so 2013: {r12/r13:.3f}')
print(f'  -> Tong 2012 thap chu yeu do {"KY NGAN" if abs(r12/r13-1)<0.2 else "KINH DOANH YEU"}')
print(f'  Quy doi 2012 ve ca nam: {r12*366/1e9:.3f} ty (thuc te ghi nhan {d12.rev.sum()/1e9:.3f} ty)')

td('3. TY TRONG DOANH THU TU KHACH MUA LAN DAU, TUNG NAM')
live['moi'] = live.nam == live.cohort
t = live.groupby(['nam','moi']).rev.sum().unstack().fillna(0)
t.columns = ['cu','moi']
t['% tu khach moi'] = (t.moi/(t.cu+t.moi)*100).round(1)
print(t.loc[2012:2022, ['% tu khach moi']].to_string())
print()
print(f'  Nam 2012 = {t.loc[2012,"% tu khach moi"]:.1f}% — BUOC PHAI la 100% theo dinh nghia,')
print('  vi nam dau tien thi moi khach deu la khach mua lan dau.')
print('  -> Phat bieu "ty trong doanh thu khach moi sut tu X xuong 4,2%" neu lay X')
print('     la gia tri 2012 thi la HANG DUNG, khong mang thong tin.')
print(f'  Gia tri dau tien CO NGHIA la nam 2013: {t.loc[2013,"% tu khach moi"]:.1f}%')

td('4. KIEM NGHI VAN CHON LOC SO LIEU — retention nam +1 KE CA 2012')
ct = live.pivot_table(index='cohort', columns=live.nam-live.cohort,
                      values='customer_id', aggfunc='nunique')
ret1 = (ct[1]/ct[0]*100).round(1)
print('  Ty le quay lai nam +1 cho MOI cohort:')
for c, v in ret1.dropna().items():
    print(f'    cohort {c}: {v:>5.1f}%')
print()
print(f'  Bo 2012: {ret1[2013]:.1f}% -> {ret1[2021]:.1f}%  (giam {ret1[2013]-ret1[2021]:.1f} diem)')
print(f'  Ke ca 2012: {ret1[2012]:.1f}% -> {ret1[2021]:.1f}%  (giam {ret1[2012]-ret1[2021]:.1f} diem)')
print(f'  -> Tinh ca 2012 thi da roi DOC HON. Bo 2012 lam so DEP hon,')
print(f'     tuc khong phai bo de giau so xau.')

td('5. CHUOI DANG KY — signup_date phu bao nhieu nam 2012?')
s12 = cu[cu.signup_date.dt.year == 2012]
sn = (s12.signup_date.max()-s12.signup_date.min()).days + 1
print(f'  signup_date bat dau: {cu.signup_date.min().date()}')
print(f'  Nam 2012: {len(s12):,} tai khoan | phu {sn}/366 ngay = {sn/366*100:.1f}%')
o_phu = n_phu/366*100
print(f'  So voi orders phu {o_phu:.1f}% nam 2012')
print()
dk = cu.signup_date.dt.year.value_counts().sort_index()
qd = dk[2012] * 366/sn
print(f'  So dang ky 2012 quy doi ca nam: {qd:,.0f} (thuc te {dk[2012]:,})')
print(f'  Ty le 2022/2012 nguyen ban : {dk[2022]/dk[2012]:.1f} lan')
print(f'  Ty le 2022/2012 quy doi    : {dk[2022]/qd:.1f} lan')
print(f'  -> Con so "gap 22 lan" {"VAN dung" if abs(dk[2022]/qd-22)<3 else "PHAI SUA"}')

td('6. MOC BEN PHAI — moc cuoi that cua tung chi so')
print(f'  Doanh thu theo nam        : cohort nao cung tinh duoc -> moc cuoi 2022')
print(f'  Retention nam +1          : can du 1 nam sau -> moc cuoi cohort {int(ret1.dropna().index.max())}')
r3 = live[live.tuoi <= 2].groupby('cohort').rev.sum()/ct[0] if 'tuoi' in live else None
live['tuoi'] = live.nam - live.cohort
r3 = (live[live.tuoi <= 2].groupby('cohort').rev.sum()/ct[0]).dropna()
du3 = [c for c in r3.index if c + 2 <= 2022]
print(f'  Gia tri cohort 3 nam      : can du 3 nam -> moc cuoi cohort {max(du3)}')
print(f'  -> Ba moc KHAC NHAU: 2022 / {int(ret1.dropna().index.max())} / {max(du3)}')

td('7. CHUOI Me6 THEO TUNG COHORT — co don dieu khong?')
print('  Gia tri 3 nam dau moi khach (gross, live):')
for c in sorted(du3):
    print(f'    cohort {c}: {r3[c]:>10,.0f} dvtt')
v = r3.loc[sorted(du3)]
dd = (v.diff().dropna() < 0).all()
print(f'\n  Don dieu giam: {dd}')
if not dd:
    bat = v.diff()[v.diff() > 0]
    print(f'  Cohort bat len: {list(bat.index)}')
print(f'\n  Co gia tri nao = 32.743 khong? '
      f'{[c for c in v.index if abs(v[c]-32743) < 500] or "khong"}')
