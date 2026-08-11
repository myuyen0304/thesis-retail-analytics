# Phương pháp xây dựng Từ điển dữ liệu và Sơ đồ ERD

> Tài liệu trình bày phương pháp. Sản phẩm liên quan:
> [data-dictionary.md](data-dictionary.md) · [erd.svg](erd.svg) · [erd.drawio](erd.drawio) · [erd.md](erd.md)

---

## 0. Tóm tắt để trả lời nhanh

Nếu chỉ có một phút để trình bày:

> Bộ dữ liệu gồm 14 tệp CSV, 2,96 triệu bản ghi, 96 trường. Em xây dựng tài liệu theo ba giai đoạn:
> **kiểm kê cấu trúc** → **kiểm định bằng dữ liệu** → **mô hình hóa khái niệm**.
>
> Nguyên tắc xuyên suốt là **không mô tả bất kỳ điều gì chưa được kiểm chứng trực tiếp trên dữ liệu**.
> Mọi con số trong tài liệu đều đến từ việc chạy kiểm tra bằng `pandas`, không suy đoán từ tên cột.
>
> Kết quả: từ điển 96 trường kèm 17 cảnh báo chất lượng dữ liệu, và sơ đồ ERD mức khái niệm ký hiệu Chen
> gồm 13 thực thể, 75 thuộc tính, 15 quan hệ.

---

## 1. Xây dựng Từ điển dữ liệu

### 1.1. Vấn đề đặt ra

Bộ dữ liệu được cung cấp dưới dạng 14 tệp CSV rời rạc, **không kèm bất kỳ tài liệu mô tả nào**. Không
biết cột nào là khóa, các bảng nối với nhau ra sao, cột nào đáng tin, cột nào là rác. Nếu bắt tay vào
mô hình hóa ngay mà không hiểu dữ liệu, mọi kết quả về sau đều không có cơ sở.

### 1.2. Quy trình bốn bước

**Bước 1 — Kiểm kê cấu trúc.** Với từng tệp, xác định: số dòng, danh sách cột, kiểu dữ liệu, số giá trị
phân biệt, số giá trị thiếu, và miền giá trị (min–max cho số, khoảng thời gian cho ngày, danh sách đầy
đủ cho biến phân loại).

Điểm cần nhấn mạnh: **liệt kê đầy đủ giá trị của biến phân loại** thay vì chỉ ghi "kiểu chuỗi". Ví dụ
`order_status` không phải là "một chuỗi bất kỳ" mà chỉ nhận đúng 6 giá trị. Biết được điều này mới phát
hiện ra nó tuân theo một vòng đời có quy luật.

**Bước 2 — Xác định khóa chính.** Với mỗi bảng, kiểm tra tính duy nhất của cột định danh ứng viên. Việc
này tưởng hiển nhiên nhưng đã cho ra một phát hiện quan trọng: bảng `order_items` **không có khóa tự
nhiên hợp lệ**, vì tồn tại 16 cặp `(order_id, product_id)` trùng lặp trên 714.669 dòng. Nếu tin vào giả
định "cặp này là khóa" mà không kiểm tra, mọi phép nối về sau sẽ nhân dòng sai.

**Bước 3 — Kiểm định toàn vẹn tham chiếu.** Với mỗi cặp khóa ngoại giả định, đếm số bản ghi ở bảng con
không tìm thấy giá trị tương ứng ở bảng cha. Đã kiểm tra 16 quan hệ trên tổng cộng 4.055.881 bản ghi,
kết quả **0 bản ghi mồ côi**.

Đồng thời đo **độ phủ ngược lại**: bao nhiêu phần trăm bản ghi ở bảng cha thực sự được tham chiếu. Con
số này quan trọng không kém, vì nó cho biết quan hệ là bắt buộc hay tùy chọn — ví dụ chỉ 74,0% khách
hàng từng đặt hàng, 66,3% sản phẩm từng được bán.

