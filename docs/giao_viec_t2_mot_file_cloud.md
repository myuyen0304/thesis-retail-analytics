# Giao việc T2: nhận một file lạ cột trên cloud, máy đề xuất ghép cột, tự đưa lên dashboard

Soạn ngày 2026-11-11, Claude. GPT code. Claude rà độc lập trước khi commit; chưa đạt thì Claude ghi vào §11 để GPT sửa.

**Làm hai lượt, Claude rà xong lượt 1 mới giao lượt 2:**
- **Lượt 1 (T2a, backend):** §2, §3, §5, §6, §6.6; test §9 mục 1–3, 5–13, 15–16.
- **Lượt 2 (T2b, trang web):** §4; test §9 mục 4, 14.

**Vì sao.** Chức năng "nhận file khác cấu trúc, máy đề xuất ghép cột, khớp mẫu thì tự công bố, không khớp thì người duyệt" mới chạy ở local
(T1). PM chọn ngày 2026-11-11 đưa lên cloud trước buổi bảo vệ 12/12, theo `docs/thiet_ke_duong_tu_dong.md` **§8.12** (đọc kỹ; §8.12 thắng
§8.1–§8.10 khi lệch). Tóm tắt quyết định:

- **(b)**: bản dựng từ một file **không bao giờ thành `active`**. Nó chỉ lên con trỏ `dashboard`, giống bản có đợt. Lượt 08:00
  (`retail_batch_pipeline`) **không đổi**.
- **Tự đưa lên dashboard như local**: đường `tu_dong` kiểm đạt thì Airflow tự ghi lệnh `dat`, **chỉ khi dashboard đang trống** và không có lệnh
  đang chờ. Đường `can_nguoi` (DE duyệt) kiểm đạt thì chờ Admin bấm.
- Dùng lại hạ tầng luồng đợt: Volume, sự kiện `overwrite=false`, `nhap_du_lieu_do`, `retail_dot_pipeline`, lệnh `dat`/`tra`, dò 30 giây (B1).

Đọc trước: `AGENTS.md`, `CLAUDE.md`, `docs/thiet_ke_duong_tu_dong.md` §2, §3, §8.12, `docs/thiet_ke_dot_web_public.md` §3, §8, và code T1:
`apps/retail_app/ui/nhap_store.py:297–410` (`_process_submission`, `auto_approve`, `approve`), `views/duyet_du_lieu.py:135–343`.

## 1. Môi trường và ràng buộc

- Worktree `D:\retail-analytics-nap`, nhánh `nap-ky/myuyen` (từ `108219d` = main `213e8fb` + script cửa sổ + `don_kho_dot.py`, có thêm commit
  phiếu này và §8.12). Mốc 1 (đợt 2023) đã đạt và dọn xong 2026-11-11. App tạm Streamlit Cloud chạy theo nhánh này, nên chỉ PM push,
  sau khi Claude rà đạt.
- Python: `D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8`, `RETAIL_TEST_DATABRICKS=0`. Nối tạm `data/` như các phiếu trước nếu test cần CSV.
- Không commit, không push. Không kết nối Databricks, không chạy Docker. Không đọc `.env.*.local`, `.streamlit/secrets.toml`, `~/.retail-secrets/*`.
- Máy thiếu RAM: chạy từng file test một lệnh; `apps` và `scripts` hai lệnh pytest riêng.
- **Không sửa:** `retail_dbt/`, `scripts/forecast/`, `deploy/airflow/dags/retail_batch_pipeline.py`, `scripts/ingest/auto_mapping.py`,
  `scripts/ingest/tu_dong.py`, `scripts/ops/don_ban_cu.py`, `docs/`. Luồng đợt và luồng local T1 phải giữ nguyên hành vi (test cũ phải qua).
- Trang web **không được import** `auto_mapping`, `duckdb`, `scripts.pipeline.cli` (Streamlit Cloud không có duckdb). Đề xuất chỉ chạy trong Airflow.
- `apps/retail_app/requirements.txt` **chưa có `pyyaml`**, mà form duyệt cloud cần `yaml`, `scripts.ingest.approval`, `extension_contract`.
  Thêm `pyyaml==6.0.3` (bản trong `.venv`, có comment ngày). Kiểm mọi module trang cloud import chỉ dùng thư viện có trong file này.

## 2. Yêu cầu một file: mã và trạng thái

Thêm vào `apps/retail_app/ui/trang_thai_dot.py` (vẫn thuần Python):

- Mã `…Z_<6 hex>_mot`. `ID_PATTERN` nhận cả `_dot` và `_mot`; thêm hàm `loai_cua(request_id)` trả `'dot'`/`'mot_file'`. `request_path` giữ cách kiểm.
- `TRANSITIONS_MOT` (`phat_lai` chọn bảng theo `loai` của yêu cầu; thêm tham số, mặc định `dot` để code cũ không đổi):

| Từ | Tới | Ai ghi |
|---|---|---|
| `da_gui` | `dang_doc`, `loi_file` | Airflow |
| `dang_doc` | `cho_duyet`, `da_duyet`, `loi_de_xuat` | Airflow (`da_duyet` = đường `tu_dong`) |
| `cho_duyet` | `da_duyet`, `cho_model_dbt`, `tu_choi` | DE/Admin trên web |
| `da_duyet` | `cho_chay`, `het_cho`, `khong_moi` | Airflow (kiểm quota, kiểm trùng §5.4) |
| `het_cho` | `cho_chay` | Airflow |
| `cho_chay` | `dang_chay` | Airflow |
| `dang_chay` | `da_kiem`, `loi` | Airflow |
| `loi` | `cho_chay`, `huy` | DE/Admin |
| `da_kiem` | `tren_dashboard` | Airflow khi xử lý lệnh `dat` |
| `tren_dashboard` | `da_tra` | Airflow |
| `da_tra` | `tren_dashboard` | Airflow |
| `loi_file`, `loi_de_xuat`, `cho_model_dbt`, `tu_choi`, `huy`, `khong_moi` | (hết) | |

- Nhãn nghiệp vụ trong `ui/nhap_dot.py` (cạnh `LABELS_DOT`): `dang_doc` "Đang đọc file", `cho_duyet` "Chờ duyệt", `da_duyet` "Đã duyệt",
  `loi_de_xuat` "Không đọc được file", `cho_model_dbt` "Chờ đội dữ liệu bổ sung mô hình", `tu_choi` "Từ chối", `khong_moi` "Không có gì mới";
  các trạng thái chung dùng nhãn của đợt.
