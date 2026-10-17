# B3c: eval câu hỏi dự báo với LLM thật

Bước B3c trong [ke_hoach_ai_gd2.md](ke_hoach_ai_gd2.md) §4: chạy chat có tool dự báo (`get_forecast`, `get_forecast_backtest`)
với mô hình ngôn ngữ thật, trên bộ câu **mới**, và chấm theo bốn nhóm do sổ giao việc nêu ([giao_viec_agent_gd2.md](giao_viec_agent_gd2.md) §3.3).

Đây là **live eval**: kết quả không trộn với test dùng provider giả (`tests/test_ai_forecast.py`).

---

## 1. Chốt bộ câu trước lượt gọi mô hình đầu tiên

Ghi ngày 2026-10-15, **trước** lần gọi mô hình đầu tiên cho bộ này.

| Mục | Giá trị |
|---|---|
| Bộ câu | `gm` (GM01–GM15) trong `scripts/ops/ai_live_eval.py` |
| Mã băm bộ câu (câu hỏi, tiêu chí chấm máy, tiêu chí đọc tay) | `34347d35334ab02e` (cách băm cũ; hàm băm sửa 2026-10-16 để tập hợp lồng nhau ổn định, cùng nội dung nay là `1176eaf10ab546c0`) |
| Mã băm code chat + script eval | `3c18e80969f6d5ef` (`apps/retail_app/ai_explain/*.py`, `dwh/releases.py`, script eval) |
| Prompt / catalog / tool | `b3-2026-10-15` / `b3-2026-10-15` / `v1.5` |
| Bản dữ liệu | `fc14b8a2f5a24ff99a434d7c` (run `b3b-01`, snapshot `5bd9a84aaf73`), local DuckDB, chế độ versioned |
| Mô hình | `deepseek-flash` qua `api.deepseek.com` (mặc định của `ai_explain/provider.py`) |

**Vì sao không commit để chốt:** PM chưa yêu cầu commit. Mã băm in ra ở mỗi lần chạy và ghi vào mỗi dòng log;
sửa câu hỏi hay tiêu chí thì mã băm đổi, và bộ đó không còn được gọi là "bộ mới".

**Vì sao không dùng bộ G\*:** phần lớn câu của bộ G\* (tháng 8/2023, cả năm 2024, "model nào chính xác nhất", SARIMAX toàn chuỗi,
năm 2025) đã dùng trong test và script review lúc phát triển B3a. Bộ GM tránh cả kỳ lẫn ý của các câu đó.

**Đã sửa rubric trước khi chạy** (`--kiem-rubric`, không gọi mô hình): khoảng 80% và chữ "chỉ 1/31 ngày" là nhãn do app gắn,
không phải ô dữ liệu, nên chuyển sang tiêu chí đọc tay; lời gọi mẫu của GM15 phải có `cogs_method` (tool đòi chọn cách COGS
kể cả khi chỉ hỏi G). Sau sửa: 15/15 case không lỗi rubric.

**Số đối chứng:** lấy từ parquet do stage dự báo ghi (`warehouse/pipeline/runs/b3b-01/forecast/`), không qua dbt hay tool chat;
G thực tế lấy từ `data/sales.csv`. Tool trả đúng các số này ở bước kiểm rubric.

## 2. Bộ câu và tiêu chí (ghi trước khi chạy)

Chấm máy: trạng thái, tool và tham số, số dẫn trỏ đúng ô, chuỗi phải có, chuỗi cấm. Đọc tay: các ý trong cột cuối.
Nhãn "dự báo", nhãn G, khoảng 80% (theo ngày), sai số tháng điển hình và "không phải model chính" do **app** gắn cạnh số;
phần chấm mô hình là: gọi đúng tool với đúng kỳ, dẫn đúng ô, lời văn không gọi dự báo là thực tế, không bịa lý do.

