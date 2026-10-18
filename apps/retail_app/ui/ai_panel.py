"""Khung "AI diễn giải" trên các trang PS1–PS5 (B8, ai_explain/page_explain.py).

Khác trang chat: không có ô nhập, không có hội thoại; AI chỉ giải thích đúng lựa chọn đang xem trên trang. Khung có màu
và nhãn riêng để người xem nhận ra phần nào do AI viết. AI chỉ chạy khi người xem bấm nút (không tự gọi khi mở trang:
tốn token, trang chậm). Kết quả giữ trong phiên theo (trang, lựa chọn, backend, bản dữ liệu, phiên bản prompt), nên đổi
lựa chọn rồi quay lại, hay rerun, không gọi lại mô hình. Token cộng vào cùng hạn mức phiên với trang chat.
"""
import os

import pandas as pd
import streamlit as st

from ai_explain import links, page_explain, provider, service, tools
from dwh.connection import release_for_read
from dwh.guarded import ai_databricks_principal
from ui.common import BACKEND_LABEL, backend, load_or_stop
from ui.fmt import arrow_safe

CHAT_PAGE = 'views/ai_explain.py'
_STYLE = ('{k} {{background: rgba(124, 58, 237, 0.06); border-color: rgba(124, 58, 237, 0.55) !important;}}'
          '{k} [data-testid="stCaptionContainer"] {{color: inherit; opacity: 0.75;}}')


def ai_unavailable(b: str, p) -> str | None:
    """Vì sao AI (chat hoặc khung trang) chưa dùng được với backend b và provider p; None nếu dùng được."""
    if b not in service.CHAT_BACKENDS:
        return f'AI chưa hỗ trợ **{BACKEND_LABEL[b]}**. Chọn backend khác ở thanh bên.'
    if b == 'postgres' and not os.environ.get('PG_AI_USER'):
        return ('Trên PostgreSQL, AI đọc bằng tài khoản chỉ-đọc riêng: đặt `PG_AI_USER` / `PG_AI_PASSWORD` (tạo bằng '
                '`scripts/ops/pg_ai_readonly_role.py`) rồi mở lại app. Hoặc chọn **DuckDB** ở thanh bên.')
    if b == 'databricks' and not all(ai_databricks_principal()):
        return ('Trên Databricks, AI đọc bằng service principal chỉ-đọc riêng (không dùng tài khoản đăng nhập của bạn): '
                'cần `RETAIL_AI_DBX_CLIENT_ID` / `RETAIL_AI_DBX_CLIENT_SECRET` trong `.env.ai.local` hoặc secret của app.')
    if p is None:
        return ('Chưa cấu hình mô hình AI. Tạo file `.env.ai.local` ở thư mục gốc repo (đã Git ignore) với dòng '
                "`RETAIL_AI_API_KEY='...'` (khóa API DeepSeek), rồi mở lại app. Không dán khóa vào chat hay commit.")
    return None


def _data_key(b: str) -> str:
    """Bản dữ liệu đang đọc: release_id ở chế độ versioned, mốc dựng kho ở chế độ cũ."""
    record = release_for_read(b)
    return record['release_id'] if record else str(load_or_stop('build_info').iloc[0]['built_at_utc'])


def _friendly(msg: str) -> str:
    """Lý do từ chối của tool, bỏ phần mã nội bộ ("Catalog chưa mở khả năng này: get_x / R / phase / None: ...")."""
    if msg.startswith('Catalog chưa mở'):
        msg = msg.rsplit(': ', 1)[-1]
    return msg[:1].upper() + msg[1:]


def _md(s: str) -> str:
    return s.replace('$', r'\$')


def _alt_link(req: page_explain.PageRequest) -> None:
    """Lựa chọn này AI chưa giải thích được: link mở lại chính trang với lựa chọn gần nhất AI giải thích được (dùng
    query params như deep link của chat, ui.common.url_choice)."""
    if req.alt:
        label, params = req.alt
        st.page_link(links.PAGES[req.page][0], label=label, icon=':material/arrow_forward:', query_params=params)


def _render(t: service.TurnResult, req: page_explain.PageRequest, cache: dict, ck) -> None:
    if t.status == 'ok':
        st.markdown(_md(t.answer_md))
        for n in t.app_notes:
            st.caption(_md(n))
        st.caption('AI viết lời; mọi con số trong đoạn trên do app lấy từ kho và kiểm trước khi hiện.')
        with st.expander('Số liệu AI đã dùng'):
            st.dataframe(arrow_safe(pd.DataFrame([
                {'Con số': shown, 'Giá trị trong kho': tools.as_plain(v), 'Lấy từ': path}
                for path, v, shown in t.values.values()])), hide_index=True, width='stretch')
            for ref, tool, args in t.calls:
                e = t.results[ref].evidence
                st.caption(f'{ref}: {e.source_description} · kho dựng lúc {e.data_version.get("built_at_utc")} UTC · '
                           f'đọc lúc {e.read_at_utc}')
            st.caption(f'{t.model} · prompt trang {t.prompt_version} · {t.llm_calls} lần gọi · {t.tokens} token')
        return
    if t.status in ('unsupported', 'no_data'):
        st.caption('AI chưa giải thích được lựa chọn này. ' + _md(_friendly(t.message)))
        _alt_link(req)
        return
    st.warning(_md(t.message or 'AI chưa tạo được lời diễn giải.'))
    if st.button('Thử lại', key=f'ai_retry_{req.page}'):
        cache.pop(ck, None)
        st.rerun()


def _body(req: page_explain.PageRequest) -> None:
    b, p = backend(), provider.from_config()
    if (why := ai_unavailable(b, p)) is not None:
        st.caption('AI chưa dùng được ở đây. ' + why)
        return
    if not req.calls:
        st.caption('AI chưa giải thích được lựa chọn này. ' + req.reason)
        _alt_link(req)
        return
    cache = st.session_state.setdefault('ai_page', {})
    ck = (b, _data_key(b), page_explain.PAGE_PROMPT_VERSION, req.key)
    t = cache.get(ck)
    if t is None:
        st.caption(f'Đang xem: {req.label}. Bấm để AI viết lời giải thích từ số liệu của đúng lựa chọn này.')
        if not st.button('Nhờ AI diễn giải', key=f'ai_btn_{req.page}', icon=':material/auto_awesome:'):
            return
        with st.spinner('AI đang đọc số liệu của lựa chọn này…'):
            t = page_explain.explain(req, b, p, session_tokens_used=st.session_state.get('ai_tokens', 0))
        cache[ck] = t
        st.session_state.ai_tokens = st.session_state.get('ai_tokens', 0) + t.tokens
    else:
        st.caption(f'Đang xem: {req.label}.')
    _render(t, req, cache, ck)


def ai_panel(req: page_explain.PageRequest) -> None:
    """Khung AI của một trang. Gọi trong cột bên phải, sau phần tóm tắt theo quy tắc."""
    key = f'ai_panel_{req.page}'
    st.html(f'<style>{_STYLE.format(k=f".st-key-{key}")}</style>')
    with st.container(border=True, key=key):
        st.markdown(':violet[**:material/auto_awesome: AI diễn giải**]')
        _body(req)
    st.page_link(CHAT_PAGE, label='Muốn hỏi câu khác? Mở trang Hỏi dữ liệu (AI)', icon=':material/forum:')
