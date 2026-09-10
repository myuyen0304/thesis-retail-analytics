# -*- coding: utf-8 -*-
"""B14 — penalizer, ghep co hoan lai, can bang sau ghep."""
import sys, os, numpy as np, pandas as pd, warnings
sys.path.insert(0, os.path.dirname(__file__))
warnings.filterwarnings('ignore')
from _cox_chung import bang_cox, ma_tran
from lifelines import CoxPHFitter
from sklearn.linear_model import LogisticRegression
def td(s): print(); print('='*78); print(s); print('='*78)

df = bang_cox(); X, m = ma_tran(df)

td('1. PENALIZER 0 vs 0.01')
kq = {}
for pen in (0.0, 0.01):
    try:
        c = CoxPHFitter(penalizer=pen).fit(X, 'thoi_gian', 'su_kien')
        kq[pen] = c.summary[['exp(coef)','exp(coef) lower 95%','exp(coef) upper 95%','p']]
        print(f'  penalizer={pen}: HOI TU, log-lik = {c.log_likelihood_:,.2f}')
    except Exception as e:
        print(f'  penalizer={pen}: KHONG HOI TU — {e}')
print()
print(f'  {"Bien":<28} {"HR p=0":>9} {"HR p=.01":>9} {"Chenh":>8}')
print('  ' + '-'*58)
for b in kq[0.0].index:
    a, bb = kq[0.0].loc[b,'exp(coef)'], kq[0.01].loc[b,'exp(coef)']
    print(f'  {b:<28} {a:>9.4f} {bb:>9.4f} {(bb/a-1)*100:>+7.2f}%')
print()
print('  CI cua promo_first:')
for pen in (0.0, 0.01):
    r = kq[pen].loc['promo_first']
    print(f'    p={pen}: [{r["exp(coef) lower 95%"]:.4f}, {r["exp(coef) upper 95%"]:.4f}]  '
          f'rong {r["exp(coef) upper 95%"]-r["exp(coef) lower 95%"]:.4f}')

td('2. PSM — ghep co hoan lai khong?')
cov = [c for c in X.columns if c not in ('thoi_gian','su_kien','promo_first')]
ps = LogisticRegression(max_iter=1000).fit(X[cov], X.promo_first).predict_proba(X[cov])[:,1]
mm = X.copy(); mm['ps'] = ps
tr, ct = mm[mm.promo_first==1].sort_values('ps'), mm[mm.promo_first==0].sort_values('ps')
idx = np.clip(np.searchsorted(ct.ps.values, tr.ps.values), 1, len(ct)-1)
tk = np.where(np.abs(ct.ps.values[idx-1]-tr.ps.values) < np.abs(ct.ps.values[idx]-tr.ps.values),
              idx-1, idx)
ok = np.abs(ct.ps.values[tk] - tr.ps.values) < 0.2*np.std(ps)
dung = tk[ok]
print(f'  So cap ghep duoc        : {ok.sum():,} / {len(tr):,} ({ok.mean()*100:.1f}%)')
print(f'  So khach doi chung KHAC NHAU: {len(np.unique(dung)):,}')
print(f'  -> Moi doi chung bi dung trung binh {ok.sum()/len(np.unique(dung)):.2f} lan')
vc = pd.Series(dung).value_counts()
print(f'  So lan mot doi chung bi dung NHIEU NHAT: {vc.max()}')
print(f'  Phan bo so lan dung: ' + '  '.join(f'{k} lan:{v:,}' for k,v in
      vc.value_counts().sort_index().head(6).items()))
print(f'\n  -> Ghep CO HOAN LAI. Tai lieu ghi "ghep duoc 100%" nhung khong noi')
print(f'     chi co {len(np.unique(dung)):,} nguoi doi chung khac nhau tren {ok.sum():,} cap.')

td('3. CAN BANG SAU GHEP — standardized mean difference')
gh_t = tr[ok]; gh_c = ct.iloc[dung]
print(f'  {"Bien":<28} {"SMD truoc":>11} {"SMD sau":>10}')
print('  ' + '-'*52)
for b in cov:
    a1, a0 = mm[mm.promo_first==1][b], mm[mm.promo_first==0][b]
    sd = np.sqrt((a1.var()+a0.var())/2)
    smd_t = (a1.mean()-a0.mean())/sd if sd > 0 else 0
    b1, b0 = gh_t[b], gh_c[b]
    sd2 = np.sqrt((b1.var()+b0.var())/2)
    smd_s = (b1.mean()-b0.mean())/sd2 if sd2 > 0 else 0
    co = '  <- >0,1' if abs(smd_s) > 0.1 else ''
    print(f'  {b:<28} {smd_t:>+11.4f} {smd_s:>+10.4f}{co}')
print('\n  Quy uoc: |SMD| < 0,1 la can bang tot.')

td('4. PSM DONG GOP GI NGOAI COX?')
c_goc = CoxPHFitter(penalizer=0).fit(X, 'thoi_gian', 'su_kien')
gh = pd.concat([gh_t, gh_c])
c_psm = CoxPHFitter(penalizer=0).fit(gh[['thoi_gian','su_kien','promo_first']],
                                     'thoi_gian','su_kien')
print(f'  HR promo_first — Cox day du : {c_goc.summary.loc["promo_first","exp(coef)"]:.4f}')
print(f'  HR promo_first — sau PSM    : {c_psm.summary.loc["promo_first","exp(coef)"]:.4f}')
print(f'\n  PSM ghep tren DUNG cac bien Cox da kiem soat: {", ".join(cov[:4])}...')
print('  Hai phuong phap dung CUNG mot thong tin -> ket qua gan nhau la')
print('  dieu PHAI XAY RA, khong phai bang chung doc lap.')
