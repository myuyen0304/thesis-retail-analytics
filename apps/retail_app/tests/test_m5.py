"""M5: trang Sức khỏe dữ liệu (docs/gd2_app_plan.md §4, §6).

Nguồn: view rpt_health_* trên nhật ký chạy dbt (schema ops, hook macros/health_log.sql) và log nạp raw._ingest_log.
Cần chạy SAU một lần `dbt build` đầy đủ trên cả hai backend (nhật ký của chính lần build đó mới được kiểm ở đây).
Các trạng thái lỗi / cũ / thiếu dựng bằng cách sửa bản sao DuckDB (không đụng kho thật), như test_khong_hardcode.
"""
import shutil
from pathlib import Path

import duckdb
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from dwh import queries
from dwh.connection import DUCKDB_PATH, read_sql
from ui.fmt import num

APP = Path(__file__).resolve().parents[1] / 'app.py'
PAGE = 'views/suc_khoe_du_lieu.py'


def _open(monkeypatch, backend, db_path=None, page=PAGE):
    monkeypatch.setenv('RETAIL_BACKEND', backend)
    if db_path is not None:
        monkeypatch.setenv('RETAIL_DUCKDB_PATH', str(db_path))
    st.cache_data.clear()
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    if page != 'views/tong_quan.py':
        at.switch_page(page).run()
    assert not at.exception, at.exception
    return at


def _ban_sao(tmp_path: Path, sql: str) -> Path:
    ban_sao = tmp_path / 'dbt.duckdb'   # giữ tên file: view trỏ bảng qua catalog "dbt"
    shutil.copy(DUCKDB_PATH, ban_sao)
    con = duckdb.connect(str(ban_sao))
    con.execute(sql)
    con.close()
    return ban_sao


def _the(at) -> dict:
    return {m.label: m.value for m in at.metric}


# ---------------- trạng thái thật sau dbt build ----------------

@pytest.mark.parametrize('backend', ['postgres', 'duckdb'])
def test_kho_dat_sau_build(monkeypatch, backend):
    s = queries.health_summary(backend).iloc[0]
    # lần kiểm gần nhất = lần dbt build đầy đủ, cùng lần dựng kho, đủ mọi test, tất cả đạt
    assert s['status_code'] == 'tot', s['status_code']
    assert s['test_command'] == 'build' and s['tests_started_at_utc'] == s['built_at_utc']
    assert s['n_tests_run'] == s['n_tests_in_project'] == s['n_tests_pass'] and s['n_tests_not_pass'] == 0
    assert s['n_singular_run'] == len(list((Path(__file__).resolve().parents[3] / 'retail_dbt' / 'tests')
                                          .glob('assert_*.sql')))   # mọi file test nghiệp vụ đều đã chạy
    at = _open(monkeypatch, backend)
    assert not at.error
    n = num(s['n_tests_run'])
    assert f'**Kho đạt:** {n}/{n} test đạt' in at.success[0].value
    the = _the(at)
    assert the['Test đạt'] == f'{n}/{n}' and the['Test không đạt'] == '0'
    assert the['Dữ liệu tới ngày'] == '31/12/2022'
    assert all(len(v) <= 11 for v in the.values())                          # 4 thẻ một hàng, không bị cắt
    nv = at.table[0].value                                                  # bảng test nghiệp vụ (chữ xuống dòng)
    assert len(nv) == s['n_singular_run'] and set(nv['Kết quả']) == {'Đạt'}
    assert '–' not in set(nv['Kiểm gì'])                                    # test nghiệp vụ nào cũng có mô tả
    assert len(at.dataframe[0].value) == s['n_generic_run']


def test_postgres_hien_log_nap_khop_bang_raw(monkeypatch):
    at = _open(monkeypatch, 'postgres')
    ng = at.dataframe[1].value.set_index('File nguồn')
    assert len(ng) == 14
    raw = read_sql("select 'orders' as t, count(*) as n from raw.orders union all "
                   "select 'order_items', count(*) from raw.order_items", 'postgres').set_index('t')['n']
    assert ng.loc['orders.csv', 'Số dòng'] == num(raw['orders']) == '646.945'
    assert ng.loc['order_items.csv', 'Số dòng'] == num(raw['order_items']) == '714.669'
    assert any('Cả lần nạp là một giao dịch' in c.value for c in at.caption)


