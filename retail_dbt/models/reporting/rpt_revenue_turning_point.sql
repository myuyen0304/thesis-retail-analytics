-- PS2 KPI "Cú đổi hướng lớn cỡ nào". 1 dòng = 1 ranh giới giữa hai giai đoạn liền nhau (seed ps2_phases).
-- Điểm đặt ở CUỐI năm ranh giới, nên "12 tháng trước" = cả năm ranh giới, "12 tháng sau" = cả năm kế tiếp
-- (quy tắc 4, docs/dwh_huong_dan_pm_ba.md §4). Độ lớn = R 12 tháng sau / R 12 tháng trước − 1 (deck slide 7).
-- turning_month_date = tháng 12 của năm ranh giới: vị trí điểm trên đường r_12m. turn_note = ghi chú BA trong seed.
-- data_*: đối chiếu với cách dữ liệu tự tìm (rpt_revenue_direction_change, khoảng so chính): lần đổi hướng có đỉnh/đáy
-- r_12m nằm trong năm ranh giới. NULL = dữ liệu không thấy đổi hướng ở đó (vd. giảm nhẹ → sập vẫn là cùng hướng xuống).
with p as (
    select
        phase_code, phase_name, trend, start_year, end_year, end_turn_note,
        lead(phase_code) over (order by start_year) as next_phase_code,
        lead(phase_name) over (order by start_year) as next_phase_name,
        lead(trend)      over (order by start_year) as next_trend
    from {{ ref('ps2_phases') }}
)
select
    p.end_year                                   as turning_year,
    p.phase_code                                 as from_phase_code,
    p.next_phase_code                            as to_phase_code,
    p.phase_name                                 as from_phase_name,
    p.next_phase_name                            as to_phase_name,
    p.trend                                      as trend_before,
    p.next_trend                                 as trend_after,
    b.r                                          as r_12m_before,
    a.r                                          as r_12m_after,
    a.r - b.r                                    as delta_r,
    {{ ratio('a.r', 'b.r') }} - 1                as magnitude,
    m.month_start_date                           as turning_month_date,
    p.end_turn_note                              as turn_note,
    dc.extreme_month_date                        as data_extreme_month_date,
    dc.change_month_date                         as data_change_month_date
from p
join {{ ref('rpt_revenue_yearly') }} b on b.year = p.end_year
join {{ ref('rpt_revenue_yearly') }} a on a.year = p.end_year + 1
join {{ ref('rpt_revenue_monthly') }} m on m.year = p.end_year and m.month = 12
left join {{ ref('rpt_revenue_direction_change') }} dc
  on dc.is_main_window and extract(year from dc.extreme_month_date) = p.end_year
where p.next_phase_code is not null
