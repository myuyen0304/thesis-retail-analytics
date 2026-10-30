# Giao việc: nhập dữ liệu mới từ giao diện web (gửi file → máy đề xuất → duyệt → chạy pipeline local → công bố)

Soạn ngày 2026-10-30. PM giao (chọn mức "đủ", 5 màn), Claude soạn phiếu. GPT code §1–§5; Claude rà độc lập trước khi commit theo
5 bước rà ở đầu [giao_viec_theo_so_do.md](giao_viec_theo_so_do.md). Chưa đạt thì Claude ghi phát hiện vào §9, GPT sửa tiếp.
Nghiệm thu thủ công §6 do PM chạy (app và pipeline chạy trên laptop, ngoài Claude Code vì RAM).

Đọc trước:
- `AGENTS.md`, `CLAUDE.md`, `docs/agent_workflows.md`; skill `retail-analytics-engineering`, `developing-with-streamlit`;
- [tien_hoa_schema.md](tien_hoa_schema.md) §5 (quy trình 7 bước), §6 (cách ly + ngưỡng), §7 (bộ của thầy), §9;
- [giao_viec_auto_mapping_lat1.md](giao_viec_auto_mapping_lat1.md) đến [lat4](giao_viec_auto_mapping_lat4.md): `auto_mapping`,
  hợp đồng mở rộng, `--extension`, cổng `validate_extension_visibility`;
- [phan_quyen.md](phan_quyen.md) §3.1 (ma trận trang), §4 (nguyên tắc), §5 (tài khoản Neon, nhật ký);
- [automation_batch.md](automation_batch.md) mục CLI (stage, root, `writer.lock`, `bo_qua`);
- notebook `notebooks/02_design/schema_evolution.ipynb` §5 (epd: sản phẩm cũ mang id mới).

## 0. Phiếu này nằm ở đâu

- Task auto mapping (lát 1–4, đã vào `main`) chứng minh hệ thống nhận được nguồn mới, nhưng mọi thao tác là lệnh trên máy DE.
  PM muốn demo cho giảng viên **từ phía stakeholder trên web**: chủ shop (role Quản lý) gửi file, hệ thống tự hiểu file, đội dữ liệu
  duyệt, pipeline chạy, công bố.
- Phạm vi vẫn là **data engineering** (PM chốt 2026-10-29): không làm trang phân tích theo nhân viên, không sửa trang PS, không
  sửa chat.
- **Chỉ chạy ở app local** (`streamlit run` trên laptop) và **kho DuckDB local**. Không chạy trên bản public Streamlit Cloud, không
  đụng Databricks, không qua Airflow (lý do ở §2).

## 1. Năm màn và giới hạn

| Màn | Ai (role) | Làm gì | Kết quả |
|---|---|---|---|
| 1. Gửi dữ liệu | Quản lý trở lên | Tải 1 file CSV/JSON, ghi mô tả | Yêu cầu mới, trạng thái `da_gui` |
| 2. Hệ thống hiểu file | (tự động, ngay sau màn 1) | Gọi `auto_mapping.propose` | Tóm tắt **bằng ngôn ngữ nghiệp vụ** cho người gửi; trạng thái `cho_duyet` |
| 3. Duyệt | DE, Admin (§10 câu 1) | Xem báo cáo kỹ thuật đầy đủ, chọn xử lý từng cột, đặt tên phần mở rộng, Duyệt hoặc Từ chối (bắt buộc ghi lý do) | Hợp đồng YAML đã duyệt, trạng thái `da_duyet`; hoặc `tu_choi` |
| 4. Chạy pipeline | DE, Admin | Bấm "Chạy": `prepare → forecast → build → validate` trên DuckDB local | `dang_chay` → `da_kiem` hoặc `loi` (kèm stage và thông báo) |
| 5. Công bố | Admin | Bấm "Công bố" | `da_cong_bo`; người gửi thấy bản dữ liệu mới |

