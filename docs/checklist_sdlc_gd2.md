# Checklist công việc GĐ2 theo SDLC

Cập nhật **2026-10-12**. Trạng thái ghi theo lần rà soát ngày này.

File này chỉ để **theo dõi việc**. Thiết kế chi tiết nằm ở các tài liệu được dẫn; không chép lại vào đây để tránh lệch:

- [kien_truc_pipeline_tong.md](kien_truc_pipeline_tong.md): lộ trình A/B, ưu tiên, cách kiểm từng bước;
- [automation_batch.md](automation_batch.md): pipeline đã có, thứ tự chuyển bản public;
- [feedback_ps1_ps5_streamlit_ai_20261010.md](feedback_ps1_ps5_streamlit_ai_20261010.md): FB01–FB07;
- [agent_skill_evaluations.md](agent_skill_evaluations.md): eval skill.

**Ký hiệu:**

- `[x]` đã làm **và đã kiểm** trong lần rà soát;
- `[ ]` chưa xong. Ghi thêm "một phần" (làm dở), "chưa kiểm" (chưa ai xác nhận trạng thái) hoặc "chưa làm".

**Người làm:**

- PM/BA: người dùng;
- Dev: Claude hoặc Codex;
- TV2: thành viên còn lại;
- Thầy: giảng viên hướng dẫn.

**Mức ưu tiên:** Must / Should / Could / Hoãn, lấy theo `kien_truc_pipeline_tong.md` §5.

**Skill:** cách dùng ở [agent_workflows.md](agent_workflows.md), mục "Chọn skill theo việc".

- Mở terminal ở thư mục gốc repo, gọi `claude`, rồi gõ tên skill kèm yêu cầu trong cùng một tin nhắn. Ví dụ: `/retail-forecasting Làm mục B1 trong docs/checklist_sdlc_gd2.md. Chưa code.`
- Codex gọi giống vậy, đổi `/` thành `$`.
- Một dòng ghi hai skill: gọi skill đầu, nhắc skill sau trong yêu cầu.
- "Không cần skill": việc của người, hoặc chỉ là chạy lệnh có sẵn.
- `developing-with-streamlit` và `databricks:databricks-core` là skill plugin, chỉ có trên máy đã cài plugin. Máy không có thì agent tra tài liệu chính thức.

## Định nghĩa xong cho mỗi chức năng

Thêm ngày 2026-10-12 theo yêu cầu PM/BA. Một chức năng chỉ được tick `[x]` khi đủ 5 điều:

1. **Code** chạy được trên backend đã nêu.
2. **Test** đi kèm và đã đạt. Ghi rõ phần nào chưa chạy, ví dụ cloud hay PostgreSQL.
3. **Tài liệu hướng dẫn** cho chức năng. Đặt trong `docs/`: một file riêng `huong_dan_<chuc_nang>.md`, hoặc một mục trong tài liệu sẵn có của chức năng đó.
4. **Mục nhật ký bàn giao** trong `dwh_huong_dan_pm_ba.md` §9. Mục này tóm tắt và trỏ tới tài liệu hướng dẫn, không chép lại.
5. **Demo cho PM/BA:** đã làm gì, trả lời PS hay yêu cầu nào, kiểm bằng gì, còn gì chờ quyết.

Tài liệu hướng dẫn gồm đủ các mục sau, viết bằng ngôn ngữ dễ hiểu:

- chức năng làm gì, cho ai dùng, trả lời PS hay yêu cầu nào;
- cách dùng (người xem app) hoặc cách chạy (người vận hành): từng bước, lệnh, màn hình;
- đầu vào, đầu ra, xem kết quả ở đâu;
- cách kiểm là chạy đúng: test nào, số đối chứng nào;
- lỗi thường gặp, cách xử lý, cách quay lại bản trước nếu có;
- giới hạn, phần chưa làm, quyết định còn chờ PM/BA;
- file code và test liên quan.

