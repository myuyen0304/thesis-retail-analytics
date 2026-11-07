# Giao việc D5a: công bố bản có đợt lên dashboard (hai con trỏ), băng rôn, `run` và DAG nạp đợt

Soạn ngày 2026-11-06. **PM chốt §12 ngày 2026-11-06: theo cả 6 đề xuất. Sẵn sàng giao GPT:** §12 mục 2 đã xong. Phiếu "hiển thị sau rollback" PM đã thử đạt, đã commit và gộp vào nhánh này ở `610123b`. GPT code; Claude rà và tự kiểm độc lập trước khi commit, chưa đạt thì ghi §11 để GPT sửa.

**Thiết kế gốc là B′, không phải bản `thiet_ke_nap_ky_moi.md` trong worktree này.** Bản trong worktree còn ghi catalog demo riêng và ẩn chat, đã bị thay. Đọc bản mới nhất bằng:

```text
git show docs/thiet-ke-b-tam-thoi:docs/thiet_ke_nap_ky_moi.md
```

Đọc các mục B′ ở §0, dòng "Đọc lại khi soạn D5" ở §4.6, và §5 mục 3–5. Phiếu này đã chép đủ luật cần làm.

Đọc trước: `AGENTS.md`, `CLAUDE.md` §1, §5, `docs/agent_workflows.md`, `docs/giao_viec_dbt_ky_dong_d3.md` §5 và §9, `scripts/pipeline/cli.py`, `scripts/pipeline/state.py`, `apps/retail_app/dwh/releases.py`.

## 0. Vì sao cần

D3 dựng được bản có đợt 2023 tổng hợp tới `validate`, nhưng `publish` và `rollback` về bản đó bị chặn (`cli.py:432`, `cli.py:597`). Lệnh `run`, app và DAG cũng chưa chạy được đợt:

- `--dot` chỉ nhận ở `prepare`, `--du-bao-tu` chỉ nhận ở `forecast` (`cli.py:569–572`, `cli.py:336–339`);
- `run` truyền cùng tham số cho mọi stage, kể cả `publish` (`cli.py:614–616`).

**B′, PM chốt 2026-11-04:**

- Registry có thêm một **con trỏ dashboard**. Admin công bố bản có đợt thì chỉ đổi con trỏ này; `active` vẫn là bản số thật.
- Lịch 08:00 chỉ ghi `active` (`state.py:113`), nên không cần dừng DAG.
- Demo xong, Admin trả con trỏ dashboard về `active`.
- Chat luôn đọc `active`.

**Yêu cầu quan trọng nhất: không có đợt và registry không có con trỏ dashboard thì mọi thứ y hệt hôm nay.** Điều này gồm lệnh của DAG lịch 08:00, `--vars` của dbt, các trang đọc `state.json` và bản public.

## 1. Phạm vi

**Làm (D5a):**

1. Con trỏ dashboard trong registry, cho cả `state.json` và dòng `retail_control.state` (§3).
2. CLI (§4):
   - `run` chạy được đợt và dừng ở `validate`;
   - `publish` bản có đợt chỉ đổi con trỏ dashboard và cần cờ xác nhận;
   - thêm lệnh trả con trỏ về `active`.
3. Cờ tổng hợp trong bản ghi registry, và băng rôn "Dữ liệu tổng hợp – chỉ để demo" trên mọi trang đọc bản có cờ (§5).
4. Trong app (§6):
   - trang dashboard đọc con trỏ dashboard; chat và trang Dự báo đọc `active`;
   - khung "AI diễn giải" ẩn khi hai con trỏ khác nhau;
   - sửa nhãn kỳ ở Tổng quan và PS1;
   - Admin có nút đưa bản có đợt lên dashboard và nút trả về.
5. DAG nạp đợt **mới, riêng**: không lịch, không có task công bố, chỉ chạy `duckdb` (§7).

**Không làm:**

- **D5b, trang Gửi/Duyệt loại "đợt"** (gửi nhiều file một lần, runner tự chạy `--dot` và `--du-bao-tu`): chờ PM chốt ở §12 mục 1.
- Không sửa `deploy/airflow/dags/retail_batch_pipeline.py`. DAG này đang chạy production (UNPAUSED, `orders_enriched`).
- Không chạy được đợt trên Databricks: cổng `target == 'databricks'` ở `cli.py:432` giữ nguyên. Lên Databricks là bước sau D5.
- Không mở rollback `active` về bản có đợt: chặn ở `cli.py:597` giữ nguyên, kể cả sau D5.
- Không sửa:
  - `scripts/forecast/*`, `scripts/ingest/dot.py`, `scripts/ingest/source_contract.py`, `scripts/ingest/extensions/*.yml`;
  - `retail_dbt/`, seed;
  - `apps/retail_app/ai_explain/` ngoài chỗ chọn bản ở §6.2;
  - `CLAUDE.md`, `docs/phan_quyen.md`.
- Không kết nối Databricks, Neon hay Airflow thật; không khởi động lại container; không dựng image.
- Không sửa số khóa để test xanh.

## 2. Môi trường và ràng buộc

- Worktree `D:/retail-analytics-nap`, nhánh `nap-ky/myuyen`, HEAD `610123b`: đã có D3 và phiếu hiển thị sau rollback. Khối Rollback trên trang Duyệt đã tự chạy lại trang và bỏ tick sau khi rollback; giữ hành vi này cho các nút mới ở §6.3. Python `D:/retail-analytics/.venv/Scripts/python.exe`. **Không commit, không push.**
- Worktree không có `data/`. `data_demo/` không vào git.
- Laptop ít RAM. GPT chỉ chạy các test ở §9; **không chạy lượt pipeline thật** (PM chạy theo script của Claude). Bị dừng vì thiếu RAM thì báo, không tự chạy lại.
- Không in tên, số điện thoại, tuổi, giới tính nhân viên hay shipper ra log, thông báo lỗi hay giao diện.
- Code đổi `scripts/pipeline` và `apps/retail_app`, nên `code_version` đổi. Khi gộp lên nhánh public phải theo quy tắc đóng băng image. Đó là việc của PM sau D5, không làm ở phiếu này.

## 3. Registry: con trỏ dashboard

Payload hiện có `active`, `active_since`, `releases` (`state.py:104–118`). Thêm hai khóa:

| Khóa | Ý nghĩa |
|---|---|
| `dashboard` | `release_id` mà các trang dashboard đọc. **Không có khóa, hoặc giá trị `null`, nghĩa là "theo `active`".** |
| `dashboard_since` | `{'release_id', 'at'}`, giống `active_since` |

**Luật:**

1. Chỉ bản `ready` **có cờ tổng hợp** (§5.1) được đặt vào `dashboard`, để con trỏ này không thành đường rollback thứ hai cho bản số thật.
2. Ghi con trỏ dùng đúng cơ chế kiểm `version` của `save()` (`state.py:83–93`), cả local lẫn Databricks. Hàm mới nhận `expected`, giống `publish(rid, expected)`.
3. Trả về `active` thì **xóa khóa** `dashboard` và `dashboard_since`, không ghi `null`. Nhờ vậy payload sau khi trả về trùng dạng payload chưa từng có con trỏ.
4. `publish()` và rollback **giữ nguyên** hai khóa này. Lịch 08:00 công bố bản mới thì dashboard vẫn ở bản có đợt cho tới khi Admin trả về. Có test.
5. `register()` không đổi.

## 4. CLI

### 4.1 `run` với đợt

