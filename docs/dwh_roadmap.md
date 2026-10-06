# Lộ trình DWH: PS1–PS5 → app code → Databricks production → Kafka

## Đổi hướng đã chốt 2026-10-05: Databricks là production

- PM chốt **Databricks là đích production** cho DWH, app phân tích và chat AI Explain. Phần "Databricks là lab" và
  "Snowflake vẫn là đích production" ở các mục bên dưới là **lịch sử**, không còn hiệu lực.
- Quy trình: dev và test ở local (DuckDB / PostgreSQL), đạt các cổng kiểm (test số, test model thật) rồi mới deploy
  lên Databricks; trên Databricks chạy lại cùng bộ kiểm trước khi công bố.
- Snowflake: script đã viết (`scripts/snowflake/`, `scripts/ingest/ingest_snowflake.py`) giữ nguyên, chưa chạy cloud,
  không còn là bước mặc định.
- Workspace hiện tại là Databricks **Free Edition**; giới hạn của bản Free (app, gọi ra internet, service principal,
  lịch chạy) phải kiểm trên tài liệu chính thức và workspace thật trước khi cam kết từng hạng mục.


Cập nhật 2026-09-27 theo hướng đã chọn: xây DWH bám nghiệp vụ, sau đó làm sản phẩm bằng code.
Thiết kế chuẩn: [star_schema.md](star_schema.md); nguồn business:
[deck updated](presentations/revenue_performance_problem_statement_updated.pptx).

## Bổ sung đã chốt 2026-09-29: skill, AI chat và Databricks lab

- Xây trước bộ skill DA/BI/Analytics Engineer dùng chung Codex + Claude Code; xem [agent_workflows.md](agent_workflows.md).
- AI Explain được bổ sung theo hướng **chat hỏi dữ liệu PS1–PS5**, truy vấn chỉ đọc có kiểm soát và trả lời dẫn về số/query/snapshot. Chưa triển khai runtime, chưa chọn LLM provider. Quyết định không AI ở kế hoạch app ngày 2026-09-27 là lịch sử.
- Databricks là **lab kiểm chứng DWH và KPI** với cùng nguồn local, không là production thứ hai; chưa yêu cầu host app/chat tại lab. Tái sử dụng hợp đồng và model dbt hiện tại, archive chỉ tham khảo. Chưa triển khai/xác nhận cloud trong đợt tạo skill.
- Snowflake vẫn là đích production. Kafka/Airflow thêm theo nhu cầu nguồn sự kiện/vận hành sau này; chưa lắp công nghệ trong đợt này.

Các trạng thái và số test trong phần lịch sử bên dưới thuộc lần ghi nhận tương ứng, không thay bằng chứng chạy hiện tại. Bộ skill và kế hoạch không chứng minh pipeline cloud hoặc AI chat đã hoạt động.

## Phạm vi và thứ tự

| Giai đoạn | Kết quả cần có | Trạng thái |
|---|---|---|
| 1. Lõi local và KPI PS1–PS5 | Fact grain đúng, conformed dimensions, reporting, kiểm chứng độc lập | Đã có local, đủ KPI 5 PS; bảng giai đoạn/điểm đổi hướng PS2 dựng ngày 2026-09-27 (155/155 PASS) |
| 2. Sản phẩm phân tích bằng code | Đọc reporting; drill-down đúng grain; giải thích số và giới hạn suy luận | Chưa triển khai trong đợt này |
| 3. Databricks production (đổi từ Snowflake ngày 2026-10-05) | Deploy pipeline + app + chat AI, quản trị quyền/chi phí, lịch chạy, publish gate, phục hồi | DWH đã lên `retail_lab` (216/216, đối soát 33/33, 2026-10-03); app đọc Databricks (2026-10-04); chat AI và host app **chưa** |
| 4. Kafka end-to-end | Event source/replay, incremental có khóa bền vững và xử lý late events | Sau pipeline chính, chưa triển khai |

