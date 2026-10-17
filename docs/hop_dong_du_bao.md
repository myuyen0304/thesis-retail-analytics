# Hợp đồng dự báo G/COGS theo ngày (B1)

**Trạng thái: §0 ĐÃ CHỐT ngày 2026-10-14** (PM chốt theo đề nghị của dev; nháp ngày 2026-10-13). Mục B1 trong [checklist_sdlc_gd2.md](checklist_sdlc_gd2.md).
Skill soạn: `retail-forecasting` (giao thức backtest) + `retail-metric-design` (định nghĩa target).
Tài liệu vào cửa của phần AI (thứ tự đọc, sổ quyết định, nhật ký): [ke_hoach_ai_gd2.md](ke_hoach_ai_gd2.md).

Hợp đồng này đi trước notebook B2. Mọi tên bảng, cột trong tài liệu là **tên đề xuất** cho tới khi có trong code.

**Cách đọc nhãn:**

| Nhãn | Nghĩa |
|---|---|
| **Đã chốt** | PM/BA đã quyết, có ngày. Không đổi nếu PM không mở lại |
| **Ràng buộc dữ liệu** | Kết luận đã chứng minh trong notebook (`CLAUDE.md` §5). Không phải lựa chọn |
| **Đề xuất** | Dev soạn, chờ PM chốt ở §0 |
| **Mở** | Chốt bằng bảng backtest ở B2, không chốt trước |

Nguồn đã đọc: `CLAUDE.md` §1, §5, §6; `docs/problem_statement.md` PS5; `docs/star_schema.md` §3;
`docs/kien_truc_pipeline_tong.md` §5 (B1–B3); `docs/automation_batch.md`;
skill `retail-forecasting`, file `references/forecast_protocol.md`.

---

## 0. Quyết định (PM chốt ngày 2026-10-14)

PM chốt theo đề nghị của dev ngày 2026-10-14. Đề nghị đã được sửa sau khi đọc lời giải tham khảo của chính bộ dữ liệu này
(`docs/references/[Reading]-Retail-Analytics-Forecasting.pdf`, Mục XIII–XIX; xem [ke_hoach_ai_gd2.md](ke_hoach_ai_gd2.md) §6).
Bản nháp 2026-10-13 của bảng này nằm trong lịch sử của file; các chỗ khác nhau được ghi ở cột "Đổi so với nháp".

| # | Quyết định | Đã chốt | Đổi so với nháp 2026-10-13 | Mục |
|---|---|---|---|---|
| Q1 | Chỉ số để chọn model | **Điểm ngày kết hợp** = (MAE G ngày + MAE COGS ngày) / 2 trên vùng chấm của một fold. Điểm của model = trung bình ba fold. RMSE và R² ngày báo kèm. **MAPE G tháng chỉ để hiển thị** cho người lập kế hoạch (PS5), không dùng để chọn | Đổi từ MAPE tháng. Lý do: tài liệu tham khảo (Mục XIII.2) ghi cuộc thi chấm MAE, RMSE, R² theo ngày trên cả Revenue lẫn COGS | §5 |
| Q2 | Điểm sàn | Thắng **seasonal naive 2 năm** về điểm ngày kết hợp ở **cả ba fold** | **Suy ra từ Q1:** giữ luật "cả ba fold", đổi thước sang điểm ngày kết hợp | §5 |
| Q3 | Biến đợt khuyến mãi lớn năm lẻ | Cờ đợt Urban Blowout thay cho cờ "tháng 8 năm lẻ". Ngày đầu, ngày cuối lấy từ cell B2 đọc `promotions.csv` | Như nháp | §3 |
| Q4 | Mốc chế độ sau đứt gãy | 2019-01-01. B2 kiểm lại bằng cell | Như nháp | §3 |
| Q5 | Hồ sơ tỷ lệ COGS/G | Tỷ lệ của tổng ΣCOGS/ΣG theo (tháng × cờ Urban Blowout) trên cửa sổ train. Đây là **một trong hai cách COGS** dự thi (Q10) | **Suy ra từ Q10:** không còn là cách duy nhất | §2.3 |
| Q6 | Mức khoảng dự báo | 80% | Như nháp | §6 |
| Q7 | Khoảng dự báo ở grain tháng | Không hiển thị khoảng tháng. Trang tháng hiện "sai số tháng điển hình" từ backtest | Như nháp | §6 |
| Q8 | AI agent dùng model nào | **Phương án A:** luật §5 chạy tự động trong pipeline mỗi bản dữ liệu, đánh dấu đúng một ứng viên `is_primary`. Agent và app trả lời bằng ứng viên này, kèm sai số backtest; so sánh các ứng viên khi được hỏi. Không để LLM tự chọn model | Như nháp | §7 |
| Q9 | Danh sách ứng viên | **Must:** các mốc (§4.1), log + SARIMAX, LightGBM, **bản gộp** log + SARIMAX và LightGBM (trọng số chọn trong phần train của từng fold). **Should:** ARIMA. **Could:** LSTM. **Không model nào được ưu tiên sẵn** | Bản gộp lên Must; LightGBM ngang hàng, không còn chỉ là đối thủ; bỏ luật "log + SARIMAX đương nhiệm" | §4, §5 |
| Q10 | Cách dự báo COGS | **Backtest quyết** giữa hai cách: (a) G × hồ sơ tỷ lệ (Q5); (b) dự báo COGS trực tiếp bằng cùng model, train riêng trên log COGS | **Mở lại** quyết định "COGS qua tỷ lệ" ngày 2026-10-11. Lý do: COGS chiếm nửa điểm; lời giải tham khảo dự báo COGS trực tiếp (Mục XIV.5) | §2.3, §4 |
| Q11 | Kaggle | **Không làm gì liên quan tới Kaggle** (PM chốt 2026-10-15): không nộp, không dùng bảng xếp hạng. File nộp chỉ là sản phẩm của khóa luận | Mới | — |

