select
    cast({{ clean('customer_id') }} as integer) as customer_id,
    cast({{ clean('zip') }} as integer) as zip,
    {{ clean('city') }} as city,                                 -- bản sao geography.city, loại ở marts
    cast({{ clean('signup_date') }} as date) as signup_date,     -- KHÔNG đáng tin (star_schema.md §6 mục 2)
    {{ clean('gender') }} as gender,
    {{ clean('age_group') }} as age_group,
    {{ clean('acquisition_channel') }} as acquisition_channel
from {{ source('raw', 'customers') }}