**Tài liệu của các chức năng đã làm:**

| Chức năng | Tài liệu hướng dẫn | Mục §9 |
|---|---|---|
| Pipeline theo bản dữ liệu + Airflow (A1, A2 local) | [automation_batch.md](automation_batch.md), viết cho người vận hành | Có, ghi ngày 2026-10-12 |
| Sửa lỗi khóa chat khi chuyển bản public | [automation_batch.md](automation_batch.md), mục "Thứ tự chuyển bản public…" | Có, chung mục trên |
| FB07, FB01 (giao diện) | Chưa có; chờ làm xong hết FB01 rồi viết chung | Có nhắc trong mục trên, chưa có mục riêng |
| Skill `retail-forecasting`, mở rộng `retail-ai-explain` | [agent_workflows.md](agent_workflows.md). Đây là công cụ cho dev, không phải chức năng sản phẩm | Không cần |

**Tài liệu phải có khi làm xong các chức năng sắp tới:**

- [ ] **B2 dự báo:** `huong_dan_du_bao.md` · Skill: `/retail-forecasting`. Gồm cách chạy lại backtest, cách đọc bảng so sánh model, model card (dữ liệu train, cửa sổ, seed, giới hạn), cách sinh file nộp.
- [ ] **B3 trang Dự báo và `get_forecast`** · Skill: `/retail-bi-product` + `/retail-ai-explain`. Gồm cách đọc trang, ý nghĩa các nhãn ("dự báo", "G – doanh thu gộp", khoảng dự báo), câu chat hỏi được và không hỏi được.
- [ ] **Chuyển bản public lên cloud** · Skill: `/retail-platform-validation`. Ghi lại lần chạy thật vào `automation_batch.md`: ngày, mã bản, kết quả từng bước, sự cố nếu có.
- [ ] **A4 theo dõi lần chạy, B6, B4, B5** · Skill: dùng skill của chính chức năng đó (xem dòng tương ứng ở mục 3). Mỗi chức năng một hướng dẫn khi làm xong.

## Tiến độ so với lịch 14 ngày

Giả định D1 = 2026-10-11, D14 = 2026-10-24; hạn cứng 2026-10-25. Hôm nay là D2.

- **Đi trước lịch:** A1 (Airflow) đã xong; theo lịch là D2–4.
- **Đang trễ, nằm trên đường găng:**
  - B1 (hợp đồng dự báo) xếp ở D1. Bản nháp xong ngày 2026-10-13, chờ PM chốt §0 của [hop_dong_du_bao.md](hop_dong_du_bao.md).
  - B2 và B3 (đều Must) cần B1, nên B1 là việc kế tiếp.

---

## 1. Lập kế hoạch và yêu cầu

**Qua pha khi:** có hợp đồng dự báo được BA chốt, và thầy đã biết các điểm lệch so với sơ đồ.

- [x] **Chốt hướng GĐ2** (PM/BA, 2026-10-11) · Không cần skill.
  - Đã chốt: hạn 10-25 cứng; ①②③ là thứ tự ưu tiên; target G theo ngày và COGS qua tỷ lệ; Airflow chạy Docker local.
  - Ghi ở `CLAUDE.md` §1 và `kien_truc_pipeline_tong.md` §4.
- [x] **Kafka hoãn** · Không cần skill. Đã ghi vào `CLAUDE.md` §1, `kien_truc_pipeline_tong.md` §4 và `dwh_roadmap.md`.
- [ ] **Báo thầy** · PM/BA · Must · chưa làm · Không cần skill. Hai nội dung:
  - Kafka hoãn, kèm 3 lý do ở §4;
  - dự báo thành lõi GĐ2.

  Xong khi: có phản hồi của thầy, ghi vào docs.
- [ ] **Duyệt nhãn R mới** "doanh thu đơn đã giao" (FB01) · PM/BA · Must · chưa làm.
  - Nhãn này đã có trong code và sẽ lên bản public ở lần deploy tới.
  - PM quyết. Muốn agent soạn các phương án đặt tên thì dùng `/retail-metric-design`.
