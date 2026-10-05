"""Kiểm câu trả lời của LLM trước khi hiện (docs/ai_explain_plan.md §5 "Câu trả lời", §11.2; case E21).

Hợp đồng: model KHÔNG viết số. Mỗi con số là một claim trỏ vào kết quả tool của chính lượt đó:
    {"id": "c1", "path": "T1.rows[0].delta_r", "sign": "am"}
    {"id": "c2", "path": "T2.derived.largest_decrease.groups"}
    {"id": "c3", "path": "T2.rows[Streetwear].contribution_to_delta"}
và câu văn chỉ chứa chỗ đặt `{c1}`. App tra giá trị thật rồi định dạng; model không tự điền số.

Chỉ claim có chỗ đặt `{cX}` trong câu văn mới được kiểm và tính; claim khai báo mà không dùng bị bỏ qua.
Bị chặn (answer_validation_failed) khi:
- tham chiếu kết quả không có / không `ok`, dòng hoặc trường không có, giá trị NULL, hoặc trỏ vào cả một khối
  (dict / danh sách không phải giá trị đơn) thay vì một ô;
- câu văn có chữ số ngoài năm của bằng chứng, số trong thông báo của app và mốc ngày/tháng người dùng tự gõ
  (số bịa, số tự tính). Số đứng trước đơn vị (tỷ, triệu, VND, %...) luôn bị chặn, kể cả khi trùng một năm;
- `sign` sai dấu thật, hoặc chữ "tăng"/"giảm" ngay trước số ngược dấu thật;
- vế câu gọi tên R mà số là G, hoặc ngược lại;
- câu có từ xếp hạng ("nhiều nhất", "chủ yếu"...) mà CHÍNH câu đó không có chỗ đặt trỏ vào phần xếp hạng tính trên
  đủ tập (`derived.largest_*`, `top_*_driver`), hoặc hướng xếp hạng ngược chữ tăng/giảm của câu;
- tên nhóm (ngành hàng, khu vực, kênh) viết thẳng mà không gắn với claim đã dùng (rows[<nhóm>] hoặc danh sách nhóm
  của claim xếp hạng): giá trị đúng ở một ô không chứng minh câu văn nói đúng nhóm;
- câu so sánh ("cao hơn", "thấp hơn"...) không dẫn số thay đổi do tool tính;
- chỗ đặt `{cX}` không có claim tương ứng.
Mỗi số hiện kèm nhãn do app dựng từ chính ô dữ liệu (chỉ tiêu, nhóm, năm), trừ khi vế câu đã ghi đúng các thông tin
đó. Không kiểm được mọi nhận định bằng lời; phần đó thuộc live eval (§13).
"""
import re
from dataclasses import dataclass, field
from numbers import Number

from ui.fmt import num, pct

MONEY = {'r', 'g', 'r_prior_year', 'delta_r', 'r_start', 'r_end', 'contrib_n', 'contrib_u', 'contrib_p', 'r_total',
         'additive_check',
         # AI3: PS1 G → R, tháng; PS2 điểm đổi hướng
         'cancelled_gross', 'returned_gross', 'undelivered_gross', 'delivered_discount', 'gap_g_minus_r', 'amount',
         'r_same_month_prior_year', 'r_12m_before', 'r_12m_after'}
PRICE = {'p_start', 'p_end'}
RATE = {'yoy_rate', 'share', 'contribution_to_delta', 'r_change_rate', 'n_change_rate', 'u_change_rate', 'p_change_rate',
        'capture_rate', 'share_cancelled', 'share_returned', 'share_undelivered', 'share_discount',
        'total_change_rate', 'cagr', 'magnitude', 'august_odd_vs_even', 'loo_min_odd_vs_even', 'loo_max_odd_vs_even',
        'eom_share', 'eom_expected_share'}
PP = {'share_shift_pp'}
PP_FRAC = {'eom_excess', 'loo_min_eom_excess', 'loo_max_eom_excess'}     # hiệu hai tỷ lệ (0,0718) → "7,2 điểm %"
COUNT = {'n_start', 'n_end', 'n_groups', 'n_groups_up', 'n_groups_down',
         'n_years', 'n_years_with_pattern', 'n_odd_years', 'n_even_years', 'n_phases', 'n_phases_eom_positive'}
UNITS = {'u_start', 'u_end'}
INDEX = {'month_index', 'august_index_odd', 'august_index_even', 'max_index_odd', 'min_index_even', 'peak_index',
         'trough_index', 'season_peak_trough_ratio', 'loo_min_ratio', 'loo_max_ratio'}
