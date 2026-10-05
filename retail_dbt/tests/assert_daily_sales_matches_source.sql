-- CLAUDE.md §5 điểm 1: sales.csv tái tạo CHÍNH XÁC từ giao dịch (gross, mọi trạng thái đơn).
-- Kho phải giữ tính chất này: 3.833/3.833 ngày, khớp tuyệt đối 2 chữ số, không thừa không thiếu ngày.
select coalesce(f.date_sk, {{ date_sk('s.sales_date') }}) as date_sk,
       f.revenue, s.revenue as src_revenue, f.cogs, s.cogs as src_cogs
from (select * from {{ ref('fact_daily_sales') }} where is_actual) f
full outer join {{ ref('stg_sales') }} s on f.date_sk = {{ date_sk('s.sales_date') }}
where f.date_sk is null or s.sales_date is null
   or f.revenue <> s.revenue or f.cogs <> s.cogs
