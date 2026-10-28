# Giao việc: auto mapping, lát 1 (đề xuất ánh xạ cho `orders_enriched`)

Soạn ngày 2026-10-27. PM giao, Claude soạn phiếu. GPT code; Claude rà độc lập trước khi commit, theo 5 bước rà ở đầu
[giao_viec_theo_so_do.md](giao_viec_theo_so_do.md). Chưa đạt thì Claude ghi phát hiện vào §9, GPT sửa tiếp. PM đọc báo cáo
rà rồi mới cho commit.

Thiết kế gốc: [tien_hoa_schema.md](tien_hoa_schema.md), đọc trước **§4, §5, §5b, §9 bước 3**. Bằng chứng số liệu:
`notebooks/02_design/schema_evolution.ipynb` (phần 1–2 cho `orders_enriched`). Đọc thêm `AGENTS.md`, `CLAUDE.md`.

## 1. Lát 1 làm gì, không làm gì

**Làm:** máy đọc một file dữ liệu mới, so với hợp đồng 14 nguồn hiện có, rồi **sinh đề xuất ánh xạ** cho BA duyệt:
`mapping_de_xuat.yml` và `bao_cao_mapping.md`. File đích nghiệm thu là `data/student_data/orders_enriched.csv`.

Ba module mới và test:

| File | Việc |
|---|---|
| `scripts/ingest/adapters.py` | Đọc CSV (bỏ BOM) và JSON (mảng đối tượng) thành bảng **toàn chuỗi**, kèm siêu dữ liệu file |
| `scripts/ingest/schema_diff.py` | So tên cột của file với hợp đồng một nguồn: khớp, thêm, thiếu, đổi thứ tự; xếp loại `khop` / `additive` / `breaking` |
| `scripts/ingest/auto_mapping.py` | Chọn nguồn logic cho file, phân loại từng cột thêm, ghi hai file đề xuất. Có CLI |
| `scripts/ingest/tests/test_*.py` | Test đơn vị trên fixture nhỏ + test tích hợp trên dữ liệu thật (tự skip nếu thiếu `data/`) |

**Không làm ở lát này** (để lát sau, sau khi BA duyệt đề xuất):
- không nạp gì: không có hợp đồng mở rộng, không đọc `trang_thai: da_duyet`;
- không sửa `scripts/pipeline/contract.py`, `scripts/pipeline/snapshot.py`, `scripts/pipeline/cli.py`,
  `scripts/ingest/source_contract.py`, `scripts/ingest/ingest_raw.py`, dbt (`retail_dbt/`), Airflow;
- không ngưỡng cách ly, không luật miền, không luật sửa tầng 2 (§6.1);
- không xử lý khóa master data (epd), phát lại (tf), `promotions_ext` (eprom);
- không sửa notebook (`schema_evolution.ipynb` do PM giữ, một notebook một chủ).

Chỉ **đọc** `SOURCES`, `COLUMNS`, `KEYS` từ `scripts/ingest/source_contract.py`; không đổi file đó.

## 2. Môi trường và ràng buộc

- Làm trong worktree `D:/retail-analytics-schema`, nhánh `schema/myuyen`. Không đụng `D:/retail-analytics` (nhánh khác,
  có file sửa dở của việc khác).
- Python: `D:/retail-analytics/.venv/Scripts/python.exe` (worktree không có `.venv`). Chạy từ root worktree.
- Thư viện: chỉ dùng thứ đã có trong venv: `duckdb` (1.5.5), `pyyaml`, thư viện chuẩn (`difflib`, `json`, `hashlib`,
  `re`). **Không cài thêm gói.**
- Dữ liệu thật lớn (`orders_enriched` 646.945 dòng × 17 cột). Đọc và tính bằng DuckDB SQL, không lặp từng dòng bằng
  Python, không nạp cả bảng vào pandas.
- Dữ liệu trong `data/student_data/` là dữ liệu ngoài, không tin cậy: chỉ đọc bằng `json` / DuckDB; không `eval`, không
  `pickle`, không chạy gì nằm trong thư mục đó.
- Đầu ra mặc định ghi vào `warehouse/schema_review/<stem file>_<UTC yyyymmddThhmmssZ>/` (`warehouse/` đã gitignore).
  Thư mục đích đã có file thì **dừng, không ghi đè** (BA có thể đang sửa file đề xuất cũ).
