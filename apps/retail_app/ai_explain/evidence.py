"""Kiểm câu trả lời của LLM trước khi hiện (docs/ai_explain_plan.md §5 "Câu trả lời", §11.2; case E21).

Hợp đồng: model KHÔNG viết số. Mỗi con số là một claim trỏ vào kết quả tool của chính lượt đó:
    {"id": "c1", "path": "T1.rows[0].delta_r", "sign": "am"}
    {"id": "c2", "path": "T2.derived.largest_decrease.groups"}
    {"id": "c3", "path": "T2.rows[Streetwear].contribution_to_delta"}
và câu văn chỉ chứa chỗ đặt `{c1}`. App tra giá trị thật rồi định dạng; model không tự điền số.

Chỉ claim có chỗ đặt `{cX}` trong câu văn mới được kiểm và tính; claim khai báo mà không dùng bị bỏ qua.
Bị chặn (answer_validation_failed) khi:
- tham chiếu kết quả không có / không `ok`, dòng hoặc trường không có, giá trị NULL, hoặc trỏ vào cả một khối
  (dict / danh sách không phải giá trị đơn) thay vì một ô;
- câu văn có chữ số ngoài năm của bằng chứng, số trong thông báo của app và mốc ngày/tháng người dùng tự gõ
  (số bịa, số tự tính). Số đứng trước đơn vị (tỷ, triệu, VND, %...) luôn bị chặn, kể cả khi trùng một năm;
- `sign` sai dấu thật, hoặc chữ "tăng"/"giảm" ngay trước số ngược dấu thật;
- vế câu gọi tên R mà số là G, hoặc ngược lại;
- câu có từ xếp hạng ("nhiều nhất", "chủ yếu"...) mà CHÍNH câu đó không có chỗ đặt trỏ vào phần xếp hạng tính trên
  đủ tập (`derived.largest_*`, `top_*_driver`), hoặc hướng xếp hạng ngược chữ tăng/giảm của câu. Hai ngoại lệ do APP
  tự đối chiếu với kho: câu gọi tên thẳng N/U/P, và câu nối "Đây (cũng) là … mạnh nhất" trỏ về giai đoạn / nhóm / điểm
  mà câu ngay trước đã dẫn số (2026-10-09);
- câu xếp hạng giai đoạn nêu tiêu chí (theo CAGR / bằng tiền) mà thiếu chỗ đặt của tiêu chí đó; câu "nhỏ nhất /
  ít nhất" dẫn derived.largest_* (phía ngược) và câu "nhiều nhất" dẫn derived.smallest_*;
- tên nhóm (ngành hàng, khu vực, kênh) viết thẳng mà không gắn với claim đã dùng (rows[<nhóm>] hoặc danh sách nhóm
  của claim xếp hạng): giá trị đúng ở một ô không chứng minh câu văn nói đúng nhóm;
- câu so sánh ("cao hơn", "thấp hơn"...) không dẫn số thay đổi do tool tính;
- chỗ đặt `{cX}` không có claim tương ứng.
Mỗi số hiện kèm nhãn do app dựng từ chính ô dữ liệu (chỉ tiêu, nhóm, năm), trừ khi vế câu đã ghi đúng các thông tin
đó. Không kiểm được mọi nhận định bằng lời; phần đó thuộc live eval (§13).
"""
import re
from dataclasses import dataclass, field
from datetime import date as _date
from numbers import Number

from ai_explain import metric_catalog as cat
from ui.fmt import num, pct

MONEY = {'r', 'g', 'r_prior_year', 'delta_r', 'r_start', 'r_end', 'contrib_n', 'contrib_u', 'contrib_p', 'r_total',
         'additive_check',
         # AI3: PS1 G → R, tháng; PS2 điểm đổi hướng
         'cancelled_gross', 'returned_gross', 'undelivered_gross', 'delivered_discount', 'gap_g_minus_r', 'amount',
         'r_same_month_prior_year', 'r_12m_before', 'r_12m_after'}
PRICE = {'p_start', 'p_end'}
# B3 (2026-10-15): số dự báo / sai số backtest (tiền), đọc từ rpt_forecast_* (ai_explain/tools.py _forecast*)
MONEY |= {'g_forecast', 'cogs_forecast', 'lower_g', 'upper_g', 'score', 'mae_g', 'mae_cogs', 'rmse_g'}
FORECAST_FIELDS = {'g_forecast', 'cogs_forecast', 'lower_g', 'upper_g', 'cogs_ratio'}
PCT100 = {'mape_g_thang', 'typical_month_error'}      # kho lưu đã nhân 100 (11,4 = 11,4%), không nhân thêm
RATE = {'coverage_80', 'improvement_vs_floor', 'yoy_rate', 'share', 'contribution_to_delta', 'r_change_rate', 'n_change_rate', 'u_change_rate', 'p_change_rate',
        'capture_rate', 'share_cancelled', 'share_returned', 'share_undelivered', 'share_discount',
        'total_change_rate', 'cagr', 'magnitude', 'august_odd_vs_even', 'loo_min_odd_vs_even', 'loo_max_odd_vs_even',
        'eom_share', 'eom_expected_share'}
PP = {'share_shift_pp'}
PP_FRAC = {'eom_excess', 'loo_min_eom_excess', 'loo_max_eom_excess'}     # hiệu hai tỷ lệ (0,0718) → "7,2 điểm %"
COUNT = {'n_start', 'n_end', 'n_groups', 'n_groups_up', 'n_groups_down', 'n_days', 'n_days_in_period', 'n_folds',
         'n_candidates', 'n_pass_floor',
         'n_years', 'n_years_with_pattern', 'n_odd_years', 'n_even_years', 'n_phases', 'n_phases_eom_positive',
         'n_phases_same_peak', 'n_phases_same_trough'}
UNITS = {'u_start', 'u_end'}
INDEX = {'cogs_ratio', 'tai_tao_bien_do', 'month_index', 'august_index_odd', 'august_index_even', 'max_index_odd', 'min_index_even', 'peak_index',
         'trough_index', 'season_peak_trough_ratio', 'loo_min_ratio', 'loo_max_ratio'}
MONTHS = {'month', 'peak_month', 'trough_month', 'peak_months', 'trough_months'}
YEARS = {'year', 'start_year', 'end_year', 'turning_year', 'first_year', 'last_year'}
# khóa chọn dòng theo tên trong path rows[<tên>]: nhóm PS5, giai đoạn A–D, năm của điểm đổi hướng
ROW_KEYS = ('dimension_value', 'phase_code', 'turning_year', 'candidate', 'period', 'feature_group')
# Số THAY ĐỔI: dương = tăng, âm = giảm. contribution_to_delta / share là TỶ LỆ, không thuộc nhóm này:
# contribution_to_delta dương = cùng chiều ΔR toàn công ty (Streetwear 2019: +83,6% của mức GIẢM).
SIGNED = {'delta_r', 'contrib_n', 'contrib_u', 'contrib_p', 'yoy_rate', 'share_shift_pp', 'r_change_rate',
          'n_change_rate', 'u_change_rate', 'p_change_rate',
          'total_change_rate', 'cagr', 'magnitude', 'august_odd_vs_even', 'loo_min_odd_vs_even', 'loo_max_odd_vs_even',
           'eom_excess', 'loo_min_eom_excess', 'loo_max_eom_excess', 'contribution_log', 'pct_vs_base'}
# Câu so sánh ("thấp hơn"...) được nói khi dẫn một cột chênh lệch / kết luận so sánh do tool tính
COMPARED = SIGNED | {'gap_g_minus_r', 'odd_even_order', 'improvement_vs_floor',   # B3: mức thấp hơn mốc sàn, tool tính
                     'beats_floor_all_folds', 'n_pass_floor'}                        # "vượt mốc sàn ở cả 3 fold", tool tính
# Thước backtest: câu "{a} thấp hơn {b}" được nói khi hai chỗ đặt cùng thước nằm hai bên chữ so sánh và app kiểm được chiều
BACKTEST_COMPARABLE = {'score', 'mae_g', 'mae_cogs', 'rmse_g', 'mape_g_thang'}
_LOWER_WORDS, _HIGHER_WORDS = ('thấp hơn', 'nhỏ hơn', 'ít hơn'), ('cao hơn', 'lớn hơn', 'nhiều hơn')
# Ô xếp hạng mức (tháng cao nhất, chỉ số tháng 8 cao nhất của năm lẻ...): +1 = phía cao, −1 = phía thấp
LEVEL_RANK = {'peak_month': 1, 'peak_index': 1, 'peak_months': 1, 'max_index_odd': 1, 'n_phases_same_peak': 1,
              'trough_month': -1, 'trough_index': -1, 'trough_months': -1, 'min_index_even': -1,
              'n_phases_same_trough': -1,
              'loo_min_ratio': -1, 'loo_min_odd_vs_even': -1, 'loo_min_eom_excess': -1,
              'loo_max_ratio': 1, 'loo_max_odd_vs_even': 1, 'loo_max_eom_excess': 1}
# Số tự nó đã là phép xếp hạng hai đầu trên đủ tập (tháng cao nhất ÷ thấp nhất): câu "giữa tháng cao nhất và thấp nhất
# là {c}" hợp lệ khi dẫn ô này
RANK_BOTH = {'season_peak_trough_ratio'}
HIGH_WORDS, LOW_WORDS = ('cao nhất', 'lớn nhất', 'nhiều nhất', 'đứng đầu', 'dẫn đầu'), ('thấp nhất', 'nhỏ nhất', 'ít nhất')
DRIVER_LABEL = {'n': 'số đơn (N)', 'u': 'số món mỗi đơn (U)', 'p': 'giá mỗi món (P)'}
# Nhãn chỉ tiêu của từng cột, để renderer tự ghi số đó là gì (không tin nhãn model tự viết).
FIELD_LABEL = {'r': 'R', 'g': 'G', 'r_prior_year': 'R', 'r_start': 'R', 'r_end': 'R', 'r_total': 'R toàn công ty',
               'delta_r': 'ΔR', 'contrib_n': 'phần góp của N', 'contrib_u': 'phần góp của U', 'contrib_p': 'phần góp của P',
               'yoy_rate': '% đổi R', 'r_change_rate': '% đổi R', 'n_change_rate': '% đổi N', 'u_change_rate': '% đổi U',
               'p_change_rate': '% đổi P', 'share': 'tỷ trọng R', 'share_shift_pp': 'đổi tỷ trọng R',
               'contribution_to_delta': '% đóng góp vào ΔR', 'n_start': 'số đơn', 'n_end': 'số đơn',
               'u_start': 'món mỗi đơn', 'u_end': 'món mỗi đơn', 'p_start': 'giá mỗi món', 'p_end': 'giá mỗi món',
               # AI3
               'cancelled_gross': 'tiền hàng đơn hủy', 'returned_gross': 'tiền hàng đơn trả',
               'undelivered_gross': 'tiền hàng đơn chưa giao', 'delivered_discount': 'chiết khấu đơn đã giao',
               'gap_g_minus_r': 'G − R', 'capture_rate': 'R/G', 'share_cancelled': 'đơn hủy / G',
               'share_returned': 'đơn trả / G', 'share_undelivered': 'đơn chưa giao / G',
               'share_discount': 'chiết khấu / G', 'r_same_month_prior_year': 'R', 'month_index': 'chỉ số tháng',
               'total_change_rate': '% đổi R cả giai đoạn', 'cagr': 'CAGR', 'r_12m_before': 'R 12 tháng trước điểm',
               'r_12m_after': 'R 12 tháng sau điểm', 'magnitude': 'độ lớn đổi hướng',
               'august_odd_vs_even': 'chênh tháng 8 năm lẻ / năm chẵn', 'august_index_odd': 'chỉ số tháng 8 TB năm lẻ',
               'august_index_even': 'chỉ số tháng 8 TB năm chẵn', 'max_index_odd': 'chỉ số tháng 8 cao nhất của năm lẻ',
               'min_index_even': 'chỉ số tháng 8 thấp nhất của năm chẵn', 'loo_min_odd_vs_even': 'thấp nhất khi bỏ từng năm',
               'loo_max_odd_vs_even': 'cao nhất khi bỏ từng năm', 'loo_min_ratio': 'thấp nhất khi bỏ từng năm',
               'loo_max_ratio': 'cao nhất khi bỏ từng năm', 'loo_min_eom_excess': 'thấp nhất khi bỏ từng năm',
               'loo_max_eom_excess': 'cao nhất khi bỏ từng năm', 'season_peak_trough_ratio': 'chênh mùa cao/thấp',
               'peak_index': 'chỉ số tháng cao nhất', 'trough_index': 'chỉ số tháng thấp nhất',
               'eom_share': 'tỷ trọng R từ ngày 26', 'eom_expected_share': 'tỷ trọng nếu rải đều',
               'eom_excess': 'mức dồn cuối tháng', 'n_years_with_pattern': 'số năm có nhịp',
               'n_phases_same_peak': 'số giai đoạn cùng tháng cao nhất',
               'n_phases_same_trough': 'số giai đoạn cùng tháng thấp nhất',
               # B3: dự báo (nhãn "dự báo" do APP gắn, không tin chữ model viết)
               'g_forecast': 'dự báo G', 'cogs_forecast': 'dự báo COGS', 'lower_g': 'cận dưới khoảng 80% dự báo G',
               'upper_g': 'cận trên khoảng 80% dự báo G', 'cogs_ratio': 'COGS/G dự báo',
               'typical_month_error': 'sai số tháng điển hình, backtest 2020–2022',
               'score': 'điểm ngày kết hợp, backtest 2020–2022', 'mae_g': 'MAE G, backtest', 'mae_cogs': 'MAE COGS, backtest',
               'rmse_g': 'RMSE G, backtest', 'r2_g': 'R² G, backtest', 'mape_g_thang': 'MAPE G tháng, backtest 2020–2022',
               'coverage_80': 'tỷ lệ ngày trong khoảng 80%, backtest', 'tai_tao_bien_do': 'tỷ lệ tái tạo biên độ tháng 8/2021',
                'improvement_vs_floor': 'điểm thấp hơn mốc seasonal naive 2 năm',
                'contribution_log': 'đóng góp vào log(G) dự báo', 'multiplier': 'hệ số nhân của nhóm biến',
                'pct_vs_base': '% so với mức nền',
                'base_log': 'mức nền log(G)', 'forecast_log': 'log(G) dự báo'}
FEATURE_GROUP_LABEL = {'mua_vu': 'mùa vụ', 'dau_cuoi_thang': 'đầu/cuối tháng',
                       'che_do_sau_2018': 'chế độ sau 2018', 'nam_chan_le': 'năm chẵn/lẻ',
                       'promo_fall_launch': 'lịch Fall Launch', 'promo_mid_year_sale': 'lịch Mid Year Sale',
                       'promo_rural_special': 'lịch Rural Special', 'promo_spring_sale': 'lịch Spring Sale',
                       'promo_urban_blowout': 'lịch Urban Blowout', 'promo_year_end_sale': 'lịch Year End Sale'}
METRIC_FAMILY = {f: 'R' for f in ('r', 'r_prior_year', 'r_start', 'r_end', 'r_total', 'delta_r', 'contrib_n', 'contrib_u',
                                   'contrib_p', 'yoy_rate', 'r_change_rate', 'share', 'share_shift_pp',
                                   'contribution_to_delta', 'r_same_month_prior_year', 'r_12m_before', 'r_12m_after',
                                   'total_change_rate', 'cagr', 'magnitude')} | {'g': 'G'} | {
    f: 'G' for f in ('g_forecast', 'lower_g', 'upper_g', 'contribution_log', 'multiplier', 'pct_vs_base',
                    'base_log', 'forecast_log')
} | {'cogs_forecast': 'COGS', 'cogs_ratio': 'COGS/G'}
_START_FIELDS = {'r_start', 'n_start', 'u_start', 'p_start'}
DRIVER_FAMILY = {f'{k}{x}': k.upper() for k in 'nup' for x in ('_start', '_end', '_change_rate')} | {
    'contrib_n': 'N', 'contrib_u': 'U', 'contrib_p': 'P'}
# Năm trong phạm vi dữ liệu nguồn (2012-07-04 → 2022-12-31, CLAUDE.md §1): nhắc tới được kể cả khi chưa gọi tool
# ("dữ liệu chỉ đến hết 2022"). Năm không phải số liệu; số đứng trước đơn vị vẫn bị chặn.
DATA_YEARS = frozenset(str(y) for y in range(2012, 2023))
_DATA_DATES = re.compile(r'2012-07-04|2022-12-31|0?4/0?7/2012|31/12/2022')     # ngày đầu / cuối của dữ liệu
MONEY_SUFFIX = ' VND'   # PM chốt 2026-10-05 (metric_catalog.DECISIONS['currency_vnd'])

RANK_WORDS = ('nhiều nhất', 'lớn nhất', 'mạnh nhất', 'cao nhất', 'thấp nhất', 'ít nhất', 'chủ yếu', 'đứng đầu',
              'chính xác nhất', 'tốt nhất', 'kém nhất',
              'nhỏ nhất', 'mạnh hơn cả', 'dẫn đầu', 'nhẹ nhất', 'chậm nhất', 'yếu nhất')
# từ xếp hạng nói về phía CỰC (ΔR âm nhất / dương nhất): largest_* chứng minh được. "nhỏ nhất", "ít nhất" là phía
# ngược lại (giảm ít nhất): chỉ smallest_* chứng minh được (có cho nhóm từ 2026-10-09; giai đoạn / điểm đổi hướng chưa có).
STRONG_WORDS = ('mạnh nhất', 'nhiều nhất', 'lớn nhất', 'dẫn đầu', 'đứng đầu', 'mạnh hơn cả')
WEAK_WORDS = ('nhỏ nhất', 'ít nhất', 'nhẹ nhất', 'chậm nhất', 'yếu nhất')
# tiêu chí xếp hạng giai đoạn PS2 mà câu văn nêu: theo CAGR (largest_*_cagr) hay theo mức đổi R bằng tiền (largest_*)
# Chỉ tính là tiêu chí khi đi sau "theo / xét / lẫn / tiêu chí": "mức đổi R là {c2}" chỉ là dẫn số, không phải tiêu chí.
_CRIT_CAGR = re.compile(r'(?:theo|xét|lẫn|tiêu chí)\s+(?:cả\s+)?(?:tiêu chí\s+)?(?:cagr|tốc độ)')
_CRIT_TIEN = re.compile(r'bằng tiền|(?:theo|xét|tiêu chí)\s+(?:cả\s+)?(?:tiêu chí\s+)?(?:mức đổi r(?!\w)|số tiền|tiền|δr)')
# câu nối mở đầu bằng đại từ chỉ giai đoạn / nhóm / điểm vừa nói ở câu trước: "Đây cũng là giai đoạn giảm mạnh nhất"
# câu nối nói về chỉ tiêu MỨC (tỷ trọng, R cao / thấp nhất), không phải mức đổi: largest_* không chứng minh được
_NOT_CHANGE = re.compile(r'tỷ trọng|chiếm|cao nhất|thấp nhất|quy mô')
# câu nói giới hạn của tool ("dữ liệu chỉ xếp hạng phía giảm nhiều nhất, không xếp hạng phía ít nhất"): không phải claim
# và câu gợi ý hỏi tiếp ("bạn có thể hỏi giai đoạn giảm mạnh nhất"); chỉ miễn khi câu không gọi tên chủ thể cụ thể
_RANK_LIMIT = re.compile(r'(?:không|chưa|chỉ)\s+(?:có\s+)?(?:xếp hạng|xếp)(?!\w)|(?:có thể|hãy|thử)\s+hỏi(?!\w)'
                         # câu mô tả LUẬT chọn model ("lấy điểm ngày thấp nhất"), không khẳng định model nào (live B3c GM14)
                         r'|luật chọn|theo luật|thước chọn')
