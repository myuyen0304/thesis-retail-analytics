# Problem statement tham khảo — Hiệu suất doanh thu theo dòng thời gian

> **Trạng thái: bản tham khảo, chưa có notebook chứng minh** (quy ước §3 `CLAUDE.md`).
> Không có con số mới. Mọi con số đều dẫn lại từ `CLAUDE.md` §5 hoặc `docs/problem_statement.md`, ghi nguồn ngay tại chỗ.

**Phạm vi:** đơn hàng có `order.order_date` từ 2012-07-04 đến 2022-12-31.
**Dữ liệu:** 19 bảng Silver trong `silver/` (thiết kế ở `docs/normalized_schema.md`).

---

## 1. Big problem được chia thành 4 tầng, 5 câu hỏi

"Hiệu suất doanh thu theo dòng thời gian" là câu hỏi quá rộng để trả lời một lần. Tài liệu này chia nó thành 4 tầng. **Tầng sau dùng kết quả của tầng trước.**

```text
BIG PROBLEM: Hiệu suất doanh thu theo dòng thời gian
│
├─ Tầng 0. Đo đúng doanh thu      → PS1 Mỗi năm, mỗi tháng công ty thực thu bao nhiêu tiền?
│
├─ Tầng 1. Trend (xu hướng)        → PS2 Doanh thu tăng hay giảm qua từng năm, giai đoạn nào đổi hướng?
│
├─ Tầng 2. Pattern (lặp theo lịch) → PS3 Doanh thu dồn vào tháng nào trong năm, ngày nào trong tháng?
│
└─ Tầng 3. Drivers (nguyên nhân)
     ├─ PS4 Doanh thu mỗi năm thay đổi vì số đơn, số món mỗi đơn, hay giá mỗi món?
     └─ PS5 Nhóm nào đóng góp nhiều nhất vào mức tăng / giảm mỗi năm?
          ├─ Ngành hàng  (product_model.category)
          ├─ Khu vực     (city.region)
          └─ Khách hàng  (số khách mua, số đơn mỗi khách, customer.acquisition_channel)
```

| Tầng | PS | Câu hỏi | Trả lời xong thì biết |
|---|---|---|---|
| 0. Đo đúng | **PS1** | Mỗi năm, mỗi tháng công ty **thực thu** bao nhiêu tiền? | Con số doanh thu đúng, dùng làm nền cho các tầng sau |
| 1. Trend | **PS2** | Doanh thu **tăng hay giảm** qua từng năm, giai đoạn nào đổi hướng? | Các giai đoạn tăng / giảm / đi ngang và điểm đổi hướng |
| 2. Pattern | **PS3** | Trong một năm, doanh thu **dồn vào những tháng nào**; trong một tháng, dồn vào **những ngày nào**; nhịp đó có lặp lại mỗi năm không? | Phần lên xuống do lịch, để không nhầm với biến động thật |
| 3. Drivers | **PS4** | Doanh thu mỗi năm thay đổi so với năm trước là do **số đơn**, **số món mỗi đơn**, hay **giá mỗi món**? | Nguyên nhân bên trong của mọi đợt tăng / giảm |
| 3. Drivers | **PS5** | **Ngành hàng nào, khu vực nào, nhóm khách nào** đóng góp nhiều nhất vào mức tăng / giảm doanh thu mỗi năm? | Nhóm nào đẩy lên, nhóm nào kéo xuống |

**Các PS hỏi cho mọi năm, không chỉ cho 2018.** Đứt gãy 2018 là một *phát hiện* đã có (`CLAUDE.md` §5.2), nên chỉ xuất hiện như ví dụ nổi bật trong kết quả, không nằm trong câu hỏi. Nhờ vậy, cùng một bảng trả lời được cả "năm 2014 thay đổi vì đâu" lẫn "năm 2019 thay đổi vì đâu".

**Ranh giới giữa Tầng 1 và Tầng 2.** Trend là **hướng đi dài hạn**, gồm cả đứt gãy 2018. Pattern chỉ là những gì **lặp lại theo lịch**. Đứt gãy 2018 chỉ xảy ra một lần nên thuộc Trend, không bàn lại ở Pattern.

Cả 5 PS đều đo **doanh thu**. Lợi nhuận và khuyến mãi không tách thành PS riêng (xem mục 4).

