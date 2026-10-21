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
import math
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from itertools import product

from ai_explain import knowledge
from ai_explain import metric_catalog as cat
from ai_explain.contracts import Evidence, QueryRecord, ToolCall, ToolResult
from ai_explain.evidence import FEATURE_GROUP_LABEL
from dwh.connection import describe
from dwh import releases
from dwh.guarded import DEFAULT_MAX_ROWS, GuardError, QueryTimeout, RowLimitExceeded, Statement, open_session

TOOL_VERSION = 'v2.2'   # S9b lượt 2: rank_dir và ngưỡng nhóm nhỏ; v2.1 là lượt đầu
                        # v1.7: chuỗi từng năm (to_year), ghi chú app (notes) cho đóng góp nhóm / sai số tháng
ALLOWED_RELATIONS = frozenset({
    'reporting.rpt_build_info', 'reporting.rpt_health_summary', 'reporting.rpt_revenue_yearly',
    'reporting.rpt_driver_period', 'reporting.rpt_revenue_segment_yearly', 'reporting.driver_rule',
    # AI3: PS1–PS3
    'reporting.rpt_revenue_total', 'reporting.rpt_revenue_bridge', 'reporting.rpt_revenue_monthly',
    'reporting.rpt_revenue_phase', 'reporting.rpt_revenue_turning_point', 'reporting.rpt_august_parity',
    'reporting.rpt_calendar_phase', 'reporting.rpt_calendar_stability',
})
# B3 (2026-10-15): được phép đọc nhưng KHÔNG bắt buộc có. rpt_forecast_* chỉ có trong bản dữ liệu của pipeline từ B2b;
# build thường (chế độ cũ, PostgreSQL) và bản dựng trước B2b không có. Đưa vào ALLOWED_RELATIONS thì guard Databricks đòi
# quyền trên bảng không tồn tại và khóa cả chat PS1–PS5. Thiếu bảng thì tool dự báo trả no_data, không lấy số nơi khác.
OPTIONAL_RELATIONS = frozenset({'reporting.rpt_forecast_daily', 'reporting.rpt_forecast_backtest',
                                'reporting.rpt_forecast_explain'})


# --- schema tham số ---

@dataclass(frozen=True)
class Param:
    kind: str                       # 'int' | 'bool' | 'enum' | 'str'
    description: str
    choices: tuple = ()
    required: bool = True
    default: object = None
    max_len: int = 100
    allow_empty: bool = False


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
        return None if isinstance(v, str) and (p.allow_empty or len(v) > 0) and len(v) <= p.max_len \
            else f'phải là chuỗi {"0" if p.allow_empty else "1"}–{p.max_len} ký tự'
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


def _release_evidence():
    record = releases.current()
    return {k: record[k] for k in ('release_id', 'snapshot_id', 'code_version', 'run_id')} if record else {}


class _Turn:
    """Gói phiên đọc + bằng chứng của một lần gọi tool."""

    def __init__(self, sess, backend, tool, args):
        self.sess, self.backend, self.tool, self.args = sess, backend, tool, args
        self.queries: list[QueryRecord] = []

    def fetch(self, source: str, sql: str, params: tuple = ()):
        assert source in ALLOWED_RELATIONS | OPTIONAL_RELATIONS, source
        st = Statement(sql, params)
        record = releases.current() if releases.enabled(self.backend) else None
        self.queries.append(QueryRecord(releases.sql_for(source, record), releases.sql_for(st.render(self.backend), record), params))
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
            data_version={**{k: _iso(v) for k, v in self.build.items()}, **_release_evidence()},
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
    to_year = a.get('to_year')          # chuỗi từng năm year → to_year (B6, biểu đồ R / G theo năm), mỗi năm một dòng
    if compare and metric != 'R':
        return ToolResult('unsupported', 'So năm trước hiện chỉ có cho R; G năm trước / ΔG chưa có cột đã kiểm. '
                          'Có thể hỏi mức G từng năm.', rejected={'metric': 'G + compare_prior_year chưa mở'})
    if to_year is not None and to_year <= year:
        return ToolResult('unsupported', f'to_year ({to_year}) phải lớn hơn year ({year}); một năm thì bỏ to_year.',
                          rejected={'to_year': f'{to_year} ≤ year {year}'})
    if (r := _check_year(turn, year, needs_prior=compare)) or (to_year and (r := _check_year(turn, to_year, False))):
        return r
    cols = ['year', 'is_analysis_period']
    cols += {'R': ['r'], 'G': ['g'], 'R_and_G': ['r', 'g']}[metric]
    if compare:
        cols += ['r_prior_year', 'delta_r', 'yoy_rate']
    where, params = ('year = {p}', (year,)) if to_year is None else ('year >= {p} and year <= {p} order by year',
                                                                     (year, to_year))
    rows = turn.fetch('reporting.rpt_revenue_yearly',
                      f"select {', '.join(cols)} from reporting.rpt_revenue_yearly where {where}", params).records()
    read_at = _now()
    if not rows:
        return ToolResult('no_data', f'Không có dòng năm {year} trong rpt_revenue_yearly.')
    last = to_year or year
    if [r['year'] for r in rows] != list(range(year, last + 1)):
        return ToolResult('query_error', f'rpt_revenue_yearly có {len(rows)} dòng cho {year}–{last}, cần đủ từng năm.')
    mids = {'R': ['R'], 'G': ['G'], 'R_and_G': ['R', 'G']}[metric] + (['delta_r', 'yoy_rate'] if compare else [])
    part = [r['year'] for r in rows if not r['is_analysis_period']]
    note = (f' Năm {", ".join(map(str, part))} thiếu tháng (dữ liệu bắt đầu {turn.build["data_start_date"]}): không so '
            'ngang năm đủ.' if part else '')
    derived = {}
    if to_year is not None:
        # xếp hạng trên đủ tập năm ĐỦ tháng (năm thiếu tháng không vào xếp hạng)
        full = [r for r in rows if r['is_analysis_period']]
        derived['n_years'] = len(rows)
        for col in ('r', 'g'):
            if col in cols and full:
                for key, pick in (('highest', max), ('lowest', min)):
                    v = pick(r[col] for r in full)
                    derived[f'{key}_{col}'] = {'years': [str(r['year']) for r in full if r[col] == v], col: v}
    label = f'năm {year}' if to_year is None else f'từng năm {year}–{to_year}'
    hint = ('' if to_year is None else ' Một năm: rows[<năm>]. Năm cao / thấp nhất (năm đủ tháng): '
            'derived.highest_<r|g>.years là NĂM, .r / .g là số của năm đó.')
    return ToolResult('ok', f'R/G {label}, chỉ đọc từ rpt_revenue_yearly.{note}{hint}', rows=rows, derived=derived,
                      evidence=turn.evidence(filters={'year': year, **({'to_year': to_year} if to_year else {})},
                                             grain='năm (ngày đặt hàng)', metrics=cat.metric_defs(*mids), read_at=read_at))


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


