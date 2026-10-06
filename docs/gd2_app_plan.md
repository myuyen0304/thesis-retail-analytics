# Kế hoạch GĐ 2: app phân tích doanh thu bằng code

Lập ngày 2026-09-27, sau khi GĐ 1 xong: DWH local đủ KPI cho 5 PS, `dbt build` 155/155 PASS.
Roadmap chung: [`dwh_roadmap.md`](dwh_roadmap.md). Tài liệu cho PM/BA: [`dwh_huong_dan_pm_ba.md`](dwh_huong_dan_pm_ba.md).
Nguồn nghiệp vụ: deck `docs/presentations/revenue_performance_problem_statement_updated.pptx`.

## Bổ sung 2026-09-29: AI chat là hướng mở rộng đã chọn

Người dùng đã chọn bổ sung **chat hỏi dữ liệu PS1–PS5**, trả lời bằng query chỉ đọc có kiểm soát, metric/kỳ lọc rõ và bằng chứng số liệu/snapshot. Đây là hướng mới thay quyết định “không làm AI” ngày 2026-09-27; các ghi chú cũ bên dưới được giữ như lịch sử của GĐ 2. Chưa triển khai runtime chat, chưa chọn provider và không ghi các mốc app hiện tại thành nghiệm thu AI.

Đợt đầu xây [bộ skill Codex + Claude Code](agent_workflows.md). Sau này chat phải phân biệt R/G, distinct/tỷ lệ, quan sát và nguyên nhân; câu ngoài PS1–PS5 phải báo rõ. Databricks chỉ là lab DWH/KPI; Snowflake vẫn là đích production. Tiêu chí chat và bộ tình huống nằm trong skill `retail-ai-explain`; feature chat được thực hiện ở đợt riêng.

> PM đã quyết ở §9 (2026-09-27). **M0 xong, PM đã nghiệm thu** (32/32 test PASS, ảnh ở `docs/screenshots/streamlit/`). **M1 xong, PM đã nghiệm thu 2026-09-28** (58/58 test app, dbt 166/166). **M2 xong, PM đã nghiệm thu 2026-09-28** (68/68). Sau đó bổ sung 2 góp ý cho PS2 (tháng đổi hướng do dữ liệu tự tìm,
tăng trưởng tháng), nhãn giai đoạn và 3 góp ý PS3 (so sánh giai đoạn, độ ổn định, chú thích): 96/96 test app, dbt 192/192. **M3 (PS3) xong, PM đã nghiệm thu 2026-09-29.** **M4 (PS4 + PS5) xong, PM đã nghiệm thu 2026-09-29** sau góp ý vòng 1 (121/121 test app, dbt 202/202). **M5 (Sức khỏe dữ liệu + hoàn thiện) dev xong 2026-09-29, chờ PM nghiệm thu** (152/152 test app sau review ngoài, dbt 216/216). **2026-10-01: sửa thẻ và bảng nhiệt PS2–PS5 theo `streamlit_ps1_ps5_ui_feedback.md` (F01–F04), chờ PM xem**; bộ test app nay 157 test, lần chạy ngày này mới kiểm trên DuckDB. Mỗi mốc làm xong ghi nhật ký ở `dwh_huong_dan_pm_ba.md` §9.

---

## 1. Mục tiêu

Một app web chạy trên máy, đọc DWH và trả lời **5 câu hỏi của deck** theo đúng thứ tự tầng:

```text
Tầng 0 (PS1: đo đúng) → Tầng 1 (PS2: xu hướng) → Tầng 2 (PS3: nhịp lịch) → Tầng 3 (PS4, PS5: vì sao)
```

Người xem không cần biết SQL. Mỗi con số trên màn hình phải có **định nghĩa, kỳ phân tích và giới hạn** đi kèm.

## 2. Nguyên tắc thiết kế: app không chứa logic nghiệp vụ

Đây là quyết định quan trọng nhất của GĐ 2:

