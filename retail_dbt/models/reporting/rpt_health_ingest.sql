{{ config(materialized='view') }}
-- Thứ tự build (2026-10-02): rpt_health_summary là view đọc rpt_build_info, rpt_health_run, rpt_health_ingest. Trên Postgres,
--   dựng lại mỗi cha chạy `drop ... __dbt_backup cascade`, khóa luôn view con chung; hai cha dựng song song (threads: 4) thì
--   khóa chéo nhau → deadlock (lần build 23:17 ngày 2026-10-02). depends_on xếp ba cha chạy lần lượt:
--   rpt_build_info → rpt_health_run → rpt_health_ingest. Không đổi số liệu.
-- depends_on: {{ ref('rpt_health_run') }}
-- Sức khỏe dữ liệu (M5): lần nạp nguồn gần nhất, 1 dòng/nguồn CSV.
-- Postgres: đọc raw._ingest_log do scripts/ingest/ingest_raw.py ghi. Cả lần nạp là 1 transaction nên mọi dòng cùng
--   loaded_at (= lúc transaction bắt đầu); sai số dòng so với contract thì rollback cả log, nên dòng nào có trong log là
--   lần nạp đã qua kiểm số dòng.
-- Snowflake / Databricks: đọc raw._ingest_log do scripts/ingest/ingest_snowflake.py / ingest_databricks.py ghi; loaded_at đã là giờ UTC, mọi dòng
--   của một lần nạp cùng loaded_at và chỉ được ghi khi cả 14 nguồn qua kiểm số dòng trên Delta.
-- DuckDB: không có bước nạp (dbt đọc thẳng data/*.csv), bảng rỗng; rpt_health_summary.ingest_mode = 'doc_csv'.
{% if target.type in ('postgres', 'databricks', 'snowflake') %}
select
    cast(source as varchar(50))                     as source,
    row_count,
    file_md5,
    {% if target.type == 'postgres' -%}
    cast(loaded_at at time zone 'UTC' as timestamp) as loaded_at_utc,
    {%- else -%}
    cast(loaded_at as timestamp)                    as loaded_at_utc,
    {%- endif %}
    cast(seconds as {{ type_double() }})            as seconds
from {{ source('raw_log', '_ingest_log') }}
where loaded_at = (select max(loaded_at) from {{ source('raw_log', '_ingest_log') }})
{% else %}
select
    cast(null as varchar(50))         as source,
    cast(null as bigint)              as row_count,
    cast(null as varchar(32))         as file_md5,
    cast(null as timestamp)           as loaded_at_utc,
    cast(null as {{ type_double() }}) as seconds
where 1 = 0
{% endif %}
