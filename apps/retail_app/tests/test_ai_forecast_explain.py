"""B4b: đối chứng SQL trực tiếp với bản dữ liệu và kiểm đường guard/answer, không gọi LLM thật."""
import datetime as dt
import json
import math
import os

import duckdb
import pytest

from ai_explain import evidence, service, tools
from ai_explain.contracts import ToolCall
from ai_explain.provider import Reply
from dwh import releases
from dwh.connection import ROOT
from tests.test_ai_chat import FakeProvider, call, final


DOCKER_STATE = ROOT / 'warehouse/pipeline/docker/state.json'
OLD_STATE = ROOT / 'warehouse/pipeline/state.json'
ARGS_DAY = {'period': 'day', 'year': 2023, 'month': 8, 'day': 15}
ARGS_MONTH = {'period': 'month', 'year': 2023, 'month': 8}


@pytest.fixture
def published(monkeypatch):
    if not DOCKER_STATE.exists():
        pytest.skip('chưa có bản pipeline Docker chứa bảng phân rã')
    state = json.loads(DOCKER_STATE.read_text(encoding='utf-8'))['payload']
    rec = releases.choose(state)
    path = (DOCKER_STATE.parent / rec['artifact_path']).resolve()
    if not path.exists():
        pytest.skip('artifact của bản đang phục vụ chưa có trên máy')
    with duckdb.connect(str(path), read_only=True) as con:
        present = con.execute('select count(*) from information_schema.tables where table_schema = ? '
                              "and table_name = 'rpt_forecast_explain'", [rec['schema']]).fetchone()[0]
    if not present:
        pytest.skip('bản đang phục vụ chưa có bảng phân rã')
    monkeypatch.setenv('RETAIL_RELEASE_MODE', 'versioned')
    monkeypatch.setenv('RETAIL_RELEASE_STATE', str(DOCKER_STATE))
    releases.reset()
    yield rec, path
    releases.reset()


@pytest.mark.parametrize('args,start,end', [
    (ARGS_DAY, dt.date(2023, 8, 15), dt.date(2023, 8, 15)),
    (ARGS_MONTH, dt.date(2023, 8, 1), dt.date(2023, 8, 31)),
])
def test_tool_khop_query_doi_chung_doc_lap(published, args, start, end):
    rec, path = published
    result = tools.run(ToolCall('explain_forecast', args), 'duckdb')
    assert result.status == 'ok', result.message
    with duckdb.connect(str(path), read_only=True) as con:
        schema = rec['schema']  # đã qua releases.checked, không lấy từ LLM
        primary = con.execute(f'select distinct model, cogs_method from {schema}.rpt_forecast_daily '
                              'where is_primary').fetchone()
        # Query đối chứng tách khỏi SQL trong tool: lọc theo ngày trước, sau đó tính trung bình theo nhóm.
        rows = con.execute(f'select feature_group, sum(contribution_log) / count(*) as mean_log, '
                           f'count(*) as n from {schema}.rpt_forecast_explain '
                           'where forecast_date between ? and ? and model = ? and cogs_method = ? '
                           'group by feature_group', [start, end, *primary]).fetchall()
        base, target = con.execute(f'select avg(base_log), avg(forecast_log) '
                                   f'from (select distinct forecast_date, base_log, forecast_log '
                                   f'from {schema}.rpt_forecast_explain '
                                   'where forecast_date between ? and ?)', [start, end]).fetchone()
    expected = {g: (c, n) for g, c, n in rows}
    assert len(expected) == 10 and len(result.rows) == 10
    assert result.evidence.data_version['release_id'] == rec['release_id']
    assert any('rpt_forecast_explain' in q.source for q in result.evidence.queries)
    for row in result.rows:
        value, n = expected[row['feature_group']]
        assert row['contribution_log'] == pytest.approx(value, abs=1e-10)
        assert row['n_days'] == n
    assert result.derived['base_log'] == pytest.approx(base, abs=1e-10)
    assert result.derived['forecast_log'] == pytest.approx(target, abs=1e-10)
    assert base + sum(x['contribution_log'] for x in result.rows) == pytest.approx(target, abs=1e-7)
    assert result.notes == [tools.EXPLAIN_LABEL]


@pytest.mark.skipif(os.environ.get('RETAIL_TEST_DATABRICKS') != '1',
                    reason='đặt RETAIL_TEST_DATABRICKS=1 để đối chứng trên cloud')
@pytest.mark.parametrize('args,start,end', [
    (ARGS_DAY, dt.date(2023, 8, 15), dt.date(2023, 8, 15)),
    (ARGS_MONTH, dt.date(2023, 8, 1), dt.date(2023, 8, 31)),
])
def test_cloud_tool_khop_query_doc_lap_cua_release_dang_phuc_vu(monkeypatch, args, start, end):
    """SP AI đọc SQL độc lập; đối chứng với tool trên cùng release mà registry đang phục vụ."""
    from databricks import sql as dbsql
    from databricks.sdk.core import Config

    from dwh.connection import databricks_config
    from dwh.guarded import ai_databricks_principal

    monkeypatch.setenv('RETAIL_RELEASE_MODE', 'versioned')
    cfg = databricks_config()
    client_id, secret = ai_databricks_principal()
    assert client_id and secret and cfg.get('DATABRICKS_HOST') and cfg.get('DATABRICKS_WAREHOUSE_ID')
    auth = Config(host=cfg['DATABRICKS_HOST'], client_id=client_id, client_secret=secret, auth_type='oauth-m2m')
    token = auth.authenticate()['Authorization'].removeprefix('Bearer ')
    conn = dbsql.connect(server_hostname=auth.host.removeprefix('https://').rstrip('/'),
                         http_path=f"/sql/1.0/warehouses/{cfg['DATABRICKS_WAREHOUSE_ID']}", access_token=token,
                         catalog=cfg.get('RETAIL_DATABRICKS_CATALOG', 'retail_lab'))
    cur = conn.cursor()
    try:
        cur.execute("select payload from retail_control.state where name = 'main'")
        state = json.loads(cur.fetchone()[0])
        rec = releases.choose(state)
        schema = rec['schema']  # releases.choose đã kiểm tên schema từ registry
        cur.execute(f'select distinct model, cogs_method from {schema}.rpt_forecast_daily where is_primary')
        primary = cur.fetchone()
        assert primary == ('lgbm_full', 'direct')
        cur.execute(f'select feature_group, sum(contribution_log) / count(*), count(*) '
                    f'from {schema}.rpt_forecast_explain '
                    'where forecast_date between ? and ? and model = ? and cogs_method = ? '
                    'group by feature_group', [start, end, *primary])
        expected = {g: (float(value), count) for g, value, count in cur.fetchall()}
        result = tools.run(ToolCall('explain_forecast', args), 'databricks')
        cur.execute("select payload from retail_control.state where name = 'main'")
        assert releases.choose(json.loads(cur.fetchone()[0]))['release_id'] == rec['release_id']
    finally:
        cur.close()
        conn.close()
    assert result.status == 'ok', result.message
    assert result.evidence.data_version['release_id'] == rec['release_id']
    assert len(expected) == len(result.rows) == 10
    for row in result.rows:
        value, count = expected[row['feature_group']]
        assert row['contribution_log'] == pytest.approx(value, abs=1e-10)
        assert row['n_days'] == count
    assert any(schema + '.rpt_forecast_explain' == q.source for q in result.evidence.queries)


def test_tham_so_va_ngoai_horizon_khong_tra_so(published):
    for args, status in [
        ({'period': 'month', 'year': 2025, 'month': 8}, 'no_data'),
        ({'period': 'month', 'year': 2023, 'month': 13}, 'unsupported'),
        ({'period': 'day', 'year': 2023, 'month': 2, 'day': 30}, 'unsupported'),
        ({**ARGS_MONTH, 'model': 'sarimax_full'}, 'unsupported'),
    ]:
        result = tools.run(ToolCall('explain_forecast', args), 'duckdb')
        assert result.status == status, result.message
        assert not result.rows
    partial = tools.run(ToolCall('explain_forecast', {'period': 'month', 'year': 2024, 'month': 7}), 'duckdb')
    assert partial.status == 'ok' and all(r['n_days'] == 1 and r['is_partial'] for r in partial.rows)
    assert 'không đại diện cả tháng' in partial.message


@pytest.mark.parametrize('versioned', [False, True])
def test_ban_cu_va_legacy_khong_muo_n_so_khac(monkeypatch, versioned):
    if versioned:
        if not OLD_STATE.exists():
            pytest.skip('chưa có registry của bản cũ')
        monkeypatch.setenv('RETAIL_RELEASE_MODE', 'versioned')
        monkeypatch.setenv('RETAIL_RELEASE_STATE', str(OLD_STATE))
    else:
        monkeypatch.delenv('RETAIL_RELEASE_MODE', raising=False)
    releases.reset()
    result = tools.run(ToolCall('explain_forecast', ARGS_MONTH), 'duckdb')
    assert result.status == 'no_data' and not result.rows and not result.derived
    assert 'không lấy số' in result.message
    ps = tools.run(ToolCall('get_revenue_summary', {'metric': 'R', 'year': 2019}), 'duckdb')
    assert ps.status == 'ok', ps.message
    releases.reset()


def test_guard_tuy_chon_khong_khoa_ban_cu(monkeypatch):
    from dwh import guarded
    from tests.test_ai_forecast import _Cur, _grants

    monkeypatch.delenv('RETAIL_RELEASE_MODE', raising=False)
    allowed, required = guarded._release_scope(_Cur(), tools.ALLOWED_RELATIONS, 'retail_lab',
                                               tools.OPTIONAL_RELATIONS)
    assert 'reporting.rpt_forecast_explain' in allowed - required
    assert not guarded._dbx_violations('ai', 'ai', _grants(tools.ALLOWED_RELATIONS), [], allowed,
                                       'retail_lab', required)
    rid = 'a' * 24
    rec = {'release_id': rid, 'status': 'ready', 'schema': f'r_{rid}_reporting'}

    class Cur(_Cur):
        def execute(self, sql, params=None):
            self._r = [(json.dumps({'active': rid, 'releases': {rid: rec}}),)]

        def fetchall(self):
            return self._r

    monkeypatch.setenv('RETAIL_RELEASE_MODE', 'versioned')
    allowed, required = guarded._release_scope(Cur(), tools.ALLOWED_RELATIONS, 'retail_lab',
                                               tools.OPTIONAL_RELATIONS)
    assert f'r_{rid}_reporting.rpt_forecast_explain' in allowed - required


def test_evidence_va_nhan_app_khong_do_model_viet(published):
    answer = 'Trong model, nhóm năm chẵn/lẻ góp {c1} vào log(G) dự báo.'
    claim = [{'id': 'c1', 'path': 'T1.rows[nam_chan_le].contribution_log'}]
    turn = service.run_turn('Vì sao tháng 8/2023 dự báo giảm?', [], 'duckdb', FakeProvider(
        call('explain_forecast', **ARGS_MONTH), final(answer=answer, claims=claim)))
    assert turn.status == 'ok', turn.validation_errors
    assert turn.app_notes == [tools.EXPLAIN_LABEL]
    assert tools.EXPLAIN_LABEL not in turn.raw_final
    assert 'log' in turn.answer_md
    bad = final(answer='Khuyến mãi khiến G đổi {c1}.', claims=claim)
    blocked = service.run_turn('Vì sao tháng 8/2023 dự báo giảm?', [], 'duckdb', FakeProvider(
        call('explain_forecast', **ARGS_MONTH), bad, bad))
    assert blocked.status == 'answer_validation_failed'
    assert any('nguyên nhân' in x for x in blocked.validation_errors)
    odd = final(answer='Do năm lẻ, G đổi {c1}.', claims=claim)
    blocked_odd = service.run_turn('Vì sao tháng 8/2023 dự báo giảm?', [], 'duckdb', FakeProvider(
        call('explain_forecast', **ARGS_MONTH), odd, odd))
    assert blocked_odd.status == 'answer_validation_failed'
    assert any('nguyên nhân' in x for x in blocked_odd.validation_errors)
    fake = {'T1': turn.results['T1']}
    assert evidence._resolve('T1.rows[nam_chan_le].contribution_log', fake)[0] is not None


