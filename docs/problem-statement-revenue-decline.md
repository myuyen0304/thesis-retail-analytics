# Phát biểu vấn đề: Tăng trưởng doanh thu & tính bền vững lợi nhuận

> Tham khảo: *Retail Analytics & Forecasting* (tài liệu hướng dẫn VinDatathon 2026 Round 1) —
> cùng bộ dữ liệu với khóa luận này. Tài liệu đề xuất 5 hướng phân tích (D1 Revenue, D2
> Customer, D3 Product, D4 Marketing, D5 Operations) và một bài toán dự báo Revenue/COGS
> (Phần C). Tài liệu này chọn sâu **D1 — Tăng trưởng doanh thu & tính bền vững lợi nhuận**.

## Vì sao chọn D1

Tài liệu tham khảo nói rõ: insight của D1 (Revenue & Profitability) là "điểm để đưa ra các
quyết định thiết kế mô hình" cho bài toán dự báo Revenue/COGS — tức là **phụ thuộc trực
tiếp** vào kết quả phân tích này, không phải một nhánh phụ. Ngoài ra, khóa luận đã có sẵn số
liệu thật từ bước EDA trước đó ([`docs/eda-cau-chuyen-du-lieu.md`](eda-cau-chuyen-du-lieu.md)),
nên problem statement này xây trên dữ liệu thật, không phải giả định suông.

---

## 1. Phát biểu vấn đề (Problem Statement)

**Bối cảnh:** Từ 2012–2022, doanh thu đạt đỉnh năm 2016, sau đó giảm **−38,56%** riêng năm
2019. Trong khi đó, lưu lượng truy cập tăng **+62,7%**, giá bán trung bình tăng **+53,7%**,
nhưng số đơn hàng giảm **−56,2%** và tỷ lệ chuyển đổi sụp từ **1,17% → 0,33%**.

**Vấn đề:** Đây là một nghịch lý — traffic tăng nhưng doanh thu giảm. Cơ chế bù đắp bằng giá
(AOV +50,7%) có vẻ không đủ bù cho sự sụp đổ về khối lượng giao dịch. Chưa rõ đây là (a)
chiến lược premiumization có chủ đích, (b) phễu chuyển đổi hỏng, hay (c) thị trường bão hòa
khiến chỉ còn nhóm khách sẵn sàng trả giá cao ở lại.

**Mục tiêu:** Xác định nguyên nhân gốc rễ của nghịch lý này, lượng hóa vai trò của từng yếu tố
(giá, chuyển đổi, tần suất mua, chế độ theo thời gian), để (a) đề xuất hành động kinh doanh,
và (b) rút ra giả định nền tảng cho pipeline dự báo Revenue/COGS 548 ngày.

**Phạm vi:** `sales.csv` (grain=ngày), `order_items`+`orders` (grain=dòng hàng), `web_traffic`
(grain=ngày), 2012–2022 làm train, suy luận áp dụng cho test 2023–2024.

---

## 2. Câu hỏi nghiên cứu — theo 4 cấp

| Cấp | Câu hỏi |
|---|---|
| Descriptive | Revenue, số đơn, AOV, traffic, conversion đã thay đổi ra sao qua 11 năm? Đỉnh và đáy ở đâu? |
| Diagnostic | Sụt giảm doanh thu đến từ **giảm khối lượng** hay **giảm giá trị mỗi giao dịch**? |
| Diagnostic | Ba/bốn giai đoạn (2012–13, 2014–18, 2019, 2020–22) có thật sự là các *chế độ* (regime) khác biệt về thống kê, hay chỉ là nhiễu? |
| Predictive | Nếu xu hướng hiện tại tiếp diễn, Revenue 2023–2024 giảm tiếp, đi ngang, hay phục hồi? |
| Prescriptive | Nên ưu tiên sửa phễu chuyển đổi, kiểm soát giá, hay giữ nguyên chiến lược? |

---

## 3. Giả thuyết — mỗi giả thuyết gắn một phép kiểm cụ thể

| # | Giả thuyết | Cách kiểm định | Bằng chứng đã có |
|---|---|---|---|
| H1 | Sụt giảm doanh thu chủ yếu do **giảm số lượng đơn** (volume effect), không phải giảm giá trị đơn | Phân rã ΔRevenue = ΔOrders×AOV + Orders×ΔAOV | Orders −56,2% >> AOV +50,7% → volume effect áp đảo |
| H2 | Conversion rate suy giảm **nhanh hơn** tốc độ traffic tăng, khiến hiệu suất marketing ròng âm | So %Δtraffic vs %Δconversion vs %Δorders | Traffic +62,7%, conversion giảm 71,8% (1,17%→0,33%) |
| H3 | Tồn tại ≥3 chế độ (regime) khác biệt về mean/variance, không phải một chuỗi dừng duy nhất | So sánh phân phối Revenue giữa các era (histogram/ANOVA) | Tài liệu tham khảo đã xác nhận 3 phân phối không chồng lấp |
| H4 | Hình dạng mùa vụ ổn định qua các regime, chỉ **mức (level)** thay đổi | Chuẩn hóa revenue tháng về [0,1] mỗi năm, đo correlation hình dạng giữa các năm | Tài liệu tham khảo xác nhận |
| H5 | Giá tăng là **phản ứng bù đắp** cho volume giảm, không phải nguyên nhân gây giảm | Đối chiếu %Δprice với %Δquantity theo năm | Quantity/đơn gần như đứng yên (~4,49) trong khi giá tăng mạnh → ủng hộ H5 |

