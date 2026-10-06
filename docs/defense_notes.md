# Kịch bản giải thích — data dictionary, ERD, relational diagram

Tài liệu chuẩn bị cho buổi nộp/bảo vệ. Mỗi câu trả lời gồm **ý nói ra miệng** (ngắn, 2–4 câu)
và **chỗ chỉ tay** để mở đúng mục khi được yêu cầu dẫn chứng.

Nguyên tắc chung khi trả lời: **mọi con số đều có một cell chạy lại được**. Nếu bị hỏi "số này ở
đâu ra", đừng giải thích bằng lời — mở notebook đúng mục và chạy lại.

---

## 0. Mở đầu 90 giây — nói trước khi bị hỏi

> "Em nộp ba tài liệu ở ba **mức trừu tượng khác nhau** của cùng một dữ liệu.
>
> **Data dictionary** mô tả dữ liệu *nguyên trạng* — 14 file, từng cột, kiểu, miền giá trị, vấn đề chất lượng.
> **ERD** là mô hình *khái niệm* — nghiệp vụ có 11 thực thể nào, liên hệ ra sao, chưa nói gì về bảng.
> **Relational diagram** là mô hình *logical* sau chuẩn hóa — 19 bảng đạt 3NF, có PK/FK và kiểu dữ liệu.
>
> Ba cái đọc theo thứ tự đó: cái sau là kết quả biến đổi của cái trước, và mỗi bước biến đổi đều có
> chứng minh chạy được trong notebook."

Ba câu đó chặn trước phần lớn câu hỏi "sao có nhiều sơ đồ thế".

---

## 1. Câu chắc chắn bị hỏi: ba thứ này khác nhau chỗ nào?

**Hỏi: ERD với relational diagram khác gì nhau? Nhìn đều là hình hộp nối với nhau.**

> Khác ở **mức trừu tượng**, không phải ở cách vẽ. ERD trả lời *nghiệp vụ có gì*; relational diagram
> trả lời *lưu thế nào trong CSDL quan hệ*. Ba dấu hiệu phân biệt cụ thể: ERD của em để nguyên quan
> hệ M:N `ORDER_ITEM ↔ PROMOTION` thành một đường, không có kiểu dữ liệu, và không có bảng nào do
> chuẩn hóa sinh ra. Relational diagram thì M:N đã thành bảng `order_item_promotion`, mọi cột đều có
> kiểu, và có thêm 5 bảng mà ERD không có.

📍 `normalized_schema.md` §1.1, khối **"Ba điều sơ đồ này cố ý làm khác §6"**

**Hỏi: có data dictionary rồi thì cần ERD làm gì?**

> Data dictionary mô tả **cột**, ERD mô tả **quan hệ**. Data dictionary nói `orders.zip` là số 5 chữ
> số, không null; nó không nói được rằng cột đó **trùng 100%** với `customers.zip` nên là dư thừa
> phi chuẩn hóa. Ngược lại ERD không nói được `bounce_rate` phi thực tế. Hai tài liệu không thay
> thế nhau vì trả lời hai loại câu hỏi khác nhau.

**Hỏi: đi từ ERD sang relational diagram bằng quy tắc nào?**

> Năm quy tắc chuẩn: thực thể mạnh → quan hệ; thực thể yếu → PK mượn của cha cộng cột phân biệt;
> 1:N → FK đặt ở phía N; 1:1 → FK kèm UNIQUE; M:N → bảng junction. Em ghi rõ mỗi quy tắc áp dụng ở
> chỗ nào, nên mọi bảng ở sơ đồ quan hệ đều truy được nguồn gốc về một thực thể trong ERD.

📍 `normalized_schema.md` **§6.1** — bảng 5 quy tắc, cột phải là chỗ đã áp dụng

---

## 2. Câu hỏi về ERD (§1.1)

**Hỏi: có 14 file mà sao chỉ 11 thực thể?**

