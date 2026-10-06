-- Đánh giá trỏ vào DÒNG HÀNG (cùng cách map với int_returns).
-- Giữ rating (measure), bỏ review_title: FD review_title -> rating (star_schema.md §5.6).
with r as (
    select *,
           row_number() over (partition by order_id, product_id order by src_row) as product_occurrence
    from {{ ref('stg_reviews') }}
)
select
    r.review_id,
    r.order_id,
    l.line_number,
    r.review_date,
    r.rating
from r
left join {{ ref('int_order_lines') }} l
    on l.order_id = r.order_id
   and l.product_id = r.product_id
   and l.product_occurrence = r.product_occurrence
