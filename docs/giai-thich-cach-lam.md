# Giải thích cách làm — đọc để hiểu, không phải để học thuộc

> Tài liệu này giải thích **bản chất** của từng việc đã làm, viết cho người đọc chưa quen với các khái
> niệm. Mục tiêu là sau khi đọc, bạn tự trả lời được câu hỏi ngoài kịch bản.
>
> Kịch bản nói: [kich-ban-trinh-bay.md](kich-ban-trinh-bay.md) ·
> Phương pháp: [phuong-phap-thuc-hien.md](phuong-phap-thuc-hien.md)

---

## Phần 1 — Từ điển dữ liệu là gì và vì sao cần

### 1.1. Hình dung đơn giản

Tưởng tượng ai đó đưa bạn 14 tệp Excel rồi bảo *"làm dự báo doanh thu đi"*. Bạn mở ra thấy hàng trăm
cột với tên như `fill_rate`, `sell_through_rate`, `promo_id_2`. Bạn không biết:

- Cột nào dùng để nối các bảng với nhau
- Cột nào chứa thông tin thật, cột nào chỉ là bản sao của cột khác
- Giá trị nào là hợp lệ, giá trị trống nghĩa là gì

**Từ điển dữ liệu** là tài liệu trả lời tất cả những câu đó cho từng cột. Nó giống như quyển từ điển:
tra một từ (một cột) thì biết nghĩa, biết cách dùng.

### 1.2. Vì sao không thể bỏ qua bước này

Có một ví dụ rất rõ trong chính bộ dữ liệu này.

Cột `signup_date` trong bảng `customers` nghe tên là "ngày đăng ký tài khoản". Nếu tin vào tên cột, bạn
sẽ tính được "khách hàng này đã gắn bó bao lâu rồi" bằng cách lấy ngày đặt hàng trừ ngày đăng ký — một
đặc trưng rất hợp lý trong bài toán dự báo.

Nhưng khi kiểm tra thực tế, **73,8% đơn hàng có ngày đặt trước ngày đăng ký**. Kết quả phép trừ ra số
âm. Nếu không kiểm tra, bạn sẽ đưa một đặc trưng vô nghĩa vào mô hình mà không hề biết.

Đó là lý do nguyên tắc xuyên suốt là: **không mô tả bất kỳ điều gì chưa kiểm chứng trực tiếp trên dữ
liệu**. Tên cột chỉ là gợi ý, không phải bằng chứng.

### 1.3. Toàn vẹn tham chiếu — nghe phức tạp nhưng ý rất đơn giản

Bảng `orders` có cột `customer_id`. Câu hỏi là: **mọi giá trị `customer_id` trong `orders` có thực sự
tồn tại trong bảng `customers` không?**

Nếu có đơn hàng ghi `customer_id = 999999` mà bảng khách hàng không có ai mang mã đó, thì đó là **bản
ghi mồ côi** — dữ liệu bị hỏng. Khi nối bảng, đơn hàng đó sẽ biến mất hoặc sinh ra giá trị trống.

Cách kiểm tra bằng Python rất ngắn:

```python
# Lấy tập hợp tất cả customer_id có trong bảng customers
ma_khach_hop_le = set(customers.customer_id)

# Đếm xem có bao nhiêu đơn hàng mang mã không nằm trong tập đó
so_mo_coi = (~orders.customer_id.isin(ma_khach_hop_le)).sum()
```

Làm như vậy cho cả 16 cặp quan hệ, tổng cộng hơn 4 triệu bản ghi, kết quả đều bằng 0.

**Ý nghĩa thực tiễn:** mọi phép nối bảng đều an toàn, không cần bước làm sạch khóa. Nhưng cũng là một
dấu hiệu cho thấy đây là dữ liệu mô phỏng — dữ liệu vận hành thật gần như luôn có vài bản ghi hỏng.

### 1.4. Cột suy diễn — khái niệm quan trọng nhất

**Cột suy diễn** là cột có thể tính lại được từ các cột khác, nên nó **không mang thông tin mới**.

Ví dụ cụ thể trong bảng `inventory`:

| `stockout_days` | `fill_rate` |
|---:|---:|
| 2 | 0,9333 |
| 1 | 0,9667 |
| 0 | 1,0000 |

Nhìn kỹ sẽ thấy: `1 − 2/30 = 0,9333` và `1 − 1/30 = 0,9667`. Vậy `fill_rate` chỉ là `stockout_days`
viết theo cách khác.

**Cách kiểm chứng:** đặt giả thuyết công thức rồi so khớp trên toàn bộ dữ liệu.

```python
import numpy as np
# Giả thuyết: fill_rate = 1 - stockout_days/30
gia_thuyet = 1 - inventory.stockout_days / 30
ty_le_khop = np.isclose(inventory.fill_rate, gia_thuyet).mean()
# Kết quả: 1.0  → khớp 100%, giả thuyết đúng
```

