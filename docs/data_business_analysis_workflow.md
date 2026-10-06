# Quy trình hiểu dữ liệu và nghiệp vụ khi nhận một dataset mới

Tài liệu này ghi lại cách tiếp cận của một **Data Analyst kết hợp Business Analyst** khi tiếp nhận một
dataset mới. Mục tiêu không chỉ là biết dữ liệu có bao nhiêu dòng hay vẽ được biểu đồ, mà phải trả lời
được:

> Dữ liệu ghi lại hoạt động kinh doanh nào, mỗi dòng đại diện cho điều gì, các bảng liên kết ra sao,
> chỉ số được tạo như thế nào và dữ liệu có thể hỗ trợ quyết định nào?

> **Áp dụng trong repo này:** xem kết quả theo từng section tại
> [`data_business_analysis_workflow_results.md`](data_business_analysis_workflow_results.md) và bằng chứng có
> thể chạy lại trong [`notebooks/01_exploration/business_eda.ipynb`](../notebooks/01_exploration/business_eda.ipynb).

Quy trình nên đi theo thứ tự:

```text
Bài toán kinh doanh
    → Câu chuyện vận hành
        → Bản đồ nguồn dữ liệu
            → Grain và quan hệ
                → Chất lượng dữ liệu
                    → Công thức KPI
                        → EDA theo câu hỏi nghiệp vụ
                            → Kết luận, giới hạn và đề xuất hành động
```

Không nên bắt đầu bằng model, correlation hoặc dashboard khi chưa hiểu các lớp phía trước.

---

## 1. Hiểu bài toán kinh doanh

Trước khi phân tích sâu các cột, cần xác định bối cảnh mà dataset được tạo ra.

### 1.1 Những câu hỏi cần trả lời

- Doanh nghiệp đang bán sản phẩm hay cung cấp dịch vụ gì?
- Khách hàng hoặc người sử dụng là ai?
- Hoạt động vận hành chính diễn ra theo trình tự nào?
- Ai hoặc hệ thống nào tạo ra từng loại dữ liệu?
- Doanh nghiệp đang gặp vấn đề gì?
- Người sử dụng kết quả phân tích cần đưa ra quyết định gì?
- Chỉ số kết quả cần quan tâm là doanh thu, lợi nhuận, tỷ lệ hoàn trả, churn, tồn kho hay chỉ số khác?
- Phạm vi thời gian, khu vực, sản phẩm và đối tượng phân tích là gì?

### 1.2 Khi không có stakeholder để hỏi

Có thể dựng một câu chuyện nghiệp vụ ban đầu từ:

- đề bài, `README` và tài liệu mô tả;
- tên file, tên bảng và tên cột;
- giá trị thực tế xuất hiện trong dữ liệu;
- quan hệ khóa giữa các bảng;
- công thức có thể tái tạo các bảng tổng hợp.

Tuy nhiên, mọi ý nghĩa chưa được tài liệu hoặc dữ liệu xác nhận phải được ghi là **giả thuyết**, không
được trình bày như sự thật.

---

## 2. Lập bản đồ toàn bộ nguồn dữ liệu

Đầu tiên cần kiểm kê tất cả file hoặc bảng, thay vì chỉ mở một bảng có vẻ quan trọng nhất.

Với mỗi nguồn, ghi lại tối thiểu:

| Câu hỏi | Ví dụ trong bán lẻ |
|---|---|
| Bảng mô tả đối tượng hay sự kiện gì? | `orders` mô tả đơn hàng |
| Một dòng đại diện cho điều gì? | Một đơn hàng |
| Khóa nhận diện bản ghi là gì? | `order_id` |
| Bảng được tạo ở bước vận hành nào? | Khi khách hoàn tất đặt hàng |
| Bảng liên kết với nguồn nào? | `customers`, `order_items`, `payments` |
| Khoảng thời gian được bao phủ? | Ngày đầu và ngày cuối có dữ liệu |
| Bảng giúp trả lời quyết định nào? | Phân tích doanh số và hành vi mua |

### 2.1 Kết quả cần có

Sau bước này, cần tạo được một **data inventory** gồm:

- tên nguồn;
- ý nghĩa nghiệp vụ;
- số dòng và số cột;
- khoảng thời gian;
- khóa dự kiến;
- grain dự kiến;
- bảng liên quan;
- vấn đề cần xác minh.

Đây mới là bản đồ khám phá ban đầu, chưa phải ERD hay thiết kế database cuối cùng.

---

## 3. Xác định grain của từng bảng

**Grain** là ý nghĩa chính xác của một dòng dữ liệu. Đây là câu hỏi phải trả lời trước khi join, tính KPI
hoặc thiết kế mô hình dữ liệu.

