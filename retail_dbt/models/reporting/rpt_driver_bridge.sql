-- PS4 / PS5: biểu đồ thác, dạng dài (1 dòng = 1 cột của thác). App chỉ đọc và vẽ, không tự cộng dồn (như rpt_revenue_bridge).
-- bridge_code 'r_nup': R đầu kỳ → + phần N → + phần U → + phần P → R cuối kỳ   (deck slide 11)
-- bridge_code 'n_cf':  N đầu kỳ → + phần C → + phần F → N cuối kỳ               (deck slide 13)
-- Cột đầu và cuối đứng từ 0 (step_year = năm của cột đó); cột giữa treo từ bar_start tới bar_end = bar_start + amount.
-- Mọi cột số ép về double: R là decimal, phần góp là double, trộn lẫn thì hai backend trả kiểu khác nhau.
{% set dbl = type_double() %}
with p as (
    select period_type, period_code, start_year, end_year,
           cast(r_start as {{ dbl }}) as r0, cast(r_end as {{ dbl }}) as r1,
           contrib_n, contrib_u, contrib_p,
           cast(n_start as {{ dbl }}) as n0, cast(n_end as {{ dbl }}) as n1,
           contrib_c, contrib_f
    from {{ ref('rpt_driver_period') }}
),
s as (
    select period_type, period_code, 'r_nup' as bridge_code, 1 as step_order, 'r_start' as step_code, start_year as step_year,
           r0 as amount, cast(0 as {{ dbl }}) as bar_start, r0 as bar_end
    from p
    union all
    select period_type, period_code, 'r_nup', 2, 'n', null, contrib_n, r0, r0 + contrib_n from p
    union all
    select period_type, period_code, 'r_nup', 3, 'u', null, contrib_u, r0 + contrib_n, r0 + contrib_n + contrib_u from p
    union all
    select period_type, period_code, 'r_nup', 4, 'p', null, contrib_p, r0 + contrib_n + contrib_u,
           r0 + contrib_n + contrib_u + contrib_p from p
    union all
    select period_type, period_code, 'r_nup', 5, 'r_end', end_year, r1, cast(0 as {{ dbl }}), r1 from p
    union all
    select period_type, period_code, 'n_cf', 1, 'n_start', start_year, n0, cast(0 as {{ dbl }}), n0 from p
    union all
    select period_type, period_code, 'n_cf', 2, 'c', null, contrib_c, n0, n0 + contrib_c from p
    union all
    select period_type, period_code, 'n_cf', 3, 'f', null, contrib_f, n0 + contrib_c, n0 + contrib_c + contrib_f from p
    union all
    select period_type, period_code, 'n_cf', 4, 'n_end', end_year, n1, cast(0 as {{ dbl }}), n1 from p
)
select period_type, period_code, bridge_code, step_order, step_code, cast(step_year as integer) as step_year,
       amount, bar_start, bar_end
from s
