{# Macro cho những chỗ cú pháp DuckDB (dev) và Snowflake (production) khác nhau. #}

{# Tên schema đúng như khai báo (staging/intermediate/marts), không ghép tiền tố target #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name if custom_schema_name is not none else target.schema }}
{%- endmacro %}

{# chuỗi nguồn: trim, chuỗi rỗng -> NULL (giống scripts/build/build_silver.py) #}
{% macro clean(col) -%}
    nullif(trim({{ col }}), '')
{%- endmacro %}

{# date -> khóa ngày YYYYMMDD; viết bằng extract nên chạy được trên mọi adapter #}
{% macro date_sk(d) -%}
    cast(extract(year from {{ d }}) * 10000 + extract(month from {{ d }}) * 100 + extract(day from {{ d }}) as integer)
{%- endmacro %}

{# thứ trong tuần, 0 = thứ Hai #}
{% macro dow_monday0(d) -%}{{ adapter.dispatch('dow_monday0')(d) }}{%- endmacro %}
{% macro default__dow_monday0(d) -%}(isodow({{ d }}) - 1){%- endmacro %}
{% macro snowflake__dow_monday0(d) -%}(dayofweekiso({{ d }}) - 1){%- endmacro %}
{% macro postgres__dow_monday0(d) -%}(cast(extract(isodow from {{ d }}) as integer) - 1){%- endmacro %}

{# kiểu số thực 8 byte: Postgres không có tên kiểu `double` #}
{% macro type_double() -%}{{ adapter.dispatch('type_double')() }}{%- endmacro %}
{% macro default__type_double() -%}double{%- endmacro %}
{% macro postgres__type_double() -%}double precision{%- endmacro %}

{# Làm tròn như numpy/pandas (nguồn sinh bằng pandas): nhân 10^d rồi làm tròn về số chẵn.
   146,25 -> 146,2 ; 0,25625 -> 0,2562. ROUND thường lệch 977/60.247 dòng tồn kho. #}
{% macro round_half_even(x, digits) -%}{{ adapter.dispatch('round_half_even')(x, digits) }}{%- endmacro %}
{% macro default__round_half_even(x, digits) -%}
    (round_even(({{ x }}) * 1e{{ digits }}, 0) / 1e{{ digits }})
{%- endmacro %}
{# Postgres: round(double precision) làm tròn về số chẵn khi đúng nửa (theo rint của nền tảng) #}
{% macro postgres__round_half_even(x, digits) -%}
    (round(cast(({{ x }}) as double precision) * cast(1e{{ digits }} as double precision)) / cast(1e{{ digits }} as double precision))
{%- endmacro %}
{% macro snowflake__round_half_even(x, digits) -%}
    (round(cast(({{ x }}) * 1e{{ digits }} as number(38, 12)), 0, 'HALF_TO_EVEN') / 1e{{ digits }})
{%- endmacro %}

{# Dãy số nguyên 0..n-1 (n <= 10.000), dùng để sinh dim_date — không cần package ngoài #}
{% macro integers(n) -%}
    select a.i + b.i * 10 + c.i * 100 + d.i * 1000 as i
    from {{ _digits() }} a cross join {{ _digits() }} b cross join {{ _digits() }} c cross join {{ _digits() }} d
    where a.i + b.i * 10 + c.i * 100 + d.i * 1000 < {{ n }}
{%- endmacro %}
{% macro _digits() -%}
    (select 0 as i union all select 1 union all select 2 union all select 3 union all select 4
     union all select 5 union all select 6 union all select 7 union all select 8 union all select 9)
{%- endmacro %}
