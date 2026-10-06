"""Gold: Silver 3NF (19 CSV) -> Data Warehouse star schema trên DuckDB.

Thiết kế theo `docs/design/star_schema.mmd` và DDL §7 của `docs/star_schema.md` (6 dim, 7 fact, 1 bridge).
Platform: DuckDB — kho OLAP dạng cột, nhúng trong 1 file, không cần server (lý do: star_schema.md §10).

Nguyên tắc (giống scripts/build/build_silver.py):
- Chỉ đọc `silver/`; `data/sales.csv` chỉ dùng để ĐỐI SOÁT, không nạp vào kho.
- Dựng vào file tạm; có bất kỳ check nào FAIL thì dừng, không thay file kho cũ.

Lệch so với DDL §7 (có chủ ý):
- `current_price`, `current_cogs`, `cogs_amount` dùng DOUBLE thay vì DECIMAL: unit_cogs nguồn là số thực
  thật (vd 15291.061153846153); ép DECIMAL làm Σ COGS/ngày lệch sales.csv ở chữ số thứ 2.
  `fact_daily_sales.cogs` = ROUND(Σ, 2) — đúng cách sales.csv được làm tròn.
- 3 cột tỷ lệ tồn kho làm tròn kiểu numpy (nhân 10^d, về số chẵn) như nguồn: 146,25 -> 146,2.

Chạy từ root repo:  .venv/Scripts/python.exe scripts/build/build_gold.py
Dùng:  duckdb.connect('warehouse/retail.duckdb', read_only=True)
"""
import os
import sys

import duckdb

SILVER = 'silver'
DATA = 'data'
OUT = 'warehouse/retail.duckdb'
TMP = OUT + '.tmp'

results = []


def check(name, violations, total=None):
    violations = int(violations)
    results.append((name, violations))
    mark = 'PASS' if violations == 0 else 'FAIL'
    tail = f' / {total:,}' if total is not None else ''
    print(f'  {mark}  {name:62s} {violations:>7,} vi phạm{tail}')


os.makedirs('warehouse', exist_ok=True)
for f in (TMP, TMP + '.wal'):
    if os.path.exists(f):
        os.remove(f)
con = duckdb.connect(TMP)
one = lambda sql: con.sql(sql).fetchone()[0]

# ============================================================ 1. Staging: 19 CSV silver
print('1. Nạp silver/ vào staging (stg, trong RAM)')
con.sql("ATTACH ':memory:' AS stg")  # staging nằm trong RAM, không chiếm chỗ trong file kho
SILVER_TABLES = ['region', 'city', 'district', 'zip_area', 'customer', 'product_model', 'product', 'promotion',
                 'order', 'order_item', 'order_item_promotion', 'payment', 'shipment', 'product_return',
                 'review_title_label', 'review', 'inventory_snapshot', 'web_traffic', 'daily_sales_forecast']
TYPES = {  # ép kiểu tường minh những cột dễ đoán sai
    'zip_area': {'zip': 'INTEGER'}, 'customer': {'zip': 'INTEGER', 'signup_date': 'DATE'},
    'product': {'list_price': 'DOUBLE', 'unit_cogs': 'DOUBLE'},
    'order_item': {'unit_price': 'DECIMAL(14,4)', 'discount_amount': 'DECIMAL(16,4)'},
    'promotion': {'applicable_category': 'VARCHAR'},
}
for t in SILVER_TABLES:
    types = TYPES.get(t, {})
    tp = f', types={types!r}' if types else ''  # dict Python trùng cú pháp struct của DuckDB
    con.sql(f"CREATE TABLE stg.\"{t}\" AS SELECT * FROM read_csv('{SILVER}/{t}.csv', header=true{tp})")
    print(f'  stg.{t:22s} {one(f"SELECT COUNT(*) FROM stg.\"{t}\""):>9,} dòng')