MONTHS = {'month', 'peak_month', 'trough_month', 'peak_months', 'trough_months'}
YEARS = {'year', 'start_year', 'end_year', 'turning_year', 'first_year', 'last_year'}
# khóa chọn dòng theo tên trong path rows[<tên>]: nhóm PS5, giai đoạn A–D, năm của điểm đổi hướng
ROW_KEYS = ('dimension_value', 'phase_code', 'turning_year')
# Số THAY ĐỔI: dương = tăng, âm = giảm. contribution_to_delta / share là TỶ LỆ, không thuộc nhóm này:
# contribution_to_delta dương = cùng chiều ΔR toàn công ty (Streetwear 2019: +83,6% của mức GIẢM).
SIGNED = {'delta_r', 'contrib_n', 'contrib_u', 'contrib_p', 'yoy_rate', 'share_shift_pp', 'r_change_rate',
          'n_change_rate', 'u_change_rate', 'p_change_rate',
          'total_change_rate', 'cagr', 'magnitude', 'august_odd_vs_even', 'loo_min_odd_vs_even', 'loo_max_odd_vs_even',
          'eom_excess', 'loo_min_eom_excess', 'loo_max_eom_excess'}
# Câu so sánh ("thấp hơn"...) được nói khi dẫn một cột chênh lệch / kết luận so sánh do tool tính
COMPARED = SIGNED | {'gap_g_minus_r', 'odd_even_order'}
# Ô xếp hạng mức (tháng cao nhất, chỉ số tháng 8 cao nhất của năm lẻ...): +1 = phía cao, −1 = phía thấp
LEVEL_RANK = {'peak_month': 1, 'peak_index': 1, 'peak_months': 1, 'max_index_odd': 1,
              'trough_month': -1, 'trough_index': -1, 'trough_months': -1, 'min_index_even': -1,
              'loo_min_ratio': -1, 'loo_min_odd_vs_even': -1, 'loo_min_eom_excess': -1,
              'loo_max_ratio': 1, 'loo_max_odd_vs_even': 1, 'loo_max_eom_excess': 1}
# Số tự nó đã là phép xếp hạng hai đầu trên đủ tập (tháng cao nhất ÷ thấp nhất): câu "giữa tháng cao nhất và thấp nhất
# là {c}" hợp lệ khi dẫn ô này
RANK_BOTH = {'season_peak_trough_ratio'}
HIGH_WORDS, LOW_WORDS = ('cao nhất', 'lớn nhất', 'nhiều nhất', 'đứng đầu'), ('thấp nhất', 'nhỏ nhất', 'ít nhất')
DRIVER_LABEL = {'n': 'số đơn (N)', 'u': 'số món mỗi đơn (U)', 'p': 'giá mỗi món (P)'}
# Nhãn chỉ tiêu của từng cột, để renderer tự ghi số đó là gì (không tin nhãn model tự viết).
FIELD_LABEL = {'r': 'R', 'g': 'G', 'r_prior_year': 'R', 'r_start': 'R', 'r_end': 'R', 'r_total': 'R toàn công ty',
               'delta_r': 'ΔR', 'contrib_n': 'phần góp của N', 'contrib_u': 'phần góp của U', 'contrib_p': 'phần góp của P',
               'yoy_rate': '% đổi R', 'r_change_rate': '% đổi R', 'n_change_rate': '% đổi N', 'u_change_rate': '% đổi U',
               'p_change_rate': '% đổi P', 'share': 'tỷ trọng R', 'share_shift_pp': 'đổi tỷ trọng R',
               'contribution_to_delta': '% đóng góp vào ΔR', 'n_start': 'số đơn', 'n_end': 'số đơn',
               'u_start': 'món mỗi đơn', 'u_end': 'món mỗi đơn', 'p_start': 'giá mỗi món', 'p_end': 'giá mỗi món',
               # AI3
               'cancelled_gross': 'tiền hàng đơn hủy', 'returned_gross': 'tiền hàng đơn trả',
               'undelivered_gross': 'tiền hàng đơn chưa giao', 'delivered_discount': 'chiết khấu đơn đã giao',
               'gap_g_minus_r': 'G − R', 'capture_rate': 'R/G', 'share_cancelled': 'đơn hủy / G',
               'share_returned': 'đơn trả / G', 'share_undelivered': 'đơn chưa giao / G',
               'share_discount': 'chiết khấu / G', 'r_same_month_prior_year': 'R', 'month_index': 'chỉ số tháng',
               'total_change_rate': '% đổi R cả giai đoạn', 'cagr': 'CAGR', 'r_12m_before': 'R 12 tháng trước điểm',
               'r_12m_after': 'R 12 tháng sau điểm', 'magnitude': 'độ lớn đổi hướng',
               'august_odd_vs_even': 'chênh tháng 8 năm lẻ / năm chẵn', 'august_index_odd': 'chỉ số tháng 8 TB năm lẻ',
               'august_index_even': 'chỉ số tháng 8 TB năm chẵn', 'max_index_odd': 'chỉ số tháng 8 cao nhất của năm lẻ',
               'min_index_even': 'chỉ số tháng 8 thấp nhất của năm chẵn', 'loo_min_odd_vs_even': 'thấp nhất khi bỏ từng năm',
               'loo_max_odd_vs_even': 'cao nhất khi bỏ từng năm', 'loo_min_ratio': 'thấp nhất khi bỏ từng năm',
               'loo_max_ratio': 'cao nhất khi bỏ từng năm', 'loo_min_eom_excess': 'thấp nhất khi bỏ từng năm',
               'loo_max_eom_excess': 'cao nhất khi bỏ từng năm', 'season_peak_trough_ratio': 'chênh mùa cao/thấp',
               'peak_index': 'chỉ số tháng cao nhất', 'trough_index': 'chỉ số tháng thấp nhất',
               'eom_share': 'tỷ trọng R từ ngày 26', 'eom_expected_share': 'tỷ trọng nếu rải đều',
               'eom_excess': 'mức dồn cuối tháng', 'n_years_with_pattern': 'số năm có nhịp'}
