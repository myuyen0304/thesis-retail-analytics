select * from (
-- M4 (PS4 + C/F của PS5): rpt_driver_period, rpt_driver_bridge, cột mới của rpt_revenue_segment_yearly.
-- 1. Dòng năm = đúng số của rpt_revenue_yearly; năm nào cũng thuộc đúng một giai đoạn (start_year < Y <= end_year)
select 'nam: khop rpt_revenue_yearly, du 2014-2022, giai doan dung quy tac' as rule, count(*) as n
from {{ ref('rpt_revenue_yearly') }} y
full outer join (select * from {{ ref('rpt_driver_period') }} where period_type = 'year') d
  on cast(d.period_code as integer) = y.year
left join {{ ref('ps2_phases') }} ph on ph.phase_code = d.phase_code
where (y.year >= 2014 and d.period_code is null) or (y.year < 2014 and d.period_code is not null)
   or (d.period_code is not null and (
        y.year is null or d.start_year <> y.year - 1 or d.end_year <> y.year
        or {{ differs('d.delta_r', 'y.delta_r') }} or {{ differs('d.contrib_n', 'y.contrib_n') }}
        or {{ differs('d.contrib_u', 'y.contrib_u') }} or {{ differs('d.contrib_p', 'y.contrib_p') }}
        or d.delta_n <> y.delta_n or {{ differs('d.contrib_c', 'y.contrib_c', 1e-6) }}
        or {{ differs('d.contrib_f', 'y.contrib_f', 1e-6) }}
        or ph.phase_code is null or not (y.year > ph.start_year and y.year <= ph.end_year)))
union all
-- 2. Dòng giai đoạn = cộng các năm của nó; ΔR, R đầu, R cuối khớp rpt_revenue_phase (PS2)
select 'giai doan: = cong cac nam, khop rpt_revenue_phase', count(*)
from {{ ref('rpt_revenue_phase') }} ph
full outer join (select * from {{ ref('rpt_driver_period') }} where period_type = 'phase') d on d.period_code = ph.phase_code
left join (
    select phase_code, sum(delta_r) as dr, sum(contrib_n) as cn, sum(contrib_u) as cu, sum(contrib_p) as cp,
           sum(delta_n) as dn, sum(contrib_c) as cc, sum(contrib_f) as cf, count(*) as k
    from {{ ref('rpt_driver_period') }} where period_type = 'year' group by phase_code
) s on s.phase_code = ph.phase_code
where d.period_code is null or ph.phase_code is null or s.k <> ph.end_year - ph.start_year
   or d.start_year <> ph.start_year or d.end_year <> ph.end_year
   or {{ differs('d.delta_r', 'ph.delta_r') }} or {{ differs('d.r_start', 'ph.r_start') }} or {{ differs('d.r_end', 'ph.r_end') }}
   or {{ differs('d.delta_r', 's.dr') }} or {{ differs('d.contrib_n', 's.cn') }} or {{ differs('d.contrib_u', 's.cu') }}
   or {{ differs('d.contrib_p', 's.cp') }} or d.delta_n <> s.dn
   or {{ differs('d.contrib_c', 's.cc', 1e-6) }} or {{ differs('d.contrib_f', 's.cf', 1e-6) }}
union all
-- 3. Cộng về tổng (deck slide 10 yêu cầu 4, slide 12 yêu cầu 5), mọi kỳ
select 'moi ky: N + U + P = delta_r = R cuoi - R dau; C + F = delta_n = N cuoi - N dau', count(*)
from {{ ref('rpt_driver_period') }}
where {{ differs('contrib_n + contrib_u + contrib_p', 'delta_r') }} or {{ differs('delta_r', 'r_end - r_start') }}
   or {{ differs('contrib_c + contrib_f', 'delta_n', 1e-6) }} or delta_n <> n_end - n_start
union all
-- 4. Phần kéo lên / kéo xuống nhiều nhất: tính lại bằng cách xếp hạng 3 dòng (không dùng greatest/least như model)
select 'top_up_driver / top_down_driver tinh lai bang xep hang', count(*)
from {{ ref('rpt_driver_period') }} d
left join (
    select period_code,
           max(case when rk_up = 1 and v > 0 then k end) as up_k,
           max(case when rk_dn = 1 and v < 0 then k end) as dn_k
    from (
        select period_code, k, v,
               row_number() over (partition by period_code order by v desc) as rk_up,
               row_number() over (partition by period_code order by v) as rk_dn
        from (
            select period_code, 'n' as k, contrib_n as v from {{ ref('rpt_driver_period') }}
            union all select period_code, 'u', contrib_u from {{ ref('rpt_driver_period') }}
            union all select period_code, 'p', contrib_p from {{ ref('rpt_driver_period') }}
        ) x
    ) r
    group by period_code
) t on t.period_code = d.period_code
where coalesce(d.top_up_driver, '-') <> coalesce(t.up_k, '-') or coalesce(d.top_down_driver, '-') <> coalesce(t.dn_k, '-')
union all
-- 5. Cờ ΔR nhỏ: tính lại từ R của rpt_revenue_yearly và seed
select 'delta_r_is_small tinh lai (ky va PS5)', count(*)
from (
    select d.delta_r_is_small as flag, abs(y1.r - y0.r) < rule.min_abs_delta_rate * y0.r as exp
    from {{ ref('rpt_driver_period') }} d
    join {{ ref('rpt_revenue_yearly') }} y0 on y0.year = d.start_year
    join {{ ref('rpt_revenue_yearly') }} y1 on y1.year = d.end_year
    cross join {{ ref('driver_rule') }} rule
    union all
    select s.delta_r_is_small, abs(y.delta_r) < rule.min_abs_delta_rate * y.r_prior_year
    from {{ ref('rpt_revenue_segment_yearly') }} s
    join {{ ref('rpt_revenue_yearly') }} y on y.year = s.year
    cross join {{ ref('driver_rule') }} rule
    where s.year >= 2014
) f
where flag is null or flag <> exp
union all
-- 6. Thác: cột đầu/cuối từ 0; cột giữa nối tiếp nhau và bằng phần góp; cột giữa cuối cùng chạm đúng giá trị cuối kỳ
select 'thac r_nup / n_cf: dung so, noi tiep, cham dung gia tri cuoi ky', count(*)
from {{ ref('rpt_driver_bridge') }} b
join {{ ref('rpt_driver_period') }} d on d.period_code = b.period_code and d.period_type = b.period_type
left join {{ ref('rpt_driver_bridge') }} prev
  on prev.period_code = b.period_code and prev.bridge_code = b.bridge_code and prev.step_order = b.step_order - 1
where {{ differs('b.bar_end - b.bar_start', 'b.amount') }}
   or (b.step_code in ('r_start', 'r_end', 'n_start', 'n_end') and b.bar_start <> 0)
   or (b.step_code = 'r_start' and ({{ differs('b.amount', 'd.r_start') }} or b.step_year <> d.start_year))
   or (b.step_code = 'r_end' and ({{ differs('b.amount', 'd.r_end') }} or b.step_year <> d.end_year))
   or (b.step_code = 'n_start' and ({{ differs('b.amount', 'd.n_start') }} or b.step_year <> d.start_year))
   or (b.step_code = 'n_end' and ({{ differs('b.amount', 'd.n_end') }} or b.step_year <> d.end_year))
   or (b.step_code = 'n' and {{ differs('b.amount', 'd.contrib_n') }})
   or (b.step_code = 'u' and {{ differs('b.amount', 'd.contrib_u') }})
   or (b.step_code = 'p' and ({{ differs('b.amount', 'd.contrib_p') }} or {{ differs('b.bar_end', 'd.r_end') }}))
   or (b.step_code = 'c' and {{ differs('b.amount', 'd.contrib_c', 1e-6) }})
   or (b.step_code = 'f' and ({{ differs('b.amount', 'd.contrib_f', 1e-6) }} or {{ differs('b.bar_end', 'd.n_end', 1e-6) }}))
   or (b.step_code in ('n', 'u', 'p', 'c', 'f') and (prev.step_order is null
        or {{ differs('b.bar_start', "case when prev.step_code in ('r_start', 'n_start') then prev.amount else prev.bar_end end", 1e-6) }}))
union all
select 'thac: moi ky du 5 cot r_nup + 4 cot n_cf', count(*)
from {{ ref('rpt_driver_period') }} d
left join (
    select period_code, sum(case when bridge_code = 'r_nup' then 1 else 0 end) as k_r,
           sum(case when bridge_code = 'n_cf' then 1 else 0 end) as k_n
    from {{ ref('rpt_driver_bridge') }} group by period_code
) b on b.period_code = d.period_code
where b.k_r is null or b.k_r <> 5 or b.k_n <> 4
union all
-- 7. PS5: hạng 1..k liền nhau, không trùng; hạng nhỏ hơn thì ΔR không nhỏ hơn
select 'PS5 delta_r_rank: 1..k, theo thu tu delta_r', count(*)
from (
    select s.dimension_name, s.year, s.delta_r_rank, s.delta_r,
           count(*) over (partition by s.dimension_name, s.year) as k,
           lag(s.delta_r) over (partition by s.dimension_name, s.year order by s.delta_r_rank) as prev_dr,
           count(*) over (partition by s.dimension_name, s.year, s.delta_r_rank) as dup
    from {{ ref('rpt_revenue_segment_yearly') }} s
    where s.year >= 2014
) r
where delta_r_rank is null or delta_r_rank < 1 or delta_r_rank > k or dup > 1 or prev_dr < delta_r
union all
select 'PS5 truoc 2014 khong co hang / co / so nhom tang giam', count(*)
from {{ ref('rpt_revenue_segment_yearly') }}
where year < 2014 and (delta_r_rank is not null or delta_r_is_small is not null or n_groups_up is not null
                       or n_groups_down is not null)
union all
-- đếm lại bằng group by (model dùng hàm cửa sổ)
select 'PS5 n_groups / n_groups_up / n_groups_down dem lai', count(*)
from {{ ref('rpt_revenue_segment_yearly') }} s
join (
    select dimension_name, year, count(*) as k,
           sum(case when delta_r > 0 then 1 else 0 end) as up, sum(case when delta_r < 0 then 1 else 0 end) as dn
    from {{ ref('rpt_revenue_segment_yearly') }} group by dimension_name, year
) g on g.dimension_name = s.dimension_name and g.year = s.year
where s.n_groups <> g.k or (s.year >= 2014 and (s.n_groups_up <> g.up or s.n_groups_down <> g.dn))
union all
-- 7b. Kiểm lựa chọn "cộng dồn từng năm" cho giai đoạn: tách thẳng N → U → P từ năm đầu tới năm cuối giai đoạn cho cùng phần
-- kéo lên / kéo xuống, mỗi phần lệch dưới 5 triệu (số 2026-09-29: lệch lớn nhất 3,2 triệu, phần N giai đoạn B)
select 'giai doan: tach thang cung ket luan, moi phan lech < 5 trieu', count(*)
from (
    select d.*,
           (y1.n - y0.n) * y0.u * y0.p as dn, y1.n * (y1.u - y0.u) * y0.p as du, y1.n * y1.u * (y1.p - y0.p) as dq
    from {{ ref('rpt_driver_period') }} d
    join {{ ref('rpt_revenue_yearly') }} y0 on y0.year = d.start_year
    join {{ ref('rpt_revenue_yearly') }} y1 on y1.year = d.end_year
    where d.period_type = 'phase'
) t
where abs(contrib_n - dn) >= 5e6 or abs(contrib_u - du) >= 5e6 or abs(contrib_p - dq) >= 5e6
   or coalesce(top_up_driver, '-') <> coalesce(case when greatest(dn, du, dq) > 0 then
          case greatest(dn, du, dq) when dn then 'n' when du then 'u' else 'p' end end, '-')
   or coalesce(top_down_driver, '-') <> coalesce(case when least(dn, du, dq) < 0 then
          case least(dn, du, dq) when dn then 'n' when du then 'u' else 'p' end end, '-')
union all
-- 8. Số khóa ngày 2026-09-29 (docs/dwh_huong_dan_pm_ba.md §9 M4). Đơn vị triệu, làm tròn 2 chữ số.
select 'so khoa M4: 2019 N -572,42 U +2,58 P +14,89; giai doan A-D; co nho chi 2015 va D', count(*)
from {{ ref('rpt_driver_period') }}
where (period_code = '2019' and not (round(contrib_n / 1e4) = -57242 and round(contrib_u / 1e4) = 258
                                     and round(contrib_p / 1e4) = 1489 and delta_n = -22481))
   or (period_code = 'A' and not (round(delta_r / 1e4) = 36034 and round(contrib_n / 1e4) = 9397
                                  and round(contrib_u / 1e4) = -3525 and round(contrib_p / 1e4) = 30162
                                  and top_up_driver = 'p' and top_down_driver = 'u'))
   or (period_code = 'B' and not (round(delta_r / 1e4) = -20023 and round(contrib_n / 1e4) = -24989
                                  and top_up_driver = 'p' and top_down_driver = 'n'))
   or (period_code = 'C' and not (round(delta_r / 1e4) = -55495 and top_up_driver = 'p' and top_down_driver = 'n'))
   or (period_code = 'D' and not (round(delta_r / 1e4) = -374 and round(contrib_n / 1e4) = -14576
                                  and round(contrib_p / 1e4) = 16034 and top_up_driver = 'p' and top_down_driver = 'n'))
   or (delta_r_is_small <> (period_code in ('2015', 'D')))
union all
-- 9. % đổi của R / N / U / P và giá trị đầu/cuối của U, P (dòng phụ dưới thẻ PS4, sửa sau góp ý PM 2026-09-29).
-- Dòng năm: khớp yoy_* của rpt_revenue_yearly (tính bằng lag, độc lập với model). Mọi kỳ: = giá trị năm cuối / năm đầu − 1.
select 'ty le doi R/N/U/P: nam khop yoy_*, moi ky = cuoi / dau - 1', count(*)
from {{ ref('rpt_driver_period') }} d
join {{ ref('rpt_revenue_yearly') }} y0 on y0.year = d.start_year
join {{ ref('rpt_revenue_yearly') }} y1 on y1.year = d.end_year
where {{ differs('d.u_start', 'y0.u', 1e-9) }} or {{ differs('d.u_end', 'y1.u', 1e-9) }}
   or {{ differs('d.p_start', 'y0.p', 1e-6) }} or {{ differs('d.p_end', 'y1.p', 1e-6) }}
   or {{ differs('d.r_change_rate', ratio('y1.r', 'y0.r') ~ ' - 1', 1e-9) }} or {{ differs('d.n_change_rate', ratio('y1.n', 'y0.n') ~ ' - 1', 1e-9) }}
   or {{ differs('d.u_change_rate', 'y1.u / y0.u - 1', 1e-9) }} or {{ differs('d.p_change_rate', 'y1.p / y0.p - 1', 1e-9) }}
   or (d.period_type = 'year' and ({{ differs('d.r_change_rate', 'y1.yoy_rate', 1e-9) }}
        or {{ differs('d.n_change_rate', 'y1.yoy_n', 1e-9) }} or {{ differs('d.u_change_rate', 'y1.yoy_u', 1e-9) }}
        or {{ differs('d.p_change_rate', 'y1.yoy_p', 1e-9) }}))
union all
select 'so khoa ty le doi: 2019 R -39,10% N -40,33% U +0,305% P +1,75%; giai doan A N 61.588 -> 66.067', count(*)
from {{ ref('rpt_driver_period') }}
where (period_code = '2019' and not (abs(r_change_rate + 0.3910) < 5e-5 and abs(n_change_rate + 0.4033) < 5e-5
                                     and abs(u_change_rate - 0.00305) < 5e-5 and abs(p_change_rate - 0.0175) < 5e-5))
   or (period_code = 'A' and not (n_start = 61588 and n_end = 66067 and round(n_change_rate * 1000) = 73))
union all
select 'so khoa M4 PS5: 2019 Streetwear giam nhieu nhat (hang 4/4), gop 83,6% muc giam, ty trong -1,03 diem %', count(*)
from {{ ref('rpt_revenue_segment_yearly') }}
where year = 2019 and dimension_name = 'category' and dimension_value = 'Streetwear'
  and not (delta_r_rank = 4 and round(contribution_to_delta * 1000) = 836 and round(share_shift_pp * 100) = -103
           and n_groups = 4 and n_groups_down = 4 and n_groups_up = 0)
) checks
where n > 0
