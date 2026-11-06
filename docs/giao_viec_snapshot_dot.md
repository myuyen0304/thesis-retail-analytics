# Giao việc D2: snapshot = bản gốc + đợt giao dịch

Soạn ngày 2026-11-04. **PM duyệt 2026-11-04, gồm 5 chỗ ở §10.** GPT code §3–§5; Claude rà và tự chạy kiểm độc lập trước khi commit, chưa đạt thì ghi §9 để GPT sửa.
Thiết kế gốc: `docs/thiet_ke_nap_ky_moi.md` §0 (B′), §4.2, §4.3 (bản mới nhất ở nhánh `docs/thiet-ke-b-tam-thoi`, worktree `D:/retail-analytics-nhap`). Phiếu này đã chép đủ luật, không cần đọc thêm để code. Chỗ phiếu chặt hơn thiết kế: §10.

Đọc trước: `AGENTS.md`, `CLAUDE.md` §1, §5, `docs/agent_workflows.md`; `scripts/pipeline/snapshot.py`, `scripts/ingest/extension_prepare.py`, `scripts/ingest/extension_contract.py`, `scripts/ingest/source_contract.py`, `scripts/pipeline/contract.py`, `scripts/pipeline/cli.py:316–445`.

## 0. Vì sao cần

- Mọi snapshot hiện đọc đúng 14 file ở `data/` với số dòng cố định (`source_contract.SOURCES`), nên năm mới không vào được.
- D2 thêm đường `prepare --dot <thư mục>`: snapshot = 14 nguồn gốc + các đợt, kiểm đợt ở ngưỡng 0.
- **D2 dừng ở stage `prepare`.** Stage sau chưa dùng được với đợt: dbt và vùng dự báo là D3, công bố là D5.
- **Không có `--dot` thì phải y hệt hôm nay, đến từng byte.** Đây là yêu cầu quan trọng nhất của phiếu: `snapshot_id` đổi là lịch 08:00 dựng bản mới trên production.

## 1. Phạm vi

**Làm:** `prepare --dot`, phân loại file trong đợt, kiểm đợt, tính `sales` của đợt, nối vào nguồn lõi, nối vào nguồn mở rộng, chặn stage sau.

**Không làm (lát sau):**

- không sửa dbt, `scripts/forecast`, `apps/retail_app`, DAG;
- không sửa `scripts/ingest/extensions/orders_enriched.yml` (hash nằm trong `snapshot_id`) và `scripts/ingest/source_contract.py`;
- không sửa `build_silver.py`, `ingest_raw.py`, `scripts/ingest/snapshot.py`, `ingest_databricks.py`: các script cũ này không nằm trên đường pipeline;
- không nạp `tf.json` (lát D2b), không thêm luật miền;
- không có con trỏ dashboard, băng rôn, trang Gửi/Duyệt (D5);
- không kết nối Databricks, Neon, Airflow; không dựng image; không đưa code lên `app/myuyen`.

## 2. Môi trường và ràng buộc

- Worktree `D:/retail-analytics-nap`, nhánh `nap-ky/myuyen`, tiếp từ `687e78b` (D1 đã commit). Python `D:/retail-analytics/.venv/Scripts/python.exe`. **Không commit, không push.**
- **Chỉ tạo/sửa:** `scripts/ingest/dot.py` (mới), `scripts/pipeline/snapshot.py`, `scripts/ingest/extension_prepare.py`, `scripts/pipeline/cli.py`, `scripts/ingest/tests/test_dot.py` (mới), `scripts/pipeline/tests/test_snapshot_dot.py` (mới); ngoài ra chỉ điền §9 của phiếu này. Sửa file khác là sai phạm vi.
- Laptop PM ít RAM: kiểm đợt bằng DuckDB `threads=2`, `memory_limit='2GB'`, không dùng pandas. Không chạy nền lệnh nặng; bị dừng vì thiếu RAM thì báo, không tự chạy lại.
- Worktree không có `data/`. Chạy thật dùng `--data D:/retail-analytics-nhap/data`, chỉ đọc. Test tự dựng dữ liệu nhỏ, không đọc dữ liệu thật.
- Không in tên, số điện thoại nhân viên hay shipper ra log, thông báo lỗi hoặc manifest.

## 3. Dòng lệnh

```text
python -m scripts.pipeline.cli prepare --run-id <id> --root <thu muc> --data <thu muc> [--extension orders_enriched] --dot <thu muc dot> [--dot <thu muc dot 2>]
```

- `--dot` lặp được; thứ tự trên dòng lệnh là thứ tự nạp.
- `--dot` dùng với stage khác `prepare`, với `--target databricks` hoặc cùng `--snapshot-id`: `ap.error`.
- Chạy lại cùng `run_id` với đợt khác (kể cả bỏ `--dot`): `ValueError`, giống cách `--extension` đang xử lý (`cli.py:350–353`). So **danh sách `ma_dot` có thứ tự**, không so đường dẫn.

## 4. Luật

Lỗi của đợt là `ValueError` có `summary` (cùng đường ghi quarantine ở `cli.py:370–373`), mã thoát 2, nói rõ file, cột, số dòng, không kèm giá trị. Mọi kiểm chạy **trước** khi công bố thư mục snapshot; lỗi thì không để lại gì trong `<root>/snapshots`.

### 4.1 Phân loại file trong thư mục đợt

Phân loại theo header và sha256, tất định, **không dùng điểm của `auto_mapping`**. Không theo tên file, trừ đuôi. Đọc CSV bằng `utf-8-sig` vì `orders_enriched.csv` có BOM.

| Nhóm | Điều kiện | Xử lý |
|---|---|---|
| `master_khong_doi` | CSV, sha256 trùng `customers`, `products` hoặc `geography` của `--data` | Bỏ qua, ghi báo cáo |
| `khop_loi` | CSV, tập cột = đúng một nguồn giao dịch, thứ tự cột có thể khác | Xếp lại theo thứ tự hợp đồng, nối vào nguồn đó |
| `loi_kem_cot_them` | CSV, chứa đủ cột của đúng một nguồn giao dịch và có cột ngoài | Chỉ lấy cột lõi, xếp theo thứ tự hợp đồng; tên cột ngoài ghi vào `cot_ngoai` |
| `chi_de_xuat` | Mọi file `.json` | Không vào kho, ghi báo cáo. Kể cả `tf.json`, `epd.json`, `eprom.json` |

Nguồn giao dịch là 9 nguồn: `orders`, `order_items`, `payments`, `shipments`, `returns`, `reviews`, `promotions`, `inventory`, `web_traffic`.

**Cả đợt lỗi khi:** thiếu một trong 9 nguồn; hai file cùng một nguồn; khớp nhiều nguồn; CSV không vào nhóm nào; header trùng master mà sha256 khác (đợt không được đổi master); có `sales.csv`, `sample_submission.csv` hoặc file khác đuôi `.csv`, `.json`; có thư mục con; file 0 dòng.

### 4.2 Kiểm đợt (ngưỡng 0)

Gọi `moc` = `max(order_date)` của 14 nguồn gốc và các đợt đứng trước. Mọi kiểm có **một mã riêng** trong thông báo.

**Thứ tự:** phân loại §4.1 → D2-7 → D2-0 → D2-1 → D2-2 → D2-3 → D2-4 → D2-5 → D2-6 → D2-8 → tính `sales` §4.3 → ghi parquet nguồn lõi đã có đợt → chạy nguồn mở rộng §4.5 → ghi manifest → đổi tên thư mục. **Dừng ở mã đầu tiên vi phạm**, không gom lỗi. Sai thứ tự sẽ hỏng theo hai cách: tính `sales` trước D2-0 thì `quantity = 'N/A'` làm vỡ hoặc tính sai im lặng; chạy mở rộng trước khi `orders.parquet` có đợt thì R3 coi 38.088 đơn 2023 là mồ côi, khoảng 5,6%, vượt ngưỡng 1%.

