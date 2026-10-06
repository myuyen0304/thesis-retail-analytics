# Data Dictionary — Datathon 2026 Round 1

Tài liệu này mô tả hai lớp dữ liệu của project:

1. **Lớp nguồn:** 14 file CSV của bài thi, giữ nguyên cấu trúc được cung cấp.
2. **Lớp quan hệ 3NF:** 19 bảng logic và view `daily_sales` được thiết kế trong
   [`normalized_schema.md`](normalized_schema.md).

Mục tiêu là giúp người đọc trả lời, theo đúng thứ tự:

> **Một dòng đại diện cho cái gì? Khóa của dòng là gì? Dòng đó liên kết với đâu? Mỗi cột có ý nghĩa gì?**

Các con số profiling trong tài liệu được tính trên bộ dữ liệu hiện có tại ngày **2026-08-10**.
Đây là quan sát của snapshot, không phải cam kết rằng dữ liệu tương lai luôn có cùng phân bố.

---

## 1. Câu chuyện nghiệp vụ và quy ước

### 1.1 Câu chuyện vận hành

```text
GEOGRAPHY → CUSTOMER → ORDER → ORDER_ITEM ← PRODUCT
                           │        │
                           │        ├── PROMOTION
                           │        ├── PRODUCT_RETURN
                           │        └── REVIEW
                           ├── PAYMENT
                           └── SHIPMENT

PRODUCT → INVENTORY_SNAPSHOT
DATE    → WEB_TRAFFIC / DAILY_SALES / DAILY_SALES_FORECAST
```

- Khách hàng thuộc một khu vực và đặt đơn hàng.
- Mỗi đơn có từ một đến nhiều dòng hàng; doanh thu và giá vốn phát sinh ở grain dòng hàng.
- Promotion áp dụng cho dòng hàng, không mặc định áp dụng cho toàn đơn.
- Payment và shipment ở grain đơn hàng; return và review ở grain dòng hàng.
- Inventory là snapshot cuối tháng theo sản phẩm.
- Web traffic và sales chỉ có grain ngày, không có khóa nối trực tiếp tới customer, session hay order.

### 1.2 Ký hiệu

| Ký hiệu | Ý nghĩa |
|---|---|
| **Grain** | Một dòng đại diện cho sự kiện/thực thể nào |
| **PK** | Primary Key — định danh duy nhất một dòng |
| **FK** | Foreign Key — tham chiếu tới PK/UK của bảng khác |
| **UK** | Unique Key — khóa ứng viên được ràng buộc unique |
| **GEN** | Cột sinh trong ETL, không tồn tại trong CSV |
| **DERIVED** | Cột tính lại được từ dữ liệu khác |
| **DROPPED** | Không lưu ở lớp 3NF; lý do phải được ghi rõ |
| **VIEW** | Kết quả truy vấn dẫn xuất, không lưu như bảng cơ sở |

`Null nguồn` và `Nullable đích` là hai khái niệm khác nhau. Null nguồn mô tả snapshot CSV;
nullable đích là quyết định constraint của schema.

### 1.3 Quy tắc khóa dòng hàng

`order_items.csv` không có khóa tự nhiên hợp lệ. Có **16 cặp** `(order_id, product_id)` bị lặp,
tương ứng 32 dòng hàng khác nhau về `quantity` hoặc `unit_price`.

Lớp 3NF phải sinh:

```text
line_number = thứ tự dòng ổn định trong từng order_id, bắt đầu từ 1
PK(order_item) = (order_id, line_number)
```

`line_number` là một quy tắc tái dựng có thể chạy lại, **không phải ground truth do nguồn cung cấp**.
`product_return` và `review` phải tham chiếu `(order_id, line_number)`, không được dùng
`(order_id, product_id)` làm FK vì có thể fan-out và tạo cảnh báo giả.

---

## 2. Tổng quan 14 file nguồn

| File | Dòng × cột | Grain | Khóa nguồn | Phạm vi thời gian | Vai trò |
|---|---:|---|---|---|---|
| `customers.csv` | 121.930 × 7 | Một khách hàng | `customer_id` | `signup_date`: 2012-01-17 → 2022-12-31 | Khách hàng |
| `geography.csv` | 39.948 × 4 | Một mã zip | `zip` | Không có cột ngày | Địa lý |
| `products.csv` | 2.412 × 8 | Một SKU/biến thể | `product_id` | Không có cột ngày | Danh mục sản phẩm |
| `promotions.csv` | 50 × 10 | Một đợt promotion | `promo_id` | 2013-01-31 → 2022-12-31 | Khuyến mãi |
| `orders.csv` | 646.945 × 8 | Một đơn hàng | `order_id` | 2012-07-04 → 2022-12-31 | Header giao dịch |
| `order_items.csv` | 714.669 × 7 | Một dòng hàng trong đơn | **Không có** | Theo `orders.order_date` | Chi tiết giao dịch |
| `payments.csv` | 646.945 × 4 | Thanh toán của một đơn | `order_id` | Theo đơn hàng | Thanh toán |
| `shipments.csv` | 566.067 × 4 | Shipment của một đơn | `order_id` | 2012-07-04 → 2022-12-31 | Giao hàng |
| `returns.csv` | 39.939 × 7 | Một event trả dòng hàng | `return_id` | 2012-07-11 → 2022-12-31 | Hậu mãi |
| `reviews.csv` | 113.551 × 7 | Một đánh giá dòng hàng | `review_id` | 2012-07-10 → 2022-12-31 | Hậu mãi |
| `inventory.csv` | 60.247 × 17 | Một sản phẩm tại snapshot cuối tháng | `(snapshot_date, product_id)` | 2012-07-31 → 2022-12-31 | Vận hành kho |
| `web_traffic.csv` | 3.652 × 7 | Traffic tổng hợp của một ngày | `date` | 2013-01-01 → 2022-12-31 | Kênh số |
| `sales.csv` | 3.833 × 3 | Actual sales của một ngày | `Date` | 2012-07-04 → 2022-12-31 | Target lịch sử, dẫn xuất |
| `sample_submission.csv` | 548 × 3 | Một ngày tương lai cần dự báo | `Date` | 2023-01-01 → 2024-07-01 | Format output |

