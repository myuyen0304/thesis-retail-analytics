select
    cast({{ clean('order_id') }} as integer) as order_id,
    cast({{ clean('ship_date') }} as date) as ship_date,
    cast({{ clean('delivery_date') }} as date) as delivery_date,
    cast({{ clean('shipping_fee') }} as decimal(10, 2)) as shipping_fee
from {{ source('raw', 'shipments') }}