> Ba file không phải thực thể nghiệp vụ. `web_traffic` là chuỗi quan sát tổng hợp theo ngày, đã bị
> gộp mất định danh trước khi tới tay — không có `session_id` để nối với đơn hàng nào.
> `sales.csv` là bảng tổng hợp suy ra được từ `order_items`, không phải nguồn sự thật.
> `sample_submission` là đầu ra của bài toán, phủ 2023–2024, giao với dữ liệu thật đúng **0 ngày**.

📍 `normalized_schema.md` §1.1, mục **"Vì sao `web_traffic` và `daily_sales_forecast` không có ở đây"**

**Hỏi: `ORDER_ITEM` là thực thể yếu nghĩa là gì?**

> Là thực thể không tồn tại độc lập và **không tự định danh được**. Một dòng hàng chỉ có nghĩa khi
> gắn với một đơn, và trong dữ liệu nguồn nó không có khóa: có **16 cặp `(order_id, product_id)`
> trùng nhau** — cùng đơn, cùng sản phẩm, khác số lượng và giá. Nên phải mượn `order_id` của đơn rồi
> thêm `line_number` để phân biệt cục bộ.

📍 `notebooks/02_design/normalization.ipynb` **§2.1** — cell in ra 32 dòng thuộc 16 đơn

**Hỏi: nếu vẫn dùng `(order_id, product_id)` làm khóa thì sao?**

> Mất thông tin thật, không phải bất tiện truy vấn. **4 dòng `returns` và 2 dòng `reviews`** sẽ không
> xác định được chúng trỏ vào dòng hàng nào. Và nó sinh ra lỗi giả: join bằng cặp đó làm fan-out
> thêm 4 dòng, khiến `RET-043492` hiện lên như vi phạm `return_quantity ≤ quantity`. Join đúng khóa
> thì **0 vi phạm / 39.939**.

📍 `notebooks/02_design/normalization.ipynb` **§6** — cell chạy cả hai nhánh join cạnh nhau

**Hỏi: sao vẽ M:N mà không tách bảng luôn cho gọn?**

> Vì `order_item_promotion` **không phải thực thể nghiệp vụ**. Nó sinh ra chỉ vì mô hình quan hệ
> không biểu diễn được M:N trực tiếp — đó là mối quan tâm mức logical. Nếu đưa nó vào ERD khái niệm
> thì em đã trộn hai mức, và mất luôn khả năng chỉ ra bước chuyển đổi.

**Hỏi: cardinality trên sơ đồ lấy từ đâu?**

> Đọc ra từ dữ liệu, không phải giả định. Ví dụ `ORDER → SHIPMENT` là 1:0..1 vì **80.878 đơn** không
> có bản ghi shipment; `CUSTOMER → ORDER` là 1:0..N vì **31.684 khách** chưa mua lần nào;
> `PRODUCT → ORDER_ITEM` là 1:0..N vì **814 sản phẩm** chưa bán lần nào.

📍 `normalized_schema.md` §1.1, bảng **"Bằng chứng cho cardinality"** — 8 dòng, mỗi dòng một nguồn

---

## 3. Câu hỏi về relational diagram và chuẩn hóa (§6, §8)

**Hỏi: 2NF chỉ vi phạm ở đúng 1 bảng — có phải em kiểm sót không?**

> Không, đó là lý do **cấu trúc**: 2NF *không thể* bị vi phạm nếu khóa chính chỉ có một cột. Trong
> 14 file thì chỉ `inventory` có khóa tổ hợp thật `(snapshot_date, product_id)` — và nó vi phạm ở
> **cả hai vế**: `product_name`/`category`/`segment` chỉ phụ thuộc `product_id`, còn `year`/`month`
> chỉ phụ thuộc `snapshot_date`.

📍 `normalized_schema.md` **§9.3**; chứng minh ở `notebooks/02_design/normalization.ipynb` §3

Nói thêm nếu bị đào sâu: hệ hiện đại hay dùng surrogate key đơn cột nên 2NF thường "có sẵn miễn phí" —
chỗ phải kiểm là bảng snapshot, bridge, junction mang thêm thuộc tính.

