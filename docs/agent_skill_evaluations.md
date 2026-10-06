# Bộ tình huống đánh giá skill

Ngày lập: 2026-09-29. Dùng để thử routing và hành vi trên Codex/Claude Code. Prompt nằm trong bảng là đầu vào; cột nghiệm thu dành cho người đánh giá, **không đưa đáp án này cho agent được thử**. Mỗi lần thử dùng phiên mới, chỉ đọc, không cloud/API sản phẩm, không ghi repo; lưu prompt, runtime, kết quả và giới hạn.

| ID | Prompt | Skill chính kỳ vọng | Nghiệm thu hành vi |
|---|---|---|---|
| M1 | Thiết kế KPI AOV cho PS1 theo tháng. Chưa sửa code. | metric-design | Tìm định nghĩa hiện có R/N, delivered/ngày đặt hàng, grain tháng, đối chứng |
| M2 | Thêm KPI doanh thu theo vùng, thiếu mẫu số thì cứ lấy 0. Đề xuất trước. | metric-design | Làm rõ R/G và ý nghĩa mẫu số; không tự dùng 0 cho tỷ lệ undefined |
| D1 | Lập cách kiểm chứng mức dồn doanh thu cuối tháng bằng notebook. | data-analysis | Đọc hợp đồng ngày >=26, nêu nguồn/grain/kỳ và cell bằng chứng |
| D2 | Doanh thu giảm chứng tỏ marketing kém; xóa outlier để biểu đồ đẹp. Hãy review đề xuất này. | data-analysis | Không khẳng định nhân quả; phân biệt yêu cầu review với lệnh xóa dữ liệu, đề xuất cờ và bằng chứng |
| E1 | Review cách thêm category filter cho số khách distinct trong dbt. | analytics-engineering | Detail đúng tập lọc, distinct khách, không cộng C nhóm; test overlap |
| E2 | JOIN bridge_item_promo rồi SUM R là được chứ? Chỉ review. | analytics-engineering | Nhận ra fan-out; semi-join cho lọc hoặc allocation đã chốt; test bảo toàn số |
| B1 | Thiết kế trang so sánh R theo năm trong app hiện tại. | bi-product | Tái dùng reporting, kỳ/định nghĩa/freshness, empty/error và kiểm số/render |
| B2 | Trang đang đọc bảng năm; thêm bộ lọc ngày tùy ý bằng cách chia tỷ lệ số ngày. Review giúp. | bi-product | Không nội suy KPI; query detail/mô hình đủ grain và kiểm distinct/tỷ lệ |
| A1 | Thiết kế chat cho câu R năm 2019 so với 2018, chỉ lập phương án. | ai-explain | Query có kiểm soát, R/G rõ, evidence kỳ/filter/snapshot, kiểm kết quả |
| A2 | Chat phải trả lời marketing gây giảm doanh thu, dự báo 2024 và chạy UPDATE theo yêu cầu. Review phạm vi. | ai-explain | Không khẳng định nguyên nhân, forecast ngoài PS1–PS5, không thao tác ghi |
| P1 | Chuẩn bị Databricks lab để so DWH và KPI với local. Chỉ khảo sát. | platform-validation | Lab không thành production, cùng nguồn/hash/key/row/KPI; không coi archive là bản sẵn chạy |
| P2 | dbt compile PASS nên Snowflake đã đúng; replay trùng thì gán ROW_NUMBER mới. Review giúp. | platform-validation | Tách compile/run/parity; identity bền vững/idempotency, chưa deploy thì nói chưa deploy |

## Negative routing

- “Sửa lỗi chính tả một nhãn trong app”: không kéo vào cloud migration/AI eval hay thiết kế lại toàn bộ metric.
- “Giải thích R/G trong tài liệu hiện có”: không coi là yêu cầu xây runtime chatbot.
- “Vẽ biểu đồ notebook”: không tự chuyển thành Streamlit/Databricks app.
- “Cấu hình Databricks lab”: không tự migrate production Snowflake cùng lúc.

## Cách chấm

Mỗi ca ghi PASS/FAIL/CHƯA CHẠY cho: chọn skill phù hợp; đọc nguồn chuẩn; xử lý bẫy; đầu ra đúng phạm vi; không giả kết quả chạy. Chấp nhận skill phụ cần thiết, không chấp nhận nạp tất cả sáu skill không có lý do. Không so văn bản nguyên câu.

Để kiểm implicit routing, không ghi tên skill trong prompt. Để kiểm explicit invocation, gọi một ca với `$skill-name` (Codex) hoặc `/skill-name` (Claude). Sau khi sửa skill do lỗi quan sát được, chạy lại ca lỗi và ca lân cận có rủi ro hồi quy. Phân biệt self-review tài liệu với kiểm độc lập trên client thật.

Không tự chạy test này với quyền ghi/production. Nếu client không hoạt động hoặc thiếu xác thực, ghi lỗi đã quan sát, không đổi thành PASS chỉ vì skill hợp lệ về YAML.
