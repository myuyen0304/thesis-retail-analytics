# Giao việc L3: đợt 2024 (bộ sinh dữ liệu, nới dải ngày dbt, chế độ không dự báo)

Soạn ngày 2026-11-09, Claude. GPT code §3–§5. Claude rà độc lập trước khi commit; chưa đạt thì ghi vào §8 để GPT sửa.
Thiết kế gốc: [thiet_ke_dot_web_public.md](thiet_ke_dot_web_public.md), các mục §8, §9, §13 Mốc 2, §14 lát L3 và L4. PM đã chốt: 2024 là đủ năm, bản có đợt 2024 không có bảng dự báo (Q5).

**Phiếu này gộp L3 và L4.** Phần dbt nằm trong phần băm và đóng băng sau cửa sổ bảo trì, mà chỉ có thể kiểm thật bằng dữ liệu 2024 do bộ sinh tạo ra. Vì vậy bộ sinh phải chạy được trước cửa sổ.

**Điều kiện bắt đầu:** L2 đã được Claude rà đạt và commit. L2 và L3 cùng sửa `scripts/pipeline/cli.py`, `du_bao_dot.py`; không làm song song.

Đọc trước:
- `AGENTS.md`, `CLAUDE.md` §5 (nhất là điểm 6: Urban Blowout năm lẻ), `docs/agent_workflows.md`;
- thiết kế ở trên;
- `scripts/demo/sinh_dot_2023.py`, `scripts/demo/tests/test_sinh_dot_2023.py`;
- `scripts/pipeline/du_bao_dot.py`, `scripts/pipeline/cli.py` (stage `forecast`, `build`);
- `retail_dbt/macros/ky.sql`, `retail_dbt/models/marts/dim_date.sql`, `fact_daily_sales.sql`, `retail_dbt/tests/assert_row_counts.sql`, `assert_rpt_calendar.sql`, `assert_ky_dot.sql`;
- `scripts/pipeline/tests/test_d3_ky_dot.py`, `test_d3_du_bao.py`.

## 0. Việc này là gì

Mốc 2: `chushop` gửi đợt 2024 → chuỗi là gốc + 2023 + 2024 → PS hiện kỳ `2013-2024`.
Ba phần:
- **A:** bộ sinh tạo được bộ 2024 đúng các ràng buộc;
- **B:** dbt build được khi dữ liệu thực tế vượt 2024-07-01, còn không đợt thì SQL **y hệt từng byte**;
- **C:** bản có đợt 2024 không có bảng dự báo, và pipeline chạy thông ở chế độ đó.

## 1. Bẫy phải tránh

1. **`dim_date` phải phủ cả các ngày sau cuối năm.** Thiết kế §9.2 ghi "4.749 dòng nếu tới 2024-12-31" là **chưa đủ**. Bộ 2023 thật có ngày trả hàng tới `2024-01-28` và ngày đánh giá tới `2024-02-06` (Claude đo ngày 2026-11-09 trên `data_demo/dot_2023`), và `shipments` có thể vượt cuối năm tương tự. Bộ 2024 sẽ tràn sang đầu 2025, và test `relationships` tới `dim_date` (`_marts.yml:85–89` cùng các dòng khác) sẽ trượt. Bộ 2023 không gặp chuyện này chỉ vì dải đang tới 2024-07-01. Cách xử lý ở §3.4.
2. **Không đợt thì y hệt.** `test_no_batch_sql_is_byte_identical` đang khóa việc này. Số dòng 4566 và 4381 không được đổi khi không có đợt.
3. **Đợt 2023 cũng phải y hệt như trước L3**, trừ chỗ §3.4 ghi rõ. Dải 2023 giữ 4566 dòng, `fact_daily_sales` 4381 dòng.
4. **`--nam 2023` phải sinh ra bộ trùng byte với bộ cũ**, cùng seed. Đổi thứ tự lấy mẫu `rng` là hỏng bộ đã dùng cho D3, D5.
5. **Năm chẵn không có Urban Blowout.** Bộ 2024 lấy mẫu từ năm lẻ trong hai cửa sổ khuyến mãi là sai dữ liệu (`CLAUDE.md` §5 điểm 6). Nghiệm thu Mốc 2 mục 2 kiểm tháng 8/2024 không có hiện tượng này.
6. **Không có bảng dự báo không được làm lỗi trang nào.** `rpt_forecast_*` là bảng tùy chọn với quyền đọc (`dbt_project.yml:40–50`), nhưng phải tự kiểm các trang có đọc dòng dự báo của `fact_daily_sales` không.
7. **Không có năm 2025 trên trang nào.** `dim_date` nới tới 2025 chỉ để khóa ngoại đạt. Mọi trang PS, Tổng quan phải dừng ở `ky_cuoi()` = 2024.
8. **Không dùng dữ liệu tổng hợp cho kết luận báo cáo.** Bộ này chỉ phục vụ demo, luôn kèm băng rôn.

