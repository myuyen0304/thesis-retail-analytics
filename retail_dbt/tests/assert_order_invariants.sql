select * from (
-- Ràng buộc nghiệp vụ trên đơn/dòng hàng (DDL §7, normalized_schema.md §8).
select 'return_quantity > quantity' as rule, count(*) as n
from {{ ref('fact_return') }} r join {{ ref('fact_order_item') }} f on f.order_item_sk = r.order_item_sk
where r.return_quantity > f.quantity
union all
select 'days_to_ship/days_to_deliver âm', count(*)
from {{ ref('fact_order') }} where days_to_ship < 0 or days_to_deliver < 0
union all
select 'ship_date_sk NULL nhưng có shipment (hoặc ngược lại)', count(*)
from {{ ref('fact_order') }} o
left join {{ ref('stg_shipments') }} s on s.order_id = o.order_id   -- LEFT JOIN: subquery trong biểu thức chạy lồng từng dòng trên Postgres
where (o.ship_date_sk is null) <> (s.order_id is null)
union all
select 'quantity <= 0 hoặc discount < 0', count(*)
from {{ ref('fact_order_item') }} where quantity <= 0 or discount_amount < 0
) checks
where n > 0