- Không commit, không push, không sửa `data/`. Comment và docstring tiếng Việt, định danh tiếng Anh, theo giọng code
  trong `scripts/pipeline/contract.py`.

## 3. Sự thật đã kiểm về `orders_enriched.csv` (kỳ vọng của test tích hợp)

Claude đo lại ngày 2026-10-27 bằng DuckDB `read_csv(all_varchar=true)`, script tạm. Số khớp notebook phần 2, trừ hai
chỗ đánh dấu † (chưa có cell trong notebook; PM thêm cell nếu đưa vào tài liệu thiết kế).

| Mục | Giá trị |
|---|---|
| Byte đầu | `EF BB BF` (BOM UTF-8) |
| Số dòng / số cột | 646.945 / 17 |
| Header (thứ tự trong file) | `order_id, order_date, customer_id, zip, city, region, district, order_status, payment_method, device_type, order_source, sales_employee_id, sales_employee_name, marital_status, education_level, years_experience, comment` |
| Cột khớp hợp đồng `orders` | 8/8: `order_id, order_date, customer_id, zip, order_status, payment_method, device_type, order_source`; **giữ thứ tự tương đối** của hợp đồng, chỉ có 3 cột thêm chen giữa (`doi_thu_tu` = sai) |
| Cột thêm | 9: `city, region, district, sales_employee_id, sales_employee_name, marital_status, education_level, years_experience, comment` |
| `city, region, district` | Khớp `geography` qua `zip` ở **646.945/646.945** dòng (cả ba cột cùng lúc). Riêng `city` còn khớp `customers.city` qua `customer_id` ở 646.945/646.945 dòng † |
| `sales_employee_id` | 200 giá trị phân biệt, 0 dòng rỗng |
| Phụ thuộc hàm vào `sales_employee_id` | `sales_employee_name` (192 giá trị †), `marital_status` (2), `education_level` (4), `years_experience` (20): **0 id vi phạm** |
| `comment` | 18 giá trị phân biệt, 0 rỗng; **cả 200 id vi phạm** phụ thuộc hàm (không thuộc thực thể nhân viên) |
| `order_id` | 646.945 giá trị phân biệt (không trùng) |
| `zip` | 29.932 giá trị phân biệt (trùng nhiều) |

Chú ý: 192 tên cho 200 id, nên **tên không phải khóa**; thực thể phải neo vào `sales_employee_id`.

## 4. Yêu cầu từng module

GPT được tự chọn cách cài đặt, miễn đạt hành vi và test ở §6. Các ngưỡng phải là **hằng số có tên**, kèm comment lý do.

### 4.1 `adapters.py`

- Một hàm đọc file theo đuôi (`.csv`, `.json`); đuôi khác thì báo lỗi rõ.
- Trả về: tên file, đường dẫn, `format`, `encoding` (`utf-8` hoặc `utf-8-sig`), `has_bom`, `sha256` của file gốc,
  `n_rows`, `columns` (tên cột theo thứ tự file, **đã bỏ BOM**), và một cách truy vấn dữ liệu bằng DuckDB (view hoặc
  relation) với **mọi cột kiểu chuỗi** (VARCHAR).
- CSV:
  - phát hiện BOM bằng byte đầu, không dựa vào việc DuckDB tự bỏ BOM;
  - file không giải mã được UTF-8 thì **dừng, báo lỗi rõ** (tên file, vị trí byte nếu có); không đoán encoding khác;
  - giữ nguyên giá trị, **không trim** (chuẩn hóa là việc của hợp đồng). Ô rỗng: DuckDB `read_csv` mặc định đọc `''`
    thành NULL, kể cả `""` có ngoặc (Claude thử 2026-10-27, duckdb 1.5.5); chấp nhận hành vi này, vì hợp đồng dùng
    `nullif(trim(x), '')` nên `''` và NULL là một.
- JSON:
  - chỉ nhận mảng đối tượng ở cấp ngoài cùng; dạng khác thì dừng, báo lỗi;
  - header = hợp các khóa theo thứ tự xuất hiện đầu tiên; khóa thiếu ở một bản ghi thành null;
  - giá trị: `None` → null, chuỗi giữ nguyên (kể cả khoảng trắng), số và bool → chuỗi, đối tượng/mảng lồng → chuỗi JSON.

### 4.2 `schema_diff.py`

