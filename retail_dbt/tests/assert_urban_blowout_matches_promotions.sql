-- Cờ is_urban_blowout sinh bằng quy tắc lịch phải trùng đúng các ngày của promo "Urban Blowout" 2012–2022.
select d.full_date, d.is_urban_blowout
from {{ ref('dim_date') }} d
where d.full_date <= cast('2022-12-31' as date)
  and d.is_urban_blowout <> exists (
        select 1 from {{ ref('dim_promotion') }} p
        where p.promo_name like 'Urban Blowout%' and d.full_date between p.start_date and p.end_date)
