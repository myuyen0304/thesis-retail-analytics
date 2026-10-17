{{ config(enabled=var('forecast_path', '') != '') }}
-- Điểm backtest của mọi mốc và ứng viên dự báo, theo fold × chỉ số (docs/hop_dong_du_bao.md §5, §7).
-- role: floor = mốc sàn (seasonal naive 2 năm), baseline = mốc khác, candidate = ứng viên được xét trong luật chọn.
-- candidate_rank: thứ tự đơn giản dùng để phá hòa (nhỏ = đơn giản hơn), lấy từ scripts/forecast/core.py RANK.
-- Đây là sai số trên số quá khứ 2020–2022, không phải độ chính xác của dự báo 2023–2024.
select
    cast(model as varchar(32))                         as model,
    cast(cogs_method as varchar(16))                   as cogs_method,
    cast(role as varchar(16))                          as role,
    cast(candidate_rank as integer)                    as candidate_rank,
    cast(fold_origin as date)                          as fold_origin,
    cast(metric as varchar(32))                        as metric,
    cast(grain as varchar(16))                         as grain,
    cast(value as {{ type_double() }})                 as value
from {{ source('forecast', 'forecast_backtest') }}
