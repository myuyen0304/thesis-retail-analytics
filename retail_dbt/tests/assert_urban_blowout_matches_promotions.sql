-- Cờ is_urban_blowout sinh bằng quy tắc lịch phải trùng đúng các ngày của promo "Urban Blowout" 2012–2022.
-- Viết bằng left join, không dùng `cờ <> exists (...)`: Databricks đọc exists( là hàm mảng nên báo lỗi cú pháp.
with promo_days as (
    select distinct d.full_date
    from {{ ref('dim_date') }} d
    join {{ ref('dim_promotion') }} p
      on p.promo_name like 'Urban Blowout%' and d.full_date between p.start_date and p.end_date
)
select d.full_date, d.is_urban_blowout
from {{ ref('dim_date') }} d
left join promo_days u on u.full_date = d.full_date
where d.full_date <= cast('2022-12-31' as date)
  and d.is_urban_blowout <> (u.full_date is not null)