METRIC_FAMILY = {f: 'R' for f in ('r', 'r_prior_year', 'r_start', 'r_end', 'r_total', 'delta_r', 'contrib_n', 'contrib_u',
                                  'contrib_p', 'yoy_rate', 'r_change_rate', 'share', 'share_shift_pp',
                                  'contribution_to_delta', 'r_same_month_prior_year', 'r_12m_before', 'r_12m_after',
                                  'total_change_rate', 'cagr', 'magnitude')} | {'g': 'G'}
_START_FIELDS = {'r_start', 'n_start', 'u_start', 'p_start'}
DRIVER_FAMILY = {f'{k}{x}': k.upper() for k in 'nup' for x in ('_start', '_end', '_change_rate')} | {
    'contrib_n': 'N', 'contrib_u': 'U', 'contrib_p': 'P'}
# Năm trong phạm vi dữ liệu nguồn (2012-07-04 → 2022-12-31, CLAUDE.md §1): nhắc tới được kể cả khi chưa gọi tool
# ("dữ liệu chỉ đến hết 2022"). Năm không phải số liệu; số đứng trước đơn vị vẫn bị chặn.
DATA_YEARS = frozenset(str(y) for y in range(2012, 2023))
_DATA_DATES = re.compile(r'2012-07-04|2022-12-31|0?4/0?7/2012|31/12/2022')     # ngày đầu / cuối của dữ liệu
MONEY_SUFFIX = ' VND'   # PM chốt 2026-10-05 (metric_catalog.DECISIONS['currency_vnd'])

RANK_WORDS = ('nhiều nhất', 'lớn nhất', 'mạnh nhất', 'cao nhất', 'thấp nhất', 'ít nhất', 'chủ yếu', 'đứng đầu',
              'nhỏ nhất', 'mạnh hơn cả')