**Giới hạn phải hiện rõ trên UI, không coi là lỗi:** dbt hiện chỉ có model cho phần mở rộng `orders_enriched`
(`stg_orders_enriched`, `dim_sales_employee`, nhánh trong `fact_order`). File được duyệt với tên khác thì dừng ở trạng thái
`cho_model_dbt` ("đã duyệt và land; cần DE viết model dbt trước khi chạy"), nút Chạy bị khóa. Đây là ranh giới thiết kế: lên star
schema là quyết định mô hình hóa của DE (`tien_hoa_schema.md` §5 bước 3–5), máy không tự sinh model.

Không làm: sửa model dbt; sinh model dbt tự động; chạy target `databricks`; trigger DAG Airflow; cho người gửi sửa file đã gửi
(gửi lại = yêu cầu mới); nhiều file trong một yêu cầu; trang phân tích theo nhân viên.

## 2. Môi trường và ràng buộc

- Worktree `D:/retail-analytics-nhap`, nhánh `nhap-ui/myuyen` tách từ `origin/main` `2e77094` (Claude tạo 2026-10-30, đã chép
  `data/`, có thêm `data/student_data/epd.json`). Python: `D:/retail-analytics/.venv/Scripts/python.exe`, chạy với thư mục làm
  việc là root worktree. **Không commit, không push** (Claude commit sau khi rà).
- **Không qua Airflow, không dựng image.** Lý do, để GPT không "sửa cho tiện":
  - DAG `retail_batch_pipeline` viết cứng `--root warehouse/pipeline/docker`, là registry của bản cloud;
  - DAG đang tạm dừng có chủ ý (lát 4 chờ P5/P6); bỏ tạm dừng thì lượt 08:00 build code mới lên Databricks và vượt quota 500 bảng;
  - container mount `./data` chỉ đọc, và hợp đồng mở rộng nằm cố định trong image;
  - image đóng băng tới sau P6 và tới khi có script dọn bản cũ.
- Vì vậy nút "Chạy" gọi CLI bằng **subprocess từ `.venv`**: `sys.executable -m scripts.pipeline.cli <stage> --target duckdb --root
  warehouse/pipeline/ui-nhap ...`. `--target duckdb` và root **viết cứng** trong code, không có tham số nào đổi được. Test phải khẳng
  định lệnh sinh ra không bao giờ chứa `databricks` hay `warehouse/pipeline/docker`.
- **Cờ bật tính năng:** biến môi trường `RETAIL_APP_NHAP_DU_LIEU=1`, mặc định tắt. Tắt thì hai trang mới không xuất hiện với bất kỳ
  role nào, kể cả khi code đã lên nhánh `app/myuyen`. Không bao giờ đặt biến này trong secrets của Streamlit Cloud (ghi vào §8).
- File tải lên là **dữ liệu không tin cậy**: chỉ nhận `.csv`, `.json`; tối đa 200 MB; tên file lưu được chuẩn hóa
  (`[a-z0-9_.-]`, bỏ đường dẫn); tính sha256 ngay khi lưu; không bao giờ thực thi hay import nội dung.
- Mọi thứ sinh ra nằm trong thư mục **đã gitignore**: file tải lên ở `data/ui_nhap/<id>/`, yêu cầu và hợp đồng ở
  `warehouse/ui_nhap/`, kho ở `warehouse/pipeline/ui-nhap/`. Không ghi vào `scripts/ingest/extensions/` (thư mục có trong git, và
  ghi vào đó làm đổi `code_version`).
- Tài khoản và nhật ký dùng Neon như hiện tại (`ui/roles.py`, `ui/auth_store.py`). Không tạo bảng mới trên Neon: dữ liệu yêu cầu
  lưu file local (CLAUDE.md §1: Neon chỉ để lưu tài khoản và nhật ký truy cập). Mọi thao tác gửi/duyệt/từ chối/chạy/công bố ghi một
  dòng qua `Store.log(username, event, detail)`.
- RAM: Streamlit cộng stage `forecast` (khoảng 4 phút) chạy cùng lúc trên laptop. GPT chạy test, không chạy lượt pipeline đầy đủ;
  lượt đầy đủ ở §6, PM chạy từ PowerShell.

