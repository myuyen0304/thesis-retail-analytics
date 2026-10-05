select * from (
-- PS2/PS3: lịch tháng liên tục, YoY cùng kỳ, R 12 tháng, chỉ số tháng, cuối tháng, D = số ngày trong tháng.
select '126 thang lien tuc 07/2012 -> 12/2022' as rule, count(*) as n
from (select count(*) as k, min(month_start_date) as lo, max(month_start_date) as hi
      from {{ ref('rpt_revenue_monthly') }}) m
where k <> 126 or lo <> cast('2012-07-01' as date) or hi <> cast('2022-12-01' as date)
union all
-- r_12m và YoY tính lại bằng self-join (độc lập với window function); NULL đúng chỗ, không NULL sai chỗ
select 'r_12m = tong 12 thang gan nhat (tu 07/2013), NULL truoc do', count(*)
from {{ ref('rpt_revenue_monthly') }} a
left join (
    select a.month_start_date, sum(b.r) as r12, count(*) as k
    from {{ ref('rpt_revenue_monthly') }} a
    join {{ ref('rpt_revenue_monthly') }} b
      on b.month_start_date <= a.month_start_date
     and b.month_start_date > cast({{ dbt.dateadd('month', -12, 'a.month_start_date') }} as date)
    group by a.month_start_date
) w on w.month_start_date = a.month_start_date
where (a.month_start_date >= cast('2013-07-01' as date) and (w.k <> 12 or {{ differs('a.r_12m', 'w.r12') }}))
   or (a.month_start_date < cast('2013-07-01' as date) and a.r_12m is not null)
union all
select 'yoy thang = R / R cung thang nam truoc - 1 (tu 08/2013), NULL truoc do', count(*)
from {{ ref('rpt_revenue_monthly') }} a
left join {{ ref('rpt_revenue_monthly') }} b
  on b.month_start_date = cast({{ dbt.dateadd('month', -12, 'a.month_start_date') }} as date)
where (a.month_start_date >= cast('2013-08-01' as date)
       and ({{ differs('a.r_same_month_prior_year', 'b.r') }} or {{ differs('a.yoy_rate', ratio('a.r', 'b.r') ~ ' - 1', 1e-12) }}))
   or (a.month_start_date < cast('2013-08-01' as date) and (a.yoy_rate is not null or a.r_same_month_prior_year is not null))
union all
select 'chi so thang: du 12 thang, khong NULL, tong = 12 moi nam 2013-2022; NULL nam 2012', count(*)
from (select year, sum(month_index) as s, count(month_index) as k from {{ ref('rpt_revenue_monthly') }}
      group by year) y
where (year between 2013 and 2022 and (k <> 12 or {{ differs('s', '12', 1e-9) }}))
   or (year = 2012 and k <> 0)
union all
select 'cuoi thang: eom_share = R ngay>=26 / R; ky vong = (D-25)/D', count(*)
from {{ ref('rpt_revenue_monthly') }}
where {{ differs('eom_share * r', 'r_day26_plus') }}
   or {{ differs('eom_expected_share * days_in_month', 'days_in_month - 25', 1e-9) }}
   or {{ differs('eom_excess', 'eom_share - eom_expected_share', 1e-12) }}
union all
-- D theo lịch = số dòng dim_date trong tháng (các tháng trọn vẹn trong dim_date)
select 'days_in_month = so ngay trong thang', count(*)
from (select month_start_date, max(days_in_month) as d, min(days_in_month) as d2, count(*) as k
      from {{ ref('dim_date') }} where full_date < cast('2024-07-01' as date)
      group by month_start_date) m
where d <> k or d2 <> k
union all
select 'thang 2 nam nhuan 2016 = 29 ngay, 2015 = 28', count(*)
from {{ ref('dim_date') }}
where (full_date = cast('2016-02-10' as date) and days_in_month <> 29)
   or (full_date = cast('2015-02-10' as date) and days_in_month <> 28)
union all
select 'eom nam: tinh doc lap tu dong hang (R ngay>=26 / R) va muc rai deu (D-25)/D trong so R thang', count(*)
from {{ ref('rpt_revenue_yearly') }} y
join (
    select year, sum(case when is_delivered and day_of_month >= 26 then net_amount else 0 end) as r26
    from {{ ref('int_reporting_order_items') }} group by year
) i on i.year = y.year
join (
    select year, sum(cast(r as {{ type_double() }}) * (days_in_month - 25) / days_in_month) / sum(cast(r as {{ type_double() }})) as expected
    from {{ ref('rpt_revenue_monthly') }} group by year
) m on m.year = y.year
where {{ differs('y.r_day26_plus', 'i.r26') }}
   or {{ differs('y.eom_share', ratio('i.r26', 'y.r'), 1e-12) }}
   or {{ differs('y.eom_expected_share', 'm.expected', 1e-12) }}
   or {{ differs('y.eom_excess', 'y.eom_share - y.eom_expected_share', 1e-12) }}
union all
select 'eom ky gop = cong cac nam; 2013-2022 duong (M3: eom_excess > 0)', count(*)
from {{ ref('rpt_revenue_total') }} t
join (select p.period_code, sum(y.r_day26_plus) as r26, sum(y.r * y.eom_expected_share) as rexp
      from {{ ref('rpt_revenue_total') }} p
      join {{ ref('rpt_revenue_yearly') }} y on y.year between p.start_year and p.end_year
      group by p.period_code) s on s.period_code = t.period_code
where {{ differs('t.r_day26_plus', 's.r26') }}
   or {{ differs('t.eom_expected_share', 's.rexp / t.r', 1e-12) }}
   or {{ differs('t.eom_excess', 't.eom_share - t.eom_expected_share', 1e-12) }}
   or (t.period_code = '2013-2022' and not (t.eom_excess > 0))
union all
select 'thang 8: -37,7% (M3); bo tung nam = cong thuc tong; moi nam le < moi nam chan', count(*)
from {{ ref('rpt_august_parity') }} ap
cross join (
    -- bỏ năm y: TB lẻ/chẵn tính lại bằng (tổng − chỉ số năm y) / (số năm − 1)
    select min(o / e - 1) as lo, max(o / e - 1) as hi
    from (
        select case when d.is_odd_year then (s.so - d.month_index) / (s.ko - 1) else s.so / s.ko end as o,
               case when d.is_odd_year then s.se / s.ke else (s.se - d.month_index) / (s.ke - 1) end as e
        from {{ ref('rpt_revenue_monthly') }} d
        cross join (
            select sum(case when is_odd_year then month_index else 0 end) as so,
                   sum(case when is_odd_year then 1 else 0 end)           as ko,
                   sum(case when is_odd_year then 0 else month_index end) as se,
                   sum(case when is_odd_year then 0 else 1 end)           as ke
            from {{ ref('rpt_revenue_monthly') }} where month = 8 and is_analysis_period
        ) s
        where d.month = 8 and d.is_analysis_period
    ) x
) chk
where not (ap.august_odd_vs_even between -0.37661 and -0.37660)
   or {{ differs('ap.loo_min_odd_vs_even', 'chk.lo', 1e-12) }}
   or {{ differs('ap.loo_max_odd_vs_even', 'chk.hi', 1e-12) }}
   or not (ap.loo_min_odd_vs_even <= ap.august_odd_vs_even and ap.august_odd_vs_even <= ap.loo_max_odd_vs_even)
   or not (ap.max_index_odd < ap.min_index_even)
union all
select 'season_peak_trough_ratio = max / min chi so thang (2013-2022)', count(*)
from {{ ref('rpt_revenue_yearly') }} y
join (select year, max(month_index) / min(month_index) as ratio from {{ ref('rpt_revenue_monthly') }}
      where year between 2013 and 2022 group by year) m on m.year = y.year
where {{ differs('y.season_peak_trough_ratio', 'm.ratio', 1e-12) }}
) checks
where n > 0
