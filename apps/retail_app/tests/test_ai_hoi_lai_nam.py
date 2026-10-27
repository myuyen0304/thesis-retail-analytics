"""NY: kiểm trọn lượt chat với mô hình giả, không gọi API."""
import re

import pytest

from ai_explain import service, tools
from ai_explain.contracts import ToolResult
from scripts.ops import ai_live_eval
from tests.test_ai_chat import FakeProvider, call, final
from tests.test_ai_forecast import ref, versioned  # noqa: F401 (fixture)


def _run(question, *steps, history=()):
    return service.run_turn(question, list(history), 'duckdb', FakeProvider(*steps))


def _forecast_answer(year=2023, month=4, tool='get_forecast'):
    path = 'T1.rows[0].g_forecast' if tool == 'get_forecast' else 'T1.rows[0].pct_vs_base'
    return final(answer=f'Dự báo G tháng {month}/{year} là {{c1}}.', claims=[{'id': 'c1', 'path': path}])


def _assert_clarifies(t):
    assert t.status == 'needs_clarification', (t.status, t.validation_errors)
    assert not t.values
    assert not re.search(r'\d+\s*(?:VND|triệu|tỷ)', (t.answer_md or '') + t.message, re.I)
    assert all(not r.ok and not r.rows and not r.derived for r in t.results.values())


@pytest.mark.parametrize('question,tool,args', [
    ('Dự báo tháng 4 là bao nhiêu?', 'get_forecast', {'metric': 'G', 'period': 'month', 'year': 2023, 'month': 4}),
    ('Dự báo tháng 9 là bao nhiêu?', 'get_forecast', {'metric': 'G', 'period': 'month', 'year': 2023, 'month': 9}),
    ('Ngày 14/8 dự báo G bao nhiêu?', 'get_forecast', {'metric': 'G', 'period': 'day', 'year': 2023, 'month': 8, 'day': 14}),
    ('Vì sao dự báo G tháng 8 thấp?', 'explain_forecast', {'period': 'month', 'year': 2023, 'month': 8}),
    ('Tháng 4 dự báo giá vốn bao nhiêu?', 'get_forecast', {'metric': 'COGS', 'period': 'month', 'year': 2024, 'month': 4}),
    ('Dự báo tháng 4 năm sau là bao nhiêu?', 'get_forecast', {'metric': 'G', 'period': 'month', 'year': 2024, 'month': 4}),
    ('Dự báo 4/24 là bao nhiêu?', 'get_forecast', {'metric': 'G', 'period': 'month', 'year': 2024, 'month': 4}),
    ('T4/23 dự báo G?', 'get_forecast', {'metric': 'G', 'period': 'month', 'year': 2023, 'month': 4}),
])
def test_ny_t1_t3_t4_t5_t6_t15_viet_tat_khong_tu_chon_nam(monkeypatch, question, tool, args):
    def no_read(*_args, **_kwargs):
        raise AssertionError('Không được đọc kho dự báo khi thiếu năm')
    monkeypatch.setattr(tools, 'run', no_read)
    t = _run(question, call(tool, **args), _forecast_answer(tool=tool))
    _assert_clarifies(t)
    assert t.results['T1'].status == 'needs_clarification'


def test_ny_t2_hai_nam_deu_bi_chan(monkeypatch):
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho'))
    t = _run('Dự báo tháng 4 là bao nhiêu?',
             call('get_forecast', metric='G', period='month', year=2023, month=4),
             call('get_forecast', metric='G', period='month', year=2024, month=4),
             _forecast_answer())
    _assert_clarifies(t)
    assert len(t.calls) == 2


def test_ny_t7_duong_vong_horizon_bi_kiem_cau_cuoi(monkeypatch):
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho'))
    t = _run('Dự báo tháng 4 là bao nhiêu?', call('get_forecast', metric='G', period='horizon'),
             final(answer='Dự báo G tháng 4/2023 là {c1}.',
                   claims=[{'id': 'c1', 'path': 'T1.rows[3].g_forecast'}]))
    _assert_clarifies(t)
    assert t.results['T1'].status == 'needs_clarification'
    assert any('chưa có năm' in e for e in t.validation_errors)


def test_ny_t8_hoi_lai_sach():
    t = _run('Dự báo tháng 4 là bao nhiêu?',
             final('needs_clarification', 'Bạn muốn dự báo tháng 4 năm 2023 hay 2024?'))
    assert t.status == 'needs_clarification' and not t.values
    assert t.answer_md and '2023' in t.answer_md and '2024' in t.answer_md


def test_ny_rubric_hoi_lai_chan_so_tien_va_tool_ok():
    case = ai_live_eval.ACCEPT_NY[0]
    t = service.TurnResult('needs_clarification', case['q'], answer_md='Bạn muốn năm 2023 hay 2024?')
    assert ai_live_eval.grade(case, t)['pass']
    t.answer_md = 'Bạn muốn năm nào? Số 2.000.000'
    assert not ai_live_eval.grade(case, t)['checks']['hoi_nam_sach']
    t.answer_md = 'Bạn muốn năm 2023 hay 2024?'
    t.calls = [('T1', 'get_forecast', {'year': 2023})]
    t.results = {'T1': ToolResult('ok', 'đã đọc')}
    assert not ai_live_eval.grade(case, t)['checks']['hoi_nam_sach']


def test_ny_t9_co_nam_lay_dung_so(versioned):
    t = _run('Dự báo tháng 4/2024 là bao nhiêu?',
             call('get_forecast', metric='G', period='month', year=2024, month=4), _forecast_answer(2024))
    assert t.status == 'ok', t.validation_errors
    assert t.results['T1'].ok and t.values['c1'][1] == t.results['T1'].rows[0]['g_forecast']


def _previous(question):
    t = _run(question, final('needs_clarification', 'Bạn muốn hỏi kỳ nào?'))
    return t.context()


def test_ny_t10_lay_nam_tu_cau_nguoi_dung_luot_truoc(versioned):
    previous = _previous('Dự báo doanh thu gộp tháng 10/2023 là bao nhiêu?')
    t = _run('Còn tháng 4 thì sao?',
             call('get_forecast', metric='G', period='month', year=2023, month=4), _forecast_answer(),
             history=[previous])
    assert t.status == 'ok', t.validation_errors
    assert '2023' in t.answer_md


