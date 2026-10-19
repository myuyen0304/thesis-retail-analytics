"""B3a: tool chat get_forecast / get_forecast_backtest đọc dự báo của bản dữ liệu (docs/ke_hoach_ai_gd2.md, hợp đồng
dự báo §5–§8).

Không có LLM thật trong file này: PASS ở đây KHÔNG phải live-model eval (bộ G* chạy bằng scripts/ops/ai_live_eval.py).

Số kỳ vọng tính THẲNG từ parquet do stage dự báo ghi (`warehouse/pipeline/runs/<run>/forecast/*.parquet`), không qua dbt,
guard hay tool đang test. Cần một bản dữ liệu đã publish có dự báo (pipeline B2b chạy local); chưa có thì skip.
"""
import datetime as dt
import json
import re
from pathlib import Path

import pandas as pd
import pytest
import yaml

from ai_explain import evidence, metric_catalog as cat, service, tools
from ai_explain.contracts import ToolCall
from dwh import guarded, releases
from dwh.connection import ROOT
from tests.test_ai_chat import E04_OK, FakeProvider, call, final

STATE = ROOT / 'warehouse' / 'pipeline' / 'state.json'
RTOL = 1e-9
PRE_B2B = '6f8654fb4b4348c483a78b64'          # bản dựng trước B2b: không có rpt_forecast_*


def _state() -> dict | None:
    if not STATE.exists():
        return None
    return json.loads(STATE.read_text(encoding='utf-8'))['payload']


@pytest.fixture(scope='module')
def ref():
    """(record bản đang phục vụ, dự báo theo ngày, backtest) từ parquet của chính lần chạy đã tạo bản đó."""
    st = _state()
    if not st or not st.get('active'):
        pytest.skip('chưa có bản dữ liệu do pipeline publish (warehouse/pipeline/state.json)')
    rec = st['releases'][st['active']]
    fdir = STATE.parent / 'runs' / rec['run_id'] / 'forecast'
    if not (fdir / 'forecast_daily.parquet').exists():
        pytest.skip(f'bản {rec["release_id"]} không có dự báo (dựng trước B2b)')
    daily = pd.read_parquet(fdir / 'forecast_daily.parquet')
    daily['forecast_date'] = pd.to_datetime(daily.forecast_date).dt.date
    return rec, daily, pd.read_parquet(fdir / 'forecast_backtest.parquet')


@pytest.fixture
def versioned(monkeypatch, ref):
    monkeypatch.setenv('RETAIL_RELEASE_MODE', 'versioned')
    monkeypatch.setenv('RETAIL_RELEASE_STATE', str(STATE))
    releases.reset()
    yield
    releases.reset()


def _run(tool='get_forecast', **a):
    return tools.run(ToolCall(tool, a), 'duckdb')


def _primary(daily):
    p = daily[daily.is_primary]
    assert p[['model', 'cogs_method']].drop_duplicates().shape[0] == 1
    return p


# --- số khớp nguồn độc lập ---

@pytest.mark.parametrize('day', [dt.date(2023, 1, 1), dt.date(2023, 8, 1), dt.date(2024, 2, 29), dt.date(2024, 7, 1)])
def test_ngay_khop_parquet(versioned, ref, day):
    _, daily, _ = ref
    exp = _primary(daily).set_index('forecast_date').loc[day]
    r = _run(metric='G_and_COGS', period='day', year=day.year, month=day.month, day=day.day)
    assert r.status == 'ok', r.message
    row = r.rows[0]
    assert row['g_forecast'] == pytest.approx(exp.yhat, rel=RTOL)
    assert (row['lower_g'], row['upper_g']) == pytest.approx((exp.lower, exp.upper), rel=RTOL)
    assert row['cogs_forecast'] == pytest.approx(exp.cogs_yhat, rel=RTOL)
    assert row['is_primary'] and row['candidate'] == f'{exp.model}/{exp.cogs_method}'
    assert r.evidence.data_version['release_id'] == ref[0]['release_id']      # bằng chứng ghi đúng bản đang đọc


def test_moi_thang_khop_parquet_va_thang_thieu_ngay(versioned, ref):
    _, daily, bt = ref
    p = _primary(daily).assign(y=lambda d: [x.year for x in d.forecast_date], m=lambda d: [x.month for x in d.forecast_date])
    exp = p.groupby(['y', 'm']).agg(g=('yhat', 'sum'), cogs=('cogs_yhat', 'sum'), n=('yhat', 'size'))
    m0 = p.iloc[0]
    tme = bt[(bt.model == m0.model) & (bt.cogs_method == m0.cogs_method) & (bt.metric == 'mape_g_thang')].value.mean()
    assert len(exp) == 19
    for (y, m), e in exp.iterrows():
        r = _run(metric='G_and_COGS', period='month', year=int(y), month=int(m))
        assert r.status == 'ok', (y, m, r.message)
        row = r.rows[0]
        assert row['g_forecast'] == pytest.approx(e.g, rel=RTOL) and row['cogs_forecast'] == pytest.approx(e.cogs, rel=RTOL)
        assert row['n_days'] == e.n and row['is_partial'] == ((y, m) == (2024, 7))
        assert row['typical_month_error'] == pytest.approx(tme, rel=RTOL)        # Q7: tháng không có khoảng
        assert 'lower_g' not in row and 'upper_g' not in row
    assert 'missing_part' in _run(metric='G', period='month', year=2024, month=7).derived


def test_nam_va_ca_ky(versioned, ref):
    _, daily, _ = ref
    p = _primary(daily)
    y23 = p[[d.year == 2023 for d in p.forecast_date]]
    r = _run(metric='G', period='year', year=2023)
    assert r.rows[0]['g_forecast'] == pytest.approx(y23.yhat.sum(), rel=RTOL) and not r.rows[0]['is_partial']
    r = _run(metric='G', period='year', year=2024)                          # "cả năm 2024": chỉ tới 2024-07-01
    assert r.status == 'ok' and r.rows[0]['n_days'] == 183 and r.rows[0]['is_partial']
    assert r.derived['missing_part'].startswith('2024-07-02 → 2024-12-31')
    h = _run(metric='G', period='horizon')
    assert h.derived['horizon_total']['n_days'] == 548
    assert h.derived['horizon_total']['g_forecast'] == pytest.approx(p.yhat.sum(), rel=RTOL)
    months = {(x.year, x.month) for x in p.forecast_date}
    full = {k: v for k, v in p.groupby([[(d.year, d.month) for d in p.forecast_date]]).yhat.sum().items()
            if k != (2024, 7)}
    hi = max(full, key=full.get)
    assert len(months) == 19 and h.derived['highest_month']['months'] == [f'{hi[1]:02d}/{hi[0]}']


def test_backtest_khop_parquet(versioned, ref):
    _, daily, bt = ref
    r = _run('get_forecast_backtest')
    assert r.status == 'ok', r.message
    mean = bt[bt.metric.isin(['score', 'mape_g_thang'])].groupby(['model', 'cogs_method', 'metric']).value.mean()
    by = {x['candidate']: x for x in r.rows}
    for (m, c, metric), v in mean.items():
        assert by[f'{m}/{c}'][metric] == pytest.approx(v, rel=RTOL)
    sc = bt[bt.metric == 'score']
    floor = sc[sc.role == 'floor'].set_index('fold_origin').value
    for (m, c), g in sc[sc.role != 'floor'].groupby(['model', 'cogs_method']):
        assert by[f'{m}/{c}']['beats_floor_all_folds'] == bool((g.set_index('fold_origin').value < floor).all())
    cand = mean.xs('score', level='metric')[[k for k in mean.xs('score', level='metric').index
                                           if by[f'{k[0]}/{k[1]}']['role'] == 'candidate']]
    best = cand.idxmin()
    assert r.derived['lowest_score']['candidates'] == [by[f'{best[0]}/{best[1]}']['candidate_label']]
    prim = _primary(daily).iloc[0]
    assert r.derived['primary']['candidate'] == f'{prim.model}/{prim.cogs_method}'
    assert r.derived['primary']['selection_reason'] == tools.SELECTION_REASON[prim.selection_step]
    # hai thước xếp hạng khác nhau ở bản này: agent phải nêu cả hai (hợp đồng §7)
    assert r.derived['rankings_differ'] == (set(r.derived['lowest_score']['candidates'])
                                            != set(r.derived['lowest_mape_g_thang']['candidates']))
    assert 'không phải độ chính xác trên 2023–2024' in r.message


# --- ứng viên khác model chính ---

def test_ung_vien_khac_khong_thay_the(versioned, ref):
    _, daily, _ = ref
    r = _run(metric='COGS', period='month', year=2023, month=8, model='sarimax_full')
    assert r.status == 'needs_clarification' and r.missing == ['cogs_method']        # hỏi COGS: không tự chọn cách COGS
    aug = pd.Series([d.year == 2023 and d.month == 8 for d in daily.forecast_date], index=daily.index)
    # chỉ hỏi G (live B3c GM15): G của model không phụ thuộc cách COGS, nên không hỏi lại; nhãn không ghi cách COGS
    r = _run(metric='G', period='month', year=2023, month=8, model='sarimax_full')
    g = {cm: daily[(daily.model == 'sarimax_full') & (daily.cogs_method == cm) & aug].yhat.sum() for cm in ('direct', 'ratio')}
    assert g['direct'] == pytest.approx(g['ratio'], rel=1e-12)
    assert r.status == 'ok' and r.rows[0]['g_forecast'] == pytest.approx(g['direct'], rel=RTOL)
    assert 'COGS' not in r.rows[0]['candidate_label'] and 'cogs_method_not_needed' in r.derived
    r = _run(metric='G', period='month', year=2023, month=8, model='sarimax_full', cogs_method='ratio')
    exp = daily[(daily.model == 'sarimax_full') & (daily.cogs_method == 'ratio') & aug].yhat.sum()
    assert r.status == 'ok' and not r.rows[0]['is_primary'] and r.rows[0]['g_forecast'] == pytest.approx(exp, rel=RTOL)
    assert 'KHÔNG phải model chính' in r.message and 'không phải model chính' in r.derived['forecast_label']
    r = _run(metric='G', period='month', year=2023, month=8, model='xgboost')
    assert r.status == 'no_data' and 'Không thay bằng model khác' in r.message


# --- ngoài kỳ, ngoài phạm vi: trạng thái trung thực, không số thay thế ---

@pytest.mark.parametrize('args,status', [
    (dict(metric='G', period='year', year=2022), 'unsupported'),          # kỳ đã có số thực tế
    (dict(metric='G', period='month', year=2022, month=12), 'unsupported'),
    (dict(metric='G', period='year', year=2025), 'no_data'),              # sau kỳ dự báo
    (dict(metric='G', period='day', year=2024, month=7, day=2), 'no_data'),
    (dict(metric='R', period='year', year=2023), 'unsupported'),          # dự báo R chưa làm
    (dict(metric='G', period='month', year=2023, month=8, dimension='category'), 'unsupported'),   # theo chiều: không có
    (dict(metric='G', period='day', year=2023, month=2, day=30), 'unsupported'),
    (dict(metric='G', period='month', year=2023), 'needs_clarification'),
    (dict(metric='G', period='horizon', year=2023), 'unsupported'),
])
def test_ngoai_ky_va_ngoai_pham_vi(versioned, args, status):
    r = _run(**args)
    assert r.status == status, r.message
    assert not r.rows


# --- chế độ cũ / bản trước B2b: không khóa chat, tool dự báo báo thẳng ---

def test_che_do_cu_khong_co_du_bao_va_chat_cu_van_chay(monkeypatch):
    monkeypatch.delenv('RETAIL_RELEASE_MODE', raising=False)
    releases.reset()
    for tool, a in [('get_forecast', dict(metric='G', period='month', year=2023, month=8)), ('get_forecast_backtest', {})]:
        r = _run(tool, **a)
        assert r.status == 'no_data' and r.message == tools.NO_FORECAST and not r.rows
    assert _run('get_revenue_summary', metric='R', year=2019).status == 'ok'


def test_ban_truoc_b2b_khong_co_du_bao(versioned):
    st = _state()
    if PRE_B2B not in st['releases']:
        pytest.skip('registry không có bản trước B2b')
    releases.pin(st['releases'][PRE_B2B])          # như khi rollback / pin bản cũ
    try:
        r = _run(metric='G', period='month', year=2023, month=8)
        assert r.status == 'no_data' and r.message == tools.NO_FORECAST
        ok = _run('get_revenue_summary', metric='R', year=2019)
        assert ok.status == 'ok' and ok.evidence.data_version['release_id'] == PRE_B2B
    finally:
        releases.reset()