| Mã | Kiểm |
|---|---|
| D2-0 | Kiểu và không rỗng trên **dòng của đợt**: `contract._checks(COLUMNS[nguồn], None)`. Bắt `quantity`, `unit_price` sai kiểu, ngày rỗng hoặc không đọc được. Thêm: `unit_price` quá 2 số lẻ bị từ chối (§10 mục 6). Không viết lại phép kiểm, không đổi đường đi khi không có `--dot` |
| D2-1 | `order_id`, `return_id`, `review_id`, `promo_id` không trùng trong đợt, không trùng bản gốc và các đợt trước |
| D2-2 | Mọi `order_date`, `ship_date`, `delivery_date`, `return_date`, `review_date`, `snapshot_date` và `date` của `web_traffic` > `moc`. Ô rỗng và ngày không đọc được đã do D2-0 bắt. **Không** áp cho `promotions.start_date`, `end_date` |
| D2-3 | Ngày đặt hàng liền nhau, không có ngày trống, từ `moc` + 1 tới ngày lớn nhất của đợt |
| D2-4 | `order_id` trong `order_items`, `payments`, `shipments`, `returns`, `reviews` phải thuộc **đơn của chính đợt này**. Trỏ tới đơn của bản gốc hay đợt trước là lỗi, vì sẽ đổi số kỳ cũ |
| D2-5 | `product_id`, `customer_id`, `zip` có trong master của `--data` |
| D2-6 | `promo_id`, `promo_id_2` khác rỗng có trong `promotions` gốc, đợt trước hoặc đợt này, và `order_date` nằm trong `[start_date, end_date]` |
| D2-7 | Hai `--dot` trên cùng dòng lệnh có cùng `ma_dot` là lỗi |
| D2-8 | Khóa chính còn lại trên **gốc + đợt**, cột khóa lấy từ `KEYS[nguồn]`, so theo kiểu hợp đồng trong `COLUMNS` (`dot.py`, không dùng `contract._checks` vì hàm đó so chuỗi; sửa ngày 2026-11-05 theo S3 ở §9). Thực tế chỉ còn bắt được `payments.order_id`, `shipments.order_id`, `web_traffic.date`, khóa `inventory`, vì các khóa khác đã qua D2-1, D2-4. Chạy sau cùng để ca trỏ về đơn gốc báo đúng D2-4 |

**Gửi lại:** trùng nguyên đợt bị D2-7 chặn. Gửi lại với mã mới (`order_id`, `return_id`, `review_id`, `promo_id`) bị D2-2 chặn, đây là ca chống cộng trùng.

**Vì sao `moc` chỉ lấy từ `order_date`:** đợt 2023 có `delivery_date` tới 2024-01-10. Nếu lấy max mọi cột thì đợt 2024 hợp lệ bắt đầu 2024-01-01 sẽ bị từ chối oan.

### 4.3 `sales` của đợt

- Hệ thống tự tính, không nhận từ file gửi: `Revenue(d) = Σ quantity × unit_price`, `COGS(d) = Σ quantity × cogs` của `products`, mọi trạng thái đơn, không trừ `discount_amount` (CLAUDE.md §5 điểm 1), theo `order_date`.
- Tính bằng DECIMAL, không dùng float; chỉ làm tròn 2 chữ số ở tổng ngày. Ghi chuỗi 2 chữ số thập phân.
- Dòng mới nối sau `sales` gốc theo ngày. `sample_submission` không đổi (xử lý ở D3).
- Cổng đối soát sẽ luôn khớp vì `sales` do chính hệ thống tính. Không ghi đây là bằng chứng dữ liệu đúng; đối chứng độc lập là `sales_doi_chung.csv` của D1, chỉ dùng trong kiểm của Claude, **không được đọc trong code**.

### 4.4 Nối vào nguồn lõi

- Thứ tự dòng: gốc, rồi từng đợt theo thứ tự `--dot`, trong đợt giữ thứ tự file. `_src_row` chạy liên tục `1..N` vì staging dựng số dòng theo `_src_row`.
- Giá trị giữ nguyên văn, ô rỗng thành NULL như đường hiện có (`snapshot.py:63`).
- `contract.check` ở `cli.py:379` vẫn chạy như hiện nay trên toàn bộ gốc + đợt, và phải đạt.

### 4.5 Nối vào nguồn mở rộng

Khi có `--extension` mà hợp đồng có `khoa_noi.nguon` là nguồn của một file `loi_kem_cot_them` trong đợt:

- File đợt phải chứa đủ `header` của hợp đồng; thiếu cột thì cả đợt lỗi. Cột ngoài hợp đồng (ví dụ `loyalty_tier`) không nạp và ghi vào `cot_ngoai`.
- Toàn bộ R1–R6 và ngưỡng chạy trên **gốc + đợt** gộp một lần, `_dong_goc` chạy liên tục. Bên trong gọi qua một tham số mới của `extension_prepare.prepare`; không có tham số thì đường đi cũ không đổi.
- `csv_sha256`, `hop_dong_sha256`, `file` của nguồn mở rộng vẫn là của file gốc và hợp đồng gốc. Mã đợt nằm ở phần định danh riêng (§4.6).
- `extension_prepare.validate` vẫn phải đạt trên snapshot có đợt.

Không có `--extension`: file vẫn nối vào nguồn lõi, phần cột thêm không vào kho.

### 4.6 Định danh và manifest

- `ma_dot` = 12 ký tự đầu sha256 của chuỗi `<tên file>:<sha256>;` theo tên file đã sắp xếp, gồm **mọi file** trong thư mục đợt.
- `snapshot_id` = công thức hiện có, nối thêm `dot:<ma_dot>;` theo thứ tự nạp. **Không đợt thì không nối gì.**
- Manifest chỉ thêm khóa khi có đợt: `co_du_lieu_tong_hop: true` và `dot`: danh sách theo thứ tự, mỗi mục có `ma_dot`, `moc`, từng file (tên, nhóm, nguồn, sha256, số dòng, khoảng ngày, `cot_ngoai`), tổng `Revenue`, `COGS` của đợt. Không có đường dẫn tuyệt đối, không có thời gian chạy.
- Mọi đợt đều coi là tổng hợp ở phạm vi 12/12; dữ liệu thật lâu dài nằm ngoài phiếu này (thiết kế §0 B′ mục 8).
- `snapshot.validate` đọc số dòng từ `SOURCES` cộng số dòng các đợt trong manifest, kiểm `_src_row`, hash và định danh như hiện nay. Sửa tay manifest phải bị phát hiện.

### 4.7 Chặn stage sau

- Trong `_execute`, sau khi `snapshot.validate` chạy ở stage khác `prepare` (`cli.py:409`): manifest có `dot` thì `ValueError` nói rõ "snapshot có đợt chưa dùng được ở stage này (D3, D5)". D3 sẽ nới cho `forecast`, `build`, `validate`; `publish` giữ chặn tới D5.
- **Đọc từ manifest, không đọc từ dòng lệnh hay context.** Đường `--snapshot-id` (`cli.py:362–366`) không có `--dot` nên nếu tin dòng lệnh thì bản tổng hợp lọt qua đúng đường này. Context cũng ghi `dot` và `co_du_lieu_tong_hop` lấy từ manifest.

## 5. Test

Test dùng dữ liệu nhỏ tự dựng, phải có:

- **Không đợt y hệt:** không `--dot`, trên fixture: `snapshot_id`, `manifest.json` và từng parquet giống từng byte với kết quả của đường cũ. Viết sao cho test này không phụ thuộc code mới, ví dụ so với công thức id viết tay và kiểm manifest không có khóa `dot`, `co_du_lieu_tong_hop`.
- **Đường đúng:** đợt sạch qua `prepare`; số dòng từng nguồn = gốc + đợt; dòng gốc không đổi; `_src_row` liên tục; `validate` đạt; `contract.check` đạt.
- **Hai đợt nối tiếp** đạt, kể cả khi `delivery_date` của đợt đầu sau ngày đầu của đợt sau; đảo thứ tự hai đợt thì D2-3 báo, vì đợt sau đứng trước để lại ngày trống.
- **Mỗi luật một ca hỏng, khớp đúng mã:** từng dòng lỗi ở §4.1; D2-0 cho `quantity`, `unit_price` sai kiểu, ngày rỗng, ngày không đọc được; D2-1 cho từng khóa, cả trùng trong đợt lẫn trùng gốc; D2-2 cho từng cột ngày, dùng ngày hợp lệ không sau `moc`; D2-3; D2-4 cho từng bảng con, cả trỏ tới đơn gốc; D2-5 cho từng khóa; D2-6 cho `promo_id` và `promo_id_2` riêng, cả không tồn tại lẫn ngoài hiệu lực; D2-7; D2-8 cho `payments`, `shipments`, `web_traffic`, `inventory`, gồm `web_traffic.date` trùng giữa hai đợt. Mỗi ca chỉ phá đúng một luật. Luật giống D1: **một kiểm không có ca hỏng thì coi như chưa kiểm**, và Claude sẽ bỏ từng mệnh đề để xem test có trượt không.
- **Chống cộng trùng:** cùng đợt hai lần báo D2-7; cùng đợt với mã mới báo D2-2.
- **`sales`:** tính đúng ca làm tròn chỉ ở tổng ngày (`cogs` = `0.104`, nhiều dòng); dòng hủy vẫn tính; có `discount_amount` không bị trừ; số kỳ vọng viết tay trong test, không tính lại bằng cùng biểu thức.
- **`loi_kem_cot_them`:** BOM, cột xen giữa và khác thứ tự; `cot_ngoai` đúng; giá trị cột ngoài không có trong parquet.
- **`khop_loi` khác thứ tự cột** vẫn ra parquet đúng thứ tự hợp đồng và `validate` đạt.
- **Mở rộng:** đợt sạch không bị R3 báo mồ côi; gốc + đợt qua R1–R6; R6 bắt được thuộc tính nhân viên đổi trong đợt; vượt ngưỡng tính trên tổng; thiếu cột hợp đồng thì lỗi; `extension_prepare.validate` đạt.
- **Định danh:** đổi một byte file đợt, kể cả file `chi_de_xuat`, thì đổi `snapshot_id`; đổi thứ tự `--dot` thì đổi; chạy lại cùng đợt ra đúng snapshot cũ; sửa tay `dot` hoặc `rows` trong manifest thì `validate` báo.
- **Chặn:** `forecast`, `build`, `validate`, `publish` trên snapshot có đợt đều bị chặn, kể cả khi vào qua `--snapshot-id` và khi context bị xóa khóa `dot` hoặc sửa về `prepared`, `forecasted`, `built`, `validated`; context giả `published`, `skipped` chỉ trả về như đường cũ, không ghi gì (sửa ngày 2026-11-05, xem §9); `--dot` với stage khác, `--target databricks`, `--snapshot-id` bị từ chối; đổi đợt trên cùng `run_id` bị từ chối.
- **Không để lại rác:** đợt lỗi thì `<root>/snapshots` không có thư mục mới.
- **Không lộ PII:** cấy tên giả vào cột ngoài và cột nhân viên; thông báo lỗi và `manifest.json` không chứa giá trị đó.

