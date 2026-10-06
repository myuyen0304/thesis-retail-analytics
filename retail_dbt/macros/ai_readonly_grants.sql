{# Cấp lại SELECT cho role chỉ-đọc của chat AI sau mỗi lần build PostgreSQL (docs/ai_explain_nhat_ky.md §3 mục 8).
   dbt dựng lại bảng/view nên quyền cấp theo từng bảng bị mất; trước đây phải chạy tay scripts/ops/pg_ai_readonly_role.py.
   - Chỉ chạy trên target postgres, và chỉ khi role đã tồn tại (DB mới chưa tạo role thì bỏ qua, build không lỗi).
   - Chỉ cấp ĐÚNG danh sách var ai_readonly_relations (= ai_explain.tools.ALLOWED_RELATIONS, test_ai_tools.py kiểm);
     không ALTER DEFAULT PRIVILEGES cho cả schema (role AI không được đọc int_reporting_order_items).
   - Bảng chưa có (build một phần) thì bỏ qua bảng đó.
   Tạo role lần đầu và kiểm quyền vẫn bằng scripts/ops/pg_ai_readonly_role.py (--check).
   Databricks (2026-10-06): cấp cho service principal chỉ-đọc của AI (application id trong env RETAIL_AI_DBX_PRINCIPAL,
   scripts/databricks/run_dbt.py tự lấy từ .env.ai.local; không ghi cứng vì khác nhau theo workspace):
   USE CATALOG, USE SCHEMA reporting và SELECT đúng danh sách var. Hook Databricks chỉ chạy một câu, nên từng GRANT
   chạy qua run_query; chưa đặt principal thì bỏ qua. Guard của app (dwh/guarded.py) vẫn kiểm quyền thật khi đọc. #}
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
{%- elif target.type == 'databricks' -%}
{%- set principal = env_var('RETAIL_AI_DBX_PRINCIPAL', '') -%}
{%- if execute and principal -%}
    {%- if not modules.re.fullmatch('[0-9a-fA-F-]{36}', principal) -%}
        {{ exceptions.raise_compiler_error('RETAIL_AI_DBX_PRINCIPAL phải là application id (UUID) của service principal') }}
    {%- endif -%}
    {%- do run_query('grant use catalog on catalog `' ~ target.database ~ '` to `' ~ principal ~ '`') -%}
    {%- set schemas = [] -%}
    {%- for r in var('ai_readonly_relations') if r.split('.')[0] not in schemas -%}
        {%- do schemas.append(r.split('.')[0]) -%}
    {%- endfor -%}
    {%- for schema in schemas -%}
        {%- set found = run_query("select 1 from `" ~ target.database ~ "`.information_schema.schemata where schema_name = '"
                                  ~ schema ~ "'") -%}
        {%- if found | length > 0 -%}
            {%- do run_query('grant use schema on schema `' ~ target.database ~ '`.`' ~ schema ~ '` to `' ~ principal ~ '`') -%}
        {%- endif -%}
    {%- endfor -%}
    {%- for r in var('ai_readonly_relations') -%}
        {%- set parts = r.split('.') -%}
        {%- if adapter.get_relation(database=target.database, schema=parts[0], identifier=parts[1]) is not none -%}
            {%- do run_query('grant select on table `' ~ target.database ~ '`.`' ~ parts[0] ~ '`.`' ~ parts[1]
                             ~ '` to `' ~ principal ~ '`') -%}
        {%- endif -%}
    {%- endfor -%}
{%- endif -%}
select 1
{%- else -%}
select 1
{%- endif -%}
{%- endmacro %}