def test_b5b2_cau_yeu_to_chinh_la_gi_dung_explain_forecast(published):
    answer = final(answer='Theo phân rã model tháng 8/2023, nhóm năm chẵn/lẻ góp {c1} vào log(G).',
                   claims=[{'id': 'c1', 'path': 'T1.rows[nam_chan_le].contribution_log'}])
    t = service.run_turn('Vì sao dự báo G tháng 8/2023 thấp, yếu tố chính là gì?', [], 'duckdb',
                         FakeProvider(call('explain_forecast', **ARGS_MONTH), answer))
    assert t.status == 'ok', t.validation_errors
    assert [name for _, name, _ in t.calls] == ['explain_forecast']


def test_b5b2_model_chinh_la_gi_dung_backtest(published):
    answer = final(answer='Theo backtest, model chính là {c1}.',
                   claims=[{'id': 'c1', 'path': 'T1.derived.primary.label'}])
    t = service.run_turn('Model dự báo chính là gì?', [], 'duckdb',
                         FakeProvider(call('get_forecast_backtest'), answer))
    assert t.status == 'ok', t.validation_errors
    assert [name for _, name, _ in t.calls] == ['get_forecast_backtest']


def test_evidence_chan_phan_ra_sai_ky(published):
    claim = [{'id': 'c1', 'path': 'T1.rows[nam_chan_le].contribution_log'}]
    answer = final(answer='Phân rã G tháng 8/2023: năm chẵn/lẻ góp {c1}.', claims=claim)
    turn = service.run_turn('Phân rã dự báo G tháng 8/2023?', [], 'duckdb', FakeProvider(
        call('explain_forecast', period='month', year=2023, month=9), answer, answer))
    assert turn.status == 'answer_validation_failed'
    assert any('khác kỳ' in e for e in turn.validation_errors)


def test_evidence_khong_lay_mot_nhom_lam_cac_nhom_khac(published):
    claim = [{'id': 'c1', 'path': 'T1.rows[promo_year_end_sale].contribution_log'}]
    wrong = final(answer='Các chương trình khuyến mãi khác góp {c1}.', claims=claim)
    turn = service.run_turn('Phân rã dự báo G tháng 8/2023?', [], 'duckdb', FakeProvider(
        call('explain_forecast', **ARGS_MONTH), wrong, wrong))
    assert turn.status == 'answer_validation_failed'
    assert any('một nhóm' in e for e in turn.validation_errors)
    claims = [{'id': 'c1', 'path': 'T1.rows[mua_vu].contribution_log'},
              {'id': 'c2', 'path': 'T1.rows[nam_chan_le].contribution_log'}]
    wrong_direction = final(answer='Các nhóm còn lại góp dương: mùa vụ {c1}, năm chẵn/lẻ {c2}.', claims=claims)
    direction = service.run_turn('Phân rã dự báo G tháng 8/2023?', [], 'duckdb', FakeProvider(
        call('explain_forecast', **ARGS_MONTH), wrong_direction, wrong_direction))
    assert direction.status == 'answer_validation_failed'
    assert any('cùng một chiều' in e for e in direction.validation_errors)


# --- Rà S7: các nhánh "không đối soát được thì không trả số", bằng dữ liệu giả (không cần bản Docker) ---

TRAINED = dt.date(2022, 12, 31)
GROUPS = sorted(tools.EXPLAIN_GROUPS)


def _fake_tables(monkeypatch, *, primary='lgbm_full', groups=None, target_shift=0.0, daily_shift=0.0, daily_n=1,
                 bad=None, contrib_override=None, days=1):
    """Bảng giả cho ngày 15/08/2023: base 14 + Σ đóng góp = forecast_log. `bad` = (nhóm, cột, giá trị) làm hỏng một ô."""
    contrib = {g: 0.01 * (i - 4) for i, g in enumerate(GROUPS)}
    if contrib_override is not None:
        contrib.update(contrib_override)
    base = 14.0
    target = base + sum(contrib.values())
    cands = [{'model': primary, 'cogs_method': 'direct', 'is_primary': True, 'selection_step': 1, 'model_version': 'v1',
              'trained_through': TRAINED, 'run_id': 'r1', 'interval_level': 0.8, 'n_days': 548,
              'first_date': dt.date(2023, 1, 1), 'last_date': dt.date(2024, 7, 1)}]

    def explain_row(g):
        r = {'feature_group': g, 'n': days, 'n_dates': days, 'min_groups': 10, 'max_groups': 10, 'min_version': 'v1',
             'max_version': 'v1', 'min_run': 'r1', 'max_run': 'r1', 'min_trained': TRAINED, 'max_trained': TRAINED,
             'base_log': base, 'contribution_log': contrib[g], 'forecast_log': target + target_shift}
        if bad and bad[0] == g:
            r[bad[1]] = bad[2]
        return r

    def fake(turn, source, sql, params=()):
        if source == 'reporting.rpt_forecast_explain':
            return [explain_row(g) for g in (groups if groups is not None else GROUPS)]
        if 'ln(yhat)' in sql:
            return [{'n': daily_n, 'forecast_log': target + daily_shift}]
        return cands

    monkeypatch.setattr(tools, '_ffetch', fake)
    return contrib


def test_du_lieu_gia_hop_le_thi_tra_so(monkeypatch):
    contrib = _fake_tables(monkeypatch)
    r = tools.run(ToolCall('explain_forecast', ARGS_DAY), 'duckdb')
    assert r.status == 'ok', r.message
    assert {x['feature_group']: x['contribution_log'] for x in r.rows} == pytest.approx(contrib)


@pytest.mark.parametrize('kw,status', [
    ({'target_shift': 0.01, 'daily_shift': 0.01}, 'query_error'),             # base + Σ ≠ forecast_log (daily vẫn khớp)
    ({'daily_shift': 0.01}, 'query_error'),                                   # lệch log(G) của rpt_forecast_daily
    ({'daily_n': 0}, 'query_error'),                                          # dự báo ngày thiếu
    ({'groups': GROUPS[:-1]}, 'query_error'),                                 # thiếu một nhóm
    ({'bad': (GROUPS[0], 'min_version', 'v0')}, 'query_error'),               # khác model_version của dự báo chính
    ({'bad': (GROUPS[0], 'max_run', 'r0')}, 'query_error'),                   # khác run_id
    ({'bad': (GROUPS[0], 'n', 2)}, 'query_error'),                            # trùng dòng / thừa ngày
    ({'bad': (GROUPS[0], 'contribution_log', float('nan'))}, 'query_error'),  # số không hữu hạn
    ({'primary': 'sarimax_full'}, 'no_data'),                                 # model chính không có phân rã
])
def test_phan_ra_khong_doi_soat_duoc_thi_khong_tra_so(monkeypatch, kw, status):
    _fake_tables(monkeypatch, **kw)
    r = tools.run(ToolCall('explain_forecast', ARGS_DAY), 'duckdb')
    assert r.status == status, (r.status, r.message)
    assert not r.rows and not r.derived


@pytest.mark.parametrize('day,ok', [(15, True), (16, False)])
def test_evidence_phan_ra_ngay_dung_thi_qua_sai_ngay_thi_chan(published, day, ok):
    claim = [{'id': 'c1', 'path': 'T1.rows[nam_chan_le].contribution_log'}]
    answer = final(answer='Phân rã G ngày 15/8/2023: năm chẵn/lẻ góp {c1}.', claims=claim)
    turn = service.run_turn('Phân rã dự báo G ngày 15/8/2023?', [], 'duckdb', FakeProvider(
        call('explain_forecast', period='day', year=2023, month=8, day=day), answer, answer))
    assert (turn.status == 'ok') is ok, (turn.status, turn.validation_errors)
    assert any('khác kỳ' in e for e in turn.validation_errors) is (not ok)


@pytest.mark.parametrize('text,ok', [
    ('Không thể kết luận Urban Blowout gây ra mức giảm; trong model nhóm này góp {c1}.', True),
    ('Phân rã không cho biết điều gì khiến G thực tế giảm; nhóm này góp {c1} trong model.', True),
    ('Dữ liệu không chứng minh G giảm do khuyến mãi; trong model nhóm này góp {c1}.', True),
    ('Urban Blowout không gây ra mức giảm; trong model nhóm này góp {c1}.', True),
    ('Dữ liệu không đủ để kết luận Urban Blowout gây ra mức giảm; nhóm này góp {c1} trong model.', True),
    ('Không thể đưa ra kết luận rằng Urban Blowout gây ra mức giảm; nhóm này góp {c1} trong model.', True),
    ('Chưa đủ cơ sở để nói Urban Blowout khiến G thực tế giảm; nhóm này góp {c1} trong model.', True),
    ('Trong model, nhóm lịch Urban Blowout làm dự báo G thấp hơn mức nền, góp {c1} vào log(G).', True),
    ('Các hệ số nhân không cộng được, và đây là thành phần của model chứ không phải kết luận Urban Blowout là nguyên nhân làm G thực tế biến động; nhóm này góp {c1}.', True),
    ('Không thể nói Urban Blowout gây ra mức giảm; nhóm này góp {c1} trong model.', True),
    ('Không có cơ sở để nói Urban Blowout gây ra mức giảm; nhóm này góp {c1} trong model.', True),
    ('Chưa có đủ bằng chứng để kết luận Urban Blowout gây ra mức giảm; nhóm này góp {c1} trong model.', True),
    ('Trong model, nhóm Urban Blowout khiến dự báo G thấp hơn mức nền, góp {c1} vào log(G).', True),
    ('Trong model, nhóm Urban Blowout khiến cho log(G) dự báo thấp hơn mức nền, góp {c1}.', True),
    ('Trong model, Urban Blowout làm G dự báo thấp hơn mức nền, góp {c1} vào log(G).', True),
    ('Trong model, Urban Blowout làm giảm dự báo G so với mức nền, góp {c1} vào log(G).', True),
    ('Urban Blowout gây ra mức giảm, nhóm này góp {c1}.', False),
    ('Không phải mùa vụ. Urban Blowout khiến G giảm {c1}.', False),
    ('Nhóm này góp {c1}, nhưng chính khuyến mãi dẫn đến G giảm.', False),
    ('Urban Blowout là nguyên nhân làm G dự báo giảm, trong model nhóm này góp {c1}.', False),
    ('Không phải mùa vụ mà Urban Blowout gây ra mức giảm; trong model nhóm này góp {c1}.', False),
    ('Không thể kết luận mùa vụ gây ra mức giảm, Urban Blowout tạo ra mức giảm {c1}.', False),
    ('Không thể phủ nhận Urban Blowout gây ra mức giảm; trong model nhóm này góp {c1}.', False),
    ('Không chỉ Urban Blowout gây ra mức giảm; trong model nhóm này góp {c1}.', False),
    ('Không phủ nhận marketing gây ra mức giảm; trong model nhóm này góp {c1}.', False),
    ('Không chỉ khuyến mãi gây ra mức giảm; trong model nhóm này góp {c1}.', False),
    ('Không chỉ marketing gây ra mức giảm; trong model nhóm này góp {c1}.', False),
    ('Không chỉ mùa vụ, Urban Blowout cũng gây ra mức giảm; trong model nhóm này góp {c1}.', False),
    ('Khuyến mãi làm doanh thu giảm; trong model nhóm này góp {c1}.', False),
    ('Urban Blowout làm giảm doanh thu thực tế; trong model nhóm này góp {c1}.', False),
    ('Urban Blowout làm tăng G thực tế; trong model nhóm này góp {c1}.', False),
    ('Urban Blowout khiến G thực tế giảm; trong model nhóm này góp {c1}.', False),
    ('Urban Blowout tạo ra mức giảm; trong model nhóm này góp {c1}.', False),
])
def test_chan_nhan_qua_cho_qua_cau_phu_dinh(published, text, ok):
    claim = [{'id': 'c1', 'path': 'T1.rows[promo_urban_blowout].contribution_log'}]
    a = final(answer=text, claims=claim)
    turn = service.run_turn('Có phải Urban Blowout là nguyên nhân làm dự báo G tháng 8/2023 giảm?', [], 'duckdb',
                            FakeProvider(call('explain_forecast', **ARGS_MONTH), a, a))
    causal = any('nguyên nhân' in e for e in turn.validation_errors)
    assert causal is (not ok), (turn.status, turn.validation_errors)
    if ok:
        assert turn.status == 'ok', turn.validation_errors


