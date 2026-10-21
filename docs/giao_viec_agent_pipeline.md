# Giao việc hoàn thiện pipeline DE cho agent (sổ tay của PM)

Soạn ngày 2026-10-18 (vai Head of AI). Dùng cho Claude Code và Codex.
"Pipeline" ở đây là phần Data Engineering trên sơ đồ GĐ1 và [kiến trúc tổng](kien_truc_pipeline_tong.md): snapshot → Bronze →
Silver → Gold → Serving → quality gate → publish, cùng Airflow và giám sát. Phần AI agent giao ở
[giao_viec_agent_gd2.md](giao_viec_agent_gd2.md). **Kafka vẫn hoãn** (PM chốt 2026-10-11), không có bước nào ở đây.

Cách chạy và bằng chứng của pipeline hiện có: [automation_batch.md](automation_batch.md). File này chỉ giữ **cách giao việc**.

**Điểm vào chính (2026-10-18):** PM giao việc tuần tự theo [giao_viec_theo_so_do.md](giao_viec_theo_so_do.md), làm đủ các ô trên
sơ đồ kiến trúc tổng. Khi đó các prompt §4.x ở đây vẫn dùng, nhưng bỏ qua worktree, gộp nhánh (§6) và mục 8 của khối §4.0
(luật §3 của file kia). Worktree chỉ dùng nếu PM muốn chạy phiên pipeline song song với phiên AI.

---

## 1. Pipeline đã có gì, còn thiếu gì

| Phần | Trạng thái | Bằng chứng |
|---|---|---|
| Snapshot bất biến (header, số dòng, SHA-256, `_src_row`) | Chạy | `scripts/pipeline/snapshot.py`, `scripts/ingest/source_contract.py` |
| Airflow Docker 4 task, retry, exit 2 không retry | Chạy | `deploy/airflow/dags/retail_batch_pipeline.py` |
| Build theo bản, quality gate, kiểm quyền reader, con trỏ active, rollback | Chạy local và Databricks | `automation_batch.md`, bản `cfe19211…` (CLI) và `b25b3e47…` (Airflow), 2026-10-17 |
| Stage dự báo trong pipeline | Chạy local và Databricks | `automation_batch.md`, mục "Stage dự báo" |
| App public đọc theo bản | Chạy | `RETAIL_RELEASE_MODE = "versioned"` từ 2026-10-17 |
| **A4 giám sát:** lịch sử lần chạy, thẻ "bản đang phục vụ", độ tươi | **Chưa có.** Mới có `failure.json` từng run và trang Sức khỏe (chỉ log dbt của bản đang phục vụ) | — |
| **A3 hợp đồng dữ liệu:** kiểu, nullable, khóa chính, quarantine | **Một phần.** Mới kiểm header, số dòng, mã băm | — |
| Cố ý làm hỏng quality gate trên cloud để thấy bản đang phục vụ được giữ | Chưa làm (mới có test local) | `automation_batch.md` dòng "Chưa làm" |
| Bật lịch Airflow | Chưa bật | DAG mặc định paused, `target=duckdb` |
| Tài liệu kiến trúc | **Lệch:** `kien_truc_pipeline_tong.md` §1 vẫn ghi "Automation pipeline: Chưa có", thân A1/A2 còn tả CLONE và cặp stage/prod | — |
| Dọn release cũ | Chưa có, mức Could | `automation_batch.md`: "chưa tự dọn lịch sử release" |

**Lưu ý `code_version`:** hàm này băm cả `retail_dbt/dbt_project.yml` và `retail_dbt/profiles.yml`, không chỉ các thư mục code
(`scripts/pipeline/cli.py`, từ 2026-10-12). Commit `d3249a1` (chú thích `profiles.yml`) và phần sửa chú thích `dbt_project.yml`
ngày 2026-10-18 vì vậy đã đổi `code_version`. Lần chạy pipeline kế tiếp sẽ dựng bản mới chứ không bỏ qua. Không hỏng gì,
chỉ tốn một lần build.

