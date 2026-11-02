# Giao việc: script dọn bản dữ liệu cũ trên Databricks

Soạn ngày 2026-11-02. PM duyệt soạn phiếu cùng ngày. GPT code §3–§5; Claude rà độc lập trước khi commit, chưa đạt thì ghi §9 để GPT sửa.
Lệnh xóa thật do PM chạy (§6). Thiết kế gốc: `docs/thiet_ke_duong_tu_dong.md` §8.6 (nhánh `tu-dong/myuyen`).

Đọc trước: `AGENTS.md`, `CLAUDE.md`, `docs/agent_workflows.md`; skill `retail-platform-validation`; `scripts/pipeline/state.py`, `scripts/pipeline/runtime.py`,
`scripts/pipeline/cli.py` (`code_version` :30–40, `rollback` :536–563), `apps/retail_app/dwh/releases.py`.

## 0. Vì sao cần

- Mỗi lượt dựng thật tạo một bộ `r_<release_id>_{raw,staging,intermediate,marts,reporting,ops}`, khoảng 83 bảng, không ghi đè bộ cũ. Metastore giới hạn 500 bảng; P5 từng trượt vì
  `QUOTA_EXCEEDED`. Đã dọn tay 3 lần bằng script tạm.
- Ngày 2026-11-01 Claude đề xuất nhầm xóa `5d32a104…`, là đích rollback P8. Phát hiện kịp nhờ đọc lại phiếu lát 4, không nhờ cơ chế nào. Quy tắc giữ bản phải nằm trong code.
- Hiện registry còn `cfe19211…`, `b25b3e47…`, `ccde5a5e…` ở `ready` dù schema đã xóa.

## 1. Bẫy phải tránh: không được đổi `status`

`apps/retail_app/dwh/releases.py:116–122` (`allowed_versions`) duyệt **mọi** mục trong `releases` và gọi `choose` → `checked` (:23), mục nào `status != 'ready'` là **ném lỗi**. Hàm này chạy ở
guard của chat (`dwh/guarded.py:368, 372`) và `verify_consumers` (`cli.py:262`). Đổi một bản sang `status: 'da_xoa'` có thể **khóa mọi câu chat public và mọi lần publish**.

- **Cách đúng:** **xóa mục đó khỏi `releases`**, chép sang khóa mới `da_xoa` trong payload. Không đổi `status` của mục nào.
- **Thứ tự bắt buộc: xóa schema trước, sửa registry sau.** Guard coi quyền trên bản không có trong registry là quyền thừa (`guarded.py:352–355`). Sửa registry trước mà schema còn thì tài khoản đọc còn
  quyền trên schema "lạ", chat có thể bị khóa. Nếu dừng giữa hai bước, mục vẫn `ready`, schema đã mất: vô hại với bản không phải `active`, và chạy lại lệnh là hoàn tất.

## 2. Môi trường và ràng buộc

- Worktree `D:/retail-analytics-don`, nhánh `don-ban/myuyen` (Claude đã tạo từ `main` `eec292b`). Python `D:/retail-analytics/.venv/Scripts/python.exe`. **Không commit, không push.**
- **Không kết nối Databricks, không chạy script với cloud thật.** Test dùng đối tượng giả.
- **Chỉ tạo 2 file:** `scripts/ops/don_ban_cu.py` và `scripts/ops/tests/test_don_ban_cu.py`.
- **Không sửa gì khác.** `code_version` băm `scripts/pipeline`, `scripts/ingest`, `apps/retail_app`, `retail_dbt/…`; sửa ở đó buộc phải dựng lại image và tốn thêm khoảng 83 bảng. `scripts/ops` nằm ngoài băm.
- Script **một file**, chạy được qua stdin trong container, vì image hiện không có file này:
  `python - <tham số>`. Được import `scripts.pipeline.runtime.Databricks`, `scripts.pipeline.state.Registry`, `writer_lock`; không import `apps/retail_app`.
- Không in `DATABRICKS_*`, token, hay payload đầy đủ.

## 3. Thiết kế

### 3.1 Dòng lệnh

```text
python - --root warehouse/pipeline/docker --catalog retail_lab                                  # mặc định: chỉ đọc, in báo cáo
python - --root … --catalog retail_lab --dat-dich-rollback <rid 24 hex>                         # ghi đích rollback vào registry
python - --root … --catalog retail_lab --xoa <rid 24 hex> [--xoa <rid>] --thuc-hien              # xóa thật
```

