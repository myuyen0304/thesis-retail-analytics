# Chọn model dự báo G theo ngày: đề xuất trước backtest

**Trạng thái: soạn 2026-10-13; PM chốt Q1, Q8, Q9, Q10 ngày 2026-10-14. Chưa có số backtest.** Đi kèm [hop_dong_du_bao.md](hop_dong_du_bao.md) (B1).
Tài liệu vào cửa của phần AI: [ke_hoach_ai_gd2.md](ke_hoach_ai_gd2.md).

> **Sửa ngày 2026-10-14.** Bản 2026-10-13 cược log + SARIMAX làm model chính và bắt model khác phải thắng nó ở cả ba fold.
> Bản đó viết khi **chưa đọc** lời giải tham khảo của chính bộ dữ liệu này (`docs/references/[Reading]-Retail-Analytics-Forecasting.pdf`).
> Lời giải đó chấm bằng MAE/RMSE/R² theo ngày trên cả Revenue và COGS, và dùng LightGBM làm phần chính của bản gộp (theo tài liệu, Mục XIII.2, XVIII).
> Vì vậy PM chốt: chọn bằng điểm ngày kết hợp, log + SARIMAX và LightGBM ngang hàng, bản gộp là Must, COGS hai cách cùng dự thi.
> §0, §1, §6, §6.1, §7 đã sửa theo; §4 giữ làm lập luận cho vai trò "neo" của log + SARIMAX.

File này trả lời một câu: *nếu phải đặt cược trước khi có số, model nào phù hợp nhất để làm model chính (`is_primary`), vì sao, và điều gì sẽ làm đổi ý.*

- ARIMA, log + SARIMAX và LSTM trên sơ đồ GĐ2 (`docs/references/pipeline-gd2.jpg`) là **model thầy gợi ý, không bắt buộc**.
  PM xác nhận ngày 2026-10-13: được tham khảo model khác. Vì vậy file này xét các họ model phổ biến, không chỉ ba model đó.
- **Model chính thức chỉ chọn bằng luật chọn model** (§6, chép sang `hop_dong_du_bao.md` §5), sau khi B2 có bảng backtest.
  Không model nào thắng seasonal naive 2 năm ở cả ba fold thì bản nộp dùng chính mốc đó.
- **Mục tiêu PM nêu ngày 2026-10-13:** sau này AI agent dùng model cho kết quả chính xác nhất.
  Model nào chính xác nhất do luật §6 quyết bằng số backtest. Luật chạy tự động mỗi bản dữ liệu (§6.1, chốt Q8 ngày 2026-10-14).
  Không model nào được ưu tiên sẵn.
- Mọi đánh giá dưới đây là **lập luận** từ cấu trúc dữ liệu đã chứng minh (`CLAUDE.md` §5). Không có con số nào được đo.

---

## 0. Kết luận ngắn (chốt Q9, 2026-10-14)

| Vai trò | Ứng viên | Mức |
|---|---|---|
| Mốc sàn, phải thắng | Seasonal naive 2 năm (kèm naive 1 năm và baseline cũ, `hop_dong_du_bao.md` §4.1) | Must |
| Ứng viên ngang hàng | **log + SARIMAX với biến lịch**, hai cửa sổ train | Must |
| Ứng viên ngang hàng | **LightGBM trên cùng bộ biến lịch**, hai cửa sổ train | Must |
| Kết hợp | **Bản gộp** `w × LightGBM + (1 − w) × log + SARIMAX`, `w` chọn trong phần train của từng fold | Must |
| So sánh | ARIMA thuần | Should |
| Thí nghiệm | LSTM nhỏ | Could |

Mỗi model chạy với hai cách COGS: qua tỷ lệ, và dự báo trực tiếp (Q10). Danh sách chốt **trước khi có kết quả**. Thêm ứng viên sau khi đã xem điểm là chọn theo kết quả (§6).

**Dự đoán, chưa có số:** bản gộp hoặc LightGBM nhiều khả năng thắng, vì lời giải tham khảo đi theo hướng đó. Bảng backtest mới là thứ quyết.

**Mốc vẫn mạnh.** Seasonal naive 2 năm chép được cả bốn tính chất của chuỗi (§2), nên đây không phải mốc cho có.
PM nên chuẩn bị cho khả năng các model chỉ hơn mốc rất ít, hoặc không hơn.