- Đầu vào: danh sách tên cột của file và danh sách cột hợp đồng của một nguồn.
- Chuẩn hóa tên trước khi so: bỏ BOM, trim, chữ thường. Ghi cả tên gốc trong file.
- Đầu ra: `matched`, `added`, `missing`, `order_changed`, và `kind`:
  - `order_changed`: **thứ tự tương đối của các cột khớp** khác thứ tự trong hợp đồng. Cột thêm chen giữa mà cột khớp
    vẫn đúng thứ tự thì **không** tính là đổi thứ tự;
  - `khop`: cùng tập cột, cùng thứ tự;
  - `additive`: không thiếu cột nào, và có cột thêm hoặc `order_changed`;
  - `breaking`: thiếu ít nhất một cột hợp đồng.
- Cột hợp đồng bị thiếu: đề xuất **ứng viên đổi tên** từ các cột thêm, dựa trên độ giống tên và kiểu suy được khớp kiểu
  hợp đồng. Chỉ là ứng viên kèm điểm, không tự coi là khớp; `kind` vẫn là `breaking`.

### 4.3 `auto_mapping.py`

**(a) Chọn nguồn logic cho file.** Chấm điểm file với từng nguồn trong `SOURCES`, ghi điểm của **mọi** nguồn có cột
trùng, đề xuất nguồn đứng đầu nếu đạt ngưỡng và cách nguồn thứ hai đủ xa, không thì `chua_ro`.

Bẫy phải tránh: `geography` có **100% cột hợp đồng** (`zip, city, region, district`) nằm trong `orders_enriched`, bằng
`orders`. Chỉ đếm "tỷ lệ cột hợp đồng có mặt" sẽ hòa. Gợi ý thêm tín hiệu: tỷ lệ cột của file thuộc hợp đồng, khóa chính
của nguồn (`KEYS`) có mặt và **không trùng** trong file (`order_id` không trùng, `zip` trùng nhiều), độ giống tên file.
Test §6 kiểm trên cả 15 file của zip để chống khớp riêng một file.

**(b) Cột khớp.** Với từng cột khớp hợp đồng: kiểu hợp đồng (`COLUMNS`) và số giá trị khác rỗng **không ép được** sang
kiểu đó (`try_cast(nullif(trim(x), '') as <kiểu>)`, cùng cách `contract.py`). Chỉ báo, không chặn.

**(c) Phân loại cột thêm.** Mỗi cột thêm nhận đúng một `loai`, xét theo thứ tự:

1. `thua`: giá trị suy được từ một nguồn đã có qua khóa nối. Điều kiện: có nguồn `S` mà khóa chính một cột `k` của `S`
   (`KEYS`) có mặt trong file, `S` có cột cùng tên chuẩn hóa, và tỷ lệ dòng khớp sau khi nối ≥ ngưỡng (gợi ý 99,9%; ghi
   rõ số khớp/tổng). Ghi **mọi** đường suy được, không chỉ đường đầu. Đề xuất: `bo` (3NF: phụ thuộc bắc cầu).
   Bảng tham chiếu đọc từ `--data` (mặc định `data/`, 14 CSV Datathon) qua chính `adapters.py`.
2. `thuc_the_moi`: nhóm cột phụ thuộc hàm vào một cột id mới. Cột id: tên kết thúc `_id`, không thuộc hợp đồng nguồn đã
   chọn. Thuộc tính: cột thêm còn lại (chưa là `thua`) có 0 id vi phạm phụ thuộc hàm. Ghi số id phân biệt, số id rỗng,
   số vi phạm của từng cột. Cột có vi phạm thì **không** vào nhóm.
3. `thuoc_tinh_le`: cột thêm còn lại. Ghi số giá trị phân biệt, tỷ lệ rỗng, tối đa 5 giá trị mẫu.

**(d) Gắn cờ nghi PII** (cờ phụ, độc lập với `loai`), **chỉ xét cột thêm**; cột hợp đồng đã có quyết định từ trước.
- Theo tên: tách tên cột theo `_` thành từ, so **nguyên từ** (không so chuỗi con) với danh sách `name`, `phone`,
  `email`, `address`, `birth`, `age`, `gender`, `ten`, `sdt` (nhóm **định danh**), và `marital`, `education` (nhóm
  **thuộc tính cá nhân nhạy cảm**, PM chốt 2026-10-28, §10). So chuỗi con sẽ bắt nhầm `average_delivery_time`,
  `page_views` (chứa `age`), `content` (chứa `ten`).
