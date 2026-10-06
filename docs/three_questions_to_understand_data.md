# Ba câu hỏi để hiểu và trình bày một bảng dữ liệu

Khi gặp bất kỳ file hoặc bảng nào, không cần cố nhớ toàn bộ cột. Trước tiên chỉ cần trả lời được ba câu:

1. **Một dòng đại diện cho cái gì?** — grain của bảng.
2. **Khóa của dòng đó là gì?** — cách nhận diện duy nhất một bản ghi.
3. **Nó gắn vào đâu trong câu chuyện bán hàng?** — quan hệ và vai trò nghiệp vụ.

Nếu trả lời chắc ba câu này, ta đã hiểu cấu trúc cơ bản của bảng và có thể tiếp tục giải thích các cột, KPI
hoặc phép join.

---

## 1. Vì sao phải hỏi “một dòng đại diện cho cái gì?”

Đây là câu hỏi về **grain**.

Ví dụ:

- một dòng trong `orders` là một đơn hàng;
- một dòng trong `order_items` là một sản phẩm xuất hiện trong một đơn;
- một dòng trong `sales` là kết quả bán hàng của một ngày.

Nếu không biết grain, ta rất dễ đếm dòng hàng thành số đơn hoặc join làm doanh thu bị nhân lên.

### Câu trả lời mẫu

> “Grain của bảng `orders` là một đơn hàng, nghĩa là mỗi dòng ghi lại một order.”

---

## 2. Vì sao phải hỏi “khóa của dòng đó là gì?”

Khóa giúp nhận diện duy nhất một dòng tại đúng grain.

Ví dụ:

- `customer_id` nhận diện một khách hàng;
- `order_id` nhận diện một đơn hàng;
- `(snapshot_date, product_id)` nhận diện tồn kho của một sản phẩm tại một thời điểm.

Không được đoán khóa chỉ từ tên cột. Phải kiểm tra khóa có null hoặc trùng trên toàn bộ dữ liệu hay không.

### Trường hợp đặc biệt của `order_items`

CSV nguồn không có `order_item_id`. Cặp `(order_id, product_id)` cũng không an toàn vì một sản phẩm có thể xuất
hiện nhiều lần trong cùng đơn. Notebook phát hiện 16 cặp như vậy.

Do đó, phân tích hiện tại tái dựng:

```text
Khóa dòng hàng = (order_id, line_number)
```

`line_number` được sinh theo thứ tự dòng trong nguồn. Đây là giả định tái dựng có thể chạy lại, không phải khóa
gốc được hệ thống nguồn cung cấp.

### Câu trả lời mẫu

> “Khóa nguồn của `orders` là `order_id`. Notebook đã kiểm tra cột này không null và không trùng.”

---

## 3. Vì sao phải hỏi “nó gắn vào đâu?”

Câu hỏi này đặt bảng vào câu chuyện vận hành:

```text
CUSTOMER → ORDER → ORDER_ITEM ← PRODUCT
```

Các bảng còn lại bổ sung thông tin:

```text
ORDER_ITEM ↔ PROMOTION
ORDER → PAYMENT
ORDER → SHIPMENT
ORDER_ITEM → RETURN
ORDER_ITEM → REVIEW
PRODUCT → INVENTORY
DATE → WEB_TRAFFIC
DATE → SALES
```

Mũi tên ở đây biểu thị quan hệ nghiệp vụ, không nhất thiết là chiều dữ liệu chạy.

### Câu trả lời mẫu

> “`payments` gắn với `orders` qua `order_id`, vì payment mô tả số tiền và phương thức thanh toán của một đơn.”

---

## 4. Áp dụng cho 14 file CSV

