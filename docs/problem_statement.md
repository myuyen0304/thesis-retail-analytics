# Thiết kế vấn đề nghiên cứu — từ Problem statement đến KPI

**Đề tài:** *Xây dựng hệ thống hỗ trợ ra quyết định kinh doanh cho doanh nghiệp thời trang
thương mại điện tử dựa trên Retail Data Warehouse*

Tài liệu này trả lời yêu cầu của giảng viên: từ tài liệu tham khảo
`docs/references/[Reading]-Retail-Analytics-Forecasting.pdf`, chọn ra vấn đề nghiên cứu bám theo tên đề tài,
thiết kế **problem statement — câu hỏi — giả thuyết**, rồi từ đó thiết kế
**measure → metric → KPI**.

> **Quy ước §3 của repo:** file `.md` là phần *diễn giải*, notebook là phần *chứng minh chạy
> lại được*. Mọi con số trong tài liệu này đã được tính từ `data/` nhưng **chưa có cell notebook
> sở hữu chúng**. Notebook chứng minh dự kiến: `business_problem_design.ipynb` (xem §9).

---

## 1. Bối cảnh và kiểm chứng tiền đề

### 1.1 Khoảng trống của tài liệu tham khảo

Tài liệu tham khảo là lời giải chính thức của AI Việt Nam cho đúng bộ dữ liệu này:

| Phần | Nội dung | Trục phân tích |
|---|---|---|
| B (tr.7–46) | 5 dashboard Tableau + `prepare_tableau_data.py` | **Revenue** |
| C (tr.47–81) | Pipeline dự báo Ridge / LightGBM / Prophet | **Revenue và COGS, dự báo tách rời** |

Suốt 81 trang **không xuất hiện một chỉ số lợi nhuận nào** — COGS chỉ được xử lý như một chuỗi
thời gian thứ hai cần dự báo, không bao giờ như một thành phần của biên lợi nhuận. Ngoài ra,
cả 5 dashboard đều truy vấn trực tiếp từ dữ liệu thô, không có tầng định nghĩa chỉ số ở giữa —
tài liệu phải tự cảnh báo về nguy cơ nhân bản `payment_value` khi join (tr.36).

Đó là khoảng trống mà đề tài này lấp: **không phải làm dashboard đẹp hơn, mà là xây tầng nền
khiến các dashboard không thể mâu thuẫn nhau.**

### 1.2 Kiểm chứng ba tiền đề trong mô tả đề tài

| Tiền đề | Kết quả kiểm chứng |
|---|---|
| doanh nghiệp **thời trang** | ✅ `category`: Streetwear 1.320 · Outdoor 743 · Casual 201 · GenZ 148. `size` S/M/L/XL, 10 màu, `segment` Activewear/Performance/Premium/Trendy… |
| **tại Việt Nam** | ⚠️ 42 thành phố Việt Nam có thật, nhưng `region` chỉ có Central/East/West — xem giới hạn §8.2 |
| **15 bảng CSV** | ⚠️ 14 bảng nguồn + `sample_submission.csv`. `README.md` đang đếm 14; cần thống nhất |

---

## 2. Problem statement chính

**Bản 1 câu (slide):**

> Doanh nghiệp có đủ dữ liệu để ra quyết định nhưng không có nơi nào định nghĩa chỉ số một cách
> thống nhất, nên cùng một câu hỏi quản trị cho ra những con số khác nhau tùy vào bảng nguồn mà
> báo cáo tình cờ truy vấn.

**Bản chuẩn (phần Đặt vấn đề):**

> Hoạt động của doanh nghiệp thời trang thương mại điện tử này được ghi nhận rải rác trong 15 bảng
> dữ liệu tách biệt — đơn hàng, chi tiết sản phẩm, khách hàng, thanh toán, khuyến mãi, hoàn trả,
> đánh giá, giao vận, tồn kho và lưu lượng truy cập website. Không tồn tại một tầng định nghĩa chỉ
> số chung, nên mỗi báo cáo phải tự nối và tự tính lại từ dữ liệu thô. Hệ quả là cùng một chỉ số
> mang cùng một tên nhưng cho ra kết quả khác nhau ở những báo cáo khác nhau, và nhà quản lý không
> có cơ sở để biết con số nào đúng. Luận văn phân tích, thiết kế và xây dựng một hệ thống hỗ trợ
> ra quyết định trên nền Retail Data Warehouse nhằm giải quyết vấn đề này.

**Bản đầy đủ (khi cần chứng minh vấn đề có thật, không phải giả định):**

> …*(như trên)*… Nghiên cứu chứng minh hậu quả này là cụ thể và đo lường được trên chính bộ dữ
> liệu: chỉ số "tỷ lệ chiết khấu" tính từ cột `discount_amount` báo **0,97%** trong khi mức giảm
> giá thực tế so với giá niêm yết là **28,73%**, khiến một đợt khuyến mãi bán lỗ **34% trên doanh
> thu** hoàn toàn vô hình trước hệ thống báo cáo; và chỉ số "doanh thu" đang được công bố cao hơn
> số tiền thực nhận **31,3%** do tính gộp cả đơn đã hủy và đơn đã hoàn trả. Đây không phải sai sót
> vận hành, mà là hệ quả trực tiếp của việc thiếu một tầng định nghĩa chỉ số thống nhất.

> **Vì sao chọn bản đầy đủ khi bảo vệ.** Mô tả đề tài nêu *lợi ích* hệ thống mang lại
> ("cùng một chỉ số sẽ cho kết quả giống nhau ở mọi dashboard"). Statement phải nêu *nỗi đau*
> tương ứng — và hai con số trên là bằng chứng nỗi đau đó có thật với chi phí đo được. Phần lớn
> luận văn về Data Warehouse chỉ khẳng định "dữ liệu phân mảnh gây khó khăn" mà không chứng minh.

---

## 3. Năm problem statement con

Mô tả đề tài nêu ba chức năng — ***theo dõi** hiệu quả → **phân tích nguyên nhân** biến động →
**dự báo*** — đặt trên hai tầng nền: **Retail DW** và **các bảng tổng hợp**. Đúng năm problem.

```text
PS1  Retail Data Warehouse        (tích hợp 15 nguồn)
 └── PS2  Tầng bảng tổng hợp      (định nghĩa chỉ số — hạt nhân luận văn)
      ├── PS3  Theo dõi           → Dashboard điều hành
      ├── PS4  Phân tích nguyên nhân → Dashboard sản phẩm + Dashboard khách hàng
      └── PS5  Dự báo             → hỗ trợ lập kế hoạch
```

---

### PS1 — Tích hợp: xây dựng Retail Data Warehouse

**Problem statement**

> Dữ liệu nằm ở 15 bảng rời với các grain khác nhau — dòng hàng, đơn hàng, khách hàng, SKU, ảnh
> chụp tồn kho cuối tháng, ngày truy cập web. Không có mô hình dữ liệu thống nhất nào cho phép trả
> lời một câu hỏi quản trị cắt ngang nhiều nghiệp vụ. Problem: thiết kế và hiện thực hóa một
> Retail Data Warehouse tích hợp toàn bộ 15 nguồn, giải quyết được các khác biệt về grain, phân
> cấp chiều và tính cộng dồn.

