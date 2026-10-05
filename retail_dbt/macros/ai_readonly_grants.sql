{# Cấp lại SELECT cho role chỉ-đọc của chat AI sau mỗi lần build PostgreSQL (docs/ai_explain_nhat_ky.md §3 mục 8).
   dbt dựng lại bảng/view nên quyền cấp theo từng bảng bị mất; trước đây phải chạy tay scripts/ops/pg_ai_readonly_role.py.
   - Chỉ chạy trên target postgres, và chỉ khi role đã tồn tại (DB mới chưa tạo role thì bỏ qua, build không lỗi).
   - Chỉ cấp ĐÚNG danh sách var ai_readonly_relations (= ai_explain.tools.ALLOWED_RELATIONS, test_ai_tools.py kiểm);
     không ALTER DEFAULT PRIVILEGES cho cả schema (role AI không được đọc int_reporting_order_items).
   - Bảng chưa có (build một phần) thì bỏ qua bảng đó.
   Tạo role lần đầu và kiểm quyền vẫn bằng scripts/ops/pg_ai_readonly_role.py (--check). #}
{% macro ai_readonly_grants() -%}
{%- if target.type == 'postgres' -%}
do $$
declare
    rel text;
    role_name text := '{{ env_var("PG_AI_USER", "retail_ai_ro") | replace("'", "''") }}';
begin
    if not exists (select 1 from pg_roles where rolname = role_name) then
        return;
    end if;
    if to_regnamespace('reporting') is not null then
        execute format('grant usage on schema reporting to %I', role_name);
    end if;
    foreach rel in array array[{% for r in var('ai_readonly_relations') %}'{{ r }}'{{ ', ' if not loop.last }}{% endfor %}]
    loop
        if to_regclass(rel) is not null then
            execute format('grant select on %s to %I', rel, role_name);
        end if;
    end loop;
end $$
{%- else -%}
select 1
{%- endif -%}
{%- endmacro %}
