{{ config(enabled=extension_enabled('orders_enriched')) }}
-- T1: bảo toàn dòng, khóa nối và dãy số dòng nguồn.
with s as (select * from {{ ref('stg_orders_enriched') }})
select 'so_dong' as rule where (select count(*) from s) <> (select count(*) from {{ source('raw', 'orders_enriched') }})
union all
select 'khoa_don' from s group by order_id having order_id is null or count(*) <> 1
union all
select 'don_mo_coi' from s where not exists (select 1 from {{ ref('stg_orders') }} o where o.order_id = s.order_id)
union all
select 'so_thu_tu' from s
having count(*) <> count(_src_row) or count(*) <> count(distinct _src_row)
    or min(_src_row) <> 1 or max(_src_row) <> count(*)