## 6. Chạy thật và báo cáo

GPT chạy tuần tự, một lần mỗi lệnh, từ root worktree. Root thử nằm trong `data_demo/` (đã gitignore), **không** dùng `warehouse/pipeline`:

```text
python -m scripts.pipeline.cli prepare --run-id d2-goc --root data_demo/kho_d2 --data D:/retail-analytics-nhap/data --extension orders_enriched
python -m scripts.pipeline.cli prepare --run-id d2-dot --root data_demo/kho_d2 --data D:/retail-analytics-nhap/data --extension orders_enriched --dot data_demo/dot_2023
```

Báo vào §9:

1. Lệnh, thời gian, kết quả pytest tách nhóm (`scripts/demo/tests`, `scripts/ingest/tests`, `scripts/pipeline/tests`), giải thích mọi ca trượt và bỏ qua; không gộp lẫn với `apps`.
2. `snapshot_id` của hai lượt. Lượt `d2-goc` phải bằng id chạy bằng code tại `fe1f65c` với cùng dữ liệu; nếu GPT chưa so được thì ghi rõ, Claude sẽ kiểm.
3. Số dòng từng nguồn, so bảng kỳ vọng dưới đây (gốc từ `SOURCES`, đợt từ manifest D1 seed 2023):

| Nguồn | Gốc + đợt = kỳ vọng |
|---|---|
| `orders` | 646.945 + 38.088 = 685.033 |
| `order_items` | 714.669 + 40.676 = 755.345 |
| `payments` | 646.945 + 38.088 = 685.033 |
| `shipments` | 566.067 + 32.960 = 599.027 |
| `returns` | 39.939 + 2.258 = 42.197 |
| `reviews` | 113.551 + 6.379 = 119.930 |
| `inventory` | 60.247 + 5.593 = 65.840 |
| `web_traffic` | 3.652 + 365 = 4.017 |
| `promotions` | 50 + 21 = 71 |
| `sales` | 3.833 + 365 = 4.198 |
| `customers`, `products`, `geography`, `sample_submission` | không đổi |

4. Nguồn mở rộng `orders_enriched`: `rows`, `so_dong_cach_ly`, `cach_ly` của cả hai lượt. Số cách ly của lượt có đợt so với lượt gốc; khác thì giải thích.
5. Phân loại 15 file của `dot_2023`: nhóm, nguồn, `cot_ngoai` (chỉ tên cột). Tổng `Revenue`, `COGS` của đợt, kèm cảnh báo đây là số tổng hợp.
6. Ba lệnh thử chặn trên bộ thật: gửi lại `--dot data_demo/dot_2023` hai lần; chạy stage `forecast` trên `d2-dot`; `--snapshot-id <id có đợt>` rồi `publish`.

## 7. Claude sẽ tự kiểm

Claude không tin riêng kết quả test của GPT và sẽ:

- so `snapshot_id`, manifest và parquet của lượt không đợt với code tại `fe1f65c`, từng byte;
- đọc parquet của `d2-dot` độc lập: phần dòng gốc y hệt lượt `d2-goc`; dòng đợt khớp file `dot_2023`; `sales` đợt khớp `sales_doi_chung.csv` và dòng ngày mẫu trong `sales.csv` của D1;
- làm hỏng từng mệnh đề trên bản sao, chạy test của GPT, gồm cả §4.7;
- tự chạy các ca chặn trên bộ thật, kể cả đợt sửa tay;
- kiểm `git status`: đúng các file ở §2, không có gì trong `data/`, `data_demo/`, `warehouse/` bị đưa vào git; `orders_enriched.yml`, `source_contract.py` không đổi.

Việc nặng do PM chạy ngoài Claude Code.

## 8. Câu chưa chắc thì hỏi

Gặp điều trái với dữ liệu thật hoặc phiếu (ví dụ cột được rỗng khác dự kiến, số dòng khác bảng §6, ca D2-x làm bộ `dot_2023` trượt) thì **dừng và báo**, không tự nới luật. Không sửa dữ liệu `dot_2023` để qua kiểm.

## 9. Báo cáo của GPT và kết quả rà

*(GPT điền phần báo cáo, Claude ghi kết quả rà.)*

### Báo cáo GPT — điểm chặn trước triển khai, ngày 2026-11-04

Đã đọc toàn bộ phiếu và đối chiếu `contract._checks`, `source_contract.COLUMNS`, `source_contract.KEYS`, đường prepare/validate hiện tại. Worktree đúng `D:/retail-analytics-nap`, nhánh `nap-ky/myuyen`, HEAD `687e78b`.

**Dừng theo §8: thứ tự kiểm ở §4.2 chưa khớp yêu cầu mã lỗi của test ở §5.** D2-0 phải chạy đầy đủ kiểm kiểu, không rỗng và khóa chính trên gốc + đợt, trước D2-1…D2-7. Nhưng:

1. `KEYS` đã có `orders.order_id`, `returns.return_id`, `reviews.review_id`, `promotions.promo_id`. Trùng trong đợt hoặc trùng gốc đều bị D2-0 phát hiện trước, nên không thể tạo ca hỏng báo riêng D2-1 cho từng khóa theo §5 nếu dừng ngay ở cổng đầu.
2. `COLUMNS` và `_checks` đã kiểm ngày không rỗng/ép được kiểu date. Ngày rỗng hoặc sai kiểu sẽ bị D2-0 phát hiện trước D2-2; ngày hợp lệ nhưng không sau mốc vẫn kiểm được ở D2-2.
3. `payments` và `shipments` có khóa chính `order_id`. Khi dòng đợt trỏ về đơn gốc đã có payment/shipment, D2-0 sẽ báo trùng khóa trước D2-4. Điều này ảnh hưởng ca §5 yêu cầu đúng mã D2-4 cho từng bảng con khi trỏ về đơn gốc.

**Cần PM chốt cách gán mã khi một ca vi phạm nhiều cổng:** giữ thứ tự và ưu tiên mã D2-0, sửa kỳ vọng các test chồng lấn; hay vẫn chạy đủ phép kiểm D2-0 nhưng gom lỗi rồi gán mã chuyên biệt D2-1/D2-2/D2-4 theo quy tắc PM duyệt. Chưa tự chọn cách nào, chưa bỏ hoặc nới phép kiểm.

Chưa sửa sáu file triển khai/test ở §2; chỉ điền §9. Chưa chạy pytest hoặc các lệnh §6, chưa sinh snapshot, không kết nối dịch vụ ngoài, không stage/commit/push. Không có kết quả test hay snapshot_id mới để báo. Sau khi PM chốt cần tiếp tục §3–§6, rồi cập nhật báo cáo nghiệm thu.

### Claude trả lời điểm chặn, ngày 2026-11-04

GPT dừng đúng; đây là lỗi soạn phiếu của Claude. Không chọn một trong hai cách đã nêu: **tách phép kiểm khóa chính khỏi D2-0.** D2-0 chỉ còn kiểu và không rỗng trên dòng đợt; thêm D2-8 cho khóa chính trên gốc + đợt, chạy sau cùng. Dừng ở mã đầu tiên, không gom lỗi. Không phép kiểm nào bị bỏ hay nới. Đã sửa §4.2, §4.4, §5. Đây là việc kỹ thuật, không đổi luật PM đã duyệt ở §10. GPT làm tiếp §3–§6 theo phiếu đã sửa.

