# Kịch bản trình bày — Từ điển dữ liệu và Sơ đồ ERD

> **Cách dùng:** phần trong khung `▶ MÀN HÌNH` là thao tác, **không đọc lên**.
> Phần chữ thường in nghiêng là lời nói, đọc gần như nguyên văn được.
> Tổng thời lượng **10 phút** + hỏi đáp.

---

## CHUẨN BỊ TRƯỚC KHI VÀO (2 phút)

Mở sẵn **4 tab trình duyệt** theo đúng thứ tự này, để chuyển tab là đúng mạch:

| Tab | File | Cuộn sẵn tới |
|---|---|---|
| 1 | Repo GitHub, nhánh `docs/duythong` | Thư mục `docs/` |
| 2 | `data-dictionary.md` | Đầu file |
| 3 | `erd.md` (có nhúng sơ đồ) | Ảnh sơ đồ ở đầu |
| 4 | `quy-trinh-kiem-dinh.md` | Bước 5 |

**Không mở** file `.drawio` — dễ lỡ tay làm hỏng sơ đồ trước mặt hội đồng.

Chuẩn bị sẵn một tờ giấy ghi 3 con số: `0 mồ côi / 4.815.470` · `93 − 15 − 3 = 75` · `sai số 0,00 / 3.833 ngày`.

---

## CHẶNG 1 — MỞ ĐẦU · 1 phút

```
▶ MÀN HÌNH: Tab 1 — repo GitHub, thấy được danh sách file trong docs/
```

*"Dạ em xin phép trình bày phần em phụ trách trong đề tài, là **từ điển dữ liệu và sơ đồ ERD**.*

*Đề tài của nhóm em là dự báo doanh thu và giá vốn hàng bán theo ngày. Bộ dữ liệu em nhận được gồm **14
tệp CSV, gần 3 triệu bản ghi, 96 trường**, trải từ tháng 7 năm 2012 đến hết 2022.*

*Khó khăn lớn nhất là dữ liệu **không kèm bất kỳ tài liệu mô tả nào**. Em không biết cột nào là khóa,
các bảng nối với nhau ra sao, cột nào đáng tin.*

```
▶ CHỈ VÀO: danh sách file trong docs/
```

*Toàn bộ sản phẩm em để trên repo này ạ: sơ đồ ERD, từ điển dữ liệu, và một tài liệu ghi lại quy trình
kiểm định có mã nguồn chạy lại được.*

*Nguyên tắc em đặt ra và tuân thủ xuyên suốt là: **không mô tả bất kỳ điều gì mà em chưa kiểm chứng
trực tiếp trên dữ liệu**. Tên cột chỉ là gợi ý, không phải bằng chứng."*

---

## CHẶNG 2 — TỪ ĐIỂN DỮ LIỆU · 3 phút

```
▶ MÀN HÌNH: chuyển sang Tab 2 — data-dictionary.md
```

### 2.1. Vì sao bước này không thể bỏ qua *(45 giây)*

*"Em xin lấy ngay một ví dụ để thấy nếu bỏ qua bước này thì hậu quả ra sao.*

*Bảng khách hàng có cột `signup_date`, nghe tên là ngày đăng ký tài khoản. Nếu tin vào tên cột, em có
thể tính đặc trưng 'khách hàng đã gắn bó bao lâu' bằng cách lấy ngày đặt hàng trừ ngày đăng ký — một
đặc trưng rất hợp lý cho bài toán dự báo.*

***Nhưng khi kiểm tra thật, 73,8% đơn hàng có ngày đặt TRƯỚC ngày đăng ký của chính khách hàng đó.***
*Phép trừ ra số âm. Nếu không kiểm tra, nhóm em đã đưa một đặc trưng vô nghĩa vào mô hình mà không hề
hay biết."*

### 2.2. Quy trình bốn bước *(30 giây)*

*"Em làm theo bốn bước: **kiểm kê cấu trúc** → **xác định khóa chính** → **kiểm định toàn vẹn tham
chiếu** → **phát hiện cột dư thừa và cột suy diễn**.*

*Em xin đi sâu vào bước thứ tư, vì đó là bước tốn công nhất nhưng cho giá trị cao nhất."*

