"""Khung giao diện kiểu report BI dùng chung của các trang phân tích: ô số thứ tự 01–04, hàng hai cột co giãn, bảng đối
chứng, định dạng biểu đồ, câu hỏi kiểm tra tiếp. Chỉ trình bày, không tính số: mọi giá trị do trang truyền vào đã đọc từ DWH.

CSS chỉ áp trên trang có gọi nap_css(), trong các container có key bắt đầu bằng bi_ hoặc the_, nên không đụng thanh bên,
đăng nhập hay trang chưa dùng khung này.
"""
from dataclasses import dataclass, field

import pandas as pd
import streamlit as st

from ui import roles

# App dùng theme mặc định của Streamlit: nền trắng hay tối theo trình duyệt người xem, nên mọi màu ở đây phải đọc được trên cả hai.
# Màu biểu đồ đã qua scripts/validate_palette.js của skill dataviz, kể cả mô phỏng mù màu.
# Không dùng cặp xanh lục / đỏ: ΔE chỉ 4,4 với mù màu đỏ-lục. Nhãn số luôn có dấu + / − nên màu không phải tín hiệu duy nhất.
MAU_TONG, MAU_TANG, MAU_GIAM = '#5B4BD6', '#0F9488', '#DC5A3C'
MAU_NUP = ['#5B4BD6', '#C2811F', '#2389C4']       # N, U, P
# Nhiều nhóm (PS5 tới 6 nhóm): 5 màu đầu đạt hết các kiểm tra; màu 6 ΔE 6,7 với mù màu nên biểu đồ phải có hình điểm khác nhau.
MAU_NHOM = ['#5B4BD6', '#C2811F', '#0F9488', '#DC5A3C', '#2389C4', '#A8489A']
MAU_NOI = '#8A90A8'                               # đường nối, đường phụ
AXIS_SO_TRIEU = "replace(format(datum.value / 1e6, ',.0f'), ',', '.')"   # trục chỉ ghi số, đơn vị ghi một lần ở tiêu đề ô
AXIS_SO_TY = "replace(format(datum.value / 1e9, ',.0f'), ',', '.')"

