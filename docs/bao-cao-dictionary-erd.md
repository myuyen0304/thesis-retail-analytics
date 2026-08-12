# Báo cáo: Từ điển dữ liệu và Sơ đồ ERD

**Nội dung phụ trách:** Từ điển dữ liệu (Data Dictionary) và Sơ đồ thực thể – liên kết (ERD)
**Sản phẩm:** [data-dictionary.md](data-dictionary.md) · [erd.svg](erd.svg) · [erd.drawio](erd.drawio)

---

## 1. Bối cảnh

Đề tài của nhóm em là dự báo doanh thu và giá vốn hàng bán theo ngày cho một doanh nghiệp bán lẻ thời
trang trực tuyến. Phần em phụ trách là bước đầu tiên: **hiểu và mô tả dữ liệu** trước khi nhóm xây dựng
mô hình.

Bộ dữ liệu gồm **14 tệp CSV, 2.960.736 bản ghi, 96 trường**, trải từ 04/07/2012 đến 31/12/2022 (3.833
ngày liên tục, không thiếu ngày nào). Giai đoạn cần dự báo là 01/01/2023 – 01/07/2024, tức 548 ngày.

Dữ liệu được cung cấp **không kèm tài liệu mô tả**, nên nguyên tắc em đặt ra là: mọi điều ghi trong tài
liệu đều phải kiểm chứng trực tiếp trên dữ liệu bằng Python và thư viện `pandas`, không suy đoán từ tên
cột.

---

## 2. PHẦN A — TỪ ĐIỂN DỮ LIỆU

### 2.1. Từ điển dữ liệu chứa những gì

Với mỗi trường trong 96 trường, em ghi lại năm thông tin:

| Thông tin | Ý nghĩa | Ví dụ |
|---|---|---|
| Kiểu dữ liệu | Số nguyên, số thực, chuỗi, ngày | `order_date` là kiểu ngày |
| Ràng buộc khóa | Khóa chính (PK), khóa ngoại (FK), hay không | `order_id` là PK của `orders` |
| Miền giá trị | Khoảng giá trị hợp lệ hoặc danh sách đầy đủ | `rating` nhận 1–5 |
| Giá trị thiếu | Có thiếu không, thiếu nghĩa là gì | `promo_id` thiếu = không có khuyến mại |
| Ý nghĩa nghiệp vụ | Cột này thực sự nói lên điều gì | `unit_price` là giá bán thực tế, khác giá niêm yết |

Điểm em chú ý: với các cột phân loại, em **liệt kê đầy đủ danh sách giá trị** thay vì chỉ ghi "kiểu
chuỗi". Nhờ vậy mới thấy `order_status` chỉ nhận đúng 6 giá trị và chúng tạo thành một vòng đời có quy
luật.

### 2.2. Mười bốn bảng chia thành bốn nhóm

Em phân nhóm theo bản chất, vì mỗi nhóm đóng vai trò khác nhau trong bài toán.

#### Nhóm 1 — Bảng sự kiện giao dịch (6 bảng)

Ghi nhận từng sự việc xảy ra, có mốc thời gian cụ thể. Đây là nguồn dữ liệu giàu thông tin nhất.

| Bảng | Số dòng | Một dòng là gì | Khóa chính |
|---|---:|---|---|
| `orders` | 646.945 | Một đơn hàng | `order_id` |
| `order_items` | 714.669 | Một dòng sản phẩm trong đơn | *(không có khóa hợp lệ)* |
| `payments` | 646.945 | Thanh toán của một đơn | `order_id` |
| `shipments` | 566.067 | Lần giao vận của một đơn | `order_id` |
| `returns` | 39.939 | Một lượt trả hàng | `return_id` |
| `reviews` | 113.551 | Một đánh giá | `review_id` |

Điểm đáng chú ý ở `order_items`: cặp `(order_id, product_id)` tưởng là khóa nhưng có **16 cặp bị trùng**
trên 714.669 dòng, nên bảng này thực chất **không có khóa tự nhiên hợp lệ**. Nếu tin đó là khóa mà không
kiểm tra, mọi phép nối bảng về sau sẽ bị nhân dòng sai.

#### Nhóm 2 — Bảng danh mục (4 bảng)

Mô tả thuộc tính của các đối tượng được tham chiếu. Không ghi sự kiện, chỉ ghi đặc điểm.

| Bảng | Số dòng | Một dòng là gì |
|---|---:|---|
| `customers` | 121.930 | Một khách hàng |
| `products` | 2.412 | Một mã sản phẩm |
| `geography` | 39.948 | Một mã vùng |
| `promotions` | 50 | Một chương trình khuyến mại |

