# Đề cương khóa luận — bài toán business và cấu trúc đề tài

**Bản 1 · 07/09/2026 · trình giảng viên hướng dẫn**

Tài liệu này chốt **một bài toán business duy nhất** và dựng đề tài từ đó.

> **Quan hệ với hai tài liệu trước.** File này **thay thế phần khung** của
> `problem_statement.md` §2 và `scope_statement.md` §2/§4/§5. Phần còn lại của hai file đó vẫn
> dùng được và được trỏ tới ở dưới: `problem_statement.md` §4–§6 (measure/metric/KPI) và
> `problem_to_kpi_review.md` (toàn bộ bằng chứng số). Chưa xóa file nào — việc hạ cấp hay lưu trữ
> để người viết quyết định.

---

## 1. Bài toán business tổng quát

**Bản một câu (dùng cho slide):**

> Doanh nghiệp quyết định giá và khuyến mãi dựa trên những con số mà chính hệ thống báo cáo của
> nó tính sai — và sai theo hướng làm chương trình khuyến mãi trông rẻ hơn, hiệu quả hơn thực tế.

**Bản chuẩn (phần Đặt vấn đề):**

> **Bối cảnh.** Doanh nghiệp thời trang thương mại điện tử, 646.945 đơn hàng giai đoạn 2012–2022,
> hoạt động được ghi nhận rải rác trong 14 bảng dữ liệu tách biệt. Không tồn tại một tầng định
> nghĩa chỉ số chung: mỗi báo cáo tự nối và tự tính lại từ dữ liệu thô.
>
> **Quan sát mâu thuẫn.** Cùng một chỉ số mang cùng một tên cho ra những giá trị khác nhau tùy
> vào bảng nguồn và bộ lọc mà báo cáo tình cờ chọn. Chênh lệch đó **không phải sai số làm tròn** —
> nó đủ lớn để **đảo ngược kết luận quản trị**. Độ sâu chiết khấu là 12,0% hay 31,6% tùy chỗ đặt
> mẫu số. Khách khuyến mãi mua nhiều hơn hay ít hơn khách thường tùy định nghĩa chữ "khuyến mãi".
>
> **Quyết định đang bị kẹt.** Bộ phận tăng trưởng chọn độ sâu chiết khấu mỗi quý và đánh giá hiệu
> quả bằng mức tăng doanh thu quan sát được trong kỳ chiến dịch. Với các định nghĩa đang dùng,
> đại lượng đó **gần như luôn dương** — nên không có cấu hình nào của chương trình khuyến mãi
> bị hệ thống báo cáo đánh giá là lỗ.
>
> **Hệ quả đo được.** Tính trên **số tiền khách thực trả**, 69,8% đơn có khuyến mãi được bán
> **dưới giá vốn** (nhóm không khuyến mãi: 0,17%). Chương trình phủ 38,4% số đơn. Báo cáo nội bộ
> không thể phát hiện điều này, vì nó chỉ đọc **một trong hai lớp chiết khấu** được áp lên giá.
>
> **Khoảng trống.** Chưa tồn tại tầng định nghĩa chỉ số đứng giữa dữ liệu thô và báo cáo — nơi
> khai báo dứt khoát mỗi chỉ số lấy mức giá nào làm mẫu số, lọc trạng thái đơn nào, ở hạt nào.
> Không có tầng đó thì mọi dashboard, mọi mô hình dự báo và mọi kết luận nhân quả xây bên trên
> đều thừa hưởng sai lệch mà không ai truy được về nguồn.

### 1.1 Cơ chế: chiết khấu hai lớp

Chiết khấu được áp **hai lần** lên cùng một dòng hàng:

| Lớp | Công thức | Đọc được ở đâu |
|---|---|---|
| 1 | `unit_price = price × (1 − d)` | ẩn trong `order_items.unit_price` |
| 2 | `discount_amount = d × quantity × unit_price` | cột `discount_amount`, hiện rõ |

Độ sâu thực so với giá niêm yết là `1 − (1 − d)²`. Báo cáo chỉ đọc lớp thứ hai nên **báo thiếu
khoảng 2,6 lần** (trung vị 12,0% thay vì 31,6%). Đây là phát hiện làm thay đổi công thức của bốn
chỉ số trong bài.

---

## 2. Vì sao đây là bài toán đúng để làm khóa luận

### 2.1 Trả lời thẳng phản biện của chính mình

