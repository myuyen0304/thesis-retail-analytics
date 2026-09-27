select
    cast({{ clean('order_id') }} as integer) as order_id,
    cast({{ clean('product_id') }} as integer) as product_id,
    cast({{ clean('quantity') }} as integer) as quantity,
    cast({{ clean('unit_price') }} as decimal(14, 2)) as unit_price,
    cast({{ clean('discount_amount') }} as decimal(16, 2)) as discount_amount,
    {{ clean('promo_id') }} as promo_id,
    {{ clean('promo_id_2') }} as promo_id_2,                                    -- rỗng 99,97%, chuyển vào bridge
    cast(_src_row as bigint) as src_row                                         -- thứ tự dòng trong file nguồn
from {{ source('raw', 'order_items') }}
