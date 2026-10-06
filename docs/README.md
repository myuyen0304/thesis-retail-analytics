# Tài liệu dự án

Thư mục này tập trung toàn bộ tài liệu Markdown về business, EDA, data dictionary và thiết kế dữ liệu.
`README.md` và `CLAUDE.md` được giữ ở root vì GitHub và công cụ dự án cần đọc chúng tại đó.

## Bắt đầu từ đâu?

| Mục tiêu | Tài liệu |
|---|---|
| Hiểu câu chuyện business | [`business_data_notes.md`](business_data_notes.md) |
| Học quy trình phân tích dataset | [`data_business_analysis_workflow.md`](data_business_analysis_workflow.md) |
| Xem kết quả EDA theo quy trình | [`data_business_analysis_workflow_results.md`](data_business_analysis_workflow_results.md) |
| Tra ý nghĩa cột và bảng | [`data-dictionary.md`](data-dictionary.md) |
| Hiểu ba câu hỏi grain–key–relationship | [`three_questions_to_understand_data.md`](three_questions_to_understand_data.md) |
| Xem mô hình quan hệ 3NF | [`normalized_schema.md`](normalized_schema.md) |
| Xem mô hình chiều | [`star_schema.md`](star_schema.md) |
| Truy vết PS1–PS5 tới mô hình chiều | [`star_schema_tu_ps.md`](star_schema_tu_ps.md) |
| Tra DDL và kiểm chứng lịch sử (không phải thiết kế chuẩn) | [`star_schema_snapshot_reference.md`](star_schema_snapshot_reference.md) |
| Lộ trình app code → Snowflake → Kafka | [`dwh_roadmap.md`](dwh_roadmap.md) |
| Hiểu lý do thiết kế database | [`database_design_explanation.md`](database_design_explanation.md) |
| Ôn câu hỏi phản biện | [`defense_notes.md`](defense_notes.md) |
| Tra các thắc mắc cụ thể của dataset | [`thac_mac_dataset.md`](thac_mac_dataset.md) |

## Notebook bằng chứng

- [`notebooks/01_exploration/dataset_storytelling_eda.ipynb`](../notebooks/01_exploration/dataset_storytelling_eda.ipynb): câu chuyện EDA tổng hợp.
- [`notebooks/01_exploration/business_eda.ipynb`](../notebooks/01_exploration/business_eda.ipynb): bằng chứng business EDA toàn dữ liệu.
- [`notebooks/01_exploration/full_data_exploration.ipynb`](../notebooks/01_exploration/full_data_exploration.ipynb): profile và anomaly toàn bộ nguồn.
- [`notebooks/02_design/normalization.ipynb`](../notebooks/02_design/normalization.ipynb): kiểm chứng 1NF → 3NF.
- [`notebooks/02_design/data_model.ipynb`](../notebooks/02_design/data_model.ipynb): kiểm chứng star schema.
- [`notebooks/02_design/star_schema_validation.ipynb`](../notebooks/02_design/star_schema_validation.ipynb): đối soát độc lập lõi PS, KPI reporting, calendar và cảnh báo fan-out; đọc warehouse read-only.
- [`notebooks/01_exploration/eda.ipynb`](../notebooks/01_exploration/eda.ipynb): cấu trúc chuỗi thời gian và forecasting constraints.
