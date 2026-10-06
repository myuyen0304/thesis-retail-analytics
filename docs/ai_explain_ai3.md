# AI Explain — AI3: mở chat cho PS1–PS3

Ngày: **2026-10-05**. Nối tiếp [ai_explain_ai2.md](ai_explain_ai2.md). Kế hoạch gốc: [ai_explain_plan.md](ai_explain_plan.md) §4, §13.

## 1. Trạng thái

| Mốc | Trạng thái | Bằng chứng |
|---|---|---|
| Tool PS1–PS3 (không LLM) | **Xong**: số khớp CSV ở mọi năm, tháng và giai đoạn; PostgreSQL khớp DuckDB | `tests/test_ai_tools_ps123.py`, `tests/test_ai_tools.py` (so PG) |
| Nghiệm thu AI3 với model thật | **Đạt trên bộ B\***: 30/30 lượt, đọc tay 0 lỗi chặn, sau khi sửa lỗi bỏ ngầm bộ lọc nhóm phát hiện ở bộ A\* | §4 |
| Model thật trên PostgreSQL | **Đạt**: B\* 30/30; toàn bộ 95 câu 93/95, hai câu trượt không do backend | §4b |
| Sửa dấu âm và lỗi mức vừa | **Đạt trên bộ mới C\***: DuckDB 30/30, PostgreSQL 30/30 | §4c |
| Chưa phủ | Tháng đổi hướng do dữ liệu tự tìm; phân rã N/U/P theo giai đoạn; nhóm × tháng | §6 |

Test AI tổng cộng **289/289**. PASS ở đây là test tool và bộ kiểm, không gọi model; kết quả model thật ở §4 là bằng chứng riêng.

## 2. Bốn tool mới

| Tool | Câu hỏi | Bảng đọc | Ghi chú |
|---|---|---|---|
| `get_revenue_gap(period, year?)` | PS1: G hụt thành R bao nhiêu, vì khoản nào | `rpt_revenue_yearly` / `rpt_revenue_total` + `rpt_revenue_bridge` | Một năm hoặc cả kỳ 2013–2022. Hai bảng đọc trong cùng phiên phải khớp nhau từng cent, bốn khoản phải cộng đúng G − R; lệch thì báo lỗi, không trả số |
| `get_revenue_monthly(metric, year, month)` | PS1/PS3: R/G của một tháng | `rpt_revenue_monthly` | Với R kèm R cùng tháng năm trước, % đổi (từ 08/2013) và chỉ số tháng (năm đủ). Chỉ có số **toàn công ty** |
| `get_revenue_trend(view)` | PS2: giai đoạn, điểm đổi hướng | `rpt_revenue_phase`, `rpt_revenue_turning_point` | 4 giai đoạn và 3 điểm PM/BA đã chốt. "Giảm mạnh nhất" có hai tiêu chí: ΔR (tiền) hoặc CAGR |
| `get_calendar_pattern(pattern)` | PS3: mùa vụ, dồn cuối tháng, tháng 8 năm lẻ | `rpt_calendar_stability`, `rpt_august_parity`, `rpt_calendar_phase`, `rpt_revenue_total` | Kèm khoảng dao động khi bỏ từng năm và số năm tự có nhịp. Số theo giai đoạn PS3 mang nhãn **đề xuất** (quy ước năm ranh giới chờ BA chốt) |

**Vẫn đóng:**
- tháng đổi hướng do dữ liệu tự tìm (tiêu chí thăm dò);
- phân rã N/U/P theo giai đoạn (cách cộng từng năm chờ PM/BA chốt);
- nhiều tháng, quý hoặc khoảng ngày;
- nhóm × tháng;
- số khách C theo nhóm.

Catalog `ai3-2026-10-05` thêm 10 chỉ tiêu:
- khoản chênh G − R;
- R/G;
- chỉ số tháng;
- % đổi R cùng tháng;
- giai đoạn;
- CAGR;
- độ lớn đổi hướng;
- chênh mùa;
- mức dồn cuối tháng;
- chênh tháng 8.

Tài khoản chỉ-đọc của AI trên PostgreSQL được cấp thêm quyền SELECT trên 8 bảng (tổng 14). Lệnh: `scripts/ops/pg_ai_readonly_role.py`.

## 3. Số đối chứng độc lập