**Bước 4 — Phát hiện cột dư thừa và cột suy diễn.** Đây là bước tốn công nhất nhưng cho giá trị cao nhất.
Cách làm là **đặt giả thuyết về công thức rồi so khớp trên toàn bộ dữ liệu**:

| Giả thuyết đặt ra | Kết quả kiểm chứng |
|---|---|
| `fill_rate = 1 − stockout_days / 30` | Khớp **100%** → là cột suy diễn |
| `stockout_flag = (stockout_days > 0)` | Khớp **100%** → là cột suy diễn |
| `sell_through_rate = units_sold / (stock_on_hand + units_sold)` | Khớp **100%** → là cột suy diễn |
| `days_of_supply = stock_on_hand / (units_sold / 30)` | Khớp **100%** → là cột suy diễn |
| `payment_value = Σ(quantity × unit_price − discount_amount)` | Khớp **100%** → là cột suy diễn |
| `refund_amount = return_quantity × unit_price` | Chỉ khớp **0,6%** → **không** suy diễn được, giữ nguyên |
| `overstock_flag` theo ngưỡng tồn kho | Ngưỡng tốt nhất chỉ khớp **83%** → **không** suy diễn được |

Hai dòng cuối cho thấy phương pháp này có tính phủ định: nó không chỉ xác nhận giả thuyết đúng mà còn
loại được giả thuyết sai. Nếu chỉ nhìn tên cột mà đoán, rất dễ kết luận nhầm `refund_amount` là cột
suy diễn.

### 1.3. Vì sao cột suy diễn lại quan trọng

Đây là điểm nên nhấn mạnh khi trình bày, vì nó nối tài liệu với phần mô hình hóa về sau:

> Cột suy diễn không mang thông tin mới. Nếu đưa cả `stockout_days` lẫn `fill_rate` vào mô hình học máy,
> hai biến này **tương quan hoàn hảo** với nhau, gây hiện tượng đa cộng tuyến. Hệ quả là các thước đo
> tầm quan trọng đặc trưng bị sai lệch, mô hình có thể gán trọng số lớn cho một biến chỉ vì nó là bản
> sao của biến khác. Vì vậy phải phát hiện và loại bỏ chúng ngay từ giai đoạn mô tả dữ liệu.

### 1.4. Kết quả

Từ điển mô tả đầy đủ **96 trường của 14 bảng**, mỗi trường ghi rõ: kiểu dữ liệu, ràng buộc khóa, miền
giá trị, và diễn giải ý nghĩa nghiệp vụ. Kèm theo là bảng tổng hợp **17 cảnh báo chất lượng dữ liệu**
xếp theo mức nghiêm trọng.

Ba phát hiện nổi bật nhất:

1. **`Revenue` và `COGS` tái tạo được chính xác tuyệt đối** từ các bảng giao dịch chi tiết:
   `Revenue(d) = Σ(quantity × unit_price)` và `COGS(d) = Σ(quantity × products.cogs)`, gộp theo
   `orders.order_date`. Sai số tuyệt đối bằng **0,00 trên cả 3.833 ngày**.

   Ba đặc điểm của công thức này phải nêu rõ vì rất dễ hiểu nhầm: doanh thu là **gộp** (không trừ giảm
   giá), tính **cả đơn đã hủy và đơn bị trả**, và mốc thời gian là **ngày đặt hàng** chứ không phải ngày
   giao hàng hay ngày thanh toán.

2. **73,80% đơn hàng được đặt trước ngày đăng ký tài khoản của chính khách hàng đó** — điều bất khả thi
   về nghiệp vụ. Hệ quả thực tiễn: mọi đặc trưng dựa trên `signup_date` (phân tích đoàn hệ, thâm niên
   khách hàng, phân biệt khách mới/cũ) đều không dùng được, phải thay bằng ngày đặt hàng đầu tiên suy
   từ chính bảng `orders`.

3. **814 trên 2.412 sản phẩm chưa từng phát sinh giao dịch**, trong đó 654 sản phẩm có giá bất thường
   dưới 100 đơn vị tiền tệ. Chúng làm lệch mọi thống kê mô tả về giá và biên lợi nhuận nếu không lọc bỏ
   trước khi tính.

