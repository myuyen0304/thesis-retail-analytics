select
    cast({{ clean('snapshot_date') }} as date) as snapshot_date,
    cast({{ clean('product_id') }} as integer) as product_id,
    cast({{ clean('stock_on_hand') }} as integer) as stock_on_hand,
    cast({{ clean('units_received') }} as integer) as units_received,
    cast({{ clean('units_sold') }} as integer) as units_sold,
    cast({{ clean('stockout_days') }} as integer) as stockout_days,
    cast({{ clean('days_of_supply') }} as {{ type_double() }}) as days_of_supply,        -- dẫn xuất: chỉ giữ ở staging để ĐỐI SOÁT, marts tính lại
    cast({{ clean('fill_rate') }} as {{ type_double() }}) as fill_rate,
    cast({{ clean('sell_through_rate') }} as {{ type_double() }}) as sell_through_rate,
    cast({{ clean('stockout_flag') }} as integer) as stockout_flag,
    cast({{ clean('overstock_flag') }} as integer) as overstock_flag,
    cast({{ clean('reorder_flag') }} as integer) as reorder_flag,                        -- hằng số, loại ở marts
    {{ clean('product_name') }} as product_name,                                         -- trùng products, loại ở marts
    {{ clean('category') }} as category,
    {{ clean('segment') }} as segment,
    cast({{ clean('year') }} as integer) as snapshot_year,
    cast({{ clean('month') }} as integer) as snapshot_month
from {{ source('raw', 'inventory') }}
