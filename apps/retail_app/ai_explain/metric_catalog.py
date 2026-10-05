"""Catalog metric và ma trận khả năng cho chat PS1–PS5 (docs/ai_explain_plan.md §11.1, docs/star_schema.md §3).

Định nghĩa lấy từ hợp đồng KPI và SQL đã kiểm (retail_dbt/macros/reporting.sql, models/reporting/*), không sáng tác.
`decision_status`:
- 'chot'    : định nghĩa trong hợp đồng KPI / PM-BA đã chốt;
- 'de_xuat' : quy ước dev đề xuất, còn chờ PM/BA chốt (dwh_huong_dan_pm_ba.md §9 M3/M4). Bằng chứng phải mang nhãn này.

Đơn vị tiền: VND (PM chốt 2026-10-05, DECISIONS["currency_vnd"]). Nguồn không ghi đơn vị; đây là quy ước PM.
Không ghi USD hay đơn vị khác.
"""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CATALOG_VERSION = 'ai3-2026-10-05'
MONEY_UNIT = 'VND'

# SQL quyết định định nghĩa các metric đang mở. Hash = nội dung các file này trong CHECKOUT hiện tại.
DEFINITION_FILES = (
    'retail_dbt/macros/reporting.sql',
    'retail_dbt/models/reporting/int_reporting_order_items.sql',
    'retail_dbt/models/reporting/rpt_revenue_yearly.sql',
    'retail_dbt/models/reporting/rpt_driver_period.sql',
    'retail_dbt/models/reporting/rpt_revenue_segment_yearly.sql',
    'retail_dbt/seeds/driver_rule.csv',
    # AI3: PS1–PS3
    'retail_dbt/models/reporting/rpt_revenue_total.sql',
    'retail_dbt/models/reporting/rpt_revenue_bridge.sql',
    'retail_dbt/models/reporting/rpt_revenue_monthly.sql',
    'retail_dbt/models/reporting/rpt_revenue_phase.sql',
    'retail_dbt/models/reporting/rpt_revenue_turning_point.sql',
    'retail_dbt/seeds/ps2_phases.csv',
    'retail_dbt/models/reporting/rpt_august_parity.sql',
    'retail_dbt/models/reporting/rpt_calendar_phase_month.sql',
    'retail_dbt/models/reporting/rpt_calendar_phase.sql',
    'retail_dbt/models/reporting/rpt_calendar_stability.sql',
)


def definition_version() -> str:
    """sha256 (12 ký tự) của DEFINITION_FILES, bỏ khác biệt CRLF/LF. Không chứng minh DB đã build từ bản này."""
    h = hashlib.sha256()
    for f in DEFINITION_FILES:
        h.update(f.encode())
        h.update((ROOT / f).read_bytes().replace(b'\r\n', b'\n'))
    return f'sql-sha256:{h.hexdigest()[:12]}'


def _m(metric_id, label, aliases, unit, formula, additivity, decision_status='chot', note='', sources=()):
    return {'metric_id': metric_id, 'label_vi': label, 'aliases_vi': aliases, 'unit': unit, 'formula': formula,
            'additivity': additivity, 'null_rule': 'mẫu số 0 hoặc thiếu kỳ gốc → NULL, không thay bằng 0',
            'decision_status': decision_status, 'note': note, 'sources': list(sources)}


_Y = 'reporting.rpt_revenue_yearly'
_D = 'reporting.rpt_driver_period'
_S = 'reporting.rpt_revenue_segment_yearly'
_T = 'reporting.rpt_revenue_total'
_B = 'reporting.rpt_revenue_bridge'
_M = 'reporting.rpt_revenue_monthly'
_PH = 'reporting.rpt_revenue_phase'
_TP = 'reporting.rpt_revenue_turning_point'
_AP = 'reporting.rpt_august_parity'
_CP = 'reporting.rpt_calendar_phase'
_CS = 'reporting.rpt_calendar_stability'

