# Phát biểu vấn đề: Sụp đổ giữ chân khách hàng — động cơ thật sau đà giảm doanh thu

> **Phát biểu vấn đề cho phần phân tích của khóa luận.**
>
> Tài liệu tham khảo *Retail Analytics & Forecasting* (VinDatathon 2026 Round 1 — cùng bộ dữ
> liệu) đề xuất 5 hướng phân tích: D1 Doanh thu, D2 Khách hàng, D3 Sản phẩm, D4 Marketing,
> D5 Vận hành. Tài liệu này chọn **D2 — Khách hàng**.
>
> **Mọi con số dưới đây đều tự tính từ dữ liệu gốc**, không trích lại từ tài liệu tham khảo.
> Script tái lập nêu ở Mục 11.

---

## 1. Vì sao chọn vấn đề này

Tài liệu tham khảo đề xuất 5 hướng (D1 Doanh thu, D2 Khách hàng, D3 Sản phẩm, D4 Marketing,
D5 Vận hành). Chọn D2 vì ba lý do:

**Thứ nhất — nó nằm ngay sau chỗ phân tích doanh thu dừng lại.** Bước EDA của khóa luận
(xem [`eda-cau-chuyen-du-lieu.md`](eda-cau-chuyen-du-lieu.md)) đã xác định: doanh thu mất
**50,5%** từ đỉnh 2016, và mức giảm đến từ **số đơn** chứ không phải giá trị mỗi đơn — số đơn
sụp trong khi AOV còn tăng **+50,7%**. Nhưng **số đơn là kết quả, không phải nguyên nhân**.
Đơn hàng do khách hàng tạo ra, nên câu hỏi kế tiếp bắt buộc phải là: *ít đơn hơn vì ít khách
hơn, hay vì mỗi khách mua thưa hơn?* Không trả lời được câu này thì mọi đề xuất hành động
đều là đoán.

**Thứ hai — bước làm sạch đã mở đường cho phân tích này.** Cột `signup_date` gốc có **73,8%
đơn đặt trước ngày đăng ký** nên không dùng được để tính thâm niên hay cohort. Bước làm sạch
đã thay bằng `first_order_date` suy từ bảng `orders`. Không có thao tác đó thì toàn bộ phân tích
cohort dưới đây **không thực hiện được**. Đây là ví dụ trực tiếp cho thấy lớp Silver phục vụ
việc gì.

**Thứ ba — nó giải thích được cấu trúc chế độ (regime) mà mô hình dự báo phải xử lý.** Xem
Mục 9.

---

## 2. Trục phân tích: chuỗi phân rã ba tầng

Đây là xương sống của toàn bộ vấn đề. Mỗi tầng bóc một lớp nguyên nhân:

```
Doanh thu
  = Số đơn                     × Giá trị mỗi đơn (AOV)
  = (Khách hoạt động × Tần suất) × AOV
  = ((Khách mới + Khách giữ lại) × Tần suất) × AOV
```

Kết quả đo được ở từng tầng, giai đoạn **2013 → 2022**:

| Tầng | Thành phần | Thay đổi | Ghi chú |
|---|---|---:|---|
| 1 | Số đơn | **−53,1%** | 76.849 → 36.004 |
| 1 | AOV | **+50,7%** | Bù đắp một phần, không đủ |
| 2 | Khách hoạt động | **−37,3%** | 39.384 → 24.696 |
| 2 | Tần suất mua/năm | **−25,3%** | 1,95 → 1,46 đơn |
| 3 | Khách mới thu nạp | **−94,7%** | 25.099 → 1.322 |
| 3 | Giữ chân năm +1 | **50,8% → 6,7%** | Cohort 2013 so với cohort 2021 |

**Phân rã định lượng mức giảm 40.845 đơn:**

| Nguồn | Đóng góp | Tỷ trọng |
|---|---:|---:|
| Do giảm **số khách hoạt động** | −28.660 đơn | **70,2%** |
| Do giảm **tần suất mua** | −19.432 đơn | **47,6%** |
| Số hạng tương tác | +7.247 đơn | −17,7% |
| **Tổng** | **−40.845 đơn** | 100% |

