# B6: biểu đồ trong chat (`show_chart`) — thiết kế, kiểm và eval với LLM thật

Bước B6 trong [ke_hoach_ai_gd2.md](ke_hoach_ai_gd2.md) §4. Luật áp dụng là dòng L2 trong `agent_levels.md` của skill `retail-ai-explain`:
biểu đồ vẽ từ đúng kết quả đã đi qua evidence, và không vẽ số không có trong evidence.

---

## 1. Thiết kế

- **Tool `show_chart(ref, y, y2?)`** (`apps/retail_app/ai_explain/charts.py`). Mô hình chỉ nêu ba thứ:
  - kết quả tool nào của lượt này (`T1`, `T2`...);
  - cột số `y`;
  - tùy chọn: cột thứ hai `y2`, phải cùng đơn vị.

  Trục x và dữ liệu do app lấy từ `results[ref].rows`, tức chính bảng trong phần **Bằng chứng** của câu trả lời.
  Schema không có tham số nào để đưa số vào biểu đồ.
- **Vẽ được:**
  - dự báo từng tháng (`get_forecast` period `horizon`);
  - so sánh ứng viên (`get_forecast_backtest`, ★ và màu đỏ đánh dấu model chính);
  - R theo nhóm của một năm (`get_segment_contribution`);
  - giai đoạn và điểm đổi hướng (`get_revenue_trend`);
  - mùa vụ, dồn cuối tháng (`get_calendar_pattern`).

  Kết quả một dòng (tổng hợp một năm, một tháng) không vẽ, vì biểu đồ cần ít nhất 2 điểm.
- **Biểu đồ dự báo:**
  - tiêu đề là nhãn dự báo do app viết (`derived.forecast_label`);
  - tháng **07/2024 không vẽ**, vì chỉ có 1/31 ngày dự báo; chú thích ghi lý do;
  - theo tháng không có khoảng dự báo (Q7), nên chú thích ghi sai số tháng điển hình;
  - khoảng 80% chỉ vẽ khi mọi dòng có cận dưới và cận trên.
- **Tách khỏi tool dữ liệu:** `show_chart` không đọc kho. Lời gọi biểu đồ:
  - không tính vào giới hạn 4 lần đọc kho, có trần riêng 2 biểu đồ mỗi câu;
  - không nhận mã T, không nằm trong danh sách lời gọi tool dữ liệu (`turn.calls`).
- **Khi nào hiện:** chỉ khi câu trả lời qua bước kiểm (`ok`). Trang vẽ lại từ kết quả đã lưu, không gọi lại mô hình.
- **Chưa làm** (ghi là giới hạn):
  - Biểu đồ R / G theo từng năm hoặc từng tháng của một năm. Chưa có tool trả cả chuỗi; `get_revenue_summary` chỉ trả một năm, mỗi câu tối đa 4 lần đọc kho. Prompt dặn không ghép nhiều lần gọi một năm.
  - Nút mở trang tương ứng kèm bộ lọc (deep link của luật L2): **đã làm 2026-10-17**, xem [ghi_chu_l2_airflow_rollback_20261017.md](ghi_chu_l2_airflow_rollback_20261017.md) mục 1.

Phiên bản: prompt `b6-2026-10-16b` (lần chạy chính ở mục 4.1 dùng `b6-2026-10-16`, trước khi rút gọn), tool `v1.6`, catalog `b3-2026-10-15`.
Mô tả tham số `model` của tool `v1.6` được rút gọn ngày 2026-10-16 mà không đổi số phiên bản; các log phân biệt bằng mã băm code
(`11cdbd8704641902` trước khi rút gọn, `d7c296e7cb6e6c29` sau).

## 2. Kiểm không gọi LLM

`apps/retail_app/tests/test_ai_charts.py`, 19 test, provider giả:
- Dữ liệu biểu đồ dự báo bằng đúng các dòng bằng chứng, và khớp tổng tháng tính thẳng từ parquet của stage dự báo (đối chứng độc lập). Dữ liệu Altair nhận cũng là các dòng đó.
- 07/2024 không vẽ; bảng so sánh model đánh dấu đúng model chính.
- Các trường hợp từ chối:
  - ref không có hoặc không ok;
  - tool một dòng;
  - cột không phải số, hoặc cột năm;
  - hai cột khác đơn vị;
  - ít hơn 2 điểm;
  - tham số thừa, trong đó có tham số đưa số.
- `show_chart` không tính vào giới hạn đọc kho và có trần riêng. Gọi trước khi có dữ liệu thì bị từ chối.
- AppTest trang chat:
  - biểu đồ hiện, rerun không gọi lại mô hình;
  - câu trả lời bị chặn thì không vẽ.