### Báo cáo GPT — hoàn tất §3–§6, ngày 2026-11-04

Đã triển khai trên `D:/retail-analytics-nap`, nhánh `nap-ky/myuyen`, nền `687e78b`. Chỉ tạo/sửa sáu file ở §2 và phần báo cáo §9. Không stage, commit, push; không sửa D1, `source_contract.py`, hợp đồng `orders_enriched.yml`, dbt, app, dự báo hay DAG. Không kết nối cloud, không dựng image, không chạy pipeline đầy đủ.

**Thay đổi:** thêm `--dot` lặp được; phân loại bằng header/hash; kiểm theo thứ tự đã chốt D2-7 → D2-0…D2-6 → D2-8; tính sales DECIMAL và nối nguồn trong vùng tạm; chạy mở rộng sau khi lõi chứa đơn mới; ghi định danh/manifest rồi mới đổi tên. Đường không đợt giữ cách ghi cũ. Cổng stage đọc manifest trước cả nhánh trả về sớm của context `published`/`skipped`, nên không thể vượt cổng chỉ bằng sửa context. Mỗi lỗi đợt có summary và chỉ nêu file/cột/số dòng.

Manifest có thêm `dot_sha256` khi có đợt để kiểm toàn bộ metadata `dot` (gồm số dòng, mốc, tổng tiền); công thức `snapshot_id` vẫn đúng §4.6, không đưa hash metadata này vào công thức. `_src_row` và `_dong_goc` liên tục theo thứ tự gốc rồi đợt. Cột ngoài hợp đồng không vào parquet. Các kết nối DuckDB dùng để kiểm/nối đợt và kiểm nguồn mở rộng của đợt đặt 2 luồng/2GB.

**Kiểm thử local, dữ liệu nhỏ tự dựng.** Lệnh chạy tại root worktree, dùng Python `D:/retail-analytics/.venv/Scripts/python.exe`:

```powershell
& D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider scripts/demo/tests -q --tb=short -rs --junitxml=C:/Users/Win/AppData/Local/Temp/d2_demo.xml
& D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider scripts/ingest/tests scripts/pipeline/tests -q --tb=short -rs --junitxml=C:/Users/Win/AppData/Local/Temp/d2_final.xml
```

Hai lệnh chạy tuần tự, không chạy song song. Lượt demo mất **263,82 giây**, exit 0; lượt ingest + pipeline cuối mất **126,67 giây**, exit 1. Số từng nhóm lấy từ XML, không cộng các lượt chạy lặp:

| Nhóm | Đạt | Trượt | Lỗi thiết lập | Bỏ qua |
|---|---:|---:|---:|---:|
| `scripts/demo/tests` | 64 | 0 | 0 | 0 |
| `scripts/ingest/tests` | 224 | 1 | 6 | 17 |
| `scripts/pipeline/tests` | 124 | 0 | 0 | 2 |

Trong đó **103 test D2 mới đều đạt**: 78 ở `test_dot.py`, 25 ở `test_snapshot_dot.py`. Sau lượt đầy đủ, tăng độ chặt hai test về cột ngoài xen giữa/header khác thứ tự và loại cột ngoài khỏi parquet mở rộng; chạy lại bằng `-k 'classify_master_json_and_extra_columns or extension_clean_and_no_pii_manifest'`: **2 đạt, 76 không chọn**, 3,73 giây. Không cộng hai ca này lần nữa vào bảng.

Các test mới có: mỗi mã kiểm một ca hỏng riêng; từng khóa D2-1, từng ngày D2-2, từng bảng con D2-4; khuyến mãi chính/phụ thiếu hoặc hết hiệu lực; trùng web traffic giữa hai đợt; hai đợt liền nhau và đảo thứ tự; gửi lại với mã mới; sales trước chiết khấu, gồm dòng hủy, `cogs=0.104` chỉ làm tròn ở tổng ngày, ngày không có dòng hàng có tổng 0; R1–R6 trên nguồn mở rộng gộp và ngưỡng tính theo tổng; hash/manifest bị sửa; CLI sai tổ hợp; stage qua snapshot_id/context bị sửa; lỗi không để snapshot dở và không lộ giá trị PII. Test đường cũ dựng công thức id, manifest và parquet tham chiếu độc lập rồi so từng byte trên fixture, đạt.

**Giải thích hồi quy chưa đạt hết:** `test_nhap_approval.py::test_epd_notebook` thiếu `data/student_data/epd.json`; sáu lỗi thiết lập của cùng file thiếu `data/student_data/orders_enriched.csv` (`test_orders_no_conflict`, `test_pii_defaults`, `test_contract_equivalent`, ba ca `test_load_rejects_decisions`). 17 ca `test_auto_mapping.py` bỏ qua do thiếu dữ liệu/tham chiếu; hai ca pipeline bỏ qua do thiếu snapshot `5bd9a84aaf73` và bản pipeline đã publish. Không chép dữ liệu vào worktree hay sửa test cũ để che các điều kiện này. Những lượt phát triển ban đầu có hai lỗi fixture đã sửa: thêm dòng CSV rỗng khi thử đổi byte, và ca R2 vô tình đổi cả ngày nên kích hoạt R4. Không còn test D2 trượt.

**Hai lệnh prepare thật**, mỗi lệnh chạy đúng một lần, tuần tự:

```powershell
& D:/retail-analytics/.venv/Scripts/python.exe -B -m scripts.pipeline.cli prepare --run-id d2-goc --root data_demo/kho_d2 --data D:/retail-analytics-nhap/data --extension orders_enriched
& D:/retail-analytics/.venv/Scripts/python.exe -B -m scripts.pipeline.cli prepare --run-id d2-dot --root data_demo/kho_d2 --data D:/retail-analytics-nhap/data --extension orders_enriched --dot data_demo/dot_2023
```

| Run | Thời gian | Exit / stage | snapshot_id |
|---|---:|---|---|
| d2-goc | 44,110 giây | 0 / prepared | `47e7cbe765d9` |
| d2-dot | 72,477 giây | 0 / prepared | `29fdaedea8c8` |

Chưa chạy lại code tại `fe1f65c` trên dữ liệu thật để so trực tiếp id/byte; **không nhận là đã chứng minh parity bộ thật với commit đó**. Test fixture độc lập của đường cũ đã đạt; phần so bộ thật với `fe1f65c` để Claude thực hiện theo §7.

Số dòng đọc từ hai manifest; toàn bộ khớp bảng kỳ vọng §6:

| Nguồn | Gốc | Có đợt | Phần tăng |
|---|---:|---:|---:|
| orders | 646.945 | 685.033 | 38.088 |
| order_items | 714.669 | 755.345 | 40.676 |
| payments | 646.945 | 685.033 | 38.088 |
| shipments | 566.067 | 599.027 | 32.960 |
| returns | 39.939 | 42.197 | 2.258 |
| reviews | 113.551 | 119.930 | 6.379 |
| inventory | 60.247 | 65.840 | 5.593 |
| web_traffic | 3.652 | 4.017 | 365 |
| promotions | 50 | 71 | 21 |
| sales | 3.833 | 4.198 | 365 |
| customers | 121.930 | 121.930 | 0 |
| products | 2.412 | 2.412 | 0 |
| geography | 39.948 | 39.948 | 0 |
| sample_submission | 548 | 548 | 0 |

Mở rộng `orders_enriched`: lượt gốc `rows=646945`, `so_dong_file=646945`, `so_dong_cach_ly=0`, `cach_ly={}`; lượt có đợt `rows=685033`, `so_dong_file=685033`, `so_dong_cach_ly=0`, `cach_ly={}`. Số cách ly không đổi; không có R3 mồ côi cho 38.088 đơn mới. `snapshot.validate`, `extension_prepare.validate` và `contract.check` đều đã qua trong hai lượt prepare.

**Đợt `635b7f755ba1`, mốc `2022-12-31`.** Phân loại đủ 15 file:

| File | Nhóm | Nguồn | cot_ngoai |
|---|---|---|---|
| customers.csv | master_khong_doi | customers | [] |
| products.csv | master_khong_doi | products | [] |
| geography.csv | master_khong_doi | geography | [] |
| orders_enriched.csv | loi_kem_cot_them | orders | Danh sách A bên dưới |
| shipments_realistic.csv | loi_kem_cot_them | shipments | Danh sách B bên dưới |
| order_items.csv | khop_loi | order_items | [] |
| payments.csv | khop_loi | payments | [] |
| returns.csv | khop_loi | returns | [] |
| reviews.csv | khop_loi | reviews | [] |
| promotions.csv | khop_loi | promotions | [] |
| inventory.csv | khop_loi | inventory | [] |
| web_traffic.csv | khop_loi | web_traffic | [] |
| tf.json | chi_de_xuat | null | [] |
| epd.json | chi_de_xuat | null | [] |
| eprom.json | chi_de_xuat | null | [] |

