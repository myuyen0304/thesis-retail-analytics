"""AI1: tool AI Explain trả đúng số, đúng kỳ/chiều, không bỏ điều kiện, xử lý lỗi trung thực (docs/ai_explain_plan.md §13).

Không có LLM trong file này: PASS ở đây KHÔNG phải live-model eval.

Số kỳ vọng tính THẲNG từ CSV trong data/ (pandas), không qua dbt, queries.py hay tool đang test:
- R   = payments.csv của đơn delivered theo order_date (nguồn độc lập với dòng hàng);
- G   = sales.csv.Revenue;
- N, Q, phần góp N/U/P và R theo nhóm = order_items × orders (× products / customers × geography), đơn delivered.
Tiền so CHÍNH XÁC theo cent nguyên (kho lưu decimal 2 chữ số). Tỷ lệ/phân rã là DOUBLE: sai số tương đối 1e-9.
Postgres không chạy thì các test _pg_ FAIL, không skip (quy ước test_backends.py).
"""
import os
import shutil
import time
import uuid
from decimal import Decimal
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from ai_explain import eval_cases, metric_catalog, tools
from ai_explain.contracts import ToolResult
from dwh import guarded, queries
from dwh.connection import DUCKDB_PATH, ROOT

DATA = ROOT / 'data'
RTOL = 1e-9
YEARS = range(2012, 2023)       # mọi năm tool get_revenue_summary mở
GROWTH = range(2014, 2023)      # mọi năm có so năm trước / phân rã / theo nhóm


def _cents(x: pd.Series) -> pd.Series:
    return np.round(x * 100).astype('int64')


@pytest.fixture(scope='module')
def src() -> dict:
    """Số đối chứng 2012–2022 từ CSV, phủ MỌI năm × chiều mà tool đang mở. Tiền theo cent nguyên."""
    R = lambda f, **k: pd.read_csv(DATA / f, low_memory=False, **k)
    o = R('orders.csv', usecols=['order_id', 'order_date', 'customer_id', 'order_status'])
    oi = R('order_items.csv', usecols=['order_id', 'product_id', 'quantity', 'unit_price', 'discount_amount'])
    pay = R('payments.csv', usecols=['order_id', 'payment_value'])
    pr = R('products.csv', usecols=['product_id', 'category'])
    cu = R('customers.csv', usecols=['customer_id', 'zip', 'acquisition_channel'])
    geo = R('geography.csv', usecols=['zip', 'region'])
    sales = R('sales.csv')
    # khóa trước khi join: mỗi đơn 1 dòng payments, sản phẩm/khách/zip là khóa
    assert o.order_id.is_unique and pay.order_id.is_unique and pr.product_id.is_unique
    assert cu.customer_id.is_unique and geo.zip.is_unique

    o['year'] = pd.to_datetime(o.order_date).dt.year
    oi['net_c'] = _cents(oi.quantity * oi.unit_price) - _cents(oi.discount_amount)
    # giữ từng dòng hàng (không dedup order_id × product_id)
    li = (oi.merge(o, on='order_id', validate='many_to_one')
            .merge(pr, on='product_id', validate='many_to_one')
            .merge(cu, on='customer_id', validate='many_to_one')
            .merge(geo, on='zip', validate='many_to_one'))
    assert len(li) == len(oi)
    ld = li[li.order_status == 'delivered']
    dlv = o[o.order_status == 'delivered']
    pay = pay.merge(dlv[['order_id', 'year']], on='order_id')
    sales['year'] = pd.to_datetime(sales.Date).dt.year

    out = {'year': {}, 'segment': {}}
    r_pay = pay.groupby('year').payment_value.apply(lambda s: int(_cents(s).sum()))
    g = sales.groupby('year').Revenue.apply(lambda s: int(_cents(s).sum()))
    r_li, q = ld.groupby('year').net_c.sum(), ld.groupby('year').quantity.sum()
    n = dlv.groupby('year').order_id.nunique()
    for y in YEARS:
        out['year'][y] = {'r_c': int(r_pay[y]), 'r_li_c': int(r_li[y]), 'g_c': int(g[y]), 'n': int(n[y]), 'q': int(q[y])}
    for dim in metric_catalog.DIMENSIONS:
        # lưới đủ nhóm × năm: nhóm xuất hiện ở BẤT KỲ trạng thái nào; năm không có R delivered = 0
        t = (ld.groupby([dim, 'year']).net_c.sum().unstack(fill_value=0)
               .reindex(index=sorted(li[dim].unique()), columns=list(YEARS), fill_value=0))
        out['segment'][dim] = {grp: {y: int(t.loc[grp, y]) for y in YEARS} for grp in t.index}
    return out