- [ ] **Quyết có chuyển bản public sang chế độ versioned trước 10-25 không** · PM/BA · Must · chưa làm.
  - Không chuyển thì bản public vẫn đọc `reporting.*` cũ, và số dự báo chưa có đường an toàn lên bản public.
  - PM quyết. Muốn agent phân tích lợi hại thì dùng `/retail-platform-validation`.
- [ ] **B1 – Hợp đồng dự báo** · PM/BA · Must · **nháp xong 2026-10-13, chờ PM chốt** · Skill: `/retail-forecasting` + `/retail-metric-design` (phần định nghĩa target).
  - Xong khi có đủ: target, grain, horizon, biến lịch, cách backtest, mốc so sánh.
  - Mỗi mục ghi rõ nhãn đã chốt hay đề xuất.
  - Bản nháp: [hop_dong_du_bao.md](hop_dong_du_bao.md). PM chốt 9 quyết định Q1–Q9 ở §0 thì đánh dấu xong.
- [ ] **Cửa sổ train** (toàn chuỗi kèm biến chế độ, hay chỉ từ 2019) · PM/BA · Must · còn mở · Skill: `/retail-forecasting`. Chốt bằng bảng backtest ở B2.

## 2. Phân tích và thiết kế

**Qua pha khi:** thiết kế khớp với code đã có, và stage dự báo đã có thiết kế.

- [x] **Kiến trúc tổng** ở `kien_truc_pipeline_tong.md` · Không cần skill. Đây là thiết kế đề xuất.
- [x] **Skill `retail-forecasting` và mở rộng `retail-ai-explain`** · Không cần skill; sửa skill theo `agent_workflows.md`.
  - Kiểm cấu trúc PASS 7/7 skill.
  - Ngày 2026-10-12 sửa để dự báo nằm trong `reporting.rpt_forecast_*`, không dùng schema `forecast` riêng.
- [ ] **Viết lại thân A1/A2 trong `kien_truc_pipeline_tong.md`** · Dev · Should · chưa làm · Skill: `/retail-platform-validation`.
  - Thân hiện vẫn tả cặp stage/prod và CLONE.
  - Cái đã làm: mỗi bản một schema riêng, DuckDB local, không CLONE.
  - Hiện mới có ghi chú ở đầu file.
- [ ] **Thiết kế stage dự báo trong pipeline** · Dev · Must · chưa làm · Skill: `/retail-forecasting` + `/retail-platform-validation`. Gồm:
  - vị trí đề xuất: sau snapshot, trước dbt build;
  - dùng lại kết quả khi snapshot và code dự báo không đổi;
  - thêm thư mục code dự báo vào `code_version()` trong `scripts/pipeline/cli.py`.
- [ ] **Giữ được rollback khi thêm relation mới** · Dev · Could · chưa làm · Skill: `/retail-platform-validation` + `/retail-ai-explain`.
  - Hiện thêm `rpt_forecast_*` thì không pin hay rollback được về các bản dựng trước đó.
  - Không làm thì ghi rõ giới hạn này (`agent_levels.md`, bước 5).
- [ ] **A3 – Data contract đầy đủ** · Dev · Should · một phần · Skill: `/retail-platform-validation` + `/retail-analytics-engineering` (đối chiếu `_sources.yml`).
  - Đã có: kiểm header, số dòng, mã băm.
  - Thiếu: kiểu dữ liệu, nullable, PK, quarantine.
- [ ] **Sửa `ai_explain_plan.md` §8 và ca E15** khi làm B3 · Dev · Must · chưa làm · Skill: `/retail-ai-explain`. Hai chỗ này vẫn coi "dự báo 2023" là câu phải từ chối.

## 3. Xây dựng

**Qua pha khi:** mọi mục Must có code, và có test đi kèm.

