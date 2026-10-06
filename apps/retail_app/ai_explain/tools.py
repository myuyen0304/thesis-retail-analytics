"""Tool registry cho chat PS1–PS5, mốc AI1 (docs/ai_explain_plan.md §4, §11). Chưa có LLM.

Luồng một lần gọi `run(call, backend)`:
1. kiểm tham số CHẶT theo schema: tool lạ, trường lạ (bộ lọc, khoảng ngày...), sai kiểu → `unsupported`;
   thiếu trường bắt buộc (R hay G, năm nào) → `needs_clarification`. Không âm thầm bỏ điều kiện, không chọn ngầm;
2. kiểm ma trận khả năng (metric_catalog.CAPABILITIES);
3. mở MỘT phiên đọc (dwh/guarded.py), đọc build marker + trạng thái kiểm → không đạt thì `quality_blocked`;
4. kiểm năm nằm trong coverage của bản dữ liệu (`no_data`) và có kỳ gốc chính thức (`unsupported`);
5. đọc bảng reporting đã kiểm chứng bằng câu SELECT cố định + tham số; gói kết quả cùng bằng chứng.

Backend do server chọn (tham số `backend` của run), không phải tham số của tool. Tên bảng/cột chỉ nằm trong code này.
Lựa chọn trạng thái (ghi lại để eval chấm nhất quán):
- năm ngoài [data_start_date, data_end_date] của bản dữ liệu (vd. 2023) → `no_data`;
- so năm trước / phân rã cho năm < growth_start_year (2012, 2013) → `unsupported` (hợp đồng không định nghĩa YoY này);
- nhóm không tồn tại trong chiều → `no_data`.
"""
import datetime as dt
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from itertools import product

from ai_explain import metric_catalog as cat
from ai_explain.contracts import Evidence, QueryRecord, ToolCall, ToolResult
from dwh.connection import describe
from dwh.guarded import DEFAULT_MAX_ROWS, GuardError, QueryTimeout, RowLimitExceeded, Statement, open_session

TOOL_VERSION = 'v1.3'
ALLOWED_RELATIONS = frozenset({
    'reporting.rpt_build_info', 'reporting.rpt_health_summary', 'reporting.rpt_revenue_yearly',
    'reporting.rpt_driver_period', 'reporting.rpt_revenue_segment_yearly', 'reporting.driver_rule',
    # AI3: PS1–PS3
    'reporting.rpt_revenue_total', 'reporting.rpt_revenue_bridge', 'reporting.rpt_revenue_monthly',
    'reporting.rpt_revenue_phase', 'reporting.rpt_revenue_turning_point', 'reporting.rpt_august_parity',
    'reporting.rpt_calendar_phase', 'reporting.rpt_calendar_stability',
})


# --- schema tham số ---

@dataclass(frozen=True)
class Param:
    kind: str                       # 'int' | 'bool' | 'enum' | 'str'
    description: str
    choices: tuple = ()
    required: bool = True
    default: object = None
    max_len: int = 100


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    params: dict
    handler: object = field(compare=False)


def _check_value(p: Param, v) -> str | None:
    """Lý do từ chối, hoặc None nếu hợp lệ. Không ép kiểu: '2019' (chuỗi) và True (bool) đều bị từ chối."""
    if p.kind == 'int':
        return None if isinstance(v, int) and not isinstance(v, bool) else 'phải là số nguyên'
    if p.kind == 'bool':
        return None if isinstance(v, bool) else 'phải là true/false'
    if p.kind == 'enum':
        return None if isinstance(v, str) and v in p.choices else f'chỉ nhận {list(p.choices)}'
    if p.kind == 'str':
        return None if isinstance(v, str) and 0 < len(v) <= p.max_len else f'phải là chuỗi 1–{p.max_len} ký tự'
    raise AssertionError(p.kind)


def _validate(spec: ToolSpec, arguments) -> tuple[dict | None, ToolResult | None]:
    if not isinstance(arguments, dict):
        return None, ToolResult('unsupported', 'Tham số phải là object JSON.', rejected={'arguments': 'không phải object'})
    rejected = {k: 'tool không có điều kiện này; không thể bỏ qua mà vẫn trả số' for k in arguments if k not in spec.params}
    for k, v in arguments.items():
        if k in spec.params and (why := _check_value(spec.params[k], v)):
            rejected[k] = f'{why}, nhận {v!r}'
    if rejected:
        return None, ToolResult('unsupported', f'`{spec.name}` không hỗ trợ: '
                                + '; '.join(f'{k} ({w})' for k, w in rejected.items()) + '.', rejected=rejected)
    missing = [k for k, p in spec.params.items() if p.required and k not in arguments]
    if missing:
        return None, ToolResult('needs_clarification', 'Cần làm rõ: ' + ', '.join(
            f'{k} — {spec.params[k].description}' for k in missing) + '.', missing=missing)
    args = {k: arguments.get(k, p.default) for k, p in spec.params.items() if k in arguments or p.default is not None}
    return args, None


# --- phiên đọc: build marker + chất lượng ---

def _iso(v):
    return v.isoformat() if isinstance(v, (dt.date, dt.datetime)) else v


