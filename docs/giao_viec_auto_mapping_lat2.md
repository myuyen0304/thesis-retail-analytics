# Giao việc: auto mapping, lát 2 (nạp ánh xạ đã duyệt của `orders_enriched` vào snapshot, cách ly 1%)

Soạn ngày 2026-10-28. PM giao, Claude soạn phiếu. GPT code; Claude rà độc lập trước khi commit, theo 5 bước rà ở đầu
[giao_viec_theo_so_do.md](giao_viec_theo_so_do.md). Chưa đạt thì Claude ghi phát hiện vào §9, GPT sửa tiếp. PM đọc báo cáo
rà rồi mới cho commit.

Thiết kế gốc: [tien_hoa_schema.md](tien_hoa_schema.md), đọc trước **§5b, §6 (cả 6.1 và 6.2), §9 bước 3 và bước 6, §10**.
Lát trước: [giao_viec_auto_mapping_lat1.md](giao_viec_auto_mapping_lat1.md) (code đã có ở `scripts/ingest/adapters.py`,
`schema_diff.py`, `auto_mapping.py`). Đọc thêm `AGENTS.md`, `CLAUDE.md`.

## 0. Lát 2 nằm ở đâu trên đường lên production

PM chốt 2026-10-28: phải chạy được trên production Databricks, và app/chat hiện chiều nhân viên bán hàng (§10 mục 6).
Các lát tiếp theo của `orders_enriched`:

| Lát | Việc | Cổng production (§9 bước 6) |
|---|---|---|
| 1 | Đề xuất ánh xạ cho BA (đã xong, `942d8dc`) | |
| **2** | **Hợp đồng mở rộng đã duyệt nằm trong Git; `prepare` dựng parquet nguồn mở rộng vào snapshot; cách ly theo ngưỡng 1%** | **1, 2** |
| 3 | dbt: `dim_sales_employee`, `sales_employee_key` trong `fact_order`, bật bằng biến `extension`; bản ứng viên local qua `validate` | 5 |
| 4 | Lên Databricks: dựng image, chạy tắt rồi bật phần mở rộng, publish | 3, 4, 6, 7 |
| 5 | App/chat hiện chiều nhân viên | |

## 1. Lát 2 làm gì, không làm gì

**Làm:**
1. Ghi **hợp đồng mở rộng đã duyệt** của `orders_enriched` vào repo (nội dung ở §3; PM duyệt phiếu này là duyệt ánh xạ).
2. Module đọc hợp đồng mở rộng: chỉ nhận mục `da_duyet`, sai thì dừng.
3. Module dựng nguồn mở rộng: đọc file qua `adapters.read_file`, kiểm từng dòng, cách ly dòng sai, áp ngưỡng 1%,
   ra parquet và mục manifest.
4. Nối vào `snapshot.prepare` / `snapshot.validate` và CLI (`--extension`). **Không bật phần mở rộng thì mọi thứ y như cũ.**

**Không làm ở lát này:**
- không sửa dbt (`retail_dbt/`), không model mới; lát 3;
- không sửa `scripts/pipeline/runtime.py` (code Databricks; manifest phải hợp với nó như hiện tại, xem §4.4);
- không sửa `scripts/ingest/source_contract.py`, không đổi ngữ nghĩa kiểm của `scripts/pipeline/contract.py`
  (được import `write_quarantine` để dùng lại);
- không sửa `adapters.py`, `schema_diff.py`, `auto_mapping.py` của lát 1;
- không luật miền, không luật sửa tầng 2 (§6.1): `orders_enriched` không cần, để lát của `tf`/`eprom`;
- không shipments, eprom, epd, tf;
- không Airflow (`deploy/`), không `apps/`, không Databricks, không notebook.

**Được sửa (file đã có trong Git):** chỉ `scripts/pipeline/snapshot.py` và `scripts/pipeline/cli.py`.
**Được tạo:** file mới dưới `scripts/ingest/` (gợi ý tên ở §4) và test mới dưới `scripts/ingest/tests/` và
`scripts/pipeline/tests/` (file test **mới**; không sửa test cũ).

## 2. Môi trường và ràng buộc

Giữ nguyên §2 của phiếu lát 1: worktree `D:/retail-analytics-schema`, nhánh `schema/myuyen`; Python
`D:/retail-analytics/.venv/Scripts/python.exe` (duckdb 1.5.5, pyarrow, pyyaml có sẵn), **không cài thêm gói**; tính bằng
DuckDB SQL, không lặp từng dòng bằng Python; dữ liệu trong `data/student_data/` không tin cậy; không sửa `data/`;
không stage, commit hay push. Comment và docstring tiếng Việt, định danh tiếng Anh, giọng như `scripts/pipeline/snapshot.py`.

