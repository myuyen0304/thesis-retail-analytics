"""B8: khung "AI diễn giải" trên trang PS1–PS5 (ai_explain/page_explain.py, ui/ai_panel.py).

Mô hình là provider GIẢ: test chứng minh luồng app (chọn tool theo lựa chọn trang, dừng trước khi gọi AI khi chưa hỗ trợ,
bước kiểm số, cache trong phiên), không chứng minh chất lượng lời của mô hình thật. Số kỳ vọng đọc từ query reporting
độc lập với tool (dwh/queries.py).
"""
import json
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from ai_explain import page_explain as pe
from ai_explain import provider, service
from ai_explain.provider import Reply, ToolCallReq
from dwh import queries
from ui.ai_panel import ai_unavailable
from ui.fmt import trieu, ty

APP = Path(__file__).resolve().parents[1] / 'app.py'


class FakeProvider:
    label = 'fake'

    def __init__(self, *steps):
        self.steps, self.seen, self.tools = list(steps), [], []

    def complete(self, messages, tools_, max_tokens=None):
        self.seen.append([dict(m) for m in messages])
        self.tools.append(tools_)
        return self.steps.pop(0)


def final(answer, claims) -> Reply:
    s = json.dumps({'status': 'ok', 'answer': answer, 'claims': claims}, ensure_ascii=False)
    return Reply(s, [], {'role': 'assistant', 'content': s}, 1000, 80)


PS4_2019 = final('Doanh thu đơn đã giao (R) năm 2019 giảm {c1} so với năm 2018. Số đơn (N) góp {c2}, số món mỗi đơn (U) '
                 'góp {c3}, giá mỗi món (P) góp {c4}. Đây là phân rã số học, chưa phải nguyên nhân.',
                 [{'id': 'c1', 'path': 'T1.rows[0].delta_r', 'sign': 'am'},
                  {'id': 'c2', 'path': 'T1.rows[0].contrib_n', 'sign': 'am'},
                  {'id': 'c3', 'path': 'T1.rows[0].contrib_u', 'sign': 'duong'},
                  {'id': 'c4', 'path': 'T1.rows[0].contrib_p', 'sign': 'duong'}])


def _explain(req, *steps, **kw):
    fake = FakeProvider(*steps)
    return pe.explain(req, 'duckdb', fake, **kw), fake


# ---------------- luồng không có giao diện ----------------

def test_ps4_nam_dung_so_kho_loi_thuong():
    t, fake = _explain(pe.request_ps4('2019', 'year', 2018, 2019, 'Năm 2019 so với 2018'), PS4_2019)
    assert t.status == 'ok' and t.llm_calls == 1
    d = queries.driver_period('duckdb').set_index('period_code').loc['2019']
    # số tiền ghi gọn cho người đọc, đúng số của rpt_driver_period; sau chữ "giảm" in trị tuyệt đối
    assert f'giảm **{trieu(abs(d["delta_r"]), 1)} đồng**' in t.answer_md
    assert f'**{trieu(d["contrib_n"], 1, signed=True)} đồng**' in t.answer_md
    # không còn nhãn kỹ thuật của bước kiểm sau số, không còn số đủ từng đồng
    assert '(phần góp của N' not in t.answer_md and 'VND' not in t.answer_md
    assert t.values and t.prompt_version == pe.PAGE_PROMPT_VERSION
    # app gọi đúng tool theo lựa chọn trang; mô hình không được nhận schema tool nào
    assert t.calls == [('T1', 'get_revenue_drivers', {'metric': 'R', 'year': 2019})]
    assert fake.tools == [[]]


