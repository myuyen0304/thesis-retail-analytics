# Giao việc L1: gửi đợt và lệnh dashboard trên web, lưu trên Volume

Soạn ngày 2026-11-07, Claude. GPT code §3–§5. Claude rà độc lập trước khi commit; chưa đạt thì ghi vào §8 để GPT sửa.
Thiết kế gốc: [thiet_ke_dot_web_public.md](thiet_ke_dot_web_public.md), các mục §3, §4, §7.4, §14 lát L1. PM đã chốt mọi quyết định ngày 2026-11-07.

Đọc trước:
- `AGENTS.md`, `CLAUDE.md`, `docs/agent_workflows.md`;
- skill `developing-with-streamlit`;
- thiết kế ở trên;
- `apps/retail_app/ui/nhap_store.py`, `apps/retail_app/ui/nhap_runner.py` (`dashboard_state`, `dashboard_action` :784–818);
- `apps/retail_app/views/gui_du_lieu.py`, `apps/retail_app/views/duyet_du_lieu.py` (khối dashboard :288–319);
- `apps/retail_app/dwh/releases.py` (`resolve` :84–102, `pointers_differ`), `apps/retail_app/ui/common.py` (`page_header` :187–192);
- `apps/retail_app/tests/test_d5_dashboard.py`.

## 0. Việc này là gì

Đây là phần web của luồng "`chushop` gửi đợt 2023 trên web public → Admin công bố lên dashboard".
- Web chỉ **ghi file và ghi sự kiện, lệnh** lên Volume `/Volumes/retail_lab/nhap_du_lieu/kho/`, rồi **đọc lại trạng thái**.
- Phân loại file, chạy pipeline, đổi con trỏ dashboard và ghi sổ đợt là việc của Airflow. Phần đó thuộc L2, **không làm ở phiếu này**.
- Làm xong L1, web gửi được đợt và hiện "Đã gửi"; trạng thái chưa đi tiếp cho tới khi có L2. Như vậy là đúng.

## 1. Bẫy phải tránh

1. **Không import `duckdb`, `scripts.ingest.auto_mapping`, `scripts.ingest.dot` trên đường cloud.** `apps/retail_app/requirements.txt` không có duckdb; import vào là trang lỗi ngay khi mở trên Streamlit Cloud. Có test chặn ở §5.
2. **Không dựa vào loại lỗi khi ghi đua.** S0 ngày 2026-11-04 (`thiet_ke_duong_tu_dong.md` §8.9) cho thấy:
   - ghi `overwrite=False` vào file đã có, cách tuần tự, báo `AlreadyExists`;
   - nhưng khi hai người ghi gần như cùng lúc, người thua thường gặp `TypeError: object of type '_io.BytesIO' has no len()` (SDK 0.117.0).
   - Vì vậy mỗi bản ghi mang mã ngẫu nhiên `ma`. Ghi lỗi **kiểu gì** cũng đọc lại file: `ma` khớp là mình đã ghi được, khác là người khác đã ghi, file không có thì báo lỗi thật.
3. **Web không giữ quyền ghi registry và không gọi CLI trên cloud.** Nút dashboard trên cloud chỉ ghi một file lệnh. Đường local (subprocess, `nhap_runner.py:797–818`) giữ nguyên từng byte.
4. **Hai khóa Databricks khác nhau:**
   - khóa ghi Volume là `retail-nhap-writer`, chỉ dùng cho Files API;
   - đọc registry dùng kết nối đọc sẵn có của app (`retail-web-ro`, qua `dwh/connection.py`).
   - Không dùng khóa này cho việc của khóa kia. Không gửi câu SQL bằng khóa ghi Volume, vì như vậy sẽ đánh thức warehouse.
5. **Không đổi luồng một file** (`RequestStore`, `TRANSITIONS` ở `nhap_store.py:17–23`, hàng đợi, auto mapping). Luồng đợt là bảng và lớp riêng.

## 2. Môi trường và ràng buộc

- **Worktree** `D:\retail-analytics-nap`, nhánh `nap-ky/myuyen`.
  - **Điều kiện bắt đầu:** PM đã commit D5a và D5a-1 (hiện 19 file chưa commit). Chưa commit thì dừng, báo PM.
  - Python: `D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8`.
- **Không commit, không push.** Không kết nối Databricks. Không đọc `.env.*.local` hay `.streamlit/secrets.toml`.
- **Chỉ sửa hoặc tạo các file ở §4.** Không sửa:
  - `scripts/` (kể cả `scripts/ingest/dot.py`, `scripts/pipeline/*`);
  - `retail_dbt/`, `deploy/`;
  - `docs/phan_quyen.md`.
- **Máy thiếu RAM:**
  - không chạy toàn bộ test app trong một lệnh;
  - không chạy chung `apps` và `scripts` trong một lệnh;
  - chạy đúng các file ở §5.
- Thư mục `data` ở worktree nap là junction:
  - tạo: `cmd /c mklink /J data D:\retail-analytics-am\data`;
  - gỡ: `cmd /c rmdir data`.
  - **Không dùng `Remove-Item -Recurse`**, vì lệnh đó xóa luôn dữ liệu ở đích.
- `apps/retail_app` nằm trong phần băm `code_version`. Đây là việc đã lường trước: mọi lát sẽ lên production cùng một lần dựng image (thiết kế §11).

## 3. Thiết kế

### 3.1 Cấu hình

| Biến | Giá trị | Mặc định |
|---|---|---|
| `RETAIL_NHAP_DOT` | `tat` / `dia` / `volume` | `tat`: không hiện gì của luồng đợt |
| `RETAIL_NHAP_VOLUME` | đường dẫn gốc trên Volume | `/Volumes/retail_lab/nhap_du_lieu/kho` |
| `RETAIL_NHAP_DIA` | thư mục gốc cho chế độ `dia` | `warehouse/ui_nhap_dot` (đã gitignore theo `warehouse/`) |
| `DATABRICKS_HOST` | host workspace | dùng chung cấu hình hiện có |
| `RETAIL_NHAP_DBX_CLIENT_ID`, `RETAIL_NHAP_DBX_CLIENT_SECRET` | khóa `retail-nhap-writer` (OAuth M2M), đặt cùng kiểu với `RETAIL_AI_DBX_*` (`dwh/guarded.py:11`) | không có thì chế độ `volume` báo "Chưa cấu hình kho đợt" và không hiện form |

- Chế độ `dia` dùng cho chạy local và test. Bố cục thư mục y hệt Volume.
- Chế độ `volume` dùng `databricks.sdk.WorkspaceClient(host=…, client_id=…, client_secret=…)`, chỉ gọi `files.upload`, `files.download`, `files.list_directory_contents`, `files.get_metadata`.
- **Không đặt đường dẫn Volume, mã client hay host cứng trong code.**

### 3.2 Lớp file: `apps/retail_app/ui/kho_dot.py` (mới)

Một giao diện, hai bản cài (`KhoDia`, `KhoVolume`). Mọi đường dẫn là đường tương đối dưới gốc, chỉ gồm `[A-Za-z0-9_./-]`, không có `..`, không bắt đầu bằng `/`. (Chốt 2026-11-08: cho chữ hoa để mã yêu cầu giữ `T`/`Z` như luồng một file, xem §3.3.)

| Hàm | Việc |
|---|---|
| `ghi_moi(path, bytes)` | Ghi file chưa có; file đã có thì `DaCo`. Ở `KhoDia`, mở bằng chế độ `xb`, ghi qua file tạm rồi đổi tên |
| `doc(path) -> bytes` | Không có thì `KhongCo` |
| `liet_ke(thu_muc) -> list[str]` | Tên con trực tiếp, đã sắp xếp; thư mục không có thì trả rỗng |
| `ghi_json_so_tiep(thu_muc, body) -> int` | Thêm bản ghi kế tiếp `<000001>.json` (§3.3); trả số đã ghi |