Tổng cộng: **2.960.736 dòng nguồn**. `data/submission.csv` là output do baseline sinh,
không thuộc 14 file nguồn.

---

## 3. Dictionary lớp nguồn

Quy ước type nguồn: `integer`, `float`, `string`, `date`. CSV không tự mang schema;
type dưới đây là type logic sau khi parse, không phải khai báo có sẵn trong file.

### 3.1 `customers.csv`

**Grain:** một khách hàng. **PK:** `customer_id`.

| Cột | Type | Null | Cardinality | Khóa/quan hệ | Ý nghĩa | Xử lý 3NF |
|---|---|---:|---:|---|---|---|
| `customer_id` | integer | 0 | 121.930 | PK | Mã khách hàng | `customer.customer_id` |
| `zip` | integer | 0 | 31.491 | FK → `geography.zip` | Mã zip nơi cư trú | `customer.zip` |
| `city` | string | 0 | 42 | DERIVED qua `zip` | Thành phố của khách | DROPPED; lấy qua `zip_area → city` |
| `signup_date` | date | 0 | 3.941 | — | Ngày đăng ký trong nguồn | `customer.signup_date`; nullable và gắn cảnh báo |
| `gender` | string | 0 | 3 | Domain | `Female`, `Male`, `Non-binary` | `customer.gender` |
| `age_group` | string | 0 | 5 | Domain | Nhóm tuổi: `18-24` … `55+` | `customer.age_group` |
| `acquisition_channel` | string | 0 | 6 | Domain | Kênh thu hút khách | `customer.acquisition_channel` |

`signup_date` không phù hợp để tính tenure/cohort: 73,8% đơn hàng có `order_date` trước ngày này.

### 3.2 `geography.csv`

**Grain:** một mã zip. **PK:** `zip`.

| Cột | Type | Null | Cardinality | Khóa/quan hệ | Ý nghĩa | Xử lý 3NF |
|---|---|---:|---:|---|---|---|
| `zip` | integer | 0 | 39.948 | PK | Mã vùng chi tiết | `zip_area.zip` |
| `city` | string | 0 | 42 | FK logic | Thành phố | `city.city`; FK trong `zip_area` |
| `region` | string | 0 | 3 | Domain | `Central`, `East`, `West` | `region.region`; FK của `city` và `district` |
| `district` | string | 0 | 39 | FK logic | Quận/khu vực | `district.district`; FK trong `zip_area` |

`city` và `district` đều roll-up về `region` nhưng cắt chéo nhau; không tồn tại cây duy nhất
`region → city → district → zip`. Mô hình 3NF chọn bốn bảng và cần ETL kiểm hai đường tới
`region` luôn nhất quán.

### 3.3 `products.csv`

**Grain:** một SKU/biến thể. **PK:** `product_id`.

| Cột | Type | Null | Cardinality | Khóa/quan hệ | Ý nghĩa | Xử lý 3NF |
|---|---|---:|---:|---|---|---|
| `product_id` | integer | 0 | 2.412 | PK | Mã SKU | `product.product_id` |
| `product_name` | string | 0 | 2.172 | FK logic | Tên model sản phẩm | `product_model.product_name`; FK trong `product` |
| `category` | string | 0 | 4 | FD từ `product_name` | `Casual`, `GenZ`, `Outdoor`, `Streetwear` | `product_model.category` |
| `segment` | string | 0 | 8 | FD từ `product_name` | Phân khúc sản phẩm | `product_model.segment` |
| `size` | string | 0 | 4 | Thuộc tính SKU | `S`, `M`, `L`, `XL`; FD theo `product_name` chỉ đúng trên snapshot | `product.size` |
| `color` | string | 0 | 10 | Thuộc tính SKU | Màu biến thể; FD theo `product_name` chỉ đúng trên snapshot | `product.color` |
| `price` | float | 0 | 1.990 | Snapshot | Giá niêm yết hiện tại | `product.list_price` |
| `cogs` | float | 0 | 2.381 | Snapshot | Giá vốn đơn vị theo dataset | `product.unit_cogs` |