**A0 – Dọn nền:**

- [x] **FB07** (đổi nguồn dữ liệu thì xóa lịch sử chat) · Skill khi sửa tiếp: `/retail-ai-explain`. Đã sửa, test đạt ngày 2026-10-12.
- [ ] **FB01** · Dev · Must · một phần · Skill: `/retail-bi-product` (trang) + `/retail-ai-explain` (catalog của chat). Còn chữ "thực nhận" ở:
  - `views/tong_quan.py` dòng 7 và 54;
  - `views/ps1_do_dung.py` dòng 7, 42 và 93;
  - nhãn `capture_rate` trong `ai_explain/metric_catalog.py` dòng 105;
  - deck.
- [ ] **FB02** · Dev · Must · một phần · Skill: `/retail-bi-product` + `/retail-ai-explain`.
  - Đã sửa: câu trên trang PS1.
  - Còn lại: catalog AI vẫn có cách gọi "thất thoát" cho phần chênh G−R; slide 5 chưa sửa.
- [ ] **FB03–FB06** · Dev · chưa kiểm. Skill theo từng mục:
  - FB03 (cách đọc KPI): `/retail-bi-product`;
  - FB04 (đơn vị tiền, phạm vi thời gian): `/retail-metric-design`;
  - FB05 (phạm vi AI): `/retail-ai-explain`;
  - FB06 (quy ước còn là đề xuất): `/retail-metric-design`.
- [ ] **Tài liệu lệch code** · Dev · Must · một phần.
  - ~~Header `retail_dbt/dbt_project.yml` vẫn ghi Snowflake là production.~~ Đã sửa 2026-10-18: ghi Databricks production, Snowflake đã bỏ.
  - ~~Header `retail_dbt/profiles.yml` vẫn ghi Snowflake / GitHub Actions.~~ Đã sửa 2026-10-18 (commit `d3249a1`).
  - `databricks_readiness_review.md` chưa sửa. Skill: `/retail-platform-validation`.
  - `dwh_huong_dan_pm_ba.md`: dòng 127 vẫn có câu "một lệnh"; dòng 397 vẫn ghi kết quả mong đợi là `PASS=216`, nay là 217. Không cần skill.
  - README vẫn ghi Kafka là "mốc tiếp theo", ngược với quyết định hoãn. Không cần skill.
- [ ] **Git** · PM/BA + Dev · Must · chưa làm · Không cần skill.
  - Kéo bản mới: `app/myuyen` đang chậm 1 commit, `main` chậm 122 commit.
  - Hai nhánh D2 của TV2 chưa merge (theo rà soát ngày 2026-10-11).
- [ ] **File `relational diagram.drawio.svg`** bị xóa không rõ lý do · PM/BA · chưa kiểm · Không cần skill. Quyết giữ xóa hay khôi phục.

**GĐ1 – Tự động hóa DE:**

- [x] **A1 – Airflow Docker local và pipeline theo bản** (Codex, 2026-10-11) · Skill khi sửa tiếp: `/retail-platform-validation`.
  - Chạy với target DuckDB, không phải PostgreSQL như plan.
  - Đã kiểm: 217/217 node, G/COGS khớp 3.833 ngày, 33 bảng, rollback qua lại.
- [x] **A2, phần local:** quality gate, con trỏ bản đang phục vụ, rollback · Skill khi sửa tiếp: `/retail-platform-validation`.
- [x] **Sửa lỗi khóa chat khi chuyển đổi** (2026-10-12) · Skill khi sửa tiếp: `/retail-ai-explain` + `/retail-platform-validation`. Gồm `_release_scope` trong `dwh/guarded.py` và `reader_grants` trong `scripts/pipeline/cli.py`. Mới kiểm local.
- [ ] **A2, phần cloud** · PM/BA + Dev · Must · chưa làm · Skill: `/retail-platform-validation` + `databricks:databricks-core`. Xem mục 5.
- [ ] **A4** · Dev · Should · chưa làm. Gồm ba phần, mỗi phần một skill:
  - bảng `ops.pipeline_run`: `/retail-platform-validation`;
  - dbt source freshness: `/retail-analytics-engineering`;
  - thẻ "lần chạy gần nhất" trên trang Sức khỏe dữ liệu: `/retail-bi-product`.
