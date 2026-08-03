# thesis-retail-analytics

Datathon 2026 Round 1 — dự báo `Revenue` và `COGS` theo ngày cho **2023-01-01 → 2024-07-01** (548 ngày),
dựa trên lịch sử **2012-07-04 → 2022-12-31** (3.833 ngày).

Giai đoạn hiện tại trên `main`: **khám phá dữ liệu + hiểu cấu trúc + thiết kế mô hình dữ liệu (ERD)**.
Chưa có preprocessing pipeline hay model — phần đó làm trên nhánh riêng.

---

## Setup lần đầu

```bash
git clone https://github.com/myuyen0304/thesis-retail-analytics.git
cd thesis-retail-analytics

python -m venv .venv
.venv\Scripts\activate          # Windows;  macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

> Dùng **pandas 3.x** (đúng như `requirements.txt`), không phải 2.x — hành vi dtype chuỗi khác nhau.

## Tải data

**Data KHÔNG nằm trong repo** (126MB, và tránh redistribute dataset của cuộc thi).

📁 **Link Google Drive:** `<DÁN LINK VÀO ĐÂY>`

Tải về rồi giải nén thành thư mục `data/` ngay tại root repo:

```
thesis-retail-analytics/
├── data/          ← ở đây
│   ├── orders.csv
│   └── ...
├── eda.ipynb
└── ...
```

Kiểm tra đủ **14 file nguồn**:

| File | Dòng × Cột | 1 dòng = |
|---|---|---|
| `customers.csv` | 121.930 × 7 | 1 khách hàng |
| `geography.csv` | 39.948 × 4 | 1 mã zip |
| `products.csv` | 2.412 × 8 | 1 SKU |
| `promotions.csv` | 50 × 10 | 1 đợt khuyến mãi |
| `orders.csv` | 646.945 × 8 | 1 đơn hàng |
| `order_items.csv` | 714.669 × 7 | 1 dòng hàng |
| `payments.csv` | 646.945 × 4 | 1 đơn hàng |
| `shipments.csv` | 566.067 × 4 | 1 lô giao |
| `returns.csv` | 39.939 × 7 | 1 lần trả hàng |
| `reviews.csv` | 113.551 × 7 | 1 đánh giá |
| `inventory.csv` | 60.247 × 17 | 1 (cuối tháng × SP) |
| `web_traffic.csv` | 3.652 × 7 | 1 ngày |
| `sales.csv` | 3.833 × 3 | 1 ngày — **target** |
| `sample_submission.csv` | 548 × 3 | 1 ngày — mẫu nộp bài |

(`data/submission.csv` là output do `baseline.ipynb` sinh ra, không có trong bộ tải về.)

---

## Bản đồ file

| File | Nội dung |
|---|---|
| `eda.ipynb` | Tìm cấu trúc sinh dữ liệu — 8 phát hiện chính, không xây model |
| `data_model.ipynb` | Kiểm chứng các quyết định trong `star_schema.md` |
| `normalization.ipynb` | Kiểm chứng các phụ thuộc hàm trong `normalized_schema.md` |
| `baseline.ipynb` | Baseline seasonal average + trend — **có lỗi đã biết**, chỉ dùng làm mốc so sánh |
| `star_schema.md` | Dimensional model + ERD |
| `normalized_schema.md` | Mô hình chuẩn hóa 1NF→3NF (19 bảng); §9 so sánh hai mô hình |
| `CLAUDE.md` | Bối cảnh project cho Claude Code — **đọc file này trước** |

**Convention:** file `.md` là phần *diễn giải*, notebook là phần *chứng minh chạy lại được*.
Mỗi khẳng định trong `.md` có một cell tương ứng trong notebook. Sửa một bên thì sửa cả bên kia.

---

## Làm việc nhóm

### Ai giữ file nào

| Người | Notebook phụ trách |
|---|---|
| myuyen | `eda.ipynb`, `data_model.ipynb`, `normalization.ipynb`, `baseline.ipynb` |
| *(bạn cùng nhóm)* | *(điền khi nhận việc)* |

### Vòng lặp hằng ngày

```bash
git checkout main && git pull        # LUÔN pull trước khi tạo nhánh mới
git checkout -b preprocess/<tên>     # <loại>/<tên>: eda, preprocess, model, docs

# ... làm việc ...

git status                           # kiểm tra: không có gì trong data/ bị staged
git add <file cụ thể>                # không dùng git add -A
git commit -m "mô tả ngắn gọn"
git push -u origin preprocess/<tên>
```

Rồi mở Pull Request trên GitHub → người kia review → merge vào `main`.

### Hai quy tắc bắt buộc với notebook

1. **Một notebook một chủ.** Hai người sửa cùng một `.ipynb` sẽ tạo conflict trong JSON mà git
   không merge được — file hỏng luôn. Cần đụng vào notebook của người kia thì nhắn trước.
2. **Không commit khi notebook đang chạy dở.** Chạy hết → save → đóng → rồi mới commit.

### Không bao giờ commit

`data/` · `.venv/` · `submission.csv` · output notebook đang chạy dở
