"""AI3: tool PS1–PS3 trả đúng số (so CSV), đúng kỳ, xử lý thiếu/ngoài phạm vi trung thực (docs/ai_explain_plan.md §13).

Không có LLM trong file này. Số kỳ vọng tính THẲNG từ CSV (pandas), không qua dbt, queries.py hay tool đang test:
- R   = payments.csv của đơn delivered, theo order_date (ngày / tháng / năm của đơn);
- G   = sales.csv.Revenue;
- khoản chênh G − R = order_items × orders theo trạng thái (tiền hàng = quantity × unit_price; chiết khấu đơn delivered).
Mốc giai đoạn PS2 lấy theo quyết định PM/BA 2026-09-27 (docs/dwh_huong_dan_pm_ba.md §4), không đọc seed của kho.
Mốc năm PS3 theo quy ước đề xuất (năm ranh giới thuộc giai đoạn kết thúc ở năm đó). Tiền so theo cent nguyên;
tỷ lệ/chỉ số là DOUBLE: sai số tương đối 1e-9.
"""
import calendar
import json
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from ai_explain import evidence, metric_catalog, tools
from dwh.connection import ROOT

DATA = ROOT / 'data'
RTOL = 1e-9
YEARS = range(2012, 2023)
FULL = range(2013, 2023)
PS2 = {'A': (2013, 2016), 'B': (2016, 2018), 'C': (2018, 2019), 'D': (2019, 2022)}         # PM/BA chốt 2026-09-27
PS3 = {'A': range(2013, 2017), 'B': range(2017, 2019), 'C': range(2019, 2020), 'D': range(2020, 2023)}   # đề xuất
TURNS = {2016: ('A', 'B', None), 2018: ('B', 'C', 'giảm tăng tốc'), 2019: ('C', 'D', 'đổi nhịp')}


def _cents(x: pd.Series) -> pd.Series:
    return np.round(x * 100).astype('int64')


def _money(c: int) -> Decimal:
    return Decimal(int(c)) / 100


def _run(tool, **arguments):
    return tools.run({'tool': tool, 'arguments': arguments}, 'duckdb')


@pytest.fixture(scope='module')
def src() -> dict:
    R = lambda f, **k: pd.read_csv(DATA / f, low_memory=False, **k)
    o = R('orders.csv', usecols=['order_id', 'order_date', 'order_status'])
    oi = R('order_items.csv', usecols=['order_id', 'quantity', 'unit_price', 'discount_amount'])
    pay = R('payments.csv', usecols=['order_id', 'payment_value'])
    sales = R('sales.csv', usecols=['Date', 'Revenue'])
    assert o.order_id.is_unique and pay.order_id.is_unique
    d = pd.to_datetime(o.order_date)
    o['year'], o['month'], o['day'] = d.dt.year, d.dt.month, d.dt.day
    li = oi.merge(o, on='order_id', validate='many_to_one')
    assert len(li) == len(oi)
    li['gross_c'] = _cents(li.quantity * li.unit_price)
    li['disc_c'] = _cents(li.discount_amount)
    st = li.order_status
    comp = pd.DataFrame({
        'year': li.year,
        'cancelled_gross': np.where(st == 'cancelled', li.gross_c, 0),
        'returned_gross': np.where(st == 'returned', li.gross_c, 0),
        'undelivered_gross': np.where(st.isin(['created', 'paid', 'shipped']), li.gross_c, 0),
        'delivered_discount': np.where(st == 'delivered', li.disc_c, 0),
        'gross_all': li.gross_c,
    }).groupby('year').sum()
    p = pay.merge(o[o.order_status == 'delivered'], on='order_id')
    p['r_c'] = _cents(p.payment_value)
    sd = pd.to_datetime(sales.Date)
    sales = sales.assign(year=sd.dt.year, month=sd.dt.month, g_c=_cents(sales.Revenue))
    r_y = p.groupby('year').r_c.sum()
    g_y = sales.groupby('year').g_c.sum()
    r_m = p.groupby(['year', 'month']).r_c.sum()
    g_m = sales.groupby(['year', 'month']).g_c.sum()
    r_m26 = p[p.day >= 26].groupby(['year', 'month']).r_c.sum().reindex(r_m.index, fill_value=0)
    return {'comp': comp, 'r_y': r_y, 'g_y': g_y, 'r_m': r_m, 'g_m': g_m, 'r_m26': r_m26}


# --- PS1: G → R ---

def _gap_expected(src, years) -> dict:
    c = src['comp'].loc[list(years)].sum()
    return {'g': int(src['g_y'].loc[list(years)].sum()), 'r': int(src['r_y'].loc[list(years)].sum()),
            **{k: int(c[k]) for k in tools.GAP_PARTS}, 'gross_all': int(c['gross_all'])}


def _check_gap(res, e):
    assert res.status == 'ok', res.message
    row = res.rows[0]
    assert e['gross_all'] == e['g']                    # G (sales.csv) = tiền hàng mọi trạng thái (CLAUDE.md §5 điểm 1)
    assert row['g'] == _money(e['g']) and row['r'] == _money(e['r'])
    for k, (step, _) in tools.GAP_PARTS.items():
        assert row[k] == _money(e[k]), k
        assert row[f'share_{step}'] == pytest.approx(e[k] / e['g'], rel=RTOL), k
    assert row['capture_rate'] == pytest.approx(e['r'] / e['g'], rel=RTOL)
    gap = e['g'] - e['r']
    assert gap == sum(e[k] for k in tools.GAP_PARTS)   # đối soát PS1 trên CSV
    assert res.derived['gap_g_minus_r'] == _money(gap)
    best = max(e[k] for k in tools.GAP_PARTS)
    assert res.derived['largest_decrease']['components'] == [lbl for k, (_, lbl) in tools.GAP_PARTS.items()
                                                              if e[k] == best]


