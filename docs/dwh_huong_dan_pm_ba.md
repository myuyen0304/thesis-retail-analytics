# Hướng dẫn Data Warehouse cho PM / BA

Tài liệu này dành cho **PM và BA/DA**. Mục đích là để PM/BA nắm được DWH lấy dữ liệu từ đâu, biến đổi ra sao, trả lời
câu hỏi business nào, và **tự kiểm** được con số mà không cần đọc code.
Chi tiết kỹ thuật (công cụ, lệnh, các giai đoạn) nằm ở `dwh_roadmap.md`; thiết kế bảng nằm ở `star_schema.md`.

Cập nhật lần cuối: 2026-10-05 (§1–§8 rà lại theo nhật ký tới mục 2026-10-05). Mỗi lần dev bàn giao một chức năng mới, dev ghi thêm vào **§9 Nhật ký bàn giao**.

---

## 1. DWH này để làm gì

DWH ưu tiên **PS1–PS5 và sản phẩm phân tích bằng code**. Dự báo là hướng mở rộng riêng, không là bước bắt buộc:

| Mục đích | Người dùng | Doanh thu dùng | Bảng |
|---|---|---|---|
| Trả lời **5 problem statement** trong deck `docs/presentations/revenue_performance_problem_statement_updated.pptx` | PM, BA, app code / BI | **R**: tiền thực nhận | schema `reporting` |
| Mở rộng dự báo nếu chọn sau này | nhóm model | **G** của phần actual; mẫu submission không phải forecast thật | `marts.fact_daily_sales` |

> **Quy tắc số 1:** trên dashboard và trong báo cáo PS, "doanh thu" luôn là **R**.
> **G** dùng đối chiếu PS1; từng là target của bài Datathon. Chưa coi mẫu non-actual là kết quả model.

---

## 2. Hai định nghĩa doanh thu: R và G

Theo slide 3 của deck:

- **G (Gross)** = Σ số lượng × đơn giá của **mọi đơn**, kể cả đơn hủy, đơn trả, đơn chưa giao, và **chưa trừ chiết khấu**. G trùng khớp `sales.csv`.
- **R (Revenue, tiền thực nhận)** = Σ (số lượng × đơn giá − chiết khấu), **chỉ tính đơn đã giao** (`delivered`).

Từ G xuống R, gộp 2012–2022 (số lấy từ `reporting.rpt_revenue_yearly`):

```text
G  16,430 tỷ   (sales.csv)
 − 1,516 tỷ    tiền hàng của đơn bị hủy (cancelled)
 − 0,908 tỷ    tiền hàng của đơn bị trả (returned)
 − 0,890 tỷ    tiền hàng của đơn chưa giao xong (created / paid / shipped)
 − 0,599 tỷ    chiết khấu trên đơn đã giao
= R 12,518 tỷ  → R/G = 76,2%
```

Mấy điểm BA hay hỏi:

- **Đơn trả bị loại hẳn khỏi R**, nên không trừ tiền hoàn thêm lần nữa. Tiền hoàn chỉ nằm ở đơn `returned`; đã có test chứng minh (§6).
- **R khớp 100% số tiền khách thanh toán** (`payments.csv`) của đơn đã giao, trên 516.716/516.716 đơn.
- Mọi con số đều **gom theo ngày đặt hàng**, không theo ngày giao.
- **Đơn vị tiền là VND** (PM chốt ngày 2026-10-05). Dữ liệu nguồn không ghi đơn vị; đây là quy ước của PM. Số trong kho là
  đồng, ví dụ R 2019 = 864.329.801,94 VND, tức khoảng 864,3 triệu đồng.

---

## 3. Flow dữ liệu: DWH nằm ở đâu

### 3.1. Đối chiếu với pipeline của giảng viên

Pipeline giảng viên vẽ là **Raw → Silver → Data Warehouse → Phân tích / BI → Sản phẩm (có AI Explained)**.
Trong project, mỗi khối ứng với các phần sau:

```text
 PIPELINE GIẢNG VIÊN        TRONG PROJECT                                   AI DÙNG
 ───────────────────        ─────────────────────────────────────────────   ──────────────
 ① Raw                      14 file CSV (data/)
                               │ scripts/ingest/ingest_raw.py (Python)
                               ▼
                         ┌──────────────── DATA WAREHOUSE (database `retail`, PostgreSQL) ────────────────┐
                         │  schema raw            bản sao nguyên văn 14 CSV                                  │
                         │     │ dbt                                                                        │
 ② Silver  (làm sạch)    │  schema staging        ép kiểu, cắt khoảng trắng                                  │
           (chuẩn hóa)   │  schema intermediate   gắn số dòng hàng, nối trả hàng / review vào dòng hàng       │
                         │     │                                                                            │
 ③ DWH  (lõi)            │  schema marts          STAR SCHEMA 14 bảng: 6 dim + 7 fact + 1 bridge
                         │     │                                                                            │
 ③' DWH (lớp phục vụ)    │  schema reporting      KPI của 5 PS, tính sẵn theo quy ước R                 ◀── PM / BA
                         └─────┼──────────────────────────────────────────────────────────────────────────┘
                               │ cùng project dbt dựng được trên: DuckDB (file), Databricks Free (lab), Snowflake (demo)
                               ▼
 ④ Phân tích / BI           app code / BI (GĐ 2)                             PM, BA, giảng viên
 ⑤ Sản phẩm + AI Explained  phân tích PS1–PS5; AI giải thích có đối chứng nếu triển khai
```

**Nói gọn:** DWH là **một database** (`retail`), chạy chính trên PostgreSQL local. Cùng một project dbt dựng được:

- bản DuckDB (file `warehouse/dbt.duckdb`), dùng dự phòng khi không bật Docker;
- bản **Databricks Free** (catalog `retail_lab`), là lab trên cloud. Bản này đã dựng, khớp local từng dòng, app đọc được
  (nhật ký §9, mục 2026-10-03 và 2026-10-04);
- bản **Snowflake**, là đích demo tháng 12/2026 (GĐ 3). Script đã có nhưng chưa chạy trên cloud (mục 2026-10-02).

Kafka làm sau pipeline chính (GĐ 4).
Bên trong database có 5 "ngăn" (schema). **Lõi của DWH là schema `marts`**, và **PM/BA đọc schema `reporting`**.

### 3.2. Lõi DWH (`marts`) gồm những gì

Lõi DWH thiết kế theo **star schema**: mỗi bảng *fact* (sự kiện, có số đo) nằm ở giữa, các bảng *dim* (chiều để
lọc / nhóm) bao quanh. Thiết kế được dẫn từ 5 PS theo thứ tự PS → KPI → grain → fact → dimension trong
`star_schema_tu_ps.md` (truy vết PS; bus matrix nghiệp vụ và hợp đồng dimension dùng chung ở `star_schema.md` §5). Bằng chứng dữ liệu: `star_schema.md`,
sơ đồ: `docs/design/star_schema.mmd`.

| Loại | Bảng | Một dòng là | Dùng cho |
|---|---|---|---|
| fact | `fact_order_item` | 1 dòng hàng trong đơn | **nguồn chính của R, G, N, Q, C** (mọi PS) |
| fact | `fact_order` | 1 đơn hàng | trạng thái đơn, tiền thanh toán, ngày gửi / giao |
| fact | `fact_daily_sales` | 1 ngày | **G** tham chiếu; non-actual lấy từ mẫu, không phải forecast đã huấn luyện |
| fact | `fact_return`, `fact_review`, `fact_inventory_snapshot`, `fact_web_traffic` | 1 lần trả / đánh giá / mốc tồn kho / ngày traffic | ngoài phạm vi 5 PS, giữ để mở rộng |
| bridge | `bridge_item_promo` | 1 cặp dòng hàng × khuyến mãi | ngoài phạm vi 5 PS |
| dim | `dim_date` | 1 ngày (2012 → 07/2024) | năm, tháng, ngày trong tháng, số ngày trong tháng, cờ Urban Blowout |
| dim | `dim_product` | 1 sản phẩm | **category** (PS5) |
| dim | `dim_customer` → `dim_geography` | 1 khách → 1 mã vùng | **acquisition_channel**, **region** (PS5) |
| dim | `dim_order_junk` | 1 tổ hợp trạng thái | **order_status**: lọc đơn `delivered` để ra R |
| dim | `dim_promotion` | 1 chương trình khuyến mãi | ngoài phạm vi 5 PS |

### 3.3. Vì sao cần thêm lớp `reporting` phía trên lõi DWH

- **marts** bám theo **cấu trúc dữ liệu** và dùng chung cho mọi mục đích. Muốn ra R phải tự join 3–5 bảng rồi lọc
  `delivered`, nên dashboard rất dễ tính sai.
- **reporting** bám theo **câu hỏi business**. Mọi quy ước của deck (chỉ lấy đơn delivered, trừ chiết khấu,
  năm phân tích 2013–2022, YoY từ 2014…) đã được xử lý sẵn. PM/BA **chỉ cần đọc lớp này**; khi cần xem tới từng đơn
  thì mới xuống `marts`.
- Kho có **158 test** (số từ M5, 2026-09-29; `dbt build` ra `PASS=216`). Test FAIL báo build không đạt, nhưng **không tự
  rollback mọi bảng đã dựng**.
  Production cần quality gate và publish nguyên version sau khi đạt; không cho app đọc bảng đang build dở.

### 3.4. Thư mục `silver/` (19 file CSV) liên quan gì tới DWH

`silver/` do `scripts/build/build_silver.py` sinh ra. Đây là bản **chuẩn hóa 3NF (19 bảng)** dùng cho phần phân tích và
thiết kế (deck PS ghi nguồn là "bảng Silver"; xem `normalized_schema.md`). DWH **không đọc** thư mục này: DWH dựng lại
tầng Silver của riêng nó (`staging` + `intermediate`) từ 14 CSV gốc, để cả pipeline chạy tự động trong một lệnh.
Hai bản cho cùng kết quả: số dòng hàng (`line_number`) trong DWH khớp với `silver/order_item.csv` (phụ lục lịch sử `star_schema_snapshot_reference.md` §10),
và R, G, N trong DWH khớp các số ghi trên deck (test `assert_rpt_deck_numbers`).

---

## 4. Câu hỏi nào lấy ở bảng nào

Ký hiệu theo slide 3 của deck: N = số đơn đã giao, Q = tổng số món, U = Q/N, P = R/Q, C = số khách có đơn đã giao,
F = N/C, AOV = R/N.

### Bảng trong schema `reporting`

| Bảng | Mỗi dòng là | Trả lời |
|---|---|---|
| `rpt_revenue_total` | 1 kỳ gộp nhiều năm (2 dòng: 2012–2022 và 2013–2022) | PS1: thẻ G, R, R/G cả kỳ (trang Tổng quan, PS1). N, C đếm lại trên cả kỳ, không cộng từ năm |
| `rpt_revenue_bridge` | 1 cột của thác G → R × 1 kỳ (2 kỳ gộp + từng năm) | PS1: thác G → hủy → trả → chưa giao → chiết khấu → R |
| `rpt_build_info` | 1 dòng | Dòng thông tin chung đầu mọi trang: lúc `dbt build` (dòng **Refresh**), ngày đầu/cuối dữ liệu, kỳ phân tích |
| `rpt_revenue_monthly` | 1 tháng (07/2012 → 12/2022, 126 dòng) | PS1, PS2, PS3 |
| `rpt_revenue_yearly` | 1 năm (2012 → 2022, 11 dòng) | PS1, PS2, PS4, phần C/F của PS5 |
| `rpt_revenue_segment_yearly` | 1 nhóm × 1 năm, theo từng chiều | PS5 |
| `rpt_driver_period` | 1 năm (2014–2022) hoặc 1 giai đoạn PS2 (13 dòng) | PS4: phần góp N, U, P và % đổi của chính R, N, U, P; PS5: phần góp C, F (thêm ở M4, 2026-09-29) |
| `rpt_driver_bridge` | 1 cột của biểu đồ thác × 1 kỳ | PS4: thác R đầu → N → U → P → R cuối; PS5: thác N đầu → C → F → N cuối |
| `rpt_august_parity` | 1 dòng | PS3: tháng 8 năm lẻ so với năm chẵn |
| `rpt_calendar_phase_month` | 1 giai đoạn × 1 tháng (4 × 12) | PS3: chỉ số tháng gộp của từng giai đoạn PS2 (thêm 2026-09-28) |
| `rpt_calendar_phase` | 1 giai đoạn (4 dòng) | PS3: so sánh 3 nhịp giữa các giai đoạn |
| `rpt_calendar_stability` | 1 nhịp (3 dòng) | PS3: độ ổn định, bỏ từng năm + số năm tự có nhịp |
| `rpt_revenue_phase` | 1 giai đoạn (4 dòng, A–D) | PS2: R đầu/cuối, tổng thay đổi, CAGR |
| `rpt_revenue_turning_point` | 1 ranh giới giữa hai giai đoạn (3 dòng) | PS2: độ lớn cú đổi hướng |
| `rpt_revenue_direction` | 1 tháng × 1 khoảng so (3, 6, 9 tháng) | PS2: đường R 12 tháng đang lên hay xuống (thêm 2026-09-28) |
| `rpt_revenue_direction_change` | 1 lần đổi hướng × 1 khoảng so (6 dòng) | PS2: dữ liệu tự tìm tháng đổi hướng, hướng mới giữ bao lâu |
| `rpt_health_summary`, `rpt_health_test`, `rpt_health_run`, `rpt_health_ingest` | 1 dòng trạng thái / 1 test / 1 lần chạy dbt / 1 file nguồn | Trang Sức khỏe dữ liệu: số có đáng tin không (thêm ở M5, 2026-09-29). Là view trên nhật ký chạy dbt (schema `ops`) và log nạp nguồn, không phải số doanh thu |

### Map từng PS sang cột

| PS | Câu hỏi | Bảng | Cột |
|---|---|---|---|
| **PS1** | Mỗi tháng, mỗi năm công ty thực nhận bao nhiêu? | monthly, yearly | `r`, `g`, `capture_rate` (R/G), `cancelled_gross`, `returned_gross`, `undelivered_gross`, `delivered_discount`, `cancelled_rate`, `cancelled_rate_change` |
| **PS2** | Doanh thu tăng hay giảm, giai đoạn nào đổi hướng? | yearly | `yoy_rate` (từ 2014), `r_prior_year` |
| | | monthly | `yoy_rate` (cùng kỳ, từ 08/2013), `r_12m` (R của 12 tháng gần nhất, từ 07/2013) |
| | Giai đoạn và điểm đổi hướng | phase | `phase_code`, `phase_name`, `start_year`, `end_year`, `r_start`, `r_end`, `total_change_rate`, `cagr` |
| | | turning_point | `turning_year`, `from_phase_code` → `to_phase_code`, `r_12m_before`, `r_12m_after`, `delta_r`, `magnitude`, `turn_note`, `data_extreme_month_date`, `data_change_month_date` |
| | Tháng đổi hướng do dữ liệu tự tìm | direction_change | `window_months`, `change_month_date` (tháng phát hiện), `direction_before` → `direction_after`, `extreme_month_date` (đỉnh/đáy), `months_held`, `held_to_end_of_data` |
| **PS3** | Doanh thu dồn vào tháng nào, ngày nào, có lặp lại không? | monthly | `month_index` (1 = tháng bình thường), `eom_share` (tỷ trọng R từ ngày 26 trở đi), `eom_expected_share` = (D−25)/D, `eom_excess` (> 0 là dồn về cuối tháng), `days_in_month` |
| | | yearly | `season_peak_trough_ratio` (chỉ số tháng cao nhất ÷ thấp nhất); `eom_share`, `eom_expected_share`, `eom_excess` của cả năm (thêm ở M3); `ps2_phase_codes` (giai đoạn PS2 của năm, năm ranh giới 'A/B') |
| | | total | `eom_share`, `eom_expected_share`, `eom_excess` của cả kỳ (thêm ở M3) |
| | | august_parity | `august_odd_vs_even`; `max_index_odd` < `min_index_even` (mọi năm lẻ thấp hơn mọi năm chẵn); `loo_min_odd_vs_even` … `loo_max_odd_vs_even` (bỏ lần lượt từng năm, thêm ở M3) |
| | So sánh giai đoạn, độ ổn định | calendar_phase, calendar_stability | `peak_month`, `trough_month`, `season_peak_trough_ratio`, `eom_excess`, `august_odd_vs_even` theo giai đoạn; `metric_value`, `loo_min` … `loo_max`, `n_years_with_pattern` theo nhịp |
| **PS4** | Đổi vì số đơn, số món mỗi đơn, hay giá mỗi món? | yearly | `n`, `u`, `p`, `aov`, `yoy_n`, `yoy_u`, `yoy_p`, `delta_r` = `contrib_n` + `contrib_u` + `contrib_p` |
| | Theo năm và theo giai đoạn PS2 | driver_period, driver_bridge | `period_type` (year / phase), `delta_r`, `contrib_n`, `contrib_u`, `contrib_p`, `top_up_driver`, `top_down_driver` (phần kéo lên / kéo xuống nhiều nhất), `delta_r_is_small` (mức đổi R dưới ngưỡng seed `driver_rule`); thác: `bar_start` → `bar_end` (thêm ở M4) |
| **PS5** | Ngành hàng, khu vực, kênh nào kéo doanh thu? | segment_yearly | `dimension_name` (category / region / acquisition_channel), `dimension_value`, `r`, `share`, `delta_r`, `yoy_rate`, `share_shift_pp` (điểm %), `contribution_to_delta`, `delta_r_rank` (1 = tăng nhiều nhất), `delta_r_is_small`, `n_groups`, `n_groups_up`, `n_groups_down` (thêm ở M4) |
| | Mất khách hay khách mua thưa đi? | yearly, driver_period | `c`, `f`, `delta_n` = `contrib_c` + `contrib_f` |

### Ví dụ đọc số: vì sao năm 2019 doanh thu rơi?

Lấy từ `rpt_revenue_yearly` và `rpt_revenue_segment_yearly`, năm 2019:

- R giảm **39,1%**, từ 1.419,3 xuống 864,3 triệu.
- **PS4**: gần như toàn bộ phần giảm do **số đơn** (`contrib_n` = −572,4 triệu). Số món mỗi đơn (+2,6) và
  giá mỗi món (+14,9) gần như không đổi.
- **PS5, C/F**: số đơn giảm 22.481 đơn. Trong đó 16.578 đơn được phân bổ cho **ít khách có đơn delivered trong kỳ hơn** (`contrib_c`), 5.903 đơn cho
  **tần suất bình quân thấp hơn** (`contrib_f`). Chưa đủ bằng chứng kết luận churn.
- **PS5, theo nhóm**: Streetwear chiếm 83,6% mức giảm, nhưng tỷ trọng của nó chỉ giảm 1,03 điểm %.
  Tức là ngành nào cũng giảm, không phải một ngành kéo sụt cả công ty.

> Đây là **phân rã số học, không phải nguyên nhân** (slide 10). Thứ tự tách N → U → P ảnh hưởng tới kết quả;
> DWH tách đúng thứ tự ghi trong deck.

### PS2: 4 giai đoạn doanh thu (PM/BA chốt ngày 2026-09-27)

**Quyết định:** chia 10 năm đủ 2013–2022 thành 4 giai đoạn, dựa trên R theo năm và đường R 12 tháng (`r_12m`).

| Giai đoạn | Năm đầu → năm cuối | Xu hướng | R đầu → R cuối (triệu) | CAGR | Tổng thay đổi |
|---|---|---|---|---:|---:|
| **A. Tăng trưởng** | 2013 → 2016 | tăng | 1.259,2 → 1.619,5 | **+8,75%/năm** | +28,6% |
| **B. Chững, giảm nhẹ** | 2016 → 2018 | giảm | 1.619,5 → 1.419,3 | **−6,39%/năm** | −12,4% |
| **C. Sập** | 2018 → 2019 | giảm mạnh | 1.419,3 → 864,3 | **−39,10%** | −39,1% |
| **D. Đi ngang mức thấp** | 2019 → 2022 | ngang | 864,3 → 860,6 | **−0,14%/năm** | −0,4% |
| *(đối chiếu) Cả kỳ* | 2013 → 2022 | | 1.259,2 → 860,6 | −4,14%/năm | −31,7% |

**Ba điểm đổi hướng** (ban đầu chốt 2 điểm, BA bổ sung điểm cuối 2019 trong cùng ngày):

| Điểm | Đổi từ → sang | Độ lớn cú đổi hướng |
|---|---|---:|
| Cuối 2016 | tăng → giảm (2016 là đỉnh R) | R 2017 / R 2016 − 1 = **−9,7%** |
| Cuối 2018 | giảm nhẹ → sập (giảm tăng tốc) | R 2019 / R 2018 − 1 = **−39,1%** (−554,9 triệu) |
| Cuối 2019 | sập → đi ngang (đổi nhịp) | R 2020 / R 2019 − 1 = **−6,7%** (−57,9 triệu) |

**Quy tắc nghiệp vụ (áp dụng cho mọi báo cáo PS2):**

1. **Mốc giai đoạn là năm đủ**, tính bằng R cả năm (chỉ đơn delivered, theo `order_date`). Không dùng 2012 vì năm đó chỉ có nửa năm.
2. **Hai giai đoạn liền nhau dùng chung năm ranh giới.** Ví dụ 2016 vừa là năm cuối của A, vừa là năm đầu của B. Đây là cách tính CAGR thông thường: tốc độ đi từ mốc này sang mốc kia.
3. **CAGR** = (R năm cuối ÷ R năm đầu)^(1/n) − 1, với n = năm cuối − năm đầu (slide 7).
   Giai đoạn C chỉ dài 1 năm, nên CAGR của C trùng với YoY 2019.
4. **Độ lớn cú đổi hướng** = R 12 tháng sau điểm ÷ R 12 tháng trước điểm − 1 (slide 7). Vì điểm đổi hướng đặt ở ranh giới năm,
   12 tháng trước là cả năm trước điểm, 12 tháng sau là cả năm sau điểm. Muốn xem điểm gãy chính xác tới tháng thì đọc `r_12m`:
   chỉ số này rơi từ 1.419,3 triệu (12/2018) xuống 1.082,9 triệu (06/2019), tức cú sập diễn ra ngay trong nửa đầu 2019.
5. **2022 hồi phục +12,3% chưa tách thành giai đoạn mới**, vì mới có 1 năm dữ liệu. Khi báo cáo, ghi là "tín hiệu hồi phục cuối
   giai đoạn D", không gọi là xu hướng tăng. Cần thêm dữ liệu 2023 mới kết luận được.
6. **Không trình bày một con số tăng trưởng cho cả 10 năm** (−4,14%/năm) như thể đó là xu hướng. Con số này trộn 4 chế độ khác nhau,
   giống lỗi của `baseline.ipynb` (CLAUDE.md §6).
7. Giai đoạn chỉ **mô tả** doanh thu đi lên hay xuống. Muốn biết **vì sao** thì xem PS4 (N/U/P) và PS5 (nhóm, C/F) theo từng giai đoạn.
   Giai đoạn không phải bằng chứng về nguyên nhân.

**Trạng thái:** đã có trong DWH:

- `reporting.rpt_revenue_phase`: 4 giai đoạn;
- `reporting.rpt_revenue_turning_point`: các ranh giới giữa hai giai đoạn.

Mốc giai đoạn nằm ở seed `retail_dbt/seeds/ps2_phases.csv`. **Muốn đổi mốc thì chỉ sửa file này**, rồi sửa các số khóa trong test `assert_rpt_phase`.
Cột `end_turn_note` của seed là ghi chú BA cho điểm đổi hướng ở cuối giai đoạn: dòng B "giảm tăng tốc" (PM chốt 2026-09-28),
dòng C "đổi nhịp"; app hiện nguyên chữ này.
Test khóa mọi số trong bảng trên, gồm cả −6,7% và hai ghi chú của cuối 2018, cuối 2019.

