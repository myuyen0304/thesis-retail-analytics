"""Trang Hỏi dữ liệu (AI): chat PS1–PS5 (docs/ai_explain_plan.md, mốc AI2–AI3).

Câu trả lời chỉ hiện SAU khi qua ai_explain/evidence.py (không stream câu chưa kiểm). Lịch sử lưu trong session_state;
rerun (đổi trang, bấm nút) chỉ vẽ lại, KHÔNG gọi lại mô hình (case E20). Đổi backend thì xóa hội thoại.
"""
import json
import os

import pandas as pd
import streamlit as st

from ai_explain import metric_catalog as cat
from ai_explain import provider, service, tools
from dwh.guarded import ai_databricks_principal
from ui.common import BACKEND_LABEL, backend, notes, page_header
from ui.fmt import arrow_safe, num

page_header('Hỏi dữ liệu (AI)', 'Hỏi bằng tiếng Việt về doanh thu PS1–PS5; mọi con số lấy từ kho và có bằng chứng.')

GOI_Y = {q: q for q in [
    'G hụt thành R bao nhiêu năm 2019, khoản nào lớn nhất?',          # PS1
    'Doanh thu chia mấy giai đoạn, giai đoạn nào giảm mạnh nhất?',    # PS2
    'Tháng 8 năm lẻ có luôn thấp hơn năm chẵn không?',               # PS3
    'Vì sao R năm 2019 giảm?',                                         # PS4
    'Ngành hàng nào kéo giảm R nhiều nhất năm 2019?',                  # PS5
]}
TRANG_THAI = {
    'needs_clarification': ('info', 'Cần làm rõ'), 'unsupported': ('info', 'Chưa hỗ trợ'),
    'no_data': ('info', 'Không có dữ liệu'), 'quality_blocked': ('warning', 'Kho chưa qua kiểm'),
    'query_error': ('warning', 'Truy vấn lỗi'), 'answer_validation_failed': ('warning', 'Chưa tạo được diễn giải'),
    'provider_error': ('warning', 'Không gọi được mô hình'), 'budget_exceeded': ('warning', 'Hết hạn mức phiên'),
}

b = backend()
if st.session_state.get('ai_backend') != b:          # cách ly ngữ cảnh/bằng chứng giữa các backend (E20)
    st.session_state.ai_turns, st.session_state.ai_tokens, st.session_state.ai_backend = [], 0, b


def _md(s: str) -> str:
    return s.replace('$', r'\$')          # st.markdown coi $...$ là công thức


def _rows_df(rows: list[dict]) -> pd.DataFrame:
    return arrow_safe(pd.DataFrame([{k: tools.as_plain(v) if not isinstance(v, (int, float, str, type(None))) else v
                                     for k, v in r.items()} for r in rows]))


def _values_df(values: dict) -> pd.DataFrame:
    return arrow_safe(pd.DataFrame([{'Chỗ': k, 'Tham chiếu': p, 'Giá trị trong kho': tools.as_plain(v), 'Hiển thị': s}
                                     for k, (p, v, s) in values.items()]))


def _evidence(ref: str, tool: str, args, res) -> None:
    label = f'Bằng chứng {ref}: `{tool}` {json.dumps(args, ensure_ascii=False)} → {res.status}'
    with st.expander(label):
        st.markdown(_md(res.message))
        if not res.ok:
            for k, v in res.rejected.items():
                st.caption(f'Bị từ chối `{k}`: {v}')
            return
        e = res.evidence
        st.dataframe(_rows_df(res.rows), hide_index=True)
        if res.derived:
            st.json({k: service.plain(v) for k, v in res.derived.items()}, expanded=False)
        st.markdown(f'**Kỳ/bộ lọc đã áp dụng:** `{json.dumps(service.plain(e.filters_applied), ensure_ascii=False)}` · '
                    f'**Grain:** {e.grain}')
        if e.method:
            st.markdown(f'**Phương pháp:** {e.method}')
        defs = [f"{m['label_vi']} ({'đã chốt' if m['decision_status'] == 'chot' else 'đề xuất, chờ PM/BA'})"
                for m in e.metrics]
        st.markdown('**Định nghĩa:** ' + '; '.join(defs))
        st.caption(f"Nguồn: {e.source_description} · kho dựng lúc {e.data_version.get('built_at_utc')} UTC · "
                   f"health {e.quality.get('status_code')} ({e.quality.get('n_tests_run')} test) · "
                   f"định nghĩa {e.definition_version} · tool {e.tool_version} · đọc lúc {e.read_at_utc} · "
                   f"request_id {e.request_id}")
        for q in e.queries:
            st.code(f'-- {q.source}; tham số {list(q.params)}\n{q.sql}', language='sql')


def _turn(t: service.TurnResult) -> None:
    with st.chat_message('user'):
        st.markdown(_md(t.question))
    with st.chat_message('assistant'):
        kind, nhan = TRANG_THAI.get(t.status, (None, None))
        if t.status == 'ok':
            st.markdown(_md(t.answer_md))
        else:
            text = t.answer_md or t.message or '; '.join(r.message for r in t.results.values()) or nhan
            getattr(st, kind)(f'**{nhan}.** {_md(text)}')
        if any(tool == 'get_revenue_drivers' and t.results[r].ok for r, tool, _ in t.calls):
            st.caption('Phần góp N → U → P là phân rã số học, cho biết ΔR "nằm ở đâu", không chứng minh nguyên nhân.')
        if t.values:
            with st.expander('Các con số trong câu trả lời lấy từ đâu'):
                st.dataframe(_values_df(t.values), hide_index=True)
        for ref, tool, args in t.calls:
            _evidence(ref, tool, args, t.results[ref])
        if t.validation_errors:
            with st.expander('Vì sao câu diễn giải bị chặn'):
                for e in t.validation_errors:
                    st.markdown(f'- {_md(e)}')
        st.caption(f'{t.model} · prompt {t.prompt_version} · {t.llm_calls} lần gọi mô hình · '
                   f'{num(t.tokens)} token · {num(t.latency_s, 1)} giây')