@pytest.mark.parametrize('question,text,ok', [
    ('Phân rã model dự báo COGS tháng 8/2023.',
     'Phân rã COGS tháng 8/2023: Urban Blowout góp {c1} vào log(COGS) dự báo.', False),
    ('Phân rã model dự báo COGS tháng 8/2023.',
     'Urban Blowout góp {c1} trong model.', False),
    ('Phân rã model dự báo COGS tháng 8/2023.',
     'Riêng G, nhóm lịch Urban Blowout góp {c1} vào log(G) trong model.', False),
    ('Phân rã model dự báo COGS tháng 8/2023.',
     'COGS chưa có phân rã. Nhóm lịch Urban Blowout góp {c1} trong model.', False),
    ('Phân rã model dự báo COGS tháng 8/2023.',
     'COGS chưa có phân rã. Riêng G, nhóm lịch Urban Blowout góp {c1} trong model G.', True),
    ('Phân rã model dự báo COGS tháng 8/2023.',
     'COGS chưa có phân rã. Dưới đây là phân rã model cho dự báo G. '
     'Nhóm lịch Urban Blowout góp {c1} trong model.', True),
    ('Phân rã model dự báo COGS tháng 8/2023.',
     'COGS chưa có phân rã. Dưới đây là phân rã cho doanh thu gộp. '
     'Nhóm lịch Urban Blowout góp {c1} trong model.', True),
    ('Phân rã model dự báo COGS tháng 8/2023.',
     'COGS chưa có phân rã. G không có phân rã. '
     'Nhóm lịch Urban Blowout góp {c1} trong model.', False),
    ('Phân rã model dự báo COGS tháng 8/2023.',
     'COGS chưa có phân rã. Dưới đây là phân rã model cho dự báo G. '
     'Đây là phân rã COGS. Nhóm lịch Urban Blowout góp {c1} trong model.', False),
    ('Phân rã model dự báo G tháng 8/2023.',
     'Phân rã COGS: Urban Blowout góp {c1} vào log(COGS).', False),
])
def test_khong_gan_dong_gop_g_cho_cogs(published, question, text, ok):
    claim = [{'id': 'c1', 'path': 'T1.rows[promo_urban_blowout].contribution_log'}]
    answer = final(answer=text, claims=claim)
    turn = service.run_turn(question, [], 'duckdb', FakeProvider(
        call('explain_forecast', **ARGS_MONTH), answer, answer))
    assert (turn.status == 'ok') is ok, (turn.status, turn.validation_errors)
    if not ok:
        assert any('COGS' in e or 'của G' in e for e in turn.validation_errors)


def test_l4b5_raw_final_tu_log_model_duoc_qua(published):
    # Chép nguyên raw_final L4B5 từ live_20261020T014332Z_l4b_7916.jsonl; không đọc log khi pytest chạy.
    raw_final = r'''{"status": "ok", "answer": "Lưu ý: phân rã model hiện chỉ có cho dự báo G (doanh thu gộp, gồm cả đơn hủy), không có phân rã riêng cho COGS — dưới đây là phân rã model chính cho dự báo G tháng 08/2023, không phải nguyên nhân biến động. So với mức nền của model, nhóm chế độ sau 2018 kéo mức nền xuống {c1} (log), hệ số nhân {c2}; nhóm lịch Urban Blowout kéo xuống {c3}, hệ số nhân {c4}; nhóm mùa vụ góp {c5}, hệ số nhân {c6}; nhóm đầu/cuối tháng góp {c7}, hệ số nhân {c8}; nhóm lịch Year End Sale góp {c9}, hệ số nhân {c10}; nhóm năm chẵn/lẻ góp {c11}, hệ số nhân {c12}; nhóm lịch Mid Year Sale góp {c13}, hệ số nhân {c14}; nhóm lịch Spring Sale góp {c15}, hệ số nhân {c16}; nhóm lịch Fall Launch góp {c17}, hệ số nhân {c18}; nhóm lịch Rural Special kéo xuống {c19}, hệ số nhân {c20}. Đây là trung bình log theo ngày trong tháng của dự báo G, không phải phần góp VND vào tổng tháng; các hệ số nhân không cộng được.", "claims": [{"id": "c1", "path": "T1.rows[che_do_sau_2018].contribution_log", "sign": "am"}, {"id": "c2", "path": "T1.rows[che_do_sau_2018].multiplier"}, {"id": "c3", "path": "T1.rows[promo_urban_blowout].contribution_log", "sign": "am"}, {"id": "c4", "path": "T1.rows[promo_urban_blowout].multiplier"}, {"id": "c5", "path": "T1.rows[mua_vu].contribution_log", "sign": "duong"}, {"id": "c6", "path": "T1.rows[mua_vu].multiplier"}, {"id": "c7", "path": "T1.rows[dau_cuoi_thang].contribution_log", "sign": "duong"}, {"id": "c8", "path": "T1.rows[dau_cuoi_thang].multiplier"}, {"id": "c9", "path": "T1.rows[promo_year_end_sale].contribution_log", "sign": "duong"}, {"id": "c10", "path": "T1.rows[promo_year_end_sale].multiplier"}, {"id": "c11", "path": "T1.rows[nam_chan_le].contribution_log", "sign": "duong"}, {"id": "c12", "path": "T1.rows[nam_chan_le].multiplier"}, {"id": "c13", "path": "T1.rows[promo_mid_year_sale].contribution_log", "sign": "duong"}, {"id": "c14", "path": "T1.rows[promo_mid_year_sale].multiplier"}, {"id": "c15", "path": "T1.rows[promo_spring_sale].contribution_log", "sign": "duong"}, {"id": "c16", "path": "T1.rows[promo_spring_sale].multiplier"}, {"id": "c17", "path": "T1.rows[promo_fall_launch].contribution_log", "sign": "duong"}, {"id": "c18", "path": "T1.rows[promo_fall_launch].multiplier"}, {"id": "c19", "path": "T1.rows[promo_rural_special].contribution_log", "sign": "am"}, {"id": "c20", "path": "T1.rows[promo_rural_special].multiplier"}]}'''
    reply = Reply(raw_final, [], {'role': 'assistant', 'content': raw_final}, 200, 50)
    turn = service.run_turn('Phân rã model dự báo COGS tháng 8/2023.', [], 'duckdb', FakeProvider(
        call('explain_forecast', **ARGS_MONTH), reply, reply))
    assert turn.status == 'ok', turn.validation_errors
    assert len(turn.values) == 20


def test_l4b5_cham_cau_tho_khong_muon_nhan_g_cua_app(published):
    from dataclasses import replace
    from scripts.ops import ai_live_eval

    claim = [{'id': 'c1', 'path': 'T1.rows[promo_urban_blowout].contribution_log'}]
    good = final(answer='COGS chưa có phân rã. Riêng G, nhóm Urban Blowout góp {c1} trong model G.',
                 claims=claim)
    turn = service.run_turn('Phân rã model dự báo COGS tháng 8/2023.', [], 'duckdb', FakeProvider(
        call('explain_forecast', **ARGS_MONTH), good))
    case = ai_live_eval.ACCEPT_L4B[-1]
    assert turn.status == 'ok' and ai_live_eval.grade(case, turn)['pass']
    # Giữ cùng nhãn số G do app gắn, chỉ thay câu thô của model: rubric phải phát hiện câu gán cho COGS.
    bad = replace(turn, raw_final=json.dumps({'answer': 'Phân rã COGS: nhóm Urban Blowout góp {c1}.'}))
    check = ai_live_eval.grade(case, bad)
    assert not check['pass'] and not check['checks']['must_if_ok']


def test_rubric_l4b4_khong_dem_ca_chua_co_tool(capsys):
    from scripts.ops import ai_live_eval

    assert ai_live_eval.check_rubric([ai_live_eval.ACCEPT_L4B[3]], 'duckdb') == 0
    report = capsys.readouterr().out
    assert '[BỎ QUA] L4B4' in report and '0/0 đạt; 1 case' in report


def test_evidence_chan_xep_hang_chu_yeu(published):
    claim = [{'id': 'c1', 'path': 'T1.rows[promo_urban_blowout].contribution_log'}]
    a = final(answer='Trong model, nhóm lịch Urban Blowout là nhóm kéo xuống chủ yếu, góp {c1}.', claims=claim)
    turn = service.run_turn('Phân rã dự báo G tháng 8/2023?', [], 'duckdb', FakeProvider(
        call('explain_forecast', **ARGS_MONTH), a, a))
    assert turn.status == 'answer_validation_failed'
    assert any('chủ yếu' in e for e in turn.validation_errors)


# --- S9b: số và cách nói nghiệp vụ lấy từ kết quả tool giả, không gọi mô hình thật ---

S9B_CONTRIB = {g: 0.001 for g in GROUPS} | {
    'promo_urban_blowout': -0.2556, 'che_do_sau_2018': -0.3032, 'mua_vu': 0.0685}


def _s9b_tool(monkeypatch):
    _fake_tables(monkeypatch, contrib_override=S9B_CONTRIB, days=31, daily_n=31)
    result = tools.run(ToolCall('explain_forecast', ARGS_MONTH), 'duckdb')
    assert result.status == 'ok', result.message
    return result


def test_s9b_phan_tram_thu_hang_va_nhom_nho(monkeypatch):
    result = _s9b_tool(monkeypatch)
    rows = {r['feature_group']: r for r in result.rows}
    for group, log_value in S9B_CONTRIB.items():
        assert rows[group]['pct_vs_base'] == pytest.approx((rows[group]['multiplier'] - 1) * 100)
        assert rows[group]['pct_vs_base'] == pytest.approx(math.expm1(log_value) * 100)
    assert [(r['feature_group'], r['rank']) for r in sorted(result.rows, key=lambda r: r['rank'])[:3]] == [
        ('che_do_sau_2018', 1), ('promo_urban_blowout', 2), ('mua_vu', 3)]
    assert evidence._fmt(rows['promo_urban_blowout']['pct_vs_base'], 'pct_vs_base', False) == '−22,6%'
    assert evidence._fmt(rows['che_do_sau_2018']['pct_vs_base'], 'pct_vs_base', False) == '−26,2%'
    assert evidence._fmt(rows['mua_vu']['pct_vs_base'], 'pct_vs_base', False) == '+7,1%'
    assert result.derived['small_groups'] == pytest.approx(
        {'n': 7, 'threshold_pct': 1.0, 'max_abs_pct': math.expm1(.001) * 100})
    assert rows['che_do_sau_2018']['rank_dir'] == 1
    assert rows['promo_urban_blowout']['rank_dir'] == 2
    assert rows['mua_vu']['rank_dir'] == 1


