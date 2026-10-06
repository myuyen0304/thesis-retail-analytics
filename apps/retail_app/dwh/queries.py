"""Mỗi hàm = một câu SELECT từ một bảng reporting.rpt_*. Không tính toán (docs/gd2_app_plan.md §2).

Thiếu KPI nào thì thêm model + test trong retail_dbt/, không vá ở đây.
"""
import pandas as pd

from dwh.connection import read_sql

# hàm → bảng nguồn, để app ghi rõ số đọc từ đâu
SOURCE = {
    'build_info': 'reporting.rpt_build_info',
    'revenue_total': 'reporting.rpt_revenue_total',
    'revenue_bridge': 'reporting.rpt_revenue_bridge',
    'revenue_yearly': 'reporting.rpt_revenue_yearly',
    'revenue_monthly': 'reporting.rpt_revenue_monthly',
    'revenue_phase': 'reporting.rpt_revenue_phase',
    'revenue_turning_point': 'reporting.rpt_revenue_turning_point',
    'august_parity': 'reporting.rpt_august_parity',
    'direction_change': 'reporting.rpt_revenue_direction_change',
    'direction_rule': 'reporting.ps2_direction_rule',
    'calendar_phase': 'reporting.rpt_calendar_phase',
    'calendar_phase_month': 'reporting.rpt_calendar_phase_month',
    'calendar_stability': 'reporting.rpt_calendar_stability',
    'driver_period': 'reporting.rpt_driver_period',
    'driver_bridge': 'reporting.rpt_driver_bridge',
    'driver_rule': 'reporting.driver_rule',
    'segment_yearly': 'reporting.rpt_revenue_segment_yearly',
    'health_summary': 'reporting.rpt_health_summary',
    'health_test': 'reporting.rpt_health_test',
    'health_ingest': 'reporting.rpt_health_ingest',
    'health_run': 'reporting.rpt_health_run',
}


def build_info(backend: str) -> pd.DataFrame:
    return read_sql('select * from reporting.rpt_build_info', backend)


def revenue_total(backend: str) -> pd.DataFrame:
    return read_sql('select * from reporting.rpt_revenue_total order by start_year', backend)


def revenue_bridge(backend: str) -> pd.DataFrame:
    # kỳ gộp trước (period_type 'total' < 'year'), rồi từng năm; trong mỗi kỳ theo thứ tự bước
    return read_sql('select * from reporting.rpt_revenue_bridge order by period_type, period_code, step_order', backend)


def revenue_yearly(backend: str) -> pd.DataFrame:
    return read_sql('select * from reporting.rpt_revenue_yearly order by year', backend)


def revenue_monthly(backend: str) -> pd.DataFrame:
    return read_sql('select * from reporting.rpt_revenue_monthly order by month_start_date', backend)


def revenue_phase(backend: str) -> pd.DataFrame:
    return read_sql('select * from reporting.rpt_revenue_phase order by start_year', backend)


def revenue_turning_point(backend: str) -> pd.DataFrame:
    return read_sql('select * from reporting.rpt_revenue_turning_point order by turning_year', backend)


def august_parity(backend: str) -> pd.DataFrame:
    return read_sql('select * from reporting.rpt_august_parity', backend)


def direction_change(backend: str) -> pd.DataFrame:
    return read_sql('select * from reporting.rpt_revenue_direction_change order by window_months, change_month_date', backend)


def direction_rule(backend: str) -> pd.DataFrame:
    return read_sql('select * from reporting.ps2_direction_rule order by window_months', backend)


def calendar_phase(backend: str) -> pd.DataFrame:
    return read_sql('select * from reporting.rpt_calendar_phase order by first_year', backend)


def calendar_phase_month(backend: str) -> pd.DataFrame:
    return read_sql('select * from reporting.rpt_calendar_phase_month order by first_year, month', backend)


def calendar_stability(backend: str) -> pd.DataFrame:
    return read_sql('select * from reporting.rpt_calendar_stability order by rhythm_order', backend)

def driver_period(backend: str) -> pd.DataFrame:
    # giai đoạn trước (period_type 'phase' < 'year'), rồi từng năm
    return read_sql('select * from reporting.rpt_driver_period order by period_type, start_year', backend)


def driver_bridge(backend: str) -> pd.DataFrame:
    return read_sql('select * from reporting.rpt_driver_bridge order by period_type, period_code, bridge_code, step_order',
                    backend)


def driver_rule(backend: str) -> pd.DataFrame:
    return read_sql('select * from reporting.driver_rule', backend)


def segment_yearly(backend: str) -> pd.DataFrame:
    return read_sql('select * from reporting.rpt_revenue_segment_yearly '
                    'order by dimension_name, year, delta_r_rank, dimension_value', backend)


# --- Sức khỏe dữ liệu (M5): view trên nhật ký chạy dbt (schema ops) và log nạp nguồn của chính kho đang đọc ---

def health_summary(backend: str) -> pd.DataFrame:
    return read_sql('select * from reporting.rpt_health_summary', backend)


def health_test(backend: str) -> pd.DataFrame:
    # lỗi lên đầu, rồi test nghiệp vụ trước test ràng buộc
    return read_sql('select * from reporting.rpt_health_test order by status_order, test_group, layer, tested_model, '
                    'test_name', backend)


def health_ingest(backend: str) -> pd.DataFrame:
    return read_sql('select * from reporting.rpt_health_ingest order by source', backend)


def health_run(backend: str) -> pd.DataFrame:
    return read_sql('select * from reporting.rpt_health_run order by started_at_utc desc limit 10', backend)
