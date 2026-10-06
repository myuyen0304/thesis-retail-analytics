select * from (
-- Khóa tổ hợp (DDL §7) không trùng.
select 'fact_order_item(order_id, line_number)' as key_name, count(*) as n
from (select order_id, line_number from {{ ref('fact_order_item') }} group by 1, 2 having count(*) > 1) x
union all
select 'fact_inventory_snapshot(date_sk, product_sk)', count(*)
from (select date_sk, product_sk from {{ ref('fact_inventory_snapshot') }} group by 1, 2 having count(*) > 1) x
union all
select 'bridge_item_promo(order_item_sk, promotion_sk)', count(*)
from (select order_item_sk, promotion_sk from {{ ref('bridge_item_promo') }} group by 1, 2 having count(*) > 1) x
union all
select 'dim_order_junk(4 thuộc tính)', count(*)
from (select order_status, payment_method, device_type, order_source from {{ ref('dim_order_junk') }}
      group by 1, 2, 3, 4 having count(*) > 1) x
) checks
where n > 0
