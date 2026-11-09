# Giao việc L2: Airflow xử lý đợt và lệnh dashboard, pipeline đợt chạy trên Databricks

Soạn ngày 2026-11-09, Claude. GPT code §3–§5. Claude rà độc lập trước khi commit; chưa đạt thì ghi vào §8 để GPT sửa.
Thiết kế gốc: [thiet_ke_dot_web_public.md](thiet_ke_dot_web_public.md), các mục §3, §5, §6, §7.1, §7.2, §8, §14 lát L2. Phần web đã xong ở [giao_viec_l1_dot_web.md](giao_viec_l1_dot_web.md).

Đọc trước:
- `AGENTS.md`, `CLAUDE.md`, `docs/agent_workflows.md`;
- thiết kế ở trên và phiếu L1 §3.3–§3.4;
- `apps/retail_app/ui/kho_dot.py`, `apps/retail_app/ui/nhap_dot.py`;
- `scripts/pipeline/cli.py`, `scripts/pipeline/du_bao_dot.py`, `scripts/pipeline/state.py`, `scripts/pipeline/runtime.py`;
- `scripts/ingest/dot.py` (`classify` :50, `classify_all` :122, `check_batch` :143);
- `deploy/airflow/dags/retail_dot_pipeline.py`, `deploy/airflow/dags/retail_batch_pipeline.py`;
- `scripts/pipeline/tests/test_airflow_extensions.py` (cách test DAG không cần scheduler), `scripts/pipeline/tests/test_d5_con_tro.py`, `scripts/ops/tests/test_don_ban_cu.py`.

## 0. Việc này là gì

L1 đã cho web ghi yêu cầu đợt và lệnh dashboard lên Volume. L2 làm phần xử lý ở Airflow:
- `nhap_du_lieu_do` dò Volume 5 phút một lần: kiểm file, phân loại, kiểm chỗ, trigger pipeline, theo dõi lượt chạy, xử lý lệnh dashboard, ghi sổ đợt;
- `retail_dot_pipeline` chạy được với target `databricks`, dừng ở validate;
- CLI cho phép `--dot` và `dat-dashboard` trên Databricks;
- bản tổng hợp chỉ cấp quyền đọc cho `retail-web-ro` (Q9).

Làm xong L2 chỉ mới kiểm bằng cloud giả. Lượt thật do PM chạy sau cửa sổ bảo trì (thiết kế §11).

**Thứ tự làm:** làm §3.1 trước, báo PM và dừng ở đó chờ PM chạy thử, rồi làm tiếp từ §3.2. Kết quả thử có thể đổi thiết kế của phần sau.

## 1. Bẫy phải tránh

1. **Chỉ có một lần dựng image, và sau đó đóng băng.** Sau cửa sổ, `retail_dbt/*`, `scripts/{pipeline,ingest,parity,forecast}` và `apps/retail_app` không sửa được tới 12/12, vì chúng nằm trong phần băm `code_version` (`cli.py:30–40`); đổi là lượt 08:00 tự publish bản mới. Vì vậy **logic dò đặt ở `scripts/ops/nhap_do.py`** và DAG ở `deploy/airflow/dags/`, đều ngoài phần băm, để sửa được sau cửa sổ. Trong phần băm chỉ đổi đúng những chỗ ở §4.
2. **Dò không được đánh thức warehouse.** Warehouse tự dừng sau 10 phút rảnh; dò 5 phút một lần qua SQL sẽ giữ nó chạy cả ngày. Lần dò bình thường chỉ dùng Files API. Chỉ mở `Databricks()` khi có việc thật: sắp trigger một đợt (đọc `active`), hoặc chạy lệnh dashboard. Có test đếm số lần mở.
3. **`airflow` và pipeline là hai môi trường Python.** Task DAG chạy bằng Python của Airflow, không có `duckdb`, `databricks-sdk`. Logic dò chạy bằng `/opt/pipeline/bin/python` qua `subprocess`, như DAG hiện có. Môi trường `/opt/pipeline` **không có `streamlit`** (Claude kiểm trong container ngày 2026-11-09), mà `ui/nhap_dot.py` import `ui.roles`, và `ui/roles.py:25` import streamlit. Vì vậy phải tách phần thuần ra file riêng (§3.2).
4. **Task không gọi được metadata DB.** Airflow 3 chỉ cho task dùng Task SDK. Bản 3.3.2 trong image có `RuntimeTaskInstance.get_dagrun_state(dag_id, run_id)` và `get_dr_count`. Route của `get_dagrun_state` trả 404 khi không có run, nên **gọi `get_dr_count(dag_id, run_ids=[…])` trước**. Không dùng `from airflow.models`.
5. **Pool chưa tồn tại thì task đứng im.** Image hiện chỉ có `default_pool`. Thêm `pool='retail_writer'` vào DAG production mà chưa tạo pool thì lượt 08:00 sẽ treo mà không báo lỗi. Tạo pool trong `airflow-init` (§3.7).
6. **Sổ đợt và trạng thái phải ghi lại được khi chạy lại.** Máy có thể tắt giữa hai lần ghi. Mọi bước của lệnh dashboard kiểm trạng thái trước khi ghi (§3.5).
7. **`D2-1`, `D2-2`, `D2-3` không được phát hiện ở bước phân loại.** Các mã này nằm ở `dot.check_batch`, chạy trong `prepare` của pipeline, không nằm trong `classify` (thiết kế §5 bước 1 ghi chưa đúng). Vì vậy chúng ra `loi` kèm mã, không ra `sai_hop_dong` (§3.6). `prepare` lỗi thì chưa có schema `r_`, nên vẫn không tốn quota.
8. **Không đưa nội dung lỗi thô vào Volume.** Thông báo ghi lên Volume chỉ là câu cố định hoặc mã `D2-*`. Exception có thể chứa SQL, token (`cli.py:515`).

