"""Lời kiểm thật, hiển thị local và xếp hạng mức R; không gọi mô hình hay cloud thật."""
import copy
import re
from decimal import Decimal
from types import SimpleNamespace

import pytest

from ai_explain import evidence, ly_do_chan, service, tools
from ai_explain.contracts import ToolResult
from tests.test_ai_chat import FakeProvider, _app, call, final, turn


# Mỗi dòng là một vị trí tạo lời kiểm trong bảng A1; các f-string đã được điền giá trị.
ERRORS = [
    pytest.param("câu văn tự viết số kèm đơn vị ['5 triệu']: số tiền / tỷ lệ phải đi qua claim", 'so_tu_viet', id='evidence.py:419'),
    pytest.param("câu văn có số tự viết ['999']: mọi số phải đi qua claim", 'so_tu_viet', id='evidence.py:424'),
    pytest.param('"còn lại/khác" cần dẫn đủ nhóm có ảnh hưởng lớn của cùng kết quả explain_forecast', 'phan_ra', id='evidence.py:760'),
    pytest.param('số nhóm và ngưỡng % phải trỏ vào derived.small_groups', 'phan_ra', id='evidence.py:763'),
    pytest.param('số nhóm phải trỏ vào derived.small_groups.n', 'phan_ra', id='evidence.py:766'),
    pytest.param('số nhóm phải trỏ vào derived.small_groups.n', 'phan_ra', id='evidence.py:768'),
    pytest.param('ngưỡng nhóm nhỏ phải trỏ vào derived.small_groups.threshold_pct', 'phan_ra', id='evidence.py:771'),
    pytest.param('"dưới" phải trỏ vào derived.small_groups.threshold_pct', 'phan_ra', id='evidence.py:773'),
    pytest.param('"tối đa/không quá/lớn nhất trong đó" phải trỏ vào derived.small_groups.max_abs_pct', 'phan_ra', id='evidence.py:775'),
    pytest.param('nhóm còn lại/khác thiếu kết quả explain_forecast cùng nguồn', 'phan_ra', id='evidence.py:779'),
    pytest.param('"còn lại/khác" cần dẫn đủ nhóm có ảnh hưởng lớn; nói "N nhóm có ảnh hưởng dưới ngưỡng mỗi nhóm"', 'phan_ra', id='evidence.py:781'),
    pytest.param('câu "Giai đoạn giảm mạnh nhất theo CAGR là {c1}" xếp hạng giai đoạn theo CAGR nhưng không có chỗ đặt trỏ vào derived.largest_decrease_cagr.phases (mỗi tiêu chí một chỗ đặt)', 'xep_hang', id='evidence.py:901'),
    pytest.param('câu hỏi nêu kỳ không hợp lệ (tháng 13/2023): trả status "needs_clarification" hỏi lại kỳ, không dùng số của kỳ khác (kể cả trong câu hỏi lại)', 'ky', id='evidence.py:1271'),
    pytest.param('câu "Năm 2018, ngành có R thấp nhất là {c1}" dẫn số dự báo của tháng 8/2023 nhưng không ghi rõ kỳ đó (câu hỏi về tháng 9/2023): số kỳ khác chỉ được nêu kèm đúng kỳ của nó, có năm, vd. "riêng tháng 8/2023, dự báo G là {c1}"; không gán cho kỳ được hỏi', 'ky', id='evidence.py:1502'),
    pytest.param('câu "Năm 2018, ngành có R thấp nhất là {c1}" ghi năm 2018 cho {c1} nhưng số đó là của năm 2019: ghi đúng kỳ của số, hoặc gọi tool đúng kỳ được hỏi; không gán số kỳ này cho kỳ khác', 'ky', id='evidence.py:1533'),
    pytest.param('"basket size" có thể là U hoặc AOV; hỏi lại người dùng, không chọn mã thay', 'dinh_nghia', id='evidence.py:1744'),
    pytest.param('không dùng get_metric_definition(G) để ánh xạ thay khái niệm/mã không được hỏi', 'dinh_nghia', id='evidence.py:1750'),
    pytest.param('chưa có định nghĩa cho khái niệm này; hỏi lại hoặc liệt kê mã gần nhất bằng đúng nhãn của mã đó, không dùng định nghĩa mã khác thay thế', 'dinh_nghia', id='evidence.py:1760'),
    pytest.param('catalog chưa có định nghĩa COGS; nói rõ không có định nghĩa, không dùng mã khác thay thế', 'dinh_nghia', id='evidence.py:1772'),
    pytest.param('câu hỏi định nghĩa G phải dẫn get_metric_definition(G); không dùng định nghĩa mã khác thay thế', 'dinh_nghia', id='evidence.py:1776'),
    pytest.param('AOV là R / N (= U × P), không phải P = R / Q', 'dinh_nghia', id='evidence.py:1780'),
    pytest.param('AOV chưa có quyết định chốt riêng trong catalog; không gọi là "đã chốt"', 'dinh_nghia', id='evidence.py:1782'),
    pytest.param('phân rã model không chứng minh nguyên nhân; chỉ nêu đóng góp trong model', 'phan_ra', id='evidence.py:1807'),
    pytest.param('"nhóm/yếu tố/biến/thành phần khác/còn lại" không có số cần đúng một kết quả explain_forecast; nói "{n} nhóm có ảnh hưởng dưới {threshold} mỗi nhóm"', 'phan_ra', id='evidence.py:1815'),
    pytest.param('"nhóm/yếu tố/biến/thành phần khác/còn lại" cần dẫn đủ nhóm có ảnh hưởng lớn; nói "{n} nhóm có ảnh hưởng dưới {threshold} mỗi nhóm"', 'phan_ra', id='evidence.py:1818'),
    pytest.param('số phân rã G bị gọi là phân rã COGS; không đổi chỉ tiêu của evidence', 'phan_ra', id='evidence.py:1826'),
    pytest.param('chỉ có phân rã G; câu hỏi COGS phải nói rõ chưa có phân rã COGS', 'phan_ra', id='evidence.py:1832'),
    pytest.param('số phân rã G trong câu hỏi COGS phải được gọi rõ là của G', 'phan_ra', id='evidence.py:1840'),
    pytest.param('câu hỏi nêu model khác nhưng phân rã chỉ thuộc model chính; không thay model', 'phan_ra', id='evidence.py:1852'),
    pytest.param('một ô đóng góp chỉ thuộc một nhóm biến; không gộp thành "các nhóm khác"', 'phan_ra', id='evidence.py:1860'),
    pytest.param('phân rã không chứng minh nhóm "rõ nhất"; nêu thứ hạng theo độ lớn đóng góp nếu cần', 'phan_ra', id='evidence.py:1862'),
    pytest.param('không gán cùng một chiều cho "các nhóm còn lại"; nêu chiều của từng nhóm', 'phan_ra', id='evidence.py:1864'),
    pytest.param('% của từng nhóm nhân với nhau, không cộng', 'phan_ra', id='evidence.py:1869'),
    pytest.param('phân rã model dẫn từ ngày / tháng khác kỳ được hỏi; gọi explain_forecast đúng kỳ', 'ky', id='evidence.py:1876'),
    pytest.param('câu hỏi vừa có kỳ ngoài vùng vừa có kỳ tham khảo trong vùng dự báo: status "ok" không hợp lệ; trả "no_data" để app ghi số tham khảo đúng kỳ', 'du_bao_pham_vi', id='evidence.py:1886'),
    pytest.param('câu hỏi hỏi "số đơn": chưa có dự báo chỉ tiêu này (dự báo chỉ có G và COGS toàn công ty); trả status "unsupported", có thể nêu số dự báo G thay thế nhưng ghi rõ đó không phải chỉ tiêu được hỏi', 'du_bao_pham_vi', id='evidence.py:1910'),
    pytest.param('câu hỏi hỏi số THỰC TẾ nhưng câu trả lời dẫn số DỰ BÁO: không đưa dự báo ra làm số thực tế; kỳ chưa có số thực tế thì trả status "no_data" (có thể nói thêm là có số dự báo)', 'du_bao_thuc_te', id='evidence.py:1915'),
    pytest.param('câu hỏi nêu kỳ tháng 9/2023 nhưng số dự báo lấy từ kỳ / grain khác (T1.rows[0].g_forecast): gọi get_forecast đúng kỳ được hỏi; kỳ ngoài 2023-01-01 → 2024-07-01 thì trả "no_data", không dùng số kỳ khác. Tổng cả vùng dự báo (derived.horizon_total) chỉ dùng khi câu hỏi gồm cả năm 2023 và 2024, và câu dẫn số gọi là "cả vùng dự báo", không gọi là tổng năm / tổng 2023–2024', 'ky', id='evidence.py:1928'),
    pytest.param('câu "Năm 2018, ngành có R thấp nhất là {c1}" dùng số của 8/2023 cho câu hỏi về khoảng quý 3/2023: chưa có tổng khoảng; nêu rõ đó là riêng tháng / ngày nào (vd. "riêng tháng 8/2023"), không gọi là tổng quý / nửa năm, hoặc trả "unsupported"', 'ky', id='evidence.py:1947'),
    pytest.param("câu hỏi nêu đích danh model ({'family': 'sarimax'}) nhưng số dự báo lấy từ ['lightgbm_tyle']: gọi get_forecast với model / cogs_method được hỏi; không có thì nói không có, không thay model", 'du_bao_pham_vi', id='evidence.py:1954'),
    pytest.param("câu hỏi về độ chính xác cần thước ['score'] (derived.lowest_score = điểm ngày kết hợp, thước chọn model; derived.lowest_mape_g_thang = MAPE G tháng, chỉ hiển thị) nhưng câu trả lời không dẫn", 'du_bao_pham_vi', id='evidence.py:1964'),
    pytest.param('claim sai dạng: 2018', 'so_tu_viet', id='evidence.py:1981'),
    pytest.param('c1: T1.rows[0].r là NULL (không tính được), không được trình bày như một số', 'so_tu_viet', id='evidence.py:1991'),
    pytest.param('c1: sign chỉ nhận "am"/"duong" cho giá trị số', 'chieu_sai', id='evidence.py:1996'),
    pytest.param('c1: nói am nhưng T1.rows[0].r thật là 12', 'chieu_sai', id='evidence.py:1998'),
    pytest.param('chỗ đặt {c1} không có claim hợp lệ', 'so_tu_viet', id='evidence.py:2003'),
    pytest.param('c1: T1.rows[0].trained_through là một ngày (ngày tháng), không phải số ngày; dùng ô đếm (n_days, n_folds) hoặc bỏ số đó', 'so_tu_viet', id='evidence.py:2024'),
    pytest.param('nhóm phân rã nói "chủ yếu/mạnh nhất/lớn nhất" hoặc từ xếp hạng tương đương: sai nhóm top-k; chiều âm là Khuyến mãi; không bỏ qua vị trí giữa', 'xep_hang', id='evidence.py:2066'),
    pytest.param('nhóm phân rã nói "tiếp theo": mảnh nối phải cùng kết quả explain_forecast với chuỗi trước', 'xep_hang', id='evidence.py:2072'),
    pytest.param('nhóm phân rã nói "tiếp theo": mảnh nối phải cùng chiều với chuỗi xếp hạng trước', 'xep_hang', id='evidence.py:2074'),
    pytest.param('nhóm phân rã nói "tiếp theo" phải là nhóm mới; ', 'xep_hang', id='evidence.py:2090'),
    pytest.param('nhóm phân rã nói "chủ yếu/mạnh nhất/lớn nhất" hoặc từ xếp hạng tương đương: sai nhóm top-k; chiều âm là Khuyến mãi; sau "Giá", nhóm kế tiếp chiều âm là "Khuyến mãi"; không bỏ qua vị trí giữa', 'xep_hang', id='evidence.py:2092'),
    pytest.param('phân rã L4 chỉ xếp hạng phía mạnh nhất theo rank_dir; bỏ chữ xếp hạng phía nhỏ (nhỏ nhất/ít nhất/nhẹ nhất/chậm nhất/yếu nhất)', 'xep_hang', id='evidence.py:2104'),
    pytest.param('câu "Ngành giảm ít nhất năm 2018 là {c1}" xếp hạng phía "nhỏ nhất / ít nhất" nhưng trong câu không có chỗ đặt xếp hạng phía đó. Nhóm (ngành, vùng, kênh): dùng derived.smallest_decrease.groups / smallest_increase.groups; tháng thấp nhất: trough_*. Giai đoạn, điểm đổi hướng: tool không xếp phía nhỏ, bỏ câu xếp hạng hoặc trả status "unsupported". KHÔNG đổi sang trả lời phía lớn nhất', 'xep_hang', id='evidence.py:2130'),
    pytest.param('câu "Năm 2018, ngành có R thấp nhất là {c1}" có ý xếp hạng ("nhiều nhất", "chủ yếu"...) nhưng trong câu không có chỗ đặt trỏ vào derived.largest_* hoặc top_*_driver (xếp hạng trên đủ tập). Đặt chỗ đặt xếp hạng ngay trong câu đó, hoặc mở câu bằng "Đây là…" ngay sau câu dẫn số của chính giai đoạn / nhóm ấy', 'xep_hang', id='evidence.py:2141'),
    pytest.param('câu "Ngành giảm ít nhất năm 2018 là {c1}" nói "nhỏ nhất / ít nhất" nhưng chỗ đặt là phía lớn nhất (largest_*, top_*_driver); nhóm thì dùng derived.smallest_decrease / smallest_increase.groups', 'xep_hang', id='evidence.py:2147'),
    pytest.param('câu "Ngành giảm nhiều nhất năm 2018 là {c1}" nói "nhiều nhất / mạnh nhất" nhưng chỗ đặt là phía nhỏ nhất (smallest_*); dùng derived.largest_*', 'xep_hang', id='evidence.py:2151'),
    pytest.param('câu "Ngành có R cao nhất năm 2018 là {c1}" nói "cao nhất" nhưng chỗ đặt trỏ vào phía thấp (peak/trough, max/min)', 'xep_hang', id='evidence.py:2167'),
    pytest.param('câu "Ngành tăng nhiều nhất năm 2018 là {c1}" nói "tăng" nhưng claim xếp hạng là chiều giảm', 'xep_hang', id='evidence.py:2174'),
    pytest.param('câu "Năm 2018, ngành có R thấp nhất là {c1}" gọi số dự báo là "thực tế": số dự báo phải nói rõ là dự báo', 'du_bao_thuc_te', id='evidence.py:2182'),
    pytest.param('câu "Năm 2018, ngành có R thấp nhất là {c1}" nói theo MAPE / sai số tháng nhưng dẫn derived.lowest_score (điểm ngày); dùng derived.lowest_mape_g_thang', 'du_bao_pham_vi', id='evidence.py:2185'),
    pytest.param('câu "Năm 2018, ngành có R thấp nhất là {c1}" nói theo điểm ngày nhưng dẫn derived.lowest_mape_g_thang; dùng derived.lowest_score', 'du_bao_pham_vi', id='evidence.py:2188'),
    pytest.param('câu "Năm 2018, ngành có R thấp nhất là {c1}" đặt số thực tế và số dự báo trong cùng một câu: tách thành hai câu riêng, mỗi câu một loại số; không cộng, trừ hay so hai loại số', 'du_bao_thuc_te', id='evidence.py:2199'),
    pytest.param('câu "Năm 2018, ngành có R thấp nhất là {c1}" so số dự báo với số thực tế: không tool nào tính chênh lệch này; nêu hai số thành hai câu riêng, không so', 'du_bao_thuc_te', id='evidence.py:2203'),
    pytest.param('câu "Năm 2018, ngành có R thấp nhất là {c1}" tự so sánh các số (cao hơn / thấp hơn...) mà không dẫn cột thay đổi do tool tính; app không kiểm được phép so sánh này', 'tu_so_sanh', id='evidence.py:2212'),
    pytest.param("câu văn viết thẳng tên nhóm ['Streetwear'] mà không gắn với claim nào đã dùng: tên nhóm phải là chỗ đặt (derived.largest_*.groups, rows[<nhóm>].dimension_value) hoặc đi cùng claim rows[<nhóm>]", 'nhom', id='evidence.py:2231'),
    pytest.param("câu văn nêu model ['sarimax'] mà không gắn với ô nào của model đó: tên model phải là chỗ đặt (derived.primary.label, rows[<ứng viên>].candidate_label) hoặc đi cùng số của chính model đó", 'du_bao_pham_vi', id='evidence.py:2237'),
    pytest.param('c1: vế câu gọi tên R nhưng T1.rows[0].g là số của G', 'phan_ra', id='evidence.py:2258'),
    pytest.param('c1: vế câu nói về U nhưng T1.rows[0].contrib_p là số của P', 'phan_ra', id='evidence.py:2262'),
    pytest.param('c1: chỗ đặt sau "góp" phải là một số (contrib_*), không phải tên thành phần', 'phan_ra', id='evidence.py:2264'),
    pytest.param('c1: câu nói "tăng" nhưng T1.rows[0].r = -12', 'chieu_sai', id='evidence.py:2271'),
    pytest.param('không kiểm được kỳ / loại số trong câu hỏi (ValueError); hỏi lại kỳ cụ thể', 'ky', id='service.py:335'),
    pytest.param('không kiểm được nguồn định nghĩa (ValueError); hỏi lại mã chỉ tiêu', 'dinh_nghia', id='service.py:342'),
    pytest.param('câu hỏi lọc nhóm [\'Streetwear\'] theo tháng / quý / ngày: chưa có số theo nhóm × kỳ đó, trả status "unsupported" (có thể nêu số thay thế nhưng phải ghi rõ đó không phải số được hỏi)', 'nhom', id='service.py:368'),
    pytest.param('câu hỏi nêu nhóm [\'Streetwear\'] nhưng câu trả lời không có số nào của nhóm đó: không được bỏ bộ lọc nhóm; gọi tool có nhóm đó hoặc trả status "unsupported"', 'nhom', id='service.py:371'),
    pytest.param('câu dự báo chưa có năm do người dùng chọn: hỏi lại năm bằng bốn chữ số, không dẫn số dự báo', 'nam_du_bao', id='service.py:599'),
    pytest.param('câu dự báo ngày/tháng chưa có năm do người dùng chọn: hỏi lại năm, không dẫn số dự báo', 'nam_du_bao', id='service.py:608'),
    pytest.param('câu trả lời dự báo nối tiếp phải ghi rõ năm người dùng đã nêu', 'nam_du_bao', id='service.py:613'),
    pytest.param('không kiểm được kỳ trong câu hỏi (ValueError); hỏi lại kỳ cụ thể, không dẫn số', 'ky', id='service.py:357'),
    pytest.param('c1: T1 không có trường r', 'so_tu_viet', id='evidence.py:1988'),
]


