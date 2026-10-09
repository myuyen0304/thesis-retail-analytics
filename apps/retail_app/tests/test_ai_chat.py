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
        self.steps, self.seen, self.max_tokens = list(steps), [], []

    def complete(self, messages, tools_, max_tokens=None):
        self.seen.append([dict(m) for m in messages])
        self.max_tokens.append(max_tokens)
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


class WorstCaseProvider:
    """Model giả xấu nhất cho hạn mức: prompt_tokens = ĐÚNG cận trên app tính, completion = ĐÚNG max_tokens.
    Trả lời lần lượt: gọi tool rồi trả câu đúng (E04), lặp vô hạn."""
    label = 'worst'

    def __init__(self):
        self.n, self.max_tokens = 0, []

    def complete(self, messages, tools_, max_tokens=None):
        self.max_tokens.append(max_tokens)
        step = (call('get_revenue_drivers', metric='R', year=2019), E04_OK)[self.n % 2]
        self.n += 1
        return Reply(step.content, step.tool_calls, step.message, service.prompt_bound(messages, tools_), max_tokens)


def test_tran_token_cung_ca_phien_khong_vuot_200k():
    """Hạn mức 200k là trần cứng: kể cả khi mỗi lần gọi tốn đúng cận trên prompt và đủ max_tokens output,
    tổng token cả phiên không vượt SESSION_TOKEN_LIMIT; app dừng TRƯỚC khi gọi chứ không sau khi đã vượt."""
    p, used, statuses = WorstCaseProvider(), 0, []
    for _ in range(100):
        t = service.run_turn('Vì sao R năm 2019 giảm?', [], 'duckdb', p, session_tokens_used=used)
        used += t.tokens
        statuses.append(t.status)
        assert used <= service.SESSION_TOKEN_LIMIT, (used, statuses)
        if t.status == 'budget_exceeded':
            break
    assert statuses[-1] == 'budget_exceeded' and statuses.count('ok') >= 3, statuses
    assert set(p.max_tokens) == {service.MAX_OUTPUT_TOKENS}            # mọi request đều mang trần output


def test_cau_tra_loi_bi_cat_o_max_tokens_thi_khong_hien():
    cut = Reply('{"status": "ok", "answer": "R năm 2019 giảm {c1', [], {'role': 'assistant', 'content': '...'}, 200,
                service.MAX_OUTPUT_TOKENS, finish_reason='length')
    t = turn(FakeProvider(call('get_revenue_drivers', metric='R', year=2019), cut))
    assert t.status == 'answer_validation_failed' and t.answer_md is None and 'bị cắt' in t.message


def test_cau_tra_loi_bi_cat_khi_goi_tool_thi_khong_chay_tool():
    c = ToolCallReq('x', 'get_revenue_drivers', '{"metric": "R", "ye')
    cut = Reply(None, [c], {'role': 'assistant', 'content': ''}, 100, service.MAX_OUTPUT_TOKENS, finish_reason='length')
    t = turn(FakeProvider(cut))
    assert t.status == 'answer_validation_failed' and not t.calls


def test_can_tren_prompt_ghi_lai_moi_lan_goi():
    fake = FakeProvider(call('get_revenue_drivers', metric='R', year=2019), E04_OK)
    t = turn(fake)
    assert [b for b, _ in t.prompt_bounds] == [service.prompt_bound(m, provider.openai_tools(tools.tool_schemas()))
                                               for m in fake.seen]
    assert [a for _, a in t.prompt_bounds] == [100, 200]


def test_loi_provider_khong_tra_so():
    t = turn(FakeProvider(ProviderError('AuthenticationError: sai khóa')))
    assert t.status == 'provider_error' and t.answer_md is None and 'sai khóa' in t.message


def test_toi_da_4_lan_goi_tool():
    steps = [call('get_revenue_summary', metric='R', year=y) for y in range(2014, 2020)]
    t = turn(FakeProvider(*steps))
    assert len(t.calls) == service.MAX_TOOL_CALLS
    assert t.status == 'answer_validation_failed' and t.llm_calls == service.MAX_LLM_CALLS


def test_backend_chua_ho_tro_khong_goi_model():
    # Databricks có đường đọc chỉ-đọc từ 2026-10-06 (tests/test_ai_databricks.py); Snowflake thì chưa
    assert 'databricks' in service.CHAT_BACKENDS
    fake = FakeProvider()
    t = service.run_turn('R 2019?', [], 'snowflake', fake)
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
    assert evidence.question_numbers('R 2019 là 999 tỷ phải không? từ 15/3 đến 10/6/2019, tháng 8') == {
        '2019', '15/3', '10/6/2019', 'tháng 8'}
    gai = final('ok', 'Đúng, R năm 2019 là 999 tỷ.')
    t = turn(FakeProvider(call('get_revenue_summary', metric='R', year=2019), gai, gai), 'R 2019 là 999 tỷ phải không?')
    assert t.status == 'answer_validation_failed' and any('999' in e for e in t.validation_errors)