def test_prompt_chat_dung_nguyen_them_ghi_chu_trang():
    t, fake = _explain(pe.request_ps4('2019', 'year', 2018, 2019, 'Năm 2019 so với 2018'), PS4_2019)
    msgs = fake.seen[0]
    assert msgs[0] == {'role': 'system', 'content': service.system_prompt(service.dt.date.today())}
    assert msgs[1]['role'] == 'system' and 'CHẾ ĐỘ GIẢI THÍCH TRANG' in msgs[1]['content']
    assert 'không công thức' in msgs[1]['content'] and 'Năm 2019 so với 2018' in msgs[1]['content']
    assert '"ref": "T1"' in msgs[2]['content']
    # live Databricks 2026-10-18: PS1 gọi R/G là "tỷ lệ thực nhận", G − R là "hụt"; PS2 thêm nhận định không có số
    assert 'Không gọi R là "thực nhận"' in msgs[1]['content']
    assert 'hụt, mất, thất thoát' in msgs[1]['content']
    assert 'không thêm nhận định không có số đi kèm' in msgs[1]['content']
    # live local 2026-10-18: "chủ yếu" không có số xếp hạng (PS5 bị chặn, PS3 / PS4 phải sửa), "không phải ngẫu nhiên" (PS3)
    assert 'Từ xếp hạng hay tỷ trọng (chủ yếu, phần lớn' in msgs[1]['content']
    assert 'Không kết luận kiểu thống kê' in msgs[1]['content'] and '"ngẫu nhiên"' in msgs[1]['content']
    assert pe.PAGE_PROMPT_VERSION == 'b8-2026-10-19'


def test_ps1_ky_va_nam():
    ans = final('Năm 2019, tiền hàng mọi đơn (G) cao hơn doanh thu đơn đã giao (R) {c1}. R chiếm {c2} của G. '
                'Đây là phân rã theo trạng thái đơn, chưa phải nguyên nhân.',
                [{'id': 'c1', 'path': 'T1.derived.gap_g_minus_r'}, {'id': 'c2', 'path': 'T1.rows[0].capture_rate'}])
    t, _ = _explain(pe.request_ps1('2019', 'year'), ans)
    y = queries.revenue_yearly('duckdb').set_index('year').loc[2019]
    assert t.status == 'ok' and f'**{trieu(y["g"] - y["r"], 1)} đồng**' in t.answer_md
    assert '(G − R)' not in t.answer_md and '(R/G' not in t.answer_md
    req = pe.request_ps1('2013-2022', 'total')
    assert req.calls == (('get_revenue_gap', {'period': '2013-2022'}),)


def test_ps2_ps3_ps5_dung_tool():
    assert [c[1]['view'] for c in pe.request_ps2().calls] == ['phases', 'turning_points']
    for code in ('mua_vu', 'cuoi_thang', 'thang_8'):
        assert pe.request_ps3(code).calls == (('get_calendar_pattern', {'pattern': code}),)
    assert pe.request_ps5('region', 2019).calls == (
        ('get_segment_contribution', {'metric': 'R', 'dimension': 'region', 'year': 2019}),)
    ans = final('Năm 2019, ngành kéo giảm nhiều nhất là {c1}. Đây là phần chia số học, chưa phải nguyên nhân.',
                [{'id': 'c1', 'path': 'T1.derived.largest_decrease.groups'}])
    t, _ = _explain(pe.request_ps5('category', 2019), ans)
    assert t.status == 'ok' and '**Streetwear**' in t.answer_md


def test_ps5_so_cua_nhom_giu_ten_nhom():
    # live local 2026-10-19: mô hình gọi ΔR của riêng Streetwear là "mức đổi của toàn công ty"; bản trang bỏ nhãn kỹ thuật nên
    # người đọc không thấy đó là số của một nhóm. Số của nhóm phải giữ tên nhóm; số không thuộc nhóm thì không.
    ans = final('Năm 2019, doanh thu đơn đã giao (R) toàn công ty giảm so với năm trước, mức đổi là {c1}. Ngành kéo giảm '
                'nhiều nhất là {c2}, với mức giảm {c3}. Đây là phân rã số học theo nhóm, chưa phải nguyên nhân.',
                [{'id': 'c1', 'path': 'T1.rows[Streetwear].delta_r', 'sign': 'am'},
                 {'id': 'c2', 'path': 'T1.derived.largest_decrease.groups'},
                 {'id': 'c3', 'path': 'T1.derived.largest_decrease.delta_r', 'sign': 'am'}])
    t, _ = _explain(pe.request_ps5('category', 2019), ans)
    assert t.status == 'ok'
    first, second = t.answer_md.split('. ')[:2]
    assert '** (Streetwear)' in first                  # số của nhóm: tên nhóm hiện ngay sau số
    assert '** (' not in second.split('**Streetwear**')[1]   # số derived không thuộc nhóm nào: không gắn thêm
    # PS4 không thuộc nhóm: bản trang vẫn bỏ nhãn như trước
    t4, _ = _explain(pe.request_ps4('2019', 'year', 2018, 2019, 'Năm 2019 so với 2018'), PS4_2019)
    assert '** (' not in t4.answer_md


