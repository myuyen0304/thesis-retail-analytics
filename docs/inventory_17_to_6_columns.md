# Vì sao `inventory.csv` có 17 cột nhưng `inventory_snapshot` chỉ giữ 6 cột?

## 1. Câu trả lời ngắn

Không có 11 cột bị mất một cách tùy tiện. `inventory.csv` là file nguồn phẳng gồm cả dữ kiện kho,
thuộc tính sản phẩm, thuộc tính lịch, chỉ số tính sẵn và một cột hằng số. Bảng lõi 3NF
`inventory_snapshot` chỉ giữ **6 dữ kiện độc lập tại đúng grain của tồn kho**; các cột còn lại được:

- lấy lại bằng join;
- tính lại từ cột gốc;
- hoặc loại vì không mang thông tin.

```text
6 cột giữ lại
+ 3 cột chuyển sang bảng sản phẩm
+ 2 cột tính từ ngày
+ 5 cột chỉ số dẫn xuất
+ 1 cột hằng số
= 17 cột nguồn
```

File nguồn `data/inventory.csv` vẫn được giữ nguyên. Việc rút từ 17 xuống 6 chỉ áp dụng cho bảng
lõi chuẩn hóa, không phải xóa dữ liệu gốc.

---

## 2. Một dòng của `inventory.csv` đại diện cho điều gì?

Một dòng biểu diễn:

> Trạng thái tồn kho của **một sản phẩm** tại **một ngày snapshot cuối tháng**.

Grain và khóa:

```text
grain = một (snapshot_date × product_id)
PK    = (snapshot_date, product_id)
```

Dữ liệu có 60.247 dòng và khóa tổ hợp này không có dòng trùng.

Ví dụ dòng đầu của file:

```text
snapshot_date   = 2022-10-31
product_id      = 1
stock_on_hand   = 3
units_received  = 1
units_sold      = 1
stockout_days   = 2
days_of_supply  = 90.0
fill_rate       = 0.9333
stockout_flag   = 1
overstock_flag  = 0
reorder_flag    = 0
sell_through_rate = 0.25
product_name    = DragonWear MA-01
category        = Casual
segment         = All-weather
year            = 2022
month           = 10
```

---

## 3. Bản đồ đầy đủ của 17 cột

| Nhóm | Cột nguồn | Đi đâu trong mô hình? | Lý do |
|---|---|---|---|
| Dữ kiện kho độc lập | `snapshot_date` | `inventory_snapshot.snapshot_date` | Vế thứ nhất của PK |
| Dữ kiện kho độc lập | `product_id` | `inventory_snapshot.product_id` | Vế thứ hai của PK và FK tới `product` |
| Dữ kiện kho độc lập | `stock_on_hand` | Giữ trong `inventory_snapshot` | Không suy ra được từ một cột còn lại |
| Dữ kiện kho độc lập | `units_received` | Giữ trong `inventory_snapshot` | Measure nhập kho của kỳ |
| Dữ kiện kho độc lập | `units_sold` | Giữ trong `inventory_snapshot` | Measure bán theo hệ vận hành kho |
| Dữ kiện kho độc lập | `stockout_days` | Giữ trong `inventory_snapshot` | Dữ kiện gốc để tính các chỉ số stockout |
| Thuộc tính sản phẩm | `product_name` | Lấy qua `product_id → product.product_name` | Chỉ phụ thuộc sản phẩm, không phụ thuộc ngày snapshot |
| Thuộc tính sản phẩm | `category` | Lấy qua `product → product_model.category` | Không lặp thuộc tính model ở mọi snapshot |
| Thuộc tính sản phẩm | `segment` | Lấy qua `product → product_model.segment` | Không lặp thuộc tính model ở mọi snapshot |
| Thuộc tính lịch | `year` | Tính từ `snapshot_date` | `EXTRACT(YEAR FROM snapshot_date)` |
| Thuộc tính lịch | `month` | Tính từ `snapshot_date` | `EXTRACT(MONTH FROM snapshot_date)` |
| Chỉ số dẫn xuất | `days_of_supply` | Tính khi đọc hoặc trong view | Khôi phục chính xác từ các measure gốc |
| Chỉ số dẫn xuất | `fill_rate` | Tính khi đọc hoặc trong view | Khôi phục chính xác từ `stockout_days` |
| Chỉ số dẫn xuất | `stockout_flag` | Tính khi đọc hoặc trong view | Chỉ là cờ của `stockout_days > 0` |
| Chỉ số dẫn xuất | `overstock_flag` | Tính khi đọc hoặc trong view | Chỉ là cờ của `days_of_supply > 90` |
| Chỉ số dẫn xuất | `sell_through_rate` | Tính khi đọc hoặc trong view | Khôi phục từ `units_sold` và `stock_on_hand` |
| Không mang thông tin | `reorder_flag` | Không lưu trong core | Cả 60.247 dòng đều bằng `0` |

