-- Cả 540 tổ hợp junk đều có đơn dùng (§5.5) — dấu hiệu dữ liệu sinh tổng hợp, và xác nhận tích Descartes đúng.
select j.*
from {{ ref('dim_order_junk') }} j
where not exists (select 1 from {{ ref('fact_order') }} o where o.order_junk_sk = j.order_junk_sk)