- Argparse: `--dot` nhận ở `prepare` và `run`; `--du-bao-tu` nhận ở `forecast` và `run`.
- `run --dot`: phải có `--du-bao-tu`, kiểm **trước** khi chạy `prepare` để không mất khoảng 90 giây rồi mới báo lỗi.
- Truyền tham số theo stage: `--dot` chỉ vào `prepare`, `--du-bao-tu` chỉ vào `forecast`. Hai cổng trong `_execute` (`cli.py:336–339`) giữ nguyên.
- Snapshot có đợt thì `run` **dừng sau `validate`** và in một dòng: bản đã qua kiểm, Admin công bố bằng `publish --xac-nhan-tong-hop`. Exit 0.
- `run` không đợt: y hệt hiện nay, gồm cả `publish`.

### 4.2 `publish` bản có đợt

- Bỏ `stage == 'publish'` khỏi điều kiện chặn ở `cli.py:432`. **Giữ `target == 'databricks'`.**
- Snapshot có đợt:
  - không có cờ `--xac-nhan-tong-hop` thì exit 2, thông báo nói rõ cần cờ này và chỉ Admin dùng;
  - có cờ thì ghi con trỏ `dashboard`, **không đụng `active`**, stage thành `published_dashboard`.
- Context của bản có đợt không bao giờ có `stage == 'published'`.
- Snapshot không đợt mà có cờ: exit 2 ("cờ chỉ dùng cho bản có đợt").
- Mỗi lần công bố ghi một dòng `history.jsonl`, phân biệt được với công bố `active`, ví dụ `stage: 'publish_dashboard'`.

### 4.3 Lệnh trả con trỏ

- Thêm lệnh, tên đề xuất `tra-dashboard`, cần `--run-id`. Lệnh xóa con trỏ theo §3 luật 3 và ghi một dòng lịch sử.
- Chạy khi không có con trỏ: kết quả `bo_qua`, exit 0, payload không đổi.
- Không đọc `--release-id`.

### 4.4 Rollback

Chặn ở `cli.py:597` giữ nguyên. Rollback `active` không đụng `dashboard`.

## 5. Cờ tổng hợp và băng rôn

### 5.1 Nguồn cờ

App public đọc Databricks nên không đọc được `manifest.json` hay `context.json` local. **Đề xuất (§12 mục 4):** khi `validate` đăng ký bản (`cli.py:480–483`), context có `dot` thì thêm `record['co_du_lieu_tong_hop'] = True`. Bản không đợt **không có khóa này**, nên bản ghi của chúng giữ nguyên từng byte như hôm nay.

Vì sao không đặt cờ trong dbt: thêm cột vào `rpt_build_info` làm đổi SQL biên dịch khi không có đợt, trái yêu cầu của D3.

### 5.2 Băng rôn

- Bản app đang đọc có `co_du_lieu_tong_hop` thì **mọi trang** hiện băng rôn cố định "Dữ liệu tổng hợp – chỉ để demo" ở đầu trang, gồm Tổng quan, PS1–PS5 và Sức khỏe dữ liệu.
- Đặt ở một chỗ dùng chung, `page_header` hoặc `sidebar` trong `ui/common.py`, không chép vào từng trang.
- Không có cờ: không có phần tử nào mới trên trang.

## 6. App

### 6.1 Chọn bản cho từng loại trang

| Trang | Đọc |
|---|---|
| Tổng quan, PS1–PS5, Sức khỏe dữ liệu | `dashboard` nếu có, ngược lại `active` |
| Dự báo | `active`. Trang này tự đứng yên, nên không phải đổi gì khác. |
| Chat (trang AI và mọi lượt gọi tool) | `active`, **kể cả khi gọi từ trang đang đọc bản có đợt** |

**Chỗ phải sửa:**

- `releases.resolve` (`dwh/releases.py:79–95`) và `choose` (`:33–40`) nhận thêm con trỏ cần đọc.
- Chat lấy bản từ pin của trang: `releases.current()` ở `ai_explain/tools.py:109, 123` và `dwh/guarded.py:362`. Phải cho chat tự resolve `active` trong scope riêng, không dùng pin của trang. Pin của trang cũng không được bị đổi sau lượt chat.
- Registry không có khóa `dashboard`: mọi trang đọc `active` như hôm nay.

**Khi hai con trỏ khác nhau:**

- khung "AI diễn giải" trên trang PS ẩn: thêm một điều kiện vào `ai_unavailable` (`ui/ai_panel.py`), có lý do rõ;
- trang chat ghi một dòng: đang dùng bản số thật, số tới ngày nào (`data_end_date` của `active`), không dùng số tổng hợp trên dashboard.

Cache `load` đã có `release_id` trong khóa (`ui/common.py:44–57`), nên đổi con trỏ không làm lẫn số. Vẫn phải có test cho điều này.

### 6.2 Nhãn kỳ trên bản có đợt

Bản có đợt có 3 dòng `rpt_revenue_total`: `2012-2022` (không phải kỳ phân tích), `2013-2022` (không phải kỳ phân tích) và `2013-2023` (kỳ phân tích).

- **`tong_quan.py:12`** lấy `.iloc[0]` của các dòng không phải kỳ phân tích. Có hai dòng như vậy, nên kết quả phụ thuộc thứ tự dòng. Sửa thành lấy theo mã `'2012-2022'`: đây là số deck slide 4, không đổi.
- **`tong_quan.py:15–18`** in thẻ cho mọi dòng. Dòng `2013-2022` sẽ mang nhãn "toàn bộ dữ liệu", **sai**. Đề xuất (§12 mục 3): trên bản có đợt, nhãn dòng này là "kỳ gốc, số thật".
- **PS1 `period_label`** (`ui/common.py:254–259`) gặp lỗi cùng loại. Dòng `2013-2022` ra "2013–2022 (toàn bộ dữ liệu)". Sửa cùng luật.
- Rà mọi trang PS bằng AppTest trên kho có đợt. Không còn chữ "2013–2022" nào ngầm hiểu là kỳ phân tích. Câu chữ của trang Dự báo và trang AI giữ nguyên, vì hai trang đó đọc `active`.

### 6.3 Nút của Admin trên trang Duyệt dữ liệu

Đặt cạnh khối rollback (`views/duyet_du_lieu.py:248–261`). Chỉ hiện khi vai trò là `admin`.

- **"Đưa bản có đợt lên dashboard (demo)":**
  - danh sách lấy từ registry: bản `ready` có cờ tổng hợp;
  - phải tick ô xác nhận "Đây là dữ liệu tổng hợp, chỉ để demo";
  - gọi CLI `publish --xac-nhan-tong-hop` bằng subprocess, theo mẫu `rollback_command` (`ui/nhap_runner.py:585–592`).
- **"Trả dashboard về bản số thật":** gọi lệnh ở §4.3. Chỉ hiện khi đang có con trỏ.
- `rollback_options` và `rollback_details` (`ui/nhap_runner.py:596–616`) phải **loại bản có cờ tổng hợp**. Hiện các bản này lọt vào danh sách rollback rồi bị CLI chặn với lỗi, trải nghiệm xấu.
- Ghi nhật ký giống rollback, theo cơ chế `audit` sẵn có.

Runner không bao giờ tự đổi con trỏ dashboard. Không thêm đường nào cho lượt tự động gọi `--xac-nhan-tong-hop`.

**Root của hai nút mới (trả lời GPT 2026-11-06):** hai nút phải tác động đúng registry mà các trang dashboard đang đọc.

- Root lấy từ thư mục cha của `RETAIL_RELEASE_STATE`, resolve trong repo. Mặc định của biến này là `warehouse/pipeline/state.json` (`dwh/releases.py:29`). Root đó truyền vào `--root` của CLI.
- Khi lượt thật chạy bằng DAG nạp đợt, PM đặt `RETAIL_RELEASE_STATE=warehouse/pipeline/docker/state.json`.
- Luồng nhập và rollback hiện có **giữ nguyên** root `warehouse/pipeline/ui-nhap` (`ui/nhap_runner.py:20`, `ui/nhap_store.py:120`).
- Hai nút chỉ hiện khi app đang ở chế độ versioned, backend `duckdb`, và file state tồn tại. Thiếu điều kiện nào thì hiện một dòng nói lý do, không có nút.

