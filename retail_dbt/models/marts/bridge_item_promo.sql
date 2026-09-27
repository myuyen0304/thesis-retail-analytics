-- Bridge M:N dòng hàng × khuyến mãi: tách nhóm lặp promo_id / promo_id_2 (§5.8).
with pairs as (
    select order_id, line_number, promo_id from {{ ref('int_order_lines') }} where promo_id is not null
    union all
    select order_id, line_number, promo_id_2 from {{ ref('int_order_lines') }} where promo_id_2 is not null
)
select
    f.order_item_sk,
    d.promotion_sk
from pairs p
join {{ ref('fact_order_item') }} f on f.order_id = p.order_id and f.line_number = p.line_number
join {{ ref('dim_promotion') }} d on d.promo_id = p.promo_id
