# Báo cáo giảng viên hướng dẫn: hệ thống dữ liệu tự động hóa (kịch bản demo)

Soạn ngày 2026-10-29 cho buổi gặp giảng viên hướng dẫn. PM cầm theo để demo và báo cáo tình hình. Mỗi ý có chỉ chỗ lấy bằng
chứng: lệnh, file log hoặc tài liệu chi tiết.

## 0. Mục tiêu giảng viên giao và trả lời ngắn

> Thiết kế và triển khai hệ thống xử lý dữ liệu tự động, bao gồm các quy trình thu thập, làm sạch, chuyển đổi, lưu trữ và
> cập nhật dữ liệu. Mục tiêu là đảm bảo dữ liệu được xử lý chính xác, nhất quán và sẵn sàng phục vụ hoạt động phân tích kinh
> doanh, trực quan hóa và dự báo doanh thu.

**Trả lời ngắn.** Hệ thống đã chạy tự động mỗi ngày bằng Airflow. Đầu ra là một bản dữ liệu (release) trên Databricks, và app
phân tích, chat AI, dự báo đều đọc từ bản này. Mỗi lượt đi qua năm bước: `prepare` → `forecast` → `build` → `validate` → `publish`.
Lỗi ở bất kỳ bước nào thì không công bố, app tiếp tục đọc bản cũ đã kiểm chứng. Dữ liệu mới có thêm field (bộ `student_data`)
đã nhận được qua quy trình tiến hóa schema có kiểm soát. Việc đưa bộ này lên Databricks đang chờ hạn mức bảng của bản Free (§3).

## 1. Năm khâu giảng viên yêu cầu: hệ thống làm gì, bằng chứng ở đâu

| Khâu | Hệ thống làm gì | Bằng chứng | Trạng thái |
|---|---|---|---|
| **Thu thập** | Stage `prepare` chụp 14 file nguồn thành snapshot Parquet bất biến: kiểm header, số dòng, số field, SHA-256. Nguồn mới (`orders_enriched`) vào qua hợp đồng phần mở rộng đã duyệt | `docs/automation_batch.md` mục Kiến trúc; `scripts/ingest/extensions/orders_enriched.yml` | Chạy thật |
| **Làm sạch** | Kiểm kiểu, not-null, khóa chính bằng đúng biểu thức của staging. Nguồn lõi doanh thu sai 1 dòng là dừng cả lượt. Nguồn mới thì cách ly dòng bẩn vào `quarantine/`, vượt ngưỡng 1% thì dừng. Không bao giờ tự sửa giá trị bẩn | `docs/automation_batch.md` mục Hợp đồng dữ liệu; `docs/tien_hoa_schema.md` §6 | Chạy thật |
| **Chuyển đổi** | dbt: staging → intermediate → marts (star schema) → reporting, kèm test khóa, quan hệ, đối soát | Lượt tắt P4 trên Databricks: dbt 225/225 node đạt (`docs/giao_viec_auto_mapping_lat4.md` §6) | Chạy thật, local và cloud |
| **Lưu trữ** | DuckDB (local) và Databricks (production). Mỗi lượt dựng schema riêng `r_<release_id>_*`. Registry giữ danh sách bản đã đạt và con trỏ bản đang phục vụ | `cli history --target databricks` | Chạy thật |
| **Cập nhật** | Airflow chạy lúc 08:00 mỗi ngày. Dữ liệu và code không đổi thì bỏ qua (`bo_qua`), đổi thì dựng bản mới. Dữ liệu mới có cấu trúc khác thì đi qua quy trình tiến hóa schema (§2) | `docs/automation_batch.md` mục Airflow Docker | Chạy thật với bộ Datathon. Bộ có nhân viên: đạt local, **chờ quota cloud** |
| **Chính xác, nhất quán** | Cổng `validate`: Revenue/COGS từng ngày khớp `sales.csv`; trên cloud so từng dòng các bảng nghiệp vụ với bản DuckDB cùng snapshot (`cloud_parity`); chặn cột nhạy cảm lọt lên marts/reporting | P4: `cloud_parity: true`, 37 relation được so | Chạy thật |
| **Sẵn sàng phục vụ** | App PS1–PS5, chat AI Explain và trang dự báo đọc cùng một bản đã công bố; stage `forecast` ghi dự báo vào `reporting.rpt_forecast_*` | App Databricks (`docs/databricks_app_van_hanh.md`) | Chạy thật với bộ Datathon. **Chiều nhân viên chưa có trên app/chat** (lát 5) |

## 2. Câu hỏi riêng của giảng viên: dữ liệu mới thêm field hoặc JSON thì sao

Trả lời chi tiết: `docs/tien_hoa_schema.md` §1 và §5. Tóm lại có 4 ý:
1. **Không nạp thẳng.** Hệ thống phát hiện thay đổi và chặn (fail-closed). Sau đó dữ liệu đi qua quy trình: land nguyên bản →
   so schema → máy đề xuất ánh xạ → BA duyệt → nâng hợp đồng → dbt + test → bản ứng viên qua cổng đối soát → công bố hoặc rollback.
2. **Máy đề xuất, người duyệt** (lát 1): `adapters.py` đọc CSV và JSON thành bảng chuỗi; `schema_diff.py` phân loại thay đổi;
   `auto_mapping.py` sinh đề xuất ánh xạ. Máy không bao giờ tự nạp.