@pytest.mark.parametrize('year', YEARS)
def test_gap_moi_nam(src, year):
    res = _run('get_revenue_gap', period='year', year=year)
    _check_gap(res, _gap_expected(src, [year]))
    assert res.rows[0]['is_analysis_period'] is (year >= 2013)
    assert res.evidence.filters_applied == {'period_type': 'year', 'period_code': str(year)}


def test_gap_ca_ky(src):
    res = _run('get_revenue_gap', period='2013-2022')
    _check_gap(res, _gap_expected(src, FULL))
    assert res.rows[0]['period'] == '2013–2022'


def test_gap_thieu_nam_hoi_lai_va_ky_gop_khong_kem_nam():
    r = _run('get_revenue_gap', period='year')
    assert r.status == 'needs_clarification' and r.missing == ['year']
    r = _run('get_revenue_gap', period='2013-2022', year=2019)
    assert r.status == 'unsupported' and 'year' in r.rejected
    assert _run('get_revenue_gap', period='year', year=2023).status == 'no_data'
    assert _run('get_revenue_gap', period='2012-2022').status == 'unsupported'      # kỳ gộp chưa mở


# --- PS1/PS3: tháng ---

def test_thang_moi_thang(src):
    r_m, g_m = src['r_m'], src['g_m']
    for (y, m), r_c in r_m.items():
        res = _run('get_revenue_monthly', metric='R_and_G', year=int(y), month=int(m))
        assert res.status == 'ok', (y, m, res.message)
        row = res.rows[0]
        assert row['r'] == _money(r_c) and row['g'] == _money(g_m[(y, m)]), (y, m)
        assert row['capture_rate'] == pytest.approx(r_c / g_m[(y, m)], rel=RTOL)
        prev = (y - 1, m)
        if (y, m) >= (2013, 8):
            assert row['r_same_month_prior_year'] == _money(r_m[prev])
            assert row['yoy_rate'] == pytest.approx(r_c / r_m[prev] - 1, rel=RTOL)
        else:
            assert row['yoy_rate'] is None and row['r_same_month_prior_year'] is None
        if y >= 2013:
            assert row['month_index'] == pytest.approx(r_c / (src['r_y'][y] / 12), rel=RTOL)
        else:
            assert row['month_index'] is None
    assert len(r_m) == 126


def test_thang_ngoai_pham_vi_va_sai_thang():
    assert _run('get_revenue_monthly', metric='R', year=2012, month=3).status == 'no_data'     # trước 07/2012
    assert _run('get_revenue_monthly', metric='R', year=2024, month=3).status == 'no_data'
    r = _run('get_revenue_monthly', metric='R', year=2019, month=13)
    assert r.status == 'unsupported' and 'month' in r.rejected
    r = _run('get_revenue_monthly', metric='G', year=2019, month=8)
    assert r.status == 'ok' and set(r.rows[0]) == {'year', 'month', 'is_analysis_period', 'g'}   # G không kèm YoY/chỉ số
    assert _run('get_revenue_monthly', year=2019, month=8).missing == ['metric']


# --- PS2: giai đoạn, điểm đổi hướng ---

def test_giai_doan(src):
    r_y = src['r_y']
    res = _run('get_revenue_trend', view='phases')
    assert res.status == 'ok' and [x['phase_code'] for x in res.rows] == list(PS2)
    exp = {}
    for x in res.rows:
        a, b = PS2[x['phase_code']]
        r0, r1 = r_y[a], r_y[b]
        assert (x['start_year'], x['end_year'], x['n_years']) == (a, b, b - a)
        assert x['r_start'] == _money(r0) and x['r_end'] == _money(r1) and x['delta_r'] == _money(r1 - r0)
        assert x['total_change_rate'] == pytest.approx(r1 / r0 - 1, rel=RTOL)
        cagr = (r1 / r0) ** (1 / (b - a)) - 1
        assert x['cagr'] == pytest.approx(cagr, rel=RTOL)
        exp[x['phase_code']] = (r1 - r0, cagr)
    lbl = {x['phase_code']: tools._phase_label(x) for x in res.rows}
    pick = lambda i, f: [lbl[min(exp, key=lambda k: f * exp[k][i])]]
    assert res.derived['largest_decrease']['phases'] == pick(0, 1) == [lbl['C']]
    assert res.derived['largest_decrease_cagr']['phases'] == pick(1, 1) == [lbl['C']]
    assert res.derived['largest_increase']['phases'] == pick(0, -1) == [lbl['A']]
    assert res.derived['largest_increase_cagr']['phases'] == pick(1, -1)