**Hỏi: `order_items` có `unit_price` phụ thuộc `product_id` — sao không phải vi phạm 2NF?**

> Vì nó **không** phụ thuộc. `unit_price` là giá **tại thời điểm bán**: trung vị 88 giá khác nhau
> cho mỗi sản phẩm, cao nhất 7.777 giá. Nó cần cả khóa, không phải một phần khóa. Em để phản chứng
> này trong bài vì đây đúng là chỗ dễ kết luận nhầm.

📍 `notebooks/02_design/normalization.ipynb` **§3.1** — mục "Phản chứng"

**Hỏi: `geography` — sao lại gọi là judgment call mà không làm dứt khoát theo 3NF?**

> Vì ở đây 3NF sách vở tạo ra rủi ro mới. `city` và `district` đều roll-up về `region` nhưng **cắt
> chéo nhau**: một city trải tới 19 district, một district trải tới 16 city. Tách chặt theo 3NF thì
> `region` tới được từ cùng một `zip` theo **hai đường**, mà schema không ép hai đường phải khớp.
> Em vẫn dùng phương án 3NF trong DDL vì đây là bài chuẩn hóa, nhưng ghi rõ production nên cân nhắc
> hướng ngược lại.

📍 `normalized_schema.md` **§4.5** — bảng so sánh hai phương án; số liệu ở `notebooks/02_design/normalization.ipynb` §4.5

Đây là câu đáng để chủ động nói ra: nó cho thấy hiểu **3NF là công cụ, không phải mục tiêu**.

**Hỏi: bỏ cột tính được có phải là chuẩn hóa không?**

> Không. Đây là hai nguyên tắc khác nhau hay bị gộp làm một. 3NF nói về **phụ thuộc hàm giữa các
> thuộc tính**; cột tính được từ cột khác là dạng dư thừa khác, bỏ vì nguyên tắc "không lưu cái
> tính được". Em tách hẳn thành mục riêng để không nhập nhằng.

📍 `normalized_schema.md` **§5**

**Hỏi: `inventory` từ 17 cột xuống 6 — chứng minh thế nào?**

> 5 cột là dẫn xuất, khớp **0 sai lệch trên 60.247 dòng** với dung sai `atol=1e-9`:
> `stockout_flag = stockout_days > 0`, `days_of_supply = ROUND(soh/(units_sold/30), 1)`,
> `fill_rate = ROUND(1 − stockout_days/30, 4)`,
> `sell_through_rate = ROUND(units_sold/(soh + units_sold), 4)`, `overstock_flag = days_of_supply > 90`.
> Cộng 5 cột bị 2NF chuyển đi và 1 cột chết `reorder_flag` (chỉ một giá trị) là 17 → 6.

📍 `notebooks/02_design/normalization.ipynb` **§5** — 5 dòng đều in `100.0% → BỎ`

**Hỏi: `sales.csv` sao lại thành view mà không phải bảng?**

> Vì nó tái tạo được chính xác từ `order_items × orders × products`, sai số tương đối tối đa
> **2,2e-16** cho Revenue và **1,0e-08** cho COGS trên cả 3.833 ngày. Công thức là
> `Σ quantity × unit_price` — **gross, không trừ `discount_amount`**, và **không lọc** `order_status`.
> Lưu nó thành bảng cơ sở là lưu lại thứ tính được, và mở đường cho hai giá trị khác nhau của cùng
> một đại lượng.

📍 `notebooks/02_design/normalization.ipynb` §5; chi tiết đầy đủ ở `notebooks/01_exploration/eda.ipynb` mục 1

**Hỏi: `payment` chỉ còn 1 cột — sao không xóa luôn bảng?**

> Đây là ví dụ gọn nhất cho *conceptual ≠ logical*. Thanh toán là khái niệm nghiệp vụ có thật nên nó
> phải có mặt ở ERD. Nhưng xuống logical thì `payment_method` trùng `orders` (lệch 0/646.945) và
> `payment_value` suy ra được 100%, nên chỉ còn `installments`. Thực thể **không biến mất, nó teo lại** —
> và chỉ nhìn thấy được điều đó khi có mức khái niệm để đối chiếu.