class _Turn:
    """Gói phiên đọc + bằng chứng của một lần gọi tool."""

    def __init__(self, sess, backend, tool, args):
        self.sess, self.backend, self.tool, self.args = sess, backend, tool, args
        self.queries: list[QueryRecord] = []

    def fetch(self, source: str, sql: str, params: tuple = ()):
        assert source in ALLOWED_RELATIONS, source
        st = Statement(sql, params)
        self.queries.append(QueryRecord(source, st.render(self.backend), params))
        return self.sess.fetch(st)

    def same_build(self) -> bool:
        """Databricks không có snapshot xuyên câu như REPEATABLE READ của Postgres: đọc lại build marker cuối lượt,
        đổi thì các câu trước có thể thuộc lần dựng khác. Chỉ phát hiện được lần dựng làm đổi rpt_build_info."""
        rows = self.sess.fetch(Statement('select built_at_utc from reporting.rpt_build_info')).rows
        return rows == [(self.build['built_at_utc'],)]

    def snapshot(self) -> ToolResult | None:
        bi = self.fetch('reporting.rpt_build_info',
                        'select built_at_utc, data_start_date, data_end_date, analysis_start_year, analysis_end_year, '
                        'growth_start_year from reporting.rpt_build_info').records()
        hs = self.fetch('reporting.rpt_health_summary',
                        'select status_code, built_at_utc, tests_are_current, tests_are_complete, n_tests_in_project, '
                        'n_tests_run, n_tests_not_pass, test_invocation_id, tests_started_at_utc '
                        'from reporting.rpt_health_summary').records()
        if len(bi) != 1 or len(hs) != 1:
            return ToolResult('quality_blocked', f'Bảng build/health có {len(bi)}/{len(hs)} dòng, cần đúng 1: kho có thể '
                              'đang dựng dở.')
        self.build, self.health = bi[0], hs[0]
        h = self.health
        if h['built_at_utc'] != self.build['built_at_utc']:
            return ToolResult('quality_blocked', 'Trạng thái kiểm không cùng lần dựng kho với dữ liệu đang đọc.')
        if not (h['status_code'] == 'tot' and h['tests_are_current'] and h['tests_are_complete']):
            return ToolResult('quality_blocked', f"Kho chưa qua cổng chất lượng (status_code={h['status_code']}, "
                              f"tests_are_current={h['tests_are_current']}, tests_are_complete={h['tests_are_complete']}). "
                              'Không trả số; xem trang Sức khỏe dữ liệu và chạy đủ `dbt build`.')
        return None

    def coverage_years(self) -> tuple[int, int]:
        return self.build['data_start_date'].year, self.build['data_end_date'].year

    def evidence(self, *, filters, grain, metrics, method=None, read_at) -> Evidence:
        return Evidence(
            request_id=uuid.uuid4().hex, tool=self.tool, tool_version=TOOL_VERSION, arguments_applied=dict(self.args),
            filters_applied=filters, grain=grain, metrics=metrics, method=method, backend=self.backend,
            source_description=describe(self.backend),
            data_version={k: _iso(v) for k, v in self.build.items()},
            quality={k: _iso(v) for k, v in self.health.items()},
            definition_version=cat.definition_version(), read_at_utc=read_at, queries=list(self.queries),
        )


def _check_year(turn: _Turn, year: int, needs_prior: bool) -> ToolResult | None:
    y0, y1 = turn.coverage_years()
    if not y0 <= year <= y1:
        return ToolResult('no_data', f'Năm {year} nằm ngoài dữ liệu thực tế ({turn.build["data_start_date"]} → '
                          f'{turn.build["data_end_date"]}, theo ngày đặt hàng). Không có số thực; sample_submission '
                          'không phải dự báo.')
    g = turn.build['growth_start_year']
    if needs_prior and year < g:
        return ToolResult('unsupported', f'So với năm trước chỉ tính từ {g}: 2012 thiếu nửa đầu năm nên {year} không có '
                          'kỳ gốc chính thức. Không tự tạo tăng trưởng.', rejected={'year': f'< growth_start_year {g}'})
    return None


# --- tool handlers ---

def _summary(turn: _Turn, a: dict) -> ToolResult:
    metric, year, compare = a['metric'], a['year'], a.get('compare_prior_year', False)
    if compare and metric != 'R':
        return ToolResult('unsupported', 'So năm trước hiện chỉ có cho R; G năm trước / ΔG chưa có cột đã kiểm. '
                          'Có thể hỏi mức G từng năm.', rejected={'metric': 'G + compare_prior_year chưa mở'})
    if (r := _check_year(turn, year, needs_prior=compare)):
        return r
    cols = ['year', 'is_analysis_period']
    cols += {'R': ['r'], 'G': ['g'], 'R_and_G': ['r', 'g']}[metric]
    if compare:
        cols += ['r_prior_year', 'delta_r', 'yoy_rate']
    rows = turn.fetch('reporting.rpt_revenue_yearly',
                      f"select {', '.join(cols)} from reporting.rpt_revenue_yearly where year = {{p}}", (year,)).records()
    read_at = _now()
    if not rows:
        return ToolResult('no_data', f'Không có dòng năm {year} trong rpt_revenue_yearly.')
    mids = {'R': ['R'], 'G': ['G'], 'R_and_G': ['R', 'G']}[metric] + (['delta_r', 'yoy_rate'] if compare else [])
    note = '' if rows[0]['is_analysis_period'] else f' Năm {year} thiếu tháng (dữ liệu bắt đầu {turn.build["data_start_date"]}): không so ngang năm đủ.'
    return ToolResult('ok', f'R/G năm {year}, chỉ đọc từ rpt_revenue_yearly.{note}', rows=rows, evidence=turn.evidence(
        filters={'year': year}, grain='năm (ngày đặt hàng)', metrics=cat.metric_defs(*mids), read_at=read_at))


_DRIVER_COLS = ['period_type', 'period_code', 'start_year', 'end_year', 'r_start', 'r_end', 'delta_r',
                'contrib_n', 'contrib_u', 'contrib_p', 'n_start', 'n_end', 'u_start', 'u_end', 'p_start', 'p_end',
                'r_change_rate', 'n_change_rate', 'u_change_rate', 'p_change_rate',
                'top_up_driver', 'top_down_driver', 'delta_r_is_small']