`tests/test_ai_tools_ps123.py` tính thẳng từ CSV bằng pandas, tiền theo cent nguyên:
- **G → R:** mọi năm 2012–2022 và cả kỳ. G lấy từ `sales.csv`, R từ `payments.csv`, các khoản chênh từ dòng hàng theo trạng thái đơn. Test kiểm luôn đối soát PS1 trên CSV: G = tiền hàng mọi trạng thái, và G − R = tổng bốn khoản.
- **Tháng:** cả 126 tháng: R, G, R/G, % so cùng tháng năm trước, chỉ số tháng; NULL đúng chỗ (trước 08/2013, năm 2012).
- **Giai đoạn và điểm đổi hướng:** tính theo mốc PM/BA chốt, không đọc seed của kho.
- **Tháng 8, mùa vụ, cuối tháng:** gồm khoảng dao động khi bỏ từng năm và số năm có nhịp.

Bộ kiểm câu trả lời có thêm 16 ca chạy trên kết quả tool thật, cả câu đúng lẫn câu sai.

## 4. Chạy với model thật (deepseek-flash, DuckDB)

| Lần chạy | Bộ | Prompt | Kết quả | Ghi chú |
|---|---|---|---|---|
| 09:47 | E30–E38, E12, E13 (bộ **phát triển**, dùng để chỉnh) | `ai3-…a` | 10/12 | Hai câu đúng bị bộ kiểm chặn nhầm ("tháng 7/2012" lấy từ thông báo của tool; câu "chênh giữa tháng cao nhất và thấp nhất"). Đã sửa bộ kiểm |
| 09:51 | E\* + H\* (65 câu, hồi quy, H\* ghi "sau sửa") | `ai3-…a` | **65/65** | Các lỗi lời nhỏ ở §0b của AI2 không còn lặp lại |
| 09:56 | **A\*** (20 câu × 3, nghiệm thu lần 1, chốt trước ở commit `a71291a`) | `ai3-…a` | 56/60 | **Lỗi chặn ở A08** ("Doanh thu Streetwear tháng 5/2019?"): lần 3 trả R toàn công ty, tức bỏ ngầm bộ lọc ngành; lần 1–2 có nói rõ nhưng vẫn để trạng thái "ok". A02c lần 3: rubric cấm chữ "tăng" bắt nhầm câu đúng |
| 12:57 | A\* sau sửa | `ai3-…b` | 59/60 | Log bị hỏng do chạy song song với B\*, nên không đọc tay được lượt A04 bị trượt. Chạy lại riêng A04 ba lần: 3/3 |
| 13:00 | **B\*** (10 câu × 3, nghiệm thu lần 2, chốt trước ở commit `72881cb`) | `ai3-…b` | **30/30** | Đọc tay 0 lỗi chặn. Log `warehouse/ai_eval/live_20261005T130041Z_ai3b_21624.jsonl` |

**Sửa lỗi A08** (commit `d921d1e`). Chốt chặn nằm trong code, không chỉ ở prompt:
- câu hỏi nêu tên nhóm (ngành, vùng, kênh) mà câu trả lời "ok" không có số nào của nhóm đó thì bị chặn;
- nhóm kèm tháng, quý hoặc ngày thì không được trả "ok".

Ở B\*, các câu "kênh referral quý 3/2020" và "vùng West tháng 12/2021" đều trả "chưa hỗ trợ". Số thay thế (cả năm của nhóm, hoặc tháng của toàn công ty) có ghi rõ "không phải số bạn hỏi".

**Lỗi lời nhỏ, chưa sửa:**
- B06: "CAGR **6,4%** mỗi năm (R giảm)" mất dấu âm, vì tên giai đoạn "Chững, giảm nhẹ" đứng ngay trước chỗ đặt nên app in giá trị tuyệt đối. Số không sai nhưng đọc dễ nhầm.
- B02 lần 2: gợi ý "hỏi kênh referral theo tháng" rồi tự nói số theo tháng không tách theo kênh.
- E35: nói tháng 5 là "tháng cao nhất chung của cả kỳ". Tool chỉ trả tháng cao nhất của từng giai đoạn (cả 4 giai đoạn đều là tháng 5); cả kỳ không có ô riêng.

**Chi phí ước** (giá cao điểm): khoảng 1,6 USD cho toàn bộ các lần chạy hôm nay. Thời gian trung bình 2–5 giây mỗi câu.

## 4b. Chạy với model thật trên PostgreSQL (2026-10-05, chiều)

Cách chạy:
- tài khoản chỉ-đọc `retail_ai_ro` (đặt qua `PG_AI_USER` / `PG_AI_PASSWORD`);
- guard đạt (`pg_ai_readonly_role.py --check`);
- `--kiem-rubric --backend postgres --set tat_ca` đạt 95/95 trước khi gọi model;
- prompt `ai3-…b`, code `a17bf68`, chạy tuần tự.