## 2. Môi trường và ràng buộc

- **Worktree** `D:\retail-analytics-nap`, nhánh `nap-ky/myuyen`. L1 đã commit (`619396f`).
- Python: `D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8`. Biến `RETAIL_TEST_DATABRICKS=0`.
- **Không commit, không push.** Không kết nối Databricks. Không chạy Docker, không dựng image. Không đọc `.env.*.local`, `.streamlit/secrets.toml`, `~/.retail-secrets/*`.
- **Chỉ sửa hoặc tạo các file ở §4.** Không sửa `retail_dbt/`, `scripts/ingest/dot.py`, `scripts/forecast/*`, `docs/phan_quyen.md`, và không sửa **phiếu L3** (đang chờ làm sau).
- **Máy thiếu RAM:** chạy từng file test một lệnh; không chạy chung `apps` và `scripts`.
- Junction `data` chỉ tạo khi test cần: `cmd /c mklink /J data D:\retail-analytics-am\data`; gỡ bằng `cmd /c rmdir data`. **Không dùng `Remove-Item -Recurse`.**

## 3. Thiết kế

### 3.1 Làm trước: script thử Volume thật (`scripts/ops/thu_kho_volume.py`, mới)

PM tự chạy trên laptop, **trước cửa sổ bảo trì**, để biết sớm đăng nhập và quyền Volume có đúng không. Script chỉ dùng Files API, không gửi SQL.

```
python -B -X utf8 scripts/ops/thu_kho_volume.py --env-file <đường dẫn> --danh-tinh writer|pipeline [--host <host>] [--goc /Volumes/retail_lab/nhap_du_lieu/kho]
```

- `writer` đọc `RETAIL_NHAP_DBX_CLIENT_ID/SECRET`, `pipeline` đọc `RETAIL_PIPELINE_CLIENT_ID/SECRET` từ file. Chỉ đọc đúng các khóa đó và `DATABRICKS_HOST`; không có host thì dùng `--host`. **Không in giá trị nào, kể cả khi lỗi.** Bắt mọi lỗi đăng nhập, in câu cố định kèm tên loại lỗi.
- Tạo client bằng `WorkspaceClient(host=…, client_id=…, client_secret=…, auth_type='oauth-m2m')` rồi dùng đúng `KhoVolume` của L1.
- Chỉ ghi dưới `thu_ket_noi/<giờ UTC>_<6 hex>/`, không bao giờ dưới `yeu_cau/`, `lenh/`, `so_dot/`.

| Mã | Kiểm | Đạt khi |
|---|---|---|
| V1 | `ghi_moi` rồi `doc` | Nội dung khớp từng byte |
| V2 | Ghi lại cùng đường dẫn | `DaCo`, nội dung vẫn là bản đầu |
| V3 | `liet_ke` | Thấy đúng file vừa ghi; thư mục không có thì trả rỗng |
| V4 | `ghi_json_so_tiep` tuần tự 2 lần | Số 1, 2; `ma` đọc lại khớp |
| V5 | 2 luồng đua, 5 vòng | Mỗi vòng đúng 1 thắng; bên kia `TrangThaiDaDoi` |
| V6 | Đọc file kích thước 1 MB | sha256 khớp |

- In mỗi mã một dòng `ĐẠT`/`TRƯỢT`. Thoát mã 0 nếu đạt hết, 1 nếu không, 3 nếu không đăng nhập được.
- **Dọn thư mục thử**, chạy trong `finally` nên cả khi một mã trượt giữa chừng. SDK 0.117.0 tách hai API: `client.files.delete(file_path)` xóa file, `client.files.delete_directory(directory_path)` chỉ xóa thư mục rỗng.
  1. Duyệt đệ quy thư mục của lượt hiện tại bằng `client.files.list_directory_contents`, gồm cả file các mã đã ghi trước khi trượt.
  2. Xóa từng file bằng `delete`, rồi xóa thư mục con từ dưới lên bằng `delete_directory`, cuối cùng xóa thư mục lượt.
  3. Trước mỗi lần xóa, kiểm đường dẫn nằm trong `<goc>/thu_ket_noi/<giờ UTC>_<6 hex>/` của lượt hiện tại; không nằm trong thì bỏ qua và cảnh báo. Không chạm các lượt khác.
  4. Lỗi dọn chỉ in cảnh báo, gồm đường dẫn và tên loại lỗi. Mã thoát vẫn theo V1–V6.
- Test bằng client giả: mọi nhánh trên, không in secret (đưa secret mẫu vào file env, chặn `capsys`), không ghi ra ngoài `thu_ket_noi/`. Client giả phải theo đúng SDK: `delete` lên thư mục thì lỗi, `delete_directory` lên thư mục còn nội dung thì lỗi. Thêm các ca về dọn:
  - đạt hết thì không còn gì của lượt;
  - một mã trượt giữa chừng vẫn dọn hết;
  - thư mục của lượt khác còn nguyên;
  - lỗi dọn không đổi mã thoát.

