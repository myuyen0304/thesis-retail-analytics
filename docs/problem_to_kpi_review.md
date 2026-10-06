# Review `problem_to_kpi.html` — đối chiếu Measure / Metric / KPI với dataset

**Bản được review:** `docs/problem_to_kpi.html`, phiên bản **v2 · 06/09/2026**
(masthead: 15 CSV · 126 MB / Đơn hàng 646.945 · dòng 714.669 / Khách 121.930 · SKU 2.412).

> **Cập nhật sau review — bản v3.** Mục 04 đã được dựng lại thành hình cây *một bài toán gốc →
> sáu nhánh con* (mã `P1`…`P6` giữ nguyên làm bí danh của các nhánh `N1`…`N6` để tra ngược về
> bảng chỉ số). Ba đính chính ở C3, C5 và mục D đã được đưa thẳng vào file HTML: nhãn của P4 đổi
> từ "lỗi grain" sang **nhị phân hóa**, con số "vòng đời ngắn hơn 39%" ở P3/H5 đã **rút lại** và
> thay bằng bản khống chế cohort (4,79 vs 4,97), P2 chuyển từ "bài toán chính" thành **nhánh bị
> loại**. **Không có con số nào mới** — mọi số liệu trong v3 đều đã có mã kiểm chứng ở dưới.

**Cách kiểm chứng lại:** chạy từ **root repo**

```bash
python scripts/verify/verify_problem_to_kpi.py
```

Script chỉ đọc, không ghi gì vào `data/`. Mỗi mục dưới đây mang một **mã số** (A1, B3, C5…)
trùng đúng với mã số script in ra, theo đúng quy ước "`.md` là diễn giải, code là chứng minh"
ở CLAUDE.md §3 — ở đây không có notebook cặp đôi nên script đóng vai trò đó.
Ngưỡng dùng trong script: lệch tương đối **≤ 2%** thì coi là khớp.

---

## A. Đính chính cho bản review v1 của chính tôi

Bản nhận xét trước đó của tôi có một lỗi gốc, kéo theo ba kết luận sai. Ghi lại ở đây
vì file review là bản lưu trong repo — người đọc sau không có lịch sử chat.

### A1. `discount_amount` KHÔNG phải khoản ghi trùng — khách thực sự trả mức đã giảm

Tôi đã kết luận `discount_amount` là một khoản bút toán ghi trùng. **Sai.** Đối chiếu `payments.csv`:

```
payment_value == Σ(quantity × unit_price) − Σ discount_amount
→ khớp 646.945 / 646.945 đơn = 100,00%,  0 đơn lệch
2022:  Σ discount = 54.441.735   |   Revenue − Payment = 54.441.735
```

Chiết khấu được áp **hai lớp** và lớp thứ hai thực sự được trừ vào tiền khách trả.

### A2. Ba mức giá phải gọi tên rõ — độ sâu 31,6% là so với giá niêm yết

| Mức giá | Công thức | 2022 | Ghi chú |
|---|---|---|---|
| Niêm yết | `Σ quantity × products.price` | 1.234.360.532 | +5,52% |
| Sau lớp 1 | `Σ quantity × unit_price` | **1.169.748.832** | = `sales.csv` Revenue, **khớp chính xác** |
| Thực trả | `− discount_amount` = `payment_value` | 1.115.307.096 | −4,65% |

Độ sâu chiết khấu trên đơn có promo, **so với giá niêm yết**: p25 = 21,89% · **trung vị = 31,58%** ·
p75 = 35,47% · max = 55,42%. Con số **31,6% của v2 là đúng**.

Nếu chỉ đo so với `qty × unit_price` thì chỉ bắt được lớp thứ hai (trung vị **12,0%**) — đó là
chỗ con số 18,85% trong bản v1 của tôi đến từ. Khi viết định nghĩa measure, **phải khai báo mẫu số
là mức giá nào**, nếu không cùng một tên gọi "discount depth" sẽ ra ba giá trị khác nhau.

### A3. `MT-07 Contribution Margin` không hề trừ hai lần — phê bình cũ của tôi bị rút lại

Vì `discount_amount` thực sự được trừ, công thức `revenue − cogs − discount` là **đúng**.

Below-Cost Order Rate tính trên tiền thực trả:

