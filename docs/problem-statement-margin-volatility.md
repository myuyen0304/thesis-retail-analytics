# Phát biểu vấn đề: Biên lợi nhuận dao động theo chu kỳ hai năm — truy về một cửa sổ 4,59%

> **Phát biểu vấn đề cho phần phân tích của khóa luận.**
>
> Tài liệu tham khảo *Retail Analytics & Forecasting* (VinDatathon 2026 Round 1 — cùng bộ dữ
> liệu) đề xuất 5 hướng: D1 Doanh thu, D2 Khách hàng, D3 Sản phẩm, D4 Marketing, D5 Vận hành.
> Tài liệu này chọn **D3 — Sản phẩm & Cơ cấu giá vốn**.
>
> **Mọi con số đều tự tính từ dữ liệu gốc.** Script tái lập nêu ở Mục 10.

---

## 1. Vì sao chọn vấn đề này

**Khóa luận dự báo hai biến: `Revenue` và `COGS`.** Gần như toàn bộ sự chú ý — của tài liệu
tham khảo lẫn của các phân tích trước — đổ vào `Revenue`. Nhưng `COGS` chiếm **một nửa hàm
mục tiêu**, và thứ nối hai biến lại với nhau là **biên lợi nhuận**.

Nếu biên ổn định, bài toán rất dễ: dự báo `Revenue` rồi nhân với một tỷ số cố định là ra
`COGS`. Tài liệu tham khảo có nhắc tới hướng này rồi **bác bỏ** nó, với lý do *"Q3 năm lẻ có
margin > 1,0 vi phạm giả định margin ổn định"* — nhưng chỉ dừng ở mức mô tả hiện tượng,
**không truy tiếp xem hiện tượng đó từ đâu ra và lớn cỡ nào**.

Đó chính là khoảng trống tài liệu này lấp: **định vị chính xác nguồn gốc của bất ổn biên lợi
nhuận, và lượng hóa nó**. Đây không phải câu hỏi phụ — nó quyết định **cách xây nửa sau của
mô hình dự báo**.

---

## 2. Quan sát khởi đầu: biên lợi nhuận nhấp nhô rất đều

Biên lợi nhuận gộp theo năm, tính trực tiếp từ `order_items ⋈ products`:

| Năm | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Biên (%)** | 11,54 | **15,88** | 11,88 | **15,40** | 11,34 | **16,64** | 11,58 | **15,97** | 9,77 | **12,77** |
| Năm | lẻ | chẵn | lẻ | chẵn | lẻ | chẵn | lẻ | chẵn | lẻ | chẵn |

Đây **không phải nhiễu ngẫu nhiên**. Năm lẻ luôn quanh **11%**, năm chẵn luôn quanh **16%** —
lặp lại đủ 5 chu kỳ, không sai nhịp lần nào. Biên độ dao động **6,87 điểm phần trăm**, độ lệch
chuẩn **2,45 đpt**.

Một dao động đều đặn như vậy **bắt buộc phải có nguyên nhân cấu trúc**, không thể là ngẫu nhiên.

---

## 3. Phát biểu vấn đề (Problem Statement)

**Bối cảnh.** Biên lợi nhuận gộp toàn hệ thống là **13,80%**, nhưng dao động từ **9,77% đến
16,64%** theo một chu kỳ hai năm hoàn hảo. Truy theo quý cho thấy dao động **không trải đều**:

| Quý | COGS/Revenue năm lẻ | COGS/Revenue năm chẵn | Chênh |
|---|---:|---:|---:|
| Q1 | 0,832 | 0,835 | −0,003 |
| Q2 | 0,827 | 0,831 | −0,004 |
| **Q3** | **1,040** | **0,859** | **+0,180** |
| Q4 | 0,884 | 0,879 | +0,005 |

**Ba quý còn lại gần như không lệch.** Toàn bộ dao động nằm ở **Q3**, và truy sâu hơn nữa thì
nằm gọn trong **tháng 8**: tỷ số COGS/Revenue tháng 8 năm lẻ là **1,340** so với **0,799** năm
chẵn.

**Vấn đề.** Trong tháng 8 của các năm lẻ:

- Giá bán trung bình rơi xuống **3.414 đvtt**, so với **5.764** ở tháng 8 năm chẵn — **thấp hơn 41%**
- Giá vốn trung bình **gần như không đổi**: 4.568 so với 4.607
- Hệ quả: **57,21% số dòng hàng bán dưới giá vốn**, so với **0,38%** ở tháng 8 năm chẵn

Cửa sổ này chỉ chiếm **3,06% doanh thu** và **4,59% số dòng hàng** của toàn bộ 11 năm. Nhưng
loại nó ra thì **độ lệch chuẩn của biên theo năm giảm từ 2,45 xuống 1,20 đpt — mất 51%**, và
biên độ dao động thu từ 6,87 xuống 3,88 đpt.

> **Nói gọn: 4,59% số dòng hàng giải thích quá nửa toàn bộ biến động biên lợi nhuận trong 10 năm.**

**Chưa xác định được** đây là (a) chiến dịch xả hàng tồn định kỳ hai năm một lần, (b) lỗi trong
bộ sinh dữ liệu mô phỏng, hay (c) một cơ chế kinh doanh khác. Ba khả năng này dẫn tới ba cách
xử lý khác nhau khi xây mô hình.

**Mục tiêu.** Định vị và lượng hóa nguồn gốc bất ổn của biên lợi nhuận; xác định xem bất ổn đó
đến từ **dịch chuyển cơ cấu danh mục** hay từ **hành vi định giá bên trong từng danh mục**; rút
ra cách xây nửa `COGS` của mô hình dự báo.

**Phạm vi.** `order_items`, `orders`, `products`, `promotions` — 2012-07-04 → 2022-12-31.
Biên tính ở cấp dòng hàng: `(quantity×unit_price − quantity×cogs) / (quantity×unit_price)`.

---

## 4. Câu hỏi nghiên cứu — theo 4 cấp phân tích

| Cấp | Câu hỏi |
|---|---|
| **Descriptive** | RQ1. Biên lợi nhuận biến động thế nào theo năm, quý, tháng và danh mục? |
| **Descriptive** | RQ2. Doanh thu tập trung vào bao nhiêu mã hàng, và bao nhiêu mã chưa từng bán? |
| **Diagnostic** | RQ3. Dao động biên đến từ **dịch chuyển cơ cấu danh mục** hay từ **định giá nội tại** trong từng danh mục? |
| **Diagnostic** | RQ4. Cửa sổ tháng 8 năm lẻ đóng góp bao nhiêu vào tổng biến động biên? |
| **Diagnostic** | RQ5. Cửa sổ đó có trùng với lịch khuyến mại đã ghi trong `promotions` không? |
| **Predictive** | RQ6. Chu kỳ hai năm có đủ ổn định để suy ra biên cho tháng 8/2023 không? |
| **Prescriptive** | RQ7. Nên dự báo `COGS` độc lập, qua tỷ số cố định, hay qua tỷ số **có điều kiện theo lịch**? |

---

## 5. Giả thuyết

Mỗi giả thuyết ghi rõ **trạng thái**: đã kiểm chứng, hay còn phải kiểm định.

| # | Giả thuyết | Cách kiểm định | Trạng thái |
|:--:|---|---|---|
| **H1** | Biên lợi nhuận dao động theo chu kỳ **hai năm**, không phải xu hướng đơn điệu | Đối chiếu biên năm lẻ với năm chẵn qua 5 chu kỳ | ✅ **Đúng** — lẻ ~11%, chẵn ~16%, không sai nhịp |
| **H2** | Dao động **tập trung ở một quý** chứ không trải đều 4 quý | So chênh lệch lẻ/chẵn của COGS/Rev từng quý | ✅ **Đúng** — Q3 lệch +0,180; ba quý kia ≈ 0 |
| **H3** | Nguyên nhân là **giá bán sụp**, không phải **giá vốn tăng** | So giá bán TB và giá vốn TB tháng 8 lẻ/chẵn | ✅ **Đúng** — giá bán −41%, giá vốn gần như không đổi |
| **H4** | Dao động do **định giá nội tại**, không do dịch chuyển cơ cấu danh mục | Phân rã Δbiên = Σ(Δw·b) + Σ(w·Δb) + tương tác | ✅ **Đúng** — nội tại +1,37 đpt (111%), cơ cấu −0,24 đpt |
| **H5** | Cửa sổ trùng với một chiến dịch khuyến mại chỉ chạy năm lẻ | Đối chiếu `promotions.start_date` với tháng 8 | ❌ **SAI** — chiến dịch tháng 8 chạy **cả 10 năm**, 5 lẻ 5 chẵn |
| **H6** | Danh mục giải thích được tỷ lệ trả hàng | So tỷ lệ trả theo 4 danh mục | ❌ **SAI** — dao động 3,26–3,52%, gần như phẳng |
| **H7** | Chu kỳ đủ ổn định để ngoại suy sang 2023–2024 | Kiểm tra tính nhất quán qua 5 chu kỳ đã có | ⏳ **Cần kiểm định** — xem Mục 9 |