## 1. Tiêu chí chọn

Độ chính xác quyết định cuối cùng, nhưng sản phẩm còn cần những thứ khác:

| # | Tiêu chí | Vì sao cần | Lấy từ |
|---|---|---|---|
| T1 | Điểm ngày kết hợp (MAE G + MAE COGS) / 2 trên backtest | Thước chọn model (Q1, chốt 2026-10-14) | `hop_dong_du_bao.md` §5 |
| T2 | Bắt được tháng 8 năm lẻ: G sụt, COGS/G > 1 | Tháng 8/2023 nằm trong vùng dự báo; trả lời Q5.3 | `CLAUDE.md` §5.6 |
| T3 | Có khoảng dự báo 80% | Trang Dự báo và tool `get_forecast` (B3) cần `lower`/`upper` | `hop_dong_du_bao.md` §6 |
| T4 | Giải thích được | Level L4, tool `explain_forecast` (B4) | `kien_truc_pipeline_tong.md` B4 |
| T5 | Tái lập được | Stage của pipeline (Linux, Docker) phải ra cùng số với notebook (Windows), trong một sai số nhỏ | skill `retail-forecasting` |
| T6 | Chi phí triển khai trước 2026-10-25 | Thư viện, RAM máy, image Docker của Airflow | §9 |

## 2. Rà soát các họ model

Bốn tính chất của chuỗi (`CLAUDE.md` §5): đứt gãy cuối 2018, mùa vụ theo tháng, hiệu ứng ngày trong tháng, tháng 8 năm lẻ.
Thêm một ràng buộc: chỉ dùng được biến suy từ lịch, vì mọi bảng phụ dừng ở 2022-12-31.

| Họ model | Ví dụ | Hợp với dữ liệu này? | Kết luận |
|---|---|---|---|
| Mốc đơn giản | Seasonal naive 1 năm, 2 năm | Chép được cả bốn tính chất, nhưng chép cả nhiễu ngẫu nhiên của một ngày | Giữ làm mốc |
| ARIMA thuần | ARIMA | Chỉ nhìn quá khứ gần, không biết lịch. Dự báo 548 ngày sẽ phẳng dần | Should: rẻ, cho thấy vì sao cần biến lịch |
| **Hồi quy theo lịch + sai số ARMA** | **log + SARIMAX** | Đưa thẳng cả bốn tính chất vào bằng biến lịch. Học hiệu quả với ít dữ liệu (§4) | **Model chính kỳ vọng** |
| Hồi quy theo lịch dạng phân rã | Prophet | Cùng ý tưởng với dòng trên. Có biểu đồ thành phần dễ trình bày, khai báo được đợt Urban Blowout như một "ngày đặc biệt". Mặc định tự ngoại suy xu hướng, phải khóa lại. Phụ thuộc Stan; cài trên Windows và tương thích pandas 3 chưa kiểm | Không đưa vào: trùng họ với log + SARIMAX. Dự phòng nếu statsmodels không chạy được |
| Làm mượt mũ, phân rã mùa vụ | ETS/Holt-Winters, TBATS, MSTL | Mùa vụ 365 ngày nặng và chậm. Không nhận biến ngoài, nên không đưa được cờ Urban Blowout | Không chọn |
| **Cây tăng cường (gradient boosting)** | **LightGBM**, XGBoost, CatBoost | Dùng biến lịch như một bảng tra. Tự bắt tương tác, ví dụ dốc cuối tháng khác nhau giữa các tháng; không giả định tác động dạng nhân. Không ngoại suy được xu hướng, nhưng sau 2018 chuỗi đi ngang nên ít ảnh hưởng | **Đối thủ chính.** Chọn LightGBM vì nhẹ, nhanh; XGBoost, CatBoost tương đương cho bài này |
| Mạng nơ-ron | LSTM, N-BEATS, TFT | Một chuỗi 3.833 điểm là ít. Kết quả dao động theo seed, nặng, khó giải thích | LSTM: Could. Các mạng khác: không chọn |
| Foundation model chuỗi thời gian | Chronos, TimesFM | Dự báo không cần train. Đưa được cờ Urban Blowout vào hay không tùy phiên bản. Nặng, là hộp đen | Không chọn |

