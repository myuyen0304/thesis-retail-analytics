# Nhật ký AI Explain (chat hỏi dữ liệu PS1–PS5)

File này là **nhật ký gộp** của phần chat AI. Mỗi đợt làm thêm một mục ở §2, gồm: đã làm gì, kết quả, bằng chứng. Đồng thời cập nhật §3 (cần cải thiện) và §4 (sẽ làm tiếp).
Chi tiết kỹ thuật vẫn nằm ở các file riêng; ở đây chỉ tóm tắt và trỏ tới.

| File chi tiết | Nội dung |
|---|---|
| [ai_explain_plan.md](ai_explain_plan.md) | Kế hoạch gốc, kiến trúc, điều kiện chuyển mốc (§13) |
| [ai_explain_ai0_ai1.md](ai_explain_ai0_ai1.md) | AI0–AI1: hợp đồng câu hỏi, catalog, 3 tool đầu, tài khoản chỉ-đọc Postgres |
| [ai_explain_review_20261005.md](ai_explain_review_20261005.md) | Review độc lập: 4 lỗi kiểm câu trả lời |
| [ai_explain_ai2.md](ai_explain_ai2.md) | AI2: nối model, bộ kiểm câu trả lời, trang chat, nghiệm thu bộ H\* |
| [ai_explain_ai3.md](ai_explain_ai3.md) | AI3: 4 tool PS1–PS3, nghiệm thu A\*/B\*, chạy trên PostgreSQL |
| [dwh_huong_dan_pm_ba.md](dwh_huong_dan_pm_ba.md) §9 | Nhật ký bàn giao cho PM/BA của cả dự án |

Hạn tiến độ khóa luận: **2026-10-25**.

---

## 1. Hiện trạng (cập nhật 2026-10-09)

| Hạng mục | Trạng thái |
|---|---|
| Câu hỏi đang trả lời được | PS1 (G → R theo năm và cả kỳ, R/G một tháng); PS2 (4 giai đoạn, 3 điểm đổi hướng); PS3 (mùa vụ, dồn cuối tháng, tháng 8 năm lẻ); PS4 (phân rã N → U → P theo năm); PS5 (đóng góp theo ngành, vùng, kênh theo năm); định nghĩa chỉ tiêu |
| Tool | 7 tool + tool định nghĩa, phiên bản `v1.4` (thêm xếp hạng phía nhỏ cho nhóm); catalog `ai3-2026-10-05`; prompt `ai3-2026-10-09b` |
| Model | `deepseek-flash`, tắt chế độ suy nghĩ; tối đa 4 lần đọc kho mỗi câu; **trần cứng** 200.000 token mỗi phiên (dừng trước khi gọi nếu lần gọi tiếp có thể vượt) |
| Kho đọc được | DuckDB local, PostgreSQL local (role chỉ-đọc `retail_ai_ro`), **Databricks `retail_lab`** (service principal chỉ-đọc `retail-ai-ro`, từ 2026-10-06); cả ba đều chỉ đọc đúng 14 bảng. Chưa có Snowflake |
| Test không gọi model | Test AI 315/315; toàn bộ test app 475 đạt, 26 bỏ qua (đều cần Databricks) |
| Model thật, bộ nghiệm thu mới nhất (C\*, soạn sau khi sửa) | DuckDB 30/30, PostgreSQL 30/30; đọc tay 0 lỗi chặn; số âm hiện đúng dấu |
| Model thật, toàn bộ 105 câu trên PostgreSQL (sau sửa) | 104/105; câu trượt bị chặn an toàn (§3 mục 10) |
| Model thật, bộ F\* (phía "ít nhất", 2026-10-09) | DuckDB: F01–F07 21/21; F08–F09 (phần chưa có phía nhỏ) 6/6 sau sửa; đọc tay 0 số sai |
| Model thật, bộ D\* (câu xếp hạng, 2026-10-09, sau khi sửa §3 mục 10) | DuckDB 34/36; đọc tay 0 số sai; D11 trả lời lệch, đã sửa (§3 mục 12), D11 sau sửa 3/3 |
| Nhánh | `app/myuyen`, **chưa push** |

---

## 2. Nhật ký

### 2026-10-03: AI0–AI1, hợp đồng câu hỏi và công cụ query (chưa có model)

- **Làm:** catalog chỉ tiêu, ma trận khả năng (câu nào mở, câu nào đóng), 3 tool: R/G theo năm, phân rã N/U/P, đóng góp theo nhóm. Đường đọc riêng cho AI: tham số hóa, giới hạn thời gian và số dòng, kiểm chất lượng kho trước khi trả số.
- **PostgreSQL:** tạo role chỉ-đọc `retail_ai_ro`; guard kiểm tra role không phải superuser và không ghi được.
- **Kết quả:** test DuckDB và PostgreSQL đều đạt; số khớp CSV ở mọi năm × chiều đang mở.
- **Chi tiết:** [ai_explain_ai0_ai1.md](ai_explain_ai0_ai1.md).

### 2026-10-04: PM chọn nhà cung cấp model

- PM chọn DeepSeek. Khóa API do PM tự đặt trong `.env.ai.local`, không gửi vào chat.

### 2026-10-05 (sáng): AI2, nối model và trang chat

- **Làm:** nối model; vòng gọi tool; **bộ kiểm câu trả lời** (model chỉ viết câu có chỗ đặt `{cX}`, app kiểm từng chỗ đặt trỏ đúng ô dữ liệu rồi tự điền số); trang chat **Hỏi dữ liệu (AI)**.
- **Review độc lập** bắt 4 lỗi kiểm câu trả lời, ví dụ số G hiện dưới nhãn R, hay "R 2019 là 10 tỷ" vẫn được chấp nhận. Đã sửa cả 4 và thêm test hồi quy.
- **Model thật lần đầu** (22 câu chuẩn × 3): 65/66 với prompt cuối. Câu trượt bị chặn an toàn, người dùng chỉ thấy bảng số.
- **Chi tiết:** [ai_explain_ai2.md](ai_explain_ai2.md) §0, [ai_explain_review_20261005.md](ai_explain_review_20261005.md).

### 2026-10-05: nghiệm thu chuyển mốc AI2 → AI3 trên bộ cách hỏi mới