def _run(tool, **arguments) -> ToolResult:
    return tools.run({'tool': tool, 'arguments': arguments}, 'duckdb')


def _money(c: int) -> Decimal:
    return Decimal(c) / 100


# --- số đúng (so CSV), mọi năm/chiều đang mở ---

def test_hai_nguon_r_doc_lap_khop_nhau(src):
    # payments (dòng tiền theo đơn) và dòng hàng cho cùng R: hai đường đối chứng độc lập
    for y in YEARS:
        assert src['year'][y]['r_c'] == src['year'][y]['r_li_c'], y


@pytest.mark.parametrize('year', YEARS)
def test_e01_r_va_g_moi_nam(src, year):
    r = _run('get_revenue_summary', metric='R_and_G', year=year)
    assert r.status == 'ok' and len(r.rows) == 1
    row = r.rows[0]
    assert row['year'] == year and row['is_analysis_period'] is (year >= 2013)
    assert isinstance(row['r'], Decimal) and isinstance(row['g'], Decimal)     # không qua float
    assert row['r'] == _money(src['year'][year]['r_c'])
    assert row['g'] == _money(src['year'][year]['g_c'])
    assert {m['metric_id'] for m in r.evidence.metrics} == {'R', 'G'}


@pytest.mark.parametrize('year', GROWTH)
def test_e03_r_so_nam_truoc_moi_nam(src, year):
    r = _run('get_revenue_summary', metric='R', year=year, compare_prior_year=True)
    assert r.status == 'ok'
    row = r.rows[0]
    r0, r1 = src['year'][year - 1]['r_c'], src['year'][year]['r_c']
    assert row['r_prior_year'] == _money(r0) and row['r'] == _money(r1)
    assert row['delta_r'] == _money(r1 - r0)
    assert row['yoy_rate'] == pytest.approx(r1 / r0 - 1, rel=RTOL)
    assert 'g' not in row                                                       # chỉ cột của metric được hỏi


@pytest.mark.parametrize('year', GROWTH)
def test_e04_phan_ra_n_u_p_moi_nam(src, year):
    r = _run('get_revenue_drivers', metric='R', year=year)
    assert r.status == 'ok' and len(r.rows) == 1
    d = r.rows[0]
    y0, y1 = src['year'][year - 1], src['year'][year]
    u0, u1 = y0['q'] / y0['n'], y1['q'] / y1['n']
    p0, p1 = y0['r_c'] / 100 / y0['q'], y1['r_c'] / 100 / y1['q']
    assert (d['start_year'], d['end_year']) == (year - 1, year)
    assert d['r_start'] == _money(y0['r_c']) and d['r_end'] == _money(y1['r_c'])
    assert d['delta_r'] == _money(y1['r_c'] - y0['r_c'])
    assert (d['n_start'], d['n_end']) == (y0['n'], y1['n'])
    assert d['contrib_n'] == pytest.approx((y1['n'] - y0['n']) * u0 * p0, rel=RTOL)
    assert d['contrib_u'] == pytest.approx(y1['n'] * (u1 - u0) * p0, rel=RTOL)
    assert d['contrib_p'] == pytest.approx(y1['n'] * u1 * (p1 - p0), rel=RTOL)
    # ba phần góp cộng về ΔR (DOUBLE; sai số tuyệt đối nhỏ cho năm ΔR gần 0)
    assert r.derived['additive_check'] == pytest.approx(float(d['delta_r']), rel=RTOL, abs=1e-3)
    assert r.derived['small_delta_rule']['decision_status'] == 'de_xuat'
    assert 'không phải nguyên nhân' in r.message


def test_e04_2019_so_don_keo_giam():
    d = _run('get_revenue_drivers', metric='R', year=2019).rows[0]
    assert d['top_down_driver'] == 'n' and d['top_up_driver'] == 'p'


