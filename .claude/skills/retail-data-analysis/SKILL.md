---
name: retail-data-analysis
description: "Phân tích dữ liệu Retail Analytics bằng notebook, kiểm chứng giả thuyết và giải thích biến động có bằng chứng. Dùng cho EDA và kết luận phân tích; không tự mở rộng thành pipeline hoặc forecasting."
---

# Phân tích có bằng chứng

## Đầu vào

Đường dẫn repo tính từ root. Đọc `AGENTS.md`, `CLAUDE.md`, `docs/agent_workflows.md`; tìm notebook liên quan trước khi tạo mới. Đọc định nghĩa KPI trong `docs/star_schema.md` nếu phân tích doanh thu. Cần câu hỏi, kỳ phân tích, nguồn và grain; tự kiểm tra schema/file có sẵn.

## Thực hiện

1. Mở đầu bằng câu chuyện nghiệp vụ, ý nghĩa một dòng và ví dụ giao dịch. Xác định câu hỏi cần kiểm chứng thay vì chạy mọi biểu đồ có thể có.
2. Kiểm nguồn tồn tại, manifest/hash hoặc version snapshot, schema và chất lượng cần cho câu hỏi. Thiếu CSV thì báo nguồn còn thiếu; không sửa đường dẫn root thành đường dẫn máy cá nhân.
3. Giữ source rows và identity. Kiểm cardinality trước/sau join; `(order_id, product_id)` không phải khóa dòng hàng. Dùng `(order_id, line_number)` theo quy tắc tái dựng của repo.
4. Ưu tiên notebook quan sát được khi người dùng cần học/kiểm từng bước. Chạy từ root, Markdown/comment tiếng Việt, định danh mới tiếng Anh. Kiểm quyền sở hữu notebook trong README trước khi sửa; phối hợp nếu notebook đã có người khác phụ trách. Thiếu tên trong bảng không có nghĩa phải xin phép để lập phương án hoặc tạo notebook độc lập trong phạm vi được giao; không chặn việc có thể làm tiếp.
5. Mỗi kết luận đi với code, bảng/biểu đồ và số lượng quan sát. Nêu kỳ thiếu, NULL, mẫu số 0, nhóm nhỏ và giới hạn nguồn khi có ảnh hưởng. Đọc [checklist bằng chứng](references/evidence.md) khi viết kết luận hoặc tài liệu.
6. Outlier là cờ để xem xét; không xóa, clip hoặc thay giá trị giao dịch nếu chưa được yêu cầu. Không biến phân rã N/U/P, C/F hay liên hệ theo ngày thành nguyên nhân, churn hoặc tác động chiến dịch.

## Bàn giao

Lưu notebook chạy hết, kết luận và tài liệu liên quan theo phạm vi yêu cầu. Ghi nguồn/snapshot, lệnh hoặc cách chạy, kiểm tra đã chạy và giới hạn. Kết luận mới trong Markdown phải trỏ tới cell có thể chạy lại.

Nếu thiếu dữ liệu/compute, bàn giao phần phân tích khả thi và ghi rõ phần chưa kiểm; không điền kết quả giả. Forecast/SHAP chỉ làm khi yêu cầu, sau khi kiểm dữ liệu tương lai và leakage; mẫu submission không phải dự báo thật.
