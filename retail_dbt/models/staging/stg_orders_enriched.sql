{{ config(enabled=extension_enabled('orders_enriched')) }}
-- Một dòng mỗi đơn được nhận; giữ dấu vết và các cột chỉ được hiện ở silver.
select
    cast({{ clean('order_id') }} as integer) as order_id,
    {{ clean('sales_employee_id') }} as sales_employee_id,
    {{ clean('sales_employee_name') }} as sales_employee_name,
    {{ clean('marital_status') }} as marital_status,
    {{ clean('education_level') }} as education_level,
    cast({{ clean('years_experience') }} as integer) as years_experience,
    {{ clean('comment') }} as comment,
    _src_row,
    _dong_goc
from {{ source('raw', 'orders_enriched') }}
