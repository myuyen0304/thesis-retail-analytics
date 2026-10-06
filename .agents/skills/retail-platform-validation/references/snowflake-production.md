# Snowflake: chuyển sang production

Snowflake là đích đã chọn; star schema không cần đổi thành snowflake schema. Profile dbt hiện có chưa chứng minh đã deploy/chạy cloud.

1. Kiểm account/region, database/schema, warehouse, authentication, role, dev/test/prod và ngân sách theo phạm vi được giao. Dùng env/secret store; quyền pipeline và quyền đọc app/chat tách nhau. Không đưa password/token vào code, SQL log hoặc ảnh.
2. Tạo landing/ingest có manifest, kiểu dữ liệu và source-row identity bền vững. Nạp lại snapshot không đổi mapping dòng hàng. Kiểm record nhiều dòng và xử lý file lỗi.
3. Kiểm adapter/version và SQL thực tế: precision/scale, rounding half-even, quoting/case, NULL, dates, key generation. Không xem macro đã viết là đã test trên Snowflake.
4. Chạy dbt trong vùng build riêng, đối soát local theo grain/key, nguồn độc lập và KPI từng kỳ/nhóm. Tài khoản app chỉ đọc version đã qua gate. Thiết kế atomic/versioned promotion và rollback trước khi bật lịch chạy; dbt test FAIL không tự che bảng đang xây dở.
5. Thử scheduler, retry, freshness/quality alert, log/audit, cost controls và restore/replay. Ghi thử nghiệm thật; không gọi cấu hình chưa chạy là vận hành ổn định.
6. Khi phạm vi gồm production app, kiểm connection normalization và cùng test consumer; chốt cách host Streamlit riêng theo tính năng/account hiện hành. AI chat chỉ đọc nguồn cho phép, dùng cùng metric contract.

Nguồn: [Snowflake documentation](https://docs.snowflake.com/), [dbt Snowflake setup](https://docs.getdbt.com/docs/core/connect-data-platform/snowflake-setup). Tra đúng feature/version tại thời điểm thực hiện; chưa khóa scheduler, LLM provider hoặc hosting trong bộ skill.
