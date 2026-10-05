{{ config(materialized='view') }}
-- Thứ tự build (2026-10-02): rpt_health_summary là view đọc rpt_build_info, rpt_health_run, rpt_health_ingest. Trên Postgres,
--   dựng lại mỗi cha chạy `drop ... __dbt_backup cascade`, khóa luôn view con chung; hai cha dựng song song (threads: 4) thì
--   khóa chéo nhau → deadlock (lần build 23:17 ngày 2026-10-02). depends_on xếp ba cha chạy lần lượt:
--   rpt_build_info → rpt_health_run → rpt_health_ingest. Không đổi số liệu.
-- depends_on: {{ ref('rpt_build_info') }}
-- Sức khỏe dữ liệu (M5): 1 dòng = 1 lần chạy dbt trên CHÍNH kho này (build/run/test/seed).
-- Nguồn: ops.dbt_invocation + ops.dbt_node_result, do hook on-run-end ghi (macros/health_log.sql).
-- Là view nên luôn đọc log mới nhất. Lần chạy đang diễn ra chưa có ở đây: hook ghi sau khi chạy xong.
with node as (
    select
        invocation_id,
        cast(sum(case when resource_type = 'test' then 1 else 0 end) as integer)                          as n_tests_run,
        cast(sum(case when resource_type = 'test' and status = 'pass' then 1 else 0 end) as integer)      as n_tests_pass,
        cast(sum(case when resource_type = 'test' and status = 'fail' then 1 else 0 end) as integer)      as n_tests_fail,
        cast(sum(case when resource_type = 'test' and status = 'error' then 1 else 0 end) as integer)     as n_tests_error,
        cast(sum(case when resource_type = 'test' and status = 'warn' then 1 else 0 end) as integer)      as n_tests_warn,
        cast(sum(case when resource_type = 'test' and status = 'skipped' then 1 else 0 end) as integer)   as n_tests_skipped,
        cast(sum(case when resource_type = 'test' and test_kind = 'singular' then 1 else 0 end) as integer) as n_singular_run,
        cast(sum(case when resource_type in ('model', 'seed') then 1 else 0 end) as integer)              as n_models_run,
        cast(sum(case when resource_type in ('model', 'seed') and status <> 'success' then 1 else 0 end) as integer)
                                                                                                           as n_models_not_ok
    from {{ source('ops', 'dbt_node_result') }}
    group by invocation_id
)
select
    i.invocation_id,
    i.command,
    i.target_name,
    i.started_at_utc,
    i.finished_at_utc,
    i.dbt_version,
    i.n_tests_in_project,
    coalesce(n.n_tests_run, 0)      as n_tests_run,
    coalesce(n.n_tests_pass, 0)     as n_tests_pass,
    coalesce(n.n_tests_run - n.n_tests_pass, 0) as n_tests_not_pass,   -- fail + error + warn + skipped
    coalesce(n.n_tests_fail, 0)     as n_tests_fail,
    coalesce(n.n_tests_error, 0)    as n_tests_error,
    coalesce(n.n_tests_warn, 0)     as n_tests_warn,
    coalesce(n.n_tests_skipped, 0)  as n_tests_skipped,
    coalesce(n.n_singular_run, 0)   as n_singular_run,
    coalesce(n.n_models_run, 0)     as n_models_run,
    coalesce(n.n_models_not_ok, 0)  as n_models_not_ok
from {{ source('ops', 'dbt_invocation') }} i
left join node n on n.invocation_id = i.invocation_id