**Câu hỏi nghiên cứu**

| Mã | Câu hỏi |
|---|---|
| Q1.1 | Chiều địa lý có phân cấp hợp lệ không, và khóa đúng của nó là gì? |
| Q1.2 | Những bảng nguồn nào không thể nối trực tiếp vào bảng fact chính, và vì sao? |
| Q1.3 | Measure nào không cộng dồn được theo mọi chiều? |
| Q1.4 | Có chỉ số kinh doanh nào **không có sẵn cột nào** trong nguồn để tính không? |

**Giả thuyết và kết quả kiểm chứng**

| Mã | Giả thuyết | Bằng chứng |
|---|---|---|
| **H1.1** | `district` **không** phải cấp phân cấp hợp lệ; khóa đúng của chiều địa lý là `(city, district)` | ✅ **39/39** district xuất hiện ở nhiều thành phố. "District #13" có mặt ở ≥8 thành phố (Bắc Giang, Bắc Ninh, Cẩm Phả, Hạ Long, Hải Phòng, Hà Nội, Lào Cai, Nam Định…) |
| **H1.2** | `payment_value` ở grain **đơn hàng**, nối thẳng vào fact grain dòng-hàng sẽ **nhân bản** giá trị | ✅ 646.945 đơn vs 714.669 dòng hàng — đúng lỗi tài liệu tham khảo cảnh báo ở tr.36 |
| **H1.3** | Tồn kho là measure **bán cộng dồn** — cộng theo sản phẩm được, cộng theo thời gian thì sai | ✅ `inventory` = ảnh chụp (cuối tháng × SP), 60.247 dòng |
| **H1.4** | `web_traffic` **không có khóa ngoại** nối vào bảng nào; chỉ ghép được ở cấp ngày | ✅ 3.652 dòng × 7 cột, không FK |
| **H1.5** | Mức giảm giá thực tế **không nằm trong cột nào** của nguồn; phải tạo measure dẫn xuất | ✅ xem H2.3 — `discount_amount` báo 0,97% khi markdown thật là 28,73% |

Các phân cấp **hợp lệ** đã kiểm chứng: `zip → city` ✅ · `city → region` ✅ ·
`(city, district) → region` ✅ · `zip` duy nhất trên 39.948 dòng ✅

> **H1.5 là giả thuyết đắt giá nhất của PS1.** Nó chứng minh thiết kế Data Warehouse không phải
> việc sao chép cột từ nguồn sang đích, mà là việc **quyết định cái gì cần được đo**.
> Bốn giả thuyết còn lại nói về *cách* tích hợp; H1.5 nói về *nội dung* cần tích hợp.

---

### PS2 — Chuẩn hóa chỉ số: tầng bảng tổng hợp *(hạt nhân của luận văn)*

**Problem statement**

> Không tồn tại định nghĩa chuẩn cho các chỉ số cốt lõi — doanh thu, giá vốn, lợi nhuận, số đơn
> hàng, tỷ lệ hoàn trả. Mỗi chỉ số có nhiều cách tính hợp lệ về mặt kỹ thuật nhưng cho kết quả
> chênh nhau tới hàng chục phần trăm, và không có cơ chế nào bắt buộc các báo cáo dùng chung một
> cách tính. Problem: thiết kế tầng bảng dữ liệu tổng hợp đóng vai trò nguồn chân lý duy nhất, và
> chứng minh được rằng mọi con số trên dashboard truy ngược được về dữ liệu nguồn.

**Câu hỏi nghiên cứu**

| Mã | Câu hỏi |
|---|---|
| Q2.1 | Doanh thu công bố hiện tại được tính thế nào, và có bao gồm đơn đã hủy / đã trả không? |
| Q2.2 | Khoảng cách giữa doanh thu công bố và doanh thu thực nhận là bao nhiêu? |
| Q2.3 | Cùng một chỉ số "chiết khấu", hai cách tính hợp lệ cho ra chênh lệch bao nhiêu? |
| Q2.4 | Cần bao nhiêu định nghĩa doanh thu để báo cáo trung thực, và mỗi định nghĩa dùng ở đâu? |

**Giả thuyết**

| Mã | Giả thuyết |
|---|---|
| **H2.1** | Doanh thu công bố tính cả đơn `cancelled` và `returned` |
| **H2.2** | Khoảng cách giữa doanh thu công bố và doanh thu thực nhận **vượt 15%** |
| **H2.3** | Tầng nguồn **không phát tín hiệu nào** cảnh báo rằng cột mang tên `discount_amount` bỏ sót cơ chế giảm giá chủ đạo, nên một báo cáo đặt tên "chiết khấu" sẽ tự nhiên chọn đúng cột sai |

#### Bằng chứng H2.1 — cách tính doanh thu hiện tại

`sales.csv` tổng = **16.430.476.586** = `Σ quantity × unit_price` **không lọc `order_status`**
(khớp chính xác đến đơn vị; nếu lọc bỏ `cancelled` thì còn 14.914.585.579 → không khớp).

| `order_status` | % doanh thu công bố |
|---|---|
| `delivered` | **79,83%** |
| `cancelled` | **9,23%** |
| `returned` | 5,52% |
| `shipped` | 2,15% |
| `paid` | 2,11% |
| `created` | 1,16% |

#### Bằng chứng H2.2 — thác nước đối soát

**Quy tắc tính (phải nêu rõ, vì đây chính là điều luận văn phê phán ở báo cáo cũ):** chỉ đơn
`delivered` mới tạo ra doanh thu thực nhận. Các khoản trừ dưới đây **rời nhau hoàn toàn** — đã
kiểm chứng: **0 đơn** vừa có dòng trong `returns.csv` vừa mang trạng thái khác `returned`, nên
`refund_amount` nằm trọn trong nhóm `returned` và không bị trừ hai lần.

```text
Gross Revenue (= sales.csv, mọi trạng thái)   16.430.476.586   100,00%
  − đơn đã hủy          (cancelled)           −1.515.891.006    −9,23%
  − đơn đã trả          (returned)              −907.543.032    −5,52%
  − đơn chưa giao       (created/paid/shipped)  −889.951.187    −5,42%
──────────────────────────────────────────────────────────────────────
= Delivered Revenue                           13.117.091.360    79,83%
  − chiết khấu trên đơn delivered               −598.915.403    −3,65%
  − hoàn tiền trên đơn delivered                          −0    −0,00%
──────────────────────────────────────────────────────────────────────
= Realized Revenue                            12.518.175.957    76,19%
```

Diễn đạt khoảng cách theo hai chiều, và **phải dùng nhất quán một chiều khi bảo vệ**:

- doanh thu công bố **phóng đại 31,3%** so với thực nhận (`16.430 / 12.518 = 1,313`);
- doanh thu thực nhận **thấp hơn 23,8%** so với công bố (`1 − 0,7619`).

> **Điểm sẽ bị hỏi khi bảo vệ — chuẩn bị sẵn câu trả lời.** Khoản trừ `created`/`paid`/`shipped`
> (5,42%) là **trạng thái tạm thời**, không phải doanh thu mất đi: một đơn đang ở `shipped` ngày
> 2022-12-31 nhiều khả năng vẫn giao được, nó chỉ đang dở dang tại thời điểm cắt dữ liệu. Nên
> chuẩn bị thêm một con số **thận trọng hơn**, chỉ loại `cancelled` + `returned` + chiết khấu và
> coi đơn dở dang rồi sẽ giao: **81,36%** (13.367.916.913). Kết luận không đổi — cả hai đều dưới
> ngưỡng cảnh báo 85% của K6 — nhưng chỉ con số 76,19% mới vượt ngưỡng nghiêm trọng 80%.
> Nêu cả hai là cách trung thực nhất.

#### Bằng chứng H2.3 — cái bẫy đặt tên ở tầng nguồn

Cùng một sự kiện (tháng 8 các năm lẻ), hai đại lượng cùng được gọi là "chiết khấu":

| Đại lượng | Công thức | Kết quả | Kết luận rút ra |
|---|---|---|---|
| `discount_amount` (cột có sẵn) | `Σ discount_amount / Σ gross` | **0,97%** | "Chiết khấu ở mức bình thường" ✅ xanh |
| Markdown so với giá niêm yết | `Σ (list − thực bán) / Σ list` | **28,73%** | "Đang xả hàng dưới giá vốn" 🔴 đỏ |

Trong khi biên lợi nhuận thật của kỳ đó là **−34,03%**.

> **Cách diễn đạt phải chính xác — điểm này sẽ bị vặn.** Đây **không phải** hai định nghĩa cùng
> đúng của một chỉ số. Markdown mới là đại lượng phản ánh đúng cơ chế giảm giá; `discount_amount`
> đo một thứ khác (phần chiết khấu *có ghi nhận*) và **không sai** — nó chỉ không đo cái mà người
> đọc báo cáo tưởng nó đo.
>
> Vấn đề nằm ở chỗ khác, và đó mới là luận điểm của PS2: **một báo cáo cần chỉ số "chiết khấu" sẽ
> tự nhiên với tay tới cột mang đúng cái tên đó**, và không có gì trong tầng dữ liệu nguồn phát
> tín hiệu rằng cột ấy bỏ sót cơ chế chủ đạo. Đây chính là loại lỗi mà tầng bảng tổng hợp sinh ra
> để chặn: khi chỉ số được định nghĩa một lần ở tầng chung, người làm dashboard không còn phải
> đoán cột nào là cột đúng.

Đây là ví dụ minh họa trung tâm của luận văn và nên đặt ngay phần mở đầu.

**→ Cả ba giả thuyết đều được ủng hộ.**

---

### PS3 — Theo dõi hiệu quả: Dashboard điều hành

**Problem statement**

> Nhà quản lý cần biết doanh nghiệp đang hoạt động tốt hay xấu, nhưng chỉ số đang dùng để trả lời
> câu hỏi đó (doanh thu gộp) vừa phóng đại kết quả vừa không phản ánh khả năng sinh lời.
> Problem: xác định bộ KPI tối thiểu đủ để theo dõi hiệu quả kinh doanh, kèm ngưỡng cảnh báo và
> hành động tương ứng.

**Câu hỏi nghiên cứu**

| Mã | Câu hỏi |
|---|---|
| Q3.1 | Bộ KPI tối thiểu nào đủ để phát hiện sớm cả bốn vấn đề tìm được ở PS2 và PS4? |
| Q3.2 | Ngưỡng cảnh báo đặt ở đâu, khi không có stakeholder giao chỉ tiêu? |
| Q3.3 | Làm sao chứng minh mọi con số trên dashboard là đúng? |

**Giả thuyết**

| Mã | Giả thuyết |
|---|---|
| **H3.1** | Một bộ **9 KPI** là đủ để bao phủ toàn bộ phát hiện của PS2 và cả năm phân tích của PS4 |
| **H3.2** | Bộ KPI **chỉ dựa trên doanh thu** sẽ **không phát hiện** được cả hai vấn đề nghiêm trọng nhất (đợt lỗ 34% và mức phóng đại 31,3%) |
| **H3.3** | Tính đúng đắn của dashboard chứng minh được bằng một **cổng kiểm tra chạy tự động**, không cần rà tay |

Chi tiết bộ KPI: xem §6. H3.3 đã có sẵn hạ tầng: `archive/databricks/retail_medallion/src/quality/`
(`30_fk_checks`, `40_invariants`, `50_reconciliation`, `99_quality_gate`).

> **H3.2 là giả thuyết biện minh cho toàn bộ đề tài.** Nếu nó bị bác bỏ — tức bộ KPI doanh thu
> thuần vẫn phát hiện được các vấn đề — thì hệ thống này không cần thiết. Vì vậy nó phải được
> kiểm định tường minh, không được coi là hiển nhiên.

---

### PS4 — Phân tích nguyên nhân: Dashboard sản phẩm & Dashboard khách hàng

**Problem statement**

> Doanh thu đã trải qua một đứt gãy cấu trúc năm 2018 và biến động mạnh theo mùa vụ, chu kỳ khuyến
> mãi và chu kỳ trong tháng. Hệ thống báo cáo hiện tại mô tả được các biến động này nhưng không
> quy trách nhiệm được cho nguyên nhân nào — không tách được ảnh hưởng của sản lượng khách hàng,
> cơ cấu danh mục, chính sách giá và hoạt động khuyến mãi. Problem: thiết kế các bảng tổng hợp và
> chỉ số cho phép phân rã biến động doanh thu và lợi nhuận về từng nguyên nhân cấu thành.

PS4 gồm năm phân tích. **D1, D2, D4** đã có bằng chứng sơ bộ; **D3, D5** là phần việc còn lại mà
mô tả đề tài bắt buộc phải có (hai dashboard được nêu đích danh).

#### D1 — Đứt gãy 2018: doanh nghiệp mất gì?

| Mã | Câu hỏi |
|---|---|
| Q4.1 | Trong phân rã `Revenue = N_đơn × Units/đơn × ASP`, thành phần nào giải thích mức rơi? |
| Q4.2 | ASP thay đổi do **giá bán** hay do **cơ cấu sản phẩm** (mix)? |
| Q4.3 | Biên lợi nhuận sau đứt gãy tốt lên hay xấu đi? |

| Mã | Giả thuyết |
|---|---|
| **H4.1** | Mức rơi chủ yếu đến từ **sản lượng đơn hàng**, không từ giá |
| **H4.2** | ASP tăng là **hiệu ứng mix**, không phải doanh nghiệp tăng giá |
| **H4.3** | Dù bán hàng đắt tiền hơn, **biên lợi nhuận vẫn xấu đi** |