**Dev định nghĩa, ghi ngày 2026-10-14, trước khi có bất kỳ điểm backtest nào.** PM muốn đổi thì đổi trước khi chạy cell chấm điểm:
- **Ngưỡng hòa 1%:** ứng viên có điểm trung bình ≤ 1,01 × điểm tốt nhất được coi là hòa với ứng viên tốt nhất.
- **Thứ tự đơn giản** (đơn giản đứng trước, dùng để phá hòa): ARIMA < log + SARIMAX < LightGBM < bản gộp < LSTM.
  Trong cùng model: cửa sổ train từ 2019 < toàn chuỗi (ít biến hơn, không cần cờ chế độ); COGS qua tỷ lệ < COGS trực tiếp.
- **Lưới trọng số bản gộp:** w ∈ {0; 0,25; 0,5; 0,75; 1} cho LightGBM, phần còn lại cho log + SARIMAX.
  Chọn bằng một năm cuối của phần train trong từng fold (validation trong). Hai thành viên của bản gộp dùng cửa sổ toàn chuỗi.
- **Tham số model cố định trước** (bậc ARMA, số cặp Fourier, tham số cây). Ghi trong notebook B2, không dò trên vùng chấm.

Còn **mở**, chốt bằng bảng backtest ở B2: cửa sổ train (toàn chuỗi kèm cờ chế độ, hay chỉ từ 2019).
log + SARIMAX và LightGBM mỗi model chạy cả hai cửa sổ; mỗi cửa sổ là một ứng viên riêng trong luật §5.

---

## 1. Câu hỏi và người dùng

- **Problem:** PS5 trong `docs/problem_statement.md`: dự báo doanh thu để lập kế hoạch bán hàng, ngân sách và nguồn lực,
  khi mọi bảng phụ dừng ở 2022-12-31.
- **Câu hỏi khóa luận phải trả lời:**

  | Mã | Câu hỏi | Hợp đồng trả lời bằng |
  |---|---|---|
  | Q5.1 | Chỉ dùng biến lịch thì đạt độ chính xác bao nhiêu? | Bảng backtest theo fold (§5) |
  | Q5.2 / H5.1 | Dự báo COGS độc lập, hay qua tỷ lệ COGS/G? | Hai cách cùng dự thi trong backtest; luật §5 chọn (Q10, chốt 2026-10-14) |
  | Q5.3 / H5.3 | Model có tái tạo được biên độ sự kiện tháng 8 năm lẻ không? | Chỉ số "tỷ lệ tái tạo biên độ" (§5) |

- **Người dùng:** PM/BA và người lập kế hoạch, qua trang Dự báo (B3) và tool chat `get_forecast` (B3).
- **Ngoài phạm vi đợt này:**
  - dự báo R. **Đã chốt** 2026-10-11: để sau;
  - dự báo theo nhóm hàng, vùng, kênh. Hợp đồng chỉ có **tổng toàn công ty**, suy từ target đã chốt. Đề xuất: chat từ chối câu hỏi dự báo theo chiều;
  - đường đối chứng khuyến mãi cho PS4 (model lịch train trên ngày không khuyến mãi, PS5 mục "Vai trò"). Để sau.

## 2. Target

### 2.1 Hợp đồng metric

