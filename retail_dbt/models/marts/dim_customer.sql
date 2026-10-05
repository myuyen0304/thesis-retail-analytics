-- SCD Type 1. Bỏ customers.city (bản sao geography.city — test assert_customers_city_is_copy).
with first_order as (
    select customer_id, min(order_date) as first_order_date
    from {{ ref('stg_orders') }}
    group by customer_id
)
select
    cast(row_number() over (order by c.customer_id) as integer) as customer_sk,
    c.customer_id,
    g.geography_sk,
    c.gender,
    c.age_group,
    c.acquisition_channel,
    c.signup_date,                                               -- KHÔNG đáng tin (§6 mục 2)
    -- hợp lệ = có ngày và không sau đơn đầu tiên (73,8% đơn phát sinh TRƯỚC signup)
    coalesce(c.signup_date is not null
             and (f.first_order_date is null or c.signup_date <= f.first_order_date), false)
                                                                 as signup_date_valid
from {{ ref('stg_customers') }} c
join {{ ref('dim_geography') }} g on g.zip = c.zip
left join first_order f on f.customer_id = c.customer_id