> **H5 và H6 bị bác bỏ.** Đây không phải thất bại: xem Mục 8.

---

## 6. Measures — độ đo thô

Measure là **một phép tổng hợp trực tiếp trên một cột**. Tự nó chưa nói lên điều gì tốt hay xấu.

| # | Measure | Công thức | Bảng nguồn | Grain |
|:--:|---|---|---|---|
| M1 | Doanh thu dòng hàng | `quantity × unit_price` | order_items | Dòng hàng |
| M2 | Giá vốn dòng hàng | `quantity × products.cogs` | order_items ⋈ products | Dòng hàng |
| M3 | Giá giao dịch | `unit_price` | order_items | Dòng hàng |
| M4 | Giá niêm yết | `products.price` | products | Mỗi mã hàng |
| M5 | Giá vốn đơn vị | `products.cogs` | products | Mỗi mã hàng |
| M6 | Ngày đặt hàng | `orders.order_date` | orders | Mỗi đơn |
| M7 | Số lượng trả | `returns.return_quantity` | returns | Mỗi lượt trả |
| M8 | Cửa sổ khuyến mại | `promotions.start_date`, `end_date` | promotions | Mỗi chiến dịch |

---

## 7. Metrics — chỉ số dẫn xuất

Metric **kết hợp từ hai measure trở lên** và mang ngữ cảnh so sánh.

| # | Metric | Công thức | Giá trị đo được | Phục vụ |
|:--:|---|---|---|---|
| Me1 | Biên lợi nhuận gộp | `(M1−M2)/M1` | **13,80%** toàn hệ thống | RQ1 |
| Me2 | Tỷ số giá vốn | `M2/M1` | 0,799 → **1,340** (T8 chẵn→lẻ) | RQ1, RQ4 |
| Me3 | Độ lệch chuẩn biên theo năm | `std(Me1 theo năm)` | **2,45 đpt** | RQ1, RQ4 |
| Me4 | Chênh lệch biên lẻ/chẵn theo quý | `Me2(lẻ) − Me2(chẵn)` | Q3: **+0,180**; còn lại ≈0 | RQ1, H2 |
| Me5 | Tỷ lệ dòng bán dưới giá vốn | `#(M3 < M5) / #dòng` | **57,21%** trong cửa sổ | RQ4, H3 |
| Me6 | Tỷ lệ giá giao dịch/niêm yết | `M3/M4` | trung vị **0,9821** | RQ3, H3 |
| Me7 | Đóng góp cơ cấu vs nội tại | `Σ(Δw·b)` và `Σ(w·Δb)` | −0,24 đpt / **+1,37 đpt** | RQ3, H4 |
| Me8 | Tỷ trọng doanh thu theo danh mục | `M1 nhóm theo category / ΣM1` | Streetwear **79,92%** | RQ1, RQ3 |
| Me9 | Mức tập trung Pareto | `%doanh thu tích lũy theo top N% mã` | Top 5% → **58,8%** | RQ2 |
| Me10 | Tỷ lệ trả hàng | `ΣM7 / Σquantity` | **3,41%**, phẳng theo danh mục | RQ1, H6 |
| Me11 | Độ giảm biến động khi loại cửa sổ | `1 − Me3(bỏ cửa sổ)/Me3(đủ)` | **51%** | RQ4 |