@pytest.mark.parametrize('year', GROWTH)
@pytest.mark.parametrize('dim', list(metric_catalog.DIMENSIONS))
def test_e05_e06_e17_nhom_moi_nam(src, dim, year):
    r = _run('get_segment_contribution', metric='R', dimension=dim, year=year)
    assert r.status == 'ok'
    exp = src['segment'][dim]
    r_tot0, r_tot1 = src['year'][year - 1]['r_c'], src['year'][year]['r_c']
    assert {x['dimension_value'] for x in r.rows} == set(exp)                   # đủ tập nhóm
    for x in r.rows:
        e = exp[x['dimension_value']]
        assert x['r'] == _money(e[year]) and x['r_prior_year'] == _money(e[year - 1])
        assert x['delta_r'] == _money(e[year] - e[year - 1])
        assert x['r_total'] == _money(r_tot1)                                   # mẫu số toàn công ty
        share, share0 = e[year] / r_tot1, e[year - 1] / r_tot0
        assert x['share'] == pytest.approx(share, rel=RTOL)
        # E17: share_shift_pp đã nhân 100 (điểm %), không nhân thêm
        assert x['share_shift_pp'] == pytest.approx((share - share0) * 100, rel=RTOL, abs=1e-9)
        assert x['contribution_to_delta'] == pytest.approx((e[year] - e[year - 1]) / (r_tot1 - r_tot0), rel=RTOL)
    # "kéo giảm nhiều nhất" = ΔR âm nhất, "kéo tăng nhiều nhất" = ΔR dương nhất, tính trên CSV
    deltas = {g: e[year] - e[year - 1] for g, e in exp.items()}
    # "giảm ít nhất" (smallest_*, PM 2026-10-09) = ΔR âm gần 0 nhất TRONG các nhóm giảm; tương tự chiều tăng
    for key, sign, pick in (('largest_decrease', -1, max), ('largest_increase', +1, max),
                            ('smallest_decrease', -1, min), ('smallest_increase', +1, min)):
        cand = {g: v for g, v in deltas.items() if sign * v > 0}
        if not cand:
            assert r.derived[key] is None
            continue
        best = pick(sign * v for v in cand.values())
        assert r.derived[key]['groups'] == sorted(g for g, v in cand.items() if sign * v == best)
        assert r.derived[key]['delta_r'] == _money(sign * best)
    assert sum(x['share'] for x in r.rows) == pytest.approx(1, rel=RTOL)
    assert sum(x['contribution_to_delta'] for x in r.rows) == pytest.approx(1, rel=RTOL)


def test_e05_khong_lay_delta_r_rank_1(src):
    # rpt_revenue_segment_yearly.delta_r_rank = 1 là TĂNG nhiều nhất / giảm ít nhất. Năm 2019 mọi ngành đều giảm,
    # nên rank 1 là ngành giảm ÍT nhất, không phải ngành kéo giảm mạnh nhất.
    r = _run('get_segment_contribution', metric='R', dimension='category', year=2019)
    seg = queries.segment_yearly('duckdb')
    rank1 = seg[(seg.dimension_name == 'category') & (seg.year == 2019) & (seg.delta_r_rank == 1)].dimension_value.item()
    assert r.derived['largest_decrease']['groups'] == ['Streetwear']
    assert rank1 != 'Streetwear'
    assert r.derived['largest_increase'] is None and r.derived['n_groups_down'] == 4


def test_e06_follow_up_doi_chieu_co_bang_chung_moi():
    a = _run('get_segment_contribution', metric='R', dimension='category', year=2019)
    b = _run('get_segment_contribution', metric='R', dimension='region', year=2019)
    assert a.evidence.request_id != b.evidence.request_id
    assert a.evidence.filters_applied == {'dimension_name': 'category', 'year': 2019}
    assert b.evidence.filters_applied == {'dimension_name': 'region', 'year': 2019}
    assert b.evidence.queries[-1].params == ('region', 2019)
    assert {x['dimension_name'] for x in b.rows} == {'region'}


def test_cung_so_voi_queries_cua_app():
    # parity với lớp query các trang đang dùng (bổ sung, không thay đối chứng CSV)
    d = _run('get_revenue_drivers', metric='R', year=2019).rows[0]
    app = queries.driver_period('duckdb')
    row = app[(app.period_type == 'year') & (app.period_code == '2019')].iloc[0]
    for c in ('contrib_n', 'contrib_u', 'contrib_p', 'r_change_rate', 'n_change_rate'):
        assert d[c] == row[c], c
    assert float(d['delta_r']) == row['delta_r']


# --- trạng thái theo bộ case §12 (phần tool) ---

@pytest.mark.parametrize('case', eval_cases.tool_cases(), ids=lambda c: c['case_id'])
def test_case_tool_layer(case):
    r = tools.run(case['tool_call'], 'duckdb')
    assert r.status == case['expected_status'], (case['case_id'], r.message)
    if r.status != 'ok':
        assert not r.rows and not r.derived and r.evidence is None


def test_e08_khong_bo_dieu_kien():
    c = next(c for c in eval_cases.CASES if c['case_id'] == 'E08')
    r = tools.run(c['tool_call'], 'duckdb')
    assert set(r.rejected) == {'region', 'start_date', 'end_date'}