| Câu | Nhóm | Câu hỏi | Trạng thái nhận | Số phải có | Đọc tay |
|---|---|---|---|---|---|
| GM01 | Nhãn dự báo | Doanh thu gộp dự kiến của tháng 3 năm 2024 là bao nhiêu? | ok | 118.649.475 | gọi là dự báo; không gọi là R hay doanh thu thực nhận; không tự đặt khoảng cho số tháng |
| GM02 | Nhãn dự báo | Ngày 29/02/2024 công ty dự kiến bán được bao nhiêu, tính theo doanh thu gộp? | ok | 1.600.408 | khoảng 80% (1.114.447 – 2.237.503) đi cùng số ngày; không nói số là chắc chắn |
| GM03 | Nhãn dự báo | Theo mô hình, giá vốn tháng 11/2023 sẽ khoảng bao nhiêu? | ok | 45.033.956 | nói là dự báo giá vốn, không gọi là doanh thu |
| GM04 | Nhãn dự báo | Tổng doanh thu gộp dự báo cho năm 2023 là bao nhiêu? | ok | 1.063.819.301 | không cộng hay so với thực tế 2022 |
| GM05 | Ngoài kỳ | Tháng 7/2024 dự báo doanh thu bao nhiêu? | ok | 4.578.009 | nói rõ chỉ ngày 01/07/2024 có dự báo; không gọi là doanh thu cả tháng |
| GM06 | Ngoài kỳ | Có dự báo doanh thu cho tháng 10/2024 không? | no_data | — | nói kỳ dự báo chỉ tới 2024-07-01; không đưa số, không ngoại suy |
| GM07 | Ngoài kỳ | Dự báo số đơn hàng tháng 5/2023 là bao nhiêu? | unsupported | — | nói chưa có dự báo số đơn; không đưa G thay cho số đơn |
| GM08 | Thực tế / dự báo | Năm 2024 công ty đã bán được tổng cộng bao nhiêu tiền? | no_data, ok, needs_clarification | nếu ok: G dự báo 2024 | nói không có số thực tế 2024; nếu đưa số thì là dự báo có nhãn, chỉ tới 2024-07-01, không viết là "đã bán" / "thực tế" |
| GM09 | Thực tế / dự báo | (sau GM01) Vậy so với cùng tháng năm 2022 thực tế thì thế nào? | ok, needs_clarification, unsupported | nếu ok: G thực tế 3/2022 = 137.537.949 | hai phần riêng, mỗi phần một nhãn; không tính chênh lệch hay % giữa dự báo và thực tế; không lấy R thực tế để so |
| GM10 | Thực tế / dự báo | Dự báo G từ tháng 12/2022 đến tháng 2/2023 | ok, needs_clarification, unsupported | — | 12/2022 là thực tế (không lấy từ `get_forecast`), 01–02/2023 là dự báo; không cộng thành một tổng |
| GM11 | Chọn model | LightGBM có chính xác hơn SARIMAX không? | ok | một ô điểm ngày và một ô MAPE G tháng | nêu cả hai thước (điểm ngày: LightGBM tốt hơn; MAPE G tháng: SARIMAX tốt hơn); nói là backtest 2020–2022 |
| GM12 | Chọn model | Model đang dùng có hơn hẳn cách lấy lại số cùng kỳ hai năm trước không? | ok | một ô so với mốc sàn | so với seasonal naive 2 năm bằng số; nói là backtest, điểm thắng lạc quan |
| GM13 | Chọn model | Sai số backtest của model chính là bao nhiêu, đo trên giai đoạn nào? | ok | điểm ngày hoặc MAPE G tháng của model chính | nói đo trên backtest 2020–2022, không phải độ chính xác 2023–2024 |
| GM14 | Chọn model | Tại sao không chọn model gộp làm model chính, trong khi sai số tháng của nó thấp hơn LightGBM? | ok | lý do chọn hoặc điểm ngày | lý do lấy từ luật (bước 2) và điểm hai model; không bịa lý do khác |
| GM15 | Chọn model | Cho mình xem dự báo tháng 12/2023 theo SARIMAX | ok, needs_clarification | nếu ok: G của biến thể SARIMAX | nếu trả số: ghi không phải model chính và biến thể nào (toàn chuỗi 46.937.419 / từ 2019 43.528.034); không trả số model chính thay vào |