## 3. Eval với LLM thật: chốt bộ câu trước lượt gọi đầu

Ghi ngày 2026-10-16, **trước** lần gọi mô hình đầu tiên cho bộ này. Bộ `v` (V01–V07) trong `scripts/ops/ai_live_eval.py`.
Câu mới, khác câu trong `test_ai_charts.py`.

| Mục | Giá trị |
|---|---|
| Mã băm bộ câu | `025154a0c0baaa81` (cách băm sửa ngày 2026-10-16 để tập hợp lồng nhau ra cùng chuỗi ở mọi lần chạy) |
| Mã băm code chat + script eval | `11cdbd8704641902` |
| Bản dữ liệu | `fc14b8a2f5a24ff99a434d7c`, local DuckDB, chế độ versioned |
| Mô hình | `deepseek-flash` |

Chấm máy có thêm cột `bieu_do`. Khi lượt trả `ok`:
- biểu đồ phải từ đúng tool nguồn, đúng cột, đủ số điểm;
- dữ liệu vẽ phải bằng số dòng bằng chứng;
- ca không cần biểu đồ thì không được có biểu đồ.

| Câu | Câu hỏi | Trạng thái nhận | Biểu đồ khi `ok` | Đọc tay |
|---|---|---|---|---|
| V01 | Cho mình xem đường dự báo doanh thu gộp theo từng tháng | ok | `get_forecast` horizon, `g_forecast`, ≥ 18 điểm | nói là dự báo G; 07/2024 không vẽ như cả tháng; không gọi là số thực tế |
| V02 | Vẽ biểu đồ so sánh các model dự báo theo sai số tháng | ok | `get_forecast_backtest`, `mape_g_thang`, ≥ 10 điểm | nói là sai số backtest 2020–2022; nhắc thước chọn model là điểm ngày |
| V03 | Vẽ biểu đồ đóng góp của từng kênh vào thay đổi R năm 2019 | ok | `get_segment_contribution`, `contribution_to_delta` hoặc `delta_r`, ≥ 2 | nói là đóng góp số học, không phải nguyên nhân |
| V04 | Vẽ R đầu và cuối của các giai đoạn doanh thu | ok | `get_revenue_trend` phases, `r_start` / `r_end`, ≥ 4 | không gọi giai đoạn là nguyên nhân |
| V05 | Vẽ biểu đồ mùa vụ: tỷ lệ tháng cao nhất so với tháng thấp nhất qua các giai đoạn | ok | `get_calendar_pattern` mua_vu, `season_peak_trough_ratio`, ≥ 4 | nói rõ dòng 2013–2022 là cả kỳ |
| V06 | Vẽ R theo từng năm từ 2013 đến 2022 | unsupported, needs_clarification, ok | không bắt buộc; nếu có thì chỉ từ `get_revenue_trend` | nói chưa có chuỗi R từng năm; nếu vẽ giai đoạn thì nói rõ không phải từng năm; không ghép nhiều lần gọi một năm |
| V07 | Vẽ biểu đồ dự báo doanh thu năm 2025 | no_data | không vẽ | nói không có dự báo 2025 |

Lệnh: `RETAIL_RELEASE_MODE=versioned RETAIL_RELEASE_STATE=warehouse/pipeline/state.json .venv/Scripts/python.exe scripts/ops/ai_live_eval.py --set v --runs 3`.

## 4. Kết quả

### 4.1 Lần chạy chính (2026-10-16, prompt `b6-2026-10-16`)

| Mục | Giá trị |
|---|---|
| Log | `warehouse/ai_eval/live_20261016T000619Z_v_29536.jsonl` (mỗi dòng có biểu đồ: ref, tool nguồn, cột, số điểm, dòng không vẽ) |
| Số lượt | 7 câu × 3 lần = 21; mã băm bộ `025154a0c0baaa81`, code `11cdbd8704641902`, bản dữ liệu `fc14b8a2f5a24ff99a434d7c` |
| Chi phí | token vào 769.119, ra 10.181; **ước** 0,24 USD |
| Chấm máy | **18/21** |
| Chấm máy + đọc tay | **15/21** |

