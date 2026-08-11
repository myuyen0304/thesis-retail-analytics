# Báo cáo: Xây dựng Từ điển dữ liệu và Sơ đồ ERD

**Nội dung phụ trách:** Từ điển dữ liệu (Data Dictionary) và Sơ đồ thực thể – liên kết (ERD)
**Sản phẩm:** [data-dictionary.md](data-dictionary.md) · [erd.svg](erd.svg) · [erd.drawio](erd.drawio)

---

## 1. Em được giao việc gì

Thưa thầy/cô, đề tài của nhóm em là dự báo doanh thu và giá vốn hàng bán theo ngày cho một doanh nghiệp
bán lẻ thời trang trực tuyến.

Phần em phụ trách là bước đầu tiên: **hiểu và mô tả dữ liệu** trước khi nhóm bắt tay vào xây dựng mô
hình. Cụ thể gồm hai sản phẩm là từ điển dữ liệu và sơ đồ ERD.

Bộ dữ liệu em nhận được gồm **14 tệp CSV, khoảng 2,96 triệu bản ghi, 96 trường dữ liệu**, trải dài từ
tháng 7 năm 2012 đến hết năm 2022. Khó khăn lớn nhất là dữ liệu được cung cấp **không kèm bất kỳ tài
liệu mô tả nào** — em không biết cột nào là khóa, các bảng nối với nhau ra sao, cột nào chứa thông tin
thật và cột nào chỉ là bản sao.

Vì vậy em đặt ra một nguyên tắc xuyên suốt cho cả hai phần việc:

> **Không mô tả bất kỳ điều gì mà em chưa kiểm chứng trực tiếp trên dữ liệu.**
> Tên cột chỉ là gợi ý, không phải bằng chứng.

Toàn bộ kiểm định em thực hiện bằng Python với thư viện `pandas`.

---

## 2. Phần thứ nhất — Từ điển dữ liệu

### 2.1. Vì sao phải làm bước này trước

Em xin lấy một ví dụ để thấy nếu bỏ qua bước này thì hậu quả ra sao.

Bảng khách hàng có cột `signup_date`, nghe tên là ngày đăng ký tài khoản. Nếu tin vào tên cột, em có thể
tính được đặc trưng "khách hàng đã gắn bó bao lâu" bằng cách lấy ngày đặt hàng trừ ngày đăng ký — một
đặc trưng rất hợp lý cho bài toán dự báo.

Nhưng khi kiểm tra thực tế, em phát hiện **73,8% đơn hàng có ngày đặt trước ngày đăng ký của chính khách
hàng đó**. Phép trừ ra số âm, tức là điều bất khả thi về mặt nghiệp vụ. Nếu không kiểm tra, nhóm em sẽ
đưa một đặc trưng vô nghĩa vào mô hình mà không hề hay biết.

### 2.2. Em đã làm theo bốn bước

**Bước 1 — Kiểm kê cấu trúc.** Với từng tệp, em xác định số dòng, kiểu dữ liệu từng cột, số lượng giá
trị thiếu và miền giá trị. Với các biến phân loại, em liệt kê **đầy đủ danh sách giá trị** thay vì chỉ
ghi "kiểu chuỗi". Nhờ vậy em phát hiện cột `order_status` chỉ nhận đúng 6 giá trị, và chúng tuân theo
một vòng đời có quy luật: tạo đơn → thanh toán → giao hàng → nhận hàng → trả hàng, với nhánh hủy đơn.

**Bước 2 — Xác định khóa chính.** Bước này tưởng đơn giản nhưng cho ra một phát hiện quan trọng: bảng
`order_items` **không có khóa tự nhiên hợp lệ**. Cặp `(order_id, product_id)` mà em tưởng là khóa lại có
**16 cặp bị trùng** trên tổng số 714.669 dòng. Nếu cứ tin đó là khóa mà không kiểm tra, mọi phép nối
bảng về sau sẽ bị nhân dòng sai.

**Bước 3 — Kiểm định toàn vẹn tham chiếu.** Ý tưởng là kiểm tra xem mọi giá trị khóa ngoại ở bảng con có
thực sự tồn tại ở bảng cha hay không. Ví dụ nếu có đơn hàng ghi mã khách hàng mà bảng khách hàng không
có ai mang mã đó, thì đó là bản ghi hỏng.

Em kiểm tra **16 quan hệ trên tổng cộng 4.055.881 bản ghi**, kết quả **không có bản ghi mồ côi nào**.
Đồng thời em đo độ phủ ngược lại — tức bao nhiêu phần trăm bản ghi ở bảng cha thực sự được tham chiếu.
Con số này về sau em dùng để xác định quan hệ là bắt buộc hay tùy chọn khi vẽ ERD.