## 2. Quyết định PM cần chốt

Không cần chốt hết trước khi giao việc. Cột "Hỏi lúc nào" cho biết agent phải dừng hỏi ở đâu.

| Mã | Câu hỏi | Đề xuất mặc định | Hỏi lúc nào |
|---|---|---|---|
| D1 | App có hiện cả các lần chạy **lỗi** không? | **Không.** Lần lỗi xem qua lệnh lịch sử của CLI và Airflow UI. App chỉ hiện bản đang phục vụ. Hiện lần lỗi trên app cần cấp thêm quyền đọc cho SP, dễ lặp lại sự cố khóa chat 2026-10-17 | Trước P1 |
| D2 | Bật lịch Airflow không, chạy target nào? | Bật lịch 08:00 cho **target duckdb** để demo. Databricks vẫn do PM bấm tay. Lịch chạy Databricks mà code đã đổi sẽ tự dựng và **tự công bố** lên app public. **PM chốt 2026-10-19: lịch 08:00 chạy target databricks** (biến `RETAIL_PIPELINE_DEFAULT_TARGET` trong `.env.airflow.local`, commit `4641d5a`); Airflow vẫn chạy local trong Docker. Code nằm cố định trong image, nên code mới chỉ lên production khi có người dựng lại image từ một commit; snapshot và code trùng bản đang phục vụ thì run `bo_qua` ở prepare | Trước P4 |
| D3 | Có làm phép thử hỏng quality gate trên cloud không? | **Có, một lần.** Tốn quota bằng một lần build (khoảng 20 phút). Bằng chứng tốt khi bảo vệ | Trước P4 |
| D4 | Xóa hay giữ code Snowflake? | **Xóa**, PM chốt 2026-10-21. P2b đã gỡ code, Claude rà, commit `020ad18`…`c73ad91`. Không dựng image, không chạy pipeline; bản đang phục vụ không đổi | Đã chốt 2026-10-21 |
| D5 | Dọn release cũ trên Databricks? | Chưa làm, chỉ ghi giới hạn | Không cần hỏi lại |
| D6 | Phiên pipeline làm trong git worktree riêng? | **Có** (xem §6). Không dùng worktree thì P1, P2 phải đợi B7 làm xong phần code | Trước P1 |

## 3. Thứ tự các bước

| Thứ tự | Bước | Ai / skill | Ngày gợi ý | Ghi chú |
|---|---|---|---|---|
| P0 | **Dọn trước:** (1) bước 0 của [giao_viec_agent_gd2.md](giao_viec_agent_gd2.md) §2 (chủ các thay đổi chưa commit trong `apps/`); (2) commit đợt sửa tài liệu bỏ Snowflake và hai file `giao_viec_agent_*.md`; (3) chốt D1, D6; (4) rồi mới tạo worktree (§6) | PM | 10-18 → 10-19 | Chặn P1. Worktree lấy code từ commit, nên file chưa commit sẽ không có trong đó (§6) |
| P1 | **A4 giám sát** | `retail-platform-validation` (+ `retail-bi-product` cho thẻ trên trang), prompt §4.1 | 10-19 → 10-20 | Should |
| P2 | **A3 hợp đồng dữ liệu bản gọn** | `retail-platform-validation` + `retail-analytics-engineering`, prompt §4.2 | 10-20 → 10-21 | Should. Cùng phiên với P1 được, làm sau P1 |
| P2b | Xóa code Snowflake theo D4 đã chốt | `retail-analytics-engineering`, prompt §4.3 | 10-21 | Xong 2026-10-21, commit `020ad18`…`c73ad91`; không tác động image Airflow đang chạy |
| P3 | Xem lại, commit, gộp nhánh worktree về `app/myuyen`, chạy bộ test app ở thư mục chính | PM (agent hỗ trợ) | 10-21 → 10-22 | Bộ test app chỉ tính ở bước này (§6) |
| P4 | **Lên cloud:** build image, chạy DAG target databricks, thử hỏng gate, bật lịch theo D2; PM push và Reboot | `retail-platform-validation` + `databricks:databricks-core`, prompt §4.4 | 10-22 → 10-23 | Không chạy lúc B7 đang eval trên Databricks |
| P5 | **Sửa tài liệu cho khớp hiện trạng** | `retail-platform-validation`, prompt §4.5 | 10-23 | Chỉ viết tài liệu, chạy song song được |

