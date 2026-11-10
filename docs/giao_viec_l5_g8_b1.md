# Giao việc L5: luật G8 cho script dọn bản, kèm sửa lỗi B1 trang không tự cập nhật

Soạn ngày 2026-11-10, Claude. GPT code. Claude rà độc lập trước khi commit; chưa đạt thì Claude ghi vào §6 để GPT sửa.

**Vì sao làm bây giờ.** Tổng duyệt ngày 2026-11-10 đạt trọn luồng trên cloud, gồm cả hai lệnh đưa lên dashboard và trả dashboard. Lượt đó lộ ra hai việc:

- **G8** (thiết kế `thiet_ke_dot_web_public.md` §10). `scripts/ops/don_ban_cu.py` không biết con trỏ `dashboard`. Khi tổng duyệt, PM phải nhớ trả dashboard trước rồi mới xóa bản thử. Nếu xóa bản đang trên dashboard, `releases.choose` (`apps/retail_app/dwh/releases.py:36–43`) sẽ báo "Chưa có phiên bản dữ liệu được công bố", và mọi trang PS đọc con trỏ `dashboard` đều hỏng. Hạn: trước lần xóa `5d32a104`, khoảng 11-22. File này nằm ngoài phần băm nên không cần dựng image.
- **B1** (PM báo ngày 2026-11-10). Admin bấm "Đưa bản có đợt lên dashboard (demo)" hoặc "Trả dashboard về bản số thật" thì trang hiện "Đang chờ Airflow xử lý lệnh (thường dưới 5 phút)". Airflow chạy xong mà thông báo vẫn đứng yên, phải tải lại trang mới thấy kết quả. Nguyên nhân: phần đợt trên trang Duyệt (`apps/retail_app/views/duyet_du_lieu.py:27–99`) và trang Gửi (`apps/retail_app/views/gui_du_lieu.py:25–57`) chỉ đọc Volume một lần lúc vẽ trang. Không có vòng dò như luồng local (`apps/retail_app/ui/nhap_runner.py:706–735`). `apps/retail_app` nằm trong phần băm, nên **B1 phải xong và được Claude rà đạt trước cửa sổ ~11-21**; trễ hơn thì không có trong buổi 12/12.

Đọc trước: `AGENTS.md`, `CLAUDE.md`, `docs/thiet_ke_dot_web_public.md` §3, §10, `docs/giao_viec_don_ban_cu.md`.

## 1. Môi trường và ràng buộc

- Worktree `D:\retail-analytics-nap`, nhánh `nap-ky/myuyen`, HEAD `0453065` trở lên.
- Python: `D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8`. Biến `RETAIL_TEST_DATABRICKS=0`.
- Không commit, không push. Không kết nối Databricks, không chạy Docker. Không đọc `.env.*.local`, `.streamlit/secrets.toml`, `~/.retail-secrets/*`.
- Máy thiếu RAM: chạy từng file test một lệnh. Chạy `apps` và `scripts` ở hai lệnh pytest riêng.
- Chỉ sửa các file ở §4. **Không sửa** `scripts/pipeline/`, `retail_dbt/`, `deploy/`, `scripts/ops/nhap_do.py`, `apps/retail_app/ui/trang_thai_dot.py`.

## 2. Phần G8: `scripts/ops/don_ban_cu.py`

Con trỏ nằm ở `payload['dashboard']`, là mã bản hoặc không có khóa. Có thể có thêm `payload['dashboard_since']` (`scripts/pipeline/state.py:123–149`). Thiếu khóa hoặc giá trị `None` nghĩa là dashboard theo bản số thật, G8 không chặn gì.

**2.1 Luật trong `plan_deletion`** (`:99–147`). Khi `dashboard` có giá trị:

| Điều kiện | Lý do ghi vào `reasons` |
|---|---|
| `dashboard` nằm trong `targets` | `G8: yêu cầu xóa bản đang trên dashboard` |
| `dashboard` không phải chuỗi 24 hex, hoặc không có trong `releases` | `G8: con trỏ dashboard không trỏ tới bản hợp lệ; trả dashboard trước khi xóa` |
| `dashboard` có trong `releases` nhưng thiếu schema (`schema_set(dashboard)` không nằm trọn trong `schemas`) | `G8: bản trên dashboard không còn đủ sáu schema` |

Hai dòng sau chặn mọi lệnh xóa, giống cách G1 và G3 đang làm: con trỏ hỏng thì phải xử lý con trỏ trước. Lần kiểm lại sau khi lấy khóa (`execute_locked`, `:278–281`) đã gọi `plan_deletion`, nên tự có G8; không thêm đường kiểm riêng.

**2.2 `checked_payload`** (`:150–156`). Thêm điều kiện: nếu `dashboard` có giá trị thì phải nằm trong `releases`. Sai thì `Blocked`, với cùng câu báo như hiện nay hoặc một câu riêng có chữ `dashboard`. Đây là lớp chặn cuối trước khi ghi registry.