- `--catalog` bắt buộc và phải bằng `Databricks().catalog`; khác thì dừng, để không nhầm catalog demo với `retail_lab`.
- `--xoa` không kèm `--thuc-hien`: in kế hoạch, không ghi gì. Mã bản phải đủ 24 ký tự hex, không nhận tiền tố, không nhận "tất cả". **Script không bao giờ tự chọn bản để xóa.**
- Mã thoát: 0 đạt; 2 bị quy tắc giữ bản chặn; 1 lỗi khác.

### 3.2 Báo cáo chỉ đọc

Một dòng mỗi bộ: `rid`, vai trò, số bảng, số view, `snapshot_id`, `code_version` (8 ký tự), `run_id`, có xóa được không và lý do. Vai trò ∈ `active`, `dich_rollback`, `dang_do`, `ready` (trong registry, còn schema),
`mo_coi` (có schema, không có trong registry), `mat_schema` (trong registry, không còn schema).

Cuối báo cáo: tổng bảng theo catalog; quota nếu đọc được (`resource_quotas.get_quota('METASTORE', <metastore>, 'table-quota')`, không đọc được thì in "không đọc được quota" và chạy tiếp, đừng dừng);
số chỗ còn lại; cảnh báo khi còn dưới 100 chỗ. Nhắc: bảng đã xóa có thể còn được tính một thời gian.

Cảnh báo nếu `code_version` của đích rollback khác `code_version` của `active`: rollback về đó khiến lịch 08:00 dựng và publish bản mới (phiếu lát 4 P8).

### 3.3 Đích rollback

- Lưu ở `payload['dich_rollback'] = {'release_id', 'dat_luc'}`, ghi qua `Registry.save` (compare-and-swap, `state.py:75–85`).
- `--dat-dich-rollback`: bản phải có trong `releases`, `status == 'ready'`, đủ schema trong catalog, và khác `active`.
- Chưa đặt đích, hoặc đích không còn hợp lệ: `--thuc-hien` **bị từ chối** (mã 2).

### 3.4 Quy tắc giữ bản (kiểm ngay trong lần chạy, sau khi giữ khóa)

`--thuc-hien` từ chối, không xóa bản nào trong lệnh, nếu **bất kỳ** điều nào đúng:

| # | Điều kiện |
|---|---|
| G1 | bản là `active`, hoặc `active` rỗng hay không có trong `releases` |
| G2 | bản là `dich_rollback`, hoặc chưa có đích hợp lệ |
| G3 | sau khi xóa, `active` hoặc đích rollback không còn đủ schema |
| G4 | có file `runs/*/context.json` chưa kết thúc (`stage` khác `skipped`, `published`, `validated`) mà `started_at` trong vòng 2 giờ: một lượt có thể đang chạy giữa hai stage, vì `writer.lock` chỉ giữ từng stage (`dagrun_timeout` 2 giờ, `deploy/airflow/dags/retail_batch_pipeline.py:42`) |
| G5 | bản được context chưa kết thúc tham chiếu (lượt có thể chạy tiếp, như P5 từng đợi quota), trừ khi thêm `--cho-xoa-ban-do <rid>` đúng mã đó |
| G6 | có view ngoài bộ trỏ vào bộ cần xóa (`information_schema.views`, tìm chuỗi `r_<rid>_` trong `view_definition`) |
| G7 | không lấy được `writer_lock(root)`: có lượt đang ghi |

Tên schema phải khớp đúng `^r_<rid>_(raw|staging|intermediate|marts|reporting|ops)$`. Không có `drop` nào với tên khác. Không bao giờ đụng `retail_control`, `pipeline_landing`, `default`, `information_schema`.

### 3.5 Trình tự `--thuc-hien`