### Hai định nghĩa dùng chung

| Tên | Cách tính | Dùng ở |
|---|---|---|
| **Doanh thu ghi nhận** | Tổng `order_item.quantity × order_item.unit_price` của **mọi** đơn, kể cả đơn bị hủy. Bằng đúng `sales.csv` (`CLAUDE.md` §5.1) | PS2–PS5 |
| **Doanh thu thực tế** | Chỉ tính đơn đã giao (`order.order_status = 'delivered'`), rồi trừ `order_item.discount_amount` | PS1 |

Ghi chú:
- Đơn `delivered` không phát sinh hoàn tiền (`docs/problem_statement.md`, thác nước H2.2), nên không cần trừ `refund_amount` trong doanh thu thực tế.
- PS2–PS5 dùng doanh thu ghi nhận vì nó phủ đủ mọi đơn và khớp đẳng thức ở PS4. PS1 cho biết mỗi năm con số này cao hơn thực tế bao nhiêu.

---

## 2. Năm problem statement

## Tầng 0 — Đo đúng doanh thu

### PS1. Mỗi năm, mỗi tháng công ty thực thu bao nhiêu tiền?

**1. Problem statement**
Con số "doanh thu" hiện có trong `sales.csv` cộng cả đơn **bị hủy**, đơn **bị trả lại**, và **chưa trừ chiết khấu**. Tính gộp 2012–2022, con số này là **16,43 tỷ** nhưng doanh thu thực tế chỉ **12,52 tỷ**, tức **76,19%** (`docs/problem_statement.md` H2.2, K6), thấp hơn con số đang báo cáo khoảng **23,8%** (gần một phần tư). Tách theo từng năm, tỷ lệ này chỉ dao động 73–80%, nên năm nào cũng bị báo cao hơn thực tế.

**2. Mục tiêu**
Có bảng **doanh thu thực tế theo từng năm và từng tháng** từ 2012 đến 2022. Với mỗi năm, chỉ ra phần chênh so với doanh thu ghi nhận nằm ở đâu: đơn hủy, đơn trả, đơn chưa giao xong, hay chiết khấu.

**3. Yêu cầu phân tích**
1. Tính doanh thu ghi nhận theo năm.
2. Tính riêng từng khoản bị trừ theo năm:
   - tiền hàng của đơn `cancelled`;
   - tiền hàng của đơn `returned`;
   - tiền hàng của đơn chưa giao xong (`created`, `paid`, `shipped`);
   - tổng chiết khấu.
3. Lấy doanh thu ghi nhận trừ các khoản trên để ra doanh thu thực tế theo năm, rồi theo tháng.
4. Vẽ hai đường (ghi nhận và thực tế) trên cùng một biểu đồ theo năm. Xem khoảng cách giữa hai đường có đổi theo thời gian không.

**4. Measure → Metric → KPI**

| Measure | Bảng tham gia | Cột |
|---|---|---|
| Tính tổng doanh thu ghi nhận | `order_item`, `order` | `quantity`, `unit_price`, `order_date` |
| Tính tổng tiền hàng theo từng trạng thái đơn | `order_item`, `order` | `quantity`, `unit_price`, `order_status`, `order_date` |
| Tính tổng chiết khấu | `order_item`, `order` | `discount_amount`, `order_date` |
| Tính tổng doanh thu thực tế (đơn đã giao, sau chiết khấu) | `order_item`, `order` | `quantity`, `unit_price`, `discount_amount`, `order_status`, `order_date` |

| Metric | Cách tính |
|---|---|
| Doanh thu thực tế theo năm / tháng | Tổng doanh thu thực tế (đơn đã giao, sau chiết khấu), gom theo năm / tháng của `order_date` |
| Tỷ lệ hủy đơn theo năm | Tiền hàng đơn `cancelled` ÷ doanh thu ghi nhận |
| Tỷ lệ chiết khấu theo năm | Tổng chiết khấu ÷ doanh thu ghi nhận |

| KPI | Cách đọc |
|---|---|
| **Tỷ lệ thực thu** = doanh thu thực tế ÷ doanh thu ghi nhận | Càng gần 100% càng tốt. Gộp 2012–2022 hiện là 76,19% (`docs/problem_statement.md` K6); từng năm 73–80% |
| **Tăng trưởng doanh thu thực tế so với năm trước (%)** | Dương là tăng, âm là giảm |
| **Tỷ lệ hủy đơn** | Càng thấp càng tốt. Hiện 9,23% (`docs/problem_statement.md` K5) |