| Mục | Nội dung | Nhãn |
|---|---|---|
| Metric | **G theo ngày.** Tên cột đề xuất `yhat`. Nhãn hiển thị: **"G – doanh thu gộp, gồm cả đơn hủy"** | Đã chốt 2026-10-11 |
| Đơn vị | VND (đồng). Dữ liệu nguồn không ghi đơn vị; đây là quy ước PM | Đã chốt 2026-10-05 (`metric_catalog.py`) |
| Grain | Một ngày lịch, tổng toàn công ty | Đã chốt 2026-10-11 |
| Tập dữ liệu | **Mọi trạng thái đơn**, gồm cả đơn hủy và đơn trả. Ngày = ngày đặt hàng | Ràng buộc dữ liệu (`CLAUDE.md` §5.1; `star_schema.md` §3) |
| Công thức thực tế | `G(d) = Σ quantity × unit_price`, **không trừ** `discount_amount`. Khớp chính xác `Revenue` của `sales.csv` | Ràng buộc dữ liệu (`CLAUDE.md` §5.1) |
| Nguồn train | Phần thực tế của `sales.csv`, đúng 3.833 ngày 2012-07-04 → 2022-12-31. Trong pipeline: `sales.parquet` của snapshot. Trong kho: `fact_daily_sales` với `is_actual = true` | Đề xuất (vị trí stage: `kien_truc_pipeline_tong.md` B2) |
| Đối chứng đầu vào | Test dbt có sẵn `assert_daily_sales_matches_source`: kho khớp `sales.csv` từng ngày, 2 chữ số | Đã có |
| Horizon | 2023-01-01 → 2024-07-01, **548 ngày**, gồm ngày 29/02/2024 | Đã chốt 2026-10-11 |
| `trained_through` | 2022-12-31 cho bản nộp. Trong backtest là ngày origin của fold | Đề xuất |
| Chiều phân tích | Không có. Không chia theo nhóm hàng, vùng, kênh | Đề xuất, suy từ target đã chốt (G tổng theo ngày) |

**Không được dùng làm dữ liệu train hay "thực tế":**
- 548 dòng `is_actual = false` của `fact_daily_sales`. Đó là bản chép `sample_submission`, không phải số thật (`star_schema.md` §3);
- `data/sample_submission.csv`. Đó là mẫu định dạng, mang sẵn giả định CAGR −3,8% đã biết là sai (`problem_statement.md` H5.2).

### 2.2 Gộp lên tháng để hiển thị

| Đại lượng | Cách gộp | Nhãn |
|---|---|---|
| G tháng | Σ G ngày (G cộng được qua các ngày) | Ràng buộc dữ liệu (`star_schema.md` §3) |
| COGS tháng | Σ COGS ngày | Ràng buộc dữ liệu |
| COGS/G tháng | ΣCOGS / ΣG của tháng. **Không** lấy trung bình tỷ lệ ngày | Ràng buộc dữ liệu (tỷ lệ phải tính lại từ tử và mẫu) |
| Khoảng dự báo tháng | Không cộng `lower`/`upper` ngày. Xem Q7 | Đề xuất |
| Tháng 07/2024 | Chỉ có 1 ngày (01/07). Hiển thị là tháng thiếu, không so với tháng đủ | Đề xuất |

### 2.3 COGS

- **Chốt 2026-10-14 (Q10), mở lại quyết định 2026-10-11:** hai cách COGS cùng dự thi, luật §5 chọn.
  - **(a) Qua tỷ lệ** (`cogs_method = 'ratio'`): `COGS(d) = G(d) × r(d)`, với `r` lấy từ hồ sơ tỷ lệ theo lịch (Q5), tính trên cửa sổ train.
  - **(b) Trực tiếp** (`cogs_method = 'direct'`): cùng model, cùng biến lịch, train riêng trên log COGS.
- **Ràng buộc dữ liệu:** `CLAUDE.md` §5.7, tỷ lệ COGS/G nên mô hình hóa như một tỷ lệ.
  Cách (b) không mâu thuẫn với kết luận này: đây là một phép thử model, backtest đo cách nào sai số ngày thấp hơn.
  Tháng 8 năm lẻ có COGS > G (`CLAUDE.md` §5.6). Dù chọn cách nào, kết quả dự báo tháng 8/2023 phải có tỷ lệ > 1 (test §9).
- **Cột đề xuất:** `cogs_method`, `cogs_ratio_hat` (= `cogs_yhat / yhat` ở cách b), `cogs_yhat`.

## 3. Biến ngoại sinh: chỉ suy từ lịch

**Ràng buộc dữ liệu:** mọi bảng phụ dừng ở 2022-12-31, nên biến ngoại sinh chỉ được suy từ lịch (`CLAUDE.md` §5, mục "Ràng buộc chi phối").

