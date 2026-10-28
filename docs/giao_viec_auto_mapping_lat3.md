# Giao việc: auto mapping, lát 3 (dbt: `dim_sales_employee` và `sales_employee_sk` trong `fact_order`, bật bằng biến)

Soạn ngày 2026-10-28. PM giao, Claude soạn phiếu. GPT code; Claude rà độc lập trước khi commit theo 5 bước rà ở đầu
[giao_viec_theo_so_do.md](giao_viec_theo_so_do.md). Chưa đạt thì Claude ghi phát hiện vào §9, GPT sửa tiếp. PM đọc báo cáo
rà rồi mới cho commit.

Đọc trước:
- [tien_hoa_schema.md](tien_hoa_schema.md) §7 (bảng thiết kế đích của `orders_enriched`), §9 bước 5–6, §10 mục 3, 5, 6;
- [giao_viec_auto_mapping_lat2.md](giao_viec_auto_mapping_lat2.md) §3 (hợp đồng đã duyệt) và §9 (B3: chuẩn hóa để ở staging);
- `AGENTS.md`, `CLAUDE.md`, skill `retail-analytics-engineering` (nhất là `references/quality.md`);
- `docs/star_schema.md` §4–§7 (grain, khóa, quy ước `_sk`).

## 0. Lát 3 nằm ở đâu

| Lát | Việc | Cổng production (§9 bước 6 tien_hoa) |
|---|---|---|
| 1 | Đề xuất ánh xạ (xong, `942d8dc`) | |
| 2 | Hợp đồng đã duyệt, `prepare --extension`, cách ly 1% (xong, `db614b6…13a4a36`) | 1, 2 |
| **3** | **dbt: staging + `dim_sales_employee` + `sales_employee_sk` trong `fact_order`, bật bằng biến; cổng `validate` đọc `hien_thi`; bản ứng viên local qua `validate`** | **5 (thử, xem §6.4)** |
| 4 | Lên Databricks: dựng image, Airflow truyền `--extension`, chạy tắt rồi bật, publish | 3, 4, 6, 7 (và 5 nếu lát 3 chưa chạy được) |
| 5 | App/chat hiện chiều nhân viên (BA định câu hỏi và metric trước) | |

## 1. Lát 3 làm gì, không làm gì

**Làm:**
1. Khai báo nguồn raw `orders_enriched` cho dbt.
2. `stg_orders_enriched` (staging, tầng silver): chuẩn hóa và ép kiểu toàn bộ cột nạp, kể cả cột nhạy cảm và `comment`.
3. `dim_sales_employee` (marts): chỉ cột `hien_thi: mart`.
4. `fact_order` thêm `sales_employee_sk` khi bật phần mở rộng; tắt thì `fact_order` y như cũ.
5. Test dbt cho phần mở rộng (singular `.sql`, bật cùng điều kiện với model).
6. Sửa `assert_rpt_health.sql` để không cố định 14 nguồn khi bật phần mở rộng (§4.5).
7. `cli.py`: truyền biến bật phần mở rộng cho dbt; cổng `validate` đọc `hien_thi` của hợp đồng (§4.6).

**Không làm ở lát này:**
- không model `reporting` mới, không sửa `ai_readonly_relations` / `app_read_relations` trong `dbt_project.yml` (lát 5);
- không sửa `scripts/pipeline/runtime.py`, `snapshot.py`, `scripts/ingest/extension_*.py`, `scripts/ingest/extensions/*.yml`;
- không sửa `assert_row_counts.sql` và các test dbt khác ngoài `assert_rpt_health.sql`;
- không sửa `apps/`, `deploy/` (Airflow chưa truyền `--extension`, lát 4), notebook, `docs/`;
- không chạy gì trên Databricks thật, không đọc `.env.*.local`, không dùng token thật.

**Được sửa (file đã có trong Git):** `retail_dbt/models/staging/_sources.yml`, `retail_dbt/models/marts/fact_order.sql`,
`retail_dbt/tests/assert_rpt_health.sql`, `scripts/pipeline/cli.py` (chỉ `dbt_build` và `validate_data`, cùng hàm phụ mới
nếu cần). Được thêm mô tả (không thêm test) cho model mới vào `_marts.yml` / một file `.yml` mới ở staging.
**Được tạo:** `retail_dbt/models/staging/stg_orders_enriched.sql`, `retail_dbt/models/marts/dim_sales_employee.sql`, test
singular mới trong `retail_dbt/tests/`, test pytest mới trong `scripts/pipeline/tests/` (file **mới**, không sửa test cũ).