def test_e02_thieu_metric_va_nam():
    r = _run('get_segment_contribution', dimension='category')
    assert r.status == 'needs_clarification' and r.missing == ['metric', 'year']


@pytest.mark.parametrize('year', ['2019', True, 2019.0, None])
def test_sai_kieu_bi_tu_choi(year):
    assert _run('get_revenue_summary', metric='R', year=year).status == 'unsupported'


def test_nam_2012_thieu_thang_co_canh_bao():
    r = _run('get_revenue_summary', metric='R', year=2012)
    assert r.status == 'ok' and r.rows[0]['is_analysis_period'] is False and 'thiếu tháng' in r.message


def test_e18_nhan_doc_hai_chi_la_tham_so():
    before = queries.revenue_yearly('duckdb')
    r = _run('get_segment_contribution', metric='R', dimension='category', year=2019,
             group="x'; drop table reporting.rpt_revenue_yearly; --")
    assert r.status == 'no_data'
    pd.testing.assert_frame_equal(queries.revenue_yearly('duckdb'), before)


def test_don_vi_tien_la_vnd():
    # PM chốt 2026-10-05: tiền là VND. Trước đó catalog cấm ghi đơn vị ("đơn vị tiền tệ chưa xác minh").
    d = metric_catalog.DECISIONS['currency_vnd']
    assert d['decision_status'] == 'chot' and 'VND' in d['text']
    assert {metric_catalog.METRICS[m]['unit'] for m in ('R', 'G', 'delta_r', 'contrib_nup')} == {'VND'}
    assert metric_catalog.METRICS['P']['unit'] == 'VND/món'
    texts = [str(metric_catalog.METRICS), str(metric_catalog.DECISIONS), str(tools.tool_schemas())]
    texts += [_run('get_revenue_drivers', metric='R', year=2019).message]
    for t in texts:
        for unit in ('USD', '$', 'chưa xác minh', 'đơn vị tiền tệ chưa'):
            assert unit not in t


def test_dinh_nghia_chi_tieu_lay_tu_catalog():
    res = _run('get_metric_definition', metric='R')
    assert res.ok and res.evidence.grain == 'định nghĩa'
    row = res.rows[0]
    assert row['metric_id'] == 'R' and 'delivered' in row['formula'] and row['decision_status'] == 'chot'
    assert row['unit'] == 'VND' and not res.derived
    assert _run('get_metric_definition', metric='X').status == 'unsupported'
    assert _run('get_metric_definition', metric='R', year=2019).status == 'unsupported'   # không có tham số năm


def test_tool_schema_chat():
    for s in tools.tool_schemas():
        assert s['input_schema']['additionalProperties'] is False
        assert 'backend' not in s['input_schema']['properties']


@pytest.mark.parametrize('mode', ['closed', 'missing'])
def test_catalog_dong_hoac_thieu_thi_khong_mo_ket_noi(monkeypatch, mode):
    catalog = ([(*c[:5], 'closed', c[6]) for c in metric_catalog.CAPABILITIES] if mode == 'closed' else [])
    monkeypatch.setattr(metric_catalog, 'CAPABILITIES', catalog)
    monkeypatch.setattr(tools, 'open_session', lambda *a, **kw: pytest.fail('Không được mở kết nối'))
    for tool, args in [
        ('get_revenue_summary', {'metric': 'R_and_G', 'year': 2019}),
        ('get_revenue_summary', {'metric': 'R', 'year': 2019, 'compare_prior_year': True}),
        ('get_revenue_drivers', {'metric': 'R', 'year': 2019}),
        ('get_segment_contribution', {'metric': 'R', 'year': 2019, 'dimension': 'category'}),
    ]:
        res = _run(tool, **args)
        assert res.status == 'unsupported' and 'capability' in res.rejected
        assert not res.rows and res.evidence is None
    assert tools.tool_schemas() == []


