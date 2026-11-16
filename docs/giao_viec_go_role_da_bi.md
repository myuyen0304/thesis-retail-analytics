# Giao việc: gỡ role DA/BI (`phan_tich`) khỏi hệ thống

Claude soạn ngày 2026-11-07, GPT code, Claude rà. PM chốt 2026-11-07:
- gỡ hẳn role DA/BI khỏi code trước code freeze;
- báo cáo khóa luận chỉ mô tả 4 role sau khi đăng nhập: Quản lý, Data engineer, Admin, và Khách (người chưa đăng nhập).

## 0. Vì sao

Báo cáo chỉ được mô tả những gì có trong code trên `main` hoặc tag `thesis-v1`. Nếu báo cáo ghi 4 role mà app vẫn có DA/BI, người đọc code hay mở app sẽ thấy lệch.

## 1. Khi nào và ở đâu

- **Nơi làm:** worktree `D:\retail-analytics-nap`, nhánh `nap-ky/myuyen`. Không tạo nhánh mới.
- **Thời điểm:** chỉ bắt đầu sau khi D5a và D5a-1 đã commit. Lý do: `tests/test_d5_dashboard.py` của D5a có dùng `phan_tich`, sửa song song sẽ đè nhau.
- **Không commit, không push.** PM duyệt rồi Claude commit từng file.

## 2. Phạm vi sửa (đã dò trên `nap-ky/myuyen` ngày 2026-11-07)

| File | Việc |
|---|---|
| `apps/retail_app/ui/roles.py` | Bỏ `phan_tich` khỏi `ROLES`, `LABEL`, `_PAGE_CHOICES`, `DEFAULT_PAGE`. Dòng `_LEVEL_FULL['lien_he']` đổi thành `'ky_su'`. Sửa docstring nếu có nhắc DA/BI. |
| `apps/retail_app/ui/auth_store.py` | Bỏ `phan_tich` khỏi `ROLES`. `create` và `set_role` với `phan_tich` phải trả lỗi "Role không hợp lệ". |
| `apps/retail_app/ui/nhap_store.py:165` | Bỏ `phan_tich` khỏi tập role được gửi dữ liệu. |
| `apps/retail_app/views/gui_du_lieu.py:75,80` | Chỉ `ky_su` và `admin` xem được lỗi kỹ thuật. |
| `apps/retail_app/views/phan_quyen.py:42,69` | Hiện chỗ này đọc `LABEL[u['role']]` và `ROLES.index(u['role'])`. Một tài khoản còn role cũ trong DB sẽ làm vỡ trang Admin (KeyError, ValueError). Phải hiện role đó là "Role cũ: phan_tich (cần đổi)", và ô chọn role mới không chọn sẵn mục nào. |
| `apps/retail_app/app.py:7` | Sửa docstring `RETAIL_APP_ROLE=...`. |
| `scripts/ops/phan_quyen_nhom.py` | Bỏ group DA/BI: bỏ `PHAN_TICH`, bỏ tham số `--nhom-phan-tich`. Chỉ còn sinh lệnh cho group data engineer. |
| Test: `test_roles.py`, `test_auth_store.py`, `test_nhap_du_lieu.py`, `test_phan_quyen_nhom.py`, `test_d5_dashboard.py` | Sửa kỳ vọng theo 4 role. Không xóa các ca kiểm role thấp hơn bị chặn. |

**Không sửa:**
- `docs/phan_quyen.md`: thuộc phiên Claude phân quyền; Claude sẽ báo PM sửa riêng;
- `retail_dbt/`, `scripts/pipeline/`, `scripts/forecast/`, `scripts/ingest/`.

## 3. Tài khoản đang có role `phan_tich` trên Neon