# --- hồi quy 4 probe của docs/ai_explain_review_20261005.md: câu sai phải bị chặn ---

SEG_2019 = dict(metric='R', dimension='category', year=2019)


def test_probe_so_g_gan_nhan_r_thi_chan():
    bad = final(answer='R năm 2019 là {c1}.', claims=[{'id': 'c1', 'path': 'T1.rows[0].g'}])
    t = service.run_turn('R năm 2019 là bao nhiêu?', [], 'duckdb', FakeProvider(
        call('get_revenue_summary', metric='R_and_G', year=2019), bad, bad))
    assert t.status == 'answer_validation_failed' and t.answer_md is None
    assert any('vế câu gọi tên R' in e for e in t.validation_errors), t.validation_errors


def test_r_va_g_lan_luot_co_nhan_cua_app():
    ok = final(answer='R và G năm 2019 lần lượt là {c1} và {c2}.',
               claims=[{'id': 'c1', 'path': 'T1.rows[0].r'}, {'id': 'c2', 'path': 'T1.rows[0].g'}])
    t = service.run_turn('R và G năm 2019?', [], 'duckdb', FakeProvider(
        call('get_revenue_summary', metric='R_and_G', year=2019), ok))
    assert t.status == 'ok', t.validation_errors
    assert '**864.329.802 VND** (R, 2019)' in t.answer_md and '**1.136.801.442 VND** (G, 2019)' in t.answer_md


def test_probe_so_trong_cau_hoi_khong_duoc_nhac_lai():
    q = 'R 2019 là 10 tỷ phải không?'
    gai = final(answer='Đúng, R năm 2019 là 10 tỷ.')
    t = turn(FakeProvider(call('get_revenue_summary', metric='R', year=2019), gai, gai), q)
    assert t.status == 'answer_validation_failed' and any('10' in e for e in t.validation_errors)
    # số trùng một năm nhưng đứng trước đơn vị cũng bị chặn
    assert evidence.check_digits('R năm 2019 là 2019 tỷ.', {'2019'})
    # mốc ngày người dùng gõ vẫn được nhắc lại nguyên cụm
    assert not evidence.check_digits('Chưa hỗ trợ kỳ 15/3 đến 10/6/2019.', evidence.question_numbers(
        'R ngành Streetwear ở vùng East từ 15/3 đến 10/6/2019?'))
    assert evidence.check_digits('Có 15 nhóm.', evidence.question_numbers('từ 15/3 đến 10/6/2019?'))


def test_probe_xep_hang_claim_khong_dung_va_ten_nhom_viet_tay_thi_chan():
    bad = final(answer='Ngành kéo giảm nhiều nhất là Luxury.',
                claims=[{'id': 'c1', 'path': 'T1.derived.largest_decrease.groups'}])
    t = service.run_turn('Ngành nào kéo giảm R nhiều nhất năm 2019?', [], 'duckdb', FakeProvider(
        call('get_segment_contribution', **SEG_2019), bad, bad))
    assert t.status == 'answer_validation_failed'
    # tên nhóm thật nhưng viết tay, claim xếp hạng không nằm trong câu đó
    sai = final(answer='Kết quả: {c1}. Ngành Casual giảm nhiều nhất.',
                claims=[{'id': 'c1', 'path': 'T1.derived.largest_decrease.groups'}])
    t = service.run_turn('Ngành nào kéo giảm R nhiều nhất năm 2019?', [], 'duckdb', FakeProvider(
        call('get_segment_contribution', **SEG_2019), sai, sai))
    errs = ' | '.join(t.validation_errors)
    assert t.status == 'answer_validation_failed' and 'Casual' in errs and 'xếp hạng' in errs, errs


def test_xep_hang_nguoc_chieu_thi_chan():
    sai = final(answer='Ngành tăng nhiều nhất là {c1}.', claims=[{'id': 'c1', 'path': 'T1.derived.largest_decrease.groups'}])
    t = service.run_turn('Ngành nào tăng nhiều nhất năm 2019?', [], 'duckdb', FakeProvider(
        call('get_segment_contribution', **SEG_2019), sai, sai))
    assert t.status == 'answer_validation_failed' and any('chiều' in e for e in t.validation_errors)