METRICS = {m['metric_id']: m for m in [
    _m('G', 'G — doanh thu gộp', ['doanh thu gộp', 'tiền hàng mọi đơn'], MONEY_UNIT,
       'SUM(quantity × unit_price), mọi trạng thái đơn, theo ngày đặt hàng', 'cộng qua tập dòng không giao nhau',
       note='Đối chứng sales.csv.Revenue. Không phải R.', sources=[_Y]),
    _m('R', 'R — doanh thu thực nhận', ['doanh thu thuần', 'doanh thu đơn đã giao'], MONEY_UNIT,
       'SUM(quantity × unit_price − discount_amount), chỉ order_status = delivered, theo ngày đặt hàng',
       'cộng qua tập dòng không giao nhau',
       note='Đơn returned bị loại cả đơn, không trừ refund thêm. Không phải dòng tiền theo ngày thanh toán.',
       sources=[_Y, _D, _S]),
    _m('N', 'N — số đơn', ['số đơn'], 'đơn', 'COUNT DISTINCT order_id, chỉ delivered',
       'không cộng qua category; cộng được qua kỳ ngày đặt không giao nhau', sources=[_Y, _D]),
    _m('Q', 'Q — số món', ['số món', 'số lượng'], 'món', 'SUM(quantity), chỉ delivered', 'như R', sources=[_Y]),
    _m('C', 'C — số khách', ['số khách'], 'khách', 'COUNT DISTINCT customer_sk, chỉ delivered',
       'KHÔNG cộng qua năm, tháng, nhóm hàng', note='C giảm chưa chứng minh churn.', sources=[_Y]),
    _m('U', 'U — số món mỗi đơn', ['món mỗi đơn'], 'món/đơn', 'Q / N', 'tính lại tử/mẫu', sources=[_Y, _D]),
    _m('P', 'P — giá thực thu TB mỗi món', ['giá mỗi món'], f'{MONEY_UNIT}/món', 'R / Q', 'tính lại tử/mẫu',
       sources=[_Y, _D]),
    _m('delta_r', 'ΔR — R đổi so năm trước', ['R tăng/giảm bao nhiêu'], MONEY_UNIT, 'R_năm − R_năm trước',
       'cộng qua năm liên tiếp', note='Chỉ từ 2014 (2012 thiếu tháng, 2013 không có năm gốc đủ).', sources=[_Y, _D, _S]),
    _m('yoy_rate', '% đổi R so năm trước', ['tăng trưởng R', 'YoY'], 'tỷ lệ (0,1 = 10%)', 'R / R_năm trước − 1',
       'không cộng', note='Chỉ từ 2014.', sources=[_Y, _S]),
    _m('contrib_nup', 'Phần góp N / U / P vào ΔR', ['do số đơn', 'do số món', 'do giá'], MONEY_UNIT,
       'ΔR_N=(N1−N0)·U0·P0; ΔR_U=N1·(U1−U0)·P0; ΔR_P=N1·U1·(P1−P0)', 'ba phần cộng đúng bằng ΔR',
       note='Phân rã số học theo thứ tự N → U → P, phụ thuộc thứ tự, KHÔNG chứng minh nguyên nhân. '
            '% đổi N/U/P không cộng thành % đổi R.', sources=[_D]),
    _m('share', 'Tỷ trọng nhóm trong R cùng năm', ['tỷ trọng'], 'tỷ lệ', 'R_nhóm / R_toàn công ty cùng năm',
       'các nhóm của MỘT chiều cộng = 1', sources=[_S]),
    _m('share_shift_pp', 'Đổi tỷ trọng', ['đổi tỷ trọng'], 'điểm % (đã nhân 100)', '(share − share năm trước) × 100',
       'không nhân 100 lần nữa', sources=[_S]),
    _m('contribution_to_delta', '% đóng góp vào ΔR toàn công ty', ['đóng góp vào mức giảm'], 'tỷ lệ',
       'ΔR_nhóm / ΔR_toàn công ty', 'các nhóm của MỘT chiều cộng = 1',
       note='Có thể âm hoặc > 100%; không clip. Mẫu số luôn là ΔR toàn công ty.', sources=[_S]),
    # --- AI3: PS1 (G → R, tháng), PS2 (giai đoạn), PS3 (nhịp lịch) ---
    _m('gap_components', 'Khoản chênh G − R', ['G hụt sang R', 'thất thoát', 'đơn hủy', 'đơn trả', 'chiết khấu'],
       MONEY_UNIT, 'G − R = tiền hàng đơn hủy + tiền hàng đơn trả + tiền hàng đơn chưa giao (created/paid/shipped) '
       '+ chiết khấu của đơn đã giao', 'bốn khoản cộng đúng bằng G − R',
       note='Đơn trả đã bị loại khỏi R, không trừ refund thêm. Tỷ trọng mỗi khoản tính trên G cùng kỳ.',
       sources=[_Y, _T, _B]),
    _m('capture_rate', 'R/G — tỷ lệ thực nhận', ['tỷ lệ thực nhận', 'R trên G'], 'tỷ lệ', 'R / G cùng kỳ',
       'không cộng; tính lại từ tử/mẫu', sources=[_Y, _T, _M]),
    _m('month_index', 'Chỉ số tháng', ['chỉ số mùa vụ', 'month index'], 'lần (1 = tháng bình thường)',
       'R tháng ÷ (R cả năm ÷ 12)', 'không cộng', note='Chỉ năm đủ 2013–2022.', sources=[_M]),
    _m('yoy_month', '% đổi R so cùng tháng năm trước', ['cùng kỳ tháng'], 'tỷ lệ', 'R tháng / R cùng tháng năm trước − 1',
       'không cộng', note='Từ tháng 08/2013 (07/2012 thiếu ba ngày đầu).', sources=[_M]),
    _m('phase', 'Giai đoạn doanh thu PS2', ['giai đoạn'], 'giai đoạn',
       'mốc năm đủ do PM/BA chốt 2026-09-27 (seed ps2_phases); hai giai đoạn liền nhau dùng chung năm ranh giới',
       'không cộng ΔR các giai đoạn thành cả kỳ',
       note='Giai đoạn chỉ mô tả R lên hay xuống, không phải nguyên nhân. Năm 2022 tăng lại chưa tách thành giai đoạn '
            'mới (mới một năm). Không trình bày một CAGR cả 10 năm như một xu hướng.', sources=[_PH]),
    _m('cagr', 'CAGR giai đoạn', ['tăng trưởng kép', 'tăng trưởng bình quân năm'], 'tỷ lệ mỗi năm',
       '(R năm cuối ÷ R năm đầu)^(1/n) − 1, n = năm cuối − năm đầu', 'không cộng', sources=[_PH]),
    _m('turn_magnitude', 'Độ lớn cú đổi hướng', ['điểm đổi hướng', 'điểm gãy'], 'tỷ lệ',
       'R 12 tháng sau điểm ÷ R 12 tháng trước điểm − 1 (điểm đặt ở ranh giới năm)', 'không cộng',
       note='Ghi chú "giảm tăng tốc", "đổi nhịp" là nhận định BA, PM chốt 2026-09-28.', sources=[_TP]),
    _m('season_ratio', 'Chênh mùa cao/thấp', ['mùa vụ', 'tháng cao điểm'], 'lần',
       'chỉ số tháng cao nhất ÷ thấp nhất (R các tháng cùng tên cộng qua các năm)', 'không cộng', sources=[_CP, _CS]),
    _m('eom_excess', 'Mức dồn cuối tháng', ['cuối tháng', 'ngày 26 trở đi'], 'điểm %',
       'tỷ trọng R từ ngày 26 − tỷ trọng kỳ vọng nếu rải đều (D − 25)/D, gia quyền theo R tháng', 'không cộng',
       note='> 0 là dồn về cuối tháng.', sources=[_T, _CP, _CS]),
    _m('august_odd_vs_even', 'Chênh tháng 8 năm lẻ / năm chẵn', ['tháng 8 năm lẻ', 'Urban Blowout'], 'tỷ lệ',
       'TB chỉ số tháng 8 các năm lẻ ÷ TB các năm chẵn − 1 (2013–2022)', 'không cộng',
       note='Mô tả lịch sử 2013–2022, không phải dự báo cho năm sau 2022.', sources=[_AP, _CS]),
]}

