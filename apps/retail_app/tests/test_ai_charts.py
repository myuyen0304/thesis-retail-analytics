"""B6 (L2): show_chart vẽ từ ĐÚNG kết quả tool đã chạy trong lượt. Mô hình giả, không gọi API.

Chứng minh: dữ liệu biểu đồ = các dòng bằng chứng của tool (và khớp số đối chứng độc lập từ parquet của stage dự báo);
lời gọi sai bị từ chối; biểu đồ không tính vào giới hạn đọc kho; trang chat vẽ lại từ kết quả đã lưu, không gọi lại mô hình.
"""
import datetime as dt
import json

import pytest

from ai_explain import charts, service
from ai_explain.contracts import ToolResult
from ai_explain.provider import Reply, ToolCallReq
from tests.test_ai_chat import FakeProvider, _app, call, final
from tests.test_ai_forecast import RTOL, ref, versioned          # noqa: F401 (fixture)

HORIZON = dict(metric='G', period='horizon')


def calls(*pairs) -> Reply:
    """Một lượt mô hình gọi nhiều tool theo thứ tự (vd. get_forecast rồi show_chart(T1))."""
    cs = [ToolCallReq(f'id{i}{n}', n, json.dumps(a)) for i, (n, a) in enumerate(pairs)]
    return Reply(None, cs, {'role': 'assistant', 'content': '', 'tool_calls': [
        {'id': c.id, 'type': 'function', 'function': {'name': c.name, 'arguments': c.arguments_json}} for c in cs]}, 100, 10)


def _turn(q, *steps, history=()):
    return service.run_turn(q, list(history), 'duckdb', FakeProvider(*steps))


OK_FC = final(answer='Biểu đồ dưới đây là dự báo G từng tháng; tháng thấp nhất là {c1}.',
              claims=[{'id': 'c1', 'path': 'T1.derived.lowest_month.months'}])


def _vega_values(spec, df) -> list[dict]:
    d = charts.chart(spec, df).to_dict()
    data = d.get('datasets') or {}
    return next(iter(data.values())) if data else d['data']['values']


# --- dữ liệu biểu đồ = bằng chứng ---

def test_bieu_do_du_bao_dung_bang_bang_chung_va_doi_chung(versioned, ref):
    _, daily, _ = ref
    t = _turn('Vẽ dự báo G từng tháng trong kỳ dự báo',
              calls(('get_forecast', HORIZON), ('show_chart', {'ref': 'T1', 'y': 'g_forecast'})), OK_FC)
    assert t.status == 'ok', t.validation_errors
    assert [tool for _, tool, _ in t.calls] == ['get_forecast'] and len(t.charts) == 1      # show_chart không thành T2
    spec, res = t.charts[0], t.results['T1']
    df = charts.frame(spec, t.results)
    full = [r for r in res.rows if not r['is_partial']]
    assert list(df['x']) == [r['period'] for r in full] and len(full) == 18 == spec.n_points
    assert list(df['gia_tri']) == [float(r['g_forecast']) for r in full]
    # đối chứng độc lập: tổng tháng của ứng viên chính tính thẳng từ parquet của stage (không qua dbt / tool)
    prim = daily[daily.is_primary]
    for _, row in df.iterrows():
        m, y = map(int, row['x'].split('/'))
        exp = prim[[d.year == y and d.month == m for d in prim.forecast_date]].yhat.sum()
        assert row['gia_tri'] == pytest.approx(exp, rel=RTOL)
    assert spec.excluded == ('07/2024 (chỉ 1/31 ngày có dự báo)',)                         # không vẽ như cả tháng
    assert spec.title == res.derived['forecast_label'] and spec.kind == 'line' and not spec.band
    assert any('Q7' in c for c in spec.captions) and any('07/2024' in c for c in spec.captions)
    assert [v['gia_tri'] for v in _vega_values(spec, df)] == list(df['gia_tri'])          # Altair nhận đúng dữ liệu đó


def test_bieu_do_backtest_danh_dau_model_chinh(versioned):
    t = _turn('Vẽ điểm sai số các model dự báo', call('get_forecast_backtest'),
              call('show_chart', ref='T1', y='score'),
              final(answer='Biểu đồ điểm ngày kết hợp; model chính là {c1}.', claims=[
                  {'id': 'c1', 'path': 'T1.derived.primary.label'}]))
    assert t.status == 'ok', t.validation_errors
    spec = t.charts[0]
    df = charts.frame(spec, t.results)
    rows = t.results['T1'].rows
    assert spec.kind == 'bar' and spec.n_points == len(rows) == len(df)
    assert list(df['gia_tri']) == [float(r['score']) for r in rows]
    assert [x for x in df['x'] if x.startswith('★ ')] == ['★ ' + next(r['candidate_label'] for r in rows if r['is_primary'])]