def test_chat_tron_luot_sau_khi_them_relation_tuy_chon_van_doc_ban_cu(versioned):
    """B4a: chạy qua service, gồm known_groups; rollback bản cũ vẫn trả PS và no_data dự báo."""
    st = _state()
    if PRE_B2B not in st['releases']:
        pytest.skip('registry không có bản trước B2b')
    releases.pin(st['releases'][PRE_B2B])
    try:
        ps = service.run_turn('Vì sao R năm 2019 giảm?', [], 'duckdb', FakeProvider(
            call('get_revenue_drivers', metric='R', year=2019), E04_OK))
        assert ps.status == 'ok' and ps.results['T1'].evidence.data_version['release_id'] == PRE_B2B
        forecast = service.run_turn('Dự báo doanh thu tháng 8/2023?', [], 'duckdb', FakeProvider(
            call('get_forecast', metric='G', period='month', year=2023, month=8),
            final('no_data', 'Bản dữ liệu này chưa có dự báo.')))
        assert forecast.status == 'no_data' and forecast.results['T1'].message == tools.NO_FORECAST
    finally:
        releases.reset()


# --- guard: bảng dự báo được phép đọc nhưng không bắt buộc có quyền ---

class _Cur:
    """Cursor giả cho _release_scope: registry không hiện với SP (chế độ cũ, chưa có pipeline cloud)."""

    def execute(self, sql, params=None):
        self._r = [(0,)]

    def fetchone(self):
        return self._r[0]


def _grants(rels, who='ai'):
    out = [('catalog', 'retail_lab', None, None, who, 'USE_CATALOG', False)]
    for r in rels:
        s, t = r.split('.')
        out += [('schema', 'retail_lab', s, None, who, 'USE_SCHEMA', False),
                ('table', 'retail_lab', s, t, who, 'SELECT', False)]
    return out


def test_guard_che_do_cu_khong_doi_quyen_bang_du_bao(monkeypatch):
    monkeypatch.delenv('RETAIL_RELEASE_MODE', raising=False)
    allowed, required = guarded._release_scope(_Cur(), tools.ALLOWED_RELATIONS, 'retail_lab', tools.OPTIONAL_RELATIONS)
    assert tools.OPTIONAL_RELATIONS <= allowed and not (tools.OPTIONAL_RELATIONS & required)
    # SP chỉ có quyền trên bảng bắt buộc (build thường không có bảng dự báo): guard đạt
    assert not guarded._dbx_violations('ai', 'ai', _grants(tools.ALLOWED_RELATIONS), [], allowed, 'retail_lab', required)
    # đã cấp quyền bảng dự báo (bản có dự báo): vẫn đạt, không bị coi là quyền thừa
    g = _grants(tools.ALLOWED_RELATIONS | tools.OPTIONAL_RELATIONS)
    assert not guarded._dbx_violations('ai', 'ai', g, [], allowed, 'retail_lab', required)
    # bảng ngoài cả hai danh sách vẫn bị chặn
    assert guarded._dbx_violations('ai', 'ai', g + _grants({'marts.fact_order_item'})[1:], [], allowed, 'retail_lab', required)


def test_guard_ban_versioned_khong_doi_quyen_bang_du_bao(monkeypatch):
    rid = 'a' * 24
    rec = {'release_id': rid, 'status': 'ready', 'schema': f'r_{rid}_reporting'}

    class Cur(_Cur):
        def execute(self, sql, params=None):
            self._r = [(json.dumps({'active': rid, 'releases': {rid: rec}}),)]

        def fetchall(self):
            return self._r
    monkeypatch.setenv('RETAIL_RELEASE_MODE', 'versioned')
    releases.reset()
    try:
        allowed, required = guarded._release_scope(Cur(), tools.ALLOWED_RELATIONS, 'retail_lab', tools.OPTIONAL_RELATIONS)
    finally:
        releases.reset()
    assert f'r_{rid}_reporting.rpt_forecast_daily' in allowed
    assert not any('rpt_forecast' in r for r in required)
    assert f'r_{rid}_reporting.rpt_build_info' in required


def test_danh_sach_bang_tuy_chon_trung_dbt_va_macro():
    proj = yaml.safe_load((ROOT / 'retail_dbt/dbt_project.yml').read_text(encoding='utf-8'))
    assert set(proj['vars']['ai_optional_relations']) == set(tools.OPTIONAL_RELATIONS)
    assert not tools.OPTIONAL_RELATIONS & tools.ALLOWED_RELATIONS
    macro = (ROOT / 'retail_dbt/macros/ai_readonly_grants.sql').read_text(encoding='utf-8')
    assert macro.count("var('ai_optional_relations', [])") == 2       # Postgres và Databricks


# --- bộ kiểm câu trả lời với kết quả dự báo (model GIẢ, không phải live eval) ---

Q8 = 'Dự báo doanh thu tháng 8/2023 là bao nhiêu?'
MONTH8 = call('get_forecast', metric='G', period='month', year=2023, month=8)


def _turn(q, *steps):
    return service.run_turn(q, [], 'duckdb', FakeProvider(*steps))


def test_so_du_bao_app_tu_gan_nhan_du_bao_va_sai_so_thang(versioned):
    ok = final(answer='Dự báo G tháng 8/2023 là {c1}. Model chính: {c2}.',
               claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}, {'id': 'c2', 'path': 'T1.derived.primary.label'}])
    t = _turn(Q8, MONTH8, ok)
    assert t.status == 'ok', t.validation_errors
    assert 'dự báo G, 08/2023' in t.answer_md and 'sai số tháng điển hình' in t.answer_md and 'khoảng 80%' not in t.answer_md
    day = final(answer='Dự báo G ngày 1/8/2023 là {c1}.', claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}])
    t = _turn('Dự báo doanh thu ngày 1/8/2023?', call('get_forecast', metric='G', period='day', year=2023, month=8, day=1),
              day)
    assert t.status == 'ok', t.validation_errors
    assert 'khoảng 80%' in t.answer_md                          # theo ngày: app tự in khoảng 80%


def test_so_cua_ung_vien_khac_ghi_khong_phai_model_chinh(versioned):
    ok = final(answer='Theo model được hỏi, dự báo G tháng 8/2023 là {c1}.',
               claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}])
    t = _turn('Dùng SARIMAX toàn chuỗi, COGS qua tỷ lệ, dự báo tháng 8/2023?',
              call('get_forecast', metric='G', period='month', year=2023, month=8, model='sarimax_full',
                   cogs_method='ratio'), ok)
    assert t.status == 'ok', t.validation_errors
    assert 'không phải model chính' in t.answer_md


@pytest.mark.parametrize('answer,claims,why', [
    # gọi số dự báo G là R
    ('Dự báo R tháng 8/2023 là {c1}.', [{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}], 'là số của G'),
    # tên model viết thẳng, không gắn ô
    ('Dự báo tháng 8/2023 là {c1}, theo model SARIMAX.', [{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}], 'model'),
    # số tự viết
    ('Dự báo tháng 8/2023 khoảng 74 triệu.', [], 'số'),
])
def test_cau_du_bao_sai_bi_chan(versioned, answer, claims, why):
    bad = final(answer=answer, claims=claims)
    t = _turn(Q8, MONTH8, bad, bad)
    assert t.status == 'answer_validation_failed', t.answer_md
    assert why in ' | '.join(t.validation_errors), t.validation_errors


def test_model_chinh_xac_nhat_phai_dan_ca_hai_thuoc_va_dung_bang_xep_hang(versioned):
    q = 'Model dự báo nào chính xác nhất?'
    ok = final(answer='Theo điểm ngày kết hợp (thước chọn model), model chính xác nhất là {c1}, điểm {c2}. Theo MAPE G '
                      'tháng thì sai số thấp nhất là {c3}, {c4}. Đây là sai số backtest 2020–2022.',
               claims=[{'id': 'c1', 'path': 'T1.derived.lowest_score.candidates'},
                       {'id': 'c2', 'path': 'T1.derived.lowest_score.score'},
                       {'id': 'c3', 'path': 'T1.derived.lowest_mape_g_thang.candidates'},
                       {'id': 'c4', 'path': 'T1.derived.lowest_mape_g_thang.mape_g_thang'}])
    t = _turn(q, call('get_forecast_backtest'), ok)
    assert t.status == 'ok', t.validation_errors
    assert '%' in t.answer_md and 'VND' in t.answer_md
    # so với mốc sàn: dẫn cột so sánh do tool tính (improvement_vs_floor), không tự so hai điểm
    vs = final(answer='Model chính có điểm thấp hơn mốc seasonal naive 2 năm {c1}.',
               claims=[{'id': 'c1', 'path': 'T1.derived.improvement_vs_floor'}])
    assert _turn(q, call('get_forecast_backtest'), vs).status == 'ok'
    # câu "chính xác nhất" trỏ vào model chính (không phải bảng xếp hạng) thì chặn
    bad = final(answer='Model chính xác nhất là {c1}.', claims=[{'id': 'c1', 'path': 'T1.derived.primary.label'}])
    t = _turn(q, call('get_forecast_backtest'), bad, bad)
    assert t.status == 'answer_validation_failed'


def test_thang_du_bao_cao_thap_nhat(versioned):
    q = 'Trong kỳ dự báo, tháng nào doanh thu thấp nhất?'
    hz = call('get_forecast', metric='G', period='horizon')
    ok = final(answer='Tháng có dự báo G thấp nhất là {c1}, {c2}.',
               claims=[{'id': 'c1', 'path': 'T1.derived.lowest_month.months'},
                       {'id': 'c2', 'path': 'T1.derived.lowest_month.g_forecast'}])
    assert _turn(q, hz, ok).status == 'ok'
    bad = final(answer='Tháng có dự báo G cao nhất là {c1}.', claims=[{'id': 'c1', 'path': 'T1.derived.lowest_month.months'}])
    t = _turn(q, call('get_forecast', metric='G', period='horizon'), bad, bad)
    assert t.status == 'answer_validation_failed'


def test_che_do_cu_cau_tra_loi_bao_khong_co_du_bao(monkeypatch):
    monkeypatch.delenv('RETAIL_RELEASE_MODE', raising=False)
    releases.reset()
    nd = final('no_data', 'Bản dữ liệu đang đọc chưa có dự báo, nên chưa trả lời được.')
    t = _turn(Q8, MONTH8, nd)
    assert t.status == 'no_data' and t.results['T1'].message == tools.NO_FORECAST


def test_ngay_thang_cua_dong_ket_qua_duoc_nhac_lai():
    forms = evidence._date_forms({'year': 2023, 'month': 8, 'forecast_date': dt.date(2023, 8, 1)})
    assert {'tháng 8', '8/2023', '1/8/2023', '01/08/2023'} <= forms


# --- RV01–RV03 (review Codex 2026-10-15, docs/review_codex_ai_gd2_20261015.md): ràng buộc câu hỏi → tool → claim ---

M8 = dict(metric='G_and_COGS', period='month', year=2023, month=8)