p = provider.from_config()
if b not in service.CHAT_BACKENDS:
    st.info(f'Chat chưa hỗ trợ **{BACKEND_LABEL[b]}**. Chọn backend khác ở thanh bên để hỏi.')
elif b == 'postgres' and not os.environ.get('PG_AI_USER'):
    st.info('Trên PostgreSQL, chat đọc bằng tài khoản chỉ-đọc riêng: đặt `PG_AI_USER` / `PG_AI_PASSWORD` (tạo bằng '
            '`scripts/ops/pg_ai_readonly_role.py`) rồi mở lại app. Hoặc chọn **DuckDB** ở thanh bên.')
elif b == 'databricks' and not all(ai_databricks_principal()):
    st.info('Trên Databricks, chat đọc bằng service principal chỉ-đọc riêng (không dùng tài khoản đăng nhập của bạn): '
            'cần `RETAIL_AI_DBX_CLIENT_ID` / `RETAIL_AI_DBX_CLIENT_SECRET` trong `.env.ai.local` hoặc secret của app.')
elif p is None:
    st.info('Chưa cấu hình mô hình AI. Tạo file `.env.ai.local` ở thư mục gốc repo (đã Git ignore) với dòng '
            "`RETAIL_AI_API_KEY='...'` (khóa API DeepSeek), rồi mở lại app. Không dán khóa vào chat hay commit.")
else:
    turns = st.session_state.ai_turns
    c1, c2 = st.columns([4, 1])
    c1.caption(f'Mô hình **{p.label}** · đọc **{BACKEND_LABEL[b]}** · đã dùng {num(st.session_state.ai_tokens)}/'
               f'{num(service.SESSION_TOKEN_LIMIT)} token của phiên · tối đa {service.MAX_TOOL_CALLS} lần đọc kho mỗi câu.')
    if c2.button('Xóa hội thoại', disabled=not turns):
        st.session_state.ai_turns, st.session_state.ai_tokens = [], 0
        st.session_state.pop('ai_goi_y', None)      # gợi ý đã chọn trước đó không được tự hỏi lại
        st.rerun()
    for t in turns:
        _turn(t)
    hoi = None
    if not turns:
        chon = st.pills('Gợi ý', list(GOI_Y), label_visibility='collapsed', key='ai_goi_y')
        hoi = GOI_Y.get(chon)
    hoi = st.chat_input('Hỏi về R, G, phân rã N/U/P, nhóm hàng/khu vực/kênh theo năm...', submit_mode='disable') or hoi
    if hoi:
        with st.spinner('Đang đọc kho và kiểm số...'):
            t = service.run_turn(hoi, [x.context() for x in turns], b, p,
                                 session_tokens_used=st.session_state.ai_tokens)
        turns.append(t)
        st.session_state.ai_tokens += t.tokens
        st.rerun()

notes(
    cach_doc=[
        'Mô hình chỉ **chọn công cụ** và **viết câu**; số do kho tính. Mỗi con số trong câu trả lời là một tham chiếu vào '
        'kết quả truy vấn của chính câu đó, app tra giá trị thật rồi mới hiện. Mở **Bằng chứng** để xem bảng, câu SQL, '
        'bộ lọc, định nghĩa và bản kho đã đọc.',
        'Câu hỏi tiếp nối ("còn theo khu vực?") giữ năm/chỉ tiêu của câu trước và đọc kho lại; không dùng lại số cũ.',
        'Đang mở: PS1 G → R theo năm hoặc cả kỳ 2013–2022, R/G một tháng; PS2 bốn giai đoạn và ba điểm đổi hướng; '
        'PS3 mùa vụ, dồn cuối tháng, tháng 8 năm lẻ/chẵn; PS4 R so năm trước và phân rã N → U → P (từ 2014); '
        f'PS5 R theo một chiều ({", ".join(cat.DIMENSIONS)}) × năm.',
    ],
    gioi_han=[
        'Chưa mở: số khách C theo nhóm, lọc nhiều chiều, nhiều tháng / quý / khoảng ngày tùy ý, G so năm trước, phân rã '
        'N/U/P theo giai đoạn, tháng đổi hướng do dữ liệu tự tìm. Hỏi những câu này thì trợ lý báo chưa hỗ trợ.',
        'Số PS3 theo giai đoạn dùng cách gom năm ranh giới đề xuất (chờ BA chốt); số cả kỳ 2013–2022 không phụ thuộc '
        'quy ước này.',
        'Phân rã là số học, không phải nguyên nhân (marketing, churn, tồn kho... không có trong dữ liệu).',
        'Câu diễn giải không qua bước kiểm số thì không hiện; khi đó chỉ hiện bảng số lấy thẳng từ kho.',
        'Tiền ghi VND: dữ liệu nguồn không ghi đơn vị tiền tệ, PM chốt dùng VND ngày 2026-10-05.',
    ],
)