Xong mục này thì báo PM rồi **dừng**.

### 3.2 Tách phần thuần của trạng thái (`apps/retail_app/ui/trang_thai_dot.py`, mới)

Chuyển từ `ui/nhap_dot.py` sang: `TRANSITIONS_DOT`, `ID_PATTERN`, `request_path`, `phat_lai`. File mới chỉ import thư viện chuẩn. `nhap_dot.py` import lại các tên này, nên `nd.phat_lai` ở test L1 vẫn chạy.

Ba thay đổi hành vi:
1. **Thêm `da_tra → tren_dashboard`.** Demo bật tắt nhiều lần (thiết kế §7.5). `da_tra` đang là trạng thái cuối nên lần bật thứ hai sẽ làm hỏng chuỗi sự kiện. Claude sửa thiết kế §3 cho khớp.
2. **`phat_lai` kiểm kiểu:** `release_id`, `ma_loi`, `thong_bao`, nếu có, phải là chuỗi; sai thì `trang_thai = 'hong'`. Lý do: Claude thử ở L1 lượt 3, `release_id` là số làm vỡ cả khối đợt ở `row['release_id'][:8]`.
3. **Trang không còn lộ lỗi kỹ thuật** khi dữ liệu kho hỏng:
   - `DotStore.latest_command`: file lệnh hoặc kết quả không đọc được, hay lệnh thiếu `loai`, thì trả lệnh có `ket_qua = {'ket_qua': 'loi', 'thong_bao': 'Dữ liệu lệnh hỏng; báo kỹ sư dữ liệu.'}`, và không khóa nút. `label` không được ném `KeyError`.
   - `DotStore.ledger` hỏng: giữ `ValueError` với câu `'Sổ đợt hỏng; báo kỹ sư dữ liệu.'`, và trang hiện đúng câu này, không phải chuỗi JSON.

### 3.3 CLI và pipeline (trong phần băm, sửa ít nhất có thể)

| Chỗ | Đổi |
|---|---|
| `cli.py:340–341` | Bỏ `or target == 'databricks'` |
| `cli.py:440–441` | Bỏ hai dòng chặn `manifest.get('dot') and target == 'databricks'` |
| `cli.py:588–589` | Bỏ `or a.target == 'databricks'` |
| `cli.py:448–452` | Target databricks thì mở `Databricks()` và truyền registry SQL vào `du_bao_dot.dung_lai`. Lượt không đợt **không** mở kết nối ở stage forecast như hiện nay |
| `cli.py:610–624` | `dat-dashboard`: bỏ chặn target. Target databricks dùng `Registry(a.root, cloud.query)` và `verify_consumers(record, registry, cloud)`, đóng `cloud` trong `finally`, giống `tra-dashboard` (`:632–638`) |
| `cli.py:516` | `failure.json` thêm `ma_loi` khi `str(error)` khớp `^D2-[A-Za-z0-9-]+:`, chỉ lấy phần mã. Không ghi phần còn lại |
| `cli.py:694` | Thêm `except BlockingIOError`: in `'writer.lock đang bận'` ra stderr, `sys.exit(75)`. DAG hiện coi mã khác 2 là lỗi tạm thời và thử lại, nên hành vi lượt 08:00 không đổi |
| `du_bao_dot.py:75–78` | `_kiem_nguon(root, release_id, target, registry)`: dùng registry truyền vào; mặc định `Registry(root)` cho local |
| `du_bao_dot.py:84–85` | `context.get('target') != target` thay cho so với `'duckdb'` |
| `du_bao_dot.py:135–136` | Bỏ chặn "Bản có đợt chỉ chạy local" |

Không đổi:
- `snapshot.prepare`, `Databricks.ingest`, `dbt_build`, `validate_data`;
- publish của bản không đợt;
- chuỗi lệnh của lượt không đợt phải y hệt trước khi sửa (có test).

**Phần `ky_cua_ban` và chế độ không dự báo thuộc L3.** L2 không đụng tới `:39–46`, `:59–66`.

### 3.4 Quyền đọc của bản tổng hợp (Q9): `verify_consumers`

Thiết kế §7.2. Trong vòng `for kind, full in [('APP', app), ('AI', ai)]` (`cli.py:248`), khi `context.get('co_du_lieu_tong_hop') is True` thì chỉ chạy `APP`. Cờ này có ở cả context của `validate` và bản ghi registry mà `dat-dashboard` truyền vào.

- Bản không đợt: danh sách câu `GRANT` và thứ tự **y hệt** trước khi sửa.
- Không đổi `_check_dbx_identity`, `allowed_versions`. Đọc `_release_scope` (`dwh/guarded.py:347`): phần bắt buộc chỉ là bản `active`, nên AI không có quyền trên bản tổng hợp vẫn đạt. Test phải chứng minh điều này với registry có cả hai bản.

### 3.5 Logic dò (`scripts/ops/nhap_do.py`, mới)

Chạy bằng `/opt/pipeline/bin/python`, cwd `/opt/retail`. Hai lệnh con, kết quả là một dòng JSON cuối ở stdout:

- `quet`: làm bước 1–3 dưới đây, trả `{"dang_chay": [{request_id, airflow_run_id, pipeline_run_id, conf}]}`.
- `ket_thuc --trang-thai <JSON>`: nhận trạng thái các lượt từ Airflow, làm bước 4–5, trả `{"trigger": [{airflow_run_id, conf}]}`.

**Dùng chung:**
- Kho: `KhoVolume(RETAIL_NHAP_VOLUME, WorkspaceClient(pipeline writer))`. Không dùng khóa `retail-nhap-writer` trong Airflow. PM cấp quyền Volume cho pipeline writer (§6). Cho phép tiêm `Kho`, hàm gọi CLI và hàm mở cloud để test bằng `KhoDia`.
- Sự kiện ghi bằng `ghi_json_so_tiep(…, {'toi': …, 'ai': 'airflow', 'ghi_chu': '', …}, expected=len(lich_su))`. Gặp `TrangThaiDaDoi` thì bỏ qua yêu cầu đó, để lần dò sau.
- **Cô lập:** một yêu cầu hay lệnh hỏng không chặn phần còn lại. In dòng log chỉ gồm mã yêu cầu và tên loại lỗi.
- Sổ đợt hỏng: **không phân loại và không trigger** đợt nào trong lần dò đó, vì không biết chuỗi; vẫn xử lý lệnh `tra` và theo dõi lượt đang chạy.
- Thư mục làm việc: `warehouse/pipeline/docker/nhap/<id>/file/`. Không cần đổi compose (`docker-compose.airflow.yml:22`).

**Bước 1: lệnh dashboard.** Lấy lệnh mới nhất chưa có `.ket_qua.json`. Gọi CLI bằng `subprocess`, timeout 300 giây, `--run-id lenh_<số>`, `--target databricks`, `--root warehouse/pipeline/docker`.

| Mã thoát CLI | Xử lý |
|---|---|
| 0 | Làm các bước sau, rồi ghi kết quả `dat` |
| 75 | Không ghi gì, để lần dò sau |
| 2 | Kết quả `loi`, `'Bản không đạt điều kiện đưa lên dashboard.'` |
| khác, hoặc hết giờ | Kết quả `loi`, `'Chưa đổi được dashboard; thử lại sau ít phút.'` |

`dat`, thứ tự cố định và kiểm trước mỗi lần ghi:
1. Không có `request_id`, hoặc yêu cầu đó có `release_id` khác lệnh: kết quả `loi`, không gọi CLI.
2. `cli dat-dashboard --release-id <rid> --xac-nhan-tong-hop`.
3. `ma_dot` chưa có trong sổ (phát lại `so_dot/`) thì ghi `vao_so {ma_dot, request_id, release_id, files}`, `files` lấy từ `yeu_cau.json`.
4. Yêu cầu khác đang `tren_dashboard` thì ghi `da_tra`, `ghi_chu: 'Thay bằng bản mới'`.
5. Yêu cầu này đang `da_kiem` hoặc `da_tra` thì ghi `tren_dashboard`.
6. Ghi `lenh/<số>.ket_qua.json` bằng `ghi_moi`; `DaCo` coi như xong.

`tra`: `cli tra-dashboard`; mọi yêu cầu `tren_dashboard` ghi `da_tra`; ghi kết quả. Sổ đợt không đổi (Q6).

Lệnh hỏng (JSON lỗi, `loai` lạ): ghi kết quả `loi`, không gọi CLI.

Máy tắt giữa hai bước: lệnh vẫn chưa có kết quả, nên lần dò sau chạy lại. `publish_dashboard` đã bỏ qua khi con trỏ đúng (`state.py:132`), các bước sau tự kiểm. **Cách này thay cho đối soát sổ với registry mỗi lần dò ở thiết kế §5**, vì đối soát đó phải đọc SQL và đánh thức warehouse. Claude sửa thiết kế cho khớp.

**Bước 2: `da_gui`.**
- Đọc `yeu_cau.json`; tên file phải khớp `[A-Za-z0-9_.-]+`, nếu không thì `loi_file`.
- **Chỉ tải đúng các file trong danh sách**, vì `dot.classify` duyệt mọi file trong thư mục (`dot.py:57–60`). Tải vào thư mục tạm cạnh đích, so `sha256` và `so_byte`, rồi đổi tên.
- Thiếu file hoặc lệch hash: `loi_file`. Đạt: `dang_kiem`.

**Bước 3: `dang_kiem` và `het_cho`.**
- `dang_kiem`: nếu file local thiếu hay lệch thì tải lại. Gọi `dot.classify(folder, 'data')`.
  - `DotError`: `sai_hop_dong`, `ma_loi` = phần trước dấu `:`, `thong_bao` = phần sau, vì câu đó chỉ gồm tên file, tên cột, số dòng.
  - Trùng đợt: `ma_dot` có trong sổ, **hoặc** có yêu cầu khác cùng `ma_dot` đang `cho_chay`, `dang_chay`, `het_cho`, `da_kiem`: `sai_hop_dong`, `ma_loi: 'D2-7'`. Phải có vế thứ hai: đợt chỉ vào sổ khi đã công bố, nên gửi lại trong lúc chờ công bố vẫn phải bị chặn (Mốc 1 nghiệm thu mục 2).
  - Lỗi khác: giữ nguyên trạng thái, in log, để lần dò sau.
