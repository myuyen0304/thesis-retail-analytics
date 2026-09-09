# Làm sạch dữ liệu — Hướng dẫn và căn cứ

> Tài liệu đi kèm notebook [`Data-Cleaning.ipynb`](../Data-Cleaning.ipynb).
> Bước trước: [Từ điển dữ liệu và Sơ đồ ERD](../Dictionary-va-ERD.ipynb)

---

<!-- muc-luc -->
## Mục lục

- [1. Nguyên tắc](#1-nguyên-tắc)
- [2. Kết quả](#2-kết-quả)
- [3. Tám nhóm thao tác](#3-tám-nhóm-thao-tác)
- [4. Hai phép kiểm chứng an toàn](#4-hai-phép-kiểm-chứng-an-toàn)
- [5. Cách chạy lại](#5-cách-chạy-lại)
- [6. Ba quyết định đáng nói khi báo cáo](#6-ba-quyết-định-đáng-nói-khi-báo-cáo)
- [7. Bước tiếp theo](#7-bước-tiếp-theo)

---
<!-- muc-luc -->

## 1. Nguyên tắc

> **Mọi thao tác làm sạch đều phải có căn cứ từ bước Từ điển dữ liệu.**
> Không xóa cột nào vì cảm tính — mỗi lần xóa đều dẫn ra được con số đã kiểm chứng.

Bước Từ điển tìm ra **17 cảnh báo chất lượng dữ liệu**. Bước này xử lý từng cảnh báo đó, không thêm không
bớt.

### Ba ràng buộc tự đặt ra

| Ràng buộc | Lý do |
|---|---|
| **Không xóa dòng nào** | Dữ liệu bẩn ở đây là *cột thừa*, không phải *dòng lỗi* — xóa dòng là sai hướng |
| **Không sửa dữ liệu gốc** | Ghi ra `data_clean/`, giữ nguyên `data/` để còn đối chiếu |
| **Kiểm chứng lại sau khi làm sạch** | Toàn vẹn tham chiếu và biến mục tiêu phải không đổi |

---

## 2. Kết quả

| Chỉ tiêu | Trước | Sau |
|---|---:|---:|
| Số cột | 96 | **84** (−12) |
| Số dòng | 2.960.736 | **2.960.736** (không mất dòng nào) |
| Bản ghi mồ côi | 0 | **0** |
| Sai số tái tạo biến mục tiêu | 0,00 | **0,00** |

Hai dòng cuối là **kiểm chứng an toàn** — chứng minh việc làm sạch không phá vỡ quan hệ giữa các bảng,
cũng không làm sai biến mục tiêu.

### Thay đổi theo từng bảng

| Bảng | Cột trước | Cột sau | Chênh |
|---|---:|---:|---:|
| `inventory` | 17 | **7** | **−10** |
| `payments` | 4 | **2** | −2 |
| `orders` | 8 | 7 | −1 |
| `reviews` | 7 | 6 | −1 |
| `order_items` | 7 | **8** | **+1** |
| `products` | 8 | **9** | **+1** |
| `customers` | 7 | 7 | 0 |
| *(7 bảng còn lại)* | | | không đổi |

`inventory` bị cắt nhiều nhất — mất 10 cột: 6 cột suy diễn, 3 cột sao chép từ `products`, 1 cột hằng số.
Đúng như phát hiện ở bước Từ điển: quá nửa bảng không mang thông tin độc lập.

`order_items` và `products` **tăng** một cột vì được thêm khóa thay thế và cờ đánh dấu.

---

## 3. Tám nhóm thao tác

### Bước 1 — Ép kiểu ngày · 12 cột

**Vấn đề:** CSV lưu ngày dưới dạng chuỗi, không so sánh hay tính hiệu ngày được.

**Xử lý:** ép 12 cột về kiểu `datetime`.

### Bước 2 — Thêm khóa thay thế cho `order_items` ⭐

**Căn cứ:** **16 cặp `(order_id, product_id)` bị trùng** trên 714.669 dòng → bảng này không có khóa tự
nhiên hợp lệ.

**Hậu quả nếu bỏ qua:** nối bảng bằng cặp đó sẽ làm **nhân dòng**, doanh thu bị tính lố mà không báo lỗi.

**Xử lý:** thêm cột `order_item_id` chạy từ 1 đến 714.669.

### Bước 3 — Loại cột hằng số · 1 cột

**Căn cứ:** `inventory.reorder_flag` luôn bằng 0 trên toàn bộ 60.247 dòng → phương sai bằng 0.

Notebook **quét tự động** toàn bộ 96 cột thay vì liệt kê tay, để chắc không sót.

### Bước 4 — Loại cột dư thừa · 7 cột

Cột là bản sao nguyên văn của bảng khác, đã kiểm chứng trùng khớp **100%**.

| Cột bị loại | Suy ra từ |
|---|---|
| `orders.zip` | `customers.zip` qua `customer_id` |
| `payments.payment_method` | `orders.payment_method` qua `order_id` |
| `customers.city` | `geography.city` qua `zip` |
| `reviews.customer_id` | `orders.customer_id` qua `order_id` |
| `inventory.product_name` | `products` |
| `inventory.category` | `products` |
| `inventory.segment` | `products` |

### Bước 5 — Loại cột suy diễn · 7 cột ⭐

Cột tính lại được bằng công thức, đã xác nhận khớp **100%**.

| Cột bị loại | Công thức |
|---|---|
| `inventory.fill_rate` | `1 − stockout_days / 30` |
| `inventory.stockout_flag` | `stockout_days > 0` |
| `inventory.sell_through_rate` | `units_sold / (stock_on_hand + units_sold)` |
| `inventory.days_of_supply` | `round(stock_on_hand / (units_sold/30), 1)` |
| `inventory.year`, `inventory.month` | tách từ `snapshot_date` |
| `payments.payment_value` | `Σ(quantity × unit_price − discount_amount)` |

**Vì sao phải loại:** hai cột tương quan hoàn hảo gây **đa cộng tuyến** — trọng số mô hình bất ổn định
và biểu đồ tầm quan trọng đặc trưng cho kết quả sai lệch.

### Bước 6 — Xử lý giá trị thiếu **có ngữ nghĩa** · 3 thao tác

> Đây là chỗ dễ sai nhất. **Không phải giá trị thiếu nào cũng là lỗi.**

| Cột | Thiếu | Nghĩa thật | Xử lý |
|---|---:|---|---|
| `order_items.promo_id` | 61,3% | Dòng hàng không có khuyến mại | Thêm cờ `co_khuyen_mai`, **giữ nguyên** cột gốc |
| `order_items.promo_id_2` | 99,97% | Khuyến mại cộng dồn | **Loại bỏ** — chỉ 206 dòng có giá trị |
| `promotions.applicable_category` | 80% | **Áp dụng mọi danh mục** | Điền nhãn `ALL` — **tuyệt đối không xóa dòng** |

Trường hợp thứ ba đáng nhấn mạnh: nếu coi đó là lỗi rồi xóa 40 dòng, hoặc điền giá trị phổ biến nhất
vào, thì **sai hoàn toàn** — giá trị thiếu ở đây mang nghĩa rộng nhất chứ không phải hẹp nhất.

### Bước 7 — Thay `signup_date` bằng `first_order_date` ⭐

**Căn cứ:** **73,8% đơn hàng đặt TRƯỚC ngày đăng ký tài khoản** — bất khả thi về nghiệp vụ.

**Vì sao không xóa hẳn:** bỏ đi thì mất thông tin về khách hàng.

**Xử lý:** thay bằng `first_order_date` — ngày đặt hàng đầu tiên, tính trực tiếp từ bảng `orders`. Chỉ số
này nhất quán về thời gian, dùng được ngay cho đặc trưng thâm niên khách hàng. Thêm cờ `da_tung_mua`
(0/1) để phân biệt khách đã giao dịch với khách chỉ đăng ký.

### Bước 8 — Đánh dấu SKU chết · không xóa

**Căn cứ:** 814 trên 2.412 sản phẩm chưa từng phát sinh giao dịch, trong đó 654 có giá bất thường dưới
100 — làm lệch mọi thống kê về giá và biên lợi nhuận.

**Vì sao không xóa:** chúng vẫn được bảng `inventory` tham chiếu. Xóa đi sẽ **tạo ra bản ghi mồ côi**.

**Xử lý:** thêm cờ `da_tung_ban` (0/1). Khi tính thống kê giá thì lọc bằng cờ này.

---

## 4. Hai phép kiểm chứng an toàn

> Làm sạch xong phải chứng minh **không phá vỡ gì**. Hai phép kiểm này là bắt buộc.

### Kiểm chứng 1 — Toàn vẹn tham chiếu

Chạy lại phép đếm bản ghi mồ côi trên 12 quan hệ khóa ngoại còn lại sau khi làm sạch.

**Kết quả:** 4.054.768 bản ghi, **0 mồ côi**. Không quan hệ nào bị phá vỡ.

*(Con số nhỏ hơn 4.815.470 ở bước Từ điển vì đã loại 3 cột khóa ngoại dư thừa.)*

### Kiểm chứng 2 — Biến mục tiêu

Dựng lại `sales.csv` từ dữ liệu **đã làm sạch**, so với bản gốc.

**Kết quả:** sai số tuyệt đối vẫn bằng **0,00 trên cả 3.833 ngày**. Việc làm sạch không làm sai lệch biến
mục tiêu.

---

## 5. Cách chạy lại

Notebook đã chạy sẵn, mở ra là thấy đủ kết quả. Nếu muốn chạy lại:

```bash
cd /d D:\datathon-2026-round-1
jupyter notebook
```

Mở `Data-Cleaning.ipynb` → **Kernel → Restart & Run All**.

Cần có thư mục `data/` chứa 14 tệp CSV gốc. Kết quả ghi ra `data_clean/`.

### Sản phẩm sinh ra

| Đường dẫn | Nội dung |
|---|---|
| `data_clean/*.csv` | 14 tệp đã làm sạch, 84 cột |
| `data_clean/_nhat_ky_lam_sach.csv` | Nhật ký 22 thao tác kèm căn cứ từng thao tác |

Thư mục `data_clean/` **không đẩy lên git** (111 MB, là dữ liệu dẫn xuất) — chạy lại notebook là có.

---

## 6. Ba quyết định đáng nói khi báo cáo

**Không xóa dòng nào.** Toàn bộ thao tác đều ở mức cột. Dữ liệu bẩn ở đây là *cột thừa* chứ không phải
*dòng lỗi*, nên xóa dòng là sai hướng và làm mất dữ liệu vô ích.

**`signup_date` thay chứ không xóa.** Bỏ hẳn thì mất thông tin về khách hàng. Thay bằng chỉ số tương
đương suy từ dữ liệu đáng tin hơn là cách xử lý giữ được giá trị phân tích.

**SKU chết đánh dấu chứ không xóa.** Xóa sẽ tạo bản ghi mồ côi trong `inventory` — tức là sửa một lỗi
lại tạo ra lỗi khác nghiêm trọng hơn.

---

## 7. Bước tiếp theo

Xây dựng đặc trưng (feature engineering) trên bộ dữ liệu đã làm sạch. Bốn cảnh báo cần nhớ:

1. **`Revenue` là doanh thu gộp**, tính cả đơn hủy và đơn trả — sai định nghĩa là sai target hoàn toàn
2. **Không dùng `signup_date`** — đã thay bằng `first_order_date`
3. **11 cột suy diễn đã bị loại** — đừng tính lại rồi đưa vào mô hình
4. **Dùng `order_item_id`** khi nối bảng `order_items`, không dùng cặp `(order_id, product_id)`