- **Code:** tài khoản có role không còn trong `ROLES` thì bị coi là khách. `roles.py:153` đã làm vậy; phải giữ nguyên và có test.
- **Script:** thêm `scripts/ops/doi_role_phan_tich.py`.
  - Mặc định chỉ in số tài khoản còn role `phan_tich`, không in tên.
  - Có `--doi-sang <role>` thì đổi bằng một lệnh `update` và ghi `audit` với hành động `doi_role`, người làm là `script`.
  - Đọc kết nối từ `RETAIL_APP_DB_URL`, không in chuỗi kết nối.
- PM tự chạy script trước khi đưa bản mới lên Streamlit Cloud. Claude và GPT không chạy với Neon thật.

## 4. Databricks

- Không chạy lệnh nào trên cloud.
- Claude sẽ viết riêng cho PM lệnh kiểm `SHOW GRANTS` và lệnh `REVOKE` cho group DA/BI, nếu group đó từng được cấp quyền.

## 5. Test bắt buộc

1. `roles.ROLES == ('khach', 'quan_ly', 'ky_su', 'admin')`, và trong `apps/` cùng `scripts/` không còn chuỗi `phan_tich`, trừ script đổi role và test của nó.
2. Tài khoản trong DB có role `phan_tich` → `current_role()` là `khach`.
3. Trang Phân quyền vẫn vẽ được với tài khoản đó và hiện "cần đổi". Admin đổi được sang role hợp lệ.
4. `create` và `set_role` với `phan_tich` → trả lỗi, DB không đổi.
5. Cột mức "Liên hệ": `quan_ly` không thấy; `ky_su` và `admin` thấy đủ.
6. Trang Gửi: `quan_ly` không thấy lỗi kỹ thuật; `ky_su` và `admin` thấy.
7. Ma trận trang của `khach`, `quan_ly`, `ky_su`, `admin` giữ nguyên như trước khi sửa (so với `_PAGE_CHOICES` cũ).
8. `phan_quyen_nhom.statements` không còn câu nào cho group DA/BI.
9. `doi_role_phan_tich.py`:
   - không có `--doi-sang` thì không ghi gì;
   - có thì đổi đúng các dòng `phan_tich` và ghi `audit`;
   - `--doi-sang` nhận role không hợp lệ (gồm cả `phan_tich`) thì báo lỗi.

**Lệnh chạy:**
- Chạy bốn file test UI theo §9 của `giao_viec_d5_cong_bo_dot.md` (cần junction `data`), cùng `test_roles.py`, `test_auth_store.py`, `test_phan_quyen_nhom.py`.
- Không chạy chung `apps` và `scripts` trong một lệnh.
- Test cần Postgres thì dùng Postgres Docker như các test `auth_store` hiện có. Không dùng Neon.

## 6. PM đã chốt (2026-11-07)

1. Tài khoản đang là DA/BI chuyển sang **Quản lý**. PM chạy `doi_role_phan_tich.py --doi-sang quan_ly`.
2. Trang Sức khỏe dữ liệu chỉ cho Data engineer và Admin xem, **không mở cho Quản lý**. Ma trận của 4 role còn lại giữ nguyên.

## 7. Kết quả

(GPT ghi sau khi làm; Claude ghi phần rà.)

### GPT — triển khai ngày 2026-11-16

Nền `69d4064`, worktree `D:/retail-analytics-nap`, nhánh `nap-ky/myuyen`. Đã áp dụng cập nhật PM ngày 2026-11-16; điều kiện D5a/D5a-1 đã đạt. Chưa commit, chưa push, không tạo nhánh.

**Đã làm:**

