-- Bật/tắt bằng config trong tests/_singular_tests.yml: chỉ chạy khi pipeline truyền var forecast_path.
-- rpt_forecast_actual đối chứng THẲNG stg_sales (sales.csv), không qua fact_daily_sales mà model đọc; số thực tế phải
-- dừng đúng ngày model dự báo train tới, và dự báo bắt đầu ngay ngày hôm sau. Trả về quy tắc bị vi phạm và số dòng.
with a as (select * from {{ ref('rpt_forecast_actual') }}),
d as (select * from {{ ref('rpt_forecast_daily') }}),
moc as (
    select (select max(sale_date) from a)         as cuoi_thuc_te,
           (select min(trained_through) from d)   as tt_min,
           (select max(trained_through) from d)   as tt_max,
           (select min(forecast_date) from d)     as dau_du_bao
)
select * from (
select 'rpt_forecast_actual khop sales.csv tung ngay (G, COGS, du ngay, khong thua)' as rule, count(*) as n
from a
full outer join {{ ref('stg_sales') }} s on s.sales_date = a.sale_date
where a.sale_date is null or s.sales_date is null or a.g <> s.revenue or a.cogs <> s.cogs
union all
select 'rpt_forecast_actual: moi ngay mot dong, khong null', count(*)
from (
    select sale_date, count(*) as k, sum(case when g is null or cogs is null then 1 else 0 end) as n_null
    from a group by sale_date
) t
where k > 1 or n_null > 0 or sale_date is null
union all
select 'so thuc te dung o trained_through; du bao bat dau ngay hom sau', count(*)
from moc
where cuoi_thuc_te is null or tt_min <> tt_max or cuoi_thuc_te <> tt_max
   or dau_du_bao <> cast({{ dbt.dateadd('day', 1, 'cuoi_thuc_te') }} as date)
) checks
where n > 0
