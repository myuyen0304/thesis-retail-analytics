{{ config(enabled=extension_enabled('shipments_realistic')) }}
with s as (select * from {{ ref('stg_shipments_realistic') }})
select 'so_dong' as rule where (select count(*) from s) <> (select count(*) from {{ source('raw', 'shipments_realistic') }})
union all
select 'khoa_don' from s group by order_id having order_id is null or count(*) <> 1
union all
select 'don_mo_coi' from s where not exists (select 1 from {{ ref('stg_orders') }} o where o.order_id = s.order_id)
union all
select 'so_thu_tu' from s
having count(*) <> count(_src_row) or count(*) <> count(distinct _src_row)
    or min(_src_row) <> 1 or max(_src_row) <> count(*)