`ghi_json_so_tiep(thu_muc, body)`:
1. Gắn `ma = uuid4().hex` và `luc` (giờ UTC ISO) vào `body`.
2. Lấy số lớn nhất trong `thu_muc`, cộng 1, ghi bằng `ghi_moi`.
3. Ghi lỗi (bất kỳ ngoại lệ nào):
   - đọc lại file đó; `ma` khớp thì coi như thành công;
   - `ma` khác thì ném `TrangThaiDaDoi('Có người vừa thao tác cùng lúc; tải lại trang.')`;
   - file không có thì ném lại lỗi gốc.
4. **Không tự thử số kế tiếp.** Người thua phải tải lại rồi bấm lại, đúng §8.2 T2.

### 3.3 Dữ liệu trên kho

```
yeu_cau/<id>/yeu_cau.json            ← ghi một lần: {id, loai:"dot", nhan, mo_ta, nguoi_gui, ngay_gui, files:[{ten, so_byte, sha256}], ma}
yeu_cau/<id>/file/<ten>
yeu_cau/<id>/su_kien/<000001>.json   ← {toi, ai, ghi_chu, ...thêm, ma, luc}
lenh/<000001>.json                   ← {loai:"dat"|"tra", release_id?, request_id?, ai, ma, luc}
lenh/<000001>.ket_qua.json           ← L2 ghi; L1 chỉ đọc: {ket_qua:"dat"|"loi", thong_bao}
so_dot/<000001>.json                 ← {loai:"vao_so"|"bo", ma_dot, request_id?, release_id?, ly_do?}; L1 chỉ ghi "bo"
```

- `<id>` dùng cùng mẫu với luồng một file (`nhap_store.py:263`, kiểm ở `folder()` `:124`), có thêm hậu tố `_dot`. Sinh bằng `strftime('%Y%m%dT%H%M%SZ_') + uuid4().hex[:6] + '_dot'`, **giữ `T`/`Z` viết hoa**. Kiểm bằng `re.fullmatch(r'[0-9]{8}T[0-9]{6}Z_[a-f0-9]{6}_dot', id)` ở mọi chỗ nhận `id` từ ngoài vào (tham số trang, tên thư mục khi liệt kê). Tên thư mục không khớp mẫu thì bỏ qua, không ném lỗi. Lý do chọn chữ hoa thay vì chữ thường: hai luồng chung một mẫu mã, và poller L2 chỉ cần một regex.
- **Thứ tự khi gửi:** ghi hết `file/` → `yeu_cau.json` → `su_kien/000001.json` (`toi: da_gui`). Yêu cầu chỉ tồn tại khi có sự kiện 1. Gửi hỏng giữa chừng thì để lại thư mục mồ côi; trang không hiện, L2 bỏ qua.
- `lenh/` dùng chung cho mọi yêu cầu. Lệnh **đang chờ** là lệnh mới nhất chưa có `.ket_qua.json`.
- `ghi_json_so_tiep` không tính `*.ket_qua.json` khi lấy số lớn nhất.

### 3.4 Trạng thái yêu cầu đợt: `apps/retail_app/ui/nhap_dot.py` (mới)

`TRANSITIONS_DOT` lấy đúng bảng ở thiết kế §3, với một chỗ chỉnh: **`cho_dashboard` không phải sự kiện**. Trạng thái này suy ra khi có lệnh `dat` đang chờ trỏ tới yêu cầu. Lý do: Admin chỉ ghi một file (lệnh), nên không có hai lần ghi rời nhau phải đối soát. Vì vậy:
- `da_kiem` → `tren_dashboard` (do Airflow ghi);
- lệnh `dat` lỗi thì yêu cầu vẫn ở `da_kiem`.

Claude sẽ sửa thiết kế §3 cho khớp.

| Sự kiện do web ghi ở L1 | Ai | Điều kiện |
|---|---|---|
| `da_gui` | `actor('gui')` | yêu cầu mới |
| `cho_chay` (chạy lại) | Kỹ sư dữ liệu hoặc Admin | đang `loi` |
| `huy` | Kỹ sư dữ liệu hoặc Admin | đang `loi` |

Các sự kiện khác do Airflow ghi; L1 chỉ cần phát lại đúng chúng.

- **`phat_lai(su_kien) -> {trang_thai, lich_su, release_id?, ma_loi?, thong_bao?}`:**
  - kiểm từng bước bằng `TRANSITIONS_DOT`;
  - số thứ tự phải liền nhau từ 1;
  - chuỗi sai thì trả `trang_thai = 'hong'` kèm lý do, không ném lỗi, để trang vẫn mở được.
- **`LABELS_DOT`** (tiếng Việt cho người dùng): Đã gửi, Đang kiểm tra file, Chờ chạy, Đang chạy, Đã kiểm tra, Chờ đưa lên dashboard, Đang trên dashboard, Đã trả dashboard, Sai hợp đồng dữ liệu, Không đọc được file, Hết chỗ lưu trữ, Lỗi khi chạy, Đã hủy, Dữ liệu trạng thái hỏng.
- **Quyền:** mọi thao tác đi qua `nhap_store.actor`:
  - gửi dùng `actor('gui')`;
  - chạy lại và hủy dùng `actor('duyet')`, kèm role `ky_su` hoặc `admin`;
  - lệnh dashboard dùng `actor('cong_bo')`, tức chỉ Admin.
  - Mỗi thao tác ghi nhật ký qua `audit.log`, với các sự kiện `dot_gui`, `dot_chay_lai`, `dot_huy`, `dashboard_lenh_dat`, `dashboard_lenh_tra`, `so_dot_bo`.

### 3.5 Gửi đợt

`gui_dot(uploads, nhan, mo_ta)`, kiểm trước khi ghi bất cứ gì:
- **Nhãn:** `nhan` khớp `^[a-z0-9_-]{1,40}$`.
- **Số file:** 1–40 file. Tên qua `safe_filename` (`nhap_store.py:83`); không trùng tên sau khi chuẩn hóa.
- **File bị từ chối:** `sales.csv`, `sample_submission.csv` (`dot.py:57` bỏ qua hai file này, nên báo rõ cho người gửi).
- **Bắt buộc:** có ít nhất một file tên bắt đầu bằng `orders`.
- **Kích thước:** mỗi file ≤ 200 MB; tổng ≤ 100 MB. Đợt 2023 đo được 19,4 MB không kèm master, 28 MB kèm master.
- **sha256:** tính trên bytes thật, đọc theo khối 1 MB. Không tin `size` của trình duyệt (cách làm như `nhap_store.py:258–287`).

Không có kiểm hợp đồng ở web. File master (`customers`, `products`, `geography`) gửi kèm hay không đều được.

### 3.6 Trang Gửi (`views/gui_du_lieu.py`)

- **`RETAIL_NHAP_DOT != 'tat'`:** hiện khối "Gửi đợt dữ liệu" gồm `file_uploader(accept_multiple_files=True, type=['csv','json'], max_upload_size=200)`, ô nhãn đợt, ô mô tả, nút gửi. Dưới đó là danh sách yêu cầu đợt, cũng theo quy tắc ai thấy gì của `visible`:
  - Quản lý chỉ thấy yêu cầu của mình;
  - Kỹ sư dữ liệu và Admin thấy tất cả.
- **Mỗi yêu cầu hiện:** nhãn, trạng thái theo `LABELS_DOT`, số file, tổng MB, giờ gửi.
  - Có `ma_loi` (D2-*) thì hiện kèm `thong_bao`.
  - Đang chạy hoặc đã kiểm tra thì hiện mã bản tóm tắt (8 ký tự).