def test_s9b_hoa_rank_on_dinh_va_thang_thieu_ngay(monkeypatch):
    contrib = {g: 0.001 for g in GROUPS} | {'mua_vu': 0.2, 'promo_urban_blowout': -0.2}
    _fake_tables(monkeypatch, contrib_override=contrib)
    day = tools.run(ToolCall('explain_forecast', ARGS_DAY), 'duckdb')
    assert day.status == 'ok'
    assert [r['feature_group'] for r in sorted(day.rows, key=lambda r: r['rank'])[:2]] == [
        'promo_urban_blowout', 'mua_vu']
    partial = tools.run(ToolCall('explain_forecast', {'period': 'month', 'year': 2024, 'month': 7}), 'duckdb')
    assert partial.status == 'ok'
    assert all(r['is_partial'] and r['n_days'] == 1 and r['n_days_in_period'] == 31 for r in partial.rows)


def test_s9b_cau_ngan_top_hai_khong_lap_nhan(monkeypatch):
    from scripts.ops import ai_live_eval

    _s9b_tool(monkeypatch)
    answer = ('Dự báo G tháng 8/2023 thấp chủ yếu do hai nhóm trong model: '
              'chế độ sau 2018 kéo xuống {c1} so với mức nền (nhóm này kéo mọi tháng), '
              'và lịch Urban Blowout kéo xuống {c2}. Mùa vụ kéo lên {c3}. '
              '{c4} nhóm có ảnh hưởng dưới {c5} mỗi nhóm.')
    claims = [{'id': 'c1', 'path': 'T1.rows[che_do_sau_2018].pct_vs_base'},
              {'id': 'c2', 'path': 'T1.rows[promo_urban_blowout].pct_vs_base'},
              {'id': 'c3', 'path': 'T1.rows[mua_vu].pct_vs_base'},
              {'id': 'c4', 'path': 'T1.derived.small_groups.n'},
              {'id': 'c5', 'path': 'T1.derived.small_groups.threshold_pct'}]
    turn = service.run_turn('Vì sao dự báo G tháng 8/2023 thấp?', [], 'duckdb', FakeProvider(
        call('explain_forecast', **ARGS_MONTH), final(answer=answer, claims=claims)))
    assert turn.status == 'ok', turn.validation_errors
    assert 'chế độ sau 2018 kéo xuống **26,2%** so với mức nền' in turn.answer_md
    assert 'lịch Urban Blowout kéo xuống **22,6%**' in turn.answer_md
    assert 'Mùa vụ kéo lên **7,1%** (so với mức nền, 08/2023)' in turn.answer_md
    assert len(turn.answer_md) <= 700
    assert ai_live_eval.grade(ai_live_eval.ACCEPT_L4D[0], turn)['pass']


def test_s9b_theo_tung_nhom_phai_du_muoi_nhom(monkeypatch):
    from scripts.ops import ai_live_eval

    _s9b_tool(monkeypatch)
    claims = [{'id': f'c{i}', 'path': f'T1.rows[{g}].pct_vs_base'} for i, g in enumerate(GROUPS, 1)]
    answer = 'Phân rã model dự báo G tháng 8/2023 theo từng nhóm: ' + '; '.join(
        f'{tools.FEATURE_GROUP_LABEL[g]} góp {{c{i}}}' for i, g in enumerate(GROUPS, 1)) + '.'
    turn = service.run_turn('Giải thích dự báo G tháng 8/2023 theo từng nhóm biến.', [], 'duckdb', FakeProvider(
        call('explain_forecast', **ARGS_MONTH), final(answer=answer, claims=claims)))
    assert turn.status == 'ok', turn.validation_errors
    assert ai_live_eval.grade(ai_live_eval.ACCEPT_L4D[2], turn)['pass']


def test_s9b_nhan_ngan_khi_thieu_ten_nhom_hoac_ky(monkeypatch):
    result = _s9b_tool(monkeypatch)
    row = next(r for r in result.rows if r['feature_group'] == 'promo_urban_blowout')
    assert evidence._label('pct_vs_base', row, 'lịch Urban Blowout kéo xuống ', answer='G tháng 8/2023') == \
        ' (so với mức nền, 08/2023)'
    assert evidence._label('pct_vs_base', row, 'lịch Urban Blowout kéo xuống ', after=' so với mức nền',
                           answer='G tháng 8/2023') == ''
    assert evidence._label('pct_vs_base', row, 'nhóm này kéo xuống ', answer='G tháng 8/2023') == \
        ' (so với mức nền, 08/2023)'
    assert evidence._label('pct_vs_base', row, 'lịch Urban Blowout kéo xuống ', answer='G tháng 9/2023') == \
        ' (so với mức nền, 08/2023)'
    assert evidence._label('pct_vs_base', row, 'nhóm này kéo xuống ', after=' so với mức nền',
                           answer='G tháng 8/2023') == ' (08/2023)'
    assert evidence._label('pct_vs_base', row, 'nhóm này ảnh hưởng mức nền ',
                           answer='G tháng 8/2023') == ' (so với mức nền, 08/2023)'
    assert evidence._label('pct_vs_base', row, 'lịch Urban Blowout kéo xuống ', after=' so với mức nền',
                           answer='G tháng 9/2023') == ' (08/2023)'


@pytest.mark.parametrize('answer,claims,needle', [
    ('Mùa vụ kéo xuống chủ yếu {c1}.',
     [{'id': 'c1', 'path': 'T1.rows[mua_vu].pct_vs_base'}], 'chủ yếu'),
    ('Tổng hai nhóm kéo xuống {c1} và {c2}.',
     [{'id': 'c1', 'path': 'T1.rows[promo_urban_blowout].pct_vs_base'},
      {'id': 'c2', 'path': 'T1.rows[che_do_sau_2018].pct_vs_base'}], 'không cộng'),
    ('{c1} nhóm còn lại mỗi nhóm dưới {c2}.',
     [{'id': 'c1', 'path': 'T1.rows[mua_vu].rank'},
      {'id': 'c2', 'path': 'T1.rows[promo_urban_blowout].pct_vs_base'}], 'small_groups'),
])
def test_s9b_chan_xep_hang_sai_cong_phan_tram_va_nhom_nho_sai(monkeypatch, answer, claims, needle):
    _s9b_tool(monkeypatch)
    rep = final(answer=answer, claims=claims)
    turn = service.run_turn('Vì sao dự báo G tháng 8/2023 thấp?', [], 'duckdb', FakeProvider(
        call('explain_forecast', **ARGS_MONTH), rep, rep))
    assert turn.status == 'answer_validation_failed'
    assert any(needle in e for e in turn.validation_errors), turn.validation_errors


# S9b lượt 2: một ngày giả có bốn nhóm đáng kể và sáu nhóm thật sự dưới ngưỡng 1%.
S9B_DAY_PCT = {'mua_vu': 84.4, 'che_do_sau_2018': -30.9, 'dau_cuoi_thang': 33.6,
               'promo_urban_blowout': 1.46}
S9B_DAY_PCT.update(dict(zip(sorted(set(GROUPS) - set(S9B_DAY_PCT)), (.846, -.5, .3, -.2, .1, -.05))))
S9B_DAY = {'period': 'day', 'year': 2024, 'month': 5, 'day': 1}


def _s9b_day_tool(monkeypatch):
    _fake_tables(monkeypatch, contrib_override={g: math.log1p(pct / 100) for g, pct in S9B_DAY_PCT.items()})
    result = tools.run(ToolCall('explain_forecast', S9B_DAY), 'duckdb')
    assert result.status == 'ok', result.message
    assert result.derived['small_groups']['n'] == 6
    assert result.derived['small_groups']['max_abs_pct'] == pytest.approx(.846)
    return result


def _s9b_turn(args, question, answer, claims):
    reply = final(answer=answer, claims=[{'id': cid, 'path': 'T1.' + path} for cid, path in claims.items()])
    return service.run_turn(question, [], 'duckdb', FakeProvider(
        call('explain_forecast', **args), reply, reply))


L4E_HEAD = 'Đây là phân rã model, không phải nguyên nhân. '
L4E_CLAIMS = {'c1': 'rows[che_do_sau_2018].pct_vs_base',
              'c2': 'rows[promo_urban_blowout].pct_vs_base',
              'c3': 'rows[mua_vu].pct_vs_base'}
L4E_QUESTION = 'Vì sao dự báo G tháng 8/2023 thấp?'


@pytest.mark.parametrize('case,answer', [
    ('A', 'Hai nhóm kéo xuống mạnh nhất: chế độ sau 2018 kéo xuống {c1}, '
     'và lịch Urban Blowout kéo xuống {c2}.'),
    ('B', 'Hai nhóm kéo xuống mạnh nhất: chế độ sau 2018 kéo xuống {c1}, '
     'và Urban Blowout kéo xuống {c2}.'),
    ('E', 'Hai nhóm kéo xuống mạnh nhất: chế độ sau năm 2018 kéo xuống {c1}, '
     'và lịch Urban Blowout kéo xuống {c2}.'),
    ('C', 'Dự báo thấp chủ yếu do chế độ sau 2018 ({c1}) và lịch Urban Blowout ({c2}). '
     'Mùa vụ kéo lên {c3}.'),
])
def test_l4e_xep_hang_alias_dung_duoc_qua(monkeypatch, case, answer):
    _s9b_tool(monkeypatch)
    claims = {cid: path for cid, path in L4E_CLAIMS.items() if '{' + cid + '}' in answer}
    turn = _s9b_turn(ARGS_MONTH, L4E_QUESTION, L4E_HEAD + answer, claims)
    assert turn.status == 'ok', (case, turn.validation_errors)


@pytest.mark.parametrize('case,answer,reason,top', [
    ('D', 'Dự báo thấp chủ yếu do chế độ sau 2018 ({c1}) và lịch Urban Blowout ({c2}), '
     'dù mùa vụ kéo lên {c3}.', 'trộn hai chiều', 'top-2 chiều âm'),
    ('F', 'Nhóm kéo xuống lớn nhất là lịch Urban Blowout ({c2}).', 'sai nhóm top-k', 'top-1 chiều âm'),
])
def test_l4e_chan_tron_chieu_va_sai_top(monkeypatch, case, answer, reason, top):
    _s9b_tool(monkeypatch)
    claims = {cid: path for cid, path in L4E_CLAIMS.items() if '{' + cid + '}' in answer}
    turn = _s9b_turn(ARGS_MONTH, L4E_QUESTION, L4E_HEAD + answer, claims)
    assert turn.status == 'answer_validation_failed', (case, turn.validation_errors)
    assert any(reason in error and top in error and 'chế độ sau 2018' in error
               for error in turn.validation_errors), turn.validation_errors
    if case == 'D':
        assert any('lịch Urban Blowout' in error and 'mùa vụ' in error and 'câu riêng' in error
                   for error in turn.validation_errors), turn.validation_errors


def test_l4e_alias_sai_nhom_claim_va_khop_mot_phan_bi_chan(monkeypatch):
    _s9b_tool(monkeypatch)
    wrong = (L4E_HEAD + 'Hai nhóm kéo xuống mạnh nhất: lịch Urban Blowout kéo xuống {c1}, '
             'và chế độ sau 2018 kéo xuống {c2}.')
    turn = _s9b_turn(ARGS_MONTH, L4E_QUESTION, wrong,
                     {k: L4E_CLAIMS[k] for k in ('c1', 'c2')})
    assert turn.status == 'answer_validation_failed'
    assert any('chỗ đặt {c1}' in e and 'claim là "chế độ sau 2018"' in e
               for e in turn.validation_errors), turn.validation_errors
    partial = (L4E_HEAD + 'Hai nhóm kéo xuống mạnh nhất: chế độ sau 2018 kéo xuống {c1}, '
               'và Urban BlowoutX kéo xuống {c2}.')
    turn = _s9b_turn(ARGS_MONTH, L4E_QUESTION, partial,
                     {k: L4E_CLAIMS[k] for k in ('c1', 'c2')})
    assert turn.status == 'answer_validation_failed'
    assert any('không gọi tên nhóm "lịch Urban Blowout"' in e for e in turn.validation_errors)