@pytest.mark.parametrize('message, expected', ERRORS)
def test_real_errors(message, expected):
    assert ly_do_chan.nhom_loi(message) == expected
    assert ly_do_chan.nhom_loi('c3: ' + message) == expected


FORBIDDEN = re.compile(r'[{}`_]|\b(?:derived|claim|tool|path|status|rank)\b', re.I)


@pytest.mark.parametrize('group', ly_do_chan.ERROR_MESSAGES)
def test_reader_messages_are_plain_vietnamese(group):
    messages = [ly_do_chan.ERROR_MESSAGES[group], ly_do_chan.GUIDANCE, ly_do_chan.RANK_GUIDANCE]
    assert all(not FORBIDDEN.search(message) for message in messages)


@pytest.mark.parametrize('status, message', ly_do_chan.STATUS_MESSAGES.items())
def test_status_messages_are_plain_vietnamese(status, message):
    shown, technical = ly_do_chan.status_message(status, 'T1.derived.n_groups = {c1}')
    assert technical and shown == message and not FORBIDDEN.search(shown)


def test_deduplicate_keep_order_and_unknown():
    errors = ['câu có ý xếp hạng'] * 5
    assert ly_do_chan.giai_thich(errors) == [ly_do_chan.ERROR_MESSAGES['xep_hang'], ly_do_chan.GUIDANCE, ly_do_chan.RANK_GUIDANCE]
    assert ly_do_chan.giai_thich(['lỗi mới', *errors, 'lỗi khác']) == [
        ly_do_chan.ERROR_MESSAGES['khac'], ly_do_chan.ERROR_MESSAGES['xep_hang'], ly_do_chan.GUIDANCE,
        ly_do_chan.RANK_GUIDANCE]


