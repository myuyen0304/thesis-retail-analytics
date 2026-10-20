"""Sửa sau eval B6 (2026-10-17): chuỗi R / G từng năm, ghi chú do app gắn, tên chỉ tiêu chênh mùa. Mô hình giả, không gọi API.

- get_revenue_summary year → to_year: mỗi năm một dòng, số khớp CSV (đối chứng độc lập của test_ai_tools), vẽ được thành
  đường; năm thiếu tháng (2012) không vào xếp hạng, không vẽ.
- ToolResult.notes: app tự in "đóng góp số học, không phải nguyên nhân" dưới R theo nhóm (live B6 V03) và ghi chú
  "theo sai số tháng model khác sai ít hơn" dưới dự báo tháng / năm (đối chứng bằng parquet backtest của stage). Ghi chú
  không gửi cho mô hình.
- Live B6 V05: "tỷ lệ tháng cao nhất so với tháng thấp nhất" là tên chỉ tiêu, không phải câu xếp hạng.
"""
import json

import pytest

from ai_explain import charts, service, tools
from ai_explain.contracts import ToolCall
from tests.test_ai_charts import calls
from tests.test_ai_chat import FakeProvider, _app, call, final
from tests.test_ai_forecast import ref, versioned          # noqa: F401 (fixture)
from tests.test_ai_tools import _money, src                # noqa: F401 (fixture: số đối chứng từ CSV)


def _run(tool, **a):
    return tools.run(ToolCall(tool, a), 'duckdb')


def _turn(q, *steps):
    return service.run_turn(q, [], 'duckdb', FakeProvider(*steps))


# --- chuỗi R / G từng năm ---

def test_chuoi_tung_nam_khop_csv(src):
    r = _run('get_revenue_summary', metric='R_and_G', year=2012, to_year=2022)
    assert r.status == 'ok', r.message
    assert [x['year'] for x in r.rows] == list(range(2012, 2023))
    for x in r.rows:
        assert x['r'] == _money(src['year'][x['year']]['r_c']) and x['g'] == _money(src['year'][x['year']]['g_c'])
        assert x['is_analysis_period'] is (x['year'] >= 2013)
    # xếp hạng trên các năm ĐỦ tháng, tính lại từ CSV
    full = {y: src['year'][y] for y in range(2013, 2023)}
    for col, key in (('r', 'r_c'), ('g', 'g_c')):
        hi = max(full, key=lambda y: full[y][key])
        lo = min(full, key=lambda y: full[y][key])
        assert r.derived[f'highest_{col}'] == {'years': [str(hi)], col: _money(full[hi][key])}
        assert r.derived[f'lowest_{col}'] == {'years': [str(lo)], col: _money(full[lo][key])}
    assert r.derived['n_years'] == 11 and '2012 thiếu tháng' in r.message
    assert r.evidence.filters_applied == {'year': 2012, 'to_year': 2022}


def test_chuoi_tung_nam_so_nam_truoc_bang_tung_lan_goi_mot_nam():
    r = _run('get_revenue_summary', metric='R', year=2014, to_year=2022, compare_prior_year=True)
    assert r.status == 'ok' and len(r.rows) == 9
    for x in r.rows:
        one = _run('get_revenue_summary', metric='R', year=x['year'], compare_prior_year=True).rows[0]
        assert {k: x[k] for k in one} == one


@pytest.mark.parametrize('a,status', [
    (dict(metric='R', year=2019, to_year=2019), 'unsupported'),          # một năm thì bỏ to_year
    (dict(metric='R', year=2020, to_year=2015), 'unsupported'),
    (dict(metric='R', year=2019, to_year=2023), 'no_data'),               # năm cuối ngoài dữ liệu thực tế
    (dict(metric='R', year=2013, to_year=2016, compare_prior_year=True), 'unsupported'),     # 2013 không có năm gốc
    (dict(metric='G', year=2015, to_year=2018, compare_prior_year=True), 'unsupported'),
])
def test_chuoi_tung_nam_tu_choi(a, status):
    r = _run('get_revenue_summary', **a)
    assert r.status == status and not r.rows, (r.status, r.message)


