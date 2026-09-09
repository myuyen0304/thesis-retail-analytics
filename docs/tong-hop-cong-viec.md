# Tổng hợp công việc đã làm

> Khóa luận: **Dự báo doanh thu và giá vốn hàng bán theo ngày** — bộ dữ liệu thương mại điện tử
> thời trang, 04/07/2012 → 31/12/2022.
> Nhánh `docs/duythong` · 39 commit · phần phụ trách: **Từ điển dữ liệu, ERD, EDA, Làm sạch,
> Phát biểu vấn đề**.

---

## Bốn giai đoạn đã hoàn thành

```
① Từ điển dữ liệu & ERD  →  ② EDA  →  ③ Làm sạch (Silver)  →  ④ Phát biểu vấn đề
   hiểu dữ liệu có gì       kể câu     dữ liệu đáng tin        chọn bài toán nghiên cứu
                            chuyện
```

Mỗi giai đoạn đều **sinh ra đầu vào cho giai đoạn sau**, không phải bốn việc rời rạc:
Từ điển tìm ra 17 cảnh báo → Làm sạch xử lý đúng 17 cảnh báo đó → Phát biểu vấn đề dùng cột
`first_order_date` mà bước làm sạch tạo ra.

---

## ① Từ điển dữ liệu và ERD

| Sản phẩm | Nội dung |
|---|---|
| [`data-dictionary.md`](data-dictionary.md) | 96 trường, 4 loại cột, **17 cảnh báo chất lượng** |
| [`erd.svg`](erd.svg) · [`erd.drawio`](erd.drawio) | ERD ký hiệu **Chen** (mức khái niệm), 13 thực thể · 15 quan hệ |
| [`erd.md`](erd.md) | Mô tả sơ đồ, 4 quy tắc thiết kế |
| [`giai-thich-erd-tieng-viet.md`](giai-thich-erd-tieng-viet.md) | Dịch toàn bộ bảng/thuộc tính + luồng nghiệp vụ |
| [`quy-trinh-kiem-dinh.md`](quy-trinh-kiem-dinh.md) | 9 bước kiểm định kèm mã chạy được |
| [`Dictionary-va-ERD.ipynb`](../Dictionary-va-ERD.ipynb) | 43 ô, đã chạy sẵn |

**Kết quả chính**

- 14 tệp · **2.960.736 dòng** · 96 cột · 3.833 ngày liên tục, không thiếu ngày nào
- Toàn vẹn tham chiếu: **15 quan hệ · 4.815.470 bản ghi · 0 bản ghi mồ côi**
- **Tìm ra công thức sinh biến mục tiêu**, sai số tuyệt đối **0,00 trên cả 3.833 ngày**:
  ```
  Revenue(d) = Σ(quantity × unit_price)
  COGS(d)    = Σ(quantity × products.cogs)
  ```
  Hệ quả: `Revenue` là **doanh thu gộp**, tính cả đơn hủy và đơn trả, không trừ giảm giá.
- Đối soát số thuộc tính: **93 − 15 khóa ngoại − 3 sao chép = 75** — khớp đúng 75 elip trên sơ đồ

**Ba lỗi mô hình hóa đã sửa sau khi rà lại:** `SALES` không đứng riêng lẻ · `SAMPLE_SUBMISSION`
không phải thực thể · `RETURNS`/`REVIEWS` nối vào `ORDER_ITEMS` chứ không phải `ORDERS`+`PRODUCTS`.

---

## ② EDA — câu chuyện dữ liệu

| Sản phẩm | Nội dung |
|---|---|
| [`eda-cau-chuyen-du-lieu.md`](eda-cau-chuyen-du-lieu.md) | Bản kể chuyện đầy đủ |
| [`eda-bieu-do-va-ket-luan.md`](eda-bieu-do-va-ket-luan.md) | Biểu đồ → số liệu → kết luận |
| [`hinh/`](hinh/) · [`scripts/ve_bieu_do.py`](../scripts/ve_bieu_do.py) | 12 biểu đồ, sinh lại được |

**Phát hiện chính**