@pytest.mark.parametrize('text', ['Bạn muốn hỏi năm nào?', 'Chỉ hỗ trợ doanh thu, chưa hỗ trợ tồn kho.'])
def test_keep_plain_status_text(text):
    assert ly_do_chan.status_message('needs_clarification', text) == (text, False)


@pytest.mark.parametrize('text', ['n_groups=3', '`rpt_health` lỗi', 'derived.lowest_r', '{c1}',
                                  'status "unsupported"', 'tool thiếu path', 'RuntimeError',
                                  'HTTP 429', 'Cần làm rõ: metric', 'T1.rows[0].r', 'reporting.rpt' ])
def test_technical_status_text_is_hidden(text):
    shown, technical = ly_do_chan.status_message('query_error', text)
    assert technical and shown == ly_do_chan.STATUS_MESSAGES['query_error']


def test_rank_error_on_page(monkeypatch):
    wrong = final(answer='Ngành có R thấp nhất năm 2018 là {c1}.',
                  claims=[{'id': 'c1', 'path': 'T1.derived.largest_decrease.groups'}])
    fake = FakeProvider(call('get_segment_contribution', metric='R', dimension='category', year=2018), wrong, wrong)
    at = _app(monkeypatch, fake)
    at.chat_input[0].set_value('Mặt hàng nào có doanh thu thấp năm 2018 vậy').run()
    assert not at.exception
    assert at.session_state.ai_turns[0].status == 'answer_validation_failed'
    reader = next(x for x in at.expander if x.label == 'Vì sao câu diễn giải bị chặn')
    technical = next(x for x in at.expander if x.label == 'Chi tiết kỹ thuật (cho người phát triển)')
    assert any('bảng xếp hạng' in x.value for x in reader.markdown)
    assert all(not FORBIDDEN.search(x.value) for x in reader.markdown)
    assert any('derived.' in x.value for x in technical.code)
    assert technical.proto.expanded is False
    assert all(x.label != technical.label for x in reader.expander)
    assert all(x.label != reader.label for x in technical.expander)


