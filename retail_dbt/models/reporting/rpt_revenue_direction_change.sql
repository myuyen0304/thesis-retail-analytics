-- PS2: các tháng đường R 12 tháng ĐỔI HƯỚNG, theo từng khoảng so (seed ps2_direction_rule).
-- Chỉ xét các đoạn hướng bền (≥ min_run_months tháng); đoạn ngắn ngược hướng ở giữa coi là nhiễu.
-- Đổi hướng = đoạn bền đầu tiên có hướng khác đoạn bền trước nó. Mỗi dòng ghi:
--   change_month_date  tháng PHÁT HIỆN (đoạn hướng mới bắt đầu); đỉnh/đáy thật nằm trước đó vì so với k tháng trước
--   extreme_month_date đỉnh (nếu chuyển sang xuống) / đáy (nếu chuyển sang lên) của r_12m, từ đầu khối hướng cũ tới tháng phát hiện
--   months_held        hướng mới giữ bao nhiêu tháng, tới lần đổi hướng kế tiếp hoặc hết dữ liệu
with dir as (
    select * from {{ ref('rpt_revenue_direction') }}
),
runs as (
    select window_months, is_main_window, direction, run_start_date,
           min(month_ordinal) as start_ord, count(*) as run_length_months
    from dir
    where is_persistent_run
    group by window_months, is_main_window, direction, run_start_date
),
p as (
    select runs.*, lag(direction) over (partition by window_months order by start_ord) as prev_direction
    from runs
),
blocks as (   -- khối = chuỗi đoạn bền liền nhau cùng hướng; chỉ giữ đoạn mở đầu mỗi khối
    select p.*,
           lag(start_ord) over (partition by window_months order by start_ord)  as prev_block_start_ord,
           lead(start_ord) over (partition by window_months order by start_ord) as next_block_start_ord
    from p
    where prev_direction is null or direction <> prev_direction
),
c as (
    select * from blocks where prev_direction is not null
),
last_month as (
    select window_months, max(month_ordinal) as last_ord from dir group by window_months
),
ext as (
    select c.window_months, c.start_ord, m.month_start_date, m.r_12m,
           row_number() over (
               partition by c.window_months, c.start_ord
               order by case when c.direction = 'xuong' then -m.r_12m else m.r_12m end, m.month_start_date
           ) as rn
    from c
    join dir m on m.window_months = c.window_months
              and m.month_ordinal between c.prev_block_start_ord and c.start_ord
)
select
    c.window_months,
    c.is_main_window,
    c.run_start_date                                               as change_month_date,
    c.prev_direction                                               as direction_before,
    c.direction                                                    as direction_after,
    e.month_start_date                                             as extreme_month_date,
    e.r_12m                                                        as extreme_r_12m,
    coalesce(c.next_block_start_ord, l.last_ord + 1) - c.start_ord as months_held,
    c.next_block_start_ord is null                                 as held_to_end_of_data
from c
join ext e on e.window_months = c.window_months and e.start_ord = c.start_ord and e.rn = 1
join last_month l on l.window_months = c.window_months