**Bước 4 — Phát hiện cột dư thừa và cột suy diễn.** Đây là bước tốn công nhất nhưng em thấy giá trị nhất.

### 2.3. Cách em phát hiện cột suy diễn

Cột suy diễn là cột tính lại được từ các cột khác, nên **không mang thông tin mới**.

Cách làm của em là **đặt giả thuyết về công thức, rồi so khớp trên toàn bộ dữ liệu**. Ví dụ em nghi cột
`fill_rate` không phải một số đo độc lập, nên thử công thức `1 − stockout_days/30` và so khớp — kết quả
đúng 100% trên cả 60.247 dòng.

Em làm tương tự với các cột khác:

| Giả thuyết | Kết quả |
|---|---|
| `fill_rate = 1 − stockout_days / 30` | Khớp 100% → **là cột suy diễn** |
| `stockout_flag = (stockout_days > 0)` | Khớp 100% → **là cột suy diễn** |
| `sell_through_rate = units_sold / (stock_on_hand + units_sold)` | Khớp 100% → **là cột suy diễn** |
| `days_of_supply = stock_on_hand / (units_sold / 30)` | Khớp 100% → **là cột suy diễn** |
| `payment_value = Σ(quantity × unit_price − discount_amount)` | Khớp 100% → **là cột suy diễn** |
| `refund_amount = return_quantity × unit_price` | Chỉ khớp 0,6% → **không** suy diễn được |
| `overstock_flag` theo ngưỡng tồn kho | Ngưỡng tốt nhất chỉ khớp 83% → **không** suy diễn được |

Em xin phép nhấn mạnh hai dòng cuối. Chúng là hai giả thuyết em đặt ra nhưng **bị dữ liệu bác bỏ**, nên
em giữ nguyên hai cột đó là thuộc tính thường. Em nêu ra vì nó cho thấy phương pháp này có tính kiểm
chứng thật sự — nếu chỉ nhìn tên cột rồi đoán thì rất dễ kết luận nhầm `refund_amount` là cột suy diễn.

### 2.4. Vì sao việc này quan trọng với mô hình

Cột suy diễn không mang thông tin mới. Nếu nhóm em đưa cả `stockout_days` lẫn `fill_rate` vào mô hình
học máy thì hai biến này tương quan hoàn hảo với nhau, gây hiện tượng **đa cộng tuyến**. Hậu quả là
trọng số của mô hình trở nên bất ổn định, và biểu đồ tầm quan trọng đặc trưng cho kết quả sai lệch — mô
hình có thể xếp hạng cao một biến chỉ vì nó là bản sao của biến khác.

Vì vậy em cho rằng phải phát hiện và loại bỏ ngay từ giai đoạn mô tả dữ liệu, chứ không đợi đến lúc
huấn luyện mới xử lý.

### 2.5. Kết quả

Từ điển dữ liệu mô tả đầy đủ **96 trường của 14 bảng**, mỗi trường ghi rõ kiểu dữ liệu, ràng buộc khóa,
miền giá trị và ý nghĩa nghiệp vụ. Kèm theo là bảng tổng hợp **17 cảnh báo chất lượng dữ liệu** xếp theo
mức độ nghiêm trọng.

Ba phát hiện em thấy quan trọng nhất:

**Thứ nhất**, hai biến mục tiêu `Revenue` và `COGS` **tái tạo được chính xác tuyệt đối** từ các bảng giao
dịch chi tiết:

```
Revenue(ngày d) = Σ (quantity × unit_price)
COGS(ngày d)    = Σ (quantity × products.cogs)
```

gộp theo `orders.order_date`. Sai số tuyệt đối bằng **0,00 trên cả 3.833 ngày**.

Có ba đặc điểm của công thức này em thấy rất dễ hiểu nhầm nên xin nêu rõ: doanh thu ở đây là **doanh thu
gộp**, không trừ giảm giá; nó tính **cả đơn đã hủy và đơn bị trả lại**; và mốc thời gian là **ngày đặt
hàng**, không phải ngày giao hàng hay ngày thanh toán.

**Thứ hai**, lỗi mâu thuẫn thời gian ở cột `signup_date` đã nêu ở trên, ảnh hưởng 73,8% đơn hàng. Hướng
xử lý của em là thay bằng ngày đặt hàng đầu tiên của mỗi khách, suy trực tiếp từ bảng `orders`.