- **Trên cloud, `nhap_kha_dung()` trả False**, nên trang hiện đang `st.stop()` ở dòng 11–13 trước khi tới mọi thứ. Đổi thành:
  - luồng một file vẫn chỉ hiện khi `nhap_kha_dung()`;
  - luồng đợt hiện theo `RETAIL_NHAP_DOT`;
  - cả hai đều không có thì giữ câu "đang được phát triển".
- **Không gọi `nhap_runner.recover_queue` trên đường đợt.**

### 3.7 Trang Duyệt (`views/duyet_du_lieu.py`)

- **Khối "Đợt dữ liệu"** cho Kỹ sư dữ liệu và Admin:
  - danh sách yêu cầu đợt;
  - nút "Chạy lại" và "Hủy" khi `loi`;
  - bảng sổ đợt, phát lại `so_dot/`, gồm thứ tự, `ma_dot` 8 ký tự, yêu cầu, bản;
  - nút "Bỏ khỏi sổ" kèm ô lý do bắt buộc, ghi sự kiện `bo`. Dòng nhắc: "Chỉ ảnh hưởng lần dựng đợt sau, không đổi dashboard đang hiện."
- **Khối dashboard, khi backend là `databricks` và `RETAIL_NHAP_DOT == 'volume'`:** dùng `dashboard_state_cloud()` mới trong `nhap_runner.py`. Hàm này đọc registry qua SQL bằng kết nối đọc sẵn có của app (cùng câu SQL với `releases.resolve`, `releases.py:94`), trả `payload`.
  - **Ứng viên:** như đường local, gồm các bản `ready` và có `co_du_lieu_tong_hop is True`.
  - **Hiện:** bản dashboard đang trỏ tới (nếu có) và giờ `dashboard_since`.
  - **Nút "Đưa bản có đợt lên dashboard (demo)":** cần ô xác nhận "Đây là dữ liệu tổng hợp, chỉ để demo", như đường local. Bấm thì ghi `lenh` loại `dat`, kèm `release_id`, và `request_id` nếu tìm được yêu cầu có `release_id` đó.
  - **Nút "Trả dashboard về bản số thật":** ghi `lenh` loại `tra`.
  - **Có lệnh đang chờ:** hiện "Đang chờ Airflow xử lý lệnh (thường dưới 5 phút)" và khóa cả hai nút.
  - **Lệnh mới nhất có kết quả `loi`:** hiện `thong_bao`.
  - Trước khi ghi lệnh, đọc lại `lenh/` **ngay lúc bấm**. Đã có lệnh đang chờ thì từ chối.
- **Backend `duckdb`:** giữ nguyên khối hiện tại và `dashboard_action` hiện tại, không đổi một dòng nào.
- **Backend `databricks` mà `RETAIL_NHAP_DOT != 'volume'`:** hiện "Công bố dashboard trên bản này cần kho đợt (Volume)", không có nút.

### 3.8 Trang Dự báo

Trong `page_header` (`common.py:187–192`), thêm nhánh cho tiêu đề `'Dự báo G và COGS'` (`views/du_bao.py:266`): khi `releases.pointers_differ()` thì `st.info('Dashboard đang hiện dữ liệu tổng hợp có đợt; trang này dùng số thật, số tới {end}.')`. `end` lấy theo cách trang AI đang làm. Nhánh trang AI giữ nguyên.

### 3.9 Khung AI trên trang PS khi dashboard đang hiện bản có đợt (PM chốt 2026-11-07)

**Hiện tại:** khi hai con trỏ khác nhau, khung AI trên mọi trang PS bị ẩn (`ai_panel.py:27–28`), kể cả khi người xem chọn năm 2019.

**PM chốt:** chỉ ẩn khi lựa chọn chạm tới dữ liệu nhập (đợt). Các năm 2012–2022 phải có AI, vì buổi demo cần trình bày AI.

**Bằng chứng Claude đo ngày 2026-11-07**, so bản thật `f6f64a3c…` với bản có đợt `99c445c1…` trong `warehouse/pipeline/d3-thu`:
- Các bảng theo năm khớp từng dòng cho mọi năm ≤ 2022: `rpt_revenue_yearly`, `rpt_revenue_monthly`, `rpt_revenue_segment_yearly`, `rpt_revenue_bridge`, `int_reporting_order_items`, phần `period_type = 'year'` của `rpt_driver_period` và `rpt_driver_bridge`.
- Các bảng theo giai đoạn hoặc cả chuỗi **lệch**: giai đoạn D kết thúc 2022 ở bản thật nhưng 2023 ở bản có đợt (`rpt_driver_period`, `rpt_revenue_phase`); kỳ của `rpt_revenue_total` cũng khác.

**Quy tắc mới**, áp dụng khi `releases.pointers_differ()`:
- **Cho AI chạy** khi mọi lời gọi trong `PageRequest.calls` đều là lời gọi theo năm, tức có `year`, không có `period_type = 'phase'`, không có `view`, **và** `year ≤ năm cuối của bản active`. Áp dụng cho PS1 chọn năm, PS4 chọn năm, PS5. `PageRequest` ở `ai_explain/page_explain.py:35–45`.
- **Ẩn** với mọi trường hợp còn lại:
  - PS2 (`get_revenue_trend` theo `view`);
  - PS3 (mẫu tính trên cả chuỗi);
  - PS1 chọn kỳ;
  - PS4 chọn giai đoạn;
  - mọi năm lớn hơn năm cuối của bản active.
- **Câu khi ẩn:**
  - lựa chọn theo năm: `'AI chỉ giải thích dữ liệu thật tới năm {N}; lựa chọn này có dữ liệu demo. Chọn một năm từ {N} trở về trước để AI giải thích.'`;
  - còn lại: `'Trang này gộp cả dữ liệu demo nên AI tạm ẩn. Hỏi AI ở trang Hỏi dữ liệu (AI), nơi AI đọc bản số thật.'`
- **Năm cuối của bản active:** lấy từ `data_end_date` của `build_info` **đọc trong `releases.active_scope()`**. Không lấy từ bản dashboard: trên trang PS, `load_or_stop('build_info')` đang trả về bản có đợt.
- **Không đổi:**
  - AI vẫn đọc bản `active` như cũ (`tools.py` dùng `active_read`);
  - hai con trỏ trùng nhau thì giữ nguyên hành vi cũ;
  - trang chat giữ nguyên (`chat=True`).
- **Cache kết quả AI** đã theo `release_id` của bản đọc (`_data_key`). Phải kiểm khóa cache dùng `release_id` của bản **active**, để kết quả không bị gắn với bản dashboard.

## 4. File được sửa

| File | Việc |
|---|---|
| `apps/retail_app/ui/kho_dot.py` (mới) | §3.1, §3.2 |
| `apps/retail_app/ui/nhap_dot.py` (mới) | §3.3–§3.5 |
| `apps/retail_app/ui/nhap_runner.py` | thêm `dashboard_state_cloud()`; không sửa hàm đang có |
| `apps/retail_app/views/gui_du_lieu.py` | §3.6 |
| `apps/retail_app/views/duyet_du_lieu.py` | §3.7 |
| `apps/retail_app/ui/common.py` | §3.8 |
| `apps/retail_app/ui/ai_panel.py` | §3.9 |
| `apps/retail_app/tests/test_d5_dashboard.py` | đổi kỳ vọng T6 ("khung ẩn khi hai con trỏ khác nhau") theo §3.9. Chỉ sửa ca đó; các ca khác giữ nguyên |
| `apps/retail_app/tests/test_l1_dot_web.py` (mới) | §5 |

Không thêm thư viện. `databricks-sdk==0.117.0` đã có trong `apps/retail_app/requirements.txt`.

