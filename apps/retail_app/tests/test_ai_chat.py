"""AI2: bộ điều phối + kiểm câu trả lời, chạy với MÔ HÌNH GIẢ (kịch bản cố định), không gọi API.

PASS ở đây chứng minh: luồng tool → kiểm claim → hiện/chặn đúng, giới hạn và ngữ cảnh. KHÔNG phải live-model eval
(model thật có hiểu câu hỏi không, chọn tool đúng không): phần đó ở scripts/ops/ai_live_eval.py, báo cáo riêng.
Đọc DuckDB `warehouse/dbt.duckdb` qua tools.run (cùng đường với test_ai_tools.py).
"""
import json

import pytest

from ai_explain import evidence, provider, service, tools
from ai_explain.contracts import ToolResult
from ai_explain.provider import ProviderError, Reply, ToolCallReq
from ui.fmt import num


class FakeProvider:
    """Trả lần lượt các Reply đã soạn; ghi lại messages nhận được để kiểm ngữ cảnh."""
    label = 'fake'

    def __init__(self, *steps):
        self.steps, self.seen = list(steps), []

    def complete(self, messages, tools_):
        self.seen.append([dict(m) for m in messages])
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def call(name, **args) -> Reply:
    c = ToolCallReq(f'id{name}{len(args)}', name, json.dumps(args))
    return Reply(None, [c], {'role': 'assistant', 'content': '', 'tool_calls': [
        {'id': c.id, 'type': 'function', 'function': {'name': name, 'arguments': c.arguments_json}}]}, 100, 10)


def final(status='ok', answer='', claims=(), fence=False) -> Reply:
    s = json.dumps({'status': status, 'answer': answer, 'claims': list(claims)}, ensure_ascii=False)
    if fence:
        s = f'```json\n{s}\n```'
    return Reply(s, [], {'role': 'assistant', 'content': s}, 200, 50)


def turn(fake, q='Vì sao R năm 2019 giảm?', history=(), **kw):
    return service.run_turn(q, list(history), 'duckdb', fake, **kw)


E04_OK = final(answer='R năm 2019 giảm {c1} so với 2018. Theo phân rã số học N → U → P, phần kéo xuống chủ yếu đến từ '
                      '{c2}, góp {c3}. Đây là phân rã số học, không phải nguyên nhân.',
               claims=[{'id': 'c1', 'path': 'T1.rows[0].delta_r', 'sign': 'am'},
                       {'id': 'c2', 'path': 'T1.rows[0].top_down_driver'},
                       {'id': 'c3', 'path': 'T1.rows[0].contrib_n', 'sign': 'am'}])


def test_e04_luong_day_du_so_lay_tu_kho():
    fake = FakeProvider(call('get_revenue_drivers', metric='R', year=2019), E04_OK)
    t = turn(fake)
    assert t.status == 'ok', t.validation_errors
    d = t.results['T1'].rows[0]
    assert num(abs(d['delta_r']), 0) in t.answer_md and 'số đơn (N)' in t.answer_md
    assert '554.945.327' in t.answer_md            # đối chứng CSV ở docs/ai_explain_ai0_ai1.md §3
    assert t.calls == [('T1', 'get_revenue_drivers', {'metric': 'R', 'year': 2019})]
    assert t.llm_calls == 2 and t.tokens == 360


def test_e21_noi_tang_khi_delta_am_thi_chan():
    lie = final(answer='R năm 2019 tăng {c1}.', claims=[{'id': 'c1', 'path': 'T1.rows[0].delta_r'}])
    t = turn(FakeProvider(call('get_revenue_drivers', metric='R', year=2019), lie, lie))
    assert t.status == 'answer_validation_failed' and t.answer_md is None
    assert any('tăng' in e for e in t.validation_errors)
    assert t.results['T1'].ok and t.results['T1'].rows   # bảng số của tool vẫn hiện được


def test_e21_sign_sai_thi_chan():
    lie = final(answer='R đổi {c1}.', claims=[{'id': 'c1', 'path': 'T1.rows[0].delta_r', 'sign': 'duong'}])
    t = turn(FakeProvider(call('get_revenue_drivers', metric='R', year=2019), lie, lie))
    assert t.status == 'answer_validation_failed'