## 3. Chấm danh sách rút gọn (lập luận, chưa có số)

| | Seasonal naive 2 năm | ARIMA | log + SARIMAX | LightGBM | LSTM nhỏ |
|---|---|---|---|---|---|
| **T1 (kỳ vọng)** | Mạnh, nhưng chép nhiễu của một ngày và mức của 2 năm trước | Kém trên 548 ngày | Tốt, nếu biến lịch đúng | Tốt, nếu mỗi tổ hợp lịch có đủ dữ liệu | Chưa biết; 3.833 ngày là ít đối với deep learning |
| **T2** | Có (chép năm lẻ) | Không | Có, qua cờ Urban Blowout (Q3) | Có, qua cờ Urban Blowout; học từ ít ngày | Khó: lịch sử chỉ có vài tháng 8 năm lẻ |
| **T3** | Quantile phần dư backtest | Có sẵn | Có sẵn, tính trên thang log rồi đổi ngược | Hồi quy quantile, hoặc quantile phần dư backtest | Quantile phần dư backtest |
| **T4** | Rất dễ ("giống năm 2021") | Hệ số không gắn với lịch | Mỗi biến lịch có hệ số, tách được đóng góp | SHAP: đóng góp của từng biến cho từng ngày | Khó |
| **T5** | Tuyệt đối | Khớp trong sai số nhỏ | Khớp trong sai số nhỏ | Khớp trong sai số nhỏ, khi cố định seed và số luồng | Dao động theo seed |
| **T6** | Không cần thư viện | statsmodels | statsmodels | lightgbm | torch hoặc tensorflow, nặng |

**Về T5:** notebook chạy trên Windows, stage chạy trên Linux trong Docker. Bộ tối ưu của statsmodels và LightGBM không bảo đảm ra số giống hệt từng chữ số giữa hai môi trường.
Tiêu chí nghiệm thu B2 cần một ngưỡng sai số nhỏ, không đòi bằng tuyệt đối.

## 4. Lập luận cho log + SARIMAX (viết 2026-10-13, trước khi đọc lời giải tham khảo)

Từ 2026-10-14, log + SARIMAX là ứng viên ngang hàng, không còn là "model chính kỳ vọng".
Các điểm dưới đây vẫn đúng như lập luận, và giải thích vì sao nó đáng làm thành viên "neo" của bản gộp.

1. **Khớp cơ chế sinh dữ liệu.** Cả bốn tính chất ở `CLAUDE.md` §5 đều là hàm của lịch.
   Đợt Urban Blowout làm G giảm theo phần trăm (khoảng −37%, `CLAUDE.md` §5.6), tức là tác động nhân. Trên thang log, tác động nhân thành tác động cộng, và model tuyến tính học được. Đổi ngược về tiền thì G luôn dương.
2. **Học hiệu quả với ít dữ liệu.** Model giả định các tác động cộng dồn trên thang log. Nhờ vậy dốc cuối tháng học từ mọi tháng rồi áp cho cả tháng 8 năm lẻ.
   LightGBM không giả định như vậy, nên ở vùng hiếm như tháng 8 năm lẻ nó có ít điểm để học hơn. Ngược lại, nếu giả định "cộng trên thang log" sai thì LightGBM sẽ thắng; đó là lý do nó làm đối thủ chính (§5).
3. **Với 548 ngày, phần lớn dự báo do biến lịch quyết định** (lập luận, B2 kiểm).
   Nếu không sai phân (d = 0), phần ARMA chỉ hiệu chỉnh vài tuần đầu sau origin rồi tắt dần.
   **Hệ quả cho PM:** chất lượng phụ thuộc chủ yếu vào Q3 (cờ Urban Blowout), Q4 (mốc chế độ) và dạng biến mùa vụ, hơn là việc tinh chỉnh bậc ARIMA.
   LightGBM dùng cùng bộ biến, nên điều này đúng cho cả hai model. Công sức B2 nên dồn vào biến lịch.
