# Giao việc D3: dbt theo kỳ của bản, dự báo đứng yên, sửa retry `prepare`

Soạn ngày 2026-11-05. PM đã chốt §10 ngày 2026-11-05. **Đổi cách làm:** PM bảo Claude tự code ("đừng tạo thêm nhánh nữa, code tiếp đi"), nên phần này **không có lớp rà độc lập của người khác**; bù bằng đột biến, đối chứng độc lập và lượt thật ở §9.
Thiết kế gốc: `docs/thiet_ke_nap_ky_moi.md` §4.4 và §4.8 phần "Dự báo đứng yên" (bản mới nhất ở worktree `D:/retail-analytics-nhap`). Phiếu này đã chép đủ luật. **§4.5 của thiết kế (dự báo học lại) không áp dụng:** PM đã gác D4, dự báo giữ đứng yên cho mốc 12/12.

Đọc trước: `AGENTS.md`, `CLAUDE.md` §1, §5, `docs/agent_workflows.md`, `docs/giao_viec_snapshot_dot.md` §0–§3; `scripts/pipeline/cli.py`, `scripts/forecast/stage.py`, các model và test nêu ở §3–§5.

## 0. Vì sao cần

D2 đã tạo được snapshot có đợt 2023 nhưng dừng ở `prepare`. dbt hiện viết cứng lịch sử dừng ở 2022, nên build bản có đợt sẽ hỏng: `fact_daily_sales` trùng ngày 2023 giữa số thực tế và dòng `sample_submission`, nhiều test khóa số trượt, năm 2023 nằm ngoài kỳ phân tích.

**Yêu cầu quan trọng nhất: không có đợt thì SQL biên dịch, `snapshot_id` và `model_version` y hệt hiện tại.** Code này sau này merge không được làm đổi bản public.

## 1. Phạm vi

**Làm:** dbt đọc kỳ của bản khi có đợt; dự báo dùng lại từ bản gốc; mở `forecast`, `build`, `validate` cho snapshot có đợt; chặn `publish` và `rollback` với bản có đợt; sửa lỗi retry `prepare --snapshot-id`.

**Không làm:**

- không sửa `scripts/forecast/*.py`, vì `model_version()` băm mọi file trong thư mục này;
- không sửa `apps/retail_app`: nhãn kỳ, băng rôn, ẩn chat, trang Dự báo là D5. Chuỗi `'2013-2022'` trong app giữ nguyên;
- không học lại dự báo, không đổi `sample_submission`, không ghi `submission.csv`;
- không sửa `scripts/ingest/source_contract.py`, `scripts/ingest/extensions/*.yml`, `scripts/ingest/dot.py`;
- không kết nối Databricks, Neon, Airflow; không dựng image; không sửa DAG;
- không sửa `CLAUDE.md`, không sửa số khóa để test xanh.

## 2. Môi trường và ràng buộc

- Worktree `D:/retail-analytics-nap`, nhánh `nap-ky/myuyen`, **sau khi Claude gộp `auto-mapping/myuyen`** (§10 mục 1). Python `D:/retail-analytics/.venv/Scripts/python.exe`. **Không commit, không push.**
- Worktree không có `data/`. Chạy thật dùng `--data D:/retail-analytics-nhap/data`, chỉ đọc. `data_demo/` không vào git.
- Laptop ít RAM. GPT chỉ chạy test nhỏ ở §7; **không chạy lượt pipeline thật** (PM chạy theo script của Claude). Không chạy nền lệnh nặng; bị dừng vì thiếu RAM thì báo, không tự chạy lại.
- Không in tên, số điện thoại, tuổi, giới tính nhân viên hay shipper ra log hoặc thông báo lỗi.
- SQL mới phải chạy được trên DuckDB, PostgreSQL và Databricks, dùng macro `cross_db.sql` sẵn có; không suy ra Databricks đạt từ DuckDB.

## 3. dbt: kỳ theo bản

### 3.1 Biến dbt

`dbt_build` (`scripts/pipeline/cli.py:46`) chỉ thêm biến khi context có `dot`. **Không có đợt thì `--vars` y như cũ.**

