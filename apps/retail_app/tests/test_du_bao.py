"""B3b: trang Dự báo (views/du_bao.py) đọc rpt_forecast_* của bản dữ liệu đang phục vụ (docs/ke_hoach_ai_gd2.md).

Ba trạng thái: chế độ cũ (báo chưa có dự báo), bản trước B2b (không có bảng dự báo), bản đang phục vụ (có số).
Số kỳ vọng lấy bằng câu SQL riêng mở THẲNG file DuckDB của bản dữ liệu (không qua dwh/, releases hay code trang), bằng
parquet do stage dự báo ghi, và bằng data/sales.csv. Cần một bản có dự báo (pipeline B2b chạy local); chưa có thì skip.
"""
import json
import shutil
from pathlib import Path

import duckdb
import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from ai_explain import metric_catalog as cat
from ai_explain import tools
from dwh import forecast_queries as fq
from dwh import queries, releases
from dwh.connection import DUCKDB_PATH, ROOT
from ui.fmt import num, trieu

APP = Path(__file__).resolve().parents[1] / 'app.py'
PAGE = 'views/du_bao.py'
STATE = ROOT / 'warehouse' / 'pipeline' / 'state.json'
PRE_B2B = '6f8654fb4b4348c483a78b64'          # bản dựng trước B2b: không có rpt_forecast_*
CAU_BACKTEST = 'sai số backtest 2020–2022, không phải độ chính xác 2023–2024'


def _payload() -> dict | None:
    return json.loads(STATE.read_text(encoding='utf-8'))['payload'] if STATE.exists() else None


def _so(s: str) -> float:
    """'54.138.706,54' → 54138706.54 (định dạng Việt của ui.fmt.num)."""
    return float(s.replace('.', '').replace(',', '.').replace('−', '-'))


def _page(mp: pytest.MonkeyPatch, state: Path | None) -> AppTest:
    mp.setenv('RETAIL_BACKEND', 'duckdb')
    if state is None:
        mp.delenv('RETAIL_RELEASE_MODE', raising=False)
    else:
        mp.setenv('RETAIL_RELEASE_MODE', 'versioned')
        mp.setenv('RETAIL_RELEASE_STATE', str(state))
    releases.reset()
    st.cache_data.clear()
    at = AppTest.from_file(str(APP), default_timeout=120).run()
    at.switch_page(PAGE).run()
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]
    return at


def _co_bang(rec: dict, name: str) -> bool:
    """Bản dữ liệu `rec` có relation reporting `name` không (mở thẳng file DuckDB của bản)."""
    con = duckdb.connect(rec['duckdb_path'], read_only=True)
    try:
        return con.execute('select count(*) from information_schema.tables where table_schema = ? and table_name = ?',
                           [rec['schema'], name]).fetchone()[0] > 0
    finally:
        con.close()


@pytest.fixture(scope='module')
def ban() -> dict:
    """Record của bản đang phục vụ; skip nếu bản đó không có dự báo."""
    p = _payload()
    if not p or not p.get('active'):
        pytest.skip('chưa có bản dữ liệu do pipeline publish (warehouse/pipeline/state.json)')
    rec = p['releases'][p['active']]
    if not (STATE.parent / 'runs' / rec['run_id'] / 'forecast' / 'forecast_daily.parquet').exists():
        pytest.skip(f'bản {rec["release_id"]} không có dự báo (dựng trước B2b)')
    return rec


@pytest.fixture(scope='module')
def sql(ban):
    """Câu đối chứng: mở thẳng file DuckDB của bản, tên schema lấy từ registry."""
    def run(q: str) -> pd.DataFrame:
        con = duckdb.connect(ban['duckdb_path'], read_only=True)
        try:
            return con.execute(q.format(s=ban['schema'])).df()
        finally:
            con.close()
    return run


@pytest.fixture(scope='module')
def trang(ban) -> AppTest:
    with pytest.MonkeyPatch.context() as mp:
        yield _page(mp, STATE)


# --- trạng thái không có dự báo: báo rõ, không lỗi, không số ---

def test_che_do_cu_bao_chua_co_du_bao(monkeypatch):
    if not DUCKDB_PATH.exists():
        pytest.skip('chưa có warehouse/dbt.duckdb')
    at = _page(monkeypatch, None)
    assert any('Chưa có dự báo' in i.value and 'chế độ cũ' in i.value for i in at.info)
    assert not at.metric and not at.dataframe and not at.warning
    assert any('Nguồn:' in c.value and 'reporting.rpt_build_info' in c.value for c in at.caption)   # trang không dừng giữa chừng