Thêm cho lát này:
- Image production dùng `duckdb==1.5.6` (`deploy/airflow/requirements-pipeline.txt`). Không dùng tính năng chỉ có ở
  1.5.6; ghi trong báo cáo nếu có chỗ phụ thuộc phiên bản.
- `snapshot_id` phải giống nhau giữa Windows (local) và Linux (container): mọi hash của file văn bản trong repo
  (hợp đồng mở rộng) tính sau khi đổi `\r\n` thành `\n`, như `code_version()` trong `cli.py`.

## 3. Hợp đồng mở rộng đã duyệt (PM/BA duyệt qua phiếu này)

Nội dung dưới đây lấy từ đề xuất lát 1 (`mapping_de_xuat.yml` của `orders_enriched`) cộng các quyết định ở
`tien_hoa_schema.md` §7 và §10. GPT **chép đúng** vào `scripts/ingest/extensions/orders_enriched.yml`; không tự thêm,
bớt hay đổi quyết định. `ngay_duyet` là ngày PM duyệt phiếu (§10 phiếu này).

| Mục | Giá trị |
|---|---|
| `ten` (tên nguồn mở rộng, cũng là tên bảng raw) | `orders_enriched` |
| `file` (tương đối với `--data`) | `student_data/orders_enriched.csv` |
| `header` (đúng thứ tự file) | `order_id, order_date, customer_id, zip, city, region, district, order_status, payment_method, device_type, order_source, sales_employee_id, sales_employee_name, marital_status, education_level, years_experience, comment` |
| `nguong_cach_ly` | `0.01` (§10 câu 1 của tien_hoa_schema) |
| `khoa_noi` | `order_id` của file → `orders.order_id` (nguồn lõi) |
| `duyet_boi`, `ngay_duyet` | `PM (myuyen0304)`, `2026-10-28` (PM duyệt phiếu, §10 câu 2) |

Từng cột (`xu_ly`):

| Cột | `xu_ly` | Kiểu | Được rỗng | `hien_thi` | Lý do |
|---|---|---|---|---|---|
| `order_id` | `khoa_noi` | `integer` | không | | Nối về `orders` |
| `order_date, customer_id, zip, order_status, payment_method, device_type, order_source` | `doi_chieu_loi` | theo `COLUMNS['orders']` | | | Đã có ở `orders`; **không nạp lại**, chỉ kiểm khớp với `orders` của cùng snapshot |
| `city, region, district` | `bo` | | | | Thừa: suy được từ `geography` qua `zip` (lát 1, 646.945/646.945) |
| `sales_employee_id` | `nap` | `string` (vd. `EMP0143`) | không | `mart` | Khóa thực thể `sales_employee` |
| `sales_employee_name` | `nap` | `string` | không | `mart` | PM chốt 2026-10-28: hiện tên |
| `marital_status` | `nap` | `string` | không | `silver` | Nhạy cảm, không lên mart/app/chat (§10 câu 3) |
| `education_level` | `nap` | `string` | không | `silver` | Như trên |
| `years_experience` | `nap` | `integer` | không | `mart` | |
| `comment` | `nap` | `string` | có | `silver` | §10 câu 5: dừng ở silver |

Thực thể: `sales_employee`, khóa `sales_employee_id`, thuộc tính `sales_employee_name, marital_status, education_level,
years_experience` (phụ thuộc hàm, lát 1: 0 vi phạm). `comment` **không** thuộc thực thể.

Mỗi cột, thực thể và cả file đều có `trang_thai: da_duyet`. `hien_thi` chỉ được ghi, lát 3 mới đọc.

## 4. Yêu cầu từng phần

GPT được tự chọn cách cài đặt, miễn đạt hành vi và test ở §6. Ngưỡng và tên lý do là **hằng số có tên**.

### 4.1 Đọc hợp đồng mở rộng (gợi ý `scripts/ingest/extension_contract.py`)

- Đọc `scripts/ingest/extensions/<ten>.yml` bằng `yaml.safe_load`. Trả cấu trúc đã kiểm, kèm `hop_dong_sha256`
  (sha256 của file sau khi đổi `\r\n` → `\n`).