1. **Mọi con số trên màn hình = một cột của một bảng `reporting.rpt_*`.** App chỉ đọc và vẽ, không tính lại R, N, CAGR,
   phân rã… bằng pandas.
2. **Thiếu KPI thì thêm vào dbt, kèm test.** Không vá bằng code trong app.
3. Nhờ vậy, **các test của DWH (155 lúc lập plan, 166 sau M1, 169 sau M2, 180 sau góp ý M2, 192 sau góp ý M3, 202 sau M4, 216 sau M5 tính cả 2 hook ghi nhật ký) chính là bảo đảm đúng số của app**. Sang GĐ 3, logic đã nằm sẵn trong dbt nên chuyển lên
   Snowflake không phải viết lại.
4. **Ngoại lệ duy nhất là bộ lọc động** (khoảng ngày tùy chọn, lọc nhiều chiều cùng lúc). Phần này phải tính lại N, C bằng
   *đếm phân biệt* trên dòng hàng, không được cộng từ bảng tháng/năm. Vì vậy bộ lọc động để sang mốc riêng (M6), có test riêng.

## 3. Tiêu chí nghiệm thu

Lấy từ 6 gạch đầu dòng của GĐ 2 trong roadmap:

| # | Yêu cầu | Nghiệm thu khi |
|---|---|---|
| 1 | Đọc `rpt_*` đúng grain định sẵn | Test tự động: số app đọc được = số trong bảng `rpt_*`, không có phép tính nào khác |
| 2 | Lọc động phải tính lại N/C từ dòng hàng | (M6, làm sau M1–M5) Lọc đúng một năm thì ra đúng N, C của `rpt_revenue_yearly` |
| 3 | Trang nào cũng ghi kỳ phân tích, định nghĩa R/G, trạng thái snapshot, thời điểm refresh | Có dải thông tin chung ở đầu mọi trang; smoke test kiểm có dải này |
| 4 | N/U/P và C/F là phân rã số học, không phải nguyên nhân | Trang PS4, PS5 có câu cảnh báo lấy từ slide 10 và 12 |
| 5 | Giai đoạn PS2 lấy từ cấu hình BA, không hardcode | App đọc `rpt_revenue_phase` / `rpt_revenue_turning_point`; đổi seed thì app đổi theo |
| 6 | AI giải thích phải dẫn về số đã kiểm | **GĐ 2 ban đầu:** không áp dụng theo quyết định 2026-09-27. **Hướng mở rộng 2026-09-29:** chat PS1–PS5, chưa triển khai/nghiệm thu. |

## 4. Các trang

Mỗi trang có cùng bố cục: **câu hỏi PS → thẻ KPI → biểu đồ → "Cách đọc" → "Giới hạn"**. Dải thông tin chung ở đầu mọi trang đọc `rpt_build_info`.