## 3. Thiết kế

### 3.1 Yêu cầu (request) và trạng thái

Mỗi yêu cầu là một thư mục `warehouse/ui_nhap/yeu_cau/<id>/` (`id` = `YYYYMMDDTHHMMSSZ_<6 hex>`):
- `yeu_cau.json`: `id`, `nguoi_gui`, `ngay_gui`, `mo_ta`, `ten_file`, `sha256`, `so_byte`, `trang_thai`, `lich_su` (mỗi lần đổi
  trạng thái: lúc, ai, từ → tới, ghi chú);
- `de_xuat/`: đầu ra của `auto_mapping.write_proposal` (`mapping_de_xuat.yml`, `bao_cao_mapping.md`);
- `hop_dong/<ten>.yml`: hợp đồng đã duyệt (màn 3);
- `chay/`: `run_id`, log subprocess, `context.json` sao từ root khi xong.

Trạng thái và chuyển hợp lệ (ngoài bảng này là lỗi, test phải chặn):

```text
da_gui → cho_duyet            (đề xuất xong)        | da_gui → loi_de_xuat (đọc file lỗi; người gửi thấy lý do)
cho_duyet → da_duyet | cho_model_dbt | tu_choi        (màn 3)
da_duyet → dang_chay → da_kiem | loi                  (màn 4; loi cho phép chạy lại → dang_chay với run_id mới)
da_kiem → da_cong_bo                                  (màn 5)
da_cong_bo → dang_chay → da_cong_bo                   ("Chạy lại để kiểm": cùng hợp đồng, cùng code → prepare ra skipped)
```

Ghi file nguyên tử (ghi tạm rồi đổi tên), dùng lại `atomic_json` của `scripts/pipeline/state.py`. Hai phiên Streamlit cùng bấm thì một
bên thắng, bên kia nhận thông báo "trạng thái đã đổi"; không ghi đè.

### 3.2 Màn 2: tóm tắt nghiệp vụ

Hàm thuần `tom_tat_nghiep_vu(de_xuat) -> list[str]` (test được, không phụ thuộc Streamlit), ví dụ với `orders_enriched.csv`:
- "Hệ thống hiểu file là: Đơn hàng (bổ sung thông tin)": nhãn tiếng Việt cho 14 nguồn, lấy từ một bảng ánh xạ trong code;
- số dòng; "khớp với N đơn hàng đã có" khi khóa nối khớp;
- thực thể mới và thuộc tính (tên cột → nhãn đọc được, không có nhãn thì giữ tên cột);
- cột trùng thông tin đã có (cột thừa) sẽ bỏ;
- cảnh báo thông tin cá nhân: "sẽ không hiển thị trên báo cáo khi chưa được duyệt";
- cảnh báo xung đột khóa (§3.3) nếu có.

Người gửi (Quản lý) **chỉ thấy tóm tắt này**, không thấy điểm số, phụ thuộc hàm hay mẫu giá trị (§10 câu 2).

### 3.3 Kiểm xung đột khóa master data (việc mới trong `auto_mapping`)

Hiện phát hiện "sản phẩm cũ mang id mới" chỉ có trong notebook §5. Đưa vào `auto_mapping` thành mục báo cáo mới
"Xung đột khóa", chạy khi nguồn đề xuất có khóa chính đơn cột (`source_contract`) và file có khóa đó:
- `id_trung_nguon`: số bản ghi có id trùng với id đã có trong nguồn;
- `id_trung_khac_noi_dung`: trong đó, số bản ghi mà các thuộc tính chung khác bản ghi cùng id;
- `danh_lai_khoa`: số bản ghi mà toàn bộ thuộc tính chung (trừ khóa) khớp **đúng một** bản ghi của nguồn nhưng id khác.

So sánh trên giá trị chuỗi đã chuẩn hóa như notebook §5 (đọc lại cell để dùng đúng phép so). Kết quả với `epd.json` phải khớp
notebook: 995 bản ghi khớp đúng một sản phẩm, 0 bản ghi khớp mà cùng id, 998 bản ghi id trùng số với `products`, 998 bản ghi id
trùng mà khác sản phẩm. Lệch thì dừng và báo, không chỉnh test cho khớp. Với `orders_enriched.csv` mục này không được báo xung đột.

