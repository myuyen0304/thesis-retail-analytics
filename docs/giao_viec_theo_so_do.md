# Giao việc: làm cho đủ sơ đồ kiến trúc tổng (sổ tay của PM)

Soạn ngày 2026-10-18 (vai Head of AI). Đích: mọi ô trên sơ đồ `docs/references/kien_truc_pipeline_tong.png`
(bản draw.io: `kien_truc_pipeline_tong.drawio` cùng thư mục) chuyển từ **[KẾ HOẠCH]** sang **đã chạy**, trừ Kafka (hoãn, PM chốt 2026-10-11).

Cách dùng: **làm tuần tự, một phiên Claude một bước**, trong thư mục chính `D:/retail-analytics`. Mỗi lần PM dán cùng một prompt (§5);
agent tự chọn bước kế tiếp trong bảng §2, làm xong thì ghi trạng thái rồi dừng. Không cần worktree, không chạy hai phiên code cùng lúc.

**Phân vai từ S5 (PM chốt 2026-10-19): Codex thực hiện, Claude rà độc lập.** Lý do: hạn mức Claude gần hết. Codex dán prompt §5,
gọi skill bằng `$tên-skill`, không nhắn được cho phiên Claude nên tự làm trọn bước. Claude chỉ rà bài của Codex khi còn token,
không sửa song song. Mỗi lúc vẫn chỉ một phiên sửa code.

**Claude rà bài Codex trước khi commit** (PM chốt 2026-10-19: không tin hoàn toàn test do Codex tự viết). PM gửi Claude
"Codex xong Sx, rà đi" kèm báo cáo của Codex. Claude rà theo thứ tự, ghi phát hiện theo mức nặng, không tự sửa:
1. `git diff` của bước: chỉ đụng file trong phạm vi bước, không sửa `data/`, không lộ secret, không xóa test cũ để cho đạt.
2. Test có thật sự kiểm hành vi không: đọc từng test mới; loại test chỉ kiểm chữ có trong prompt, test giả lập mất chính phần
   cần kiểm, test luôn đạt. Với test chính, tạm bỏ phần code mới (`git stash` hoặc đảo điều kiện) và chạy lại: test phải trượt.
3. Đối chứng độc lập một hai con số bằng đường khác code đang kiểm (pandas từ CSV, hoặc query thẳng vào bảng).
4. Kiểm các điều bắt buộc của bước (ví dụ S5: cộng đóng góp trên thang log, bảng mới là bảng tùy chọn nên rollback bản cũ vẫn
   chạy, đủ các bước bẫy relation mới, nhãn "phân rã model, không phải nguyên nhân").
5. Câu chữ trong nhật ký và tài liệu khớp bằng chứng. Test nhanh chạy trong phiên; việc nặng theo luật 7, PM chạy.

Prompt chi tiết của từng bước nằm ở hai file đã có: [giao_viec_agent_gd2.md](giao_viec_agent_gd2.md) (phần AI, §3.x) và
[giao_viec_agent_pipeline.md](giao_viec_agent_pipeline.md) (phần DE, §4.x). File này thêm hai prompt mới (§4) và luật chạy tuần tự (§3).

---

## 1. Từng ô trên sơ đồ: đã có hay chưa

| Ô trên sơ đồ | Hiện trạng 2026-10-18 | Bước |
|---|---|---|
| Nguồn 14 CSV → Snapshot bất biến (Parquet + SHA-256) | Đã chạy | — |
| Mũi tên "kiểm data contract" Snapshot → Bronze | Một phần: mới kiểm header, số dòng, mã băm | S4 |
| Kafka (nét đứt) | Hoãn | — |
| Bronze / Silver / Gold, Databricks production, DuckDB local | Đã chạy | — |
| Task `forecast_train_score` trong dòng DAG | Chưa đúng sơ đồ: dự báo chạy **bên trong** task `ingest_and_dbt_build` | S2 |
| ① Dự báo time series | Đã chạy: log + SARIMAX, ARIMA, LightGBM, bản gộp; model chính `lgbm_full / direct` chọn bằng backtest. **LSTM chưa làm** | D7 |
| `reporting.rpt_forecast_*` | Đã chạy, local và Databricks | — |
| Quality gate → publish / giữ bản đang phục vụ | Đã chạy. Chưa thử cố ý làm hỏng gate trên cloud | S6 |
| "Điều phối + giám sát" của Airflow | Điều phối đã chạy. Giám sát một phần: chưa có lịch sử lần chạy, chưa có thẻ bản đang phục vụ | S3 |
| Trang PS1–PS5, Sức khỏe dữ liệu, Trang Dự báo | Đã chạy | — |
| LLM router chọn tool | Có ở dạng LLM tự chọn tool; chưa có luật chọn level và nghiệm thu | S1 |
| L1 Query, L2 Dashboard (`show_chart`, deep link), L3 Forecast | Đã chạy, cả bản public | — |
| L4 Explainable tool | Chưa làm | S5, S7 |
| RAG BM25 | Chưa làm | S8 |
| Evidence check → Answer | Đã chạy | — |
| Bản thân sơ đồ | Lệch: còn ghi [KẾ HOẠCH] cho các ô đã chạy; hộp ① ghi thước MAE/RMSE/sMAPE và "COGS qua tỷ lệ", khác cái đã chốt | S10 |