Trễ thì cắt theo thứ tự: phần bật lịch của P4 → P2b → P2. Giữ P1 (ô "monitor (Airflow)" trên sơ đồ thầy) và P5.
**Phiên pipeline không bao giờ được làm chậm B7** (Must bên AI).

## 4. Prompt dán sẵn

Thay `/` bằng `$` khi dùng Codex. Mỗi prompt dán vào một phiên mới, **sau khối mở đầu §4.0**.

### 4.0 Khối mở đầu cho phiên pipeline

Giống khối §3.0 của `giao_viec_agent_gd2.md`, khác ở mục 1, 3, 7 và thêm mục 8.

```text
Trước khi sửa gì:
1. Đọc CLAUDE.md, rồi docs/giao_viec_agent_pipeline.md, rồi docs/automation_batch.md, rồi docs/kien_truc_pipeline_tong.md §5–§6.
2. Chạy git status và xem giờ sửa của các file sắp đụng. File đã bị sửa mà không phải do phiên này viết: không stage,
   không revert, không ghi đè. File cần sửa đang có thay đổi chưa rõ chủ: dừng lại hỏi PM.
3. Không sửa file trong apps/, scripts/, retail_dbt/ khi pipeline đang chạy: pipeline băm các thư mục này (và
   retail_dbt/dbt_project.yml, profiles.yml) thành code_version.
   Chạy pipeline local để kiểm (P1, P2) thì dùng --root riêng, KHÔNG BAO GIỜ dùng warehouse/pipeline của thư mục chính:
   phiên B7 đọc warehouse/pipeline/state.json, công bố vào đó sẽ đổi bản ngay giữa lúc B7 đang eval.
   Chạy cloud (P4) chỉ qua deployment Airflow hiện có (root warehouse/pipeline/docker): một catalog chỉ một writer.
4. Databricks: luôn có --profile, không tự chọn profile; hỏi PM trước mọi lệnh ghi lên cloud hoặc tốn quota.
5. Python: D:/retail-analytics/.venv/Scripts/python.exe, đặt PYTHONUTF8=1. Không dựng Kafka, không làm gì với Kaggle hay Snowflake
   (trừ bước P2b khi PM đã chốt xóa).
6. Không commit khi PM chưa nói. PM cho commit thì mỗi file một commit, message tiếng Việt không dấu, không có dòng
   Co-Authored-By, git add từng file, không bao giờ commit data/. Push do PM tự gõ.
7. Xong việc: ghi kết quả nghiệm thu vào docs/automation_batch.md (cùng kiểu các dòng "Nghiệm thu local …" đã có),
   một mục bàn giao ở docs/dwh_huong_dan_pm_ba.md §9. Giải thích cho PM bằng lời đời thường, nói rõ đã sửa file chung nào.
8. Phiên AI (B7) đang sửa cùng repo. Không sửa: apps/retail_app/ai_explain/*, apps/retail_app/dwh/guarded.py,
   apps/retail_app/ui/common.py, các biến reader trong retail_dbt/dbt_project.yml (ai_*_relations, app_*_relations),
   scripts/ops/ai_live_eval.py. Cần sửa các file này thì dừng, báo PM.
```

### 4.1 P1: A4 giám sát