- **Kiểm chỗ** (sau khi phân loại đạt, và mỗi lần dò với `het_cho`): đếm qua `schemas.list` + `tables.list` của `retail_lab`, tính cả view, bằng pipeline writer. `dùng + 183 > 500` thì `het_cho`, ngược lại `cho_chay`.
  - **Giới hạn đã biết, ghi vào docstring:** số đếm không gồm bảng vừa xóa còn bị tính trễ khoảng 7 ngày, và pipeline writer không đọc được quota thật (S0). Quá quota thì dbt lỗi, yêu cầu ra `loi`, DE chạy lại sau khi dọn.
- Sự kiện `cho_chay` mang thêm `ma_dot`. Với `het_cho → cho_chay` cũng vậy, lấy từ lần phân loại.

**Bước 4: theo dõi `dang_chay`** (`ket_thuc`):

| Trạng thái DAG run | Xử lý |
|---|---|
| `queued`, `running` | Không làm gì |
| `success` | Đọc `runs/<pipeline_run_id>/context.json`. `stage == 'validated'`, có `release_id`, `co_du_lieu_tong_hop is True` thì `da_kiem {release_id}`. Khác đi thì `loi` |
| `failed` | `loi`. Đọc `failure.json`: có `ma_loi` thì ghi kèm, `thong_bao = 'Lượt chạy lỗi ở bước <stage>; kỹ sư dữ liệu xem nhật ký.'` |
| không có run | Đưa vào danh sách trigger lại, dùng `airflow_run_id` và `conf` đã ghi trong sự kiện `dang_chay` (máy tắt giữa lúc ghi sự kiện và trigger) |

**Bước 5: `cho_chay`.** Chỉ khi không còn yêu cầu `dang_chay`; lấy yêu cầu có `id` nhỏ nhất, mỗi lần một yêu cầu.
1. Mở `Databricks()`, đọc `active` bằng `Registry(root, cloud.query)`, rồi đóng.
2. Bộ phần mở rộng: các nguồn có `mo_rong` trong `snapshots/<snapshot_id của active>/manifest.json` (Q10). Không ghi cứng tên nào. Hôm nay bản `active` chỉ có `orders_enriched`. Thiếu manifest thì giữ `cho_chay`, in log.
3. Tải lại các đợt trong sổ về `nhap/<request_id của đợt>/file/`, so sha256 với `files` trong sổ. Lệch thì giữ `cho_chay`, in log.
4. `lan` = số sự kiện `dang_chay` đã có + 1. `pipeline_run_id = 'dot_<id>_<lan>'`, `airflow_run_id` cùng giá trị.
5. `conf = {request_id, target: 'databricks', dots: [đường dẫn tuyệt đối theo thứ tự sổ, đợt mới cuối cùng], du_bao_tu: <active>, extensions, pipeline_run_id}`.
6. Ghi `dang_chay {lan, airflow_run_id, pipeline_run_id, conf}` **trước**, rồi trả về để DAG trigger.

### 3.6 Hai DAG

**`deploy/airflow/dags/nhap_du_lieu_do.py` (mới).** `schedule='*/5 * * * *'`, `catchup=False`, `max_active_runs=1`, `is_paused_upon_creation=True`, `dagrun_timeout=20 phút`, `retries=0`, không có pool.

```
quet → doc_trang_thai → ket_thuc → trigger (mapped)
```

- `quet`, `ket_thuc`: `subprocess.run` với timeout, mã khác 0 thì `AirflowException`. Output của `subprocess` đi vào log, không in env.
- `doc_trang_thai`: với từng lượt, `get_dr_count` trước, có thì `get_dagrun_state`. Dùng `get_current_context()['ti']`.
- `trigger`: `TriggerDagRunOperator.partial(task_id=…, trigger_dag_id='retail_dot_pipeline', skip_when_already_exists=True, wait_for_completion=False).expand_kwargs(…)`, từ `airflow.providers.standard.operators.trigger_dagrun`. `trigger_run_id` là `airflow_run_id`.

**`retail_dot_pipeline.py`.** Thay `dot` bằng các tham số dưới, giữ không có stage `publish` (`:16–17`). Chỉ trigger từ ngoài, `schedule=None`.

| Param | Kiểm |
|---|---|
| `target` | `duckdb` (mặc định) hoặc `databricks` |
| `dots` | Mảng không rỗng, mỗi phần tử khớp `^/opt/retail/(data_demo/[a-zA-Z0-9_-]{1,100}\|warehouse/pipeline/docker/nhap/[0-9]{8}T[0-9]{6}Z_[a-f0-9]{6}_dot/file)$` |
| `du_bao_tu` | 24 hex, như cũ |
| `extensions` | Như cũ |
| `pipeline_run_id` | Tùy chọn, `^[a-zA-Z0-9_-]{1,100}$`; không có thì băm `run_id` như cũ |
| `request_id` | Tùy chọn, đúng mẫu mã; chỉ để truy vết |
| `force` | Như cũ |

Mỗi task thêm `pool='retail_writer'`. `--target`, `--dot` (mỗi đường dẫn một cờ, giữ thứ tự) lấy từ param. Mã 2 vẫn là `AirflowFailException`.

**`retail_batch_pipeline.py` (DAG production).** Chỉ thêm **một** khóa `'pool': 'retail_writer'` vào `default_args` (`:43`). PM đã duyệt ở thiết kế §5 bước 6. Không đổi gì khác; có test so diff.