def test_duckdb_bao_khong_co_log_nap(monkeypatch):
    at = _open(monkeypatch, 'duckdb')
    assert not at.error
    assert any('không có bước nạp riêng' in i.value for i in at.info)
    assert len(at.dataframe) == 2          # test ràng buộc + lịch sử, không có bảng log nạp


# ---------------- trạng thái dựng trên bản sao DuckDB ----------------

LAN_KIEM = '(select test_invocation_id from reporting.rpt_health_summary)'


def test_test_fail_thi_bao_do_va_dua_len_dau(monkeypatch, tmp_path):
    db = _ban_sao(tmp_path, "update ops.dbt_node_result set status = 'fail', failures = 3, "
                            "message = 'Got 3 results, configured to fail if != 0' "
                            f"where node_name = 'assert_rpt_driver' and invocation_id = {LAN_KIEM}")
    at = _open(monkeypatch, 'duckdb', db)
    assert '**1 test không đạt**' in at.error[0].value and not at.success
    assert _the(at)['Test không đạt'] == '1'
    nv = at.table[0].value
    assert (nv.index[0], nv.iloc[0]['Kết quả']) == ('assert_rpt_driver', 'Không đạt (3 dòng lệch)')
    ct = at.dataframe[1].value                                            # bảng chi tiết lỗi
    assert ct['Thông báo của dbt'].tolist() == ['Got 3 results, configured to fail if != 0']
    assert at.dataframe[-1].value['Test không đạt'].tolist()[0] == '1'    # lịch sử


def test_kho_dung_lai_sau_lan_kiem_thi_bao_cu(monkeypatch, tmp_path):
    db = _ban_sao(tmp_path, "update ops.dbt_invocation set started_at_utc = started_at_utc - interval 1 day")
    at = _open(monkeypatch, 'duckdb', db)
    assert '**Kết quả test có thể đã cũ:**' in at.warning[0].value and not at.success


def test_chi_kiem_mot_phan_thi_bao_thieu(monkeypatch, tmp_path):
    s = queries.health_summary('duckdb').iloc[0]          # kho thật, đọc trước khi trỏ app sang bản sao
    db = _ban_sao(tmp_path, "delete from ops.dbt_node_result where resource_type = 'test' and test_kind = 'not_null'")
    at = _open(monkeypatch, 'duckdb', db)
    con = duckdb.connect(str(db), read_only=True)
    con_lai = con.execute('select n_tests_run from reporting.rpt_health_summary').fetchone()[0]
    con.close()
    assert con_lai < s['n_tests_run']
    assert (f'**Lần kiểm gần nhất chỉ chạy một phần:** {num(con_lai)}/{num(s["n_tests_in_project"])} test'
            in at.warning[0].value)


def test_chua_co_nhat_ky_thi_bao_vang_khong_loi(monkeypatch, tmp_path):
    db = _ban_sao(tmp_path, 'delete from ops.dbt_node_result; delete from ops.dbt_invocation')
    at = _open(monkeypatch, 'duckdb', db)
    assert not at.error
    assert '**Chưa có kết quả test trên kho này.**' in at.warning[0].value
    assert list(_the(at)) == ['Dữ liệu tới ngày']


TRANG = ['views/tong_quan.py', 'views/ps1_do_dung.py', 'views/ps2_xu_huong.py', 'views/ps3_nhip_lich.py',
         'views/ps4_don_mon_gia.py', 'views/ps5_nhom.py', PAGE]
DUOC_RONG = {'health_test', 'health_ingest', 'health_run'}   # load_or_stop(allow_empty=True): trang tự xử lý


@pytest.mark.parametrize('page', TRANG)
def test_moi_bang_trang_doc_ma_rong_thi_khong_van_loi(monkeypatch, page):
    # review 2026-09-29: bảng rpt_* rỗng không được làm trang văng lỗi (.iloc[0] / .loc[...] trên DataFrame rỗng).
    # Lấy danh sách bảng trang thật sự đọc, rồi lần lượt cho từng bảng trả về 0 dòng.
    doc = list(_open(monkeypatch, 'duckdb', page=page).session_state['_reads'])
    assert 'build_info' in doc and len(doc) >= 2
    for q in doc:
        with monkeypatch.context() as m:
            goc = getattr(queries, q)
            m.setattr(queries, q, lambda b, goc=goc: goc(b).iloc[0:0])
            at = _open(monkeypatch, 'duckdb', page=page)
            if q not in DUOC_RONG:
                assert any(f'`{queries.SOURCE[q]}`' in w.value and 'không có dòng nào' in w.value
                           for w in at.warning), (page, q)
                assert not at.metric and not at.dataframe, (page, q)   # dừng trước khi vẽ số


