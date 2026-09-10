# -*- coding: utf-8 -*-
"""B12 — promo_first co phai chi la MUA cua don dau?"""
import sys, os, numpy as np, pandas as pd, warnings
sys.path.insert(0, os.path.dirname(__file__))
warnings.filterwarnings('ignore')
from _cox_chung import bang_cox, ma_tran
from lifelines import CoxPHFitter
def td(s): print(); print('='*78); print(s); print('='*78)

td('1. LICH KHUYEN MAI CO CO DINH KHONG?')
pr = pd.read_csv('data/promotions.csv', parse_dates=['start_date','end_date'])
pr['md'] = pr.start_date.dt.strftime('%m-%d')
g = pr.groupby('promo_type' if 'promo_type' in pr else 'promo_id')
print(f'  So chien dich: {len(pr)}')
print('\n  Ngay bat dau (thang-ngay) va so lan xuat hien:')
for md, n in pr.md.value_counts().sort_index().items():
    nam = sorted(pr[pr.md == md].start_date.dt.year.tolist())
    print(f'    {md}: {n:>2} lan  nam {nam}')

td('2. BANG CHEO promo_first x THANG CUA DON DAU')
df = bang_cox()
b = df.groupby('thang_dau').agg(so_khach=('promo_first','size'),
                                co_promo=('promo_first','sum'))
b['% co promo'] = (b.co_promo/b.so_khach*100).round(1)
print(b.to_string())
print(f'\n  Min {b["% co promo"].min():.1f}%  Max {b["% co promo"].max():.1f}%  '
      f'Bien do {b["% co promo"].max()-b["% co promo"].min():.1f} diem')
cuc = b[(b['% co promo'] < 5) | (b['% co promo'] > 95)]
print(f'  Thang gan 0% hoac gan 100%: {list(cuc.index) if len(cuc) else "khong co"}')

td('3. COX THEM THANG CUA DON DAU')
X1, m = ma_tran(df)
c1 = CoxPHFitter(penalizer=0).fit(X1, 'thoi_gian', 'su_kien')
hr0 = c1.summary.loc['promo_first','exp(coef)']
print(f'  Chua co thang : HR promo_first = {hr0:.4f}  '
      f'[{c1.summary.loc["promo_first","exp(coef) lower 95%"]:.4f}, '
      f'{c1.summary.loc["promo_first","exp(coef) upper 95%"]:.4f}]')

X2, m2 = ma_tran(df, them=['thang_dau'])
c2 = CoxPHFitter(penalizer=0).fit(X2, 'thoi_gian', 'su_kien')
hr1 = c2.summary.loc['promo_first','exp(coef)']
print(f'  Da them thang : HR promo_first = {hr1:.4f}  '
      f'[{c2.summary.loc["promo_first","exp(coef) lower 95%"]:.4f}, '
      f'{c2.summary.loc["promo_first","exp(coef) upper 95%"]:.4f}]')
print(f'  Thay doi: {(hr1/hr0-1)*100:+.1f}%')

td('4. SO SANH TRONG CUNG MOT CUA SO KHUYEN MAI')
# Chon thang co ca hai nhom du lon
for th in sorted(b.index):
    d = df[df.thang_dau == th]
    n1, n0 = (d.promo_first == 1).sum(), (d.promo_first == 0).sum()
    if n1 > 500 and n0 > 500:
        r1 = d[d.promo_first == 1].su_kien.mean()*100
        r0 = d[d.promo_first == 0].su_kien.mean()*100
        print(f'  Thang {th:>2}: co promo {n1:>6,} ({r1:.1f}% mua lai)  |  '
              f'khong promo {n0:>6,} ({r0:.1f}%)  |  chenh {r1-r0:+.1f} diem')
print('\n  Nhom "khong promo" trong cua so khuyen mai ton tai vi promo chi ap dung')
print('  cho mot so danh muc / gia tri don nhat dinh (applicable_category,')
print('  min_order_value trong promotions.csv).')