`scope_statement.md` §1 đã viết: *"phần có giá trị nghiên cứu không nằm ở kiến trúc kho dữ liệu —
đó là công việc kỹ thuật đã có lời giải chuẩn."* Câu đó **đúng**, và đề cương này không phủ nhận.

Đóng góp của khóa luận **không phải** "xây một kho dữ liệu". Kho dữ liệu là hạ tầng, và đúng là
đã có lời giải chuẩn. Đóng góp là:

> **Định lượng được rằng *lựa chọn định nghĩa chỉ số* là một quyết định có hậu quả kinh doanh
> đo được — và đưa ra quy trình kiểm tra độ nhạy của một định nghĩa trước khi dùng nó để kết luận.**

Khác biệt nằm ở chữ *định lượng*. Nói "định nghĩa chỉ số thì quan trọng" là điều hiển nhiên, không
phải nghiên cứu. Nói "đây là sáu lựa chọn định nghĩa, mỗi lựa chọn có một độ lớn đo được, và **ba
trong sáu** làm kết luận kinh doanh **đổi dấu**" thì là một kết quả thực nghiệm, có phương pháp,
và khái quát được sang bộ dữ liệu khác.

### 2.2 Vì sao KHÔNG chọn "đo tác động gia tăng của khuyến mãi" làm trục

`scope_statement.md` đề xuất trục là counterfactual ROI. Đề cương này **chuyển hướng đó ra khỏi
trung tâm**, vì hai lý do độc lập, mỗi lý do đã đủ:

**(a) Không định danh được — thất bại positivity.** Lịch khuyến mãi *chính là* lịch. 46,74% số
ngày 2013–2022 nằm trong một cửa sổ chiến dịch, phân bố cực lệch:

| T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | T10 | T11 | T12 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 8% | 50% | 47% | 57% | **0%** | 27% | 74% | 53% | **100%** | 4% | 43% | **100%** |

Tháng 9 và tháng 12 phủ 100% — **không tồn tại** quan sát đối chứng ở hai tháng đó. Tập huấn luyện
"kỳ không chiến dịch" thực tế chỉ còn T5, T10 và đầu T1, rồi phải ngoại suy sang T9 và T12. Phơi
nhiễm khuyến mãi và mùa vụ **không tách được về nguyên tắc**. Đây không phải vấn đề độ chính xác
của baseline — cải thiện mô hình không sửa được nó.

**(b) Dữ liệu là mô phỏng, và bộ sinh có quy luật cơ học.** Tỷ số `unit_price / price` khớp đúng
`1 − discount_value` tới **bốn chữ số thập phân ở cả sáu bậc chiết khấu**. `bounce_rate` đứng yên
trong dải 0,0044–0,0045 suốt mười năm. Nghĩa là phản ứng hành vi trước khuyến mãi trong bộ dữ liệu
này **là tham số do người viết bộ sinh đặt ra**, không phải hành vi người tiêu dùng. Một ước lượng
nhân quả ở đây đo lại **bộ mô phỏng**, không đo nền kinh tế. Trước hội đồng, câu hỏi *"quá trình
sinh dữ liệu là gì?"* sẽ không có câu trả lời phòng thủ được.

**Ngược lại, bài toán đo lường miễn nhiễm với cả hai vấn đề trên.** Khẳng định *"sáu định nghĩa
của cùng một chỉ số cho ra các giá trị khác nhau, và chênh lệch đó đảo ngược kết luận"* là một
phát biểu **về bản thân các định nghĩa**, đúng bất kể dữ liệu được sinh ra thế nào. Đó là lý do
nó đứng vững còn kết luận nhân quả thì không.

### 2.3 Khoảng trống so với tài liệu tham khảo

`docs/references/[Reading]-Retail-Analytics-Forecasting.pdf` là lời giải chính thức cho đúng bộ dữ liệu này.
Suốt 81 trang **không xuất hiện một chỉ số lợi nhuận nào** — `COGS` chỉ được xử lý như chuỗi thời
gian thứ hai cần dự báo, không bao giờ như thành phần của biên lợi nhuận. Cả 5 dashboard đều truy
vấn trực tiếp từ dữ liệu thô, không có tầng định nghĩa ở giữa; tài liệu phải tự cảnh báo nguy cơ
nhân bản `payment_value` khi join (tr.36).

Đề tài này lấp đúng chỗ đó: **không phải làm dashboard đẹp hơn, mà là xây tầng nền khiến các
dashboard không thể mâu thuẫn nhau — rồi chứng minh bằng số rằng nếu thiếu tầng đó thì mâu thuẫn
là bao nhiêu.**