- Sự kiện mang thêm trường chuỗi được phát lại vào trạng thái: `duong` (`tu_dong`/`tay`), `ten_mo_rong`, `hop_dong_sha256`, như `release_id` hiện nay.
  `ly_do` là danh sách `{ma, nghiep_vu, ky_thuat}` từ `phan_loai`; kiểm kiểu, sai kiểu thì `hong`.

## 3. Bố cục Volume (thêm vào `kho`)

```
yeu_cau/<id>_mot/yeu_cau.json            {id, loai:'mot_file', nguoi_gui, vai_tro, mo_ta, ngay_gui, file:{ten, so_byte, sha256}}
yeu_cau/<id>_mot/file/<ten_file>
yeu_cau/<id>_mot/su_kien/<000001>.json
yeu_cau/<id>_mot/de_xuat/mapping_de_xuat.yml, bao_cao_mapping.md      (Airflow ghi)
yeu_cau/<id>_mot/hop_dong/<ten>.yml                                  (hợp đồng của lượt; Airflow ghi ở tu_dong, web ghi khi DE duyệt)
hop_dong_da_duyet/<ten>/v<N>.yml                                     (chỉ thêm, overwrite=false)
hop_dong_da_duyet/<ten>/tu_choi/<000001>.json                        (từ chối nâng, chỉ thêm)
```

- **Hợp đồng hiện hành** của `<ten>` = file `v<N>.yml` có `N` lớn nhất trên Volume và qua `extension_contract.load`; không có thư mục thì lấy
  `scripts/ingest/extensions/<ten>.yml` của repo làm v1 (không ghi lên Volume). Không dùng `hien_hanh.json` (cần ghi đè). Hai người nâng cùng
  lúc: người sau ghi `v<N>` bị `DaCo`, báo tải lại.
- Viết lớp `KhoHopDong(kho)` mới trong `apps/retail_app/ui/kho_hop_dong.py`, cùng giao diện cần dùng của `ContractRegistry`
  (`current`, `ung_vien`, `write(expected=…)`, `rejected`, `reject`). Không import `scripts.pipeline.state` (cần `writer_lock` đĩa) — lớp này
  không dùng khóa đĩa. `ContractRegistry` local giữ nguyên.

## 4. Trang web

**4.1 Trang Gửi** (`views/gui_du_lieu.py`, chế độ `volume`): thêm lựa chọn "Một file dữ liệu mới" bên cạnh "Một đợt nhiều file".
Một file CSV/JSON ≤ 200 MB, tên an toàn như đợt; ghi `yeu_cau.json`, file, sự kiện `da_gui` qua `DotStore` (mở rộng `gui_dot` hoặc thêm
`gui_mot_file`). Danh sách "Yêu cầu đã gửi" hiện cả hai loại, nhãn §2. Quyền như đợt (Quản lý/DE/Admin). Dò 30 giây (B1) phải tính cả trạng thái
chờ của yêu cầu một file (`can_theo_doi`: `da_gui`, `dang_doc`, `da_duyet`, `het_cho`, `cho_chay`, `dang_chay`).

**4.2 Trang Duyệt** (`views/duyet_du_lieu.py`, chế độ `volume`), khối mới "Yêu cầu một file", DE/Admin:
- Hiện trạng thái, đường xử lý, hợp đồng, `ly_do[].ky_thuat`, báo cáo `bao_cao_mapping.md` và đề xuất (đọc từ Volume).
- `cho_duyet`: **dùng chung form duyệt với local**. Tách phần vẽ form ở `duyet_du_lieu.py:176–217` thành hàm trong `ui/form_duyet.py`
  trả `(name, decisions)` hoặc `None`; local và cloud cùng gọi. Duyệt: dựng hợp đồng bằng `approval.hop_dong_tu_de_xuat(proposal, decisions, name,
  f"ui_nhap_cloud/{id}/{ten_file}", username, utc())`, kiểm bằng `extension_contract.load` trong thư mục tạm, ghi `hop_dong/<name>.yml`
  (`ghi_moi`), rồi sự kiện `da_duyet` (có `ten_mo_rong`, `hop_dong_sha256`, `duong:'tay'`) hoặc `cho_model_dbt` nếu
  `approval.has_dbt_model` sai. Tên chưa có hợp đồng nào thì ghi `hop_dong_da_duyet/<name>/v1.yml` như `approve` local (`nhap_store.py:404–406`).
- Từ chối: bắt buộc lý do → `tu_choi`.
- `loi`: "Chạy lại" → `cho_chay`, "Hủy" → `huy` (như đợt).
- **Nâng hợp đồng:** yêu cầu đường `tu_dong` có `cot_moi` khác rỗng → form nâng như local (`duyet_du_lieu.py:292–343`), ghi `v<N+1>.yml` với
  `expected=N`; từ chối nâng ghi `tu_choi/`. **Không nạp bù tự động**: sau khi nâng, hiện "Cột mới có hiệu lực từ lần gửi sau; gửi lại file để
  dựng bản có cột mới". (Khác local có chủ đích; §8.12.)
- Ghi nhật ký Neon như luồng đợt (`audit.log`).

**4.3 Khối "Bản dữ liệu trên dashboard"** (Admin, `duyet_du_lieu.py:72–105`): danh sách ứng viên gồm bản `co_du_lieu_tong_hop is True`
**hoặc** `chi_dashboard is True`. Nhãn rõ loại: "Bản có đợt (dữ liệu tổng hợp)" / "Bản có nguồn mới `<tên>`". Ô xác nhận "dữ liệu tổng hợp" chỉ
bắt buộc với bản có đợt. Lệnh `dat` mang thêm `request_id` khi chọn bản một file.

**4.4 Băng rôn:** `ui/common.py:47` giữ băng rôn "dữ liệu tổng hợp" chỉ cho bản có đợt. Bản `chi_dashboard` hiện một dòng nhỏ
"Đang xem bản có nguồn mới `<tên>`, chưa phải bản chính" (lấy từ bản ghi registry, §6.1).

## 5. Airflow: `scripts/ops/nhap_do.py`

`_requests` nhận cả `loai == 'mot_file'` (kiểm `yeu_cau.json` theo §3). Logic đợt giữ nguyên; thêm nhánh cho một file.

**5.1 `quet`, `da_gui`:** tải file về `data/ui_nhap_cloud/<id>/<ten_file>` (gốc repo trong container, xem §6.4), kiểm `so_byte` + `sha256`
như `_download`; sai → `loi_file`. Đúng → `dang_doc`.