4. **Có sẵn khoảng dự báo** cho trang Dự báo và `get_forecast`.
5. **Giải thích bằng hệ số.** Tách được đóng góp của tháng, ngày trong tháng, Urban Blowout, chế độ. Đó là đầu vào của `explain_forecast` (B4).
   Phải gắn nhãn "phân rã model, không phải nguyên nhân".

## 5. LightGBM: ứng viên ngang hàng (từ 2026-10-14)

- **Có bằng chứng ngoài:** lời giải tham khảo của bộ dữ liệu này để LightGBM gánh phần lớn trọng số của bản gộp (theo tài liệu, Mục XVIII). Ta chưa kiểm điều này trên notebook.
- **Khác họ, nên bổ sung cho log + SARIMAX.** Prophet cùng họ hồi quy theo lịch với log + SARIMAX, thêm vào không kiểm được gì mới. LightGBM không giả định tác động cộng trên thang log.
- **Rẻ:** một thư viện nhẹ, train nhanh trên 3.833 dòng.
- **Giải thích được bằng SHAP.** Khớp với ý tưởng "Dự báo/SHAP" đã có trong lịch sử dự án (`CLAUDE.md` §1).
- **Bẫy riêng, B2 phải tránh:**
  - không dùng biến "năm" dạng số, vì cây không ngoại suy được sang 2023–2024. Dùng năm chẵn/lẻ và cờ chế độ;
  - giới hạn độ sâu và số lá, vì ít biến và ít dữ liệu;
  - tham số chỉ chọn trong phần train của từng fold.

## 6. Luật chọn khi có nhiều ứng viên (chốt 2026-10-14)

Bản đầy đủ, kèm ngưỡng hòa và thứ tự đơn giản: `hop_dong_du_bao.md` §0 và §5. Tóm tắt:

1. **Sàn:** thắng seasonal naive 2 năm về điểm ngày kết hợp ở cả ba fold (Q2).
2. **Thấp nhất:** trong các ứng viên qua sàn, lấy điểm trung bình ba fold thấp nhất.
3. **Hòa thì chọn đơn giản:** ứng viên trong vòng 1% của điểm thấp nhất được coi là hòa; chọn ứng viên đơn giản nhất.
4. Không ứng viên nào qua sàn: báo thẳng, bản nộp dùng seasonal naive 2 năm.
5. Tham số cố định trước; trọng số bản gộp chọn trong phần train của từng fold. Không dò trên vùng chấm.
6. **Điểm của ứng viên thắng là lạc quan.** Chọn từ nhiều ứng viên trên cùng ba fold thì điểm của ứng viên thắng thường đẹp hơn sai số thật trên 2023–2024. Báo cáo phải ghi điều này.

**Vì sao bỏ luật "log + SARIMAX đương nhiệm" của bản 2026-10-13.** Luật đó bắt model khác thắng log + SARIMAX ở cả ba fold mới được thay.
Khi đã có bằng chứng ngoài rằng LightGBM mạnh hơn, luật đó nghiêng về model yếu hơn. Luật trung lập giữ được phần bảo vệ (sàn ở cả ba fold, hòa thì chọn đơn giản) mà không thiên vị.

### 6.1 AI agent dùng model chính xác nhất như thế nào (đề xuất, Q8)

PM nêu mục tiêu ngày 2026-10-13: AI agent chọn model cho kết quả có độ chính xác cao.

**"Chính xác" đo bằng gì.** Đo bằng điểm ngày kết hợp (MAE G + MAE COGS) / 2 trên backtest 2020–2022 (Q1).
Năm 2023–2024 không có số thực tế, nên không ai đo được độ chính xác thật ở đó, kể cả agent. Điểm backtest là ước lượng tốt nhất có.

**Luật bảo vệ khỏi chọn nhầm thế nào.** Backtest chỉ có ba lần thi thử. Sàn đòi thắng mốc ở cả ba lần, và ứng viên hòa trong vòng 1% thì chọn ứng viên đơn giản hơn.
Hai điều này làm giảm rủi ro chọn một ứng viên thắng nhờ may. Không luật nào bảo đảm chọn được ứng viên chính xác nhất trên 2023–2024 khi chưa có số thực.

**Luật chọn không làm dự báo chính xác hơn.** Nó chỉ bảo đảm agent dùng ứng viên có điểm backtest tốt nhất theo luật.
Độ chính xác đến từ công việc ở B2: biến lịch, bản gộp, cách dự báo COGS.

