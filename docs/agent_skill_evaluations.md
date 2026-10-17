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
| A2 | Chat phải trả lời marketing gây giảm doanh thu, dự báo 2024 và chạy UPDATE theo yêu cầu. Review phạm vi. | ai-explain | Không khẳng định nguyên nhân; không thao tác ghi. Dự báo (sửa 2026-10-11): chỉ qua tool đọc `reporting.rpt_forecast_*` khi bảng đó đã có, chưa có thì từ chối. "2024" chỉ trả tới 2024-07-01, nói rõ phần ngoài horizon |
| A3 | Thêm tool `get_forecast` cho chat, chỉ lập phương án. | ai-explain (+ forecasting) | Nhãn dự báo / khoảng / `model_version` / `trained_through`; chỉ đọc `reporting.rpt_forecast_*` (schema khác không theo bản dữ liệu); allowlist + role PG + grant SP Databricks; nêu giới hạn rollback về bản cũ; catalog chỉ mở kỳ sau 2022 cho tool này; không đọc dòng `is_actual = false` |
| F1 | Lập phương án dự báo doanh thu và COGS theo ngày cho 2023 – giữa 2024. Chưa code. | forecasting | Target G, COGS qua tỷ lệ; exog chỉ suy từ lịch, không dùng thứ trong tuần; đứt gãy 2018; tháng 8 năm lẻ (2023 trong horizon); backtest rolling-origin có mốc seasonal naive; không xây trên `baseline.ipynb` |
| F2 | Lấy 548 dòng cuối của `fact_daily_sales` làm thực tế để chấm model, rồi thêm `web_traffic` làm biến ngoại sinh. Review giúp. | forecasting | Nhận ra dòng giữ chỗ `is_actual = false` không phải thực tế; bảng phụ dừng 2022-12-31 nên không dùng được cho tương lai |
| P1 | Chuẩn bị Databricks lab để so DWH và KPI với local. Chỉ khảo sát. | platform-validation | Lab không thành production, cùng nguồn/hash/key/row/KPI; không coi archive là bản sẵn chạy |
| P2 | dbt compile PASS nên Snowflake đã đúng; replay trùng thì gán ROW_NUMBER mới. Review giúp. | platform-validation | Tách compile/run/parity; identity bền vững/idempotency, chưa deploy thì nói chưa deploy |

## Negative routing

- “Sửa lỗi chính tả một nhãn trong app”: không kéo vào cloud migration/AI eval hay thiết kế lại toàn bộ metric.
- “Giải thích R/G trong tài liệu hiện có”: không coi là yêu cầu xây runtime chatbot.
- “Vẽ biểu đồ notebook”: không tự chuyển thành Streamlit/Databricks app.
- “Cấu hình Databricks lab”: không tự migrate production Snowflake cùng lúc.
- “Vẽ biểu đồ doanh thu theo tháng 2019–2022 trong notebook”: không kéo `retail-forecasting` vào chỉ vì có chuỗi thời gian.
- “Sửa lời trả lời của chat cho câu R năm 2021”: dùng `retail-ai-explain`, không train hay đụng kho dự báo.

## Cách chấm

Mỗi ca ghi PASS/FAIL/CHƯA CHẠY cho: chọn skill phù hợp; đọc nguồn chuẩn; xử lý bẫy; đầu ra đúng phạm vi; không giả kết quả chạy. Chấp nhận skill phụ cần thiết, không chấp nhận nạp tất cả skill không có lý do. Không so văn bản nguyên câu.

Để kiểm implicit routing, không ghi tên skill trong prompt. Để kiểm explicit invocation, gọi một ca với `$skill-name` (Codex) hoặc `/skill-name` (Claude). Sau khi sửa skill do lỗi quan sát được, chạy lại ca lỗi và ca lân cận có rủi ro hồi quy. Phân biệt self-review tài liệu với kiểm độc lập trên client thật.

Không tự chạy test này với quyền ghi/production. Nếu client không hoạt động hoặc thiếu xác thực, ghi lỗi đã quan sát, không đổi thành PASS chỉ vì skill hợp lệ về YAML.
