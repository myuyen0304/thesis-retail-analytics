# Thiết kế: nạp dữ liệu kỳ mới (năm 2023 tổng hợp) để dashboard PS tự cập nhật

Trạng thái: **đề xuất, chờ PM duyệt** (soạn 2026-10-31). Chưa code, chưa giao GPT. Duyệt xong mới tách phiếu giao việc theo lát (§6).
Số có dấu † là số khảo sát sơ bộ, chưa có cell/test chứng minh; mọi khẳng định khác dẫn `file:dòng`.

## 0. Yêu cầu và quyết định

- **Thầy hướng dẫn (PM báo 2026-10-31):** demo "nạp dữ liệu → dashboard tự cập nhật số liệu, biểu đồ doanh thu năm mới".
- Luồng nhập trên web ([giao_viec_nhap_du_lieu_ui.md](giao_viec_nhap_du_lieu_ui.md)) đã có nửa sau: app đọc bản đang công bố, nên
  công bố bản mới là trang đổi theo. Phần thiếu là **nạp giao dịch kỳ mới vào nguồn lõi**; hiện bị chặn có chủ ý
  ([tien_hoa_schema.md](tien_hoa_schema.md) §8).
- **PM chốt 2026-10-31:**
  1. Năm mới là **2023, dữ liệu tổng hợp (synthetic)**: không có giao dịch thật sau 2022-12-31 (CLAUDE.md §1).
  2. **Nhiều file trong một yêu cầu** (đợt giao dịch gồm nhiều bảng). Quyết định này **đảo** dòng "Không làm: nhiều file trong một
     yêu cầu" ở phiếu nhập UI §1, chỉ cho loại yêu cầu mới "đợt giao dịch kỳ mới".
  3. ~~Tắt dự báo ở root demo.~~ **Đổi cùng ngày (PM):** giữ dự báo; model **học lại trên toàn bộ số thực tế của bản** (gốc + đợt)
     và dự báo kỳ ngay sau ngày thực tế cuối (§4.5). File nộp Datathon vẫn sinh từ bản gốc, không đổi.
  4. **Kỳ phân tích theo dữ liệu (PM):** đợt có đủ bảng phục vụ metric PS thì năm mới hiện đầy đủ trên Tổng quan, PS1–PS5
     (§8 câu 4 đã chốt).
  5. **AI khi có dữ liệu mới (PM xác nhận đề xuất):**
     - **Model dự báo** tự học lại mỗi khi có bản dữ liệu mới: stage forecast train trên toàn bộ số thực tế của bản, chọn model theo
       luật đã đăng ký, không ai phải bấm gì; bản cũ dùng lại kết quả đã kiểm hash snapshot (`stage.py:135–139`). Làm ở lát D4.
     - **Chat AI (LLM) không train:** mỗi câu hỏi nó truy vấn bản đang công bố, nên dữ liệu mới là chat thấy ngay. Vướng duy nhất là
       chat coi "số thực tế dừng ở 2022-12-31" là luật. Bỏ các mốc ngày cứng và chạy lại bộ eval chat là **lát D6** (§4.7); chưa xong
       D6 thì chat ẩn ở bản có đợt.

- **PM đổi 2026-11-01 (mốc báo cáo 2026-12-12):**
  1. **Đợt 2023 tổng hợp được lên Databricks, nhưng chỉ ở catalog demo riêng** (cách A, §4.8), không bao giờ vào `retail_lab`.
     Thay dòng "chỉ local" ở bản trước.
  2. **Giữ dự báo đứng yên cho 12/12:** bản có đợt dùng lại kết quả dự báo của bản gốc, không train lại. Mục 3 và phần model của mục
     5 ở trên tạm gác, D4 và D6 làm sau 12/12 nếu còn thời gian. **PM cần xác nhận lại với thầy** vì dự báo là lõi GĐ2.

## 1. Ước lượng và ảnh hưởng lịch

**Lưu ý 2026-11-01:** ước lượng dưới đây tính cả D4, D6 và chỉ chạy local, chưa tính lại theo phạm vi mới.

