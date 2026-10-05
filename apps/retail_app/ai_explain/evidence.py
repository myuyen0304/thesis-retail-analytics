"""Kiểm câu trả lời của LLM trước khi hiện (docs/ai_explain_plan.md §5 "Câu trả lời", §11.2; case E21).

Hợp đồng: model KHÔNG viết số. Mỗi con số là một claim trỏ vào kết quả tool của chính lượt đó:
    {"id": "c1", "path": "T1.rows[0].delta_r", "sign": "am"}
    {"id": "c2", "path": "T2.derived.largest_decrease.groups"}
    {"id": "c3", "path": "T2.rows[Streetwear].contribution_to_delta"}
và câu văn chỉ chứa chỗ đặt `{c1}`. App tra giá trị thật rồi định dạng; model không tự điền số.

Bị chặn (answer_validation_failed) khi:
- tham chiếu kết quả không có / không `ok`, dòng hoặc trường không có, giá trị NULL;
- câu văn có chữ số ngoài năm của bằng chứng và số người dùng tự gõ trong câu hỏi (số bịa, số tự tính);
- `sign` sai dấu thật, hoặc chữ "tăng"/"giảm" ngay trước số ngược dấu thật;
- dùng từ xếp hạng ("nhiều nhất", "chủ yếu"...) mà không có claim trỏ vào phần xếp hạng tính trên đủ tập
  (`derived.largest_*`, `top_*_driver`): một ô số đúng không chứng minh "lớn nhất";
- chỗ đặt `{cX}` không có claim tương ứng.
Không kiểm được mọi nhận định bằng lời; phần đó thuộc live eval (§13).
"""
import re
from dataclasses import dataclass, field
from numbers import Number

from ui.fmt import num, pct

MONEY = {'r', 'g', 'r_prior_year', 'delta_r', 'r_start', 'r_end', 'contrib_n', 'contrib_u', 'contrib_p', 'r_total',
         'additive_check'}
PRICE = {'p_start', 'p_end'}
RATE = {'yoy_rate', 'share', 'contribution_to_delta', 'r_change_rate', 'n_change_rate', 'u_change_rate', 'p_change_rate'}
PP = {'share_shift_pp'}
COUNT = {'n_start', 'n_end', 'n_groups', 'n_groups_up', 'n_groups_down'}
UNITS = {'u_start', 'u_end'}
# Số THAY ĐỔI: dương = tăng, âm = giảm. contribution_to_delta / share là TỶ LỆ, không thuộc nhóm này:
# contribution_to_delta dương = cùng chiều ΔR toàn công ty (Streetwear 2019: +83,6% của mức GIẢM).
SIGNED = {'delta_r', 'contrib_n', 'contrib_u', 'contrib_p', 'yoy_rate', 'share_shift_pp', 'r_change_rate',
          'n_change_rate', 'u_change_rate', 'p_change_rate'}
DRIVER_LABEL = {'n': 'số đơn (N)', 'u': 'số món mỗi đơn (U)', 'p': 'giá mỗi món (P)'}
MONEY_SUFFIX = ' (đơn vị tiền)'

RANK_WORDS = ('nhiều nhất', 'lớn nhất', 'mạnh nhất', 'cao nhất', 'thấp nhất', 'ít nhất', 'chủ yếu', 'đứng đầu',
              'nhỏ nhất', 'mạnh hơn cả')
NEG_WORDS = ('giảm', 'sụt', 'kéo xuống', 'âm', 'mất')
POS_WORDS = ('tăng', 'kéo lên', 'góp thêm', 'dương', 'cải thiện')
_PLACEHOLDER = re.compile(r'\{(c\d+)\}')
_PATH = re.compile(r'^(T\d+)\.(rows\[([^\]]+)\]\.(\w+)|derived\.(\w+)(?:\.(\w+))?)$')
_NUMBER = re.compile(r'\d[\d.,]*')


def _is_num(v) -> bool:
    return isinstance(v, Number) and not isinstance(v, bool)     # tiền là Decimal, tỷ lệ là float


@dataclass
class Checked:
    ok: bool
    errors: list[str]
    answer_md: str | None = None                       # câu trả lời đã thay số thật (chỉ khi ok)
    values: dict = field(default_factory=dict)          # claim id → (path, giá trị gốc, chuỗi hiển thị)


def _resolve(path: str, results: dict):
    """(giá trị, tên trường) hoặc ném ValueError với lý do."""
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
        if sel.isdigit():
            i = int(sel)
            if i >= len(res.rows):
                raise ValueError(f'{ref} không có dòng {i}')
            row = res.rows[i]
        else:
            hit = [r for r in res.rows if r.get('dimension_value') == sel]
            if len(hit) != 1:
                raise ValueError(f'{ref} không có nhóm {sel!r}')
            row = hit[0]
        if fld not in row:
            raise ValueError(f'{ref} không có trường {fld}')
        return row[fld], fld
    key, sub = m.group(5), m.group(6)
    if key not in res.derived:
        raise ValueError(f'{ref}.derived không có {key}')
    v = res.derived[key]
    if sub is not None:
        if not isinstance(v, dict) or sub not in v:
            raise ValueError(f'{ref}.derived.{key} không có {sub}')
        v = v[sub]
    return v, sub or key


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
    if fld in UNITS:
        return num(x, 2)
    if fld in COUNT or fld in ('year', 'start_year', 'end_year'):
        return num(x)
    return num(x, 2, signed)