## 2. Môi trường và ràng buộc

Giữ §2 của phiếu lát 2: worktree `D:/retail-analytics-schema`, nhánh `schema/myuyen`; Python và dbt
`D:/retail-analytics/.venv/Scripts/` (dbt-core 1.12.5, dbt-duckdb 1.11.0), không cài thêm gói; không sửa `data/`; không
stage, commit hay push; UTF-8 không BOM. Comment SQL tiếng Việt, giọng như model hiện có.

Ràng buộc dbt:
- **Không có test YAML** (`data_tests:`) cho model mới, và không có cho cột mới của `fact_order` trong `_marts.yml`. dbt vẫn
  đăng ký test YAML của model bị tắt và làm hỏng build thường (đã gặp ở `_forecast.yml`, xem comment đầu file đó). Mọi kiểm
  nằm trong test singular `.sql` có `{{ config(enabled=...) }}` cùng điều kiện với model.
- Chỉ dùng macro có sẵn (`clean`, `date_sk`, `type_double`...) và SQL chung DuckDB/PostgreSQL/Databricks. Cần khác biệt thì
  dùng `adapter.dispatch` như `macros/cross_db.sql`; không thêm nhánh Snowflake.
- Không `row_number()` thiếu `order by`; khóa thay thế đánh như `dim_customer`.

## 3. Thiết kế

### 3.1 Biến bật

- `cli.dbt_build` thêm `vars_['extensions'] = context['extensions']` **chỉ khi** context có khóa này (lát 2 chỉ ghi khóa khi
  bật). Tắt thì `--vars` y như hiện nay.
- Trong dbt, điều kiện bật là `'orders_enriched' in var('extensions', [])`. Đặt điều kiện này ở một chỗ (macro mới, ví dụ
  `extension_enabled('orders_enriched')` trong file macro mới) để model, test và `_sources.yml` dùng chung.

### 3.2 Nguồn

`orders_enriched` vào source `raw` (cùng schema `r_<release_id>_raw` trên Databricks, cùng `external_location`
`read_parquet('<snapshot_path>/orders_enriched.parquet')` trên DuckDB). GPT chọn: khai báo luôn hoặc `enabled` theo biến; điều
kiện là build tắt không đổi số node model/seed/test (§6.3).

### 3.3 `stg_orders_enriched` (view, staging)

Một dòng mỗi dòng nhận của parquet (646.945 trên dữ liệu thật). Chuẩn hóa bằng `clean()` như `stg_orders` (lát 2 B3: parquet
giữ giá trị gốc, chuẩn hóa ở staging):

| Cột | Kiểu |
|---|---|
| `order_id` | `integer` |
| `sales_employee_id`, `sales_employee_name`, `marital_status`, `education_level`, `comment` | chuỗi (`clean`) |
| `years_experience` | `integer` |
| `_src_row`, `_dong_goc` | giữ để truy ngược |

`marital_status`, `education_level`, `comment` có `hien_thi: silver`: **chỉ dừng ở model này**, không đi tiếp lên marts.

### 3.4 `dim_sales_employee` (table, marts)

SCD Type 1, grain = một nhân viên (200 trên dữ liệu thật).

| Cột | Nguồn |
|---|---|
| `sales_employee_sk` | `cast(row_number() over (order by sales_employee_id) as integer)`, như `dim_customer` |
| `sales_employee_id` | khóa tự nhiên |
| `sales_employee_name` | thuộc tính, `hien_thi: mart` |
| `years_experience` | thuộc tính, `hien_thi: mart` |

Thuộc tính lấy theo id; phụ thuộc hàm đã kiểm ở `prepare` (R6), nhưng test dbt kiểm lại độc lập (§5, T2). Không `distinct` để
che lỗi: nếu một id có hai bộ thuộc tính thì dim phải ra hai dòng và test bắt.

### 3.5 `fact_order`