def test_query_error_on_page(monkeypatch):
    monkeypatch.setattr(tools, 'run', lambda *a, **kw: ToolResult('query_error', 'Tập nhóm không đủ, n_groups=3'))
    at = _app(monkeypatch, FakeProvider(call('get_segment_contribution', metric='R', dimension='category', year=2018),
                                             final(status='no_data', answer='Không đọc được số liệu: n_groups không đủ.')))
    at.chat_input[0].set_value('Mặt hàng nào có doanh thu thấp năm 2018 vậy').run()
    assert not at.exception
    assert any(ly_do_chan.STATUS_MESSAGES['query_error'] in x.value for x in at.warning)
    assert all('n_groups' not in x.value for x in at.warning)
    technical = next(x for x in at.expander if x.label == 'Chi tiết kỹ thuật (cho người phát triển)')
    assert any('n_groups' in x.value for x in technical.code)


@pytest.mark.parametrize('dim', ['category', 'region', 'acquisition_channel'])
def test_segment_extremes_from_full_rows(dim):
    result = tools.run({'tool': 'get_segment_contribution', 'arguments': {'metric': 'R', 'dimension': dim, 'year': 2018}}, 'duckdb')
    assert result.ok, result.message
    for key, pick in [('highest_r', max), ('lowest_r', min)]:
        value = pick(row['r'] for row in result.rows)
        expected = [row['dimension_value'] for row in result.rows if row['r'] == value]
        assert result.derived[key] == dict(groups=expected, r=value, tie=len(expected) > 1)
    assert 'Xếp theo mức R của năm trên đủ tập nhóm (highest_r / lowest_r)' in result.evidence.method


