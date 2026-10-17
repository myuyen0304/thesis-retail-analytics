# Bộ skill DA/BI/Analytics Engineer

Quyết định ngày **2026-09-29**: bộ skill dùng chung cho Codex và Claude Code, phục vụ Retail Analytics từ local đến cloud. Đây là hướng dẫn làm việc cho coding agent; không phải runtime AI chat của sản phẩm.

## Kiến trúc và phạm vi đã chốt

Cập nhật 2026-10-11 theo `CLAUDE.md` §1 và [kien_truc_pipeline_tong.md](kien_truc_pipeline_tong.md):

- Local PostgreSQL/DuckDB: phát triển và tạo đối chứng.
- Databricks: **production** từ 2026-10-05, gồm DWH, app và chat. Trước đó là lab kiểm chứng. Snowflake không còn là bước mặc định; có profile không đồng nghĩa đã deploy.
- AI Explain: **chat hỏi dữ liệu PS1–PS5** (L1), có query, bằng chứng và giới hạn suy luận. Từ 2026-10-11 mở rộng thành agent 4 level của GĐ2: L2 biểu đồ, L3 đọc dự báo, L4 giải thích, RAG tri thức không cấp số.
- Dự báo: từ 2026-10-11 là lõi của GĐ2. Target là G theo ngày, COGS suy qua tỷ lệ. Dùng skill `retail-forecasting`.
- Airflow: chạy trong Docker local, điều phối batch (chốt 2026-10-11).
- Kafka: hoãn, có thể không làm. Nếu sau này làm, CSV replay phải ghi rõ là mô phỏng.

Lần xây skill đầu (2026-09-29) chưa deploy cloud, chưa xây runtime chat và chưa chọn LLM provider. Không dùng mốc PASS trong tài liệu cũ để chứng minh trạng thái hiện tại.

## Nguồn chuẩn và cách đọc

Mọi đường dẫn trong skill dạng `docs/`, `retail_dbt/`, `apps/` tính từ **root repo**. Link `references/...` và `assets/...` trong skill tính từ thư mục chứa `SKILL.md`.

| Cần tìm | Nguồn chuẩn |
|---|---|
| Quy ước repo và bối cảnh | `AGENTS.md`, `CLAUDE.md`; chỉ dẫn mới của người dùng có ưu tiên |
| Hợp đồng nghiệp vụ/grain/KPI | [star_schema.md](star_schema.md), phần §3 về metric |
| Công thức thực thi và kiểm chất lượng | `retail_dbt/models/`, `retail_dbt/macros/`, `retail_dbt/tests/` |
| Bằng chứng kết luận dữ liệu | Notebook tương ứng trong `notebooks/`; CSV/snapshot dùng để đối chứng |
| App, trạng thái và nghiệm thu | [gd2_app_plan.md](gd2_app_plan.md), code và test trong `apps/retail_app/` |
| Cloud và thứ tự phát triển | [dwh_roadmap.md](dwh_roadmap.md); bản Databricks archive chỉ tham khảo |
| Kiến trúc GĐ2: pipeline, dự báo, agent 4 level | [kien_truc_pipeline_tong.md](kien_truc_pipeline_tong.md); các mục A/B trong đó là thiết kế đề xuất |

Nếu tài liệu và code không khớp, chỉ ra chỗ lệch và kiểm nguồn/test trước khi sửa; không tự chọn con số thuận tiện. Không sao chép toàn bộ định nghĩa KPI vào từng skill.

Tài liệu giữ mốc lịch sử và ghi chú sửa sau đó: đọc quyết định/correction mới nhất, không lấy một dòng grep của bảng đề xuất cũ làm chính sách hiện hành. Không suy ra file/thư mục thiếu từ Glob/rg mặc định khi bị Git ignore; kiểm đường dẫn trực tiếp. Profile/workspace chưa kiểm trong lần này phải ghi chưa kiểm, không khẳng định từ memory.

## Chọn skill theo việc

| Skill | Vai trò thường dùng | Đầu ra |
|---|---|---|
| `retail-metric-design` | DA, AE, BI | Hợp đồng metric: câu hỏi, grain, filters, công thức, phép tổng hợp, đối chứng |
| `retail-data-analysis` | DA | Notebook chạy lại được, bằng chứng và giới hạn kết luận |
| `retail-analytics-engineering` | AE | Model dbt, test grain/join/reconciliation và báo cáo chạy |
| `retail-bi-product` | BI | Trang/biểu đồ/bộ lọc, số liệu khớp nguồn, test rendering và trạng thái lỗi |
| `retail-ai-explain` | BI, AE | Luồng chat/agent có kiểm soát (L1–L4, RAG), evidence và eval; code khi được giao xây tính năng |
| `retail-platform-validation` | AE, DE | Kiểm tương thích, chạy/đối soát nền tảng, bằng chứng publish gate |
| `retail-forecasting` | DA, DS | Hợp đồng dự báo, notebook so sánh model + backtest, bảng `reporting.rpt_forecast_*` trong bản dữ liệu của pipeline kèm test, file nộp. Ranh giới với `retail-ai-explain` là các bảng `rpt_forecast_*` |

Chọn tập skill nhỏ nhất đủ cho yêu cầu. Thay đổi nhãn UI không phải đi lại toàn bộ thiết kế DWH; thêm KPI mới cần định nghĩa trước model và consumer. Đọc reference theo nhiệm vụ, không nạp tất cả.

## Gọi trên Codex và Claude Code

Codex nhận source tại `.agents/skills/`; Claude Code nhận bản đồng bộ tại `.claude/skills/`. Chỉ sửa source Codex rồi đồng bộ. Có thể gọi tên trực tiếp hoặc để agent chọn theo description.

