{# Measure cộng dồn của 5 PS, gom từ int_reporting_order_items theo một grain bất kỳ (tháng, năm).
   N và C là đếm PHÂN BIỆT nên phải tính lại ở từng grain, không cộng từ grain nhỏ hơn.
   Dùng CASE thay cho FILTER (Snowflake không có FILTER). #}
{% macro revenue_measures() -%}
    sum(gross_amount)                                                            as g,
    sum(case when is_delivered then net_amount end)                              as r,
    sum(case when order_status = 'cancelled' then gross_amount else 0 end)       as cancelled_gross,
    sum(case when order_status = 'returned' then gross_amount else 0 end)        as returned_gross,
    sum(case when order_status in ('created', 'paid', 'shipped') then gross_amount else 0 end)
                                                                                 as undelivered_gross,
    sum(case when is_delivered then discount_amount else 0 end)                  as delivered_discount,
    count(distinct case when is_delivered then order_id end)                     as n,
    sum(case when is_delivered then quantity else 0 end)                         as q,
    count(distinct case when is_delivered then customer_sk end)                  as c
{%- endmacro %}

{# Tỷ số tính lại từ tử/mẫu (không SUM/AVG tỷ số con); mẫu 0 -> NULL.
   Model và test đều chia qua macro này: chia thẳng hai DECIMAL thì Databricks cắt kết quả còn 6 chữ số thập phân. #}
{% macro ratio(num, den) -%}
    (cast({{ num }} as {{ type_double() }}) / nullif(cast({{ den }} as {{ type_double() }}), 0))
{%- endmacro %}

{# Chỉ số dẫn xuất U, P, F, AOV và các tỷ lệ PS1 #}
{% macro revenue_ratios() -%}
    {{ ratio('q', 'n') }}                    as u,          /* số món mỗi đơn */
    {{ ratio('r', 'q') }}                    as p,          /* giá TB mỗi món, sau chiết khấu */
    {{ ratio('n', 'c') }}                    as f,          /* số đơn mỗi khách */
    {{ ratio('r', 'n') }}                    as aov,
    {{ ratio('r', 'g') }}                    as capture_rate,         /* R/G */
    {{ ratio('cancelled_gross', 'g') }}      as cancelled_rate,       /* tiền hàng bị hủy / G */
    {{ ratio('delivered_discount', 'r + delivered_discount') }} as discount_rate  /* chiết khấu / tiền hàng đơn delivered */
{%- endmacro %}

{# Cho test: a lệch b. NULL cũng tính là lệch (abs(NULL) > x không bao giờ TRUE nên sẽ lọt).
   Sai số = max(tuyệt đối, tương đối × |b|): tỷ số tính bằng DOUBLE (~15 chữ số). #}
{% macro differs(a, b, abs_tol=0.01, rel_tol=1e-9) -%}
    (({{ a }}) is null or ({{ b }}) is null
     or abs(({{ a }}) - ({{ b }})) > greatest({{ abs_tol }}, {{ rel_tol }} * abs({{ b }})))
{%- endmacro %}