**Cờ `--xac-nhan-tong-hop` không phải xác thực.** CLI không kiểm tài khoản app. Người gõ CLI trực tiếp là người vận hành được tin cậy, giống `publish` và `rollback` hiện nay. Mục đích của cờ là để không lượt tự động nào công bố nhầm bản có đợt.

"Chỉ Admin" được kiểm ở app, tại hai chỗ:
- lúc vẽ nút;
- trong hàm xử lý nút, trước khi gọi subprocess. Hàm đọc lại `roles.current_role()`, không dựa vào việc nút đã được vẽ.

Test phải có: vai trò khác Admin gọi thẳng hàm xử lý thì bị từ chối, không có subprocess nào chạy.

## 7. DAG nạp đợt riêng

Thêm file mới `deploy/airflow/dags/retail_dot_pipeline.py`. Dùng lại tối đa code của DAG cũ bằng import hoặc chép ít, **không sửa file cũ**.

- `schedule=None`, `is_paused_upon_creation=True`, `max_active_runs=1`, chỉ trigger tay.
- Params:
  - `dot`: tên thư mục con dưới `/opt/retail/data_demo`, pattern chặt, không có `/` hay `..`;
  - `du_bao_tu`: 24 hex, bắt buộc;
  - `force`.
- **Target cố định `duckdb`.** Không đọc `RETAIL_PIPELINE_DEFAULT_TARGET`, vì máy demo đặt biến này là `databricks`.
- Bốn task: `prepare --dot` → `forecast --du-bao-tu` → `build` → `validate`. **Không có task `publish`.** Root giống DAG cũ (`warehouse/pipeline/docker`), vì `--du-bao-tu` đọc bản gốc trong cùng root.
- `docker-compose.airflow.yml`: thêm mount `./data_demo:/opt/retail/data_demo:ro`. Chỉ sửa file, không khởi động lại container. PM khởi động lại sau khi gộp.
- Phần mở rộng: đợt hiện cần `orders_enriched` và `shipments_realistic` (`docs/giao_viec_dbt_ky_dong_d3.md` §8). Lấy từ param `extensions` như DAG cũ, mặc định rỗng. Ghi rõ trong mô tả DAG.

## 8. Không đợt thì y hệt (bắt buộc có test)

- `command()` của `retail_batch_pipeline.py` cho đúng danh sách tham số như trước, với mọi tổ hợp param hiện có. File này không đổi byte nào.
- `run` không đợt gọi đủ 5 stage với cùng tham số như trước.
- `state.json` không có khóa `dashboard`: `releases.resolve` trả cùng bản ghi như trước, ở cả trang lẫn chat.
- Bản ghi registry của bản không đợt không có `co_du_lieu_tong_hop`.
- Trang không có băng rôn, khung AI không ẩn thêm, nhãn kỳ Tổng quan và PS1 giữ chữ cũ trên bản không đợt.
- SQL dbt và `--vars` không đổi: D5 không sửa `retail_dbt/`. Test `test_d3_ky_dot.py::test_no_batch_sql_is_byte_identical` vẫn đạt.

## 9. Test bắt buộc và lệnh chạy

Test mới ở `scripts/pipeline/tests/test_d5_con_tro.py` và `apps/retail_app/tests/test_d5_dashboard.py`. Dùng registry và kho nhỏ tự dựng, không đọc dữ liệu thật.

- **T1. Registry:**
  - đặt con trỏ đạt với bản có cờ; từ chối bản không cờ và bản chưa `ready`;
  - `expected` sai thì từ chối, payload không đổi;
  - trả về thì xóa khóa;
  - `publish()` và rollback giữ con trỏ;
  - nhánh `sql` dùng một hàm `sql` giả, kiểm câu `update ... where version = ?`.
- **T2. `run`:**
  - `run --dot` thiếu `--du-bao-tu` lỗi trước khi gọi `prepare`;
  - tham số đi đúng stage;
  - có đợt dừng ở `validate`, không gọi `publish`;
  - không đợt gọi đủ 5 stage, tham số như cũ.
- **T3. `publish`:**
  - bản có đợt không cờ: exit 2, registry không đổi;
  - có cờ: chỉ `dashboard` đổi, `active` và `active_since` giữ nguyên;
  - bản không đợt có cờ: exit 2;
  - `target databricks` vẫn chặn;
  - dòng lịch sử đúng.
- **T4.** `tra-dashboard`: lần đầu đạt, lần hai `bo_qua`; rollback về bản có đợt vẫn bị chặn như D3.
- **T5.** Cờ `co_du_lieu_tong_hop` chỉ có ở bản ghi của bản có đợt.
- **T6. App, AppTest trên registry có hai con trỏ:**
  - Tổng quan và PS đọc schema của bản `dashboard`;
  - trang Dự báo đọc `active`;
  - băng rôn hiện;
  - khung AI ẩn kèm lý do;
  - trả con trỏ về thì mọi thứ như cũ.
- **T7. Chat:**
  - gọi tool trong lúc trang đã pin bản `dashboard`: mọi SQL trong `QueryRecord` dùng schema của `active`;
  - sau lượt chat, pin của trang vẫn là bản `dashboard`.
- **T8.** Nhãn kỳ: Tổng quan lấy số deck từ `'2012-2022'` bất kể thứ tự dòng; nhãn "kỳ gốc, số thật" chỉ có trên bản có đợt.
- **T9.** Trang Duyệt:
  - nút công bố chỉ hiện với Admin, cần tick xác nhận;
  - danh sách rollback không có bản có cờ;
  - lệnh subprocess đúng tham số.
- **T10. DAG mới:**
  - lệnh từng task đúng; không có task `publish`; target luôn `duckdb`;
  - `dot` có `..` hoặc `/` bị param từ chối.

  Theo mẫu `test_airflow_extensions.py`; không cần Airflow chạy thật.
- **T11.** Mọi mục ở §8.
- **T12. Đột biến tối thiểu:** mỗi luật dưới đây làm hỏng thử một lần, và test phải bắt được:
  - bỏ kiểm cờ ở §4.2;
  - cho `publish` bản có đợt ghi `active`;
  - chat dùng pin của trang;
  - DAG mới thêm `publish`;
  - rollback options không lọc bản có cờ.

  Ghi kết quả vào §11.

```text
python -m pytest scripts/pipeline/tests -q
python -m pytest scripts/ingest/tests -q
python -m pytest apps/retail_app/tests -q
```

Chạy từng lệnh riêng; không gộp `apps` với `scripts` vì trùng `conftest`.

**Worktree thiếu `data/`:** `nhap_kha_dung()` trả `False` (`ui/nhap_store.py:95–103`), các trang nhập dừng sớm, nên 19 test trang trượt dù code đúng. Claude đã kiểm ngày 2026-11-06 ở `610123b`.

Cách chạy đúng:

1. Tạm tạo junction tới data có sẵn, chỉ để đọc:
   ```text
   New-Item -ItemType Junction -Path data -Target D:\retail-analytics-am\data
   ```
2. Chạy test.
3. Gỡ junction:
   ```text
   cmd /c rmdir data
   ```
   **Không dùng `Remove-Item -Recurse`.**

Có junction thì bốn file `test_nhap_theo_doi`, `test_nhap_tu_dong`, `test_nhap_du_lieu`, `test_extension_grants` đạt 326/326. Sau D5a không được có ca trượt nào.

## 10. Nghiệm thu

**Claude tự kiểm, không dùng test của GPT làm bằng chứng duy nhất:**

