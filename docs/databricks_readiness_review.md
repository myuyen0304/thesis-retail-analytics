# Kiểm tra khả năng chuyển Retail DWH lên Databricks

Ngày kiểm: **2026-10-02**. Phạm vi: kiểm code local, nguồn CSV và đọc DuckDB hiện có; đối chiếu tài liệu Databricks. Chưa chọn workspace, chưa đăng nhập, upload, compile target Databricks hoặc chạy cloud.

## 1. Kết luận

**Có thể chuyển kiến trúc DWH hiện tại lên Databricks. Code hiện tại chưa sẵn sàng để chạy nguyên trạng.**

Giữ mô hình `raw → staging → intermediate → marts → reporting`, star schema, grain và hợp đồng KPI PS1–PS5. Phần phải bổ sung là adapter/profile, loader, macro SQL, quote identifier và nhật ký ingestion. Chưa có căn cứ để hứa thời gian triển khai hoặc tốc độ cloud.

Đây là đánh giá khả thi, chưa thay đổi quyết định nền tảng trong `dwh_roadmap.md`. Hướng triển khai đề xuất: cùng snapshot nguồn, build đầy đủ trong catalog riêng được chọn, đối soát trước khi cho app đọc.

## 2. Bằng chứng đã kiểm trực tiếp

### 2.1. Code và môi trường

- 53 model SQL: 14 staging, 4 intermediate, 14 marts, 21 reporting. Một số model reporting tự cấu hình thành view.
- 3 file macro; 22 file singular test SQL; ngoài ra có generic test khai báo YAML. **22 không phải tổng số test dbt**.
- `profiles.yml` có `postgres`, `duckdb`, `snowflake`; chưa có target `databricks`.
- `.venv`: dbt-core `1.12.5`, DuckDB `1.5.5`; chưa cài `dbt-databricks`, `dbt-spark`, `databricks-sql-connector`.
- Databricks CLI `1.4.0` có trên PATH. Trong shell kiểm tra không có biến `DATABRICKS_*`; file cấu hình mặc định trong home không tồn tại. Kết quả này **không chứng minh người dùng chưa có workspace hoặc chưa đăng nhập trên trình duyệt**.
- Chưa kiểm edition, warehouse, catalog, quyền và quota của workspace thực tế.
- Checkout có nhiều thay đổi sẵn của người dùng. Không sửa code runtime, requirements, profile, skill hoặc roadmap; không stage/commit.

Fingerprint SHA-256 của 88 file SQL/YAML trong `retail_dbt` (loại `target`, `dbt_packages`) và `scripts/ingest/ingest_raw.py`:

`c54cc1d625253cb27eff3b62683e4a57bc34ea743144a84a41461a69a5b06346`

Cách tính: sort đường dẫn, ghép lần lượt `path.as_posix().encode() + NUL + file_bytes + NUL`, rồi SHA-256. Fingerprint phản ánh code tại thời điểm kiểm; không chứng minh DuckDB được build từ đúng revision đó.

### 2.2. Nguồn và baseline local

Đọc CSV bằng `csv.reader` (logical record), kiểm độ rộng record so với header; không in dữ liệu cá nhân. Đủ 14 nguồn, **2.960.736 record**, **131.825.398 byte** (~131,8 MB). Không có record sai số field hay record nhiều dòng trong snapshot hiện tại. Loader tương lai vẫn cần hỗ trợ CSV quoted/multiline đúng chuẩn.

| Nguồn | Record |
|---|---:|
| customers | 121.930 |
| geography | 39.948 |
| products | 2.412 |
| promotions | 50 |
| orders | 646.945 |
| order_items | 714.669 |
| payments | 646.945 |
| shipments | 566.067 |
| returns | 39.939 |
| reviews | 113.551 |
| inventory | 60.247 |
| web_traffic | 3.652 |
| sales | 3.833 |
| sample_submission | 548 |

Đọc `warehouse/dbt.duckdb` bằng `read_only=True`:

| Kiểm tra | Kết quả |
|---|---|
| Dòng `marts.fact_order_item` | 714.669 |
| Khóa khác nhau `(order_id, line_number)` | 714.669 |
| `int_returns`, `int_reviews` thiếu `line_number` | 0 / 0 |
| Số dòng báo cáo năm / tháng | 11 / 126 |
| R delivered năm 2019 | 864.329.801,94 |
| N delivered năm 2019 | 33.259 |

