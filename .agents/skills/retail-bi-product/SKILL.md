---
name: retail-bi-product
description: "Phát triển trang phân tích, biểu đồ, bộ lọc và drill-down Retail Analytics. Dùng cho sản phẩm BI đọc DWH và nghiệm thu số trên giao diện; không thay thế skill kỹ thuật Streamlit."
---

# Sản phẩm BI bám câu hỏi nghiệp vụ

## Đầu vào và routing

Đường dẫn repo tính từ root. Đọc `AGENTS.md`, `CLAUDE.md`, `docs/agent_workflows.md`, phần liên quan của `docs/gd2_app_plan.md` và code trang/query hiện tại. Khi sửa Streamlit, đọc `developing-with-streamlit` nếu có; nếu thiếu, kiểm phiên bản cài đặt rồi tra tài liệu Streamlit chính thức tương ứng. Không tự đổi framework hay host.

Kế hoạch app giữ cả lịch sử và bảng đề xuất cũ. Khi thấy quyết định trái nhau, đọc phần bổ sung/correction và §9 đầy đủ, không kết luận từ một dòng grep. Dùng chỉ dẫn mới nhất của người dùng và quyết định mới nhất có liên quan; không hỏi lại lựa chọn đã được chốt, kể cả M6 hoặc AI chat.

## Thực hiện

1. Xác định câu hỏi, người xem, metric và grain của trang. Bố cục hiện hành là câu hỏi → KPI → biểu đồ → cách đọc → giới hạn. Giữ giao diện tiếng Việt, định dạng số Việt và thuật ngữ nghiệp vụ nhất quán.
2. Tìm model reporting đáp ứng câu hỏi. Thiếu KPI thì dùng `retail-analytics-engineering` bổ sung dbt/test, không tính công thức business lại trong UI hoặc hardcode số deck.
3. Bộ lọc phải giữ đúng ngữ nghĩa metric. Nếu bảng năm/tháng không đủ grain cho khoảng ngày hoặc nhiều chiều, bổ sung query detail được kiểm chứng; không cộng distinct C/N hoặc lấy trung bình tỷ lệ đã tổng hợp.
4. Đọc DWH qua lớp connection/query hiện có; giữ kết nối chỉ đọc. Thông tin kỳ phân tích, định nghĩa R/G, snapshot và freshness phải đi cùng số liệu. Không trình bày nguồn lịch sử như realtime.
5. Dùng [checklist UI và nghiệm thu](references/acceptance.md) để chọn trạng thái và test phù hợp. Chỉ thêm khả năng người dùng cần; không nhồi tên adapter, framework hoặc kỹ thuật nội bộ vào luồng chính.

## Bàn giao

Chạy test số liệu/query và AppTest cho trang đổi, kiểm backend liên quan. Chỉ khẳng định đã kiểm nền tảng có lần chạy thật. Chụp ảnh khi môi trường hỗ trợ, ghi rõ nếu mới kiểm headless. Đưa lệnh chạy, nguồn số, ảnh/bằng chứng và giới hạn còn lại.

Khi yêu cầu có AI chat, dùng thêm `retail-ai-explain`; bố trí nguồn/SQL dưới phần mở rộng để người xem kiểm được nhưng không phải đọc SQL mới hiểu câu trả lời.
