# Giải thích thiết kế cơ sở dữ liệu 3NF

Tài liệu này giải thích vì sao 14 file CSV nguồn được thiết kế thành mô hình quan hệ 3NF gồm 19 bảng.
Nguồn thiết kế chi tiết là [`normalized_schema.md`](normalized_schema.md); bằng chứng dữ liệu nằm trong
[`notebooks/02_design/normalization.ipynb`](../notebooks/02_design/normalization.ipynb) và [`notebooks/01_exploration/business_eda.ipynb`](../notebooks/01_exploration/business_eda.ipynb).

Mục tiêu của tài liệu là giúp trả lời được ba câu khi trình bày:

1. Bảng này lưu sự thật nghiệp vụ nào?
2. Vì sao bảng hoặc cột phải được tách như vậy?
3. Thiết kế đang ngăn vấn đề dữ liệu nào?

---

## 1. Mục tiêu của thiết kế

Thiết kế không cố tạo càng nhiều bảng càng tốt. Mục tiêu là:

> Mỗi sự thật nghiệp vụ chỉ được lưu ở một nơi, mỗi dòng có định danh rõ ràng và các quan hệ được database
> bảo vệ bằng khóa cùng constraint.

14 CSV nguồn là các file phẳng:

- không khai báo primary key;
- không khai báo foreign key;
- chứa một số cột bị sao chép;
- chứa cột có thể tính lại;
- `order_items` không có khóa dòng hàng hợp lệ;
- promotion được trải trên hai cột lặp.

Quá trình chuẩn hóa khôi phục cấu trúc quan hệ từ dữ liệu đó. Kết quả cuối gồm:

- 19 bảng cơ sở;
- 17 quan hệ;
- `sales.csv` trở thành view `daily_sales`, không phải bảng cơ sở.

Đây là thiết kế dành cho hệ thống nguồn hoặc OLTP, nơi dữ liệu được thêm, sửa và cần bảo đảm nhất quán.

---

## 2. Câu chuyện nghiệp vụ

Xương sống của toàn bộ hệ thống là:

```text
GEOGRAPHY → CUSTOMER → ORDER → ORDER_ITEM ← PRODUCT
```

Đọc thành câu chuyện:

```text
Khách hàng sống tại một khu vực
    → khách tạo đơn hàng
        → đơn có một hoặc nhiều dòng sản phẩm
            → mỗi dòng tham chiếu một sản phẩm
```

Các nghiệp vụ bổ sung:

```text
ORDER → PAYMENT
ORDER → SHIPMENT

ORDER_ITEM ↔ PROMOTION
ORDER_ITEM → PRODUCT_RETURN
ORDER_ITEM → REVIEW

PRODUCT → INVENTORY_SNAPSHOT
```

Hai bảng đứng độc lập:

```text
WEB_TRAFFIC
DAILY_SALES_FORECAST
```

`web_traffic` không có `session_id`, `customer_id` hoặc `order_id`. `daily_sales_forecast` là kết quả tương lai,
không phải giao dịch đã xảy ra. Vì vậy không có foreign key hợp lệ để nối hai bảng này vào cây giao dịch.

---

## 3. Ba nguyên tắc chuẩn hóa

### 3.1 First Normal Form — 1NF

1NF hỏi:

- mỗi dòng có được định danh không;
- mỗi ô có chứa một giá trị nguyên tử không;
- có nhóm cột lặp hay không.

Trong dataset, hai vấn đề 1NF đều nằm ở `order_items`:

1. Không có khóa dòng hàng hợp lệ.
2. Promotion được lưu bằng `promo_id` và `promo_id_2`.

### 3.2 Second Normal Form — 2NF

2NF hỏi:

> Thuộc tính không khóa có phụ thuộc toàn bộ khóa tổ hợp hay chỉ phụ thuộc một phần khóa?

2NF chỉ có thể bị vi phạm khi bảng dùng khóa tổ hợp. Trong dataset, `inventory` là ví dụ chính với khóa:

```text
(snapshot_date, product_id)
```

### 3.3 Third Normal Form — 3NF

3NF hỏi:

> Một thuộc tính không khóa có xác định một thuộc tính không khóa khác hay không?

Nếu tồn tại:

```text
Primary Key → A → B
```