- Doanh thu đỉnh **2016**, mất **44,4%** đến 2022; riêng 2019 giảm **38,56%** trong một năm
- **Nghịch lý:** lưu lượng truy cập **+62,7%** nhưng tỷ lệ chuyển đổi sụp **1,17% → 0,33%**
- Số đơn **−56,2%** (từ đỉnh) trong khi giá trị mỗi đơn **+50,7%** — giá bù không đủ
- Thất thoát: cứ 100 đồng ghi nhận thì **16,9 đồng** không về túi (hủy 9,23% · hoàn 3,11% ·
  giảm giá 4,56%)
- Tập trung cực đoan: **top 5% mã hàng → 58,8% doanh thu**; 814/2.412 mã chưa từng bán

**Đã tự phát hiện và sửa hai lỗi nghiêm trọng trong chính phần này:**

| Lỗi | Sửa |
|---|---|
| Đơn vị tiền sai **1000 lần** ở mọi con số (chia `1e6` nhưng ghi "tỷ") | Tính lại toàn bộ theo `tỷ đvtt` |
| Biểu đồ thất thoát **hỏng hoàn toàn** — chia `1e12` với trục 0–20 nên cột phẳng ở đáy | Đổi thang, vẽ lại |

---

## ③ Làm sạch dữ liệu — lớp Silver

| Sản phẩm | Nội dung |
|---|---|
| [`lam-sach-du-lieu.md`](lam-sach-du-lieu.md) | Tài liệu chỉ dẫn kèm căn cứ từng thao tác |
| [`Data-Cleaning.ipynb`](../Data-Cleaning.ipynb) | 33 ô, đã chạy sẵn |
| [`Data-Cleaning-Slides.pptx`](../Data-Cleaning-Slides.pptx) | 15 slide, có ghi chú thuyết trình |
| [`ban-do-show-ket-qua.md`](ban-do-show-ket-qua.md) | Bản đồ slide → ô notebook |

**Nguyên tắc:** mọi thao tác đều truy ngược được về một trong **17 cảnh báo** của bước Từ điển.
Không xóa cột nào vì cảm tính.

| Chỉ tiêu | Trước | Sau |
|---|---:|---:|
| Số cột | 96 | **84** (−12) |
| Số dòng | 2.960.736 | **2.960.736** (không mất dòng nào) |
| Bản ghi mồ côi | 0 | **0** |
| Sai số tái tạo biến mục tiêu | 0,00 | **0,00** |

Hai dòng cuối là **kiểm chứng an toàn** — chứng minh làm sạch không phá vỡ quan hệ bảng, cũng
không làm sai biến đang đi dự báo.

**Ba quyết định đáng nói:** không xóa dòng nào · `signup_date` **thay** chứ không xóa (73,8% đơn
đặt trước ngày đăng ký) · 814 SKU chết **đánh dấu** chứ không xóa (xóa sẽ tạo bản ghi mồ côi
trong `inventory`).

---

## ④ Phát biểu vấn đề

Hai hướng đã dựng đầy đủ, chọn một làm bài toán lớn của khóa luận.

### D2 — Xói mòn nền khách hàng *(hướng chính)*

| Sản phẩm | Nội dung |
|---|---|
| [`problem-statement-customer-retention.md`](problem-statement-customer-retention.md) | Tài liệu chính, ~950 dòng |
| [`D2-Demo.ipynb`](../D2-Demo.ipynb) · [`D2-Demo.html`](../D2-Demo.html) | Demo 39 ô, đã chạy, 0 lỗi |
| [`hinh/12-kaplan-meier-promo.png`](hinh/12-kaplan-meier-promo.png) | Đường Kaplan–Meier |
| 4 script trong [`scripts/`](../scripts/) | Kiểm chứng · Cox PH · nghiệm thu · vẽ biểu đồ |

**Cấu trúc:** bài toán lớn rã thành **6 bài toán nhỏ** (BTN1–BTN6), mỗi cái có khoảng trống và
đầu ra riêng; 7 câu hỏi nghiên cứu theo 4 cấp; 9 giả thuyết có ghi trạng thái; 13 measure →
13 metric → 7 KPI, nối bằng ma trận truy vết.

**Bốn phát hiện**

