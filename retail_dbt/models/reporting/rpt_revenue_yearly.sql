-- PS1 + PS2 + PS4 + phần C/F của PS5 theo NĂM (2012 → 2022; phân tích chính 2013–2022, tăng trưởng từ 2014).
-- N, C đếm phân biệt lại ở grain năm (không cộng từ tháng).
with y as (
    select year, {{ revenue_measures() }}
    from {{ ref('int_reporting_order_items') }}
    group by year
),
b as (
    select
        y.*,
        {{ revenue_ratios() }}
    from y
),
season as (   -- PS3 KPI "chênh mùa cao / mùa thấp" = chỉ số tháng cao nhất ÷ thấp nhất trong năm
    select year, max(month_index) / nullif(min(month_index), 0) as season_peak_trough_ratio
    from {{ ref('rpt_revenue_monthly') }}
    group by year
),
l as (
    select
        b.*,
        lag(r) over (order by year) as r0, lag(n) over (order by year) as n0,
        lag(u) over (order by year) as u0, lag(p) over (order by year) as p0,
        lag(c) over (order by year) as c0, lag(f) over (order by year) as f0,
        lag(cancelled_rate) over (order by year) as cancelled_rate0
    from b
)
select
    year,
    year between 2013 and 2022                                    as is_analysis_period,
    g, r, cancelled_gross, returned_gross, undelivered_gross, delivered_discount,
    n, q, c, u, p, f, aov, capture_rate, cancelled_rate, discount_rate,
    -- 2013 không có năm trước đủ 12 tháng → tăng trưởng chính thức bắt đầu 2014
    case when year >= 2014 then r0 end                            as r_prior_year,
    case when year >= 2014 then {{ ratio('r', 'r0') }} - 1 end    as yoy_rate,
    case when year >= 2014 then cancelled_rate - cancelled_rate0 end as cancelled_rate_change,
    -- PS4 KPI "tăng trưởng N, U, P theo năm"
    case when year >= 2014 then {{ ratio('n', 'n0') }} - 1 end    as yoy_n,
    case when year >= 2014 then {{ ratio('u', 'u0') }} - 1 end    as yoy_u,
    case when year >= 2014 then {{ ratio('p', 'p0') }} - 1 end    as yoy_p,
    s.season_peak_trough_ratio,
    -- PS4: tách ΔR theo thứ tự N → U → P (phân rã số học, không phải nhân quả). Ba phần cộng = ΔR.
    case when year >= 2014 then r - r0 end                        as delta_r,
    case when year >= 2014 then (n - n0) * u0 * p0 end            as contrib_n,
    case when year >= 2014 then n * (u - u0) * p0 end             as contrib_u,
    case when year >= 2014 then n * u * (p - p0) end              as contrib_p,
    -- PS5: tách ΔN = phần do số khách C + phần do tần suất F. Hai phần cộng = ΔN.
    case when year >= 2014 then n - n0 end                        as delta_n,
    case when year >= 2014 then (c - c0) * f0 end                 as contrib_c,
    case when year >= 2014 then c * (f - f0) end                  as contrib_f
from l
left join season s using (year)