---

## Tầng 1 — Trend

### PS2. Doanh thu tăng hay giảm qua từng năm, và giai đoạn nào đổi hướng?

**1. Problem statement**
Doanh thu không đi theo một hướng suốt 2012–2022. Ví dụ đã biết: doanh thu rơi khoảng **40% vào cuối 2018** rồi đi ngang (`CLAUDE.md` §5.2).
Nếu chỉ tính một mức tăng trưởng trung bình cho cả 10 năm thì kết quả sai. `notebooks/04_forecasting/baseline.ipynb` đã làm vậy và ra −3,8%/năm, con số không đúng với giai đoạn nào (`CLAUDE.md` §6).
Hiện chưa có bảng nào chỉ ra năm nào tăng, năm nào giảm, và doanh thu đổi hướng vào những tháng nào.

**2. Mục tiêu**
Chia 2012–2022 thành **các giai đoạn** có hướng rõ ràng (tăng / giảm / đi ngang), xác định **mọi điểm đổi hướng**, và tính mức tăng trưởng riêng cho từng giai đoạn.

**3. Yêu cầu phân tích**
1. Tính doanh thu ghi nhận theo tháng và theo năm.
2. Tính tăng trưởng của mỗi năm so với năm trước.
3. Tại mỗi tháng, tính tổng doanh thu 12 tháng gần nhất. Cách này làm mượt phần lên xuống theo mùa (PS3 sẽ đo riêng phần đó). Tìm các tháng mà đường này đổi hướng.
4. Chia 2012–2022 thành các giai đoạn theo những điểm đổi hướng đó, tính mức tăng trưởng bình quân năm cho **từng** giai đoạn.

**4. Measure → Metric → KPI**

| Measure | Bảng tham gia | Cột |
|---|---|---|
| Tính tổng doanh thu ghi nhận theo ngày | `order_item`, `order` | `quantity`, `unit_price`, `order_date` |

| Metric | Cách tính |
|---|---|
| Doanh thu theo tháng, theo năm | Measure gom theo tháng / năm |
| Doanh thu 12 tháng gần nhất | Tổng doanh thu 12 tháng tính lùi từ tháng đang xét |

| KPI | Cách đọc |
|---|---|
| **Tăng trưởng so với năm trước (%)** | Năm nào âm là năm doanh thu giảm |
| **Tăng trưởng bình quân năm của từng giai đoạn (%)** | So các giai đoạn với nhau, ví dụ trước và sau 2018 |
| **Mức thay đổi tại điểm đổi hướng (%)** | Doanh thu 12 tháng sau điểm đó so với 12 tháng trước điểm đó |

---

## Tầng 2 — Pattern

### PS3. Trong một năm, doanh thu dồn vào những tháng nào; trong một tháng, dồn vào những ngày nào; nhịp đó có lặp lại mỗi năm không?

**1. Problem statement**
Doanh thu **không rải đều theo thời gian**. Trong cùng một năm, có tháng bán được gấp đôi tháng khác; trong cùng một tháng, những ngày cuối bán được nhiều hơn hẳn những ngày đầu. Phần lên xuống này **lặp lại theo lịch**, năm nào cũng vậy, nên nó không phải dấu hiệu công ty đang tốt lên hay xấu đi.

Có ba nhịp lặp, ở ba khoảng thời gian khác nhau (`CLAUDE.md` §5):

| Nhịp | Nhìn trong khoảng nào | Đã biết gì |
|---|---|---|
| Theo tháng | một năm (12 tháng) | cao nhất **tháng 4–6**, thấp nhất **tháng 12–1** (§5.3) |
| Theo ngày trong tháng | một tháng (~30 ngày) | doanh thu **tăng dần về cuối tháng** (§5.4) |
| Tháng 8 chẵn / lẻ | hai năm một lần | **tháng 8 năm lẻ** thấp hơn tháng 8 năm chẵn khoảng **37%** (§5.6) |

Nhịp thứ ba xếp vào Pattern vì nó **lặp lại theo lịch** — biết năm chẵn hay lẻ là đoán được — dù nguyên nhân nằm ở một chương trình khuyến mãi trong bảng `promotion`.