Lệnh chạy (từ root):

```bash
RETAIL_RELEASE_MODE=versioned RETAIL_RELEASE_STATE=warehouse/pipeline/state.json \
  .venv/Scripts/python.exe scripts/ops/ai_live_eval.py --set gm --kiem-rubric    # không gọi mô hình
RETAIL_RELEASE_MODE=versioned RETAIL_RELEASE_STATE=warehouse/pipeline/state.json \
  .venv/Scripts/python.exe scripts/ops/ai_live_eval.py --set gm --runs 3         # gọi mô hình thật, tốn phí API
```

Bộ dự báo từ chối chạy ở chế độ cũ: ở đó mọi câu trả `no_data`, các ca chờ `no_data` sẽ đạt giả.

## 3. Kết quả lần chạy 2026-10-15

| Mục | Giá trị |
|---|---|
| Log | `warehouse/ai_eval/live_20261015T161752Z_gm_2920.jsonl` (Git ignore; mỗi dòng có câu hỏi, tool + tham số, câu trả lời đã kiểm, claim → giá trị, lỗi kiểm, token, mã băm, bản dữ liệu) |
| Số lượt | 15 câu × 3 lần = 45 lượt (GM09 chạy kèm lượt GM01 trước nó); 109 lần gọi mô hình |
| Bản dữ liệu | mọi lần đọc tool có `release_id` = `fc14b8a2f5a24ff99a434d7c` trong evidence; mã băm bộ `34347d35334ab02e`, code `3c18e80969f6d5ef` ở mọi dòng |
| Token, chi phí | vào 1.195.688, ra 19.339; **ước** khoảng 0,38 USD theo giá cao điểm (chỉ ước, số thật xem trang billing của DeepSeek). Thời gian trung bình 3,6 giây một lượt, lâu nhất 6,0 giây |
| Chấm máy | **33/45** lượt đạt |
| Chấm máy + đọc tay | **27/45** lượt đạt (đọc tay đánh trượt thêm 6 lượt máy cho đạt, bảng dưới). Hai trong sáu lượt đó (GM13) trượt vì lỗi hiển thị ".,2f", là lỗi khách quan nhưng **ngoài** tiêu chí ghi trước; chấm đúng theo tiêu chí ghi trước là **29/45** |

**Điều quan trọng nhất:** không lượt nào hiện một con số không có trong kết quả tool, và không lượt nào gọi số dự báo là số thực tế.
Mọi lượt trượt thuộc một trong ba loại: bước kiểm của app chặn nhầm câu trả lời đúng (người dùng chỉ thấy bảng số), câu hỏi lại chưa đúng chỗ,
hoặc lời văn sai ở chỗ không phải con số (một lỗi hiển thị và một câu giải thích sai).

### 3.1 Theo nhóm

| Nhóm | Câu | Đạt (máy + tay) | Nhận xét |
|---|---|---|---|
| Đúng nhãn dự báo | GM01–GM04 | **12/12** | Số đúng ô, khớp số đối chứng từ parquet (118.649.475; 1.600.408 kèm khoảng 80% 1.114.447 – 2.237.503; 45.033.956; 1.063.819.301). Câu nào cũng nói rõ là dự báo G, số thực tế dừng ở 2022-12-31 |
| Từ chối ngoài kỳ | GM05–GM07 | **8/9** | Tháng 7/2024 nói rõ chỉ 1/31 ngày có dự báo; tháng 10/2024 từ chối, không ngoại suy. GM07 lần 1 trả `ok` kèm số G tháng 5/2023 khi được hỏi số đơn (có ghi rõ "không phải số đơn hàng") |
| Không nhầm thực tế / dự báo | GM08–GM10 | **3/9** | GM08 (năm 2024 "đã bán") 3/3 đúng: báo không có số thực, đề nghị số dự báo. GM09 và GM10 trượt cả 3 lần (mục 3.2) |
| Giải thích việc chọn model bằng dữ liệu | GM11–GM15 | **4/15** | Lượt nào hiện câu trả lời thì số và lý do đều lấy từ backtest (GM11 nêu đủ hai thước: điểm ngày LightGBM 577.160 < SARIMAX 617.357; MAPE G tháng SARIMAX 8,2% < LightGBM 11,4%). Phần lớn lượt trượt là bước kiểm của app chặn nhầm |

