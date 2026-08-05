# Data Dictionary — Datathon 2026 Round 1

**Miền dữ liệu:** thương mại điện tử thời trang (thị trường Việt Nam), 14 file CSV.
**Khoảng thời gian lịch sử:** 2012-07-04 → 2022-12-31.
**Bài toán:** dự báo `Revenue` và `COGS` theo ngày cho 2023-01-01 → 2024-07-01 (548 ngày).

Mọi con số dưới đây được kiểm chứng trực tiếp trên file, không suy đoán.

---

## 0. Tổng quan các bảng

| File | Số dòng | Grain (1 dòng = ?) | Khóa chính | Vai trò |
|---|---:|---|---|---|
| `sales.csv` | 3,833 | 1 ngày | `Date` | **Target — chuỗi cần dự báo** |
| `sample_submission.csv` | 548 | 1 ngày | `Date` | Format nộp bài |
| `orders.csv` | 646,945 | 1 đơn hàng | `order_id` | Fact — header đơn hàng |
| `order_items.csv` | 714,669 | 1 dòng sản phẩm trong đơn | `(order_id, product_id)`¹ | Fact — chi tiết đơn |
| `payments.csv` | 646,945 | 1 đơn hàng | `order_id` | Fact — thanh toán (1:1 với orders) |
| `shipments.csv` | 566,067 | 1 đơn hàng | `order_id` | Fact — vận chuyển (subset của orders) |
| `returns.csv` | 39,939 | 1 dòng trả hàng | `return_id` | Fact — trả hàng |
| `reviews.csv` | 113,551 | 1 đánh giá | `review_id` | Fact — đánh giá sản phẩm |
| `inventory.csv` | 60,247 | 1 sản phẩm × 1 tháng | `(snapshot_date, product_id)` | Fact — snapshot tồn kho cuối tháng |
| `web_traffic.csv` | 3,652 | 1 ngày | `date` | Fact — traffic website |
| `customers.csv` | 121,930 | 1 khách hàng | `customer_id` | Dimension |
| `products.csv` | 2,412 | 1 SKU | `product_id` | Dimension |
| `geography.csv` | 39,948 | 1 mã zip | `zip` | Dimension |
| `promotions.csv` | 50 | 1 chương trình KM | `promo_id` | Dimension |

¹ Có **16 cặp `(order_id, product_id)` trùng lặp** (714,669 dòng vs 714,653 cặp distinct) — cần `groupby` hoặc thêm surrogate key khi join. Không ảnh hưởng đến tổng hợp doanh thu.

---

## 1. `sales.csv` — TARGET

Chuỗi thời gian cần dự báo. **Không có ngày trống**: 3,833 ngày liên tục = đúng số ngày distinct trong `orders.order_date`.

| Cột | Kiểu | Mô tả |
|---|---|---|
| `Date` | date | Ngày giao dịch. `2012-07-04` → `2022-12-31` |
| `Revenue` | float | Doanh thu **gộp** trong ngày |
| `COGS` | float | Giá vốn hàng bán trong ngày |

### ⚠️ Công thức tái tạo — đã kiểm chứng khớp 100% trên cả 3,833 ngày

```
Revenue(d) = Σ  order_items.quantity × order_items.unit_price
COGS(d)    = Σ  order_items.quantity × products.cogs
```
với tổng lấy trên **mọi `order_items` thuộc đơn có `orders.order_date = d`**.

Ba điểm cực kỳ quan trọng:

1. **`discount_amount` KHÔNG bị trừ.** `Revenue` là doanh thu gộp theo giá niêm yết trên dòng đơn. (Giả thuyết "net = qty×price − discount" lệch ở 1,707/3,833 ngày — chính là các ngày có khuyến mãi; giả thuyết "gross" lệch 0 ngày, sai số tối đa 0.0000.)
2. **KHÔNG lọc theo `order_status`.** Đơn `cancelled` (59,462 đơn, ~9.2%) vẫn được tính vào doanh thu.
3. **KHÔNG trừ hàng trả về.** `returns.refund_amount` không tác động tới `sales.csv`.

Sai số kiểm chứng: `Revenue` max diff = 0.0000, `COGS` max diff = 0.0000 trên toàn bộ chuỗi.

