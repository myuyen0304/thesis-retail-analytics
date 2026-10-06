-- Không JOIN nào làm rơi dòng: mỗi dòng nguồn sang đúng 1 dòng star; return/review map đủ sang line_number.
select 'order_items -> fact_order_item' as flow
where (select count(*) from {{ ref('stg_order_items') }}) <> (select count(*) from {{ ref('fact_order_item') }})
union all select 'orders -> fact_order'
where (select count(*) from {{ ref('stg_orders') }}) <> (select count(*) from {{ ref('fact_order') }})
union all select 'customers -> dim_customer'
where (select count(*) from {{ ref('stg_customers') }}) <> (select count(*) from {{ ref('dim_customer') }})
union all select 'inventory -> fact_inventory_snapshot'
where (select count(*) from {{ ref('stg_inventory') }}) <> (select count(*) from {{ ref('fact_inventory_snapshot') }})
union all select 'returns: map line_number'
where exists (select 1 from {{ ref('int_returns') }} where line_number is null)
union all select 'reviews: map line_number'
where exists (select 1 from {{ ref('int_reviews') }} where line_number is null)
union all select 'returns -> fact_return'
where (select count(*) from {{ ref('stg_returns') }}) <> (select count(*) from {{ ref('fact_return') }})
union all select 'reviews -> fact_review'
where (select count(*) from {{ ref('stg_reviews') }}) <> (select count(*) from {{ ref('fact_review') }})
