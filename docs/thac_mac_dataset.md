# Thắc mắc về dataset

Tài liệu này dùng để ghi lại các câu hỏi phát sinh khi đọc dataset và câu trả lời đã được kiểm tra
trên toàn bộ dữ liệu. Không ghi giả định thành sự thật; phần nào dữ liệu không đủ giải thích sẽ
được đánh dấu rõ.

## Mục lục

1. [`promo_id_2` là gì?](#cau-1)
2. [Vì sao hai promotion xuất hiện cùng lúc?](#cau-2)
3. [`promo_id_2` ảnh hưởng `discount_amount` thế nào?](#cau-3)
4. [Những mâu thuẫn không được tự suy diễn](#cau-4)
5. [Vì sao không nên giữ `promo_id_2` trong relational model?](#cau-5)
6. [Kết luận cần nhớ về promotion](#cau-6)
7. [`COGS` là gì và có giá trị business gì?](#cau-7)
8. [Nguồn kiểm chứng trong repo](#cau-8)
9. [Tại sao `geography` được tách thành 4 bảng?](#cau-9)
10. [Nếu `city` và `district` đã có `region`, tại sao còn cần bảng `region`?](#cau-10)
11. [`installments` trong `payments` là gì?](#cau-11)
12. [Tại sao phải sinh bảng junction giữa `order_item` và `promotion`?](#cau-12)
13. [Giải thích thiết kế bốn bảng geography trong `docs/design/normalized_schema.mmd`](#cau-13)
14. [Tại sao tách riêng `product_model`, không để chung một bảng `product`?](#cau-14)

---

<a id="cau-1"></a>

## 1. `promo_id_2` là gì?

### Trả lời ngắn gọn

`promo_id_2` là **mã chương trình khuyến mãi bổ sung thứ hai được áp dụng trên cùng một dòng hàng
(`order_item`)**.

Cả `promo_id` và `promo_id_2` đều tham chiếu đến `promotions.promo_id`.

`promo_id_2` không phải:

- promotion thứ hai của toàn bộ đơn hàng;
- một loại promotion riêng;
- cột chứa giá trị discount;
- bản sao của `promo_id`.

### Bằng chứng từ toàn bộ dữ liệu

Đã kiểm tra toàn bộ `714.669` dòng của `order_items.csv` và toàn bộ `promotions.csv`:

| Kiểm tra | Kết quả |
|---|---:|
| Tổng dòng `order_items` | 714.669 |
| Dòng có `promo_id` | 276.316 |
| Dòng có `promo_id_2` | 206 |
| Tỷ lệ dòng có `promo_id_2` | 0,03% |
| Có `promo_id_2` nhưng thiếu `promo_id` | 0 |
| `promo_id_2 == promo_id` | 0 |
| Số đơn liên quan | 205 |
| Số dòng hàng liên quan | 206 |

Chỉ có đúng hai tổ hợp promotion đồng thời:

| `promo_id` chính | `promo_id_2` bổ sung | Số dòng |
|---|---|---:|
| `PROMO-0013` — Fall Launch 2015 | `PROMO-0015` — Urban Blowout 2015 | 132 |
| `PROMO-0023` — Fall Launch 2017 | `PROMO-0025` — Urban Blowout 2017 | 74 |

Không có tổ hợp thứ ba.

---

<a id="cau-2"></a>

## 2. Vì sao hai promotion xuất hiện cùng lúc?

### Cặp promotion năm 2015

| Thuộc tính | `PROMO-0013` | `PROMO-0015` |
|---|---|---|
| Tên | Fall Launch 2015 | Urban Blowout 2015 |
| Loại | percentage | fixed |
| Giá trị | 10% | 50 |
| Bắt đầu | 2015-08-30 | 2015-07-30 |
| Kết thúc | 2015-10-01 | 2015-09-02 |
| Category áp dụng | tất cả | Streetwear |
| `stackable_flag` | 1 | 0 |
| `min_order_value` | 0 | 200.000 |

Hai khoảng thời gian giao nhau từ `2015-08-30` đến `2015-09-02`. Toàn bộ 132 dòng có cặp này
đều phát sinh đúng trong bốn ngày giao nhau:

| Ngày | Số dòng |
|---|---:|
| 2015-08-30 | 23 |
| 2015-08-31 | 38 |
| 2015-09-01 | 36 |
| 2015-09-02 | 35 |

### Cặp promotion năm 2017

| Thuộc tính | `PROMO-0023` | `PROMO-0025` |
|---|---|---|
| Tên | Fall Launch 2017 | Urban Blowout 2017 |
| Loại | percentage | fixed |
| Giá trị | 10% | 50 |
| Bắt đầu | 2017-08-30 | 2017-07-30 |
| Kết thúc | 2017-10-02 | 2017-09-02 |
| Category áp dụng | tất cả | Streetwear |
| `stackable_flag` | 1 | 0 |
| `min_order_value` | 0 | 150.000 |

Hai khoảng thời gian giao nhau từ `2017-08-30` đến `2017-09-02`. Toàn bộ 74 dòng có cặp này
đều phát sinh đúng trong bốn ngày giao nhau:

| Ngày | Số dòng |
|---|---:|
| 2017-08-30 | 7 |
| 2017-08-31 | 11 |
| 2017-09-01 | 16 |
| 2017-09-02 | 40 |

### Kiểm tra category và thời gian

Trên toàn bộ 206 dòng:

- 206/206 có `order_date` nằm trong khoảng hiệu lực của promotion chính;
- 206/206 có `order_date` nằm trong khoảng hiệu lực của promotion thứ hai;
- 206/206 thuộc category `Streetwear`, đúng category của Urban Blowout.

Kết luận được dữ liệu chứng minh:

> `promo_id_2` chỉ xuất hiện khi Fall Launch và Urban Blowout cùng tồn tại trên một dòng hàng trong
> cửa sổ thời gian chồng lấn.

---

<a id="cau-3"></a>

## 3. `promo_id_2` ảnh hưởng `discount_amount` thế nào?

Với toàn bộ 206 dòng có hai promotion, công thức khớp chính xác là:

```text
discount_amount
    = ROUND(quantity × unit_price × 10% + 50, 2)
```

Trong đó:

- phần `10%` đến từ Fall Launch trong `promo_id`;
- phần `50` đến từ Urban Blowout trong `promo_id_2`.

### Ví dụ `order_id = 320123`

Dòng nguồn:

```text
order_id         = 320123
product_id       = 2331
quantity         = 5
unit_price       = 6,671.13
promo_id         = PROMO-0013
promo_id_2       = PROMO-0015
discount_amount  = 3,385.57
```

Tính lại:

```text
Gross             = 5 × 6,671.13
                  = 33,355.65

Fall Launch       = 10% × 33,355.65
                  = 3,335.565

Urban Blowout     = 50

Discount cuối     = ROUND(3,335.565 + 50, 2)
                  = 3,385.57
```

Kết quả khớp `discount_amount` trong nguồn.

### Điểm bất thường của fixed discount

Khi Urban Blowout nằm một mình trong `promo_id`, dữ liệu dùng:

```text
discount_amount = 50 × quantity
```

Kết quả kiểm tra:

- 5.072/5.072 dòng `PROMO-0015` nằm một mình khớp `50 × quantity`;
- 5.385/5.385 dòng `PROMO-0025` nằm một mình khớp `50 × quantity`.

Nhưng khi Urban Blowout nằm trong `promo_id_2`, dữ liệu chỉ cộng `50` **một lần cho cả dòng hàng**:

```text
discount_amount = gross × 10% + 50
```

không phải:

```text
discount_amount = gross × 10% + 50 × quantity
```

Đây là hành vi quan sát được trong dữ liệu. Dataset không cung cấp tài liệu nghiệp vụ để giải thích
vì sao fixed discount được xử lý khác nhau giữa vị trí thứ nhất và vị trí thứ hai.

---

<a id="cau-4"></a>

## 4. Những mâu thuẫn không được tự suy diễn

### 4.1 Không phải cả hai promotion đều có `stackable_flag = 1`

Dữ liệu promotion ghi:

| Promotion | `stackable_flag` |
|---|---:|
| `PROMO-0013` | 1 |
| `PROMO-0015` | 0 |
| `PROMO-0023` | 1 |
| `PROMO-0025` | 0 |

Vì vậy không được khẳng định “cả hai promotion đều stackable”. Điều duy nhất có thể khẳng định là:

> Dữ liệu thực tế đã gán chúng cùng một dòng hàng và `discount_amount` đã bao gồm cả hai.

Chưa đủ thông tin để biết ý nghĩa chính xác của `stackable_flag`: promotion có cờ `1` được phép
nhận thêm promotion, promotion có cờ `0` không được kết hợp, hay một quy tắc khác.

### 4.2 `min_order_value` không được dữ liệu thực thi

Urban Blowout có ngưỡng:

- `PROMO-0015.min_order_value = 200.000`;
- `PROMO-0025.min_order_value = 150.000`.

Gross của các đơn chứa `promo_id_2` nằm từ `1.841,02` đến `130.740,12`. Nếu các giá trị sử dụng
cùng đơn vị tiền, kết quả là:

```text
Số dòng đạt min_order_value = 0 / 206
```

Do đó không được tuyên bố các dòng này thỏa điều kiện giá trị đơn tối thiểu. Có thể dữ liệu không
thực thi trường này hoặc có quy ước đơn vị/quy tắc không được cung cấp; dataset không đủ bằng chứng
để chọn một trong hai cách giải thích.

### 4.3 Cửa sổ chồng lấn năm 2017 kết thúc ngày 02/09

Urban Blowout 2017 kết thúc `2017-09-02`, nên cửa sổ giao nhau chính xác là:

```text
2017-08-30 → 2017-09-02
```

Không phải đến `2017-10-02`; ngày đó là ngày kết thúc riêng của Fall Launch 2017.

---

<a id="cau-5"></a>

## 5. Vì sao không nên giữ `promo_id_2` trong relational model?

Nguồn đang biểu diễn danh sách promotion bằng các cột đánh số:

```text
ORDER_ITEM(
    ...,
    promo_id,
    promo_id_2
)
```

Cấu trúc này có ba vấn đề:

1. một thuộc tính lặp bị trải thành nhiều cột;
2. muốn tìm mọi dòng dùng promotion X phải tìm trong cả hai cột;
3. nếu một dòng được áp dụng promotion thứ ba thì phải thay đổi schema để thêm `promo_id_3`.

Về business, đây là quan hệ nhiều-nhiều:

```text
ORDER_ITEM M ─── N PROMOTION
```

Phải chuyển thành bảng junction:

```text
ORDER_ITEM_PROMOTION(
    order_id PK, FK,
    line_number PK, FK,
    promo_id PK, FK
)
```

Ví dụ dòng `order_id = 320123` sau khi chuẩn hóa:

```text
order_id  line_number  promo_id
320123    1            PROMO-0013
320123    1            PROMO-0015
```

Kết quả trên toàn bộ dữ liệu:

```text
276.316 association từ promo_id
    206 association từ promo_id_2
--------------------------------
276.522 dòng order_item_promotion
```

Không có association trùng vì không có dòng nào có `promo_id == promo_id_2`.

---

<a id="cau-6"></a>

## 6. Kết luận cần nhớ

> `promo_id_2` là promotion bổ sung thứ hai trên cùng một dòng hàng. Nó chỉ xuất hiện ở 206 dòng
> trong hai cửa sổ Fall Launch chồng với Urban Blowout năm 2015 và 2017. Khi thiết kế relational
> model, không giữ `promo_id_2`; chuyển cả hai cột promotion thành các dòng trong bảng junction
> `order_item_promotion`.

Những điều không được khẳng định vì dữ liệu không hỗ trợ đầy đủ:

- không nói cả hai promotion đều có `stackable_flag = 1`;
- không nói 206 dòng thỏa `min_order_value`;
- không tự giải thích vì sao fixed discount hoạt động khác nhau khi nằm ở `promo_id_2`;
- không xem `promo_id_2` là promotion của toàn bộ order.

---

<a id="cau-7"></a>

## 7. `COGS` là gì và có giá trị business gì?

### Trả lời ngắn gọn

`COGS` là viết tắt của **Cost of Goods Sold — giá vốn hàng bán**.

> `Revenue` cho biết bán được bao nhiêu tiền; `COGS` cho biết lượng hàng đã bán vốn tốn bao nhiêu
> tiền.

Trong dataset, mỗi SKU trong `products.csv` có một cột `cogs`, đại diện cho giá vốn của một đơn vị
sản phẩm. COGS được tính theo ba cấp:

```text
Unit COGS  = products.cogs
Line COGS  = order_items.quantity × products.cogs
Daily COGS = Σ Line COGS của tất cả dòng hàng trong ngày
```

`sales.csv.COGS` được tái tạo chính xác từ `orders`, `order_items` và `products` bằng công thức
trên.

### Ví dụ `order_id = 46270`

Đơn này có:

```text
quantity          = 4
unit_price        = 615.65
unit_cogs         = 486.680153
discount_amount   = 369.39
```

Tính Revenue và COGS:

```text
Gross Revenue = 4 × 615.65
              = 2,462.60

COGS          = 4 × 486.680153
              ≈ 1,946.72
```

Lợi nhuận gộp trước discount:

```text
Gross Profit = Gross Revenue − COGS
             = 2,462.60 − 1,946.72
             = 515.88

Gross Margin = Gross Profit / Gross Revenue
             ≈ 20,95%
```

Khách thực trả sau discount:

```text
Net Payment = Gross Revenue − Discount
            = 2,462.60 − 369.39
            = 2,093.21
```

Nếu so tiền thực trả với giá vốn:

```text
Net Payment − COGS
= 2,093.21 − 1,946.72
= 146.49
```

Ví dụ này cho thấy một đơn có Revenue khá cao nhưng lợi nhuận còn lại sau discount có thể thấp.

### Giá trị business của COGS

#### Đo lợi nhuận thay vì chỉ nhìn doanh thu

Hai ngày cùng có Revenue 10 triệu nhưng không có chất lượng kinh doanh giống nhau:

```text
Ngày A: Revenue = 10 triệu, COGS = 6 triệu → Gross Profit = 4 triệu
Ngày B: Revenue = 10 triệu, COGS = 9 triệu → Gross Profit = 1 triệu
```

Nếu chỉ dự báo Revenue thì không biết doanh nghiệp đang bán hàng với biên lợi nhuận cao hay thấp.

#### Đánh giá hiệu quả promotion

Promotion có thể làm số lượng bán tăng nhưng làm lợi nhuận giảm:

```text
Net Sales = Gross Revenue − Discount
```

Nếu:

```text
Net Sales < COGS
```

thì số tiền thu sau discount thấp hơn giá vốn, chưa tính thêm chi phí vận hành. Trong dataset,
Urban Blowout vào tháng 8 năm lẻ có thể làm `COGS > Revenue`; đây là tín hiệu promotion rất mạnh
hoặc bất thường về quan hệ giá bán–giá vốn cần được mô hình hóa riêng.

#### So sánh khả năng sinh lời của sản phẩm

Ở cấp dòng hàng có thể tính:

```text
Unit Margin = unit_price − unit_cogs
Margin %    = (unit_price − unit_cogs) / unit_price
```

Nhờ đó có thể phân biệt:

- sản phẩm bán nhiều nhưng biên lợi nhuận thấp;
- sản phẩm bán ít nhưng biên lợi nhuận cao;
- category hoặc product mix nào làm COGS tăng nhanh hơn Revenue.

#### Lập kế hoạch tiền hàng

Forecast COGS giúp ước lượng giá vốn gắn với lượng hàng dự kiến bán. Ví dụ:

```text
Forecast Revenue = 100 triệu
Forecast COGS    = 75 triệu
```

Doanh nghiệp biết khoảng 75 triệu giá vốn liên quan đến doanh số dự kiến, từ đó hỗ trợ kế hoạch
mua hàng và dòng tiền.

### Công thức cần nhớ trong bài toán này

```text
Revenue      = Σ(quantity × unit_price)       -- gross, chưa trừ discount
COGS         = Σ(quantity × products.cogs)
Gross Profit = Revenue − COGS
Gross Margin = (Revenue − COGS) / Revenue
COGS Ratio   = COGS / Revenue
```

`COGS Ratio` cho biết để tạo ra một đồng Revenue cần bao nhiêu đồng giá vốn:

- tỷ lệ thấp hơn thường cho thấy biên lợi nhuận gộp cao hơn;
- tỷ lệ gần `1` cho thấy biên lợi nhuận rất mỏng;
- tỷ lệ lớn hơn `1` nghĩa là COGS lớn hơn Revenue theo định nghĩa của dataset.

### Giới hạn khi diễn giải COGS trong dataset

COGS của dataset chỉ được tính từ:

```text
quantity × products.cogs
```

Nó không bao gồm:

- `shipping_fee`;
- discount;
- refund;
- chi phí marketing;
- lương nhân viên;
- chi phí kho và chi phí vận hành khác.

Ngoài ra, công thức tái tạo `sales.csv` cộng các dòng hàng mà không lọc `order_status` và không
điều chỉnh return. Vì vậy đây là **COGS theo định nghĩa của dataset/bài thi**, chưa chắc tương đương
COGS kế toán cuối cùng của một doanh nghiệp thực tế.

`products.cogs` cũng là một giá trị ở cấp sản phẩm trong file danh mục; nguồn không cung cấp lịch
sử thay đổi giá vốn theo thời gian. Không được tự suy luận đây là giá vốn lịch sử chính xác tại mọi
ngày nếu không có thêm dữ liệu hiệu lực.

### Kết luận cần nhớ

> Revenue đo quy mô bán hàng; COGS đo chi phí trực tiếp của lượng hàng đó. Dự báo cả hai mới cho
> biết doanh nghiệp đang tăng trưởng có lợi nhuận hay chỉ bán nhiều với biên lợi nhuận thấp.

---

<a id="cau-8"></a>

## 8. Nguồn kiểm chứng trong repo

- `data/order_items.csv`: toàn bộ dòng hàng và hai cột promotion.
- `data/promotions.csv`: định nghĩa 50 promotion.
- `data/orders.csv`: ngày và tổng gross của các đơn liên quan.
- `data/products.csv`: category của sản phẩm.
- `data/sales.csv`: Revenue và COGS tổng hợp theo ngày.
- `notebooks/01_exploration/eda.ipynb`: kiểm chứng công thức tái tạo Revenue và COGS.
- `notebooks/02_design/data_model.ipynb` §5.5: kiểm tra quan hệ M:N với promotion.
- `notebooks/02_design/normalization.ipynb` §2.2: kiểm tra nhóm cột lặp và bảng junction.
- `normalized_schema.md` §2.2: giải thích chuẩn hóa `promo_id`/`promo_id_2`.

---

<a id="cau-9"></a>

## 9. Tại sao `geography` được tách thành 4 bảng?

### Trả lời ngắn gọn

`geography.csv` đang đặt bốn loại sự thật vào cùng một bảng:

```text
zip | city | district | region
```

Dữ liệu chứng minh các phụ thuộc:

```text
zip      → city
zip      → district
city     → region
district → region
```

Nếu giữ bảng phẳng, city, district và region sẽ bị lặp lại trên rất nhiều zip. Thiết kế 3NF tách thành:

```text
region
city
district
zip_area
```

Mục tiêu là đưa mỗi sự thật về một nơi sở hữu và tránh phải sửa cùng một region trên nhiều dòng zip.

### Ví dụ minh họa trước khi tách

Ví dụ dưới đây dùng giá trị minh họa để giải thích cấu trúc, không phải trích nguyên văn các dòng nguồn:

| `zip` | `city` | `district` | `region` |
|---:|---|---|---|
| 10001 | Bac Ninh | District #05 | East |
| 10002 | Bac Ninh | District #05 | East |
| 10003 | Bac Ninh | District #08 | East |
| 10004 | Hai Duong | District #05 | East |
| 20001 | Da Nang | District #02 | Central |

Ta thấy:

- `East` bị lặp trên nhiều dòng;
- `Bac Ninh` bị lặp theo từng zip;
- `District #05` cũng bị lặp theo từng zip.

Nếu `Bac Ninh` đổi region, bảng phẳng buộc phải sửa tất cả dòng zip của Bac Ninh. Bỏ sót một dòng sẽ tạo dữ
liệu không nhất quán.

### Sau khi tách

#### Bảng `region`

Mỗi region chỉ xuất hiện một lần:

| `region` |
|---|
| East |
| Central |
| West |

```text
PRIMARY KEY = region
```

#### Bảng `city`

Mỗi city tham chiếu một region:

| `city` | `region` |
|---|---|
| Bac Ninh | East |
| Hai Duong | East |
| Da Nang | Central |

```text
PRIMARY KEY = city
FOREIGN KEY = region
```

#### Bảng `district`

Mỗi district tham chiếu một region:

| `district` | `region` |
|---|---|
| District #05 | East |
| District #08 | East |
| District #02 | Central |

```text
PRIMARY KEY = district
FOREIGN KEY = region
```

#### Bảng `zip_area`

Mỗi zip chỉ cần chỉ ra city và district:

| `zip` | `city` | `district` |
|---:|---|---|
| 10001 | Bac Ninh | District #05 |
| 10002 | Bac Ninh | District #05 |
| 10003 | Bac Ninh | District #08 |
| 10004 | Hai Duong | District #05 |
| 20001 | Da Nang | District #02 |

```text
PRIMARY KEY = zip
FOREIGN KEY = city
FOREIGN KEY = district
```

`zip_area` không cần lưu lại `region` vì region có thể được tìm qua city hoặc district.

### Vì sao không dùng một cây `region → city → district → zip`?

Dataset không chứng minh city chứa district theo một cây duy nhất. City và district **cắt chéo nhau**:

```text
Bac Ninh
├── District #05
└── District #08

District #05
├── Bac Ninh
└── Hai Duong
```

Một city có thể xuất hiện với nhiều district, đồng thời một district có thể xuất hiện với nhiều city. Vì vậy
không có hai phụ thuộc:

```text
city → district
district → city
```

Mô hình đúng theo dữ liệu có dạng hình thoi:

```text
              REGION
              /    \
           CITY    DISTRICT
              \    /
              ZIP_AREA
                  |
               CUSTOMER
```

### Ví dụ tìm khu vực của một khách hàng

Giả sử customer lưu:

| `customer_id` | `zip` |
|---:|---:|
| 44051 | 10001 |

Ta lần theo:

```text
customer 44051
    → zip 10001
        → city Bac Ninh
        → district District #05
            → region East
```

`customer` không cần lưu lại city, district hoặc region vì có thể suy ra các thông tin này từ `zip`.

### Lợi ích của việc tách

Giả sử `Bac Ninh` chuyển từ `East` sang một region khác.

Nếu giữ bảng phẳng, phải sửa mọi dòng zip thuộc Bac Ninh:

```text
10001 | Bac Ninh | ... | East
10002 | Bac Ninh | ... | East
10003 | Bac Ninh | ... | East
...
```

Nếu có 1.000 zip thì có thể phải sửa 1.000 dòng. Với thiết kế tách bảng, chỉ cần sửa một dòng trong `city`:

| `city` | `region` |
|---|---|
| Bac Ninh | Region mới |

Mọi zip thuộc Bac Ninh sẽ nhận region mới khi join.

### Điểm yếu của thiết kế 4 bảng

Thiết kế này đạt 3NF nhưng một zip có thể tìm region theo hai đường:

```text
zip → city → region
zip → district → region
```

Nếu dữ liệu bị nhập sai:

```text
Bac Ninh     → East
District #05 → Central
```

thì cùng một zip sẽ trả về hai region khác nhau. Database cần validation hoặc ETL test để bảo đảm hai đường luôn
nhất quán.

Đánh đổi thực tế:

| Phương án | Ưu điểm | Nhược điểm |
|---|---|---|
| Tách 4 bảng | đạt 3NF, ít dư thừa, cập nhật một nơi | nhiều join, phải kiểm tra region theo hai đường |
| Giữ geography phẳng | dễ hiểu và truy vấn | region lặp nhiều lần, có nguy cơ update anomaly |

Vì tài liệu `normalized_schema.md` đang trình bày bài toán chuẩn hóa nên chọn phương án bốn bảng. Trong production,
phương án phẳng vẫn có thể hợp lý nếu workload chủ yếu là phân tích và hệ thống có cách kiểm soát consistency khác.

### Câu trả lời khi giảng viên hỏi

> “Em tách geography thành `region`, `city`, `district` và `zip_area` vì dữ liệu chứng minh `city → region` và
> `district → region`. Nếu giữ region trong từng dòng zip thì region sẽ bị lặp hàng nghìn lần và dễ phát sinh
> update anomaly. `zip_area` giữ quan hệ giữa zip với city và district. Tuy nhiên city và district cắt chéo nhau,
> nên đây không phải cây địa lý đơn giản; production cần kiểm tra hai đường city–region và district–region luôn
> nhất quán.”

### Kết luận cần nhớ

```text
region   = danh mục vùng
city     = thành phố và vùng của thành phố
district = quận/huyện và vùng của quận/huyện
zip_area = zip thuộc city và district nào
```

> Tách geography thành bốn bảng giúp mỗi sự thật địa lý chỉ được lưu một lần. Đây là quyết định đạt 3NF, nhưng
> phải chấp nhận thêm join và kiểm soát tính nhất quán của region theo hai đường.

---

<a id="cau-10"></a>

## 10. Nếu `city` và `district` đã có cột `region`, tại sao còn cần bảng `region`?

### Trả lời ngắn gọn

Nếu bỏ bảng `region` nhưng vẫn giữ cột `region` trong `city` và `district` thì **không mất thông tin nào**.

Ví dụ không có bảng `region`:

```text
city(city PK, region)
district(district PK, region)
```

Ta vẫn biết Bac Ninh thuộc East và District #02 thuộc Central.

Vì vậy bảng `region` không được tạo để tránh mất dữ liệu. Nó là một lựa chọn thiết kế
**reference/master data**, chủ yếu để quản lý danh sách region hợp lệ và cho các bảng con tham chiếu bằng foreign
key.

### Không có bảng `region` thì dữ liệu vẫn đầy đủ

#### Bảng `city`

| `city` | `region` |
|---|---|
| Bac Ninh | East |
| Da Nang | Central |

#### Bảng `district`

| `district` | `region` |
|---|---|
| District #05 | East |
| District #02 | Central |

Hai bảng trên vẫn chứa đầy đủ quan hệ:

```text
city → region
district → region
```

Không cần bảng `region` để khôi phục các thông tin này.

### Vậy bảng `region` mang lại giá trị gì?

#### 1. “Quản lý miền giá trị dùng chung” nghĩa là gì?

**Miền giá trị** của một cột là tập hợp các giá trị mà cột đó được phép nhận.

Trong dataset này, miền giá trị hợp lệ của `region` là:

```text
{Central, East, West}
```

Từ “dùng chung” có nghĩa là **cả `city.region` và `district.region` đều phải dùng đúng cùng một danh sách trên**,
thay vì mỗi bảng tự chấp nhận một danh sách khác nhau.

Nếu không có nơi quản lý chung, dữ liệu có thể trở thành:

```text
city
city         region
Bac Ninh     East
Da Nang      Central

district
district      region
District #05  EAST
District #02  Central Region
```

Con người có thể hiểu `East` và `EAST` cùng chỉ một vùng, nhưng database coi chúng là hai chuỗi khác nhau. Khi
`GROUP BY region`, kết quả có thể bị tách thành nhiều nhóm giả:

```text
East
EAST
Central
Central Region
```

Bảng `region` đóng vai trò như danh sách chuẩn duy nhất:

| `region` |
|---|
| Central |
| East |
| West |

Muốn thêm một vùng mới như `South`, phải thêm `South` vào bảng `region` trước. Sau đó cả `city` và `district`
mới có thể sử dụng đúng giá trị đó. Đây là ý nghĩa cụ thể của **quản lý miền giá trị dùng chung**.

#### 2. “Bảo vệ bằng foreign key” nghĩa là gì?

Khi khai báo:

```sql
CREATE TABLE region (
    region VARCHAR(16) PRIMARY KEY
);

CREATE TABLE city (
    city   VARCHAR(64) PRIMARY KEY,
    region VARCHAR(16) NOT NULL REFERENCES region(region)
);

CREATE TABLE district (
    district VARCHAR(32) PRIMARY KEY,
    region   VARCHAR(16) NOT NULL REFERENCES region(region)
);
```

foreign key buộc giá trị được nhập vào `city.region` hoặc `district.region` **phải tồn tại trước trong
`region.region`**.

Ví dụ bảng `region` chỉ có:

```text
Central, East, West
```

Lệnh hợp lệ:

```sql
INSERT INTO city(city, region)
VALUES ('Bac Ninh', 'East');
```

Database chấp nhận vì `East` đã tồn tại trong bảng `region`.

Lệnh không hợp lệ:

```sql
INSERT INTO city(city, region)
VALUES ('Hai Phong', 'Eats');
```

Database từ chối vì `Eats` không tồn tại trong bảng `region`. Nhờ đó các lỗi gõ sai hoặc cách viết không thống
nhất như sau không lọt vào bảng con:

```text
Eats
EAST
WESTT
Central Region
```

Đó là ý nghĩa của câu **“FK bảo vệ dữ liệu”**: database kiểm tra điều kiện tồn tại này ở thời điểm `INSERT` hoặc
`UPDATE`, thay vì chờ analyst phát hiện lỗi sau khi dữ liệu đã được sử dụng.

FK còn bảo vệ chiều ngược lại. Nếu `city` vẫn đang tham chiếu `East`, database thông thường không cho xóa dòng
`East` khỏi bảng `region` một cách tùy tiện:

```sql
DELETE FROM region WHERE region = 'East';
```

Việc xóa sẽ bị từ chối, trừ khi schema chủ động cấu hình hành vi khác như `ON DELETE CASCADE`.

#### 3. FK này bảo vệ được gì và không bảo vệ được gì?

FK hiện tại bảo đảm:

```text
city.region     phải thuộc {Central, East, West}
district.region phải thuộc {Central, East, West}
```

Nhưng nó **không bảo đảm** city và district của cùng một zip được gán cùng region.

Ví dụ sau vẫn vượt qua cả hai FK vì `East` và `West` đều tồn tại trong bảng `region`:

```text
city
Bac Ninh → East

district
District #05 → West

zip_area
21122 → Bac Ninh + District #05
```

Từ zip `21122`, đi theo city sẽ ra `East`, còn đi theo district lại ra `West`. Hai FK riêng lẻ không phát hiện
được mâu thuẫn giữa hai đường này. Muốn bảo vệ quy tắc đó phải có thêm ETL test, trigger hoặc thiết kế constraint
khác.

Vì vậy cần nói chính xác:

> FK tới bảng `region` chỉ kiểm soát **region có thuộc danh sách hợp lệ hay không**. Nó không tự kiểm soát
> **city và district của cùng một zip có cùng region hay không**.

Nếu không có bảng `region`, có thể dùng cùng một `CHECK`, `ENUM` hoặc ETL validation cho cả hai bảng để đạt mục
đích kiểm soát miền tương tự:

```sql
CHECK (region IN ('Central', 'East', 'West'))
```

#### 4. Có một nơi quản lý danh sách region

Nếu sau này region có thêm thuộc tính:

```text
region_id
region_name
region_code
manager
warehouse
timezone
```

thì bảng riêng trở nên có giá trị rõ ràng.

Ví dụ:

| `region_id` | `region_name` | `manager` |
|---|---|---|
| R01 | East | Nguyen A |
| R02 | Central | Tran B |
| R03 | West | Le C |

`city` và `district` chỉ cần tham chiếu `region_id`.

#### 5. Quản lý việc đổi tên

Không có bảng `region`, tên `East` nằm trong nhiều dòng của `city` và `district`. Nếu đổi thành `Eastern`, phải
sửa nhiều dòng ở nhiều bảng.

Nếu dùng khóa ổn định:

```text
region_id = R01
region_name = East
```

thì chỉ cần đổi `region_name`; các bảng con vẫn tham chiếu `R01`.

### Hạn chế của schema hiện tại

Schema hiện tại dùng:

```text
region(region PK)
city(city PK, region FK)
district(district PK, region FK)
```

Nghĩa là tên `East`, `Central`, `West` vẫn được lưu lặp trong các khóa ngoại của `city` và `district`. Vì bảng
`region` hiện chỉ có một cột, lợi ích giảm lưu trữ hoặc giảm lặp không lớn.

Trong mô hình hiện tại, bảng `region` chủ yếu cung cấp:

- danh sách giá trị hợp lệ;
- foreign key bảo vệ dữ liệu;
- một điểm mở rộng nếu region có thêm thuộc tính trong tương lai.

Thiết kế thực dụng hơn khi region là thực thể nghiệp vụ có thể dùng:

```text
region(
    region_id PK,
    region_name UNIQUE
)

city(
    city PK,
    region_id FK
)

district(
    district PK,
    region_id FK
)
```

### 3NF có bắt buộc phải tạo bảng `region` không?

**Không bắt buộc.**

Bảng sau vẫn có thể đạt 3NF:

```text
city(city PK, region)
```

Trong bảng này chỉ có phụ thuộc:

```text
city → region
```

Không có thuộc tính không khóa khác tạo phụ thuộc bắc cầu. Tương tự:

```text
district(district PK, region)
```

cũng có thể đạt 3NF.

Do đó, việc tạo bảng `region` là quyết định mô hình hóa region thành một thực thể/danh mục dùng chung, không phải
yêu cầu bắt buộc của 3NF.

### Ba phương án đều có thể hợp lệ

#### Phương án A — Có bảng `region`

```text
region
├── city
└── district
```

Phù hợp khi:

- muốn foreign key kiểm soát region hợp lệ;
- region có hoặc sẽ có thuộc tính riêng;
- region là thực thể nghiệp vụ cần được quản lý.

#### Phương án B — Không có bảng `region`

```text
city(city, region)
district(district, region)
```

Phù hợp khi:

- region chỉ là nhãn đơn giản;
- chỉ có vài giá trị cố định;
- region không có thuộc tính riêng;
- muốn giảm số bảng và số join.

Có thể kiểm soát giá trị bằng:

```sql
CHECK (region IN ('East', 'Central', 'West'))
```

#### Phương án C — Giữ geography phẳng

```text
geography(zip, city, district, region)
```

Phù hợp khi dữ liệu chủ yếu dùng để phân tích, ít cập nhật và cần truy vấn đơn giản. Đổi lại, region bị lặp trên
nhiều zip.

### Bổ sung cho kết luận ở câu 9

Việc tách `city`, `district` và `zip_area` xử lý các phụ thuộc địa lý và giảm lặp tại grain zip. Tuy nhiên, tách
thêm bảng `region` một cột **không phải điều bắt buộc để đạt 3NF**.

Phát biểu chính xác hơn là:

> Bảng `region` được giữ để biến region thành một danh mục dùng chung và tạo đích tham chiếu cho foreign key.
> Nếu region chỉ là ba nhãn cố định, không có thuộc tính riêng, có thể bỏ bảng này và dùng `CHECK`/`ENUM` mà không
> làm mất thông tin.

### Câu trả lời khi giảng viên hỏi

> “Miền giá trị dùng chung ở đây là danh sách ba region hợp lệ: `Central`, `East`, `West`. Cả `city.region` và
> `district.region` đều là foreign key tới danh sách này, nên database chấp nhận `East` nhưng từ chối giá trị gõ
> sai như `Eats` vì nó không tồn tại trong bảng `region`. FK cũng ngăn xóa một region đang được bảng con sử dụng.
> Tuy nhiên, FK này chỉ kiểm tra region có hợp lệ hay không; nó không bảo đảm city và district của cùng một zip
> được gán cùng region. Nếu bỏ bảng `region` nhưng vẫn giữ cột region ở `city` và `district` thì không mất thông
> tin và hai bảng vẫn có thể đạt 3NF. Với chỉ ba nhãn cố định, dùng cùng một `CHECK` hoặc `ENUM` ở hai bảng cũng
> đạt mục đích kiểm soát miền. Vì vậy bảng `region` là lựa chọn quản lý master data và mở rộng tương lai, không
> phải yêu cầu bắt buộc của 3NF.”

### Kết luận cần nhớ

```text
Không có bảng region ≠ mất thông tin.
Có bảng region = có danh mục dùng chung + FK + nơi mở rộng.
```

> Tạo bảng `region` là một quyết định thiết kế có đánh đổi. Không nên giải thích rằng 3NF bắt buộc mọi giá trị
> phân loại phải trở thành một bảng riêng.

---

<a id="cau-11"></a>

## 11. `installments` trong `payments` là gì?

### Trả lời ngắn gọn

`installments` là **số kỳ thanh toán được ghi nhận cho một đơn hàng**.

```text
installments = 1   → thanh toán một kỳ
installments = 3   → chia khoản thanh toán thành ba kỳ
installments = 12  → chia khoản thanh toán thành mười hai kỳ
```

Grain của `payments.csv` là một payment tổng hợp cho một đơn, nên mỗi `order_id` chỉ có một giá trị
`installments`.

### Bằng chứng từ toàn bộ dữ liệu

Toàn bộ 646.945 dòng của `payments.csv` không thiếu `installments` và chỉ có năm giá trị:

| `installments` | Số đơn |
|---:|---:|
| 1 | 262.866 |
| 2 | 1.094 |
| 3 | 218.949 |
| 6 | 109.910 |
| 12 | 54.126 |

Vì mọi giá trị đều dương, relational model có thể khai báo:

```sql
installments SMALLINT NOT NULL CHECK (installments > 0)
```

### Quan hệ với `payment_value`

Trong dataset:

```text
payment_value = Σ(quantity × unit_price − discount_amount)
```

`payment_value` là tổng tiền net của đơn sau discount, còn `installments` cho biết tổng tiền đó được ghi nhận
với bao nhiêu kỳ thanh toán.

Nếu giả sử chia đều và không có lãi hoặc phí, có thể minh họa gần đúng:

```text
số tiền mỗi kỳ ≈ payment_value / installments
```

Tuy nhiên, đây chỉ là phép minh họa. Dataset không cung cấp lịch thanh toán hoặc số tiền thực tế của từng kỳ,
nên không được xem công thức trên là một business rule đã được xác nhận.

### Những điều không được tự suy diễn

Từ `installments` không thể kết luận:

- ngày đến hạn của từng kỳ;
- mỗi kỳ đã thanh toán hay chưa;
- số tiền thực tế của từng kỳ;
- có lãi suất hoặc phí trả góp hay không;
- giao dịch có bị retry, thất bại hoặc hoàn tiền hay không;
- `installments > 1` luôn đồng nghĩa với một hợp đồng tín dụng thực tế.

Đặc biệt, dữ liệu có nhiều phương thức thanh toán cùng xuất hiện với nhiều kỳ. Vì vậy nên diễn giải đây là
**số kỳ được dataset ghi nhận**, không áp đặt quy tắc của một nhà cung cấp thanh toán ngoài đời vào dữ liệu.

### Vì sao bảng `payment` sau chuẩn hóa chỉ giữ `installments`?

Nguồn `payments.csv` có bốn cột:

```text
order_id, payment_method, payment_value, installments
```

Sau chuẩn hóa:

- `payment_method` bị bỏ vì đã có trong `orders` và khớp 100% theo `order_id`;
- `payment_value` bị bỏ khỏi bảng cơ sở vì tính lại chính xác từ các dòng hàng;
- `installments` được giữ vì không thể suy ra từ `orders` hoặc `order_items`.

Do đó bảng còn:

```text
payment
-------
order_id       PK, FK
installments
```

Việc bảng chỉ còn một thuộc tính nghiệp vụ không có nghĩa `payment` vô dụng. Nó vẫn lưu một sự thật không nằm
ở bảng nào khác: đơn hàng được ghi nhận thanh toán qua bao nhiêu kỳ.

### Câu trả lời khi giảng viên hỏi

> “`installments` là số kỳ thanh toán được ghi nhận cho một đơn. Dữ liệu chỉ có các giá trị 1, 2, 3, 6 và 12.
> Em giữ cột này trong bảng `payment` vì nó không suy ra được từ bảng khác. Tuy nhiên, dataset không có payment
> schedule, lãi suất hoặc trạng thái từng kỳ, nên em không khẳng định số tiền mỗi kỳ hay tiến độ trả góp thực tế.”

### Kết luận cần nhớ

```text
payment_value = tổng tiền net của đơn.
installments  = số kỳ thanh toán được ghi nhận.
```

> Có thể dùng `payment_value / installments` để minh họa nếu giả sử chia đều, nhưng không được coi đó là dữ kiện
> đã được dataset chứng minh.

---

<a id="cau-12"></a>

## 12. Tại sao phải sinh bảng junction giữa `order_item` và `promotion`? Nếu đặt trực tiếp thì sao?

### Trả lời ngắn gọn

Vì không thể đặt một foreign key duy nhất ở bên nào mà vẫn biểu diễn đúng quan hệ nhiều-nhiều:

```text
Một order_item có thể dùng nhiều promotion.
Một promotion có thể được dùng bởi nhiều order_item.
```

Bảng junction không đại diện cho một thực thể nghiệp vụ mới. Nó đại diện cho **sự kiện một promotion được áp
dụng lên một dòng hàng cụ thể**.

### Ví dụ thật trong dataset

Một dòng hàng của đơn `320123` có:

| `order_id` | `line_number` | `product_id` | `quantity` | `promo_id` | `promo_id_2` |
|---:|---:|---:|---:|---|---|
| 320123 | 1 | 2331 | 5 | PROMO-0013 | PROMO-0015 |

Nghĩa là cùng một dòng hàng đang áp dụng hai promotion. Đồng thời, mỗi promotion trên còn có thể xuất hiện ở
nhiều dòng hàng khác. Vì vậy đây là quan hệ M:N.

### Trường hợp 1 — Đặt một `promo_id` trực tiếp trong `order_item`

```text
order_item(
    order_id,
    line_number,
    product_id,
    promo_id FK
)
```

Thiết kế này chỉ lưu được **một promotion trên một dòng hàng**. Nó không lưu đủ trường hợp đơn `320123` đang có
cả `PROMO-0013` và `PROMO-0015`.

#### Cách chữa sai A — Thêm nhiều cột promotion

```text
promo_id_1, promo_id_2, promo_id_3, ...
```

Hậu quả:

- đây là nhóm cột lặp;
- không biết trước phải tạo bao nhiêu cột;
- promotion thứ tư xuất hiện thì phải sửa schema;
- muốn tìm các dòng dùng promotion X phải kiểm tra tất cả các cột.

Ví dụ truy vấn trở nên phụ thuộc vào số cột:

```sql
WHERE promo_id_1 = 'PROMO-0015'
   OR promo_id_2 = 'PROMO-0015'
   OR promo_id_3 = 'PROMO-0015'
```

#### Cách chữa sai B — Lặp lại dòng `order_item`

```text
order_id  line_number  product_id  quantity  promo_id
320123    1            2331        5         PROMO-0013
320123    1            2331        5         PROMO-0015
```

Thông tin dòng hàng bị lặp hai lần. Khi tính:

```sql
SUM(quantity * unit_price)
```

doanh thu của dòng hàng có nguy cơ bị cộng hai lần. Grain “một dòng là một mặt hàng trong đơn” cũng bị phá vỡ.

### Trường hợp 2 — Đặt thông tin dòng hàng trực tiếp trong `promotion`

```text
promotion(
    promo_id,
    promo_name,
    order_id,
    line_number
)
```

Thiết kế này chỉ cho một promotion trỏ tới một dòng hàng. Nhưng một promotion có thể áp dụng cho rất nhiều dòng
hàng. Muốn lưu hết phải lặp lại định nghĩa promotion:

```text
promo_id    promo_name          order_id  line_number
PROMO-0013 Fall Launch 2015     320123    1
PROMO-0013 Fall Launch 2015     320124    2
PROMO-0013 Fall Launch 2015     320200    1
```

Khi tên hoặc quy tắc promotion thay đổi, nhiều dòng phải được cập nhật và có thể trở nên không nhất quán.

### Bảng junction giải quyết như thế nào?

Giữ mỗi bảng đúng grain của nó:

```text
order_item
320123  1  2331  quantity=5

promotion
PROMO-0013  Fall Launch 2015
PROMO-0015  Urban Blowout 2015
```

Bảng junction chỉ lưu các liên kết:

```text
order_item_promotion
order_id  line_number  promo_id
320123    1            PROMO-0013
320123    1            PROMO-0015
```

Grain:

> Một dòng là một promotion được áp dụng lên một dòng hàng cụ thể.

Khóa và foreign key:

```text
PK: (order_id, line_number, promo_id)

FK: (order_id, line_number)
    → order_item(order_id, line_number)

FK: promo_id
    → promotion(promo_id)
```

Quan hệ M:N ban đầu được chuyển thành hai quan hệ 1:N:

```text
order_item 1 ── N order_item_promotion N ── 1 promotion
```

Nếu ngày mai một dòng hàng có promotion thứ ba, chỉ cần thêm một dòng vào `order_item_promotion`. Không phải thêm
cột, không sửa schema và không lặp lại dữ liệu dòng hàng hoặc định nghĩa promotion.

### `discount_amount` có chuyển vào bảng junction không?

Không, với dữ liệu hiện tại nên giữ `discount_amount` trong `order_item`.

Dataset chỉ cung cấp tổng discount của cả dòng hàng, không cung cấp số discount được phân bổ riêng cho từng
promotion. Nếu tự đặt `discount_amount` vào từng association thì phải tự suy diễn một quy tắc phân bổ mà nguồn
không chứng minh.

### Khi nào không cần bảng junction?

Nếu luật nghiệp vụ bảo đảm tuyệt đối:

```text
Mỗi order_item chỉ được áp dụng tối đa một promotion.
```

thì có thể đặt `promo_id FK` trực tiếp trong `order_item`. Nhưng dataset này có `promo_id_2` trên 206 dòng, nên
luật một promotion trên một dòng hàng không đúng với dữ liệu hiện có.

### Câu trả lời khi giảng viên hỏi

> “Nếu đặt một `promo_id` trực tiếp trong `order_item`, mỗi dòng hàng chỉ lưu được một promotion. Thêm nhiều cột
> promo sẽ tạo nhóm lặp; còn lặp dòng hàng theo từng promo sẽ phá grain và có thể làm nhân đôi quantity, doanh
> thu. Đặt dòng hàng vào `promotion` cũng không được vì một promotion áp dụng cho nhiều dòng hàng, làm định nghĩa
> promotion bị lặp. Vì vậy em tạo bảng junction, trong đó mỗi dòng chỉ ghi một sự thật: promotion nào được áp
> dụng cho dòng hàng nào.”

### Kết luận cần nhớ

```text
Không có junction:
- hoặc không lưu đủ nhiều promotion;
- hoặc phải thêm cột;
- hoặc phải lặp dữ liệu và làm sai grain.

Có junction:
- một association = một dòng;
- thêm quan hệ bằng cách thêm dòng, không sửa schema;
- giữ nguyên grain của order_item và promotion.
```

---

<a id="cau-13"></a>

## 13. Giải thích thiết kế bốn bảng geography trong `docs/design/normalized_schema.mmd`

### Sơ đồ đang biểu diễn điều gì?

Phần geography trong `docs/design/normalized_schema.mmd` có cấu trúc:

```text
region
  ├── city
  └── district
         \ /
       zip_area
          |
       customer
```

Các quan hệ cụ thể:

```text
region   1 ── N city
region   1 ── N district
city     1 ── N zip_area
district 1 ── N zip_area
zip_area 1 ── N customer
```

Thiết kế này được tạo từ bốn phụ thuộc hàm đã kiểm chứng trên dữ liệu:

```text
zip      → city
zip      → district
city     → region
district → region
```

Nói bằng ngôn ngữ nghiệp vụ:

- biết một mã zip thì biết nó gắn với city nào;
- biết một mã zip thì biết nó gắn với district nào;
- mỗi city trong dataset thuộc một region;
- mỗi district trong dataset cũng thuộc một region.

### Một dòng nguồn được tách thành bốn bảng như thế nào?

Giả sử `geography.csv` có dòng:

| `zip` | `city` | `district` | `region` |
|---:|---|---|---|
| 21122 | Bac Ninh | District #05 | East |

Dòng này được phân phối vào bốn bảng.

#### 1. Bảng `region`

```text
region
------
East
```

- Một dòng đại diện cho một region hợp lệ.
- PK là `region`.
- Trong schema hiện tại, bảng này chủ yếu là danh mục giá trị dùng chung cho `city` và `district`.

#### 2. Bảng `city`

```text
city       region
---------  ------
Bac Ninh   East
```

- Một dòng đại diện cho một city.
- PK là `city`.
- `region` là FK tới `region.region`.
- Sự thật được lưu ở đây là: **Bac Ninh thuộc region East**.

#### 3. Bảng `district`

```text
district       region
-------------  ------
District #05   East
```

- Một dòng đại diện cho một district.
- PK là `district`.
- `region` là FK tới `region.region`.
- Sự thật được lưu ở đây là: **District #05 thuộc region East**.

#### 4. Bảng `zip_area`

```text
zip    city       district
-----  ---------  ------------
21122  Bac Ninh   District #05
```

- Một dòng đại diện cho một mã zip.
- PK là `zip`.
- `city` là FK tới `city.city`.
- `district` là FK tới `district.district`.
- Bảng này giữ điểm giao giữa zip, city và district.

### Tại sao `zip_area` không giữ thêm cột `region`?

Vì từ một zip đã có thể suy ra region qua city:

```text
21122 → Bac Ninh → East
```

Hoặc qua district:

```text
21122 → District #05 → East
```

Nếu tiếp tục lưu `region` trong từng dòng `zip_area`, cùng một sự thật sẽ bị lặp trên nhiều zip:

```text
21122  Bac Ninh  District #05  East
21123  Bac Ninh  District #05  East
21124  Bac Ninh  District #05  East
```

Nếu region của Bac Ninh thay đổi, phải cập nhật tất cả các zip. Bỏ sót một dòng có thể tạo ra:

```text
21122  Bac Ninh  East
21123  Bac Ninh  West
```

Khi tách bảng, quan hệ `Bac Ninh → East` chỉ được lưu một lần trong `city`. Đây là phần dư thừa và update anomaly
mà thiết kế muốn giảm.

### Tại sao không thiết kế thành cây `region → city → district → zip`?

Vì dữ liệu không chứng minh district nằm hoàn toàn bên trong city.

EDA cho kết quả:

```text
city → district  SAI
district → city  SAI
```

Trong dữ liệu:

- một city trải trên tối đa 19 district;
- một district trải trên tối đa 16 city.

Do đó city và district **cắt chéo nhau**, không phải một cái là cấp con duy nhất của cái kia. Nếu thiết kế:

```text
region → city → district → zip
```

thì schema đang ngầm khẳng định mỗi district chỉ thuộc một city, trái với dữ liệu. Vì vậy `zip_area` phải giữ đồng
thời hai FK `city` và `district`.

### Đọc ký hiệu cardinality trong file `.mmd`

#### `region ||--o{ city : "gồm"`

```text
Một region có thể có từ 0 đến nhiều city.
Mỗi city phải thuộc đúng một region.
```

FK thực hiện quan hệ:

```text
city.region → region.region
```

#### `region ||--o{ district : "gồm"`

```text
Một region có thể có từ 0 đến nhiều district.
Mỗi district phải thuộc đúng một region.
```

FK:

```text
district.region → region.region
```

#### `city ||--o{ zip_area : "chứa"`

```text
Một city có thể chứa từ 0 đến nhiều zip.
Mỗi zip phải thuộc đúng một city.
```

FK:

```text
zip_area.city → city.city
```

#### `district ||--o{ zip_area : "chứa"`

```text
Một district có thể chứa từ 0 đến nhiều zip.
Mỗi zip phải thuộc đúng một district.
```

FK:

```text
zip_area.district → district.district
```

#### `zip_area ||--o{ customer : "cư trú"`

```text
Một zip có thể có từ 0 đến nhiều customer.
Mỗi customer phải tham chiếu đúng một zip.
```

FK:

```text
customer.zip → zip_area.zip
```

### Truy từ customer ra geography như thế nào?

Bảng `customer` chỉ cần giữ `zip`. Muốn biết city, district và region của khách hàng:

```sql
SELECT
    c.customer_id,
    z.zip,
    z.city,
    z.district,
    ci.region
FROM customer c
JOIN zip_area z
  ON c.zip = z.zip
JOIN city ci
  ON z.city = ci.city;
```

Cũng có thể lấy region theo district:

```sql
SELECT
    c.customer_id,
    z.zip,
    z.city,
    z.district,
    d.region
FROM customer c
JOIN zip_area z
  ON c.zip = z.zip
JOIN district d
  ON z.district = d.district;
```

Hai đường phải trả về cùng một region.

### Điểm yếu quan trọng của thiết kế bốn bảng

Region của một zip có thể được suy ra theo hai đường:

```text
zip → city → region
zip → district → region
```

Giả sử dữ liệu bị nhập thành:

```text
city:
Bac Ninh → East

district:
District #05 → West

zip_area:
21122 → Bac Ninh + District #05
```

Tất cả FK riêng lẻ vẫn hợp lệ vì `East`, `West`, `Bac Ninh` và `District #05` đều tồn tại trong bảng cha. Nhưng
cùng zip `21122` lại cho hai kết quả:

```text
Đi qua city     → East
Đi qua district → West
```

PK/FK trong sơ đồ không tự ngăn được mâu thuẫn này. Khi triển khai cần thêm ETL test, trigger hoặc constraint phù
hợp để kiểm tra:

```text
city.region = district.region
cho từng dòng zip_area
```

Đây là lý do phải nói thiết kế bốn bảng là một **đánh đổi**: giảm dư thừa ở grain zip nhưng tăng số join và tạo
ra yêu cầu kiểm soát tính nhất quán giữa hai đường.

### Bảng `region` có bắt buộc không?

Không. Có thể dùng:

```text
city(city PK, region)
district(district PK, region)
zip_area(zip PK, city FK, district FK)
```

Không mất thông tin và `city`, `district` vẫn có thể đạt 3NF. Bảng `region` một cột hiện chủ yếu:

- quản lý danh sách region hợp lệ `Central`, `East`, `West`;
- cho `city` và `district` tham chiếu bằng FK;
- tạo điểm mở rộng nếu sau này region có `region_id`, `manager`, `warehouse`, v.v.

Nếu region chỉ là ba nhãn cố định, có thể bỏ bảng riêng và dùng cùng một `CHECK` hoặc `ENUM` ở `city` và
`district`.

### Mục đích tổng thể của việc tách `geography` thành bốn bảng

Nói chính xác là **tách bảng nguồn `geography` thành bốn bảng**, không phải “tách `region` thành bốn bảng”.

Bảng nguồn có cấu trúc:

```text
geography(zip, city, district, region)
```

Sau chuẩn hóa:

```text
region(region)
city(city, region)
district(district, region)
zip_area(zip, city, district)
```

Mục đích là để **mỗi loại sự thật địa lý có một nơi sở hữu**:

| Bảng | Sự thật được lưu |
|---|---|
| `region` | Region nào là giá trị hợp lệ |
| `city` | Một city thuộc region nào |
| `district` | Một district thuộc region nào |
| `zip_area` | Một zip gắn với city và district nào |

#### “Region bị lặp trên gần 40.000 zip” nghĩa là gì?

Dataset có:

```text
39.948 dòng geography
39.948 zip khác nhau
3 region khác nhau: Central, East, West
0 dòng bị duplicate hoàn toàn
```

Vì vậy “lặp” ở đây **không có nghĩa là các dòng bị duplicate**. Mỗi dòng vẫn là một zip khác nhau. Thứ bị lặp
là nhãn `Central`, `East` hoặc `West` được ghi lại trong từng dòng zip:

| `region` | Số dòng zip ghi lại nhãn đó |
|---|---:|
| Central | 14.512 |
| East | 18.929 |
| West | 6.507 |
| **Tổng** | **39.948** |

Ví dụ Bac Ninh có 1.346 zip và cả 1.346 dòng đều ghi lại `region = East`:

```text
zip    city       district      region
15222  Bac Ninh   District #13  East
15227  Bac Ninh   District #13  East
15259  Bac Ninh   District #13  East
...    Bac Ninh   ...           East
```

Trong khi EDA đã chứng minh:

```text
city → region
```

Chỉ cần biết `city = Bac Ninh` đã suy ra được `region = East`. Vì vậy quan hệ này chỉ cần lưu một lần:

```text
city
city       region
Bac Ninh   East
```

Các zip chỉ lưu city và district:

```text
zip_area
zip    city       district
15222  Bac Ninh   District #13
15227  Bac Ninh   District #13
15259  Bac Ninh   District #13
```

Khi cần region, truy vấn join `zip_area.city → city.region`.

#### Lợi ích cụ thể

1. Quan hệ `city → region` chỉ lưu trong 42 dòng `city`, thay vì lặp theo 39.948 dòng zip.
2. Quan hệ `district → region` chỉ lưu trong 39 dòng `district`.
3. Khi một city được phân sang region khác, chỉ cập nhật dòng city đó, không cập nhật tất cả zip của city.
4. `zip_area` giữ đúng sự thật ở grain zip: zip gắn với city và district nào.
5. Hai FK tới `city` và `district` biểu diễn đúng cấu trúc cắt chéo, thay vì ép thành cây sai
   `region → city → district → zip`.

Giá trị chính của việc tách nằm ở ba bảng `city`, `district`, `zip_area`. Riêng bảng `region` một cột là lựa chọn
danh mục dùng chung: có thể giữ để dùng FK hoặc thay bằng `CHECK`/`ENUM` nếu chỉ có ba nhãn cố định.

### Câu trả lời khi giảng viên hỏi

> “Nói chính xác là em tách bảng `geography`, không phải tách riêng `region`. Nguồn có 39.948 zip khác nhau và
> không có dòng duplicate; thứ bị lặp là ba nhãn `Central`, `East`, `West` được ghi lại trên toàn bộ 39.948 dòng.
> Ví dụ Bac Ninh có 1.346 zip và cả 1.346 dòng đều ghi `East`, trong khi EDA chứng minh `city → region`. Vì vậy
> em lưu quan hệ `Bac Ninh → East` một lần trong bảng `city`; tương tự, quan hệ district–region được lưu trong
> bảng `district`. City và district cắt chéo nhau nên `zip_area` phải giữ đồng thời FK tới cả hai, không thể ép
> thành một cây city–district. Bảng `region` chỉ là danh mục giá trị chung và không bắt buộc để đạt 3NF. Điểm yếu
> là region có thể được suy ra theo hai đường, nên khi triển khai phải kiểm tra hai đường luôn khớp.”

### Kết luận cần nhớ

```text
region   = danh mục region hợp lệ
city     = city thuộc region nào
district = district thuộc region nào
zip_area = zip gắn với city và district nào
customer = khách cư trú tại zip nào

Không tạo cây city → district vì hai chiều cắt chéo.
Không lưu region trong zip_area vì region đã suy ra được.
Phải kiểm tra hai đường city → region và district → region luôn khớp.
```

---

<a id="cau-14"></a>

## 14. Tại sao tách riêng `product_model`, không để chung một bảng `product`?

### Trả lời ngắn gọn

Dataset đang chứa hai grain khác nhau trong cùng `products.csv`:

```text
product_model = một dòng cho một model/tên sản phẩm
product       = một dòng cho một product_id/SKU cụ thể
```

`category` và `segment` được xác định bởi `product_name`, không phải bởi từng lần xuất hiện của
`product_id`. Nếu giữ chung, cùng một thông tin model bị lặp ở nhiều SKU và tạo phụ thuộc bắc cầu:

```text
product_id → product_name → category, segment
```

Vì vậy mô hình 3NF tách phần mô tả model ra khỏi phần mô tả SKU.

### Bằng chứng từ toàn bộ `products.csv`

| Kiểm tra | Kết quả |
|---|---:|
| Tổng số dòng / `product_id` | 2.412 |
| Số `product_name` khác nhau | 2.172 |
| Số `product_name` gắn với nhiều `product_id` | 186 |
| Số dòng lặp thêm theo `product_name` | 240 |
| Vi phạm `product_name → category` | 0 / 2.172 tên |
| Vi phạm `product_name → segment` | 0 / 2.172 tên |
| Dòng trùng `(product_name, size, color)` | 240 |

Như vậy:

```text
product_name → category, segment
```

được dữ liệu hỗ trợ tuyệt đối trên snapshot và được chấp nhận là FD nghiệp vụ của model.

### Ví dụ thật trong dataset

```text
product_id  product_name      category    segment       size  color  price
280         LotusWear UE-01   Streetwear  Performance   S     red    12596.85
380         LotusWear UE-01   Streetwear  Performance   S     red       34.04
```

Hai dòng có cùng `product_name`, `category`, `segment`, `size`, `color`, nhưng khác `product_id`,
`price` và `cogs`. Ví dụ này cho thấy:

- `product_name` không phải khóa của bảng SKU;
- `product_id` vẫn cần thiết để định danh từng dòng sản phẩm;
- `category`, `segment` đang bị lặp theo mỗi `product_id` cùng model.

### Nếu giữ tất cả trong một bảng thì vấn đề gì xảy ra?

Giả sử giữ nguyên bảng rộng:

```text
product(
    product_id PK,
    product_name,
    category,
    segment,
    size,
    color,
    list_price,
    unit_cogs
)
```

Trong quan hệ này:

```text
product_id → product_name, category, segment, size, color, list_price, unit_cogs
product_name → category, segment
```

`product_name` không phải superkey vì một tên có thể xuất hiện ở nhiều `product_id`. Nhưng nó lại
xác định hai thuộc tính không khóa `category`, `segment`. Do đó tồn tại phụ thuộc bắc cầu:

```text
product_id → product_name → category, segment
```

Đây là lý do bảng rộng không đạt 3NF với tập FD nghiệp vụ đã khai báo.

### Update anomaly cụ thể

Giả sử `LotusWear UE-01` có 10 SKU. Nếu giữ bảng chung, giá trị:

```text
category = Streetwear
segment  = Performance
```

phải được ghi lại 10 lần. Khi doanh nghiệp đổi category của model này, phải cập nhật cả 10 dòng.
Nếu chỉ 9 dòng được cập nhật, database có thể xuất hiện trạng thái:

```text
product_id = 280 → category = Streetwear
product_id = 380 → category = Casual
```

Cùng một `product_name` nhưng hai category khác nhau, trái với FD nghiệp vụ đã chấp nhận.

Sau khi tách, quan hệ model chỉ được lưu một lần:

```text
product_model
product_name      category     segment
LotusWear UE-01   Streetwear   Performance
```

Đổi category chỉ cần cập nhật một dòng.

### Thiết kế sau khi tách

```text
PRODUCT_MODEL(
    product_name PK,
    category,
    segment
)

PRODUCT(
    product_id PK,
    product_name FK,
    size,
    color,
    list_price,
    unit_cogs
)
```

Cardinality:

```text
PRODUCT_MODEL 1 ─── 0..N PRODUCT
```

Một model có thể có nhiều SKU; mỗi SKU thuộc đúng một model.

Phân rã là lossless vì phần giao của hai bảng là `product_name`, và `product_name` là khóa của
`product_model`. Join lại theo `product_name` tái tạo được bảng rộng mà không làm mất dòng.

### Tại sao `size`, `color` vẫn nằm trong `product`?

Toàn bộ snapshot hiện tại cũng cho:

```text
product_name → size, color
```

với 0 vi phạm / 2.172 tên. Tuy nhiên, không sử dụng hai FD này làm quy tắc nghiệp vụ vì một model
thời trang có thể phát sinh nhiều biến thể:

```text
Model A
├── size S, color Black
├── size M, color Black
└── size L, color Blue
```

Trong trạng thái đó:

```text
product_name ↛ size, color
```

Vì vậy `size`, `color` được giữ ở grain SKU trong `product`. Kết quả 0 vi phạm hiện tại được ghi là
**FD đúng trên snapshot**, không được nâng thành FD nghiệp vụ cho mọi dữ liệu tương lai.

Đây là ví dụ quan trọng cho nguyên tắc:

> Dữ liệu hữu hạn có thể bác bỏ một FD bằng phản ví dụ, nhưng việc chưa thấy phản ví dụ không tự động
> chứng minh FD đó là quy tắc nghiệp vụ lâu dài.

### Vì sao không dùng `(product_name, size, color)` làm khóa?

Tổ hợp này có 240 dòng trùng trong dữ liệu. Ví dụ hai dòng `LotusWear UE-01` phía trên có cùng cả
`product_name`, `size`, `color` nhưng vẫn là hai `product_id` khác nhau và có giá khác nhau.

Do đó:

```text
(product_name, size, color) không phải candidate key
```

`product_id` không phải khóa thay thế “trang trí”; nó thực sự cần để định danh từng dòng SKU trong
dataset hiện tại.

### Khi query có bị bất tiện không?

Muốn xem SKU cùng thông tin model, chỉ cần join:

```sql
SELECT
    p.product_id,
    p.product_name,
    pm.category,
    pm.segment,
    p.size,
    p.color,
    p.list_price,
    p.unit_cogs
FROM product p
JOIN product_model pm
  ON pm.product_name = p.product_name;
```

Có thể tạo view rộng cho EDA hoặc báo cáo. Bảng core vẫn giữ 3NF, còn người phân tích không phải
lặp lại câu join trong mọi truy vấn.

### Có bắt buộc phải tách trong mọi hệ thống không?

Không. Nếu mục tiêu chỉ là một file phân tích nhỏ hoặc bảng dimensional phục vụ BI, giữ bảng product
phẳng có thể tiện hơn. Việc tách có ý nghĩa khi mục tiêu là relational core 3NF, cần giảm update
anomaly và quản lý model/SKU như hai grain riêng.

Trong production, `product_name` có thể đổi tên hoặc không đủ ổn định để làm PK. Khi có yêu cầu đó,
nên dùng khóa thay thế:

```text
product_model(
    model_id PK,
    product_name,
    category,
    segment
)

product(
    product_id PK,
    model_id FK,
    size,
    color,
    list_price,
    unit_cogs
)
```

Dataset hiện không cung cấp `model_id`, nên thiết kế logical hiện tại dùng `product_name` làm khóa
tự nhiên có thể khôi phục từ nguồn. Đây là giới hạn của dữ liệu, không phải khẳng định rằng tên sản
phẩm luôn là khóa tốt trong mọi hệ thống thực tế.

### Câu trả lời khi giảng viên hỏi

> “Em tách `product_model` vì file nguồn trộn hai grain: model và SKU. Toàn bộ dữ liệu có 2.412
> `product_id` nhưng chỉ 2.172 `product_name`; 186 tên gắn với nhiều mã sản phẩm. Đồng thời,
> `product_name → category, segment` đúng với 0 vi phạm, nên nếu giữ một bảng sẽ có phụ thuộc bắc
> cầu `product_id → product_name → category, segment` và lặp thông tin model trên nhiều SKU.
> `product_model` lưu category, segment một lần; `product` giữ product_id, size, color và các giá trị
> theo SKU. Dù snapshot hiện tại cũng cho `product_name → size, color`, em không coi đó là FD nghiệp
> vụ vì model thời trang có thể có nhiều biến thể. Ngoài ra `(product_name, size, color)` có 240 dòng
> trùng nên `product_id` vẫn là khóa cần thiết.”

### Kết luận cần nhớ

```text
product_model = grain model; giữ product_name, category, segment
product       = grain SKU; giữ product_id, size, color, list_price, unit_cogs

FD nghiệp vụ dùng để tách:
product_name → category, segment

FD chỉ đúng trên snapshot, không dùng để tách:
product_name → size, color

(product_name, size, color) có 240 dòng trùng
⇒ product_id vẫn là PK cần thiết
```
