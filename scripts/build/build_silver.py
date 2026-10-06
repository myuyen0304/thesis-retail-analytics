"""Tiền xử lý: 14 CSV nguồn -> Silver 3NF gồm 19 file CSV.

Thiết kế theo `docs/design/normalized_schema.mmd` (relational diagram) và DDL §8 của `docs/normalized_schema.md`.
Logic port từ `archive/databricks/retail_medallion/src/silver/core/*.sql`, trừ hai chỗ theo sơ đồ đã chốt:
`payment_method` nằm ở `payment` (không ở `order`), `zip` là chuỗi.

Nguyên tắc:
- Đọc mọi cột dạng chuỗi; cột giữ lại được ghi ra đúng như nguồn, chỉ ép kiểu khi kiểm tra.
- Chỉ bỏ một cột sau khi đã đối soát nó là bản sao / dẫn xuất khớp 100%.
- Có bất kỳ check nào FAIL thì dừng, không ghi file nào.

Chạy từ root repo:  .venv/Scripts/python.exe scripts/build/build_silver.py
"""
import os
import sys

import numpy as np
import pandas as pd

DATA = 'data'
OUT = 'silver'  # root repo; đã gitignore như data/
R = lambda f, **k: pd.read_csv(f'{DATA}/{f}', dtype=str, low_memory=False, **k)

num = lambda s: pd.to_numeric(s)
day = lambda s: pd.to_datetime(s, format='%Y-%m-%d')

results = []


def check(name, violations, total=None):
    violations = int(violations)
    results.append((name, violations))
    mark = 'PASS' if violations == 0 else 'FAIL'
    tail = f' / {total:,}' if total is not None else ''
    print(f'  {mark}  {name:62s} {violations:>7,} vi phạm{tail}')


# ============================================================ 1. Contract nguồn
print('1. Contract nguồn')
SOURCES = {
    'geography':         (['zip', 'city', 'region', 'district'], 39_948),
    'customers':         (['customer_id', 'zip', 'city', 'signup_date', 'gender', 'age_group', 'acquisition_channel'], 121_930),
    'products':          (['product_id', 'product_name', 'category', 'segment', 'size', 'color', 'price', 'cogs'], 2_412),
    'promotions':        (['promo_id', 'promo_name', 'promo_type', 'discount_value', 'start_date', 'end_date',
                           'applicable_category', 'promo_channel', 'stackable_flag', 'min_order_value'], 50),
    'orders':            (['order_id', 'order_date', 'customer_id', 'zip', 'order_status', 'payment_method',
                           'device_type', 'order_source'], 646_945),
    'order_items':       (['order_id', 'product_id', 'quantity', 'unit_price', 'discount_amount', 'promo_id', 'promo_id_2'], 714_669),
    'payments':          (['order_id', 'payment_method', 'payment_value', 'installments'], 646_945),
    'shipments':         (['order_id', 'ship_date', 'delivery_date', 'shipping_fee'], 566_067),
    'returns':           (['return_id', 'order_id', 'product_id', 'return_date', 'return_reason', 'return_quantity', 'refund_amount'], 39_939),
    'reviews':           (['review_id', 'order_id', 'product_id', 'customer_id', 'review_date', 'rating', 'review_title'], 113_551),
    'inventory':         (['snapshot_date', 'product_id', 'stock_on_hand', 'units_received', 'units_sold', 'stockout_days',
                           'days_of_supply', 'fill_rate', 'stockout_flag', 'overstock_flag', 'reorder_flag',
                           'sell_through_rate', 'product_name', 'category', 'segment', 'year', 'month'], 60_247),
    'web_traffic':       (['date', 'sessions', 'unique_visitors', 'page_views', 'bounce_rate',
                           'avg_session_duration_sec', 'traffic_source'], 3_652),
    'sales':             (['Date', 'Revenue', 'COGS'], 3_833),
    'sample_submission': (['Date', 'Revenue', 'COGS'], 548),
}
src = {}
for name, (cols, rows) in SOURCES.items():
    df = R(f'{name}.csv')
    check(f'{name}: header + {rows:,} dòng', (list(df.columns) != cols) + (len(df) != rows))
    for c in df.columns:  # trim, chuỗi rỗng -> NaN
        df[c] = df[c].str.strip().replace('', np.nan)
    src[name] = df

