# Truy vết PS → star schema → kiểm chứng

Nguồn nghiệp vụ chuẩn: [deck updated](presentations/revenue_performance_problem_statement_updated.pptx).
Thiết kế chuẩn duy nhất: [star_schema.md](star_schema.md). Tài liệu này là bản truy vết, không định nghĩa lại một mô hình cạnh tranh.
Bằng chứng chạy lại: [star_schema_validation.ipynb](../notebooks/02_design/star_schema_validation.ipynb).
Cập nhật 2026-09-27.

## 1. Từ câu hỏi nghiệp vụ tới grain

Cả 5 PS nhìn vào bán hàng. Một đơn có nhiều dòng sản phẩm: để phân tích category, giữ
**một dòng hàng trong đơn**; không chỉ giữ một dòng/ngày hoặc một dòng/đơn.
R/G/Q cộng được trên tập dòng rời nhau, nhưng N phải đếm đơn và C phải đếm khách phân biệt ở đúng tập lọc.

| Yêu cầu của deck | Dữ liệu nguyên tử cần giữ | Dimension / trường dùng | Lớp hiện có |
|---|---|---|---|
| PS1: đo đúng doanh thu và phần G−R | quantity, unit_price, discount, trạng thái | date; order_junk.order_status | monthly, yearly |
| PS2: xu hướng và đổi hướng | R theo ngày/tháng/năm | date | monthly, yearly; giai đoạn chưa triển khai |
| PS3: mùa vụ, cuối tháng, T8 lẻ/chẵn | R từng ngày | ngày, tháng, năm, days_in_month | monthly, yearly, august_parity |
| PS4: R = N × U × P, AOV | order_id, quantity, net_amount | date và lọc delivered | yearly |
| PS5: nhóm đóng góp và N = C × F | customer_id, order_id, R từng dòng | product.category; customer.acquisition_channel; customer → geography.region | segment_yearly, yearly |

