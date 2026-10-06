# AI Explain — bàn giao AI0–AI1 (hợp đồng + công cụ query, chưa có LLM)

Ngày: **2026-10-03**. Kế hoạch gốc: [ai_explain_plan.md](ai_explain_plan.md) §0, §11–§14.

## 1. Trạng thái gate

| Mốc | Trạng thái | Bằng chứng |
|---|---|---|
| AI0 → AI1 | **Đạt cho lát cắt R 2019 so 2018 → PS4 N/U/P → PS5 theo nhóm** | Catalog + ma trận khả năng trong code; case E01–E22; số đối chứng độc lập từ CSV khớp DuckDB (§3) |
| AI1 (DuckDB) | **Đạt** | `tests/test_ai_tools.py`: 98 test DuckDB/không cần server đạt, phủ mọi năm × chiều đang mở; 2 mutation bị bắt (§5) |
| AI1 (PostgreSQL) | **Đạt** (2026-10-03, sau khi Docker chạy lại) | Role `retail_ai_ro` qua guard; 60 test PG đạt: cùng số DuckDB ở mọi năm × chiều đang mở (cả nhóm giảm/tăng nhiều nhất), từ chối superuser, không ghi được, timeout thật (§5) |
| AI1 → AI2 | **Chưa chuyển** | Phần kỹ thuật AI1 đã đủ. PM đã chọn provider (2026-10-04, §6 mục 2); còn chờ model, hạn mức chi phí, API key |

Chưa có LLM, chưa gọi API, chưa có trang chat. PASS ở đây là test tool, **không phải live-model eval**.

## 2. Đã xây gì

| File | Vai trò |
|---|---|
| `apps/retail_app/ai_explain/contracts.py` | Trạng thái (`ok`, `needs_clarification`, `unsupported`, `no_data`, `quality_blocked`, `query_error`), kết quả tool, bằng chứng. Trạng thái lỗi không được kèm số |
| `apps/retail_app/ai_explain/metric_catalog.py` | Định nghĩa metric (theo [star_schema.md](star_schema.md) §3), `decision_status` chốt/đề xuất, ma trận khả năng, hash SQL định nghĩa |
| `apps/retail_app/ai_explain/tools.py` | 3 tool, kiểm tham số chặt, cổng chất lượng, gói bằng chứng, JSON Schema cho AI2 |
| `apps/retail_app/ai_explain/eval_cases.py` | Case E01–E22 dạng dữ liệu, tách phần kiểm được bằng tool và phần chờ LLM |
| `apps/retail_app/dwh/guarded.py` | Đường đọc riêng cho AI: tham số driver, giữ `Decimal`, timeout, giới hạn dòng, một phiên một bản dữ liệu, guard quyền PG |
| `scripts/ops/pg_ai_readonly_role.py` | Tạo role `retail_ai_ro` chỉ SELECT 6 bảng/view cho phép; `--check` chạy guard |
| `apps/retail_app/tests/test_ai_tools.py` | Test số (so CSV), trạng thái, bằng chứng, giới hạn, cổng chất lượng, PG |

Không sửa model dbt, `queries.py`, `connection.read_sql` hay trang app hiện có.

### Tool đang mở

| Tool | Câu hỏi | Bảng đọc |
|---|---|---|
| `get_revenue_summary(metric R/G/R_and_G, year, compare_prior_year?)` | E01, E03 | `rpt_revenue_yearly` |
| `get_revenue_drivers(metric, year, period_type='year')` | E04 | `rpt_driver_period`, `driver_rule` |
| `get_segment_contribution(metric, dimension, year, group?)` | E05, E06 | `rpt_revenue_segment_yearly` |

Mọi lượt đọc thêm `rpt_build_info` + `rpt_health_summary` trong **cùng phiên**. Health phải `tot`, `tests_are_current`,
`tests_are_complete`, và cùng build marker với dữ liệu. Không đạt thì `quality_blocked`, không trả số.

### Ma trận khả năng

| Mở | Chưa mở (tool trả `unsupported`) |
|---|---|
| R, G mức năm | G so năm trước / ΔG: chưa có cột đã kiểm |
| R so năm trước, từ 2014 | Phân rã N/U/P cho G |
| Phân rã ΔR N → U → P theo năm, từ 2014 | Phân rã theo giai đoạn PS2: phương pháp cộng dồn năm **chờ PM/BA chốt** |
| R theo **một** chiều (category / region / acquisition_channel) × năm | Nhiều chiều giao nhau, khoảng ngày tùy ý: cần query M6 đã nghiệm thu |
| | C kỳ gộp, C theo nhóm; tool C/F (`get_order_drivers`); tool PS1 bridge, PS2, PS3 |

Trường lạ (vd. `region`, `start_date` khi tool không có) bị **từ chối**, không bỏ qua rồi trả tổng. Thiếu metric/năm →
`needs_clarification`, không chọn ngầm R hay G. `backend` không phải tham số tool.