def test_ten_nhom_gan_voi_claim_cua_nhom_do_thi_dat():
    ok = final(answer='Streetwear giảm {c1} năm 2019.',
               claims=[{'id': 'c1', 'path': 'T1.rows[Streetwear].delta_r', 'sign': 'am'}])
    t = service.run_turn('Streetwear năm 2019 giảm bao nhiêu?', [], 'duckdb', FakeProvider(
        call('get_segment_contribution', **SEG_2019), ok))
    assert t.status == 'ok', t.validation_errors
    assert '463.947.221 VND' in t.answer_md


def test_probe_claim_tro_vao_ca_khoi_khong_lam_crash():
    bad = final(answer='Quy tắc {c1}.', claims=[{'id': 'c1', 'path': 'T1.derived.small_delta_rule'}])
    t = turn(FakeProvider(call('get_revenue_drivers', metric='R', year=2019), bad, bad))
    assert t.status == 'answer_validation_failed' and any('một khối' in e for e in t.validation_errors)


def test_loi_bat_ngo_khi_kiem_khong_lam_crash(monkeypatch):
    def boom(*a, **k):
        raise TypeError('x')
    monkeypatch.setattr(service, 'validate', boom)
    t = turn(FakeProvider(call('get_revenue_drivers', metric='R', year=2019), E04_OK, E04_OK))
    assert t.status == 'answer_validation_failed' and t.answer_md is None


# --- lỗi gặp ở live eval 2026-10-05 (model thật), dựng lại bằng mô hình giả ---

def test_live_ma_ai1_va_nam_trong_pham_vi_du_lieu_khong_bi_chan_nham():
    # E10/E12: "lát cắt AI1" bị đọc thành số 1; E15b: "dữ liệu chỉ đến hết năm 2022" khi chưa gọi tool
    assert not evidence.check_digits('Chưa hỗ trợ ở lát cắt AI1, PS3.', set())
    t = turn(FakeProvider(final('unsupported', 'Không có số thực năm 2023: dữ liệu chỉ có đến hết năm 2022.')),
             'Dự báo R năm 2023?')
    assert t.status == 'unsupported', t.validation_errors
    assert evidence.check_digits('Năm 2022 R là 2022 VND.', set())          # năm đứng trước đơn vị vẫn bị chặn
    assert not evidence.check_digits('Năm 2019, ngành hàng giảm nhiều nhất là {c1}.', set())   # 'ngàn' ≠ 'ngành'
    assert evidence.check_digits('R là 864 ngàn, giảm 39%.', set())


def test_live_don_vi_lap_sau_cho_dat_bi_bo():
    ok = final(answer='R năm 2019 là {c1} VND, giảm {c2} %.',
               claims=[{'id': 'c1', 'path': 'T1.rows[0].r'}, {'id': 'c2', 'path': 'T1.rows[0].yoy_rate', 'sign': 'am'}])
    t = service.run_turn('R năm 2019?', [], 'duckdb', FakeProvider(
        call('get_revenue_summary', metric='R', year=2019, compare_prior_year=True), ok))
    assert t.status == 'ok', t.validation_errors
    assert 'VND VND' not in t.answer_md and 'VND** VND' not in t.answer_md and '% %' not in t.answer_md
    assert '**864.329.802 VND**' in t.answer_md


def test_live_so_cua_u_gan_cho_p_thi_chan():
    # E04 live: "{top_up_driver = P} góp {contrib_u}" — số góp của U được nói là của P
    sai = final(answer='R giảm {c1}; phần kéo xuống chủ yếu là {c2}. Ngược lại {c3} góp {c4}.',
                claims=[{'id': 'c1', 'path': 'T1.rows[0].delta_r', 'sign': 'am'},
                        {'id': 'c2', 'path': 'T1.rows[0].top_down_driver'},
                        {'id': 'c3', 'path': 'T1.rows[0].top_up_driver'},
                        {'id': 'c4', 'path': 'T1.rows[0].contrib_u', 'sign': 'duong'}])
    t = turn(FakeProvider(call('get_revenue_drivers', metric='R', year=2019), sai, sai))
    assert t.status == 'answer_validation_failed' and any('là số của U' in e for e in t.validation_errors), \
        t.validation_errors
    assert t.results['T1'].rows[0]['top_up_driver'] == 'p'
    dung = final(answer='R giảm {c1}; phần kéo xuống chủ yếu là {c2}, góp {c3}. Giá mỗi món góp {c4}.',
                 claims=[{'id': 'c1', 'path': 'T1.rows[0].delta_r', 'sign': 'am'},
                         {'id': 'c2', 'path': 'T1.rows[0].top_down_driver'},
                         {'id': 'c3', 'path': 'T1.rows[0].contrib_n', 'sign': 'am'},
                         {'id': 'c4', 'path': 'T1.rows[0].contrib_p', 'sign': 'duong'}])
    t = turn(FakeProvider(call('get_revenue_drivers', metric='R', year=2019), dung))
    assert t.status == 'ok', t.validation_errors