def test_dong_chuoi_nam_trong_catalog_thi_chan_truoc_khi_mo_ket_noi(monkeypatch):
    from ai_explain import metric_catalog
    monkeypatch.setattr(metric_catalog, 'CAPABILITIES', [
        (*c[:5], 'closed', c[6]) if c[:3] == ('get_revenue_summary', 'R', 'years') else c
        for c in metric_catalog.CAPABILITIES])
    with monkeypatch.context() as m:
        m.setattr(tools, 'open_session', lambda *a, **kw: pytest.fail('Không được mở kết nối'))
        r = _run('get_revenue_summary', metric='R', year=2015, to_year=2019)
        assert r.status == 'unsupported' and 'years' in r.rejected['capability']
    assert _run('get_revenue_summary', metric='R', year=2019).ok                     # một năm vẫn mở


def test_mot_nam_khong_doi():
    r = _run('get_revenue_summary', metric='R', year=2019)
    assert r.status == 'ok' and len(r.rows) == 1 and not r.derived
    assert r.evidence.queries[-1].sql.endswith('where year = ?')            # SQL một năm như trước


def test_schema_co_to_year():
    s = next(x for x in service.chat_schemas() if x['function']['name'] == 'get_revenue_summary')
    assert s['function']['parameters']['properties']['to_year']['type'] == 'integer'
    assert 'to_year' not in s['function']['parameters']['required']


SERIES = dict(metric='R', year=2012, to_year=2022)
SERIES_OK = final(answer='Biểu đồ dưới đây là R từng năm; năm R cao nhất là {c1} với {c2}.',
                  claims=[{'id': 'c1', 'path': 'T1.derived.highest_r.years'},
                          {'id': 'c2', 'path': 'T1.derived.highest_r.r'}])


def test_bieu_do_chuoi_nam_dung_bang_chung(src):
    t = _turn('Vẽ R theo từng năm từ 2012 đến 2022',
              calls(('get_revenue_summary', SERIES), ('show_chart', {'ref': 'T1', 'y': 'r'})), SERIES_OK)
    assert t.status == 'ok', t.validation_errors
    spec = t.charts[0]
    assert spec.kind == 'line' and spec.n_points == 10 and spec.excluded == ('2012 (năm thiếu tháng)',)
    df = charts.frame(spec, t.results)
    assert list(df['x']) == [str(y) for y in range(2013, 2023)]
    assert list(df['gia_tri']) == [float(_money(src['year'][y]['r_c'])) for y in range(2013, 2023)]
    hi = max(range(2013, 2023), key=lambda y: src['year'][y]['r_c'])
    assert f'năm R cao nhất là **{hi}**' in t.answer_md


@pytest.mark.parametrize('answer,paths,ok', [
    ('R năm 2017 là {c1}.', ['rows[5].r'], True),                  # năm giữa khoảng, câu ghi đúng năm của số
    ('R năm 2019 là {c1}.', ['rows[5].r'], False),                 # số của 2017 gán cho 2019
    ('R năm 2017 là {c1}.', ['rows[2017].r'], True),               # chọn dòng theo năm (live bộ N: rows[2016])
    ('R năm 2019 là {c1}.', ['rows[2017].r'], False),
    ('Năm R cao nhất là 2017.', [], False),                       # xếp hạng không dẫn ô xếp hạng
    # live bộ N02 (2026-10-17): câu xếp hạng phải dẫn derived.highest_r; rows[<năm>] không chứng minh "cao nhất"
    ('Trong giai đoạn 2013–2022, năm có R cao nhất là {c1}, với R đạt {c2}.',
     ['derived.highest_r.years', 'derived.highest_r.r'], True),
    ('Trong giai đoạn 2013–2022, năm có R cao nhất là {c1}, với R đạt {c2}.', ['rows[2016].year', 'rows[2016].r'], False),
])
def test_chuoi_nam_cau_dan_so(answer, paths, ok):
    claims = [{'id': f'c{i}', 'path': f'T1.{x}'} for i, x in enumerate(paths, 1)]
    rep = final(answer=answer, claims=claims)
    t = _turn('R từng năm từ 2012 đến 2022 thế nào?', call('get_revenue_summary', **SERIES), rep, rep)
    assert (t.status == 'ok') == ok, (answer, t.status, t.validation_errors)