@pytest.mark.parametrize('values', [(5, 5, 1), (5, 1, 1), (5, 5, 5)])
def test_segment_ties_and_selected_group(values):
    # Gọi handler thật với phiên đọc giả: xếp hạng vẫn dùng đủ tập dù chỉ chọn xem một nhóm.
    rows = [dict(dimension_value=name, r=Decimal(value), delta_r=-1, n_groups=3, n_groups_down=3, n_groups_up=0, delta_r_is_small=False)
            for name, value in zip(['A', 'B', 'C'], values)]
    reader = SimpleNamespace(fetch=lambda *a: SimpleNamespace(records=lambda: rows),
                             coverage_years=lambda: (2012, 2022), build={'growth_start_year': 2014},
                             evidence=lambda **kw: kw)
    result = tools._segment(reader, dict(metric='R', dimension='category', year=2018, group='C'))
    assert result.ok
    for key, pick in [('highest_r', max), ('lowest_r', min)]:
        value = Decimal(pick(values))
        groups = [row['dimension_value'] for row in rows if row['r'] == value]
        assert result.derived[key] == dict(groups=groups, r=value, tie=len(groups) > 1)


def test_incomplete_groups_cannot_rank():
    rows = [dict(dimension_value='A', r=1, delta_r=-1, n_groups=2)]
    reader = SimpleNamespace(fetch=lambda *a: SimpleNamespace(records=lambda: rows),
                             coverage_years=lambda: (2012, 2022), build={'growth_start_year': 2014})
    result = tools._segment(reader, dict(metric='R', dimension='category', year=2018))
    assert result.status == 'query_error' and not result.derived