- **Vì sao cần:** bộ 22 câu đã dùng để chỉnh prompt nên không còn khách quan.
- **Làm:** soạn bộ H\* gồm 30 câu chưa dùng để chỉnh; chốt rubric và commit (`a34b12f`) trước khi chạy.
- **Kết quả:** **90/90**, đọc tay 0 lỗi chặn → đạt điều kiện chuyển sang AI3.
- **Chi tiết:** [ai_explain_ai2.md](ai_explain_ai2.md) §0b.

### 2026-10-05: AI3, mở PS1–PS3

- **Làm:** 4 tool mới (G → R, tháng, giai đoạn và điểm đổi hướng, nhịp lịch); số đối chứng tính độc lập từ CSV, khớp từng cent.
- **Nghiệm thu lần 1 (A\*, 20 câu × 3):** 56/60. **Bắt được lỗi chặn:** hỏi "Streetwear tháng 5/2019" thì model trả số toàn công ty, tức bỏ ngầm bộ lọc ngành.
- **Sửa bằng code, không chỉ dặn trong prompt:** hỏi một nhóm thì câu trả lời phải có số của đúng nhóm đó; hỏi nhóm theo tháng hoặc quý thì trả "chưa hỗ trợ".
- **Nghiệm thu lần 2 (B\*, bộ mới, 10 câu × 3):** **30/30**, đọc tay 0 lỗi chặn.
- **Sự cố:** chạy song song hai lượt nên ghi chung một file log và log bị hỏng. Đã đổi tên file log, thêm tên bộ và pid.
- **Chi tiết:** [ai_explain_ai3.md](ai_explain_ai3.md) §1–§4.

### 2026-10-05 (chiều): chạy model thật trên PostgreSQL

- **Làm:** kiểm guard, kiểm rubric trên PostgreSQL (95/95), rồi chạy model thật.
- **Kết quả:** B\* × 3 **30/30**; toàn bộ 95 câu × 1 **93/95**.
- **Hai câu trượt** không do PostgreSQL: một câu gắn nhãn trạng thái chưa chuẩn; một câu bị bộ kiểm chặn đúng (§3, mục 2–3).
- **Đọc tay:** phát hiện lỗi mất dấu âm gặp nhiều hơn dự kiến (§3, mục 1).
- **Chi tiết:** [ai_explain_ai3.md](ai_explain_ai3.md) §4b.

### 2026-10-05 (tối): PM chốt Databricks production; kiểm khả thi trên workspace

- **Quyết định:** Databricks là production cho DWH, app và chat AI. Dev và test local trước rồi mới deploy.
- **Kiểm** (profile `retail-dev`, được PM cho phép; chỉ đọc + một lần chạy thử đã xóa):
  - serverless gọi được `api.deepseek.com` (401 từ DeepSeek vì không kèm khóa), `pypi.org`, `example.com`;
  - có sẵn 9 endpoint chat do Databricks host, trong đó có `databricks-deepseek-v4-flash-0731`;
  - 1 SQL warehouse 2X-Small; chưa có app, chưa có service principal; `retail_lab` chưa cấp quyền cho ai, mọi bảng thuộc tài khoản PM.
- **Giới hạn bản Free** (tài liệu chính thức): tối đa 3 app; app chạy tối đa 24 giờ sau mỗi lần khởi động; gọi ra internet giới hạn ở một số domain tin cậy.

### 2026-10-05 (tối): sửa lỗi số âm mất dấu và các lỗi mức vừa

- **Làm** (commit `4b8b63c`, `7897f31`):
  - **Số âm mất dấu:** app chỉ in giá trị tuyệt đối khi chữ "tăng/giảm" đứng **sát** trước số (≤ 3 chữ, không qua ngoặc/phẩy/gạch); còn lại in dấu thật. Chữ hướng sát trước mà ngược dấu thì chặn.
  - **Tháng cao/thấp cả kỳ:** tool mùa vụ có thêm `rows[0].peak_month / trough_month` (cả kỳ) và `n_phases_same_peak / _trough` (số giai đoạn cùng tháng).
  - **Nhãn năm ngoài dữ liệu:** prompt quy tắc 6: hỏi số thực tế thì trả "không có dữ liệu", hỏi dự báo thì trả "chưa hỗ trợ".
  - **Trần token cứng:** mỗi request gửi kèm trần output 2.048 token; trước khi gọi, app cộng cận trên của prompt (số byte), không đủ chỗ thì dừng. Output bị cắt thì không hiện.
  - **Quyền Postgres:** dbt tự cấp lại SELECT cho role AI sau mỗi lần build (hook `on-run-end`, đúng 14 bảng).
- **Kiểm không gọi model:** test AI 289 → **315**, đều đạt. Mỗi test mới đã được thử ngược: tạm trả code về cách cũ thì test trượt (7 test dấu âm; test trần token vượt lên 205.116 token).
- **Kiểm Postgres thật:** thu hồi quyền → tool báo thiếu quyền → `dbt build` (217/217) → tool đọc lại được (rubric 105/105), **không** chạy script cấp quyền. Build DuckDB cũng 217/217.
- **Model thật:**

  | Lượt | Kết quả |
  |---|---|
  | **C\*** (bộ mới, chốt ở commit trước khi chạy) × 3, DuckDB | **30/30**, đọc tay 0 lỗi chặn |
  | **C\*** × 3, PostgreSQL | **30/30**, đọc tay 0 lỗi chặn |
  | E15, E15b, H15, A04d × 10 (sau sửa) | 39/40; **nhãn trạng thái đúng 40/40** (E15 10/10 "không có dữ liệu"). Lượt trượt: A04d bị rubric cấm cụm "sẽ thấp" bắt nhầm câu từ chối đúng ("không thể nói tháng 8/2023 sẽ thấp hay không"). **Không** sửa rubric sau khi xem kết quả |
  | Toàn bộ 105 câu × 1, PostgreSQL (sau sửa) | 104/105; A03 bị chặn an toàn (§3 mục 10) |

  - Cận trên prompt đúng ở **cả 391 lần gọi** (luôn ≥ 3,01 lần số thật).
  - Quét 125 số âm đã hiện: 25 số in không dấu, cả 25 đều có chữ "giảm" đứng sát trước.
