{# D3: kỳ của bản có đợt. Không có đợt thì biến dùng mặc định và SQL biên dịch không đổi. #}
{% macro co_dot() -%}
    {{ return(var('co_dot', false)) }}
{%- endmacro %}

{% macro ky_cuoi() -%}
    {{ return(var('analysis_end_year', 2022)) }}
{%- endmacro %}

{% macro dot_so_dong(nguon) -%}
    {{ return(var('dot_so_dong', {}).get(nguon, 0)) }}
{%- endmacro %}

{# Giai đoạn PS2 của bản: năm mới gộp vào giai đoạn cuối, không sửa seed (PM chốt 2026-10-31). #}
{% macro ps2_phases_ky(bi_danh='') -%}
    {%- if co_dot() -%}
        (select phase_code, phase_name, start_year,
                case when end_year = (select max(end_year) from {{ ref('ps2_phases') }}) then {{ ky_cuoi() }} else end_year end as end_year,
                trend, end_turn_note
         from {{ ref('ps2_phases') }}) {{ bi_danh or 'ps2_phases_ky' }}
    {%- else -%}
        {{ ref('ps2_phases') }}{% if bi_danh %} {{ bi_danh }}{% endif %}
    {%- endif -%}
{%- endmacro %}