Lệnh dashboard **không** dùng pool, khác thiết kế §5 bước 6 (Claude sửa thiết kế cho khớp). Lý do: `max_active_runs=1`, nên nếu task lệnh chờ pool trong khi đợt đang dựng cả tiếng, DAG dò đứng theo và không ai theo dõi được lượt đó. `writer.lock` đã giữ từng stage, mã 75 cho biết phải đợi lần dò sau, và `dat-dashboard` nhẹ, không ảnh hưởng RAM.

### 3.7 Compose và mẫu môi trường

- `docker-compose.airflow.yml`, lệnh của `airflow-init`: chèn `airflow pools set retail_writer 1 'CLI ghi cua pipeline' &&` ngay sau `airflow db migrate &&`.
- `deploy/airflow/env.example`: thêm `RETAIL_NHAP_VOLUME=/Volumes/retail_lab/nhap_du_lieu/kho`, kèm một dòng giải thích. Không thêm khóa mới.

## 4. File được sửa

| File | Phần băm | Việc |
|---|---|---|
| `scripts/ops/thu_kho_volume.py` (mới) | không | §3.1 |
| `scripts/ops/tests/test_thu_kho_volume.py` (mới) | không | §3.1 |
| `apps/retail_app/ui/trang_thai_dot.py` (mới) | có | §3.2 |
| `apps/retail_app/ui/nhap_dot.py` | có | §3.2 |
| `apps/retail_app/views/gui_du_lieu.py`, `views/duyet_du_lieu.py` | có | §3.2 mục 3; chỉ phần hiện lỗi |
| `apps/retail_app/tests/test_l1_dot_web.py` | có | thêm ca §3.2 |
| `scripts/pipeline/cli.py` | có | §3.3, §3.4 |
| `scripts/pipeline/du_bao_dot.py` | có | §3.3 |
| `scripts/pipeline/tests/test_l2_dot_cloud.py` (mới) | có | §5 |
| `scripts/pipeline/tests/test_airflow_extensions.py` | có | ca pool, DAG đợt |
| `scripts/pipeline/tests/test_d3_du_bao.py`, `test_d5_con_tro.py` | có | chỉ sửa ca đang khóa đúng hành vi vừa đổi (chặn databricks); ghi rõ từng ca trong báo cáo |
| `scripts/ops/nhap_do.py`, `scripts/ops/tests/test_nhap_do.py` (mới) | không | §3.5 |
| `deploy/airflow/dags/nhap_du_lieu_do.py` (mới) | không | §3.6 |
| `deploy/airflow/dags/retail_dot_pipeline.py` | không | §3.6 |
| `deploy/airflow/dags/retail_batch_pipeline.py` | không | đúng một khóa `pool` |
| `docker-compose.airflow.yml`, `deploy/airflow/env.example` | không | §3.7 |

Không thêm thư viện.

## 5. Kiểm

Không cần Databricks hay Docker. Dùng `KhoDia` thư mục tạm, cloud giả ghi lại mọi câu SQL, hàm CLI giả. DAG test theo cách của `test_airflow_extensions.py`.

1. **§3.1:** các ca đã ghi ở mục đó.
2. **Tách file:** chạy tiến trình con với `sys.modules['streamlit'] = None`, import `ui.trang_thai_dot`, `ui.kho_dot`: không lỗi. Test L1 vẫn đạt.
3. **Trạng thái:**
   - `da_tra → tren_dashboard` hợp lệ; `release_id` số ra `hong`;
   - trang Duyệt với lệnh hỏng, lệnh thiếu `loai`, kết quả hỏng: không có chuỗi `Expecting property`, nút không bị khóa; sổ hỏng: hiện đúng câu cố định.
4. **Luồng đạt:** `da_gui → dang_kiem → cho_chay → dang_chay → da_kiem → tren_dashboard → da_tra → tren_dashboard`, trên `KhoDia`, dùng đợt mẫu nhỏ.
5. **File:** sai sha256, sai kích thước, thiếu file, tên chứa `../` đều ra `loi_file`, không ghi ra ngoài `nhap/`; file lạ trong Volume ngoài danh sách không bị tải.
6. **Phân loại:** thiếu một bảng giao dịch ra `sai_hop_dong` với `D2-missing`; gửi lại đợt đã vào sổ ra `D2-7`; gửi lại khi đợt trước đang `da_kiem`, chưa vào sổ, cũng ra `D2-7`; gửi lại sau khi DE `bo` khỏi sổ thì được chạy. Các ca này **không** gọi cloud và không trigger.
7. **Không đánh thức warehouse:** lần dò có một yêu cầu `da_gui`, lần dò không có việc, lần dò có `dang_chay`: số lần mở `Databricks()` đều bằng 0. Trigger một đợt: đúng 1. Lệnh dashboard: 0 trong `nhap_do.py` (kết nối nằm trong CLI).
8. **Trigger:**
   - hai yêu cầu `cho_chay`: chỉ yêu cầu `id` nhỏ nhất;
   - đang có `dang_chay`: không trigger thêm;
   - `extensions` đúng theo manifest giả của `active`, không ghi cứng: đổi manifest thì `conf` đổi;
   - thứ tự `dots`: đợt trong sổ theo thứ tự, đợt mới cuối cùng; ledger có `bo` thì bỏ đợt đó;
   - DE chạy lại sau `loi`: `lan` tăng, `pipeline_run_id` mới;
   - sự kiện ghi trước khi trả trigger; "không có run" thì trigger lại đúng `airflow_run_id` cũ.
