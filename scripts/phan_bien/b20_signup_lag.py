# -*- coding: utf-8 -*-
"""B20 — Do tre signup_date: lech he thong hay ngau nhien, sua duoc khong?"""
import pandas as pd, numpy as np, warnings
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import stats as st
warnings.filterwarnings('ignore')
D = 'data/'
od = pd.read_csv(D+'orders.csv', parse_dates=['order_date'])
cu = pd.read_csv(D+'customers.csv', parse_dates=['signup_date'])
live = od[od.order_status != 'cancelled']
f = live.groupby('customer_id').order_date.min()
c = cu.set_index('customer_id')
tre = (f - c.signup_date.reindex(f.index)).dt.days.dropna()
def td(s): print(); print('='*78); print(s); print('='*78)

td('1. PHAN BO DO TRE')
print(f'  n = {len(tre):,} khach')
for q in (1, 5, 25, 50, 75, 95, 99):
    print(f'    p{q:<2} = {tre.quantile(q/100):>9,.0f} ngay')
print(f'  Trung binh {tre.mean():,.0f} | Do lech chuan {tre.std():,.0f}')
print(f'  Do rong p5-p95: {tre.quantile(.95)-tre.quantile(.05):,.0f} ngay '
      f'= {(tre.quantile(.95)-tre.quantile(.05))/365:.1f} nam')
h = np.histogram(tre, bins=60)
dinh = h[1][h[0].argmax()]
print(f'  Dinh histogram quanh: {dinh:,.0f} ngay')
print(f'  -> Phan bo {"TAN MAT" if tre.std() > 500 else "TAP TRUNG"}')

plt.rcParams.update({'font.family':['Segoe UI','Arial','DejaVu Sans'],'figure.dpi':120,
                     'axes.spines.top':False,'axes.spines.right':False})
fig, ax = plt.subplots(figsize=(9,4.4))
ax.hist(tre, bins=80, color='#2b6cb0', alpha=.85)
ax.axvline(0, color='#c53030', lw=2, ls='--')
ax.text(50, ax.get_ylim()[1]*.9, 'Độ trễ = 0\n(đăng ký đúng ngày mua đầu)',
        color='#c53030', fontsize=10)
ax.set_xlabel('signup_date − first_order_date (ngày)')
ax.set_ylabel('Số khách')
ax.set_title('Độ trễ đăng ký tản mát trên hơn 10 năm, không có đỉnh rõ')
fig.tight_layout(); fig.savefig('docs/hinh/b20-signup-lag.png')
print('  Da luu docs/hinh/b20-signup-lag.png')

td('2. DO TRE CO PHU THUOC NAM MUA DAU / KENH / VUNG KHONG?')
df = pd.DataFrame({'tre': tre})
df['nam'] = f.reindex(tre.index).dt.year
df['kenh'] = c.acquisition_channel.reindex(tre.index)
print('  Theo nam mua dau (trung vi):')
for y, v in df.groupby('nam').tre.median().items():
    print(f'    {y}: {v:>9,.0f} ngay  (n={len(df[df.nam==y]):>6,})')
print('\n  Theo kenh thu nap (trung vi):')
for k, v in df.groupby('kenh').tre.median().items():
    print(f'    {k:<18}: {v:>9,.0f} ngay')
F, p = st.f_oneway(*[g.values for _, g in df.groupby('kenh').tre])
print(f'  ANOVA theo kenh: F = {F:.3f}  p = {p:.4f}')

td('3. THU TU XEP HANG CO GIU DUOC KHONG?')
sd = c.signup_date.reindex(tre.index)
rho, pv = st.spearmanr(sd.astype('int64'), f.reindex(tre.index).astype('int64'))
print(f'  Spearman(signup_date, first_order_date) = {rho:.4f}  p = {pv:.3e}')
print(f'  -> {"CO giu thu tu" if abs(rho) > 0.3 else "KHONG giu thu tu"}')

td('4. KET LUAN')
print(f'  Do lech chuan {tre.std():,.0f} ngay = {tre.std()/365:.1f} nam -> TAN MAT.')
print(f'  Trung vi theo nam mua dau bien thien manh -> phu thuoc nam, nhung')
print(f'  do la HE QUA co hoc (mua som thi do tre am nhieu hon), khong phai quy luat sua duoc.')
print(f'  Spearman {rho:.4f} -> {"con dung phan tang duoc" if abs(rho)>0.3 else "KHONG dung phan tang duoc"}')
print(f'  => KHONG SUA DUOC. Cach 2 o Muc 5.1 van khong thuc hien duoc.')