def test_l4e_sua_cau_tron_chieu_thanh_hai_cau_duoc_qua(monkeypatch):
    _s9b_tool(monkeypatch)
    bad = L4E_HEAD + ('Dự báo thấp chủ yếu do chế độ sau 2018 ({c1}) và lịch Urban Blowout ({c2}), '
                      'dù mùa vụ kéo lên {c3}.')
    good = L4E_HEAD + ('Dự báo thấp chủ yếu do chế độ sau 2018 ({c1}) và lịch Urban Blowout ({c2}). '
                       'Mùa vụ kéo lên {c3}.')
    claims = [{'id': cid, 'path': 'T1.' + path} for cid, path in L4E_CLAIMS.items()]
    fake = FakeProvider(call('explain_forecast', **ARGS_MONTH),
                        final(answer=bad, claims=claims), final(answer=good, claims=claims))
    turn = service.run_turn(L4E_QUESTION, [], 'duckdb', fake)
    assert turn.status == 'ok', turn.validation_errors
    assert turn.llm_calls == 3
    assert any('trộn hai chiều' in e and 'câu riêng' in e for e in turn.repair_errors)
    assert any('trộn hai chiều' in m.get('content', '') for m in fake.seen[-1] if m.get('role') == 'user')


@pytest.mark.parametrize('case,answer,ok', [
    ('G', 'Chế độ sau 2018 và Urban Blowout là hai nhóm kéo xuống mạnh nhất '
     '({c1} và {c2}).', True),
    ('H', 'Chế độ sau 2018 và lịch Urban Blowout là hai nhóm kéo xuống mạnh nhất '
     '({c1} và {c2}).', True),
    ('I', 'Hai nhóm kéo xuống mạnh nhất là chế độ sau 2018 và lịch Urban Blowout, '
     'lần lượt {c1} và {c2}.', True),
    ('J', 'Hai nhóm kéo xuống mạnh nhất là lịch Urban Blowout và chế độ sau 2018, '
     'lần lượt {c1} và {c2}.', False),
    ('K', 'Hai nhóm kéo xuống mạnh nhất ({c1} và {c2}) là chế độ sau 2018 và '
     'lịch Urban Blowout.', True),
    ('M', 'Hai nhóm kéo xuống mạnh nhất: lịch Urban Blowout ({c1}) và '
     'chế độ sau 2018 ({c2}).', False),
])
def test_l4f_day_cho_dat_ten_nhom(monkeypatch, case, answer, ok):
    _s9b_tool(monkeypatch)
    turn = _s9b_turn(ARGS_MONTH, L4E_QUESTION, L4E_HEAD + answer,
                     {k: L4E_CLAIMS[k] for k in ('c1', 'c2')})
    assert (turn.status == 'ok') is ok, (case, turn.validation_errors)
    if not ok:
        assert any('chỗ đặt' in err and 'claim là' in err for err in turn.validation_errors)


@pytest.mark.parametrize('case,answer,ok', [
    ('N', 'Hai nhóm kéo xuống mạnh nhất: chế độ sau 2018 góp {c1} (hệ số nhân {c4}) '
     'và lịch Urban Blowout góp {c2} (hệ số nhân {c5}). Mùa vụ kéo lên {c3}.', True),
    ('O', 'Hai nhóm kéo xuống mạnh nhất: lịch Urban Blowout góp {c1} (hệ số nhân {c4}) '
     'và chế độ sau 2018 góp {c2} (hệ số nhân {c5}). Mùa vụ kéo lên {c3}.', False),
    ('P', 'Hai nhóm kéo xuống mạnh nhất là chế độ sau 2018 và lịch Urban Blowout, lần lượt '
     '{c1} và {c2} (hệ số nhân {c4} và {c5}). Mùa vụ kéo lên {c3}.', True),
    ('R', 'Hai nhóm kéo xuống mạnh nhất là {c6} ({c1}) và {c7} ({c2}). '
     'Mùa vụ kéo lên {c3}.', True),
    ('S', 'Hai nhóm kéo xuống mạnh nhất là lịch Urban Blowout {c6} ({c1}) và {c7} ({c2}). '
     'Mùa vụ kéo lên {c3}.', False),
])
def test_l4f_nhieu_claim_cung_nhom_va_ten_feature_label(monkeypatch, case, answer, ok):
    _s9b_tool(monkeypatch)
    paths = L4E_CLAIMS | {
        'c4': 'rows[che_do_sau_2018].multiplier',
        'c5': 'rows[promo_urban_blowout].multiplier',
        'c6': 'rows[che_do_sau_2018].feature_label',
        'c7': 'rows[promo_urban_blowout].feature_label',
    }
    claims = {cid: path for cid, path in paths.items() if '{' + cid + '}' in answer}
    turn = _s9b_turn(ARGS_MONTH, L4E_QUESTION, L4E_HEAD + answer, claims)
    assert (turn.status == 'ok') is ok, (case, turn.validation_errors)
    if not ok:
        assert any('chỗ đặt' in err and 'claim là' in err for err in turn.validation_errors)


@pytest.mark.parametrize('answer,path,ok,needle', [
    ('Nhóm đẩy dự báo lên nhiều nhất là mùa vụ ({c1}).',
     'rows[mua_vu].pct_vs_base', True, ''),
    ('Nhóm đẩy dự báo lên nhiều nhất là lịch Urban Blowout ({c1}).',
     'rows[promo_urban_blowout].pct_vs_base', False, 'sai nhóm top-k'),
    ('Lịch Urban Blowout ({c1}) dẫn đầu nhóm kéo lên.',
     'rows[promo_urban_blowout].pct_vs_base', False, 'top-1 chiều dương'),
])
def test_l4f_chu_xep_hang_khac_cua_phan_ra(monkeypatch, answer, path, ok, needle):
    contrib = {g: .001 for g in GROUPS} | {
        'mua_vu': .6, 'promo_urban_blowout': .2, 'dau_cuoi_thang': .1}
    _fake_tables(monkeypatch, contrib_override=contrib)
    args = {'period': 'day', 'year': 2024, 'month': 5, 'day': 2}
    turn = _s9b_turn(args, 'Ngày 2/5/2024, nhóm nào đẩy dự báo G lên nhiều nhất?',
                     L4E_HEAD + answer, {'c1': path})
    assert (turn.status == 'ok') is ok, turn.validation_errors
    if not ok:
        assert any(needle in err and 'mùa vụ' in err for err in turn.validation_errors)


@pytest.mark.parametrize('word', ['đứng đầu', 'mạnh hơn cả'])
def test_l4f_xep_hang_mo_rong_va_phia_nho(monkeypatch, word):
    _s9b_tool(monkeypatch)
    good = L4E_HEAD + f'Chế độ sau 2018 kéo xuống {{c1}}, {word} nhóm kéo xuống.'
    turn = _s9b_turn(ARGS_MONTH, L4E_QUESTION, good, {'c1': L4E_CLAIMS['c1']})
    assert turn.status == 'ok', turn.validation_errors
    weak = L4E_HEAD + 'Chế độ sau 2018 kéo xuống ít nhất {c1}.'
    turn = _s9b_turn(ARGS_MONTH, L4E_QUESTION, weak, {'c1': L4E_CLAIMS['c1']})
    assert turn.status == 'answer_validation_failed'
    assert any('phân rã L4 chỉ xếp hạng phía mạnh nhất theo rank_dir' in err
               for err in turn.validation_errors)


def test_l4f_day_ten_khong_vuot_qua_placeholder_khac(monkeypatch):
    _s9b_tool(monkeypatch)
    answer = (L4E_HEAD + 'Lịch Urban Blowout có thứ hạng {c3}, nhưng nhóm kéo xuống mạnh nhất '
              'là {c1}, tức chế độ sau 2018.')
    turn = _s9b_turn(ARGS_MONTH, L4E_QUESTION, answer,
                     {'c1': L4E_CLAIMS['c1'], 'c3': 'rows[promo_urban_blowout].rank'})
    assert turn.status == 'ok', turn.validation_errors


def test_l4f_chan_dao_thu_tu_l4e5(monkeypatch):
    contrib = {g: .001 for g in GROUPS} | {
        'che_do_sau_2018': math.log1p(-.246), 'promo_urban_blowout': math.log1p(-.214),
        'dau_cuoi_thang': math.log1p(-.1)}
    _fake_tables(monkeypatch, contrib_override=contrib)
    answer = (L4E_HEAD + 'Ngày 15/8/2023, nhóm kéo xuống mạnh nhất là lịch Urban Blowout với {c1}, '
              'tiếp theo là chế độ sau 2018 kéo xuống {c2}, và đầu/cuối tháng kéo xuống {c3}.')
    claims = {'c1': 'rows[promo_urban_blowout].pct_vs_base',
              'c2': 'rows[che_do_sau_2018].pct_vs_base',
              'c3': 'rows[dau_cuoi_thang].pct_vs_base'}
    turn = _s9b_turn(ARGS_DAY, 'Vì sao dự báo G ngày 15/8/2023 thấp?', answer, claims)
    assert turn.status == 'answer_validation_failed', turn.validation_errors
    assert any('sai thứ tự' in err and 'chế độ sau 2018' in err and 'lịch Urban Blowout' in err
               for err in turn.validation_errors), turn.validation_errors


def test_l4f_claim_feature_label_goi_ten_dung_hang(monkeypatch):
    contrib = {g: .001 for g in GROUPS} | {
        'mua_vu': -.35, 'che_do_sau_2018': -.30, 'dau_cuoi_thang': -.25}
    _fake_tables(monkeypatch, contrib_override=contrib, days=31, daily_n=31)
    month = {'period': 'month', 'year': 2024, 'month': 1}
    result = tools.run(ToolCall('explain_forecast', month), 'duckdb')
    assert result.status == 'ok'
    rows = {r['feature_group']: r for r in result.rows}
    assert rows['mua_vu']['rank_dir'] == 1
    good = L4E_HEAD + 'Tháng 1/2024, nhóm kéo xuống mạnh nhất là {c1}, kéo xuống {c2} so với mức nền.'
    turn = _s9b_turn(month, 'Nhóm nào kéo G tháng 1/2024 xuống mạnh nhất?', good,
                     {'c1': 'rows[mua_vu].feature_label', 'c2': 'rows[mua_vu].pct_vs_base'})
    assert turn.status == 'ok', turn.validation_errors
    assert 'mùa vụ' in turn.answer_md
    wrong = L4E_HEAD + 'Tháng 1/2024, nhóm kéo xuống mạnh nhất là {c1}.'
    first_group = result.rows[0]['feature_group']
    assert first_group == 'che_do_sau_2018'  # hàng 0 không phải top-1 chiều âm
    turn = _s9b_turn(month, 'Nhóm nào kéo G tháng 1/2024 xuống mạnh nhất?', wrong,
                     {'c1': 'rows[0].feature_label'})
    assert turn.status == 'answer_validation_failed', turn.validation_errors
    assert any('sai nhóm top-k' in err and 'mùa vụ' in err for err in turn.validation_errors)