**5.2 `quet`, `dang_doc`:** chạy giống `_process_submission` local (`nhap_store.py:307–344`), nhưng hợp đồng đọc từ `KhoHopDong`:
`auto_mapping.propose(file, Path('data'))` → ghi `de_xuat/` lên Volume → `ung_vien` → `approval.has_dbt_model` → `tu_dong.phan_loai`.
- Lỗi đọc file → `loi_de_xuat` (chỉ ghi tên lỗi, không ghi nội dung file).
- `can_nguoi` → `cho_duyet` kèm `ly_do`, `duong:'tay'`.
- `tu_dong` → dựng `hop_dong_cua_luot(approved, header, f"ui_nhap_cloud/{id}/{ten_file}", phien_ban, utc())`, kiểm `load`, ghi `hop_dong/<ten>.yml`,
  rồi `da_duyet` với `duong:'tu_dong'`, `ten_mo_rong`, `hop_dong_sha256`, `cot_moi`. Lỗi hợp đồng → `cho_duyet` lý do `hop_dong_khong_hop_le`.

**5.3 `quet`, `da_duyet`/`het_cho`:** web giữ khóa ghi, nên **Airflow không tin hợp đồng web ghi** mà tự kiểm lại trước khi chạy:
- `hop_dong/<ten>.yml` qua `extension_contract.load`; `sha256` khớp sự kiện `da_duyet`;
- `doc['ten'] == ten_mo_rong` của sự kiện, và **`doc['file'] == f"ui_nhap_cloud/{id}/{ten_file}"`** đúng file của yêu cầu này
  (chặn hợp đồng trỏ sang `sales.csv` hay file khác dưới `data/`);
- `approval.has_dbt_model(ten)` do Airflow tự gọi;
- hợp đồng hiện hành của `<ten>` (nếu có) đọc được: `v<N>` lớn nhất hỏng thì **không lùi về bản cũ**, coi như lỗi.
Sai bất kỳ điều nào → `loi` kèm `thong_bao` nghiệp vụ, không trigger. Đúng → kiểm trùng §5.4, rồi `_quota` → `cho_chay` hoặc `het_cho`.
Đường `tay` cũng tự vào hàng sau khi DE duyệt (không có nút "Chạy" như local; báo cáo UC14 sẽ sửa theo).

**5.4 Không có gì mới:** nếu `csv_sha256` và `hop_dong_sha256` của phần mở rộng đó trùng đúng bản đang trên dashboard hoặc một bản một file
`da_kiem`/`tren_dashboard`/`da_tra` khác → `khong_moi`, không trigger (§8.10 mục 3). So bằng manifest snapshot của bản đó
(`sources[<ten>]`), không so tên file.

**5.5 `ket_thuc`, `cho_chay` → trigger** (một lượt mỗi lần, chung hàng với đợt, `max_active_runs=1`):
- Thư mục phần mở rộng của lượt: `warehouse/pipeline/docker/nhap/<id>/hop_dong/` gồm hợp đồng của lượt **và** hợp đồng repo của mọi phần mở
  rộng khác đang có trong manifest của `active` (cùng cách `_extensions_for_run` local, `nhap_runner.py:283`). Trùng tên thì hợp đồng của lượt thắng.
  Bản một file **không gồm đợt nào** trong sổ đợt.
- `conf = {request_id, target:'databricks', dots:[], extension_dir:<thư mục trên>, extensions:<danh sách>, du_bao_tu:<active>,
  pipeline_run_id:f"mot_{id}_{lan}", chi_dashboard:True}`.

**5.6 `ket_thuc`, lượt xong:** `success` và `context` có `stage == 'validated'`, `chi_dashboard is True`, `release_id` → `da_kiem`. Còn lại như đợt.
Ngay sau `da_kiem`, nếu `duong == 'tu_dong'`: đọc registry; **chỉ khi** `dashboard` trống **và** lệnh **mới nhất** trong `lenh/` (nếu có) đã có
`.ket_qua.json` (cùng cách `_process_command` chỉ xét lệnh mới nhất; lệnh cũ hơn không có kết quả thì bỏ qua), thì ghi lệnh `{loai:'dat', request_id, release_id, ai:'airflow'}` bằng `ghi_json_so_tiep`. Ngược lại, giữ `da_kiem` và ghi
`yeu_cau/<id>/thong_bao.json` bằng `ghi_moi` (đã có thì bỏ qua): "Dashboard đang có bản khác; chờ Admin đưa lên." Trang Duyệt hiện dòng này.
Đọc registry lỗi thì không ghi lệnh (an toàn: chờ Admin).

**5.7 `_process_command`:** nhận `dat` cho yêu cầu một file: kiểm `row['release_id'] == rid`, trạng thái `da_kiem`/`da_tra`/`tren_dashboard`;
**không** đụng sổ đợt; chuyển mọi yêu cầu (đợt hoặc một file) khác đang `tren_dashboard` sang `da_tra`. Gọi `dat-dashboard` với cờ mới §6.2.
`tra` chuyển cả hai loại. Luồng đợt hiện tại giữ nguyên.

## 6. Pipeline và DAG

**6.1 Cờ `--chi-dashboard`** (`scripts/pipeline/cli.py`): chỉ ở `prepare`/`run`, cần `--extension-dir`, cấm dùng cùng `--dot`. Ghi
`context['chi_dashboard'] = True` và `context['nguon_moi'] = <danh sách tên phần mở rộng có trong extension_dir mà khác repo>`. `validate` chép hai
khóa này vào bản ghi registry. `Registry.publish` (`state.py:104`) từ chối bản `chi_dashboard`, như bản tổng hợp. `publish` của CLI từ chối luôn.

**6.2 Con trỏ dashboard:** `Registry.publish_dashboard` (`state.py:128`), CLI `dat-dashboard` (`cli.py:627`), `ui/nhap_dot.py:192`,
`ui/nhap_runner.py:810` nhận bản `ready` có `co_du_lieu_tong_hop is True` **hoặc** `chi_dashboard is True`. `--xac-nhan-tong-hop` vẫn bắt buộc
với bản có đợt; với bản `chi_dashboard` dùng cờ mới `--xac-nhan-nguon-moi` (nhap_do truyền khi lệnh của yêu cầu một file). Sai cờ → lỗi exit 2.
`verify_consumers` (`cli.py:248`) giữ nhánh mặc định (cấp cả APP và AI) cho bản `chi_dashboard`.