#### Nhóm 3 — Chuỗi thời gian (3 bảng)

Đã được tổng hợp sẵn theo ngày hoặc tháng.

| Bảng | Số dòng | Một dòng là gì |
|---|---:|---|
| `sales` | 3.833 | Doanh thu và giá vốn của một ngày — **đây là biến cần dự báo** |
| `web_traffic` | 3.652 | Lưu lượng website của một ngày |
| `inventory` | 60.247 | Tồn kho của một sản phẩm trong một tháng |

#### Nhóm 4 — Tệp kỹ thuật (1 tệp)

`sample_submission.csv` gồm 548 dòng, là khuôn dạng nộp kết quả dự báo. Nó chứa các ngày tương lai với
giá trị chỉ mang tính minh họa, **không phải dữ liệu thật**.

### 2.3. Bốn loại cột em phân biệt trong từ điển

Đây là phần quan trọng nhất của từ điển, vì nó quyết định cột nào dùng được cho mô hình.

**Loại 1 — Cột thông tin thật.** Mang dữ liệu độc lập, không suy ra được từ đâu. Ví dụ `quantity`,
`unit_price`, `order_date`. Đây là loại duy nhất thực sự có giá trị cho mô hình.

**Loại 2 — Cột khóa ngoại.** Tồn tại để nối bảng, không phải tính chất của đối tượng. Ví dụ
`orders.customer_id`. Có 15 cột loại này.

**Loại 3 — Cột dư thừa.** Là bản sao nguyên văn của cột ở bảng khác. Ví dụ `payments.payment_method`
trùng khớp 100% với `orders.payment_method`; `customers.city` suy được từ `geography` qua mã vùng.

**Loại 4 — Cột suy diễn.** Tính lại được bằng công thức từ các cột khác trong cùng bảng.

Cách em phát hiện loại 4 là **đặt giả thuyết công thức rồi so khớp trên toàn bộ dữ liệu**:

| Cột nghi ngờ | Công thức thử | Kết quả |
|---|---|---|
| `fill_rate` | `1 − stockout_days / 30` | Khớp **100%** → là cột suy diễn |
| `stockout_flag` | `stockout_days > 0` | Khớp **100%** → là cột suy diễn |
| `sell_through_rate` | `units_sold / (stock_on_hand + units_sold)` | Khớp **100%** → là cột suy diễn |
| `days_of_supply` | `stock_on_hand / (units_sold / 30)` | Khớp **100%** → là cột suy diễn |
| `payment_value` | `Σ(quantity × unit_price − discount_amount)` | Khớp **100%** → là cột suy diễn |
| `refund_amount` | `return_quantity × unit_price` | Chỉ khớp **0,6%** → **không** suy diễn được |
| `overstock_flag` | Ngưỡng tồn kho | Tốt nhất chỉ khớp **83%** → **không** suy diễn được |

Hai dòng cuối là hai giả thuyết bị dữ liệu bác bỏ, nên em giữ nguyên hai cột đó là cột thông tin thật.

**Vì sao phải tách bạch bốn loại này:** cột dư thừa và cột suy diễn không mang thông tin mới. Nếu đưa cả
`stockout_days` lẫn `fill_rate` vào mô hình, hai biến tương quan hoàn hảo với nhau sẽ gây **đa cộng
tuyến** — trọng số mô hình bất ổn định và biểu đồ tầm quan trọng đặc trưng cho kết quả sai lệch.

### 2.4. Kiểm định toàn vẹn tham chiếu

Em kiểm tra xem mọi giá trị khóa ngoại ở bảng con có thực sự tồn tại ở bảng cha hay không. Nếu có đơn
hàng ghi mã khách mà bảng khách hàng không có ai mang mã đó thì gọi là **bản ghi mồ côi**, dữ liệu bị
hỏng.

Kết quả: kiểm tra **15 quan hệ trên 4.815.470 bản ghi, không có bản ghi mồ côi nào**.

Đồng thời em đo **độ phủ ngược lại** — bao nhiêu phần trăm bản ghi ở bảng cha thực sự được tham chiếu.
Con số này về sau dùng để xác định quan hệ bắt buộc hay tùy chọn khi vẽ ERD:

| Đo lường | Kết quả |
|---|---:|
| Khách hàng từng đặt hàng | 74,0% |
| Sản phẩm từng được bán | 66,3% |
| Mã vùng có khách hàng | 78,8% |
| Đơn hàng có dòng hàng | 100% |
| Đơn hàng có giao vận | 87,5% |

### 2.5. Ba phát hiện quan trọng nhất

**Phát hiện 1 — Hai biến mục tiêu tái tạo được chính xác tuyệt đối.**