def test_bieu_do_hai_chi_tieu_cung_don_vi(versioned):
    t = _turn('Vẽ dự báo G và COGS từng tháng', calls(('get_forecast', dict(metric='G_and_COGS', period='horizon')),
                                                     ('show_chart', {'ref': 'T1', 'y': 'g_forecast', 'y2': 'cogs_forecast'})),
              final(answer='Biểu đồ dự báo G và COGS từng tháng; tháng G thấp nhất là {c1}.',
                    claims=[{'id': 'c1', 'path': 'T1.derived.lowest_month.months'}]))
    assert t.status == 'ok', t.validation_errors
    df = charts.frame(t.charts[0], t.results)
    assert sorted(set(df['cot'])) == ['cogs_forecast', 'g_forecast'] and len(df) == 36


def test_khoang_80_chi_ve_khi_moi_dong_co_can():
    rows = [{'period': f'0{d}/08/2023', 'g_forecast': 100.0 + d, 'lower_g': 80.0 + d, 'upper_g': 120.0 + d,
             'is_primary': True} for d in (1, 2)]
    res = {'T1': ToolResult('ok', 'x', rows=rows, derived={'forecast_label': 'Dự báo, khoảng 80% theo ngày'})}
    spec, out = charts.build({'ref': 'T1', 'y': 'g_forecast'}, res, [('T1', 'get_forecast', {})])
    assert out.ok and spec.band
    df = charts.frame(spec, res)
    assert list(df['duoi']) == [81.0, 82.0] and list(df['tren']) == [121.0, 122.0]
    rows[1]['upper_g'] = None
    spec, _ = charts.build({'ref': 'T1', 'y': 'g_forecast'}, res, [('T1', 'get_forecast', {})])
    assert not spec.band                                              # thiếu một cận: không vẽ khoảng


# --- từ chối ---

_ROWS = [{'period': '01/2023', 'year': 2023, 'g_forecast': 1.0, 'cogs_forecast': 0.9, 'cogs_ratio': 0.9,
          'candidate_label': 'x', 'is_partial': False},
         {'period': '02/2023', 'year': 2023, 'g_forecast': 2.0, 'cogs_forecast': 1.8, 'cogs_ratio': 0.9,
          'candidate_label': 'x', 'is_partial': False}]


@pytest.mark.parametrize('args,results,calls_,why', [
    ({'ref': 'T2', 'y': 'g_forecast'}, {'T1': ToolResult('ok', 'x', rows=_ROWS)}, [('T1', 'get_forecast', {})],
     'không phải kết quả tool của lượt này'),
    ({'ref': 'T1', 'y': 'g_forecast'}, {'T1': ToolResult('no_data', 'x')}, [('T1', 'get_forecast', {})], 'no_data'),
    # tool không có trục x (get_revenue_summary vẽ được từ 2026-10-17 khi có to_year, nên ca này đổi sang get_revenue_gap)
    ({'ref': 'T1', 'y': 'r'}, {'T1': ToolResult('ok', 'x', rows=[{'year': 2019, 'r': 1}, {'year': 2020, 'r': 2}])},
     [('T1', 'get_revenue_gap', {})], 'không có dạng nhiều dòng'),
    ({'ref': 'T1', 'y': 'candidate_label'}, {'T1': ToolResult('ok', 'x', rows=_ROWS)}, [('T1', 'get_forecast', {})],
     'không phải cột số'),
    ({'ref': 'T1', 'y': 'year'}, {'T1': ToolResult('ok', 'x', rows=_ROWS)}, [('T1', 'get_forecast', {})],
     'không phải cột số'),
    ({'ref': 'T1', 'y': 'g_forecast', 'y2': 'cogs_ratio'}, {'T1': ToolResult('ok', 'x', rows=_ROWS)},
     [('T1', 'get_forecast', {})], 'khác đơn vị'),
    ({'ref': 'T1', 'y': 'g_forecast'}, {'T1': ToolResult('ok', 'x', rows=_ROWS[:1])}, [('T1', 'get_forecast', {})],
     'ít nhất 2'),
    ({'ref': 'T1', 'y': ['g_forecast']}, {'T1': ToolResult('ok', 'x', rows=_ROWS)}, [('T1', 'get_forecast', {})],
     'chỉ nhận'),
    ({'ref': 'T1', 'y': 'g_forecast', 'values': [1, 2]}, {'T1': ToolResult('ok', 'x', rows=_ROWS)},
     [('T1', 'get_forecast', {})], 'chỉ nhận'),                       # không có đường đưa số vào biểu đồ
])
def test_show_chart_tu_choi(args, results, calls_, why):
    spec, out = charts.build(args, results, calls_)
    assert spec is None and out.status == 'unsupported' and why in out.message, out.message