- **Rubric mới:** `must_neg` kiểm số âm phải đọc ra là âm. Rubric cũ chỉ kiểm chuỗi "6,4", nên lỗi B06 lọt qua 30/30. Bộ chấm này viết độc lập với code đang kiểm và có test riêng.
- **Chi phí ước:** khoảng 0,86 USD.
- **Chi tiết:** [ai_explain_ai3.md](ai_explain_ai3.md) §4c.

### 2026-10-06: đường đọc chỉ-đọc cho chat trên Databricks (B1, local, chưa đổi gì trên cloud)

- **PM chốt:** model production giữ API DeepSeek (khóa **mới** trong secret của Databricks); làm Databricks trước §3 mục 10.
- **Thiết kế:** chat đọc Databricks bằng **service principal riêng** (`RETAIL_AI_DBX_CLIENT_ID/_SECRET`), không bao giờ dùng tài khoản đăng nhập của PM. Trước mỗi lần đọc, guard kiểm 4 luật:
  1. đúng danh tính đã cấu hình;
  2. không là owner của đối tượng nào;
  3. không có quyền nào ngoài USE + SELECT đúng 14 bảng (gồm cả quyền **thừa kế**, mà các view quyền của Unity Catalog đã liệt kê sẵn);
  4. không nhìn thấy bảng nào khác.
- **Ngoại lệ:** bản Free cấp sẵn quyền cho mọi tài khoản, nên guard chấp nhận **7 ngoại lệ có tên**, PM duyệt ngày 10-06:
  - `samples`;
  - USE `system`;
  - sandbox `workspace.default`;
  - `system.ai`;
  - Marketplace;
  - CREATE_MANAGED_STORAGE trên vị trí lưu trữ quản lý;
  - `information_schema`.

  Trong `retail_lab` không có ngoại lệ nào.
- **Giới hạn:** Databricks không có snapshot xuyên câu như Postgres. Tool đọc lại build marker cuối lượt; kho dựng lại giữa chừng thì không trả số.
- **Kiểm:**
  - test mới 37 đạt; toàn bộ test app **512 đạt**, 109 bỏ qua (cần cloud);
  - thử ngược 8 đột biến (tắt từng luật, nới ngoại lệ, bỏ đọc lại build marker, sai kiểu tham số): cả 8 làm test trượt;
  - test thật, chỉ đọc: tài khoản PM **bị từ chối** (sai danh tính; và là owner nếu cấu hình nhầm).
- **Đo:** warehouse nguội, câu đầu mất 21,8 giây, nên timeout Databricks là 60 giây; 3 câu kiểm quyền mất khoảng 4,9 giây mỗi lần gọi tool.
- **Phát hiện:** kho trên Databricks đang lệch lần dựng (health 10-03, 8 bảng sửa 10-05), nên phải `dbt build` lại trước khi chat đọc.
- **Commit:** `c03ab57` (đường đọc + test), `dc2dbc2` (hook dbt cấp SELECT cho SP; id lấy từ `.env.ai.local` qua `run_dbt.py`).
- **Còn lại:** B2 (build lại kho, tạo SP, cấp quyền) → B3 (so số với DuckDB, model thật) → B4 (deploy app). Các bước này cần cloud; hỏi PM trước mỗi bước.

### 2026-10-06: B2, dựng lại kho Databricks + danh tính AI (PM duyệt 5 bước)

- **Sửa thêm sau review**, commit `b7e189c`:
  - guard **tự kiểm**: phải nhận ra USE + SELECT đủ 14 bảng của chính SP, không thì từ chối. Lý do: nếu `grantee` ghi theo dạng khác danh tính, các luật khác sẽ âm thầm không áp dụng;
  - `known_groups` không còn nhớ lỗi thành tập rỗng. Tập rỗng đồng nghĩa "câu hỏi không lọc nhóm", tức tắt ngầm phép chặn bỏ bộ lọc;
  - thử ngược: 10/10 đột biến bị test bắt.
- **Cloud** (profile `retail-dev`):
  1. tạo SP `retail-ai-ro` (application id `fe5ce5de-9655-499a-bd2e-db61c0b2af7b`, quyền Databricks SQL access) và OAuth secret 90 ngày, **hết hạn 2027-01-04**. Secret ghi thẳng vào `.env.ai.local`, không in ra;
  2. CAN_USE trên warehouse `95d9f64890e29b5f`;
  3. trước khi build, SP mở phiên: khớp danh tính, **không có quyền thừa nào ngoài 7 ngoại lệ**, chỉ thiếu SELECT (đúng như dự kiến);
  4. `dbt build` đủ (commit `b7e189c`): **217/217**. Health `tot`, cùng lần dựng với build_info. `grantee` ghi đúng application id, SELECT đủ 14 bảng; SP đọc R 2019 = 864.329.801,94, khớp DuckDB;
  5. thử hook: thu hồi SELECT `rpt_revenue_yearly` → tool từ chối và nêu đúng bảng thiếu → build lần 2 → hook cấp lại (SP qua được guard).
     - Build lần 2 **hỏng do mạng**: kết nối bị đóng, 1 test chờ 1.972 giây; 205 đạt, 1 lỗi, 11 bỏ qua. Kho thành `loi_test` và **chat từ chối trả số** (`quality_blocked`), đúng thiết kế.
     - Build lần 3: **217/217**, kho về `tot`.
- **DuckDB** build lại từ cùng commit: 217/217.
- **Đo:** mỗi lần gọi tool trên Databricks mất khoảng 13–16 giây (guard 3 câu + dữ liệu, warehouse 2X-Small). Sẽ đo trọn câu hỏi ở B3.
- **Quy tắc vận hành:** trên Databricks production **chỉ build đủ**, không `-s`. Build một phần dựng lại vài bảng mà không chạy lại health; nhiều khả năng đó là nguyên nhân kho lệch ngày 10-05.
- **Gói deploy** (commit `f633158`, chưa deploy):
  - `deploy/databricks_app/` (`app.yaml`, `requirements.txt` ghim phiên bản) và `scripts/databricks/build_app_bundle.py`;
  - trang đọc bằng SP của app; `RETAIL_BACKENDS=databricks`;
  - chạy thử gói trên máy: 8/8 trang mở được, hash định nghĩa khớp repo.