### 2.3. Cách phát hiện cột suy diễn *(1 phút — nói kỹ nhất)*

```
▶ CUỘN TỚI: mục 9 — inventory.csv, phần fill_rate
```

*"**Câu hỏi em đặt ra:** cột `fill_rate` có phải một số đo độc lập không, hay chỉ là cột khác viết theo
cách khác?*

***Cách em kiểm tra:*** *đặt giả thuyết về công thức, rồi so khớp trên toàn bộ dữ liệu. Em thử*
*`fill_rate = 1 trừ stockout_days chia 30`.*

***Kết quả:*** *khớp **100% trên cả 60.247 dòng**. Vậy đó là cột suy diễn.*

*Em làm tương tự và xác nhận thêm bốn cột nữa. **Nhưng quan trọng không kém là có hai giả thuyết bị bác
bỏ**: `refund_amount` bằng `return_quantity` nhân `unit_price` chỉ khớp 0,64%, và `overstock_flag` theo
ngưỡng tồn kho thì ngưỡng tốt nhất cũng chỉ khớp 83%. Hai cột đó em giữ nguyên là thuộc tính thường.*

*Em nêu hai trường hợp bị bác bỏ này để thấy phương pháp **có tính kiểm chứng thật**, không phải nhìn
tên cột rồi đoán ạ."*

### 2.4. Vì sao việc này quan trọng *(20 giây)*

*"Cột suy diễn không mang thông tin mới. Nếu nhóm em đưa cả `stockout_days` lẫn `fill_rate` vào mô hình
thì hai biến tương quan hoàn hảo với nhau, gây **đa cộng tuyến** — trọng số mô hình bất ổn định và biểu
đồ tầm quan trọng đặc trưng cho kết quả sai lệch."*

### 2.5. Kết quả *(25 giây)*

```
▶ CUỘN XUỐNG CUỐI FILE: bảng 17 cảnh báo chất lượng dữ liệu
```

*"Từ điển cuối cùng mô tả đầy đủ **96 trường của 14 bảng**, kèm bảng tổng hợp **17 cảnh báo chất lượng
dữ liệu** xếp theo mức nghiêm trọng.*

*Trong đó phát hiện lớn nhất là hai biến mục tiêu **tái tạo được chính xác tuyệt đối** từ các bảng giao
dịch — em sẽ nói kỹ ở phần sau ạ."*

---

## CHẶNG 3 — SƠ ĐỒ ERD · 4 phút

```
▶ MÀN HÌNH: chuyển sang Tab 3 — erd.md, thấy ảnh sơ đồ ở đầu file
▶ PHÓNG TO sơ đồ vừa đủ nhìn thấy toàn bộ
```

### 3.1. Quyết định đầu tiên: chọn đúng loại sơ đồ *(45 giây)*

*"Trước khi vẽ, em phải xác định vẽ loại nào, vì có hai loại sơ đồ hay bị gọi lẫn là ERD.*

***Relational Diagram*** *vẽ các bảng có cột khóa chính khóa ngoại, trả lời câu hỏi 'dữ liệu lưu trong
bảng nào'. Đó là mức logic.*

***ERD mức khái niệm*** *dùng ký hiệu Chen — thực thể là hình chữ nhật, quan hệ là hình thoi, thuộc tính
là hình elip. Nó trả lời 'dữ liệu là gì và liên quan với nhau ra sao'.*

*Quy trình thiết kế cơ sở dữ liệu đi theo thứ tự **ERD trước, rồi mới ánh xạ sang mô hình quan hệ**, nên
sản phẩm em nộp là ERD mức khái niệm ký hiệu Chen ạ."*

### 3.2. Quy tắc khó nhất: khóa ngoại biến mất *(1 phút)*

```
▶ CHỈ VÀO: hình thoi "đặt" giữa CUSTOMERS và ORDERS
```

*"Điều em nhận ra khi làm là **ERD không phải bản chép lại cấu trúc tệp CSV**. Em áp dụng bốn quy tắc,
trong đó quy tắc khó hiểu nhất là quy tắc đầu.*

*Bảng `orders` trong tệp CSV có cột `customer_id`. Nhưng trong ERD, cột này **biến mất** — thay bằng
hình thoi 'đặt' này đây.*

