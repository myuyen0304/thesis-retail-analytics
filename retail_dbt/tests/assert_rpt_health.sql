select * from (
-- M5 Sức khỏe dữ liệu (rpt_health_run, rpt_health_test, rpt_health_ingest, rpt_health_summary).
-- Lưu ý: test chạy TRONG lần build, trước hook on-run-end, nên kiểm log của các lần chạy TRƯỚC. Các quy tắc dưới đây
-- phải đúng với mọi lịch sử log (kể cả rỗng). Log của chính lần build này kiểm ở test app (tests/test_m5.py).
-- Trả về quy tắc bị vi phạm và số dòng vi phạm.

-- 1. Số đếm của rpt_health_run đếm lại độc lập bằng count(...) trên ops.dbt_node_result
with dem as (
    select i.invocation_id,
           count(case when n.resource_type = 'test' then 1 end)                               as n_tests_run,
           count(case when n.resource_type = 'test' and n.status = 'pass' then 1 end)         as n_tests_pass,
           count(case when n.resource_type = 'test' and n.status = 'fail' then 1 end)         as n_tests_fail,
           count(case when n.resource_type = 'test' and n.status = 'error' then 1 end)        as n_tests_error,
           count(case when n.resource_type = 'test' and n.test_kind = 'singular' then 1 end)  as n_singular_run,
           count(case when n.resource_type in ('model', 'seed') and n.status <> 'success' then 1 end) as n_models_not_ok
    from {{ source('ops', 'dbt_invocation') }} i
    left join {{ source('ops', 'dbt_node_result') }} n on n.invocation_id = i.invocation_id
    group by i.invocation_id
),
lan_kiem as (   -- lần chạy gần nhất có ít nhất 1 test
    select max(i.started_at_utc) as started_at_utc
    from {{ source('ops', 'dbt_invocation') }} i
    where exists (select 1 from {{ source('ops', 'dbt_node_result') }} n
                  where n.invocation_id = i.invocation_id and n.resource_type = 'test')
)
select 'rpt_health_run: so dem test / model khop dem lai' as rule, count(*) as n
from {{ ref('rpt_health_run') }} r
full outer join dem d on d.invocation_id = r.invocation_id
where r.invocation_id is null or d.invocation_id is null
   or r.n_tests_run <> d.n_tests_run or r.n_tests_pass <> d.n_tests_pass or r.n_tests_fail <> d.n_tests_fail
   or r.n_tests_error <> d.n_tests_error or r.n_singular_run <> d.n_singular_run
   or r.n_models_not_ok <> d.n_models_not_ok
union all
select 'rpt_health_run: pass + fail + error + warn + skipped = so test da chay; khong dat = phan con lai', count(*)
from {{ ref('rpt_health_run') }}
where n_tests_pass + n_tests_fail + n_tests_error + n_tests_warn + n_tests_skipped <> n_tests_run
   or n_tests_fail + n_tests_error + n_tests_warn + n_tests_skipped <> n_tests_not_pass
union all
-- 2. Tóm tắt lấy đúng lần kiểm gần nhất; rpt_health_test có đúng số test của lần đó
select 'rpt_health_summary: dung lan kiem gan nhat', count(*)
from {{ ref('rpt_health_summary') }} s
cross join lan_kiem k
where (k.started_at_utc is null and s.test_invocation_id is not null)
   or (k.started_at_utc is not null and (s.tests_started_at_utc is null or s.tests_started_at_utc <> k.started_at_utc))
union all
select 'rpt_health_test: so dong = so test cua lan kiem', count(*)
from (select count(*) as k from {{ ref('rpt_health_test') }}) t
cross join {{ ref('rpt_health_summary') }} s
where t.k <> coalesce(s.n_tests_run, 0)
union all
select 'rpt_health_summary: dung 1 dong', count(*)
from (select count(*) as k from {{ ref('rpt_health_summary') }}) t
where k <> 1
union all
-- 3. Trạng thái chung khớp các cờ (kiểm theo chiều ngược: từ mã suy ra điều kiện)
select 'status_code khop so loi va cac co', count(*)
from {{ ref('rpt_health_summary') }}
where (status_code = 'loi_test') <> (coalesce(n_tests_fail + n_tests_error, 0) > 0)
   or (status_code = 'chua_kiem') <> (test_invocation_id is null)
   or (status_code = 'tot' and not (tests_are_current and tests_are_complete and not raw_newer_than_build
                                    and n_tests_skipped = 0 and n_models_not_ok = 0))
   or (status_code = 'kiem_cu' and tests_are_current)
union all
-- 4. Log nạp nguồn
{% if target.type in ('postgres', 'databricks', 'snowflake') %}
select 'ingest: du 14 nguon, cung 1 lan nap', count(*)
from (select count(*) as k, count(distinct loaded_at_utc) as t from {{ ref('rpt_health_ingest') }}) x
where k > 0 and (k <> 14 or t <> 1)
union all
select 'ingest: so dong trong log = so dong bang raw', count(*)
from {{ ref('rpt_health_ingest') }} g
join (
    {%- set nguon = ['customers', 'geography', 'products', 'promotions', 'orders', 'order_items', 'payments',
                     'shipments', 'returns', 'reviews', 'inventory', 'web_traffic', 'sales', 'sample_submission'] %}
    {%- for t in nguon %}
    select '{{ t }}' as source, count(*) as n from {{ source('raw', t) }}{% if not loop.last %} union all{% endif %}
    {%- endfor %}
) r on r.source = g.source
where r.n <> g.row_count
{% else %}
select 'ingest: DuckDB khong co log nap, ingest_mode = doc_csv', count(*)
from {{ ref('rpt_health_summary') }}
where ingest_mode <> 'doc_csv' or n_sources_ingested <> 0
{% endif %}
) t
where n > 0