## 2. Các bước, theo thứ tự

Agent cập nhật cột **Trạng thái** khi làm xong (`xong YYYY-MM-DD` hoặc `cắt`), kèm một chữ dẫn tới bằng chứng.

| Bước | Việc | Ô trên sơ đồ | Skill | Prompt | Điều kiện trước | Trạng thái |
|---|---|---|---|---|---|---|
| S0 | **Dọn trước (PM):** chốt chủ các thay đổi chưa commit trong `apps/` (`evidence.py`, `test_ai_forecast.py`, các trang và test PS1–PS4); commit đợt tài liệu bỏ Snowflake và ba file giao việc | — | — | — | — | một phần 2026-10-18: rv12f là của Codex, PM giữ, commit `946f507` + `c2e443f`; trang PS1–PS5 do Codex đang sửa (chặn S2); tài liệu Snowflake chưa commit (không chặn S1) |
| S1 | B7: router chọn level, bộ held-out, báo cáo AI4 (Must) | LLM router | `retail-ai-explain` | gd2 §3.7 | phần rv12f của S0 (đã xong). Không đụng `views/`, `ui/common.py` khi Codex còn sửa trang PS | xong 2026-10-18: held-out `b7` local 64/72, Databricks 21/24 (đạt cả máy lẫn tay); commit `5722b9e`…`892cbc6`; S1b (K17, K16, K08) commit `b34d3e9`…`929c1b8`; [ai_eval_b7_nghiem_thu.md](ai_eval_b7_nghiem_thu.md) |
| SPS | B8: AI giải thích trên từng trang PS1–PS5 (PM chốt 2026-10-18, sổ quyết định `ke_hoach_ai_gd2.md` §2), kèm sửa lỗi đợt bố cục mới của Codex | Streamlit App | `retail-ai-explain` + `retail-bi-product` (+ `retail-analytics-engineering` nếu thêm cột dbt) | — | Codex đã commit bố cục mới (`c3e0d95`…`7edbdfe`) và dừng sửa trang PS; Claude làm thay. Không sửa prompt chat (`service.py`), `evidence.py`, `tools.py` khi S1 còn mở | dev xong 2026-10-18, đã commit (`8d89b22`…`4ef1b24`, prompt trang …b `eafc91d`); LLM thật: Databricks 5/5 ok, local 15 lượt đọc tay 12/15, 0 câu sai số. Chờ PM quyết siết thêm PAGE_NOTE (từ xếp hạng, kết luận thống kê) rồi đo lại bằng lượt mới; `ke_hoach_ai_gd2.md` §8 |
| S2 | Tách dự báo thành task `forecast_train_score` riêng | dòng DAG | `retail-platform-validation` | §4.1 file này | S1; SPS xong và commit (pipeline băm cả `apps/`) | xong 2026-10-18, commit `93f3309`…`c847816`: `run` local `s2-20261018-02` (PM chạy ngoài Claude Code) publish `06f157ee…` (năm stage, dbt PASS=223), dự báo lệch 0 so với `dbx-20261017-01`; image / DAG Docker để S6 ([automation_batch.md](automation_batch.md), mục Kiểm chứng) |
| S3 | A4 giám sát: lịch sử lần chạy, thẻ bản đang phục vụ, độ tươi | Airflow giám sát | `retail-platform-validation` (+ `retail-bi-product`) | pipeline §4.1 | S2. D1 = không (PM 2026-10-18) | dev xong 2026-10-19, chưa commit: lịch sử `<root>/history.jsonl` (cloud: `retail_control.run_history`, không grant reader) + lệnh `cli history`; giờ công bố `active_since` cạnh con trỏ; thẻ "Bản dữ liệu đang phục vụ" ở trang Sức khỏe; code app cũ đọc payload mới đạt. Chuỗi chạy PM trong `warehouse/pipeline-s3`: 2 bản, rollback đạt / bỏ qua / mã sai, 18 dòng lịch sử. Cloud chưa chạy ([automation_batch.md](automation_batch.md), mục Giám sát và Kiểm chứng) |
| S4 | A3 kiểm data contract: kiểu, nullable, khóa chính, quarantine | mũi tên data contract | `retail-platform-validation` + `retail-analytics-engineering` | pipeline §4.2 | S3 | dev xong 2026-10-19, chưa commit: `COLUMNS` / `KEYS` trong `source_contract.py` (kiểu khớp cast staging), validator `scripts/pipeline/contract.py` ở prepare, dòng sai → quarantine + exit 2; test 24 mới; chuỗi chạy PM trong `warehouse/pipeline-s4`: publish `e9e6f92f…`, `--snapshot-id 5bd9a84aaf73` đạt, prepare 21 giây (trước 13–15 giây). Cloud chưa chạy ([automation_batch.md](automation_batch.md)) |
| S5 | B4a: dữ liệu giải thích dự báo `rpt_forecast_explain` | L4 (phần dữ liệu) | `retail-forecasting` | gd2 §3.5, prompt thứ nhất | S4 | chưa làm |
| S6 | **Lên cloud một lần** cho S2–S5: **trước hết** PM push và Reboot bản public (luật 6, §3); rồi build image, chạy DAG Databricks, thử hỏng gate, bật lịch | Databricks, quality gate | `retail-platform-validation` + `databricks:databricks-core` | pipeline §4.4, theo luật 6 | PM cho commit code S1–S5 | chưa làm |
| S7 | B4b: tool `explain_forecast`. **Kèm, thêm khi tăng `PROMPT_VERSION` ở S7:** dòng router cho K02 (khoảng nhiều năm trùng ranh giới giai đoạn → `get_revenue_trend` phases) và K22 (tháng không kèm năm có ở cả 2023 và 2024 → hỏi lại năm), xem `ai_eval_b7_nghiem_thu.md` §7. **Hạn mức token:** sau B7, 3 câu tốn nhất chỉ còn dư khoảng 1.300 token dưới 200 nghìn (`test_tran_token_xau_nhat_con_du`); schema tool mới và dòng router phải tính lại hạn mức | L4 Explainable tool | `retail-ai-explain` | gd2 §3.5, prompt thứ hai | S5 (S6 nếu muốn eval trên cloud) | chưa làm |
| S8 | B5: RAG `search_knowledge`. **Hạn mức token:** như S7, schema tool mới, dòng router và đoạn văn trả về đều cộng vào cận trên mỗi lần gọi; kiểm `test_tran_token_xau_nhat_con_du` trước khi giao | RAG | `retail-ai-explain` | gd2 §3.9 | S7 hoặc S7 bị cắt | chưa làm |
| S9 | Đưa lên bản public: PM push, Reboot; một lượt chat trọn vẹn trên public hỏi L4 và RAG; bổ sung kết quả nhóm eval L4/RAG vào `docs/ai_eval_b7_nghiem_thu.md`; **chạy lại bộ held-out của S1 một lần** (cùng mã băm, không sửa câu) trên `PROMPT_VERSION` cuối, ghi thành dòng hồi quy dù kết quả thế nào | Streamlit App | `retail-ai-explain` | — | S7, S8 | chưa làm |
| S10 | Vẽ lại sơ đồ theo hiện trạng và sửa tài liệu cho khớp | cả sơ đồ | `retail-platform-validation` | §4.2 file này | S9 | chưa làm |