@pytest.mark.parametrize('key,blocked,kept', [
    (('get_revenue_summary', 'G', 'year'),
     {'tool': 'get_revenue_summary', 'metric': 'R_and_G'},
     {'tool': 'get_revenue_summary', 'metric': 'R'}),
    (('get_revenue_summary', 'R', 'year_vs_prior'),
     {'tool': 'get_revenue_summary', 'metric': 'R', 'compare_prior_year': True},
     {'tool': 'get_revenue_summary', 'metric': 'R', 'compare_prior_year': False}),
    (('get_segment_contribution', 'R', 'year', 'chiều × nhóm × năm', 'region'),
     {'tool': 'get_segment_contribution', 'metric': 'R', 'dimension': 'region'},
     {'tool': 'get_segment_contribution', 'metric': 'R', 'dimension': 'category'}),
])
def test_catalog_dong_tung_to_hop_schema_va_runtime_cung_doi(monkeypatch, key, blocked, kept):
    monkeypatch.setattr(metric_catalog, 'CAPABILITIES', [
        (*c[:5], 'closed', c[6]) if c[:len(key)] == key else c for c in metric_catalog.CAPABILITIES])
    tool = blocked['tool']
    args = {k: v for k, v in blocked.items() if k != 'tool'}
    with monkeypatch.context() as m:
        m.setattr(tools, 'open_session', lambda *a, **kw: pytest.fail('Không được mở kết nối'))
        assert _run(tool, year=2019, **args).status == 'unsupported'
    props = next(s for s in tools.tool_schemas() if s['name'] == tool)['input_schema']['properties']
    changed = next(k for k in args if args[k] != kept[k])
    assert args[changed] not in props[changed]['enum']
    assert _run(kept['tool'], year=2019, **{k: v for k, v in kept.items() if k != 'tool'}).ok


# --- bằng chứng ---

def test_bang_chung_day_du():
    r = _run('get_revenue_drivers', metric='R', year=2019)
    e = r.evidence
    assert len(e.request_id) == 32 and e.backend == 'duckdb' and e.source_description.startswith('DuckDB')
    assert e.arguments_applied == {'metric': 'R', 'year': 2019, 'period_type': 'year'}
    assert e.filters_applied == {'period_type': 'year', 'period_code': '2019'}
    bi = queries.build_info('duckdb').iloc[0]
    assert e.data_version['built_at_utc'] == bi.built_at_utc.isoformat()
    assert e.data_version['data_end_date'] == '2022-12-31'
    assert e.quality['status_code'] == 'tot' and e.quality['built_at_utc'] == e.data_version['built_at_utc']
    assert e.definition_version.startswith('sql-sha256:')
    assert [q.source for q in e.queries] == ['reporting.rpt_build_info', 'reporting.rpt_health_summary',
                                             'reporting.rpt_driver_period', 'reporting.driver_rule']
    assert e.queries[2].params == ('2019',) and '?' in e.queries[2].sql and '2019' not in e.queries[2].sql
    assert all(m['decision_status'] in ('chot', 'de_xuat') for m in e.metrics)


# --- giới hạn thực thi ---

def test_timeout_duckdb_ngat_truy_van():
    sess = guarded.open_session('duckdb', tools.ALLOWED_RELATIONS, timeout_s=0.3)
    t0 = time.monotonic()
    try:
        with pytest.raises(guarded.QueryTimeout):
            sess.fetch(guarded.Statement('select count(*) from range(100000000000) a, range(10) b'))
    finally:
        sess.close()
    assert time.monotonic() - t0 < 5


def test_vuot_so_dong_thi_tu_choi_khong_cat():
    sess = guarded.open_session('duckdb', tools.ALLOWED_RELATIONS, max_rows=5)
    try:
        assert len(sess.fetch(guarded.Statement('select * from range(5)')).rows) == 5
        with pytest.raises(guarded.RowLimitExceeded):
            sess.fetch(guarded.Statement('select * from range(6)'))
    finally:
        sess.close()
    r = tools.run({'tool': 'get_segment_contribution',
                   'arguments': {'metric': 'R', 'dimension': 'acquisition_channel', 'year': 2019}}, 'duckdb', max_rows=5)
    assert r.status == 'query_error' and not r.rows and not r.derived


def test_sql_cho_ai_khong_chua_phan_tram():
    with pytest.raises(ValueError):
        guarded.Statement("select 1 where 'a' like 'a%'").render('duckdb')


def test_timeout_trong_tool_khong_tra_so(monkeypatch):
    class _Cham:
        def fetch(self, st):
            raise guarded.QueryTimeout('quá 5 giây')

        def close(self):
            pass

    monkeypatch.setattr(tools, 'open_session', lambda *a, **k: _Cham())
    r = _run('get_revenue_drivers', metric='R', year=2019)
    assert r.status == 'query_error' and 'quá thời gian' in r.message and not r.rows


def test_khong_mo_duoc_kho(monkeypatch, tmp_path):
    monkeypatch.setenv('RETAIL_DUCKDB_PATH', str(tmp_path / 'khong_co.duckdb'))
    r = _run('get_revenue_summary', metric='R', year=2019)
    assert r.status == 'query_error' and not r.rows


