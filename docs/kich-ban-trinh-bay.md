# Kịch bản trình bày: Từ điển dữ liệu và Sơ đồ ERD

> Thời lượng dự kiến **8–10 phút**. Phần in nghiêng là ghi chú thao tác, không đọc lên.
> Tài liệu tham chiếu: [phuong-phap-thuc-hien.md](phuong-phap-thuc-hien.md) ·
> [giai-thich-cach-lam.md](giai-thich-cach-lam.md)

---

## Mở đầu — 30 giây

*Mở sẵn hai file: `erd.svg` và `data-dictionary.md`.*

> Thưa thầy/cô, phần em trình bày hôm nay là bước chuẩn bị dữ liệu cho đề tài dự báo doanh thu.
>
> Bộ dữ liệu em nhận được gồm 14 tệp CSV, khoảng 2,96 triệu bản ghi, 96 trường, **không kèm bất kỳ tài
> liệu mô tả nào**. Không biết cột nào là khóa, các bảng nối với nhau ra sao, cột nào đáng tin.
>
> Em đã xây dựng hai sản phẩm: một **từ điển dữ liệu** mô tả toàn bộ 96 trường, và một **sơ đồ ERD**
> mức khái niệm. Nguyên tắc xuyên suốt là **không mô tả bất kỳ điều gì chưa được kiểm chứng trực tiếp
> trên dữ liệu**.

---

## Phần A — Từ điển dữ liệu · 3 phút

### A1. Vì sao phải làm trước

> Nếu bắt tay mô hình hóa ngay mà chưa hiểu dữ liệu thì mọi kết quả về sau đều không có cơ sở. Nên em
> làm từ điển trước.

### A2. Quy trình bốn bước

*Có thể chiếu bảng bốn bước, hoặc chỉ nói.*

> Em làm theo bốn bước.
>
> **Bước một, kiểm kê cấu trúc.** Với từng tệp, em xác định số dòng, kiểu dữ liệu từng cột, số giá trị
> thiếu, và miền giá trị. Điểm em muốn nhấn mạnh là với biến phân loại, em **liệt kê đầy đủ các giá trị**
> chứ không chỉ ghi "kiểu chuỗi". Nhờ vậy mới phát hiện `order_status` chỉ nhận đúng 6 giá trị và chúng
> tuân theo một vòng đời có quy luật.
>
> **Bước hai, xác định khóa chính.** Bước này tưởng hiển nhiên nhưng cho ra một phát hiện quan trọng:
> bảng `order_items` **không có khóa tự nhiên hợp lệ**, vì có 16 cặp `order_id` và `product_id` bị trùng
> trên tổng số 714.669 dòng. Nếu em cứ tin cặp đó là khóa mà không kiểm tra, mọi phép nối về sau sẽ nhân
> dòng sai.
>
> **Bước ba, kiểm định toàn vẹn tham chiếu.** Em kiểm tra 16 quan hệ khóa ngoại trên tổng cộng hơn 4
> triệu bản ghi, kết quả **không có bản ghi mồ côi nào**. Đồng thời em đo độ phủ ngược lại, tức bao nhiêu
> phần trăm bản ghi ở bảng cha thực sự được tham chiếu — con số này về sau dùng để xác định quan hệ là
> bắt buộc hay tùy chọn.
>
> **Bước bốn, phát hiện cột dư thừa và cột suy diễn.** Đây là bước tốn công nhất nhưng giá trị cao nhất.

### A3. Cách phát hiện cột suy diễn — điểm nhấn

*Đây là phần nên nói kỹ, vì nó thể hiện phương pháp.*

> Cách làm của em là **đặt giả thuyết về công thức, rồi so khớp trên toàn bộ dữ liệu**.
>
> Ví dụ em nghi cột `fill_rate` không phải số đo độc lập. Em thử công thức `1 trừ stockout_days chia 30`
> và so khớp — kết quả **đúng 100% trên cả 60.247 dòng**. Vậy đó là cột suy diễn.
>
> Em làm tương tự với năm cột khác và đều xác nhận. Nhưng quan trọng không kém là **có hai giả thuyết bị
> bác bỏ**: em thử `refund_amount` bằng `return_quantity` nhân `unit_price` thì chỉ khớp 0,6 phần trăm,
> và `overstock_flag` theo ngưỡng tồn kho thì ngưỡng tốt nhất cũng chỉ khớp 83 phần trăm. Nên hai cột đó
> em giữ nguyên là thuộc tính thường.
>
> Em nêu hai trường hợp bị bác bỏ này để cho thấy phương pháp **có tính kiểm chứng**, không phải nhìn tên
> cột rồi đoán.

