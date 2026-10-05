select * from (
-- Chỉ bỏ một cột nguồn sau khi chứng minh nó là bản sao / hằng số (star_schema.md §8).
select 'customers.city == geography.city qua zip' as reason, count(*) as n
from {{ ref('stg_customers') }} c join {{ ref('stg_geography') }} g on g.zip = c.zip
where c.city <> g.city
union all
select 'orders.zip == customers.zip', count(*)
from {{ ref('stg_orders') }} o join {{ ref('stg_customers') }} c on c.customer_id = o.customer_id
where o.zip <> c.zip
union all
select 'orders.payment_method == payments.payment_method', count(*)
from {{ ref('stg_orders') }} o join {{ ref('stg_payments') }} p on p.order_id = o.order_id
where o.payment_method <> p.payment_method
union all
select 'reviews.customer_id == orders.customer_id', count(*)
from {{ ref('stg_reviews') }} r join {{ ref('stg_orders') }} o on o.order_id = r.order_id
where r.customer_id <> o.customer_id
union all
select 'inventory.product_name/category/segment == products', count(*)
from {{ ref('stg_inventory') }} i join {{ ref('stg_products') }} p on p.product_id = i.product_id
where i.product_name <> p.product_name or i.category <> p.category or i.segment <> p.segment
union all
select 'inventory.reorder_flag là hằng 0', count(*)
from {{ ref('stg_inventory') }} where reorder_flag <> 0
union all
select 'inventory.year/month == tách từ snapshot_date', count(*)
from {{ ref('stg_inventory') }}
where snapshot_year <> extract(year from snapshot_date) or snapshot_month <> extract(month from snapshot_date)
) checks
where n > 0
