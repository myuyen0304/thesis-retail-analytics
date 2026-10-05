-- Đơn hàng + 2 bảng quan hệ 1:1 / 1:0..1 được hấp thụ (star_schema.md §3):
-- payments -> chỉ installments là thông tin mới (§5.2); shipments -> ngày gửi/giao + phí ship.
select
    o.order_id,
    o.order_date,
    o.customer_id,
    o.order_status,
    o.payment_method,
    o.device_type,
    o.order_source,
    p.installments,
    s.ship_date,
    s.delivery_date,
    s.shipping_fee
from {{ ref('stg_orders') }} o
join {{ ref('stg_payments') }} p on p.order_id = o.order_id
left join {{ ref('stg_shipments') }} s on s.order_id = o.order_id
