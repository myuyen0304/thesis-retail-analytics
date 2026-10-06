-- Junk dimension = tích Descartes 4 thuộc tính cardinality thấp: 6 × 5 × 3 × 6 = 540 (§5.5).
-- Sinh đủ tích, không chỉ các tổ hợp đang có (test assert_order_junk_all_used: cả 540 đều có đơn).
with s  as (select distinct order_status   from {{ ref('stg_orders') }}),
     pm as (select distinct payment_method from {{ ref('stg_orders') }}),
     dt as (select distinct device_type    from {{ ref('stg_orders') }}),
     os as (select distinct order_source   from {{ ref('stg_orders') }})
select
    cast(row_number() over (order by order_status, payment_method, device_type, order_source) as integer)
        as order_junk_sk,
    order_status,
    payment_method,
    device_type,
    order_source
from s cross join pm cross join dt cross join os