> Đọc bảng này: mất khách là nguyên nhân **chính** (70,2%), nhưng mất tần suất cũng gần một
> nửa (47,6%). Đây **không phải** một vấn đề đơn lẻ mà là **hai sự cố xảy ra đồng thời** —
> và chúng nhân lên nhau. Số hạng tương tác dương vì hai mức giảm chồng lấn, tránh đếm trùng.

---

## 3. Phát biểu vấn đề (Problem Statement)

**Bối cảnh.** Trên 121.930 tài khoản đăng ký, chỉ 90.246 (74,0%) từng phát sinh giao dịch.
Trong nhóm đã mua, 24,8% chỉ mua **đúng một lần** rồi biến mất. Tính đến 31/12/2022, có
**97.177 tài khoản — 79,7% toàn bộ tập đăng ký — hoặc chưa từng mua, hoặc không giao dịch
quá một năm.**

**Vấn đề.** Doanh nghiệp đang chịu **hai thất bại chồng nhau**:

1. **Thất bại thu nạp** — lượng khách mới mỗi năm giảm **−94,7%** (25.099 → 1.322). Phễu đầu
   vào gần như đã tắt.
2. **Thất bại giữ chân** — chất lượng cohort suy giảm đơn điệu qua từng năm: doanh thu 3 năm
   đầu trên mỗi khách rơi từ **81.902 xuống 36.064 đvtt (−56,0%)**, tỷ lệ quay lại năm +1 rơi
   từ **50,8% xuống 6,7%**.

Hai thất bại này **nhân lên nhau**: ít khách mới hơn, mà mỗi khách mới lại kém giá trị hơn.
Hệ quả là tỷ trọng doanh thu đến từ khách mới sụp từ **53,0% (2013) xuống 3,7% (2022)** —
doanh nghiệp hiện gần như **hoàn toàn sống nhờ nền khách cũ**.

**Chưa xác định được** đây là (a) thị trường bão hòa nên hết khách để thu nạp, (b) ngân sách
marketing bị cắt nên ngừng thu nạp, hay (c) sản phẩm/trải nghiệm xuống cấp nên khách không
quay lại. Ba nguyên nhân này đòi hỏi ba hành động hoàn toàn khác nhau.

**Mục tiêu.** Phân tách đóng góp của thu nạp và giữ chân vào đà giảm; xác định thời điểm và
cơ chế của bước gãy 2019; đánh giá nền khách cũ hiện tại có đủ ổn định để đỡ doanh thu
2023–2024 hay không.

**Phạm vi.** `customers`, `orders`, `order_items` — 2012-07-04 → 2022-12-31. Dùng
`first_order_date` (từ lớp Silver) làm mốc cohort, **không dùng** `signup_date`.

---

## 4. Câu hỏi nghiên cứu — theo 4 cấp phân tích

| Cấp | Câu hỏi |
|---|---|
| **Descriptive** | RQ1. Cấu trúc tập khách hàng hiện tại ra sao: bao nhiêu đang hoạt động, ngủ đông, chưa từng mua? |
| **Descriptive** | RQ2. Lượng khách mới thu nạp và tỷ lệ giữ chân đã thay đổi thế nào qua 10 năm? |
| **Diagnostic** | RQ3. Trong mức giảm 53,1% số đơn, bao nhiêu do **mất khách** và bao nhiêu do **giảm tần suất**? |
| **Diagnostic** | RQ4. Chất lượng cohort suy giảm **đều đặn** theo thời gian, hay **gãy đột ngột** tại một mốc? |
| **Diagnostic** | RQ5. Kênh thu nạp có tạo ra khác biệt về giá trị khách hàng không? |
| **Predictive** | RQ6. Nền khách cũ hiện tại có đủ ổn định để giữ doanh thu 2023–2024 đi ngang, hay sẽ tiếp tục xói mòn? |
| **Prescriptive** | RQ7. Với ngân sách giới hạn, nên ưu tiên **kích hoạt 31.684 khách chưa từng mua**, **giành lại nhóm ngủ đông**, hay **thu nạp khách mới**? |

---

## 5. Giả thuyết

Mỗi giả thuyết ghi rõ **trạng thái**: đã kiểm chứng bằng dữ liệu, hay còn phải kiểm định.