```text
/retail-platform-validation Làm A4 (giám sát) trong docs/kien_truc_pipeline_tong.md §5, theo docs/giao_viec_agent_pipeline.md §4.1.
PM đã chốt D1 = [không / có] (app có hiện lần chạy lỗi không).

Đọc trước: docs/automation_batch.md (cả mục "Nhật ký và lỗi"); scripts/pipeline/cli.py, state.py;
deploy/airflow/dags/retail_batch_pipeline.py; apps/retail_app/views/suc_khoe_du_lieu.py; apps/retail_app/dwh/releases.py.

Việc 1, lịch sử lần chạy:
- Mỗi stage (prepare, build, validate, publish) và mỗi lần rollback, dù đạt, bỏ qua hay lỗi, để lại một bản ghi:
  run_id, stage, target, snapshot_id, code_version, release_id, giờ bắt đầu, giờ kết thúc, kết quả, loại lỗi.
  Không ghi SQL, token hay nội dung exception (giống failure.json hiện nay).
- Ghi từ CLI (scripts/pipeline/cli.py), không chỉ từ callback Airflow: lần chạy cloud đầu tiên chạy bằng CLI.
- Không đặt lịch sử trong schema theo bản r_<id>_ops: bản lỗi không bao giờ được công bố, nên sẽ không ai thấy.
- Không sửa bản ghi release trong registry: register() từ chối sửa bản đã qua quality gate.
- Local: file trong --root. Cloud: bảng trong retail_control, do writer sở hữu. Không GRANT bảng này cho SP reader
  (reader hiện có USE SCHEMA trên retail_control và SELECT riêng trên retail_control.state, xem reader_grants).
- Ghi lịch sử thất bại thì không được che lỗi gốc, và không được làm một lần publish đã đổi con trỏ bị báo là lỗi.
- Có lệnh in N lần chạy gần nhất (ví dụ `python -m scripts.pipeline.cli history`).

Việc 2, thẻ "bản đang phục vụ" trên trang Sức khỏe dữ liệu (chế độ versioned): release_id, snapshot, code_version rút gọn,
run đã dựng, giờ công bố, tuổi của bản (giờ hiện tại trừ giờ công bố). Chế độ cũ: ghi "không áp dụng", không lỗi.
- Chỉ lấy từ những gì SP reader đã được đọc. Gợi ý: lưu giờ công bố cạnh con trỏ active trong payload registry
  (không trong bản ghi release); registry cũ chưa có trường này thì app vẫn chạy.
- Không cấp quyền mới cho SP reader, không đổi danh sách quyền mà guard kiểm. Đây là nguyên nhân sự cố khóa chat
  2026-10-17 (automation_batch.md, "Sự cố sau publish"). D1 = có thì phần hiện lần lỗi làm SAU khi B7 xong, ở thư mục chính,
  đi đủ các bước bẫy trong .agents/skills/retail-ai-explain/references/agent_levels.md (file này chưa commit, worktree không có).

Việc 3, độ tươi: đo bằng tuổi của bản đang phục vụ, không dùng dbt source freshness theo ngày dữ liệu. Dữ liệu dừng ở
2022-12-31 theo thiết kế, nên freshness theo ngày dữ liệu luôn đỏ; không đưa nó vào quality gate. Ngưỡng cảnh báo theo
lịch chạy (D2); lịch còn tắt thì chỉ hiện tuổi, không tô đỏ. Ghi lý do vào automation_batch.md.

Không làm: task Airflow chỉ để ghi log (CLI đã ghi); email/Slack; đổi luật quality gate; các file ở mục 8 khối mở đầu; commit.

Xong khi:
- test pipeline mới đạt: lần đạt, bỏ qua, lỗi giữa chừng, rollback đều có bản ghi; lỗi ghi lịch sử không che lỗi gốc;
- scripts/pipeline/tests và apps/retail_app/tests/test_releases.py đạt;
- một lần chạy local trong --root riêng tạo bản mới, lệnh lịch sử thấy đủ các stage;
- AppTest trang Sức khỏe đạt ở chế độ cũ và versioned, kể cả với registry cũ chưa có trường mới;
- chiều ngược lại cũng đạt: code app CŨ (dwh/releases.py, _release_scope trong dwh/guarded.py của commit trước P1) đọc
  payload registry MỚI vẫn chạy. Ở P4, pipeline ghi payload mới lên cloud trước khi PM kịp Reboot bản public.
Cloud: chưa chạy, ghi là chưa chạy.
```