# zip ép sang INTEGER: phải chắc không có zip nào mất số 0 đầu
check('zip không có số 0 đầu (ép INTEGER an toàn)',
      one(f"SELECT COUNT(*) FROM read_csv('{SILVER}/zip_area.csv', all_varchar=true) WHERE zip <> ltrim(zip, '0')"))

# ============================================================ 2. DDL (§7, FK có tên cột)
print('\n2. Tạo bảng theo DDL §7')
con.sql("""
CREATE TABLE dim_date (
    date_sk INTEGER PRIMARY KEY, full_date DATE NOT NULL UNIQUE,
    year SMALLINT NOT NULL, quarter SMALLINT NOT NULL, month SMALLINT NOT NULL, month_name VARCHAR(12) NOT NULL,
    day_of_month SMALLINT NOT NULL, day_of_week SMALLINT NOT NULL, day_of_year SMALLINT NOT NULL,
    is_weekend BOOLEAN NOT NULL, is_month_end BOOLEAN NOT NULL,
    is_urban_blowout BOOLEAN NOT NULL, is_forecast_period BOOLEAN NOT NULL);

CREATE TABLE dim_geography (
    geography_sk INTEGER PRIMARY KEY, zip INTEGER NOT NULL UNIQUE,
    city VARCHAR(64) NOT NULL, district VARCHAR(32) NOT NULL, region VARCHAR(16) NOT NULL);

CREATE TABLE dim_customer (
    customer_sk INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL UNIQUE,
    geography_sk INTEGER NOT NULL REFERENCES dim_geography(geography_sk),
    gender VARCHAR(16) NOT NULL, age_group VARCHAR(16) NOT NULL, acquisition_channel VARCHAR(32) NOT NULL,
    signup_date DATE, signup_date_valid BOOLEAN NOT NULL);

CREATE TABLE dim_product (
    product_sk INTEGER PRIMARY KEY, product_id INTEGER NOT NULL UNIQUE, product_name VARCHAR(64) NOT NULL,
    category VARCHAR(32) NOT NULL, segment VARCHAR(32) NOT NULL, size VARCHAR(4) NOT NULL, color VARCHAR(16) NOT NULL,
    current_price DOUBLE NOT NULL, current_cogs DOUBLE NOT NULL, price_anomaly BOOLEAN NOT NULL);

CREATE TABLE dim_promotion (
    promotion_sk INTEGER PRIMARY KEY, promo_id VARCHAR(16) NOT NULL UNIQUE, promo_name VARCHAR(64) NOT NULL,
    promo_type VARCHAR(16) NOT NULL, discount_value DECIMAL(10,2) NOT NULL,
    start_date DATE NOT NULL, end_date DATE NOT NULL, applicable_category VARCHAR(32),
    promo_channel VARCHAR(24) NOT NULL, stackable_flag BOOLEAN NOT NULL, min_order_value INTEGER NOT NULL);

CREATE TABLE dim_order_junk (
    order_junk_sk INTEGER PRIMARY KEY, order_status VARCHAR(16) NOT NULL, payment_method VARCHAR(24) NOT NULL,
    device_type VARCHAR(12) NOT NULL, order_source VARCHAR(24) NOT NULL,
    UNIQUE (order_status, payment_method, device_type, order_source));

CREATE TABLE fact_order_item (
    order_item_sk BIGINT PRIMARY KEY, order_id INTEGER NOT NULL, line_number SMALLINT NOT NULL,
    date_sk INTEGER NOT NULL REFERENCES dim_date(date_sk),
    customer_sk INTEGER NOT NULL REFERENCES dim_customer(customer_sk),
    product_sk INTEGER NOT NULL REFERENCES dim_product(product_sk),
    order_junk_sk INTEGER NOT NULL REFERENCES dim_order_junk(order_junk_sk),
    quantity SMALLINT NOT NULL, unit_price DECIMAL(14,4) NOT NULL,
    gross_amount DECIMAL(16,4) NOT NULL, discount_amount DECIMAL(16,4) NOT NULL,
    net_amount DECIMAL(16,4) NOT NULL, cogs_amount DOUBLE NOT NULL,
    UNIQUE (order_id, line_number));

CREATE TABLE fact_order (
    order_id INTEGER PRIMARY KEY,
    order_date_sk INTEGER NOT NULL REFERENCES dim_date(date_sk),
    ship_date_sk INTEGER REFERENCES dim_date(date_sk),
    delivery_date_sk INTEGER REFERENCES dim_date(date_sk),
    customer_sk INTEGER NOT NULL REFERENCES dim_customer(customer_sk),
    order_junk_sk INTEGER NOT NULL REFERENCES dim_order_junk(order_junk_sk),
    payment_value DECIMAL(16,4) NOT NULL, installments SMALLINT NOT NULL, shipping_fee DECIMAL(10,2),
    days_to_ship SMALLINT, days_to_deliver SMALLINT);

CREATE TABLE fact_daily_sales (
    date_sk INTEGER PRIMARY KEY REFERENCES dim_date(date_sk),
    revenue DECIMAL(18,2) NOT NULL, cogs DECIMAL(18,2) NOT NULL, is_actual BOOLEAN NOT NULL);

CREATE TABLE fact_inventory_snapshot (
    date_sk INTEGER NOT NULL REFERENCES dim_date(date_sk),
    product_sk INTEGER NOT NULL REFERENCES dim_product(product_sk),
    stock_on_hand INTEGER NOT NULL, units_received INTEGER NOT NULL, units_sold INTEGER NOT NULL,
    stockout_days SMALLINT NOT NULL, days_of_supply DECIMAL(10,1) NOT NULL, fill_rate DECIMAL(6,4) NOT NULL,
    sell_through_rate DECIMAL(6,4) NOT NULL, stockout_flag BOOLEAN NOT NULL, overstock_flag BOOLEAN NOT NULL,
    PRIMARY KEY (date_sk, product_sk));

CREATE TABLE fact_return (
    return_id VARCHAR(16) PRIMARY KEY,
    order_item_sk BIGINT NOT NULL REFERENCES fact_order_item(order_item_sk),
    date_sk INTEGER NOT NULL REFERENCES dim_date(date_sk),
    return_reason VARCHAR(32) NOT NULL, return_quantity SMALLINT NOT NULL, refund_amount DECIMAL(16,2) NOT NULL);

CREATE TABLE fact_review (
    review_id VARCHAR(16) PRIMARY KEY,
    order_item_sk BIGINT NOT NULL REFERENCES fact_order_item(order_item_sk),
    date_sk INTEGER NOT NULL REFERENCES dim_date(date_sk),
    rating SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5));

CREATE TABLE bridge_item_promo (
    order_item_sk BIGINT NOT NULL REFERENCES fact_order_item(order_item_sk),
    promotion_sk INTEGER NOT NULL REFERENCES dim_promotion(promotion_sk),
    PRIMARY KEY (order_item_sk, promotion_sk));

CREATE TABLE fact_web_traffic (
    date_sk INTEGER PRIMARY KEY REFERENCES dim_date(date_sk),
    sessions INTEGER NOT NULL, unique_visitors INTEGER NOT NULL, page_views INTEGER NOT NULL,
    bounce_rate DECIMAL(8,5) NOT NULL, avg_session_duration_sec DECIMAL(8,1) NOT NULL,
    traffic_source VARCHAR(24) NOT NULL);
""")