| Biến | Mặc định | Có đợt 2023 |
|---|---|---|
| `co_dot` | `false` | `true` |
| `analysis_end_year` | `2022` | `2023` |
| `last_actual_date` | không có | `2023-12-31` |
| `forecast_trained_through` | không có | `trained_through` của dự báo nguồn, `2022-12-31` |

Thêm hàm `ky_cua_ban(snapshot_path)` trong `scripts/pipeline/`: đọc `max(Date)` trong `sales.parquet` của snapshot, không viết cứng năm. Ngày cuối không phải 31/12 thì `ValueError` (§10 mục 2).

**Giữ SQL không đổi:** viết `{{ var('analysis_end_year', 2022) }}` để bản mặc định ra đúng chữ `2022`; nhánh mới đặt trong `{% if var('co_dot', false) %}`. Ghi chú mới dùng `{# #}`, không dùng `--`, vì chú thích `--` đi vào SQL biên dịch.

### 3.2 Model phải đổi

| File | Việc |
|---|---|
| `models/marts/fact_daily_sales.sql` | Có đợt: nhánh dự báo chỉ giữ `sales_date > last_actual_date` |
| `models/marts/dim_date.sql` | `is_forecast_period`: có đợt thì sau `last_actual_date`. Dải ngày và 4.566 dòng giữ nguyên. `last_actual_date` phải trước `2024-07-01`, không thì build dừng |
| `models/reporting/rpt_build_info.sql:12` | `analysis_end_year` đọc biến |
| `rpt_revenue_monthly.sql:27`, `rpt_revenue_yearly.sql:43`, `rpt_revenue_segment_yearly.sql:38` | `is_analysis_period` tới `analysis_end_year` |
| `rpt_revenue_total.sql:5–7` | Có đợt: giữ hai dòng cũ `2012-2022`, `2013-2022` với `is_analysis_period = false`, thêm dòng `2013-<năm cuối>` với `true` (§10 mục 3) |
| `rpt_forecast_actual.sql` | Có đợt: chỉ lấy ngày `<= forecast_trained_through`, để trang Dự báo không vẽ số tổng hợp cạnh dự báo |
| Nơi dùng `ref('ps2_phases')`: `rpt_calendar_phase_month.sql:10,16`, `rpt_driver_period.sql:16`, `rpt_revenue_phase.sql:22`, `rpt_revenue_turning_point.sql:13`, `rpt_revenue_yearly.sql:29`, `tests/assert_rpt_driver.sql:8`, `tests/assert_rpt_phase.sql:12,38,63` | Có đợt: giai đoạn cuối (`end_year` lớn nhất) kéo tới `analysis_end_year`. Không sửa file seed. Viết một macro dùng chung; lưu ý nơi không có bí danh, vì subquery trên Postgres cần bí danh |

Các model khác đi theo `is_analysis_period` thì không cần sửa. Nếu thấy mốc năm cứng ngoài danh sách này, báo ở §9.

### 3.3 Test

**Nguyên tắc:** bản không đợt giữ nguyên toàn bộ. Bản có đợt thì số khóa của **năm hoặc giai đoạn không đổi** vẫn phải chạy; chỉ tắt số khóa của phép gộp **có chứa 2023** và thay bằng phép tính lại từ thành phần.