---

## 4. Measures — độ đo thô (tổng hợp trực tiếp một cột, chưa so sánh)

| Measure | Công thức | Nguồn | Grain |
|---|---|---|---|
| Daily Revenue | `SUM(quantity × unit_price)` | order_items → order_date | Ngày |
| Daily COGS | `SUM(quantity × products.cogs)` | order_items ⋈ products | Ngày |
| Order Count | `COUNTD(order_id)` | orders | Ngày |
| Session Count | `SUM(sessions)` | web_traffic | Ngày |
| Units Sold | `SUM(quantity)` | order_items | Ngày |
| Avg Unit Price | `AVG(unit_price)` | order_items | Ngày |

---

## 5. Metrics — chỉ số dẫn xuất (kết hợp ≥2 measure, có ngữ cảnh)

| Metric | Công thức | Trả lời cho |
|---|---|---|
| Gross Margin % | `(Revenue−COGS)/Revenue×100` | RQ1, H3 |
| AOV | `Revenue / Order Count` | H1 |
| Conversion Rate | `Order Count / Session Count × 100` | H2 |
| Revenue CAGR | `(Rev_2022/Rev_2013)^(1/9) − 1` | RQ1 |
| Volume Effect | `ΔOrders × AOV_kỳ_trước` | H1 |
| Price Effect | `ΔAOV × Orders_kỳ_trước` | H1, H5 |
| Seasonal Shape Correlation | `corr(rev_tháng chuẩn hóa năm A, năm B)` | H4 |

**Khác biệt Measure vs Metric:** Measure là một con số thô (một `SUM`, một `COUNT`) — tự nó
không nói lên điều gì tốt hay xấu. Metric là phép **tính có ngữ cảnh** trên ≥2 measure (tỷ lệ,
delta, tốc độ) — bắt đầu trả lời câu hỏi phân tích, nhưng vẫn chưa gắn mục tiêu kinh doanh.

---

## 6. KPI — metric gắn mục tiêu, có ngưỡng, dùng để giám sát

| KPI | Công thức | Ngưỡng đề xuất | Khi lệch → hành động |
|---|---|---|---|
| Revenue CAGR | như trên | ≥ 0% | Âm liên tục 2 năm → review chiến lược giá/kênh |
| Gross Margin % | như trên | ≥ 18% | Dưới 14% → đặt floor price cho khuyến mãi |
| Conversion Rate | như trên | ≥ 0,8% | Tiếp tục giảm → audit phễu UX |
| AOV Growth / \|Order Decline\| | `%ΔAOV / \|%ΔOrders\|` | ≥ 1,0 | Dưới 1,0 nhiều kỳ → premiumization không bù đủ, cần đổi chiến lược |

**Khác biệt Metric vs KPI:** Không phải Metric nào cũng là KPI. KPI là Metric được **chọn ra**
vì gắn với một mục tiêu chiến lược cụ thể, có ngưỡng cảnh báo và một hành động rõ ràng khi
lệch ngưỡng — nếu không có ngưỡng/hành động thì đó chỉ dừng ở Metric để tham khảo.

> Các con số ngưỡng (18%, 0,8%, 1,0) là đề xuất minh họa dựa trên vùng dao động lịch sử đã
> quan sát — nhóm nên tự hiệu chỉnh lại sau khi chạy số liệu đầy đủ, đừng trích dẫn như số
> cố định.

---

## 7. Nối sang bài toán dự báo

Ba giả thuyết H3, H4, H5 ở trên chính là ba giả định kỹ thuật mà tài liệu tham khảo dùng để
thiết kế mô hình dự báo:

- **H3** → cần sample weighting + calibration theo regime
- **H4** → dùng Fourier seasonality
- **H5** → không dự báo COGS qua tỷ số cố định, vì margin không ổn định ở Q3 năm lẻ

Đây là mạch nối tự nhiên: phân tích D1 xong thì có sẵn lý do kỹ thuật cho từng quyết định ở
chương xây dựng mô hình dự báo Revenue/COGS.
