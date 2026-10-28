{# Một điều kiện chung cho các model và test của nguồn mở rộng. #}
{% macro extension_enabled(name) -%}
    {{ return(name in var('extensions', [])) }}
{%- endmacro %}