- Chỉ còn `khach`, `quan_ly`, `ky_su`, `admin`; role cũ trong DB hoặc biến môi trường bị coi là Khách. Giữ nguyên ma trận trang của bốn role này; Sức khỏe dữ liệu chỉ có kỹ sư dữ liệu và Admin.
- Gỡ role cũ khỏi kho nhập local và Volume. Trang Gửi chỉ cho kỹ sư dữ liệu/Admin xem lỗi kỹ thuật và báo cáo mapping kỹ thuật.
- Trang Phân quyền hiện `Role cũ: phan_tich (cần đổi)` thay vì lỗi KeyError/ValueError. Ô Role mới không có lựa chọn mặc định với tài khoản cũ, kể cả vừa chuyển từ tài khoản khác; nút Đổi role bị khóa tới khi Admin chọn role hợp lệ. Admin đổi được role và có audit.
- `create`/`set_role` từ chối role cũ, không ghi DB hay audit. Giữ các ca kiểm role thấp hơn bị chặn; bỏ các tham số kiểm role đã gỡ, chuyển ca đổi role hợp lệ sang Quản lý.
- Script sinh GRANT chỉ còn group kỹ sư dữ liệu, không nhận `--nhom-phan-tich`. Chỉ sinh chuỗi lệnh, không thực thi cloud.
- Script đổi role mới mặc định chỉ SELECT đếm tài khoản cũ, không khởi tạo bảng, không in tên hay URL. `--doi-sang` chỉ nhận role gán được; đúng một UPDATE cho các dòng role cũ, mỗi dòng có audit `doi_role`, người làm `script`. UPDATE và audit cùng giao dịch: audit lỗi thì toàn bộ đổi role được hoàn tác. Gọi lại không ghi audit thừa. PM dùng `--doi-sang quan_ly` theo quyết định §6.

**Danh sách file đã sửa/tạo (18 file, tính cả báo cáo này):**

1. `apps/retail_app/ui/roles.py`: gỡ role, đổi ngưỡng xem đầy đủ Liên hệ sang kỹ sư dữ liệu.
2. `apps/retail_app/ui/auth_store.py`: gỡ role gán được.
3. `apps/retail_app/ui/nhap_store.py`: gỡ role khỏi quyền xem yêu cầu local.
4. `apps/retail_app/ui/nhap_dot.py`: gỡ role khỏi quyền xem yêu cầu Volume (chỗ bổ sung PM chỉ định).
5. `apps/retail_app/views/gui_du_lieu.py`: giới hạn xem lỗi/báo cáo kỹ thuật ở hai vị trí PM chỉ định.
6. `apps/retail_app/views/phan_quyen.py`: hiển thị role cũ và yêu cầu chọn role mới rõ ràng.
7. `apps/retail_app/app.py`: sửa danh sách role trong docstring.
8. `scripts/ops/phan_quyen_nhom.py`: chỉ sinh lệnh cho group kỹ sư dữ liệu.
9. `scripts/ops/doi_role_phan_tich.py` (mới): đếm/chuyển role và audit nguyên tử.
10. `apps/retail_app/tests/test_roles.py`.
11. `apps/retail_app/tests/test_auth_store.py`.
12. `apps/retail_app/tests/test_nhap_du_lieu.py`: thêm ba ca AppTest kiểm lỗi kỹ thuật theo role, giữ kiểm báo cáo mapping.
13. `apps/retail_app/tests/test_phan_quyen_nhom.py`.
14. `apps/retail_app/tests/test_d5_dashboard.py`.
15. `apps/retail_app/tests/test_l1_dot_web.py` (bổ sung theo PM).
16. `apps/retail_app/tests/test_t2_mot_file_web.py` (bổ sung theo PM).
17. `apps/retail_app/tests/test_doi_role_phan_tich.py` (mới): 18 ca về script, role cũ, trang Admin, ma trận quyền và quét chuỗi role cũ.
18. `docs/giao_viec_go_role_da_bi.md`: chỉ ghi kết quả vào §7, không ghi phần rà của Claude.

**Môi trường và lệnh test đã chạy:**