9. **Theo dõi:** đủ các dòng bảng bước 4, gồm `failure.json` có `D2-1`, không có `ma_loi`, và `success` mà context không `validated`. Không thông báo nào chứa nội dung exception.
10. **Quota:** dùng 317 thì `cho_chay`, 318 thì `het_cho`; `het_cho` tự sang `cho_chay` khi đủ chỗ; có tính view.
11. **Lệnh dashboard:**
    - đủ bảng mã thoát; mã 75 không ghi gì;
    - `dat` lặp lại sau khi "máy tắt" giữa từng bước (giả lập ném lỗi lần lượt sau bước 2, 3, 4, 5): chạy lại cho đúng trạng thái cuối, sổ không có hai dòng `vao_so`, không có sự kiện trùng;
    - `dat` bản D24 khi D23 đang trên dashboard: yêu cầu D23 ra `da_tra`;
    - `dat` lệch `release_id` với yêu cầu: `loi`, không gọi CLI;
    - lệnh hỏng: `loi`, không gọi CLI;
    - `tra`: sổ không đổi.
12. **Cô lập:** một yêu cầu `yeu_cau.json` hỏng, một yêu cầu tốt: yêu cầu tốt vẫn đi tiếp. Sổ hỏng: không trigger, nhưng lệnh `tra` vẫn chạy.
13. **CLI databricks với cloud giả:**
    - `prepare`, `forecast` nhận `--dot` target databricks và đi đúng registry SQL; bản nguồn target khác thì từ chối;
    - `dat-dashboard` target databricks gọi `publish_dashboard` qua SQL, `verify_consumers` chạy với cloud, `cloud.close` luôn được gọi, kể cả khi lỗi;
    - khóa bận thoát mã 75;
    - `failure.json` có `ma_loi` đúng, không có chữ nào khác của lỗi.
14. **Q9:** bản tổng hợp: có `GRANT` cho client APP, **không** có câu nào cho client AI, không kết nối bằng client AI. Bản không đợt: danh sách câu y hệt bản chụp trước khi sửa. Guard: `_release_scope` với registry có cả hai bản, AI chỉ có quyền trên `active`, vẫn đạt.
15. **Không đợt thì y hệt:** chuỗi lệnh `command()` của `retail_batch_pipeline` và của CLI không đổi; `git diff` của file DAG production chỉ có đúng một dòng thêm.
16. **DAG:**
    - `nhap_du_lieu_do` đúng lịch, `max_active_runs=1`, tạm dừng khi tạo;
    - `retail_dot_pipeline` không có stage `publish`; đường dẫn `../`, đường dẫn ngoài hai mẫu, rỗng đều bị từ chối;
    - mọi task CLI của hai DAG có `pool='retail_writer'`; compose có lệnh tạo pool trước khi scheduler chạy.
17. **Không hồi quy**, từng lệnh một, ghi số trước và sau khi sửa:
    - `apps/retail_app/tests/test_l1_dot_web.py`, `test_d5_dashboard.py`;
    - `scripts/pipeline/tests/test_airflow_extensions.py`, `test_d5_con_tro.py`, `test_d3_du_bao.py`, `test_d3_ky_dot.py`, `test_snapshot_dot.py`, `test_extensions_cli.py`;
    - `scripts/ops/tests/test_don_ban_cu.py`, `scripts/ingest/tests/test_dot.py`.

Claude sẽ thử đột biến khi rà, ít nhất gồm:
- gọi `Databricks()` trong mọi lần dò;
- bỏ vế "yêu cầu khác cùng `ma_dot`" của D2-7;
- ghi `vao_so` không kiểm đã có;
- đổi thứ tự: ghi kết quả trước khi ghi sổ;
- ghi sổ khi CLI lỗi;
- mã 75 thành `loi`;
- trigger trước rồi mới ghi `dang_chay`;
- cho nhiều lượt chạy cùng lúc;
- ghi cứng `extensions`;
- tải mọi file trong thư mục thay vì theo danh sách;
- bỏ kiểm sha256 của đợt trong sổ;
- Q9: vẫn cấp quyền cho AI;
- bỏ `da_tra → tren_dashboard`;
- ghi `str(error)` vào `failure.json` hoặc Volume;
- bỏ `pool` ở một task;
- đổi ngưỡng 183.

## 6. Không giao GPT

- Commit, push, PR. Đặt Streamlit Secrets và `.env.airflow.local`. Mọi thao tác trên Databricks thật. Không dựng image, không chạy Docker.
- **PM, trước cửa sổ, theo script Claude viết:**
  1. Chạy `thu_kho_volume.py` với `writer`, rồi `pipeline`.
  2. Cấp `READ VOLUME`, `WRITE VOLUME`, `USE SCHEMA nhap_du_lieu` cho `retail-pipeline-writer` nếu bước 1 báo thiếu (thiết kế T2 §8.5). **Không bao giờ cấp cho `account users`.**
  3. Dựng image thử dưới **tên khác** (`retail-airflow:thu-l2`), không dùng tên `retail-airflow:local`, rồi nạp 3 file DAG bằng image đó để bắt lỗi import. Image thử không thay DAG đang chạy.