thì `B` không nên tiếp tục nằm trong cùng bảng. Nó phải được đưa về đúng chủ sở hữu.

### Câu nhớ ngắn

```text
1NF: dòng có định danh, không có nhóm lặp.
2NF: phụ thuộc toàn bộ khóa tổ hợp.
3NF: không phụ thuộc bắc cầu qua thuộc tính không khóa.
```

---

## 4. Vì sao `order_item` cần `line_number`?

CSV `order_items` không có `order_item_id`. Ban đầu có thể nghĩ khóa là:

```text
(order_id, product_id)
```

Nhưng dữ liệu có 16 cặp bị trùng. Ví dụ cùng một đơn và cùng một sản phẩm xuất hiện thành hai dòng với quantity
và unit price khác nhau:

```text
order_id = 14280, product_id = 976
├── quantity = 1, unit_price = 4019.47
└── quantity = 2, unit_price = 3937.99
```

Vì vậy `(order_id, product_id)` không thể nhận diện duy nhất một dòng hàng.

Thiết kế thêm:

```text
line_number
```

Khóa mới:

```text
PRIMARY KEY (order_id, line_number)
```

Ý nghĩa:

- `order_id` cho biết dòng thuộc đơn nào;
- `line_number` phân biệt các dòng bên trong đơn;
- một order item không thể tồn tại độc lập với order.

Đây là mô hình của một thực thể yếu: định danh dòng hàng phải mượn khóa của order.

### Vì sao quyết định này quan trọng?

`returns` và `reviews` trong nguồn chỉ tham chiếu `(order_id, product_id)`. Với các cặp trùng, có 4 return và
2 review không xác định được đang trỏ vào dòng nào nếu dùng cặp này.

ETL phải:

1. giữ thứ tự nguồn ổn định;
2. sinh `line_number` trước;
3. sau đó mới ánh xạ return và review;
4. dùng `(order_id, line_number)` làm foreign key.

Nếu join bằng `(order_id, product_id)`, dữ liệu có thể bị fan-out, làm tăng số dòng và tạo lỗi chất lượng giả.

---

## 5. Vì sao cần `order_item_promotion`?

Nguồn lưu promotion trong hai cột:

```text
promo_id
promo_id_2
```

Đây là một nhóm cột lặp. Nếu sau này một dòng có promotion thứ ba thì phải thêm `promo_id_3`, nghĩa là thay đổi
schema chỉ để thêm dữ liệu.

Thiết kế tạo bảng junction:

```text
order_item_promotion
--------------------
order_id
line_number
promo_id
```

Khóa chính:

```text
(order_id, line_number, promo_id)
```

Quan hệ trở thành:

```text
ORDER_ITEM N ↔ N PROMOTION
```

Một dòng hàng có thể không có, có một hoặc có nhiều promotion mà không phải đổi cấu trúc database.

Dữ liệu hiện tại tạo 276.522 liên kết item–promotion sau khi unpivot hai cột nguồn.

---

## 6. Vì sao `inventory` bị rút từ 17 xuống 6 cột?

Grain của inventory là:

```text
Một sản phẩm tại một snapshot
```

Khóa:

```text
(snapshot_date, product_id)
```

Nhưng nguồn chứa các thuộc tính:

```text
product_name, category, segment
year, month
```

Các phụ thuộc thực tế:

```text
product_id → product_name, category, segment
snapshot_date → year, month
```

Các cột trên chỉ phụ thuộc một phần khóa tổ hợp, nên không thuộc grain inventory.

Thiết kế xử lý:

- thông tin sản phẩm chuyển về `product` và `product_model`;
- `year`, `month` tính từ `snapshot_date`;
- inventory chỉ giữ measure tại snapshot.

Kết quả:

```text
inventory_snapshot
------------------
snapshot_date
product_id
stock_on_hand
units_received
units_sold
stockout_days
```

### Các cột dẫn xuất bị loại

Notebook đã kiểm chứng năm cột có thể tính lại 100%:

```text
stockout_flag      = stockout_days > 0
days_of_supply     = ROUND(stock_on_hand / (units_sold / 30), 1)
fill_rate          = ROUND(1 - stockout_days / 30, 4)
sell_through_rate  = ROUND(units_sold / (stock_on_hand + units_sold), 4)
overstock_flag     = days_of_supply > 90
```