def test_live_xep_hang_goi_ten_n_u_p_duoc_app_doi_chieu():
    # E04b live: "R giảm chủ yếu ở số đơn (N)" viết thẳng; app tự đối chiếu top_down_driver = n
    dung = final(answer='R năm 2019 giảm chủ yếu ở số đơn (N), phần góp {c1}.',
                 claims=[{'id': 'c1', 'path': 'T1.rows[0].contrib_n', 'sign': 'am'}])
    assert turn(FakeProvider(call('get_revenue_drivers', metric='R', year=2019), dung)).status == 'ok'
    sai = final(answer='R năm 2019 giảm chủ yếu ở giá mỗi món (P), phần góp {c1}.',
                claims=[{'id': 'c1', 'path': 'T1.rows[0].contrib_p', 'sign': 'duong'}])
    t = turn(FakeProvider(call('get_revenue_drivers', metric='R', year=2019), sai, sai))
    assert t.status == 'answer_validation_failed'
    vo = final(answer='Trong đó, số đơn (N) góp {c1} và là thành phần kéo giảm nhiều nhất.',
               claims=[{'id': 'c1', 'path': 'T1.rows[0].contrib_n', 'sign': 'am'}])
    assert turn(FakeProvider(call('get_revenue_drivers', metric='R', year=2019), vo)).status == 'ok'
    assert not evidence.check_digits('Dữ liệu từ 2012-07-04 đến 2022-12-31.', set())


PHASES = ('get_revenue_trend', {'view': 'phases'})
TURNS = ('get_revenue_trend', {'view': 'turning_points'})


def _one(tool, answer, claims, q='Giai đoạn sập thì CAGR bao nhiêu?'):
    """Một lượt, model trả cùng một câu ở cả lần đầu và lần sửa: trạng thái cho biết bộ kiểm có cho qua không."""
    f = final(answer=answer, claims=claims)
    return service.run_turn(q, [], 'duckdb', FakeProvider(call(tool[0], **tool[1]), f, f))


def test_live_cau_noi_day_la_manh_nhat_duoc_app_doi_chieu():
    # §3 mục 10 nhật ký (live A03, A03d, C02): câu nối "Đây (cũng) là… mạnh nhất" không có chỗ đặt xếp hạng, đại từ trỏ
    # về giai đoạn câu trước đã dẫn số. App đối chiếu với derived.largest_* trên đủ 4 giai đoạn.
    c = [{'id': 'c1', 'path': 'T1.rows[C].delta_r', 'sign': 'am'}, {'id': 'c2', 'path': 'T1.rows[C].cagr', 'sign': 'am'},
         {'id': 'c3', 'path': 'T1.derived.n_phases'}]
    # không nêu tiêu chí → C phải đứng đầu theo CẢ tiền lẫn CAGR (đúng trong kho)
    t = _one(PHASES, 'Giai đoạn sập (C), R giảm {c1}, CAGR {c2}. Đây cũng là giai đoạn giảm mạnh nhất trong {c3} giai đoạn.', c)
    assert t.status == 'ok', t.validation_errors
    t = _one(PHASES, 'Giai đoạn sập, R giảm {c1}; đây cũng là mức giảm mạnh nhất theo cả mức đổi R bằng tiền lẫn CAGR '
                     'trong {c3} giai đoạn.', c)
    assert t.status == 'ok', t.validation_errors
    # A03d: CAGR dẫn ở câu trước bằng claim xếp hạng, tiền dẫn ngay trong câu
    t = _one(PHASES, 'Giai đoạn sập là {c1}, CAGR {c2}. Đây là giai đoạn giảm mạnh nhất theo CAGR, và cũng đứng đầu về mức '
                     'đổi R bằng tiền tại {c4}.',
             [{'id': 'c1', 'path': 'T1.derived.largest_decrease_cagr.phases'}, c[1],
              {'id': 'c4', 'path': 'T1.derived.largest_decrease.phases'}])
    assert t.status == 'ok', t.validation_errors
    # A03 (tăng, "dẫn đầu")
    t = _one(PHASES, 'Giai đoạn tăng trưởng (A) có mức tăng R {c1}. Đây là giai đoạn tăng mạnh nhất theo mức đổi R bằng '
                     'tiền, và cũng dẫn đầu theo CAGR.', [{'id': 'c1', 'path': 'T1.rows[A].delta_r', 'sign': 'duong'}])
    assert t.status == 'ok', t.validation_errors
    # điểm đổi hướng và nhóm
    t = _one(TURNS, 'Cú đổi hướng cuối 2018 có độ lớn {c1}. Đây là cú đổi hướng giảm mạnh nhất.',
             [{'id': 'c1', 'path': 'T1.rows[2018].magnitude', 'sign': 'am'}])
    assert t.status == 'ok', t.validation_errors
    t = _one(('get_segment_contribution', SEG_2019), 'Streetwear giảm {c1} năm 2019. Đây là mức giảm lớn nhất trong các '
             'ngành hàng.', [{'id': 'c1', 'path': 'T1.rows[Streetwear].delta_r', 'sign': 'am'}],
             q='Ngành nào kéo giảm R mạnh nhất năm 2019?')
    assert t.status == 'ok', t.validation_errors


