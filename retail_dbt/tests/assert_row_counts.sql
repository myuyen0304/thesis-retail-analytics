-- Số dòng 14 bảng star khớp star_schema.md §4/§7. Trả về bảng lệch.
with expected (tbl, n) as (
    select 'dim_date', 4566 union all select 'dim_geography', 39948 union all select 'dim_customer', 121930
    union all select 'dim_product', 2412 union all select 'dim_promotion', {{ 50 + dot_so_dong('promotions') }} union all select 'dim_order_junk', 540
    union all select 'fact_order_item', {{ 714669 + dot_so_dong('order_items') }} union all select 'fact_order', {{ 646945 + dot_so_dong('orders') }}
    union all select 'fact_daily_sales', 4381 union all select 'fact_inventory_snapshot', {{ 60247 + dot_so_dong('inventory') }}
    union all select 'fact_return', {{ 39939 + dot_so_dong('returns') }} union all select 'fact_review', {{ 113551 + dot_so_dong('reviews') }}
    union all select 'bridge_item_promo', {% if co_dot() %}(select sum(case when promo_id is not null then 1 else 0 end) + sum(case when promo_id_2 is not null then 1 else 0 end) from {{ ref('stg_order_items') }}){% else %}276522{% endif %} union all select 'fact_web_traffic', {{ 3652 + dot_so_dong('web_traffic') }}
),
actual as (
    {%- set tbls = ['dim_date', 'dim_geography', 'dim_customer', 'dim_product', 'dim_promotion', 'dim_order_junk',
                    'fact_order_item', 'fact_order', 'fact_daily_sales', 'fact_inventory_snapshot', 'fact_return',
                    'fact_review', 'bridge_item_promo', 'fact_web_traffic'] %}
    {%- for t in tbls %}
    select '{{ t }}' as tbl, count(*) as n from {{ ref(t) }}{% if not loop.last %} union all{% endif %}
    {%- endfor %}
)
select e.tbl, e.n as expected, a.n as actual
from expected e left join actual a on a.tbl = e.tbl
where a.n is null or a.n <> e.n