| Thành phần | 2012–2018 | 2019–2022 | Thay đổi |
|---|---|---|---|
| Số đơn/năm | 76.913 | 36.753 | **−52,2%** |
| Units/đơn | 5,016 | 4,798 | −4,3% |
| ASP | 4.795,63 | 6.243,73 | **+30,2%** |
| COGS/Revenue | 0,8573 | 0,8748 | xấu đi |
| **Biên lợi nhuận gộp** | **14,27%** | **12,52%** | **−1,75 điểm %** |

*Số đơn/năm chuẩn hóa theo độ dài giai đoạn: giai đoạn trước dài 6,49 năm (dữ liệu bắt đầu
2012-07-04, không phải đầu năm), giai đoạn sau dài 4,0 năm. Các chỉ số còn lại là tỷ lệ nên không
phụ thuộc độ dài giai đoạn.*

Phân rã ASP trên **730 SKU có mặt ở cả hai giai đoạn** (chỉ số Laspeyres — áp giá mới lên cơ cấu cũ):

```text
ASP trên rổ chung:  4.318 → 5.342  (+23,7%)
  hiệu ứng GIÁ (giá mới, cơ cấu cũ) = −0,7%
  hiệu ứng MIX                      = +24,6%
giá niêm yết TB (theo units): 5.154 → 6.759
```

Phép phân rã chỉ giải thích **+23,7%** chứ không phải toàn bộ +30,2%, vì nó chỉ chạy trên rổ SKU
chung. Phần chênh còn lại đến từ **SKU vào/ra danh mục** — điều đó càng củng cố H4.2, vì những
SKU biến mất chính là nhóm hàng rẻ.

**→ H4.1, H4.2, H4.3 đều được ủng hộ.** Doanh nghiệp không hề tăng giá (hiệu ứng giá ≈ 0). Nửa số
đơn hàng biến mất, tập trung ở phân khúc hàng rẻ, kéo ASP lên một cách thụ động. Sản phẩm bán ra
đắt hơn 30% nhưng biên lợi nhuận vẫn hụt 1,75 điểm phần trăm.

> Đây chính là lý do một dashboard lấy doanh thu làm trục nguy hiểm: nhìn ASP tăng 30% rất dễ đọc
> nhầm thành *"chiến lược nâng cấp sản phẩm thành công"*, trong khi thực tế là mất thị phần ở đáy.

#### D2 — Khuyến mãi tháng 8 năm lẻ: tạo giá trị hay phá giá trị?

Chương trình *"Urban Blowout"* diễn ra tháng 8 các năm lẻ theo chu kỳ hai năm. Tài liệu tham khảo
biết hiện tượng này (`PROMO_SCHEDULE`, tr.57) nhưng chỉ dùng nó **làm feature dự báo** — tức coi
là hiện tượng phải học thuộc, không phải quyết định kinh doanh cần đánh giá.

| Mã | Câu hỏi |
|---|---|
| Q4.4 | Đợt khuyến mãi có tạo ra **đơn hàng tăng thêm** không? |
| Q4.5 | Mức giảm là **markdown thật trong từng SKU** hay do bán sang nhóm hàng rẻ? |
| Q4.6 | Biên lợi nhuận trong đợt là bao nhiêu? |

| Mã | Giả thuyết |
|---|---|
| **H4.4** | Đợt khuyến mãi **không tạo uplift sản lượng đơn hàng** |
| **H4.5** | Mức giảm là markdown thật trong từng SKU |
| **H4.6** | Đợt khuyến mãi **bán dưới giá vốn** |

Gộp toàn bộ năm chẵn vs năm lẻ: doanh thu/ngày 5.436.813 vs 3.246.450 (−40,3%), ASP 5.763,44 vs
3.419,89 (−40,7%), biên lợi nhuận **+20,06% vs −34,03%**, tỷ lệ `discount_amount` 0,06% vs 0,97%.

> **Cảnh báo phương pháp — con số gộp không dùng được cho Q4.4.** Số đơn/ngày gộp là 192,24 (chẵn)
> vs 193,90 (lẻ), nhìn qua thì "y hệt". Nhưng phép gộp này **trộn qua đứt gãy 2018**: năm chẵn có
> 4 năm trước / 2 năm sau, năm lẻ có 3 trước / 2 sau, trong khi sản lượng đơn giảm một nửa qua đứt
> gãy. Hai hiệu ứng ngược chiều có thể triệt tiêu nhau và tạo ra sự bằng nhau giả. Q4.4 phải kiểm
> định bằng đối chứng giữ chế độ cố định.

**Kiểm định H4.6 — biên lợi nhuận tháng 8 theo từng năm** (mức tuyệt đối, không cần đối chứng)

| Năm | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Chẵn/lẻ | C | **L** | C | **L** | C | **L** | C | **L** | C | **L** | C |
| Biên LN T8 | +21,1% | **−30,7%** | +20,6% | **−32,4%** | +19,9% | **−35,4%** | +20,8% | **−34,2%** | +19,7% | **−40,1%** | +17,2% |

Sáu năm chẵn dương, năm năm lẻ âm, **không một ngoại lệ**. H4.6 vững tuyệt đối.

**Kiểm định H4.4 — đối chứng trong cùng năm** (tháng 8 so với trung bình tháng 7 và tháng 9;
cách này giữ cố định cả chế độ lẫn xu hướng theo đúng nghĩa đen)

| | Số đơn/ngày T8 lệch so với T7 & T9 |
|---|---|
| Trung bình các năm **chẵn** (không khuyến mãi) | **+17,63%** |
| Trung bình các năm **lẻ** (có Urban Blowout) | **+14,04%** |
| **Uplift do khuyến mãi** | **−3,6 điểm %** |

Đối chứng thứ hai, so trong từng chế độ: 2013–2018 cho uplift **+0,3%**; 2019–2022 cho +9,6% nhưng
con số này không tin được vì chỉ có 2 năm mỗi nhóm và các năm lẻ (2019, 2021) đều đứng *trước* các
năm chẵn (2020, 2022) trên một xu hướng đang giảm — tức bị lẫn với xu hướng.

**Kiểm định H4.5 — mix hay markdown**, trên **1.033 SKU có mặt ở cả hai nhóm**:

```text
độ sâu giảm giá so với giá niêm yết:  0,06%  →  28,73%
giá niêm yết TB:                      5.767  →  5.712   (không đổi)
```

**→ Cả ba giả thuyết đều được ủng hộ.** Đây là phát hiện mạnh nhất của luận văn:

> Tháng 8 vốn đã là tháng cao điểm tự nhiên (+17,6% so với tháng liền kề, ở những năm không khuyến
> mãi). Đợt Urban Blowout **không những không kéo thêm đơn hàng nào, mà còn thấp hơn mức cao điểm
> tự nhiên đó 3,6 điểm phần trăm** — trong khi giảm giá thật 28,7 điểm phần trăm trên đúng những
> SKU đó và bán ra ở mức **lỗ 34% trên doanh thu**. Đúng lượng khách đó, đúng những món hàng đó,
> chỉ khác là bán lỗ.