```
Revenue(ngày d) = Σ (quantity × unit_price)      với mọi dòng hàng của đơn đặt trong ngày d
COGS(ngày d)    = Σ (quantity × products.cogs)
```

Sai số tuyệt đối bằng **0,00 trên cả 3.833 ngày**. Ba đặc điểm rất dễ hiểu nhầm cần nêu rõ:

- Doanh thu là **gộp**, không trừ giảm giá — dù giảm giá chiếm 4,56% tổng doanh thu
- Tính **cả đơn đã hủy và đơn bị trả lại** — nếu loại hai nhóm này, doanh thu chỉ còn 85,25%
- Mốc thời gian là **ngày đặt hàng**, không phải ngày giao hàng hay ngày thanh toán

**Phát hiện 2 — Mâu thuẫn thời gian ở `signup_date`.** Có **73,8% đơn hàng được đặt trước ngày đăng ký
tài khoản** của chính khách hàng đó — điều bất khả thi về nghiệp vụ. Hệ quả là mọi đặc trưng dựa trên
ngày đăng ký (phân tích đoàn hệ, thâm niên khách hàng) đều không dùng được. Hướng xử lý là thay bằng
ngày đặt hàng đầu tiên của mỗi khách, suy trực tiếp từ bảng `orders`.

**Phát hiện 3 — 814 trên 2.412 sản phẩm chưa từng bán.** Trong đó 654 sản phẩm có giá bất thường dưới
100 đơn vị tiền tệ. Chúng làm lệch mọi thống kê về giá và biên lợi nhuận nếu không lọc bỏ trước khi
tính.

---

## 3. PHẦN B — SƠ ĐỒ ERD

### 3.1. Vì sao chọn ERD mức khái niệm, ký hiệu Chen

Có hai loại sơ đồ hay bị gọi lẫn lộn là "ERD":

| | ERD (mức khái niệm) | Relational Diagram (mức logic) |
|---|---|---|
| Ký hiệu | Chen: chữ nhật, hình thoi, elip | Bảng có danh sách cột |
| Trả lời | Dữ liệu **là gì**, liên quan ra sao | Dữ liệu **lưu ở bảng nào** |
| Khóa ngoại | **Không** vẽ | Vẽ thành cột FK |

Quy trình thiết kế cơ sở dữ liệu đi theo thứ tự **ERD → ánh xạ → Relational Diagram**, nên ERD là bước
trước. Sản phẩm em nộp là ERD mức khái niệm.

### 3.2. Ý nghĩa từng ký hiệu trên sơ đồ

| Ký hiệu | Ý nghĩa | Có bao nhiêu |
|---|---|---:|
| Hình chữ nhật | Thực thể | 13 |
| Hình chữ nhật **viền đôi** | Thực thể yếu — không tự định danh được | 4 |
| Hình chữ nhật **viền nét đứt** | Thực thể suy diễn — tính lại được hoàn toàn | 1 |
| Hình thoi | Mối quan hệ | 15 |
| Hình thoi **viền đôi** | Quan hệ định danh — cấp danh tính cho thực thể yếu | 5 |
| Hình elip | Thuộc tính | 75 |
| Elip **chữ gạch chân** | Thuộc tính khóa | 8 |
| Elip **nét đứt** | Thuộc tính suy diễn | 11 |
| Số `1` / `N` cạnh thực thể | Bản số | 30 nhãn |
| **Đường đôi** | Tham gia toàn bộ — mọi bản thể đều phải tham gia | — |
| **Đường đơn** | Tham gia bộ phận — có thể không tham gia | — |
| **Đường nét đứt** | Liên kết không phải khóa ngoại vật lý | 5 |

### 3.3. Quy tắc quan trọng nhất: khóa ngoại không được vẽ

Trong tệp CSV, bảng `orders` có cột `customer_id`. Trong ERD, cột này **biến mất**, thay bằng hình thoi
*"đặt"* nối `CUSTOMERS` với `ORDERS`.

Lý do: hình thoi đó **chính là** lời khẳng định "đơn hàng thuộc về khách hàng". Vẽ thêm cột
`customer_id` nữa là nói cùng một điều hai lần. Nói cách khác, `customer_id` không phải một tính chất
của đơn hàng như ngày đặt hay trạng thái — nó chỉ là cơ chế kỹ thuật để nối bảng, mà mô hình khái niệm
thì không mô tả cơ chế.

Đây là lý do số thuộc tính giảm từ 96 xuống 75:

```
93 cột (13 tệp)  −  15 cột khóa ngoại  −  3 cột sao chép  =  75 thuộc tính
```

