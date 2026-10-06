-- PS2, deck slide 6 yêu cầu 4: "tìm tháng đường R 12 tháng đổi hướng, xem hướng mới có kéo dài không".
-- 1 dòng = 1 tháng × 1 khoảng so (seed ps2_direction_rule). Hướng tại tháng t = r_12m(t) so với r_12m(t − k):
-- lớn hơn là 'len', nhỏ hơn là 'xuong'. Các tháng liền nhau cùng hướng gom thành một "đoạn" (run);
-- đoạn dài ≥ min_run_months tháng mới tính là hướng bền (ghi chú slide 7: "dấu xu hướng kéo dài ít nhất 6 tháng").
-- Chỉ xét LÊN hay XUỐNG, không xét tốc độ: giảm nhẹ → giảm mạnh vẫn là cùng hướng.
with m as (
    select month_start_date, year * 12 + month as month_ordinal, r_12m
    from {{ ref('rpt_revenue_monthly') }}
    where r_12m is not null
),
d as (
    select
        w.window_months, w.is_main_window, w.min_run_months,
        m.month_start_date, m.month_ordinal, m.r_12m,
        p.r_12m                                            as r_12m_window_ago,
        {{ ratio('m.r_12m', 'p.r_12m') }} - 1              as change_rate,
        case when m.r_12m > p.r_12m then 'len'
             when m.r_12m < p.r_12m then 'xuong'
             else 'ngang' end                              as direction
    from {{ ref('ps2_direction_rule') }} w
    cross join m
    join m p on p.month_ordinal = m.month_ordinal - w.window_months
),
g as (   -- gaps-and-islands: cùng hướng liền nhau → cùng grp
    select d.*,
           row_number() over (partition by window_months order by month_ordinal)
         - row_number() over (partition by window_months, direction order by month_ordinal) as grp
    from d
)
select
    window_months, is_main_window, min_run_months,
    month_start_date, month_ordinal, r_12m, r_12m_window_ago, change_rate, direction,
    min(month_start_date) over (partition by window_months, direction, grp)          as run_start_date,
    count(*) over (partition by window_months, direction, grp)                        as run_length_months,
    count(*) over (partition by window_months, direction, grp) >= min_run_months      as is_persistent_run
from g