**Thứ ba**, có **814 trên 2.412 sản phẩm chưa từng phát sinh giao dịch nào**, trong đó 654 sản phẩm có
giá bất thường dưới 100 đơn vị tiền tệ. Chúng làm lệch mọi thống kê mô tả về giá và biên lợi nhuận nếu
không lọc bỏ trước khi tính.

---

## 3. Phần thứ hai — Sơ đồ ERD

### 3.1. Em phải chọn đúng loại sơ đồ trước

Đây là việc đầu tiên và cũng là chỗ em từng làm sai. Có hai loại sơ đồ hay bị gọi lẫn lộn là "ERD":

| | ERD (mức khái niệm) | Relational Diagram (mức logic) |
|---|---|---|
| Ký hiệu | Chen: chữ nhật, hình thoi, elip | Bảng có danh sách cột và khóa |
| Trả lời câu hỏi | Dữ liệu **là gì**, liên quan ra sao | Dữ liệu **lưu trong bảng nào** |
| Khóa ngoại | **Không** vẽ thành thuộc tính | Vẽ thành cột khóa ngoại |
| Dùng cho | Phân tích nghiệp vụ | Thiết kế và triển khai CSDL |

Bản đầu tiên em vẽ theo ký hiệu chân chim với đầy đủ cột khóa ngoại — đó thực chất là Relational
Diagram, không phải ERD. Sau khi tra lại giáo trình, em vẽ lại theo **ký hiệu Chen ở mức khái niệm**,
vì quy trình thiết kế cơ sở dữ liệu đi theo thứ tự ERD trước, rồi mới ánh xạ sang mô hình quan hệ.

### 3.2. Bốn quy tắc em áp dụng khi chuyển từ tệp CSV sang sơ đồ

Điều em nhận ra là **ERD không phải bản chép lại cấu trúc tệp**. Cần bốn phép biến đổi.

**Quy tắc 1 — Khóa ngoại không được vẽ thành thuộc tính.**

Bảng `orders` trong tệp CSV có cột `customer_id`. Nhưng trong ERD, cột này **biến mất**, thay bằng hình
thoi *"đặt"* nối `CUSTOMERS` với `ORDERS`.

Lý do là hình thoi đó **chính là** lời khẳng định "đơn hàng thuộc về khách hàng". Nếu vẽ thêm cột
`customer_id` vào ô `ORDERS` nữa thì em đang nói cùng một điều hai lần. Nói cách khác, `customer_id`
không phải một tính chất của đơn hàng như ngày đặt hay trạng thái — nó chỉ là cơ chế kỹ thuật để nối
bảng, mà mô hình khái niệm thì không mô tả cơ chế.

Tổng cộng **15 cột khóa ngoại** đã được chuyển thành quan hệ.

**Quy tắc 2 — Nhận diện thực thể yếu.**

Thực thể yếu là thực thể không tự định danh được, phải mượn khóa của thực thể chủ. Em xin lấy ví dụ đời
thường: nói *"phòng số 3"* thì vô nghĩa nếu không nói rõ **phòng số 3 của tòa nhà nào**.

Bộ dữ liệu này có bốn thực thể yếu:

| Thực thể yếu | Vì sao |
|---|---|
| `ORDER_ITEMS` | Một dòng hàng chỉ có nghĩa khi biết thuộc đơn nào; bản thân không có mã riêng |
| `PAYMENTS` | Khóa chính chính là `order_id` — chỉ là phần mở rộng của đơn hàng |
| `SHIPMENTS` | Tương tự `PAYMENTS` |
| `INVENTORY` | Được xác định bởi **cặp** (ngày chốt sổ, sản phẩm), không chỉ bởi ngày |

Trên sơ đồ chúng vẽ **viền đôi**, nối với thực thể chủ bằng **hình thoi viền đôi**, gọi là quan hệ định
danh vì chính quan hệ đó cấp danh tính cho nó.

**Quy tắc 3 — Đánh dấu thuộc tính suy diễn.**

Kết quả kiểm chứng công thức ở phần từ điển được em thể hiện trực tiếp lên sơ đồ: thuộc tính suy diễn vẽ
**elip nét đứt**. Có 11 thuộc tính như vậy. Riêng bảng `INVENTORY` thì **6 trên 13 thuộc tính là suy
diễn**, tức quá nửa bảng không mang thông tin độc lập.

**Quy tắc 4 — Loại bỏ những gì không phải thực thể nghiệp vụ.**