| Test | Bản có đợt |
|---|---|
| `assert_row_counts` | Giữ số cứng cho bản không đợt. Có đợt: số kỳ vọng = số gốc + số dòng đợt trong manifest, cho `fact_order`, `fact_order_item`, `fact_return`, `fact_review`, `fact_inventory_snapshot`, `fact_web_traffic`. `bridge_item_promo` dẫn xuất nên so với phép đếm độc lập từ `stg_order_items`. Các `dim_*` giữ số cũ |
| `assert_rpt_total` | Số khóa `2012-2022`, `2013-2022` giữ nguyên. Dòng 66–73 và phần so `rpt_build_info` ở dòng 129–133: `data_end_date` của bản có đợt là ngày cuối 2023, nên so với dòng kỳ mới thay vì `2012-2022`. Số kỳ thác: 3 kỳ gộp + 12 năm |
| `assert_rpt_deck_numbers` | Slide 4 đang cộng mọi năm trong `rpt_revenue_yearly`: giới hạn `year <= 2022`, số khóa giữ nguyên. Chênh tháng 8 (`n_odd_years`, `n_even_years`) và slide 8 đọc `is_analysis_period`: có đợt thì tắt số 5 và 5, tính lại theo kỳ của bản. Đọc lại từng dòng còn lại |
| `assert_rpt_calendar` | Dòng 3–6: số tháng và tháng cuối theo kỳ của bản. Dòng 33, 108: tới `analysis_end_year`. Dòng 99 (chênh tháng 8): tắt, thay bằng tính lại |
| `assert_rpt_phase` | Dòng 16: kết thúc `analysis_end_year`. CAGR A, B, C và 3 điểm đổi hướng giữ nguyên. CAGR D: tắt, thay bằng tính lại |
| `assert_rpt_calendar_phase` | A, B, C giữ nguyên. D: `last_year = analysis_end_year`, chênh mùa tính lại. Khoảng bỏ-một-năm dòng 85–88: tắt |
| `assert_rpt_direction` | Mốc 2016–2017 và dòng 71–73 giữ nguyên. Ba dòng `len` có cờ giữ tới cuối dữ liệu (59–61): tắt |
| `assert_rpt_driver` | Năm 2019 và giai đoạn A, B, C giữ nguyên. Giai đoạn D và dòng 164 (`delta_r_is_small`): tắt |
| `assert_rpt_forecast` | CTE `actual` chỉ lấy ngày `<= forecast_trained_through`, số còn lại không đổi |
| `assert_rpt_forecast_actual` | Giới hạn **cả hai vế** về `<= forecast_trained_through`, vì `stg_sales` có cả 2023 |

**Thêm test mới `tests/assert_ky_dot.sql`**, chỉ bật khi `co_dot`:

- năm mới: G và COGS theo ngày khớp `stg_sales` của năm đó, đủ ngày, không trùng `date_sk`;
- dòng dự báo của `fact_daily_sales` **đúng bằng** các ngày `sample_submission` sau `last_actual_date`. Số dòng tổng vẫn 4.381† nên phép đếm không bắt được lọc sai;
- `dim_date.is_forecast_period` đúng với các ngày đó;
- `rpt_revenue_total` dòng kỳ mới bằng cộng các năm; `rpt_forecast_actual` dừng ở `forecast_trained_through`.

Thêm mô tả vào `tests/_singular_tests.yml`, vì thiếu mô tả sẽ không hiện trên trang Sức khỏe dữ liệu.

## 4. Dự báo đứng yên

Dòng lệnh mới, chỉ cho stage `forecast`:

```text
python -m scripts.pipeline.cli forecast --run-id <id> --root <thu muc> --du-bao-tu <release_id>
```

| Trường hợp | Kết quả |
|---|---|
| Snapshot có đợt, thiếu `--du-bao-tu` | `ValueError`, nói rõ cần bản nguồn |
| Snapshot không đợt, có `--du-bao-tu` | `ValueError` trong `_execute` (parser chưa biết snapshot nên không dùng được `ap.error`) |
| Snapshot không đợt, không có tham số | `stage.run` như cũ |

Viết ở module mới `scripts/pipeline/du_bao_dot.py`. **Không train.** Trước khi chép phải kiểm đủ, sai là `ValueError`:

1. Bản nguồn có trong registry của cùng `--root`, `status = ready`, `target = duckdb`.
2. Snapshot của bản nguồn **không có đợt**.
3. `forecast_meta.json` của nguồn tồn tại, mọi file khớp `sha256`, `model_version` bằng `stage.model_version()`.
4. `sales` của snapshot nguồn **trùng từng dòng** với `sales` của snapshot đợt ở các ngày `<= trained_through`, và nguồn không có ngày nào sau đó. Kiểm bằng DuckDB `threads=2`, `memory_limit='2GB'`.
5. Mọi dòng dự báo có `trained_through` duy nhất; ngày đầu đợt là ngày ngay sau đó.
6. Vẫn còn ngày dự báo sau `last_actual_date`.

Rồi chép ba parquet nguyên byte sang `runs/<id>/forecast` bằng thư mục tạm và `os.replace`, như `stage.run`. Meta mới: `snapshot_id` của run, `model_version`, `run_id`, `sha256`, các khóa `check_forecast` cần, thêm `nguon_du_bao` gồm `release_id`, `snapshot_id`, `run_id`. `check_forecast` (`cli.py:101`) **không sửa** và phải đạt. Chạy lại stage cùng `run_id` không chép lại nếu đã đúng.