## 2. Môi trường và ràng buộc

- **Worktree** `D:\retail-analytics-nap`, nhánh `nap-ky/myuyen`.
- Python: `D:/retail-analytics/.venv/Scripts/python.exe -B -X utf8`. Biến `RETAIL_TEST_DATABRICKS=0`.
- **Không commit, không push.** Không kết nối Databricks, không chạy Docker. Không đọc `.env.*.local`, `.streamlit/secrets.toml`.
- **Không chạy `dbt build` toàn bộ hay `cli run`.** Việc nặng do PM chạy theo script Claude viết (§6). GPT dùng `dbt compile` với `--vars` như `test_d3_ky_dot.py`.
- **Không commit `data/`, `data_demo/`, `warehouse/`.**
- **Chỉ sửa hoặc tạo các file ở §4.** Không sửa `scripts/ingest/dot.py`, `scripts/ingest/source_contract.py`, `scripts/forecast/*`, seed, `docs/phan_quyen.md`. Không sửa số khóa chỉ để test xanh.
- Junction `data` chỉ tạo khi test cần: `cmd /c mklink /J data D:\retail-analytics-am\data`; gỡ bằng `cmd /c rmdir data`. **Không dùng `Remove-Item -Recurse`.**

## 3. Thiết kế

### 3.1 Phần A: bộ sinh (`scripts/demo/sinh_dot_2023.py`)

File nằm ngoài phần băm. Giữ tên file. Thêm tham số:

```
--nam 2023|2024 (mặc định 2023)
--dot-truoc <thư mục> (lặp được; các đợt đã nối trước đợt này, theo thứ tự)
```

Mặc định `--ra`, `--kiem`, `--seed` theo `--nam`: `data_demo/dot_<nam>`, `data_demo/dot_<nam>_kiem`, seed = năm. `--nam 2023` không có `--dot-truoc` thì mọi thứ như cũ.

| Chỗ | Hiện tại | Đổi |
|---|---|---|
| `day_mapping` `:75–82` | 365 ngày của 2023; cửa sổ năm lẻ lấy mẫu `(2019, 2021)` | Theo số ngày của năm. Năm lẻ giữ nguyên từng phép gọi `rng`. Năm chẵn: trong hai cửa sổ `30/01–01/03`, `30/07–02/09` chỉ lấy mẫu từ `(2020, 2022)`; ngoài cửa sổ lấy từ `(2019, 2020, 2021, 2022)` |
| `:80` `target.replace(year=…)` | Lỗi ở `2024-02-29` khi năm mẫu không nhuận | Ngày 29/2 chỉ lấy mẫu năm 2020 (năm chẵn và nhuận trong cửa sổ) |
| `:156` | `' 2023 mau '` | Theo `--nam` |
| `:191–195`, `:199–` | Tồn kho, lưu lượng năm 2023 | Theo `--nam`; `monthrange` đúng tháng 2 nhuận; `web_traffic` đủ 366 ngày |
| `:233–242` | JSON theo mốc 2023 | Theo `--nam` |
| `max_id` `:110`, `:116`, `:127` | Chỉ lấy mã lớn nhất từ dữ liệu gốc | Lấy lớn nhất từ dữ liệu gốc **và** mọi `--dot-truoc`. Nếu không, `check_batch` báo `D2-1` |
| `validate` `:255–` | Mốc `2022-12-31` ở K3; K5 so với mapping | K3 dùng ngày cuối của đợt trước (hoặc `2022-12-31` nếu không có). Thêm kiểm trùng mã với `--dot-truoc` |
| `anh_xa_ngay.csv` `:400` | Cột `ngay_2023` | `ngay_<nam>` |