D1–D5 khoảng **2–3 tuần**† (GPT code theo lát, Claude rà mỗi lát), nặng hơn ước lượng 1–2 tuần trước đó vì thêm bộ sinh dữ liệu,
xung đột với vùng dự báo 2023 và phải cô lập chat. D6 (chat theo kỳ, ~87 chỗ năm cứng + eval live) thêm khoảng **1 tuần**†.
Hạn báo cáo tháng 12; nếu bắt đầu đầu tháng 11 thì D1–D5 xong khoảng giữa–cuối tháng 11†, D6 sát đầu tháng 12† — nếu trễ, demo vẫn
chạy được với chat ẩn.

Đẩy lùi / chồng lấn: chạy lại P5 và duyệt P6 (~2026-11-05, không phụ thuộc phiếu này, vẫn làm song song); viết báo cáo; đóng băng
bản public ~2 tuần trước bảo vệ. Code đổi `retail_dbt`, `scripts/pipeline`, `apps/retail_app` nên đổi `code_version`
(`scripts/pipeline/cli.py:30`): chịu quy tắc đóng băng image (dựng lại một lần, sau P6 và sau script dọn bản cũ).

## 2. Ràng buộc

- **Dữ liệu tổng hợp chỉ ở môi trường demo:** root demo `warehouse/pipeline/ui-nhap` (DuckDB local) và catalog demo trên Databricks
  (§4.8). Không bao giờ vào `data/` gốc, catalog `retail_lab`, app public hiện tại hay `main` data. Bản nào chứa đợt tổng hợp thì mọi
  trang hiện băng rôn **"Dữ liệu tổng hợp – chỉ để demo"**.
- **Production không đổi hành vi:** mọi thay đổi dbt/app/CLI bật bằng biến (như `extension_enabled()`); không có đợt thì build ra
  **y hệt** hôm nay.
- **Nguồn lõi giữ ngưỡng cách ly 0** ([tien_hoa_schema.md](tien_hoa_schema.md) §6): một dòng sai là dừng cả đợt.
- **Đợt:** mọi ngày giao dịch của đợt phải **sau** ngày lớn nhất của bản gốc; gửi lại đúng đợt đã nạp bị từ chối (idempotent).
- Không sửa số đã chốt 2013–2022; không dùng số 2023 tổng hợp cho bất kỳ kết luận nào trong báo cáo.
- **Chat AI và khung "AI diễn giải" ẩn ở bản có đợt cho tới khi lát D6 đạt** (lý do §3, cách mở §4.7).

## 3. Hiện trạng: chỗ nào chặn nạp kỳ mới

| Chặn | Ở đâu | Hệ quả nếu nạp 2023 |
|---|---|---|
| Số dòng 14 nguồn cố định ở 5 chỗ — **chỉ chặn khi thêm dòng vào chính 14 nguồn** (trường hợp C ở §3.1); nguồn mới đi đường mở rộng không đụng tới | `source_contract.SOURCES`, `build_silver.py`, `ingest_raw.py`, `ingest/snapshot.py`, `assert_row_counts.sql` ([tien_hoa_schema.md](tien_hoa_schema.md) §3) | prepare/build dừng ngay |
| 2023 là **vùng dự báo** trong bảng doanh thu ngày | `retail_dbt/models/marts/fact_daily_sales.sql:3` (548 dòng từ `sample_submission`, `is_actual = false`); `dim_date.sql:41` (`is_forecast_period` = từ 2023-01-01) | trùng `date_sk` giữa số thực tế 2023 và dòng vùng dự báo |
| Vùng dự báo lấy cứng từ `sample_submission` (548 ngày từ 2023-01-01) | `scripts/forecast/stage.py:143–146`, `core.py:19`; `dim_date.sql:1` (dải ngày tới 2024-07-01); Tết chỉ có 2011–2025 và kiểm cứng 2023/2024 (`core.py:105–108`); kiểm tháng 8 viết cứng năm (`core.py:449–462`, `august_2023_check` `core.py:511`) | có số thực tế 2023 thì stage forecast dừng ("không phải 548 ngày liền sau ngày thực tế cuối", `stage.py:146`) |
| Đối soát G/COGS từng ngày với `sales` của snapshot | `scripts/pipeline/cli.py:129–136` | đợt phải có `sales` 2023 khớp đúng `Σ quantity × unit_price` (CLAUDE.md §5 điểm 1) |
| Kỳ phân tích viết cứng 2013–2022 | `rpt_revenue_total.sql:5–7`, `rpt_revenue_yearly.sql:43`, `rpt_revenue_monthly.sql:27`, `rpt_revenue_segment_yearly.sql:38`, `rpt_build_info.sql:11–12`, seed `ps2_phases.csv` | dữ liệu 2023 vào kho nhưng **không hiện** trên PS3–PS5 |
| Trang PS lọc `is_analysis_period` | `views/ps3_nhip_lich.py:26–28`, `ps4_don_mon_gia.py:198`, `ps5_nhom.py:196`; Tổng quan và PS1 vẽ cả năm ngoài kỳ nhưng làm mờ (`ps1_do_dung.py:164`) | như trên |
| Test khóa số | `assert_rpt_deck_numbers.sql`, `assert_rpt_total.sql`, `assert_rpt_phase.sql`, `assert_rpt_calendar*.sql`, `assert_rpt_driver.sql`, … | phải giữ nguyên cho 2013–2022, không áp lên 2023 |
| Chat coi "số thực tế dừng 2022-12-31" là luật | `ai_explain/service.py:167`, `evidence.py:153–156, 984`, `tools.py:347, 736, 899` | chat chặn hoặc nói sai về 2023 → ẩn ở bản có đợt tới khi D6 đạt (§4.7). Rà sơ bộ: khoảng 87 chỗ viết năm/ngày cứng trong 6 file `ai_explain/` (`tools.py` 30, `metric_catalog.py` 22, `evidence.py` 17, `service.py` 14, `charts.py` 2, `links.py` 2) và 6 chỗ trong `knowledge_corpus.json`† |