- Tắt: SQL biên dịch **y hệt** hiện nay (§6.3).
- Bật: thêm `sales_employee_sk` bằng `left join` `stg_orders_enriched` theo `order_id`, rồi `left join` `dim_sales_employee`
  theo `sales_employee_id`. Không làm nhân dòng: `order_id` duy nhất trong staging (lát 2 R2), test cũ
  `assert_every_source_row_lands` đã buộc `count(stg_orders) = count(fact_order)`.
- Đơn không có dòng nhận (dòng bị cách ly ở `prepare`, tối đa 1%): `sales_employee_sk` **NULL** (§10 câu 1).

Đã kiểm: trong `retail_dbt/` và `apps/` không chỗ nào đọc `fact_order` bằng `select *` hay theo vị trí cột; chỉ test singular
đọc theo tên cột. App và chat chỉ đọc `reporting`.

## 4. Yêu cầu từng phần

### 4.1 `_sources.yml`, macro bật

Như §3.1–3.2. Không đổi khai báo 14 nguồn hiện có.

### 4.2 Model

Như §3.3–3.5. Model mới có `{{ config(enabled=...) }}` theo §3.1. Thêm `description` cho model mới (không test YAML).

### 4.3 Test dbt singular (bật cùng điều kiện)

| # | Kiểm | Kỳ vọng trên dữ liệu thật |
|---|---|---|
| T1 | `count(stg_orders_enriched) = count(source raw.orders_enriched)`; `order_id` không NULL, không trùng; mọi `order_id` có trong `stg_orders`; `_src_row` liền 1..N | 646.945 |
| T2 | `dim_sales_employee`: `sales_employee_sk` và `sales_employee_id` không NULL, không trùng; số dòng = số `sales_employee_id` phân biệt trong staging; mỗi id trong staging có đúng một bộ (`sales_employee_name`, `years_experience`) và bộ đó trùng dim | 200 |
| T3 | `fact_order`: số dòng `sales_employee_sk` khác NULL = số dòng staging nối được về `fact_order`; mọi `sales_employee_sk` khác NULL có trong dim; **nối lại độc lập** `fact_order → dim → staging` theo `order_id` ra đúng `sales_employee_id` của staging | 646.945 khác NULL, 0 NULL |
| T4 | Số đơn NULL `sales_employee_sk` = số đơn trong `stg_orders` không có trong staging | 0 |

Không viết test chỉ lặp lại đúng biểu thức của model (skill `retail-analytics-engineering` mục 5).

### 4.4 Tắt phần mở rộng

Không bật biến thì: không model mới, không test mới, `fact_order` không có cột mới, mọi SQL biên dịch trùng bản trước (§6.3).

### 4.5 `assert_rpt_health.sql`

Trên PostgreSQL/Databricks, phần "4. Log nạp nguồn" cố định `k <> 14` và danh sách 14 nguồn. Khi bật phần mở rộng,
`runtime.ingest` ghi 15 dòng vào `_ingest_log`, nên **build trên cloud sẽ trượt** dù local vẫn qua (nhánh DuckDB không đọc log).
Sửa:
- số nguồn kỳ vọng = 14 + số nguồn mở rộng đang bật;
- danh sách đối chiếu số dòng thêm các nguồn mở rộng đang bật.

Tắt thì SQL biên dịch **trùng từng ký tự** bản cũ (§6.3). Ghi trong báo cáo: `apps/retail_app/tests/test_databricks.py:38`
cũng cố định `n_sources_ingested == 14`; không sửa ở lát này (lát 4/5).

### 4.6 `cli.py`

- `dbt_build`: như §3.1.
- `validate_data`, thêm **cổng hiển thị** khi `context` có `extensions`. Với mỗi nguồn mở rộng, đọc hợp đồng qua
  `extension_contract.load` (không tự đọc YAML), rồi lấy danh sách cột của mọi bảng/view trong `r_<rid>_marts` và
  `r_<rid>_reporting` (qua `information_schema.columns`, dùng `fetch` như phần đối soát hiện có, để lát 4 chạy được trên cloud):
  - cột `nap` có `hien_thi: silver` xuất hiện ở bất kỳ quan hệ nào trong hai schema đó: **dừng**, nêu tên cột và bảng;
  - cột `nap` có `hien_thi: mart` không có trong `dim_sales_employee` (hay quan hệ nào trong `r_<rid>_marts`): **dừng**.
  Không bật phần mở rộng: không chạy cổng này, kết quả `validate` y như cũ.