- [ ] **A5 – Kafka** · **Hoãn**. Nếu sau này làm thì dùng `/retail-platform-validation`.

**GĐ2 – Dự báo và AI agent:**

- [ ] **B2 – Notebook so sánh model** · TV2 hoặc Dev · Must · chưa làm · Skill: `/retail-forecasting`. Mọi ô con bên dưới dùng cùng skill này.
  - Mỗi notebook một chủ; ghi chủ vào README trước khi tạo.
  - Không xây tiếp lên `baseline.ipynb`.
  - Mọi model chạy trên cùng các fold backtest. Giao thức ở `retail-forecasting`, file `references/forecast_protocol.md`.

  Làm theo thứ tự dưới đây. Ba model ARIMA, log + SARIMAX, LSTM (ANN) lấy từ sơ đồ thầy (`references/pipeline-gd2.jpg`). LSTM làm sau cùng; nếu trễ vẫn bàn giao được hai model đầu.
  - [ ] **Mốc so sánh** · Must.
    - Seasonal naive lặp năm trước.
    - Một biến thể lặp cùng kỳ hai năm trước, để bắt chu kỳ tháng 8.
    - `baseline.ipynb`.

    Xong khi: có sai số của các mốc trên từng fold.
  - [ ] **ARIMA** · Must.
    - Chạy trên chuỗi G theo ngày.
    - Bậc (p, d, q) chọn trên phần train của fold, không chọn trên phần chấm.

    Xong khi: có sai số từng fold, so được với mốc so sánh.
  - [ ] **log + SARIMAX** · Must.
    - Mô hình hóa log(G).
    - Biến ngoại sinh chỉ suy từ lịch: Fourier hoặc tháng, ngày-trong-tháng, cờ tháng 8 năm lẻ, cờ chế độ sau 2018.
    - Không dùng thứ trong tuần.

    Xong khi: có sai số từng fold, và khoảng dự báo lấy trên thang log rồi exp ngược lại.
  - [ ] **LSTM (ANN)** · Must, làm sau cùng.
    - Mạng nhỏ.
    - Scaler fit riêng trên phần train của từng fold.
    - Chạy vài seed và báo độ dao động giữa các seed.

    Xong khi: có sai số từng fold, và khoảng dự báo tính từ quantile phần dư backtest.
  - [ ] **Tỷ lệ COGS/G** · Must. Dự báo tỷ lệ rồi tính COGS = G × tỷ lệ, dùng chung cho mọi model.

    Xong khi: tỷ lệ tháng 8 năm lẻ ra > 1 (khoảng 1,36).
  - [ ] **Chọn model và chốt cửa sổ train** · PM/BA + Dev · Must. Chọn bằng bảng backtest ở mục 4. Model không vượt seasonal naive thì báo thẳng.
- [ ] **B2 – Stage dự báo trong pipeline** · Dev · Must · chưa làm. Ra `reporting.rpt_forecast_daily` và `rpt_forecast_backtest`, kèm test dbt. Skill:
  - `/retail-forecasting` (nội dung dự báo);
  - `/retail-analytics-engineering` (model dbt và test);
  - `/retail-platform-validation` (stage trong pipeline).
- [ ] **B2 – File nộp** `Date, Revenue, COGS` · Dev · Must · chưa làm · Skill: `/retail-forecasting`. Ghi vào `data/`, **không commit**.
- [ ] **B3 – Trang Dự báo và tool `get_forecast`** · Dev · Must · chưa làm.
  - Trang Dự báo: `/retail-bi-product`, kèm `developing-with-streamlit` cho phần kỹ thuật Streamlit.
  - Tool chat: `/retail-ai-explain`. Làm đủ 7 bước trong `references/agent_levels.md` của skill này.
