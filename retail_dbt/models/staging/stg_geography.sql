select
    cast({{ clean('zip') }} as integer) as zip,
    {{ clean('city') }} as city,
    {{ clean('district') }} as district,
    {{ clean('region') }} as region
from {{ source('raw', 'geography') }}
