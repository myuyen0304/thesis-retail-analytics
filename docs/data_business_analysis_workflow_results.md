# Kết quả EDA theo quy trình hiểu dữ liệu và nghiệp vụ

Tài liệu này áp dụng từng section trong
[`data_business_analysis_workflow.md`](data_business_analysis_workflow.md) vào 14 nguồn CSV của bài toán bán lẻ.
Các con số được tạo lại từ toàn bộ dữ liệu trong [`notebooks/01_exploration/business_eda.ipynb`](../notebooks/01_exploration/business_eda.ipynb), không lấy từ mẫu
`head()`.

Quy ước đọc kết quả:

- **Quan sát**: đo trực tiếp từ dữ liệu.
- **Diễn giải**: ý nghĩa hợp lý rút ra từ quan sát.
- **Giả thuyết**: cách giải thích cần thêm dữ liệu hoặc thiết kế kiểm chứng.
- **Chưa xác định**: dataset không đủ thông tin để kết luận.

---

## 1. Hiểu bài toán kinh doanh

### Kết luận hiện tại

Dataset mô tả một doanh nghiệp bán lẻ thời trang với vòng đời chính:

```text
Khu vực → Khách hàng → Đơn hàng → Dòng sản phẩm ← Sản phẩm
                                  ↓
                              Khuyến mãi
                    Đơn hàng → Thanh toán/Giao hàng
                    Dòng hàng → Hoàn trả/Đánh giá
                    Sản phẩm → Snapshot tồn kho
                    Ngày → Web traffic/Sales actual/Forecast
```

- Lịch sử giao dịch và sales actual: `2012-07-04 → 2022-12-31`.
- Bài toán đầu ra: dự báo `Revenue` và `COGS` theo ngày cho 548 ngày từ `2023-01-01 → 2024-07-01`.
- Người sử dụng kết quả có thể dùng dữ liệu cho planning doanh thu/giá vốn, phân tích danh mục, khuyến mãi,
  fulfillment, hậu mãi và tồn kho.
- `sample_submission.csv` là khung output tương lai, không phải actual.

### Điều chưa được dữ liệu xác nhận

- Tiền tệ, múi giờ và định nghĩa kế toán chính thức.
- SLA giao hàng để phân biệt đúng hạn và trễ.
- Người sở hữu từng hệ thống nguồn và quy trình nhập liệu thực tế.
- KPI chính thức mà stakeholder ưu tiên ngoài hai target `Revenue` và `COGS`.

---

## 2. Lập bản đồ toàn bộ nguồn dữ liệu

Notebook đã đọc đủ 14/14 nguồn, tổng cộng **2.960.736 dòng**.

| Nguồn | Số dòng | Grain | Khóa nguồn dự kiến | Phạm vi thời gian |
|---|---:|---|---|---|
| `customers` | 121.930 | một khách hàng | `customer_id` | 2012-01-17 → 2022-12-31 |
| `geography` | 39.948 | một mã zip | `zip` | không có cột ngày |
| `products` | 2.412 | một SKU/biến thể | `product_id` | không có cột ngày |
| `promotions` | 50 | một chương trình | `promo_id` | 2013-01-31 → 2022-12-31 |
| `orders` | 646.945 | một đơn hàng | `order_id` | 2012-07-04 → 2022-12-31 |
| `order_items` | 714.669 | một dòng sản phẩm trong đơn | nguồn thiếu khóa dòng hàng | kế thừa ngày từ `orders` |
| `payments` | 646.945 | thanh toán của một đơn | `order_id` | kế thừa ngày từ `orders` |
| `shipments` | 566.067 | vận chuyển của một đơn | `order_id` | 2012-07-04 → 2022-12-31 |
| `returns` | 39.939 | một lần trả dòng hàng | `return_id` | 2012-07-11 → 2022-12-31 |
| `reviews` | 113.551 | một đánh giá dòng hàng | `review_id` | 2012-07-10 → 2022-12-31 |
| `inventory` | 60.247 | một sản phẩm tại một snapshot tháng | `(snapshot_date, product_id)` | 2012-07-31 → 2022-12-31 |
| `web_traffic` | 3.652 | traffic tổng hợp một ngày | `date` | 2013-01-01 → 2022-12-31 |
| `sales` | 3.833 | sales actual một ngày | `Date` | 2012-07-04 → 2022-12-31 |
| `sample_submission` | 548 | một ngày tương lai cần dự báo | `Date` | 2023-01-01 → 2024-07-01 |