### 4.2 P2: A3 hợp đồng dữ liệu bản gọn

```text
/retail-platform-validation Làm A3 bản gọn (hợp đồng dữ liệu) trong docs/kien_truc_pipeline_tong.md §5, theo
docs/giao_viec_agent_pipeline.md §4.2. Dùng thêm retail-analytics-engineering cho phần đối chiếu với dbt.

Đọc trước: scripts/ingest/source_contract.py; scripts/pipeline/snapshot.py; retail_dbt/models/staging/ (_sources.yml và
kiểu cast trong từng model staging); CLAUDE.md §5 điểm 1 và 8.

Hiện có: hợp đồng mỗi nguồn = header + số dòng, kèm SHA-256 của CSV ghim cứng; snapshot lưu mọi cột dạng chuỗi.

Việc:
- Mở rộng hợp đồng trong source_contract.py: mỗi cột có kiểu và nullable; mỗi nguồn có khóa chính. Kiểu khai báo phải
  khớp cách model staging cast; đọc model, không đoán.
- Validator chạy ở stage prepare, trên dữ liệu snapshot, trước build: ép được kiểu, cột not-null không có null,
  khóa chính không trùng. Khóa ngoại để dbt test lo như hiện nay.
- Gặp dòng sai: dừng với exit 2 trước dbt (Airflow không retry), ghi bằng chứng vào thư mục quarantine của run:
  dòng sai, _src_row, lý do. KHÔNG bỏ dòng sai rồi chạy tiếp: bỏ dòng làm lệch đối soát G/COGS với sales (§5 điểm 1).
  Không viết code sửa hay khử dòng lỗi (§5 điểm 8: dữ liệu sạch, đây không phải bài làm sạch).
- Test đối chiếu: danh sách nguồn của hợp đồng khớp _sources.yml (file này chỉ có tên bảng, không có cột);
  kiểu cột khớp kiểu cast ở staging.

Bẫy:
- grep mọi chỗ dùng SOURCES trước khi đổi cấu trúc. snapshot.validate() và prepare() đang unpack (header, count).
  ingest_raw.py, scripts/ingest/snapshot.py, scripts/build/build_silver.py có bản SOURCES cũ của riêng chúng: không sửa.
- SHA-256 của CSV đang ghim, nên dữ liệu thật không bao giờ làm validator báo lỗi. Test đột biến (đổi tên cột, sai kiểu,
  khóa trùng, null) phải dùng CSV tạm và hợp đồng tạm (tham số contract=). Không sửa data/.
- Snapshot cũ 5bd9a84aaf73 phải validate được, --snapshot-id 5bd9a84aaf73 vẫn chạy, snapshot_id không đổi.
- scripts/ingest nằm trong code_version: đổi hợp đồng thì lần chạy sau dựng bản mới. Ghi thời gian stage prepare
  trước và sau khi thêm validator.

Không làm: sửa data/; đổi công thức R/G hay model dbt; ghi quarantine rồi build tiếp; các file ở mục 8 khối mở đầu; commit.

Xong khi: test đột biến từng loại lỗi đạt (dừng trước dbt, exit 2, có file quarantine ghi lý do); test đối chiếu đạt;
scripts/pipeline/tests và test_releases.py đạt; một lần chạy local với dữ liệu thật trong --root riêng đạt, có thời gian
prepare trước/sau.
```

### 4.3 P2b: xóa code Snowflake (chỉ khi PM chốt D4 = xóa)