Máy **không tự từ chối**: chỉ báo. DE quyết ở màn 3. Trang duyệt hiện cảnh báo đỏ khi `danh_lai_khoa > 0` hoặc
`id_trung_khac_noi_dung > 0`.

### 3.4 Màn 3: từ đề xuất sang hợp đồng

Module mới `scripts/ingest/approval.py`, hàm thuần `hop_dong_tu_de_xuat(de_xuat, quyet_dinh, ten, file_rel, nguoi_duyet, ngay)
-> dict`:
- `quyet_dinh`: với mỗi cột, `xu_ly` ∈ {`khoa_noi`, `doi_chieu_loi`, `bo`, `nap`}; với cột `nap`: `kieu`, `duoc_rong`,
  `hien_thi` ∈ {`mart`, `silver`}; thực thể đã duyệt; `nguong_cach_ly` (mặc định 0,01).
- Mặc định trên form lấy từ đề xuất: cột khớp → `doi_chieu_loi`, khóa nối → `khoa_noi`, cột thừa → `bo`, cột thực thể mới → `nap`;
  **cột nghi PII mặc định `hien_thi: silver`**, DE phải chủ động đổi sang `mart`.
- Đầu ra phải qua được `extension_contract.load` (ghi YAML vào `hop_dong/`, gọi `load(ten, directory)`); không qua thì hiện lỗi của
  `load` trên form, không lưu.
- `file_rel` là đường dẫn tương đối trong `data/`: `ui_nhap/<id>/<ten_file>`.
- Tên phần mở rộng `ten`: mặc định theo tên file (chuẩn hóa về `[a-z][a-z0-9_]*`), DE sửa được, không được trùng 14 nguồn.
- Sau khi lưu: có model dbt cho `ten` (tìm `extension_enabled('<ten>')` trong `retail_dbt/models`) → `da_duyet`; không có →
  `cho_model_dbt`.
- Với demo `orders_enriched.csv`: duyệt theo mặc định rồi sửa đúng như `scripts/ingest/extensions/orders_enriched.yml` phải ra hợp
  đồng **tương đương** (cùng `cot`, `thuc_the`, `khoa_noi`, `nguong_cach_ly`; khác `file`, `duyet_boi`, `ngay_duyet`). Có test.

### 3.5 CLI: thư mục hợp đồng ngoài repo

Thêm `--extension-dir` cho `scripts/pipeline/cli.py` (chỉ hợp lệ cùng `--extension`, như `--extension` hiện tại):
- truyền vào `snapshot.prepare(..., extension_directory=...)`;
- **ghi vào `context.json`** (`extension_dir`) để stage sau dùng lại, vì `--extension` chỉ cho ở `prepare`/`run`;
- `validate_extension_visibility` đang gọi `extension_contract.load(name)` không có thư mục: phải đọc `context['extension_dir']`
  khi có. Rà mọi chỗ gọi `extension_contract.load(` và `snapshot.validate(` trong `scripts/pipeline`, không sót chỗ nào;
- không có `--extension-dir` thì hành vi **y như cũ** (test hồi quy lát 4 phải đạt nguyên).

Hash hợp đồng (gồm cả `file`, `duyet_boi`, `ngay_duyet`) và sha256 file đã nằm trong `snapshot_id` (`identity_suffix`), nên hai
yêu cầu khác nhau luôn ra hai snapshot khác nhau, kể cả cùng nội dung file. Chạy lại **chính yêu cầu đã công bố** (cùng hợp đồng,
cùng code với bản đang phục vụ của root `ui-nhap`) thì `prepare` ra `skipped` (`bo_qua`). Màn 4 hiển thị trường hợp này là
"Không có gì mới, bỏ qua" và giữ `da_cong_bo`, không phải lỗi.

### 3.6 Màn 4 và 5: chạy và công bố