@pytest.mark.parametrize('req', [
    pe.request_ps1('2012-2022', 'total'),                                 # kỳ không có tham số tool
    pe.request_ps4('A', 'phase', 2013, 2016, 'Giai đoạn A'),              # catalog chưa mở phân rã theo giai đoạn
    pe.request_ps5('region', 2013),                                       # 2013 chưa có năm gốc đủ 12 tháng
], ids=['ps1_2012_2022', 'ps4_giai_doan', 'ps5_2013'])
def test_lua_chon_chua_ho_tro_khong_goi_ai(req):
    t, fake = _explain(req)                    # provider không có bước nào: gọi là lỗi
    assert t.status == 'unsupported' and t.llm_calls == 0 and fake.seen == []
    assert t.message and t.answer_md is None


def test_so_tu_viet_bi_chan_sau_mot_lan_sua():
    bad = final('R năm 2019 giảm 554,9 triệu so với năm 2018.', [])
    t, fake = _explain(pe.request_ps4('2019', 'year', 2018, 2019, 'Năm 2019 so với 2018'), bad, bad)
    assert t.status == 'answer_validation_failed' and t.llm_calls == 2 and t.answer_md is None
    assert 'Câu trả lời chưa qua bước kiểm' in fake.seen[1][-1]['content']


def test_mo_hinh_goi_tool_thi_khong_chay():
    c = ToolCallReq('id1', 'get_revenue_summary', '{"metric": "R", "year": 2015}')
    call = Reply(None, [c], {'role': 'assistant', 'content': ''}, 100, 10)
    t, fake = _explain(pe.request_ps4('2019', 'year', 2018, 2019, 'Năm 2019 so với 2018'), call, PS4_2019)
    assert t.status == 'ok' and list(t.results) == ['T1']           # không có T2 do mô hình gọi
    assert 'không gọi tool' in fake.seen[1][-1]['content']


def test_het_han_muc_phien_thi_dung_truoc():
    t, fake = _explain(pe.request_ps4('2019', 'year', 2018, 2019, 'Năm 2019 so với 2018'),
                       session_tokens_used=service.SESSION_TOKEN_LIMIT - 10)
    assert t.status == 'budget_exceeded' and fake.seen == []


def test_dieu_kien_dung_ai_chung_voi_chat(monkeypatch):
    monkeypatch.delenv('PG_AI_USER', raising=False)
    assert 'PG_AI_USER' in ai_unavailable('postgres', object())
    assert '.env.ai.local' in ai_unavailable('duckdb', None)
    assert ai_unavailable('duckdb', object()) is None


# ---------------- trên trang (AppTest) ----------------

def _page(monkeypatch, page, fake):
    monkeypatch.setenv('RETAIL_BACKEND', 'duckdb')
    monkeypatch.setattr(provider, 'from_config', lambda: fake)
    st.cache_data.clear()
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    at.switch_page(page).run()
    assert not at.exception and not at.error
    return at


def _ai_button(at):
    return next(b for b in at.button if b.label == 'Nhờ AI diễn giải')


def test_trang_ps4_bam_nut_roi_khong_goi_lai(monkeypatch):
    fake = FakeProvider(PS4_2019)
    at = _page(monkeypatch, 'views/ps4_don_mon_gia.py', fake)
    assert fake.seen == []                                          # mở trang không tự gọi AI
    assert any('AI diễn giải' in m.value for m in at.markdown)
    _ai_button(at).click().run()
    assert not at.exception and len(fake.seen) == 1
    d = queries.driver_period('duckdb').set_index('period_code').loc['2019']
    assert any(f'{trieu(abs(d["delta_r"]), 1)} đồng' in m.value for m in at.markdown)
    assert any(e.label == 'Số liệu AI đã dùng' for e in at.expander)
    at.run()                                                        # rerun: vẫn hiện, không gọi lại
    at.selectbox[0].select('2017').run()
    at.selectbox[0].select('2019').run()                            # đổi lựa chọn rồi quay lại: lấy từ cache
    assert len(fake.seen) == 1
    assert any(f'{trieu(abs(d["delta_r"]), 1)} đồng' in m.value for m in at.markdown)
    assert at.session_state['ai_tokens'] == 1080