`PostgreSQL` là dev local hiện tại; `DuckDB` là snapshot kiểm chứng gọn; `Databricks` là đích production (từ 2026-10-05; trước đó là Snowflake).
Project dbt có cấu hình đa target; có cấu hình **không đồng nghĩa** đã chạy thành công trên cloud.
Python phục vụ ingest/phân tích/app; dbt phục vụ transform và test. BI là consumer tùy chọn, không bắt buộc
Power BI thay cho hướng code đã chọn. Forecast/SHAP là extension riêng, không còn là bước mặc định của PS1–PS5.

Kafka không cần để đọc bộ CSV tĩnh hiện có, nhưng vẫn là phần mở rộng pipeline cần thiết nếu đề tài yêu cầu luồng sự kiện.
Nếu demo bằng replay CSV, ghi rõ là mô phỏng; không gọi là realtime business source.
Airflow có thể điều phối khi có nhiều phụ thuộc/backfill/retry; chỉ chốt sau khi thiết kế vận hành rõ.

---

## GĐ 1: Dựng DWH local (PostgreSQL + Python + dbt)

**Mục tiêu:** dựng star schema 14 bảng (xem `star_schema.md`; DDL lịch sử ở `star_schema_snapshot_reference.md` §7) trên PostgreSQL local, có test tự động.

```text
data/*.csv ──(Python: scripts/ingest/ingest_raw.py)──▶ PostgreSQL schema raw        (14 bảng, mọi cột TEXT, + _src_row)
                                          │  dbt
                                          ├─▶ staging.stg_*           (14 view: ép kiểu, trim)        ≈ Bronze
                                          ├─▶ intermediate.int_*      (4 view: line_number, map return/review) ≈ Silver
                                          ├─▶ marts.dim_* / fact_*    (14 bảng star)                  = Gold / DWH
                                          └─▶ reporting.rpt_*         (KPI của 5 PS, đọc từ marts)    → app code / BI
```

**Chạy** (từ root repo):

```bash
docker compose up -d                                          # PostgreSQL 17, cổng 5433
.venv/Scripts/python.exe scripts/ingest/ingest_raw.py                # nạp raw, kiểm header + số dòng
PYTHONUTF8=1 .venv/Scripts/dbt.exe build --project-dir retail_dbt --profiles-dir retail_dbt
```

**Tiêu chí xong:**
- `dbt build` pass toàn bộ, gồm 39 model, 1 seed và 115 test (từ 2026-09-27; trước đó 37 model và 101 test):
  - PK/FK/not_null;
  - số dòng 14 bảng;
  - doanh thu/giá vốn theo ngày khớp tuyệt đối `sales.csv` trên 3.833 ngày;
  - 5 cột dẫn xuất tồn kho khớp `inventory.csv`;
  - các cột bị loại đều đã chứng minh là bản sao;
  - tầng reporting đối soát với nguồn độc lập (xem mục *Tầng reporting* bên dưới).
- Marts trên PostgreSQL giống từng dòng với target duckdb và với `warehouse/retail.duckdb`.
  `warehouse/retail.duckdb` do `scripts/build/build_gold.py` sinh ra, một bản dựng độc lập không dùng dbt, dùng làm đối chứng.

**Lịch sử bàn giao ngày 2026-09-26** (không phải lần chạy dbt mới trong đợt sửa thiết kế):
- Target `postgres` (PostgreSQL 17 trong Docker):
  - `scripts/ingest/ingest_raw.py` nạp 14/14 nguồn đúng số dòng, mất khoảng 6 giây;
  - `dbt build` **138/138 PASS** (có tầng reporting), mất khoảng 90 giây.
- Target `duckdb`: 138/138 PASS.
- So từng dòng (EXCEPT ALL hai chiều), 14/14 bảng marts giống hệt nhau giữa Postgres, DuckDB và bản
  `scripts/build/build_gold.py`. Nghĩa là ba cách dựng ra cùng một kết quả.
- Test có tác dụng thật: cố ý làm sai cách làm tròn thì test tồn kho FAIL đúng 977 dòng.
- Bài học khi viết SQL cho nhiều nền tảng: trên Postgres, subquery `NOT IN`/`EXISTS` nằm **trong một biểu thức**
  sẽ bị chạy lồng từng dòng. Một test từng treo hơn 10 phút; viết lại bằng LEFT JOIN thì hết.