| Biến | Bằng chứng | Nhãn |
|---|---|---|
| Mùa vụ theo tháng | `CLAUDE.md` §5.3. Dạng biến (Fourier năm hay 12 biến tháng) chọn ở B2. SARIMAX không mô hình trực tiếp được mùa vụ 365 ngày, nên mùa vụ năm phải đưa vào qua biến ngoại sinh | Dùng: ràng buộc dữ liệu. Dạng: mở |
| Ngày trong tháng, khoảng cách tới cuối tháng | `CLAUDE.md` §5.4: tín hiệu baseline bỏ sót nhiều nhất | Dùng: ràng buộc dữ liệu. Dạng: mở |
| Cờ đợt Urban Blowout, chỉ năm lẻ. Ngày đầu, ngày cuối lấy từ `promotions.csv` trong cell B2 | `CLAUDE.md` §5.6; `notebooks/01_exploration/eda.ipynb`, code cell ngay sau mục "Cơ chế: khuyến mãi Urban Blowout chạy 2 năm một lần" | **Đã chốt** 2026-10-14 (Q3) |
| Cờ chế độ sau đứt gãy, từ 2019-01-01 | `CLAUDE.md` §5.2 ghi "cuối 2018". Ngày mốc phải có cell kiểm ở B2. Chỉ cần khi train toàn chuỗi | **Đã chốt** 2026-10-14 (Q4) |
| Thứ trong tuần | `CLAUDE.md` §5.5: R² = 0,008 | **Không dùng**: ràng buộc dữ liệu |
| `web_traffic`, `inventory`, `reviews`, `promotions` ở thời điểm tương lai | Dừng ở 2022-12-31 | **Không dùng**: ràng buộc dữ liệu |
| Cờ cho cả 6 họ khuyến mãi (Spring, Mid-Year, Fall Launch, Year-End, Urban Blowout, Rural Special; hai họ sau chỉ năm lẻ) | `notebooks/04_forecasting/so_sanh_model.ipynb` §2.2: luật "ngày đầu, ngày cuối hay gặp nhất mỗi họ" tái tạo các cửa sổ 2013–2022 lệch tối đa 2 ngày, 0,52% số ngày khuyến mãi bị lệch. Cửa sổ 2023–2024 là ngoại suy từ luật | **Dùng** (cell B2, 2026-10-14) |
| Đầu tháng (ngày 1–3), cuối tháng (3 ngày cuối) | Cuối tháng: `CLAUDE.md` §5.4. Đầu tháng: `notebooks/04_forecasting/so_sanh_model.ipynb` §2.3, ngày 1 và ngày 2 đạt luật đưa biến (ngày 1 cao hơn phần model chưa có biến này giải thích, cùng dấu ở mọi năm). Đây là phát hiện mới, `CLAUDE.md` §5.4 chỉ nói dốc cuối tháng | **Dùng** cả hai (cell B2, 2026-10-14) |
| Tết (khoảng cách tới mồng 1 Tết) | Lời giải tham khảo thấy G thấp trước Tết, bứt lên sau Tết (theo tài liệu, Mục XIV.3). `notebooks/04_forecasting/so_sanh_model.ipynb` §2.3: sau khi đã có mùa vụ năm, cờ khuyến mãi và đầu/cuối tháng, không nhóm 7 ngày nào quanh Tết đạt luật đưa biến. Ngày Tết lấy từ thư viện `holidays` | **Không dùng** (cell B2, 2026-10-14) |
| Ngày lễ cố định khác | Chưa có bằng chứng | Không dùng |

## 4. Model và mốc so sánh

ARIMA, log + SARIMAX và LSTM trên sơ đồ GĐ2 là **thầy gợi ý, không bắt buộc** (PM xác nhận 2026-10-13). Danh sách ứng viên chốt ở Q9 (2026-10-14).

Thứ tự làm: mốc so sánh → log + SARIMAX → LightGBM → bản gộp → ARIMA → LSTM. Chưa có các mục Should, Could vẫn bàn giao được.
**Ứng viên** = (model, cửa sổ train, cách COGS). Mỗi ứng viên có G và COGS cho mọi ngày của vùng chấm.

### 4.1 Mốc so sánh (đề xuất)

Mốc phải tính được theo cùng một luật ở mọi fold và ở bài thật, kể cả khi "năm trước" của ngày cần dự báo cũng nằm trong vùng dự báo.

| Mốc | Luật cho ngày cần dự báo `d` (tháng `m`, ngày `k`) |
|---|---|
| **Seasonal naive 1 năm** | Lấy G của ngày (`m`, `k`) ở **năm gần nhất đã quan sát** (ngày đó ≤ `trained_through`) |
| **Seasonal naive 2 năm** | Như trên, nhưng năm đó phải **cùng tính chẵn/lẻ** với năm của `d`. Mốc này bắt được chu kỳ tháng 8 năm lẻ |
| **Baseline cũ** | Tái tạo phương pháp của `baseline.ipynb` (trung bình mùa vụ × CAGR gộp) trong notebook mới. **Không sửa và không xây tiếp** `baseline.ipynb` (`CLAUDE.md` §6) |