Các bảng không có cột ngày riêng phải nhận thời gian thông qua quan hệ với `orders`; không được tự gán khoảng
thời gian chỉ dựa vào tên file.

---

## 3. Xác định grain của từng bảng

### Bằng chứng

- Toàn bộ khóa dự kiến đều không null và không trùng, ngoại trừ `order_items` vì CSV không cung cấp khóa dòng.
- Có **16** cặp `(order_id, product_id)` xuất hiện nhiều hơn một lần trong cùng đơn. Vì vậy cặp này không phải
  khóa an toàn.
- Notebook sinh `line_number` theo thứ tự nguồn và dùng `(order_id, line_number)` làm định danh tái dựng.
- `payments.order_id` và `shipments.order_id` là duy nhất trong snapshot, nên dữ liệu quan sát thể hiện quan hệ
  tối đa một payment và một shipment cho mỗi order.
- `returns` và `reviews` thuộc cấp dòng hàng, nhưng nguồn chỉ giữ `(order_id, product_id)`. Có 4 return và 2 review
  rơi vào các cặp nhập nhằng.
- `inventory` là snapshot `(snapshot_date, product_id)`, không phải giao dịch bán.
- `web_traffic` chỉ có grain ngày, không có foreign key tới customer, session hay order.

### Giới hạn

`line_number` là quy tắc tái dựng có thể lặp lại, không phải khóa gốc từ hệ thống nguồn. Production cần source
cung cấp `order_item_id` hoặc khóa dòng hàng ổn định.

---

## 4. Lần theo một giao dịch thực tế

Notebook dùng `order_id = 46270`:

- Đơn ngày `2013-02-04`, khách `44051`, khu vực East, trạng thái `delivered`.
- Một dòng hàng: 4 sản phẩm `VietMotion RP-51`, category Outdoor, segment Activewear.
- Gross Revenue: `4 × 615,65 = 2.462,60`.
- Discount: `369,39`; Net Payment: `2.093,21`.
- COGS: `4 × 486,68 = 1.946,72`; Gross Profit sau discount: `146,49`.
- Thanh toán bằng PayPal trong 3 kỳ.
- Ship ngày `2013-02-06`, delivery ngày `2013-02-10`, lead time 4 ngày.
- Có review 5 sao; không có return được hiển thị cho giao dịch này.

Ví dụ xác nhận giá và discount nằm ở dòng hàng, COGS đơn vị nằm ở product, payment/shipment thuộc order, còn
review thuộc dòng sản phẩm.

---

## 5. Kiểm tra chất lượng và quan hệ dữ liệu

### Kết quả chất lượng

- **0 dòng trùng hoàn toàn** trong cả 14 nguồn.
- Ngoài các null có ý nghĩa nghiệp vụ, các bảng không có null ở khóa dự kiến.
- `promotions` có 40 null trong một cột; `order_items` có 1.152.816 null ở hai cột promotion. Đây chủ yếu biểu
  diễn không có promotion hoặc không có promotion thứ hai, chưa phải bằng chứng dữ liệu lỗi.
- **0 orphan** trên 15 cột liên kết được kiểm tra giữa customer, geography, order, item, product, promotion,
  payment, shipment, return, review và inventory.
- `sales` có đủ mọi ngày trong khoảng lịch sử: **0 ngày thiếu**.
- Có 0 dòng vi phạm các luật cơ bản đã kiểm tra: promotion kết thúc trước khi bắt đầu, delivery trước ship,
  quantity không dương, giá/payment âm, return quantity không dương, rating ngoài `[1, 5]`, tồn kho âm.

### Điểm cần xử lý bằng thiết kế thay vì “làm sạch” tùy ý

- `order_items` thiếu khóa dòng hàng ổn định.
- Promotion được lưu bằng hai cột lặp `promo_id`, `promo_id_2`; cần unpivot thành bảng nối.
- 80.878 order không có shipment. Đây chưa chắc là lỗi; cần đối chiếu `order_status` và quy trình fulfillment
  trước khi xử lý.