| File | Một dòng đại diện cho gì? | Khóa | Gắn vào đâu? |
|---|---|---|---|
| `customers.csv` | một khách hàng | `customer_id` | khách hàng tạo `orders` và thuộc một `geography` qua `zip` |
| `geography.csv` | một mã zip | `zip` | bổ sung city, district và region cho khách hàng/đơn hàng |
| `products.csv` | một SKU hoặc biến thể sản phẩm | `product_id` | được mua trong `order_items` và được theo dõi trong `inventory` |
| `promotions.csv` | một chương trình khuyến mãi | `promo_id` | được áp dụng cho dòng hàng qua `promo_id`/`promo_id_2` |
| `orders.csv` | một đơn hàng | `order_id` | nối customer với item, payment và shipment |
| `order_items.csv` | một dòng sản phẩm trong đơn | nguồn thiếu khóa; tái dựng `(order_id, line_number)` | nối order với product và tạo Revenue/COGS |
| `payments.csv` | thanh toán của một đơn trong snapshot | `order_id` | gắn với `orders`; chứa payment method, value và installments |
| `shipments.csv` | vận chuyển của một đơn trong snapshot | `order_id` | gắn với `orders`; chứa ngày ship, delivery và shipping fee |
| `returns.csv` | một event trả dòng hàng | `return_id` | gắn về order item qua `(order_id, product_id)` trong nguồn |
| `reviews.csv` | một đánh giá dòng hàng | `review_id` | gắn về order item và customer |
| `inventory.csv` | một sản phẩm tại một snapshot tháng | `(snapshot_date, product_id)` | gắn với `products`; mô tả tồn kho và vận hành SKU |
| `web_traffic.csv` | traffic tổng hợp của một ngày | `date` | so sánh với sales theo ngày; không có FK tới order/customer |
| `sales.csv` | Revenue và COGS actual của một ngày | `Date` | bảng tổng hợp được tái tạo từ giao dịch |
| `sample_submission.csv` | một ngày tương lai cần dự báo | `Date` | định nghĩa khung output, không phải actual |

---

## 5. Cách trả lời khi giảng viên chọn ngẫu nhiên một file

### Ví dụ: `order_items.csv`

> “Một dòng của `order_items` đại diện cho một dòng sản phẩm trong một đơn hàng. File nguồn chưa có khóa dòng
> ổn định, nên notebook sinh `line_number` và dùng `(order_id, line_number)`. Bảng này nối `orders` với
> `products`, đồng thời chứa quantity, unit price, discount và promotion để tính các KPI tiền.”

### Ví dụ: `inventory.csv`

> “Một dòng của `inventory` đại diện cho một sản phẩm tại một snapshot tháng. Khóa là
> `(snapshot_date, product_id)`. Nó gắn với `products` và dùng để phân tích stockout, overstock, days of supply;
> đây là snapshot vận hành chứ không phải một giao dịch bán hàng.”

### Ví dụ: `sales.csv`

> “Một dòng của `sales` đại diện cho Revenue và COGS actual của một ngày, khóa là `Date`. Bảng này là tổng hợp
> theo thời gian. Notebook đã tái tạo chính xác Revenue từ `order_items × orders` và COGS từ
> `order_items × orders × products`.”

### Ví dụ: `web_traffic.csv`

> “Một dòng của `web_traffic` là traffic website tổng hợp trong một ngày, khóa là `date`. Nó chỉ ghép với sales
> theo thời gian vì không có `customer_id`, `session_id` hoặc `order_id`. Do đó correlation traffic–revenue
> không phải conversion hay bằng chứng nhân quả.”

---

## 6. Mẫu trống để dùng cho dataset khác

```markdown
## Tên bảng: `...`

1. Một dòng đại diện cho:
2. Khóa dự kiến:
3. Bảng gắn với:
4. Cột liên kết:
5. Vai trò nghiệp vụ:
6. Điều đã được dữ liệu kiểm chứng:
7. Giả định hoặc giới hạn:
```

---

## Câu chốt để nhớ

```text
Hiểu một bảng = hiểu grain + khóa + quan hệ.
```

Sau khi ba phần này rõ ràng, ta mới đi tiếp tới công thức KPI, kiểm tra chất lượng, EDA và thiết kế database.