Thêm cổng mới, chỉ khi `--nam` chẵn:
- **K9:** mọi ngày mẫu trong hai cửa sổ thuộc năm chẵn; `COGS/Revenue` theo tháng 8 < 1.
- **K10:** `count(distinct order_date)` = 366 khi 2024 (`check_batch` đòi đủ ngày, `dot.py:163`).

Điều kiện `D2-2` của `check_batch` cần **mọi ngày sau mốc cắt**: ngày đơn, giao, trả, đánh giá của 2024 phải sau 2023-12-31. Ngày của đợt 2023 vượt sang 2024 không vi phạm, vì `check_batch` chỉ xét đợt đang nối.

**Trùng khóa do tràn năm:** `check_batch` kiểm `D2-8` trên `base + new`. Tồn kho theo tháng và lưu lượng theo ngày phải không trùng khóa với bộ trước.

### 3.2 Phần C: chế độ không dự báo (`scripts/pipeline/du_bao_dot.py`, `cli.py`)

Thiết kế §9.3.

- **`ky_cua_ban`:** bỏ `raise` ở `:44–45`. Trả thêm `khong_du_bao: last >= LICH_CUOI`. Vẫn đòi kết thúc 31/12 (`:42`).
- **`bien_dbt`:** nếu không có `forecast_path` trong context thì không truyền `forecast_trained_through`. Cộng thêm `dim_date_cuoi` (§3.4).
- **`dung_lai`:** không đổi đường có dự báo. Hàm mới `khong_du_bao(context)` trả metadata tối thiểu, không ghi file vào `forecast/`.
- **`cli.py`, stage `forecast`:** snapshot có đợt và `ky_cua_ban` báo `khong_du_bao` thì đặt `context['stage'] = 'forecasted'`, `context['khong_du_bao'] = True`, **không** đặt `forecast_path`. Vẫn đòi `--du-bao-tu` để giao diện lệnh giống nhau, nhưng không đọc tới bản nguồn. Đường hiện có không đổi.
- **`cli.py`, stage `build`:** có `khong_du_bao` thì bỏ `check_forecast` và `cloud.ingest_forecast`. `dbt_build` đã tự bỏ `forecast_path` qua `.get` (`:47`). `rpt_forecast_*` tắt theo biến này.
- **Quyền:** `consumers()` và `present()` đã xử lý bảng tùy chọn, không cần sửa. Test phải chứng minh.
- `validate_data` so `fact_daily_sales where is_actual` với `sales.parquet`, đã đúng cho trường hợp 0 dòng dự báo.

### 3.3 Phần B: các chỗ theo dải ngày

Chỉ đổi khi `co_dot()`. **Khi không đợt, SQL biên dịch không đổi một byte**, kể cả comment.