> **Ghi chú đối chiếu `CLAUDE.md` §5.6.** §5.6 ghi doanh thu năm lẻ **−37%** và tỷ lệ COGS/Revenue
> **~1,36**; ở đây là −40,3% và 1,34. Chênh lệch đến từ nguồn tính: §5.6 tính trên chuỗi ngày của
> `sales.csv`, còn bảng này tính trên `order_items × orders × products`. Không mâu thuẫn (§5.1 bảo
> đảm hai nguồn khớp ở mức tổng), chỉ khác cách lấy trung bình. Notebook chứng minh phải trình bày
> cả hai cách để §5.6 và tài liệu này không nói ngược nhau.

#### D3 — Khách hàng biến mất sau 2018: họ là ai? *(Dashboard khách hàng)*

D1 cho thấy số đơn hàng giảm 52%. Câu hỏi tiếp theo — và là nội dung chính của Dashboard khách
hàng — là **ai đã rời đi**.

| Mã | Câu hỏi |
|---|---|
| Q4.7 | Nhóm khách rời đi tập trung ở phân khúc nào (giới tính, độ tuổi, kênh thu hút, địa lý)? |
| Q4.8 | Có dấu hiệu báo trước trong hành vi mua trước khi họ rời đi không? |
| Q4.9 | Tỷ lệ giữ chân theo cohort đăng ký thay đổi thế nào qua đứt gãy? |

| Mã | Giả thuyết | Trạng thái |
|---|---|---|
| **H4.7** | Nhóm khách rời đi tập trung ở phân khúc mua hàng giá thấp — nhất quán với hiệu ứng mix ở H4.2 | ⏳ **chưa kiểm định** |
| **H4.8** | Tỷ lệ giữ chân của các cohort đăng ký **sau 2018** thấp hơn rõ rệt so với cohort trước | ⏳ **chưa kiểm định** |

**Dữ liệu hỗ trợ — đã kiểm chứng đầy đủ:**
`customers.csv` có `gender` (Female 59.640 · Male 57.457 · Non-binary 4.833), `age_group`
(5 nhóm: 18-24, 25-34, 35-44, 45-54, 55+), `acquisition_channel` (6 kênh: organic_search,
social_media, paid_search, email_campaign, referral, direct), và `signup_date` phủ
2012-01-17 → 2022-12-31 **không thiếu một dòng nào**. Phân tích RFM và cohort làm được ngay.

#### D4 — Cao điểm cuối tháng: nhu cầu thật hay doanh số mua bằng chiết khấu?

| Mã | Câu hỏi | Mã | Giả thuyết |
|---|---|---|---|
| Q4.10 | Biên lợi nhuận cuối tháng khác gì giữa tháng? | **H4.9** | Cuối tháng doanh thu cao nhất nhưng **biên lợi nhuận thấp nhất** |
| Q4.11 | Tỷ lệ chiết khấu cuối tháng có cao hơn không? | **H4.10** | Chênh lệch được giải thích bằng **chiết khấu sâu hơn** |

| Vị trí trong tháng | Doanh thu/ngày | Biên LN gộp | Tỷ lệ chiết khấu |
|---|---|---|---|
| Ngày 01–10 | 3.657.472 | 13,52% | 4,64% |
| Ngày 11–25 | 4.061.858 | **14,66%** | **4,02%** |
| **Ngày 26–cuối tháng** | **6.058.487** | **12,51%** | **5,48%** |

**→ H4.9 và H4.10 được ủng hộ.** Doanh thu cuối tháng cao hơn giữa tháng 49%, nhưng biên lợi
nhuận thấp hơn 2,15 điểm % và chiết khấu sâu hơn 1,46 điểm %.

> **Giới hạn phải nêu rõ.** Dữ liệu **không** cho phép phân biệt hai cách giải thích: (a) nhân
> viên bán hàng đẩy chiết khấu để chốt chỉ tiêu tháng, hay (b) khách hàng nhận lương cuối tháng
> nên mua nhiều hơn và nhạy giá hơn. Muốn tách bạch cần dữ liệu chỉ tiêu/hoa hồng nhân viên —
> không có trong 15 file nguồn. D4 vì vậy dừng ở mức **mô tả có kiểm định**, không kết luận nhân
> quả. Đây là phân tích yếu nhất trong năm cái, xếp ở vị trí phụ.

#### D5 — Lợi nhuận theo sản phẩm *(Dashboard sản phẩm)*

Mô tả đề tài nêu đích danh *"bảng tổng hợp doanh thu, lợi nhuận và tỷ lệ hoàn trả theo sản phẩm"*.

| Mã | Câu hỏi | Mã | Giả thuyết | Trạng thái |
|---|---|---|---|---|
| Q4.12 | Trong 2.412 SKU, bao nhiêu SKU thực sự tạo ra lợi nhuận? | **H4.11** | Lợi nhuận tập trung ở thiểu số SKU; một phần danh mục có biên âm ngay cả ngoài đợt khuyến mãi | ⏳ **chưa kiểm định** |
| Q4.13 | Tỷ lệ hoàn trả có tương quan với biên lợi nhuận theo SKU không? | **H4.12** | SKU có tỷ lệ hoàn trả cao làm xói mòn lợi nhuận nhiều hơn mức mà báo cáo doanh thu thể hiện | ⏳ **chưa kiểm định** |

Dữ liệu hỗ trợ: `products` (2.412 SKU × 8 cột, có `category`, `segment`, `price`, `cogs`) ×
`returns` (39.939 dòng, có `return_reason`) × `reviews` (113.551 dòng).

---

### PS5 — Dự báo: hỗ trợ lập kế hoạch

**Problem statement**

> Doanh nghiệp cần dự báo doanh thu để lập kế hoạch bán hàng, ngân sách marketing và chuẩn bị
> nguồn lực. Ràng buộc đặc thù: **toàn bộ các bảng dữ liệu phụ đều dừng ở 2022-12-31**, không bảng
> nào phủ vùng cần dự báo, nên mô hình không được sử dụng bất kỳ biến ngoại sinh nào ngoài các
> biến suy ra từ lịch. Problem: xây dựng mô hình dự báo hoạt động được dưới ràng buộc đó, và được
> đánh giá theo **giá trị hỗ trợ lập kế hoạch** chứ không theo thứ hạng độ chính xác.

| Mã | Câu hỏi |
|---|---|
| Q5.1 | Dưới ràng buộc chỉ dùng biến lịch, độ chính xác đạt được là bao nhiêu? |
| Q5.2 | Nên dự báo Revenue và COGS độc lập, hay dự báo Revenue rồi nhân với tỷ lệ COGS/Revenue? |
| Q5.3 | Mô hình có tái tạo được biên độ của sự kiện tháng 8 năm lẻ không? |