Ví dụ:

| Bảng | Grain có thể có |
|---|---|
| `customers` | Một khách hàng |
| `orders` | Một đơn hàng |
| `order_items` | Một dòng sản phẩm trong một đơn hàng |
| `payments` | Một lần hoặc một phương thức thanh toán của đơn hàng |
| `shipments` | Một lần giao hàng của đơn hàng |
| `inventory` | Một sản phẩm tại một ngày chụp tồn kho |
| `sales` | Kết quả bán hàng tổng hợp theo ngày |

### 3.1 Cách kiểm chứng grain

Không kết luận chỉ dựa vào tên bảng. Cần kiểm tra:

- cột hoặc tổ hợp cột nào là duy nhất;
- một khóa nghiệp vụ xuất hiện bao nhiêu lần;
- duplicate là lỗi hay phản ánh đúng nghiệp vụ;
- một đơn có nhiều sản phẩm, payment hoặc shipment hay không;
- cùng một sản phẩm có thể xuất hiện nhiều lần trong một đơn hay không;
- dữ liệu snapshot khác dữ liệu giao dịch như thế nào.

### 3.2 Vì sao grain quan trọng?

Nếu xác định sai grain, ta có thể:

- join làm nhân bản bản ghi;
- đếm số dòng sản phẩm thành số đơn hàng;
- cộng doanh thu hoặc chi phí nhiều lần;
- so sánh KPI ở hai cấp độ không tương thích;
- chọn sai khóa chính và khóa ngoại;
- tạo feature bị rò rỉ hoặc sai ý nghĩa.

---

## 4. Lần theo một giao dịch thực tế

Một cách nhanh để hiểu business là chọn một giao dịch có thật và đi xuyên qua tất cả bảng liên quan.

Ví dụ vòng đời một đơn hàng bán lẻ:

```text
Khách hàng
    → tạo đơn hàng
        → mua một hoặc nhiều sản phẩm
            → có thể áp dụng khuyến mãi
        → thanh toán
        → giao hàng
        → có thể hoàn trả hoặc đánh giá
```

Với giao dịch được chọn, cần trả lời:

- Khách hàng là ai và thuộc khu vực nào?
- Đơn được tạo lúc nào và có trạng thái gì?
- Đơn có bao nhiêu dòng hàng và tổng số lượng bao nhiêu?
- Giá bán, chiết khấu và chi phí nằm ở bảng nào?
- Một dòng hàng có thể nhận nhiều promotion không?
- Một đơn có thể có nhiều payment hoặc shipment không?
- Return thuộc cấp đơn hàng hay cấp dòng hàng?
- Review đánh giá sản phẩm, đơn hàng hay trải nghiệm giao hàng?

Một giao dịch cụ thể giúp biến nhiều bảng rời rạc thành một câu chuyện vận hành dễ nhớ.

---

## 5. Kiểm tra chất lượng và quan hệ dữ liệu

Việc kiểm tra phải chạy trên toàn bộ dữ liệu liên quan, không chỉ dựa vào `head()` hoặc một mẫu nhỏ.

### 5.1 Kiểm tra cấu trúc

- số dòng và số cột;
- tên cột và kiểu dữ liệu thực tế;
- khoảng thời gian và độ liên tục của ngày;
- đơn vị đo, tiền tệ và múi giờ;
- miền giá trị của các cột phân loại.

### 5.2 Kiểm tra chất lượng

- null và tỷ lệ null;
- duplicate theo khóa dự kiến;
- số lượng, giá hoặc chi phí âm;
- ngày kết thúc trước ngày bắt đầu;
- giá trị ngoài miền hợp lệ;
- outlier và các lần thay đổi cấu trúc bất thường;
- định dạng không thống nhất giữa các nguồn.

### 5.3 Kiểm tra quan hệ

- khóa chính có thực sự duy nhất và không null không;
- khóa ngoại có bản ghi cha tương ứng không;
- quan hệ thực tế là một-một, một-nhiều hay nhiều-nhiều;
- số dòng thay đổi thế nào trước và sau join;
- tổng KPI có bị nhân lên sau join không;
- bảng nào là nguồn chi tiết và bảng nào là dữ liệu tổng hợp hoặc dẫn xuất.

Không nên mặc định dataset “bẩn”. Chỉ kết luận có lỗi khi có bằng chứng đo đếm được và phải phân biệt
lỗi dữ liệu với hiện tượng nghiệp vụ hợp lệ.

---

## 6. Tái tạo và đối soát KPI

Tên cột chưa đủ để xác định ý nghĩa của KPI. Cần tìm công thức thực sự sinh ra chỉ số.