---

## 3. Bằng chứng: sáu bẫy đo lường

Mỗi dòng dưới đây là **một lựa chọn định nghĩa**, không phải một lỗi dữ liệu. Cột cuối cho biết
kết luận kinh doanh có đổi dấu hay không.

| # | Lựa chọn định nghĩa | Giá trị A | Giá trị B | Đổi dấu? | Mã |
|---|---|---|---|---|---|
| 1 | Mẫu số độ sâu chiết khấu: giá niêm yết hay giá sau lớp 1 | **31,6%** | 12,0% | không, nhưng lệch 2,6× | A2 |
| 2 | "Khuyến mãi" = đơn đầu tiên hay **bất kỳ** đơn nào | 4,79 / 8,19 | 9,00 / 1,76 | **CÓ** | C4 |
| 3 | Có khống chế cohort năm đơn đầu hay không | −41% | **−3,6%** | **CÓ** (nghịch lý Simpson) | C5 |
| 4 | Thước đo giá khi so AOV promo/non-promo | −20,5% | **−2,0%** | **CÓ** (hiệu ứng giá, không phải hành vi) | B8 |
| 5 | `stockout_flag` nhị phân hay `stockout_days` liên tục | 67,34% | **3,87%** | không, nhưng thổi phồng 17× | B6, C3 |
| 6 | Mẫu SKU: toàn danh mục hay tập từng bán | 2.412 | **1.598** | không, nhưng 33,7% là hàng chết | C7 |

Ba mức giá phải gọi tên rõ (năm 2022):

| Mức giá | Công thức | Giá trị | Ghi chú |
|---|---|---|---|
| Niêm yết | `Σ quantity × products.price` | 1.234.360.532 | +5,52% |
| Sau lớp 1 | `Σ quantity × unit_price` | **1.169.748.832** | = `sales.csv` Revenue, khớp **chính xác** |
| Thực trả | `− discount_amount` = `payment_value` | 1.115.307.096 | −4,65% |
| Bỏ đơn `cancelled` | | 1.061.061.965 | −9,29% |

Thêm hai điểm về chính **target** của bài dự báo:

- `payment_value == Σ(quantity × unit_price) − Σ discount_amount` khớp **646.945/646.945 đơn = 100%**.
  Chiết khấu lớp hai thực sự được trừ vào tiền khách trả (A1).
- `sales.csv` **bao gồm 59.462 đơn `cancelled`** (9,19%). "Doanh thu" trong bài toán này **≠**
  "doanh thu đã thực hiện" (B4). Đây không phải lỗi để đi sửa target — công thức tái tạo `sales.csv`
  đã chốt ở `CLAUDE.md` §5.1 — mà là một sự thật **bắt buộc phải khai báo** khi định nghĩa Revenue.

Và một điểm về nguồn dữ liệu bị loại:

- `web_traffic` **độc lập** với bộ sinh đơn hàng: tương quan trên sai phân ngày = **+0,0105**,
  `bounce_rate` bất động 0,0044–0,0045 suốt 10 năm (C1). Kết luận "sụp đổ chuyển đổi −71%" chỉ là
  hai chuỗi rời nhau. Phân rã `ln(đơn) = ln(phiên) + ln(CVR)` là **đồng nhất thức**, đúng với mọi
  bộ số, sai số 1,78e−15 — không có giá trị chẩn đoán (C2).

---

## 4. Từ bài toán → đề tài: bốn lớp

| Lớp | Nội dung | Vai trò |
|---|---|---|
| **L0** | Quyết định đang bị kẹt: chọn độ sâu chiết khấu mỗi quý | Bối cảnh |
| **L1** | **Tầng ngữ nghĩa (gold)** — mỗi measure khai báo mẫu số, bộ lọc, hạt, định nghĩa promo | **Đóng góp kỹ thuật** |
| **L2** | **Quy trình kiểm tra độ nhạy định nghĩa** — sáu bẫy ở §3, mỗi bẫy một độ lớn đo được | **Đóng góp phương pháp** |
| **L3** | **Kinh tế khuyến mãi khi đo đúng** — mô tả, không nhân quả | Kết quả ứng dụng |
| **L4** | **Giới hạn định danh** — vì sao ROI khuyến mãi không trả lời được từ dữ liệu này | **Kết quả nghiên cứu** |