- **Dừng (ValueError, nêu tên file và mục sai)** khi:
  - mục nào (file, cột, thực thể) có `trang_thai` khác `da_duyet` (tiêu chí nghiệm thu 1, §5b);
  - thiếu `duyet_boi` hoặc `ngay_duyet`;
  - `ten` trùng một nguồn trong `SOURCES`, hoặc không khớp `[a-z][a-z0-9_]*` (sẽ thành tên bảng Databricks);
  - `xu_ly` ngoài `khoa_noi / doi_chieu_loi / bo / nap`; cột trong `header` không có mục, hoặc mục không có trong `header`;
  - `khoa_noi` trỏ tới nguồn không thuộc `SOURCES`; cột `doi_chieu_loi` không có trong `COLUMNS` của nguồn đó;
  - kiểu không thuộc tập kiểu của `COLUMNS` (`string`, `integer`, `date`, `double`, `decimal(p,s)`);
  - `nguong_cach_ly` ngoài `[0, 1)`.

### 4.2 Dựng nguồn mở rộng (gợi ý `scripts/ingest/extension_prepare.py`)

Đầu vào: hợp đồng đã kiểm, thư mục `data`, và bảng `orders` lõi của **cùng lần prepare** (parquet vừa dựng).

**Kiểm cấp file (sai thì dừng, không cách ly):**
- header đọc qua `adapters.read_file` phải **đúng bằng** `header` của hợp đồng (cùng tên, cùng thứ tự). Lệch thì báo
  cột thêm/thiếu và nhắc "chạy lại `scripts.ingest.auto_mapping` rồi duyệt lại"; không nạp phần nào;
- file 0 dòng thì dừng.

**Kiểm từng dòng.** Giá trị chuẩn hóa như hợp đồng lõi: `nullif(trim(x), '')`. Mỗi lý do là một hằng số:

| # | Lý do | Dòng bị cách ly |
|---|---|---|
| R1 | `order_id` rỗng hoặc không ép được `integer` | dòng đó |
| R2 | `order_id` trùng trong file | **mọi** dòng mang `order_id` đó (không chọn bản nào) |
| R3 | `order_id` không có trong `orders` lõi | dòng đó (dòng con mồ côi; không bao giờ đụng dòng lõi, §6.2) |
| R4 | cột `doi_chieu_loi` khác giá trị của `orders` lõi cùng `order_id` (so sau chuẩn hóa, NULL bằng NULL) | dòng đó |
| R5 | cột `nap` rỗng mà không được rỗng, hoặc không ép được kiểu | dòng đó |
| R6 | `sales_employee_id` có thuộc tính mâu thuẫn (cùng id, khác giá trị ở ít nhất một thuộc tính, NULL tính là một giá trị) | **mọi** dòng của id đó (cách ly dây chuyền, §6.2) |

- R6 chỉ xét các dòng đã qua R1–R5, để một ô `years_experience` hỏng không kéo cả nhân viên vào cách ly.
- Một dòng có thể dính nhiều lý do: bằng chứng ghi mọi lý do, nhưng **ngưỡng đếm số dòng phân biệt**.
- **Ngưỡng:** `so_dong_cach_ly / so_dong_file > nguong_cach_ly` thì dừng. Đúng bằng ngưỡng thì **vẫn chạy tiếp**
  (PM chốt 2026-10-28, §10 câu 1 phiếu này).

**Đầu ra khi qua ngưỡng** (ghi vào thư mục snapshot tạm trước khi `os.rename`, như các nguồn lõi):
- `<ten>.parquet`: chỉ các cột `khoa_noi` + `nap`, toàn chuỗi như nguồn lõi (ô rỗng thành NULL như `prepare`), thêm:
  - `_src_row`: đánh **liền 1..N trên các dòng được nhận**, theo thứ tự dòng gốc trong file;
  - `_dong_goc`: số dòng gốc trong file (dòng dữ liệu đầu tiên là 1), để truy ngược.
  Không có cột `bo` và `doi_chieu_loi`.
- `cach_ly/<ten>.csv` trong snapshot: `_dong_goc, ly_do, cot` và giá trị gốc của cả dòng, mỗi lý do tối đa `SAMPLE`
  dòng như `contract.py` (có thể 0 dòng dữ liệu).
- Mục manifest (§4.4).

**Khi vượt ngưỡng:** không tạo snapshot; trả bằng chứng để CLI ghi vào `<run>/quarantine/` qua
`contract.write_quarantine` (cùng đường lỗi hiện có, mã thoát 2), thông báo nêu tên nguồn, số dòng cách ly / số dòng file
và ngưỡng.