**2.3 Báo cáo** (`print_report`, `:194–244`).
- Cột vai trò: bản trùng `dashboard` và khác `active` ghi `dashboard`. Thứ tự ưu tiên: `active` > `dashboard` > `dich_rollback` > các vai trò còn lại. Cột lý do vẫn ghi đủ mọi luật chặn, kể cả khi một bản vừa là `dashboard` vừa là đích rollback.
- Sau dòng "Tổng bảng trong catalog", in thêm một dòng: `Con trỏ dashboard: <mã bản>` hoặc `Con trỏ dashboard: theo bản số thật`.

**2.4 Không đổi:** `removed_payload` giữ nguyên các khóa `dashboard`, `dashboard_since` (nó đã sao chép mọi khóa khác). Không thêm cờ nào để vượt G8. Muốn xóa bản đang trên dashboard thì Admin bấm trả dashboard trước.

## 3. Phần B1: trang Gửi và trang Duyệt tự cập nhật trạng thái đợt

**3.1 Hàm thuần ở `apps/retail_app/ui/nhap_dot.py`** (file này không import `streamlit`).
- `DotStore.anh_chup(username, role)` trả một giá trị so sánh được bằng `==`, gồm:
  - với mỗi yêu cầu trong `visible(...)`: `id`, `trang_thai`, `release_id`, `ma_loi`, `thong_bao`;
  - lệnh mới nhất: `so`, `loai`, và `ket_qua` (hoặc `None`).
- Hàm `can_theo_doi(anh)` trả `True` khi có ít nhất một điều sau:
  - lệnh mới nhất có `ket_qua is None`;
  - có yêu cầu ở `da_gui`, `dang_kiem`, `het_cho`, `cho_chay` hoặc `dang_chay`.

  Các trạng thái khác thì không dò, để không gọi Files API liên tục.

**3.2 Fragment dò** (một hàm dùng chung, đặt ở `apps/retail_app/ui/nhap_dot.py` hoặc một file mới `apps/retail_app/ui/theo_doi_dot.py`; import `streamlit` lười trong hàm như `nhap_runner.monitor_page`).
- Gọi `@st.fragment(run_every='30s' if can_theo_doi(anh_dau) else None)`. 30 giây là chủ ý: mỗi lần dò tốn vài lệnh Files API, mà Airflow cũng chỉ dò 5 phút một lần.
- Mỗi lần chạy:
  1. Nếu người đăng nhập hoặc vai trò đã đổi thì `st.rerun(scope='app')`. Chép đúng cách `monitor_page` làm (`nhap_runner.py:716–718`).
  2. Đọc lại `anh_chup`. Khác ảnh lúc vẽ trang thì `st.rerun(scope='app')`, để cả trang vẽ lại bằng code hiện có. **Không vẽ lại từng phần trong fragment.**
  3. Lỗi khi đọc Volume (`OSError`, `ValueError`, lỗi SDK) thì bỏ qua lần dò đó, không hiện lỗi mới và không làm trang sập. Lần sau dò tiếp. Không in nội dung lỗi ra màn hình.
- Không dùng `time.sleep` và không dùng `st.rerun` theo vòng lặp.

**3.3 Gắn vào trang.**
- `views/duyet_du_lieu.py`: gọi fragment một lần, sau khi đã vẽ xong khung "Đợt dữ liệu" và khung "Bản dữ liệu trên dashboard". Ảnh đầu dùng chính dữ liệu đã đọc để vẽ trang, không đọc thêm lần nữa. Chỉ gọi khi `dots is not None` và đã đăng nhập.
- `views/gui_du_lieu.py`: tương tự, cho danh sách đợt của người gửi, đặt sau vòng `for row in dots.visible(...)`.
- Không đổi chữ, nút, quyền hay thứ tự khung trên trang. Không đổi luồng local (`monitor_page`).

**3.4 Ràng buộc với Streamlit Cloud.** Không thêm thư viện. `streamlit==1.64.0` đã có `st.fragment(run_every=...)` (luồng local đang dùng). View và module mới không được import `duckdb`, `yaml`, `scripts.ingest.auto_mapping`. Claude sẽ chạy lại script giả lập `sys.path` của Cloud để kiểm.

## 4. File được sửa

| File | Việc |
|---|---|
| `scripts/ops/don_ban_cu.py` | §2 |
| `scripts/ops/tests/test_don_ban_cu.py` | Ca G8 ở §5.1 |
| `apps/retail_app/ui/nhap_dot.py` | §3.1, có thể cả §3.2 |
| `apps/retail_app/ui/theo_doi_dot.py` (mới, nếu tách) | §3.2 |
| `apps/retail_app/views/duyet_du_lieu.py` | §3.3, chỉ thêm lời gọi |
| `apps/retail_app/views/gui_du_lieu.py` | §3.3, chỉ thêm lời gọi |
| `apps/retail_app/tests/test_l5_theo_doi_dot.py` (mới) | Ca B1 ở §5.2 |
| `apps/retail_app/tests/test_l1_dot_web.py` | Chỉ thêm module mới vào ca kiểm import khi chỉ có thư mục app trên `sys.path`, nếu ca đó liệt kê module |