### 3.1 Dữ liệu từ nhiều nguồn khác chảy vào: ba trường hợp

Mười bốn nguồn là **hợp đồng lõi** (doanh thu G/COGS đối soát được với `sales`, CLAUDE.md §5 điểm 1), không phải giới hạn "chỉ nhận 14
file". Nguồn khác vào hệ thống theo một trong ba đường; khác định dạng (JSON, tên cột, kiểu) thì adapter + auto mapping đưa về hợp đồng
trước ([tien_hoa_schema.md](tien_hoa_schema.md) §4–§5).

| Trường hợp | Ví dụ | Đường đi | Đụng 14 nguồn? | Hiện trạng |
|---|---|---|---|---|
| A. Thêm thuộc tính cho thực thể đã có | `orders_enriched` (nhân viên bán hàng của đơn) | mở rộng: auto mapping → DE duyệt → model dbt riêng → chiều/bảng mới | không | **đã có** (lát 1–4 + trang nhập web); mỗi nguồn mới cần một model dbt (trạng thái "Chờ model dbt") |
| B. Thực thể mới hoàn toàn | shipper, khuyến mãi của hệ thống khác (`eprom`) | như A, thực thể/namespace riêng ([tien_hoa_schema.md](tien_hoa_schema.md) §7) | không | thiết kế có, chưa có model |
| C. Thêm **dòng** cho chính nguồn lõi | đơn năm 2023; đơn của cửa hàng/kênh khác cùng kỳ | đợt (§4.2–§4.3): mỗi file khớp đúng một nguồn lõi, kiểm khóa, số dòng theo manifest | **có**, vì G/COGS phải đối soát lại | phiếu này (chỉ kỳ mới) |

C từ hệ thống khác **cùng kỳ** còn thêm bài toán khóa trùng giữa hai hệ thống (cần `source_system` hoặc dải khóa riêng, như `epd` va
chạm 997 id ở [tien_hoa_schema.md](tien_hoa_schema.md) §2): ngoài phạm vi phiếu này.

## 4. Thiết kế

### 4.1 Sinh dữ liệu 2023 tổng hợp (công cụ của DE, chạy một lần)

Phương án A (đề xuất ban đầu, nay thay bằng B ở bảng dưới): **dời năm 2021 lên đúng 2 năm**: mọi bảng giao dịch có ngày trong 2021 (`orders`, `order_items`, `payments`, `shipments`,
`returns`, `reviews`, `promotions` của 2021, `sales`, `web_traffic`, `inventory`) cộng 2 năm vào mọi cột ngày, khóa giao dịch
(`order_id`, `promo_id`, …) cấp mới nối tiếp max id hiện có; master (`customers`, `products`, `geography`) giữ nguyên.