| Mã | Giả thuyết |
|---|---|
| **H5.1** | Mô hình hoá `COGS/Revenue` như một **tỷ lệ** cho kết quả tốt hơn dự báo hai chuỗi độc lập |
| **H5.2** | Ước lượng xu hướng bằng một hằng số CAGR duy nhất là **sai**, vì nó gộp hai chế độ qua đứt gãy 2018 |
| **H5.3** | Mô hình chỉ dùng biến lịch **không tái tạo đủ biên độ** của sự kiện tháng 8 năm lẻ |

**Bằng chứng sơ bộ cho H5.2.** Tài liệu tham khảo dùng CAGR −3,8%/năm. Cùng con số đó được nhúng
cứng vào `sample_submission.csv` của ban tổ chức: `Revenue(2024) = 0,962 × Revenue(2023)` chính
xác, Pearson r = 1,0000, độ lệch chuẩn của tỷ số = 0. Tức file mẫu nộp bài **chính là** một
baseline trung bình mùa vụ × xu hướng, mang sẵn giả định đã biết là sai.

**Bằng chứng sơ bộ cho H5.3.** Tỷ lệ COGS/Revenue thực tế tháng 8 năm lẻ là **1,34**; mô hình của
tài liệu tham khảo chỉ tái tạo ~1,35 lần chênh lệch giữa hai loại năm, tức mất khoảng 40% biên độ
của chính hiệu ứng mà họ đưa vào làm feature.

> **Vai trò của PS5 trong hệ thống.** Đây là hạng mục bắt buộc theo mô tả đề tài
> (*"một mô hình AI được xây dựng để dự báo doanh thu theo ngày hoặc tháng"*). Ngoài chức năng
> lập kế hoạch, nó còn phục vụ PS4: đường dự báo từ mô hình chỉ dùng biến lịch, huấn luyện trên
> những ngày không khuyến mãi, chính là **đường đối chứng** để tính `Promo Uplift %` ở mức chặt
> chẽ hơn phép so sánh tháng liền kề.

---

## 4. Measure — độ đo

**Measure** = một cột **cộng dồn được** tại grain của bảng fact. Không chứa phán đoán kinh doanh,
không chứa phép chia. Đây là lớp nền của Retail Data Warehouse.

**Grain của fact chính:** `fact_order_item` — *một dòng = một sản phẩm trong một đơn hàng*.

| Measure | Công thức | Nguồn | Tính cộng dồn |
|---|---|---|---|
| `quantity` | cột gốc | `order_items` | additive |
| `gross_line_amount` | `quantity × unit_price` | `order_items` | additive |
| `list_line_amount` | `quantity × products.price` | `order_items × products` | additive |
| `cogs_line_amount` | `quantity × products.cogs` | `order_items × products` | additive |
| `discount_amount` | cột gốc | `order_items` | additive |
| `markdown_amount` | `list_line_amount − gross_line_amount` | dẫn xuất | additive |
| `refund_amount` | cột gốc | `returns` | additive |
| `return_quantity` | cột gốc | `returns` | additive |
| `payment_value` | cột gốc | `payments` | additive — **grain đơn hàng**, không phải dòng hàng |
| `order_count` | `COUNT(DISTINCT order_id)` | `orders` | **non-additive** |
| `customer_count` | `COUNT(DISTINCT customer_id)` | `orders` | **non-additive** |
| `inventory_on_hand` | cột gốc | `inventory` | **semi-additive** — cộng theo SP, không cộng theo thời gian |

### Ba điểm bắt buộc phải nêu ở lớp measure

1. **`markdown_amount` là measure mới, và nó tồn tại là vì H1.5 / H2.3.** Dữ liệu có sẵn
   `discount_amount`, nhưng cơ chế giảm giá thật nằm ở khoảng cách giữa `products.price` (niêm
   yết) và `order_items.unit_price` (thực bán) — thứ không có cột nào ghi lại. Không có measure
   này thì đợt lỗ 34% vô hình.
2. **`order_count` và `customer_count` non-additive.** Cộng số đơn theo ngày rồi cộng tiếp theo
   tháng vẫn đúng; nhưng cộng số khách theo ngày rồi cộng theo tháng thì **sai** (khách mua nhiều
   ngày bị đếm lặp). Trong bảng tổng hợp phải khai báo rõ, và ở Tableau phải dùng `COUNTD` /
   `{FIXED : ...}` thay vì `SUM`.
3. **`payment_value` khác grain (H1.2).** Nó ở mức đơn hàng; join thẳng vào `fact_order_item` sẽ
   **nhân bản** giá trị theo số dòng hàng. Tài liệu tham khảo mắc đúng lỗi này (tr.36). Trong DW
   phải tách thành `fact_payment` riêng.

---

## 5. Metric — chỉ số

**Metric** = measure + phép tổng hợp + grain + bộ lọc. Có thể là tỷ lệ, có thể so sánh.
Đây chính là nội dung của **các bảng dữ liệu tổng hợp** nêu trong mô tả đề tài.

| Metric | Công thức | Grain mặc định | Phục vụ |
|---|---|---|---|
| `Gross Revenue` | `Σ gross_line_amount` | ngày | nền — bằng đúng `sales.csv` |
| `Delivered Revenue` | `Σ gross_line_amount WHERE status='delivered'` | ngày | PS2 |
| `Net Revenue` | `Gross Revenue − discount − refund` | ngày | PS2 |
| `Realized Revenue` | `Delivered Revenue − discount(delivered) − refund(delivered)` | ngày | PS2 |
| `COGS` | `Σ cogs_line_amount` | ngày | nền |
| `Gross Margin %` | `(Net Revenue − COGS) / Net Revenue` | ngày/tháng | **trục chính** |
| `COGS Ratio` | `COGS / Gross Revenue` | ngày | PS5 (H5.1) |
| `AOV` | `Gross Revenue / order_count` | ngày | D1 |
| `UPO` | `Σ quantity / order_count` | ngày | D1 |
| `ASP` | `Gross Revenue / Σ quantity` | ngày | D1, D2 |
| `Markdown Depth %` | `Σ markdown_amount / Σ list_line_amount` | ngày/SKU | **D2 — chỉ số mà báo cáo cũ không có** |
| `Discount Rate %` | `Σ discount_amount / Σ gross_line_amount` | ngày | D2, D4 |
| `Cancellation Rate %` | `gross(cancelled) / gross(all)` | tháng | PS2 |
| `Return Rate %` | `Σ refund_amount / Σ gross_line_amount` | tháng/SKU | PS2, D5 |
| `EOM Concentration` | `Σ rev(ngày ≥26) / Σ rev(tháng)` | tháng | D4 |
| `Promo Uplift %` | `(thực tế − đối chứng) / đối chứng` | đợt KM | D2 |
| `Retention Rate` | `% cohort còn mua ở kỳ thứ n` | cohort × kỳ | D3 |
| `RFM Score` | phân vị Recency/Frequency/Monetary | khách hàng | D3 |
| `Forecast MAPE` | `mean(\|ŷ−y\|/y)` | kỳ dự báo | PS5 |

