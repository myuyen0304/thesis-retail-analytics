# Giao việc B2: chữ "Đường xử lý" trên danh sách yêu cầu một file (kho cloud)

Soạn ngày 2026-11-13, Claude. GPT code. Claude rà độc lập trước khi commit; chưa đạt thì Claude ghi vào §7 để GPT sửa.

**Vì sao làm bây giờ.** Nghiệm thu T2 trên cloud (`docs/giao_viec_t2_mot_file_cloud.md` §12, phát hiện 1) cho thấy: yêu cầu một file vừa gửi
(trạng thái `da_gui`, Airflow chưa đọc file) đã hiện "Đường xử lý: Chờ đội dữ liệu". Người xem hiểu là file bị đẩy sang đường tay, trong khi máy còn
chưa đọc. Luồng local đã xử lý đúng: chưa có `duong` thì hiện "Đang đọc và hiểu file…" (`apps/retail_app/views/gui_du_lieu.py:126–129`,
`apps/retail_app/views/duyet_du_lieu.py:247–250`). Khối kho cloud thì thiếu nhánh này. `apps/retail_app` nằm trong phần băm `code_version`, nên
**phải xong và được Claude rà đạt trước cửa sổ bảo trì #2 (~2026-11-24)**. Trễ hơn thì lỗi này sẽ hiện trong buổi bảo vệ 12/12.

Đọc trước: `AGENTS.md`, `CLAUDE.md`, `docs/giao_viec_t2_mot_file_cloud.md` §12.

## 1. Môi trường và ràng buộc

- Worktree `D:\retail-analytics-nap`, nhánh `nap-ky/myuyen`, HEAD `abee6c2` trở lên.
- Python: `D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8`. Biến `RETAIL_TEST_DATABRICKS=0`.
- Không commit, không push. Không kết nối Databricks, không chạy Docker. Không đọc `.env.*.local`, `.streamlit/secrets.toml`, `~/.retail-secrets/*`.
- Máy thiếu RAM: chạy từng file test bằng một lệnh riêng.
- Chỉ sửa các file ở §4. **Không sửa** `scripts/`, `retail_dbt/`, `deploy/`, `apps/retail_app/ui/trang_thai_dot.py`, khối local (`nhap_runner`).

## 2. Hiện trạng

Trên kho cloud, yêu cầu một file đi qua các trạng thái sau (`apps/retail_app/ui/trang_thai_dot.py`, `TRANSITIONS_MOT`). Trường `duong` (`tu_dong`/`tay`)
chỉ có sau khi Airflow đọc xong file:

| Trạng thái | Có `duong`? | Chữ hiện nay | Chữ đúng |
|---|---|---|---|
| `da_gui`, `dang_doc` | không | "Đường xử lý: Chờ đội dữ liệu" | "Đang đọc và hiểu file…" |
| `loi_file`, `loi_de_xuat` | không | "Đường xử lý: Chờ đội dữ liệu" | không hiện dòng đường xử lý (nhãn trạng thái đã nói lỗi) |
| mọi trạng thái khác | có | "Tự động" / "Chờ đội dữ liệu" | giữ nguyên |

Hai chỗ đang sai:
- `apps/retail_app/views/gui_du_lieu.py:70` (trang Gửi, danh sách "Yêu cầu đã gửi");
- `apps/retail_app/views/duyet_du_lieu.py:64` (trang Duyệt, khối "Yêu cầu một file").

## 3. Việc cần làm

1. Thêm vào `apps/retail_app/ui/nhap_dot.py` một hàm thuần, không gọi Streamlit và không đọc kho:
   `chu_duong_xu_ly(row) -> str | None`.
   - `row['duong'] == 'tu_dong'` → `'Đường xử lý: Tự động'`.
   - `row['duong'] == 'tay'` → `'Đường xử lý: Chờ đội dữ liệu'`.
   - Không có `duong` và trạng thái là `da_gui` hoặc `dang_doc` → `'Đang đọc và hiểu file…'` (đúng chuỗi của khối local, dấu `…` là một ký tự).
   - Không có `duong`, trạng thái khác → `None`.
2. Ở hai chỗ §2, gọi hàm này và chỉ `st.caption` khi kết quả khác `None`. Không đổi gì khác trên hai trang: không đổi thứ tự dòng, không đổi khối local,
   không thêm lần đọc kho, và giữ nguyên số lần gọi `DotStore.visible` (test `test_actual_pages_mot_timer_single_read` phải vẫn đạt).

## 4. File được sửa

- `apps/retail_app/ui/nhap_dot.py`: thêm `chu_duong_xu_ly`.
- `apps/retail_app/views/gui_du_lieu.py`: dòng 70.
- `apps/retail_app/views/duyet_du_lieu.py`: dòng 64.
- `apps/retail_app/tests/test_t2_mot_file_web.py`: thêm test §5.

## 5. Test phải có

1. **Hàm thuần**, tham số hóa đủ 6 ca: `da_gui` và `dang_doc` không `duong`; `loi_file` và `loi_de_xuat` không `duong`; `tu_dong`; `tay`. So **đúng chuỗi**, không dùng `in`.
2. **Trang thật** (`AppTest`, cùng fixture `cloud_store` như các test `test_actual_*`), tham số hóa theo trang `gui_du_lieu`/`duyet_du_lieu`:
   - Yêu cầu một file vừa gửi (`da_gui`, chưa có `duong`): có caption "Đang đọc và hiểu file…", **không** caption nào chứa "Chờ đội dữ liệu".
   - Ghi tiếp sự kiện sang `dang_doc`, rồi `cho_duyet` với `duong='tay'`, chạy lại trang: lúc `dang_doc` vẫn là "Đang đọc…"; lúc `cho_duyet` có "Đường xử lý: Chờ đội dữ liệu".
   - Một yêu cầu `loi_de_xuat`: không có caption nào bắt đầu bằng "Đường xử lý".
   - Không có `exception`, không có `error`.
3. Các test cũ của hai trang giữ nguyên, không sửa câu assert cũ cho khớp.

## 6. Kiểm và báo cáo

Chạy từng lệnh, ghi số đạt / trượt / bỏ qua **trước và sau** khi sửa:
- `apps/retail_app/tests/test_t2_mot_file_web.py`
- `apps/retail_app/tests/test_nhap_theo_doi.py`
- `apps/retail_app/tests/test_l1_dot_web.py`
- `apps/retail_app/tests/test_l5_theo_doi_dot.py`

Báo gồm: danh sách file, `git status --short`, `git diff --stat`, số test trước và sau, và chỗ làm khác phiếu nếu có. Chỗ nào phiếu chưa rõ thì hỏi,
không tự đoán.

**Claude sẽ thử đột biến:**
- bỏ nhánh `dang_doc` (chỉ còn `da_gui`);
- trả về chuỗi "Chờ đội dữ liệu" khi không có `duong` (lỗi cũ);
- `loi_de_xuat` vẫn hiện dòng đường xử lý;
- đổi `…` thành `...`;
- một trong hai trang vẫn dùng biểu thức cũ.

**Kiểm trên màn hình:** sau khi Claude rà đạt, PM xem trên app local ở chế độ `RETAIL_NHAP_DOT=dia`. Claude ghi sẵn một yêu cầu `da_gui` vào kho đĩa
rồi chuyển sang `cho_duyet`, `duong='tay'`. Lượt thật trên cloud diễn ra sau cửa sổ #2.

## 7. Rà của Claude (Claude ghi, GPT đọc để sửa)

(trống)