> **Hệ quả cho modeling:** bạn có thể tái tạo target ở mức chi tiết bất kỳ — theo category, region, kênh, phân khúc khách hàng — rồi dự báo từng thành phần và cộng lại (hierarchical / bottom-up forecasting). Đây là lợi thế lớn so với chỉ dùng `sales.csv`.

---

## 2. `sample_submission.csv` — Format nộp bài

| Cột | Kiểu | Mô tả |
|---|---|---|
| `Date` | date | `2023-01-01` → `2024-07-01`, 548 ngày liên tục |
| `Revenue` | float | Giá trị dự báo (file mẫu chứa giá trị placeholder) |
| `COGS` | float | Giá trị dự báo |

Khoảng dự báo dài **548 ngày (~18 tháng)** — horizon rất xa, đòi hỏi mô hình nắm được xu hướng dài hạn và mùa vụ năm, không thể dựa vào lag ngắn.

---

## 3. `orders.csv` — Header đơn hàng

| Cột | Kiểu | Mô tả |
|---|---|---|
| `order_id` | int | **PK**, duy nhất. Miền `1 → 834,397` nhưng chỉ có 646,945 dòng → **khuyết 187,452 giá trị, KHÔNG liên tục**. Không dùng làm biến số học, không suy thứ tự thời gian từ ID |
| `order_date` | date | Ngày đặt hàng. `2012-07-04` → `2022-12-31` |
| `customer_id` | int | **FK →** `customers.customer_id`. 0 giá trị mồ côi |
| `zip` | int | **FK →** `geography.zip`. **100% trùng với `customers.zip`** của khách hàng đó → cột dư thừa |
| `order_status` | enum | Xem phân bố bên dưới |
| `payment_method` | enum | `credit_card`, `cod`, `paypal`, `bank_transfer`, `apple_pay` |
| `device_type` | enum | `desktop`, `mobile`, `tablet` |
| `order_source` | enum | `direct`, `email_campaign`, `organic_search`, `paid_search`, `referral`, `social_media` |

**Phân bố `order_status`:**

| Status | Số đơn | % | Có bản ghi shipment? | Có bản ghi return? |
|---|---:|---:|---|---|
| `delivered` | 516,716 | 79.9% | 516,192 (99.9%) | không |
| `cancelled` | 59,462 | 9.2% | **0** | không |
| `returned` | 36,142 | 5.6% | 36,113 (99.9%) | 36,062 (99.8%) |
| `shipped` | 13,773 | 2.1% | 13,762 (99.9%) | không |
| `paid` | 13,577 | 2.1% | **0** | không |
| `created` | 7,275 | 1.1% | **0** | không |

Trạng thái tuân theo vòng đời hợp lý: `created → paid → shipped → delivered → returned`, nhánh `cancelled`. Chỉ đơn đã `shipped` trở đi mới có bản ghi vận chuyển; chỉ đơn `returned` mới có bản ghi trả hàng (100% các dòng `returns` đều trỏ tới đơn `returned`).

---

## 4. `order_items.csv` — Chi tiết dòng đơn

| Cột | Kiểu | Null | Mô tả |
|---|---|---:|---|
| `order_id` | int | 0 | **FK →** `orders.order_id` |
| `product_id` | int | 0 | **FK →** `products.product_id`. 0 giá trị mồ côi |
| `quantity` | int | 0 | Số lượng |
| `unit_price` | float | 0 | Giá bán thực tế tại thời điểm đặt. **Chỉ 3/714,669 dòng trùng khớp tuyệt đối với `products.price`** (tỷ lệ trung vị `unit_price/price` = 0.982) → giá biến động theo thời gian, `products.price` chỉ là giá tham chiếu hiện tại |
| `discount_amount` | float | 0 | Số tiền giảm giá của dòng. Tổng 749.6 tr trên gross 16,430.5 tr = **4.56%** |
| `promo_id` | str | 438,353 (61.3%) | **FK →** `promotions.promo_id`. 0 mồ côi. → chỉ **38.7%** dòng đơn có khuyến mãi |
| `promo_id_2` | str | 714,463 (99.97%) | Khuyến mãi thứ 2 khi `stackable_flag=1`. Chỉ **206 dòng** có giá trị |