Vì sao chọn 2021:
- cùng tính lẻ với 2023 → giữ siêu khuyến mãi Urban Blowout tháng 8 năm lẻ (CLAUDE.md §5 điểm 6);
- 2021 và 2023 đều không nhuận → không lệch ngày 29/02;
- sau đứt gãy 2018 (§5 điểm 2) nên mức doanh thu hợp lý;
- thứ trong tuần lệch 2 ngày nhưng gần như vô nghĩa (§5 điểm 5, R² = 0,008).

Hệ quả: mọi bất biến hiện có (tổng thanh toán, thứ tự đặt/gửi/giao, `sales = Σ quantity × unit_price`) **tự đúng** vì là cùng dữ
liệu dời ngày; `sales` 2023 khớp đúng `order_items` 2023 → qua được cổng đối soát. Đơn cuối 2021 có giao/trả sang 2022 sẽ thành 2024:
chấp nhận (vẫn sau bản gốc). **Phải kiểm lại với từng test bất biến trước khi chốt** (bước đầu của lát 1).

**Ba phương án (§8 câu 1, PM hỏi thêm 2026-10-31 phương án "synthetic dựa trên dữ liệu gốc"):**

| | A. Dời 2021 + 2 năm | **B. Trộn ngày từ dữ liệu gốc (bootstrap theo ngày) — đề xuất** | C. Mô hình ngẫu nhiên theo cấu trúc EDA |
|---|---|---|---|
| Cách làm | chép nguyên năm 2021 | mỗi ngày của 2023 lấy **toàn bộ đơn của một ngày "mẫu"** cùng tháng, cùng ngày-trong-tháng ở một năm 2019–2022 chọn ngẫu nhiên có seed; tháng 8 chỉ lấy năm lẻ (2019, 2021) | sinh số đơn, giỏ hàng, giá từ phân phối ước lượng |
| Trông "mới" | không: biểu đồ 2023 trùng y 2021 | có: mỗi ngày từ một năm khác nhau | có |
| Bất biến (thanh toán, thứ tự đặt/gửi/giao, `sales = Σ quantity × unit_price`) | tự đúng | **tự đúng**, vì lấy trọn đơn kèm mọi bảng con và dời mọi ngày của đơn cùng một khoảng | phải tự chứng minh từng cái |
| Giữ cấu trúc EDA | có | có: mùa vụ tháng, ngày-trong-tháng (cùng ngày), Urban Blowout tháng 8 năm lẻ, mức sau đứt gãy 2018 | chỉ những gì được mô hình hóa |
| Công | ít nhất | thêm khoảng 2–3 ngày so với A† | nhiều nhất |

Chi tiết phương án B (kiểm ở bước đầu D1):
- Khóa giao dịch (`order_id`, `promo_id`, …) cấp mới nối tiếp max id; master (`customers`, `products`, `geography`) giữ nguyên, khóa
  ngoại tới master tự đúng.
- Đơn mẫu mang theo `order_items`, `payments`, `shipments`, `returns`, `reviews` của nó; mọi cột ngày cộng cùng một độ lệch
  (ngày 2023 − ngày mẫu). Mỗi ngày 2023 ứng đúng một ngày mẫu khác nhau nên không đơn nào bị chép hai lần.
- `promotions`: khuyến mãi của năm mẫu dời sang 2023 với `promo_id` mới, dòng hàng trỏ theo ánh xạ cũ → mới.
- `web_traffic` theo ngày mẫu; `inventory` theo tháng mẫu (grain kiểm lại ở D1).
- `sales` 2023 **tính lại** từ `order_items` của đợt (không chép), nên khớp cổng đối soát theo định nghĩa.
- Giới hạn ghi rõ: Tết âm lịch rơi vào ngày khác nhau mỗi năm, chọn ngày mẫu theo dương lịch nên hiệu ứng Tết 2023 có thể lệch;
  không có xu hướng tăng/giảm mới (sau 2018 chuỗi đi ngang, §5 điểm 2).

Đầu ra: thư mục `data_demo/dot_2023/` (gitignore) gồm một CSV mỗi bảng + `manifest.json` (bảng, số dòng, sha256, khoảng ngày,
`nguon_sinh`, seed, bảng ánh xạ ngày 2023 → ngày mẫu). Script ở `scripts/demo/` (có test), không chạy trong app.