def test_chon_dong_theo_nam_chi_khi_dung_mot_dong():
    from ai_explain import evidence
    t = _turn('R từng năm từ 2012 đến 2022 thế nào?', call('get_revenue_summary', **SERIES),
              final(answer='R năm 2016 là {c1}.', claims=[{'id': 'c1', 'path': 'T1.rows[2016].r'}]))
    assert t.status == 'ok' and t.values['c1'][1] == next(r['r'] for r in t.results['T1'].rows if r['year'] == 2016)
    seg = _run('get_segment_contribution', metric='R', dimension='region', year=2019)       # mọi dòng cùng năm 2019
    with pytest.raises(ValueError):
        evidence._resolve('T1.rows[2019].r', {'T1': seg})


# --- V05: tên chỉ tiêu chênh mùa không phải câu xếp hạng (4 câu trả lời live 2026-10-16, nguyên chữ) ---

V05_LIVE = [
    ('Biểu đồ dưới đây thể hiện tỷ lệ tháng cao nhất so với tháng thấp nhất (chênh mùa) của từng giai đoạn và cả kỳ. Cả '
     'kỳ 2013–2022, tháng cao nhất là tháng {c1} và tháng thấp nhất là tháng {c2}, chênh mùa là {c3}. Xét theo giai đoạn, '
     'chênh mùa của giai đoạn Tăng trưởng là {c4}, giai đoạn Chững, giảm nhẹ là {c5}, giai đoạn Sập là {c6}, giai đoạn Đi '
     'ngang mức thấp là {c7}. Cả {c8} giai đoạn đều có cùng tháng cao nhất và cùng tháng thấp nhất với cả kỳ. Lưu ý: số '
     'theo giai đoạn dùng cách gom năm đề xuất, đang chờ BA chốt.',
     ['rows[0].peak_month', 'rows[0].trough_month', 'rows[0].season_peak_trough_ratio', 'rows[A].season_peak_trough_ratio',
      'rows[B].season_peak_trough_ratio', 'rows[C].season_peak_trough_ratio', 'rows[D].season_peak_trough_ratio',
      'derived.n_phases_same_peak']),
    ('Biểu đồ dưới đây thể hiện tỷ lệ tháng cao nhất so với tháng thấp nhất (chênh mùa) của từng giai đoạn và cả kỳ. Cả '
     'kỳ 2013–2022, tháng cao nhất là tháng {c1} và tháng thấp nhất là tháng {c2}, chênh mùa là {c3}. Cả {c4} giai đoạn '
     'đều có cùng tháng cao nhất và cùng tháng thấp nhất với cả kỳ. Lưu ý số theo giai đoạn dùng cách gom năm đề xuất, '
     'đang chờ BA chốt.',
     ['rows[0].peak_month', 'rows[0].trough_month', 'rows[0].season_peak_trough_ratio', 'derived.n_phases_same_peak']),
    ('Biểu đồ dưới đây thể hiện chênh mùa (tháng cao nhất so với tháng thấp nhất) của từng giai đoạn và cả kỳ. Cả kỳ '
     '2013–2022, tháng cao nhất là tháng {c1} và tháng thấp nhất là tháng {c2}, chênh mùa là {c3}. Số giai đoạn có cùng '
     'tháng cao nhất với cả kỳ là {c4}, và số giai đoạn có cùng tháng thấp nhất với cả kỳ là {c5}. Lưu ý số theo giai '
     'đoạn dùng cách gom năm đề xuất, đang chờ BA chốt.',
     ['rows[0].peak_month', 'rows[0].trough_month', 'rows[0].season_peak_trough_ratio', 'derived.n_phases_same_peak',
      'derived.n_phases_same_trough']),
    ('Đã vẽ biểu đồ chênh mùa (tỷ lệ tháng cao nhất so với tháng thấp nhất) cho cả kỳ và {c1} giai đoạn. Cả kỳ 2013–2022, '
     'tháng cao nhất là tháng {c2} và tháng thấp nhất là tháng {c3}, tỷ lệ chênh mùa là {c4}. Số giai đoạn có cùng tháng '
     'cao nhất với cả kỳ là {c5}, cùng tháng thấp nhất là {c6}. Lưu ý: số theo giai đoạn dùng cách gom năm đề xuất, đang '
     'chờ BA chốt.',
     ['derived.n_phases', 'rows[0].peak_month', 'rows[0].trough_month', 'rows[0].season_peak_trough_ratio',
      'derived.n_phases_same_peak', 'derived.n_phases_same_trough']),
]
V05_Q = 'Vẽ biểu đồ mùa vụ: tỷ lệ tháng cao nhất so với tháng thấp nhất qua các giai đoạn'