- Python `D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8`, `RETAIL_TEST_DATABRICKS=0`, `PYTHONDONTWRITEBYTECODE=1`.
- Các biến `PG_*` trong tiến trình test được ép về cấu hình mặc định Postgres local (`localhost:5433`, DB/user `retail`), schema tài khoản tạm riêng từng ca và xóa khi xong. Không dùng `RETAIL_APP_DB_URL` thật/Neon.
- `RETAIL_DUCKDB_PATH=D:/retail-analytics/warehouse/dbt.duckdb`: đọc file có sẵn; không chép database sang worktree.
- Tạo junction `D:/retail-analytics-nap/data` → `D:/retail-analytics/data` chỉ để đọc dữ liệu cho bốn file UI theo §5; đã gỡ junction sau test, giữ nguyên thư mục nguồn. Postgres đã chạy sẵn, không chạy lệnh Docker.
- Mỗi file một lệnh pytest, chạy tuần tự; không gộp apps với scripts.

Kiểm trước sửa:

```text
D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8 -m pytest apps/retail_app/tests/test_roles.py -q
43 passed in 85.46s (0:01:25)
```

Kết quả cuối sau sửa, nguyên dòng tóm tắt từng lệnh:

```text
D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8 -m pytest apps/retail_app/tests/test_doi_role_phan_tich.py -q
18 passed in 16.60s

D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8 -m pytest apps/retail_app/tests/test_roles.py -q
41 passed in 63.14s (0:01:03)

D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8 -m pytest apps/retail_app/tests/test_auth_store.py -q
16 passed in 12.42s

D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8 -m pytest apps/retail_app/tests/test_phan_quyen_nhom.py -q
8 passed in 0.04s

D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8 -m pytest apps/retail_app/tests/test_nhap_theo_doi.py -q
61 passed in 20.32s

D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8 -m pytest apps/retail_app/tests/test_nhap_tu_dong.py -q
151 passed in 107.44s (0:01:47)

D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8 -m pytest apps/retail_app/tests/test_nhap_du_lieu.py -q
99 passed in 65.11s (0:01:05)

D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8 -m pytest apps/retail_app/tests/test_extension_grants.py -q
17 passed in 0.23s

D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8 -m pytest apps/retail_app/tests/test_d5_dashboard.py -q
34 passed in 14.54s

D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8 -m pytest apps/retail_app/tests/test_l1_dot_web.py -q
139 passed in 58.75s

D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8 -m pytest apps/retail_app/tests/test_t2_mot_file_web.py -q
95 passed in 25.11s

D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8 -m pytest apps/retail_app/tests/test_l5_theo_doi_dot.py -q
67 passed in 8.57s

D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8 -m pytest apps/retail_app/tests/test_tao_admin.py -q
4 passed in 4.36s
```

Tổng kết lần kiểm cuối: **750 đạt, 0 trượt, 0 bỏ qua, 13 file**; không cộng lặp 43 ca baseline trước sửa.

**Kiểm thêm và giới hạn:**

- Quét `rg -n "phan_tich" apps scripts` chỉ còn script chuyển role và file test của chính script, đúng ngoại lệ §5.1. Có test tự động bảo vệ điều này cho mã Python.
- `git diff --check` đạt; Git chỉ cảnh báo CRLF sẽ đổi LF khi Git chạm file, không có lỗi khoảng trắng.
- Điểm diễn giải §5.5: giữ `_LEVEL_MASKED['lien_he'] = 'quan_ly'` như trước. Quản lý chỉ thấy dữ liệu Liên hệ đã che, không thấy đầy đủ; kỹ sư dữ liệu/Admin thấy đủ. Đây là cách giữ nguyên hành vi của bốn role còn lại và chỉ đổi `_LEVEL_FULL` đúng §2.
- Không sửa `docs/phan_quyen.md`, `docs/kich_ban_demo_bao_ve.md`, `docs/ban_do_flow.md`, hay các thư mục cấm. Không đọc file secrets. Không commit/push, không gọi Databricks/Neon thật, không chạy Docker.
- Script chuyển role chỉ được kiểm trên schema Postgres local tạm. PM vẫn cần tự chạy chuyển sang Quản lý trên Neon trước khi đưa app mới lên cloud; chưa nghiệm thu cloud.
- Không có lệch phạm vi hay câu hỏi mở khác. Các tài liệu untracked có sẵn (`ban_do_flow.md`, `kich_ban_demo_bao_ve.md`, `huong_dan_nghiem_thu_ai_demo_cloud.md`) được giữ nguyên.