---

## 4. Vì sao chỉ giữ 6 cột?

### 4.1 Ba cột sản phẩm đặt sai grain

Trong bảng nguồn, một sản phẩm có thể xuất hiện ở nhiều tháng nhưng `product_name`, `category` và
`segment` không đổi theo tháng:

```text
product_id → product_name, category, segment
```

Trong khi khóa của inventory là:

```text
(snapshot_date, product_id)
```

Ba thuộc tính trên chỉ phụ thuộc vào **một phần của khóa tổ hợp**, tức `product_id`. Nếu giữ chúng
trong inventory, cùng một tên/category/segment sẽ bị lặp lại tới 126 snapshot. Đây là phụ thuộc bộ
phận và là vấn đề 2NF.

Cách lấy lại:

```text
inventory_snapshot.product_id
    → product.product_id
    → product.product_name
    → product_model.category, product_model.segment
```

### 4.2 `year`, `month` đã nằm bên trong `snapshot_date`

```text
snapshot_date → year, month
```

Ví dụ `2022-10-31` luôn cho `year = 2022`, `month = 10`. Lưu cả ba làm phát sinh nhiều nguồn cho
cùng một sự thật; chẳng hạn `snapshot_date = 2022-10-31` nhưng `month = 11` là trạng thái mâu thuẫn
mà schema không nên cho phép.

### 4.3 Năm chỉ số được tính lại chính xác

Các công thức đã được kiểm trên toàn bộ 60.247 dòng bằng `np.isclose(atol=1e-9)`:

```text
stockout_flag = (stockout_days > 0)

days_of_supply = ROUND(
    stock_on_hand / (units_sold / 30),
    1
)

fill_rate = ROUND(
    1 - stockout_days / 30,
    4
)

sell_through_rate = ROUND(
    units_sold / (stock_on_hand + units_sold),
    4
)

overstock_flag = (days_of_supply > 90)
```

Lưu cả dữ kiện gốc lẫn kết quả tính làm xuất hiện nguy cơ lệch nhau sau cập nhật. Ví dụ nếu
`stockout_days` đổi từ 2 thành 0 nhưng quên đổi `stockout_flag`, cùng một dòng sẽ vừa nói “không có
ngày stockout” vừa nói “có stockout”. Tính chỉ số trong view giúp luôn dùng giá trị mới nhất.

### 4.4 `reorder_flag` không phân biệt được dòng nào

`reorder_flag` có đúng một giá trị duy nhất:

```text
0 trên 60.247 / 60.247 dòng
```

Cột này không giúp lọc, phân nhóm hay giải thích khác biệt giữa các snapshot. Loại nó khỏi core không
làm mất thông tin phân biệt. Nếu sau này có quy tắc reorder thật, nên tính lại từ quy tắc nghiệp vụ
đã được xác nhận thay vì khôi phục cột hằng số này.

---

## 5. Kiểm tra trực tiếp trên dòng ví dụ

Với:

```text
stock_on_hand = 3
units_sold    = 1
stockout_days = 2
```

Ta tính được:

```text
days_of_supply    = ROUND(3 / (1/30), 1) = 90.0
fill_rate         = ROUND(1 - 2/30, 4)   = 0.9333
stockout_flag     = (2 > 0)              = 1
sell_through_rate = ROUND(1/(3+1), 4)    = 0.25
overstock_flag    = (90.0 > 90)          = 0
```

Tất cả khớp dòng nguồn. Chú ý `overstock_flag` dùng dấu `>` chứ không phải `>=`.

---

## 6. Bảng lõi sau chuẩn hóa

```sql
CREATE TABLE inventory_snapshot (
    snapshot_date  DATE     NOT NULL,
    product_id     INTEGER  NOT NULL REFERENCES product,
    stock_on_hand  INTEGER  NOT NULL,
    units_received INTEGER  NOT NULL,
    units_sold     INTEGER  NOT NULL,
    stockout_days  SMALLINT NOT NULL,
    PRIMARY KEY (snapshot_date, product_id)
);
```