def test_ban_truoc_b2b_bao_chua_co_du_bao(monkeypatch, tmp_path):
    p = _payload()
    if not p or PRE_B2B not in p['releases'] or not Path(p['releases'][PRE_B2B]['duckdb_path']).exists():
        pytest.skip('registry không có bản trước B2b')
    p['active'] = PRE_B2B                          # như khi rollback về bản cũ
    for rec in p['releases'].values():
        rec.pop('artifact_path', None)             # state tạm nằm ở tmp_path: dùng đường dẫn tuyệt đối duckdb_path
    state = tmp_path / 'state.json'
    state.write_text(json.dumps({'payload': p}), encoding='utf-8')
    at = _page(monkeypatch, state)
    assert any('Chưa có dự báo' in i.value and PRE_B2B in i.value for i in at.info)
    assert not at.metric and not at.dataframe and not at.warning
    assert any('Nguồn:' in c.value and 'reporting.rpt_build_info' in c.value for c in at.caption)   # trang không dừng giữa chừng


# --- bản có dự báo ---

def test_nhan_bat_buoc(trang, sql, ban):
    meta = sql('select distinct model, cogs_method, model_version, trained_through, run_id, selection_step '
               'from {s}.rpt_forecast_daily where is_primary')
    assert len(meta) == 1
    m = meta.iloc[0]
    nhan = next(x.value for x in trang.markdown if 'Đây là số dự báo' in x.value)
    for phai_co in [cat.G_LABEL, f'`{m.model} / {m.cogs_method}`', f'**model_version** `{m.model_version}`',
                    f'**trained_through** {m.trained_through:%d/%m/%Y}', f'`{m.run_id}`', 'khoảng dự báo 80%',
                    'tháng không có khoảng (Q7)']:
        assert phai_co in nhan, phai_co
    assert CAU_BACKTEST in nhan.lower()
    assert tools.SELECTION_REASON[m.selection_step] in nhan            # lý do từ selection_step, chung với chat
    assert not trang.warning
    if _co_bang(ban, 'rpt_forecast_actual'):
        assert not trang.info                      # đủ dự báo và số thực tế: không thông báo trạng thái


def test_tong_thang_khop_query_doi_chung(trang, sql, ban):
    exp = sql("select strftime(forecast_date, '%m/%Y') as thang, sum(yhat) as g, sum(cogs_yhat) as cogs, "
              'count(*) as n from {s}.rpt_forecast_daily where is_primary group by 1 order by min(forecast_date)')
    full = trang.dataframe[1].value
    assert list(full.columns) == ['Tháng', 'G dự báo', 'COGS dự báo', 'Số ngày có dự báo']
    assert full['Tháng'].tolist() == exp['thang'].tolist() and len(exp) == 19
    for got, want in [(full['G dự báo'].map(_so), exp['g']), (full['COGS dự báo'].map(_so), exp['cogs'])]:
        assert (abs(got.values - want.values) <= 0.005 + 1e-12 * want.values).all()   # làm tròn 2 chữ số
    # parquet của stage dự báo (không qua dbt) cho cùng tổng tháng
    pq = pd.read_parquet(STATE.parent / 'runs' / ban['run_id'] / 'forecast' / 'forecast_daily.parquet')
    pq = pq[pq.is_primary]
    g_pq = pq.groupby(pd.to_datetime(pq.forecast_date).dt.strftime('%m/%Y'), sort=False)['yhat'].sum()
    assert g_pq.loc[exp['thang']].values == pytest.approx(exp['g'].values, rel=1e-12)
    # KPI cả kỳ = tổng 548 ngày
    # bảng PM nhìn thấy (triệu, 1 chữ số; COGS/G = ΣCOGS ÷ ΣG của tháng, hợp đồng §2.2 — không lấy TB tỷ lệ ngày)
    bang = trang.dataframe[0].value
    assert bang['Tháng'].tolist() == exp['thang'].tolist()
    for cot, want in [('G dự báo', exp['g']), ('COGS dự báo', exp['cogs'])]:
        got = bang[cot].map(lambda x: _so(x.removesuffix(' triệu')) * 1e6)
        assert (abs(got.values - want.values) <= 0.05e6 + 1).all(), cot
    assert bang['COGS/G'].tolist() == (exp['cogs'] / exp['g']).map(lambda v: num(v, 3)).tolist()
    # KPI cả kỳ = tổng 548 ngày
    for nhan, want in [('G dự báo cả kỳ', exp['g'].sum()), ('COGS dự báo cả kỳ', exp['cogs'].sum())]:
        the = next(x for x in trang.metric if x.label.startswith(nhan))
        assert _so(the.help.split('Số đầy đủ: ')[1].rstrip('.')) == pytest.approx(want, abs=0.006), nhan