def test_e21_so_tu_viet_thi_chan():
    bia = final(answer='R năm 2019 giảm khoảng 555 triệu.', claims=[])
    t = turn(FakeProvider(call('get_revenue_drivers', metric='R', year=2019), bia, bia))
    assert t.status == 'answer_validation_failed' and any('số tự viết' in e for e in t.validation_errors)


def test_sua_mot_lan_thi_dat():
    bia = final(answer='R giảm 555 triệu.', claims=[])
    fake = FakeProvider(call('get_revenue_drivers', metric='R', year=2019), bia, E04_OK)
    t = turn(fake)
    assert t.status == 'ok' and t.llm_calls == 3
    assert 'chưa qua bước kiểm' in fake.seen[-1][-1]['content']


def test_xep_hang_phai_tro_vao_tap_day_du():
    # "nhiều nhất" nhưng chỉ trỏ một dòng → chặn (một ô số đúng không chứng minh "lớn nhất")
    sai = final(answer='Ngành kéo giảm nhiều nhất là Streetwear với {c1}.',
                claims=[{'id': 'c1', 'path': 'T1.rows[Streetwear].delta_r', 'sign': 'am'}])
    q = 'Ngành hàng nào kéo giảm R mạnh nhất năm 2019?'
    t = service.run_turn(q, [], 'duckdb', FakeProvider(
        call('get_segment_contribution', metric='R', dimension='category', year=2019), sai, sai))
    assert t.status == 'answer_validation_failed'
    dung = final(answer='Ngành kéo giảm nhiều nhất năm 2019 là {c1}, giảm {c2}, bằng {c3} mức giảm toàn công ty.',
                 claims=[{'id': 'c1', 'path': 'T1.derived.largest_decrease.groups'},
                         {'id': 'c2', 'path': 'T1.derived.largest_decrease.delta_r', 'sign': 'am'},
                         {'id': 'c3', 'path': 'T1.rows[Streetwear].contribution_to_delta', 'sign': 'duong'}])
    t = service.run_turn(q, [], 'duckdb', FakeProvider(
        call('get_segment_contribution', metric='R', dimension='category', year=2019), dung))
    assert t.status == 'ok', t.validation_errors
    assert '**Streetwear**' in t.answer_md and '463.947.221' in t.answer_md


def test_e06_follow_up_dung_ngu_canh_co_cau_truc():
    q1 = 'Ngành hàng nào kéo giảm R mạnh nhất năm 2019?'
    t1 = service.run_turn(q1, [], 'duckdb', FakeProvider(
        call('get_segment_contribution', metric='R', dimension='category', year=2019),
        final(answer='Ngành giảm mạnh nhất: {c1}.', claims=[{'id': 'c1', 'path': 'T1.derived.largest_decrease.groups'}])))
    assert t1.status == 'ok'
    fake = FakeProvider(call('get_segment_contribution', metric='R', dimension='region', year=2019),
                        final(answer='Theo khu vực, giảm mạnh nhất là {c1}.',
                              claims=[{'id': 'c1', 'path': 'T1.derived.largest_decrease.groups'}]))
    t2 = service.run_turn('Còn theo khu vực?', [t1.context()], 'duckdb', fake)
    assert t2.status == 'ok'
    ctx = fake.seen[0][1]['content']
    assert '"dimension": "category"' in ctx and '"year": 2019' in ctx
    assert 'Streetwear' not in ctx and 'giảm mạnh nhất' not in ctx     # không gửi lại văn xuôi/số của lượt trước
    e1, e2 = t1.results['T1'].evidence, t2.results['T1'].evidence
    assert e1.request_id != e2.request_id and e2.filters_applied['dimension_name'] == 'region'


def test_e07_g_sau_phan_ra_r_thi_tu_choi():
    fake = FakeProvider(call('get_revenue_drivers', metric='G', year=2019),
                        final('unsupported', 'Phân rã N → U → P chỉ có cho R, chưa có cho G.'))
    t = turn(fake, 'Còn G?')
    assert t.status == 'unsupported' and t.results['T1'].status == 'unsupported' and not t.values


