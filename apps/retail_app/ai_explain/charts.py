"""B6 (L2): biểu đồ trong chat, vẽ từ ĐÚNG kết quả tool đã chạy trong lượt (skill retail-ai-explain, agent_levels.md dòng L2).

Mô hình chỉ gọi `show_chart(ref, y, y2?)`: kết quả tool nào (T1, T2...) và cột số nào. App chọn trục x theo tool, lấy dữ liệu
thẳng từ `results[ref].rows` (đã qua evidence của tool đó) và tự viết nhãn. Không có đường nào để mô hình đưa số vào biểu đồ.
Biểu đồ không đọc kho nên không tính vào MAX_TOOL_CALLS; không nằm trong turn.calls / turn.results (giữ số T1, T2... và các
luật "status ok cần tool dữ liệu ok"). Chưa làm: deep link sang trang kèm bộ lọc.
"""
import re
from dataclasses import dataclass
from numbers import Number

import altair as alt
import pandas as pd

from ai_explain import evidence
from ai_explain.contracts import ToolResult

TOOL = 'show_chart'
MAX_CHARTS = 2
MIN_POINTS = 2
SCHEMA = {
    'name': TOOL,
    'description': 'Vẽ biểu đồ từ kết quả tool dữ liệu nhiều dòng đã chạy trong lượt; app lấy số và nhãn.',
    'input_schema': {'type': 'object', 'additionalProperties': False, 'required': ['ref', 'y'], 'properties': {
        'ref': {'type': 'string', 'description': 'vd. T1', 'maxLength': 4},
        'y': {'type': 'string', 'description': 'cột số trong rows, vd. g_forecast', 'maxLength': 40},
        'y2': {'type': 'string', 'description': 'cột thứ hai cùng đơn vị', 'maxLength': 40},
    }},
}
# trục x theo tool; tool không có trong bảng (một dòng: tổng hợp năm, tháng, định nghĩa...) thì không vẽ
X_FIELD = {'get_forecast': 'period', 'get_forecast_backtest': 'candidate_label', 'get_segment_contribution': 'dimension_value',
           'get_revenue_trend': ('phase_name', 'turning_year'), 'get_calendar_pattern': 'period',
           'get_revenue_summary': 'year'}           # chuỗi từng năm (to_year); một năm thì chỉ 1 điểm, không vẽ
# trục x là chuỗi tháng / năm liên tiếp: đường; còn lại (nhóm, ứng viên, giai đoạn, "cả kỳ" cạnh giai đoạn): cột
LINE_TOOLS = {'get_forecast', 'get_revenue_summary'}
# cột số không phải chỉ tiêu (khóa, đếm, năm, cận khoảng): không vẽ làm trục y
NOT_Y = {'year', 'month', 'n_days', 'n_days_in_period', 'candidate_rank', 'n_folds', 'start_year', 'end_year', 'n_years',
         'turning_year', 'peak_month', 'trough_month', 'n_groups', 'n_groups_up', 'n_groups_down', 'n_years_with_pattern',
         'n_odd_years', 'n_even_years', 'typical_month_error', 'lower_g', 'upper_g', 'r_total'}
_UNITS = (('tiền', evidence.MONEY | evidence.PRICE), ('tỷ lệ', evidence.RATE | evidence.PCT100),
          ('điểm %', evidence.PP | evidence.PP_FRAC))


def _unit(fld: str) -> str:
    return next((name for name, s in _UNITS if fld in s), fld)


def _is_value(v) -> bool:
    return isinstance(v, Number) and not isinstance(v, bool)


@dataclass(frozen=True)
class ChartSpec:
    ref: str
    tool: str
    x: str
    y: tuple
    kind: str                     # 'line' | 'bar'
    title: str
    captions: tuple
    excluded: tuple               # nhãn x của dòng KHÔNG vẽ (tháng thiếu ngày, ô trống) — ghi ở chú thích
    band: bool                    # vẽ khoảng 80% (chỉ khi mọi dòng có lower_g / upper_g)
    n_points: int