### Hai metric cần giải thích thêm

**`Revenue = order_count × UPO × ASP`** là một **đẳng thức đúng tuyệt đối** trên bộ dữ liệu này
(hệ quả trực tiếp của `CLAUDE.md` §5.1). Đây là phép phân rã chuẩn của luận văn — mọi biến động
doanh thu đều quy được về ba thành phần này, và D1 chính là một lần áp dụng nó.

**`Promo Uplift %` cần một đường đối chứng (counterfactual)**, vì so sánh thẳng "trong đợt vs
ngoài đợt" sẽ lẫn với mùa vụ và với đứt gãy 2018 — D2 đã cho thấy con số gộp không dùng được.
Luận văn dùng hai mức đối chứng, tăng dần về độ chặt:

1. **Đối chứng tháng liền kề trong cùng năm** — giữ cố định chế độ và xu hướng theo đúng nghĩa
   đen, không cần mô hình. Đây là bằng chứng chính của Q4.4.
2. **Đối chứng bằng mô hình calendar-only của PS5** — huấn luyện trên những ngày không khuyến mãi,
   dự báo ngược vào vùng khuyến mãi để ước lượng doanh thu-nếu-không-có-KM.

---

## 6. KPI — chỉ số đánh giá hiệu quả

**KPI** = metric + **mục tiêu** + **ngưỡng** + **chu kỳ** + **người chịu trách nhiệm** +
**hành động khi vi phạm**. Một metric không có ngưỡng và không gắn hành động thì chỉ là con số,
không phải KPI.

> **Giới hạn phương pháp — phải nêu trong luận văn.** Đây là dữ liệu mô phỏng dùng cho mục đích
> nghiên cứu; **không có stakeholder nào cung cấp mục tiêu kinh doanh**. Mọi ngưỡng dưới đây được
> suy ra từ chính lịch sử dữ liệu (đường nền giai đoạn, phân vị), **không phải** mục tiêu do doanh
> nghiệp đặt ra. Đây là giới hạn thật, phải nói thẳng thay vì trình bày như thể có người giao chỉ tiêu.

| # | KPI | Metric nền | Mục tiêu | Cảnh báo | Nghiêm trọng | Chu kỳ | Chủ sở hữu | Hành động khi vi phạm |
|---|---|---|---|---|---|---|---|---|
| K1 | **Biên lợi nhuận gộp** | `Gross Margin %` | ≥ 14,27% (nền trước 2019) | < 12,52% | **< 0%** | tháng | Giám đốc kinh doanh | Rà soát chính sách giá theo phân khúc |
| K2 | **Tỷ lệ đợt KM có lãi** | `Gross Margin %` theo đợt | 100% đợt có margin > 0 | < 100% | có đợt margin < −10% | mỗi đợt | Trưởng marketing | Dừng/thiết kế lại đợt — *hiện Urban Blowout ở −34%* |
| K3 | **Uplift đơn hàng của KM** | `Promo Uplift %` (theo `order_count`, có đối chứng mùa vụ) | ≥ +15% | < +5% | **≤ 0%** | mỗi đợt | Trưởng marketing | KM không kéo thêm khách → cắt ngân sách — *Urban Blowout ở −3,6 đ%* |
| K4 | **Độ sâu markdown** | `Markdown Depth %` | ≤ 10% | > 15% | > 25% | tuần | Quản lý giá | *Bắt được đúng lỗ hổng mà KPI chiết khấu bỏ sót* |
| K5 | **Tỷ lệ hủy đơn** | `Cancellation Rate %` | ≤ 5% | > 8% | > 10% | tháng | Vận hành | *Hiện 9,23% — đang ở vùng cảnh báo* |
| K6 | **Tỷ lệ thực nhận** | `Realized Revenue / Gross Revenue` | ≥ 90% | < 85% | < 80% | tháng | Tài chính | *Hiện **76,19%** (thận trọng: 81,36%) — cả hai đều dưới ngưỡng cảnh báo* |
| K7 | **Tỷ lệ đối soát đạt** | quality gate | **100%** | < 100% | bất kỳ FK/invariant sai | mỗi lần chạy pipeline | Data engineer | Chặn publish dashboard |
| K8 | **Tỷ lệ giữ chân cohort** | `Retention Rate` (kỳ 12) | ≥ mức cohort 2013–2017 | thấp hơn 5 điểm % | thấp hơn 10 điểm % | quý | Trưởng CRM | Rà soát chất lượng kênh thu hút — *phục vụ D3* |
| K9 | **Tỷ lệ hoàn trả theo SKU** | `Return Rate %` theo SKU | ≤ 3,11% (mức toàn hệ thống) | > 5% | > 10% | tháng | Quản lý danh mục | Rà soát SKU theo `return_reason`, cân nhắc loại khỏi danh mục — *phục vụ D5* |

### Ghi chú thiết kế KPI

- **K3 là KPI quan trọng nhất về mặt phát hiện.** K2 (margin của đợt) đã đủ để kết luận Urban
  Blowout lỗ, nhưng K3 mới trả lời được câu *"vậy có đáng lỗ không?"* — và câu trả lời là không,
  vì uplift đơn hàng âm.
- **K4 tồn tại là kết quả của H2.3.** Nếu chỉ có KPI theo `Discount Rate %`, tháng 8 năm lẻ báo
  0,97% — dưới mọi ngưỡng, hoàn toàn "xanh". K4 dựa trên `markdown_amount` báo 28,73%.
  **Cùng một sự kiện, hai measure, hai kết luận trái ngược.**
- **K7 là KPI của chính hệ thống, không phải của kinh doanh.** Nó trả lời câu hỏi *"làm sao biết
  con số trên dashboard đúng?"* — và ngưỡng duy nhất chấp nhận được là 100%. Đã có sẵn hạ tầng:
  `archive/databricks/retail_medallion/src/quality/`.

---

## 7. Bản đồ tổng: Problem → Question → Hypothesis → Measure → Metric → KPI → Dashboard

