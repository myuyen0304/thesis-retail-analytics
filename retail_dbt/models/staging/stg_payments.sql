select
    cast({{ clean('order_id') }} as integer) as order_id,
    {{ clean('payment_method') }} as payment_method,
    cast({{ clean('payment_value') }} as {{ type_double() }}) as payment_value,  -- dẫn xuất = Σ net, chỉ dùng đối soát
    cast({{ clean('installments') }} as integer) as installments
from {{ source('raw', 'payments') }}