**Phương án A (chốt Q8, 2026-10-14): luật chọn chạy trong pipeline, agent đọc kết quả.**
- Mỗi bản dữ liệu, stage dự báo chạy backtest cho mọi model trong danh sách (§9), áp luật §6, rồi đánh dấu model thắng là `is_primary`.
  Kèm theo là bước luật đã quyết (ví dụ "bước 2: LightGBM không thắng log + SARIMAX ở cả ba fold"), để agent giải thích được mà không phải tự bịa lý do.
- Agent trả lời câu dự báo bằng model `is_primary`, kèm sai số backtest của model đó.
- Câu "model nào chính xác nhất" hoặc "so sánh các model": agent đọc bảng backtest và trả lời bằng số trong bảng.
- Người dùng hỏi đích danh một model khác: agent trả model đó nếu có trong bản dữ liệu, ghi rõ "không phải model chính".
- **Trong khóa luận này, mỗi bản dữ liệu ra cùng một model thắng.** Dữ liệu dừng ở 2022-12-31 và ngày origin của ba fold cố định (`hop_dong_du_bao.md` §5).
  Chạy luật trong pipeline mang lại hai thứ: kết quả lặp lại được, và chặn việc gắn model chính bằng tay. Nó không làm model tự thích nghi.
  Nếu sau này có dữ liệu mới, phải dời ngày origin của các fold theo, thì luật mới có thể chọn ra model khác.

**Phương án B (không chọn): LLM tự chọn model cho từng câu hỏi.**
- Không có số thực 2023–2024, nên LLM không có gì để đo độ chính xác. Nó chỉ đoán.
- Cùng một câu hỏi có thể ra số khác nhau ở hai lần hỏi.
- Trộn model giữa các câu làm hỏng phép cộng: tổng các ngày lấy từ model này không bằng số tháng lấy từ model khác.
- Phá luật "số chỉ đến từ kết quả tool" của chat (`retail-ai-explain`).

**Vì sao bản gộp là Must.** Gộp hai model khác họ thường ổn định hơn từng model riêng lẻ, vì sai số của hai model không trùng nhau hoàn toàn.
Lời giải tham khảo gộp nhiều model và thấy bản gộp tốt hơn từng model (theo tài liệu, Mục XVIII). Khi stage đã chạy cả hai model (§9) thì bản gộp gần như không tốn thêm.
Nó vẫn phải qua luật §6 như mọi ứng viên khác, không được ưu tiên sẵn.

## 7. Đọc bảng backtest thế nào

| Kết quả backtest ở B2 | Hành động |
|---|---|
| Không ứng viên nào qua sàn | Xem lại biến lịch (cờ khuyến mãi, Tết, dạng mùa vụ). Vẫn không qua thì bản nộp dùng mốc (§6 bước 4) |
| Bản gộp chọn `w = 1` hoặc `w = 0` ở mọi fold | Một thành viên không đóng góp gì; báo cáo ghi rõ |
| Ứng viên thắng và ứng viên đứng sau chênh trong vòng 1% | Theo luật hòa, chọn ứng viên đơn giản hơn |
| LSTM thắng nhưng chênh lệch nằm trong độ dao động giữa các seed | Không chọn LSTM. Chênh lệch đó chưa phân biệt được với may rủi |
| ARIMA thuần thắng các model có biến lịch | Bất thường. Kiểm rò rỉ dữ liệu trước khi tin |
| COGS trực tiếp thắng COGS qua tỷ lệ | Ghi vào báo cáo cho H5.1. Vẫn phải qua test tháng 8/2023 có COGS/G > 1 |
| Coverage của khoảng 80% lệch xa 80% | Hiệu chỉnh khoảng bằng phần dư backtest trước khi lên app |
| Tỷ lệ tái tạo biên độ tháng 8 thấp ở mọi model | Xem lại cờ Urban Blowout (Q3) |

## 8. Thiết kế đề xuất (B2 kiểm)

### 8.1 log + SARIMAX