def _claims(paths):
    return [{'id': f'c{i}', 'path': f'T1.{p}'} for i, p in enumerate(paths, 1)]


@pytest.mark.parametrize('answer,paths', V05_LIVE)
def test_v05_ten_chi_tieu_chenh_mua_khong_bi_chan(answer, paths):
    rep = final(answer=answer, claims=_claims(paths))
    t = _turn(V05_Q, call('get_calendar_pattern', pattern='mua_vu'), rep, rep)
    assert t.status == 'ok', t.validation_errors


@pytest.mark.parametrize('answer', [
    'Giai đoạn có chênh mùa (tháng cao nhất so với tháng thấp nhất) lớn nhất là giai đoạn A.',   # xếp hạng thật
    'Tháng cao nhất là tháng 5.',
    'Giai đoạn A có tỷ lệ cao nhất so với thấp nhất mạnh nhất.',
])
def test_v05_cau_xep_hang_that_van_bi_chan(answer):
    rep = final(answer=answer, claims=[])
    t = _turn(V05_Q, call('get_calendar_pattern', pattern='mua_vu'), rep, rep)
    assert t.status != 'ok', t.answer_md


# --- ghi chú app ---

SEG = dict(metric='R', dimension='acquisition_channel', year=2019)
SEG_OK = final(answer='Kênh kéo giảm nhiều nhất là {c1}.', claims=[{'id': 'c1', 'path': 'T1.derived.largest_decrease.groups'}])


def test_v03_dong_gop_nhom_co_ghi_chu_app_khong_gui_mo_hinh():
    t = _turn('Vẽ biểu đồ đóng góp của từng kênh vào thay đổi R năm 2019',
              calls(('get_segment_contribution', SEG), ('show_chart', {'ref': 'T1', 'y': 'delta_r'})), SEG_OK)
    assert t.status == 'ok', t.validation_errors
    assert t.app_notes == [tools.SEGMENT_NOTE] and 'không chứng minh nguyên nhân' in tools.SEGMENT_NOTE
    payload = service.tool_payload('T1', t.results['T1'])
    assert tools.SEGMENT_NOTE not in payload and 'notes' not in json.loads(payload)


def test_v03_trang_chat_in_ghi_chu(monkeypatch):
    fake = FakeProvider(calls(('get_segment_contribution', SEG), ('show_chart', {'ref': 'T1', 'y': 'delta_r'})), SEG_OK)
    at = _app(monkeypatch, fake)
    at.chat_input[0].set_value('Vẽ biểu đồ đóng góp của từng kênh vào thay đổi R năm 2019').run()
    assert not at.exception, at.exception
    assert any(tools.SEGMENT_NOTE in c.value for c in at.caption)