| Câu | Đạt | Nhận xét |
|---|---|---|
| V01 dự báo từng tháng | 3/3 | Biểu đồ `get_forecast` horizon, 18 điểm, 07/2024 không vẽ; câu trả lời nói rõ dự báo G, tháng 07/2024 chỉ 1 ngày |
| V02 so model theo sai số tháng | 3/3 | Biểu đồ `mape_g_thang` 15 ứng viên và mốc; nói thước chọn model là điểm ngày, sai số backtest 2020–2022 |
| V03 đóng góp từng kênh năm 2019 | 0/3 (máy 3/3) | Biểu đồ `delta_r` 6 kênh, số đúng; **không** nói "đóng góp số học, không phải nguyên nhân" (tiêu chí đọc tay ghi trước) |
| V04 R đầu / cuối giai đoạn | 3/3 | Biểu đồ hai cột `r_start`, `r_end`; nói "mô tả xu hướng, không phải nguyên nhân" |
| V05 mùa vụ | 0/3 | Biểu đồ dựng đúng (5 điểm) nhưng câu trả lời bị bước kiểm chặn: "tỷ lệ tháng **cao nhất** so với tháng **thấp nhất**" là tên chỉ tiêu, bị luật câu xếp hạng coi là câu xếp hạng không dẫn số. Lượt bị chặn thì không vẽ |
| V06 R từng năm (giới hạn) | 3/3 | `unsupported`, nói chưa có chuỗi R từng năm, gợi ý xem giai đoạn; không ghép nhiều lần gọi một năm |
| V07 dự báo 2025 | 3/3 | `no_data`, không vẽ |

**Lượt trượt: nguyên nhân và đề xuất (chưa sửa, chờ PM):**

| Câu | Lỗi của ai | Đề xuất |
|---|---|---|
| V05 | App (kiểm quá chặt) | Luật câu xếp hạng không coi "tháng cao nhất so với tháng thấp nhất" / "chênh mùa" là câu xếp hạng (đó là tên chỉ tiêu `season_peak_trough_ratio`) |
| V03 | Prompt / app | App tự gắn chú thích "đóng góp số học, không phải nguyên nhân" khi trả số của `get_segment_contribution` (như đã làm với phân rã N → U → P), thay vì trông vào câu văn của mô hình |

### 4.2 Chạy lại sau khi rút gọn prompt (bộ đã dùng, không phải nghiệm thu)

Sau lần chạy chính, prompt và schema được rút gọn (`b6-2026-10-16b`) để trường hợp xấu nhất vẫn chứa 3 lượt trong hạn mức 200.000 token
của phiên (test `test_tran_token_cung_ca_phien_khong_vuot_200k`; nay 199.629, dư rất ít). Chạy lại bộ V một lần
(`live_20261016T001226Z_v_*.jsonl`, ước 0,08 USD): 6/7 đạt chấm máy, cùng mẫu với lần chính (V05 vẫn bị chặn nhầm).

**Ghi chú về mã băm:** hàm băm bộ câu sửa ngày 2026-10-16 (tập hợp lồng nhau trước đây ra chuỗi khác nhau mỗi lần chạy). Bộ GM của B3c
không đổi nội dung; mã băm theo cách mới là `1176eaf10ab546c0` (mã cũ `34347d35334ab02e` ghi ở [ai_eval_b3c_du_bao.md](ai_eval_b3c_du_bao.md)).

### 4.3 Giới hạn

- Một mô hình, 3 lần mỗi câu, một bản dữ liệu local; chưa chạy trên Databricks.
- Chưa có ảnh chụp trang chat có biểu đồ (đã kiểm bằng AppTest).
- Chưa vẽ được R / G theo từng năm, từng tháng của một năm; nút mở trang kèm bộ lọc đã có từ 2026-10-17 ([ghi_chu_l2_airflow_rollback_20261017.md](ghi_chu_l2_airflow_rollback_20261017.md) mục 1).
- Phần dư token của trường hợp xấu nhất rất mỏng: thêm chữ vào prompt sẽ làm test trần 200k trượt; khi đó cần rút gọn tiếp hoặc PM quyết đổi hạn mức.

## 5. Sửa sau eval (PM duyệt 2026-10-17) và bộ câu mới N

PM chọn sửa cả hai đề xuất ở mục 4.1 và làm thêm chuỗi R / G từng năm. Chi tiết phần sửa và phần kiểm: [review](review_codex_ai_gd2_20261015.md) §9.11.

- **V05:** luật câu xếp hạng bỏ qua tên chỉ tiêu "tháng cao nhất so với tháng thấp nhất" trước khi tìm chữ xếp hạng; câu xếp hạng thật vẫn bị kiểm.
- **V03:** app tự in "Đóng góp của từng nhóm là phân rã số học…, không chứng minh nguyên nhân" dưới mọi câu trả lời có R theo nhóm (`ToolResult.notes`, không gửi cho mô hình). Log eval ghi các ghi chú này ở cột `app_notes`.
- **Chuỗi từng năm:** `get_revenue_summary` nhận thêm `to_year`, trả mỗi năm một dòng từ `rpt_revenue_yearly` (không thêm bảng); vẽ được thành đường; năm thiếu tháng (2012) không vào xếp hạng và không vẽ. Tool `v1.7`, catalog `b6-2026-10-17`.