# live B6 V03: mô hình không tự nói câu này, nên app in dưới câu trả lời (như ghi chú N → U → P của trang chat)
SEGMENT_NOTE = ('Đóng góp của từng nhóm là phân rã số học của ΔR toàn công ty: cho biết thay đổi R nằm ở nhóm nào, không '
                'chứng minh nguyên nhân.')
_SEG_COLS = ['dimension_name', 'dimension_value', 'year', 'r', 'r_total', 'share', 'r_prior_year', 'delta_r',
             'yoy_rate', 'share_shift_pp', 'contribution_to_delta', 'n_groups', 'n_groups_up', 'n_groups_down',
             'delta_r_is_small']


def _extreme(rows: list[dict], sign: int, pick=max) -> dict | None:
    """Nhóm có ΔR âm nhất (sign=-1) / dương nhất (sign=+1) trên ĐỦ tập nhóm. Đồng hạng → trả mọi nhóm, tie=True.
    pick=min: phía NHỎ trong các nhóm cùng chiều ("giảm ít nhất" = ΔR âm gần 0 nhất; PM chốt 2026-10-09 cần trả lời thẳng)."""
    cand = [r for r in rows if r['delta_r'] is not None and sign * r['delta_r'] > 0]
    if not cand:
        return None
    best = pick(sign * r['delta_r'] for r in cand)
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
               'smallest_decrease': _extreme(rows, -1, min), 'smallest_increase': _extreme(rows, +1, min),
               'n_groups': len(rows), 'n_groups_down': rows[0]['n_groups_down'], 'n_groups_up': rows[0]['n_groups_up'],
               'denominator': 'ΔR và R toàn công ty cùng năm (không đổi khi chỉ xem một nhóm)'}
    if (g := a.get('group')) is not None:
        if g not in {r['dimension_value'] for r in rows}:
            return ToolResult('no_data', f'Không có nhóm này trong {dim} năm {year}. Các nhóm có: '
                              + ', '.join(r['dimension_value'] for r in rows) + '.', rejected={'group': 'không tồn tại'})
        derived['selected_group'] = g
    if rows[0]['delta_r_is_small']:
        derived['small_delta_rule'] = cat.DECISIONS['driver_small_delta_rule']
    return ToolResult('ok', f'R theo {dim} năm {year} so {year - 1}; "kéo giảm nhiều nhất" = ΔR âm nhất; "giảm ít nhất" = '
                      'ΔR âm gần 0 nhất trong các nhóm giảm (smallest_decrease); tương tự cho chiều tăng. Đóng góp của '
                      'nhóm là phân rã số học, không phải nguyên nhân.',
                      rows=rows, derived=derived, notes=[SEGMENT_NOTE], evidence=turn.evidence(
                          filters={'dimension_name': dim, 'year': year}, grain='một chiều × một nhóm × năm',
                          metrics=cat.metric_defs('R', 'delta_r', 'yoy_rate', 'share', 'share_shift_pp',
                                                  'contribution_to_delta'),
                          method='Xếp theo ΔR (tiền) trên đủ tập nhóm, cả phía lớn nhất (largest_*) lẫn phía nhỏ nhất '
                                 '(smallest_*: chỉ trong các nhóm cùng chiều); đồng hạng giữ tất cả. Không dùng '
                                 'delta_r_rank (rank 1 = tăng nhiều nhất / giảm ít nhất).',
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


# --- B3: đọc dự báo do pipeline ghi (docs/hop_dong_du_bao.md §5–§8, docs/ke_hoach_ai_gd2.md) ---
# Tool chỉ ĐỌC reporting.rpt_forecast_* của bản dữ liệu đang phục vụ; không train, không chọn model (luật chạy trong
# pipeline, Q8). Mặc định ứng viên is_primary; ứng viên khác chỉ khi người hỏi nêu đích danh.

FORECAST_START, FORECAST_END = (dt.date.fromisoformat(d) for d in cat.FORECAST_HORIZON)
NO_FORECAST = ('Bản dữ liệu đang đọc không có bảng dự báo (reporting.rpt_forecast_*). Dự báo chỉ có trong bản dữ liệu do '
               'pipeline dựng từ bước B2b (chế độ versioned); chế độ cũ, PostgreSQL và bản dựng trước B2b không có. '
               'Không lấy số ở nguồn khác thay vào.')
MODEL_LABEL = {
    'lgbm_full': 'LightGBM, train toàn chuỗi', 'lgbm_2019': 'LightGBM, train từ 2019',
    'sarimax_full': 'log + SARIMAX, train toàn chuỗi', 'sarimax_2019': 'log + SARIMAX, train từ 2019',
    'blend_full': 'bản gộp LightGBM + log SARIMAX, train toàn chuỗi', 'arima_2019': 'ARIMA, train từ 2019',
    'naive2y': 'mốc seasonal naive 2 năm', 'naive1y': 'mốc seasonal naive 1 năm',
    'baseline_cu': 'mốc baseline cũ (trung bình mùa vụ × tăng trưởng gộp)',
}
COGS_LABEL = {'direct': 'COGS dự báo trực tiếp', 'ratio': 'COGS qua tỷ lệ COGS/G', 'copy': 'COGS chép theo mốc'}
# Lý do do APP viết từ selection_step mà pipeline ghi (luật hợp đồng §5); LLM không tự đặt lý do.
SELECTION_REASON = {
    'buoc_1_khong_ung_vien_nao_qua_san': 'Bước 1 của luật chọn: không ứng viên nào thắng mốc seasonal naive 2 năm về '
                                         'điểm ngày kết hợp ở cả 3 fold backtest, nên dùng mốc làm model chính.',
    'buoc_2_diem_thap_nhat': 'Bước 2 của luật chọn: trong các ứng viên thắng mốc seasonal naive 2 năm ở cả 3 fold backtest, '
                             'ứng viên này có điểm ngày kết hợp trung bình thấp nhất.',
    'buoc_3_hoa_chon_don_gian': 'Bước 3 của luật chọn: các ứng viên có điểm trong vòng 1% của điểm thấp nhất được coi là '
                                'hòa; ứng viên này đơn giản nhất trong nhóm hòa.',
}
BACKTEST_NOTE = ('Sai số backtest 2020–2022 (3 fold, mỗi fold dự báo 548 ngày), không phải độ chính xác trên 2023–2024 '
                 '(chưa có số thực). Điểm của ứng viên thắng là lạc quan vì được chọn từ nhiều ứng viên trên cùng 3 fold.')
# B7 S1b (live b7 K08: 2/3 lượt vẽ điểm ngày mà không nói đó là thước chọn): ghi chú app in dưới mọi câu trả lời dẫn
# get_forecast_backtest, như ghi chú MAPE tháng của get_forecast; không gửi cho mô hình
SELECTION_NOTE = ('Điểm ngày kết hợp ((MAE G + MAE COGS) / 2, trung bình 3 fold) là thước chọn model chính; MAPE G tháng '
                  'chỉ để hiển thị và có thể xếp hạng khác. ' + BACKTEST_NOTE)


class _NoForecast(Exception):
    pass


def _missing_relation(e: Exception) -> bool:
    """Lỗi 'bảng không tồn tại' của DuckDB / PostgreSQL / Databricks khi đọc rpt_forecast_*."""
    m = str(e).lower()
    return 'rpt_forecast' in m and any(k in m for k in ('does not exist', 'not found', 'cannot be found', 'catalog error',
                                                       'table_or_view_not_found', 'undefined'))


def _ffetch(turn: '_Turn', source: str, sql: str, params: tuple = ()) -> list[dict]:
    try:
        return turn.fetch(source, sql, params).records()
    except Exception as e:
        if _missing_relation(e):
            raise _NoForecast() from e
        raise


def _cand(model: str, cogs: str) -> str:
    return f'{model}/{cogs}'


def _cand_label(model: str, cogs: str) -> str:
    return f"{MODEL_LABEL.get(model, model)} · {COGS_LABEL.get(cogs, cogs)}"


def _candidates(turn: '_Turn') -> tuple[list[dict] | None, ToolResult | None]:
    rows = _ffetch(turn, 'reporting.rpt_forecast_daily',
                   'select model, cogs_method, is_primary, selection_step, model_version, trained_through, run_id, '
                   'interval_level, count(*) as n_days, min(forecast_date) as first_date, max(forecast_date) as last_date '
                   'from reporting.rpt_forecast_daily group by model, cogs_method, is_primary, selection_step, '
                   'model_version, trained_through, run_id, interval_level order by model, cogs_method')
    prim = [r for r in rows if r['is_primary']]
    if not rows:
        return None, ToolResult('no_data', NO_FORECAST)
    if len(prim) != 1 or len({(r['model'], r['cogs_method']) for r in rows}) != len(rows):
        return None, ToolResult('query_error', f'rpt_forecast_daily có {len(prim)} ứng viên is_primary (cần đúng 1) hoặc '
                                'ứng viên trùng metadata; không trả số.')
    return rows, None


def _primary_info(p: dict) -> dict:
    return {'candidate': _cand(p['model'], p['cogs_method']), 'label': _cand_label(p['model'], p['cogs_method']),
            'selection_step': p['selection_step'],
            'selection_reason': SELECTION_REASON.get(p['selection_step'], f"bước {p['selection_step']} (chưa có mô tả)"),
            'model_version': p['model_version'], 'trained_through': p['trained_through']}


# tên họ model người hỏi hay dùng → tiền tố mã ứng viên (live B3c GM11: model='lightgbm'; GM15: "theo SARIMAX")
FAMILY = {'lgbm': 'lgbm', 'lightgbm': 'lgbm', 'sarimax': 'sarimax', 'log sarimax': 'sarimax', 'arima': 'arima',
          'blend': 'blend', 'bản gộp': 'blend', 'ban gop': 'blend', 'ensemble': 'blend'}


def _family(model, rows: list[dict]) -> str | None:
    """Tiền tố họ nếu `model` là TÊN HỌ (không trùng mã ứng viên nào); None nếu là mã ứng viên hoặc tên lạ."""
    if any(r['model'] == model for r in rows):
        return None
    return FAMILY.get(' '.join(str(model).replace('_', ' ').replace('+', ' ').lower().split()))


def _pick(rows: list[dict], a: dict, g_only: bool = False) -> tuple[dict | None, ToolResult | None]:
    """Ứng viên được đọc: mặc định is_primary. Có model / cogs_method thì đúng ứng viên đó, không thay bằng ứng viên khác.
    model là tên họ có nhiều biến thể (cửa sổ train) thì hỏi lại. g_only (chỉ hỏi G): không đòi chọn cách COGS, vì
    G của một model không phụ thuộc cách COGS (_forecast kiểm lại trên dữ liệu trước khi trả số)."""
    prim = next(r for r in rows if r['is_primary'])
    model, cogs = a.get('model'), a.get('cogs_method')
    if model is None and cogs is None:
        return prim, None
    model = model or prim['model']
    if fam := _family(model, rows):
        models = sorted({r['model'] for r in rows if r['model'].startswith(fam + '_')})
        if len(models) > 1:
            return None, ToolResult('needs_clarification', f'Họ model "{model}" có {len(models)} biến thể trong bản dữ liệu: '
                                    + ', '.join(f'{m} ({MODEL_LABEL.get(m, m)})' for m in models)
                                    + '. Cần chọn một biến thể; không tự chọn, không thay bằng model chính.',
                                    missing=['model'])
        model = models[0] if models else model
    hit = [r for r in rows if r['model'] == model and (cogs is None or r['cogs_method'] == cogs)]
    have = ', '.join(_cand(r['model'], r['cogs_method']) for r in rows)
    if not hit:
        return None, ToolResult('no_data', f'Bản dữ liệu không có ứng viên {_cand(model, cogs or "*")}. Các ứng viên có: '
                                f'{have}. Không thay bằng model khác.', rejected={'model': 'không có trong bản dữ liệu'})
    if len(hit) > 1 and g_only:
        return sorted(hit, key=lambda r: (not r['is_primary'], r['cogs_method']))[0], None
    if len(hit) > 1:
        return None, ToolResult('needs_clarification', f'Model {model} có {len(hit)} cách tính COGS: '
                                + ', '.join(f"{r['cogs_method']} ({COGS_LABEL.get(r['cogs_method'], '')})" for r in hit)
                                + '. Cần chọn cogs_method.', missing=['cogs_method'])
    return hit[0], None


def _month_end(y: int, m: int) -> dt.date:
    return (dt.date(y + m // 12, m % 12 + 1, 1) - dt.timedelta(days=1))


def _window(a: dict) -> tuple[tuple | None, ToolResult | None]:
    """(nhãn kỳ, ngày đầu, ngày cuối của kỳ được hỏi) hoặc lỗi. Kiểm kỳ so với kỳ dự báo ở hàm gọi."""
    p, y, m, d = a['period'], a.get('year'), a.get('month'), a.get('day')
    need = {'day': ['year', 'month', 'day'], 'month': ['year', 'month'], 'year': ['year'], 'horizon': []}[p]
    if (miss := [k for k in need if a.get(k) is None]):
        return None, ToolResult('needs_clarification', f'Cần làm rõ: {", ".join(miss)} của kỳ dự báo.', missing=miss)
    if (extra := [k for k in ('year', 'month', 'day') if k not in need and a.get(k) is not None]):
        return None, ToolResult('unsupported', f'period = {p} không đi kèm {", ".join(extra)}.',
                                rejected={k: f'không dùng với period {p}' for k in extra})
    try:
        if p == 'day':
            start = end = dt.date(y, m, d)
            return (f'{d:02d}/{m:02d}/{y}', start, end), None
        if p == 'month':
            if not 1 <= m <= 12:
                raise ValueError
            return (f'{m:02d}/{y}', dt.date(y, m, 1), _month_end(y, m)), None
        if p == 'year':
            return (str(y), dt.date(y, 1, 1), dt.date(y, 12, 31)), None
    except ValueError:
        return None, ToolResult('unsupported', 'Ngày / tháng không hợp lệ.', rejected={'period': 'ngày không có thật'})
    return ('2023-01-01 → 2024-07-01', FORECAST_START, FORECAST_END), None


def _outside(label: str, start: dt.date, end: dt.date) -> ToolResult | None:
    if end < FORECAST_START:
        return ToolResult('unsupported', f'Kỳ {label} nằm trong dữ liệu thực tế (tới 2022-12-31): không có dự báo cho kỳ '
                          'đã qua. Hỏi số thực tế thì dùng các tool số liệu lịch sử. Không đưa dự báo ra làm thực tế.',
                          rejected={'period': 'trước kỳ dự báo'})
    if start > FORECAST_END:
        return ToolResult('no_data', f'Kỳ {label} nằm ngoài kỳ dự báo 2023-01-01 → 2024-07-01 (548 ngày). Không có số dự '
                          'báo cho kỳ này; không ngoại suy thêm.')
    if start < FORECAST_START:
        return ToolResult('unsupported', f'Kỳ {label} có phần trước 2023-01-01 là dữ liệu thực tế: hỏi riêng phần thực tế '
                          'và phần dự báo, không cộng chung.', rejected={'period': 'trộn thực tế và dự báo'})
    return None


def _typical_month_error(turn: '_Turn', c: dict):
    rows = _ffetch(turn, 'reporting.rpt_forecast_backtest',
                   "select fold_origin, value from reporting.rpt_forecast_backtest where model = {p} and cogs_method = {p} "
                   "and metric = 'mape_g_thang' and grain = 'thang'", (c['model'], c['cogs_method']))
    vals = [r['value'] for r in rows if r['value'] is not None]
    return sum(vals) / len(vals) if len(vals) == 3 else None


def _month_metric_note(turn: '_Turn', c: dict) -> list[str]:
    """Câu hỏi dự báo theo tháng / năm: model chính chọn theo điểm NGÀY (Q1, Q8). PM giữ một model chính (2026-10-15) và
    muốn agent nói kèm khi thước tháng xếp model khác tốt hơn. App in ghi chú từ rpt_forecast_backtest (không viết sẵn
    tên model, không chọn lại model); không có khi model chính cũng có MAPE G tháng thấp nhất. G không phụ thuộc cách
    COGS nên so theo model."""
    rows = _ffetch(turn, 'reporting.rpt_forecast_backtest',
                   "select model, cogs_method, avg(value) as value, count(*) as n from reporting.rpt_forecast_backtest "
                   "where role = 'candidate' and metric = 'mape_g_thang' and grain = 'thang' group by model, cogs_method")
    by = {}
    for r in rows:
        if r['value'] is not None and r['n'] == 3:
            by[r['model']] = min(by.get(r['model'], r['value']), r['value'])
    if c['model'] not in by:
        return []
    best = min(by.values())
    hit = sorted(m for m, v in by.items() if v == best)
    if c['model'] in hit:
        return []
    return [f'Theo sai số tháng (MAPE G tháng, backtest 2020–2022), {" / ".join(MODEL_LABEL.get(m, m) for m in hit)} '
            f'sai ít hơn model chính: {_pct1(best)} so với {_pct1(by[c["model"]])}. Model chính được chọn theo điểm ngày '
            'kết hợp (luật chọn chốt trước khi chấm); hỏi "so sánh các model" để xem đủ hai thước.']


def _pct1(v) -> str:
    return f'{float(v):.1f}'.replace('.', ',') + '%'


def _fields(metric: str, g, cogs) -> dict:
    out = {}
    if metric in ('G', 'G_and_COGS'):
        out['g_forecast'] = g
    if metric in ('COGS', 'G_and_COGS'):
        out['cogs_forecast'] = cogs
    if metric == 'G_and_COGS' and g:
        out['cogs_ratio'] = cogs / g
    return out


def _forecast(turn: '_Turn', a: dict) -> ToolResult:
    w, err = _window(a)
    if err:
        return err
    label, start, end = w
    if (err := _outside(label, start, end)):
        return err
    try:
        cands, err = _candidates(turn)
        if err:
            return err
        c, err = _pick(cands, a, g_only=a['metric'] == 'G')
        if err:
            return err
        prim = next(r for r in cands if r['is_primary'])
        key = (c['model'], c['cogs_method'])
        any_cogs = (a.get('model') is not None and a.get('cogs_method') is None
                    and sum(r['model'] == c['model'] for r in cands) > 1)     # chỉ hỏi G, model có nhiều cách COGS
        head = {'candidate': _cand(*key),
                'candidate_label': MODEL_LABEL.get(c['model'], c['model']) if any_cogs else _cand_label(*key),
                'is_primary': c['is_primary'], 'model_version': c['model_version'], 'trained_through': c['trained_through']}
        metric, p = a['metric'], a['period']
        last = min(end, FORECAST_END)
        if any_cogs:
            diff = _ffetch(turn, 'reporting.rpt_forecast_daily',
                           'select count(*) as n from (select forecast_date, max(yhat) - min(yhat) as d '
                           'from reporting.rpt_forecast_daily where model = {p} and forecast_date >= {p} '
                           'and forecast_date <= {p} group by forecast_date) x where d > 0.000001', (c['model'], start, last))
            if diff[0]['n']:
                return ToolResult('needs_clarification', f'G của {c["model"]} khác nhau giữa các cách tính COGS ở '
                                  f'{diff[0]["n"]} ngày: cần chọn cogs_method.', missing=['cogs_method'])
        derived = {'primary': _primary_info(prim), 'selected_is_primary': bool(c['is_primary']),
                   'horizon': '2023-01-01 → 2024-07-01'}
        if any_cogs:
            derived['cogs_method_not_needed'] = 'G của model này như nhau ở mọi cách tính COGS (đã kiểm trên kỳ được hỏi)'
        notes = []
        if p == 'day':
            r = _ffetch(turn, 'reporting.rpt_forecast_daily',
                        'select forecast_date, yhat, lower, upper, cogs_yhat from reporting.rpt_forecast_daily '
                        'where model = {p} and cogs_method = {p} and forecast_date = {p}', (*key, start))
            if len(r) != 1:
                return ToolResult('query_error', f'Ngày {label}: {len(r)} dòng dự báo cho ứng viên, cần 1.')
            r = r[0]
            row = {'period': label, 'year': start.year, 'month': start.month, 'forecast_date': start, **head,
                   **_fields(metric, r['yhat'], r['cogs_yhat'])}
            if 'g_forecast' in row:
                row['lower_g'], row['upper_g'] = r['lower'], r['upper']
            rows = [row]
        else:
            group = p == 'horizon'
            sel = ('extract(year from forecast_date) as y, extract(month from forecast_date) as m, ' if group else '')
            r = _ffetch(turn, 'reporting.rpt_forecast_daily',
                        f'select {sel}count(*) as n_days, sum(yhat) as g, sum(cogs_yhat) as cogs '
                        'from reporting.rpt_forecast_daily where model = {p} and cogs_method = {p} '
                        'and forecast_date >= {p} and forecast_date <= {p}'
                        + (' group by extract(year from forecast_date), extract(month from forecast_date) '
                           'order by y, m' if group else ''), (*key, start, last))
            tme = _typical_month_error(turn, c) if metric != 'COGS' and p in ('month', 'horizon') else None
            notes = _month_metric_note(turn, c) if metric != 'COGS' and c['is_primary'] else []
            rows = []
            for x in r:
                if group:
                    y, m = int(x['y']), int(x['m'])
                    lab, n_all = f'{m:02d}/{y}', _month_end(y, m).day
                    extra = {'year': y, 'month': m}
                else:
                    lab, n_all = label, (end - start).days + 1
                    extra = {'year': start.year, **({'month': start.month} if p == 'month' else {})}
                row = {'period': lab, **extra, **head, **_fields(metric, x['g'], x['cogs']), 'n_days': int(x['n_days']),
                       'n_days_in_period': n_all, 'is_partial': int(x['n_days']) < n_all}
                if tme is not None:
                    row['typical_month_error'] = tme
                rows.append(row)
            expect = (last - start).days + 1
            if sum(x['n_days'] for x in rows) != expect:
                return ToolResult('query_error', f'Kỳ {label}: có {sum(x["n_days"] for x in rows)} ngày dự báo, cần '
                                  f'{expect}; không trả tổng thiếu ngày.')
            if end > FORECAST_END:
                # cụm danh từ (live B3c GM05: câu cũ là cả mệnh đề nên câu trả lời lặp "nằm ngoài kỳ dự báo")
                derived['missing_part'] = (f'{(FORECAST_END + dt.timedelta(days=1)).isoformat()} → {end.isoformat()} '
                                           f'({(end - FORECAST_END).days} ngày)')
            if group:
                tot = {'n_days': sum(x['n_days'] for x in rows)}
                tot.update(_fields(metric, sum(x['g'] for x in r), sum(x['cogs'] for x in r)))
                derived['horizon_total'] = tot
                full = [x for x in rows if not x['is_partial'] and 'g_forecast' in x]
                if full:
                    hi, lo = max(x['g_forecast'] for x in full), min(x['g_forecast'] for x in full)
                    derived['highest_month'] = {'months': [x['period'] for x in full if x['g_forecast'] == hi],
                                                'g_forecast': hi}
                    derived['lowest_month'] = {'months': [x['period'] for x in full if x['g_forecast'] == lo],
                                               'g_forecast': lo}
    except _NoForecast:
        return ToolResult('no_data', NO_FORECAST)
    read_at = _now()
    pi = derived['primary']
    derived['forecast_label'] = (f"Dự báo, {cat.G_LABEL}. Ứng viên: {head['candidate_label']}"
                                 + ('' if c['is_primary'] else ' (không phải model chính)')
                                 + f" · model_version {c['model_version']} · train tới {_iso(c['trained_through'])}"
                                 + (' · khoảng 80% theo ngày' if p == 'day' else
                                    ' · tháng / năm không có khoảng dự báo (Q7), xem sai số tháng điển hình'))
    note = ('' if c['is_primary'] else f" Ứng viên này KHÔNG phải model chính; model chính là {pi['label']}.")
    mids = {'G': ['G_forecast'], 'COGS': ['COGS_forecast'], 'G_and_COGS': ['G_forecast', 'COGS_forecast']}[metric]
    mids += ['forecast_interval'] if p == 'day' and metric != 'COGS' else (['mape_g_thang'] if metric != 'COGS' else [])
    return ToolResult('ok', f'Dự báo ({cat.G_LABEL}) kỳ {label}, đọc từ rpt_forecast_daily của bản dữ liệu đang phục vụ. '
                      'Kỳ dự báo 2023-01-01 → 2024-07-01; số thực tế dừng ở 2022-12-31. Đây là DỰ BÁO, không phải số '
                      'thực tế; không cộng hay so trực tiếp với R thực tế.'
                      + (' Theo ngày có khoảng 80%.' if p == 'day' else ' Tháng / năm không có khoảng dự báo; '
                         'typical_month_error là sai số tháng điển hình (MAPE G tháng, backtest 2020–2022).')
                      + note + f" Lý do chọn model chính: {pi['selection_reason']}",
                      rows=rows, derived=derived, notes=notes, evidence=turn.evidence(
                          filters={'period': p, **{k: a[k] for k in ('year', 'month', 'day') if a.get(k) is not None},
                                   'candidate': head['candidate'], 'forecast_window': f'{start} → {last}'},
                          grain={'day': 'ngày', 'month': 'tháng (cộng các ngày)', 'year': 'năm (cộng các ngày)',
                                 'horizon': 'tháng trong kỳ dự báo (cộng các ngày)'}[p],
                          metrics=cat.metric_defs(*mids), read_at=read_at,
                          method=cat.DECISIONS['forecast_selection_rule']['text']))


EXPLAIN_GROUPS = frozenset({'mua_vu', 'dau_cuoi_thang', 'che_do_sau_2018', 'nam_chan_le',
                            'promo_fall_launch', 'promo_mid_year_sale', 'promo_rural_special',
                            'promo_spring_sale', 'promo_urban_blowout', 'promo_year_end_sale'})
EXPLAIN_LABEL = 'Phân rã model, không phải nguyên nhân'


def _explain_forecast(turn: '_Turn', a: dict) -> ToolResult:
    """Đóng góp log(G) của model chính; tháng là trung bình từng ngày, không phải phần góp VND vào tổng tháng."""
    w, err = _window(a)
    if err:
        return err
    label, start, end = w
    if (err := _outside(label, start, end)):
        return err
    last = min(end, FORECAST_END)
    try:
        candidates, err = _candidates(turn)
        if err:
            return err
        primary = next(c for c in candidates if c['is_primary'])
        # B4a chỉ lưu phân rã cho LightGBM chính. Không mượn phân rã của ứng viên khác.
        if primary['model'] != 'lgbm_full':
            return ToolResult('no_data', 'Model chính của bản dữ liệu này chưa có phân rã trong '
                              'rpt_forecast_explain; không lấy thành phần từ model khác.')
        raw = _ffetch(turn, 'reporting.rpt_forecast_explain',
                      'select feature_group, count(*) as n, count(distinct forecast_date) as n_dates, '
                      'min(expected_groups) as min_groups, max(expected_groups) as max_groups, '
                      'min(model_version) as min_version, max(model_version) as max_version, '
                      'min(run_id) as min_run, max(run_id) as max_run, '
                      'min(trained_through) as min_trained, max(trained_through) as max_trained, '
                      'avg(base_log) as base_log, avg(contribution_log) as contribution_log, '
                      'avg(forecast_log) as forecast_log '
                      'from reporting.rpt_forecast_explain where model = {p} and cogs_method = {p} '
                      'and forecast_date >= {p} and forecast_date <= {p} group by feature_group order by feature_group',
                      (primary['model'], primary['cogs_method'], start, last))
        if not raw:
            return ToolResult('no_data', 'Bản dữ liệu đang phục vụ chưa có phân rã model cho kỳ này; '
                              'không lấy số từ nguồn khác thay vào.')
        days = (last - start).days + 1
        if (len(raw) != len(EXPLAIN_GROUPS) or {r['feature_group'] for r in raw} != EXPLAIN_GROUPS
                or any(r['n'] != days or r['n_dates'] != days or r['min_groups'] != len(EXPLAIN_GROUPS)
                       or r['max_groups'] != len(EXPLAIN_GROUPS) or r['min_version'] != primary['model_version']
                       or r['max_version'] != primary['model_version'] or r['min_run'] != primary['run_id']
                       or r['max_run'] != primary['run_id'] or r['min_trained'] != primary['trained_through']
                       or r['max_trained'] != primary['trained_through'] for r in raw)):
            return ToolResult('query_error', 'Phân rã thiếu ngày / nhóm hoặc không cùng model_version, run_id, '
                              'trained_through với dự báo chính; không trả số.')
        base, target = float(raw[0]['base_log']), float(raw[0]['forecast_log'])
        if (not all(math.isfinite(float(r[k])) for r in raw for k in ('base_log', 'contribution_log', 'forecast_log'))
                or any(abs(float(r['base_log']) - base) > 1e-9 or abs(float(r['forecast_log']) - target) > 1e-9
                       for r in raw)
                or abs(base + sum(float(r['contribution_log']) for r in raw) - target) > 1e-7):
            return ToolResult('query_error', 'Phân rã không đối soát về log(G) dự báo; không trả số.')
        daily = _ffetch(turn, 'reporting.rpt_forecast_daily',
                        'select count(*) as n, avg(ln(yhat)) as forecast_log from reporting.rpt_forecast_daily '
                        'where model = {p} and cogs_method = {p} and forecast_date >= {p} and forecast_date <= {p}',
                        (primary['model'], primary['cogs_method'], start, last))[0]
        if daily['n'] != days or daily['forecast_log'] is None or abs(float(daily['forecast_log']) - target) > 1e-7:
            return ToolResult('query_error', 'Phân rã không khớp dự báo G của cùng bản dữ liệu; không trả số.')
        rows = [{'period': label, 'year': start.year, 'month': start.month,
                 **({'day': start.day} if a['period'] == 'day' else {}), 'feature_group': r['feature_group'],
                 'feature_label': FEATURE_GROUP_LABEL[r['feature_group']],
                 'contribution_log': float(r['contribution_log']), 'multiplier': math.exp(float(r['contribution_log'])),
                 'pct_vs_base': math.expm1(float(r['contribution_log'])) * 100,
                 'n_days': days, 'n_days_in_period': (end - start).days + 1, 'is_partial': last < end,
                 'candidate': _cand(primary['model'], primary['cogs_method']),
                 'model_version': primary['model_version'], 'trained_through': primary['trained_through']}
                for r in raw]
        ranked = sorted(rows, key=lambda r: (-abs(r['contribution_log']), r['feature_label'], r['feature_group']))
        for rank, row in enumerate(ranked, 1):
            row['rank'] = rank
        for direction in (-1, 1):
            directed = [r for r in ranked if r['contribution_log'] * direction > 0]
            for rank, row in enumerate(directed, 1):
                row['rank_dir'] = rank
        for row in rows:
            if row['contribution_log'] == 0:
                row['rank_dir'] = None
        small = [r for r in rows if abs(r['pct_vs_base']) < 1]
    except _NoForecast:
        return ToolResult('no_data', 'Bản dữ liệu đang phục vụ chưa có bảng reporting.rpt_forecast_explain; '
                          'không lấy số từ nguồn khác thay vào.')
    return ToolResult('ok', f'{EXPLAIN_LABEL}. Đóng góp theo nhóm biến cho dự báo G kỳ {label}; '
                      + ('mỗi dòng là một ngày.' if a['period'] == 'day' else
                         'mỗi dòng là trung bình log theo ngày trong tháng, không phải phần góp VND vào tổng tháng.')
                      + (f' Chỉ có {days} ngày đến {last.isoformat()}, không đại diện cả tháng.' if last < end else '')
                      + ' base_log + tổng contribution_log = forecast_log; multiplier = exp(contribution_log), '
                      'các multiplier không cộng được. Đóng góp đo so với mức nền base_log của model, không phải so với '
                      'kỳ trước. pct_vs_base là ảnh hưởng của từng nhóm khi xét riêng, không cộng các %. '
                      'Các nhóm là thành phần của model, không chứng minh nguyên nhân biến động.',
                      rows=rows, derived={'base_log': base, 'forecast_log': target, 'candidate': rows[0]['candidate'],
                                           'small_groups': {'n': len(small), 'threshold_pct': 1.0,
                                                           'max_abs_pct': max((abs(r['pct_vs_base']) for r in small),
                                                                              default=0.0)}},
                      notes=[EXPLAIN_LABEL], evidence=turn.evidence(
                          filters={'period': a['period'], 'forecast_window': f'{start} → {last}',
                                   'candidate': rows[0]['candidate']},
                          grain='ngày' if a['period'] == 'day' else 'tháng (trung bình log theo ngày)',
                          metrics=cat.metric_defs('G_forecast'), read_at=_now(),
                          method='LightGBM pred_contrib trên log(G); nhóm biến cộng trong không gian log. '
                                 'Tháng = trung bình log theo ngày, không phải phân rã tổng VND.'))


_BT_METRICS = ('score', 'mae_g', 'mae_cogs', 'rmse_g', 'r2_g', 'mape_g_thang', 'coverage_80', 'tai_tao_bien_do')


def _forecast_backtest(turn: '_Turn', a: dict) -> ToolResult:
    try:
        cands, err = _candidates(turn)
        if err:
            return err
        agg = _ffetch(turn, 'reporting.rpt_forecast_backtest',
                      'select model, cogs_method, role, candidate_rank, metric, avg(value) as value, count(*) as n_folds '
                      'from reporting.rpt_forecast_backtest where metric in ('
                      + ', '.join('{p}' for _ in _BT_METRICS) + ') group by model, cogs_method, role, candidate_rank, metric',
                      _BT_METRICS)
        folds = _ffetch(turn, 'reporting.rpt_forecast_backtest',
                        "select model, cogs_method, role, fold_origin, value from reporting.rpt_forecast_backtest "
                        "where metric = 'score' order by fold_origin")
        sel, fam = None, None
        if a.get('model') is not None and (fam := _family(a['model'], cands)):
            pass                     # tên họ: trả cả bảng, kèm danh sách biến thể của họ (so sánh họ model, live B3c GM11)
        elif a.get('model') is not None or a.get('cogs_method') is not None:
            sel, err = _pick(cands, a)
            if err:
                return err
    except _NoForecast:
        return ToolResult('no_data', NO_FORECAST)
    read_at = _now()
    floor = {f['fold_origin']: f['value'] for f in folds if f['role'] == 'floor'}
    if len(floor) != 3:
        return ToolResult('query_error', f'rpt_forecast_backtest có {len(floor)} fold của mốc sàn, cần 3.')
    prim = next(r for r in cands if r['is_primary'])
    by: dict = {}
    for x in agg:
        k = (x['model'], x['cogs_method'])
        row = by.setdefault(k, {'candidate': _cand(*k), 'candidate_label': _cand_label(*k), 'role': x['role'],
                                'candidate_rank': x['candidate_rank'], 'is_primary': k == (prim['model'], prim['cogs_method'])})
        row[x['metric']] = x['value']
        if x['metric'] == 'score':
            row['n_folds'] = int(x['n_folds'])
    for k, row in by.items():
        mine = {f['fold_origin']: f['value'] for f in folds if (f['model'], f['cogs_method']) == k}
        row['beats_floor_all_folds'] = (row['role'] != 'floor' and set(mine) == set(floor)
                                        and all(mine[o] < floor[o] for o in floor))
    rows = sorted(by.values(), key=lambda r: (r.get('score') is None, r.get('score')))
    if any(r.get('n_folds') != 3 or r.get('score') is None for r in rows):
        return ToolResult('query_error', 'rpt_forecast_backtest thiếu điểm của ứng viên ở một fold; không xếp hạng trên tập thiếu.')
    cand_rows = [r for r in rows if r['role'] == 'candidate']

    def lowest(metric):
        vals = [r for r in cand_rows if r.get(metric) is not None]
        best = min(r[metric] for r in vals)
        hit = [r['candidate_label'] for r in vals if r[metric] == best]
        return {'candidates': hit, metric: best, 'tie': len(hit) > 1}
    floor_row = next(r for r in rows if r['role'] == 'floor')
    pr = by[(prim['model'], prim['cogs_method'])]
    derived = {
        'primary': {**_primary_info(prim), 'score': pr['score'], 'mape_g_thang': pr.get('mape_g_thang')},
        'floor': {'label': floor_row['candidate_label'], 'score': floor_row['score']},
        'improvement_vs_floor': 1 - pr['score'] / floor_row['score'],
        'lowest_score': lowest('score'), 'lowest_mape_g_thang': lowest('mape_g_thang'),
        'n_candidates': len(cand_rows), 'n_pass_floor': sum(r['beats_floor_all_folds'] for r in cand_rows),
        'tie_rule': 'trong vòng 1% của điểm thấp nhất thì coi là hòa và chọn ứng viên đơn giản hơn',
        'backtest_note': BACKTEST_NOTE,
    }
    derived['rankings_differ'] = set(derived['lowest_score']['candidates']) != set(derived['lowest_mape_g_thang']['candidates'])
    derived['n_folds'] = len(floor)
    if sel is not None:
        derived['selected'] = by[(sel['model'], sel['cogs_method'])]
    if fam is not None:
        derived['family'] = {'name': a['model'],
                             'candidates': [r['candidate_label'] for r in rows if r['candidate'].startswith(fam + '_')]}
    return ToolResult('ok', 'So sánh ứng viên dự báo trên backtest, đọc từ rpt_forecast_backtest. Thước CHỌN model là điểm '
                      'ngày kết hợp (MAE G + MAE COGS) / 2, trung bình 3 fold; MAPE G tháng chỉ để hiển thị, có thể xếp '
                      f'hạng khác. {BACKTEST_NOTE} Model chính: {derived["primary"]["label"]}. '
                      f'{derived["primary"]["selection_reason"]}',
                      rows=rows, derived=derived, notes=[SELECTION_NOTE], evidence=turn.evidence(
                          filters={'backtest': '3 fold, origin 2020-06-30 / 2020-12-31 / 2021-06-30'},
                          grain='ứng viên (trung bình 3 fold)', read_at=read_at,
                          metrics=cat.metric_defs('forecast_score', 'mape_g_thang'),
                          method=cat.DECISIONS['forecast_selection_rule']['text']))


_YEAR = Param('int', 'năm theo ngày đặt hàng, vd. 2019')
_METRIC_RG = Param('enum', 'R (đơn delivered, sau chiết khấu) hay G (mọi đơn, chưa trừ chiết khấu)', ('R', 'G'))

def _search_knowledge(args: dict, backend: str) -> ToolResult:
    """Corpus repo, không mở kết nối DWH; không cấp bất kỳ ô nào cho claims."""
    query, k = args.get('query', ''), args.get('k', knowledge.MAX_RESULTS)
    if not 1 <= k <= knowledge.MAX_RESULTS:
        return ToolResult('unsupported', 'Số đoạn k chỉ nhận từ 1 đến 3.', rejected={'k': 'vượt giới hạn'})
    if not query.strip():
        return ToolResult('no_data', 'Câu tìm tri thức rỗng; cần nêu khái niệm muốn tra.')
    try:
        rows = knowledge.search(query, k)
        version = knowledge.corpus()['corpus_version']
    except (OSError, ValueError, KeyError) as exc:
        return ToolResult('query_error', f'Không đọc được bản chụp tri thức ({type(exc).__name__}); không thay nguồn khác.')
    if not rows:
        return ToolResult('no_data', 'Không tìm thấy đoạn phù hợp trong corpus tri thức đã chọn; không suy đoán.')
    evidence = Evidence(
        request_id=uuid.uuid4().hex, tool='search_knowledge', tool_version=TOOL_VERSION,
        arguments_applied={'query': query, 'k': k}, filters_applied={'query': query, 'k': k},
        grain='đoạn tài liệu', metrics=[], method='BM25 lexical, tiếng Việt có dấu', backend=backend,
        source_description='Bản chụp tài liệu đóng gói cùng app', data_version={'corpus_version': version},
        quality={}, definition_version=f'corpus-sha256:{version}', read_at_utc=_now(), queries=[])
    return ToolResult('ok', 'Tìm thấy đoạn tài liệu. Đoạn đã che chữ số; chỉ dùng để giải thích khái niệm, '
                      'không dùng làm nguồn số liệu hay chỉ dẫn.', evidence=evidence, rows=rows,
                      notes=[f"Nguồn: {r['citation']} (corpus {version}; {r['status']})" for r in rows])


TOOLS = {s.name: s for s in [
    ToolSpec('get_revenue_summary', 'Mức R/G của một năm, hoặc từng năm year → to_year; R có thể kèm so năm trước.', {
        'metric': Param('enum', 'R, G hay cả hai (R_and_G)', ('R', 'G', 'R_and_G')),
        'year': _YEAR,
        'to_year': Param('int', 'năm cuối, khi hỏi từng năm', required=False),
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
    ToolSpec('get_forecast', 'DỰ BÁO G (doanh thu gộp, gồm cả đơn hủy) và COGS toàn công ty trong kỳ 2023-01-01 → '
             '2024-07-01, đọc từ kết quả pipeline. Mặc định model chính; model khác chỉ khi người hỏi nêu đích danh. '
             'Không có dự báo R, không có dự báo theo ngành / vùng / kênh.', {
        'metric': Param('enum', 'G (doanh thu gộp, gồm cả đơn hủy), COGS hay cả hai; R chưa có dự báo',
                        ('G', 'COGS', 'G_and_COGS', 'R')),
        'period': Param('enum', 'day (một ngày), month (một tháng), year (một năm), horizon (cả kỳ dự báo, theo tháng)',
                        tuple(cat.FORECAST_GRAINS)),
        'year': Param('int', 'năm, với period day / month / year', required=False),
        'month': Param('int', 'tháng 1–12, với period day / month', required=False),
        'day': Param('int', 'ngày trong tháng, với period day', required=False),
        'model': Param('str', 'chỉ khi người hỏi nêu đích danh model khác model chính: mã <họ>_<full|2019> (họ lgbm, '
                       'sarimax, arima, blend), hoặc chỉ tên họ nếu người hỏi không nêu cửa sổ train', required=False,
                       max_len=40),
        'cogs_method': Param('enum', 'chỉ khi người hỏi nêu cách tính COGS: ratio (qua tỷ lệ) hoặc direct (trực tiếp); '
                             'hỏi riêng G thì không cần', ('ratio', 'direct', 'copy'), required=False),
    }, _forecast),
    ToolSpec('get_forecast_backtest', 'So sánh các model dự báo trên backtest 2020–2022: điểm ngày kết hợp (thước chọn '
             'model), MAPE G tháng (hiển thị), sàn seasonal naive 2 năm, model chính và lý do chọn. Dùng cho "model nào '
             'chính xác nhất", "vì sao chọn model này", "model X sai số bao nhiêu".', {
        'model': Param('str', 'tùy chọn: mã ứng viên hoặc tên họ được hỏi; so hai họ thì không truyền', required=False,
                       max_len=40),
        'cogs_method': Param('enum', 'tùy chọn: ratio / direct / copy', ('ratio', 'direct', 'copy'), required=False),
    }, _forecast_backtest),
    ToolSpec('explain_forecast', 'Phân rã model chính LightGBM theo nhóm biến cho dự báo G một ngày hoặc một tháng '
             'trong 2023-01-01 → 2024-07-01. Đóng góp ở thang log, tháng là trung bình ngày; '
             'không suy ra nguyên nhân. Không dùng để giải thích COGS hay model khác.', {
        'period': Param('enum', 'day (một ngày) hoặc month (một tháng)', ('day', 'month')),
        'year': Param('int', 'năm trong vùng dự báo'),
        'month': Param('int', 'tháng 1–12'),
        'day': Param('int', 'ngày trong tháng, chỉ với period day', required=False),
    }, _explain_forecast),
    ToolSpec('search_knowledge', 'Tra định nghĩa, quy ước PS, data dictionary, kết luận nghiên cứu và hợp đồng dự báo '
             'trong corpus tài liệu tuyển chọn. Trả đoạn và nguồn; tuyệt đối không cấp số liệu.', {
        'query': Param('str', 'cụm khái niệm cần tìm, tối đa 180 ký tự', max_len=180, allow_empty=True),
        'k': Param('int', 'số đoạn, từ 1 đến 3', required=False, default=3),
    }, _search_knowledge),
]}


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


@releases.pinned_read
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
    if spec.name == 'search_knowledge':
        return _search_knowledge(args, backend)
    try:
        sess = open_session(backend, ALLOWED_RELATIONS, timeout_s=timeout_s, max_rows=max_rows,
                            optional_relations=OPTIONAL_RELATIONS)
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
        # cùng phạm vi quyền với run(): thiếu optional thì quyền đọc rpt_forecast_* của bản pipeline bị coi là thừa (GuardError)
        sess = open_session(backend, ALLOWED_RELATIONS, optional_relations=OPTIONAL_RELATIONS)
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