- `orders.order_status='returned'` và event trong `returns` không nên mặc định là cùng một định nghĩa KPI.

---

## 6. Tái tạo và đối soát KPI

### Công thức được dữ liệu xác nhận

```text
Gross Revenue = Σ(quantity × unit_price)
Net Sales     = Gross Revenue − Σ(discount_amount)
COGS          = Σ(quantity × products.cogs)
Gross Profit  = Net Sales − COGS
AOV           = Net Sales / số order
```

### Reconciliation

| Phép đối soát | Số bản ghi | Sai số tuyệt đối lớn nhất | Kết luận |
|---|---:|---:|---|
| `sales.Revenue` với gross từ dòng hàng | 3.833 ngày | 0 | khớp |
| `sales.COGS` với quantity × product COGS | 3.833 ngày | 0,00499927 | khớp trong sai số float |
| `payments.payment_value` với net sales theo order | 646.945 đơn | 0 | khớp |

Điểm quan trọng: `sales.Revenue` là **Gross Revenue**, không trừ discount. COGS trong dataset chưa bao gồm
shipping, refund, marketing, lương hay chi phí vận hành; vì vậy không được gọi Gross Profit ở đây là lợi nhuận
kế toán cuối cùng.

---

## 7. Thực hiện EDA theo câu hỏi nghiệp vụ

### 7.1 Kết quả kinh doanh

- 646.945 đơn từ 90.246 khách có mua, 714.669 dòng hàng và 3.213.143 units.
- Gross Revenue: **16,430 tỷ**; Discount: **0,750 tỷ**; Net Sales: **15,681 tỷ**.
- COGS: **14,163 tỷ**; Gross Profit sau discount: **1,517 tỷ**; Gross Margin: **9,68%**.
- AOV theo Net Sales: **24.238,33**.
- Biểu đồ tháng cho thấy một vùng đứt gãy cuối 2018; trước khi forecasting phải đánh giá các chế độ thời gian
  riêng thay vì ngoại suy một trend duy nhất.

### 7.2 Sản phẩm và khuyến mãi

- Streetwear tạo Net Sales lớn nhất, **12,558 tỷ**, nhưng margin **9,28%**; GenZ nhỏ hơn nhiều nhưng margin cao
  nhất trong bốn category, **15,47%**. Quy mô và hiệu quả không phải cùng một khái niệm.
- 276.316 dòng có `promo_id`, 206 dòng có promotion thứ hai; unpivot tạo **276.522** liên kết item–promotion.
- Cả 206 dòng hai promotion khớp công thức discount quan sát được `10% gross + 50`.
- Urban Blowout xuất hiện vào tháng 8 các năm lẻ. Trong các tháng 8 đó, `COGS/Revenue` lần lượt khoảng
  1,307–1,401; các tháng 8 năm chẵn quan sát được nằm khoảng 0,789–0,828.
- Đây là association lịch sử có ích cho planning/forecasting, chưa chứng minh promotion là nguyên nhân duy nhất.

### 7.3 Khách hàng và thị trường

- East có Net Sales lớn nhất: **7,291 tỷ**; Central **4,719 tỷ**; West **3,670 tỷ**.
- `organic_search` đứng đầu theo acquisition channel với **4,712 tỷ** Net Sales.
- Acquisition channel là thuộc tính hồ sơ khách, không phải attribution chắc chắn của từng order.
- Phân tích khách mới/quay lại, cohort và mức tập trung doanh thu chưa được thực hiện trong vòng EDA này; được
  đưa vào backlog thay vì suy đoán.

### 7.4 Vận hành và hậu mãi

- 566.067 shipment có lead time trung bình **4,499 ngày**, median **4 ngày**.
- Chưa thể tính tỷ lệ giao trễ vì không có SLA hoặc promised delivery date.
- Return line rate **5,59%**; return unit rate **3,41%**; refund/Net Sales **3,26%**.
- Rating trung bình **3,936/5**.
- Snapshot tồn kho mới nhất là `2022-12-31`; các chỉ số stockout/overstock có thể dùng để sàng lọc SKU, nhưng
  `inventory.units_sold` chưa được chứng minh là tổng hợp trực tiếp từ `order_items`.

