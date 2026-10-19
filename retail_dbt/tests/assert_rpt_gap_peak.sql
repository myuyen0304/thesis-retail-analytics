select * from (
-- B8 (2026-10-18): hai cột trang PS1 / PS3 trước đây tự tính trong app, nay đọc từ reporting.
-- Trả về quy tắc bị vi phạm và số dòng vi phạm.

-- 1. G − R của kỳ gộp và từng năm = G trừ R = cộng bốn khoản chênh (hủy, trả, chưa giao, chiết khấu đơn đã giao)
select 'rpt_revenue_total: gap_g_minus_r = G - R = cong 4 khoan chenh' as rule, count(*) as n
from {{ ref('rpt_revenue_total') }}
where {{ differs('gap_g_minus_r', 'g - r') }}
   or {{ differs('gap_g_minus_r', 'cancelled_gross + returned_gross + undelivered_gross + delivered_discount') }}
union all
select 'rpt_revenue_yearly: gap_g_minus_r = G - R = cong 4 khoan chenh', count(*)
from {{ ref('rpt_revenue_yearly') }}
where {{ differs('gap_g_minus_r', 'g - r') }}
   or {{ differs('gap_g_minus_r', 'cancelled_gross + returned_gross + undelivered_gross + delivered_discount') }}
union all
-- 2. Tháng cao / thấp nhất cả kỳ (nhịp mua_vu): R gộp các năm của tháng đó là lớn / nhỏ nhất trong 12 tháng,
--    và tỷ số hai tháng này đúng bằng metric_value. Nhịp khác để trống.
select 'rpt_calendar_stability: peak_month / trough_month cua mua_vu', count(*)
from {{ ref('rpt_calendar_stability') }} s
cross join (
    select max(r) as r_max, min(r) as r_min, count(*) as k
    from (select month, sum(r) as r from {{ ref('rpt_revenue_monthly') }} where is_analysis_period group by month) m
) p
left join (select month, sum(r) as r from {{ ref('rpt_revenue_monthly') }} where is_analysis_period group by month) hi
       on hi.month = s.peak_month
left join (select month, sum(r) as r from {{ ref('rpt_revenue_monthly') }} where is_analysis_period group by month) lo
       on lo.month = s.trough_month
where s.rhythm_code = 'mua_vu'
  and (p.k <> 12 or {{ differs('hi.r', 'p.r_max') }} or {{ differs('lo.r', 'p.r_min') }}
       or {{ differs('s.metric_value', ratio('hi.r', 'lo.r'), abs_tol=1e-9) }})
union all
select 'rpt_calendar_stability: nhip khac mua_vu khong co peak_month / trough_month', count(*)
from {{ ref('rpt_calendar_stability') }}
where rhythm_code <> 'mua_vu' and (peak_month is not null or trough_month is not null)
) checks
where n > 0