```text
/retail-analytics-engineering PM chốt ngày 2026-10-21: xóa code Snowflake. Danh sách chờ xóa ở docs/dwh_roadmap.md,
mục "Đổi hướng đã chốt 2026-10-18: bỏ hẳn Snowflake".

- Trước khi xóa: dbt compile target duckdb, lưu SQL đã compile. Sau khi xóa: compile lại, so từng file; phải giống hệt.
  Databricks compile chỉ khi PM cho (có --profile).
- Không đụng chữ "snowflake schema" (kiểu mô hình dữ liệu, docs/star_schema.md) và notebook.
- Sửa requirements.txt, không gỡ gói khỏi .venv.
- B7 phải xong phần code trước, vì danh sách có apps/retail_app/tests/test_ai_chat.py.

Không làm: đổi logic model; commit.
Xong khi: SQL compile trước/sau giống nhau; dbt build duckdb đạt; scripts/pipeline/tests và bộ test app đạt;
grep -ri snowflake chỉ còn nghĩa kiểu mô hình dữ liệu và tài liệu lịch sử.
```

### 4.4 P4: lên cloud và bật lịch

```text
/retail-platform-validation Làm P4 trong docs/giao_viec_agent_pipeline.md: đưa A4/A3 lên Databricks.
PM đã chốt: D2 = [lịch / target], D3 = [có / không]. Profile Databricks: [PM ghi tên].

Điều kiện trước: code A4/A3 đã commit và gộp về app/myuyen; phiên B7 KHÔNG đang chạy eval với --backend databricks.

1. Build image Airflow từ bản xuất sạch (git archive) của commit đó, không từ thư mục đang có thay đổi chưa commit,
   để code_version của bản cloud khớp đúng commit. Tạo lại các service.
2. Chạy DAG target databricks tới publish. Báo riêng từng bước: compile, build, quality gate, parity, quyền reader, publish.
   Sau publish: một lượt chat trọn vẹn (service.run_turn, provider giả) trên backend databricks gồm một câu dự báo và một câu PS,
   như automation_batch.md yêu cầu; lệnh lịch sử thấy đủ stage của run cloud.
3. D3 = có: đề xuất cách làm hỏng quality gate mà không để lại thay đổi trong nhánh chính (ví dụ sửa tạm một test singular
   trong bản xuất riêng, dựng image riêng). Hỏi PM trước khi chạy. Phải thấy: exit 2, Airflow không retry,
   con trỏ active không đổi, app public vẫn đọc bản cũ, lịch sử có bản ghi lỗi.
   Chạy trong cùng deployment Airflow, không mở root thứ hai trỏ cùng catalog. Xong thì build lại image từ commit thật
   trước mọi lần chạy tiếp hay bật lịch, và kiểm code_version của lần chạy kế khớp commit đó.
4. Bật lịch theo D2. Tham số mặc định của DAG là target=duckdb: lần chạy theo lịch không đụng Databricks trừ khi đổi
   mặc định. Không tự đổi mặc định sang databricks khi PM chưa chốt.
   (Đã làm 2026-10-19: PM chốt databricks; mặc định đọc từ `RETAIL_PIPELINE_DEFAULT_TARGET`, xem automation_batch.md mục Airflow Docker.)
5. PM push rồi Reboot bản public; kiểm thẻ "bản đang phục vụ" trên trang Sức khỏe bản public.

Không làm: xóa release cũ; đổi Secrets của app public; Kafka; commit.
Xong khi: có release mới trên cloud qua đủ gate; phép thử hỏng gate (nếu D3 = có) giữ nguyên bản đang phục vụ;
lịch đúng D2; kết quả ghi vào automation_batch.md mục Databricks.
```

### 4.5 P5: sửa tài liệu cho khớp hiện trạng

```text
/retail-platform-validation Sửa tài liệu pipeline cho khớp code và các lần chạy thật, theo docs/giao_viec_agent_pipeline.md §4.5.
Chỉ sửa tài liệu, không sửa code.

Điều kiện trước: PM đã commit đợt sửa tài liệu bỏ Snowflake (2026-10-18), vì các file dưới đây đang có thay đổi đó.

- docs/kien_truc_pipeline_tong.md: bảng §1 và §2 viết lại theo hiện trạng (giữ bản 2026-10-11 trong <details> làm lịch sử);
  thân A1/A2 ở §5 tả đúng cái đã làm: mỗi bản một schema riêng, con trỏ active, không CLONE, không cặp stage/prod;
  trạng thái A3/A4 theo kết quả P1/P2.
- docs/checklist_sdlc_gd2.md: các dòng đã xong mà còn [ ] (thiết kế stage dự báo, A2 phần cloud, chuyển bản public, A4 nếu xong).
- docs/dwh_roadmap.md: dòng "3b. Tự động hóa DE" trong bảng trạng thái.
- docs/dwh_huong_dan_pm_ba.md: câu "một lệnh" và kết quả mong đợi PASS=216.
- docs/databricks_readiness_review.md: thêm banner "lịch sử, xem automation_batch.md", không viết lại.

Mỗi khẳng định trạng thái trỏ về bằng chứng (dòng nghiệm thu trong automation_batch.md, mã release, commit).
Không thêm số chưa có bằng chứng. Không commit.
```

