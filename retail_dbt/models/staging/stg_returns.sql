select
    {{ clean('return_id') }} as return_id,
    cast({{ clean('order_id') }} as integer) as order_id,
    cast({{ clean('product_id') }} as integer) as product_id,
    cast({{ clean('return_date') }} as date) as return_date,
    {{ clean('return_reason') }} as return_reason,
    cast({{ clean('return_quantity') }} as integer) as return_quantity,
    cast({{ clean('refund_amount') }} as decimal(16, 2)) as refund_amount,
    cast(_src_row as bigint) as src_row
from {{ source('raw', 'returns') }}
