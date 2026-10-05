-- PS2 KPI "Tăng trưởng TB năm (CAGR)" theo từng giai đoạn. 1 dòng = 1 giai đoạn do PM/BA chốt
-- (seed ps2_phases, 2026-09-27; quy tắc: docs/dwh_huong_dan_pm_ba.md §4 "PS2: 4 giai đoạn").
-- Mốc là năm đủ, R cả năm lấy từ rpt_revenue_yearly. Hai giai đoạn liền nhau dùng chung năm ranh giới.
-- CAGR = (R năm cuối / R năm đầu)^(1/n) − 1, n = năm cuối − năm đầu (deck slide 7).
-- band_start_date / band_end_date: tháng 12 của năm đầu / năm cuối. r_12m tại tháng 12 = R cả năm, nên trên đường r_12m
-- giai đoạn nằm đúng từ band_start_date tới band_end_date (app chỉ tô nền theo 2 cột này, không tự suy từ năm).
select
    p.phase_code,
    p.phase_name,
    p.trend,
    p.start_year,
    p.end_year,
    p.end_year - p.start_year                                      as n_years,
    s.r                                                            as r_start,
    e.r                                                            as r_end,
    e.r - s.r                                                      as delta_r,
    {{ ratio('e.r', 's.r') }} - 1                                  as total_change_rate,
    power({{ ratio('e.r', 's.r') }},
          {{ ratio(1, 'p.end_year - p.start_year') }}) - 1         as cagr,
    ms.month_start_date                                            as band_start_date,
    me.month_start_date                                            as band_end_date
from {{ ref('ps2_phases') }} p
join {{ ref('rpt_revenue_yearly') }} s on s.year = p.start_year
join {{ ref('rpt_revenue_yearly') }} e on e.year = p.end_year
join {{ ref('rpt_revenue_monthly') }} ms on ms.year = p.start_year and ms.month = 12
join {{ ref('rpt_revenue_monthly') }} me on me.year = p.end_year and me.month = 12