def test_diem_doi_huong(src):
    r_y = src['r_y']
    res = _run('get_revenue_trend', view='turning_points')
    assert res.status == 'ok' and [x['turning_year'] for x in res.rows] == list(TURNS)
    for x in res.rows:
        y = x['turning_year']
        assert (x['from_phase_code'], x['to_phase_code'], x['turn_note']) == TURNS[y]
        assert x['r_12m_before'] == _money(r_y[y]) and x['r_12m_after'] == _money(r_y[y + 1])
        assert x['magnitude'] == pytest.approx(r_y[y + 1] / r_y[y] - 1, rel=RTOL)
    assert res.derived['largest_decrease']['turns'] == ['cuối 2018 (B → C)']
    assert res.derived['largest_increase'] is None
    assert _run('get_revenue_trend', view='direction_changes').status == 'unsupported'


# --- PS3: nhịp lịch ---

def _month_index(src) -> pd.Series:
    r_m = src['r_m']
    full = r_m[r_m.index.get_level_values(0) >= 2013]
    return full / full.groupby(level=0).transform('sum') * 12


def _eom_excess(src, years) -> float:
    """Tỷ trọng R ngày ≥ 26 − Σ R tháng × (D − 25)/D ÷ Σ R (gia quyền theo R tháng)."""
    r_m, r26 = src['r_m'], src['r_m26']
    idx = [k for k in r_m.index if k[0] in years]
    tot = sum(r_m[k] for k in idx)
    exp = sum(r_m[k] * (calendar.monthrange(*k)[1] - 25) / calendar.monthrange(*k)[1] for k in idx)
    return sum(r26[k] for k in idx) / tot - exp / tot


def _aug(mi, years):
    a = {y: mi[(y, 8)] for y in years}
    odd = [v for y, v in a.items() if y % 2]
    even = [v for y, v in a.items() if not y % 2]
    return np.mean(odd) / np.mean(even) - 1, odd, even


def test_thang_8(src):
    mi = _month_index(src)
    ratio, odd, even = _aug(mi, FULL)
    loo = [_aug(mi, [y for y in FULL if y != d])[0] for d in FULL]
    res = _run('get_calendar_pattern', pattern='thang_8')
    assert res.status == 'ok'
    h = res.rows[0]
    assert (h['n_odd_years'], h['n_even_years']) == (5, 5)
    assert h['august_index_odd'] == pytest.approx(np.mean(odd), rel=RTOL)
    assert h['august_index_even'] == pytest.approx(np.mean(even), rel=RTOL)
    assert h['august_odd_vs_even'] == pytest.approx(ratio, rel=RTOL)
    assert h['max_index_odd'] == pytest.approx(max(odd), rel=RTOL)
    assert h['min_index_even'] == pytest.approx(min(even), rel=RTOL)
    assert h['loo_min_odd_vs_even'] == pytest.approx(min(loo), rel=RTOL)
    assert h['loo_max_odd_vs_even'] == pytest.approx(max(loo), rel=RTOL)
    below = bool(max(odd) < min(even))
    assert res.derived['all_odd_below_all_even'] is below is True
    k = sum((y % 2 and mi[(y, 8)] < min(even)) or (not y % 2 and mi[(y, 8)] > max(odd)) for y in FULL)
    assert (h['n_years_with_pattern'], h['n_years']) == (k, 10)


def test_mua_vu(src):
    r_m, mi = src['r_m'], _month_index(src)
    pooled = lambda ys: pd.Series({m: sum(r_m[(y, m)] for y in ys) for m in range(1, 13)})
    p = pooled(FULL)
    loo = [pooled([y for y in FULL if y != d]) for d in FULL]
    res = _run('get_calendar_pattern', pattern='mua_vu')
    assert res.status == 'ok'
    h = res.rows[0]
    assert h['season_peak_trough_ratio'] == pytest.approx(p.max() / p.min(), rel=RTOL)
    assert h['loo_min_ratio'] == pytest.approx(min(s.max() / s.min() for s in loo), rel=RTOL)
    assert h['loo_max_ratio'] == pytest.approx(max(s.max() / s.min() for s in loo), rel=RTOL)
    # tháng cao / thấp nhất CẢ KỲ (R cùng tên tháng cộng 2013–2022), duy nhất
    assert (p == p.max()).sum() == 1 and (p == p.min()).sum() == 1
    assert (h['peak_month'], h['trough_month']) == (p.idxmax(), p.idxmin())
    k = 0
    for y in FULL:
        s = mi.loc[y]
        k += s.idxmax() in (4, 5, 6) and s.idxmin() in (12, 1)
    assert (h['n_years_with_pattern'], h['n_years']) == (k, 10)
    phases = res.rows[1:]
    assert [x['phase_code'] for x in phases] == list(PS3)
    for x in phases:
        ys = PS3[x['phase_code']]
        s = pooled(ys)
        idx = s / (s.sum() / 12)
        assert (x['first_year'], x['last_year'], x['n_years']) == (ys[0], ys[-1], len(ys))
        assert (x['peak_month'], x['trough_month']) == (idx.idxmax(), idx.idxmin())
        assert x['peak_index'] == pytest.approx(idx.max(), rel=RTOL)
        assert x['trough_index'] == pytest.approx(idx.min(), rel=RTOL)
        assert x['season_peak_trough_ratio'] == pytest.approx(idx.max() / idx.min(), rel=RTOL)
    assert res.derived['peak_months'] == sorted({x['peak_month'] for x in phases}) == [5]
    assert res.derived['trough_months'] == [12]
    # số giai đoạn có cùng tháng cao / thấp nhất với cả kỳ: tính từ CSV ở trên, không đọc lại từ tool
    same_peak = sum(pooled(PS3[c]).idxmax() == p.idxmax() for c in PS3)
    same_trough = sum(pooled(PS3[c]).idxmin() == p.idxmin() for c in PS3)
    assert (res.derived['n_phases_same_peak'], res.derived['n_phases_same_trough']) == (same_peak, same_trough) == (4, 4)
    assert res.derived['phase_year_rule']['decision_status'] == 'de_xuat'       # quy ước PS3 chưa chốt