def test_sua_so_trong_ban_sao_thi_trang_doi_theo(trang, ban, monkeypatch, tmp_path):
    # như tests/test_khong_hardcode.py: chép file của bản, sửa số dự báo một ngày và model_version, trang phải đổi theo
    shutil.copy(ban['duckdb_path'], tmp_path / 'dbt.duckdb')        # giữ tên dbt.duckdb: view trỏ bảng qua catalog "dbt"
    con = duckdb.connect(str(tmp_path / 'dbt.duckdb'))
    con.execute(f"update {ban['schema']}.rpt_forecast_daily set yhat = yhat + 1000000 "
                "where is_primary and forecast_date = date '2023-08-15'")
    con.execute(f"update {ban['schema']}.rpt_forecast_daily set model_version = 'SOLA42' where is_primary")
    con.close()
    p = _payload()
    rec = dict(p['releases'][p['active']], duckdb_path=str(tmp_path / 'dbt.duckdb'))
    rec.pop('artifact_path', None)
    state = tmp_path / 'state.json'
    state.write_text(json.dumps({'payload': {**p, 'releases': {rec['release_id']: rec}}}), encoding='utf-8')
    sua = _page(monkeypatch, state)
    goc, moi = (t.dataframe[1].value.set_index('Tháng')['G dự báo'].map(_so) for t in (trang, sua))
    assert moi['08/2023'] - goc['08/2023'] == pytest.approx(1_000_000, abs=0.02)
    assert (moi.drop('08/2023') == goc.drop('08/2023')).all()
    assert any('`SOLA42`' in x.value for x in sua.markdown)


def test_thang_07_2024_la_thang_thieu_va_khong_co_khoang_thang(trang):
    bang = trang.dataframe[0].value
    cuoi = bang.iloc[-1]
    assert cuoi['Tháng'] == '07/2024' and cuoi['Số ngày có dự báo'] == '1/31' and 'Tháng thiếu' in cuoi['Ghi chú']
    assert (bang['Ghi chú'].iloc[:-1] == '').all()
    for df in trang.dataframe[:2]:                 # Q7: bảng tháng không có cột khoảng / cận
        assert not [c for c in df.columns if any(k in c.lower() for k in ('khoảng', 'cận', 'lower', 'upper'))]
    assert any('Tháng không có khoảng dự báo (Q7)' in c.value and CAU_BACKTEST in c.value for c in trang.caption)


def test_sai_so_thang_dien_hinh_va_bang_ung_vien(trang, sql):
    bt = sql("select model, cogs_method, role, avg(case when metric = 'score' then value end) as score, "
             "avg(case when metric = 'mape_g_thang' then value end) as mape, "
             "count(case when metric = 'score' then 1 end) as n from {s}.rpt_forecast_backtest group by 1, 2, 3")
    prim = sql('select distinct model, cogs_method from {s}.rpt_forecast_daily where is_primary').iloc[0]
    p = bt[(bt.model == prim.model) & (bt.cogs_method == prim.cogs_method)].iloc[0]
    the = next(x for x in trang.metric if x.label == 'Sai số tháng điển hình')
    assert the.value == num(p.mape, 1) + '%' and CAU_BACKTEST in the.help
    ss = trang.dataframe[2].value
    assert len(ss) == len(bt) and (bt.n == 3).all()
    sao = ss[ss['Model'].str.startswith('★ ')]
    assert len(sao) == 1                                                   # đúng một model chính
    r = sao.iloc[0]
    assert r['Model'] == '★ ' + tools.MODEL_LABEL[prim.model] and r['Cách tính COGS'] == tools.COGS_LABEL[prim.cogs_method]
    assert r['Điểm ngày'] == trieu(p.score, 3) and r['MAPE G tháng'] == num(p.mape, 1) + '%'
    assert r['Thắng sàn cả 3 fold'] == 'Có' and p.role == 'candidate'
    # bước luật đã chọn: chú thích dưới bảng, lấy từ selection_step của bản
    step = sql('select distinct selection_step from {s}.rpt_forecast_daily where is_primary').iloc[0, 0]
    assert any(c.value.startswith(f'★ = model chính, chọn ở **bước {step.split("_")[1]}') for c in trang.caption)
    # thứ tự theo điểm ngày (thước chọn), không theo MAPE; đúng một mốc sàn
    assert ss['Điểm ngày'].map(lambda x: _so(x.removesuffix(' triệu'))).is_monotonic_increasing
    assert ss['Model'].str.endswith('(mốc sàn)').sum() == 1 == (bt.role == 'floor').sum()


