{{ config(materialized='view') }}
-- PS3 KPI "Chênh tháng 8 năm lẻ / năm chẵn" = TB chỉ số tháng 8 năm lẻ ÷ TB năm chẵn − 1 (2013–2022).
-- Năm lẻ có Urban Blowout (CLAUDE.md §5 điểm 6); 08/2023 nằm trong vùng dự báo.
select
    count(case when is_odd_year then 1 end)                          as n_odd_years,
    count(case when not is_odd_year then 1 end)                      as n_even_years,
    avg(case when is_odd_year then month_index end)                  as august_index_odd,
    avg(case when not is_odd_year then month_index end)              as august_index_even,
    avg(case when is_odd_year then month_index end)
      / avg(case when not is_odd_year then month_index end) - 1      as august_odd_vs_even
from {{ ref('rpt_revenue_monthly') }}
where month = 8 and is_analysis_period