1. Mất đơn do **hai sự cố đồng thời**: ít khách (72,2%) và mua thưa (45,2%)
2. Là thất bại **kích hoạt**, không phải thu nạp — đăng ký mới tăng **đơn điệu gấp 22 lần**
3. Rổ khách cạn chỉ giải thích **26,9%**; tín hiệu thật chiếm **73,1%**
4. ⭐ Tín hiệu thô nói khuyến mãi làm giảm **39,2%** giá trị khách; sau khi kiểm soát cohort chỉ
   còn **5,2%**

> Phát hiện thứ tư là đóng góp mới: nếu dừng ở phân tích mô tả, kết luận sẽ là *"cắt ngân sách
> khuyến mãi ngay"* — **một quyết định sai**, do nhầm tương quan với nhân quả.

**Phương pháp dùng:** Cox proportional hazards · Kaplan–Meier + log-rank · Schoenfeld residuals ·
propensity score matching · ANOVA · phân rã logarit.

### D3 — Bất ổn biên lợi nhuận *(hướng dự phòng)*

[`problem-statement-margin-volatility.md`](problem-statement-margin-volatility.md)

Biên lợi nhuận dao động theo **chu kỳ hai năm** không sai nhịp suốt 5 chu kỳ (năm lẻ ~11%, năm
chẵn ~16%). Truy ra: toàn bộ dao động nằm trong **tháng 8 của năm lẻ** — chỉ **4,59% số dòng
hàng** nhưng giải thích **51%** toàn bộ biến động biên 10 năm.

Cảnh báo cho chương dự báo: giai đoạn test chứa **đúng một** tháng 8 năm lẻ (08/2023).

---

## Cách kiểm chứng số liệu

Nguyên tắc xuyên suốt: **kiểm chứng phải đi bằng đường khác**. Tính bằng script A rồi chạy lại
script A không chứng minh gì.

| Phép kiểm | Kết quả |
|---|---|
| Ba nhóm khách cộng lại bằng tổng đăng ký | 121.930 — khớp |
| Phân rã logarit: rổ cạn + tỷ lệ hút = tổng | sai số **4,4×10⁻¹⁶** |
| **Hai đường phân rã độc lập gặp nhau** (phễu vs vòng đời) | cùng ra **−0,348**, sai số **1,7×10⁻¹⁶** |
| `sales.csv` vs `Σ(quantity × unit_price)` | tỷ lệ **1,000000** trên 3.833 ngày |
| `payment_value` = gross − discount | khớp **100%** trên 646.945 đơn |
| Nghiệm thu bộ chỉ số D2 | **8/8** dòng `OK` |

---

## Toàn bộ sản phẩm

| Loại | Số lượng |
|---|---:|
| Tài liệu Markdown | 12 |
| Notebook đã chạy sẵn | 3 |
| Script Python tái lập | 8 |
| Biểu đồ | 12 |
| Slide thuyết trình | 1 bộ (15 slide) |
| Bản PDF | 10 |
| Commit | 39 |

Mọi con số trong tài liệu đều sinh từ script chạy trên `data/` gốc — **không con số nào gõ tay**.

---

## Việc chưa xong

| | Cần gì | Làm được không |
|---|---|---|
| **BTN5** Nền khách đỡ nổi 2023–24? | Kiểm định điểm gãy (Chow test / Bai–Perron) | ✅ Làm được với dữ liệu hiện có |
| **BTN6** Ngân sách nên đi đâu? | Bảng chi phí marketing | ❌ **Bộ dữ liệu không có** |
| **H4** Bước gãy 2019 là hệ quả trễ? | Mô phỏng doanh thu từ cohort | ✅ Làm được |

Ba việc này đã ghi rõ lý do trong tài liệu — BTN6 là **giới hạn dữ liệu**, không phải thiếu công.

**Giai đoạn tiếp theo của khóa luận:** xây dựng đặc trưng (lớp Gold) và mô hình dự báo. Bốn cảnh
báo cần mang theo:

1. `Revenue` là doanh thu **gộp** — tính cả đơn hủy và đơn trả
2. Không dùng `signup_date` — đã thay bằng `first_order_date`
3. 11 cột suy diễn đã bị loại — đừng tính lại rồi đưa vào mô hình
4. Nối bảng `order_items` bằng `order_item_id`, không dùng cặp `(order_id, product_id)`
