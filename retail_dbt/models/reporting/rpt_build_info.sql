-- Dải thông tin chung của app (docs/gd2_app_plan.md §3, tiêu chí 3): 1 dòng.
-- built_at_utc = lúc lệnh dbt build/run bắt đầu (giờ UTC, không kèm múi giờ để hai backend cùng kiểu).
-- Cột này khác nhau giữa các lần build và giữa hai backend; test so hai backend bỏ riêng cột này.
select
    cast('{{ run_started_at.strftime("%Y-%m-%d %H:%M:%S") }}' as timestamp) as built_at_utc,
    min(order_date)   as data_start_date,       -- đơn đầu tiên
    max(order_date)   as data_end_date,         -- đơn cuối cùng = lúc trích dữ liệu (trạng thái đơn chốt ở đây)
    2013              as analysis_start_year,   -- slide 3: phân tích 10 năm đủ 2013–2022
    2022              as analysis_end_year,
    2014              as growth_start_year      -- tăng trưởng năm tính từ 2014
from {{ ref('int_reporting_order_items') }}