| | Tỷ lệ |
|---|---|
| Đơn **có** promo | **69,78%** ← v2 ghi 69,8%, đúng |
| Đơn không promo | 0,17% |
| Toàn bộ | 26,88% |
| *(tính trên gross, không trừ discount — con số sai của bản v1)* | *18,44%* |

---

## B. Những con số v2 công bố — tái lập được

### B1–B2. Cấu trúc giá promo có quy luật đúng như v2 mô tả

`unit_price = products.price × (1 − discount_value)` chính xác ở cả 6 bậc:

| `discount_value` | `promo_type` | `unit_price / price` | Số dòng |
|---|---|---|---|
| 10 | percentage | 0,9000 | 45.448 |
| 12 | percentage | 0,8800 | 71.591 |
| 15 | percentage | 0,8498 | 8.905 |
| 18 | percentage | 0,8201 | 57.417 |
| 20 | percentage | 0,8000 | 71.799 |
| **50** | **fixed** | **0,4999** | 20.950 |

Bậc `fixed 50` của *Urban Blowout* hành xử như **giảm 50%**, không phải 50 đơn vị tiền —
v2 phát hiện đúng. Đây là một cái bẫy thật: đọc `promo_type` theo nghĩa đen sẽ tính sai toàn bộ
mô hình giá.

### B3. Năm định nghĩa doanh thu, và `sales.csv` chứa đơn đã hủy

Xem bảng ở **A2**, cộng thêm: bỏ đơn `cancelled` → 1.061.061.965 (**−9,29%**).

### B4. `sales.csv` bao gồm **59.462 đơn `cancelled`** (9,19% trên 646.945 đơn)

Đây là phát hiện mạnh nhất của v2. Target của bài dự báo cộng cả doanh thu của đơn không bao giờ
được giao. Nhưng lưu ý CLAUDE.md §5.1: công thức tái tạo `sales.csv` **đã được chốt** là
`Σ quantity × unit_price` không lọc trạng thái. Nên đây **không phải lỗi để đi sửa target** —
mà là một sự thật phải nêu khi định nghĩa "Revenue" trong tầng ngữ nghĩa, vì
"doanh thu" trong bài toán này ≠ "doanh thu đã thực hiện".

### B5. P2 — các con số đếm đều đúng

| | 2013 | 2022 |
|---|---|---|
| `sessions` | 6.801.940 | 11.063.658 |
| Số đơn | 76.849 | 36.004 |
| Đơn / 1.000 phiên | 11,30 | 3,25 |

*(Vấn đề của P2 không nằm ở các con số này — xem C1.)*

### B6. P4 — số học đúng: hết hàng thật là 3,87% SKU-ngày

`mean(stockout_days)/30 = 3,87%` so với `stockout_flag = 67,34%`. Khoảng cách 67% ↔ 4% là có
thật và đáng làm case study. *(Nhưng v2 giải thích sai nguyên nhân — xem C3.)*

Chênh 3,87 vs 3,81 của v2 đã truy ra được, không phải sai số: v2 chia cho **số ngày thật của
tháng**, `Σ stockout_days / Σ days_in_month = 3,81%`, còn cột `fill_rate` trong file dùng
**mẫu số cố định 30** → `Σ stockout_days / (n × 30) = 3,87%`. Cả hai đều tính đúng; chúng trả lời
hai câu hỏi khác nhau. Bản thân việc này lại củng cố C3.

### B7. P5 — first-touch ≠ last-touch, 20,0%

`customers.acquisition_channel` trùng với `order_source` của đơn đầu tiên chỉ **20,01%**,
trong khi mức ngẫu nhiên với 6 giá trị là 16,7%. Hai cột cùng tên "kênh" nhưng gần như độc lập.

### B8. Khoảng cách AOV promo/non-promo **đổi dấu** tùy thước đo giá

| Thước đo | Promo | Non-promo | Chênh |
|---|---|---|---|
| `qty × unit_price` | 21.914 | 27.565 | **−20,5%** |
| `qty × price` (niêm yết) | 27.002 | 27.566 | **−2,0%** |
| Số unit / đơn | 5,01 | 4,94 | +1,4% |

Giỏ hàng gần như **không đổi** — chênh lệch AOV gần như toàn bộ là hiệu ứng giá, không phải
hành vi mua. v2 nói đúng chỗ này.

