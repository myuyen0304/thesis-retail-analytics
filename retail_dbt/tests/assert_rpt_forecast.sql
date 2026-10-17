-- Bật/tắt bằng config trong tests/_singular_tests.yml: chỉ chạy khi pipeline truyền var forecast_path.
-- Kho dự báo B2b (docs/hop_dong_du_bao.md §9). Trả về quy tắc bị vi phạm và số dòng vi phạm.
with d as (select * from {{ ref('rpt_forecast_daily') }}),
b as (select * from {{ ref('rpt_forecast_backtest') }}),
actual as (
    select max(date_sk) as last_sk,
           min(cast(cogs as {{ type_double() }}) / cast(revenue as {{ type_double() }})) as ratio_lo,
           max(cast(cogs as {{ type_double() }}) / cast(revenue as {{ type_double() }})) as ratio_hi,
           sum(case when date_sk between 20220801 and 20220831 then cast(revenue as {{ type_double() }}) end) as g_aug_2022
    from {{ ref('fact_daily_sales') }}
    where is_actual
),
-- Luật chọn (hợp đồng §5) tính lại từ mae_g, mae_cogs; ngưỡng hòa 1% khớp TIE trong scripts/forecast/core.py
s as (
    select model, cogs_method, role, candidate_rank, fold_origin,
           sum(case when metric = 'mae_g' then value end) as mae_g,
           sum(case when metric = 'mae_cogs' then value end) as mae_cogs,
           (sum(case when metric = 'mae_g' then value end) + sum(case when metric = 'mae_cogs' then value end)) / 2 as score
    from b
    where metric in ('mae_g', 'mae_cogs')
    group by model, cogs_method, role, candidate_rank, fold_origin
),
cand as (
    select s.model, s.cogs_method, s.candidate_rank, avg(s.score) as score_mean,
           sum(case when s.score < f.score then 1 else 0 end) as wins, count(*) as folds
    from s
    join (select fold_origin, score from s where role = 'floor') f on f.fold_origin = s.fold_origin
    where s.role = 'candidate'
    group by s.model, s.cogs_method, s.candidate_rank
),
ok as (select * from cand where folds = 3 and wins = 3),
pick as (
    select model || '|' || cogs_method as k
    from ok
    where score_mean <= (select min(score_mean) from ok) * (1 + 0.01)
    order by candidate_rank
    limit 1
),
-- Bước của luật đã chọn (khớp core.py): không ai qua sàn → bước 1; chọn đúng ứng viên điểm thấp nhất → bước 2; còn lại
-- (hòa trong 1%, chọn ứng viên đơn giản hơn) → bước 3. Chat đọc selection_step để giải thích (RV06, review Codex 2026-10-15).
lowest as (
    select model || '|' || cogs_method as k
    from ok
    order by score_mean, candidate_rank
    limit 1
),
step as (
    select case when (select count(*) from ok) = 0 then 'buoc_1_khong_ung_vien_nao_qua_san'
                when (select k from pick) = (select k from lowest) then 'buoc_2_diem_thap_nhat'
                else 'buoc_3_hoa_chon_don_gian' end as expected
),
-- Các chỉ số chat đọc từ rpt_forecast_backtest: mỗi ứng viên / mốc phải có đủ ở cả 3 fold
need_metric as (
    select 'score' as metric union all select 'mae_g' union all select 'mae_cogs' union all select 'rmse_g'
    union all select 'r2_g' union all select 'mape_g_thang' union all select 'coverage_80' union all select 'tai_tao_bien_do'
)
select * from (
-- 0. Cột bắt buộc và giá trị hợp lệ
select 'rpt_forecast_daily: cot bat buoc khong null, cogs_method hop le' as rule, count(*) as n
from d
where forecast_date is null or model is null or model_version is null or trained_through is null
   or is_primary is null or yhat is null or cogs_yhat is null or cogs_method not in ('ratio', 'direct', 'copy')
union all
select 'rpt_forecast_backtest: cot bat buoc khong null, role hop le', count(*)
from b
where model is null or fold_origin is null or metric is null or value is null or role not in ('floor', 'baseline', 'candidate')
union all
-- 1. Mỗi ứng viên đủ 548 ngày liền nhau, không trùng, bắt đầu ngay sau ngày thực tế cuối
select 'moi ung vien du 548 ngay lien nhau, khong trung', count(*)
from (
    select model, cogs_method, count(*) as k, count(distinct forecast_date) as kd,
           {{ dbt.datediff('min(forecast_date)', 'max(forecast_date)', 'day') }} as span
    from d group by model, cogs_method
) t
where k <> 548 or kd <> 548 or span <> 547
union all
select 'trained_through = ngay thuc te cuoi; du bao trong 548 ngay sau do; co model_version, run_id', count(*)
from d cross join actual a
where {{ date_sk('d.trained_through') }} <> a.last_sk
   or {{ dbt.datediff('d.trained_through', 'd.forecast_date', 'day') }} not between 1 and 548
   or d.model_version is null or d.run_id is null
union all
-- 2. Khoảng dự báo và số dương. coalesce: so sánh với NULL ra NULL và WHERE sẽ bỏ qua dòng đó (RV05)
select '0 < lower <= yhat <= upper; COGS du bao > 0', count(*)
from d
where not coalesce(d.lower > 0 and d.lower <= d.yhat and d.yhat <= d.upper and d.cogs_yhat > 0, false)
union all
-- 2b. Cận, mức khoảng, tỷ lệ COGS/G: không NULL, hữu hạn (NaN / vô cực nằm ngoài BETWEEN ở cả ba nền tảng), mức = 0,8 (Q6)
select 'khoang du bao: lower, upper, interval_level, cogs_ratio_hat khong null, huu han; interval_level = 0.8', count(*)
from d
where d.lower is null or d.upper is null or d.interval_level is null or d.cogs_ratio_hat is null
   or not coalesce(d.yhat between 0 and 1e15 and d.lower between 0 and 1e15 and d.upper between 0 and 1e15
                   and d.cogs_yhat between 0 and 1e15 and d.cogs_ratio_hat between 0 and 100
                   and abs(d.interval_level - 0.8) < 1e-9, false)
union all
-- 3. Đúng một ứng viên chính, và nó khớp luật chọn tính lại từ backtest
select 'dung mot ung vien is_primary', count(*)
from (select count(distinct model || '|' || cogs_method) as k from d where is_primary) t
where k <> 1
union all
select 'ung vien chinh co is_primary o moi ngay', count(*)
from (
    select model, cogs_method, sum(case when is_primary then 1 else 0 end) as p, count(*) as k
    from d group by model, cogs_method
) t
where p <> 0 and p <> k
union all
select 'is_primary khop luat chon tinh lai tu mae_g, mae_cogs (hop dong §5)', count(*)
from (
    select coalesce((select k from pick), (select max(model || '|' || cogs_method) from s where role = 'floor')) as expected,
           (select max(model || '|' || cogs_method) from d where is_primary) as got
) t
where got is null or expected <> got
union all
select 'selection_step cua ung vien chinh khop buoc luat tinh lai; ung vien khac khong co selection_step', count(*)
from d cross join step
where (d.is_primary and (d.selection_step is null or d.selection_step <> step.expected))
   or (not d.is_primary and d.selection_step is not null)
union all
-- 4. Backtest đủ để tính lại luật
select 'dung mot moc san trong backtest', count(*)
from (select count(distinct model || '|' || cogs_method) as k from b where role = 'floor') t
where k <> 1
union all
select 'moi ung vien va moc co mae_g, mae_cogs o du 3 fold', count(*)
from (
    select c.model, c.cogs_method, count(distinct s.fold_origin) as k
    from (select distinct model, cogs_method from d) c
    left join s on s.model = c.model and s.cogs_method = c.cogs_method and s.mae_g is not null and s.mae_cogs is not null
    group by c.model, c.cogs_method
) t
where k <> 3
union all
-- 4b. Chat xếp hạng bằng các dòng score và đọc đủ chỉ số: score khớp (mae_g + mae_cogs) / 2, khóa không trùng,
--     đủ chỉ số ở 3 fold (RV06)
select 'score backtest = (mae_g + mae_cogs) / 2 o moi ung vien x fold', count(*)
from s
left join (select model, cogs_method, fold_origin, value from b where metric = 'score') v
       on v.model = s.model and v.cogs_method = s.cogs_method and v.fold_origin = s.fold_origin
where v.value is null or not coalesce(abs(v.value - s.score) <= 1e-6 * (abs(s.score) + 1), false)
union all
select 'rpt_forecast_backtest: khoa (model, cogs_method, fold_origin, metric, grain) khong trung', count(*)
from (
    select model, cogs_method, fold_origin, metric, grain, count(*) as k
    from b group by model, cogs_method, fold_origin, metric, grain
) t
where k > 1
union all
select 'moi ung vien va moc co du chi so chat doc o 3 fold', count(*)
from (
    select c.model, c.cogs_method, m.metric, count(distinct b.fold_origin) as k
    from (select distinct model, cogs_method from d) c
    cross join need_metric m
    left join b on b.model = c.model and b.cogs_method = c.cogs_method and b.metric = m.metric and b.value is not null
    group by c.model, c.cogs_method, m.metric
) t
where k <> 3
union all
-- 5. COGS/G ngày nằm trong khoảng lịch sử nới 10% (không cấm > 1 ngoài Urban Blowout: lịch sử có, notebook §8)
select 'COGS/G du bao trong khoang COGS/G ngay lich su noi 10%', count(*)
from d cross join actual a
where d.cogs_yhat / d.yhat < a.ratio_lo * 0.9 or d.cogs_yhat / d.yhat > a.ratio_hi * 1.1
union all
-- 6. Tháng 8/2023 (năm lẻ, Urban Blowout) của ứng viên chính: G sụt so với tháng 8/2022, COGS > G
select 'thang 8/2023 cua ung vien chinh: G thap hon thang 8/2022 thuc te, COGS/G > 1', count(*)
from (
    select sum(yhat) as g, sum(cogs_yhat) as c
    from d
    where is_primary and extract(year from forecast_date) = 2023 and extract(month from forecast_date) = 8
) t cross join actual a
where t.g is null or not (t.g < a.g_aug_2022 and t.c > t.g)
) checks
where n > 0