- [ ] **B6 – `show_chart`** · Dev · Should · chưa làm · Skill: `/retail-ai-explain` + `/retail-bi-product`.
- [ ] **B4 – `explain_forecast`** · Dev · Could · chưa làm · Skill: `/retail-ai-explain` + `/retail-forecasting` (thành phần của model).
- [ ] **B5 – RAG** · Dev · Could · chưa làm · Skill: `/retail-ai-explain`.
- [ ] **B7 – Router và báo cáo AI4** · Dev + PM/BA · Must · chưa làm · Skill: `/retail-ai-explain`.

## 4. Kiểm thử

**Qua pha khi:** bộ test đầy đủ đạt trên PostgreSQL và DuckDB, eval có ghi phiên bản, và bảng backtest đã có.

- [x] **Test pipeline, release và guard Databricks** (2026-10-12): 63 đạt, 83 bỏ qua vì cần cloud. Skill khi kiểm lại: `/retail-platform-validation`.
- [x] **Test app trên DuckDB** (2026-10-12, trước khi sửa guard): 383 đạt. 107 lỗi, tất cả do PostgreSQL đang tắt. Không cần skill: chỉ chạy pytest.
- [ ] **Chạy đủ bộ test app khi bật container `retail_dwh`** · Dev · Must · chưa làm · Không cần skill. Phải làm trước khi push.
- [ ] **dbt build trên PostgreSQL vẫn 217/217, và parity đạt** · Dev · Must · chưa kiểm · Skill: `/retail-analytics-engineering` + `/retail-platform-validation` (parity). Codex đã đổi macro schema và thêm 3 cột vào `rpt_build_info`; mới kiểm trên DuckDB.
- [ ] **Chạy thử app local ở chế độ versioned** (DuckDB) · Dev + PM/BA · Should · chưa làm · Skill: `/retail-platform-validation`. Cách chạy ở `automation_batch.md`.
- [ ] **Eval hành vi skill** (các ca A3, F1, F2 và negative routing) · Dev · Should · chưa làm.
  - **Không gọi tên skill.** Ca này kiểm xem agent có tự chọn đúng skill không: mở phiên mới, dán câu trong `agent_skill_evaluations.md`.
  - Chỉ một lượt riêng kiểm cách gọi tên thì mới gõ `/tên-skill`.
- [ ] **B2 – Bảng backtest** · Dev · Must · chưa làm · Skill: `/retail-forecasting`.
  - ARIMA, log + SARIMAX và LSTM, mỗi model so với seasonal naive và baseline, báo theo từng fold.
  - Có cột sai số riêng tháng 8 năm lẻ.
  - Có test tháng 8/2023: G sụt, COGS/G > 1.
- [ ] **B3/B7 – Eval chat** · Dev · Must · chưa làm · Skill: `/retail-ai-explain`.
  - Bộ G* cho dự báo, gồm câu ngoài horizon.
  - Live eval trên Databricks, ghi phiên bản model / prompt / catalog / dữ liệu.

## 5. Triển khai

**Qua pha khi:** bản public chạy code mới, chat vẫn trả lời, và pipeline cloud công bố được một bản.

- [ ] **Tách commit thành 3 nhóm** · Dev · Must · một phần · Không cần skill.
  - 2026-10-12, PM chỉ cho commit code: `6d8c5bb` (pipeline + sửa khóa chat), `7610391` (FB01 + FB07). Đã push lên `origin/app/myuyen` ngày 2026-10-12.
  - Còn ngoài git: docs, `CLAUDE.md`, `README.md`, nhóm skill (file `.md` của skill, manifest sync, `scripts/skills/*`).
  - Các nhóm: docs Kafka + skill; automation của Codex + sửa khóa chat; giao diện + FB07.
  - Quy ước: commit message tiếng Việt không dấu, không có dòng Co-Authored-By.
  - `git add` từng file; docs phải dùng `git add -f` vì repo có rule exclude local.
  - Kiểm không có gì trong `data/` bị stage.