### A4. Vì sao cột suy diễn quan trọng

> Cột suy diễn không mang thông tin mới. Nếu em đưa cả `stockout_days` lẫn `fill_rate` vào mô hình học
> máy thì hai biến này tương quan hoàn hảo với nhau, gây **đa cộng tuyến**, làm sai lệch thước đo tầm
> quan trọng đặc trưng. Nên phải phát hiện và loại bỏ ngay từ giai đoạn mô tả dữ liệu.

### A5. Ba phát hiện nổi bật

*Nói nhanh, mỗi ý một câu. Nếu thiếu thời gian, chỉ nói ý 1.*

> Từ điển cuối cùng mô tả 96 trường kèm 17 cảnh báo chất lượng dữ liệu. Ba phát hiện đáng chú ý nhất:
>
> **Một là**, hai biến mục tiêu `Revenue` và `COGS` **tái tạo được chính xác tuyệt đối** từ các bảng giao
> dịch chi tiết, sai số bằng không trên cả 3.833 ngày. Có ba điểm rất dễ hiểu nhầm: doanh thu là **gộp**,
> không trừ giảm giá; tính **cả đơn đã hủy và đơn bị trả**; và mốc thời gian là **ngày đặt hàng**.
>
> **Hai là**, có **73,8 phần trăm đơn hàng được đặt trước ngày đăng ký tài khoản** của chính khách hàng
> đó — điều bất khả thi về nghiệp vụ. Hệ quả là mọi đặc trưng dựa trên ngày đăng ký đều không dùng được.
>
> **Ba là**, có 814 trên 2.412 sản phẩm chưa từng phát sinh giao dịch, làm lệch mọi thống kê về giá nếu
> không lọc bỏ trước.

---

## Phần B — Sơ đồ ERD · 4 phút

### B1. Chọn đúng loại sơ đồ

*Đây là chỗ dễ bị hỏi nhất. Nói rõ ràng, chậm.*

> Trước khi vẽ, em phải xác định vẽ loại nào, vì có hai loại sơ đồ hay bị gọi lẫn là ERD.
>
> **ERD mức khái niệm** dùng ký hiệu Chen: thực thể là hình chữ nhật, quan hệ là hình thoi, thuộc tính là
> hình elip. Nó trả lời câu hỏi *dữ liệu là gì và liên quan với nhau ra sao*.
>
> **Relational Diagram mức logic** thì vẽ các bảng có khóa chính khóa ngoại, trả lời câu hỏi *dữ liệu lưu
> trong bảng nào*.
>
> Quy trình thiết kế cơ sở dữ liệu đi theo thứ tự ERD trước, rồi ánh xạ sang mô hình quan hệ. Nên sản
> phẩm em nộp là **ERD mức khái niệm, ký hiệu Chen**.

### B2. Bốn quy tắc chuyển đổi

*Chiếu `erd.svg`. Vừa nói vừa chỉ vào hình.*

> Điểm mấu chốt là **ERD không phải bản chép lại cấu trúc tệp CSV**. Em áp dụng bốn quy tắc.
>
> **Quy tắc một: khóa ngoại không được vẽ thành thuộc tính.** Ví dụ bảng `orders` có cột `customer_id`.
> Trong ERD, cột này **biến mất**, thay bằng hình thoi *"đặt"* nối `CUSTOMERS` với `ORDERS`.
> *(Chỉ vào hình thoi "đặt".)* Vì liên kết đã do hình thoi biểu diễn rồi, vẽ thêm cột khóa ngoại là mô tả
> trùng một thứ hai lần. Tổng cộng 15 cột khóa ngoại đã chuyển thành quan hệ.
>
> **Quy tắc hai: nhận diện thực thể yếu.** *(Chỉ vào ORDER_ITEMS viền đôi.)* Thực thể yếu là thực thể
> không tự định danh được, phải mượn khóa của thực thể chủ. Em có bốn thực thể yếu, vẽ viền đôi và nối
> bằng hình thoi viền đôi. Ví dụ `PAYMENTS` có khóa chính chính là `order_id` của `ORDERS`.
>
> **Quy tắc ba: đánh dấu thuộc tính suy diễn.** *(Chỉ vào elip nét đứt của INVENTORY.)* Kết quả kiểm
> chứng công thức ở phần trước được thể hiện trực tiếp lên hình bằng elip nét đứt. Có 11 thuộc tính như
> vậy. Riêng bảng `INVENTORY` thì 6 trên 13 thuộc tính là suy diễn — tức quá nửa bảng không mang thông
> tin độc lập.
>
> **Quy tắc bốn: loại bỏ cái không phải thực thể nghiệp vụ.** Em loại `sample_submission.csv` vì nó là
> khuôn dạng nộp kết quả dự báo, chứa ngày tương lai với giá trị chỉ mang tính minh họa — đó là quy ước
> kỹ thuật, không phải dữ liệu nghiệp vụ.