Em loại `sample_submission.csv` khỏi sơ đồ, vì nó là khuôn dạng nộp kết quả dự báo — chứa 548 ngày tương
lai với giá trị chỉ mang tính minh họa. Đó là quy ước kỹ thuật của cuộc thi chứ không phải dữ liệu
nghiệp vụ. Nó vẫn được mô tả đầy đủ trong từ điển dữ liệu.

Em cũng loại ba cột `product_name`, `category`, `segment` trong bảng tồn kho, vì chúng là bản sao nguyên
văn từ bảng sản phẩm, thuộc về thực thể sản phẩm chứ không phải thuộc tính của tồn kho.

### 3.3. Cách em chứng minh sơ đồ không sót và không bịa

Em làm một phép đối soát:

```
93 cột (13 tệp)  −  15 cột khóa ngoại  −  3 cột sao chép  =  75 thuộc tính
```

Con số 75 khớp đúng với số elip trên sơ đồ. Nghĩa là mỗi cột của dữ liệu gốc đều có một trong ba số
phận: trở thành thuộc tính, trở thành quan hệ, hoặc bị loại bỏ có lý do ghi rõ. Không cột nào bị bỏ
quên, cũng không có thuộc tính nào được thêm vào từ suy đoán.

### 3.4. Bản số và mức độ tham gia đều đo trên dữ liệu

Em không suy đoán bản số từ tên bảng mà đếm trực tiếp:

| Quan hệ | Đo được | Kết luận |
|---|---|---|
| `ORDERS` → `ORDER_ITEMS` | 1–5 dòng mỗi đơn | 1:N |
| `ORDER_ITEMS` → `RETURNS` | 39.939 dòng / 39.937 cặp | 1:N |
| `ORDER_ITEMS` → `REVIEWS` | 113.551 dòng / 113.551 cặp | 1:1 |
| `ORDERS` → `PAYMENTS` | Đúng 646.945 = 646.945 | 1:1 |

Ngoài bản số, sơ đồ còn thể hiện **mức độ tham gia** — đây là hai khái niệm khác nhau. Bản số trả lời
*một bên có bao nhiêu bản thể ứng với một bản thể bên kia*; mức độ tham gia trả lời *có bắt buộc mọi bản
thể đều phải tham gia quan hệ không*.

Em vẽ đường đôi cho tham gia toàn bộ, đường đơn cho tham gia bộ phận, dựa trên số liệu đo được:

| Bên tham gia | Tỷ lệ | Ký hiệu |
|---|---:|---|
| Đơn hàng có dòng hàng | 100% | Đường đôi |
| Đơn hàng có thanh toán | 100% | Đường đôi |
| Đơn hàng có giao vận | 87,5% | Đường đơn |
| Khách hàng từng đặt hàng | 74,0% | Đường đơn |
| Sản phẩm từng được bán | 66,3% | Đường đơn |

Sơ đồ dùng **thuần ký hiệu Chen**: bản số chỉ ghi `1` hoặc `N`, còn tính bắt buộc hay tùy chọn thể hiện
bằng kiểu đường, không trộn với hệ ký hiệu `(min, max)`.

---

## 4. Quá trình rà soát

Em xin trình bày thêm phần này, vì sơ đồ đã trải qua bốn vòng rà soát và **vòng nào cũng tìm ra lỗi**.
Em nghĩ việc nêu ra sẽ giúp thầy/cô thấy các kết luận trong sơ đồ đến từ kiểm chứng chứ không phải cảm
tính.

**Lỗi 1 — Vẽ nhầm loại sơ đồ.** Em vẽ ra Relational Diagram thay vì ERD, như đã trình bày ở mục 3.1.

**Lỗi 2 — Vẽ `SALES` tách rời không nối gì.** Em suy luận theo cấu trúc tệp: bảng này không có cột khóa
ngoại nào nên không có quan hệ. Nhưng khi kiểm tra, tập ngày trong `sales` **trùng khớp tuyệt đối** với
tập ngày đặt hàng trong `orders` — cùng 3.833 ngày, không lệch ngày nào. Quan hệ tồn tại thật, chỉ là
nối qua giá trị ngày chứ không qua mã khóa. Em bổ sung quan hệ và vẽ nét đứt để phân biệt với khóa ngoại
vật lý.

Bài học em rút ra là ERD mô tả **quan hệ nghiệp vụ**, không phải cấu trúc tệp.

**Lỗi 3 — Nối `RETURNS` và `REVIEWS` sai đích.** Ban đầu em thấy bảng `returns` có hai cột `order_id` và
`product_id` nên vẽ hai quan hệ riêng, một tới `ORDERS` và một tới `PRODUCTS`. Nhưng kiểm tra cho thấy
hai cột đó **đi cùng nhau**: mọi cặp `(order_id, product_id)` của `returns` đều nằm trọn trong
`order_items`, không lệch dòng nào.