Đây là bảng lưu sự kiện gốc ở grain `(snapshot_date, product_id)`. Nó không nhằm thay thế giao diện
phân tích đầy đủ.

---

## 7. Khi cần đủ thông tin thì truy vấn thế nào?

### 7.1 Lấy lại thuộc tính sản phẩm

```sql
SELECT
    i.snapshot_date,
    i.product_id,
    p.product_name,
    pm.category,
    pm.segment,
    p.size,
    p.color,
    i.stock_on_hand,
    i.units_received,
    i.units_sold,
    i.stockout_days
FROM inventory_snapshot i
JOIN product p
  ON p.product_id = i.product_id
JOIN product_model pm
  ON pm.product_name = p.product_name;
```

### 7.2 Tạo view phục vụ phân tích

Có thể tạo một view `inventory_enriched` chứa:

```text
6 cột inventory_snapshot
+ product_name, category, segment, size, color
+ year, month
+ 5 chỉ số tính lại
```

View cho người phân tích cảm giác sử dụng một bảng rộng như CSV, trong khi dữ liệu lõi vẫn có một
nguồn sự thật duy nhất và không lưu dư thừa.

### 7.3 Năm chỉ số này thực sự được lưu ở đâu?

Câu trả lời phụ thuộc vào **tầng dữ liệu**. Không nên dùng một chữ “database” cho cả dữ liệu thô,
bảng lõi và lớp phục vụ phân tích.

| Tầng | Có chứa 5 cột không? | Có lưu vật lý không? | Vai trò |
|---|---|---|---|
| File nguồn `data/inventory.csv` | Có | Có, trong CSV | Bản xuất dữ liệu nguyên trạng nhận từ nguồn |
| `staging.inventory_raw` nếu triển khai staging | Nên có đủ 17 cột | Có | Lưu bản sao raw để truy vết và đối chiếu ETL |
| `core.inventory_snapshot` | Không | Có, nhưng chỉ 6 cột độc lập | Nguồn sự thật chuẩn hóa |
| View `analytics.inventory_enriched` | Có, dưới dạng biểu thức | **Không** lưu từng kết quả | Tính mỗi khi query |
| Materialized view, nếu sau này cần tối ưu | Có | Có bản cache vật lý | Phải refresh khi dữ liệu lõi thay đổi |

Vì vậy, trong thiết kế hiện tại:

```text
days_of_supply
fill_rate
stockout_flag
overstock_flag
sell_through_rate
```

không phải cột vật lý của `core.inventory_snapshot`. Chúng là phép tính có tên, được cung cấp qua
view hoặc viết trực tiếp trong câu `SELECT`.

Repository hiện tại mới mô tả thiết kế logical/DDL; chưa có PostgreSQL pipeline đã triển khai. Bảng
`staging.inventory_raw`, view analytics và materialized view ở trên là cách tổ chức đề xuất khi hiện
thực hóa database, không phải các object đang tồn tại sẵn trong project.

#### Vì sao `inventory.csv` vẫn có số ở các cột đó?

Điều **quan sát được** là các giá trị đã có sẵn trong CSV và cả năm cột khớp 100% với công thức khi
kiểm trên 60.247 dòng. Điều đó chứng minh chúng có thể tái tạo từ các cột gốc.

Điều **không được dataset cung cấp** là lineage của hệ thống nguồn: không có tài liệu cho biết các
con số được tính trong ứng dụng, kho dữ liệu hay lúc export CSV. Suy luận hợp lý nhất là file nguồn
là một bản xuất phẳng phục vụ phân tích nên phía tạo dữ liệu đã tính sẵn các KPI cho tiện sử dụng.
Đây là suy luận, không phải sự kiện đã được nguồn xác nhận.

Việc một cột xuất hiện trong CSV không bắt buộc bảng core phải lưu lại cột đó. Ví dụ một báo cáo có
thể chứa cả `quantity`, `unit_price` và `line_total`; bảng giao dịch vẫn có thể chỉ lưu hai đầu vào và
tính `line_total` khi đọc.

#### Ví dụ tạo view để query như cột bình thường

```sql
CREATE VIEW analytics.inventory_enriched AS
WITH calculated AS (
    SELECT
        i.*,
        ROUND(
            i.stock_on_hand::numeric
            / NULLIF(i.units_sold::numeric / 30, 0),
            1
        ) AS days_of_supply,
        ROUND(1 - i.stockout_days::numeric / 30, 4) AS fill_rate,
        CASE WHEN i.stockout_days > 0 THEN 1 ELSE 0 END AS stockout_flag,
        ROUND(
            i.units_sold::numeric
            / NULLIF(i.stock_on_hand + i.units_sold, 0),
            4
        ) AS sell_through_rate
    FROM core.inventory_snapshot i
)
SELECT
    calculated.*,
    CASE WHEN days_of_supply > 90 THEN 1 ELSE 0 END AS overstock_flag
FROM calculated;
```