- Docker mặc định chỉ cấp 64MB `/dev/shm`, không đủ cho hash join song song của test đối soát
  ("could not resize shared memory segment"). `docker-compose.yml` đặt `shm_size: 512mb`.

### Tầng reporting: phục vụ 5 problem statement

Lõi marts giữ grain dòng hàng để phục vụ **business** là 5 PS trong deck `docs/presentations/revenue_performance_problem_statement_updated.pptx`.
Tầng `retail_dbt/models/reporting/` (schema `reporting`) tính sẵn KPI theo đúng quy ước của deck (slide 3):
**R** = Σ(quantity × unit_price − discount_amount), chỉ đơn delivered; **G** = mọi đơn, chưa trừ chiết khấu (= `sales.csv`).
Thiết kế được phản biện hai vòng với Codex CLI (đề xuất → review) ngày 2026-09-26.

| Model | Grain | Phục vụ | Cột chính |
|---|---|---|---|
| `int_reporting_order_items` (view) | dòng hàng | nền chung | trạng thái đơn, `is_delivered`, lịch, category / region / acquisition_channel |
| `rpt_revenue_monthly` | tháng, 07/2012–12/2022 | PS1, PS2, PS3 | G, R, tách G−R (hủy / trả / chưa giao / chiết khấu), N Q C U P F AOV, YoY cùng kỳ (từ 08/2013), `r_12m` (từ 07/2013), `month_index`, `eom_share` so với (D−25)/D |
| `rpt_revenue_yearly` | năm, 2012–2022 | PS1, PS2, PS4, PS5 | như trên + YoY từ 2014, tăng trưởng N/U/P, tách ΔR = N + U + P, tách ΔN = C + F, chênh mùa cao/thấp |
| `rpt_revenue_segment_yearly` | chiều × nhóm × năm | PS5 | R, tỷ trọng, ΔR, dịch chuyển tỷ trọng (điểm %), % đóng góp vào ΔR tổng |
| `rpt_august_parity` (view) | 1 dòng | PS3 | chỉ số T8 năm lẻ / năm chẵn − 1 |

Nguyên tắc:
- **N và C là đếm phân biệt**, tính lại ở từng grain. N cộng được qua thời gian (một đơn có một ngày đặt),
  C thì không (một khách mua nhiều tháng). Mọi tỷ số tính lại từ tử/mẫu, không cộng hay lấy trung bình tỷ số con.
- **Không cộng ba chiều PS5 với nhau**: đó là ba góc nhìn của cùng một R.
- **Chưa làm:** bảng giai đoạn / điểm đổi hướng của PS2. Mốc giai đoạn là *kết quả* phân tích PS2, chưa chốt,
  không tự chọn mốc trong warehouse.
- `fact_daily_sales` **giữ nguyên là G** (tham chiếu; forecast là hướng mở rộng riêng).

Test (`retail_dbt/tests/assert_rpt_*.sql`):
- `assert_rpt_reconciles`: nền không mất/nhân dòng; G − R = hủy + trả + chưa giao + chiết khấu; đối soát **từng tháng và
  từng năm** với đối chứng nhiều grain (N, C từ `fact_order`; R độc lập từ `payments.csv`; Q và R ngày ≥ 26 từ `fact_order_item`;
  G từ `fact_daily_sales`). Các fact dẫn xuất chỉ là đối chứng nội bộ; notebook mới còn đọc trực tiếp CSV.
- `assert_rpt_decomposition_additive`: từng phần tách đúng công thức deck (đúng thứ tự N → U → P), cộng về ΔR / ΔN;
  PS5 cộng về tổng, lưới nhóm × năm dựng từ nguồn.
- `assert_rpt_calendar`: 126 tháng liên tục; R 12 tháng và YoY tính lại bằng self-join; chỉ số tháng; D theo lịch (năm nhuận).
- `assert_rpt_deck_numbers`: con số ghi trong deck (G, R, R/G 76,2%, returns chỉ ở đơn returned, 2019 giảm > 30%,
  T8 năm lẻ −35%…−40%, doanh thu dồn cuối tháng). Deck đổi số thì sửa test cùng lúc.