### 5.1 Bộ N: chốt trước lượt gọi đầu

Ghi ngày 2026-10-17, **trước** lần gọi mô hình đầu tiên cho bộ này. Bộ `n` (N01–N05) trong `scripts/ops/ai_live_eval.py`, câu mới, khác câu trong `test_ai_chuoi_nam_ghi_chu.py`. `--kiem-rubric` bắt một lỗi rubric (N02 thiếu tiền tố `.derived`) và lỗi này đã sửa trước khi chốt.

| Mục | Giá trị |
|---|---|
| Mã băm bộ câu | `9e3f522b350f2947` |
| Mã băm code chat + script eval | `9602ec626245d7a5` |
| Bản dữ liệu | `fc14b8a2f5a24ff99a434d7c`, local DuckDB, chế độ versioned |
| Mô hình / prompt | `deepseek-flash`, prompt `b6-2026-10-17b` |

| Câu | Câu hỏi | Trạng thái nhận | Chấm máy | Đọc tay |
|---|---|---|---|---|
| N01 | Vẽ doanh thu gộp G từng năm từ 2015 đến 2021 | ok | `get_revenue_summary` 2015 → 2021, biểu đồ cột `g`, ≥ 7 điểm | một lần gọi cho cả chuỗi; gọi đúng là G |
| N02 | R năm nào cao nhất trong giai đoạn 2013–2022? | ok | dẫn `derived.highest_r.years`, có "2016" | không nói nguyên nhân |
| N03 | Cho mình R của từng năm 2012–2014 | ok | `get_revenue_summary` 2012 → 2014, dẫn ô `r` | nói 2012 thiếu tháng, không so ngang với năm đủ |
| N04 | Dự báo doanh thu gộp tháng 6/2023 là bao nhiêu? | ok | dẫn `g_forecast`, có "129.404.273" | `app_notes` có ghi chú "theo sai số tháng … sai ít hơn model chính"; câu văn không mâu thuẫn ghi chú |
| N05 | Vẽ đóng góp của từng vùng vào thay đổi R năm 2020 | ok | `get_segment_contribution` region 2020, biểu đồ ≥ 3 điểm | không nói nguyên nhân; câu "đóng góp số học" có trong câu văn hoặc `app_notes` |

Lệnh: `RETAIL_RELEASE_MODE=versioned RETAIL_RELEASE_STATE=warehouse/pipeline/state.json .venv/Scripts/python.exe scripts/ops/ai_live_eval.py --set n --runs 1`
(chạy 1 lần để vừa mức chi PM duyệt).

### 5.2 Kết quả (2026-10-17)

| Lần chạy | Log | Chấm máy | Đọc tay |
|---|---|---|---|
| Bộ V sau sửa, 2 lần (bộ đã dùng, không phải nghiệm thu), prompt `b6-2026-10-17` | `live_20261017T055345Z_v_28700.jsonl` | 12/14 | V03 2/2: câu văn nói "phân rã số học, không phải nguyên nhân", ghi chú app cũng hiện. V05 2/2: không còn bị chặn. V01, V02, V04, V07 đạt như trước. V06 0/2 theo tiêu chí khóa ngày 16/10 (chỉ nhận biểu đồ giai đoạn): nay chat vẽ R 10 năm 2013–2022 bằng `to_year`, nói đúng năm cao nhất 2016, thấp nhất 2021. Đây là lệch tiêu chí có chủ ý vì có chức năng mới, không sửa tiêu chí |
| Bộ N, 1 lần, prompt `b6-2026-10-17b` | `live_20261017T060936Z_n_29328.jsonl` | 4/5 | N02 bị chặn: mô hình viết `rows[2016]` (app chưa hiểu là dòng năm 2016) rồi `derived.highest_r.years[0]`. N01 viết "năm có G cao nhất là {số tiền}", không nêu năm. N03 nói 2012 thiếu tháng; N04 có ghi chú thước tháng; N05 có ghi chú nhóm và câu "phân rã số học" |
| N01, N02 sau khi sửa `rows[<năm>]` và lời tool | `live_20261017T061243Z_n_23140.jsonl` | 2/2 | N01 "Năm có G cao nhất là **2016**, với G là …"; N02 "R cao nhất giai đoạn 2013–2022 là năm **2016**" |

Chi phí ước (giá niêm yết): bộ V 0,15 USD, bộ N 0,05 + 0,02 USD.