Trung bình ~1.10 dòng sản phẩm/đơn (714,669 / 646,945).

---

## 5. `payments.csv` — Thanh toán

| Cột | Kiểu | Mô tả |
|---|---|---|
| `order_id` | int | **PK / FK →** `orders.order_id`. Quan hệ **1:1** — đúng 646,945 dòng, không trùng |
| `payment_method` | enum | Lặp lại `orders.payment_method` → **dư thừa** |
| `payment_value` | float | **= Σ(`quantity` × `unit_price` − `discount_amount`) của đơn.** Kiểm chứng: 0/646,945 sai lệch |
| `installments` | int | Số kỳ trả góp: `1, 2, 3, 6, 12` |

> Lưu ý: `payment_value` là giá trị **net sau giảm giá** — **khác** với định nghĩa `Revenue` trong `sales.csv` (gross). Đừng dùng `payments` để tái tạo target.

---

## 6. `shipments.csv` — Vận chuyển

| Cột | Kiểu | Mô tả |
|---|---|---|
| `order_id` | int | **PK / FK →** `orders.order_id`, duy nhất. 566,067 dòng = **87.5% đơn hàng** |
| `ship_date` | date | Ngày xuất kho |
| `delivery_date` | date | Ngày giao thành công |
| `shipping_fee` | float | Phí vận chuyển. **Không nằm trong `Revenue`** |

Chỉ tồn tại cho đơn có trạng thái `shipped` / `delivered` / `returned`. Feature khai thác được: `delivery_date − ship_date` (thời gian giao), `ship_date − order_date` (thời gian xử lý) → tương quan với `return_reason = late_delivery`.

---

## 7. `returns.csv` — Trả hàng

| Cột | Kiểu | Mô tả |
|---|---|---|
| `return_id` | str | **PK**, `RET-XXXXXX` |
| `order_id` | int | **FK →** `orders.order_id`. 36,062 đơn distinct → có đơn trả nhiều dòng |
| `product_id` | int | **FK →** `products.product_id` |
| `return_date` | date | Ngày trả |
| `return_reason` | enum | `changed_mind`, `defective`, `late_delivery`, `not_as_described`, `wrong_size` |
| `return_quantity` | int | Số lượng trả |
| `refund_amount` | float | Số tiền hoàn. **Không ảnh hưởng `sales.csv`** |

100% dòng trỏ tới đơn có `order_status = 'returned'`.

---

## 8. `reviews.csv` — Đánh giá

| Cột | Kiểu | Mô tả |
|---|---|---|
| `review_id` | str | **PK**, `REV-XXXXXXX` |
| `order_id` | int | **FK →** `orders.order_id`, 0 mồ côi. 111,369 đơn distinct (**17.2%** đơn có review) |
| `product_id` | int | **FK →** `products.product_id` |
| `customer_id` | int | **FK →** `customers.customer_id` (suy ra được từ `order_id` → dư thừa) |
| `review_date` | date | Ngày đánh giá |
| `rating` | int | 1–5 |
| `review_title` | str | Tiêu đề ngắn (không có phần thân review) |

Grain thực tế = `(order_id, product_id)` duy nhất (113,551 cặp = 113,551 dòng).

---

## 9. `inventory.csv` — Snapshot tồn kho

Grain: **1 sản phẩm × 1 tháng**, chốt vào ngày cuối tháng. 126 tháng (2012-07 → 2022-12), 60,247 dòng.

