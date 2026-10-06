# Mở rộng Data Engineering khi có yêu cầu cụ thể

## Quyết định trước khi lắp công nghệ

Ghi nhu cầu business, SLA/freshness, nguồn thật hay replay, volume, ordering, identity, thay đổi schema, retention và khả năng backfill. Chỉ hỏi phần không thể tìm từ repo/source. Kafka phục vụ event stream; Airflow điều phối dependency/retry/backfill. Không bắt buộc thêm cả hai chỉ để tăng số công nghệ.

## Hợp đồng sự kiện và trạng thái

- Chốt business key, event ID/version, event time và processing time; tên partition key phải xuất phát từ ordering cần giữ. Không invent lịch sử delivered/returned từ một CSV snapshot.
- Replay CSV là mô phỏng, cần manifest/run ID riêng; giữ raw và snapshot tái hiện deck. Nguồn sự kiện mới không được thay bộ expected của snapshot cũ.
- Dedup/idempotent merge dựa trên identity bền vững; cùng event hai lần không đổi kết quả. Source-row mapping hiện tại phải được nâng cấp khi nguồn thay đổi, không gán lại bằng ROW_NUMBER mỗi lần chạy.
- Late event sửa đúng kỳ nghiệp vụ: delivered → returned có thể làm R thay đổi ở ngày đặt hàng gốc theo hợp đồng đề tài. Định nghĩa cửa sổ xử lý, replay phần ngoài cửa sổ và chính sách retraction rõ ràng.
- SCD2 chỉ dùng khi có thay đổi thuộc tính được capture; lookup theo thời điểm thích hợp, distinct khách theo durable ID, không theo số phiên bản dimension.

## Vận hành và kiểm chứng

Thiết kế DAG/task theo dependency dữ liệu, retry hữu hạn, timeout, checkpoint, quarantine/DLQ khi cần, log và cảnh báo có người xử lý. Backfill chạy trong vùng riêng rồi quality gate/publish, không ghi đè consumer giữa chừng. Giữ một scheduler chịu trách nhiệm cho mỗi chuỗi thay vì hai scheduler tranh chạy cùng job.

Test event trùng, out-of-order, late event, restart giữa chừng, schema drift, nguồn lỗi và replay cùng manifest. So incremental với full rebuild trên cùng trạng thái nguồn. Đo freshness và throughput nếu yêu cầu; không gọi luồng là realtime chỉ vì dùng Kafka.

Khi workflow Kafka/Airflow đã có code và nhu cầu lặp lại rõ, tách skill chuyên biệt từ reference này; giữ metric/grain ở nguồn nghiệp vụ chung.