Các cột này không bị loại vì 3NF. Chúng bị loại theo nguyên tắc riêng:

> Không lưu lại dữ liệu có thể tính chính xác từ dữ liệu nguồn, trừ khi có lý do hiệu năng hoặc audit rõ ràng.

`reorder_flag` cũng bị loại vì chỉ có một giá trị `0`, không mang thông tin.

---

## 7. Vì sao tách `product_model` và `product`?

Dữ liệu chứng minh:

```text
product_id → product_name → category, segment
```

`category` và `segment` thuộc product model, không thuộc riêng từng SKU.

Thiết kế:

```text
product_model
-------------
product_name PK
category
segment
```

```text
product
-------
product_id PK
product_name FK
size
color
list_price
unit_cogs
```

Ý nghĩa:

- một product model mô tả dòng sản phẩm chung;
- một product là biến thể SKU cụ thể theo size, color và giá;
- category và segment không bị lặp lại trên từng biến thể.

`product_id` vẫn cần thiết vì `(product_name, size, color)` không duy nhất trong dữ liệu.

---

## 8. Vì sao địa lý thành bốn bảng?

Nguồn `geography` có:

```text
zip, city, district, region
```

Dữ liệu chứng minh:

```text
zip → city
zip → district
city → region
district → region
```

Thiết kế 3NF chặt:

```text
region(region PK)
city(city PK, region FK)
district(district PK, region FK)
zip_area(zip PK, city FK, district FK)
```

Lợi ích:

- region không bị lặp trên hàng nghìn zip;
- đổi region của city chỉ cần sửa một dòng;
- city, district và zip có source of truth riêng.

### Đánh đổi

City và district cắt chéo nhau, không tạo thành một cây địa lý duy nhất. Từ một zip có thể tới region theo hai
đường:

```text
zip → city → region
zip → district → region
```

DDL thông thường không tự bảo đảm hai đường luôn khớp. Vì vậy:

- phương án bốn bảng đạt 3NF chặt;
- phương án geography phẳng dễ truy vấn và có thể thực dụng hơn trong production.

Đây là ví dụ cho thấy 3NF là công cụ, không phải mục tiêu tự thân.

---

## 9. Vì sao bỏ các cột địa lý bị sao chép?

### `customers.city`

Dữ liệu chứng minh:

```text
customer_id → zip → city
```

`customers.city` khớp hoàn toàn với city suy từ geography. Nó được bỏ để city chỉ có một owner.

### `orders.zip`

Dữ liệu chứng minh:

```text
order_id → customer_id → zip
```

`orders.zip` khớp hoàn toàn với `customers.zip`. Dataset không cung cấp địa chỉ giao hàng riêng, nên cột này là
bản sao của địa chỉ customer và được bỏ.

---

## 10. Vì sao tách `review_title_label`?

Dữ liệu chứng minh chiều phụ thuộc:

```text
review_title → rating
```

Một title luôn ứng với đúng một rating, nhưng một rating có thể có nhiều title.

Thiết kế:

```text
review_title_label
------------------
review_title PK
rating
```

```text
review
------
review_id PK
order_id FK
line_number FK
review_date
review_title FK
```

`review` không cần lưu lại `rating` vì có thể suy qua `review_title`.

### Giới hạn cần nói

Trong hệ thống thực tế, người dùng thường nhập rating độc lập. Phụ thuộc này có thể là dấu vết của dữ liệu tổng
hợp. Thiết kế hiện tại đúng theo snapshot, không phải quy luật chung cho mọi hệ thống review.

---

## 11. Vì sao bỏ các cột sao chép từ bảng cha?

| Cột nguồn | Có thể suy ra từ | Quyết định |
|---|---|---|
| `customers.city` | `customer → zip_area → city` | bỏ khỏi `customer` |
| `orders.zip` | `order → customer → zip` | bỏ khỏi `order` |
| `payments.payment_method` | `payment → order → payment_method` | bỏ khỏi `payment` |
| `reviews.customer_id` | `review → order → customer_id` | bỏ khỏi `review` |

Nguyên tắc:

```text
Mỗi sự thật chỉ có một owner.
Bảng khác muốn biết thì join qua foreign key.
```