# ============================================================ 3. Nạp (dim trước, fact sau — FK được DuckDB kiểm khi INSERT)
print('3. Nạp dữ liệu')
SK = lambda d: f"CAST(strftime({d}, '%Y%m%d') AS INTEGER)"  # date -> date_sk YYYYMMDD

con.sql(f"""
INSERT INTO dim_date
SELECT {SK('d')}, d, year(d), quarter(d), month(d), monthname(d), day(d),
       isodow(d) - 1,                                         -- 0 = thứ Hai
       dayofyear(d), isodow(d) >= 6, d = last_day(d),
       year(d) % 2 = 1 AND strftime(d, '%m-%d') BETWEEN '07-30' AND '09-02',   -- quy tắc lịch, phủ cả 2023
       d >= DATE '2023-01-01'
FROM (SELECT CAST(range AS DATE) AS d FROM range(DATE '2012-01-01', DATE '2024-07-02', INTERVAL 1 DAY))
""")

con.sql("""
INSERT INTO dim_geography
SELECT ROW_NUMBER() OVER (ORDER BY z.zip), z.zip, z.city, z.district, c.region
FROM stg.zip_area z JOIN stg.city c USING (city)
""")

# signup_date_valid: signup không sau đơn đầu tiên của khách (khách chưa có đơn: chỉ cần khác NULL)
con.sql("""
INSERT INTO dim_customer
SELECT ROW_NUMBER() OVER (ORDER BY c.customer_id), c.customer_id, g.geography_sk,
       c.gender, c.age_group, c.acquisition_channel, c.signup_date,
       c.signup_date IS NOT NULL AND (f.first_order IS NULL OR c.signup_date <= f.first_order)
FROM stg.customer c
JOIN dim_geography g USING (zip)
LEFT JOIN (SELECT customer_id, MIN(order_date) AS first_order FROM stg."order" GROUP BY 1) f USING (customer_id)
""")

