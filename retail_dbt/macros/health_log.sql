{# Nhật ký chạy dbt ngay trong kho (schema ops), cho trang Sức khỏe dữ liệu của app (docs/gd2_app_plan.md, M5).
   Vì sao không đọc target/run_results.json: file đó chỉ có 1 bản, lần chạy sau (target khác) ghi đè, nên app đọc
   Postgres có thể hiện kết quả test của DuckDB. Ghi vào chính kho đang build thì mỗi backend có kết quả của riêng nó,
   và thiết kế để mang sang Snowflake ở GĐ 3 (không cần file trên máy); chưa chạy thử trên Snowflake.
   on-run-start: tạo bảng nếu chưa có. on-run-end: ghi 1 dòng/lần chạy + 1 dòng/node (model, seed, test).
   Hook on-run-end vẫn chạy khi có test FAIL, nên lần build lỗi cũng được ghi lại. #}

{% macro health_log_commands() -%}
    {{ return(['build', 'run', 'test', 'seed', 'snapshot']) }}
{%- endmacro %}

{% macro health_log_setup() %}
    {% if execute and flags.WHICH in health_log_commands() %}
        {% do run_query('create schema if not exists ops') %}
        {% do run_query("create table if not exists ops.dbt_invocation (
            invocation_id varchar(64), command varchar(20), target_name varchar(50),
            started_at_utc timestamp, finished_at_utc timestamp, dbt_version varchar(20),
            n_tests_in_project integer, n_models_in_project integer)") %}
        {% do run_query("create table if not exists ops.dbt_node_result (
            invocation_id varchar(64), node_id varchar(500), resource_type varchar(20), node_name varchar(300),
            status varchar(20), failures integer, execution_time " ~ type_double() ~ ", message varchar(2000),
            test_kind varchar(50), column_name varchar(200), tested_model varchar(200), description varchar(1000))") %}
    {% endif %}
{% endmacro %}

{% macro _sql_str(x, n=1000) -%}
    {%- if x is none -%}null{%- else -%}'{{ (x | string)[:n] | replace("'", "''") }}'{%- endif -%}
{%- endmacro %}

{% macro health_log_results(results) %}
    {% if execute and flags.WHICH in health_log_commands() %}
        {% set nodes = graph.nodes.values() | list %}
        {% set n_tests = nodes | selectattr('resource_type', 'equalto', 'test') | list | length %}
        {% set n_models = nodes | selectattr('resource_type', 'equalto', 'model') | list | length %}
        {% set finished = modules.datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') %}
        {% do run_query("insert into ops.dbt_invocation values ('" ~ invocation_id ~ "', '" ~ flags.WHICH ~ "', '"
            ~ target.name ~ "', cast('" ~ run_started_at.strftime('%Y-%m-%d %H:%M:%S') ~ "' as timestamp), cast('"
            ~ finished ~ "' as timestamp), '" ~ dbt_version ~ "', " ~ n_tests ~ ", " ~ n_models ~ ")") %}
        {% set rows = [] %}
        {% for r in results %}
            {% set n = r.node %}
            {% set meta = n.test_metadata if n.resource_type == 'test' else none %}
            {% set kind = (meta.name if meta else 'singular') if n.resource_type == 'test' else none %}
            {% set col = meta.kwargs.get('column_name') if meta else none %}
            {% set attached = n.attached_node if n.resource_type == 'test' else none %}
            {% do rows.append("('" ~ invocation_id ~ "', " ~ _sql_str(n.unique_id, 500) ~ ", '" ~ n.resource_type ~ "', "
                ~ _sql_str(n.name, 300) ~ ", '" ~ r.status ~ "', "
                ~ (r.failures if r.failures is not none else 'null') ~ ", " ~ (r.execution_time or 0) ~ ", "
                ~ _sql_str(r.message, 2000) ~ ", " ~ _sql_str(kind, 50) ~ ", " ~ _sql_str(col, 200) ~ ", "
                ~ _sql_str(attached.split('.')[-1] if attached else none, 200) ~ ", "
                ~ _sql_str(n.description if n.description else none) ~ ")") %}
        {% endfor %}
        {% if rows %}
            {% do run_query('insert into ops.dbt_node_result values ' ~ rows | join(', ')) %}
        {% endif %}
    {% endif %}
{% endmacro %}