# --- cổng chất lượng (bản sao DB, file gốc không đổi) ---

def _ban_sao(tmp_path: Path, sql: str) -> Path:
    p = tmp_path / 'dbt.duckdb'      # giữ tên dbt.duckdb: view trỏ bảng qua catalog "dbt"
    shutil.copy(DUCKDB_PATH, p)
    con = duckdb.connect(str(p))
    con.execute(sql)
    con.close()
    return p


def test_kho_dung_lai_sau_lan_kiem_thi_chan(monkeypatch, tmp_path):
    # build marker mới hơn lần chạy test cuối → rpt_health_summary không còn 'tot'
    p = _ban_sao(tmp_path, "update reporting.rpt_build_info set built_at_utc = built_at_utc + interval 1 day")
    monkeypatch.setenv('RETAIL_DUCKDB_PATH', str(p))
    r = _run('get_revenue_summary', metric='R', year=2019)
    assert r.status == 'quality_blocked' and 'status_code=' in r.message and not r.rows


def test_build_info_rong_thi_chan(monkeypatch, tmp_path):
    p = _ban_sao(tmp_path, 'delete from reporting.rpt_build_info')
    monkeypatch.setenv('RETAIL_DUCKDB_PATH', str(p))
    assert _run('get_revenue_summary', metric='R', year=2019).status == 'quality_blocked'


def test_e22_dong_hang_giu_moi_nhom(monkeypatch, tmp_path):
    # cho Outdoor giảm đúng bằng Streetwear năm 2019 → hai nhóm đồng hạng "kéo giảm nhiều nhất"
    p = _ban_sao(tmp_path, "update reporting.rpt_revenue_segment_yearly set delta_r = -463947221.16 "
                           "where dimension_name = 'category' and dimension_value = 'Outdoor' and year = 2019")
    monkeypatch.setenv('RETAIL_DUCKDB_PATH', str(p))
    r = _run('get_segment_contribution', metric='R', dimension='category', year=2019)
    assert r.status == 'ok'
    assert r.derived['largest_decrease'] == {'groups': ['Outdoor', 'Streetwear'], 'delta_r': Decimal('-463947221.16'),
                                             'tie': True}


def test_dong_hang_phia_giam_it_nhat_giu_moi_nhom(monkeypatch, tmp_path):
    # GenZ giảm đúng bằng Casual năm 2019 → hai nhóm đồng hạng "giảm ít nhất"
    p = _ban_sao(tmp_path, "update reporting.rpt_revenue_segment_yearly set delta_r = -22448070.60 "
                           "where dimension_name = 'category' and dimension_value = 'GenZ' and year = 2019")
    monkeypatch.setenv('RETAIL_DUCKDB_PATH', str(p))
    r = _run('get_segment_contribution', metric='R', dimension='category', year=2019)
    assert r.derived['smallest_decrease'] == {'groups': ['Casual', 'GenZ'], 'delta_r': Decimal('-22448070.60'), 'tie': True}


def test_bang_nhom_thieu_dong_thi_khong_xep_hang(monkeypatch, tmp_path):
    p = _ban_sao(tmp_path, "delete from reporting.rpt_revenue_segment_yearly "
                           "where dimension_name = 'category' and dimension_value = 'Streetwear'")
    monkeypatch.setenv('RETAIL_DUCKDB_PATH', str(p))
    r = _run('get_segment_contribution', metric='R', dimension='category', year=2019)
    assert r.status == 'query_error' and not r.derived


# --- PostgreSQL: tài khoản AI ---

def test_pg_thieu_tai_khoan_ai_thi_khong_doc(monkeypatch):
    monkeypatch.delenv('PG_AI_USER', raising=False)
    r = tools.run({'tool': 'get_revenue_summary', 'arguments': {'metric': 'R', 'year': 2019}}, 'postgres')
    assert r.status == 'query_error' and 'PG_AI_USER' in r.message


def test_pg_tu_choi_tai_khoan_superuser_cua_app(monkeypatch):
    # tài khoản app/dbt (retail) là superuser → guard phải từ chối dù câu SQL chỉ là SELECT
    monkeypatch.setenv('PG_AI_USER', os.environ.get('PG_USER', 'retail'))
    monkeypatch.setenv('PG_AI_PASSWORD', os.environ.get('PG_PASSWORD', 'retail'))
    r = tools.run({'tool': 'get_revenue_summary', 'arguments': {'metric': 'R', 'year': 2019}}, 'postgres')
    assert r.status == 'query_error' and 'superuser' in r.message, r.message