def test_ny_t11_sai_nam_luot_truoc_bi_chan(monkeypatch):
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho'))
    previous = _previous('Dự báo doanh thu gộp tháng 10/2023 là bao nhiêu?')
    t = _run('Còn tháng 4 thì sao?',
             call('get_forecast', metric='G', period='month', year=2024, month=4), _forecast_answer(2024),
             history=[previous])
    assert t.status != 'ok' and not t.values and not t.results['T1'].ok


def test_ny_t12_hai_nam_luot_truoc_bi_chan(monkeypatch):
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho'))
    previous = _previous('So sánh dự báo tháng 4/2023 và 4/2024')
    t = _run('Còn tháng 5?', call('get_forecast', metric='G', period='month', year=2023, month=5),
             _forecast_answer(month=5), history=[previous])
    _assert_clarifies(t)


def test_ny_t13_nam_chi_trong_tham_so_tool_khong_du(monkeypatch):
    previous = _run('Dự báo tháng 4 là bao nhiêu?',
                    call('get_forecast', metric='G', period='month', year=2023, month=4),
                    final('needs_clarification', 'Bạn muốn năm nào?')).context()
    assert previous['tool_calls'][0]['arguments']['year'] == 2023
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho'))
    t = _run('Còn tháng 5?', call('get_forecast', metric='G', period='month', year=2023, month=5),
             _forecast_answer(month=5), history=[previous])
    _assert_clarifies(t)


def test_ny_t14_dap_rieng_nam_sau_hoi_lai(versioned):
    previous = _run('Dự báo tháng 4 là bao nhiêu?',
                    final('needs_clarification', 'Bạn muốn năm nào?')).context()
    t = _run('năm 2024', call('get_forecast', metric='G', period='month', year=2024, month=4),
             _forecast_answer(2024), _forecast_answer(2024), history=[previous])
    assert t.status == 'ok', t.validation_errors
    assert '2024' in t.answer_md and t.results['T1'].ok


@pytest.mark.parametrize('previous_question,year,args,answer', [
    ('Dự báo G ngày 14/8 thế nào?', 2023,
     {'metric': 'G', 'period': 'day', 'year': 2023, 'month': 8, 'day': 14},
     'Dự báo G ngày 14/8/2023 là {c1}.'),
    ('T4/23 dự báo G?', 2024,
     {'metric': 'G', 'period': 'month', 'year': 2024, 'month': 4},
     'Dự báo G tháng 4/2024 là {c1}.'),
])
def test_ny_l5_dap_nam_cho_ngay_va_viet_tat(versioned, previous_question, year, args, answer):
    previous = _run(previous_question, final('needs_clarification', 'Bạn muốn năm nào?')).context()
    t = _run(str(year), call('get_forecast', **args),
             final(answer=answer, claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}]), history=[previous])
    assert t.status == 'ok', t.validation_errors
    assert str(year) in t.answer_md and t.results['T1'].ok


def test_ny_t16_so_thuc_te_khong_anh_huong(versioned):
    t = _run('Doanh thu R năm 2019 là bao nhiêu?',
             call('get_revenue_summary', metric='R', year=2019),
             final(answer='R năm 2019 là {c1}.', claims=[{'id': 'c1', 'path': 'T1.rows[0].r'}]))
    assert t.status == 'ok', t.validation_errors


def test_r1_nam_thuc_te_khong_cap_nam_du_bao(monkeypatch):
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho dự báo'))
    t = _run('Dự báo tháng 4 so với thực tế tháng 4/2022 thế nào?',
             call('get_forecast', metric='G', period='month', year=2023, month=4), _forecast_answer())
    _assert_clarifies(t)
    assert t.results['T1'].status == 'needs_clarification'


def test_r1_nam_thuc_te_khong_mo_duong_vong_horizon(monkeypatch):
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho dự báo'))
    t = _run('Dự báo tháng 4 so với thực tế tháng 4/2022 thế nào?',
             call('get_forecast', metric='G', period='horizon'), _forecast_answer())
    _assert_clarifies(t)
    assert t.results['T1'].status == 'needs_clarification'


def test_r1_nam_ngoai_ky_2025_van_no_data(versioned):
    t = _run('Dự báo tháng 4/2025 là bao nhiêu?',
             call('get_forecast', metric='G', period='month', year=2025, month=4),
             final('no_data', 'Tháng 4/2025 nằm ngoài kỳ dự báo, không có số.'))
    assert t.status == 'no_data' and not t.values
    assert t.results['T1'].status == 'no_data'


def test_r1_cau_31_co_nam_du_bao_va_nam_thuc_te(versioned):
    t = _run('Tháng 9/2023 dự báo cao hơn hay thấp hơn tháng 9/2022 thực tế bao nhiêu phần trăm?',
             call('get_forecast', metric='G', period='month', year=2023, month=9),
             _forecast_answer(2023, 9))
    assert t.status == 'ok', t.validation_errors
    assert t.results['T1'].ok and t.values['c1'][1] == t.results['T1'].rows[0]['g_forecast']


@pytest.mark.parametrize('reply', ['2023 nhé', 'năm 2023 ạ', 'lấy 2023'])
def test_r2_dap_nam_tu_nhien_cho_ngay(versioned, reply):
    previous = _run('Dự báo G ngày 14/8 thế nào?',
                    final('needs_clarification', 'Bạn muốn năm nào?')).context()
    answer = final(answer='Dự báo G ngày 14/8/2023 là {c1}.',
                   claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}])
    t = _run(reply, call('get_forecast', metric='G', period='day', year=2023, month=8, day=14),
             answer, history=[previous])
    assert t.status == 'ok', t.validation_errors
    assert '2023' in t.answer_md and t.results['T1'].ok


@pytest.mark.parametrize('label,month', [
    ('T4', 4), ('tháng một', 1), ('THÁNG GIÊNG', 1), ('tháng hai', 2), ('tháng ba', 3),
    ('tháng tư', 4), ('tháng bốn', 4), ('tháng năm', 5), ('tháng sáu', 6),
    ('tháng bảy', 7), ('tháng tám', 8), ('tháng chín', 9), ('tháng mười', 10),
    ('tháng mười một', 11), ('tháng mười hai', 12), ('tháng chạp', 12),
])
def test_r3_thang_viet_tat_hoac_viet_chu_phai_hoi_nam(monkeypatch, label, month):
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho dự báo'))
    question = f'Dự báo {label} là bao nhiêu?'
    t = _run(question, call('get_forecast', metric='G', period='month', year=2023, month=month),
             _forecast_answer(2023, month))
    _assert_clarifies(t)


