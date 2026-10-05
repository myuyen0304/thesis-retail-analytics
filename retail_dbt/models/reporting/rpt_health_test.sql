{{ config(materialized='view') }}
-- Sức khỏe dữ liệu (M5): kết quả từng test của lần chạy GẦN NHẤT có chạy test (theo rpt_health_run).
-- test_group: 'nghiep_vu' = test SQL tự viết (tests/assert_*.sql: đối soát, số khóa deck, công thức);
--             'rang_buoc' = test khai báo trong YAML (unique / not_null / relationships / accepted_values).
-- layer: tầng của bảng được kiểm (test nghiệp vụ assert_rpt_* → reporting, các assert_* khác → marts).
with last_run as (
    select invocation_id, started_at_utc
    from {{ ref('rpt_health_run') }}
    where n_tests_run > 0
    order by started_at_utc desc
    limit 1
)
select
    t.node_name                                                   as test_name,
    case when t.test_kind = 'singular' then 'nghiep_vu' else 'rang_buoc' end as test_group,
    t.test_kind,
    t.tested_model,
    t.column_name,
    case
        when t.test_kind = 'singular' and t.node_name like 'assert_rpt%' then 'reporting'
        when t.test_kind = 'singular' then 'marts'
        when t.tested_model like 'stg%' then 'staging'
        when t.tested_model like 'int%' then 'intermediate'
        when t.tested_model like 'dim%' or t.tested_model like 'fact%' or t.tested_model like 'bridge%' then 'marts'
        else 'reporting'
    end                                                           as layer,
    t.status,
    case when t.status in ('fail', 'error') then 1 when t.status = 'warn' then 2 when t.status = 'skipped' then 3
         else 4 end                                               as status_order,   -- lỗi lên đầu
    t.failures,
    t.message,
    t.description,
    t.execution_time,
    r.started_at_utc                                              as run_started_at_utc
from {{ source('ops', 'dbt_node_result') }} t
join last_run r on r.invocation_id = t.invocation_id
where t.resource_type = 'test'
