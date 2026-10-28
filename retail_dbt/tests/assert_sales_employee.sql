{{ config(enabled=extension_enabled('orders_enriched')) }}
-- T2: khóa và bộ thuộc tính kiểm độc lập với cách đánh số khóa thay thế.
with s as (
    select sales_employee_id, sales_employee_name, years_experience
    from {{ ref('stg_orders_enriched') }}
    group by sales_employee_id, sales_employee_name, years_experience
), d as (select * from {{ ref('dim_sales_employee') }})
select 'khoa_thay_the' as rule from d group by sales_employee_sk having sales_employee_sk is null or count(*) <> 1
union all
select 'khoa_tu_nhien' from d group by sales_employee_id having sales_employee_id is null or count(*) <> 1
union all
select 'phu_thuoc_ham' from s group by sales_employee_id having count(*) <> 1
union all
select 'so_nhan_vien' where (select count(*) from d) <>
    (select count(distinct sales_employee_id) from {{ ref('stg_orders_enriched') }})
union all
select 'thuoc_tinh' from s full outer join d on s.sales_employee_id = d.sales_employee_id
where s.sales_employee_id is null or d.sales_employee_id is null
   or s.sales_employee_name is distinct from d.sales_employee_name
   or s.years_experience is distinct from d.years_experience