**6.3 Dự báo:** bản `chi_dashboard` không train lại. Thêm `du_bao_dot.dung_lai_cung_sales(context, root, release_id, registry=…)`: chỉ chép dự
báo khi `sales.parquet` của snapshot lượt này **trùng từng dòng** với snapshot bản nguồn (`Date, Revenue, COGS`, so `except all` hai chiều như
`_kiem_khop`), ghi `nguon_du_bao`. Khác → `ValueError('sales khác bản nguồn; không dùng lại dự báo')`. CLI `forecast`: `--du-bao-tu` cho phép
với snapshot không đợt **chỉ khi** `context['chi_dashboard']`. `build` không gọi `bien_dot` cho bản không đợt (như hiện nay).

**6.4 `deploy/airflow/dags/retail_dot_pipeline.py`:** thêm param `extension_dir` (null hoặc đường dẫn khớp
`/opt/retail/warehouse/pipeline/docker/nhap/<id>_mot/hop_dong`), `chi_dashboard` (boolean). `dots` được rỗng **chỉ khi** `chi_dashboard`
và có `extension_dir`. `request_id` nhận `_dot` hoặc `_mot`. `prepare` truyền `--extension-dir` và `--chi-dashboard`. Vẫn không có stage publish.

**6.5 `docker-compose.airflow.yml`:** thêm mount ghi `./data/ui_nhap_cloud:/opt/retail/data/ui_nhap_cloud` cho các service Airflow, giữ `./data` chỉ đọc.
`.gitignore` đã bỏ `data/`; kiểm lại.

**6.6 Dọn sau nghiệm thu** (`scripts/ops/don_kho_dot.py`): hợp đồng đã duyệt nằm lại trên Volume sau mỗi lượt thử; một `orders_enriched` v2 thử
nghiệm có `bonus` sẽ đổi cách phân loại mọi file gửi sau. Thêm cờ `--ca-hop-dong` (mặc định tắt) để liệt kê/xóa thêm `hop_dong_da_duyet/`.
Giữ mặc định chỉ liệt kê, `--thuc-hien` mới xóa. Docstring ghi thêm hai chỗ PM dọn tay trên máy: `data/ui_nhap_cloud/` và
`warehouse/pipeline/docker/nhap/*_mot/`.

## 7. Không đổi (Claude sẽ kiểm)

- `active`, lượt 08:00, `retail_batch_pipeline`, biến `RETAIL_PIPELINE_DEFAULT_EXTENSIONS`.
- Luồng đợt: mọi test `test_nhap_do.py`, `test_l1_dot_web.py`, `test_l5_theo_doi_dot.py`, `test_d5_*`, `test_l2_dot_cloud.py` qua không sửa kỳ vọng.
- Luồng local T1: test `test_nhap_du_lieu*.py` qua.
- Dữ liệu cá nhân: đề xuất và báo cáo không chứa giá trị ô; log chỉ ghi tên lỗi.

## 8. File được sửa

`apps/retail_app/ui/trang_thai_dot.py`, `ui/nhap_dot.py`, `ui/kho_hop_dong.py` (mới), `ui/form_duyet.py` (mới), `ui/common.py`, `ui/nhap_runner.py`
(chỉ dòng 810), `views/gui_du_lieu.py`, `views/duyet_du_lieu.py`, `scripts/ops/nhap_do.py`, `scripts/pipeline/cli.py`, `scripts/pipeline/state.py`,
`scripts/pipeline/du_bao_dot.py`, `deploy/airflow/dags/retail_dot_pipeline.py`, `docker-compose.airflow.yml`, `scripts/ops/don_kho_dot.py`,
`apps/retail_app/requirements.txt`, và test. File khác cần sửa thì hỏi trước.

## 9. Test phải có (file mới `scripts/ops/tests/test_t2_mot_file.py`, `apps/retail_app/tests/test_t2_mot_file_web.py`, `scripts/pipeline/tests/test_t2_chi_dashboard.py`)

1. `phat_lai` với `TRANSITIONS_MOT`: chuỗi hợp lệ cho cả hai đường; bước sai → `hong`; yêu cầu đợt cũ không đổi.
2. `quet` đường `tu_dong` (Volume giả, file `orders_enriched` cắt nhỏ): `da_gui → dang_doc → da_duyet → cho_chay`, có `de_xuat/`, `hop_dong/` đúng
   `file: ui_nhap_cloud/<id>/…`, `duyet_boi` "he_thong (…)".
3. `quet` đường `can_nguoi`: file thiếu cột → `cho_duyet` lý do `thieu_cot`; tên cột lạ → `chua_ro_nguon`/`chua_co_hop_dong`. Không trigger.
4. Duyệt trên web (store giả): ghi `hop_dong/`, sự kiện `da_duyet`; hợp đồng sai → lỗi, không ghi gì; `cho_model_dbt` khi không có model.
5. Hợp đồng bị đổi trên Volume sau duyệt (sha256 lệch) → không trigger.
6. `KhoHopDong`: repo làm v1; `v2` trên Volume thắng; nâng đồng thời → người sau `DaCo`; từ chối nâng ghi `tu_choi/`.
7. `khong_moi` khi gửi lại đúng file đã có bản.
8. `ket_thuc`: conf đúng §5.5 (gộp hợp đồng repo của `active`, `dots == []`, `chi_dashboard`); `da_kiem` chỉ khi `chi_dashboard` trong context.
9. Tự đưa lên dashboard: dashboard trống → có lệnh `dat` `ai:'airflow'`; dashboard có bản → không lệnh, có `thong_bao.json`; có lệnh đang chờ →
   không lệnh; đường `tay` → không lệnh.
10. `_process_command` với yêu cầu một file: không ghi sổ đợt; yêu cầu đợt đang `tren_dashboard` chuyển `da_tra`; `tra` chuyển cả hai.
11. CLI: `--chi-dashboard` không có `--extension-dir` → lỗi; cùng `--dot` → lỗi; `publish` bản `chi_dashboard` → lỗi; `dat-dashboard` bản
    `chi_dashboard` thiếu `--xac-nhan-nguon-moi` → exit 2; đủ cờ → con trỏ đổi, `active` không đổi.
12. `dung_lai_cung_sales`: trùng → chép, có `nguon_du_bao`; lệch một dòng → `ValueError`.
13. DAG `command()`: `dots` rỗng chỉ khi `chi_dashboard` + `extension_dir`; đường dẫn sai → lỗi; `prepare` có `--extension-dir`, `--chi-dashboard`.
14. Trang web không import `duckdb`/`auto_mapping` khi chế độ `volume` (kiểm `sys.modules` sau khi import view, như test L1); mọi module
    ngoài thư viện chuẩn mà view cloud nạp phải có tên trong `apps/retail_app/requirements.txt` (so tên gói, có bảng tên module→gói cho `yaml`→`pyyaml`).
