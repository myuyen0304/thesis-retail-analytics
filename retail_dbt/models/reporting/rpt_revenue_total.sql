-- PS1 TOÀN KỲ: 1 dòng mỗi kỳ gộp nhiều năm. Deck slide 4 dùng 2012–2022 (G 16,43 tỷ, R 12,52 tỷ, R/G 76,2%);
-- kỳ phân tích chính là 2013–2022 (slide 3: 2012 chỉ có nửa năm).
-- N, C đếm phân biệt lại trên cả kỳ (không cộng từ năm): một khách mua nhiều năm chỉ tính 1 lần.
with periods as (
    select '2012-2022' as period_code, 2012 as start_year, 2022 as end_year, false as is_analysis_period
    union all
    select '2013-2022', 2013, 2022, true
),
t as (
    select
        p.period_code, p.start_year, p.end_year, p.is_analysis_period,
        min(i.order_date) as first_order_date,
        max(i.order_date) as last_order_date,
        {{ revenue_measures() }}
    from periods p
    join {{ ref('int_reporting_order_items') }} i on i.year between p.start_year and p.end_year
    group by p.period_code, p.start_year, p.end_year, p.is_analysis_period
),
eom as (      -- PS3 "mức dồn về cuối tháng" cả kỳ; mức rải đều = TB (D−25)/D các tháng, trọng số R tháng (như rpt_revenue_yearly)
    select p.period_code,
           sum(m.r_day26_plus)                                      as r_day26_plus,
           {{ ratio('sum(m.r * m.eom_expected_share)', 'sum(m.r)') }} as eom_expected_share
    from periods p
    join {{ ref('rpt_revenue_monthly') }} m on m.year between p.start_year and p.end_year
    group by p.period_code
)
select
    t.*,
    {{ revenue_ratios() }},
    e.r_day26_plus,
    {{ ratio('e.r_day26_plus', 't.r') }}                            as eom_share,
    e.eom_expected_share,
    {{ ratio('e.r_day26_plus', 't.r') }} - e.eom_expected_share     as eom_excess
from t
join eom e using (period_code)