@pytest.mark.parametrize('previous_question,month', [('Dự báo T4 là bao nhiêu?', 4),
                                                      ('Dự báo tháng tư là bao nhiêu?', 4),
                                                      ('Dự báo tháng năm là bao nhiêu?', 5)])
def test_r3_dap_nam_sau_thang_viet_chu(versioned, previous_question, month):
    previous = _run(previous_question, final('needs_clarification', 'Bạn muốn năm nào?')).context()
    t = _run('2023 nhé', call('get_forecast', metric='G', period='month', year=2023, month=month),
             _forecast_answer(2023, month), history=[previous])
    assert t.status == 'ok', t.validation_errors
    assert t.results['T1'].ok


@pytest.mark.parametrize('question', [
    'Dự báo tháng 4 so với tháng 4/2022 thế nào?',
    'So với tháng 4/2022, dự báo tháng 4 thế nào?',
    'Dự báo tháng 4 có cao hơn năm 2022 không?',
    'Dự báo tháng 4 so với cùng kỳ 2022?',
    'Dự báo tháng 4 so với cùng tháng năm 2022 thế nào?',
    'Dự báo tháng 4 tăng bao nhiêu so với 2021?',
    'Dự báo T4 so với T4/2022?',
    'Dự báo tháng 4/2022 là bao nhiêu?',
])
@pytest.mark.parametrize('period', ['month', 'horizon'])
def test_r1b_nam_lich_su_khong_mo_tool_du_bao(monkeypatch, question, period):
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho dự báo'))
    args = {'metric': 'G', 'period': period}
    if period == 'month':
        args.update(year=2023, month=4)
    t = _run(question, call('get_forecast', **args), _forecast_answer())
    if question == 'Dự báo tháng 4/2022 là bao nhiêu?':
        assert t.status == 'no_data' and not t.values and not t.results['T1'].rows
        assert t.results['T1'].status == 'no_data'
    else:
        _assert_clarifies(t)
        assert t.results['T1'].status == 'needs_clarification'


def test_r1b_l6_hoi_ca_ky_van_doc_duoc(versioned):
    t = _run('Dự báo cả kỳ là bao nhiêu?', call('get_forecast', metric='G', period='horizon'),
             final(answer='Tổng dự báo G cả kỳ là {c1}.',
                   claims=[{'id': 'c1', 'path': 'T1.derived.horizon_total.g_forecast'}]))
    assert t.status == 'ok', t.validation_errors
    assert t.results['T1'].ok and t.values['c1'][1] == t.results['T1'].derived['horizon_total']['g_forecast']


def test_r1b_l6_hoi_nam_2024_van_doc_duoc(versioned):
    t = _run('Dự báo G cả năm 2024 là bao nhiêu?',
             call('get_forecast', metric='G', period='year', year=2024),
             final(answer='Dự báo G năm 2024 là {c1}; phần chưa có là {c2}.',
                   claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'},
                           {'id': 'c2', 'path': 'T1.derived.missing_part'}]))
    assert t.status == 'ok', t.validation_errors
    assert t.results['T1'].ok and t.values['c1'][1] == t.results['T1'].rows[0]['g_forecast']


def test_r1b_l6_thang_co_nam_doc_qua_horizon_van_duoc(versioned):
    t = _run('Dự báo tháng 4/2023 là bao nhiêu?',
             call('get_forecast', metric='G', period='horizon'),
             final(answer='Dự báo G tháng 4/2023 là {c1}.',
                   claims=[{'id': 'c1', 'path': 'T1.rows[3].g_forecast'}]))
    assert t.status == 'ok', t.validation_errors
    assert t.results['T1'].ok and t.values['c1'][1] == t.results['T1'].rows[3]['g_forecast']


def test_r1b_thang_2025_khong_hien_so_tham_khao_nam_2023(monkeypatch):
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho dự báo'))
    t = _run('Dự báo doanh thu tháng 8/2025?',
             call('get_forecast', metric='G', period='month', year=2023, month=8),
             _forecast_answer(2023, 8))
    assert t.status == 'no_data' and not t.values
    assert '8/2025' in t.message and '01/01/2023' in t.message and '01/07/2024' in t.message
    assert 'năm nào' not in t.message.lower()
    assert t.results['T1'].status == 'no_data' and not t.results['T1'].rows


def _r5_history():
    first = _run('Dự báo tháng tư là bao nhiêu?',
                 final('needs_clarification', 'Bạn muốn năm nào?'))
    second = _run('2024 nhé', call('get_forecast', metric='G', period='month', year=2024, month=4),
                  _forecast_answer(2024), history=[first.context()])
    assert second.status == 'ok', second.validation_errors
    return [first.context(), second.context()]


@pytest.mark.parametrize('tool,args', [
    ('get_forecast', {'metric': 'G', 'period': 'month', 'year': 2023, 'month': 5}),
    ('explain_forecast', {'period': 'month', 'year': 2023, 'month': 5}),
])
def test_r5_sau_dap_nam_khong_doc_nam_model_tu_chon(versioned, monkeypatch, tool, args):
    history = _r5_history()
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho dự báo'))
    t = _run('Còn tháng năm?',
             call(tool, **args), _forecast_answer(2023, 5, tool), history=history)
    _assert_clarifies(t)
    assert t.results['T1'].status == 'needs_clarification'


def test_r5_sau_dap_nam_doc_dung_nam_2024(versioned):
    t = _run('Còn tháng năm?',
             call('get_forecast', metric='G', period='month', year=2024, month=5),
             _forecast_answer(2024, 5), history=_r5_history())
    assert t.status == 'ok', t.validation_errors
    assert t.results['T1'].ok and '2024' in t.answer_md


