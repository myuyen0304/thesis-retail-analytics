{{ config(enabled=extension_enabled('shipments_realistic')) }}
-- Đối chiếu nguồn trực tiếp; không giả định công thức đánh số khóa thay thế.
with expected as (
    select cast(order_id as integer) as order_id, {{ clean('shipper_id') }} as shipper_id
    from {{ source('raw', 'shipments_realistic') }}
), f as (select * from {{ ref('fact_order') }})
select 'so_don' as rule where (select count(*) from f) <> (select count(*) from {{ ref('int_orders') }})
union all
select 'khoa_don' from f group by order_id having count(*) <> 1
union all
select 'gan_shipper' from f
left join expected e on e.order_id = f.order_id
left join {{ ref('dim_shipper') }} d on d.shipper_sk = f.shipper_sk
where e.shipper_id is distinct from d.shipper_id
   or (e.shipper_id is null and f.shipper_sk is not null)
   or (e.shipper_id is not null and f.shipper_sk is null)