geo, cus, prd, pro = src['geography'], src['customers'], src['products'], src['promotions']
ords, itm, pay, shp = src['orders'], src['order_items'], src['payments'], src['shipments']
ret, rev, inv, web = src['returns'], src['reviews'], src['inventory'], src['web_traffic']

# ============================================================ 2. Dựng 19 bảng
print('\n2. Đối soát trước khi bỏ cột')
T = {}

# --- Địa lý (phương án A §4.5: region tới được theo hai đường city / district)
check('city -> region là hàm', geo.groupby('city').region.nunique().gt(1).sum())
check('district -> region là hàm', geo.groupby('district').region.nunique().gt(1).sum())
T['region'] = geo[['region']].drop_duplicates().sort_values('region')
T['city'] = geo[['city', 'region']].drop_duplicates().sort_values('city')
T['district'] = geo[['district', 'region']].drop_duplicates().sort_values('district')
T['zip_area'] = geo[['zip', 'city', 'district']]

# --- Khách hàng: bỏ customers.city (bản sao geography.city qua zip)
z = cus.merge(geo[['zip', 'city']], on='zip', how='left', suffixes=('', '_geo'))
check('customers.city == geography.city qua zip', (z.city != z.city_geo).sum(), len(z))
T['customer'] = cus[['customer_id', 'zip', 'gender', 'age_group', 'acquisition_channel', 'signup_date']]

# --- Danh mục
check('product_name -> category, segment là hàm',
      prd.groupby('product_name')[['category', 'segment']].nunique().gt(1).any(axis=1).sum())
T['product_model'] = prd[['product_name', 'category', 'segment']].drop_duplicates().sort_values('product_name')
T['product'] = prd.rename(columns={'price': 'list_price', 'cogs': 'unit_cogs'})[
    ['product_id', 'product_name', 'size', 'color', 'list_price', 'unit_cogs']]
T['promotion'] = pro  # applicable_category NULL = mọi category; stackable_flag giữ 0/1 như nguồn

# --- Đơn hàng: bỏ orders.zip (bản sao customer.zip) và orders.payment_method (giữ ở payment, §4.4)
z = ords.merge(cus[['customer_id', 'zip']], on='customer_id', how='left', suffixes=('', '_cus'))
check('orders.zip == customers.zip qua customer_id', (z.zip != z.zip_cus).sum(), len(z))
z = ords.merge(pay[['order_id', 'payment_method']], on='order_id', how='left', suffixes=('', '_pay'))
check('orders.payment_method == payments.payment_method', (z.payment_method != z.payment_method_pay).sum(), len(z))
T['order'] = ords[['order_id', 'order_date', 'customer_id', 'order_status', 'device_type', 'order_source']]

# --- Dòng hàng: line_number theo THỨ TỰ NGUỒN (§2.1); product_occurrence để map return/review
itm['line_number'] = itm.groupby('order_id', sort=False).cumcount() + 1
itm['product_occurrence'] = itm.groupby(['order_id', 'product_id'], sort=False).cumcount() + 1
T['order_item'] = itm[['order_id', 'line_number', 'product_id', 'quantity', 'unit_price', 'discount_amount']]

# --- Junction khuyến mãi (tách nhóm lặp promo_id / promo_id_2, §2.2)
oip = (itm.melt(id_vars=['order_id', 'line_number'], value_vars=['promo_id', 'promo_id_2'], value_name='promo')
          .dropna(subset=['promo']).rename(columns={'promo': 'promo_id'}))
T['order_item_promotion'] = oip[['order_id', 'line_number', 'promo_id']].sort_values(['order_id', 'line_number', 'promo_id'])