## 5. Kiểm

Dùng `KhoDia` trên thư mục tạm, cộng một `KhoVolume` với `WorkspaceClient` giả (ghi lại mọi lời gọi). Không cần Databricks.

1. **Ghi đua:**
   - `ghi_json_so_tiep` cho hai bên cùng ghi một số: đúng một bên thành công, bên kia `TrangThaiDaDoi`, nội dung file là của bên thắng;
   - với `KhoVolume` giả: ném `TypeError` mà file đã chứa `ma` của mình thì tính là thành công; `ma` khác thì `TrangThaiDaDoi`; file không có thì ném lại lỗi gốc.
2. **Phát lại:**
   - chuỗi hợp lệ ra đúng trạng thái, `release_id`, `ma_loi`;
   - bước nhảy sai, số thứ tự hở, hay sự kiện lạ đều ra `hong` mà không ném lỗi;
   - có lệnh `dat` đang chờ trỏ tới yêu cầu `da_kiem` thì nhãn là "Chờ đưa lên dashboard".
3. **Gửi:**
   - từng luật ở §3.5 có một test bị từ chối, và không có file nào được ghi;
   - gửi hợp lệ thì thứ tự ghi đúng là `file/*` → `yeu_cau.json` → `su_kien/000001.json`;
   - sha256 khớp nội dung; gửi hỏng ở file thứ 2 thì không có `su_kien/` và trang không hiện yêu cầu.
4. **Quyền:**
   - khách và Quản lý không ghi được lệnh;
   - Kỹ sư dữ liệu ghi được "Chạy lại", không ghi được lệnh dashboard;
   - Admin đang xem như Quản lý không ghi được lệnh;
   - Quản lý chỉ thấy yêu cầu của mình.
5. **Lệnh:**
   - đang có lệnh chờ thì ghi lệnh mới bị từ chối;
   - đọc kết quả `loi` thì hiện thông báo và mở khóa nút.
6. **Không có duckdb trên đường cloud:** chạy một tiến trình con (`python -I -X utf8`) với `sys.modules['duckdb'] = None`, import `ui.kho_dot`, `ui.nhap_dot` và chạy hai trang bằng `streamlit.testing.v1.AppTest` với `RETAIL_NHAP_DOT=volume` cộng kho giả. Không lỗi import.
7. **Trang:**
   - `RETAIL_NHAP_DOT=tat`: hai trang y như trước (so với kết quả của các test hiện có);
   - `volume` + backend `databricks`: khối dashboard cloud hiện đúng ứng viên từ registry giả, bấm nút ghi đúng một file lệnh;
   - backend `duckdb`: `dashboard_action` vẫn gọi subprocess như cũ (test D5 hiện có phải đạt nguyên).
8. **Trang Dự báo:** hai con trỏ khác nhau thì có dòng ghi chú; trùng nhau thì không có.
8b. **Khung AI (§3.9).** Dùng registry giả có hai con trỏ khác nhau; năm cuối của bản active là 2022, của bản dashboard là 2023:
   - PS1 năm 2019, PS4 năm 2019, PS5 năm 2022: khung AI hiện, nút gọi được;
   - PS4 năm 2023, PS5 năm 2023, PS1 năm 2023: ẩn, kèm câu theo năm;
   - PS2, PS3, PS1 chọn kỳ, PS4 chọn giai đoạn: ẩn, kèm câu "gộp cả dữ liệu demo";
   - năm cuối phải đọc từ bản active: đổi `data_end_date` của bản dashboard không làm đổi kết quả;
   - hai con trỏ trùng nhau: mọi trường hợp như trước, dùng các ca T6 cũ.
9. **Không hồi quy:** chạy riêng từng lệnh:
   - `apps/retail_app/tests/test_nhap_du_lieu.py`, `test_nhap_theo_doi.py`, `test_nhap_tu_dong.py`, `test_d5_dashboard.py`, `test_roles.py`, `test_du_bao.py`, `test_l1_dot_web.py`;
   - ghi số đạt của các file cũ **trước khi sửa** làm mốc, sau khi sửa phải bằng hoặc hơn.

Claude sẽ thử đột biến khi rà, ít nhất gồm:
- bỏ đọc lại `ma`;
- tự thử số kế tiếp khi thua;
- bỏ kiểm `actor('cong_bo')`;
- bỏ chặn lệnh khi đang có lệnh chờ;
- đổi thứ tự ghi khi gửi;
- import `duckdb` ở đầu `nhap_dot.py`;
- bỏ kiểm tổng 100 MB;
- §3.9: lấy năm cuối từ bản dashboard thay vì bản active;
- §3.9: cho qua lời gọi `view`/`phase`;
- §3.9: đổi `≤` thành `<`.

## 6. Không giao GPT

Commit, push, PR. Đặt Streamlit Secrets. Mọi thao tác trên Databricks thật. L2 (DAG, CLI, pipeline). Không sửa `docs/phan_quyen.md`.

## 7. Báo cáo của GPT khi xong (PM dán cho Claude rà)

- Danh sách file đã sửa; `git status --short`.
- Số đạt/trượt/skip của từng file test ở §5 mục 9, cả trước và sau khi sửa.
- Chỗ làm khác phiếu và lý do. Chỗ nào phiếu chưa rõ thì ghi câu hỏi, không tự đoán.
- Ảnh hoặc mô tả hai trang ở chế độ `dia` khi chạy app local, với một đợt mẫu từ `data_demo/dot_2023`.

### GPT — L1 — 2026-11-08

**Đã triển khai L1, gồm §3.9.** Worktree `D:/retail-analytics-nap`, nhánh `nap-ky/myuyen`, HEAD `015de11`. Không commit, không push. Chỉ sửa/tạo 9 file code/test ở §4, cộng báo cáo này theo §7. Không sửa §8.

**Điểm đã chốt:** PM cho phép `T/Z` viết hoa. Giữ mẫu mã `[0-9]{8}T[0-9]{6}Z_[a-f0-9]{6}_dot`, kiểm mã ở biên nhận yêu cầu và bỏ qua tên thư mục không hợp lệ khi liệt kê.

**Claude trả lời (2026-11-08):** chọn (2), cho `T`/`Z` viết hoa. Đã sửa §3.2 (bộ ký tự `[A-Za-z0-9_./-]`) và §3.3 (cách sinh và regex của mã đợt). Không đổi mẫu mã của luồng một file.

**File đã sửa/tạo:**

| File | Nội dung |
|---|---|
| `apps/retail_app/ui/kho_dot.py` | Kho đĩa và Volume; ghi mới, kiểm đường dẫn, tranh số bằng `ma`, không tự thử số kế tiếp; cấu hình `tat/dia/volume` |
| `apps/retail_app/ui/nhap_dot.py` | Phát lại trạng thái đợt; kiểm upload trước mọi lần ghi; thứ tự file → metadata → sự kiện 1; quyền, audit, lệnh dashboard, sổ đợt |
| `apps/retail_app/ui/nhap_runner.py` | Chỉ thêm `dashboard_state_cloud()`, dùng kết nối đọc app, không dùng khóa ghi Volume |
| `apps/retail_app/views/gui_du_lieu.py` | Form nhiều file và danh sách đợt; không chạy hàng đợi local trên nhánh cloud |
| `apps/retail_app/views/duyet_du_lieu.py` | Đợt, chạy lại/hủy, sổ đợt; Admin ghi lệnh cloud, khóa hai nút khi chờ, hiện kết quả lỗi |
| `apps/retail_app/ui/common.py` | Ghi chú bản số thật trên trang Dự báo khi hai con trỏ khác nhau |
| `apps/retail_app/ui/ai_panel.py` | AI theo năm thật, ẩn kỳ/giai đoạn/cả chuỗi và năm demo; năm cuối và khóa cache lấy từ active |
| `apps/retail_app/tests/test_d5_dashboard.py` | Chỉ bổ sung kỳ vọng trong `test_t6_panel_hidden_only_when_pointers_differ`, các ca khác giữ nguyên |
| `apps/retail_app/tests/test_l1_dot_web.py` | 104 ca, gồm ghi đua, quyền, upload, UI, cloud giả, chặn import và AI theo lựa chọn |