`products.price`/`cogs` không có effective date, nên không thể dựng lịch sử SCD Type 2.
654 SKU có `price < 100` chưa từng được bán; đây là cờ chất lượng dữ liệu, không phải dimension phân tích.

### 3.4 `promotions.csv`

**Grain:** một đợt promotion. **PK:** `promo_id`; `promo_name` là UK trong snapshot.

| Cột | Type | Null | Cardinality | Khóa/quan hệ | Ý nghĩa | Xử lý 3NF |
|---|---|---:|---:|---|---|---|
| `promo_id` | string | 0 | 50 | PK | Mã promotion | `promotion.promo_id` |
| `promo_name` | string | 0 | 50 | UK | Tên chương trình | `promotion.promo_name` |
| `promo_type` | string | 0 | 2 | Domain | `fixed` hoặc `percentage` | `promotion.promo_type` |
| `discount_value` | float | 0 | 6 | — | Giá trị giảm theo `promo_type` | `promotion.discount_value` |
| `start_date` | date | 0 | 50 | — | Ngày bắt đầu | `promotion.start_date` |
| `end_date` | date | 0 | 50 | CHECK | Ngày kết thúc, phải ≥ `start_date` | `promotion.end_date` |
| `applicable_category` | string | 40 | 2 | FK logic nullable | Category áp dụng; null nghĩa là không giới hạn category | `promotion.applicable_category` |
| `promo_channel` | string | 0 | 5 | Domain | Kênh áp dụng | `promotion.promo_channel` |
| `stackable_flag` | integer 0/1 | 0 | 2 | Domain | Cờ cho phép kết hợp | `promotion.stackable_flag` boolean |
| `min_order_value` | integer | 0 | 5 | — | Ngưỡng giá trị đơn ghi trong định nghĩa promo | `promotion.min_order_value` |

Promotion tương lai sau 2022 không có trong nguồn. Urban Blowout 2023 là giả định forecasting,
không phải feature ngoại sinh đã biết.

### 3.5 `orders.csv`

**Grain:** một đơn hàng. **PK:** `order_id`.

| Cột | Type | Null | Cardinality | Khóa/quan hệ | Ý nghĩa | Xử lý 3NF |
|---|---|---:|---:|---|---|---|
| `order_id` | integer | 0 | 646.945 | PK | Mã đơn hàng | `order.order_id` |
| `order_date` | date | 0 | 3.833 | — | Ngày đặt đơn | `order.order_date` |
| `customer_id` | integer | 0 | 90.246 | FK → `customers` | Khách đặt đơn | `order.customer_id` |
| `zip` | integer | 0 | 29.932 | Bản sao | Trùng `customers.zip` qua `customer_id` ở 100% dòng | DROPPED |
| `order_status` | string | 0 | 6 | Domain | Lifecycle: `created`, `paid`, `shipped`, `delivered`, `returned`, `cancelled` | `order.order_status` |
| `payment_method` | string | 0 | 5 | Domain | Phương thức thanh toán | `order.payment_method` |
| `device_type` | string | 0 | 3 | Domain | `desktop`, `mobile`, `tablet` | `order.device_type` |
| `order_source` | string | 0 | 6 | Domain | Kênh phát sinh đơn | `order.order_source` |

`orders.zip` không phải ship-to address độc lập. Nó bằng địa chỉ khách hàng trên toàn bộ snapshot.

### 3.6 `order_items.csv`

**Grain:** một dòng hàng trong đơn. **Khóa nguồn:** không có. **Khóa đích:**
`(order_id, line_number)` sau khi sinh `line_number`.

| Cột | Type | Null | Cardinality | Khóa/quan hệ | Ý nghĩa | Xử lý 3NF |
|---|---|---:|---:|---|---|---|
| `order_id` | integer | 0 | 646.945 | FK → `orders` | Đơn chứa dòng hàng | `order_item.order_id` |
| `product_id` | integer | 0 | 1.598 | FK → `products` | SKU được bán | `order_item.product_id` |
| `quantity` | integer | 0 | 8 | CHECK > 0 | Số lượng bán | `order_item.quantity` |
| `unit_price` | float | 0 | 501.330 | — | Giá bán đơn vị tại thời điểm giao dịch | `order_item.unit_price` |
| `discount_amount` | float | 0 | 204.449 | CHECK ≥ 0 | Tổng giảm giá của dòng hàng | `order_item.discount_amount` |
| `promo_id` | string | 438.353 | 50 | FK → `promotions` | Promotion thứ nhất nếu có | Unpivot → `order_item_promotion.promo_id` |
| `promo_id_2` | string | 714.463 | 2 | FK → `promotions` | Promotion thứ hai nếu có | Unpivot → `order_item_promotion.promo_id` |
| `line_number` | GEN | — | 1–5/đơn | PK bộ phận | Thứ tự nguồn ổn định trong đơn | `order_item.line_number` |