Hiện chưa có con số nào cho biết mỗi nhịp này lớn đến đâu. Khi không biết, rất dễ nhầm một tháng thấp theo mùa là dấu hiệu kinh doanh xấu. Dự báo 2023–2024 cũng sẽ bỏ sót tháng 8/2023, vì 2023 là năm lẻ.

**2. Mục tiêu**
Đo **độ lớn** của ba nhịp lịch (theo tháng, theo ngày trong tháng, tháng 8 năm lẻ) và kiểm tra chúng **có lặp lại ổn định qua các năm** không.

**3. Yêu cầu phân tích**
1. **Theo tháng — so trong nội bộ từng năm.** Với mỗi năm, lấy doanh thu từng tháng chia cho doanh thu trung bình 12 tháng **của chính năm đó**, rồi mới lấy trung bình qua các năm. Chia trong từng năm để mức nền to nhỏ của từng năm bị triệt tiêu: nhờ vậy xu hướng dài hạn và đứt gãy 2018 (việc của PS2) không lẫn vào đây, phần còn lại đúng là nhịp lịch.
2. **Theo ngày trong tháng:** tính tỷ trọng doanh thu rơi vào **ngày 26 trở đi**. Mốc 26 lấy 5–6 ngày cuối, tức khoảng **17–19% số ngày trong tháng**; nếu doanh thu rải đều thì phần này cũng chỉ chiếm chừng đó. Vượt bao nhiêu so với mốc này chính là mức dồn về cuối tháng.
3. **Tháng 8:** so doanh thu tháng 8 của từng năm, tách năm chẵn và năm lẻ.
4. Với cả ba nhịp, vẽ riêng từng năm để kiểm tra nhịp có giữ nguyên giữa các giai đoạn tìm được ở PS2 không.

**4. Measure → Metric → KPI**

| Measure | Bảng tham gia | Cột |
|---|---|---|
| Tính tổng doanh thu ghi nhận theo ngày | `order_item`, `order` | `quantity`, `unit_price`, `order_date` |
| Lấy tháng, ngày trong tháng, năm chẵn/lẻ | `order` | `order_date` |

| Metric | Cách tính |
|---|---|
| Chỉ số mùa vụ của tháng *m* | Doanh thu tháng *m* ÷ doanh thu trung bình 12 tháng **của cùng năm**, rồi lấy trung bình qua các năm. **1,00 = đúng bằng một tháng trung bình**, lớn hơn 1 là tháng cao |
| Tỷ trọng cuối tháng | Doanh thu từ ngày 26 trở đi ÷ doanh thu cả tháng |
| Doanh thu tháng 8 theo năm | Measure lọc tháng 8, gom theo năm |

| KPI | Cách đọc |
|---|---|
| **Tỷ số tháng cao nhất / tháng thấp nhất** | Càng lớn thì mùa vụ càng mạnh |
| **% doanh thu dồn vào cuối tháng** | So với mốc rải đều **17–19%**. Vượt càng xa mốc đó thì doanh thu càng dồn về cuối tháng |
| **Chênh lệch tháng 8 năm lẻ so với năm chẵn (%)** | Khoảng −37% theo `CLAUDE.md` §5.6 |

---

## Tầng 3 — Drivers

### PS4. Doanh thu mỗi năm thay đổi so với năm trước là do số đơn, số món mỗi đơn, hay giá mỗi món?

**1. Problem statement**
PS2 cho biết doanh thu tăng / giảm **khi nào**, nhưng chưa cho biết **vì sao**. Doanh thu của một kỳ luôn bằng đúng tích của ba số (`CLAUDE.md` §5.1):

> **Doanh thu = Số đơn × Số món trên mỗi đơn × Giá trung bình mỗi món**

Cùng một mức tăng 10% có thể đến từ ba nguồn rất khác nhau, và mỗi nguồn dẫn tới một hành động khác:
- số đơn đổi: do khách mua nhiều / ít lần hơn, cần xem hoạt động thu hút và giữ khách;
- số món mỗi đơn đổi: do khách mua nhiều / ít món hơn mỗi lần, cần xem bán kèm;
- giá mỗi món đổi: do giá bán hoặc cơ cấu sản phẩm đổi, cần xem chính sách giá.