📍 `normalized_schema.md` §1.1, đoạn cuối mục ánh xạ 11 thực thể → 17 bảng

**Hỏi: cardinality vẽ 1:0..1 thì lấy gì đảm bảo?**

> Phải có ràng buộc đỡ, nếu không sơ đồ chỉ đang **mô tả dữ liệu hiện có** chứ không **ràng buộc dữ
> liệu tương lai**. `payment` và `shipment` thì `order_id` vừa là PK vừa là FK nên tự khắc duy nhất.
> `review` và `product_return` có PK riêng nên phải khai `UNIQUE (order_id, line_number)` — chỗ này
> tài liệu của em từng hụt thật ở `product_return`, đã bổ sung.

📍 `normalized_schema.md` **§6.1 quy tắc 4** — có ghi luôn chỗ từng thiếu

---

## 4. Câu hỏi về data dictionary

**Hỏi: data dictionary để làm gì, khác gì EDA?**

> EDA trả lời *dữ liệu nói lên điều gì*; data dictionary trả lời *dữ liệu này là gì*. Nó là hợp
> đồng mô tả: mỗi cột nghĩa là gì, kiểu gì, miền giá trị nào, null bao nhiêu, có bẫy gì khi dùng.
> Người mới vào nhóm đọc nó là dùng được dữ liệu ngay mà không phải đọc lại toàn bộ notebook.

**Hỏi: sao data dictionary không có notebook chứng minh như hai tài liệu kia?**

Đây là **điểm yếu thật**, nên trả lời thẳng thay vì chống chế:

> Convention của nhóm là mỗi khẳng định trong `.md` có một cell chạy lại được. `star_schema.md` và
> `normalized_schema.md` theo đúng convention đó; data dictionary thì chưa. Em đã đối chiếu thủ công
> toàn bộ số liệu trong đó với dữ liệu gốc và chúng khớp, nhưng phần chứng minh tự động thì còn nợ.

---

## 5. Câu hỏi bẫy — chuẩn bị sẵn

**Hỏi: sao project có tới mấy sơ đồ? Cái nào mới là đúng?**

> Đúng cả, vì chúng ở các mức và mục đích khác nhau: ERD khái niệm (§1.1), relational diagram 3NF
> (§6.2), và một mô hình chiều riêng trong `star_schema.md` cho workload phân tích.

⚠️ **Trước khi nộp phải xử lý:** `docs/erd.md` đang tự gọi mình là *"star/snowflake schema"* nhưng
nội dung là ERD của 14 bảng nguồn — trong khi `star_schema.md` mới là star schema thật. Nếu nộp cả
hai mà chưa sửa tiêu đề thì đây là câu hỏi **không có đường trả lời tốt**.

**Hỏi: star schema của em vi phạm 3NF đấy.**

> Vâng, và là **cố ý**. `dim_product` mang `category`/`segment` phẳng, `dim_order_junk` gộp 4 thuộc
> tính, `fact_daily_sales` lưu sẵn số tổng hợp — cả ba đều là vi phạm 3NF có chủ đích. Hai mô hình
> tối ưu cho hai thứ khác nhau: mô hình 3NF cho workload ghi, star schema cho workload đọc. Để trả
> lời "doanh thu theo region" thì 3NF cần **5 join**, star schema cần **2**.

📍 `normalized_schema.md` **§9.5** — bảng đối chiếu ba mô hình

**Hỏi: dữ liệu này chỉ đọc, chuẩn hóa để làm gì?**

Đây là câu khó nhất, và tài liệu đã chuẩn bị sẵn câu trả lời trung thực:

> Đúng, dữ liệu là 14 file CSV tĩnh, không có nghiệp vụ ghi. Update anomaly mà 3NF ngăn chặn ở đây là
> **giả định**, không phải rủi ro đang xảy ra — không ai đổi `category` của một sản phẩm trong 60.247
> dòng `inventory`, vì không ai đổi gì cả. Giá trị của bài chuẩn hóa ở đây là **khôi phục cấu trúc
> sinh dữ liệu**: nó chỉ ra chỗ nào là dư thừa, chỗ nào là cột tính được, chỗ nào là lỗi khóa.