# tên chỉ tiêu season_peak_trough_ratio ("tỷ lệ tháng cao nhất so với tháng thấp nhất", "chênh mùa (cao nhất / thấp nhất)"):
# là TÊN số, không phải câu xếp hạng (live B6 V05, 3/3 lượt bị chặn nhầm). Bỏ cụm này trước khi tìm chữ xếp hạng; chữ xếp
# hạng còn lại trong câu ("giai đoạn có chênh mùa lớn nhất") vẫn bị kiểm
_METRIC_NAME_RANK = re.compile(r'(?:tháng\s+)?cao nhất\s*(?:so với|so|trên|÷|/)\s*(?:tháng\s+)?thấp nhất', re.I)
# chủ thể cụ thể trong câu: giai đoạn A–D, năm, tháng (tên nhóm đã có bước kiểm riêng; N/U/P xét bằng _said_driver)
_NAMED_SUBJECT = re.compile(r'giai đoạn\s+[A-D](?!\w)|(?<!\d)(?:19|20)\d\d(?!\d)|tháng\s+\d', re.I)
_ANAPHOR = re.compile(r'^\s*(?:và\s+)?(?:đây|đó|(?:giai đoạn|ngành hàng|ngành|nhóm|vùng|khu vực|kênh|điểm đổi hướng|'
                      r'điểm|cú đổi hướng)\s+(?:này|đó))(?!\w)')
# so sánh hai số ("2019 cao hơn 2020") là phép tính model tự làm: chỉ được nói khi câu dẫn cột thay đổi tool đã tính
COMPARE_WORDS = ('cao hơn', 'thấp hơn', 'lớn hơn', 'nhỏ hơn', 'nhiều hơn', 'ít hơn', 'vượt')
NEG_WORDS = ('giảm', 'sụt', 'kéo xuống', 'âm', 'mất')
POS_WORDS = ('tăng', 'kéo lên', 'góp thêm', 'dương', 'cải thiện')
_PLACEHOLDER = re.compile(r'\{(c\d+)\}')
_PATH = re.compile(r'^(T\d+)\.(rows\[([^\]]+)\]\.(\w+)|derived\.(\w+)(?:\.(\w+))?)$')
_NUMBER = re.compile(r'(?<![^\W\d])\d[\d.,]*')     # không tính chữ số dính sau chữ cái (AI1, PS3, c1)
_SENTENCE = re.compile(r'[.;!?\n]')
# mốc ngày/tháng người dùng có thể gõ: 15/3, 10/6/2019, tháng 8, ngày 15, quý 3
DATE_RE = _DATE = re.compile(r'(?<!\d)\d{1,2}/\d{1,2}(?:/\d{4})?(?![\d/])|(?:ngày|tháng|quý)\s+\d{1,2}(?!\d)', re.I)
# số đứng trước đơn vị tiền/tỷ lệ: chỉ miễn nguyên cụm có trong DEF của lượt này
_UNIT_AFTER = re.compile(r'(?<![^\W\d])\d(?:[\d.,]*\d)?\s*(?:tỷ|tỉ|triệu|nghìn|ngàn|vnd|đồng|usd|\$|%)(?!\w)', re.I)
_DRIVER_WORD = {'N': re.compile(r'số đơn|(?<!\w)N(?!\w)'),
                'U': re.compile(r'số món|món mỗi đơn|(?<!\w)U(?!\w)'),
                'P': re.compile(r'giá(?! trị)|(?<!\w)P(?!\w)')}
_DUP_MONEY = re.compile(r'\s*(?:VND|VNĐ|đồng)(?!\w)', re.I)
_DUP_PCT = re.compile(r'\s*%')
_DUP_PP = re.compile(r'\s*điểm\s*(?:%|phần trăm)', re.I)
_METRIC_WORD = re.compile(r'ΔR|(?<![\w])[RG](?![\w])|doanh thu thực nhận|tiền thực nhận|tiền hàng|doanh thu gộp'
                          r'|(?<![\w])COGS(?![\w])|giá vốn', re.I)
_RATIO_WORD = re.compile(r'(?:tỷ lệ\s+)?(?:COGS|giá vốn)\s*(?:/|trên|÷)\s*(?:G|doanh thu(?:\s+gộp)?)(?![\w])', re.I)


def _is_num(v) -> bool:
    return isinstance(v, Number) and not isinstance(v, bool)     # tiền là Decimal, tỷ lệ là float


@dataclass
class Checked:
    ok: bool
    errors: list[str]
    answer_md: str | None = None                       # câu trả lời đã thay số thật (chỉ khi ok)
    values: dict = field(default_factory=dict)          # claim id → (path, giá trị gốc, chuỗi hiển thị)
    groups: set = field(default_factory=set)            # tên nhóm (ngành/vùng/kênh) gắn với claim đã dùng


def _resolve(path: str, results: dict):
    """(giá trị, tên trường, dòng | None) hoặc ném ValueError với lý do."""
    m = _PATH.match(path or '') if isinstance(path, str) else None
    if not m:
        raise ValueError(f'đường dẫn {path!r} sai dạng (vd. T1.rows[0].delta_r, T1.derived.largest_decrease.groups)')
    ref = m.group(1)
    res = results.get(ref)
    if res is None:
        raise ValueError(f'{ref} không phải kết quả tool của lượt này')
    if not res.ok:
        raise ValueError(f'{ref} có trạng thái {res.status}, không có số')
    if res.evidence is not None and res.evidence.tool == 'search_knowledge':
        raise ValueError(f'{ref} là đoạn tài liệu RAG, không được làm nguồn claim hay chỗ đặt')
    if m.group(2).startswith('rows'):
        sel, fld = m.group(3), m.group(4)
        # chuỗi từng năm (get_revenue_summary to_year): rows[2016] là dòng năm 2016 khi đúng một dòng có năm đó
        # (live bộ N 2026-10-17: mô hình viết rows[2016], app đọc thành dòng thứ 2016 và chặn)
        by_year = [r for r in res.rows if str(r.get('year')) == sel] if len(sel) == 4 and sel.isdigit() else []
        if len(by_year) == 1 and 'turning_year' not in by_year[0]:
            row = by_year[0]
        elif sel.isdigit() and not (len(sel) == 4 and 'turning_year' in (res.rows[0] if res.rows else {})):
            i = int(sel)
            if i >= len(res.rows):
                raise ValueError(f'{ref} không có dòng {i}')
            row = res.rows[i]
        else:
            hit = [r for r in res.rows if any(r.get(k) is not None and str(r[k]) == sel for k in ROW_KEYS)]
            if len(hit) != 1:
                raise ValueError(f'{ref} không có nhóm / giai đoạn / điểm {sel!r}')
            row = hit[0]
        if fld not in row:
            raise ValueError(f'{ref} không có trường {fld}')
        return row[fld], fld, row
    key, sub = m.group(5), m.group(6)
    if key not in res.derived:
        raise ValueError(f'{ref}.derived không có {key}')
    v = res.derived[key]
    if sub is not None:
        if not isinstance(v, dict) or sub not in v:
            raise ValueError(f'{ref}.derived.{key} không có {sub}')
        v = v[sub]
    if isinstance(v, dict) or (isinstance(v, list) and not all(isinstance(x, (str, Number)) for x in v)):
        raise ValueError(f'{path} là cả một khối dữ liệu, không phải một ô; trỏ tới khóa con là số hoặc chữ')
    return v, sub or key, None


def _fmt(v, fld: str, absolute: bool) -> str:
    if isinstance(v, list):
        return ', '.join(map(str, v))
    if isinstance(v, bool):
        return 'có' if v else 'không'
    if isinstance(v, _date):             # trained_through, forecast_date: trước đây rơi xuống num() và in ".,2f" (live B3c GM13)
        return v.strftime('%d/%m/%Y')
    if fld in ('top_up_driver', 'top_down_driver'):
        return DRIVER_LABEL.get(v, str(v))
    if isinstance(v, str):
        return v
    x = abs(v) if absolute else v
    signed = fld in SIGNED and not absolute
    if fld in MONEY:
        return num(x, 0, signed) + MONEY_SUFFIX
    if fld in PRICE:
        return num(x, 2) + MONEY_SUFFIX
    if fld in RATE:
        return pct(x, 1, signed)
    if fld in PCT100:
        return num(x, 1) + '%'
    if fld in PP:
        return num(x, 1, signed) + ' điểm %'
    if fld in PP_FRAC:
        return num(x * 100, 1, signed) + ' điểm %'
    if fld == 'pct_vs_base':
        return num(x, 1, signed and not absolute) + '%'
    if fld == 'max_abs_pct':
        return num(x, 3) + '%'
    if fld == 'threshold_pct':
        return num(x, 1) + '%'
    if fld == 'n':
        return num(x)
    if fld in ('contribution_log', 'base_log', 'forecast_log'):
        return num(x, 4, signed) + ' log'
    if fld == 'multiplier':
        return num(x, 4) + ' lần'
    if fld in UNITS or fld in INDEX:
        return num(x, 2)
    if fld in YEARS or fld in MONTHS:
        return str(int(x))                 # năm/tháng không có dấu nghìn ("2019", không phải "2.019")
    if fld in COUNT:
        return num(x)
    return num(x, 2, signed)


def allowed_years(results: dict) -> set[str]:
    """Số được viết thẳng trong câu văn: năm của dòng kết quả, kỳ đã lọc, năm gốc "so năm trước", và số trong
    thông báo do app viết (vd. phạm vi dữ liệu 2012-07-04 → 2022-12-31 khi tool trả no_data)."""
    years = set()
    for res in results.values():
        msg = _numbers(res.message)             # thông báo do app viết, không phải do model
        years |= msg | {str(int(t)) for t in msg if t.isdigit()}      # "2012-07-04" → model viết "tháng 7/2012"
        for r in res.rows:
            for k in ('year', 'start_year', 'end_year', 'period_code', 'month', 'turning_year', 'first_year', 'last_year'):
                if r.get(k) is not None:
                    years.add(str(r[k]))
            years |= _date_forms(r)
        if res.evidence:
            for k in ('year', 'period_code', 'month'):
                v = res.evidence.filters_applied.get(k)
                if v is not None:
                    years.add(str(v))
                    if k != 'month' and str(v).isdigit():
                        years.add(str(int(v) - 1))
    return years


def _date_forms(r: dict) -> set[str]:
    """Cách viết mốc ngày / tháng của MỘT dòng kết quả có năm–tháng (dự báo, tháng PS1): "tháng 8", "8/2023",
    "01/08/2023"... để câu văn được nhắc lại kỳ của chính dòng đó, không mở số nào khác."""
    y, m = r.get('year'), r.get('month')
    if not (isinstance(y, int) and isinstance(m, int)):
        return set()
    out = {f'tháng {m}', f'tháng {m:02d}', f'{m}/{y}', f'{m:02d}/{y}', str(m), f'{m:02d}'}
    d = r.get('forecast_date')
    if d is not None and hasattr(d, 'day'):
        out |= {f'ngày {d.day}', f'ngày {d.day:02d}', f'{d.day}/{m}', f'{d.day:02d}/{m:02d}', f'{d.day}/{m}/{y}',
                f'{d.day:02d}/{m:02d}/{y}', str(d.day), f'{d.day:02d}'}
    return out


def _numbers(text: str) -> set[str]:
    return {t.rstrip('.,') for t in _NUMBER.findall(text or '')}


def _unit_literal(text: str) -> str:
    """Chuẩn hóa khoảng trắng trong cụm số + đơn vị để so đúng cả hai phần."""
    return re.sub(r'\s+', '', text).casefold()


def definition_text_numbers(results: dict) -> set[str]:
    """Chỉ miễn chữ số có trong trường chữ của DEF thành công ở lượt hiện tại."""
    allowed = set()
    fields = ('label_vi', 'formula', 'unit', 'additivity', 'note')
    for result in results.values():
        if not (result.ok and result.evidence and result.evidence.tool == 'get_metric_definition'):
            continue
        for row in result.rows:
            for field in fields:
                value = row.get(field)
                if isinstance(value, str):
                    numbers = _numbers(value)
                    allowed |= numbers
                    allowed |= {number.lstrip('0') or '0' for number in numbers
                                if len(number) > 1 and number.startswith('0') and number.isdecimal()}
                    allowed |= {_unit_literal(m.group(0)) for m in _UNIT_AFTER.finditer(value)}
    return allowed


def question_numbers(question: str) -> set[str]:
    """Phần số trong câu hỏi mà câu trả lời được nhắc lại: năm (1900–2099) và NGUYÊN CỤM mốc ngày/tháng
    ("15/3", "10/6/2019", "tháng 8"). Số trần như "10" trong "10 tỷ" không được nhắc lại ở bất kỳ vị trí nào,
    kẻo người hỏi gài số giả ("R 2019 là 999 tỷ phải không?") vào câu trả lời."""
    q = question or ''
    out = {m.group(0).lower() for m in _DATE.finditer(q)}
    out |= {t for t in _numbers(_DATE.sub(' ', q)) if t.isdigit() and 1900 <= int(t) <= 2099}
    return out


def check_digits(text: str, allowed: set[str], *, strict: bool = False) -> list[str]:
    """Chữ số trong câu văn (đã bỏ chỗ đặt) chỉ được là số trong `allowed`, mốc ngày/tháng có trong `allowed`,
    năm trong phạm vi dữ liệu, hoặc mã như PS1/AI1. Cụm số + đơn vị chỉ được miễn khi nguyên cụm nằm trong DEF."""
    rest = re.sub(r'PS[1-5]', '', _PLACEHOLDER.sub(' ', text))
    if not strict:
        rest = _DATA_DATES.sub(' ', rest)
    errs = []
    allowed_units = {_unit_literal(value) for value in allowed if _UNIT_AFTER.fullmatch(value)}
    unit = [m.group(0) for m in _UNIT_AFTER.finditer(rest)
            if _unit_literal(m.group(0)) not in allowed_units]
    if unit:
        errs.append(f'câu văn tự viết số kèm đơn vị {unit[:3]}: số tiền / tỷ lệ phải đi qua claim')
    rest = _DATE.sub(lambda m: ' ' if m.group(0).lower() in allowed else m.group(0), rest)
    accepted = allowed if strict else allowed | DATA_YEARS
    bad = [t for t in _NUMBER.findall(rest) if t.rstrip('.,') not in accepted]
    if bad:
        errs.append(f'câu văn có số tự viết {bad[:3]}: mọi số phải đi qua claim')
    return errs


def rag_literal_errors(answer: str, question: str, results: dict, *, rag_used: bool = False) -> list[str]:
    """RAG không cấp cả ngày/năm lịch sử vốn được miễn ở chat L1; chỉ chấp nhận kỳ từ câu hỏi/tool số."""
    if not isinstance(answer, str) or not (rag_used or any(r.evidence and r.evidence.tool == 'search_knowledge'
                                                          for r in results.values())):
        return []
    data_results = {ref: r for ref, r in results.items()
                    if r.evidence and r.evidence.tool != 'search_knowledge'}
    return check_digits(answer, allowed_years(data_results) | question_numbers(question), strict=True)


def _direction(window: str) -> int:
    w = window.lower().replace('tăng trưởng', '')      # "tăng trưởng âm 39%" là cách nói bình thường, không phải "tăng"
    neg, pos = any(x in w for x in NEG_WORDS), any(x in w for x in POS_WORDS)
    return -1 if neg and not pos else (1 if pos and not neg else 0)


_DIR_WORD = re.compile(r'(?<!\w)(?:' + '|'.join(re.escape(x) for x in NEG_WORDS + POS_WORDS) + r')(?!\w)')
# giữa chữ tăng/giảm và chỗ đặt chỉ được vài chữ, không có ngoặc / phẩy / gạch / mũi tên: "giảm {c}", "mức giảm R là {c}"
_DIR_GAP_BREAK = re.compile(r'[()\[\],—–→:]')


def _adjacent_direction(seg: str) -> int:
    """Hướng của chữ tăng/giảm ĐI LIỀN trước chỗ đặt (tối đa 3 chữ ở giữa, không qua ngoặc/phẩy/gạch).
    Chỉ khi đó số mới được in không dấu: "R giảm {c}" → "R giảm 5,8 triệu". Chữ "giảm" ở xa hoặc thuộc tên khác
    ("giai đoạn B — Chững, giảm nhẹ (2016→2018), với CAGR {c}") thì giữ dấu thật, không thì người đọc hiểu thành tăng."""
    w = seg.lower().replace('tăng trưởng', ' ' * len('tăng trưởng'))
    hits = list(_DIR_WORD.finditer(w))
    if not hits:
        return 0
    tail = w[hits[-1].end():]
    if _DIR_GAP_BREAK.search(tail) or len(tail.split()) > 3:
        return 0
    return -1 if hits[-1].group(0) in NEG_WORDS else 1


def _rank_direction(path: str) -> int:
    """Hướng của claim xếp hạng: −1 (largest_/smallest_decrease, top_down_driver), +1 (largest_/smallest_increase,
    top_up_driver), 0 nếu không phải claim xếp hạng."""
    if re.search(r'\.derived\.(?:largest|smallest)_decrease', path) or path.endswith('top_down_driver'):
        return -1
    if re.search(r'\.derived\.(?:largest|smallest)_increase', path) or path.endswith('top_up_driver'):
        return 1
    if '.derived.lowest_' in path:          # B3: lowest_score / lowest_mape_g_thang / lowest_month (phía thấp)
        return -1
    if '.derived.highest_' in path:
        return 1
    return LEVEL_RANK.get(path.rsplit('.', 1)[-1], 0)