### 3.2 Lượt trượt: nguyên nhân và đề xuất sửa (chưa sửa, chờ PM xem)

| Câu | Lượt trượt | Chuyện gì xảy ra | Lỗi của ai | Đề xuất sửa |
|---|---|---|---|---|
| GM10 "Dự báo G từ tháng 12/2022 đến tháng 2/2023" | 3/3 | Mô hình làm đúng: gọi dự báo cho 12/2022 (tool từ chối vì là kỳ thực tế), 01/2023 và 02/2023, rồi viết câu tách hai phần. Bước kiểm của app đọc câu hỏi chỉ thấy hai đầu mút 12/2022 và 2/2023, coi số tháng 01/2023 là "sai kỳ" và chặn. Lần 3 mô hình chuyển sang hỏi lại | **App (kiểm quá chặt)** | Bộ đọc kỳ trong câu hỏi hiểu "từ tháng X đến tháng Y": mọi tháng ở giữa đều là kỳ được hỏi |
| GM09 "(sau GM01) Vậy so với cùng tháng năm 2022 thực tế thì thế nào?" | 3/3 | Lần 1 (máy cho đạt): chỉ đưa G thực tế 3/2022 và nói sai rằng G dự báo và G thực tế là "hai tập đơn khác nhau" (đúng với G so R, sai với G so G). Lần 2: app đọc "tháng năm 2022" thành **tháng Năm** (tháng 5) 2022, chặn số dự báo, mô hình chuyển sang `no_data`. Lần 3: mô hình dẫn `T2` của lượt trước; app chặn đúng | Prompt (lần 1), **app** (lần 2), mô hình (lần 3, đã bị chặn) | Sửa quy tắc 16 của prompt: G dự báo và G thực tế cùng định nghĩa, được đặt cạnh nhau, mỗi số một nhãn, không tính chênh lệch; chỉ cấm so với R. Bộ đọc kỳ: "cùng tháng năm 2022" là năm, không phải tháng 5 |
| GM12, GM13, GM14 (so mốc sàn, sai số model chính, vì sao không chọn bản gộp) | 2/3, 1/3, 2/3 | Câu trả lời dẫn đúng điểm của từng model, nhưng app chặn vì ba luật viết cho câu "model nào chính xác nhất": (a) đòi dẫn đúng ô `derived.lowest_score` / `lowest_mape_g_thang` dù câu đã dẫn điểm của chính model được hỏi; (b) cấm "thấp hơn", "vượt" giữa hai số vì không có cột chênh lệch do tool tính; (c) đọc "dẫn đầu", "thứ hạng" là "cao nhất", trong khi với sai số thì thấp mới là tốt | **App (kiểm quá chặt)** | (a) nhận mọi claim của thước `score` / `mape_g_thang` là đã dẫn thước, chỉ đòi `lowest_*` khi câu hỏi có "nhất"; (b) cho phép so hai số backtest khi cả hai đều được dẫn và app kiểm được chiều; (c) thước sai số: "dẫn đầu" nghĩa là thấp nhất |
| GM13 | 2 lượt máy cho đạt | Câu hiện "mỗi fold dự báo **.,2f** ngày": mô hình dẫn `trained_through` (ngày train tới 2022-12-31) như thể là số ngày mỗi fold, và app định dạng ô kiểu ngày bằng hàm số nên in ra chuỗi rác | Mô hình (dẫn sai ô) + **app (lỗi hiển thị)** | App định dạng ô ngày thành ngày (31/12/2022) và kiểm chữ đứng trước chỗ đặt: "số ngày" không được trỏ vào ô ngày. Tool backtest có thể trả thêm số ngày mỗi fold (548) để mô hình khỏi đoán |
| GM15 "Cho mình xem dự báo tháng 12/2023 theo SARIMAX" | 3/3 theo đọc tay | Cả 3 lần đều hỏi lại (trạng thái được chấp nhận), nhưng mô hình tự chọn SARIMAX toàn chuỗi mà không nói còn bản train từ 2019. Tool đòi chọn cách COGS dù chỉ hỏi G (G của hai cách COGS bằng nhau). Lần 2, 3 còn gợi ý "chỉ cần G thì dùng model chính", tức thay model được hỏi bằng model chính | Tool + prompt | Tool: chỉ hỏi cách COGS khi câu hỏi có COGS; tên họ model ("SARIMAX", "LightGBM") thì trả danh sách biến thể để hỏi lại. Prompt: không gợi ý thay bằng model chính khi người hỏi nêu đích danh model |
| GM11 "LightGBM có chính xác hơn SARIMAX không?" | 1/3 | Lần 1 mô hình truyền `model='lightgbm'` (không phải mã ứng viên), tool trả không có; rồi hỏi lại biến thể. Lần 2, 3 gọi không tham số và trả lời đúng | Mô hình + mô tả tool | Mô tả tham số `model` liệt kê mã ứng viên của bản dữ liệu, hoặc nhận tên họ model; prompt: so sánh họ model thì gọi `get_forecast_backtest` không truyền `model` |
| GM07 "Dự báo số đơn hàng tháng 5/2023?" | 1/3 | Lần 1 trả `ok` kèm số G (có ghi rõ không phải số đơn, chưa hỗ trợ dự báo số đơn) | Mô hình | Bước kiểm: câu hỏi dự báo chỉ tiêu không có dự báo (số đơn, khách, R) thì không cho `ok`, như luật lọc nhóm đã có |

