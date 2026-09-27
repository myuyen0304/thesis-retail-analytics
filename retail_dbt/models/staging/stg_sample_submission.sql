select
    cast({{ clean('"Date"') }} as date) as sales_date,
    cast({{ clean('"Revenue"') }} as decimal(18, 2)) as revenue,
    cast({{ clean('"COGS"') }} as decimal(18, 2)) as cogs
from {{ source('raw', 'sample_submission') }}