def _drivers(turn: _Turn, a: dict) -> ToolResult:
    if a['metric'] != 'R':
        return ToolResult('unsupported', 'Phân rã N → U → P chỉ có cho R; không dùng phần góp của R để giải thích G.',
                          rejected={'metric': 'G chưa có phân rã'})
    if a.get('period_type', 'year') != 'year':
        return ToolResult('unsupported', 'Phân rã theo giai đoạn PS2 chưa mở: phương pháp "cộng phần góp từng năm" '
                          'còn chờ PM/BA chốt. Có thể hỏi từng năm.', rejected={'period_type': 'phase chưa mở'})
    year = a['year']
    if (r := _check_year(turn, year, needs_prior=True)):
        return r
    rows = turn.fetch('reporting.rpt_driver_period',
                      f"select {', '.join(_DRIVER_COLS)} from reporting.rpt_driver_period "
                      "where period_type = 'year' and period_code = {p}", (str(year),)).records()
    rule = turn.fetch('reporting.driver_rule', 'select min_abs_delta_rate from reporting.driver_rule').records()
    read_at = _now()
    if not rows:
        return ToolResult('no_data', f'Không có dòng phân rã năm {year} trong rpt_driver_period.')
    if len(rows) != 1 or len(rule) != 1:
        return ToolResult('query_error', f'Kỳ {year} có {len(rows)} dòng phân rã / {len(rule)} dòng driver_rule, cần đúng 1.')
    d = rows[0]
    decision = dict(cat.DECISIONS['driver_small_delta_rule'], value=rule[0]['min_abs_delta_rate'])
    return ToolResult('ok', f'Phân rã ΔR năm {year} so {year - 1} theo N → U → P (phân rã số học, không phải nguyên nhân).',
                      rows=rows, derived={'additive_check': d['contrib_n'] + d['contrib_u'] + d['contrib_p'],
                                          'small_delta_rule': decision},
                      evidence=turn.evidence(
                          filters={'period_type': 'year', 'period_code': str(year)}, grain='năm so năm trước',
                          metrics=cat.metric_defs('R', 'delta_r', 'contrib_nup', 'N', 'U', 'P'),
                          method='Phân rã tuần tự N → U → P (docs/star_schema.md §4); 0 = năm trước, 1 = năm đang xét',
                          read_at=read_at))


_SEG_COLS = ['dimension_name', 'dimension_value', 'year', 'r', 'r_total', 'share', 'r_prior_year', 'delta_r',
             'yoy_rate', 'share_shift_pp', 'contribution_to_delta', 'n_groups', 'n_groups_up', 'n_groups_down',
             'delta_r_is_small']


def _extreme(rows: list[dict], sign: int) -> dict | None:
    """Nhóm có ΔR âm nhất (sign=-1) / dương nhất (sign=+1) trên ĐỦ tập nhóm. Đồng hạng → trả mọi nhóm, tie=True."""
    cand = [r for r in rows if r['delta_r'] is not None and sign * r['delta_r'] > 0]
    if not cand:
        return None
    best = max(sign * r['delta_r'] for r in cand)
    groups = [r['dimension_value'] for r in cand if sign * r['delta_r'] == best]
    return {'groups': groups, 'delta_r': sign * best, 'tie': len(groups) > 1}


def _segment(turn: _Turn, a: dict) -> ToolResult:
    if a['metric'] != 'R':
        return ToolResult('unsupported', 'Phân bổ theo nhóm chỉ có cho R.', rejected={'metric': 'G chưa có theo nhóm'})
    dim, year = a['dimension'], a['year']
    if (r := _check_year(turn, year, needs_prior=True)):
        return r
    rows = turn.fetch('reporting.rpt_revenue_segment_yearly',
                      f"select {', '.join(_SEG_COLS)} from reporting.rpt_revenue_segment_yearly "
                      'where dimension_name = {p} and year = {p} order by dimension_value', (dim, year)).records()
    read_at = _now()
    if not rows:
        return ToolResult('no_data', f'Không có dòng {dim} năm {year} trong rpt_revenue_segment_yearly.')
    n_groups = {r['n_groups'] for r in rows}
    if n_groups != {len(rows)}:      # xếp hạng phải trên đủ tập, không trên phần bị thiếu
        return ToolResult('query_error', f'Tập nhóm {dim} năm {year} không đủ ({len(rows)} dòng, n_groups={n_groups}).')
    derived = {'largest_decrease': _extreme(rows, -1), 'largest_increase': _extreme(rows, +1),
               'n_groups': len(rows), 'n_groups_down': rows[0]['n_groups_down'], 'n_groups_up': rows[0]['n_groups_up'],
               'denominator': 'ΔR và R toàn công ty cùng năm (không đổi khi chỉ xem một nhóm)'}
    if (g := a.get('group')) is not None:
        if g not in {r['dimension_value'] for r in rows}:
            return ToolResult('no_data', f'Không có nhóm này trong {dim} năm {year}. Các nhóm có: '
                              + ', '.join(r['dimension_value'] for r in rows) + '.', rejected={'group': 'không tồn tại'})
        derived['selected_group'] = g
    if rows[0]['delta_r_is_small']:
        derived['small_delta_rule'] = cat.DECISIONS['driver_small_delta_rule']
    return ToolResult('ok', f'R theo {dim} năm {year} so {year - 1}; "kéo giảm nhiều nhất" = ΔR âm nhất.',
                      rows=rows, derived=derived, evidence=turn.evidence(
                          filters={'dimension_name': dim, 'year': year}, grain='một chiều × một nhóm × năm',
                          metrics=cat.metric_defs('R', 'delta_r', 'yoy_rate', 'share', 'share_shift_pp',
                                                  'contribution_to_delta'),
                          method='Xếp theo ΔR (tiền) trên đủ tập nhóm; đồng hạng giữ tất cả. Không dùng delta_r_rank '
                                 '(rank 1 = tăng nhiều nhất / giảm ít nhất).',
                          read_at=read_at))