# --- Thanh toán: bỏ payment_value (dẫn xuất = Σ(qty×price − discount), §5)
net = (num(itm.quantity) * num(itm.unit_price) - num(itm.discount_amount)).groupby(itm.order_id).sum()
z = pay.assign(net=pay.order_id.map(net))
check('payment_value == Σ(qty×price − discount), |sai lệch| > 0,01',
      ((num(z.payment_value) - z.net).abs() > 0.01).sum(), len(z))
T['payment'] = pay[['order_id', 'payment_method', 'installments']]

T['shipment'] = shp


# --- Hậu mãi: map (order_id, product_id, occurrence) -> line_number, rồi bỏ product_id
def map_line(df, label):
    d = df.assign(product_occurrence=df.groupby(['order_id', 'product_id'], sort=False).cumcount() + 1)
    d = d.merge(itm[['order_id', 'product_id', 'product_occurrence', 'line_number', 'quantity']],
                on=['order_id', 'product_id', 'product_occurrence'], how='left', validate='one_to_one')
    check(f'{label}: map đủ sang line_number', d.line_number.isna().sum(), len(d))
    d['line_number'] = d.line_number.astype('Int64')
    return d


rt = map_line(ret, 'returns')
T['product_return'] = rt[['return_id', 'order_id', 'line_number', 'return_date', 'return_reason',
                          'return_quantity', 'refund_amount']]

rv = map_line(rev, 'reviews')
z = rv.merge(ords[['order_id', 'customer_id']], on='order_id', how='left', suffixes=('', '_ord'))
check('reviews.customer_id == orders.customer_id', (z.customer_id != z.customer_id_ord).sum(), len(z))
check('review_title -> rating là hàm', rev.groupby('review_title').rating.nunique().gt(1).sum())
T['review_title_label'] = rev[['review_title', 'rating']].drop_duplicates().sort_values('review_title')
T['review'] = rv[['review_id', 'order_id', 'line_number', 'review_date', 'review_title']]

# --- Tồn kho: chỉ bỏ cột sau khi đối soát (§2.3, §3.1, §5 — công thức đúng ở §5.1)
i = inv.assign(**{c: num(inv[c]) for c in ['stock_on_hand', 'units_sold', 'stockout_days', 'days_of_supply',
                                            'fill_rate', 'stockout_flag', 'overstock_flag', 'reorder_flag',
                                            'sell_through_rate']})
check('inventory.reorder_flag là hằng 0', (i.reorder_flag != 0).sum(), len(i))
check('stockout_flag == (stockout_days > 0)', (i.stockout_flag != (i.stockout_days > 0)).sum(), len(i))
with np.errstate(divide='ignore', invalid='ignore'):
    dos = (i.stock_on_hand / (i.units_sold / 30)).round(1)
    str_ = (i.units_sold / (i.stock_on_hand + i.units_sold)).round(4)
same = lambda a, b: ~(np.isclose(a, b, atol=1e-9) | (a.isna() & b.isna()) | (np.isinf(a) & b.isna()))
check('days_of_supply == ROUND(stock/(sold/30), 1)', same(dos, i.days_of_supply).sum(), len(i))
check('fill_rate == ROUND(1 − stockout_days/30, 4)', same((1 - i.stockout_days / 30).round(4), i.fill_rate).sum(), len(i))
check('sell_through_rate == ROUND(sold/(stock+sold), 4)', same(str_, i.sell_through_rate).sum(), len(i))
check('overstock_flag == (days_of_supply > 90)', (i.overstock_flag != (i.days_of_supply > 90)).sum(), len(i))
z = inv.merge(prd[['product_id', 'product_name', 'category', 'segment']], on='product_id', how='left', suffixes=('', '_p'))
check('inventory.product_name/category/segment == products',
      ((z.product_name != z.product_name_p) | (z.category != z.category_p) | (z.segment != z.segment_p)).sum(), len(z))
sd = day(inv.snapshot_date)
check('inventory.year/month == tách từ snapshot_date',
      ((num(inv.year) != sd.dt.year) | (num(inv.month) != sd.dt.month)).sum(), len(inv))
T['inventory_snapshot'] = inv[['snapshot_date', 'product_id', 'stock_on_hand', 'units_received', 'units_sold', 'stockout_days']]

