-- Periodic snapshot, grain = (cuối tháng × sản phẩm). BÁN CỘNG TÍNH: không SUM stock_on_hand qua nhiều mốc.
-- 5 cột dẫn xuất TÍNH lại theo công thức (star_schema.md §4, §7), không chép từ nguồn;
-- test assert_inventory_derived_matches_source xác nhận khớp inventory.csv.
{%- set dbl = type_double() %}
{%- set dos = round_half_even('cast(stock_on_hand as ' ~ dbl ~ ') / (cast(units_sold as ' ~ dbl ~ ') / 30)', 1) %}
with i as (
    select *, {{ dos }} as dos
    from {{ ref('stg_inventory') }}
)
select
    {{ date_sk('i.snapshot_date') }}  as date_sk,
    p.product_sk,
    i.stock_on_hand,
    i.units_received,
    i.units_sold,                     -- KHÔNG khớp fact_order_item (§6 mục 3)
    i.stockout_days,
    i.dos                             as days_of_supply,
    {{ round_half_even('1 - cast(i.stockout_days as ' ~ dbl ~ ') / 30', 4) }} as fill_rate,
    {{ round_half_even('cast(i.units_sold as ' ~ dbl ~ ') / (i.stock_on_hand + i.units_sold)', 4) }} as sell_through_rate,
    i.stockout_days > 0               as stockout_flag,
    i.dos > 90                        as overstock_flag
from i
join {{ ref('dim_product') }} p on p.product_id = i.product_id