Sau unpivot có **276.522** liên kết promotion: 276.316 từ `promo_id` và 206 từ `promo_id_2`.
Không có dòng nào có hai promo trùng mã hoặc có `promo_id_2` mà thiếu `promo_id`.

### 3.7 `payments.csv`

**Grain:** thanh toán tổng hợp của một đơn. **PK/FK:** `order_id`.

| Cột | Type | Null | Cardinality | Khóa/quan hệ | Ý nghĩa | Xử lý 3NF |
|---|---|---:|---:|---|---|---|
| `order_id` | integer | 0 | 646.945 | PK, FK → `orders` | Đơn được thanh toán | `payment.order_id` |
| `payment_method` | string | 0 | 5 | Bản sao | Khớp `orders.payment_method` ở 100% dòng | DROPPED |
| `payment_value` | float | 0 | 595.420 | DERIVED | Net payment của đơn | DROPPED; dùng đối soát |
| `installments` | integer | 0 | 5 | CHECK > 0 | Số kỳ: 1, 2, 3, 6, 12 | `payment.installments` |

`payment_value = Σ(quantity × unit_price − discount_amount)` theo đơn. Đây là **net**, khác
`sales.Revenue`, vốn là gross.

### 3.8 `shipments.csv`

**Grain:** shipment của một đơn. **PK/FK:** `order_id`. Quan hệ với order là 1:0..1.

| Cột | Type | Null | Cardinality | Khóa/quan hệ | Ý nghĩa | Xử lý 3NF |
|---|---|---:|---:|---|---|---|
| `order_id` | integer | 0 | 566.067 | PK, FK → `orders` | Đơn được giao | `shipment.order_id` |
| `ship_date` | date | 0 | 3.831 | CHECK NOT NULL | Ngày gửi | `shipment.ship_date` |
| `delivery_date` | date | 0 | 3.831 | CHECK ≥ `ship_date` | Ngày giao | `shipment.delivery_date`; nullable trong schema |
| `shipping_fee` | float | 0 | 1.856 | — | Phí vận chuyển | `shipment.shipping_fee` |

80.878 đơn không có shipment. Null về quan hệ không tự động là lỗi; phải đọc cùng `order_status`.

### 3.9 `returns.csv`

**Grain:** một event trả dòng hàng. **PK:** `return_id`.

| Cột | Type | Null | Cardinality | Khóa/quan hệ | Ý nghĩa | Xử lý 3NF |
|---|---|---:|---:|---|---|---|
| `return_id` | string | 0 | 39.939 | PK | Mã lần trả | `product_return.return_id` |
| `order_id` | integer | 0 | 36.062 | FK → `orders` | Đơn chứa dòng bị trả | `product_return.order_id` |
| `product_id` | integer | 0 | 1.286 | Khóa ghép nguồn | SKU hỗ trợ ánh xạ dòng hàng | Dùng để resolve `line_number`, sau đó DROPPED |
| `return_date` | date | 0 | 3.806 | — | Ngày trả | `product_return.return_date` |
| `return_reason` | string | 0 | 5 | Domain | Lý do trả | `product_return.return_reason` |
| `return_quantity` | integer | 0 | 8 | CHECK > 0 | Số lượng trả | `product_return.return_quantity` |
| `refund_amount` | float | 0 | 39.560 | — | Số tiền refund ghi nhận | `product_return.refund_amount` |
| `line_number` | GEN | — | — | FK → `order_item` | Dòng hàng được trả | Sinh bằng occurrence ổn định |

Có 4 dòng return nằm trên cặp `(order_id, product_id)` nhập nhằng. Join đúng
`(order_id, line_number)` cho 0 trường hợp `return_quantity > quantity`; join sai tạo fan-out và
cảnh báo giả `RET-043492`.

### 3.10 `reviews.csv`

**Grain:** một đánh giá dòng hàng. **PK:** `review_id`.

| Cột | Type | Null | Cardinality | Khóa/quan hệ | Ý nghĩa | Xử lý 3NF |
|---|---|---:|---:|---|---|---|
| `review_id` | string | 0 | 113.551 | PK | Mã đánh giá | `review.review_id` |
| `order_id` | integer | 0 | 111.369 | FK → `orders` | Đơn chứa dòng được đánh giá | `review.order_id` |
| `product_id` | integer | 0 | 1.412 | Khóa ghép nguồn | SKU hỗ trợ ánh xạ dòng hàng | Dùng resolve `line_number`, sau đó DROPPED |
| `customer_id` | integer | 0 | 48.676 | Bản sao | Suy được qua `order_id` | DROPPED |
| `review_date` | date | 0 | 3.825 | — | Ngày đánh giá | `review.review_date` |
| `rating` | integer | 0 | 5 | CHECK 1..5 | Điểm đánh giá | `review_title_label.rating` |
| `review_title` | string | 0 | 18 | FK logic | Nhãn đánh giá | `review_title_label.review_title`; FK trong `review` |
| `line_number` | GEN | — | — | FK → `order_item` | Dòng hàng được đánh giá | Sinh bằng occurrence ổn định |

FD quan sát được là `review_title → rating`, không phải chiều ngược lại. Có 2 review nằm trên
cặp item nhập nhằng; ánh xạ theo occurrence là giả định tái dựng.