| Lần chạy | Bộ | Kết quả | Log |
|---|---|---|---|
| 14:28 | B\* × 3 | **30/30**, đọc tay 0 lỗi chặn | `live_20261005T142854Z_ai3b_5264.jsonl` |
| 14:30 | E\* + H\* + A\* + B\* × 1 (95 câu) | **93/95** | `live_20261005T143021Z_tat_ca_8768.jsonl` |

Hai câu trượt, đều không do backend:
- **E15** "Doanh thu năm 2023": lời đúng (dữ liệu chỉ đến 2022), không có số, nhưng nhãn là `unsupported` thay vì `no_data`. Không có hại cho người đọc.
- **A04** "Tháng nào doanh thu thấp nhất": bị bộ kiểm chặn, app chỉ hiện bảng số.
  - Model thêm câu "tháng thấp nhất lặp lại ở cả {n_phases} giai đoạn". Câu này đúng: cả 4 giai đoạn đều có đáy ở tháng 12.
  - Nhưng `n_phases` chỉ là số giai đoạn, không chứng minh các giai đoạn có cùng đáy, nên chặn là đúng.
  - Đây có thể cũng là nguyên nhân lượt A04 trượt ở lần chạy 12:57 (log hỏng, không kiểm lại được).
  - Cách sửa đề xuất: thêm `derived.n_phases_same_peak` / `n_phases_same_trough`.

Đọc tay thêm, các lỗi lời (không phải lỗi số):
- **Mất dấu âm** khi trong câu có chữ "giảm": B06 lần 1 ("CAGR 6,4% mỗi năm", không có cả chữ "R giảm"), E13 ("CAGR 39,1%"), A03c ("độ lớn 9,7%", câu sau có nói "R giảm"). Cùng nguyên nhân với B06 ở §4, nhưng gặp nhiều hơn → nên sửa trước demo.
- **A02:** lặp cùng một số hai lần liền ("−7,5% −7,5%").

Chi phí ước khoảng 0,57 USD cho hai lần chạy.

## 4c. Sửa lỗi dấu âm và các lỗi mức vừa, nghiệm thu bằng C\* (2026-10-05, tối)

**Thay đổi** (commit `4b8b63c`, `7897f31`; prompt `ai3-2026-10-05c`, tool `v1.3`):
- **`evidence.py`:** chỉ bỏ dấu khi chữ tăng/giảm đứng sát trước số (`_adjacent_direction`); chữ đứng sát mà ngược dấu thì chặn.
- **`tools.py` (mùa vụ):** thêm `rows[0].peak_month / trough_month` cả kỳ, lấy R cùng tên tháng cộng qua 2013–2022 từ `rpt_revenue_monthly` và kiểm lại tỷ số khớp `rpt_calendar_stability` trong cùng phiên. Thêm `derived.n_phases_same_peak / _trough`, được tính là chỗ đặt xếp hạng.
- **`service.py`:**
  - quy tắc 6: số thực tế → `no_data`, dự báo → `unsupported`;
  - quy tắc 14: dẫn các ô mới;
  - trần token cứng: `prompt_bound` + `MAX_OUTPUT_TOKENS=2048`, kèm `finish_reason == 'length'` thì không hiện.
- **`provider.py`:** gửi `max_tokens`, trả `finish_reason`.
- **dbt:** `macros/ai_readonly_grants.sql` + var `ai_readonly_relations`; test kiểm danh sách trùng `ALLOWED_RELATIONS`.

**Bằng chứng không gọi model:**
- test AI 315/315; toàn bộ test app 475 đạt, 26 bỏ qua (Databricks);
- các test mới dùng nguyên văn `raw_final` của B06, E13, A03c, A04 lấy từ log;
- thử ngược: trả code về cách cũ thì test trượt.

**Model thật** (log ở `warehouse/ai_eval/`):

| Giờ (UTC) | Bộ | Backend | Kết quả | Log |
|---|---|---|---|---|
| 15:52 | **C\*** × 3 (mới, chốt ở `4b8b63c` trước khi chạy) | DuckDB | **30/30** | `live_20261005T155233Z_ai3c_5716.jsonl` |
| 15:53 | **C\*** × 3 | PostgreSQL | **30/30** | `live_20261005T155357Z_ai3c_24104.jsonl` |
| 15:55 | E15, E15b, H15, A04d × 10 (sau sửa) | DuckDB | 39/40; nhãn đúng 40/40 | `live_20261005T155518Z_tat_ca_21156.jsonl` |
| 15:56 | 105 câu × 1 (sau sửa) | PostgreSQL | 104/105 | `live_20261005T155626Z_tat_ca_2368.jsonl` |