Nếu cùng một sự thật được lưu ở hai nơi, khi sửa một nơi nhưng quên nơi còn lại sẽ sinh update anomaly.

---

## 12. Vì sao bảng `payment` chỉ còn ít cột?

Nguồn có:

```text
order_id
payment_method
payment_value
installments
```

Nhưng:

- `payment_method` đã thuộc `order`;
- `payment_value` có thể tái tạo chính xác từ các dòng hàng.

Công thức:

```text
payment_value = Σ(quantity × unit_price - discount_amount)
```

Vì vậy bảng sau chuẩn hóa là:

```text
payment
-------
order_id PK, FK
installments
```

Payment vẫn là một khái niệm nghiệp vụ. Nó chỉ bị rút gọn vì phần lớn cột nguồn đang bị sao chép hoặc tính được.

Trong hệ thống thanh toán thực tế có nhiều giao dịch, refund hoặc retry, grain có thể phải là một payment event
với `payment_id`, không nhất thiết là một payment cho mỗi order.

---

## 13. Vì sao `sales.csv` trở thành view?

Notebook chứng minh:

```text
Revenue/ngày = Σ(quantity × unit_price)
COGS/ngày    = Σ(quantity × product.unit_cogs)
```

`sales.csv` có thể tái tạo từ:

```text
order → order_item → product
```

Do đó nó trở thành:

```text
daily_sales VIEW
```

Lợi ích:

- không lưu cùng một doanh thu ở hai nơi;
- tránh sales tổng hợp lệch với giao dịch;
- khi giao dịch thay đổi, view tính lại kết quả.

Lưu ý định nghĩa:

```text
sales.Revenue = Gross Revenue
              = Σ(quantity × unit_price)
```

Revenue này không trừ `discount_amount`. Trong khi đó `payments.payment_value` là số tiền sau discount.

---

## 14. Vì sao `web_traffic` đứng riêng?

Grain của `web_traffic` là một ngày:

```text
traffic_date
sessions
unique_visitors
page_views
bounce_rate
avg_session_duration_sec
traffic_source
```

Bảng không có:

```text
session_id
customer_id
order_id
```

Vì vậy không thể tạo foreign key tới customer hoặc order. Ghép web traffic và sales theo ngày chỉ là time
alignment để phân tích tương quan, không phải quan hệ giao dịch và không chứng minh conversion.

---

## 15. Vì sao `daily_sales_forecast` đứng riêng?

`daily_sales_forecast` lưu kết quả dự báo:

```text
2023-01-01 → 2024-07-01
```

Trong khi giao dịch thực tế kết thúc:

```text
2022-12-31
```

Các ngày forecast chưa có order thực tế. Vì vậy không thể tạo foreign key từ forecast tới order hoặc sales actual.

Đây là output của mô hình, không phải sự kiện kinh doanh đã xảy ra.

---

## 16. Vì sao các quan hệ có cardinality như vậy?

```text
CUSTOMER 1 ─── 0..N ORDER
ORDER    1 ─── 1..N ORDER_ITEM
PRODUCT  1 ─── 0..N ORDER_ITEM

ORDER    1 ─── 1 PAYMENT
ORDER    1 ─── 0..1 SHIPMENT

ORDER_ITEM N ─── N PROMOTION
ORDER_ITEM 1 ─── 0..1 PRODUCT_RETURN
ORDER_ITEM 1 ─── 0..1 REVIEW

PRODUCT 1 ─── 0..N INVENTORY_SNAPSHOT
```

### Giải thích

- Một customer có thể chưa mua hoặc có nhiều order.
- Một order phải có ít nhất một order item.
- Một product có thể chưa bán hoặc xuất hiện trong nhiều order item.
- Mỗi order quan sát được có đúng một payment.
- Order có thể chưa có shipment.
- Item và promotion là quan hệ nhiều-nhiều nên cần junction table.
- Một item có thể không có hoặc có tối đa một return/review trong snapshot hiện tại.
- Một product có nhiều inventory snapshot theo thời gian.

Cardinality trên sơ đồ phải được hỗ trợ bằng constraint. Ví dụ:

```text
payment.order_id                PRIMARY KEY + FOREIGN KEY
shipment.order_id               PRIMARY KEY + FOREIGN KEY
review(order_id, line_number)   UNIQUE + FOREIGN KEY
product_return(order_id, line_number) UNIQUE + FOREIGN KEY
```