***Lý do:*** *hình thoi đó chính là lời khẳng định 'đơn hàng thuộc về khách hàng'. Nếu em vẽ thêm cột
`customer_id` vào ô `ORDERS` nữa thì em đang nói cùng một điều **hai lần**.*

*Nói cách khác, `customer_id` không phải một tính chất của đơn hàng như ngày đặt hay trạng thái — nó là
**cơ chế kỹ thuật** để nối bảng, mà mô hình khái niệm thì không mô tả cơ chế.*

*Tổng cộng **15 cột khóa ngoại đã được chuyển thành 15 mối quan hệ** ạ."*

### 3.3. Kết quả: phép đối soát *(45 giây)*

```
▶ CUỘN TỚI: mục 5 — Phép đối soát
▶ Nếu có bảng, viết lên: 93 − 15 − 3 = 75
```

*"Để chứng minh sơ đồ khớp chính xác với dữ liệu gốc, em làm một phép đối soát:*

***93 cột của 13 tệp, trừ 15 cột khóa ngoại, trừ 3 cột sao chép, bằng 75 thuộc tính.***

*Ba cột bị loại là `product_name`, `category`, `segment` trong bảng tồn kho — chúng là bản sao nguyên văn
từ bảng sản phẩm, thuộc về thực thể sản phẩm chứ không phải thuộc tính của tồn kho.*

*Đếm số hình elip trên sơ đồ được **đúng 75**. Nghĩa là mỗi cột của dữ liệu gốc đều được truy vết: hoặc
thành thuộc tính, hoặc thành quan hệ, hoặc bị loại bỏ có lý do ghi rõ. Không cột nào bị bỏ quên, cũng
không có thuộc tính nào em bịa thêm ạ."*

### 3.4. Thực thể yếu *(45 giây)*

```
▶ CUỘN LÊN SƠ ĐỒ, CHỈ VÀO: ORDER_ITEMS có viền đôi
```

*"Bốn thực thể vẽ **viền đôi** là thực thể yếu — không tự định danh được, phải mượn khóa của thực thể
chủ. Giống như nói 'phòng số 3' thì vô nghĩa nếu không nói rõ **phòng số 3 của tòa nhà nào**.*

*Ví dụ `ORDER_ITEMS` này. Em xếp nó là thực thể yếu vì khi kiểm tra khóa chính, em phát hiện **16 cặp
`(order_id, product_id)` bị trùng** trên 714.669 dòng — nên cặp đó **không phải khóa hợp lệ**.*

*Phát hiện này quan trọng về mặt thực hành: nếu em cứ tin cặp đó là khóa mà không kiểm tra, mọi phép nối
bảng về sau sẽ bị nhân dòng sai ạ."*

### 3.5. Bản số đo trên dữ liệu, không đoán *(45 giây)*

```
▶ CUỘN TỚI: mục 4 — bảng 15 mối quan hệ
```

*"Bản số em **không suy đoán từ tên bảng** mà đếm trực tiếp.*

*Ví dụ quan hệ giữa dòng hàng và đánh giá: em đếm được **113.551 đánh giá ứng đúng 113.551 cặp khác
nhau**, nghĩa là không cặp nào lặp lại, mỗi dòng hàng có tối đa **một** đánh giá — nên bản số là 1:1.*

*Còn trả hàng thì có 39.939 dòng trên 39.937 cặp, tức có dòng hàng bị trả nhiều lần — nên là 1:N.*

```
▶ CHỈ VÀO SƠ ĐỒ: một đường đôi và một đường đơn
```

*Ngoài bản số, sơ đồ còn thể hiện **mức độ tham gia** — đây là hai khái niệm khác nhau. Bản số trả lời
'một bên có bao nhiêu bản thể', còn mức tham gia trả lời 'có bắt buộc mọi bản thể đều tham gia không'.*

***Đường đôi*** *nghĩa là bắt buộc — 100% đơn hàng đều có dòng hàng và đều có bản ghi thanh toán.*
***Đường đơn*** *nghĩa là tùy chọn — chỉ 87,5% đơn có giao vận, vì đơn bị hủy thì không bao giờ được
giao ạ."*

