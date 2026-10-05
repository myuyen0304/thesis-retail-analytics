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
from dwh.guarded import (DEFAULT_MAX_ROWS, DEFAULT_TIMEOUT_S, GuardError, QueryTimeout, RowLimitExceeded, Statement,
                         open_session)

TOOL_VERSION = 'v1.1'
ALLOWED_RELATIONS = frozenset({
    'reporting.rpt_build_info', 'reporting.rpt_health_summary', 'reporting.rpt_revenue_yearly',
    'reporting.rpt_driver_period', 'reporting.rpt_revenue_segment_yearly', 'reporting.driver_rule',
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
]}


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def run(call: ToolCall | dict, backend: str, *, timeout_s: float = DEFAULT_TIMEOUT_S,
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
        return turn.snapshot() or spec.handler(turn, args)
    except QueryTimeout as e:
        return ToolResult('query_error', f'Truy vấn quá thời gian ({e}); không trả số thay thế.')
    except RowLimitExceeded as e:
        return ToolResult('query_error', f'{e}; không cắt bớt để xếp hạng trên tập thiếu.')
    except Exception as e:
        return ToolResult('query_error', f'Truy vấn lỗi: {type(e).__name__}. Không trả số.')
    finally:
        sess.close()


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
