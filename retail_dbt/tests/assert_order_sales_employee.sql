{{ config(enabled=extension_enabled('orders_enriched')) }}
-- T3: truy ngược khóa fact qua dim để so mã tự nhiên theo từng đơn.
with f as (select * from {{ ref('fact_order') }}),
s as (select * from {{ ref('stg_orders_enriched') }}),
d as (select * from {{ ref('dim_sales_employee') }})
select 'so_don_co_nhan_vien' as rule
where (select count(*) from f where sales_employee_sk is not null) <>
      (select count(*) from s join f on s.order_id = f.order_id)
union all
select 'khoa_mo_coi' from f left join d on f.sales_employee_sk = d.sales_employee_sk
where f.sales_employee_sk is not null and d.sales_employee_sk is null
union all
select 'sai_nhan_vien' from f
left join d on f.sales_employee_sk = d.sales_employee_sk
left join s on f.order_id = s.order_id
where d.sales_employee_id is distinct from s.sales_employee_id