1. Diff không chạm các file ở "Không làm" của §1. `retail_batch_pipeline.py` trùng byte với `20bce05`.
2. Đọc tay từng chỗ chọn bản trong `releases.py`, `guarded.py`, `tools.py`. Tìm mọi lời gọi `releases.current()` và `resolve()` mới, và xác nhận không lời gọi nào làm chat đọc bản có đợt.
3. Tự chạy lại đột biến T12 và thêm đột biến của riêng Claude.

**PM chạy theo script Claude viết, ngoài Claude Code, trên root `d3-thu`, có sẵn bản gốc `f6f64a3c…` của lượt D3.** Bản có đợt `0bce3b72…` của D3 **không dùng được** ở đây, vì hai lý do. Thứ nhất, bản ghi của nó không có cờ tổng hợp, do đăng ký trước D5. Thứ hai, `code_version` của nó là của code D3. Vì vậy phải dựng bản có đợt mới bằng code D5a. Từ lúc `validate` tới lúc `publish`, không được sửa file nào dưới `apps/retail_app/` hay `scripts/`, vì publish kiểm `code_version`.

1. `run --dot ... --du-bao-tu f6f64a3c8909485baf3d67ef` với run mới: dừng ở `validate`.
2. Thử công bố bản có đợt hai lần: không cờ thì bị chặn; có cờ thì `dashboard` đổi, `active` giữ nguyên.
3. Mở app versioned trỏ registry này:
   - Tổng quan và PS có năm 2023 và băng rôn;
   - trang Dự báo và chat theo bản số thật;
   - khung AI ẩn.

   Bạn chụp ảnh từng trang. **Không F5 khi đang chạy.**
4. Admin bấm "Trả dashboard về bản số thật": mọi trang về như cũ, không còn băng rôn.
5. Kiểm DAG mới bằng `airflow dags test` hoặc trigger tay trên Airflow local. Bước này chỉ làm khi PM chủ động và DAG production đã được tạm dừng, vì hai DAG dùng chung `writer.lock` và root `docker`.

## 11. Kết quả

(GPT ghi phần làm và lệch so với phiếu; Claude ghi phần rà.)

### GPT — D5a, ngày 2026-11-07

Đã triển khai D5a trên `nap-ky/myuyen`, nền `610123b`; chưa commit/push. **Bộ hồi quy app toàn phần chưa đạt**, không dùng kết quả test giả để kết luận nghiệm thu kho thật.

**File đã đổi/tạo:**

- `scripts/pipeline/state.py`: thêm đặt/xóa dashboard có kiểm version và expected; không cho bản tổng hợp vào active.
- `scripts/pipeline/cli.py`: run có đợt dừng ở validate; publish cần xác nhận và chỉ ghi dashboard; thêm tra-dashboard và lịch sử; giữ chặn rollback/Databricks cho bản có đợt.
- `scripts/pipeline/tests/test_d5_con_tro.py` (mới): 30 ca về registry, CLI, lịch sử, DAG và tương thích không đợt.
- `scripts/pipeline/tests/test_d3_du_bao.py`, `scripts/pipeline/tests/test_snapshot_dot.py`: đổi regex thông báo publish cũ sang yêu cầu cờ xác nhận của D5 (giải thích bên dưới).
- `apps/retail_app/dwh/releases.py`: chọn active/dashboard, ghim bản đọc, phạm vi chat riêng và khôi phục pin của trang.
- `apps/retail_app/dwh/guarded.py`, `apps/retail_app/ai_explain/tools.py`: phiên SQL/tool chat dùng active, giữ bản qua nhiều tool trong cùng lượt.
- `apps/retail_app/app.py`, `apps/retail_app/ui/common.py`: chọn con trỏ theo trang, băng rôn dùng chung, thông báo nguồn của chat và nhãn kỳ gốc.
- `apps/retail_app/ui/ai_panel.py`, `apps/retail_app/views/ai_explain.py`: ẩn khung AI trên dashboard đang khác active; trang chat vẫn hoạt động trên active.
- `apps/retail_app/views/tong_quan.py`: lấy kỳ deck bằng mã 2012-2022, không phụ thuộc thứ tự dòng.
- `apps/retail_app/ui/nhap_runner.py`, `apps/retail_app/views/duyet_du_lieu.py`: hai nút Admin, kiểm lại quyền trong handler, xác nhận, root đúng registry dashboard, rerun/bỏ tick sau thành công; lọc bản tổng hợp khỏi rollback.
- `apps/retail_app/tests/test_d5_dashboard.py` (mới): 29 ca trên kho DuckDB nhỏ tự dựng, AppTest và subprocess giả.
- `deploy/airflow/dags/retail_dot_pipeline.py` (mới): DAG trigger tay, bốn task, target duckdb, không publish; kiểm param và truyền extensions.
- `docker-compose.airflow.yml`: mount data_demo chỉ đọc; không chạy compose.
- `docs/giao_viec_d5_cong_bo_dot.md`: báo cáo này; giữ các quyết định PM đã ghi trong phiếu.

**Chỗ khác phiếu/kỳ vọng cũ và lý do:**

- Không mở rộng sang D5b. Không sửa các file bị cấm, không sửa số khóa, số liệu hay ngưỡng kỳ vọng để test xanh.
- Hai test D3/snapshot trước đây đòi thông báo “chưa dùng ... D5” khi publish bản có đợt. D5 mở đường publish có xác nhận nên thay regex bằng `--xac-nhan-tong-hop`; vẫn kiểm từ chối trường hợp không xác nhận, không bỏ ca chặn.
- T6: Tổng quan chạy AppTest trọn trang trên kho giả. PS1–PS5, Sức khỏe, Dự báo và chat được kiểm tại biên đọc `build_info`: schema/năm, băng rôn, rồi trả con trỏ và đọc lại active; test dừng trước phần metric ngoài fixture. Đây **không phải** bằng chứng toàn bộ biểu đồ PS đã render trên kho có đợt. Khung AI có test riêng xác nhận không nạp provider khi ẩn. Phần hiển thị đầy đủ trên kho thật vẫn cần nghiệm thu §10.

**Chi tiết xử lý và quyết định:**

- Root và quyền làm đúng câu trả lời PM ở cuối §6.3: root lấy từ cha của RETAIL_RELEASE_STATE; handler đọc lại current_role. Không đổi RequestStore.pipeline_state hoặc rollback_command.
- Con trỏ null theo active; lệnh trả về xóa cả hai khóa. Công bố lại bản đã published_dashboard vẫn cần xác nhận; có thể đưa bản đó trở lại sau khi đã trả dashboard về active.
- Chat nhiều tool giữ cùng active trong một lượt, ngay cả khi registry thay đổi giữa các tool; thoát lượt trả nguyên pin của trang. Đây là cách giữ tính nhất quán của lượt đọc.
- Không tự dựng kho thật để chữa các lỗi app phụ thuộc warehouse; giữ đúng lệnh cấm chạy pipeline thật.

**Kết quả kiểm thử (chạy riêng từng lệnh, Python venv đã chỉ định):**

| Lệnh | Đạt | Trượt/lỗi | Bỏ qua |
|---|---:|---:|---:|
| `python -m pytest scripts/pipeline/tests -q` | 286 | 0 | 2 |
| `python -m pytest scripts/ingest/tests -q` | 337 | 0 | 0 |
| `python -m pytest apps/retail_app/tests -q` | 800 | 628 | 604 |

Lệnh thực tế thêm `-B`, `--tb=short` và `--junitxml` để ghi bằng chứng; lượt app đặt `RETAIL_TEST_DATABRICKS=0`. Không gộp apps với scripts. Lượt app cuối mất 899,79 giây và pytest exit 1.