**Dữ liệu tự tìm tháng đổi hướng (bổ sung 2026-09-28, deck slide 6 yêu cầu 4).** Mốc ở trên là quyết định của BA. Để có bằng
chứng từ dữ liệu, dbt tìm tháng đường R 12 tháng đổi hướng theo ghi chú slide 7: so R 12 tháng với chính nó k tháng trước
(k = 3, 6, 9; 6 là khoảng so chính), hướng mới phải giữ ≥ 6 tháng liền. Quy tắc nằm ở seed `ps2_direction_rule`.

| Khoảng so | Lên → xuống | Xuống → lên |
|---|---|---|
| 3 tháng | đỉnh 08/2016, phát hiện 11/2016, giữ 61 tháng | đáy 10/2021, phát hiện 12/2021, giữ 13 tháng tới hết dữ liệu |
| **6 tháng (chính)** | đỉnh 08/2016, phát hiện 02/2017, giữ 60 tháng | đáy 10/2021, phát hiện 02/2022, giữ 11 tháng tới hết dữ liệu |
| 9 tháng | đỉnh 08/2016, phát hiện 05/2017, giữ 60 tháng | đáy 10/2021, phát hiện 05/2022, giữ 8 tháng tới hết dữ liệu |

- Mốc **cuối 2016** được dữ liệu xác nhận: đỉnh 08/2016 ở cả ba khoảng so.
- Mốc **cuối 2018, cuối 2019** là đổi **tốc độ**, hai phía cùng hướng xuống, nên cách này không tìm ra. Đây là nhận định của BA
  (ghi chú "giảm tăng tốc", "đổi nhịp").
- Đáy 10/2021 rồi đi lên tới hết dữ liệu: khớp quy tắc 5 ("tín hiệu hồi phục", chưa đủ thành giai đoạn mới).
- Test `assert_rpt_direction` khóa các số trên. Đây là tiêu chí thăm dò, không khẳng định mọi điểm gãy (ghi chú slide 7). Câu SQL ở §7 vẫn chạy được để đối chiếu tay.

> **BA đã xác nhận ngày 2026-09-27: giữ 3 điểm đổi hướng.** Mỗi ranh giới giữa hai giai đoạn là một điểm:
>
> - cuối 2016 (A → B, −9,7%);
> - cuối 2018 (B → C, −39,1%);
> - cuối 2019 (C → D, −6,7%).
>
> Điểm cuối 2019 đánh dấu cú sập dừng lại, chuyển sang đi ngang. Hướng vẫn là giảm nhưng chậm hẳn lại, nên khi trình bày gọi là
> "đổi nhịp", không gọi là "đảo chiều".

---

## 5. Quy tắc dùng số (Power BI và Excel)

1. **Không cộng, không lấy trung bình các cột tỷ lệ**: `u`, `p`, `f`, `aov`, `capture_rate`, `month_index`, `share`, `yoy_*`.
   Muốn tính cho một kỳ gộp thì tính lại từ tử và mẫu, ví dụ AOV quý = Σ r ÷ Σ n khi các tháng không giao nhau.
   N không cộng tùy ý qua category vì một đơn có thể mua nhiều category.
2. **C (số khách) không cộng qua thời gian.** Một khách mua cả tháng 1 lẫn tháng 2 chỉ tính là 1 khách của năm.
   Cần C của năm thì lấy ở `rpt_revenue_yearly`, **không** cộng 12 tháng lại.
   (N, Q, R, G thì cộng qua thời gian được.)
3. **Không cộng ba chiều của PS5 với nhau.** category, region và channel là ba cách cắt **cùng một R**.
   Luôn lọc đúng một `dimension_name` trước khi cộng.
4. **2012 chỉ để tham khảo** (dữ liệu bắt đầu từ 04/07/2012). Phân tích chính dùng 2013–2022, lọc bằng cột
   `is_analysis_period = true`. YoY năm bắt đầu từ 2014.
5. Ô **trống (NULL)** là có chủ đích, **không phải lỗi**. Đó là chỗ không có kỳ so sánh hợp lệ: YoY trước 2014,
   `r_12m` trước 07/2013, `month_index` của 2012.
6. `contribution_to_delta` có thể **âm hoặc lớn hơn 100%**. Ví dụ: một nhóm tăng trong khi tổng giảm.

---

## 6. Làm sao biết số đúng

Kho có **158 test** (số từ M5, 2026-09-29), gồm 22 test nghiệp vụ tự viết và các test ràng buộc cột (khóa không trùng,
không rỗng, giá trị hợp lệ). Test FAIL làm kết quả build không đạt. Đây không phải cơ chế publish nguyên tử. Nhóm test theo câu hỏi PM/BA hay đặt:

| PM/BA muốn chắc rằng… | Test |
|---|---|
| Kho không làm mất hay nhân đôi dòng nào so với 14 file gốc | `assert_row_counts`, `assert_every_source_row_lands`, `assert_rpt_reconciles` |
| G của từng ngày bằng đúng `sales.csv` (3.833/3.833 ngày) | `assert_daily_sales_matches_source` |
| R của **từng tháng, từng năm** bằng tiền khách thật sự thanh toán (`payments.csv`) | `assert_rpt_reconciles` |
| N, C tính lại từ grain đơn ra cùng kết quả (kiểm nội bộ, không phải nguồn độc lập khỏi dòng hàng) | `assert_rpt_reconciles` |
| G − R đúng bằng hủy + trả + chưa giao + chiết khấu | `assert_rpt_reconciles` |
| Các phần N, U, P tách đúng công thức slide 11 và cộng lại đúng ΔR; C, F cộng lại đúng ΔN | `assert_rpt_decomposition_additive` |
| Ba chiều PS5 đều cộng về đúng R tổng, không thiếu nhóm nào | `assert_rpt_decomposition_additive` |
| R 12 tháng, YoY, chỉ số tháng, số ngày trong tháng (kể cả năm nhuận) đúng | `assert_rpt_calendar` |
| Các con số ghi trên deck vẫn đúng | `assert_rpt_deck_numbers` |
| 4 giai đoạn PS2 liền mạch 2013–2022, CAGR và độ lớn đổi hướng đúng định nghĩa, đúng số đã chốt | `assert_rpt_phase` |
| Thẻ cả kỳ PS1 đúng số deck slide 4, thác G → R cộng đúng, dòng thông tin chung đúng | `assert_rpt_total` |
| Tháng đường R 12 tháng đổi hướng (dữ liệu tự tìm) đúng quy tắc seed và đúng số đã khóa | `assert_rpt_direction` |
| PS3 theo giai đoạn: mỗi năm thuộc đúng một giai đoạn, chỉ số tháng và độ ổn định tính đúng | `assert_rpt_calendar_phase` |
| PS4/PS5 theo năm và giai đoạn: phần góp N, U, P, C, F khớp bảng năm, thác cộng đúng, cờ "R đổi rất nhỏ" đúng ngưỡng | `assert_rpt_driver` |
| Trang Sức khỏe dữ liệu đếm đúng số test đạt/không đạt và đọc đúng nhật ký nạp nguồn | `assert_rpt_health` |

**Xem kết quả test trên app:** trang **Sức khỏe dữ liệu** (thêm ở M5) hiện kết quả từng test của lần kiểm gần nhất,
kèm mô tả tiếng Việt cho các test nghiệp vụ ở bảng trên, và báo vàng nếu kho được dựng lại sau lần kiểm hoặc chỉ kiểm một phần.

**Test có bắt lỗi thật không?** Dev đã cố ý gài lỗi vào code rồi xem test có báo không (mutation test):

| Lỗi cố ý gài | Kết quả |
|---|---|
| Tính cả đơn `shipped` là đã giao | 2 test FAIL |
| Tách U trước N (sai thứ tự deck) | FAIL |
| CAGR dùng số mũ 1/(n+1) thay vì 1/n | `assert_rpt_phase` FAIL |
| Để hở một năm giữa giai đoạn A và B | `assert_rpt_phase` FAIL |
| Đổi ngưỡng "cuối tháng" từ ngày 26 thành ngày 25 | FAIL |
| Làm tròn tồn kho sai kiểu | FAIL đúng 977 dòng |

> **Khi deck đổi số hoặc đổi định nghĩa**, BA báo dev để dev sửa `assert_rpt_deck_numbers` **cùng lúc** với model.
> Nếu không, build sẽ FAIL, và đó là cơ chế có chủ đích để số trên deck và số trong kho không lệch nhau.

---

## 7. Tự kiểm số (BA/DA)

Mở DBeaver, pgAdmin hoặc Power BI và kết nối: server `localhost`, cổng `5433`, database `retail`, user/mật khẩu `retail`.
Máy cần đang chạy Docker và đã build, xem §8.

```sql
-- PS1: R, G, R/G theo năm
select year, r, g, capture_rate from reporting.rpt_revenue_yearly order by year;

-- PS2: tăng trưởng năm và R 12 tháng gần nhất
select month_start_date, r, r_12m, yoy_rate from reporting.rpt_revenue_monthly order by 1;

-- PS2: CAGR của 4 giai đoạn đã chốt (§4)
with giai_doan(ten, nam_dau, nam_cuoi) as (values
    ('A. Tăng trưởng', 2013, 2016), ('B. Chững, giảm nhẹ', 2016, 2018),
    ('C. Sập', 2018, 2019),         ('D. Đi ngang mức thấp', 2019, 2022))
select g.ten, g.nam_dau, g.nam_cuoi, d.r as r_dau, c.r as r_cuoi,
       power(c.r / d.r, 1.0 / (g.nam_cuoi - g.nam_dau)) - 1 as cagr
from giai_doan g
join reporting.rpt_revenue_yearly d on d.year = g.nam_dau
join reporting.rpt_revenue_yearly c on c.year = g.nam_cuoi
order by g.nam_dau;

-- PS3: chỉ số tháng của một năm, và tháng 8 năm lẻ / chẵn
select month, month_index, eom_share, eom_expected_share from reporting.rpt_revenue_monthly where year = 2022;
select * from reporting.rpt_august_parity;          -- august_odd_vs_even ≈ −0,377

-- PS4: tách ΔR
select year, delta_r, contrib_n, contrib_u, contrib_p from reporting.rpt_revenue_yearly where year >= 2014;

-- PS5: nhóm nào kéo xuống năm 2019
select dimension_value, r, delta_r, share_shift_pp, contribution_to_delta
from reporting.rpt_revenue_segment_yearly
where dimension_name = 'category' and year = 2019 order by delta_r;
```

---

## 8. Chạy lại toàn bộ kho (dev làm; PM/BA chỉ cần biết thứ tự)

Chạy từ thư mục gốc repo, cần có sẵn `data/` (tải theo `README.md`).

**PowerShell** (cửa sổ terminal thường của Windows):

```powershell
docker compose up -d                                                # bật PostgreSQL
$env:PYTHONUTF8 = '1'                                               # bắt buộc, xem lưu ý bên dưới
.venv\Scripts\python.exe scripts\ingest\ingest_raw.py                # nạp 14 CSV vào raw, khoảng 6 giây
.venv\Scripts\dbt.exe build --project-dir retail_dbt --profiles-dir retail_dbt   # dựng + 158 test, khoảng 90 giây
.venv\Scripts\python.exe scripts\ops\pg_ai_readonly_role.py          # cấp lại quyền đọc cho chat AI
```

**Git Bash:**

```bash
docker compose up -d
.venv/Scripts/python.exe scripts/ingest/ingest_raw.py
PYTHONUTF8=1 .venv/Scripts/dbt.exe build --project-dir retail_dbt --profiles-dir retail_dbt
.venv/Scripts/python.exe scripts/ops/pg_ai_readonly_role.py
```

- **Thiếu `PYTHONUTF8=1` thì dbt dừng ngay** với lỗi `'charmap' codec can't decode`. Lý do: file SQL có chú thích tiếng
  Việt (UTF-8), còn Windows mặc định đọc bằng bảng mã khác. Trong PowerShell, `$env:PYTHONUTF8 = '1'` chỉ có hiệu lực trong
  cửa sổ đang mở; mở cửa sổ mới thì gõ lại.
- **Sau mỗi lần dựng lại Postgres phải chạy `pg_ai_readonly_role.py`.** dbt dựng lại bảng nên mất quyền đọc đã cấp cho tài
  khoản chỉ đọc của chat AI. Không chạy thì trang **Hỏi dữ liệu (AI)** báo lỗi quyền (nhật ký 2026-10-04: 56 test chat lỗi
  cho tới khi chạy lại). Kiểm nhanh: thêm `--check`.
- Gặp lỗi **"deadlock detected"** thì chạy lại `dbt build` (nhật ký 2026-10-02: lỗi ngẫu nhiên khi hai bảng dựng song song).

Kết quả mong đợi là dòng cuối có `PASS=216 ... ERROR=0` (53 model + 3 seed + 158 test + 2 hook ghi nhật ký cho trang
Sức khỏe dữ liệu; số ngày 2026-09-29 sau M5. Sau M4 là 202, lúc GĐ1 xong là 155).

Lệnh trên dựng Postgres (target mặc định). Muốn dựng bản DuckDB (`warehouse/dbt.duckdb`) thì thêm `--target duckdb`.
Dựng trên Databricks: nhật ký §9, mục 2026-10-03. Dựng trên Snowflake: mục 2026-10-02.

### 8.1. Mở app phân tích (Streamlit)

Chạy từ thư mục gốc repo. App chỉ **đọc** kho, không dựng lại, nên kho phải được build trước (mục 8).

**PowerShell** (cửa sổ terminal thường của Windows):

```powershell
cd D:\retail-analytics
docker compose up -d                        # nếu Postgres chưa chạy
$env:RETAIL_BACKEND = "postgres"            # hoặc "duckdb" nếu không bật Docker, "databricks" để đọc lab cloud
.venv\Scripts\streamlit.exe run apps/retail_app/app.py --server.headless true --browser.gatherUsageStats false
```

**Git Bash:**

```bash
RETAIL_BACKEND=postgres .venv/Scripts/streamlit.exe run apps/retail_app/app.py --server.headless true --browser.gatherUsageStats false
```

Sau đó mở `http://localhost:8501`.

- `RETAIL_BACKEND` chỉ chọn nguồn **mặc định** lúc mở. Bỏ trống thì là `postgres`. Đổi được ở thanh bên của app, gồm
  3 nguồn: PostgreSQL (Docker), DuckDB (file, dự phòng), Databricks (cloud, lab).
- **Databricks** cần đã đăng nhập `databricks auth login --profile retail-dev` và có file `.env.databricks.local`. Mỗi bảng
  đọc mất khoảng 2,5 giây, nên trước khi demo mở qua mọi trang một lượt (app giữ số 10 phút). Chi tiết: nhật ký
  2026-10-04.
- Trang **Hỏi dữ liệu (AI)** cần file `.env.ai.local` ở thư mục gốc, ghi `RETAIL_AI_API_KEY='<khóa DeepSeek>'`. File này
  không commit, không gửi khóa vào chat. Trên Postgres cần đã chạy `pg_ai_readonly_role.py` (mục 8). Chi tiết: nhật ký
  2026-10-05 và [ai_explain_ai2.md](ai_explain_ai2.md).
- `--server.headless true` để Streamlit không hỏi email lúc chạy lần đầu và không tự mở trình duyệt.
  `--browser.gatherUsageStats false` để tắt gửi thống kê sử dụng về Streamlit. Bỏ hai tùy chọn này đi thì app vẫn chạy.
- Tắt app: bấm `Ctrl+C` trong cửa sổ đang chạy.
- **Sửa code trong `apps/retail_app/ui/`, `dwh/` hay `ai_explain/` thì phải tắt app rồi chạy lại.** Tải lại trang chưa đủ,
  vì app đang chạy có thể vẫn giữ bản cũ của module đã import (nhật ký 2026-10-02: app đang chạy vẫn dùng CSS cũ của
  `ui/common.py`, app mở mới thì hiện đúng). Sửa file trong `views/` thì tải lại trang là đủ.
- **Nên chạy app ở cửa sổ terminal riêng**, không nhờ Claude Code chạy nền. Ngày 2026-09-29, lúc máy thiếu bộ nhớ, Claude Code đã
  tự tắt app đang chạy nền. App không lỗi.
- **Lúc demo trên DuckDB, không chạy `dbt build --target duckdb`** (nhật ký M0: dbt đang ghi thì app đọc lỗi "file đang bị dùng").
  Build xong thì bấm "Đọc lại dữ liệu" ở thanh bên.
- **Kiểm app tự động** (không cần mở trình duyệt):
  `PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest apps/retail_app -q -p no:cacheprovider`
  (PowerShell: `$env:PYTHONUTF8 = '1'; .venv\Scripts\python.exe -m pytest apps/retail_app -q -p no:cacheprovider`).
  Kết quả mong đợi: **`360 passed, 26 skipped`** (số ngày 2026-10-05, sau khi đổi VND; lúc máy chậm có test mở trang quá
  hạn 30 giây, chạy riêng lại test đó). 26 test bỏ qua là test cần Databricks, chỉ
  chạy khi đặt `$env:RETAIL_TEST_DATABRICKS = '1'`. Cần cả Postgres và `warehouse/dbt.duckdb` đã build **đầy đủ** (`dbt build`,
  không `-s`): test M5 kiểm nhật ký của chính lần build đó. Trên Postgres cần đã chạy `pg_ai_readonly_role.py`.
- **Trước khi demo, mở trang Sức khỏe dữ liệu** của backend sẽ dùng: phải thấy khung xanh "Kho đạt". Khung vàng/đỏ thì trang
  ghi lý do và lệnh cần chạy.

---

## 9. Nhật ký bàn giao (dev → PM/BA)

> **Về các dòng "Chưa commit" bên dưới:** đó là trạng thái lúc ghi mục. Ngày 2026-10-05, code của mọi mục tới AI2 đã vào
> hai commit trên nhánh `app/myuyen` (chưa push): `8a7da3e` (DWH dbt, app, AI0–AI1, backend Databricks) và `954d75f` (AI2).
> Thư mục `docs/` vẫn **chưa commit**, theo quyết định PM giữ ở máy. Sửa đổi sau hai commit này cũng chưa commit.

Mỗi chức năng mới ghi một mục: **làm gì, vì sao, trả lời PS nào, kiểm bằng gì, còn gì chưa làm.**

### 2026-09-26: DWH local (GĐ 1)
- **Làm:** PostgreSQL chạy bằng Docker, nạp 14 CSV, dựng star schema 14 bảng bằng dbt.
- **Kiểm:** `dbt build` 116/116 PASS (32 model + 84 test). Kết quả giống hệt nhau khi dựng bằng 3 cách (Postgres, DuckDB, script Python độc lập).

### 2026-09-26: Tầng reporting phục vụ 5 PS
- **Vì sao:** khi soát lại theo deck thì thấy marts đã đủ dữ liệu, nhưng PS nào cũng phải tự lọc đơn delivered,
  tự join nhiều bảng, dễ tính sai trên dashboard. Thêm nữa, tài liệu GĐ 3 cũ từng ghi doanh thu dashboard là G (sai với deck), đã sửa.
- **Làm:** 4 bảng/view `rpt_*` (§4) và 4 test `assert_rpt_*` (§6). Thêm `days_in_month` vào `dim_date` cho PS3.
- **Cách làm:** thiết kế được phản biện hai vòng với một AI khác (Codex): một vòng đề xuất, một vòng review code.
  Vòng review phát hiện test còn lỏng (NULL lọt qua, chỉ đối soát tổng toàn kỳ), đã sửa.
- **Kiểm:** 138/138 PASS trên Postgres và DuckDB; 3 mutation test đều FAIL đúng như mong đợi.
- **Chưa làm, cần PM/BA quyết:**
  1. **Mốc giai đoạn của PS2** (ví dụ 2013–2016 tăng, 2017–2018 chững, 2019 rơi, 2020–2022 đi ngang?).
     Dev không tự chọn mốc, vì đây là *kết quả phân tích* của BA. Khi BA chốt mốc, dev thêm bảng CAGR theo
     giai đoạn và bảng "cú đổi hướng" (slide 7).
  2. **Deck và file nguồn đang lệch nhau:** deck `_updated` dùng R, còn `docs/revenue_performance_problem_statement.md`
     và `scripts/docs_gen/build_ps_deck.py` vẫn là bản cũ dùng G. Cần chốt bản chuẩn.
  3. Các bảng **không phục vụ PS nào**: `fact_inventory_snapshot`, `fact_web_traffic`, `fact_review`,
     `dim_promotion`/`bridge_item_promo`, `fact_return`. Các bảng này thuộc thiết kế star schema nên vẫn giữ, nhưng
     nằm ngoài phạm vi 5 PS. Nếu mở rộng câu hỏi (tồn kho, traffic, đánh giá) thì dữ liệu đã có sẵn.

### 2026-09-27: Dọn cây thư mục theo chuẩn project data engineering

- **Vì sao:** thư mục gốc có hơn 20 file lẫn lộn (notebook, slide, sơ đồ, script), khó tìm và khó giải thích với giảng viên.
- **Làm:** thư mục gốc giờ chỉ còn file cấu hình. Cây thư mục mới có trong `README.md`, mục "Cây thư mục":
  - `notebooks/` chia theo 4 bước: khám phá → thiết kế → làm sạch → dự báo;
  - `scripts/` chia theo vai trò: ingest / build / verify / sinh tài liệu;
  - slide nằm ở `docs/presentations/`, sơ đồ ở `docs/design/`, tài liệu tham khảo ở `docs/references/`;
  - bản Databricks cũ chuyển vào `archive/`.
- **Không đổi:** nội dung notebook, `data/`, các file `.md` trong `docs/` (vẫn để phẳng), và mọi con số.
- **Kiểm:**
  - Mọi link / đường dẫn trong tài liệu đều đã sửa theo vị trí mới (có một script dò lại toàn bộ).
  - Cả 9 notebook đều đọc được `data/`.
  - Chạy lại toàn bộ: nạp dữ liệu 14/14; `dbt build` 138/138 PASS trên Postgres và DuckDB; sơ đồ sinh lại đúng chỗ mới.
  - Ba script chạy từ vị trí mới: `build_silver.py` 111 check PASS (19 bảng, 3.235.699 dòng); `build_gold.py` 53 check PASS; `verify_problem_to_kpi.py` 14/14 `[OK]`.
- **Sửa kèm:** trước đây, nạp lại dữ liệu sau khi đã build thì bị lỗi (Postgres chặn xóa bảng vì view của dbt đang phụ thuộc). Đã sửa.
- **PM/BA cần biết:**
  - Mở notebook bằng VS Code như bình thường.
  - Nếu dùng Jupyter Lab thì thêm `%cd ../..` ở cell đầu.
  - Deck PS giờ nằm ở `docs/presentations/`.

### 2026-09-27: Dẫn lại star schema từ 5 PS (top-down)

> Mục lịch sử này được cập nhật bởi mục bàn giao kế tiếp: giữ các fact ngoài PS cho nghiệp vụ khác,
> không còn chờ quyết định loại bỏ; forecast là extension, không là lộ trình chính.

- **Vì sao:** PM/BA chỉ ra rằng thiết kế cũ (`star_schema.md`) đi từ dữ liệu lên, trong khi flow đúng là
  PS → KPI → grain → fact → dimension.
- **Làm:** viết `star_schema_tu_ps.md`, dẫn lần lượt:
  - KPI của từng PS (slide 5–13);
  - 1 business process: bán hàng;
  - grain là dòng hàng, vì N và C không cộng được và PS5 cần category;
  - các measure;
  - 5 dimension và bus matrix.
  Bằng chứng dữ liệu cũ chuyển thành bước kiểm chứng (§7).