@pytest.mark.parametrize('word, key, expected', [
    ('thấp nhất', 'lowest_r', True), ('cao nhất', 'highest_r', True),
    ('thấp nhất', 'highest_r', False), ('cao nhất', 'lowest_r', False),
    ('giảm nhiều nhất', 'lowest_r', False), ('tăng nhiều nhất', 'highest_r', False),
    ('giảm ít nhất', 'lowest_r', False), ('tăng ít nhất', 'highest_r', False),
    ('thấp nhất', 'largest_decrease', False), ('cao nhất', 'largest_increase', False),
])
def test_segment_rank_claim(word, key, expected):
    result = tools.run({'tool': 'get_segment_contribution', 'arguments': {'metric': 'R', 'dimension': 'category', 'year': 2018}}, 'duckdb')
    assert result.ok
    # Kiểm đúng loại xếp hạng cả khi một phía ΔR không có trong dữ liệu năm này.
    result = copy.deepcopy(result)
    result.derived.setdefault('largest_increase', None)
    if result.derived[key] is None:
        result.derived[key] = dict(groups=['A'], delta_r=1, tie=False)
    checked = evidence.validate(f'Ngành có R {word} năm 2018 là {{c1}}.',
                                [{'id': 'c1', 'path': f'T1.derived.{key}.groups'}], {'T1': result})
    assert checked.ok is expected, checked.errors