T['web_traffic'] = web.rename(columns={'date': 'traffic_date'})
T['daily_sales_forecast'] = src['sample_submission'].rename(
    columns={'Date': 'forecast_date', 'Revenue': 'revenue', 'COGS': 'cogs'})

# ============================================================ 3. Quality gate
print('\n3. Quality gate trên 19 bảng')

PK = {
    'region': ['region'], 'city': ['city'], 'district': ['district'], 'zip_area': ['zip'],
    'customer': ['customer_id'], 'product_model': ['product_name'], 'product': ['product_id'],
    'promotion': ['promo_id'], 'order': ['order_id'], 'order_item': ['order_id', 'line_number'],
    'order_item_promotion': ['order_id', 'line_number', 'promo_id'], 'payment': ['order_id'],
    'shipment': ['order_id'], 'product_return': ['return_id'], 'review_title_label': ['review_title'],
    'review': ['review_id'], 'inventory_snapshot': ['snapshot_date', 'product_id'],
    'web_traffic': ['traffic_date'], 'daily_sales_forecast': ['forecast_date'],
}
for t, cols in PK.items():
    d = T[t]
    check(f'PK {t}({", ".join(cols)})', d.duplicated(cols).sum() + d[cols].isna().any(axis=1).sum(), len(d))

for t, cols in [('promotion', ['promo_name']), ('product_return', ['order_id', 'line_number']),
                ('review', ['order_id', 'line_number'])]:
    check(f'UK {t}({", ".join(cols)})', T[t].duplicated(cols).sum(), len(T[t]))

FK = [  # (bảng con, cột con, bảng cha, cột cha) — theo quan hệ trong docs/design/normalized_schema.mmd
    ('city', ['region'], 'region', ['region']),
    ('district', ['region'], 'region', ['region']),
    ('zip_area', ['city'], 'city', ['city']),
    ('zip_area', ['district'], 'district', ['district']),
    ('customer', ['zip'], 'zip_area', ['zip']),
    ('product', ['product_name'], 'product_model', ['product_name']),
    ('order', ['customer_id'], 'customer', ['customer_id']),
    ('order_item', ['order_id'], 'order', ['order_id']),
    ('order_item', ['product_id'], 'product', ['product_id']),
    ('order_item_promotion', ['order_id', 'line_number'], 'order_item', ['order_id', 'line_number']),
    ('order_item_promotion', ['promo_id'], 'promotion', ['promo_id']),
    ('payment', ['order_id'], 'order', ['order_id']),
    ('shipment', ['order_id'], 'order', ['order_id']),
    ('product_return', ['order_id', 'line_number'], 'order_item', ['order_id', 'line_number']),
    ('review', ['order_id', 'line_number'], 'order_item', ['order_id', 'line_number']),
    ('review', ['review_title'], 'review_title_label', ['review_title']),
    ('inventory_snapshot', ['product_id'], 'product', ['product_id']),
]
key = lambda d, cols: pd.MultiIndex.from_frame(d[cols].astype(str))
for child, cc, parent, pc in FK:
    orphan = ~key(T[child], cc).isin(key(T[parent], pc))
    check(f'FK {child}({", ".join(cc)}) -> {parent}', orphan.sum(), len(T[child]))

check('region tới qua city == region tới qua district',
      (T['zip_area'].merge(T['city'], on='city').merge(T['district'], on='district', suffixes=('_c', '_d'))
       .pipe(lambda d: (d.region_c != d.region_d).sum())), len(T['zip_area']))
check('order ||--|{ order_item: đơn nào cũng có dòng hàng', (~T['order'].order_id.isin(itm.order_id)).sum())
check('order ||--|| payment: đơn nào cũng có payment', (~T['order'].order_id.isin(pay.order_id)).sum())

