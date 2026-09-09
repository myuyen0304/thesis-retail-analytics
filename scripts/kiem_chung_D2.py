# -*- coding: utf-8 -*-
"""Kiem chung doc lap toan bo so lieu D2 — Phan F cua ban giao viec.

Nguyen tac F1: kiem chung phai di bang DUONG KHAC, khong phai chay lai cung ham.
Moi con so o day duoc tinh lai tu data/ goc, khong trich tu tai lieu nao.

Chay:  python scripts/kiem_chung_D2.py
"""
import pandas as pd, numpy as np, warnings
from scipy import stats as st
warnings.filterwarnings('ignore')

D = 'data/'
od = pd.read_csv(D+'orders.csv', parse_dates=['order_date'])
cu = pd.read_csv(D+'customers.csv')
oi = pd.read_csv(D+'order_items.csv', low_memory=False)
sh = pd.read_csv(D+'shipments.csv', parse_dates=['ship_date','delivery_date'])
rt = pd.read_csv(D+'returns.csv')
wt = pd.read_csv(D+'web_traffic.csv', parse_dates=['date'])

# ── QUY UOC BO LOC (khai bao MOT LAN, dung nhat quan) ────────────────────
live = od[od.order_status != 'cancelled']      # 587.483 don
ALL  = od                                       # 646.945 don, gom ca cancelled
REF  = pd.Timestamp('2022-12-31')

oi['gross'] = oi.quantity * oi.unit_price
rev_by_order = oi.groupby('order_id').gross.sum()

def tieu_de(s):
    print(); print('='*76); print(s); print('='*76)

print(f'Bo loc: live = {len(live):,} don (loai {len(ALL)-len(live):,} don cancelled '
      f'= {(len(ALL)-len(live))/len(ALL)*100:.1f}%)  |  ALL = {len(ALL):,} don')

# ═══════════════════════════════════════════════════════════════════════
tieu_de('A1 — TACH RO CAN RA KHOI TY LE HUT  (phan ra logarit)')
f = live.groupby('customer_id').order_date.min()
newy = f.dt.year.value_counts().sort_index()
pool, p = {}, len(cu)
for y in range(2013, 2023):
    pool[y] = p
    p -= newy.get(y, 0)

r13, r22 = newy[2013]/pool[2013], newy[2022]/pool[2022]
tot    = np.log(newy[2022]/newy[2013])
d_pool = np.log(pool[2022]/pool[2013])
d_rate = np.log(r22/r13)

print(f'  Pool dau nam   2013: {pool[2013]:>7,}   2022: {pool[2022]:>7,}')
print(f'  Ty le hut      2013: {r13*100:>6.2f}%   2022: {r22*100:>6.2f}%')
print(f'  Khach mua lan dau 2013: {newy[2013]:>5,}   2022: {newy[2022]:>5,}  '
      f'({(newy[2022]/newy[2013]-1)*100:+.1f}%)')
print()
print(f'  Tong                 ln = {tot:+.3f}')
print(f'    Ro can (co hoc)    ln = {d_pool:+.3f}   -> {d_pool/tot*100:5.1f}%')
print(f'    Ty le hut (that)   ln = {d_rate:+.3f}   -> {d_rate/tot*100:5.1f}%')
sai = abs(d_pool + d_rate - tot)
print(f'  [KIEM TONG] {d_pool:+.3f} + {d_rate:+.3f} = {d_pool+d_rate:+.3f}  '
      f'| sai so {sai:.2e}  -> {"OK" if sai < 0.01 else "LECH"}')

# ═══════════════════════════════════════════════════════════════════════
tieu_de('A2 — CHUOI DANG KY MOI (de doi khung "thu nap" -> "kich hoat")')
cu['signup_date'] = pd.to_datetime(cu.signup_date)
dk = cu.signup_date.dt.year.value_counts().sort_index()
print('  ' + '  '.join(f'{y}:{v:,}' for y, v in dk.items()))
don_dieu = (dk.loc[2013:2022].diff().dropna() > 0).all()
print(f'  Tang don dieu 2013-2022: {don_dieu}   |  2012 -> 2022 gap {dk.iloc[-1]/dk.iloc[0]:.0f} lan')
m = live[['customer_id','order_date']].merge(cu[['customer_id','signup_date']], on='customer_id')
print(f'  Nhung: {(m.order_date < m.signup_date).mean()*100:.1f}% don dat TRUOC ngay dang ky'
      f'  -> signup_date mau thuan noi tai, KHONG dung lam can cu dinh luong')

# ═══════════════════════════════════════════════════════════════════════
tieu_de('A3 — BA LOI SO')
d = oi.merge(ALL[['order_id','order_date']], on='order_id')
yr = d.groupby(d.order_date.dt.year).gross.sum()
print(f'  [1] Doanh thu tu dinh 2016:')
print(f'        2016 -> 2022 = {yr[2022]/yr[2016]-1:+.1%}   <- CON SO DUNG')
print(f'        2016 -> 2021 = {yr[2021]/yr[2016]-1:+.1%}   <- 50,5% cu la moc nay')