def test_cuoi_thang(src):
    res = _run('get_calendar_pattern', pattern='cuoi_thang')
    assert res.status == 'ok'
    h = res.rows[0]
    assert h['eom_excess'] == pytest.approx(_eom_excess(src, FULL), rel=1e-9, abs=1e-12)
    loo = [_eom_excess(src, [y for y in FULL if y != d]) for d in FULL]
    assert h['loo_min_eom_excess'] == pytest.approx(min(loo), rel=RTOL)
    assert h['loo_max_eom_excess'] == pytest.approx(max(loo), rel=RTOL)
    k = sum(_eom_excess(src, [y]) > 0 for y in FULL)
    assert (h['n_years_with_pattern'], h['n_years']) == (k, 10)
    for x in res.rows[1:]:
        assert x['eom_excess'] == pytest.approx(_eom_excess(src, PS3[x['phase_code']]), rel=RTOL)
    assert res.derived['n_phases_eom_positive'] == sum(x['eom_excess'] > 0 for x in res.rows[1:])


# --- catalog, schema, bằng chứng ---

def test_catalog_mo_dung_to_hop_moi():
    names = {s['name']: s for s in tools.tool_schemas()}
    assert {'get_revenue_gap', 'get_revenue_monthly', 'get_revenue_trend', 'get_calendar_pattern'} <= set(names)
    assert names['get_revenue_trend']['input_schema']['properties']['view']['enum'] == ['phases', 'turning_points']
    assert metric_catalog.capability_blockers('get_revenue_drivers', {'metric': 'R', 'year': 2019, 'period_type': 'phase'})
    for f in metric_catalog.DEFINITION_FILES:
        assert (metric_catalog.ROOT / f).is_file(), f


@pytest.mark.parametrize('call', [
    ('get_revenue_gap', {'period': 'year', 'year': 2019}), ('get_revenue_monthly', {'metric': 'R', 'year': 2019, 'month': 8}),
    ('get_revenue_trend', {'view': 'phases'}), ('get_calendar_pattern', {'pattern': 'thang_8'})], ids=lambda c: c[0])
def test_bang_chung_cua_tool_moi(call):
    res = _run(call[0], **call[1])
    e = res.evidence
    assert res.status == 'ok' and e.tool == call[0] and e.queries and e.metrics
    assert all(q.source in tools.ALLOWED_RELATIONS for q in e.queries)
    assert e.quality['status_code'] == 'tot' and e.data_version['built_at_utc']


def test_moi_cot_so_cua_tool_moi_co_dinh_dang():
    """Cột số nào tool mới trả mà evidence không biết định dạng thì sẽ hiện kiểu 2 chữ số thập phân vô nghĩa."""
    known = (evidence.MONEY | evidence.PRICE | evidence.RATE | evidence.PP | evidence.PP_FRAC | evidence.COUNT
             | evidence.UNITS | evidence.INDEX | evidence.MONTHS | evidence.YEARS)
    calls = [('get_revenue_gap', {'period': 'year', 'year': 2019}), ('get_revenue_gap', {'period': '2013-2022'}),
             ('get_revenue_monthly', {'metric': 'R_and_G', 'year': 2019, 'month': 8}),
             ('get_revenue_trend', {'view': 'phases'}), ('get_revenue_trend', {'view': 'turning_points'})] + [
             ('get_calendar_pattern', {'pattern': p}) for p in ('mua_vu', 'cuoi_thang', 'thang_8')]
    for tool, args in calls:
        res = _run(tool, **args)
        cols = {k for r in res.rows for k, v in r.items() if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool)}
        assert cols <= known, (tool, sorted(cols - known))


# --- bộ kiểm câu trả lời trên kết quả tool thật (không LLM): câu đúng qua, câu sai bị chặn ---