def _said_metric(seg: str) -> str | None:
    """Chỉ tiêu mà đoạn ngay trước chỗ đặt gọi tên ('R' / 'G'); None nếu không gọi tên hoặc gọi cả hai
    ("R và G lần lượt là {c1} và {c2}": khi đó nhãn của app nói rõ số nào là gì)."""
    # B3 (RV02, RV08, review Codex 2026-10-15): COGS / giá vốn là chỉ tiêu riêng; "tỷ lệ COGS/G", "COGS/G", "giá vốn
    # trên doanh thu" là chỉ tiêu TỶ LỆ riêng (bỏ chữ COGS và G bên trong để không đếm thành hai chỉ tiêu)
    ratio = _RATIO_WORD.search(seg) is not None
    seg = _RATIO_WORD.sub(' ', seg)
    fams = {'COGS' if h.lower() in ('cogs', 'giá vốn') else 'G' if h.lower() in ('g', 'tiền hàng', 'doanh thu gộp')
            else 'R' for h in _METRIC_WORD.findall(seg)} | ({'COGS/G'} if ratio else set())
    return fams.pop() if len(fams) == 1 else None


def _said_driver(seg: str) -> str | None:
    """Thành phần N/U/P mà đoạn ngay trước chỗ đặt gọi tên; None nếu không gọi hoặc gọi nhiều ("N → U → P")."""
    hits = [k for k, rx in _DRIVER_WORD.items() if rx.search(seg)]
    return hits[0] if len(hits) == 1 else None


def _verified_driver_rank(sent: str, results: dict) -> bool:
    """Câu xếp hạng gọi tên thẳng N/U/P ("R giảm chủ yếu ở số đơn"): app tự đối chiếu với top_down_driver /
    top_up_driver của kết quả phân rã DUY NHẤT trong lượt, theo chữ tăng/giảm của câu. Không tin lời model."""
    rows = [r for res in results.values() if res.ok for r in res.rows if 'top_down_driver' in r]
    if len(rows) != 1 or any(w in sent.lower() for w in WEAK_WORDS):     # top_*_driver là phía LỚN nhất
        return False
    d = _direction(_PLACEHOLDER.sub(' ', sent))
    if not d and any(w in sent.lower() for w in STRONG_WORDS) and _is_num(rows[0].get('delta_r')):
        # "Thành phần đóng góp nhiều nhất là giá mỗi món (P)" (live H04c): câu không có chữ tăng/giảm → theo chiều ΔR
        d = (rows[0]['delta_r'] > 0) - (rows[0]['delta_r'] < 0)
    if not d:
        return False
    top = rows[0]['top_down_driver' if d < 0 else 'top_up_driver']
    clauses = [c for c in re.split(r'[,:()]|\{c\d+\}', sent) if any(w in c.lower() for w in RANK_WORDS)]
    # vế chứa từ xếp hạng không gọi tên N/U/P ("... và là thành phần kéo giảm nhiều nhất") → xét cả câu
    said = [_said_driver(c) or _said_driver(_PLACEHOLDER.sub(' ', sent)) for c in clauses]
    return bool(top) and bool(clauses) and all(x == str(top).upper() for x in said)


def _verified_explain_rank(sent: str, by_id: dict, results: dict) -> bool:
    """Đối chiếu mọi nhóm L4 được dẫn trong câu với top-k của đúng một kết quả tool."""
    refs = {}
    for cid in _PLACEHOLDER.findall(sent):
        item = by_id.get(cid)
        if not item or item[2] not in ('contribution_log', 'multiplier', 'pct_vs_base'):
            continue
        path, row = item[0].get('path', ''), item[3]
        ref = path.split('.')[0]
        res = results.get(ref)
        if not row or not res or not res.ok or not res.evidence or res.evidence.tool != 'explain_forecast':
            continue
        refs.setdefault(ref, set()).add(row.get('feature_group'))
    if len(refs) != 1 or any(w in sent.lower() for w in WEAK_WORDS):
        return False
    ref, groups = next(iter(refs.items()))
    if None in groups or not groups:
        return False
    rows = results[ref].rows
    said = _PLACEHOLDER.sub(' ', sent).lower()
    up = bool(re.search(r'\b(?:cao|tăng|kéo\s+lên)\b', said))
    down = bool(re.search(r'\b(?:thấp|giảm|kéo\s+xuống)\b', said))
    if up and down:
        return False
    if up or down:
        direction = 1 if up else -1
        selected = [r for r in rows if r['feature_group'] in groups]
        if len(selected) != len(groups) or any(r['contribution_log'] * direction <= 0 for r in selected):
            return False
        expected = {r['feature_group'] for r in rows
                    if r['contribution_log'] * direction > 0 and r.get('rank_dir') in range(1, len(groups) + 1)}
    else:
        expected = {r['feature_group'] for r in rows if r.get('rank') in range(1, len(groups) + 1)}
    return (len(expected) == len(groups) and groups == expected
             and all(str(r.get('feature_label', '')).lower() in said for r in rows
                     if r['feature_group'] in groups))


_SMALL_COUNT = re.compile(r'(\{c\d+\})\s+nhóm\s+(?:còn\s+lại|khác|có\s+ảnh\s+hưởng)', re.I)
_SMALL_UNDER = re.compile(r'\b(?:dưới|nhỏ hơn)\s*(\{c\d+\})', re.I)
_SMALL_MAX = re.compile(r'\b(?:tối đa|không quá|lớn nhất trong đó)\s*(\{c\d+\})', re.I)
_SMALL_REMAINDER = re.compile(r'\bnhóm\s+còn\s+lại\b', re.I)
_EXPLAIN_REMAINDER_UNNUMBERED = re.compile(
    r'\b(?:nhóm|yếu\s+tố|biến|thành\s+phần)\s+(?:khác|còn\s+lại)\b', re.I)
_SUM_WORD = re.compile(r'\b(?:tổng|cộng lại|cộng dồn)\b', re.I)


def _negated_sum(sent: str, start: int) -> bool:
    before = re.findall(r'\b[\wÀ-ỹ]+\b', sent[:start].lower())[-3:]
    return 'không' in before or 'chẳng' in before


def _explain_significant_cited(ref: str, answer: str, values: dict, results: dict) -> bool:
    """Các nhóm từ ngưỡng trở lên của một kết quả đã có số trong toàn câu trả lời."""
    res = results.get(ref)
    if not res or not res.ok or not res.evidence or res.evidence.tool != 'explain_forecast':
        return False
    threshold = res.derived['small_groups']['threshold_pct']
    significant = {r['feature_group'] for r in res.rows if abs(r['pct_vs_base']) >= threshold}
    cited = {m[1] for cid, (path, _value, _shown) in values.items() if '{' + cid + '}' in answer
             and path.startswith(ref + '.rows[')
             and (m := re.search(r'\.rows\[([^]]+)\]\.(?:pct_vs_base|contribution_log|multiplier)$', path))}
    return significant <= cited


def _small_groups_errors(sent: str, answer: str, values: dict, results: dict) -> list[str]:
    """Đối chiếu cả vị trí hai claim, ngưỡng thật và tập nhóm đã dẫn số trong lời."""
    ids = _PLACEHOLDER.findall(sent)
    paths = {cid: values[cid][0] for cid in ids if cid in values}
    small_claim = any('.derived.small_groups.' in p for p in paths.values())
    remainder = bool(_SMALL_REMAINDER.search(sent))
    other = bool(re.search(r'\bnhóm\s+khác\b', sent, re.I))
    count = _SMALL_COUNT.search(sent)
    if not (small_claim or ids and (remainder or other or count
                                    or re.search(r'mỗi\s+nhóm\s+(?:dưới|nhỏ hơn)\s*\{c\d+\}', sent, re.I))):
        return []

    # Liệt kê tên và số của từng nhóm là một lời khác với tóm tắt "N nhóm ... dưới X".
    if (remainder or other) and not small_claim and not count and not _SMALL_UNDER.search(sent) \
            and not _SMALL_MAX.search(sent):
        row_refs = {p.split('.')[0] for p in paths.values() if '.rows[' in p}
        if len(row_refs) == 1:
            ref = row_refs.pop()
            if _explain_significant_cited(ref, answer, values, results):
                return []
        return ['"còn lại/khác" cần dẫn đủ nhóm có ảnh hưởng lớn của cùng kết quả explain_forecast']
    refs = {p.split('.')[0] for p in paths.values() if '.derived.small_groups.' in p}
    if len(refs) != 1:
        return ['số nhóm và ngưỡng % phải trỏ vào derived.small_groups']
    ref = refs.pop()
    if (remainder or other or any(p == ref + '.derived.small_groups.n' for p in paths.values())) and not count:
        return ['số nhóm phải trỏ vào derived.small_groups.n']
    if count and paths.get(count[1][1:-1]) != ref + '.derived.small_groups.n':
        return ['số nhóm phải trỏ vào derived.small_groups.n']
    under, maximum = _SMALL_UNDER.search(sent), _SMALL_MAX.search(sent)
    if not under and not maximum:
        return ['ngưỡng nhóm nhỏ phải trỏ vào derived.small_groups.threshold_pct']
    if under and paths.get(under[1][1:-1]) != ref + '.derived.small_groups.threshold_pct':
        return ['"dưới" phải trỏ vào derived.small_groups.threshold_pct']
    if maximum and paths.get(maximum[1][1:-1]) != ref + '.derived.small_groups.max_abs_pct':
        return ['"tối đa/không quá/lớn nhất trong đó" phải trỏ vào derived.small_groups.max_abs_pct']
    if remainder or other:
        res = results.get(ref)
        if not res or not res.ok or not res.evidence or res.evidence.tool != 'explain_forecast':
            return ['nhóm còn lại/khác thiếu kết quả explain_forecast cùng nguồn']
        if not _explain_significant_cited(ref, answer, values, results):
            return ['"còn lại/khác" cần dẫn đủ nhóm có ảnh hưởng lớn; nói "N nhóm có ảnh hưởng dưới ngưỡng mỗi nhóm"']
    return []


def _criteria(sent: str) -> set[str]:
    """Tiêu chí xếp hạng câu văn nêu: {'cagr'}, {'tien'}, cả hai ("cả mức đổi R bằng tiền lẫn CAGR") hoặc rỗng."""
    s = _PLACEHOLDER.sub(' ', sent).lower()
    return {k for k, rx in (('cagr', _CRIT_CAGR), ('tien', _CRIT_TIEN)) if rx.search(s)}


def _is_phase_result(res) -> bool:
    return 'largest_decrease_cagr' in res.derived      # chỉ kết quả giai đoạn PS2 có hai tiêu chí xếp hạng


def _rank_kind(row: dict) -> tuple[str, str] | None:
    """(danh sách trong derived.largest_*, cột xếp hạng) mà dòng này thuộc về: giai đoạn, điểm đổi hướng, nhóm."""
    if row.get('phase_code') is not None and 'cagr' in row:
        return 'phases', 'delta_r'
    if row.get('turning_year') is not None:
        return 'turns', 'magnitude'
    if isinstance(row.get('dimension_value'), str):
        return 'groups', 'delta_r'
    return None


def _row_label_in(row: dict, kind: str, labels) -> bool:
    """Dòng có nằm trong danh sách xếp hạng không. Nhãn do tools.py dựng: "C — Sập (2018→2019)",
    "cuối 2016 (A → B)", tên nhóm."""
    if not isinstance(labels, list):
        return False
    if kind == 'phases':
        return any(str(x).startswith(f"{row['phase_code']} — ") for x in labels)
    if kind == 'turns':
        return any(str(x).startswith(f"cuối {row['turning_year']} ") for x in labels)
    return row['dimension_value'] in labels


def _verified_backtest_compare(sent: str, by_id: dict) -> bool:
    """Câu so hai số backtest (live B3c GM14: "bản gộp có MAPE G tháng {c2}, thấp hơn mức {c3} của model chính"): mỗi chữ
    so sánh phải có chỗ đặt gần nhất phía trước và phía sau cùng một thước backtest, và chiều đúng với giá trị thật.
    Chỉ cho thước backtest; câu so sánh R/G theo năm vẫn phải dẫn cột thay đổi tool đã tính."""
    low = sent.lower()
    hits = [(m.start(), w) for w in _LOWER_WORDS + _HIGHER_WORDS for m in re.finditer(re.escape(w), low)]
    if not hits or any(w in low for w in COMPARE_WORDS if w not in _LOWER_WORDS + _HIGHER_WORDS):
        return False                        # "vượt" (mốc sàn...) không có chiều số để kiểm ở đây
    marks = [(m.start(), m[1]) for m in _PLACEHOLDER.finditer(sent) if m[1] in by_id]
    for pos, word in hits:
        before = [cid for p, cid in marks if p < pos]
        after = [cid for p, cid in marks if p > pos]
        if not before or not after:
            return False
        a, b = by_id[before[-1]], by_id[after[0]]
        if not (a[2] == b[2] and a[2] in BACKTEST_COMPARABLE and _is_num(a[1]) and _is_num(b[1])):
            return False
        if (a[1] < b[1]) != (word in _LOWER_WORDS) or a[1] == b[1]:
            return False
    return True


def _verified_anaphor_rank(sent: str, prev: str, by_id: dict, results: dict, need: set | None = None) -> bool:
    """Câu nối "Đây (cũng) là giai đoạn giảm mạnh nhất…" (live A03, A03d, C02, E05): câu không có chỗ đặt xếp hạng
    nhưng đại từ ở đầu câu trỏ về giai đoạn / nhóm / điểm mà CÂU NGAY TRƯỚC đã dẫn số (rows[X] hoặc claim xếp hạng
    một phần tử). App tự đối chiếu X với derived.largest_* tính trên đủ tập, theo chiều tăng/giảm của câu và theo
    tiêu chí câu nêu; giai đoạn mà câu không nêu tiêu chí thì phải đứng đầu theo CẢ tiền lẫn CAGR. Không tin lời model.
    "nhỏ nhất", "ít nhất" (phía ngược) không đối chiếu được nên vẫn chặn. Câu phải có chữ tăng/giảm: xếp hạng ở đây là
    theo MỨC ĐỔI (ΔR, CAGR, độ lớn đổi hướng); câu nói về tỷ trọng / mức R ("vùng này chiếm tỷ trọng lớn nhất") là chỉ
    tiêu khác nên không đối chiếu. `need`: chỉ đối chiếu các tiêu chí này (tiêu chí câu nêu mà chỗ đặt trong câu
    chưa chứng minh)."""
    low = _PLACEHOLDER.sub(' ', sent).lower()
    strong, weak = any(w in low for w in STRONG_WORDS), any(w in low for w in WEAK_WORDS)
    if not _ANAPHOR.match(low) or strong == weak:
        return False
    side = 'smallest' if weak else 'largest'      # "Đây là ngành giảm ít nhất" → smallest_decrease (chỉ nhóm có)
    if _NOT_CHANGE.search(low):
        return False
    # đối tượng của câu trước: mọi claim trỏ vào dòng có thể xếp hạng phải cùng một dòng
    bound = {}
    for cid in _PLACEHOLDER.findall(prev):
        if cid not in by_id:
            continue
        c, v, fld, row = by_id[cid]
        ref = c['path'].split('.')[0]
        if row is not None and _rank_kind(row):
            bound[id(row)] = (ref, row)
        elif isinstance(v, list) and len(v) == 1 and '.derived.largest_' in c['path']:
            hit = [r for r in results[ref].rows if _rank_kind(r) and _row_label_in(r, _rank_kind(r)[0], v)]
            if len(hit) == 1:
                bound[id(hit[0])] = (ref, hit[0])
    if len(bound) != 1:
        return False
    (ref, row), = bound.values()
    kind, key = _rank_kind(row)
    d = _direction(low)
    if not d:
        return False
    res = results[ref]
    crit = need if need is not None else (_criteria(sent) or {'tien', 'cagr'}) if _is_phase_result(res) else {'tien'}
    for k in crit:
        top = res.derived.get(f"{side}_{'increase' if d > 0 else 'decrease'}{'_cagr' if k == 'cagr' else ''}")
        if not isinstance(top, dict) or top.get('tie') or not _row_label_in(row, kind, top.get(kind)):
            return False
    return True


def _criteria_errors(sent: str, paths: list[str], results: dict, prev: str = '', by_id: dict | None = None) -> list[str]:
    """Câu xếp hạng giai đoạn nêu tiêu chí ("theo CAGR", "bằng tiền", "cả … lẫn …") thì mỗi tiêu chí phải có chỗ đặt
    trỏ vào đúng bảng xếp hạng: CAGR → derived.largest_*_cagr, tiền → derived.largest_* (live A03: câu "… và cũng đứng
    đầu theo CAGR" chỉ dẫn xếp hạng theo tiền). Câu nối "Đây là…" thì tiêu chí còn thiếu được app đối chiếu với đối
    tượng của câu trước (live A03d: CAGR dẫn ở câu trước, tiền dẫn trong câu)."""
    have = set()
    for p in paths:
        ref = p.split('.')[0]
        if '.derived.largest_' in p and ref in results and _is_phase_result(results[ref]):
            have.add('cagr' if re.search(r'\.derived\.largest_\w+_cagr\.', p) else 'tien')
    if not have:
        return []
    missing = _criteria(sent) - have
    if missing and by_id is not None and _verified_anaphor_rank(sent, prev, by_id, results, need=missing):
        return []
    hint = {'cagr': 'derived.largest_*_cagr.phases', 'tien': 'derived.largest_*.phases'}
    return [f'câu "{sent.strip()[:80]}" xếp hạng giai đoạn theo {"CAGR" if k == "cagr" else "mức đổi R bằng tiền"} '
            f'nhưng không có chỗ đặt trỏ vào {hint[k]} (mỗi tiêu chí một chỗ đặt)' for k in sorted(missing)]