def _label(row: dict, x: str) -> str | None:
    """Nhãn trục x của một dòng; dòng giai đoạn của get_calendar_pattern không có `period` mà có phase_code + năm."""
    if row.get(x) is not None:
        return str(row[x])
    if row.get('phase_code') is not None:
        a, b = row.get('first_year'), row.get('last_year')
        return f"Giai đoạn {row['phase_code']}" + (f' ({a})' if a == b else f' ({a}–{b})' if a is not None else '')
    return None


def build(args, results: dict, calls: list) -> tuple[ChartSpec | None, ToolResult]:
    """Kiểm lời gọi show_chart với kết quả của CHÍNH lượt này. Trả (spec, kết quả gửi lại mô hình)."""
    def no(status, msg):
        return None, ToolResult(status, msg)
    if not isinstance(args, dict) or set(args) - {'ref', 'y', 'y2'} or not isinstance(args.get('ref'), str) \
            or not isinstance(args.get('y'), str) or ('y2' in args and not isinstance(args['y2'], str)):
        return no('unsupported', 'show_chart chỉ nhận ref (vd. "T1"), y và y2 (tùy chọn) là tên cột.')
    ref = args['ref']
    tool = next((t for r, t, _a in calls if r == ref), None)
    res = results.get(ref)
    if not re.fullmatch(r'T\d+', ref) or res is None or tool is None:
        return no('unsupported', f'{ref} không phải kết quả tool của lượt này: gọi tool dữ liệu trước rồi mới vẽ.')
    if not res.ok:
        return no('unsupported', f'{ref} ({tool}) có trạng thái {res.status}, không có số để vẽ.')
    xs = X_FIELD.get(tool)
    xs = (xs,) if isinstance(xs, str) else xs or ()
    x = next((f for f in xs if res.rows and all(_label(r, f) is not None for r in res.rows)), None)
    if x is None:
        return no('unsupported', f'{tool} không có dạng nhiều dòng vẽ được (trục x). Vẽ được: dự báo period horizon, '
                  'so sánh model, R theo nhóm, giai đoạn / điểm đổi hướng, mùa vụ, R / G từng năm (to_year).')
    ys = tuple(dict.fromkeys(f for f in (args['y'], args.get('y2')) if f))
    for f in ys:
        if f in NOT_Y or not any(f in r for r in res.rows) or not all(_is_value(r.get(f)) or r.get(f) is None
                                                                       for r in res.rows):
            return no('unsupported', f'Cột {f!r} không phải cột số vẽ được của {ref}. Cột vẽ được: '
                      + ', '.join(sorted({k for r in res.rows for k, v in r.items() if _is_value(v) and k not in NOT_Y})))
    if len(ys) == 2 and _unit(ys[0]) != _unit(ys[1]):
        return no('unsupported', f'{ys[0]} và {ys[1]} khác đơn vị, không vẽ chung một trục.')
    keep, excluded = [], []
    for r in res.rows:
        partial = bool(r.get('is_partial'))
        short_year = r.get('is_analysis_period') is False          # năm thiếu tháng (2012): không vẽ cạnh năm đủ
        if partial or short_year or any(r.get(f) is None for f in ys):
            excluded.append(_label(r, x) + (f" (chỉ {r['n_days']}/{r['n_days_in_period']} ngày có dự báo)" if partial
                                            else ' (năm thiếu tháng)' if short_year else ' (không có giá trị)'))
        else:
            keep.append(r)
    if len(keep) < MIN_POINTS:
        return no('unsupported', f'{ref} chỉ có {len(keep)} điểm vẽ được; biểu đồ cần ít nhất {MIN_POINTS}.')
    captions = []
    if tool == 'get_forecast':
        title = res.derived.get('forecast_label', 'Dự báo')
        tme = next((r['typical_month_error'] for r in keep if _is_value(r.get('typical_month_error'))), None)
        if tme is not None:
            captions.append(f'Theo tháng không có khoảng dự báo (Q7); sai số tháng điển hình '
                            f'{evidence.num(tme, 1)}% (backtest 2020–2022).')
    elif tool == 'get_forecast_backtest':
        title = 'So sánh ứng viên dự báo trên backtest 2020–2022 (★ = model chính)'
        captions.append(res.derived.get('backtest_note', ''))
    elif tool == 'get_revenue_summary':
        title = (' / '.join(evidence.FIELD_LABEL.get(f, f) for f in ys)
                 + f" từng năm {keep[0]['year']}–{keep[-1]['year']} (theo ngày đặt hàng)")
    else:
        title = res.message.split('.')[0]
    if excluded:
        captions.append('Không vẽ: ' + '; '.join(excluded) + '.')
    band = (ys == ('g_forecast',) and all(_is_value(r.get('lower_g')) and _is_value(r.get('upper_g')) for r in keep))
    spec = ChartSpec(ref, tool, x, ys, 'line' if tool in LINE_TOOLS else 'bar', title, tuple(c for c in captions if c),
                     tuple(excluded), band, len(keep))
    return spec, ToolResult('ok', f'Biểu đồ {", ".join(ys)} từ {ref} ({spec.n_points} điểm) sẽ hiện dưới câu trả lời. '
                            'App tự ghi nhãn; câu văn vẫn chỉ dẫn số qua chỗ đặt.')