### 4.2 Loại yêu cầu mới: "đợt giao dịch kỳ mới"

- Trang Gửi có thêm lựa chọn loại yêu cầu. Loại "đợt giao dịch" nhận **nhiều file** (đề xuất: đủ các bảng trong manifest đợt), mỗi
  file áp quy tắc file không tin cậy hiện có (§2 phiếu nhập UI); tổng dung lượng đợt ≤ 200 MB†.
- `auto_mapping.propose` chạy cho từng file: file phải nhận ra **đúng một nguồn lõi**, schema khớp 100% (không cột thêm/thiếu), nếu
  không thì cả đợt `loi_de_xuat`. Báo cáo đợt: số dòng từng bảng, khoảng ngày, kiểm trùng khóa với bản gốc.
- Tóm tắt nghiệp vụ cho Quản lý: "Đợt giao dịch 01/2023–12/2023: N đơn, M dòng hàng, doanh thu G ≈ …".
- Duyệt (DE/Admin) không chỉnh cột: chỉ Duyệt/Từ chối đợt. Chạy, công bố như luồng hiện có (DE chạy, Admin công bố).

### 4.3 Snapshot = bản gốc + các đợt

- `prepare` nhận thêm `--dot <thư mục đợt>` (lặp được): snapshot = 14 nguồn gốc + nối các đợt theo thứ tự đã duyệt. `snapshot_id`
  gồm sha256 của từng đợt (như `identity_suffix` của phần mở rộng).
- **Số dòng lấy từ manifest** (gốc + đợt), bỏ số cứng ở 5 chỗ; không có đợt thì số = số cũ (production không đổi).
- Kiểm của đợt, ngưỡng 0: khóa không trùng gốc và không trùng trong đợt; khóa ngoại tới master và tới bảng giao dịch (đợt + gốc);
  ngày của đợt > ngày max của gốc; header đúng hợp đồng nguồn lõi; `sales` của đợt bằng `Σ quantity × unit_price` theo ngày.

### 4.4 dbt: kỳ dữ liệu theo bản, không viết cứng

- **Kỳ suy ra từ dữ liệu của bản, không viết cứng năm nào:** `ky_cuoi` = năm đủ 12 tháng cuối cùng có số thực tế (tính từ ngày
  thực tế lớn nhất trong snapshot; bộ gốc ra 2022). `rpt_build_info.analysis_end_year`, `is_analysis_period`, kỳ toàn bộ trong
  `rpt_revenue_total` và các bảng năm/tháng đọc từ đó. Nhờ vậy nạp 2023 rồi 2024 dùng cùng một code, dashboard tự thêm năm.
- **Năm chưa đủ** (vd. đợt chỉ tới 06/2023): hiện trên biểu đồ tháng/năm với nhãn "chưa đủ năm", không vào kỳ phân tích chính, như
  cách đang xử lý năm 2012 (nửa năm).
- **Vùng dự báo:** `fact_daily_sales` và `dim_date.is_forecast_period` bắt đầu sau ngày thực tế lớn nhất của bản, không cố định
  2023-01-01. Bản có đợt: dòng vùng dự báo lấy theo vùng của stage forecast (§4.5), không từ `sample_submission`; `dim_date` sinh
  tới hết vùng dự báo của bản. Không đợt: như cũ.
- Giai đoạn PS2 (`ps2_phases.csv`): giữ 4 giai đoạn cũ; năm mới vào giai đoạn cuối hoặc giai đoạn "sau 2022" (§8 câu 3).
- **Test khóa số giữ nguyên nhưng giới hạn 2013–2022** (hoặc kỳ gốc); thêm test tổng quát cho kỳ mới (bảo toàn G/COGS, đủ ngày,
  không trùng `date_sk`).

### 4.5 Pipeline, dự báo học lại và cổng

- **Dự báo học lại trên dữ liệu mới (PM 2026-10-31).** Stage forecast vốn đã train trên `sales` của snapshot (`stage.py:141`) và
  đòi vùng dự báo liền sau ngày thực tế cuối (`stage.py:144`); chỉ cần đổi **nguồn của vùng**: bản có đợt thì vùng = `H` = 548 ngày
  ngay sau ngày thực tế cuối, sinh từ lịch (đợt 2023 → 2024-01-01 … 2025-07-01). Không đợt thì vẫn đọc `sample_submission` như
  hiện nay.