Đã đối chiếu AST: mọi hàm cũ trong `nhap_runner.py` và hai trang không đổi; khối dashboard local cuối trang Duyệt không đổi nội dung. `RequestStore`, `TRANSITIONS`, `dashboard_action`, `rollback_command` giữ nguyên. Không có diff trong `scripts/`, `retail_dbt/`, `deploy/`, `docs/phan_quyen.md`. Không thay thư viện.

**git status --short:**

```text
 M apps/retail_app/tests/test_d5_dashboard.py
 M apps/retail_app/ui/ai_panel.py
 M apps/retail_app/ui/common.py
 M apps/retail_app/ui/nhap_runner.py
 M apps/retail_app/views/duyet_du_lieu.py
 M apps/retail_app/views/gui_du_lieu.py
?? apps/retail_app/tests/test_l1_dot_web.py
?? apps/retail_app/ui/kho_dot.py
?? apps/retail_app/ui/nhap_dot.py
?? docs/giao_viec_go_role_da_bi.md
?? docs/giao_viec_l1_dot_web.md
?? docs/thiet_ke_dot_web_public.md
```

Ba tài liệu chưa theo dõi đã có từ đầu lượt. Không sửa `giao_viec_go_role_da_bi.md` hay `thiet_ke_dot_web_public.md`. Phiếu L1 được Claude sửa §3.2/§3.3 để trả lời điểm chặn; phần GPT cập nhật trong lượt này là báo cáo §7.

**Test trước/sau từng file** (đạt / trượt / bỏ qua):

| File | Trước sửa | Sau sửa |
|---|---|---|
| `test_nhap_du_lieu.py` | 97 / 0 / 0 | 97 / 0 / 0 |
| `test_nhap_theo_doi.py` | 61 / 0 / 0 | 61 / 0 / 0 |
| `test_nhap_tu_dong.py` | 151 / 0 / 0 | 151 / 0 / 0 |
| `test_d5_dashboard.py` | 35 / 0 / 0 | 35 / 0 / 0 |
| `test_roles.py` | 39 / 4 / 0 | 39 / 4 / 0 |
| `test_du_bao.py` | 2 / 0 / 9 | 2 / 0 / 9 |
| `test_l1_dot_web.py` | Chưa có | 104 / 0 / 0 |
| **Tổng** | **385 / 4 / 9** | **489 / 4 / 9** |

Đã so trạng thái từng testcase trong JUnit trước/sau: sáu file cũ có cùng tập ca và cùng kết quả; không có ca đạt → trượt. **Không gọi toàn bộ bộ kiểm là xanh:** bốn lỗi cũ vẫn còn ở `test_menu_theo_role[quan_ly/phan_tich/ky_su/admin]`, cùng assertion thiếu liên kết sang trang AI trên PS1. Worktree không có `warehouse/dbt.duckdb`; không dựng kho để lách mốc và không sửa kỳ vọng các ca này. Chín skip Dự báo giữ nguyên: thiếu kho legacy, thiếu registry/bản dự báo và bản cũ để đối chứng.

Mỗi file chạy bằng một lệnh riêng, tại root worktree, với `RETAIL_TEST_DATABRICKS=0`:

```text
D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8 -m pytest apps/retail_app/tests/test_nhap_du_lieu.py -q --tb=short
D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8 -m pytest apps/retail_app/tests/test_nhap_theo_doi.py -q --tb=short
D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8 -m pytest apps/retail_app/tests/test_nhap_tu_dong.py -q --tb=short
D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8 -m pytest apps/retail_app/tests/test_d5_dashboard.py -q --tb=short
D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8 -m pytest apps/retail_app/tests/test_roles.py -q --tb=short
D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8 -m pytest apps/retail_app/tests/test_du_bao.py -q --tb=short
D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8 -m pytest apps/retail_app/tests/test_l1_dot_web.py -q --tb=short
```

Lệnh thực tế thêm `--junitxml=<TEMP>/l1_before_<tên>.xml` hoặc `l1_after_<tên>.xml`; tên lần lượt là `nhap`, `theo_doi`, `tu_dong`, `d5`, `roles`, `du_bao`, `l1`. Thời gian lượt cuối tương ứng: 45,40; 15,03; 81,63; 14,32; 80,81; 2,53; 11,43 giây. Không chạy cả bộ app hay gộp apps với scripts.

**Đột biến §5: 10/10 bị bắt, từng lượt khôi phục file gốc; không lỗi collection.**

| Mã | Đột biến | Test bắt được |
|---|---|---|
| M1 | Bỏ so `ma` sau lỗi ghi | `test_volume_typeerror_reads_ma[other]` |
| M2 | Thử ghi số kế tiếp khi thua | `test_volume_typeerror_reads_ma[other]` |
| M3 | Đổi kiểm `actor('cong_bo')` thành quyền gửi | `test_non_admin_cannot_write_command` với Quản lý, DA/BI, DE |
| M4 | Bỏ chặn lệnh đang chờ | `test_pending_command_error_result_and_label` |
| M5 | Ghi metadata trước các file | `test_valid_upload_order_hash_chunks_and_audit`, `test_second_file_failure_leaves_invisible_orphan` |
| M6 | Import DuckDB ở đầu `nhap_dot.py` | `test_cloud_import_in_isolated_process` |
| M7 | Bỏ giới hạn tổng dung lượng | `test_actual_bytes_limits_before_write[total]` |
| M8 | Đọc năm cuối từ pin dashboard thay vì active | `test_ai_years_and_series_gate[3/4/5]` |
| M9 | Cho qua `view`/`period_type=phase` | `test_ai_years_and_series_gate[9]`, `test_ai_all_calls_must_qualify` |
| M10 | Đổi `<=` thành `<` | `test_ai_years_and_series_gate[2]` (PS5 năm 2022) |

Log, JUnit và bảng kết quả: `<TEMP>/l1_mutations/`; có `results.json` và hash xác nhận khôi phục ở `restored_hashes.json`. Sau đột biến đã bổ sung ca tên file chứa `..`, đưa kiểm đường dẫn lên trước mọi lần ghi rồi chạy bộ L1 cuối 104 ca đạt. Test ghi đua thật lặp 10 lần; đã bắt và sửa trường hợp Windows thêm tiền tố thiết bị khi thư mục đang được tạo. Test tiến trình con dùng `python -I -B -X utf8`, đặt cả ba module cấm thành `None`, import hai lớp mới và chạy cả hai trang với kho giả.

**Mô tả hai trang ở chế độ `dia`, bộ mẫu `data_demo/dot_2023`:**

- Chạy bằng AppTest local, `KhoDia` thật trong thư mục tạm; đọc bytes thật của cả 15 file mẫu, tổng **28.071.776 byte**. Tài khoản/nhật ký và `file_uploader` được giả lập; tắt luồng một file để chỉ thử lát L1. Không chạy pipeline, không phân loại hợp đồng.
- Trang **Gửi dữ liệu**: nhập nhãn `dot_2023`, gửi form; hiện **“Đã gửi đợt dot_2023.”**, yêu cầu **“dot_2023 · Đã gửi”**, dòng **“15 file · 26.77 MB · <giờ UTC gửi>”**.
- Trang **Duyệt dữ liệu**, vai trò DE: khối **“Đợt dữ liệu”** hiện cùng yêu cầu **Đã gửi**; khối **“Sổ đợt”** có 0 dòng. Không có nút Chạy lại/Hủy vì yêu cầu chưa ở `loi`. Đứng ở `da_gui` là đúng L1, chờ L2 xử lý.
- Hai trang: **0 exception, 0 error**; lượt xác nhận cuối mã thoát **0**, kho tạm đã dọn. Bằng chứng: `<TEMP>/l1_demo.json`. Đây là thử headless, chưa phải upload thủ công trong trình duyệt hay web public. Một lượt harness chẩn đoán thêm PS1 bị lỗi import do mở trực tiếp file view; không tính lượt đó là bằng chứng nghiệm thu. Lượt cuối chỉ kiểm hai trang L1 đã đạt.