def test_r5_so_sanh_nam_hien_tai_va_nam_ngay_truoc(versioned):
    previous = _run('Dự báo tháng 4/2023 là bao nhiêu?',
                    call('get_forecast', metric='G', period='month', year=2023, month=4),
                    _forecast_answer())
    assert previous.status == 'ok', previous.validation_errors
    t = _run('So sánh với tháng 4/2024',
             call('get_forecast', metric='G', period='month', year=2023, month=4),
             call('get_forecast', metric='G', period='month', year=2024, month=4),
             final(answer='Dự báo G tháng 4/2023 là {c1}; tháng 4/2024 là {c2}.',
                   claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'},
                           {'id': 'c2', 'path': 'T2.rows[0].g_forecast'}]), history=[previous.context()])
    assert t.status == 'ok', t.validation_errors
    assert t.results['T1'].ok and t.results['T2'].ok


@pytest.mark.parametrize('question', ['Còn năm sau thì sao?', 'Năm sau thì sao?', 'Còn năm tới?'])
@pytest.mark.parametrize('tool,args', [
    ('get_forecast', {'metric': 'G', 'period': 'month', 'year': 2024, 'month': 4}),
    ('explain_forecast', {'period': 'month', 'year': 2024, 'month': 4}),
])
def test_r6_nam_tuong_doi_khong_doc_nam_model_chon(versioned, monkeypatch, question, tool, args):
    previous = _run('Dự báo tháng 4/2023 là bao nhiêu?',
                    call('get_forecast', metric='G', period='month', year=2023, month=4),
                    _forecast_answer())
    assert previous.status == 'ok', previous.validation_errors
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho dự báo'))
    t = _run(question, call(tool, **args), _forecast_answer(2024, 4, tool), history=[previous.context()])
    _assert_clarifies(t)
    assert t.results['T1'].status == 'needs_clarification'


def test_r6_nam_2024_go_ro_tool_duoc_doc(versioned, monkeypatch):
    previous = _run('Dự báo tháng 4/2023 là bao nhiêu?',
                    call('get_forecast', metric='G', period='month', year=2023, month=4),
                    _forecast_answer())
    assert previous.status == 'ok', previous.validation_errors
    original_run = tools.run
    calls = []

    def recorded_run(*args, **kwargs):
        calls.append(args[0])
        return original_run(*args, **kwargs)

    monkeypatch.setattr(tools, 'run', recorded_run)
    t = _run('Thế còn 2024?', call('get_forecast', metric='G', period='month', year=2024, month=4),
             _forecast_answer(2024), _forecast_answer(2024), history=[previous.context()])
    assert calls and calls[0].tool == 'get_forecast'
    assert t.results['T1'].ok and t.results['T1'].rows


@pytest.mark.parametrize('question,args', [
    ('Dự báo doanh thu tháng 8/2025?', {'metric': 'G', 'period': 'month', 'year': 2023, 'month': 8}),
    ('Dự báo doanh thu tháng 8/2025?', {'metric': 'G', 'period': 'month', 'year': 2025, 'month': 8}),
    ('Dự báo doanh thu tháng 1 và tháng 2/2025?',
     {'metric': 'G', 'period': 'month', 'year': 2023, 'month': 8}),
    ('Ngày 2/7/2025 dự báo G?', {'metric': 'G', 'period': 'day', 'year': 2023, 'month': 7, 'day': 2}),
])
def test_r7_thang_ngoai_ky_khong_doc_so_tham_khao(monkeypatch, question, args):
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho dự báo'))
    t = _run(question, call('get_forecast', **args),
             final('no_data', 'Không có dự báo cho kỳ này. Riêng tháng 8/2023, G là {c1}.',
                   [{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}]))
    assert t.status == 'no_data' and not t.values
    assert '2025' in t.message and '01/01/2023' in t.message and '01/07/2024' in t.message
    assert 'năm nào' not in t.message.lower()
    assert t.results['T1'].status == 'no_data' and not t.results['T1'].rows


def test_r7_cau_noi_tiep_thang_ngoai_ky_khong_doc_so(versioned, monkeypatch):
    previous = _run('Dự báo tháng 4/2023 là bao nhiêu?',
                    call('get_forecast', metric='G', period='month', year=2023, month=4),
                    _forecast_answer())
    assert previous.status == 'ok', previous.validation_errors
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho dự báo'))
    t = _run('Còn tháng 8/2025?',
             call('get_forecast', metric='G', period='month', year=2023, month=8),
             _forecast_answer(2023, 8), history=[previous.context()])
    assert t.status == 'no_data' and not t.values
    assert '8/2025' in t.message and t.results['T1'].status == 'no_data'


@pytest.mark.parametrize('question,tool,args', [
    ('Dự báo 4/2024?', 'get_forecast', {'metric': 'G', 'period': 'month', 'year': 2023, 'month': 4}),
    ('Giải thích dự báo 4/2024?', 'explain_forecast', {'period': 'month', 'year': 2023, 'month': 4}),
])
def test_r8_ky_m_nam_chan_tool_sai_nam(monkeypatch, question, tool, args):
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho dự báo'))
    t = _run(question, call(tool, **args), _forecast_answer(2023, 4, tool))
    _assert_clarifies(t)
    assert t.results['T1'].status == 'needs_clarification'


def test_r8_ky_m_nam_dung_nam_van_doc_duoc(versioned):
    t = _run('Dự báo 4/2024?',
             call('get_forecast', metric='G', period='month', year=2024, month=4), _forecast_answer(2024))
    assert t.status == 'ok', t.validation_errors
    assert t.results['T1'].ok


@pytest.mark.parametrize('question', ['Sang năm thì sao?', 'Còn năm tiếp theo?', 'Qua năm kế tiếp thì sao?'])
@pytest.mark.parametrize('tool,args', [
    ('get_forecast', {'metric': 'G', 'period': 'month', 'year': 2024, 'month': 4}),
    ('explain_forecast', {'period': 'month', 'year': 2024, 'month': 4}),
])
def test_r6b_khong_go_nam_moi_thi_khong_doc_nam_khac(versioned, monkeypatch, question, tool, args):
    previous = _run('Dự báo tháng 4/2023?',
                    call('get_forecast', metric='G', period='month', year=2023, month=4),
                    _forecast_answer())
    assert previous.status == 'ok', previous.validation_errors
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho dự báo'))
    t = _run(question, call(tool, **args), _forecast_answer(2024, 4, tool), history=[previous.context()])
    _assert_clarifies(t)
    assert t.results['T1'].status == 'needs_clarification'