| Chỗ | Khi `co_dot` |
|---|---|
| `retail_dbt/models/marts/dim_date.sql:5` | `integers(so_ngay_dim_date())` thay cho `4566` (§3.4) |
| `retail_dbt/models/marts/_marts.yml:9` | Ghi thêm dải khi có đợt |
| `retail_dbt/tests/assert_row_counts.sql:3` | `dim_date` = `so_ngay_dim_date()` |
| `retail_dbt/tests/assert_row_counts.sql:6` | `fact_daily_sales` = số ngày thực tế + số ngày dự báo. 2023: 4.198 + 183 = 4.381. 2024: 4.564 + 0 = 4.564. Tính từ `last_actual_date` |
| `retail_dbt/tests/assert_rpt_calendar.sql:45` | `full_date < ` ngày đầu tháng kế của `dim_date_cuoi`; không đợt giữ nguyên `2024-07-01` |
| `retail_dbt/models/reporting/_forecast.yml:14` | Chỉ sửa mô tả |
| `rpt_driver_period.sql:2`, `apps/retail_app/views/ps4_don_mon_gia.py:30` | Chú thích cũ về kỳ |

Kiểm thêm và ghi kết quả vào báo cáo, sửa nếu sai:
- `fact_daily_sales.sql:19–20`: không còn dòng dự báo;
- `assert_ky_dot.sql` với `last_actual_date = 2024-12-31`;
- mọi `assert_*` có năm hay ngày ghi cứng: `grep -n "202[2-4]" retail_dbt/tests retail_dbt/models`, liệt kê từng dòng và lý do giữ hoặc đổi. `is_urban_blowout` ở `dim_date` không đổi.
- `is_forecast_period` của `dim_date` là `full_date > last_actual_date`, tức các ngày đầu 2025 mang cờ dự báo mà không có dòng dự báo nào. Kiểm không model hay trang nào coi "có ngày dự báo" là "có dòng dự báo".

### 3.4 Dải `dim_date` theo dữ liệu

- `du_bao_dot.ky_cua_ban` tính thêm `dim_date_cuoi`, ngày lớn nhất trong các cột ngày của snapshot: `order_date`, `ship_date`, `delivery_date`, `return_date`, `review_date`, `snapshot_date`, `date`, đọc từ parquet bằng duckdb, **làm tròn lên cuối tháng**, và không nhỏ hơn `2024-07-01`.
- Macro mới `so_ngay_dim_date()` trong `retail_dbt/macros/ky.sql`: không đợt trả `4566`; có đợt tính `(dim_date_cuoi − 2012-01-01) + 1` bằng Jinja `modules.datetime`.
- `integers(n)` hỗ trợ tới 9999 (`macros/cross_db.sql:57–61`), đủ.

Ví dụ phải khớp trong test: bộ 2023 thật: ngày lớn nhất 2024-02-06 → `2024-07-01` → **4566** (đúng số cũ). Bộ 2024 kết thúc ví dụ 2025-02-06 → `2025-02-28` → **4808**.

### 3.5 App

Không thêm logic mới nếu không cần. Trang phải đúng với bản 2013–2024, 0 dòng dự báo:
- `period_label` (`common.py:264–271`) tự ra `2013-2024`;
- Tổng quan, PS1–PS5, Sức khỏe dữ liệu không lỗi, không có năm 2025;
- trang Dự báo vẫn đọc `active`, không đổi;
- khung AI: năm 2023, 2024 ẩn; năm ≤ năm cuối của `active` vẫn hiện (L1 §3.9).

Hai lỗi chữ hiển thị PM thấy khi nghiệm thu D5a (`docs/giao_viec_d5_cong_bo_dot.md` §11, ghi nhận (h), (i)). Sửa ở phiếu này vì `apps/retail_app` đóng băng sau cửa sổ bảo trì:

1. **Nhãn kỳ** (`period_label`, `common.py`): với bản có cờ tổng hợp, cả `2012-2022` và `2013-2022` khi không phải kỳ phân tích đều ghi `(kỳ gốc, số thật)`. Chỉ áp cho đúng hai mã này. Bản không cờ giữ nguyên như cũ, `2012–2022` vẫn là `(toàn bộ dữ liệu)`.
2. **Ngày trong chú thích** (`page_header`, `common.py`, hai nhánh Hỏi dữ liệu và Dự báo): dùng `_d(end)`, ra dạng `31/12/2022`, không còn `00:00:00`.

