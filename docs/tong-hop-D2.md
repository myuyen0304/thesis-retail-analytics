# Tổng hợp bài toán D2 — Xói mòn nền khách hàng

> Bài toán lớn của khóa luận **Dự báo doanh thu và giá vốn hàng bán theo ngày**.
> Bộ dữ liệu thương mại điện tử thời trang, 04/07/2012 → 31/12/2022.
>
> Tài liệu chính: [`problem-statement-customer-retention.md`](problem-statement-customer-retention.md) ·
> Demo: [`D2-Demo.ipynb`](../D2-Demo.ipynb)

---

## 1. Bài toán lớn

> Doanh thu mất **44,4%** từ đỉnh 2016. Mức giảm đến từ **số đơn**, không phải giá trị mỗi đơn —
> AOV còn tăng **+50,7%**. Nhưng số đơn là *kết quả*, không phải nguyên nhân: đơn hàng do khách
> hàng tạo ra.
>
> **Câu hỏi thật:** nền khách hàng xói mòn ở khâu nào, cơ chế gì gây ra, và can thiệp nào giữ
> lại được?

### Trục phân tích ba tầng

```
Doanh thu
  = Số đơn                       × AOV
  = (Khách hoạt động × Tần suất) × AOV
  = ((Khách mới + Khách giữ lại) × Tần suất) × AOV
```

Sáu bài toán nhỏ ứng với đúng các thành phần trong phân rã này — nên chúng **phủ kín nguyên
nhân**, không phải gom bài toán rời theo chủ đề.

---

## 2. Cây bài toán và tiến độ

```
BÀI TOÁN LỚN — nền khách hàng xói mòn
│
├── BTN1 · Tập khách đang ở trạng thái nào?          ✅ 26,0 / 53,7 / 20,3%
│
├── BTN2 · Mất khách hay mua thưa đi?                ✅ 72,2% / 45,2%
│     └── BTN3 · Kích hoạt hỏng hay giữ chân hỏng?   ✅ 26,9% / 73,1%
│           └── BTN4 · Cơ chế ở đơn đầu?             ✅ TRỌNG TÂM
│
├── BTN5 · Nền khách đỡ nổi 2023–24?                 ⏳ cần Chow test
└── BTN6 · Ngân sách nên đi đâu?                     ⏳ thiếu dữ liệu chi phí
```

| | Bài toán nhỏ | Kết quả |
|---|---|---|
| **BTN1** | Trạng thái tập khách | 31.684 chưa mua · 65.493 ngủ đông · 24.753 hoạt động |
| **BTN2** | Mất khách hay mua thưa | Ít khách **72,2%** · mua thưa **45,2%** · tương tác −17,4% |
| **BTN3** | Kích hoạt hay giữ chân | Rổ cạn **26,9%** · tỷ lệ hút giảm **73,1%** |
| **BTN4** | Cơ chế ở đơn đầu | Khuyến mãi: thô **39,2%** → kiểm soát xong còn **5,2%** |
| **BTN5** | Nền khách 2023–24 | Đi ngang 3 năm, nhưng n = 3 quá mỏng |
| **BTN6** | Ngân sách | Đã loại phương án theo kênh; thiếu bảng chi phí |

---

## 3. Bốn phát hiện chính

**① Không phải một sự cố, mà hai sự cố đồng thời.**
Mất khách (72,2%) và giảm tần suất (45,2%) xảy ra cùng lúc và nhân lên nhau. Sửa một cái không đủ.

**② Là thất bại KÍCH HOẠT, không phải thu nạp.**
Số tài khoản đăng ký mới tăng **đơn điệu gấp 22 lần** (957 → 21.103). Phễu đầu vào không tắt —
cái hỏng là người đăng ký rồi không mua. Nếu phát biểu là *"thu nạp hỏng"* thì chuỗi đăng ký
này bác lại ngay lập tức.

**③ Rổ khách cạn chỉ giải thích được 26,9%.**
`customers.csv` là danh sách **đóng** 121.930 người, nên "khách mới giảm" trộn lẫn hiệu ứng cơ
học với tín hiệu thật. Phân rã logarit tách hai thứ: ngay cả khi loại bỏ *hoàn toàn* hiệu ứng
cạn rổ, tỷ lệ chuyển đổi vẫn sụp hơn **8 lần** (20,02% → 2,38%), chiếm **73,1%** mức giảm.

**④ ⭐ Phần lớn "tác hại của khuyến mãi" thực ra là hiệu ứng cohort.**
Tín hiệu thô nói khách có khuyến mãi ở đơn đầu mua ít hơn **39,2%** (4,59 vs 7,56 đơn trọn đời).
Sau khi kiểm soát năm cohort, danh mục và giá trị đơn, hiệu ứng còn lại chỉ **HR = 0,948** —
chậm hơn ~**5,2%**. Biến `cohort_year` có HR = **0,7478**, mạnh hơn hẳn mọi biến khác.

