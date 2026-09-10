# -*- coding: utf-8 -*-
"""B16 — Me5, Me6 co lech theo THANG mua dau khong?"""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
D = 'data/'
od = pd.read_csv(D+'orders.csv', parse_dates=['order_date'])
oi = pd.read_csv(D+'order_items.csv', low_memory=False)
oi['gross'] = oi.quantity*oi.unit_price
rev_o = oi.groupby('order_id').gross.sum()
live = od[od.order_status != 'cancelled'].copy()
live['nam'] = live.order_date.dt.year
live['rev'] = live.order_id.map(rev_o)
f = live.groupby('customer_id').order_date.min()
live['cohort'] = live.customer_id.map(f.dt.year)
def td(s): print(); print('='*78); print(s); print('='*78)

td('1. COHORT 2013 — retention nam +1 theo THANG mua dau')
c13 = f[f.dt.year == 2013]
h14 = set(live[live.nam == 2014].customer_id)
rows = []
for th in range(1, 13):
    kh = set(c13[c13.dt.month == th].index)
    if kh:
        rows.append([th, len(kh), len(kh & h14), len(kh & h14)/len(kh)*100])
b = pd.DataFrame(rows, columns=['Thang','So khach','Quay lai 2014','Ty le %'])
b['Ty le %'] = b['Ty le %'].round(1)
print(b.to_string(index=False))
print(f'\n  Thang 1: {b.iloc[0]["Ty le %"]:.1f}%   Thang 12: {b.iloc[-1]["Ty le %"]:.1f}%'
      f'   Chenh {b.iloc[-1]["Ty le %"]-b.iloc[0]["Ty le %"]:+.1f} diem')

td('2. PHAN BO THANG MUA DAU — cohort 2013 vs cohort 2020')
for c in (2013, 2020):
    fc = f[f.dt.year == c]
    pb = (fc.dt.month.value_counts(normalize=True).sort_index()*100).round(1)
    print(f'  Cohort {c}: ' + '  '.join(f'T{m}:{v:.1f}%' for m, v in pb.items()))

td('3. TINH LAI Me5 VA Me6 THEO CUA SO 365 / 1.095 NGAY')
lv = live[['customer_id','order_date','rev']].copy()
lv['d1'] = lv.customer_id.map(f)
lv['ngay'] = (lv.order_date - lv.d1).dt.days
lv['cohort'] = lv.customer_id.map(f.dt.year)
co = lv.groupby('cohort').customer_id.nunique()

# Me5 phien ban 365 ngay
me5_ngay = {}
for c in sorted(co.index):
    kh = set(f[f.dt.year == c].index)
    q = lv[(lv.cohort == c) & (lv.ngay >= 1) & (lv.ngay <= 365)].customer_id.nunique()
    me5_ngay[c] = q/len(kh)*100
# Me5 phien ban nam duong lich
ct = live.pivot_table(index='cohort', columns=live.nam-live.cohort,
                      values='customer_id', aggfunc='nunique')
me5_nam = (ct[1]/ct[0]*100)

print(f'  {"Cohort":>7} {"Nam duong lich":>16} {"365 ngay":>11} {"Chenh":>9}')
print('  ' + '-'*48)
for c in sorted(co.index):
    if c in me5_nam.index and not np.isnan(me5_nam[c]):
        print(f'  {c:>7} {me5_nam[c]:>15.1f}% {me5_ngay[c]:>10.1f}% '
              f'{me5_ngay[c]-me5_nam[c]:>+8.1f}')

print()
me6_ngay = {}
for c in sorted(co.index):
    r = lv[(lv.cohort == c) & (lv.ngay <= 1095)].rev.sum()
    me6_ngay[c] = r/co[c]
lv['tuoi'] = lv.order_date.dt.year - lv.cohort
me6_nam = (lv[lv.tuoi <= 2].groupby('cohort').rev.sum()/co)
print(f'  {"Cohort":>7} {"Me6 nam DL":>13} {"Me6 1095 ngay":>15} {"Chenh %":>9}')
print('  ' + '-'*48)
for c in sorted(co.index):
    if c <= 2019:
        print(f'  {c:>7} {me6_nam[c]:>13,.0f} {me6_ngay[c]:>15,.0f} '
              f'{(me6_ngay[c]/me6_nam[c]-1)*100:>+8.1f}%')