def test_segment_rank_end_to_end():
    answer = final(answer='Ngành có R thấp nhất năm 2018 là {c1}, R là {c2}.', claims=[
        {'id': 'c1', 'path': 'T1.derived.lowest_r.groups'}, {'id': 'c2', 'path': 'T1.derived.lowest_r.r'}])
    result = turn(FakeProvider(call('get_segment_contribution', metric='R', dimension='category', year=2018), answer),
                  q='Mặt hàng nào có doanh thu thấp năm 2018 vậy')
    assert result.status == 'ok', result.validation_errors
    assert result.results['T1'].derived['lowest_r']['groups']


@pytest.mark.parametrize('word, keys', [
    ('thấp nhất', ['lowest_r', 'highest_r']),
    ('cao nhất', ['highest_r', 'lowest_r']),
    ('tăng / giảm nhiều nhất', ['lowest_r']),
])
def test_segment_rank_cannot_mix_sides_or_change_directions(word, keys):
    result = tools.run({'tool': 'get_segment_contribution', 'arguments': {'metric': 'R', 'dimension': 'category', 'year': 2018}}, 'duckdb')
    assert result.ok
    claims = [{'id': f'c{i}', 'path': f'T1.derived.{key}.groups'} for i, key in enumerate(keys, 1)]
    placeholders = ' và '.join('{' + item['id'] + '}' for item in claims)
    checked = evidence.validate(f'Ngành có R {word} năm 2018 là {placeholders}.', claims, {'T1': result})
    assert not checked.ok