### 7.5 Mối liên hệ giữa các hiện tượng

- Ghép theo ngày được 3.652 ngày giữa traffic và sales.
- `corr(sessions, Gross Revenue) = 0,3211`; `corr(unique_visitors, Gross Revenue) = 0,3188`.
- `orders/sessions = 0,0074` chỉ là proxy cấp ngày, không phải conversion rate chính thức.
- Phân tích “giao hàng trễ → review thấp” chưa hợp lệ vì thiếu định nghĩa trễ; promotion → return cần kiểm soát
  category, thời gian và selection bias trước khi diễn giải.

---

## 8. Tách bằng chứng, diễn giải và nguyên nhân

| Tầng | Kết luận trong dataset |
|---|---|
| Quan sát | Streetwear có 12,558 tỷ Net Sales và margin 9,28% |
| Diễn giải | Streetwear là category chủ lực về quy mô nhưng không đứng đầu về margin |
| Giả thuyết | Cơ cấu promotion hoặc product mix có thể góp phần làm margin thấp hơn |
| Chưa chứng minh | Promotion gây ra margin thấp |

Tương tự, correlation traffic–revenue và mẫu hình Urban Blowout chỉ là bằng chứng đồng biến/đồng thời. Muốn kết
luận nhân quả cần experiment, quasi-experiment hoặc ít nhất dữ liệu kiểm soát đầy đủ hơn.

---

## 9. Sản phẩm bàn giao sau vòng EDA này

| Artifact | Trạng thái | Vai trò |
|---|---|---|
| `data_business_analysis_workflow.md` | có | quy trình tái sử dụng |
| `data_business_analysis_workflow_results.md` | có | câu trả lời theo từng section |
| `notebooks/01_exploration/business_eda.ipynb` | có, đã chạy 17/17 code cell | bằng chứng EDA có output |
| `business_data_notes.md` | có | diễn giải business chi tiết |
| `normalized_schema.md` và diagram | có | mô hình quan hệ sau EDA |
| Assumption log và question backlog | nằm trong tài liệu này | giới hạn và câu hỏi cần xác nhận |

Notebook không phải database production và chưa xây forecasting model.

---

## 10. Checklist tự đánh giá

### Đã trả lời bằng dữ liệu

- [x] Câu chuyện vận hành và xương sống giao dịch.
- [x] Kiểm kê đủ 14 nguồn, row count, grain, khóa và phạm vi thời gian.
- [x] Kiểm tra uniqueness, null, duplicate, orphan và một số business rule cơ bản.
- [x] Lần theo một order thật.
- [x] Tái tạo Gross Revenue, Net Sales/Payment và COGS.
- [x] EDA kết quả kinh doanh, category, region, channel, promotion, fulfillment, hậu mãi, inventory và traffic.
- [x] Tách quan sát, diễn giải và giả thuyết.

### Còn mở hoặc cần stakeholder

- [ ] Xác nhận tiền tệ, múi giờ, COGS kế toán và source of truth của return.
- [ ] Có SLA/promised date để định nghĩa giao trễ.
- [ ] Có khóa dòng hàng ổn định từ hệ thống nguồn.
- [ ] Phân tích cohort khách mới/quay lại và concentration.
- [ ] Định nghĩa KPI chính thức cùng filter cho order hủy/return/refund.
- [ ] Thiết kế kiểm chứng causal impact của promotion.

---

## Đề xuất bước tiếp theo

1. Hoàn thiện customer EDA: new/returning, cohort và concentration.
2. Tính profitability sau refund theo product/category, nhưng ghi rõ shipping và OPEX vẫn chưa có.
3. Đối chiếu 80.878 order không có shipment theo `order_status` trước khi gọi là vấn đề vận hành.
4. Tách train trước/sau đứt gãy 2018 và xây các feature calendar có thể biết trong tương lai.
5. Không dùng trực tiếp auxiliary feature sau `2022-12-31`, vì các bảng phụ không phủ vùng forecast.

Kết luận hiện tại: dataset đã đủ để mô tả business flow, grain, quan hệ, công thức tiền và các tín hiệu EDA
chính. Những câu hỏi về nhân quả, SLA và định nghĩa kế toán vẫn phải được giữ ở trạng thái chưa xác nhận.