---

## 8. KPI — chỉ số gắn mục tiêu và ngưỡng hành động

KPI là Metric **được chọn ra** vì gắn với mục tiêu, **có ngưỡng** và **có hành động khi lệch
ngưỡng**. Metric không có ngưỡng và hành động thì chỉ là số tham khảo.

| # | KPI | Công thức | Hiện tại | Ngưỡng đề xuất | Khi lệch ngưỡng → hành động |
|:--:|---|---|---:|---:|---|
| K1 | **Biên lợi nhuận gộp năm** | Me1 theo năm | 12,77% | ≥ 15% | Dưới ngưỡng → rà soát chính sách giá của kỳ xả hàng |
| K2 | **Ổn định biên** | Me3 | 2,45 đpt | ≤ 1,5 đpt | Vượt ngưỡng → biên không dự báo được bằng tỷ số cố định |
| K3 | **Tỷ lệ bán dưới giá vốn** | Me5 | 18,62% | ≤ 5% | Vượt ngưỡng → đặt giá sàn ràng buộc theo `cogs` |
| K4 | **Lệch biên lẻ/chẵn Q3** | Me4 tại Q3 | +0,180 | ≤ 0,05 | Vượt ngưỡng → tồn tại chu kỳ ẩn, mô hình phải có cờ lịch |
| K5 | **Rủi ro tập trung danh mục** | Me8 lớn nhất | 79,92% | ≤ 60% | Vượt ngưỡng → phụ thuộc một danh mục, cần đa dạng hóa |
| K6 | **Tỷ lệ mã hàng chết** | `#chưa bán / #mã` | 33,7% | ≤ 15% | Vượt ngưỡng → rà soát danh mục, ngừng nhập mã không quay vòng |

> **Về các ngưỡng.** Đặt theo vùng lịch sử quan sát được, không phải chuẩn ngành: K1 = 15% là
> mức các năm chẵn đạt được; K2 = 1,5 đpt là mức đạt được sau khi loại cửa sổ bất thường
> (1,20 đpt). Nhóm nên hiệu chỉnh sau khi thống nhất mục tiêu — **đừng trích dẫn như số cố định.**

---

## 8b. Ma trận truy vết — chuỗi thiết kế nối liền

Đọc theo hàng ngang: mỗi câu hỏi đều truy được xuống một KPI có hành động.

| Câu hỏi | Giả thuyết | Measure | Metric | KPI |
|---|---|---|---|---|
| RQ1 Biên biến động thế nào | H1, H2 | M1, M2, M6 | Me1, Me2, Me3, Me4 | K1, K2, K4 |
| RQ2 Tập trung sản phẩm | — | M1, M4 | Me9 | K6 |
| RQ3 Cơ cấu hay định giá | H4 | M1, M2, M3, M4 | Me6, Me7, Me8 | K5 |
| RQ4 Cửa sổ đóng góp bao nhiêu | H3 | M1, M2, M3, M5, M6 | Me5, Me11 | K3 |
| RQ5 Có trùng lịch khuyến mại | H5 | M6, M8 | Me2 | — *(bác bỏ)* |
| RQ6 Có ngoại suy được không | H7 | M1, M2, M6 | Me4 | K4 |
| RQ7 Dự báo COGS kiểu nào | H1, H4, H7 | M1, M2 | Me2, Me3, Me11 | K2, K4 |

**Ba điều bảng này cho thấy:**

1. **Không có Measure thừa** — cả 8 measure đều được ít nhất một câu hỏi dùng tới.
2. **Không có câu hỏi cụt** — mỗi RQ đều dẫn tới KPI, trừ RQ5 vốn kết luận *bác bỏ* nên đúng ra
   không được đẻ ra KPI nào.
3. **Hai giả thuyết bị bác bỏ (H5, H6) là kết quả có giá trị**, không phải thất bại:
   - **H5 sai** ngăn nhóm gán nhầm nguyên nhân cho lịch khuyến mại. Chiến dịch tháng 8 chạy
     **cả 10 năm** — nếu không kiểm tra, cả chương phân tích sẽ dựng trên một nhân quả sai.
   - **H6 sai** ngăn nhóm xây một KPI trả hàng theo danh mục mà dữ liệu không đỡ nổi
     (3,26–3,52%, chênh chưa tới 0,3 đpt).

