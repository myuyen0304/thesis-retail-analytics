-- Accumulating snapshot, grain = 1 đơn (646.945). dim_date đóng 3 vai trò: đặt / gửi / giao.
with net as (
    select order_id, sum(net_amount) as payment_value
    from {{ ref('fact_order_item') }}
    group by order_id
)
select
    o.order_id,
    {{ date_sk('o.order_date') }}                                   as order_date_sk,
    {{ date_sk('o.ship_date') }}                                    as ship_date_sk,      -- NULL nếu chưa gửi
    {{ date_sk('o.delivery_date') }}                                as delivery_date_sk,
    c.customer_sk,
    j.order_junk_sk,
    n.payment_value,                                    -- = Σ net_amount; khớp payments.payment_value (test)
    o.installments,                                     -- thông tin DUY NHẤT mới từ payments (§5.2)
    o.shipping_fee,
    {{ dbt.datediff('o.order_date', 'o.ship_date', 'day') }}       as days_to_ship,      -- ship − order
    {{ dbt.datediff('o.ship_date', 'o.delivery_date', 'day') }}    as days_to_deliver    -- delivery − ship
from {{ ref('int_orders') }} o
join net n on n.order_id = o.order_id
join {{ ref('dim_customer') }} c on c.customer_id = o.customer_id
join {{ ref('dim_order_junk') }} j
  on  j.order_status = o.order_status and j.payment_method = o.payment_method
  and j.device_type = o.device_type   and j.order_source = o.order_source