1. Giữ `writer_lock(root)` suốt lệnh. Đọc registry mới nhất rồi kiểm §3.4; đọc trước khi lấy khóa không có giá trị.
2. Với từng bản: `drop schema if exists <catalog>.<schema> cascade`, rồi đọc lại xác nhận không còn schema nào của bản đó. Còn thì dừng, không sửa registry của bản đó.
3. Sau khi mọi schema đã mất: một lần `Registry.save`, bỏ các mục khỏi `releases`, thêm vào `payload['da_xoa']` (giữ `release_id`, `snapshot_id`, `code_version`, `run_id`, `schema`, thêm `xoa_luc`). Trước khi ghi, chạy kiểm: payload mới, mọi mục `releases` đều `status == 'ready'` và có `active`.
4. Bị writer khác đổi registry (`RuntimeError` của `save`): đọc lại và thử lại một lần, không ghi đè.
5. Chạy lại lệnh sau khi dừng giữa chừng phải hoàn tất được: `mat_schema` được phép `--xoa`; bản đã ở `da_xoa` báo "đã xóa trước đó", mã 0.
6. In kết quả và lệnh `UNDROP` gợi ý. Registry không tự khôi phục.

Không xóa file trong `pipeline_landing` hay `warehouse/pipeline/docker/runs/`: ngoài phạm vi, không tính quota bảng.

## 4. Yêu cầu theo file

| File | Việc |
|---|---|
| `scripts/ops/don_ban_cu.py` (mới) | §3; tách phần quyết định thành hàm thuần (nhận trạng thái, trả kế hoạch hoặc lý do chặn) |
| `scripts/ops/tests/test_don_ban_cu.py` (mới) | §5 |

## 5. Kiểm

Cloud giả (ghi lại mọi câu SQL) và `Registry` thật trên thư mục tạm (`sql=None`), không cần Databricks:
- **Chỉ đọc:** không có `--thuc-hien` thì không có câu `drop` nào và registry không đổi.
- **Từng quy tắc G1–G7:** mỗi quy tắc một test ra mã 2, không có câu `drop`, registry không đổi. Trong lệnh có cả bản hợp lệ lẫn bản bị chặn thì không xóa bản nào.
- **Mã bản:** tiền tố, sai độ dài, chữ hoa bị từ chối; sai `--catalog` bị từ chối.
- **Đúng tên:** với danh sách schema có `r_<rid>_reporting_tmp`, `r_<rid>x_raw`, `retail_control`, chỉ 6 tên đúng mẫu bị `drop`.
- **Thứ tự:** mọi câu `drop` xảy ra trước `Registry.save`. Giả lập `drop` lỗi ở bước giữa thì registry không đổi; chạy lại thì hoàn tất.
- **Hợp đồng với app (quan trọng nhất):** nạp `apps/retail_app/dwh/releases.py` trong **test**, gọi `allowed_versions(payload_sau_khi_xoa, ...)` và `choose(payload)` trên payload sau khi xóa: không ném lỗi; `da_xoa` và `dich_rollback` không ảnh hưởng kết quả; bản đã xóa không còn trong tập cho phép.
- **Payload thật:** dựng payload có đủ 6 khóa như registry hiện tại (`active`, `active_since`, `releases`…), xác nhận các khóa khác còn nguyên.
- **Compare-and-swap:** registry đổi giữa chừng → thử lại đúng một lần, không ghi đè; đổi lần nữa → mã 1.
- **Không đổi `code_version`:** `git diff --name-only origin/main...HEAD` rỗng và `git status --short` chỉ có 2 file của phiếu cộng chính phiếu. So với `origin/main`, vì `main` local có thể cũ (sửa 2026-11-02).
- **Thử vô hiệu (mutation), công cụ để thư mục tạm:** bỏ G1; bỏ G2; đảo thứ tự drop và save; đổi `status` thay vì xóa mục; nới mẫu tên schema; ghi test nào trượt.

## 6. Chạy thật (PM chạy, sau khi Claude rà đạt)

Từ PowerShell ở `D:\retail-analytics-don`. Không dựng lại image. Hai dòng đặt encoding là bắt buộc: Claude thử ngày 2026-11-02, thiếu chúng thì chữ Việt ra `cÃ³ thá»ƒ xÃ³a`.

```powershell
$OutputEncoding = New-Object Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
function don { Get-Content scripts\ops\don_ban_cu.py -Raw -Encoding UTF8 | docker exec -i -w /opt/retail -e PYTHONPATH=/opt/retail -e PYTHONIOENCODING=utf-8 retail-analytics-airflow-scheduler-1 /opt/pipeline/bin/python - --root warehouse/pipeline/docker --catalog retail_lab @args }
```