_DEF_COLS = ('metric_id', 'label_vi', 'aliases_vi', 'formula', 'unit', 'additivity', 'decision_status', 'note')


def _definition(turn: _Turn, a: dict) -> ToolResult:
    """Định nghĩa một chỉ tiêu, lấy từ metric_catalog (cùng nguồn với phần Bằng chứng của mọi tool). Không có số."""
    m = cat.METRICS[a['metric']]
    row = {k: (', '.join(m[k]) if isinstance(m[k], list) else m[k]) for k in _DEF_COLS}
    return ToolResult('ok', f'Định nghĩa {m["label_vi"]} theo catalog {cat.CATALOG_VERSION} '
                      f'(trạng thái: {"đã chốt" if m["decision_status"] == "chot" else "đề xuất, chờ PM/BA chốt"}).',
                      rows=[row], evidence=turn.evidence(filters={'metric': a['metric']}, grain='định nghĩa',
                                                         metrics=cat.metric_defs(a['metric']), read_at=_now()))


# --- AI3: PS1 (G → R, tháng), PS2 (giai đoạn), PS3 (nhịp lịch) ---

# cột tiền của rpt_revenue_yearly / rpt_revenue_total → bước của rpt_revenue_bridge, nhãn nghiệp vụ
GAP_PARTS = {
    'cancelled_gross': ('cancelled', 'tiền hàng đơn hủy'),
    'returned_gross': ('returned', 'tiền hàng đơn trả'),
    'undelivered_gross': ('undelivered', 'tiền hàng đơn chưa giao'),
    'delivered_discount': ('discount', 'chiết khấu đơn đã giao'),
}
ANALYSIS_WINDOW = '2013-2022'


def _gap(turn: _Turn, a: dict) -> ToolResult:
    if a['period'] == 'year':
        if 'year' not in a:
            return ToolResult('needs_clarification', 'Cần làm rõ: year — năm nào, hoặc chọn cả kỳ 2013–2022.',
                              missing=['year'])
        year = a['year']
        if (r := _check_year(turn, year, needs_prior=False)):
            return r
        src, head, where, params = ('reporting.rpt_revenue_yearly', 'year, is_analysis_period', 'year = {p}', (year,))
        ptype, code = 'year', str(year)
    else:
        if 'year' in a:
            return ToolResult('unsupported', 'Cả kỳ 2013–2022 không đi kèm một năm; hỏi một năm thì chọn period = year.',
                              rejected={'year': 'không dùng cùng period 2013-2022'})
        src, head, where, params = ('reporting.rpt_revenue_total', 'period_code, start_year, end_year, is_analysis_period',
                                    'period_code = {p}', (ANALYSIS_WINDOW,))
        ptype, code = 'total', ANALYSIS_WINDOW
    rows = turn.fetch(src, f"select {head}, g, r, {', '.join(GAP_PARTS)}, capture_rate from {src} where {where}",
                      params).records()
    steps = turn.fetch('reporting.rpt_revenue_bridge',
                       'select step_code, amount, share_of_g from reporting.rpt_revenue_bridge '
                       'where period_type = {p} and period_code = {p} order by step_order', (ptype, code)).records()
    read_at = _now()
    if not rows:
        return ToolResult('no_data', f'Không có dòng kỳ {code} trong {src}.')
    by = {s['step_code']: s for s in steps}
    if len(rows) != 1 or len(steps) != 6 or set(by) != {'g', 'r', *(st for st, _ in GAP_PARTS.values())}:
        return ToolResult('query_error', f'Kỳ {code}: {len(rows)} dòng kỳ / {len(steps)} bước thác, cần 1 / 6.')
    row = dict(rows[0])
    # hai bảng đọc trong cùng phiên phải khớp: G, R là bước đầu/cuối; mỗi khoản chênh = −(bước trừ) của thác
    if (by['g']['amount'] != row['g'] or by['r']['amount'] != row['r']
            or any(by[st]['amount'] != -row[c] for c, (st, _) in GAP_PARTS.items())):
        return ToolResult('query_error', f'Thác G → R kỳ {code} không khớp bảng kỳ trong cùng phiên; không trả số.')
    for c, (st, _) in GAP_PARTS.items():
        row[f'share_{st}'] = by[st]['share_of_g']
    if ptype == 'total':
        row['period'] = '2013–2022'
    parts = {lbl: row[c] for c, (_, lbl) in GAP_PARTS.items()}
    gap, best = row['g'] - row['r'], max(parts.values())
    if sum(parts.values()) != gap:
        return ToolResult('query_error', f'Bốn khoản chênh kỳ {code} không cộng đúng G − R; không trả số.')
    biggest = [k for k, v in parts.items() if v == best]
    note = '' if row['is_analysis_period'] else ' Năm 2012 thiếu nửa đầu năm: không so ngang năm đủ.'
    return ToolResult('ok', f'G → R kỳ {code}: G trừ tiền hàng đơn hủy, đơn trả, đơn chưa giao và chiết khấu đơn đã giao '
                      f'thì ra R. Tỷ trọng mỗi khoản tính trên G cùng kỳ.{note}', rows=[row], derived={
                          'gap_g_minus_r': gap,
                          'largest_decrease': {'components': biggest, 'amount': best, 'tie': len(biggest) > 1}},
                      evidence=turn.evidence(
                          filters={'period_type': ptype, 'period_code': code}, grain='kỳ (ngày đặt hàng)',
                          metrics=cat.metric_defs('G', 'R', 'gap_components', 'capture_rate'),
                          method='Thác G → R (docs/star_schema.md §3, đối soát PS1); khoản lớn nhất xét trên đủ bốn khoản',
                          read_at=read_at))


