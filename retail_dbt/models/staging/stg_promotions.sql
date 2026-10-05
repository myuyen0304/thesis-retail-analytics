select
    {{ clean('promo_id') }} as promo_id,
    {{ clean('promo_name') }} as promo_name,
    {{ clean('promo_type') }} as promo_type,
    cast({{ clean('discount_value') }} as decimal(10, 2)) as discount_value,
    cast({{ clean('start_date') }} as date) as start_date,
    cast({{ clean('end_date') }} as date) as end_date,
    {{ clean('applicable_category') }} as applicable_category,                -- NULL = mọi category
    {{ clean('promo_channel') }} as promo_channel,
    {{ clean('stackable_flag') }} = '1' as stackable_flag,                    -- nguồn 0/1
    cast({{ clean('min_order_value') }} as integer) as min_order_value
from {{ source('raw', 'promotions') }}