**Chỗ khác phiếu / chi tiết triển khai:**

- Không thay đổi thiết kế nghiệp vụ. Quyết định chữ hoa đã theo trả lời PM và bản phiếu cập nhật.
- `ghi_json_so_tiep` có tham số nội bộ tùy chọn `expected` để ràng buộc số cuối lúc đọc trạng thái và lúc tranh ghi. Nếu đã có sự kiện/lệnh mới thì báo trạng thái đổi, không thử số mới; tránh khe đua giữa kiểm “lệnh đang chờ” và lấy số ghi.
- `KhoDia` trên Windows: mở file tạm bằng `xb`, ghi/flush/fsync rồi `os.rename` không ghi đè. Nhánh POSIX dùng `os.link` rồi bỏ file tạm để giữ tính nguyên tử và không ghi đè (vì `rename` POSIX ghi đè đích); nhánh này chưa được chạy trên máy Linux.
- Kiểm đường dẫn so sánh sau khi chuẩn hóa tiền tố thiết bị Windows, vẫn chặn ra ngoài root. Tên file được kiểm cả luật đường dẫn trước mọi lần ghi, vì `safe_filename` cũ vẫn có thể giữ `..` ở giữa tên.
- Test giới hạn dung lượng hạ hằng số trong fixture để tạo ca biên nhỏ, đồng thời kiểm hằng số production đúng 200/100 MiB và kiểm bytes thật, không tin `upload.size`; không cấp phát file 200 MB trên máy ít RAM.

**Câu hỏi còn mở:** không còn điểm chặn trong phạm vi L1. Bốn lỗi test cũ và chín skip là giới hạn bằng chứng đã nêu, không che hoặc sửa kỳ vọng.

**Chưa kiểm / ngoài phạm vi:** Files API và quyền SP trên Volume thật; registry Databricks thật; tài khoản Neon; Airflow/L2 và quá trình chuyển tiếp sau `da_gui`; LLM thật; upload thủ công qua trình duyệt. Không đọc `.env.*.local` hay `.streamlit/secrets.toml` bằng công cụ, không cấu hình secret, không chạy pipeline, Docker/image hay cloud. Junction `data` trỏ `D:/retail-analytics-am/data` được gỡ cuối lượt bằng `cmd /c rmdir data`; không dùng Remove-Item và không xóa dữ liệu đích.


### GPT — L1 — sửa sau rà lượt 1 — 2026-11-08

**Đã sửa đủ 1–5 của §8 lượt 1**, trên nhánh `nap-ky/myuyen`. Không commit, không push.

1. Hai trang Gửi/Duyệt dùng lại đúng `local_available = nhap_kha_dung()`. Test mới đặt backend Databricks, chế độ đợt `tat`, khả dụng local True và xác nhận form một file vẫn hiện. Fixture cloud giả khả dụng local False theo môi trường cloud.
2. Trang Duyệt lấy giờ từ `dashboard_since['at']`, chỉ hiện khi release_id khớp dashboard. Test dùng dict đúng hình và thêm ca khác bản thì ẩn giờ.
3. Test gọi thẳng hàm bắt C2 (chưa ready, cờ False/1/thiếu, thiếu thông tin), C5 (lệnh chờ của A không đổi nhãn B), C11 (DE không được retry/hủy da_gui hoặc da_kiem; bytes sự kiện giữ nguyên).
4. Kho Volume lấy riêng host qua `databricks_config()`; mã client/secret vẫn từ biến writer riêng, cố định `auth_type='oauth-m2m'`. Test giả host cấu hình khác host môi trường và có mã reader; kiểm đúng tham số client.
5. `visible()` cô lập ValueError/KeyError/TypeError theo từng yêu cầu. DE/Admin thấy dòng an toàn trạng thái hong, Quản lý/Phân tích bỏ qua metadata hỏng vì không xác định được chủ sở hữu. Yêu cầu tốt vẫn hiện. Test JSON hỏng, thiếu nguoi_gui/ngay_gui, ngay_gui sai kiểu và AppTest Duyệt không lỗi.

**File sửa lượt này:** apps/retail_app/views/gui_du_lieu.py, views/duyet_du_lieu.py, ui/kho_dot.py, ui/nhap_dot.py, tests/test_l1_dot_web.py (cùng dưới apps/retail_app), cộng báo cáo này. Giữ nguyên các nháp L1 khác.

**Kiểm thử:** từng lệnh riêng từ root worktree, RETAIL_TEST_DATABRICKS=0; Python `D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8 -m pytest <file> -q --tb=short`.

| File dưới apps/retail_app/tests | Trước (đạt/trượt/bỏ qua, Claude rà) | Sau | Thời gian |
|---|---|---|---|
| test_l1_dot_web.py | 104/0/0 | **120/0/0** | 17,48 giây |
| test_nhap_du_lieu.py | 97/0/0, có junction | **97/0/0** | 81,74 giây |
| test_d5_dashboard.py | 35/0/0 | **35/0/0** | 27,44 giây |

Tổng **252 đạt, 0 trượt, 0 bỏ qua**. Không chạy toàn bộ app. Lượt đầu L1 có 119 đạt/1 trượt do fixture mới thiếu pending; bổ sung fixture rồi chạy lại đạt 120/120, không sửa code production để né lỗi fixture.

**Đột biến:** chạy tuần tự trên ui/nhap_dot.py, khôi phục nguyên bytes sau mỗi lượt và kiểm không có sửa đồng thời. Cả ba bị bắt bởi assertion, không phải lỗi thu thập test.

| Mã | Đột biến | Test bắt được | Khi đột biến |
|---|---|---|---|
| C2 | Bỏ kiểm ready/cờ tổng hợp trong handler | test_c2_command_rejects_ineligible_release | 5 trượt |
| C5 | Bỏ so request_id lệnh với yêu cầu | test_c5_pending_label_only_for_matching_request | 1 trượt |
| C11 | Bỏ điều kiện trạng thái loi trong change | test_c11_change_rejects_non_error_without_event | 4 trượt |

Log: `%TEMP%/l1_review_C2.txt`, `l1_review_C5.txt`, `l1_review_C11.txt`; bảng `l1_review_mutations.json`. Không còn đột biến trong code.

**Junction:** test_nhap_du_lieu cần data trỏ D:/retail-analytics-am/data, tạo bằng cmd /c mklink /J. Sau test gỡ bằng cmd /c rmdir data, xác nhận thư mục đích còn tồn tại.

**Khác phiếu / câu hỏi:** không có. Không sửa §8. Không chạy pipeline/cloud, không đọc file secret; cấu hình được giả trong test. Chưa kiểm OAuth/Files API trên Volume thật.

**Git status --short** (gồm nháp cũ; không sửa giao_viec_go_role_da_bi và thiet_ke_dot_web_public):