- Theo giá trị: cột mà phần lớn giá trị khác rỗng giống số điện thoại (có dấu `+`, khoảng trắng, `-` hoặc số 0 đầu, độ
  dài 9–12 chữ số). Cột toàn chữ số không có các dấu hiệu đó (id, zip) không bị gắn.
- Ghi lý do gắn cờ, nêu rõ nhóm (định danh / thuộc tính nhạy cảm) và từ khớp. Danh sách mẫu là hằng số.
- Cả hai nhóm dùng chung cờ `nghi_pii` vì cùng một xử lý: bỏ khỏi mart (§10). `years_experience` **không** bị gắn.

**(e) Chi tiết đề xuất cho thực thể mới:** tên đề xuất (bỏ hậu tố `_id`, ví dụ `sales_employee`), ghi chú "BA quyết:
bảng 3NF mới, dim mới hay dừng ở silver" (máy không tự quyết, §5b "Máy không bao giờ tự làm").

**CLI:**

```powershell
D:/retail-analytics/.venv/Scripts/python.exe -m scripts.ingest.auto_mapping data/student_data/orders_enriched.csv
# tùy chọn: --data data  --out <thư mục>
```

In ra đường dẫn hai file kết quả và một dòng tóm tắt (nguồn đề xuất, số cột theo từng `loai`). Mã thoát 0 khi sinh được
đề xuất (kể cả `chua_ro` hay `breaking`, vì đó là nội dung báo cáo); mã khác 0 chỉ khi không đọc được file hoặc đầu ra đã tồn tại.

## 5. Định dạng đầu ra

### 5.1 `mapping_de_xuat.yml`

Mỗi mục BA cần quyết có `trang_thai: de_xuat`. BA sửa thành `da_duyet` hoặc `tu_choi` (lát sau mới đọc). Khung tối thiểu,
GPT được thêm trường bằng chứng:

```yaml
phien_ban: 1
sinh_luc_utc: '2026-10-27T00:00:00Z'
file: {ten: orders_enriched.csv, sha256: '…', dinh_dang: csv, encoding: utf-8-sig, co_bom: true, so_dong: 646945, so_cot: 17}
nguon:
  de_xuat: orders            # hoặc chua_ro
  trang_thai: de_xuat
  diem: [{nguon: orders, diem: 0.0, …}, {nguon: geography, diem: 0.0, …}]
schema_diff: {loai: additive, doi_thu_tu: true, cot_khop: [...], cot_them: [...], cot_thieu: [], ung_vien_doi_ten: []}
cot:
  - {ten_trong_file: order_id, loai: khop, cot_hop_dong: order_id, kieu_hop_dong: integer, khong_ep_duoc: 0}
  - ten_trong_file: city
    loai: thua
    de_xuat: bo
    bang_chung: [{nguon: geography, khoa_noi: zip, khop: 646945, tong: 646945}, {nguon: customers, khoa_noi: customer_id, khop: 646945, tong: 646945}]
    trang_thai: de_xuat
  - {ten_trong_file: sales_employee_name, loai: thuc_the_moi, thuc_the: sales_employee, nghi_pii: true, ly_do_pii: '…', trang_thai: de_xuat}
thuc_the_moi:
  - {ten_de_xuat: sales_employee, khoa: sales_employee_id, thuoc_tinh: [...], so_khoa: 200, khoa_rong: 0, vi_pham: {...}, trang_thai: de_xuat}
```

- Ghi YAML bằng `yaml.safe_dump(..., allow_unicode=True, sort_keys=False)`; đọc lại bằng `yaml.safe_load` phải ra đúng dữ liệu.
- Cột `khop` không cần `trang_thai` (không có gì để quyết), trừ khi `khong_ep_duoc > 0`.
- Không có dấu thời gian hay đường dẫn tuyệt đối nào khác ngoài `sinh_luc_utc`, để hai lần chạy trên cùng file chỉ khác
  đúng một dòng đó (test §6 kiểm).
- Thứ tự phải tất định, vì DuckDB không bảo đảm thứ tự dòng khi không có `ORDER BY`:
  - giá trị mẫu: tần suất giảm dần, rồi theo giá trị;
  - `diem`, `bang_chung`, ứng viên đổi tên: điểm (hoặc số khớp) giảm dần, rồi theo tên;
  - `cot`: theo thứ tự cột trong file;
  - điểm làm tròn 4 chữ số thập phân.

### 5.2 `bao_cao_mapping.md`