@pytest.mark.parametrize('question', ['So với cùng kỳ năm trước thì sao?', 'So với năm ngoái thì sao?'])
def test_r6c_so_sanh_doc_dung_nam_nguoi_dung_da_go(versioned, monkeypatch, question):
    previous = _run('Dự báo tháng 4/2023?',
                    call('get_forecast', metric='G', period='month', year=2023, month=4),
                    _forecast_answer())
    assert previous.status == 'ok', previous.validation_errors
    original_run = tools.run
    calls = []

    def recorded_run(*args, **kwargs):
        calls.append(args[0])
        return original_run(*args, **kwargs)

    monkeypatch.setattr(tools, 'run', recorded_run)
    t = _run(question, call('get_forecast', metric='G', period='month', year=2023, month=4),
             _forecast_answer(), history=[previous.context()])
    assert t.status == 'ok', t.validation_errors
    assert t.results['T1'].ok and calls and calls[0].arguments['year'] == 2023


def test_r6c_dau_phien_nam_tuong_doi_van_hoi_lai(monkeypatch):
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho dự báo'))
    t = _run('Dự báo doanh thu năm nay?',
             call('get_forecast', metric='G', period='year', year=2023),
             final(answer='Dự báo G năm 2023 là {c1}.', claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}]))
    _assert_clarifies(t)
    assert t.results['T1'].status == 'needs_clarification'


@pytest.mark.parametrize('question,asked_period', [
    ('Doanh thu tháng 8/2025 là bao nhiêu?', 'tháng 8/2025'),
    ('Tháng 9/2025 thì sao?', 'tháng 9/2025'),
    ('Dự báo 4/2022?', 'tháng 4/2022'),
    ('Dự báo G 4/2022?', 'tháng 4/2022'),
    ('Dự báo ngày 31/12/2022?', 'ngày 31/12/2022'),
    ('Còn 8/2025?', 'tháng 8/2025'),
])
def test_r7b_ky_ngoai_pham_vi_khong_doc_so_va_ghi_dung_ky(monkeypatch, question, asked_period):
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho dự báo'))
    previous = _previous('Dự báo tháng 4/2023?')
    t = _run(question, call('get_forecast', metric='G', period='month', year=2023, month=8),
             _forecast_answer(2023, 8), history=[previous])
    assert t.status == 'no_data' and not t.values
    assert t.results['T1'].status == 'no_data' and not t.results['T1'].rows
    assert asked_period in t.message and '01/01/2023' in t.message and '01/07/2024' in t.message
    assert question.rstrip('?!') not in t.message and 'năm nào' not in t.message.lower()


def test_r7b_ngoai_ky_sau_khi_mo_phien_khong_can_chu_du_bao(monkeypatch):
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho dự báo'))
    t = _run('Doanh thu tháng 8/2025 là bao nhiêu?',
             call('get_forecast', metric='G', period='month', year=2023, month=8),
             _forecast_answer(2023, 8))
    assert t.status == 'no_data' and t.results['T1'].status == 'no_data'
    assert not t.values and 'tháng 8/2025' in t.message


def test_r7b_thang_thuc_te_truoc_ky_khong_bi_chan(versioned):
    t = _run('Doanh thu R tháng 3/2022 là bao nhiêu?',
             call('get_revenue_monthly', metric='R', year=2022, month=3),
             final(answer='R tháng 3/2022 là {c1}.', claims=[{'id': 'c1', 'path': 'T1.rows[0].r'}]))
    assert t.status == 'ok', t.validation_errors
    assert t.results['T1'].ok


def test_r7b_thang_trong_ky_khong_bi_bao_ngoai_ky(versioned):
    t = _run('Dự báo tháng 7/2024?',
             call('get_forecast', metric='G', period='month', year=2024, month=7), _forecast_answer(2024, 7))
    assert t.status == 'ok', t.validation_errors
    assert t.results['T1'].ok


def test_r9_cau_rag_nam_nao_khong_bi_luat_nam_du_bao_chan():
    t = _run('Mô hình dự báo dùng dữ liệu của những năm nào?',
             call('search_knowledge', query='dữ liệu huấn luyện mô hình dự báo'),
             final(answer='Tài liệu mô tả các năm dữ liệu dùng để huấn luyện mô hình.'))
    assert t.status == 'ok', t.validation_errors
    assert [name for _, name, _ in t.calls] == ['search_knowledge']


def test_r9_cau_thuc_te_noi_sau_du_bao_khong_bi_chan(versioned):
    previous = _run('Tổng dự báo doanh thu cả vùng dự báo là bao nhiêu?',
                    call('get_forecast', metric='G', period='horizon'),
                    final(answer='Tổng dự báo G cả kỳ là {c1}.',
                          claims=[{'id': 'c1', 'path': 'T1.derived.horizon_total.g_forecast'}]))
    assert previous.status == 'ok', previous.validation_errors
    t = _run('Năm nào doanh thu thực tế cao nhất?',
             call('get_revenue_summary', metric='R', year=2022),
             final(answer='R thực tế năm 2022 là {c1}.',
                   claims=[{'id': 'c1', 'path': 'T1.rows[0].r'}]), history=[previous.context()])
    assert t.status == 'ok', t.validation_errors
    assert [name for _, name, _ in t.calls] == ['get_revenue_summary']


@pytest.mark.parametrize('question,year,month', [
    ('Dự báo 4-2024?', 2024, 4),
    ('Dự báo 2024/4?', 2024, 4),
    ('Dự báo 8-2025?', 2025, 8),
    ('Dự báo 2025/8?', 2025, 8),
])
def test_r8b_cach_viet_thang_khac_dung_chung_guard(monkeypatch, question, year, month):
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho dự báo'))
    t = _run(question,
             call('get_forecast', metric='G', period='month', year=2023, month=month),
             _forecast_answer(2023, month))
    if year == 2025:
        assert t.status == 'no_data' and f'tháng {month}/{year}' in t.message
        assert t.results['T1'].status == 'no_data'
    else:
        _assert_clarifies(t)
        assert t.results['T1'].status == 'needs_clarification'


def test_r8b_thang_2024_dung_nam_van_doc_duoc(versioned):
    t = _run('Dự báo 2024/4?',
             call('get_forecast', metric='G', period='month', year=2024, month=4), _forecast_answer(2024))
    assert t.status == 'ok', t.validation_errors