- **PM, trong cửa sổ:** bật cả hai DAG mới (đều tạm dừng khi tạo), kiểm pool `retail_writer` đã có **trước** khi bật lại `retail_batch_pipeline`.

## 7. Báo cáo của GPT khi xong (PM dán cho Claude rà)

- **Báo riêng khi xong §3.1**, rồi dừng.
- Danh sách file đã sửa; `git status --short`; `git diff --stat`.
- Số đạt/trượt/skip của từng file ở §5 mục 17, trước và sau khi sửa.
- Từng ca test cũ phải sửa và vì sao.
- Chỗ làm khác phiếu và lý do. Chỗ nào phiếu chưa rõ thì ghi câu hỏi, không tự đoán.

## 8. Rà của Claude (Claude ghi, GPT đọc để sửa)

### Lượt 1 — §3.1 (2026-11-09): chưa đạt, sửa rồi báo lại, **vẫn dừng trước §3.2**

Claude tự chạy `test_thu_kho_volume.py`: 37 đạt. Chữ ký 5 hàm Files API dùng trong script khớp SDK 0.117.0. Thử 27 mutation trên bản sao: 20 bị test bắt, 7 sống sót.

**R1 (phải sửa) — có thể không dọn được thư mục con.** `allowed()` loại mọi đường dẫn có phần rỗng, nên `.../v1/` bị từ chối. Client giả luôn trả thư mục không có `/` cuối. API thật chưa rõ: tài liệu không nói về đường dẫn trong phản hồi, nhưng ví dụ đường dẫn thư mục ở request có `/` cuối, và `KhoVolume.liet_ke` đã `rstrip('/')`. Claude cho client giả trả `/` cuối thì V1–V6 vẫn đạt, mã thoát 0, nhưng còn 9 file và 10 thư mục của lượt thử trên Volume.
- Sửa: với mục `is_directory`, bỏ **đúng một** `/` cuối trước khi kiểm `allowed()` và trước khi gọi API. `//` hay `/../` vẫn phải bị từ chối. Không nới cho mục là file.
- Test: chạy các ca dọn ở §3.1 với cả hai dạng thư mục (có và không có `/` cuối); dạng nào cũng không còn gì của lượt.

**R2 (phải sửa, Claude bổ sung vào §3.1) — trượt mà không biết vì sao.** Script nuốt exception rồi chỉ in `V1: TRƯỢT`. Mục đích của script là biết sớm quyền Volume có đúng không, nên PM cần phân biệt được thiếu quyền với lỗi khác.
- Sửa: khi mã trượt do exception, in `V1: TRƯỢT (<tên loại lỗi>)`, ví dụ `PermissionDenied`. Chỉ in tên loại, không in nội dung lỗi. Trượt do so sánh sai thì giữ `V1: TRƯỢT`.
- Test: fake ném `PermissionDenied(SECRET)` thì có tên loại, không có secret, mã thoát 1, vẫn dọn hết.

**R3 — Claude rút lại (2026-11-09), không làm.** Claude từng đề nghị thêm test cho 5 kiểm phụ. Đây là script thử dùng vài lần, chính lượt chạy thật mới là phép kiểm V1–V6, nên không đáng thêm một vòng sửa. Chỉ sửa R1, R2 và test của hai mục đó; Claude rà nhanh rồi PM chạy thật.

**Không phải sửa, chỉ ghi nhận:** thử SDK thật với khóa giả và host `.invalid`, script im lặng hơn 110 giây (Claude dừng ở đó, chưa thấy mã thoát). Chỉ xảy ra khi host sai; đừng thêm tham số vào `WorkspaceClient`.

Báo cáo lại: kết quả test, và xác nhận chỉ sửa 2 file §3.1.

### Lượt 2 — §3.1 (2026-11-09): đạt, GPT làm tiếp từ §3.2

GPT sửa R1, R2 và làm cả R3 vì đọc phiếu trước khi Claude rút mục này. Claude giữ phần test thêm. Claude chạy lại 65 test đạt và đọc phần sửa R1, R2; không chạy lại mutation.

PM chạy thật trên `/Volumes/retail_lab/nhap_du_lieu/kho`:

| Danh tính | Kết quả | Ghi chú |
|---|---|---|
| `pipeline` | V1–V6 đạt, thoát 0, không cảnh báo dọn | Lần đầu thiếu quyền; PM cấp `USE SCHEMA` trên schema, `READ VOLUME`, `WRITE VOLUME` trên `kho` cho `retail-pipeline-writer` |
| `writer` | V1–V6 đạt, thoát 0, không cảnh báo dọn | Chạy bằng bản env tạm đã đổi tên khóa, xóa ngay sau khi chạy |

Sau lượt trượt đầu của `pipeline`, `thu_ket_noi` trống (PM kiểm bằng `databricks fs ls`, trước lần chạy `writer` cuối cùng). Lượt đó có `V6: TimeoutError`; sau khi cấp quyền không còn, nguyên nhân chưa kiểm riêng.

**Lưu ý cho PM:** `~/.retail-secrets/nhap_writer.env` dùng tên `DATABRICKS_CLIENT_ID/SECRET`. Khi đặt Streamlit Secrets phải dùng tên `RETAIL_NHAP_DBX_CLIENT_ID/SECRET`. Với `.env.airflow.local`, tên `RETAIL_PIPELINE_CLIENT_ID/SECRET` đã đúng.