VALIDATE_CASES = [
    # (tên, lời gọi, câu hỏi, answer, claims, kỳ vọng ok?)
    ('gap năm', ('get_revenue_gap', {'period': 'year', 'year': 2019}), 'G hụt sang R bao nhiêu năm 2019?',
     'Năm 2019, G là {c1} và R là {c2}, tức G − R là {c3}. Khoản làm hụt lớn nhất là {c4} với {c5}; R/G là {c6}.',
     [{'id': 'c1', 'path': 'T1.rows[0].g'}, {'id': 'c2', 'path': 'T1.rows[0].r'},
      {'id': 'c3', 'path': 'T1.derived.gap_g_minus_r'}, {'id': 'c4', 'path': 'T1.derived.largest_decrease.components'},
      {'id': 'c5', 'path': 'T1.rows[0].cancelled_gross'}, {'id': 'c6', 'path': 'T1.rows[0].capture_rate'}], True),
    ('gap sai: lớn nhất không trỏ xếp hạng', ('get_revenue_gap', {'period': 'year', 'year': 2019}), 'G hụt R 2019?',
     'Khoản lớn nhất là tiền hàng đơn hủy {c1}.', [{'id': 'c1', 'path': 'T1.rows[0].cancelled_gross'}], False),
    ('gap cả kỳ', ('get_revenue_gap', {'period': '2013-2022'}), 'Cả giai đoạn 2013–2022 R chiếm bao nhiêu G?',
     'Cả kỳ 2013–2022, R/G là {c1}; đơn hủy chiếm {c2} của G.',
     [{'id': 'c1', 'path': 'T1.rows[0].capture_rate'}, {'id': 'c2', 'path': 'T1.rows[0].share_cancelled'}], True),
    ('tháng', ('get_revenue_monthly', {'metric': 'R', 'year': 2019, 'month': 8}), 'R tháng 8/2019?',
     'R tháng 8/2019 là {c1}, giảm {c2} so với cùng tháng năm trước ({c3}); chỉ số tháng là {c4}.',
     [{'id': 'c1', 'path': 'T1.rows[0].r'}, {'id': 'c2', 'path': 'T1.rows[0].yoy_rate', 'sign': 'am'},
      {'id': 'c3', 'path': 'T1.rows[0].r_same_month_prior_year'}, {'id': 'c4', 'path': 'T1.rows[0].month_index'}], True),
    ('tháng sai dấu', ('get_revenue_monthly', {'metric': 'R', 'year': 2019, 'month': 8}), 'R tháng 8/2019?',
     'R tháng 8/2019 tăng {c1}.', [{'id': 'c1', 'path': 'T1.rows[0].yoy_rate'}], False),
    ('tháng 7/2013 yoy NULL', ('get_revenue_monthly', {'metric': 'R', 'year': 2013, 'month': 7}), 'R tháng 7/2013?',
     'R tháng 7/2013 đổi {c1} so cùng kỳ.', [{'id': 'c1', 'path': 'T1.rows[0].yoy_rate'}], False),
    ('giai đoạn ΔR', ('get_revenue_trend', {'view': 'phases'}), 'Giai đoạn nào giảm mạnh nhất?',
     'Theo mức đổi R (tiền), giai đoạn giảm mạnh nhất là {c1}, R giảm {c2}; theo CAGR cũng là {c3} với {c4} mỗi năm.',
     [{'id': 'c1', 'path': 'T1.derived.largest_decrease.phases'}, {'id': 'c2', 'path': 'T1.derived.largest_decrease.delta_r'},
      {'id': 'c3', 'path': 'T1.derived.largest_decrease_cagr.phases'},
      {'id': 'c4', 'path': 'T1.derived.largest_decrease_cagr.cagr'}], True),
    ('giai đoạn theo mã', ('get_revenue_trend', {'view': 'phases'}), 'CAGR giai đoạn A?',
     'Giai đoạn A có CAGR {c1}, R từ {c2} lên {c3}.',
     [{'id': 'c1', 'path': 'T1.rows[A].cagr'}, {'id': 'c2', 'path': 'T1.rows[A].r_start'},
      {'id': 'c3', 'path': 'T1.rows[A].r_end'}], True),
    ('giai đoạn sai hướng xếp hạng', ('get_revenue_trend', {'view': 'phases'}), 'Giai đoạn nào tăng mạnh nhất?',
     'Giai đoạn tăng mạnh nhất là {c1}.', [{'id': 'c1', 'path': 'T1.derived.largest_decrease.phases'}], False),
    ('điểm đổi hướng', ('get_revenue_trend', {'view': 'turning_points'}), 'Điểm đổi hướng nào lớn nhất?',
     'Cú đổi hướng giảm mạnh nhất là {c1}, độ lớn {c2}: R 12 tháng từ {c3} xuống {c4}.',
     [{'id': 'c1', 'path': 'T1.derived.largest_decrease.turns'}, {'id': 'c2', 'path': 'T1.rows[2018].magnitude', 'sign': 'am'},
      {'id': 'c3', 'path': 'T1.rows[2018].r_12m_before'}, {'id': 'c4', 'path': 'T1.rows[2018].r_12m_after'}], True),
    ('tháng 8', ('get_calendar_pattern', {'pattern': 'thang_8'}), 'Tháng 8 năm lẻ có luôn thấp hơn năm chẵn?',
     'Có: {c1}. Tính trên chỉ số tháng 8, năm lẻ thấp hơn năm chẵn {c2}; chỉ số cao nhất của năm lẻ là {c3}, thấp nhất '
     'của năm chẵn là {c4}. Bỏ lần lượt từng năm, mức chênh vẫn nằm trong khoảng {c5} đến {c6}.',
     [{'id': 'c1', 'path': 'T1.derived.odd_even_order'}, {'id': 'c2', 'path': 'T1.rows[0].august_odd_vs_even'},
      {'id': 'c3', 'path': 'T1.rows[0].max_index_odd'}, {'id': 'c4', 'path': 'T1.rows[0].min_index_even'},
      {'id': 'c5', 'path': 'T1.rows[0].loo_min_odd_vs_even'}, {'id': 'c6', 'path': 'T1.rows[0].loo_max_odd_vs_even'}], True),
    ('tháng 8 tự so sánh', ('get_calendar_pattern', {'pattern': 'thang_8'}), 'Tháng 8 năm lẻ?',
     'Chỉ số tháng 8 năm lẻ {c1} thấp hơn năm chẵn {c2}.',
     [{'id': 'c1', 'path': 'T1.rows[0].august_index_odd'}, {'id': 'c2', 'path': 'T1.rows[0].august_index_even'}], False),
    ('mùa vụ', ('get_calendar_pattern', {'pattern': 'mua_vu'}), 'Doanh thu cao nhất vào tháng nào?',
     'Ở cả {c1} giai đoạn, tháng cao nhất là tháng {c2} và tháng thấp nhất là tháng {c3}. Cả kỳ 2013–2022, chênh mùa '
     'cao/thấp là {c4} lần.', [{'id': 'c1', 'path': 'T1.derived.n_phases'}, {'id': 'c2', 'path': 'T1.derived.peak_months'},
                               {'id': 'c3', 'path': 'T1.derived.trough_months'},
                               {'id': 'c4', 'path': 'T1.rows[0].season_peak_trough_ratio'}], True),
    ('mùa vụ đảo cao/thấp', ('get_calendar_pattern', {'pattern': 'mua_vu'}), 'Tháng nào thấp nhất?',
     'Tháng thấp nhất là tháng {c1}.', [{'id': 'c1', 'path': 'T1.derived.peak_months'}], False),
    ('cuối tháng', ('get_calendar_pattern', {'pattern': 'cuoi_thang'}), 'Doanh thu có dồn về cuối tháng không?',
     'Có. Cả kỳ, R từ ngày 26 chiếm {c1}, trong khi nếu rải đều chỉ {c2}; mức dồn cuối tháng là {c3} điểm %. Giai đoạn C '
     'có mức dồn {c4}.', [{'id': 'c1', 'path': 'T1.rows[0].eom_share'}, {'id': 'c2', 'path': 'T1.rows[0].eom_expected_share'},
                          {'id': 'c3', 'path': 'T1.rows[0].eom_excess'}, {'id': 'c4', 'path': 'T1.rows[C].eom_excess'}], True),
    ('H14 cụt nghĩa', ('get_revenue_drivers', {'metric': 'R', 'year': 2019}), 'Vì sao R 2019 giảm?',
     'Thành phần kéo giảm nhiều nhất là {c1}, với mức đóng góp {c2}.',
     [{'id': 'c1', 'path': 'T1.rows[0].top_down_driver'}, {'id': 'c2', 'path': 'T1.rows[0].top_down_driver'}], False),
]