Ghi `nguon_du_bao` vào `context['forecast']`.

## 5. Mở và chặn stage

Chỗ chặn hiện tại ở `cli.py:423`.

| Stage, snapshot có đợt | Sau D3 |
|---|---|
| `forecast`, `build`, `validate` | Được chạy |
| `publish` | **Vẫn chặn**, thông báo nói rõ D5 |
| `rollback` về bản có đợt | **Chặn mới** |

**Vì sao chặn rollback:** `validate` đăng ký bản là `ready`, và trang Duyệt liệt kê mọi bản `ready` để rollback, nên không chặn thì bản có đợt thành bản đang xem mà không qua `publish`. Thêm vào nhánh rollback (`cli.py:553–568`): đọc `snapshots/<snapshot_id>/manifest.json` của bản đích; có `dot` thì từ chối, không ghi `rollbacks/`. Không có file manifest thì xử lý như hiện nay (đường Databricks). Bản không đợt rollback y như cũ.

Không tự công bố: `RETAIL_PIPELINE_DEFAULT_EXTENSIONS`, DAG, `nhap_runner` không đổi.

## 6. Sửa lỗi retry `prepare --snapshot-id` (tồn từ D2)

**Lỗi:** tạo run bằng `prepare --dot`, rồi chạy lại cùng `run_id` bằng `prepare --snapshot-id` thì báo exit 2 "danh sách --dot khác" (`cli.py:358`), vì context có đợt mà dòng lệnh này không được nhận `--dot`. Lỗi an toàn vì dừng, không làm sai số, nhưng retry theo `--snapshot-id` sẽ trượt.

**Sửa, trong nhánh `context_path.exists()` (`cli.py:348–360`):**

- Có `snapshot_id` và context có `dot`: yêu cầu `context['snapshot_id'] == snapshot_id`, khác thì `ValueError('run_id đã dùng cho snapshot khác')`; bỏ qua phép so `ma_dot`, vì `dot_sha256` trong manifest đã niêm phong danh sách đợt.
- Không có `snapshot_id`: so `ma_dot` như hiện nay. Chạy lại không kèm `--dot` trên run có đợt vẫn báo lỗi.
- Run không đợt: **giữ y hệt**, kể cả việc hiện chưa so `snapshot_id` khi retry. Claude ghi nhận khoảng trống này, không sửa ở phiếu này.

## 7. Test bắt buộc và lệnh chạy

Test mới ở `scripts/pipeline/tests/test_d3_ky_dot.py` và `test_d3_du_bao.py`, dùng dữ liệu nhỏ tự dựng, không đọc dữ liệu thật. Theo mẫu `test_shipments_dbt.py` để chạy SQL mà không cần build cả kho.

- **T1.** Render mọi model và test trong §3 với biến mặc định: trùng từng byte bản trước D3 (so với `git show HEAD:<file>` render cùng cách).
- **T2.** `ky_cua_ban`: 2023-12-31 ra 2023; ngày cuối khác 31/12 báo lỗi; không viết cứng năm.
- **T3.** `dbt_build`: không đợt thì JSON `--vars` y như cũ; có đợt thì đủ 4 biến.
- **T4.** `fact_daily_sales`, `dim_date`: chạy SQL trên DuckDB nhỏ có đợt; làm hỏng bộ lọc thì `assert_ky_dot` phải bắt được.
- **T5.** `rpt_revenue_total` có 3 kỳ khi có đợt; 2 kỳ khi không.
- **T6.** Giai đoạn cuối kéo tới năm mới, các giai đoạn khác không đổi.
- **T7.** `du_bao_dot`: mỗi điều kiện §4 mục 1–6 có một ca hỏng riêng và phải báo lỗi; ca đạt thì `check_forecast` đạt, ba parquet trùng byte nguồn, có `nguon_du_bao`; chạy lại không đổi file.
- **T8.** Không đợt có `--du-bao-tu` lỗi; có đợt thiếu tham số lỗi; không đợt không tham số gọi `stage.run`.
- **T9.** `publish` và `rollback` về bản có đợt đều bị từ chối, kho và `rollbacks/` không đổi; rollback bản không đợt vẫn đạt.
- **T10.** Retry §6: tạo bằng `--dot` rồi retry `--snapshot-id` đúng id thì trả context cũ; khác id thì lỗi; retry không kèm `--dot` thì lỗi; retry `--dot` y như cũ vẫn idempotent; run không đợt không đổi hành vi.
- **T11.** `git diff` không chạm `scripts/forecast/`, `source_contract.py`, `dot.py`, `extensions/`; `stage.model_version()` trước và sau bằng nhau.