# so sánh hai số ("2019 cao hơn 2020") là phép tính model tự làm: chỉ được nói khi câu dẫn cột thay đổi tool đã tính
COMPARE_WORDS = ('cao hơn', 'thấp hơn', 'lớn hơn', 'nhỏ hơn', 'nhiều hơn', 'ít hơn', 'vượt')
NEG_WORDS = ('giảm', 'sụt', 'kéo xuống', 'âm', 'mất')
POS_WORDS = ('tăng', 'kéo lên', 'góp thêm', 'dương', 'cải thiện')
_PLACEHOLDER = re.compile(r'\{(c\d+)\}')
_PATH = re.compile(r'^(T\d+)\.(rows\[([^\]]+)\]\.(\w+)|derived\.(\w+)(?:\.(\w+))?)$')
_NUMBER = re.compile(r'(?<![^\W\d])\d[\d.,]*')     # không tính chữ số dính sau chữ cái (AI1, PS3, c1)
_SENTENCE = re.compile(r'[.;!?\n]')
# mốc ngày/tháng người dùng có thể gõ: 15/3, 10/6/2019, tháng 8, ngày 15, quý 3
_DATE = re.compile(r'(?<!\d)\d{1,2}/\d{1,2}(?:/\d{4})?(?![\d/])|(?:ngày|tháng|quý)\s+\d{1,2}(?!\d)', re.I)
# số đứng trước đơn vị tiền/tỷ lệ: không bao giờ được viết tay
_UNIT_AFTER = re.compile(r'(?<![^\W\d])\d(?:[\d.,]*\d)?\s*(?:tỷ|tỉ|triệu|nghìn|ngàn|vnd|đồng|usd|\$|%)(?!\w)', re.I)
_DRIVER_WORD = {'N': re.compile(r'số đơn|(?<!\w)N(?!\w)'),
                'U': re.compile(r'số món|món mỗi đơn|(?<!\w)U(?!\w)'),
                'P': re.compile(r'giá(?! trị)|(?<!\w)P(?!\w)')}
_DUP_MONEY = re.compile(r'\s*(?:VND|VNĐ|đồng)(?!\w)', re.I)
_DUP_PCT = re.compile(r'\s*%')
_DUP_PP = re.compile(r'\s*điểm\s*(?:%|phần trăm)', re.I)
_METRIC_WORD = re.compile(r'ΔR|(?<![\w])[RG](?![\w])|doanh thu thực nhận|tiền thực nhận|tiền hàng|doanh thu gộp')


def _is_num(v) -> bool:
    return isinstance(v, Number) and not isinstance(v, bool)     # tiền là Decimal, tỷ lệ là float


@dataclass
class Checked:
    ok: bool
    errors: list[str]
    answer_md: str | None = None                       # câu trả lời đã thay số thật (chỉ khi ok)
    values: dict = field(default_factory=dict)          # claim id → (path, giá trị gốc, chuỗi hiển thị)


def _resolve(path: str, results: dict):
    """(giá trị, tên trường, dòng | None) hoặc ném ValueError với lý do."""
    m = _PATH.match(path or '') if isinstance(path, str) else None
    if not m:
        raise ValueError(f'đường dẫn {path!r} sai dạng (vd. T1.rows[0].delta_r, T1.derived.largest_decrease.groups)')
    ref = m.group(1)
    res = results.get(ref)
    if res is None:
        raise ValueError(f'{ref} không phải kết quả tool của lượt này')
    if not res.ok:
        raise ValueError(f'{ref} có trạng thái {res.status}, không có số')
    if m.group(2).startswith('rows'):
        sel, fld = m.group(3), m.group(4)
        if sel.isdigit() and not (len(sel) == 4 and 'turning_year' in (res.rows[0] if res.rows else {})):
            i = int(sel)
            if i >= len(res.rows):
                raise ValueError(f'{ref} không có dòng {i}')
            row = res.rows[i]
        else:
            hit = [r for r in res.rows if any(r.get(k) is not None and str(r[k]) == sel for k in ROW_KEYS)]
            if len(hit) != 1:
                raise ValueError(f'{ref} không có nhóm / giai đoạn / điểm {sel!r}')
            row = hit[0]
        if fld not in row:
            raise ValueError(f'{ref} không có trường {fld}')
        return row[fld], fld, row
    key, sub = m.group(5), m.group(6)
    if key not in res.derived:
        raise ValueError(f'{ref}.derived không có {key}')
    v = res.derived[key]
    if sub is not None:
        if not isinstance(v, dict) or sub not in v:
            raise ValueError(f'{ref}.derived.{key} không có {sub}')
        v = v[sub]
    if isinstance(v, dict) or (isinstance(v, list) and not all(isinstance(x, (str, Number)) for x in v)):
        raise ValueError(f'{path} là cả một khối dữ liệu, không phải một ô; trỏ tới khóa con là số hoặc chữ')
    return v, sub or key, None