| # | Giả thuyết | Cách kiểm định | Trạng thái |
|:--:|---|---|---|
| **H1** | Mất khách hoạt động đóng góp lớn hơn giảm tần suất vào đà giảm đơn | Phân rã ΔĐơn = ΔKhách×Tần suất + Khách×ΔTần suất + tương tác | ✅ **Đúng** — 70,2% so với 47,6% |
| **H2** | Suy giảm thu nạp khách mới nghiêm trọng hơn suy giảm giữ chân | So %Δkhách mới với %Δretention năm +1 | ✅ **Đúng** — −94,7% so với −86,8% điểm tương đối, thu nạp nặng hơn |
| **H3** | Chất lượng cohort suy giảm **đơn điệu**, không phải gãy một lần tại 2019 | Hồi quy giá trị 3 năm đầu theo năm cohort; kiểm tra tính đơn điệu | ✅ **Đúng** — giảm liên tục 2013→2019, không có bước nhảy riêng ở 2019 |
| **H4** | Bước gãy 2019 ở doanh thu là **hệ quả trễ** của suy giảm cohort tích lũy, không phải cú sốc độc lập | Mô phỏng doanh thu từ cohort: nếu tái tạo được bước gãy 2019 mà không cần biến sốc ngoại sinh thì H4 đúng | ⏳ **Cần kiểm định** |
| **H5** | Kênh thu nạp **không** phân hóa giá trị khách hàng | So LTV trung bình giữa 6 kênh; ANOVA | ✅ **Đúng** — chênh lệch chỉ **2,9%** giữa kênh cao nhất và thấp nhất |
| **H6** | Giai đoạn 2020–2022 là **chế độ ổn định** do nền khách cũ đỡ, không phải đoạn giữa của đà rơi tiếp | Kiểm định xu hướng số khách hoạt động 2020–2022 | ✅ **Đúng** — 24.335 → 23.984 → 24.696, đi ngang, 2022 nhích lên |

> **H5 mâu thuẫn với tài liệu tham khảo.** Xem Mục 8.

---

## 6. Measures — độ đo thô

Measure là **một phép tổng hợp trực tiếp trên một cột**. Tự nó chưa nói lên điều gì tốt hay xấu.

| # | Measure | Công thức | Bảng nguồn | Grain |
|:--:|---|---|---|---|
| M1 | Số khách đăng ký | `COUNT(customer_id)` | customers | Toàn tập |
| M2 | Số khách có giao dịch | `COUNTD(orders.customer_id)` | orders | Toàn tập / năm |
| M3 | Số đơn hàng | `COUNT(order_id)` | orders | Ngày / năm |
| M4 | Doanh thu | `SUM(quantity × unit_price)` | order_items | Ngày / năm |
| M5 | Ngày mua đầu tiên | `MIN(order_date)` theo khách | orders | Mỗi khách |
| M6 | Ngày mua gần nhất | `MAX(order_date)` theo khách | orders | Mỗi khách |
| M7 | Số đơn trọn đời | `COUNT(order_id)` theo khách | orders | Mỗi khách |
| M8 | Doanh thu trọn đời | `SUM(rev)` theo khách | orders ⋈ order_items | Mỗi khách |

---

## 7. Metrics — chỉ số dẫn xuất

Metric **kết hợp từ hai measure trở lên** và mang ngữ cảnh so sánh. Bắt đầu trả lời được câu
hỏi phân tích, nhưng chưa gắn mục tiêu kinh doanh.

| # | Metric | Công thức | Giá trị đo được | Phục vụ |
|:--:|---|---|---|---|
| Me1 | Tỷ lệ kích hoạt | `M2 / M1` | **74,0%** | RQ1 |
| Me2 | Tỷ lệ mua lại | `#khách có M7 ≥ 2 / M2` | **75,2%** | RQ1 |
| Me3 | Tần suất mua/năm | `M3(năm) / M2(năm)` | 1,95 → **1,46** | RQ3, H1 |
| Me4 | Khách mới mỗi năm | `COUNT(khách có year(M5) = Y)` | 25.099 → **1.322** | RQ2, H2 |
| Me5 | Giữ chân năm +N | `khách cohort C mua ở năm C+N / kích thước cohort C` | 50,8% → **6,7%** | RQ2, H3 |
| Me6 | Giá trị cohort 3 năm | `SUM(rev 3 năm đầu) / kích thước cohort` | 81.902 → **36.064** | RQ4, H3 |
| Me7 | Tỷ trọng doanh thu khách mới | `rev khách mới / tổng rev` | 53,0% → **3,7%** | RQ6 |
| Me8 | Tỷ lệ ngủ đông | `khách có recency > 365 ngày / M1` | **79,7%** | RQ1, RQ7 |
| Me9 | LTV theo kênh | `AVG(M8)` nhóm theo `acquisition_channel` | 178.674–183.767 | RQ5, H5 |
| Me10 | Đóng góp khách vs tần suất | `ΔKhách×Tần suất₀` và `Khách₀×ΔTần suất` | 70,2% / 47,6% | RQ3, H1 |

