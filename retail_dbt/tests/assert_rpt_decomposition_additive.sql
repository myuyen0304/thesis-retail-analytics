select * from (
-- PS4/PS5: từng phần tách đúng CÔNG THỨC deck (slide 11, 13) — không chỉ đúng tổng —, và cộng về tổng.
-- Công thức tính lại từ N, Q, R, C của năm trước/năm nay (U = Q/N, P = R/Q, F = N/C), không dùng cột u/p/f.
with y as (
    select year, n, q, r, c, delta_r, delta_n, contrib_n, contrib_u, contrib_p, contrib_c, contrib_f,
           yoy_rate, yoy_n, yoy_u, yoy_p,
           lag(n) over (order by year) n0, lag(q) over (order by year) q0,
           lag(r) over (order by year) r0, lag(c) over (order by year) c0
    from {{ ref('rpt_revenue_yearly') }}
),
e as (
    select y.*,
           (n - n0) * (cast(q0 as {{ type_double() }}) / n0) * (r0 / q0)                          as exp_n,
           n * (cast(q as {{ type_double() }}) / n - cast(q0 as {{ type_double() }}) / n0) * (r0 / q0) as exp_u,
           n * (cast(q as {{ type_double() }}) / n) * (r / q - r0 / q0)                           as exp_p,
           (c - c0) * (cast(n0 as {{ type_double() }}) / c0)                                     as exp_c,
           c * (cast(n as {{ type_double() }}) / c - cast(n0 as {{ type_double() }}) / c0)        as exp_f
    from y
)
select 'contrib N/U/P/C/F dung cong thuc deck (dung thu tu N -> U -> P)' as rule, count(*) as n
from e
where year >= 2014
  and ({{ differs('contrib_n', 'exp_n') }} or {{ differs('contrib_u', 'exp_u') }} or {{ differs('contrib_p', 'exp_p') }}
       or {{ differs('contrib_c', 'exp_c', 1e-6) }} or {{ differs('contrib_f', 'exp_f', 1e-6) }})
union all
select 'contrib_n + contrib_u + contrib_p = delta_r = R1 - R0', count(*)
from e
where year >= 2014 and ({{ differs('contrib_n + contrib_u + contrib_p', 'delta_r') }} or {{ differs('delta_r', 'r - r0') }})
union all
select 'contrib_c + contrib_f = delta_n = N1 - N0', count(*)
from e
where year >= 2014 and ({{ differs('contrib_c + contrib_f', 'delta_n', 1e-6) }} or delta_n <> n - n0)
union all
select 'tang truong R, N, U, P dung (nam >= 2014)', count(*)
from e
where year >= 2014 and ({{ differs('yoy_rate', 'r / r0 - 1', 1e-12) }} or {{ differs('yoy_n', 'cast(n as ' ~ type_double() ~ ') / n0 - 1', 1e-12) }}
       or {{ differs('(1 + yoy_n) * (1 + yoy_u) * (1 + yoy_p) - 1', 'yoy_rate', 1e-9) }})
union all
select 'nam < 2014 khong co tang truong / phan tach', count(*)
from e
where year < 2014 and (delta_r is not null or yoy_rate is not null or contrib_n is not null or delta_n is not null)

-- PS5
union all
select 'PS5: moi chieu x nam cong ve tong (R, ty trong, delta, dich chuyen, dong gop)', count(*)
from (
    select dimension_name, year,
           sum(r) as r, sum(share) as share, sum(delta_r) as delta_r,
           sum(share_shift_pp) as shift, sum(contribution_to_delta) as contrib
    from {{ ref('rpt_revenue_segment_yearly') }}
    group by dimension_name, year
) s
join {{ ref('rpt_revenue_yearly') }} y on y.year = s.year
where {{ differs('s.r', 'y.r') }}
   or {{ differs('s.share', '1', 1e-9) }}
   or (y.year >= 2014 and ({{ differs('s.delta_r', 'y.delta_r') }} or {{ differs('s.shift', '0', 1e-7) }}
                           or (y.delta_r <> 0 and {{ differs('s.contrib', '1', 1e-9) }})))
union all
-- Lưới kỳ vọng dựng từ NGUỒN (fact_order_item + dim), không từ chính output: đủ mọi nhóm × 11 năm, không trùng
select 'PS5: luoi nhom x nam dung voi nguon, khong trung khoa', count(*)
from (
    {%- for d, src in [('category', 'p.category'), ('region', 'g.region'), ('acquisition_channel', 'c.acquisition_channel')] %}
    select '{{ d }}' as dimension_name, {{ src }} as dimension_value
    from {{ ref('fact_order_item') }} f
    join {{ ref('dim_product') }} p on p.product_sk = f.product_sk
    join {{ ref('dim_customer') }} c on c.customer_sk = f.customer_sk
    join {{ ref('dim_geography') }} g on g.geography_sk = c.geography_sk
    group by {{ src }}
    {% if not loop.last %}union all{% endif %}
    {%- endfor %}
) v
cross join (select distinct year from {{ ref('rpt_revenue_yearly') }}) t
full outer join (
    select dimension_name, dimension_value, year, count(*) as k
    from {{ ref('rpt_revenue_segment_yearly') }}
    group by dimension_name, dimension_value, year
) s on s.dimension_name = v.dimension_name and s.dimension_value = v.dimension_value and s.year = t.year
where v.dimension_name is null or s.dimension_name is null or s.k <> 1
) checks
where n > 0
