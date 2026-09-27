select * from (
-- PS1/PS4: đẳng thức nội bộ của tầng reporting, và đối soát TỪNG THÁNG / NĂM với nguồn ĐỘC LẬP
-- (fact_order ở grain đơn, stg_payments, fact_daily_sales, fact_order_item không qua int_reporting).
-- Trả về quy tắc bị vi phạm và số dòng vi phạm.

-- Nền: int_reporting_order_items giữ nguyên số dòng và measure của fact_order_item (join không làm mất/nhân dòng)
select 'nen reporting bao toan dong va measure cua fact_order_item' as rule, count(*) as n
from (select count(*) k, sum(quantity) q, sum(gross_amount) g, sum(net_amount) r from {{ ref('int_reporting_order_items') }}) a
cross join (select count(*) k, sum(quantity) q, sum(gross_amount) g, sum(net_amount) r from {{ ref('fact_order_item') }}) b
where a.k <> b.k or a.q <> b.q or {{ differs('a.g', 'b.g') }} or {{ differs('a.r', 'b.r') }}
union all
select 'G - R = huy + tra + chua giao + chiet khau (thang)', count(*)
from {{ ref('rpt_revenue_monthly') }}
where {{ differs('g - r', 'cancelled_gross + returned_gross + undelivered_gross + delivered_discount') }}
union all
select 'G - R = huy + tra + chua giao + chiet khau (nam)', count(*)
from {{ ref('rpt_revenue_yearly') }}
where {{ differs('g - r', 'cancelled_gross + returned_gross + undelivered_gross + delivered_discount') }}
union all
select 'U, P, F, AOV dung dinh nghia (thang)', count(*)
from {{ ref('rpt_revenue_monthly') }}
where {{ differs('n * u * p', 'r') }} or {{ differs('n * aov', 'r') }} or {{ differs('c * f', 'n', 1e-6) }}
union all
select 'U, P, F, AOV dung dinh nghia (nam)', count(*)
from {{ ref('rpt_revenue_yearly') }}
where {{ differs('n * u * p', 'r') }} or {{ differs('n * aov', 'r') }} or {{ differs('c * f', 'n', 1e-6) }}
union all
-- Đối soát độc lập theo THÁNG: N, C từ fact_order; Q, R ngày >= 26 từ fact_order_item; R từ payments; G từ fact_daily_sales
select 'thang khop nguon doc lap (N, C, Q, R, R ngay>=26, G)', count(*)
from (
    select d.month_start_date, count(*) as n, count(distinct o.customer_sk) as c,
           sum(cast(p.payment_value as decimal(18, 2))) as r
    from {{ ref('fact_order') }} o
    join {{ ref('dim_order_junk') }} j on j.order_junk_sk = o.order_junk_sk
    join {{ ref('dim_date') }} d on d.date_sk = o.order_date_sk
    join {{ ref('stg_payments') }} p on p.order_id = o.order_id
    where j.order_status = 'delivered'
    group by d.month_start_date
) o
join (
    select d.month_start_date, sum(f.quantity) as q,
           sum(case when d.day_of_month >= 26 then f.net_amount else 0 end) as r26
    from {{ ref('fact_order_item') }} f
    join {{ ref('dim_order_junk') }} j on j.order_junk_sk = f.order_junk_sk
    join {{ ref('dim_date') }} d on d.date_sk = f.date_sk
    where j.order_status = 'delivered'
    group by d.month_start_date
) i on i.month_start_date = o.month_start_date
join (
    select d.month_start_date, sum(s.revenue) as g
    from {{ ref('fact_daily_sales') }} s join {{ ref('dim_date') }} d on d.date_sk = s.date_sk
    where s.is_actual
    group by d.month_start_date
) s on s.month_start_date = o.month_start_date
left join {{ ref('rpt_revenue_monthly') }} m on m.month_start_date = o.month_start_date
where m.month_start_date is null
   or m.n <> o.n or m.c <> o.c or m.q <> i.q
   or {{ differs('m.r', 'o.r') }} or {{ differs('m.r_day26_plus', 'i.r26') }} or {{ differs('m.g', 's.g') }}
union all
select 'so thang doi soat = so thang reporting', count(*)
from (select count(distinct d.month_start_date) k from {{ ref('fact_daily_sales') }} s
      join {{ ref('dim_date') }} d on d.date_sk = s.date_sk where s.is_actual) a
cross join (select count(*) k from {{ ref('rpt_revenue_monthly') }}) b
where a.k <> b.k
union all
-- Đối soát độc lập theo NĂM (C năm không suy ra được từ C tháng)
select 'nam khop nguon doc lap (N, C, R, G)', count(*)
from (
    select d.year, count(*) as n, count(distinct o.customer_sk) as c,
           sum(cast(p.payment_value as decimal(18, 2))) as r
    from {{ ref('fact_order') }} o
    join {{ ref('dim_order_junk') }} j on j.order_junk_sk = o.order_junk_sk
    join {{ ref('dim_date') }} d on d.date_sk = o.order_date_sk
    join {{ ref('stg_payments') }} p on p.order_id = o.order_id
    where j.order_status = 'delivered'
    group by d.year
) o
join (
    select d.year, sum(s.revenue) as g
    from {{ ref('fact_daily_sales') }} s join {{ ref('dim_date') }} d on d.date_sk = s.date_sk
    where s.is_actual group by d.year
) s on s.year = o.year
left join {{ ref('rpt_revenue_yearly') }} y on y.year = o.year
where y.year is null or y.n <> o.n or y.c <> o.c or {{ differs('y.r', 'o.r') }} or {{ differs('y.g', 's.g') }}
union all
select 'moi don delivered co dung 1 dong payments', count(*)
from {{ ref('fact_order') }} o
join {{ ref('dim_order_junk') }} j on j.order_junk_sk = o.order_junk_sk
left join (select order_id, count(*) k from {{ ref('stg_payments') }} group by order_id) p on p.order_id = o.order_id
where j.order_status = 'delivered' and (p.order_id is null or p.k <> 1)
) checks
where n > 0