@pytest.mark.parametrize('cid,q,tool,args,answer,path', [
    ('R01', 'Dự báo doanh thu tháng 8/2023?', 'get_forecast', dict(metric='G', period='year', year=2023),
     'Dự báo G tháng 8/2023 là {c1}.', 'T1.rows[0].g_forecast'),
    ('R02', 'Doanh thu thực tế tháng 8/2023 là bao nhiêu?', 'get_forecast', M8,
     'Doanh thu thực tế tháng 8/2023 là {c1}.', 'T1.rows[0].g_forecast'),
    ('R03', 'Dự báo giá vốn COGS tháng 8/2023?', 'get_forecast', M8, 'Dự báo COGS tháng 8/2023 là {c1}.',
     'T1.rows[0].g_forecast'),
    ('R04', 'Dự báo G tháng 8/2023?', 'get_forecast', M8, 'Dự báo G tháng 8/2023 là {c1}.', 'T1.rows[0].cogs_forecast'),
    ('R05', 'Dự báo doanh thu năm 2025?', 'get_forecast', dict(metric='G', period='year', year=2023),
     'Dự báo doanh thu năm 2025 là {c1}.', 'T1.rows[0].g_forecast'),
    ('R06', 'Dùng SARIMAX toàn chuỗi, COGS qua tỷ lệ, dự báo tháng 8/2023?', 'get_forecast', M8,
     'Dự báo G tháng 8/2023 là {c1}.', 'T1.rows[0].g_forecast'),
    ('R07', 'Theo MAPE G tháng, model nào chính xác nhất?', 'get_forecast_backtest', {},
     'Theo MAPE G tháng, model chính xác nhất là {c1}.', 'T1.derived.lowest_score.candidates'),
    # biến thể: câu so sánh chung chỉ dẫn một thước; câu nói điểm ngày mà dẫn thước MAPE
    ('R08', 'Model dự báo nào chính xác nhất?', 'get_forecast_backtest', {}, 'Model chính xác nhất là {c1}.',
     'T1.derived.lowest_score.candidates'),
    ('R09', 'Theo điểm ngày, model nào tốt nhất?', 'get_forecast_backtest', {},
     'Theo điểm ngày, model tốt nhất là {c1}.', 'T1.derived.lowest_mape_g_thang.candidates'),
    # biến thể kỳ: hỏi ngày mà dẫn số tháng; hỏi năm 2024 mà dẫn tháng 7/2024
    ('R10', 'Dự báo doanh thu ngày 1/8/2023?', 'get_forecast', M8, 'Dự báo G ngày 1/8/2023 là {c1}.',
     'T1.rows[0].g_forecast'),
    ('R11', 'Dự báo cả năm 2024?', 'get_forecast', dict(metric='G', period='month', year=2024, month=7),
     'Dự báo G năm 2024 là {c1}.', 'T1.rows[0].g_forecast'),
])
def test_rv_cau_sai_bi_chan(versioned, cid, q, tool, args, answer, path):
    bad = final(answer=answer, claims=[{'id': 'c1', 'path': path}])
    t = _turn(q, call(tool, **args), bad, bad)
    assert t.status == 'answer_validation_failed', (cid, t.answer_md)


@pytest.mark.parametrize('q,tool,args,answer,claims', [
    ('Dự báo doanh thu ngày 1/8/2023?', 'get_forecast', dict(metric='G', period='day', year=2023, month=8, day=1),
     'Dự báo G ngày 1/8/2023 là {c1}.', ['T1.rows[0].g_forecast']),
    ('Dự báo doanh thu cả năm 2024?', 'get_forecast', dict(metric='G', period='year', year=2024),
     'Dự báo G năm 2024 là {c1}; {c2}.', ['T1.rows[0].g_forecast', 'T1.derived.missing_part']),
    # G, COGS và tỷ lệ trong cùng câu: mỗi vế gọi đúng chỉ tiêu của số
    ('Tháng 8/2023 dự báo doanh thu và giá vốn thế nào?', 'get_forecast', M8,
     'Dự báo G tháng 8/2023 là {c1}, COGS là {c2}, tỷ lệ COGS/G {c3}.',
     ['T1.rows[0].g_forecast', 'T1.rows[0].cogs_forecast', 'T1.rows[0].cogs_ratio']),
    ('Dùng SARIMAX toàn chuỗi, COGS qua tỷ lệ, dự báo tháng 8/2023?', 'get_forecast',
     dict(M8, model='sarimax_full', cogs_method='ratio'), 'Theo model được hỏi, dự báo G tháng 8/2023 là {c1}.',
     ['T1.rows[0].g_forecast']),
    ('Model dự báo nào chính xác nhất?', 'get_forecast_backtest', {},
     'Theo điểm ngày kết hợp, chính xác nhất là {c1}; theo MAPE G tháng là {c2}.',
     ['T1.derived.lowest_score.candidates', 'T1.derived.lowest_mape_g_thang.candidates']),
    ('Theo MAPE G tháng, model nào chính xác nhất?', 'get_forecast_backtest', {},
     'Theo MAPE G tháng, sai số thấp nhất là {c1}.', ['T1.derived.lowest_mape_g_thang.candidates']),
    # câu không nêu kỳ (tháng thấp nhất cả kỳ dự báo): không có kỳ để ràng buộc
    ('Trong kỳ dự báo, tháng nào doanh thu thấp nhất?', 'get_forecast', dict(metric='G', period='horizon'),
     'Tháng có dự báo G thấp nhất là {c1}.', ['T1.derived.lowest_month.months']),
])
def test_rv_cau_dung_van_qua(versioned, q, tool, args, answer, claims):
    ok = final(answer=answer, claims=[{'id': f'c{i + 1}', 'path': p} for i, p in enumerate(claims)])
    t = _turn(q, call(tool, **args), ok)
    assert t.status == 'ok', t.validation_errors


def test_rv_follow_up_doi_ky(versioned):
    t1 = _turn(Q8, MONTH8, final(answer='Dự báo G tháng 8/2023 là {c1}.',
                                 claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}]))
    assert t1.status == 'ok', t1.validation_errors
    ok = final(answer='Dự báo G tháng 9/2023 là {c1}.', claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}])
    t = service.run_turn('Còn tháng 9/2023?', [t1.context()], 'duckdb', FakeProvider(
        call('get_forecast', metric='G', period='month', year=2023, month=9), ok))
    assert t.status == 'ok', t.validation_errors
    # gọi lại kỳ cũ (tháng 8) cho câu hỏi tháng 9: chặn
    bad = final(answer='Dự báo G tháng 9/2023 là {c1}.', claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}])
    t = service.run_turn('Còn tháng 9/2023?', [t1.context()], 'duckdb', FakeProvider(MONTH8, bad, bad))
    assert t.status == 'answer_validation_failed'


def test_rv_ngoai_ky_tra_no_data_khong_so(versioned):
    nd = final('no_data', 'Năm 2025 nằm ngoài kỳ dự báo, không có số.')
    t = _turn('Dự báo doanh thu năm 2025?', call('get_forecast', metric='G', period='year', year=2025), nd)
    assert t.status == 'no_data' and not t.values


def test_rv03_luat_hoa_model_chinh_khac_diem_thap_nhat(versioned):
    """Fixture luật hòa (bước 3): model chính KHÁC ứng viên có điểm thấp nhất. Câu nói model chính "điểm thấp nhất"
    phải bị chặn; câu nêu riêng hai ý thì đạt."""
    res = _run('get_forecast_backtest')
    other = next(r for r in res.rows if r['role'] == 'candidate' and not r['is_primary'])
    res.derived['primary'] = {**res.derived['primary'], 'candidate': other['candidate'], 'label': other['candidate_label'],
                              'selection_step': 'buoc_3_hoa_chon_don_gian',
                              'selection_reason': tools.SELECTION_REASON['buoc_3_hoa_chon_don_gian']}
    results = {'T1': res}
    q = 'Model dự báo nào chính xác nhất?'
    bad = {'status': 'ok', 'answer': 'Model chính {c1} có điểm ngày thấp nhất, MAPE thấp nhất là {c2}.',
           'claims': [{'id': 'c1', 'path': 'T1.derived.primary.label'},
                      {'id': 'c2', 'path': 'T1.derived.lowest_mape_g_thang.candidates'}]}
    _, errs, _ = service._check_final(bad, results, q)
    assert errs, 'câu gộp "model chính" với "điểm thấp nhất" phải bị chặn'
    good = {'status': 'ok', 'answer': 'Theo điểm ngày, điểm thấp nhất là {c1}; theo MAPE G tháng là {c2}. Model chính là '
                                      '{c3}: {c4}',
            'claims': [{'id': 'c1', 'path': 'T1.derived.lowest_score.candidates'},
                       {'id': 'c2', 'path': 'T1.derived.lowest_mape_g_thang.candidates'},
                       {'id': 'c3', 'path': 'T1.derived.primary.label'},
                       {'id': 'c4', 'path': 'T1.derived.primary.selection_reason'}]}
    _, errs, chk = service._check_final(good, results, q)
    assert not errs, errs
    assert other['candidate_label'] in chk.answer_md


def test_rv_ky_va_model_trong_cau_hoi():
    assert evidence.question_periods('Dự báo doanh thu tháng 8/2023?') == [(2023, 8, None)]
    assert evidence.question_periods('ngày 1/8/2023 thì sao') == [(2023, 8, 1)]
    assert evidence.question_periods('Dự báo cả năm 2024') == [(2024, None, None)]
    assert evidence.question_periods('SARIMAX train từ 2019, tháng 8 năm 2023') == [(2023, 8, None)]
    assert evidence.question_periods('Còn tháng 9?') == [(None, 9, None)]
    assert evidence.question_model('Dùng SARIMAX toàn chuỗi, COGS qua tỷ lệ') == {'family': 'sarimax', 'window': 'full',
                                                                               'cogs': 'ratio'}


# --- biến thể cách viết kỳ (bổ sung RV01, 2026-10-15): đọc đúng kỳ thì vừa không lọt câu sai, vừa không chặn nhầm ---

@pytest.mark.parametrize('q,expect', [
    ('Dự báo T8/2023?', [(2023, 8, None)]),
    ('dự báo 2023-08', [(2023, 8, None)]),
    ('tháng 8 2023', [(2023, 8, None)]),                 # trước: tách thành năm 2023 + tháng 8 → lọt số cả năm
    ('tháng tám năm 2023', [(2023, 8, None)]),
    ('ngày 1 tháng 8 năm 2023', [(2023, 8, 1)]),          # trước: mất ngày → chặn nhầm câu đúng theo ngày
    ('2023-08-01', [(2023, 8, 1)]),
    ('quý 3/2023', [('range', dt.date(2023, 7, 1), dt.date(2023, 9, 30), 'quý 3/2023')]),      # trước: đọc thành tháng 3/2023
    ('nửa đầu năm 2024', [('range', dt.date(2024, 1, 1), dt.date(2024, 6, 30), 'nửa đầu 2024')]),
    ('dự báo 6 tháng cuối 2023', [('range', dt.date(2023, 7, 1), dt.date(2023, 12, 31), 'nửa cuối 2023')]),
    ('12/2023 và 1/2024', [(2023, 12, None), (2024, 1, None)]),
    ('dự báo năm sau', []),                               # kỳ tương đối: không ràng buộc
])
def test_doc_ky_cac_cach_viet(q, expect):
    assert evidence.question_periods(q) == expect


@pytest.mark.parametrize('q,args,path,ok', [
    ('Dự báo doanh thu 2023-08?', dict(metric='G', period='month', year=2023, month=8), 'T1.rows[0].g_forecast', True),
    ('Dự báo tháng tám năm 2023?', dict(metric='G', period='month', year=2023, month=8), 'T1.rows[0].g_forecast', True),
    ('Dự báo ngày 1 tháng 8 năm 2023?', dict(metric='G', period='day', year=2023, month=8, day=1),
     'T1.rows[0].g_forecast', True),
    ('Dự báo tháng 8 2023?', dict(metric='G', period='year', year=2023), 'T1.rows[0].g_forecast', False),
    # quý / nửa năm: tool không có grain này. Câu mẫu không nêu tháng nào nên số tháng 8 bị hiểu thành số của cả quý:
    # chặn (RV07). Câu nêu rõ "riêng tháng 8" thì qua: test_rv07_*
    ('Dự báo quý 3/2023?', dict(metric='G', period='month', year=2023, month=8), 'T1.rows[0].g_forecast', False),
    ('Dự báo quý 3/2023?', dict(metric='G', period='month', year=2023, month=3), 'T1.rows[0].g_forecast', False),
    ('Dự báo 6 tháng đầu 2024?', dict(metric='G', period='year', year=2024), 'T1.rows[0].g_forecast', False),
])
def test_bien_the_ky_tron_luong(versioned, q, args, path, ok):
    rep = final(answer='Theo kỳ được hỏi, dự báo G là {c1}.', claims=[{'id': 'c1', 'path': path}])
    t = _turn(q, call('get_forecast', **args), rep, rep)
    assert (t.status == 'ok') == ok, (q, t.status, t.validation_errors)


# --- RV07–RV09 (review Codex 2026-10-15 §7) ---

def _m(y, m):
    return call('get_forecast', metric='G_and_COGS', period='month', year=y, month=m)


