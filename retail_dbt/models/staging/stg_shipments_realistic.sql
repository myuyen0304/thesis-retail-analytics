{{ config(enabled=extension_enabled('shipments_realistic')) }}
-- Một dòng mỗi đơn được nhận; giữ thuộc tính silver và dấu vết nguồn.
select
    {{ clean('shipper_id') }} as shipper_id,
    cast({{ clean('order_id') }} as integer) as order_id,
    {{ clean('shipper_company') }} as shipper_company,
    {{ clean('shipper_vehicle') }} as shipper_vehicle,
    cast({{ clean('shipper_experience_years') }} as integer) as shipper_experience_years,
    cast({{ clean('shipper_rating') }} as double) as shipper_rating,
    cast({{ clean('delivery_success_rate') }} as double) as delivery_success_rate,
    cast({{ clean('average_delivery_time') }} as integer) as average_delivery_time,
    {{ clean('working_shift') }} as working_shift,
    cast({{ clean('join_date') }} as date) as join_date,
    {{ clean('shipper_name') }} as shipper_name,
    {{ clean('shipper_phone') }} as shipper_phone,
    {{ clean('shipper_gender') }} as shipper_gender,
    cast({{ clean('shipper_age') }} as integer) as shipper_age,
    {{ clean('shipper_marital_status') }} as shipper_marital_status,
    {{ clean('shipper_education') }} as shipper_education,
    {{ clean('city') }} as city,
    {{ clean('region') }} as region,
    {{ clean('district') }} as district,
    _src_row,
    _dong_goc
from {{ source('raw', 'shipments_realistic') }}