def _year_of(fld: str, row: dict | None):
    if not row:
        return None
    if 'period' in row:                                   # kỳ gộp 2013–2022
        return row['period']
    if row.get('month') is not None and row.get('year') is not None:
        y = int(row['year']) - (1 if fld == 'r_same_month_prior_year' else 0)
        return f"{row['month']}/{y}"
    if row.get('turning_year') is not None:
        t = int(row['turning_year'])
        return {'r_12m_before': t, 'r_12m_after': t + 1}.get(fld, f'cuối {t}')
    if row.get('first_year') is not None:                 # giai đoạn PS3 (năm lịch gom theo giai đoạn)
        a, b = row['first_year'], row.get('last_year')
        return str(a) if a == b else f'{a}–{b}'
    if fld == 'r_prior_year' and row.get('year') is not None:
        return int(row['year']) - 1
    if fld in _START_FIELDS:
        return row.get('start_year')
    if row.get('phase_code') is not None and fld != 'r_end':      # giai đoạn PS2: cả khoảng năm
        return f"{row['start_year']}→{row['end_year']}"
    return row.get('year', row.get('end_year'))


def _label_parts(fld: str, row: dict | None) -> tuple:
    """(chỉ tiêu, nhóm, kỳ, phần thêm) do app dựng từ chính ô dữ liệu; chỉ tiêu None nếu cột chưa có nhãn."""
    row_ = row or {}
    group = row_.get('dimension_value') or (f"giai đoạn {row_['phase_code']}" if row_.get('phase_code') else None)
    if row_.get('feature_group') and fld in ('contribution_log', 'multiplier', 'pct_vs_base'):
        group = 'nhóm ' + FEATURE_GROUP_LABEL.get(row_['feature_group'], row_['feature_group'])
    if row_.get('candidate_label') and (row_.get('is_primary') is False or fld not in FORECAST_FIELDS):
        # số của ứng viên khác model chính, hoặc số backtest của từng ứng viên: nhãn ghi rõ ứng viên nào
        group = row_['candidate_label'] + ('' if row_.get('is_primary') else ', không phải model chính')
    extra = []
    if fld == 'g_forecast' and _is_num(row_.get('lower_g')) and _is_num(row_.get('upper_g')):
        extra.append(f"khoảng 80%: {num(row_['lower_g'], 0)} – {num(row_['upper_g'], 0)}{MONEY_SUFFIX}")
    if fld == 'g_forecast' and _is_num(row_.get('typical_month_error')):
        extra.append(f"sai số tháng điển hình {num(row_['typical_month_error'], 1)}% (backtest 2020–2022)")
    if fld in FORECAST_FIELDS and row_.get('is_partial'):
        extra.append(f"chỉ {row_['n_days']}/{row_['n_days_in_period']} ngày có dự báo")
    if fld in ('contribution_log', 'multiplier', 'pct_vs_base') and row_.get('is_partial'):
        extra.append(f"chỉ {row_['n_days']}/{row_['n_days_in_period']} ngày trong tháng")
    return FIELD_LABEL.get(fld), group, _year_of(fld, row), extra


def _label(fld: str, row: dict | None, clause: str, actual: bool = False, answer: str = '',
           after: str = '') -> str:
    """Nhãn do app dựng từ ô dữ liệu; số L4 bỏ nhãn khi vế có đúng nhóm và câu trả lời có đúng kỳ.
    actual (B7): khi có cả dự báo, số thực tế luôn mang nhãn "thực tế" do app gắn."""
    name, group, year, extra = _label_parts(fld, row)
    if name is None:
        return ''
    if actual:
        return ' (' + ', '.join([f'{name} thực tế'] + [str(x) for x in (group, year) if x is not None] + extra) + ')'
    if fld in ('contribution_log', 'multiplier', 'pct_vs_base') and row and row.get('feature_group'):
        feature = str(row.get('feature_label') or FEATURE_GROUP_LABEL.get(row['feature_group'], row['feature_group']))
        period = _claim_period(row)
        said_period = any(_period_match(spec, period) for spec in _periods(answer))
        # Phần "so với mức nền" thường đứng SAU chỗ đặt; chỉ đọc tới chỗ đặt / vế kế tiếp.
        before = re.split(r'[,;:()—–.!?\n]|\bvà\b', clause, flags=re.I)[-1]
        local = before + re.split(r'[,;:()—–.!?\n]|\bvà\b|\{c\d+\}', after, maxsplit=1, flags=re.I)[0]
        has_base = 'mức nền' in local.lower()
        if feature.lower() in before.lower() and has_base and said_period:
            return ' (' + ', '.join(extra) + ')' if extra else ''
        short = ([] if 'so với mức nền' in local.lower() else ['so với mức nền']) \
            + ([str(year)] if year is not None else [])
        return ' (' + ', '.join(short + extra) + ')'
    parts = [name] + [str(x) for x in (group, year) if x is not None] + extra
    said = (fld in ('r', 'g', 'r_prior_year', 'delta_r', 'r_start', 'r_end')
            and _said_metric(clause) == METRIC_FAMILY.get(fld)
            and (group is None or str(group).lower() in clause.lower())
            and (year is None or str(year) in clause))
    return '' if said else ' (' + ', '.join(parts) + ')'


_MIX_CMP = re.compile(r'cao hơn|thấp hơn|lớn hơn|nhỏ hơn|nhiều hơn|ít hơn|vượt|chênh|gấp|so với|tăng|giảm')
_NEGATED = re.compile(r'(?:không|chưa)\s+(?:\S+\s+){0,3}$')     # "không cộng, trừ hay so với", "không tính chênh lệch"
_NEG_WORD = re.compile(r'(?<!\w)(?:không|chưa)(?!\w)')
_TURN_WORD = re.compile(r'(?<!\w)(?:nhưng|còn|trong khi|tuy nhiên|song)(?!\w)')   # phủ định không vắt qua chữ đổi ý
_CLAUSE_CUT = re.compile(r'[,;:()—–]')
_PAST_YEAR = re.compile(r'(?<!\d)(?:201[2-9]|202[0-2])(?!\d)')    # năm có số thực tế (2012-07-04 → 2022-12-31)


def _number_kind(path: str, fld: str, results: dict) -> str | None:
    """'du_bao': số dự báo của get_forecast; 'thuc_te': số của tool số liệu lịch sử. Số backtest không thuộc loại nào."""
    res = results.get(path.split('.')[0])
    tool = res.evidence.tool if res is not None and res.evidence is not None else ''
    if tool == 'get_forecast':
        return 'du_bao' if fld in FORECAST_FIELDS else None
    return 'thuc_te' if tool and not tool.startswith('get_forecast') and fld in FIELD_LABEL else None


def _negated(before: str) -> bool:
    """Phần câu trước chữ so sánh có phủ định cho chính chữ đó: "không" ở đầu vế ("Không thể trả lời bằng phần trăm
    chênh lệch", live b7 K16), hoặc trong 3 chữ ngay trước kể cả qua dấu phẩy liệt kê ("không cộng, trừ hay so với").
    Không tính phủ định nằm trước "nhưng / còn…" ("không phải R, nhưng cao hơn thực tế" vẫn là phép so)."""
    seg = _TURN_WORD.split(before)[-1]
    return bool(_NEGATED.search(seg) or _NEG_WORD.search(_CLAUSE_CUT.split(seg)[-1]))


def _mix_compare(low: str) -> bool:
    """Câu có chữ so sánh / đổi không bị phủ định ("không so với" không phải một phép so)."""
    return any(not _negated(low[:m.start()]) for m in _MIX_CMP.finditer(low))


def _group_names(results: dict) -> set[str]:
    names = set()
    for res in results.values():
        if not res.ok:
            continue
        names |= {r['dimension_value'] for r in res.rows if isinstance(r.get('dimension_value'), str)}
        names |= {r[k] for r in res.rows for k in ('candidate', 'candidate_label') if isinstance(r.get(k), str)}
        for v in res.derived.values():
            if isinstance(v, dict) and isinstance(v.get('groups'), list):
                names |= {g for g in v['groups'] if isinstance(g, str)}
    return names


# B3: họ model viết thẳng trong câu ("LightGBM chính xác nhất") phải gắn với một ô đã dùng có tên họ đó
# (derived.primary.label, rows[<ứng viên>].candidate_label...); không thì model có thể gán sai số cho sai model.
# Mốc seasonal naive không nằm trong danh sách: câu giải thích luật chọn hay nhắc tới nó, và số của mốc vẫn qua nhãn app.
MODEL_FAMILY = {'LightGBM': r'lightgbm|lgbm', 'SARIMAX': r'sarimax', 'ARIMA': r'(?<![a-z])arima(?![a-z])',
                'bản gộp': r'bản gộp|blend'}
_LEVEL_PATH = re.compile(r'\.derived\.(?:lowest|highest)_')

# --- B3 (RV01–RV03, review Codex 2026-10-15): ràng buộc câu hỏi → tool → claim cho số dự báo ---
# Nhãn app tự gắn cạnh số chỉ BỘC LỘ mâu thuẫn; các kiểm dưới đây CHẶN câu sai. Câu hỏi là dữ liệu đầu vào của người
# dùng (không phải chỉ dẫn): chỉ đọc kỳ, loại số, model, thước xếp hạng được nêu tường minh.

_ACTUAL_Q = re.compile(r'thực tế|thực đạt|đã đạt', re.I)
_FORECAST_Q = re.compile(r'dự báo|dự kiến|dự đoán|(?<!\w)sẽ(?!\w)', re.I)
_MAPE_RX = re.compile(r'mape|sai số (?:tổng )?tháng|theo tháng|tổng tháng', re.I)
_SCORE_RX = re.compile(r'điểm ngày|điểm kết hợp|theo ngày|thước chọn|(?<!\w)mae(?!\w)', re.I)
_RANK_PATH = re.compile(r'\.derived\.lowest_(score|mape_g_thang)\.')
_HORIZON_PATH = re.compile(r'\.derived\.(?:horizon_total|highest_month|lowest_month)\.')
# B4b: nhận các cách gán nguyên nhân phổ biến; phủ định nhân quả có luật riêng bên dưới.
_CAUSAL = re.compile(r'\b(?:nguyên nhân là|là nguyên nhân|gây ra|gây nên|'
                     r'khiến\b(?!\s+(?:cho\s+)?(?:log\(\s*g\s*\)\s+)?dự báo\b)|dẫn đến|tạo ra|'
                     r'làm(?:\s+cho)?\s+(?:(?:tăng|giảm)\s+)?(?:g|doanh thu|giá vốn|cogs)\b'
                     r'(?!\s+dự báo\b)|'
                     r'(?:do|vì)\s+(?:hiệu ứng\s+)?(?:năm lẻ|urban blowout|khuyến mãi|marketing))\b')
_CAUSAL_TURN = re.compile(r'\b(?:nhưng|còn|trong khi|tuy nhiên|song|mà)\b|[,.;:!?]')
_CAUSAL_DENIAL = re.compile(r'\b(?:không|chưa)\s+(?:'
                            r'(?:(?:thể|đủ)\s+)?(?:kết luận|khẳng định|chứng minh|cho biết|cho thấy|biết|có bằng chứng)'
                            r'|(?:thể\s+)?đưa ra kết luận'
                            r'|đủ\s+(?:(?:cơ sở|bằng chứng|dữ liệu)\s+)?(?:để\s+)?(?:kết luận|nói|khẳng định)'
                            r'|phải\s+(?:là\s+)?(?:kết luận|bằng chứng)'
                            r'|thể\s+nói'
                            r'|có\s+(?:đủ\s+)?(?:cơ sở|bằng chứng|dữ liệu)\b(?:\s+để\s+(?:kết luận|nói|khẳng định))?'
                            r')\b')
_CAUSAL_NON_DENIAL = re.compile(r'\b(?:không|chưa)\s+(?:(?:thể|cần)\s+)?(?:phủ nhận|chỉ)\b')
_G_DECOMP_SCOPE = re.compile(r'\bphân rã\b(?:\s+\S+){0,8}\s+(?:cho|của)\s+(?:dự báo\s+)?'
                             r'(?:G\b|doanh thu gộp)|\bphân rã\s+(?:model\s+)?(?:dự báo\s+)?'
                             r'(?:G\b|doanh thu gộp)', re.I)
_G_DECOMP_UNAVAILABLE = re.compile(r'\b(?:không|chưa)\s+(?:có\s+)?phân rã\s+(?:model\s+)?'
                                 r'(?:G\b|doanh thu gộp)|\b(?:G\b|doanh thu gộp)\s+'
                                 r'(?:không|chưa)\s+có\s+phân rã', re.I)
_COGS_DECOMP_SCOPE = re.compile(r'\bphân rã\b(?:\s+\S+){0,8}\s+(?:cho|của)\s+'
                                r'(?:dự báo\s+)?(?:COGS\b|giá vốn)|\bphân rã\s+(?:model\s+)?'
                                r'(?:dự báo\s+)?(?:COGS\b|giá vốn)', re.I)


def _causal_denied(before: str) -> bool:
    """Chỉ bỏ qua khẳng định nhân quả khi chính vế đó từ chối kết luận; không mượn phủ định ở vế trước."""
    clause = _CAUSAL_TURN.split(before)[-1]
    if _CAUSAL_NON_DENIAL.search(clause):
        return False
    return bool(_CAUSAL_DENIAL.search(clause)
                or re.search(r'\b(?:không|chưa)(?:\s+\S+){0,2}\s*$', clause))
MODEL_CODE = {'LightGBM': 'lgbm', 'SARIMAX': 'sarimax', 'ARIMA': 'arima', 'bản gộp': 'blend'}


_MONTH_WORD = {'một': 1, 'giêng': 1, 'hai': 2, 'ba': 3, 'tư': 4, 'bốn': 4, 'năm': 5, 'sáu': 6, 'bảy': 7, 'tám': 8,
               'chín': 9, 'mười': 10, 'mười một': 11, 'mười hai': 12, 'chạp': 12}
_ROMAN_Q = {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4}


def _month_end_day(y: int, m: int) -> int:
    import calendar
    return calendar.monthrange(y, m)[1]


def _day(y, m, d):
    """datetime.date nếu ngày có thật và năm trong vùng hợp lý; None nếu không (RV09: không để ValueError thoát ra)."""
    import datetime as _dt
    try:
        return _dt.date(y, m, d) if 1900 <= y <= 2100 else None
    except (TypeError, ValueError):
        return None


def question_periods(question: str) -> list[tuple]:
    """Kỳ nêu tường minh trong câu hỏi. Ba dạng:
    - (năm, tháng, ngày), None = không nêu: một ngày, một tháng, một năm, hoặc "tháng 9" không năm (follow-up);
    - ('range', ngày đầu, ngày cuối, nhãn): quý, 6 tháng / nửa đầu, cuối năm, "từ tháng a đến tháng b". Tool không có
      grain này: chỉ dẫn được số của từng tháng / ngày nằm trọn trong khoảng, và câu phải nêu đúng tháng đó (RV07);
    - ('invalid', đoạn chữ): kỳ không có thật (quý 5, tháng 13, ngày 31/2, năm 0000) → hỏi lại, không dùng số kỳ khác (RV09).
    "từ 2019" trong tên model và "2020–2022" (kỳ backtest) không phải kỳ được hỏi. Hàm không ném lỗi với mọi chuỗi."""
    q = re.sub(r'(?:train\s+)?từ\s+2019|20(?:20|13)\s*[–-]\s*20\d\d', ' ', (question or '').lower())
    out = []

    def take(rx, conv):
        nonlocal q
        for m in re.finditer(rx, q):
            out.append(conv(m) or ('invalid', m[0].strip()))
        q = re.sub(rx, ' ', q)

    def one(y, m=None, d=None):
        # kiểm miền rồi mới trả kỳ; ngày có thật chỉ khi đủ năm/tháng/ngày
        y, m, d = (int(x) if x is not None else None for x in (y, m, d))
        if y is not None and not 1900 <= y <= 2100 or m is not None and not 1 <= m <= 12:
            return None
        if d is not None and _day(y or 2024, m or 1, d) is None:
            return None
        return (y, m, d)

    def span(y, m1, m2, label):
        y, m1, m2 = int(y), int(m1), int(m2)
        if not (1900 <= y <= 2100 and 1 <= m1 <= m2 <= 12):
            return None
        return ('range', _day(y, m1, 1), _day(y, m2, _month_end_day(y, m2)), label)

    def span2(y1, m1, y2, m2):
        # khoảng tháng vắt qua năm ("từ tháng 12/2022 đến tháng 2/2023", live B3c GM10): mọi tháng ở giữa đều được hỏi
        y1, m1, y2, m2 = int(y1), int(m1), int(y2), int(m2)
        if not (1900 <= y1 <= y2 <= 2100 and 1 <= m1 <= 12 and 1 <= m2 <= 12 and (y1, m1) <= (y2, m2)):
            return None
        return ('range', _day(y1, m1, 1), _day(y2, m2, _month_end_day(y2, m2)), f'{m1}/{y1}–{m2}/{y2}')

    words = '|'.join(sorted(map(re.escape, _MONTH_WORD), key=len, reverse=True))
    # một ngày: 1/8/2023, 2023-08-01, ngày 1 tháng 8 năm 2023
    take(r'(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)', lambda m: one(m[1], m[2], m[3]))
    take(r'(?<!\d)(\d{1,2})/(\d{1,2})/(\d{4})(?!\d)', lambda m: one(m[3], m[2], m[1]))
    take(r'ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+(?:năm\s+)?(\d{4})', lambda m: one(m[3], m[2], m[1]))
    take(r'(?:từ\s+)?(?:tháng\s+)?(?<![\d/])(\d{1,2})\s*/\s*(\d{4})\s*(?:đến|tới|→|-|–)\s*(?:hết\s+)?(?:tháng\s+)?'
         r'(\d{1,2})\s*/\s*(\d{4})(?!\d)', lambda m: span2(m[2], m[1], m[4], m[3]))
    # "cùng tháng / cùng kỳ năm 2022" là năm 2022, tháng lấy theo ngữ cảnh; không phải "tháng Năm" (tháng 5) 2022
    # (live B3c GM09). Dạng ('same_month', năm, None, nhãn): khớp số một tháng bất kỳ của năm đó
    take(r'cùng\s+(?:tháng|kỳ)\s+(?:của\s+)?năm\s+(\d{4})',
         lambda m: ('same_month', int(m[1]), None, f'cùng tháng năm {m[1]}') if 1900 <= int(m[1]) <= 2100 else None)
    # khoảng: quý N/yyyy, 6 tháng / nửa đầu, cuối năm, từ tháng a đến (tháng) b/yyyy. Quý viết "Q3/2023", "quý III/2023"
    # (review Claude 2026-10-17): trước đọc thành tháng 3/2023 / cả năm 2023, nên câu trả lời lặp lại "Q3/2023" kèm số
    # tháng 3 lọt; phải đứng trước dạng tháng m/yyyy
    def quarter(m):
        n = _ROMAN_Q.get(m[1]) or int(m[1])
        return span(m[2], 3 * n - 2, 3 * n, f'quý {n}/{m[2]}') if 1 <= n <= 4 else None

    take(r'(?:quý\s*|(?<!\w)q\s*)(\d+|(?:iv|i{1,3})(?!\w))\s*(?:/|-|năm)?\s*(\d{4})', quarter)
    take(r'(?:6 tháng|sáu tháng|nửa)\s+(đầu|cuối)\s+(?:năm\s+)?(\d{4})',
         lambda m: span(m[2], 1, 6, f'nửa đầu {m[2]}') if m[1] == 'đầu' else span(m[2], 7, 12, f'nửa cuối {m[2]}'))
    take(r'(?:từ\s+)?tháng\s+(\d{1,2})\s*(?:đến|tới|-|–)\s*(?:tháng\s+)?(\d{1,2})\s*(?:/|năm)?\s*(\d{4})',
         lambda m: span(m[3], m[1], m[2], f'tháng {int(m[1])}–{int(m[2])}/{m[3]}'))
    # một tháng: 8/2023, T8/2023, 2023-08, tháng 8 năm 2023, tháng 8 2023, tháng tám năm 2023
    take(r'(?<!\d)(\d{4})-(\d{1,2})(?![\d-])', lambda m: one(m[1], m[2]))
    take(r'(?:tháng\s+)?(?<![\d/])(\d{1,2})\s*/\s*(\d{4})(?!\d)', lambda m: one(m[2], m[1]))
    take(r'tháng\s+(\d{1,2})\s+(?:năm\s+)?(\d{4})', lambda m: one(m[2], m[1]))
    take(rf'tháng\s+({words})\s+(?:năm\s+)?(\d{{4}})', lambda m: one(m[2], _MONTH_WORD[m[1]]))
    # một năm; tháng không năm (follow-up)
    take(r'năm\s+(\d{4})|(?<![\d.,])(20\d\d)(?![\d.,])', lambda m: one(m[1] or m[2]))
    take(r'tháng\s+(\d{1,2})(?!\d)', lambda m: one(None, m[1]))
    return out