- **Kết quả:** flow top-down ra đúng lõi đang có (`fact_order_item` + 5 dim). Nhưng DWH hiện dựng rộng hơn yêu cầu:
  - 5 bảng ngoài phạm vi 5 PS;
  - 2 bảng chỉ dùng để đối soát;
  - `fact_daily_sales` phục vụ dự báo.
- **Không đổi:** chưa sửa model nào, mọi con số giữ nguyên.
- **Chờ PM/BA quyết:** xử lý 5 bảng ngoài phạm vi thế nào; mốc giai đoạn cho PS2.

### 2026-09-27: Chỉnh thiết kế theo PS và khả năng mở rộng

- **Làm:** chuẩn hóa [star_schema.md](star_schema.md), truy vết PS, ERD và bộ 3 sơ đồ.
- **Giữ:** core dòng hàng và các fact nghiệp vụ khác, không xóa vì ngoài PS; không sửa model dbt.
- **Mở rộng:** mỗi quy trình có grain riêng, dùng conformed dimensions; không join nhiều fact detail rồi cộng tiền.
- **Kiểm:** [star_schema_validation.ipynb](../notebooks/02_design/star_schema_validation.ipynb) đọc CSV và DuckDB read-only,
  **198/198 PASS**, có đối chứng tiền độc lập, lịch, distinct và phân rã; không là xác nhận deploy.
- **Giới hạn:** R là KPI theo trạng thái snapshot và order_date, không chứng minh dòng tiền/kế toán theo ngày.
  Khi Kafka cập nhật trạng thái, cần tính lại kỳ đặt hàng và giữ frozen snapshot để tái hiện deck.
- **Chưa làm:** CAGR/giai đoạn PS2, app code, Snowflake production, Kafka, persistent keys và lịch sử SCD2.

### 2026-09-27: Đưa pipeline DWH lên git (PR về `main`)

- **PM quyết:** chỉ đưa file build pipeline lên `main`; mọi thứ khác (docs, notebook, slide, script phụ) giữ ở local.
- **Làm:** nhánh `dwh/myuyen` tách từ `origin/main`, gồm 1 commit `c7de0ab` với 64 file:
  - `docker-compose.yml`, `requirements.txt`, `scripts/ingest/ingest_raw.py`;
  - toàn bộ `retail_dbt/` (models, macros, tests, `dbt_project.yml`, `profiles.yml` chỉ đọc biến môi trường);
  - `.gitignore` bổ sung `silver.zip`, `warehouse/`, artifact của dbt.
- **Kiểm:** chạy `dbt build` ngay trong nhánh mới, trên Postgres: 138/138 PASS. Không có file nào của `data/` hay file sinh ra khi chạy.
- **Local:** phần còn lại được ẩn khỏi `git status` bằng `.git/info/exclude`. File này chỉ có ở máy này, không commit.
- **PM quyết thêm (cùng ngày):** nhánh `dwh/myuyen` **chỉ để trên GitHub làm bản lưu**, không mở PR, không merge vào `main`.
  Lý do: đây là bản dev local (Postgres/Docker), target Snowflake chưa chạy thử. Chỉ đưa lên `main` khi có bản
  production ở GĐ3 (dbt chạy PASS trên Snowflake, có script nạp lên stage và lịch chạy tự động).

### 2026-09-27: Chốt 4 giai đoạn doanh thu cho PS2

- **PM/BA quyết:** chia 2013–2022 thành 4 giai đoạn:
  - A 2013→2016 tăng (+8,75%/năm);
  - B 2016→2018 chững (−6,39%/năm);
  - C 2018→2019 sập (−39,1%);
  - D 2019→2022 đi ngang (−0,14%/năm).

  Có hai điểm đổi hướng: cuối 2016 và cuối 2018.
- **Ghi lại:** 7 quy tắc nghiệp vụ và bảng số ở §4, mục "PS2: 4 giai đoạn"; câu SQL tự kiểm ở §7.
  Đã chạy câu SQL này trên Postgres và ra đúng các số trong bảng.
- **Cập nhật kèm:** `star_schema.md` §4, `star_schema_tu_ps.md` §5, `dwh_roadmap.md` (bảng trạng thái GĐ1).
- **Chưa làm:** model dbt cho bảng giai đoạn và bảng điểm đổi hướng, kèm test khóa số. Làm xong phần này là GĐ1 hoàn tất.

### 2026-09-27: Dựng bảng giai đoạn và điểm đổi hướng PS2 trong dbt (xong)

- **Vì sao:** mốc 4 giai đoạn đã chốt (mục trên). Cần đưa vào DWH để dashboard/app đọc thẳng, không tự viết SQL, và khóa số bằng test.
- **Kế hoạch:**
  1. seed `ps2_phases.csv`: danh sách giai đoạn do BA chốt;
  2. model `rpt_revenue_phase`: 1 dòng mỗi giai đoạn;
  3. model `rpt_revenue_turning_point`: 1 dòng mỗi điểm đổi hướng;
  4. test cho công thức, tính liền mạch của các giai đoạn, và các số đã chốt;
  5. build trên Postgres và DuckDB, rồi so hai bên.
- **Tiến độ:**
  - ✅ Bước 1–4: đã tạo `seeds/ps2_phases.csv` (4 dòng), `rpt_revenue_phase` (4 dòng), `rpt_revenue_turning_point` (3 dòng, xem ghi chú),
    và test `assert_rpt_phase` kiểm liền mạch, R độc lập, định nghĩa CAGR, độ lớn đổi hướng, số đã chốt.
    `dbt build` trên Postgres: **155/155 PASS** (trước là 138; thêm 1 seed, 2 model, 14 test).
  - ✅ Bước 5: DuckDB cũng **155/155 PASS**. Hai bảng mới ra số giống hệt Postgres.
  - ✅ Mutation test: cố ý làm sai số mũ CAGR thì FAIL; cố ý để hở 1 năm giữa A và B thì FAIL. Sau đó đã khôi phục và build lại 155/155.
  - ✅ Notebook kiểm chứng `star_schema_validation.ipynb` chạy lại vẫn **198/198 PASS**, tức không làm hỏng phần đã có.
  - ✅ Đã cập nhật tài liệu:
    - hướng dẫn này: §4 (bảng reporting, map PS2, mục PS2), §6 (test, mutation), §8 (số test mong đợi);
    - `dwh_roadmap.md`;
    - `star_schema.md` §4;
    - `star_schema_tu_ps.md` §5.
- **Kết quả:** PS2 đã đủ KPI trên slide 7. **GĐ1 hoàn tất**: đủ KPI cho cả 5 PS.
- **BA xác nhận:** giữ 3 điểm đổi hướng, gồm cả ranh giới cuối 2019 (C → D, −6,7%). Xem ghi chú trong mục PS2 ở §4.
- **Chưa commit:** theo quyết định của PM, code chỉ đưa lên git khi có bản production (GĐ3).

### 2026-09-27: Lập kế hoạch GĐ 2 (app phân tích)

- **Trước đó, BA xác nhận:** giữ 3 điểm đổi hướng PS2. Đã ghi ở §4, mục PS2; điểm cuối 2019 gọi là "đổi nhịp".
- **Làm:** viết `gd2_app_plan.md`, có link từ `dwh_roadmap.md` mục GĐ 2. Nội dung:
  - 7 trang: Tổng quan, PS1–PS5, Sức khỏe dữ liệu;
  - nguyên tắc: app **không chứa logic nghiệp vụ**, mọi số lấy từ `rpt_*`;
  - kiến trúc 2 backend: Postgres, DuckDB;
  - các mốc M0–M6, mỗi mốc có số nghiệm thu cụ thể.
- **Chưa làm:** chưa cài thư viện, chưa có code app.
- **Chờ PM quyết (§9 của kế hoạch):**
  - framework (dev đề xuất Streamlit);
  - app để demo hay để BA dùng hằng ngày (quyết định có làm M6 bộ lọc động không);
  - có làm AI giải thích không;
  - giao diện tiếng Việt.
- **PM đã quyết (cùng ngày):** dùng Streamlit; app **chỉ để demo**, nên bỏ M6; không làm AI giải thích. Riêng giao diện
  tiếng Việt thì PM không nêu, dev theo đề xuất là **có**. Đã ghi vào `gd2_app_plan.md` §9.

### 2026-09-27: M0, khung app Streamlit (xong)

- **Làm:** dựng `apps/retail_app/` gồm:
  - 7 trang trong menu; trang Tổng quan đọc thẳng `rpt_revenue_yearly`, 6 trang còn lại hiện "làm ở mốc Mx";
  - thanh bên chọn nguồn dữ liệu Postgres/DuckDB;
  - `dwh/connection.py` là chỗ duy nhất kết nối DB; `dwh/queries.py` chỉ chứa câu SELECT.
- **Đổi so với plan:**
  - thư mục `data/` đổi thành `dwh/`, vì `.gitignore` có dòng `data/` sẽ ẩn luôn thư mục đó;
  - thư mục `pages/` đổi thành `views/`, vì Streamlit coi `pages/` là kiểu nhiều trang cũ: AppTest chạy thẳng file trang, bỏ qua
    `app.py`, nên mất thanh bên. Đổi tên xong thì hết.
- **Cài thêm:** `streamlit==1.64.0`, `pytest==9.1.1`. Khi cài, uv tự nâng `pyarrow` từ 25.0.0 lên 25.0.1. Đã ghim cả ba vào
  `requirements.txt`.
- **Kiểm (chạy lại được):** `PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest apps/retail_app` cho kết quả **28/28 PASS**:
  - `rpt_revenue_yearly` từ Postgres và DuckDB **giống hệt nhau**: cùng cột, cùng kiểu, 11 năm. Test so tuyệt đối mọi cột, kể
    cả 18 cột số thực, không cho sai số. Đây là tiêu chí nghiệm thu M0 (`test_revenue_yearly_hai_backend`).
  - Thêm: cả 7 bảng trong schema `reporting` so hai backend. Cột tiền, số nguyên, chữ, ngày phải bằng tuyệt đối; cột số thực
    lệch tương đối ≤ 1e-12. Thực tế chỉ `rpt_august_parity` lệch ở 2 cột, cỡ 2,9e-16 (bit cuối), còn lại trùng tuyệt đối.
  - Smoke test: 7 trang × 2 backend chạy không lỗi, thanh bên có mặt ở mọi trang.
  - Giả lập Postgres tắt (trỏ sai cổng): trang báo lỗi rõ và gợi ý chuyển sang DuckDB, app không sập.
  - Mutation: cố ý sửa R lệch 0,01 hoặc U lệch 1e-9 thì phép so hai backend FAIL, tức test có tác dụng (`test_phep_so_bat_duoc_sai_lech`).
- **Mở server thật:** `/_stcore/health` trả `ok`, trang chủ trả HTTP 200. Việc này chỉ chứng minh server lên được, không kiểm
  backend hay nội dung trang; phần đó do smoke test ở trên kiểm.
- **PM mở app xem (2026-09-27, 22:17 và 22:21).** Hai ảnh lượt này đã xóa theo yêu cầu PM, vì hai ảnh "Đọc lại dữ liệu" ở dưới
  đã thay thế: chúng có cùng bảng số và thêm câu báo nguồn. Đối chiếu 3 điểm cần xem:
  - ✅ menu đủ 7 trang tiếng Việt;
  - ✅ bảng có 11 năm (2012–2022), số theo kiểu Việt; dòng 2019 (G 1.136.801.441,51; R 864.329.801,94; N 33.259) khớp đúng
    `rpt_revenue_yearly` trên Postgres khi dev truy vấn lại;
  - ✅ chuyển sang DuckDB (22:21), bấm **Đọc lại dữ liệu**: bảng vẫn hiện, cùng số với Postgres.
- **PM hỏi: làm sao chắc bảng đọc từ DB mà không phải số dev gõ sẵn?** Có 3 bằng chứng, xếp từ yếu đến mạnh:
  1. **Quét code:** tìm các con số trên ảnh (`1136801441`, `1.136.801`, `864329801`, `33259`, `741497748`…) trong `apps/`, không
     thấy chỗ nào. Trang Tổng quan chỉ gọi `load_or_stop('revenue_yearly')`, hàm này chạy đúng một câu
     `select * from reporting.rpt_revenue_yearly order by year`. Cách này chỉ chứng minh "không thấy", nên cần thêm 2 cách dưới.
  2. **Test sửa số** `apps/retail_app/tests/test_khong_hardcode.py` (PASS):
     - chép `warehouse/dbt.duckdb` ra file tạm, sửa dòng 2019 thành số lạ (G 123.456.789,01; R 98.765.432,10; N 4.242);
     - cho app đọc file tạm thì app hiện **đúng số lạ**; đọc file gốc thì vẫn ra số thật;
     - nếu số nằm sẵn trong code, app sẽ không đổi theo và test FAIL. File gốc không bị sửa.
     - Để làm được, `dwh/connection.py` thêm biến môi trường `RETAIL_DUCKDB_PATH` để trỏ sang file khác.
     - Giới hạn: test này chỉ chạy trên DuckDB. Postgres dùng cùng code trang, chỉ khác hàm kết nối.
  3. **PM/BA tự truy vấn DB, không qua app** (từ root repo), rồi so với dòng 2019 trên ảnh:

     ```bash
     # Postgres (Docker)
     docker exec retail_dwh psql -U retail -d retail -c "select year, g, r, n from reporting.rpt_revenue_yearly where year = 2019"
     # DuckDB
     PYTHONUTF8=1 .venv/Scripts/python.exe -c "import duckdb; print(duckdb.connect('warehouse/dbt.duckdb', read_only=True).sql('select year, g, r, n from reporting.rpt_revenue_yearly where year = 2019').fetchall())"
     ```

     Dev đã chạy thử cả hai lệnh: đều ra `2019 | 1136801441.51 | 864329801.94 | 33259`, khớp ảnh.
     Trong Git Bash, lệnh `docker exec` cần thêm `MSYS_NO_PATHCONV=1` ở đầu; trên PowerShell thì không cần.
- **Còn một câu hỏi xa hơn: số trong DB có đúng không?** Câu này do 155 test dbt trả lời, không phải app. Ví dụ:
  - `assert_rpt_reconciles` đối soát bảng `rpt_*` theo từng tháng và từng năm với các nguồn độc lập (`fact_order`, `stg_payments`,
    `fact_daily_sales`);
  - `assert_rpt_deck_numbers` khóa các số trên deck, ví dụ G = 16.430.476.585,53 và R = 12.518.175.957,20.
- Sau khi thêm test sửa số, bộ test app là **29/29 PASS**.
- **PM yêu cầu (2026-09-27): bằng chứng phải hiện ngay trên app.** Đã làm:
  - bấm **Đọc lại dữ liệu** thì app xóa bộ nhớ đệm, truy vấn DB lại, rồi hiện khung xanh, ví dụ: *"Đã đọc lại dữ liệu thành công:
    11 dòng từ `reporting.rpt_revenue_yearly` trên **PostgreSQL localhost:5433/retail**, lúc 22:35:10 27/09/2026."* Góc màn hình
    có thêm thông báo nhỏ "Đọc từ … thành công". Với DuckDB, câu báo ghi `DuckDB warehouse/dbt.duckdb`;
  - khi không bấm nút, dưới tiêu đề luôn có dòng *"Nguồn: bảng … trên … Truy vấn DB lúc … (giữ trong bộ nhớ đệm 10 phút)"*.
    Giờ ghi ở đây là lúc truy vấn DB thật, không phải lúc lấy từ bộ nhớ đệm;
  - nếu DB lỗi thì **không** báo thành công, chỉ hiện lỗi đỏ như cũ;
  - bấm nút ở trang chưa làm (PS1–PS5, Sức khỏe dữ liệu) thì app báo "Trang này chưa đọc dữ liệu nào từ DB";
  - test mới trong `tests/test_smoke.py`: bấm nút thì có câu báo thành công, đúng backend, đúng 11 dòng, đúng tên bảng; lần chạy
    sau thì câu báo biến mất; Postgres tắt thì không báo thành công. Bộ test app: **32/32 PASS**.
  - Lưu ý: câu báo cho biết app vừa truy vấn DB nào và được bao nhiêu dòng. Muốn chứng minh số không gõ sẵn thì vẫn dựa vào
    test sửa số ở trên.
  - **PM kiểm trên app thật:** bấm nút trên cả hai backend, đều hiện khung xanh và thông báo góc màn hình, số trong bảng giống nhau.
    - Postgres, lúc 22:34:49: *"… 11 dòng từ `reporting.rpt_revenue_yearly` trên PostgreSQL localhost:5433/retail …"*

      ![M0: bấm Đọc lại trên Postgres](screenshots/streamlit/m0_doc_lai_postgres.png)
    - DuckDB, lúc 22:35:13: *"… 11 dòng từ `reporting.rpt_revenue_yearly` trên DuckDB warehouse/dbt.duckdb …"*

      ![M0: bấm Đọc lại trên DuckDB](screenshots/streamlit/m0_doc_lai_duckdb.png)
- **M0 nghiệm thu xong (PM, 2026-09-27):**
  - tiêu chí M0 đạt, xem test `test_revenue_yearly_hai_backend`;
  - PM đã xem giao diện thật, có 2 ảnh ở `docs/screenshots/streamlit/` (`m0_doc_lai_postgres.png`, `m0_doc_lai_duckdb.png`);
  - còn một lỗi giao diện (canh lề cột số) để sửa ở M1.
- **Ghi nhận từ ảnh, sửa ở M1:** cột tiền và số đơn đang canh trái, vì đã đổi sang chuỗi để định dạng kiểu Việt. Chỉ cột Năm canh
  phải. Bảng số nên canh phải hết.
- **Khóa file DuckDB (câu hỏi mở trong plan §5), chạy thử 1 lần** bằng `apps/retail_app/tests/manual_duckdb_lock.py` (cách chạy
  ghi đầu file; không nằm trong pytest vì mất khoảng 1 phút):
  - cho app đọc DuckDB 2 lần/giây trong lúc `dbt build --target duckdb` chạy: dbt vẫn **155/155 PASS**;
  - nhưng **27/107** lần app đọc bị lỗi "file đang bị dùng" trong lúc dbt ghi. App đã báo lỗi kèm hướng dẫn "đợi build xong rồi
    bấm Đọc lại dữ liệu".
  - → **Quy tắc demo:** không chạy `dbt build --target duckdb` trong lúc đang trình chiếu trên DuckDB.
- **Cách mở app** (từ root repo; Postgres Docker phải đang chạy, nếu không thì chọn DuckDB ở thanh bên):

  ```bash
  .venv/Scripts/streamlit.exe run apps/retail_app/app.py
  ```

  Lần đầu, Streamlit hỏi email trong terminal: bấm Enter để bỏ qua. Trình duyệt mở `http://localhost:8501`.
  (Lệnh đầy đủ, cập nhật 2026-09-29: mục 8.1.)

- **Chưa commit:** code app giữ ở local tới GĐ 3.
- **PM đổi quyết định về M6 (2026-09-27):** **vẫn làm M6** (bộ lọc động), nhưng chỉ bắt đầu **sau khi M1–M5 được nghiệm thu**.
  Đã sửa `gd2_app_plan.md` §3 (tiêu chí 2 áp dụng lại), §6 (M6) và §9.
  - M6 cho người xem tự chọn khoảng thời gian hoặc lọc nhiều chiều cùng lúc (ngành hàng × khu vực × kênh). App phải tính lại số
    từ dòng hàng. N và C phải đếm phân biệt, không cộng từ bảng tháng/năm.
  - Phần tính toán vẫn nằm trong dbt, có test riêng; app chỉ truyền điều kiện lọc.
  - Nghiệm thu: lọc trùng đúng một năm thì ra đúng N, C, R của `rpt_revenue_yearly`.
  - M1–M5 không phải làm khác đi. `dwh/queries.py` vẫn là chỗ duy nhất đọc DB, nên M6 chỉ thêm hàm mới, không sửa trang cũ.
- **Tiếp theo: M1, gồm trang Tổng quan và PS1** (plan §6). Việc cần làm:
  1. **dbt:** thêm 1 model toàn kỳ (ví dụ `rpt_revenue_total`) có G, R, R/G và các phần của thác G → R. Kèm test khóa số
     G = 16.430.476.585,53, R = 12.518.175.957,20, R/G = 76,2%. Đã kiểm G này là tổng **2012–2022**; nếu chỉ tính 2013–2022 thì ra
     15.688.978.837,51. Theo nguyên tắc "app không chứa logic", app không tự cộng.
  2. **Dải thông tin chung** ở đầu mọi trang (plan §3, tiêu chí 3): kỳ phân tích, định nghĩa R/G, trạng thái snapshot, thời
     điểm refresh.
  3. **Trang Tổng quan:** thẻ KPI G, R, R/G; biểu đồ R theo năm; lối sang 5 trang PS.
  4. **Trang PS1:** thác G → R (hủy, trả, chưa giao, chiết khấu), R/G theo năm, tỷ lệ hủy, kèm "Cách đọc" và "Giới hạn".
  5. **Sửa canh lề:** cột số canh phải.
  6. **Kiểm:** pytest khóa số trên app, smoke test, so hai backend, rồi PM xem và chụp ảnh `m1_*.png`.
  - Vẽ biểu đồ: dùng Altair, đã có sẵn theo Streamlit, nên không cài thêm thư viện. Nếu thác G → R vẽ bằng Altair quá rối thì dev
    báo lại trước khi cài Plotly.

### M1: Tổng quan + PS1 (xong, PM nghiệm thu 2026-09-28)

- **Kết quả:** app hiện đúng G = 16.430.476.585,53; R = 12.518.175.957,20; R/G = 76,2% (tiêu chí M1), trên cả Postgres và DuckDB.
  Thác G → R vẽ được bằng Altair, không cần cài Plotly.

  ![M1: trang Tổng quan](screenshots/streamlit/m1_tong_quan_postgres.png)
- **dbt thêm 3 bảng, tổng cộng 166/166 PASS trên cả hai backend** (trước M1 là 155):
  - `rpt_revenue_total`: 2 dòng, **2012–2022** (toàn bộ dữ liệu, số của deck) và **2013–2022** (kỳ phân tích,
    G = 15.688.978.837,51). Cùng các cột với `rpt_revenue_yearly` (G, R, R/G, 4 phần bị trừ, N, C, U, P, AOV…).
  - `rpt_revenue_bridge`: thác G → R ở dạng dài: 13 kỳ (2 kỳ gộp + 11 năm) × 6 bước (G, hủy, trả, chưa giao, chiết khấu, R).
    Vị trí đáy/đỉnh từng cột cũng tính sẵn trong dbt, app chỉ vẽ.
  - `rpt_build_info`: 1 dòng, gồm lúc `dbt build`, ngày đầu/cuối của dữ liệu, kỳ phân tích. Dải thông tin chung đọc từ đây.
  - Test mới `assert_rpt_total` khóa: số deck; toàn kỳ = tổng các năm (G, R, 4 phần, số món, số đơn); C đếm phân biệt nên
    **nhỏ hơn** tổng C các năm; G − R = 4 phần; mỗi kỳ đủ 6 bước và các cột thác nối tiếp nhau.
  - **Thử làm sai cố ý** (sửa bước "đơn trả", đổi năm đầu của kỳ 2013–2022 thành 2012): test FAIL đúng 2 quy tắc. Đã khôi phục.