> **Đây là đóng góp mới của khóa luận.** Nếu dừng ở phân tích mô tả, kết luận sẽ là *"cắt ngân
> sách khuyến mãi ngay"* — **một quyết định sai**, xuất phát từ nhầm tương quan với nhân quả.
> Bước đi từ mô tả sang cơ chế không phải làm cho đẹp bài, nó **đổi hẳn khuyến nghị**.

---

## 4. Chín giả thuyết và kết quả

Ghi cả cái bị bác bỏ — đó là kết quả, không phải thất bại.

| # | Giả thuyết | Kết quả |
|:--:|---|---|
| H1 | Mất khách lớn hơn giảm tần suất | ✅ 72,2% vs 45,2% |
| H2 | Sau khi trừ rổ cạn, tỷ lệ hút vẫn là nguyên nhân chính | ✅ 73,1% vs 26,9% |
| H3 | Chất lượng cohort giảm đơn điệu | ✅ giảm liên tục, không gãy riêng ở 2019 |
| H4 | Gãy 2019 là hệ quả trễ của suy giảm cohort | ⏳ cần kiểm định |
| H5 | Kênh thu nạp không phân hóa giá trị | ⚠️ **không bác bỏ được H₀** — F = 0,823 · p = 0,533 |
| H6 | 2020–22 chưa thấy dấu hiệu tiếp tục rơi | ⚠️ ủng hộ yếu, n = 3 |
| H7 | Khuyến mãi đơn đầu giảm khả năng quay lại | ✅ đúng nhưng nhỏ — HR 0,948 |
| H8 | Giao hàng chậm giảm khả năng quay lại | ❌ **SAI** — p = 0,303 |
| H9 | Trả hàng đơn đầu là tín hiệu rời bỏ mạnh nhất | ❌ **SAI** — p = 0,161 |

> **H8 và H9 bị bác bỏ có giá trị thực hành:** đầu tư rút ngắn thời gian giao hàng **không phải**
> đòn bẩy giữ chân. Nếu không kiểm, nhóm có thể đề xuất sai hướng.

---

## 5. Phương pháp đã dùng

| Phương pháp | Dùng cho |
|---|---|
| Phân rã logarit `ln(a×b) = ln(a) + ln(b)` | Tách rổ cạn khỏi tỷ lệ hút (BTN3) |
| Phân rã ba thành phần | Mất khách vs giảm tần suất (BTN2) |
| Phân tích cohort | Chất lượng khách theo năm gia nhập |
| **Cox proportional hazards** | Cơ chế quay lại mua (BTN4) |
| **Kaplan–Meier + log-rank** | So sánh đường sống sót theo khuyến mãi |
| **Schoenfeld residuals** | Kiểm tra giả định của mô hình Cox |
| **Propensity score matching** | Tiến gần nhân quả cho `promo_first` |
| **ANOVA một chiều** | Kiểm định khác biệt LTV giữa 6 kênh |

**Về mô hình Cox:** 84.566 khách · 74,1% có sự kiện · trung vị 312 ngày · concordance 0,653.
Schoenfeld cho thấy `log_aov` và `category_Outdoor` **vi phạm** giả định — đã báo cáo rõ. Hai
biến mang kết luận chính (`promo_first` p = 0,104 · `cohort_year` p = 0,269) **không vi phạm**.

---

## 6. Bộ chỉ số

**13 Measure → 13 Metric → 7 KPI**, nối bằng ma trận truy vết. Mỗi bài toán nhỏ truy được xuống
một KPI có ngưỡng và hành động.

Ba thay đổi đáng nói so với bản đầu:

| | Vấn đề | Sửa |
|---|---|---|
| **Me8** | Lỗi grain — tử số trộn khách chưa mua (không có recency) với khách ngủ đông | Tách đôi: Me8a 26,0% · Me8b 72,6% |
| **K2** | Mục tiêu tăng trưởng trên một rổ **chỉ có thể co lại** — bất khả thi về cấu trúc | Đổi sang tỷ lệ hút từ pool |
| **K7** | Sáu KPI cũ **đều một hướng**, không cái nào chặn chi phí | Thêm guardrail: đơn đầu có khuyến mãi ≤ 30% |

> K7 trả lời phản biện: *"Nếu em giành lại khách bằng giảm giá sâu thì K1 tăng nhưng lợi nhuận
> sập — có gì chặn không?"*

---

## 7. Kiểm chứng số liệu

Nguyên tắc: **kiểm chứng phải đi bằng đường khác**. Tính bằng script A rồi chạy lại script A
không chứng minh gì — chỉ chứng minh code chạy hai lần ra cùng kết quả.

| Phép kiểm | Kết quả |
|---|---|
| Ba nhóm khách cộng lại bằng tổng đăng ký | 31.684 + 65.493 + 24.753 = **121.930** |
| Phân rã logarit: rổ cạn + tỷ lệ hút = tổng | sai số **4,4×10⁻¹⁶** |
| **Hai đường phân rã độc lập gặp nhau** | phễu và vòng đời cùng ra **−0,348**, sai số **1,7×10⁻¹⁶** |
| `sales.csv` vs `Σ(quantity × unit_price)` | tỷ lệ **1,000000** trên 3.833 ngày |
| `payment_value` = gross − discount | khớp **100%** trên 646.945 đơn |
| Nghiệm thu bộ chỉ số | **8/8** dòng `OK` |