### L1 — Tầng ngữ nghĩa

Hạ tầng đã có: bronze (14 CSV) → silver (19 bảng 3NF) + quality gate, ở `archive/databricks/retail_medallion/`,
với nhánh chạy local là `scripts/build/build_silver.py`. Tầng gold (star schema theo `docs/star_schema.md`) đã dựng
bằng dbt trên PostgreSQL local, ở `retail_dbt/` (xem `docs/dwh_roadmap.md`, cập nhật 2026-09-26). **Chưa có**
tầng metric: toàn bộ measure ở `problem_statement.md` §4 và metric ở §5 cần được hiện thực hóa trên các bảng
marts đó. Đây chính là *"các bảng dữ liệu tổng hợp"* nêu trong tên đề tài.

Ràng buộc thiết kế rút ra từ §3: **mỗi measure bắt buộc khai báo bốn thứ** — mức giá ở mẫu số, bộ
lọc `order_status`, hạt, và định nghĩa "promo" (đơn đầu hay bất kỳ đơn nào). Thiếu một trong bốn
thì cùng một tên gọi cho ra nhiều giá trị.

### L2 — Quy trình kiểm tra độ nhạy

Phần khái quát được của khóa luận. Với mỗi chỉ số, biến thiên có hệ thống bốn chiều khai báo ở
trên, đo độ phân tán của kết quả, và đánh dấu những chỉ số mà **kết luận đổi dấu**. §3 là kết quả
áp dụng quy trình này lên sáu chỉ số của bộ dữ liệu hiện tại.

### L3 — Kinh tế khuyến mãi, mô tả

Đo đúng rồi thì bức tranh là: 38,4% đơn có khuyến mãi · độ sâu thực trung vị 31,6% so với giá niêm
yết · **69,8% đơn khuyến mãi bán dưới giá vốn** trên tiền thực trả · giỏ hàng gần như không đổi
(5,01 so với 4,94 unit/đơn, +1,4%).

**Đây là phát biểu kế toán, không phải phát biểu nhân quả** — nó nói *"tiền đã nhận thấp hơn giá
vốn trên 69,8% số đơn khuyến mãi"*, không nói *"khuyến mãi gây ra thua lỗ"*. Vì vậy nó đứng vững
trước cả hai phản biện ở §2.2.

Biên lợi nhuận gộp theo năm là **răng cưa chẵn/lẻ**, không suy giảm đơn điệu:

```
2012 20,8% | 2013 11,5% | 2014 15,9% | 2015 11,9% | 2016 15,4% | 2017 11,3%
2018 16,6% | 2019 11,6% | 2020 16,0% | 2021  9,8% | 2022 12,8%
```

Năm lẻ luôn thấp hơn năm chẵn kề bên, khớp với chu kỳ 2 năm của *Urban Blowout* (`CLAUDE.md` §5.6).
**2022 (12,8%) còn cao hơn 2013 (11,5%)** — không có "biên co dần". Mốc 2012 = 20,8% là **năm cụt**
(từ 2012-07-04) và chưa hề có khuyến mãi; không dùng làm điểm đầu của bất kỳ đường xu hướng nào.

> **Không dùng con số CAGR −3,80%/năm.** Nó đúng về số học nhưng gộp hai chế độ qua đứt gãy cuối
> 2018, nên vô nghĩa về diễn giải (`CLAUDE.md` §6). Ở đâu cần phát biểu xu hướng thì dùng bảng
> răng cưa trên.

### L4 — Giới hạn định danh, coi như một kết quả

Bảng phủ ở §2.2(a) cộng bằng chứng bộ sinh cơ học cho một kết luận có thể phát biểu thành định lý
thực nghiệm: **câu hỏi ROI mà doanh nghiệp muốn trả lời không trả lời được từ dữ liệu doanh nghiệp
đang thu thập.** Phần này chỉ ra cụ thể cần bổ sung **đo đạc gì** thì mới trả lời được — nhóm giữ
lại (holdout) không nhận khuyến mãi, ngẫu nhiên hóa độ sâu chiết khấu, và ghi nhận đối chứng ở cấp
từng chiến dịch thay vì cấp quý.

Năng lực chỉ ra giới hạn của dữ liệu, kèm chẩn đoán định lượng vì sao, là một kết quả nghiên cứu
đàng hoàng — và an toàn hơn nhiều so với việc báo cáo một ước lượng nhân quả không định danh được.

