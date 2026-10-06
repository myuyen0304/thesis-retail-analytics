select * from (
-- PS2: giai đoạn và điểm đổi hướng (quy tắc: docs/dwh_huong_dan_pm_ba.md §4 "PS2: 4 giai đoạn").
-- PM/BA đổi mốc thì sửa seed ps2_phases VÀ các số khóa ở cuối file này cùng lúc.

-- 1. Các giai đoạn phủ liền mạch 2013–2022: bắt đầu 2013, kết thúc 2022, giai đoạn sau bắt đầu đúng năm giai đoạn trước kết thúc
select 'giai doan phai phu lien mach 2013-2022' as rule, count(*) as n
from (
    select start_year, end_year,
           lag(end_year) over (order by start_year) as prev_end,
           min(start_year) over () as first_start,
           max(end_year) over () as last_end
    from {{ ref('ps2_phases') }}
) t
where end_year <= start_year
   or (prev_end is not null and prev_end <> start_year)
   or first_start <> 2013 or last_end <> 2022
union all
-- 2. R đầu/cuối khớp R tính độc lập từ dòng hàng delivered (không qua rpt_revenue_yearly)
select 'r_start/r_end khop dong hang delivered', count(*)
from {{ ref('rpt_revenue_phase') }} ph
join (
    select year, sum(net_amount) as r
    from {{ ref('int_reporting_order_items') }}
    where is_delivered
    group by year
) y on y.year in (ph.start_year, ph.end_year)
where (y.year = ph.start_year and {{ differs('ph.r_start', 'y.r') }})
   or (y.year = ph.end_year   and {{ differs('ph.r_end', 'y.r') }})
union all
-- 3. Định nghĩa CAGR: (1 + cagr)^n = r_end / r_start
select 'cagr dung dinh nghia', count(*)
from {{ ref('rpt_revenue_phase') }}
where abs(power(1 + cagr, n_years) - {{ ratio('r_end', 'r_start') }}) > 1e-9
   or {{ differs('delta_r', 'r_end - r_start') }}
union all
-- 4. Mỗi ranh giới giữa hai giai đoạn có đúng 1 điểm đổi hướng, độ lớn = R năm sau / R năm ranh giới − 1
select 'so diem doi huong = so giai doan - 1', count(*)
from (select (select count(*) from {{ ref('ps2_phases') }}) - 1 as expected,
             (select count(*) from {{ ref('rpt_revenue_turning_point') }}) as actual) t
where expected <> actual
union all
select 'do lon diem doi huong dung dinh nghia', count(*)
from {{ ref('rpt_revenue_turning_point') }} tp
join {{ ref('rpt_revenue_yearly') }} b on b.year = tp.turning_year
join {{ ref('rpt_revenue_yearly') }} a on a.year = tp.turning_year + 1
where abs(tp.magnitude - ({{ ratio('a.r', 'b.r') }} - 1)) > 1e-12
union all
-- 5. Vị trí trên đường r_12m (app tô nền / đặt điểm theo các cột này): r_12m tại tháng 12 = R cả năm
select 'r_12m tai band_start/band_end = r_start/r_end', count(*)
from {{ ref('rpt_revenue_phase') }} ph
join {{ ref('rpt_revenue_monthly') }} ms on ms.month_start_date = ph.band_start_date
join {{ ref('rpt_revenue_monthly') }} me on me.month_start_date = ph.band_end_date
where {{ differs('ms.r_12m', 'ph.r_start') }} or {{ differs('me.r_12m', 'ph.r_end') }}
union all
select 'r_12m tai turning_month_date = r_12m_before', count(*)
from {{ ref('rpt_revenue_turning_point') }} tp
left join {{ ref('rpt_revenue_monthly') }} m on m.month_start_date = tp.turning_month_date
where m.r_12m is null or {{ differs('m.r_12m', 'tp.r_12m_before') }}
union all
-- 5b. Nhãn giai đoạn của năm (rpt_revenue_yearly.ps2_phase_codes, PS3 dùng): có mã giai đoạn ⇔ năm nằm trong giai đoạn đó
select 'nhan giai doan cua nam = cac giai doan chua nam do', count(*)
from {{ ref('rpt_revenue_yearly') }} y
cross join {{ ref('ps2_phases') }} p
where (y.year between p.start_year and p.end_year)
   <> (coalesce(position(p.phase_code in y.ps2_phase_codes), 0) > 0)
union all
select 'nhan giai doan: 2012 NULL; 2016 A/B, 2018 B/C, 2019 C/D', count(*)
from {{ ref('rpt_revenue_yearly') }}
where (year = 2012 and ps2_phase_codes is not null)
   or (year = 2016 and ps2_phase_codes <> 'A/B')
   or (year = 2018 and ps2_phase_codes <> 'B/C')
   or (year = 2019 and ps2_phase_codes <> 'C/D')
union all
-- 6. Số đã chốt ngày 2026-09-27 (bảng trong docs/dwh_huong_dan_pm_ba.md §4)
select 'so da chot: CAGR A +8,75%, B -6,39%, C -39,10%, D -0,14%', count(*)
from {{ ref('rpt_revenue_phase') }}
where (phase_code = 'A' and not (cagr between  0.08750 and  0.08752))
   or (phase_code = 'B' and not (cagr between -0.06386 and -0.06385))
   or (phase_code = 'C' and not (cagr between -0.39101 and -0.39100))
   or (phase_code = 'D' and not (cagr between -0.00145 and -0.00144))
union all
select 'so da chot: diem doi huong cuoi 2016 -9,7%, cuoi 2018 -39,1% (giam tang toc), cuoi 2019 -6,7% (doi nhip)', count(*)
from {{ ref('rpt_revenue_turning_point') }}
where (turning_year = 2016 and not (magnitude between -0.09728 and -0.09726))
   or (turning_year = 2018 and not (magnitude between -0.39101 and -0.39100))
   or (turning_year = 2019 and not (magnitude between -0.06701 and -0.06700))
   or coalesce(turn_note, '') <> case turning_year when 2018 then 'giảm tăng tốc' when 2019 then 'đổi nhịp' else '' end
) checks
where n > 0
