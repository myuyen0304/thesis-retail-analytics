{{ config(materialized='view') }}
-- Nền chung cho 5 PS: 1 dòng hàng (grain = fact_order_item), gắn sẵn lịch, trạng thái đơn và 3 chiều của PS5.
-- R = net_amount của dòng thuộc đơn delivered (deck slide 3). G = gross_amount của mọi dòng.
select
    f.order_item_sk,
    f.order_id,
    f.customer_sk,
    d.full_date                                   as order_date,
    d.year,
    d.month,
    d.month_start_date,
    d.day_of_month,
    d.days_in_month,
    j.order_status,
    j.order_status = 'delivered'                  as is_delivered,
    p.category,
    g.region,
    c.acquisition_channel,
    f.quantity,
    f.gross_amount,
    f.discount_amount,
    f.net_amount
from {{ ref('fact_order_item') }} f
join {{ ref('dim_date') }} d        on d.date_sk = f.date_sk
join {{ ref('dim_order_junk') }} j  on j.order_junk_sk = f.order_junk_sk
join {{ ref('dim_product') }} p     on p.product_sk = f.product_sk
join {{ ref('dim_customer') }} c    on c.customer_sk = f.customer_sk
join {{ ref('dim_geography') }} g   on g.geography_sk = c.geography_sk