@pytest.mark.parametrize('q,tool,answer,ok', [
    # RV07: khoảng (quý, nửa năm, tháng a–b): số một tháng chỉ được nói là RIÊNG tháng đó
    ('Dự báo tổng doanh thu quý 3/2023?', _m(2023, 8), 'Tổng doanh thu G dự báo quý 3/2023 là {c1}.', False),   # N03
    ('Dự báo doanh thu quý 3/2023?', _m(2023, 8), 'Riêng tháng 8/2023, dự báo G là {c1}.', True),               # C02
    ('Dự báo doanh thu quý 3/2023?', _m(2023, 8), 'Cả quý 3/2023, riêng tháng 8 đóng góp dự báo G {c1}.', False),
    ('Dự báo doanh thu 6 tháng đầu 2024?', _m(2024, 3), 'Dự báo G nửa đầu 2024 là {c1}.', False),
    ('Dự báo doanh thu 6 tháng đầu 2024?', _m(2024, 3), 'Riêng tháng 3/2024, dự báo G là {c1}.', True),
    ('Dự báo doanh thu từ tháng 3 đến tháng 5/2023?', _m(2023, 4), 'Tổng 3 tháng là {c1}.', False),
    ('Dự báo doanh thu từ tháng 3 đến tháng 5/2023?', _m(2023, 4), 'Dự báo G tháng 4/2023 là {c1}.', True),
    ('Dự báo doanh thu từ tháng 3 đến tháng 5/2023?', _m(2023, 6), 'Dự báo G tháng 6/2023 là {c1}.', False),
])
def test_rv07_so_mot_thang_khong_thanh_tong_khoang(versioned, q, tool, answer, ok):
    rep = final(answer=answer, claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}])
    t = _turn(q, tool, rep, rep)
    assert (t.status == 'ok') == ok, (q, answer, t.status, t.validation_errors)


@pytest.mark.parametrize('q,answer,field,ok', [
    ('Dự báo tỷ lệ COGS/G tháng 8/2023?', 'Dự báo tỷ lệ COGS/G tháng 8/2023 là {c1}.', 'cogs_ratio', True),     # C01
    ('Dự báo tỷ lệ COGS/G tháng 8/2023?', 'Dự báo tỷ lệ COGS/G tháng 8/2023 là {c1}.', 'g_forecast', False),    # N01
    ('Dự báo doanh thu G tháng 8/2023?', 'Dự báo doanh thu G tháng 8/2023 là {c1}.', 'cogs_ratio', False),     # N02
    ('Giá vốn trên doanh thu tháng 8/2023 dự báo bao nhiêu?', 'Giá vốn trên doanh thu dự báo tháng 8/2023 là {c1}.',
     'cogs_ratio', True),
    ('Giá vốn trên doanh thu tháng 8/2023 dự báo bao nhiêu?', 'Giá vốn trên doanh thu dự báo tháng 8/2023 là {c1}.',
     'cogs_forecast', False),
])
def test_rv08_ty_le_cogs_g_la_chi_tieu_rieng(versioned, q, answer, field, ok):
    rep = final(answer=answer, claims=[{'id': 'c1', 'path': f'T1.rows[0].{field}'}])
    t = _turn(q, _m(2023, 8), rep, rep)
    assert (t.status == 'ok') == ok, (answer, field, t.status, t.validation_errors)


@pytest.mark.parametrize('q', ['Dự báo doanh thu quý 5/2023?', 'Dự báo doanh thu quý 0/2023?', 'Dự báo doanh thu năm 0000?',
                               'Dự báo doanh thu ngày 31/2/2023?', 'Dự báo doanh thu tháng 13/2023?'])
def test_rv09_ky_khong_hop_le_khong_crash_khong_dung_so_ky_khac(versioned, q):
    rep = final(answer='Dự báo G là {c1}.', claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}])
    t = _turn(q, _m(2023, 8), rep, rep)                              # câu có số dự báo: chặn, không văng lỗi
    assert t.status == 'answer_validation_failed'
    assert any('không hợp lệ' in e for e in t.validation_errors), t.validation_errors
    ask = final('needs_clarification', 'Kỳ trong câu hỏi không có thật, bạn muốn hỏi quý / tháng nào?')
    assert _turn(q, ask).status == 'needs_clarification'               # hỏi lại: đúng
    # câu không phải dự báo (tool số thực tế) cũng không văng lỗi và không dùng số của kỳ khác
    r = final(answer='R năm 2019 là {c1}.', claims=[{'id': 'c1', 'path': 'T1.rows[0].r'}])
    t = _turn(q.replace('Dự báo doanh thu', 'R'), call('get_revenue_summary', metric='R', year=2019), r, r)
    assert t.status == 'answer_validation_failed'


@pytest.mark.parametrize('n', [1, 2, 3, 4])
def test_rv09_quy_hop_le_van_chay(versioned, n):
    m = 3 * n - 1
    rep = final(answer=f'Riêng tháng {m}/2023, dự báo G là {{c1}}.', claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}])
    assert _turn(f'Dự báo doanh thu quý {n}/2023?', _m(2023, m), rep).status == 'ok'


@pytest.mark.parametrize('q', ['quý 99999/2023', 'năm 99999', '1/1/1', 'tháng 00/2023', '2023-00-00', 'quý /2023', '', None])
def test_rv09_doc_ky_khong_bao_gio_nem_loi(q):
    evidence.question_periods(q)


# --- RV10 (review Codex 2026-10-15 §7.4): hỏi lại / từ chối kèm số của kỳ khác khi kỳ nhập sai ---

@pytest.mark.parametrize('status', ['needs_clarification', 'unsupported', 'no_data'])
@pytest.mark.parametrize('q', ['Dự báo doanh thu quý 5/2023?', 'Dự báo doanh thu tháng 13/2023?',
                               'Dự báo doanh thu ngày 31/2/2023?'])
def test_rv10_cau_khac_ok_kem_so_ky_khac_bi_chan(versioned, q, status):
    rep = final(status, 'Bạn muốn hỏi kỳ nào? Trong lúc chờ, dự báo G tháng 8/2023 là {c1}.',
                [{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}])
    t = _turn(q, _m(2023, 8), rep, rep)                               # N05: không hiện số tháng 8 cho kỳ nhập sai
    assert t.status == 'answer_validation_failed', (t.status, t.answer_md)
    assert any('không hợp lệ' in e for e in t.validation_errors), t.validation_errors


def test_rv10_tool_so_thuc_te_cung_bi_chan(versioned):
    r = final('needs_clarification', 'Quý 5 không có; R năm 2019 là {c1}.', [{'id': 'c1', 'path': 'T1.rows[0].r'}])
    t = _turn('R quý 5/2019?', call('get_revenue_summary', metric='R', year=2019), r, r)
    assert t.status == 'answer_validation_failed'


def test_rv10_hoi_lai_hop_le_van_dat(versioned):
    # không dẫn số: hỏi lại kỳ nhập sai vẫn đạt (đã có ở RV09); kỳ hợp lệ thì câu hỏi lại vẫn được dẫn số đã kiểm
    ask = final('needs_clarification', 'Quý 5 không có thật, bạn muốn hỏi quý nào của 2023?')
    assert _turn('Dự báo doanh thu quý 5/2023?', ask).status == 'needs_clarification'
    rep = final('needs_clarification', 'Chưa có số tổng quý. Riêng tháng 8/2023, dự báo G là {c1}; bạn cần tháng nào?',
                [{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}])
    t = _turn('Dự báo doanh thu quý 3/2023?', _m(2023, 8), rep, rep)
    assert t.status == 'needs_clarification' and '{c1}' not in t.answer_md, (t.status, t.validation_errors)


# --- RV12 (review Codex 2026-10-15 §9): câu khác ok dẫn số dự báo kỳ khác phải ghi đúng kỳ của số đó. Từ lượt 5 (PM chọn
# 2026-10-16) app tự dẫn số kỳ khác theo khuôn: các ca từng "phải chặn" ở nhánh khác ok nay phải hiện theo khuôn ---

_COVER = re.compile(r'\S.* nằm ngoài (?:vùng dự báo|dữ liệu thực tế) \(\d\d/\d\d/\d{4} → \d\d/\d\d/\d{4}\), nên chưa có '
                    r'(?:dự báo|số thực tế) cho (?:kỳ này|các kỳ này)\.')
_BULLET = re.compile(r'- [^:\n]+, [^:\n]+: .+ là \*\*[^*\n]+\*\*(?: \(.*\))?')
_GAN_SO = ('số này', 'mức này', 'tổng này', 'dùng', 'áp dụng', 'coi ', 'tương tự', 'thay ')


def _khuon(t, status, asked='2025', ky=('08/2023',)):
    """RV12 lượt 5: câu trả lời khác ok có số kỳ khác do app dẫn theo khuôn. Viết độc lập với evidence.py: chữ số chỉ
    nằm trong câu "ngoài vùng" hoặc dòng số tham khảo; kỳ được hỏi không có trong dòng số hay câu hỏi lại; mỗi dòng số
    ghi kỳ thật; câu còn lại của mô hình không trỏ / dùng / phỏng đoán số."""
    assert t.status == status and t.answer_md, (t.status, t.validation_errors)
    head, sep, rest = t.answer_md.partition('\n\nSố tham khảo, không phải số bạn hỏi:\n\n')
    assert sep, t.answer_md
    body, _, tail = rest.partition('\n\n')
    lines = body.split('\n')
    assert all(_BULLET.fullmatch(x) for x in lines), lines
    for sent in (x.strip() for x in re.findall(r'[^.!?\n]+[.!?]*', head + '\n' + tail) if x.strip()):
        assert _COVER.fullmatch(sent) or not re.search(r'\d', sent), sent
        assert _COVER.fullmatch(sent) or not any(w in sent.lower() for w in _GAN_SO), sent
    assert asked not in body + tail, (asked, body, tail)
    assert all(any(k in x for x in lines) for k in ky), (ky, lines)


@pytest.mark.parametrize('status', ['no_data', 'unsupported', 'needs_clarification'])
@pytest.mark.parametrize('answer', [
    'Dự báo G năm 2025 là {c1}.',                                     # N06: số 08/2023 gán cho năm 2025
    'Chưa có số cả năm. Dự báo G tháng 8 năm 2025 là {c1}.',          # ghi tháng đúng nhưng năm của kỳ được hỏi
    'Chưa có dự báo năm 2025, tham khảo dự báo G là {c1}.',           # không ghi kỳ của số
])
def test_rv12_so_ky_khac_app_dan_theo_khuon(versioned, answer, status):
    rep = final(status, answer, [{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}])
    t = _turn('Dự báo doanh thu năm 2025?', _m(2023, 8), rep, rep)
    _khuon(t, status)


@pytest.mark.parametrize('answer', [
    'Chưa có dự báo năm 2025. Riêng tháng 8/2023, dự báo G là {c1}.',  # đối chứng của Codex
    'Chưa có dự báo năm 2025; riêng tháng 8/2023 dự báo G là {c1}.',
    'Năm 2025 ngoài kỳ dự báo: dự báo G tháng 8 năm 2023 là {c1}.',
])
def test_rv12_so_tham_khao_ghi_dung_ky_van_dat(versioned, answer):
    rep = final('no_data', answer, [{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}])
    t = _turn('Dự báo doanh thu năm 2025?', _m(2023, 8), rep, rep)
    assert t.status == 'no_data' and t.answer_md and '74.151.832' in t.answer_md, (t.status, t.validation_errors)


def test_rv12_so_dung_ky_duoc_hoi_khong_doi(versioned):
    # câu hỏi lại dẫn số ĐÚNG kỳ được hỏi: luật RV12 không áp (đã có ở RV10 với quý; ở đây với tháng)
    rep = final('needs_clarification', 'Dự báo G tháng này là {c1}; bạn cần thêm giá vốn không?',
                [{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}])
    t = _turn('Dự báo doanh thu tháng 8/2023?', _m(2023, 8), rep, rep)
    assert t.status == 'needs_clarification' and t.answer_md, (t.status, t.validation_errors)


# --- live B3c (docs/ai_eval_b3c_du_bao.md §3.2): 7 đề xuất PM duyệt 2026-10-16; mỗi đề xuất có ca đạt và ca bị chặn ---

def test_b3c_gm10_khoang_thang_vat_qua_nam(versioned):
    assert evidence.question_periods('Dự báo G từ tháng 12/2022 đến tháng 2/2023') == [
        ('range', dt.date(2022, 12, 1), dt.date(2023, 2, 28), '12/2022–2/2023')]
    q = 'Dự báo G từ tháng 12/2022 đến tháng 2/2023'
    good = final(answer='Tháng 12/2022 là kỳ thực tế nên không có dự báo. Dự báo G tháng 01/2023 là {c1}, tháng 02/2023 '
                        'là {c2}.', claims=[{'id': 'c1', 'path': 'T2.rows[0].g_forecast'},
                                            {'id': 'c2', 'path': 'T3.rows[0].g_forecast'}])
    steps = [call('get_forecast', metric='G', period='month', year=y, month=m) for y, m in ((2022, 12), (2023, 1), (2023, 2))]
    t = _turn(q, *steps, good)
    assert t.status == 'ok', t.validation_errors                      # live: cả 3 lần bị chặn nhầm
    tong = final(answer='Tổng dự báo G từ tháng 12/2022 đến tháng 2/2023 là {c1}.',
                 claims=[{'id': 'c1', 'path': 'T2.rows[0].g_forecast'}])
    t = _turn(q, *[call('get_forecast', metric='G', period='month', year=y, month=m) for y, m in ((2022, 12), (2023, 1))],
              tong, tong)
    assert t.status == 'answer_validation_failed'                      # một tháng không được gọi là tổng khoảng (RV07)
    # "doanh thu gộp" là tên của G, không phải chữ chỉ tổng (live sau sửa); "gộp hai tháng" thì vẫn là tổng
    for answer, ok in (('Riêng tháng 02/2023, G dự báo là {c1} (doanh thu gộp, gồm cả đơn hủy).', True),
                       ('Gộp hai tháng 01/2023 và 02/2023, dự báo G là {c1}.', False)):
        rep = final(answer=answer, claims=[{'id': 'c1', 'path': 'T3.rows[0].g_forecast'}])
        t = _turn(q, *steps, rep, rep)
        assert (t.status == 'ok') == ok, (answer, t.validation_errors)