_CSS = """
[data-testid="stMainBlockContainer"]:has(.st-key-bi_doi_dau) {padding: 3.6rem 2rem 2rem; max-width: none;}
.st-key-bi_doi_dau h1 {font-size: 1.65rem; font-weight: 650; padding: 0.55rem 0 0;}
.st-key-bi_doi_ai_tiep [data-testid="stColumn"] > [data-testid="stVerticalBlock"],
.st-key-bi_doi_ai_tiep [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [class*="st-key-bi_khoi_"] {height: 100%;}

[class*="st-key-bi_khoi_"] {
    border-radius: 0.8rem; container-type: inline-size;
    box-shadow: 0 2px 10px rgba(128, 128, 128, 0.12); padding: 0.85rem 1rem;
}
[class*="st-key-bi_khoi_"] [data-testid="stVerticalBlock"] {gap: 0.5rem;}
[class*="st-key-bi_khoi_"] h3 {padding: 0; font-size: 0.95rem; font-weight: 600; letter-spacing: 0.01em;}
[class*="st-key-bi_khoi_"] h4 {padding: 0.1rem 0 0.25rem; font-size: 1.3rem; font-weight: 650; line-height: 1.35;}
[class*="st-key-bi_khoi_"] [data-testid="stMarkdownContainer"]:has(h3, h4) {margin-bottom: 0 !important;}
[class*="st-key-bi_khoi_"] li, [class*="st-key-bi_khoi_"] p {font-size: 0.9rem;}
[class*="st-key-bi_khoi_"] li {margin: 0.1rem 0;}
[class*="st-key-bi_khoi_"] [data-testid="stCaptionContainer"] p {font-size: 0.76rem;}

/* Không đặt nền thẻ: đường xu hướng của st.metric vẽ nền theme, không đổi được bằng tham số. Viền xám trong suốt hợp cả nền trắng và tối */
[class*="st-key-the_"] [data-testid="stMetric"] {
    border: 1px solid rgba(128, 128, 128, 0.28); border-radius: 0.7rem; padding: 0.6rem 0.75rem;
    box-shadow: inset 0 3px 0 #5B4BD6;
    display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr); align-items: end; column-gap: 0.5rem;
}
/* Bỏ lớp bọc phần chữ để nhãn, số, dòng phụ thành ô riêng trên lưới: nhãn trải hết thẻ, không xuống dòng giữa cụm từ */
[class*="st-key-the_"] [data-testid="stMetric"] > div:first-child {display: contents;}
[class*="st-key-the_"] [data-testid="stMetricLabel"] {grid-column: 1 / -1;}
[class*="st-key-the_"] [data-testid="stMetricValue"] {grid-column: 1; grid-row: 2;}
[class*="st-key-the_"] [data-testid="stMetricValue"] + div {grid-column: 1; grid-row: 3;}
[class*="st-key-the_"] [data-testid="stMetric"] > div:last-child {grid-column: 2; grid-row: 2 / span 2; min-width: 0; padding: 0;}
[class*="st-key-the_"] [data-testid="stMetricChart"] svg {width: 100%;}
[class*="st-key-the_"] [data-testid="stMetricLabel"] p {font-size: 0.78rem; opacity: 0.75;}
[class*="st-key-the_"] [data-testid="stMetricValue"] {font-size: clamp(1.1rem, 8.6cqi, 1.65rem) !important; font-weight: 650;}
[class*="st-key-the_"] [data-testid="stMetricValue"] * {font-size: inherit; font-weight: inherit;}
[class*="st-key-the_"] [data-testid="stMetricDelta"] p {font-size: 0.76rem;}
[class*="st-key-the_"] [data-testid="stMetricDeltaDescription"] p {font-size: 0.72rem;}

[class*="st-key-bi_khoi_"] [data-testid="stAlert"] [data-testid="stAlertContainer"] {
    padding: 0.35rem 0.7rem; border-radius: 0.4rem;
}
[class*="st-key-bi_khoi_"] [data-testid="stAlert"] p {font-size: 0.8rem;}

[class*="st-key-bi_khoi_"] [data-testid="stTable"] table {border: none;}
[class*="st-key-bi_khoi_"] [data-testid="stTable"] td, [class*="st-key-bi_khoi_"] [data-testid="stTable"] th {
    padding: 0.5rem 0.55rem; font-size: 0.82rem; border-left: none; border-right: none; border-color: rgba(128, 128, 128, 0.28);
}
[class*="st-key-bi_khoi_"] [data-testid="stTable"] th {font-weight: 500; background: transparent; opacity: 0.75;}

[class*="st-key-bi_khoi_"] [data-testid="stPageLink"] a {
    border: 1px solid rgba(91, 75, 214, 0.45); border-radius: 0.55rem; padding: 0.1rem 0.55rem;
}
[class*="st-key-bi_khoi_"] [data-testid="stPageLink"] a:hover {background: rgba(91, 75, 214, 0.08);}
[class*="st-key-bi_khoi_"] [data-testid="stPageLink"] a :is(p, span) {white-space: normal; overflow: visible; text-overflow: clip; font-size: 0.82rem;}
[class*="st-key-bi_khoi_"] [data-testid="stExpander"] details {border-color: rgba(128, 128, 128, 0.28);}
[class*="st-key-bi_khoi_"] [data-testid="stExpander"] summary p {font-size: 0.82rem;}
@container (max-width: 820px) {
    [class*="st-key-bi_khoi_"] [class*="st-key-the_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
        flex: 1 1 calc(50% - 1rem); min-width: calc(50% - 1rem); width: calc(50% - 1rem);
    }
}
/* Thẻ hẹp: đường xu hướng xuống dưới số, nếu không số tiền bị cắt. Container ở đây là chính thẻ (hang_the). */
@container (max-width: 205px) {
    [class*="st-key-the_"] [data-testid="stMetricValue"],
    [class*="st-key-the_"] [data-testid="stMetricValue"] + div,
    [class*="st-key-the_"] [data-testid="stMetric"] > div:last-child {grid-column: 1 / -1; grid-row: auto;}
}
"""


@dataclass(frozen=True)
class CauHoi:
    """Một câu hỏi kiểm tra tiếp và trang trả lời được câu đó."""
    cau: str                                     # câu hỏi, không chứa kết luận
    trang: str                                   # khóa trong roles.PAGES
    chi_tiet: str = ''                           # trang mở ra hiện gì, hiện ở tooltip của nút (để không tưởng còn giữ bộ lọc)
    params: dict = field(default_factory=dict)   # chỉ dùng tham số trang đọc bằng ui.common.url_choice


def nap_css() -> None:
    """Gọi một lần ở đầu trang dùng khung này. Rời trang thì CSS mất theo."""
    st.html(f'<style>{_CSS}</style>')


def khoi(so: str, ten: str, mo_ta: str = ''):
    """Ô có nền và viền, tiêu đề kèm số thứ tự. Dùng: `with khoi('01', 'Nhận định'): ...`. so='' thì không có số."""
    box = st.container(border=True, key=f'bi_khoi_{so or ten.lower().replace(" ", "_")}')
    box.subheader(f':violet-badge[{so}] {ten}' if so else ten, anchor=False)
    if mo_ta:
        box.caption(mo_ta)
    return box