def _monthly(turn: _Turn, a: dict) -> ToolResult:
    metric, year, month = a['metric'], a['year'], a['month']
    if not 1 <= month <= 12:
        return ToolResult('unsupported', 'Tháng phải từ 1 đến 12.', rejected={'month': f'nhận {month}'})
    if (r := _check_year(turn, year, needs_prior=False)):
        return r
    cols = ['year', 'month', 'is_analysis_period'] + {'R': ['r'], 'G': ['g'], 'R_and_G': ['r', 'g', 'capture_rate']}[metric]
    if metric != 'G':
        cols += ['r_same_month_prior_year', 'yoy_rate', 'month_index']
    rows = turn.fetch('reporting.rpt_revenue_monthly', f"select {', '.join(cols)} from reporting.rpt_revenue_monthly "
                      'where year = {p} and month = {p}', (year, month)).records()
    read_at = _now()
    if not rows:
        return ToolResult('no_data', f'Không có tháng {month}/{year} trong dữ liệu thực tế ({turn.build["data_start_date"]} '
                          f'→ {turn.build["data_end_date"]}, theo ngày đặt hàng).')
    notes = []
    if metric != 'G' and rows[0]['yoy_rate'] is None:
        notes.append('So cùng tháng năm trước chỉ có từ 08/2013.')
    if metric != 'G' and rows[0]['month_index'] is None:
        notes.append('Chỉ số tháng chỉ tính cho năm đủ 2013–2022.')
    mids = {'R': ['R'], 'G': ['G'], 'R_and_G': ['R', 'G', 'capture_rate']}[metric]
    mids += ['yoy_month', 'month_index'] if metric != 'G' else []
    return ToolResult('ok', ' '.join([f'{metric} tháng {month}/{year}, chỉ đọc từ rpt_revenue_monthly.'] + notes),
                      rows=rows, evidence=turn.evidence(filters={'year': year, 'month': month},
                                                        grain='tháng (ngày đặt hàng)', metrics=cat.metric_defs(*mids),
                                                        read_at=read_at))


_PHASE_COLS = ['phase_code', 'phase_name', 'trend', 'start_year', 'end_year', 'n_years', 'r_start', 'r_end', 'delta_r',
               'total_change_rate', 'cagr']
_TURN_COLS = ['turning_year', 'from_phase_code', 'to_phase_code', 'from_phase_name', 'to_phase_name', 'r_12m_before',
              'r_12m_after', 'delta_r', 'magnitude', 'turn_note']


def _extreme_by(rows: list[dict], key: str, sign: int, label, out: str) -> dict | None:
    """Dòng có `key` âm nhất (sign=-1) / dương nhất (+1) trên ĐỦ tập dòng; đồng hạng giữ tất cả."""
    cand = [r for r in rows if r[key] is not None and sign * r[key] > 0]
    if not cand:
        return None
    best = max(sign * r[key] for r in cand)
    hit = [label(r) for r in cand if sign * r[key] == best]
    return {out: hit, key: sign * best, 'tie': len(hit) > 1}


def _phase_label(r: dict) -> str:
    return f"{r['phase_code']} — {r['phase_name']} ({r['start_year']}→{r['end_year']})"


def _trend(turn: _Turn, a: dict) -> ToolResult:
    if a['view'] == 'phases':
        rows = turn.fetch('reporting.rpt_revenue_phase', f"select {', '.join(_PHASE_COLS)} from reporting.rpt_revenue_phase "
                          'order by start_year').records()
        read_at = _now()
        if len(rows) != 4:
            return ToolResult('query_error', f'rpt_revenue_phase có {len(rows)} giai đoạn, hợp đồng PS2 là 4.')
        derived = {'n_phases': len(rows)}
        for key in ('delta_r', 'cagr'):
            sfx = '' if key == 'delta_r' else '_cagr'
            derived[f'largest_decrease{sfx}'] = _extreme_by(rows, key, -1, _phase_label, 'phases')
            derived[f'largest_increase{sfx}'] = _extreme_by(rows, key, +1, _phase_label, 'phases')
        return ToolResult('ok', 'Bốn giai đoạn R do PM/BA chốt ngày 2026-09-27; hai giai đoạn liền nhau dùng chung năm '
                          'ranh giới. "Giảm/tăng mạnh nhất" có hai tiêu chí: theo ΔR (tiền) hoặc theo CAGR (%/năm). '
                          'Giai đoạn chỉ mô tả R lên hay xuống, không phải nguyên nhân. Năm 2022 tăng lại chưa tách '
                          'thành giai đoạn mới.', rows=rows, derived=derived, evidence=turn.evidence(
                              filters={'view': 'phases'}, grain='giai đoạn PS2', read_at=read_at,
                              metrics=cat.metric_defs('phase', 'R', 'delta_r', 'cagr'),
                              method='CAGR = (R năm cuối ÷ R năm đầu)^(1/n) − 1; xếp hạng trên đủ 4 giai đoạn, '
                                     'theo ΔR (largest_*) hoặc CAGR (largest_*_cagr)'))
    rows = turn.fetch('reporting.rpt_revenue_turning_point', f"select {', '.join(_TURN_COLS)} "
                      'from reporting.rpt_revenue_turning_point order by turning_year').records()
    read_at = _now()
    if len(rows) != 3:
        return ToolResult('query_error', f'rpt_revenue_turning_point có {len(rows)} điểm, hợp đồng PS2 là 3.')

    def label(r):
        return f"cuối {r['turning_year']} ({r['from_phase_code']} → {r['to_phase_code']})"
    return ToolResult('ok', 'Ba điểm đổi hướng ở ranh giới các giai đoạn PS2. Độ lớn = R 12 tháng sau điểm ÷ R 12 '
                      'tháng trước điểm − 1; điểm đặt ở ranh giới năm nên 12 tháng trước là cả năm của điểm, 12 tháng '
                      'sau là cả năm kế tiếp. Ghi chú đổi hướng là nhận định BA, PM chốt.', rows=rows,
                      derived={'largest_decrease': _extreme_by(rows, 'magnitude', -1, label, 'turns'),
                               'largest_increase': _extreme_by(rows, 'magnitude', +1, label, 'turns')},
                      evidence=turn.evidence(filters={'view': 'turning_points'}, grain='điểm đổi hướng PS2',
                                             metrics=cat.metric_defs('phase', 'R', 'turn_magnitude'), read_at=read_at,
                                             method='Xếp theo độ lớn (%) trên đủ 3 điểm'))