### B9. Biên lợi nhuận gộp là **răng cưa chẵn/lẻ**, không phải suy giảm đơn điệu

```
2012 20,8% | 2013 11,5% | 2014 15,9% | 2015 11,9% | 2016 15,4% | 2017 11,3%
2018 16,6% | 2019 11,6% | 2020 16,0% | 2021  9,8% | 2022 12,8%
```

Năm lẻ luôn thấp hơn năm chẵn kề bên. Khớp với CLAUDE.md §5.6 (chu kỳ 2 năm của *Urban Blowout*).
Mốc 2012 = 20,8% là **năm cụt** (từ 2012-07-04) và chưa hề có khuyến mãi — đừng dùng nó làm
điểm đầu của bất kỳ đường xu hướng nào.

---

## C. Những vấn đề còn lại trong v2

### C1. P2 đứng trên hai chuỗi gần như không liên quan nhau — nhưng lại được xếp làm bài toán chính

```
corr(số đơn/ngày, sessions/ngày)      = +0,1909
corr theo tháng                        = +0,2827
corr trên SAI PHÂN ngày                = +0,0105   ← gần bằng 0
bounce_rate: min 0,0032  max 0,0058
trung bình mỗi năm: 2013…2022 = 0,0045 0,0044 0,0044 0,0044 0,0045 0,0045 0,0045 0,0045 0,0045 0,0045
```

Ba dấu hiệu cùng chỉ một hướng: `web_traffic` được **sinh độc lập** với bộ sinh đơn hàng.
Bounce rate 0,44% không tồn tại trong thương mại điện tử thật (thực tế 20–60%) và bất động đến
4 chữ số suốt 10 năm. Tương quan trên sai phân ~0 nghĩa là biết lưu lượng hôm nay **không** cho
biết gì thêm về số đơn hôm nay.

Nên "sụp đổ chuyển đổi −71%" chỉ là: một chuỗi đi lên, một chuỗi đi xuống, hai chuỗi rời nhau.
v2 có ghi hạn chế này ở mục "hạn chế phải nêu", nhưng vẫn gắn nhãn *"tín hiệu rất mạnh, đã đo"*
và *"khuyến nghị làm chính"*. Hai chỗ đó mâu thuẫn nhau.

### C2. Phân rã log của P2 là **đồng nhất thức**, không phải chẩn đoán

Vì `CVR ≡ đơn / phiên` theo đúng định nghĩa, nên

```
ln(đơn) = ln(phiên) + ln(CVR)     sai số tối đa 1,78e−15
```

đúng **tuyệt đối với mọi bộ số bất kỳ**. Một khi phiên tăng còn đơn giảm thì
"CVR giải thích toàn bộ mức giảm" là hệ quả đại số bắt buộc, không phải phát hiện.
Phân rã chỉ có giá trị chẩn đoán khi ba thành phần được đo **độc lập** (ví dụ CVR lấy từ
funnel riêng), không phải khi một thành phần là thương của hai thành phần kia.

### C3. P4 gọi sai tên nguyên nhân: đây là lỗi **nhị phân hóa**, không phải lỗi grain

v2 giải thích 67% ↔ 4% là "hai chỉ số cùng đúng vì khác grain". Không phải:

```
fill_rate == round(1 − stockout_days/30, 4)     → khớp 100,0% số dòng
corr(stockout_days, fill_rate)                  → −1,0000
số dòng = 60.247  |  số cặp (product_id, snapshot_date) duy nhất = 60.247
```

`stockout_flag`, `stockout_days`, `fill_rate` nằm **cùng một dòng**, cùng grain SKU × tháng.
`fill_rate` là cột **dẫn xuất tuyến tính** từ `stockout_days` (mẫu số cố định 30, không phải số
ngày thật của tháng — khớp với `days_in_month` chỉ 55,5%), không phải phép đo độc lập ở grain khác.

Bệnh thật: `stockout_flag` bật khi có **≥ 1 ngày** hết hàng, bất kể 1 ngày hay 28 ngày. Vì v2
bán P4 như "case study lỗi grain để đi phỏng vấn", gọi sai tên bệnh sẽ phản tác dụng. Sửa nhãn
thành *binarization / threshold collapse* thì case study vẫn nguyên giá trị.

### C4. Con số vòng đời khách 4,67 / 7,67 không khai báo định nghĩa

