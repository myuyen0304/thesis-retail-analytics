# -*- coding: utf-8 -*-
"""BTN4 — Bien nao tai don hang DAU TIEN quyet dinh khach co quay lai?

Phan C cua ban giao viec. Di tu MO TA sang CO CHE.
  - Cox proportional hazards: thoi gian tu don 1 den don 2
  - Kaplan-Meier + log-rank tach theo promo_first
  - Kiem tra gia dinh PH bang Schoenfeld residuals
  - Propensity score matching de tien gan nhan qua

Chay:  python scripts/btn4_survival.py
"""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
from lifelines import CoxPHFitter, KaplanMeierFitter
from lifelines.statistics import logrank_test, proportional_hazard_test

D, REF = 'data/', pd.Timestamp('2022-12-31')
od = pd.read_csv(D+'orders.csv', parse_dates=['order_date'])
oi = pd.read_csv(D+'order_items.csv', low_memory=False)
p  = pd.read_csv(D+'products.csv', usecols=['product_id','category'])
sh = pd.read_csv(D+'shipments.csv', parse_dates=['ship_date','delivery_date'])
rt = pd.read_csv(D+'returns.csv', usecols=['order_id'])

live = od[od.order_status != 'cancelled']          # bo loc chuan
oi['gross'] = oi.quantity * oi.unit_price

def td(s): print(); print('='*76); print(s); print('='*76)

# ── 1. Xay bang cap khach hang ────────────────────────────────────────
s = live.sort_values('order_date')
first = s.groupby('customer_id').agg(oid1=('order_id','first'), d1=('order_date','first'))
sec   = s[s.duplicated('customer_id', keep='first')].groupby('customer_id').order_date.first()

df = first.copy()
df['d2'] = sec.reindex(df.index)
df['su_kien'] = df.d2.notna().astype(int)
df['thoi_gian'] = np.where(df.su_kien == 1, (df.d2-df.d1).dt.days, (REF-df.d1).dt.days)
df = df[df.thoi_gian > 0]

# Bien tai don dau
rev1 = oi.groupby('order_id').gross.sum()
df['aov_first'] = df.oid1.map(rev1)
promo1 = oi.groupby('order_id').promo_id.apply(lambda x: x.notna().any())
df['promo_first'] = df.oid1.map(promo1).fillna(False).astype(int)
dl = (sh.set_index('order_id').delivery_date - sh.set_index('order_id').ship_date).dt.days
df['delivery_days'] = df.oid1.map(dl)
df['returned_first'] = df.oid1.isin(set(rt.order_id)).astype(int)
cat1 = (oi.merge(p, on='product_id').groupby(['order_id','category']).gross.sum()
          .reset_index().sort_values('gross').groupby('order_id').category.last())
df['category_first'] = df.oid1.map(cat1)
df['cohort_year'] = df.d1.dt.year

print(f'So khach          : {len(df):,}')
print(f'  Da mua lai      : {df.su_kien.sum():,} = {df.su_kien.mean()*100:.1f}%')
print(f'  Bi cat cut      : {(1-df.su_kien).sum():,} = {(1-df.su_kien.mean())*100:.1f}%')
print(f'  Trung vi t/gian : {df[df.su_kien==1].thoi_gian.median():.0f} ngay')
print(f'  Don dau co promo: {df.promo_first.mean()*100:.1f}%')
print(f'  Phu delivery    : {df.delivery_days.notna().mean()*100:.1f}%')

# ── 2. Tin hieu tho truoc khi kiem soat ───────────────────────────────
td('2. TIN HIEU THO (chua kiem soat gi — CHUA phai nhan qua)')
sl = live.groupby('customer_id').size()
df['don_tron_doi'] = sl.reindex(df.index)
for v, ten in [(1,'CO promo   '), (0,'KHONG promo')]:
    d = df[df.promo_first == v]
    print(f'  Don dau {ten}: {len(d):>6,} khach | {d.don_tron_doi.mean():.2f} don tron doi '
          f'| mua lai {d.su_kien.mean()*100:.1f}%')
r = df[df.promo_first==1].don_tron_doi.mean() / df[df.promo_first==0].don_tron_doi.mean()
print(f'  -> Nhom co promo mua it hon {(1-r)*100:.1f}%')

# ── 3. Kaplan-Meier + log-rank ────────────────────────────────────────
td('3. KAPLAN-MEIER + LOG-RANK theo promo_first')
km = KaplanMeierFitter()
moc = {}
for v, ten in [(0,'KHONG promo'), (1,'CO promo   ')]:
    d = df[df.promo_first==v]
    km.fit(d.thoi_gian, d.su_kien)
    moc[v] = [float(km.predict(t)) for t in (90,180,365,730)]
    print(f'  {ten}: ty le CHUA quay lai sau  90n {moc[v][0]:.3f} | 180n {moc[v][1]:.3f} '
          f'| 365n {moc[v][2]:.3f} | 730n {moc[v][3]:.3f}')
