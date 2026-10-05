-- Không có file nguồn: sinh dải ngày 2012-01-01 -> 2024-07-01 (4.566 dòng, phủ cả vùng dự báo).
-- Chỉ dùng extract(...) và dbt.dateadd để chạy được trên DuckDB, PostgreSQL và Snowflake.
with days as (
    select cast({{ dbt.dateadd('day', 'i', "cast('2012-01-01' as date)") }} as date) as full_date
    from ({{ integers(4566) }}) n
),
p as (
    select
        full_date,
        cast(extract(year from full_date) as integer)  as y,
        cast(extract(month from full_date) as integer) as m,
        cast(extract(day from full_date) as integer)   as d,
        cast(extract(day from cast({{ dbt.dateadd('day', 1, 'full_date') }} as date)) as integer) as d_next,
        cast({{ dbt.date_trunc('month', 'full_date') }} as date) as month_start
    from days
)
select
    {{ date_sk('full_date') }}                          as date_sk,
    full_date,
    cast(y as smallint)                                 as year,
    cast(extract(quarter from full_date) as smallint)   as quarter,
    cast(m as smallint)                                 as month,
    case m
        when 1 then 'January'  when 2 then 'February' when 3 then 'March'     when 4 then 'April'
        when 5 then 'May'      when 6 then 'June'     when 7 then 'July'      when 8 then 'August'
        when 9 then 'September' when 10 then 'October' when 11 then 'November' else 'December'
    end                                                 as month_name,
    cast(d as smallint)                                 as day_of_month,
    cast({{ dow_monday0('full_date') }} as smallint)    as day_of_week,    -- 0 = thứ Hai
    cast(extract(doy from full_date) as smallint)       as day_of_year,
    {{ dow_monday0('full_date') }} >= 5                 as is_weekend,
    d_next = 1                                          as is_month_end,   -- ngày mai là mùng 1
    month_start                                         as month_start_date,
    -- D của PS3: theo lịch (ngày cuối tháng), không đếm ngày có đơn
    cast(extract(day from cast({{ dbt.dateadd('day', -1, "cast(" ~ dbt.dateadd('month', 1, 'month_start') ~ " as date)") }} as date)) as smallint)
                                                        as days_in_month,
    -- cờ nghiệp vụ rút ra từ EDA (CLAUDE.md §5 điểm 6): Urban Blowout năm lẻ, 30/07–02/09.
    -- Quy tắc LỊCH (không tra dim_promotion) để phủ được cả 2023 trong vùng dự báo.
    mod(y, 2) = 1 and ((m = 7 and d >= 30) or m = 8 or (m = 9 and d <= 2))
                                                        as is_urban_blowout,
    full_date >= cast('2023-01-01' as date)             as is_forecast_period
from p
