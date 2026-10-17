"""Đọc kho dự báo cho trang Dự báo (B3b, docs/ke_hoach_ai_gd2.md; hợp đồng docs/hop_dong_du_bao.md §2.2, §6–§8).

Tách khỏi queries.py vì `reporting.rpt_forecast_*` là bảng TÙY CHỌN: chỉ có trong bản dữ liệu do pipeline dựng từ B2b
(chế độ versioned). Chế độ cũ, PostgreSQL và bản trước B2b không có. queries.SOURCE phải có ở mọi backend và trùng
`app_read_relations` của dbt, nên các bảng này không nằm ở đó (giống OPTIONAL_RELATIONS của chat, ai_explain/tools.py).

`rpt_forecast_actual` (số thực tế G, COGS theo ngày) có từ bản dựng sau 2026-10-15; bản B2b đầu tiên có dự báo nhưng
chưa có bảng này, trang khi đó chỉ vẽ phần dự báo.
"""
import pandas as pd

from dwh.connection import read_sql

SOURCE = {
    'forecast_daily': 'reporting.rpt_forecast_daily',
    'forecast_backtest': 'reporting.rpt_forecast_backtest',
    'actual_daily': 'reporting.rpt_forecast_actual',
}
ACTUAL_FROM = '2021-01-01'      # số thực tế vẽ nối với dự báo: 2021–2022 (giao việc B3b)


def forecast_daily(backend: str) -> pd.DataFrame:
    # chỉ ứng viên chính: luật chọn chạy trong pipeline (Q8), trang không tự chọn
    return read_sql('select * from reporting.rpt_forecast_daily where is_primary order by forecast_date', backend)


def forecast_backtest(backend: str) -> pd.DataFrame:
    return read_sql('select * from reporting.rpt_forecast_backtest order by model, cogs_method, metric, fold_origin',
                    backend)


def actual_daily(backend: str) -> pd.DataFrame:
    # G = doanh thu gộp, gồm cả đơn hủy (= sales.csv), cùng bản dữ liệu với dự báo
    return read_sql('select sale_date, g, cogs from reporting.rpt_forecast_actual '
                    f"where sale_date >= date '{ACTUAL_FROM}' order by sale_date", backend)
