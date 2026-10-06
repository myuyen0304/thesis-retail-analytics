-- Grain = 1 ngày, 2013-01-01 -> 2022-12-31. bounce_rate ≈0,005 phi thực tế — không xây metric trên đó.
select
    {{ date_sk('traffic_date') }} as date_sk,
    sessions,
    unique_visitors,
    page_views,
    bounce_rate,
    avg_session_duration_sec,
    traffic_source                -- 1 nhãn/ngày, KHÔNG phải phân rã
from {{ ref('stg_web_traffic') }}