### 3.11 `inventory.csv`

**Grain:** một sản phẩm tại một snapshot cuối tháng. **PK:** `(snapshot_date, product_id)`.

| Cột | Type | Null | Cardinality | Khóa/quan hệ | Ý nghĩa | Xử lý 3NF |
|---|---|---:|---:|---|---|---|
| `snapshot_date` | date | 0 | 126 | PK(1) | Mốc cuối tháng | `inventory_snapshot.snapshot_date` |
| `product_id` | integer | 0 | 1.624 | PK(2), FK → `products` | Sản phẩm tại snapshot | `inventory_snapshot.product_id` |
| `stock_on_hand` | integer | 0 | 1.895 | Measure | Tồn kho ghi nhận | `inventory_snapshot.stock_on_hand` |
| `units_received` | integer | 0 | 360 | Measure | Units nhập trong kỳ | `inventory_snapshot.units_received` |
| `units_sold` | integer | 0 | 303 | Measure | Units sold theo hệ vận hành kho | `inventory_snapshot.units_sold` |
| `stockout_days` | integer | 0 | 29 | Measure | Số ngày stockout | `inventory_snapshot.stockout_days` |
| `days_of_supply` | float | 0 | 9.289 | DERIVED | Số ngày tồn đủ bán | DROPPED; tính khi đọc |
| `fill_rate` | float | 0 | 29 | DERIVED | Proxy mức đáp ứng | DROPPED; tính khi đọc |
| `stockout_flag` | integer 0/1 | 0 | 2 | DERIVED | Có stockout hay không | DROPPED; tính khi đọc |
| `overstock_flag` | integer 0/1 | 0 | 2 | DERIVED | Days of supply > 90 | DROPPED; tính khi đọc |
| `reorder_flag` | integer | 0 | 1 | Hằng số | Cờ reorder không mang thông tin | DROPPED |
| `sell_through_rate` | float | 0 | 4.017 | DERIVED | Tỷ lệ bán trên tồn đầu kỳ proxy | DROPPED; tính khi đọc |
| `product_name` | string | 0 | 1.465 | Bản sao | Tên sản phẩm | DROPPED; lấy qua `product` |
| `category` | string | 0 | 4 | Bản sao | Category | DROPPED; lấy qua `product_model` |
| `segment` | string | 0 | 8 | Bản sao | Segment | DROPPED; lấy qua `product_model` |
| `year` | integer | 0 | 11 | DERIVED | Năm của snapshot | DROPPED; lấy từ `snapshot_date` |
| `month` | integer | 0 | 12 | DERIVED | Tháng của snapshot | DROPPED; lấy từ `snapshot_date` |

`inventory.units_sold` không reconcile với `order_items`; coi đây là nguồn vận hành độc lập.
Các measure tồn kho là bán cộng tính: không SUM `stock_on_hand` qua nhiều snapshot.

### 3.12 `web_traffic.csv`

**Grain:** traffic tổng hợp của một ngày. **PK:** `date`.

| Cột | Type | Null | Cardinality | Khóa/quan hệ | Ý nghĩa | Xử lý 3NF |
|---|---|---:|---:|---|---|---|
| `date` | date | 0 | 3.652 | PK | Ngày traffic | `web_traffic.traffic_date` |
| `sessions` | integer | 0 | 3.447 | Measure | Sessions/ngày | `web_traffic.sessions` |
| `unique_visitors` | integer | 0 | 3.382 | CHECK ≤ sessions | Visitors duy nhất/ngày | `web_traffic.unique_visitors` |
| `page_views` | integer | 0 | 3.620 | Measure | Page views/ngày | `web_traffic.page_views` |
| `bounce_rate` | float | 0 | 261 | Measure | Bounce rate trong nguồn | `web_traffic.bounce_rate` |
| `avg_session_duration_sec` | float | 0 | 1.771 | Measure | Thời lượng session trung bình | `web_traffic.avg_session_duration_sec` |
| `traffic_source` | string | 0 | 6 | Nhãn | Một nhãn nguồn trên mỗi ngày | `web_traffic.traffic_source` |

Đây không phải dữ liệu theo traffic source: toàn bảng vẫn chỉ có một dòng/ngày. Ghép với sales
theo ngày chỉ là time alignment, không phải FK và không tạo conversion rate chính thức.

### 3.13 `sales.csv`

**Grain:** actual sales của một ngày. **PK:** `Date`. Đây là nguồn target nhưng có thể tái tạo
từ giao dịch, nên lớp 3NF biểu diễn bằng view.

| Cột | Type | Null | Cardinality | Khóa/quan hệ | Ý nghĩa | Xử lý 3NF |
|---|---|---:|---:|---|---|---|
| `Date` | date | 0 | 3.833 | PK | Ngày actual | `daily_sales.sale_date` VIEW |
| `Revenue` | float | 0 | 3.833 | DERIVED | Gross Revenue theo ngày | `daily_sales.revenue` VIEW |
| `COGS` | float | 0 | 3.833 | DERIVED | COGS theo ngày | `daily_sales.cogs` VIEW |

