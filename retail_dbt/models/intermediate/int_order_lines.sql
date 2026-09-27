-- Dòng hàng có khóa ổn định (order_id, line_number) theo THỨ TỰ NGUỒN (star_schema.md §5.1):
-- 16 cặp (order_id, product_id) trùng nên khóa tự nhiên không dùng được.
-- product_occurrence: lần thứ mấy sản phẩm xuất hiện trong đơn — dùng để map returns/reviews.
select
    order_id,
    row_number() over (partition by order_id order by src_row)             as line_number,
    row_number() over (partition by order_id, product_id order by src_row) as product_occurrence,
    product_id,
    quantity,
    unit_price,
    discount_amount,
    promo_id,
    promo_id_2
from {{ ref('stg_order_items') }}