### 2026-10-06: B3, chat chạy trên Databricks bằng SP chỉ-đọc (chỉ đọc + model thật)

| Kiểm | Kết quả |
|---|---|
| Rubric bằng tool, toàn bộ 105 câu (`--kiem-rubric --set tat_ca --backend databricks`) | **105/105** |
| So số Databricks với DuckDB: 83 tổ hợp tool đang mở (`tests/test_ai_databricks.py`, `RETAIL_TEST_DATABRICKS=1`); hai kho dựng từ cùng commit `b7e189c` | **khớp chính xác** (Decimal); cả file 124 đạt, mất 19 phút |
| Tài khoản PM mở phiên AI (cloud thật) | bị từ chối |
| Model thật bộ **C\*** × 3 (**kiểm ngang backend**, prompt không đổi `ai3-2026-10-05c`, code `f633158`) | **30/30**; đọc tay 0 lỗi chặn, dấu âm đúng (−6,4%, −39,1%, −9,7%, −0,1%) |

- **Thời gian:** mỗi câu mất khoảng 11–14 giây (1 lần gọi tool), câu bị từ chối không cần tool mất khoảng 1 giây.
- **Token:** 60 lần gọi, 0 lần vượt cận trên prompt.
- **Chi phí ước:** khoảng 0,13 USD.
- **Log:** `warehouse/ai_eval/live_20261006T053356Z_ai3c_12564.jsonl`.
- **Chưa kiểm:** app chạy trên Databricks Apps có gọi được DeepSeek không (B4).

### 2026-10-06: B4, chuẩn bị deploy (PM duyệt)

- **Đã làm:**
  - scope `retail-ai` gồm `ai-sp-client-id` và `ai-sp-client-secret`, đưa vào bằng SDK, không in ra; chỉ PM có quyền MANAGE;
  - tạo app `retail-analytics` (chưa chạy): URL `https://retail-analytics-7474650611714585.aws.databricksapps.com`, SP của app `053217a2-6d16-409a-bfde-080805aceb04`, resource gồm warehouse và 2 secret của SP AI;
  - hook dbt (commit `92d63bd`) cấp SELECT **đúng 21 bảng** của các trang cho SP của app. Chạy `run-operation`, rồi kiểm: SP app 21 bảng, SP AI 14 bảng;
  - gói code `92d63bd` tải lên `/Workspace/Users/.../retail-analytics-app` bằng `workspace import-dir`. `databricks sync` không dùng được vì bỏ qua thư mục `build/` (bị gitignore).
- **Khóa DeepSeek (PM làm 2026-10-07):** khóa **mới chỉ cho Databricks**, PM tự đưa vào `retail-ai/deepseek-api-key` (terminal riêng).
  Khóa cũ giữ trong `.env.ai.local` cho local; chỉ thu hồi khi nghi bị lộ.

### 2026-10-07: B4, deploy app trên Databricks Apps

- **Lỗi 1:** `No matching distribution found for numpy==2.5.1`: Databricks Apps chạy **Python 3.11** (pip 24.0), numpy 2.5.x đòi ≥3.12.
  Sửa: numpy 2.4.6. Toàn bộ test app chạy lại trên Python 3.11: 517 đạt, 109 bỏ qua do thiếu cấu hình cloud (`2425dbf`).
- **Lỗi 2:** app crash `Invalid value for '--server.port': '${DATABRICKS_APP_PORT:-8000}'`: `command` không chạy qua shell.
  Sửa: bỏ `--server.port/--server.address`, runtime tự đặt qua `STREAMLIT_SERVER_PORT/ADDRESS` (`fdb8681`).
- **Kết quả:** deployment `01f1c21213781b3ab17c57ce9d75624e` SUCCEEDED, server cổng 8000, health 200.
- **12:20 UTC:** Databricks tự tắt compute: *"App compute was stopped due to workspace or account status"*; bản deploy đang chạy
  bị gỡ (`active_deployment` = null). `system.billing.usage`: 06/10 SQL 10,56 DBU không bị tắt; 07/10 SQL 2,84 + APPS 3,78 DBU bị tắt.
  Ngưỡng của bản Free không công bố, nên chỉ ghi là quan sát.

### 2026-10-08: bật lại app; bản public trên Streamlit Community Cloud (PM chọn)

- **Bật lại:** `apps start` → compute ACTIVE, tự deploy lại từ workspace (`BUILD_REVISION` = `fdb8681`), RUNNING.
  Hướng dẫn PM tự làm: `docs/databricks_app_van_hanh.md`.
- **Lý do có bản public:** Databricks Apps bắt người xem đăng nhập workspace, không có chế độ công khai. Giao diện chạy trên
  Streamlit Community Cloud; dữ liệu vẫn đọc `retail_lab` trên Databricks. PM chọn: chat tự do, khóa DeepSeek riêng cho bản public;
  tắt app Databricks khi bản Streamlit ổn.
- **Danh tính:** trên Databricks Apps nền tảng tự cấp SP cho các trang; ngoài Databricks thì không. **Không** dùng `retail-ai-ro`
  cho các trang (nới quyền là nới guard). Tạo SP `retail-web-ro` (application id `f1e26aa2-0daf-4aaf-987f-b6cbf55d07e1`, secret hết hạn
  2027-01-06); hook dbt cấp SELECT đúng `app_read_relations` qua env `RETAIL_WEB_DBX_PRINCIPAL`; chạy `run-operation`, kiểm lại:
  21 SELECT + USE CATALOG `retail_lab` + USE SCHEMA `reporting`, không gì thêm.
- **Không sửa code app:** Streamlit nạp Secrets lúc khởi động server và đặt các khóa gốc thành biến môi trường
  (`streamlit/web/bootstrap.py` → `secrets.load_if_toml_exists()`); `connection.py`, `provider.py`, `guarded.py` đều đọc biến môi trường.