Điểm cần hiểu: **phương pháp này cũng bác bỏ được giả thuyết sai.** Khi thử `refund_amount` bằng
`return_quantity × unit_price`, tỷ lệ khớp chỉ 0,6% → giả thuyết sai, cột đó không suy diễn được. Chính
việc có trường hợp bị bác bỏ mới chứng minh cách làm là kiểm chứng chứ không phải đoán.

### 1.5. Vì sao cột suy diễn gây hại

Giả sử bạn đưa cả `stockout_days` và `fill_rate` vào mô hình học máy. Vì hai biến này là **hàm tuyến
tính của nhau**, mô hình không có cách nào phân biệt đóng góp của từng biến.

Hậu quả gọi là **đa cộng tuyến** (multicollinearity):

- Trọng số của hai biến trở nên bất ổn định, đổi mạnh khi dữ liệu thay đổi chút ít
- Biểu đồ "tầm quan trọng đặc trưng" cho kết quả sai lệch — mô hình có thể xếp hạng cao một biến chỉ vì
  nó là bản sao
- Bạn không rút ra được kết luận đúng về yếu tố nào thực sự ảnh hưởng doanh thu

Nên phải phát hiện và loại bỏ từ giai đoạn mô tả dữ liệu, chứ không đợi đến lúc huấn luyện.

---

## Phần 2 — ERD: từ tệp CSV đến mô hình khái niệm

### 2.1. Hai loại sơ đồ hay bị nhầm

Đây là chỗ đã vẽ sai một lần, nên cần hiểu kỹ.

| | ERD (mức khái niệm) | Relational Diagram (mức logic) |
|---|---|---|
| Hình vẽ | Chữ nhật, hình thoi, elip | Các bảng có danh sách cột |
| Trả lời câu hỏi | Dữ liệu **là gì**, liên quan ra sao | Dữ liệu **lưu ở đâu**, khóa nào |
| Khóa ngoại | Không xuất hiện | Xuất hiện thành cột FK |
| Giai đoạn | Phân tích nghiệp vụ | Thiết kế cơ sở dữ liệu |

Cách nhớ: **ERD là bản vẽ phác của kiến trúc sư, Relational Diagram là bản vẽ thi công.** Kiến trúc sư
vẽ "phòng khách thông với bếp"; bản thi công mới ghi "cửa rộng 90cm, bản lề loại X".

Quy trình chuẩn đi theo thứ tự: ERD → ánh xạ → Relational Diagram.

### 2.2. Vì sao khóa ngoại phải biến mất

Đây là quy tắc gây khó hiểu nhất, nên giải thích bằng ví dụ.

Trong tệp CSV, bảng `orders` có cột `customer_id`. Cột này tồn tại để **máy tính biết đơn hàng thuộc về
khách nào**.

Nhưng trong ERD, ta đã vẽ một hình thoi *"đặt"* nối `CUSTOMERS` với `ORDERS`. Hình thoi đó **chính là**
lời khẳng định "đơn hàng thuộc về khách hàng". Nếu vẽ thêm cột `customer_id` vào ô `ORDERS` nữa thì ta
đang nói cùng một điều **hai lần**.

Nói cách khác: `customer_id` không phải một **tính chất** của đơn hàng (như ngày đặt, trạng thái); nó là
**cơ chế kỹ thuật** để nối bảng. Mô hình khái niệm mô tả tính chất và liên hệ, không mô tả cơ chế.

Trong bộ dữ liệu này có 15 cột khóa ngoại, tất cả đều chuyển thành quan hệ.

### 2.3. Thực thể yếu — hiểu bằng ví dụ đời thường

**Thực thể yếu** là thực thể không tự đứng độc lập được, phải dựa vào một thực thể khác mới xác định
được nó là ai.

Ví dụ đời thường: *"phòng số 3"* — câu này vô nghĩa nếu không nói rõ **phòng số 3 của tòa nhà nào**. Số
phòng chỉ có ý nghĩa trong phạm vi một tòa nhà. Vậy PHÒNG là thực thể yếu, TÒA NHÀ là thực thể chủ.

Áp dụng vào bộ dữ liệu:

| Thực thể yếu | Vì sao yếu |
|---|---|
| `ORDER_ITEMS` | Một "dòng hàng" chỉ có nghĩa khi biết nó thuộc đơn nào. Bản thân nó không có mã riêng |
| `PAYMENTS` | Khóa chính của nó chính là `order_id` — nó chỉ là phần mở rộng của đơn hàng |
| `SHIPMENTS` | Tương tự `PAYMENTS` |
| `INVENTORY` | Một dòng tồn kho được xác định bởi **cặp** (ngày chốt sổ, sản phẩm), không chỉ bởi ngày |

