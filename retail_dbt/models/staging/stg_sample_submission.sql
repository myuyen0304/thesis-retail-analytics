select
    cast({{ clean(adapter.quote('Date')) }} as date) as sales_date,
    cast({{ clean(adapter.quote('Revenue')) }} as decimal(18, 2)) as revenue,
    cast({{ clean(adapter.quote('COGS')) }} as decimal(18, 2)) as cogs
from {{ source('raw', 'sample_submission') }}