def test_e15_nam_ngoai_du_lieu_nhac_lai_nam_trong_cau_hoi():
    fake = FakeProvider(call('get_revenue_summary', metric='R_and_G', year=2023),
                        final('no_data', 'Không có dữ liệu thực tế năm 2023; dữ liệu dừng ở cuối 2022.'))
    t = turn(fake, 'Doanh thu năm 2023?')
    # 2023 có trong câu hỏi, 2022 có trong thông báo phạm vi dữ liệu của tool
    assert t.status == 'no_data' and '2023' in t.answer_md and not t.values, t.validation_errors
    bia = final('no_data', 'Không có dữ liệu năm 2023; năm 2021 là 1,2 tỷ.')
    t = turn(FakeProvider(call('get_revenue_summary', metric='R_and_G', year=2023), bia, bia), 'Doanh thu năm 2023?')
    assert t.status == 'answer_validation_failed'


def test_e02_hoi_lai_khong_goi_tool():
    fake = FakeProvider(final('needs_clarification', 'Bạn muốn xem R (đơn đã giao, sau chiết khấu) hay G (mọi đơn)?'))
    t = turn(fake, 'Doanh thu năm 2019?')
    assert t.status == 'needs_clarification' and 'R' in t.answer_md and not t.calls


def test_json_trong_khoi_code_van_doc_duoc():
    fake = FakeProvider(call('get_revenue_drivers', metric='R', year=2019),
                        final(answer=json.loads(E04_OK.content)['answer'], claims=json.loads(E04_OK.content)['claims'],
                              fence=True))
    assert turn(fake).status == 'ok'


def test_het_han_muc_token_thi_khong_goi_model():
    fake = FakeProvider()
    t = turn(fake, session_tokens_used=service.SESSION_TOKEN_LIMIT)
    assert t.status == 'budget_exceeded' and not fake.seen


def test_loi_provider_khong_tra_so():
    t = turn(FakeProvider(ProviderError('AuthenticationError: sai khóa')))
    assert t.status == 'provider_error' and t.answer_md is None and 'sai khóa' in t.message


def test_toi_da_4_lan_goi_tool():
    steps = [call('get_revenue_summary', metric='R', year=y) for y in range(2014, 2020)]
    t = turn(FakeProvider(*steps))
    assert len(t.calls) == service.MAX_TOOL_CALLS
    assert t.status == 'answer_validation_failed' and t.llm_calls == service.MAX_LLM_CALLS


def test_databricks_chua_ho_tro_khong_goi_model():
    fake = FakeProvider()
    t = service.run_turn('R 2019?', [], 'databricks', fake)
    assert t.status == 'unsupported' and not fake.seen


def test_loi_kho_duoc_uu_tien_hon_nhan_cua_model(monkeypatch):
    monkeypatch.setattr(tools, 'run', lambda c, b: ToolResult('quality_blocked', 'Kho chưa qua cổng chất lượng.'))
    t = turn(FakeProvider(call('get_revenue_drivers', metric='R', year=2019),
                          final('unsupported', 'Chưa trả lời được vì kho chưa qua kiểm.')))
    assert t.status == 'quality_blocked'


def test_status_ok_ma_khong_co_ket_qua_tool_thi_chan():
    t = turn(FakeProvider(final(answer='R năm 2019 giảm mạnh.'), final(answer='R năm 2019 giảm mạnh.')))
    assert t.status == 'answer_validation_failed'


def test_payload_cho_model_khong_co_sql_hay_thong_tin_ket_noi():
    res = tools.run({'tool': 'get_revenue_drivers', 'arguments': {'metric': 'R', 'year': 2019}}, 'duckdb')
    p = service.tool_payload('T1', res)
    assert 'select' not in p.lower() and 'dbt.duckdb' not in p and 'request_id' not in p
    assert json.loads(p)['rows'][0]['delta_r'].startswith('-554945327.33')    # Decimal → chuỗi đủ chữ số