Trên sơ đồ, thực thể yếu vẽ **viền đôi**, và quan hệ nối nó với thực thể chủ vẽ **hình thoi viền đôi**
(gọi là quan hệ định danh, vì chính quan hệ đó cấp cho nó danh tính).

### 2.4. Vì sao `ORDER_ITEMS` phải là thực thể chứ không phải hình thoi

Câu này rất dễ bị hỏi, và câu trả lời khá tinh tế.

Trong ký hiệu Chen, khi hai thực thể có quan hệ **nhiều–nhiều** và quan hệ đó mang thuộc tính riêng, ta
thường vẽ nó thành **hình thoi có thuộc tính**. Một đơn hàng chứa nhiều sản phẩm, một sản phẩm nằm trong
nhiều đơn hàng — đúng là nhiều–nhiều, và có thuộc tính riêng là `quantity`, `unit_price`. Vậy theo lẽ
thường phải vẽ hình thoi.

**Nhưng không được**, vì `ORDER_ITEMS` còn tham gia ba quan hệ khác: với `PROMOTIONS` (khuyến mại nào áp
dụng), với `RETURNS` (bị trả lại), với `REVIEWS` (được đánh giá).

Trong ký hiệu Chen, **một quan hệ không thể có quan hệ con**. Chỉ thực thể mới nối được với quan hệ. Nên
`ORDER_ITEMS` buộc phải là thực thể. Loại thực thể này gọi là **thực thể kết hợp** (associative entity).

### 2.5. Bản số và mức độ tham gia — hai thứ khác nhau

Nhiều người nhầm hai khái niệm này. Chúng trả lời hai câu hỏi khác nhau:

**Bản số** trả lời: *một bên có bao nhiêu bản thể ứng với một bản thể bên kia?*
→ Ghi bằng số `1` hoặc `N` cạnh thực thể.

**Mức độ tham gia** trả lời: *có bắt buộc mọi bản thể đều phải tham gia quan hệ không?*
→ Thể hiện bằng đường đôi (bắt buộc) hoặc đường đơn (tùy chọn).

Ví dụ quan hệ giữa `ORDERS` và `SHIPMENTS`:

- **Bản số 1:1** — một đơn hàng có tối đa một lần giao vận, một lần giao vận thuộc đúng một đơn
- **Tham gia:** phía `SHIPMENTS` là **đường đôi** (mọi bản ghi giao vận đều phải thuộc về một đơn), phía
  `ORDERS` là **đường đơn** (chỉ 87,5% đơn có giao vận — đơn bị hủy thì không bao giờ được giao)

Nếu chỉ ghi bản số mà không ghi mức tham gia, người đọc sẽ tưởng mọi đơn hàng đều được giao.

Các con số tham gia đều đo trên dữ liệu:

| Bên tham gia | Tỷ lệ | Kết luận |
|---|---:|---|
| Đơn hàng có dòng hàng | 100% | Toàn bộ — đường đôi |
| Đơn hàng có thanh toán | 100% | Toàn bộ — đường đôi |
| Đơn hàng có giao vận | 87,5% | Bộ phận — đường đơn |
| Khách hàng từng đặt hàng | 74,0% | Bộ phận — đường đơn |
| Sản phẩm từng được bán | 66,3% | Bộ phận — đường đơn |

### 2.6. Vì sao có đường vẽ nét đứt

Nét đứt đánh dấu **liên kết không phải khóa ngoại vật lý** — tức là quan hệ có thật về mặt nghiệp vụ,
nhưng trong tệp CSV không có cột nào biểu diễn nó. Có hai loại:

**Loại một — liên kết theo trục thời gian.** Bảng `sales` không có cột nào trỏ sang `orders`. Nhưng khi
kiểm tra, tập ngày trong `sales` **trùng khớp tuyệt đối** với tập ngày đặt hàng trong `orders` — cùng
3.833 ngày, không lệch ngày nào. Quan hệ tồn tại thật, chỉ là nối qua giá trị ngày chứ không qua mã
khóa.

**Loại hai — liên kết qua cột dư thừa.** Bảng `orders` có cột `zip`, nhưng cột này trùng khớp 100% với
`zip` của khách hàng tương ứng. Nghĩa là nó chỉ là bản sao, có thể suy ra từ `CUSTOMERS`. Quan hệ
`ORDERS`–`GEOGRAPHY` tồn tại nhưng là dư thừa, nên vẽ nét đứt.

### 2.7. Phép đối soát — cách chứng minh sơ đồ không sai sót

Đây là kỹ thuật đơn giản nhưng rất thuyết phục khi bảo vệ:

```
93 cột (13 tệp)  −  15 cột khóa ngoại  −  3 cột sao chép  =  75 thuộc tính
```