- **App:**
  - Mọi trang có **dải thông tin chung** (kỳ phân tích, định nghĩa R/G, trạng thái snapshot, lúc `dbt build` theo giờ Việt Nam,
    backend đang đọc).
  - **Tổng quan:** 2 hàng thẻ G, R, R/G (2012–2022 và 2013–2022); cột G/R theo năm (2012 tô nhạt vì chưa đủ năm); bảng năm; lối
    sang 5 trang PS; "Cách đọc" và "Giới hạn".
  - **PS1:** chọn kỳ (2 kỳ gộp hoặc từng năm); thẻ KPI; thác G → R kèm bảng; G/R theo tháng; R/G và tỷ lệ hủy theo năm; bảng năm.
  - Cột số trong bảng đã canh phải (lỗi ghi nhận ở M0).
  - Bấm **Đọc lại dữ liệu** thì khung xanh liệt kê mọi bảng trang vừa đọc, kèm số dòng.
- **Test app: 53/53 PASS** lúc dev xong (M0 có 32; 58 sau khi sửa theo câu hỏi của PM bên dưới). Test mới khóa số deck trên thẻ KPI, thác và bảng năm của PS1, đổi kỳ sang 2019 thì số
  đổi theo `rpt_revenue_yearly`. Test chứng minh không gõ sẵn: sửa G, R toàn kỳ trên một bản sao DB thì thẻ KPI đổi theo.
- **PM gửi 3 ảnh PS1** (kỳ 2012–2022, 2013–2022, 2022), số khớp DB:

  ![M1: PS1 kỳ 2012–2022](screenshots/streamlit/m1_ps1_2012_2022_postgres.png)
  ![M1: PS1 kỳ 2013–2022](screenshots/streamlit/m1_ps1_2013_2022_postgres.png)
  ![M1: PS1 năm 2022](screenshots/streamlit/m1_ps1_2022_postgres.png)
- **Sửa sau khi xem ảnh** (dev chụp thêm toàn trang để xem phần dưới). Tiêu đề thác trong 3 ảnh trên là bản cũ:
  - tiêu đề thác bị lồng ngoặc "(2012–2022 (toàn bộ dữ liệu))" → tách kỳ xuống dòng chú thích bên dưới;
  - bảng năm chỉ hiện 10 dòng, phải cuộn mới thấy 2022 → hiện đủ 11 năm (cả trang Tổng quan);
  - trục tỷ lệ hủy ghi "9%" ở mọi vạch (vì tỷ lệ chỉ dao động 9,0–9,6%) → thêm 1 chữ số thập phân;
  - biểu đồ G/R theo tháng: trục ghi "0,1 tỷ" lặp 3 lần và mỗi năm hiện 2 nhãn → đổi trục sang triệu, mỗi năm một nhãn;
  - thẻ "Tỷ lệ chiết khấu" 4,6% khác nhãn 3,6% trên thác: cùng khoản tiền, khác mẫu số (thẻ chia cho tiền hàng đơn đã giao, thác
    chia cho G) → ghi rõ trong ô "?" của thẻ và thêm một ý ở "Cách đọc".

  ![M1: PS1 toàn trang sau khi sửa](screenshots/streamlit/m1_ps1_toan_trang_postgres.png)
- **Câu hỏi cho BA, thấy khi xem PS1 năm 2022:** phần "đơn chưa giao" chiếm 4,8–5,4% G mỗi năm từ 2012 đến 2020, rồi lên **8,0%
  (2021) và 7,9% (2022)**. Vì 2021 cũng cao nên không phải do đơn cuối năm 2022 chưa kịp giao. Cả 3 trạng thái
  `created`, `paid`, `shipped` đều tăng. Đây là phần lớn lý do R/G rơi từ 76,5% (2020) xuống 73,4% (2021). Dev chưa tìm nguyên nhân;
  BA quyết định có đưa vào "Cách đọc" của PS1 không. Kiểm lại:
  `select period_code, share_of_g from reporting.rpt_revenue_bridge where step_code = 'undelivered' and period_type = 'year'`.
- **PM hỏi (2026-09-28): chọn năm 2012 mà biểu đồ "G và R theo tháng" vẫn hiện nhãn năm 2012–2022, tháng trong năm đâu?**
  Đúng là lỗi: biểu đồ này vẽ mọi tháng và không đổi theo ô **Kỳ**. Đã sửa:
  - chọn **một năm** → cột G/R của từng tháng T1…T12 trong năm đó, kèm bảng tháng (G, R, R/G, tỷ lệ hủy, số đơn, R so cùng tháng
    năm trước). Năm 2012 chỉ có T7–T12, trang ghi rõ;
  - chọn **kỳ gộp** → đường theo tháng đúng trong kỳ đó (2012–2022: 126 tháng, 2013–2022: 120 tháng), không có bảng tháng vì quá dài;
  - hai biểu đồ R/G, tỷ lệ hủy và bảng năm vẫn hiện mọi năm để so sánh, có đường gạch đỏ đánh dấu năm đang chọn;
  - số lấy thẳng từ các dòng của `rpt_revenue_monthly`, app chỉ lọc theo năm, không tính lại.
  - 5 test mới (chọn 2019 ra đúng 12 tháng, chọn 2012 ra T7–T12, số khớp `rpt_revenue_monthly` trên cả hai backend; kỳ gộp ra
    đúng số tháng). Bộ test app: **58/58 PASS**.

  ![M1: PS1 chọn năm 2019](screenshots/streamlit/m1_ps1_2019_theo_thang_postgres.png)
- **PM nghiệm thu M1 ngày 2026-09-28** ("check PS1 oke rồi"), sau khi xem lại PS1 đã sửa. Chuyển sang M2 (PS2).
- **Chưa commit.**

### M2: PS2 xu hướng (xong, PM nghiệm thu 2026-09-28)

- **Kết quả:** trang PS2 hiện đúng các số đã chốt, trên cả Postgres và DuckDB (tiêu chí M2):
  - CAGR 4 giai đoạn: A **+8,75%**, B **−6,39%**, C **−39,10%**, D **−0,14%**;
  - độ lớn 3 điểm đổi hướng: cuối 2016 **−9,7%**, cuối 2018 **−39,1%**, cuối 2019 **−6,7%** (ghi "đổi nhịp").

  ![M2: trang PS2](screenshots/streamlit/m2_ps2_xu_huong_postgres.png)
- **Trang PS2 gồm:**
  - 4 thẻ CAGR, mỗi thẻ một giai đoạn (ô "?" ghi tổng thay đổi cả giai đoạn);
  - đường **R 12 tháng gần nhất**, tô nền 4 giai đoạn, chấm đỏ + nhãn ở 3 điểm đổi hướng;
  - bảng giai đoạn (R năm đầu/cuối, chênh R, tổng thay đổi, CAGR) và bảng điểm đổi hướng (R 12 tháng trước/sau, độ lớn, ghi chú BA);
  - cột tăng trưởng R theo năm, 2014–2022;
  - "Cách đọc" theo 7 quy tắc ở §4: 2022 +12,3% ghi là "tín hiệu hồi phục cuối giai đoạn D"; **không có** con số tăng trưởng
    cho cả 10 năm; giai đoạn chỉ mô tả, muốn biết vì sao thì xem PS4, PS5.
- **Cách đặt giai đoạn lên đường R 12 tháng:** giá trị của đường tại tháng 12 đúng bằng R cả năm. Vì vậy giai đoạn A (2013→2016)
  nằm từ 12/2013 tới 12/2016, điểm đổi hướng cuối 2016 nằm ở 12/2016. Đường bắt đầu từ 07/2013 nên đoạn 07–11/2013 không thuộc
  giai đoạn nào; trang ghi rõ.
- **dbt: 169/169 PASS trên cả hai backend** (M1 là 166):
  - `rpt_revenue_phase` thêm `band_start_date`, `band_end_date`; `rpt_revenue_turning_point` thêm `turning_month_date`, `turn_note`.
    App tô nền và đặt điểm theo các cột này, không gõ năm nào trong code (tiêu chí 5 của plan);
  - seed `ps2_phases` thêm cột `end_turn_note` (xem §4). Chữ "đổi nhịp" nằm ở seed, không đoán bằng quy tắc: nếu suy từ chiều
    tăng/giảm thì cuối 2018 (giảm → giảm mạnh) cũng thành "đổi nhịp", trái với bảng BA đã chốt. Muốn đổi ghi chú: sửa cột này
    trong seed, rồi sửa chữ khóa trong `assert_rpt_phase`;
  - `assert_rpt_phase` thêm: đường R 12 tháng tại `band_start_date`/`band_end_date` = R năm đầu/cuối, tại `turning_month_date` =
    R 12 tháng trước; khóa thêm −6,7% và "đổi nhịp" chỉ ở cuối 2019;
  - **thử làm sai cố ý** (chuyển "đổi nhịp" sang dòng B, đặt `band_end_date` ở tháng 11): test FAIL đúng 2 quy tắc. Đã khôi phục.
    Thử thêm từng chỗ một (DuckDB, `--store-failures` để xem dòng lỗi), đã khôi phục và build lại 169/169:
    - chuyển "đổi nhịp" từ dòng C sang dòng B của seed → FAIL, quy tắc "số đã chốt… (doi nhip)" báo `n = 2`
      (cuối 2018 có chữ mà không phải 2019; cuối 2019 mất chữ);
    - đổi số khóa −6,7% trong test thành −7,0% → FAIL, cùng quy tắc báo `n = 1` (chỉ cuối 2019 lệch).
- **Test app: 68/68 PASS** (M1 là 58). Test mới:
  - thẻ CAGR, bảng giai đoạn, bảng điểm đổi hướng khớp số chốt và khớp `rpt_*` trên cả hai backend;
  - "Cách đọc" có câu hồi phục 2022, không có con số cả 10 năm, có dẫn sang PS4/PS5;
  - **chứng minh không gõ sẵn:** sửa tên + CAGR giai đoạn A và độ lớn + ghi chú điểm cuối 2016 trên một bản sao DB → trang đổi theo.
- **Câu hỏi cho BA:** cuối 2018 (giảm nhẹ → sập) có cần ghi chú như cuối 2019 không, ví dụ "giảm tăng tốc"?
  **PM trả lời 2026-09-28: có ghi chú.** PM không nêu chữ nên dev dùng "giảm tăng tốc" như đề xuất. Đã sửa seed (dòng B),
  `assert_rpt_phase` (khóa cả hai ghi chú), "Cách đọc" của PS2 và test app. dbt vẫn 169/169.
- **PM nghiệm thu M2 ngày 2026-09-28** ("M2 ok"), rồi yêu cầu bổ sung 2 góp ý trước khi nghiệm thu M3 (mục dưới). Các chỗ dev tự quyết (nền giai đoạn từ tháng 12 tới tháng 12, CAGR 2 chữ số
  thập phân, không có con số cả 10 năm, câu hồi phục 2022, biểu đồ tăng trưởng năm, màu giai đoạn, cột `end_turn_note`) giữ nguyên.
- **Chưa commit.**

