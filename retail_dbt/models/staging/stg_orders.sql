select
    cast({{ clean('order_id') }} as integer) as order_id,
    cast({{ clean('order_date') }} as date) as order_date,
    cast({{ clean('customer_id') }} as integer) as customer_id,
    cast({{ clean('zip') }} as integer) as zip,                  -- bản sao customers.zip, loại ở marts
    {{ clean('order_status') }} as order_status,
    {{ clean('payment_method') }} as payment_method,
    {{ clean('device_type') }} as device_type,
    {{ clean('order_source') }} as order_source
from {{ source('raw', 'orders') }}
