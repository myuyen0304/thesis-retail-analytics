-- Phẳng ở grain = zip: city và district cắt chéo nhau, không có cây snowflake (star_schema.md §5.4).
select
    cast(row_number() over (order by zip) as integer) as geography_sk,
    zip,
    city,
    district,
    region
from {{ ref('stg_geography') }}