Test D2 đang khẳng định `forecast`, `build` bị chặn trên snapshot có đợt được sửa theo §5, nêu rõ ở §9. Không sửa kỳ vọng nào khác.

```text
python -m pytest scripts/pipeline/tests -q
python -m pytest scripts/ingest/tests -q
python -m pytest apps/retail_app/tests/test_extension_grants.py apps/retail_app/tests/test_nhap_du_lieu.py apps/retail_app/tests/test_nhap_tu_dong.py -q
```

Chạy từng lệnh riêng; không gộp `apps` với `scripts` vì trùng `conftest`.

## 8. Nghiệm thu

**PM chạy bằng script Claude viết, ngoài Claude Code:** một lượt không đợt rồi một lượt có đợt, cùng `--root`, mỗi lượt có `orders_enriched` và `shipments_realistic`.

**Claude tự kiểm, không dùng test của GPT làm bằng chứng duy nhất:**

1. **Không đợt:** SQL biên dịch trùng `D:/retail-analytics-am` lúc trước D3 ở ba cấu hình (không mở rộng, `orders_enriched`, cả hai), che `built_at_utc`. `snapshot_id` giữ `5bd9a84aaf73`, `47e7cbe765d9`, `086effe8607b`. `model_version` không đổi. G, COGS từng ngày lệch 0.
2. **Có đợt, số cũ không đổi:** so bản có đợt với bản không đợt trên mọi bảng marts và reporting: dòng thuộc năm hoặc tháng `<= 2022` phải **giống từng ô**, không có ngoại lệ ngầm.
3. **Có đợt, phần được phép đổi** chỉ gồm: dòng kỳ mới của `rpt_revenue_total` và bridge của nó; giai đoạn cuối PS2 ở `rpt_revenue_phase`, `rpt_calendar_phase`, `rpt_driver_period`; `rpt_calendar_stability`; `rpt_august_parity`; cờ cuối dữ liệu ở `rpt_revenue_direction*`. Khác ở chỗ ngoài danh sách thì dừng và báo.
4. **2023 đối chứng độc lập:** `fact_daily_sales` 2023 trùng `data_demo/dot_2023_kiem/sales_doi_chung.csv`, file này sinh từ `sales.csv` gốc qua `anh_xa_ngay.csv`. Cổng `validate` không đủ, vì so với `sales.parquet` mà `dot.py` tính bằng cùng công thức.
5. **Số dòng kỳ vọng†:** `fact_order` 685.033, `fact_order_item` 755.345, `fact_return` 42.197, `fact_review` 119.930, `fact_inventory_snapshot` 65.840, `fact_web_traffic` 4.017, `fact_daily_sales` 4.381 (4.198 thực tế + 183 dự báo).
6. **Dự báo:** `rpt_forecast_daily` trùng bản nguồn; `rpt_forecast_actual` dừng ở 2022-12-31; `submission.csv` không đổi.
7. **Chặn:** `publish` và `rollback` về bản có đợt đều dừng; bản đang xem không đổi.
8. Làm hỏng từng mệnh đề §3–§6; đột biến nào sống thì coi như chưa kiểm.

**Chưa chứng minh sau D3:** chạy trên Postgres và Databricks; hiển thị trên app (D5).

## 9. Kết quả (Claude code và tự kiểm, 2026-11-06)

**Lệch so với phiếu:**
- `dim_promotion`: đợt có `promotions.csv` được nối vào nguồn lõi, nên số dòng kỳ vọng tăng theo đợt (`50 + số dòng đợt`, tức 71†), không giữ số cũ như §3.3 viết ban đầu.
- `bridge_item_promo` ở bản có đợt đếm từ `stg_order_items` thay cho số cứng.
- Tên macro là `ps2_phases_ky`, kèm `co_dot`, `ky_cuoi`, `dot_so_dong` trong `retail_dbt/macros/ky.sql`.