_STAB_NAMES = {   # rpt_calendar_stability → tên cột theo nhịp, để app định dạng đúng loại số
    'mua_vu': ('season_peak_trough_ratio', 'loo_min_ratio', 'loo_max_ratio'),
    'cuoi_thang': ('eom_excess', 'loo_min_eom_excess', 'loo_max_eom_excess'),
    'thang_8': ('august_odd_vs_even', 'loo_min_odd_vs_even', 'loo_max_odd_vs_even'),
}
_CAL_PHASE_COLS = {
    'mua_vu': ['peak_month', 'peak_index', 'trough_month', 'trough_index', 'season_peak_trough_ratio'],
    'cuoi_thang': ['eom_share', 'eom_expected_share', 'eom_excess'],
}
_AUG_COLS = ['n_odd_years', 'n_even_years', 'august_index_odd', 'august_index_even', 'august_odd_vs_even',
             'max_index_odd', 'min_index_even']


def _calendar(turn: _Turn, a: dict) -> ToolResult:
    pat = a['pattern']
    st = turn.fetch('reporting.rpt_calendar_stability', 'select metric_value, loo_min, loo_max, n_years_with_pattern, '
                    'n_years from reporting.rpt_calendar_stability where rhythm_code = {p}', (pat,)).records()
    if len(st) != 1:
        return ToolResult('query_error', f'rpt_calendar_stability có {len(st)} dòng cho nhịp {pat}, cần 1.')
    value, lo, hi = _STAB_NAMES[pat]
    s = st[0]
    head = {'period_code': ANALYSIS_WINDOW, 'period': '2013–2022', value: s['metric_value'], lo: s['loo_min'],
            hi: s['loo_max'], 'n_years_with_pattern': s['n_years_with_pattern'], 'n_years': s['n_years']}
    derived, phases, mids, decision = {}, [], ['month_index'], None
    if pat == 'thang_8':
        ap = turn.fetch('reporting.rpt_august_parity', f"select {', '.join(_AUG_COLS)} "
                        'from reporting.rpt_august_parity').records()
        if len(ap) != 1 or ap[0]['august_odd_vs_even'] != s['metric_value']:
            return ToolResult('query_error', 'rpt_august_parity không khớp rpt_calendar_stability trong cùng phiên.')
        head.update(ap[0])
        below = ap[0]['max_index_odd'] < ap[0]['min_index_even']
        derived['all_odd_below_all_even'] = below
        derived['odd_even_order'] = ('năm lẻ nào cũng có tháng 8 thấp hơn mọi năm chẵn' if below
                                     else 'có năm lẻ có tháng 8 không thấp hơn mọi năm chẵn')
        mids.append('august_odd_vs_even')
        note = ('So chỉ số tháng 8 (R tháng 8 ÷ R trung bình tháng của chính năm đó), không so R tuyệt đối. '
                'odd_even_order là kết luận so sánh do app tính: chỉ số tháng 8 cao nhất của năm lẻ có thấp hơn chỉ số '
                'thấp nhất của năm chẵn không. Mô tả lịch sử, không phải dự báo năm sau 2022.')
    else:
        cols = _CAL_PHASE_COLS[pat]
        if pat == 'mua_vu':
            # tháng cao / thấp nhất CẢ KỲ: R các tháng cùng tên cộng qua 2013–2022 (đúng cách rpt_calendar_stability
            # tính chênh mùa); kiểm lại tỷ số max ÷ min khớp metric_value đọc trong cùng phiên
            pooled = turn.fetch('reporting.rpt_revenue_monthly', 'select month, sum(r) as r from '
                                'reporting.rpt_revenue_monthly where is_analysis_period group by month').records()
            hi = max(x['r'] for x in pooled)
            lo = min(x['r'] for x in pooled)
            if len(pooled) != 12 or abs(float(hi) / float(lo) - s['metric_value']) > 1e-9 * s['metric_value']:
                return ToolResult('query_error', 'rpt_revenue_monthly không khớp rpt_calendar_stability trong cùng phiên.')
            peaks = [x['month'] for x in pooled if x['r'] == hi]
            troughs = [x['month'] for x in pooled if x['r'] == lo]
            if len(peaks) == 1 and len(troughs) == 1:        # hòa thì không có "tháng cao nhất" duy nhất để nói
                head.update(peak_month=peaks[0], trough_month=troughs[0])
        if pat == 'cuoi_thang':
            tot = turn.fetch('reporting.rpt_revenue_total', 'select eom_share, eom_expected_share, eom_excess '
                             'from reporting.rpt_revenue_total where period_code = {p}', (ANALYSIS_WINDOW,)).records()
            if len(tot) != 1 or abs(tot[0]['eom_excess'] - s['metric_value']) > 1e-12:
                return ToolResult('query_error', 'rpt_revenue_total không khớp rpt_calendar_stability trong cùng phiên.')
            head.update(eom_share=tot[0]['eom_share'], eom_expected_share=tot[0]['eom_expected_share'])
        phases = turn.fetch('reporting.rpt_calendar_phase', 'select phase_code, phase_name, first_year, last_year, '
                            f"n_years, {', '.join(cols)} from reporting.rpt_calendar_phase order by first_year").records()
        if len(phases) != 4:
            return ToolResult('query_error', f'rpt_calendar_phase có {len(phases)} giai đoạn, cần 4.')
        derived['n_phases'] = len(phases)
        if pat == 'mua_vu':
            derived['peak_months'] = sorted({p['peak_month'] for p in phases})
            derived['trough_months'] = sorted({p['trough_month'] for p in phases})
            if 'peak_month' in head:
                derived['n_phases_same_peak'] = sum(p['peak_month'] == head['peak_month'] for p in phases)
                derived['n_phases_same_trough'] = sum(p['trough_month'] == head['trough_month'] for p in phases)
            mids.append('season_ratio')
            note = ('Chênh mùa cả kỳ = R các tháng cùng tên cộng qua 2013–2022, tháng cao nhất ÷ thấp nhất; '
                    'rows[0].peak_month / trough_month là tháng cao / thấp nhất CẢ KỲ. peak_months / trough_months là '
                    'tập tháng cao / thấp nhất của từng giai đoạn; n_phases_same_peak / n_phases_same_trough là số giai '
                    'đoạn có cùng tháng cao / thấp nhất với cả kỳ.')
        else:
            derived['n_phases_eom_positive'] = sum(p['eom_excess'] > 0 for p in phases)
            mids.append('eom_excess')
            note = 'Mức dồn cuối tháng > 0: R từ ngày 26 trở đi nhiều hơn mức rải đều theo số ngày.'
        decision = cat.DECISIONS['ps3_boundary_year']
        derived['phase_year_rule'] = decision
    read_at = _now()
    return ToolResult('ok', f'Nhịp {pat} kỳ 2013–2022 (rows[0]); loo_min/loo_max là khoảng dao động khi bỏ lần lượt '
                      f'từng năm; n_years_with_pattern là số năm tự có nhịp. {note}', rows=[head] + phases,
                      derived=derived, evidence=turn.evidence(
                          filters={'pattern': pat, 'period_code': ANALYSIS_WINDOW}, grain='nhịp lịch (rows[0] cả kỳ, '
                          'các dòng sau theo giai đoạn PS3)' if phases else 'nhịp lịch cả kỳ', read_at=read_at,
                          metrics=cat.metric_defs(*mids), method=decision['text'] if decision else None))