def test_ngu_canh_khong_co_van_xuoi():
    fake = FakeProvider(call('get_revenue_drivers', metric='R', year=2019), E04_OK)
    ctx = turn(fake).context()
    assert set(ctx) == {'question', 'status', 'tool_calls'}
    assert ctx['tool_calls'] == [{'tool': 'get_revenue_drivers', 'arguments': {'metric': 'R', 'year': 2019},
                                  'status': 'ok'}]


def test_cong_cu_dinh_dang_openai():
    t = provider.openai_tools(tools.tool_schemas())
    assert {x['function']['name'] for x in t} == set(tools.TOOLS)
    assert all(x['type'] == 'function' and x['function']['parameters']['additionalProperties'] is False for x in t)


def test_chua_co_khoa_thi_khong_tao_provider(monkeypatch, tmp_path):
    monkeypatch.setattr(provider, 'AI_CONFIG', tmp_path / 'khong_co.env')
    monkeypatch.delenv('RETAIL_AI_API_KEY', raising=False)
    assert provider.from_config() is None
    monkeypatch.setenv('RETAIL_AI_API_KEY', 'gia')
    p = provider.from_config()
    assert p.model == 'deepseek-flash' and p.base_url == 'https://api.deepseek.com'


def test_tang_truong_am_va_ty_le_dong_gop_khong_bi_chan_nham():
    # cách nói thật của E03/E05: "tăng trưởng âm"; % đóng góp DƯƠNG vào mức GIẢM (cùng chiều ΔR toàn công ty)
    rows = [{'dimension_value': 'Streetwear', 'year': 2019, 'yoy_rate': -0.391, 'contribution_to_delta': 0.836}]
    chk = evidence.validate('R năm 2019 tăng trưởng {c1}. Streetwear kéo giảm {c2} mức giảm toàn công ty.', [
        {'id': 'c1', 'path': 'T1.rows[0].yoy_rate', 'sign': 'am'},
        {'id': 'c2', 'path': 'T1.rows[Streetwear].contribution_to_delta'}], _res(rows))
    assert chk.ok, chk.errors
    assert '−39,1%' in chk.answer_md and '83,6%' in chk.answer_md


def test_khong_nhac_lai_so_gai_trong_cau_hoi():
    assert evidence.question_numbers('R 2019 là 999 tỷ phải không? từ 15/3 đến 10/6/2019') == {
        '2019', '15', '3', '10', '6'}
    gai = final('ok', 'Đúng, R năm 2019 là 999 tỷ.')
    t = turn(FakeProvider(call('get_revenue_summary', metric='R', year=2019), gai, gai), 'R 2019 là 999 tỷ phải không?')
    assert t.status == 'answer_validation_failed' and any('999' in e for e in t.validation_errors)


# --- evidence.validate trên kết quả dựng tay ---

def _res(rows, derived=None):
    return {'T1': ToolResult('ok', 'x', rows=rows, derived=derived or {})}


@pytest.mark.parametrize('path,why', [
    ('T2.rows[0].r', 'không phải kết quả'), ('T1.rows[3].r', 'không có dòng'), ('T1.rows[0].khong', 'không có trường'),
    ('T1.derived.x', 'không có x'), ('rows[0].r', 'sai dạng'), ('T1.rows[0].r_prior_year', 'NULL'),
])
def test_claim_sai_tham_chieu(path, why):
    chk = evidence.validate('Số {c1}.', [{'id': 'c1', 'path': path}], _res([{'r': 1, 'r_prior_year': None}]))
    assert not chk.ok and any(why in e for e in chk.errors), chk.errors


def test_cho_dat_khong_co_claim():
    chk = evidence.validate('Số {c1} và {c2}.', [{'id': 'c1', 'path': 'T1.rows[0].r'}], _res([{'r': 1}]))
    assert not chk.ok and any('{c2}' in e for e in chk.errors)


