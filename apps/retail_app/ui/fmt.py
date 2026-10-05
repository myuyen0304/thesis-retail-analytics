"""Định dạng số kiểu Việt: dấu chấm ngăn nghìn, dấu phẩy thập phân (1.234,5). Chỉ định dạng, không tính toán."""
import math

import pandas as pd


def _missing(x) -> bool:
    return x is None or x is pd.NA or (isinstance(x, float) and math.isnan(x))


def num(x, decimals: int = 0, signed: bool = False) -> str:
    if _missing(x):
        return '–'
    s = f'{x:+,.{decimals}f}' if signed else f'{x:,.{decimals}f}'
    return s.replace(',', '_').replace('.', ',').replace('_', '.').replace('-', '−')


def pct(x, decimals: int = 1, signed: bool = False) -> str:
    """Tỷ lệ (0,762) → '76,2%'."""
    if _missing(x):
        return '–'
    return num(x * 100, decimals, signed) + '%'


def pp(x, decimals: int = 1) -> str:
    """Chênh hai tỷ lệ (0,003) → '+0,3 điểm %'."""
    if _missing(x):
        return '–'
    return num(x * 100, decimals, signed=True) + ' điểm %'


def ty(x, decimals: int = 2, signed: bool = False) -> str:
    """Số tiền lớn (16.430.476.585,53) → '16,43 tỷ'. Dùng cho nhãn biểu đồ; số đầy đủ dùng num(x, 2)."""
    if _missing(x):
        return '–'
    return num(x / 1e9, decimals, signed) + ' tỷ'


def trieu(x, decimals: int = 1, signed: bool = False) -> str:
    """Số tiền cỡ trăm triệu (−572.400.000) → '−572,4 triệu'. Dùng cho phần góp PS4/PS5."""
    if _missing(x):
        return '–'
    return num(x / 1e6, decimals, signed) + ' triệu'


# Nhãn trục Altair/Vega: d3-format mặc định kiểu Mỹ (1,234.5) nên đổi dấu bằng biểu thức Vega
AXIS_TY = "replace(format(datum.value / 1e9, '.1f'), '.', ',') + ' tỷ'"
AXIS_TRIEU = "format(datum.value / 1e6, '.0f') + ' triệu'"       # số theo tháng (vài trăm triệu): 1 chữ số thập phân tỷ sẽ lặp nhãn
AXIS_PCT1 = "replace(format(datum.value * 100, '.1f'), '.', ',') + '%'"   # tỷ lệ dao động hẹp (tỷ lệ hủy 9,0–9,6%)