def _fmt(v, fld: str, absolute: bool) -> str:
    if isinstance(v, list):
        return ', '.join(map(str, v))
    if isinstance(v, bool):
        return 'có' if v else 'không'
    if fld in ('top_up_driver', 'top_down_driver'):
        return DRIVER_LABEL.get(v, str(v))
    if isinstance(v, str):
        return v
    x = abs(v) if absolute else v
    signed = fld in SIGNED and not absolute
    if fld in MONEY:
        return num(x, 0, signed) + MONEY_SUFFIX
    if fld in PRICE:
        return num(x, 2) + MONEY_SUFFIX
    if fld in RATE:
        return pct(x, 1, signed)
    if fld in PP:
        return num(x, 1, signed) + ' điểm %'
    if fld in PP_FRAC:
        return num(x * 100, 1, signed) + ' điểm %'
    if fld in UNITS or fld in INDEX:
        return num(x, 2)
    if fld in YEARS or fld in MONTHS:
        return str(int(x))                 # năm/tháng không có dấu nghìn ("2019", không phải "2.019")
    if fld in COUNT:
        return num(x)
    return num(x, 2, signed)


def allowed_years(results: dict) -> set[str]:
    """Số được viết thẳng trong câu văn: năm của dòng kết quả, kỳ đã lọc, năm gốc "so năm trước", và số trong
    thông báo do app viết (vd. phạm vi dữ liệu 2012-07-04 → 2022-12-31 khi tool trả no_data)."""
    years = set()
    for res in results.values():
        msg = _numbers(res.message)             # thông báo do app viết, không phải do model
        years |= msg | {str(int(t)) for t in msg if t.isdigit()}      # "2012-07-04" → model viết "tháng 7/2012"
        for r in res.rows:
            for k in ('year', 'start_year', 'end_year', 'period_code', 'month', 'turning_year', 'first_year', 'last_year'):
                if r.get(k) is not None:
                    years.add(str(r[k]))
        if res.evidence:
            for k in ('year', 'period_code', 'month'):
                v = res.evidence.filters_applied.get(k)
                if v is not None:
                    years.add(str(v))
                    if k != 'month' and str(v).isdigit():
                        years.add(str(int(v) - 1))
    return years


def _numbers(text: str) -> set[str]:
    return {t.rstrip('.,') for t in _NUMBER.findall(text or '')}


def question_numbers(question: str) -> set[str]:
    """Phần số trong câu hỏi mà câu trả lời được nhắc lại: năm (1900–2099) và NGUYÊN CỤM mốc ngày/tháng
    ("15/3", "10/6/2019", "tháng 8"). Số trần như "10" trong "10 tỷ" không được nhắc lại ở bất kỳ vị trí nào,
    kẻo người hỏi gài số giả ("R 2019 là 999 tỷ phải không?") vào câu trả lời."""
    q = question or ''
    out = {m.group(0).lower() for m in _DATE.finditer(q)}
    out |= {t for t in _numbers(_DATE.sub(' ', q)) if t.isdigit() and 1900 <= int(t) <= 2099}
    return out


def check_digits(text: str, allowed: set[str]) -> list[str]:
    """Chữ số trong câu văn (đã bỏ chỗ đặt) chỉ được là số trong `allowed`, mốc ngày/tháng có trong `allowed`,
    năm trong phạm vi dữ liệu, hoặc mã như PS1/AI1. Số đứng trước đơn vị (tỷ, triệu, VND, %...) luôn bị chặn."""
    rest = _DATA_DATES.sub(' ', re.sub(r'PS[1-5]', '', _PLACEHOLDER.sub(' ', text)))
    errs = []
    unit = [m.group(0) for m in _UNIT_AFTER.finditer(rest)]
    if unit:
        errs.append(f'câu văn tự viết số kèm đơn vị {unit[:3]}: số tiền / tỷ lệ phải đi qua claim')
    rest = _DATE.sub(lambda m: ' ' if m.group(0).lower() in allowed else m.group(0), rest)
    bad = [t for t in _NUMBER.findall(rest) if t.rstrip('.,') not in allowed | DATA_YEARS]
    if bad:
        errs.append(f'câu văn có số tự viết {bad[:3]}: mọi số phải đi qua claim')
    return errs


def _direction(window: str) -> int:
    w = window.lower().replace('tăng trưởng', '')      # "tăng trưởng âm 39%" là cách nói bình thường, không phải "tăng"
    neg, pos = any(x in w for x in NEG_WORDS), any(x in w for x in POS_WORDS)
    return -1 if neg and not pos else (1 if pos and not neg else 0)


def _rank_direction(path: str) -> int:
    """Hướng của claim xếp hạng: −1 (largest_decrease, top_down_driver), +1 (largest_increase, top_up_driver),
    0 nếu không phải claim xếp hạng."""
    if '.derived.largest_decrease' in path or path.endswith('top_down_driver'):
        return -1
    if '.derived.largest_increase' in path or path.endswith('top_up_driver'):
        return 1
    return LEVEL_RANK.get(path.rsplit('.', 1)[-1], 0)


