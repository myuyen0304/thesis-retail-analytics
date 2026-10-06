-- PS3 (deck slide 8 yêu cầu 2): so sánh 3 nhịp lịch giữa các giai đoạn PS2. 1 dòng = 1 giai đoạn.
-- Năm của giai đoạn theo quy ước ở rpt_calendar_phase_month (năm ranh giới tính cho giai đoạn kết thúc ở năm đó),
-- nên mỗi giai đoạn là một dải năm liền first_year → last_year, không trùng nhau.
--   Nhịp 1: tháng cao / thấp nhất và chênh mùa cao/thấp, trên chỉ số tháng gộp của giai đoạn;
--   Nhịp 2: mức dồn cuối tháng, cùng cách tính với rpt_revenue_yearly (mức rải đều trọng số R tháng);
--   Nhịp 3: TB chỉ số tháng 8 năm lẻ / năm chẵn, cùng cách tính với rpt_august_parity. NULL nếu giai đoạn thiếu một phía.
with pm as (
    select * from {{ ref('rpt_calendar_phase_month') }}
),
ph as (
    select distinct phase_code, phase_name, first_year, last_year, n_years from pm
),
ranked as (
    select phase_code, month, month_index,
           row_number() over (partition by phase_code order by month_index desc, month) as rk_high,
           row_number() over (partition by phase_code order by month_index, month)      as rk_low
    from pm
),
season as (
    select phase_code,
           max(case when rk_high = 1 then month end)       as peak_month,
           max(case when rk_high = 1 then month_index end) as peak_index,
           max(case when rk_low = 1 then month end)        as trough_month,
           max(case when rk_low = 1 then month_index end)  as trough_index
    from ranked
    group by phase_code
),
m as (
    select ph.phase_code, mo.*
    from ph
    join {{ ref('rpt_revenue_monthly') }} mo on mo.year between ph.first_year and ph.last_year
),
eom as (
    select phase_code,
           sum(r_day26_plus)                                        as r_day26_plus,
           {{ ratio('sum(r_day26_plus)', 'sum(r)') }}               as eom_share,
           {{ ratio('sum(r * eom_expected_share)', 'sum(r)') }}     as eom_expected_share
    from m
    group by phase_code
),
aug as (
    select phase_code,
           count(case when is_odd_year then 1 end)                  as n_odd_years,
           count(case when not is_odd_year then 1 end)              as n_even_years,
           avg(case when is_odd_year then month_index end)          as august_index_odd,
           avg(case when not is_odd_year then month_index end)      as august_index_even
    from m
    where month = 8
    group by phase_code
)
select
    ph.phase_code, ph.phase_name, ph.first_year, ph.last_year, ph.n_years,
    s.peak_month, s.peak_index, s.trough_month, s.trough_index,
    {{ ratio('s.peak_index', 's.trough_index') }}                   as season_peak_trough_ratio,
    e.r_day26_plus, e.eom_share, e.eom_expected_share,
    e.eom_share - e.eom_expected_share                              as eom_excess,
    a.n_odd_years, a.n_even_years, a.august_index_odd, a.august_index_even,
    {{ ratio('a.august_index_odd', 'a.august_index_even') }} - 1    as august_odd_vs_even,
    -- thứ hạng giữa các giai đoạn (1 = cao nhất), để trang viết nhận xét so sánh mà không tự sắp xếp
    rank() over (order by {{ ratio('s.peak_index', 's.trough_index') }} desc) as season_ratio_rank,
    rank() over (order by e.eom_share - e.eom_expected_share desc)           as eom_excess_rank
from ph
join season s using (phase_code)
join eom e using (phase_code)
join aug a using (phase_code)