**Lịch gợi ý (hạn 2026-10-25):** S0 10-18 → 10-19 · SPS 10-18 → 10-20 · S1 10-19 → 10-21 · S2, S3 10-21 → 10-22 · S4, S5 10-22 → 10-23 ·
S6 10-23 · S7, S8 10-23 → 10-24 · S9, S10 10-24 → 10-25.

**Trễ thì cắt theo thứ tự:** S8 → S7 → S5 → S4 → phần bật lịch của S6. Bước bị cắt giữ viền [KẾ HOẠCH] trên sơ đồ ở S10.
**Không cắt:** S1 (Must), SPS (PM chốt mỗi PS có AI giải thích), S6 (bản cloud phải có code đã làm), S10 (sơ đồ và tài liệu phải nói đúng).

**Quyết định PM** (mã D1–D6 ở `giao_viec_agent_pipeline.md` §2; đề xuất mặc định ghi ở đó). Thêm một mục:

| Mã | Câu hỏi | Đề xuất mặc định | Hỏi lúc nào |
|---|---|---|---|
| D7 | Làm LSTM cho đúng chữ trên sơ đồ? | **Không.** PM đã xác nhận 2026-10-13 được dùng model khác, chọn bằng backtest; LSTM là Could. Ở S10 hộp ① ghi đúng model đã chạy, LSTM ghi "không làm, lý do…" | Trước S10. Chọn làm thì thêm bước S8b `retail-forecasting` sau S8 |