Ví dụ Codex:

```text
$retail-metric-design Thiết kế tỷ lệ khách quay lại; chỉ ra dữ liệu có đủ chứng minh không.
$retail-data-analysis Kiểm chứng nhịp cuối tháng bằng notebook và giải thích giới hạn.
$retail-analytics-engineering Thêm bộ lọc category cho số khách, không cộng distinct từ nhóm.
$retail-bi-product Thêm trang so sánh R theo năm, giữ nguồn và kỳ phân tích rõ ràng.
$retail-ai-explain Thiết kế chat PS1–PS5 với query chỉ đọc và bộ eval cho câu hỏi ngoài phạm vi.
$retail-platform-validation Lập kế hoạch lab Databricks đối soát DWH/KPI với snapshot local.
$retail-forecasting Lập backtest rolling-origin cho log + SARIMAX, có sai số riêng tháng 8 năm lẻ.
```

Claude Code dùng cùng yêu cầu với `/retail-metric-design`, `/retail-data-analysis`, `/retail-analytics-engineering`, `/retail-bi-product`, `/retail-ai-explain`, `/retail-platform-validation`, `/retail-forecasting`.

Agent phải tự tìm thông tin có trong repo trước khi hỏi. Khi câu hỏi thật sự mơ hồ (ví dụ doanh thu R/G) thì làm rõ; không biến skill thành quy trình hỏi xác nhận cho mọi bước đã được giao. Skill không mở rộng quyền deploy hay thay đổi dữ liệu ngoài yêu cầu.

## Quy trình tính năng mới

1. Xác định quyết định người dùng cần, nguồn và grain. Tìm metric/model có sẵn.
2. Nếu đổi business contract, cập nhật định nghĩa và bằng chứng trước hoặc cùng implementation. Phần chưa chốt ghi rõ là đề xuất.
3. Thực thi ở đúng lớp: dbt tính KPI, app trình bày, LLM giải thích kết quả có nguồn. Query filter động tính từ detail được kiểm chứng.
4. Kiểm phần bị ảnh hưởng và đối chứng độc lập. Nêu backend/snapshot/lệnh/artifact; chưa chạy cloud thì ghi chưa chạy.
5. Bàn giao đầu ra đã được yêu cầu. Sửa workflow skill chỉ khi có nhu cầu lặp lại hoặc lỗi quan sát được; không tự mở rộng thêm công nghệ.

Mỗi lần bàn giao cần trả lời: thay đổi gì, theo định nghĩa nào, đã kiểm gì và giới hạn nào còn lại. Báo cáo cloud phân biệt compile/deploy/run/parity/publish. Câu chat phân biệt observation/decomposition/hypothesis; không dựa vào câu văn tự tin để nghiệm thu.

## Đồng bộ và kiểm tra

Chạy từ root:

```powershell
.venv/Scripts/python.exe scripts/skills/sync_skills.py --check
.venv/Scripts/python.exe scripts/skills/sync_skills.py --write
.venv/Scripts/python.exe scripts/skills/validate_skills.py
.venv/Scripts/python.exe -m pytest scripts/skills/tests -q
```

`--check` chỉ đọc: exit 0 = khớp, 1 = cần đồng bộ, 2 = xung đột/lỗi. `--write` chỉ quản lý các skill trong bảng (danh sách `SKILLS` trong `scripts/skills/sync_skills.py`). Thêm skill mới: thêm tên vào cuối `SKILLS` rồi chạy `--write`. Bớt skill khỏi danh sách thì script dừng, phải xử lý manifest có chủ đích; chuẩn hóa CRLF/LF và ghi manifest hash. File bị sửa thủ công ở bản Claude làm preflight dừng trước khi ghi. Khi có xung đột, đối chiếu nội dung và hợp nhất thay đổi có chủ đích vào source; khôi phục bản generated đã biết trước khi sync, không xóa manifest để bỏ qua kiểm tra.

Script không xóa skill ngoài danh sách; file reference bị bỏ ở source chỉ bị xóa khỏi bản Claude nếu thuộc manifest và chưa bị sửa. Nếu ghi bị gián đoạn, kiểm file/manifest và phục hồi bản đã biết trước khi chạy lại; đây không phải giao dịch filesystem nguyên tử. Không hỗ trợ symlink/junction hay file nhị phân trong các skill được quản lý.

`AGENTS.md` giữ nguyên trong đợt này. Skill kỹ thuật Streamlit/Databricks cài sẵn có thể hỗ trợ, nhưng máy thiếu chúng vẫn có đường tra tài liệu chính thức. Không cần tạo subagent hoặc cài plugin để dùng bộ skill.

Repo hiện có quy tắc local `.git/info/exclude` bỏ qua `docs/`; nếu muốn chia sẻ qua Git, phải stage đích danh các tài liệu bàn giao bằng `git add -f <file>`. Không tự sửa exclude hoặc stage toàn bộ. Chưa có commit/push trong đợt xây skill.

## Kiểm chứng và tài liệu kỹ thuật

Bộ tình huống: [agent_skill_evaluations.md](agent_skill_evaluations.md). Kết quả lần triển khai: [agent_skill_validation.md](agent_skill_validation.md). Kiểm cấu trúc không thay thế kiểm hành vi; mock/query-test không thay live LLM/cloud run.

- [Codex skill discovery và invocation](https://learn.chatgpt.com/docs/build-skills)
- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [dbt trên Databricks](https://docs.databricks.com/aws/en/partners/prep/dbt)

Các đường dẫn/runtime phải kiểm lại khi nâng công cụ; nội dung kỹ thuật sản phẩm đặt ở reference tương ứng, không hardcode version vào quy trình chung.