def test_cau_noi_xep_hang_sai_hoac_khong_doi_chieu_duoc_thi_van_chan():
    def blocked(tool, answer, claims, why=''):
        t = _one(tool, answer, claims)
        assert t.status == 'answer_validation_failed', (answer, t.answer_md)
        assert why in ' | '.join(t.validation_errors), t.validation_errors
    b = [{'id': 'c1', 'path': 'T1.rows[B].cagr', 'sign': 'am'}]
    # B không phải giai đoạn giảm mạnh nhất
    blocked(PHASES, 'Giai đoạn B có CAGR {c1}. Đây là giai đoạn giảm mạnh nhất.', b, 'xếp hạng')
    # A đứng đầu chiều TĂNG, câu nói giảm
    blocked(PHASES, 'Giai đoạn A có CAGR {c1}. Đây là giai đoạn giảm mạnh nhất.',
            [{'id': 'c1', 'path': 'T1.rows[A].cagr', 'sign': 'duong'}], 'xếp hạng')
    # câu trước nói hai giai đoạn: đại từ không rõ trỏ vào đâu
    blocked(PHASES, 'CAGR của A là {c1}, của C là {c2}. Đây là giai đoạn giảm mạnh nhất.',
            [{'id': 'c1', 'path': 'T1.rows[A].cagr', 'sign': 'duong'},
             {'id': 'c2', 'path': 'T1.rows[C].cagr', 'sign': 'am'}], 'xếp hạng')
    # không mở bằng đại từ (live A10: chú thích trong ngoặc)
    blocked(PHASES, 'Ví dụ giai đoạn C (giai đoạn giảm mạnh nhất) có CAGR {c1}.',
            [{'id': 'c1', 'path': 'T1.rows[C].cagr', 'sign': 'am'}], 'xếp hạng')
    # nêu tiêu chí CAGR nhưng chỉ dẫn xếp hạng theo tiền
    blocked(PHASES, 'Giai đoạn giảm mạnh nhất theo CAGR là {c1}.',
            [{'id': 'c1', 'path': 'T1.derived.largest_decrease.phases'}], 'largest_*_cagr')
    # "nhỏ nhất" dẫn largest_* (phía ngược); câu nối "nhỏ nhất" (live A03c) cũng không đối chiếu được
    blocked(TURNS, 'Cú đổi hướng nhỏ nhất là {c1}.', [{'id': 'c1', 'path': 'T1.derived.largest_decrease.turns'}],
            'nhỏ nhất')
    blocked(TURNS, 'Cú đổi hướng cuối 2016 có độ lớn {c1}. Đây là mức đổi hướng nhỏ nhất.',
            [{'id': 'c1', 'path': 'T1.rows[2016].magnitude', 'sign': 'am'}], 'xếp hạng')
    # câu nối nói về TỶ TRỌNG (chỉ tiêu mức), không có chữ tăng/giảm: West 2021 kéo giảm nhiều nhất nhưng không chiếm
    # tỷ trọng lớn nhất → không được lấy xếp hạng ΔR để cho qua
    t = _one(('get_segment_contribution', dict(metric='R', dimension='region', year=2021)),
             'West giảm {c1} năm 2021. Vùng này chiếm tỷ trọng lớn nhất.',
             [{'id': 'c1', 'path': 'T1.rows[West].delta_r', 'sign': 'am'}], q='Năm 2021 vùng nào kéo R xuống nhiều nhất?')
    assert t.status == 'answer_validation_failed', t.answer_md
    t = _one(('get_segment_contribution', dict(metric='R', dimension='region', year=2021)),
             'West giảm {c1} năm 2021. Vùng này là vùng mạnh nhất.',
             [{'id': 'c1', 'path': 'T1.rows[West].delta_r', 'sign': 'am'}], q='Năm 2021 vùng nào kéo R xuống nhiều nhất?')
    assert t.status == 'answer_validation_failed', t.answer_md
    # A04: số giai đoạn n_phases không chứng minh "cùng tháng thấp nhất"
    t = _one(('get_calendar_pattern', {'pattern': 'mua_vu'}), 'Tháng thấp nhất là tháng {c1}. Tháng thấp nhất cũng lặp '
             'lại ở cả {c2} giai đoạn.', [{'id': 'c1', 'path': 'T1.derived.trough_months'},
                                         {'id': 'c2', 'path': 'T1.derived.n_phases'}], q='Tháng nào bán ít nhất?')
    assert t.status == 'answer_validation_failed'


