{{ config(enabled=extension_enabled('orders_enriched')) }}
-- SCD Type 1. Giữ mọi bộ thuộc tính khác nhau để test phát hiện id mâu thuẫn.
with employees as (
    select sales_employee_id, sales_employee_name, years_experience
    from {{ ref('stg_orders_enriched') }}
    group by sales_employee_id, sales_employee_name, years_experience
)
select
    cast(row_number() over (order by sales_employee_id) as integer) as sales_employee_sk,
    sales_employee_id,
    sales_employee_name,
    years_experience
from employees