LECH = {'bo_dong_dau': lambda df: df.iloc[1:], 'bo_dong_cuoi': lambda df: df.iloc[:-1],
        'chi_con_dong_dau': lambda df: df.iloc[:1]}


@pytest.mark.parametrize('page', TRANG)
def test_bang_lech_nhau_thi_khong_van_loi(monkeypatch, page):
    # bảng có dòng nhưng thiếu năm/kỳ/nhóm mà bảng khác có (vd. kho dựng dở giữa hai lần build): trang không được văng lỗi
    # khi lọc/chọn dòng; thiếu dòng cần dùng thì cảnh báo nêu tên bảng rồi dừng. Bình thường dbt giữ các bảng khớp nhau.
    doc = list(_open(monkeypatch, 'duckdb', page=page).session_state['_reads'])
    that = {q: getattr(queries, q)('duckdb') for q in doc}          # đọc DB 1 lần, các lượt sau lấy từ bộ nhớ
    for q in doc:
        monkeypatch.setattr(queries, q, lambda b, q=q: that[q].copy())
    loi = []
    for q in doc:
        for ten, cat in LECH.items():
            with monkeypatch.context() as m:
                m.setattr(queries, q, lambda b, q=q, cat=cat: cat(that[q]).copy())
                st.cache_data.clear()
                at = AppTest.from_file(str(APP), default_timeout=30).run()
                if page != 'views/tong_quan.py':
                    at.switch_page(page).run()
                if at.exception:
                    noi = [x for x in at.exception[0].stack_trace if 'views' in x or 'ui' in x]
                    loi.append(f'{q} / {ten}: {at.exception[0].message} @ {noi[-1:] }')
    assert not loi, '\n'.join(loi)


@pytest.mark.parametrize('page, q, bo, bang, cau', [
    ('views/tong_quan.py', 'revenue_total', lambda d: d[d['is_analysis_period']], 'rpt_revenue_total',
     'của kỳ toàn bộ dữ liệu'),
    ('views/ps5_nhom.py', 'driver_period', lambda d: d[d['period_code'] != '2019'], 'rpt_driver_period', 'của năm 2019'),
    ('views/ps5_nhom.py', 'segment_yearly', lambda d: d[~((d['year'] == 2019) & (d['dimension_name'] == 'category'))],
     'rpt_revenue_segment_yearly', 'của ngành hàng năm 2019'),
    ('views/ps3_nhip_lich.py', 'calendar_stability', lambda d: d[d['rhythm_code'] != 'mua_vu'], 'rpt_calendar_stability',
     'của nhịp mùa vụ'),
])
def test_bang_lech_thi_bao_ro_bang_nao_thieu_gi(monkeypatch, page, q, bo, bang, cau):
    goc = getattr(queries, q)
    monkeypatch.setattr(queries, q, lambda b: bo(goc(b)))
    at = _open(monkeypatch, 'duckdb', page=page)
    w = [x.value for x in at.warning if 'thiếu dòng' in x.value]
    assert len(w) == 1 and f'`reporting.{bang}`' in w[0] and cau in w[0], [x.value for x in at.warning]
    assert 'Sức khỏe dữ liệu' in w[0]


def test_bang_rong_thi_bao_vang_khong_ve_so(monkeypatch, tmp_path):
    # hoàn thiện M5: bảng rpt_* rỗng (kho dựng dở) → cảnh báo có hướng xử lý, không văng lỗi, không vẽ số
    db = _ban_sao(tmp_path, 'delete from reporting.rpt_revenue_yearly')
    at = _open(monkeypatch, 'duckdb', db, page='views/tong_quan.py')
    assert not at.error
    assert 'reporting.rpt_revenue_yearly' in at.warning[0].value and 'không có dòng nào' in at.warning[0].value
    assert not at.dataframe