Danh sách A: `city`, `region`, `district`, `sales_employee_id`, `sales_employee_name`, `marital_status`, `education_level`, `years_experience`, `comment`, `loyalty_tier`.

Danh sách B: `shipper_id`, `shipper_company`, `shipper_vehicle`, `shipper_experience_years`, `shipper_rating`, `delivery_success_rate`, `average_delivery_time`, `working_shift`, `join_date`, `shipper_name`, `shipper_phone`, `shipper_gender`, `shipper_age`, `shipper_marital_status`, `shipper_education`, `city`, `region`, `district`.

Đây là tên cột ngoài **lõi**. Khi bật mở rộng orders_enriched, chỉ cột đã duyệt được nạp theo hợp đồng; `loyalty_tier` không nạp. Ba JSON không vào kho.

Tổng đợt do hệ thống tính: **Revenue (G) = 1.108.842.415,88; COGS = 992.869.698,28**, 365 ngày sales. **Dữ liệu tổng hợp chỉ để demo**, không dùng kết luận nghiệp vụ. Số này không phải đối chứng độc lập: code không đọc `sales_doi_chung.csv` của D1.

**Thử chặn trên bộ thật:**

```powershell
& D:/retail-analytics/.venv/Scripts/python.exe -B -m scripts.pipeline.cli prepare --run-id d2-trung --root data_demo/kho_d2 --data D:/retail-analytics-nhap/data --extension orders_enriched --dot data_demo/dot_2023 --dot data_demo/dot_2023
& D:/retail-analytics/.venv/Scripts/python.exe -B -m scripts.pipeline.cli forecast --run-id d2-dot --root data_demo/kho_d2
& D:/retail-analytics/.venv/Scripts/python.exe -B -m scripts.pipeline.cli prepare --run-id d2-theo-id --root data_demo/kho_d2 --data D:/retail-analytics-nhap/data --extension orders_enriched --snapshot-id 29fdaedea8c8
& D:/retail-analytics/.venv/Scripts/python.exe -B -m scripts.pipeline.cli publish --run-id d2-theo-id --root data_demo/kho_d2
```

| Ca | Kết quả | Thời gian |
|---|---|---:|
| Gửi cùng đợt hai lần | Exit 2, `D2-7: file=635b7f755ba1; cột=-; số dòng=1` | 1,932 giây |
| forecast trên d2-dot | Exit 2, `snapshot có đợt chưa dùng được ở stage này (D3, D5)` | 1,710 giây |
| prepare qua snapshot_id | Exit 0, prepared, vẫn snapshot `29fdaedea8c8` | 2,672 giây |
| publish trên d2-theo-id | Exit 2, cùng thông báo chặn D3/D5 | 1,550 giây |

Sau các ca thử, `data_demo/kho_d2/snapshots` chỉ có hai thư mục `47e7cbe765d9` và `29fdaedea8c8`, không có thư mục tạm hoặc snapshot mới của ca lỗi. Không chạy dự báo/build/publish thực sự.

**Phạm vi và giới hạn:** `git diff --check` đạt; Git chỉ có sáu file §2 và phiếu này thay đổi, không có file staged; `data_demo/` được ignore. Không thay đổi luật đã chốt hoặc nới cổng kiểm. Chưa chạy rà đột biến hay đối soát parquet bộ thật độc lập của Claude; chưa chứng minh tương thích các stage D3/D5 và chúng vẫn bị chặn. Đã điền §9 và dừng tại đây.

### Claude rà D2 lượt 1, ngày 2026-11-05: chưa đạt

Bộ kiểm nằm ngoài repo (`C:/Users/Win/d2_kiem`), chạy trên đúng code GPT báo, không sửa code. Đã so sha256 sáu file trước và sau lượt chạy: không đổi. Log: `ket_qua.log`.

| Hạng mục §7 | Kết quả |
|---|---|
| Không đợt, `prepare`: `snapshot_id`, manifest, parquet, `cach_ly` so với code `fe1f65c` | **Đạt, giống từng byte**: mở rộng `47e7cbe765d9` (17 file), 14 nguồn `5bd9a84aaf73` (15 file) |
| Không đợt, bốn stage sau khi run `skipped` | **Trượt**, xem S1 |
| Đọc độc lập parquet `d2-dot` (không import code repo) | **Đạt hết**: định danh, số dòng từng nguồn, dòng gốc y hệt, dòng đợt khớp file từng ô, `sales` khớp `sales_doi_chung.csv` và khớp tính lại bằng Decimal, không có PII trong manifest (dữ liệu tổng hợp) |
| File hợp đồng, dbt, app so với `fe1f65c` | **Đạt**, không đổi |
| Ca chặn trên bộ thật, đợt sửa tay (lượt đầu bộ kiểm của Claude lỗi vì gặp thư mục `cach_ly`; đã sửa và chạy lại ngày 2026-11-05, sha256 bốn file code trùng lượt đầu, log `ket_qua_5.log`) | **Đạt hết**: chạy lại ra đúng `29fdaedea8c8`, 17 file giống từng byte; `forecast`, `build`, `validate`, `publish` bị chặn, kể cả sau `prepare --snapshot-id`; 5 kiểu sửa manifest bị bắt trước cổng đợt; 16 ca sửa tay ra đúng mã và không để lại snapshot, gồm gửi lại cùng kỳ với mã mới (D2-2); đổi một byte `tf.json` thì đổi `snapshot_id` |
| Làm hỏng từng mệnh đề, 81 ca | 60 bị bắt, **21 sống sót**, xem T1–T9 |
| Ca biên ngoài test của GPT, 17 ca | 13 đạt, **4 trượt**, xem S2–S4 |

**Sửa code:**

- **S1. `cli.py`, trả lại thứ tự của `fe1f65c`.** Đo được: run `skipped`, bốn stage từ 1,1 giây lên 4,8 giây; snapshot đã dọn thì `forecast` từ exit 0 thành exit 2 `FileNotFoundError`, mà DAG không retry mã 2. Thứ tự đúng: `published`/`skipped` trả về, rồi `code_version`, rồi `snapshot.validate`, cổng đợt đặt ngay sau `validate`. Nguyên nhân từ phiếu: §4.7 ghi đúng vị trí nhưng §5 đòi chặn mọi kiểu sửa context; Claude đã sửa §5. Context giả `published`/`skipped` không làm được gì vì các nhánh đó chỉ trả về. Sửa `test_stages_blocked_from_manifest` theo §5 mới, thêm test giả `published`/`skipped` không đổi registry, và test không đợt: run `skipped` có `snapshot_path` không còn vẫn trả về.
- **S2. `dot.py`, D2-1 so `order_id` theo kiểu hợp đồng (integer), cả trong đợt lẫn với gốc.** Hiện `011` và `11`, `01` và `1` lọt qua `prepare`, vì so chuỗi còn staging và `new_sales` ép số nguyên. Đo trên fixture: mỗi ngày Revenue từ `0.20` thành `0.40`, snapshot vẫn được tạo. Unique trên `fact_order` có thể bắt lúc build (chưa chạy), nhưng D2 phải chặn trước. `return_id`, `review_id`, `promo_id` là string, giữ nguyên. **Test riêng, trượt trước khi sửa:** `011`/`11` trong đợt; `01`/`1` với gốc.
- **S3. `dot.py`, D2-8 so khóa theo kiểu hợp đồng, trong `dot.py`, không sửa `contract._checks`.** Hiện `web_traffic.date` có `2023-1-1` và `2023-01-01` không bị bắt. Đây là lỗi soạn phiếu của Claude: phiếu bảo dùng lại `_checks`. **Test riêng, trượt trước khi sửa:** `2023-1-1` cạnh `2023-01-01`.
- **S4. `dot.py`, D2-0 từ chối `unit_price` quá 2 số lẻ.** Hợp đồng và staging là `decimal(14,2)` nhưng `new_sales` tính trên `decimal(38,16)`: `0.105` × 2 cho `sales` 0,21 còn staging 0,22. Bộ thật không có ca này (gốc 0/714.669 dòng, đợt 0/40.676 dòng), nên không đổi `snapshot_id` của đợt hiện tại. Đây là luật mới chặt hơn gốc, đã ghi §10 mục 6. **Test riêng, trượt trước khi sửa:** `unit_price=0.105`.
- **S5 (nhỏ). `dot.py:160`, D2-3 báo số ngày thiếu thay vì số ngày có đơn.** Thiếu một ngày mà thông báo ghi `số dòng=364`, người đọc tưởng hỏng 364 dòng. **Test riêng, trượt trước khi sửa:** thiếu đúng một ngày thì báo `số dòng=1`.