Không thiếu ngày trong khoảng lịch sử. `Revenue` không trừ discount, không lọc status và không
trừ refund.

### 3.14 `sample_submission.csv`

**Grain:** một ngày tương lai cần dự báo. **PK:** `Date`. Các giá trị Revenue/COGS trong file là
placeholder hoặc baseline mẫu, không phải actual.

| Cột | Type | Null | Cardinality | Khóa/quan hệ | Ý nghĩa | Xử lý 3NF |
|---|---|---:|---:|---|---|---|
| `Date` | date | 0 | 548 | PK | Ngày dự báo | `daily_sales_forecast.forecast_date` |
| `Revenue` | float | 0 | 548 | Output | Revenue dự báo | `daily_sales_forecast.revenue` |
| `COGS` | float | 0 | 548 | Output | COGS dự báo | `daily_sales_forecast.cogs` |

---

## 4. Dictionary lớp quan hệ 3NF

Schema này là mô hình logic cho nguồn sự thật kiểu OLTP. Nó không thay thế star schema hoặc
feature table phục vụ forecasting.

### 4.1 Geography và customer

| Bảng | Grain / PK | Cột và constraint | Nguồn / ý nghĩa |
|---|---|---|---|
| `region` | Một region; PK `region` | `region VARCHAR(16)` | Danh mục 3 region từ `geography.region` |
| `city` | Một city; PK `city` | `city VARCHAR(64)`; `region` FK NOT NULL | City roll-up về region |
| `district` | Một district; PK `district` | `district VARCHAR(32)`; `region` FK NOT NULL | District roll-up về region |
| `zip_area` | Một zip; PK `zip` | `zip INTEGER`; `city` FK; `district` FK | Ánh xạ zip tới city và district |
| `customer` | Một khách; PK `customer_id` | `customer_id`; `zip` FK; `gender`; `age_group`; `acquisition_channel` NOT NULL; `signup_date` nullable | Bỏ `customers.city`; địa lý lấy qua zip |

Cardinality: `region 1:N city`, `region 1:N district`, `city 1:N zip_area`,
`district 1:N zip_area`, `zip_area 1:N customer`.

### 4.2 Product và promotion

| Bảng | Grain / PK | Cột và constraint | Nguồn / ý nghĩa |
|---|---|---|---|
| `product_model` | Một model; PK `product_name` | `product_name VARCHAR(64)`; `category`, `segment` NOT NULL | Tách FD nghiệp vụ `product_name → category, segment` |
| `product` | Một SKU; PK `product_id` | `product_id`; `product_name` FK; `size`; `color`; `list_price DECIMAL(14,6)`; `unit_cogs DECIMAL(14,6)`; CHECK `unit_cogs <= list_price` | Biến thể sản phẩm và giá snapshot |
| `promotion` | Một đợt promotion; PK `promo_id`, UK `promo_name` | 10 cột tương ứng nguồn; `applicable_category` nullable; CHECK `end_date >= start_date` | Định nghĩa promotion |

### 4.3 Giao dịch

| Bảng | Grain / PK | Cột và constraint | Nguồn / ý nghĩa |
|---|---|---|---|
| `order` | Một đơn; PK `order_id` | `order_date`; `customer_id` FK; `order_status`; `payment_method`; `device_type`; `order_source` NOT NULL | Header đơn; bỏ `orders.zip` |
| `order_item` | Một dòng hàng; PK `(order_id, line_number)` | `order_id` FK; `line_number`; `product_id` FK; `quantity > 0`; `unit_price`; `discount_amount >= 0` | Dòng giao dịch; `line_number` là GEN |
| `order_item_promotion` | Một promotion trên một dòng; PK `(order_id, line_number, promo_id)` | FK kép tới `order_item`; FK tới `promotion` | Junction table sau unpivot |
| `payment` | Payment của một đơn; PK/FK `order_id` | `installments > 0` | Chỉ giữ thông tin không suy ra được |
| `shipment` | Shipment của một đơn; PK/FK `order_id` | `ship_date` NOT NULL; `delivery_date` nullable; `shipping_fee`; CHECK delivery ≥ ship | Quan hệ order 1:0..1 |

### 4.4 Hậu mãi

| Bảng | Grain / PK | Cột và constraint | Nguồn / ý nghĩa |
|---|---|---|---|
| `product_return` | Một event trả; PK `return_id` | `(order_id, line_number)` FK và UK; `return_date`; `return_reason`; `return_quantity > 0`; `refund_amount` | Tối đa một return trên một dòng theo snapshot |
| `review_title_label` | Một nhãn review; PK `review_title` | `rating` CHECK 1..5 | Tách FD `review_title → rating` |
| `review` | Một đánh giá; PK `review_id` | `(order_id, line_number)` FK và UK; `review_date`; `review_title` FK | Bỏ `customer_id`; rating lấy qua label |

### 4.5 Vận hành và output