Ba cột bị loại là `product_name`, `category`, `segment` trong bảng tồn kho — chúng là bản sao nguyên văn
từ `PRODUCTS`, thuộc về thực thể sản phẩm chứ không phải thuộc tính của tồn kho.

### 3.4. Mười ba thực thể — thuộc tính và ý nghĩa

#### `GEOGRAPHY` — Địa lý · 4 thuộc tính

| Thuộc tính | Loại | Ý nghĩa |
|---|---|---|
| `zip` | **Khóa** | Mã vùng, 39.948 giá trị |
| `city` | Thường | Thành phố, 42 giá trị |
| `region` | Thường | Khu vực: East, Central, West |
| `district` | Thường | Quận/huyện, dạng `District #01`–`#39` |

*Lưu ý khi trình bày:* `district` **không lồng trong** `city` — cùng một mã quận xuất hiện ở tới 16
thành phố khác nhau, nên không dùng nó làm đơn vị địa lý độc lập được.

#### `CUSTOMERS` — Khách hàng · 6 thuộc tính

| Thuộc tính | Loại | Ý nghĩa |
|---|---|---|
| `customer_id` | **Khóa** | Định danh khách hàng |
| `signup_date` | Thường | Ngày đăng ký — **không đáng tin**, xem phát hiện 2 |
| `gender` | Thường | Female, Male, Non-binary |
| `age_group` | Thường | 18-24, 25-34, 35-44, 45-54, 55+ |
| `acquisition_channel` | Thường | Kênh thu hút khách, 6 giá trị |
| `city` | **Suy diễn** | Suy được từ `GEOGRAPHY` qua mã vùng |

*Cột `zip` đã biến thành quan hệ "cư trú tại".*

#### `PRODUCTS` — Sản phẩm · 8 thuộc tính

| Thuộc tính | Loại | Ý nghĩa |
|---|---|---|
| `product_id` | **Khóa** | Định danh, liên tục 1–2.412 |
| `product_name` | Thường | Tên mã hàng |
| `category` | Thường | Streetwear, Outdoor, Casual, GenZ |
| `segment` | Thường | 8 phân khúc |
| `size` | Thường | S, M, L, XL |
| `color` | Thường | 10 màu |
| `price` | Thường | **Giá niêm yết** — chỉ tham chiếu |
| `cogs` | Thường | **Giá vốn đơn vị** — dùng trực tiếp để tính `COGS` |

*Lưu ý khi trình bày:* `segment` **không lồng hoàn toàn trong** `category` — phân khúc `Activewear` xuất
hiện ở cả `Casual` lẫn `Outdoor`. Và `price` khác `unit_price` trong giao dịch: giá niêm yết chỉ mang
tính tham chiếu, giá bán thực tế biến động theo thời gian.

#### `PROMOTIONS` — Khuyến mại · 10 thuộc tính

| Thuộc tính | Loại | Ý nghĩa |
|---|---|---|
| `promo_id` | **Khóa** | Định danh chương trình |
| `promo_name` | Thường | Tên chương trình |
| `promo_type` | Thường | percentage hoặc fixed |
| `discount_value` | Thường | Mức giảm, nghĩa phụ thuộc `promo_type` |
| `start_date`, `end_date` | Thường | Khoảng hiệu lực, khoảng 30 ngày |
| `applicable_category` | Thường | Danh mục áp dụng — **thiếu 80%, nghĩa là áp dụng cho mọi danh mục** |
| `promo_channel` | Thường | Kênh triển khai |
| `stackable_flag` | Thường | Có cho cộng dồn khuyến mại khác không |
| `min_order_value` | Thường | Giá trị đơn tối thiểu |

*Điểm dễ bị hỏi:* giá trị thiếu ở `applicable_category` **mang ý nghĩa rộng nhất** chứ không phải dữ
liệu lỗi. Nếu điền thay thế hoặc loại bỏ 40 dòng đó thì sẽ ra kết luận sai.

#### `ORDERS` — Đơn hàng · 6 thuộc tính

| Thuộc tính | Loại | Ý nghĩa |
|---|---|---|
| `order_id` | **Khóa** | Định danh đơn |
| `order_date` | Thường | Ngày đặt hàng — **mốc thời gian ghi nhận doanh thu** |
| `order_status` | Thường | 6 giá trị theo vòng đời |
| `payment_method` | Thường | 5 phương thức |
| `device_type` | Thường | mobile, desktop, tablet |
| `order_source` | Thường | 6 kênh dẫn khách |

*Vòng đời `order_status` đáng nói khi trình bày:* `created` → `paid` → `shipped` → `delivered` →
`returned`, với `cancelled` là nhánh thoát. Trạng thái này **quyết định hoàn toàn** việc có bản ghi giao
vận hay trả hàng: ba trạng thái đầu chưa phát sinh giao vận, chỉ đơn `returned` mới có bản ghi trả hàng.