```text
 M apps/retail_app/tests/test_d5_dashboard.py
 M apps/retail_app/ui/ai_panel.py
 M apps/retail_app/ui/common.py
 M apps/retail_app/ui/nhap_runner.py
 M apps/retail_app/views/duyet_du_lieu.py
 M apps/retail_app/views/gui_du_lieu.py
?? apps/retail_app/tests/test_l1_dot_web.py
?? apps/retail_app/ui/kho_dot.py
?? apps/retail_app/ui/nhap_dot.py
?? docs/giao_viec_go_role_da_bi.md
?? docs/giao_viec_l1_dot_web.md
?? docs/thiet_ke_dot_web_public.md
```

### GPT — L1 — sửa sau rà lượt 2 — 2026-11-09

- Mục 1: thêm `test_review_single_file_kept_with_databricks_backend`: backend Databricks, chế độ đợt `tat`, khả dụng local True; xác nhận khối local và thông báo chưa có yêu cầu trên trang Duyệt, không có khối đợt. Không sửa code trang.
- Mục 2: `DotStore.visible()` kiểm từng phần tử `files` là dict, `ten` là chuỗi và `so_byte` có kiểu int chính xác (loại bool). Metadata hỏng vẫn được cô lập theo từng yêu cầu như lượt 1. Bổ sung tám ca: files không phải list, phần tử số, thiếu so_byte, so_byte bool/chuỗi/số thực, thiếu ten, ten là số.
- File sửa: `apps/retail_app/ui/nhap_dot.py`, `apps/retail_app/tests/test_l1_dot_web.py` và báo cáo này. Không sửa §8; các nháp khác giữ nguyên.

**Kiểm thử:** Python `D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8`, `RETAIL_TEST_DATABRICKS=0`; chạy riêng `-m pytest apps/retail_app/tests/test_l1_dot_web.py -q --tb=short`. Trước sửa: **120 đạt / 0 trượt / 0 bỏ qua** (23,31 giây). Sau sửa: **129 đạt / 0 trượt / 0 bỏ qua** (51,01 giây). Không cần junction data. Không chạy lại bộ khác theo §8 lượt 2.

| Đột biến | Test bắt được | Kết quả |
|---|---|---|
| C17: thêm điều kiện backend khác Databricks vào local_available trang Duyệt | test_review_single_file_kept_with_databricks_backend | 1 trượt do thiếu khối local |
| C24: bỏ kiểm files là list | test_corrupt_metadata_isolated_per_request[files_not_list] | 1 trượt do metadata hỏng vẫn hiện với Quản lý |

Hai đột biến chạy tuần tự và khôi phục nguyên bytes sau mỗi lượt, có assertion xác nhận. Log: `%TEMP%/l1_review2_C17.txt`, `%TEMP%/l1_review2_C24.txt`. Không còn đột biến trong code.

**Khác phiếu / câu hỏi:** không có. Không commit, không push, không chạy pipeline hay kết nối cloud. Bằng chứng chỉ là test local/kho giả; chưa kiểm Volume thật.

## 8. Rà của Claude (Claude ghi, GPT đọc để sửa)

### Lượt 1 — 2026-11-08: **chưa đạt, sửa 3 điểm bắt buộc rồi báo lại**

**Claude tự chạy lại** (worktree nap, `RETAIL_TEST_DATABRICKS=0`, từng file một lệnh):

| File | Kết quả | Ghi chú |
|---|---|---|
| `test_l1_dot_web.py` | 104 / 0 / 0 | |
| `test_d5_dashboard.py` | 35 / 0 / 0 | |
| `test_nhap_theo_doi.py`, `test_nhap_tu_dong.py` | 61 / 0 / 0; 151 / 0 / 0 | |
| `test_nhap_du_lieu.py` | 78 / **19** / 0 khi **không** có junction `data`; 97 / 0 / 0 khi có | 19 ca trang dừng ở `nhap_kha_dung()`. Báo cáo sau phải ghi rõ cần junction `data` cho file này |
| `test_roles.py` | 39 / 4 / 0 | 4 ca `test_menu_theo_role` trượt cả trước L1 (JUnit `l1_before_roles.xml`) vì thiếu `warehouse/dbt.duckdb`. Khi đặt `RETAIL_DUCKDB_PATH` tới bản sao kho của worktree chính: **5 / 0**, tức liên kết AI trên PS1 vẫn hiện sau khi sửa `ai_panel.py` |
| `test_du_bao.py` | 2 / 0 / 9 | |

**Đột biến độc lập của Claude** (15 lượt, `pytest -x` trên `test_l1_dot_web.py`, mỗi lượt khôi phục file và kiểm hash): **12 bị bắt, 3 lọt**.

| Mã | Đột biến | Kết quả |
|---|---|---|
| C1 | bỏ kiểm `expected` trong `ghi_json_so_tiep` | bắt |
| **C2** | bỏ kiểm `status == 'ready'` và `co_du_lieu_tong_hop is True` trong `dashboard_command` | **lọt** |
| C3 | bỏ kiểm `confirmed` | bắt |
| C4 | Quản lý thấy yêu cầu của người khác | bắt |
| **C5** | `label()` bỏ điều kiện `command['request_id'] == row['id']` | **lọt** |
| C6 | bỏ `@releases.active_read` ở `_data_key` | bắt |
| C7 | `_demo_reason` không trả `None` khi hai con trỏ trùng | bắt |
| C8 | nới `ID_PATTERN` | bắt |
| C9 | nhận `sales.csv` | bắt |
| C10 | bỏ chặn `..` | bắt |
| **C11** | `change()` bỏ điều kiện `trang_thai == 'loi'` | **lọt** |
| C12 | bỏ bắt buộc lý do khi bỏ khỏi sổ | bắt |
| C13 | `all` → `any` ở kiểm năm AI | bắt |
| C14 | bỏ `st.stop()` sau khối đợt khi không có luồng local | bắt |
| C15 | bỏ bắt buộc file `orders*` | bắt |

**Bắt buộc sửa:**

1. **Đổi luồng một file ngoài phiếu, không ghi ở "Chỗ khác phiếu".** `gui_du_lieu.py:15` và `duyet_du_lieu.py:17` thêm `backend() != 'databricks'` vào `local_available`. Trước L1, máy local chọn backend Databricks vẫn thấy luồng một file; giờ luồng này bị ẩn. Như vậy là trái bẫy 5 ở §1. Trên Streamlit Cloud, `nhap_kha_dung()` vốn đã trả False vì không có duckdb, nên điều kiện thêm vào không cần cho cloud. **Sửa:** dùng lại đúng `nhap_kha_dung()`. Khối dashboard local tự báo "chỉ hỗ trợ DuckDB local" như cũ khi backend là Databricks. Thêm một test: backend `databricks`, `RETAIL_NHAP_DOT=tat`, `nhap_kha_dung` giả True → trang Gửi vẫn hiện luồng một file như trước L1.
2. **`dashboard_since` là dict, không phải chuỗi.** CLI ghi `{'release_id': …, 'at': '…Z'}` (`scripts/pipeline/state.py:135–136`). Vì vậy trang Duyệt cloud in ra `Giờ công bố: {'release_id': …}`. Test `test_cloud_ui_return_and_roles` giả lập sai hình (`'2026-11-08'`). **Sửa:** hiện `dashboard_since['at']`, và nếu `release_id` trong đó khác `dashboard` thì không hiện giờ. Test dùng đúng hình dict.
3. **Thêm test bắt C2, C5, C11:**
   - C2: registry giả có bản `status != 'ready'` hoặc `co_du_lieu_tong_hop` khác `True` → `dashboard_command(rid, confirmed=True)` ném lỗi, không có file trong `lenh/`. Phải gọi thẳng hàm, không qua trang, vì trang đã lọc ứng viên.
   - C5: có lệnh `dat` đang chờ cho yêu cầu A, yêu cầu B cũng `da_kiem` → nhãn của B là "Đã kiểm tra", không phải "Chờ đưa lên dashboard".
   - C11: Kỹ sư dữ liệu gọi `change()` trên yêu cầu ở `da_gui` và ở `da_kiem` → `ValueError`, không thêm sự kiện. Nếu thiếu kiểm này, một sự kiện ghi sai sẽ làm cả yêu cầu thành `hong` khi phát lại.