def test_ket_qua_loi_khong_duoc_dan_so():
    chk = evidence.validate('Số {c1}.', [{'id': 'c1', 'path': 'T1.rows[0].r'}],
                            {'T1': ToolResult('no_data', 'không có')})
    assert not chk.ok and any('no_data' in e for e in chk.errors)


def test_dinh_dang_theo_loai_cot():
    rows = [{'yoy_rate': -0.391, 'share_shift_pp': 2.5, 'n_end': 33259, 'u_end': 4.866}]
    chk = evidence.validate('% đổi {c1}; tỷ trọng tăng {c2}; số đơn {c3}; món mỗi đơn {c4}.', [
        {'id': 'c1', 'path': 'T1.rows[0].yoy_rate', 'sign': 'am'},
        {'id': 'c2', 'path': 'T1.rows[0].share_shift_pp', 'sign': 'duong'},
        {'id': 'c3', 'path': 'T1.rows[0].n_end'}, {'id': 'c4', 'path': 'T1.rows[0].u_end'}], _res(rows))
    assert chk.ok, chk.errors
    assert '−39,1%' in chk.answer_md and '2,5 điểm %' in chk.answer_md      # share_shift_pp KHÔNG nhân 100 lần nữa
    assert '33.259' in chk.answer_md and '4,87' in chk.answer_md


# --- trang chat (AppTest), vẫn mô hình giả ---

def _app(monkeypatch, fake, backend='duckdb'):
    from streamlit.testing.v1 import AppTest
    import streamlit as st
    from tests.test_smoke import APP
    monkeypatch.setenv('RETAIL_BACKEND', backend)
    monkeypatch.setattr(provider, 'from_config', lambda: fake)
    st.cache_data.clear()
    return AppTest.from_file(str(APP), default_timeout=60).run().switch_page('views/ai_explain.py').run()


def test_trang_chat_hoi_dap_va_rerun_khong_goi_lai_model(monkeypatch):
    fake = FakeProvider(call('get_revenue_drivers', metric='R', year=2019), E04_OK)
    at = _app(monkeypatch, fake)
    assert not at.exception and not at.error
    at.chat_input[0].set_value('Vì sao R năm 2019 giảm?').run()
    assert not at.exception, at.exception
    assert len(fake.seen) == 2
    assert any('554.945.327' in m.value for m in at.markdown)
    assert any('phân rã số học' in c.value for c in at.caption)
    labels = [e.label for e in at.expander]
    assert any(l.startswith('Bằng chứng T1') for l in labels)
    at.run()                                    # rerun: vẽ lại lịch sử, không gọi API
    assert len(fake.seen) == 2 and any('554.945.327' in m.value for m in at.markdown)


def test_trang_chat_cau_bi_chan_chi_hien_bang_so(monkeypatch):
    lie = final(answer='R năm 2019 tăng {c1}.', claims=[{'id': 'c1', 'path': 'T1.rows[0].delta_r'}])
    at = _app(monkeypatch, FakeProvider(call('get_revenue_drivers', metric='R', year=2019), lie, lie))
    at.chat_input[0].set_value('Vì sao R năm 2019 giảm?').run()
    assert not at.exception and not at.error
    assert any('Chưa tạo được diễn giải' in w.value for w in at.warning)
    assert not any('R năm 2019 tăng' in m.value for m in at.markdown)       # câu sai không được hiện
    assert any('nói "tăng"' in m.value for m in at.markdown)                # lý do chặn thì có


def test_trang_chat_doi_backend_xoa_hoi_thoai(monkeypatch):
    fake = FakeProvider(call('get_revenue_drivers', metric='R', year=2019), E04_OK)
    at = _app(monkeypatch, fake)
    at.chat_input[0].set_value('Vì sao R năm 2019 giảm?').run()
    assert len(at.session_state.ai_turns) == 1
    at.sidebar.radio[0].set_value('postgres').run()
    assert at.session_state.ai_turns == [] and len(fake.seen) == 2


def test_trang_chat_chua_co_khoa_chi_bao_info(monkeypatch):
    at = _app(monkeypatch, None)
    assert not at.exception and not at.error
    assert any('.env.ai.local' in i.value for i in at.info)
    assert not at.chat_input