## 3. Luật chạy tuần tự (thay cho các khối mở đầu cũ)

Khi làm theo file này, dùng khối §3.0 của `giao_viec_agent_gd2.md` cho mọi bước, kể cả bước DE, với ba chỗ đổi:

1. **Không có phiên code nào chạy song song.** Bỏ qua mục 8 (vùng cấm) của khối §4.0 trong `giao_viec_agent_pipeline.md`
   và toàn bộ §6 của file đó (worktree, gộp nhánh).
2. **Chạy pipeline local được công bố vào `warehouse/pipeline`** (mặc định), miễn là không có eval nào đang chạy.
   Báo cáo ghi run_id và release_id. Chạy cloud chỉ qua deployment Airflow hiện có (root `warehouse/pipeline/docker`).
3. **Nhật ký:** bước AI ghi `ke_hoach_ai_gd2.md` §8; bước DE ghi `automation_batch.md`. Bước nào cũng thêm một mục bàn giao
   ở `dwh_huong_dan_pm_ba.md` §9 và cập nhật cột Trạng thái ở §2 file này.

Thêm các luật:

4. **Mỗi tool mới (S7, S8) thêm một dòng vào mục router** trong system prompt (`service.py`) và tăng `PROMPT_VERSION`.
   Bộ held-out của S1 giữ nguyên, không sửa để chạy lại cho đạt; L4 và RAG có nhóm eval riêng.
5. **Bước đụng quyền đọc relation mới (S5, S7)** đi đủ mục "Bẫy khi thêm tool đọc relation mới" trong
   `.agents/skills/retail-ai-explain/references/agent_levels.md`. Sau khi cấp quyền, kiểm bằng một lượt chat trọn vẹn
   (`service.run_turn`, provider giả, một câu dự báo và một câu PS), như sự cố 2026-10-17 đã dạy.
6. **S6: app trước, pipeline sau** (đúng thứ tự "Thứ tự chuyển bản public" trong `automation_batch.md`). Bản public đang chạy code cũ,
   trong đó `OPTIONAL_RELATIONS` (`ai_explain/tools.py`) chưa có `rpt_forecast_explain`. Nếu chạy DAG trước, stage validate cấp cho
   SP AI quyền đọc bảng này và chat public bị khóa ngay. Vì vậy S6 làm theo thứ tự:
   (a) PM push code S1–S5 đã commit, Reboot bản public;
   (b) một lượt chat trọn vẹn trên public với bản đang phục vụ hiện tại (`b25b3e47…`, chưa có bảng mới; đồng thời chứng minh
       đường "bảng tùy chọn chưa có" vẫn chạy);
   (c) bản Databricks Apps (dùng chung SP AI) đã dừng hoặc cùng code; chưa rõ thì hỏi PM;
   (d) rồi mới làm prompt pipeline §4.4 (bước 5 của prompt đó, push và Reboot, coi như đã làm ở (a)).
7. **Việc chạy lâu và nặng thì PM tự chạy** (PM chốt 2026-10-19): chạy pipeline, train hay backtest model, eval LLM nhiều lượt,
   bộ test đầy đủ kéo dài. Agent viết sẵn lệnh PowerShell dán được (thư mục, `$env:PYTHONUTF8=1`, lệnh, run_id, dấu hiệu xong),
   gửi PM, rồi chỉ đọc kết quả (context.json, manifest, log). Test nhanh vài phút vẫn chạy trong phiên. Lý do: máy 15,7 GB RAM,
   Claude Code từng hai lần tự dừng pipeline vì thiếu RAM (2026-10-18), và ngồi chờ lần chạy dài tốn token.

## 4. Hai prompt mới

### 4.1 S2: tách dự báo thành task riêng của DAG