### 4.3 `snapshot.py`

- `prepare(data, landing, contract=None, extensions=())`: `extensions` là danh sách tên nguồn mở rộng.
  - Nguồn lõi dựng như hiện nay, rồi mới dựng nguồn mở rộng (cần `orders` lõi cho R3, R4).
  - **`extensions` rỗng: kết quả từng byte như hiện nay**, kể cả `snapshot_id` và `manifest.json`.
  - Có nguồn mở rộng: chuỗi định danh = chuỗi cũ + với mỗi nguồn mở rộng theo tên tăng dần
    `ext:<ten>:<csv_sha256>:<hop_dong_sha256>;`. Đổi file **hoặc** đổi hợp đồng đều ra `snapshot_id` mới, nên snapshot
    cũ dựng theo hợp đồng cũ không bị dùng lại.
- `validate(path, contract=None)`:
  - mục **không** có `mo_rong` phải đúng bằng tập `SOURCES` và kiểm như hiện nay;
  - mục có `mo_rong`: đọc lại hợp đồng mở rộng hiện có trong repo, `hop_dong_sha256` phải khớp; header parquet đúng bằng
    cột nạp + `_src_row, _dong_goc`; `_src_row` liền 1..`rows`; `_dong_goc` tăng ngặt, trong `1..so_dong_file`;
    `rows + so_dong_cach_ly == so_dong_file`; `parquet_sha256` khớp; tệp `cach_ly/<ten>.csv` có và khớp hash ghi trong manifest;
  - tính lại `snapshot_id` theo đúng công thức trên.

### 4.4 Mục manifest của nguồn mở rộng

Phải có **mọi khóa mà `runtime.ingest` đọc**: `header` (cột nạp, không gồm `_src_row`/`_dong_goc`), `rows` (= số dòng
**được nhận**), `csv_sha256`, `csv_md5`, `parquet_sha256`. `runtime.ingest` kiểm `count, count distinct _src_row, min, max`
bằng `(rows, rows, 1, rows)`; cách đánh `_src_row` ở 4.2 thỏa điều này mà **không sửa `runtime.py`**.

Thêm: `mo_rong: true`, `file`, `hop_dong_sha256`, `so_dong_file`, `so_dong_cach_ly`, `cach_ly` (`{lý do: số dòng}`),
`cach_ly_sha256`.

### 4.5 `cli.py`

- Thêm `--extension TEN` (lặp được) cho `prepare` và `run`. Lưu vào `context.json` dạng danh sách tên tăng dần, kèm
  `so_dong_cach_ly` từng nguồn mở rộng.
- `run_id` đã có `context.json` mà tập `--extension` khác tập đã lưu: **dừng**, giống khi đổi `--target`
  (hiện nay hàm trả context cũ im lặng; với phần mở rộng thì phải báo).
- `--snapshot-id`: tập nguồn mở rộng trong manifest phải đúng bằng tập `--extension`, không thì dừng.
- Lỗi vượt ngưỡng đi đúng đường lỗi hợp đồng hiện có (ghi quarantine của run, mã thoát 2, Airflow không retry).
- `history` in thêm số dòng cách ly của nguồn mở rộng nếu có.
- Không `--extension`: hành vi, `context.json` và lịch sử **giống hiện nay** (không thêm khóa rỗng nào làm lệch test cũ).

## 5. Định dạng `scripts/ingest/extensions/orders_enriched.yml`

Khung tối thiểu; GPT được thêm trường mô tả nhưng không thêm quyết định:

```yaml
phien_ban: 1
ten: orders_enriched
file: student_data/orders_enriched.csv
trang_thai: da_duyet
duyet_boi: PM (myuyen0304)
ngay_duyet: '2026-10-28'
nguong_cach_ly: 0.01
khoa_noi: {cot: order_id, nguon: orders, cot_nguon: order_id}
header: [order_id, order_date, customer_id, zip, city, region, district, order_status, payment_method, device_type,
         order_source, sales_employee_id, sales_employee_name, marital_status, education_level, years_experience, comment]
cot:
  - {ten: order_id, xu_ly: khoa_noi, kieu: integer, duoc_rong: false, trang_thai: da_duyet}
  - {ten: order_date, xu_ly: doi_chieu_loi, trang_thai: da_duyet}
  # ... customer_id, zip, order_status, payment_method, device_type, order_source: doi_chieu_loi
  - {ten: city, xu_ly: bo, ly_do: 'thừa, suy từ geography qua zip', trang_thai: da_duyet}
  # ... region, district: bo
  - {ten: sales_employee_id, xu_ly: nap, kieu: string, duoc_rong: false, hien_thi: mart, trang_thai: da_duyet}
  - {ten: sales_employee_name, xu_ly: nap, kieu: string, duoc_rong: false, hien_thi: mart, trang_thai: da_duyet}
  - {ten: marital_status, xu_ly: nap, kieu: string, duoc_rong: false, hien_thi: silver, trang_thai: da_duyet}
  - {ten: education_level, xu_ly: nap, kieu: string, duoc_rong: false, hien_thi: silver, trang_thai: da_duyet}
  - {ten: years_experience, xu_ly: nap, kieu: integer, duoc_rong: false, hien_thi: mart, trang_thai: da_duyet}
  - {ten: comment, xu_ly: nap, kieu: string, duoc_rong: true, hien_thi: silver, trang_thai: da_duyet}
thuc_the:
  - ten: sales_employee
    khoa: sales_employee_id
    thuoc_tinh: [sales_employee_name, marital_status, education_level, years_experience]
    trang_thai: da_duyet
```

Kiểu của cột `doi_chieu_loi` lấy từ `COLUMNS['orders']`, không ghi lại trong file này.

## 6. Test bắt buộc

Theo mẫu test lát 1 (`ROOT` từ `__file__`, `sys.path.insert`, `tmp_path`). Test đơn vị dùng fixture nhỏ: một thư mục
`data` giả gồm 14 CSV lõi rất nhỏ (có thể truyền `contract=` nhỏ như test cũ của `snapshot`) và một file mở rộng.
Hợp đồng mở rộng của test viết vào `tmp_path`; loader phải nhận được thư mục hợp đồng làm tham số để test không đụng
`scripts/ingest/extensions/`.

### 6.1 Test đơn vị (không cần `data/`, dưới 15 giây)

| Ca | Tình huống | Kỳ vọng |
|---|---|---|
| E1 | Hợp đồng có một cột `trang_thai: de_xuat`; thiếu `ngay_duyet`; `xu_ly` lạ; `ten: orders`; `khoa_noi` tới nguồn lạ; cột header không có mục; `nguong_cach_ly: 1.5` | mỗi ca dừng, thông báo nêu mục sai |
| E2 | File thêm một cột / thiếu một cột / đảo thứ tự hai cột so với `header` | dừng, nhắc chạy lại auto mapping; không tạo snapshot |
| E3 | File sạch | `so_dong_cach_ly` 0; parquet đúng cột nạp + `_src_row`, `_dong_goc`; không có cột `bo`, `doi_chieu_loi` |
| E4 | Mỗi lý do R1–R6 một ca (R2: hai dòng cùng `order_id`; R6: một id có hai `years_experience`) | đúng lý do; R2, R6 cách ly **mọi** dòng liên quan; `_src_row` của phần nhận vẫn liền 1..N, `_dong_goc` đúng dòng gốc |
| E5 | Dòng có `years_experience = 'abc'` của một id mà các dòng khác của id đó nhất quán | chỉ dòng đó bị cách ly (R5), id không bị R6 |
| E6 | Dòng dính hai lý do | bằng chứng ghi hai lý do; ngưỡng đếm một dòng |
| E7 | Ngưỡng: dưới, đúng bằng, trên `nguong_cach_ly` | dưới: chạy; trên: dừng, không có snapshot, quarantine của run có bằng chứng; đúng bằng: **chạy** (PM chốt) |
| E8 | `snapshot_id`: không phần mở rộng (so với cách tính cũ trên cùng fixture); bật phần mở rộng; cùng file nhưng đổi hợp đồng; hợp đồng CRLF so với LF | không phần mở rộng: **giống hệt** id cũ; bật: khác; đổi hợp đồng: khác; CRLF/LF: **giống** |
| E9 | `validate`: snapshot có phần mở rộng hợp lệ; sửa một byte parquet; sửa hợp đồng sau khi prepare; xóa `cach_ly/<ten>.csv` | hợp lệ qua; ba ca sau dừng |
| E10 | Mục manifest của nguồn mở rộng | có đủ `header, rows, csv_sha256, csv_md5, parquet_sha256`; thống kê `_src_row` đúng bằng `(rows, rows, 1, rows)` (điều kiện của `runtime.ingest`) |
| E11 | CLI: cùng `run_id` mà đổi tập `--extension`; `--snapshot-id` với tập `--extension` lệch manifest; không `--extension` | hai ca đầu dừng; ca thứ ba `context.json` không có khóa mới |
| E12 | Nguồn lõi có một dòng sai kiểu khi bật phần mở rộng | vẫn dừng như hiện nay (ngưỡng 0 của 14 nguồn không đổi) |