def test_trang_ps4_giai_doan_bao_chua_ho_tro(monkeypatch):
    fake = FakeProvider()
    at = _page(monkeypatch, 'views/ps4_don_mon_gia.py', fake)
    at.selectbox[0].select('A').run()
    _ai_button(at).click().run()
    assert not at.exception and fake.seen == []
    assert any('AI chưa giải thích được lựa chọn này' in c.value and 'get_revenue_drivers' not in c.value
               for c in at.caption)
    assert any(pl.proto.label == 'Xem năm 2016 so với 2015 để AI giải thích' for pl in at.get('page_link'))


def test_trang_ps1_ky_2012_2022_khong_co_nut(monkeypatch):
    # kỳ mặc định của PS1 (deck slide 4) AI chưa giải thích: không có nút, có link sang kỳ 2013–2022 (?ky=)
    at = _page(monkeypatch, 'views/ps1_do_dung.py', FakeProvider())
    assert not any(b.label == 'Nhờ AI diễn giải' for b in at.button)
    assert any('AI chưa giải thích được lựa chọn này' in c.value for c in at.caption)
    assert any(pl.proto.label == 'Xem kỳ 2013–2022 để AI giải thích' for pl in at.get('page_link'))
    assert pe.request_ps1('2012-2022', 'total').alt[1] == {'ky': '2013-2022'}


@pytest.mark.parametrize('page', ['views/ps2_xu_huong.py', 'views/ps3_nhip_lich.py', 'views/ps5_nhom.py'])
def test_moi_trang_ps_co_khung_ai(monkeypatch, page):
    at = _page(monkeypatch, page, FakeProvider())
    assert any('AI diễn giải' in m.value for m in at.markdown)
    assert any(b.label == 'Nhờ AI diễn giải' for b in at.button)
    assert any('không do AI viết' in c.value for c in at.caption)
    # lối sang trang chat luôn hiện dưới khung, cả khi chưa bấm (ảnh 2026-10-18: bản đầu thoát sớm nên mất link)
    assert any('Hỏi dữ liệu (AI)' in pl.proto.label for pl in at.get('page_link'))


# ---------------- bản dữ liệu cũ chưa có cột mới (app trước, pipeline sau) ----------------

def test_ps1_ps3_chay_voi_ban_chua_co_cot_moi(monkeypatch):
    total, yearly, stab = queries.revenue_total, queries.revenue_yearly, queries.calendar_stability
    monkeypatch.setattr(queries, 'revenue_total', lambda b: total(b).drop(columns='gap_g_minus_r'))
    monkeypatch.setattr(queries, 'revenue_yearly', lambda b: yearly(b).drop(columns='gap_g_minus_r'))
    monkeypatch.setattr(queries, 'calendar_stability', lambda b: stab(b).drop(columns=['peak_month', 'trough_month']))
    at = _page(monkeypatch, 'views/ps1_do_dung.py', FakeProvider())
    assert [m.label for m in at.metric][:3] == ['G: tiền hàng mọi đơn', 'R: doanh thu đơn đã giao', 'Tỷ lệ R/G']
    at.switch_page('views/ps3_nhip_lich.py').run()
    assert not at.exception and not at.error
    assert any('tháng cao và thấp xem trên bảng nhiệt' in m.value for m in at.markdown)


def test_ps3_ten_thang_doc_tu_cot_dbt(monkeypatch):
    at = _page(monkeypatch, 'views/ps3_nhip_lich.py', FakeProvider())
    s = queries.calendar_stability('duckdb').set_index('rhythm_code').loc['mua_vu']
    assert any(f'T{int(s["peak_month"])} có R cao nhất; T{int(s["trough_month"])} thấp nhất' in m.value
               for m in at.markdown)
    assert pd.notna(s['peak_month'])