Sau khi có view, người dùng query như thể năm chỉ số là cột bình thường:

```sql
SELECT
    snapshot_date,
    product_id,
    days_of_supply,
    fill_rate,
    stockout_flag,
    overstock_flag,
    sell_through_rate
FROM analytics.inventory_enriched
WHERE snapshot_date = DATE '2022-10-31';
```

Database sẽ đọc 6 cột gốc từ `core.inventory_snapshot`, thực hiện công thức rồi trả kết quả. Với
view thường, kết quả không được lưu thành năm cột vật lý sau khi câu query kết thúc.

#### Khi nào nên lưu vật lý bằng materialized view?

Chỉ nên cân nhắc khi dữ liệu rất lớn hoặc các dashboard gọi cùng phép tính liên tục và việc tính lại
trở thành nút thắt hiệu năng. Khi đó materialized view là một **bản cache có thể tái tạo**, không phải
nguồn sự thật mới. Cần quy định rõ lịch `REFRESH MATERIALIZED VIEW`; nếu không refresh, KPI có thể
cũ hơn bảng core.

Với 60.247 dòng của dataset hiện tại, view thường là cách đơn giản và dễ bảo vệ hơn: không dư thừa,
luôn nhất quán với dữ liệu gốc và chi phí tính toán nhỏ.

---

## 8. Điều gì thật sự bị mất và điều gì không?

| Cột | Có mất thông tin độc lập không? | Vì sao? |
|---|---|---|
| `product_name`, `category`, `segment` | Không | Lấy lại bằng FK và join |
| `year`, `month` | Không | Tính chính xác từ `snapshot_date` |
| Năm chỉ số dẫn xuất | Không | Tính chính xác từ 6 cột giữ lại |
| `reorder_flag` | Không có thông tin phân biệt để mất | Toàn bộ giá trị đều bằng 0 |

Nói chính xác hơn, thiết kế không cố “giữ nguyên hình dạng CSV”; nó cố giữ mọi **sự thật độc lập**
và tái tạo phần còn lại khi cần.

---

## 9. Câu trả lời ngắn khi bảo vệ

> `inventory.csv` có 17 cột vì file nguồn đã trộn dữ kiện kho, thuộc tính sản phẩm, thuộc tính lịch,
> chỉ số tính sẵn và một cột hằng số. Bảng `inventory_snapshot` chỉ giữ 6 dữ kiện độc lập ở grain
> `(snapshot_date, product_id)`. Ba thuộc tính sản phẩm lấy lại bằng join, `year` và `month` tính từ
> ngày, năm chỉ số được tái tạo chính xác bằng công thức, còn `reorder_flag` bị loại vì toàn bộ đều
> bằng 0. Vì vậy mô hình không mất thông tin nghiệp vụ độc lập; nó chỉ không lưu dữ liệu dư thừa.

## 10. Những điều không nên khẳng định quá mức

- Không nói “mọi cột tính được đều là vi phạm 3NF”. Việc bỏ chỉ số dẫn xuất còn dựa trên nguyên tắc
  không lưu kết quả có thể tính lại và tránh update anomaly.
- Không coi `units_sold` trong inventory là bản sao chắc chắn của `order_items`. Đây là measure của
  hệ vận hành kho và không reconcile hoàn toàn với dữ liệu giao dịch bán.
- Không tự suy đoán quy tắc reorder mới từ `reorder_flag`, vì nguồn chỉ cung cấp một cột toàn số 0.
- Các công thức trên là kết quả quan sát và kiểm chứng của dataset hiện tại; nếu hệ thống nghiệp vụ
  thay đổi định nghĩa KPI thì view cũng phải được cập nhật.

## 11. Nguồn kiểm chứng trong project

- `notebooks/02_design/normalization.ipynb` §3.1: phụ thuộc bộ phận của inventory.
- `notebooks/02_design/normalization.ipynb` §5: kiểm tra năm công thức dẫn xuất với dung sai `atol=1e-9`.
- `docs/normalized_schema.md` §3.1 và §5: lập luận chuẩn hóa và DDL.
- `docs/data-dictionary.md`: ánh xạ từng cột nguồn sang mô hình 3NF.
