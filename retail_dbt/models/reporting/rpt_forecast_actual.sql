{{ config(enabled=var('forecast_path', '') != '') }}
-- Số THỰC TẾ G và COGS theo ngày để trang Dự báo vẽ cạnh dự báo (B3b, docs/hop_dong_du_bao.md §2.1, §7).
-- Dựng cùng bản dữ liệu và cùng điều kiện với rpt_forecast_daily (var forecast_path), nên trang không phải đọc marts.
-- G = doanh thu gộp, gồm cả đơn hủy (= sales.csv, CLAUDE.md §5.1); không phải R của PS1–PS5.
-- Chỉ phần is_actual: 548 dòng vùng dự báo của fact_daily_sales là bản chép sample_submission, không phải số thật.
select
    d.full_date      as sale_date,
    f.revenue        as g,
    f.cogs           as cogs
from {{ ref('fact_daily_sales') }} f
join {{ ref('dim_date') }} d on d.date_sk = f.date_sk
where f.is_actual
