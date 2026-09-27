-- 5 cột dẫn xuất tồn kho TÍNH lại theo công thức phải khớp inventory.csv trên cả 60.247 dòng.
select f.date_sk, p.product_id
from {{ ref('fact_inventory_snapshot') }} f
join {{ ref('dim_product') }} p on p.product_sk = f.product_sk
join {{ ref('stg_inventory') }} s
  on {{ date_sk('s.snapshot_date') }} = f.date_sk and s.product_id = p.product_id
where abs(f.days_of_supply - s.days_of_supply) > 1e-9
   or abs(f.fill_rate - s.fill_rate) > 1e-9
   or abs(f.sell_through_rate - s.sell_through_rate) > 1e-9
   or f.stockout_flag <> (s.stockout_flag = 1)
   or f.overstock_flag <> (s.overstock_flag = 1)