def test_l4f_rubric_tinh_doc_lap_tu_ket_qua_tool(monkeypatch):
    from scripts.ops import ai_live_eval

    _s9b_tool(monkeypatch)
    answer = L4E_HEAD + ('Hai nhóm kéo xuống mạnh nhất: chế độ sau 2018 {c1}, '
                         'lịch Urban Blowout {c2}.')
    turn = _s9b_turn(ARGS_MONTH, L4E_QUESTION, answer,
                     {k: L4E_CLAIMS[k] for k in ('c1', 'c2')})
    assert turn.status == 'ok', turn.validation_errors
    monkeypatch.setattr(evidence, '_verified_explain_rank',
                        lambda *_args: (_ for _ in ()).throw(AssertionError('rubric gọi guard')))
    assert ai_live_eval._l4f_ranked_ok(answer, turn)
    wrong = L4E_HEAD + ('Hai nhóm kéo xuống mạnh nhất: lịch Urban Blowout {c2}, '
                        'chế độ sau 2018 {c1}.')
    assert not ai_live_eval._l4f_ranked_ok(wrong, turn)
    assert not ai_live_eval._l4f_ranked_ok('Nhóm kéo xuống mạnh nhất là lịch Urban Blowout {c2}.', turn)
    assert ai_live_eval._l4f_ranked_ok('Chế độ sau 2018 kéo xuống {c1}.', turn)
    checks_why = ai_live_eval.grade(ai_live_eval.ACCEPT_L4F[0], turn)['checks']
    checks_other = ai_live_eval.grade(ai_live_eval.ACCEPT_L4F[1], turn)['checks']
    assert 'toi_da_3_nhom' in checks_why and 'toi_da_3_nhom' not in checks_other


def test_l4f_rubric_ngay_14_08_dung_sai_thu_tu_va_lan_luot(published):
    from scripts.ops import ai_live_eval

    args = {'period': 'day', 'year': 2023, 'month': 8, 'day': 14}
    result = tools.run(ToolCall('explain_forecast', args), 'duckdb')
    assert result.status == 'ok', result.message
    rows = {row['feature_group']: row for row in result.rows}
    assert rows['che_do_sau_2018']['rank_dir'] == 1
    assert rows['promo_urban_blowout']['rank_dir'] == 2
    assert rows['che_do_sau_2018']['pct_vs_base'] == pytest.approx(-24.7, abs=.1)
    assert rows['promo_urban_blowout']['pct_vs_base'] == pytest.approx(-22.1, abs=.1)

    ordered = L4E_HEAD + 'Hai nhóm kéo xuống mạnh nhất: chế độ sau 2018 {c1}, lịch Urban Blowout {c2}.'
    reversed_order = L4E_HEAD + 'Hai nhóm kéo xuống mạnh nhất: lịch Urban Blowout {c2}, chế độ sau 2018 {c1}.'
    paired = (L4E_HEAD + 'Hai nhóm kéo xuống mạnh nhất là chế độ sau 2018 và lịch Urban Blowout, '
              'lần lượt {c1} và {c2} (hệ số nhân {c4} và {c5}).')
    claims = {cid: path for cid, path in (L4E_CLAIMS | {
        'c4': 'rows[che_do_sau_2018].multiplier',
        'c5': 'rows[promo_urban_blowout].multiplier',
    }).items() if cid != 'c3'}
    turn = _s9b_turn(args, 'Vì sao dự báo G ngày 14/8/2023 thấp?', paired, claims)
    assert turn.status == 'ok', turn.validation_errors
    assert ai_live_eval._l4f_ranked_ok(ordered, turn) is True
    assert ai_live_eval._l4f_ranked_ok(reversed_order, turn) is False
    assert ai_live_eval._l4f_ranked_ok(paired, turn) is True


L4G_DAY = {'period': 'day', 'year': 2023, 'month': 8, 'day': 14}
L4G_CLAIMS = {
    'c1': 'rows[che_do_sau_2018].feature_label',
    'c2': 'rows[che_do_sau_2018].pct_vs_base',
    'c3': 'rows[dau_cuoi_thang].feature_label',
    'c4': 'rows[dau_cuoi_thang].pct_vs_base',
    'c5': 'derived.small_groups.n',
    'c6': 'derived.small_groups.threshold_pct',
    'c7': 'rows[promo_urban_blowout].feature_label',
    'c8': 'rows[promo_urban_blowout].pct_vs_base',
    'c9': 'rows[mua_vu].pct_vs_base',
}
L4G_HEAD = 'Đây là phân rã model, không phải nguyên nhân. '
L4G_X1 = ('Nhóm kéo xuống mạnh nhất là {c1} ({c2}); tiếp theo là {c3} kéo xuống {c4}. '
          'Ngoài ra {c5} nhóm có ảnh hưởng dưới {c6} mỗi nhóm.')
L4G_X2 = 'Nhóm kéo xuống mạnh nhất là {c1} ({c2}); đứng thứ hai là {c3} kéo xuống {c4}.'
L4G_GOOD = 'Nhóm kéo xuống mạnh nhất là {c1} ({c2}); tiếp theo là {c7} kéo xuống {c8}.'


@pytest.mark.parametrize('case,answer,ok,needle', [
    ('X1', L4G_X1, False, 'lịch Urban Blowout'),
    ('X2', L4G_X2, False, 'lịch Urban Blowout'),
    ('X3', 'Hai nhóm kéo xuống mạnh nhất là {c1} ({c2}) và {c3} ({c4}).', False,
     'lịch Urban Blowout'),
    ('đúng hai nhóm', L4G_GOOD, True, ''),
    ('nối kế thừa chiều', 'Nhóm kéo xuống mạnh nhất là {c1} ({c2}); tiếp theo là {c7} ({c8}).', True, ''),
    ('đúng ba nhóm', L4G_GOOD[:-1] + '; kế đến là đầu/cuối tháng kéo xuống {c4}.', True, ''),
    ('đảo nhóm 2/3', 'Nhóm kéo xuống mạnh nhất là {c1} ({c2}); tiếp theo là {c3} ({c4}); '
     'kế đến là {c7} ({c8}).', False, 'lịch Urban Blowout'),
    ('đổi chiều', L4G_GOOD + ' Ở chiều ngược lại, mùa vụ kéo lên {c9}.', True, ''),
    ('thứ Hai', 'Nhóm kéo xuống mạnh nhất là {c1} ({c2}). Thứ Hai, {c3} kéo xuống {c4}.', True, ''),
    ('tháng tiếp theo', 'Nhóm kéo xuống mạnh nhất là {c1} ({c2}). Tháng tiếp theo, '
     '{c3} kéo xuống {c4}.', True, ''),
    ('thứ hai độc lập', 'Đứng thứ hai là {c3} kéo xuống {c4}.', False, 'lịch Urban Blowout'),
    ('thứ hai và tên nhóm khác sau số', 'Đứng thứ hai là lịch Urban Blowout kéo xuống {c8}, '
     'còn mùa vụ được nêu riêng.', True, ''),
    ('nối không chuỗi', 'Tiếp theo là đầu/cuối tháng kéo xuống {c4}.', True, ''),
])
def test_l4g_thu_tu_phan_ra_ngay_14_08(published, case, answer, ok, needle):
    result = tools.run(ToolCall('explain_forecast', L4G_DAY), 'duckdb')
    assert result.status == 'ok', result.message
    rows = {row['feature_group']: row for row in result.rows}
    for group, rank, pct in (('che_do_sau_2018', 1, -24.74),
                             ('promo_urban_blowout', 2, -22.06), ('dau_cuoi_thang', 3, -5.27)):
        assert rows[group]['rank_dir'] == rank
        assert rows[group]['pct_vs_base'] == pytest.approx(pct, abs=.06)
    claims = {cid: path for cid, path in L4G_CLAIMS.items() if '{' + cid + '}' in answer}
    turn = _s9b_turn(L4G_DAY, 'Vì sao G dự báo ngày 14/8/2023 thấp hơn mức nền?',
                     L4G_HEAD + answer, claims)
    assert (turn.status == 'ok') == ok, (case, turn.validation_errors)
    if needle:
        assert any(needle in err and ('top-' in err or 'thứ hai' in err or 'thứ 2' in err)
                   for err in turn.validation_errors), (case, turn.validation_errors)


@pytest.mark.parametrize('word', ['tiếp theo', 'tiếp đến', 'kế đến', 'kế tiếp', 'sau đó là', 'theo sau là'])
def test_l4g_cac_tu_noi_tiep_phai_dung_nhom_ke(published, word):
    answer = L4G_HEAD + f'Nhóm kéo xuống mạnh nhất là {{c1}} ({{c2}}); {word} {{c3}} kéo xuống {{c4}}.'
    turn = _s9b_turn(L4G_DAY, 'Vì sao G dự báo ngày 14/8/2023 thấp?', answer,
                     {cid: L4G_CLAIMS[cid] for cid in ('c1', 'c2', 'c3', 'c4')})
    assert turn.status == 'answer_validation_failed', (word, turn.validation_errors)


@pytest.mark.parametrize('word', ['đứng thứ hai', 'xếp thứ nhì', 'nhóm thứ ba', 'mạnh thứ 2', 'lớn thứ 3',
                                   'nhiều thứ ba'])
def test_l4g_vi_tri_tuong_minh_khong_can_chuoi_truoc(published, word):
    answer = L4G_HEAD + f'{word} là {{c3}} kéo xuống {{c4}}.'
    turn = _s9b_turn(L4G_DAY, 'Phân rã G dự báo ngày 14/8/2023?', answer,
                     {cid: L4G_CLAIMS[cid] for cid in ('c3', 'c4')})
    should_pass = word in ('nhóm thứ ba', 'lớn thứ 3', 'nhiều thứ ba')
    assert (turn.status == 'ok') == should_pass, (word, turn.validation_errors)


def test_l4g_rubric_doc_lap_kiem_manh_noi_va_thu_tu(published, monkeypatch):
    from scripts.ops import ai_live_eval

    answer = L4G_HEAD + L4G_GOOD + ' Đầu/cuối tháng kéo xuống {c3} {c4}.'
    turn = _s9b_turn(L4G_DAY, 'Vì sao G dự báo ngày 14/8/2023 thấp?', answer,
                     {cid: L4G_CLAIMS[cid] for cid in ('c1', 'c2', 'c3', 'c4', 'c7', 'c8')})
    assert turn.status == 'ok', turn.validation_errors
    monkeypatch.setattr(evidence, '_verified_explain_rank',
                        lambda *_args: (_ for _ in ()).throw(AssertionError('rubric gọi guard')))
    assert ai_live_eval._l4g_ranked_ok(answer, turn)
    assert not ai_live_eval._l4g_ranked_ok(L4G_HEAD + L4G_X1, turn)
    assert not ai_live_eval._l4g_ranked_ok(L4G_HEAD + L4G_X2, turn)
    assert ai_live_eval._l4g_ranked_ok(L4G_HEAD + L4G_GOOD[:-1] +
                                       '; kế đến là đầu/cuối tháng kéo xuống {c4}.', turn)
    assert not ai_live_eval._l4g_ranked_ok(L4G_HEAD +
                                           'Nhóm kéo xuống mạnh nhất là {c1} ({c2}); tiếp theo là {c3} ({c4}); '
                                           'kế đến là {c7} ({c8}).', turn)


