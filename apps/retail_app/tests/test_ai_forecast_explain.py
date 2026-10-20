"""B4b: đối chứng SQL trực tiếp với bản dữ liệu và kiểm đường guard/answer, không gọi LLM thật."""
import datetime as dt
import json
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
                 bad=None):
    """Bảng giả cho ngày 15/08/2023: base 14 + Σ đóng góp = forecast_log. `bad` = (nhóm, cột, giá trị) làm hỏng một ô."""
    contrib = {g: 0.01 * (i - 4) for i, g in enumerate(GROUPS)}
    base = 14.0
    target = base + sum(contrib.values())
    cands = [{'model': primary, 'cogs_method': 'direct', 'is_primary': True, 'selection_step': 1, 'model_version': 'v1',
              'trained_through': TRAINED, 'run_id': 'r1', 'interval_level': 0.8, 'n_days': 548,
              'first_date': dt.date(2023, 1, 1), 'last_date': dt.date(2024, 7, 1)}]

    def explain_row(g):
        r = {'feature_group': g, 'n': 1, 'n_dates': 1, 'min_groups': 10, 'max_groups': 10, 'min_version': 'v1',
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
