# -*- coding: utf-8 -*-
"""Ve duong Kaplan-Meier tach theo promo_first — yeu cau C1 cua ban giao viec."""
import pandas as pd, numpy as np, warnings
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from lifelines import KaplanMeierFitter
from lifelines.statistics import logrank_test
warnings.filterwarnings('ignore')

plt.rcParams.update({
    'font.family': ['Segoe UI','Arial','DejaVu Sans'], 'font.size': 11,
    'axes.titlesize': 14, 'axes.titleweight': 'bold',
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.grid': True, 'grid.alpha': .25, 'axes.axisbelow': True,
    'figure.dpi': 130, 'savefig.dpi': 130, 'savefig.bbox': 'tight',
})
XANH, DO, XAM = '#2b6cb0', '#c53030', '#a0aec0'

D, REF = 'data/', pd.Timestamp('2022-12-31')
od = pd.read_csv(D+'orders.csv', parse_dates=['order_date'])
oi = pd.read_csv(D+'order_items.csv', low_memory=False)
live = od[od.order_status != 'cancelled']

s = live.sort_values('order_date')
first = s.groupby('customer_id').agg(oid1=('order_id','first'), d1=('order_date','first'))
sec = s[s.duplicated('customer_id', keep='first')].groupby('customer_id').order_date.first()

df = first.copy()
df['d2'] = sec.reindex(df.index)
df['su_kien'] = df.d2.notna().astype(int)
df['thoi_gian'] = np.where(df.su_kien == 1, (df.d2-df.d1).dt.days, (REF-df.d1).dt.days)
df = df[df.thoi_gian > 0]
df['promo_first'] = df.oid1.map(
    oi.groupby('order_id').promo_id.apply(lambda x: x.notna().any())).fillna(False).astype(int)

fig, ax = plt.subplots(figsize=(10, 5.2))
km = KaplanMeierFitter()
moc = {}
for v, ten, mau in [(0, 'Đơn đầu KHÔNG khuyến mại', XANH), (1, 'Đơn đầu CÓ khuyến mại', DO)]:
    d = df[df.promo_first == v]
    km.fit(d.thoi_gian, d.su_kien, label=f'{ten}  (n = {len(d):,})'.replace(',', '.'))
    km.plot_survival_function(ax=ax, color=mau, lw=2.6, ci_alpha=.12)
    moc[v] = float(km.predict(365))

ax.axvline(365, color=XAM, ls=':', lw=1.6)
ax.annotate('', xy=(365, moc[0]), xytext=(365, moc[1]),
            arrowprops=dict(arrowstyle='<->', color='#1a202c', lw=1.8))
ax.text(395, (moc[0]+moc[1])/2, f'Chênh {(moc[1]-moc[0])*100:.1f}\nđiểm %\ntại 1 năm',
        fontsize=10.5, fontweight='bold', va='center')
ax.text(372, .96, 'Mốc 1 năm', color='#4a5568', fontsize=10)

lr = logrank_test(df[df.promo_first==0].thoi_gian, df[df.promo_first==1].thoi_gian,
                  df[df.promo_first==0].su_kien, df[df.promo_first==1].su_kien)
ax.text(1180, .93,
        f'Log-rank\n$\\chi^2$ = {lr.test_statistic:.1f}\np < 0,001',
        fontsize=10.5, va='top', ha='left',
        bbox=dict(boxstyle='round,pad=.5', fc='#fff8e1', ec='#d6b656'))

ax.set_xlabel('Số ngày kể từ đơn hàng đầu tiên')
ax.set_ylabel('Tỷ lệ khách CHƯA quay lại mua')
ax.set_title('Khách có khuyến mại ở đơn đầu quay lại chậm hơn — nhưng phần lớn là hiệu ứng cohort')
ax.set_xlim(0, 1500); ax.set_ylim(.3, 1.0)
ax.legend(loc='lower left', frameon=False)
fig.subplots_adjust(bottom=0.26)
fig.text(0.125, 0.055,
         'Đường thấp hơn = quay lại nhiều hơn. Vùng mờ là khoảng tin cậy 95%.\n'
         'Khoảng cách thô này gồm cả hiệu ứng cohort; sau khi kiểm soát, HR chỉ còn 0,948.',
         fontsize=9.5, color='#4a5568', style='italic', va='top')

fig.savefig('docs/hinh/12-kaplan-meier-promo.png')
print('Da luu docs/hinh/12-kaplan-meier-promo.png')
print(f'  Chua quay lai tai 365 ngay: khong promo {moc[0]:.3f} | co promo {moc[1]:.3f}')
print(f'  Chenh {(moc[1]-moc[0])*100:.1f} diem phan tram')
print(f'  Log-rank chi2 = {lr.test_statistic:.2f}, p = {lr.p_value:.3e}')
