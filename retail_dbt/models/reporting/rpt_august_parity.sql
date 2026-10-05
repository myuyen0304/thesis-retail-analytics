{{ config(materialized='view') }}
-- PS3 KPI "Chênh tháng 8 năm lẻ / năm chẵn" = TB chỉ số tháng 8 năm lẻ ÷ TB năm chẵn − 1 (2013–2022).
-- Năm lẻ có Urban Blowout (CLAUDE.md §5 điểm 6); 08/2023 nằm trong vùng dự báo.
-- Deck slide 8, yêu cầu 4–5: "năm nào cũng vậy không", "không bị vài năm bất thường kéo lệch":
--   max_index_odd < min_index_even  → mọi năm lẻ đều thấp hơn mọi năm chẵn;
--   loo_min / loo_max               → chênh lệch khi bỏ lần lượt từng năm (10 lần), khoảng dao động.
with a as (
    select year, is_odd_year, month_index
    from {{ ref('rpt_revenue_monthly') }}
    where month = 8 and is_analysis_period
),
loo as (      -- bỏ năm d.year, tính lại chênh lẻ/chẵn trên 9 năm còn lại
    select d.year as dropped_year,
           avg(case when a.is_odd_year then a.month_index end)
             / avg(case when not a.is_odd_year then a.month_index end) - 1 as odd_vs_even
    from a d
    join a on a.year <> d.year
    group by d.year
)
select
    count(case when is_odd_year then 1 end)                          as n_odd_years,
    count(case when not is_odd_year then 1 end)                      as n_even_years,
    avg(case when is_odd_year then month_index end)                  as august_index_odd,
    avg(case when not is_odd_year then month_index end)              as august_index_even,
    avg(case when is_odd_year then month_index end)
      / avg(case when not is_odd_year then month_index end) - 1      as august_odd_vs_even,
    max(case when is_odd_year then month_index end)                  as max_index_odd,
    min(case when not is_odd_year then month_index end)              as min_index_even,
    (select min(odd_vs_even) from loo)                               as loo_min_odd_vs_even,
    (select max(odd_vs_even) from loo)                               as loo_max_odd_vs_even
from a
