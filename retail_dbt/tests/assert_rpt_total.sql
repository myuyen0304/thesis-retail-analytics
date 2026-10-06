select * from (
-- PS1 toàn kỳ (rpt_revenue_total), thác G → R (rpt_revenue_bridge) và dải thông tin chung (rpt_build_info).
-- Trả về quy tắc bị vi phạm và số dòng vi phạm.

-- 1. Số khóa: deck slide 4 (2012-2022) và G kỳ phân tích 2013-2022 (docs/dwh_huong_dan_pm_ba.md §9, M1)
select 'khoa so: 2012-2022 G = 16.430.476.585,53; R = 12.518.175.957,20; R/G = 76,2%' as rule, count(*) as n
from {{ ref('rpt_revenue_total') }}
where period_code = '2012-2022'
  and (abs(g - 16430476585.53) > 0.01 or abs(r - 12518175957.20) > 0.01
       or capture_rate < 0.7615 or capture_rate >= 0.7625)
union all
select 'khoa so: 2013-2022 G = 15.688.978.837,51', count(*)
from {{ ref('rpt_revenue_total') }}
where period_code = '2013-2022' and abs(g - 15688978837.51) > 0.01
union all
select 'du 2 ky gop', count(*)
from (select count(*) k from {{ ref('rpt_revenue_total') }}) t
where k <> 2
union all
-- 2. Toàn kỳ = cộng các năm cho measure cộng được (G, R, 4 phần, Q, N: mỗi đơn chỉ thuộc 1 năm)
select 'toan ky = tong cac nam (G, R, 4 phan chenh, Q, N)', count(*)
from {{ ref('rpt_revenue_total') }} t
join (
    select t.period_code,
           sum(y.g) g, sum(y.r) r, sum(y.cancelled_gross) cg, sum(y.returned_gross) rg,
           sum(y.undelivered_gross) ug, sum(y.delivered_discount) dd, sum(y.q) q, sum(y.n) n
    from {{ ref('rpt_revenue_total') }} t
    join {{ ref('rpt_revenue_yearly') }} y on y.year between t.start_year and t.end_year
    group by t.period_code
) y on y.period_code = t.period_code
where {{ differs('t.g', 'y.g') }} or {{ differs('t.r', 'y.r') }}
   or {{ differs('t.cancelled_gross', 'y.cg') }} or {{ differs('t.returned_gross', 'y.rg') }}
   or {{ differs('t.undelivered_gross', 'y.ug') }} or {{ differs('t.delivered_discount', 'y.dd') }}
   or t.q <> y.q or t.n <> y.n
union all
-- 3. C KHÔNG cộng được: đối soát với đếm phân biệt độc lập trên fact_order, và phải nhỏ hơn tổng C các năm
select 'C toan ky khop dem phan biet doc lap tu fact_order', count(*)
from {{ ref('rpt_revenue_total') }} t
left join (
    select t.period_code, count(distinct o.customer_sk) c, count(*) n
    from {{ ref('rpt_revenue_total') }} t
    join {{ ref('dim_date') }} d on d.year between t.start_year and t.end_year
    join {{ ref('fact_order') }} o on o.order_date_sk = d.date_sk
    join {{ ref('dim_order_junk') }} j on j.order_junk_sk = o.order_junk_sk
    where j.order_status = 'delivered'
    group by t.period_code
) o on o.period_code = t.period_code
where o.period_code is null or t.c <> o.c or t.n <> o.n
union all
select 'C toan ky < tong C cac nam (khach mua nhieu nam chi tinh 1 lan)', count(*)
from {{ ref('rpt_revenue_total') }} t
join (
    select t.period_code, sum(y.c) c
    from {{ ref('rpt_revenue_total') }} t
    join {{ ref('rpt_revenue_yearly') }} y on y.year between t.start_year and t.end_year
    group by t.period_code
) y on y.period_code = t.period_code
where t.c >= y.c
union all
select 'G - R = huy + tra + chua giao + chiet khau; U, P, F, AOV dung dinh nghia (toan ky)', count(*)
from {{ ref('rpt_revenue_total') }}
where {{ differs('g - r', 'cancelled_gross + returned_gross + undelivered_gross + delivered_discount') }}
   or {{ differs('n * u * p', 'r') }} or {{ differs('n * aov', 'r') }} or {{ differs('c * f', 'n', 1e-6) }}
union all
-- 4. Ngày đầu/cuối của kỳ 2012-2022 = toàn bộ lịch sử fact_daily_sales (không thiếu ngày, CLAUDE.md §1)
select 'ky 2012-2022 phu dung ngay dau/cuoi cua lich su', count(*)
from {{ ref('rpt_revenue_total') }} t
cross join (
    select min(d.full_date) d0, max(d.full_date) d1
    from {{ ref('fact_daily_sales') }} s join {{ ref('dim_date') }} d on d.date_sk = s.date_sk
    where s.is_actual
) h
where t.period_code = '2012-2022' and (t.first_order_date <> h.d0 or t.last_order_date <> h.d1)

union all
-- 5. Thác G → R: mỗi kỳ đủ 6 bước, khóa (kỳ, bước) duy nhất; kỳ = 2 kỳ gộp + 11 năm
select 'thac: moi ky du 6 buoc, khoa (period_code, step_order) duy nhat', count(*)
from (
    select period_code, count(*) k, count(distinct step_order) ks, min(step_order) s0, max(step_order) s1
    from {{ ref('rpt_revenue_bridge') }} group by period_code
) b
where k <> 6 or ks <> 6 or s0 <> 1 or s1 <> 6
union all
select 'thac: so ky = so dong rpt_revenue_total + rpt_revenue_yearly', count(*)
from (select count(distinct period_code) k from {{ ref('rpt_revenue_bridge') }}) b
cross join (select count(*) k from {{ ref('rpt_revenue_total') }}) t
cross join (select count(*) k from {{ ref('rpt_revenue_yearly') }}) y
where b.k <> t.k + y.k
union all
-- bước 1 là G, bước 6 là R, cả hai đứng từ 0; bước 2–5 âm và nối tiếp nhau; cột cuối của phần trừ dừng đúng ở R
select 'thac: G -> tru dan -> R, cac cot noi tiep nhau', count(*)
from (
    select b.*,
           lag(bar_end) over (partition by period_code order by step_order) as prev_end,
           max(case when step_code = 'g' then amount end) over (partition by period_code) as g_amt,
           max(case when step_code = 'r' then amount end) over (partition by period_code) as r_amt
    from {{ ref('rpt_revenue_bridge') }} b
) b
where (step_code in ('g', 'r') and ({{ differs('bar_start', '0') }} or {{ differs('bar_end', 'amount') }} or amount < 0))
   or (step_code not in ('g', 'r') and (amount > 0 or {{ differs('bar_start', 'prev_end') }}
                                       or {{ differs('bar_end', 'bar_start + amount') }}))
   or (step_code = 'discount' and {{ differs('bar_end', 'r_amt') }})
   or {{ differs('share_of_g * g_amt', 'abs(amount)') }}
union all
-- mỗi bước = đúng cột nguồn (kỳ gộp: rpt_revenue_total; năm: rpt_revenue_yearly)
select 'thac: moi buoc = cot nguon', count(*)
from {{ ref('rpt_revenue_bridge') }} b
left join (
    select period_code, g, cancelled_gross, returned_gross, undelivered_gross, delivered_discount, r
    from {{ ref('rpt_revenue_total') }}
    union all
    select cast(year as varchar(4)), g, cancelled_gross, returned_gross, undelivered_gross, delivered_discount, r
    from {{ ref('rpt_revenue_yearly') }}
) s on s.period_code = b.period_code
where s.period_code is null
   or {{ differs('b.amount', "case b.step_code when 'g' then s.g when 'cancelled' then -s.cancelled_gross
        when 'returned' then -s.returned_gross when 'undelivered' then -s.undelivered_gross
        when 'discount' then -s.delivered_discount when 'r' then s.r end") }}

union all
-- 6. Dải thông tin chung: đúng 1 dòng; ngày đầu/cuối = lịch sử; kỳ phân tích khớp cờ của rpt_revenue_yearly
select 'build_info: 1 dong, ngay dau/cuoi, ky phan tich, nam bat dau tang truong', count(*)
from (select count(*) k from {{ ref('rpt_build_info') }}) c
cross join {{ ref('rpt_build_info') }} i
cross join (
    select min(case when is_analysis_period then year end) a0, max(case when is_analysis_period then year end) a1,
           min(case when yoy_rate is not null then year end) g0
    from {{ ref('rpt_revenue_yearly') }}
) y
cross join {{ ref('rpt_revenue_total') }} t
where t.period_code = '2012-2022'
  and (c.k <> 1 or i.data_start_date <> t.first_order_date or i.data_end_date <> t.last_order_date
       or i.analysis_start_year <> y.a0 or i.analysis_end_year <> y.a1 or i.growth_start_year <> y.g0)
) checks
where n > 0
