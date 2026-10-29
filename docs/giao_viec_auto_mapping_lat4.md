# Giao việc: auto mapping, lát 4 (lên Databricks: Airflow truyền `--extension`, test cloud theo số nguồn, lượt chạy production)

Soạn ngày 2026-10-28. PM giao, Claude soạn phiếu. GPT code phần nhỏ ở §1–§5; Claude rà độc lập trước khi commit theo 5 bước rà ở
đầu [giao_viec_theo_so_do.md](giao_viec_theo_so_do.md). Chưa đạt thì Claude ghi phát hiện vào §9, GPT sửa tiếp. Phần chạy cloud
(§6) do PM tự chạy theo lệnh trong phiếu; Claude chỉ đọc kết quả.

Đọc trước:
- [tien_hoa_schema.md](tien_hoa_schema.md) §9 bước 6 (7 cổng production, thứ tự chạy cloud), §10 mục 3 và 6;
- [giao_viec_auto_mapping_lat3.md](giao_viec_auto_mapping_lat3.md) §9 (C3–C5) và §10;
- [automation_batch.md](automation_batch.md) mục Airflow Docker (dựng image từ `git archive`, target của lịch);
- `AGENTS.md`, `CLAUDE.md`, skill `retail-platform-validation`.

## 0. Lát 4 nằm ở đâu