- Test mới D5: pipeline 30/30 và app 29/29 đạt (đã nằm trong tổng trên).
- Bốn file UI bắt buộc: test_nhap_theo_doi 61, test_nhap_tu_dong 151, test_nhap_du_lieu 97, test_extension_grants 17: **326 đạt, 0 trượt, 0 bỏ qua**.
- Hai skip pipeline: thiếu snapshot `5bd9a84aaf73` và chưa có bản pipeline publish. Test `test_no_batch_sql_is_byte_identical` nằm trong bộ pipeline đạt.
- App toàn phần có 628 ca trượt, tập trung ở các bộ AI/tools/trang BI phụ thuộc kho và số liệu. Worktree không có `warehouse/dbt.duckdb`; một số lỗi ghi rõ thiếu file hoặc query_error. **Chưa đối chiếu từng ca với HEAD, nên không khẳng định tất cả 628 lỗi là lỗi nền/môi trường.** Tập tên ca trượt trùng hoàn toàn lượt app trước sửa cuối (0 ca thêm, 0 ca bớt); đây không phải phép so với main/HEAD.
- Lượt app trước: 798 đạt, 628 trượt, 604 bỏ qua; lượt cuối tăng hai ca mới đạt. Không cộng các lượt chạy lặp vào tổng.
- Bằng chứng local: `%TEMP%/d5_pipeline.xml`, `d5_ingest.xml`, `d5_apps_final.xml`, `d5_apps_final.log`.

**T12 — đã thực sự gây đột biến và chạy test, 5/5 bị bắt:**

| Đột biến | Test bắt được | Kết quả khi làm hỏng |
|---|---|---|
| Bỏ kiểm cờ xác nhận ở publish | `test_t3_publish_confirmation_and_history` | 1 trượt, exit 1 |
| Publish bản có đợt ghi active | `test_t3_publish_confirmation_and_history` | 1 trượt, exit 1 |
| Chat kế thừa pin dashboard của trang | `test_t7_real_tool_sql_active_and_pin_restored` | 1 trượt, exit 1 |
| Thêm task publish vào DAG mới | `test_t10_dag_only_four_stages` | 1 trượt, exit 1 |
| Bỏ lọc bản tổng hợp khỏi rollback options | `test_t9_confirmation_commands_and_rollback_options` | 1 trượt, exit 1 |

Các ca trượt do assertion, không phải lỗi collection. Mỗi đột biến khôi phục file nguyên byte bằng finally; sau đó chạy lại hồi quy. Log tại `%TEMP%/d5_mutations/`, bảng kết quả `results.json`.

**Giới hạn kiểm chứng và dọn môi trường:**

- Chưa chạy pipeline thật, kho D3 của PM, nghiệm thu/chụp ảnh toàn bộ trang §10, Airflow thật, Databricks/Neon, hay mô hình AI thật.
- Chưa chứng minh bộ app toàn phần không có hồi quy so với HEAD. Cần rà 628 ca trượt và chạy trên kho kiểm thử đầy đủ trước khi coi toàn bộ app đạt.
- Không khởi động container, dựng image, commit hoặc push. Không thay đổi DAG cũ; SHA256 giữ nguyên `CB20D04287827835AF7DBFAD567012A592190832A596A65FE86DD103C5DEEF76`.
- Đã dùng junction data tới `D:/retail-analytics-am/data` theo hướng dẫn; gỡ sau test bằng `cmd /c rmdir data`, không xóa dữ liệu đích.

### Claude rà — 2026-11-07

**Kết luận: code đạt ở mức đọc và test. Chưa nghiệm thu, vì còn một lỗi chặn ở thiết kế (R1). Lỗi này do phiếu bỏ sót, không phải lỗi của GPT.**

**§10.1 Phạm vi file.**
- `retail_batch_pipeline.py` trùng byte với `20bce05`.
- `scripts/ingest/`, `retail_dbt/`, `scripts/forecast/` không đổi so với `610123b`.

**§10.2 Đọc tay chỗ chọn bản.** Đã tìm mọi lời gọi `current()`, `resolve()`, `pin()`, `open_session()` và `release_for_read()`.
- **Chat:**
  - `tools.run` và `known_groups` dùng `active_read`;
  - `service` và `page_explain` dùng `pinned_read`, nay cũng chạy trong `active_scope`;
  - `guarded._DuckDBSession` resolve trong `active_scope`;
  - `_release_scope` của Databricks dùng `active_current()`, hoặc `choose(..., pointer='active')`.
- **Trang:** con trỏ chọn ở `sidebar` theo `nav.url_path`.
- Không thấy đường nào để chat đọc bản `dashboard`.
- Ghi nhận nhỏ, không chặn:
  - (a) `open_session` ghim bản vào ngữ cảnh của nơi gọi. Hiện an toàn vì mọi nơi gọi đều nằm trong `active_read`.
  - (b) Con trỏ chọn theo `url_path`, mà trang mặc định có `url_path == ''`. Hiện mọi trang mặc định đều là trang dashboard nên đúng. Nếu sau này đổi trang mặc định sang Dự báo hay chat thì sai.
  - (c) `dashboard_state` không chặn `RETAIL_RELEASE_STATE` trỏ ra ngoài repo.
  - (d) Nút lỗi chỉ báo "kiểm tra nhật ký pipeline", không hiện `stderr` như rollback.

**Hồi quy so với HEAD (`610123b`):**
- Claude dựng worktree tách tại HEAD, cùng junction `data`, rồi chạy bộ app toàn phần. Kết quả: 771 đạt, **628 trượt**, 604 bỏ qua.
- So từng ca với lượt cuối của GPT: **0 ca đạt → trượt**, 0 ca trượt → đạt. 29 ca chỉ có ở bản mới đều là `test_d5_dashboard`, đều đạt. Vậy 628 ca trượt đều có từ trước, do thiếu `warehouse/dbt.duckdb`.
- **Lượt có kho:** Claude chép kho `dbt.duckdb` ngày 2026-10-18 vào cả hai worktree rồi chạy lại.
  - HEAD xong: 1.102 đạt, 298 trượt.
  - Bản D5a bị Claude Code dừng ở khoảng 75% vì máy thiếu RAM. Tới điểm dừng, bản D5a chưa có ca trượt nào ở những vùng HEAD trượt.
  - Ca dừng nằm ở `test_m4`; chạy riêng thì 4/4 đạt.
  - **Không chạy lại cả bộ**, nên phép so có kho **chưa trọn**.
- Đã gỡ junction, xóa kho chép và worktree tạm.

**Đột biến của Claude (16 ca, chạy trên test D5 và D3):** 15 ca bị bắt.

| Ca | Test bắt |
|---|---|
| C1 trang Dự báo đọc `dashboard` | `test_t6_each_page_selects_correct_schema[du_bao]` |
| C2 `_DuckDBSession` dùng pin của trang | `test_t7_direct_guard_reads_active` |
| C3 mỗi tool resolve lại, không giữ bản trong lượt | `test_t7_many_tools_keep_active_for_one_turn` |
| C4 `Registry.publish` nhận bản tổng hợp | `test_t1_rejected_no_write[active]` |
| C5 publish `active` xóa con trỏ `dashboard` | `test_t1_lifecycle_and_active_rollback` |
| C6 trả con trỏ ghi `null` thay vì xóa khóa | `test_t1_lifecycle_and_active_rollback` |
| C7 khung AI không ẩn | `test_t6_each_page_selects_correct_schema[ai_explain]` |
| C8 băng rôn không hiện | `test_t6_total_full_page_and_return` |
| C9 hàm xử lý bỏ kiểm Admin | **không bắt**, vì `actor('cong_bo')` (`ui/nhap_store.py:75`) cũng chặn vai trò khác Admin trước subprocess. Đây là lớp chặn thứ hai, không phải lỗ hổng. |
| C10 nhãn "kỳ gốc" hiện cả trên bản không đợt | `test_t8_period_label_scoped_to_synthetic` |
| C11 `choose` bỏ qua con trỏ | `test_t7_real_tool_sql_active_and_pin_restored` |
| C12 bản không đợt có khóa `co_du_lieu_tong_hop=False` | `test_t5_registry_flag[False]` |
| C13 `run --dot` không dừng ở `validate` | `test_t2_run_arguments_and_stop[True]` |
| C14 `publish_dashboard` bỏ kiểm `expected` | `test_t1_rejected_no_write[expected]` |
| C15 hàm xử lý bỏ kiểm ô xác nhận | `test_t9_confirmation_commands_and_rollback_options` |
| C16 `rollback_details` không lọc bản tổng hợp | `test_t9_confirmation_commands_and_rollback_options` |