@pytest.mark.parametrize('answer,ok', [
    ('Số DỰ BÁO G là {c1} cho tháng 01/2023 và {c2} cho tháng 02/2023.', True),
    ('Số DỰ BÁO G là {c1} cho tháng 02/2023 và {c2} cho tháng 01/2023.', False),
])
def test_b3c_gm10_ky_sau_cho_tung_so(versioned, answer, ok):
    # Live GM10: kỳ sau {c2} thuộc chính {c2}, không thuộc số {c1} ở trước chữ "và".
    rep = final(answer=answer, claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'},
                                       {'id': 'c2', 'path': 'T2.rows[0].g_forecast'}])
    t = _turn('Dự báo G từ tháng 12/2022 đến tháng 2/2023', _m(2023, 1), _m(2023, 2), rep, rep)
    assert (t.status == 'ok') == ok, (answer, t.status, t.validation_errors)


def test_b3c_gm09_cung_thang_nam_va_so_sanh_tiep_noi(versioned):
    assert evidence.question_periods('Vậy so với cùng tháng năm 2022 thực tế thì thế nào?') == [
        ('same_month', 2022, None, 'cùng tháng năm 2022')]
    assert evidence.question_periods('Dự báo doanh thu tháng năm 2023?') == [(2023, 5, None)]    # "tháng năm" vẫn là tháng 5
    t1 = _turn('Doanh thu gộp dự kiến của tháng 3 năm 2024 là bao nhiêu?',
               call('get_forecast', metric='G', period='month', year=2024, month=3),
               final(answer='Dự báo G tháng 3/2024 là {c1}.', claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}]))
    assert t1.status == 'ok', t1.validation_errors
    q = 'Vậy so với cùng tháng năm 2022 thực tế thì thế nào?'
    tools_ = [call('get_forecast', metric='G', period='month', year=2024, month=3),
              call('get_revenue_monthly', metric='G', year=2022, month=3)]
    hai_phan = final(answer='Dự báo G tháng 3/2024 là {c1}; G thực tế tháng 3/2022 là {c2}.',
                     claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}, {'id': 'c2', 'path': 'T2.rows[0].g'}])
    t = service.run_turn(q, [t1.context()], 'duckdb', FakeProvider(*tools_, hai_phan))
    assert t.status == 'ok', t.validation_errors
    gan_sai = final(answer='G tháng 3/2022 là {c1}.', claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}])
    t = service.run_turn(q, [t1.context()], 'duckdb', FakeProvider(*tools_, gan_sai, gan_sai))
    assert t.status == 'answer_validation_failed'                      # số dự báo 3/2024 gán cho 3/2022
    t = service.run_turn(q, [], 'duckdb', FakeProvider(*tools_, hai_phan, hai_phan))
    assert t.status == 'answer_validation_failed'                      # không có lượt trước: không phải câu tiếp nối
    assert 'CÙNG định nghĩa' in service.system_prompt(dt.date(2026, 10, 16))


@pytest.mark.parametrize('q,answer,claims,ok', [
    # (a) câu so mốc sàn dẫn điểm model chính + MAPE thấp nhất: đã nêu cả hai thước (live GM12 bị chặn nhầm)
    ('Model đang dùng có hơn hẳn cách lấy lại số cùng kỳ hai năm trước không?',
     'Điểm ngày của model chính là {c1}, cải thiện {c2} so với mốc sàn. Theo MAPE G tháng, thấp nhất là {c3}.',
     ['T1.derived.primary.score', 'T1.derived.improvement_vs_floor', 'T1.derived.lowest_mape_g_thang.candidates'], True),
    ('Model nào chính xác nhất?', 'Chính xác nhất là {c1}.', ['T1.derived.lowest_score.candidates'], False),
    # (b) so hai số cùng thước, app kiểm chiều (live GM14)
    ('Vì sao không chọn bản gộp dù sai số tháng thấp hơn?',
     'Bản gộp có MAPE G tháng {c1}, thấp hơn {c2} của model chính; điểm ngày của bản gộp {c3} cao hơn {c4}.',
     ['T1.rows[blend_full/direct].mape_g_thang', 'T1.derived.primary.mape_g_thang', 'T1.rows[blend_full/direct].score',
      'T1.derived.primary.score'], True),
    ('Vì sao không chọn bản gộp dù sai số tháng thấp hơn?', 'Bản gộp có MAPE G tháng {c1}, cao hơn {c2} của model chính.',
     ['T1.rows[blend_full/direct].mape_g_thang', 'T1.derived.primary.mape_g_thang'], False),
    ('Vì sao không chọn bản gộp dù sai số tháng thấp hơn?', 'Bản gộp có MAPE G tháng {c1}, thấp hơn điểm ngày {c2}.',
     ['T1.rows[blend_full/direct].mape_g_thang', 'T1.derived.primary.score'], False),       # khác thước: không so được
    # câu mô tả luật chọn không có chỗ đặt: không phải câu xếp hạng (live sau sửa GM14); câu gọi tên model thì vẫn kiểm
    ('Vì sao không chọn bản gộp dù sai số tháng thấp hơn?',
     'Theo luật chọn: trước hết phải thắng mốc sàn ở cả 3 fold, sau đó lấy điểm ngày thấp nhất. Model chính được chọn '
     'vì {c1}, điểm ngày {c2}.', ['T1.derived.primary.selection_reason', 'T1.derived.primary.score'], True),
    ('Vì sao không chọn bản gộp dù sai số tháng thấp hơn?',
     'Theo luật chọn, LightGBM có điểm ngày thấp nhất. Model chính được chọn vì {c1}.',
     ['T1.derived.primary.selection_reason'], False),
    # (c) "dẫn đầu" theo sai số = thấp nhất (live GM13)
    ('Theo MAPE G tháng, model nào tốt nhất?', 'Theo MAPE G tháng, nhóm dẫn đầu là {c1}.',
     ['T1.derived.lowest_mape_g_thang.candidates'], True),
    ('Theo MAPE G tháng, model nào tốt nhất?', 'Theo MAPE G tháng, sai số cao nhất là {c1}.',
     ['T1.derived.lowest_mape_g_thang.candidates'], False),
])
def test_b3c_gm12_14_cau_do_chinh_xac(versioned, q, answer, claims, ok):
    rep = final(answer=answer, claims=[{'id': f'c{i + 1}', 'path': p} for i, p in enumerate(claims)])
    t = _turn(q, call('get_forecast_backtest'), rep, rep)
    assert (t.status == 'ok') == ok, (q, answer, t.status, t.validation_errors)


def test_b3c_gm13_o_ngay_khong_in_rac_va_khong_la_so_ngay(versioned):
    rep = final(answer='Model chính train tới {c1}, gồm {c2} fold.',
                claims=[{'id': 'c1', 'path': 'T1.derived.primary.trained_through'}, {'id': 'c2', 'path': 'T1.derived.n_folds'}])
    t = _turn('Model chính train tới ngày nào?', call('get_forecast_backtest'), rep)
    assert t.status == 'ok' and '31/12/2022' in t.answer_md and '.,2f' not in t.answer_md, (t.answer_md, t.validation_errors)
    bad = final(answer='Mỗi fold dự báo {c1} ngày.', claims=[{'id': 'c1', 'path': 'T1.derived.primary.trained_through'}])
    t = _turn('Sai số backtest đo trên bao nhiêu ngày?', call('get_forecast_backtest'), bad, bad)
    assert t.status == 'answer_validation_failed' and any('không phải số ngày' in e for e in t.validation_errors)


def test_b3c_gm15_gm11_ten_ho_model(versioned):
    r = _run(metric='G', period='month', year=2023, month=12, model='sarimax')
    assert r.status == 'needs_clarification' and r.missing == ['model'], r.message
    assert 'sarimax_full' in r.message and 'sarimax_2019' in r.message and 'không thay bằng model chính' in r.message
    r = _run(metric='G', period='month', year=2023, month=12, model='LightGBM')
    assert r.status == 'needs_clarification' and 'lgbm_full' in r.message and 'lgbm_2019' in r.message
    r = _run(metric='G', period='month', year=2023, month=12, model='arima')           # họ chỉ có một biến thể
    assert r.status == 'ok' and r.rows[0]['candidate'].startswith('arima_2019/') and not r.rows[0]['is_primary']
    r = _run('get_forecast_backtest', model='lightgbm')                                # so họ: cả bảng + biến thể
    assert r.status == 'ok' and r.derived['family']['candidates']
    assert all(c.startswith('LightGBM') for c in r.derived['family']['candidates'])
    assert 'KHÔNG truyền model' in service.system_prompt(dt.date(2026, 10, 16))


@pytest.mark.parametrize('status,answer,ok', [
    ('ok', 'Dự báo tháng 5/2023 là {c1}.', False),                                     # live GM07 lần 1
    ('unsupported', 'Chưa có dự báo số đơn hàng. Riêng dự báo G tháng 5/2023 là {c1}, không phải số đơn.', True),
])
def test_b3c_gm07_du_bao_chi_tieu_chua_co(versioned, status, answer, ok):
    rep = final(status, answer, [{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}])
    t = _turn('Dự báo số đơn hàng tháng 5/2023 là bao nhiêu?',
              call('get_forecast', metric='G', period='month', year=2023, month=5), rep, rep)
    assert (t.status == status) == ok, (t.status, t.validation_errors)
    assert not evidence._NOFC_Q.search('Dự báo doanh thu tháng 5/2023 là bao nhiêu?')
    assert evidence._NOFC_Q.search('Dự báo R năm 2023?') and not evidence._NOFC_Q.search('Dự báo r năm 2023?')


def test_b3c_gm05_phan_thieu_la_cum_danh_tu(versioned):
    assert _run(metric='G', period='year', year=2024).derived['missing_part'] == '2024-07-02 → 2024-12-31 (183 ngày)'


# --- RV12 lượt 2 (2026-10-16): biến thể của N06 mà luật lượt 1 bỏ lọt (probe trước sửa: 10/15 ca sai vẫn hiện) ---

Q25 = 'Dự báo doanh thu năm 2025?'
_HZ = dict(metric='G', period='horizon')
_ROW, _TOT, _HI = 'T1.rows[0].g_forecast', 'T1.derived.horizon_total.g_forecast', 'T1.derived.highest_month.g_forecast'
_A22 = ('get_revenue_summary', dict(metric='G', year=2022), 'T1.rows[0].g')
_M8 = ('get_forecast', dict(metric='G', period='month', year=2023, month=8), _ROW)
_KY = {_ROW: 'Tháng 08/2023', _TOT: 'Cả vùng dự báo 01/01/2023 → 01/07/2024', _HI: 'tháng cao nhất vùng dự báo',
       _A22[2]: 'Năm 2022'}            # kỳ thật app ghi ở dòng số tham khảo (lượt 5)


