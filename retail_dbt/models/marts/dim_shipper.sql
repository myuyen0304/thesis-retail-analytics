{{ config(enabled=extension_enabled('shipments_realistic')) }}
-- Type 1: bộ thuộc tính hiện tại; không suy kinh nghiệm ở thời điểm giao.
with shippers as (
    select shipper_id, shipper_company, shipper_vehicle, shipper_experience_years, shipper_rating, delivery_success_rate, average_delivery_time, working_shift, join_date, shipper_name, shipper_phone, city, region, district
    from {{ ref('stg_shipments_realistic') }}
    group by shipper_id, shipper_company, shipper_vehicle, shipper_experience_years, shipper_rating, delivery_success_rate, average_delivery_time, working_shift, join_date, shipper_name, shipper_phone, city, region, district
)
select
    cast(row_number() over (order by shipper_id) as integer) as shipper_sk,
    shipper_id,
    shipper_company,
    shipper_vehicle,
    shipper_experience_years,
    shipper_rating,
    delivery_success_rate,
    average_delivery_time,
    working_shift,
    join_date,
    shipper_name,
    shipper_phone,
    city,
    region,
    district
from shippers