### Dự báo nằm ở đâu?

Bài dự báo `Revenue`/`COGS` theo ngày (đề bài gốc Datathon, hiện là nội dung trên `main`) trở
thành **một dịch vụ của tầng L1**, không phải trục. Ràng buộc chi phối: mọi bảng phụ dừng ở
2022-12-31, nên feature ngoại sinh phải là biến **suy ra từ lịch** (`CLAUDE.md` §5). Giữ nguyên
tám kết luận đã chốt ở `CLAUDE.md` §5 làm nền cho phần này.

---

## 5. Câu hỏi nghiên cứu và giả thuyết

**RQ trung tâm.** Lựa chọn định nghĩa chỉ số ảnh hưởng tới kết luận quản trị ở mức độ nào, và một
tầng ngữ nghĩa khai báo tường minh loại bỏ được bao nhiêu phần của ảnh hưởng đó?

| Mã | Giả thuyết | Kiểm định | Trạng thái |
|---|---|---|---|
| **H1** | Tồn tại chỉ số mà chỉ đổi một chiều khai báo cũng làm kết luận **đổi dấu** | Liệt kê biến thể, so dấu | **đã đúng** — 3/6 ở §3 |
| **H2** | Trên tiền thực trả, tỷ lệ đơn khuyến mãi dưới giá vốn cao hơn nhóm không khuyến mãi ở mức có ý nghĩa vận hành | So tỷ lệ, bootstrap CI | **đã đúng** — 69,8% vs 0,17% |
| **H3** | Chênh lệch AOV promo/non-promo chủ yếu là hiệu ứng **giá**, không phải thay đổi hành vi giỏ hàng | Phân rã giá/lượng trên rổ SKU chung | **đã đúng** — giỏ +1,4% |
| **H4** | Tác động gia tăng của khuyến mãi **không định danh được** trên bộ dữ liệu này | Bảng phủ + kiểm tra overlap | **đã đúng** — §2.2(a) |

Bốn giả thuyết đều đã có bằng chứng số; phần việc còn lại là chuyển sang notebook (§7).

---

## 6. Phạm vi