@pytest.mark.parametrize('case,answer,ok,needle', [
    ('E1', 'Nhóm kéo xuống mạnh nhất là chế độ sau 2018 ({c2}). '
     'Lịch Urban Blowout kéo xuống {c8}. Tiếp theo là đầu/cuối tháng ({c4}).', True, ''),
    ('E13', 'Nhóm kéo xuống mạnh nhất là chế độ sau 2018 ({c2}); '
     'thứ hai là đầu/cuối tháng ({c4}).', False, 'lịch Urban Blowout'),
    ('bỏ qua nhóm thứ hai', 'Nhóm kéo xuống mạnh nhất là chế độ sau 2018 ({c2}). '
     'Đầu/cuối tháng kéo xuống {c4}. Tiếp theo là lịch Urban Blowout ({c8}).',
     False, 'lịch Urban Blowout'),
    ('không nói tiếp', 'Nhóm kéo xuống mạnh nhất là chế độ sau 2018 ({c2}). '
     'Đầu/cuối tháng kéo xuống {c4}.', True, ''),
    ('thứ 2 là sai', 'Nhóm kéo xuống mạnh nhất là chế độ sau 2018 ({c2}); '
     'thứ 2 là đầu/cuối tháng ({c4}).', False, 'lịch Urban Blowout'),
    ('thứ 2 là đúng', 'Nhóm kéo xuống mạnh nhất là chế độ sau 2018 ({c2}); '
     'thứ 2 là lịch Urban Blowout ({c8}).', True, ''),
    ('thứ hai, sai', 'Nhóm kéo xuống mạnh nhất là chế độ sau 2018 ({c2}). '
     'Thứ hai, đầu/cuối tháng kéo xuống {c4}.', False, 'lịch Urban Blowout'),
    ('thứ hai, đúng', 'Nhóm kéo xuống mạnh nhất là chế độ sau 2018 ({c2}). '
     'Thứ hai, lịch Urban Blowout kéo xuống {c8}.', True, ''),
    ('thứ Hai đầu câu', 'Thứ Hai, 14/8/2023, nhóm kéo xuống mạnh nhất là '
     'chế độ sau 2018 ({c2}).', True, ''),
    ('thứ Hai sau ngày', 'Ngày 14/8/2023 là thứ Hai; nhóm kéo xuống mạnh nhất là '
     'chế độ sau 2018 ({c2}).', True, ''),
    ('thứ 2 sau ngày', 'Ngày 14/8/2023 là thứ 2; nhóm kéo xuống mạnh nhất là '
     'chế độ sau 2018 ({c2}).', True, ''),
    ('thứ Hai là ngày', 'Thứ Hai là ngày 14/8/2023, nhóm kéo xuống mạnh nhất là '
     'chế độ sau 2018 ({c2}).', True, ''),
    ('E14', 'Nhóm kéo xuống mạnh nhất là chế độ sau 2018 ({c2}). '
     'Mùa vụ kéo lên {c9}. Tiếp theo là đầu/cuối tháng ({c4}).', True, ''),
])
def test_l4g_bien_chuoi_va_vi_tri_thu_hai(published, case, answer, ok, needle):
    from types import SimpleNamespace

    from scripts.ops import ai_live_eval

    result = tools.run(ToolCall('explain_forecast', L4G_DAY), 'duckdb')
    assert result.status == 'ok', result.message
    claims = {cid: path for cid, path in L4G_CLAIMS.items() if '{' + cid + '}' in answer}
    raw = L4G_HEAD + answer
    turn = _s9b_turn(L4G_DAY, 'Vì sao G dự báo ngày 14/8/2023 thấp hơn mức nền?', raw, claims)
    assert (turn.status == 'ok') == ok, (case, turn.validation_errors)
    if needle:
        assert any(needle in error for error in turn.validation_errors), (case, turn.validation_errors)
    rubric_turn = SimpleNamespace(results={'T1': result},
                                  values={cid: ('T1.' + path, None, '') for cid, path in claims.items()})
    # E14 là giới hạn guard đã chốt; rubric độc lập vẫn phải nhận ra nhóm thứ hai bị bỏ qua.
    rubric_ok = False if case == 'E14' else ok
    assert ai_live_eval._l4g_ranked_ok(raw, rubric_turn) == rubric_ok, case


@pytest.mark.parametrize('case,answer,guard_ok,rubric_ok', [
    ('N1', 'Nhóm kéo xuống mạnh nhất là chế độ sau 2018 ({c2}). '
     'Thứ nhì là đầu/cuối tháng ({c4}).', False, False),
    ('N2', 'Nhóm kéo xuống mạnh nhất là chế độ sau 2018 ({c2}). '
     'Thứ hai là lịch Urban Blowout ({c8}), và thứ ba là đầu/cuối tháng ({c4}).', True, True),
    ('N2 nhiều claim', 'Nhóm kéo xuống mạnh nhất là chế độ sau 2018 ({c2}). '
     'Thứ hai là {c7} ({c8}), và thứ ba là {c3} ({c4}).', True, True),
    ('N3', 'Nhóm kéo xuống mạnh nhất là chế độ sau 2018 ({c2}). '
     'Thứ hai là lịch Urban Blowout ({c8}), và thứ ba là mùa vụ ({c9}).', False, False),
    ('N4', 'Nhóm kéo xuống mạnh nhất là chế độ sau 2018 ({c2}); '
     'thứ 2 là đầu/cuối tháng ({c4}).', False, False),
    ('N5', 'Nhóm kéo xuống mạnh nhất là chế độ sau 2018 ({c2}); '
     'thứ 2 là lịch Urban Blowout ({c8}).', True, True),
    ('M1', 'Nhóm kéo xuống mạnh nhất là chế độ sau 2018 ({c2}). '
     'Mùa vụ đóng góp {c9}. Tiếp theo là lịch Urban Blowout kéo xuống {c8}.', True, True),
    ('M2', 'Nhóm kéo xuống mạnh nhất là chế độ sau 2018 ({c2}). '
     'Ngoài ra, mùa vụ ở mức {c9}. Tiếp theo trong nhóm kéo xuống là lịch Urban Blowout ({c8}).', True, True),
    ('M3', 'Nhóm kéo xuống mạnh nhất là chế độ sau 2018 ({c2}). '
     'Lịch Urban Blowout ở mức {c8}. Tiếp theo là đầu/cuối tháng ({c4}).', True, True),
    ('E4', 'Nhóm kéo xuống mạnh nhất là chế độ sau 2018 ({c2}); '
     'tiếp theo là lịch Urban Blowout ({c8}). Ở chiều ngược lại, mùa vụ kéo lên {c9}.', True, True),
    ('E6', 'Nhóm kéo xuống mạnh nhất là chế độ sau 2018 ({c2}); '
     'lịch Urban Blowout đứng thứ hai ({c8}); đầu/cuối tháng đứng thứ ba ({c4}).', True, True),
    ('E7', 'Lịch Urban Blowout đứng thứ hai trong các nhóm kéo xuống, ở mức {c8}.', True, True),
    ('E12', 'Nhóm kéo xuống mạnh nhất là chế độ sau 2018 ({c2}). '
     'Mùa vụ kéo lên {c9}. Tiếp theo là lịch Urban Blowout ({c8}).', True, True),
    ('E14', 'Nhóm kéo xuống mạnh nhất là chế độ sau 2018 ({c2}). '
     'Mùa vụ kéo lên {c9}. Tiếp theo là đầu/cuối tháng ({c4}).', True, False),
    ('bỏ qua vị trí hai', 'Nhóm kéo xuống mạnh nhất là chế độ sau 2018 ({c2}). '
     'Đầu/cuối tháng kéo xuống {c4}. Tiếp theo là lịch Urban Blowout ({c8}).', False, False),
])
def test_l4g_luot6_vi_tri_va_chieu_ngam(published, case, answer, guard_ok, rubric_ok):
    from types import SimpleNamespace

    from scripts.ops import ai_live_eval

    result = tools.run(ToolCall('explain_forecast', L4G_DAY), 'duckdb')
    assert result.status == 'ok', result.message
    claims = {cid: path for cid, path in L4G_CLAIMS.items() if '{' + cid + '}' in answer}
    raw = 'Đây là phân rã model dự báo G, không phải nguyên nhân. ' + answer
    turn = _s9b_turn(L4G_DAY, 'Vì sao G dự báo ngày 14/8/2023 thấp hơn mức nền?', raw, claims)
    assert (turn.status == 'ok') == guard_ok, (case, turn.validation_errors)
    rubric_turn = SimpleNamespace(results={'T1': result},
                                  values={cid: ('T1.' + path, None, '') for cid, path in claims.items()})
    assert ai_live_eval._l4g_ranked_ok(raw, rubric_turn) == rubric_ok, case


def test_l4f_tron_chieu_khong_co_nhom_cung_chieu_khong_in_top_0(monkeypatch):
    _s9b_tool(monkeypatch)
    answer = (L4E_HEAD + 'Dự báo cao chủ yếu do chế độ sau 2018 kéo xuống {c1} '
              'và lịch Urban Blowout kéo xuống {c2}.')
    turn = _s9b_turn(ARGS_MONTH, L4E_QUESTION, answer,
                     {k: L4E_CLAIMS[k] for k in ('c1', 'c2')})
    assert turn.status == 'answer_validation_failed'
    assert any('chọn một chiều cho câu xếp hạng' in err and 'top-0' not in err
               for err in turn.validation_errors), turn.validation_errors


def test_s9b2_tool_rank_dir_va_nguong(monkeypatch):
    result = _s9b_day_tool(monkeypatch)
    rows = {r['feature_group']: r for r in result.rows}
    assert rows['mua_vu']['pct_vs_base'] == pytest.approx(84.4)
    assert rows['che_do_sau_2018']['pct_vs_base'] == pytest.approx(-30.9)
    assert rows['dau_cuoi_thang']['pct_vs_base'] == pytest.approx(33.6)
    assert rows['promo_urban_blowout']['pct_vs_base'] == pytest.approx(1.46)
    assert [r['feature_group'] for r in sorted(result.rows, key=lambda r: r['rank_dir'] or 99)
            if r['contribution_log'] > 0][:2] == ['mua_vu', 'dau_cuoi_thang']
    assert rows['che_do_sau_2018']['rank_dir'] == 1
    assert result.derived['small_groups']['threshold_pct'] == 1.0


def test_s9b2_chan_nhom_nho_co_dau_phay(monkeypatch):
    _s9b_tool(monkeypatch)
    turn = _s9b_turn(ARGS_MONTH, 'Vì sao dự báo G tháng 8/2023 thấp?',
                     'Lịch Urban Blowout kéo xuống {c1} so với mức nền. {c4} nhóm còn lại, mỗi nhóm dưới {c5}.',
                     {'c1': 'rows[promo_urban_blowout].pct_vs_base', 'c4': 'rows[mua_vu].rank',
                      'c5': 'rows[mua_vu].pct_vs_base'})
    assert turn.status == 'answer_validation_failed'
    assert any('small_groups' in e for e in turn.validation_errors), turn.validation_errors


def test_s9b2_chan_max_abs_sau_duoi(monkeypatch):
    _s9b_day_tool(monkeypatch)
    turn = _s9b_turn(S9B_DAY, 'Vì sao dự báo G ngày 1/5/2024 cao?',
                     'Ngày 1/5/2024, {c2} nhóm có ảnh hưởng dưới {c3} mỗi nhóm.',
                     {'c2': 'derived.small_groups.n', 'c3': 'derived.small_groups.max_abs_pct'})
    assert turn.status == 'answer_validation_failed'
    assert any('threshold_pct' in e for e in turn.validation_errors), turn.validation_errors


def test_s9b2_chan_con_lai_khi_thieu_nhom_lon(monkeypatch):
    _s9b_day_tool(monkeypatch)
    turn = _s9b_turn(S9B_DAY, 'Vì sao dự báo G ngày 1/5/2024 cao?',
                     'Ngày 1/5/2024, mùa vụ kéo lên {c1} so với mức nền. '
                     '{c2} nhóm còn lại, mỗi nhóm dưới {c3}.',
                     {'c1': 'rows[mua_vu].pct_vs_base', 'c2': 'derived.small_groups.n',
                      'c3': 'derived.small_groups.threshold_pct'})
    assert turn.status == 'answer_validation_failed'
    assert any('"còn lại/khác"' in e for e in turn.validation_errors), turn.validation_errors


def test_s9b3_chan_nhom_khac_khi_thieu_nhom_lon(monkeypatch):
    _s9b_day_tool(monkeypatch)
    turn = _s9b_turn(S9B_DAY, 'Vì sao dự báo G ngày 1/5/2024 cao?',
                     'Ngày 1/5/2024, mùa vụ kéo lên {c1} so với mức nền; '
                     '{c8} nhóm khác, mỗi nhóm dưới {c9}.',
                     {'c1': 'rows[mua_vu].pct_vs_base', 'c8': 'derived.small_groups.n',
                      'c9': 'derived.small_groups.threshold_pct'})
    assert turn.status == 'answer_validation_failed'
    assert any('"còn lại/khác"' in e for e in turn.validation_errors), turn.validation_errors


