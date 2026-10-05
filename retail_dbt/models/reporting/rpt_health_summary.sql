{{ config(materialized='view') }}
-- Sức khỏe dữ liệu (M5): 1 dòng, trạng thái chung để app hiện thông báo. App chỉ đổi status_code sang câu chữ.
-- Lần kiểm = lần chạy gần nhất có chạy test. Mốc so = rpt_build_info.built_at_utc (lúc dựng kho, cùng run_started_at).
--   tests_are_current   : lần kiểm bắt đầu từ lúc dựng kho trở về sau (cùng lần `dbt build`, hoặc `dbt test` chạy sau);
--                         false = kho được dựng lại sau lần kiểm cuối (vd. `dbt run`), kết quả test có thể đã cũ.
--   tests_are_complete  : chạy đủ mọi test của dự án (không phải chỉ một phần như `dbt test -s ...`).
--   raw_newer_than_build: nạp lại nguồn sau lần dựng kho → số trên app chưa theo nguồn mới (chỉ Postgres).
-- status_code, theo thứ tự ưu tiên: chua_kiem, loi_test, loi_build, kiem_cu, kiem_thieu, nguon_moi_hon, tot.
with b as (
    select built_at_utc, data_end_date from {{ ref('rpt_build_info') }}
),
t as (
    select * from {{ ref('rpt_health_run') }}
    where n_tests_run > 0
    order by started_at_utc desc
    limit 1
),
i as (
    select max(loaded_at_utc) as last_ingest_at_utc, cast(count(*) as integer) as n_sources_ingested
    from {{ ref('rpt_health_ingest') }}
),
f as (
    select
        b.built_at_utc,
        b.data_end_date,
        t.invocation_id                   as test_invocation_id,
        t.command                         as test_command,
        t.started_at_utc                  as tests_started_at_utc,
        t.finished_at_utc                 as tests_finished_at_utc,
        t.n_tests_in_project,
        t.n_tests_run,
        t.n_tests_pass,
        t.n_tests_not_pass,
        t.n_tests_fail,
        t.n_tests_error,
        t.n_tests_warn,
        t.n_tests_skipped,
        t.n_singular_run,
        t.n_tests_run - t.n_singular_run  as n_generic_run,
        t.n_models_not_ok,
        '{{ "log" if target.type in ("postgres", "databricks", "snowflake") else "doc_csv" }}' as ingest_mode,
        i.last_ingest_at_utc,
        i.n_sources_ingested,
        t.started_at_utc >= b.built_at_utc                     as tests_are_current,
        t.n_tests_run = t.n_tests_in_project                   as tests_are_complete,
        coalesce(i.last_ingest_at_utc > b.built_at_utc, false) as raw_newer_than_build
    from b
    left join t on 1 = 1
    cross join i
)
select
    f.*,
    case
        when test_invocation_id is null then 'chua_kiem'
        when n_tests_fail + n_tests_error > 0 then 'loi_test'
        when n_tests_skipped + n_models_not_ok > 0 then 'loi_build'
        when not tests_are_current then 'kiem_cu'
        when not tests_are_complete then 'kiem_thieu'
        when raw_newer_than_build then 'nguon_moi_hon'
        else 'tot'
    end as status_code
from f