1. `don`: báo cáo chỉ đọc. Kỳ vọng: `dbb80f56` `active`; `5d32a104`, `03ad08c0` `ready`; `cfe19211`, `b25b3e47`, `ccde5a5e` `mat_schema`. Gửi Claude rà.
2. `don --dat-dich-rollback 5d32a10432ad4e338975a23a`. `don` lại thấy `dich_rollback`.
3. `don --xoa ccde5a5e21c54e9e9054066f`: kế hoạch, không ghi. Chạy thêm với `--thuc-hien` cho từng trong 3 bản `mat_schema`; đây là lần chạy đầu, chỉ sửa registry, không xóa bảng nào.
4. Mở web public: trang PS và một câu chat vẫn bình thường. Nếu lỗi, dừng và báo Claude.
5. Thử chặn: `don --xoa dbb80f5674af47fe9c98f796 --thuc-hien` và `don --xoa 5d32a10432ad4e338975a23a --thuc-hien`: cả hai phải ra mã 2, không xóa gì.
6. **`03ad08c0` chưa xóa ở phiếu này.** PM quyết sau khi lịch 08:00 chạy ổn vài ngày.

## 7. Báo cáo của GPT khi xong (PM dán cho Claude rà)

- Danh sách file; số đạt/trượt/skip của §5; kết quả từng mutation (sửa gì, test nào trượt).
- Xác nhận không kết nối Databricks; `git status` và `git diff --name-only main`.
- Đoạn in mẫu của báo cáo với dữ liệu giả; chỗ làm khác phiếu và vì sao.

## 8. Không giao GPT

§6, commit, push, PR. Không sửa `docs/phan_quyen.md`.

## 9. Rà của Claude (Claude ghi, GPT đọc để sửa)

**Lượt 1, 2026-11-02: Chưa đạt, sửa nhẹ.** Logic xóa đúng phiếu, Claude chưa thấy lỗi làm mất dữ liệu; nhưng đây là script xóa thật, nên test phải bắt được từng quy tắc trước khi PM chạy.

Claude đã kiểm: chạy lại 33 test đều đạt; đọc `state.py`, `runtime.py`; đọc 22 `context.json` thật (có `started_at`, `release_id`; 2 context chưa kết thúc đều cũ và không tham chiếu 3 bản `mat_schema`); `publish` giữ khóa lạ trong payload nên `da_xoa`, `dich_rollback` không mất. Thử vô hiệu trên bản sao 25 đột biến: 18 bị bắt, 7 lọt. `check_truoc_save` và `check_truoc_drop` lọt vì hai kiểm thay nhau đỡ, không tính là lỗi.

Lệch GPT báo về "104 commit" **không phải lỗi của GPT**: `main` local cũ. `git rev-list --count origin/main..HEAD` = 0, phiếu §5 đã sửa cách kiểm.