**Ghi chú nhỏ (đạt nhưng nên sửa):** GM05 có câu lặp ý "nằm ngoài kỳ dự báo, không có số nằm ngoài kỳ dự báo nên không có số"
vì `derived.missing_part` là cả một mệnh đề; nên đổi thành cụm danh từ ("2024-07-02 → 2024-07-31, 30 ngày").
Câu trả lời dự báo nào cũng tự thêm câu "Model chính được chọn vì …" dù không được hỏi; đúng dữ liệu nhưng dài.

### 3.3 Phần nào do app, phần nào do mô hình

Nhãn "dự báo G", khoảng 80% theo ngày, sai số tháng điển hình, "chỉ 1/31 ngày có dự báo", "không phải model chính" và dòng
`model_version` / `trained_through` dưới câu trả lời đều do **app** gắn từ kết quả tool, nên nhóm "đúng nhãn" chủ yếu đo code của app
(đã có test không gọi LLM). Phần mô hình kiểm soát: chọn đúng tool và kỳ, dẫn đúng ô, lời văn không gọi dự báo là thực tế, không bịa lý do.

### 3.4 Giới hạn của lần chạy

- Một mô hình (`deepseek-flash`), 3 lần mỗi câu, một bản dữ liệu local. Chưa chạy trên Databricks.
- Bộ GM đã dùng xong: sửa prompt, tool hay bước kiểm theo mục 3.2 thì lần nghiệm thu sau cần bộ câu mới (B7 có bộ held-out riêng).
- Chưa có câu "vì sao tháng 8/2023 giảm" (B4, chưa làm) và câu vẽ biểu đồ (B6).
- Lần chạy trước khi PM trả lời việc agent tự kèm ghi chú "đo theo tháng thì SARIMAX chính xác hơn", và trước khi Codex kiểm lại RV10, RV11.

## 4. Sửa theo đề xuất (PM duyệt 2026-10-16)

PM duyệt sửa cả 7 đề xuất ở mục 3.2. Không đổi model, luật chọn, thước đo hay quyết định dự báo.