## 5. Nghiệm thu khi agent báo "xong"

Dùng năm câu ở §4 của `giao_viec_agent_gd2.md`, hỏi thêm ba câu:

1. **Chạy pipeline với `--root` nào, run_id và release_id nào?** Khi chạy song song với phiên AI thì không được là
   `warehouse/pipeline` của thư mục chính. Làm tuần tự theo `giao_viec_theo_so_do.md` thì được (luật 2, §3 của file đó),
   trừ lúc có phiên đang đo trên bản active local.
2. **Lần chạy lỗi để lại gì?** Exit code, `failure.json`, bản ghi lịch sử, file quarantine (A3), con trỏ active trước và sau.
3. **`code_version` của lần chạy là của commit nào?** Bản cloud phải dựng từ code đã commit.

## 6. Phối hợp với phiên AI (B7)

- **Worktree (D6 = có):** phiên pipeline làm P1, P2 trong một git worktree riêng, nhánh riêng tách từ `app/myuyen`. Ví dụ:
  `git worktree add -b pipeline/myuyen D:/retail-analytics-pipeline app/myuyen`. Mở phiên Claude mới trong thư mục đó.
  - **Tạo worktree sau P0.** Worktree chỉ có những gì đã commit. Chưa commit thì trong đó không có file này, không có quyết định
    bỏ Snowflake trong `CLAUDE.md`, và skill nạp từ `.claude/skills` của worktree là bản cũ: phiên mới làm theo chỉ dẫn cũ mà không biết.
  - File chưa rõ chủ (`retail-ai-explain/SKILL.md`, `chat_evaluation.md`, `retail-data-analysis/SKILL.md`, `scripts/skills/*`,
    `agent_levels.md`, skill `retail-forecasting`) không commit ở P0, nên worktree không có. P1, P2 không cần chúng.
  - Python dùng đường dẫn tuyệt đối `D:/retail-analytics/.venv/Scripts/python.exe`; chạy pipeline thêm `--data D:/retail-analytics/data`.
  - `warehouse/` và `.env.*.local` chỉ có ở thư mục chính. Nhiều test app đọc `warehouse/`, nên ở worktree chúng bị skip.
    **Test bị skip không tính là đạt.** Bộ test app tính ở P3, sau khi gộp về thư mục chính.
  - Gộp nhánh về `app/myuyen` là bước của PM (P3), không để agent tự gộp.
- **Không dùng worktree:** P1, P2 đợi B7 xong phần code, vì lần chạy pipeline kiểm của phiên này sẽ hỏng
  ("Code đổi giữa các stage") mỗi khi phiên B7 sửa `apps/`.
- **Không công bố lên Databricks** lúc B7 đang eval với `--backend databricks`: bản đổi giữa chừng làm ba lần chạy eval không cùng dữ liệu.
- **Vùng cấm của phiên pipeline** cho tới khi B7 xong: các file ở mục 8 khối mở đầu §4.0. B4a (bên AI) cũng sửa các biến
  reader trong `dbt_project.yml`, nên B4a và phần "hiện lần lỗi trên app" (D1 = có) không chạy cùng lúc.
- Phiên chỉ viết tài liệu (P5) chạy song song với mọi phiên khác, sau khi đợt sửa tài liệu Snowflake đã commit.
