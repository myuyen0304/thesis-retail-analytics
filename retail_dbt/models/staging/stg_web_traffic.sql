select
    cast({{ clean('"date"') }} as date) as traffic_date,
    cast({{ clean('sessions') }} as integer) as sessions,
    cast({{ clean('unique_visitors') }} as integer) as unique_visitors,
    cast({{ clean('page_views') }} as integer) as page_views,
    cast({{ clean('bounce_rate') }} as decimal(8, 5)) as bounce_rate,                            -- ≈0,005, phi thực tế
    cast({{ clean('avg_session_duration_sec') }} as decimal(8, 1)) as avg_session_duration_sec,
    {{ clean('traffic_source') }} as traffic_source                                              -- 1 nhãn/ngày
from {{ source('raw', 'web_traffic') }}