**R1 — lỗi chặn: nút Admin không công bố được bản do DAG dựng.**
- **Nguyên nhân:** nút chạy CLI trên máy host. Nhánh `publish` trong `_execute` vẫn gọi ba bước, bước nào cũng hỏng với bản dựng trong Docker:
  1. kiểm `code_version`: image đóng băng ở commit cũ, nên khác code trên host;
  2. `snapshot.validate(context['snapshot_path'])`;
  3. `verify_consumers`, mở `context['duckdb_path']`.
- Context do Docker ghi lưu đường dẫn container. Ví dụ thật ở `warehouse/pipeline/docker/runs/425338e8…/context.json`: `snapshot_path = /opt/retail/warehouse/pipeline/docker/snapshots/47e7cbe765d9`. Trên host không có đường dẫn này.
- Test của D5a giả subprocess, còn §10 bước 1–4 dựng bản trên host, nên cả hai đều không lộ lỗi này.
- `tra-dashboard` chỉ đọc registry nên chạy được từ host.

**R2 — §10 bước 5 (DAG mới) cần dựng lại image.** DAG và `cli.py` vào image bằng `COPY` (`deploy/airflow/Dockerfile:9–12`), không mount.
- Dựng lại image làm đổi `code_version` của DAG production. DAG này đang UNPAUSED, target `databricks`, nên lượt 08:00 kế tiếp sẽ build lại trên Databricks thay vì bỏ qua.
- Mount `data_demo` cần tạo lại container.

**R3:** `0bce3b72…` không công bố được (đã sửa câu ở §10).

### Claude rà D5a-1 (§13) — 2026-11-07

**Kết luận: đạt ở mức đọc code và test.** Chưa nghiệm thu: còn §10 bước 1–4 do PM chạy. Phiên rà không nhận được báo cáo D5a-1 của GPT, và §11 chưa có mục GPT cho D5a-1, nên phần dưới chỉ dựa trên code trong worktree.

**Đọc diff.**
- `dat-dashboard` (`cli.py`, nhánh `a.stage == 'dat-dashboard'`):
  - kiểm đúng thứ tự §13.1 trong `writer_lock`;
  - chỉ đọc `state.json` rồi gọi `verify_consumers(record, registry, None)`;
  - đường dẫn kho lấy từ `artifact_path` tương đối theo `registry.path.parent`. Bản ghi do `validate` ghi luôn có khóa này (`cli.py`, dòng `record['artifact_path'] = ...`), kể cả hai bản thật trong `d3-thu`;
  - `expected` đọc trong cùng lock; ghi một dòng lịch sử `publish_dashboard`, lần hai cho `bo_qua`.
- Nút Duyệt gọi `dat-dashboard ... --xac-nhan-tong-hop --target duckdb --root <cha của RETAIL_RELEASE_STATE>`, không còn lấy `run_id` từ bản ghi. Lỗi hiện `stderr`, trống thì hiện `stdout`.
- `app.py` dò ngược `nav` sang khóa `roles.PAGES` bằng `page is nav`. Ở Streamlit 1.64, `st.navigation` trả về chính object trong danh sách (`navigation.py`, `matching_pages[0]`), nên phép so `is` đúng.
- So với `610123b`, `scripts/ingest/`, `retail_dbt/`, `scripts/forecast/` không đổi. `retail_batch_pipeline.py` giữ SHA256 `cb20d042…deef76`.

**Test** (Python venv, `-B -X utf8`; apps và scripts chạy riêng):
- 4 file UI và `test_d5_dashboard.py`: 361 đạt, gồm 326 ca UI và 35 ca D5;
- `test_d5_con_tro.py`, `test_d3_du_bao.py`, `test_snapshot_dot.py`: 118 đạt.

**Đột biến của Claude (14 ca): test bắt 11 ca.**

| Ca | Test bắt |
|---|---|
| D1 bỏ kiểm cờ ở `dat-dashboard` | `test_t13_rejected_preserves_registry[flag]` |
| D2 bỏ kiểm `ready` ở CLI | `test_t13_rejected_preserves_registry[not_ready]` |
| D2b bỏ kiểm `ready` ở cả CLI lẫn `publish_dashboard` | `test_t1_rejected_no_write[not_ready]` |
| D3 bỏ `verify_consumers` (bước 5 của 13.1) | `test_t13_rejected_preserves_registry[missing_file]` |
| D4 bỏ `writer_lock` | **không bắt** |
| D5 cho `--target databricks` | `test_t13_rejected_preserves_registry[cloud]` |
| D6 bỏ kiểm 24 hex | **không bắt**: id sai dạng vẫn bị chặn vì không có trong registry. `release_id` không dùng làm đường dẫn. |
| D7 `expected = None` thay vì đọc trong lock | `test_t13_registry_only_publish[False]` |
| D8 không ghi lịch sử | `test_t13_registry_only_publish[False]` |
| D9 `sidebar` quay lại so `url_path` | `test_t14_default_page_reads_active[du_bao]` |
| D10 nút lỗi không hiện `stderr` | `test_t9_dashboard_command_error_visible` |
| D11 nút vẫn gọi `publish` theo `run_id` | `test_t9_confirmation_commands_and_rollback_options` |
| D12 hàm xử lý bỏ kiểm `ready`/cờ trước subprocess | **không bắt**: CLI kiểm lại, đây là lớp chặn thứ hai |
| D13 nút thiếu `--xac-nhan-tong-hop` | `test_t9_confirmation_commands_and_rollback_options` |

Ba ca §13.4 yêu cầu (bỏ bước 5, bỏ kiểm cờ, quay lại `url_path`) đều bị bắt.

**Ghi nhận, không chặn:**
- (e) Không test nào giữ `writer_lock` của `dat-dashboard`. `publish_dashboard` có kiểm `expected`, nên lỗi tranh ghi chỉ xảy ra khi hai lệnh cùng đọc trước khi một lệnh ghi xong. Có thể thêm test giả `writer_lock` để ghi nhận đã vào lock.
- (f) D12 không có test riêng. Nếu muốn giữ lớp chặn này, thêm ca: bản không `ready` thì `dashboard_action` không gọi subprocess.
- (g) `run --dot` vẫn in "Admin công bố bằng publish --xac-nhan-tong-hop". Câu này vẫn đúng, nhưng chưa nhắc nút trên app (tức `dat-dashboard`).


### GPT — D5a-1 — 2026-11-07

Đã làm §13 trên `D:/retail-analytics-nap`, nhánh `nap-ky/myuyen`, chưa commit/push. Kết quả dưới đây là lượt chạy lại sau khi PM xác nhận phiên Claude chạy đột biến đồng thời đã dừng.

**Phần thực hiện, file đổi so với D5a:**

