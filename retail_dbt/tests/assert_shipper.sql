{{ config(enabled=extension_enabled('shipments_realistic')) }}
-- Phụ thuộc hàm kiểm đủ 17 thuộc tính, kể cả thuộc tính chỉ ở silver.
with s as (select shipper_id, shipper_company, shipper_vehicle, shipper_experience_years, shipper_rating, delivery_success_rate, average_delivery_time, working_shift, join_date, shipper_name, shipper_phone, shipper_gender, shipper_age, shipper_marital_status, shipper_education, city, region, district from {{ ref('stg_shipments_realistic') }} group by shipper_id, shipper_company, shipper_vehicle, shipper_experience_years, shipper_rating, delivery_success_rate, average_delivery_time, working_shift, join_date, shipper_name, shipper_phone, shipper_gender, shipper_age, shipper_marital_status, shipper_education, city, region, district),
d as (select * from {{ ref('dim_shipper') }})
select 'khoa_thay_the' as rule from d group by shipper_sk having shipper_sk is null or count(*) <> 1
union all
select 'khoa_tu_nhien' from d group by shipper_id having shipper_id is null or count(*) <> 1
union all
select 'phu_thuoc_ham' from s group by shipper_id having count(*) <> 1
union all
select 'so_shipper' where (select count(*) from d) <> (select count(distinct shipper_id) from s)
union all
select 'thuoc_tinh' from s full outer join d on s.shipper_id = d.shipper_id
where s.shipper_id is null or d.shipper_id is null
   or s.shipper_company is distinct from d.shipper_company
   or s.shipper_vehicle is distinct from d.shipper_vehicle
   or s.shipper_experience_years is distinct from d.shipper_experience_years
   or s.shipper_rating is distinct from d.shipper_rating
   or s.delivery_success_rate is distinct from d.delivery_success_rate
   or s.average_delivery_time is distinct from d.average_delivery_time
   or s.working_shift is distinct from d.working_shift
   or s.join_date is distinct from d.join_date
   or s.shipper_name is distinct from d.shipper_name
   or s.shipper_phone is distinct from d.shipper_phone
   or s.city is distinct from d.city
   or s.region is distinct from d.region
   or s.district is distinct from d.district