### B3. Đối soát — chứng minh không sót không bịa

*Viết công thức lên bảng nếu có thể. Đây là điểm mạnh nên nói.*

> Để chứng minh sơ đồ khớp chính xác với dữ liệu gốc, em làm phép đối soát:
>
> **93 cột của 13 tệp, trừ 15 cột khóa ngoại, trừ 3 cột sao chép, bằng 75 thuộc tính.**
>
> Con số 75 khớp đúng với số elip trên sơ đồ. Nghĩa là mọi cột của dữ liệu gốc đều được truy vết: hoặc
> thành thuộc tính, hoặc thành quan hệ, hoặc bị loại bỏ có lý do ghi rõ. Ba cột bị loại là
> `product_name`, `category`, `segment` trong bảng tồn kho, vì chúng là bản sao nguyên văn từ `PRODUCTS`.

### B4. Bản số và mức độ tham gia

> Bản số em **không suy đoán từ tên bảng** mà đo trực tiếp. Ví dụ quan hệ giữa dòng hàng và đánh giá: em
> đếm được 113.551 đánh giá ứng đúng 113.551 cặp khác nhau, nghĩa là mỗi dòng hàng có tối đa **một** đánh
> giá, nên bản số là 1:1. Còn trả hàng thì có 39.939 dòng trên 39.937 cặp, tức có dòng hàng bị trả nhiều
> lần, nên là 1:N.
>
> Ngoài bản số, sơ đồ còn thể hiện **mức độ tham gia**. *(Chỉ vào một đường đôi và một đường đơn.)*
> Đường đôi nghĩa là tham gia toàn bộ — 100% đơn hàng đều có dòng hàng và đều có bản ghi thanh toán.
> Đường đơn nghĩa là tham gia bộ phận — chỉ 87,5% đơn có giao vận, 74% khách hàng từng đặt hàng, và
> 66,3% sản phẩm từng được bán.
>
> Sơ đồ dùng **thuần ký hiệu Chen**: bản số chỉ ghi 1 hoặc N, còn tính bắt buộc hay tùy chọn thể hiện
> bằng kiểu đường, không trộn với hệ ký hiệu min-max.

---

## Phần C — Quá trình rà soát · 1,5 phút

*Phần này nghe như tự nhận lỗi, nhưng thực ra là điểm mạnh nhất. Nói tự tin.*

> Em muốn trình bày thêm về quá trình kiểm chứng, vì sơ đồ này trải qua bốn vòng rà soát và **vòng nào
> cũng tìm ra lỗi**.
>
> **Vòng một**, em vẽ nhầm loại sơ đồ — vẽ ra Relational Diagram thay vì ERD. Em vẽ lại theo ký hiệu Chen.
>
> **Vòng hai**, em vẽ `SALES` tách rời không nối gì, vì trong tệp CSV nó không có cột khóa ngoại nào.
> Nhưng khi kiểm tra thì tập ngày của `SALES` **trùng khớp tuyệt đối** với tập ngày đặt hàng của
> `ORDERS`. Quan hệ tồn tại thật, chỉ là không hiện ra dưới dạng cột. Em bổ sung quan hệ và vẽ nét đứt để
> phân biệt với khóa ngoại vật lý.
>
> **Vòng ba**, em nối `RETURNS` và `REVIEWS` tới `ORDERS` và `PRODUCTS` một cách riêng lẻ. Kiểm tra cho
> thấy cặp `order_id` và `product_id` của chúng nằm trọn trong `ORDER_ITEMS`, không lệch dòng nào. Nghĩa
> là mỗi lượt trả hàng gắn với **một dòng hàng cụ thể** — em trả lại *hai cái áo size M màu đỏ trong đơn
> số 5*, chứ không phải trả đơn 5 và trả sản phẩm X một cách rời rạc. Em thay 4 quan hệ sai bằng 2 quan
> hệ đúng.
>
> **Vòng bốn**, em phát hiện thêm 6 thuộc tính suy diễn chưa đánh dấu và sửa một bản số bị sai.
>
> Em nêu quá trình này vì nó cho thấy các kết luận trong sơ đồ đều **đến từ kiểm chứng trên dữ liệu**,
> chứ không phải vẽ theo cảm tính rồi giữ nguyên.

---