def _said_metric(seg: str) -> str | None:
    """Chỉ tiêu mà đoạn ngay trước chỗ đặt gọi tên ('R' / 'G'); None nếu không gọi tên hoặc gọi cả hai
    ("R và G lần lượt là {c1} và {c2}": khi đó nhãn của app nói rõ số nào là gì)."""
    fams = {'G' if h.lower() in ('g', 'tiền hàng', 'doanh thu gộp') else 'R' for h in _METRIC_WORD.findall(seg)}
    return fams.pop() if len(fams) == 1 else None


def _said_driver(seg: str) -> str | None:
    """Thành phần N/U/P mà đoạn ngay trước chỗ đặt gọi tên; None nếu không gọi hoặc gọi nhiều ("N → U → P")."""
    hits = [k for k, rx in _DRIVER_WORD.items() if rx.search(seg)]
    return hits[0] if len(hits) == 1 else None


def _verified_driver_rank(sent: str, results: dict) -> bool:
    """Câu xếp hạng gọi tên thẳng N/U/P ("R giảm chủ yếu ở số đơn"): app tự đối chiếu với top_down_driver /
    top_up_driver của kết quả phân rã DUY NHẤT trong lượt, theo chữ tăng/giảm của câu. Không tin lời model."""
    rows = [r for res in results.values() if res.ok for r in res.rows if 'top_down_driver' in r]
    d = _direction(_PLACEHOLDER.sub(' ', sent))
    if len(rows) != 1 or not d:
        return False
    top = rows[0]['top_down_driver' if d < 0 else 'top_up_driver']
    clauses = [c for c in re.split(r'[,:()]|\{c\d+\}', sent) if any(w in c.lower() for w in RANK_WORDS)]
    # vế chứa từ xếp hạng không gọi tên N/U/P ("... và là thành phần kéo giảm nhiều nhất") → xét cả câu
    said = [_said_driver(c) or _said_driver(_PLACEHOLDER.sub(' ', sent)) for c in clauses]
    return bool(top) and bool(clauses) and all(x == str(top).upper() for x in said)


def _year_of(fld: str, row: dict | None):
    if not row:
        return None
    if 'period' in row:                                   # kỳ gộp 2013–2022
        return row['period']
    if row.get('month') is not None and row.get('year') is not None:
        y = int(row['year']) - (1 if fld == 'r_same_month_prior_year' else 0)
        return f"{row['month']}/{y}"
    if row.get('turning_year') is not None:
        t = int(row['turning_year'])
        return {'r_12m_before': t, 'r_12m_after': t + 1}.get(fld, f'cuối {t}')
    if row.get('first_year') is not None:                 # giai đoạn PS3 (năm lịch gom theo giai đoạn)
        a, b = row['first_year'], row.get('last_year')
        return str(a) if a == b else f'{a}–{b}'
    if fld == 'r_prior_year' and row.get('year') is not None:
        return int(row['year']) - 1
    if fld in _START_FIELDS:
        return row.get('start_year')
    if row.get('phase_code') is not None and fld != 'r_end':      # giai đoạn PS2: cả khoảng năm
        return f"{row['start_year']}→{row['end_year']}"
    return row.get('year', row.get('end_year'))


def _label(fld: str, row: dict | None, clause: str) -> str:
    """Nhãn do app dựng từ chính ô dữ liệu: (chỉ tiêu, nhóm, năm). Bỏ nhãn chỉ khi vế câu đã gọi đúng chỉ tiêu,
    nhóm và năm của một số tiền R/G/ΔR."""
    name = FIELD_LABEL.get(fld)
    if name is None:
        return ''
    row_ = row or {}
    year = _year_of(fld, row)
    group = row_.get('dimension_value') or (f"giai đoạn {row_['phase_code']}" if row_.get('phase_code') else None)
    parts = [name] + [str(x) for x in (group, year) if x is not None]
    said = (fld in ('r', 'g', 'r_prior_year', 'delta_r', 'r_start', 'r_end')
            and _said_metric(clause) == METRIC_FAMILY.get(fld)
            and (group is None or str(group).lower() in clause.lower())
            and (year is None or str(year) in clause))
    return '' if said else ' (' + ', '.join(parts) + ')'