| Bảng | Grain / PK | Cột và constraint | Nguồn / ý nghĩa |
|---|---|---|---|
| `inventory_snapshot` | Một `(snapshot_date, product_id)` | `snapshot_date`; `product_id` FK; `stock_on_hand`; `units_received`; `units_sold`; `stockout_days` | Chỉ giữ 6 cột nguồn độc lập |
| `web_traffic` | Một ngày; PK `traffic_date` | `sessions`; `unique_visitors`; `page_views`; `bounce_rate`; `avg_session_duration_sec`; `traffic_source`; CHECK visitors ≤ sessions | Chuỗi ngày độc lập với order |
| `daily_sales_forecast` | Một ngày dự báo; PK `forecast_date` | `revenue DECIMAL(18,2)`; `cogs DECIMAL(18,2)` | Output 548 ngày |

### 4.6 View `daily_sales`

`sales.csv` không tạo bảng cơ sở thứ 20. View được tính từ giao dịch:

```sql
CREATE VIEW daily_sales AS
SELECT o.order_date AS sale_date,
       SUM(oi.quantity * oi.unit_price) AS revenue,
       SUM(oi.quantity * p.unit_cogs)   AS cogs
FROM order_item oi
JOIN "order" o ON o.order_id = oi.order_id
JOIN product p ON p.product_id = oi.product_id
GROUP BY o.order_date;
```

---

## 5. Ma trận ánh xạ nguồn → 3NF

| Nguồn | Đích chính | Chuyển đổi bắt buộc |
|---|---|---|
| `customers` | `customer` | Bỏ `city`; giữ `zip` làm FK |
| `geography` | `region`, `city`, `district`, `zip_area` | Deduplicate danh mục và kiểm region nhất quán theo hai đường |
| `products` | `product_model`, `product` | Tách category/segment theo `product_name`; giữ size/color ở SKU; rename `price`, `cogs` |
| `promotions` | `promotion` | Map 1:1; đổi `stackable_flag` sang boolean |
| `orders` | `order` | Bỏ `zip` sao chép |
| `order_items` | `order_item`, `order_item_promotion` | Sinh `line_number`; unpivot hai cột promo |
| `payments` | `payment` | Bỏ `payment_method`; dùng `payment_value` để audit rồi không lưu |
| `shipments` | `shipment` | Map 1:1 theo order; chấp nhận order không có shipment |
| `returns` | `product_return` | Resolve occurrence sang `line_number`; bỏ `product_id` sau mapping |
| `reviews` | `review_title_label`, `review` | Resolve `line_number`; bỏ `customer_id`; tách title/rating |
| `inventory` | `inventory_snapshot` | 17 → 6 cột; bỏ bản sao, hằng số và năm measure dẫn xuất |
| `web_traffic` | `web_traffic` | Rename `date → traffic_date` |
| `sales` | VIEW `daily_sales` | Không load như bảng; dùng để reconciliation |
| `sample_submission` | `daily_sales_forecast` | Rename `Date → forecast_date` |

Mọi cột nguồn đã được định tuyến trong §3: giữ, đổi tên, chuyển bảng, unpivot, dẫn xuất hoặc loại bỏ.

---

## 6. Công thức nghiệp vụ và cột dẫn xuất

### 6.1 Tiền và lợi nhuận

Ở grain dòng hàng:

```text
gross_revenue = quantity × unit_price
net_sales     = gross_revenue − discount_amount
line_cogs     = quantity × products.cogs
gross_profit  = net_sales − line_cogs
gross_margin  = gross_profit / net_sales
```

Ở grain ngày:

```text
sales.Revenue(d) = Σ gross_revenue
sales.COGS(d)    = Σ line_cogs
```

Ở grain đơn:

```text
payments.payment_value(order) = Σ net_sales
```

Ba đại lượng không được đánh đồng:

- `sales.Revenue`: gross, chưa trừ discount.
- `payment_value`: net sau discount.
- `refund_amount`: event hậu mãi, không được nguồn trừ khỏi `sales.Revenue`.

COGS của dataset không bao gồm shipping, marketing, lương, chi phí kho/vận hành hoặc refund;
không nên gọi đây là lợi nhuận kế toán cuối cùng.

### 6.2 Năm cột inventory tính lại được

Các công thức dưới đây khớp 100% trên 60.247 dòng với `np.isclose(atol=1e-9)` sau khi áp dụng
đúng bước làm tròn:

```text
stockout_flag     = (stockout_days > 0)
days_of_supply    = ROUND(stock_on_hand / (units_sold / 30), 1)
fill_rate         = ROUND(1 − stockout_days / 30, 4)
sell_through_rate = ROUND(units_sold / (stock_on_hand + units_sold), 4)
overstock_flag    = (days_of_supply > 90)
```

Mẫu số `30` là quy ước cố định của dataset, không thay bằng số ngày thật của tháng.

---

## 7. Quan hệ và kiểm tra toàn vẹn

### 7.1 Quan hệ nguồn

15 phép kiểm ở cấp cột, tính riêng hai cột promotion:

| Child | Parent | Kết quả snapshot |
|---|---|---|
| `customers.zip` | `geography.zip` | 0 orphan |
| `orders.customer_id` | `customers.customer_id` | 0 orphan |
| `orders.zip` | `geography.zip` | 0 orphan |
| `order_items.order_id` | `orders.order_id` | 0 orphan |
| `order_items.product_id` | `products.product_id` | 0 orphan |
| `order_items.promo_id` | `promotions.promo_id` | 0 orphan trên dòng non-null |
| `order_items.promo_id_2` | `promotions.promo_id` | 0 orphan trên dòng non-null |
| `payments.order_id` | `orders.order_id` | 0 orphan |
| `shipments.order_id` | `orders.order_id` | 0 orphan |
| `returns.order_id` | `orders.order_id` | 0 orphan |
| `returns.product_id` | `products.product_id` | 0 orphan |
| `reviews.order_id` | `orders.order_id` | 0 orphan |
| `reviews.product_id` | `products.product_id` | 0 orphan |
| `reviews.customer_id` | `customers.customer_id` | 0 orphan |
| `inventory.product_id` | `products.product_id` | 0 orphan |

Sau normalization, hai cột promo trở thành một quan hệ M:N duy nhất qua junction table.

### 7.2 Constraint không biểu diễn được chỉ bằng FK

- `return_quantity <= order_item.quantity` cần trigger hoặc test liên bảng.
- `city.region` và `district.region` của cùng một zip phải nhất quán.
- Việc gán `line_number` phải dùng thứ tự nguồn ổn định trước mọi join return/review.
- `daily_sales` phải reconcile với `sales.csv` trong dung sai số thực.

---

## 8. Phụ lục chất lượng dữ liệu

| Vấn đề quan sát | Tác động | Quy tắc sử dụng |
|---|---|---|
| 16 cặp `(order_id, product_id)` trùng | Không thể dùng cặp này làm item PK | Sinh `line_number`; không group làm mất dòng |
| 4 return và 2 review trên cặp item nhập nhằng | Không biết line ground truth từ nguồn | Ánh xạ theo occurrence và công bố giả định |
| `customers.signup_date` không nhất quán lịch sử đơn | Cohort/tenure sai | Không dùng cho cohort nếu chưa có nguồn xác nhận |
| `products.price < 100` ở 654 SKU chưa từng bán | Hai thang giá nghi lỗi | Audit/filter; không tạo `price_tier` phân tích |
| `products.price` chỉ là snapshot | Không dựng được lịch sử giá | Giữ `unit_price` trong `order_item` |
| `orders.order_status='returned'` khác bảng `returns` | Hai nguồn sự thật | KPI return theo dòng dùng bảng `returns`; ghi rõ định nghĩa |
| 80.878 order không có shipment | Có thể hợp lệ theo lifecycle | Không gọi toàn bộ là lỗi nếu chưa xét status |
| `inventory.units_sold` chỉ khớp giao dịch ở tỷ lệ thấp | Hai hệ thống đo khác nhau | Coi inventory là nguồn vận hành độc lập |
| `inventory.reorder_flag` hằng số | Không mang thông tin | Loại bỏ |
| `web_traffic` một dòng/ngày nhưng có `traffic_source` | Không phải phân rã theo source | Không SUM hoặc gọi là attribution/conversion |
| `bounce_rate` trung bình khoảng 0,005 | Phi thực tế | Không xây KPI quan trọng nếu chưa xác minh semantics |
| `sales` gross, payment net | Nhầm source-of-truth tiền | Định nghĩa metric layer rõ ràng |
| Mọi bảng phụ dừng ở 2022-12-31 | Không có feature tương lai trực tiếp | Chỉ dùng feature lịch sử hoặc calendar-derived |

Toàn vẹn tham chiếu tốt không có nghĩa mọi giá trị đều đúng về nghiệp vụ. Nhiều pattern phân bố
và miền giá trị cho thấy dữ liệu có tính mô phỏng; kết luận causal hoặc khái quát ra thị trường
thật phải được trình bày như giả thuyết.

---

## 9. Nguồn kiểm chứng và bảo trì

| Nội dung | Nguồn bằng chứng trong repo |
|---|---|
| Grain, quality, reconciliation và câu chuyện business | [`notebooks/01_exploration/business_eda.ipynb`](../notebooks/01_exploration/business_eda.ipynb) |
| Khóa, cardinality, FK và star schema | [`notebooks/02_design/data_model.ipynb`](../notebooks/02_design/data_model.ipynb) |
| FD 1NF/2NF/3NF và công thức inventory | [`notebooks/02_design/normalization.ipynb`](../notebooks/02_design/normalization.ipynb) |
| DDL 19 bảng và view | [`normalized_schema.md`](normalized_schema.md) |
| Target, structural break và forecasting constraints | [`notebooks/01_exploration/eda.ipynb`](../notebooks/01_exploration/eda.ipynb) |

Khi CSV hoặc schema thay đổi, cập nhật theo thứ tự:

1. Chạy lại notebook bằng chứng.
2. Kiểm row count, null, cardinality, PK/FK và công thức.
3. Cập nhật DDL/schema nếu quyết định thiết kế thay đổi.
4. Cập nhật data dictionary sau cùng, không sửa số liệu bằng suy đoán.