```text
/retail-platform-validation Làm S2 trong docs/giao_viec_theo_so_do.md: tách stage dự báo thành task riêng, đúng dòng DAG
trên sơ đồ: prepare_snapshot → forecast_train_score → ingest_and_dbt_build → quality_and_reader_gate → publish_release.

Đọc trước: docs/automation_batch.md mục "Stage dự báo"; scripts/pipeline/cli.py (execute, forecast_stage);
deploy/airflow/dags/retail_batch_pipeline.py; scripts/pipeline/tests/test_pipeline.py.

Việc:
- Thêm stage `forecast` vào CLI, giữa prepare và build. Lệnh `run` chạy đủ năm stage. Kết quả vẫn ghi vào
  runs/<run_id>/forecast/ và được dùng lại khi khớp snapshot, model_version và hash file, như hiện nay.
- build đòi stage forecast đã xong, thiếu thì báo lỗi rõ. Run bỏ qua (cùng snapshot và code) thì stage forecast cũng bỏ qua.
  run_id đang dở từ trước thay đổi: chạy tiếp được, hoặc báo rõ phải tạo run_id mới.
- Lỗi hợp đồng dự báo vẫn exit 2, Airflow không retry. Task dự báo có execution_timeout đủ cho lần chậm nhất đã đo (956 giây).

Không làm: sửa scripts/forecast/ (ứng viên, tham số, luật chọn); sửa dbt; commit.

Không cài Airflow vào .venv. File DAG kiểm bằng AST như test hiện có trong test_pipeline.py (kiểm đủ năm task, đúng thứ tự);
import DAG thật (airflow dags list-import-errors trong image) để dành cho S6.

Xong khi: test pipeline cũ và test mới cho stage forecast (đạt, bỏ qua, lỗi hợp đồng, retry dùng lại kết quả) đạt;
một lần `run` local tạo bản qua quality gate, dự báo trùng bản trước (so bằng scripts/ops/so_sanh_du_bao.py);
test AST của DAG đạt. Build image và chạy DAG Docker để dành cho S6.
```

### 4.2 S10: vẽ lại sơ đồ và sửa tài liệu

```text
/retail-platform-validation Làm S10 trong docs/giao_viec_theo_so_do.md: cập nhật sơ đồ kiến trúc tổng và tài liệu theo hiện trạng.

Sơ đồ: sửa docs/references/kien_truc_pipeline_tong.drawio (giữ bố cục, chỉ đổi ô và chữ), xuất lại PNG cùng tên
(drawio-ai render), rồi xem PNG kiểm bằng mắt.
- Ô đã chạy (có bằng chứng trong automation_batch.md hoặc ke_hoach_ai_gd2.md §8): viền liền, bỏ chữ [KẾ HOẠCH].
- Ô chưa làm hoặc bị cắt: giữ viền tím [KẾ HOẠCH]. Kafka giữ nét đứt, nhãn HOÃN.
- Hộp ①: ghi đúng model đã chạy (log + SARIMAX, ARIMA, LightGBM, bản gộp; model chính LightGBM chọn bằng backtest),
  thước chọn là điểm ngày kết hợp (MAE G + MAE COGS)/2, COGS hai cách cùng dự thi. LSTM ghi theo quyết định D7.
- Thêm nhãn cho phần mới nếu đã làm: lịch sử lần chạy (giám sát), quarantine (data contract), task forecast_train_score.
- docs/references/ bị loại khỏi git trên máy này (.git/info/exclude): báo PM, hỏi có muốn đưa sơ đồ vào git không.

Tài liệu: làm prompt §4.5 của docs/giao_viec_agent_pipeline.md, và sửa mermaid §3 của docs/kien_truc_pipeline_tong.md
cho cùng hiện trạng với sơ đồ.

Không thêm số chưa có bằng chứng. Không commit.
Xong khi: mọi ô trên sơ đồ khớp cột "Hiện trạng" mới của bảng §1 file này (agent cập nhật bảng đó); PM xem PNG và đồng ý.
```

## 5. Prompt PM dán mỗi lần

Mở phiên Claude mới trong `D:/retail-analytics`, dán:

```text
Làm việc theo docs/giao_viec_theo_so_do.md. Đọc §1–§3. Chọn bước ĐẦU TIÊN trong bảng §2 có trạng thái "chưa làm" mà điều kiện
trước đã đủ; nếu đó là bước của PM (S0, hoặc cần PM cho commit) thì dừng và nói PM cần làm gì. Gọi đúng skill ghi trong bảng
bằng công cụ Skill, làm đúng prompt của bước đó, theo luật §3. Gặp quyết định D1–D7 chưa chốt thì hỏi PM, kèm đề xuất mặc định.
Xong bước: cập nhật cột Trạng thái, trả lời PM sáu câu nghiệm thu ở §4 của docs/giao_viec_agent_gd2.md (bước DE S2–S4, S6
trả lời thêm ba câu ở §5 của docs/giao_viec_agent_pipeline.md), rồi DỪNG, không tự sang bước sau.
```

Agent báo xong thì PM kiểm bằng chứng (các câu nghiệm thu), cho commit nếu đạt, rồi mở phiên mới và dán lại đúng prompt trên.