- Luật chọn model giữ như đăng ký 2026-10-14 (ứng viên, fold F1–F3, cách chấm; `core.py:6, 25, 40`); model thắng được **huấn luyện
  lại trên toàn bộ số thực tế của bản** (§8 câu 7).
- Bỏ chỗ cứng theo năm: dải năm Tết theo dữ liệu + vùng (`core.py:105–108`); kiểm "tháng 8 năm lẻ đầu tiên trong vùng" thay cho
  `august_2023_check` (`core.py:511`).
- **File nộp Datathon** (`submission.csv`) chỉ sinh từ bản gốc; bản có đợt không ghi đè.
- Model học trên dữ liệu tổng hợp nên trang Dự báo của bản đó mang băng rôn; không dùng số này trong báo cáo.
- Thời gian: stage forecast mất khoảng 6 phút trên laptop (lượt nghiệm thu nhập UI 2026-10-31, log 16:10:42 → 16:16:43)†.
- `validate` đối soát G/COGS từng ngày cho **cả kỳ** (gốc + đợt) với `sales` của snapshot như hiện nay.
- Context/manifest ghi `co_du_lieu_tong_hop: true` để app hiện băng rôn.

### 4.6 App ở root demo

- PS1–PS5, Tổng quan đọc kỳ từ `rpt_build_info` (đã có `analysis_start_year`/`analysis_end_year`, `ps2_xu_huong.py:31`), không tự
  viết 2013–2022 trong caption/label.
- Băng rôn "Dữ liệu tổng hợp – chỉ để demo" khi bản có cờ.
- Chat và khung "AI diễn giải" ẩn khi bản có cờ tổng hợp, cho tới khi D6 đạt.
- Chạy app ở chế độ versioned trỏ registry `ui-nhap` (`RETAIL_RELEASE_MODE=versioned`, `RETAIL_RELEASE_STATE=...`,
  `dwh/releases.py:17, 29`) — **chưa thử thật, phải kiểm ở §7 trước khi code**.

### 4.7 Chat theo kỳ của bản (lát D6, sau D5)

- **Không train lại gì:** chat là LLM gọi công cụ query có cấu trúc; số luôn lấy từ bản đang công bố (CLAUDE.md, skill
  `retail-ai-explain`). Việc của D6 là bỏ giả định "dữ liệu dừng 2022-12-31".
- **Kỳ đọc từ bản:** ngày thực tế cuối, kỳ phân tích (`analysis_start_year`/`analysis_end_year`) và vùng dự báo lấy từ
  `rpt_build_info` / `rpt_forecast_*` của bản, thay cho mốc cứng ở `service.py`, `evidence.py`, `tools.py`, `metric_catalog.py`,
  `charts.py`, `links.py` (§3). Luật "hỏi lại năm cho câu dự báo" (`docs/giao_viec_codex_hoi_lai_nam.md`) giữ nguyên, chỉ đổi mốc.
- **RAG tri thức** (`knowledge_corpus.json`) vẫn không cấp số; câu nhắc năm cứng sửa thành "kỳ của bản" hoặc giữ kèm nhãn "kết luận
  trên dữ liệu 2013–2022".
- **Kết luận trên dữ liệu tổng hợp:** khi câu trả lời dùng số của đợt tổng hợp, chat ghi rõ "số tổng hợp – chỉ để demo" và không đưa
  nguyên nhân (Urban Blowout, đứt gãy 2018…) cho năm mới nếu chưa có bằng chứng trong kết quả query.
- **Eval:**
  - bộ câu hiện có chạy lại trên bản gốc phải cho **cùng kết quả** như trước D6 (không hồi quy);
  - thêm bộ câu cho bản có đợt: "G năm 2023", "so 2023 với 2022", "dự báo 2024", "tháng 8/2023"… với đáp án đối chứng từ query
    độc lập;
  - unit test/query test tách khỏi eval LLM; kết quả mock không ghi là đạt live.
- **Phạm vi:** chỉ app local, bản demo `ui-nhap`; chat trên Streamlit Cloud và Databricks không đổi hành vi.

### 4.8 Catalog demo trên Databricks (cách A, PM chốt 2026-11-01; chưa tạo)

