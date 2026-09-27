select
    cast({{ clean('"Date"') }} as date) as sales_date,
    cast({{ clean('"Revenue"') }} as decimal(18, 2)) as revenue,  -- gross, KHÔNG trừ discount
    cast({{ clean('"COGS"') }} as decimal(18, 2)) as cogs         -- đã làm tròn 2 chữ số
from {{ source('raw', 'sales') }}