@pytest.mark.parametrize('q,src,status,answer', [
    (Q25, _M8, 'no_data', 'Chưa có cả năm. Dự báo G tháng 8 là {c1}.'),                     # tháng không năm: đọc thành 8/2025
    ('Dự báo doanh thu tháng 8/2025?', _M8, 'no_data', 'Dự báo G tháng 8 là {c1}.'),
    (Q25, _M8, 'no_data', 'Theo tháng 8/2023, dự báo G là {c1}, áp dụng cho năm 2025.'),     # vế sau gán lại
    (Q25, _M8, 'no_data', 'Dự báo G là {c1} (tháng 8/2023), tức năm 2025.'),
    (Q25, _M8, 'no_data', 'Dự báo G tháng 8/2023 là {c1}. Có thể coi đây là dự báo năm 2025.'),   # câu sau gán lại
    # câu miễn trừ "không phải số thực tế" (tool dự báo bảo nhắc lại) không phải chữ phủ định kỳ được hỏi (advisor 2026-10-16)
    (Q25, _M8, 'no_data', 'Dự báo G tháng 8/2023 là {c1}, áp dụng cho năm 2025 (không phải số thực tế).'),
    (Q25, _M8, 'no_data', 'Dự báo G tháng 8/2023 là {c1}. Đây là dự báo năm 2025 chứ không phải số thực tế.'),
    (Q25, ('get_forecast', _HZ, _TOT), 'no_data', 'Dự báo G năm 2025 là {c1}.'),              # tổng cả vùng (derived)
    (Q25, ('get_forecast', _HZ, _HI), 'no_data', 'Tháng cao nhất năm 2025 dự báo G là {c1}.'),
    (Q25, ('get_forecast', _HZ, _TOT), 'needs_clarification', 'Bạn muốn xem tháng nào? Tổng dự báo G là {c1}.'),
    (Q25, _A22, 'no_data', 'Dự báo G năm 2025 khoảng {c1}.'),                                 # số thực tế 2022
    (Q25, _M8, 'ok', 'Dự báo G tháng 8 là {c1}.'),                                            # nhánh ok: đối chiếu
    (Q25, ('get_forecast', _HZ, _TOT), 'ok', 'Dự báo G năm 2025 là {c1}.'),
    (Q25, _A22, 'ok', 'Dự báo G năm 2025 khoảng {c1}.'),                                      # trước sửa: hiện, nhãn (G, 2022)
    ('R năm 2019 là bao nhiêu?', ('get_revenue_summary', dict(metric='R', year=2018), 'T1.rows[0].r'), 'ok',
     'R năm 2019 là {c1}.'),                                                                   # cùng lớp lỗi, tool PS
])
def test_rv12b_so_ky_khac_ok_chan_khac_ok_theo_khuon(versioned, q, src, status, answer):
    tool, args, path = src
    rep = final(status, answer, [{'id': 'c1', 'path': path}])
    t = _turn(q, call(tool, **args), rep, rep)
    if status == 'ok':                        # nhánh ok giữ luật chặn của lượt 2
        assert t.status == 'answer_validation_failed', (t.status, t.answer_md)
    else:                                     # khác ok: câu mô hình không hiện, app dẫn số theo khuôn (lượt 5)
        _khuon(t, status, asked='8/2025' if '8/2025' in q else '2025', ky=(_KY[path],))


@pytest.mark.parametrize('q,src,status,answer', [
    (Q25, _M8, 'no_data', 'Chưa có dự báo năm 2025. Riêng tháng 8/2023, dự báo G là {c1}.'),   # đối chứng Codex
    (Q25, _M8, 'no_data', 'Chưa có dự báo năm 2025, riêng tháng 8/2023 dự báo G là {c1}.'),
    (Q25, _M8, 'no_data', 'Riêng tháng 8/2023 dự báo G là {c1}, còn năm 2025 chưa có dự báo.'),
    (Q25, _M8, 'needs_clarification', 'Năm 2025 ngoài kỳ dự báo. Bạn có muốn xem năm 2023 không? Tháng 8/2023 dự báo '
     'G là {c1}.'),
    (Q25, ('get_forecast', _HZ, _TOT), 'no_data',
     'Chưa có dự báo năm 2025. Cả vùng dự báo 01/01/2023 → 01/07/2024, tổng dự báo G là {c1}.'),
    (Q25, ('get_forecast', dict(metric='G', period='year', year=2023), _ROW), 'no_data',
     'Chưa có dự báo năm 2025. Tham khảo: năm 2023 dự báo G là {c1}.'),
    (Q25, _A22, 'no_data', 'Chưa có dự báo năm 2025. Số thực tế gần nhất: G năm 2022 là {c1}.'),
    (Q25, _A22, 'ok', 'G năm 2022 là {c1}.'),                                                  # nhánh ok: kỳ ghi đúng
    (Q25, _M8, 'no_data', 'Chưa có dự báo năm 2025 (vùng dự báo chỉ tới 01/07/2024). Riêng tháng 8/2023, dự báo G là {c1} '
     '(dự báo, không phải số thực tế).'),
    (Q25, _M8, 'no_data', 'Riêng tháng 8/2023 dự báo G là {c1}, đây không phải số năm 2025.'),
])
def test_rv12b_so_tham_khao_ghi_dung_ky_van_hien(versioned, q, src, status, answer):
    tool, args, path = src
    rep = final(status, answer, [{'id': 'c1', 'path': path}])
    t = _turn(q, call(tool, **args), rep, rep)
    assert t.status == status and t.answer_md, (t.status, t.validation_errors)


@pytest.mark.parametrize('answer,claims', [
    ('So với năm 2018, R năm 2019 giảm {c1}.', ['delta_r']),                 # số thay đổi thuộc cả hai năm
    ('So với năm 2018, R giảm {c1}.', ['delta_r']),
    ('R năm 2018 là {c1}.', ['r_prior_year']),                               # số năm trước của dòng 2019
    ('Năm 2019 R là {c1}, năm trước là {c2}.', ['r', 'r_prior_year']),       # vế "năm trước" không mượn kỳ qua vế có số khác
])
def test_rv12b_so_thay_doi_va_nam_truoc_van_dat(versioned, answer, claims):
    rep = final('ok', answer, [{'id': f'c{i + 1}', 'path': f'T1.rows[0].{f}'} for i, f in enumerate(claims)])
    t = _turn('R năm 2019 so với năm trước?', call('get_revenue_summary', metric='R', year=2019, compare_prior_year=True),
              rep, rep)
    assert t.status == 'ok', (answer, t.validation_errors)


# câu live ĐÃ ĐÚNG (log warehouse/ai_eval/live_20261005*), luật kỳ RV12 lượt 2 bản đầu chặn nhầm khi phát lại 1.246 câu:
# hai số trong một vế ("năm 2019 là {c1} và năm 2020 là {c2}"), kỳ tương đối, ô năm, số thay đổi "so năm trước giảm {cX}"
_LIVE_DUNG = [
    ('Tháng 8 năm lẻ có luôn thấp hơn năm chẵn không?', 'unsupported',
     [('get_revenue_summary', dict(metric='R', year=2019)), ('get_revenue_summary', dict(metric='R', year=2020))],
     'Không trả lời được: dữ liệu hiện có là doanh thu theo NĂM. Nếu muốn, tôi có thể so cả năm: doanh thu thực nhận R năm '
     '2019 là {c1} và năm 2020 là {c2}.', {'c1': 'T1.rows[0].r', 'c2': 'T2.rows[0].r'}),
    ('Năm ngoái R bao nhiêu?', 'needs_clarification',
     [('get_revenue_summary', dict(metric='R', year=2022, compare_prior_year=True))],
     'Bạn muốn xem doanh thu thực nhận (R) của năm nào? Hiện dữ liệu có tới năm 2022; ví dụ năm 2022 thì R là {c1} và năm '
     'trước đó là {c2}.', {'c1': 'T1.rows[0].r', 'c2': 'T1.rows[0].r_prior_year'}),
    ('Năm ngoái R bao nhiêu?', 'needs_clarification', [('get_revenue_summary', dict(metric='R', year=2022))],
     'Hôm nay là năm {c1} nên "năm ngoái" sẽ là năm {c1}, nhưng dữ liệu chỉ có tới năm {c1}. Bạn muốn xem năm nào? (Ví dụ '
     'năm gần nhất có dữ liệu là {c1}: R đạt {c2}.)', {'c1': 'T1.rows[0].year', 'c2': 'T1.rows[0].r'}),
    ('Doanh thu thực nhận tháng 12/2020 bao nhiêu?', 'ok', [('get_revenue_monthly', dict(metric='R', year=2020, month=12))],
     'Doanh thu thực nhận (R) tháng 12/2020 là {c1}. So với cùng tháng năm trước, R tháng 12/2020 giảm {c2} (R cùng tháng '
     'năm trước là {c3}). Chỉ số tháng của tháng này là {c4} (R tháng chia cho R trung bình tháng của năm 2020).',
     {'c1': 'T1.rows[0].r', 'c2': 'T1.rows[0].yoy_rate', 'c3': 'T1.rows[0].r_same_month_prior_year',
      'c4': 'T1.rows[0].month_index'}),
    ('Tháng 5/2017 R tăng hay giảm so với cùng kỳ năm trước?', 'ok',
     [('get_revenue_monthly', dict(metric='R', year=2017, month=5))],
     'R tháng 5/2017 giảm {c1} so với cùng kỳ năm trước; R tháng này là {c2} và R tháng 5/2016 là {c3}.',
     {'c1': 'T1.rows[0].yoy_rate', 'c2': 'T1.rows[0].r', 'c3': 'T1.rows[0].r_same_month_prior_year'}),
    ('Doanh thu kênh referral quý 3/2020?', 'unsupported',
     [('get_segment_contribution', dict(metric='R', dimension='acquisition_channel', year=2020, group='referral'))],
     'Chưa hỗ trợ số theo quý. Mình chỉ có thể nêu số cả năm 2020 của kênh referral: R là {c1}, so năm trước giảm {c2} '
     '— nhưng đây là số cả năm, không phải số quý 3/2020 bạn hỏi.',
     {'c1': 'T1.rows[referral].r', 'c2': 'T1.rows[referral].delta_r'}),
    ('Vùng West tháng 12 năm 2021 thu được bao nhiêu?', 'unsupported',
     [('get_revenue_monthly', dict(metric='R', year=2021, month=12))],
     'Số theo tháng chỉ có cho toàn công ty. Mình chỉ có thể cho bạn R tháng 12/2021 của toàn công ty là {c1}, so cùng '
     'tháng năm trước đổi {c2} (R cùng tháng năm trước là {c3}); đây không phải số của riêng vùng West.',
     {'c1': 'T1.rows[0].r', 'c2': 'T1.rows[0].yoy_rate', 'c3': 'T1.rows[0].r_same_month_prior_year'}),
    (Q25, 'no_data', [_M8[:2]],
     'Chưa có dự báo năm 2025. Riêng năm 2023, tháng 8 dự báo G là {c1}.', {'c1': _ROW}),   # tháng lấy năm ghi trước
    # RV12 lượt 3, bản đầu chặn nhầm (phát lại E08): kỳ trong ngoặc là kỳ mà chữ "chưa hỗ trợ" phủ định
    ('R ngành Streetwear ở vùng East từ 15/3 đến 10/6/2019?', 'unsupported',
     [('get_segment_contribution', dict(metric='R', dimension='region', year=2019, group='East'))],
     'Không trả lời được theo đúng yêu cầu: dữ liệu hiện có chỉ theo năm, chưa hỗ trợ truy vấn theo khoảng ngày tùy ý '
     '(15/3–10/6/2019). Nếu bạn muốn, tôi có thể cho số theo cả năm 2019 cho vùng East: doanh thu thực nhận R là {c1}, so '
     'năm trước giảm {c2}.', {'c1': 'T1.rows[East].r', 'c2': 'T1.rows[East].delta_r'}),
]


@pytest.mark.parametrize('q,status,steps,answer,claims', _LIVE_DUNG)
def test_rv12b_cau_live_dung_khong_bi_chan_nham(versioned, q, status, steps, answer, claims):
    rep = final(status, answer, [{'id': c, 'path': p} for c, p in claims.items()])
    t = _turn(q, *[call(n, **a) for n, a in steps], rep, rep)
    assert t.status == status and t.answer_md, (t.status, t.validation_errors)


# --- RV12 lượt 3 (Codex §9.5, 2026-10-16): một chữ "chưa" từng miễn cả vế; nay mỗi lần nhắc kỳ được hỏi cần phủ định riêng ---

_REF = 'Riêng tháng 8/2023, dự báo G là {c1}. '


