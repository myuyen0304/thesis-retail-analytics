{{ config(enabled=var('forecast_path', '') != '') }}
-- Dự báo G và COGS theo ngày × ứng viên của bản dữ liệu (docs/hop_dong_du_bao.md §7).
-- Nguồn: stage dự báo của pipeline (scripts/forecast/stage.py), cùng code với notebooks/04_forecasting/so_sanh_model.ipynb.
-- Số DỰ BÁO, không phải số thực tế. G = doanh thu gộp, gồm cả đơn hủy (không so trực tiếp với R của PS1–PS5).
-- Đúng một ứng viên is_primary: luật chọn của hợp đồng §5 chọn, test assert_rpt_forecast tính lại để kiểm.
select
    cast(forecast_date as date)                        as forecast_date,
    cast(model as varchar(32))                         as model,
    cast(cogs_method as varchar(16))                   as cogs_method,
    cast(model_version as varchar(32))                 as model_version,
    cast(run_id as varchar(100))                       as run_id,
    cast(trained_through as date)                      as trained_through,
    cast(is_primary as boolean)                        as is_primary,
    cast(selection_step as varchar(64))                as selection_step,
    cast(yhat as {{ type_double() }})                  as yhat,
    cast(lower as {{ type_double() }})                 as lower,
    cast(upper as {{ type_double() }})                 as upper,
    cast(interval_level as {{ type_double() }})        as interval_level,
    cast(cogs_ratio_hat as {{ type_double() }})        as cogs_ratio_hat,
    cast(cogs_yhat as {{ type_double() }})             as cogs_yhat
from {{ source('forecast', 'forecast_daily') }}