- **Thư viện:** `deploy/databricks_app/requirements.txt` chuyển thành `apps/retail_app/requirements.txt`. Streamlit Cloud ưu tiên file
  cùng thư mục với entrypoint hơn file ở root (root có numpy 2.5.1 và dbt); `build_app_bundle.py` chép file này ra gốc gói Databricks.
- **Kiểm giả lập trên máy (Python 3.11):** chạy gói `build/databricks_app` (không file `.env`, `DATABRICKS_CONFIG_FILE` trỏ file không có),
  biến môi trường lấy từ `.env.streamlit_cloud.local`; kiểm `connection.ROOT` là gốc gói và nguồn ghi "SP của app".
  8/8 trang không lỗi; chat qua SP AI + DeepSeek: C01 `ok` (CAGR −6,4%), C07 `no_data`, C08 `unsupported`.
  Lần chạy đầu nạp nhầm code từ repo (đọc profile của PM); đã sửa script và chạy lại, chỉ tính lần sau.
- **Test:** `test_dbt_cap_lai_quyen_ai_dung_danh_sach_tool` đạt (kiểm thêm env `RETAIL_WEB_DBX_PRINCIPAL` dùng danh sách bảng của trang).
  Các test PostgreSQL chưa chạy lại vì Docker đang tắt.
- **Chưa làm (PM):** deploy trên share.streamlit.io theo `docs/streamlit_cloud_deploy.md`, bật public, smoke; sau đó `apps stop` app Databricks.

### 2026-10-09: bản public chạy trên Streamlit Community Cloud

- **PM deploy** theo `docs/streamlit_cloud_deploy.md`: nhánh `app/myuyen` (commit `0f07cc5`), entrypoint `apps/retail_app/app.py`,
  Python 3.11. Link: https://retail-analytics-ps.streamlit.app/
- **Kiểm từ ngoài, ẩn danh** (không đăng nhập, chỉ cookie phiên do Streamlit Cloud cấp): `/~/+/_stcore/health` = `ok`;
  `api/v2/app/status` báo `viewerAuthEnabled: false` (mở công khai), `streamlitVersion` 1.64.0 (đúng file thư viện đã ghim).
- **Smoke qua websocket của Streamlit** (`scratchpad/smoke_public.py`, chạy từng trang như người xem): 8/8 trang không exception,
  không `st.error`; Tổng quan ghi nguồn Databricks catalog `retail_lab`, `rpt_revenue_yearly` 11 dòng.
  Không gửi câu chat trong lần kiểm này.
- **Chưa làm:** PM hỏi thử 3 câu chat (C01, C07, C08) trên link public; sau đó `apps stop` app Databricks.

### 2026-10-09: sửa lỗi câu xếp hạng (§3 mục 10), nghiệm thu bằng bộ D\*

- **Lỗi cũ:** model viết câu nối "Đây (cũng) là giai đoạn giảm mạnh nhất…" ngay sau câu đã dẫn số của giai đoạn đó, nhưng câu nối
  không có chỗ đặt xếp hạng nên bị chặn. Trong log cũ, lỗi này gặp ở A03, A03d, C02 (C02: 3/6 lượt phải sửa) và E05; A03 có lượt
  bị chặn hẳn, chỉ hiện bảng số.
- **Đã làm (commit `09b9930`, nhánh `app/myuyen`, chưa push):**
  - `evidence.py`: app **tự đối chiếu** câu nối. Đại từ ở đầu câu ("đây", "đó", "giai đoạn này", "ngành này"…) phải trỏ về đúng
    MỘT giai đoạn / nhóm / điểm đổi hướng mà câu ngay trước đã dẫn số. App kiểm đối tượng đó có đứng đầu `derived.largest_*`
    (tính trên đủ tập) theo chiều tăng/giảm của câu không. Không tin lời model; giống cách đã làm với câu gọi tên N/U/P.
  - Kiểm **tiêu chí**: câu nói "theo CAGR" thì phải có chỗ đặt `largest_*_cagr`, "bằng tiền" thì `largest_*`, "cả … lẫn …" thì cả
    hai. Câu nối không nêu tiêu chí thì giai đoạn phải đứng đầu theo **cả hai** mới qua.
  - Chặn thêm: "nhỏ nhất / ít nhất" dẫn `largest_*` (đó là phía ngược); thêm chữ "dẫn đầu" vào danh sách từ xếp hạng (trước đây
    câu có chữ này không bị kiểm). Câu "thành phần đóng góp nhiều nhất là P" không có chữ tăng/giảm thì lấy chiều theo ΔR (live H04c).
  - Lời nhắc sửa cho model nêu đúng đường dẫn cần dùng theo tiêu chí; prompt thêm ví dụ câu xếp hạng (`ai3-2026-10-09`).
  - Log eval lưu thêm câu trả lời lần đầu (`raw_first`) và đếm số lượt phải sửa vì câu xếp hạng: chấm tự động không thấy lỗi này
    vì phần lớn được sửa ở lần thử lại.
- **Kiểm không gọi model:**
  - 3 test mới trong `tests/test_ai_chat.py`: 6 câu nối đúng phải qua; 8 kiểu sai phải bị chặn (giai đoạn không đứng đầu, ngược
    chiều, câu trước nói hai giai đoạn, chú thích trong ngoặc, thiếu tiêu chí CAGR, "nhỏ nhất", câu "lặp lại ở cả {n_phases}").
  - Chạy lại offline **1.082 câu trả lời cuối** trong mọi log live cũ (dựng lại kết quả tool từ lời gọi đã log, DuckDB): không câu
    nào trước qua mà nay bị chặn; 1 câu A03 trước bị chặn nay qua (A đứng đầu cả tiền lẫn CAGR, app đã đối chiếu).
  - Test AI trên DuckDB: 272 đạt. 87 test lỗi đều vì **Docker Desktop tắt** (86 test `_pg_` không nối được PostgreSQL; 1 test giao
    diện đổi sang backend postgres bị dừng ở bước đọc `build_info`: "ConnectionTimeout"). **Bật Docker, chạy lại cùng ngày (sau cả đợt "ít nhất"): 124/124 test PostgreSQL đạt.**
