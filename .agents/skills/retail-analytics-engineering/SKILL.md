---
name: retail-analytics-engineering
description: "Xây hoặc sửa dbt staging, fact, dimension, reporting và kiểm thử Retail Analytics. Dùng khi thay đổi mô hình dữ liệu, SQL nghiệp vụ, join hoặc khả năng lọc/tổng hợp KPI."
---

# Analytics Engineering cho Retail DWH

## Nguồn chuẩn

Đường dẫn repo tính từ root. Đọc `AGENTS.md`, `CLAUDE.md`, `docs/agent_workflows.md`; sau đó đọc phần liên quan của `docs/star_schema.md`, model YAML/SQL và test hiện tại. Dùng `retail-metric-design` nếu yêu cầu đổi định nghĩa chưa rõ.

## Quy trình thay đổi

1. Xác định grain, key, measure, dimensions và downstream bị ảnh hưởng trước khi sửa SQL. Mở rộng đúng tầng staging → intermediate → marts → reporting; nghiệp vụ nằm trong dbt, app đọc kết quả.
2. Giữ thứ tự nguồn để tái dựng line_number. Không dedup theo `(order_id, product_id)`; không dùng ROW_NUMBER không có thứ tự bền vững khi replay/incremental. Preserve values, chỉ thêm cờ outlier khi được yêu cầu.
3. Kiểm join cardinality và fan-out: bridge promotion có thể nhân dòng; dùng semi-join/EXISTS cho lọc, hoặc allocation được chốt cho phân bổ. Không chọn DISTINCT để che join sai.
4. Với KPI, áp dụng hợp đồng trong `docs/star_schema.md`: R/G và delivered, distinct N/C, tỷ lệ từ tử/mẫu, NULL khi mẫu số 0, PS5 không cộng ba chiều. Query bộ lọc động phải tính từ detail đúng tập, có cùng ngữ nghĩa với reporting.
5. Viết test gắn với rủi ro thay đổi: keys/FK/not_null, source-row conservation, reconciliation, phép tổng hợp và kỳ/nhóm biên. Dùng [hướng dẫn quality gate](references/quality.md); không chỉ test lại cùng biểu thức của model.
6. Dùng adapter dispatch/macro cho khác biệt SQL; đọc macro hiện hành trước khi thêm nhánh. Không suy ra Snowflake/Databricks PASS từ compile hoặc kết quả PostgreSQL/DuckDB.

## Chạy và bàn giao

Lấy lệnh, dependencies và target hiện tại từ repo. Chạy test/model liên quan, rồi build phần downstream bị ảnh hưởng khi cần. Chỉ chạy ingest/full refresh khi cần và thuộc phạm vi được giao; ingest hiện tại có thể thay raw và dependency views.

Ghi chính xác backend, nguồn/snapshot, phiên bản code, lệnh, artifact/result và test chưa chạy. dbt FAIL không tự rollback bảng đã materialize: chỉ publish một version đã qua gate. Hoàn thành khi có đối soát độc lập và phần hồi quy phù hợp; cập nhật tài liệu/notebook khi thay định nghĩa hoặc kết luận dữ liệu.