- **Tách riêng:** catalog riêng, tên đề xuất `retail_demo`, có registry `retail_control` riêng vì registry nằm trong catalog đang cấu
  hình (`scripts/pipeline/state.py:59–60`). Pipeline và app đều đọc catalog từ `RETAIL_DATABRICKS_CATALOG`
  (`scripts/pipeline/runtime.py:19`, `apps/retail_app/dwh/connection.py:140`). App demo là một app Streamlit Cloud riêng, cùng code,
  khác cấu hình; app public hiện tại không đổi.
- **Chặn bằng code, không dựa vào quy ước:** bản có `co_du_lieu_tong_hop: true` mà catalog là `retail_lab` thì pipeline từ chối. Mặc
  định của biến là `retail_lab`, nên thiếu biến cũng phải bị chặn.
- **Quyền:** chỉ cấp đọc cho đúng principal của app demo, không bao giờ cho `account users`.
- **Quota (đọc bằng profile `retail-dev`, 2026-11-01):**
  - `table-quota` tính theo **metastore**, nên catalog demo **dùng chung** với `retail_lab`: đang **317/500**, còn 183 bảng.
  - Mỗi bản khoảng 80 bảng†. Chạy lại P5 dùng khoảng 80†, còn khoảng 100† cho demo, chỉ đủ một bản.
  - Demo cần ít nhất 2 bản (bản gốc và bản có đợt), nên **phải xóa bớt bản cũ trước** (PM duyệt và tự chạy). Bảng đã xóa vẫn bị tính
    quota một thời gian: đợt xóa 2026-10-29 còn tính lúc 03:10 UTC cùng ngày, đến 2026-11-01 đã hết. Phải xóa sớm, không để sát demo.
  - `schema-quota` tính theo catalog (50), `catalog-quota` 3/50†: chưa vướng.
- **Tạo catalog:** tài khoản PM đang sở hữu `retail_lab` và `dbacademy`, nhóm workspace admin có `CREATE_CATALOG`; chưa thử tạo thật.
- **Dự báo đứng yên:** stage forecast của bản có đợt dùng lại kết quả bản gốc, có kiểm hash và ghi rõ lấy từ bản nào. Stage hiện đòi vùng
  dự báo liền sau ngày thực tế cuối (`scripts/forecast/stage.py`) và `check_forecast` (`scripts/pipeline/cli.py:101`) kiểm kết quả
  cùng lượt, nên phải đổi có kiểm soát. Trang Dự báo ghi nhãn "Dự báo từ bản gốc, chưa học dữ liệu 2023"; không so với số 2023 tổng
  hợp để kết luận độ chính xác. **Chưa rà hết** chỗ dbt và `validate` đọc vùng dự báo (§4.4, §4.5), phải rà trước khi soạn phiếu.
- **Chat:** ẩn ở app demo theo §4.6; chat bản public không đổi.

## 5. Tiêu chí nghiệm thu

**Lưu ý 2026-11-01:** mục 4 (dự báo 2024–2025) và mục 6 (D6) tạm gác theo §0; mục 5 chạy trên catalog demo. Sẽ viết lại khi soạn phiếu.

1. **Không đợt → giống hệt hôm nay:** build root demo không có đợt cho cùng số mọi `rpt_*` và G/COGS từng ngày như kho của lượt
   `demo-lat4-bat-01` (2026-10-29); toàn bộ test hiện có đạt; production `code_version` đổi nhưng số không đổi.
2. **Có đợt 2023:** mọi số 2013–2022 (bảng `rpt_*`, số deck, G/COGS từng ngày) **không đổi một đồng**; năm 2023 xuất hiện trên
   Tổng quan, PS1–PS5; G/COGS 2023 từng ngày = `sales` của đợt = G/COGS của ngày mẫu tương ứng trong bản gốc (đối chứng độc lập
   qua bảng ánh xạ trong manifest).
3. Đợt sai (trùng khóa, ngày chồng bản gốc, `sales` lệch, thiếu bảng) bị chặn với thông báo đúng; gửi lại đợt đã nạp bị từ chối.
4. Băng rôn hiện; chat ẩn; trang Dự báo của bản có đợt 2023 hiện vùng 2024-01-01 → 2025-07-01, model học trên số thực tế tới
   2023-12-31; không đợt thì dự báo giống hệt bản gốc; `submission.csv` không đổi.