*Hai cột `customer_id` và `zip` đã biến thành quan hệ.*

#### `ORDER_ITEMS` — Dòng hàng · 3 thuộc tính · **Thực thể yếu**

| Thuộc tính | Loại | Ý nghĩa |
|---|---|---|
| `quantity` | Thường | Số lượng đặt, 1–8 |
| `unit_price` | Thường | **Giá bán thực tế** tại thời điểm giao dịch |
| `discount_amount` | Thường | Số tiền giảm giá của dòng |

*Vì sao là thực thể yếu:* một "dòng hàng" chỉ có nghĩa khi biết nó thuộc đơn nào — bản thân nó không có
mã định danh riêng, và cặp `(order_id, product_id)` lại có 16 trường hợp trùng.

*Vì sao là thực thể chứ không phải hình thoi:* trong ký hiệu Chen, quan hệ nhiều–nhiều có thuộc tính
thường được vẽ thành hình thoi. Nhưng `ORDER_ITEMS` còn tham gia **ba quan hệ khác** với `PROMOTIONS`,
`RETURNS` và `REVIEWS`. Một quan hệ không thể có quan hệ con, nên nó buộc phải là thực thể. Loại này gọi
là **thực thể kết hợp**.

*Đây là thực thể quan trọng nhất của đề tài,* vì hai biến mục tiêu sinh trực tiếp từ nó.

#### `PAYMENTS` — Thanh toán · 3 thuộc tính · **Thực thể yếu**

| Thuộc tính | Loại | Ý nghĩa |
|---|---|---|
| `installments` | Thường | Số kỳ trả góp: 1, 2, 3, 6, 12 |
| `payment_value` | **Suy diễn** | Bằng tổng `quantity × unit_price − discount_amount` của đơn |
| `payment_method` | **Suy diễn** | Trùng khớp 100% với `orders.payment_method` |

*Điểm đáng nói:* sau khi loại cột khóa ngoại và hai cột suy diễn, bảng này **chỉ còn đúng một thuộc tính
thật** là `installments`. Đó là lý do nó được xếp làm thực thể yếu — về bản chất nó chỉ là phần mở rộng
của `ORDERS`.

*Phân biệt quan trọng:* `payment_value` là số tiền **thực thu** (đã trừ giảm giá), còn `Revenue` trong
`SALES` là doanh thu **gộp**. Hai đại lượng khác nhau, chênh đúng bằng tổng giảm giá.

#### `SHIPMENTS` — Giao vận · 3 thuộc tính · **Thực thể yếu**

| Thuộc tính | Loại | Ý nghĩa |
|---|---|---|
| `ship_date` | Thường | Ngày xuất kho, cách ngày đặt 0–3 ngày |
| `delivery_date` | Thường | Ngày giao thành công, cách ngày xuất kho 2–7 ngày |
| `shipping_fee` | Thường | Phí vận chuyển, **không nằm trong `Revenue`** |

#### `RETURNS` — Trả hàng · 5 thuộc tính

| Thuộc tính | Loại | Ý nghĩa |
|---|---|---|
| `return_id` | **Khóa** | Định danh lượt trả |
| `return_date` | Thường | Ngày trả, cách ngày đặt 5–31 ngày |
| `return_reason` | Thường | 5 lý do |
| `return_quantity` | Thường | Số lượng trả |
| `refund_amount` | Thường | Số tiền hoàn — **không** ảnh hưởng `Revenue` |

#### `REVIEWS` — Đánh giá · 4 thuộc tính

| Thuộc tính | Loại | Ý nghĩa |
|---|---|---|
| `review_id` | **Khóa** | Định danh đánh giá |
| `review_date` | Thường | Ngày đánh giá, cách ngày đặt 3–40 ngày |
| `rating` | Thường | Thang 1–5 |
| `review_title` | Thường | 18 tiêu đề định sẵn, **không phải văn bản tự do** |

#### `INVENTORY` — Tồn kho · 13 thuộc tính · **Thực thể yếu**