def test_lowest_r_on_page(monkeypatch):
    answer = final(answer='Ngành có R thấp nhất năm 2018 là {c1}, R là {c2}.', claims=[
        {'id': 'c1', 'path': 'T1.derived.lowest_r.groups'}, {'id': 'c2', 'path': 'T1.derived.lowest_r.r'}])
    fake = FakeProvider(call('get_segment_contribution', metric='R', dimension='category', year=2018), answer)
    at = _app(monkeypatch, fake)
    at.chat_input[0].set_value('Mặt hàng nào có doanh thu thấp năm 2018 vậy').run()
    assert not at.exception
    result = at.session_state.ai_turns[0]
    assert result.status == 'ok', result.validation_errors
    assert not any(x.label == 'Vì sao câu diễn giải bị chặn' for x in at.expander)
    assert any('Ngành có R thấp nhất năm 2018' in x.value for x in at.markdown)
    assert all(group in result.answer_md for group in result.results['T1'].derived['lowest_r']['groups'])


@pytest.mark.parametrize('message, extra', [
    ('câu "Ngành R thấp nhất năm 2018 là {c1}" có ý xếp hạng nhưng không dẫn derived.lowest_r', False),
    ('xếp hạng mức R của nhóm dẫn sai phía cao / thấp', False),
    ('câu "Ngành giảm nhiều nhất năm 2018 là {c1}" có ý xếp hạng nhưng không dẫn derived.largest_decrease', True),
])
def test_rank_guidance_only_for_change_ranking(message, extra):
    messages = ly_do_chan.giai_thich([message] * 5)
    assert (ly_do_chan.RANK_GUIDANCE in messages) is extra
    assert messages.count(ly_do_chan.ERROR_MESSAGES['xep_hang']) == 1


@pytest.mark.parametrize('answer, year, key, expected', [
    ('Ngành ảnh hưởng lớn nhất tới ΔR năm 2019 là {c1}.', 2019, 'largest_decrease', True),
    ('Ngành có đóng góp lớn nhất năm 2019 là {c1}.', 2019, 'largest_decrease', True),
    ('Ngành có R thấp nhất năm 2018 là {c1}.', 2018, 'largest_decrease', False),
    ('Ngành đóng góp lớn nhất năm 2019 là {c1}.', 2019, 'lowest_r', False),
])
def test_segment_change_context_regression(answer, year, key, expected):
    result = tools.run({'tool': 'get_segment_contribution',
                        'arguments': {'metric': 'R', 'dimension': 'category', 'year': year}}, 'duckdb')
    assert result.ok, result.message
    assert result.derived[key] is not None
    checked = evidence.validate(answer, [{'id': 'c1', 'path': f'T1.derived.{key}.groups'}], {'T1': result})
    assert checked.ok is expected, checked.errors


@pytest.mark.parametrize('context', [
    'ΔR', 'đóng góp', 'ảnh hưởng', 'tác động', 'thay đổi', 'biến động', 'chênh lệch', 'so với năm trước',
])
@pytest.mark.parametrize('word, key, expected', [
    ('lớn nhất', 'largest_decrease', True), ('thấp nhất', 'lowest_r', False),
])
def test_segment_change_context_terms(context, word, key, expected):
    result = tools.run({'tool': 'get_segment_contribution',
                        'arguments': {'metric': 'R', 'dimension': 'category', 'year': 2019}}, 'duckdb')
    assert result.ok, result.message
    answer = f'Ngành có mức {word} ({context}) năm 2019 là {{c1}}.'
    checked = evidence.validate(answer, [{'id': 'c1', 'path': f'T1.derived.{key}.groups'}], {'T1': result})
    assert checked.ok is expected, checked.errors