---

## CHẶNG 4 — BẰNG CHỨNG · 1,5 phút

```
▶ MÀN HÌNH: chuyển sang Tab 4 — quy-trinh-kiem-dinh.md, Bước 5
```

*"Toàn bộ những con số em vừa trình bày đều **kiểm chứng lại được**. Em có tài liệu ghi lại 9 bước kiểm
định, mỗi bước gồm mã nguồn chạy được và kết quả thật khi chạy.*

```
▶ CHỈ VÀO: khối code và khối kết quả của Bước 5
```

*Đây là bước phát hiện cột suy diễn — bên trên là đoạn mã, bên dưới là kết quả in ra. Thầy/cô có thể
chạy lại để kiểm chứng ạ.*

***Ba kết quả kiểm định chính:***

- *Toàn vẹn tham chiếu: **15 quan hệ, 4.815.470 bản ghi, không có bản ghi mồ côi nào***
- *Đối soát thuộc tính: **93 trừ 15 trừ 3 bằng 75**, khớp với sơ đồ*
- *Biến mục tiêu tái tạo được với **sai số 0,00 trên cả 3.833 ngày***

```
▶ CUỘN TỚI: Bước 6 — công thức sinh biến mục tiêu
```

*Về điểm cuối, em xin nói rõ hơn vì đây là phát hiện quan trọng nhất. `Revenue` bằng tổng `quantity`
nhân `unit_price`, `COGS` bằng tổng `quantity` nhân `cogs`, gộp theo ngày đặt hàng.*

*Ba điều rút ra rất dễ hiểu nhầm nên em ghi rõ trong từ điển: doanh thu là **gộp**, không trừ giảm giá;
tính **cả đơn đã hủy và đơn bị trả lại**; và mốc thời gian là **ngày đặt hàng**, không phải ngày giao
hàng.*

*Nghĩa là khi nhóm em báo cáo kết quả dự báo, phải nói rõ đang dự báo **giá trị đặt hàng**, không phải
doanh thu ghi nhận theo chuẩn kế toán ạ."*

---

## CHẶNG 5 — CHỐT · 30 giây

```
▶ MÀN HÌNH: quay lại Tab 3 — sơ đồ ERD
```

*"Tóm lại, sản phẩm em hoàn thành gồm:*

- *Từ điển dữ liệu mô tả **96 trường của 14 bảng**, kèm 17 cảnh báo chất lượng*
- *Sơ đồ ERD mức khái niệm với **13 thực thể, 75 thuộc tính, 15 quan hệ***

*Toàn bộ số liệu đều kiểm chứng được bằng cách chạy lại trên dữ liệu gốc. Đây là cơ sở để nhóm em bước
sang giai đoạn xây dựng đặc trưng và mô hình dự báo.*

*Em xin hết ạ. Mong thầy/cô góp ý."*

---

# PHỤ LỤC — HỎI ĐÁP

## Bảy câu hay bị hỏi

**Vì sao 14 tệp mà sơ đồ chỉ có 13 thực thể?**
> *"`sample_submission.csv` là khuôn dạng nộp kết quả dự báo, chứa 548 ngày tương lai với giá trị chỉ
> mang tính minh họa. Đó là quy ước kỹ thuật của cuộc thi chứ không phải thực thể nghiệp vụ, nên em
> không đưa vào mô hình khái niệm. Nó vẫn được mô tả đầy đủ trong từ điển dữ liệu ạ."*

**Vì sao khóa ngoại không xuất hiện trong sơ đồ?**
> *"Vì đây là ERD mức khái niệm. Liên kết giữa các thực thể đã do hình thoi quan hệ biểu diễn rồi; vẽ
> thêm cột khóa ngoại là mô tả trùng một thứ hai lần. Khóa ngoại chỉ xuất hiện sau bước ánh xạ sang mô
> hình quan hệ ạ."*

**Vì sao `ORDER_ITEMS` là thực thể mà không phải hình thoi?**
> *"Trong ký hiệu Chen, quan hệ nhiều–nhiều có thuộc tính thường được vẽ thành hình thoi. Nhưng
> `ORDER_ITEMS` còn tham gia ba quan hệ khác với `PROMOTIONS`, `RETURNS` và `REVIEWS`. Một quan hệ không
> thể có quan hệ con, nên nó bắt buộc phải là thực thể ạ."*