@pytest.mark.parametrize('case', VALIDATE_CASES, ids=lambda c: c[0])
def test_kiem_cau_tra_loi_ps123(case):
    name, call, q, answer, claims, expect = case
    res = {'T1': tools.run({'tool': call[0], 'arguments': call[1]}, 'duckdb')}
    chk = evidence.validate(answer, claims, res, frozenset(evidence.question_numbers(q)))
    assert chk.ok is expect, chk.errors


def test_tu_choi_duoc_nhac_thang_bat_dau_du_lieu():
    """Live 2026-10-05 (E31b): thông báo no_data ghi 2012-07-04, model viết "tháng 7/2012" → không được chặn."""
    res = {'T1': _run('get_revenue_monthly', metric='R', year=2012, month=3)}
    assert res['T1'].status == 'no_data'
    allowed = evidence.allowed_years(res) | evidence.question_numbers('Tháng 3/2012 doanh thu thực nhận là bao nhiêu?')
    assert evidence.check_digits('Dữ liệu chỉ bắt đầu từ tháng 7/2012, nên tháng 3/2012 không có số.', allowed) == []
    assert evidence.check_digits('Tháng 3/2012 khoảng 9 tỷ.', allowed)          # số kèm đơn vị vẫn bị chặn


def test_chenh_mua_giua_thang_cao_nhat_va_thap_nhat():
    """Live 2026-10-05 (E35): câu mô tả chính tỷ số cao nhất ÷ thấp nhất không bị coi là xếp hạng thiếu chỗ đặt."""
    res = {'T1': _run('get_calendar_pattern', pattern='mua_vu')}
    ok = evidence.validate('Chênh mùa cả kỳ giữa tháng cao nhất và tháng thấp nhất là {c1} lần.',
                           [{'id': 'c1', 'path': 'T1.rows[0].season_peak_trough_ratio'}], res)
    assert ok.ok, ok.errors
    bad = evidence.validate('Tháng cao nhất có chỉ số {c1}.', [{'id': 'c1', 'path': 'T1.rows[0].loo_min_ratio'}], res)
    assert not bad.ok