Lựa chọn trạng thái: năm ngoài coverage (2023) → `no_data`; so năm trước/phân rã cho 2012–2013 → `unsupported`
(hợp đồng không định nghĩa YoY này); nhóm không tồn tại → `no_data` kèm danh sách nhóm có thật.

Quy ước **đề xuất** còn giữ nhãn trong bằng chứng: ngưỡng ΔR nhỏ 1% (`driver_rule`), phân rã giai đoạn = cộng năm,
năm ranh giới PS3. Đơn vị tiền tệ lúc làm AI0–AI1 chưa xác minh nên catalog không ghi VND/USD; ngày 2026-10-05 PM chốt VND, catalog đã đổi.

## 3. Số đối chứng độc lập (lát cắt 2018 → 2019)

Tính thẳng từ CSV bằng pandas, tiền theo cent nguyên; không qua dbt hay tool. R lấy từ `payments.csv` của đơn delivered
(theo `order_date`) và **khớp tuyệt đối** tổng dòng hàng. G lấy từ `sales.csv`.

| Chỉ tiêu | 2018 | 2019 | DuckDB / tool |
|---|---:|---:|---|
| R | 1.419.275.129,27 | 864.329.801,94 | khớp từng cent |
| G | 1.850.122.456,08 | 1.136.801.441,51 | khớp từng cent |
| N (đơn) | 55.740 | 33.259 | khớp |
| Q (món) | 270.404 | 161.837 | khớp |
| ΔR | | −554.945.327,33 | khớp từng cent |
| Phần góp N / U / P | | −572.420.598,87 / +2.582.715,71 / +14.892.555,84 | sai số tương đối < 1e-9, cộng = ΔR |

PS5 theo ngành hàng 2019 (ΔR, khớp từng cent): Streetwear −463.947.221,16; Outdoor −44.049.224,39;
GenZ −24.500.811,18; Casual −22.448.070,60. **Ngành kéo giảm nhiều nhất = Streetwear (ΔR âm nhất)**, trong khi
`delta_r_rank = 1` là Casual (giảm ít nhất). Tool chọn theo ΔR trên đủ tập nhóm; đồng hạng thì giữ tất cả.
Test không dừng ở lát cắt 2019. Mọi năm mà tool đang mở đều được so với CSV:
- R, G năm 2012–2022;
- R so năm trước và phân rã N/U/P năm 2014–2022;
- 3 chiều × 2014–2022: ΔR từng nhóm, tỷ trọng, `share_shift_pp` (E17), % đóng góp, nhóm giảm/tăng nhiều nhất.

Region tra theo khách → zip → vùng. Cả mã khách và zip đều là khóa duy nhất.

Đây là **phân rã số học**, không chứng minh nguyên nhân (marketing, churn, tồn kho...).

**Snapshot:** DuckDB `warehouse/dbt.duckdb`, `built_at_utc = 2026-10-02 16:37:46`, phạm vi ngày đặt hàng
2012-07-04 → 2022-12-31, health `tot` (158 test, 0 lỗi — nhật ký đã lưu, không chạy lại dbt). sha256 CSV:

```text
orders.csv       f4b3029f386f5f5a6baabd78aad0140e5a101ea6975f4cbaba04976813f3f3af
order_items.csv  a8b2adfe54eec0dda79ced28e5987d6846b7f31cb6052356ab3a1772cc85e0bc
payments.csv     aacef7716fe1c1442bc46e8885019cf1d67e12655c2e0f28bd0c9e92e145a6e7
products.csv     890946808d8237dad0d39153efd427f5399a5e6eaa2302681ab6bdf8a706204c
sales.csv        081d539f50d41f202edfb064a2cf218d44e3ac1429c6c34fd1869ae060aa882d
customers.csv    5e58abf49e99d52bf8ddda44601a30e78667760908b862287bc6e69a45cf77b8
geography.csv    f5d150bdfdfca7ac0c38118b1f5f8ea1b3f5de4cd23fa700d5aa0adcd2ab6353
```

## 4. Bằng chứng mỗi lần gọi tool

`request_id` (uuid do app sinh, không phải query ID của DB), tool + version, tham số đã áp dụng, điều kiện lọc thực tế,
grain, định nghĩa metric kèm `decision_status`, phương pháp, backend + nơi đọc, build marker + coverage, trạng thái
health, `definition_version`, giờ đọc UTC, và từng câu SQL với tham số. Giá trị chưa làm tròn: tiền là `Decimal`.

`definition_version` = hash các file SQL định nghĩa trong **checkout**; không chứng minh DB được build từ đúng bản đó.
Phiên bản dữ liệu là build marker, không phải hash này.

## 5. Đã kiểm gì

```powershell
cd apps/retail_app
..\..\.venv\Scripts\python.exe -m pytest tests/test_ai_tools.py -q -p no:cacheprovider
```

