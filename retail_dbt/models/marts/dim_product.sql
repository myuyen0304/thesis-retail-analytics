-- SCD Type 1: price/cogs là giá HIỆN TẠI; giá lúc bán nằm ở fact_order_item.unit_price (§5.7).
select
    cast(row_number() over (order by product_id) as integer) as product_sk,
    product_id,
    product_name,                  -- KHÔNG unique
    category,
    segment,
    size,
    color,
    price       as current_price,
    cogs        as current_cogs,
    price < 100 as price_anomaly   -- cờ chất lượng dữ liệu, KHÔNG dùng để GROUP BY (§6 mục 1)
from {{ ref('stg_products') }}