## Kết — 30 giây

> Tóm lại, sản phẩm gồm từ điển dữ liệu mô tả 96 trường kèm 17 cảnh báo chất lượng, và sơ đồ ERD mức khái
> niệm với 13 thực thể, 75 thuộc tính, 15 quan hệ.
>
> Toàn bộ số liệu đều kiểm chứng được bằng cách chạy lại trên dữ liệu gốc. Đây là nền để em bước sang
> phần xây dựng đặc trưng và mô hình dự báo.
>
> Em xin hết ạ, mong thầy/cô góp ý.

---

## Dự phòng câu hỏi

*Đọc lướt trước khi vào phòng. Trả lời ngắn, đúng trọng tâm, không vòng vo.*

**Vì sao 14 tệp mà sơ đồ chỉ có 13 thực thể?**
> `sample_submission.csv` là khuôn dạng nộp kết quả dự báo, chứa 548 ngày tương lai với giá trị chỉ mang
> tính minh họa. Đó là quy ước kỹ thuật của cuộc thi chứ không phải thực thể nghiệp vụ. Nó vẫn được mô tả
> đầy đủ trong từ điển dữ liệu ạ.

**Vì sao khóa ngoại không xuất hiện trong sơ đồ?**
> Vì đây là ERD mức khái niệm. Liên kết giữa các thực thể đã do hình thoi quan hệ biểu diễn; vẽ thêm cột
> khóa ngoại là mô tả trùng. Khóa ngoại chỉ xuất hiện sau bước ánh xạ sang mô hình quan hệ ạ.

**Vì sao `ORDER_ITEMS` là thực thể mà không phải hình thoi?**
> Trong ký hiệu Chen, quan hệ nhiều–nhiều có thuộc tính thường vẽ thành hình thoi. Nhưng `ORDER_ITEMS`
> còn tham gia ba quan hệ khác với `PROMOTIONS`, `RETURNS` và `REVIEWS`. Một quan hệ không thể có quan hệ
> con, nên nó bắt buộc phải là thực thể ạ.

**Vì sao một số đường vẽ nét đứt?**
> Nét đứt đánh dấu liên kết không phải khóa ngoại vật lý, gồm hai loại: liên kết theo trục thời gian như
> `SALES` với `ORDERS`, và liên kết qua cột dư thừa suy được từ nơi khác như `ORDERS` với `GEOGRAPHY` ạ.

**Làm sao biết `SALES` là thực thể suy diễn?**
> Vì em tái tạo được nó chính xác tuyệt đối từ dữ liệu giao dịch. `Revenue` bằng tổng của `quantity` nhân
> `unit_price`, `COGS` bằng tổng của `quantity` nhân `cogs`, gộp theo ngày đặt hàng. Sai số bằng 0,00
> trên toàn bộ 3.833 ngày ạ.

**Bộ dữ liệu này có phải dữ liệu thực tế không?**
> Em nghĩ là dữ liệu mô phỏng ạ. Có nhiều dấu hiệu: toàn vẹn tham chiếu tuyệt đối trên hơn 4 triệu bản
> ghi, `quantity` phân bố đều gần như hoàn hảo trên 8 mức, `fill_rate` là hàm xác định của
> `stockout_days` với mẫu số cố định 30, và tính mùa vụ ngược với quy luật bán lẻ thời trang. Nên các kết
> luận nghiệp vụ cần diễn giải thận trọng ạ.

**Em dùng công cụ gì để làm?**
> Em dùng Python với thư viện `pandas` để kiểm định dữ liệu, và draw.io để vẽ sơ đồ ạ. File nguồn
> `.drawio` em vẫn giữ để chỉnh sửa được.

---

## Bảng tra nhanh

*Liếc khi cần con số giữa lúc trả lời.*

| Chỉ tiêu | Giá trị |
|---|---|
| Số tệp / bản ghi / trường | 14 · 2.960.736 · 96 |
| Khoảng thời gian lịch sử | 04/07/2012 – 31/12/2022 · 3.833 ngày, không thiếu ngày nào |
| Giai đoạn cần dự báo | 01/01/2023 – 01/07/2024 · 548 ngày |
| Quan hệ đã kiểm định | 16, trên 4.055.881 bản ghi · **0 mồ côi** |
| ERD | 13 thực thể · 75 thuộc tính · 15 quan hệ |
| Trong đó | 4 thực thể yếu · 1 thực thể suy diễn · 11 thuộc tính suy diễn |
| Cảnh báo chất lượng dữ liệu | 17 |
| Sai số tái tạo biến mục tiêu | 0,00 trên 3.833/3.833 ngày |