- [ ] **PR vào `main`**, TV2 review · PM/BA + TV2 · Must · chưa làm · Không cần skill.
- [x] **Bước 0 – Tạo writer service principal** · PM/BA · Must · **xong 2026-10-15** (dev chạy CLI dưới profile `retail-dev`, PM đồng ý).
  SP `retail-pipeline-writer`: SQL access + workspace access, `Can use` warehouse, `USE CATALOG` + `CREATE SCHEMA` + `MANAGE` trên
  `retail_lab` (MANAGE nhận được trên bản Free). Secret hết hạn **2027-01-13**. `.env.airflow.local` đủ mọi dòng.
  - PM làm trên giao diện Databricks. Muốn agent hướng dẫn hoặc soạn câu lệnh thì dùng `/retail-platform-validation` + `databricks:databricks-core`.
  - Cho quyền dùng warehouse, `USE CATALOG` + `CREATE SCHEMA` trên catalog `retail_lab`.
  - Cho quyền `MANAGE` trên catalog. Chưa thử trên bản Free.
  - Điền `.env.airflow.local`. Không dán secret vào chat.
- [ ] **Chuyển bản public** · PM/BA + Dev · Must · chưa làm · Skill: `/retail-platform-validation`, kèm `databricks:databricks-core` khi chạy lệnh Databricks. Làm đúng thứ tự ở `automation_batch.md`, mục "Thứ tự chuyển bản public…":
  - [ ] merge phần đọc theo bản của app, rồi **Reboot** bản public;
  - [ ] dừng app trên Databricks Apps. Profile Databricks do PM chọn;
  - [ ] build lại image Airflow, rồi chạy DAG với `target = databricks`;
  - [ ] hỏi chat public một câu. Nếu bị khóa thì thu hồi quyền vừa cấp để mở khóa;
  - [ ] bật `RETAIL_RELEASE_MODE = "versioned"` trong Secrets, kiểm evidence có `release_id`.
- [ ] **Bật lịch Airflow** (`RETAIL_PIPELINE_SCHEDULE_ENABLED`) · PM/BA · Should · chưa làm · Skill: `/retail-platform-validation`. Chỉ bật sau khi nghiệm thu.

## 6. Vận hành và bảo trì

**Qua pha khi:** có cách theo dõi lỗi, có tài liệu bàn giao và kịch bản demo.

- [ ] **Theo dõi mỗi lần chạy** · PM/BA · Should · chưa làm · Skill: `/retail-platform-validation`. Hiện xem bằng Airflow UI và `failure.json`; A4 sẽ thêm bảng theo dõi.
- [ ] **Dọn bản cũ** · Dev · Could · chưa làm · Skill: `/retail-platform-validation`.
  - Chưa có cơ chế dọn.
  - Mỗi bản ở local khoảng 46MB; trên Databricks thì tốn hạn mức bản Free.
- [ ] **Tài liệu hướng dẫn và nhật ký bàn giao** cho mỗi chức năng mới, theo "Định nghĩa xong" ở đầu file · Dev · Must · một phần · Skill: dùng skill của chính chức năng đó.
  - Đã có mục §9 ngày 2026-10-12 cho pipeline và phần sửa khóa chat.
  - Các chức năng sau làm theo bảng ở đầu file.
- [ ] **Tài liệu bảo vệ, báo cáo AI4, kịch bản demo** (D14) · PM/BA + Dev · Must · chưa làm.
  - Báo cáo AI4: `/retail-ai-explain`. Tài liệu bảo vệ và kịch bản demo: không cần skill.
  - Khi bảo vệ phải nói rõ lịch Airflow chạy trên laptop, không phải scheduler production.