15. Airflow chặn hợp đồng web ghi sai (§5.3): `file` trỏ `sales.csv`, `ten` khác sự kiện, không có model dbt, `v<N>` mới nhất hỏng → `loi`, không trigger.
16. `don_kho_dot.py --ca-hop-dong`: liệt kê có `hop_dong_da_duyet/`; không cờ thì không đụng; vẫn chặn gốc ngoài `kho`.

## 10. Kiểm và báo cáo

Chạy riêng từng file test mới và các test ở §7. Báo cáo cho Claude: danh sách file đổi, số test qua/trượt từng file (dán dòng tóm tắt pytest),
chỗ lệch phiếu và lý do, câu hỏi còn mở. Không tự sửa phiếu.

## 11. Rà của Claude (Claude ghi, GPT đọc để sửa)

### Lượt 1 (T2a backend), 2026-11-11: ĐẠT

**Quyết định trong lượt (PM/Claude chốt, đè lên phiếu ở trên):**
- **Cờ CLI web (phương án 1):** `nhap_runner.dashboard_action` chọn cờ theo bản ghi: `chi_dashboard` → `--xac-nhan-nguon-moi`,
  `co_du_lieu_tong_hop` → `--xac-nhan-tong-hop`; có cả hai hoặc không có cờ nào → `ValueError`, không gọi CLI.
- **Chữ ký nghiệp vụ (đè §5.4):** `hop_dong_sha256` đổi mỗi lượt (`file` chứa id, `ngay_duyet`), nên không dùng để chống trùng.
  `kho_hop_dong.chu_ky_nghiep_vu(doc)` = sha256 JSON (`sort_keys`, `ensure_ascii=False`) của hợp đồng bỏ `file`, `ngay_duyet`, `duyet_boi`,
  `hop_dong_sha256`; giữ `phien_ban`. Ghi vào sự kiện `da_duyet`, phát lại như `hop_dong_sha256`. `_mot_duplicate` so chữ ký của sự kiện yêu
  cầu kia và `csv_sha256` trong manifest bản của nó; **không đọc hợp đồng cũ trên đĩa**. Thiếu chữ ký, hoặc manifest lỗi ở bản không phải
  dashboard → coi là không trùng (chạy). Con trỏ dashboard hỏng → `loi`. Đường `tay` (lượt 2) phải ghi chữ ký bằng cùng hàm.
- **Đính chính §5.6:** `_process_command` không chỉ xét lệnh mới nhất mà lấy lệnh **mới nhất chưa có kết quả**, nên lệnh cũ còn treo vẫn được
  xử lý ở lượt sau. Giữ nguyên bộ xử lý; `_auto_dashboard` chỉ tự ghi `dat` khi **mọi** lệnh trong `lenh/` đã có `.ket_qua.json` hợp lệ
  (`dat`/`loi`). Nếu chỉ xét lệnh cuối, một lệnh cũ còn treo có thể ghi đè dashboard sau khi Airflow tự đưa lên.
- **Lệch phiếu chấp nhận:** `TRANSITIONS_MOT` thêm `da_duyet → loi`, `het_cho → loi/khong_moi` (cần cho kiểm lại hợp đồng §5.3).

**Claude tự chạy** (`RETAIL_TEST_DATABRICKS=0`, từng file, nối tạm `data/` rồi gỡ):
- Mới: `test_t2_mot_file_web.py` 31, `test_t2_chi_dashboard.py` 28, `test_t2_mot_file.py` 55.
- Cũ (§7): `test_nhap_do` 46, `test_l1_dot_web` 140, `test_l5_theo_doi_dot` 67, `test_d5_dashboard` 35, `test_d5_con_tro` 39,
  `test_l2_dot_cloud` 11, `test_nhap_du_lieu` 97, `test_don_ban_cu` 63, `test_d3_du_bao` 41, `test_airflow_extensions` 12,
  `test_extensions_cli` 7, `test_nhap_extension_dir` 9, `test_state_io` 9. Không trượt.
- Web (`ui.kho_hop_dong`, `ui.nhap_dot`, `ui.trang_thai_dot`) không nạp `duckdb`, `auto_mapping`, `scripts.pipeline.cli`.
- `data/ui_nhap_cloud/`, `warehouse/pipeline/docker/nhap/` nằm trong `.gitignore`.

**Đột biến: 28/30 bị bắt.** Bị bắt: tự ghi khi dashboard có bản; chỉ xét lệnh cuối; bỏ kiểm `file`/sha/model dbt/`v<N>` của hợp đồng;
không bao giờ trùng; bỏ so chữ ký; chữ ký gồm `file`; manifest lỗi thành `loi`; sai cờ CLI (nhap_do, web, `dat-dashboard`); bản một file
ghi sổ đợt; `da_kiem` không cần `chi_dashboard`; tự ghi cả đường `tay`; `dots` khác rỗng; hợp đồng repo thắng hợp đồng lượt;
`publish` (Registry, CLI) nhận `chi_dashboard`; `dung_lai_cung_sales` không so sales; DAG bỏ khớp `request_id`/cho `dots` rỗng;
`nguon_moi` rỗng; web nhận bản hai loại; `phat_lai` bỏ kiểm `duong`; `KhoHopDong` lùi về repo khi `v<N>` hỏng; web nhận nhiều yêu cầu.
Lọt:
- Bỏ `doc['ten'] != name` ở `_mot_contract`: **tương đương**, vì `load_raw` đã bắt `doc['ten'] == name` (`extension_contract.py:33`).
- Bỏ `record.get('chi_dashboard') is not True` ở `_auto_dashboard`: **thiếu test** (không chặn; `ket_thuc` đã đòi `chi_dashboard`
  trong context và `dat-dashboard` cũng chặn). Thêm ở lượt 2.

**Việc gộp vào lượt 2 (không chặn lượt 1):**
1. Test: bản ghi registry không có `chi_dashboard` → `_auto_dashboard` không ghi lệnh, có `thong_bao.json`.
2. `cli.py` dòng in sau `validate` (`run`): với bản `chi_dashboard` đang in "publish --xac-nhan-tong-hop" (sai, publish bị từ chối); đổi thành
   "Admin đưa lên dashboard bằng dat-dashboard --xac-nhan-nguon-moi".
3. Đường `tay` trên web ghi `chu_ky_nghiep_vu` vào sự kiện `da_duyet` bằng `kho_hop_dong.chu_ky_nghiep_vu`.