**Đã kiểm, chưa cần dữ liệu thật:**
- SQL biên dịch không đợt giống hệt `49d3454` ở 4 cấu hình (không mở rộng, có dự báo, `orders_enriched`, hai mở rộng), che `built_at_utc`.
- `scripts/pipeline/tests`: 254 đạt, 2 bỏ qua; test mới `test_d3_du_bao.py`, `test_d3_ky_dot.py`.
- `scripts/ingest/tests`: 302 đạt, 28 bỏ qua; 7 ca lỗi vì worktree này không có `data/student_data`. D3 không đổi file nào trong `scripts/ingest`.
- Test app (`test_extension_grants`, `test_nhap_du_lieu`, `test_nhap_tu_dong`) ở worktree này: 239 đạt, 7 trượt. 7 ca đó là test trang và trượt y hệt ở `49d3454`; D3 không đổi file nào trong `apps/`. Nguyên nhân: worktree không có `data/` nên `nhap_kha_dung()` là `False` và trang dừng sớm.
- 29 đột biến: test bắt cả 29. Trong đó 24 ở `du_bao_dot.py`, `cli.py`; 5 ở model, macro và `assert_row_counts`. **Chưa có đột biến nào trên các `assert_*.sql` khác.** Các nhánh `co_dot` trong đó, gồm những số khóa bị tắt khi có đợt, chỉ chạy ở lượt thật.
- Trong lúc kiểm tìm ra một lỗi của chính D3 và đã sửa: rollback về bản ghi registry không có `snapshot_id` bị `KeyError`.

**Cách so "giống từng ô" ở `d3_kiem.py`:** cột `double` so sau khi làm tròn 9 chữ số, vì hai bản cùng dữ liệu vẫn lệch ở chữ số rất nhỏ. 9 là mức chặt nhất đã thử: hai bản cùng dữ liệu `a52ba6b5` và `67a380a8` khớp ở 9 và 6 chữ số, không làm tròn thì lệch.

**Lượt thật 1 (PM chạy, 2026-11-06, run `d3-dot`):**
- Các bước trước build đều đạt. Bản gốc ra snapshot `086effe8607b`, trùng bản hai mở rộng trước đây. `prepare` có đợt, retry `prepare --snapshot-id` (lỗi tồn từ D2) và `forecast --du-bao-tu` cũng đạt.
- `build` dừng: dbt 235 đạt, 2 test trượt. Cả hai trượt vì test ghi cứng theo kỳ 2013–2022, không phải vì số sai:
  - `assert_rpt_calendar_phase` (luật độ ổn định) ghi cứng `n_years <> 10`, trong khi kỳ có đợt có 11 năm. Các điều kiện khác của luật vẫn đạt: giá trị cả kỳ khớp `rpt_revenue_total` và `rpt_august_parity`, và nằm trong khoảng bỏ-từng-năm. Đã sửa thành số năm theo kỳ (`ky_cuoi() - 2012`).
  - `assert_rpt_driver` (luật 7b, tách thẳng so với cộng dồn từng năm): giai đoạn D 2019–2023 lệch N +10,47 triệu, P −12,78 triệu, vượt ngưỡng 5 triệu đo ngày 2026-09-29 trên D 2019–2022. Kết luận vẫn giống: kéo lên là P, kéo xuống là N. A, B, C không đổi. Đã sửa: khi có đợt, D bỏ ngưỡng 5 triệu nhưng vẫn phải cùng kết luận; A, B, C giữ ngưỡng. **Đây là nới một ngưỡng thực nghiệm; PM đồng ý 2026-11-06.**
- Đã kiểm hai luật mới trên chính kho `d3-dot`: đều đạt. Đổi số năm thành 12 thì luật bắt lỗi. Test D3 có 52 đạt; SQL không đợt vẫn giống hệt `49d3454`.
- Code đổi giữa các stage nên run cũ không chạy tiếp được. `d3_chay.py` chuyển sang run `d3-dot2`.