- **Ngày 29/02:** năm mốc không nhuận thì lấy ngày 28/02 của năm đó.
- **Năm mốc trước đứt gãy (đề xuất):** nếu năm cùng chẵn/lẻ gần nhất nằm trước mốc chế độ (Q4, chốt 2019-01-01), ngày đó dùng seasonal naive 1 năm.
  Chỉ ảnh hưởng F1: các ngày tháng 7–12/2020 sẽ phải neo vào 2018, năm thuộc chế độ cũ, làm mốc kém đi giả tạo và điều kiện Q2 trở nên quá dễ ở F1.
- **Ví dụ ở bài thật:** seasonal naive 1 năm lấy năm 2022 cho mọi ngày từ 2023-01-01 đến 2024-07-01. Seasonal naive 2 năm lấy năm 2021 cho ngày năm 2023 và năm 2022 cho ngày năm 2024.
- COGS của mốc: dùng cùng luật với COGS/G (lấy tỷ lệ của ngày mốc).

### 4.2 Model (chốt Q9, 2026-10-14)

| Model | Ghi chú | Mức |
|---|---|---|
| log + SARIMAX | Biến lịch ở §3, phần sai số ARMA bậc thấp. Hai cửa sổ train: toàn chuỗi kèm cờ chế độ, và từ 2019. Thầy gợi ý | Must |
| LightGBM | Cùng bộ biến lịch ở §3, thêm năm chẵn/lẻ. **Không** dùng biến "năm" dạng số (cây không ngoại suy được). Hai cửa sổ train như trên. Giải thích bằng SHAP | Must |
| Bản gộp | `w × LightGBM + (1 − w) × log + SARIMAX`, cộng trên thang tiền. `w` chọn trong lưới §0 bằng một năm cuối của phần train trong từng fold. Hai thành viên dùng cửa sổ toàn chuỗi | Must |
| ARIMA | Trên log G, không biến lịch. Cho thấy vì sao cần biến lịch | Should. Thầy gợi ý |
| LSTM nhỏ | Cố định seed, báo độ dao động giữa các seed. Scaler fit trên phần train **của từng fold** | Could. Thầy gợi ý |

Mỗi model chạy với cả hai cách COGS (Q10). Mốc so sánh lấy COGS theo cùng luật với G (lấy COGS của ngày mốc).

**Không model nào được ưu tiên sẵn** (chốt 2026-10-14). Lập luận trước backtest ở [chon_model_du_bao.md](chon_model_du_bao.md) chỉ là dự đoán.
Lời giải tham khảo của bộ dữ liệu này dùng LightGBM làm phần chính của bản gộp (theo tài liệu, Mục XVIII); ta kiểm lại bằng backtest của mình.

## 5. Backtest

**Kiểu:** rolling-origin, mỗi fold dự báo đúng 548 ngày như bài thật. Đề xuất theo `forecast_protocol.md`.

| Fold | Origin (`trained_through`) | Vùng chấm | Số ngày | Tháng 8 đủ trong vùng chấm | Số ngày train nếu chỉ dùng từ 2019 |
|---|---|---|---|---|---|
| F1 | 2020-06-30 | 2020-07-01 → 2021-12-30 | 548 | 2020, **2021 (lẻ)** | 547 |
| F2 | 2020-12-31 | 2021-01-01 → 2022-07-02 | 548 | **2021 (lẻ)** | 731 |
| F3 | 2021-06-30 | 2021-07-01 → 2022-12-30 | 548 | **2021 (lẻ)**, 2022 | 912 |

- Cột ngày trong bảng là phép tính lịch, không cần dữ liệu.
- F2 giống bài thật nhất: bắt đầu ngày 1/1 của một năm lẻ, dài 548 ngày.
- F3 kết thúc 2022-12-30: ngày 2022-12-31 không được chấm.
- **Không** dùng origin 2019-12-31: năm 2020 nhuận nên 548 ngày chỉ tới 2021-07-01, fold đó không có tháng 8 năm lẻ.
- Train từ 2019 thì F1 chỉ có 547 ngày sau đứt gãy. Đây là dữ kiện phải cân khi chốt cửa sổ train.
- **Tháng thiếu ngày ở hai đầu fold** (ví dụ 12/2021 ở F1, 07/2022 ở F2) bị loại khỏi chỉ số tháng.

