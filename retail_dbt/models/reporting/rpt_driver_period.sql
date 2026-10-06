-- PS4 (deck slide 10–11) và phần C/F của PS5 (slide 12–13): ΔR = N + U + P, ΔN = C + F theo KỲ.
-- 1 dòng = 1 kỳ: từng năm 2014–2022 (period_type 'year') hoặc một giai đoạn PS2 (period_type 'phase').
-- Giai đoạn = CỘNG phần góp của các năm Y có start_year < Y <= end_year. ΔR năm Y là R_Y − R_(Y−1), nên tổng các năm đúng
-- bằng R cuối − R đầu giai đoạn (khớp rpt_revenue_phase.delta_r; đây không phải quy ước mới như ở PS3).
-- Đây là cộng dồn từng năm, KHÔNG phải một lần tách N → U → P từ năm đầu thẳng tới năm cuối: phần tương tác khác nhau nên
-- hai cách cho số khác nhau (dev đề xuất cộng dồn, docs/dwh_huong_dan_pm_ba.md §9 M4).
-- top_up_driver / top_down_driver: phần (n / u / p) góp dương lớn nhất / âm lớn nhất; NULL nếu không phần nào dương / âm.
-- delta_r_is_small: |ΔR| < min_abs_delta_rate × R đầu kỳ (seed driver_rule): % đóng góp không ổn định, nên đọc số tiền.
-- *_change_rate: % đổi của chính R / N / U / P, so thẳng năm cuối với năm đầu kỳ (dòng phụ dưới thẻ KPI PS4).
-- Không cộng được: % đổi của N, U, P cộng lại KHÔNG bằng % đổi R; chỉ phần góp (tiền) mới cộng về ΔR.
with y as (
    select year, r, n, u, p, delta_r, delta_n, contrib_n, contrib_u, contrib_p, contrib_c, contrib_f
    from {{ ref('rpt_revenue_yearly') }}
),
ph as (
    select phase_code, phase_name, start_year, end_year from {{ ref('ps2_phases') }}
),
yr as (
    select 'year' as period_type, cast(y.year as varchar(4)) as period_code, ph.phase_code, ph.phase_name,
           y.year - 1 as start_year, y.year as end_year,
           y.delta_r, y.contrib_n, y.contrib_u, y.contrib_p, y.delta_n, y.contrib_c, y.contrib_f
    from y
    left join ph on y.year > ph.start_year and y.year <= ph.end_year
    where y.delta_r is not null
),
pp as (
    select 'phase' as period_type, ph.phase_code as period_code, ph.phase_code, ph.phase_name,
           ph.start_year, ph.end_year,
           cast(sum(yr.delta_r) as decimal(38, 2)) as delta_r,
           sum(yr.contrib_n) as contrib_n, sum(yr.contrib_u) as contrib_u, sum(yr.contrib_p) as contrib_p,
           cast(sum(yr.delta_n) as bigint) as delta_n,
           sum(yr.contrib_c) as contrib_c, sum(yr.contrib_f) as contrib_f
    from ph
    join yr on yr.phase_code = ph.phase_code
    group by ph.phase_code, ph.phase_name, ph.start_year, ph.end_year
),
k as (
    select * from yr
    union all
    select * from pp
)
select
    k.period_type, k.period_code, k.phase_code, k.phase_name,
    cast(k.start_year as integer) as start_year, cast(k.end_year as integer) as end_year,
    y0.r as r_start, y1.r as r_end, k.delta_r,
    k.contrib_n, k.contrib_u, k.contrib_p,
    y0.n as n_start, y1.n as n_end, k.delta_n,
    y0.u as u_start, y1.u as u_end, y0.p as p_start, y1.p as p_end,
    {{ ratio('y1.r', 'y0.r') }} - 1 as r_change_rate,
    {{ ratio('y1.n', 'y0.n') }} - 1 as n_change_rate,
    {{ ratio('y1.u', 'y0.u') }} - 1 as u_change_rate,
    {{ ratio('y1.p', 'y0.p') }} - 1 as p_change_rate,
    k.contrib_c, k.contrib_f,
    case when greatest(k.contrib_n, k.contrib_u, k.contrib_p) > 0 then
        case greatest(k.contrib_n, k.contrib_u, k.contrib_p)
            when k.contrib_n then 'n' when k.contrib_u then 'u' else 'p' end
    end as top_up_driver,
    case when least(k.contrib_n, k.contrib_u, k.contrib_p) < 0 then
        case least(k.contrib_n, k.contrib_u, k.contrib_p)
            when k.contrib_n then 'n' when k.contrib_u then 'u' else 'p' end
    end as top_down_driver,
    abs(k.delta_r) < rule.min_abs_delta_rate * y0.r as delta_r_is_small
from k
join y y0 on y0.year = k.start_year
join y y1 on y1.year = k.end_year
cross join {{ ref('driver_rule') }} rule