def _best_month_models(bt):
    """Đối chứng độc lập: MAPE G tháng trung bình 3 fold của từng model ứng viên, từ parquet backtest của stage."""
    x = bt[(bt.role == 'candidate') & (bt.metric == 'mape_g_thang') & (bt.grain == 'thang')]
    m = x.groupby(['model', 'cogs_method']).value.mean().groupby('model').min()
    return m, sorted(m[m == m.min()].index)


@pytest.mark.parametrize('a', [dict(metric='G', period='month', year=2023, month=8),
                               dict(metric='G', period='year', year=2023),
                               dict(metric='G_and_COGS', period='horizon')])
def test_du_bao_thang_nam_co_ghi_chu_thuoc_thang(versioned, ref, a):
    _, daily, bt = ref
    by, best = _best_month_models(bt)
    prim = daily[daily.is_primary].model.iloc[0]
    r = _run('get_forecast', **a)
    assert r.status == 'ok'
    if prim in best:
        assert r.notes == []
        return
    assert len(r.notes) == 1
    note = r.notes[0]
    assert all(tools.MODEL_LABEL[m] in note for m in best) and tools.MODEL_LABEL[prim] not in note
    assert f'{by[best[0]]:.1f}'.replace('.', ',') + '%' in note and f'{by[prim]:.1f}'.replace('.', ',') + '%' in note
    assert 'điểm ngày' in note


@pytest.mark.parametrize('a', [dict(metric='G', period='day', year=2023, month=8, day=15),       # theo ngày: khoảng 80%
                               dict(metric='COGS', period='month', year=2023, month=8),         # MAPE G tháng là của G
                               dict(metric='G', period='month', year=2023, month=8, model='sarimax_full')])
def test_du_bao_khong_ghi_chu_thuoc_thang(versioned, a):
    r = _run('get_forecast', **a)
    assert r.status == 'ok' and r.notes == [], (r.status, r.message, r.notes)


def test_ghi_chu_thuoc_thang_khong_co_khi_model_chinh_cung_thap_nhat(monkeypatch):
    rows = [{'model': 'lgbm_full', 'cogs_method': 'direct', 'value': 8.0, 'n': 3},
            {'model': 'sarimax_full', 'cogs_method': 'direct', 'value': 9.0, 'n': 3}]
    monkeypatch.setattr(tools, '_ffetch', lambda *a, **k: rows)
    assert tools._month_metric_note(None, {'model': 'lgbm_full'}) == []
    rows[0]['value'] = 10.0
    assert 'log + SARIMAX, train toàn chuỗi' in tools._month_metric_note(None, {'model': 'lgbm_full'})[0]
    rows[1]['n'] = 2                                         # thiếu fold: không so
    assert tools._month_metric_note(None, {'model': 'lgbm_full'}) == []


def test_tran_token_xau_nhat_con_du():
    """3 câu xấu nhất (test_tran_token_cung_ca_phien_khong_vuot_200k) vẫn vừa hạn mức phiên. Hạn mức 200k cũ hết chỗ khi
    B4b thêm tool explain_forecast (mỗi lượt xấu nhất ~71,9 nghìn token); PM nâng lên 500k ngày 2026-10-19."""
    from tests.test_ai_chat import WorstCaseProvider
    assert service.SESSION_TOKEN_LIMIT == 500_000
    p, used = WorstCaseProvider(), 0
    for _ in range(3):
        t = service.run_turn('Vì sao R năm 2019 giảm?', [], 'duckdb', p, session_tokens_used=used)
        assert t.status == 'ok'
        used += t.tokens
    assert service.SESSION_TOKEN_LIMIT - used >= 1000, used