| Thuộc tính | Loại | Ý nghĩa |
|---|---|---|
| `snapshot_date` | **Khóa bộ phận** | Ngày chốt sổ, luôn là ngày cuối tháng |
| `stock_on_hand` | Thường | Tồn kho cuối kỳ |
| `units_received` | Thường | Nhập trong kỳ |
| `units_sold` | Thường | Bán trong kỳ theo sổ kho |
| `stockout_days` | Thường | Số ngày hết hàng |
| `overstock_flag` | Thường | Cờ tồn kho vượt ngưỡng |
| `reorder_flag` | Thường | **Hằng số 0 trên toàn bộ dữ liệu** — không mang thông tin |
| `days_of_supply` | **Suy diễn** | `stock_on_hand / (units_sold / 30)` |
| `fill_rate` | **Suy diễn** | `1 − stockout_days / 30` |
| `stockout_flag` | **Suy diễn** | `stockout_days > 0` |
| `sell_through_rate` | **Suy diễn** | `units_sold / (stock_on_hand + units_sold)` |
| `year`, `month` | **Suy diễn** | Tách từ `snapshot_date` |

*Điểm đáng nói:* **6 trên 13 thuộc tính là suy diễn**, tức quá nửa bảng không mang thông tin độc lập.
Cộng thêm `reorder_flag` là hằng số, bảng này chỉ còn 6 cột thực sự có giá trị.

*Vì sao là thực thể yếu:* một dòng tồn kho được xác định bởi **cặp** (ngày chốt sổ, sản phẩm), chứ không
chỉ bởi ngày. `snapshot_date` một mình không đủ định danh nên gọi là **khóa bộ phận**, vẽ elip gạch chân
nét đứt.

#### `SALES` — Doanh thu · 3 thuộc tính · **Thực thể suy diễn**

| Thuộc tính | Loại | Ý nghĩa |
|---|---|---|
| `Date` | **Khóa** | Ngày |
| `Revenue` | **Suy diễn** | `Σ(quantity × unit_price)` |
| `COGS` | **Suy diễn** | `Σ(quantity × products.cogs)` |

*Vì sao vẽ viền nét đứt:* toàn bộ nội dung của thực thể này tính lại được từ `ORDER_ITEMS`, sai số bằng
0,00 trên cả 3.833 ngày. Nó không phải dữ liệu gốc độc lập.

*Đây là biến mục tiêu của đề tài.*

#### `WEB_TRAFFIC` — Lưu lượng website · 7 thuộc tính

| Thuộc tính | Loại | Ý nghĩa |
|---|---|---|
| `date` | **Khóa** | Ngày |
| `sessions` | Thường | Số phiên truy cập |
| `unique_visitors` | Thường | Khách truy cập duy nhất |
| `page_views` | Thường | Lượt xem trang |
| `bounce_rate` | Thường | Tỷ lệ thoát — **biên độ cực hẹp**, sức giải thích thấp |
| `avg_session_duration_sec` | Thường | Thời lượng phiên trung bình |
| `traffic_source` | Thường | Nhãn nguồn truy cập của ngày |

*Điểm dễ hiểu nhầm:* bảng này chỉ có **một dòng cho mỗi ngày** kèm một nhãn nguồn, nên `traffic_source`
**không phải** bảng phân rã theo kênh như tên gọi gợi ý. Các chỉ số là số liệu tổng của toàn website.

*Hạn chế:* bảng bắt đầu từ 2013-01-01, thiếu 181 ngày đầu so với `SALES`, và **không có dữ liệu cho giai
đoạn cần dự báo 2023–2024**.

### 3.5. Mười lăm mối quan hệ — đọc và giải thích

Cách đọc một quan hệ: số cạnh thực thể cho biết **có bao nhiêu bản thể của chính thực thể đó** ứng với
một bản thể bên kia.

#### Nhóm quan hệ quanh `ORDERS`

**1. `CUSTOMERS` (1) — đặt — (N) `ORDERS`**
> Một khách hàng đặt nhiều đơn; một đơn thuộc đúng một khách. Trung bình 7,17 đơn mỗi khách có giao
> dịch, cao nhất 107 đơn.
>
> Phía `ORDERS` là **đường đôi** vì mọi đơn đều phải có khách. Phía `CUSTOMERS` là **đường đơn** vì chỉ
> 74,0% khách từng đặt hàng — 31.684 khách chưa mua bao giờ.

**2. `ORDERS` (1) — gồm — (N) `ORDER_ITEMS`** · *quan hệ định danh*
> Một đơn gồm nhiều dòng hàng, trung bình 1,10 dòng, tối đa 5.
>
> **Đường đôi cả hai phía**: mọi đơn đều có ít nhất một dòng hàng, và mọi dòng hàng đều thuộc về một
> đơn. Hình thoi viền đôi vì `ORDER_ITEMS` là thực thể yếu, chính quan hệ này cấp danh tính cho nó.

**3. `ORDERS` (1) — thanh toán bằng — (1) `PAYMENTS`** · *quan hệ định danh*
> Quan hệ **1:1 tuyệt đối**: đúng 646.945 đơn ứng 646.945 bản ghi thanh toán, không thừa không thiếu.
> Đường đôi cả hai phía.

