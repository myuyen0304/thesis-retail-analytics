# -*- coding: utf-8 -*-
"""Nghiem thu Phan D — moi gia tri phai khop trong sai so 0,5 diem phan tram.

Neu co dong LECH, kiem tra theo thu tu:
  (1) da dung dung 'live' hay 'orders' chua
  (2) REF co dung 2022-12-31 khong
  (3) duong dan data/ co tro vao Bronze chua lam sach khong
"""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')

D = 'data/'
orders      = pd.read_csv(D+'orders.csv', parse_dates=['order_date'])
customers   = pd.read_csv(D+'customers.csv')
order_items = pd.read_csv(D+'order_items.csv', low_memory=False)
shipments   = pd.read_csv(D+'shipments.csv', parse_dates=['ship_date','delivery_date'])
returns     = pd.read_csv(D+'returns.csv')

live = orders[orders.order_status != 'cancelled']
REF  = pd.Timestamp('2022-12-31')
first_oid = live.sort_values('order_date').groupby('customer_id').order_id.first()
f = live.groupby('customer_id').order_date.min()

buyers  = orders.customer_id.nunique()
recency = (REF - orders.groupby('customer_id').order_date.max()).dt.days
Me8a = (len(customers) - buyers) / len(customers)
Me8b = (recency > 365).sum() / buyers

new_by_year = f.dt.year.value_counts().sort_index()
M13, p = {}, len(customers)
for y in range(2013, 2023):
    M13[y] = p; p -= new_by_year.get(y, 0)

promo_by_order = order_items.groupby('order_id').promo_id.apply(lambda s: s.notna().any())
M12 = promo_by_order.reindex(first_oid.values).fillna(False)
dl  = (shipments.set_index('order_id').delivery_date
     - shipments.set_index('order_id').ship_date).dt.days
M9  = dl.reindex(first_oid.values)
M10 = pd.Series(first_oid.values).isin(returns.order_id)

s   = live.sort_values('order_date')
sec = s[s.duplicated('customer_id', keep='first')].groupby('customer_id').order_date.first()
Me12 = (sec - f.reindex(sec.index)).dt.days.median()

ket_qua = [
    ("Me8a  chua kich hoat",      Me8a*100,                        26.0),
    ("Me8b  ngu dong",            Me8b*100,                        72.6),
    ("Me11  hut tu pool 2013",    new_by_year[2013]/M13[2013]*100, 20.02),
    ("Me11  hut tu pool 2022",    new_by_year[2022]/M13[2022]*100,  2.38),
    ("K7    don dau co promo",    M12.mean()*100,                  30.6),
    ("M9    trung vi ngay giao",  M9.median(),                      4.0),
    ("M10   ty le tra hang",      M10.mean()*100,                   6.1),
    ("Me12  trung vi toi don 2",  Me12,                           308.0),
]
so_ok = 0
for ten, thuc, mong in ket_qua:
    ok = abs(thuc - mong) <= 0.5
    so_ok += ok
    print(f"{'OK  ' if ok else 'LECH'} {ten:26s} {thuc:9.2f}   (ky vong {mong})")

print()
print(f"Ket qua: {so_ok}/{len(ket_qua)} dong OK")

# Kiem tong bat buoc
chua = len(customers) - buyers
ngu  = int((recency > 365).sum())
hd   = int((recency <= 365).sum())
print(f"Kiem tong: {chua:,} + {ngu:,} + {hd:,} = {chua+ngu+hd:,} "
      f"| tap dang ky {len(customers):,} -> {'OK' if chua+ngu+hd == len(customers) else 'LECH'}")