**Mỗi test chính phải trượt khi bỏ phần code tương ứng.** Báo cáo ghi đã thử vô hiệu phần nào (vd. bỏ kiểm
`trang_thai`, bỏ cách ly dây chuyền R2/R6, đổi `>` thành `>=` ở ngưỡng, bỏ hợp đồng khỏi chuỗi định danh, bỏ chuẩn hóa
CRLF) và test nào trượt.

### 6.2 Hồi quy

| Bộ | Mốc (Claude chạy 2026-10-28) |
|---|---|
| `scripts/pipeline/tests` (test cũ, không sửa) | 54 đạt, 2 skip |
| `scripts/ingest/tests` (60 test của lát 1) | 60 đạt |
| `pytest scripts` | 146 đạt + số test mới, 3 skip |

### 6.3 Chạy trên dữ liệu thật (lệnh PM tự chạy, không đưa vào pytest vì đọc cả 14 CSV)

```powershell
cd D:\retail-analytics-schema
$py = 'D:/retail-analytics/.venv/Scripts/python.exe'
& $py -m scripts.pipeline.cli prepare --run-id lat2-tat --root warehouse/pipeline/lat2
& $py -m scripts.pipeline.cli prepare --run-id lat2-bat --root warehouse/pipeline/lat2 --extension orders_enriched
```

Kỳ vọng:
- `lat2-tat`: `snapshot_id` **`5bd9a84aaf73`**, đúng mốc `review-20261027` (tiêu chí nghiệm thu 4);
- `lat2-bat`: `snapshot_id` khác; `orders_enriched`: `so_dong_file` 646.945, `rows` 646.945, `so_dong_cach_ly` 0;
  200 `sales_employee_id` phân biệt trong parquet.

GPT chạy được thì ghi kết quả vào báo cáo; máy thiếu RAM thì ghi "chưa chạy", PM chạy.

## 7. Lệnh chạy

```powershell
cd D:\retail-analytics-schema
D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest scripts/ingest/tests -q -p no:cacheprovider
D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest scripts/pipeline/tests -q -p no:cacheprovider
D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest scripts -q -p no:cacheprovider
```

## 8. Báo cáo của GPT khi xong (PM dán cho Claude rà)

- Danh sách file đã tạo/sửa; với `snapshot.py` và `cli.py`, tóm tắt từng chỗ đổi.
- Số đạt/trượt/skip của ba lệnh ở §7.
- Kết quả thử vô hiệu code (§6.1): phần nào, test nào trượt.
- Kết quả §6.3 (hai `snapshot_id`, các số của `orders_enriched`) hoặc "chưa chạy".
- Nội dung `scripts/ingest/extensions/orders_enriched.yml`.
- Giới hạn còn lại, chỗ làm khác phiếu (nếu có) và vì sao.

## 9. Rà của Claude (Claude ghi, GPT đọc để sửa)

| Lượt | Ngày | Kết quả | Phát hiện (mức nặng) | GPT đã sửa |
|---|---|---|---|---|
| 1 | 2026-10-28 | **Chưa đạt, sửa nhẹ**; phần lõi đúng, dữ liệu thật đạt | B1, B3 sửa theo phiếu; B2 thêm test; B4–B7 ghi nhận | B1–B4 (lượt 2) |
| 2 | 2026-10-28 | **Đạt**, B1–B4 đã sửa đúng | không có lỗi mới; 1 ghi nhận (C18) | |

### Lượt 1 (2026-10-28)

**Claude đã kiểm và đạt:**
- Ba lệnh §7 chạy lại: `scripts/ingest/tests` 100 đạt; `scripts/pipeline/tests` 61 đạt, 2 skip; `pytest scripts` 193 đạt,
  3 skip (= 146 + 47 test mới), khớp báo cáo GPT.