- **Model thật, bộ D\*** (12 câu soạn sau khi sửa, commit trước lần gọi đầu; DuckDB, 3 lượt, `deepseek-flash`, prompt
  `ai3-2026-10-09`, code `09b9930`; log `warehouse/ai_eval/live_20261009T085911Z_d_28660.jsonl`, ~0,19 USD):
  - chấm tự động **34/36**; câu xếp hạng **3/36** lượt phải sửa ở lần đầu, đều là D11 (câu bẫy "giảm ít nhất");
  - D01 lượt 1 trượt chấm vì trỏ ô CAGR qua `largest_decrease_cagr.cagr` thay vì `.phases`; nội dung đúng (§3 mục 14);
  - D11 lượt 1 bị chặn đúng (model khẳng định "ngành giảm ít nhất", tool không xếp phía này); lượt 2, 3 qua nhưng **trả lời lệch**
    sang "ngành kéo giảm nhiều nhất" (§3 mục 12);
  - đọc tay: **0 số sai**, không câu nào nói nguyên nhân; câu nối mới hiện thật ở D09 ("Đây đúng là giai đoạn giảm mạnh nhất theo cả
    mức đổi R bằng tiền lẫn CAGR") và D12.
- **So trước / sau trên đúng câu cũ** (C02, A03, A03d × 3 lượt, ghi "sau sửa"; log `live_20261009T090143Z_tat_ca_28568.jsonl`):
  **9/9** đạt, **0/9** lượt phải sửa câu xếp hạng (trước: C02 phải sửa 3/6 lượt, A03 có lượt bị chặn hẳn). Bộ C\*, A\* đã dùng nên
  đây là đối chiếu, không phải nghiệm thu.
- **Sửa thêm sau khi đọc D\* (commit `24c86d5`; D\* đã dùng nên các lần chạy dưới đây là "sau sửa", không phải nghiệm thu):**
  - Review thấy câu nối có thể cho qua xếp hạng sai về **chỉ tiêu khác**: "West giảm … Vùng này chiếm tỷ trọng lớn nhất" sẽ qua
    vì câu không có chữ tăng/giảm và app lấy chiều theo dấu ΔR. Nay câu nối **bắt buộc có chữ tăng/giảm** và không được nói về
    tỷ trọng / mức cao thấp; thêm test chặn đúng câu này.
  - D11 trả lời lệch một phần là **do lời nhắc sửa của app**: lời nhắc gợi ý `derived.largest_*.phases` (câu hỏi về ngành) và
    gợi ý mở câu bằng "Đây là…", nên model đổi "ít nhất" thành "nhiều nhất". Nay lời nhắc cho câu "nhỏ nhất / ít nhất" nói thẳng:
    tool không xếp phía này, bỏ câu xếp hạng, nêu số từng nhóm hoặc trả `unsupported`, **không đổi sang phía lớn nhất**; gợi ý
    `.phases` chỉ hiện khi lượt đó có kết quả giai đoạn. Câu chỉ nói giới hạn của tool ("dữ liệu chỉ xếp hạng phía giảm nhiều
    nhất…"), không có số và không gọi tên nhóm, không bị coi là câu xếp hạng.
  - Chạy lại offline 1.130 câu trả lời cuối: so với `09b9930` không câu nào đổi kết quả; so với code trước ngày 09/10, 10 câu trả
    lời hôm nay (D09, D12, A03, A03d, C02) sẽ bị chặn nếu dùng bộ kiểm cũ.
  - Model thật D11 × 3 sau sửa (log `live_20261009T090809Z_d_28772.jsonl`): **3/3 đúng hướng**: 1 lượt nêu ΔR của cả 4 ngành, 2
    lượt trả "chưa trả lời được, chưa có xếp hạng phía giảm ít nhất" kèm gợi ý. Lần sửa giữa chừng (log `…090713Z_d_30232`) 2/3,
    lượt trượt bị chặn vì câu nói giới hạn của tool, đã sửa như trên.
  - `pytest tests/test_ai_chat.py`: 67 đạt (bỏ riêng 1 test cần PostgreSQL).
  - Kết quả 0/9 lượt phải sửa ở C02/A03/A03d là hiệu quả **chung** của prompt mới và bộ kiểm mới, không tách được phần nào.
- **Chưa làm:** chạy D\* trên Databricks (bộ kiểm không phụ thuộc kho; số trên Databricks đã khớp DuckDB 83 tổ hợp ngày 2026-10-06);
  chưa push nên **bản public vẫn chạy prompt cũ** `ai3-2026-10-05c`. Push sẽ làm Streamlit Cloud tự deploy lại: chờ PM quyết.


### 2026-10-09: chat trả lời thẳng "ngành / vùng / kênh giảm ít nhất là …" (PM chốt), nghiệm thu bằng bộ F\*

- **PM chốt:** cần chat trả lời thẳng "ngành giảm ít nhất là …" (§3 mục 12).
- **Đã làm (commit `02b772e`, `c1700ad`):**
  - `tools.py` (tool `v1.4`): công cụ theo nhóm thêm `derived.smallest_decrease` / `smallest_increase`. "Giảm ít nhất" = ΔR âm
    gần 0 nhất **trong các nhóm giảm**; "tăng ít nhất" tương tự. Tính trên đủ tập nhóm, đồng hạng giữ mọi nhóm. Không thêm chỉ tiêu
    mới, chỉ thêm một phép xếp trên cùng cột ΔR. Giai đoạn, điểm đổi hướng, N/U/P **chưa** có phía nhỏ.
  - `evidence.py`: câu "ít nhất / nhỏ nhất / nhẹ nhất / chậm nhất" phải dẫn `smallest_*`; câu "nhiều nhất" dẫn `smallest_*` thì
    chặn; câu nối "Đây là ngành giảm ít nhất" đối chiếu với `smallest_*`. Bịt một lỗ có từ trước: "số đơn (N) giảm ít nhất" từng
    được đối chiếu như câu "nhiều nhất" nên có thể qua sai.
  - Câu từ chối hoặc gợi ý hỏi tiếp ("dữ liệu chưa xếp hạng được…", "bạn có thể hỏi…") không còn bị coi là câu xếp hạng, miễn là
    không gọi tên một thành phần, giai đoạn, năm, tháng cụ thể (tên nhóm vẫn kiểm như cũ).
  - Prompt `ai3-2026-10-09b`: thêm cách dùng `smallest_*` và ví dụ.
- **Kiểm không gọi model:** `test_ai_tools.py` so `smallest_*` với CSV cho mọi năm × 3 chiều + test đồng hạng; test chat thêm
  câu đúng / sai cho phía nhỏ (68 đạt). Chạy lại offline mọi log cũ: không câu nào trước qua mà nay bị chặn.
- **Model thật, bộ F\*** (10 câu soạn sau khi sửa, commit trước lần gọi đầu; DuckDB × 3; log
  `warehouse/ai_eval/live_20261009T092200Z_f_21684.jsonl`, ~0,18 USD):
  - F01–F07 (giảm / tăng ít nhất theo ngành, vùng, kênh; năm có nhóm tăng lẫn giảm; hỏi cả hai phía; follow-up): **21/21**;
  - F10 (năm 2021 không kênh nào tăng): 3/3, chat nói không có kênh tăng và nêu kênh giảm ít nhất; một lượt viết "tăng ít nhất
    (tức giảm ít nhất)", vụng nhưng không sai số;
  - F08 (giai đoạn), F09 (N/U/P), phần chưa có phía nhỏ: lần đầu 4/6 lượt bị chặn dù câu cuối là lời từ chối đúng. Đã sửa như trên;
    chạy lại F08, F09 × 3 "sau sửa" (log `…092454Z_f_28432`): **6/6**, chat nói chưa xếp được và nêu số / gợi ý câu hỏi khác;
  - đọc tay: 0 số sai. Ở lần đầu, model vẫn hay tự xếp phía nhỏ cho giai đoạn, N/U/P rồi mới sửa (6/6 lượt F08, F09), tốn thêm một
    lần gọi model nhưng không lọt ra người dùng.
- **D11** (bộ D\*, trước là câu bẫy): đổi đáp án sang "Casual qua `smallest_decrease.groups`" theo quyết định PM; ghi trong rubric.

---

## 3. Cần cải thiện (lỗi và hạn chế đang biết)

Mức: **cao** = người đọc có thể hiểu sai; **vừa** = câu đúng nhưng mất phần diễn giải hoặc nhãn chưa chuẩn; **thấp** = câu thừa hoặc vụng.

| # | Vấn đề | Mức | Gặp ở | Hướng sửa | Trạng thái |
|---|---|---|---|---|---|
| 1 | **Số âm mất dấu** khi trong câu có chữ "giảm", kể cả chữ "giảm" nằm trong tên giai đoạn "Chững, giảm nhẹ". Ví dụ "CAGR 6,4% mỗi năm" thay vì −6,4% | **cao** | B06, E13, A03c | Chỉ bỏ dấu khi chữ "giảm" đi liền trước chỗ đặt và nói về chính số đó, không xét cả câu; thêm test | **Đã sửa** (`4b8b63c`); C\* 60/60 đúng dấu |
| 2 | "Tháng thấp nhất lặp lại ở cả 4 giai đoạn": câu đúng nhưng tool không có ô chứng minh, nên bị chặn và chỉ hiện bảng số | vừa | A04 | Thêm `derived.n_phases_same_peak` / `n_phases_same_trough` | **Đã sửa** (`4b8b63c`) |
| 3 | Câu hỏi năm 2023 gắn nhãn "chưa hỗ trợ" thay vì "không có dữ liệu" (nội dung trả lời đúng) | vừa | E15 (1/95 lượt) | Nhắc trong prompt hoặc app tự đổi nhãn khi năm nằm ngoài 2012–2022 | **Đã sửa** bằng prompt (`ai3-…c`); 40/40 nhãn đúng |
| 4 | Lặp cùng một số hai lần liền ("−7,5% −7,5%") | thấp | A02 | Bộ kiểm chặn hai chỗ đặt liền nhau trỏ cùng một ô | Chưa sửa |
| 5 | Gợi ý tự mâu thuẫn: mời "hỏi kênh referral theo tháng" rồi nói số theo tháng không tách theo kênh | thấp | B02 | Sửa quy tắc gợi ý trong prompt | Chưa sửa |
| 6 | Nói tháng 5 là "tháng cao nhất chung của cả kỳ" trong khi tool chỉ trả tháng cao nhất theo từng giai đoạn | thấp | E35 | Gộp vào mục 2 (thêm ô cả kỳ) | **Đã sửa** (`4b8b63c`) |
| 7 | Hạn 200.000 token chỉ được kiểm trước mỗi lần gọi model, chưa phải trần cứng; lần gọi cuối có thể vượt | vừa | Thiết kế | Trần output + cận trên prompt trước mỗi lần gọi | **Đã sửa** (`4b8b63c`). Đổi lại, phiên dừng sớm hơn khoảng 22–26 nghìn token, tức khoảng 2 câu hỏi |
| 8 | Mỗi lần build lại Postgres làm mất quyền của role AI, phải chạy lại `scripts/ops/pg_ai_readonly_role.py` | vừa | Vận hành | Hook `on-run-end` của dbt | **Đã sửa** (`7897f31`); đã kiểm thật trên Postgres local |
| 9 | Chạy app hoặc eval trên Postgres phải đặt `PG_AI_USER` / `PG_AI_PASSWORD`; thiếu thì chat từ chối đọc | thấp | Vận hành | Ghi vào hướng dẫn chạy app | Đã ghi ở ai3.md §4b |
| 10 | Model tự thêm câu xếp hạng ("tăng/giảm mạnh nhất…") mà chỗ đặt chứng minh nằm ở câu khác, nên bị chặn. Đúng nguyên tắc, nhưng mất phần lời; thường sửa được trong lần thử lại (C02: 3/6 lượt phải sửa), có lúc không (A03) | vừa | A03, A04, C02 | Prompt: ví dụ cụ thể "câu xếp hạng phải tự chứa chỗ đặt largest_*"; hoặc cho phép dẫn lại chỗ đặt đã dùng | **Đã sửa** (`09b9930`): app tự đối chiếu câu nối "Đây là…" + kiểm tiêu chí tiền/CAGR, prompt có ví dụ. D\*: 3/36 lượt phải sửa (đều là câu bẫy D11); C02/A03/A03d sau sửa 0/9 |
| 11 | Rubric A04d cấm cụm "sẽ thấp" bắt nhầm câu từ chối đúng | thấp | A04d (1/10) | Sửa rubric trước một lần chạy nghiệm thu **mới**, ghi lý do | Chưa sửa |
| 12 | Hỏi "ngành nào giảm **ít** nhất": tool chỉ xếp phía lớn nhất. Lần đầu model khẳng định "giảm ít nhất là …" nên bị chặn; lời nhắc sửa của app lại gợi ý `largest_*`, nên model trả lời lệch sang "ngành kéo giảm **nhiều** nhất" (số đúng, không đúng câu hỏi) | vừa | D11 (2/3 lượt lệch, 1/3 bị chặn) | Lời nhắc sửa nói rõ tool không xếp phía nhỏ, không đổi câu hỏi. Muốn chat trả lời thẳng "giảm ít nhất là …" thì thêm `smallest_decrease` / `smallest_increase` vào tool nhóm (tính trên đủ tập): **PM chọn** | **Đã sửa** (`24c86d5`, `02b772e`, `c1700ad`): PM chốt trả lời thẳng → tool có `smallest_*` cho nhóm; F\* F01–F07 21/21. Giai đoạn, N/U/P vẫn chưa có phía nhỏ (chat nói chưa xếp được) |
| 13 | Từ định lượng "duy nhất", "đều", "tất cả" và số viết bằng chữ ("bốn giai đoạn", "ba điểm") chưa được bộ kiểm xét. Các câu gặp đều đúng với dữ liệu | thấp | D12 ("giai đoạn duy nhất có CAGR dương"), E05, A03c | Kiểm số viết bằng chữ như chữ số; câu "duy nhất / đều" phải dẫn n_groups_down / n_groups_up… | Chưa sửa |
| 14 | Một chỗ đặt dùng chung cho "cả hai tiêu chí" ("…giảm mạnh nhất đều là {c1}" với c1 = largest_decrease.phases), còn CAGR dẫn qua `largest_decrease_cagr.cagr`: app chưa nối giá trị CAGR với tên giai đoạn. Đúng với dữ liệu (C đứng đầu cả hai) | thấp | D01 (1/3) | Câu nêu "hai tiêu chí" phải có cả `largest_*.phases` và `largest_*_cagr.phases` | Chưa sửa |
| 15 | Lặp tên thành phần: "số đơn (N) với **số đơn (N)**" | thấp | D07 (1/3) | Gộp với mục 4 (chặn chỗ đặt nhắc lại chữ ngay trước) | Chưa sửa |

**Chưa mở (giới hạn có chủ đích, không phải lỗi):**
- nhóm × tháng/quý;
- quý hoặc khoảng ngày tùy ý;
- phân rã N/U/P theo giai đoạn;
- tháng đổi hướng do dữ liệu tự tìm;
- số khách C theo nhóm;
- đọc từ Snowflake (Databricks đã mở ngày 2026-10-06);
- dự báo năm 2023 trở đi.

---

## 4. Sẽ làm tiếp (đề xuất, chờ PM đồng ý)

| Thứ tự | Việc | Vì sao | Ước lượng |
|---|---|---|---|
| 1 | **Đưa AI Explain lên Databricks production** (PM **chốt** 2026-10-05). **Tiến độ 2026-10-06:** B1–B3 xong (chat đọc Databricks, 105/105, khớp DuckDB, C\* 30/30); B4 chờ khóa DeepSeek mới để deploy. Các bước: kiểm app trên Databricks có gọi được API model không; đường đọc chỉ-đọc cho Databricks (danh tính riêng, quyền đúng 14 bảng); khóa API trong secret; test so Databricks với DuckDB; chạy model thật trên Databricks; rồi mới deploy app. **Đã kiểm 2026-10-05** (profile `retail-dev`): serverless gọi được `api.deepseek.com` (nhận 401 từ chính DeepSeek khi không kèm khóa); app có thể theo chính sách khác, chỉ biết chắc khi deploy. Workspace có sẵn endpoint `databricks-deepseek-v4-flash-0731` (model do Databricks host, không cần khóa ngoài). Chưa có app hay service principal nào; `retail_lab` chưa cấp quyền cho ai | Mục tiêu "mọi thứ lên production" | 2–3 ngày, cần cloud |
| 2 | ~~§3 mục 10 (câu xếp hạng tự thêm), sau đó nghiệm thu bằng bộ câu mới D\*~~ **Xong 2026-10-09** (`09b9930`). Tiếp theo: §3 mục 12 (hỏi phía "ít nhất"), chờ PM chọn cách; lần nghiệm thu sau cần một bộ câu mới chưa dùng (D\* đã dùng) | Lỗi an toàn còn lặp lại | nửa ngày |
| 3 | Báo cáo AI4 cho bảo vệ: tách test truy vấn, test giao diện và model thật; ghi phiên bản model, prompt, catalog, dữ liệu | Kế hoạch §13; bằng chứng cho hội đồng | 1 ngày |
| 4 | Kịch bản demo chat: 5–7 câu phủ PS1–PS5, kèm 1–2 câu bị từ chối đúng | Demo có kiểm soát | 2 giờ |

**Chờ PM/BA chốt:**
- quy ước năm ranh giới PS3 (đang ghi "đề xuất");
- cách cộng N/U/P theo giai đoạn;
- ngưỡng ΔR nhỏ 1%.

**Chờ PM quyết:**
- thu hồi khóa API cũ;
- có push nhánh `app/myuyen` không;
- xử lý các file đang sửa hoặc xóa ở thư mục gốc.

---

## 5. Cách ghi tiếp nhật ký

- Mỗi đợt làm: thêm một mục `### yyyy-mm-dd: <việc>` ở cuối §2, gồm 3–5 gạch đầu dòng **Làm / Kết quả / Chi tiết**.
- Lỗi mới thì thêm dòng vào §3; sửa xong thì đổi cột trạng thái, kèm commit. Không xóa dòng.
- Cập nhật bảng §1 và §4 cho khớp.
- Kết quả model thật luôn ghi kèm bộ câu, số lần chạy, prompt và tên file log. Không trộn với kết quả test dùng model giả.