def _spec_label(x: tuple) -> str:
    if x[0] in ('range', 'same_month'):
        return x[3]
    if x[0] == 'invalid':
        return f'{x[1]} (không hợp lệ)'
    return '/'.join(str(v) for v in (x[2], x[1], x[0]) if v is not None)


def _claim_period(row: dict | None) -> tuple | None:
    if not row or row.get('year') is None:
        return None
    d = row.get('forecast_date')
    return int(row['year']), row.get('month'), (d.day if d is not None and hasattr(d, 'day') else row.get('day'))


def _period_match(spec: tuple, got: tuple | None) -> bool:
    if got is None:
        return False
    gy, gm, gd = got
    if spec[0] == 'invalid':
        return False
    if spec[0] == 'same_month':
        return gy == spec[1] and gm is not None and gd is None
    if spec[0] == 'range':
        import datetime as _dt
        if gm is None:
            return False                     # số cả năm không nằm trọn trong quý / nửa năm
        first = _dt.date(gy, gm, gd or 1)
        last = _dt.date(gy, gm, gd or _month_end_day(gy, gm))
        return spec[1] <= first and last <= spec[2]
    sy, sm, sd = spec
    if (sm is None) != (gm is None) or (sd is None) != (gd is None):
        return False                         # khác grain: hỏi tháng mà dẫn số cả năm (R01) và ngược lại
    return (sy is None or sy == gy) and (sm is None or sm == gm) and (sd is None or sd == gd)


def question_model(question: str) -> dict:
    """Model / cửa sổ / cách COGS người hỏi nêu đích danh."""
    q, want = question or '', {}
    fam = [code for f, code in MODEL_CODE.items() if re.search(MODEL_FAMILY[f], q, re.I)]
    if len(fam) == 1:
        want['family'] = fam[0]
    if re.search(r'toàn chuỗi', q, re.I):
        want['window'] = 'full'
    elif re.search(r'(?:train\s+)?từ\s+2019', q, re.I):
        want['window'] = '2019'
    if re.search(r'qua tỷ lệ', q, re.I):
        want['cogs'] = 'ratio'
    elif re.search(r'(?:cogs|giá vốn)[^.?!]{0,20}trực tiếp|dự báo trực tiếp', q, re.I):
        want['cogs'] = 'direct'
    return want


def _cand_matches(candidate: str, want: dict) -> bool:
    model, _, cogs = candidate.partition('/')
    return ((not want.get('family') or model.startswith(want['family']))
            and (not want.get('window') or model.endswith('_' + want['window']))
            and (not want.get('cogs') or cogs == want['cogs']))


def _names_period(text: str, row: dict) -> bool:
    """Câu có nêu đúng kỳ của dòng (tháng / ngày) không: "tháng 8", "8/2023", "01/08/2023"..."""
    y, m, d = row.get('year'), row.get('month'), row.get('forecast_date')
    pats = [rf'tháng\s+0?{m}(?!\d)', rf'(?<![\d/])0?{m}\s*/\s*{y}']
    if d is not None and hasattr(d, 'day'):
        pats = [rf'(?<!\d)0?{d.day}\s*/\s*0?{m}(?!\d)', rf'ngày\s+0?{d.day}(?!\d)']
    return any(re.search(p, text, re.I) for p in pats)


_AGG_WORD = re.compile(r'tổng|cả quý|toàn quý|cả nửa|cả \d+ tháng|cả kỳ|cộng lại|gộp', re.I)
_NOT_AGG = re.compile(r'doanh thu gộp|bản gộp', re.I)


def invalid_period_errors(question: str, values: dict) -> list[str]:
    """RV09, RV10: câu hỏi nêu kỳ không có thật (quý 5, tháng 13, ngày 31/2...) thì không trả số của kỳ nào, kể cả tool
    không phải dự báo. Áp cho MỌI trạng thái có claim số: câu hỏi lại / từ chối kèm số kỳ khác cũng bị chặn (RV10);
    hỏi lại không dẫn số vẫn được."""
    if (bad_specs := [x[1] for x in question_periods(question or '') if x[0] == 'invalid']) and values:
        return [f'câu hỏi nêu kỳ không hợp lệ ({", ".join(bad_specs[:3])}): trả status "needs_clarification" hỏi lại '
                'kỳ, không dùng số của kỳ khác (kể cả trong câu hỏi lại)']
    return []


# RV12 lượt 2 (2026-10-16): vùng dự báo, chữ gọi vùng dự báo, chữ phủ định kỳ được hỏi, kỳ tương đối, trường số lệch kỳ
_FC_START, _FC_END = (_date.fromisoformat(d) for d in cat.FORECAST_HORIZON)
_HORIZON_NAME = re.compile(r'vùng dự báo|kỳ dự báo|cả vùng|toàn (?:bộ )?(?:vùng|kỳ)|18 tháng|548 ngày', re.I)
# kỳ tương đối ("năm trước đó", "cùng tháng năm trước", "tháng này"): không đối chiếu được bằng chữ số (phát lại live)
_REL = re.compile(r'năm (?:trước|ngoái)|cùng (?:kỳ|tháng) năm (?:trước|ngoái)|tháng (?:này|trước)|năm nay|kỳ này', re.I)
_CONJ = re.compile(r'\s(?:và|còn|nhưng|trong khi)\s', re.I)
# RV12 lượt 5 (PM chọn 2026-10-16): câu trả lời khác ok có số của kỳ khác kỳ được hỏi thì app tự dựng câu dẫn số theo
# khuôn (reference_answer). Lượt 2–4 kiểm chữ phủ định trong câu mô hình viết; mỗi lượt vá lại dời lỗ sang chỗ khác
# (review §9.9: 17 câu từ chối đúng bị chặn, 9 câu gán sai vẫn lọt). Câu của mô hình chỉ được giữ khi không có chữ số,
# chỗ đặt, kỳ tương đối, hay chữ trỏ / dùng / phỏng đoán số; bỏ nhầm một câu chỉ mất lời, không mất số.
_DATA_START, _DATA_END = _date(2012, 7, 4), _date(2022, 12, 31)          # dữ liệu thực tế (CLAUDE.md §1)
_MODEL_DROP = re.compile(r'\d|\{c\d+\}|' + _REL.pattern + r'|năm (?:sau|tới|kế)|sang năm'
                         r'|(?:(?:con\s+)?số|mức|giá trị|tổng|kết quả)\s+(?:này|đó|trên|dưới|kia)(?!\w)'
                         r'|tương tự|tương đương|tương đồng|xấp xỉ|quanh mức|ước (?:tính|lượng|chừng)|kỳ vọng|giả định'
                         r'|có lẽ|khả năng|(?<!\w)(?:chắc|sẽ|giống|gần như|na ná)(?!\w)|không khác'
                         r'|(?<!\w)(?:dùng|lấy|áp dụng|coi)(?!\w)|(?<!\w)thay\s+(?:cho|thế|vào)(?!\w)', re.I)
_TAIL_SENT = re.compile(r'(?:nếu|bạn có thể|bạn muốn|bạn cần|hãy)(?!\w)', re.I)       # câu hỏi lại / gợi ý: để cuối
_CONNECTIVE = re.compile(r'(?:ngoài ra|thêm vào đó|hơn nữa|bên cạnh đó|đồng thời|cũng)(?!\w)', re.I)   # câu nối: cần câu mở
_DIM_WORD = {'category': 'ngành', 'region': 'vùng', 'acquisition_channel': 'kênh'}
REF_HEADER = 'Số tham khảo, không phải số bạn hỏi:'
ASKED_HEADER = 'Số đúng kỳ trong câu hỏi:'                            # B7 S1b, xem reference_answer
_REF_ASK = re.compile(r'tham khảo|(?<!\w)mốc(?!\w)', re.I)             # người hỏi tự xin số làm mốc tham khảo (rv12f)
_GROUP_Q = re.compile(r'(?<!\w)(?:ngành|vùng(?!\s+dự báo)|khu vực|kênh|nhóm|category|region|channel)(?!\w)', re.I)
_PRIOR = {'r_prior_year', 'r_same_month_prior_year'}            # số của cùng kỳ năm trước so với dòng
_CHANGE = re.compile(r'^delta_|yoy|change|contribution|shift')   # so kỳ của dòng với cùng kỳ năm trước: thuộc cả hai kỳ
_SHIFTED = re.compile(r'before|after|_start$|_end$')            # r_12m_before, r_start...: kỳ không suy được từ dòng
_REF_DERIVED = re.compile(r'\.derived\.(horizon_total|highest_month|lowest_month)\.')


@dataclass(frozen=True)
class _Ref:
    """Số tham khảo của kỳ KHÁC kỳ được hỏi: nhãn kỳ thật, các kỳ (năm, tháng, ngày) của số, tổng cả vùng dự báo hay không,
    có phải số "năm trước" của dòng (r_prior_year...: "năm trước đó là {cX}" được coi là đã ghi kỳ)."""
    label: str
    gots: tuple
    horizon: bool = False
    kind: str = 'dự báo'
    prior: bool = False


def _value_gots(tool: str, fld: str, row: dict | None) -> tuple:
    """Các kỳ (năm, tháng, ngày) mà một ô số đo thuộc về, theo metadata của dòng; () nếu không xác định (không kiểm).
    Ô năm / tháng / số đếm không phải số đo của kỳ ("Hôm nay là năm {c1}", phát lại live H02b)."""
    got = _claim_period(row)
    if got is None or tool == 'get_forecast_backtest' or fld not in MONEY | PRICE | RATE | PCT100 | PP | PP_FRAC | INDEX:
        return ()
    if tool == 'get_forecast':
        return (got,) if fld in FORECAST_FIELDS else ()
    y, m, d = got
    if fld in _PRIOR:
        return ((y - 1, m, d),)
    if _SHIFTED.search(fld):
        return ()
    return ((y, m, d), (y - 1, m, d)) if _CHANGE.search(fld) else (got,)


def _spec_years(s: tuple) -> set:
    if s[0] == 'range':
        return set(range(s[1].year, s[2].year + 1))
    if s[0] == 'same_month':
        return {s[1]}
    return set() if s[0] in (None, 'invalid') else {s[0]}


def _years_of(specs: list) -> set:
    return set().union(*map(_spec_years, specs)) if specs else set()


def _overlaps_horizon(s: tuple) -> bool:
    if s[0] == 'range':
        return s[1] <= _FC_END and _FC_START <= s[2]
    if s[0] == 'same_month':
        return _FC_START.year <= s[1] <= _FC_END.year
    y, m, d = s
    if y is None:
        return False
    lo = _date(y, m or 1, d or 1)
    hi = _date(y, m or 12, d or _month_end_day(y, m or 12))
    return lo <= _FC_END and _FC_START <= hi


def _contains(s: tuple, g: tuple) -> bool:
    """Kỳ ghi s chứa kỳ của số g (năm chứa tháng của nó): luật kỳ ghi sai không đòi đúng grain."""
    if s[0] in ('range', 'same_month'):
        return _period_match(s, g)
    return all(a is None or a == b for a, b in zip(s, g))


_YEAR_FIELDS = {'year', 'start_year', 'end_year', 'turning_year', 'first_year', 'last_year'}


def _with_years(answer: str, values: dict) -> str:
    """Chỗ đặt trỏ ô năm ("năm gần nhất có dữ liệu là {c1}: R đạt {c2}") thay bằng chữ "năm YYYY" để luật kỳ đọc được kỳ
    câu ghi (phát lại live H02b); chỉ dùng để kiểm, không đổi câu hiện ra."""
    for cid, (path, v, _s) in values.items():
        if path.rsplit('.', 1)[-1] in _YEAR_FIELDS and isinstance(v, int) and not isinstance(v, bool):
            answer = (answer or '').replace('{' + cid + '}', f'năm {v}')
    return answer


def _periods(text: str) -> list:
    return [x for x in question_periods(_PLACEHOLDER.sub(' ', text)) if x[0] != 'invalid']


def _positions(clause: str):
    """Mỗi chỗ đặt trong vế: (id, phần dẫn từ chỗ đặt trước đó, phần đuôi tới chỗ đặt sau / chữ nối, đầu vế, thứ tự)."""
    ms = list(_PLACEHOLDER.finditer(clause))
    for k, m in enumerate(ms):
        lead = clause[ms[k - 1].end() if k else 0:m.start()]
        tail = _CONJ.split(clause[m.end():ms[k + 1].start() if k + 1 < len(ms) else len(clause)], maxsplit=1)[0]
        yield m[1], (lead, tail, clause[:m.start()], k)


def _said(clauses: list, i: int, pos: tuple, horizon: bool, cross: bool, stop_rel: bool = True) -> tuple:
    """Kỳ mà câu gán cho một chỗ đặt: (các kỳ ghi, có kỳ tương đối, có chữ gọi vùng dự báo). Tìm lần lượt ở phần dẫn ngay
    trước chỗ đặt, phần đuôi ngay sau, rồi (cross=True) đầu vế và các vế phía trước; cross=False dừng ở chỗ đặt khác.
    stop_rel=False: chữ kỳ tương đối không dừng việc tìm ("..., so năm trước giảm {c3}": kỳ của số thay đổi là kỳ ghi
    phía trước). Tháng không năm lấy năm ghi gần nhất phía trước trong câu ("Riêng năm 2023, tháng 8 là {c1}")."""
    lead, tail, head, k = pos
    # "{c1} cho tháng 01/2023 và {c2} cho tháng 02/2023": kỳ trong lead của c2 thuộc c1;
    # kỳ ngay sau c2 mới là kỳ của c2. Chỉ ưu tiên đuôi khi có chữ nối và đuôi tự nêu kỳ.
    near = [tail, lead] if k and _CONJ.search(lead) and _periods(tail) else [lead, tail]
    cands = near + ([head] + clauses[:i][::-1] if cross else [] if k else clauses[:i][::-1])
    for n, text in enumerate(cands):
        if n >= 2 and not cross and _PLACEHOLDER.search(text):
            break
        said, rel, hz = _periods(text), bool(_REL.search(text)), horizon and bool(_HORIZON_NAME.search(text))
        if said or (rel and stop_rel) or hz:
            if any(s[0] is None for s in said):
                ys = [s[0] for s in _periods(' '.join(clauses[:i] + [head])) if isinstance(s[0], int)]
                said = [(ys[-1], *s[1:]) if s[0] is None and ys else s for s in said]
            return said, rel, hz
    return [], False, False


def _ref_named(ref: _Ref, said: list, rel: bool, hz: bool, q_years: set) -> bool:
    """Câu có ghi đúng kỳ thật của số tham khảo không. Tổng vùng dự báo: có chữ gọi vùng dự báo và mọi kỳ ghi kèm nằm
    trong vùng. Còn lại: ít nhất một kỳ ghi khớp kỳ của số và không kỳ ghi nào là kỳ được hỏi; tháng không ghi năm
    ("tháng 8") không đủ khi câu hỏi nêu năm khác năm của số (hỏi 2025, "dự báo tháng 8 là..." đọc thành tháng 8/2025);
    kỳ tương đối ("năm trước đó") chỉ đủ cho số "năm trước" của dòng."""
    if ref.horizon:
        return hz and all(_overlaps_horizon(s) for s in said)
    if not said:
        return rel and ref.prior
    years = {g[0] for g in ref.gots}
    hits = [s for s in said if any(_period_match(s, g) for g in ref.gots) and not (s[0] is None and q_years - years)]
    return bool(hits) and not any(s not in hits and _spec_years(s) & q_years for s in said)