Nếu chỉ vẽ `1:1` nhưng không có `PRIMARY KEY` hoặc `UNIQUE`, database không bảo vệ được quan hệ đó cho dữ liệu
tương lai.

---

## 17. Danh sách 19 bảng và vai trò

| Bảng | Grain/khóa | Vì sao tồn tại? |
|---|---|---|
| `region` | một region | source of truth của region |
| `city` | một city | city thuộc một region |
| `district` | một district | district thuộc một region |
| `zip_area` | một zip | nối zip với city và district |
| `customer` | một customer | hồ sơ khách và nơi cư trú |
| `product_model` | một product name/model | owner của category và segment |
| `product` | một SKU | biến thể size/color, giá và unit COGS |
| `promotion` | một promotion | định nghĩa chương trình khuyến mãi |
| `order` | một order | sự kiện đặt hàng và trạng thái đơn |
| `order_item` | một dòng hàng | sản phẩm, quantity, giá bán và discount |
| `order_item_promotion` | một item–promotion | biểu diễn quan hệ nhiều-nhiều |
| `payment` | payment của một order | số kỳ thanh toán trong snapshot |
| `shipment` | shipment của một order | ngày giao và shipping fee |
| `product_return` | một return event | dòng hàng bị trả, quantity và refund |
| `review_title_label` | một review title | ánh xạ title sang rating |
| `review` | một review | đánh giá của một dòng hàng |
| `inventory_snapshot` | một product tại một snapshot | tồn kho và vận hành SKU |
| `web_traffic` | một ngày traffic | hoạt động website tổng hợp |
| `daily_sales_forecast` | một ngày tương lai | output Revenue và COGS dự báo |

Ngoài 19 bảng trên còn có:

```text
daily_sales VIEW
```

View này tái tạo sales actual theo ngày từ giao dịch.

---

## 18. Vì sao không gom thành một bảng lớn?

Nếu gom tất cả thành một bảng:

- thông tin customer lặp lại trên từng dòng hàng;
- category và segment lặp lại trong nhiều SKU và snapshot;
- một order có nhiều item và promotion sẽ làm fan-out;
- Revenue, return và review có thể bị nhân lên khi join;
- sửa một sự thật phải sửa nhiều dòng;
- khó xác định đâu là source of truth.

3NF giải quyết bằng bốn nguyên tắc:

```text
Mỗi bảng có một grain.
Mỗi grain có một khóa.
Mỗi sự thật có một owner.
Quan hệ được bảo vệ bằng foreign key và constraint.
```

---

## 19. Vì sao không dùng trực tiếp 3NF để forecasting?

3NF và star schema phục vụ hai mục tiêu khác nhau.

| Tiêu chí | 3NF | Star schema | One Big Table |
|---|---|---|---|
| Mục tiêu | hệ thống nguồn/OLTP | dashboard và phân tích | ML/feature |
| Dư thừa | thấp nhất | chấp nhận có chủ đích | cao nhất |
| Số join | nhiều | ít | không hoặc rất ít |
| Update anomaly | thấp nhất | trung bình | cao nhất |
| Người dùng phân tích | khó hơn | dễ hơn | dễ nhất |

Kiến trúc thực tế có thể là:

```text
CSV/Staging
    → Core 3NF
        → Analytics star schema hoặc view
            → Feature table
                → Forecasting model
```

Vì vậy:

- 3NF bảo vệ dữ liệu nguồn;
- star schema hỗ trợ truy vấn phân tích;
- feature table phục vụ model.

Không mô hình nào đúng cho mọi workload.

---

## 20. Những giới hạn phải nói trung thực

1. Dataset hiện là 14 CSV tĩnh, không có nghiệp vụ ghi thật. Update anomaly là rủi ro giả định nếu triển khai
   thành hệ OLTP.