**Chỉ số** (chốt Q1, 2026-10-14). Báo **theo từng fold**, không chỉ báo trung bình:

| Chỉ số | Grain | Vai trò |
|---|---|---|
| **Điểm ngày kết hợp** = (MAE G + MAE COGS) / 2 | Ngày | **Chọn model** (Q1) |
| MAE G, MAE COGS | Ngày | Hai thành phần của điểm, báo riêng |
| RMSE, R² trên G và COGS | Ngày | Báo kèm: cùng bộ thước của cuộc thi (theo tài liệu tham khảo, Mục XIII.2) |
| MAPE trên G tháng | Tháng đủ ngày | **Hiển thị** cho người lập kế hoạch (PS5, `Forecast MAPE` trong `problem_statement.md` §5). Không dùng để chọn |
| MAE G riêng tháng 8 năm lẻ | Ngày trong tháng 8/2021 | Trả lời Q5.3 |
| Tỷ lệ tái tạo biên độ tháng 8 | Tháng 8/2021 | Trả lời Q5.3. Định nghĩa bên dưới |
| Sai số COGS/G tháng | Tháng đủ ngày | Trả lời Q5.2 |
| Coverage của khoảng 80% | Ngày | Kiểm khoảng dự báo |

Dự báo trên thang log rồi exp ngược cho ra **trung vị**, không phải trung bình. Với thước MAE, trung vị là lựa chọn đúng, nên không hiệu chỉnh lệch log.
B2 vẫn đo độ lệch này để báo cáo.

**Tỷ lệ tái tạo biên độ tháng 8** (đề xuất):
- Biên độ sụt thực tế = 1 − G(tháng 8/2021) / G(tháng 8/2020).
- Biên độ sụt dự báo = 1 − Ĝ(tháng 8/2021) / G(tháng 8/2020). Mẫu số luôn là số thực tế.
- Tỷ lệ tái tạo = biên độ dự báo / biên độ thực tế. Bằng 1 là tái tạo đủ. H5.3 dự đoán con số này nhỏ hơn 1.
- Làm tương tự cho COGS/G tháng 8/2021: so tỷ lệ dự báo với tỷ lệ thực tế.

**Luật chọn ứng viên** (chốt 2026-10-14, Q1, Q2, Q9, Q10; ngưỡng và thứ tự ở §0):
1. **Sàn:** ứng viên phải thắng seasonal naive 2 năm về điểm ngày kết hợp ở **cả ba fold**. Không ứng viên nào qua thì báo thẳng, và dùng mốc làm bản nộp.
2. **Thấp nhất:** trong các ứng viên qua bước 1, tìm điểm trung bình ba fold thấp nhất.
3. **Hòa thì chọn đơn giản:** mọi ứng viên có điểm ≤ 1,01 × điểm thấp nhất được coi là hòa; chọn ứng viên đơn giản nhất theo thứ tự ở §0.
   LSTM thêm điều kiện: chênh lệch với ứng viên đứng sau phải lớn hơn độ dao động giữa các seed.
4. **Không dò trên vùng chấm:** tham số model cố định trước; trọng số bản gộp chọn trong phần train của từng fold.
5. **Điểm của ứng viên thắng là lạc quan**, vì được chọn từ nhiều ứng viên trên cùng ba fold. Báo cáo phải ghi điều này.

**Ai chạy luật** (chốt Q8, 2026-10-14): stage dự báo của pipeline chạy luật này mỗi bản dữ liệu, không phải người chọn tay và không phải LLM.
Notebook B2 chứng minh luật trên một snapshot; stage phải ra cùng ứng viên thắng với notebook trên cùng snapshot đó.

**Điều kiện tiên quyết** B2 phải kiểm bằng cell đầu tiên, chưa coi là sự thật:
- G > 0 và COGS > 0 mọi ngày. Cần cho phép log và cho MAPE;
- đầu vào đủ 3.833 ngày liên tục, không có dòng `is_actual = false`.

## 6. Khoảng dự báo

| Mục | Nội dung | Nhãn |
|---|---|---|
| Mức | 80% | Đã chốt 2026-10-14 (Q6) |
| Cách tính, mọi ứng viên | Quantile 10% và 90% của phần dư log (`log thực tế − log dự báo`) trên backtest, nhân vào `yhat`. Cùng một cách cho mọi model, kể cả bản gộp | Đề xuất của dev |
| Kiểm coverage | Khoảng dùng để chấm fold nào thì lấy quantile từ **hai fold còn lại**, để phép kiểm không tự chấm chính nó. Bản cuối lấy quantile từ cả ba fold | Đề xuất của dev |
| SARIMAX | Báo thêm khoảng tự nhiên của model (trên thang log, exp ngược) để so | Đề xuất của dev |
| Grain tháng | Không hiển thị khoảng tháng. Hiển thị "sai số tháng điển hình" từ backtest | Đã chốt 2026-10-14 (Q7) |