---

## 8. KPI — chỉ số gắn mục tiêu và ngưỡng hành động

KPI là Metric **được chọn ra** vì gắn với một mục tiêu chiến lược, **có ngưỡng cảnh báo** và
**có hành động rõ ràng khi lệch ngưỡng**. Metric không có ngưỡng và hành động thì chỉ dừng ở
mức tham khảo, không phải KPI.

| # | KPI | Công thức | Hiện tại | Ngưỡng đề xuất | Khi lệch ngưỡng → hành động |
|:--:|---|---|---:|---:|---|
| K1 | **Giữ chân năm +1** | Me5 với N=1 | 6,7% | ≥ 20% | Dưới ngưỡng → triển khai chuỗi nuôi dưỡng sau đơn đầu tiên |
| K2 | **Tăng trưởng khách mới** | `Me4(Y)/Me4(Y−1) − 1` | −1,3% | ≥ 0% | Âm 2 năm liên tiếp → xem lại toàn bộ ngân sách thu nạp |
| K3 | **Tỷ lệ ngủ đông** | Me8 | 79,7% | ≤ 60% | Vượt ngưỡng → chiến dịch giành lại nhóm recency 1–2 năm |
| K4 | **Tỷ lệ chuyển đổi lần đầu** | Me1 | 74,0% | ≥ 80% | Dưới ngưỡng → chuỗi email kích hoạt cho 31.684 tài khoản chưa mua |
| K5 | **Giá trị cohort 3 năm** | Me6 | 36.064 | Không giảm YoY | Giảm 2 cohort liên tiếp → chất lượng khách đang xuống, kiểm tra nguồn thu nạp |
| K6 | **Độ phụ thuộc khách cũ** | `1 − Me7` | 96,3% | ≤ 85% | Vượt ngưỡng → rủi ro tập trung, doanh thu phụ thuộc một nền khách đang già đi |

> **Về các ngưỡng.** Chúng được đặt theo vùng lịch sử đã quan sát chứ không phải chuẩn ngành:
> K1 = 20% là mức trung bình retention năm +1 của toàn bộ cohort 2013–2021 đo được; K6 = 85%
> tương ứng thời điểm 2014 khi cơ cấu còn lành mạnh. Nhóm nên hiệu chỉnh lại sau khi thống nhất
> mục tiêu kinh doanh — **đừng trích dẫn như số cố định.**

---

## 9. Một phát hiện đi ngược tài liệu tham khảo

Tài liệu tham khảo (Mục X.2.4 và X.3.4) đề xuất **tái phân bổ ngân sách theo kênh**, với lập
luận rằng các kênh mang về khách có LTV khác nhau.

Kiểm chứng lại trên dữ liệu gốc thì **không thấy khác biệt đó**:

| Kênh thu nạp | Số khách | % | LTV trung bình |
|---|---:|---:|---:|
| organic_search | 26.950 | 29,9% | 183.212 |
| social_media | 18.002 | 19,9% | 183.767 |
| paid_search | 17.999 | 19,9% | 181.772 |
| email_campaign | 10.886 | 12,1% | 180.701 |
| referral | 9.072 | 10,1% | 180.222 |
| direct | 7.337 | 8,1% | 178.674 |

Chênh lệch giữa kênh cao nhất và thấp nhất chỉ **2,9%** — nhỏ hơn nhiều so với sai số lấy mẫu ở
các kênh nhỏ. **`acquisition_channel` gần như độc lập với giá trị khách hàng.**