con.sql("""
INSERT INTO dim_product
SELECT ROW_NUMBER() OVER (ORDER BY p.product_id), p.product_id, p.product_name, m.category, m.segment,
       p.size, p.color, p.list_price, p.unit_cogs, p.list_price < 100          -- ngưỡng 100, §6 mục 1
FROM stg.product p JOIN stg.product_model m USING (product_name)
""")

con.sql("""
INSERT INTO dim_promotion
SELECT ROW_NUMBER() OVER (ORDER BY promo_id), promo_id, promo_name, promo_type, discount_value,
       start_date, end_date, applicable_category, promo_channel, stackable_flag = 1, min_order_value
FROM stg.promotion
""")

# junk dim = tích Descartes đủ 540 tổ hợp (§5.5), không chỉ các tổ hợp đang có
con.sql("""
INSERT INTO dim_order_junk
SELECT ROW_NUMBER() OVER (ORDER BY s, pm, dt, os), s, pm, dt, os
FROM (SELECT DISTINCT order_status AS s FROM stg."order")
CROSS JOIN (SELECT DISTINCT payment_method AS pm FROM stg.payment)
CROSS JOIN (SELECT DISTINCT device_type AS dt FROM stg."order")
CROSS JOIN (SELECT DISTINCT order_source AS os FROM stg."order")
""")

# bảng tạm: mỗi đơn -> date_sk, customer_sk, order_junk_sk (dùng chung cho 2 fact)
con.sql(f"""
CREATE TEMP TABLE ord AS
SELECT o.order_id, o.order_date, {SK('o.order_date')} AS date_sk, c.customer_sk, j.order_junk_sk, p.installments
FROM stg."order" o
JOIN stg.payment p USING (order_id)
JOIN dim_customer c USING (customer_id)
JOIN dim_order_junk j ON j.order_status = o.order_status AND j.payment_method = p.payment_method
                     AND j.device_type = o.device_type AND j.order_source = o.order_source
""")

con.sql("""
INSERT INTO fact_order_item
SELECT ROW_NUMBER() OVER (ORDER BY i.order_id, i.line_number), i.order_id, i.line_number,
       o.date_sk, o.customer_sk, p.product_sk, o.order_junk_sk,
       i.quantity, i.unit_price,
       i.quantity * i.unit_price,
       i.discount_amount,
       i.quantity * i.unit_price - i.discount_amount,
       i.quantity * p.current_cogs
FROM stg.order_item i
JOIN ord o USING (order_id)
JOIN dim_product p USING (product_id)
""")

