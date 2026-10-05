-- Transaction fact, trỏ vào DÒNG HÀNG (không phải đơn).
select
    r.return_id,
    f.order_item_sk,
    {{ date_sk('r.return_date') }} as date_sk,
    r.return_reason,
    r.return_quantity,
    r.refund_amount
from {{ ref('int_returns') }} r
join {{ ref('fact_order_item') }} f on f.order_id = r.order_id and f.line_number = r.line_number