def test_khong_bo_ngam_bo_loc_nhom():
    """Live AI3 2026-10-05 (A08): hỏi Streetwear tháng 5/2019, model trả R toàn công ty tháng 5/2019 với status ok."""
    from ai_explain import service
    groups = tools.known_groups('duckdb')
    assert {'Streetwear', 'East', 'organic_search'} <= groups
    month = {'T1': _run('get_revenue_monthly', metric='R', year=2019, month=5)}
    chk = evidence.validate('R tháng 5/2019 là {c1}.', [{'id': 'c1', 'path': 'T1.rows[0].r'}], month,
                            frozenset(evidence.question_numbers('Doanh thu Streetwear tháng 5/2019?')))
    assert chk.ok
    assert service._group_filter_errors('ok', chk, 'Doanh thu Streetwear tháng 5/2019?', groups)      # nhóm × tháng
    assert service._group_filter_errors('ok', chk, 'R của Streetwear năm 2019?', groups)               # bỏ nhóm
    assert not service._group_filter_errors('unsupported', chk, 'Doanh thu Streetwear tháng 5/2019?', groups)
    seg = {'T1': _run('get_segment_contribution', metric='R', dimension='category', year=2019)}
    chk = evidence.validate('R của Streetwear năm 2019 là {c1}.', [{'id': 'c1', 'path': 'T1.rows[Streetwear].r'}], seg)
    assert chk.ok and not service._group_filter_errors('ok', chk, 'R của Streetwear năm 2019?', groups)



# Nguyên văn raw_final của model thật (log warehouse/ai_eval/, 2026-10-05). Trước khi sửa, app in số âm KHÔNG dấu vì
# trong câu có chữ "giảm" ở xa (tên giai đoạn "Chững, giảm nhẹ", "giảm mạnh nhất, CAGR {c}") → đọc thành tăng.
SIGN_LIVE = [
    ('B06 PG lần 1', ('get_revenue_trend', {'view': 'phases'}), 'Giai đoạn chững lại có CAGR bao nhiêu?',
     '{"status": "ok", "answer": "Giai đoạn chững lại là giai đoạn B — Chững, giảm nhẹ (2016→2018), với CAGR {c1} mỗi '
     'năm.", "claims": [{"id": "c1", "path": "T1.rows[B].cagr", "sign": "am"}]}',
     ['**−6,4%**'], []),
    ('B06 DuckDB', ('get_revenue_trend', {'view': 'phases'}), 'Giai đoạn chững lại có CAGR bao nhiêu?',
     '{"status": "ok", "answer": "Giai đoạn chững lại là giai đoạn B — Chững, giảm nhẹ (2016→2018), với CAGR {c1} mỗi '
     'năm (R giảm).", "claims": [{"id": "c1", "path": "T1.rows[B].cagr", "sign": "am"}]}',
     ['**−6,4%**'], []),
    ('E13 PG', ('get_revenue_trend', {'view': 'phases'}), 'Giai đoạn nào doanh thu giảm mạnh nhất?',
     '{"status": "ok", "answer": "Theo mức đổi R bằng tiền, giai đoạn giảm mạnh nhất là {c1}, với ΔR {c2}. Theo CAGR, '
     'cũng chính giai đoạn này giảm mạnh nhất, CAGR {c3}. Đây là mô tả xu hướng, không phải nguyên nhân; năm 2022 tăng '
     'lại chỉ là tín hiệu hồi phục cuối giai đoạn D, chưa tách thành giai đoạn mới.", "claims": [{"id": "c1", "path": '
     '"T1.derived.largest_decrease.phases"}, {"id": "c2", "path": "T1.derived.largest_decrease.delta_r", "sign": "am"}, '
     '{"id": "c3", "path": "T1.derived.largest_decrease_cagr.cagr", "sign": "am"}]}',
     ['**−554.945.327 VND**', '**−39,1%**'], []),
    # câu này vừa có số xa chữ "giảm" (c1: phải giữ dấu) vừa có "tức R giảm {c2}" (c2: chữ giảm liền trước, bỏ dấu)
    ('A03c PG', ('get_revenue_trend', {'view': 'turning_points'}), 'Cú đổi hướng cuối 2016 lớn cỡ nào?',
     '{"status": "ok", "answer": "Cú đổi hướng cuối 2016 (từ giai đoạn Tăng trưởng sang Chững, giảm nhẹ) có độ lớn {c1}: '
     'R mười hai tháng sau điểm so với mười hai tháng trước điểm, tức R giảm {c2}. Cú đổi hướng giảm mạnh nhất trong ba '
     'điểm là {c3}.", "claims": [{"id": "c1", "path": "T1.rows[2016].magnitude", "sign": "am"}, {"id": "c2", "path": '
     '"T1.rows[2016].delta_r", "sign": "am"}, {"id": "c3", "path": "T1.derived.largest_decrease.turns"}]}',
     ['**−9,7%**', 'tức R giảm **157.529.357 VND**'], ['−157.529.357']),
]


@pytest.mark.parametrize('case', SIGN_LIVE, ids=lambda c: c[0])
def test_so_am_khong_mat_dau_khi_chu_giam_o_xa(case):
    name, call, q, raw, must, banned = case
    d = json.loads(raw)
    res = {'T1': tools.run({'tool': call[0], 'arguments': call[1]}, 'duckdb')}
    chk = evidence.validate(d['answer'], d['claims'], res, frozenset(evidence.question_numbers(q)))
    assert chk.ok, chk.errors
    for x in must:
        assert x in chk.answer_md, chk.answer_md
    for x in banned:
        assert x not in chk.answer_md, chk.answer_md