# Quy ước còn chờ PM/BA chốt mà kết quả tool có thể chạm tới
DECISIONS = {
    'driver_small_delta_rule': {
        'decision_status': 'de_xuat',
        'text': 'delta_r_is_small = |ΔR| < min_abs_delta_rate × R đầu kỳ, seed driver_rule (hiện 0,01). '
                'Ngưỡng dev đề xuất, không phải ngưỡng thống kê đã chứng minh; khi cờ bật nên đọc số tiền, không đọc %.',
        'source': 'retail_dbt/seeds/driver_rule.csv',
    },
    'driver_phase_sum_of_years': {
        'decision_status': 'de_xuat',
        'text': 'Phân rã theo giai đoạn = cộng phần góp từng năm (khác phân rã một lần đầu → cuối). Chưa mở trong v1.',
        'source': 'retail_dbt/models/reporting/rpt_driver_period.sql',
    },
    'ps3_boundary_year': {
        'decision_status': 'de_xuat',
        'text': 'PS3 gom năm lịch theo giai đoạn: năm ranh giới tính cho giai đoạn KẾT THÚC ở năm đó (A 2013–2016, '
                'B 2017–2018, C 2019, D 2020–2022), khác cách PS2 dùng chung năm ranh giới. Quy ước dev, chờ BA chốt.',
        'source': 'retail_dbt/models/reporting/rpt_calendar_phase.sql',
    },
    'currency_vnd': {
        'decision_status': 'chot',
        'text': 'Mọi số tiền (R, G, ΔR, phần góp, P) ghi bằng VND (đồng). Dữ liệu nguồn không ghi đơn vị; PM chốt '
                'ngày 2026-10-05. Không ghi hay quy đổi sang đơn vị tiền tệ khác.',
        'source': 'docs/dwh_huong_dan_pm_ba.md §2, §9 (2026-10-05)',
    },
}