- Thêm số liệu cổng vào kết quả `validate` chỉ khi bật (ví dụ `hidden_columns_checked`); tắt thì khóa kết quả như cũ.
- So tên cột không phân biệt hoa thường (Databricks trả tên thường).

## 5. Test bắt buộc

### 5.1 pytest (không cần `data/`, không chạy dbt, dưới 15 giây)

File mới, ví dụ `scripts/pipeline/tests/test_extensions_dbt.py`.

| Ca | Tình huống | Kỳ vọng |
|---|---|---|
| D1 | `dbt_build` với context không có `extensions` (giả `subprocess.run`, đọc `--vars`) | `--vars` đúng 4 khóa như cũ (cộng `forecast_path` nếu có) |
| D2 | `dbt_build` với `extensions: ['orders_enriched']` | `--vars` có `extensions` |
| D3 | Cổng hiển thị: `fetch` giả trả cột của `r_x_marts.dim_sales_employee` gồm `marital_status` | dừng, thông báo nêu `marital_status` và bảng |
| D4 | Như D3 nhưng cột nằm ở `r_x_reporting.<bảng>`; viết hoa `MARITAL_STATUS` | dừng |
| D5 | Thiếu `sales_employee_name` trong marts | dừng |
| D6 | Đủ cột `mart`, không cột `silver` | qua |
| D7 | Không bật phần mở rộng | không gọi truy vấn cột; kết quả `validate` không có khóa mới |
| D8 | Hợp đồng sửa `hien_thi` của `years_experience` thành `silver` (hợp đồng trong `tmp_path`) | cổng đổi theo hợp đồng: `years_experience` trong marts thì dừng |

Mỗi test chính phải trượt khi bỏ phần code tương ứng; báo cáo ghi đã thử vô hiệu gì, test nào trượt. Công cụ thử vô hiệu
**để ngoài `scripts/`** (ví dụ `warehouse/schema_review/`), không tạo file như `verify_extension_mutations.py` trong gói code
(lát 2 B5, PM chốt không commit).

### 5.2 Hồi quy

| Bộ | Mốc (sau lát 2, `13a4a36`) |
|---|---|
| `scripts/ingest/tests` | 114 đạt |
| `scripts/pipeline/tests` (test cũ không sửa) | 61 đạt, 2 skip |
| `pytest scripts` | 207 đạt + số test mới, 3 skip |

## 6. Kiểm bằng dbt (GPT chạy được thì chạy; nặng thì ghi "chưa chạy")

### 6.1 Danh sách node

```powershell
cd D:\retail-analytics-schema
$dbt = 'D:/retail-analytics/.venv/Scripts/dbt.exe'
$env:RETAIL_DUCKDB_BUILD_PATH = 'warehouse/lat3/scratch.duckdb'
& $dbt ls --project-dir retail_dbt --profiles-dir retail_dbt --target duckdb --resource-type model --resource-type seed --resource-type test > warehouse/lat3/ls_tat.txt
& $dbt ls --project-dir retail_dbt --profiles-dir retail_dbt --target duckdb --resource-type model --resource-type seed --resource-type test --vars '{\"extensions\": [\"orders_enriched\"]}' > warehouse/lat3/ls_bat.txt
```

Lưu ý: bốn model `rpt_forecast_*` và test của chúng chỉ bật khi có `forecast_path`. Để so với mốc, chạy cả hai lệnh với
thêm `forecast_path` lấy từ `warehouse/pipeline/review-20261027/runs/review-20261027/context.json`.

Kỳ vọng: tập node của `ls_tat` **trùng** tập node model/seed/test trong
`warehouse/pipeline/review-20261027/runs/review-20261027/duckdb/manifest.json` (3 seed, 57 model = 33 table + 24 view,
162 test); `ls_bat` = `ls_tat` cộng đúng 2 model và các test T1–T4.

### 6.2 Build bật trên snapshot thật (không qua pipeline)

Snapshot `47e7cbe765d9` đã có ở `warehouse/pipeline/lat2/snapshots/`. Build DuckDB vào file tạm, **không** dùng
`warehouse/dbt.duckdb` hay `dbt.duckdb` của `review-20261027`:

```powershell
$env:RETAIL_DUCKDB_BUILD_PATH = 'warehouse/lat3/bat.duckdb'
& $dbt build --project-dir retail_dbt --profiles-dir retail_dbt --target duckdb --target-path warehouse/lat3/target_bat `
  --vars '{\"snapshot_path\": \"D:/retail-analytics-schema/warehouse/pipeline/lat2/snapshots/47e7cbe765d9\", \"extensions\": [\"orders_enriched\"]}'
```

Kỳ vọng: mọi node đạt; `dim_sales_employee` 200 dòng; `fact_order` 646.945 dòng, 0 NULL `sales_employee_sk`. Nếu RAM không đủ
thì ghi "chưa chạy" (PM chạy ở §6.5).

### 6.3 Tắt phần mở rộng: SQL biên dịch trùng bản trước

Biên dịch với **đúng** `--vars` của lượt `review-20261027` (đọc `release_id, snapshot_id, code_version, snapshot_path,
forecast_path` từ `warehouse/pipeline/review-20261027/runs/review-20261027/context.json`), `--target-path` riêng, file DuckDB
tạm, rồi so cả cây `compiled/` với `warehouse/pipeline/review-20261027/runs/review-20261027/duckdb/compiled/`.

Kỳ vọng: **không khác file nào, không khác ký tự nào** (cùng vars nên cả `rpt_build_info` cũng trùng). Báo cáo ghi lệnh và
kết quả so (số file, số file khác).

### 6.4 Cổng 5: `dbt compile --target databricks` (thử)

`.venv` không có dbt-databricks; `D:/retail-analytics/.venv-databricks` có. Thử biên dịch phần bật với biến môi trường **giả**
(`DATABRICKS_HOST=example.invalid`, `DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/x`, `DATABRICKS_TOKEN=x`), `--vars` có
`release_id` giả và `extensions`, chỉ chọn `stg_orders_enriched dim_sales_employee fact_order` và test T1–T4. Không dùng
token hay file `.env.*.local` thật.

- Biên dịch được: ghi SQL Databricks của ba model vào báo cáo (đường dẫn file).
- dbt đòi kết nối thật: ghi "chưa chạy được, chuyển cổng 5 sang lát 4", kèm thông báo lỗi.

### 6.5 Lệnh PM tự chạy: bản ứng viên local qua `validate`, không publish

Stage `build` cần stage `forecast` (`check_forecast`), khoảng 5 phút và nặng RAM, nên PM chạy ngoài Claude Code:

```powershell
cd D:\retail-analytics-schema
$py = 'D:/retail-analytics/.venv/Scripts/python.exe'
$r = 'warehouse/pipeline/lat3'
& $py -m scripts.pipeline.cli prepare  --run-id lat3-bat --root $r --extension orders_enriched
& $py -m scripts.pipeline.cli forecast --run-id lat3-bat --root $r
& $py -m scripts.pipeline.cli build    --run-id lat3-bat --root $r
& $py -m scripts.pipeline.cli validate --run-id lat3-bat --root $r
& $py -m scripts.pipeline.cli history  --root $r
```

Dừng ở `validate` (tiêu chí nghiệm thu 5 của §5b tien_hoa: không publish). Kỳ vọng: `snapshot_id` `47e7cbe765d9`; dbt mọi node
đạt; `validate` qua G/COGS 3.833 ngày, sức khỏe `tot`, cổng hiển thị qua.

## 7. Lệnh chạy test

```powershell
cd D:\retail-analytics-schema
D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest scripts/ingest/tests -q -p no:cacheprovider
D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest scripts/pipeline/tests -q -p no:cacheprovider
D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest scripts -q -p no:cacheprovider
```

## 8. Báo cáo của GPT khi xong (PM dán cho Claude rà)

- Danh sách file tạo/sửa; với file đã có trong Git, tóm tắt từng chỗ đổi.
- Số đạt/trượt/skip của ba lệnh §7.
- Kết quả thử vô hiệu (§5.1): phần nào, test nào trượt; công cụ để ở đâu.
- Kết quả §6.1–§6.4 (hoặc "chưa chạy" kèm lý do); với §6.3 ghi số file đã so và số file khác.
- SQL biên dịch DuckDB của `stg_orders_enriched`, `dim_sales_employee`, `fact_order` (bật) và đoạn sửa của `assert_rpt_health.sql`.
- Giới hạn còn lại, chỗ làm khác phiếu (nếu có) và vì sao.

## 9. Rà của Claude (Claude ghi, GPT đọc để sửa)

| Lượt | Ngày | Kết quả | Phát hiện (mức nặng) | GPT đã sửa |
|---|---|---|---|---|
| 1 | 2026-10-28 | **Chưa đạt, sửa nhẹ** | C1 (vừa), C2 (thấp); C3–C5 ghi nhận, không phải sửa | C1, C2 (lượt 2) |
| 2 | 2026-10-28 | **Đạt** | C6 (thấp, tùy PM): D9 khớp lỗi quá rộng | C6 (lượt 3, PM chọn sửa trước khi commit) |
| 3 | 2026-10-28 | **Đạt** | Không còn phát hiện. D9 `match='hien_thi'`; Claude thử lại: chèn chuẩn hóa `lower()` → hai ca D9 trượt; pytest 114 / 73+2 / 219+3 | |

**Lượt 1, Claude tự chạy lại (không dựa vào số của GPT):**
- pytest §7: ingest 114 đạt; pipeline 70 đạt + 2 skip (61 + 9 ca D); `scripts` 216 đạt + 3 skip. File mới không BOM.
- §6.3 làm lại theo cách chặt hơn: `git archive HEAD retail_dbt` ra thư mục tạm, biên dịch HEAD và bản sửa với **cùng** vars của
  `review-20261027`, so 222/222 file: **chỉ** `rpt_build_info.sql` khác, đúng dòng `built_at_utc` (thời điểm biên dịch). Tắt phần mở
  rộng không đổi SQL nào. Kỳ vọng "cả `rpt_build_info` cũng trùng" của phiếu là sai của Claude (`built_at_utc` lấy giờ chạy). Hai hook
  khác khoảng trắng trong báo cáo GPT là do so bản compile với bản build, không phải do code lát 3.
- Bản sao `warehouse/lat3/bat.duckdb`: `dim_sales_employee` 200 dòng / 200 id; `fact_order` 646.945 dòng, 0 NULL; `fact_order` bỏ cột
  mới thì trùng `fact_order` của `review-20261027` cả hai chiều (`except all` = 0), thứ tự cột cũ giữ nguyên, chỉ thêm
  `sales_employee_sk`; nối `fact_order → dim` so thẳng với parquet `orders_enriched` (không qua staging): 0 đơn lệch nhân viên.
- Cổng hiển thị chạy trên `information_schema.columns` thật của DuckDB (đổi tên schema sang `r_x_*`): qua, 3 cột ẩn, 3 cột mart.
- Thử vô hiệu T1–T4 trên dữ liệu thật (sửa trong transaction rồi rollback, chạy SQL test đã biên dịch): **11/11 bị bắt**: gắn sai
  nhân viên, NULL một đơn, khóa mồ côi, dim sai thuộc tính, dim trùng id, dim trùng sk, staging mất dòng, trùng `order_id`, đơn mồ
  côi, vỡ phụ thuộc hàm, `_src_row` lủng.

**Phát hiện:**
- **C1 (vừa): cổng hiển thị hở khi hợp đồng ghi `hien_thi` thiếu hoặc sai chữ.** `validate_extension_visibility` chỉ xét
  `hien_thi == 'silver'` và `== 'mart'`; cột `nap` không có `hien_thi`, hay ghi `Silver`/`an`/gõ nhầm, rơi vào cả hai nhánh
  `if`, **không bị kiểm**, và `extension_contract.load` cũng không kiểm trường này. Một lỗi gõ trong hợp đồng làm
  `marital_status` lên mart mà `validate` vẫn qua: cổng hở chứ không chặn (Claude đã chạy: bỏ `hien_thi` hoặc ghi `Silver` cho
`marital_status`, đặt cột này vào `r_x_marts.dim_sales_employee` → cổng trả `hidden_columns_checked: 2`, không dừng). Sửa trong `cli.py` (lát này không sửa
  `extension_contract.py`): mọi cột `nap` phải có `hien_thi` thuộc `{'mart', 'silver'}`, không thì dừng và nêu tên cột. Thêm ca
  **D9** (hợp đồng trong `tmp_path` bỏ `hien_thi` của `marital_status`, hoặc ghi `Silver`: dừng), có thử vô hiệu.
- **C2 (thấp): D5 không phân biệt "cột mart nằm ở reporting chứ không ở marts".** Bỏ điều kiện `if schema == marts` khi tính
  `available` thì D5 vẫn qua (Claude đã thử trên bản sao: 9/9 test D vẫn đạt). Thêm một ca: `sales_employee_name` chỉ có ở `r_x_reporting.<bảng>` thì dừng.
- C3 (ghi nhận): `assert_rpt_health.sql` cộng cố định `orders_enriched` chứ không đếm `var('extensions')`. Chấp nhận: mỗi nguồn mở
  rộng đều cần model và khai báo nguồn riêng; truyền tên khác thì cloud trượt (dừng an toàn), không lọt.
- C4 (ghi nhận): khối nguồn `raw` thứ hai chỉ đọc parquet; bật phần mở rộng mà không có `snapshot_path` thì dbt báo không thấy file.
  Đúng ý: phần mở rộng chỉ đi qua `prepare --extension`.
- C5 (việc lát 4/5): `stg_orders_enriched` trên Databricks là view ở `r_<rid>_staging`, có `marital_status`/`education_level`.
  Cổng chỉ kiểm marts/reporting, nên lát 4/5 phải giữ quyền app/chat chỉ trên marts/reporting (kiểm GRANT, `docs/phan_quyen.md`).

**GPT sửa C1, C2 rồi báo lại:** ba lệnh §7; kết quả thử vô hiệu D1–D9 (cả ca C2); không cần chạy lại §6.1–§6.3 nếu chỉ sửa `cli.py`
và file test.

**Lượt 2 (2026-10-28): Đạt.** GPT chỉ sửa `cli.py` (thêm 2 dòng kiểm `hien_thi`) và file test (D9 hai ca, thêm ca C2).
- Claude chạy lại §7: ingest 114 đạt; pipeline 73 đạt + 2 skip; `scripts` 219 đạt + 3 skip. Hai file không BOM.
- Claude tự thử vô hiệu trên bản sao `scripts/` (không dùng công cụ của GPT): bỏ kiểm `hien_thi` → hai ca D9 trượt; bỏ
  `schema == marts` → ca C2 trượt. C1, C2 đóng.
- **C6 (thấp, tùy PM):** D9 khớp lỗi bằng chữ `marital_status`, mà thông báo "chỉ được hiện ở silver" cũng chứa chữ này. Nếu code tự
  chuẩn hóa (`Silver` → `silver`, thiếu → `silver`) thì D9 vẫn qua (Claude đã thử: 12/12 đạt). Code hiện tại **không** chuẩn hóa, nên
  không có lỗi; chỉ là test chưa giữ được quy tắc "không tự chuẩn hóa". Sửa một dòng: `match='hien_thi'` trong D9.

## 10. Câu hỏi PM chốt trước khi giao

| # | Câu hỏi | Đề xuất của Claude | PM chốt |
|---|---|---|---|
| 1 | Đơn không có nhân viên (dòng `orders_enriched` bị cách ly ở `prepare`, tối đa 1%): `sales_employee_sk` để NULL hay trỏ tới một dòng "Không rõ" trong dim? | **NULL**, theo lệ `ship_date_sk` của `fact_order` (NULL khi chưa gửi); test T4 kiểm đúng số đơn NULL. Dòng "Không rõ" làm dim 201 dòng và lẫn vào đếm nhân viên ở lát 5 | **2026-10-28: NULL** |
| 2 | Tên khóa thay thế: `sales_employee_sk` (quy ước repo: `customer_sk`, `order_junk_sk`...) hay `sales_employee_key` (tien_hoa §7)? | **`sales_employee_sk`**, khớp repo; Claude sửa tên ở tien_hoa §7 sau khi PM duyệt | **2026-10-28: `sales_employee_sk`** (tien_hoa §7 đã sửa theo) |

**Việc theo sau, không giao GPT ở lát này:**
- Airflow (`deploy/`) chưa truyền `--extension`: lát 4.
- `apps/retail_app/tests/test_databricks.py:38` cố định 14 nguồn: lát 4/5.
- `docs/star_schema.md` thêm `dim_sales_employee`: cần cell chứng minh trong notebook (quy ước `.md` ↔ notebook), Claude/PM làm
  sau khi bản ứng viên đạt.