def _pg_env(monkeypatch) -> tuple[str, str]:
    # cần chạy scripts/ops/pg_ai_readonly_role.py sau mỗi `dbt build --target postgres`
    user = os.environ.get('PG_AI_USER', 'retail_ai_ro')
    password = os.environ.get('PG_AI_PASSWORD', 'retail_ai_ro')
    monkeypatch.setenv('PG_AI_USER', user)
    monkeypatch.setenv('PG_AI_PASSWORD', password)
    return user, password


def _giong_nhau(a, b, path='') -> None:
    # Decimal/int/str phải bằng tuyệt đối; float (DOUBLE) cho sai số tương đối 1e-12
    if isinstance(b, dict):
        assert isinstance(a, dict) and set(a) == set(b), path
        for k in b:
            _giong_nhau(a[k], b[k], f'{path}.{k}')
    elif isinstance(b, (list, tuple)):
        assert isinstance(a, (list, tuple)) and len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            _giong_nhau(x, y, f'{path}[{i}]')
    elif isinstance(b, float):
        assert a == pytest.approx(b, rel=1e-12, abs=1e-9), path
    else:
        assert a == b, path


_PG_CALLS = ([('get_revenue_summary', {'metric': 'R_and_G', 'year': y}) for y in YEARS]
             + [('get_revenue_summary', {'metric': 'R', 'year': y, 'compare_prior_year': True}) for y in GROWTH]
             + [('get_revenue_drivers', {'metric': 'R', 'year': y}) for y in GROWTH]
             + [('get_segment_contribution', {'metric': 'R', 'dimension': d, 'year': y})
                for d in metric_catalog.DIMENSIONS for y in GROWTH]
             # AI3: PS1–PS3 (DuckDB == CSV ở tests/test_ai_tools_ps123.py)
             + [('get_revenue_gap', {'period': 'year', 'year': y}) for y in YEARS]
             + [('get_revenue_gap', {'period': '2013-2022'})]
             + [('get_revenue_monthly', {'metric': 'R_and_G', 'year': y, 'month': m}) for y in (2012, 2013, 2019)
                for m in (7, 8, 12)]
             + [('get_revenue_trend', {'view': v}) for v in ('phases', 'turning_points')]
             + [('get_calendar_pattern', {'pattern': p}) for p in ('mua_vu', 'cuoi_thang', 'thang_8')])


@pytest.mark.parametrize('tool,args', _PG_CALLS, ids=lambda x: x if isinstance(x, str) else '-'.join(map(str, x.values())))
def test_pg_tra_cung_so_duckdb_moi_nam(monkeypatch, tool, args):
    # PG == DuckDB ở mọi năm × chiều đang mở; cùng với DuckDB == CSV ở trên → PG == CSV
    _pg_env(monkeypatch)
    pg = tools.run({'tool': tool, 'arguments': args}, 'postgres')
    dk = tools.run({'tool': tool, 'arguments': args}, 'duckdb')
    assert pg.status == dk.status == 'ok', pg.message
    _giong_nhau(pg.rows, dk.rows, 'rows')
    _giong_nhau(pg.derived, dk.derived, 'derived')     # gồm largest_decrease/increase, additive_check


def test_pg_role_chi_doc_khong_ghi_duoc(monkeypatch):
    import psycopg
    user, password = _pg_env(monkeypatch)
    conn = psycopg.connect(host=os.environ.get('PG_HOST', 'localhost'), port=int(os.environ.get('PG_PORT', '5433')),
                           dbname=os.environ.get('PG_DATABASE', 'retail'), user=user, password=password,
                           connect_timeout=5, autocommit=False)
    try:
        denied = (psycopg.errors.InsufficientPrivilege, psycopg.errors.ReadOnlySqlTransaction)
        # WHERE false không sửa dòng nào kể cả khi quyền sai. Mỗi phép thử luôn rollback,
        # kể cả pytest.raises thất bại; DDL dùng tên riêng để không đụng bảng của lượt khác.
        table = f'ai_permission_probe_{uuid.uuid4().hex}'
        for sql in ('update reporting.rpt_revenue_yearly set r = r where false',
                    f'create table reporting.{table} (x int)'):
            _assert_pg_statement_denied(conn, sql, denied)
        _assert_pg_statement_denied(conn, 'select count(*) from reporting.int_reporting_order_items',
                                    psycopg.errors.InsufficientPrivilege)
    finally:
        conn.rollback()
        conn.close()


