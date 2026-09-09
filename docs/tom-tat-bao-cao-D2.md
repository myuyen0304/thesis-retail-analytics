# D2 — Tóm tắt để báo cáo

> Bản một trang để cầm khi trình bày. Nội dung đầy đủ ở
> [`problem-statement-customer-retention.md`](problem-statement-customer-retention.md),
> demo chạy được ở [`D2-Demo.ipynb`](../D2-Demo.ipynb).

---

## 1. Bài toán lớn — nói trong ba câu

> Doanh thu mất **44,4%** từ đỉnh 2016. Mức giảm đến từ **số đơn**, không phải giá trị mỗi đơn —
> AOV còn tăng **+50,7%**. Nhưng số đơn là *kết quả*, không phải nguyên nhân: đơn hàng do khách
> tạo ra, nên câu hỏi thật là **nền khách hàng xói mòn ở khâu nào, cơ chế gì gây ra, và can
> thiệp nào giữ lại được**.

---

## 2. Tám con số phải thuộc

| | Con số | Ý nghĩa |
|---|---:|---|
| 1 | **−53,2%** | Số đơn 2013 → 2022 (69.756 → 32.620) |
| 2 | **72,2% / 45,2%** | Mất đơn do *ít khách* / do *mua thưa* |
| 3 | **26,9% / 73,1%** | Giảm khách mới do *rổ cạn* / do *tỷ lệ hút giảm* ⭐ |
| 4 | **20,02% → 2,38%** | Tỷ lệ hút từ pool — sụp hơn 8 lần |
| 5 | **49,5% → 7,0%** | Giữ chân năm +1, cohort 2013 → 2021 |
| 6 | **39,2% → 5,2%** | Tác hại khuyến mãi: thô → sau khi kiểm soát ⭐⭐ |
| 7 | **26,0% / 53,7% / 20,3%** | Chưa mua / ngủ đông / đang hoạt động |
| 8 | **5/5** | Số phép kiểm chứng chéo đều khớp |

---

## 3. Cây bài toán

```
BÀI TOÁN LỚN — nền khách hàng xói mòn
│
├── BTN1 · Tập khách đang ở trạng thái nào?          ✅ 26,0/53,7/20,3%
│
├── BTN2 · Mất khách hay mua thưa đi?                ✅ 72,2% / 45,2%
│     └── BTN3 · Kích hoạt hỏng hay giữ chân hỏng?   ✅ 26,9% / 73,1%
│           └── BTN4 · Cơ chế ở đơn đầu?             ✅ TRỌNG TÂM
│
├── BTN5 · Nền khách đỡ nổi 2023–24?                 ⏳ cần Chow test
└── BTN6 · Ngân sách nên đi đâu?                     ⏳ thiếu dữ liệu chi phí
```

**Câu nói kèm sơ đồ này** *(gần như chắc chắn bị hỏi)*:

> *"Sáu bài toán nhỏ không phải em tự chọn theo chủ đề. Chúng suy ra từ phân rã: doanh thu bằng
> số khách nhân tần suất nhân giá trị đơn, mà số khách lại bằng khách mới cộng khách giữ lại.
> Mỗi bài toán ứng với đúng một thành phần, nên phủ kín nguyên nhân chứ không bỏ sót."*

---

## 4. Bốn phát hiện chính

**① Không phải một sự cố, mà hai sự cố đồng thời.** Mất khách (72,2%) và giảm tần suất (45,2%)
xảy ra cùng lúc và nhân lên nhau. Sửa một cái không đủ.

**② Đây là thất bại KÍCH HOẠT, không phải thu nạp.** Đăng ký mới tăng **đơn điệu gấp 22 lần**
(957 → 21.103). Phễu đầu vào không tắt — cái hỏng là người đăng ký rồi không mua.

**③ Rổ cạn chỉ giải thích được 26,9%.** Ngay cả khi loại bỏ *hoàn toàn* hiệu ứng cơ học của một
danh sách khách đóng, tỷ lệ chuyển đổi vẫn sụp hơn 8 lần — chiếm **73,1%** mức giảm.