**`git diff --stat` (chỉ các file tracked):**

```text
 apps/retail_app/app.py                        |  2 +-
 apps/retail_app/tests/test_auth_store.py      |  2 +-
 apps/retail_app/tests/test_d5_dashboard.py    |  6 +++---
 apps/retail_app/tests/test_l1_dot_web.py      |  4 ++--
 apps/retail_app/tests/test_nhap_du_lieu.py    | 18 ++++++++++++++++--
 apps/retail_app/tests/test_phan_quyen_nhom.py | 15 +++++++--------
 apps/retail_app/tests/test_roles.py           | 16 ++++++++--------
 apps/retail_app/tests/test_t2_mot_file_web.py |  2 +-
 apps/retail_app/ui/auth_store.py              |  2 +-
 apps/retail_app/ui/nhap_dot.py                |  2 +-
 apps/retail_app/ui/nhap_store.py              |  2 +-
 apps/retail_app/ui/roles.py                   |  9 ++++-----
 apps/retail_app/views/gui_du_lieu.py          |  4 ++--
 apps/retail_app/views/phan_quyen.py           |  8 ++++----
 scripts/ops/phan_quyen_nhom.py                | 16 +++++-----------
 15 files changed, 57 insertions(+), 51 deletions(-)
```

Hai file code/test mới và phiếu này đang untracked nên không có trong stat; đã liệt kê đầy đủ ở trên. Không stage file.

### Claude — rà độc lập ngày 2026-11-16

**Kết luận: ĐẠT**, chưa commit, chờ PM duyệt.

- Đọc toàn bộ diff 15 file tracked và 2 file mới. Ma trận trang của 4 role giữ nguyên: test so với bảng viết cứng của bản cũ, không lấy từ code mới. `_LEVEL_FULL['lien_he']` đổi thành `'ky_su'` đúng §2. `_LEVEL_MASKED` giữ `quan_ly`, nên Quản lý vẫn chỉ thấy bản che như trước.
- Tài khoản còn role cũ: `logged_in_user()` bỏ phiên (`roles.py:150`), nên nhãn ở thanh bên (`roles.py:232`) không bị KeyError. Trang Phân quyền dùng `LABEL.get`; ô role mới để trống, nút khóa tới khi chọn.
- `doi_role_phan_tich.py`: không gọi `init()`, không tạo bảng. Lệnh UPDATE và audit chạy trong cùng một kết nối, không bật autocommit, nên là một giao dịch. Audit ghi đúng định dạng `set_role` (`doi_role`, `{'tai_khoan','role'}`), người làm là `script`. Không in tên tài khoản hay URL.
- Quét lại `phan_tich` và `DA/BI` trong `apps`, `scripts`, `deploy`: chỉ còn script đổi role và test của nó.
- Tự chạy lại, mỗi file một lệnh: `test_doi_role_phan_tich` 18/18, `test_phan_quyen_nhom` 8/8, `test_auth_store` 16/16, `test_roles` 41/41. Lần đầu chạy `test_roles` trượt 3 ca vì thiếu `RETAIL_DUCKDB_PATH` (lỗi môi trường); đặt biến này thì đạt hết. Không chạy lại 9 file UI còn lại.
- Ghi nhận nhỏ, không chặn: tài khoản role cũ đăng nhập sẽ bị đưa về form đăng nhập mà không có thông báo. Không ảnh hưởng gì sau khi PM chạy script đổi role.