## 4. File được sửa

| File | Phần băm | Việc |
|---|---|---|
| `scripts/demo/sinh_dot_2023.py`, `scripts/demo/tests/test_sinh_dot_2023.py` | không | §3.1 |
| `scripts/pipeline/du_bao_dot.py`, `scripts/pipeline/cli.py` | có | §3.2, §3.4 |
| `retail_dbt/macros/ky.sql` | có | §3.4 |
| `retail_dbt/models/marts/dim_date.sql`, `_marts.yml` | có | §3.3 |
| `retail_dbt/tests/assert_row_counts.sql`, `assert_rpt_calendar.sql` | có | §3.3 |
| `retail_dbt/models/reporting/_forecast.yml`, `rpt_driver_period.sql` | có | chú thích |
| `apps/retail_app/views/ps4_don_mon_gia.py` | có | chú thích |
| `scripts/pipeline/tests/test_d3_ky_dot.py`, `test_d3_du_bao.py` | có | thêm ca; chỉ sửa ca đang khóa `raise` ở `:44–45`, ghi rõ trong báo cáo |
| `scripts/pipeline/tests/test_l3_khong_du_bao.py` (mới) | có | §5 |
| `apps/retail_app/tests/test_l3_trang_2024.py` (mới) | có | §5 mục 6 |
| `apps/retail_app/ui/common.py` | có | §3.5, hai lỗi chữ |
| `apps/retail_app/tests/test_d5_dashboard.py` | có | chỉ sửa ca T8 ở `:160` theo nhãn mới; ca bản không cờ ở `:154` và `:163` giữ nguyên |
| `apps/retail_app/tests/test_l1_dot_web.py` | có | chỉ sửa `:418` và `:423`: dữ liệu giả dùng `pd.Timestamp('2022-12-31')`, kiểm `số tới 31/12/2022` và không có `00:00:00` |

Chỗ khác cần sửa theo §3.3 mục "kiểm thêm" thì **ghi vào báo cáo trước khi sửa**, nêu dòng và lý do.

## 5. Kiểm

1. **Bộ sinh:**
   - `--nam 2023` trên dữ liệu test nhỏ: trùng byte với kết quả trước khi sửa (chụp hash trước khi sửa);
   - `--nam 2024` ra đủ 366 ngày đơn, không lỗi ở 29/2; ngày mẫu trong cửa sổ thuộc `(2020, 2022)`; K9, K10 chạy; `--dot-truoc` làm mã bắt đầu sau mã lớn nhất của đợt trước;
   - cùng seed ra cùng bộ, khác seed ra khác;
   - `--nam` khác 2023, 2024 bị từ chối.
2. **Đợt nối được:** `dot.classify` và `check_batch` trên bộ nhỏ 2023 + 2024: không có D2-1, D2-2, D2-3, D2-8.
3. **dbt compile với `--vars`:**
   - không đợt: trùng byte với bản chụp trước khi sửa (`test_no_batch_sql_is_byte_identical`);
   - đợt 2023: `so_ngay_dim_date()` vẫn là 4566; SQL `dim_date`, `fact_daily_sales` như trước L3;
   - đợt 2024: `dim_date` dùng số ngày đúng; `rpt_forecast_*` tắt; không có `forecast_trained_through`;
   - `so_ngay_dim_date`: năm nhuận và các biên ở §3.4.
4. **Pipeline với cloud giả:**
   - stage `forecast` chế độ không dự báo: `stage = 'forecasted'`, `khong_du_bao`, không có `forecast_path`, **không đọc** bản nguồn;
   - `build`: không gọi `check_forecast`, `ingest_forecast`; có gọi `dbt_build`;
   - `validate`: `verify_consumers` chỉ đòi bảng dự báo khi có;
   - chạy lại stage giữ đúng trạng thái;
   - đợt 2023 vẫn đi đường cũ: có `forecast_path`, có `--du-bao-tu` được đọc;
   - đợt kết thúc giữa năm vẫn bị từ chối;
   - không đợt không đổi: `forecast_stage` vẫn được gọi.