def test_live_d11_hoi_it_nhat_loi_nhac_khong_day_sang_nhieu_nhat():
    # live D11: lời nhắc cũ gợi ý derived.largest_*.phases (câu hỏi về ngành) và câu nối "Đây là…" → model đổi câu hỏi
    t = _one(('get_segment_contribution', SEG_2019),
             'Năm 2019 cả {c1} ngành đều giảm R. Ngành giảm ít nhất theo mức đổi R là {c2}, với ΔR là {c3}.',
             [{'id': 'c1', 'path': 'T1.derived.n_groups_down'}, {'id': 'c2', 'path': 'T1.rows[Casual].dimension_value'},
              {'id': 'c3', 'path': 'T1.rows[Casual].delta_r', 'sign': 'am'}], q='Năm 2019 ngành hàng nào giảm ít nhất?')
    errs = ' | '.join(t.validation_errors)
    assert t.status == 'answer_validation_failed'
    assert 'KHÔNG đổi sang trả lời phía lớn nhất' in errs and '.phases' not in errs and 'Đây là' not in errs, errs
    # câu nói giới hạn của tool, không có số, không gọi tên nhóm: không phải claim xếp hạng
    t = _one(('get_segment_contribution', SEG_2019),
             'Năm 2019 cả {c1} ngành đều giảm R: Casual giảm {c2}. Dữ liệu chỉ xếp hạng phía giảm nhiều nhất, không xếp '
             'hạng phía giảm ít nhất.', [{'id': 'c1', 'path': 'T1.derived.n_groups_down'},
                                       {'id': 'c2', 'path': 'T1.rows[Casual].delta_r', 'sign': 'am'}],
             q='Năm 2019 ngành hàng nào giảm ít nhất?')
    assert t.status == 'ok', t.validation_errors
    # live F09 / F08: câu từ chối nhắc cả "N/U/P", câu gợi ý hỏi tiếp → không phải claim
    drv = ('get_revenue_drivers', dict(metric='R', year=2019))
    t = _one(drv, 'Năm 2019, ΔR là {c1}. Với ba thành phần N/U/P, dữ liệu hiện chưa xếp hạng được thành phần nào kéo giảm '
                  'ít nhất. Bạn có thể hỏi thành phần nào kéo giảm nhiều nhất.',
             [{'id': 'c1', 'path': 'T1.rows[0].delta_r', 'sign': 'am'}], q='Thành phần nào kéo giảm ít nhất năm 2019?')
    assert t.status == 'ok', t.validation_errors
    # gọi tên một chủ thể cụ thể thì vẫn kiểm: một thành phần, một giai đoạn, một năm
    for sai in ('Số món mỗi đơn (U) giảm ít nhất, dù dữ liệu chưa xếp hạng phía này. ΔR là {c1}.',
                'Giai đoạn C giảm mạnh nhất, bạn có thể hỏi thêm. ΔR là {c1}.',
                'Năm 2019 giảm mạnh nhất, bạn có thể hỏi thêm. ΔR là {c1}.'):
        t = _one(drv, sai, [{'id': 'c1', 'path': 'T1.rows[0].delta_r', 'sign': 'am'}], q='Năm 2019 thế nào?')
        assert t.status == 'answer_validation_failed', (sai, t.answer_md)
    # nhưng gọi tên nhóm trong câu đó thì vẫn chặn
    t = _one(('get_segment_contribution', SEG_2019), 'Casual giảm ít nhất, dù dữ liệu chỉ xếp hạng phía nhiều nhất.', [],
             q='Năm 2019 ngành hàng nào giảm ít nhất?')
    assert t.status == 'answer_validation_failed'


