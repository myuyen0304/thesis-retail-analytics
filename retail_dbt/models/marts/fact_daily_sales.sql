-- Aggregate fact, grain = 1 ngày. Phần thực tế TÍNH từ fact_order_item — không nạp sales.csv
-- (sales.csv chỉ dùng để đối soát: test assert_daily_sales_matches_source, CLAUDE.md §5 điểm 1).
-- 548 dòng vùng dự báo lấy từ sample_submission, cờ is_actual = false.
select
    date_sk,
    cast(sum(gross_amount) as decimal(18, 2))      as revenue,   -- gross, KHÔNG trừ discount
    cast(round(cast(sum(cogs_amount) as decimal(38, 8)), 2) as decimal(18, 2)) as cogs,  -- làm tròn 2 chữ số như sales.csv
    true                                           as is_actual
from {{ ref('fact_order_item') }}
group by date_sk

union all

select
    {{ date_sk('sales_date') }},
    revenue,
    cogs,
    false
from {{ ref('stg_sample_submission') }}