5. **`dim_date_cuoi`:** snapshot giả có ngày đánh giá muộn hơn mọi ngày đơn: cột đó quyết định kết quả. Bỏ một cột khỏi danh sách thì test trượt.
6. **Trang**, bằng `AppTest`, `load_or_stop` giả trả dữ liệu 2013–2024 không có dòng dự báo:
   - Tổng quan, PS1–PS5, Sức khỏe dữ liệu không exception, không lỗi;
   - không có lựa chọn năm 2025 trong bộ lọc;
   - nhãn kỳ là `2013-2024`;
   - thẻ `2012–2022` và `2013–2022` ghi `(kỳ gốc, số thật)`, không còn `(toàn bộ dữ liệu)`;
   - khung AI đúng L1 §3.9 với năm 2024.
7. **Không hồi quy**, từng lệnh một, ghi số trước và sau khi sửa:
   - `scripts/demo/tests/test_sinh_dot_2023.py`;
   - `scripts/pipeline/tests/test_d3_ky_dot.py`, `test_d3_du_bao.py`, `test_d5_con_tro.py`, `test_snapshot_dot.py`, `test_l2_dot_cloud.py`;
   - `scripts/ingest/tests/test_dot.py`;
   - `apps/retail_app/tests/test_l1_dot_web.py`, `test_d5_dashboard.py`.

Claude sẽ thử đột biến khi rà, ít nhất gồm:
- `dim_date` dừng ở `last_actual_date`, không tính ngày trả, đánh giá;
- không làm tròn lên cuối tháng;
- `so_ngay_dim_date` đổi kết quả khi không đợt;
- `fact_daily_sales` đếm thừa số ngày dự báo khi hết vùng dự báo;
- cửa sổ năm chẵn lấy mẫu năm lẻ;
- bỏ cổng K9, K10;
- `max_id` bỏ `--dot-truoc`;
- `--nam 2023` đổi thứ tự `rng`;
- chế độ không dự báo vẫn đọc bản nguồn;
- `build` vẫn gọi `check_forecast`;
- bỏ chặn đợt giữa năm.

**Claude rà đợt thật sau khi PM chạy §6:** đối chiếu số dòng `dim_date`, `fact_daily_sales`, tổng G/COGS 2024 so với đối chứng của bộ sinh, không có tỷ lệ COGS/Revenue > 1 ở tháng 8/2024.

## 6. Không giao GPT

- Commit, push, PR, Databricks, Docker.
- **PM, trước cửa sổ, ngoài Claude Code, theo script Claude viết**, trên root riêng:
  1. Sinh `data_demo/dot_2024` với `--dot-truoc data_demo/dot_2023`.
  2. `cli run` target `duckdb`, 3 lượt: không đợt; đợt 2023; đợt 2023 + 2024. Đây là cửa kiểm chính của L3, vì `dbt build` mới chạy test `relationships` và các `assert_*` thật.
  3. Mở app local với bản 2023 + 2024, chụp Tổng quan, PS1–PS5.
- Vì `retail_dbt/` đóng băng sau cửa sổ, **3 lượt này phải đạt trước cửa sổ**. Lượt nào trượt vì lỗi dbt thì sửa và chạy lại trước khi dựng image.

## 7. Báo cáo của GPT khi xong (PM dán cho Claude rà)

- Danh sách file đã sửa; `git status --short`; `git diff --stat`.
- Số đạt/trượt/skip của từng file ở §5 mục 7, trước và sau khi sửa.
- Kết quả `grep` ở §3.3: từng dòng và lý do giữ hoặc đổi.
- Từng ca test cũ phải sửa và vì sao.
- Chỗ làm khác phiếu và lý do. Chỗ nào phiếu chưa rõ thì ghi câu hỏi, không tự đoán.

## 8. Rà của Claude (Claude ghi, GPT đọc để sửa)