| Cột | Kiểu | Mô tả |
|---|---|---|
| `snapshot_date` | date | Ngày cuối tháng |
| `product_id` | int | **FK →** `products.product_id` |
| `stock_on_hand` | int | Tồn kho cuối kỳ |
| `units_received` | int | Nhập trong kỳ |
| `units_sold` | int | Bán trong kỳ |
| `stockout_days` | int | Số ngày hết hàng trong tháng, 0–28 |
| `days_of_supply` | float | Số ngày tồn kho đủ bán (max 68,100 → **có outlier cực đoan**) |
| `fill_rate` | float | Tỷ lệ đáp ứng, 0.0667–1. ⚠️ **Cột suy diễn thuần tuý** — xem bên dưới |
| `stockout_flag` | 0/1 | 40,571 dòng = 67.3% |
| `overstock_flag` | 0/1 | 45,942 dòng = 76.3% |
| `reorder_flag` | 0/1 | **Luôn = 0 trên toàn bộ 60,247 dòng → cột vô dụng, loại bỏ** |
| `sell_through_rate` | float | Tỷ lệ bán hết, 0.0004–0.853 |
| `product_name`, `category`, `segment` | str | **Denormalized từ `products`** (khớp 100%) → dư thừa |
| `year`, `month` | int | Tách từ `snapshot_date` → dư thừa |

⚠️ **`fill_rate` = 1 − `stockout_days` / 30, đúng 100% trên cả 60,247 dòng.** Đây là hàm xác định của `stockout_days` chứ không phải phép đo độc lập — chỉ nhận 29 giá trị rời rạc. Dùng đồng thời hai cột này tạo đa cộng tuyến hoàn hảo; giữ một cột là đủ. (Mẫu số cố định 30 bất kể tháng có 28/29/31 ngày — thêm một dấu hiệu dữ liệu được sinh tổng hợp.)

⚠️ `stockout_flag` và `overstock_flag` chồng lấn nhau: **30,495 dòng (50.6%) bật CẢ HAI cờ** cùng lúc — vừa hết hàng vừa tồn kho vượt ngưỡng trong cùng một tháng. Chỉ 4,229 dòng (7.0%) không bật cờ nào. Ngữ nghĩa hai cờ này không loại trừ nhau như tên gọi gợi ý; kiểm tra kỹ trước khi dùng làm feature.

⚠️ `inventory` chỉ phủ **1,624 / 2,412 SKU (67.3%)** → không ghép được tồn kho cho toàn bộ giao dịch.

---

## 10. `web_traffic.csv` — Traffic website

**Đúng 1 dòng/ngày**, 3,652 ngày: `2013-01-01` → `2022-12-31`.

| Cột | Kiểu | Mô tả |
|---|---|---|
| `date` | date | Ngày |
| `sessions` | int | Số phiên |
| `unique_visitors` | int | Khách duy nhất |
| `page_views` | int | Lượt xem trang |
| `bounce_rate` | float | Tỷ lệ thoát (giá trị mẫu ~0.005 — thang đo bất thường, cần kiểm tra) |
| `avg_session_duration_sec` | float | Thời lượng phiên TB (giây) |
| `traffic_source` | enum | ⚠️ **Chỉ 1 dòng/ngày** nên cột này KHÔNG phải phân rã theo nguồn — nó chỉ là nhãn nguồn chiếm ưu thế của ngày đó |

⚠️ **Bẫy lớn:** dữ liệu chỉ có tới 2022-12-31, **thiếu 6 tháng đầu** so với `sales.csv` (2012-07 → 2012-12) và **không có giá trị nào cho kỳ dự báo 2023–2024**. Muốn dùng làm biến ngoại sinh cho test set thì phải tự dự báo nó trước (rủi ro cộng dồn sai số), hoặc chỉ dùng cho phân tích/validation.

---

## 11. `customers.csv` — Dimension khách hàng

| Cột | Kiểu | Mô tả |
|---|---|---|
| `customer_id` | int | **PK**, 121,930 giá trị duy nhất |
| `zip` | int | **FK →** `geography.zip`. 0 mồ côi |
| `city` | str | **Denormalized từ `geography`** → dư thừa |
| `signup_date` | date | `2012-01-17` → `2022-12-31`. ⚠️ **Không đáng tin — xem cảnh báo bên dưới** |
| `gender` | enum | `Female`, `Male`, `Non-binary` |
| `age_group` | enum | `18-24`, `25-34`, `35-44`, `45-54`, `55+` |
| `acquisition_channel` | enum | 6 giá trị, **trùng danh mục với `orders.order_source`** và `web_traffic.traffic_source` |

### 🚨 `signup_date` mâu thuẫn thời gian — 73.80% đơn hàng