@pytest.mark.parametrize('q,src,answer', [
    # hai ca của Codex (scripts/review/review_rv12b_codex_20261016.py), giữ nguyên chữ
    (Q25, _M8, 'Chưa có dự báo năm 2025. Riêng tháng 8/2023, dự báo G là {c1}. Năm 2025 chưa có dự báo nhưng số này là '
     'dự báo năm 2025.'),
    (Q25, _M8, _REF + 'Năm 2025 chưa có dự báo nhưng có thể dùng số này làm dự báo năm 2025.'),
    (Q25, _M8, _REF + 'Năm 2025 nằm ngoài vùng dự báo và số này áp dụng cho năm 2025.'),
    (Q25, _M8, _REF + 'Không có dự báo năm 2025 số này là dự báo năm 2025.'),                   # không chữ nối
    (Q25, _M8, _REF + 'Số này là dự báo năm 2025 dù năm 2025 chưa có dự báo.'),                # gán trước, phủ định sau
    (Q25, _M8, _REF + 'Dùng số này cho năm 2025 vì năm 2025 chưa có dự báo.'),
    (Q25, _M8, _REF + 'Năm 2025 chưa có dự báo nhưng có thể dùng số này.'),                    # gán ngầm, không nhắc lại kỳ
    (Q25, _M8, _REF + 'Năm 2025 nằm ngoài vùng dự báo nên áp dụng mức này.'),
    (Q25, _M8, _REF + 'Năm 2025 chưa có dự báo. Có thể dùng số này thay.'),
    (Q25, ('get_forecast', _HZ, _TOT), 'Cả vùng dự báo 01/01/2023 → 01/07/2024, tổng dự báo G là {c1}. Năm 2025 chưa có '
     'dự báo nhưng tổng này là dự báo năm 2025.'),
    (Q25, _A22, 'Số thực tế gần nhất: G năm 2022 là {c1}. Năm 2025 chưa có dự báo nhưng số này là dự báo năm 2025.'),
])
def test_rv12c_cau_gan_lai_khong_hien(versioned, q, src, answer):
    tool, args, path = src
    rep = final('no_data', answer, [{'id': 'c1', 'path': path}])
    t = _turn(q, call(tool, **args), rep, rep)
    _khuon(t, 'no_data', ky=(_KY[path],))


@pytest.mark.parametrize('q,answer', [
    (Q25, 'Chưa có dự báo năm 2025 vì năm 2025 nằm ngoài vùng dự báo. ' + _REF),            # hai lần nhắc, hai phủ định
    (Q25, 'Năm 2025 nằm ngoài vùng dự báo nên chưa có số cho năm 2025. ' + _REF),
    ('Dự báo doanh thu năm 2025 và 2026?', 'Chưa có dự báo năm 2025 và 2026. ' + _REF),      # liệt kê: một phủ định
    ('Dự báo doanh thu năm 2025 và 2026?', 'Năm 2025 và năm 2026 đều nằm ngoài vùng dự báo. ' + _REF),
    ('Dự báo doanh thu tháng 1 và tháng 2/2025?', 'Không có dự báo cho tháng 1 và tháng 2/2025. ' + _REF),
    (Q25, _REF + 'Không nên dùng số này làm dự báo năm 2025.'),                              # "không nên" không phải chữ nối
    (Q25, 'Năm 2025 chưa có dự báo nên không thể dùng số này cho năm 2025. ' + _REF),
    (Q25, 'Năm 2025 chưa có dự báo. ' + _REF + 'Có thể dùng số này để so sánh với thực tế tháng 8/2022.'),
    (Q25, 'Mình chưa có dự báo năm 2025 và cũng không thể suy ra năm 2025 từ số này. ' + _REF),
    (Q25, 'Riêng tháng 8/2023, dự báo G là {c1}, số này chỉ để tham khảo vì năm 2025 chưa có dự báo.'),
])
def test_rv12c_moi_lan_nhac_co_phu_dinh_van_hien(versioned, q, answer):
    rep = final('no_data', answer, [{'id': 'c1', 'path': _ROW}])
    t = _turn(q, call(*_M8[:1], **_M8[1]), rep, rep)
    _khuon(t, 'no_data')


# RV12 lượt 4 (Codex §9.8): câu hỏi có trỏ số, phủ định sai phạm vi và mốc tham khảo đúng nghĩa. cu: kỳ vọng của
# lượt 4 (hiện / chặn). Lượt 5: mọi ca hiện theo khuôn, câu gán số kỳ khác của mô hình không còn trong câu trả lời.
@pytest.mark.parametrize('status,answer,cu', [
    ('no_data', _REF + 'Năm 2025 chưa có dự báo nhưng số này là dự báo năm 2025?', False),
    ('needs_clarification', _REF + 'Năm 2025 chưa có dự báo. Bạn có muốn dùng số này làm dự báo năm 2025?', False),
    ('no_data', _REF + 'Số này là dự báo năm 2025 chưa điều chỉnh.', False),
    ('no_data', _REF + 'Không có lý do gì để không coi đây là dự báo năm 2025.', False),
    ('no_data', _REF + 'Chưa có lý do gì để không coi đây là dự báo năm 2025.', False),
    ('no_data', _REF + 'Số này là dự báo năm 2025 chưa thể điều chỉnh.', False),
    ('no_data', 'Năm 2025 chưa có dự báo. ' + _REF
     + 'Không có lý do gì để không dùng số này.', False),
    ('no_data', 'Năm 2025 chưa có dự báo. ' + _REF + 'Có thể dùng số này làm mốc tham khảo.', True),
    ('no_data', 'Năm 2025 chưa có dự báo. ' + _REF
     + 'Có thể dùng số này làm mốc tham khảo để so sánh, không phải dự báo năm 2025.', True),
    ('needs_clarification', 'Năm 2025 chưa có dự báo. ' + _REF + 'Bạn muốn xem kỳ nào khác?', True),
])
def test_rv12d_so_tham_khao_khong_thanh_du_bao_ky_hoi(versioned, status, answer, cu):
    rep = final(status, answer, [{'id': 'c1', 'path': _ROW}])
    t = _turn(Q25, call(*_M8[:1], **_M8[1]), rep, rep)
    _khuon(t, status)


def test_rv12d_live_e08_khoang_ngay_chua_gop_duoc_khong_bi_chan(versioned):
    # Câu E08 đã từng hiện đúng: "chưa gộp được" phủ định khả năng trả số khoảng ngày người dùng hỏi.
    answer = ('Chưa hỗ trợ được: dữ liệu hiện chỉ có R theo từng năm hoặc từng tháng cho toàn công ty, chưa gộp được '
              'khoảng ngày tùy ý (15/3–10/6/2019), và cũng chưa có số theo tháng cho một nhóm như ngành hàng hay khu '
              'vực. Mình chỉ có thể nêu số cả năm 2019: R của ngành Streetwear là {c1} và R của vùng East là {c2} — '
              'đây là số cả năm, không phải số của khoảng ngày bạn hỏi.')
    rep = final('unsupported', answer,
                [{'id': 'c1', 'path': 'T1.rows[Streetwear].r'}, {'id': 'c2', 'path': 'T2.rows[East].r'}])
    t = _turn('R ngành Streetwear ở vùng East từ 15/3 đến 10/6/2019?',
              call('get_segment_contribution', metric='R', dimension='category', year=2019, group='Streetwear'),
              call('get_segment_contribution', metric='R', dimension='region', year=2019, group='East'), rep, rep)
    assert t.status == 'unsupported' and t.answer_md, (t.status, t.validation_errors)
    # lượt 5: khoảng ngày nằm trong dữ liệu (lý do là grain / nhóm) nên không có câu "ngoài vùng"; mỗi số ghi nhóm và năm
    _khuon(t, 'unsupported', asked='15/3', ky=('Năm 2019, ngành Streetwear: R là', 'Năm 2019, vùng East: R là'))
    assert 'nằm ngoài' not in t.answer_md


# --- RV12 lượt 5 (PM chọn hướng (a) 2026-10-16): app tự dẫn số kỳ khác theo khuôn ở câu trả lời khác ok ---

def test_rv12e_khuon_dung_tung_chu(versioned):
    rep = final('no_data', 'Chưa có dự báo năm 2025. ' + _REF + 'Năm 2025 chưa có dự báo nhưng số này là dự báo năm 2025.',
                [{'id': 'c1', 'path': _ROW}])
    t = _turn(Q25, call(*_M8[:1], **_M8[1]), rep, rep)
    assert t.status == 'no_data' and t.answer_md == (
        'Năm 2025 nằm ngoài vùng dự báo (01/01/2023 → 01/07/2024), nên chưa có dự báo cho kỳ này.\n\n'
        'Số tham khảo, không phải số bạn hỏi:\n\n'
        '- Tháng 08/2023, toàn công ty: dự báo G là **74.151.832 VND** (sai số tháng điển hình 11,4% (backtest 2020–2022))'
    ), t.answer_md


@pytest.mark.parametrize('answer', ['Dữ liệu năm 2023 chưa được cập nhật. ', 'Dữ liệu không bao gồm năm 2023. ',
                                    'Năm 2023 không thuộc dữ liệu hiện có. '])
def test_rv12e_ps_tu_choi_viet_tu_nhien_van_hien(versioned, answer):
    # review §9.9: ba câu từ chối đúng này từng bị chặn nhầm vì cụm phủ định ngoài danh sách
    rep = final('no_data', answer + 'Số gần nhất: R năm 2022 là {c1}.', [{'id': 'c1', 'path': 'T1.rows[0].r'}])
    t = _turn('R năm 2023 là bao nhiêu?', call('get_revenue_summary', metric='R', year=2022), rep, rep)
    _khuon(t, 'no_data', asked='2023', ky=('Năm 2022, toàn công ty: R là',))
    assert t.answer_md.startswith('Năm 2023 nằm ngoài dữ liệu thực tế (04/07/2012 → 31/12/2022)'), t.answer_md


def test_rv12e_b03_lan_so_dung_ky_va_ky_khac(versioned):
    # live B03: hỏi vùng West tháng 12/2021, tool chỉ có R toàn công ty; câu dẫn thêm R cùng tháng năm trước (kỳ khác)
    ans = ('Số theo tháng chỉ có cho toàn công ty, chưa hỗ trợ tách riêng theo khu vực. Mình chỉ có thể cho bạn R tháng '
           '12/2021 của toàn công ty là {c1}, so cùng tháng năm trước đổi {c2} (R cùng tháng năm trước là {c3}); đây không '
           'phải số của riêng vùng West.')
    rep = final('unsupported', ans, [{'id': 'c1', 'path': 'T1.rows[0].r'}, {'id': 'c2', 'path': 'T1.rows[0].yoy_rate'},
                                     {'id': 'c3', 'path': 'T1.rows[0].r_same_month_prior_year'}])
    t = _turn('Vùng West tháng 12 năm 2021 thu được bao nhiêu?',
              call('get_revenue_monthly', metric='R', year=2021, month=12), rep, rep)
    _khuon(t, 'unsupported', asked='West', ky=('Tháng 12/2021, toàn công ty: R là', 'Tháng 12/2021, toàn công ty: % đổi R',
                                               'Tháng 12/2020, toàn công ty: R là'))
    assert t.answer_md.startswith('Số theo tháng chỉ có cho toàn công ty, chưa hỗ trợ tách riêng theo khu vực.')
    assert 'nằm ngoài' not in t.answer_md            # tháng 12/2021 có trong dữ liệu: lý do là nhóm, không phải kỳ


@pytest.mark.parametrize('q,src,lead,extra', [
    (Q25, _M8, 'Năm 2025 chưa có dự báo. ', 'Khả năng cao sẽ giống vậy.'),
    (Q25, _M8, 'Năm 2025 chưa có dự báo. ', 'Doanh thu khi đó chắc cũng không khác mấy.'),
    ('Doanh thu kênh referral quý 3/2020?', ('get_segment_contribution', dict(metric='R', dimension='acquisition_channel',
     year=2020, group='referral'), 'T1.rows[referral].r'), 'Chưa hỗ trợ số theo quý. ', 'Quý 3 chắc cũng giống vậy.'),
    ('Doanh thu kênh referral quý 3/2020?', ('get_segment_contribution', dict(metric='R', dimension='acquisition_channel',
     year=2020, group='referral'), 'T1.rows[referral].r'), 'Chưa hỗ trợ số theo quý. ', 'Khả năng cao sẽ gần như vậy.'),
])
def test_rv12e_cau_phong_doan_khong_so_bi_bo(versioned, q, src, lead, extra):
    # câu phỏng đoán không có số, không nhắc kỳ: có câu "ngoài vùng" thì bỏ mọi câu dẫn; không có thì lọc chữ phỏng đoán
    tool, args, path = src
    rep = final('no_data' if q == Q25 else 'unsupported', lead + 'Số tham khảo là {c1}. ' + extra,
                [{'id': 'c1', 'path': path}])
    t = _turn(q, call(tool, **args), rep, rep)
    assert t.answer_md and extra not in t.answer_md, t.answer_md
    assert (lead.strip() in t.answer_md) == (q != Q25), t.answer_md    # PS: câu lý do không số vẫn giữ


