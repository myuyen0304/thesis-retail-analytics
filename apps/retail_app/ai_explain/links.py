"""B6 (L2): nút mở trang phân tích kèm đúng bộ lọc của tool đã chạy trong lượt (docs/kien_truc_pipeline_tong.md B6).

App dựng link từ tham số của lời gọi tool đã `ok`, không lấy từ câu văn của mô hình, nên không thêm gì vào prompt.
Link chỉ có khi trang giữ được mọi bộ lọc của lời gọi: kỳ / chiều / năm đi qua query params (trang đọc bằng
ui.common.url_choice); phần hẹp hơn mà trang vẫn hiện đủ (một tháng trong bảng tháng của năm, một nhóm trong bảng các
nhóm, một ngày trong kỳ dự báo) thì nêu trong nhãn. Trang không biểu diễn được (G ở trang chỉ có R, chuỗi nhiều năm,
model không phải model chính, giai đoạn chưa mở) thì không có link, vì link mất bộ lọc dễ làm người xem đọc nhầm số.
"""
from dataclasses import dataclass, field

# trang → (đường dẫn trong app.py, tên hiện trên nút); cùng tên với st.Page của app.py
PAGES = {
    'ps1': ('views/ps1_do_dung.py', 'PS1: Đo đúng doanh thu'),
    'ps2': ('views/ps2_xu_huong.py', 'PS2: Xu hướng'),
    'ps3': ('views/ps3_nhip_lich.py', 'PS3: Nhịp lịch'),
    'ps4': ('views/ps4_don_mon_gia.py', 'PS4: Số đơn, số món, giá'),
    'ps5': ('views/ps5_nhom.py', 'PS5: Nhóm kéo lên/xuống'),
    'du_bao': ('views/du_bao.py', 'Dự báo'),
}
DIM_VI = {'category': 'ngành hàng', 'region': 'khu vực', 'acquisition_channel': 'kênh thu hút khách'}


@dataclass(frozen=True)
class PageLink:
    page: str                      # đường dẫn trang, vd. views/ps5_nhom.py
    label: str                     # chữ trên nút: tên trang · bộ lọc đã mở sẵn
    query_params: dict = field(default_factory=dict)
    ref: str = ''                  # kết quả tool sinh ra link (T1, T2...)


def _link(key: str, ref: str, params: dict, detail: str) -> PageLink:
    page, title = PAGES[key]
    return PageLink(page, f'{title} · {detail}' if detail else title, {k: str(v) for k, v in params.items()}, ref)


def _one(ref: str, tool: str, a: dict, res) -> PageLink | None:
    """Một lời gọi → một link, hoặc None khi trang không giữ được bộ lọc."""
    year = a.get('year')
    if tool == 'get_revenue_summary':
        if a.get('to_year') not in (None, year):        # chuỗi nhiều năm: PS1 chỉ chọn một kỳ
            return None
        return _link('ps1', ref, {'ky': year}, f'năm {year}')
    if tool == 'get_revenue_monthly':
        return _link('ps1', ref, {'ky': year}, f'năm {year}, bảng theo tháng có tháng {int(a["month"]):02d}')
    if tool == 'get_revenue_gap':
        if a.get('period') == '2013-2022':
            return _link('ps1', ref, {'ky': '2013-2022'}, 'kỳ 2013–2022')
        return _link('ps1', ref, {'ky': year}, f'năm {year}')
    if tool == 'get_revenue_drivers':                     # PS4 chỉ có R và kỳ năm
        if a.get('metric', 'R') != 'R' or a.get('period_type', 'year') != 'year':
            return None
        return _link('ps4', ref, {'ky': year}, f'năm {year} so với {year - 1}')
    if tool == 'get_segment_contribution':                # PS5 chỉ có R
        if a.get('metric', 'R') != 'R':
            return None
        dim = a['dimension']
        detail = f'{DIM_VI.get(dim, dim)}, năm {year}'
        if a.get('group'):
            detail += f' (bảng các nhóm có {a["group"]})'
        return _link('ps5', ref, {'chieu': dim, 'nam': year}, detail)
    if tool == 'get_revenue_trend':                       # trang không có bộ lọc; hiện cả giai đoạn và điểm đổi hướng
        return _link('ps2', ref, {}, '')
    if tool == 'get_calendar_pattern':                    # trang hiện cả mùa vụ, cuối tháng, tháng 8
        return _link('ps3', ref, {}, '')
    if tool == 'get_forecast':                            # trang chỉ vẽ model chính, cả kỳ dự báo
        if not (res.derived or {}).get('selected_is_primary'):
            return None
        return _link('du_bao', ref, {}, 'model chính, cả kỳ dự báo')
    if tool == 'get_forecast_backtest':                   # bảng so sánh trên trang có mọi ứng viên
        return _link('du_bao', ref, {}, 'bảng so sánh các model')
    return None                                           # get_metric_definition: không có trang tương ứng


def page_links(calls, results) -> list[PageLink]:
    """Link của các tool `ok` trong lượt, theo thứ tự gọi; trùng (trang, bộ lọc) thì giữ link đầu."""
    out, seen = [], set()
    for ref, tool, args in calls:
        res = results.get(ref)
        if res is None or not res.ok:
            continue
        link = _one(ref, tool, dict(args or {}), res)
        key = link and (link.page, tuple(sorted(link.query_params.items())))
        if link and key not in seen:
            seen.add(key)
            out.append(link)
    return out