_YEAR = Param('int', 'năm theo ngày đặt hàng, vd. 2019')
_METRIC_RG = Param('enum', 'R (đơn delivered, sau chiết khấu) hay G (mọi đơn, chưa trừ chiết khấu)', ('R', 'G'))

TOOLS = {s.name: s for s in [
    ToolSpec('get_revenue_summary', 'Mức R/G của một năm; với R có thể kèm so năm trước.', {
        'metric': Param('enum', 'R, G hay cả hai (R_and_G)', ('R', 'G', 'R_and_G')),
        'year': _YEAR,
        'compare_prior_year': Param('bool', 'kèm R năm trước, ΔR, % đổi', required=False, default=False),
    }, _summary),
    ToolSpec('get_revenue_drivers', 'Phân rã ΔR một năm so năm trước theo N → U → P (phân rã số học).', {
        'metric': _METRIC_RG,
        'year': _YEAR,
        'period_type': Param('enum', 'year (mở) hoặc phase (chưa mở)', ('year', 'phase'), required=False, default='year'),
    }, _drivers),
    ToolSpec('get_segment_contribution', 'R theo MỘT chiều × năm: ΔR, tỷ trọng, % đóng góp vào ΔR toàn công ty.', {
        'metric': _METRIC_RG,
        'dimension': Param('enum', 'category / region / acquisition_channel', tuple(cat.DIMENSIONS)),
        'year': _YEAR,
        'group': Param('str', 'tên một nhóm của chiều (tùy chọn)', required=False),
    }, _segment),
    ToolSpec('get_metric_definition', 'Định nghĩa một chỉ tiêu (R, G, N, U, P, ΔR...): công thức, đơn vị, cách cộng, '
             'trạng thái chốt. Dùng cho câu hỏi "X là gì", "R khác G thế nào". Không trả số liệu.', {
        'metric': Param('enum', 'mã chỉ tiêu trong catalog', tuple(cat.METRICS)),
    }, _definition),
    ToolSpec('get_revenue_gap', 'PS1: G hụt thành R bao nhiêu và vì khoản nào (tiền hàng đơn hủy, đơn trả, đơn chưa '
             'giao, chiết khấu đơn đã giao), kèm R/G; một năm hoặc cả kỳ 2013–2022.', {
        'period': Param('enum', 'year (một năm) hoặc 2013-2022 (cả kỳ phân tích)', ('year', ANALYSIS_WINDOW)),
        'year': Param('int', 'năm, chỉ dùng khi period = year', required=False),
    }, _gap),
    ToolSpec('get_revenue_monthly', 'PS1/PS3: R hoặc G của MỘT tháng; với R kèm R cùng tháng năm trước, % đổi và chỉ số '
             'tháng (R tháng ÷ TB tháng của năm).', {
        'metric': Param('enum', 'R, G hay cả hai (R_and_G, kèm R/G)', ('R', 'G', 'R_and_G')),
        'year': _YEAR,
        'month': Param('int', 'tháng 1–12'),
    }, _monthly),
    ToolSpec('get_revenue_trend', 'PS2: các giai đoạn R do PM/BA chốt (R đầu/cuối, ΔR, CAGR, xếp hạng) hoặc các điểm '
             'đổi hướng (độ lớn, ghi chú). Mô tả xu hướng, không phải nguyên nhân.', {
        'view': Param('enum', 'phases (giai đoạn) hoặc turning_points (điểm đổi hướng)', ('phases', 'turning_points')),
    }, _trend),
    ToolSpec('get_calendar_pattern', 'PS3: nhịp lịch 2013–2022 và độ ổn định: mua_vu (tháng cao/thấp, chênh mùa), '
             'cuoi_thang (dồn về cuối tháng), thang_8 (tháng 8 năm lẻ so năm chẵn).', {
        'pattern': Param('enum', 'mua_vu / cuoi_thang / thang_8', ('mua_vu', 'cuoi_thang', 'thang_8')),
    }, _calendar),
]}


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def run(call: ToolCall | dict, backend: str, *, timeout_s: float | None = None,
        max_rows: int = DEFAULT_MAX_ROWS) -> ToolResult:
    if isinstance(call, dict):
        call = ToolCall(call.get('tool'), call.get('arguments'))
    spec = TOOLS.get(call.tool) if isinstance(call.tool, str) else None
    if spec is None:
        return ToolResult('unsupported', f'Không có tool {call.tool!r}. Tool đang mở: {sorted(TOOLS)}.',
                          rejected={'tool': 'không có trong registry'})
    args, err = _validate(spec, call.arguments)
    if err:
        return err
    if blockers := cat.capability_blockers(spec.name, args):
        return ToolResult('unsupported', 'Catalog chưa mở khả năng này: ' + '; '.join(blockers) + '.',
                          rejected={'capability': '; '.join(blockers)})
    try:
        sess = open_session(backend, ALLOWED_RELATIONS, timeout_s=timeout_s, max_rows=max_rows)
    except GuardError as e:
        return ToolResult('query_error', f'Kết nối AI không đạt điều kiện chỉ đọc: {e}. Không đọc dữ liệu.')
    except Exception as e:
        return ToolResult('query_error', f'Không kết nối được {backend}: {type(e).__name__}.')
    try:
        turn = _Turn(sess, backend, spec.name, args)
        result = turn.snapshot() or spec.handler(turn, args)
        if backend == 'databricks' and hasattr(turn, 'build') and not turn.same_build():
            return ToolResult('query_error', 'Kho vừa được dựng lại trong lúc đọc (build marker đổi giữa các câu); '
                              'không trả số trộn hai lần dựng. Hỏi lại sau khi build xong.')
        return result
    except QueryTimeout as e:
        return ToolResult('query_error', f'Truy vấn quá thời gian ({e}); không trả số thay thế.')
    except RowLimitExceeded as e:
        return ToolResult('query_error', f'{e}; không cắt bớt để xếp hạng trên tập thiếu.')
    except Exception as e:
        return ToolResult('query_error', f'Truy vấn lỗi: {type(e).__name__}. Không trả số.')
    finally:
        sess.close()