---

## 2. Xây dựng Sơ đồ ERD

### 2.1. Chọn đúng loại sơ đồ

Đây là quyết định đầu tiên và cũng là chỗ dễ sai nhất. Có hai loại sơ đồ thường bị gọi lẫn lộn là "ERD":

| | ERD (mức khái niệm) | Relational Diagram (mức logic) |
|---|---|---|
| Ký hiệu | Chen: chữ nhật, hình thoi, elip | Bảng có khóa chính / khóa ngoại |
| Mô tả | Dữ liệu là gì, liên quan ra sao | Dữ liệu lưu trong bảng nào |
| Khóa ngoại | **Không** vẽ thành thuộc tính | Vẽ thành cột FK |
| Dùng cho | Phân tích nghiệp vụ | Thiết kế và triển khai CSDL |

Sản phẩm nộp là **ERD mức khái niệm, ký hiệu Chen**. Quy trình thiết kế CSDL chuẩn đi theo thứ tự
ERD → ánh xạ → Relational Diagram, nên ERD là bước trước.

### 2.2. Bốn quy tắc chuyển từ tệp CSV sang mô hình khái niệm

Điểm mấu chốt: **ERD không phải bản chép lại cấu trúc tệp**. Cần bốn phép biến đổi.

**Quy tắc 1 — Khóa ngoại không vẽ thành thuộc tính.**

Trong mô hình khái niệm, liên kết giữa các thực thể đã được biểu diễn bằng hình thoi quan hệ. Vẽ thêm
cột khóa ngoại là mô tả cùng một thứ hai lần.

Ví dụ: bảng `orders` có cột `customer_id`. Trong ERD, cột này biến mất, thay bằng hình thoi *"đặt"* nối
`CUSTOMERS` với `ORDERS`. Tổng cộng **15 cột khóa ngoại** đã được chuyển thành quan hệ.

**Quy tắc 2 — Nhận diện thực thể yếu.**

Thực thể yếu là thực thể không tự định danh được, phải mượn khóa của thực thể chủ. Cách nhận biết: khóa
chính của nó chính là khóa ngoại trỏ sang bảng khác, hoặc nó không có khóa riêng nào.

| Thực thể yếu | Căn cứ |
|---|---|
| `ORDER_ITEMS` | Không có khóa tự nhiên hợp lệ (16 cặp trùng lặp) |
| `PAYMENTS` | Khóa chính chính là `order_id` của `ORDERS` |
| `SHIPMENTS` | Tương tự `PAYMENTS` |
| `INVENTORY` | Khóa ghép, trong đó `snapshot_date` chỉ là khóa bộ phận |

Chúng được vẽ **viền đôi**, nối với thực thể chủ bằng **hình thoi viền đôi** (quan hệ định danh).

**Quy tắc 3 — Đánh dấu thuộc tính suy diễn.**

Kết quả kiểm chứng công thức ở Bước 4 phần trên được thể hiện trực tiếp lên sơ đồ: thuộc tính suy diễn
vẽ **elip nét đứt**. Có 11 thuộc tính như vậy.

**Quy tắc 4 — Loại bỏ những gì không phải thực thể nghiệp vụ.**

Hai loại bị loại:

- **`sample_submission.csv`** — là khuôn dạng nộp kết quả dự báo, chứa 548 ngày tương lai với giá trị
  chỉ mang tính minh họa. Đây là quy ước kỹ thuật của cuộc thi, không phải dữ liệu nghiệp vụ.
- **Ba cột `product_name`, `category`, `segment` trong `inventory.csv`** — là bản sao nguyên văn từ
  `PRODUCTS`, thuộc về thực thể sản phẩm chứ không phải thuộc tính của tồn kho.

### 2.3. Đối soát số lượng — cách chứng minh không sót, không bịa

Đây là bước nên trình bày, vì nó chứng minh sơ đồ khớp chính xác với dữ liệu gốc:

```
93 cột (13 tệp)  −  15 cột khóa ngoại  −  3 cột sao chép  =  75 thuộc tính
```

Con số 75 khớp đúng với số elip trên sơ đồ. Mọi cột của dữ liệu gốc đều được truy vết: hoặc thành thuộc
tính, hoặc thành quan hệ, hoặc bị loại bỏ có lý do ghi rõ.

### 2.4. Xác định bản số và mức độ tham gia bằng dữ liệu

Bản số **không suy đoán từ tên bảng** mà đo trực tiếp:

| Quan hệ | Đo được | Kết luận |
|---|---|---|
| `ORDERS` → `ORDER_ITEMS` | 1–5 dòng mỗi đơn | 1:N |
| `ORDER_ITEMS` → `RETURNS` | 1–2 lượt trả | 1:N |
| `ORDER_ITEMS` → `REVIEWS` | 1–1 đánh giá | 1:1 |
| `ORDERS` → `PAYMENTS` | Đúng 646.945 = 646.945 | 1:1 |
| `ORDERS` → `SHIPMENTS` | 566.067 trên 646.945 đơn | 1:1, tham gia bộ phận |

Mức độ tham gia đo bằng độ phủ:

| Bên tham gia | Tỷ lệ | Ký hiệu |
|---|---:|---|
| Đơn hàng có dòng hàng | 100% | Đường đôi (toàn bộ) |
| Đơn hàng có thanh toán | 100% | Đường đôi (toàn bộ) |
| Đơn hàng có giao vận | 87,5% | Đường đơn (bộ phận) |
| Khách hàng từng đặt hàng | 74,0% | Đường đơn (bộ phận) |
| Sản phẩm từng được bán | 66,3% | Đường đơn (bộ phận) |
| Dòng hàng có khuyến mại | 38,7% | Đường đơn (bộ phận) |

Sơ đồ dùng **thuần ký hiệu Chen**: bản số chỉ ghi `1` hoặc `N`, còn tính bắt buộc hay tùy chọn thể hiện
bằng đường đôi hay đường đơn — không trộn với hệ ký hiệu `(min, max)`.

### 2.5. Quá trình rà soát và các lần sửa

Sơ đồ trải qua bốn vòng rà soát, mỗi vòng đều tìm ra lỗi. Quá trình này đáng trình bày vì nó cho thấy
cách kiểm chứng chứ không chỉ cho thấy kết quả.

**Lần 1 — Sai loại sơ đồ.** Bản đầu vẽ theo ký hiệu chân chim với đầy đủ cột khóa ngoại. Đó là
Relational Diagram, không phải ERD. Đã vẽ lại theo ký hiệu Chen.

**Lần 2 — `SALES` bị vẽ tách rời.** Lý do ban đầu: trong tệp CSV nó không có cột khóa ngoại nào. Nhưng
kiểm tra cho thấy tập `sales.Date` **trùng khớp tuyệt đối** với tập `orders.order_date` (cùng 3.833
ngày). Quan hệ tồn tại thật, chỉ là không hiện dưới dạng cột khóa ngoại. Đã bổ sung hai quan hệ theo
trục thời gian, vẽ nét đứt để phân biệt với khóa ngoại vật lý.

**Lần 3 — `RETURNS` và `REVIEWS` nối sai đích.** Ban đầu nối riêng lẻ tới `ORDERS` và `PRODUCTS`. Kiểm
tra cho thấy cặp `(order_id, product_id)` của chúng nằm trọn trong `ORDER_ITEMS`, **0 dòng lệch**.
Nghĩa là mỗi lượt trả hàng gắn với một **dòng hàng cụ thể**, không phải với đơn hàng và sản phẩm rời
rạc. Đã thay 4 quan hệ sai bằng 2 quan hệ đúng.

**Lần 4 — Thiếu thuộc tính suy diễn và sai bản số.** Phát hiện thêm 6 thuộc tính suy diễn chưa đánh
dấu, và sửa bản số `ORDER_ITEMS`–`REVIEWS` từ 1:N thành 1:1.

---