**4. `ORDERS` (1) — được giao bởi — (1) `SHIPMENTS`** · *quan hệ định danh*
> Bản số 1:1 — một đơn có tối đa một lần giao vận. Nhưng phía `ORDERS` là **đường đơn**: chỉ 87,5% đơn
> có bản ghi giao vận, vì đơn ở trạng thái `cancelled`, `paid`, `created` chưa bao giờ rời kho.
>
> *Đây là ví dụ tốt để giải thích sự khác nhau giữa bản số và mức độ tham gia.*

**5. `ORDERS` (N) — giao đến — (1) `GEOGRAPHY`** · *nét đứt*
> Vẽ nét đứt vì cột `orders.zip` **trùng khớp 100%** với mã vùng của khách hàng tương ứng — đây là quan
> hệ qua cột dư thừa, suy được từ `CUSTOMERS`.

#### Nhóm quan hệ quanh `PRODUCTS`

**6. `PRODUCTS` (1) — được bán trong — (N) `ORDER_ITEMS`** · *quan hệ định danh*
> Một sản phẩm nằm trong nhiều dòng hàng. Phía `PRODUCTS` là **đường đơn** vì chỉ 66,3% sản phẩm từng
> được bán.

**7. `PRODUCTS` (1) — được kiểm kê — (N) `INVENTORY`** · *quan hệ định danh*
> Một sản phẩm được kiểm kê nhiều kỳ, tối đa 126 kỳ. Phía `PRODUCTS` đường đơn vì chỉ 67,3% sản phẩm có
> trong sổ kho.

#### Nhóm quan hệ quanh `ORDER_ITEMS`

**8. `ORDER_ITEMS` (1) — bị trả lại — (N) `RETURNS`**
> **Đây là quan hệ hay bị vẽ sai nhất.** Bảng `returns` có hai cột `order_id` và `product_id`, dễ tưởng
> là hai quan hệ riêng tới `ORDERS` và `PRODUCTS`. Nhưng hai cột đó **đi cùng nhau**: mọi cặp
> `(order_id, product_id)` của `returns` đều nằm trọn trong `order_items`, không lệch dòng nào.
>
> Cách hiểu trực quan: khách trả lại *"hai cái áo size M màu đỏ trong đơn số 5"* — đó là một **dòng
> hàng** cụ thể, không phải trả đơn số 5 và trả sản phẩm X như hai việc riêng biệt.
>
> Bản số là 1:N vì có 39.939 lượt trả trên 39.937 cặp khác nhau, tức có dòng hàng bị trả nhiều lần.

**9. `ORDER_ITEMS` (1) — được đánh giá — (1) `REVIEWS`**
> Cùng lý do như trên. Nhưng bản số là **1:1** vì 113.551 đánh giá ứng đúng 113.551 cặp khác nhau — mỗi
> dòng hàng có tối đa một đánh giá.

**10. `PROMOTIONS` (1) — áp dụng cho — (N) `ORDER_ITEMS`**
> Phía `PROMOTIONS` là **đường đôi** vì cả 50 chương trình đều được sử dụng. Phía `ORDER_ITEMS` là đường
> đơn vì chỉ 38,7% dòng hàng có khuyến mại.

**11. `PROMOTIONS` (1) — cộng dồn cho — (N) `ORDER_ITEMS`** · *nét đứt*
> Quan hệ thứ hai, ứng với cột `promo_id_2` khi cho phép cộng dồn hai khuyến mại. Vẽ nét đứt vì cột này
> **rỗng 99,97%** — chỉ 206 dòng có giá trị, giá trị thông tin không đáng kể.

#### Nhóm quan hệ khác

**12. `CUSTOMERS` (N) — cư trú tại — (1) `GEOGRAPHY`**
> Nhiều khách cùng một mã vùng. Phía `CUSTOMERS` đường đôi vì mọi khách đều có mã vùng; phía `GEOGRAPHY`
> đường đơn vì chỉ 78,8% mã vùng có khách.

**13. `CUSTOMERS` (1) — viết — (N) `REVIEWS`** · *nét đứt*
> Vẽ nét đứt vì `reviews.customer_id` **trùng khớp 100%** với khách hàng của đơn tương ứng — suy được
> qua `ORDERS`, nên là quan hệ dư thừa.

