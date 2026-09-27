select * from (
-- Các con số / khẳng định ghi trong deck docs/presentations/revenue_performance_problem_statement_updated.pptx.
-- Deck đổi số thì sửa test này cùng lúc.
select 'slide 4: G = 16.430.476.585,53; R = 12.518.175.957,20 (2012-2022)' as rule, count(*) as n
from (select sum(g) as g, sum(r) as r from {{ ref('rpt_revenue_yearly') }}) t
where abs(g - 16430476585.53) > 0.01 or abs(r - 12518175957.20) > 0.01
union all
select 'slide 4/5: R/G = 76,2%', count(*)
from (select sum(r) / sum(g) as rg from {{ ref('rpt_revenue_yearly') }}) t
where rg < 0.7615 or rg >= 0.7625
union all
select 'slide 3/15: tien hoan (returns) chi roi vao don returned', count(*)
from {{ ref('fact_return') }} r
join {{ ref('fact_order_item') }} f on f.order_item_sk = r.order_item_sk
join {{ ref('dim_order_junk') }} j on j.order_junk_sk = f.order_junk_sk
where j.order_status <> 'returned'
union all
select 'slide 6: doanh thu roi manh cuoi 2018 (R 2019 so 2018 < -30%)', count(*)
from {{ ref('rpt_revenue_yearly') }}
where year = 2019 and yoy_rate > -0.30
union all
select 'slide 8/9: thang 8 nam le thap hon nam chan ~37% (5 le, 5 chan)', count(*)
from {{ ref('rpt_august_parity') }}
where n_odd_years <> 5 or n_even_years <> 5 or august_odd_vs_even > -0.35 or august_odd_vs_even < -0.40
union all
select 'slide 8: doanh thu don ve cuoi thang (eom_excess > 0 toan ky 2013-2022)', count(*)
from (select sum(r_day26_plus) / sum(r) as share,
             sum(r * eom_expected_share) / sum(r) as expected
      from {{ ref('rpt_revenue_monthly') }} where is_analysis_period) t
where share <= expected
) checks
where n > 0