## 7. Đầu ra cho B2 và B3 (đã có trong code từ 2026-10-15)

Code: `scripts/forecast/stage.py` ghi parquet; `retail_dbt/models/reporting/rpt_forecast_*.sql` đọc thành bảng; test: `retail_dbt/tests/assert_rpt_forecast.sql` và `assert_rpt_forecast_actual.sql`. Ba model và hai test chỉ bật khi pipeline truyền var `forecast_path`.

App và chat chỉ đọc `reporting.rpt_forecast_*` trong bản dữ liệu đang phục vụ. Không tạo schema `forecast` riêng (`automation_batch.md`).

**`reporting.rpt_forecast_daily`:** một dòng = một ngày × một ứng viên trong một bản dữ liệu. Khóa: (`model`, `cogs_method`, `forecast_date`).

| Cột | Ý nghĩa |
|---|---|
| `forecast_date` | Ngày cần dự báo, 2023-01-01 → 2024-07-01 |
| `model`, `model_version` | Tên model kèm cửa sổ train (ví dụ `lgbm_full`, `sarimax_2019`) và phiên bản code/tham số |
| `cogs_method` | `ratio` hoặc `direct` (Q10) |
| `run_id`, `trained_through` | Lần chạy pipeline; ngày cuối của dữ liệu train |
| `is_primary` | Đúng một ứng viên (`model`, `cogs_method`) mỗi bản dữ liệu (Q8) |
| `selection_step` | Bước của luật §5 đã chọn ứng viên `is_primary`; null ở các ứng viên khác |
| `yhat`, `lower`, `upper` | G dự báo và khoảng 80% |
| `interval_level` | 0.8 |
| `cogs_ratio_hat`, `cogs_yhat` | Tỷ lệ COGS/G và COGS dự báo |

**`reporting.rpt_forecast_backtest`:** một dòng = một ứng viên × một fold × một chỉ số. Cột: `model`, `cogs_method`, `role`, `candidate_rank`, `fold_origin`, `metric`, `grain`, `value`.
- `role`: `floor` (mốc sàn seasonal naive 2 năm), `baseline` (mốc khác), `candidate` (ứng viên được xét trong luật chọn).
- `candidate_rank`: thứ tự đơn giản dùng để phá hòa (0 = đơn giản nhất), cùng nguồn với `RANK` trong `scripts/forecast/core.py`.
- `metric`: `mae_g`, `mae_cogs`, `score`, `rmse_g`, `rmse_cogs`, `r2_g`, `r2_cogs` (grain `ngay`); `mape_g_thang` (grain `thang`);
  `mae_g_t8_2021`, `tai_tao_bien_do`, `cogs_g_t8_du_bao` (grain `thang_8_2021`); `coverage_80`; `blend_weight_lgbm` (trọng số LightGBM của bản gộp, grain `fold`).
Bảng phải có `mae_g` và `mae_cogs` của mọi ứng viên và mốc ở mọi fold, để test §9 tính lại được luật chọn từ chính bảng này.
Bảng cũng phải có các chỉ số hiển thị của §5 (ít nhất `mape_g_thang`, `rmse_g`, `r2_g`, tỷ lệ tái tạo biên độ tháng 8), để agent trả lời được cả câu hỏi theo tháng.
Lý do: thứ hạng theo ngày và theo tháng khác nhau (`notebooks/04_forecasting/so_sanh_model.ipynb` §7); agent không được chỉ đưa thước có lợi cho ứng viên chính.

**`reporting.rpt_forecast_actual`** (thêm 2026-10-15, PM duyệt khi làm trang Dự báo B3b): một dòng = một ngày **thực tế**, 2012-07-04 → 2022-12-31. Cột `sale_date`, `g`, `cogs`, lấy từ `fact_daily_sales` (`is_actual`) của cùng bản dữ liệu. Trang Dự báo vẽ số thực tế cạnh dự báo từ bảng này, không đọc marts. Test `assert_rpt_forecast_actual`: khớp `sales.csv` từng ngày, mỗi ngày một dòng, ngày cuối = `trained_through`, dự báo bắt đầu ngay hôm sau. Bảng chỉ có từ các bản dựng sau 2026-10-15; bản trước đó có dự báo nhưng không có số thực tế đi kèm.

