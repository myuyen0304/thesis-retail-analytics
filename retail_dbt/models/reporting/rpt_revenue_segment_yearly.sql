-- PS5: R theo từng chiều RIÊNG (category / region / acquisition_channel) × năm.
-- Ba chiều là ba góc nhìn của cùng một R: không cộng các chiều với nhau.
-- Lưới năm × nhóm đầy đủ (nhóm không có doanh thu năm đó = 0) để không mất phần sụt giảm.
{% set dims = ['category', 'region', 'acquisition_channel'] %}
with seg as (
    {%- for d in dims %}
    select '{{ d }}' as dimension_name, {{ d }} as dimension_value, year,
           sum(case when is_delivered then net_amount else 0 end) as r
    from {{ ref('int_reporting_order_items') }}
    group by {{ d }}, year
    {% if not loop.last %}union all{% endif %}
    {%- endfor %}
),
grid as (
    select v.dimension_name, v.dimension_value, t.year, t.r as r_total, t.delta_r as delta_r_total
    from (select distinct dimension_name, dimension_value from seg) v
    cross join {{ ref('rpt_revenue_yearly') }} t
),
full_grid as (
    select g.dimension_name, g.dimension_value, g.year, g.r_total, g.delta_r_total,
           coalesce(s.r, 0) as r
    from grid g
    left join seg s
      on s.dimension_name = g.dimension_name and s.dimension_value = g.dimension_value and s.year = g.year
),
l as (
    select
        f.*,
        {{ ratio('r', 'r_total') }}                                                       as share,
        lag(r) over (partition by dimension_name, dimension_value order by year)          as r0,
        lag({{ ratio('r', 'r_total') }}) over (partition by dimension_name, dimension_value order by year) as share0
    from full_grid f
)
select
    dimension_name,
    dimension_value,
    year,
    year between 2013 and 2022                                         as is_analysis_period,
    r,
    r_total,
    share,                                                             -- tỷ trọng trong R cùng năm
    case when year >= 2014 then r0 end                                 as r_prior_year,
    case when year >= 2014 then r - r0 end                             as delta_r,
    case when year >= 2014 then {{ ratio('r', 'r0') }} - 1 end         as yoy_rate,
    case when year >= 2014 then (share - share0) * 100 end             as share_shift_pp,   -- điểm %
    -- % đóng góp vào ΔR tổng: có thể âm hoặc > 100%; ΔR tổng = 0 → NULL
    case when year >= 2014 then {{ ratio('r - r0', 'delta_r_total') }} end as contribution_to_delta
from l
