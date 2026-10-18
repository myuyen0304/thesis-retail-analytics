"""B7: router chọn level (mục "CHỌN TOOL (router)" trong system prompt, docs/giao_viec_agent_gd2.md §3.7).

Mô hình giả, không gọi API: PASS ở đây KHÔNG phải live-model eval. Việc chọn tool là của mô hình thật nên file này không
chứng minh router chọn đúng; file này chứng minh app giữ đúng luật ở từng nhánh khi mô hình đã chọn tool (L1 số liệu
lịch sử, L2 biểu đồ + nút mở trang, L3 dự báo, câu trộn thực tế / dự báo, ngoài phạm vi, mơ hồ, tiếp nối), và chặn câu
trả lời sai ở nhánh trộn. Router chọn tool đúng hay không đo bằng bộ held-out (scripts/ops/ai_live_eval.py --set b7).
Câu hỏi ở đây khác câu của bộ held-out.
"""
import datetime as dt

import pytest

from ai_explain import links, service
from tests.test_ai_chat import FakeProvider, call, final
from tests.test_ai_forecast import ref, versioned          # noqa: F401 (fixture)


def _turn(q, *steps, history=()):
    return service.run_turn(q, list(history), 'duckdb', FakeProvider(*steps))


def test_prompt_co_muc_router_tro_toi_quy_tac_chi_tiet():
    p = service.system_prompt(dt.date(2026, 10, 18))
    router = p[p.index('CHỌN TOOL (router)'):p.index('QUY TẮC BẮT BUỘC')]
    for x in ('Thực tế tới 2022', 'quy tắc 16', 'Vẽ: 17', 'Trộn thực tế và dự báo', '"unsupported"', 'Mơ hồ: 2',
              'Tiếp nối: 9'):
        assert x in router, x
    assert 'hai câu riêng' in p and 'không đặt cạnh nhau' in p and 'CÙNG định nghĩa' in p
    assert service.PROMPT_VERSION.startswith('b7-')


# --- L1: số liệu lịch sử, có nút mở trang PS kèm bộ lọc ---

def test_l1_so_lieu_lich_su_va_nut_mo_trang():
    t = _turn('Năm 2018, G hụt thành R bao nhiêu?', call('get_revenue_gap', period='year', year=2018),
              final(answer='Năm 2018, G − R là {c1}.', claims=[{'id': 'c1', 'path': 'T1.derived.gap_g_minus_r'}]))
    assert t.status == 'ok', t.validation_errors
    assert 'thực tế' not in t.answer_md                     # chỉ câu trộn mới gắn nhãn "thực tế"
    assert [lk.page for lk in links.page_links(t.calls, t.results)] == ['views/ps1_do_dung.py']


# --- L2: biểu đồ vẽ từ kết quả tool trong cùng lượt ---

def test_l2_bieu_do_tu_ket_qua_cua_luot():
    t = _turn('Vẽ R đầu kỳ của từng giai đoạn', call('get_revenue_trend', view='phases'),
              call('show_chart', ref='T1', y='r_start'), final(answer='Biểu đồ R đầu kỳ của các giai đoạn ở dưới.'))
    assert t.status == 'ok', t.validation_errors
    assert [(s.ref, list(s.y)) for s in t.charts] == [('T1', ['r_start'])]
    assert [lk.page for lk in links.page_links(t.calls, t.results)] == ['views/ps2_xu_huong.py']


def test_l2_bieu_do_khong_co_tool_nguon_bi_tu_choi():
    t = _turn('Vẽ R theo giai đoạn', call('show_chart', ref='T1', y='r_start'),
              final(status='unsupported', answer='Chưa vẽ được vì lượt này chưa đọc dữ liệu.'))
    assert t.charts == [] and t.chart_calls[0][1] != 'ok'


# --- L3: dự báo, nhãn do app gắn ---

def test_l3_du_bao_co_nhan_cua_app(versioned):
    t = _turn('Dự báo G tháng 12/2023?', call('get_forecast', metric='G', period='month', year=2023, month=12),
              final(answer='Dự báo G tháng 12/2023 là {c1}.', claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}]))
    assert t.status == 'ok', t.validation_errors
    assert '(dự báo G, 12/2023' in t.answer_md and 'thực tế' not in t.answer_md
    assert [lk.page for lk in links.page_links(t.calls, t.results)] == ['views/du_bao.py']


# --- câu trộn thực tế và dự báo ---

_Q_MIX = 'G thực tế tháng 12/2021 và G dự báo tháng 12/2023 là bao nhiêu?'
_MIX_G = [call('get_revenue_monthly', metric='G', year=2021, month=12),
          call('get_forecast', metric='G', period='month', year=2023, month=12)]
_MIX_R = [call('get_revenue_monthly', metric='R', year=2021, month=12),
          call('get_forecast', metric='G', period='month', year=2023, month=12)]


def _mix(answer, tools_=_MIX_G, q=_Q_MIX, actual='g'):
    rep = final(answer=answer, claims=[{'id': 'c1', 'path': f'T1.rows[0].{actual}'},
                                       {'id': 'c2', 'path': 'T2.rows[0].g_forecast'}])
    return _turn(q, *tools_, rep, rep)


def test_tron_hai_cau_qua_va_moi_phan_mot_nhan(versioned):
    t = _mix('G thực tế tháng 12/2021 là {c1}. Dự báo G tháng 12/2023 là {c2}.')
    assert t.status == 'ok', t.validation_errors      # trước B7: luật rv12f ép no_data vì 12/2021 "ngoài vùng dự báo"
    assert '(G thực tế, 12/2021)' in t.answer_md and '(dự báo G, 12/2023' in t.answer_md
    assert {tool for _, tool, _ in t.calls} == {'get_revenue_monthly', 'get_forecast'}


