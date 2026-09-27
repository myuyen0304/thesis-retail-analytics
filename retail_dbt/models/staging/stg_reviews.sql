select
    {{ clean('review_id') }} as review_id,
    cast({{ clean('order_id') }} as integer) as order_id,
    cast({{ clean('product_id') }} as integer) as product_id,
    cast({{ clean('customer_id') }} as integer) as customer_id,  -- suy được từ order_id, loại ở marts
    cast({{ clean('review_date') }} as date) as review_date,
    cast({{ clean('rating') }} as integer) as rating,
    {{ clean('review_title') }} as review_title,
    cast(_src_row as bigint) as src_row
from {{ source('raw', 'reviews') }}
