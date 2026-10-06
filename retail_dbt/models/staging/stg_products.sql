select
    cast({{ clean('product_id') }} as integer) as product_id,
    {{ clean('product_name') }} as product_name,
    {{ clean('category') }} as category,
    {{ clean('segment') }} as segment,
    {{ clean('size') }} as size,
    {{ clean('color') }} as color,
    cast({{ clean('price') }} as {{ type_double() }}) as price,  -- số thực thật (vd 15291.061153846153), không ép DECIMAL
    cast({{ clean('cogs') }} as {{ type_double() }}) as cogs
from {{ source('raw', 'products') }}