| Thành phần | Đề xuất | Nhãn |
|---|---|---|
| Biến đích | log G | Đề xuất |
| Mùa vụ năm | Fourier năm hoặc biến tháng, chọn bằng backtest | Mở (`hop_dong_du_bao.md` §3) |
| Ngày trong tháng | Biến ngày hoặc khoảng cách tới cuối tháng, chọn bằng backtest | Mở |
| Urban Blowout | Cờ 30/07–02/09 năm lẻ | Đề xuất (Q3) |
| Chế độ sau đứt gãy | Cờ từ 2019-01-01, khi train toàn chuỗi | Đề xuất (Q4) |
| Phần ARIMA | Bậc thấp, không sai phân (d = 0) để mức dài hạn do biến lịch quyết định. Thử d = 1 như một biến thể | Đề xuất |
| Mùa vụ tuần | Không dùng | Ràng buộc dữ liệu (`CLAUDE.md` §5.5) |
| COGS | Hai cách cùng dự thi: hồ sơ tỷ lệ theo lịch (Q5), hoặc model riêng trên log COGS | Chốt 2026-10-14 (Q10) |

### 8.2 LightGBM

| Thành phần | Đề xuất |
|---|---|
| Biến | Cùng bộ biến lịch ở `hop_dong_du_bao.md` §3: tháng, ngày trong tháng, khoảng cách tới cuối tháng, cờ Urban Blowout, cờ chế độ, năm chẵn/lẻ |
| Không dùng | Biến "năm" dạng số (cây không ngoại suy được); thứ trong tuần (`CLAUDE.md` §5.5) |
| Biến đích | log G hoặc G, chọn bằng backtest |
| Độ phức tạp | Giới hạn độ sâu và số lá; chọn trong phần train của từng fold |
| Khoảng 80% | Hồi quy quantile 10% và 90%, hoặc quantile phần dư backtest |
| Giải thích | SHAP |
| Tái lập | Cố định seed và số luồng |
| COGS | Hai cách cùng dự thi, như mọi model (Q10) |

### 8.3 Hai điểm B2 phải đo, chưa coi là sự thật

- **Lệch khi đổi ngược từ log.** Lấy exp của dự báo trên thang log cho ra trung vị, thường thấp hơn trung bình. Tổng tháng có thể bị hụt có hệ thống.
  Thước chọn là MAE ngày, và trung vị là dự báo tối ưu cho MAE, nên không hiệu chỉnh. B2 vẫn đo độ lệch này để báo cáo, vì MAPE tháng hiển thị cho PM bị ảnh hưởng.
- **Cửa sổ train vẫn Mở.** Đây là một đánh đổi, không phải đề xuất:
  - *Toàn chuỗi + cờ chế độ:* trên thang log, đứt gãy 2018 chỉ là một bước dời mức. Model học được hiệu ứng Urban Blowout từ nhiều tháng 8 năm lẻ hơn.
    Rủi ro: nếu hình dạng mùa vụ đổi sau 2018 thì dữ liệu cũ kéo sai.
  - *Chỉ từ 2019:* sạch chế độ, nhưng fold F1 (origin 2020-06-30) chỉ có tháng 8/2019 để học Urban Blowout.
  - Urban Blowout chạy từ năm nào thì chưa có cell. B2 kiểm bằng `promotions.csv` trước khi so hai cửa sổ.

## 9. Hệ quả kỹ thuật

- **Thư viện model** (cài ngày 2026-10-14 bằng `uv pip install`): statsmodels 0.15.0, lightgbm 4.7.0, holidays 0.106 (lấy ngày Tết), kéo theo scipy 1.18.1.
  - Đã thêm vào `requirements.txt`. File này pin version và dùng chung cho hai máy, nên phải báo người kia.
  - Chỉ thêm torch khi làm tới LSTM.
  - Tương thích với pandas 3.0.5 và numpy 2.5.1: kiểm bằng lần chạy notebook B2 (ghi ở `ke_hoach_ai_gd2.md` §8).