DIMENSIONS = {
    'category': 'ngành hàng của sản phẩm (dim_product)',
    'region': 'vùng của KHÁCH theo snapshot (dim_customer → dim_geography), không phải nơi giao hàng',
    'acquisition_channel': 'kênh thu hút khách (dim_customer), không phải order_source hay kênh marketing tạo doanh thu',
}

# Ma trận khả năng: tổ hợp tool × metric × kỳ × grain × chiều. Chỉ dòng 'open' được tools.run thực thi.
CAPABILITIES = [
    # tool, metric, period, grain, dimension, status, ghi chú / lý do
    ('get_revenue_summary', 'R', 'year', 'năm', None, 'open', 'mức R; so năm trước từ 2014'),
    ('get_revenue_summary', 'R', 'year_vs_prior', 'năm', None, 'open', 'so năm trước từ 2014'),
    ('get_revenue_summary', 'G', 'year', 'năm', None, 'open', 'chỉ mức G; G so năm trước chưa có cột đã kiểm'),
    ('get_revenue_drivers', 'R', 'year', 'năm', None, 'open', 'phân rã N → U → P, từ 2014'),
    ('get_segment_contribution', 'R', 'year', 'chiều × nhóm × năm', 'category', 'open', 'ΔR, tỷ trọng, % đóng góp'),
    ('get_segment_contribution', 'R', 'year', 'chiều × nhóm × năm', 'region', 'open', 'như category'),
    ('get_segment_contribution', 'R', 'year', 'chiều × nhóm × năm', 'acquisition_channel', 'open', 'như category'),
    ('get_revenue_summary', 'G', 'year_vs_prior', 'năm', None, 'closed', 'chưa có G năm trước / ΔG đã kiểm'),
    ('get_revenue_drivers', 'G', 'year', 'năm', None, 'closed', 'phân rã N/U/P chỉ tính cho R'),
    ('get_revenue_drivers', 'R', 'phase', 'giai đoạn PS2', None, 'closed', 'phương pháp cộng dồn năm chờ PM/BA chốt'),
    ('get_segment_contribution', 'G', 'year', 'chiều × nhóm × năm', '*', 'closed', 'segment chỉ có R'),
    ('get_segment_contribution', 'R', 'year', 'nhiều chiều giao nhau', 'category × region', 'closed',
     'cần query detail M6 đã nghiệm thu'),
    ('*', '*', 'khoảng ngày tùy ý', '*', '*', 'closed', 'cần query detail M6 đã nghiệm thu'),
    ('*', 'C', 'nhiều năm gộp', '*', '*', 'closed', 'C không cộng qua năm; chưa có query C cho kỳ gộp'),
    ('get_order_drivers', 'N', 'year', 'năm', None, 'closed', 'C/F có trong rpt_driver_period; tool chưa mở ở AI1'),
    ('get_revenue_trend', 'R', 'direction_changes', 'giai đoạn PS2', None, 'closed',
     'tháng đổi hướng do dữ liệu tự tìm (R 12 tháng): tiêu chí thăm dò, chưa mở cho chat'),
    ('*', '*', 'nhiều tháng / quý / khoảng ngày', '*', '*', 'closed', 'chỉ có từng tháng hoặc từng năm; chưa gộp kỳ tùy ý'),
    ('*', '*', 'sau 2022-12-31', '*', '*', 'closed', 'ngoài coverage; sample_submission không phải dự báo'),
]


# Định nghĩa chỉ tiêu ("R là gì"): đọc từ catalog này, không đọc số; vẫn qua cổng chất lượng của kho như mọi tool.
CAPABILITIES += [('get_metric_definition', m, 'không kỳ', 'định nghĩa', None, 'open', 'định nghĩa từ catalog, không có số')
                 for m in METRICS]