Tiếng Việt, cho BA đọc. Thứ tự từ cần quyết nhiều nhất tới ít nhất:
1. Tóm tắt: file, nguồn đề xuất kèm điểm hai nguồn đầu, loại schema-diff, BOM.
2. Ca mơ hồ (`chua_ro`, ứng viên đổi tên, cột thiếu), nếu có.
3. Nghi PII.
4. Thực thể mới.
5. Cột thừa và đường suy ra.
6. Thuộc tính lẻ.
7. Cột khớp (bảng gọn, kèm `khong_ep_duoc`).
8. Cuối báo cáo: "Máy chỉ đề xuất; chưa có gì được nạp. Sửa `trang_thai` trong `mapping_de_xuat.yml`."

Mọi số trong báo cáo lấy từ cùng dữ liệu với file YAML (sinh từ một cấu trúc, không tính hai lần).

## 6. Test bắt buộc

Đặt ở `scripts/ingest/tests/`, tên file riêng: `test_adapters.py`, `test_schema_diff.py`, `test_auto_mapping.py`
(tránh trùng tên `test_contract.py` của pipeline khi chạy `pytest scripts`). Theo mẫu `scripts/pipeline/tests/test_contract.py`:
`ROOT` từ `__file__`, `sys.path.insert`, fixture tạm bằng `tmp_path`.

Lưu ý `KEYS`: `order_items` là `None`, `inventory` là khóa ghép. Chấm điểm nguồn và luật `thua` phải xử lý cả hai mà
không lỗi (luật `thua` chỉ dùng khóa một cột; khóa ghép và `None` thì bỏ qua đường suy đó).

### 6.1 Test đơn vị (fixture nhỏ, không cần `data/`, phải chạy dưới 10 giây)

| Ca | Tình huống | Kỳ vọng |
|---|---|---|
| U1 | CSV có BOM | `has_bom`, `encoding == 'utf-8-sig'`, cột đầu không chứa `\ufeff` |
| U2 | CSV không BOM | `has_bom` sai, `encoding == 'utf-8'` |
| U3 | CSV byte không phải UTF-8 (vd. cp1258) | lỗi rõ, không trả bảng |
| U4 | CSV có `'  a  '`; JSON có `'  a  '`, `''` và `None` | không trim; JSON giữ `''` khác NULL |
| U5 | JSON mảng đối tượng, khóa thiếu ở một bản ghi, có `None`, số, bool, đối tượng lồng | header là hợp khóa theo thứ tự; null đúng chỗ; mọi cột VARCHAR; lồng thành chuỗi JSON |
| U6 | JSON cấp ngoài là đối tượng, hoặc mảng số | lỗi rõ |
| U7 | `schema_diff`: cùng cột cùng thứ tự / thêm cột ở cuối / thêm cột **chen giữa** (cột khớp vẫn đúng thứ tự) / hoán vị hai cột hợp đồng / thiếu cột / tên khác hoa thường và dính BOM | `khop` / `additive` / `additive`, `order_changed` sai / `additive`, `order_changed` đúng / `breaking` / `khop` |
| U8 | Thiếu `order_date`, có cột thêm `orderdate` cùng kiểu ngày | `breaking`, `orderdate` là ứng viên đổi tên đứng đầu |
| U9 | Fixture "đơn mở rộng" (~30 dòng) + bảng tham chiếu nhỏ: cột suy được qua khóa, nhóm id + 2 thuộc tính, một cột vi phạm phụ thuộc hàm, một cột tên người | đúng `thua` / `thuc_the_moi` / `thuoc_tinh_le`; cột vi phạm không vào nhóm; tên người có `nghi_pii` |
| U10 | Như U9 nhưng sửa một giá trị cột suy được để tỷ lệ khớp dưới ngưỡng | cột đó **không** là `thua` |
| U11 | File có cột trùng tên với nguồn tham chiếu nhưng **không** có khóa nối của nguồn đó | không là `thua` |
| U12 | File chỉ gồm cột của `geography`, khóa không trùng | nguồn đề xuất `geography` |
| U13 | File toàn cột lạ | `chua_ro` |
| U14 | CLI chạy hai lần vào cùng thư mục | lần hai dừng, mã khác 0, file lần một giữ nguyên |
| U15 | Chạy hai lần vào hai thư mục | hai YAML chỉ khác dòng `sinh_luc_utc` |

**Mỗi test chính phải trượt khi bỏ phần code tương ứng.** Trong báo cáo, GPT ghi đã thử vô hiệu tạm phần nào (vd. bỏ bước
bỏ BOM, bỏ kiểm khóa không trùng, bỏ kiểm vi phạm phụ thuộc hàm) và test nào trượt.

