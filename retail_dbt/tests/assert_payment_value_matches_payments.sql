-- §5.2: payments.payment_value == Σ(quantity × unit_price − discount) => bảng payments bỏ được.
select o.order_id, o.payment_value, p.payment_value as src_payment_value
from {{ ref('fact_order') }} o
join {{ ref('stg_payments') }} p on p.order_id = o.order_id
where abs(o.payment_value - p.payment_value) > 0.01