📍 `normalized_schema.md` **§9.6**

**Hỏi: em có chỗ nào từng kết luận sai không?**

Đừng né — kể ra là điểm cộng, vì nó chứng minh quy trình có khả năng tự bắt lỗi:

> Có. `normalized_schema.md` §5 từng kết luận `fill_rate`, `sell_through_rate`, `overstock_flag` là
> measure độc lập không tính được. Sai cả ba. Mỗi cột lệch đúng **một chi tiết**: sai mẫu số, sai mẫu
> số, sai dấu `>=` thay vì `>`. Em phát hiện khi **đối chiếu chéo** với data dictionary do bạn cùng
> nhóm viết độc lập — bạn ấy ghi đúng công thức `fill_rate`. Sửa xong thì `inventory_snapshot` từ
> 9 cột xuống 6. Bài học em rút ra và đã viết vào tài liệu: gần-khớp là lý do **thử biến thể**, không
> phải bằng chứng cột độc lập; và mọi khẳng định "khớp 100%" phải ghi rõ dung sai.

📍 `normalized_schema.md` **§5.1** — có bảng liệt kê cả bốn công thức sai và số đọc ra

**Hỏi: dữ liệu có sạch không, có phải xử lý missing/outlier nhiều không?**

> Toàn vẹn tham chiếu **hoàn hảo: 0 orphan trên 14 quan hệ**. Đây là bài *khôi phục cấu trúc*, không
> phải bài *làm sạch dữ liệu*. Vấn đề nằm ở chỗ khác: khóa không hợp lệ, cột dẫn xuất, và 10 vấn đề
> chất lượng đã liệt kê thành rule khi load.

📍 `notebooks/02_design/data_model.ipynb` §3 và `star_schema.md` §6

---

## 6. Tra nhanh — hỏi gì thì mở cái gì

| Chủ đề | Diễn giải | Chứng minh |
|---|---|---|
| Ba mức mô hình | `normalized_schema.md` §1.1 | — |
| ERD khái niệm | §1.1 (sơ đồ + bảng thuộc tính) | — |
| Cardinality | §1.1 "Bằng chứng cho cardinality" | `notebooks/02_design/normalization.ipynb` §6, `notebooks/02_design/data_model.ipynb` §3 |
| ERD → quan hệ | §6.1 (5 quy tắc) | — |
| Relational diagram | §6.2 | khớp 1:1 với DDL §8 |
| 1NF | §2 | `notebooks/02_design/normalization.ipynb` §2.1, §2.2 |
| 2NF | §3, §9.3 | `notebooks/02_design/normalization.ipynb` §3, §3.1 |
| 3NF | §4 | `notebooks/02_design/normalization.ipynb` §4.1–§4.5 |
| Cột dẫn xuất | §5, §5.1 | `notebooks/02_design/normalization.ipynb` §5 |
| DDL + ràng buộc | §8 | `notebooks/02_design/normalization.ipynb` §6 (13/13 CHECK đạt) |
| Quy mô 19 bảng | §7 | `notebooks/02_design/normalization.ipynb` §7 |
| So sánh 3NF ↔ star | §9.5, §9.6 | — |
| Star schema | `star_schema.md` | `notebooks/02_design/data_model.ipynb` |
| Từng cột, chất lượng dữ liệu | `docs/data-dictionary.md` | *(chưa có notebook)* |

---

## 7. Ba con số nên thuộc lòng

| | |
|---|---|
| **3.833 / 548** | số ngày lịch sử (2012-07-04 → 2022-12-31) / số ngày dự báo (2023-01-01 → 2024-07-01) |
| **11 → 17 → 19** | thực thể khái niệm → bảng từ 11 thực thể đó → cộng `web_traffic` và `daily_sales_forecast` |
| **0** | số orphan trên 14 quan hệ |