Chưa tách ra thì chưa biết một năm tăng là nhờ đâu, một năm giảm là vì đâu.

**2. Mục tiêu**
Có bảng **cho mọi năm 2013–2022**: doanh thu thay đổi bao nhiêu so với năm trước, và **mỗi thành phần góp bao nhiêu phần trăm** vào mức thay đổi đó. Cùng bảng này trả lời được cho bất kỳ năm nào, dù năm đó nằm trước hay sau 2018, dù doanh thu tăng hay giảm.

**3. Yêu cầu phân tích**
1. Tính ba thành phần theo năm: số đơn, số món trên mỗi đơn, giá trung bình mỗi món.
2. Kiểm tra lại: tích ba thành phần phải bằng đúng doanh thu của năm đó.
3. Với **từng cặp năm liền nhau**, tính % thay đổi của doanh thu và của từng thành phần, rồi chia mức thay đổi doanh thu cho ba thành phần.
4. Gom theo các giai đoạn tìm được ở PS2 để thấy trong mỗi giai đoạn, thành phần nào thường là động lực chính.

Ví dụ từ kết quả sơ bộ (`docs/problem_statement.md` D1), khi so giai đoạn trước và sau 2018: số đơn mỗi năm **giảm 52,2%**, còn giá trung bình mỗi món **tăng 30,2%**. Tức là đợt giảm này do mất đơn, không phải do giá. Các năm khác sẽ đọc theo cùng cách.

**4. Measure → Metric → KPI**

| Measure | Bảng tham gia | Cột |
|---|---|---|
| Đếm số đơn hàng | `order` | `order_id`, `order_date` |
| Tính tổng số món đã bán | `order_item`, `order` | `quantity`, `order_date` |
| Tính tổng doanh thu ghi nhận | `order_item`, `order` | `quantity`, `unit_price`, `order_date` |

| Metric | Cách tính |
|---|---|
| Số món trên mỗi đơn | Tổng số món ÷ số đơn |
| Giá trung bình mỗi món | Doanh thu ÷ tổng số món |
| Giá trị trung bình mỗi đơn | Doanh thu ÷ số đơn (= số món/đơn × giá/món) |

| KPI | Cách đọc |
|---|---|
| **Thay đổi số đơn so với năm trước (%)** | Dương là thêm lượt mua, âm là mất lượt mua |
| **Thay đổi số món trên mỗi đơn so với năm trước (%)** | Dương là khách mua nhiều món hơn mỗi lần |
| **Thay đổi giá trung bình mỗi món so với năm trước (%)** | Dương là bán đắt hơn hoặc bán nhiều hàng giá cao hơn |
| **Phần đóng góp của từng thành phần vào mức thay đổi doanh thu (%)** | Thành phần có phần lớn nhất là động lực chính của năm đó |

---

### PS5. Ngành hàng nào, khu vực nào, nhóm khách nào đóng góp nhiều nhất vào mức tăng / giảm doanh thu mỗi năm?

**1. Problem statement**
PS4 cho biết mỗi năm doanh thu đổi vì thành phần nào, nhưng chưa biết thay đổi đó nằm ở **đâu** và ở **ai**. Có hai khả năng:
- thay đổi dồn vào một vài ngành hàng, một khu vực, hay một nhóm khách: công ty biết chính xác nhóm nào đang đẩy lên, nhóm nào đang kéo xuống;
- thay đổi trải đều mọi nhóm: vấn đề (hoặc thành công) nằm ở cấp toàn công ty.

Với khách hàng, số đơn tách tiếp được thành:

> **Số đơn = Số khách có mua trong năm × Số đơn mỗi khách**

Tách như vậy sẽ biết số đơn đổi là do **số khách** đổi hay do **mỗi khách mua dày / thưa** đi.

**2. Mục tiêu**
Có bảng **cho mọi năm 2013–2022**: mỗi ngành hàng, mỗi khu vực, mỗi kênh thu hút khách tăng / giảm bao nhiêu doanh thu so với năm trước, và chiếm bao nhiêu phần trăm mức thay đổi tổng. Kèm theo đó, số đơn thay đổi là do số khách hay do số đơn mỗi khách.