Tên model trong bảng viết tắt tiền tố `rpt_revenue_`; `august_parity` là `rpt_august_parity`.
Năm chính 2013–2022, YoY năm từ 2014; mọi PS theo **order_date**. Định nghĩa chi tiết và mặt nạ NULL:
[thiết kế §3–4](star_schema.md#3-hợp-đồng-kpi-cùng-định-nghĩa-ở-mọi-công-cụ).

## 2. Vì sao ra lõi một fact và năm dimension liên quan?

- `fact_order_item`: giữ grain (order_id, line_number), giá bán tại giao dịch và measure gốc.
- `dim_date`: phân tích lịch; cùng một lịch cho các vai trò ngày của nghiệp vụ khác.
- `dim_order_junk`: tổ hợp bối cảnh đơn, đặc biệt order_status để phân biệt R/G.
- `dim_product`: category cho PS5 và thuộc tính phục vụ các nhu cầu mở rộng.
- `dim_customer`: khóa khách để đếm C, acquisition_channel để phân tích.
- `dim_geography`: region đi **qua khách**; không có geography_sk trực tiếp trên fact_order_item.

Không chỉ giữ những cột xuất hiện trong PS rồi xóa phần còn lại. Dimension là tài sản dùng chung
của các quy trình nghiệp vụ. Gender, size, color, device_type… ngoài KPI hiện tại vẫn có thể có ý nghĩa
cho phân tích mới; tính hữu dụng phải được đánh giá theo nghiệp vụ đó.

## 3. Không nhầm phạm vi PS với phạm vi toàn warehouse

| Nhóm | Bảng | Cách hiểu đúng |
|---|---|---|
| Lõi hiện tại | fact_order_item + 5 dimension trên | Đủ chi tiết phục vụ cả 5 PS |
| Vòng đời đơn | fact_order | Một đơn; ngày đặt/gửi/giao; kiểm tính nhất quán ở grain đơn |
| Trả/đánh giá | fact_return, fact_review | Sự kiện khác grain, giữ riêng; không trừ refund lần hai khỏi R |
| Tồn kho / web | fact_inventory_snapshot, fact_web_traffic | Nghiệp vụ khác, không ép vào fact bán hàng |
| Khuyến mãi | dim_promotion, bridge_item_promo | M:N; cần quy tắc phân bổ nếu đo doanh thu theo promotion |
| Tổng hợp gross | fact_daily_sales | G thực tế và phần mẫu non-actual; không phải R và không chứng minh forecast đã có |

Bus matrix đúng nghĩa có hàng là **quy trình nghiệp vụ**, không phải PS.
Xem [bus matrix và hợp đồng conformed dimension](star_schema.md#5-bus-matrix-thêm-nghiệp-vụ-bằng-fact-mới).
Một câu hỏi mới không mặc nhiên cần fact mới; một sự kiện/ngrain mới mới là lý do tách fact.
Các fact mới dùng cùng định danh dimension, không tạo các bản customer/product không tương thích.

## 4. Dữ liệu kiểm chứng quyết định thiết kế

| Quyết định | Bằng chứng / phép kiểm | Giới hạn |
|---|---|---|
| Dòng hàng có khóa | (order_id, product_id) lặp; (order_id, line_number) unique trong snapshot | line_number theo thứ tự file không tự ổn định khi replay file khác |
| Surrogate key để tham chiếu dòng | Kiểm PK/FK và EXCEPT ALL hai chiều với CSV | ROW_NUMBER rebuild không là persistent key mapping |
| R đúng quy ước delivered | Tiền từng đơn đối chiếu trực tiếp payments.csv | fact_order.payment_value dẫn xuất từ dòng hàng không là nguồn tiền độc lập |
| G khác R | G ngày đối chiếu sales.csv; tách G−R | fact_daily_sales actual cũng dẫn xuất từ fact_order_item |
| Region qua customer | Kiểm từng dòng region bằng join CSV nguồn | Vùng khách snapshot, không suy diễn lịch sử địa chỉ giao |
| Dimension hiện là Type 1 | Nguồn snapshot không cung cấp chuỗi hiệu lực thuộc tính | Không chứng minh thuộc tính chưa từng đổi; không dựng SCD2 giả |
| Reporting đúng grain | N/C tính từ detail riêng cho tháng/năm; kiểm đầy đủ KPI | Khoảng lọc tùy chọn phải tính lại, không cộng C hay AVG tỷ số |
| Nhiều fact dùng cùng dimension | Kiểm keys/FK; ví dụ fan-out và aggregate trước join | Shared dimension không bảo đảm an toàn khi join detail-detail |

Notebook kiểm chứng mới nối tiếp [data_model.ipynb](../notebooks/02_design/data_model.ipynb),
không thay thế hoặc sửa các kết luận lịch sử trong notebook cũ.

## 5. Mức hoàn thành so với nghiệp vụ

**Đã có trong model local:** 1 view detail và 4 reporting model, không còn là thiết kế chưa có tầng KPI.
Notebook mới kiểm trực tiếp snapshot DuckDB đang có, không chạy lại dbt hoặc xác nhận server production.

**Đã làm (2026-09-27):** bảng CAGR theo giai đoạn (`rpt_revenue_phase`) và điểm đổi hướng (`rpt_revenue_turning_point`) PS2; mốc 4 giai đoạn A–D ở seed `ps2_phases` (`dwh_huong_dan_pm_ba.md` §4); 2026-09-28 thêm tháng đổi hướng do dữ liệu tự tìm (`rpt_revenue_direction_change`, seed `ps2_direction_rule`). Giữ tham số giai đoạn/version phân tích;
không tự quyết ranh giới hoặc thêm dim giai đoạn chỉ để đáp ứng một báo cáo.

**Mở rộng sau:** app code phục vụ PS; triển khai Snowflake có quality/publish gate; sau đó Kafka với
idempotency, khóa bền vững và cập nhật lại kỳ order_date khi trạng thái đổi.
Forecast/SHAP là đề tài mở rộng riêng nếu được chọn, không là điều kiện mặc định để hoàn thành PS1–PS5.