| Trang | Trả lời | Nguồn (`reporting.*`) | Nội dung chính |
|---|---|---|---|
| **Tổng quan** | Bức tranh chung | `rpt_revenue_total`, `rpt_revenue_yearly` | G, R, R/G toàn kỳ; R theo năm; link sang 5 trang PS |
| **PS1: Đo đúng doanh thu** | Mỗi tháng/năm thực nhận bao nhiêu? | `rpt_revenue_bridge`, `rpt_revenue_total`, `rpt_revenue_yearly`, `rpt_revenue_monthly` | Thác G → R (hủy, trả, chưa giao, chiết khấu); R/G theo năm; tỷ lệ hủy |
| **PS2: Xu hướng** | Tăng hay giảm, giai đoạn nào đổi hướng? | `rpt_revenue_phase`, `rpt_revenue_turning_point`, `rpt_revenue_monthly`, `rpt_revenue_yearly`, `rpt_revenue_direction_change`, `ps2_direction_rule` | Đường `r_12m` có **tô nền 4 giai đoạn A–D**, đánh dấu **3 điểm đổi hướng** (cuối 2018 "giảm tăng tốc", cuối 2019 "đổi nhịp") và đỉnh/đáy do **dữ liệu tự tìm**; bảng CAGR; YoY năm; YoY tháng |
| **PS3: Nhịp lịch** | Dồn vào tháng nào, ngày nào, có lặp lại? | `rpt_revenue_monthly`, `rpt_revenue_yearly`, `rpt_revenue_total`, `rpt_august_parity`, `rpt_calendar_phase`, `rpt_calendar_phase_month`, `rpt_calendar_stability` | Heatmap chỉ số tháng × năm; mức dồn cuối tháng; tháng 8 năm lẻ/chẵn (−37,7%); độ ổn định 3 nhịp; so sánh giữa giai đoạn A–D |
| **PS4: Số đơn, số món, giá** | Đổi vì N, U hay P? | `rpt_revenue_yearly`, `rpt_driver_period`, `rpt_driver_bridge`, `driver_rule` | Chọn năm hoặc giai đoạn → biểu đồ thác: ΔR = contrib_n + contrib_u + contrib_p; so sánh giữa các năm và giai đoạn; bảng N, U, P, AOV |
| **PS5: Nhóm kéo lên/xuống** | Ngành hàng, khu vực, kênh nào? | `rpt_revenue_segment_yearly`, `rpt_revenue_yearly`, `rpt_driver_period`, `rpt_driver_bridge`, `driver_rule` | Chọn **một** chiều và một năm → xếp hạng ΔR, dịch chuyển tỷ trọng; ΔN = contrib_c + contrib_f. **Không bao giờ cộng 3 chiều với nhau** |
| **Sức khỏe dữ liệu** | Số có đáng tin không? | `rpt_health_summary`, `rpt_health_test`, `rpt_health_run`, `rpt_health_ingest` (view trên nhật ký dbt ở schema `ops` và `raw._ingest_log`) | Trạng thái chung; kết quả từng test của lần kiểm gần nhất; lần nạp gần nhất và số dòng từng nguồn; các lần chạy dbt gần đây |

**Sửa 2026-09-29 (M5):** bản đầu của plan đọc `retail_dbt/target/run_results.json`. Đổi sang nhật ký trong kho vì file đó
chỉ có một bản, lần build sau ghi đè: build DuckDB sau Postgres thì trang Postgres sẽ hiện kết quả test của DuckDB. Hook
`on-run-end` của dbt (`retail_dbt/macros/health_log.sql`) ghi kết quả vào chính kho đang build, nên mỗi backend có kết quả
riêng. Cách này được thiết kế để mang sang Snowflake ở GĐ 3 (không cần file trên máy), nhưng **chưa chạy thử**; log nạp
trên Snowflake (COPY INTO) còn phải xử lý riêng.

Chữ "Giới hạn" lấy từ slide 15, ví dụ:

- R theo trạng thái đơn lúc trích dữ liệu, không phải sổ kế toán;
- chưa rõ đơn vị tiền tệ (ngày 2026-10-05 PM chốt VND: app bỏ dòng này, ghi "Tiền: VND" ở dải thông tin chung);
- region chỉ là 3 nhãn của dữ liệu mô phỏng;
- các mối liên hệ chưa phải nguyên nhân.

## 5. Kiến trúc

```text
retail_dbt  ──dbt build──▶  schema reporting (Postgres local | DuckDB | Databricks lab | Snowflake ở GĐ 3)
                                        │  chỉ đọc
apps/retail_app/
  app.py                 điểm vào, điều hướng giữa các trang
  views/                 7 trang ở §4 (không đặt tên pages/: Streamlit coi đó là kiểu nhiều trang cũ)
  dwh/connection.py      1 chỗ duy nhất chọn backend: postgres (mặc định) | duckdb | databricks (lab) | snowflake (GĐ 3)
  dwh/queries.py         mỗi hàm = 1 câu SELECT từ một bảng rpt_*; không tính toán
  ui/                    dải thông tin chung, thẻ KPI, định dạng số kiểu Việt (1.234,5)
  tests/                 test số liệu + smoke test mọi trang
```

