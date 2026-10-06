select * from (
-- Phụ thuộc hàm quyết định thiết kế dimension (star_schema.md §5.4, §5.6; normalized_schema.md §4).
select 'city -> region' as fd, count(*) as n
from (select city from {{ ref('stg_geography') }} group by city having count(distinct region) > 1) x
union all
select 'district -> region', count(*)
from (select district from {{ ref('stg_geography') }} group by district having count(distinct region) > 1) x
union all
select 'review_title -> rating', count(*)
from (select review_title from {{ ref('stg_reviews') }} group by review_title having count(distinct rating) > 1) x
union all
select 'product_name -> category, segment', count(*)
from (select product_name from {{ ref('stg_products') }} group by product_name
      having count(distinct category) > 1 or count(distinct segment) > 1) x
) checks
where n > 0