def test_r10_cung_ky_nam_truoc_lay_tu_nam_da_go(versioned):
    t = _run('Dự báo tháng 4/2024 so với cùng kỳ năm trước?',
             call('get_forecast', metric='G', period='month', year=2024, month=4),
             call('get_forecast', metric='G', period='month', year=2023, month=4),
             final(answer='Dự báo G tháng 4/2024 là {c1}; cùng kỳ năm 2023 là {c2}.',
                   claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'},
                           {'id': 'c2', 'path': 'T2.rows[0].g_forecast'}]))
    assert t.status == 'ok', t.validation_errors
    assert all(t.results[ref].ok for ref in ('T1', 'T2'))
    assert '2024' in t.answer_md and '2023' in t.answer_md


def test_r10_nam_lien_truoc_la_thuc_te(versioned):
    t = _run('Dự báo tháng 4/2023 so với cùng kỳ năm trước?',
             call('get_forecast', metric='G', period='month', year=2023, month=4),
             call('get_revenue_monthly', metric='G', year=2022, month=4),
             final(answer='Dự báo G tháng 4/2023 là {c1}; G thực tế tháng 4/2022 là {c2}.',
                   claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'},
                           {'id': 'c2', 'path': 'T2.rows[0].g'}]))
    assert t.status == 'ok', t.validation_errors
    assert t.results['T1'].ok and t.results['T2'].ok
    assert '2023' in t.answer_md and '2022' in t.answer_md


def test_r10_khong_go_nam_van_phai_hoi_lai(monkeypatch):
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho dự báo'))
    t = _run('Dự báo tháng 4 so với cùng kỳ năm trước?',
             call('get_forecast', metric='G', period='month', year=2023, month=4),
             _forecast_answer())
    _assert_clarifies(t)


def test_r11_mo_hinh_sua_dung_nam_trong_cung_luot(versioned, monkeypatch):
    original_run = tools.run
    called = []

    def recorded_run(*args, **kwargs):
        called.append(args[0])
        return original_run(*args, **kwargs)

    monkeypatch.setattr(tools, 'run', recorded_run)
    t = _run('Dự báo tháng 4/2024?',
             call('get_forecast', metric='G', period='month', year=2023, month=4),
             call('get_forecast', metric='G', period='month', year=2024, month=4),
             final(answer='Dự báo G tháng 4/2024 là {c1}.',
                   claims=[{'id': 'c1', 'path': 'T2.rows[0].g_forecast'}]))
    assert t.status == 'ok', t.validation_errors
    assert t.results['T1'].status == 'needs_clarification' and not t.results['T1'].rows
    assert t.results['T2'].ok and len(called) == 1 and called[0].arguments['year'] == 2024
    assert '2024' in t.answer_md and 'năm nào' not in t.answer_md.lower()


@pytest.mark.parametrize('question', ['Dự báo 04.2024?', 'Dự báo kỳ 04@2024?'])
@pytest.mark.parametrize('tool', ['get_forecast', 'explain_forecast'])
@pytest.mark.parametrize('period', ['month', 'year'])
def test_r8c_nam_da_go_chan_doc_nam_khac_du_chua_nhan_ky(monkeypatch, question, tool, period):
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho sai năm'))
    args = {'period': period, 'year': 2023}
    if period == 'month':
        args['month'] = 4
    t = _run(question, call(tool, **args), _forecast_answer(tool=tool))
    _assert_clarifies(t)
    assert '2024' in t.results['T1'].message
    assert 'năm nào' not in t.message.lower()


@pytest.mark.parametrize('question,label', [
    ('Dự báo 14.08.2024?', 'ngày 14/8/2024'),
    ('Dự báo ngày 14-8-2024?', 'ngày 14/8/2024'),
    ('Dự báo 08.2024?', 'tháng 8/2024'),
])
def test_r11b_ngay_thang_ngoai_ky_nhan_dung(monkeypatch, question, label):
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho ngoài kỳ'))
    t = _run(question, call('get_forecast', metric='G', period='month', year=2023, month=8),
             _forecast_answer(2023, 8))
    assert t.status == 'no_data' and not t.values
    assert not t.results['T1'].rows and label in t.message
    assert 'năm nào' not in t.message.lower()


@pytest.mark.parametrize('phrase', ['năm ngoái', 'cùng kỳ năm ngoái', 'năm liền trước'])
def test_r10b_nam_ngoai_cung_nghia_nam_truoc(versioned, phrase):
    t = _run(f'Dự báo 4/2024 so với {phrase}?',
             call('get_forecast', metric='G', period='month', year=2024, month=4),
             call('get_forecast', metric='G', period='month', year=2023, month=4),
             final(answer='Dự báo G tháng 4/2024 là {c1}; tháng 4/2023 là {c2}.',
                   claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'},
                           {'id': 'c2', 'path': 'T2.rows[0].g_forecast'}]))
    assert t.status == 'ok', t.validation_errors
    assert t.results['T1'].ok and t.results['T2'].ok
    assert '2024' in t.answer_md and '2023' in t.answer_md


def test_r11b_chan_sai_nam_nhac_dung_ky_cho_model_va_nguoi_dung(monkeypatch):
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho sai năm'))
    provider = FakeProvider(call('get_forecast', metric='G', period='month', year=2023, month=4),
                            final(status='needs_clarification', answer='Bạn muốn dự báo năm nào?'))
    t = service.run_turn('Dự báo 4/2024?', [], 'duckdb', provider)
    _assert_clarifies(t)
    tool_message = next(m['content'] for m in provider.seen[-1] if m['role'] == 'tool')
    assert 'tháng 4/2024' in tool_message and 'năm nào' not in tool_message.lower()
    for message in (t.results['T1'].message, t.message or t.answer_md):
        assert 'tháng 4/2024' in message
        assert 'năm nào' not in message.lower()


def test_r11b_da_sua_tool_nhung_cau_cuoi_sai_nam(versioned):
    t = _run('Dự báo tháng 4/2024?',
             call('get_forecast', metric='G', period='month', year=2023, month=4),
             call('get_forecast', metric='G', period='month', year=2024, month=4),
             final(answer='Dự báo G tháng 4/2023 là {c1}.',
                   claims=[{'id': 'c1', 'path': 'T2.rows[0].g_forecast'}]))
    assert t.status != 'ok' and not t.values
    assert not t.results['T1'].rows and t.results['T2'].ok
    assert 'tháng 4/2024' in t.message and 'năm nào' not in t.message.lower()


