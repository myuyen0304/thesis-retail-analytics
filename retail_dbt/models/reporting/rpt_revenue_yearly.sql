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
eom as (      -- PS3 KPI "mức dồn về cuối tháng" của cả năm. Mức rải đều của năm = TB (D−25)/D các tháng, trọng số R tháng
    select year,
           sum(r_day26_plus)                                        as r_day26_plus,
           {{ ratio('sum(r * eom_expected_share)', 'sum(r)') }}     as eom_expected_share
    from {{ ref('rpt_revenue_monthly') }}
    group by year
),
ph as (       -- PS2/PS3: nhãn giai đoạn của năm (seed ps2_phases). Năm ranh giới thuộc cả hai giai đoạn (quy tắc 2) → 'A/B'
    select y.year, {{ listagg_ordered('p.phase_code', "'/'", 'p.start_year') }} as ps2_phase_codes
    from (select distinct year from {{ ref('int_reporting_order_items') }}) y
    join {{ ref('ps2_phases') }} p on y.year between p.start_year and p.end_year
    group by y.year
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
    ph.ps2_phase_codes,
    e.r_day26_plus,
    {{ ratio('e.r_day26_plus', 'r') }}                            as eom_share,
    e.eom_expected_share,
    {{ ratio('e.r_day26_plus', 'r') }} - e.eom_expected_share     as eom_excess,
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
left join eom e using (year)
left join ph using (year)