**Câu nói khi bị hỏi *"chứng minh đi"*:**

> *"Em không chứng minh từng số riêng lẻ. Em thiết kế để các số **buộc phải khớp nhau** — nếu
> một số sai thì phép kiểm chéo sẽ vỡ. Đây là năm phép kiểm đó, và cả năm đều khớp."*

---

## 8. Sản phẩm

| Tệp | Nội dung |
|---|---|
| [`problem-statement-customer-retention.md`](problem-statement-customer-retention.md) | Tài liệu chính, ~950 dòng |
| [`D2-Demo.ipynb`](../D2-Demo.ipynb) | Demo 39 ô, đã chạy sẵn, 0 lỗi |
| [`D2-Demo.html`](../D2-Demo.html) | Bản dự phòng, không cần Jupyter |
| [`hinh/12-kaplan-meier-promo.png`](hinh/12-kaplan-meier-promo.png) | Đường Kaplan–Meier |
| [`scripts/kiem_chung_D2.py`](../scripts/kiem_chung_D2.py) | Kiểm chứng độc lập toàn bộ số liệu |
| [`scripts/btn4_survival.py`](../scripts/btn4_survival.py) | Cox PH · KM · Schoenfeld · PSM |
| [`scripts/nghiem_thu_D2.py`](../scripts/nghiem_thu_D2.py) | Nghiệm thu 8 chỉ số + kiểm tổng |
| [`scripts/ve_kaplan_meier.py`](../scripts/ve_kaplan_meier.py) | Sinh biểu đồ Kaplan–Meier |
| [`scripts/phan_tich_khach_hang.py`](../scripts/phan_tich_khach_hang.py) | Phân rã đơn hàng, cohort retention |
| [`scripts/phan_tich_kh_2.py`](../scripts/phan_tich_kh_2.py) | Doanh thu mới/cũ, recency, LTV theo kênh |

**Mọi con số trong tài liệu đều sinh từ script chạy trên `data/` gốc — không con số nào gõ tay.**

### Chạy lại

```bash
pip install lifelines
python scripts/nghiem_thu_D2.py
```

> **Lưu ý kernel.** Mở `D2-Demo.ipynb` phải chọn kernel **`Python 3.12 (datathon)`**. Kernel mặc
> định là Anaconda Python 3.7.1 / pandas 0.23.4, **không có `lifelines`** — chọn nhầm sẽ báo
> `ModuleNotFoundError`.

---

## 9. Việc chưa xong

| | Cần gì | Làm được không |
|---|---|---|
| **BTN5** Nền khách đỡ nổi 2023–24? | Kiểm định điểm gãy (Chow test / Bai–Perron) | ✅ **Làm được** với dữ liệu hiện có |
| **BTN6** Ngân sách nên đi đâu? | Bảng chi phí marketing | ❌ **Bộ dữ liệu không có** |
| **H4** Gãy 2019 là hệ quả trễ? | Mô phỏng doanh thu từ cohort | ✅ **Làm được** |

Phân biệt này quan trọng: BTN6 là **giới hạn dữ liệu**, không phải thiếu công.

---

## 10. Ba điều thành thật nên nói trước khi bị hỏi

1. **`promo_first` là tương quan đã kiểm soát, không phải nhân quả.** Khách nhạy giá tự chọn vào
   nhóm khuyến mãi theo đặc điểm không quan sát được. Matching chỉ cân bằng biến *đã quan sát*.
2. **H6 chỉ dựa trên n = 3 điểm.** Đủ để nói *chưa thấy dấu hiệu tiếp tục rơi*, chưa đủ khẳng
   định chế độ ổn định.
3. **`signup_date` hỏng nặng** — 73,8% đơn đặt trước ngày đăng ký, 89,1% khách có độ trễ âm.
   Chỉ dùng để bác bỏ khung "thu nạp hỏng", không làm căn cứ định lượng.

---

## 11. Nối sang chương mô hình

Cấu trúc khách hàng **giải thích cơ chế** sinh ra các chế độ mà mô hình dự báo phải xử lý:

- **2014–2018** — cohort chất lượng cao 2013–2015 (retention ~50%/năm) đang sung sức
- **2019** — cohort chất lượng cao suy kiệt, cohort thay thế chỉ giữ được ~8%
- **2020–2022** — ổn định ở mức thấp, giữ bởi nền khách lặp lại ~23.000 người

**Hệ quả:** ngoại suy xu hướng đơn thuần sẽ dự đoán 2023–2024 tiếp tục giảm, nhưng cấu trúc
khách hàng nói **đi ngang quanh mức 2022**. Đây là **giả định thứ tư** bổ sung cho ba quyết định
kỹ thuật đã có (sample weighting · Fourier seasonality · không dự báo COGS qua tỷ số cố định):
một **ràng buộc mức** cho giai đoạn dự báo.