3. **Kết quả trên bộ `student_data`:**
   - `orders_enriched`: nhận, thành chiều mới `dim_sales_employee`, gồm 200 nhân viên. Tình trạng hôn nhân và học vấn chỉ nằm ở
     tầng silver, không lên marts/reporting.
   - `epd.json`: từ chối, vì khóa sản phẩm va chạm với `products` mà tên, giá khác. Nạp vào thì COGS lệch.
   - Các file còn lại: lý do nhận hay không nhận ghi ở `docs/tien_hoa_schema.md` §7.
4. **Bộ Datathon không bị ảnh hưởng:** chạy với phần mở rộng tắt thì ra đúng snapshot cũ `5bd9a84aaf73`; lượt tắt trên Databricks
   (P4) qua mọi cổng.

**Lượt bật trên DuckDB (bằng chứng mới nhất, code đang ở `main`):** ⏳ đang chạy, Claude điền số khi xong.

## 3. Báo cáo tình hình: sự cố quota trên Databricks

Kể theo thứ tự này:
1. **Chuyện gì xảy ra.** Ngày 2026-10-28 chạy lượt bật trên Databricks. Bước nạp dừng với lỗi `UC_RESOURCE_QUOTA_EXCEEDED`:
   bản Free cho tối đa 500 bảng mỗi metastore, trong khi đã có 552.
2. **Vì sao.** Mỗi lượt dựng một bộ schema riêng khoảng 80 bảng để có thể rollback, và chưa có quy định dọn bản cũ.
3. **Hệ thống phản ứng đúng thiết kế.** Lượt hỏng không bao giờ được công bố. App và chat vẫn đọc bản cũ `03ad08c0…` đã kiểm
   chứng. Đích rollback vẫn sẵn.
4. **Đã xử lý.** PM duyệt xóa 3 bộ cũ (236 bảng), không xóa bản đang phục vụ và đích rollback.
5. **Phát hiện thêm.** Bảng đã xóa vẫn bị tính quota khoảng 7 ngày, để có thể khôi phục bằng `UNDROP`. Quota hiện là 553/500,
   dự kiến giảm quanh 2026-11-05. Sau đó chạy lại `build` → `validate`, rồi mới công bố.
6. **Bài học, đưa vào việc tiếp theo.** Cần quy định giữ bản: chỉ giữ khoảng 4 bản, và dọn bản cũ trước ít nhất một tuần.

## 4. Những gì chưa có (nói trước)

| Việc | Vì sao chưa | Ghi ở đâu |
|---|---|---|
| Nạp tăng dần (incremental); hiện mỗi lượt dựng lại toàn bộ từ snapshot | Dữ liệu Datathon tĩnh; ưu tiên tính đúng và rollback | `docs/tien_hoa_schema.md` §8 |
| Quy định giữ bản trên cloud | Mới lộ ra qua sự cố quota | §3 ở trên |
| App/chat theo nhân viên bán hàng (lát 5) | Phải chờ DWH có `dim_sales_employee` trên cloud; BA định câu hỏi và metric trước | `docs/tien_hoa_schema.md` §9 bước 6 |
| Streaming (Kafka) | Hoãn theo quyết định 2026-10-11; pipeline chạy batch theo lịch | `docs/kien_truc_pipeline_tong.md` §4 |
| Điều phối không phụ thuộc máy bật | Airflow chạy Docker trên laptop; máy tắt lúc 08:00 thì lỡ lượt, bản đang phục vụ giữ nguyên | `docs/automation_batch.md` mục Airflow Docker |

## 5. Kịch bản demo (khoảng 15 phút)

| # | Mở gì | Nói gì |
|---|---|---|
| 1 | Sơ đồ ở `docs/automation_batch.md` mục Kiến trúc | Năm stage; lỗi thì giữ bản tốt trước |
| 2 | Airflow UI `http://127.0.0.1:8080`: DAG `retail_batch_pipeline` và lịch sử các lượt | Tự động theo lịch 08:00; mỗi task là một stage |
| 3 | `cli history --target databricks` | Mỗi stage một dòng: đạt, bỏ qua, lỗi (có dòng lỗi quota) |
| 4 | `docs/tien_hoa_schema.md` §1 và báo cáo đề xuất ánh xạ của lát 1 | Trả lời câu hỏi dữ liệu mới thêm field hoặc JSON |
| 5 | Kết quả lượt bật trên DuckDB (§2) | Có chiều nhân viên; cột nhạy cảm bị chặn; số Datathon không đổi |
| 6 | App Databricks: trang Sức khỏe dữ liệu (thẻ "Bản dữ liệu đang phục vụ"), một trang PS, trang dự báo, hỏi chat một câu | Phân tích, trực quan hóa, dự báo đọc cùng một bản đã kiểm chứng |
| 7 | §3 và §4 | Tình hình, sự cố quota, việc tiếp theo |

## 6. Chuẩn bị trước buổi gặp

- Bật Docker Desktop và các container Airflow. **Không bỏ tạm dừng DAG**: nếu bật lại, lượt 08:00 sẽ thấy code mới khác bản
  đang phục vụ, sẽ build lại và trượt quota.
- Trước giờ demo ít nhất 30 phút, bật app Databricks và bấm qua một lượt (`docs/databricks_app_van_hanh.md` §5).
- Xem quota hiện tại (chỉ đọc):

  ```powershell
  databricks resource-quotas get-quota METASTORE f40df823-d715-4524-9564-4b1e8329c927 table-quota --profile retail-dev
  ```

  Nếu `quota_count` khoảng 316, tức đã dưới 500, nhắn Claude "chạy lại P5". Kịp trước buổi gặp thì demo được cả bảng mới trên
  Databricks.