## 3. Chuẩn bị câu hỏi

**Hỏi: Vì sao 14 tệp mà sơ đồ chỉ có 13 thực thể?**
> `sample_submission.csv` là khuôn dạng nộp kết quả dự báo, chứa 548 ngày tương lai với giá trị chỉ
> mang tính minh họa. Đó là quy ước kỹ thuật, không phải thực thể nghiệp vụ, nên không đưa vào mô hình
> khái niệm. Nó vẫn được mô tả đầy đủ trong từ điển dữ liệu.

**Hỏi: Vì sao khóa ngoại không xuất hiện trong sơ đồ?**
> Vì đây là ERD mức khái niệm. Liên kết giữa các thực thể đã được biểu diễn bằng hình thoi quan hệ; vẽ
> thêm cột khóa ngoại là mô tả trùng một thứ hai lần. Khóa ngoại chỉ xuất hiện sau bước ánh xạ sang mô
> hình quan hệ.

**Hỏi: Vì sao `ORDER_ITEMS` là thực thể chứ không phải một hình thoi quan hệ?**
> Trong ký hiệu Chen, quan hệ nhiều–nhiều có thuộc tính thường được vẽ thành hình thoi. Nhưng ở đây
> `ORDER_ITEMS` còn tham gia ba quan hệ khác với `PROMOTIONS`, `RETURNS` và `REVIEWS`. Một quan hệ không
> thể có quan hệ con, nên nó bắt buộc phải là thực thể.

**Hỏi: Vì sao một số đường vẽ nét đứt?**
> Nét đứt đánh dấu liên kết không phải khóa ngoại vật lý — gồm hai loại: liên kết theo trục thời gian
> (`SALES`–`ORDERS`, `SALES`–`WEB_TRAFFIC`) và liên kết qua cột dư thừa suy được từ nơi khác
> (`ORDERS`–`GEOGRAPHY`, `CUSTOMERS`–`REVIEWS`).

**Hỏi: Làm sao biết `SALES` là thực thể suy diễn?**
> Vì đã tái tạo được nó chính xác tuyệt đối từ dữ liệu giao dịch:
> `Revenue = Σ(quantity × unit_price)`, `COGS = Σ(quantity × products.cogs)`, gộp theo ngày đặt hàng.
> Sai số tuyệt đối bằng 0,00 trên toàn bộ 3.833 ngày.

**Hỏi: Bộ dữ liệu này có phải dữ liệu thực tế không?**
> Nhiều dấu hiệu cho thấy đây là dữ liệu mô phỏng: toàn vẹn tham chiếu tuyệt đối trên hơn 4 triệu bản
> ghi, `quantity` phân bố đều gần như hoàn hảo trên 8 mức, `fill_rate` là hàm xác định của
> `stockout_days` với mẫu số cố định 30, các trần cứng về thời gian giao vận, và tính mùa vụ ngược với
> quy luật bán lẻ thời trang. Do đó các kết luận nghiệp vụ cần diễn giải thận trọng.

---

## 4. Bảng tra nhanh số liệu

| Chỉ tiêu | Giá trị |
|---|---|
| Số tệp dữ liệu | 14 |
| Tổng bản ghi | 2.960.736 |
| Tổng số trường | 96 |
| Khoảng thời gian | 04/07/2012 – 31/12/2022 (3.833 ngày, không thiếu ngày nào) |
| Giai đoạn dự báo | 01/01/2023 – 01/07/2024 (548 ngày) |
| Quan hệ khóa ngoại đã kiểm định | 16, trên 4.055.881 bản ghi |
| Bản ghi mồ côi | 0 |
| **ERD** — thực thể | 13 (4 thực thể yếu, 1 thực thể suy diễn) |
| **ERD** — thuộc tính | 75 (11 suy diễn, 13 khóa) |
| **ERD** — quan hệ | 15 (5 quan hệ định danh) |
| Cảnh báo chất lượng dữ liệu | 17 |
| Sai số tái tạo biến mục tiêu | 0,00 trên 3.833/3.833 ngày |
