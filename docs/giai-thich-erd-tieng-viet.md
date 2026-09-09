# Giải thích sơ đồ ERD bằng tiếng Việt

> Tài liệu tra cứu nhanh: dịch nghĩa toàn bộ tên bảng, tên thuộc tính trên sơ đồ
> [`erd.svg`](erd.svg), kèm mô tả luồng nghiệp vụ.

---

# PHẦN 1 — Mười ba bảng

| Tên trên sơ đồ | Nghĩa tiếng Việt | Một dòng là gì |
|---|---|---|
| `GEOGRAPHY` | Địa lý | Một mã vùng |
| `CUSTOMERS` | Khách hàng | Một khách hàng |
| `PRODUCTS` | Sản phẩm | Một mã hàng cụ thể (đã tính cả size, màu) |
| `PROMOTIONS` | Chương trình khuyến mại | Một đợt khuyến mại |
| `ORDERS` | Đơn hàng | Một đơn hàng |
| `ORDER_ITEMS` | Dòng hàng trong đơn | Một sản phẩm trong một đơn |
| `PAYMENTS` | Thanh toán | Việc thanh toán của một đơn |
| `SHIPMENTS` | Giao vận | Lần giao hàng của một đơn |
| `RETURNS` | Trả hàng | Một lượt trả lại hàng |
| `REVIEWS` | Đánh giá | Một đánh giá sản phẩm |
| `INVENTORY` | Tồn kho | Tồn kho của một sản phẩm trong một tháng |
| `SALES` | Doanh thu ngày | Doanh thu và giá vốn của một ngày |
| `WEB_TRAFFIC` | Lưu lượng website | Lưu lượng truy cập của một ngày |

---

# PHẦN 2 — Dịch thuộc tính từng bảng

<!-- muc-luc -->
## Mục lục