# days_to_ship = ship − order; days_to_deliver = delivery − ship (thời gian vận chuyển)
con.sql(f"""
INSERT INTO fact_order
SELECT o.order_id, o.date_sk,
       {SK('s.ship_date')}, {SK('s.delivery_date')},
       o.customer_sk, o.order_junk_sk,
       n.payment_value, o.installments, s.shipping_fee,
       date_diff('day', o.order_date, s.ship_date),
       date_diff('day', s.ship_date, s.delivery_date)
FROM ord o
JOIN (SELECT order_id, SUM(net_amount) AS payment_value FROM fact_order_item GROUP BY 1) n USING (order_id)
LEFT JOIN stg.shipment s USING (order_id)
""")

# aggregate fact: thực tế TÍNH từ fact_order_item (gross, mọi trạng thái đơn) + 548 dòng vùng dự báo
con.sql(f"""
INSERT INTO fact_daily_sales
SELECT date_sk, SUM(gross_amount), ROUND(SUM(cogs_amount), 2), TRUE FROM fact_order_item GROUP BY 1
UNION ALL
SELECT {SK('forecast_date')}, revenue, cogs, FALSE FROM stg.daily_sales_forecast
""")

# 5 cột dẫn xuất TÍNH lại theo công thức (§4, §7), không chép từ nguồn.
# Làm tròn như numpy (nguồn sinh bằng pandas): nhân 10^d rồi làm tròn về số chẵn -> 0,25625 thành 0,2562
RE = lambda x, d: f'round_even(({x}) * 1e{d}, 0) / 1e{d}'
DOS = RE('i.stock_on_hand / (i.units_sold / 30)', 1)
con.sql(f"""
INSERT INTO fact_inventory_snapshot
SELECT {SK('i.snapshot_date')}, p.product_sk,
       i.stock_on_hand, i.units_received, i.units_sold, i.stockout_days,
       {DOS},
       {RE('1 - i.stockout_days / 30', 4)},
       {RE('i.units_sold / (i.stock_on_hand + i.units_sold)', 4)},
       i.stockout_days > 0,
       {DOS} > 90
FROM stg.inventory_snapshot i JOIN dim_product p USING (product_id)
""")

con.sql(f"""
INSERT INTO fact_return
SELECT r.return_id, f.order_item_sk, {SK('r.return_date')}, r.return_reason, r.return_quantity, r.refund_amount
FROM stg.product_return r JOIN fact_order_item f USING (order_id, line_number)
""")

con.sql(f"""
INSERT INTO fact_review
SELECT r.review_id, f.order_item_sk, {SK('r.review_date')}, l.rating
FROM stg.review r
JOIN fact_order_item f USING (order_id, line_number)
JOIN stg.review_title_label l USING (review_title)
""")

con.sql("""
INSERT INTO bridge_item_promo
SELECT f.order_item_sk, d.promotion_sk
FROM stg.order_item_promotion b
JOIN fact_order_item f USING (order_id, line_number)
JOIN dim_promotion d USING (promo_id)
""")

con.sql(f"""
INSERT INTO fact_web_traffic
SELECT {SK('traffic_date')}, sessions, unique_visitors, page_views, bounce_rate, avg_session_duration_sec, traffic_source
FROM stg.web_traffic
""")

# ============================================================ 4. Quality gate
print('\n4. Quality gate')
ROWS = {'dim_date': 4_566, 'dim_geography': 39_948, 'dim_customer': 121_930, 'dim_product': 2_412,
        'dim_promotion': 50, 'dim_order_junk': 540, 'fact_order_item': 714_669, 'fact_order': 646_945,
        'fact_daily_sales': 4_381, 'fact_inventory_snapshot': 60_247, 'fact_return': 39_939,
        'fact_review': 113_551, 'bridge_item_promo': 276_522, 'fact_web_traffic': 3_652}
for t, n in ROWS.items():
    check(f'row count {t} == {n:,}', one(f'SELECT COUNT(*) FROM {t}') != n)