def test_thuc_te_la_G_cung_ban_khong_phai_R(ban, sql, monkeypatch):
    if not _co_bang(ban, 'rpt_forecast_actual'):
        pytest.skip(f'bản {ban["release_id"]} dựng trước rpt_forecast_actual')
    monkeypatch.setenv('RETAIL_RELEASE_MODE', 'versioned')
    monkeypatch.setenv('RETAIL_RELEASE_STATE', str(STATE))
    releases.reset()
    try:
        tt = fq.actual_daily('duckdb')
    finally:
        releases.reset()
    assert len(tt) == 730 and tt.sale_date.min() == pd.Timestamp('2021-01-01') and tt.sale_date.max() == pd.Timestamp('2022-12-31')
    thang = tt.groupby(tt.sale_date.dt.to_period('M'))['g'].sum()
    rpt = sql("select month_start_date, g, r from {s}.rpt_revenue_monthly where year in (2021, 2022) order by 1")
    assert thang.values == pytest.approx(rpt.g.values, abs=0.01)          # G của PS1–PS5, không phải R
    assert not (abs(thang.values - rpt.r.values) < 1).any()
    sales = ROOT / 'data' / 'sales.csv'
    if sales.exists():                                                     # nguồn gốc: sales.csv (CLAUDE.md §5.1)
        s = pd.read_csv(sales, parse_dates=['Date']).set_index('Date').loc['2021-01-01':'2022-12-31']
        assert tt.set_index('sale_date')['g'].values == pytest.approx(s['Revenue'].values, abs=0.006)
        assert tt.set_index('sale_date')['cogs'].values == pytest.approx(s['COGS'].values, abs=0.006)


def test_ban_co_du_bao_chua_co_bang_thuc_te(monkeypatch, tmp_path):
    # bản B2b đầu tiên (rpt_forecast_* có, rpt_forecast_actual chưa có): vẫn hiện dự báo, báo thiếu số thực tế, không lỗi
    p = _payload()
    cu = [r for r in (p or {}).get('releases', {}).values()
          if Path(r['duckdb_path']).exists() and _co_bang(r, 'rpt_forecast_daily') and not _co_bang(r, 'rpt_forecast_actual')]
    if not cu:
        pytest.skip('registry không có bản có dự báo mà chưa có rpt_forecast_actual')
    p['active'] = cu[0]['release_id']
    for rec in p['releases'].values():
        rec.pop('artifact_path', None)
    state = tmp_path / 'state.json'
    state.write_text(json.dumps({'payload': p}), encoding='utf-8')
    at = _page(monkeypatch, state)
    assert any('chưa có bảng số thực tế' in i.value and 'rpt_forecast_actual' in i.value for i in at.info)
    assert not at.warning and len(at.metric) == 4 and len(at.dataframe) == 4
    assert not any('marts.' in c.value for c in at.caption)                # không đọc marts thay vào


def test_trang_ps_khong_doc_du_bao():
    # số dự báo không trộn vào trang PS1–PS5; queries.SOURCE (= app_read_relations, mọi backend) không có bảng tùy chọn
    views = Path(__file__).resolve().parents[1] / 'views'
    for f in ['tong_quan.py', 'ps1_do_dung.py', 'ps2_xu_huong.py', 'ps3_nhip_lich.py', 'ps4_don_mon_gia.py', 'ps5_nhom.py']:
        text = (views / f).read_text(encoding='utf-8')
        assert 'forecast' not in text and 'du_bao' not in text, f
    assert not [t for t in queries.SOURCE.values() if 'forecast' in t or t.startswith('marts.')]
    assert all(t.startswith('reporting.') for t in fq.SOURCE.values())   # trang Dự báo không đọc ngoài reporting


def test_rv11_quyen_doc_ba_bang_trang_du_bao():
    # RV11 (review Codex 2026-10-15 §8): ba bảng trang đọc = var app_optional_relations; macro cấp cho SP của app và của
    # bản web cả danh sách này (bỏ qua bảng chưa có); không vào app_read_relations bắt buộc
    import re
    import yaml
    proj = yaml.safe_load((ROOT / 'retail_dbt' / 'dbt_project.yml').read_text(encoding='utf-8'))['vars']
    assert set(proj['app_optional_relations']) == set(fq.SOURCE.values())
    assert not set(proj['app_optional_relations']) & set(proj['app_read_relations'])
    macro = re.sub(r'\{#.*?#\}', '', (ROOT / 'retail_dbt' / 'macros' / 'ai_readonly_grants.sql').read_text(encoding='utf-8'),
                   flags=re.S)
    for who in ('APP', 'WEB'):
        assert (f"env_var('RETAIL_{who}_DBX_PRINCIPAL', ''), var('app_read_relations') + var('app_optional_relations', [])"
                in macro), who