def allowed_years(results: dict) -> set[str]:
    """Số được viết thẳng trong câu văn: năm của dòng kết quả, kỳ đã lọc, năm gốc "so năm trước", và số trong
    thông báo do app viết (vd. phạm vi dữ liệu 2012-07-04 → 2022-12-31 khi tool trả no_data)."""
    years = set()
    for res in results.values():
        years |= _numbers(res.message)          # thông báo do app viết, không phải do model
        for r in res.rows:
            for k in ('year', 'start_year', 'end_year', 'period_code'):
                if r.get(k) is not None:
                    years.add(str(r[k]))
        if res.evidence:
            for k in ('year', 'period_code'):
                v = res.evidence.filters_applied.get(k)
                if v is not None:
                    years.add(str(v))
                    if str(v).isdigit():
                        years.add(str(int(v) - 1))
    return years


def _numbers(text: str) -> set[str]:
    return {t.rstrip('.,') for t in _NUMBER.findall(text or '')}


def question_numbers(question: str) -> set[str]:
    """Số trong câu hỏi mà câu trả lời được nhắc lại: CHỈ năm (1900–2099) và số ngày/tháng ≤ 31 (vd. "15/3").
    Số khác (vd. "R 2019 là 999 tỷ phải không?") không được nhắc lại, kẻo người hỏi gài số giả vào câu trả lời."""
    return {t for t in _numbers(question) if t.isdigit() and (1900 <= int(t) <= 2099 or int(t) <= 31)}


def check_digits(text: str, allowed: set[str]) -> list[str]:
    """Chữ số trong câu văn (đã bỏ chỗ đặt) chỉ được là số trong `allowed`, hoặc tên PS1–PS5."""
    rest = re.sub(r'PS[1-5]', '', _PLACEHOLDER.sub('', text))
    bad = [t for t in _NUMBER.findall(rest) if t.rstrip('.,') not in allowed]
    return [f'câu văn có số tự viết {bad[:3]}: mọi số phải đi qua claim'] if bad else []


def _direction(window: str) -> int:
    w = window.lower().replace('tăng trưởng', '')      # "tăng trưởng âm 39%" là cách nói bình thường, không phải "tăng"
    neg, pos = any(x in w for x in NEG_WORDS), any(x in w for x in POS_WORDS)
    return -1 if neg and not pos else (1 if pos and not neg else 0)


def validate(answer: str, claims: list, results: dict, extra_allowed: frozenset = frozenset()) -> Checked:
    errors = []
    if not isinstance(answer, str) or not answer.strip():
        return Checked(False, ['thiếu câu trả lời'])
    if not isinstance(claims, list):
        return Checked(False, ['claims phải là danh sách'])
    by_id, values = {}, {}
    for c in claims:
        if not isinstance(c, dict) or not isinstance(c.get('id'), str):
            errors.append(f'claim sai dạng: {c!r}'[:120])
            continue
        try:
            v, fld = _resolve(c.get('path'), results)
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
        by_id[c['id']] = (c, v, fld)

    for cid in _PLACEHOLDER.findall(answer):
        if cid not in by_id and not any(e.startswith(f'{cid}:') for e in errors):
            errors.append(f'chỗ đặt {{{cid}}} không có claim hợp lệ')
    errors += check_digits(answer, allowed_years(results) | set(extra_allowed))

    low = answer.lower()
    if any(w in low for w in RANK_WORDS):
        rank_ok = any(('.derived.largest_' in c['path']) or c['path'].endswith(('top_up_driver', 'top_down_driver'))
                      for c, _, _ in by_id.values())
        if not rank_ok:
            errors.append('câu có ý xếp hạng ("nhiều nhất", "chủ yếu"...) nhưng không có claim trỏ vào '
                          'derived.largest_* hoặc top_*_driver (xếp hạng trên đủ tập)')

    # chữ "tăng"/"giảm" ngay trước số phải cùng dấu với số thật
    rendered, last = [], 0
    for m in _PLACEHOLDER.finditer(answer):
        cid = m.group(1)
        before = answer[last:m.start()]
        rendered.append(before)
        last = m.end()
        if cid not in by_id:
            continue
        c, v, fld = by_id[cid]
        absolute = False
        if fld in SIGNED and _is_num(v) and v != 0:
            d = _direction(re.split(r'[.;:!?\n]', before)[-1][-40:])
            if d and d != (1 if v > 0 else -1):
                errors.append(f'{cid}: câu nói "{"tăng" if d > 0 else "giảm"}" nhưng {c["path"]} = {v}')
            absolute = d != 0          # đã có chữ tăng/giảm đúng dấu → in giá trị tuyệt đối cho dễ đọc
        s = _fmt(v, fld, absolute)
        values[cid] = (c['path'], v, s)
        rendered.append(f'**{s}**')
    rendered.append(answer[last:])
    if errors:
        return Checked(False, errors)
    return Checked(True, [], ''.join(rendered), values)