### 6.2 Test tích hợp (dữ liệu thật; `pytest.skip` nếu thiếu `data/student_data/`)

| Ca | Kỳ vọng |
|---|---|
| I1 | `orders_enriched.csv`: mọi số ở §3 (nguồn `orders`, `additive`, `doi_thu_tu` sai, BOM, 8 khớp với `khong_ep_duoc` = 0, 9 thêm; `city, region, district` là `thua` có đường `geography` qua `zip` 646.945/646.945; thực thể `sales_employee` đúng 4 thuộc tính, 200 khóa, 0 rỗng; `comment` là `thuoc_tinh_le`; tập cột `nghi_pii` **đúng bằng** `{sales_employee_name, marital_status, education_level}`; ba cột này vẫn nằm trong thực thể `sales_employee`, cờ chỉ là cờ phụ) |
| I2 | Chọn nguồn cho cả 15 file của zip: 10 CSV trùng byte → đúng nguồn cùng tên; `orders_enriched` → `orders`; `shipments_realistic` → `shipments`; `epd.json` → `products`; `tf.json` → `web_traffic`; `eprom.json` → `promotions` (lát sau mới tách `promotions_ext`) |
| I3 | `shipments_realistic.csv`: file **không có `zip`**, nên `city, region, district` **không** được là `thua` (là nơi của shipper, khác nơi giao ở ≈97% dòng) |
| I4 | Hồi quy: `pytest scripts/pipeline/tests` giữ đúng mốc của HEAD `4056de8` (Claude chạy 2026-10-27): **54 đạt, 2 skip, 0 trượt**. Hai skip: `test_contract.py:58` (snapshot nằm ở `warehouse/pipeline/review-20261027/`, không ở `warehouse/pipeline/snapshots/`) và `test_pipeline.py:361` (worktree chưa có bản publish ở root mặc định) |

I2 và I3 chỉ kiểm phần chọn nguồn và phân loại `thua`; các kỳ vọng khác của shipments/eprom/epd/tf thuộc lát sau.

## 7. Lệnh chạy

```powershell
cd D:\retail-analytics-schema
D:/retail-analytics/.venv/Scripts/python.exe -m pytest scripts/ingest/tests -q
D:/retail-analytics/.venv/Scripts/python.exe -m pytest scripts/pipeline/tests -q
D:/retail-analytics/.venv/Scripts/python.exe -m scripts.ingest.auto_mapping data/student_data/orders_enriched.csv
```

Mục tiêu thời gian: CLI trên `orders_enriched` dưới 2 phút; cả `scripts/ingest/tests` dưới 5 phút. Chậm hơn thì ghi
trong báo cáo, không tự giảm phạm vi test.

## 8. Báo cáo của GPT khi xong (PM dán cho Claude rà)

- Danh sách file đã tạo/sửa (chỉ trong `scripts/ingest/` và `scripts/ingest/tests/`).
- Lệnh pytest đã chạy, số đạt/trượt/skip của `scripts/ingest/tests` và `scripts/pipeline/tests`.
- Kết quả thử vô hiệu code (§6.1): phần nào, test nào trượt.
- Toàn văn `bao_cao_mapping.md` sinh cho `orders_enriched`, và đường dẫn `mapping_de_xuat.yml`.
- Điểm chọn nguồn của 15 file (bảng: file, nguồn 1 + điểm, nguồn 2 + điểm).
- Các ngưỡng đã chọn và lý do.
- Thời gian chạy CLI và test.
- Giới hạn còn lại, chỗ đã làm khác phiếu (nếu có) và vì sao.

## 9. Rà của Claude (Claude ghi, GPT đọc để sửa)

| Lượt | Ngày | Kết quả | Phát hiện (mức nặng) | GPT đã sửa |
|---|---|---|---|---|
| | | | | |

## 10. Quyết định của PM

| Ngày | Câu hỏi | PM chốt |
|---|---|---|
| 2026-10-28 | `marital_status`, `education_level` của nhân viên (và `shipper_marital_status`, `shipper_education` ở lát sau) có tính là nhạy cảm không? | **Có.** Xử lý như PII: gắn cờ `nghi_pii` (§4.3 d), bỏ khỏi mart, không vào ngữ cảnh chat hay kho RAG (`docs/tien_hoa_schema.md` §10 mục 3) |