def test_nhom_giam_it_nhat_tra_loi_thang_bang_smallest():
    # PM 2026-10-09: cần trả lời thẳng "ngành giảm ít nhất là …" → derived.smallest_decrease (tính trên đủ tập)
    q = 'Năm 2019 ngành hàng nào giảm ít nhất?'
    seg = ('get_segment_contribution', SEG_2019)
    t = _one(seg, 'Năm 2019 ngành giảm ít nhất là {c1}, giảm {c2}.',
             [{'id': 'c1', 'path': 'T1.derived.smallest_decrease.groups'},
              {'id': 'c2', 'path': 'T1.derived.smallest_decrease.delta_r', 'sign': 'am'}], q=q)
    assert t.status == 'ok', t.validation_errors
    assert '**Casual**' in t.answer_md and '22.448.071' in t.answer_md
    # câu nối: Casual (câu trước) đúng là ngành giảm ít nhất; GenZ thì không
    t = _one(seg, 'Casual giảm {c1} năm 2019. Đây là ngành giảm ít nhất.',
             [{'id': 'c1', 'path': 'T1.rows[Casual].delta_r', 'sign': 'am'}], q=q)
    assert t.status == 'ok', t.validation_errors
    for sai, claims in [
        ('GenZ giảm {c1} năm 2019. Đây là ngành giảm ít nhất.',                      # GenZ không phải
         [{'id': 'c1', 'path': 'T1.rows[GenZ].delta_r', 'sign': 'am'}]),
        ('Ngành giảm ít nhất là {c1}.', [{'id': 'c1', 'path': 'T1.derived.largest_decrease.groups'}]),   # phía ngược
        ('Ngành kéo giảm nhiều nhất là {c1}.', [{'id': 'c1', 'path': 'T1.derived.smallest_decrease.groups'}]),
        ('Ngành tăng ít nhất là {c1}.', [{'id': 'c1', 'path': 'T1.derived.smallest_decrease.groups'}]),  # ngược chiều
        ('Ngành giảm nhẹ nhất là {c1}.', [{'id': 'c1', 'path': 'T1.derived.largest_decrease.groups'}]),  # "nhẹ nhất"
        ('Năm 2019 GenZ là ngành giảm nhẹ nhất, giảm {c1}.',                                         # không dẫn xếp hạng
         [{'id': 'c1', 'path': 'T1.rows[GenZ].delta_r', 'sign': 'am'}]),
    ]:
        t = _one(seg, sai, claims, q=q)
        assert t.status == 'answer_validation_failed', (sai, t.answer_md)
    # N/U/P chưa có xếp hạng phía nhỏ: "số đơn giảm ít nhất" không được đối chiếu với top_down_driver
    t = _one(('get_revenue_drivers', dict(metric='R', year=2019)), 'R năm 2019 giảm ít nhất ở số đơn (N), góp {c1}.',
             [{'id': 'c1', 'path': 'T1.rows[0].contrib_n', 'sign': 'am'}], q='Thành phần nào giảm ít nhất năm 2019?')
    assert t.status == 'answer_validation_failed'


def test_live_thanh_phan_nhieu_nhat_khong_co_chu_tang_giam():
    # live H04c: năm 2022 R tăng, câu "đóng góp nhiều nhất là giá mỗi món (P)" không có chữ tăng/giảm → theo chiều ΔR
    ok = final(answer='Thành phần đóng góp nhiều nhất là giá mỗi món (P), góp {c1}.',
               claims=[{'id': 'c1', 'path': 'T1.rows[0].contrib_p', 'sign': 'duong'}])
    q = 'R năm 2022 đổi chủ yếu nhờ đâu?'
    assert service.run_turn(q, [], 'duckdb', FakeProvider(
        call('get_revenue_drivers', metric='R', year=2022), ok)).status == 'ok'
    sai = final(answer='Thành phần đóng góp nhiều nhất là số món mỗi đơn (U), góp {c1}.',
                claims=[{'id': 'c1', 'path': 'T1.rows[0].contrib_u'}])
    assert service.run_turn(q, [], 'duckdb', FakeProvider(
        call('get_revenue_drivers', metric='R', year=2022), sai, sai)).status == 'answer_validation_failed'