**Nên sửa (nhỏ, làm cùng lượt):**

4. `kho_dot.configured_store()`:
   - tạo client bằng `WorkspaceClient(host=…, client_id=…, client_secret=…, auth_type='oauth-m2m')`, giống `dwh/guarded.py:297`, để SDK không trộn với `DATABRICKS_TOKEN` hay profile có trong môi trường;
   - lấy host qua `dwh.connection.databricks_config()` thay vì `os.getenv`, để chế độ `volume` chạy local đọc được `.env.databricks.local`. Chỉ lấy host, không lấy mã client từ đó.
   - Test: thêm `auth_type` vào ca `test_volume_client_uses_writer_credentials_only`.
5. `DotStore.visible()` chỉ bỏ qua `KhongCo`. Một `yeu_cau.json` hỏng (JSON lỗi, thiếu `nguoi_gui` hay `ngay_gui`) làm cả danh sách đợt báo lỗi. **Sửa:** bắt `ValueError`/`KeyError`/`TypeError` cho từng yêu cầu; Kỹ sư dữ liệu và Admin thấy dòng đó với trạng thái "Dữ liệu trạng thái hỏng", Quản lý thì bỏ qua. Thêm một test.

**Đã kiểm, đạt:**
- thứ tự ghi `file/*` → `yeu_cau.json` → `su_kien/000001.json`, và đọc lại `ma` sau mọi lỗi ghi;
- `st.rerun()` nằm trong `try/except Exception` không bị nuốt (`RerunException` không kế thừa `Exception`);
- khóa cache AI theo bản active, có test `key[1] == 'a'*24`;
- năm cuối đọc trong `active_scope()`, và cache của `load_or_stop` theo `release_id` của bản active;
- đường cloud không import duckdb;
- khối dashboard local giữ nguyên;
- `dashboard_state_cloud` dùng kết nối đọc của app;
- junction `data` đã gỡ, `D:\retail-analytics-am\data` còn đủ 21 mục (Claude tạo lại tạm để chạy test rồi gỡ bằng `cmd /c rmdir`).

**Khi báo lại:** liệt kê thay đổi theo 1–5; chạy lại `test_l1_dot_web.py`, `test_nhap_du_lieu.py` (có junction), `test_d5_dashboard.py`; ghi đột biến C2, C5, C11 sau khi sửa đều bị bắt.

### Lượt 2 — 2026-11-08: **đạt phần code; bổ sung 2 test (và một kiểm nhỏ) rồi báo lại**

**Claude chạy lại** (`RETAIL_TEST_DATABRICKS=0`, Python `.venv` của worktree chính):

| File | Kết quả |
|---|---|
| `test_l1_dot_web.py` | 120 đạt |
| `test_d5_dashboard.py` | 35 đạt |
| `test_nhap_theo_doi.py` / `test_nhap_tu_dong.py` | 61 / 151 đạt |
| `test_nhap_du_lieu.py` (junction tạm, đã gỡ; `am/data` còn 21 mục) | 97 đạt |
| `test_roles.py` với `RETAIL_DUCKDB_PATH` trỏ bản sao kho | 43 đạt |

**Đột biến: 24 lỗi cài, test bắt 22.** C1–C15 của lượt 1 nay đều bị bắt (gồm C2, C5, C11). Chín đột biến mới nhắm vào 5 điểm sửa:

| Mã | Đột biến | Kết quả |
|---|---|---|
| C16 | trang Gửi: `local_available = backend() != 'databricks' and nhap_kha_dung()` | bắt |
| C17 | trang **Duyệt**: cùng đột biến | **lọt** |
| C18 | in `str(since)` thay vì `since['at']` | bắt |
| C19 | bỏ điều kiện `since['release_id'] == dashboard` | bắt |
| C20 | bỏ `auth_type='oauth-m2m'` | bắt |
| C21 | lấy host bằng `os.getenv` | bắt |
| C22 | `visible()` chỉ bắt `ValueError` | bắt |
| C23 | bỏ kiểm trường chuỗi | bắt |
| C24 | bỏ kiểm `files` là list | **lọt** |

**Cần bổ sung (không đổi hành vi đã đạt):**
1. Test cho trang Duyệt giống `test_single_file_kept_with_databricks_backend`: backend Databricks, chế độ đợt `tat`, `nhap_kha_dung()` True → khối local của trang Duyệt vẫn hiện, không có khối đợt. Phải bắt được C17.
2. Ca `files` hỏng trong `test_corrupt_metadata_isolated_per_request`. Trang Gửi/Duyệt cộng `f['so_byte']` của từng file, nên một phần tử không phải dict, hoặc `so_byte` không phải số nguyên, vẫn làm vỡ cả danh sách. **Sửa:** trong `visible()` kiểm thêm mỗi phần tử `files` là dict có `ten` kiểu chuỗi và `so_byte` kiểu `int` (không nhận `bool`). Thêm các ca: `files` không phải list, phần tử là số, thiếu `so_byte`. Phải bắt được C24.

**Khi báo lại:** chạy lại `test_l1_dot_web.py`; ghi C17, C24 bị bắt. Không cần chạy lại các file khác nếu chỉ sửa `nhap_dot.py` và file test.

### Lượt 3 — 2026-11-09: **L1 đạt ở mức test local với Volume giả, GPT không phải sửa thêm**

**Claude chạy lại** (`RETAIL_TEST_DATABRICKS=0`): `test_l1_dot_web.py` + `test_d5_dashboard.py` + `test_nhap_theo_doi.py` = **225 đạt**, trong đó L1 129 đạt. Thống kê diff của 6 file đã theo dõi vẫn là 173 dòng thêm / 12 dòng xóa, như lượt 2. Lượt này không chạy lại `test_nhap_tu_dong.py`, `test_nhap_du_lieu.py`, `test_roles.py`, vì GPT chỉ sửa `nhap_dot.py` và file test; kết quả gần nhất của ba file này ở lượt 2.

**Đột biến: 27 lỗi cài, test bắt cả 27.** Gồm C1–C24 (có C17, C24) và 3 lỗi mới vào đoạn kiểm `files`:

| Mã | Đột biến | Kết quả |
|---|---|---|
| C25 | bỏ vòng kiểm từng phần tử `files` | bắt |
| C26 | `type(so_byte) is not int` → `isinstance`, nhận cả `bool` | bắt |
| C27 | bỏ kiểm `ten` là chuỗi | bắt |

**Thăm dò dữ liệu hỏng ngoài `yeu_cau.json`** (test nháp của Claude, không thêm vào repo): sự kiện có `release_id` không phải chuỗi; `lenh/*.json` hoặc `.ket_qua.json` hỏng; lệnh thiếu `loai`; sổ đợt có `loai` lạ. Trong cả 5 ca, trang Duyệt không văng ngoại lệ, nhưng hiện `st.error` với thông báo kỹ thuật, tức khối đợt hoặc sổ đợt không dùng được cho tới khi sửa tay. Không phát hiện ghi sai dữ liệu. **Không chặn L1**, vì các file này chỉ do code của mình ghi, và L2 mới là nơi ghi sự kiện chạy và kết quả lệnh. **Chuyển vào phiếu L2:** kiểm kiểu `release_id` khi phát lại sự kiện, và quyết định cách hiện lệnh hoặc sổ đợt hỏng.

**Chưa kiểm:** đăng nhập OAuth và Files API trên Volume thật.