- Mutation test đã chạy: tính cả đơn `shipped` là delivered → 2 test FAIL; đảo thứ tự tách N/U → FAIL;
  đổi ngưỡng cuối tháng 26 → 25 → FAIL.

---

## GĐ 2: Sản phẩm phân tích bằng code

**Kế hoạch chi tiết:** [`gd2_app_plan.md`](gd2_app_plan.md) (lập 2026-09-27: trang, kiến trúc, mốc M0–M6, cách kiểm, việc cần PM quyết).

- App đọc `reporting.rpt_*` cho đúng grain định sẵn; drill-down/filter động dùng detail và tính lại distinct N/C.
- Trang PS1–PS5 phải hiện kỳ phân tích, định nghĩa R/G, trạng thái snapshot và thời điểm refresh.
- Giải thích N/U/P và C/F bằng phân rã số học, không biến thành kết luận nguyên nhân hoặc churn.
- PS2: BA chốt/cấu hình giai đoạn và phương pháp điểm đổi hướng; lưu version phân tích, không hardcode mốc tùy ý.
- Chọn framework và cách host khi triển khai app; chưa tạo app trong đợt thiết kế này.
- Nếu thêm AI giải thích: câu trả lời phải dẫn về số liệu/query có kiểm chứng, phân biệt quan sát/giả thuyết.

## GĐ 3: Snowflake production — checklist trước triển khai

Đây là yêu cầu nghiệm thu tương lai, không là bằng chứng deploy hay hướng dẫn dịch vụ đã được xác minh trực tiếp.

1. Kiểm quyền truy cập, vùng triển khai, ngân sách, dev/test/prod và cơ chế quản lý secrets.
2. Ingest có manifest/version nguồn, kiểu dữ liệu, xử lý file lỗi và idempotency. Giữ source-row identity
   để không đổi line_number khi replay. Lưu snapshot nguồn dùng cho deck.
3. Kiểm SQL/macro thực tế trên Snowflake, đặc biệt rounding/cast. Không suy ra portability từ test local.
4. Tạo các lớp raw/staging/intermediate/marts/reporting; đối soát từng kỳ, PK/FK/grain và mọi KPI PS,
   không chỉ so một tổng doanh thu.
5. Test xong mới publish một version hoàn chỉnh cho app. dbt test FAIL tự nó không rollback mọi bảng đã materialize.
6. Service role quyền tối thiểu, scheduler, cảnh báo freshness/quality, budget guardrails, log/audit và replay/restore.
7. Kiểm dashboard/app production end-to-end, bằng chứng endpoint + lịch chạy + kết quả quality gate.

Thiết kế star không cần đổi thành snowflake schema chỉ vì chạy trên Snowflake.
Thời hạn/credit trial và quyền tính năng phải kiểm lại tại thời điểm triển khai; không lấy ghi chú cũ làm bảo đảm production.

## GĐ 4: Kafka sau khi pipeline chính ổn định

- Chốt producer/source, business event ID, schema/version và khóa phân vùng; không invent event history từ CSV snapshot.
- Tách ingest/event log khỏi fact nghiệp vụ. Một event stream có thể cập nhật một fact, không phải mỗi topic luôn là một fact.
- Dùng persistent surrogate-key mapping; ROW_NUMBER full rebuild hiện tại chưa đủ.
- Dedup, idempotent merge, watermark/late events, replay, retry và cảnh báo; mô tả rõ event time/processing time.
- Khi trạng thái delivered → returned, tính lại R cho ngày/tháng **đặt hàng gốc** theo hợp đồng đề tài.
- Giữ snapshot frozen riêng để tái hiện con số PPT; số realtime có thể đổi khi trạng thái đổi.
- Nghiệp vụ mới: fact grain riêng + conformed dimension + kiểm thử drill-across trước khi publish.

## Bằng chứng của lần chỉnh thiết kế

[Notebook mới](../notebooks/02_design/star_schema_validation.ipynb) kiểm dữ liệu nguồn và snapshot DuckDB read-only.
Đợt này không chạy ingest/dbt build, không sửa models/tests, không deploy và không dựng Kafka.
