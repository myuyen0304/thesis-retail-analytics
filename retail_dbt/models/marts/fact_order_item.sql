-- Transaction fact, grain = 1 dòng hàng (714.669). Surrogate key BẮT BUỘC (§5.1); order_id = degenerate dim.
with o as (
    select o.order_id, o.order_date, c.customer_sk, j.order_junk_sk
    from {{ ref('int_orders') }} o
    join {{ ref('dim_customer') }} c on c.customer_id = o.customer_id
    join {{ ref('dim_order_junk') }} j
      on  j.order_status = o.order_status and j.payment_method = o.payment_method
      and j.device_type = o.device_type   and j.order_source = o.order_source
)
select
    cast(row_number() over (order by l.order_id, l.line_number) as bigint) as order_item_sk,
    l.order_id,
    cast(l.line_number as smallint)                    as line_number,
    {{ date_sk('o.order_date') }}                      as date_sk,
    o.customer_sk,
    p.product_sk,
    o.order_junk_sk,
    l.quantity,
    l.unit_price,                                      -- giá TẠI THỜI ĐIỂM BÁN
    l.quantity * l.unit_price                          as gross_amount,
    l.discount_amount,
    l.quantity * l.unit_price - l.discount_amount      as net_amount,
    l.quantity * p.current_cogs                        as cogs_amount   -- DOUBLE: cogs nguồn là số thực
from {{ ref('int_order_lines') }} l
join o on o.order_id = l.order_id
join {{ ref('dim_product') }} p on p.product_id = l.product_id