**477,453 / 646,945 đơn hàng (73.80%) được đặt TRƯỚC ngày `signup_date` của chính khách hàng đó** — bất khả thi về mặt nghiệp vụ. Nguyên nhân gần như chắc chắn: `signup_date` được sinh ngẫu nhiên độc lập với lịch sử giao dịch, không bị ràng buộc phải sớm hơn đơn đầu tiên.

**Hệ quả — các feature sau KHÔNG dùng được:**
- ❌ Cohort analysis theo tháng đăng ký
- ❌ Thâm niên/tuổi khách hàng tại thời điểm đặt hàng (`order_date − signup_date` âm ở 73.8% trường hợp)
- ❌ Phân biệt khách mới vs khách cũ dựa trên `signup_date`

**Thay thế:** suy trực tiếp từ lịch sử giao dịch — dùng `MIN(orders.order_date)` theo `customer_id` làm mốc "khách hàng xuất hiện lần đầu". Chỉ số này nhất quán về thời gian và tính được hoàn toàn từ `orders`.

Ghi chú thêm: **31,684 khách (26.0%) chưa từng đặt đơn nào**; chỉ 90,246/121,930 khách có giao dịch. Trung bình 7.17 đơn/khách *có giao dịch* (không phải 5.31 nếu chia cho toàn bộ dimension).

---

## 12. `products.csv` — Dimension sản phẩm

| Cột | Kiểu | Mô tả |
|---|---|---|
| `product_id` | int | **PK**, 1 → 2,412, liên tục không đứt đoạn (bảng duy nhất có ID liên tục) |
| `product_name` | str | Tên SKU, ví dụ `DragonWear MA-01`. **Chỉ 2,172 tên distinct / 2,412 dòng — có trùng lặp**, xem cảnh báo bên dưới |
| `category` | enum | `Casual`, `GenZ`, `Outdoor`, `Streetwear`. Doanh thu cực lệch: `Streetwear` chiếm **79.9%** |
| `segment` | enum | `Activewear`, `All-weather`, `Balanced`, `Everyday`, `Performance`, `Premium`, `Standard`, `Trendy`. ⚠️ **KHÔNG lồng hoàn toàn trong `category`** — xem bên dưới |
| `size` | enum | `S`, `M`, `L`, `XL` |
| `color` | str | 10 màu: `black`, `white`, `red`, `blue`, `green`, `yellow`, `orange`, `pink`, `purple`, `silver` |
| `price` | float | Giá niêm yết hiện tại — **không dùng được cho lịch sử** (khớp `unit_price` ở 3/714,669 dòng). Phân bố **hai đỉnh** do lẫn SKU không hoạt động |
| `cogs` | float | **Giá vốn — dùng trực tiếp để tính `COGS` target.** Biên lợi nhuận gộp lý thuyết TB 26.6% *(xem lưu ý)* |

`cogs` là **hằng số theo sản phẩm, không đổi theo thời gian** — đây là lý do `COGS` tái tạo được chính xác tuyệt đối.

### ⚠️ `segment` không phải phân cấp con của `category`

Bảy phân khúc thuộc duy nhất một category, nhưng **`Activewear` xuất hiện ở CẢ `Casual` và `Outdoor`**. Số phân khúc mỗi category cũng không đồng đều:

| `category` | Các `segment` | Số SKU |
|---|---|---:|
| `Streetwear` | `Everyday` (405), `Performance` (347), `Balanced` (306), `Standard` (262) | 1,320 |
| `Outdoor` | `Activewear` (566), `Premium` (177) | 743 |
| `Casual` | `All-weather` (169), `Activewear` (32) | 201 |
| `GenZ` | `Trendy` (148) | 148 |

→ **Không được coi `segment` là chi tiết hoá của `category`** khi làm hierarchical forecasting; hai chiều này giao nhau chứ không lồng nhau. Nếu cần phân cấp thật, phải dùng cặp `(category, segment)`.

### ⚠️ 186 tên SKU bị nhân bản với giá mâu thuẫn — và 814 SKU chết