| Mã | Mức | Phát hiện | Việc cho GPT |
|---|---|---|---|
| D1 | Trung bình | `test_catalog_sai_bi_tu_choi` đạt vì **lý do khác**: bỏ hẳn kiểm catalog ở `main` (`don_ban_cu.py:333`) test vẫn đạt, vì `Registry` thật gọi cloud giả rồi lỗi, cũng ra mã 1. Đây là lớp chặn nhầm catalog demo với `retail_lab` | Truyền `registry_factory` chạy được; kiểm lỗi đúng là do catalog, ví dụ theo thông báo ở D2 và cloud không nhận câu SQL nào |
| D2 | Trung bình | `main` nuốt thông báo của chính script (`:376–379`): nhập sai mã hay sai catalog chỉ in `Lỗi: ValueError`, PM không biết sửa gì | Lỗi đầu vào do script tự kiểm (tên lớp riêng) in nguyên thông báo, mã 1. Lỗi từ driver/SDK giữ nguyên cách chỉ in tên lớp. Thêm test |
| D3 | Trung bình | Không test `--cho-xoa-ban-do` chỉ có tác dụng với **đúng mã**: đổi `rid not in overrides` thành `not overrides` vẫn đạt | Thêm test: hai bản dở, cho phép một mã, bản kia vẫn bị G5 chặn, không có `drop` |
| D4 | Trung bình | Không test xác nhận sau DROP (`:262–263`): bỏ kiểm vẫn đạt. Phiếu §3.5 bước 2 đòi còn schema thì không sửa registry | Thêm test: cloud giả giữ lại schema sau `drop` → mã 1, registry không đổi |
| D5 | Trung bình | Không test kiểm lại khi thử ghi lần hai (`:270–273`): bỏ kiểm vẫn đạt | Thêm test: registry đổi giữa chừng, bản mới làm một quy tắc giữ bản trúng (ví dụ `active` thành bản khác thiếu schema) → mã 2, không ghi đè |
| D6 | Trung bình | Không test `started_at` hỏng hoặc thiếu (`:71–74`): sửa thành bỏ qua vẫn đạt | Thêm test: context chưa kết thúc có `started_at` thiếu và sai dạng → G4 chặn |
| D7 | Thấp | Lệch phiếu: `mutation_probe` và `DON_MUTATION` nằm trong file test giao nộp (`test_don_ban_cu.py:19–50`). Phiếu §5 yêu cầu công cụ thử vô hiệu để thư mục tạm | Bỏ khỏi file test |
| D8 | Thấp | `:69–70` đọc giờ không múi giờ theo giờ máy. `cli.py:393` ghi UTC dạng `%Y-%m-%d %H:%M:%S`. Container đang UTC nên hiện đúng, đổi `TZ` sẽ làm G4 lệch | Coi giờ không múi là UTC; test với đúng định dạng đó |
| D9 | Thấp | Gợi ý khôi phục (`:286–288`) nói như chắc chắn làm được, chỉ nêu schema `_raw`. Chưa ai thử `UNDROP` sau `DROP SCHEMA CASCADE` | Thêm vào câu in: "chưa kiểm chứng, hỏi DE trước khi làm"; nêu rõ phải làm cho từng schema |

Sửa xong báo lại số test và không commit. Claude sẽ chạy lại đúng bộ thử vô hiệu trên.

**Lượt 2, 2026-11-02: Đạt.** D1–D9 đã sửa đúng §9. Claude chạy lại: 41 test đạt, 0 trượt, 0 skip; `git status` chỉ có 2 file code và phiếu. Bộ thử vô hiệu cũ trên bản sao: 23/25 bị bắt, gồm cả 5 chỗ lọt ở lượt 1; 2 chỗ còn lại (`checked_payload` trước DROP và trước save) đỡ lẫn nhau, không phải thiếu test. Đột biến "nuốt lỗi CAS lần hai" viết lại cho đúng cú pháp cũng bị bắt.

Giới hạn: mọi test dùng cloud giả. Câu SQL thật trên Databricks mới được kiểm ở §6 bước 1. Gợi ý `UNDROP` chưa ai thử.

**Chạy thật §6, 2026-11-02 (PM chạy, Claude đọc ảnh chụp): ĐẠT bước 1–5.**

- Bước 1: đúng vai trò kỳ vọng; 172 bảng trong catalog khớp 56 + 56 + 58 + 2 của `retail_control`. "Không đọc được quota" với tài khoản writer, chưa rõ lý do vì script không in; không chặn việc dọn, kiểm quota bằng profile `retail-dev`.
- Bước 2: đích rollback = `5d32a10432ad4e338975a23a`, không có cảnh báo lệch `code_version`.
- Bước 3: bỏ `b25b3e47…`, `ccde5a5e…`, `cfe19211…` khỏi `releases` trong một lệnh (phiếu viết "từng bản", script nhận nhiều `--xoa` nên gộp). Mã thoát 0; không có bảng nào bị xóa, tổng bảng vẫn 172. Registry còn `03ad08c0…`, `5d32a104…`, `dbb80f56…`.
- Bước 4: chat web public trả đúng G 2022 = 1.169.748.832 VND sau khi sửa registry; trang PS1 kỳ 2012–2022 hiện G 16,43 tỷ, R 12,52 tỷ, R/G 76,2%, khớp số khóa `assert_rpt_total.sql`.
- Bước 5: xóa `dbb80f56…` ra "G1: yêu cầu xóa active", xóa `5d32a104…` ra "G2: yêu cầu xóa đích rollback", cả hai mã 2, không có dòng `Đã dọn`.

Chưa kiểm: lịch 08:00 chạy trên registry mới (kế tiếp 2026-11-03). Bước 6: `03ad08c0…` vẫn giữ, PM quyết sau.