**14. `SALES` (1) — được tổng hợp theo ngày từ — (N) `ORDERS`** · *nét đứt*
> Đây là quan hệ đặc biệt nhất. Trong tệp CSV, `sales` **không có cột nào** trỏ sang `orders`. Nhưng khi
> kiểm tra, tập ngày trong `sales` **trùng khớp tuyệt đối** với tập ngày đặt hàng — cùng 3.833 ngày,
> không lệch ngày nào.
>
> Quan hệ tồn tại thật, chỉ là nối qua **giá trị ngày** chứ không qua mã khóa. Vẽ nét đứt để phân biệt
> với khóa ngoại vật lý. Đường đôi cả hai phía.

**15. `SALES` (1) — có lưu lượng truy cập — (1) `WEB_TRAFFIC`** · *nét đứt*
> Cùng độ chi tiết (mỗi ngày một dòng) nên nối được theo trục thời gian. Phía `SALES` là đường đơn vì
> 181 ngày đầu không có dữ liệu lưu lượng.

### 3.6. Vì sao 14 tệp mà sơ đồ chỉ có 13 thực thể

`sample_submission.csv` là khuôn dạng nộp kết quả dự báo — chứa 548 ngày tương lai với `Revenue` và
`COGS` chỉ là số minh họa, không phải dữ liệu thật. Đó là quy ước kỹ thuật của cuộc thi, không phải thực
thể nghiệp vụ, nên không đưa vào mô hình khái niệm. Nó vẫn được mô tả đầy đủ trong từ điển dữ liệu.

---

## 4. Tổng kết

| Sản phẩm | Nội dung |
|---|---|
| Từ điển dữ liệu | 96 trường của 14 bảng, kèm 17 cảnh báo chất lượng dữ liệu |
| Sơ đồ ERD | 13 thực thể · 75 thuộc tính · 15 quan hệ |
| Trong đó | 4 thực thể yếu · 1 thực thể suy diễn · 11 thuộc tính suy diễn · 5 quan hệ định danh |
| Kiểm định | 15 quan hệ trên 4.815.470 bản ghi, 0 bản ghi mồ côi |

Toàn bộ số liệu đều kiểm chứng được bằng cách chạy lại trên dữ liệu gốc. Đây là cơ sở để nhóm em bước
sang giai đoạn xây dựng đặc trưng và huấn luyện mô hình dự báo.

---

## Phụ lục — Câu hỏi dự đoán

**Vì sao khóa ngoại không xuất hiện trong sơ đồ?**
> Vì đây là ERD mức khái niệm. Liên kết giữa các thực thể đã do hình thoi quan hệ biểu diễn; vẽ thêm cột
> khóa ngoại là mô tả trùng một thứ hai lần. Khóa ngoại chỉ xuất hiện sau bước ánh xạ sang mô hình quan
> hệ ạ.

**Thực thể yếu khác thực thể thường ở chỗ nào?**
> Thực thể yếu không tự định danh được, phải mượn khóa của thực thể chủ. Giống như nói *"phòng số 3"* thì
> vô nghĩa nếu không nói rõ phòng số 3 của tòa nhà nào ạ. Trong bộ dữ liệu này có 4 thực thể yếu.

**Bản số và mức độ tham gia khác nhau ra sao?**
> Bản số trả lời một bên có bao nhiêu bản thể ứng với một bản thể bên kia, ghi bằng số 1 hoặc N. Mức độ
> tham gia trả lời có bắt buộc mọi bản thể đều tham gia quan hệ không, thể hiện bằng đường đôi hay đường
> đơn. Ví dụ `ORDERS` với `SHIPMENTS` là 1:1 nhưng phía `ORDERS` đường đơn, vì chỉ 87,5% đơn có giao vận
> ạ.

**Vì sao `ORDER_ITEMS` là thực thể mà không phải hình thoi?**
> Vì nó còn tham gia ba quan hệ khác với `PROMOTIONS`, `RETURNS` và `REVIEWS`. Trong ký hiệu Chen, một
> quan hệ không thể có quan hệ con, nên nó buộc phải là thực thể ạ.

**Vì sao một số đường vẽ nét đứt?**
> Nét đứt đánh dấu liên kết không phải khóa ngoại vật lý, gồm hai loại: liên kết theo trục thời gian như
> `SALES` với `ORDERS`, và liên kết qua cột dư thừa như `ORDERS` với `GEOGRAPHY` ạ.

**Làm sao chứng minh sơ đồ không bỏ sót cột nào?**
> Em làm phép đối soát: 93 cột của 13 tệp, trừ 15 cột khóa ngoại đã chuyển thành quan hệ, trừ 3 cột sao
> chép từ `PRODUCTS`, bằng đúng 75 thuộc tính trên sơ đồ ạ.

**Em dùng công cụ gì?**
> Em dùng Python với thư viện `pandas` để kiểm định dữ liệu và draw.io để vẽ sơ đồ ạ.