def frame(spec: ChartSpec, results: dict) -> pd.DataFrame:
    """Dữ liệu vẽ: đúng các dòng của results[spec.ref] (trừ dòng ghi ở spec.excluded), dạng dài theo chỉ tiêu."""
    out = []
    for r in results[spec.ref].rows:
        if r.get('is_partial') or r.get('is_analysis_period') is False or any(r.get(f) is None for f in spec.y):
            continue
        star = '★ ' if spec.tool == 'get_forecast_backtest' and r.get('is_primary') else ''
        for f in spec.y:
            item = {'x': star + _label(r, spec.x), 'chi_tieu': evidence.FIELD_LABEL.get(f, f), 'cot': f,
                    'gia_tri': float(r[f]), 'hien_thi': evidence._fmt(r[f], f, False),
                    'chinh': bool(r.get('is_primary'))}
            if spec.band:
                item.update(duoi=float(r['lower_g']), tren=float(r['upper_g']))
            out.append(item)
    return pd.DataFrame(out)


def chart(spec: ChartSpec, df: pd.DataFrame) -> alt.Chart:
    order = list(dict.fromkeys(df['x']))
    x = alt.X('x:N', title=None, sort=order, axis=alt.Axis(labelAngle=-45 if len(order) > 6 else 0, labelLimit=180))
    y = alt.Y('gia_tri:Q', title=' / '.join(dict.fromkeys(df['chi_tieu'])))
    tip = [alt.Tooltip('x:N', title=''), alt.Tooltip('chi_tieu:N', title='Chỉ tiêu'),
           alt.Tooltip('hien_thi:N', title='Giá trị')]
    if len(spec.y) > 1:
        color = alt.Color('chi_tieu:N', title=None, legend=alt.Legend(orient='top'))
    elif spec.tool == 'get_forecast_backtest':
        color = alt.condition('datum.chinh', alt.value('#c0392b'), alt.value('#4c78a8'))     # model chính tô đỏ
    else:
        color = alt.value('#4c78a8')
    layers = []
    if spec.band:
        layers.append(alt.Chart(df).mark_area(opacity=0.2).encode(x=x, y='duoi:Q', y2='tren:Q'))
    base = alt.Chart(df)
    mark = base.mark_line(point=True) if spec.kind == 'line' else base.mark_bar()
    layers.append(mark.encode(x=x, y=y, color=color, tooltip=tip))
    return alt.layer(*layers).properties(height=280, title=alt.TitleParams(spec.title, fontSize=12, anchor='start'))
