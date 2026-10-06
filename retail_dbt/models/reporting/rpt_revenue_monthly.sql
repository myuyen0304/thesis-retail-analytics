-- PS1 + PS2 + PS3 theo THÁNG (grain = month_start_date, 07/2012 → 12/2022, 126 tháng liên tục).
-- Lịch sử không thiếu ngày nào (CLAUDE.md §1) nên tháng nào cũng có đơn; test assert_rpt_calendar kiểm tra.
with m as (
    select
        month_start_date,
        min(year)                                                        as year,
        min(month)                                                       as month,
        min(days_in_month)                                               as days_in_month,
        {{ revenue_measures() }},
        sum(case when is_delivered and day_of_month >= 26 then net_amount else 0 end) as r_day26_plus
    from {{ ref('int_reporting_order_items') }}
    group by month_start_date
),
w as (
    select
        m.*,
        lag(r, 12) over (order by month_start_date)                                         as r_same_month_prior_year,
        sum(r) over (order by month_start_date rows between 11 preceding and current row)   as r_12m_raw,
        avg(r) over (partition by year)                                                     as r_year_monthly_avg
    from m
)
select
    month_start_date,
    year,
    month,
    days_in_month,
    year between 2013 and 2022                                  as is_analysis_period,   -- 2012 chỉ có nửa năm
    mod(year, 2) = 1                                            as is_odd_year,
    g, r, cancelled_gross, returned_gross, undelivered_gross, delivered_discount,
    n, q, c,
    {{ revenue_ratios() }},
    -- PS2: tăng trưởng cùng kỳ. 07/2012 thiếu 3 ngày đầu nên YoY bắt đầu từ 08/2013.
    case when month_start_date >= cast('2013-08-01' as date) then r_same_month_prior_year end
                                                                as r_same_month_prior_year,
    case when month_start_date >= cast('2013-08-01' as date)
         then {{ ratio('r', 'r_same_month_prior_year') }} - 1 end as yoy_rate,
    -- 12 tháng đủ đầu tiên là 08/2012 → 07/2013 (07/2012 bắt đầu từ ngày 04)
    case when month_start_date >= cast('2013-07-01' as date) then r_12m_raw end as r_12m,
    -- PS3: chỉ số tháng = R tháng / TB 12 tháng cùng năm (chỉ năm đủ 12 tháng)
    case when year >= 2013 then {{ ratio('r', 'r_year_monthly_avg') }} end      as month_index,
    r_day26_plus,
    {{ ratio('r_day26_plus', 'r') }}                            as eom_share,            -- tỷ trọng R ngày >= 26
    {{ ratio('days_in_month - 25', 'days_in_month') }}          as eom_expected_share,   -- (D − 25)/D nếu rải đều
    {{ ratio('r_day26_plus', 'r') }} - {{ ratio('days_in_month - 25', 'days_in_month') }}
                                                                as eom_excess            -- > 0: dồn về cuối tháng
from w