| Nhánh | Vai trò | Quyết định |
|---|---|---|
| **L1 + L2 — tầng ngữ nghĩa và kiểm tra độ nhạy** | **Chương trung tâm** | giữ |
| L3 — kinh tế khuyến mãi (mô tả) | Chương ứng dụng | giữ |
| L4 — giới hạn định danh | Chương kết quả âm | giữ |
| Dự báo `Revenue`/`COGS` | Dịch vụ của L1 | giữ, hạ cấp |
| Vòng đời khách khuyến mãi | Ví dụ cho bẫy #2 và #3 ở §3 | giữ, **chỉ như case study đo lường** |
| Kênh thu hút khách | Ví dụ cho bẫy first-touch/last-touch (20,01% khớp, mức ngẫu nhiên 16,7%) | giữ, thu hẹp |
| Hết hàng gây mất doanh thu | **Đã loại** — case study lỗi **nhị phân hóa** (bẫy #5) | loại, giữ làm ví dụ |
| Lưu lượng web giải thích doanh thu | **Đã loại** — hai chuỗi độc lập (C1, C2) | loại, giữ làm ví dụ |
| Ước lượng ROI khuyến mãi bằng counterfactual | **Đã loại** — §2.2 | loại, thành L4 |

Hai nhánh bị loại cuối cùng **không bị xóa** — chúng trở thành ví dụ trong L2, đúng vai trò:
mỗi cái minh họa một bẫy đo lường cụ thể.

---

## 7. Hạn chế và phần việc còn lại

### Hạn chế

- **Dữ liệu là mô phỏng** (VinDatathon 2026), đơn vị tiền không xác định → ưu tiên tỷ lệ và thứ
  hạng hơn giá trị tuyệt đối. Đây cũng chính là lý do trục nhân quả bị loại (§2.2b).
- **Không có mục tiêu do doanh nghiệp giao** → mọi ngưỡng KPI suy từ chính lịch sử dữ liệu.
- **`region` là nhãn tổng hợp**, chỉ có Central/East/West, không có "North"; các thành phố phía Bắc
  xếp vào "East". Mọi phân tích cấp region diễn giải trên nhãn vùng của bộ dữ liệu, **không** suy
  rộng ra vùng miền địa lý Việt Nam.
- **Không có dữ liệu chi phí marketing** → so sánh ROI giữa kênh chỉ là so sánh tương đối.
- **Chỉ có sáu mức chiết khấu rời rạc** ứng với sáu chiến dịch → không ngoại suy ngoài dải quan sát.

### Trạng thái chứng minh — điểm phải nêu rõ

Mọi con số trong tài liệu này tái lập được bằng:

```bash
python scripts/verify/verify_problem_to_kpi.py
```

Mã số trong ngoặc ở các mục trên (A1, A2, A3a, B1–B9, C1–C7) trùng với mã script in ra; toàn bộ
đã chạy và khớp trong ngưỡng 2%.

**Nhưng script không phải notebook.** Theo quy ước `CLAUDE.md` §3, mỗi khẳng định trong `.md` phải
có **một cell chạy lại được** trong notebook tương ứng. Vì vậy:

> **Chưa con số nào trong tài liệu này đủ điều kiện đưa vào `CLAUDE.md` §5.**

### Việc còn lại

| # | Việc | Ghi chú |
|---|---|---|
| 1 | Tạo `business_problem_design.ipynb` | Notebook chứng minh cho tài liệu này. Bốn cell bắt buộc C1–C4 đã đặc tả ở `problem_statement.md` §9.1 |
| 2 | Hiện thực hóa `src/gold/` | L1. Thiết kế đã xong ở `docs/star_schema.md` |
| 3 | Cập nhật `CLAUDE.md` §1 và `README.md` | **Chỉ sau khi giảng viên chốt** — hiện hai file mô tả project là bài toán dự báo |
| 4 | Cập nhật `CLAUDE.md` §3 và `docs/README.md` | §3 liệt kê 4 notebook, thực tế có 10 |
| 5 | Gán chủ notebook trong `README.md` | Bảng "Ai giữ file nào" còn trống ô thành viên thứ hai |

---

## 8. Về tên đề tài

**Đề nghị giữ nguyên tên hiện tại:**

> *Xây dựng hệ thống hỗ trợ ra quyết định kinh doanh cho doanh nghiệp thời trang thương mại điện
> tử dựa trên Retail Data Warehouse*

Với khung ở §4, tên này **đã chính xác** — không cần đổi. "Hệ thống hỗ trợ ra quyết định" chính là
L1 + L2; "Retail Data Warehouse" chính là hạ tầng bronze→silver→gold đã có. Điều `scope_statement.md`
§1 lo ngại — rằng kiến trúc kho dữ liệu không đủ giá trị nghiên cứu — được xử lý ở §2.1: đóng góp
nằm ở **L2**, không ở kiến trúc.

Nếu cần làm rõ hơn trọng tâm, có thể thêm **phụ đề** thay vì đổi tên:

> *…: tầng định nghĩa chỉ số và ứng dụng vào đánh giá hiệu quả chương trình khuyến mãi*

---

## 9. Ba điểm xin ý kiến thầy/cô

1. **Trọng tâm là tầng đo lường, không phải nhân quả.** Em xin chuyển câu hỏi *"khuyến mãi có tạo
   doanh thu gia tăng không"* ra khỏi trung tâm, vì trên bộ dữ liệu này nó **không định danh được**
   (tháng 9 và 12 phủ khuyến mãi 100%, không có đối chứng) và vì dữ liệu là mô phỏng với bộ sinh
   cơ học. Thầy/cô thấy việc trình bày sự bất khả này **như một kết quả** (L4) có được chấp nhận
   không, hay hội đồng sẽ kỳ vọng phải có một ước lượng nhân quả?

2. **Độ sâu của đóng góp phương pháp.** Quy trình kiểm tra độ nhạy định nghĩa (L2) với sáu chỉ số
   đã đo, ba trong đó đổi dấu kết luận — mức đó đã đủ cho khóa luận ở bậc này chưa, hay cần mở rộng
   thành một khung hình thức hơn (ví dụ phát biểu thành bộ tiêu chí kiểm định cho mọi measure)?

3. **Hai nhánh bị loại.** Hết hàng (lỗi nhị phân hóa) và lưu lượng web (hai chuỗi độc lập) — nên
   giữ trong luận văn như ví dụ minh họa cho L2, hay cắt bớt để tập trung?

---

*Nguồn bằng chứng: `scripts/verify/verify_problem_to_kpi.py` · `docs/problem_to_kpi_review.md` ·
`CLAUDE.md` §5. Chi tiết measure/metric/KPI: `docs/problem_statement.md` §4–§6.*
