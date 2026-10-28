{{ config(enabled=extension_enabled('orders_enriched')) }}
-- T4: phần thiếu nhân viên phải đúng bằng phần đơn không được nhận.
select 'so_don_thieu_nhan_vien' as rule
where (select count(*) from {{ ref('fact_order') }} where sales_employee_sk is null) <>
      (select count(*) from {{ ref('stg_orders') }} o where not exists (
          select 1 from {{ ref('stg_orders_enriched') }} s where s.order_id = o.order_id))
