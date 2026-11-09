{{ config(enabled=co_dot()) }}
-- Chỉ bật ở bản có đợt (D3). Số năm mới, vùng dự báo và kỳ gộp mới; hai số khóa kỳ gốc tính lại từ năm, tháng.
{% set moc = var('last_actual_date') %}
select * from (
select 'nam moi: G, COGS tung ngay khop stg_sales, du ngay, khong thua' as rule, count(*) as n
from (
    select date_sk, revenue, cogs from {{ ref('fact_daily_sales') }}
    where is_actual and date_sk > 20221231
) f
full outer join (
    select {{ date_sk('sales_date') }} as date_sk, revenue, cogs from {{ ref('stg_sales') }}
    where sales_date > cast('2022-12-31' as date)
) s on s.date_sk = f.date_sk
where f.date_sk is null or s.date_sk is null or f.revenue <> s.revenue or f.cogs <> s.cogs
union all
select 'moi ngay chi mot dong trong fact_daily_sales', count(*)
from (select date_sk from {{ ref('fact_daily_sales') }} group by date_sk having count(*) > 1) t
union all
select 'dong du bao dung bang ngay sample_submission sau ngay thuc te cuoi', count(*)
from (select date_sk from {{ ref('fact_daily_sales') }} where not is_actual) f
full outer join (
    select {{ date_sk('sales_date') }} as date_sk from {{ ref('stg_sample_submission') }}
    where sales_date > cast('{{ moc }}' as date)
) s on s.date_sk = f.date_sk
where f.date_sk is null or s.date_sk is null
union all
select 'so thuc te dung o ngay thuc te cuoi', count(*)
from (select max(date_sk) as k from {{ ref('fact_daily_sales') }} where is_actual) t
where k <> {{ moc | replace('-', '') }}
union all
select 'is_forecast_period dung khi va chi khi sau ngay thuc te cuoi', count(*)
from {{ ref('dim_date') }}
where is_forecast_period <> (full_date > cast('{{ moc }}' as date))
union all
select 'ky gop moi bang cong cac nam; chi ky moi la ky phan tich', count(*)
from {{ ref('rpt_revenue_total') }} t
cross join (select sum(g) as g, sum(r) as r from {{ ref('rpt_revenue_yearly') }}
            where year between 2013 and {{ ky_cuoi() }}) y
where (t.period_code = '2013-{{ ky_cuoi() }}'
       and (not t.is_analysis_period or {{ differs('t.g', 'y.g') }} or {{ differs('t.r', 'y.r') }}))
   or (t.period_code in ('2012-2022', '2013-2022') and t.is_analysis_period)
union all
select 'du dong ky gop moi', count(*)
from (select count(*) as k from {{ ref('rpt_revenue_total') }} where period_code = '2013-{{ ky_cuoi() }}') t
where k <> 1
union all
select 'giai doan cuoi ket thuc o nam cuoi cua ky; van 4 giai doan', count(*)
from (select count(*) as k, max(end_year) as hi from {{ ref('rpt_revenue_phase') }}) t
where k <> 4 or hi <> {{ ky_cuoi() }}
union all
select 'ky goc: thang 8 nam le so nam chan 2013-2022 van -37,66%', count(*)
from (
    select avg(case when mod(year, 2) = 1 then cast(month_index as {{ type_double() }}) end)
           / avg(case when mod(year, 2) = 0 then cast(month_index as {{ type_double() }}) end) - 1 as ratio
    from {{ ref('rpt_revenue_monthly') }}
    where month = 8 and year between 2013 and 2022
) t
where not (ratio between -0.37661 and -0.37660)
union all
select 'ky goc: CAGR 2019-2022 van -0,14%', count(*)
from (
    select power(cast(max(case when year = 2022 then r end) as {{ type_double() }})
                 / cast(max(case when year = 2019 then r end) as {{ type_double() }}), 1.0 / 3) - 1 as cagr
    from {{ ref('rpt_revenue_yearly') }}
) t
where not (cagr between -0.00145 and -0.00144)
) checks
where n > 0