**`returns.csv` có hai cột khóa ngoại, sao sơ đồ chỉ vẽ một quan hệ?**
> *"Dạ hai cột đó luôn đi thành cặp và cùng trỏ tới một dòng hàng cụ thể. Em đã kiểm chứng: mọi cặp
> `(order_id, product_id)` của `returns` đều nằm trọn trong `order_items`, không lệch dòng nào.*
>
> *Khách trả lại 'hai cái áo size M màu đỏ trong đơn số 5' — đó là một dòng hàng, chứ không phải trả đơn
> số 5 và trả sản phẩm X như hai việc riêng biệt. Khi ánh xạ sang mô hình quan hệ, quan hệ này sẽ tách
> thành cặp khóa ngoại đúng như trong tệp CSV ạ."*

**Vì sao có đường vẽ nét đứt?**
> *"Nét đứt đánh dấu liên kết không phải khóa ngoại vật lý, gồm hai loại: liên kết theo trục thời gian
> như `SALES` với `ORDERS`, và liên kết qua cột dư thừa suy được từ nơi khác như `ORDERS` với
> `GEOGRAPHY` ạ."*

**Làm sao biết `SALES` là thực thể suy diễn?**
> *"Vì em tái tạo được nó chính xác tuyệt đối từ dữ liệu giao dịch, sai số bằng 0,00 trên toàn bộ 3.833
> ngày ạ. Nên nó không phải dữ liệu gốc độc lập."*

**Em dùng công cụ gì?**
> *"Em dùng Python với thư viện `pandas` để kiểm định dữ liệu, và draw.io để vẽ sơ đồ ạ. File nguồn
> `.drawio` em vẫn giữ trên repo để chỉnh sửa được."*

## Khi gặp câu không biết

Đừng bịa số. Nói thẳng:

> *"Điểm này em chưa kiểm tra ạ. Em có script kiểm định chạy lại được, em sẽ chạy và báo cáo thầy/cô
> sau."*

Câu này an toàn tuyệt đối vì bạn **có script thật** — nó biến điểm yếu thành điểm mạnh.

## Nếu được hỏi thêm về phân tích

Mở `eda-bieu-do-va-ket-luan.md`, chỉ trình bày **Hình 3**:

> *"Em có phân tích thêm hướng giá trị kinh doanh. Phát hiện đáng chú ý nhất là **lưu lượng truy cập
> website tăng 62,7% nhưng số đơn hàng lại giảm 53,1%** — tỷ lệ chuyển đổi sụp từ 1,17% xuống 0,33%.*
>
> *Nghĩa là marketing vẫn kéo được khách vào, vấn đề nằm ở khâu chuyển đổi. Kết luận này giúp doanh
> nghiệp không đổ thêm tiền quảng cáo sai chỗ ạ."*

---

# GIẤY NHỚ — SỐ LIỆU HAY BỊ HỎI

```
QUY MÔ
  14 tệp · 2.960.736 bản ghi · 96 trường
  Lịch sử: 04/07/2012 – 31/12/2022 (3.833 ngày, không thiếu ngày nào)
  Dự báo:  01/01/2023 – 01/07/2024 (548 ngày)

KIỂM ĐỊNH
  Toàn vẹn tham chiếu: 15 quan hệ · 4.815.470 bản ghi · 0 mồ côi
  Đối soát:            93 − 15 − 3 = 75 thuộc tính
  Biến mục tiêu:       sai số 0,00 trên 3.833/3.833 ngày

SƠ ĐỒ ERD
  13 thực thể · 75 thuộc tính · 15 quan hệ
  4 thực thể yếu · 1 thực thể suy diễn
  11 thuộc tính suy diễn · 8 thuộc tính khóa · 5 quan hệ định danh

PHÁT HIỆN CHÍNH
  signup_date sai:      73,8% đơn đặt trước ngày đăng ký
  order_items trùng:    16 cặp (order_id, product_id)
  SKU chưa từng bán:    814/2.412 (33,7%)
  Cảnh báo chất lượng:  17 mục
```
