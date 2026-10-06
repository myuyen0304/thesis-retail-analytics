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
├── notebooks/
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

(`data/submission.csv` là output do `notebooks/04_forecasting/baseline.ipynb` sinh ra, không có trong bộ tải về.)

---

## Cây thư mục

```
thesis-retail-analytics/
├── README.md · CLAUDE.md · requirements.txt · docker-compose.yml
├── data/                  (gitignore) 14 CSV nguồn — tải từ Drive
├── notebooks/             phân tích + bằng chứng cho docs/ (chạy với thư mục làm việc = root repo)
│   ├── 01_exploration/    eda, business_eda, full_data_exploration, dataset_storytelling_eda
│   ├── 02_design/         data_model (star), normalization (3NF), database_design_demo
│   ├── 03_cleaning/       full_dataset_cleaning
│   └── 04_forecasting/    baseline
├── scripts/               chạy từ root repo
│   ├── ingest/            ingest_raw.py      14 CSV → PostgreSQL schema raw
│   ├── build/             build_silver.py    → silver/ (3NF) · build_gold.py → warehouse/ (đối chứng dbt)
│   ├── verify/            verify_problem_to_kpi.py
│   └── docs_gen/          sinh hình / slide cho docs/
├── retail_dbt/            dbt: staging → intermediate → marts (star) → reporting (KPI 5 PS)
├── docs/                  tài liệu (*.md để phẳng)
│   ├── design/            *.mmd, relational diagram, diagrams/
│   ├── presentations/     *.pptx
│   └── references/        tài liệu tham khảo, sơ đồ pipeline
├── archive/databricks/    bản Databricks cũ — chỉ tham khảo, không chạy
├── .vscode/settings.json  cho notebook chạy từ root repo
└── silver/ · warehouse/   (gitignore) sinh lại được bằng scripts/build/
```

**Notebook đọc `data/` theo đường dẫn tương đối từ root repo.** VS Code đã cấu hình sẵn (`.vscode/settings.json`).
Dùng Jupyter Lab/Notebook thì kernel mặc định chạy ở thư mục của notebook: thêm `%cd ../..` ở cell đầu khi chạy tay,
đừng sửa `DATA = 'data'`.

---

## Bản đồ file

| File | Nội dung |
|---|---|
| `notebooks/01_exploration/eda.ipynb` | Tìm cấu trúc sinh dữ liệu — 5 phát hiện chính, không xây model |
| `notebooks/02_design/data_model.ipynb` | Kiểm chứng các quyết định trong `docs/star_schema.md` |
| `notebooks/02_design/normalization.ipynb` | Kiểm chứng các phụ thuộc hàm trong `docs/normalized_schema.md` |
| `notebooks/04_forecasting/baseline.ipynb` | Baseline seasonal average + trend — **có lỗi đã biết**, chỉ dùng làm mốc so sánh |
| `docs/star_schema_tu_ps.md` | Dẫn star schema từ 5 PS: PS → KPI → grain → fact → dimension, bus matrix |
| `docs/star_schema.md` | Dimensional model + ERD |
| `docs/normalized_schema.md` | Mô hình chuẩn hóa 1NF→3NF (19 bảng); §9 so sánh hai mô hình |
| `docs/` | Toàn bộ tài liệu business, EDA, data dictionary, schema và defense |
| `CLAUDE.md` | Bối cảnh project cho Claude Code — **đọc file này trước** |

**Convention:** file `.md` là phần *diễn giải*, notebook là phần *chứng minh chạy lại được*.
Mỗi khẳng định trong `.md` có một cell tương ứng trong notebook. Sửa một bên thì sửa cả bên kia.

---

## Làm việc nhóm

### Ai giữ file nào

| Người | Notebook phụ trách |
|---|---|
| myuyen | `notebooks/01_exploration/eda.ipynb`, `notebooks/02_design/data_model.ipynb`, `notebooks/02_design/normalization.ipynb`, `notebooks/04_forecasting/baseline.ipynb` |
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