- 7 file `.py` tạo/sửa không có BOM. `scripts/ingest/extensions/orders_enriched.yml` trên đĩa khớp §3/§5 từng dòng.
- Snapshot thật GPT đã dựng (`warehouse/pipeline/lat2/`), Claude đọc lại độc lập:
  - `manifest.json` của `5bd9a84aaf73` (lượt `lat2-tat`) **trùng từng byte** với mốc `review-20261027`;
  - trong `47e7cbe765d9`, 14 mục nguồn lõi giống hệt mục của `5bd9a84aaf73`;
  - `orders_enriched`: `so_dong_file` = `rows` = 646.945, `so_dong_cach_ly` 0, 200 `sales_employee_id`;
    parquet toàn chuỗi, đúng 7 cột nạp + `_src_row`, `_dong_goc`;
  - so từng dòng parquet với dòng `_dong_goc` của CSV gốc: **0/646.945 dòng lệch**;
  - `snapshot.validate` qua; `context.json` có `extensions`, `so_dong_cach_ly`; `history` in số cách ly.
- `runtime.ingest` (`runtime.py:38–60`) tạo bảng raw bằng `select *` rồi chỉ kiểm thống kê `_src_row`, không so header:
  cột `_dong_goc` thành một cột thêm của raw, không cần sửa `runtime.py`. Thư mục `cach_ly/` không được upload (chỉ
  `<ten>.parquet`).
- Thử vô hiệu: 20 phép của GPT đều bị bắt. Claude thử thêm 17 phép trên bản sao ở scratchpad: 4 bị bắt (bỏ
  `rows + so_dong_cach_ly == so_dong_file` trong `validate`, bỏ ép kiểu R5, R3 so chuỗi thay vì kiểu, bỏ
  `so_dong_cach_ly` khỏi context), 13 lọt (xem B2–B4).

**Phát hiện:**

| # | Mức | Chỗ | Vấn đề | Việc cho GPT |
|---|---|---|---|---|
| B1 | nhẹ, lệch phiếu | `extension_prepare.py`, dòng thêm R2 | `count(*) over (partition by typed_key) > 1` gom mọi khóa NULL vào một nhóm: từ hai dòng `order_id` rỗng/không ép được trở lên thì các dòng đó bị ghi **cả R1 lẫn R2** dù không trùng khóa (Claude thử trên DuckDB: `'abc'` và `''` đều ra R2). Ngưỡng không sai vì đếm dòng phân biệt, nhưng `cach_ly[R2]` trong manifest và bằng chứng BA đọc bị thổi lên | Thêm điều kiện `typed_key is not null` cho R2. Test: hai dòng khóa hỏng → `cach_ly == {R1: 2}`, không có R2 |
| B2 | nhẹ, thiếu test | R4 | Code đúng (`is distinct from`), nhưng đổi thành `<>` vẫn qua 47 test: chưa có ca một bên NULL, một bên có giá trị (chỉ có ca NULL–NULL) | Thêm ca: file để trống `order_status` khi `orders` lõi có giá trị → R4 |
| B3 | nhẹ, lệch phiếu | `extension_prepare.py`, `copy ... from normalized` | Parquet ghi giá trị **đã trim**; §4.2 yêu cầu "toàn chuỗi như nguồn lõi (ô rỗng thành NULL như `prepare`)", còn lõi không trim. Dữ liệu thật có 0 ô có khoảng trắng đầu/cuối nên `47e7cbe765d9` không đổi. Đổi nguồn sang `original` vẫn qua 47 test | Ghi giá trị gốc như lõi (chỉ ô rỗng thành NULL); chuẩn hóa để staging lát 3. Thêm test ghim: ô `' EMP1 '` qua kiểm nhưng parquet giữ nguyên `' EMP1 '` |
| B4 | ghi nhận | `extension_contract.py`, `extension_prepare.validate`, `snapshot.prepare`, `cli.main` | Chốt GPT thêm ngoài §4 chưa có test (thử bỏ từng chốt vẫn qua): ngưỡng và `file` trong `validate`; nguồn đổi trong lúc đọc/prepare; chặn `..` trong `file`; kiểu khóa nối; header trùng; cấm cột `_`; thực thể chỉ nhận cột `nap`; `--extension` ngoài `prepare/run` | Với mỗi chốt giữ lại: thêm một test, hoặc bỏ chốt. Ít nhất: ngưỡng trong `validate`, `..`, kiểu khóa nối, `--extension` sai stage |
| B5 | ghi nhận, PM quyết | `scripts/ingest/verify_extension_mutations.py` | Công cụ thử vô hiệu nằm trong gói `scripts/ingest/`, nên được tính vào `code_version` và vào image; ghi ra `warehouse/schema_review/` | **PM chốt 2026-10-28: không commit.** File để nguyên trên đĩa (untracked); bằng chứng giữ ở `lat2_mutations.json` |
| B6 | ghi nhận | `cli.print_history`; quarantine của run | `history` in một dòng "cách ly" cho **mỗi dòng lịch sử**: lệnh `run --extension` có 5 stage thì in 5 dòng trùng. CSV quarantine của run có cột `_src_row` trùng `_dong_goc` | Tùy chọn: in theo `run_id` phân biệt; bỏ cột trùng |
| B7 | ghi nhận | `original` trong `extension_prepare.prepare` | `_dong_goc` lấy từ `row_number() over ()`, dựa vào thứ tự chèn của DuckDB, không có `order by` tường minh. Trên dữ liệu thật đúng 0 lệch; fixture 200 dòng không bắt được lỗi thứ tự | Không chặn. Có thể làm chắc thêm sau |

