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
CATALOG_VERSION = 'ai1-2026-10-05'
MONEY_UNIT = 'VND'

# SQL quyết định định nghĩa các metric đang mở. Hash = nội dung các file này trong CHECKOUT hiện tại.
DEFINITION_FILES = (
    'retail_dbt/macros/reporting.sql',
    'retail_dbt/models/reporting/int_reporting_order_items.sql',
    'retail_dbt/models/reporting/rpt_revenue_yearly.sql',
    'retail_dbt/models/reporting/rpt_driver_period.sql',
    'retail_dbt/models/reporting/rpt_revenue_segment_yearly.sql',
    'retail_dbt/seeds/driver_rule.csv',
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
        'text': 'PS3: năm ranh giới thuộc giai đoạn kết thúc ở năm đó. Tool PS3 chưa mở trong v1.',
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
    ('get_revenue_trend / get_calendar_pattern / get_revenue_gap', '*', '*', '*', '*', 'closed',
     'PS1 bridge, PS2, PS3: chưa mở ở lát cắt AI1'),
    ('*', '*', 'sau 2022-12-31', '*', '*', 'closed', 'ngoài coverage; sample_submission không phải dự báo'),
]


# Định nghĩa chỉ tiêu ("R là gì"): đọc từ catalog này, không đọc số; vẫn qua cổng chất lượng của kho như mọi tool.
CAPABILITIES += [('get_metric_definition', m, 'không kỳ', 'định nghĩa', None, 'open', 'định nghĩa từ catalog, không có số')
                 for m in METRICS]


def open_capabilities() -> list[tuple]:
    return [c for c in CAPABILITIES if c[5] == 'open']


def capability_blockers(tool: str, arguments: dict) -> list[str]:
    """Kiểm tổ hợp sau kiểm kiểu. Thiếu dòng catalog cũng là đóng; R_and_G cần cả R và G.

    So năm trước cần cả quyền đọc mức năm lẫn quyền so sánh. Coverage thực tế vẫn do tool kiểm sau khi đọc build.
    Schema và dispatcher dùng chung hàm này, không coi từng enum hợp lệ là đủ để mở một tổ hợp.
    """
    grain = {'get_revenue_summary': 'năm', 'get_revenue_drivers': 'năm',
             'get_segment_contribution': 'chiều × nhóm × năm', 'get_metric_definition': 'định nghĩa'}.get(tool)
    if grain is None:
        return ['tool chưa có ánh xạ grain trong catalog']
    metrics = ('R', 'G') if arguments.get('metric') == 'R_and_G' else (arguments.get('metric'),)
    periods = ['không kỳ'] if tool == 'get_metric_definition' else [arguments.get('period_type', 'year')]
    if tool == 'get_revenue_summary' and arguments.get('compare_prior_year', False):
        periods.append('year_vs_prior')
    if tool == 'get_revenue_drivers' and periods == ['phase']:
        grain = 'giai đoạn PS2'
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
