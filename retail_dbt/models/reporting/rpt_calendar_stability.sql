-- PS3 (deck slide 8 yêu cầu 5: "kết quả không bị vài năm bất thường kéo lệch"). 1 dòng = 1 nhịp lịch, kỳ 2013–2022.
-- Hai kiểm tra cho MỖI nhịp:
--   loo_min / loo_max        chỉ số tính lại 10 lần, mỗi lần bỏ một năm → khoảng dao động (một năm bất thường kéo được bao nhiêu);
--   n_years_with_pattern     số năm TỰ có nhịp đó khi xét riêng từng năm. Nhịp có ở hầu hết các năm thì không thể do vài năm tạo ra.
-- Nhịp 1 (mua_vu):     chênh mùa cao/thấp trên chỉ số tháng gộp 2013–2022 = R tháng cao nhất ÷ thấp nhất (cộng các năm);
--                      năm có nhịp = tháng cao nhất thuộc T4–T6 VÀ tháng thấp nhất thuộc T12–T1 (deck slide 8).
-- Nhịp 2 (cuoi_thang): mức dồn cuối tháng 2013–2022 (như rpt_revenue_total); năm có nhịp = eom_excess của năm > 0.
-- Nhịp 3 (thang_8):    chênh tháng 8 năm lẻ / năm chẵn (rpt_august_parity); năm có nhịp = năm lẻ thấp hơn mọi năm chẵn,
--                      năm chẵn cao hơn mọi năm lẻ.
-- Tỷ số qua ratio() (DOUBLE): chia thẳng hai DECIMAL thì Databricks cắt còn 6 chữ số thập phân (3,394248).
with mo as (
    select * from {{ ref('rpt_revenue_monthly') }} where is_analysis_period
),
yrs as (
    select distinct year from mo
),
-- nhịp 1
pooled as (
    select month, sum(r) as r from mo group by month
),
loo_pm as (
    select d.year as dropped_year, m.month, sum(m.r) as r
    from yrs d join mo m on m.year <> d.year
    group by d.year, m.month
),
loo_season as (
    select dropped_year, {{ ratio('max(r)', 'min(r)') }} as v from loo_pm group by dropped_year
),
year_rank as (
    select year, month,
           row_number() over (partition by year order by month_index desc) as rk_high,
           row_number() over (partition by year order by month_index)      as rk_low
    from mo
),
season_years as (
    select count(*) as k
    from (select year,
                 max(case when rk_high = 1 then month end) as peak_month,
                 max(case when rk_low = 1 then month end)  as trough_month
          from year_rank group by year) t
    where peak_month in (4, 5, 6) and trough_month in (12, 1)
),
-- nhịp 2
loo_eom as (
    select d.year as dropped_year,
           {{ ratio('sum(m.r_day26_plus)', 'sum(m.r)') }} - {{ ratio('sum(m.r * m.eom_expected_share)', 'sum(m.r)') }} as v
    from yrs d join mo m on m.year <> d.year
    group by d.year
),
-- nhịp 3
a8 as (
    select year, is_odd_year, month_index from mo where month = 8
),
aug_years as (
    select count(*) as k
    from a8
    where (is_odd_year and month_index < (select min(month_index) from a8 where not is_odd_year))
       or (not is_odd_year and month_index > (select max(month_index) from a8 where is_odd_year))
)
select 1 as rhythm_order, 'mua_vu' as rhythm_code,
       (select {{ ratio('max(r)', 'min(r)') }} from pooled)                          as metric_value,
       (select min(v) from loo_season) as loo_min, (select max(v) from loo_season)    as loo_max,
       (select k from season_years)                                                  as n_years_with_pattern,
       (select count(*) from yrs)                                                    as n_years
union all
select 2, 'cuoi_thang',
       (select {{ ratio('sum(r_day26_plus)', 'sum(r)') }} - {{ ratio('sum(r * eom_expected_share)', 'sum(r)') }} from mo),
       (select min(v) from loo_eom), (select max(v) from loo_eom),
       (select count(*) from {{ ref('rpt_revenue_yearly') }} where is_analysis_period and eom_excess > 0),
       (select count(*) from yrs)
union all
select 3, 'thang_8',
       ap.august_odd_vs_even, ap.loo_min_odd_vs_even, ap.loo_max_odd_vs_even,
       (select k from aug_years),
       (select count(*) from yrs)
from {{ ref('rpt_august_parity') }} ap