Sáu biến thể định nghĩa hợp lý, không cái nào ra đúng 4,67 / 7,67:

| Định nghĩa | Promo | Non-promo |
|---|---|---|
| Tất cả đơn, promo = đơn đầu tiên | 4,79 | 8,19 |
| Tất cả đơn, promo = **bất kỳ** đơn nào | 9,00 | 1,76 |
| Bỏ `cancelled`, promo = đơn đầu | 4,60 | 7,58 |
| Bỏ `cancelled`, promo = bất kỳ đơn nào | 8,39 | 1,75 |
| Bỏ `cancelled` + `returned` | 4,47 | 7,21 |
| Chỉ `delivered` | 4,35 | 6,85 |

Con số của v2 nằm giữa hàng 1 và hàng 3. Chú ý hàng 2 và 4: đổi *"promo ở đơn đầu"* thành
*"promo ở bất kỳ đơn nào"* làm kết luận **đảo ngược hoàn toàn** (4,79 vs 8,19 → 9,00 vs 1,76),
vì khách mua nhiều thì kiểu gì cũng dính ít nhất một chương trình. Đây chính xác là loại measure
phải khai báo grain và bộ lọc, nếu không thì con số vô nghĩa.

**Nhưng đừng dừng ở đây** — mục này chỉ là vấn đề khai báo. Xem **C5**: dù chọn định nghĩa nào
trong sáu dòng trên, khoảng cách đó cũng tan gần hết khi khống chế cohort. Đó mới là lỗi thật.

### C5. ⚠️ Khoảng cách vòng đời gần như **hoàn toàn** là ảo giác của cửa sổ quan sát

Đây là lỗi nghiêm trọng nhất còn lại, và nó cũng đính chính luôn nhận xét trước đó của tôi
(tôi đã nói khống chế cohort làm khoảng cách *rộng ra* — sai).

Số đơn trọn đời trung bình, tách theo **năm của đơn đầu tiên**:

| Năm đơn đầu | Promo | Non-promo | n_promo | n_non |
|---|---|---|---|---|
| 2012 | — | **14,19** | 0 | **22.068** |
| 2013 | 7,87 | 8,75 | 10.767 | 14.332 |
| 2014 | 4,45 | 4,62 | 4.635 | 8.658 |
| 2015 | 3,02 | 3,14 | 3.870 | 4.958 |
| 2016 | 2,20 | 2,29 | 2.150 | 4.242 |
| 2017 | 1,78 | 1,81 | 2.001 | 2.788 |
| 2018 | 1,51 | 1,49 | 1.226 | 2.491 |
| 2019 | 1,27 | 1,36 | 856 | 1.042 |
| 2020 | 1,22 | 1,23 | 584 | 916 |
| 2021 | 1,13 | 1,13 | 599 | 741 |
| 2022 | 1,05 | 1,05 | 483 | 839 |

`promotions.csv` bắt đầu từ **2013**, nên **toàn bộ 22.068 khách của cohort 2012 bị gán nhãn
non-promo theo cấu trúc dữ liệu**, và họ có 10,5 năm để tích lũy đơn → trung bình 14,19 đơn.

Bỏ riêng cohort 2012 ra: **promo 4,79 vs non-promo 4,97** — khoảng cách từ **−41% xuống còn −3,6%**.
Và trong **từng cohort năm một**, hai nhóm gần như trùng khít.

Đây là **nghịch lý Simpson** dạng sách giáo khoa. Kết luận "khách thu hút bằng khuyến mãi có vòng
đời ngắn hơn 39%" không đứng được. Nếu vẫn muốn giữ luận điểm này, phải:
1. so sánh **trong cùng cohort** (đã làm ở trên → hiệu ứng gần như biến mất), và
2. cắt cửa sổ quan sát bằng nhau cho mọi khách (ví dụ chỉ đếm đơn trong 12 tháng đầu kể từ đơn đầu tiên).

### C6. Bài toán định danh của counterfactual chưa được đụng tới

H2′ đề xuất baseline "chỉ huấn luyện trên các kỳ không có chiến dịch". Nhưng **46,74%** số ngày
2013–2022 nằm trong một cửa sổ chiến dịch (50 chiến dịch trong `promotions.csv`), phân bố cực lệch:

| T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | T10 | T11 | T12 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 8% | 50% | 47% | 57% | **0%** | 27% | 74% | 53% | **100%** | 4% | 43% | **100%** |

Tập huấn luyện thực tế chỉ còn T5, T10 và đầu T1 — rồi phải ngoại suy sang T9 và T12 vốn bị phủ
100%. Lịch khuyến mãi **chính là** lịch, nên phơi nhiễm promo và mùa vụ không tách được
(positivity/overlap failure). Vấn đề không phải độ chính xác baseline, mà là **không tồn tại kỳ đối chứng**.

Hệ quả cho KPI: ngưỡng WAPE ≤ 12% cho baseline này đo sai thứ. Đo được thì cũng không dùng để
suy ra incrementality.

### C7. Danh mục có **814 / 2.412 SKU (33,7%) chưa từng được bán**

Masthead ghi "SKU 2.412" là đúng theo danh mục, nhưng chỉ **1.598** SKU từng xuất hiện trong
`order_items`. Phân loại ABC–XYZ của P4 phải khai báo mẫu là danh mục hay tập từng bán —
một phần ba là hàng chết sẽ đẩy toàn bộ SKU vào nhóm C/Z.

### C8. Hai chỗ lệch với kết luận đã chốt trong CLAUDE.md

| v2 ghi | CLAUDE.md |
|---|---|
| Đứt gãy cấu trúc năm **2019** | §5.2: **cuối 2018** |
| CAGR −3,80% "đúng như tài liệu" | §6: con số này **đã biết là sai** vì gộp hai chế độ qua đứt gãy |

Về mốc đứt gãy: tôi **không** dò lại (§5 cấm nói ngược điểm đã chốt mà không chỉ ra cell sai, và
tôi không chỉ ra được). Hai cách ghi có thể đang mô tả cùng một đứt gãy — "cuối 2018" gọi tên quý
cuối của chế độ cũ, "2019" gọi tên năm đầu của chế độ mới. Điểm cần thống nhất chỉ là **dùng chung
một cách ghi**, và trong repo này cách ghi của §5.2 là cách chuẩn.

Về CAGR: −3,80% đúng về số học nhưng vô nghĩa về diễn giải. Xác nhận nó là "đúng" mà không kèm
cảnh báo của §6 sẽ khiến người đọc dùng lại nó.

---

## D. Khuyến nghị

1. **Giữ P6 (tầng ngữ nghĩa / chất lượng đo lường) làm nền.** Nó mạnh lên hẳn nhờ hai bằng chứng
   định lượng thật: target chứa 59.462 đơn hủy (B4), và chiết khấu hai lớp làm ba mức giá bị
   dùng lẫn lộn (A2).
2. **Đổi chỗ P1 và P2.** P1 có bốn con số đã kiểm chứng, đều đến từ các bảng giao dịch có quan hệ
   nhân quả thật (31,6% · 69,8% · giỏ hàng không đổi · below-cost 0,2% ở nhóm không promo).
   P2 chỉ có hai chuỗi rời nhau (C1) và một phân rã đồng nhất thức (C2).
3. **Nếu vẫn giữ P2, đổi khung thành *"kiểm định xem `web_traffic` có dùng được không"***.
   Đó là một mục P6 rất tốt, và câu trả lời "không — hệ số tương quan trên sai phân là 0,01"
   là một kết quả đàng hoàng, phòng thủ được trước hội đồng.
4. **Bỏ luận điểm "vòng đời ngắn hơn 39%"** hoặc thay bằng bản có khống chế cohort (C5).
   Ở dạng hiện tại nó là nghịch lý Simpson và sẽ bị hỏi ngay.
5. **Sửa nhãn P4** từ "lỗi grain" thành "lỗi nhị phân hóa" (C3) — case study vẫn giữ nguyên sức nặng.
6. **Mọi định nghĩa measure phải khai báo:** mức giá nào ở mẫu số, lọc `order_status` nào,
   "promo" nghĩa là đơn đầu hay bất kỳ đơn nào. C4 cho thấy chỉ đổi mục cuối là kết luận đảo chiều.

---

*Mọi con số trong file này tái lập được bằng `python scripts/verify/verify_problem_to_kpi.py`
(chạy từ root repo, cần `data/`). Mã số trong script trùng với mã số các mục ở trên.*