def test_r8c_dau_cham_dung_ky_van_tra_so(versioned):
    t = _run('Dự báo 04.2024?',
             call('get_forecast', metric='G', period='month', year=2024, month=4), _forecast_answer(2024))
    assert t.status == 'ok', t.validation_errors
    assert t.results['T1'].ok and t.values


def test_r8c_giu_ngoai_le_nam_cau_ngay_truoc(versioned):
    previous = _run('Dự báo tháng 4/2023?',
                    call('get_forecast', metric='G', period='month', year=2023, month=4), _forecast_answer())
    assert previous.status == 'ok', previous.validation_errors
    t = _run('So sánh với tháng 4/2024?',
             call('get_forecast', metric='G', period='month', year=2023, month=4),
             call('get_forecast', metric='G', period='month', year=2024, month=4),
             final(answer='Dự báo G tháng 4/2023 là {c1}; tháng 4/2024 là {c2}.',
                   claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'},
                           {'id': 'c2', 'path': 'T2.rows[0].g_forecast'}]),
             history=[previous.context()])
    assert t.status == 'ok', t.validation_errors
    assert t.results['T1'].ok and t.results['T2'].ok


def test_r10b_nam_ngoai_khong_co_nam_goc_van_hoi_lai(monkeypatch):
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã tự chọn năm'))
    t = _run('Dự báo tháng 4 so với năm ngoái?',
             call('get_forecast', metric='G', period='month', year=2023, month=4), _forecast_answer())
    _assert_clarifies(t)


def test_r10b_khong_mo_so_sanh_ca_nam(versioned):
    answer = final(answer='Dự báo G năm 2024 là {c1}; năm 2023 là {c2}.',
                   claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'},
                           {'id': 'c2', 'path': 'T2.rows[0].g_forecast'}])
    t = _run('Dự báo năm 2024 so với năm ngoái?',
             call('get_forecast', metric='G', period='year', year=2024),
             call('get_forecast', metric='G', period='year', year=2023), answer, answer)
    assert t.status != 'ok' and not t.values


def test_r11b_khong_co_loi_tool_nhung_cau_cuoi_sai_nam(versioned):
    answer = final(answer='Dự báo G tháng 4/2023 là {c1}.',
                   claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}])
    t = _run('Dự báo tháng 4/2024?',
             call('get_forecast', metric='G', period='month', year=2024, month=4), answer, answer)
    assert t.status == 'answer_validation_failed' and not t.values
    assert 'tháng 4/2024' in t.message and 'năm nào' not in t.message.lower()


_LOI_KHAC = [
    final(answer='Dự báo G tháng 8/2023 là {c1}, cao nhất mọi thời đại vì khách hàng tăng mạnh.',
          claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}]),
    final(answer='Dự báo G tháng 8/2023 là 999 tỷ.'),
]


@pytest.mark.parametrize('bad', _LOI_KHAC, ids=['xep_hang', 'so_tu_viet'])
def test_r11c_doc_dung_nam_loi_khac_giu_cau_bao_cu(versioned, bad):
    t = _run('Dự báo tháng 8/2023 là bao nhiêu?',
             call('get_forecast', metric='G', period='month', year=2023, month=8), bad, bad)
    assert t.status == 'answer_validation_failed' and not t.values
    assert t.message.startswith('Câu diễn giải của mô hình không qua bước kiểm số')
    assert 'Bảng số bên dưới lấy thẳng từ kho' in t.message and 'Bạn đã hỏi' not in t.message


@pytest.mark.parametrize('bad', _LOI_KHAC, ids=['xep_hang', 'so_tu_viet'])
def test_r11c_cau_noi_doi_chung_giu_cau_bao_cu(versioned, bad):
    previous = _run('Dự báo tháng 4/2023?',
                    call('get_forecast', metric='G', period='month', year=2023, month=4), _forecast_answer())
    t = _run('Còn tháng 8 thì sao?', call('get_forecast', metric='G', period='month', year=2023, month=8), bad, bad,
             history=[previous.context()])
    assert t.status == 'answer_validation_failed' and not t.values
    assert t.message.startswith('Câu diễn giải của mô hình không qua bước kiểm số')


def test_r11c_cau_live_xep_hang_giu_cau_bao_cu(versioned):
    bad = final(answer='Nhóm kéo dự báo G tháng 1/2024 xuống mạnh nhất là ngày cuối tháng với {c1}.',
                claims=[{'id': 'c1', 'path': 'T1.rows[0].pct_vs_base'}])
    t = _run('Nhóm nào kéo dự báo G tháng 1/2024 xuống mạnh nhất?',
             call('explain_forecast', period='month', year=2024, month=1), bad, bad)
    assert t.status == 'answer_validation_failed' and not t.values, t.validation_errors
    assert t.message.startswith('Câu diễn giải của mô hình không qua bước kiểm số')


def test_r11c_loi_ky_that_van_neu_ky_khong_chep_loi_dan_mo_hinh(versioned):
    answer = final(answer='Dự báo G tháng 4/2023 là {c1}.',
                   claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}])
    t = _run('Dự báo tháng 4/2024?',
             call('get_forecast', metric='G', period='month', year=2024, month=4), answer, answer)
    assert t.status == 'answer_validation_failed' and not t.values
    assert 'tháng 4/2024' in t.message and 'Bảng số bên dưới lấy thẳng từ kho' in t.message
    assert 'năm khác thay thế' not in t.message


def test_r11c_chan_sai_nam_tach_loi_mo_hinh_va_nguoi_dung(monkeypatch):
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho sai năm'))
    provider = FakeProvider(call('get_forecast', metric='G', period='month', year=2023, month=4),
                            _forecast_answer(2023, 4))
    t = service.run_turn('Dự báo tháng 4/2024?', [], 'duckdb', provider)
    _assert_clarifies(t)
    tool_message = next(m['content'] for m in provider.seen[-1] if m['role'] == 'tool')
    assert 'năm khác thay thế' in tool_message
    assert 'tháng 4/2024' in t.message and 'năm khác thay thế' not in t.message