> Một thiết kế phân tích tốt phải biết **dừng** khi bằng chứng không đủ. Đó là lý do mỗi giả
> thuyết ở Mục 5 đều phải ghi trạng thái, thay vì chỉ liệt kê những cái đúng.

---

## 9. Ý nghĩa cho bài toán dự báo Revenue/COGS

Đây là phần nối trực tiếp sang chương mô hình.

**Kết luận cốt lõi: `COGS` không dự báo được bằng tỷ số cố định, nhưng dự báo được bằng
tỷ số CÓ ĐIỀU KIỆN THEO LỊCH.**

Lý do: bất ổn của biên **không phải ngẫu nhiên**, mà tập trung vào một cửa sổ **hoàn toàn suy
được từ ngày tháng** — tháng 8 của năm lẻ. Đây đúng là loại đặc trưng sống sót qua chân trời dự
báo 18 tháng, vì nó không cần bất kỳ giá trị lịch sử nào (`lag`) để tính.

**Ba đặc trưng đề xuất, đều tính được từ `Date`:**

```python
is_odd_year      = (Date.year % 2 == 1)
is_august        = (Date.month == 8)
in_clearance_win = is_odd_year & is_august      # cua so bat thuong
```

**Cảnh báo quan trọng về giai đoạn test.** Giai đoạn dự báo là **01/01/2023 → 01/07/2024**:

| | 2023 | 2024 |
|---|---|---|
| Loại năm | **lẻ** | chẵn |
| Tháng 8 có trong test? | **Có** (01–31/08/2023) | Không (test kết thúc 01/07/2024) |

> Giai đoạn test chứa **đúng một** tháng 8 năm lẻ. Nếu mô hình bỏ qua cửa sổ này, `COGS` tháng
> 8/2023 sẽ bị dự báo thấp hơn thực tế rất nhiều — vì mô hình sẽ áp tỷ số ~0,86 trong khi giá
> trị thật quanh **1,34**. Riêng một tháng đó đủ để kéo hỏng điểm MAE của cả biến `COGS`.

Điều này cũng **giải thích cơ chế** cho khuyến nghị của tài liệu tham khảo (mô hình chuyên biệt
theo quý + cờ `is_odd_year`): không phải vì "Q3 khó", mà vì **tháng 8 năm lẻ là một chế độ định
giá khác hẳn**, và mô hình cần được phép biểu diễn nó tách rời.

---

## 10. Tái lập số liệu

| Script | Sinh ra |
|---|---|
| [`scripts/phan_tich_bien_ln.py`](../scripts/phan_tich_bien_ln.py) | Mục 2–3, 5, 7: biên theo năm/quý, cơ cấu danh mục, phân rã mix, Pareto, trả hàng |
| [`scripts/phan_tich_bien_ln2.py`](../scripts/phan_tich_bien_ln2.py) | Mục 3, 8: truy cơ chế tháng 8, đối chiếu lịch khuyến mại, tác động lên độ ổn định |

```bash
python scripts/phan_tich_bien_ln.py
```

Chạy từ thư mục gốc dự án, đọc trực tiếp `data/` (dữ liệu Bronze) để mọi con số đối chiếu được
với nguồn gốc.

**Lưu ý về đơn vị tiền:** dữ liệu là mô phỏng, đơn vị tiền tệ không xác định — ký hiệu *đvtt*.
Mọi giá trị tuyệt đối chỉ nên dùng để so sánh tương đối.

**Một quan sát cần thận trọng:** ngay ngoài cửa sổ bất thường, vẫn có **17,76%** số dòng hàng
bán dưới giá vốn. Tỷ lệ này cao bất thường với một doanh nghiệp thật, và củng cố khả năng đây
là đặc tính của **bộ sinh dữ liệu mô phỏng** chứ không phải hành vi kinh doanh có chủ đích. Khi
viết vào khóa luận nên nêu rõ giới hạn này thay vì diễn giải như một quyết định kinh doanh.