Module `apps/retail_app/ui/nhap_runner.py` (hoặc tên tương đương):
- `lenh(stage, run_id, ten, extension_dir) -> list[str]`: hàm thuần sinh lệnh; nơi duy nhất viết `--target duckdb` và root
  `warehouse/pipeline/ui-nhap`;
- "Chạy": tạo `run_id` = `ui-<id>-<n>`; chạy nền một tiến trình con lần lượt `prepare` (kèm `--extension ten --extension-dir ...`)
  → `forecast` → `build` → `validate`, dừng ở stage lỗi đầu tiên; log ra `chay/<run_id>.log`; khi xong cập nhật trạng thái.
  Tiến trình con phải sống tiếp khi phiên Streamlit tải lại (không giữ handle trong `session_state` làm nguồn sự thật; trạng thái
  đọc từ file);
- tôn trọng `writer.lock` của root: đang có lượt khác thì nút Chạy khóa và ghi lý do;
- trang tự làm mới trạng thái mỗi 5 giây khi có yêu cầu `dang_chay` (`st.fragment(run_every=...)` hoặc tương đương), hiện stage
  hiện tại và thời gian đã chạy;
- `da_kiem`: hiện tóm tắt từ `context.json`: `release_id`, `snapshot_id`, `so_dong_cach_ly`, `quality` (`daily_rows`,
  `relations_checked`, `hidden_columns_checked`, `mart_columns_checked`), và với `orders_enriched` thêm số dòng
  `dim_sales_employee` và số đơn có `sales_employee_sk` (query chỉ đọc vào `dbt.duckdb` của lượt đó);
- "Công bố" (chỉ Admin): `cli publish --run-id <run_id> --target duckdb --root warehouse/pipeline/ui-nhap`. Chỉ đổi con trỏ
  của root `ui-nhap`; **không** ảnh hưởng kho app đang đọc (backend app không đổi trong phiếu này).

### 3.7 Trang và quyền

- Hai trang mới trong `ui/roles.py` `PAGES`: `gui_du_lieu` ("Gửi dữ liệu"), `duyet_du_lieu` ("Duyệt dữ liệu").
- `PAGES_BY_ROLE` (khi cờ bật): `gui_du_lieu` cho `quan_ly`, `phan_tich`, `ky_su`, `admin`; `duyet_du_lieu` cho `ky_su`, `admin`.
  Cờ tắt thì hai key này bị loại khỏi mọi role (thực hiện trong `allowed`/`PAGES_BY_ROLE`, có test).
- Trong trang Duyệt: Duyệt/Từ chối/Chạy cho `ky_su`, `admin`; Công bố chỉ `admin`. Quyền thao tác kiểm theo
  `roles.current_role()` (admin đang "Xem như role" thấp hơn thì mất nút, đúng ý), người thực hiện ghi theo username đăng nhập.
- Trang Gửi: Quản lý và DA/BI chỉ thấy yêu cầu của chính mình; DE/Admin thấy tất cả.
- Khách không thấy cả hai trang trong mọi trường hợp.

## 4. Yêu cầu theo file

| File | Việc |
|---|---|
| `scripts/ingest/auto_mapping.py` | Mục "Xung đột khóa" (§3.3) trong `propose` và báo cáo md; không đổi các mục cũ |
| `scripts/ingest/approval.py` (mới) | §3.4 |
| `scripts/pipeline/cli.py` | `--extension-dir` (§3.5) |
| `apps/retail_app/ui/nhap_store.py` (mới) | Yêu cầu, trạng thái, chuyển hợp lệ, ghi nguyên tử, lưu file tải lên (§2, §3.1) |
| `apps/retail_app/ui/nhap_runner.py` (mới) | §3.6 |
| `apps/retail_app/views/gui_du_lieu.py` (mới) | Màn 1–2 |
| `apps/retail_app/views/duyet_du_lieu.py` (mới) | Màn 3–5 |
| `apps/retail_app/ui/roles.py` | Hai trang, cờ, ma trận (§3.7) |
| test tương ứng | §5 |