5. Demo trên app (PM chạy): Quản lý gửi đợt → DE duyệt, chạy → Admin công bố → Tổng quan và PS có năm 2023.
6. **D6:** trên bản có đợt, chat trả lời đúng số 2023 và dự báo 2024–2025 theo đáp án đối chứng, có nhãn "số tổng hợp"; bộ eval cũ
   trên bản gốc không hồi quy.

## 6. Thứ tự làm (mỗi lát một phiếu GPT, Claude rà trước khi sang lát sau)

**Phạm vi 12/12 (PM 2026-11-01):** D1, D2, D3, D5 và catalog demo (§4.8). D4, D6 tạm gác.

| Lát | Việc | Ra gì |
|---|---|---|
| D1 | Bộ sinh dữ liệu (§4.1) + kiểm bất biến | `data_demo/dot_2023/` + test |
| D2 | Snapshot + đợt, số dòng theo manifest, kiểm đợt (§4.3) | `prepare --dot`, test; không đợt = như cũ |
| D3 | dbt kỳ động, vùng dự báo theo bản, test khóa số giới hạn kỳ gốc (§4.4) | nghiệm thu §5 mục 1–2 bằng CLI |
| D4 | Dự báo học lại, vùng theo ngày thực tế cuối (§4.5) | lượt CLI đầy đủ có forecast 2024–2025; không đợt = forecast như cũ |
| D5 | App: kỳ động, băng rôn, ẩn chat; trang Gửi/Duyệt loại "đợt" (§4.2, §4.6) | nghiệm thu §5 mục 3–5 |
| D6 | Chat theo kỳ của bản: bỏ mốc ngày cứng, eval lại (§4.7) | nghiệm thu §5 mục 6; mở lại chat ở bản có đợt |

Nhánh mới tách từ `nhap-ui/myuyen` sau khi phiếu nhập UI qua §6.

## 7. Điều kiện trước khi giao GPT

- PM chạy xong nghiệm thu §6 của phiếu nhập UI, **kèm bước trỏ app vào registry `ui-nhap`** (chế độ versioned) và ảnh trang Sức
  khỏe dữ liệu. Toàn bộ ý "dashboard tự cập nhật" dựa vào bước này; nó chưa được thử.
- PM chốt §8.

## 8. Câu hỏi PM chốt

1. **Cách sinh 2023:** PM hỏi thêm phương án "synthetic dựa trên dữ liệu gốc" → Claude đề xuất **B. trộn ngày từ dữ liệu gốc** (§4.1).
   **Chờ PM xác nhận B** (hay A/C).
2. ~~Bảng trong đợt~~ **Chốt 2026-10-31 (PM):** đủ mọi bảng giao dịch có ngày, để mọi test bất biến đạt và PS có đủ metric.
3. ~~PS2 giai đoạn~~ **Chốt 2026-10-31 (PM):** năm mới gộp vào giai đoạn cuối hiện có, không đổi luật seed.
4. ~~**Kỳ phân tích chính:** 2013–2023 hay giữ 2013–2022?~~ **Chốt 2026-10-31 (PM):** kỳ theo dữ liệu (2013–2023 khi có đợt 2023),
   năm mới hiện đầy đủ trên PS1–PS5 với các metric có bảng nguồn trong đợt.
5. **Băng rôn và chat:** ~~đồng ý ẩn chat ở root demo?~~ **Chốt 2026-10-31 (PM):** ẩn tạm tới khi D6 đạt, rồi mở lại; băng rôn
   "Dữ liệu tổng hợp – chỉ để demo" vẫn giữ.
6. ~~Năm chưa đủ~~ **Chốt 2026-10-31 (PM):** hiện kèm nhãn "chưa đủ năm", để ngoài kỳ phân tích chính (giống năm 2012).
7. ~~Học lại dự báo~~ **Chốt 2026-10-31 (PM, theo đề xuất):** giữ nguyên luật chọn và fold F1–F3 đã đăng ký 2026-10-14, chỉ huấn
   luyện lại trên dữ liệu mới; không mở lại `hop_dong_du_bao.md`.
8. ~~Độ dài vùng dự báo~~ **Chốt 2026-10-31 (PM, theo đề xuất):** 548 ngày như đề Datathon, dùng lại `H`.