@pytest.mark.parametrize('answer, shown', [
    ('R năm 2019 giảm {c1}.', '**554.945.327 VND**'),                              # chữ giảm liền trước: bỏ dấu cho dễ đọc
    ('Năm 2019, mức giảm R là {c1}.', '**554.945.327 VND**'),                      # 3 chữ ở giữa: còn bỏ dấu
    ('Mức giảm R năm 2019 là {c1}.', '**−554.945.327 VND**'),                      # 4 chữ ở giữa: giữ dấu
    ('R năm 2019 giảm so với năm 2018 một khoản {c1}.', '**−554.945.327 VND**'),   # xa hơn 3 chữ: giữ dấu
    ('R năm 2019 (giảm) là {c1}.', '**−554.945.327 VND**'),                        # qua ngoặc: giữ dấu
    ('Năm 2019 R đổi {c1}.', '**−554.945.327 VND**'),                              # không có chữ hướng: giữ dấu
])
def test_chi_bo_dau_khi_chu_huong_di_lien_truoc_so(answer, shown):
    res = {'T1': _run('get_revenue_summary', metric='R', year=2019, compare_prior_year=True)}
    chk = evidence.validate(answer, [{'id': 'c1', 'path': 'T1.rows[0].delta_r'}], res)
    assert chk.ok, chk.errors
    assert shown in chk.answer_md, chk.answer_md


def test_chu_huong_lien_truoc_so_sai_dau_thi_chan():
    """Câu có cả "tăng" lẫn "giảm" (cửa sổ rộng không kết luận được) nhưng chữ liền trước số ngược dấu → chặn,
    không được in giá trị tuyệt đối của một số ngược với chữ đứng ngay trước nó."""
    res = {'T1': _run('get_revenue_summary', metric='R', year=2022, compare_prior_year=True)}
    assert res['T1'].rows[0]['delta_r'] > 0
    bad = evidence.validate('R năm 2022 không tăng mà giảm {c1}.', [{'id': 'c1', 'path': 'T1.rows[0].delta_r'}], res)
    assert not bad.ok
    trend = {'T1': _run('get_revenue_trend', view='phases')}
    ok = evidence.validate('Giai đoạn C có tốc độ tăng trưởng {c1} mỗi năm.', [{'id': 'c1', 'path': 'T1.rows[C].cagr'}],
                           trend)
    assert ok.ok and '**−39,1%**' in ok.answer_md, (ok.errors, ok.answer_md)



A04_RAW = ('{"status": "ok", "answer": "Theo nhịp mùa vụ của R giai đoạn 2013–2022, tháng thấp nhất là tháng {c1}, và '
           'tháng cao nhất là tháng {c2}; chênh mùa cao/thấp cả kỳ là {c3}. Nhịp này có ở {c4} trên {c5} năm, và khi bỏ '
           'lần lượt từng năm thì chênh mùa dao động trong khoảng {c6} đến {c7}. Tháng thấp nhất cũng lặp lại ở cả {c8} '
           'giai đoạn. Lưu ý: số theo giai đoạn dùng cách gom năm đề xuất, đang chờ chốt.", "claims": [{"id": "c1", '
           '"path": "T1.derived.trough_months"}, {"id": "c2", "path": "T1.derived.peak_months"}, {"id": "c3", "path": '
           '"T1.rows[0].season_peak_trough_ratio"}, {"id": "c4", "path": "T1.rows[0].n_years_with_pattern"}, {"id": "c5", '
           '"path": "T1.rows[0].n_years"}, {"id": "c6", "path": "T1.rows[0].loo_min_ratio"}, {"id": "c7", "path": '
           '"T1.rows[0].loo_max_ratio"}, {"id": "c8", "path": "T1.derived.n_phases"}]}')


def test_cung_thang_thap_nhat_moi_giai_doan_phai_co_cho_dat_rieng():
    """Live PG 2026-10-05 (A04): "tháng thấp nhất lặp lại ở cả {c8} giai đoạn" với c8 = n_phases bị chặn (n_phases
    chỉ là số giai đoạn, không chứng minh cùng tháng). Ô n_phases_same_trough chứng minh được thì câu qua."""
    res = {'T1': _run('get_calendar_pattern', pattern='mua_vu')}
    d = json.loads(A04_RAW)
    q = frozenset(evidence.question_numbers('Tháng nào doanh thu thấp nhất trong năm?'))
    assert not evidence.validate(d['answer'], d['claims'], res, q).ok
    claims = [c if c['id'] != 'c8' else {'id': 'c8', 'path': 'T1.derived.n_phases_same_trough'} for c in d['claims']]
    chk = evidence.validate(d['answer'], claims, res, q)
    assert chk.ok, chk.errors
    assert 'lặp lại ở cả **4**' in chk.answer_md
    # tháng thấp nhất CẢ KỲ là ô riêng (E35 trước đây nói "cả kỳ" bằng tập tháng của từng giai đoạn)
    chk = evidence.validate('Cả kỳ 2013–2022, tháng cao nhất là tháng {c1}, thấp nhất là tháng {c2}.',
                            [{'id': 'c1', 'path': 'T1.rows[0].peak_month'}, {'id': 'c2', 'path': 'T1.rows[0].trough_month'}],
                            res)
    assert chk.ok and 'tháng **5**' in chk.answer_md and 'tháng **12**' in chk.answer_md, (chk.errors, chk.answer_md)
    # đảo chiều: "cao nhất" mà trỏ số giai đoạn cùng tháng THẤP nhất → chặn
    bad = evidence.validate('Tháng cao nhất lặp lại ở cả {c1} giai đoạn.',
                            [{'id': 'c1', 'path': 'T1.derived.n_phases_same_trough'}], res)
    assert not bad.ok
