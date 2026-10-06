-- Dựng tài nguyên Snowflake cho Retail DWH trên MỘT account mới (mỗi lần đổi account trial).
-- KHÔNG chạy file này trực tiếp: chạy scripts/snowflake/bootstrap.py để điền khóa công khai và hạn mức credit,
-- rồi mở bản đã điền (warehouse/snowflake_bootstrap.sql) trong Snowsight → Worksheet, chọn "Run All" bằng ACCOUNTADMIN.
-- Chạy lại nhiều lần không sao: mọi lệnh đều IF NOT EXISTS / SET.
--
-- Tạo ra:
--   TRANSFORMER  role pipeline: sở hữu database RETAIL, nạp raw + chạy dbt
--   REPORTER     role chỉ đọc cho app/chat (cấp quyền đọc schema reporting ở bước nối app, chưa làm)
--   TRANSFORM_WH warehouse XSMALL, tự tắt sau 60 giây rảnh — trial hết khi hết 30 ngày HOẶC hết credit
--   RETAIL_MONITOR hạn mức credit/tháng: 80% báo, 100% tạm dừng warehouse
--   RETAIL_DBT   user TYPE=SERVICE đăng nhập bằng key-pair (Snowflake chặn password cho user service từ 2026-08–10)

USE ROLE ACCOUNTADMIN;

CREATE ROLE IF NOT EXISTS TRANSFORMER COMMENT = 'Retail DWH: nap raw + dbt';
CREATE ROLE IF NOT EXISTS REPORTER COMMENT = 'Retail DWH: app/chat chi doc';
GRANT ROLE TRANSFORMER TO ROLE SYSADMIN;
GRANT ROLE REPORTER TO ROLE SYSADMIN;

CREATE WAREHOUSE IF NOT EXISTS TRANSFORM_WH
    WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60 AUTO_RESUME = TRUE INITIALLY_SUSPENDED = TRUE;
CREATE RESOURCE MONITOR IF NOT EXISTS RETAIL_MONITOR WITH CREDIT_QUOTA = {{credit_quota}}
    FREQUENCY = MONTHLY START_TIMESTAMP = IMMEDIATELY
    TRIGGERS ON 80 PERCENT DO NOTIFY ON 100 PERCENT DO SUSPEND;
ALTER RESOURCE MONITOR RETAIL_MONITOR SET CREDIT_QUOTA = {{credit_quota}};   -- chạy lại với --credit-quota khác thì cập nhật
ALTER WAREHOUSE TRANSFORM_WH SET RESOURCE_MONITOR = RETAIL_MONITOR;
GRANT USAGE, OPERATE ON WAREHOUSE TRANSFORM_WH TO ROLE TRANSFORMER;
GRANT USAGE ON WAREHOUSE TRANSFORM_WH TO ROLE REPORTER;

-- TRANSFORMER sở hữu database nên tự tạo schema raw/staging/.../ops khi nạp và khi dbt build
CREATE DATABASE IF NOT EXISTS RETAIL;
GRANT OWNERSHIP ON DATABASE RETAIL TO ROLE TRANSFORMER COPY CURRENT GRANTS;
GRANT USAGE ON DATABASE RETAIL TO ROLE REPORTER;

CREATE USER IF NOT EXISTS RETAIL_DBT TYPE = SERVICE
    DEFAULT_ROLE = TRANSFORMER DEFAULT_WAREHOUSE = TRANSFORM_WH DEFAULT_NAMESPACE = RETAIL
    COMMENT = 'Retail DWH: loader + dbt, key-pair';
ALTER USER RETAIL_DBT SET RSA_PUBLIC_KEY = '{{rsa_public_key}}';
ALTER USER RETAIL_DBT SET TIMEZONE = 'UTC';   -- log nạp / build ghi giờ UTC như Postgres, DuckDB
GRANT ROLE TRANSFORMER TO USER RETAIL_DBT;

-- Kiểm: phải thấy RSA_PUBLIC_KEY_FP khác rỗng và TYPE = SERVICE
DESC USER RETAIL_DBT;
