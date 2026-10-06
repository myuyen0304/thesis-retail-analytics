---
name: retail-platform-validation
description: "Chuyển và đối soát Retail DWH giữa local và Databricks production (Snowflake là phương án cũ); thiết kế kiểm chứng cho ingestion, replay và orchestration khi được yêu cầu. Dùng cho portability và nghiệm thu nền tảng."
---

# Kiểm chứng nền tảng bằng cùng hợp đồng dữ liệu

## Routing

Đường dẫn repo tính từ root. Đọc `AGENTS.md`, `CLAUDE.md`, `docs/agent_workflows.md`, roadmap, profile dbt và macro hiện tại. Xác minh trạng thái runtime, không xem config hoặc tài liệu lịch sử là bằng chứng deploy.

Không suy ra file/thư mục vắng mặt từ Glob/rg mặc định: `docs/`, `archive/` có thể bị Git ignore/exclude. Kiểm đường dẫn trực tiếp (Read, Test-Path hoặc tìm có include ignored) trước khi khẳng định thiếu; với archive đọc `archive/databricks/retail_medallion/README.md` nếu cần. Không khẳng định profile/workspace hiện có hay không dựa vào memory/ngữ cảnh cũ; chưa đọc/kiểm trong lần này thì ghi “chưa kiểm”.

- Databricks (production từ 2026-10-05, PM chốt; trước đó là lab): đọc [databricks](references/databricks-lab.md). Các câu "lab, không production" trong file đó là lịch sử.
- Snowflake (không còn là đích mặc định; chỉ khi được yêu cầu): đọc [snowflake](references/snowflake-production.md).
- Kafka, incremental, Airflow hoặc vận hành nguồn mới: đọc [DE extension](references/de-extension.md).

Chỉ đọc reference theo nhiệm vụ; không tự triển khai cả ba hướng. Tận dụng skill nền tảng tương ứng nếu có, nếu thiếu thì tra tài liệu chính thức hiện hành và CLI help; không tự cài cả bộ plugin.

## Quy trình chung

1. Xác nhận mục đích, nguồn/snapshot, target và quyền thao tác đã được người dùng cho phép. Tìm cấu hình trong repo và môi trường; không in secrets. Nếu workspace/target chưa được chọn, hỏi trước khi tác động cloud; không hỏi lại lựa chọn đã rõ.
2. Ghi baseline từ local: manifest/hash nguồn, code revision hoặc hash file thay đổi, key/grain/types và kết quả marts/reporting. Xác minh baseline bằng test/nguồn độc lập phù hợp, không chỉ dùng con số trong deck.
3. Tái sử dụng dbt và hợp đồng nghiệp vụ; cô lập khác biệt SQL, loader và connections. Giữ source-row identity. Không phục hồi archive như bản triển khai hiện hành.
4. Phân biệt các bước: static/compile → deploy → run → quality gate → parity → publish. Báo trạng thái theo bước đã thực sự hoàn thành, không gộp “build chạy được” với “số đúng”.
5. So count, key/duplicate/null, schema/types, từng dòng theo key rồi KPI theo kỳ/nhóm. Tiền/số đếm exact sau chuẩn hóa hợp đồng; tolerance cho float phải có lý do theo cột. Không chỉ so tổng toàn kỳ hoặc làm tròn để che sai lệch.
6. Kiểm rerun/idempotency theo cơ chế ingest. Khi test fail, giữ kết quả phục vụ đã đạt trước đó; ghi sai khác và nguyên nhân, không publish bảng xây dở. Mở rộng sang app/chat chỉ khi phạm vi bao gồm consumer.

## Đầu ra nghiệm thu

Báo cáo phải có target/workspace, quyền/phạm vi sử dụng, nguồn/hash, code, run ID/thời gian, các lệnh, artifacts, đối soát và phần chưa kiểm. Không ghi credentials vào báo cáo. Ghi cost/runtime quan sát được nếu có, không ước thành số đã đo.

Các lần chạy có mutation tuân theo phạm vi được giao. Thiếu môi trường/quyền thì vẫn hoàn thành kiểm static và kế hoạch chạy; đánh dấu cloud “chưa chạy”, không mock PASS. Từ 2026-10-05 Databricks là đích production (DWH, app, chat AI); Snowflake chỉ làm khi được yêu cầu.