**Kết luận lượt 1:** sửa B1, B3; thêm test B1, B2, B3 và các test chọn ở B4; chạy lại ba lệnh §7 và hai lệnh §6.3 (kỳ vọng
`5bd9a84aaf73` và `47e7cbe765d9` không đổi, vì dữ liệu thật không có ô khoảng trắng và không có khóa hỏng). Không cần
sửa `runtime.py`, hợp đồng, hay phần nối CLI.

### Lượt 2 (2026-10-28)

GPT sửa `extension_prepare.py` (B1: R2 thêm `typed_key is not null`; B3: parquet ghi từ `original`, chỉ `nullif(x, '')`,
kiểm R1–R6 vẫn trên giá trị chuẩn hóa) và tạo `scripts/ingest/tests/test_extensions_review.py` (14 test cho B1–B4).
Không đổi `snapshot.py`, `cli.py`, YAML, test cũ, `runtime.py`; B5 để nguyên (untracked); B6 tùy chọn, chưa làm.

**Claude kiểm:**
- Hai file sửa/tạo không BOM. Ba lệnh §7: 114 đạt; 61 đạt, 2 skip; 207 đạt, 3 skip (khớp báo cáo).
- Thử vô hiệu trên bản sao, 18 phép (17 phép lượt 1, với C13/C14 đảo lại thành bỏ bản sửa B1/B3, cộng C18):
  **17 bị bắt**, gồm cả 8 chốt ở B4. Lọt 1: **C18** bỏ `nullif(x, '')` khi ghi parquet. Ghi nhận, không chặn: adapter
  đọc CSV đã đưa ô rỗng về NULL nên `nullif` hiện là phòng hờ thừa (khác `prepare` lõi đọc bằng `csv` của Python).
- Báo cáo GPT ghi §6.3 chạy lại trên context/snapshot có sẵn, tức là chưa dựng lại parquet bằng code mới. Claude dựng lại từ
  đầu vào thư mục mới (`prepare --run-id l2-bat --root warehouse/pipeline/lat2-luot2-claude --extension orders_enriched`):
  vẫn ra `47e7cbe765d9`; `manifest.json`, `orders_enriched.parquet`, `cach_ly/orders_enriched.csv`, `orders.parquet`
  **trùng từng byte** với lượt 1. Đường tắt phần mở rộng không đổi code ở lượt này (mốc `5bd9a84aaf73` lượt 1 vẫn giữ).

**Kết luận lượt 2: Đạt.** Commit theo từng file, trừ `verify_extension_mutations.py` (PM chốt không commit, B5).

## 10. Câu hỏi PM chốt trước khi giao

| # | Câu hỏi | Đề xuất của Claude | PM chốt |
|---|---|---|---|
| 1 | Số dòng cách ly **đúng bằng** 1% thì sao? (§6.2 của tien_hoa_schema chỉ nói "dưới" và "vượt") | Vẫn chạy tiếp; chỉ dừng khi **vượt** 1% | **2026-10-28: theo đề xuất.** Đúng bằng ngưỡng vẫn chạy; dừng khi `so_dong_cach_ly / so_dong_file > nguong_cach_ly` |
| 2 | Duyệt nội dung hợp đồng mở rộng ở §3 (cột nạp, cột bỏ, cột đối chiếu, kiểu, `hien_thi`) | Duyệt như §3 | **2026-10-28: duyệt.** `ngay_duyet: '2026-10-28'` |