**④ Phần lớn "tác hại của khuyến mãi" là hiệu ứng cohort.** Tín hiệu thô nói giảm **39,2%**; sau
khi kiểm soát năm cohort thì chỉ còn **5,2%**. Biến `cohort_year` có HR = 0,7478 — mạnh hơn hẳn
mọi biến khác.

> **Đây là điều đáng nói nhất cả bài:** nếu dừng ở phân tích mô tả, kết luận sẽ là *"cắt ngân
> sách khuyến mãi ngay"*. Đó là **một quyết định sai**, xuất phát từ nhầm tương quan với nhân
> quả. Bước đi từ mô tả sang cơ chế không phải làm cho đẹp bài — nó **đổi hẳn khuyến nghị**.

---

## 5. Bản đồ: nói gì → mở ô nào

Số `In[n]` là số hiện bên trái mỗi ô trong `D2-Demo.ipynb`.

| Nói về | Mở | Chỉ vào |
|---|---|---|
| Quy mô dữ liệu, bộ lọc | `In[1]` | `live = 587.483` · loại 9,2% đơn hủy |
| **BTN1** trạng thái tập khách | `In[2]` | Kiểm tổng `= 121.930 → KHỚP` |
| **BTN2** phân rã số đơn | `In[3]` | `72,2%` / `45,2%` / `−17,4%` |
| **BTN3** tách rổ cạn ⭐ | `In[4]` | `−0,783 + −2,128 = −2,911`, sai số `4,4e-16` |
| Bác bỏ khung "thu nạp hỏng" | `In[5]` | Đăng ký tăng 22 lần · 89,1% độ trễ âm |
| Ma trận cohort | `In[6]` | `49,5% → 7,0%` |
| **BTN4** thiết lập | `In[7]` | 74,1% có sự kiện · trung vị 312 ngày |
| Tín hiệu thô | `In[8]` | `4,59` vs `7,56` đơn — chênh 39,2% |
| Đường Kaplan–Meier | `In[10]` | **Biểu đồ** — chênh 10,0 điểm % tại 1 năm |
| **Cox — kết quả chính** ⭐⭐ | `In[11]` | `promo 0,9482` · `cohort_year 0,7478` |
| Schoenfeld | `In[12]` | promo p=0,104 · cohort p=0,269 → **không vi phạm** |
| Matching | `In[13]` | HR `0,9461`, hiệu ứng **vẫn còn** |
| ANOVA kênh | `In[14]` | `F = 0,823 · p = 0,533` |
| **Năm phép kiểm** | `In[15]` | Bảng `5/5 KHỚP` |

---

## 6. Năm phép kiểm chứng — chiếu `In[15]`

```
1. Ba nhóm cộng lại bằng tổng đăng ký       121.930  =  121.930   KHỚP
2. Phân rã ln: rổ cạn + tỷ lệ hút = tổng  −2,911196 = −2,911196   KHỚP
3. Hai đường độc lập gặp nhau             −0,348322 = −0,348322   KHỚP
4. sales.csv vs Σ(quantity × unit_price)        1,0 =       1,0   KHỚP
5. payment_value = gross − discount          100,0% =      100%   KHỚP
```

**Câu nói khi bị hỏi *"chứng minh đi"*:**

> *"Em không chứng minh từng số riêng lẻ. Em thiết kế để các số **buộc phải khớp nhau** — nếu một
> số sai thì phép kiểm chéo sẽ vỡ. Đây là năm phép kiểm đó, và cả năm đều khớp."*

> Phép kiểm số 3 là mạnh nhất: cùng đo `ln(doanh thu 2022/2013)` bằng hai phân rã dùng **sáu
> thành phần hoàn toàn khác nhau** (phễu vs vòng đời), sai số `1,7e-16`.

---

## 7. Bảy câu hỏi khó — và câu trả lời

