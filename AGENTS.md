# Repository Guidelines

## Cấu trúc dự án

Trọng tâm: DWH phân tích doanh thu. Đọc `CLAUDE.md` và `README.md` trước khi sửa.

- `retail_dbt/`: SQL theo tầng `staging`, `intermediate`, `marts`, `reporting`; kiểm thử trong `tests/`.
- `apps/retail_app/`: ứng dụng Streamlit; `dwh/` truy vấn, `views/` trang, `ui/` thành phần chung, `tests/` kiểm thử.
- `scripts/`: nạp dữ liệu, build, kiểm chứng và sinh tài liệu.
- `notebooks/`: khám phá, thiết kế, làm sạch, dự báo.
- `docs/`: tài liệu; `design/` chứa sơ đồ, `presentations/` chứa slide.
- `data/` chứa CSV nguồn; `silver/`, `warehouse/` chứa dữ liệu sinh lại được. `archive/databricks/` chỉ tham khảo.

## Cài đặt và chạy

Chạy tại root bằng PowerShell; chuẩn bị đủ 14 CSV trong `data/`.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
# Khởi động PostgreSQL; chờ healthy
docker compose up -d
# Nạp lại toàn bộ raw, sau đó dựng DWH và kiểm thử
.venv/Scripts/python.exe scripts/ingest/ingest_raw.py
.venv/Scripts/dbt.exe build --project-dir retail_dbt --profiles-dir retail_dbt --target postgres
# Chạy ứng dụng
.venv/Scripts/python.exe -m streamlit run apps/retail_app/app.py
# Kiểm thử ứng dụng
.venv/Scripts/python.exe -m pytest apps/retail_app
```

Dựng thêm target `duckdb` bằng lệnh dbt trên trước khi chạy toàn bộ pytest: test dùng cả hai backend.

## Phong cách và đặt tên

Python thụt 4 khoảng trắng; dùng `snake_case`. Giữ tiền tố dbt `stg_`, `int_`, `dim_`, `fact_`, `rpt_`. Viết tài liệu, comment bằng tiếng Việt; định danh mới bằng tiếng Anh. Chưa có cấu hình formatter/linter chung.

Notebook chạy từ root; giữ `DATA = 'data'`. Kết luận dữ liệu trong Markdown phải có cell chứng minh tương ứng.

## Kiểm thử

Dùng pytest và Streamlit AppTest: file `test_*.py`, hàm `test_*`. dbt có kiểm tra YAML và SQL `assert_*.sql`; lỗi chặn build. Chưa quy định tỷ lệ coverage. Bổ sung kiểm tra grain, khóa và đối soát khi sửa model. Chạy hết, lưu notebook trước commit; phối hợp với người phụ trách.

## Commit và Pull Request

Dùng nhánh `<loại>/<tên>`, ví dụ `docs/erd-fix`; PR về `main` để thành viên còn lại review. Commit ngắn, tiếng Việt không dấu: `Them so do Mermaid cho mo hinh 3NF`. Stage từng file. PR nêu thay đổi, kết quả kiểm thử, issue liên quan; kèm ảnh nếu sửa giao diện.

## Dữ liệu và cấu hình

Không commit `data/`, `.venv/`, database, output hoặc secrets. Dùng biến môi trường `PG_*`, `SNOWFLAKE_*`; không ghi mật khẩu production vào code.