Ý nghĩa: mỗi cột trong dữ liệu gốc phải có một trong ba số phận, không có ngoại lệ:

1. Trở thành **thuộc tính** trên sơ đồ (75 cột)
2. Trở thành **quan hệ** vì nó là khóa ngoại (15 cột)
3. Bị **loại bỏ có lý do ghi rõ** (3 cột sao chép từ `PRODUCTS`)

Đếm số elip trên sơ đồ được đúng 75. Vậy không cột nào bị bỏ quên, cũng không có thuộc tính nào được
bịa thêm.

---

## Phần 3 — Vì sao phải rà soát bốn lần

Sơ đồ này sửa bốn lần, mỗi lần đều tìm ra lỗi thật. Hiểu **vì sao mắc lỗi** quan trọng hơn là nhớ đã
sửa gì.

### Lỗi 1 — Vẽ nhầm loại sơ đồ

**Nguyên nhân:** trong ngành phần mềm, người ta thường gọi cả sơ đồ chân chim là "ERD". Nhưng trong môn
Cơ sở dữ liệu, "ERD" có nghĩa hẹp hơn: mô hình khái niệm ký hiệu Chen.

**Bài học:** thuật ngữ có thể khác nhau giữa môi trường công nghiệp và học thuật. Khi làm khóa luận, nên
theo định nghĩa của môn học.

### Lỗi 2 — Vẽ `SALES` tách rời

**Nguyên nhân:** suy luận theo cấu trúc tệp — "không có cột khóa ngoại thì không có quan hệ".

**Sai ở đâu:** ERD mô tả **quan hệ nghiệp vụ**, không phải cấu trúc tệp. Doanh thu một ngày rõ ràng có
liên hệ với các đơn hàng của ngày đó, dù không có cột nào nói lên điều đó.

**Bài học:** khi mô hình hóa khái niệm, phải hỏi *"trong thực tế chúng có liên quan không?"* trước, rồi
mới tìm bằng chứng trong dữ liệu — chứ không phải ngược lại.

### Lỗi 3 — `RETURNS` và `REVIEWS` nối sai đích

**Nguyên nhân:** thấy bảng `returns` có hai cột `order_id` và `product_id`, nên vẽ hai quan hệ riêng —
một tới `ORDERS`, một tới `PRODUCTS`.

**Sai ở đâu:** hai cột đó **đi cùng nhau**, chúng cùng trỏ tới **một dòng hàng cụ thể** trong
`ORDER_ITEMS`. Kiểm chứng: mọi cặp `(order_id, product_id)` của `returns` đều tồn tại trong
`order_items`, không lệch dòng nào.

**Cách hiểu trực quan:** bạn trả lại *"hai cái áo size M màu đỏ trong đơn số 5"* — đó là một dòng hàng.
Bạn không trả lại "đơn số 5" và đồng thời trả lại "áo màu đỏ" như hai việc riêng biệt.

**Bài học:** khi một bảng có nhiều cột khóa ngoại, phải kiểm tra xem chúng độc lập hay đi thành cặp.

### Lỗi 4 — Bỏ sót thuộc tính suy diễn và sai bản số

**Nguyên nhân:** chỉ kiểm tra một số công thức dễ thấy, chưa thử hết.

**Bài học:** việc kiểm chứng cần làm có hệ thống — duyệt qua từng cột và đặt câu hỏi "cột này có tính
lại được từ cột khác không", chứ không chỉ kiểm những cột trông đáng ngờ.

---

## Phần 4 — Tự kiểm tra hiểu bài

Nếu trả lời được sáu câu sau mà không nhìn tài liệu, bạn đã nắm đủ để bảo vệ:

1. Vì sao cột khóa ngoại không xuất hiện trên ERD, trong khi nó có thật trong tệp CSV?
2. `PAYMENTS` khác `ORDERS` ở chỗ nào mà bị coi là thực thể yếu?
3. Bản số và mức độ tham gia khác nhau ra sao? Cho một ví dụ trong sơ đồ.
4. Vì sao có hai cột dữ liệu tương quan hoàn hảo lại là điều xấu cho mô hình?
5. Làm sao chứng minh sơ đồ không bỏ sót cột nào của dữ liệu gốc?
6. Nếu thầy/cô nói *"em vẽ thiếu, `sample_submission` đâu?"*, bạn trả lời thế nào?

*(Đáp án nằm rải trong tài liệu này: câu 1 ở mục 2.2, câu 2 ở mục 2.3, câu 3 ở mục 2.5, câu 4 ở mục 1.5,
câu 5 ở mục 2.7, câu 6 ở mục 2.1 kết hợp quy tắc bốn trong
[phuong-phap-thuc-hien.md](phuong-phap-thuc-hien.md).)*