**Thêm test** (code hiện tại đã đúng ở T3–T5 theo ca biên hoặc đọc độc lập, nhưng test không giữ được). Tên trong ngoặc là đột biến phải bị bắt; Claude sẽ chạy lại đúng các đột biến này để nghiệm thu:

- **T1.** `test_d22_each_date` lấy tham số từ chính `dot.DATES`, nên bỏ cột khỏi `DATES` thì mất luôn ca (7 đột biến sống). Viết tay danh sách cột trong test. (`D2-2 bo orders`, `bo ship_date`, `bo delivery_date`, `bo returns`, `bo reviews`, `bo inventory`, `bo web_traffic`)
- **T2.** Fixture luôn `quantity=1`, nên bỏ `quantity` khỏi công thức `sales` vẫn đạt. Thêm ca `quantity` > 1 với số viết tay. (`sales bo quantity`)
- **T3.** D2-5 cho từng bảng và cột có khóa ngoài, không chỉ `orders`, `order_items`. (`D2-5 chi hai bang`)
- **T4.** D2-6 ca hợp lệ: khuyến mãi của gốc và của đợt trước được nhận. (`D2-6 chi dot nay`, `D2-6 chi goc`)
- **T5.** `D2-format` và `D2-changed` có ca riêng; header bắt đầu `_` báo `D2-header`. (`41 ma D2-format`, `46 bo bam lai file`, `41 header gach duoi`)
- **T6.** Thư mục con đặt tên `x.csv` trong thư mục đợt báo `D2-file`. (`41 bo chan thu muc con`)
- **T7.** Mở rộng: đợt thiếu cột hợp đồng báo `D2-extension`; file mở rộng gốc có header khác `doc['header']` thì `extension_prepare` từ chối ở chế độ nối đợt. (`45 bo kiem thieu cot`, `45 bo kiem header goc`)
- **T8.** `snapshot.validate`: sửa một mục trong `files` (`sha256` hoặc `ten`), giữ nguyên `ma_dot`, tính lại `dot_sha256`, phải báo; không sửa `ma_dot` vì `snapshot_id` đã bắt, đột biến vẫn sống. Sửa `co_du_lieu_tong_hop` phải báo. Snapshot đã có sẵn mà hỏng thì `prepare` chạy lại phải báo. (`46 validate ma_dot`, `46 validate co tong hop`, `46 khong kiem lai khi out ton tai`)
- **T9.** Gọi `_execute` trực tiếp với `dots` và stage khác `prepare`. (`3 gac trong _execute`)

**Ghi nhận:** khóa `dot_sha256` ngoài phiếu được chấp nhận, không đổi công thức `snapshot_id`.

**Chuyển cho D3, không sửa ở D2:** chạy lại `prepare --snapshot-id` cùng `run_id` trên snapshot có đợt báo exit 2 "danh sách --dot khác" (`cli.py:358`), vì context có đợt mà dòng lệnh này không được nhận `--dot`. Lỗi này an toàn vì dừng, không làm sai số, và lệnh `--dot` chạy lại vẫn idempotent. Nếu D3 hoặc DAG nhập dùng `--snapshot-id` cho snapshot có đợt thì phải xử lý, vì retry sẽ trượt.

**Thứ tự:** lượt chạy lại ca chặn đã xong, GPT sửa S1–S5 và T1–T9 được. Sửa xong, GPT chạy lại lệnh §6, cập nhật §9 và dừng, không commit. Claude chạy lại toàn bộ bộ kiểm trên code mới, gồm đúng các đột biến đã nêu.

### GPT sửa sau Claude rà D2 lượt 1 — ngày 2026-11-05

**Đã sửa S1–S5 và bổ sung T1–T9.** Làm tại `D:/retail-analytics-nap`, nhánh `nap-ky/myuyen`. Lượt này chỉ sửa `scripts/ingest/dot.py`, `scripts/pipeline/cli.py`, hai file test D2 và mục §9 này. Các thay đổi D2 có sẵn trong `snapshot.py`, `extension_prepare.py` giữ nguyên. Không sửa `orders_enriched.yml`, `source_contract.py` hoặc dữ liệu `dot_2023`; không commit, stage, push, kết nối cloud hay chạy pipeline đầy đủ.

**Bằng chứng trượt trước sửa code:** thêm năm ca S2–S5 vào test, chạy khi code vẫn nguyên trước lượt sửa. Kết quả cuối của bước này **5 trượt, 78 không chọn**, 5,60 giây, exit 1. Hai ca S2 (`011`/`11` trong đợt; `01`/`1` với gốc), S3 (hai cách viết cùng ngày) và S4 (`0.105`) đều trượt vì không ném `DotError`; S5 trượt vì summary ghi 2 thay vì 1 ngày thiếu. Ca S2 với gốc giữ bảng con trỏ đúng đơn mới để chỉ phá D2-1. Lượt thử đầu của ca này còn bị D2-4 bắt do fixture bảng con chưa đổi; đã chỉnh fixture và chạy lại toàn bộ năm ca **trước khi sửa code**. XML cuối: `C:/Users/Win/AppData/Local/Temp/d2_review_red.xml`.

| Mã | Đã sửa và kiểm |
|---|---|
| S1 | Trả lại thứ tự `published/skipped` → kiểm `code_version` → `snapshot.validate` → cổng đợt. Test bốn stage, context bị xóa dấu đợt và đổi về từng trạng thái `prepared/forecasted/built/validated` vẫn bị chặn. Context giả `published/skipped` trả về, không đổi registry/context và không gọi kiểm snapshot hoặc code. Run không đợt `skipped` vẫn trả về khi snapshot không còn. Có test kiểm code trước snapshot. |
| S2 | D2-1 dùng kiểu từ `COLUMNS` cho cả so trùng trong đợt và với gốc/các đợt trước: `order_id` ép integer; ba khóa string giữ nguyên. Hai ca hồi quy đều đạt sau sửa. |
| S3 | D2-8 dựng biểu thức phân vùng khóa theo kiểu hợp đồng trong `dot.py`, gồm khóa ghép. Không sửa `contract._checks` hay `source_contract.py`. Ca `2023-1-1` cạnh `2023-01-01` bị D2-8 bắt. Đây là thực hiện chỉ dẫn mới §9 thay cho cách gọi `_checks({}, KEYS[nguồn])` còn ghi ở §4.2. |
| S4 | D2-0 kiểm phần lẻ của `unit_price` và giá trị trước/sau ép `decimal(14,2)` trước D2-1 và trước tính sales; từ chối quá hai số lẻ, không sửa giá. Ca `0.105` bị D2-0 bắt. Đường không đợt không đổi. |
| S5 | D2-3 báo số ngày còn thiếu = độ dài khoảng ngày trừ số ngày có đơn. Ca thiếu đúng một ngày có summary bằng 1. |

| Test | Phần bổ sung để bắt đột biến |
|---|---|
| T1 | Viết tay đủ bảy cột ngày trong tham số `test_d22_each_date`, không lấy từ `dot.DATES`. |
| T2 | `quantity=3`, số sales viết tay: ngày đầu Revenue `0.40`, COGS `0.42`; ngày sau `0.20` và `0.21`. |
| T3 | Viết tay đủ bảy cặp bảng/cột tham chiếu master, gồm returns, reviews và inventory. |
| T4 | Cả `promo_id` và `promo_id_2`, mỗi cột có ca hợp lệ tham chiếu khuyến mãi gốc, đợt trước và đợt hiện tại. |
| T5 | JSON sai cú pháp và CSV sai encoding báo D2-format; sửa file sau khi kiểm đợt báo D2-changed; header thêm cột `_private` báo D2-header. |
| T6 | Thư mục con tên `x.csv` báo D2-file. |
| T7 | Ca thiếu `comment` của đợt kiểm đúng summary `D2-extension: comment`, để không lẫn với kiểm header phía sau; thêm ca header file mở rộng gốc đủ cột nhưng đảo thứ tự bị D2-extension từ chối trong chế độ nối đợt. |
| T8 | Hai ca sửa `sha256`/`ten` trong files, giữ `ma_dot`, tính lại `dot_sha256` vẫn bị validate bắt; sửa cờ tổng hợp bị bắt; làm hỏng parquet snapshot đã tồn tại rồi prepare lại bị bắt. |
| T9 | Gọi `_execute` trực tiếp với dots và từng stage forecast/build/validate/publish/run: ValueError đúng cổng, chưa tạo root. |

**Lệnh pytest** (chạy tại root worktree, tuần tự):