Kết quả ngày 2026-10-03 (sau khi Docker chạy lại): **158 passed, 0 failed** (98 DuckDB/không cần server + 60 PostgreSQL). Lần chạy đầu trong ngày, lúc Docker lỗi,
là 99 đạt và 2 FAIL `ConnectionTimeout`. Toàn bộ `pytest apps/retail_app` (gồm test cũ của app trên PostgreSQL): **259 passed**, chạy lúc file test AI còn 102 test,
trước khi mở rộng phép so PG.

Các test đường PostgreSQL đều đạt, chạy bằng role `retail_ai_ro` do `scripts/ops/pg_ai_readonly_role.py` tạo trên Docker local:
- thiếu `PG_AI_USER` → không đọc;
- tài khoản app `retail` (superuser) → guard từ chối;
- 56 lượt gọi tool trên PostgreSQL trả cùng số DuckDB, so cả `rows` lẫn `derived` (nhóm giảm/tăng nhiều nhất, kiểm cộng N/U/P):
  R/G 2012–2022, R so năm trước và phân rã 2014–2022, 3 chiều × 2014–2022. Cộng với DuckDB khớp CSV ở trên → PostgreSQL khớp CSV;
- role không UPDATE/CREATE được, và không SELECT được `int_reporting_order_items`;
- timeout thật: `pg_sleep(5)` với giới hạn 0,3 giây bị ngắt dưới 3 giây. Kiểm ngược: giới hạn 10 giây thì `pg_sleep(1)`
  chạy hết.

Snapshot PostgreSQL: `built_at_utc = 2026-10-02 16:38:57`, health `tot` (158/158 test). Đây là một lần build riêng với DuckDB
(16:37:46), nhưng số khớp ở mọi năm × chiều đang mở.

Các test DuckDB đạt gồm:
- số E01/E03/E04/E05/E06/E17 so CSV ở mọi năm × chiều đang mở;
- trạng thái mọi case có phần tool;
- trường lạ, sai kiểu (`'2019'`, `True`, `2019.0`);
- nhãn độc hại chỉ đi qua tham số, DB không đổi;
- timeout DuckDB thật (ngắt sau 0,3 giây); vượt số dòng thì từ chối;
- không mở được kho → `query_error`;
- bản sao DB: kho dựng lại sau lần kiểm, build_info rỗng, bảng nhóm thiếu dòng → bị chặn, không xếp hạng trên tập thiếu;
- đồng hạng (E22): hai nhóm cùng ΔR âm nhất → trả cả hai, `tie = True`.

Mutation (sửa tạm rồi khôi phục):
- xếp nhóm không theo ΔR âm nhất → 4 FAIL;
- bỏ kiểm trường lạ → 3 FAIL.

**Chưa chạy:** `dbt build` (dùng bản kho đã build và đã kiểm ngày 2026-10-02), live model.

## 6. Việc còn lại trước AI2

1. ~~Bật Docker, chạy script role, chạy lại test~~: **xong 2026-10-03**. Lưu ý vận hành: sau mỗi
   `dbt build --target postgres` phải chạy lại `scripts/ops/pg_ai_readonly_role.py`, vì dbt dựng lại bảng làm mất quyền.
2. PM chọn provider/model, nơi chạy và hạn mức chi phí (§9 của kế hoạch). Code không khóa provider nào.
   **PM chốt 2026-10-04:** giai đoạn dev dùng API LLM của DeepSeek, sau này chuyển sang OpenAI. Vì vậy lớp gọi LLM phải
   đổi provider bằng cấu hình (biến môi trường), không viết riêng cho một hãng. **Còn chờ:** model, hạn mức chi phí
   (API DeepSeek tính phí theo lượt dùng), API key đặt qua biến môi trường. Chỉ gửi kết quả tổng hợp của tool cho
   provider, không gửi dòng dữ liệu khách hàng.
   **Đơn vị tiền:** PM chốt hiển thị VND (2026-10-04). Đây là quy ước hiển thị do PM chọn, dữ liệu nguồn không ghi
   đơn vị. Còn chờ xác nhận thang đo: giá TB mỗi món P trong kho là 4.003–6.548. Nếu đọc nguyên giá trị thì một món thời
   trang chỉ khoảng 5 nghìn đồng, nên cần chốt "VND" hay "nghìn VND" trước khi sửa `MONEY_UNIT`, case E01 và test đơn vị.
3. AI2: validator claim có cấu trúc (E21), bộ điều phối + context follow-up (E06/E07/E20), phần LLM của E02/E04/E14.
4. Gate production: build marker + health chưa chứng minh mọi bảng cùng một lần publish (kế hoạch §11.3).
   Demo local dùng bản DB cố định đã kiểm, không build đè trong lúc chat.
5. AI5: `definition_version` đọc file `retail_dbt/` trên đĩa ở mỗi lần gọi. Bản triển khai không kèm `retail_dbt/` sẽ gặp
   `query_error` ở mọi câu. Khi đó phải tính hash lúc build/đóng gói.