| Câu hỏi | Trả lời | Mở |
|---|---|---|
| *"Rổ khách có hạn thì khách mới giảm là đương nhiên, sao gọi là thất bại?"* | Đã tách: rổ cạn chỉ 26,9%, tín hiệu thật 73,1% | `In[4]` |
| *"Em nói thu nạp hỏng, nhưng đăng ký tăng đều mà?"* | Đúng — nên em gọi là thất bại **kích hoạt**, không phải thu nạp | `In[5]` |
| *"Khuyến mãi làm mất 39% giá trị khách, sao không cắt?"* | Con số đó là **tương quan thô**. Kiểm soát cohort xong chỉ còn 5,2% | `In[11]` |
| *"Sao chắc đó là nhân quả?"* | **Không chắc.** Em nói rõ đây là tương quan đã kiểm soát; còn confound ẩn không quan sát được | Mục 9.6 |
| *"Sao không chứng minh các kênh như nhau?"* | Không thể chứng minh điều không tồn tại. Em ghi *"không bác bỏ được H₀"*, kèm F và p | `In[14]` |
| *"Mô hình có vi phạm giả định không?"* | Có — `log_aov` và `category_Outdoor`. Nhưng hai biến mang kết luận chính **không** vi phạm | `In[12]` |
| *"Sao chưa xong BTN5, BTN6?"* | BTN5 cần Chow test — làm được. BTN6 cần bảng chi phí marketing — **dữ liệu không có** | Mục 3b |

---

## 8. Mạch 10 phút

| Phút | Nội dung | Mở |
|---|---|---|
| 0–1 | Bài toán lớn — ba câu ở Mục 1 | — |
| 1–2 | Cây bài toán, kèm câu nói ở Mục 3 | Sơ đồ |
| 2–3 | **BTN2** phân rã đơn: hai sự cố đồng thời | `In[3]` |
| 3–5 | **BTN3** tách rổ cạn ⭐ | `In[4]` `In[5]` |
| 5–8 | **BTN4** cơ chế: 39,2% → 5,2% ⭐⭐ | `In[10]` `In[11]` |
| 8–9 | Giới hạn: tương quan, không phải nhân quả | Mục 9.6 |
| 9–10 | **Năm phép kiểm chứng — kết bài ở đây** | `In[15]` |

> Nếu chỉ còn thời gian cho một thứ: chọn **`In[11]`** (Cox) và **`In[15]`** (năm phép kiểm).
> Một cái là đóng góp mới, một cái là bằng chứng số liệu đáng tin.

---

## 9. Chuẩn bị trước khi vào phòng

**Chọn đúng kernel.** Mở `D2-Demo.ipynb` → góc trên phải chọn **`Python 3.12 (datathon)`**.
Kernel mặc định là Anaconda Python 3.7.1 / pandas 0.23.4, **không có `lifelines`** — chọn nhầm
sẽ báo `ModuleNotFoundError` ngay `In[7]`.

**Chạy `Restart & Run All` một lần trước buổi báo cáo**, rồi để nguyên. Notebook mất vài phút vì
có mô hình Cox. Đã chạy sẵn thì lúc giảng viên bảo chạy lại chỉ cần `Ctrl + Enter`.

**Dự phòng:** máy phòng học không mở được Jupyter thì mở [`D2-Demo.html`](../D2-Demo.html) bằng
trình duyệt — nội dung y hệt, đã kèm sẵn mọi kết quả và biểu đồ.

---

## 10. Ba điều thành thật nên nói trước khi bị hỏi

1. **`promo_first` là tương quan đã kiểm soát, không phải nhân quả.** Khách nhạy giá tự chọn vào
   nhóm khuyến mãi theo đặc điểm không quan sát được. Matching chỉ cân bằng biến *đã quan sát*.
2. **H6 chỉ dựa trên n = 3 điểm.** Đủ để nói *chưa thấy dấu hiệu tiếp tục rơi*, chưa đủ khẳng
   định chế độ ổn định.
3. **BTN6 thiếu dữ liệu, không phải thiếu công.** Bộ dữ liệu không có bảng chi phí marketing —
   nêu rõ giới hạn tốt hơn là ước tính bừa.