- `scripts/pipeline/cli.py`: thêm `dat-dashboard`, cần run-id và cờ xác nhận; kiểm lần lượt cờ, target duckdb, id 24 hex, bản ready có cờ, rồi `verify_consumers(record, registry, None)` trong writer_lock. Lấy expected trong cùng lock, chỉ đổi dashboard/dashboard_since; ghi history stage publish_dashboard, lần hai cùng bản là bo_qua. Không đọc context, snapshot hoặc gọi hàm code_version; không nối cloud. Giữ đường publish theo run của D5a và tiếp tục từ chối cờ trên run.
- `apps/retail_app/ui/nhap_runner.py`: nút gọi dat-dashboard bằng release-id và run-id mới dạng ui-dashboard-<thời điểm>; bỏ lấy run-id từ bản ghi. Giữ các lớp chặn quyền, actor, xác nhận, ready/cờ và root đã chốt.
- `apps/retail_app/views/duyet_du_lieu.py`: lệnh lỗi hiện stderr; nếu stderr trống thì hiện stdout. Thành công vẫn rerun và bỏ tick.
- `apps/retail_app/app.py`: giữ ánh xạ khóa roles.PAGES sang đối tượng Page, dò ngược trang đang chạy để truyền khóa cho sidebar. Không dùng url_path để chọn con trỏ. Sidebar đã so đúng hai khóa du_bao/ai_explain nên không cần sửa thêm common.py.
- `scripts/pipeline/tests/test_d5_con_tro.py`: thêm 10 ca T13. Kho DuckDB nhỏ được tạo trong tmp_path, dùng verify_consumers thật; artifact_path tương đối còn duckdb_path/context mang đường dẫn /opt/retail. Có cả trường hợp không có context. Từ chối thiếu cờ, cloud, id sai, bản không tồn tại, không cờ, chưa ready, thiếu file và thiếu bảng; registry giữ nguyên byte. Kiểm lịch sử và lần gọi lặp.
- `apps/retail_app/tests/test_d5_dashboard.py`: sửa T9 theo lệnh mới, thử bản ghi không có run_id; thêm 4 ca hiện stderr/stdout cho đặt/trả dashboard, 2 ca T14 đặt Dự báo/chat làm trang mặc định và xác nhận đọc active.
- `docs/giao_viec_d5_cong_bo_dot.md`: mục báo cáo này. Giữ nguyên phần rà của Claude.

**Sự cố sửa đồng thời và phạm vi:**

- Đã tạm dừng khi thấy writer_lock bị thay bằng if True. Theo xác nhận PM, đó là đột biến D4 của phiên Claude khác, đã khôi phục và dừng.
- Kiểm lại cli.py, state.py, app.py, duyet_du_lieu.py, nhap_runner.py: các sửa D5a-1 vẫn đủ; ba khối with writer_lock(a.root) đúng. Không cần khôi phục thêm code.
- Không lấy lượt hồi quy bị xen sửa làm bằng chứng cuối. Chạy lại ba đột biến và các bộ test dưới đây; hash cả năm file trước/sau đột biến và sau hồi quy trùng nhau.
- Không làm khác §13, không mở rộng sang D5b hoặc các ghi nhận không chặn khác. Không sửa kỳ vọng số liệu/test cũ để test xanh; T9 đổi kỳ vọng lệnh đúng yêu cầu §13.2. Không sửa thêm state.py ở D5a-1.

**Kết quả cuối (Python `D:/retail-analytics/.venv/Scripts/python.exe`, chạy từng lệnh riêng):**

| Bộ/lệnh pytest | Đạt | Trượt/lỗi | Bỏ qua |
|---|---:|---:|---:|
| `scripts/pipeline/tests -q` | 296 | 0 | 2 |
| `scripts/ingest/tests -q` | 337 | 0 | 0 |
| Bốn file UI nhập + `apps/retail_app/tests/test_d5_dashboard.py -q` | 361 | 0 | 0 |

Lệnh app chạy đúng các file: `test_nhap_theo_doi.py` (61), `test_nhap_tu_dong.py` (151), `test_nhap_du_lieu.py` (97), `test_extension_grants.py` (17), `test_d5_dashboard.py` (35), tất cả dưới `apps/retail_app/tests/`. Bốn file UI đạt **326/326**. D5 CLI đạt **40/40** trong tổng pipeline; D5 app đạt **35/35** trong tổng app. Không cộng trùng các số riêng vào tổng.

Lệnh thực tế thêm `-B`, `--tb=short`, `--junitxml`; app đặt RETAIL_TEST_DATABRICKS=0. Hai skip pipeline là thiếu snapshot 5bd9a84aaf73 và chưa có bản do pipeline publish. Không chạy lại app toàn phần theo yêu cầu PM.

Bằng chứng cuối: `%TEMP%/d5a1_pipeline_final.xml`, `d5a1_ingest_final.xml`, `d5a1_app_final.xml`. Thời gian lần lượt 114,05 giây; 212,76 giây; 138,68 giây.

**Ba đột biến §13.4 — chạy lại sau khi hết sửa đồng thời, bắt 3/3:**

| Đột biến | Test bắt | Khi gây lỗi |
|---|---|---|
| Bỏ bước đọc thử kho | `test_t13_rejected_preserves_registry[missing_file]`, `[missing_table]` | 2 trượt, exit 1 |
| Bỏ kiểm cờ dat-dashboard | `test_t13_rejected_preserves_registry[flag]` | 1 trượt, exit 1 |
| Truyền nav.url_path thay khóa trang cho sidebar | `test_t14_default_page_reads_active[du_bao]`, `[ai_explain]` | 2 trượt, exit 1 |

Đây là lỗi assertion được test bắt, không phải lỗi collection. Mỗi lần đều khôi phục nguyên byte trong finally; sau đó mới chạy hồi quy cuối. Log/bảng kết quả/hash tại `%TEMP%/d5a1_mutations_final/` (`results.json`, `restored_hashes.json` và ba log).

**Dọn môi trường, phần chưa kiểm:**

- Đã gỡ junction data bằng `cmd /c rmdir data` sau khi kiểm đúng junction/đích. Thư mục `D:/retail-analytics-am/data` vẫn tồn tại.
- Chưa chạy nghiệm thu §10 bước 1–4 trên kho thật; PM thực hiện. Không chạy pipeline thật, Docker, dựng image, DAG production hoặc kết nối Databricks/Neon/Airflow. Không chạy §10 bước 5 theo quyết định bổ sung.
- Không commit, push, stage hay sửa các file bị cấm. Các test local và kho tự dựng không thay cho nghiệm thu thực tế.

### Claude kiểm lại sau báo cáo GPT D5a-1 — 2026-11-07

Lượt rà ở trên chạy đột biến cùng lúc với lúc GPT đang sửa (GPT có ghi lại sự cố này). Vì vậy Claude kiểm lại trên code hiện tại.

- **Không còn sót đột biến.** Không tìm thấy mẫu nào của 14 ca: `if True:`, `if False:`, `(lambda *x: None)`, `expected = None`, `nav.url_path` truyền vào `sidebar`, thông báo lỗi thay cho `stderr`.
- **Các khối giữ nguyên:** `cli.py` còn đủ 3 khối `with writer_lock(a.root)`. `dat-dashboard` vẫn kiểm 24 ký tự hex (`:612`) và vẫn gọi `verify_consumers(record, registry, None)` (`:620`). Nút vẫn truyền `--xac-nhan-tong-hop` (`nhap_runner.py:812`).
- **Test chạy lại:**
  - `test_d5_con_tro.py`, `test_d3_du_bao.py`, `test_snapshot_dot.py`: 118 đạt;
  - bốn file UI cùng `test_extension_grants.py` và `test_d5_dashboard.py`: 361 đạt.
- **Môi trường:** junction `data` đã gỡ; `D:\retail-analytics-am\data` còn 21 mục.

**Kết luận: D5a-1 đạt ở mức code và test**, khớp với báo cáo GPT. Ba ghi nhận (e), (f), (g) ở trên vẫn để ngỏ, không chặn. Còn chờ §10 bước 1–4 do PM chạy.

## 12. PM cần chốt trước khi giao

**PM chốt 2026-11-06: theo đề xuất ở cả 6 mục.** Cụ thể:
- D5b tách phiếu riêng;
- gộp phiếu "hiển thị sau rollback" trước khi giao D5a;
- giữ thẻ `2012–2022` với nhãn "toàn bộ dữ liệu";
- cờ đặt trong bản ghi registry;
- con trỏ dashboard chỉ nhận bản có cờ;
- DAG mới chỉ chạy `duckdb`.

