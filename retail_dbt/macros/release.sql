{# Namespace tùy chọn: mặc định giữ hành vi các backend cũ. #}
{% macro release_schema(layer) -%}
    {%- set release = var('release_id', '') -%}
    {%- if release and not modules.re.fullmatch('[a-f0-9]{24}', release) -%}
        {{ exceptions.raise_compiler_error('release_id phải gồm 24 ký tự hex') }}
    {%- endif -%}
    {{ ('r_' ~ release ~ '_') if release else '' }}{{ layer }}
{%- endmacro %}
