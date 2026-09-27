select
    cast(row_number() over (order by promo_id) as integer) as promotion_sk,
    promo_id,
    promo_name,
    promo_type,
    discount_value,
    start_date,
    end_date,
    applicable_category,   -- NULL = mọi category
    promo_channel,
    stackable_flag,
    min_order_value
from {{ ref('stg_promotions') }}