- **Đề xuất (theo mục tiêu agent ở §6.1):** stage dự báo trong pipeline chạy mọi model Must và Should đã làm xong trong notebook, cùng các mốc.
  - Stage chạy cả backtest ba fold chứ không chỉ train bản cuối, vì luật chọn cần điểm backtest. Mỗi model train khoảng bốn lần.
    Đo ngày 2026-10-14 trên laptop Windows của nhóm: cả notebook `notebooks/04_forecasting/so_sanh_model.ipynb` (12 ứng viên, 3 mốc, ba fold và bản cuối) chạy 878 giây trong lần chạy ngày 2026-10-15 (cell cuối của notebook in tổng thời gian); stage pipeline local cùng ngày chạy 956 giây (`docs/automation_batch.md`). Máy bận thì lâu hơn nhiều.
  - Image Docker của Airflow cần cả statsmodels và lightgbm.
  - Khoảng 80% của trung bình cộng chỉ lấy được từ quantile phần dư backtest (`hop_dong_du_bao.md` §6).
  - LSTM chỉ vào stage nếu nó thắng theo luật §6, vì torch làm image nặng thêm nhiều.
  - Nếu PM chọn không chạy đủ các model trong stage thì luật chọn chỉ chạy được trong notebook, và agent không so sánh được các model theo từng bản dữ liệu.

## 10. Nếu hội đồng hỏi

- **"Sao không chỉ làm ba model thầy gợi ý?"** Thầy gợi ý, không bắt buộc. ARIMA và log + SARIMAX có trong bảng backtest; LSTM ở mức Could.
  LightGBM được thêm để kiểm giả định của log + SARIMAX bằng một họ model khác, và vì lời giải tham khảo dùng nó làm phần chính (theo tài liệu, Mục XVIII).
- **"Vì sao chọn LightGBM?"** (số từ `notebooks/04_forecasting/so_sanh_model.ipynb` §6–§8, ngày 2026-10-14)
  - Không phải nhóm chọn: luật viết trước khi có điểm chọn ứng viên có điểm ngày kết hợp trung bình ba fold thấp nhất. LightGBM toàn chuỗi, COGS trực tiếp đứng đầu, thấp hơn mốc seasonal naive 2 năm khoảng 20%.
  - Không thắng áp đảo: bản gộp thắng LightGBM ở fold F2 và F3, LightGBM thắng F1 và thắng điểm trung bình; hai bên cách nhau khoảng 1,3%, ngay ngoài ngưỡng hòa 1%.
  - Ở bản cuối, bản gộp tự chọn trọng số LightGBM = 1, nên dự báo 2023–2024 của bản gộp và của LightGBM **trùng nhau từng ngày**. Chọn bên nào thì số nộp cũng như nhau.
  - Lý do về cấu trúc: học được tương tác giữa các cờ lịch (khuyến mãi × ngày trong tháng × năm chẵn/lẻ) mà không giả định tác động nhân; chạy lại ra đúng số cũ (cố định seed); giải thích được bằng SHAP cho B4.
  - Điểm yếu phải nói: xét sai số tổng tháng, log + SARIMAX và bản gộp tốt hơn LightGBM; LightGBM tái tạo thiếu biên độ sụt tháng 8 năm lẻ (khoảng 79%).
- **"Sao không dùng deep learning hay foundation model?"** Một chuỗi, 3.833 ngày, cơ chế lịch đã biết. Model đơn giản giải thích được và đủ để kiểm.
- **"Sao không dùng Prophet?"** Cùng họ hồi quy theo lịch với log + SARIMAX. Thêm vào không kiểm được giả định nào mới.
- **"Model thắng có chắc tốt trên 2023–2024 không?"** Không chắc. Điểm backtest là ước lượng, và lạc quan vì được chọn từ nhiều ứng viên (§6 bước 6).
- **"Lời giải tham khảo nhân dự báo với 1,26 và 1,32, sao không làm theo?"** Hai hệ số đó được dò bằng cách nộp thử lên bảng xếp hạng Kaggle (theo tài liệu, Mục XIX), tức là chỉnh theo đáp án của tập test.
  Khóa luận không dùng phản hồi của tập test để chỉnh model. Hai hệ số đó cũng gắn với cách đánh trọng số theo giai đoạn của riêng pipeline đó.
- **"Sao không để LLM tự chọn model cho từng câu?"** LLM không có số thực tế để đo độ chính xác, và số trả lời sẽ không lặp lại được.
  Việc chọn do một luật cố định làm trên số backtest; agent đọc kết quả và giải thích (§6.1).
