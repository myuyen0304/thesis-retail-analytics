-- Trả hàng trỏ vào DÒNG HÀNG: map (order_id, product_id, lần xuất hiện) -> line_number
with r as (
    select *,
           row_number() over (partition by order_id, product_id order by src_row) as product_occurrence
    from {{ ref('stg_returns') }}
)
select
    r.return_id,
    r.order_id,
    l.line_number,
    r.return_date,
    r.return_reason,
    r.return_quantity,
    r.refund_amount
from r
left join {{ ref('int_order_lines') }} l
    on l.order_id = r.order_id
   and l.product_id = r.product_id
   and l.product_occurrence = r.product_occurrence
