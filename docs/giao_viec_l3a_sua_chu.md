# Giao việc L3a: sửa chữ hiển thị trước cửa sổ bảo trì

Soạn ngày 2026-11-09, Claude. GPT code. Claude rà độc lập trước khi commit; chưa đạt thì ghi vào §5 để GPT sửa.

**Phạm vi:** PM chốt ngày 2026-11-09 chỉ demo đợt 2023. Phần đợt 2024 hoãn tới sau 12/12, phiếu cũ [giao_viec_l3_dot_2024.md](giao_viec_l3_dot_2024.md) giữ nguyên để dùng sau và **không làm**. Phiếu này chỉ gồm ba chỗ chữ phải sửa trước khi `apps/retail_app` và `scripts/pipeline` đóng băng.

Không đổi số liệu, không đổi logic. Đọc trước: `AGENTS.md`, `CLAUDE.md`, `docs/giao_viec_d5_cong_bo_dot.md` §11 ghi nhận (h), (i).

## 1. Môi trường và ràng buộc

- Worktree `D:\retail-analytics-nap`, nhánh `nap-ky/myuyen`. L2 đã commit tới `3243756`.
- Python: `D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8`. Biến `RETAIL_TEST_DATABRICKS=0`.
- Không commit, không push. Không kết nối Databricks, không chạy Docker. Không đọc `.env.*.local`, `.streamlit/secrets.toml`.
- Máy thiếu RAM: chạy từng file test một lệnh.
- Chỉ sửa 5 file ở §3. Đặc biệt **không sửa `retail_dbt/`**.

## 2. Việc

**2.1 Nhãn kỳ** (`period_label`, `apps/retail_app/ui/common.py:266–272`). Bản có cờ tổng hợp: `2012-2022` và `2013-2022`, khi không phải kỳ phân tích, đều ghi `(kỳ gốc, số thật)`. Chỉ áp cho đúng hai mã này. Bản không cờ giữ nguyên: `2012–2022` vẫn là `(toàn bộ dữ liệu)`.

**2.2 Ngày trong chú thích** (`page_header`, `common.py:193`, `:196`). Dùng `_d(end)` để ra dạng `31/12/2022`, không còn `00:00:00`.

**2.3 Câu lỗi `--dot`** (`scripts/pipeline/cli.py:342`, `:599`). L2 đã cho chạy trên Databricks nên chữ "local" sai. Đổi cả hai chỗ thành `--dot chỉ dùng với prepare, không cùng --snapshot-id`. Điều kiện kiểm giữ nguyên.

## 3. File được sửa

| File | Việc |
|---|---|
| `apps/retail_app/ui/common.py` | 2.1, 2.2 |
| `scripts/pipeline/cli.py` | 2.3, đúng hai dòng |
| `apps/retail_app/tests/test_d5_dashboard.py` | Chỉ ca T8 ở `:160`: bản cờ tổng hợp nay là `2012–2022 (kỳ gốc, số thật)`. Ca bản không cờ ở `:154`, `:163` giữ nguyên |
| `apps/retail_app/tests/test_l1_dot_web.py` | `test_forecast_note_only_when_different`: dữ liệu giả dùng `pd.Timestamp('2022-12-31')`, kiểm có `số tới 31/12/2022`, không có `00:00:00`. Thêm ca tương tự cho `Hỏi dữ liệu (AI)` |
| `scripts/pipeline/tests/test_snapshot_dot.py` | Chỉ `:116`, đổi chuỗi `match` theo câu mới |

## 4. Kiểm và báo cáo

Chạy từng lệnh, ghi đạt/trượt/skip trước và sau khi sửa: `test_d5_dashboard.py`, `test_l1_dot_web.py`, `test_snapshot_dot.py`, `test_l2_dot_cloud.py`.

Báo: danh sách file, `git status --short`, `git diff --stat`, số test trước và sau, chỗ làm khác phiếu nếu có. Chỗ nào phiếu chưa rõ thì hỏi, không tự đoán.

Claude sẽ thử đột biến: áp nhãn mới cho bản không cờ; áp cho mã khác hai mã trên; bỏ `_d` ở từng nhánh.

## 5. Rà của Claude (Claude ghi, GPT đọc để sửa)