```powershell
& D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider scripts/ingest/tests/test_dot.py -k 'test_s2 or test_s3 or test_s4 or test_s5' -q --tb=short --junitxml=C:/Users/Win/AppData/Local/Temp/d2_review_red.xml
& D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider scripts/ingest/tests/test_dot.py scripts/pipeline/tests/test_snapshot_dot.py -q --tb=short --junitxml=C:/Users/Win/AppData/Local/Temp/d2_review_focused.xml
& D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider scripts/demo/tests -q --tb=short -rs --junitxml=C:/Users/Win/AppData/Local/Temp/d2_review_demo.xml
& D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider scripts/ingest/tests scripts/pipeline/tests -q --tb=short -rs --junitxml=C:/Users/Win/AppData/Local/Temp/d2_review_regression.xml
```

Lệnh đầu là bằng chứng trước sửa code. Sau sửa, bộ D2 riêng **159 đạt, 0 trượt, 0 bỏ qua**, 84,78 giây, exit 0: 104 test ingest và 55 test pipeline. Lượt demo mất **152,89 giây**, exit 0; lượt ingest + pipeline mất **120,01 giây**, exit 1. Kết quả hồi quy cuối tách từ XML, không cộng lặp bộ D2 riêng:

| Nhóm | Đạt | Trượt | Lỗi thiết lập | Bỏ qua |
|---|---:|---:|---:|---:|
| scripts/demo/tests | 64 | 0 | 0 | 0 |
| scripts/ingest/tests | 250 | 1 | 6 | 17 |
| scripts/pipeline/tests | 154 | 0 | 0 | 2 |

Ca trượt `test_epd_notebook` thiếu `data/student_data/epd.json`. Sáu lỗi thiết lập ở `test_nhap_approval.py` thiếu `data/student_data/orders_enriched.csv`: `test_orders_no_conflict`, `test_pii_defaults`, `test_contract_equivalent`, ba ca `test_load_rejects_decisions`. 17 ca auto_mapping bỏ qua do thiếu student_data/bảng tham chiếu; hai ca pipeline bỏ qua do thiếu snapshot `5bd9a84aaf73` trong warehouse và bản đã publish. Đây là các điều kiện thiếu dữ liệu đã ghi ở lượt trước; không sửa test cũ hoặc chép dữ liệu vào worktree. Toàn bộ 159 test D2 cũng đạt trong lượt hồi quy cuối.

**Chạy lại §6 trên bộ thật.** Dùng root mới `data_demo/kho_d2_luot2`, vì root cũ đã có context `d2-goc`/`d2-dot` và sẽ trả về sớm mà không thực thi code prepare vừa sửa. Đây là thay đổi duy nhất về cách chạy so với lệnh mẫu §6; dữ liệu, run_id, extension và đợt giữ nguyên. Không xóa hoặc sửa kho thử cũ. Mỗi lệnh bên dưới chạy một lần, tuần tự:

```powershell
& D:/retail-analytics/.venv/Scripts/python.exe -B -m scripts.pipeline.cli prepare --run-id d2-goc --root data_demo/kho_d2_luot2 --data D:/retail-analytics-nhap/data --extension orders_enriched
& D:/retail-analytics/.venv/Scripts/python.exe -B -m scripts.pipeline.cli prepare --run-id d2-dot --root data_demo/kho_d2_luot2 --data D:/retail-analytics-nhap/data --extension orders_enriched --dot data_demo/dot_2023
& D:/retail-analytics/.venv/Scripts/python.exe -B -m scripts.pipeline.cli prepare --run-id d2-trung --root data_demo/kho_d2_luot2 --data D:/retail-analytics-nhap/data --extension orders_enriched --dot data_demo/dot_2023 --dot data_demo/dot_2023
& D:/retail-analytics/.venv/Scripts/python.exe -B -m scripts.pipeline.cli forecast --run-id d2-dot --root data_demo/kho_d2_luot2
& D:/retail-analytics/.venv/Scripts/python.exe -B -m scripts.pipeline.cli prepare --run-id d2-theo-id --root data_demo/kho_d2_luot2 --data D:/retail-analytics-nhap/data --extension orders_enriched --snapshot-id 29fdaedea8c8
& D:/retail-analytics/.venv/Scripts/python.exe -B -m scripts.pipeline.cli publish --run-id d2-theo-id --root data_demo/kho_d2_luot2
```

| Lệnh / tình huống | Giây | Exit | Kết quả |
|---|---:|---:|---|
| prepare d2-goc | 19,354 | 0 | prepared, snapshot `47e7cbe765d9` |
| prepare d2-dot | 33,951 | 0 | prepared, snapshot `29fdaedea8c8` |
| Gửi hai lần cùng đợt | 2,100 | 2 | D2-7, mã đợt `635b7f755ba1`, số dòng 1 |
| forecast d2-dot | 1,865 | 2 | `snapshot có đợt chưa dùng được ở stage này (D3, D5)` |
| prepare qua snapshot-id | 2,925 | 0 | prepared, vẫn `29fdaedea8c8` |
| publish d2-theo-id | 1,656 | 2 | Cùng thông báo chặn D3/D5 |

**Đối chiếu artifacts:** mỗi snapshot mới có 17 file; so SHA256 theo đường dẫn tương đối của toàn bộ file thì giống từng byte với snapshot tương ứng ở `data_demo/kho_d2`. Riêng snapshot gốc còn so trực tiếp với bộ artifacts Claude đã dựng bằng `fe1f65c` tại `C:/Users/Win/d2_kiem/kho_so/cu_mo_rong/snapshots/47e7cbe765d9`: đủ 17 file, giống từng byte. Không chạy lại code fe1f65c trong lượt này; đây là đối chiếu với artifacts đối chứng Claude đã lưu.

Số dòng đọc lại từ hai manifest mới:

| Nguồn | Gốc | Có đợt |
|---|---:|---:|
| orders | 646945 | 685033 |
| order_items | 714669 | 755345 |
| payments | 646945 | 685033 |
| shipments | 566067 | 599027 |
| returns | 39939 | 42197 |
| reviews | 113551 | 119930 |
| inventory | 60247 | 65840 |
| web_traffic | 3652 | 4017 |
| promotions | 50 | 71 |
| sales | 3833 | 4198 |
| customers | 121930 | 121930 |
| products | 2412 | 2412 |
| geography | 39948 | 39948 |
| sample_submission | 548 | 548 |

Tất cả khớp kỳ vọng §6. Mở rộng `orders_enriched`: gốc `rows=so_dong_file=646945`, có đợt `rows=so_dong_file=685033`; cả hai `so_dong_cach_ly=0`, `cach_ly={}`. Cách ly không đổi. Các cổng snapshot/extension/contract đều đạt trong hai prepare.

Phân loại đủ 15 file không đổi: `customers.csv`, `products.csv`, `geography.csv` là `master_khong_doi`, nguồn cùng tên; bảy file `order_items.csv`, `payments.csv`, `returns.csv`, `reviews.csv`, `promotions.csv`, `inventory.csv`, `web_traffic.csv` là `khop_loi`, nguồn cùng tên; `orders_enriched.csv` là `loi_kem_cot_them` → orders; `shipments_realistic.csv` là `loi_kem_cot_them` → shipments; `tf.json`, `epd.json`, `eprom.json` là `chi_de_xuat`, nguồn null. `cot_ngoai` của hai file thêm cột khớp nguyên danh sách A/B ở báo cáo trước trong §9; 13 file còn lại đều `[]`. Đã đọc lại và so toàn bộ manifest, không chỉ so id.

Đợt vẫn `635b7f755ba1`, **Revenue = 1108842415.88, COGS = 992869698.28**. Đây là **số dữ liệu tổng hợp để demo**, không phải kết luận nghiệp vụ hay đối chứng độc lập. SHA256 cả 15 file đầu vào khớp manifest bất biến của lượt trước; hai file hợp đồng bị cấm sửa cũng giữ nguyên hash. Sau ca chặn, thư mục snapshots chỉ có hai snapshot trên, không có thư mục tạm; registry thử có `active=null`, `releases={}`.

**Giới hạn và kết thúc:** chưa chạy lại bộ 81 đột biến của Claude; đã thêm các test T1–T9 để Claude nghiệm thu bằng đúng các đột biến đã nêu. Không sửa lỗi retry `prepare --snapshot-id` đã chuyển D3. Không đổi luật ngoài S1–S5 đã chốt. `git diff --check` đạt, không có file staged. Đã cập nhật §9 và dừng, không commit, không push.

### Claude rà D2 lượt 2, ngày 2026-11-05: code đạt, còn thiếu 2 ca test

Chạy trên đúng code GPT (sha256 ghi đầu `ket_qua.log`), PM chạy ngoài Claude Code; riêng phần đột biến mất 5.567 giây. Bộ kiểm ở `C:\Users\Win\d2_kiem`, ngoài repo. Số Revenue, COGS của đợt là số tổng hợp, không dùng cho kết luận.