Nghĩa là mỗi lượt trả hàng gắn với **một dòng hàng cụ thể** — khách trả lại *hai cái áo size M màu đỏ
trong đơn số 5*, chứ không phải trả đơn số 5 và trả sản phẩm X như hai việc riêng biệt. Em thay 4 quan
hệ sai bằng 2 quan hệ đúng.

**Lỗi 4 — Bỏ sót thuộc tính suy diễn và sai một bản số.** Em phát hiện thêm 6 thuộc tính suy diễn chưa
đánh dấu, và sửa bản số giữa `ORDER_ITEMS` và `REVIEWS` từ 1:N thành 1:1.

---

## 5. Kết quả và hướng tiếp theo

Sản phẩm em hoàn thành gồm:

| Sản phẩm | Nội dung |
|---|---|
| Từ điển dữ liệu | 96 trường của 14 bảng, kèm 17 cảnh báo chất lượng dữ liệu |
| Sơ đồ ERD | 13 thực thể, 75 thuộc tính, 15 quan hệ, ký hiệu Chen mức khái niệm |

Trong đó có 4 thực thể yếu, 1 thực thể suy diễn, 11 thuộc tính suy diễn và 5 quan hệ định danh.

Toàn bộ số liệu đều kiểm chứng được bằng cách chạy lại trên dữ liệu gốc. Đây là cơ sở để nhóm em bước
sang giai đoạn tiếp theo là xây dựng đặc trưng và huấn luyện mô hình dự báo.

Em xin hết. Mong thầy/cô góp ý ạ.

---

## Phụ lục — Một số câu hỏi em dự đoán và phần trả lời

**Vì sao 14 tệp mà sơ đồ chỉ có 13 thực thể?**
> `sample_submission.csv` là khuôn dạng nộp kết quả dự báo, chứa ngày tương lai với giá trị chỉ mang
> tính minh họa. Đó là quy ước kỹ thuật, không phải thực thể nghiệp vụ. Nó vẫn được mô tả đầy đủ trong
> từ điển dữ liệu ạ.

**Vì sao khóa ngoại không xuất hiện trong sơ đồ?**
> Vì đây là ERD mức khái niệm. Liên kết giữa các thực thể đã do hình thoi quan hệ biểu diễn rồi; vẽ thêm
> cột khóa ngoại là mô tả trùng một thứ hai lần. Khóa ngoại chỉ xuất hiện sau bước ánh xạ sang mô hình
> quan hệ ạ.

**Vì sao `ORDER_ITEMS` là thực thể mà không phải hình thoi?**
> Trong ký hiệu Chen, quan hệ nhiều–nhiều có thuộc tính thường được vẽ thành hình thoi. Nhưng
> `ORDER_ITEMS` còn tham gia ba quan hệ khác với `PROMOTIONS`, `RETURNS` và `REVIEWS`. Một quan hệ không
> thể có quan hệ con, nên nó bắt buộc phải là thực thể ạ.

**Vì sao một số đường vẽ nét đứt?**
> Nét đứt đánh dấu liên kết không phải khóa ngoại vật lý, gồm hai loại: liên kết theo trục thời gian như
> `SALES` với `ORDERS`, và liên kết qua cột dư thừa suy được từ nơi khác như `ORDERS` với `GEOGRAPHY` ạ.

**Làm sao em biết `SALES` là thực thể suy diễn?**
> Vì em tái tạo được nó chính xác tuyệt đối từ dữ liệu giao dịch, sai số bằng 0,00 trên toàn bộ 3.833
> ngày ạ.

**Bộ dữ liệu này có phải dữ liệu thực tế không?**
> Em nghĩ là dữ liệu mô phỏng ạ. Có nhiều dấu hiệu: toàn vẹn tham chiếu tuyệt đối trên hơn 4 triệu bản
> ghi, số lượng đặt hàng phân bố đều gần như hoàn hảo trên 8 mức, `fill_rate` là hàm xác định của
> `stockout_days` với mẫu số cố định 30, và tính mùa vụ ngược với quy luật bán lẻ thời trang. Nên các
> kết luận nghiệp vụ cần được diễn giải thận trọng ạ.

**Em dùng công cụ gì?**
> Em dùng Python với thư viện `pandas` để kiểm định dữ liệu, và draw.io để vẽ sơ đồ ạ. File nguồn
> `.drawio` em vẫn giữ để chỉnh sửa được.