1. **Tách D5 thành D5a (phiếu này) và D5b (trang Gửi/Duyệt loại "đợt").**
   - Thiết kế gốc gộp trang Gửi/Duyệt loại "đợt" vào D5. Phần đó gồm: gửi nhiều file một lần, phân nhóm theo §4.2 của thiết kế, runner tự chạy `--dot` và lấy `--du-bao-tu` là `active`. Runner sẽ báo lỗi rõ nếu `active` không hợp lệ làm nguồn, không tự chọn bản khác.
   - B′ ghi "chưa có T2 thì DE nạp đợt bằng Airflow". Vì vậy D5a đã đủ cho demo: DE nạp đợt bằng DAG ở §7, Admin công bố trên app ở §6.3, dashboard đổi số.
   - **Đề xuất:** giao D5a trước. D5b soạn phiếu riêng, chỉ làm nếu D5a đạt trước khoảng 2026-11-20, để còn thời gian cho bước lên Databricks.
2. **Phiếu "hiển thị sau rollback" chưa commit** (`D:/retail-analytics-am`, nhánh `auto-mapping/myuyen`):
   - phiếu này sửa `nhap_runner.py`, `duyet_du_lieu.py`, `gui_du_lieu.py`, tức chính các file D5a sửa;
   - nhánh `nap-ky/myuyen` đã gộp auto mapping **trước** phần đó.
   - **Đề xuất:** PM thử §5 của phiếu đó, Claude commit rồi gộp vào `nap-ky/myuyen`, xong mới giao D5a. Không làm vậy thì GPT code trên nền cũ và sau này phải gỡ xung đột.
3. **Nhãn kỳ trên bản có đợt (§6.2).** Đề xuất:
   - thẻ `2013–2022` ghi "kỳ gốc, số thật";
   - thẻ `2012–2022` giữ "toàn bộ dữ liệu", vì đó là số deck;
   - thẻ `2013–2023` ghi "kỳ phân tích".

   Có muốn ẩn thẻ `2012–2022` trên bản có đợt cho đỡ rối không?
4. **Nguồn cờ băng rôn:** khóa `co_du_lieu_tong_hop` trong bản ghi registry, chỉ có ở bản có đợt (§5.1). Đề xuất: đồng ý.
5. **Con trỏ dashboard chỉ nhận bản có cờ tổng hợp** (§3 luật 1). Đề xuất: đồng ý, để con trỏ này không thành đường rollback thứ hai.
6. **DAG mới chỉ chạy `duckdb`** (§7). Đợt trên Databricks là bước "lên Databricks" sau D5, cần mở cổng `cli.py:432` và kiểm quota. Đề xuất: đồng ý.

## 13. Bổ sung D5a-1 (PM chốt 2026-11-07, sau phần rà ở §11)

PM chọn:
- **R1:** thêm lệnh chỉ đổi con trỏ;
- **R2:** bỏ §10 bước 5 trước mốc 2026-12-12. File DAG mới giữ trong repo; không dựng lại image, không đụng DAG production.

Làm tiếp trên chính worktree này, chưa commit. Không đổi gì ngoài các mục dưới đây.

### 13.1 Lệnh `dat-dashboard`

```text
python -m scripts.pipeline.cli dat-dashboard --run-id <id> --release-id <24 hex> --xac-nhan-tong-hop --root <root>
```

- Theo mẫu `tra-dashboard`: chạy trong `writer_lock(root)` và **chỉ đọc registry**. Không đọc `runs/<id>/context.json`, snapshot hay `code_version`. Nhờ vậy lệnh dùng được cho cả bản dựng trên máy lẫn bản dựng trong Docker.
- **Kiểm, theo thứ tự; sai thì exit 2 và registry không đổi:**
  1. có cờ `--xac-nhan-tong-hop`;
  2. `--target duckdb`, vì `databricks` vẫn chặn như §4.2;
  3. `--release-id` đúng 24 hex;
  4. bản ghi tồn tại, `status == 'ready'`, `co_du_lieu_tong_hop is True`;
  5. **đọc thử kho của bản đó**: gọi `verify_consumers(record, registry, None)`. Bản ghi có `artifact_path` tương đối, nên đường dẫn resolve theo `registry.path.parent`, chạy được trên máy.
- **Vì sao bước 5 cần:** ở `cli.py:493–494`, `register` ghi bản `ready` *trước* `verify_consumers`. Nên có thể có bản `ready` mà kho không đọc được.
- **Đạt:** gọi `registry.publish_dashboard(rid, expected)`, với `expected` là giá trị `dashboard` đọc trong cùng lock. Ghi một dòng `history.jsonl`, stage `publish_dashboard`, có `release_id`. Đặt lại đúng bản đang trỏ thì kết quả `bo_qua`, giống `publish_dashboard` hiện có.
- `--xac-nhan-tong-hop` nay nhận ở `publish` và `dat-dashboard`. `run` vẫn không nhận cờ này. `publish --xac-nhan-tong-hop` theo run giữ nguyên như D5a.

### 13.2 Nút trên trang Duyệt

- `dashboard_action` gọi `dat-dashboard --release-id <bản chọn> --xac-nhan-tong-hop` với `--run-id ui-dashboard-<thời điểm>`, giống nhánh trả con trỏ. Bỏ phần lấy `run_id` từ bản ghi.
- Các lớp chặn giữ nguyên:
  - hàm xử lý đọc lại vai trò;
  - `actor('cong_bo')`;
  - ô xác nhận;
  - kiểm `ready` và cờ trước subprocess.
- Lệnh lỗi thì hiện `stderr` (hoặc `stdout` nếu trống), như khối Rollback, thay cho câu "kiểm tra nhật ký pipeline".

### 13.3 Chọn con trỏ theo trang (ghi nhận (b) ở §11)

`sidebar` đang so `nav.url_path`, mà trang mặc định có `url_path == ''`. Sửa:
- `app.py` truyền **khóa trang** trong `roles.PAGES`, lấy từ trang đang chạy; ví dụ dò ngược `nav` sang khóa;
- `sidebar` so khóa đó với `('du_bao', 'ai_explain')`.

Có test: đặt tạm `DEFAULT_PAGE` của một vai trò thành `du_bao`, mở app không chuyển trang, phải đọc `active`.

### 13.4 Test bắt buộc

- **T13:**
  - `dat-dashboard` đạt với bản có cờ mà `runs/<id>/context.json` mang đường dẫn `/opt/retail/...` hoặc không có file: chỉ `dashboard` và `dashboard_since` đổi;
  - từ chối, với registry giữ nguyên từng byte:
    - thiếu cờ;
    - `databricks`;
    - id sai dạng;
    - bản không cờ;
    - bản chưa `ready`;
    - kho của bản không mở được hoặc thiếu bảng;
  - dòng lịch sử đúng; chạy lần hai cùng bản thì `bo_qua`.
- **T9 sửa:** lệnh subprocess của nút đúng tham số mới; lỗi thì hiện `stderr`.
- **T14:** mục 13.3.
- **Đột biến, ghi vào §11:**
  - bỏ bước 5 của 13.1;
  - bỏ kiểm cờ ở `dat-dashboard`;
  - `sidebar` quay lại so `url_path`.

Lệnh chạy giữ như §9: bốn file UI phải 326/326 đạt, và `test_d5_*` đạt. Không cần chạy lại bộ app toàn phần; Claude sẽ so với HEAD.

### 13.5 §10 sau bổ sung

- Bước 2 thêm: công bố bằng nút trên app, tức đi qua `dat-dashboard`.
- **Bước 5 bỏ** trước 2026-12-12.