Hai cách giải thích, cần phân biệt trước khi kết luận:
1. Doanh nghiệp thật sự có các kênh không phân hóa về chất lượng khách.
2. Trường này được gán ngẫu nhiên trong bộ sinh dữ liệu mô phỏng — nhiều khả năng hơn.

Dù theo cách nào, **kết luận thực hành là như nhau: không thể biện minh cho đề xuất tái phân bổ
ngân sách theo kênh dựa trên bộ dữ liệu này.** Đây là ví dụ cho thấy vì sao phải tự kiểm chứng
lại số của tài liệu tham khảo thay vì trích lại.

---

## 10. Ý nghĩa cho bài toán dự báo Revenue/COGS

Đây là phần nối trực tiếp sang chương mô hình của khóa luận.

**Cấu trúc khách hàng giải thích được vì sao tồn tại các chế độ (regime).** Tài liệu tham khảo
mô tả ba chế độ tách biệt và kê đơn *sample weighting + calibration*, nhưng chỉ mô tả hiện
tượng chứ không giải thích cơ chế. Phân tích cohort cho thấy cơ chế đó:

- **2014–2018 (vùng đỉnh)** — các cohort chất lượng cao 2013–2015 (retention ~50%/năm) đang ở
  giai đoạn sung sức nhất.
- **2019 (bước gãy)** — thời điểm các cohort chất lượng cao đã suy kiệt, trong khi cohort thay
  thế chỉ giữ chân được ~8%.
- **2020–2022 (chế độ mới)** — ổn định ở mức thấp, giữ bởi nền khách lặp lại khoảng
  **24.000 khách**.

**Hệ quả dự báo quan trọng nhất:** ngoại suy xu hướng đơn thuần sẽ dự đoán 2023–2024 **tiếp tục
giảm**. Nhưng cấu trúc khách hàng nói khác — số khách hoạt động đã **đi ngang ba năm liền**
(24.335 → 23.984 → 24.696) và 2022 còn nhích lên. Nền khách này không còn chỗ để rơi thêm:
phần dễ rời đã rời hết, phần còn lại là nhóm lặp lại ổn định.

> **Dự báo nên đi ngang quanh mức 2022, không nên tiếp tục dốc xuống.** Đây là một giả định
> có căn cứ cơ chế, kiểm chứng được — không phải cảm tính về đường xu hướng.

Tài liệu tham khảo (Phần C) rút ra ba quyết định kỹ thuật từ EDA chuỗi thời gian:

1. **Sample weighting + calibration** — vì ba chế độ có phân phối tách biệt
2. **Fourier seasonality** — vì hình dạng mùa vụ ổn định trong khi mức thay đổi
3. **Không dự báo COGS qua tỷ số cố định** — vì biên Q3 năm lẻ vượt 1,0

Phân tích cohort ở trên bổ sung **giả định thứ tư**: **ràng buộc mức (level constraint) cho
giai đoạn dự báo**, với căn cứ là quy mô nền khách lặp lại đã ổn định ba năm liền.

---

## 11. Tái lập số liệu

Toàn bộ con số trong tài liệu này sinh từ hai script:

| Script | Sinh ra |
|---|---|
| [`scripts/phan_tich_khach_hang.py`](../scripts/phan_tich_khach_hang.py) | Mục 2–5: quy mô, mua lại, phân rã đơn, thu nạp, cohort retention |
| [`scripts/phan_tich_kh_2.py`](../scripts/phan_tich_kh_2.py) | Mục 3, 8, 9: doanh thu mới/cũ, recency, chất lượng cohort, LTV theo kênh |

```bash
python scripts/phan_tich_khach_hang.py
```

Chạy từ thư mục gốc dự án, đọc trực tiếp `data/` (dữ liệu Bronze chưa làm sạch) để mọi con số
đối chiếu được với nguồn gốc. Riêng mốc cohort dùng `MIN(order_date)` — trùng đúng định nghĩa
`first_order_date` mà bước làm sạch đã tạo ra.

**Lưu ý về đơn vị tiền:** dữ liệu là mô phỏng, đơn vị tiền tệ không xác định. Mọi giá trị tuyệt
đối ghi là *đvtt* và chỉ nên dùng để so sánh tương đối, đúng như khuyến cáo của tài liệu tham
khảo: *tập trung vào tỷ lệ và thứ hạng thay vì giá trị tuyệt đối.*
