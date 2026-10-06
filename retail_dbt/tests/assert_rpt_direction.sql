select * from (
-- PS2 tháng đổi hướng (rpt_revenue_direction, rpt_revenue_direction_change). Quy tắc: seed ps2_direction_rule.
-- Đổi quy tắc trong seed thì sửa các số khóa ở cuối file này cùng lúc.

-- 1. Hướng tính lại độc lập bằng lag() trên dãy r_12m liên tục (không qua month_ordinal, không qua self-join)
select 'huong = so r_12m voi k thang truoc (tinh lai bang lag)' as rule, count(*) as n
from {{ ref('rpt_revenue_direction') }} d
full join (
    select month_start_date, k, r_12m, prev
    from (
        select month_start_date, r_12m, 3 as k, lag(r_12m, 3) over (order by month_start_date) as prev
        from {{ ref('rpt_revenue_monthly') }} where r_12m is not null
        union all
        select month_start_date, r_12m, 6, lag(r_12m, 6) over (order by month_start_date)
        from {{ ref('rpt_revenue_monthly') }} where r_12m is not null
        union all
        select month_start_date, r_12m, 9, lag(r_12m, 9) over (order by month_start_date)
        from {{ ref('rpt_revenue_monthly') }} where r_12m is not null
    ) x
    where prev is not null
) i on i.month_start_date = d.month_start_date and i.k = d.window_months
where d.month_start_date is null or i.month_start_date is null
   or {{ differs('d.r_12m_window_ago', 'i.prev') }}
   or d.direction <> case when i.r_12m > i.prev then 'len' when i.r_12m < i.prev then 'xuong' else 'ngang' end
union all
-- 2. Đoạn (run): mọi tháng trong đoạn cùng hướng, đoạn liền nhau khác hướng, độ dài đúng
select 'doan cung huong: do dai dung, hai doan lien nhau khac huong', count(*)
from (
    select window_months, run_start_date, direction, run_length_months, is_persistent_run, min_run_months,
           count(*) over (partition by window_months, run_start_date) as k,
           min(direction) over (partition by window_months, run_start_date) as dmin,   -- Postgres: không có count(distinct) over
           max(direction) over (partition by window_months, run_start_date) as dmax,
           lag(direction) over (partition by window_months order by month_start_date) as prev_dir,
           lag(run_start_date) over (partition by window_months order by month_start_date) as prev_run
    from {{ ref('rpt_revenue_direction') }}
) r
where k <> run_length_months or dmin <> dmax
   or (prev_run is not null and prev_run <> run_start_date and prev_dir = direction)
   or is_persistent_run <> (run_length_months >= min_run_months)
union all
-- 3. Điểm đổi hướng: hướng trước ≠ sau; hướng mới giữ ≥ min_run_months; đỉnh/đáy đúng là r_12m của tháng đó
select 'diem doi huong: khac huong, giu du lau, dinh/day khop r_12m', count(*)
from {{ ref('rpt_revenue_direction_change') }} c
join {{ ref('ps2_direction_rule') }} w on w.window_months = c.window_months
left join {{ ref('rpt_revenue_monthly') }} m on m.month_start_date = c.extreme_month_date
where c.direction_before = c.direction_after
   or c.months_held < w.min_run_months
   or m.r_12m is null or {{ differs('c.extreme_r_12m', 'm.r_12m') }}
   or c.extreme_month_date > c.change_month_date
union all
-- 4. Số khóa ngày 2026-09-28 (deck slide 6 yêu cầu 4; docs/dwh_huong_dan_pm_ba.md §9 M2)
select 'so khoa: 3/6/9 thang -> xuong 11/2016, 02/2017, 05/2017 (dinh 08/2016); len 12/2021, 02/2022, 05/2022 (day 10/2021)', count(*)
from (
    select count(*) as k,
           sum(case when (window_months, change_month_date, direction_after, extreme_month_date, held_to_end_of_data) in (
                    (3, cast('2016-11-01' as date), 'xuong', cast('2016-08-01' as date), false),
                    (6, cast('2017-02-01' as date), 'xuong', cast('2016-08-01' as date), false),
                    (9, cast('2017-05-01' as date), 'xuong', cast('2016-08-01' as date), false),
                    (3, cast('2021-12-01' as date), 'len',   cast('2021-10-01' as date), true),
                    (6, cast('2022-02-01' as date), 'len',   cast('2021-10-01' as date), true),
                    (9, cast('2022-05-01' as date), 'len',   cast('2021-10-01' as date), true))
                    then 1 else 0 end) as hit
    from {{ ref('rpt_revenue_direction_change') }}
) t
where k <> 6 or hit <> 6
union all
-- 5. Đối chiếu với mốc BA (cột data_* của rpt_revenue_turning_point): cuối 2016 (tăng → giảm) dữ liệu tự tìm thấy,
--    đỉnh 08/2016, phát hiện 02/2017; cuối 2018, cuối 2019 là đổi tốc độ cùng hướng xuống nên không thấy
select 'doi chieu BA: cuoi 2016 du lieu thay (dinh 08/2016, phat hien 02/2017); cuoi 2018, 2019 khong', count(*)
from {{ ref('rpt_revenue_turning_point') }}
where (turning_year = 2016 and not (data_extreme_month_date = cast('2016-08-01' as date)
                                    and data_change_month_date = cast('2017-02-01' as date)))
   or (turning_year in (2018, 2019) and data_extreme_month_date is not null)
   or (trend_before = 'tang') <> (data_extreme_month_date is not null)
) checks
where n > 0