def _group_names(results: dict) -> set[str]:
    names = set()
    for res in results.values():
        if not res.ok:
            continue
        names |= {r['dimension_value'] for r in res.rows if isinstance(r.get('dimension_value'), str)}
        for v in res.derived.values():
            if isinstance(v, dict) and isinstance(v.get('groups'), list):
                names |= {g for g in v['groups'] if isinstance(g, str)}
    return names


def validate(answer: str, claims: list, results: dict, extra_allowed: frozenset = frozenset()) -> Checked:
    errors = []
    if not isinstance(answer, str) or not answer.strip():
        return Checked(False, ['thiếu câu trả lời'])
    if not isinstance(claims, list):
        return Checked(False, ['claims phải là danh sách'])
    used = set(_PLACEHOLDER.findall(answer))
    by_id, values = {}, {}
    for c in claims:
        if not isinstance(c, dict) or not isinstance(c.get('id'), str):
            errors.append(f'claim sai dạng: {c!r}'[:120])
            continue
        if c['id'] not in used:          # khai báo mà không dùng: bỏ qua, không được tính cho nhận định nào
            continue
        try:
            v, fld, row = _resolve(c.get('path'), results)
        except ValueError as e:
            errors.append(f'{c["id"]}: {e}')
            continue
        if v is None:
            errors.append(f'{c["id"]}: {c["path"]} là NULL (không tính được), không được trình bày như một số')
            continue
        sign = c.get('sign')
        if sign is not None:
            if sign not in ('am', 'duong') or not _is_num(v):
                errors.append(f'{c["id"]}: sign chỉ nhận "am"/"duong" cho giá trị số')
            elif v == 0 or (sign == 'am') != (v < 0):
                errors.append(f'{c["id"]}: nói {sign} nhưng {c["path"]} thật là {v}')
        by_id[c['id']] = (c, v, fld, row)

    for cid in sorted(used):
        if cid not in by_id and not any(e.startswith(f'{cid}:') for e in errors):
            errors.append(f'chỗ đặt {{{cid}}} không có claim hợp lệ')
    errors += check_digits(answer, allowed_years(results) | set(extra_allowed))

    # câu xếp hạng: chỗ đặt xếp hạng phải nằm trong CHÍNH câu đó và cùng hướng với chữ tăng/giảm của câu
    for sent in _SENTENCE.split(answer):
        if not any(w in sent.lower() for w in RANK_WORDS):
            continue
        ranks = [_rank_direction(by_id[cid][0]['path']) for cid in _PLACEHOLDER.findall(sent) if cid in by_id]
        ranks = [r for r in ranks if r]
        if not ranks and _verified_driver_rank(sent, results):
            continue
        if not ranks and any(by_id[cid][2] in RANK_BOTH for cid in _PLACEHOLDER.findall(sent) if cid in by_id):
            continue
        if not ranks:
            errors.append(f'câu "{sent.strip()[:80]}" có ý xếp hạng ("nhiều nhất", "chủ yếu"...) nhưng trong câu '
                          'không có chỗ đặt trỏ vào derived.largest_* hoặc top_*_driver (xếp hạng trên đủ tập)')
            continue
        level = [_rank_direction(by_id[cid][0]['path']) for cid in _PLACEHOLDER.findall(sent)
                 if cid in by_id and by_id[cid][0]['path'].rsplit('.', 1)[-1] in LEVEL_RANK]
        hi, lo = any(w in sent.lower() for w in HIGH_WORDS), any(w in sent.lower() for w in LOW_WORDS)
        if level and hi != lo and all(r != (1 if hi else -1) for r in level):
            errors.append(f'câu "{sent.strip()[:80]}" nói "{"cao" if hi else "thấp"} nhất" nhưng chỗ đặt trỏ vào phía '
                          f'{"thấp" if hi else "cao"} (peak/trough, max/min)')
            continue
        d = _direction(_PLACEHOLDER.sub(' ', sent))
        if d and all(r != d for r in ranks):
            errors.append(f'câu "{sent.strip()[:80]}" nói "{"tăng" if d > 0 else "giảm"}" nhưng claim xếp hạng là '
                          f'chiều {"tăng" if d < 0 else "giảm"}')

    # câu so sánh phải dẫn ít nhất một số thay đổi do tool tính (delta_r, yoy_rate, *_change_rate...)
    # (câu không có chỗ đặt nào, vd. nhắc lại câu hỏi "tháng 8 năm lẻ có thấp hơn..." khi từ chối, thì không xét)
    for sent in _SENTENCE.split(answer):
        cids = [cid for cid in _PLACEHOLDER.findall(sent) if cid in by_id]
        if cids and any(w in sent.lower() for w in COMPARE_WORDS) and not any(by_id[c][2] in COMPARED for c in cids):
            errors.append(f'câu "{sent.strip()[:80]}" tự so sánh các số (cao hơn / thấp hơn...) mà không dẫn cột thay đổi '
                          'do tool tính; app không kiểm được phép so sánh này')

    # tên nhóm viết thẳng phải gắn với claim đã dùng (rows[<nhóm>] hoặc danh sách nhóm của claim)
    bound = set()
    for c, v, fld, row in by_id.values():
        if row and isinstance(row.get('dimension_value'), str):
            bound.add(row['dimension_value'])
        if isinstance(v, str):
            bound.add(v)
        if isinstance(v, list):
            bound |= {x for x in v if isinstance(x, str)}
    plain_text = _PLACEHOLDER.sub(' ', answer)
    loose = sorted(n for n in _group_names(results) - bound
                   if re.search(rf'(?<!\w){re.escape(n)}(?!\w)', plain_text, re.I))
    if loose:
        errors.append(f'câu văn viết thẳng tên nhóm {loose[:3]} mà không gắn với claim nào đã dùng: tên nhóm phải là '
                      'chỗ đặt (derived.largest_*.groups, rows[<nhóm>].dimension_value) hoặc đi cùng claim rows[<nhóm>]')

    # chữ "tăng"/"giảm" ngay trước số phải cùng dấu với số thật; vế câu gọi tên R mà số là G (hoặc ngược lại) thì chặn
    # (tương tự với N/U/P: "{c2: giá mỗi món (P)} góp {c3: contrib_u}" là gắn số của U cho P)
    rendered, last, prev, prev_driver = [], 0, 0, None
    for m in _PLACEHOLDER.finditer(answer):
        cid = m.group(1)
        rendered.append(answer[last:m.start()])
        last = m.end()
        if cid not in by_id:
            prev, prev_driver = m.end(), None
            continue
        c, v, fld, row = by_id[cid]
        parts = re.split(r'[.;:!?\n]', answer[prev:m.start()])
        seg = parts[-1]                # đoạn từ chỗ đặt trước / đầu vế câu
        if len(parts) > 1:
            prev_driver = None
        prev = m.end()
        said, fam = _said_metric(seg), METRIC_FAMILY.get(fld)
        if said and fam and said != fam:
            errors.append(f'{cid}: vế câu gọi tên {said} nhưng {c["path"]} là số của {fam}')
        drv = DRIVER_FAMILY.get(fld)
        said_drv = _said_driver(seg) or prev_driver
        if drv and said_drv and said_drv != drv:
            errors.append(f'{cid}: vế câu nói về {said_drv} nhưng {c["path"]} là số của {drv}')
        if fld in ('top_up_driver', 'top_down_driver') and re.search(r'(mức|góp|bằng)\W*$', seg.strip(), re.I):
            errors.append(f'{cid}: chỗ đặt sau "{seg.strip()[-20:]}" phải là một số (contrib_*), không phải tên thành phần')
        prev_driver = str(v).upper() if fld in ('top_up_driver', 'top_down_driver') else None
        absolute = False
        if fld in SIGNED and _is_num(v) and v != 0:
            d = _direction(seg[-40:])
            if d and d != (1 if v > 0 else -1):
                errors.append(f'{cid}: câu nói "{"tăng" if d > 0 else "giảm"}" nhưng {c["path"]} = {v}')
            absolute = d != 0          # đã có chữ tăng/giảm đúng dấu → in giá trị tuyệt đối cho dễ đọc
        s = _fmt(v, fld, absolute)
        lbl = _label(fld, row, seg) if _is_num(v) else ''
        values[cid] = (c['path'], v, s + lbl)
        rendered.append(f'**{s}**{lbl}')
        # model hay viết lại đơn vị sau chỗ đặt ("{c1} VND"): app đã ghi đơn vị, bỏ bản lặp
        unit = (_DUP_MONEY if fld in MONEY | PRICE else _DUP_PCT if fld in RATE
                else _DUP_PP if fld in PP | PP_FRAC else None)
        dup = unit.match(answer, last) if unit else None
        if dup:
            last = prev = dup.end()
    rendered.append(answer[last:])
    if errors:
        return Checked(False, errors)
    return Checked(True, [], ''.join(rendered), values)