| Kiểm | Kết quả |
|---|---|
| Không đợt so với `fe1f65c` | Giống từng byte: mở rộng `47e7cbe765d9` 16 file, 14 nguồn `5bd9a84aaf73` 15 file, `d2-goc` của GPT cũng giống |
| Run `skipped` (S1) | Bốn stage 1,1 giây cả cũ lẫn mới; snapshot đã dọn thì `forecast` vẫn exit 0 cả cũ lẫn mới |
| Đọc độc lập parquet đợt | Đạt hết: `ma_dot`, `snapshot_id` tính lại khớp; dòng gốc y hệt; dòng đợt khớp file từng ô; `sales` khớp phép tính Decimal |
| Ca chặn trên bộ thật | Đạt hết, gồm S2, S3, S4 và S5 (`số dòng=1`); chặn stage, chặn sửa manifest tay, đổi một byte file `chi_de_xuat` đổi `snapshot_id` |
| Ca biên trên fixture | 26/26 đạt, gồm 4 ca lượt 1 trượt |
| Đột biến | 88/90 bị bắt; 21 đột biến sống ở lượt 1 đều đã bị bắt. Sống: `S4 bo regex`, `S4 bo so sanh ep kieu` |

**Hai đột biến sống là thiếu test, không phải lỗi code.** `test_s4_unit_price_excess_scale` chỉ có `0.105`, mà giá này bị cả hai mệnh đề của S4 bắt, nên bỏ một mệnh đề test vẫn đạt. Claude đã chạy thử trên bản sao, cả hai mệnh đề đều có việc: bỏ regex thì `0.100` lọt, bỏ phép so ép kiểu thì `1.5E-2` lọt.

**GPT làm T10, chỉ một việc:** thêm `0.100` và `1.5E-2` vào ca D2-0 của S4, giữ `0.105`. Chỉ sửa `scripts/ingest/tests/test_dot.py`. Chạy lại bộ D2 riêng, cập nhật §9, dừng, không commit. Không cần chạy lại §6 vì code không đổi.

**Chưa kiểm độc lập, sẽ kiểm sau T10 bằng `chay_cuoi.py`:** hồi quy `scripts/demo/tests`, `scripts/ingest/tests`, `scripts/pipeline/tests` và bốn file test `apps` có dùng `scripts.pipeline`, trên bản sao có `data/`. Các số hồi quy hiện vẫn là GPT báo, và GPT chạy khi thiếu dữ liệu nên còn 1 trượt, 6 lỗi thiết lập, 17 bỏ qua. Dự kiến sau khi có `data/` vẫn còn 2 bỏ qua ở pipeline, do bản sao không có snapshot `5bd9a84aaf73` trong warehouse; đó không phải hồi quy. Đột biến `D2-4 bo payments` mất 2.312 giây, các đột biến cùng nhóm 13–23 giây; chưa rõ lý do, có thể máy ngủ. Kết quả "bị bắt" không đổi, sẽ đo lại.

**Đã sửa phiếu theo lượt này:** dòng D2-0 thêm luật S4, dòng D2-8 bỏ cách gọi `_checks` theo S3 (§4.2).

### GPT — hoàn tất T10, ngày 2026-11-05

Làm tại `D:/retail-analytics-nap`, nhánh `nap-ky/myuyen`. Đã đọc mục “Claude rà D2 lượt 2” và thực hiện đúng T10: chỉ sửa `scripts/ingest/tests/test_dot.py`, tham số hóa `test_s4_unit_price_excess_scale` với ba giá trị `0.105`, `0.100`, `1.5E-2`; cả ba giữ kỳ vọng bị từ chối bằng `D2-0`. Giữ nguyên ca `0.105`, không sửa code triển khai hay test khác. Ngoài file test, chỉ thêm báo cáo này vào §9 theo yêu cầu.

Đã chạy bộ D2 riêng tại root worktree:

```powershell
& D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider scripts/ingest/tests/test_dot.py scripts/pipeline/tests/test_snapshot_dot.py -q --tb=short -rs --junitxml=C:/Users/Win/AppData/Local/Temp/d2_t10.xml
```

Kết quả: **161 đạt, 0 trượt/lỗi, 0 bỏ qua**, 142,82 giây, exit 0. Hai ca bổ sung đạt; bộ D2 tăng từ 159 lên 161 ca. Không chạy lại §6 hoặc bộ hồi quy rộng; không chạy bộ đột biến của Claude, không nhận các kiểm đó là đã chạy trong lượt này. Không làm khác T10. `git diff --check` đạt, không có file staged. Giữ nguyên các thay đổi có sẵn trong worktree; không commit, không push. Đã cập nhật §9 rồi dừng.

### Claude kiểm cuối D2, ngày 2026-11-05

**Kết luận: D2 đạt, đã commit từng file (`8febfd0`…`ac61d3a`).** PM chạy `chay_cuoi.py` ngoài Claude Code trên bản sao có dữ liệu thật; Claude đọc log và xác minh lại bước đột biến.

| Kiểm | Kết quả |
|---|---|
| Phạm vi T10 | Chỉ `test_dot.py` đổi. Năm file code và test còn lại giữ đúng hash đã rà. `retail_dbt`, `apps`, `source_contract.py`, `orders_enriched.yml` giống `fe1f65c` |
| Bộ D2 | 161 đạt, 0 trượt, 0 bỏ qua |
| Ba đột biến | Đều bị bắt bằng lỗi test thật: `S4 bo regex` ở ca `0.100`, `S4 bo so sanh ep kieu` ở ca `1.5E-2`, `D2-4 bo payments` ở ca `1-payments` |
| Hồi quy `scripts/demo/tests` | 64 đạt |
| Hồi quy `scripts/ingest/tests` | 276 đạt |
| Hồi quy `scripts/pipeline/tests` | 154 đạt, 2 bỏ qua: chưa có snapshot `5bd9a84aaf73` và chưa có bản publish local trong bản sao, không phải hồi quy |
| Bốn file `apps` gọi pipeline | 284 đạt |

`D2-4 bo payments` lần này mất 12 giây, lần trước 2.312 giây; đột biến và test giống nhau nên nghi do máy bận lúc đó, chưa chứng minh. Chuyển cho D3: `prepare --snapshot-id` cùng `run_id` trên snapshot có đợt báo exit 2 (`cli.py:358`).

## 10. Chỗ phiếu chặt hơn thiết kế (PM đã duyệt 2026-11-04)

1. **Bảng con chỉ được trỏ tới đơn của chính đợt** (D2-4). Thiết kế §4.3 cho phép "đợt + gốc". Trả hàng năm 2023 của đơn 2022 là chuyện có thật, nhưng cho phép thì số kỳ cũ có thể đổi, trái §5 mục 2. Bộ 2023 không có ca này.
2. **`moc` lấy từ `order_date`** thay vì "ngày lớn nhất" chung chung, lý do ở §4.2.
3. **Ngày đặt hàng phải liền nhau** (D2-3), thiết kế chưa có. Lịch sử `sales` không thiếu ngày nào (CLAUDE.md §1), vùng dự báo cũng đòi liền ngày.
4. **Phân loại theo header và sha256, không theo điểm `auto_mapping`.** Thiết kế §4.2 ghi chạy `propose` cho từng file. Lý do: `tf.json`, `epd.json`, `eprom.json` được `propose` nhận về `web_traffic`, `products`, `promotions` (số ở §9 phiếu D1); nếu tin điểm thì đợt sẽ có hai file cùng nguồn. Trang Gửi ở D5 vẫn hiện đề xuất của `propose` để người duyệt xem.
5. **Mọi đợt đều coi là tổng hợp** ở phạm vi 12/12.
6. **`unit_price` của đợt quá 2 số lẻ bị từ chối (D2-0)**, thêm và PM duyệt ngày 2026-11-05. Đường gốc làm tròn âm thầm khi ép kiểu; đợt thì không sửa giá trị bẩn. Bộ thật không có ca này.

**Chuyển cho lát sau, không làm ở D2:** snapshot luôn dựng lại từ bản gốc, nên "đợt đã nạp" ở D2 chỉ là các `--dot` trên cùng dòng lệnh. Số vẫn an toàn vì không có gì cộng dồn giữa các lượt. D5 và T2 phải tự giữ danh sách đợt đã duyệt, truyền đủ theo thứ tự mỗi lần chạy, và quyết định gửi lại là từ chối hay thay đợt cũ.

**Điều kiện ở thiết kế §7** (app chạy chế độ versioned trên registry `ui-nhap`): D2 chỉ tới `prepare`, không có app đọc gì, nên không phụ thuộc. Phải kiểm lại trước khi soạn phiếu D5.