def reference_refs(question: str, values: dict, results: dict) -> tuple[list, dict]:
    """RV12: số không bao phủ mọi kỳ trong câu hỏi → app dẫn theo khuôn ở câu khác ok. Câu hỏi có thể vừa hỏi kỳ thiếu
    số vừa xin kỳ tham khảo; việc claim khớp kỳ tham khảo không được tắt khuôn cho kỳ thiếu số. Gồm số dự báo derived và
    số thực tế có năm."""
    specs = [x for x in question_periods(question or '') if x[0] != 'invalid']
    q_hz = bool(_HORIZON_NAME.search(question or ''))
    other, cands = {}, {}
    for cid, (path, _v, _s) in values.items():
        res = results.get(path.split('.')[0])
        if res is None or not res.ok or res.evidence is None:
            continue
        try:
            _, fld, row = _resolve(path, results)
        except ValueError:
            continue
        tool = res.evidence.tool
        if tool == 'get_forecast' and (m := _REF_DERIVED.search(path)):
            d = res.derived.get(m[1]) or {}
            if m[1] == 'horizon_total':
                spans = [_spec_span(s) for s in specs]
                partly_outside = any(sp is not None and (sp[0] < _FC_START or sp[1] > _FC_END) for sp in spans)
                if partly_outside or (not q_hz and not any(
                        s[0] == 'range' and s[1] <= _FC_START and _FC_END <= s[2] for s in specs)):
                    other[cid] = _Ref(f'vùng dự báo {_FC_START.isoformat()} → {_FC_END.isoformat()}', (), True)
                continue
            gots = tuple((int(p[3:]), int(p[:2]), None) for p in d.get('months', []) if re.fullmatch(r'\d\d/\d{4}', p))
            if gots:
                cands[cid] = _Ref(', '.join(d['months']), gots)
            continue
        if gots := _value_gots(tool, fld, row):
            fc = tool == 'get_forecast'
            cands[cid] = _Ref(row.get('period') if fc else ' / '.join(map(_spec_label, gots)), gots,
                              kind='dự báo' if fc else 'thực tế', prior=fld in _PRIOR)
    # Có kỳ được hỏi thiếu số (hoặc là khoảng: tool không có tổng khoảng) → mọi số là số tham khảo: số khớp kỳ tham khảo
    # không được tắt khuôn cho kỳ thiếu số (rv12f). Mọi kỳ được hỏi đều có số → chỉ số của kỳ KHÁC là số tham khảo
    # (B7 S1b, live b7 K17: "cộng G thực tế 2021 với G dự báo 2024" có đủ số hai kỳ, chỉ phép cộng là chưa hỗ trợ).
    have = [g for r in cands.values() for g in r.gots]
    gap = any(s[0] == 'range' or not any(_period_match(s, g) for g in have) for s in specs)
    for cid, r in cands.items():
        if not specs or gap or not any(_period_match(s, g) for s in specs for g in r.gots):
            other[cid] = r
    return specs, other


def _asked_specs(path: str, results: dict, specs: list) -> list:
    """[(kỳ được hỏi, loại số)] mà số ở path là số đúng kỳ và đúng loại: số thực tế cho kỳ chạm dữ liệu thực tế, số dự
    báo cho kỳ chạm vùng dự báo (năm 2024 chỉ có tới 01/07, nhãn của số tự ghi phần có dự báo). Số cả vùng / tháng cao,
    thấp nhất vùng dự báo không tính. Kỳ được hỏi là khoảng (quý, nửa năm…) không tính: tool không có tổng khoảng, số một
    tháng trong khoảng không phải số được hỏi (phát lại live E38 "R quý 2 năm 2019")."""
    res = results.get(path.split('.')[0])
    if res is None or not res.ok or res.evidence is None or _REF_DERIVED.search(path):
        return []
    try:
        _, fld, row = _resolve(path, results)
    except ValueError:
        return []
    fc = res.evidence.tool == 'get_forecast'
    gots = _value_gots(res.evidence.tool, fld, row)
    lo, hi = (_FC_START, _FC_END) if fc else (_DATA_START, _DATA_END)
    return [(s, 'dự báo' if fc else 'thực tế') for s in specs
            if s[0] != 'range' and (sp := _spec_span(s)) is not None and sp[0] <= hi and lo <= sp[1]
            and any(_period_match(s, g) for g in gots)]


def _unnamed_period_errors(answer: str, other: dict, specs: list) -> list[str]:
    """other: chỗ đặt → _Ref của các số KHÔNG thuộc kỳ được hỏi. Câu phải ghi kỳ thật của số ngay ở chỗ đặt (RV12; số của
    lượt trước trong câu hỏi so sánh, live B3c GM09)."""
    errs, q_years = [], _years_of(specs)
    for sent in _SENTENCE.split(answer or ''):
        clauses = re.split(r'[,:]', sent)
        for i, clause in enumerate(clauses):
            for cid, pos in _positions(clause):
                if cid not in other:
                    continue
                ref = other[cid]
                if not _ref_named(ref, *_said(clauses, i, pos, ref.horizon, cross=True, stop_rel=ref.prior), q_years):
                    asked = ', '.join(_spec_label(x) for x in specs) or 'không nêu kỳ'
                    errs.append(f'câu "{sent.strip()[:80]}" dẫn số {ref.kind} của {ref.label} nhưng không ghi rõ kỳ '
                                f'đó (câu hỏi về {asked}): số kỳ khác chỉ được nêu kèm đúng kỳ của nó, có năm, vd. "riêng '
                                f'{ref.label}, {ref.kind} G là {{{cid}}}"; không gán cho kỳ được hỏi')
    return errs


def stated_period_errors(values: dict, results: dict, answer: str = '') -> list[str]:
    """RV12 ("mọi trạng thái có claim số"), áp cả status ok: kỳ câu ghi ngay ở chỗ đặt (phần dẫn / đuôi, hoặc vế phía
    trước không có chỗ đặt khác) phải chứa kỳ của số theo dòng dữ liệu. "R năm 2019 là {c1}" với số của 2018 bị chặn,
    thay vì chỉ hiện nhãn (R, 2018) cạnh câu sai. Câu không ghi kỳ, hoặc ghi kỳ tương đối ("tháng này", "năm trước
    đó"): app vẫn tự gắn nhãn kỳ."""
    gots_of = {}
    for cid, (path, _v, _s) in values.items():
        res = results.get(path.split('.')[0])
        if res is None or not res.ok or res.evidence is None:
            continue
        try:
            _, fld, row = _resolve(path, results)
        except ValueError:
            continue
        if gots := _value_gots(res.evidence.tool, fld, row):
            gots_of[cid] = gots
    errs, answer = [], _with_years(answer, values)
    for sent in _SENTENCE.split(answer or ''):
        clauses = re.split(r'[,:]', sent)
        for i, clause in enumerate(clauses):
            for cid, pos in _positions(clause):
                if cid not in gots_of:
                    continue
                said, _rel, _hz = _said(clauses, i, pos, False, cross=False)
                if said and not any(_contains(s, g) for s in said for g in gots_of[cid]):
                    errs.append(f'câu "{sent.strip()[:80]}" ghi {", ".join(map(_spec_label, said))} cho {{{cid}}} nhưng '
                                f'số đó là của {" / ".join(map(_spec_label, gots_of[cid]))}: ghi đúng kỳ của số, hoặc '
                                'gọi tool đúng kỳ được hỏi; không gán số kỳ này cho kỳ khác')
    return errs


def _spec_text(s: tuple) -> str:
    if s[0] in ('range', 'same_month'):
        return s[3]
    y, m, d = s
    return f'ngày {d}/{m}/{y}' if d else f'tháng {m}/{y}' if m else f'năm {y}'


def _spec_span(s: tuple):
    """(ngày đầu, ngày cuối) của kỳ được hỏi; None nếu không chắc (thiếu năm, "cùng tháng năm X")."""
    if s[0] == 'range':
        return s[1], s[2]
    if not isinstance(s[0], int):
        return None
    y, m, d = s
    return _date(y, m or 1, d or 1), _date(y, m or 12, d or _month_end_day(y, m or 12))


def _coverage_line(question: str, specs: list, has_actual: frozenset = frozenset()) -> str:
    """Nêu riêng các kỳ đọc chắc và nằm trọn ngoài vùng; kỳ khác trong cùng câu hỏi không bị gọi nhầm là ngoài vùng.
    Kỳ nằm trong vùng (lý do là grain, nhóm, chỉ tiêu: B02, B03, E08) không có câu này. has_actual (B7 S1b): kỳ đã
    có số thực tế trong câu trả lời không bị gọi là "ngoài vùng dự báo" (live b7 K17: hỏi G thực tế năm 2021)."""
    fc = bool(_FORECAST_Q.search(question or ''))
    lo, hi = (_FC_START, _FC_END) if fc else (_DATA_START, _DATA_END)
    outside = [s for s in specs if (sp := _spec_span(s)) is not None and (sp[1] < lo or sp[0] > hi)
               and not (fc and s in has_actual)]
    if not outside:
        return ''
    ky = ' và '.join(dict.fromkeys(map(_spec_text, outside)))
    vung = f'{"vùng dự báo" if fc else "dữ liệu thực tế"} ({lo:%d/%m/%Y} → {hi:%d/%m/%Y})'
    return (f'{ky[0].upper()}{ky[1:]} nằm ngoài {vung}, nên chưa có {"dự báo" if fc else "số thực tế"} cho '
            f'{"các kỳ này" if len(outside) > 1 else "kỳ này"}.')


def _period_text(p) -> str:
    t = str(p)
    if re.fullmatch(r'\d{4}', t):
        return f'năm {t}'
    if re.fullmatch(r'\d{1,2}/\d{4}', t):
        return f'tháng {t}'
    if m := re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', t):
        return f'ngày {m[3]}/{m[2]}/{m[1]}'
    return t


def _ref_line(path: str, v, results: dict) -> str:
    """Một dòng khuôn "- Kỳ, nhóm: chỉ tiêu là **số** (phần thêm)", nhãn lấy từ dòng dữ liệu; '' nếu ô không phải số đo
    (năm, tên). Số đo thiếu nhãn chỉ tiêu / kỳ: ValueError (không hiện số không nhãn)."""
    _, fld, row = _resolve(path, results)
    if not _is_num(v) or fld in _YEAR_FIELDS or fld == 'month':
        return ''
    name, group, year, extra = _label_parts(fld, row)
    if m := _REF_DERIVED.search(path):
        d = results[path.split('.')[0]].derived.get(m[1]) or {}
        if m[1] == 'horizon_total':
            ky, name = f'cả vùng dự báo {_FC_START:%d/%m/%Y} → {_FC_END:%d/%m/%Y}', name and f'tổng {name}'
        else:
            ky = 'tháng ' + ', '.join(d.get('months', [])) if d.get('months') else ''
            name = name and f'{name}, tháng {"cao" if m[1] == "highest_month" else "thấp"} nhất vùng dự báo'
    else:
        ky = _period_text(year) if year is not None else ''
    if name is None or not ky:
        raise ValueError(f'{path}: app chưa dựng được nhãn chỉ tiêu / kỳ cho số này nên không dẫn được; bỏ số này')
    if group is None:
        group = 'toàn công ty'
    elif row and row.get('dimension_value') and row.get('dimension_name') in _DIM_WORD:
        group = f"{_DIM_WORD[row['dimension_name']]} {group}"
    tail = f' ({"; ".join(extra)})' if extra else ''
    return f'- {ky[0].upper()}{ky[1:]}, {group}: {name} là **{_fmt(v, fld, False)}**{tail}'


def _model_sentences(answer: str) -> tuple[list, list]:
    """Câu của mô hình được giữ: (câu dẫn, câu hỏi lại / gợi ý). Bỏ mọi câu có chữ số, chỗ đặt, kỳ tương đối, chữ trỏ /
    dùng / phỏng đoán số (_MODEL_DROP)."""
    lead, tail = [], []
    for t in re.findall(r'[^.!?\n]+[.!?]*', (answer or '').replace('**', '')):
        t = t.strip().lstrip('-*•').strip()
        if len(re.findall(r'[^\W\d_]+', t)) < 3 or _MODEL_DROP.search(t):        # mẩu cắt câu (").") hoặc câu bị bỏ
            continue
        t = t if t[-1] in '.!?' else t + '.'
        (tail if t.endswith('?') or _TAIL_SENT.match(t) else lead).append(t)
    return lead, tail


def reference_answer(question: str, status: str, answer: str, values: dict, results: dict) -> tuple:
    """RV12 lượt 5: câu trả lời khác ok có số của kỳ khác kỳ được hỏi → (markdown do app dựng, lỗi); (None, []) nếu không
    có số kỳ khác. Khuôn: [câu ngoài vùng, nếu chắc] + câu dẫn của mô hình (đã lọc) → "Số tham khảo, không phải số bạn
    hỏi:" + mỗi số một dòng có kỳ, nhóm, chỉ tiêu do app ghi → câu hỏi lại / gợi ý của mô hình (đã lọc). Mô hình không
    còn tự viết câu chứa số kỳ khác, nên không gán được số đó cho kỳ được hỏi."""
    specs, other = reference_refs(question, values, results)
    if not other:
        return None, []
    lines, asked, errs, seen, has_actual = [], [], [], set(), set()
    # số đúng kỳ được hỏi, đúng loại số của kỳ đó (thực tế tới 2022, dự báo trong vùng dự báo): mục riêng, không xếp vào
    # "không phải số bạn hỏi" (B7 S1b). Giữ khuôn cũ khi câu hỏi xin số "tham khảo / mốc" (rv12f) hoặc lọc nhóm (B03:
    # số toàn công ty đúng kỳ vẫn không phải số của vùng được hỏi)
    split = bool(specs) and not _REF_ASK.search(question or '') and not _GROUP_Q.search(question or '')
    for cid, (path, v, _s) in values.items():
        if path in seen:
            continue
        seen.add(path)
        try:
            line = _ref_line(path, v, results)
        except ValueError as e:
            errs.append(f'{cid}: {e}')
            continue
        hits = _asked_specs(path, results, specs)
        has_actual |= {s for s, kind in hits if kind == 'thực tế'}
        if line:
            (asked if split and hits else lines).append(line)
    if errs:
        return None, errs
    lead, tail = _model_sentences(answer)
    cover = _coverage_line(question, specs, frozenset(has_actual))
    head = [cover] if cover else lead            # có câu "ngoài vùng" thì câu dẫn của mô hình không thêm gì, chỉ thêm rủi ro
    if not head or _CONNECTIVE.match(head[0]):            # câu lý do chính có chữ số đã bị bỏ, còn lại câu "Ngoài ra..."
        head.insert(0, 'Câu hỏi cần nói rõ thêm trước khi có số đúng kỳ.' if status == 'needs_clarification'
                    else 'Chưa có số đúng như câu hỏi.')
    if not tail and status == 'needs_clarification':
        tail = ['Bạn muốn xem kỳ nào?']
    md = ' '.join(head) + (f'\n\n{ASKED_HEADER}\n\n' + '\n'.join(asked) if asked else '') + (
        f'\n\n{REF_HEADER}\n\n' + '\n'.join(lines) if lines else '')
    return md + ('\n\n' + ' '.join(tail) if tail else ''), []


_NOFC_Q = re.compile(r'(?:dự báo|dự kiến|dự đoán)\s+(?:\S+\s+){0,2}?(?:số đơn|đơn hàng|số khách|khách hàng|số món|'
                     r'lợi nhuận|biên lợi nhuận|doanh thu thuần|doanh thu thực nhận|(?-i:R)(?!\w))', re.I)
_COMPARE_Q = re.compile(r'so với|so sánh|cùng tháng|cùng kỳ|chênh', re.I)
_BACKTEST_MEASURE = {'score', 'mape_g_thang'}
_DEFINITION_Q = re.compile(r'là\s+gì|định\s+nghĩa|được\s+tính|tính[^.!?;\n]{0,40}thế\s+nào|'
                           r'what\s+is|what\s+does|define(?:d)?\b|definition\b|'
                           r'mean(?:ing)?\b|stand\s+for', re.I)
_DEFINITION_SUBSTITUTE = re.compile(
    r'không\s+có\s+mã\s+(?:\w+\s+)?riêng|tương\s+ứng\s+là|tương\s+đương|chính\s+là|'
    r'hay\s+còn\s+gọi|gần\s+với', re.I)
_UNKNOWN_DEFINITION = re.compile(r'chưa\s+có\s+định\s+nghĩa\s+cho\s+khái\s+niệm\s+này', re.I)
_AMBIGUOUS_DEFINITION = re.compile(r'(?<!\w)basket\s+size(?!\w)', re.I)
_AOV_AS_P = re.compile(r'\bAOV\s*(?:=|là)\s*(?:P\b|R\s*/\s*Q\b|giá\s+(?:thực\s+thu\s+)?'
                       r'(?:TB|trung\s+bình)\s+mỗi\s+món\b)', re.I)
_AOV_CHOT = re.compile(r'\bAOV\b[^.;!?]*\bđã\s+chốt\b', re.I)
_RULE10_DEFINITION_CODES = {'R', 'G', 'N', 'U', 'P', 'Q', 'C', 'F', 'AOV', 'G_forecast'}
_NUMERIC_DEFINITION_QUERY = re.compile(r'bao\s+nhiêu|\b(?:năm|tháng|kỳ)\s+\d', re.I)
_DEFINITION_FOLLOWUP = re.compile(r'\b(?:nó|(?:chỉ\s+số|con\s+số|mã)\s+(?:đó|này))\b', re.I)