| Đề xuất | Đã sửa | File |
|---|---|---|
| GM10 khoảng tháng | Bộ đọc kỳ hiểu "từ tháng 12/2022 đến tháng 2/2023" (vắt qua năm): mọi tháng ở giữa là kỳ được hỏi | `evidence.question_periods` |
| GM09 "cùng tháng năm 2022"; G dự báo cạnh G thực tế | "cùng tháng / cùng kỳ năm YYYY" là năm YYYY, không phải tháng 5 ("tháng năm 2023" đứng riêng vẫn là tháng 5). Câu hỏi so sánh tiếp nối được dẫn lại số dự báo của kỳ lượt trước nếu vế câu ghi đúng kỳ của số; luật "hỏi thực tế mà dẫn dự báo" chỉ chặn số dự báo của chính kỳ được hỏi. Quy tắc 16 của prompt: G dự báo và G thực tế cùng định nghĩa, đặt cạnh nhau với nhãn riêng, không tính chênh lệch; chỉ R mới khác tập đơn | `evidence.forecast_question_errors`, `service._context_periods`, `service.system_prompt` |
| GM12–GM14 luật câu độ chính xác | (a) ô điểm của chính model (`derived.primary.score`, `rows[..].mape_g_thang`) tính là đã dẫn thước; (b) câu "{a} thấp hơn {b}" giữa hai số cùng thước backtest được nói khi app kiểm đúng chiều; "vượt mốc sàn" dẫn được `beats_floor_all_folds`; (c) với sai số, "dẫn đầu / đứng đầu" là thấp nhất; (d) câu mô tả luật chọn ("lấy điểm thấp nhất") không có chỗ đặt không bị coi là câu xếp hạng | `evidence.validate`, `_verified_backtest_compare` |
| GM13 ".,2f" | Ô kiểu ngày in dd/mm/yyyy; "{ô ngày} ngày" bị chặn; backtest trả `derived.n_folds` | `evidence._fmt`, `evidence.validate`, `tools._forecast_backtest` |
| GM15 "theo SARIMAX" | Tên họ model (`sarimax`, `lightgbm`, `arima`, `bản gộp`) không trùng mã ứng viên: tool trả danh sách biến thể để hỏi lại; họ chỉ một biến thể thì dùng luôn. Chỉ hỏi G thì không đòi cách COGS (tool kiểm G giống nhau giữa các cách COGS trên kỳ được hỏi, khác thì vẫn hỏi lại). Prompt: không tự chọn biến thể, không gợi ý thay bằng model chính | `tools._pick`, `tools._forecast` |
| GM11 `model='lightgbm'` | `get_forecast_backtest` nhận tên họ: trả cả bảng kèm `derived.family`; prompt: so hai họ model thì không truyền `model` | `tools._forecast_backtest`, prompt |
| GM07 dự báo số đơn | Câu hỏi "dự báo / dự kiến + số đơn, khách, R, lợi nhuận..." không được trả `ok`; `unsupported` kèm số G thay thế có ghi rõ thì được | `evidence.forecast_question_errors` |
| Ghi chú GM05 | `derived.missing_part` thành cụm danh từ ("2024-07-02 → 2024-12-31 (183 ngày)") | `tools._forecast` |

Phiên bản: prompt `b3c-2026-10-16`, tool `v1.6`, catalog không đổi (`b3-2026-10-15`).

**Kiểm (provider giả, local):** 16 test mới `test_b3c_*` trong `tests/test_ai_forecast.py` (mỗi đề xuất có ca đạt và ca bị chặn); bộ hồi quy §8 510 passed; năm script review của Codex exit 0.

