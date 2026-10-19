{{ config(enabled=var('forecast_path', '') != '') }}
-- B4a: phân rã model chính LightGBM cho log(G) dự báo; không phải nguyên nhân.
-- Một dòng = ngày dự báo × nhóm biến. base_log + tổng contribution_log = ln(yhat).
-- multiplier = exp(contribution_log) là hệ số nhân riêng, không cộng các multiplier hoặc %.
select
    cast(forecast_date as date)                as forecast_date,
    cast(model as varchar(32))                 as model,
    cast(cogs_method as varchar(16))           as cogs_method,
    cast(model_version as varchar(32))         as model_version,
    cast(run_id as varchar(100))               as run_id,
    cast(trained_through as date)              as trained_through,
    cast(feature_group as varchar(100))        as feature_group,
    cast(expected_groups as integer)            as expected_groups,
    cast(base_log as {{ type_double() }})      as base_log,
    cast(contribution_log as {{ type_double() }}) as contribution_log,
    cast(forecast_log as {{ type_double() }})  as forecast_log,
    cast(multiplier as {{ type_double() }})    as multiplier
from {{ source('forecast', 'forecast_explain') }}