R và N năm 2019 đã tính lại độc lập từ `orders.csv JOIN order_items.csv`, lọc `order_status = 'delivered'` và ngày trong năm 2019: **khớp chính xác DuckDB**. Đây là kiểm tra một lát cắt, chưa phải đối soát toàn bộ KPI hay mọi dòng.

`rpt_build_info` ghi lần build **2026-09-29 14:45:38 UTC**; health log hiện lưu 158/158 test pass và 0 model lỗi. Đây là **kết quả lịch sử được đọc lại**, không phải 158 test chạy mới trong lần audit này. Không dùng nó để chứng nhận code hiện tại hoặc Databricks đã PASS.

## 3. Các điểm cần xử lý

### DB01 — Chưa có adapter và target Databricks

**Chặn chạy dbt trên Databricks.**

Nguồn: `retail_dbt/profiles.yml`, `requirements.txt`, metadata package đang cài.

Thêm `dbt-databricks` trong môi trường riêng, kiểm tương thích với dbt-core trước khi pin. Profile cần host, HTTP path, catalog, schema, phương thức xác thực; secrets qua môi trường/cơ chế xác thực được chọn. Không giả định CLI OAuth tự động dùng được cho mọi connector hoặc dbt profile. Tài liệu chính thức hướng dẫn riêng [dbt Core trên Databricks](https://docs.databricks.com/aws/en/partners/prep/dbt).

### DB02 — Loader PostgreSQL chưa dùng được cho Delta

**Chặn ingestion; phải giữ identity để tránh sai mapping.**

Nguồn: `scripts/ingest/ingest_raw.py`, `models/staging/_sources.yml`, `int_order_lines.sql`, `int_returns.sql`, `int_reviews.sql`.

Loader hiện dùng `psycopg`, `COPY FROM STDIN`, identity và transaction PostgreSQL. Metadata `external_location` đọc CSV local trong `_sources.yml` phục vụ DuckDB; không tự upload dữ liệu cho adapter Databricks.

Đề xuất loader mới:

1. Kiểm đủ danh sách 14 file, header, field count, row count và checksum.
2. Tạo `_src_row` bằng **thứ tự logical record của từng file nguồn** trước bước xử lý phân tán; có snapshot ID/checksum đi kèm.
3. Giữ mọi cột nguồn dạng chuỗi ở raw, quy ước empty/NULL tương thích staging. Có thể đóng gói raw thành Parquet mang `_src_row` rồi upload vào Volume được cấp quyền và nạp Delta.
4. Nạp snapshot theo phiên bản, ghi log từng nguồn; chạy lại cùng snapshot không nhân bản dòng.

Kiểm trực tiếp phát hiện **16 cặp `(order_id, product_id)` lặp** trong CSV. Vì vậy không thay `(order_id, line_number)` bằng cặp đó, không dùng `monotonically_increasing_id()` hoặc thứ tự đọc Spark để tái tạo vị trí nguồn. Kiểm cả mapping trả hàng/đánh giá và bridge khuyến mãi sau migration.

### DB03 — Quote identifier cần sửa ở ba staging model

**Rủi ro SQL lỗi hoặc đọc literal thay cột tùy cấu hình.**

- `stg_sales.sql`: `clean('"Date"')`, `clean('"Revenue"')`, `clean('"COGS"')`.
- `stg_sample_submission.sql`: cùng kiểu quote.
- `stg_web_traffic.sql`: `clean('"date"')`.

Databricks dùng backtick cho delimited identifier. Chuyển sang quote qua adapter hoặc một macro chung, giữ đúng tên nguồn. Không dựa vào thiết lập ANSI ngầm định. [Identifiers](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-identifiers).

### DB04 — Hai macro đang mặc định theo DuckDB

**Cần nhánh Databricks trước build.**

Nguồn: `retail_dbt/macros/cross_db.sql`.

| Macro | Nhánh default hiện tại | Hướng triển khai |
|---|---|---|
| `dow_monday0` | `isodow(d) - 1` | Dùng hàm Databricks tương đương, `weekday(d)` trả Monday = 0 |
| `round_half_even` | `round_even(x * 10^d, 0) / 10^d` | Thử nhánh dựa trên `bround`; kiểm chính xác quy tắc nhân trước rồi làm tròn và kiểu DOUBLE/DECIMAL |

Đối chiếu [weekday](https://docs.databricks.com/aws/en/sql/language-manual/functions/weekday) và [bround](https://docs.databricks.com/aws/en/sql/language-manual/functions/bround). **Có cùng tên quy tắc HALF_EVEN chưa chứng minh mọi kết quả float giống numpy/DuckDB.** Phải chạy `assert_inventory_derived_matches_source` trên cả 60.247 dòng tồn kho, kiểm cả cờ `overstock_flag` phụ thuộc kết quả làm tròn.

`extract(DOY FROM ...)` được Databricks hỗ trợ theo [tài liệu extract](https://docs.databricks.com/aws/en/sql/language-manual/functions/extract), nên không coi đây là lỗi cần sửa. `dbt.dateadd`, `dbt.datediff`, `dbt.date_trunc`, `dbt.listagg` đã dùng macro dbt: kiểm SQL sau compile bằng adapter Databricks thực tế; chưa kết luận PASS từ đọc code.

### DB05 — Health ingestion hiện rơi vào nhánh DuckDB

**Có thể sai thông tin freshness dù các bảng KPI build được.**

Nguồn:

- `models/reporting/rpt_health_ingest.sql`: chỉ PostgreSQL đọc `_ingest_log`; mọi target khác trả bảng rỗng.
- `rpt_health_summary.sql`: mọi target khác PostgreSQL mang `ingest_mode = 'doc_csv'`.
- `tests/assert_rpt_health.sql`: nhánh else mặc định kỳ vọng không có ingest log.
- `macros/health_log.sql`: ghi `ops` bằng tên hai thành phần và timestamp chung.

Thêm nhánh ingestion Databricks cùng schema log rõ ràng; sửa source YAML/test tương ứng. Kiểm timezone UTC, thứ tự run, ingest mới hơn build và trường hợp thiếu nguồn. Đảm bảo hook ghi đúng catalog. Kiểm kết quả **sau on-run-end** vì test trong build chưa thấy log kết thúc của chính lần chạy.

### DB06 — Catalog, publish và parity cần thiết kế rõ

**Điều kiện nghiệm thu, chưa phải lỗi runtime đã quan sát.**

- `generate_schema_name` trả thẳng `raw/staging/intermediate/marts/reporting`; hook dùng `ops`. Target khác tên không tự cô lập dữ liệu. Chọn catalog riêng hoặc cơ chế schema riêng đồng bộ cả refs, sources và hooks trước khi chạy.
- Các bảng hiện materialize riêng lẻ; một lần `dbt build` có test lỗi không tự hoàn tác mọi bảng đã thay. Build ở nơi chưa phục vụ người dùng, chỉ chuyển app sau khi quality gate và parity đạt. Không suy cơ chế rollback PostgreSQL áp dụng nguyên trạng cho toàn pipeline Delta.
- So sánh money DECIMAL chính xác sau thống nhất scale; count/khóa chính xác; DOUBLE có tolerance được giải thích theo cột. Kiểm đặc biệt phép SUM, nhân/chia decimal, COGS float, NULL, chia 0, ngày và thứ tự sort.
- Surrogate key nhiều dimension và fact dùng `row_number`: có thể đối soát cùng snapshot với thứ tự xác định; chưa phải chiến lược khóa bền vững khi bổ sung dữ liệu/incremental. Chưa cần thiết kế Kafka cho migration snapshot đầu tiên.

### DB07 — Streamlit cần connector riêng ở bước sau

Nguồn: `apps/retail_app/dwh/connection.py` chỉ nhận `postgres/duckdb`; các hàm `queries.py` đọc tên `reporting.*`.

Đưa DWH lên Databricks không tự làm app kết nối được. Bổ sung backend/connector, catalog mặc định hoặc tên đầy đủ, xác thực chỉ đọc và chuẩn hóa dữ liệu trả về. Chỉ thực hiện khi DWH đã đối soát; giao diện 5 PS có thể tái sử dụng nếu giữ schema đầu ra. [SQL connectors](https://docs.databricks.com/aws/en/dev-tools/sql-drivers-tools).

## 4. Trình tự triển khai và điều kiện hoàn thành

1. **Chọn workspace**: xác nhận Free Edition/gói khác, warehouse, catalog, landing Volume và quyền được cấp. Chưa thực hiện trong audit.
2. **Chuẩn bị local**: môi trường adapter riêng, target Databricks, sửa DB03–DB04; giữ khả năng chạy PostgreSQL/DuckDB.
3. **Ingest snapshot**: manifest 14 nguồn, `_src_row`, log, kiểm count/header/checksum/NULL và rerun.
4. **Build DWH**: chạy dbt bằng target thật, lưu manifest/run_results riêng để không ghi đè bằng chứng local; kiểm hooks và toàn bộ generic/singular tests.
5. **Đối soát**: marts theo business key; mapping từng return/review; dimensions/bridge; PS1–PS5 từng năm/tháng/giai đoạn/nhóm. Không chỉ so tổng doanh thu.
6. **Publish**: chỉ cho app đọc sau khi đạt gate; thử truy vấn, kiểm latency, cache, quota và lỗi kết nối. Kiểm tài khoản đọc không có quyền ghi.

Phân biệt trạng thái:

| Bước | Trạng thái lần kiểm này |
|---|---|
| Đọc code, nguồn, baseline DuckDB | Đã thực hiện |
| Một đối chứng độc lập R/N năm 2019 | Đạt |
| Cài adapter / compile target Databricks | Chưa thực hiện |
| Kết nối / deploy / build / test cloud | Chưa thực hiện |
| Parity toàn bộ local ↔ Databricks | Chưa thực hiện |
| Publish / benchmark / kết nối Streamlit | Chưa thực hiện |

## 5. Free Edition và archive

Free Edition có warehouse giới hạn, quota và giới hạn vận hành; có thể dùng cho thử nghiệm đồ án, nhưng khả năng của workspace cần kiểm thực tế. [Giới hạn chính thức](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations).

`archive/databricks/retail_medallion/README.md` mô tả pipeline Bronze/Silver cũ với 19 bảng 3NF, chưa phải triển khai 53 model dbt hiện tại. Chỉ tham khảo; đường dẫn lệnh cũ trong README cũng chưa được chuyển sang `archive/`. Không dùng archive để khẳng định cloud đã sẵn sàng.

## 6. Checksum nguồn tại thời điểm kiểm

SHA-256 của byte file gốc, không phải hash dữ liệu sau chuẩn hóa:

| File CSV | SHA-256 |
|---|---|
| customers | `5e58abf49e99d52bf8ddda44601a30e78667760908b862287bc6e69a45cf77b8` |
| geography | `f5d150bdfdfca7ac0c38118b1f5f8ea1b3f5de4cd23fa700d5aa0adcd2ab6353` |
| products | `890946808d8237dad0d39153efd427f5399a5e6eaa2302681ab6bdf8a706204c` |
| promotions | `158ee5843ee41a28b5f5748ab2c73bd712524da6c00930fa9e80774e3751b0be` |
| orders | `f4b3029f386f5f5a6baabd78aad0140e5a101ea6975f4cbaba04976813f3f3af` |
| order_items | `a8b2adfe54eec0dda79ced28e5987d6846b7f31cb6052356ab3a1772cc85e0bc` |
| payments | `aacef7716fe1c1442bc46e8885019cf1d67e12655c2e0f28bd0c9e92e145a6e7` |
| shipments | `9a96bd80dde30dae22d726cdcd414dd8463b879de4ec1f09334c22396a56242b` |
| returns | `501717bc76cf237c0dbbb68f586351870047198042c4232376983fec94699534` |
| reviews | `5230859408955d611bc430df5d788eb66fedd56f3be9f6fe912af6da643fa0f1` |
| inventory | `1bbcdd89569a5df4b938ac0577f0657030c41c3a18956f4ad748f1bf4f289768` |
| web_traffic | `9bc9b72e44a814e50ae6e9fdcfa915cda6fa2c5cf306b1b4b36b27dce8f44cf3` |
| sales | `081d539f50d41f202edfb064a2cf218d44e3ac1429c6c34fd1869ae060aa882d` |
| sample_submission | `1c0c574c3bc0edab5b053fb21c0cbb67393316d206503e14fbe4b17b9ce41aba` |