| Lát | Việc | Cổng production (§9 bước 6 tien_hoa) |
|---|---|---|
| 1 | Đề xuất ánh xạ (xong, `942d8dc`) | |
| 2 | Hợp đồng đã duyệt, `prepare --extension`, cách ly 1% (xong; đã vào `main` qua PR #19, `1572680`) | 1, 2 |
| 3 | dbt `stg_orders_enriched`, `dim_sales_employee`, `sales_employee_sk`; cổng hiển thị (xong, `16244fb…ace7361`, **chưa vào `main`**) | 5 (chưa: §0.1) |
| **4** | **Airflow truyền `--extension`, lịch giữ phần mở rộng, test cloud theo số nguồn; PM chạy tắt rồi bật trên Databricks, publish** | **3, 4, 5, 6, 7** |
| 5 | App/chat hiện chiều nhân viên (BA định câu hỏi và metric trước) | |

### 0.1 Bảy cổng: đã qua gì, lát 4 làm gì

| # | Cổng | Trạng thái | Lát 4 |
|---|---|---|---|
| 1 | Ánh xạ đã duyệt nằm trong Git | Qua (lát 2): `scripts/ingest/extensions/orders_enriched.yml` đã commit, nằm trong phần băm `code_version` | |
| 2 | Đếm dòng khi có cách ly | Qua (lát 2): manifest ghi `rows` = số dòng nhận, `so_dong_file`, `so_dong_cach_ly`; `_src_row` liền 1..N | |
| 3 | DuckDB 1.5.6 trong image (`.venv` là 1.5.5) | Chưa kiểm | PM chạy `prepare` trong container (§6, P3) |
| 4 | Dữ liệu trong container | Chưa: Airflow mount `./data` chỉ đọc từ `D:/retail-analytics`, mà `data/student_data/` ở đó chỉ có file zip | PM chép `orders_enriched.csv` (§6, P1) |
| 5 | dbt trên Databricks | **Chưa qua.** Lát 3 §6.4 biên dịch với host giả không ra file nào (adapter dò `example.invalid` rồi dừng; `warehouse/lat3/target_databricks/` không có `compiled/`) | Cổng thật là stage `build` của lượt bật trên cloud. Trượt thì dừng trước publish, bản đang phục vụ không đổi |
| 6 | Cột nhạy cảm ở raw/staging trên cloud | Đã có cơ chế (§3.3) | Thêm test âm (§4.3); bằng chứng cloud là `validate` lượt bật |
| 7 | Nhánh | PR #19 mới đưa tới lát 2 (`13a4a36`) vào `main` | PR lát 3 + 4 vào `main`, image dựng từ commit merge (§6, P0) |

## 1. Lát 4 làm gì, không làm gì

**GPT làm:**
1. DAG Airflow nhận tập phần mở rộng, chỉ truyền `--extension` cho stage `prepare` (§3.1).
2. Giá trị mặc định đọc từ biến môi trường, để lịch 08:00 giữ phần mở rộng sau khi bật (§3.2).
3. `apps/retail_app/tests/test_databricks.py`: bỏ số 14 cố định, kiểm số nguồn theo log nạp (§4.2).
4. Test âm cho quyền đọc: tài khoản app/chat không được thấy bảng staging/raw của phần mở rộng (§4.3).

**Không làm ở lát này:**
- không sửa `scripts/pipeline/*.py`, `scripts/ingest/*.py`, `scripts/ingest/extensions/*.yml`, `retail_dbt/`, `apps/retail_app/`
  ngoài hai file test ở §4.2–§4.3; thấy lỗi ở đó thì ghi vào báo cáo, không tự sửa;
- không model `reporting` mới, không sửa `ai_readonly_relations` / `app_read_relations` (lát 5);
- không sửa comment "14 nguồn" trong `scripts/ingest/ingest_databricks.py:6`, `retail_dbt/models/reporting/rpt_health_ingest.sql:12`
  (chỉ là comment, ghi vào báo cáo), không sửa `apps/retail_app/tests/test_m5.py:86` (chỉ chạy PostgreSQL local, không có phần mở rộng);
- không chạy Docker, Airflow hay Databricks; không đọc `.env.*.local`, không dùng token thật; không sửa `docs/`, notebook.

**Được sửa:** `deploy/airflow/dags/retail_batch_pipeline.py`, `deploy/airflow/env.example` (thêm một dòng biến mới, để trống),
`apps/retail_app/tests/test_databricks.py` (chỉ `test_databricks_suc_khoe_tot` và hàm phụ mới).
**Được tạo:** test pytest mới trong `scripts/pipeline/tests/` và `apps/retail_app/tests/` (file **mới**).

## 2. Môi trường và ràng buộc

Giữ §2 của phiếu lát 3: worktree `D:/retail-analytics-schema`, nhánh `schema/myuyen` (HEAD `ace7361`); Python
`D:/retail-analytics/.venv/Scripts/python.exe`, không cài thêm gói (`.venv` **không có Airflow**); không sửa `data/`; không stage,
commit hay push; UTF-8 không BOM. Comment tiếng Việt, giọng như code hiện có.

Công cụ thử vô hiệu để ngoài `scripts/` (ví dụ `warehouse/schema_review/`), không tạo file kiểu `verify_extension_mutations.py`
trong gói code (lát 2 B5).

## 3. Thiết kế

### 3.1 DAG nhận phần mở rộng

- Thêm param `extensions`: mảng tên, mỗi tên khớp `^[a-z][a-z0-9_]*$` (cùng luật tên với `extension_contract.load`).
  Trigger tay: `--conf '{"target": "databricks", "extensions": ["orders_enriched"]}'`.
- `command(stage, context)` thêm `--extension <tên>` cho từng tên (bỏ trùng, theo thứ tự sắp xếp) **chỉ khi `stage == 'prepare'`**.
  `cli.py:517` từ chối `--extension` ở stage khác (`ap.error`), và từ stage thứ hai trở đi CLI đọc tập phần mở rộng từ `context.json`.
- Không có phần mở rộng: lệnh của cả 5 stage **trùng từng phần tử** bản hiện nay.
- Tên không có hợp đồng: CLI đã dừng ở `prepare` (`extension_contract.load` không thấy file). DAG không lặp lại kiểm này.

### 3.2 Lịch 08:00 phải giữ phần mở rộng

Lịch không truyền được conf. Nếu mặc định của `extensions` là rỗng thì sau khi publish bản bật:
- 08:00 hôm sau, `prepare` dựng snapshot `5bd9a84aaf73` (không phần mở rộng);
- bản đang phục vụ có snapshot `47e7cbe765d9`, nên kiểm bỏ qua ở `cli.py:381` không bỏ qua;
- lượt lịch build, validate rồi **publish bản 14 nguồn**: `dim_sales_employee` biến khỏi production.

Thiết kế theo lệ `RETAIL_PIPELINE_DEFAULT_TARGET`:
- mặc định của `extensions` đọc từ `RETAIL_PIPELINE_DEFAULT_EXTENSIONS`, danh sách cách nhau bằng dấu phẩy, bỏ khoảng trắng hai đầu
  và phần tử rỗng; không đặt hoặc rỗng thì `[]`;
- một phần tử sai luật tên thì **DAG lỗi lúc nạp** (hiện ngay trên UI), không âm thầm bỏ phần tử;
- comment cạnh param ghi lý do (lịch không truyền conf) và hệ quả khi rollback (§6, P8).

Với biến này đặt `orders_enriched`, lịch 08:00 dựng `47e7cbe765d9`; snapshot và `code_version` trùng bản đang phục vụ thì `bo_qua`
ngay ở `prepare`, như lịch hiện nay.

### 3.3 Quyền đọc của app/chat (cổng 6, C5 lát 3): đã có cơ chế, lát 4 chỉ thêm test âm

Đã kiểm trong code (chỉ đọc):
- `cli.consumers()` lấy danh sách bảng từ `retail_dbt/dbt_project.yml` (`app_read_relations`, `ai_readonly_relations` và hai danh sách tùy
  chọn). Mọi phần tử đều là `reporting.*`.
- `cli.reader_grants` chỉ cấp `USE CATALOG`, `USE SCHEMA` và `SELECT` trên registry và các bảng đó trong `r_<rid>_reporting`.
- `cli.verify_consumers` (chạy ở `validate` và `publish`) đăng nhập bằng **chính** service principal của app và của chat, rồi gọi
  `dwh.guarded._check_dbx_identity`. Hàm này từ chối khi tài khoản có quyền ngoài danh sách, hoặc **nhìn thấy** bảng ngoài danh sách
  (`_dbx_violations`, luật `seen`).

Vậy `stg_orders_enriched` (view ở `r_<rid>_staging`, có `marital_status`, `education_level`) và `orders_enriched` ở `r_<rid>_raw`
không đọc được bằng tài khoản app/chat. Nếu ai đó cấp thêm quyền, `validate` dừng. `dim_sales_employee` nằm ở marts, cũng **không**
có quyền đọc cho app/chat: lát 4 không làm app/chat hiện nhân viên (lát 5 thêm model `reporting` và danh sách quyền).

## 4. Yêu cầu từng phần

### 4.1 `deploy/airflow/dags/retail_batch_pipeline.py`, `deploy/airflow/env.example`

Như §3.1–3.2. `env.example` thêm `RETAIL_PIPELINE_DEFAULT_EXTENSIONS=` (để trống) kèm một dòng comment giải thích.

### 4.2 `apps/retail_app/tests/test_databricks.py`

`test_databricks_suc_khoe_tot` đang buộc `n_sources_ingested == 14` và 14 dòng log nạp. Sửa thành kiểm theo log:
- tập tên nguồn trong `queries.health_ingest('databricks')` **chứa đủ** 14 nguồn của `scripts/ingest/source_contract.SOURCES`;
- phần dư (nếu có) chỉ gồm tên có hợp đồng trong `scripts/ingest/extensions/*.yml`;
- `n_sources_ingested` = số dòng log = số tên phân biệt.

**Không** cố định 15: rollback về bản 14 nguồn thì test phải vẫn đạt. Registry không lưu `extensions` nên test không tra được tập
mở rộng của bản đang phục vụ; kiểm theo log là đủ.

Tách phần kiểm thành hàm phụ thuần (nhận danh sách tên và số `n_sources_ingested`), rồi thêm test **không cần cloud** cho hàm phụ:

| Ca | Log nạp | Kỳ vọng |
|---|---|---|
| H1 | 14 nguồn lõi | đạt |
| H2 | 14 + `orders_enriched` | đạt |
| H3 | thiếu `orders` | trượt |
| H4 | 14 + tên không có hợp đồng | trượt |
| H5 | `n_sources_ingested` khác số dòng log | trượt |

Ghi trong báo cáo: lệnh PM chạy test cloud sau khi publish, chạy từ worktree nào, dựa trên cách `dwh/connection.py` tìm cấu hình
Databricks (đọc code, không đọc file `.env.*.local`).

### 4.3 Test âm quyền đọc (file mới, ví dụ `apps/retail_app/tests/test_extension_grants.py`)

Gọi thẳng hàm thuần `dwh.guarded._dbx_violations` (không cần cloud), với `allowed_relations` dựng từ `cli.consumers()` đặt vào
`r_x_reporting`, như `verify_consumers` làm:

| Ca | Tình huống | Kỳ vọng |
|---|---|---|
| G1 | Tài khoản có `SELECT` trên `r_x_staging.stg_orders_enriched` | từ chối, thông báo nêu bảng đó |
| G2 | `USE_SCHEMA` trên `r_x_staging` | từ chối |
| G3 | Không có quyền trực tiếp, nhưng danh sách đối tượng nhìn thấy có `r_x_raw.orders_enriched` | từ chối (luật `seen`) |
| G4 | Chỉ có đúng quyền `verify_consumers` cấp | đạt (ca chứng: G1–G3 không trượt vì dữ liệu giả sai dạng) |
| G5 | `cli.consumers()` | mọi phần tử bắt đầu bằng `reporting.`; không có `stg_orders_enriched`, `orders_enriched`, `dim_sales_employee` |

Dữ liệu giả dựng theo đúng dạng bộ mà `_check_dbx_identity` truyền vào (đọc `_DBX_GRANTS`, `_DBX_OBJECTS`). Nếu `apps/retail_app/tests`
đã có test sinh dữ liệu dạng này thì dùng lại hàm phụ của nó (import), không chép.

### 4.4 Test DAG (file mới, ví dụ `scripts/pipeline/tests/test_airflow_extensions.py`)

`.venv` không có Airflow. Test phải gọi **hàm `command` thật** của file DAG, không chép thân hàm: ví dụ đặt module giả cho `airflow`,
`airflow.sdk`, `airflow.exceptions` (và `pendulum` nếu `.venv` không có) vào `sys.modules` qua `monkeypatch`, rồi nạp file DAG bằng
`importlib`. Test AST hiện có (`test_pipeline.py:148–184`) giữ nguyên, phải vẫn đạt.

| Ca | Tình huống | Kỳ vọng |
|---|---|---|
| A1 | `params` không có `extensions` hoặc `[]`, cả 5 stage | lệnh trùng từng phần tử lệnh của code trước lát 4 (so với danh sách viết tay trong test) |
| A2 | `extensions: ['orders_enriched']` | `prepare` có đúng một cặp `--extension orders_enriched`; 4 stage còn lại không có `--extension` |
| A3 | `extensions` có tên trùng, sai thứ tự; kèm `snapshot_id` và `force` | `prepare` có mỗi tên một lần, theo thứ tự sắp xếp, cùng `--snapshot-id`, `--force` |
| A4 | Biến `RETAIL_PIPELINE_DEFAULT_EXTENSIONS` không đặt / rỗng / `' orders_enriched , '` | mặc định `[]` / `[]` / `['orders_enriched']` |
| A5 | Biến có phần tử sai luật tên (`'Orders'`, `'a b'`) | nạp file DAG lỗi |

Mỗi test chính phải trượt khi bỏ phần code tương ứng. Báo cáo ghi đã thử vô hiệu gì và test nào trượt, tối thiểu:
- truyền `--extension` cho mọi stage → A2 trượt;
- bỏ đọc biến môi trường → A4 trượt;
- bỏ kiểm luật tên → A5 trượt;
- bỏ luật `seen` trong bản sao `_dbx_violations` → G3 trượt;
- bỏ kiểm phần dư trong hàm phụ §4.2 → H4 trượt.

### 4.5 Kiểm thêm, chỉ đọc code, ghi vào báo cáo

- Trên Databricks, cổng hiển thị (`cli.validate_extension_visibility`) đọc `information_schema.columns` không ghi catalog. Xác nhận phiên
  của `scripts/pipeline/runtime.Databricks` đặt catalog là catalog của pipeline (`RETAIL_DATABRICKS_CATALOG`), để câu đó đọc đúng
  `retail_lab.information_schema`. (Sai catalog thì cổng báo thiếu cột mart, tức là dừng chứ không lọt; chỉ cần ghi lại.)
- Trong `validate` lượt bật trên cloud, phần so cloud–local (`compare`) chạy qua mọi bảng marts/reporting, gồm `dim_sales_employee`
  và `fact_order` có `sales_employee_sk`. Xác nhận `sales_employee_sk` (`row_number() over (order by sales_employee_id)`) cho cùng
  số trên DuckDB và Databricks: mã nhân viên chỉ gồm ký tự ASCII? Đọc từ parquet snapshot `47e7cbe765d9` để trả lời.

## 5. Hồi quy

| Bộ | Mốc (sau lát 3, `ace7361`) |
|---|---|
| `scripts/ingest/tests` | 114 đạt |
| `scripts/pipeline/tests` (test cũ không sửa) | 73 đạt, 2 skip |
| `pytest scripts` | 219 đạt + số test mới, 3 skip |
| `apps/retail_app/tests/test_databricks.py` | ghi số trước và sau khi sửa (không đặt `RETAIL_TEST_DATABRICKS` thì phần cloud skip) |
| file test mới ở `apps/retail_app/tests/` | đạt hết |

```powershell
cd D:\retail-analytics-schema
$py = 'D:/retail-analytics/.venv/Scripts/python.exe'
& $py -B -m pytest scripts/ingest/tests -q -p no:cacheprovider
& $py -B -m pytest scripts/pipeline/tests -q -p no:cacheprovider
& $py -B -m pytest scripts -q -p no:cacheprovider
& $py -B -m pytest apps/retail_app/tests/test_databricks.py apps/retail_app/tests/test_extension_grants.py -q -p no:cacheprovider
```

## 6. Lượt chạy production (sau khi Claude rà lát 4 đạt và PM cho commit)

GPT **không** chạy phần này. PM chốt 2026-10-28: Claude chạy P2–P5 (lượt cloud chạy nền), dừng ở `validate`, rà kết quả rồi **hỏi
PM trước P6 publish**; P7 PM tự sửa `.env.airflow.local` (Claude không đọc file này). Mọi lệnh chạy ở worktree chính `D:\retail-analytics` (nơi có
`docker-compose.airflow.yml`, `.env.airflow.local` và state `warehouse/pipeline/docker`). Container lấy tên theo các lần chạy trước
(`retail-analytics-airflow-scheduler-1`); khác thì xem `docker ps`.

**Không chạy stage cloud từ worktree hay từ `.venv`.** `code_version` băm cả `scripts/ingest`, nên file chưa commit
(`verify_extension_mutations.py`) làm lệch mã code. Chỉ chạy trong container dựng từ `git archive`.

Lượt đầu chạy CLI từng stage, như lần chạy cloud đầu tiên ngày 2026-10-17: dừng được giữa `validate` và `publish`. DAG chỉ dùng
lại sau khi đã đặt biến mặc định ở P7. Từ P3 trở đi, khai báo một lần trong cửa sổ PowerShell (container đã có biến môi trường
Databricks từ `.env.airflow.local`):

```powershell
function cli { docker exec -w /opt/retail retail-analytics-airflow-scheduler-1 /opt/pipeline/bin/python -m scripts.pipeline.cli @args }
```

**P0. Đưa code lên `main`.** Commit lát 4 trên `schema/myuyen`, mở PR lát 4 vào `main`, người kia review, merge. Ghi mã commit
merge là `<M>`. *Lát 3 đã vào `main` qua PR #20 (`c3d5364`, 2026-10-28); còn PR lát 4. PM chốt 2026-10-28: chờ code lát 4 rồi mới
dựng image, không chạy P2 từ `c3d5364`.*

**P1. Dữ liệu trong container (cổng 4).** Chép đúng file đã dùng ở local, rồi kiểm hash:

```powershell
Copy-Item D:\retail-analytics-schema\data\student_data\orders_enriched.csv D:\retail-analytics\data\student_data\
(Get-FileHash D:\retail-analytics\data\student_data\orders_enriched.csv -Algorithm SHA256).Hash
# kỳ vọng 59375877B6AB0A688522DF6F7DDF102F39D32E9CA8AC915F74C73F4CF2862F76 (csv_sha256 trong manifest 47e7cbe765d9)
```

*Đã làm 2026-10-28 (Claude chép theo yêu cầu của PM): SHA-256 khớp.*

**P2. Tạm dừng lịch, dựng image từ `<M>`.** Tránh khung 08:00.

```powershell
cd D:\retail-analytics
docker exec retail-analytics-airflow-scheduler-1 airflow dags pause retail_batch_pipeline
git fetch origin
$tmp = "$env:TEMP\retail-image-lat4"
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue; New-Item -ItemType Directory $tmp | Out-Null
git archive -o "$tmp.tar" <M> apps/retail_app scripts retail_dbt deploy
tar -xf "$tmp.tar" -C $tmp
docker build -f "$tmp\deploy\airflow\Dockerfile" -t retail-airflow:local $tmp
docker compose -f docker-compose.airflow.yml up -d --force-recreate airflow-api airflow-scheduler airflow-dag-processor
docker exec -w /opt/retail retail-analytics-airflow-scheduler-1 /opt/pipeline/bin/python -c "from scripts.pipeline.cli import code_version; print(code_version())"
```

Gửi Claude mã `code_version` in ra; Claude tính lại từ `<M>` để đối chiếu.

**P3. DuckDB 1.5.6 trong image (cổng 3).** Chạy `prepare` target duckdb ở root riêng, không đụng cloud:

```powershell
cli prepare --run-id lat4-img-tat --target duckdb --root warehouse/pipeline/lat4-image
cli prepare --run-id lat4-img-bat --target duckdb --root warehouse/pipeline/lat4-image --extension orders_enriched
```

Kỳ vọng: snapshot `5bd9a84aaf73` và `47e7cbe765d9`, `so_dong_cach_ly` 0. Claude so nội dung parquet `orders_enriched` với bản local
(`parquet_sha256` có thể khác giữa hai bản DuckDB; khác byte mà cùng nội dung thì không chặn).

**P4. Lượt tắt trên cloud, dừng ở `validate`.** Chứng minh code lát 3 + 4 không đổi bộ Datathon trên production.

```powershell
foreach ($s in 'prepare','forecast','build','validate') {
  cli $s --run-id dbx-lat4-tat-01 --target databricks --root warehouse/pipeline/docker
  if ($LASTEXITCODE) { break }
}
```

Kỳ vọng: snapshot `5bd9a84aaf73`; stage `validated`; kết quả `quality` không có khóa `hidden_columns_checked`. Không publish (§10 câu 2).

**P5. Lượt bật trên cloud, dừng ở `validate` (cổng 5 và 6).**

```powershell
cli prepare --run-id dbx-lat4-bat-01 --target databricks --root warehouse/pipeline/docker --extension orders_enriched
foreach ($s in 'forecast','build','validate') {
  cli $s --run-id dbx-lat4-bat-01 --target databricks --root warehouse/pipeline/docker
  if ($LASTEXITCODE) { break }
}
```

Kỳ vọng, PM gửi Claude `warehouse/pipeline/docker/runs/<run>/context.json` và log để rà:
- snapshot `47e7cbe765d9`;
- dbt trên Databricks mọi node đạt, gồm T1–T4 (đây là cổng 5);
- `quality`: `cloud_parity: true`, `hidden_columns_checked: 3`, `mart_columns_checked: 3`;
- `_ingest_log` 15 dòng, sức khỏe `tot`;
- `verify_consumers` qua với hai tài khoản app/chat: đây là bằng chứng cloud của cổng 6.

P5 thay cho lượt local §6.5 của phiếu lát 3 (PM chưa chạy): stage `build` trong container dựng cả DuckDB lẫn Databricks, và `validate`
so hai bên. Mốc của §6.5 lát 3 (dbt 224 node, `dim_sales_employee` 200 dòng) đọc trên log của P5.

**Kết quả chạy (2026-10-28 → 10-29).**
- P1–P3 đạt.
- P4 đạt: release `5d32a10432ad4e338975a23a` ở trạng thái `ready`, chưa publish, là đích rollback. dbt 225/225 trên cả DuckDB và
  Databricks; `cloud_parity: true`.
- P5:
  - `prepare` và `forecast` đạt: release `dbb80f5674af47fe9c98f796`, snapshot `47e7cbe765d9`, 0 dòng cách ly.
  - `build` trượt ở bước nạp raw lên cloud với lỗi `QUOTA_EXCEEDED.UC_RESOURCE_QUOTA_EXCEEDED`. Databricks Free cho mỗi metastore
    tối đa 500 bảng, trong khi catalog `retail_lab` có 552 bảng: 6 bộ `r_<release_id>_*`, mỗi bộ khoảng 80 bảng, chưa bộ nào được dọn.
  - PM duyệt xóa 3 bộ cũ (236 bảng): `16bfafc5…` (không có trong registry), `cfe19211…` và `b25b3e47…`. Còn lại 316 bảng.
  - Chạy lại `build` vẫn trượt, Databricks báo "estimated count 553": bảng đã xóa vẫn bị tính quota trong khoảng 7 ngày giữ để
    `UNDROP`, và không có lệnh tự phục vụ để xóa hẳn ngay.
  - PM chốt 2026-10-29: chờ Databricks xóa hẳn (khoảng 2026-11-05), rồi chạy lại `build` → `validate` với cùng run-id.
    Từ giờ tới khi publish, DAG giữ tạm dừng; app/chat vẫn đọc `03ad08c0…`.
- Hệ quả cho quy định giữ bản (chưa làm): một bản chiếm khoảng 80 bảng, bảng đã xóa còn chiếm quota thêm khoảng 7 ngày. Vì vậy
  phải dọn bản cũ trước ít nhất một tuần, hoặc chỉ giữ khoảng 4 bản.

**P6. Publish**, sau khi Claude rà P5 đạt. Lấy sẵn mã release đang phục vụ (`03ad08c0…`, đủ 24 ký tự) để rollback:

```powershell
cli history --target databricks --root warehouse/pipeline/docker
cli publish --run-id dbx-lat4-bat-01 --target databricks --root warehouse/pipeline/docker
```

**P7. Lịch giữ phần mở rộng.** PM thêm `RETAIL_PIPELINE_DEFAULT_EXTENSIONS=orders_enriched` vào `.env.airflow.local` (Claude không
đọc file này), recreate ba dịch vụ, bỏ tạm dừng rồi trigger một lượt **không kèm conf**. DAG đang tạm dừng thì lượt trigger tay chỉ
xếp hàng, không chạy. Bỏ tạm dừng xong, Airflow có thể chạy ngay mốc 08:00 vừa qua (như lần bật lịch 2026-10-19); lượt đó cũng không
kèm conf nên cùng kỳ vọng:

```powershell
docker compose -f docker-compose.airflow.yml up -d --force-recreate airflow-api airflow-scheduler airflow-dag-processor
docker exec retail-analytics-airflow-dag-processor-1 printenv RETAIL_PIPELINE_DEFAULT_EXTENSIONS   # phải in orders_enriched; không thì dừng ở đây
# Mặc định của param được tính lúc dag-processor nạp file DAG. Trước khi bỏ tạm dừng, mở form Trigger trên UI (127.0.0.1:8080):
# ô extensions phải sẵn ["orders_enriched"]. Chưa thấy thì chờ dag-processor nạp lại, không bỏ tạm dừng.
docker exec retail-analytics-airflow-scheduler-1 airflow dags unpause retail_batch_pipeline
docker exec retail-analytics-airflow-scheduler-1 airflow dags trigger retail_batch_pipeline --run-id dbx-lat4-lich-01
# kỳ vọng: context.json có extensions ["orders_enriched"], stage skipped (bo_qua), bản đang phục vụ không đổi
```

Lượt này ra `bo_qua` chỉ khi biến đã đặt đúng. Nếu nó build lại, dừng DAG ngay và báo Claude: biến chưa vào container, lượt đó sẽ
publish bản 14 nguồn.

**P8. Rollback (để sẵn, chỉ chạy khi cần).** Đích rollback là **bản tắt của P4** (`release_id` trong
`warehouse/pipeline/docker/runs/dbx-lat4-tat-01/context.json`). Lệnh `rollback` nhận mọi bản có trong registry, kể cả bản `ready` chưa
từng publish (`cli.py:534–540`), và vẫn kiểm quyền đọc của app/chat trước khi đổi con trỏ.

```powershell
docker exec retail-analytics-airflow-scheduler-1 airflow dags pause retail_batch_pipeline
cli rollback --run-id rollback-lat4 --release-id <release_id của P4> --target databricks --root warehouse/pipeline/docker
```

Rồi **xóa** `RETAIL_PIPELINE_DEFAULT_EXTENSIONS` trong `.env.airflow.local`, recreate ba dịch vụ, kiểm form Trigger như P7 (ô
`extensions` rỗng), mới bỏ tạm dừng. Khi đó lịch 08:00 dựng `5bd9a84aaf73` với cùng `code_version` của bản P4, nên `bo_qua`.

Vì sao không lấy `03ad08c0…` làm đích: bản đó dựng từ code `67042493…`, còn image đã mang code lát 3 + 4. Rollback về đó thì 08:00 thấy
cùng snapshot nhưng khác code, nên dựng và publish một bản mới ngay sáng hôm sau. Chỉ dùng `03ad08c0…` khi chính image mới có lỗi; lúc
đó giữ DAG tạm dừng cho tới khi dựng lại image cũ.

Hai bẫy ngược chiều (§3.2):
- bản đang phục vụ là bản tắt mà biến vẫn `orders_enriched`: 08:00 dựng lại bản bật và publish;
- bản đang phục vụ là bản bật mà biến trống: 08:00 publish bản 14 nguồn.

**P9. Kiểm sau publish.** Test cloud theo lệnh GPT ghi ở §4.2; mở app và chat trên Databricks, hỏi 2–3 câu PS1–PS5 đã có: phải
trả lời như trước. Lát 4 **không** nghiệm thu "app/chat hiện nhân viên" (lát 5).

## 7. Báo cáo của GPT khi xong (PM dán cho Claude rà)

- Danh sách file tạo/sửa; với file đã có trong Git, tóm tắt từng chỗ đổi.
- Số đạt/trượt/skip của các lệnh §5.
- Kết quả thử vô hiệu (§4.4): phần nào, test nào trượt; công cụ để ở đâu.
- Đoạn diff của DAG; lệnh của 5 stage trước và sau khi bật (in từ test A1–A2).
- Trả lời hai ý §4.5 và cách chạy test cloud (§4.2).
- Giới hạn còn lại, chỗ làm khác phiếu (nếu có) và vì sao; chỗ thấy lỗi ngoài phạm vi sửa (§1).

## 8. Không giao GPT ở lát này

- §6 (Docker, Airflow, Databricks): PM chạy, Claude rà kết quả.
- Ghi kết quả lượt cloud vào `docs/automation_batch.md` và `tien_hoa_schema.md` §9 bước 6: Claude làm sau P9, hỏi PM trước khi commit.
- `docs/star_schema.md` thêm `dim_sales_employee`: cần cell chứng minh trong notebook, làm sau khi production đạt.

## 9. Rà của Claude (Claude ghi, GPT đọc để sửa)

| Lượt | Ngày | Kết quả | Phát hiện (mức nặng) | GPT đã sửa |
|---|---|---|---|---|
| 1 | 2026-10-28 | **Đạt** | Không có phát hiện phải sửa. Ghi nhận: hành vi param mảng trên Airflow thật chưa kiểm (P7 kiểm form Trigger) | |

**Lượt 1, Claude tự chạy lại (không dựa vào số của GPT):**
- Diff đúng phạm vi §1: sửa 3 file (DAG, `env.example`, `test_databricks.py`), tạo 2 file test; không đụng `scripts/pipeline`, `scripts/ingest`,
  `retail_dbt`, code app. Không BOM, `git diff --check` đạt.
- pytest §5: ingest 114 đạt; pipeline 82 đạt + 2 skip (73 + 9 ca A); `scripts` 228 đạt + 3 skip; hai file app 16 đạt + 27 skip (phần cloud).
  Test AST cũ của DAG (`test_pipeline.py`) vẫn đạt.
- `source_contract.SOURCES` có đúng 14 tên, trùng khóa `manifest['sources']` của snapshot `47e7cbe765d9` trừ `orders_enriched`, nên hàm
  kiểm log nạp so đúng tên nguồn.
- Thử vô hiệu trên bản sao (công cụ riêng của Claude): truyền `--extension` mọi stage → A2 trượt; bỏ đọc biến → A4, A5 trượt; bỏ kiểm tên
  → A5 trượt; bỏ kiểm nguồn dư → H4 trượt; bỏ luật `seen` của `_dbx_violations` → G3 (app, chat) trượt. 5/5 bị bắt.

## 10. Câu hỏi PM chốt trước khi giao

| # | Câu hỏi | Đề xuất của Claude | PM chốt |
|---|---|---|---|
| 1 | Lịch 08:00 sau khi bản bật lên production: giữ phần mở rộng bằng biến `RETAIL_PIPELINE_DEFAULT_EXTENSIONS` (§3.2), hay tạm dừng lịch tới lát 5? | **Dùng biến.** Lịch vẫn chạy mỗi sáng và `bo_qua` khi dữ liệu, code không đổi. Tạm dừng lịch thì mất phần tự động đã nghiệm thu S6, và quên bật lại cũng không ai biết | **2026-10-28: dùng biến** (PM cho commit code lát 4 theo §3.2) |
| 2 | Lượt tắt (P4) trên cloud: dừng ở `validate`, hay publish luôn? | **Dừng ở `validate`.** Chỉ cần chứng minh bộ Datathon không đổi. Bản tắt ở trạng thái `ready` vẫn là đích rollback (P8): cùng code với image mới, nên lịch 08:00 không dựng lại sau rollback. Publish nó thì chỉ thêm một lần đổi con trỏ không cần. Lượt bật (P5–P6) mới publish | **2026-10-28: dừng ở `validate`** |