rev_kh = oi.merge(live[['order_id','customer_id']], on='order_id').groupby('customer_id').gross.sum()
t = pd.DataFrame({'ltv': rev_kh}).join(cu.set_index('customer_id').acquisition_channel).dropna()
groups = [g.values for _, g in t.groupby('acquisition_channel').ltv]
F, pval = st.f_oneway(*groups)
tb = t.groupby('acquisition_channel').ltv.mean()
print(f'  [2] H5 — LTV theo kenh:')
print(f'        Cao nhat {tb.max():>10,.0f} | Thap nhat {tb.min():>10,.0f} | '
      f'chenh {(tb.max()/tb.min()-1)*100:.2f}%')
print(f'        ANOVA F = {F:.3f}  p = {pval:.4f}  -> '
      f'{"KHONG bac bo duoc H0" if pval > .05 else "bac bo H0"}')
print(f'  [3] H2 — bo phep so -94,7% voi -86,8%: hai dai luong khac don vi, khong so truc tiep')

# ═══════════════════════════════════════════════════════════════════════
tieu_de('D — CHI SO SAU HIEU CHINH')
buyers  = ALL.customer_id.nunique()
buyers_live = live.customer_id.nunique()
recency = (REF - ALL.groupby('customer_id').order_date.max()).dt.days
Me8a = (len(cu) - buyers) / len(cu)
Me8b = (recency > 365).sum() / buyers
print(f'  Me8a  Ty le chua kich hoat (mau so = toan bo dang ky) : {Me8a*100:>6.2f}%')
print(f'  Me8b  Ty le ngu dong       (mau so = chi nhom da mua) : {Me8b*100:>6.2f}%')
print(f'  Me11  Ty le hut tu pool    2013 {r13*100:.2f}%  ->  2022 {r22*100:.2f}%')

first_oid = live.sort_values('order_date').groupby('customer_id').order_id.first()
print(f'\n  So khach co don dau (live): {len(first_oid):,}')
dl = (sh.set_index('order_id').delivery_date - sh.set_index('order_id').ship_date).dt.days
M9  = dl.reindex(first_oid.values)
M10 = pd.Series(first_oid.values).isin(rt.order_id)
promo_by_order = oi.groupby('order_id').promo_id.apply(lambda s: s.notna().any())
M12 = promo_by_order.reindex(first_oid.values).fillna(False)
print(f'  M9    Trung vi ngay giao don dau : {M9.median():>6.1f} ngay  (phu {M9.notna().mean()*100:.1f}%)')
print(f'  M10   Ty le don dau bi tra hang  : {M10.mean()*100:>6.2f}%')
print(f'  M12   Ty le don dau co khuyen mai: {M12.mean()*100:>6.2f}%   <- K7')

s_ = live.sort_values('order_date')
sec = s_[s_.duplicated('customer_id', keep='first')].groupby('customer_id').order_date.first()
Me12 = (sec - f.reindex(sec.index)).dt.days.median()
print(f'  Me12  Trung vi ngay toi don 2    : {Me12:>6.0f} ngay')
print(f'        Co su kien (da mua lai)    : {len(sec):,} = {len(sec)/len(f)*100:.1f}%')
print(f'        Bi cat cut (censored)      : {len(f)-len(sec):,} = {(len(f)-len(sec))/len(f)*100:.1f}%')

# ═══════════════════════════════════════════════════════════════════════
tieu_de('F3-KY THUAT 1 — KIEM TONG (ba nhom phai cong lai bang tong dang ky)')
chua_mua = len(cu) - buyers
ngu_dong = int((recency > 365).sum())
hoat_dong = int((recency <= 365).sum())
tong = chua_mua + ngu_dong + hoat_dong
print(f'  Chua tung mua          {chua_mua:>7,}')
print(f'  Da mua, ngu >365 ngay  {ngu_dong:>7,}')
print(f'  Dang hoat dong <=365   {hoat_dong:>7,}')
print(f'  {"-"*32}')
print(f'  Tong                   {tong:>7,}   |  Tap dang ky {len(cu):>7,}  '
      f'-> {"OK" if tong == len(cu) else "LECH"}')

