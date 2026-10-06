-- PS1: thác G → R, dạng dài (1 dòng = 1 cột của biểu đồ thác). App chỉ đọc và vẽ, không tự cộng dồn.
-- Kỳ: 2 kỳ gộp của rpt_revenue_total + từng năm của rpt_revenue_yearly.
-- Bước 1 là G (cột từ 0), bước 2–5 là phần bị trừ (amount âm, cột treo từ bar_start xuống bar_end), bước 6 là R (cột từ 0).
with p as (
    select period_code, 'total' as period_type, cast(null as integer) as year, is_analysis_period,
           g, cancelled_gross, returned_gross, undelivered_gross, delivered_discount, r
    from {{ ref('rpt_revenue_total') }}
    union all
    select cast(year as varchar(4)), 'year', year, is_analysis_period,
           g, cancelled_gross, returned_gross, undelivered_gross, delivered_discount, r
    from {{ ref('rpt_revenue_yearly') }}
),
s as (
    select period_code, period_type, year, is_analysis_period, g,
           1 as step_order, 'g' as step_code, g as amount, 0 as bar_start, g as bar_end
    from p
    union all
    select period_code, period_type, year, is_analysis_period, g,
           2, 'cancelled', -cancelled_gross, g, g - cancelled_gross
    from p
    union all
    select period_code, period_type, year, is_analysis_period, g,
           3, 'returned', -returned_gross, g - cancelled_gross, g - cancelled_gross - returned_gross
    from p
    union all
    select period_code, period_type, year, is_analysis_period, g,
           4, 'undelivered', -undelivered_gross, g - cancelled_gross - returned_gross,
           g - cancelled_gross - returned_gross - undelivered_gross
    from p
    union all
    select period_code, period_type, year, is_analysis_period, g,
           5, 'discount', -delivered_discount, g - cancelled_gross - returned_gross - undelivered_gross,
           g - cancelled_gross - returned_gross - undelivered_gross - delivered_discount
    from p
    union all
    select period_code, period_type, year, is_analysis_period, g,
           6, 'r', r, 0, r
    from p
)
select
    period_code, period_type, year, is_analysis_period,
    step_order, step_code, amount, bar_start, bar_end,
    {{ ratio('abs(amount)', 'g') }} as share_of_g      -- độ lớn bước / G của cùng kỳ
from s