Ví dụ các công thức thường gặp:

```text
Gross Revenue = Σ(quantity × unit_price)
COGS          = Σ(quantity × unit_cost)
Gross Profit  = Gross Revenue − COGS
AOV           = Revenue / số đơn hàng
Return Rate   = số đơn hoặc dòng hàng bị trả / số đơn hoặc dòng hàng đủ điều kiện
```

Khi đối soát, cần xác minh:

- Revenue là gross hay net?
- Discount đã được trừ hay chỉ được lưu để tham khảo?
- Đơn hủy và đơn hoàn trả có được tính không?
- COGS là chi phí tại thời điểm bán hay chi phí kế toán hoàn chỉnh?
- Tử số và mẫu số của một tỷ lệ có cùng grain và cùng phạm vi không?
- Tổng tính từ giao dịch có khớp bảng báo cáo theo ngày hoặc tháng không?
- Sai lệch là do công thức, filter, join hay thời điểm ghi nhận?

Đối soát thành công giúp tìm ra **luật sinh dữ liệu**. Nếu chưa khớp, phải ghi rõ sai lệch thay vì tự chọn
một công thức thuận tiện.

---

## 7. Thực hiện EDA theo câu hỏi nghiệp vụ

EDA không chỉ là histogram, heatmap hoặc thống kê mô tả. Mỗi phần phân tích nên theo cấu trúc:

> Khái niệm → Công thức → Bằng chứng EDA → Ý nghĩa kinh doanh → Giới hạn kết luận

### 7.1 Nhóm câu hỏi thường dùng

**Kết quả kinh doanh**

- Doanh thu, chi phí và lợi nhuận thay đổi thế nào theo thời gian?
- Có mùa vụ, đứt gãy cấu trúc hoặc giai đoạn bất thường không?
- Tăng trưởng đến từ số đơn, số lượng trên mỗi đơn hay giá trung bình?

**Sản phẩm và khuyến mãi**

- Sản phẩm nào bán nhiều nhưng biên lợi nhuận thấp?
- Promotion gắn với đơn hàng hay dòng hàng?
- Khuyến mãi đi cùng thay đổi về số lượng, doanh thu và lợi nhuận như thế nào?

**Khách hàng**

- Khách hàng mới và khách hàng quay lại đóng góp ra sao?
- Hành vi có khác theo nhóm khách hàng hoặc khu vực không?
- Có dấu hiệu tập trung doanh thu vào một nhóm nhỏ khách hàng không?

**Vận hành**

- Giao hàng mất bao lâu và tỷ lệ trễ là bao nhiêu?
- Return tập trung ở sản phẩm, khu vực hay phương thức vận chuyển nào?
- Tồn kho có dấu hiệu thiếu hàng hoặc dư hàng không?

**Mối liên hệ giữa các hiện tượng**

- Giao hàng trễ có đi cùng review thấp không?
- Web traffic có đi cùng doanh thu cao hơn không?
- Promotion có đi cùng thay đổi tỷ lệ return không?

Các câu hỏi “có đi cùng” chỉ mô tả mối liên hệ. Chúng chưa chứng minh rằng một yếu tố gây ra yếu tố
còn lại.

---

## 8. Tách bằng chứng, diễn giải và nguyên nhân

Một kết luận tốt cần ghi rõ nó đang ở tầng nào:

| Tầng kết luận | Ý nghĩa | Ví dụ |
|---|---|---|
| Quan sát | Điều đo trực tiếp được từ dữ liệu | Doanh thu tháng B thấp hơn tháng A 20% |
| Diễn giải | Ý nghĩa hợp lý rút ra từ quan sát | Giai đoạn B có hiệu quả bán hàng thấp hơn |
| Giả thuyết nguyên nhân | Lời giải thích cần kiểm chứng thêm | Có thể do hết hàng hoặc chiến dịch kém hiệu quả |
| Quan hệ nhân quả | Nguyên nhân đã được chứng minh bằng thiết kế phù hợp | Chiến dịch làm tăng doanh thu trong thử nghiệm đối chứng |

Không được biến “hai biến cùng thay đổi” thành kết luận nhân quả. Nếu dataset không chứa giá đối thủ,
ngân sách quảng cáo hoặc lịch sự kiện, cũng không được dùng những yếu tố đó làm nguyên nhân chắc chắn.

---

## 9. Sản phẩm bàn giao sau khi hiểu dữ liệu

Một vòng khám phá hoàn chỉnh thường tạo ra:

1. **Business flow** — câu chuyện vận hành từ đầu đến cuối.
2. **Data inventory** — danh sách nguồn, grain, khóa và phạm vi dữ liệu.
3. **Data dictionary** — ý nghĩa nghiệp vụ của bảng và cột.
4. **Relationship map** — quan hệ và cardinality giữa các đối tượng.
5. **KPI dictionary** — tên chỉ số, công thức, grain, filter và giới hạn.
6. **EDA notebook** — bằng chứng có thể chạy lại được.
7. **Data-quality report** — vấn đề, mức ảnh hưởng và cách xử lý đề xuất.
8. **Business findings** — phát hiện có bằng chứng và giá trị sử dụng.
9. **Assumption log** — giả định chưa được xác nhận.
10. **Question backlog** — câu hỏi cần stakeholder hoặc nguồn dữ liệu khác trả lời.
11. **Next-step recommendation** — dashboard, thiết kế dữ liệu, forecasting hoặc thử nghiệm tiếp theo.

Tài liệu diễn giải và notebook bằng chứng nên đi thành cặp: mỗi khẳng định định lượng quan trọng cần có
phép kiểm tra có thể chạy lại.

---

## 10. Checklist tự đánh giá

Trước khi nói rằng đã hiểu dataset, cần tự trả lời được:

### Business

- [ ] Dataset mô tả hoạt động kinh doanh nào?
- [ ] Ai tạo ra dữ liệu và dữ liệu được tạo ở bước vận hành nào?
- [ ] Người dùng kết quả phân tích cần đưa ra quyết định gì?
- [ ] Đối tượng, sự kiện và vòng đời nghiệp vụ chính là gì?

### Data

- [ ] Đã kiểm kê tất cả nguồn dữ liệu chưa?
- [ ] Một dòng trong từng bảng đại diện cho điều gì?
- [ ] Khóa và quan hệ đã được kiểm chứng bằng dữ liệu chưa?
- [ ] Join có gây nhân bản dòng hoặc KPI không?
- [ ] Đã xác định khoảng thời gian và phạm vi bao phủ chưa?

### KPI và EDA

- [ ] KPI được tính theo công thức nào và ở grain nào?
- [ ] Có thể tái tạo bảng tổng hợp từ dữ liệu chi tiết không?
- [ ] EDA đang trả lời câu hỏi nghiệp vụ nào?
- [ ] Kết luận có số liệu và phép kiểm tra hỗ trợ không?
- [ ] Đã phân biệt tương quan với nhân quả chưa?

### Giao tiếp kết quả

- [ ] Có thể kể lại toàn bộ dataset bằng một câu chuyện đơn giản không?
- [ ] Đã ghi rõ giới hạn và giả định chưa?
- [ ] Đã chỉ ra phát hiện nào có thể dẫn tới hành động chưa?
- [ ] Người khác có thể chạy lại bằng chứng không?

---

## 11. Mẫu ghi chú ngắn cho một dataset mới

Có thể dùng khung sau trong lần phân tích tiếp theo:

```markdown
# Tổng quan dataset

## 1. Bài toán kinh doanh
- Mục tiêu:
- Người sử dụng kết quả:
- Quyết định cần hỗ trợ:
- Phạm vi:

## 2. Câu chuyện vận hành
- Tác nhân:
- Sự kiện chính:
- Trình tự vận hành:

## 3. Bản đồ dữ liệu
| Nguồn | Ý nghĩa | Grain | Khóa | Phạm vi thời gian |
|---|---|---|---|---|

## 4. KPI
| KPI | Công thức | Grain | Filter | Giới hạn |
|---|---|---|---|---|

## 5. Bằng chứng EDA
- Quan sát:
- Số liệu hỗ trợ:
- Ý nghĩa kinh doanh:
- Giới hạn:

## 6. Vấn đề chất lượng dữ liệu
- Vấn đề:
- Bằng chứng:
- Ảnh hưởng:
- Hướng xử lý:

## 7. Giả thuyết và câu hỏi còn mở
- Giả thuyết chưa kiểm chứng:
- Thông tin cần stakeholder xác nhận:

## 8. Đề xuất bước tiếp theo
- Phân tích hoặc sản phẩm tiếp theo:
- Giá trị kỳ vọng:
```

---

## Kết luận

Một dataset được xem là đã hiểu khi có thể giải thích bằng lời đơn giản:

> Ai làm gì, khi nào, tạo ra bản ghi nào, tiền hoặc KPI được tính thế nào, các nguồn nối với nhau ra sao
> và dữ liệu giúp doanh nghiệp quyết định điều gì?

Nếu chưa trả lời được các câu hỏi đó thì chưa nên vội xây model, dashboard hoặc database. Phân tích tốt
bắt đầu từ nghiệp vụ, được kiểm chứng bằng dữ liệu và kết thúc bằng một quyết định có thể hành động.