**Lượt thật 2 (PM chạy, 2026-11-06, run `d3-dot2`, DuckDB), log ở `C:/Users/Win/am_kiem/d3_luot/ket_qua.log`:**
- `prepare` (snapshot `12cd64e18aae`), retry `prepare`, `forecast --du-bao-tu`, `build`, `validate` đều đạt, release `0bce3b72b734452ca89a2f5b`.
- §8.7: `publish` dừng với "snapshot có đợt chưa dùng được ở stage này (D5)"; `rollback` về bản có đợt dừng với "Bản có đợt chưa được đưa thành bản đang xem (D5)"; bản đang xem vẫn là bản gốc.
- §8.2: mọi bảng marts và reporting giống từng ô ở phần `<= 2022` (cột double làm tròn 9 chữ số), trừ 4 bảng thuộc danh sách §8.3 được phép đổi:
  - `rpt_calendar_stability` 3 dòng (3 nhịp, giờ tính trên 11 năm);
  - `rpt_august_parity` 1 dòng (thêm tháng 8/2023, năm lẻ);
  - `rpt_revenue_direction` 24 dòng, đều là tháng 2022-02 → 2022-12: chuỗi "lên" kéo dài sang 2023 nên độ dài chuỗi tăng;
  - `rpt_revenue_direction_change` 3 dòng: `months_held` tăng 12 (13 → 25, 11 → 23, 8 → 20), vẫn "giữ tới cuối dữ liệu", hướng không đổi.
  
  `rpt_revenue_turning_point` nằm trong danh sách được đổi nhưng không đổi.
- §8.4: `fact_daily_sales` 2023 khớp `sales_doi_chung.csv` cả 365 ngày, lệch 0.
- §8.5: số dòng đúng cả 7 bảng fact và `dim_promotion` 71; thực tế 4.198 + dự báo 183; `rpt_revenue_total` 3 dòng; `rpt_build_info` kỳ tới 2023, dữ liệu tới 2023-12-31.
- §8.6: ba file `forecast_*.parquet` trùng byte bản gốc; `rpt_forecast_actual` dừng ở 2022-12-31 (3.833 dòng); `trained_through` 2022-12-31; context ghi `co_du_lieu_tong_hop`.
- Sau khi sửa hai test: `scripts/pipeline/tests` 256 đạt, 2 bỏ qua.

**Chưa chứng minh:**
- `submission.csv` không đổi (§8.6): script chưa so file này.
- §8.1 lượt chạy thật mới so `snapshot_id`. SQL giống byte thì đã kiểm, còn `model_version` và G/COGS từng ngày chưa so trên kho thật.
- §8.8: chưa làm hỏng thử các nhánh `co_dot` trong các `assert_*.sql`. Lượt thật chỉ cho thấy các nhánh này đạt, chưa cho thấy chúng bắt được lỗi.
- Postgres, Databricks, hiển thị trên app (D5).

## 10. PM cần chốt trước khi giao

1. **Gộp `auto-mapping/myuyen` vào `nap-ky/myuyen` trước khi giao.** Lý do: `dot_2023` có `shipments_realistic.csv`, nhưng hợp đồng nguồn này chỉ có ở nhánh auto mapping; không gộp thì đường "đợt + hai nguồn mở rộng" phải tới D5 mới chạy lần đầu. Đã thử `git merge-tree`, không có xung đột. **Đề xuất: gộp.**
2. **Đợt chưa đủ năm: tạm chặn ở D3.** Thiết kế §8 câu 6 đã chốt hiện kèm nhãn "chưa đủ năm", nhưng demo chỉ dùng trọn năm 2023 và phiếu này không có dữ liệu thử để kiểm đường đó. Chặn thì không có đường chạy chưa kiểm. **Đề xuất: chặn, làm khi có nhu cầu.**
3. **Giữ cả kỳ cũ khi có đợt:** bản có đợt có 3 kỳ: `2012-2022`, `2013-2022`, `2013-2023`; kỳ phân tích chính là `2013-2023`, đúng §8 câu 4. Giữ hai kỳ cũ để kiểm trực tiếp "số cũ không đổi một đồng". App cũ đọc `'2013-2022'` thì vẫn ra số đúng cho tới khi D5 đổi nhãn.
