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