2. `line_number` được sinh từ thứ tự nguồn, không phải khóa gốc từ hệ thống.
3. Tách geography thành bốn bảng đạt 3NF nhưng cần kiểm soát region theo hai đường city/district.
4. `review_title → rating` có thể là dấu vết dữ liệu tổng hợp, không phải quy tắc review phổ quát.
5. Payment trong hệ thống thật có thể cần grain payment event thay vì một payment cho một order.
6. `products.unit_cogs` không có lịch sử hiệu lực; COGS dataset không phải đầy đủ chi phí kế toán.
7. `web_traffic` không có khóa giao dịch nên không thể chứng minh conversion.
8. Thiết kế mới dừng ở mô hình và DDL; chưa có ETL hoặc database production đang chạy.

---

## 21. Câu trả lời khi giảng viên hỏi “tại sao thiết kế như vậy?”

> “Em không chia 14 CSV thành 19 bảng chỉ để có nhiều bảng. Em bắt đầu từ grain và câu chuyện nghiệp vụ.
> `order_items` không có khóa hợp lệ nên em thêm `line_number`. Hai cột promotion là nhóm lặp nên em tạo bảng
> nối. Các thuộc tính sản phẩm bị lặp trong inventory được đưa về bảng product. Những cột sao chép như customer
> city, order zip và payment method được bỏ để mỗi sự thật chỉ có một owner. Các chỉ số tính lại được như daily
> sales và inventory metrics không lưu thành dữ liệu nguồn.
>
> Kết quả là schema 3NF phù hợp cho hệ OLTP và bảo vệ toàn vẹn dữ liệu. Khi phân tích hoặc forecasting, em sẽ
> tạo star schema hoặc view từ core 3NF để giảm số join.”

---

## 22. Các câu hỏi phản biện thường gặp

### “Tại sao không dùng `(order_id, product_id)` làm khóa?”

Vì dữ liệu có 16 cặp bị trùng. Dùng cặp này sẽ làm return/review bị nhập nhằng và có thể gây fan-out.

### “Tại sao phải tạo bảng `order_item_promotion`?”

Vì một item có thể có nhiều promotion. Hai cột `promo_id`, `promo_id_2` là nhóm lặp và không mở rộng được.

### “Tại sao bỏ `payment_value`?”

Vì nó khớp chính xác với tổng net sales của order. Giữ cả hai sẽ tạo hai nguồn sự thật.

### “Tại sao `sales` là view?”

Vì Revenue và COGS theo ngày được tái tạo chính xác từ giao dịch. View tránh lưu tổng hợp bị lệch.

### “Tại sao tách geography nhiều bảng như vậy?”

Để đạt 3NF chặt và tránh lặp region trên hàng nghìn zip. Tuy nhiên production có thể chọn geography phẳng nếu
ưu tiên đơn giản và kiểm soát consistency theo hướng khác.

### “3NF có tốt nhất cho forecasting không?”

Không. 3NF tốt cho hệ thống nguồn. Star schema hoặc feature table phù hợp hơn cho phân tích và forecasting.

### “Thiết kế này đã triển khai database chưa?”

Chưa. Repo hiện có mô hình, DDL, diagram và notebook chứng minh; chưa có ETL hoặc database production.

---

## 23. Cách trình bày bằng diagram

Khi mở [`normalized_schema.drawio`](../normalized_schema.drawio) hoặc
[`docs/design/normalized_schema.mmd`](design/normalized_schema.mmd), trình bày theo thứ tự:

1. Chỉ xương sống `customer → order → order_item ← product`.
2. Giải thích khóa `(order_id, line_number)`.
3. Chỉ bảng nối `order_item_promotion`.
4. Gắn payment/shipment vào order.
5. Gắn return/review vào order item.
6. Gắn inventory snapshot vào product.
7. Giải thích `web_traffic` và forecast đứng riêng.
8. Kết luận `sales` là view.

Không nên bắt đầu bằng cách đọc lần lượt 19 bảng; người nghe sẽ khó nhớ. Bắt đầu từ giao dịch, sau đó mới mở
rộng từng miền.

---

## Kết luận

Thiết kế này được tạo ra từ các quyết định có bằng chứng:

```text
Hiểu business
    → xác định grain
        → kiểm tra khóa
            → tìm nhóm lặp
                → kiểm tra phụ thuộc hàm
                    → loại cột sao chép và dẫn xuất
                        → tạo PK, FK, UNIQUE, CHECK
```

Câu chốt:

> Mô hình 3NF đưa mỗi sự thật về đúng chủ sở hữu và dùng constraint để giữ các sự thật đó nhất quán.