**Ghi chú vận hành (PM):** `don_ban_cu --dat-dich-rollback` chưa chặn bản `chi_dashboard`/tổng hợp (file cấm sửa ở phiếu này): **không đặt
đích rollback là bản một file**. Yêu cầu một file ở `het_cho` đọc registry (SQL warehouse) mỗi lượt dò 5 phút cho tới khi đủ quota; tránh bằng cách **dọn bản thử ngay sau
mỗi lượt, không để quá 1 bản thử tồn đọng** (quota cần số bảng + 183 ≤ 500; mỗi bản thử ~80 bảng/view). Thứ tự dọn: trả dashboard → tắt hai
DAG đợt → `don_ban_cu --xoa` (chạy thử rồi `--thuc-hien`) → `don_kho_dot --ca-hop-dong --thuc-hien` → xóa tay `data/ui_nhap_cloud/` và
`warehouse/pipeline/docker/nhap/*_mot/`.
`nhap_runner.py:655` (danh sách bản local) chưa loại `chi_dashboard`; `Registry.publish` vẫn chặn, nên chỉ hiện lỗi khi bấm.
Chưa kiểm trên cloud thật (nghiệm thu ở tổng duyệt).

### Lượt 2 (T2b trang web), 2026-11-12: ĐẠT

**Quyết định trong lượt:** cho phép sửa ngoài §8 đúng một dòng `scripts/ingest/approval.py`: `default_decisions` import `normalize` từ
`scripts.ingest.tu_dong` thay vì `adapters` (hai hàm giống hệt; `adapters` nạp DuckDB nên form chung không chạy được trên cloud).

**Claude tự chạy** (`RETAIL_TEST_DATABRICKS=0`, từng file, nối tạm `data/` rồi gỡ): `test_t2_mot_file_web` 84, `test_t2_chi_dashboard` 30,
`test_t2_mot_file` 56, `test_l1_dot_web` 140, `test_l5_theo_doi_dot` 67, `test_d5_dashboard` 35, `test_d5_con_tro` 39, `test_nhap_du_lieu` 97,
`test_nhap_tu_dong` 151, `test_nhap_do` 46, `test_l2_dot_cloud` 11, `test_don_ban_cu` 63, `test_tu_dong` 44. Không trượt. Trang Gửi/Duyệt được
render bằng AppTest trong test T2. `test_smoke`/`test_m1` không chạy (worktree thiếu `warehouse/dbt.duckdb`).

**Đột biến: 21/24 bị bắt.** Bị bắt: duyệt không ghi chữ ký; bỏ kiểm model dbt (`cho_model_dbt`); ghi hợp đồng trước khi kiểm; không ghi `v1`;
sai `duong`; bỏ kiểm trạng thái/số sự kiện; từ chối không lý do; nâng khi đã từ chối; nâng `mart` khi dbt chưa có cột; nhịp dò bỏ `dang_doc`;
gửi quá 200 MB; sai sha; mã `_dot` cho một file; ô xác nhận tổng hợp với bản nguồn mới; ứng viên mang cả hai cờ; mất băng rôn; `approval`
quay lại `adapters`; nâng hợp đồng ghi lệnh nạp bù; trang Gửi mất lựa chọn một file; `_auto_dashboard` không kiểm `chi_dashboard`
(mục 1 việc gộp lượt 1); `cli` in sai hướng dẫn (mục 2). Lọt:
- Bỏ so tên cột ở `upgrade_contract`: **tương đương**, `extension_contract.load` bắt `{cot.ten} == header` khi `KhoHopDong.write` kiểm.
- Bỏ kiểm role ở `change`: **tương đương**, `actor('duyet')` chỉ cho role có trang Duyệt (`ky_su`, `admin`).
- Bỏ `expected=` khi `upgrade_contract` gọi `KhoHopDong.write`: **thiếu test** (test xung đột giả `write`). Code đúng; nếu thiếu, người nâng
  sau có thể ghi `v<N+2>` đè ý người trước trong khe giữa kiểm và ghi. Không chặn; thêm test khi có lượt sửa sau.

**Ghi chú (không chặn):** `DotStore.approve` ghi `hop_dong/<ten>.yml` rồi mới ghi sự kiện; nếu ghi sự kiện lỗi giữa chừng, duyệt lại cùng tên
gặp `DaCo` (file bất biến). Gỡ bằng Từ chối rồi gửi lại file. Chưa kiểm trên cloud thật (tổng duyệt).

## 12. Kịch bản nghiệm thu trên cloud (PM chạy, Claude đọc kết quả)