def _assert_pg_statement_denied(conn, sql, denied):
    with conn.transaction(force_rollback=True):
        with pytest.raises(denied):
            conn.execute(sql)


def test_pg_probe_rollback_ke_ca_quyen_viet_bi_cap_nham(monkeypatch):
    """Thử nhánh nguy hiểm trên bảng tạm của phiên: assertion fail vẫn hoàn tác ghi/DDL."""
    import psycopg
    user, password = _pg_env(monkeypatch)
    with psycopg.connect(host=os.environ.get('PG_HOST', 'localhost'), port=int(os.environ.get('PG_PORT', '5433')),
                          dbname=os.environ.get('PG_DATABASE', 'retail'), user=user, password=password,
                          connect_timeout=5, autocommit=False) as conn:
        # Chỉ phiên kiểm thử được phép ghi để mô phỏng cấp nhầm quyền; role thật vẫn giữ nguyên.
        # Các lệnh bên dưới chỉ tác động bảng TEMP của phiên, không sửa bảng reporting.
        conn.read_only = False
        conn.execute('create temp table ai_probe_existing (value int)')
        conn.execute('insert into ai_probe_existing values (7)')
        for sql in ('update ai_probe_existing set value = 0',
                    'create temp table ai_probe_created (value int)'):
            with pytest.raises(pytest.fail.Exception, match='DID NOT RAISE'):
                _assert_pg_statement_denied(conn, sql, psycopg.errors.InsufficientPrivilege)
        assert conn.execute('select value from ai_probe_existing').fetchone() == (7,)
        assert conn.execute("select to_regclass('pg_temp.ai_probe_created')").fetchone() == (None,)
        conn.rollback()


def test_pg_timeout_ngat_truy_van(monkeypatch):
    # statement_timeout của phiên (SET LOCAL) phải ngắt câu chạy lâu, không đợi hết 5 giây
    monkeypatch.setenv('PG_AI_USER', os.environ.get('PG_AI_USER', 'retail_ai_ro'))
    monkeypatch.setenv('PG_AI_PASSWORD', os.environ.get('PG_AI_PASSWORD', 'retail_ai_ro'))
    sess = guarded.open_session('postgres', tools.ALLOWED_RELATIONS, timeout_s=0.3)
    t0 = time.monotonic()
    try:
        with pytest.raises(guarded.QueryTimeout):
            sess.fetch(guarded.Statement('select pg_sleep(5)'))
    finally:
        sess.close()
    assert time.monotonic() - t0 < 3


def test_dbt_cap_lai_quyen_ai_dung_danh_sach_tool():
    """Hook on-run-end của dbt (macros/ai_readonly_grants.sql) cấp SELECT theo var ai_readonly_relations: danh sách đó
    phải trùng ALLOWED_RELATIONS, không thừa (role AI đọc bảng ngoài phạm vi) cũng không thiếu (tool lỗi quyền)."""
    import re

    import yaml
    from dwh.connection import ROOT
    proj = yaml.safe_load((ROOT / 'retail_dbt' / 'dbt_project.yml').read_text(encoding='utf-8'))
    assert set(proj['vars']['ai_readonly_relations']) == set(tools.ALLOWED_RELATIONS)
    assert '{{ ai_readonly_grants() }}' in proj['on-run-end']
    macro = re.sub(r'\{#.*?#\}', '', (ROOT / 'retail_dbt' / 'macros' / 'ai_readonly_grants.sql').read_text(
        encoding='utf-8'), flags=re.S)                                   # bỏ phần chú thích, chỉ xét SQL
    assert "target.type == 'postgres'" in macro and 'pg_roles' in macro and 'default privileges' not in macro.lower()
    # Databricks: SELECT từng bảng trong var, KHÔNG cấp SELECT cả schema/catalog (thừa kế xuống mọi bảng)
    assert "target.type == 'databricks'" in macro and "env_var('RETAIL_AI_DBX_PRINCIPAL'" in macro
    # SP của app (Databricks Apps) chỉ đọc đúng các bảng mà trang đọc
    assert set(proj['vars']['app_read_relations']) == set(queries.SOURCE.values())
    assert "env_var('RETAIL_APP_DBX_PRINCIPAL', ''), var('app_read_relations')" in macro
    # SP của bản public trên Streamlit Community Cloud: cùng danh sách bảng của trang, không phải danh sách AI
    assert "env_var('RETAIL_WEB_DBX_PRINCIPAL', ''), var('app_read_relations')" in macro
    assert 'grant select on table' in macro and not re.search(r'grant (select|all)[^\n]*on (schema|catalog)', macro, re.I)