# Mỗi dòng silver phải sang đúng 1 dòng gold (JOIN trong bước 3 không được làm rơi dòng)
for gold, stg in [('fact_order_item', 'order_item'), ('fact_return', 'product_return'), ('fact_review', 'review'),
                  ('bridge_item_promo', 'order_item_promotion'), ('fact_inventory_snapshot', 'inventory_snapshot'),
                  ('fact_order', '"order"'), ('dim_customer', 'customer'), ('dim_geography', 'zip_area')]:
    check(f'{gold} giữ đủ dòng của stg.{stg.strip(chr(34))}',
          one(f'SELECT COUNT(*) FROM stg.{stg}') - one(f'SELECT COUNT(*) FROM {gold}'))

# FK: DuckDB đã chặn khi INSERT; đếm lại tường minh để có bằng chứng in ra (theo quan hệ trong docs/design/star_schema.mmd)
FK = [('dim_customer', 'geography_sk', 'dim_geography', 'geography_sk'),
      ('fact_order_item', 'date_sk', 'dim_date', 'date_sk'),
      ('fact_order_item', 'customer_sk', 'dim_customer', 'customer_sk'),
      ('fact_order_item', 'product_sk', 'dim_product', 'product_sk'),
      ('fact_order_item', 'order_junk_sk', 'dim_order_junk', 'order_junk_sk'),
      ('bridge_item_promo', 'order_item_sk', 'fact_order_item', 'order_item_sk'),
      ('bridge_item_promo', 'promotion_sk', 'dim_promotion', 'promotion_sk'),
      ('fact_order', 'order_date_sk', 'dim_date', 'date_sk'),
      ('fact_order', 'ship_date_sk', 'dim_date', 'date_sk'),
      ('fact_order', 'delivery_date_sk', 'dim_date', 'date_sk'),
      ('fact_order', 'customer_sk', 'dim_customer', 'customer_sk'),
      ('fact_order', 'order_junk_sk', 'dim_order_junk', 'order_junk_sk'),
      ('fact_return', 'order_item_sk', 'fact_order_item', 'order_item_sk'),
      ('fact_return', 'date_sk', 'dim_date', 'date_sk'),
      ('fact_review', 'order_item_sk', 'fact_order_item', 'order_item_sk'),
      ('fact_review', 'date_sk', 'dim_date', 'date_sk'),
      ('fact_daily_sales', 'date_sk', 'dim_date', 'date_sk'),
      ('fact_inventory_snapshot', 'date_sk', 'dim_date', 'date_sk'),
      ('fact_inventory_snapshot', 'product_sk', 'dim_product', 'product_sk'),
      ('fact_web_traffic', 'date_sk', 'dim_date', 'date_sk')]
for c, cc, p, pc in FK:
    check(f'FK {c}.{cc} -> {p}',
          one(f'SELECT COUNT(*) FROM {c} x WHERE x.{cc} IS NOT NULL AND x.{cc} NOT IN (SELECT {pc} FROM {p})'),
          one(f'SELECT COUNT(*) FROM {c}'))

check('dim_order_junk: cả 540 tổ hợp đều có đơn dùng',
      one('SELECT COUNT(*) FROM dim_order_junk WHERE order_junk_sk NOT IN (SELECT order_junk_sk FROM fact_order)'))
check('ship_date_sk NULL <=> không có shipment',
      one('SELECT COUNT(*) FROM fact_order WHERE (ship_date_sk IS NULL) <> (order_id NOT IN (SELECT order_id FROM stg.shipment))'))
check('is_urban_blowout (quy tắc lịch) == ngày thuộc promo Urban Blowout, 2012–2022',
      one("""SELECT COUNT(*) FROM dim_date d WHERE d.full_date <= DATE '2022-12-31' AND d.is_urban_blowout <>
             EXISTS (SELECT 1 FROM dim_promotion p WHERE p.promo_name LIKE 'Urban Blowout%'
                     AND d.full_date BETWEEN p.start_date AND p.end_date)"""))