# AI3 (2026-10-05): PS1–PS3, chỉ đọc bảng reporting đã có test dbt; số đối chứng CSV ở tests/test_ai_tools.py.
CAPABILITIES += [
    ('get_revenue_gap', 'G_to_R', 'year', 'kỳ', None, 'open', 'thác G → R một năm (2012 thiếu nửa năm)'),
    ('get_revenue_gap', 'G_to_R', '2013-2022', 'kỳ', None, 'open', 'thác G → R cả kỳ phân tích 2013–2022'),
    ('get_revenue_monthly', 'R', 'month', 'tháng', None, 'open',
     'R một tháng; so cùng tháng năm trước từ 08/2013; chỉ số tháng cho năm đủ'),
    ('get_revenue_monthly', 'G', 'month', 'tháng', None, 'open', 'G một tháng (chưa có G so cùng kỳ)'),
    ('get_revenue_trend', 'R', 'phases', 'giai đoạn PS2', None, 'open', '4 giai đoạn PM/BA chốt 2026-09-27'),
    ('get_revenue_trend', 'R', 'turning_points', 'giai đoạn PS2', None, 'open', '3 điểm đổi hướng giữa các giai đoạn'),
    ('get_calendar_pattern', 'R', 'mua_vu', 'nhịp lịch', None, 'open',
     'chênh mùa 2013–2022 + tháng cao/thấp nhất từng giai đoạn (năm ranh giới PS3: đề xuất)'),
    ('get_calendar_pattern', 'R', 'cuoi_thang', 'nhịp lịch', None, 'open', 'dồn cuối tháng 2013–2022 + từng giai đoạn'),
    ('get_calendar_pattern', 'R', 'thang_8', 'nhịp lịch', None, 'open', 'tháng 8 năm lẻ / năm chẵn 2013–2022'),
]


def _capability_key(tool: str, arguments: dict) -> tuple[str | None, tuple, list]:
    """(grain, các metric, các kỳ) của một lời gọi, để tra CAPABILITIES. grain None = tool chưa có trong catalog."""
    a = arguments
    if tool == 'get_revenue_summary':
        periods = ['year'] + (['year_vs_prior'] if a.get('compare_prior_year', False) else [])
        return 'năm', _metrics(a.get('metric')), periods
    if tool == 'get_revenue_drivers':
        phase = a.get('period_type', 'year') == 'phase'
        return ('giai đoạn PS2' if phase else 'năm'), _metrics(a.get('metric')), [a.get('period_type', 'year')]
    if tool == 'get_segment_contribution':
        return 'chiều × nhóm × năm', _metrics(a.get('metric')), [a.get('period_type', 'year')]
    if tool == 'get_metric_definition':
        return 'định nghĩa', (a.get('metric'),), ['không kỳ']
    if tool == 'get_revenue_gap':
        return 'kỳ', ('G_to_R',), [a.get('period')]
    if tool == 'get_revenue_monthly':
        return 'tháng', _metrics(a.get('metric')), ['month']
    if tool == 'get_revenue_trend':
        return 'giai đoạn PS2', ('R',), [a.get('view')]
    if tool == 'get_calendar_pattern':
        return 'nhịp lịch', ('R',), [a.get('pattern')]
    return None, (), []


def _metrics(metric) -> tuple:
    return ('R', 'G') if metric == 'R_and_G' else (metric,)


def open_capabilities() -> list[tuple]:
    return [c for c in CAPABILITIES if c[5] == 'open']


def capability_blockers(tool: str, arguments: dict) -> list[str]:
    """Kiểm tổ hợp sau kiểm kiểu. Thiếu dòng catalog cũng là đóng; R_and_G cần cả R và G.

    So năm trước cần cả quyền đọc mức năm lẫn quyền so sánh. Coverage thực tế vẫn do tool kiểm sau khi đọc build.
    Schema và dispatcher dùng chung hàm này, không coi từng enum hợp lệ là đủ để mở một tổ hợp.
    """
    grain, metrics, periods = _capability_key(tool, arguments)
    if grain is None:
        return ['tool chưa có ánh xạ grain trong catalog']
    blockers = []
    for metric in metrics:
        for period in periods:
            key = (tool, metric, period, grain, arguments.get('dimension'))
            matches = [c for c in CAPABILITIES if c[:5] == key]
            # Không mở nếu catalog bị trùng hoặc có trạng thái chưa xác định.
            if len(matches) != 1 or matches[0][5] != 'open':
                reason = matches[0][6] if len(matches) == 1 else 'tổ hợp chưa được mở duy nhất trong catalog'
                blockers.append(f'{tool} / {metric} / {period} / {arguments.get("dimension")}: {reason}')
    return blockers


def metric_defs(*metric_ids: str) -> list[dict]:
    return [METRICS[m] for m in metric_ids]