| Problem | Câu hỏi | Giả thuyết | Measure then chốt | Metric | KPI | Dashboard |
|---|---|---|---|---|---|---|
| **PS1** Retail DW | Q1.1–1.4 | H1.1–1.5 | toàn bộ + phân cấp chiều | — | — | *(tầng nền)* |
| **PS2** Bảng tổng hợp | Q2.1–2.4 | H2.1–2.3 | `refund_amount`, **`markdown_amount`**, `order_status` | `Realized Revenue`, `Markdown Depth %` | K4, K5, K6 | *(tầng nền)* |
| **PS3** Theo dõi | Q3.1–3.3 | H3.1–3.3 | tất cả | toàn bộ bộ KPI | K1–K9 | **Điều hành** |
| **PS4·D1** Đứt gãy 2018 | Q4.1–4.3 | H4.1–4.3 | `quantity`, `gross_line_amount`, `order_count` | `AOV`, `UPO`, `ASP`, `Gross Margin %` | K1 | Điều hành |
| **PS4·D2** Khuyến mãi | Q4.4–4.6 | H4.4–4.6 | **`markdown_amount`** | `Markdown Depth %`, `Promo Uplift %` | K2, K3, **K4** | **Sản phẩm** |
| **PS4·D3** Khách rời đi | Q4.7–4.9 | H4.7–4.8 ⏳ | `customer_count`, `order_count` | `Retention Rate`, `RFM Score` | **K8** | **Khách hàng** |
| **PS4·D4** Cuối tháng | Q4.10–4.11 | H4.9–4.10 | `discount_amount`, `cogs_line_amount` | `EOM Concentration`, `Gross Margin %` | K1 | Điều hành |
| **PS4·D5** Lợi nhuận theo SP | Q4.12–4.13 | H4.11–4.12 ⏳ | `cogs_line_amount`, `refund_amount` | `Gross Margin %`/SKU, `Return Rate %` | K1, **K9** | **Sản phẩm** |
| **PS5** Dự báo | Q5.1–5.3 | H5.1–5.3 | `gross_line_amount`, `cogs_line_amount` | `COGS Ratio`, `Forecast MAPE` | — | Điều hành |
| Xuyên suốt | *"số này có đúng không?"* | — | tất cả | đối soát §5.1 | **K7** | tất cả |

Tổng: **5 problem · 27 câu hỏi · 26 giả thuyết · 12 measure · 19 metric · 9 KPI · 3 dashboard.**

⏳ = **giả thuyết chưa kiểm định.** Bốn giả thuyết H4.7, H4.8, H4.11, H4.12 (thuộc D3 và D5) hiện
mới chỉ xác nhận được rằng **dữ liệu đủ để kiểm định**, chưa chạy kiểm định. 22 giả thuyết còn lại
đều đã có bằng chứng sơ bộ trong tài liệu này. Không được trình bày bốn giả thuyết này ngang hàng
với phần đã kiểm chứng.

---

## 8. Giới hạn của nghiên cứu

### 8.1 Không có mục tiêu do doanh nghiệp giao

Mọi ngưỡng KPI ở §6 suy từ chính lịch sử dữ liệu. Xem ghi chú đầu §6.

### 8.2 `region` là nhãn tổng hợp, không phải vùng miền Việt Nam

Dữ liệu chỉ có ba giá trị **Central / East / West**, không có "North", và các thành phố phía Bắc
(Hà Nội, Hải Phòng, Hạ Long, Lào Cai, Thái Nguyên…) đều được xếp vào "East". Phân bố khách hàng:
East 58.178 · Central 44.286 · West 19.466.

Vì mô tả đề tài đã nêu rõ đây là dữ liệu **mô phỏng**, đây là đặc tính của bộ mô phỏng chứ không
phải khiếm khuyết doanh nghiệp gặp phải. **Cách nêu đúng:** *"mọi phân tích ở cấp region diễn giải
trên nhãn vùng của bộ dữ liệu, không suy rộng ra vùng miền địa lý thực tế của Việt Nam."*
Không viết thành "dữ liệu sai" — sẽ phải bảo vệ một luận điểm không phải luận điểm của mình.

### 8.3 Không kết luận nhân quả ở D4

Xem ghi chú cuối D4 — thiếu dữ liệu chỉ tiêu/hoa hồng nhân viên.

### 8.4 Ràng buộc chi phối mọi lựa chọn feature ở PS5

**Mọi bảng phụ đều dừng ở 2022-12-31.** Không bảng nào phủ vùng dự báo. Feature ngoại sinh dùng
được phải là biến **suy ra từ lịch**: tháng, ngày-trong-tháng, năm chẵn/lẻ, khoảng cách tới cuối
tháng, cờ mùa khuyến mãi… Không thể dùng trực tiếp `web_traffic`, `inventory`, `reviews`… ở thời
điểm tương lai.

### 8.5 Hướng đã cân nhắc và loại khỏi phạm vi

| Hướng | Lý do loại |
|---|---|
| Dự đoán tỷ lệ trả hàng từ nội dung đánh giá | Nghiêng về ML hơn BI; `reviews` chỉ phủ 113.551/646.945 đơn |
| Ảnh hưởng thời gian giao hàng | `shipments` chỉ có 4 cột, không đủ xây câu chuyện |
| Tối ưu độ chính xác dự báo thuần túy | Là đề bài gốc của cuộc thi, không phù hợp hướng hệ thống hỗ trợ quyết định |

---

## 9. Phần việc còn lại

### 9.1 Notebook chứng minh

Theo quy ước §3, mọi con số trong tài liệu này cần một cell chạy lại được. Hiện **chưa có**.

Đề xuất: notebook mới `business_problem_design.ipynb`, nhánh riêng (`docs/problem-design`),
do myuyen sở hữu — không đụng vào 4 notebook đang có, đúng quy tắc *một notebook một chủ*.
Cấu trúc theo đúng §3 của tài liệu này: mỗi PS một section, mỗi giả thuyết một cell.

Bốn cell **bắt buộc**, vì đó là những chỗ mà cách tính ngây thơ cho kết quả sai:

| Cell | Nội dung | Sai lầm nó phòng tránh |
|---|---|---|
| C1 | Kiểm tra phụ thuộc hàm của chiều địa lý | Coi `district` là một cấp phân cấp hợp lệ |
| C2 | Phân rã Laspeyres giá/mix trên rổ SKU chung | Đọc ASP +30,2% thành "tăng giá" |
| C3 | Uplift KM bằng đối chứng tháng liền kề trong cùng năm | Gộp năm chẵn/lẻ qua đứt gãy 2018 |
| C4 | Thác nước doanh thu theo `order_status`, kiểm tra giao nhau giữa các khoản trừ | Trừ hai lần `returned` và `refund_amount` |

### 9.2 Tầng gold còn thiếu

Pipeline hiện có bronze → silver (19 bảng 3NF) + quality gate, **chưa có `src/gold/`**.
Toàn bộ measure ở §4 và metric ở §5 cần được hiện thực hóa ở tầng đó — đây chính là *"các bảng
dữ liệu tổng hợp"* nêu trong mô tả đề tài. `docs/star_schema.md` đã thiết kế xong nhưng chưa
triển khai.

### 9.3 Cần cập nhật cho khớp tên đề tài

`CLAUDE.md` §1 và `README.md` hiện mô tả project là bài toán *"dự báo `Revenue` và `COGS` theo
ngày"*. Với tên đề tài hiện tại, dự báo là **PS5 — một trong năm problem**, không phải trục.
Hai file này cần sửa lại, và nên sửa cùng commit với tài liệu này: `CLAUDE.md` điều hướng phiên
làm việc của cả hai thành viên, để lệch sẽ khiến công việc tiếp theo bị đẩy về hướng cũ.