def test_s9b3_nhom_khac_du_nhom_lon_duoc_qua(monkeypatch):
    _s9b_tool(monkeypatch)
    turn = _s9b_turn(ARGS_MONTH, 'Vì sao dự báo G tháng 8/2023 thấp?',
                     'Tháng 8/2023, lịch Urban Blowout kéo xuống {c1} so với mức nền; '
                     'chế độ sau 2018 kéo xuống {c2} so với mức nền; '
                     'mùa vụ kéo lên {c3} so với mức nền; '
                     '{c8} nhóm khác, mỗi nhóm dưới {c9}.',
                     {'c1': 'rows[promo_urban_blowout].pct_vs_base',
                      'c2': 'rows[che_do_sau_2018].pct_vs_base',
                      'c3': 'rows[mua_vu].pct_vs_base',
                      'c8': 'derived.small_groups.n',
                      'c9': 'derived.small_groups.threshold_pct'})
    assert turn.status == 'ok', turn.validation_errors
    assert '**7** nhóm khác, mỗi nhóm dưới **1,0%**' in turn.answer_md


def test_s9b3_nhom_co_anh_huong_duoi_khong_ngu_y_con_lai(monkeypatch):
    _s9b_day_tool(monkeypatch)
    turn = _s9b_turn(S9B_DAY, 'Vì sao dự báo G ngày 1/5/2024 cao?',
                     '{c8} nhóm có ảnh hưởng dưới {c9} mỗi nhóm.',
                     {'c8': 'derived.small_groups.n',
                      'c9': 'derived.small_groups.threshold_pct'})
    assert turn.status == 'ok', turn.validation_errors
    assert '**6** nhóm có ảnh hưởng dưới **1,0%** mỗi nhóm.' in turn.answer_md


@pytest.mark.parametrize('ending', [
    '; các nhóm khác ảnh hưởng nhỏ.',
    '. Các nhóm khác ảnh hưởng không đáng kể.',
    '; các yếu tố khác đều nhỏ.',
])
def test_s9b4_chan_phan_con_lai_khong_co_so_khi_thieu_nhom_lon(monkeypatch, ending):
    _s9b_day_tool(monkeypatch)
    turn = _s9b_turn(S9B_DAY, 'Vì sao dự báo G ngày 1/5/2024 cao?',
                     'Ngày 1/5/2024, mùa vụ kéo lên {c1} so với mức nền' + ending,
                     {'c1': 'rows[mua_vu].pct_vs_base'})
    assert turn.status == 'answer_validation_failed'
    assert any('nhóm có ảnh hưởng dưới' in e for e in turn.validation_errors), turn.validation_errors


def test_s9b4_phan_con_lai_khong_so_du_nhom_lon_duoc_qua(monkeypatch):
    _s9b_tool(monkeypatch)
    turn = _s9b_turn(ARGS_MONTH, 'Vì sao dự báo G tháng 8/2023 thấp?',
                     'Tháng 8/2023, lịch Urban Blowout kéo xuống {c1} so với mức nền; '
                     'chế độ sau 2018 kéo xuống {c2} so với mức nền; '
                     'mùa vụ kéo lên {c3} so với mức nền. Các nhóm khác ảnh hưởng nhỏ.',
                     {'c1': 'rows[promo_urban_blowout].pct_vs_base',
                      'c2': 'rows[che_do_sau_2018].pct_vs_base',
                      'c3': 'rows[mua_vu].pct_vs_base'})
    assert turn.status == 'ok', turn.validation_errors
    assert 'Các nhóm khác ảnh hưởng nhỏ.' in turn.answer_md


@pytest.mark.parametrize('ending', [
    'Các kỳ khác không được so sánh ở đây.',
    'Model khác cần kết quả phân rã riêng.',
    'Phân rã model không chứng minh nguyên nhân thực tế.',
])
def test_s9b4_khong_bat_nham_cau_ngoai_phan_con_lai(monkeypatch, ending):
    _s9b_day_tool(monkeypatch)
    turn = _s9b_turn(S9B_DAY, 'Vì sao dự báo G ngày 1/5/2024 cao?',
                     'Ngày 1/5/2024, mùa vụ kéo lên {c1} so với mức nền. ' + ending,
                     {'c1': 'rows[mua_vu].pct_vs_base'})
    assert turn.status == 'ok', turn.validation_errors


def test_s9b4_phan_con_lai_khong_so_hai_ket_qua_bi_chan(monkeypatch):
    result = _s9b_day_tool(monkeypatch)
    answer = 'Ngày 1/5/2024, mùa vụ kéo lên {c1} so với mức nền. Các nhóm khác ảnh hưởng nhỏ.'
    values = {'c1': ('T1.rows[mua_vu].pct_vs_base', 84.4, '84,4%')}
    errors = evidence.forecast_question_errors('Vì sao dự báo G ngày 1/5/2024 cao?', values,
                                               {'T1': result, 'T2': result}, answer)
    assert any('đúng một kết quả explain_forecast' in e for e in errors), errors


def test_s9b2_nhom_nho_khong_noi_con_lai_duoc_qua(monkeypatch):
    _s9b_day_tool(monkeypatch)
    turn = _s9b_turn(S9B_DAY, 'Vì sao dự báo G ngày 1/5/2024 cao?',
                     'Ngày 1/5/2024, mùa vụ kéo lên {c1} so với mức nền. '
                     '{c2} nhóm có ảnh hưởng dưới {c3} mỗi nhóm.',
                     {'c1': 'rows[mua_vu].pct_vs_base', 'c2': 'derived.small_groups.n',
                      'c3': 'derived.small_groups.threshold_pct'})
    assert turn.status == 'ok', turn.validation_errors
    assert 'mùa vụ kéo lên **84,4%** so với mức nền' in turn.answer_md
    assert '**6** nhóm có ảnh hưởng dưới **1,0%** mỗi nhóm' in turn.answer_md


def test_s9b2_chan_xep_hang_cao_lan_nhom_am(monkeypatch):
    _s9b_day_tool(monkeypatch)
    turn = _s9b_turn(S9B_DAY, 'Vì sao dự báo G ngày 1/5/2024 cao?',
                     'Dự báo G ngày 1/5/2024 cao chủ yếu do mùa vụ ({c1}) và chế độ sau 2018 ({c2}) so với mức nền.',
                     {'c1': 'rows[mua_vu].pct_vs_base', 'c2': 'rows[che_do_sau_2018].pct_vs_base'})
    assert turn.status == 'answer_validation_failed'
    assert any('rank_dir' in e for e in turn.validation_errors), turn.validation_errors


def test_s9b2_xep_hang_cao_dung_hai_nhom_duong(monkeypatch):
    from scripts.ops import ai_live_eval

    _s9b_day_tool(monkeypatch)
    turn = _s9b_turn(S9B_DAY, 'Vì sao dự báo G ngày 1/5/2024 cao?',
                     'Dự báo G ngày 1/5/2024 cao chủ yếu do mùa vụ kéo lên {c1} so với mức nền và '
                     'đầu/cuối tháng kéo lên {c2} so với mức nền. '
                     '{c3} nhóm có ảnh hưởng dưới {c4} mỗi nhóm.',
                     {'c1': 'rows[mua_vu].pct_vs_base', 'c2': 'rows[dau_cuoi_thang].pct_vs_base',
                      'c3': 'derived.small_groups.n', 'c4': 'derived.small_groups.threshold_pct'})
    assert turn.status == 'ok', turn.validation_errors
    assert 'mùa vụ kéo lên **84,4%** so với mức nền' in turn.answer_md
    assert 'đầu/cuối tháng kéo lên **33,6%** so với mức nền' in turn.answer_md
    assert ai_live_eval.grade(ai_live_eval.ACCEPT_L4D[1], turn)['pass']


def test_s9b2_chan_rank_dir_khi_rank_chung_van_dung(monkeypatch):
    _s9b_day_tool(monkeypatch)
    turn = _s9b_turn(S9B_DAY, 'Vì sao dự báo G ngày 1/5/2024 cao?',
                     'Dự báo G ngày 1/5/2024 cao chủ yếu do mùa vụ {c1}, đầu/cuối tháng {c2} '
                     'và chế độ sau 2018 {c3} so với mức nền.',
                     {'c1': 'rows[mua_vu].pct_vs_base', 'c2': 'rows[dau_cuoi_thang].pct_vs_base',
                      'c3': 'rows[che_do_sau_2018].pct_vs_base'})
    assert turn.status == 'answer_validation_failed'
    assert any('rank_dir' in e for e in turn.validation_errors), turn.validation_errors


def test_s9b2_chan_xep_hang_co_ca_hai_chieu(monkeypatch):
    _s9b_day_tool(monkeypatch)
    turn = _s9b_turn(S9B_DAY, 'Vì sao dự báo G ngày 1/5/2024 cao?',
                     'Dự báo G ngày 1/5/2024 cao chủ yếu do mùa vụ kéo lên {c1} '
                     'và chế độ sau 2018 kéo xuống {c2} so với mức nền.',
                     {'c1': 'rows[mua_vu].pct_vs_base', 'c2': 'rows[che_do_sau_2018].pct_vs_base'})
    assert turn.status == 'answer_validation_failed'
    assert any('rank_dir' in e for e in turn.validation_errors), turn.validation_errors


def test_s9b2_con_lai_du_nhom_duoc_qua(monkeypatch):
    _s9b_day_tool(monkeypatch)
    answer = ('Ngày 1/5/2024: mùa vụ {c1}; chế độ sau 2018 {c2}; đầu/cuối tháng {c3}; '
              'lịch Urban Blowout {c4}. {c5} nhóm còn lại, mỗi nhóm dưới {c6}.')
    claims = {'c1': 'rows[mua_vu].pct_vs_base', 'c2': 'rows[che_do_sau_2018].pct_vs_base',
              'c3': 'rows[dau_cuoi_thang].pct_vs_base', 'c4': 'rows[promo_urban_blowout].pct_vs_base',
              'c5': 'derived.small_groups.n', 'c6': 'derived.small_groups.threshold_pct'}
    turn = _s9b_turn(S9B_DAY, 'Phân rã dự báo G ngày 1/5/2024?', answer, claims)
    assert turn.status == 'ok', turn.validation_errors


def test_s9b2_max_abs_dung_voi_toi_da(monkeypatch):
    _s9b_day_tool(monkeypatch)
    turn = _s9b_turn(S9B_DAY, 'Phân rã dự báo G ngày 1/5/2024?',
                     'Ngày 1/5/2024, {c1} nhóm có ảnh hưởng tối đa {c2} mỗi nhóm.',
                     {'c1': 'derived.small_groups.n', 'c2': 'derived.small_groups.max_abs_pct'})
    assert turn.status == 'ok', turn.validation_errors
    assert 'tối đa **0,846%** mỗi nhóm' in turn.answer_md


def test_s9b2_phu_dinh_phep_cong_duoc_qua(monkeypatch):
    _s9b_tool(monkeypatch)
    turn = _s9b_turn(ARGS_MONTH, 'Vì sao dự báo G tháng 8/2023 thấp?',
                     'Không có tổng: lịch Urban Blowout kéo xuống {c1} và chế độ sau 2018 kéo xuống {c2} '
                     'so với mức nền, hai % này nhân với nhau, không cộng lại được.',
                     {'c1': 'rows[promo_urban_blowout].pct_vs_base',
                      'c2': 'rows[che_do_sau_2018].pct_vs_base'})
    assert turn.status == 'ok', turn.validation_errors