Không sửa: `retail_dbt/`, `deploy/`, `docker-compose.airflow.yml`, `scripts/ingest/extensions/`, các trang PS, chat, `docs/`
(Claude cập nhật docs sau khi rà, hỏi PM trước).

## 5. Kiểm

Chạy được trong worktree, không cần Databricks:
- **auto_mapping:** xung đột khóa với `epd.json` ra đúng 4 số ở §3.3; `orders_enriched.csv` không có xung đột; test cũ của lát 1
  đạt nguyên.
- **approval:** mặc định từ đề xuất; PII mặc định `silver`; hợp đồng tương đương `orders_enriched.yml` (§3.4); quyết định sai
  (thiếu cột, `khoa_noi` lệch kiểu, tên trùng nguồn) bị `extension_contract.load` chặn với đúng thông báo.
- **cli:** `--extension-dir` đi tới `prepare` và `validate_extension_visibility` (dùng một hợp đồng trong thư mục tạm mà
  `scripts/ingest/extensions/` không có; không truyền thư mục thì phải lỗi "không tìm thấy"); không có cờ thì lát 4 không đổi.
- **store:** đủ chuyển hợp lệ ở §3.1, chuyển sai bị chặn; ghi nguyên tử; tên file độc hại (`../x.csv`, `a\b.json`, `.exe`) bị chặn
  hoặc chuẩn hóa; vượt 200 MB bị chặn.
- **runner:** lệnh sinh ra luôn có `--target duckdb` và root `ui-nhap`, không bao giờ chứa `databricks` hay `pipeline/docker`;
  dừng ở stage lỗi đầu tiên (giả lập CLI bằng script tạm); `writer.lock` đang giữ thì không chạy.
- **roles:** cờ tắt → hai trang không có ở role nào; cờ bật → đúng ma trận §3.7; khách không bao giờ thấy.
- **Thử vô hiệu (mutation):** với mỗi nhóm trên, sửa tạm một chỗ trong code (bỏ kiểm root, bỏ PII→silver, bỏ truyền
  `extension_dir` ở validate, bỏ cờ) và ghi test nào trượt. Công cụ thử để ở thư mục tạm, không đưa vào repo.
- Toàn bộ test hiện có của repo phải đạt như trước (ghi số đạt/trượt/skip; 2 test `test_kho_dat_sau_build` có thể trượt vì kho
  local chưa build lại, ghi rõ nếu gặp).

## 6. Nghiệm thu thủ công (PM chạy, sau khi §5 đạt và Claude rà xong)

Từ PowerShell, root worktree, cờ bật, app trỏ Neon như bản local hiện tại:

```powershell
cd D:\retail-analytics-nhap
$env:RETAIL_APP_NHAP_DU_LIEU = '1'
D:\retail-analytics\.venv\Scripts\python.exe -m streamlit run apps\retail_app\app.py
```

1. Admin tạo tài khoản `chushop` (Quản lý) và `de1` (Data engineer) nếu chưa có.
2. `chushop` gửi `data\student_data\orders_enriched.csv` → thấy tóm tắt nghiệp vụ, trạng thái chờ duyệt. Không thấy trang Duyệt.
3. `de1` mở Duyệt, sửa theo `orders_enriched.yml`, Duyệt → `da_duyet`. Bấm Chạy → theo dõi đủ 4 stage (khoảng 6 phút) →
   `da_kiem`: 0 dòng cách ly, `daily_rows` 3833, 3 cột ẩn, 3 cột mart, `dim_sales_employee` 200 dòng, 646.945 đơn có nhân viên.
4. `chushop` gửi `epd.json` → tóm tắt có cảnh báo xung đột khóa; `de1` Từ chối kèm lý do → `chushop` thấy lý do.
5. Admin Công bố yêu cầu ở bước 3 → `chushop` thấy "đã cập nhật".
6. Trên yêu cầu đã công bố ở bước 5, bấm "Chạy lại để kiểm" → "Không có gì mới, bỏ qua" trong vài giây.
7. Tắt cờ, chạy lại app → hai trang biến mất với mọi role.
8. Trang Phân quyền → nhật ký có các dòng gửi/duyệt/từ chối/chạy/công bố.