p, oi, sh = T['product'], T['order_item'], T['shipment']
CHECKS = [  # 13 ràng buộc của DDL §8 (cùng danh sách với notebooks/02_design/normalization.ipynb §6)
    ('product.unit_cogs <= list_price', num(p.unit_cogs) > num(p.list_price)),
    ('order_item.quantity > 0', num(oi.quantity) <= 0),
    ('order_item.discount_amount >= 0', num(oi.discount_amount) < 0),
    ('payment.installments > 0', num(T['payment'].installments) <= 0),
    ('shipment.ship_date NOT NULL', sh.ship_date.isna()),
    ('shipment.delivery_date >= ship_date', day(sh.delivery_date) < day(sh.ship_date)),
    ('product_return.return_quantity > 0', num(rt.return_quantity) <= 0),
    ('promotion.end_date >= start_date', day(pro.end_date) < day(pro.start_date)),
    ('review_title_label.rating BETWEEN 1 AND 5', ~num(T['review_title_label'].rating).between(1, 5)),
    ('web_traffic.unique_visitors <= sessions', num(web.unique_visitors) > num(web.sessions)),
    ('review UNIQUE(order_id, line_number)', T['review'].duplicated(['order_id', 'line_number'])),
    ('product_return UNIQUE(order_id, line_number)', T['product_return'].duplicated(['order_id', 'line_number'])),
    ('return_quantity <= quantity (join qua line_number)', num(rt.return_quantity) > num(rt.quantity)),
]
for name, bad in CHECKS:
    check(f'CHECK {name}', bad.sum(), len(bad))

# NOT NULL: mọi cột trừ các cột nullable trong DDL §8
NULLABLE = {('customer', 'signup_date'), ('shipment', 'delivery_date'), ('promotion', 'applicable_category')}
nulls = sum(int(T[t][c].isna().sum()) for t in T for c in T[t].columns if (t, c) not in NULLABLE)
check('NOT NULL trên mọi cột không nullable', nulls)

# sales.csv phải là VIEW tái tạo được: gross Revenue (không trừ discount), COGS theo product.unit_cogs
s = (oi.merge(T['order'][['order_id', 'order_date']], on='order_id')
       .merge(p[['product_id', 'unit_cogs']], on='product_id'))
s = pd.DataFrame({'Revenue': num(s.quantity) * num(s.unit_price),
                  'COGS': num(s.quantity) * num(s.unit_cogs), 'Date': s.order_date}).groupby('Date').sum()
sales = src['sales'].set_index('Date')
check('daily_sales view có đúng 3.833 ngày', len(s.index.symmetric_difference(sales.index)))
check('daily_sales Revenue/COGS khớp sales.csv (atol 1e-6)',
      (~np.isclose(s.Revenue, num(sales.Revenue.reindex(s.index)), atol=1e-6)).sum()
      + (~np.isclose(s.COGS, num(sales.COGS.reindex(s.index)), atol=1e-6)).sum(), len(s))

ROWS = {'region': 3, 'city': 42, 'district': 39, 'zip_area': 39_948, 'customer': 121_930, 'product_model': 2_172,
        'product': 2_412, 'promotion': 50, 'order': 646_945, 'order_item': 714_669, 'order_item_promotion': 276_522,
        'payment': 646_945, 'shipment': 566_067, 'product_return': 39_939, 'review_title_label': 18,
        'review': 113_551, 'inventory_snapshot': 60_247, 'web_traffic': 3_652, 'daily_sales_forecast': 548}
for t, n in ROWS.items():
    check(f'row count {t} == {n:,}', len(T[t]) != n)
check('tổng 19 bảng == 3.235.699 dòng', sum(len(d) for d in T.values()) != 3_235_699)

failed = [n for n, v in results if v]
if failed:
    print(f'\n{len(failed)} check FAIL — dừng, không ghi file nào.')
    sys.exit(1)

# ============================================================ 4. Ghi 19 CSV
print(f'\n4. Ghi ra {OUT}/  ({len(results)} check đều PASS)')
os.makedirs(OUT, exist_ok=True)
for t in PK:
    path = f'{OUT}/{t}.csv'
    T[t].to_csv(path + '.tmp', index=False)
    os.replace(path + '.tmp', path)
    print(f'  {t:22s} {len(T[t]):>9,} dòng  {T[t].shape[1]:>2} cột')
print(f'  {"TỔNG":22s} {sum(len(d) for d in T.values()):>9,} dòng')