**186 tên sản phẩm ứng với 426 dòng** (132 tên có 2 bản, 54 tên có 3 bản). Các bản sao **giống hệt nhau ở `category`, `segment`, `size`, `color`** — chỉ khác `price` và `cogs`, chênh nhau tới hàng trăm lần:

| `product_id` | `product_name` | `category` / `segment` / `size` / `color` | `price` | `cogs` | Số dòng trong `order_items` |
|---:|---|---|---:|---:|---:|
| 280 | `LotusWear UE-01` | Streetwear / Performance / S / red | 12,596.85 | 11,967.01 | 120 |
| 380 | `LotusWear UE-01` | Streetwear / Performance / S / red | 34.04 | 21.34 | **0** |

**Tin tốt: không ảnh hưởng target.** Toàn bộ 654 SKU có `price < 100` đều **chưa từng xuất hiện trong `order_items`** → đóng góp đúng **0%** vào cả `Revenue` lẫn `COGS`. Trong mỗi cặp nhân bản, chỉ bản có giá thực mới phát sinh giao dịch.

**Nhưng ảnh hưởng mọi thống kê mô tả về giá.** Bảng chia làm hai quần thể:

| Nhóm | Số SKU | `price` trung vị | Biên LN lý thuyết trung vị |
|---|---:|---:|---:|
| **Hoạt động** (có giao dịch) | 1,598 (66.3%) | 5,505.13 | 19.78% |
| **Không hoạt động** (0 giao dịch) | 814 (33.7%) | 37.21 | 38.97% |

→ **Luôn lọc `product_id IN (SELECT DISTINCT product_id FROM order_items)` trước khi tính bất kỳ thống kê giá/biên lợi nhuận nào.**

**Lưu ý về con số 26.6%:** đây là biên lợi nhuận lý thuyết trung bình trên toàn bộ 2,412 SKU (gồm cả SKU chết). **Biên lợi nhuận gộp thực tế của toàn hệ thống chỉ 13.8%** (`1 − ΣCOGS/ΣRevenue`), vì doanh thu tập trung vào `Streetwear` — danh mục có biên thấp:

| `category` | % doanh thu | Biên LN gộp thực tế |
|---|---:|---:|
| `Streetwear` | 79.92% | 13.24% |
| `Outdoor` | 15.18% | 16.37% |
| `Casual` | 2.80% | 11.75% |
| `GenZ` | 2.09% | 19.13% |

---

## 13. `geography.csv` — Dimension địa lý

| Cột | Kiểu | Mô tả |
|---|---|---|
| `zip` | int | **PK**, 39,948 mã |
| `city` | str | Thành phố (VD: Hai Phong, Phu Ly) |
| `region` | enum | `Central`, `East`, `West` |
| `district` | str | Quận/huyện, dạng `District #N` |

---

## 14. `promotions.csv` — Dimension khuyến mãi

50 chương trình, `2013-01-31` → 2022-11-18.

| Cột | Kiểu | Null | Mô tả |
|---|---|---:|---|
| `promo_id` | str | 0 | **PK**, `PROMO-00XX` |
| `promo_name` | str | 0 | VD `Spring Sale 2013` — có tên mùa vụ, mã hoá được thành feature lịch |
| `promo_type` | enum | 0 | `percentage`, `fixed` |
| `discount_value` | float | 0 | % nếu `percentage`, số tiền nếu `fixed` |
| `start_date` / `end_date` | date | 0 | Khoảng hiệu lực (~30 ngày) |
| `applicable_category` | str | **40 (80%)** | Rỗng = áp dụng cho mọi category |
| `promo_channel` | enum | 0 | `email`, `online`, … |
| `stackable_flag` | 0/1 | 0 | Cho phép cộng dồn KM (tương ứng `order_items.promo_id_2`) |
| `min_order_value` | float | 0 | Giá trị đơn tối thiểu |

Vì `promotions` phủ toàn bộ 2013–2022 với ngày bắt đầu/kết thúc rõ ràng, đây là **nguồn feature lịch tốt nhất** — và là biến ngoại sinh duy nhất có thể *biết trước* nếu đề bài cung cấp lịch KM 2023–2024. Nếu không, ta có thể suy ra chu kỳ lặp hàng năm từ `promo_name`.

---

