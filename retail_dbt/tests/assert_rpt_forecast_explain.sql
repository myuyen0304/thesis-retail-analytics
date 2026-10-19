-- B4a: bản chỉ qua gate nếu từng ngày phân rã cộng được trên thang log và khớp ứng viên chính.
-- Bật/tắt trong tests/_singular_tests.yml cùng forecast_path.
with e as (select * from {{ ref('rpt_forecast_explain') }}),
d as (select * from {{ ref('rpt_forecast_daily') }} where is_primary),
g as (
    select forecast_date, count(*) as n, count(distinct feature_group) as group_count,
           min(expected_groups) as expected_lo, max(expected_groups) as expected_hi,
           min(base_log) as base_lo, max(base_log) as base_hi,
           min(forecast_log) as forecast_lo, max(forecast_log) as forecast_hi,
           sum(contribution_log) as total_log
    from e group by forecast_date
),
bad as (
    select 'ngoai_ung_vien_chinh_hoac_sai_metadata' as rule, count(*) as n
    from e left join d on e.forecast_date = d.forecast_date
    where d.forecast_date is null or e.model <> d.model or e.cogs_method <> d.cogs_method
       or e.model_version <> d.model_version or e.run_id <> d.run_id
       or e.trained_through <> d.trained_through
    union all
    select 'thieu_ngay_hoac_nhom', count(*)
    from d left join g on d.forecast_date = g.forecast_date
    where (d.model = 'lgbm_full' and (g.n is null or g.n <> g.group_count or g.group_count < 5
          or g.group_count <> g.expected_lo or g.expected_lo <> g.expected_hi))
       or (d.model <> 'lgbm_full' and g.n is not null)
    union all
    select 'thieu_nhom_bat_buoc', count(*)
    from g where exists (select 1 from d where model = 'lgbm_full')
      and (not exists (select 1 from e x where x.forecast_date = g.forecast_date and x.feature_group = 'mua_vu')
        or not exists (select 1 from e x where x.forecast_date = g.forecast_date and x.feature_group = 'dau_cuoi_thang')
        or not exists (select 1 from e x where x.forecast_date = g.forecast_date and x.feature_group = 'che_do_sau_2018')
        or not exists (select 1 from e x where x.forecast_date = g.forecast_date and x.feature_group = 'nam_chan_le')
        or not exists (select 1 from e x where x.forecast_date = g.forecast_date and x.feature_group like 'promo_%'))
    union all
    select 'log_khong_cong_ve_du_bao', count(*)
    from g join d on g.forecast_date = d.forecast_date
    where not coalesce(abs(g.base_lo - g.base_hi) <= 1e-10
                   and abs(g.forecast_lo - g.forecast_hi) <= 1e-10
                   and abs(g.base_lo + g.total_log - ln(d.yhat)) <= 1e-7
                   and abs(g.forecast_lo - ln(d.yhat)) <= 1e-7, false)
    union all
    select 'dong_gop_hoac_he_so_khong_hop_le', count(*)
    from e
    where not coalesce(e.base_log between -100 and 100 and e.contribution_log between -100 and 100
                   and e.forecast_log between -100 and 100
                   and e.multiplier > 0 and abs(e.multiplier - exp(e.contribution_log)) <= 1e-8, false)
)
select * from bad where n > 0