def _nen_toi() -> bool:
    # Trình duyệt tự báo chế độ và app chạy lại khi đổi. AppTest không có trình duyệt nên là None, tính như nền sáng.
    return st.context.theme.type == 'dark'


def mau_chu() -> str:
    """Nhãn số trên biểu đồ: mark_text của Vega không tự theo màu chữ của theme (nền tối mà để mặc định thì ra chữ đen)."""
    return '#FAFAFA' if _nen_toi() else '#31333F'


def mau_nen() -> str:
    """Viền ngăn các phần chồng nhau trên biểu đồ: trùng màu nền thì trông như khe hở."""
    return '#0E1117' if _nen_toi() else '#FFFFFF'


def mau(chu: str, gia_tri) -> str:
    """Tô chữ theo dấu của số thật (không đoán từ chuỗi đã định dạng), dùng trong câu trả lời đầu trang."""
    return f':{"green" if gia_tri > 0 else "red" if gia_tri < 0 else "gray"}[{chu}]'


def hang_doi(key: str, ty_le: tuple = (1, 1), nguong_px: int = 760) -> list:
    """Hàng hai cột, xếp chồng khi hàng hẹp hơn nguong_px. st.columns chỉ xếp chồng khi màn hình dưới 640px, nên ở màn
    1024px có thanh bên hai cột sẽ quá hẹp. Đo theo bề rộng của hàng (container query), không theo màn hình."""
    k = f'.st-key-bi_doi_{key}'
    cot = '[data-testid="stColumn"]'
    # :not: chỉ cột của chính hàng này, không đụng hàng lồng bên trong (hàng trong đo theo ngưỡng của nó)
    st.html(f'<style>{k} {{container-type: inline-size;}}'
            f'@container (max-width: {nguong_px}px) {{{k} {cot}:not({k} {cot} {cot}) '
            '{flex: 1 1 100%; min-width: 100%; width: 100%;}}</style>')
    return st.container(key=f'bi_doi_{key}').columns(ty_le, gap='medium')


def dinh_dang_bieu_do(chart):
    """Nền trong suốt, lưới mờ, không viền, chữ trục theo theme: dữ liệu nổi hơn khung biểu đồ."""
    return (chart.properties(background='transparent')
            .configure_view(strokeWidth=0)
            .configure_axis(gridColor='rgba(128, 128, 128, 0.18)', domainColor='rgba(128, 128, 128, 0.45)', tickSize=0,
                            labelFontSize=11, labelPadding=6)
            .configure_legend(labelFontSize=12, symbolType='circle', symbolSize=90))


def bang_doi_chung(df: pd.DataFrame, cot_dau: str, dau: list) -> None:
    """Bảng số nhỏ: dòng đầu là dòng tổng, cột cot_dau tô màu theo dau (số thật, không đoán từ chuỗi đã định dạng).
    Dùng st.table vì cần tô theo ô và luôn hiện đủ dòng; bảng dài vẫn dùng st.dataframe."""
    # Chữ trong bảng cần tương phản cao hơn màu cột vì là chữ nhỏ, nên hai nền dùng hai cặp màu khác nhau
    chu_tang, chu_giam = ('#3DD6A8', '#FF8A8F') if _nen_toi() else ('#0B7A5C', '#C23A45')

    def to_mau(d: pd.DataFrame) -> pd.DataFrame:
        css = pd.DataFrame('', index=d.index, columns=d.columns)
        css.iloc[0, :] = 'background-color: rgba(91, 75, 214, 0.14); font-weight: 600'
        for i, s in enumerate(dau):
            if pd.notna(s) and s != 0:
                mau_o = chu_tang if s > 0 else chu_giam
                css.iloc[i, d.columns.get_loc(cot_dau)] += f'; color: {mau_o}; font-weight: 600'
        return css

    so = list(df.columns[1:])
    st.table(df.style.apply(to_mau, axis=None).set_properties(subset=so, **{'text-align': 'right'}), border='horizontal',
             hide_index=True)


def hoi_tiep(items: list[CauHoi]) -> None:
    """Các câu hỏi kèm nút sang trang trả lời được. Trang role không được xem thì bỏ cả câu: st.page_link tới trang ngoài
    navigation sẽ lỗi, và không nên gợi ý việc người xem không làm được."""
    role = roles.current_role()
    hien = [c for c in items if roles.allowed(role, c.trang)]
    if not hien:
        st.caption('Quyền hiện tại chưa mở trang phân tích liên quan.')
        return
    for i, c in enumerate(hien):
        path, ten = roles.PAGES[c.trang]
        trai, phai = hang_doi(f'tiep_{i}', (3, 2), 420)
        trai.markdown(c.cau)
        phai.page_link(path, label=ten, icon=':material/arrow_forward:', query_params=c.params or None, width='stretch',
                       help=c.chi_tiet or None)