- **Bổ sung sau góp ý (2026-09-28), 2 việc:**
  1. **Dữ liệu tự tìm tháng đổi hướng** (deck slide 6 yêu cầu 4: "tìm tháng đường này đổi hướng, xem hướng mới có kéo dài
     không"). Trước đó trang chỉ vẽ mốc BA lên biểu đồ, chưa phải bằng chứng. Đã thêm:
     - seed `ps2_direction_rule` (khoảng so 3/6/9 tháng, 6 là chính, hướng mới ≥ 6 tháng; theo ghi chú slide 7). PM không
       chọn quy tắc riêng nên dùng đúng ghi chú slide 7, không thêm ngưỡng tốc độ;
     - model `rpt_revenue_direction` (hướng từng tháng) và `rpt_revenue_direction_change` (các lần đổi hướng, đỉnh/đáy, giữ
       bao lâu); `rpt_revenue_turning_point` thêm `data_extreme_month_date`, `data_change_month_date` để đối chiếu mốc BA;
     - test `assert_rpt_direction`: hướng tính lại độc lập bằng `lag()`, đoạn cùng hướng đúng độ dài, đỉnh/đáy khớp R 12 tháng,
       khóa số (bảng ở §4), đối chiếu mốc BA;
     - trang PS2: tam giác đen đánh dấu đỉnh 08/2016 và đáy 10/2021 trên biểu đồ; bảng "Dữ liệu tự tìm" cho 3 khoảng so;
       cột "Dữ liệu tự tìm thấy?" trong bảng điểm đổi hướng (cuối 2016: 08/2016, phát hiện 02/2017; cuối 2018, 2019: không);
       "Giới hạn" ghi rõ dữ liệu chỉ xác nhận mốc đổi hướng, mốc đổi tốc độ là nhận định BA.
     - Kết quả: cuối 2016 được dữ liệu xác nhận; cuối 2018, cuối 2019 là đổi tốc độ, không tự tìm ra (bảng ở §4).
  2. **Tăng trưởng theo tháng so với cùng tháng năm trước** (slide 6 yêu cầu 2): trước đây chỉ có ở bảng tháng của PS1. Đã
     thêm biểu đồ cột từ 08/2013 trên PS2, nền tô 4 giai đoạn. Đọc thẳng `yoy_rate` của `rpt_revenue_monthly`, không sửa dbt.
  - **dbt 180/180 PASS trên cả hai backend** (169 trước đó; thêm 1 seed, 2 model, 8 test). Lần đầu build Postgres lỗi vì
    `count(distinct …) over (…)` không có trên Postgres; đã đổi sang so `min`/`max`.
  - **Thử làm sai cố ý:** đổi độ dài tối thiểu của khoảng so chính từ 6 xuống 3 tháng → FAIL quy tắc số khóa; đảo cách tìm
    đỉnh/đáy → FAIL 2 quy tắc (số khóa, đối chiếu mốc BA). Đã khôi phục.
  - **Test app: 84/84 PASS** (75 trước đó): bảng dữ liệu tự tìm khớp `rpt_*` trên cả hai backend, cột đối chiếu mốc BA,
    biểu đồ tháng có trên trang, sửa tháng phát hiện trên bản sao DB thì trang đổi theo. `test_backends.py` so thêm 3 bảng mới
    giữa hai backend.
  - Ảnh `m2_ps2_xu_huong_postgres.png` đã chụp lại.

  ![M2: trang PS2 sau khi bổ sung](screenshots/streamlit/m2_ps2_xu_huong_postgres.png)

### M3: PS3 nhịp lịch (xong, PM nghiệm thu 2026-09-29)

- **Kết quả:** trang PS3 hiện đúng tiêu chí M3 trên cả Postgres và DuckDB:
  - tháng 8 năm lẻ so với năm chẵn: **−37,7%** (TB chỉ số tháng 8 của 5 năm lẻ 0,83 ÷ 5 năm chẵn 1,33 − 1);
  - mức dồn về cuối tháng 2013–2022: **+7,2 điểm %** > 0 (R từ ngày 26 chiếm 25,0%, rải đều chỉ 17,9%).
    Năm nào cũng dương, từ +5,8 (2013) tới +7,9 điểm % (2014).

  ![M3: trang PS3](screenshots/streamlit/m3_ps3_nhip_lich_postgres.png)
- **Trang PS3 gồm** 3 nhịp của deck slide 8:
  - **theo tháng:** bảng nhiệt chỉ số tháng, 10 năm × 12 tháng. Mỗi ô là một tháng thật, không lấy trung bình (§5 quy tắc 1).
    Cao T4–T6, thấp T11–T1, năm nào cũng lặp lại;
  - **cuối tháng:** bảng nhiệt mức dồn (điểm %) từng tháng;
  - **tháng 8:** cột chỉ số tháng 8 từng năm, tô màu năm lẻ/chẵn, kèm đường TB hai nhóm;
  - bảng theo năm: chênh mùa cao/thấp, tỷ trọng ngày ≥ 26, mức rải đều, mức dồn, chỉ số tháng 8;
  - "Giới hạn" lấy từ ghi chú slide 9: chỉ số tháng không loại hết xu hướng trong năm; nhịp tháng 8 chỉ dựa trên 5 + 5 năm,
    là quan sát thăm dò, chưa phải quy luật dự báo.
- **dbt thêm cột (vẫn 169/169 PASS trên cả hai backend,** vì các kiểm tra mới là quy tắc thêm vào test có sẵn):
  - `rpt_revenue_yearly`, `rpt_revenue_total` thêm `r_day26_plus`, `eom_share`, `eom_expected_share`, `eom_excess`. Trước đây
    mức dồn chỉ có theo tháng, còn KPI cả kỳ chỉ nằm trong test `assert_rpt_deck_numbers`. Mức rải đều của năm/kỳ là TB
    (D − 25)/D các tháng, trọng số R tháng, giống cách test đó tính;
  - `rpt_august_parity` thêm `max_index_odd`, `min_index_even` (slide 8 yêu cầu 4: "năm nào cũng vậy không") và
    `loo_min_odd_vs_even`, `loo_max_odd_vs_even` (yêu cầu 5: bỏ lần lượt từng năm, chênh vẫn từ **−39,1% đến −36,2%**);
  - `assert_rpt_calendar` thêm 3 quy tắc: mức dồn năm tính độc lập từ dòng hàng; kỳ gộp = cộng các năm và 2013–2022 phải dương;
    tháng 8 khóa −37,7%, khoảng bỏ-từng-năm tính lại bằng công thức tổng, mọi năm lẻ < mọi năm chẵn;
  - **thử làm sai cố ý:** tính mức rải đều năm bằng TB không trọng số → FAIL 2 quy tắc (năm: 11 dòng, kỳ gộp: 2 dòng);
    lấy TB thay cho min ở `loo_min_odd_vs_even` → FAIL quy tắc tháng 8. Đã khôi phục. Một lần thử khác (bỏ nhầm năm kế tiếp
    thay vì năm đang xét) **không** làm test FAIL, vì kết quả min/max không đổi, nên không tính là bằng chứng.
- **Test app: 75/75 PASS** (M2 là 68). Test mới: 3 thẻ KPI, bảng năm và chỉ số tháng 8 khớp `rpt_*` trên cả hai backend; câu
  "năm lẻ nào cũng thấp hơn mọi năm chẵn" chỉ hiện khi đúng như vậy. **Chứng minh không gõ sẵn:** sửa chỉ số tháng 8/2013
  thành 2,5 trên bản sao DB thì thẻ ra −13,4% và câu trên đổi thành "có năm lẻ cao hơn năm chẵn".
  - Khi làm test này thấy: trên DuckDB, view trỏ bảng qua tên file (`dbt`), nên bản sao DB phải giữ tên `dbt.duckdb`.
- **Quan sát cho BA (chưa tìm nguyên nhân):** 2013–2022, hai tháng gần như **không** dồn về cuối tháng:
  - tháng 6: từ −2,2 tới +0,5 điểm % (trung vị −0,4);
  - tháng 11: từ −3,3 tới +2,6 điểm % (trung vị +0,4); âm ở 2013, 2018, 2019, 2020, 2021.

  Tháng 2 thấp hơn (trung vị +4,9, năm 2020 −0,3). Chín tháng còn lại năm nào cũng dồn, từ +3,8 tới +15,4 điểm %. Kiểm lại:
  `select month, min(eom_excess), median(eom_excess), max(eom_excess) from reporting.rpt_revenue_monthly where is_analysis_period group by month order by month`
  (hàm `median` chạy trên DuckDB; Postgres dùng `percentile_cont(0.5) within group (order by eom_excess)`).
  Ô 11/2021 hiện "−0,0" vì mức dồn là −0,04 điểm %, âm nhưng làm tròn 1 chữ số thập phân thành 0.
- **Slide 8 yêu cầu 2** "so chỉ số giữa các năm **và giữa các giai đoạn ở PS2**": dev hỏi cách gom vì hai giai đoạn liền nhau
  dùng chung năm ranh giới. **PM chọn 2026-09-28: ghi nhãn giai đoạn A–D cạnh mỗi năm trên bảng nhiệt.** Đã làm:
  - `rpt_revenue_yearly` thêm cột `ps2_phase_codes`, tính từ seed `ps2_phases`: năm nằm trong giai đoạn nào thì mang mã đó,
    năm ranh giới mang cả hai (2016 "A/B", 2018 "B/C", 2019 "C/D"), 2012 để trống. BA đổi mốc thì nhãn đổi theo;
  - `assert_rpt_phase` thêm 2 quy tắc: có mã ⇔ năm nằm trong giai đoạn; khóa 2012, 2016, 2018, 2019. Thử làm sai (bỏ năm
    cuối khỏi mỗi giai đoạn) → FAIL cả 2 quy tắc. Đã khôi phục. dbt vẫn **180/180** trên cả hai backend;
  - trang PS3: hai bảng nhiệt ghi "2016 · A/B"… cạnh mỗi năm; bảng theo năm thêm cột "Giai đoạn". Không tính thêm số nào.
  - Test app **85/85 PASS**: cột "Giai đoạn" đúng trên cả hai backend; sửa nhãn năm 2014 trên bản sao DB thì trang đổi theo.
  - Ảnh `m3_ps3_nhip_lich_postgres.png` đã chụp lại.
- **Bổ sung sau góp ý M3 (2026-09-28), 3 việc:**
  1. **So sánh nhịp lịch giữa các giai đoạn** (slide 8 yêu cầu 2). Chỉ ghi nhãn A–D cạnh năm chưa đủ, cần so sánh có số và
     nhận xét. **Quy ước năm ranh giới** (dev đề xuất, cần PM/BA xác nhận): năm ranh giới tính cho giai đoạn **kết thúc** ở
     năm đó, năm 2013 tính cho A. Kết quả: A 2013–2016 (4 năm), B 2017–2018 (2), C 2019 (1), D 2020–2022 (3). Đây là **quy
     ước riêng để so sánh PS3**: PS3 gom doanh thu theo năm lịch nên mỗi năm phải thuộc đúng một giai đoạn, không năm nào bị
     đếm hai lần. Nó **không đồng nhất với nền màu trang PS2**: nền PS2 là mốc trên đường R 12 tháng, điểm tháng 12 năm ranh
     giới dùng chung cho hai giai đoạn kề nhau. Nhãn "A/B" trên bảng nhiệt vẫn giữ (thành viên theo seed).
     *(Sửa 2026-09-28 theo góp ý: bản đầu ghi "lý do: khớp nền màu trang PS2", dễ hiểu nhầm.)*
     - Model `rpt_calendar_phase_month` (chỉ số tháng gộp = R tháng cộng các năm ÷ TB tháng của giai đoạn, tính lại từ tổng,
       không lấy TB chỉ số) và `rpt_calendar_phase` (tháng cao/thấp nhất, chênh mùa, mức dồn, tháng 8 lẻ/chẵn, thứ hạng).
     - Kết quả:

       | Giai đoạn | Cao nhất | Thấp nhất | Chênh mùa | Mức dồn cuối tháng | T8 lẻ / chẵn |
       |---|---|---|---:|---:|---:|
       | A (2013–2016) | T5 | T12 | 2,91 lần | +7,3 điểm % | −37,3% |
       | B (2017–2018) | T5 | T12 | **4,52 lần** | +7,1 điểm % | −43,0% |
       | C (2019) | T5 | T12 | 3,71 lần | +6,9 điểm % | – (chỉ có năm lẻ) |
       | D (2020–2022) | T5 | T12 | 3,54 lần | +7,0 điểm % | −37,6% |

     - Nhận xét: nhịp mùa (cùng đỉnh T5, đáy T12) và nhịp dồn cuối tháng xuất hiện ở cả bốn giai đoạn; chênh tháng 8 lẻ/chẵn
       chỉ kiểm được ở A, B, D (C chỉ có năm 2019, năm lẻ). Khác nhau ở độ mạnh: mùa vụ mạnh nhất ở B, yếu nhất ở A.
       *(Sửa 2026-09-28 theo góp ý: bản đầu ghi "cả 3 nhịp có ở mọi giai đoạn", quá mức với C.)* Trang ghi kèm lưu ý: năm doanh thu giảm trong năm (2018 có T12 chỉ 0,33) làm chênh mùa lớn hơn, và giai
       đoạn 1–2 năm kém chắc. Trang ghép nhận xét từ các cột; thứ hạng tính sẵn trong dbt.
  2. **Độ ổn định cho cả 3 nhịp** (slide 8 yêu cầu 5). Trước đó chỉ tháng 8 có kiểm bỏ từng năm. Model
     `rpt_calendar_stability`, mỗi nhịp hai cách kiểm: tính lại khi bỏ lần lượt từng năm, và đếm số năm tự có nhịp.

     | Nhịp | Cả 10 năm | Bỏ lần lượt từng năm | Số năm tự có nhịp |
     |---|---:|---:|---:|
     | Mùa cao T4–T6, thấp T12–T1 (chênh mùa gộp) | 3,39 lần | 3,22 đến 3,49 lần | 10/10 |
     | Dồn cuối tháng | +7,2 điểm % | +7,1 đến +7,3 điểm % | 10/10 |
     | Tháng 8 năm lẻ thấp | −37,7% | −39,1% đến −36,2% | 10/10 |

     Nhịp có ở từng năm riêng lẻ nên không thể do vài năm bất thường tạo ra. "Giới hạn" ghi rõ: chỉ 10 năm, bỏ một năm mỗi lần,
     chưa đủ coi là quy luật cho các năm sau.
  3. **Chú thích KPI cuối tháng:** ô "?" của thẻ +7,2 điểm % nay ghi mức so sánh "nếu R rải đều theo ngày trong từng tháng, giữ
     nguyên doanh thu mỗi tháng (mỗi tháng (D − 25)/D, cộng lại theo trọng số R tháng)".
  - Test `assert_rpt_calendar_phase`: mỗi năm đúng 1 giai đoạn theo quy ước; chỉ số gộp = cộng các năm, tổng 12; mức dồn giai
    đoạn tính lại qua bảng năm; bỏ-từng-năm của mùa vụ tính lại bằng phép trừ; khóa số hai bảng trên. **Thử làm sai cố ý**
    (tính năm ranh giới cho giai đoạn sau) → FAIL 2 quy tắc (3 năm xếp sai, 4 giai đoạn lệch số). Đã khôi phục.
  - **dbt 192/192 PASS trên cả hai backend** (180 trước đó; thêm 3 model, 9 test). **Test app 96/96 PASS** (85 trước đó).
  - Lúc làm, công cụ chạy lệnh của Claude Code bị lỗi phía máy chủ một lúc; code viết trong lúc đó đã được build và test lại.
- **Sửa thẻ KPI thứ 2 (PM 2026-09-28):** thẻ cũ "Bỏ lần lượt từng năm, chênh tháng 8 vẫn là" hiện một khoảng
  "−39,1% đến −36,2%", quá dài nên bị cắt thành "−39,1% đến …" và khó hiểu. Nay 3 thẻ là 3 nhịp, mỗi thẻ một số ngắn:
  tháng 8 năm lẻ / chẵn −37,7%; **chênh mùa cao / thấp 3,39 lần** (cột `metric_value` dòng `mua_vu` của
  `rpt_calendar_stability`); mức dồn cuối tháng +7,2 điểm %. Khoảng bỏ-từng-năm chuyển vào ô "?" của thẻ và vẫn có đủ trong
  bảng độ ổn định. Test app kiểm nhãn, số, độ dài số (≤ 12 ký tự), và sửa `metric_value` trên bản sao DB thành 9,87 thì thẻ
  ra "9,87 lần". Vẫn **96/96 PASS**.
- **PM hỏi (2026-09-28) "+7,2 điểm %" nghĩa là gì.** Trả lời: 2013–2022, R từ ngày 26 tới cuối tháng chiếm 25,0%; nếu R rải
  đều theo ngày thì chỉ 17,9%; chênh 7,2 **điểm %** (hiệu hai tỷ lệ, không phải "cao hơn 7,2%"). Tính theo ngày, mỗi ngày từ
  26 trở đi bán khoảng 1,4 lần một ngày trung bình (25,0 ÷ 17,9). Thẻ giữ nguyên, ô "?" đã có đủ hai tỷ lệ.
- **PM nghiệm thu M3 ngày 2026-09-29** ("note M3 vô đi, sang qua làm M4"), sau các góp ý ở trên. Quy ước năm ranh giới
  giữ như dev đề xuất; PM chưa có ý kiến riêng về quy ước, nên trang vẫn ghi "chưa được BA chốt". Chuyển sang M4 (PS4 + PS5).
- **Chưa commit.**

### M4: PS4 + PS5 (xong, PM nghiệm thu 2026-09-29)

- **Kết quả theo tiêu chí M4** (đúng trên cả Postgres và DuckDB):
  - PS4, năm 2019: thẻ "Phần do số đơn N" = **−572,4 triệu**. Ba phần cộng lại đúng bằng mức đổi R:
    −572,4 + 2,6 + 14,9 = **−554,9 triệu**. Test app cộng trên cột dbt (không cộng số đã làm tròn), sai số < 0,01.
  - PS5 **không có chỗ nào cộng 3 chiều**. Mỗi lần chỉ xem một chiều (ngành hàng / khu vực / kênh). Test chọn lần lượt cả
    3 chiều: bảng chỉ có đúng các nhóm của chiều đó, không có dòng "Tổng". Số tổng lấy từ `rpt_revenue_yearly`.
  - Câu cảnh báo (plan §3, tiêu chí 4) nằm ở đầu trang: PS4 lấy từ slide 10 ("Thứ tự tách (N → U → P) ảnh hưởng kết quả.
    Đây là phép chia số học, chưa chứng minh nguyên nhân."); PS5 lấy từ slide 12 và ghi chú slide 13 (không cộng giữa các
    chiều; C/F là phép chia số học; region là 3 nhãn mô phỏng; ít khách mua hơn chưa chắc là khách bỏ đi).

  ![M4: trang PS4](screenshots/streamlit/m4_ps4_don_mon_gia_postgres.png)
  ![M4: trang PS5](screenshots/streamlit/m4_ps5_nhom_postgres.png)
- **Trang PS4 gồm:**
  - ô chọn kỳ: 4 giai đoạn PS2 và từng năm 2014–2022 (mặc định 2019);
  - 4 thẻ: R đổi, phần do N, phần do U, phần do P (ô "?" ghi công thức slide 11); câu "kéo lên / kéo xuống nhiều nhất"
    (sửa cách trình bày sau góp ý vòng 1, xem bên dưới);
  - thác R đầu kỳ → N → U → P → R cuối kỳ, kèm bảng số đầy đủ (cột U, P nhỏ so với R nên khó thấy trên hình);
  - **so sánh giữa các năm** (deck slide 10 yêu cầu 5): cột chồng ba phần mỗi năm, hình thoi = mức đổi R; bảng theo năm;
  - **so sánh giữa các giai đoạn**: bảng và nhận xét ghép từ cột;
  - bảng N, U, P, AOV và tăng trưởng theo năm (yêu cầu 1–2; N × U × P = R đã kiểm trong `assert_rpt_reconciles`).
- **Trang PS5 gồm:**
  - chọn một chiều và một năm (mặc định ngành hàng, 2019);
  - 3 thẻ: R cả công ty đổi, nhóm tăng nhiều nhất, nhóm giảm nhiều nhất ("Không có" nếu không nhóm nào tăng / giảm);
  - biểu đồ và bảng xếp hạng nhóm: R hai năm, số tiền đổi, % đổi, tỷ trọng, dịch chuyển tỷ trọng, % đóng góp;
  - nhận xét ghép từ cột, kèm cách đọc: % đóng góp lớn mà tỷ trọng gần như không đổi nghĩa là nhóm đổi cùng nhịp cả công ty;
  - đường tỷ trọng các nhóm qua 10 năm;
  - phần C/F: 3 thẻ, thác N đầu → C → F → N cuối, bảng theo năm.
- **dbt thêm:**
  - seed `driver_rule` (ngưỡng "mức đổi R nhỏ", xem quyết định 2 bên dưới);
  - `rpt_driver_period`: 1 dòng = 1 năm hoặc 1 giai đoạn, gồm phần góp N/U/P, C/F, phần kéo lên / kéo xuống nhiều nhất,
    cờ mức đổi nhỏ;
  - `rpt_driver_bridge`: thác dạng dài như `rpt_revenue_bridge` của PS1, app chỉ vẽ;
  - `rpt_revenue_segment_yearly` thêm `delta_r_rank`, `delta_r_is_small`, `n_groups`, `n_groups_up`, `n_groups_down` (câu
    "Số nhóm giảm: 4/4" trên PS5 đọc từ cột, app không tự đếm);
  - test `assert_rpt_driver`: dòng năm khớp `rpt_revenue_yearly`; dòng giai đoạn = cộng các năm và khớp mức đổi R của
    `rpt_revenue_phase`; mọi kỳ N + U + P = ΔR, C + F = ΔN; phần kéo lên/xuống tính lại bằng xếp hạng; cờ nhỏ tính lại;
    thác nối tiếp đúng; hạng PS5 đúng thứ tự; số nhóm tăng/giảm đếm lại bằng group by; khóa số ngày 2026-09-29 (gồm
    2019 cả 4 ngành hàng đều giảm).
  - **Thử làm sai cố ý**, 3 lần, mỗi lần đều đã khôi phục:
    - 2 chỗ cùng lúc: xếp năm vào giai đoạn theo quy tắc sai (đầu ≤ Y < cuối) và nối sai cột U của thác → FAIL 6 quy tắc;
    - riêng cột U của thác nối sai → FAIL đúng quy tắc thác (26 dòng);
    - riêng hạng PS5 xếp ngược chiều → FAIL quy tắc hạng (90 dòng) và số khóa Streetwear.
    Sau khi khôi phục, dbt build lại PASS toàn bộ trên cả hai backend.
- **Kết quả theo giai đoạn** (triệu):

  | Giai đoạn | R đổi | Phần N | Phần U | Phần P | Kéo lên nhiều nhất | Kéo xuống nhiều nhất |
  |---|---:|---:|---:|---:|---|---|
  | A 2013→2016 | +360,3 | +94,0 | −35,2 | +301,6 | P | U |
  | B 2016→2018 | −200,2 | −249,9 | −36,7 | +86,4 | P | N |
  | C 2018→2019 | −554,9 | −572,4 | +2,6 | +14,9 | P | N |
  | D 2019→2022 | −3,7 | −145,8 | −18,3 | +160,3 | P | N |

  Đọc: tính cả giai đoạn, giá mỗi món P kéo lên ở cả 4 giai đoạn (theo năm thì 2015, 2017, 2021 P giảm). Số đơn N kéo xuống
  ở B, C, D. D gần như đi ngang vì N giảm và P tăng bù nhau. Đây là phép chia số học, chưa phải nguyên nhân.
  PS5 năm 2019: cả 4 ngành hàng đều giảm; C/F: số đơn giảm 22.481, trong đó 16.578 do số khách, 5.903 do tần suất.
- **3 chỗ dev tự quyết, chờ PM/BA chốt:**
  1. **Phần góp của giai đoạn = cộng phần góp từng năm** (năm Y tính cho giai đoạn có đầu < Y ≤ cuối). Tổng các năm đúng bằng
     mức đổi R giai đoạn ở PS2, nên đây không phải quy ước chia năm mới như PS3. Cách khác là tách thẳng một lần từ năm đầu tới
     năm cuối: đã so, mỗi phần lệch tối đa 3,2 triệu (phần N giai đoạn B) và cùng phần kéo lên / kéo xuống ở cả 4 giai đoạn.
     Test khóa điều này (lệch < 5 triệu, cùng kết luận).
  2. **Ngưỡng "mức đổi R nhỏ" = 1% R đầu kỳ** (seed `driver_rule`). Deck chỉ nói "khi ΔR gần 0 ưu tiên số tiền", không có
     số. Với 1%, chỉ năm 2015 (+2,9 triệu, 0,2% R 2014) và giai đoạn D (−3,7 triệu, 0,4% R 2019) bị đánh dấu. Khi đó PS5
     vẫn hiện % đóng góp nhưng ghi "(không ổn định)".
  3. Quy ước năm ranh giới của PS3 (từ M3), vẫn chưa chốt.
- **dbt 202/202 PASS trên cả hai backend** (192 trước đó; thêm 1 seed, 2 model, 7 test). **Test app 121/121 PASS** (96
  trước đó). Test mới trong `test_m4.py` và `test_khong_hardcode.py` (sửa phần góp N và tên nhóm trên bản sao DB thì
  trang đổi theo). Test "trang chưa làm" của M1 chuyển sang trang Sức khỏe dữ liệu, vì PS4 không còn là trang chờ.
- **Việc PM cần làm để nghiệm thu M4:** mở app, xem trang PS4 và PS5; chốt 3 chỗ ở trên.
- **Góp ý vòng 1 của PM (2026-09-29): 4 thẻ PS4 khó hiểu, số khó nhìn.**
  - Lỗi: số "−554,9 triệu" và nhãn "Phần do số món mỗi …" bị cắt ở màn hình của PM. Thẻ chỉ ghi số tiền, không nói yếu tố đó
    tự đổi bao nhiêu, nên khó hiểu "phần do số đơn −572,4 triệu" là gì. Test cũ chỉ đếm ≤ 13 ký tự nên không bắt được.
  - **Cách đọc 4 thẻ (năm 2019):** số đơn giảm 40,3% (55.740 → 33.259). Nếu số món mỗi đơn và giá mỗi món giữ như 2018 thì
    riêng việc đó làm doanh thu giảm 572,4 triệu. Số món mỗi đơn (+0,3%) và giá mỗi món (+1,8%) tăng nhẹ, bù lại
    2,6 + 14,9 = 17,5 triệu. Cộng lại: −572,4 + 2,6 + 14,9 = −554,9 triệu = doanh thu giảm (−39,1%).
  - **Sửa:**
    - số lớn vẫn là số tiền (vì 3 thẻ N + U + P cộng đúng bằng thẻ Doanh thu), bỏ chữ "triệu" khỏi từng thẻ, ghi một lần ở
      dòng trên: "2018 → 2019: doanh thu đổi bao nhiêu, do đâu (số lớn: triệu)"; nhãn ngắn: "Doanh thu R", "Do số đơn N",
      "Do số món/đơn U", "Do giá/món P";
    - dòng màu nhỏ dưới số: % đổi của chính yếu tố đó và giá trị đầu → cuối (vd. "−40,3%  55.740 → 33.259 đơn"). Đỏ = giảm,
      xanh = tăng. Màu lấy từ số thật, vì Streamlit chỉ coi dấu "-" thường là âm, còn app in dấu "−";
    - dòng "Cách đọc thẻ" nói rõ: ba thẻ N + U + P cộng lại bằng thẻ Doanh thu; **các % không cộng lại được**
      (−40,3% + 0,3% + 1,8% ≠ −39,1%);
    - câu tóm tắt nói phần lớn hơn trước và có cả % lẫn tiền: "doanh thu giảm 554,9 triệu (−39,1%); kéo xuống nhiều nhất là
      số đơn N (giảm 40,3%, làm R −572,4 triệu); kéo lên nhiều nhất là giá mỗi món P (tăng 1,8%, làm R +14,9 triệu)".
      Nhận xét so sánh giai đoạn dùng cùng câu này;
    - giai đoạn: số lớn là cộng từng năm, còn dòng % so thẳng năm cuối với năm đầu (vd. A: số đơn 61.588 → 66.067, +7,3%);
      trang ghi rõ điều này.
  - **dbt:** `rpt_driver_period` thêm `u_start`, `u_end`, `p_start`, `p_end`, `r_change_rate`, `n_change_rate`,
    `u_change_rate`, `p_change_rate` (app không tự chia). `assert_rpt_driver` thêm 2 quy tắc: dòng năm khớp `yoy_*` của
    `rpt_revenue_yearly`, mọi kỳ = năm cuối / năm đầu − 1; khóa số 2019 (R −39,10%, N −40,33%, U +0,305%, P +1,75%) và
    giai đoạn A (N 61.588 → 66.067). Thử làm sai cố ý (% đổi P lệch 0,1 điểm %) → FAIL cả 2 quy tắc (13 dòng + khóa số);
    đã khôi phục, build lại PASS.
  - **Kiểm:** chụp ảnh ở khung rộng 1600 px như màn hình PM: số và nhãn không còn bị cắt (ảnh PS4 ở trên đã chụp lại).
    Test app khóa cả số lớn, dòng %, dòng đầu → cuối, câu tóm tắt; giới hạn số ≤ 8 ký tự, nhãn ≤ 16 ký tự.
    `test_khong_hardcode` sửa thêm `n_change_rate` trên bản sao DB thì dòng % đổi theo. 3 thẻ đầu trang PS5 đã chụp
    kiểm, không bị cắt nên giữ nguyên.
  - dbt vẫn **202/202** trên cả hai backend (thêm quy tắc trong test có sẵn, không thêm test mới); test app **121/121**.
- **PM nghiệm thu M4 ngày 2026-09-29** ("M4 nghiệm thu rồi, làm M5 đi"), sau góp ý vòng 1. PM chưa có ý kiến về 3 chỗ dev
  tự quyết ở trên (phần góp giai đoạn = cộng từng năm, ngưỡng 1%, năm ranh giới PS3), nên cả 3 vẫn ghi "chờ PM/BA chốt".
  Phần thẻ C/F cuối trang PS5 giữ nguyên (dev mới đề nghị sửa theo cách của PS4, PM chưa yêu cầu). Chuyển sang M5.
- **Chưa commit.**

### M5: Sức khỏe dữ liệu + hoàn thiện (dev xong 2026-09-29, chờ PM nghiệm thu)

- **Trả lời câu hỏi:** "Số trên app có đáng tin không?" Trang **Sức khỏe dữ liệu** gồm:
  - khung trạng thái chung: xanh "Kho đạt" / đỏ (test không đạt, model dựng lỗi) / vàng (kết quả test đã cũ, chỉ kiểm một
    phần, nguồn nạp mới hơn kho, chưa có kết quả). Khung nào cũng ghi lý do và lệnh cần chạy;
  - 4 thẻ: số test đạt (vd. 158/158), số test không đạt, lúc kiểm, dữ liệu tới ngày;
  - **kết quả từng test** của lần kiểm gần nhất: 22 test nghiệp vụ có mô tả tiếng Việt (vd. "Doanh thu và giá vốn theo ngày
    dựng lại từ giao dịch khớp chính xác sales.csv, đủ 3.833 ngày"), 136 test ràng buộc cột trong ô mở rộng. Test không đạt
    xếp lên đầu, tô đỏ, kèm số dòng lệch và thông báo của dbt;
  - **lần nạp nguồn gần nhất** (Postgres): 14 file, số dòng, thời gian nạp, mã MD5. DuckDB không có bước nạp (dbt đọc thẳng
    CSV) nên trang ghi rõ điều đó thay vì báo lỗi;
  - 10 lần chạy dbt gần nhất trên kho đang đọc.

  ![M5: Sức khỏe dữ liệu, Postgres](screenshots/streamlit/m5_suc_khoe_du_lieu_postgres.png)
  ![M5: Sức khỏe dữ liệu, DuckDB](screenshots/streamlit/m5_suc_khoe_du_lieu_duckdb.png)
  ![M5: ví dụ khi có test không đạt (bản sao DuckDB, sửa cố ý)](screenshots/streamlit/m5_suc_khoe_du_lieu_vi_du_test_loi.png)
- **Đổi so với plan:** plan ghi đọc `retail_dbt/target/run_results.json`. Không dùng, vì file đó chỉ có một bản, lần build sau
  ghi đè: build DuckDB sau Postgres thì trang Postgres sẽ hiện kết quả test của DuckDB. Thay bằng **nhật ký trong chính kho**:
  hook `on-run-start` / `on-run-end` của dbt (`retail_dbt/macros/health_log.sql`) ghi mỗi lần chạy vào schema `ops`
  (`dbt_invocation`, `dbt_node_result`). Mỗi backend có kết quả riêng. Thiết kế để mang sang Snowflake ở GĐ 3, **chưa chạy thử**. Hook vẫn ghi khi
  build có test FAIL (đã thử bằng một test cố ý FAIL). Phần sửa này đã ghi vào `gd2_app_plan.md` §4.
- **dbt thêm:**
  - 4 view: `rpt_health_run` (1 dòng/lần chạy: số test đạt/không đạt, model lỗi), `rpt_health_test` (từng test của lần kiểm
    gần nhất, nhóm nghiệp vụ/ràng buộc, tầng), `rpt_health_ingest` (log nạp gần nhất; rỗng trên DuckDB),
    `rpt_health_summary` (1 dòng, `status_code`). Là view nên luôn đọc log mới nhất. App chỉ đổi mã trạng thái sang câu chữ;
    việc đếm, so thời điểm, chọn trạng thái nằm trong dbt;
  - `tests/_singular_tests.yml`: mô tả 1 dòng cho 22 test nghiệp vụ (thêm test mới thì thêm mô tả ở đây);
  - test `assert_rpt_health`: số đếm đếm lại độc lập; tóm tắt lấy đúng lần kiểm gần nhất; trạng thái khớp các cờ; Postgres:
    đủ 14 nguồn cùng 1 lần nạp, **số dòng trong log = số dòng bảng `raw` thật**; DuckDB: không có log.
  - **Thử làm sai cố ý**, 3 lần, mỗi lần đã khôi phục: đếm nhầm test đạt thành không đạt → FAIL 2 quy tắc; tóm tắt lấy lần kiểm
    cũ nhất → FAIL "đúng lần kiểm gần nhất" và "số dòng = số test"; log nạp lệch 1 dòng ở `sales` (Postgres) → FAIL "số dòng
    trong log = số dòng bảng raw". Sau đó xóa nhật ký thử nghiệm (schema `ops`, `dbt_test__audit`) và build lại cả hai
    backend, nên lịch sử trên trang chỉ gồm các lần build sạch.
- **Hoàn thiện chung (mọi trang):** bảng `rpt_*` rỗng (vd. kho đang dựng dở) thì trang hiện cảnh báo vàng kèm tên bảng và
  cách xử lý, không vẽ số, không văng lỗi. Số trống vẫn hiện "–".
- **Kiểm:**
  - dbt **216/216 PASS trên cả hai backend** (53 model + 3 seed + 158 test + 2 hook; trước đó 202).
  - Test app **134/134 PASS** (121 trước đó). Smoke test 7/7 trang × 2 backend (tiêu chí M5) nay chạy trên trang thật.
    `test_m5.py` (9 test): trạng thái thật sau build là "Kho đạt" trên cả hai backend, đủ 22 test nghiệp vụ có mô tả; Postgres
    số dòng `orders.csv`, `order_items.csv` khớp bảng raw; DuckDB báo không có log, không lỗi. Trên bản sao DuckDB sửa cố ý:
    1 test FAIL → khung đỏ, test đó lên đầu; lùi giờ kiểm → "có thể đã cũ"; xóa bớt test → "chỉ chạy một phần"; xóa nhật ký →
    "chưa có kết quả"; xóa `rpt_revenue_yearly` → trang Tổng quan cảnh báo bảng rỗng. `test_backends` khai báo 4 view mới là
    **cố ý khác nhau giữa hai backend** (nhật ký riêng), không so.
  - Chụp ảnh ở khung 1600 px: bảng test nghiệp vụ dùng dạng bảng tĩnh để mô tả dài tự xuống dòng (bản đầu bị cắt chữ).
- **Cách mở app:** §8.1 đã có từ trước; thêm dòng "trước khi demo, mở trang Sức khỏe dữ liệu, phải thấy khung xanh".
- **Lưu ý:**
  - Test trong một lần `dbt build` kiểm nhật ký của các lần chạy **trước** (hook ghi sau khi build xong); nhật ký của chính
    lần build đó được `test_m5.py` kiểm sau build.
  - Trên Postgres, dựng lại riêng một view/bảng cha (vd. `dbt build -s rpt_build_info`) sẽ xóa luôn view phụ thuộc
    (`rpt_health_summary`) tới lần build đầy đủ kế tiếp; trang khi đó báo không đọc được bảng. Build đầy đủ thì không sao.
  - Chưa kiểm trên app trạng thái "nguồn mới hơn kho" (phải nạp lại raw thật); quy tắc này có trong `assert_rpt_health`.
- **Chưa làm:** vòng xoay "đang tải" (bảng nhỏ, có cache nên chưa cần); ô không áp dụng vẫn hiện "–" như các mốc trước.
  Sang Snowflake (GĐ 3) còn phải xử lý log nạp: hiện mọi target không phải Postgres đều bị coi là "đọc thẳng CSV" như
  DuckDB, trong khi Snowflake nạp bằng COPY INTO.
- **Review ngoài (GPT, 2026-09-29), 2 ý:**
  - [P2] "App văng lỗi khi bảng reporting rỗng" (Tổng quan, PS4, PS5). Tái hiện đúng 3 ca đó trên code hiện tại: cả 3
    đều hiện cảnh báo vàng, không lỗi. Review có vẻ chạy trên bản trước M5, vì phần chặn bảng rỗng ở trên được thêm trong
    M5. Đã khóa bằng `test_moi_bang_trang_doc_ma_rong_thi_khong_van_loi` (`test_m5.py`): với 7 trang, lấy danh sách bảng
    trang thật sự đọc, rồi cho **từng bảng** trả về 0 dòng. Mỗi ca phải không lỗi, có cảnh báo nêu đúng tên bảng, và không vẽ
    thẻ/bảng số. Ngoại lệ là 3 bảng được phép rỗng của trang Sức khỏe: ở đó chỉ kiểm không lỗi.
  - [P3] Phần C/F cuối trang PS5 là số **toàn công ty**, không theo chiều đang chọn ở trên, nhưng chưa ghi rõ. Đã sửa:
    - tiêu đề thành "Số đơn toàn công ty, năm …: đổi vì số khách (C) hay vì tần suất mua (F)?";
    - thêm dòng chú thích "không chia theo {chiều} đang chọn";
    - thẻ đầu thành "Số đơn toàn công ty đổi (…→…)".
    
    Số liệu không đổi. `test_ps5_c_f_2019` kiểm cả 3 nhãn.
  - Test app sau khi sửa: **141/141 PASS** (134 + 7 trang của test mới).
  - **Làm tiếp (PM yêu cầu 2026-09-30): bảng có dòng nhưng lệch nhau.** Chặn bảng rỗng ở trên chưa phủ trường hợp này.
    Ví dụ: PS5 có năm 2019 trong `rpt_revenue_segment_yearly` nhưng `rpt_driver_period` lại thiếu năm 2019. Test
    `test_bang_lech_nhau_thi_khong_van_loi` thử 3 kiểu lệch với từng bảng của 7 trang: bỏ dòng đầu, bỏ dòng cuối, chỉ giữ
    dòng đầu.
    - **Bản cũ văng lỗi ở 5 trang:**
      - Tổng quan: `total.loc['2012-2022']`;
      - PS1: chọn kỳ;
      - PS2: tên giai đoạn, dòng R 12 tháng đầu tiên, khoảng so chính;
      - PS3: kỳ phân tích, nhãn giai đoạn cạnh năm, nhịp mùa vụ;
      - PS5: năm đang chọn ở `rpt_revenue_yearly`, `rpt_driver_period`, bảng C/F.
    - **Cách sửa:** thêm 3 hàm chặn chung ở `ui/common.py`: `need` (phần đã lọc phải có dòng), `pick` (lấy 1 dòng theo
      khóa) và `need_keys` (khóa của bảng này phải có ở bảng kia). Thiếu dòng thì trang dừng và hiện cảnh báo vàng: bảng nào,
      thiếu dòng gì, cách xử lý (xem trang Sức khỏe dữ liệu, chạy `dbt build` đầy đủ, bấm Đọc lại). Thác N/U/P ở PS4 và thác
      C/F ở PS5 thiếu dòng cũng báo như vậy, không vẽ biểu đồ rỗng.
    - Tổng quan nay chọn kỳ toàn bộ dữ liệu theo cột `is_analysis_period`, không gõ cứng `'2012-2022'` nữa.
    - Bình thường dbt giữ các bảng khớp nhau (`assert_rpt_*`), nên cảnh báo này không hiện.
    - **Kiểm:**
      - `test_bang_lech_thi_bao_ro_bang_nao_thieu_gi` (4 ca) kiểm cảnh báo nêu đúng tên bảng và dòng thiếu;
      - test app **152/152 PASS**, thời gian chạy tăng từ khoảng 4 lên khoảng 7,5 phút vì phép thử bảng lệch chạy khoảng
        120 lượt trang.
- **Việc PM cần làm để nghiệm thu M5:** mở app, xem trang Sức khỏe dữ liệu trên cả hai nguồn (đổi ở thanh bên).
- **Chưa commit.**

### 2026-10-01: Sửa thẻ và bảng nhiệt PS2–PS5 theo feedback (dev xong, chờ PM xem)

- **Nguồn:** `docs/streamlit_ps1_ps5_ui_feedback.md`, checklist F01–F04. Chỉ đổi cách trình bày: không sửa model dbt, mọi số
  vẫn đọc từ `reporting.rpt_*`, số liệu không đổi.
- **F01, PS4:**
  - thẻ đầu đổi nhãn "Doanh thu R" → **"Thay đổi R"**. Số lớn của thẻ này là mức đổi (−554,9), không phải mức doanh thu;
  - dòng ngay trên hàng thẻ ghi đơn vị và kỳ: "Số lớn: **triệu**, mức đổi 2018 → 2019. Dòng màu: % đổi của **chính yếu tố**
    ghi ở dòng dưới";
  - dòng xám dưới số ghi tên yếu tố: "R: 1.419,3 → 864,3 triệu", "N: 55.740 → 33.259 đơn", "U: …", "P: …";
  - dòng "Cách đọc thẻ" nói rõ: ba thẻ N + U + P cộng lại bằng thẻ Thay đổi R, còn các % không cộng lại thành % đổi của R.
    Câu giải thích riêng cho kỳ giai đoạn giữ nguyên.
- **F02, PS2:**
  - dòng trên hàng thẻ: "**CAGR: tăng trưởng trung bình mỗi năm của R** (số lớn, **%/năm**). Dòng màu: **tổng thay đổi** của R
    cả giai đoạn";
  - mỗi thẻ thêm dòng màu: tổng thay đổi lấy từ `total_change_rate`, kèm khoảng năm. Ví dụ A: số lớn +8,75%, dòng màu
    "+28,6% tổng 2013→2016";
  - nhãn thẻ chỉ giữ tên giai đoạn ("A. Tăng trưởng"). Khoảng năm chuyển xuống dòng màu, vì ở khổ 1280 px có mở sidebar,
    nhãn cũ "A. Tăng trưởng (2013→2016)" bị cắt mất phần năm (lỗi này có từ trước đợt feedback).
- **F03, PS5:** hai thẻ "… tăng/giảm nhiều nhất" hiện thêm số tiền (dòng màu) và % đóng góp (dòng xám).
  - Ví dụ 2019, ngành hàng: "Streetwear", "−463,9 triệu", "83,6% tổng mức giảm".
  - % giữ dấu, không ép về 0–100%. Ví dụ 2021, ngành hàng: Casual "+6,2 triệu · −15,3% tổng mức giảm", vì Casual tăng trong
    khi cả công ty giảm.
  - Năm có ΔR cả công ty dưới 1% (vd. 2015): thẻ vẫn hiện số tiền nhưng ghi "% góp không ổn định", không đưa % kiểu 400% lên
    thẻ.
  - ΔR cả công ty = 0 (dbt trả `contribution_to_delta` NULL): ghi "% góp không xác định". Trường hợp này dữ liệu thật không
    có; test giả lập bằng cách sửa bảng trong bộ nhớ.
  - Không có nhóm tăng/giảm thì thẻ vẫn ghi "Không có", không mượn số của nhóm giảm ít nhất.
  - Phần C/F bên dưới vẫn ghi rõ **toàn công ty**.
- **F04, PS3:** bảng nhiệt chỉ số tháng theo năm và theo giai đoạn nay **dùng chung một thang màu**, nên cùng giá trị thì cùng
  màu.
  - Miền màu đối xứng quanh 1, lấy từ cực trị của cả hai bảng (hiện là 0,23–1,77), nên không ô nào bị bão hòa màu.
  - Hai bảng có chú giải màu, ghi mẫu số riêng: "1 = TB tháng của năm đó" và "1 = TB tháng của giai đoạn đó".
  - Ngưỡng chữ trắng/đen trong ô tính theo cùng thang.
  - Bảng mức dồn cuối tháng giữ thang riêng, tâm 0, có thêm chú giải theo điểm %.
- **Không làm các đề xuất tùy chọn (§4 file feedback):** file ghi rõ chỉ cân nhắc sau checklist chính, và tránh làm trang dài
  thêm khi chưa có lợi ích rõ. PM muốn làm mục nào thì báo.
- **Kiểm:**
  - test mới:
    - PS2: dòng màu = `total_change_rate`;
    - PS5: thẻ đổi theo năm × chiều (2019/2021/2022 × 3 chiều), % âm, năm 2015 không ổn định, mẫu số 0;
    - PS3: đọc spec biểu đồ, kiểm hai bảng cùng thang màu và miền màu phủ đủ cực trị.

    Test cũ đổi nhãn theo, vẫn giữ kiểm số.
  - Lần chạy ngày 2026-10-01 **chỉ trên DuckDB**:
    - chạy cả bộ sau khi sửa F01–F04: 102 test không cần Postgres đều PASS;
    - sau đó dev rút gọn chữ trên thẻ PS2/PS5 cho vừa khổ 1280 px rồi chạy lại. Lần này máy thiếu bộ nhớ nên Claude Code
      dừng giữa chừng: 61 test đầu PASS, không test nào lỗi, phần còn lại **chưa chạy xong**;
    - **cần chạy lại cả bộ** trước khi nghiệm thu.
  - **Chưa kiểm trên Postgres:** Docker Desktop đang lỗi (API trả lỗi 500), nên 55 test cần Postgres đều báo
    "connection failed" tới `localhost:5433`. Đó là lỗi kết nối, không ghi là PASS. Bật lại Docker rồi chạy lại cả bộ, kỳ vọng
    `157 passed`.
  - Ảnh (DuckDB, chụp bằng Edge headless, có mở sidebar):

    ![PS2: thẻ CAGR, 1280 px](screenshots/streamlit/fb1001_ps2_the_cagr_duckdb_1280.png)
    ![PS4: năm 2019, 1280 px](screenshots/streamlit/fb1001_ps4_the_2019_duckdb_1280.png)
    ![PS4: năm 2019, 1600 px](screenshots/streamlit/fb1001_ps4_the_2019_duckdb_1600.png)
    ![PS5: ngành hàng 2019, 1280 px](screenshots/streamlit/fb1001_ps5_the_nhom_2019_nganh_hang_duckdb_1280.png)
    ![PS3: hai bảng nhiệt chung thang màu, 1280 px](screenshots/streamlit/fb1001_ps3_hai_bang_nhiet_chung_thang_mau_duckdb_1280.png)
- **Giới hạn còn lại:**
  - Ở 1280 px có mở sidebar, dòng xám "đầu → cuối" dưới 4 thẻ PS4 bị cắt cuối dòng bằng dấu "…". Tên yếu tố (R/N/U/P), số
    lớn và % vẫn đọc đủ. Ở 1600 px (màn hình demo) dòng hiện đủ.
  - PS4 chọn giai đoạn mới kiểm bằng AppTest (`test_ps4_chon_giai_doan`), chưa chụp ảnh.
  - Trên PS5, thẻ "Không có" thấp hơn thẻ có số tiền một dòng.
- **Chưa commit.**

### 2026-10-02: Làm tròn số tiền khi hiển thị, thêm đơn vị cho thẻ PS4 (dev xong, chờ PM xem)

- **Nguồn:** góp ý PM ngày 2026-10-02. Khi hiển thị nên làm tròn còn 2–3 chữ số, số doanh thu ở PS1 quá dài nên khó nhìn, và
  thẻ PS4 chỉ có số mà không có đơn vị. Chỉ đổi cách trình bày: không sửa model dbt, số liệu không đổi.
- **Quy ước mới (mọi trang):**
  - mức tiền của năm hoặc cả kỳ (thẻ, bảng theo năm) ghi theo **tỷ, 2 số lẻ**, ví dụ G 2012–2022 = **16,43 tỷ**,
    R 2019 = 0,86 tỷ;
  - mức tiền theo tháng, các phần của **một** năm (thác PS1 khi chọn một năm) và mức **thay đổi** ghi theo **triệu, 1 số lẻ**,
    ví dụ −572,4 triệu;
  - mỗi cột và mỗi biểu đồ chỉ dùng một đơn vị, không tự đổi đơn vị theo từng số;
  - **số đầy đủ** (2 chữ số thập phân) vẫn xem được để đối chiếu:
    - thẻ G, R: rê chuột vào dấu (?) ("Số đầy đủ: 16.430.476.585,53");
    - biểu đồ: rê chuột lên cột hoặc đường;
  - số đơn, số khách, tỷ lệ, chỉ số giữ nguyên, vì đã ngắn.
- **PS1 và Tổng quan:**
  - thẻ G, R ghi theo tỷ;
  - thác G → R (nhãn cột và bảng):
    - kỳ nhiều năm ghi theo tỷ;
    - chọn một năm thì ghi theo triệu. Lý do: các phần bị trừ của một năm chỉ vài chục triệu, ghi theo tỷ chỉ còn 1 chữ số
      (2019: "−0,04 tỷ"). Hai khoản khác nhau (đơn trả 61,3 triệu, đơn chưa giao 60,9 triệu) cùng hiện "−0,06 tỷ", và số
      trên cột cộng lại thành 0,87 trong khi R = 0,86;
    - 2019 nay ghi: 1.136,8 / −106,2 / −61,3 / −60,9 / −44,1 / 864,3 triệu;
  - bảng 12 tháng (khi chọn một năm) ghi theo triệu;
  - bảng theo năm ghi theo tỷ.

  Ghi chú "bốn phần cộng lại đúng bằng G − R" có thêm câu: số trên bảng đã làm tròn nên cộng lại có thể lệch ở chữ số cuối.
- **PS2:**
  - bảng "Dữ liệu tự tìm", bảng giai đoạn và bảng điểm đổi hướng: mức R theo tỷ;
  - cột "Chênh R" theo triệu, cùng số với PS4 (giai đoạn D: −3,7 triệu).
- **PS4:**
  - bốn thẻ nay **có đơn vị**: "Thay đổi R **−554,9 triệu**", "Do số đơn N **−572,4 triệu**", "+2,6 triệu", "+14,9 triệu";
  - bỏ câu "Số lớn: **triệu**" ở dòng trên thẻ vì đơn vị đã nằm trên thẻ;
  - **4 thẻ vẫn nằm một hàng.** Bản đầu đưa thẻ Thay đổi R lên hàng riêng, ba thẻ kia xuống dưới. PM xem ảnh và thấy không
    đẹp, nên đã bỏ cách đó;
  - **các thẻ đều nhau** (hàm dùng chung `hang_the` trong `ui/common.py`, CSS chỉ áp trong khối thẻ của trang, không ảnh hưởng
    thẻ khác):
    - mọi thẻ cùng khuôn: nhãn / số lớn / ô màu % / dòng xám, mỗi phần một dòng. Trước đây dòng xám ngắn thì nằm cạnh ô %,
      dài thì bị đẩy xuống, nên các thẻ lệch nhau (ảnh PM lúc 22:56);
    - các thẻ cao bằng thẻ cao nhất;
    - cỡ chữ số lớn bằng 11% bề rộng thẻ (CSS container query), tối đa bằng cỡ mặc định. Màn rộng thì số vẫn to; ở 1280 px
      có mở sidebar thì số nhỏ lại vừa thẻ, không bị cắt. Trước đây (ảnh PM ngày 2026-09-29) số dài 12 ký tự bị cắt;
    - dòng xám dài thì xuống dòng thay vì bị cắt "…". Giới hạn ghi ở mục 2026-10-01 nay đã hết;
  - đã thử đặt ô % cùng hàng với số lớn. Cách này bị PM gạt: giữ khuôn ban đầu (ô % dưới số), chỉ cần các thẻ đều nhau;
  - dòng xám của thẻ R gọn hơn: "R: 1.419 → 864 triệu" (trước là "1.419,3 → 864,3 triệu");
  - bảng thác ghi theo triệu, cùng số với nhãn trên cột;
  - "Cách đọc thẻ" nói rõ: ba thẻ N + U + P cộng lại bằng thẻ Thay đổi R, nhưng số đã làm tròn có thể lệch 0,1 triệu. Số gốc
    khớp chính xác, kiểm bằng dbt test `assert_rpt_decomposition_additive`.
- **PS5, ba thẻ đầu trang** (góp ý PM ngày 2026-10-02: ba thẻ không đều, khó hiểu số nói lên điều gì):
  - dùng cùng hàm `hang_the`, nên ba thẻ cao bằng nhau và cùng khuôn;
  - thẻ "R cả công ty đổi" có thêm ô % đổi của R (cột `yoy_rate`, 2019: −39,1%) và dòng "R: 1.419 → 864 triệu";
  - thẻ "Không có" (không nhóm nào tăng/giảm) có ô xám ghi số nhóm (cột `n_groups_up` / `n_groups_down` / `n_groups`, vd.
    "0/4 nhóm tăng") và dòng "Mọi ngành hàng đều giảm". Thẻ vẫn không mượn số tiền của nhóm giảm ít nhất;
  - thêm câu dẫn trên hàng thẻ: "**2018 → 2019: R cả công ty đổi bao nhiêu, ngành hàng nào kéo nhiều nhất.** Dòng màu: số tiền
    đổi (thẻ đầu: % đổi của R). Dòng xám: nhóm chiếm bao nhiêu % tổng mức giảm của cả công ty."
- **Tiêu chí M1 vẫn kiểm được:** test so thẻ với số gọn (16,43 tỷ; 12,52 tỷ), **và** so tooltip của thẻ với số đầy đủ của deck
  (16.430.476.585,53; 12.518.175.957,20). Test "sửa số trong DB thì app đổi theo" kiểm cả số gọn lẫn số đầy đủ trong tooltip.
- **Kiểm (ngày 2026-10-02, Postgres đã chạy lại):**
  - bốn file test bị ảnh hưởng (`test_m1`, `test_m2`, `test_m4`, `test_khong_hardcode`), phần không cần Postgres: 35 PASS;
  - `test_m1`, `test_m2`, `test_m4` phần Postgres: 18 PASS;
  - các file không đổi (`test_m3`, `test_m5`, `test_smoke`, `test_backends`, cùng `test_khong_hardcode`), phần không cần
    Postgres, chạy trước khi sửa thác PS1 một năm: 93 PASS;
  - không thêm hàm test mới, chỉ sửa và thêm điều kiện kiểm, nên tổng vẫn kỳ vọng `157 passed`;
  - **chưa chạy lại cả bộ một lượt.** Máy hay thiếu bộ nhớ nên lần này chỉ chạy từng phần.
- **Ảnh** (Postgres, năm 2019, có mở sidebar, chụp bằng Edge headless). App PM đang chạy không nạp lại `ui/common.py` đã sửa,
  vì Streamlit không nạp lại module đã import. Nên dev bật tạm một app phụ ở cổng 8502 để chụp, chụp xong tắt ngay:

  ![PS4: 4 thẻ đều nhau, 1280 px](screenshots/streamlit/fb1002_ps4_the_2019_postgres_1280.png)
  ![PS4: 4 thẻ đều nhau, 1600 px](screenshots/streamlit/fb1002_ps4_the_2019_postgres_1600.png)
  ![PS5: 3 thẻ đều nhau, ngành hàng 2019, 1280 px](screenshots/streamlit/fb1002_ps5_the_2019_nganh_hang_postgres_1280.png)
  ![PS5: 3 thẻ đều nhau, ngành hàng 2019, 1600 px](screenshots/streamlit/fb1002_ps5_the_2019_nganh_hang_postgres_1600.png)

  Sau khi sửa thẻ, `test_m1`, `test_m4`, `test_khong_hardcode` chạy lại trên cả hai backend: 43 PASS. Test PS5 kiểm thêm ô %
  và dòng xám của thẻ đầu, ô "0/4 nhóm tăng" của thẻ "Không có" (đếm từ cột dbt), và câu dẫn.
- **Chưa commit.**

### 2026-10-02: Sửa lỗi deadlock khi `dbt build` trên Postgres (dev xong)

- **Hiện tượng:** PM chạy `dbt build` lúc 23:17 và nhận `PASS=205 ERROR=1 SKIP=10`. Model `rpt_health_run` lỗi "deadlock detected".
- **Nguyên nhân** (log Postgres, `docker logs retail_dwh`, 16:17:31 UTC):
  - view `rpt_health_summary` đọc ba model cha: `rpt_build_info`, `rpt_health_run`, `rpt_health_ingest`;
  - trên Postgres, mỗi lần dựng lại một cha, dbt chạy `drop … __dbt_backup cascade`. Lệnh này phải khóa cả view con chung;
  - dbt chạy 4 luồng, và lần này hai cha (`rpt_health_run`, `rpt_health_ingest`) dựng cùng lúc nên khóa chéo nhau. Postgres hủy
    một bên;
  - lỗi xảy ra ngẫu nhiên, tùy thời điểm: hai lần build ngay trước đó đều `PASS=216`.
- **Hậu quả của lần lỗi:**
  - `rpt_health_summary` bị `cascade` xóa mất, nên trang Sức khỏe dữ liệu không đọc được bảng;
  - còn sót view tạm `rpt_health_run__dbt_backup`;
  - các bảng số liệu PS1–PS5 vẫn dựng bình thường.
- **Sửa:** thêm `-- depends_on:` vào `rpt_health_run.sql` (cha: `rpt_build_info`) và `rpt_health_ingest.sql` (cha:
  `rpt_health_run`). Ba cha của `rpt_health_summary` nay chạy lần lượt `rpt_build_info → rpt_health_run → rpt_health_ingest`,
  không còn khóa chéo nhau. SQL và số liệu không đổi.
- **Kiểm:**
  - `dbt ls -s +rpt_health_ingest` cho thấy cây phụ thuộc đã có `rpt_build_info` và `rpt_health_run`;
  - `dbt build` đầy đủ trên Postgres: **`PASS=216 WARN=0 ERROR=0 SKIP=0`**;
  - sau build: đủ 4 view `rpt_health_*`, không còn bảng hay view `__dbt_backup` / `__dbt_tmp` nào;
  - `rpt_health_summary` = `tot`, 158/158 test;
  - `rpt_build_info.built_at_utc` = 2026-10-02 16:21:38 UTC (23:21 giờ VN).
- **Còn rủi ro cùng loại (chưa sửa, chưa từng gặp):** vài view khác cũng có từ hai cha trở lên dựng song song:
  - `int_orders`, `int_returns`, `int_reviews` (tầng intermediate);
  - `int_reporting_order_items` (đọc 6 bảng marts).

  Gặp lại lỗi "deadlock detected" thì chạy lại `dbt build`.
- **Lệnh build trong PowerShell** (cú pháp `PYTHONUTF8=1 lệnh` ở §8 chỉ dùng được trong bash/Git Bash; thiếu biến này dbt báo
  `'charmap' codec can't decode`):
  `$env:PYTHONUTF8 = '1'; .venv\Scripts\dbt.exe build --project-dir retail_dbt --profiles-dir retail_dbt`
- **Chưa commit.**

### 2026-10-02: Bộ script dựng DWH trên Snowflake, đổi account trial được (dev xong, chưa chạy cloud)

- **Vì sao làm:** PM chốt dùng Snowflake cho buổi demo chính thức tháng 12/2026; Databricks Free dùng làm lab. Trial
  Snowflake chỉ 30 ngày nên mỗi tháng có thể phải đổi account. FAQ chính thức của Snowflake cho đăng ký trial mới khi trial cũ
  hết hạn. Mục tiêu: **mỗi account mới chỉ cần dán một file SQL**, phần còn lại do script dựng lại và tự đối soát.
- **Quy trình cho mỗi account mới** (chạy từ root, PowerShell đặt `$env:PYTHONUTF8 = '1'` trước):
  1. `.venv\Scripts\python.exe scripts\snowflake\bootstrap.py`: tạo khóa đăng nhập (chỉ lần đầu, lưu ở `~/.snowflake/`, ngoài
     repo), điền sẵn `warehouse/snowflake_bootstrap.sql`, tạo `.env.snowflake.local` nếu chưa có.
  2. Snowsight → Worksheet → mở `warehouse/snowflake_bootstrap.sql` → Run All bằng ACCOUNTADMIN.
  3. Điền `SNOWFLAKE_ACCOUNT` (dạng `ORG-ACCOUNT`) và ngày đăng ký trial vào `.env.snowflake.local`.
  4. `.venv\Scripts\python.exe scripts\ingest\snapshot.py` (một lần cho mỗi bộ `data/`), rồi
     `.venv\Scripts\python.exe scripts\ingest\ingest_snowflake.py --snapshot <id>`.
  5. `.venv\Scripts\python.exe scripts\snowflake\run_dbt.py build`.
  6. `.venv\Scripts\python.exe scripts\parity\compare_dwh.py snowflake`: so từng bảng với DuckDB local.
- **Quyết định kỹ thuật (PM không cần chọn, nhưng nên biết):**
  - **Đăng nhập bằng khóa, không password.** Từ đợt 2026-08–10, Snowflake chặn password cho user dạng dịch vụ. Profile dbt đổi
    `password` → `private_key_path` cho user `RETAIL_DBT`.
  - **Tiền không bị xài lố:** warehouse cỡ nhỏ nhất, tự tắt sau 60 giây rảnh. Thêm hạn mức 20 credit/tháng: dùng 80% thì báo,
    100% thì dừng. Đổi hạn mức bằng `bootstrap.py --credit-quota <số>`.
  - **Thứ tự dòng nguồn đánh ở máy** (`_src_row`), Snowflake và Databricks nạp cùng một snapshot Parquet. Lý do: order_items có
    16 cặp (đơn, sản phẩm) lặp; đánh thứ tự sai thì ghép nhầm trả hàng/đánh giá mà tổng doanh thu vẫn đúng.
  - **Làm tròn tồn kho trên Snowflake** viết lại để không ép kiểu số trước khi làm tròn. Giả lập trên DuckDB: 0/60.247 dòng
    lệch ở cả 3 cột (1.912 ca đúng nửa).
  - Tách role: `TRANSFORMER` (nạp + dbt), `REPORTER` (app/chat chỉ đọc; cấp quyền đọc khi nối app).
- **Kiểm (ở máy):**
  - compile dbt cho Snowflake không cần kết nối: **216/216 node**; SQL đúng quote `"Date"`, `dayofweekiso`,
    `listagg … within group (order by …)`;
  - DuckDB và Postgres sau khi sửa: đều **`PASS=216`**;
  - script đối soát tự kiểm: bản sao giống hệt → 33/33 bảng khớp; sửa 0,01 tiền, lệch float 1e-9, xóa 1 dòng → đều bị bắt; lệch
    1e-15 (do thứ tự cộng) → không báo lệch;
  - kiểm chéo hai engine thật: `compare_dwh.py postgres` → **33/33 bảng Postgres khớp DuckDB** từng dòng. Hai engine trả cùng
    kiểu dữ liệu ở mọi cột (model đã ép kiểu tường minh), nên quy tắc "một bên decimal, một bên float" mới kiểm bằng ca thử
    trực tiếp, chưa gặp trên engine thật — Snowflake là lần đầu.
- **Chưa làm / chưa kiểm:** chưa đăng ký account, **chưa chạy bất kỳ bước nào trên Snowflake**; chưa cấp quyền đọc cho
  `REPORTER`; app Streamlit chưa nối Snowflake. Script đối soát chạy hết khoảng 6 phút.
- **Thay đổi kèm theo:** `.gitignore` thêm `/.env.snowflake.local`; `retail_dbt/profiles.yml` (target snowflake);
  `rpt_health_ingest`, `rpt_health_summary`, `assert_rpt_health` có nhánh Snowflake để trang Sức khỏe dữ liệu đọc nhật ký nạp.
- **Chưa commit.**

### 2026-10-03: AI Explain AI0–AI1, công cụ query cho chat (dev xong DuckDB + PostgreSQL chỉ đọc, chưa có LLM)

- **Vì sao làm:** bước đầu của chat PS1–PS5 theo [ai_explain_plan.md](ai_explain_plan.md) §14. Mục tiêu là chốt câu hỏi nào
  trả được, bằng số nào, và có công cụ trả số đúng **trước khi** nối LLM.
- **Đã làm:**
  - 3 công cụ: R/G theo năm; R 2019 so 2018 tách theo số đơn / số món / giá; R theo ngành hàng, vùng, kênh thu hút.
    Câu hỏi thiếu R/G hoặc năm → hỏi lại. Câu có điều kiện chưa hỗ trợ (vd. khoảng ngày, hai chiều cùng lúc) → từ chối rõ,
    không âm thầm bỏ điều kiện. Năm 2023 → báo ngoài dữ liệu thực.
  - "Ngành kéo giảm nhiều nhất 2019" = **Streetwear** (giảm 463,9 triệu), chọn theo số tiền giảm. Cột hạng có sẵn xếp
    Casual hạng 1 vì Casual giảm *ít* nhất; công cụ không dùng cột hạng đó.
  - Mỗi câu trả lời mang bằng chứng: bảng nguồn, câu truy vấn và tham số, lần dựng kho, trạng thái kiểm. Kho chưa qua kiểm →
    không trả số.
- **Kiểm:** số tính thẳng từ CSV khớp kho **từng cent** ở mọi năm 2012–2022 (R, G, ΔR, theo ngành/vùng/kênh) và
  phần góp N/U/P. Sau khi Docker chạy lại: 158/158 test công cụ AI đạt (PostgreSQL trả cùng số DuckDB ở mọi năm, mọi chiều),
  toàn bộ test app 259 đạt. Trên PostgreSQL, chat
  đọc bằng tài khoản riêng chỉ xem được 6 bảng tổng hợp, không sửa được dữ liệu, không xem được dòng hàng có mã khách;
  câu chạy quá giờ bị ngắt. Sau mỗi lần dựng lại kho PostgreSQL phải chạy lại `scripts/ops/pg_ai_readonly_role.py`. Chi tiết:
  [ai_explain_ai0_ai1.md](ai_explain_ai0_ai1.md).
- **Quy ước vẫn treo, chat ghi nhãn "đề xuất":** ngưỡng 1%, phân rã giai đoạn = cộng năm, năm ranh giới PS3.
  Phân rã theo giai đoạn **chưa mở** trong chat cho tới khi PM/BA chốt.
- **PM cần quyết trước AI2:** chọn provider/model LLM, nơi chạy, hạn mức chi phí. Đơn vị tiền tệ vẫn chưa xác minh.
- **PM quyết (2026-10-04):** dev dùng API DeepSeek, sau chuyển OpenAI, nên đổi provider bằng cấu hình. Tiền hiển thị VND
  (ngày 2026-10-05 PM tạm đổi sang ghi trung tính, rồi **chốt lại VND** cùng ngày: xem mục cuối §9).
  Đây là quy ước PM chọn, nguồn không ghi đơn vị. Còn chờ: model, hạn mức chi phí, API key, và VND hay nghìn VND
  (giá TB mỗi món chỉ 4.003–6.548 đơn vị). Ba quy ước "đề xuất" giữ nhãn cho tới khi PM/BA chốt.
- **Chưa commit.**

### 2026-10-03: DWH chạy trên Databricks Free, khớp local từng dòng (lab, xong)

- **Vì sao làm:** Databricks Free là môi trường lab để kiểm DWH chạy được ngoài máy, trước khi lên Snowflake demo tháng 12.
- **Ở đâu:** workspace Databricks Free của PM, catalog riêng **`retail_lab`** (tách khỏi project khác). Bên trong có các schema
  `raw` (14 bảng nguồn + volume `landing` chứa file Parquet), `staging`, `intermediate`, `marts`, `reporting`, `ops`.
  Đăng nhập bằng OAuth qua trình duyệt (profile CLI `retail-dev`), không dùng token dán tay.
- **Kết quả:**
  - nạp snapshot `5bd9a84aaf73`: **14/14 nguồn** đủ số dòng (2.960.736), thứ tự dòng nguồn đủ 1..n, mất khoảng 7 phút;
  - `dbt build`: **`PASS=216`** (lần chạy `80765d11…`, khoảng 5 phút trên warehouse 2X-Small). Trang Sức khỏe dữ liệu trên
    Databricks báo trạng thái "tốt": 158/158 test đạt, 14 nguồn có nhật ký nạp;
  - đối soát `compare_dwh.py databricks`: **33/33 bảng marts + reporting khớp DuckDB local từng dòng**.
- **Lỗi gặp ở lần chạy đầu và cách sửa (số liệu DWH không đổi):**
  - Databricks **cắt phép chia hai số thập phân còn 6 chữ số** (3,394248 thay vì 3,3942482519…). Model
    `rpt_calendar_stability` (bảng độ ổn định nhịp lịch PS3) chia thẳng nên lệch ở chữ số thứ 7. Đã đổi sang macro `ratio()`
    (chia bằng số thực) như mọi model khác. 5 test tính lại tỷ lệ cũng chia thẳng nên báo lệch giả, nay cũng dùng `ratio()`.
  - test Urban Blowout viết `cờ <> exists (...)`, Databricks không đọc được → viết lại bằng `left join`, cùng ý nghĩa.
  - test PS4 ghi cứng kiểu `double precision` (chỉ Postgres có) → dùng macro kiểu số thực theo engine.
  - Kiểm hồi quy sau khi sửa: DuckDB và Postgres đều **`PASS=216`**; `compare_dwh.py postgres` vẫn **33/33**; compile
    Snowflake không cần kết nối cho 7 node vừa sửa: chạy được, SQL ra `cast(... as double)`.
- **Chưa làm / chưa kiểm:** chưa chạy lại bước nạp lần hai để kiểm nạp lặp không nhân dòng; chưa nối Streamlit/chat vào
  Databricks.
- **Dọn workspace (PM làm, 2026-10-03):** xóa 3 schema của project Olist cũ trong catalog `workspace` và thu hồi 2 token cũ
  không còn dùng.
- **Thay đổi kèm theo:** `rpt_calendar_stability.sql`, macro `ratio()` (thêm ghi chú), 6 test trong `retail_dbt/tests/`.
- **Chưa commit.**

### 2026-10-04: App phân tích đọc được DWH trên Databricks (dev xong, chờ PM xem)

- **Vì sao làm:** PM chốt làm Databricks trước, Snowflake tính sau. DWH đã lên Databricks (mục 2026-10-03), bước này cho
  app Streamlit đọc thẳng số từ cloud.
- **Cách dùng:** mở app như cũ (`.venv\Scripts\streamlit.exe run apps/retail_app/app.py`), ở thanh bên chọn
  **Databricks (cloud, lab)**. Muốn app mở thẳng Databricks: đặt `$env:RETAIL_BACKEND = 'databricks'` trước khi chạy.
  Dòng "Nguồn: …" dưới mỗi trang ghi `Databricks catalog retail_lab`. **Tốc độ đo được:** khoảng 2,5 giây cho mỗi bảng
  khi warehouse đang chạy (mỗi lần đọc mở kết nối và đăng nhập mới). Trang đọc nhiều bảng thì lần mở đầu cộng dồn các bảng
  đó. Nếu warehouse đang tắt thì phải chờ bật thêm, phần này chưa đo. Sau lần đầu, app giữ số 10 phút (bấm
  **Đọc lại dữ liệu** để lấy mới), nên lúc demo nên mở qua mọi trang một lượt trước.
- **Điều kiện:** đã đăng nhập `databricks auth login --profile retail-dev` và có `.env.databricks.local`. Thiếu một trong hai
  hoặc phiên đăng nhập hết hạn → trang báo rõ cách đăng nhập lại, gợi ý chuyển DuckDB, không văng lỗi.
- **Kiểm:**
  - cả 17 bảng số liệu app đọc (PS1–PS5, thông tin bản dựng): Databricks ra **đúng số DuckDB** theo cùng tiêu chí đã dùng
    cho Postgres (cột, kiểu dữ liệu giống hệt; số tiền, số đếm bằng tuyệt đối; tỷ số lệch tương đối ≤ 1e-12);
  - 4 bảng sức khỏe dữ liệu: cùng cột, cùng kiểu với Postgres; trang Sức khỏe trên Databricks báo kho "tốt", đủ 14 file
    trong log nạp;
  - **7/7 trang** vẽ không lỗi khi chọn Databricks;
  - toàn bộ test app không cần cloud: **316 đạt** (25 test cần Databricks bỏ qua khi không bật). Test cần cloud: **26/26 đạt**.
    Bật bằng `$env:RETAIL_TEST_DATABRICKS = '1'`. Máy teammate không có workspace thì các test này tự bỏ qua, không báo lỗi.
- **Lưu ý vận hành:** dựng lại kho Postgres (`dbt build --target postgres`) làm mất quyền đọc của tài khoản chat AI; lần này
  56 test chat báo lỗi quyền cho tới khi chạy lại `scripts/ops/pg_ai_readonly_role.py` (đã chạy, đạt).
- **Chưa làm:** chat AI chưa đọc Databricks (vẫn Postgres/DuckDB); app vẫn chạy trên máy, chưa host lên Databricks Apps.
- **Thay đổi kèm theo:** `apps/retail_app/dwh/connection.py` (backend `databricks`), `ui/common.py` (nhãn + lời nhắc khi lỗi),
  `views/suc_khoe_du_lieu.py` (ghi đúng script nạp của từng kho), `app.py` (docstring), `tests/test_smoke.py` (thanh bên có
  3 lựa chọn), test mới `tests/test_databricks.py`; `requirements.txt` thêm `databricks-sql-connector`, `databricks-sdk`;
  `docs/gd2_app_plan.md` §5 thêm backend Databricks.
- **Chưa commit.**

### 2026-10-05: AI Explain AI2, trang chat **Hỏi dữ liệu (AI)** (dev xong với mô hình giả, chờ khóa API để chạy model thật)

- **Vì sao làm:** giảng viên chốt hạn kết thúc tiến độ khóa luận là **2026-10-25**, nên đẩy nhanh phần chat.
- **PM chốt (2026-10-05):**
  - model `deepseek-flash`;
  - mỗi câu tối đa 4 lần đọc kho, mỗi phiên tối đa 200.000 token;
  - tiền ghi trung tính "đơn vị tiền", chưa ghi VND (**đã thay**: PM chốt VND cùng ngày, xem mục kế tiếp);
  - commit code lên nhánh riêng.
- **Đã làm:**
  - trang mới **Hỏi dữ liệu (AI)** trong app;
  - model chỉ chọn công cụ và viết câu, **không được viết số**. Mỗi con số trong câu là một tham chiếu vào bảng kết quả
    của kho. App tra số thật, kiểm dấu tăng/giảm, kiểm câu "nhiều nhất" có dựa trên đủ nhóm, rồi mới hiện;
  - câu sai thì model được sửa một lần; sửa vẫn sai thì trang chỉ hiện bảng số lấy thẳng từ kho, kèm lý do bị chặn;
  - mỗi câu trả lời có phần **Bằng chứng**: bảng số, bộ lọc, định nghĩa, câu SQL, bản kho đã đọc.
  - Câu tiếp nối ("còn theo khu vực?") giữ năm và chỉ tiêu của câu trước, rồi đọc kho lại.
- **Kiểm:** 36 test với **mô hình giả** (kịch bản viết sẵn, có cả kịch bản cố tình nói sai): đạt hết, gồm:
  - chặn câu nói "tăng" khi R giảm;
  - chặn số tự viết;
  - không gọi lại model khi mở lại trang.

  Đây **chưa phải** kết quả của model thật.
- **PM cần làm:** tạo file `.env.ai.local` ở thư mục gốc với `RETAIL_AI_API_KEY='<khóa DeepSeek>'`. Không gửi khóa vào
  chat. Sau đó dev chạy `scripts/ops/ai_live_eval.py`: 22 câu hỏi chuẩn, chấm tự động, ước chi phí. Chi tiết:
  [ai_explain_ai2.md](ai_explain_ai2.md).
- **Thay đổi kèm theo:**
  - `requirements.txt` thêm `openai` (thư viện gọi API chuẩn OpenAI, dùng cho cả DeepSeek);
  - `.gitignore` thêm `/.env.ai.local`;
  - `app.py` thêm trang;
  - `tests/test_smoke.py` thêm trang chat.
- **Kiểm toàn app:** 354 test đạt, 26 test cần Databricks bỏ qua vì chạy tùy chọn và chưa bật.
- **Commit:** trên nhánh `app/myuyen` ngày 2026-10-05, chưa push:
  - `8a7da3e`: code DWH, app, AI0–AI1;
  - `954d75f`: AI2.

  Thư mục `docs/` không commit, theo quyết định PM giữ ở máy.

### 2026-10-05: PM chốt đơn vị tiền là VND; rà lại phần hướng dẫn §1–§8

- **PM chốt:** đơn vị tiền là **VND** (đồng). Thay cho hai ghi chép trước đó trong nhật ký: "VND" (2026-10-04) và "ghi trung
  tính 'đơn vị tiền'" (2026-10-05). Hết câu hỏi "VND hay nghìn VND": số trong kho là đồng.
- **App và chat đã đổi sang VND** (cùng ngày, theo yêu cầu PM):
  - **app:** dải thông tin chung đầu mọi trang thêm dòng "**Tiền:** VND (PM chốt ngày 05/10/2026; dữ liệu nguồn không ghi
    đơn vị). "tỷ" là tỷ đồng, "triệu" là triệu đồng." Phần Giới hạn ở cuối mọi trang bỏ câu "Chưa rõ đơn vị tiền tệ"
    (`ui/common.py`). Số trên thẻ, bảng giữ nguyên dạng "16,43 tỷ", "−572,4 triệu": thêm chữ "đồng" vào từng số sẽ làm số
    dài ra, thẻ PS4 hẹp lại bị cắt (mục 2026-10-02);
  - **chat AI:**
    - số tiền trong câu trả lời và bằng chứng ghi kèm "VND", ví dụ "864.329.802 VND" (trước là "(đơn vị tiền)",
      `ai_explain/evidence.py`);
    - catalog: đơn vị của R, G, ΔR, phần góp N/U/P là `VND`, của P là `VND/món`. Thêm quyết định `currency_vnd` (trạng
      thái `chot`) vào `DECISIONS` (`ai_explain/metric_catalog.py`);
    - chỉ dẫn cho model: tiền là VND do app điền, không ghi USD, không tự đổi sang nghìn/triệu/tỷ (`ai_explain/service.py`);
    - trang chat: dòng giới hạn ghi "Tiền ghi VND" (`views/ai_explain.py`);
    - bộ câu chấm: thôi cấm "VND", chuyển sang cấm "USD" và chữ "đơn vị tiền" cũ (`ai_explain/eval_cases.py`,
      `scripts/ops/ai_live_eval.py`);
  - **test:** `test_khong_ghi_don_vi_tien_te` đổi thành `test_don_vi_tien_la_vnd`: kiểm quyết định `currency_vnd` đã chốt,
    đơn vị các metric tiền là VND, không còn chữ "USD", "$", "chưa xác minh";
  - **tài liệu:** `ai_explain_plan.md`, `ai_explain_ai2.md`, `ai_explain_ai0_ai1.md`, `gd2_app_plan.md` ghi quyết định
    VND, giữ dòng cũ làm lịch sử.
- **Kiểm (2026-10-05):** toàn bộ test app `pytest apps/retail_app`: **359 passed, 1 failed, 26 skipped** (16 phút, máy
  chậm). Test lỗi `test_ps4_canh_bao_slide_10` quá hạn 30 giây khi mở trang (không liên quan đơn vị tiền); chạy riêng lại:
  **PASS** trong 2,2 giây. Tổng 360 test (trước 354): gồm cả test mới trong `tests/test_ai_tools.py` đang sửa dở từ trước,
  chưa commit, không thuộc đợt này. Live eval với model thật **chưa chạy** (chưa có khóa API).
- **Chưa đổi:** `star_schema.md` ("số tiền giữ đơn vị của nguồn", vẫn đúng: kho không gắn mã tiền tệ),
  `de_cuong_khoa_luan.md` và `scope_statement.md` (còn ghi "đơn vị tiền không xác định"; tài liệu khóa luận, PM quyết có
  sửa không).
- **Rà lại §1–§8** cho khớp nhật ký tới ngày 2026-10-05:
  - §2 ghi đơn vị VND;
  - §3.1 thêm Databricks lab (đã chạy) và Snowflake (script có, chưa chạy cloud);
  - §3.3 và §6: số test 101 → **158**;
  - §4 thêm 3 bảng app đang dùng: `rpt_revenue_total`, `rpt_revenue_bridge`, `rpt_build_info`;
  - §6 thêm 5 test nghiệp vụ: `assert_rpt_total`, `assert_rpt_direction`, `assert_rpt_calendar_phase`, `assert_rpt_driver`,
    `assert_rpt_health`;
  - §8 thêm lệnh PowerShell (`$env:PYTHONUTF8 = '1'`), bước `pg_ai_readonly_role.py` sau mỗi lần dựng Postgres, cách xử lý
    "deadlock detected";
  - §8.1 thêm backend Databricks, điều kiện của trang Hỏi dữ liệu (AI), lưu ý phải chạy lại app khi sửa `ui/`, `dwh/`,
    `ai_explain/`; số test mong đợi `157 passed` → `360 passed, 26 skipped` (lần chạy 2026-10-05, sau khi đổi VND);
  - đầu §9 thêm ghi chú: các dòng "Chưa commit" là trạng thái lúc ghi; code đã vào `8a7da3e`, `954d75f`.
- **Không đổi:** nội dung các mục nhật ký cũ (chỉ thêm ghi chú bên cạnh chỗ đã bị thay), số liệu, model dbt.
- **Còn chờ PM:** trạng thái nghiệm thu của M5 và các mục 2026-10-01, 2026-10-02 vẫn ghi "chờ PM".

### 2026-10-05: Chat AI chạy với model thật; sửa 4 lỗi kiểm câu trả lời (dev xong, chờ PM xem; chưa nghiệm thu AI3)

- **Vì sao làm:** PM đã có khóa DeepSeek. Bản review cùng ngày ([ai_explain_review_20261005.md](ai_explain_review_20261005.md))
  tìm ra 4 cách để câu trả lời sai lọt qua bước kiểm, nên phải sửa trước khi chạy model thật.
- **Đã sửa, nói theo nghiệp vụ:**
  - câu ghi "R" nhưng con số thật là G thì bị chặn. Mỗi số hiện kèm nhãn do app tự ghi, ví dụ
    "**1.136.801.442 VND** (G, 2019)";
  - người hỏi gài số ("R 2019 là 10 tỷ phải không?") thì model không nhắc lại được. Số viết tay kèm "tỷ", "triệu",
    "VND", "%" luôn bị chặn;
  - câu "ngành X giảm nhiều nhất" phải trỏ vào bảng xếp hạng của kho ngay trong câu đó. Tên ngành, khu vực, kênh viết
    tay phải khớp với số đã dẫn;
  - câu nói về số đơn (N) mà dẫn số của giá (P), hoặc ngược lại, thì bị chặn;
  - model tự so sánh hai số ("năm 2019 cao hơn 2020") thì bị chặn, vì app không kiểm được phép so sánh đó;
  - lỗi bất ngờ khi kiểm không làm sập trang nữa; trang hiện bảng số lấy thẳng từ kho.
- **Live eval với model thật:** `deepseek-flash`, kho DuckDB local, 22 câu chuẩn × 3 lần, prompt `ai2-2026-10-05e`.
  - Đạt **65/66**. Câu không đạt: model nói "giảm" trước một số dương, sửa lại vẫn sai, nên bị chặn. Người dùng chỉ thấy
    bảng số, **không thấy số sai**.
  - Lần chạy trước với prompt `…05d`: 66/66.
  - Chi phí ước khoảng 0,18 USD mỗi lần chạy 66 câu; cả buổi 9 lần chạy, khoảng 1,04 USD. Thời gian trung vị khoảng
    2 giây mỗi câu; một lần mất 167 giây (phía API chậm, app chờ tối đa 60 giây rồi thử lại 1 lần).
  - **Lưu ý:** 22 câu này đã được dùng để chỉnh prompt và bộ kiểm, nên 65/66 **chưa phải điểm nghiệm thu**. Nghiệm thu
    cần một bộ cách hỏi mới chưa dùng để chỉnh (kế hoạch §13).
  - Mình đã đọc tay phần lời: không câu nào khẳng định nguyên nhân, không nhắc lại số gài, số khớp đối chứng CSV.
  - Chi tiết, cùng một lần nới bộ chấm cho E04/E04b có ghi lý do: [ai_explain_ai2.md §0](ai_explain_ai2.md).
- **Kiểm:** hai bộ test AI đạt **213/213** (gồm PostgreSQL). Toàn app `pytest apps/retail_app`: **372 passed, 1 failed,
  26 skipped** (10,6 phút). Test lỗi là `test_postgres_khong_chay_thi_bao_loi_ro`, quá hạn 30 giây khi mở trang (máy
  chậm lúc chạy cả bộ, không liên quan chat). Chạy riêng lại: **PASS** trong 11,8 giây.
- **Còn lại:**
  - đôi khi model kể sai năng lực khi từ chối, ví dụ nói "trả lời được số khách" trong khi C chưa mở;
  - câu so sánh không kèm số chưa được kiểm;
  - hạn 200.000 token chưa phải trần chi phí cứng;
  - live eval mới chạy trên DuckDB, chưa chạy trên PostgreSQL.
- **PM nên làm:** khóa API đã được dán vào chat nên đã nằm trong log hội thoại. Nên thu hồi khóa này trên trang
  DeepSeek, tạo khóa mới, rồi tự thay vào `.env.ai.local`.

### 2026-10-05: Chat AI trả lời được câu hỏi định nghĩa ("R là gì") (dev xong, chờ PM xem)

- **PM gặp trên app:**
  - hỏi "R là gì" thì chat hỏi lại năm;
  - hỏi "what is R stand for" thì báo "Chưa tạo được diễn giải… bảng số bên dưới" nhưng không có bảng nào.
- **Vì sao:**
  - chat chỉ có công cụ đọc số theo năm, chưa có công cụ tra định nghĩa. Model trả lời bằng trí nhớ thì bị bộ kiểm
    chặn, đúng quy tắc: câu trả lời phải dựa trên thứ đọc được;
  - trang đang mở còn chạy code cũ (chân trang ghi `prompt ai2-2026-10-05`). Muốn thấy bản mới phải tắt app rồi chạy lại.
- **Đã sửa:**
  - thêm công cụ tra định nghĩa. Định nghĩa lấy từ danh mục chỉ tiêu đã chốt, cùng nguồn với phần Bằng chứng: công
    thức, đơn vị, cách cộng, trạng thái chốt hay đề xuất;
  - câu báo lỗi khi lượt không đọc được gì giờ ghi rõ "chưa đọc được dữ liệu nào", không nhắc bảng số nữa.
- **Kiểm:**
  - test AI 215/215;
  - model thật: "R là gì", "what is R stand for", "G khác R thế nào?" mỗi câu 3 lần, đạt 9/9; bộ cũ chạy lại đạt 25/25.

### 2026-10-05: Sửa lỗi Arrow ở bảng nguồn số của trang chat AI (dev xong, chờ PM xem)

- **PM gặp:** terminal Streamlit in `ArrowTypeError … Conversion failed for column Giá trị trong kho`.
- **Vì sao:** cột này trộn chuỗi (số tiền kiểu Decimal được đổi sang chuỗi để giữ đủ chữ số) với số thực (tỷ lệ).
  Streamlit tự chữa rồi vẫn hiện bảng, nên trang không sập, nhưng log báo lỗi dài.
- **Đã sửa:** trước khi vẽ bảng, cột nào trộn chuỗi với số thì đưa cả cột về chuỗi. Áp cho bảng nguồn số và bảng bằng chứng.
- **Kiểm:** test AI 216/216, gồm một test tái hiện đúng lỗi. Phải tắt app rồi chạy lại mới thấy bản sửa.

### 2026-10-05: Nghiệm thu chat AI trên bộ cách hỏi mới, gate AI2 → AI3 (dev xong, chờ PM xem)

- **Vì sao cần:** bộ 25 câu cũ đã dùng để chỉnh prompt, nên đạt trên bộ đó chưa đủ khách quan.
- **Đã làm:** soạn bộ mới 30 câu chưa từng dùng để chỉnh.
  - Đổi năm: 2016, 2017, 2020, 2021, 2022.
  - Thêm chiều kênh thu hút khách và câu hỏi chiều "tăng nhiều nhất".
  - Follow-up đổi năm và đổi chiều.
  - Cách hỏi mới cho các câu: ngoài phạm vi, ghi/xóa kho, chèn lệnh, đưa số sai, hỏi định nghĩa.
- **Cách giữ khách quan:**
  - Số phải có tính độc lập từ CSV. Kiểm rubric bằng tool trước khi gọi model: 30/30 khớp.
  - Commit bộ câu `a34b12f` trước lượt chạy đầu tiên.
  - Không chỉnh prompt giữa chừng.
- **Kết quả với model thật** (deepseek-flash, DuckDB, mỗi câu 3 lần):
  - chấm tự động 90/90 lượt đạt;
  - đọc tay 0 lỗi chặn: không số sai, không nói nguyên nhân;
  - khoảng 2 giây mỗi câu; chi phí ước khoảng 0,26 USD cho cả 90 lượt.
- **Lỗi lời nhỏ, chưa sửa:**
  - một câu cụt nghĩa;
  - nhắc số khách C dù chưa mở;
  - mời "xem theo tháng" dù chưa hỗ trợ;
  - dấu âm/dương không đồng nhất trong một câu.
  - Sửa cùng đợt mở tool PS1–PS3.
- **Chi tiết:** `docs/ai_explain_ai2.md` §0b.
- **Việc kế:** mở tool PS1–PS3 (AI3), chạy model thật trên PostgreSQL.

### 2026-10-05: Chat AI trả lời được PS1–PS3 (dev xong, chờ PM xem)

- **Mở thêm:**
  - PS1: G hụt thành R bao nhiêu và vì khoản nào (đơn hủy, đơn trả, đơn chưa giao, chiết khấu), theo năm hoặc cả kỳ 2013–2022; R/G của một tháng;
  - PS2: 4 giai đoạn và 3 điểm đổi hướng đã chốt;
  - PS3: tháng cao/thấp nhất, dồn cuối tháng, tháng 8 năm lẻ so năm chẵn, kèm độ ổn định khi bỏ từng năm.
- **Kiểm số:** mọi năm, tháng, giai đoạn đều so thẳng với CSV, khớp từng cent; PostgreSQL khớp DuckDB. Test AI 289/289.
- **Model thật:** bộ nghiệm thu mới 10 câu × 3 lần đạt 30/30, đọc tay không có lỗi chặn.
  - Lần nghiệm thu trước đó bắt được một lỗi: hỏi "Streetwear tháng 5/2019", model trả số toàn công ty, tức bỏ ngầm bộ lọc ngành.
  - Đã chặn bằng code: hỏi một nhóm thì phải có số của đúng nhóm đó; nhóm theo tháng hoặc quý thì trả "chưa hỗ trợ".
- **Chưa mở:** nhóm theo tháng hoặc quý, khoảng ngày tùy ý, phân rã theo giai đoạn, tháng đổi hướng do dữ liệu tự tìm.
- **Cần PM/BA chốt:** quy ước năm ranh giới PS3. Số theo giai đoạn của PS3 đang ghi "đề xuất".
- **Chi tiết:** `docs/ai_explain_ai3.md`. Muốn thấy bản mới thì tắt app rồi chạy lại.

### 2026-10-05: Chat AI chạy model thật trên PostgreSQL (dev xong, chờ PM xem)

- **Kết quả:** chat đọc kho PostgreSQL bằng tài khoản chỉ-đọc riêng `retail_ai_ro`, qua guard của app.
  - Bộ nghiệm thu B\*: 10 câu × 3 lần, **30/30**.
  - Toàn bộ 95 câu, mỗi câu 1 lần: **93/95**.
  - Không có số sai, không bỏ ngầm bộ lọc. Số khớp số đối chứng của rubric (đã kiểm 95/95 trên PostgreSQL trước khi gọi model).
- **Hai câu trượt, đều không phải do PostgreSQL:**
  - "Doanh thu năm 2023": trả lời đúng ý (dữ liệu chỉ đến 2022) nhưng gắn nhãn "chưa hỗ trợ" thay vì "không có dữ liệu".
  - "Tháng nào doanh thu thấp nhất": model thêm câu "tháng thấp nhất lặp lại ở cả 4 giai đoạn". Câu đúng, nhưng tool không có ô số chứng minh, nên app chặn phần lời và chỉ hiện bảng số.
- **Lỗi lời gặp nhiều hơn:** số âm mất dấu khi trong câu có chữ "giảm" (CAGR giai đoạn B, giai đoạn C, điểm đổi hướng 2016). Có một lần lặp cùng một số hai lần liền. Đề xuất sửa trước khi demo.
- **Chạy app trên PostgreSQL** phải đặt `PG_AI_USER` / `PG_AI_PASSWORD`. Docker local dùng mặc định `retail_ai_ro`.
- **Chi tiết:** `docs/ai_explain_ai3.md` §4.

### 2026-10-05: Chat AI sửa lỗi số âm mất dấu và các lỗi mức vừa (dev xong, chờ PM xem)

- **Đã sửa:**
  - số âm không còn bị in thành số dương (ví dụ CAGR giai đoạn B nay hiện **−6,4%**);
  - trợ lý trả được "tháng thấp nhất cả kỳ" và "cả 4 giai đoạn cùng tháng thấp nhất" kèm số chứng minh;
  - hỏi số năm 2023–2024 thì trả "không có dữ liệu", hỏi dự báo thì trả "chưa hỗ trợ";
  - hạn 200.000 token mỗi phiên thành trần cứng (đổi lại, phiên ngắn hơn khoảng 2 câu);
  - build Postgres xong tự cấp lại quyền cho tài khoản AI.
- **Kiểm:** test AI 315/315. Bộ câu nghiệm thu mới C\*, soạn và commit trước khi chạy: DuckDB 30/30, PostgreSQL 30/30, đọc tay 0 lỗi chặn.
- **Còn lại:** đôi khi model tự thêm câu "tăng/giảm mạnh nhất" mà không kèm số chứng minh, app chặn phần lời và chỉ hiện bảng số (1/105 lượt).
- **Chi tiết:** `docs/ai_explain_nhat_ky.md`, `docs/ai_explain_ai3.md` §4c.

### 2026-10-05: PM chốt Databricks là đích production (quyết định, chưa triển khai phần mới)

- **Quyết định:** Databricks là **production** cho DWH, app phân tích và chat AI; không còn là "lab".
- **Quy trình:** dev và test ở local (DuckDB / PostgreSQL) trước, đạt thì mới deploy lên Databricks và chạy lại cùng bộ kiểm.
- **Snowflake:** thôi là bước mặc định. Script đã viết giữ nguyên, chưa chạy cloud.
- **Đã có trên Databricks:** DWH `retail_lab` (216/216, đối soát 33/33, ngày 2026-10-03); app đọc được Databricks (2026-10-04).
- **Chưa có:** chat AI đọc Databricks; app host trên Databricks.
- **Đã kiểm khả thi (cùng ngày):** serverless gọi được API DeepSeek; workspace có sẵn model `databricks-deepseek-v4-flash-0731` do Databricks host. Còn lại: app tự dừng sau 24 giờ mỗi lần khởi động, tối đa 3 app; khả năng gọi ra ngoài của app chỉ biết chắc khi deploy.
- **Đã sửa tài liệu:** CLAUDE.md §1, `docs/dwh_roadmap.md`, skill `retail-platform-validation` (bản Claude và bản Codex).

### 2026-10-06: chat AI chạy trên Databricks (đã kiểm), app đã tạo trên Databricks Apps (chờ khóa để deploy)

- **Chat đọc Databricks bằng tài khoản máy riêng, chỉ đọc** (`retail-ai-ro`, chỉ SELECT đúng 14 bảng). Tài khoản đăng nhập của PM bị chặn, không dùng được cho chat.
- **Kiểm:**
  - số trên Databricks **khớp DuckDB** ở cả 83 câu hỏi mẫu cho tool;
  - model thật **30/30** câu nghiệm thu C\*;
  - mỗi câu trả lời mất khoảng 11–14 giây.
- **Kho Databricks** dựng lại đủ (217/217). Có một lần build hỏng do mạng: kho thành "lỗi test", và **chat tự từ chối trả số** cho tới khi build lại đạt. Quy tắc: trên production chỉ build đủ, không build một phần.
- **Đã tạo trên workspace:**
  - SP `retail-ai-ro` (secret hết hạn 2027-01-04);
  - secret scope `retail-ai`;
  - app `retail-analytics` (SP của app chỉ đọc 21 bảng các trang dùng);
  - code đã tải lên workspace.
- **Khóa DeepSeek (PM làm 2026-10-07):** tạo khóa **mới chỉ dùng cho Databricks**, tự đưa vào secret trong terminal riêng.
  Khóa cũ giữ trong `.env.ai.local` để chạy local; chỉ thu hồi khi nghi bị lộ.
- **Lưu ý demo:** bản Free tự dừng app sau 24 giờ, hoặc sớm hơn khi tài khoản chạm giới hạn sử dụng (gặp ngày 2026-10-07);
  trước buổi demo phải bật lại app. Cách tự bật lại: `docs/databricks_app_van_hanh.md`.

### 2026-10-07: app chạy trên Databricks Apps

- **Deploy thành công** (bản code `fdb8681`), sau khi sửa 2 lỗi:
  - Databricks Apps chạy Python 3.11, không cài được numpy 2.5.1 → ghim numpy 2.4.6; toàn bộ test app chạy lại trên Python 3.11 đạt (`2425dbf`);
  - lệnh khởi động không chạy qua shell nên cờ `--server.port ${...}` làm app crash → bỏ cờ, nền tảng tự đặt cổng (`fdb8681`).
- **Cùng tối (12:20 UTC)** Databricks tự tắt app: *"stopped due to workspace or account status"* (giới hạn bản Free).
  Bảng usage: ngày 06/10 SQL dùng 10,56 DBU không bị tắt; ngày 07/10 tổng thấp hơn nhưng có thêm app chạy liên tục 3,78 DBU.

### 2026-10-08: bật lại app Databricks; chuẩn bị bản public trên Streamlit Community Cloud

- **Bật lại app** bằng `apps start` (tự deploy lại gói `fdb8681`). Hướng dẫn PM tự bật lại: `docs/databricks_app_van_hanh.md`.
- **PM chọn có bản public** (ai cũng xem, không cần đăng nhập). Databricks Apps không cho mở công khai, nên giao diện chạy trên
  **Streamlit Community Cloud**, dữ liệu vẫn đọc **kho Databricks production**. PM chọn: chat để tự do, dùng khóa DeepSeek riêng;
  tắt app Databricks khi bản Streamlit chạy ổn.
- **Đã làm (PM duyệt):**
  - SP mới `retail-web-ro` cho các trang: kiểm lại chỉ SELECT đúng 21 bảng; hook dbt cấp lại quyền sau mỗi build;
  - `requirements.txt` của bản deploy chuyển về `apps/retail_app/` (dùng chung cho Streamlit Cloud và gói Databricks);
  - nội dung Secrets sẵn trong `.env.streamlit_cloud.local` (Git ignore), PM chỉ điền khóa DeepSeek.
- **Kiểm (giả lập Streamlit Cloud trên máy):** không file `.env`, không profile, chỉ biến môi trường từ Secrets → 8/8 trang mở được,
  chat C01 ra số, câu 2024 báo không có dữ liệu, câu dự báo 2023 báo không hỗ trợ.
- **PM làm tiếp:** theo `docs/streamlit_cloud_deploy.md` (tạo khóa, deploy, bật public, smoke).
- **Giới hạn:** bản public phụ thuộc bản Free của cả Streamlit (app ngủ khi lâu không ai xem) và Databricks (có thể bị chặn khi chạm
  giới hạn); không cam kết luôn sẵn sàng.

### 2026-10-09: bản public chạy trên Streamlit Community Cloud (dev kiểm các trang; chờ PM hỏi thử chat)

- **Link công khai:** https://retail-analytics-ps.streamlit.app/ (không cần đăng nhập). PM tự deploy từ nhánh `app/myuyen`.
- **Đã kiểm (ẩn danh, từ ngoài):** app báo mở công khai; 8/8 trang mở được, không trang nào báo lỗi; Tổng quan đọc kho
  Databricks `retail_lab`, đủ 11 năm.
- **PM làm tiếp:** hỏi thử 3 câu chat theo `docs/streamlit_cloud_deploy.md` Bước 5; ổn thì tắt app Databricks (Bước 6).

### 2026-10-09: chat AI sửa lỗi câu "… mạnh nhất" bị chặn (dev xong, chờ PM xem)

- **Lỗi PM thấy được:** hỏi "giai đoạn sập giảm bao nhiêu", chat hay viết thêm câu "Đây cũng là giai đoạn giảm mạnh nhất…". App
  không kiểm được câu đó nên chặn cả phần lời, chỉ hiện bảng số (nhật ký AI §3 mục 10).
- **Đã sửa:** app tự kiểm câu "Đây (cũng) là … mạnh nhất" với bảng xếp hạng tính trên đủ các giai đoạn / ngành / vùng: đúng thì
  hiện, sai thì vẫn chặn. Câu nói "theo CAGR" hay "bằng tiền" phải đúng theo tiêu chí đó. Commit `09b9930` và `24c86d5` (nhánh `app/myuyen`,
  **chưa push**).
- **Kiểm:**
  - test không gọi model: 272 đạt trên DuckDB; 87 test cần PostgreSQL lúc đầu chưa kiểm được vì Docker tắt; bật Docker chạy lại cùng ngày: **124/124 test PostgreSQL đạt**;
  - chạy lại 1.082 câu trả lời cũ: không câu nào trước qua mà nay bị chặn;
  - model thật, bộ 12 câu mới D\* × 3 lượt: **34/36** đạt chấm tự động, đọc tay 0 số sai;
  - đúng 3 câu cũ hay lỗi (C02, A03, A03d) × 3 lượt: **9/9**, không lượt nào phải sửa (trước: C02 phải sửa 3/6 lượt).
- **Lần chạy D\* đầu:** hỏi "ngành nào giảm **ít** nhất" thì chat trả lời lệch sang "giảm nhiều nhất" (đã sửa, xem dòng cuối).
  Chi tiết: `docs/ai_explain_nhat_ky.md`.
- **Bản public** (https://retail-analytics-ps.streamlit.app/) chưa có bản sửa này. Muốn có thì push nhánh `app/myuyen`, Streamlit
  Cloud tự deploy lại: chờ PM quyết.
- **Sửa thêm cùng ngày** (commit `24c86d5`): câu "Đây là … lớn nhất" phải nói về tăng/giảm, không được nói về tỷ trọng; hỏi "giảm
  ít nhất" thì chat nêu số từng ngành hoặc báo "chưa xếp được", không đổi sang "giảm nhiều nhất". Model thật D11 × 3 sau sửa: 3/3
  đúng hướng. Câu hỏi PM còn lại chỉ là: có cần chat trả lời thẳng "ngành giảm ít nhất là …" không (phải thêm xếp hạng phía nhỏ).

### 2026-10-09: chat trả lời thẳng "ngành / vùng / kênh giảm ít nhất là …" (dev xong, chờ PM xem)

- **PM chốt:** chat cần trả lời thẳng "ngành giảm ít nhất là …".
- **Đã làm:** công cụ theo nhóm tính thêm nhóm giảm ít nhất / tăng ít nhất trên đủ các nhóm (chỉ trong các nhóm cùng chiều). App
  kiểm câu "ít nhất / nhẹ nhất" phải dẫn đúng xếp hạng này. Commit `02b772e`, `c1700ad`.
- **Kiểm:** model thật, bộ 10 câu mới F\* × 3: hỏi ngành / vùng / kênh giảm hoặc tăng ít nhất **21/21**; đọc tay 0 số sai.
- **Chưa có phía "ít nhất"** cho giai đoạn và cho N/U/P: chat nói "chưa xếp được" kèm số (6/6 lượt sau sửa).
- **Ví dụ:** "Năm 2019 ngành hàng nào giảm ít nhất?" → "Casual, giảm 22.448.071 VND".


### 2026-10-09: PS5, thẻ "Số đơn đổi" không còn bị cắt chữ (dev xong, chờ PM xem)

- **PM báo:** thẻ đầu của phần "Số đơn toàn công ty: đổi vì số khách (C) hay tần suất (F)" hiện "Số đơn toàn công ty đổi
  (2016→2…", khó đọc.
- **Đã sửa:**
  - nhãn thẻ rút còn "Số đơn đổi (2016→2017)". Chữ "toàn công ty" vẫn ở tiêu đề, dòng chú thích ngay trên và phần chú giải (?)
    của thẻ (`views/ps5_nhom.py`);
  - 3 thẻ dùng chung khuôn `hang_the` như thẻ PS4/PS5 nên cao bằng nhau;
  - `hang_the` (`ui/common.py`): nhãn dài được xuống dòng thay vì bị cắt "…". Khi thẻ hẹp (≤ 230px, vd. màn 1024px), MỌI thẻ trong
    hàng chừa sẵn 2 dòng nhãn, nên dòng số vẫn thẳng hàng. Áp luôn cho thẻ PS4 và thẻ đầu trang PS5 (trước đó "Do số món/đơn U",
    "Ngành hàng giảm nhiều nhất" cũng bị cắt ở màn hẹp).
- **Kiểm:** chụp ảnh thật (DuckDB) ở 1024, 1150, 1280px: nhãn đủ chữ, 3 số thẳng hàng; thẻ PS4, PS5 không lệch. Test trang
  PS1, PS4, PS5 và smoke trên DuckDB đạt; bật Docker chạy lại mọi test PostgreSQL (gồm 8 trang smoke, trang PS4, PS5): 124/124 đạt.
- **PM xem:** chạy lại app (sửa ở `ui/common.py` cần tắt app rồi bật lại, không chỉ tải lại trang).
- **Chưa commit.**