check('Σ measure fact_order_item == stg (quantity, gross, discount)',
      one("""SELECT (SELECT SUM(quantity) FROM fact_order_item) <> (SELECT SUM(quantity) FROM stg.order_item)
               OR (SELECT SUM(gross_amount) FROM fact_order_item) <> (SELECT SUM(quantity * unit_price) FROM stg.order_item)
               OR (SELECT SUM(discount_amount) FROM fact_order_item) <> (SELECT SUM(discount_amount) FROM stg.order_item)"""))

# Điểm 1 §5 CLAUDE.md: sales.csv tái tạo CHÍNH XÁC từ giao dịch — kho phải giữ được tính chất này
sales = f"read_csv('{DATA}/sales.csv', header=true, types={{'Revenue': 'DECIMAL(18,2)', 'COGS': 'DECIMAL(18,2)'}})"
check('fact_daily_sales thực tế phủ đúng 3.833 ngày của sales.csv',
      one(f"""SELECT COUNT(*) FROM (SELECT date_sk FROM fact_daily_sales WHERE is_actual) a
              FULL JOIN (SELECT {SK('Date')} AS date_sk FROM {sales}) s USING (date_sk)
              WHERE a.date_sk IS NULL OR s.date_sk IS NULL"""))
check('fact_daily_sales Revenue/COGS == sales.csv (khớp tuyệt đối, 2 chữ số)',
      one(f"""SELECT COUNT(*) FROM fact_daily_sales f JOIN {sales} s ON f.date_sk = {SK('s.Date')}
              WHERE f.revenue <> s.Revenue OR f.cogs <> s.COGS"""), 3_833)
check('fact_order.payment_value == Σ net_amount (định nghĩa net, §5.2)',
      one("""SELECT COUNT(*) FROM fact_order o JOIN (SELECT order_id, SUM(net_amount) n FROM fact_order_item GROUP BY 1) i
             USING (order_id) WHERE o.payment_value <> i.n"""))
check('5 cột dẫn xuất tồn kho (tính lại) == data/inventory.csv',
      one(f"""SELECT COUNT(*) FROM fact_inventory_snapshot f
              JOIN dim_product p USING (product_sk)
              JOIN read_csv('{DATA}/inventory.csv', header=true) s
                ON f.date_sk = {SK('s.snapshot_date')} AND p.product_id = s.product_id
              WHERE abs(f.days_of_supply - s.days_of_supply) > 1e-9 OR abs(f.fill_rate - s.fill_rate) > 1e-9
                 OR abs(f.sell_through_rate - s.sell_through_rate) > 1e-9
                 OR f.stockout_flag <> (s.stockout_flag = 1) OR f.overstock_flag <> (s.overstock_flag = 1)"""), 60_247)
check('fact_return.return_quantity <= quantity dòng hàng',
      one('SELECT COUNT(*) FROM fact_return r JOIN fact_order_item f USING (order_item_sk) WHERE r.return_quantity > f.quantity'))
check('days_to_ship, days_to_deliver >= 0',
      one('SELECT COUNT(*) FROM fact_order WHERE days_to_ship < 0 OR days_to_deliver < 0'))

con.sql('DETACH stg')

failed = [n for n, v in results if v]
if failed:
    con.close()
    print(f'\n{len(failed)} check FAIL — dừng, giữ nguyên {OUT} cũ (nếu có).')
    sys.exit(1)

# ============================================================ 5. Thay file kho
con.sql('CHECKPOINT')
con.close()
os.replace(TMP, OUT)
print(f'\n5. Ghi {OUT}  ({len(results)} check đều PASS, {os.path.getsize(OUT) / 1e6:.1f} MB)')
con = duckdb.connect(OUT, read_only=True)
for t in ROWS:
    print(f'  {t:26s} {one(f"SELECT COUNT(*) FROM {t}"):>9,} dòng')