- [`GEOGRAPHY` — Địa lý](#geography--địa-lý)
- [`CUSTOMERS` — Khách hàng](#customers--khách-hàng)
- [`PRODUCTS` — Sản phẩm](#products--sản-phẩm)
- [`PROMOTIONS` — Chương trình khuyến mại](#promotions--chương-trình-khuyến-mại)
- [`ORDERS` — Đơn hàng](#orders--đơn-hàng)
- [`ORDER_ITEMS` — Dòng hàng trong đơn](#orderitems--dòng-hàng-trong-đơn)
- [`PAYMENTS` — Thanh toán](#payments--thanh-toán)
- [`SHIPMENTS` — Giao vận](#shipments--giao-vận)
- [`RETURNS` — Trả hàng](#returns--trả-hàng)
- [`REVIEWS` — Đánh giá](#reviews--đánh-giá)
- [`INVENTORY` — Tồn kho](#inventory--tồn-kho)
- [`SALES` — Doanh thu ngày · BIẾN CẦN DỰ BÁO](#sales--doanh-thu-ngày--biến-cần-dự-báo)
- [`WEB_TRAFFIC` — Lưu lượng website](#webtraffic--lưu-lượng-website)
- [Luồng chính: hành trình một đơn hàng](#luồng-chính-hành-trình-một-đơn-hàng)
- [Luồng phụ trợ](#luồng-phụ-trợ)
- [Sơ đồ luồng](#sơ-đồ-luồng)
- [1. Doanh thu ghi nhận ngay lúc đặt hàng](#1-doanh-thu-ghi-nhận-ngay-lúc-đặt-hàng)
- [2. Trạng thái đơn quyết định luồng có đi tiếp không](#2-trạng-thái-đơn-quyết-định-luồng-có-đi-tiếp-không)
- [3. `ORDER_ITEMS` là trung tâm của mọi thứ](#3-orderitems-là-trung-tâm-của-mọi-thứ)

---
<!-- muc-luc -->

## `GEOGRAPHY` — Địa lý

| Thuộc tính | Nghĩa |
|---|---|
| `zip` | Mã vùng |
| `city` | Thành phố |
| `region` | Khu vực (Đông / Trung / Tây) |
| `district` | Quận, huyện |

## `CUSTOMERS` — Khách hàng

| Thuộc tính | Nghĩa |
|---|---|
| `customer_id` | Mã khách hàng |
| `signup_date` | Ngày đăng ký tài khoản — **không đáng tin**, 73,8% đơn đặt trước ngày này |
| `gender` | Giới tính |
| `age_group` | Nhóm tuổi |
| `acquisition_channel` | Kênh thu hút khách — khách biết đến shop qua đâu |
| `city` | Thành phố *(suy diễn)* |

## `PRODUCTS` — Sản phẩm

| Thuộc tính | Nghĩa |
|---|---|
| `product_id` | Mã sản phẩm |
| `product_name` | Tên sản phẩm |
| `category` | Danh mục: Streetwear / Outdoor / Casual / GenZ |
| `segment` | Phân khúc |
| `size` | Kích cỡ |
| `color` | Màu sắc |
| `price` | Giá niêm yết |
| `cogs` | **Giá vốn** — giá nhập, dùng để tính lợi nhuận |

## `PROMOTIONS` — Chương trình khuyến mại

| Thuộc tính | Nghĩa |
|---|---|
| `promo_id` | Mã chương trình |
| `promo_name` | Tên chương trình |
| `promo_type` | Kiểu giảm: theo phần trăm hay số tiền cố định |
| `discount_value` | Mức giảm |
| `start_date` | Ngày bắt đầu |
| `end_date` | Ngày kết thúc |
| `applicable_category` | Danh mục áp dụng — **để trống nghĩa là áp dụng tất cả** |
| `promo_channel` | Kênh triển khai |
| `stackable_flag` | Có cho cộng dồn với khuyến mại khác không |
| `min_order_value` | Giá trị đơn tối thiểu để được áp dụng |

## `ORDERS` — Đơn hàng

| Thuộc tính | Nghĩa |
|---|---|
| `order_id` | Mã đơn hàng |
| `order_date` | **Ngày đặt hàng** — mốc ghi nhận doanh thu |
| `order_status` | Trạng thái đơn |
| `payment_method` | Hình thức thanh toán |
| `device_type` | Thiết bị đặt hàng: điện thoại / máy tính / máy tính bảng |
| `order_source` | Kênh dẫn tới đơn hàng |

**Sáu trạng thái đơn hàng:**

| Giá trị | Nghĩa | Tỷ lệ |
|---|---|---:|
| `created` | Vừa tạo đơn, chưa thanh toán | 1,1% |
| `paid` | Đã thanh toán, chưa xuất kho | 2,1% |
| `shipped` | Đang giao | 2,1% |
| `delivered` | Đã giao thành công | 79,9% |
| `returned` | Đã giao rồi bị trả lại | 5,6% |
| `cancelled` | Đã hủy | 9,2% |

## `ORDER_ITEMS` — Dòng hàng trong đơn

| Thuộc tính | Nghĩa |
|---|---|
| `quantity` | Số lượng mua |
| `unit_price` | **Giá bán thực tế** tại thời điểm mua |
| `discount_amount` | Số tiền được giảm |

## `PAYMENTS` — Thanh toán

| Thuộc tính | Nghĩa |
|---|---|
| `installments` | Số kỳ trả góp — giá trị 1 nghĩa là trả một lần |
| `payment_value` | Số tiền thực trả *(suy diễn)* |
| `payment_method` | Hình thức thanh toán *(suy diễn)* |

## `SHIPMENTS` — Giao vận

| Thuộc tính | Nghĩa |
|---|---|
| `ship_date` | Ngày xuất kho |
| `delivery_date` | Ngày giao tới tay khách |
| `shipping_fee` | Phí vận chuyển |

## `RETURNS` — Trả hàng

| Thuộc tính | Nghĩa |
|---|---|
| `return_id` | Mã lượt trả |
| `return_date` | Ngày trả |
| `return_reason` | Lý do trả |
| `return_quantity` | Số lượng trả |
| `refund_amount` | Số tiền hoàn lại |

**Năm lý do trả hàng:**

| Giá trị | Nghĩa |
|---|---|
| `wrong_size` | Sai kích cỡ |
| `defective` | Sản phẩm lỗi |
| `not_as_described` | Không giống mô tả |
| `changed_mind` | Khách đổi ý |
| `late_delivery` | Giao trễ |

## `REVIEWS` — Đánh giá

| Thuộc tính | Nghĩa |
|---|---|
| `review_id` | Mã đánh giá |
| `review_date` | Ngày đánh giá |
| `rating` | Số sao, thang 1–5 |
| `review_title` | Tiêu đề đánh giá — chỉ có 18 mẫu định sẵn, không phải văn bản tự do |

## `INVENTORY` — Tồn kho

| Thuộc tính | Nghĩa |
|---|---|
| `snapshot_date` | Ngày chốt sổ, luôn là ngày cuối tháng |
| `stock_on_hand` | Số lượng còn trong kho |
| `units_received` | Số lượng nhập trong tháng |
| `units_sold` | Số lượng bán trong tháng |
| `stockout_days` | Số ngày hết hàng trong tháng |
| `overstock_flag` | Cờ báo tồn kho quá nhiều |
| `reorder_flag` | Cờ báo cần nhập thêm — **luôn bằng 0, không dùng được** |
| `days_of_supply` | Số ngày hàng còn đủ bán *(suy diễn)* |
| `fill_rate` | Tỷ lệ đáp ứng đơn hàng *(suy diễn)* |
| `stockout_flag` | Cờ báo có hết hàng *(suy diễn)* |
| `sell_through_rate` | Tỷ lệ bán hết hàng *(suy diễn)* |
| `year` | Năm *(suy diễn)* |
| `month` | Tháng *(suy diễn)* |

## `SALES` — Doanh thu ngày · BIẾN CẦN DỰ BÁO

| Thuộc tính | Nghĩa |
|---|---|
| `Date` | Ngày |
| `Revenue` | **Doanh thu gộp** trong ngày *(suy diễn)* |
| `COGS` | **Giá vốn hàng bán** trong ngày *(suy diễn)* |

## `WEB_TRAFFIC` — Lưu lượng website

| Thuộc tính | Nghĩa |
|---|---|
| `date` | Ngày |
| `sessions` | Số phiên truy cập |
| `unique_visitors` | Số người truy cập, không tính trùng |
| `page_views` | Số lượt xem trang |
| `bounce_rate` | Tỷ lệ thoát ngay |
| `avg_session_duration_sec` | Thời gian ở lại trung bình, tính bằng giây |
| `traffic_source` | Nguồn truy cập |

---

# PHẦN 3 — Luồng nghiệp vụ

## Luồng chính: hành trình một đơn hàng

### Bước 1 — Khách vào website

`WEB_TRAFFIC` ghi nhận hôm nay có bao nhiêu người vào, đến từ nguồn nào. Đây là **đầu phễu**.

### Bước 2 — Khách đặt hàng

Tạo một dòng trong `ORDERS`. Hệ thống ghi lại: ai đặt (`CUSTOMERS`), giao đi đâu (`GEOGRAPHY`), đặt
bằng thiết bị gì, đến từ kênh nào. Trạng thái ban đầu là `created`.

### Bước 3 — Chi tiết đơn hàng

Tạo các dòng trong `ORDER_ITEMS`. Mỗi sản phẩm khách chọn là một dòng, ghi rõ: mua sản phẩm nào
(`PRODUCTS`), số lượng bao nhiêu, giá bao nhiêu, có áp khuyến mại nào không (`PROMOTIONS`).

> Trung bình mỗi đơn có **1,10 dòng hàng**, tối đa 5 dòng.

### Bước 4 — Thanh toán

Tạo một dòng trong `PAYMENTS`. Trạng thái đơn chuyển thành `paid`. Số tiền thực trả bằng tổng giá trị
các dòng hàng trừ đi giảm giá.

> Quan hệ **1:1 tuyệt đối** — mọi đơn đều có đúng một bản ghi thanh toán, không thừa không thiếu.

### Bước 5 — Xuất kho và giao hàng

Tạo một dòng trong `SHIPMENTS`. Trạng thái chuyển `shipped` rồi `delivered`. Hàng xuất kho sau 0–3
ngày, giao tới tay khách sau 2–7 ngày nữa.

> Chỉ **87,5%** số đơn đi tới được bước này. Đơn ở trạng thái `cancelled`, `paid`, `created` không bao
> giờ rời kho.

### Bước 6 — Sau khi khách nhận hàng

Có hai nhánh có thể xảy ra:

- **Trả hàng** → tạo dòng trong `RETURNS`. Xảy ra sau 5–31 ngày, ở **5,6%** số đơn. Trạng thái đơn
  chuyển thành `returned`.
- **Đánh giá** → tạo dòng trong `REVIEWS`. Xảy ra sau 3–40 ngày, ở **17,2%** số đơn.

> Điểm quan trọng: cả hai đều gắn với **một dòng hàng cụ thể**, không phải với cả đơn. Khách trả lại
> *"hai cái áo size M màu đỏ"*, chứ không trả cả đơn hàng.

## Luồng phụ trợ

### Tồn kho

`INVENTORY` chốt sổ mỗi cuối tháng cho từng sản phẩm: còn bao nhiêu trong kho, nhập bao nhiêu, bán bao
nhiêu, có ngày nào hết hàng không. Luồng này chạy song song, không gắn trực tiếp với đơn hàng nào.

### Khuyến mại

`PROMOTIONS` là lịch các đợt giảm giá. Khi khách mua đúng vào ngày có khuyến mại, dòng hàng sẽ được ghi
mã chương trình và số tiền được giảm.

> Chỉ **38,7%** số dòng hàng có khuyến mại. Các đợt khuyến mại phủ **44,5%** số ngày trong 11 năm.

### Tổng hợp doanh thu

Cuối mỗi ngày, hệ thống cộng tất cả các dòng hàng thuộc những đơn đặt trong ngày hôm đó thành một dòng
trong `SALES`. Đây chính là biến mà nhóm cần dự báo.

## Sơ đồ luồng

```
        WEB_TRAFFIC                    PROMOTIONS        INVENTORY
        (khách vào)                    (lịch giảm giá)   (chốt sổ hàng tháng)
             |                              |                  |
             v                              v                  v
CUSTOMERS --> ORDERS --> ORDER_ITEMS <-- PRODUCTS -------------+
             |  |  |           |
             |  |  |           +--> RETURNS   (5,6% đơn, sau 5-31 ngày)
             |  |  |           +--> REVIEWS   (17,2% đơn, sau 3-40 ngày)
             |  |  |
             |  |  +--> PAYMENTS   (1:1, mọi đơn đều có)
             |  +-----> SHIPMENTS  (87,5% đơn)
             |
             +--- gộp theo ngày ---> SALES  <== BIẾN CẦN DỰ BÁO
```

---

# PHẦN 4 — Ba điều đáng nhớ về luồng này

## 1. Doanh thu ghi nhận ngay lúc đặt hàng

Không phải lúc giao hàng, cũng không phải lúc thanh toán. Nên `SALES` tính cả những đơn sau đó bị hủy
hoặc bị trả lại.

> **16,9%** doanh thu ghi nhận không bao giờ về túi thật: hủy đơn 9,23%, hoàn tiền 3,11%, giảm giá
> 4,56%.

Khi báo cáo kết quả dự báo phải nói rõ đang dự báo **giá trị đặt hàng**, không phải doanh thu ghi nhận
theo chuẩn kế toán.

## 2. Trạng thái đơn quyết định luồng có đi tiếp không

Đơn `cancelled` dừng lại ngay, không bao giờ có bản ghi giao vận. Chỉ đơn `returned` mới có bản ghi trả
hàng. Trường `order_status` vì vậy không chỉ là một nhãn phân loại — nó là **ràng buộc nghiệp vụ** được
cài sẵn trong dữ liệu.

## 3. `ORDER_ITEMS` là trung tâm của mọi thứ

Bảng này nối đơn hàng với sản phẩm, gắn với khuyến mại, và là nơi phát sinh cả trả hàng lẫn đánh giá.
Đây cũng chính là nơi sinh ra hai biến mục tiêu:

```
Revenue(ngày d) = tổng (quantity × unit_price)   của các đơn đặt trong ngày d
COGS(ngày d)    = tổng (quantity × cogs)
```

Đã kiểm chứng: **sai số 0,00 trên cả 3.833 ngày**.
