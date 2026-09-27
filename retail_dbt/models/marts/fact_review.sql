-- Transaction fact, trỏ vào DÒNG HÀNG. Giữ rating (measure gộp được), bỏ review_title (§5.6).
select
    r.review_id,
    f.order_item_sk,
    {{ date_sk('r.review_date') }} as date_sk,
    r.rating
from {{ ref('int_reviews') }} r
join {{ ref('fact_order_item') }} f on f.order_id = r.order_id and f.line_number = r.line_number