**Phục vụ AI agent** (chốt Q8, 2026-10-14; [chon_model_du_bao.md](chon_model_du_bao.md) §6.1):
- Stage ghi vào bản dữ liệu **mọi ứng viên Must và Should** đã làm xong, cùng các mốc, không chỉ ứng viên chính. Agent cần đủ các model để so sánh khi được hỏi.
- Thêm cột `selection_step` vào `rpt_forecast_daily`: bước nào của luật §5 đã chọn model `is_primary`. Agent dùng cột này để giải thích vì sao model đó được chọn, không tự đặt lý do.

**File nộp:** `Date, Revenue, COGS`, 548 dòng theo đúng thứ tự `data/sample_submission.csv`, lấy từ ứng viên `is_primary`.
`Revenue = yhat`, `COGS = cogs_yhat`, làm tròn 2 chữ số. Ghi vào `data/`, **không commit** (`CLAUDE.md` §2).

## 8. Nhãn hiển thị

Mọi số dự báo trên app và chat phải kèm:
- "G – doanh thu gộp, gồm cả đơn hủy". **Đã chốt** 2026-10-11;
- chữ "dự báo", khoảng dự báo, `model_version` và `trained_through`. **Đề xuất**, lấy từ kế hoạch B3 và skill `retail-forecasting`.

Thêm:
- Không trộn số dự báo vào bảng thực tế của PS1–PS5.
- Không so G dự báo với R thực tế. Hai số khác tập đơn.
- Không gọi phân rã thành phần model là nguyên nhân.
- Nói về độ tin cậy của model thì dùng "sai số backtest 2020–2022", **không** nói "độ chính xác X%" trên 2023–2024. Ghi thêm rằng điểm của model thắng là lạc quan (§5 bước 5). **Đề xuất.**
- **Việc của B3:** nhãn G trong `apps/retail_app/ai_explain/metric_catalog.py` hiện là "G — doanh thu gộp", thiếu "gồm cả đơn hủy". B3 phải thống nhất hai nhãn.

## 9. Tiêu chí nghiệm thu B2

Test dbt cho `rpt_forecast_*`, chạy trong quality gate của pipeline:
- mỗi ứng viên đủ 548 ngày, không trùng, không thiếu ngày;
- `0 < lower ≤ yhat ≤ upper`;
- đúng một ứng viên `is_primary` mỗi bản dữ liệu;
- ứng viên `is_primary` khớp với kết quả áp luật §5 lên `mae_g`, `mae_cogs` trong `rpt_forecast_backtest` của cùng bản (Q8). Test này bảo đảm agent luôn dùng ứng viên thắng theo luật, không phải ứng viên gắn tay;
- `model_version`, `trained_through` không null; `trained_through ≤ 2022-12-31`;
- COGS/G ngày nằm trong khoảng COGS/G ngày đã thấy trong lịch sử 2012–2022, nới 10% mỗi phía (đề xuất của dev, sửa 2026-10-14).
  **Không** cấm COGS/G > 1 ngoài Urban Blowout: số thực tế có 214 ngày như vậy, phần lớn ở tháng 11–12 (`notebooks/04_forecasting/so_sanh_model.ipynb` §8, cell kiểm COGS/G theo ngày);
- kiểm tường minh tháng 8/2023: G tháng thấp hơn G thực tế tháng 8/2022, và COGS/G tháng > 1.

**Không ghi cứng** con số COGS/G của tháng 8 năm lẻ vào test (1,34 hay 1,36 tùy cách tính, xem §10). Ngưỡng khác, nếu có, lấy từ lịch sử hoặc backtest.

Bàn giao B2 gồm: notebook đã chạy hết; bảng backtest theo fold; ghi snapshot id, cửa sổ train, seed, phiên bản thư viện.

## 10. Điểm lệch cần B2 làm rõ

- **Tỷ lệ COGS/G tháng 8 năm lẻ (đã rõ, `notebooks/04_forecasting/so_sanh_model.ipynb` §2.4):** hai số đều đúng, khác cách tính.
  Gộp mọi tháng 8 năm lẻ 2013–2021: **tỷ lệ của tổng** ΣCOGS/ΣG ≈ 1,34 (`problem_statement.md`); **trung bình tỷ lệ ngày** ≈ 1,36 (`CLAUDE.md` §5.6).
  Hợp đồng dùng tỷ lệ của tổng (§2.2). Chưa sửa `CLAUDE.md` §5.6; đề nghị PM cho thêm chú thích "trung bình tỷ lệ ngày" vào đó.
- **Cờ "tháng 8 năm lẻ" so với cửa sổ Urban Blowout:** PM chốt Q3 ngày 2026-10-14, dùng cửa sổ Urban Blowout. Ngày đầu, ngày cuối lấy từ `promotions.csv` trong cell B2.
  Chỉ số "MAE tháng 8 năm lẻ" vẫn đo theo tháng 8, để khớp câu hỏi Q5.3.
