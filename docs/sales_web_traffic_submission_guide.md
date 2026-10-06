# Hướng dẫn `sales`, `web_traffic`, `sample_submission` và `submission`

## Mục lục

1. [Mục tiêu và phạm vi](#1-mục-tiêu-và-phạm-vi)
2. [Câu chuyện vận hành](#2-câu-chuyện-vận-hành)
3. [Bằng chứng trên snapshot hiện tại](#3-bằng-chứng-trên-snapshot-hiện-tại)
4. [`sales.csv`: target lịch sử](#4-salescsv-target-lịch-sử)
5. [`web_traffic.csv`: tín hiệu website lịch sử](#5-web_trafficcsv-tín-hiệu-website-lịch-sử)
6. [`sample_submission.csv`: contract đầu ra](#6-sample_submissioncsv-contract-đầu-ra)
7. [`submission.csv`: kết quả do model sinh](#7-submissioncsv-kết-quả-do-model-sinh)
8. [Quy trình sử dụng đúng](#8-quy-trình-sử-dụng-đúng)
9. [Code validation tham khảo](#9-code-validation-tham-khảo)
10. [Giới hạn và điều không được suy diễn](#10-giới-hạn-và-điều-không-được-suy-diễn)

## 1. Mục tiêu và phạm vi

Tài liệu này giải thích bốn file thường bị nhầm vai trò:

```text
data/sales.csv
data/web_traffic.csv
data/sample_submission.csv
data/submission.csv
```

Mục tiêu là trả lời bốn câu hỏi:

1. Một dòng trong mỗi file đại diện cho điều gì?
2. Vì sao các file được tách riêng và không có cùng vai trò?
3. Cần clean/validate chúng như thế nào?
4. Dùng chúng ra sao để tạo file dự báo mà không gây leakage?

Trạng thái triển khai hiện tại:

- `sales.csv`, `web_traffic.csv`, `sample_submission.csv` là file trong bộ dữ liệu;
- `submission.csv` là output do `notebooks/04_forecasting/baseline.ipynb` sinh ra;
- pipeline Silver local hiện mới được triển khai cho `order_items.csv`;
- chưa có script Silver local riêng cho `sales.csv` hoặc `web_traffic.csv`;
- các bước cleaning trong tài liệu này là contract/quy trình cần áp dụng khi mở rộng pipeline.

## 2. Câu chuyện vận hành

Trong một ngày lịch sử, website có lượt truy cập và cửa hàng phát sinh giao dịch. Hai hiện tượng đó
được quan sát ở cùng grain ngày nhưng đến từ hai nguồn khác nhau:

```text
Website trong ngày ──> web_traffic.csv
Giao dịch trong ngày ──> orders + order_items + products ──> sales.csv
```

Model học quan hệ trong lịch sử để dự báo hai target tương lai:

```text
Lịch sử                                             Tương lai
2012-07-04 ─────────────── 2022-12-31               2023-01-01 ───── 2024-07-01

sales.csv        ─┐
                  ├─> train/validate model ─> dự báo ─> submission.csv
web_traffic.csv  ─┘                          ngày lấy từ sample_submission.csv
```

Điểm quan trọng:

- `sales.csv` chứa target actual lịch sử;
- `web_traffic.csv` chỉ là tín hiệu lịch sử, không phải giao dịch;
- `sample_submission.csv` định nghĩa các ngày và schema phải nộp;
- `submission.csv` chứa dự báo do model tạo ra.

## 3. Bằng chứng trên snapshot hiện tại

Các con số dưới đây được kiểm tra trực tiếp trên dữ liệu local ngày 2026-08-19:

| File | Số dòng × cột | Grain | Khoảng ngày | Missing | Duplicate ngày |
|---|---:|---|---|---:|---:|
| `sales.csv` | 3.833 × 3 | Một ngày actual | 2012-07-04 → 2022-12-31 | 0 | 0 |
| `web_traffic.csv` | 3.652 × 7 | Một ngày traffic | 2013-01-01 → 2022-12-31 | 0 | 0 |
| `sample_submission.csv` | 548 × 3 | Một ngày cần dự báo | 2023-01-01 → 2024-07-01 | 0 | 0 |
| `submission.csv` | 548 × 3 | Một ngày dự báo | 2023-01-01 → 2024-07-01 | 0 | 0 |

Cả bốn khoảng thời gian đều liên tục, không thiếu ngày bên trong khoảng riêng của chúng.

`sample_submission.csv` và `submission.csv` trong checkout hiện tại giống nhau byte-for-byte, cùng
SHA-256:


```text
1C0C574C3BC0EDAB5B053FB21C0CBB67393316D206503E14FBE4B17B9CE41ABA
```

Đây là quan sát về trạng thái file hiện tại, không phải quy tắc bền vững. Sau khi chạy model khác,
`submission.csv` có thể và thường phải khác file mẫu.

## 4. `sales.csv`: target lịch sử

### 4.1. Grain và khóa

Một dòng là tổng Revenue và COGS của một ngày lịch sử.

```text
Date,Revenue,COGS
2012-07-04,5123547.94,3982991.19
```

Grain và khóa:

```text
Grain: một ngày actual
PK logic: Date
```

### 4.2. Ý nghĩa cột

| Cột | Ý nghĩa | Vai trò |
|---|---|---|
| `Date` | Ngày bán hàng | Khóa ngày |
| `Revenue` | Gross Revenue của ngày | Target dự báo |
| `COGS` | Cost of Goods Sold của ngày | Target dự báo |

Trong dataset này:

```text
Revenue(d) = Σ(order_items.quantity × order_items.unit_price)
COGS(d)    = Σ(order_items.quantity × products.cogs)
```

`Revenue` là gross, không trừ `discount_amount`, không trừ refund và không lọc theo order status.
Nó khác với `payments.payment_value`, vốn gần với số tiền net sau discount.

`COGS` là giá vốn sản phẩm theo định nghĩa cuộc thi. Nó chưa bao gồm shipping, marketing, lương,
kho vận hành hoặc refund; vì vậy không nên gọi đây là tổng chi phí kế toán.

### 4.3. Vì sao `sales` là dữ liệu dẫn xuất?

File có thể tái tạo từ giao dịch:

```sql
SELECT o.order_date,
       SUM(oi.quantity * oi.unit_price) AS revenue,
       SUM(oi.quantity * p.cogs)        AS cogs
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN products p ON p.product_id = oi.product_id
GROUP BY o.order_date;
```

Vì vậy trong mô hình quan hệ chuẩn hóa, `sales` phù hợp làm `daily_sales` view hơn là một bảng nguồn
sự thật độc lập. Nếu vừa lưu giao dịch vừa lưu bảng tổng hợp mà không reconcile, hai nơi có thể lệch.

### 4.4. Cách clean và validate `sales`

Các kiểm tra bắt buộc:

1. Header chính xác là `Date, Revenue, COGS`.
2. `Date` parse được, unique, tăng liên tục theo ngày.
3. Đúng 3.833 ngày từ `2012-07-04` đến `2022-12-31` đối với snapshot hiện tại.
4. `Revenue`, `COGS` không null, hữu hạn và không âm.
5. Tiền giữ precision hai chữ số; trong Silver nên dùng `DECIMAL`, không dùng float làm source of truth.
6. Reconcile với tổng từ `orders × order_items × products` theo ngày.
7. Không trừ discount/refund hoặc lọc status nếu mục tiêu là khớp định nghĩa chính thức của file.

Outlier Revenue/COGS nên được gắn cờ để phân tích, không tự động xóa. Một ngày cao bất thường có thể
là campaign thật; một ngày có `COGS > Revenue` có thể liên quan promotion chứ chưa chắc là lỗi nhập.

## 5. `web_traffic.csv`: tín hiệu website lịch sử

### 5.1. Grain và khóa

Một dòng là traffic website tổng hợp của một ngày:

```text
date,sessions,unique_visitors,page_views,bounce_rate,avg_session_duration_sec,traffic_source
2013-01-01,9760,7253,39093,0.00514,102.9,organic_search
```

```text
Grain: traffic tổng hợp của một ngày
PK logic: date
```

### 5.2. Ý nghĩa cột

| Cột | Ý nghĩa quan sát được | Kiểm tra phù hợp |
|---|---|---|
| `date` | Ngày ghi nhận traffic | Date hợp lệ, unique |
| `sessions` | Số session trong ngày | Số nguyên không âm |
| `unique_visitors` | Số visitor riêng biệt | `0 <= unique_visitors <= sessions` |
| `page_views` | Tổng lượt xem trang | Số nguyên không âm |
| `bounce_rate` | Bounce rate theo nguồn | Hữu hạn, trong `[0,1]` |
| `avg_session_duration_sec` | Thời lượng session trung bình | Hữu hạn, không âm |
| `traffic_source` | Một nhãn nguồn traffic của ngày | Không rỗng, category hợp lệ |

Snapshot hiện có sáu nhãn `traffic_source`:

| Nhãn | Số ngày |
|---|---:|
| `organic_search` | 1.090 |
| `paid_search` | 784 |
| `social_media` | 632 |
| `email_campaign` | 505 |
| `referral` | 375 |
| `direct` | 266 |

### 5.3. Vì sao không có FK đến order/customer?

Nguồn không có:

```text
session_id
customer_id
order_id
```

Do đó không thể chứng minh session nào tạo ra đơn nào hoặc visitor nào là customer nào. Quan hệ sau
không tồn tại trong dữ liệu:

```text
WEB_TRAFFIC ──FK──> ORDER     -- sai
```

Có thể ghép `web_traffic.date = sales.Date` để so hai chuỗi theo thời gian, nhưng đó chỉ là
**analytical time alignment**, không phải FK giao dịch và không chứng minh traffic gây ra Revenue.

### 5.4. `traffic_source` không phải bảng phân rã theo channel

Mỗi ngày chỉ có đúng một dòng và một nhãn `traffic_source`. Vì vậy không được hiểu rằng file chứa số
traffic riêng cho sáu channel trong cùng một ngày. Không được group rồi SUM các dòng channel như một
bảng attribution vì các dòng đó không tồn tại.

Ý nghĩa chính xác của nhãn là “nguồn traffic được gán cho ngày” theo dữ liệu nguồn. Dataset không cho
biết đó là dominant source, campaign source hay một quy tắc gán khác; cần business owner xác nhận nếu
muốn diễn giải sâu hơn.

### 5.5. Cách clean và validate `web_traffic`

Các bước nên áp dụng:

1. Kiểm tra đúng bảy cột và trim tên/giá trị chuỗi.
2. Parse `date`, bảo đảm unique và liên tục từ `2013-01-01` đến `2022-12-31`.
3. Parse `sessions`, `unique_visitors`, `page_views` thành integer không âm.
4. Kiểm tra `unique_visitors <= sessions`.
5. Kiểm tra `bounce_rate` hữu hạn và thuộc `[0,1]`; giữ nguyên unit, không tự nhân 100.
6. Kiểm tra `avg_session_duration_sec >= 0`.
7. Chuẩn hóa `traffic_source` thành category và cảnh báo nhãn ngoài sáu giá trị quan sát.
8. Gắn cờ outlier thay vì drop ngày có traffic cao.

`page_views >= sessions` đúng trên toàn snapshot hiện tại, nhưng đây mới là invariant quan sát được.
Chỉ nên nâng thành contract bắt buộc khi có xác nhận định nghĩa metric từ nguồn.

### 5.6. Có dùng làm feature dự báo được không?

Có thể dùng traffic lịch sử để nghiên cứu quan hệ với sales trong phần thời gian giao nhau. Tuy nhiên:

- `sales` bắt đầu từ `2012-07-04`, còn traffic bắt đầu từ `2013-01-01`;
- 181 ngày đầu của `sales` không có traffic;
- `web_traffic` dừng ở `2022-12-31`;
- vùng cần dự báo 2023–2024 không có traffic tương lai.

Khi join lịch sử, nên dùng left join từ `sales` và thêm `has_web_traffic` thay vì vô tình drop 181
ngày đầu. Khi dự báo tương lai, chỉ được dùng:

- calendar feature biết trước;
- lag/rolling feature tính hoàn toàn từ quá khứ;
- traffic tương lai nếu có một mô hình riêng tạo ra nó mà không dùng future actual.

Không được lấy trực tiếp traffic 2023–2024 vì file nguồn không có những giá trị này.

## 6. `sample_submission.csv`: contract đầu ra

### 6.1. Grain và vai trò

Một dòng là một ngày tương lai phải có dự báo:

```text
Date,Revenue,COGS
2023-01-01,2665507.20,2518885.15
```

```text
Grain: một ngày cần dự báo
PK logic: Date
```

File định nghĩa:

- 548 ngày cần nộp;
- thứ tự ngày;
- tên và thứ tự ba cột `Date, Revenue, COGS`;
- format output mà hệ thống chấm mong đợi.

### 6.2. Vì sao các giá trị có sẵn không phải actual?

Khoảng ngày của sample bắt đầu sau ngày cuối cùng của lịch sử. Không có order tương lai tương ứng để
xác nhận các con số này. Giá trị `Revenue`, `COGS` trong sample phải được xem là placeholder hoặc
baseline mẫu, không phải ground truth.

Khi xây feature tương lai, chỉ lấy `Date` từ sample:

```python
future = sample_submission[["Date"]].copy()
```

Không dùng hai cột target có sẵn để train, validate, làm lag hoặc đánh giá model. Làm vậy sẽ biến
khung output thành nhãn giả và gây leakage/đánh giá sai.

### 6.3. Cách validate sample

1. Header chính xác `Date, Revenue, COGS`.
2. Có đúng 548 dòng.
3. `Date` unique, liên tục từ `2023-01-01` đến `2024-07-01`.
4. Không giao ngày với `sales.csv`.
5. Không diễn giải `Revenue`, `COGS` của sample là actual.

Trong mô hình dữ liệu, file này có thể ánh xạ thành scaffold `daily_sales_forecast`, nhưng không có FK
tới future order vì các order đó chưa tồn tại.

## 7. `submission.csv`: kết quả do model sinh

### 7.1. Nguồn gốc

`submission.csv` không thuộc 14 file nguồn. Notebook `notebooks/04_forecasting/baseline.ipynb` tạo file theo luồng:

```python
submission = test[["Date", "Revenue_pred", "COGS_pred"]].rename(
    columns={"Revenue_pred": "Revenue", "COGS_pred": "COGS"}
)
submission["Date"] = submission["Date"].dt.strftime("%Y-%m-%d")
submission.to_csv("data/submission.csv", index=False)
```

Baseline hiện tại sử dụng:

- mức nền trung bình ngày của năm 2022;
- hệ số tăng trưởng hình học theo năm;
- seasonal profile trung bình theo `(month, day)`.

Baseline này chỉ là mốc so sánh. Repo đã ghi nhận việc gộp tăng trưởng toàn giai đoạn qua structural
break cuối 2018 là hạn chế; không nên xem đây là model cuối cùng.

### 7.2. Contract của output

File hợp lệ phải:

1. Có đúng ba cột theo thứ tự `Date, Revenue, COGS`.
2. Có đúng 548 dòng.
3. Có `Date` giống sample cả giá trị lẫn thứ tự.
4. Không có index CSV thừa.
5. Dự báo là số hữu hạn, không missing.
6. Dự báo không âm theo logic nghiệp vụ.
7. Làm tròn Revenue/COGS đến hai chữ số thập phân trước khi ghi.

Không dùng `submission.csv` làm input cho pipeline cleaning hoặc làm target train. Đây là artifact có
thể tái tạo và nằm trong thư mục `data/` đã được gitignore.

## 8. Quy trình sử dụng đúng

### Bước 1 — Validate source

```text
sales.csv               -> target lịch sử sạch
web_traffic.csv         -> feature lịch sử sạch
sample_submission.csv   -> contract ngày tương lai
```

Fail pipeline khi sai header, duplicate ngày, thiếu ngày contract, parse lỗi hoặc vi phạm domain.
Outlier chỉ gắn cờ và báo cáo, không tự xóa.

### Bước 2 — Tạo bảng train theo ngày

```python
train = sales.merge(
    web_traffic,
    left_on="Date",
    right_on="date",
    how="left",
    validate="one_to_one",
)
train["has_web_traffic"] = train["date"].notna()
```

Không dùng inner join nếu chưa chủ động chấp nhận mất 181 ngày đầu.

### Bước 3 — Chia tập theo thời gian

Không random split chuỗi thời gian. Dùng backtest/validation theo mốc thời gian, ví dụ train đến
2020 rồi validate 2021–2022. Mọi rolling statistic hoặc encoding phải fit từ quá khứ của từng fold.

### Bước 4 — Tạo future feature

```python
future = sample_submission[["Date"]].copy()
future["month"] = future["Date"].dt.month
future["day"] = future["Date"].dt.day
future["day_of_year"] = future["Date"].dt.dayofyear
```

Không copy `Revenue`, `COGS` từ sample vào feature matrix. Không điền traffic tương lai bằng actual
không tồn tại.

### Bước 5 — Predict và ghi submission

```python
submission = sample_submission[["Date"]].copy()
submission["Revenue"] = revenue_prediction
submission["COGS"] = cogs_prediction
submission[["Revenue", "COGS"]] = submission[["Revenue", "COGS"]].round(2)
submission.to_csv("data/submission.csv", index=False)
```

### Bước 6 — Validate output trước khi nộp

So header, row count, thứ tự ngày, null, infinity, số âm và precision. Không coi việc file ghi thành
công là đủ; output có thể đúng cú pháp nhưng sai ngày hoặc chứa target copy từ sample.

## 9. Code validation tham khảo

Đoạn code sau chạy từ root repository và chỉ đọc dữ liệu:

```python
from pathlib import Path

import numpy as np
import pandas as pd


DATA = Path("data")


def assert_daily_dates(frame, column, start, end, expected_rows):
    dates = pd.to_datetime(frame[column], errors="raise")
    expected = pd.date_range(start, end, freq="D")

    assert len(frame) == expected_rows
    assert not dates.duplicated().any()
    assert dates.equals(pd.Series(expected, name=column))
    return dates


sales = pd.read_csv(DATA / "sales.csv")
assert list(sales.columns) == ["Date", "Revenue", "COGS"]
sales["Date"] = assert_daily_dates(
    sales, "Date", "2012-07-04", "2022-12-31", 3_833
)
assert sales[["Revenue", "COGS"]].notna().all().all()
assert np.isfinite(sales[["Revenue", "COGS"]]).all().all()
assert sales[["Revenue", "COGS"]].ge(0).all().all()


traffic = pd.read_csv(DATA / "web_traffic.csv")
assert list(traffic.columns) == [
    "date",
    "sessions",
    "unique_visitors",
    "page_views",
    "bounce_rate",
    "avg_session_duration_sec",
    "traffic_source",
]
traffic["date"] = assert_daily_dates(
    traffic, "date", "2013-01-01", "2022-12-31", 3_652
)
assert traffic[["sessions", "unique_visitors", "page_views"]].ge(0).all().all()
assert traffic["unique_visitors"].le(traffic["sessions"]).all()
assert traffic["bounce_rate"].between(0, 1).all()
assert traffic["avg_session_duration_sec"].ge(0).all()
assert traffic["traffic_source"].str.strip().ne("").all()


sample = pd.read_csv(DATA / "sample_submission.csv")
assert list(sample.columns) == ["Date", "Revenue", "COGS"]
sample["Date"] = assert_daily_dates(
    sample, "Date", "2023-01-01", "2024-07-01", 548
)
assert set(sales["Date"]).isdisjoint(set(sample["Date"]))


submission = pd.read_csv(DATA / "submission.csv")
assert list(submission.columns) == ["Date", "Revenue", "COGS"]
submission["Date"] = pd.to_datetime(submission["Date"], errors="raise")
assert submission["Date"].equals(sample["Date"])
assert submission[["Revenue", "COGS"]].notna().all().all()
assert np.isfinite(submission[["Revenue", "COGS"]]).all().all()
assert submission[["Revenue", "COGS"]].ge(0).all().all()

print("SALES/TRAFFIC/SUBMISSION VALIDATION PASSED")
```

Đây là validation tối thiểu. Reconciliation `sales` với giao dịch và kiểm tra leakage của feature cần
được thực hiện riêng vì chúng phụ thuộc pipeline/model cụ thể.

## 10. Giới hạn và điều không được suy diễn

### Quan sát đã kiểm chứng

- `sales` có 3.833 ngày actual liên tục.
- `web_traffic` có 3.652 ngày liên tục và bắt đầu muộn hơn `sales` 181 ngày.
- `sample_submission` có 548 ngày tương lai, không giao với lịch sử.
- `sales.Revenue` là gross và có thể tái tạo từ order item.
- `web_traffic` không có khóa session/customer/order.
- sample và submission hiện tại giống nhau byte-for-byte.

### Không được suy diễn

- Không gọi giá trị sample là future actual.
- Không gọi phép join traffic-sales theo ngày là FK hay conversion attribution.
- Không kết luận `traffic_source` là dominant channel nếu chưa có metadata xác nhận.
- Không xem tương quan traffic-Revenue là quan hệ nhân quả.
- Không dùng traffic tương lai không tồn tại làm feature.
- Không coi COGS của dataset là toàn bộ chi phí kế toán.
- Không coi baseline hiện tại là model production hoặc model cuối cùng.

## Tài liệu liên quan

- [`business_data_notes.md`](business_data_notes.md): câu chuyện business và quy tắc quan hệ.
- [`data-dictionary.md`](data-dictionary.md): kiểu, cardinality và mapping từng cột.
- [`data_business_analysis_workflow_results.md`](data_business_analysis_workflow_results.md): bằng chứng EDA và reconciliation.
- [`../notebooks/04_forecasting/baseline.ipynb`](../notebooks/04_forecasting/baseline.ipynb): baseline tạo `submission.csv`.
- [`../scripts/build/build_silver.py`](../scripts/build/build_silver.py): cleaning + đối soát đã triển khai cho cả 14 nguồn (Silver 3NF).