Chạy bằng **bộ Airflow thử** (`scripts/ops/tong_duyet.ps1`, image dựng từ commit hiện tại của `nap-ky/myuyen`) và thư mục
`kho/tong_duyet`. Airflow chính vẫn chạy code cũ, giữ lịch 08:00; hai DAG đợt của nó vẫn tắt. Không chạy gần 08:00. Tắt Sleep máy.
File demo (đã thu nhỏ, nghiệm thu local 2026-11-05) ở `D:\retail-analytics-nhap\data\student_data\demo_2022\` và
`D:\retail-analytics-schema\data\student_data\`. Claude đã chạy thử phân loại trên máy (2026-11-12): `shipments_realistic.csv` → `tu_dong`;
`orders_enriched_bonus.csv` → `tu_dong`, `cot_moi = [bonus]`; `orders_enriched_thieu_comment.csv` → `can_nguoi` (`thieu_cot`);
`tf.json` → `can_nguoi` (`chua_co_hop_dong`, `doi_kieu`, `xung_dot_khoa`); quyết định mặc định của form cho `tf` ra hợp đồng hợp lệ, chưa có model dbt.

**File JSON demo (Claude dựng 2026-11-12, để chứng minh "nhận JSON, thêm/bớt field" đi trọn đường):** `orders_enriched_bonus.json`
(20,3 MB) và `orders_enriched_thieu_comment.json` (16,1 MB), cùng thư mục `demo_2022`, chuyển từ hai file CSV cùng tên: mảng đối tượng,
giữ thứ tự cột, mọi giá trị là chuỗi, ô rỗng thành `null`. Claude kiểm trên máy: `adapters.read_file` của bản JSON và bản CSV lệch 0 ô
(36.004 dòng); phân loại giống nhau (`bonus.json` → `tu_dong`, `cot_moi = [bonus]`; `thieu_comment.json` → `can_nguoi`, `thieu_cot`); mô phỏng
hợp đồng của lượt (`nhap_do` dòng 610–617) rồi `extension_prepare.prepare` ra `orders_enriched.parquet` lệch 0 dòng so với bản CSV.
Ca A giữ CSV, nên kịch bản có cả hai định dạng.

Lệnh `.\tong_duyet.ps1` dưới đây chạy trong `D:\retail-analytics-nap\scripts\ops`. Mỗi bước `truoc`, `trang_thai`, `kiem_t2`, `bao_cao_don`: dán kết quả cho Claude.

**Chuẩn bị**
1. `New-Item -ItemType Directory -Force D:\retail-analytics\data\ui_nhap_cloud`
2. App tạm, Secrets: đường dẫn kho đổi thành `/Volumes/retail_lab/nhap_du_lieu/kho/tong_duyet` → Save → Reboot.
3. `.\tong_duyet.ps1 dung` → `.\tong_duyet.ps1 truoc`. Đạt khi: `dashboard` null, `dat_nguong_do` true, `so_yeu_cau_co_san` 0.
4. `.\tong_duyet.ps1 bat`.

**A. Đường tự động, tự đưa lên dashboard, chống trùng**
- A1. Quản lý gửi "Một file dữ liệu mới" `demo_2022\shipments_realistic.csv`. Mong đợi: Đã gửi → Đang đọc file → Đã duyệt (đường Tự động) → Chờ chạy →
  Đang chạy → Đã kiểm tra → Đang trên dashboard, không ai bấm. Kẹt quá 10 phút ở một trạng thái thì `trang_thai`.
- A2. Admin và khách xem PS1: dòng nhỏ "Đang xem bản có nguồn mới shipments_realistic, chưa phải bản chính"; số G/R giống bản chính (sales không đổi).
- A3. `kiem_t2`. Đạt: `ket_luan` DAT, `active` = `moc.active`, bản có `chi_dashboard` true, `nguon_moi` có `shipments_realistic`, `dim_shipper` 80,
  `sales_lech_ngay` 0, một lệnh `dat` `ai: airflow`.
- A4. Gửi lại đúng file đó. Mong đợi trong ~5 phút: "Không có gì mới", không có lượt chạy.

**Sửa B (2026-11-12, sau A3):** ước tính quota ở trên sai. Ngưỡng của `nhap_do._quota` đếm **cả bảng lẫn view** (`truoc` 248, sau
bản A 334), không phải 174 bảng; 334 + 183 > 500 nên một bản thứ hai không chạy khi bản A còn. Thứ tự mới:
- B1'. (A vẫn trên dashboard) gửi `orders_enriched_bonus.json`. Mong đợi: Đã duyệt (Tự động) rồi **Hết chỗ lưu trữ** (`het_cho`), không chạy.
- B2 như dưới (nâng v2 không cần quota).
- B3'. Admin Trả dashboard (A thành Đã trả) → `tat_do` → `xoa_ban <bản A>` → `bat`. Trong ~5 phút B từ `het_cho` sang Chờ chạy, chạy, rồi
  **tự lên dashboard** (dashboard trống, đường tự động).
- B4'. Admin Trả dashboard (B thành Đã trả) → chọn bản B (nhãn "Bản có nguồn mới orders_enriched"), không có ô xác nhận tổng hợp → Đưa lên
  → B Đang trên dashboard: thử nút Admin đưa bản một file lên.
- B5'. `kiem_t2` như B4 dưới. Ca "bản dựng xong khi dashboard đang bận thì không tự lên" không thử được trên cloud lần này (quota); chỉ có test.

**Dọn quota (2026-11-12, sau A4, thay B1'–B5'):** `bao_cao_don` cho bốn bản: active `1eb69c0e…` 83, đích rollback `5d32a104…` 80,
dashboard (bản A) `6b38412d…` 86, `dbb80f56…` (active trước cửa sổ #1, cùng snapshot với active) 83; còn 2 bảng `retail_control`.
Chuyển đích rollback sang `dbb80f56…` (`don_ban_cu --dat-dich-rollback`) rồi `xoa_ban 5d32a104…` → còn 254, 254 + 183 ≤ 500: chạy **B gốc**
dưới đây, thử được cả ca dashboard bận. Cuối D chỉ xóa bản A và B; giữ `dbb80f56…` làm đích rollback.

**B. Cột mới, dashboard đang bận, nâng hợp đồng, Admin đưa lên** (bản gốc; chạy sau khi dọn quota ở trên)
- B1. (A vẫn trên dashboard) gửi `demo_2022\orders_enriched_bonus.json` (JSON, thêm field `bonus`). Mong đợi: đường Tự động, chạy tới Đã kiểm tra, **không** tự lên dashboard;
  trang Duyệt hiện "Dashboard đang có bản khác; chờ Admin đưa lên."
- B2. Kỹ sư dữ liệu, trang Duyệt, yêu cầu B: "Nâng hợp đồng orders_enriched v1 → v2", cột `bonus` để `nap`/`silver` → Duyệt nâng. Mong đợi: dòng
  "Cột mới có hiệu lực từ lần gửi sau…", không có yêu cầu hay lượt chạy mới.
- B3. Admin: Trả dashboard (chờ ≤ 5 phút, A thành Đã trả dashboard) → chọn bản B (nhãn "Bản có nguồn mới orders_enriched"), không có ô xác nhận
  tổng hợp → Đưa lên → chờ ≤ 5 phút → B Đang trên dashboard, dòng nhỏ đổi sang `orders_enriched`.
- B4. `kiem_t2`. Đạt: DAT, bản B `dim_sales_employee` 200, `hop_dong_da_duyet.orders_enriched` = `[v2.yml]`, mọi lệnh có kết quả.

**C. Đường tay (không tốn quota)**
- C1. Gửi `demo_2022\orders_enriched_thieu_comment.json` (JSON, bớt field `comment`) → Chờ duyệt, lý do thiếu cột. Kỹ sư dữ liệu Từ chối kèm lý do. Quản lý thấy "Lý do từ chối".
- C2. Gửi `D:\retail-analytics-schema\data\student_data\tf.json` → Chờ duyệt. Kỹ sư dữ liệu Duyệt với mặc định của form (tên `tf`) → "Chờ đội dữ liệu
  bổ sung mô hình", không chạy.
- C3. `kiem_t2`: hai yêu cầu `tu_choi`, `cho_model_dbt`; `hop_dong_da_duyet` có `tf: [v1.yml]`.
- Đường tay **có chạy** dùng chung code sau `da_duyet` với đường tự động (test lượt 1, mục 8); kịch bản không có file demo nào duyệt tay mà dbt chạy được.

**D. Dọn (bắt buộc, §11 lượt 1)**
1. Admin Trả dashboard; chờ ≤ 5 phút; `trang_thai` không còn `tren_dashboard`.
2. `.\tong_duyet.ps1 tat_do` → `.\tong_duyet.ps1 bao_cao_don` (dán) → `.\tong_duyet.ps1 xoa_ban <bản A>` → `.\tong_duyet.ps1 xoa_ban <bản B>`.
3. `.\tong_duyet.ps1 xoa_kho` (xóa cả `hop_dong_da_duyet/` của thư mục thử).
4. Xóa tay: nội dung `D:\retail-analytics\data\ui_nhap_cloud\` và `D:\retail-analytics\warehouse\pipeline\docker\nhap\*_mot\`.
5. `.\tong_duyet.ps1 ha`.
6. **Giữ** Secrets app tạm ở `kho/tong_duyet` tới cửa sổ bảo trì #2, để không ai gửi một file vào kho thật khi Airflow chính còn code cũ.

**Kết quả nghiệm thu (2026-11-12 → 2026-11-13, PM chạy, Claude đọc kết quả)**

Chạy theo **B gốc** sau khi dọn quota. Bản chính trong suốt đợt: `1eb69c0ea3dc4d17826364c6`; đích rollback: `dbb80f5674af47fe9c98f796`.

| Ca | Yêu cầu / bản | Thực tế | Kết luận |
|---|---|---|---|
| Chuẩn bị | | `truoc` đạt | Đạt |
| A1–A3 | `20261112T074526Z_ac6d15_mot` → bản A `6b38412dc6fb4dc4848728b3` | Tự đi hết các trạng thái, tự lên dashboard, không ai bấm; dòng nhỏ hiện cho khách; `kiem_t2` DAT | Đạt |
| A4 | | Không thử: gửi lại sẽ dựng bản mới (A đã xóa; chữ ký hợp đồng đổi sau v2) và vượt quota. Chỉ có test | Bỏ |
| B1 | `20261112T143649Z_909673_mot` → bản B `53db83c3515441f48ca5b909` | Đường Tự động, `cot_moi` = `bonus`, dừng ở Đã kiểm tra, không tự đè A; hiện "Dashboard đang có bản khác; chờ Admin đưa lên." | Đạt |
| B2 | hợp đồng `orders_enriched` | Nâng v1 → v2, `bonus` để `nap`, kiểu integer, `silver`; không sinh yêu cầu hay lượt chạy mới | Đạt |
| B3 | lệnh 2 `tra`, lệnh 3 `dat` | Admin Trả A rồi đưa B lên; dashboard = B, công bố 2026-11-13 02:11:42Z; PS1 16,43 tỷ / 12,52 tỷ / 76,2% (khớp bản chính) | Đạt |
| (dọn giữa) | bản A | Sau B3: `xoa_ban 6b38412d…` | Xong |
| B4 | | `kiem_t2` DAT: active không đổi, `chi_dashboard` true, `nguon_moi` `orders_enriched`, `sales_lech_ngay` 0, `dim_sales_employee` 200, 3 lệnh đều `dat`, `orders_enriched: [v2.yml]` | Đạt |
| C1 | `20261113T025446Z_1a94e2_mot` | Chờ duyệt, lý do "File thiếu cột comment so với hợp đồng orders_enriched v2"; DE Từ chối với lý do "File thiếu cột comment" → `tu_choi` | Đạt |
| C2 | `20261113T032356Z_7d8196_mot` (`tf.json`) | Chờ duyệt (không có hợp đồng, nguồn gần nhất `web_traffic`, lỗi ép kiểu, trùng khóa); DE duyệt tên `tf` → `cho_model_dbt`, không chạy | Đạt |
| C3 | | `kiem_t2` DAT: `tu_choi` + `cho_model_dbt`, `hop_dong_da_duyet` có `tf: [v1.yml]` | Đạt |
| D | | Thử `xoa_ban` B khi B còn trên dashboard → chốt **G8 chặn**, không xóa gì. Admin Trả → B `da_tra`, dashboard null → `tat_do` → `bao_cao_don` (chỉ B xóa được; G1, G2 khóa active và rollback) → `xoa_ban 53db83c3…` → `xoa_kho` → xóa tay `*_mot` (giữ `*_dot`) → `ha` | Xong |

Sau D: catalog `retail_lab` chỉ còn schema của `r_1eb69c0e` và `r_dbb80f56`; dashboard null; Secrets app tạm vẫn trỏ `kho/tong_duyet`.

**Thời gian đo được** (từ `lich_su` và task Airflow):
- **A** (CSV 95 MB):
  - chờ DAG 4m48s; đọc và ghép cột 8s; hàng đợi khoảng 50s;
  - pipeline 13m30: `prepare_snapshot` 1m15, `forecast_from_source` 21s, `ingest_and_dbt_build` 7m07, `quality_and_reader_gate` 4m43;
  - tự lên dashboard thêm khoảng 6 phút;
  - tổng khoảng 26 phút.
- **B** (JSON 19 MB): ghép cột 31s; pipeline 31 phút, vì `ingest_and_dbt_build` nằm chờ 14m40 sau `forecast_from_source`. Chưa rõ nguyên nhân; ca A không gặp.

**Phát hiện, chưa sửa:**
1. Trên danh sách kho cloud, dòng "Đường xử lý: Chờ đội dữ liệu" hiện ngay lúc Đã gửi, khi chưa biết đường nào. Vị trí: `views/gui_du_lieu.py:70`, `views/duyet_du_lieu.py:64`. Khối local có nhánh `da_gui` riêng. Lỗi chỉ ở chữ hiển thị; phải sửa trước cửa sổ #2 vì `apps/retail_app` nằm trong `code_version`.
2. `nhap_do._quota` chỉ đếm bảng và view đang tồn tại. Bảng đã xóa vẫn được metastore tính quota một thời gian (418/500 lúc đọc 2026-11-12 15:38Z), nên guard có thể cho chạy rồi dựng hỏng giữa chừng.
3. `bao_cao_don` in "Không đọc được quota".
4. `airflow dags pause` (`tat_do`) in `is_paused False`, tức trạng thái trước khi tắt. `dags list` sau đó cho `True`.
5. Ca A4 (gửi trùng) và ca "bản dựng xong khi dashboard bận không tự lên" có test; ca sau đã thử được trên cloud ở B1.

**Bằng chứng** (`D:\retail-analytics-nap\warehouse\nghiem_thu_t2_20261113\`, gitignored, chỉ trên máy PM):
- `kho_va_registry.json`: 48 file gồm sự kiện, đề xuất, hợp đồng, lệnh của 4 yêu cầu, và registry. Ba file dữ liệu lớn không chép.
- `airflow_thoi_gian.txt`: các lượt chạy và thời gian từng task.
- Ảnh chụp màn hình do PM giữ.