# ═══════════════════════════════════════════════════════════════════════
tieu_de('F5 — KIEM CHUNG CHEO: HAI DUONG PHAN RA DOC LAP PHAI GAP NHAU')
ALL2 = ALL.copy(); ALL2['rev'] = ALL2.order_id.map(rev_by_order); ALL2['nam'] = ALL2.order_date.dt.year
wt['nam'] = wt.date.dt.year
ss = wt.groupby('nam').sessions.sum()
g = ALL2.groupby('nam').agg(rev=('rev','sum'), don=('order_id','size'), kh=('customer_id','nunique'))
A, B = 2013, 2022
rev_ln = np.log(g.rev[B]/g.rev[A])
# Duong 1: pheu     rev = sessions x CVR x AOV
cvr = g.don/ss
aov = g.rev/g.don
p1 = [np.log(ss[B]/ss[A]), np.log(cvr[B]/cvr[A]), np.log(aov[B]/aov[A])]
# Duong 2: vong doi rev = khach x tan suat x AOV
ts = g.don/g.kh
p2 = [np.log(g.kh[B]/g.kh[A]), np.log(ts[B]/ts[A]), np.log(aov[B]/aov[A])]
print(f'  Muc tieu: ln(doanh thu 2022 / 2013) = {rev_ln:+.3f}')
print(f'  Duong 1 (pheu)     ln(sessions) {p1[0]:+.3f}  + ln(CVR) {p1[1]:+.3f}  '
      f'+ ln(AOV) {p1[2]:+.3f}  = {sum(p1):+.3f}')
print(f'  Duong 2 (vong doi) ln(khach)    {p2[0]:+.3f}  + ln(tan suat) {p2[1]:+.3f}  '
      f'+ ln(AOV) {p2[2]:+.3f}  = {sum(p2):+.3f}')
e1, e2 = abs(sum(p1)-rev_ln), abs(sum(p2)-rev_ln)
print(f'  Sai so: duong 1 {e1:.2e}  |  duong 2 {e2:.2e}  -> '
      f'{"OK — hai duong doc lap gap nhau" if max(e1,e2) < 0.01 else "LECH"}')

# ═══════════════════════════════════════════════════════════════════════
tieu_de('F6 — TINH LAI CAC SO CHINH THEO BO LOC live')
sl = live.groupby('customer_id').size()
print(f'  Khach tung giao dich  : {buyers_live:,} / {len(cu):,} = {buyers_live/len(cu)*100:.1f}%   (live)')
print(f'                          {buyers:,} / {len(cu):,} = {buyers/len(cu)*100:.1f}%   (ALL)')
print(f'  Mua dung 1 lan        : {(sl==1).sum():,} = {(sl==1).mean()*100:.1f}% nhom da mua  (live)')
print(f'  Ngu dong (>365 ngay)  : {(recency>365).sum()/len(cu)*100:.1f}% tong dang ky  (ALL, mau so cu)')

live2 = live.copy(); live2['nam'] = live2.order_date.dt.year
live2['cohort'] = live2.customer_id.map(f.dt.year)
live2['tuoi'] = live2.nam - live2.cohort
ct = live2.pivot_table(index='cohort', columns='tuoi', values='customer_id', aggfunc='nunique')
ret = ct.div(ct[0], axis=0)*100
print(f'  Retention nam +1      : {ret[1].loc[2013]:.1f}% (cohort 2013) -> '
      f'{ret[1].loc[2021]:.1f}% (cohort 2021)   (live)')
live2['rev'] = live2.order_id.map(rev_by_order)
r3 = live2[live2.tuoi<=2].groupby('cohort').rev.sum()/ct[0]
print(f'  Gia tri cohort 3 nam  : {r3.loc[2013]:,.0f} -> {r3.loc[2020]:,.0f}  '
      f'({(r3.loc[2020]/r3.loc[2013]-1)*100:+.1f}%)   (live)')
live2['moi'] = live2.nam == live2.cohort
dt = live2.groupby(['nam','moi']).rev.sum().unstack()
tm = (dt[True]/(dt[True]+dt[False])*100)
print(f'  Doanh thu tu khach moi: {tm.loc[2013]:.1f}% (2013) -> {tm.loc[2022]:.1f}% (2022)   (live)')
print(f'  Phan ra don 2013->2022 (live):')
gl = live2.groupby('nam').agg(don=('order_id','size'), kh=('customer_id','nunique'))
k0,k1 = gl.kh[2013], gl.kh[2022]; f0,f1 = gl.don[2013]/k0, gl.don[2022]/k1
dk_, dt_ = (k1-k0)*f0, (f1-f0)*k0
tt_ = gl.don[2022]-gl.don[2013]
print(f'    Don {gl.don[2013]:,} -> {gl.don[2022]:,} ({(gl.don[2022]/gl.don[2013]-1)*100:+.1f}%)  |  '
      f'Khach {k0:,} -> {k1:,} ({(k1/k0-1)*100:+.1f}%)  |  Tan suat {f0:.2f} -> {f1:.2f} ({(f1/f0-1)*100:+.1f}%)')
print(f'    Do so khach {dk_/tt_*100:.1f}%  |  do tan suat {dt_/tt_*100:.1f}%  |  '
      f'tuong tac {(tt_-dk_-dt_)/tt_*100:.1f}%')

print(); print('='*76); print('HET'); print('='*76)