def test_live_tu_so_sanh_hai_so_thi_chan():
    # E12 live: hỏi tháng 8, model lấy R cả năm rồi tự so "2019 cao hơn 2020" để kết luận
    sai = final('unsupported', 'Chưa có số theo tháng. R 2019 là {c1}, cao hơn R 2020 là {c2}.',
                claims=[{'id': 'c1', 'path': 'T1.rows[0].r'}, {'id': 'c2', 'path': 'T2.rows[0].r'}])
    t = turn(FakeProvider(call('get_revenue_summary', metric='R', year=2019),
                          call('get_revenue_summary', metric='R', year=2020), sai, sai),
             'Tháng 8 năm lẻ có luôn thấp hơn năm chẵn không?')
    assert t.status == 'answer_validation_failed' and any('so sánh' in e for e in t.validation_errors)
    dung = final(answer='R năm 2019 thấp hơn năm 2018, giảm {c1}.',
                 claims=[{'id': 'c1', 'path': 'T1.rows[0].delta_r', 'sign': 'am'}])
    assert turn(FakeProvider(call('get_revenue_drivers', metric='R', year=2019), dung)).status == 'ok'


def test_cau_hoi_dinh_nghia_tra_loi_bang_tool_dinh_nghia():
    # PM hỏi trên app 2026-10-05: "R là gì" → model hỏi lại năm; "what is R stand for" → trả lời không dựa tool, bị chặn
    ok = final(answer='R là doanh thu thực nhận: {c1}. Trạng thái định nghĩa: {c2}.',
               claims=[{'id': 'c1', 'path': 'T1.rows[0].formula'}, {'id': 'c2', 'path': 'T1.rows[0].decision_status'}])
    t = turn(FakeProvider(call('get_metric_definition', metric='R'), ok), 'what is R stand for')
    assert t.status == 'ok', t.validation_errors
    assert 'delivered' in t.answer_md and t.results['T1'].evidence.metrics[0]['metric_id'] == 'R'
    # không gọi tool mà vẫn "ok" thì vẫn chặn; câu báo không còn nhắc "bảng số bên dưới" khi không có bảng
    prose = final(answer='R là doanh thu thực nhận.')
    t = turn(FakeProvider(prose, prose), 'R là gì')
    assert t.status == 'answer_validation_failed' and 'chưa đọc được dữ liệu' in t.message


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


def test_bang_gia_tri_tron_chuoi_va_so_van_ra_arrow():
    """Lỗi 2026-10-05: cột 'Giá trị trong kho' có Decimal (→ chuỗi) cạnh float → ArrowTypeError khi st.dataframe."""
    import pandas as pd
    import pyarrow as pa
    from decimal import Decimal
    from ui.fmt import arrow_safe
    df = pd.DataFrame({'v': [tools.as_plain(Decimal('1136801442.50')), tools.as_plain(-0.391), None], 'n': [1, 2, 3]})
    with pytest.raises(pa.ArrowTypeError):
        pa.Table.from_pandas(df.copy())
    out = arrow_safe(df)
    pa.Table.from_pandas(out)
    assert list(out['v'][:2]) == ['1136801442.50', '-0.391'] and pd.isna(out['v'][2]) and out['n'].dtype == 'int64'


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


@pytest.mark.parametrize('text, number, expect', [
    ('CAGR **−6,4%** mỗi năm', '6,4', True),
    ('CAGR **6,4%** mỗi năm (R giảm)', '6,4', False),                       # B06 live: chữ "giảm" ở sau, số không dấu
    ('Chững, giảm nhẹ (2016→2018), với CAGR **6,4%**', '6,4', False),       # B06 live: chữ "giảm" thuộc tên giai đoạn
    ('giảm mạnh nhất, CAGR **39,1%**', '39,1', False),                      # E13 live
    ('R giảm **57.915.103 VND**', '57.915.103', True),
    ('mức giảm R là **57.915.103 VND**', '57.915.103', True),
    ('đã giảm **45,7%** (% đổi R, 8/2021)', '45,7', True),
    ('−6,4% rồi lại 6,4%', '6,4', False),                                   # mọi lần xuất hiện đều phải đọc ra âm
    ('không có số', '6,4', False),
])
def test_bo_cham_live_nhan_ra_so_am_mat_dau(text, number, expect):
    """Bộ chấm live eval (must_neg) viết độc lập với evidence.py; kiểm nó trên các câu thật đã lọt rubric cũ."""
    import sys
    from dwh.connection import ROOT
    sys.path.insert(0, str(ROOT / 'scripts' / 'ops'))
    from ai_live_eval import neg_shown
    assert neg_shown(text, number) is expect
