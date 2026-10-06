-- Σ measure không đổi qua các tầng: staging -> fact_order_item.
select 'quantity' as measure
where (select sum(quantity) from {{ ref('fact_order_item') }}) <> (select sum(quantity) from {{ ref('stg_order_items') }})
union all
select 'gross_amount'
where (select sum(gross_amount) from {{ ref('fact_order_item') }})
   <> (select sum(quantity * unit_price) from {{ ref('stg_order_items') }})
union all
select 'discount_amount'
where (select sum(discount_amount) from {{ ref('fact_order_item') }}) <> (select sum(discount_amount) from {{ ref('stg_order_items') }})
union all
select 'refund_amount'
where (select sum(refund_amount) from {{ ref('fact_return') }}) <> (select sum(refund_amount) from {{ ref('stg_returns') }})