## Tổng kết chất lượng dữ liệu

**Điểm mạnh**
- Toàn vẹn tham chiếu **hoàn hảo**: 0 khóa ngoại mồ côi trên tất cả các quan hệ đã kiểm tra.
- Hầu như **không có giá trị khuyết**, trừ `promo_id`/`promo_id_2` (khuyết = "không có KM", đúng ngữ nghĩa) và `applicable_category`.
- Target tái tạo được **chính xác tuyệt đối** từ dữ liệu giao dịch.

**Cảnh báo**

Sắp theo mức độ nghiêm trọng:

| # | Vấn đề | Ảnh hưởng |
|---:|---|---|
| 1 | `Revenue` là **gross**, không trừ discount, không lọc `cancelled` | Sai định nghĩa → sai target hoàn toàn |
| 2 | **`customers.signup_date` sau `order_date` ở 73.80% đơn** | Mọi feature cohort/thâm niên/khách-mới đều vô hiệu. Thay bằng `MIN(order_date)` theo khách |
| 3 | `web_traffic` không có dữ liệu 2023–2024 | Không dùng trực tiếp làm biến ngoại sinh cho test |
| 4 | **814/2,412 SKU (33.7%) chưa từng bán**, 654 trong đó có giá bất thường <100 | Bóp méo mọi thống kê giá/biên LN. Phải lọc trước khi phân tích danh mục |
| 5 | 16 cặp `(order_id, product_id)` trùng trong `order_items` | `(order_id, product_id)` **không phải PK hợp lệ**; join bùng nổ dòng nếu không xử lý |
| 6 | **`segment` không lồng trong `category`** (`Activewear` ở cả `Casual` lẫn `Outdoor`) | Sai phân cấp khi làm hierarchical forecasting |
| 7 | `web_traffic` thiếu 6 tháng đầu (2012-H2) | Lệch khoảng thời gian khi join với `sales` |
| 8 | **`inventory.fill_rate` = 1 − `stockout_days`/30 (khớp 100%)** | Cột suy diễn — đa cộng tuyến hoàn hảo, giữ 1 trong 2 |
| 9 | `inventory.stockout_flag` + `overstock_flag` cùng bật ở 50.6% dòng | Ngữ nghĩa hai cờ không loại trừ nhau |
| 10 | `orders.order_id` khuyết 187,452 giá trị (max 834,397 ≠ 646,945 dòng) | ID không liên tục — không dùng làm biến số học |
| 11 | `inventory.reorder_flag` toàn 0 | Loại bỏ |
| 12 | `inventory.days_of_supply` max 68,100 | Outlier cực đoan, cần winsorize |
| 13 | `inventory` chỉ phủ 67.3% SKU | Không ghép được cho toàn bộ giao dịch |
| 14 | `products.price` không phản ánh giá lịch sử | Luôn dùng `order_items.unit_price` |
| 15 | Cột denormalized (`orders.zip`, `inventory.category`, `customers.city`, `payments.payment_method`, `reviews.customer_id`) | Dư thừa — bỏ qua khi build feature |
| 16 | `bounce_rate` ~0.005, biên độ chỉ 0.0032–0.0058 | Thang đo đáng ngờ, gần như hằng số |
| 17 | 31,684 khách (26.0%) chưa từng mua | `customers` không phải tập khách đã giao dịch |

**Dấu hiệu dữ liệu mô phỏng.** Nhiều đặc điểm cho thấy đây không phải dữ liệu vận hành thực: toàn vẹn tham chiếu tuyệt đối (0 mồ côi trên 4,055,881 bản ghi kiểm tra), `quantity` phân bố gần như đều hoàn hảo trên 8 mức (mỗi mức 12.4–12.5%), `fill_rate` là hàm xác định của `stockout_days` với mẫu số cố định 30, các trần cứng về lead time (ship ≤3 ngày, giao ≤7 ngày, trả ≤31 ngày, review ≤40 ngày), và mùa vụ ngược quy luật bán lẻ thời trang (đỉnh tháng 4–6, đáy tháng 11–1). Các kết luận nghiệp vụ rút ra cần diễn giải thận trọng, không khái quát hoá cho thị trường thực.
