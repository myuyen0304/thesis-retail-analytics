-- PS3 (deck slide 8 yêu cầu 2): nhịp theo tháng của từng giai đoạn PS2. 1 dòng = 1 giai đoạn × 1 tháng (4 × 12).
-- Quy ước năm ranh giới để SO SÁNH (không đếm trùng): năm Y tính cho giai đoạn có start_year < Y <= end_year, tức giai đoạn
-- KẾT THÚC ở năm đó (2016 → A, 2018 → B, 2019 → C); năm đầu của giai đoạn đầu tiên (2013) tính cho giai đoạn đó.
-- Đây là quy ước RIÊNG của PS3 (gom theo năm lịch), chưa được BA chốt. Nền màu trang PS2 là mốc trên đường R 12 tháng
-- (điểm 12/Y dùng chung cho hai giai đoạn kề nhau), không phải cách chia năm này.
-- (Nhãn 'A/B' ở rpt_revenue_yearly.ps2_phase_codes là THÀNH VIÊN theo seed, khác quy ước này.)
-- Chỉ số tháng của giai đoạn tính lại từ tử và mẫu (docs/dwh_huong_dan_pm_ba.md §5 quy tắc 1), không lấy TB chỉ số các năm:
--   month_index = Σ R tháng m các năm trong giai đoạn ÷ (Σ R cả giai đoạn ÷ 12).
with first_phase as (
    select min(start_year) as y from {{ ref('ps2_phases') }}
),
yp as (
    select y.year, p.phase_code, p.phase_name, p.start_year
    from (select distinct year from {{ ref('rpt_revenue_monthly') }} where is_analysis_period) y
    cross join first_phase f
    join {{ ref('ps2_phases') }} p
      on (y.year > p.start_year and y.year <= p.end_year)
      or (y.year = p.start_year and p.start_year = f.y)
),
pm as (
    select yp.phase_code, yp.phase_name, m.month,
           min(yp.year) as first_year, max(yp.year) as last_year, count(*) as n_years,
           sum(m.r) as r
    from yp
    join {{ ref('rpt_revenue_monthly') }} m on m.year = yp.year
    group by yp.phase_code, yp.phase_name, m.month
)
select
    phase_code, phase_name, first_year, last_year, n_years, month, r,
    {{ ratio('r', 'sum(r) over (partition by phase_code) / 12') }} as month_index
from pm