**3. Yêu cầu phân tích**
1. **Ngành hàng:** tính doanh thu theo năm cho từng `category`.
2. **Khu vực:** tính doanh thu theo năm cho từng `region`.
3. **Khách hàng:**
   - tính số khách có mua và số đơn mỗi khách theo năm, kiểm tra tích hai số bằng số đơn ở PS4;
   - tính doanh thu theo năm cho từng `acquisition_channel` (kênh khách đến lần đầu).
4. Với mỗi chiều và **từng cặp năm liền nhau**: mỗi nhóm tăng / giảm bao nhiêu tiền, chiếm bao nhiêu phần trăm mức thay đổi tổng.
5. Gom theo các giai đoạn ở PS2 để xem tỷ trọng các nhóm có dịch chuyển giữa các giai đoạn không (ví dụ trước và sau 2018).

Lưu ý: `region` chỉ có 3 nhãn Central / East / West. Đây là nhãn của bộ dữ liệu mô phỏng, không suy ra vùng miền thật (`docs/problem_statement.md` §8.2).

**4. Measure → Metric → KPI**

| Measure | Bảng tham gia | Cột |
|---|---|---|
| Tính tổng doanh thu ghi nhận theo ngày | `order_item`, `order` | `quantity`, `unit_price`, `order_date` |
| Gắn ngành hàng cho từng dòng hàng | `order_item` → `product` → `product_model` | `product_id`, `product_name`, `category` |
| Gắn khu vực cho từng đơn | `order` → `customer` → `zip_area` → `city` | `customer_id`, `zip`, `city`, `region` |
| Đếm số khách có mua trong năm | `order` | `customer_id`, `order_date` |
| Gắn kênh thu hút cho từng đơn | `order` → `customer` | `customer_id`, `acquisition_channel` |

| Metric | Cách tính |
|---|---|
| Doanh thu theo ngành hàng / khu vực / kênh thu hút × năm | Measure doanh thu gom theo nhóm và năm |
| Tỷ trọng doanh thu của nhóm | Doanh thu nhóm ÷ doanh thu tổng cùng năm |
| Số đơn mỗi khách | Số đơn ÷ số khách có mua trong năm |

| KPI | Cách đọc |
|---|---|
| **Tăng trưởng doanh thu từng nhóm so với năm trước (%)** | Nhóm dương cao nhất đang đẩy lên, nhóm âm nhiều nhất đang kéo xuống |
| **Phần đóng góp vào mức thay đổi (%)** = thay đổi doanh thu của nhóm ÷ thay đổi doanh thu tổng | Nhóm có phần đóng góp lớn nhất là nhóm quyết định năm đó. **Năm nào doanh thu tổng gần như đứng yên thì mẫu số gần 0, tỷ lệ này phồng lên quá 100% hoặc xuống dưới −100%; khi đó phải đọc kèm số tiền tuyệt đối, không đọc riêng phần trăm** |
| **Phần đóng góp của nhóm lớn nhất (%)**, hoặc của 2 nhóm dẫn đầu | Đây là KPI trả lời trực tiếp câu hỏi ở mục 1: cao thì mức thay đổi **dồn** vào vài nhóm, thấp thì **trải đều** mọi nhóm |
| **Thay đổi tỷ trọng của nhóm giữa hai giai đoạn (điểm %)** | Tỷ trọng giai đoạn sau trừ tỷ trọng giai đoạn trước (giai đoạn lấy từ PS2). Khác 0 nhiều nghĩa là cơ cấu đã dịch chuyển, không chỉ lên xuống theo năm |
| **Thay đổi số khách có mua (%)**, so với năm trước | Âm là mất khách |
| **Thay đổi số đơn mỗi khách (%)**, so với năm trước | Âm là khách còn lại mua thưa đi. So với KPI trên: cái nào đổi mạnh hơn là nguyên nhân chính của thay đổi số đơn |

---

## 3. Bảng tổng hợp