def test_rv12e_hoi_lai_bi_bo_thi_app_hoi_lai(versioned):
    rep = final('needs_clarification', _REF + 'Bạn có muốn dùng số này làm dự báo năm 2025?', [{'id': 'c1', 'path': _ROW}])
    t = _turn(Q25, call(*_M8[:1], **_M8[1]), rep, rep)
    _khuon(t, 'needs_clarification')
    assert t.answer_md.endswith('\n\nBạn muốn xem kỳ nào?'), t.answer_md


def test_rv12e_so_khong_co_nhan_khong_hien(versioned):
    # ô số chưa có nhãn chỉ tiêu (n_days) cạnh số kỳ khác: app không dẫn số không nhãn, trả lỗi để mô hình sửa
    rep = final('no_data', _REF + 'Tháng đó có {c2} ngày có dự báo.',
                [{'id': 'c1', 'path': _ROW}, {'id': 'c2', 'path': 'T1.rows[0].n_days'}])
    t = _turn(Q25, call(*_M8[:1], **_M8[1]), rep, rep)
    assert t.status == 'answer_validation_failed' and not t.answer_md, (t.status, t.answer_md)
    assert any('chưa dựng được nhãn' in e for e in t.validation_errors), t.validation_errors


def test_rv12e_ky_khong_hop_le_van_khong_dan_so(versioned):
    # RV10 giữ nguyên: kỳ không có thật thì không dẫn số nào, kể cả theo khuôn
    rep = final('no_data', _REF, [{'id': 'c1', 'path': _ROW}])
    t = _turn('Dự báo doanh thu quý 5/2025?', call(*_M8[:1], **_M8[1]), rep, rep)
    assert t.status == 'answer_validation_failed' and not t.answer_md, (t.status, t.answer_md)


# RV12 lượt kiểm Codex 2026-10-17: câu hỏi tự nêu cả kỳ thiếu số lẫn kỳ tham khảo.
@pytest.mark.parametrize('answer', [
    'Năm 2025 chưa có dự báo. Riêng tháng 8/2023, dự báo G là {c1}; số này chỉ để tham khảo.',
    'Năm 2025 chưa có dự báo. Riêng tháng 8/2023, dự báo G là {c1}. Số này là dự báo năm 2025.',
    'Riêng tháng 8/2023, dự báo G là {c1}. Bạn có thể dùng số đó làm dự báo năm 2025.',
])
def test_rv12f_hai_ky_trong_cau_hoi_van_dung_khuon(versioned, answer):
    q = 'Dự báo G năm 2025 có không? Nếu chưa có, cho thêm số tháng 8/2023 làm mốc tham khảo.'
    rep = final('no_data', answer, [{'id': 'c1', 'path': _ROW}])
    t = _turn(q, call(*_M8[:1], **_M8[1]), rep, rep)
    _khuon(t, 'no_data', asked='2025', ky=('08/2023',))
    assert t.answer_md.startswith('Năm 2025 nằm ngoài vùng dự báo (01/01/2023 → 01/07/2024)'), t.answer_md
    assert 'Số này là dự báo năm 2025' not in t.answer_md
    assert 'làm dự báo năm 2025' not in t.answer_md


def test_rv12f_cau_hoi_co_tong_vung_va_nam_2025_van_dung_khuon(versioned):
    q = 'Dự báo G năm 2025 có không? Nếu không, cho tổng cả vùng dự báo làm mốc tham khảo.'
    rep = final('no_data', 'Tổng cả vùng dự báo là {c1}. Đây là dự báo năm 2025.',
                [{'id': 'c1', 'path': 'T1.derived.horizon_total.g_forecast'}])
    t = _turn(q, call('get_forecast', metric='G', period='horizon'), rep, rep)
    _khuon(t, 'no_data', asked='2025', ky=('Cả vùng dự báo',))
    assert t.answer_md.startswith('Năm 2025 nằm ngoài vùng dự báo (01/01/2023 → 01/07/2024)'), t.answer_md
    assert 'Đây là dự báo năm 2025' not in t.answer_md


@pytest.mark.parametrize('answer', [
    'Năm 2025 chưa có dự báo. Riêng tháng 8/2023, dự báo G là {c1}. Số này là dự báo năm 2025.',
    'Năm 2025 chưa có dự báo. Riêng tháng 8/2023, dự báo G là {c1}; số này chỉ để tham khảo.',
])
def test_rv12f_ok_khong_duoc_bo_qua_ky_thieu_du_bao(versioned, answer):
    q = 'Dự báo G năm 2025 có không? Nếu chưa có, cho thêm số tháng 8/2023 làm mốc tham khảo.'
    rep = final('ok', answer, [{'id': 'c1', 'path': _ROW}])
    t = _turn(q, call(*_M8[:1], **_M8[1]), rep, rep)
    assert t.status == 'answer_validation_failed' and not t.answer_md, (t.status, t.answer_md)


def test_rv12f_ok_ky_tham_khao_2024_chi_co_mot_phan(versioned):
    q = 'Dự báo G năm 2025 có không? Cho thêm số năm 2024 làm mốc tham khảo.'
    rep = final('ok', 'Năm 2024 dự báo G là {c1}. Số này là dự báo năm 2025.',
                [{'id': 'c1', 'path': _ROW}])
    t = _turn(q, call('get_forecast', metric='G', period='year', year=2024), rep, rep)
    assert t.status == 'answer_validation_failed' and not t.answer_md, (t.status, t.answer_md)


def test_rv12f_sua_status_cho_ky_2024_thieu_mot_phan(versioned):
    q = 'Dự báo G năm 2025 có không? Cho thêm số năm 2024 làm mốc tham khảo.'
    claim = [{'id': 'c1', 'path': _ROW}]
    wrong = final('ok', 'Năm 2024 dự báo G là {c1}. Số này là dự báo năm 2025.', claim)
    fixed = final('no_data', 'Năm 2025 chưa có dự báo. Riêng năm 2024, dự báo G là {c1}.', claim)
    t = _turn(q, call('get_forecast', metric='G', period='year', year=2024), wrong, fixed)
    assert t.status == 'no_data' and t.answer_md, (t.status, t.validation_errors)
    assert t.answer_md.startswith('Năm 2025 nằm ngoài vùng dự báo'), t.answer_md
    assert 'Năm 2024, toàn công ty' in t.answer_md and 'Số này là dự báo năm 2025' not in t.answer_md


# --- review Claude 2026-10-17: quý viết "Q3/2023" / "quý III/2023"; số cả vùng dự báo cho câu hỏi nêu năm ---

_Q3 = ('range', dt.date(2023, 7, 1), dt.date(2023, 9, 30), 'quý 3/2023')


@pytest.mark.parametrize('q,expect', [
    ('Dự báo G Q3/2023 bao nhiêu?', [_Q3]),          # trước: đọc thành tháng 3/2023
    ('dự báo q3 2023', [_Q3]),
    ('Q3-2023', [_Q3]),
    ('Q3 năm 2023', [_Q3]),
    ('quý III/2023', [_Q3]),                        # trước: đọc thành cả năm 2023
    ('quý iii năm 2023', [_Q3]),
    ('quý IV/2023', [('range', dt.date(2023, 10, 1), dt.date(2023, 12, 31), 'quý 4/2023')]),
    ('Q5/2023', [('invalid', 'q5/2023')]),
    ('tháng 3/2023', [(2023, 3, None)]),              # không có chữ quý / Q: vẫn là tháng
    ('Dự báo PS3 năm 2023', [(2023, None, None)]),
])
def test_doc_quy_viet_tat_va_la_ma(q, expect):
    assert evidence.question_periods(q) == expect


def _claims_t(answer):
    # {cN} trỏ số dự báo G của lượt gọi tool thứ N
    return [{'id': f'c{n}', 'path': f'T{n}.rows[0].g_forecast'} for n in sorted({int(x) for x in re.findall(r'\{c(\d+)\}',
                                                                                                          answer)})]


@pytest.mark.parametrize('q,months,answer,ok', [
    # câu trả lời lặp lại cách viết "Q3/2023" với số tháng 3: trước đây cả câu hỏi lẫn câu trả lời đều đọc thành tháng
    # 3/2023 nên lọt
    ('Dự báo G Q3/2023 bao nhiêu?', [3], 'Dự báo G Q3/2023 là {c1}.', False),
    ('Dự báo G Q3/2023 bao nhiêu?', [3], 'Dự báo G quý 3/2023 là {c1}.', False),
    ('Dự báo G Q3/2023 bao nhiêu?', [8], 'Tổng dự báo G Q3/2023 là {c1}.', False),
    # nêu riêng từng tháng trong quý: trước đây bị chặn nhầm
    ('Dự báo G Q3/2023 bao nhiêu?', [7, 8, 9],
     'Chưa có tổng quý. Riêng tháng 7/2023 là {c1}, tháng 8/2023 là {c2}, tháng 9/2023 là {c3}.', True),
    ('Dự báo G quý III/2023?', [7], 'Riêng tháng 7/2023, dự báo G là {c1}.', True),
    ('Dự báo G quý III/2023?', [7], 'Tổng dự báo G quý III/2023 là {c1}.', False),
    ('Dự báo G quý III/2023?', [3], 'Riêng tháng 3/2023, dự báo G là {c1}.', False),
    ('Dự báo G Q5/2023?', [8], 'Dự báo G là {c1}.', False),
])
def test_quy_viet_tat_va_la_ma(versioned, q, months, answer, ok):
    rep = final(answer=answer, claims=_claims_t(answer))
    t = _turn(q, *[_m(2023, m) for m in months], rep, rep)
    assert (t.status == 'ok') == ok, (q, answer, t.status, t.validation_errors)


_HZ_TOTAL = ['T1.derived.horizon_total.g_forecast']


@pytest.mark.parametrize('q,answer,paths,ok', [
    # câu hỏi nêu năm mà muốn số cả vùng dự báo: trước đây luôn bị chặn
    ('Dự báo G giai đoạn 2023–2024 tổng bao nhiêu?', 'Tổng dự báo G cả kỳ dự báo là {c1}.', _HZ_TOTAL, True),
    ('Tổng dự báo G 2023-2024 là bao nhiêu?', 'Tổng dự báo G cả vùng dự báo là {c1}.', _HZ_TOTAL, True),
    ('Tháng nào dự báo G cao nhất từ 2023 đến 2024?', 'Tháng {c1} có dự báo G cao nhất, {c2}.',
     ['T1.derived.highest_month.months', 'T1.derived.highest_month.g_forecast'], True),
    # vùng dự báo dừng ở 01/07/2024: tổng cả vùng không phải tổng 2023–2024, câu phải gọi đúng tên vùng dự báo
    ('Tổng dự báo G 2023-2024 là bao nhiêu?', 'Tổng dự báo G 2023–2024 là {c1}.', _HZ_TOTAL, False),
    # câu hỏi một năm: tổng cả vùng không phải tổng năm đó (dùng dòng năm)
    ('Tổng dự báo G năm 2023 là bao nhiêu?', 'Tổng dự báo G cả kỳ dự báo là {c1}.', _HZ_TOTAL, False),
])
def test_so_ca_vung_du_bao_cho_cau_hoi_neu_nam(versioned, q, answer, paths, ok):
    rep = final(answer=answer, claims=[{'id': f'c{i + 1}', 'path': p} for i, p in enumerate(paths)])
    t = _turn(q, call('get_forecast', metric='G', period='horizon'), rep, rep)
    assert (t.status == 'ok') == ok, (q, answer, t.status, t.validation_errors)


@pytest.mark.parametrize('side', ['highest_month', 'lowest_month'])
def test_thang_cao_thap_nhat_vung_du_bao_theo_nam_hoi(versioned, side):
    # tháng cao / thấp nhất cả vùng dự báo cũng là cao / thấp nhất của năm chứa nó; năm kia thì không suy được
    months = _run(metric='G', period='horizon').derived[side]['months']
    word = 'cao' if side == 'highest_month' else 'thấp'
    for y in (2023, 2024):
        rep = final(answer=f'Tháng {{c1}} có dự báo G {word} nhất, {{c2}}.',
                    claims=[{'id': 'c1', 'path': f'T1.derived.{side}.months'},
                            {'id': 'c2', 'path': f'T1.derived.{side}.g_forecast'}])
        t = _turn(f'Tháng nào dự báo G {word} nhất năm {y}?', call('get_forecast', metric='G', period='horizon'), rep, rep)
        assert (t.status == 'ok') == all(p.endswith(f'/{y}') for p in months), (y, months, t.validation_errors)
