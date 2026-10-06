---
name: retail-metric-design
description: "Thiết kế KPI, grain và tiêu chí nghiệm thu cho Retail Analytics khi thêm câu hỏi nghiệp vụ, measure hoặc chiều phân tích. Dùng trước khi thay đổi định nghĩa số trên dbt, BI hay chat."
---

# Thiết kế metric từ nghiệp vụ

## Đọc đúng ngữ cảnh

Các đường dẫn `docs/`, `retail_dbt/`, `notebooks/` trong skill tính từ root repository, không từ thư mục skill. Đọc `AGENTS.md`, `CLAUDE.md` và `docs/agent_workflows.md`; dùng bảng nguồn chuẩn trong tài liệu cuối để tìm định nghĩa hiện hành. Đọc phần liên quan của `docs/star_schema.md`, YAML và SQL reporting; không cần đọc toàn bộ kho tài liệu.

## Quy trình

1. Nêu người dùng cần quyết định gì, ví dụ một đơn/dòng hàng và ý nghĩa của một dòng đầu ra. Tìm metric đã có trước khi tạo metric mới.
2. Phân biệt câu hỏi chưa rõ với thông tin có thể tự tìm. Nếu người dùng nói “doanh thu” mà ngữ cảnh không xác định R hay G, hỏi rõ hoặc trình bày cả hai có nhãn; không âm thầm chọn.
3. Viết hợp đồng theo [mẫu](assets/metric_contract.md): tập lọc, thời gian, grain, khóa, dimensions, phép tổng hợp, tử/mẫu, NULL/zero, nguồn, giới hạn và đối chứng.
4. Kiểm tra fan-out, distinct, tỷ lệ và khả năng tổng hợp qua từng chiều. Nghiệp vụ có grain mới cần fact riêng và dimension dùng chung thích hợp. Bộ lọc đa chiều phải tính distinct từ detail ở đúng tập lọc.
5. Dùng hợp đồng KPI ở `docs/star_schema.md` làm chuẩn cho R/G, ngày đặt hàng và trạng thái snapshot. Không đổi nghĩa thành tiền vào theo ngày thanh toán hoặc doanh thu kế toán. Mẫu số 0 cho NULL theo hợp đồng hiện hành; thiếu dữ liệu không tự đổi thành 0.
6. Tách định nghĩa đã thống nhất, đề xuất và quyết định còn thiếu. Chỉ hỏi quyết định business ảnh hưởng kết quả; không hỏi vị trí file hoặc công thức đã có trong repo.

## Bàn giao và hoàn thành

Bàn giao hợp đồng metric cùng danh sách model, notebook, test và trang bị ảnh hưởng. Khi yêu cầu gồm triển khai, tiếp tục bằng `retail-analytics-engineering` và/hoặc `retail-bi-product`; bản hợp đồng không thay thế phần thực thi đã được yêu cầu.

Kết luận mới về dữ liệu phải có cell chứng minh chạy lại được. Thay đổi định nghĩa phải cập nhật bằng chứng và test liên quan; không sửa số đã khóa chỉ để test xanh. Hoàn thành khi metric tính được ở đúng grain, có đối chứng độc lập và không còn quyết định nghiệp vụ trọng yếu chưa rõ.