lr = logrank_test(df[df.promo_first==0].thoi_gian, df[df.promo_first==1].thoi_gian,
                  df[df.promo_first==0].su_kien, df[df.promo_first==1].su_kien)
print(f'  Log-rank: chi2 = {lr.test_statistic:.2f}  p = {lr.p_value:.3e}  -> '
      f'{"khac biet co y nghia thong ke" if lr.p_value < .05 else "khong khac biet"}')

# ── 4. Cox proportional hazards ───────────────────────────────────────
td('4. COX PROPORTIONAL HAZARDS (da kiem soat cohort, danh muc, gia tri don)')
m = df.dropna(subset=['delivery_days','aov_first','category_first']).copy()
m['log_aov'] = np.log1p(m.aov_first)
X = pd.get_dummies(m[['thoi_gian','su_kien','promo_first','delivery_days','returned_first',
                      'log_aov','category_first','cohort_year']],
                   columns=['category_first'], drop_first=True, dtype=float)
X['cohort_year'] = X.cohort_year - X.cohort_year.min()
print(f'  Mau dung duoc: {len(X):,} khach ({len(X)/len(df)*100:.1f}% tong)')
cph = CoxPHFitter(penalizer=0.01).fit(X, 'thoi_gian', 'su_kien')
r = cph.summary[['exp(coef)','exp(coef) lower 95%','exp(coef) upper 95%','p']]
r.columns = ['HR','CI_thap','CI_cao','p']
print()
print(r.round(4).to_string())
print(f'\n  Concordance = {cph.concordance_index_:.4f}')
print('  HR > 1: quay lai NHANH hon (tot)  |  HR < 1: quay lai CHAM hon (xau)')

# ── 5. Kiem tra gia dinh PH ───────────────────────────────────────────
td('5. KIEM TRA GIA DINH PROPORTIONAL HAZARDS (Schoenfeld)')
try:
    ph = proportional_hazard_test(cph, X, time_transform='rank')
    res = ph.summary[['test_statistic','p']].round(4)
    print(res.to_string())
    vp = res[res.p < 0.05].index.tolist()
    print(f'\n  Bien VI PHAM gia dinh PH (p < 0,05): {vp if vp else "khong co"}')
    if vp:
        print('  -> Phai bao cao ro va dien giai HR nhu trung binh theo thoi gian,')
        print('     hoac tach mo hinh theo tang thoi gian. KHONG duoc lo di.')
except Exception as e:
    print(f'  Khong chay duoc: {e}')

# ── 6. Propensity score matching ──────────────────────────────────────
td('6. PROPENSITY SCORE MATCHING — tien gan nhan qua cho promo_first')
from sklearn.linear_model import LogisticRegression
cov = [c for c in X.columns if c not in ('thoi_gian','su_kien','promo_first')]
ps = LogisticRegression(max_iter=1000).fit(X[cov], X.promo_first).predict_proba(X[cov])[:,1]
mm = X.copy(); mm['ps'] = ps
tr, ct = mm[mm.promo_first==1].sort_values('ps'), mm[mm.promo_first==0].sort_values('ps')
print(f'  Diem xu huong: nhom co promo TB {tr.ps.mean():.4f} | nhom khong TB {ct.ps.mean():.4f}')

idx = np.searchsorted(ct.ps.values, tr.ps.values)
idx = np.clip(idx, 1, len(ct)-1)
tk = np.where(np.abs(ct.ps.values[idx-1]-tr.ps.values) < np.abs(ct.ps.values[idx]-tr.ps.values),
              idx-1, idx)
kc = np.abs(ct.ps.values[tk] - tr.ps.values)
cal = 0.2*np.std(ps)
ok = kc < cal
print(f'  Caliper = 0,2 x do lech chuan = {cal:.5f}')
print(f'  Ghep duoc {ok.sum():,}/{len(tr):,} cap ({ok.mean()*100:.1f}%)')

gh = pd.concat([tr[ok], ct.iloc[tk[ok]]])
print(f'  Mau sau ghep: {len(gh):,}')
cph2 = CoxPHFitter(penalizer=0.01).fit(gh[['thoi_gian','su_kien','promo_first']], 'thoi_gian', 'su_kien')
hr_t = cph.summary.loc['promo_first','exp(coef)']
hr_m = cph2.summary.loc['promo_first','exp(coef)']
p_m  = cph2.summary.loc['promo_first','p']
print()
print(f'  HR promo_first TRUOC matching : {hr_t:.4f}')
print(f'  HR promo_first SAU  matching  : {hr_m:.4f}  (p = {p_m:.3e})')
print(f'  Hieu ung {"VAN CON" if abs(hr_m-1) > 0.02 and p_m < .05 else "BIEN MAT"} sau khi ghep cap')

print(); print('='*76)
print('LUU Y: HR cua promo_first la TUONG QUAN da kiem soat, khong phai nhan qua')
print('tuyet doi. Van con confound khong quan sat duoc (vi du: y dinh mua ban dau).')
print('='*76)