**Những khác biệt giữa các backend đã biết trước:**

- Target DuckDB không có `raw._ingest_log`, nên trang Sức khỏe dữ liệu phải hiện "không có log" chứ không báo lỗi.
- Snowflake viết hoa tên cột không đặt trong ngoặc kép, nên `queries.py` phải đổi tên cột về chữ thường sau khi đọc.
- DuckDB khóa file. Đã kiểm ở M0: app mở rồi đóng kết nối chỉ-đọc sau mỗi câu, nên `dbt build --target duckdb` vẫn PASS.
  Chiều ngược lại, trong lúc dbt ghi file thì app đọc bị lỗi (27/107 lần), vì vậy không build DuckDB trong lúc đang demo.
- Thư mục con của app không được trùng mẫu trong `.gitignore` (`data/`, `build/`, `lib/`, `target/`…). Vì thế dùng `dwh/`, không dùng `data/`.
- Hôm nay Docker từng không lên được vì lỗi WSL. Backend DuckDB là đường dự phòng để vẫn demo được.
- Databricks (thêm 2026-10-04, catalog `retail_lab`): đăng nhập bằng profile OAuth của Databricks CLI, đọc cấu hình ở
  `.env.databricks.local`; giờ TIMESTAMP trả về kèm múi UTC nên `connection.py` bỏ múi cho giống hai backend kia.
  Test so số với DuckDB ở `tests/test_databricks.py` chỉ chạy khi đặt `RETAIL_TEST_DATABRICKS=1` (máy không có
  workspace thì skip). Chat AI chưa hỗ trợ Databricks.

## 6. Các mốc

Mỗi mốc có tiêu chí xong riêng. Xong mốc nào ghi nhật ký mốc đó.

| Mốc | Làm gì | Xong khi |
|---|---|---|
| **M0: Nền** ✅ | Chốt framework (§9); cài thư viện bằng `uv pip install --python .venv/Scripts/python.exe`, ghim phiên bản vào `requirements.txt`; khung app, `connection.py` 2 backend | App mở được; đọc `rpt_revenue_yearly` qua cả Postgres và DuckDB ra **giống hệt nhau** |
| **M1: Tổng quan + PS1** ✅ | Dải thông tin chung, trang Tổng quan, trang PS1 | App hiện đúng G = 16.430.476.585,53; R = 12.518.175.957,20; R/G = 76,2%. Từ 2026-10-02 (góp ý PM) thẻ ghi gọn 16,43 tỷ / 12,52 tỷ; số đầy đủ nằm trong tooltip (?) của thẻ và test vẫn kiểm số đó |
| **M2: PS2** ✅ | Đường R 12 tháng, tô giai đoạn, 3 điểm đổi hướng, bảng CAGR | CAGR A–D và độ lớn 3 điểm trên app = các số đã chốt (+8,75%, −6,39%, −39,10%, −0,14%; −9,7%, −39,1%, −6,7%) |
| **M3: PS3** ✅ | Heatmap chỉ số tháng, mức dồn cuối tháng, tháng 8 | Tháng 8 năm lẻ/chẵn = −37,7%; `eom_excess` > 0 |
| **M4: PS4 + PS5** ✅ | Biểu đồ thác N/U/P; xếp hạng nhóm; C/F | Thác 2019: contrib_n = −572,4 triệu; ba phần cộng lại = ΔR; PS5 không có chỗ nào cộng 3 chiều |
| **M5: Sức khỏe dữ liệu + hoàn thiện** (dev xong, chờ PM nghiệm thu) | Trang Sức khỏe dữ liệu; smoke test mọi trang; hướng dẫn chạy | Smoke test 7/7 trang không lỗi trên cả 2 backend; cập nhật `dwh_huong_dan_pm_ba.md` (cách mở app) |
| **M6: Bộ lọc động** *(làm sau khi M1–M5 được nghiệm thu)* | Lọc khoảng ngày / nhiều chiều; tính N, C bằng đếm phân biệt trên dòng hàng | Model + test trong dbt; lọc trùng grain có sẵn thì ra đúng số của `rpt_*` |