def test_show_chart_khong_tinh_vao_gioi_han_doc_kho_va_co_tran_rieng(versioned):
    m = dict(metric='G', period='month', year=2023)
    data = calls(*[('get_forecast', dict(m, month=k)) for k in (1, 2, 3)], ('get_forecast', HORIZON))
    chart = calls(*[('show_chart', {'ref': 'T4', 'y': 'g_forecast'})] * (charts.MAX_CHARTS + 1))
    ok = final(answer='Biểu đồ dưới đây là dự báo G từng tháng; tháng thấp nhất là {c1}.',
               claims=[{'id': 'c1', 'path': 'T4.derived.lowest_month.months'}])
    t = _turn('Vẽ dự báo G từng tháng', data, chart, ok)
    assert len(t.calls) == service.MAX_TOOL_CALLS and len(t.charts) == charts.MAX_CHARTS, t.chart_calls
    assert t.chart_calls[-1][1] == 'unsupported' and 'Đã đủ' in t.chart_calls[-1][2]


def test_show_chart_truoc_khi_co_du_lieu_bi_tu_choi(versioned):
    t = _turn('Vẽ dự báo G từng tháng', call('show_chart', ref='T1', y='g_forecast'), call('get_forecast', **HORIZON),
              OK_FC)
    assert t.status == 'ok' and t.charts == [] and t.chart_calls[0][1] == 'unsupported'


def test_prompt_va_schema_co_show_chart():
    p = service.system_prompt(dt.date(2026, 10, 16))
    assert 'show_chart(ref="T1"' in p and 'không ghép' in p
    assert charts.SCHEMA['input_schema']['additionalProperties'] is False
    assert set(charts.SCHEMA['input_schema']['properties']) == {'ref', 'y', 'y2'}


# --- trang chat (AppTest, chế độ cũ, tool PS5 nhiều dòng) ---

SEG = dict(metric='R', dimension='category', year=2022)
SEG_OK = final(answer='Biểu đồ dưới đây là R theo ngành hàng năm 2022; R toàn công ty là {c1}.',
               claims=[{'id': 'c1', 'path': 'T1.rows[0].r_total'}])


def _charts_on_page(at) -> int:
    return len(at.get('vega_lite_chart'))


def test_trang_chat_ve_bieu_do_va_rerun_khong_goi_lai_model(monkeypatch):
    fake = FakeProvider(calls(('get_segment_contribution', SEG), ('show_chart', {'ref': 'T1', 'y': 'r'})), SEG_OK)
    at = _app(monkeypatch, fake)
    at.chat_input[0].set_value('Vẽ R theo ngành hàng năm 2022').run()
    assert not at.exception and not at.error, at.exception
    assert _charts_on_page(at) == 1 and len(fake.seen) == 2
    assert any('Biểu đồ vẽ từ kết quả T1' in c.value for c in at.caption)
    at.run()                                                            # rerun: vẽ lại từ kết quả đã lưu
    assert _charts_on_page(at) == 1 and len(fake.seen) == 2


def test_trang_chat_khong_ve_khi_cau_tra_loi_chua_qua_kiem(monkeypatch):
    lie = final(answer='R toàn công ty năm 2022 là {c1}, khoảng 860 triệu.',      # tự viết số: bị chặn
                claims=[{'id': 'c1', 'path': 'T1.rows[0].r_total'}])
    fake = FakeProvider(calls(('get_segment_contribution', SEG), ('show_chart', {'ref': 'T1', 'y': 'r'})), lie, lie)
    at = _app(monkeypatch, fake)
    at.chat_input[0].set_value('Vẽ R theo ngành hàng năm 2022').run()
    assert not at.exception
    t = at.session_state.ai_turns[0]
    assert t.status != 'ok' and len(t.charts) == 1                     # spec có nhưng không vẽ
    assert _charts_on_page(at) == 0


def test_bieu_do_mua_vu_nhan_giai_doan_va_la_cot(monkeypatch):
    t = _turn('Vẽ tỷ lệ mùa vụ theo giai đoạn', call('get_calendar_pattern', pattern='mua_vu'),
              call('show_chart', ref='T1', y='season_peak_trough_ratio'),
              final(answer='Biểu đồ dưới đây là tỷ lệ mùa vụ cả kỳ và theo từng giai đoạn.'))
    assert t.status == 'ok', t.validation_errors
    spec = t.charts[0]
    df = charts.frame(spec, t.results)
    assert spec.kind == 'bar' and list(df['x']) == ['2013–2022', 'Giai đoạn A (2013–2016)', 'Giai đoạn B (2017–2018)',
                                                    'Giai đoạn C (2019)', 'Giai đoạn D (2020–2022)']
    assert list(df['gia_tri']) == [r['season_peak_trough_ratio'] for r in t.results['T1'].rows]