## 7. Báo cáo của GPT khi xong (PM dán cho Claude rà)

- Danh sách file tạo/sửa; với file đã có trong Git, tóm tắt từng chỗ đổi.
- Số đạt/trượt/skip của §5; kết quả thử vô hiệu (sửa gì, test nào trượt).
- Bốn số xung đột khóa với `epd.json`, và cách so sánh đã dùng (dẫn cell notebook).
- Diff của `cli.py` và danh sách mọi chỗ gọi `extension_contract.load(` / `snapshot.validate(` đã rà.
- Chỗ làm khác phiếu (nếu có) và vì sao; lỗi thấy ngoài phạm vi.

## 8. Không giao GPT

- §6 nghiệm thu: PM chạy, Claude đọc kết quả.
- Commit, push, PR: Claude làm sau khi rà, theo lệnh PM.
- Docs (`tien_hoa_schema.md`, `bao_cao_gvhd_tu_dong_hoa.md` kịch bản demo): Claude cập nhật sau nghiệm thu, hỏi PM trước khi commit.
- `docs/phan_quyen.md` thuộc phiên Claude phân quyền: dòng 31 ("BA duyệt đề xuất auto mapping qua PR trên repo, không qua app") và
  bảng §3.1 phải đổi theo §3.7. PM nhắn phiên đó sửa sau khi chốt §10.
- Thứ tự lên public (nếu có): merge vào `main` được, nhưng **không bật cờ trên Streamlit Cloud**. Code đổi `apps/retail_app`,
  `scripts/ingest`, `scripts/pipeline` nên đổi `code_version`: chịu chung quy tắc đóng băng image (dựng lại image đúng một lần,
  sau P6 và sau khi có script dọn bản cũ).

## 9. Rà của Claude (Claude ghi, GPT đọc để sửa)

| Lượt | Ngày | Kết quả | Phát hiện | GPT đã sửa |
|---|---|---|---|---|
| | | | | |

## 10. Câu hỏi PM chốt trước khi giao

**PM chốt 2026-10-30: cả 5 câu theo đề xuất.** Duyệt: DE và Admin (DA/BI chưa mở). Quản lý chỉ thấy tóm tắt nghiệp vụ, từ DA/BI
thấy thêm báo cáo kỹ thuật. Duyệt trên app song song với PR, chỉ áp cho root local `ui-nhap`. Chạy: DE và Admin; Công bố: Admin.
Giới hạn file 200 MB. Câu hỏi gốc giữ dưới đây để ghi lý do.

1. **Ai được duyệt?** Đề xuất: DE và Admin. BA thuộc role DA/BI; muốn BA duyệt trên app thì thêm `phan_tich` vào trang Duyệt
   (nhưng không cho Chạy).
2. **Người gửi thấy gì?** Đề xuất: Quản lý chỉ thấy tóm tắt nghiệp vụ (§3.2); DA/BI trở lên thấy thêm báo cáo kỹ thuật.
3. **Duyệt trên app thay hay song song với duyệt qua PR?** Đề xuất: song song. Duyệt trên app chỉ áp cho root local `ui-nhap`;
   hợp đồng dùng cho production (`scripts/ingest/extensions/`) vẫn qua PR như `phan_quyen.md` dòng 31.
4. **Ai được bấm Chạy?** Đề xuất: DE và Admin; Công bố chỉ Admin (cùng tinh thần `phan_quyen.md` §2: admin quyết rollback).
5. **Giới hạn dung lượng file:** đề xuất 200 MB (mặc định của Streamlit; `orders_enriched.csv` là 155 MB, kiểm 2026-10-30).

Câu lệnh tạo worktree (đã chạy 2026-10-30):

```bash
git worktree add -b nhap-ui/myuyen D:/retail-analytics-nhap origin/main   # 2e77094
cp -r D:/retail-analytics/data D:/retail-analytics-nhap/
cp D:/retail-analytics-schema/data/student_data/epd.json D:/retail-analytics-nhap/data/student_data/
```