def _asked_definition_codes(question: str) -> set[str]:
    """Mã viết nguyên dạng và aliases_vi là nguồn duy nhất để nhận mã được hỏi."""
    asked = set()
    for code, metric in cat.METRICS.items():
        if re.search(r'(?<!\w)' + re.escape(code) + r'(?!\w)', question or ''):
            asked.add(code)
            continue
        if any(re.search(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', question or '', re.I)
               for alias in metric['aliases_vi']):
            asked.add(code)
    # F có trong prompt nhưng chưa có trong catalog: nhận đúng mã để báo thiếu, không suy ra công thức.
    if re.search(r'(?<!\w)F(?!\w)', question or ''):
        asked.add('F')
    if 'G' in asked and re.search(r'(?<!\w)G\s+dự\s+báo\b', question, re.I):
        asked.remove('G')
        asked.add('G_forecast')
    return asked


def _explicit_definition_codes(question: str, asked: set[str]) -> set[str]:
    """Chỉ mã quy tắc 10 đứng sát cụm hỏi định nghĩa mới buộc đọc catalog."""
    explicit = set()
    for code in asked & _RULE10_DEFINITION_CODES:
        names = [code] + (cat.METRICS[code]['aliases_vi'] if code in cat.METRICS else [])
        if code == 'G_forecast':
            names.append('G dự báo')
        for name in names:
            token = r'(?<!\w)' + re.escape(name) + r'(?!\w)'
            strong_patterns = (
                rf'{token}\s+(?:là\s+gì|nghĩa\s+là\s+gì|(?:được\s+)?tính[^.!?;\n]{{0,40}}(?:thế\s+nào|ra\s+sao))',
                rf'(?:định\s+nghĩa|define|definition\s+of|what\s+is|what\s+does|công\s+thức(?:\s+tính)?)\s+{token}',
                rf'how\s+is\s+{token}[^.!?;\n]{{0,40}}\bdefined\b',
                rf'{token}\s+(?:mean|meaning|stand\s+for)\b',
            )
            weak_pattern = rf'cách\s+tính\s+{token}'
            if (any(re.search(pattern, question or '', re.I) for pattern in strong_patterns)
                    or (not _NUMERIC_DEFINITION_QUERY.search(question or '')
                        and re.search(weak_pattern, question or '', re.I))):
                explicit.add(code)
                break
    return explicit


def definition_question_errors(question: str, values: dict, results: dict, answer: str, status: str,
                               history: list[dict] | tuple = ()) -> list[str]:
    """Đối chiếu mã được hỏi với mã được dùng; không ánh xạ khái niệm sang mã khác."""
    asked = _asked_definition_codes(question)
    explicit = _explicit_definition_codes(question, asked)
    previous = history[-1].get('question', '') if history and isinstance(history[-1], dict) else ''
    if previous and _DEFINITION_FOLLOWUP.search(question or ''):
        inherited = _asked_definition_codes(previous)
        asked |= inherited
        if _DEFINITION_Q.search(question or '') and not _NUMERIC_DEFINITION_QUERY.search(question or ''):
            explicit |= inherited & _RULE10_DEFINITION_CODES
    definitions = {ref: res.rows[0].get('metric_id') for ref, res in results.items()
                   if res.ok and res.evidence and res.evidence.tool == 'get_metric_definition' and res.rows}
    cited_definition_refs = {ref for path, _value, _shown in values.values()
                             if (ref := path.split('.')[0]) in definitions}
    errs = []
    if _AMBIGUOUS_DEFINITION.search(question or ''):
        if status != 'needs_clarification' or definitions or not re.search(r'\?|bạn\s+muốn|ý\s+bạn', answer or '', re.I):
            errs.append('"basket size" có thể là U hoặc AOV; hỏi lại người dùng, không chọn mã thay')
        return errs
    # Nhánh này áp dụng theo hành vi trả lời: dùng định nghĩa Y để nối thay thế dù câu hỏi không hề nêu Y.
    if _DEFINITION_SUBSTITUTE.search(answer or ''):
        substituted = set(definitions.values()) - asked
        if substituted:
            errs.append(f'không dùng get_metric_definition({", ".join(sorted(substituted))}) để ánh xạ thay '
                        'khái niệm/mã không được hỏi')
    cited_unasked = {definitions[ref] for path, _value, _shown in values.values()
                     if path.rsplit('.', 1)[-1] in ('formula', 'unit', 'additivity')
                     and (ref := path.split('.')[0]) in definitions and definitions[ref] not in asked}
    clarifies_candidate = (status == 'needs_clarification'
                           and re.search(r'\?|bạn\s+muốn|ý\s+bạn', answer or '', re.I)
                           and any(re.search(r'(?<!\w)' + re.escape(code) + r'(?!\w)', answer or '')
                                   for code in cited_unasked))
    if cited_unasked and (status == 'ok' or status == 'needs_clarification' and not clarifies_candidate):
        errs.append('chưa có định nghĩa cho khái niệm này; hỏi lại hoặc liệt kê mã gần nhất '
                    'bằng đúng nhãn của mã đó, không dùng định nghĩa mã khác thay thế')
    if not asked:
        return errs
    for code in sorted(asked):
        if code not in cat.METRICS:
            if code not in explicit:
                continue
            unavailable = (status == 'unsupported' and not definitions
                           and re.search(r'\b(?:không|chưa|thiếu)\s+(?:có\s+)?định\s+nghĩa\s+'
                                         + re.escape(code) + r'\b', answer or '', re.I))
            if not unavailable:
                errs.append(f'catalog chưa có định nghĩa {code}; nói rõ không có định nghĩa, không dùng mã khác thay thế')
        elif code in explicit and ((status == 'ok' and code not in definitions.values())
                                   or cited_definition_refs and not any(definitions[ref] == code
                                                                         for ref in cited_definition_refs)):
            errs.append(f'câu hỏi định nghĩa {code} phải dẫn get_metric_definition({code}); '
                        'không dùng định nghĩa mã khác thay thế')
        if code == 'AOV':
            if _AOV_AS_P.search(answer or ''):
                errs.append('AOV là R / N (= U × P), không phải P = R / Q')
            if cat.METRICS['AOV']['decision_status'] != 'chot' and _AOV_CHOT.search(answer or ''):
                errs.append('AOV chưa có quyết định chốt riêng trong catalog; không gọi là "đã chốt"')
    return errs


def forecast_question_errors(question: str, values: dict, results: dict, answer: str = '',
                             context_periods: frozenset = frozenset()) -> list[str]:
    """Lỗi ràng buộc giữa câu hỏi và các claim của câu trả lời đã qua validate (RV01, RV03, RV07, RV09; live B3c).
    context_periods: kỳ (năm, tháng, ngày) của các lượt get_forecast ok ở lượt trước; câu hỏi so sánh tiếp nối
    ("vậy so với cùng tháng năm 2022 thực tế?") được dẫn lại số dự báo của kỳ đó khi vế câu ghi đúng kỳ."""
    used = []
    for path, _v, _s in values.values():
        res = results.get(path.split('.')[0])
        if res is None or not res.ok or res.evidence is None:
            continue
        try:
            _, fld, row = _resolve(path, results)
        except ValueError:
            continue
        used.append((path, fld, row, res.evidence.tool))
    fc = [u for u in used if u[3] == 'get_forecast' and (u[1] in FORECAST_FIELDS or _HORIZON_PATH.search(u[0]))]
    q, errs = question or '', []
    if any(r.ok and r.evidence and r.evidence.tool == 'explain_forecast' for r in results.values()):
        # Câu từ chối nhân quả được qua; phủ định một đối tượng khác không phủ định nguyên nhân ở vế sau.
        if any(not _causal_denied(sent[:m.start()]) for sent in _SENTENCE.split((answer or '').lower())
               for m in _CAUSAL.finditer(sent)):
            errs.append('phân rã model không chứng minh nguyên nhân; chỉ nêu đóng góp trong model')
        clauses = _SENTENCE.split(answer or '')
        explain_refs = [ref for ref, res in results.items() if res.ok and res.evidence
                        and res.evidence.tool == 'explain_forecast']
        for sent in clauses:
            if _PLACEHOLDER.search(sent) or not _EXPLAIN_REMAINDER_UNNUMBERED.search(sent):
                continue
            if len(explain_refs) != 1:
                errs.append('"nhóm/yếu tố/biến/thành phần khác/còn lại" không có số cần đúng một kết quả '
                            'explain_forecast; nói "{n} nhóm có ảnh hưởng dưới {threshold} mỗi nhóm"')
            elif not _explain_significant_cited(explain_refs[0], answer, values, results):
                errs.append('"nhóm/yếu tố/biến/thành phần khác/còn lại" cần dẫn đủ nhóm có ảnh hưởng lớn; '
                            'nói "{n} nhóm có ảnh hưởng dưới {threshold} mỗi nhóm"')
        for cid, (path, _v, _s) in values.items():
            res = results.get(path.split('.')[0])
            if res is None or res.evidence is None or res.evidence.tool != 'explain_forecast':
                continue
            if any('{' + cid + '}' in sent and (_said_metric(sent) == 'COGS'
                                               or re.search(r'log\(\s*COGS\s*\)', sent, re.I)) for sent in clauses):
                errs.append('số phân rã G bị gọi là phân rã COGS; không đổi chỉ tiêu của evidence')
                break
        if _said_metric(q) == 'COGS':
            if not any(re.search(r'\b(?:COGS|giá vốn)\b', sent, re.I)
                       and re.search(r'\b(?:không|chưa)\b', sent, re.I)
                       and re.search(r'phân rã|giải thích', sent, re.I) for sent in clauses):
                errs.append('chỉ có phân rã G; câu hỏi COGS phải nói rõ chưa có phân rã COGS')
            g_scope = False
            for sent in clauses:
                ids = _PLACEHOLDER.findall(sent)
                explain_ids = [cid for cid in ids if (item := values.get(cid))
                               and (res := results.get(item[0].split('.')[0])) is not None
                               and res.evidence and res.evidence.tool == 'explain_forecast']
                if explain_ids and not (re.search(r'\bG\b|doanh thu gộp|log\(G\)', sent, re.I) or g_scope):
                    errs.append('số phân rã G trong câu hỏi COGS phải được gọi rõ là của G')
                    break
                # Nhãn ở câu mở đầu chỉ áp dụng cho các câu sau; câu chứa số gán COGS vẫn bị chặn ở trên.
                if _G_DECOMP_SCOPE.search(sent) and not _G_DECOMP_UNAVAILABLE.search(sent):
                    g_scope = True
                elif _COGS_DECOMP_SCOPE.search(sent):
                    g_scope = False
        want = question_model(q)
        if want:
            selected = {row.get('candidate') for r in results.values() if r.ok and r.evidence
                        and r.evidence.tool == 'explain_forecast' for row in r.rows}
            if not any(_cand_matches(c, want) for c in selected if isinstance(c, str)):
                errs.append('câu hỏi nêu model khác nhưng phân rã chỉ thuộc model chính; không thay model')
        for sent in _SENTENCE.split(answer or ''):
            ids = _PLACEHOLDER.findall(sent)
            groups = {path.split('rows[', 1)[1].split(']', 1)[0] for cid in ids
                      if (item := values.get(cid)) and (path := item[0]).split('.')[0] in results
                      and results[path.split('.')[0]].evidence
                      and results[path.split('.')[0]].evidence.tool == 'explain_forecast' and 'rows[' in path}
            if len(groups) == 1 and re.search(r'các (?:nhóm|chương trình)[^.;]*?(?:còn lại|khác)', sent, re.I):
                errs.append('một ô đóng góp chỉ thuộc một nhóm biến; không gộp thành "các nhóm khác"')
            if groups and re.search(r'rõ nhất', sent, re.I):
                errs.append('phân rã không chứng minh nhóm "rõ nhất"; nêu thứ hạng theo độ lớn đóng góp nếu cần')
            if groups and re.search(r'các nhóm còn lại\s+góp\s+(?:dương|âm)', sent, re.I):
                errs.append('không gán cùng một chiều cho "các nhóm còn lại"; nêu chiều của từng nhóm')
            if any(not _negated_sum(sent, m.start()) for m in _SUM_WORD.finditer(sent)):
                pct_paths = {values[cid][0] for cid in ids if cid in values
                             and values[cid][0].endswith('.pct_vs_base')}
                if len(pct_paths) >= 2:
                    errs.append('% của từng nhóm nhân với nhau, không cộng')
            errs += _small_groups_errors(sent, answer, values, results)
    specs = question_periods(q)
    explain_used = [u for u in used if u[3] == 'explain_forecast' and u[2] is not None]
    if explain_used and specs and any(not any(_period_match(s, _claim_period(u[2])) for s in specs)
                                      for u in explain_used):
        errs.append('phân rã model dẫn từ ngày / tháng khác kỳ được hỏi; gọi explain_forecast đúng kỳ')
    # Câu hỏi vừa có kỳ thiếu dự báo vừa xin kỳ tham khảo: status ok có thể khiến
    # lời model gán lại số tham khảo cho kỳ thiếu số ở câu sau (RV12). Với trường
    # hợp này dùng no_data để app dựng số tham khảo theo kỳ lấy từ bằng chứng.
    # Kỳ trước vùng dự báo mà nằm trong dữ liệu thực tế không thiếu số: quy tắc 16 trả bằng số thực tế (B7: câu trộn
    # "G thực tế tháng 12/2021 và dự báo tháng 12/2023" trả hai phần, không ép no_data).
    spans = [sp for s in specs if (sp := _spec_span(s)) is not None]
    if (_FORECAST_Q.search(q)
            and any(sp[1] < _DATA_START or sp[0] > _FC_END for sp in spans)
            and any(_overlaps_horizon(s) for s in specs if s[0] != 'invalid')):
        errs.append('câu hỏi vừa có kỳ ngoài vùng vừa có kỳ tham khảo trong vùng dự báo: status "ok" không hợp lệ; '
                    'trả "no_data" để app ghi số tham khảo đúng kỳ')

    def in_specs(u) -> bool:
        """Số dự báo u thuộc kỳ được hỏi. Số cả vùng dự báo (derived) không có kỳ trên dòng (review Claude 2026-10-17:
        "tổng dự báo 2023–2024", "tháng nào cao nhất từ 2023 đến 2024" luôn bị chặn nhầm): tháng cao / thấp nhất cả vùng
        thuộc kỳ được hỏi khi mọi tháng đó nằm trong kỳ được hỏi (cao nhất cả vùng cũng là cao nhất của kỳ con chứa nó);
        tổng cả vùng chỉ khi các năm / khoảng được hỏi phủ trọn vùng dự báo VÀ mọi câu dẫn số gọi tên vùng dự báo (vùng
        dừng ở 01/07/2024 nên không phải tổng 2023–2024)."""
        if not (m := _REF_DERIVED.search(u[0])):
            return any(_period_match(s, _claim_period(u[2])) for s in specs)
        d = results[u[0].split('.')[0]].derived.get(m[1]) or {}
        if m[1] != 'horizon_total':
            gots = [(int(p[3:]), int(p[:2]), None) for p in d.get('months', []) if re.fullmatch(r'\d\d/\d{4}', p)]
            return bool(gots) and all(any(_contains(s, g) for s in specs) for g in gots)
        years = {s[0] for s in specs if isinstance(s[0], int) and s[1] is None}
        cover = (set(range(_FC_START.year, _FC_END.year + 1)) <= years
                 or any(s[0] == 'range' and s[1] <= _FC_START and _FC_END <= s[2] for s in specs))
        sents = [x for cid, (p, _v, _s) in values.items() if p == u[0]
                 for x in _SENTENCE.split(answer or '') if '{' + cid + '}' in x]
        return cover and bool(sents) and all(_HORIZON_NAME.search(_PLACEHOLDER.sub(' ', x)) for x in sents)

    errs += invalid_period_errors(q, values)
    if fc and (m := _NOFC_Q.search(q)):
        errs.append(f'câu hỏi hỏi "{m[0]}": chưa có dự báo chỉ tiêu này (dự báo chỉ có G và COGS toàn công ty); trả status '
                    '"unsupported", có thể nêu số dự báo G thay thế nhưng ghi rõ đó không phải chỉ tiêu được hỏi')
    # số dự báo được đưa ra làm số thực tế CỦA KỲ ĐƯỢC HỎI (hoặc câu không nêu kỳ); số dự báo kỳ khác xét ở luật kỳ dưới
    asked = [u for u in fc if not specs or in_specs(u)]
    if asked and _ACTUAL_Q.search(q) and not _FORECAST_Q.search(q):
        errs.append('câu hỏi hỏi số THỰC TẾ nhưng câu trả lời dẫn số DỰ BÁO: không đưa dự báo ra làm số thực tế; kỳ chưa '
                    'có số thực tế thì trả status "no_data" (có thể nói thêm là có số dự báo)')
    if fc and specs:
        bad = sorted({u[0] for u in fc if not in_specs(u)})
        if bad and _COMPARE_Q.search(q) and context_periods:
            # câu so sánh tiếp nối: số dự báo của kỳ lượt trước được dẫn lại nếu vế câu ghi đúng kỳ của nó
            prior = {p for p in bad for u in fc if u[0] == p and _claim_period(u[2]) in context_periods}
            other = {cid: _Ref(row.get('period'), (_claim_period(row),)) for cid, (p, _v, _s) in values.items()
                     if p in prior for u in fc if u[0] == p for row in [u[2]]}
            errs += _unnamed_period_errors(answer, other, specs)
            bad = [p for p in bad if p not in prior]
        if bad:
            nhan = ', '.join(_spec_label(x) for x in specs)
            errs.append(f'câu hỏi nêu kỳ {nhan} nhưng số dự báo lấy từ kỳ / grain khác ({", ".join(bad[:3])}): gọi '
                        'get_forecast đúng kỳ được hỏi; kỳ ngoài 2023-01-01 → 2024-07-01 thì trả "no_data", không dùng '
                        'số kỳ khác' + ('. Tổng cả vùng dự báo (derived.horizon_total) chỉ dùng khi câu hỏi gồm cả năm '
                                        '2023 và 2024, và câu dẫn số gọi là "cả vùng dự báo", không gọi là tổng năm / '
                                        'tổng 2023–2024' if any('.derived.horizon_total.' in p for p in bad) else ''))
    # RV07: câu hỏi là một KHOẢNG (quý, nửa năm, tháng a–b). Tool không có tổng khoảng: số một tháng / ngày trong khoảng
    # chỉ được dẫn khi câu nêu đúng kỳ của nó, và không được gọi là tổng / cả khoảng
    ranges = [x for x in specs if x[0] == 'range']
    if fc and ranges:
        by_path = {p: (fld, row) for p, fld, row, _ in fc}
        for sent in _SENTENCE.split(answer or ''):
            for cid in _PLACEHOLDER.findall(sent):
                p = values.get(cid, (None,))[0]
                if p not in by_path or by_path[p][1] is None:
                    continue
                row, plain = by_path[p][1], _PLACEHOLDER.sub(' ', sent)
                lab = ', '.join(x[3] for x in ranges)
                # "doanh thu gộp" (tên của G), "bản gộp" (tên model) không phải chữ chỉ tổng (live B3c GM10 sau sửa)
                if _AGG_WORD.search(_NOT_AGG.sub(' ', plain)) or not _names_period(plain, row):
                    errs.append(f'câu "{sent.strip()[:80]}" dùng số của {row.get("period")} cho câu hỏi về khoảng {lab}: '
                                'chưa có tổng khoảng; nêu rõ đó là riêng tháng / ngày nào (vd. "riêng tháng 8/2023"), '
                                'không gọi là tổng quý / nửa năm, hoặc trả "unsupported"')
    want = question_model(q)
    if fc and want:
        cands = {u[2]['candidate'] for u in fc if u[2] and isinstance(u[2].get('candidate'), str)}
        if not any(_cand_matches(c, want) for c in cands):
            errs.append(f'câu hỏi nêu đích danh model ({want}) nhưng số dự báo lấy từ {sorted(cands) or "ứng viên khác"}: '
                        'gọi get_forecast với model / cogs_method được hỏi; không có thì nói không có, không thay model')
    rk = {m[1] for u in used if (m := _RANK_PATH.search(u[0]))}
    if rk:
        need = ({'mape_g_thang'} if _MAPE_RX.search(q) else set()) | ({'score'} if _SCORE_RX.search(q) else set())
        need = need or {'score', 'mape_g_thang'}          # câu so sánh chung: nêu CẢ hai thước (hợp đồng §7)
        # đã dẫn thước = chỗ đặt xếp hạng của thước đó HOẶC một ô điểm của chính thước đó (điểm model chính, điểm của
        # ứng viên được hỏi): live B3c GM12–GM14 bị chặn nhầm khi câu đã dẫn derived.primary.score / rows[..].mape_g_thang
        cited = rk | {u[1] for u in used if u[3] == 'get_forecast_backtest' and u[1] in _BACKTEST_MEASURE}
        if miss := need - cited:
            errs.append(f'câu hỏi về độ chính xác cần thước {sorted(miss)} (derived.lowest_score = điểm ngày kết hợp, thước '
                        'chọn model; derived.lowest_mape_g_thang = MAPE G tháng, chỉ hiển thị) nhưng câu trả lời không dẫn')
    return errs



def validate(answer: str, claims: list, results: dict, extra_allowed: frozenset = frozenset()) -> Checked:
    errors = []
    if not isinstance(answer, str) or not answer.strip():
        return Checked(False, ['thiếu câu trả lời'])
    if not isinstance(claims, list):
        return Checked(False, ['claims phải là danh sách'])
    used = set(_PLACEHOLDER.findall(answer))
    by_id, values = {}, {}
    for c in claims:
        if not isinstance(c, dict) or not isinstance(c.get('id'), str):
            errors.append(f'claim sai dạng: {c!r}'[:120])
            continue
        if c['id'] not in used:          # khai báo mà không dùng: bỏ qua, không được tính cho nhận định nào
            continue
        try:
            v, fld, row = _resolve(c.get('path'), results)
        except ValueError as e:
            errors.append(f'{c["id"]}: {e}')
            continue
        if v is None:
            errors.append(f'{c["id"]}: {c["path"]} là NULL (không tính được), không được trình bày như một số')
            continue
        sign = c.get('sign')
        if sign is not None:
            if sign not in ('am', 'duong') or not _is_num(v):
                errors.append(f'{c["id"]}: sign chỉ nhận "am"/"duong" cho giá trị số')
            elif v == 0 or (sign == 'am') != (v < 0):
                errors.append(f'{c["id"]}: nói {sign} nhưng {c["path"]} thật là {v}')
        by_id[c['id']] = (c, v, fld, row)

    for cid in sorted(used):
        if cid not in by_id and not any(e.startswith(f'{cid}:') for e in errors):
            errors.append(f'chỗ đặt {{{cid}}} không có claim hợp lệ')
    errors += check_digits(answer, allowed_years(results) | set(extra_allowed) | definition_text_numbers(results))
    # ô kiểu NGÀY không phải số ngày: "mỗi fold dự báo {c2} ngày" với c2 = trained_through (live B3c GM13)
    for m in _PLACEHOLDER.finditer(answer):
        if m[1] in by_id and isinstance(by_id[m[1]][1], _date) and re.match(r'\s*ngày(?!\w)', answer[m.end():], re.I):
            errors.append(f'{m[1]}: {by_id[m[1]][0]["path"]} là một ngày (ngày tháng), không phải số ngày; dùng ô đếm '
                          '(n_days, n_folds) hoặc bỏ số đó')

    # câu xếp hạng: chỗ đặt xếp hạng phải nằm trong CHÍNH câu đó và cùng hướng với chữ tăng/giảm của câu; hoặc app tự
    # đối chiếu được (N/U/P viết thẳng, câu nối "Đây là…" trỏ về đối tượng của câu ngay trước)
    pieces = _SENTENCE.split(answer)
    for i, sent in enumerate(pieces):
        low = _METRIC_NAME_RANK.sub(' ', sent.lower())
        if not any(w in low for w in RANK_WORDS):
            continue
        prev = next((p for p in reversed(pieces[:i]) if p.strip()), '')
        paths = [by_id[cid][0]['path'] for cid in _PLACEHOLDER.findall(sent) if cid in by_id]
        ranks = [r for r in map(_rank_direction, paths) if r]
        explain_groups = [by_id[cid][3] for cid in _PLACEHOLDER.findall(sent) if cid in by_id
                          and by_id[cid][3] and by_id[cid][3].get('feature_group')
                          and (res := results.get(by_id[cid][0]['path'].split('.')[0])) is not None
                          and res.evidence and res.evidence.tool == 'explain_forecast']
        if explain_groups and any(w in low for w in ('chủ yếu', 'mạnh nhất', 'lớn nhất')):
            if not _verified_explain_rank(sent, by_id, results):
                errors.append('nhóm phân rã nói "chủ yếu/mạnh nhất/lớn nhất" phải đúng top-k theo chiều và rank_dir '
                              '(hoặc rank khi không nêu chiều) của cùng kết quả tool')
            continue
        if not ranks and _verified_driver_rank(sent, results):
            continue
        if not ranks and any(by_id[cid][2] in RANK_BOTH for cid in _PLACEHOLDER.findall(sent) if cid in by_id):
            continue
        if not ranks and _verified_anaphor_rank(sent, prev, by_id, results):
            continue
        if (not paths and _RANK_LIMIT.search(low) and not _said_driver(sent)
                and not _NAMED_SUBJECT.search(_PLACEHOLDER.sub(' ', sent))):
            # câu nói giới hạn của tool / gợi ý hỏi tiếp, không khẳng định chủ thể nào (live D11 sau sửa, F08, F09).
            # "N/U/P" nhắc cả ba thì _said_driver = None; gọi riêng một thành phần thì vẫn kiểm.
            continue
        weak = any(w in low for w in WEAK_WORDS) and not any(w in low for w in STRONG_WORDS)
        strong = any(w in low for w in STRONG_WORDS) and not any(w in low for w in WEAK_WORDS)
        if not ranks and weak:
            # live D11: lời nhắc cũ chỉ cách dùng largest_* nên model đổi câu hỏi "ít nhất" thành "nhiều nhất"
            errors.append(f'câu "{sent.strip()[:80]}" xếp hạng phía "nhỏ nhất / ít nhất" nhưng trong câu không có chỗ đặt '
                          'xếp hạng phía đó. Nhóm (ngành, vùng, kênh): dùng derived.smallest_decrease.groups / '
                          'smallest_increase.groups; tháng thấp nhất: trough_*. Giai đoạn, điểm đổi hướng: tool không xếp '
                          'phía nhỏ, bỏ câu xếp hạng hoặc trả status "unsupported". KHÔNG đổi sang trả lời phía lớn nhất')
            continue
        if not ranks:
            crit = _criteria(sent) if any(r.ok and _is_phase_result(r) for r in results.values()) else set()
            where = (' hoặc '.join(h for k, h in (('tien', 'derived.largest_*.phases'),
                                                    ('cagr', 'derived.largest_*_cagr.phases')) if k in crit)
                     or 'derived.largest_* hoặc top_*_driver (dự báo: derived.lowest_score / lowest_mape_g_thang / '
                        'highest_month / lowest_month; R / G từng năm: derived.highest_r / lowest_r .years)')
            errors.append(f'câu "{sent.strip()[:80]}" có ý xếp hạng ("nhiều nhất", "chủ yếu"...) nhưng trong câu '
                          f'không có chỗ đặt trỏ vào {where} (xếp hạng trên đủ tập). Đặt chỗ đặt xếp hạng ngay trong '
                          'câu đó, hoặc mở câu bằng "Đây là…" ngay sau câu dẫn số của chính giai đoạn / nhóm ấy')
            continue
        ranked = [p for p in paths if _rank_direction(p) and p.rsplit('.', 1)[-1] not in LEVEL_RANK]
        if weak and ranked and all('.derived.smallest_' not in p and '.derived.lowest_' not in p for p in ranked):
            errors.append(f'câu "{sent.strip()[:80]}" nói "nhỏ nhất / ít nhất" nhưng chỗ đặt là phía lớn nhất (largest_*, '
                          'top_*_driver); nhóm thì dùng derived.smallest_decrease / smallest_increase.groups')
            continue
        if strong and ranked and all('.derived.smallest_' in p for p in ranked):
            errors.append(f'câu "{sent.strip()[:80]}" nói "nhiều nhất / mạnh nhất" nhưng chỗ đặt là phía nhỏ nhất '
                          '(smallest_*); dùng derived.largest_*')
            continue
        crit_errs = _criteria_errors(sent, paths, results, prev, by_id)
        if crit_errs:
            errors += crit_errs
            continue
        level = [_rank_direction(by_id[cid][0]['path']) for cid in _PLACEHOLDER.findall(sent)
                 if cid in by_id and (by_id[cid][0]['path'].rsplit('.', 1)[-1] in LEVEL_RANK
                                      or _LEVEL_PATH.search(by_id[cid][0]['path']))]
        hi, lo = any(w in sent.lower() for w in HIGH_WORDS), any(w in sent.lower() for w in LOW_WORDS)
        if level and all(_RANK_PATH.search(by_id[cid][0]['path']) for cid in _PLACEHOLDER.findall(sent)
                         if cid in by_id and _LEVEL_PATH.search(by_id[cid][0]['path'])):
            # xếp hạng theo SAI SỐ (lowest_score / lowest_mape_g_thang): "dẫn đầu", "đứng đầu" là sai số thấp nhất (live B3c)
            hi = any(w in sent.lower() for w in HIGH_WORDS if w not in ('dẫn đầu', 'đứng đầu'))
        if level and hi != lo and all(r != (1 if hi else -1) for r in level):
            errors.append(f'câu "{sent.strip()[:80]}" nói "{"cao" if hi else "thấp"} nhất" nhưng chỗ đặt trỏ vào phía '
                          f'{"thấp" if hi else "cao"} (peak/trough, max/min)')
            continue
        d = _direction(_PLACEHOLDER.sub(' ', sent))
        # xếp hạng MỨC của dự báo (sai số thấp nhất, tháng cao nhất) không có chiều tăng/giảm để đối chiếu
        ranks = [_rank_direction(p) for p in paths if _rank_direction(p) and not _LEVEL_PATH.search(p)]
        if d and ranks and all(r != d for r in ranks):
            errors.append(f'câu "{sent.strip()[:80]}" nói "{"tăng" if d > 0 else "giảm"}" nhưng claim xếp hạng là '
                          f'chiều {"tăng" if d < 0 else "giảm"}')

    # B3: câu nói "thực tế" mà dẫn số dự báo; câu nêu thước (MAPE / điểm ngày) mà dẫn xếp hạng của thước kia
    for sent in _SENTENCE.split(answer):
        cids = [cid for cid in _PLACEHOLDER.findall(sent) if cid in by_id]
        low = _PLACEHOLDER.sub(' ', sent).lower()
        if any(by_id[c][2] in FORECAST_FIELDS for c in cids) and 'thực tế' in low and 'dự báo' not in low:
            errors.append(f'câu "{sent.strip()[:80]}" gọi số dự báo là "thực tế": số dự báo phải nói rõ là dự báo')
        ranks_in = {m[1] for c in cids if (m := _RANK_PATH.search(by_id[c][0]['path']))}
        if ranks_in == {'score'} and _MAPE_RX.search(low) and not _SCORE_RX.search(low):
            errors.append(f'câu "{sent.strip()[:80]}" nói theo MAPE / sai số tháng nhưng dẫn derived.lowest_score (điểm '
                          'ngày); dùng derived.lowest_mape_g_thang')
        if ranks_in == {'mape_g_thang'} and _SCORE_RX.search(low) and not _MAPE_RX.search(low):
            errors.append(f'câu "{sent.strip()[:80]}" nói theo điểm ngày nhưng dẫn derived.lowest_mape_g_thang; dùng '
                          'derived.lowest_score')

    # B7 router, câu trộn thực tế và dự báo (quy tắc 16): mỗi phần một câu riêng; không so hai loại số bằng lời ("dự báo
    # thấp hơn thực tế", "chênh so với năm 2021"), vì không tool nào tính chênh lệch dự báo − thực tế
    kind = {cid: k for cid, (c, _v, fld, _row) in by_id.items() if (k := _number_kind(c['path'], fld, results))}
    mixed = {'du_bao', 'thuc_te'} <= set(kind.values())
    for sent in _SENTENCE.split(answer):
        ks = {kind[cid] for cid in _PLACEHOLDER.findall(sent) if cid in kind}
        low = _PLACEHOLDER.sub(' ', sent).lower()
        if ks == {'du_bao', 'thuc_te'}:
            errors.append(f'câu "{sent.strip()[:80]}" đặt số thực tế và số dự báo trong cùng một câu: tách thành hai câu '
                          'riêng, mỗi câu một loại số; không cộng, trừ hay so hai loại số')
        elif _mix_compare(low) and ((mixed and 'dự báo' in low and 'thực tế' in low)
                                    or ('du_bao' in ks and 'backtest' not in low and _PAST_YEAR.search(low))):
            errors.append(f'câu "{sent.strip()[:80]}" so số dự báo với số thực tế: không tool nào tính chênh lệch này; '
                          'nêu hai số thành hai câu riêng, không so')

    # câu so sánh phải dẫn ít nhất một số thay đổi do tool tính (delta_r, yoy_rate, *_change_rate...)
    # (câu không có chỗ đặt nào, vd. nhắc lại câu hỏi "tháng 8 năm lẻ có thấp hơn..." khi từ chối, thì không xét)
    for sent in _SENTENCE.split(answer):
        cids = [cid for cid in _PLACEHOLDER.findall(sent) if cid in by_id]
        if (cids and any(w in sent.lower() for w in COMPARE_WORDS) and not any(by_id[c][2] in COMPARED for c in cids)
                and not _verified_backtest_compare(sent, by_id)):
            errors.append(f'câu "{sent.strip()[:80]}" tự so sánh các số (cao hơn / thấp hơn...) mà không dẫn cột thay đổi '
                          'do tool tính; app không kiểm được phép so sánh này')

    # tên nhóm viết thẳng phải gắn với claim đã dùng (rows[<nhóm>] hoặc danh sách nhóm của claim)
    bound = set()
    for c, v, fld, row in by_id.values():
        if row and isinstance(row.get('dimension_value'), str):
            bound.add(row['dimension_value'])
        for k in ('candidate', 'candidate_label'):
            if row and isinstance(row.get(k), str):
                bound.add(row[k])
        if isinstance(v, str):
            bound.add(v)
        if isinstance(v, list):
            bound |= {x for x in v if isinstance(x, str)}
    plain_text = _PLACEHOLDER.sub(' ', answer)
    loose = sorted(n for n in _group_names(results) - bound
                   if re.search(rf'(?<!\w){re.escape(n)}(?!\w)', plain_text, re.I))
    if loose:
        errors.append(f'câu văn viết thẳng tên nhóm {loose[:3]} mà không gắn với claim nào đã dùng: tên nhóm phải là '
                      'chỗ đặt (derived.largest_*.groups, rows[<nhóm>].dimension_value) hoặc đi cùng claim rows[<nhóm>]')
    bound_text = ' | '.join(bound).lower()
    fam = sorted(f for f, rx in MODEL_FAMILY.items()
                 if re.search(rx, plain_text, re.I) and not re.search(rx, bound_text, re.I))
    if fam and any(r.ok and r.evidence and r.evidence.tool.startswith('get_forecast') for r in results.values()):
        errors.append(f'câu văn nêu model {fam} mà không gắn với ô nào của model đó: tên model phải là chỗ đặt '
                      '(derived.primary.label, rows[<ứng viên>].candidate_label) hoặc đi cùng số của chính model đó')

    # chữ "tăng"/"giảm" ngay trước số phải cùng dấu với số thật; vế câu gọi tên R mà số là G (hoặc ngược lại) thì chặn
    # (tương tự với N/U/P: "{c2: giá mỗi món (P)} góp {c3: contrib_u}" là gắn số của U cho P)
    rendered, last, prev, prev_driver = [], 0, 0, None
    for m in _PLACEHOLDER.finditer(answer):
        cid = m.group(1)
        rendered.append(answer[last:m.start()])
        last = m.end()
        if cid not in by_id:
            prev, prev_driver = m.end(), None
            continue
        c, v, fld, row = by_id[cid]
        parts = re.split(r'[.;:!?\n]', answer[prev:m.start()])
        seg = parts[-1]                # đoạn từ chỗ đặt trước / đầu vế câu
        if len(parts) > 1:
            prev_driver = None
        prev = m.end()
        said, fam = _said_metric(seg), METRIC_FAMILY.get(fld)
        if said and fam and said != fam:
            errors.append(f'{cid}: vế câu gọi tên {said} nhưng {c["path"]} là số của {fam}')
        drv = DRIVER_FAMILY.get(fld)
        said_drv = _said_driver(seg) or prev_driver
        if drv and said_drv and said_drv != drv:
            errors.append(f'{cid}: vế câu nói về {said_drv} nhưng {c["path"]} là số của {drv}')
        if fld in ('top_up_driver', 'top_down_driver') and re.search(r'(mức|góp|bằng)\W*$', seg.strip(), re.I):
            errors.append(f'{cid}: chỗ đặt sau "{seg.strip()[-20:]}" phải là một số (contrib_*), không phải tên thành phần')
        prev_driver = str(v).upper() if fld in ('top_up_driver', 'top_down_driver') else None
        absolute = False
        if fld in SIGNED and _is_num(v) and v != 0:
            d, near = _direction(seg[-40:]), _adjacent_direction(seg)
            for x in {d, near} - {0}:
                if x != (1 if v > 0 else -1):
                    errors.append(f'{cid}: câu nói "{"tăng" if x > 0 else "giảm"}" nhưng {c["path"]} = {v}')
            # chỉ bỏ dấu khi chữ tăng/giảm đúng dấu đi liền trước số; còn lại in dấu thật (−6,4%)
            absolute = near != 0
        s = _fmt(v, fld, absolute)
        lbl = _label(fld, row, seg, actual=mixed and kind.get(cid) == 'thuc_te', answer=answer,
                     after=answer[m.end():]) if _is_num(v) else ''
        values[cid] = (c['path'], v, s + lbl)
        rendered.append(f'**{s}**{lbl}')
        # model hay viết lại đơn vị sau chỗ đặt ("{c1} VND"): app đã ghi đơn vị, bỏ bản lặp
        unit = (_DUP_MONEY if fld in MONEY | PRICE else _DUP_PCT if fld in RATE
                else _DUP_PP if fld in PP | PP_FRAC else None)
        dup = unit.match(answer, last) if unit else None
        if dup:
            last = prev = dup.end()
    rendered.append(answer[last:])
    if errors:
        return Checked(False, errors)
    return Checked(True, [], ''.join(rendered), values, bound)