@pytest.mark.parametrize('phrase', ['so với cùng kỳ', 'YoY', 'so với năm vừa rồi'])
def test_r10c_cung_ky_tran_va_yoy_khi_go_mot_nam(versioned, phrase):
    t = _run(f'Dự báo tháng 4/2024 {phrase}?',
             call('get_forecast', metric='G', period='month', year=2024, month=4),
             call('get_forecast', metric='G', period='month', year=2023, month=4),
             final(answer='Dự báo G tháng 4/2024 là {c1}; tháng 4/2023 là {c2}.',
                   claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'},
                           {'id': 'c2', 'path': 'T2.rows[0].g_forecast'}]))
    assert t.status == 'ok', t.validation_errors
    assert t.results['T1'].ok and t.results['T2'].ok


@pytest.mark.parametrize('phrase', ['so với cùng kỳ', 'YoY'])
def test_r10c_khong_go_nam_van_hoi_lai(monkeypatch, phrase):
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã tự chọn năm'))
    t = _run(f'Dự báo tháng 4 {phrase}?',
             call('get_forecast', metric='G', period='month', year=2024, month=4), _forecast_answer(2024))
    _assert_clarifies(t)


@pytest.mark.parametrize('phrase', ['so với cùng kỳ tháng trước', 'so với cùng kỳ quý trước', 'so với cùng kỳ của tháng 3'])
def test_r10c_cung_ky_ky_khac_khong_doc_nam_truoc(versioned, monkeypatch, phrase):
    original_run = tools.run
    years = []

    def recorded_run(*args, **kwargs):
        years.append(args[0].arguments.get('year'))
        return original_run(*args, **kwargs)

    monkeypatch.setattr(tools, 'run', recorded_run)
    answer = final(answer='Dự báo G tháng 4/2024 là {c1}; tháng 4/2023 là {c2}.',
                   claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'},
                           {'id': 'c2', 'path': 'T2.rows[0].g_forecast'}])
    t = _run(f'Dự báo tháng 4/2024 {phrase}?',
             call('get_forecast', metric='G', period='month', year=2024, month=4),
             call('get_forecast', metric='G', period='month', year=2023, month=4), answer, answer)
    assert 2023 not in years and t.status != 'ok'
    assert t.results['T2'].status == 'needs_clarification' and not t.results['T2'].rows


def _hint(provider):
    return [m['content'] for m in provider.seen[0] if m['role'] == 'system' and 'đáp cho câu hỏi lại' in m['content']]


@pytest.mark.parametrize('reply', ['Năm 2024', '2024', 'lấy năm 2023'])
def test_ny9_dap_nam_sau_hoi_lai_co_goi_y_ky_da_hoi(versioned, reply):
    # live 2026-10-27: lượt trước không gọi tool thì mô hình hỏi xác nhận "tháng tư năm 2024 phải không?"
    previous = _run('Dự báo tháng 4 là bao nhiêu?', final('needs_clarification', 'Bạn muốn năm nào?')).context()
    assert previous['tool_calls'] == []
    year = int(re.search(r'\d{4}', reply).group())
    p = FakeProvider(call('get_forecast', metric='G', period='month', year=year, month=4), _forecast_answer(year))
    t = service.run_turn(reply, [previous], 'duckdb', p)
    assert t.status == 'ok', t.validation_errors
    (hint,) = _hint(p)
    assert 'Dự báo tháng 4 là bao nhiêu?' in hint and f'năm {year}' in hint and 'không hỏi xác nhận' in hint


@pytest.mark.parametrize('question,previous', [
    ('Năm 2024', {'question': 'R năm 2022 là bao nhiêu?', 'status': 'ok', 'tool_calls': []}),
    ('Năm 2024', {'question': 'Dự báo tháng 4 là bao nhiêu?', 'status': 'ok', 'tool_calls': []}),
    ('Năm 2025', {'question': 'Dự báo tháng 4 là bao nhiêu?', 'status': 'needs_clarification', 'tool_calls': []}),
    ('Dự báo tháng 5/2024?', {'question': 'Dự báo tháng 4 là bao nhiêu?', 'status': 'needs_clarification',
                              'tool_calls': []}),
])
def test_ny9_khong_phai_cau_dap_nam_thi_khong_goi_y(question, previous):
    p = FakeProvider(final('needs_clarification', 'Bạn muốn hỏi kỳ nào?'))
    service.run_turn(question, [previous], 'duckdb', p)
    assert _hint(p) == []


@pytest.mark.parametrize('previous_question,reply,args,asked', [
    ('Dự báo tháng 8 là bao nhiêu?', '2024', {'period': 'month', 'year': 2024, 'month': 8}, 'tháng 8/2024'),
    ('Dự báo G ngày 14/8 thế nào?', 'Năm 2024', {'period': 'day', 'year': 2024, 'month': 8, 'day': 14},
     'ngày 14/8/2024'),
    ('T12 dự báo G?', 'năm 2024', {'period': 'month', 'year': 2024, 'month': 12}, 'tháng 12/2024'),
])
def test_ny9_dap_nam_ghep_ky_sau_horizon_chi_bao_khong_co(monkeypatch, previous_question, reply, args, asked):
    # gợi ý khiến mô hình gọi tool ngay; kỳ ghép nằm sau 01/07/2024 thì chỉ báo không có (quyết định lượt 3)
    monkeypatch.setattr(tools, 'run', lambda *_a, **_k: pytest.fail('đã đọc kho cho kỳ ngoài horizon'))
    previous = {'question': previous_question, 'status': 'needs_clarification', 'tool_calls': []}
    path = 'T1.rows[0].g_forecast'
    t = _run(reply, call('get_forecast', metric='G', **args),
             final(answer=f'Dự báo G {asked} là {{c1}}.', claims=[{'id': 'c1', 'path': path}]), history=[previous])
    assert t.status == 'no_data' and not t.values
    assert f'({asked}) nằm ngoài kỳ dự báo' in t.message and 'không có dữ liệu thực tế hoặc dự báo' in t.message


def test_ny9_dap_nam_ghep_ky_trong_horizon_van_doc(versioned):
    previous = {'question': 'Dự báo tháng 8 là bao nhiêu?', 'status': 'needs_clarification', 'tool_calls': []}
    t = _run('2023', call('get_forecast', metric='G', period='month', year=2023, month=8),
             _forecast_answer(2023, 8), history=[previous])
    assert t.status == 'ok', t.validation_errors
    assert t.results['T1'].ok