Ghi chú các lượt trượt:
- **A04d lần 4:** rubric cấm cụm "sẽ thấp" bắt nhầm câu từ chối đúng. Rubric giữ nguyên, không nới sau khi xem kết quả.
- **A03:** model thêm câu "tăng mạnh nhất… trong {c6} giai đoạn" mà chỗ đặt xếp hạng nằm ở câu trước, nên bị chặn đúng nguyên tắc (lỗi an toàn). Cùng kiểu với C02, nơi 3/6 lượt phải sửa một lần rồi mới qua.

Đọc tay C\* (60 lượt) không có lỗi chặn; số phụ model tự đưa thêm (R đầu/cuối giai đoạn, % đổi cả giai đoạn D, 6,7%) đã đối chiếu, đều khớp.

Cận trên prompt đúng ở cả 391 lần gọi thật (cận / thật ≥ 3,01). Đổi lại, phiên dừng sớm hơn khoảng 22–26 nghìn token (khoảng 2 câu).

## 4d. Chat trên Databricks production (2026-10-06)

- **Đường đọc:** `dwh/guarded.py` `_DatabricksSession`. Chat dùng **service principal riêng** `retail-ai-ro` (OAuth M2M), không bao giờ dùng tài khoản người hay SP của app.
- **Guard** đọc quyền thật trong `system.information_schema` (các view quyền đã gồm quyền thừa kế) và chặn khi:
  - sai danh tính;
  - SP là owner của đối tượng nào;
  - có quyền nào ngoài USE + SELECT đúng 14 bảng;
  - nhìn thấy bảng nào khác;
  - không nhận ra quyền của chính mình.
- **7 ngoại lệ nền tảng** do bản Free cấp cho mọi tài khoản, PM duyệt; danh sách ở đầu phần Databricks trong `guarded.py`.
- **Không có snapshot xuyên câu:** tool đọc lại build marker cuối lượt.
- **Kết quả:**
  - rubric **105/105**;
  - số **khớp chính xác DuckDB** ở 83 tổ hợp tool;
  - model thật **C\* × 3 = 30/30** (kiểm ngang backend, prompt `ai3-2026-10-05c`), đọc tay 0 lỗi chặn.
  - Log: `live_20261006T053356Z_ai3c_12564.jsonl`.
- **Thời gian:** khoảng 11–14 giây mỗi câu.
- **Chi tiết từng bước** (B1–B4): `docs/ai_explain_nhat_ky.md` §2.

## 5. Khi demo nên nói gì

- Hỏi một ngành, vùng hoặc kênh **theo tháng** thì trợ lý trả "chưa hỗ trợ". Đây là giới hạn đúng của kho, không phải lỗi.
- "Giai đoạn nào giảm mạnh nhất" có hai tiêu chí: theo tiền hoặc theo CAGR. Cả hai đều ra giai đoạn C (sập 2018 → 2019).
- Tháng 8 năm lẻ so bằng **chỉ số tháng**, không so R tuyệt đối, và là mô tả lịch sử, không phải dự báo 2023.
- Số PS3 theo giai đoạn đang dùng quy ước đề xuất. Số cả kỳ 2013–2022 không phụ thuộc quy ước này.

## 6. Việc còn lại

1. ~~Chạy model thật trên PostgreSQL~~: xong, §4b.
2. Sửa các lỗi lời ở §4 và §4b (mất dấu âm, lặp số, chỗ chứng minh "cùng tháng ở mọi giai đoạn"). Sau đó chạy lại B\* và ghi là "sau sửa"; cần thêm bộ câu mới cho lần nghiệm thu sau.
3. Báo cáo AI4: tách test truy vấn, test giao diện và model thật; ghi phiên bản model, prompt, catalog, dữ liệu.
4. Chờ PM/BA chốt: quy ước năm ranh giới PS3, phân rã theo giai đoạn, ngưỡng ΔR nhỏ 1%.

## 7. File

- Code: `apps/retail_app/ai_explain/{tools,evidence,service,metric_catalog,eval_cases}.py`, `apps/retail_app/views/ai_explain.py`.
- Test: `apps/retail_app/tests/test_ai_tools_ps123.py` (mới), `tests/test_ai_tools.py` (so PG).
- Eval: `scripts/ops/ai_live_eval.py`:
  - các bộ `--set chuan|moi|ai3|ai3b|tat_ca`;
  - `--kiem-rubric` kiểm rubric mà không gọi model;
  - log ở `warehouse/ai_eval/`.
- Commit trên `app/myuyen` (chưa push): `1461aa7`, `a71291a`, `d921d1e`, `72881cb`, `a17bf68`.