_KNOWN_GROUPS: dict[str, frozenset] = {}


def known_groups(backend: str) -> frozenset:
    """Tên mọi nhóm của 3 chiều PS5 (Streetwear, East, organic_search...), để bộ điều phối biết câu hỏi có lọc nhóm hay
    không. Đọc qua phiên chỉ-đọc như mọi tool. Chỉ nhớ kết quả ĐỌC ĐƯỢC; lỗi (kể cả tập rỗng) thì raise, không trả tập
    rỗng: tập rỗng nghĩa là "câu hỏi không lọc nhóm" và sẽ tắt ngầm phép kiểm bỏ bộ lọc (lỗi chặn AI3, A08). Trên
    Databricks lỗi thoáng qua (warehouse nguội, token) dễ xảy ra, nên không được nhớ lỗi suốt đời process."""
    if backend not in _KNOWN_GROUPS:
        sess = open_session(backend, ALLOWED_RELATIONS)
        try:
            rows = sess.fetch(Statement('select distinct dimension_value from reporting.rpt_revenue_segment_yearly')).records()
        finally:
            sess.close()
        groups = frozenset(r['dimension_value'] for r in rows if isinstance(r['dimension_value'], str))
        if not groups:
            raise RuntimeError('rpt_revenue_segment_yearly không có nhóm nào')
        _KNOWN_GROUPS[backend] = groups
    return _KNOWN_GROUPS[backend]


def tool_schemas() -> list[dict]:
    """Chỉ công bố tool/giá trị có tổ hợp mở. run vẫn kiểm lại tổ hợp, kể cả lời gọi cũ từ model."""
    out = []
    for s in TOOLS.values():
        domains = {k: p.choices if p.kind == 'enum' else (False, True)
                   for k, p in s.params.items() if p.kind in ('enum', 'bool')}
        variants = [dict(zip(domains, values)) for values in product(*domains.values())]
        opened = [a for a in variants if not cat.capability_blockers(s.name, a)]
        if not opened:
            continue
        props = {}
        for k, p in s.params.items():
            t = {'int': 'integer', 'bool': 'boolean', 'enum': 'string', 'str': 'string'}[p.kind]
            props[k] = {'type': t, 'description': p.description}
            if k in domains:
                props[k]['enum'] = [v for v in domains[k] if any(a[k] == v for a in opened)]
            if p.kind == 'str':
                props[k]['maxLength'] = p.max_len
        out.append({'name': s.name, 'description': s.description, 'input_schema': {
            'type': 'object', 'properties': props, 'additionalProperties': False,
            'required': [k for k, p in s.params.items() if p.required]}})
    return out


def as_plain(v):
    """Decimal → chuỗi đủ chữ số (không qua float) khi cần xuất JSON."""
    return str(v) if isinstance(v, Decimal) else _iso(v)