**Chạy lại bộ GM với LLM thật sau sửa** (2026-10-16, 1 lần, `warehouse/ai_eval/live_20261015T224746Z_gm_29128.jsonl`, ước 0,12 USD):
14/15 lượt đạt chấm máy; đọc tay các câu từng trượt (GM05, GM07, GM09, GM10, GM11, GM12, GM13, GM15) đều đúng tiêu chí ghi trước.
GM14 còn bị chặn vì câu mô tả luật chọn ("lấy điểm thấp nhất"); đã sửa (điểm (d) ở trên) rồi chạy lại riêng GM14 3 lần (`live_20261015T235021Z_gm_15224.jsonl`, ước 0,04 USD): 2/3 đạt; lượt còn lại bị chặn **đúng** vì mô hình tự viết chữ số "1" (ngưỡng hòa 1%) ngoài chỗ đặt.
Đây **không phải** nghiệm thu: bộ GM đã dùng và đã được dùng để sửa. Nghiệm thu cần bộ câu mới (B7).
**Kiểm hồi quy sau khi B6 rút gọn prompt** (`b6-2026-10-16b`, 2026-10-16, bộ đã dùng, không phải nghiệm thu):
chạy bộ GM 1 lần (`live_20261016T002052Z_gm_25908.jsonl`, ước 0,13 USD): 14/15. GM09, GM12, GM14 (các câu dựa vào phần chữ đã rút gọn)
vẫn đúng. GM10 lộ một chặn nhầm mới của luật RV07: chữ "gộp" trong "doanh thu **gộp**" (tên của G) bị coi là chữ chỉ tổng khoảng. Đã sửa
(`evidence._NOT_AGG`, kèm test ca đạt và ca "gộp hai tháng" vẫn bị chặn), chạy lại GM10 2 lần: 2/2 (`live_20261016T002317Z_gm_*.jsonl`).

## 5. Ghi chú thước tháng và chạy lại bộ GM (2026-10-17)

PM chọn (2026-10-17) cho agent tự kèm ghi chú khi thước tháng xếp model khác tốt hơn model chính. Đây là phần "chưa có" ở quyết định
2026-10-15 ([ke_hoach_ai_gd2.md](ke_hoach_ai_gd2.md) §2). Model chính, luật chọn và thước đo không đổi.

- **Cách làm:** app gắn ghi chú (`tools._month_metric_note`, `ToolResult.notes`), không qua câu văn của mô hình, không thêm chữ vào
  prompt. Ghi chú hiện dưới câu trả lời dự báo G theo tháng / năm / cả vùng khi ứng viên đang đọc là model chính. Tên model và hai số
  MAPE lấy từ `rpt_forecast_backtest` của bản dữ liệu đang phục vụ. Bản hiện tại: "Theo sai số tháng (MAPE G tháng, backtest
  2020–2022), log + SARIMAX, train toàn chuỗi sai ít hơn model chính: 8,2% so với 11,4%. Model chính được chọn theo điểm ngày kết
  hợp…". Không có ghi chú khi hỏi theo ngày, chỉ hỏi COGS, hỏi đích danh một model, hoặc khi model chính cũng có MAPE thấp nhất.
- **Kiểm:** test đối chứng với parquet backtest của stage ([review](review_codex_ai_gd2_20261015.md) §9.11).
- **Chạy lại bộ GM với AI thật** (bộ đã dùng, không phải nghiệm thu; mã băm bộ `1176eaf10ab546c0` không đổi):
  - prompt `b6-2026-10-17`, 1 lần (`live_20261017T055250Z_gm_28504.jsonl`): chấm máy 15/15. Đọc tay: ghi chú thước tháng hiện ở GM01,
    GM04, GM05, GM07, GM09, GM10. GM11–GM14 không còn nói "điểm của model thắng là lạc quan" (0/4; lần chạy 16/10: 4/4), vì bản này
    rút câu đó khỏi quy tắc 16.
  - Prompt `b6-2026-10-17b` trả câu đó lại; chạy lại GM11–GM14 (`live_20261017T060500Z_gm_30244.jsonl`): 4/4 đạt, cả 4 câu nói
    "lạc quan".
  - Lời hơi lủng củng, chưa sửa: GM14 in "Hai thước xếp hạng khác nhau ở đây (**có**)".
- Chi phí ước: 0,12 + 0,04 USD.