| Tầng | PS | Câu hỏi | Bảng Silver | KPI chính |
|---|---|---|---|---|
| 0. Đo đúng | PS1 | Thực thu bao nhiêu mỗi năm / tháng? | `order_item`, `order` | Tỷ lệ thực thu, tăng trưởng doanh thu thực tế |
| 1. Trend | PS2 | Tăng hay giảm, giai đoạn nào đổi hướng? | `order_item`, `order` | Tăng trưởng so với năm trước, tăng trưởng từng giai đoạn |
| 2. Pattern | PS3 | Dồn vào tháng nào trong năm, ngày nào trong tháng? | `order_item`, `order` | Tỷ số tháng cao/thấp, % dồn cuối tháng, chênh tháng 8 năm lẻ |
| 3. Drivers | PS4 | Mỗi năm đổi vì số đơn, số món/đơn hay giá/món? | `order_item`, `order` | % thay đổi và phần đóng góp của số đơn, số món/đơn, giá/món |
| 3. Drivers | PS5 | Ngành hàng / khu vực / nhóm khách nào quyết định mức tăng / giảm mỗi năm? | `order_item`, `order`, `product`, `product_model`, `customer`, `zip_area`, `city` | Phần đóng góp vào mức thay đổi, thay đổi số khách và số đơn/khách |

---

## 4. Những gì đã bỏ, và lý do

| Đã bỏ | Lý do |
|---|---|
| PS "Khuyến mãi có ăn mòn biên lợi nhuận không?" | Đo **lợi nhuận** (cần `product.unit_cogs`), không đo doanh thu. Nếu giảng viên muốn mở rộng sang lợi nhuận thì thêm lại. Tác động của tháng 8 năm lẻ lên doanh thu đã nằm trong PS3 |
| Chiều kênh bán (`order.order_source`, `order.device_type`) trong PS5 | Giữ PS5 gọn ở 3 chiều. Có thể thêm theo cùng cách làm nếu cần |
| Các thuật ngữ viết tắt (UPT, ASP, AOV, EOM, CAGR, Revenue Leakage) | Thay bằng tên tiếng Việt kèm công thức để người đọc không cần tra |

## 5. Đối chiếu với đề xuất của GPT

### Khung 3 tầng của GPT

GPT chia big problem thành 3 tầng: **Revenue Trend** (tăng/giảm thế nào?), **Revenue Pattern** (có seasonality / peak / decline không?), **Revenue Drivers** (Product/Category, Region, Customer). Tài liệu này giữ khung đó và sửa 4 chỗ:

| Chỗ chưa ổn trong khung GPT | Cách sửa ở bản này |
|---|---|
| "decline" nằm ở Pattern, chồng lên Trend | Đứt gãy 2018 chỉ nằm ở Trend (PS2). Pattern chỉ gồm những gì lặp lại theo lịch (PS3) |
| Thiếu bước chốt định nghĩa doanh thu | Thêm **Tầng 0** (PS1) |
| Drivers mới là tên chiều, chưa phải câu hỏi | Viết thành câu hỏi PS5, có Measure → Metric → KPI |
| Drivers thiếu phân rã bên trong | Thêm PS4: số đơn × số món/đơn × giá/món, làm trước khi xét từng nhóm |

### Bản 6 PS của GPT

| GPT | Ở bản này |
|---|---|
| PS1 Doanh thu thay đổi thế nào theo thời gian? · PS2 Giai đoạn nào tăng/giảm đáng kể? | Gộp thành **PS2** (cùng dữ liệu, cùng biểu đồ) |
| PS3 Doanh thu có tính mùa vụ không? | **PS3**, bổ sung ngày trong tháng và tháng 8 năm lẻ |
| PS6 Tăng trưởng do số lượng hay giá trị đơn? | **PS4**, tách thành 3 thành phần thay vì 2 (giá trị đơn = số món/đơn × giá/món) |
| PS4 Nhóm sản phẩm nào đóng góp? · PS5 Khu vực nào tốt hơn? | Gộp thành **PS5**, thêm chiều khách hàng |
| — | **PS1** mới: doanh thu thực tế, đúng ví dụ "doanh thu sau chiết khấu" của giảng viên |

GPT ghi `revenue`, `date`, `region`, `category` như cột có sẵn. Trên Silver:
- `revenue` phải tính từ `quantity × unit_price`;
- `date` là `order.order_date`;
- `region` và `category` phải join qua nhiều bảng (xem Measure của PS5).

## Tài liệu liên quan

- `docs/problem_statement.md`: nguồn các con số, gồm thác nước doanh thu (H2.2, K6), phân rã 2018 (D1), tháng 8 năm lẻ (D2), cuối tháng (D4).
- `CLAUDE.md` §5: 8 kết luận đã chứng minh từ EDA.
- `docs/normalized_schema.md`: thiết kế 19 bảng Silver.