## 7. Cách kiểm

1. **Test số liệu (pytest):** với mỗi hàm trong `queries.py`, so kết quả với bảng `rpt_*` tương ứng. Riêng các số của deck
   và của PS2 thì khóa cứng, giống `assert_rpt_deck_numbers` và `assert_rpt_phase`.
2. **So hai backend:** chạy cùng bộ test trên Postgres và DuckDB, kết quả phải giống hệt.
3. **Smoke test:** render từng trang ở chế độ không giao diện, không được có lỗi. Đã kiểm ở M0: Streamlit 1.64 có
   `streamlit.testing.v1.AppTest`, đang dùng trong `apps/retail_app/tests/test_smoke.py`.
4. **Demo cho PM/BA** sau mỗi mốc, kèm ảnh chụp màn hình trong nhật ký. Ảnh app lưu riêng ở `docs/screenshots/streamlit/`,
   đặt tên `<mốc>_<trang>[_<backend>].png` (ví dụ `m0_doc_lai_postgres.png`, `m2_ps2_xu_huong_duckdb.png`).

## 8. Phạm vi

**Không làm trong GĐ 2:**

- dự báo / SHAP (phần mở rộng riêng, CLAUDE.md §1);
- deploy Snowflake và host app trên cloud (GĐ 3);
- Kafka (GĐ 4);
- đăng nhập, phân quyền người dùng.

**Git:** theo quyết định của PM ngày 2026-09-27, code app **giữ ở local**. Tới GĐ 3, `apps/retail_app/` (trừ file cấu hình
chứa thông tin kết nối) sẽ vào bộ file production cùng `retail_dbt/`.

## 9. Quyết định của PM

**Đã quyết ngày 2026-09-27:**

- dùng **Streamlit**;
- app **chỉ để demo**, bỏ M6. **Sửa cùng ngày:** PM vẫn làm M6, nhưng chỉ bắt đầu sau khi M1–M5 được nghiệm thu;
- **không** làm AI giải thích ở GĐ 2 ban đầu; **được thay bằng hướng mở rộng chat PS1–PS5 ngày 2026-09-29**, xem phần bổ sung đầu tài liệu;
- giao diện **tiếng Việt**: PM không nêu, dev theo đề xuất.

Bảng dưới giữ lại để ghi lý do lúc đề xuất.

| Câu hỏi | Đề xuất của dev | Vì sao |
|---|---|---|
| **Framework nào?** | **Streamlit** | Toàn bộ vẫn là Python, không cần học thêm frontend; mỗi trang là một file, hợp với 7 trang ở §4. Việc host Streamlit ngay trên Snowflake sẽ **kiểm lại ở đầu GĐ 3**, hiện chưa khẳng định. Phương án khác: Dash (linh hoạt hơn, nhiều code hơn), hoặc FastAPI + React (đẹp nhất nhưng tốn gấp mấy lần công) |
| **App dùng cho ai?** | Demo trước hội đồng | Nếu chỉ để demo thì bỏ M6 (bộ lọc động), app gọn và chắc số hơn. Nếu BA dùng hằng ngày thì làm M6 |
| **Có AI giải thích số không?** | Chưa làm ở GĐ 2 | Muốn làm đúng thì mọi câu trả lời phải dẫn về câu query đã kiểm, phân biệt quan sát và giả thuyết. Nên để sau khi 5 trang PS chạy ổn |
| **Giao diện tiếng Việt?** | Có | Khớp deck và tài liệu (CLAUDE.md §0); tên cột kỹ thuật vẫn giữ tiếng Anh |
