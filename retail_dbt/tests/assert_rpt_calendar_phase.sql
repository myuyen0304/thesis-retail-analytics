select * from (
-- PS3 so sánh giai đoạn (rpt_calendar_phase_month, rpt_calendar_phase) và độ ổn định (rpt_calendar_stability).

-- 1. Quy ước năm ranh giới: mỗi năm 2013–2022 thuộc đúng 1 giai đoạn, các giai đoạn nối liền không trùng;
--    năm ranh giới (có '/' trong ps2_phase_codes) tính cho giai đoạn đứng trước (kết thúc ở năm đó)
select 'moi nam dung 1 giai doan, nam ranh gioi -> giai doan ket thuc o nam do' as rule, count(*) as n
from {{ ref('rpt_revenue_yearly') }} y
left join (select distinct phase_code, first_year, last_year from {{ ref('rpt_calendar_phase_month') }}) p
  on y.year between p.first_year and p.last_year
where y.is_analysis_period
  and (p.phase_code is null
       or position(p.phase_code in y.ps2_phase_codes) <> 1)          -- mã đầu tiên trong 'A/B' là giai đoạn kết thúc
union all
select 'moi nam chi thuoc 1 giai doan (khong dem trung)', count(*)
from (select y.year, count(*) as k
      from {{ ref('rpt_revenue_yearly') }} y
      join (select distinct phase_code, first_year, last_year from {{ ref('rpt_calendar_phase_month') }}) p
        on y.year between p.first_year and p.last_year
      group by y.year) t
where k <> 1
union all
-- 2. Chỉ số tháng gộp: R = cộng R tháng của các năm; tổng 12 tháng = 12
select 'chi so thang gop: R = cong cac nam, tong 12 thang = 12', count(*)
from (
    select pm.phase_code, pm.month, pm.r, pm.month_index, sum(m.r) as r_chk,
           sum(pm.month_index) over (partition by pm.phase_code) as s
    from {{ ref('rpt_calendar_phase_month') }} pm
    join {{ ref('rpt_revenue_monthly') }} m
      on m.month = pm.month and m.year between pm.first_year and pm.last_year
    group by pm.phase_code, pm.month, pm.r, pm.month_index
) t
where {{ differs('r', 'r_chk') }} or {{ differs('s', '12', 1e-9) }}
union all
-- 3. Bảng giai đoạn: đỉnh/đáy đúng là max/min chỉ số gộp; mức dồn tính lại qua rpt_revenue_yearly (đường khác)
select 'giai doan: dinh/day = max/min chi so gop; muc don tinh lai tu bang nam', count(*)
from {{ ref('rpt_calendar_phase') }} c
join (select phase_code, max(month_index) as hi, min(month_index) as lo
      from {{ ref('rpt_calendar_phase_month') }} group by phase_code) x on x.phase_code = c.phase_code
join (select p.phase_code, sum(y.r_day26_plus) as r26, sum(y.r) as r, sum(y.r * y.eom_expected_share) as rexp
      from (select distinct phase_code, first_year, last_year from {{ ref('rpt_calendar_phase_month') }}) p
      join {{ ref('rpt_revenue_yearly') }} y on y.year between p.first_year and p.last_year
      group by p.phase_code) e on e.phase_code = c.phase_code
where {{ differs('c.peak_index', 'x.hi', 1e-12) }} or {{ differs('c.trough_index', 'x.lo', 1e-12) }}
   or {{ differs('c.season_peak_trough_ratio', 'x.hi / x.lo', 1e-12) }}
   or {{ differs('c.r_day26_plus', 'e.r26') }}
   or {{ differs('c.eom_excess', ratio('e.r26', 'e.r') ~ ' - ' ~ ratio('e.rexp', 'e.r'), 1e-12) }}
   or ((c.n_odd_years = 0 or c.n_even_years = 0) and c.august_odd_vs_even is not null)
union all
-- 4. Độ ổn định: cả kỳ khớp bảng gốc; giá trị cả kỳ nằm trong khoảng bỏ-từng-năm; số năm có nhịp ≤ số năm
select 'on dinh: ca ky khop rpt_revenue_total / rpt_august_parity; loo_min <= ca ky <= loo_max', count(*)
from {{ ref('rpt_calendar_stability') }} s
cross join (select eom_excess from {{ ref('rpt_revenue_total') }} where is_analysis_period) t
cross join {{ ref('rpt_august_parity') }} ap
where (s.rhythm_code = 'cuoi_thang' and {{ differs('s.metric_value', 't.eom_excess', 1e-12) }})
   or (s.rhythm_code = 'thang_8' and {{ differs('s.metric_value', 'ap.august_odd_vs_even', 1e-12) }})
   or not (s.loo_min <= s.metric_value and s.metric_value <= s.loo_max)
   or s.n_years_with_pattern > s.n_years or s.n_years <> 10
union all
-- chênh mùa gộp bỏ năm y tính lại bằng cách trừ: (R tháng m cả kỳ − R tháng m năm y), không qua join năm <> y
select 'on dinh mua vu: bo tung nam tinh lai bang phep tru', count(*)
from {{ ref('rpt_calendar_stability') }} s
cross join (
    select min(v) as lo, max(v) as hi
    from (select d.year, {{ ratio('max(a.r - d.r)', 'min(a.r - d.r)') }} as v
          from {{ ref('rpt_revenue_monthly') }} d
          join (select month, sum(r) as r from {{ ref('rpt_revenue_monthly') }} where is_analysis_period group by month) a
            on a.month = d.month
          where d.is_analysis_period
          group by d.year) t
) chk
where s.rhythm_code = 'mua_vu' and ({{ differs('s.loo_min', 'chk.lo', 1e-12) }} or {{ differs('s.loo_max', 'chk.hi', 1e-12) }})
union all
-- 5. Số khóa ngày 2026-09-28 (docs/dwh_huong_dan_pm_ba.md §9, góp ý M3)
select 'so khoa giai doan: nam A 2013-16, B 2017-18, C 2019, D 2020-22; chenh mua A 2,91 B 4,52 C 3,71 D 3,54', count(*)
from {{ ref('rpt_calendar_phase') }}
where not ((phase_code = 'A' and first_year = 2013 and last_year = 2016 and season_peak_trough_ratio between 2.9065 and 2.9067)
        or (phase_code = 'B' and first_year = 2017 and last_year = 2018 and season_peak_trough_ratio between 4.5193 and 4.5194)
        or (phase_code = 'C' and first_year = 2019 and last_year = 2019 and season_peak_trough_ratio between 3.7098 and 3.7099)
        or (phase_code = 'D' and first_year = 2020 and last_year = 2022 and season_peak_trough_ratio between 3.5375 and 3.5376))
   or peak_month <> 5 or trough_month <> 12
union all
select 'so khoa on dinh: mua vu 3,39 (3,22-3,49), cuoi thang +7,18 (7,08-7,35), thang 8 -37,7 (-39,1 den -36,2); 10/10 nam', count(*)
from {{ ref('rpt_calendar_stability') }}
where n_years_with_pattern <> 10
   or (rhythm_code = 'mua_vu' and not (metric_value between 3.3942 and 3.3943 and loo_min between 3.2213 and 3.2214
                                       and loo_max between 3.4895 and 3.4896))
   or (rhythm_code = 'cuoi_thang' and not (metric_value between 0.07183 and 0.07184 and loo_min between 0.07082 and 0.07083
                                           and loo_max between 0.07345 and 0.07346))
) checks
where n > 0