## 5. Test phải có

**5.1 G8** (hàm thuần `plan_deletion`, `checked_payload`, `print_report`; cloud giả như các ca hiện có):
- xóa bản đang trên dashboard thì bị chặn với `G8: yêu cầu xóa bản đang trên dashboard`, và không có câu `DROP` nào chạy;
- con trỏ trỏ tới bản không có trong `releases`, con trỏ không phải 24 hex, hoặc bản dashboard thiếu một schema: mọi lệnh xóa đều bị chặn với lý do G8 tương ứng;
- không có khóa `dashboard` hoặc `dashboard: None` thì kết quả y như trước L5. Các ca cũ phải đạt nguyên;
- dashboard trỏ bản A, xóa bản B hợp lệ thì được, và registry sau khi ghi vẫn giữ `dashboard = A` và `dashboard_since`;
- con trỏ đổi sang đúng bản đang xóa trong lúc chờ khóa thì lần kiểm lại sau khóa chặn (registry giả trả payload khác ở lần đọc thứ hai);
- báo cáo có vai trò `dashboard`, có dòng `Con trỏ dashboard: …` cho cả hai trường hợp.

**5.2 B1** (Volume giả `KhoDia` như `test_l1_dot_web.py`; Streamlit thì dùng `streamlit.testing.v1.AppTest` hoặc mock như các ca đang có):
- `can_theo_doi`: `True` với lệnh chưa có kết quả và với từng trạng thái chờ trong §3.1. `False` khi chỉ còn `da_kiem`, `tren_dashboard`, `da_tra`, `loi`, `sai_hop_dong`, `loi_file`, `huy`, và lệnh đã có kết quả;
- `anh_chup` đổi khi ghi thêm `lenh/<n>.ket_qua.json`, và khi ghi thêm một sự kiện trạng thái;
- ghi kết quả lệnh vào Volume giả sau khi trang đã vẽ, rồi chạy fragment một lần: trang vẽ lại và không còn câu "Đang chờ Airflow xử lý lệnh". Làm cho cả `dat` và `tra`;
- không có gì đang chờ thì fragment không đặt `run_every` (hoặc đặt `None`);
- Volume ném lỗi khi dò thì trang không sập và không hiện thêm `st.error`;
- vai trò đổi giữa hai lần dò thì trang chạy lại cả app.

## 6. Kiểm và báo cáo

Chạy từng lệnh. Ghi số đạt, trượt và bỏ qua, trước và sau khi sửa:
- `scripts/ops/tests/test_don_ban_cu.py`, `scripts/ops/tests/test_nhap_do.py`;
- `apps/retail_app/tests/test_l1_dot_web.py`, `apps/retail_app/tests/test_l5_theo_doi_dot.py`, `apps/retail_app/tests/test_nhap_du_lieu.py`, `apps/retail_app/tests/test_d5_dashboard.py`.

Báo gồm: danh sách file, `git status --short`, `git diff --stat`, số test trước và sau, chỗ làm khác phiếu nếu có. Chỗ nào phiếu chưa rõ thì hỏi, không tự đoán.

**Claude sẽ thử đột biến:**
- G8:
  - bỏ dòng chặn khi xóa đúng bản dashboard;
  - bỏ chặn khi con trỏ hỏng;
  - bỏ kiểm thiếu schema của bản dashboard;
  - bỏ điều kiện mới trong `checked_payload`;
  - `removed_payload` làm rơi khóa `dashboard`;
  - báo cáo xếp `dich_rollback` trước `dashboard`.
- B1:
  - `can_theo_doi` luôn `False`;
  - bỏ một trạng thái chờ khỏi danh sách;
  - ảnh chụp bỏ `ket_qua` của lệnh;
  - fragment không rerun cả app khi ảnh khác;
  - nuốt lỗi bằng cách in `st.error`;
  - bỏ kiểm đổi vai trò.

**Kiểm trên màn hình sau khi Claude rà đạt.** Bộ Airflow thử và bản thử đã xóa ngày 2026-11-10. Muốn thử lại lệnh dashboard trên cloud thì phải tổng duyệt lại, tốn khoảng 83 chỗ quota. Vì vậy chia làm hai phần:
- **Trước cửa sổ:** PM xem phần danh sách đợt tự cập nhật trên app local ở chế độ `RETAIL_NHAP_DOT=dia`. Claude ghi trạng thái mới vào kho đĩa để trang tự đổi. Khung "Bản dữ liệu trên dashboard" chỉ hiện khi nguồn là Databricks, nên phần lệnh dashboard chỉ dựa vào test §5.2.
- **Lượt thật sau cửa sổ:** PM xem trang tự đổi sau khi bấm "Đưa lên dashboard", không phải tải lại.

Phần G8 được kiểm ở lần chạy `bao_cao_don` kế tiếp: báo cáo phải có dòng `Con trỏ dashboard`.

## 7. Rà của Claude (Claude ghi, GPT đọc để sửa)

Chưa có.