def test_tron_so_thuc_te_khong_ghi_chu_van_co_nhan_thuc_te_cua_app(versioned):
    t = _mix('G tháng 12/2021 là {c1}. Dự báo G tháng 12/2023 là {c2}.')
    assert t.status == 'ok', t.validation_errors
    assert '(G thực tế, 12/2021)' in t.answer_md                    # app gắn, không tin chữ mô hình viết


def test_tron_r_thuc_te_va_g_du_bao_hai_cau(versioned):
    t = _mix('R thực tế tháng 12/2021 là {c1}. Dự báo chỉ có G: dự báo G tháng 12/2023 là {c2}.', _MIX_R,
             'R thực tế tháng 12/2021 và dự báo doanh thu tháng 12/2023?', actual='r')
    assert t.status == 'ok', t.validation_errors
    assert '(R thực tế, 12/2021)' in t.answer_md and '(dự báo G, 12/2023' in t.answer_md


@pytest.mark.parametrize('answer,tools_,actual', [
    ('G thực tế tháng 12/2021 là {c1}, còn dự báo G tháng 12/2023 là {c2}.', _MIX_G, 'g'),          # chung một câu
    ('Dự báo G tháng 12/2023 là {c2}, cao hơn G thực tế tháng 12/2021 là {c1}.', _MIX_G, 'g'),      # so trực tiếp
    ('G thực tế tháng 12/2021 là {c1}. Dự báo G tháng 12/2023 là {c2}, chênh không nhiều so với năm 2021.', _MIX_G, 'g'),
    ('G thực tế tháng 12/2021 là {c1}. Dự báo G tháng 12/2023 là {c2}. Như vậy dự báo thấp hơn thực tế.', _MIX_G, 'g'),
    ('R thực tế tháng 12/2021 là {c1}, dự báo G tháng 12/2023 là {c2}.', _MIX_R, 'r'),             # R cạnh G dự báo
    ('Dự báo G tháng 12/2023 là {c2}, giảm so với R thực tế tháng 12/2021 ({c1}).', _MIX_R, 'r'),
])
def test_tron_sai_bi_chan(versioned, answer, tools_, actual):
    t = _mix(answer, tools_, actual=actual)
    assert t.status == 'answer_validation_failed' and not t.answer_md, (answer, t.status, t.answer_md)


def test_tron_cau_phu_dinh_khong_bi_chan_nham(versioned):
    t = _mix('G thực tế tháng 12/2021 là {c1}. Dự báo G tháng 12/2023 là {c2}. Hai số không cộng, trừ hay so với nhau.')
    assert t.status == 'ok', t.validation_errors


def test_ky_sau_vung_du_bao_van_theo_rv12f(versioned):
    # 2025 ngoài cả dữ liệu thực tế lẫn vùng dự báo: vẫn phải trả no_data (luật rv12f giữ nguyên cho kỳ sau vùng)
    rep = final(answer='Dự báo G tháng 12/2023 là {c1}.', claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}])
    t = _turn('Dự báo G năm 2025 và tháng 12/2023?', _MIX_G[1], rep, rep)
    assert t.status == 'answer_validation_failed', (t.status, t.answer_md)


# --- ngoài phạm vi, mơ hồ, tiếp nối ---

def test_ngoai_pham_vi_khong_goi_tool():
    t = _turn('Kho hàng còn bao nhiêu áo khoác?', final(status='unsupported',
                                                        answer='Chưa hỗ trợ câu hỏi tồn kho; chỉ có doanh thu PS1–PS5.'))
    assert t.status == 'unsupported' and t.calls == [] and t.answer_md


def test_ngoai_pham_vi_khong_duoc_viet_so():
    rep = final(status='unsupported', answer='Tồn kho khoảng 120 chiếc, nhưng chưa hỗ trợ.')
    t = _turn('Kho hàng còn bao nhiêu áo khoác?', rep, rep)
    assert t.status == 'answer_validation_failed'


def test_mo_ho_hoi_lai():
    t = _turn('Doanh thu ra sao?', final(status='needs_clarification', answer='Bạn muốn xem R hay G, năm nào?'))
    assert t.status == 'needs_clarification' and t.calls == []


def test_tiep_noi_giu_ngu_canh_tool_va_goi_lai_tool(versioned):
    t1 = _turn('Dự báo G tháng 12/2023?', _MIX_G[1],
               final(answer='Dự báo G tháng 12/2023 là {c1}.', claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}]))
    fake = FakeProvider(call('get_forecast', metric='G', period='month', year=2024, month=1),
                        final(answer='Dự báo G tháng 1/2024 là {c1}.', claims=[{'id': 'c1', 'path': 'T1.rows[0].g_forecast'}]))
    t2 = service.run_turn('Còn tháng 1/2024?', [t1.context()], 'duckdb', fake)
    assert t2.status == 'ok', t2.validation_errors
    ctx = next(m['content'] for m in fake.seen[0] if m['content'].startswith('NGỮ CẢNH CÁC LƯỢT TRƯỚC'))
    assert '"get_forecast"' in ctx and '"month": 12' in ctx and 'Dự báo G tháng 12/2023 là' not in ctx
    assert t2.calls[0][2]['month'] == 1 and '(dự báo G, 01/2024' in t2.answer_md
