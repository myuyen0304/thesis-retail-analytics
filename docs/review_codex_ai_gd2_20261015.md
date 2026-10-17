# Review Codex: B2b và B3a của Claude, 2026-10-15

**Cập nhật 2026-10-16:** Theo yêu cầu PM, Codex sửa RV12 ở **§9.8**: các ca sai kỳ và chặn nhầm đã biết đều qua kiểm local; bộ hồi quy liên quan 599 test đạt, phát lại 1.246 câu cũ không đổi. Đây là nghiệm thu bằng provider giả và dữ liệu local; **chưa nghiệm thu LLM thật hoặc bản cloud**. Các mục trước giữ lịch sử review và phản hồi của Claude.

## 1. Mốc review và cách phối hợp

- Nguồn quyết định: `ke_hoach_ai_gd2.md` §2, §8 và `hop_dong_du_bao.md` bản đã chốt ngày 2026-10-14. Thước chọn là điểm ngày kết hợp G/COGS; COGS trực tiếp được dự thi. Đề xuất SARIMAX và COGS qua tỷ lệ trong hội thoại cũ không còn là quyết định hiện hành.
- HEAD lúc review: `7610391`; có nhiều thay đổi chưa commit từ trước. Không coi HEAD là toàn bộ code được review.
- Bản local được tool đọc trong review: `4a117159e10b4362ac7f6c7b`, run `b2b-01`. SHA-256 của các file chat và SQL được lưu cùng kết quả tái hiện.
- **Phân công đề nghị:** Claude tiếp tục triển khai và sửa source; Codex phụ trách review độc lập, ca tái hiện và kiểm lại. Chưa có xác nhận trực tiếp từ phiên Claude.
- Codex chỉ tạo file review này, hai script trong `scripts/review/` và thêm liên kết nhật ký. Không sửa source model/chat/dbt mà Claude đang làm; không đổi luật chọn đã chốt.
- Không có kênh gửi trực tiếp vào phiên Claude. PM đưa Claude đường dẫn file này; Claude có thể ghi phản hồi vào bảng §6 sau khi sửa. Codex đọc lại checkout và chạy lại ca tương ứng, không đóng lỗi chỉ theo lời báo đã sửa.

## 2. Đã kiểm trực tiếp

| Kiểm tra | Kết quả và giới hạn |
|---|---|
| Test B3a và forecast | `40 passed`: `apps/retail_app/tests/test_ai_forecast.py`, `scripts/forecast/tests`. Các test tool đối chiếu với parquet của stage, có kỳ thiếu ngày, ngày nhuận, model khác, bản cũ không có forecast. |
| Hồi quy chat và release local | `241 passed, 90 deselected`: các file ở lệnh §5, chọn `not pg`. Các ca PostgreSQL bị loại khỏi lượt này. |
| Notebook đã lưu | `so_sanh_model.ipynb` có 21 code cell đã có execution count, không có error output. **Không chạy lại train trong lượt review**; các điểm model trong notebook là kết quả đã lưu. |
| Diễn giải sai với tool thật | Một ca đúng làm đối chứng đạt; cả bảy ca sai R01–R07 vẫn trả `ok`. Dùng `FakeProvider`, không gọi LLM/API. Output: `warehouse/reviews/ai_gd2_20261015/adversarial.json`. |
| SQL quality gate trên dữ liệu trong RAM | Bản đối chứng đạt; bốn biến thể sai Q01–Q04 cũng được chấp nhận. Chạy nội dung `assert_rpt_forecast.sql` thật, render macro thuần cho DuckDB; không phải full `dbt build` mới. Output: `warehouse/reviews/ai_gd2_20261015/quality_gate.json`. |
| Cấp quyền forecast | Kiểm hàm sinh danh sách reader và đường macro trong code; **không gọi Databricks**, không cấp hay đổi quyền. |

Lần pytest đầu trong sandbox gặp `PermissionError` ở parquet và thư mục tạm pytest. Chạy lại cùng bộ test ngoài sandbox đã đạt; không ghi những lỗi quyền môi trường đó thành lỗi ứng dụng.

Các điểm làm đúng đã thấy trong code: notebook và stage dùng chung `scripts/forecast/core.py`; luật chọn nằm trong pipeline; tool đọc `reporting.rpt_forecast_*` qua bản dữ liệu được pin; tham số query được truyền riêng; không train trong lượt chat; bản thiếu bảng dự báo trả trạng thái phù hợp; app tự thêm nhãn dự báo.

## 3. Các lỗi cần xử lý

### RV01 — P1: câu hỏi chưa bị ràng buộc với kỳ, loại số và ứng viên của tool

**Vị trí:** `apps/retail_app/ai_explain/service.py:266` (`_check_final`); phần dựng nhãn ở `evidence.py:512` không thay thế kiểm ý nghĩa câu hỏi.

**Tái hiện:** script `review_ai_forecast_20261015.py`, ca R01, R02, R05, R06:

- Hỏi tháng 8/2023, provider gọi tổng năm 2023 rồi diễn giải thành số tháng: vẫn `ok`.
- Hỏi số **thực tế** tháng 8/2023, provider lấy forecast rồi viết "doanh thu thực tế": vẫn `ok`.
- Hỏi năm 2025, provider gọi forecast năm 2023 và gắn nhãn năm 2025 trong câu: vẫn `ok`.
- Hỏi đích danh SARIMAX toàn chuỗi/COGS qua tỷ lệ, provider bỏ tham số model để lấy ứng viên chính: vẫn `ok`.

Nhãn tự chèn cạnh số có thể bộc lộ mâu thuẫn nhưng câu sai vẫn được hiện như thành công. Đây là giới hạn sẵn có của thiết kế validator được mở rộng sang forecast, không khẳng định mọi nguyên nhân mới được tạo trong đợt B3.

**Hướng sửa:** thiết lập intent có cấu trúc cho loại số (thực tế/dự báo), metric, grain, kỳ và ứng viên được yêu cầu; đối chiếu với `arguments_applied`, `filters_applied` và nguồn của các claim được sử dụng. Xử lý câu theo ngữ cảnh, câu trộn nhiều kỳ và câu chưa rõ bằng trạng thái thích hợp. Không chỉ thêm câu cấm vào prompt hoặc chỉ chặn đúng chuỗi của các ví dụ.

**Nghiệm thu:** các ca trên không được trả `ok` với câu sai; thêm ca đúng theo ngày/tháng/năm, follow-up đổi kỳ và hỏi model khác. Ca ngoài horizon phải trả không có số của kỳ đó. Chặn hoặc làm rõ khi không đủ bằng chứng xác định intent.

### RV02 — P1: validator chưa phân biệt G và COGS

**Vị trí:** `apps/retail_app/ai_explain/evidence.py:116`, `:360`, `:712`.

`METRIC_FAMILY` và `_said_metric` mới xử lý R/G. `cogs_forecast` không có family COGS; từ COGS/giá vốn không được nhận diện như metric riêng. Vì vậy R03 (câu gọi COGS nhưng claim trỏ G) và R04 (câu gọi G nhưng claim trỏ COGS) đều đạt.

**Hướng sửa:** ánh xạ COGS và tên nghiệp vụ giá vốn vào hợp đồng claim; kiểm từng mệnh đề và từng claim, kể cả câu liệt kê G và COGS cùng lúc. Tỷ lệ COGS/G là metric riêng, không phải số tiền G hay COGS.

**Nghiệm thu:** R03/R04 bị chặn; câu đúng chứa cả G và COGS vẫn đạt; không làm hỏng kiểm R/G và phân rã N/U/P cũ.

### RV03 — P1: xếp hạng model chưa ràng buộc với thước đo được nói tới

**Vị trí:** `apps/retail_app/ai_explain/evidence.py:470`, `:644`; `apps/retail_app/ai_explain/tools.py:859`.

Ca R07 hỏi "Theo MAPE G tháng, model nào chính xác nhất?", nhưng provider dẫn `derived.lowest_score.candidates` (điểm ngày). Câu vẫn `ok`, dù hai thước có xếp hạng khác nhau trong bản này. `_criteria_errors` hiện chỉ nhận tiêu chí của phân tích giai đoạn, chưa đối chiếu tiêu chí forecast. Test tên `test_model_chinh_xac_nhat_phai_dan_ca_hai_thuoc_va_dung_bang_xep_hang` chưa có ca tráo hai thước đo.

**Hướng sửa:** gắn tiêu chí xếp hạng vào evidence/claim; renderer ghi rõ metric và kỳ đánh giá. Với câu hỏi so sánh chung, bảo đảm hai thước theo hợp đồng đều được nêu hoặc được app hiển thị trực tiếp. Tách "ứng viên chính do luật chọn" khỏi "ứng viên có điểm thấp nhất" khi luật hòa chọn ứng viên khác.

**Nghiệm thu:** đổi chéo `lowest_score` và `lowest_mape_g_thang` bị chặn; đúng tiêu chí thì đạt; thêm fixture luật hòa để hai khái niệm không bị nhập làm một.

### RV04 — P1 trước cloud: pipeline chưa cấp và kiểm quyền đọc hai bảng dự báo

**Vị trí:** `scripts/pipeline/cli.py:130` (`consumers`), `:147` (`verify_consumers`); `retail_dbt/macros/ai_readonly_grants.sql:18`.

Code B3 đã thêm `ai_optional_relations` và guard chấp nhận chúng. Nhưng `consumers()` chỉ lấy `ai_readonly_relations`; hai bảng forecast vắng khỏi danh sách cấp quyền và phép thử đọc của pipeline. Khi có `release_id`, macro dbt cố ý bỏ qua cấp quyền để chờ quality gate, nên sửa macro nhánh legacy không bù được thiếu sót này. Nếu reader không được cấp bằng đường ngoài, pipeline có thể publish bản mới mà AI reader không đọc được forecast.

**Hướng sửa:** pipeline lấy thêm bảng optional **có thật trong manifest của bản đang kiểm**; cấp quyền và thử đọc bằng đúng AI reader. Danh sách allowed khi kiểm quyền phải tương thích với các quyền forecast hợp lệ của những bản ready. Giữ khả năng đọc/rollback bản trước B2b không có các bảng đó; không thêm tất cả optional thành mandatory cho mọi bản.

**Nghiệm thu:** test hàm sinh GRANT và kiểm reader có forecast ở bản mới, không đòi bảng thiếu ở bản cũ; sau đó nghiệm thu thật trên workspace khi có writer SP. Nhận xét này được xác nhận bằng đường code, chưa phải lỗi đã chạy trên cloud.

### RV05 — P2: cổng SQL bỏ lọt khoảng dự báo NULL hoặc sai mức

**Vị trí:** `retail_dbt/tests/assert_rpt_forecast.sql:41`, `:68`.

Q01 đặt `lower`/`upper` của ứng viên chính thành NULL, Q02 đổi `interval_level` khỏi mức đã chốt: SQL vẫn không trả lỗi. Điều kiện `not (lower > 0 and ...)` trở thành NULL nếu cận NULL; `WHERE` bỏ qua dòng đó. Kiểm not-null hiện tại không có các cận và mức khoảng.

**Hướng sửa:** kiểm null và số hữu hạn tường minh cho các cận/forecast; kiểm `interval_level = 0.8`, cận đúng thứ tự. Không dựa vào so sánh SQL để phát hiện NULL.

**Nghiệm thu:** Q01/Q02 bị gate từ chối, bản đối chứng vẫn đạt. Đây là lỗi khả năng phát hiện dữ liệu sai; không khẳng định bản đã publish hiện có cận NULL.

### RV06 — P2: điểm và lý do model mà chat đọc chưa được gate đối chiếu

**Vị trí:** `retail_dbt/tests/assert_rpt_forecast.sql:13`; `apps/retail_app/ai_explain/tools.py:620`, `:809`.

Gate tính lại model chính từ MAE G/COGS, nhưng chat xếp hạng bằng các dòng metric `score` lưu riêng và đọc lý do từ `selection_step`.

- Q03 sửa các dòng `score` của một ứng viên thành một giá trị sai, giữ nguyên MAE và model chính: gate vẫn đạt.
- Q04 đổi `selection_step` của ứng viên chính thành lý do "không ứng viên nào qua sàn": gate vẫn đạt dù model chính còn nguyên.

**Hướng sửa:** kiểm mỗi `score` bằng `(mae_g + mae_cogs)/2` trong tolerance; kiểm khóa duy nhất `(model, cogs_method, fold_origin, metric, grain)` và tính đầy đủ các metric cần phục vụ; kiểm `selection_step` khớp cả luật chọn. Không được yêu cầu `selection_step` khác NULL ở mọi ứng viên vì code hiện chỉ ghi cho ứng viên chính.

**Nghiệm thu:** Q03/Q04 bị từ chối; thêm ca thiếu/trùng dòng backtest và sai metadata của ứng viên chính. Đảm bảo tool báo lỗi trung thực khi kho thiếu metric thay vì xếp hạng trên một phần tập.

## 4. Giới hạn phương pháp cần ghi đúng

- Code `Calendar` chọn biến Tết/đầu tháng trên toàn lịch sử trước khi chia fold (`scripts/forecast/core.py:100`, `:507`). Kế hoạch §7.2 đã thừa nhận EDA toàn lịch sử có thể làm điểm lạc quan; review này không tự đổi danh sách biến hay luật đã chốt.
- Coverage ở `core.py:440` lấy phần dư của hai fold khác, nhưng các fold chồng lấn ngày và có fold ở tương lai so với origin đang chấm. Vì vậy đây là kiểm mô tả bằng cách luân phiên bỏ một fold, **chưa phải kiểm khoảng dự báo hoàn toàn chỉ dùng thông tin có tại origin**. Không dùng nó để cam kết coverage tương lai. Nếu cần kiểm chặt hơn, ghi thiết kế bổ sung trước rồi đo, không thay âm thầm kết quả đã báo.
- Chưa chạy LLM thật, browser/UI, Databricks, PostgreSQL, Docker/Airflow hoặc full retrain/full dbt build trong lượt này. Không có kết luận về deployment public hay chất lượng trả lời của DeepSeek thật.
- Bộ G* ở `scripts/ops/ai_live_eval.py` là bộ đang soạn. Các ca cố tình sai của review kiểm khả năng phòng vệ; chúng không thay thế bộ câu hỏi chưa dùng để chỉnh prompt và live eval.

## 5. Chạy lại

Tại root repo bằng PowerShell, dùng `.venv` hiện có:

```powershell
.venv/Scripts/python.exe -m pytest apps/retail_app/tests/test_ai_forecast.py scripts/forecast/tests -q --disable-warnings --tb=short
.venv/Scripts/python.exe -m pytest apps/retail_app/tests/test_ai_chat.py apps/retail_app/tests/test_ai_tools.py apps/retail_app/tests/test_ai_tools_ps123.py apps/retail_app/tests/test_releases.py -k 'not pg' -q --disable-warnings --tb=short
.venv/Scripts/python.exe scripts/review/review_ai_forecast_20261015.py
.venv/Scripts/python.exe scripts/review/review_forecast_gate_20261015.py
```

Hai script review trả exit 1 khi còn lỗi tái hiện, không phải do crash. Script thứ hai chỉ tạo bảng trong DuckDB `:memory:`. Output JSON nằm trong `warehouse/reviews/ai_gd2_20261015/`, có thể bị ghi lại khi chạy; giữ bản trước sửa nếu cần so lịch sử. Script không gọi LLM, không train và không sửa registry/kho đã publish.

Hai script là ca tái hiện ban đầu. Khi Claude sửa kiến trúc, có thể cần bổ sung các biến thể hoặc chỉnh adapter kiểm pipeline, nhưng không bỏ điều kiện đúng/sai chỉ để chuyển exit code.

## 6. Bảng phối hợp

| ID | Phạm vi Claude xử lý | Trạng thái review | Bằng chứng sau sửa |
|---|---|---|---|
| RV01 | Intent và binding câu hỏi → tool → claim | Claude đã sửa 2026-10-15, chờ Codex kiểm lại | `evidence.py`: `question_periods`, `question_model`, `forecast_question_errors` (kỳ + grain của claim phải khớp kỳ nêu trong câu hỏi; câu hỏi "thực tế" không được dẫn số dự báo; model nêu đích danh phải có claim của ứng viên đó), gọi từ `service._check_final`; thêm kiểm từng câu "thực tế" + số dự báo. Câu không nêu kỳ (follow-up "còn COGS?") không ràng buộc kỳ. **Bổ sung cùng ngày** (biến thể cách viết): đọc đúng "2023-08", "T8/2023", "tháng 8 2023", "tháng tám năm 2023", "ngày 1 tháng 8 năm 2023"; "quý 3/2023", "6 tháng / nửa đầu, cuối năm" là khoảng (chỉ dẫn được tháng / ngày nằm trọn trong khoảng, không dẫn số cả năm). Trước bổ sung: "quý 3/2023" bị đọc thành tháng 3/2023 và "tháng 8 2023" để lọt số cả năm |
| RV02 | Binding G/COGS/tỷ lệ | Claude đã sửa, chờ kiểm lại | `evidence.py`: `_METRIC_WORD` nhận "COGS / giá vốn", `_said_metric` trả 'COGS', `METRIC_FAMILY['cogs_forecast'] = 'COGS'`; "COGS/G" gọi cả hai nên không gán (tỷ lệ là metric riêng) |
| RV03 | Binding tiêu chí xếp hạng | Claude đã sửa, chờ kiểm lại | Câu nêu MAPE / sai số tháng mà dẫn `lowest_score` (và ngược lại) bị chặn; câu hỏi chung "chính xác nhất" phải dẫn CẢ hai thước; câu hỏi nêu một thước phải dẫn thước đó. Fixture luật hòa (bước 3, model chính ≠ điểm thấp nhất): `test_rv03_luat_hoa_model_chinh_khac_diem_thap_nhat` |
| RV04 | Quyền và kiểm reader của pipeline versioned | Claude đã sửa ở code; **cloud chưa chạy** | `scripts/pipeline/cli.py`: `consumers()` gồm `ai_optional_relations`; `present()` chỉ lấy bảng tùy chọn có trong schema của bản; `verify_consumers` (local và cloud) cấp quyền / thử đọc theo `present`, `allowed_versions` dùng danh sách đầy đủ. Test `test_ai_reader_gom_bang_du_bao_chi_khi_ban_co`; chạy thật `verify_consumers` local trên `4a117159…` (có dự báo) và `6f8654fb…` (trước B2b): đều đạt |
| RV05 | Not-null/finite/mức khoảng dự báo của gate | Claude đã sửa, chờ kiểm lại | `assert_rpt_forecast.sql`: quy tắc thứ tự cận bọc `coalesce(…, false)`; quy tắc mới 2b: cận / mức / tỷ lệ không NULL, hữu hạn (BETWEEN), `interval_level = 0.8` |
| RV06 | Đối chiếu score và selection_step | Claude đã sửa, chờ kiểm lại | Cùng file: `score = (mae_g + mae_cogs)/2` (sai số tương đối 1e-6), khóa backtest không trùng, đủ 8 chỉ số chat đọc ở 3 fold, `selection_step` của model chính khớp bước luật tính lại (CTE `step`), ứng viên khác không có `selection_step` |

**Bằng chứng chung sau sửa (Claude, 2026-10-15; không gọi LLM thật, không chạy cloud, không full `dbt build` mới):**
- `scripts/review/review_ai_forecast_20261015.py`: exit 0; CONTROL `ok`, R01–R07 đều `answer_validation_failed` với lỗi đúng loại.
- `scripts/review/review_forecast_gate_20261015.py`: exit 0; CONTROL đạt, Q01–Q04 bị gate từ chối; danh sách thiếu quyền forecast của pipeline rỗng.
- `apps/retail_app/tests/test_ai_forecast.py`: 71 passed (R01–R11 sai phải chặn, 7 ca đúng phải qua, follow-up đổi kỳ, ngoài kỳ, luật hòa; 11 cách viết kỳ và 7 ca trọn luồng theo cách viết, gồm quý / nửa năm). Cùng lượt `tests/test_ai_chat.py`: 68 passed (bỏ 1 test cần PostgreSQL).
- `tests/test_ai_chat.py` (bỏ 1 test cần PostgreSQL): không hồi quy; `scripts/pipeline/tests` + `scripts/forecast/tests`: 22 passed.
- Chưa chạy: PostgreSQL (Docker tắt), Databricks, live LLM (bộ G* ở `ai_live_eval.py --set g` mới kiểm rubric 12/12).

Ưu tiên RV01–RV03 trước khi nghiệm thu chat; RV05–RV06 trước bản forecast tiếp theo; RV04 trước nghiệm thu cloud. Không đổi quyết định nghiệp vụ để xử lý những lỗi kỹ thuật này.

Prompt giao cho phiên Claude hiện tại:

```text
/retail-ai-explain Phối hợp với Codex theo docs/review_codex_ai_gd2_20261015.md.
Đọc sổ quyết định docs/ke_hoach_ai_gd2.md §2 trước; tiếp tục bảo vệ các thay đổi đang làm.
Sửa RV01–RV03 trước, dùng các ca tái hiện trong scripts/review/ làm điểm xuất phát,
thêm test đúng/sai cho các biến thể ngôn ngữ và giữ hồi quy chat cũ.
Sau đó xử lý RV04–RV06 ở pipeline/gate theo phạm vi bước đang làm.
Không đổi target, thước chọn, ứng viên, ngưỡng hòa; không gọi Kaggle hoặc tự deploy.
Ghi file đã sửa, lệnh và kết quả thật vào bảng phối hợp để Codex kiểm lại.
Không ghi mock PASS thành live LLM PASS, hoặc kiểm code cấp quyền thành cloud PASS.
```

## 7. Codex kiểm lại sau sửa — 2026-10-15

### 7.1. Kết quả trực tiếp

- Chạy lại `review_ai_forecast_20261015.py`: exit 0. CONTROL đạt; R01–R07 đều `answer_validation_failed`.
- Chạy lại `review_forecast_gate_20261015.py`: exit 0. CONTROL đạt; Q01–Q04 bị chặn; danh sách thiếu bảng forecast trong `consumers()` rỗng. SQL được thực thi trên DuckDB trong RAM với bản sao dữ liệu local, không phải full dbt build.
- Bộ hồi quy dưới đây: **334 passed, 90 deselected, 78,34 giây**. `-k 'not pg'` bỏ các ca PostgreSQL; không tính chúng là đạt.
- Bản sửa mới có `consumers → present → reader_grants/verify_consumers`; test pipeline kiểm bảng optional ở cả bản có và chưa có forecast. Chưa chạy reader thật trên Databricks.
- `rereview_ai_forecast_20261015.py`: exit 1 do **4 ca sai còn lọt/lỗi**, 2 đối chứng đúng đạt. Đây là provider giả trả lời có chủ đích để kiểm validator; không kết luận tần suất LLM thật mắc lỗi.
- Hash `evidence.py`: `14bd595a61f12646eb7e8ffacaa562e7f54afd2f0d8968b3de69cf50809aaa45`; SQL gate: `513773918c1071a751ee9b7023232679b826c5275d4cd90d578051eda906e010`. JSON mới: `warehouse/reviews/ai_gd2_20261015/rereview_adversarial.json`.

```powershell
.venv/Scripts/python.exe -m pytest apps/retail_app/tests/test_ai_forecast.py apps/retail_app/tests/test_ai_chat.py apps/retail_app/tests/test_ai_tools.py apps/retail_app/tests/test_ai_tools_ps123.py apps/retail_app/tests/test_releases.py scripts/forecast/tests scripts/pipeline/tests -k 'not pg' -q --disable-warnings --tb=short
.venv/Scripts/python.exe scripts/review/rereview_ai_forecast_20261015.py
```

Trạng thái Codex hiện hành (thay cho trạng thái chờ ở §6):

| ID | Kết luận sau kiểm lại |
|---|---|
| RV01 | Ca cũ đã chặn; còn sai nghĩa tổng quý (RV07) và exception parser mới (RV09) |
| RV02 | Đổi chéo G/COGS đã chặn; phần tỷ lệ còn thiếu (RV08) |
| RV03 | Ca xếp hạng cũ và hồi quy đạt; chưa xác nhận live LLM |
| RV04 | Đã bổ sung code và test local; nghiệm thu cloud còn mở |
| RV05 | Hai ca dữ liệu sai ban đầu bị chặn |
| RV06 | Hai ca score/lý do sai ban đầu bị chặn; test forecast/pipeline đạt |

### RV07 — P1: số một tháng vẫn được gọi thành tổng quý

**Vị trí:** `apps/retail_app/ai_explain/evidence.py:627–638`, `:685–694`.

`_period_match` chỉ kiểm tháng/ngày nằm trong khoảng quý. Không kiểm câu trả lời đang nói một phần hay toàn bộ khoảng đó. Ca N03 hỏi **tổng doanh thu quý 3/2023**, tool lấy tháng 8/2023, câu trả lời gọi số tháng đó là **tổng quý 3/2023**: `run_turn` vẫn trả `ok`. Nhãn tháng app tự thêm không ngăn câu văn sai.

**Sửa:** ràng buộc kỳ và phép tổng hợp của từng claim với nội dung câu. Nếu tool chưa hỗ trợ tổng quý thì trả trạng thái phù hợp hoặc trình bày rõ từng tháng; không chấp nhận một số tháng mang nhãn tổng quý. Muốn hỗ trợ tổng khoảng thì query/tool phải tính và trả metadata phạm vi, không để LLM tự cộng.

**Nghiệm thu:** N03 bị chặn; C02 nói rõ "riêng tháng 8" vẫn được dẫn. Thêm nửa năm và khoảng nhiều tháng để kiểm cùng nguyên tắc. Không bắt mọi câu hỏi quý phải có tool mới chỉ để sửa validator.

### RV08 — P1: chưa ràng buộc tỷ lệ COGS/G với đúng loại số

**Vị trí:** `apps/retail_app/ai_explain/evidence.py:116–120`, `:361–368`, `:877–879`.

`_said_metric` cố ý trả None khi gặp COGS/G; `METRIC_FAMILY` chưa có `cogs_ratio`. Do đó N01 gọi `g_forecast` là tỷ lệ COGS/G và N02 gọi `cogs_ratio` là doanh thu G đều trả `ok`. Đây là hai chiều sai đơn vị, không phải vấn đề làm tròn.

**Sửa:** biểu diễn tỷ lệ như loại chỉ tiêu riêng và kiểm theo từng claim/vế câu. Cần phân biệt G, COGS, tỷ lệ COGS/G; không bỏ kiểm chỉ vì câu có cả chữ G lẫn COGS.

**Nghiệm thu:** N01/N02 bị chặn; C01 dẫn tỷ lệ đúng và test hiện có nêu cả ba chỉ tiêu trong một câu vẫn đạt.

### RV09 — P2: quý không hợp lệ làm exception thoát khỏi service

**Vị trí:** `apps/retail_app/ai_explain/evidence.py:604–605`, `:685`; `apps/retail_app/ai_explain/service.py:281–282`.

Parser nhận mọi chữ số làm quý rồi tạo `datetime.date` trực tiếp. N04 với "quý 5/2023" đi qua tool tháng hợp lệ nhưng `run_turn` ném `ValueError: month must be in 1..12`, không trả kết quả có kiểm soát. `forecast_question_errors` được gọi ngoài `_safe_validate`; parser còn được gọi ngay cả khi không có claim forecast.

**Sửa:** kiểm miền quý/năm/ngày trước khi tạo date và trả thông tin kỳ không hợp lệ để yêu cầu làm rõ. Lỗi nhập liệu không được làm crash, cũng không được bỏ kỳ sai rồi dùng số kỳ khác.

**Nghiệm thu:** quý 0/5, năm 0000 và ngày/tháng không hợp lệ trả trạng thái có kiểm soát; quý 1–4 hợp lệ vẫn chạy. Kiểm cả câu có forecast lẫn câu không có forecast.

### 7.2. Bàn giao lượt tiếp theo

Codex chỉ thêm script tái hiện và cập nhật tài liệu; không sửa source Claude phụ trách. Không retrain, publish, đổi registry, gọi Kaggle, LLM thật hay Databricks. Chưa chạy browser/UI, PostgreSQL hoặc full dbt build ở lượt kiểm lại.

```text
/retail-ai-explain Đọc docs/review_codex_ai_gd2_20261015.md §7.
Sửa RV07–RV09, giữ nguyên sổ quyết định và các test đã đạt.
Chạy scripts/review/rereview_ai_forecast_20261015.py cùng hai script review cũ;
thêm test đúng/sai theo tiêu chí nghiệm thu rồi cập nhật bằng chứng để Codex kiểm lại.
Không đổi tiêu chí của script để biến câu sai thành đạt; không tự deploy hoặc gọi Kaggle.
```

### 7.3. Claude sửa RV07–RV09 — 2026-10-15 (chờ Codex kiểm lại)

| ID | Sửa gì | File | Test thêm |
|---|---|---|---|
| RV07 | Câu hỏi về một **khoảng** (quý, 6 tháng / nửa đầu, cuối năm, "từ tháng a đến tháng b") được đọc thành `('range', đầu, cuối, nhãn)`. Số của một tháng / ngày trong khoảng chỉ được dẫn khi CHÍNH câu đó nêu đúng tháng / ngày của số (vd. "riêng tháng 8/2023") và không có chữ tổng hợp ("tổng", "cả quý", "cả nửa", "cộng lại"...). Số cả năm hay tháng ngoài khoảng vẫn bị chặn như trước. Không thêm tool tổng khoảng | `evidence.py`: `question_periods`, `_names_period`, `_AGG_WORD`, nhánh RV07 trong `forecast_question_errors` (nhận thêm `answer`) | `test_rv07_so_mot_thang_khong_thanh_tong_khoang` (8 ca: N03, C02, "cả quý", nửa năm sai / đúng, tháng 3–5 sai / đúng / ngoài khoảng). Ca cũ `test_bien_the_ky_tron_luong[quý 3/2023, tháng 8]` đổi kỳ vọng thành bị chặn, vì câu mẫu không nêu tháng nào |
| RV08 | "Tỷ lệ COGS/G", "COGS/G", "giá vốn trên doanh thu" là chỉ tiêu riêng `COGS/G` ở từng vế câu (`_RATIO_WORD`, bỏ chữ COGS và G bên trong rồi mới đếm chỉ tiêu); `METRIC_FAMILY['cogs_ratio'] = 'COGS/G'` | `evidence.py`: `_RATIO_WORD`, `_said_metric`, `METRIC_FAMILY` | `test_rv08_ty_le_cogs_g_la_chi_tieu_rieng` (C01, N01, N02, "giá vốn trên doanh thu" đúng / sai). Câu nêu cả G, COGS, tỷ lệ trong một câu vẫn đạt (`test_rv_cau_dung_van_qua`) |
| RV09 | Kiểm miền trước khi tạo ngày: quý 1–4, tháng 1–12, ngày có thật, năm 1900–2100; sai thì `('invalid', đoạn chữ)`. Câu trả lời có số (bất kỳ tool nào) cho câu hỏi có kỳ không hợp lệ bị chặn, nhắc trả `needs_clarification`; không dùng số kỳ khác. `forecast_question_errors` gọi qua `_safe_forecast_errors` (như `_safe_validate`), parser không ném lỗi với mọi chuỗi | `evidence.py`: `_day`, `question_periods`, `_spec_label`; `service.py`: `_safe_forecast_errors` | `test_rv09_ky_khong_hop_le_khong_crash_khong_dung_so_ky_khac` (quý 5, quý 0, năm 0000, 31/2/2023, tháng 13; cả câu dự báo, câu hỏi lại và câu dùng tool số thực tế), `test_rv09_quy_hop_le_van_chay` (quý 1–4), `test_rv09_doc_ky_khong_bao_gio_nem_loi` |

**Lệnh và kết quả thật** (PowerShell / Git Bash từ root, `.venv`, local DuckDB, provider giả; không gọi LLM thật, không cloud, không PostgreSQL):
- Lệnh hồi quy ở §7.1: **364 passed, 90 deselected** (Codex lần trước: 334; thêm 30 test mới, không test cũ nào bị bỏ).
- `scripts/review/rereview_ai_forecast_20261015.py`: **exit 0**. C01, C02 `ok`; N01, N02 chặn vì sai chỉ tiêu (`COGS/G` ≠ `G`); N03 chặn vì số 08/2023 bị gọi là tổng quý; N04 chặn vì "quý 5/2023 (không hợp lệ)", không còn exception.
- `scripts/review/review_ai_forecast_20261015.py`: **exit 0** (CONTROL `ok`, R01–R07 chặn). `scripts/review/review_forecast_gate_20261015.py`: **exit 0**.
- Hash sau sửa: `evidence.py` `4c4f6a7f7d27916dfdfbd50a3d4d07828ba8144271f7d2b6f37fcc014b2907e0`; `service.py` `8d0fadfc53ea1af29093b6438f2af4c8a5801c80befc891e1800f07de38fe5d1`; SQL gate không đổi (`513773918c10…`).
- Không đổi tiêu chí trong ba script review của Codex. Không đổi target, thước chọn, ứng viên, ngưỡng hòa.

**Giới hạn còn lại để Codex xét:** ràng buộc dựa trên kỳ và chữ trong câu do app đọc; cách nói kỳ chưa có trong parser (vd. "dịp Tết", "mùa hè năm sau") thì không ràng buộc kỳ, chỉ còn các kiểm khác. Chưa chạy live LLM (G*), PostgreSQL, Databricks.

### 7.4. Codex kiểm lại sau sửa RV07–RV09

**Kết quả trực tiếp:** `review_ai_forecast_20261015.py` exit 0 (CONTROL đạt, R01–R07 chặn); `review_forecast_gate_20261015.py` exit 0 (CONTROL đạt, Q01–Q04 chặn, đủ hai bảng forecast trong danh sách AI reader); bộ hồi quy §7.1 đạt **364 passed / 90 deselected trong 33,86 giây**. Trong `rereview_ai_forecast_20261015.py`, hai đối chứng C01/C02 đạt và N01–N04 bị chặn, xác nhận sửa RV07–RV09 ở các câu `status=ok`. Codex thêm N05 và script trả **exit 1** do lỗi mới dưới đây. JSON kết quả ở `warehouse/reviews/ai_gd2_20261015/rereview_adversarial.json`; source `evidence.py` có SHA-256 `4c4f6a7f7d27916dfdfbd50a3d4d07828ba8144271f7d2b6f37fcc014b2907e0`.

**RV10 — P2: câu hỏi lại vẫn kèm số của kỳ khác khi kỳ nhập sai.** Vị trí: `apps/retail_app/ai_explain/service.py`, nhánh `_check_final` cho các trạng thái khác `ok` có `claims`; nhánh này gọi `_safe_validate` nhưng bỏ qua `_safe_forecast_errors`. `evidence.py:736` chỉ chặn kỳ sai khi validator được gọi. N05 hỏi `Dự báo doanh thu quý 5/2023?`; provider giả trả `needs_clarification` cùng câu “Trong lúc chờ, dự báo G tháng 8/2023 là {c1}” dẫn `T1.rows[0].g_forecast`. Service chấp nhận, render **74.151.832 VND** và không báo lỗi. Đây là số đúng của tháng 8 nhưng không phải câu trả lời cho kỳ người dùng nhập; mâu thuẫn với yêu cầu RV09 “không dùng số kỳ khác”.

**Hướng sửa:** áp dụng kiểm kỳ không hợp lệ cho mọi trạng thái có claim số, hoặc không cho claim số ở `needs_clarification` khi kỳ người dùng chưa xác định. Giữ khả năng hỏi lại không có claim. **Nghiệm thu:** N05 bị từ chối; N04 vẫn bị chặn; câu hỏi lại không dẫn số vẫn đạt; không hồi quy các trạng thái từ chối hợp lệ khác. Chạy lại cả ba script review và bộ hồi quy §7.1.

```text
/retail-ai-explain Đọc docs/review_codex_ai_gd2_20261015.md §7.4. Sửa RV10 ở nhánh
needs_clarification có claim số; không cho dùng số kỳ khác khi câu hỏi chứa kỳ không hợp lệ.
Chạy scripts/review/rereview_ai_forecast_20261015.py, hai script review cũ và test hồi quy;
ghi kết quả để Codex kiểm lại. Không đổi điều kiện sai/đúng của script tái hiện.
```

## 8. Codex kiểm checkout có B3b — 2026-10-15

**Phạm vi hiện hành:** bản local đang phục vụ `fc14b8a2f5a24ff99a434d7c`; trang Dự báo đọc `rpt_forecast_daily`, `rpt_forecast_backtest`, `rpt_forecast_actual`. Đọc code, registry và các bảng có thật trong DuckDB; không dựa riêng vào lời báo hay số test của Claude.

**Kết quả chạy lại:**

- `review_ai_forecast_20261015.py`: exit 0; CONTROL đạt, R01–R07 chặn.
- `review_forecast_gate_20261015.py`: exit 0; CONTROL đạt, Q01–Q04 chặn. Đây là gate cho **hai bảng dự báo**, chưa thay thế kiểm SQL riêng của `rpt_forecast_actual`.
- `rereview_ai_forecast_20261015.py`: exit 1; C01/C02 đạt, N01–N04 chặn, **N05 vẫn lọt** như RV10. Trạng thái `needs_clarification` hiển thị số G tháng 8/2023 cho câu hỏi quý 5/2023. `service._check_final` hiện vẫn chỉ gọi `_safe_forecast_errors` ở nhánh `ok`.
- Test chat, tool, release, trang Dự báo, forecast và pipeline: **374 passed, 90 deselected trong 77,47 giây** với `-k 'not pg'`. `test_du_bao.py` nằm trong bộ này và kiểm AppTest cùng tổng tháng qua truy vấn DuckDB độc lập. Local DuckDB không kiểm được quyền của app reader trên Databricks.

```powershell
.venv/Scripts/python.exe -m pytest apps/retail_app/tests/test_ai_forecast.py apps/retail_app/tests/test_ai_chat.py apps/retail_app/tests/test_ai_tools.py apps/retail_app/tests/test_ai_tools_ps123.py apps/retail_app/tests/test_releases.py apps/retail_app/tests/test_du_bao.py scripts/forecast/tests scripts/pipeline/tests -k 'not pg' -q --disable-warnings --tb=short
.venv/Scripts/python.exe scripts/review/review_forecast_page_grants_20261015.py
```

### RV11 — P1 trước cloud: app reader thiếu quyền trên cả ba bảng trang Dự báo

**Bằng chứng:** `apps/retail_app/dwh/forecast_queries.py` có `SOURCE` gồm ba bảng `reporting.rpt_forecast_daily`, `reporting.rpt_forecast_backtest`, `reporting.rpt_forecast_actual`; `views/du_bao.py` đọc cả ba. Cả ba bảng có trong schema của release local đang phục vụ. Nhưng `retail_dbt/dbt_project.yml` chỉ cho **AI reader** hai bảng dự báo trong `ai_optional_relations`, còn `app_read_relations` không có bảng nào trong ba bảng. `scripts/pipeline/cli.py:135–200` dùng `consumers()` rồi sinh GRANT/kiểm reader cho app theo danh sách app đó. Script đối chứng `review_forecast_page_grants_20261015.py` trả exit 1: `app_reader_missing` gồm cả ba bảng, `app_grant_statements_for_page` rỗng. JSON: `warehouse/reviews/ai_gd2_20261015/page_grants.json`.

**Ảnh hưởng:** trang local DuckDB chạy được vì không dùng Unity Catalog grant; trên đường Databricks versioned, app service principal chưa được pipeline cấp/thử SELECT cho ba bảng này. Đây là lỗi đường code trước cloud, **chưa phải bằng chứng đã lỗi trên deployment**. App public hiện vẫn ở chế độ cũ theo sổ quyết định §2.

**Hướng sửa và nghiệm thu:** thêm danh sách bảng app **tùy chọn** theo release, rồi dùng nó trong cấp quyền và thử đọc bằng chính app reader; cả `rpt_forecast_actual` phải được gồm vào. Bản trước B2b không có ba bảng vẫn phải rollback/đọc trang cũ được. `allowed_versions` phải chấp nhận quyền hợp lệ của các bản ready khác. Test sinh GRANT khi bảng có, không đòi khi bảng vắng, và kiểm app reader thật trên workspace khi có writer SP/đường cloud được chốt. Không đưa ba bảng vào danh sách bắt buộc cho mọi release.

**Trạng thái bàn giao:** RV10 và RV11 còn mở. Codex chỉ thêm script tái hiện và tài liệu; source AI/trang/pipeline đang do Claude xây. Chưa chạy live LLM, PostgreSQL, browser thật, Databricks reader, hoặc full dbt build mới trong lượt này.

```text
/retail-ai-explain Đọc docs/review_codex_ai_gd2_20261015.md §8.
Sửa RV10 ở nhánh trả lời khác ok có claim số và RV11 ở app reader pipeline cho ba bảng Dự báo tùy chọn.
Giữ rollback bản trước B2b. Chạy ba script AI review, script review_forecast_page_grants_20261015.py
và bộ hồi quy §8; ghi bằng chứng để Codex kiểm lại. Không tự deploy hoặc đổi luật chọn model.
```

### 8.1. Claude sửa RV10 — 2026-10-15 (chờ Codex kiểm lại)

Phạm vi: chỉ RV10 (§7.4). **RV11 (§8) chưa sửa**, chờ PM giao. Không đổi tiêu chí trong các script của `scripts/review/`.

| Mục | Nội dung |
|---|---|
| Sửa | `ai_explain/evidence.py`: tách kiểm "kỳ không hợp lệ" thành hàm `invalid_period_errors(question, values)`; `forecast_question_errors` gọi lại hàm này, nên hành vi ở status `ok` giữ nguyên. `ai_explain/service.py`: nhánh `_check_final` cho status khác `ok` có `claims` (hỏi lại, unsupported, no_data) nay chạy thêm `invalid_period_errors`, bọc trong `_safe_invalid_period_errors` như `_safe_forecast_errors` |
| Cách chọn | Theo hướng 1 của §7.4: áp kiểm kỳ không hợp lệ cho **mọi** trạng thái có claim số. Các ràng buộc khác (kỳ lệch, model, thước xếp hạng, khoảng) vẫn chỉ áp cho `ok`, để không chặn các câu từ chối hợp lệ hiện có |
| Test mới | `tests/test_ai_forecast.py`, 11 test: 9 ca (3 kỳ sai × `needs_clarification` / `unsupported` / `no_data`) kèm số tháng 8/2023 đều thành `answer_validation_failed`; tool số thực tế (`R quý 5/2019?`) cũng bị chặn; đối chứng: hỏi lại không dẫn số vẫn `needs_clarification`, hỏi lại kỳ hợp lệ (quý 3/2023) dẫn số "riêng tháng 8/2023" vẫn đạt |
| Thử ngược | Tạm bỏ dòng gọi kiểm ở nhánh khác `ok`: 10/11 test RV10 trượt, chỉ ca đối chứng đạt. Đã khôi phục |

**Lệnh và kết quả** (local, provider giả; không phải live LLM):

```powershell
.venv/Scripts/python.exe scripts/review/review_ai_forecast_20261015.py           # exit 0
.venv/Scripts/python.exe scripts/review/review_forecast_gate_20261015.py         # exit 0
.venv/Scripts/python.exe scripts/review/rereview_ai_forecast_20261015.py         # exit 0: C01/C02 ok; N01–N05 chặn (N05 answer_validation_failed)
.venv/Scripts/python.exe scripts/review/review_forecast_page_grants_20261015.py  # exit 1: RV11 còn mở
.venv/Scripts/python.exe -m pytest <bộ hồi quy §8> -k 'not pg' -q --disable-warnings --tb=short   # 385 passed, 90 deselected (374 + 11 test RV10)
.venv/Scripts/python.exe -m pytest <bộ hồi quy §8> -q --disable-warnings --tb=short                # 475 passed (PostgreSQL Docker đang bật)
```

**Hash sau sửa:** `evidence.py` `c935f6f94dcf4c7a31913fe18e739714a772e4b1d517ed72b2b532a3cd6a60ac`; `service.py` `6a3dc8ce2624b672dc635d7172ef6afa3643c53f12282379d4325593ed486078`.
JSON của ba script AI review và `page_grants.json` trong `warehouse/reviews/ai_gd2_20261015/` đã được ghi lại bởi lần chạy này.

**Giới hạn:** sửa chỉ ở app, không đổi dữ liệu; bản đang phục vụ `fc14b8a2f5a24ff99a434d7c` dựng trước sửa này, nên `code_version` của bản khác code hiện tại cho tới lần chạy pipeline sau. Câu từ chối có claim của kỳ **hợp lệ** nhưng lệch kỳ được hỏi (vd. hỏi 2025, dẫn số 07/2024 trong `no_data`) chưa bị ràng buộc kỳ; RV10 không yêu cầu, ghi để Codex xét.

### 8.2. Claude sửa RV11 — 2026-10-15 (chờ Codex kiểm lại)

Không đổi tiêu chí trong `scripts/review/`. Không đưa ba bảng trang Dự báo vào danh sách bắt buộc `app_read_relations`.

| Mục | Nội dung |
|---|---|
| Danh sách bảng app tùy chọn | `retail_dbt/dbt_project.yml`: var mới `app_optional_relations` = `rpt_forecast_actual`, `rpt_forecast_backtest`, `rpt_forecast_daily` (= `forecast_queries.SOURCE`) |
| Pipeline | `scripts/pipeline/cli.py`: `consumers()` trả app = `app_read_relations + app_optional_relations`; `optional_relations()` = hợp của bảng tùy chọn AI và app, nên `present()` lọc cả hai. Nhánh local của `verify_consumers` sửa `set(app + present(ai, ...))` thành `set(present(app + ai, ...))`: trước sửa, thêm bảng tùy chọn vào app sẽ làm thử đọc bản trước B2b hỏng. Nhánh cloud dùng sẵn `present(full, ...)`, `reader_grants` và `allowed_versions(state, full)` cho kind APP |
| Macro (đường không qua pipeline) | `retail_dbt/macros/ai_readonly_grants.sql`: SP của app (`RETAIL_APP_DBX_PRINCIPAL`) và của bản web (`RETAIL_WEB_DBX_PRINCIPAL`) cấp thêm `var('app_optional_relations', [])`; `_dbx_grant_read` bỏ qua bảng chưa có. Build thường không có các bảng này nên không cấp gì |
| Test mới | `scripts/pipeline/tests/test_pipeline.py`: `test_app_reader_gom_ba_bang_trang_du_bao_chi_khi_ban_co` (danh sách = `forecast_queries.SOURCE`, không thuộc bắt buộc; có bảng thì sinh GRANT, vắng thì không; `allowed_versions` chấp nhận bảng tùy chọn của mọi bản ready) và `test_verify_consumers_local_moi_ban_ready` (chạy `verify_consumers` local trên cả bản trước B2b `6f8654fb…`, bản `4a117159…` và bản `fc14b8a2…`). `apps/retail_app/tests/test_du_bao.py`: `test_rv11_quyen_doc_ba_bang_trang_du_bao` (var khớp `forecast_queries.SOURCE`, macro cấp cho APP và WEB). Test RV04 cũ sửa kỳ vọng: không còn khẳng định "app không có bảng tùy chọn" |
| Thử ngược | Khôi phục dòng `set(app + present(ai, ...))`: `test_verify_consumers_local_moi_ban_ready` trượt với `Catalog Error: Table with name rpt_forecast_backtest does not exist` ở bản `6f8654fb…`. Đã khôi phục bản sửa |

**Lệnh và kết quả** (local):

```powershell
.venv/Scripts/python.exe scripts/review/review_forecast_page_grants_20261015.py  # exit 0: app_reader_missing = []; 3 câu GRANT cho ba bảng
.venv/Scripts/python.exe scripts/review/review_ai_forecast_20261015.py           # exit 0
.venv/Scripts/python.exe scripts/review/review_forecast_gate_20261015.py         # exit 0
.venv/Scripts/python.exe scripts/review/rereview_ai_forecast_20261015.py         # exit 0
.venv/Scripts/python.exe -m pytest <bộ hồi quy §8> -k 'not pg' -q --disable-warnings --tb=short   # 388 passed, 90 deselected
.venv/Scripts/python.exe -m pytest <bộ hồi quy §8> -q --disable-warnings --tb=short                # 478 passed (PostgreSQL Docker bật)
dbt parse (duckdb, không var forecast_path)                                                       # 217 node như trước
```

**Hash sau sửa:** `cli.py` `f04cf8928ff04dab80f27e20b786d651063ce5b1ba7356a94aa3c489b40d237f`; `dbt_project.yml` `7bdea583908a9d40a32b056f97324c73ec9e0499b09a938f191017af2856e85d`; `ai_readonly_grants.sql` `701cf36b80986f533e6e633dff3386ca7f8d91fd04eadb9d0d683b3a7aa75ef1`.

**Chưa chạy / giới hạn:**
- Đường cloud của `verify_consumers` (GRANT rồi thử đọc bằng chính app SP, `_check_dbx_identity`) chưa chạy: cần writer SP và pipeline Databricks, quyết định còn chờ PM (`ke_hoach_ai_gd2.md` §2). Nhánh Databricks của macro mới qua `dbt parse`, chưa render trên workspace.
- Pipeline chỉ cấp quyền và thử đọc cho hai danh tính APP và AI. SP của bản web public (`RETAIL_WEB_DBX_PRINCIPAL`) chỉ được macro cấp ở build không có `release_id`; khi chuyển bản public sang chế độ versioned cần xét thêm danh tính này. RV11 không yêu cầu.

## 9. Codex kiểm lại sau sửa RV10–RV11 — 2026-10-15

**Kết quả hiện hành:** release local `fc14b8a2f5a24ff99a434d7c`; Docker PostgreSQL healthy trên cổng 5433. Bộ hồi quy §8 chạy **478 passed / 0 failed trong 40,89 giây**, gồm test PostgreSQL. `dbt parse` với target DuckDB và PostgreSQL đều exit 0 khi đặt `PYTHONUTF8=1`; lần đầu không đặt UTF-8 bị lỗi giải mã cp1252 trên Windows, không phải lỗi SQL/dbt. Không chạy `dbt build` mới.

- `review_ai_forecast_20261015.py`: exit 0, R01–R07 chặn.
- `rereview_ai_forecast_20261015.py`: exit 0, C01/C02 đạt, N01–N05 chặn; riêng N05 `needs_clarification` có số của kỳ khác nay `answer_validation_failed`.
- `review_forecast_gate_20261015.py`: exit 0, CONTROL đạt, Q01–Q04 chặn; kiểm bản sao parquet trong RAM.
- `review_forecast_page_grants_20261015.py`: exit 0, `app_reader_missing=[]`; sinh đủ ba lệnh GRANT cho `rpt_forecast_actual`, `rpt_forecast_backtest`, `rpt_forecast_daily` ở release local. Code `present()` và test pipeline kiểm bản trước B2b vẫn được đọc. Chưa cấp/thử quyền thật trên workspace.
- `review_ai_nonok_period_20261015.py`: **exit 1** vì RV12 dưới đây. JSON ca mới ở `warehouse/reviews/ai_gd2_20261015/nonok_period.json`.

### RV12 — P1: câu `no_data` gán số dự báo kỳ khác thành kỳ người dùng hỏi

**Vị trí:** `apps/retail_app/ai_explain/service.py`, nhánh `_check_final` cho trạng thái khác `ok` có `claims` (khoảng dòng 300). Sau RV10, nhánh này chỉ gọi `invalid_period_errors` cho kỳ **không hợp lệ**; kỳ hợp lệ nhưng sai với claim vẫn chưa được so. Ca N06 hỏi “Dự báo doanh thu năm 2025?”; provider giả dùng tool `get_forecast` tháng 8/2023 rồi trả `no_data` với câu “Dự báo G năm 2025 là {c1}”. Service chấp nhận, render **74.151.832 VND**, lỗi rỗng. Nhãn app tự thêm `08/2023` bộc lộ mâu thuẫn nhưng câu văn sai vẫn hiện.

**Đối chứng:** cùng câu hỏi và cùng claim, đáp “Chưa có dự báo năm 2025. Riêng tháng 8/2023, dự báo G là {c1}” được chấp nhận; đó là cách trình bày một số tham khảo đúng kỳ nếu sản phẩm muốn cho phép.

**Hướng sửa:** với mọi trạng thái có claim số, kiểm kỳ mà từng vế câu đang gán cho claim theo metadata của dòng; số tham khảo kỳ khác chỉ được hiện khi câu ghi rõ kỳ thật của nó. Giữ trạng thái `no_data` cho năm 2025 và khả năng hỏi lại không dẫn số. Tránh áp toàn bộ luật “claim phải thuộc kỳ trong câu hỏi” của `ok` sang `no_data`, vì sẽ chặn cả đối chứng tham khảo đúng nhãn.

**Nghiệm thu:** script ca N06 exit 0 (đối chứng qua, N06 bị chặn); `rereview_ai_forecast_20261015.py` và ba script trước vẫn exit 0; bộ hồi quy §8 và test `no_data`/`unsupported` có dẫn số đúng kỳ vẫn đạt. Test trên provider giả kiểm validator, chưa đo hành vi live LLM.

```text
/retail-ai-explain Đọc docs/review_codex_ai_gd2_20261015.md §9. Sửa RV12:
trạng thái no_data có claim số không được gọi số 08/2023 thành dự báo năm 2025;
số tham khảo ghi rõ "riêng tháng 8/2023" vẫn được phép.
Chạy scripts/review/review_ai_nonok_period_20261015.py, bốn script review cũ,
test hồi quy §8 và ghi kết quả để Codex kiểm lại. Giữ nguyên quyết định dự báo và quyền đã sửa.
```

### 9.1. Claude sửa RV12 — 2026-10-15 (chờ Codex kiểm lại)

Không đổi tiêu chí trong `scripts/review/`. Không áp luật "claim phải thuộc kỳ trong câu hỏi" của `ok` sang trạng thái khác.

| Mục | Nội dung |
|---|---|
| Luật mới | `apps/retail_app/ai_explain/evidence.py`: `reference_period_errors(question, values, results, answer)`. Claim số dự báo (`get_forecast`, trường `FORECAST_FIELDS`, có dòng) mà kỳ của dòng **không** khớp kỳ nào trong câu hỏi thì vế câu chứa chỗ đặt phải tự ghi kỳ, và mọi kỳ ghi ở đó phải khớp kỳ thật của dòng. Vế câu = phần giữa dấu `,` `:` trong một câu; vế không ghi kỳ thì lấy kỳ ở vế gần nhất phía trước trong cùng câu. Không ghi kỳ, hoặc ghi kỳ được hỏi ("năm 2025", "tháng 8 năm 2025"), thì chặn. Claim đúng kỳ được hỏi và claim `derived.*` không thuộc luật này |
| Nối vào service | `service._safe_invalid_period_errors` gọi thêm `reference_period_errors` cho nhánh trạng thái khác `ok` có claim (cùng chỗ RV10); lỗi bất ngờ vẫn thành lỗi kiểm, không crash |
| Test mới | `apps/retail_app/tests/test_ai_forecast.py`: `test_rv12_so_ky_khac_gan_cho_ky_duoc_hoi_bi_chan` (3 câu × 3 trạng thái: N06, ghi "tháng 8 năm 2025", không ghi kỳ), `test_rv12_so_tham_khao_ghi_dung_ky_van_dat` (đối chứng của Codex và hai cách viết đúng kỳ, gồm dấu `;` và `:`), `test_rv12_so_dung_ky_duoc_hoi_khong_doi` |
| Thử ngược | Thay `service.reference_period_errors` bằng hàm trả rỗng rồi chạy script RV12: N06 `finding: true`, exit 1. Sau đó chạy lại script thật để file `nonok_period.json` giữ kết quả sau sửa |

**Lệnh và kết quả** (local, release `fc14b8a2f5a24ff99a434d7c`, PostgreSQL Docker bật):

```powershell
.venv/Scripts/python.exe scripts/review/review_ai_nonok_period_20261015.py      # exit 0: CONTROL hiện số, N06 answer_validation_failed
.venv/Scripts/python.exe scripts/review/review_ai_forecast_20261015.py           # exit 0
.venv/Scripts/python.exe scripts/review/rereview_ai_forecast_20261015.py         # exit 0
.venv/Scripts/python.exe scripts/review/review_forecast_gate_20261015.py         # exit 0
.venv/Scripts/python.exe scripts/review/review_forecast_page_grants_20261015.py  # exit 0
.venv/Scripts/python.exe -m pytest <bộ hồi quy §8, gồm test_du_bao.py> -q --disable-warnings --tb=short   # 494 passed
```

494 = 478 trước đây + 13 test RV12 + 3 test mới ở `scripts/forecast/tests` (bên dưới).

**Thay đổi khác trong cùng lượt, ngoài RV12** (để Codex biết khi so diff):
- `scripts/forecast/core.py`: hàm `tet_dates()` gọi `holidays.country_holidays(..., language='en_US')`. Lý do: không truyền `language` thì tên ngày lễ đi theo biến `LANG`; image Airflow có `LANG=C.UTF-8` nên trả "Tết Nguyên Đán", không tìm thấy "Lunar New Year", và stage dự báo trong Docker dừng với `ValueError: Ngày Tết từ thư viện holidays lệch...` (lần chạy `b3c-docker-01`). Trên Windows `LANG=en_US.UTF-8` nên kết quả cũ không đổi. Test `test_tet_dates_do_not_depend_on_locale` (3 giá trị `LANG`). Ứng viên, tham số và luật chọn không đổi; `model_version` đổi vì hash code dự báo đổi.
- `scripts/ops/ai_live_eval.py`: bộ câu GM cho B3c, ghi mã băm / phiên bản / bản dữ liệu mỗi lượt, bộ dự báo từ chối chạy ở chế độ cũ. Kết quả live: [ai_eval_b3c_du_bao.md](ai_eval_b3c_du_bao.md). Lần live chạy **trước** sửa RV12 (mã băm code `3c18e80969f6d5ef`).

**Hash sau sửa:** `evidence.py` `b6c55767ba43c59b98461a18168d6e6b9eb13c87e8db026ffd31ae841cfc3568`; `service.py` `5cce59d5c068058560aa2dee130aaf222874dd261a23e51e2b4fbe20e4b588ed`; `core.py` `ee8c5c886f610a82e820c6bfded598298ad24121a64153a2141dda2fd6e5a618`.

**Lỗi app thấy qua eval live, chưa sửa (chờ PM):** `evidence._fmt` không xử lý ô kiểu ngày (`derived.primary.trained_through`) nên in ".,2f" vào câu trả lời (GM13, [ai_eval_b3c_du_bao.md](ai_eval_b3c_du_bao.md) §3.2); validate không chặn được vì claim trỏ đúng một ô có giá trị.

**Chưa chạy / giới hạn:** test dùng provider giả, chưa đo live LLM sau sửa. Luật chỉ áp cho số dự báo; số thực tế của tool PS dẫn kèm câu hỏi lại vẫn theo luật cũ. Đề xuất sửa từ eval B3c (khoảng tháng "từ 12/2022 đến 2/2023", "cùng tháng năm 2022", luật câu độ chính xác) chưa làm, chờ PM.

### 9.2. Claude sửa 7 đề xuất từ eval live B3c — 2026-10-16 (chờ Codex kiểm lại)

PM duyệt sửa các đề xuất ở [ai_eval_b3c_du_bao.md](ai_eval_b3c_du_bao.md) §3.2; bảng sửa đầy đủ ở §4 của file đó. Không đổi tiêu chí trong `scripts/review/`.
Các chỗ **nới** bước kiểm (Codex nên soi kỹ xem có mở lỗ cho câu sai không):
- câu so sánh tiếp nối được dẫn số dự báo của kỳ lượt trước (`context_periods`, chỉ lấy từ tham số tool đã chạy, chỉ khi câu hỏi có "so với / so sánh / cùng tháng / cùng kỳ / chênh" và vế câu ghi đúng kỳ của số);
- luật "hỏi thực tế mà dẫn dự báo" chỉ chặn số dự báo của chính kỳ được hỏi (số kỳ khác do luật kỳ xử lý);
- câu "{a} thấp hơn {b}" giữa hai số cùng thước backtest (app kiểm chiều; thước khác nhau hoặc sai chiều thì chặn);
- "dẫn đầu / đứng đầu" với `lowest_score` / `lowest_mape_g_thang`; câu mô tả luật chọn không có chỗ đặt;
- `get_forecast` chỉ hỏi G với model có hai cách COGS: không hỏi lại (tool kiểm G trùng trên kỳ hỏi).
Các chỗ **siết**: dự báo chỉ tiêu chưa có (số đơn, R...) không được `ok`; "{ô ngày} ngày" bị chặn; tên họ model có nhiều biến thể thì hỏi lại.

Lệnh: `.venv/Scripts/python.exe -m pytest <bộ hồi quy §8> -q --disable-warnings --tb=short` → 510 passed (PostgreSQL bật); năm script review exit 0.
Test `test_ung_vien_khac_khong_thay_the` đổi kỳ vọng: hỏi G với `sarimax_full` không còn `needs_clarification` (hỏi COGS thì vẫn có).

### 9.3. B6 `show_chart` — 2026-10-16 (chờ Codex kiểm)

Đường code mới, Codex nên soi: `apps/retail_app/ai_explain/charts.py` (kiểm lời gọi, dựng dữ liệu, Altair), `service.run_turn` (nhánh
`show_chart` trước giới hạn `MAX_TOOL_CALLS`; lời gọi biểu đồ không vào `turn.calls` / `turn.results`), `service.chat_schemas()`,
`views/ai_explain.py` (vẽ khi `status == 'ok'`). Bất biến muốn giữ: biểu đồ không có số nào ngoài `results[ref].rows` của chính lượt;
ref của lượt trước / ref không ok / tool một dòng / cột không phải số / hai cột khác đơn vị / tham số thừa đều bị từ chối.

Lệnh: `.venv/Scripts/python.exe -m pytest <bộ hồi quy §8> apps/retail_app/tests/test_ai_charts.py -q --disable-warnings --tb=short` → 529 passed;
năm script review exit 0. Prompt rút gọn (`b6-2026-10-16b`) để `test_tran_token_cung_ca_phien_khong_vuot_200k` vẫn đạt (199.629 / 200.000);
`test_can_tren_prompt_ghi_lai_moi_lan_goi` nay so với `service.chat_schemas()` (có schema biểu đồ).

**Image Airflow Docker lại cũ** so với code (build trước RV12, sửa B3c và B6): build lại trước khi chạy pipeline `--target databricks`.
Bổ sung 2026-10-16: `evidence._NOT_AGG` bỏ "doanh thu gộp" / "bản gộp" trước khi tìm chữ chỉ tổng của luật RV07 (live GM10 sau khi khoảng tháng
vắt qua năm được nhận); "gộp hai tháng ... là {c1}" vẫn bị chặn (test trong `test_b3c_gm10_khoang_thang_vat_qua_nam`). 529 passed; năm script exit 0.

### 9.4. Claude sửa RV12 lượt 2 — 2026-10-16 (chờ Codex kiểm lại)

**Vì sao RV12 còn mở sau §9.1.** Ca N06 trong script đã bị chặn (`review_ai_nonok_period_20261015.py` exit 0). Nhưng PM ghi RV12 còn mở,
nên Claude soạn 15 biến thể sát N06 và 6 câu tham khảo ghi đúng kỳ, chốt danh sách trước khi sửa (provider giả). Chạy trên code §9.3, **10/15
ca sai vẫn hiện**. Khi tự review bản sửa, Claude thêm 2 ca câu miễn trừ (bảng dưới), cả hai cũng lọt. 6 câu đúng, gồm đối chứng của Codex, đều hiện. Các ca đều hỏi "Dự báo doanh thu năm 2025?", trừ ca ghi khác.

| Nhóm lọt | Ví dụ | Vì sao lọt |
|---|---|---|
| Tháng không ghi năm | "Dự báo G tháng 8 là {c1}" (số 08/2023; cả khi hỏi "tháng 8/2025") | `_period_match` coi năm trống là khớp mọi năm |
| Gán lại ở vế / câu sau | "Theo tháng 8/2023, dự báo G là {c1}, áp dụng cho năm 2025"; "… Có thể coi đây là dự báo năm 2025" | luật chỉ xét vế chứa số và các vế trước nó |
| Số derived của cả vùng | `derived.horizon_total`, `derived.highest_month` gọi là "năm 2025" | `_claim_period` trả `None`, nên claim bị bỏ qua |
| Số thực tế | G năm 2022 gọi là "dự báo G năm 2025", ở `no_data` và cả **`ok`** | luật lượt 1 chỉ xét số dự báo; ở `ok`, app chỉ gắn nhãn "(G, 2022)" cạnh câu sai |
| Câu miễn trừ làm chữ phủ định (thêm sau, khi tự review bản sửa) | "Dự báo G tháng 8/2023 là {c1}, áp dụng cho năm 2025 (không phải số thực tế)"; "Đây là dự báo năm 2025 chứ không phải số thực tế" | bản sửa đầu miễn mọi vế có chữ "không". Tool dự báo bảo mô hình nhắc "không phải số thực tế", nên câu miễn trừ này xuất hiện thường xuyên. Hai ca được thêm vào bộ thử **trước** khi sửa và chạy lại: cả hai lọt (`claude_rv12b_probe_truoc_sua_b13_b14.json`) |

Cùng lớp lỗi, ngoài dự báo: ở `ok`, "R năm 2019 là {c1}" với số của 2018 vẫn hiện, kèm nhãn "(R, 2018)". Theo hướng sửa ở §9 ("mọi trạng
thái có claim số"), lượt này sửa cả trường hợp đó.

**Sửa.** Chỉ sửa bước kiểm (`apps/retail_app/ai_explain/evidence.py`, `service.py`). Prompt giữ nguyên, vì chỉ còn dư 371 token.

| Luật | Nội dung |
|---|---|
| Kỳ gán cho từng chỗ đặt (`_positions`, `_said`) | Đọc kỳ ở phần dẫn ngay trước chỗ đặt. Không có thì đọc phần đuôi ngay sau (tới chỗ đặt kế tiếp hoặc tới chữ nối "và / còn / nhưng / trong khi"). Vẫn không có thì đọc đầu vế, rồi các vế phía trước. Lượt 1 đọc cả vế, nên một vế có hai số ("năm 2019 là {c1} và năm 2020 là {c2}") bị coi là sai |
| Số tham khảo kỳ khác, status khác `ok` (`reference_period_errors`) | Ít nhất một kỳ ghi phải khớp kỳ thật của số, và không kỳ ghi nào là kỳ được hỏi. Tháng không ghi năm lấy năm ghi trước đó trong câu; không có năm thì không đủ khi câu hỏi nêu năm khác. Luật áp cho cả số derived: tổng cả vùng cần chữ "vùng dự báo / kỳ dự báo / cả vùng…", mọi kỳ ghi kèm phải nằm trong 2023-01-01 → 2024-07-01; tháng cao / thấp nhất phải ghi đúng tháng. Luật cũng áp cho số thực tế có `year` |
| Vế nhắc kỳ được hỏi (`_asked_mention_errors`) | Khi câu trả lời có số tham khảo, vế nào nhắc kỳ được hỏi phải **nói kỳ đó không có số** (`_NEG`, danh sách dương): "chưa…", "vượt", "hết vùng", "nằm ngoài", "ngoài kỳ / vùng / phạm vi", "không có / hỗ trợ / thể", "không … được", "không phải (số / dự báo / mức) (của) (riêng) năm / tháng / quý / ngày / kỳ…". "Không phải số thực tế / nguyên nhân" **không** tính. Miễn hai trường hợp: vế có số của chính kỳ được hỏi, và câu hỏi lại kết thúc bằng "?" không có số |
| Mọi trạng thái, cả `ok` (`stated_period_errors`) | Kỳ câu ghi ngay ở chỗ đặt phải chứa kỳ của số theo dòng; năm chứa các tháng của nó |

Kỳ của từng loại ô (`_value_gots`):
- Mặc định là `year` / `month` của dòng.
- `r_prior_year`, `r_same_month_prior_year` thuộc năm trước.
- Ô thay đổi (`delta_*`, `yoy_rate`, `contribution_to_delta`, `share_shift_pp`) thuộc cả hai năm.
- Không kiểm: `r_12m_before/after`, `*_start` / `*_end`, ô năm và số đếm.

**Chỗ nới, Codex nên soi:**
- Danh sách chữ phủ định `_NEG`. Một cách viết phủ định kỳ được hỏi mà danh sách chưa có sẽ bị chặn nhầm. Ngược lại, câu gán số cho kỳ được hỏi mà chen được một cụm trong danh sách vào cùng vế sẽ lọt.
- Kỳ tương đối ("năm trước", "cùng tháng năm trước", "tháng này", "năm nay", "kỳ này"):
  - luật `ok` bỏ qua, app vẫn gắn nhãn;
  - luật số tham khảo chỉ coi là đã ghi kỳ với ô "năm trước" của dòng. Với ô thay đổi ("so năm trước giảm {c3}"), luật tìm tiếp kỳ ghi phía trước.
- Chữ nối cắt phần đuôi.
- Ô năm do claim cấp ("năm gần nhất có dữ liệu là {c1}: R đạt {c2}") được tính là kỳ ghi.
- Câu "?" không có số được bỏ qua.

**Phát lại câu live đã ghi** (`warehouse/reviews/ai_gd2_20261015/claude_rv12b_phat_lai.py`).
- Đầu vào: 1.246 câu đã hiện trong `warehouse/ai_eval/live_*.jsonl`. Mỗi câu chạy lại trên DuckDB với đúng tham số tool và `raw_final` của lần đó.
- Bản sửa đầu chặn nhầm 9 câu vốn đúng. Đó là các câu có hai số trong một vế, "năm trước đó là {c2}", "so năm trước giảm {c3}", "tháng này" và ô năm.
- Sau khi sửa, **không câu nào bị luật mới chặn**. Cách kiểm: chạy thêm một lượt cơ sở (`--stub`) với các luật mới tắt, rồi so từng câu với bản cuối. Hai lượt (`claude_rv12b_phat_lai_co_so.json`, `claude_rv12b_phat_lai_cuoi.json`) ra **0 câu khác nhau**. 14 câu lệch so với log lệch ở cả hai lượt, tức do luật có từ trước (AI3, B3c, review RV), không do lượt này.
- Tám dạng câu đúng từ log thành test `test_rv12b_cau_live_dung_khong_bi_chan_nham`.

**Test** (`apps/retail_app/tests/test_ai_forecast.py`, 37 ca `test_rv12b_*`):
- 15 ca sai phải bị chặn: 10 ca lọt, 2 ca câu miễn trừ, 2 ca `ok` để đối chiếu, và "R năm 2019 là {số 2018}";
- 10 ca số tham khảo ghi đúng kỳ phải hiện;
- 4 ca số thay đổi / năm trước phải đạt;
- 8 ca câu live đúng.

**Thử ngược:** tắt các luật mới rồi chạy lại 13 ca sai đầu tiên: 11 ca trượt. 2 ca còn đạt là hai ca `ok` mà luật `ok` có từ trước đã chặn.
Kết quả probe:
- trước sửa: `claude_rv12b_probe_truoc_sua.json` (10 ca lọt) và `claude_rv12b_probe_truoc_sua_b13_b14.json` (2 ca câu miễn trừ lọt);
- sau sửa: `claude_rv12b_probe_sau_sua.json` (25/25 đúng).

**Lệnh và kết quả** (local, release `fc14b8a2f5a24ff99a434d7c`, PostgreSQL Docker bật):

```powershell
.venv/Scripts/python.exe warehouse/reviews/ai_gd2_20261015/claude_rv12b_probe.py out.json   # exit 0, 25/25
.venv/Scripts/python.exe warehouse/reviews/ai_gd2_20261015/claude_rv12b_phat_lai.py co_so.json --stub   # cơ sở, luật mới tắt
.venv/Scripts/python.exe warehouse/reviews/ai_gd2_20261015/claude_rv12b_phat_lai.py cuoi.json          # so "all": 0 câu khác
.venv/Scripts/python.exe scripts/review/review_ai_nonok_period_20261015.py                     # exit 0 (và 4 script còn lại exit 0)
.venv/Scripts/python.exe -m pytest <bộ hồi quy §8> apps/retail_app/tests/test_ai_charts.py -q --disable-warnings --tb=short   # 566 passed
.venv/Scripts/python.exe -m pytest apps/retail_app/tests -q --disable-warnings --tb=short       # 743 passed, 110 skipped (Databricks), 0 failed
```

**Hash sau sửa:** `evidence.py` `0460955e72cde17c710397f0b6e3591ddbfeb616bbc3da1b36f3bc3b621eda5f`; `service.py`
`2ebb45b195f81a43fb8855997bba65465ea65de8601f9b07b3b4ebfb2ec3d479`; `test_ai_forecast.py`
`aee437e4165b227d5f73d5751a7c5144b8557a2a31a828b1ee5765854019932c`.

**Thay câu giới hạn ở §9.1:** câu "luật chỉ áp cho số dự báo; số thực tế của tool PS… theo luật cũ" không còn đúng. Số thực tế có năm nay đi
qua cùng luật.

**Chưa chạy / giới hạn:**
- Mới thử bằng provider giả và phát lại câu cũ, chưa đo live LLM sau sửa.
- Bước kiểm đọc chữ, nên một cách viết chưa thử vẫn có thể lọt, ví dụ gán ngầm bằng đại từ ở câu không nhắc kỳ nào ("con số này dùng được cho sang năm").
- Câu live được phát lại phần lớn là câu PS ngày 05/10. Câu dự báo chỉ có bộ G / GM / V.
- Luật kỳ ghi sai ở `ok` (`stated_period_errors`) đổi hành vi của chat PS1–PS5, không riêng phần dự báo: câu "R năm 2019 là {số 2018}" nay bị chặn, không còn hiện kèm nhãn. Bản web public chỉ đổi khi deploy lại.

### 9.5. Codex kiểm độc lập §9.4 — 2026-10-16

**Kết luận: RV12 còn mở (P1).** Mã nguồn có đúng SHA-256 mà Claude ghi ở §9.4. Bộ 25 ca của Claude chạy lại **25/25 đạt**; script N06 và script N01–N05 của Codex exit 0; bộ hồi quy liên quan **566 passed**; toàn bộ test app **743 passed, 110 skipped** (Databricks). Hai ca mới, khác bộ 25 ca, vẫn cho hiện câu sai. Chúng dùng provider giả và bản DuckDB versioned local `fc14b8a2f5a24ff99a434d7c`.

| Ca | Câu trả lời do provider đưa ra (số `{c1}` lấy từ `get_forecast(G, month, 08/2023)`) | Kỳ vọng | Thực tế |
|---|---|---|---|
| Đối chứng | "Chưa có dự báo năm 2025. Riêng tháng 8/2023, dự báo G là {c1}." | Hiện `no_data` | Đúng |
| Mâu thuẫn ở câu sau | "Chưa có dự báo năm 2025. Riêng tháng 8/2023, dự báo G là {c1}. Năm 2025 chưa có dự báo **nhưng số này là dự báo năm 2025**." | Chặn | **Vẫn hiện `no_data`** |
| Mâu thuẫn trong cùng câu | "Riêng tháng 8/2023, dự báo G là {c1}. Năm 2025 chưa có dự báo **nhưng có thể dùng số này làm dự báo năm 2025**." | Chặn | **Vẫn hiện `no_data`** |

**Nguyên nhân trong code:** `_asked_mention_errors` ở `evidence.py:1014` bỏ qua cả vế khi `_NEG.search(clause)` tìm thấy một từ phủ định. Hai vế sai đều có "chưa" cho lần nhắc 2025 đầu, nhưng gán dương số cho lần nhắc 2025 sau. `_unnamed_period_errors` chỉ thấy `{c1}` ghi đúng 08/2023 ở câu trước; `stated_period_errors` cũng chỉ xét vị trí claim, nên không bắt câu gán lại sau đó. `service._check_final` nhận câu trả lời vì cả hai bộ kiểm trả danh sách lỗi rỗng.

**Tái hiện:** `.venv/Scripts/python.exe scripts/review/review_rv12b_codex_20261016.py` → đối chứng đạt, hai ca sai được hiện, script **exit 1**. Chi tiết ở `warehouse/reviews/ai_gd2_20261015/codex_rv12b_extra.json`. Đây là lỗi hiện câu có số dự báo sai kỳ, không chỉ là cách ghi nhãn.

**Kiểm phát lại độc lập:** chạy `claude_rv12b_phat_lai.py` hai lần với file output riêng của Codex (lượt `--stub` và lượt hiện tại). Cả hai phát lại 1.246 câu có `raw_final`; mảng `all` và `diffs` bằng nhau, nên luật mới không làm đổi kết quả nào của **tập câu cũ**. Cả hai có cùng 14 câu khác log gốc; lượt này chỉ xác định sai khác đó không do các luật RV12 mới, chưa truy nguyên từng câu. Có 9 dòng JSON hỏng không được phát lại. File kết quả: `warehouse/reviews/ai_gd2_20261015/codex_rv12b_replay_base.json` và `codex_rv12b_replay_current.json`. Tập cũ chưa chứa hai câu mâu thuẫn trên, vì vậy phép phát lại không chứng minh RV12 đã kín.

**Đề nghị Claude sửa:** kiểm từng lần nhắc kỳ được hỏi trong ngữ cảnh của chính mệnh đề, thay vì miễn cả vế chỉ vì có `_NEG`; nếu một vế vừa nói "chưa có" vừa gán số tham khảo cho kỳ đó thì phải từ chối câu trả lời. Thêm hai ca này vào test cố định; giữ ca đối chứng, bộ 25 ca và kiểm phát lại để tránh chặn nhầm. Chỉ đóng RV12 khi cả hai ca sai bị chặn, các câu tham khảo ghi đúng kỳ vẫn hiện. Codex chưa sửa source Claude phụ trách, chưa chạy LLM thật hay Databricks cho lượt này.

### 9.6. Claude sửa RV12 lượt 3 — 2026-10-16 (chờ Codex kiểm lại)

**Xác nhận lỗi §9.5.** Trên code §9.4, script `review_rv12b_codex_20261016.py` cho hai ca sai hiện (exit 1). Nguyên nhân đúng như Codex ghi:
`_asked_mention_errors` bỏ qua cả vế khi `_NEG` thấy một chữ phủ định, nên lần nhắc "năm 2025" thứ hai (sau "nhưng") không bị xét.

**Bộ ca chốt trước khi sửa** (`warehouse/reviews/ai_gd2_20261015/claude_rv12c_probe.py`). SHA-256 ghi trước khi sửa `evidence.py`, không
đổi sau đó: `24036137c219b27b2d806fe8edcb0c784c397010e03d2ad1f68b861dc3961786`. 155 ca, provider giả, hỏi "Dự báo doanh thu năm 2025?"
trừ ca ghi khác, số tham khảo là `get_forecast(G, month, 08/2023)` trừ nhóm E.

| Nhóm | Ca | Phải | Trước sửa |
|---|---|---|---|
| A. 2 ca của Codex, thêm bản `unsupported` và bản `ok` | 4 | chặn | 1 bị chặn (bản `ok`, luật RV01 có từ trước) |
| B. Ma trận 3 chữ phủ định × 10 cách nối (nhưng, mà, song, tuy nhiên, nên, vậy nên, chứ, còn, nối liền, ";") × 4 cách gán lại | 120 | chặn | 12 bị chặn (chỉ các ca ";") |
| C. Đảo thứ tự: gán trước, phủ định sau ("dù", "mặc dù", "tuy", "vì") | 4 | chặn | 0 |
| D. Gán ngầm, không nhắc lại kỳ ("… nhưng có thể dùng số này", "tạm lấy số này", "Có thể dùng số này thay.") | 6 | chặn | 0 |
| E. Số tham khảo khác loại: tổng cả vùng dự báo, G thực tế 2022 | 2 | chặn | 0 |
| F. Câu đúng: G01–G08 của §9.4, hai lần nhắc có hai phủ định, liệt kê "2025 và 2026", "tháng 1 và tháng 2/2025", "Không nên dùng số này làm dự báo năm 2025", "dùng số này để so sánh…" | 19 | hiện | 18 (chặn nhầm câu "Không nên dùng số này…") |

Trước sửa: 31/155 đúng, 13/136 ca sai bị chặn (`claude_rv12c_probe_truoc_sua.json`). Sau sửa: **155/155** (`claude_rv12c_probe_sau_sua.json`).
Bản `ok` của ca Codex đã bị chặn từ trước, nên lỗ chỉ nằm ở nhánh khác `ok`.

**Sửa.** Chỉ sửa `_asked_mention_errors` và các hằng số đi kèm trong `apps/retail_app/ai_explain/evidence.py`. `service.py` và prompt giữ nguyên.

| Luật | Nội dung |
|---|---|
| Phủ định theo từng lần nhắc (`_scope_segments`, `_unnegated`) | Vế (giữa hai dấu `,` `:`) được cắt tiếp ở chữ nối `_SCOPE`: nhưng, song, tuy nhiên, tuy vậy, dù vậy, mặc dù, dù, tuy, mà, còn, chứ, trong khi, vậy nên, cho nên, nên, vì vậy, vì thế, do đó, do vậy, bởi vì, vì, tức là, tức, nghĩa là, và, hoặc, hay. "nên" đứng sau "không / chẳng" không cắt. Trong mỗi đoạn, mỗi chữ phủ định `_NEG` được gán cho lần nhắc kỳ được hỏi gần nó nhất. Còn lần nhắc nào không được gán chữ phủ định nào thì chặn. Câu không có chữ nối ("Năm 2025 chưa có dự báo số này là dự báo năm 2025") vẫn bị chặn, vì "chưa" gần lần nhắc đầu hơn |
| Liệt kê kỳ | Các kỳ liền nhau, giữa chỉ có chữ kỳ hoặc "và / hoặc / hay", tính là một lần nhắc ("năm 2025 và 2026"). Đoạn chỉ gồm kỳ, không có động từ, gộp vào đoạn kề. Ngoặc không cắt đoạn |
| Gán ngầm (`_USE_REF`) | Status khác `ok`, có số tham khảo kỳ khác, câu khẳng định (không kết thúc bằng "?") có một trong các cụm: "dùng / lấy / áp dụng / thay (luôn / tạm) + số này / con số này / số đó / số trên / mức này / giá trị này / tổng này / kết quả này"; "coi / xem + số này + là / như"; "số này … dùng / áp dụng / thay" → chặn. Được qua khi có "không / chưa / đừng / chẳng" trong 3 từ ngay trước động từ hoặc trong cụm, hoặc cụm ghi rõ "để so sánh / tham khảo / đối chiếu" |
| `_NEG` thêm | "không nên", "đừng" |

Giữ nguyên từ lượt 2: vế nhắc kỳ được hỏi mà không có chữ phủ định nào vẫn bị chặn; các miễn trừ (vế có số của chính kỳ được hỏi, câu hỏi
lại "?" không có số, kỳ ghi đúng là kỳ thật của số tham khảo) không đổi.

**Phát lại câu live đã ghi** (1.246 câu, cách làm như §9.4).
- Bản sửa đầu chặn nhầm 3 câu vốn đúng, đều là E08: "chưa hỗ trợ truy vấn theo khoảng ngày tùy ý (15/3–10/6/2019)". Dấu ngoặc tách kỳ khỏi
  chữ "chưa" đứng trước. Đã sửa (ngoặc không cắt đoạn, đoạn chỉ gồm kỳ gộp vào đoạn kề); câu E08 thành test.
- Một bản vá giữa chừng đặt tên hằng số mới trùng `_ANAPHOR` (luật PS1–PS3 ở dòng 157), làm 8 test PS hỏng và lệch phép phát lại. Bộ hồi
  quy và phép phát lại bắt được; hằng số mới đổi tên thành `_REF_WORD`. Quét AST: không còn tên nào được gán hai lần ở cấp module.
- Bản cuối: mảng `all` và `diffs` **bằng đúng** kết quả lượt 2 (`claude_rv12b_phat_lai_cuoi.json`), tức luật lượt 3 không đổi kết quả của
  câu cũ nào. Vẫn 14 câu lệch log như lượt 2. Kết quả: `claude_rv12c_phat_lai.json`.
- Như Codex ghi, tập câu cũ không có câu mâu thuẫn kiểu §9.5, nên phép phát lại chỉ kiểm chặn nhầm, không chứng minh luật kín.

**Test** (`apps/retail_app/tests/test_ai_forecast.py`, thêm 22 ca):
- `test_rv12c_phu_dinh_khong_che_lan_nhac_khac`, 11 ca phải chặn: hai ca của Codex giữ nguyên chữ, nối bằng "và", nối liền, hai ca đảo thứ
  tự, ba ca gán ngầm, tổng cả vùng, G thực tế 2022;
- `test_rv12c_moi_lan_nhac_co_phu_dinh_van_hien`, 10 ca phải hiện;
- câu live E08 thêm vào `test_rv12b_cau_live_dung_khong_bi_chan_nham`.

**Thử ngược:** thay `_asked_mention_errors` bằng bản lượt 2 rồi chạy 21 ca `rv12c`: cả 11 ca phải chặn đều trượt; ca "Không nên dùng số
này…" cũng trượt (bản cũ chặn nhầm); 9 ca còn lại đạt.

**Lệnh và kết quả** (local, release `fc14b8a2f5a24ff99a434d7c`, PostgreSQL Docker bật):

```powershell
.venv/Scripts/python.exe warehouse/reviews/ai_gd2_20261015/claude_rv12c_probe.py out.json     # exit 0, 155/155
.venv/Scripts/python.exe warehouse/reviews/ai_gd2_20261015/claude_rv12b_probe.py out.json     # exit 0, 25/25
.venv/Scripts/python.exe warehouse/reviews/ai_gd2_20261015/claude_rv12b_phat_lai.py rv12c.json  # all / diffs bằng lượt 2
.venv/Scripts/python.exe scripts/review/review_rv12b_codex_20261016.py                         # exit 0 (5 script còn lại cũng exit 0)
.venv/Scripts/python.exe -m pytest <bộ hồi quy §8> -q                                          # 588 passed
.venv/Scripts/python.exe -m pytest apps/retail_app/tests -q                                    # 765 passed, 110 skipped (Databricks), 0 failed
```

Chạy script của Codex thì script ghi lại `codex_rv12b_extra.json` bằng kết quả sau sửa (cả ba ca `passed: true`). Script không bị sửa.

**Hash sau sửa:** `evidence.py` `8d189831e6b1a26828fb19cf5ab41fed128d1a1581b6f0dcf1f2d937157df2bc`; `service.py` không đổi
`2ebb45b195f81a43fb8855997bba65465ea65de8601f9b07b3b4ebfb2ec3d479`; `test_ai_forecast.py`
`823d376b1bcfcd35fb821044f63d0371f79dcc938c16869acc97a5a678d16138`; script Codex
`e186416e3df72f5ff06f94958682c4a06f25ce19476e2b17df3ca4cf003a0b2d`.

**Chưa chạy / giới hạn:**
- Mới thử bằng provider giả và phát lại câu cũ, chưa đo live LLM sau sửa.
- Vẫn là kiểm bằng chữ. Ba câu dưới (đã thử bằng provider giả, sau `Riêng tháng 8/2023, dự báo G là {c1}.`) **vẫn hiện**; Codex nên soi
  tiếp hướng này:
  - chữ phủ định đứng sát lần nhắc gán số nhưng phủ định thứ khác ("Số này là dự báo năm 2025 chưa điều chỉnh");
  - gán ngầm bằng từ ngoài danh sách ("Năm 2025 chưa có dự báo, nhưng mức tương tự vẫn hợp lý");
  - phủ định kép ("không có lý do gì để không coi đây là dự báo năm 2025");
  - câu kết thúc bằng "?" không có chỗ đặt vẫn được miễn như §9.4. Đã thử, ở cả `no_data` và `needs_clarification`, hai câu sau **vẫn
    hiện**: "Năm 2025 chưa có dự báo nhưng số này là dự báo năm 2025?" và "Bạn có muốn dùng số này làm dự báo năm 2025?". Chưa sửa
    lượt này. Đề xuất: chỉ miễn câu "?" không có cả chỗ đặt lẫn chữ trỏ số (`_REF_WORD`: "số này / mức này / số trên…"), rồi phát lại
    để kiểm chặn nhầm câu hỏi lại.
- Luật gán ngầm có thể chặn nhầm câu gợi ý hợp lý chưa có trong log: đã thử, "Năm 2025 chưa có dự báo; có thể dùng số này làm mốc." bị
  chặn.
- Phạm vi: `_asked_mention_errors` áp cho mọi câu trả lời khác `ok` có số tham khảo kỳ khác, kể cả chat PS1–PS5 (ví dụ hỏi quý
  hoặc khoảng ngày, trả số cả năm). Ba câu chặn nhầm ở bản đầu (E08) đều là câu PS `unsupported`. Phát lại 1.246 câu cũ, phần lớn là câu
  PS ngày 05/10, bản cuối không đổi kết quả câu nào. Bản web public chỉ đổi khi deploy lại.
- Hướng kín hơn, chưa làm, chờ PM quyết: ở status khác `ok`, app tự viết câu dẫn số tham khảo theo khuôn cố định ("Riêng {kỳ thật}, dự báo
  G là …") và bỏ phần chữ tự do của mô hình quanh số.

### 9.7. Codex kiểm độc lập §9.6 — 2026-10-16

**Kết luận: hai ca §9.5 đã sửa, RV12 vẫn mở (P1).** SHA-256 của `evidence.py`, `service.py`, `test_ai_forecast.py` khớp §9.6. Script Codex lượt trước exit 0: câu tham khảo đúng 08/2023 hiện, hai câu gán lại năm 2025 bị chặn. Probe lượt 2 **25/25** và probe lượt 3 **155/155**; bộ hồi quy AI/dự báo/pipeline liên quan **588 passed**. Năm script review cũ exit 0 (script quality gate ban đầu gặp quyền đọc Parquet trong sandbox, chạy lại ngoài sandbox exit 0). Không chạy lại toàn bộ 765 test app mà Claude báo ở §9.6.

**Ca mới kiểm độc lập:** cùng hỏi "Dự báo doanh thu năm 2025?"; provider giả lấy `get_forecast(G, month, 08/2023)` và dẫn `{c1}` đúng nhãn ở câu đầu. Kết quả lưu ở `warehouse/reviews/ai_gd2_20261015/codex_rv12c_extra.json`.

| Ca | Vế thêm sau câu "Riêng tháng 8/2023, dự báo G là {c1}." | Kỳ vọng | Thực tế |
|---|---|---|---|
| Đối chứng | "Chưa có dự báo năm 2025" ở câu trước; hoặc hỏi "Bạn muốn xem kỳ nào khác?" | Hiện câu trả lời | Cả hai hiện |
| Gán sai dưới dạng câu hỏi | "Năm 2025 chưa có dự báo nhưng số này là dự báo năm 2025?" | Chặn | **Vẫn hiện `no_data`** |
| Gợi dùng số sai kỳ | "Năm 2025 chưa có dự báo. Bạn có muốn dùng số này làm dự báo năm 2025?" | Chặn | **Vẫn hiện `needs_clarification`** |
| Phủ định thuộc việc khác | "Số này là dự báo năm 2025 chưa điều chỉnh." | Chặn | **Vẫn hiện `no_data`** |
| Phủ định kép | "Không có lý do gì để không coi đây là dự báo năm 2025." | Chặn | **Vẫn hiện `no_data`** |
| Tham khảo đúng nghĩa | "Năm 2025 chưa có dự báo. … Có thể dùng số này làm mốc tham khảo." và bản viết rõ "… để so sánh, không phải dự báo năm 2025." | Hiện câu tham khảo đúng kỳ | **Cả hai bị `answer_validation_failed`** |

**Tái hiện:** `.venv/Scripts/python.exe scripts/review/review_rv12c_codex_20261016.py` → 2 đối chứng đạt, 4 câu sai vẫn hiện với `validation_errors=[]`, 2 câu tham khảo bị chặn; **exit 1**. Bốn câu lọt là cùng lớp mà Claude đã nêu ở giới hạn §9.6; Codex xác nhận trực tiếp trên checkout hiện tại. Câu "để so sánh, không phải dự báo năm 2025" làm rõ ca chặn nhầm so với câu "mốc tham khảo" ngắn của Claude.

**Nguyên nhân theo code:** `_asked_mention_errors` miễn nguyên câu kết thúc `?` không có `{c1}` (`evidence.py:1072`), rồi bỏ kiểm dùng số tham khảo ở câu hỏi (`:1085`). `_unnegated` đếm chữ `_NEG` gần kỳ được nhắc, không xác định nó đang phủ định **dự báo năm 2025** hay "điều chỉnh" / một chữ phủ định khác, nên nhận hai câu khẳng định sai. `_USE_REF` bắt "dùng số này" trước khi xét "làm mốc tham khảo để so sánh" (`:1087`), gây chặn nhầm. Không sửa source Claude phụ trách trong lượt này.

**Hồi quy log cũ:** Codex phát lại 1.246 câu `raw_final` trên bản hiện tại; mảng `all` và `diffs` bằng bản Codex trước sửa, cùng 14 câu khác log gốc và 9 dòng JSON hỏng không được phát lại. Output `warehouse/reviews/ai_gd2_20261015/codex_rv12c_replay_current.json`. Kết quả này kiểm hành vi trên tập cũ; tập đó không có các vế sai ở bảng trên.

**Nghiệm thu để Claude sửa tiếp:** câu trả lời khác `ok` có số tham khảo 08/2023 không được khẳng định hoặc đề nghị dùng số ấy làm dự báo 2025, kể cả khi vế kết thúc `?` hoặc chứa một chữ "không/chưa" phủ định việc khác. Câu chỉ ghi đúng kỳ và dùng làm mốc **tham khảo để so sánh**, nói rõ không phải dự báo 2025, phải được hiện. Giữ 155 ca của Claude, hai ca §9.5 và phép phát lại cũ. Nếu bước kiểm chữ tiếp tục khó phân biệt, có thể để app dựng phần dẫn số tham khảo theo khuôn an toàn như đề xuất cuối §9.6; đó là hướng sửa, chưa triển khai hay được PM chốt. Chưa kiểm live LLM hoặc Databricks sau sửa.

### 9.8. Codex sửa và kiểm lại RV12 — 2026-10-16

PM yêu cầu Codex sửa source rồi test. Chỉ sửa bước kiểm kỳ ở `apps/retail_app/ai_explain/evidence.py`, thêm test tại `apps/retail_app/tests/test_ai_forecast.py` và mở rộng `scripts/review/review_rv12c_codex_20261016.py`; không đổi tool, prompt, số dự báo hay bản dữ liệu.

**Sửa:**

- Câu hỏi lại kết thúc bằng `?` chỉ được miễn kiểm kỳ khi **không trỏ số tham khảo**. Vì vậy "Bạn muốn xem kỳ nào khác?" vẫn qua; "Bạn có muốn dùng số này làm dự báo năm 2025?" bị chặn.
- Chữ phủ định phải nói về việc **không có số/dự báo** hoặc **không thể dùng số**. "Chưa điều chỉnh", "chưa thể điều chỉnh" và "không/chưa có lý do gì để không coi đây là dự báo năm 2025" không còn che phép gán sai kỳ. Giữ các cách từ chối thật đã gặp trong log, gồm "chưa hỗ trợ" và "chưa gộp được khoảng ngày".
- Câu dùng số đúng kỳ "làm mốc tham khảo" được qua, kể cả bản ghi rõ "để so sánh, không phải dự báo năm 2025". Phủ định kép "không có lý do gì để không dùng số này" không được coi là lời khuyên **không** dùng số.

**Test trước/sau sửa:** bảy ca RV12 mới ban đầu có 6 trượt; thêm ca phủ định kép không nhắc lại năm và hai ca phủ định sai phạm vi khi soi tiếp. Bản cuối: `review_rv12c_codex_20261016.py` **11/11 đạt, exit 0**; câu sai đều ra `answer_validation_failed` và không hiện số, câu tham khảo đúng kỳ vẫn hiện. Nhóm test `rv12b`, `rv12c`, `rv12d` **70 passed**. Probe Claude lượt 2 **25/25**, lượt 3 **155/155**; script Codex §9.5 và các script review kỳ cũ exit 0. Bộ hồi quy AI/dự báo/pipeline liên quan **599 passed**.

**Chặn nhầm tìm trong phép phát lại:** bản sửa đầu chặn câu live E08 `unsupported`: "chưa gộp được khoảng ngày tùy ý (15/3–10/6/2019)". Codex thêm nguyên câu và hai tool call của log thành test `test_rv12d_live_e08_khoang_ngay_chua_gop_duoc_khong_bi_chan`, rồi sửa đúng cụm này. Phát lại bản cuối 1.246 câu có `raw_final`: `all` và `diffs` **bằng bản trước sửa**; cùng 14 câu khác log gốc từ trước, 9 dòng JSON hỏng không phát lại. File: `warehouse/reviews/ai_gd2_20261015/codex_rv12d_replay_tight.json`.

**Phạm vi kết luận:** các ca RV12 đã biết và các ca mở rộng ở §9.7 đạt trên bản DuckDB versioned local `fc14b8a2f5a24ff99a434d7c` với provider giả. Chưa chạy lại toàn bộ app, live LLM, Databricks hay deploy. Bước kiểm vẫn dựa trên cách viết câu; phép phát lại log cũ và test giả không chứng minh mọi câu LLM chưa thấy đều đúng. Với đường public, cần đánh giá live bằng bộ câu mới và cân nhắc app dựng câu dẫn số tham khảo theo khuôn an toàn nếu còn cách viết lọt.

### 9.9. Claude kiểm lại §9.8 — 2026-10-16

**Kết luận: mọi ca đã biết đều đạt, nhưng RV12 vẫn mở (P1). Lượt sửa này còn gây thêm chặn nhầm câu từ chối đúng (P2).** Claude không sửa
source ở lượt này. Mã băm đã kiểm: `evidence.py` `5dace4715cc2ff9e7ccfde1f801ecee329a981cbffeefa237580335e328943d7`, `test_ai_forecast.py`
`194b35f178fae63f3298123dde58f915508d1126cbf6f0b0fdff62775140e5b4`, `review_rv12c_codex_20261016.py`
`bb29bf00b001c12847dff4861c41a2b2242f55fb3f37d1b47f350ac973e2ec92`; `service.py` không đổi (`2ebb45b1…d479`). Chạy trên release local
`fc14b8a2f5a24ff99a434d7c`, provider giả.

**Tái hiện §9.8:**
- `review_rv12c_codex_20261016.py`: 11/11, exit 0. Sáu script review cũ: exit 0. Chạy các script này sẽ ghi lại `codex_rv12b_extra.json` và
  `codex_rv12c_extra.json` bằng kết quả hiện tại.
- Probe Claude lượt 2 đạt 25/25. Lượt 3 đạt 155/155, mã băm bộ ca không đổi.
- Phát lại 1.246 câu: mảng `all` và `diffs` bằng `claude_rv12b_phat_lai_cuoi.json`.
- Hồi quy §8: 599 passed. Toàn bộ test app: 776 passed, 110 skipped (Databricks), 0 failed.

**Bộ ca mới** (`warehouse/reviews/ai_gd2_20261015/claude_rv12d_probe.py`). SHA-256 ghi trước lượt chạy đầu:
`e5207f951910e51d131a75ca53fa40ef91fc3812260c2d5a8c2bb65b44ebea83`. Kết quả ở `claude_rv12d_probe_ket_qua.json`.
- Bộ có 37 ca, cùng khuôn §9.7: hỏi "Dự báo doanh thu năm 2025?", tool trả `get_forecast(G, month, 08/2023)`, câu dẫn ghi đúng kỳ của `{c1}`.
- Nhóm S là chat PS: hỏi "R năm 2023 là bao nhiêu?", dẫn R năm 2022.
- Cột cuối chạy lại cùng ca, chỉ thay `_NEG` bằng bản lượt 3, để tách ca đổi do lượt 4.
- Mọi ca bị chặn đều do `_asked_mention_errors` ("nhắc … (kỳ được hỏi) cạnh số tham khảo").
- Provider giả gửi lại nguyên câu ở lượt sửa (`service.py`: một lượt sửa, có kèm lời báo lỗi). Vì vậy số chặn nhầm ở đây là trường hợp
  xấu nhất. Với mô hình thật, lời báo lỗi ("nói rõ 2025 chưa có số") thường dẫn tới câu có cụm trong danh sách: mỗi câu chặn nhầm tốn
  thêm một lượt gọi, và chỉ hiện lỗi khi lượt sửa cũng trượt. Log live cũ có 146 lượt phải sửa, 28 lượt vẫn trượt sau khi sửa. Ca lọt
  không có lượt sửa, vì câu sai được hiện ngay lần đầu. Tỷ lệ thật chỉ đo được bằng live.

| Nhóm | Ca | Phải | Bản §9.8 | `_NEG` lượt 3 |
|---|---|---|---|---|
| P. Từ chối đúng, dùng cụm ngoài danh sách `_NEG` | 14 | hiện | **0/14 hiện** | 9/14 hiện |
| PC. Từ chối đúng, dùng cụm có trong danh sách ("nằm ngoài", "vượt quá vùng", "chưa được dự báo", "chưa có dự báo") | 4 | hiện | 4/4 | 4/4 |
| R. Gán số 08/2023 cho năm 2025; cụm phủ định nói về việc khác, hoặc gán ngầm "mức tương tự" | 11 | chặn | **0/11 chặn** | 0/11 |
| RC. Đối chứng: "Số này là dự báo năm 2025." và bản "… chưa điều chỉnh." | 2 | chặn | 2/2 | 1/2 |
| S. PS từ chối đúng | 3 | hiện | **0/3 hiện** | 1/3 |
| SC. PS đối chứng "Năm 2023 nằm ngoài dữ liệu." | 1 | hiện | 1/1 | 1/1 |
| SR. PS gán sai: "Số này là R năm 2023 chưa có số kiểm toán." và bản không có phủ định | 2 | chặn | 1/2 | 1/2 |

Tổng: 8/37 đúng. Có **17 ca chặn nhầm**: 10 ca mới do lượt 4 thu hẹp `_NEG`, 7 ca có từ trước. Có **12 ca lọt**; cả 12 cũng lọt với
`_NEG` lượt 3.

**Chặn nhầm mới do lượt 4.** Các câu này qua được ở lượt 3:
- "Năm 2025 chưa nằm trong vùng dự báo."
- "Mô hình chưa dự báo tới năm 2025."
- "Dự báo năm 2025 chưa được hỗ trợ." Log live có 29 câu dùng cụm "chưa được hỗ trợ".
- "…, nên năm 2025 không có trong kết quả."
- "Tôi không thể đưa ra dự báo năm 2025."
- "Hiện chưa thể ước tính doanh thu năm 2025."
- "Năm 2025 chưa có trong kho dự báo."
- "Dự báo năm 2025 không có sẵn."
- "Còn năm 2025 thì chưa có."
- PS: "Dữ liệu năm 2023 chưa được cập nhật."

**Chặn nhầm có từ trước:** "không thuộc vùng dự báo", "không nằm trong vùng dự báo", "Vùng dự báo không bao gồm năm 2025", "Năm 2025
không được dự báo", và ba câu PS cùng kiểu.

**Còn lọt.** 9 ca (R00–R07, SR0) thuộc đúng lớp mà §9.7 đặt làm tiêu chí: cụm phủ định có trong danh sách nhưng nói về việc khác, nên
che lần nhắc kỳ được hỏi. 3 ca (R08–R10) là câu phỏng đoán "mức tương tự", không kèm số. §9.7 chưa đặt lớp này làm tiêu chí; PM có thể
coi là chấp nhận được.
- "Số này là dự báo năm 2025 chưa có số thực tế." Cụm "chưa có số" là lời miễn trừ quen thuộc của câu trả lời dự báo.
- "Số này là dự báo năm 2025 vượt kỳ vọng."
- "Đây là dự báo năm 2025 nằm ngoài dự kiến."
- "Số này là dự báo năm 2025 không phải tháng 8/2023."
- "Số này là dự báo năm 2025 không có dữ liệu thực tế đối chiếu."
- "Số này là dự báo năm 2025 không thể tính chính xác hơn."
- "Số này là dự báo năm 2025 chưa thể xem là chắc chắn."
- Phủ định kép: "Không phải là không thể dùng số này cho năm 2025."
- Gán ngầm, không có chữ "số này": "Năm 2025 chưa có dự báo, nhưng có lẽ cũng quanh mức tháng 8/2023", "… mức tương tự vẫn hợp lý",
  "… song có thể kỳ vọng mức tương đương".
- PS: "Số này là R năm 2023 chưa có số kiểm toán."

**Vì sao phép phát lại không bắt được.** Trong log live, câu từ chối kỳ ngoài vùng gần như chỉ viết "nằm ngoài" (81 lần) hoặc "không có / chưa
có số". Còn 29 câu "chưa được hỗ trợ" không đi cùng số tham khảo kỳ khác. Vì vậy phép phát lại đạt không nói được gì về chặn nhầm với cách
viết mới.

**Nhận định.** Bốn lượt vá đều làm cùng một việc: thêm hoặc bớt cụm chữ. Mỗi lượt đóng ca vừa tìm thấy, và lỗ dời sang chỗ khác:
- Lượt 4 thu hẹp danh sách để chặn "chưa điều chỉnh", làm 10 câu từ chối đúng bị chặn.
- Các cụm còn trong danh sách ("chưa có số", "vượt", "nằm ngoài", "không phải tháng …") vẫn che câu gán sai.

Claude không thấy danh sách cụm nào vừa đủ rộng cho câu từ chối thật, vừa đủ hẹp để không che câu gán sai.

**Đề xuất (chờ PM quyết, chưa làm):**
1. Ở status khác `ok`, mô hình không tự viết câu chứa số tham khảo kỳ khác. Có hai cách:
   - (a) app dựng câu dẫn số theo khuôn cố định: "{kỳ hỏi} chưa có dự báo. Riêng {kỳ thật của số}, dự báo G là {số}.";
   - (b) bỏ số tham khảo khỏi câu trả lời, app hiện số đó ở khung bằng chứng có nhãn kỳ.

   Với cả hai cách, luật cụm chữ chỉ còn kiểm phần chữ không có số.
2. Đo live bộ GM và V (khoảng 0,2–0,3 USD) để biết tỷ lệ chặn nhầm và tỷ lệ lọt với cách viết thật của mô hình. Phép đo này nên làm sau khi
   chọn hướng ở bước 1.

**Lặt vặt:** `evidence.py` có 41 dòng LF lẫn trong file CRLF, `ke_hoach_ai_gd2.md` có 5 dòng như vậy. Python không bị ảnh hưởng, và git
(`core.autocrlf=true`) sẽ chuẩn hóa khi commit. Claude không sửa, để mã băm đã ghi không đổi.

### 9.10. Claude làm hướng khuôn: RV12 lượt 5 — 2026-10-17 (chờ Codex kiểm)

**Quyết định của PM.** Sau §9.9, PM chọn hướng (a): với câu trả lời khác `ok` có dẫn số của kỳ khác kỳ được hỏi, app tự viết câu dẫn
số đó; mô hình không còn tự viết câu chứa số này. **Tiêu chí nghiệm thu RV12 vì vậy đổi:**
- Trước đây: câu gán sai phải bị chặn.
- Nay: câu gán sai của mô hình không được xuất hiện. Số của kỳ khác chỉ hiện trong dòng do app viết, kèm kỳ thật, nhóm và chỉ tiêu.
- Câu trả lời vẫn hiện với status gốc.

Nhánh `ok` không đổi.

**Sửa.** Chỉ sửa `apps/retail_app/ai_explain/evidence.py` và `service.py`; không đổi prompt, tool hay bản dữ liệu.
- `reference_period_errors` tách thành hai hàm:
  - `reference_refs`: chỉ nhận ra số của kỳ khác, luật nhận ra giữ như lượt 2;
  - `reference_answer`: dựng câu trả lời theo khuôn.
- Thứ tự các phần của khuôn:
  1. **Câu "ngoài vùng"**, chỉ có khi mọi kỳ được hỏi đọc được chắc chắn (có năm) và nằm trọn ngoài vùng:
     - câu hỏi dự báo: "Năm 2025 nằm ngoài vùng dự báo (01/01/2023 → 01/07/2024), nên chưa có dự báo cho kỳ này.";
     - câu hỏi khác: "… nằm ngoài dữ liệu thực tế (04/07/2012 → 31/12/2022), nên chưa có số thực tế …".

     Nếu kỳ được hỏi nằm trong vùng (lý do thật là grain, nhóm hay chỉ tiêu, như ca B02, B03, E08) thì không có câu này.
  2. **Câu dẫn của mô hình.** Chỉ dùng khi không có câu "ngoài vùng". Một câu được giữ khi:
     - có từ 3 chữ trở lên;
     - không có chữ số, chỗ đặt `{cN}`, hay kỳ tương đối;
     - không có chữ trỏ, dùng hay phỏng đoán số (`_MODEL_DROP`).

     Không còn câu nào thì app thêm "Chưa có số đúng như câu hỏi."; với status hỏi lại là "Câu hỏi cần nói rõ thêm trước khi có số đúng kỳ.".
     Câu đầu là câu nối ("Ngoài ra…") thì app thêm câu này phía trước.
  3. **Khối số.** Dòng đầu "Số tham khảo, không phải số bạn hỏi:", sau đó mỗi số một dòng "- Kỳ, nhóm: chỉ tiêu là **số** (phần thêm)".
     - Kỳ, nhóm và chỉ tiêu lấy từ dòng dữ liệu, qua `_label_parts` tách từ `_label`.
     - Nhóm ghi "ngành / vùng / kênh X", hoặc "toàn công ty" khi không có nhóm.
     - Số luôn có dấu: ΔR ghi −5.792.272 VND.
     - Ô năm và ô tên được bỏ qua. Số đo chưa có nhãn chỉ tiêu hoặc kỳ thì trả lỗi để mô hình sửa, không hiện số không nhãn.
  4. **Câu hỏi lại hoặc gợi ý** của mô hình, cũng qua bộ lọc ở mục 2. Status hỏi lại mà không còn câu hỏi nào thì app thêm "Bạn muốn xem
     kỳ nào?".
- **Phạm vi áp dụng:** mọi câu trả lời khác `ok` có số của kỳ khác, kể cả khi lẫn số đúng kỳ (B03: R toàn công ty tháng 12/2021 cạnh R
  tháng 12/2020). Câu trả lời không có số kỳ khác giữ luật cũ: kỳ ghi trong câu phải khớp kỳ của số.
- **Giữ nguyên:** nhánh `ok` (luật chặn của lượt 2) và RV10 (kỳ không có thật thì không dẫn số nào).
- **Gỡ:** `_asked_mention_errors` và các hằng số chữ phủ định của lượt 2–4 (`_NEG`, `_SCOPE`, `_USE_REF`, `_DOUBLE_NEG_BEFORE`…). Sau
  khi đổi, các phần này không còn được gọi. Bản trước khi sửa, đúng bản §9.9 đã kiểm (`5dace47…`, `2ebb45b…`, `194b35f…`), lưu ở
  `warehouse/reviews/ai_gd2_20261015/truoc_khuon/`.

**Kiểm** (local, release `fc14b8a2f5a24ff99a434d7c`, provider giả):
- **Chạy lại câu đầu vào mọi bộ RV12 theo tiêu chí mới.** Script `claude_rv12e_probe.py`, SHA-256 chốt trước lượt chạy đầu:
  `3cc96fd0d619f98fac6562b79ddeb69dff4dd800dc472e23e33b5632779335b9`. Kết quả **231/231**: Codex §9.5 3/3, Codex §9.8 11/11, Claude
  lượt 2 25/25, lượt 3 155/155, lượt 4 37/37.
  - 226 ca đi qua khuôn. Ở các ca này: mọi câu có chữ số phải là câu "ngoài vùng" hoặc dòng số; năm được hỏi không có trong dòng số hay
    câu cuối; câu còn lại không có chữ trỏ hay dùng số.
  - 5 ca còn lại (status `ok`, hoặc số đúng kỳ) giữ kỳ vọng cũ.
  - Hàm kiểm viết độc lập với `evidence.py`.
- **Test** (`test_ai_forecast.py`):
  - 38 test RV12 cũ "phải chặn" ở nhánh khác `ok` đổi sang kiểm khuôn (`_khuon`, viết độc lập), giữ nguyên câu đầu vào, kể cả 10 ca
    của Codex trong `test_rv12d_*`. Ca status `ok` vẫn kiểm chặn.
  - Thêm 12 test `rv12e`: khuôn đúng từng chữ; 3 câu từ chối PS viết tự nhiên từng bị chặn nhầm ở §9.9; B03 lẫn số đúng kỳ và kỳ khác;
    4 câu phỏng đoán không kèm số; câu hỏi lại bị bỏ thì app hỏi; số không nhãn trả lỗi; RV10.
- **Thử phá:**
  - tắt bộ lọc câu: 8 test RV12 trượt (các ca không có câu "ngoài vùng", và câu hỏi lại);
  - dòng số ghi kỳ được hỏi thay kỳ thật: 54 test trượt.
- **Phát lại 1.246 câu:** status bằng lượt 2 (`all`, `diffs`). Phép này không đo được khuôn, vì khuôn chỉ thay chữ, không đổi status.
- **Trước / sau trên câu live:** 23 lượt (16 câu khác nhau, đều là chat PS) đi qua khuôn: `claude_rv12e_truoc_sau.md`. Cột "trước" là
  câu đã hiện khi chạy live.
- **Hồi quy §8:** 611 passed (599 cũ + 12 test `rv12e`). **Toàn bộ test app:** chưa có kết quả trọn vẹn: Claude Code dừng lần chạy vì máy thiếu bộ nhớ, khi đã qua khoảng 90% số test và chưa có test nào hỏng; cần chạy lại. *Bổ sung 2026-10-17:* chạy riêng (foreground) phần còn thiếu (`test_smoke`, `test_m1`–`test_m5`, `test_khong_hardcode`, `test_backends`): 162 passed. Trong lúc chạy, một phiên Claude khác đang sửa `evidence.py`, nên không chắc lần chạy này đúng bản lượt 5. Toàn bộ test app trên bản §9.11: 844 passed, 110 skipped, 0 failed.
- **Script Codex:**
  - `review_rv12b_codex_20261016.py`, `review_rv12c_codex_20261016.py` và `review_ai_nonok_period_20261015.py` **exit 1**, vì vẫn dùng
    tiêu chí cũ "phải chặn" (N06 và 9 câu gán sai nay hiện theo khuôn, đúng kỳ);
  - 4 script còn lại exit 0.

  Claude không sửa script của Codex. Đề nghị Codex đổi tiêu chí ba script này theo quyết định của PM.

**Thay đổi người dùng thấy** (chi tiết ở `claude_rv12e_truoc_sau.md`):
- Mỗi số tham khảo nay ghi đủ kỳ, nhóm (hoặc "toàn công ty") và chỉ tiêu. Chữ quanh số không còn do mô hình viết.
- Câu từ chối ngắn hơn, vì mọi câu có chữ số của mô hình bị bỏ, kể cả câu nêu lý do:
  - E08 mất "chưa hỗ trợ khoảng ngày tùy ý (15/3–10/6/2019)" và "mỗi nhóm tính riêng, không phải giao của hai điều kiện";
  - H08 và E12 mất câu lý do chính.

  8 trên 16 câu chỉ còn câu mở chung "Chưa có số đúng như câu hỏi." / "Câu hỏi cần nói rõ thêm…". B02, B03 và một bản H08 giữ được câu
  lý do, vì câu đó không có chữ số.
- Câu hỏi dự báo kỳ ngoài vùng: chỉ còn câu "ngoài vùng" do app viết, khối số, và câu hỏi lại nếu có.

**Giới hạn / chưa làm:**
- Chưa đo live. Prompt vẫn hướng dẫn mô hình viết câu dẫn số kỳ khác ("Riêng tháng 8/2023, …"); app bỏ câu đó. Có thể rút phần hướng dẫn
  này khỏi prompt để bớt token, và nhắc mô hình viết lý do không kèm chữ số. Chưa làm, chờ PM.
- Bộ lọc câu vẫn là danh sách chữ, nhưng sai ở đây chỉ làm mất lời, không gắn được số vào kỳ sai: số chỉ hiện trong dòng app viết. Còn
  lọt được câu phỏng đoán không có số, không nhắc kỳ, không dùng chữ nào trong danh sách, khi câu trả lời không có câu "ngoài vùng".
- Áp cho cả chat PS1–PS5. Bản web public chỉ đổi khi deploy lại.

**Hash sau sửa (lượt 5):** `evidence.py` `c413e8d6463849611e00c1e5bd6f1bc3ff975cf43a8f2029a9cded583dc5b514`; `service.py`
`86b5bea8836b1af197198dbac026348f3f819da2800dca3484aa970f813ac97c`; `test_ai_forecast.py`
`233080ec55f17401ffd3fa8a75a72d5109099711de28770e8dc2bb883782ac2e`. `evidence.py` ghi CRLF toàn file (hết dòng LF lẫn của §9.9).

**Test chưa chạy trên bản cuối:** bộ hồi quy §8 (611 passed) không gồm `test_smoke.py`, `test_m1.py`–`test_m5.py`,
`test_khong_hardcode.py`, `test_backends.py` (và hai file Databricks, vốn bỏ qua ở local). Vì vậy trang chat hiển thị khuôn mới (dòng mở
đầu, khối số dạng danh sách) chưa được kiểm bằng AppTest trên bản cuối.

**Tiêu chí chấm của eval live:** các ca khác `ok` mà khuôn sẽ viết lại (GM06, V07, E12, H02b, B02, B03, E08, H08; GM07 dẫn số G cùng kỳ nên không qua khuôn) không có `must`
nào. `banned` của E12 là "2023", và khuôn không thêm năm này. `hand` của GM06 / V07 vẫn đọc tay được ("kỳ dự báo chỉ tới 2024-07-01",
"không có dự báo 2025"). Không thấy tiêu chí nào sẽ trượt chỉ vì chữ của khuôn.

### 9.11. Claude: sửa sau eval B6, ghi chú thước tháng, chuỗi R / G từng năm, hạn mức token — 2026-10-17 (chờ Codex kiểm)

**Quyết định của PM (2026-10-17):** làm hết các việc đang chờ:
- sửa hai đề xuất B6 (V05, V03);
- agent tự kèm ghi chú khi thước tháng xếp model khác tốt hơn model chính ("đo theo tháng thì SARIMAX chính xác hơn");
- tool chuỗi R theo năm;
- câu dặn mô hình viết lý do không kèm chữ số (đánh đổi của §9.10);
- hạn mức token.

Bản này độc lập với RV12: khuôn §9.10 không đổi. Phần sửa `question_periods` (Q3/2023, quý III) và `forecast_question_errors`
(`in_specs`) trong `evidence.py` là của một phiên Claude khác cùng ngày, ghi riêng ở `ke_hoach_ai_gd2.md` §8.

**Sửa:**
- **V05** (`evidence.validate`, vòng câu xếp hạng): bỏ cụm tên chỉ tiêu `season_peak_trough_ratio` ("tháng cao nhất so với
  tháng thấp nhất", `_METRIC_NAME_RANK`) trước khi tìm chữ xếp hạng. Chữ xếp hạng còn lại trong câu vẫn bị kiểm.
- **V03** (`contracts.ToolResult.notes`, mới): ghi chú do app in dưới câu trả lời, không gửi cho mô hình (`tool_payload` không
  đổi). `get_segment_contribution` gắn `tools.SEGMENT_NOTE` ("phân rã số học…, không chứng minh nguyên nhân").
  - `TurnResult.app_notes` gom ghi chú của các kết quả ok, bỏ trùng.
  - Trang chat in các ghi chú này.
  - Log eval ghi cột `app_notes`.
- **Ghi chú thước tháng** (`tools._month_metric_note`): áp cho dự báo G hoặc G_and_COGS theo tháng / năm / cả vùng, khi ứng viên
  đang đọc là model chính.
  - Đọc `rpt_forecast_backtest` (`role = 'candidate'`, `mape_g_thang`, grain `thang`, đủ 3 fold) và so theo model, vì G không
    phụ thuộc cách COGS.
  - Model chính không nằm trong nhóm MAPE thấp nhất thì gắn ghi chú: tên model lấy từ `MODEL_LABEL`, hai số MAPE, kèm câu
    "model chính chọn theo điểm ngày kết hợp".
  - Không viết sẵn tên model; không đổi luật chọn, ứng viên hay thước.
- **Chuỗi từng năm:** `get_revenue_summary` nhận thêm `to_year` (> `year`) và đọc `rpt_revenue_yearly`, không thêm relation nào.
  - Thiếu năm thì trả `query_error`.
  - `derived.highest_r` / `lowest_r` (và cặp `_g`) xếp trên các năm đủ tháng; `.years` là chuỗi năm.
  - Catalog mở `('get_revenue_summary', R / G, 'years')`, và `_capability_key` thêm `'years'` khi có `to_year`.
  - `charts.py`: `get_revenue_summary` vẽ thành đường theo năm; năm thiếu tháng (`is_analysis_period = false`) không vẽ và được
    ghi ở chú thích.
  - `evidence._resolve`: `rows[<năm>]` chọn đúng dòng năm đó khi chỉ một dòng có năm ấy. Cách chọn này có từ live bộ N, vì
    mô hình viết `rows[2016]`. Kết quả nhiều dòng cùng năm (R theo nhóm) vẫn báo lỗi như cũ.
  - Lời báo lỗi câu xếp hạng nêu thêm `highest_r` / `lowest_r`; lời của tool ghi `.years` là năm.
- **Prompt `b6-2026-10-17b`:**
  - quy tắc 5 thêm một câu: khác ok mà dẫn số kỳ khác thì câu lý do không ghi năm, ngày hay chữ số;
  - quy tắc 17: R / G từng năm gọi một lần `year + to_year`;
  - quy tắc 16 rút chữ trùng với nhãn app.
  - Bản `b6-2026-10-17` (không có hậu tố b) còn bỏ câu "điểm của model thắng là lạc quan". Live GM11–GM14 sau đó 0/4 câu còn
    nói ý này (lần chạy 16/10: 4/4), nên bản b trả câu này lại.
- **Hạn mức token:** giữ 200.000 / phiên (PM chốt 2026-10-05). `MAX_OUTPUT_TOKENS` hạ từ 2048 xuống 1536: trong 1.277 lượt live
  05–17/10, cả một lượt (nhiều lần gọi) ra tối đa 1.116 token. Trường hợp xấu nhất 3 câu nay dùng 198.453, còn dư 1.547; trước
  lượt này dư 371. Có test khóa phần dư ≥ 1.000.
- Tool `v1.7`, catalog `b6-2026-10-17`.

**Kiểm** (local DuckDB, bản `fc14b8a2f5a24ff99a434d7c`):
- Test mới `test_ai_chuoi_nam_ghi_chu.py`, 36 test:
  - chuỗi năm khớp CSV qua đối chứng độc lập của `test_ai_tools` (R theo payments, G theo `sales.csv`, xếp hạng tính lại);
  - so năm trước bằng các lần gọi một năm; từ chối; cổng catalog;
  - biểu đồ bằng số CSV; câu dẫn số giữa khoảng / sai năm; `rows[<năm>]`;
  - 4 câu V05 live nguyên chữ nay qua, 3 câu xếp hạng thật vẫn bị chặn;
  - ghi chú đóng góp nhóm không gửi mô hình, AppTest in ghi chú;
  - ghi chú thước tháng đối chứng với parquet backtest của stage; không có ghi chú theo ngày, theo COGS, model nêu đích danh, hay
    khi model chính cũng thấp nhất;
  - phần dư token.
- `test_ai_charts.py`: đổi một ca từ chối cũ. Ca này lấy `get_revenue_summary` hai dòng làm ví dụ "không vẽ được", nay vẽ được,
  nên đổi sang `get_revenue_gap`; ý của ca giữ nguyên.
- Thử phá 8 kiểu, mỗi kiểu đều làm test trượt (1–4 test):
  - tắt bỏ tên chỉ tiêu;
  - bỏ ghi chú nhóm;
  - ghi chú tháng luôn rỗng;
  - chọn model cao nhất;
  - vẽ cả năm thiếu tháng;
  - xếp hạng gồm 2012;
  - bỏ `'years'` khỏi khóa năng lực;
  - tắt chọn dòng theo năm.
- Hồi quy §8 cộng file mới: 672 passed (bản cuối). Toàn bộ test app: 844 passed, 110 skipped (Databricks), 0 failed, chạy trước
  hai sửa cuối (`rows[<năm>]`, lời của tool); sau hai sửa đó chạy lại hồi quy và `test_smoke` + `test_m5` (AppTest trang chat): 53 passed.
- Probe RV12 `claude_rv12e_probe.py` (mã băm không đổi): 231/231.
- Phát lại 1.246 câu live: status không đổi so với §9.10.
- Phát lại thêm 31 câu live từng bị chặn (`answer_validation_failed` có `raw_final`): 21 câu nay hiện. Tắt riêng phần sửa V05 thì
  còn 17, tức phần sửa này chỉ mở thêm đúng 4 câu V05. 17 câu kia đã được mở bởi các lượt sửa trước (GM10–GM14, D11, F08–F09, khuôn
  RV12…). Chạy lại trên bản cuối, gồm thêm câu N02 bị chặn hôm nay: 32 câu, vẫn 21 câu hiện. Câu N02 vẫn bị chặn, và chặn đúng:
  câu "năm có R cao nhất là…" trỏ `rows[2016]` chứ không trỏ `derived.highest_r`. Lần chạy lại N02 đạt nhờ lời của tool.
- Script Codex: 4 exit 0; `review_ai_nonok_period`, `review_rv12b`, `review_rv12c` exit 1 như §9.10 (tiêu chí cũ "phải chặn").
  Kết quả không đổi do lượt này.

**Live** (`deepseek-flash`; ước tổng 0,50 USD):

| Bộ | Lượt | Chấm máy | Đọc tay |
|---|---|---|---|
| GM (`1176eaf10ab546c0`, đã dùng) | 15 | 15/15 | 11/15 với prompt `b6-2026-10-17`: GM11–GM14 thiếu "lạc quan". Sửa prompt (bản b), chạy lại GM11–GM14: 4/4 |
| V (`025154a0c0baaa81`, đã dùng) | 14 | 12/14 | V03 2/2 (câu văn và ghi chú app), V05 2/2. V06 0/2 theo tiêu chí khóa ngày 16/10 (chỉ nhận biểu đồ giai đoạn); nay chat vẽ R 10 năm bằng tool mới, số đúng: lệch tiêu chí có chủ ý, không sửa tiêu chí |
| PS B02, B03, E08, E12, H02b, H08 (đã dùng) | 18 | 16/18 | 18/18 lượt giữ câu lý do; không lượt nào dẫn số kỳ khác nên không đi qua khuôn. H08 2/3 lượt trả `no_data`, vì mô hình truyền `group="miền Tây"` (cũng có ở log 05/10), dù câu vẫn nói quý chưa hỗ trợ |
| N (`9e3f522b350f2947`, chốt trước lượt gọi đầu, [b6](ai_eval_b6_bieu_do.md) §5.1) | 5 | 4/5 | N02 bị chặn (`rows[2016]` / `.years[0]`), N01 viết "năm có G cao nhất là {số tiền}". Sau khi sửa `rows[<năm>]` và lời tool, chạy lại N01–N02: 2/2. N03–N05 đạt; N04 có ghi chú thước tháng, N05 có ghi chú nhóm |

Ghi chú: 6 câu PS ở bảng trên chính là "16 câu" của §9.10, vì 16 là số câu trả lời khác nhau của 6 câu hỏi này.

**Giới hạn / đề nghị Codex soi:**
- Ghi chú thước tháng hiện dưới **mọi** câu trả lời dự báo G theo tháng / năm, kể cả `unsupported` có kèm số G thay thế (GM07).
  Có thể thấy lặp nếu hỏi nhiều câu liền.
- `rows[<năm>]` là đường chọn dòng mới trong `_resolve`; cần soi các tool một dòng có cột `year` (tháng, dự báo). Ở các tool
  này `rows[<năm>]` ra đúng dòng đó, như `rows[0]`.
- **Khuôn RV12 lượt 5 (§9.10) vẫn chưa có lượt live nào đi qua.** Hôm nay có 21 lượt khác `ok` không bị chặn, và không lượt nào dẫn
  số của kỳ khác. Chỉ hai lượt có số: GM07 đưa G cùng tháng 5/2023 (khác chỉ tiêu), B03 đưa R toàn công ty cùng tháng 12/2021 (khác
  nhóm). Các lượt còn lại chỉ đề nghị. Vì vậy "18/18 giữ câu lý do" ở bộ PS chưa chứng minh câu dặn mới của quy tắc 5 có tác dụng.
  Trên 6 câu này, AI hôm nay không dẫn số kỳ khác, nên khối "Số tham khảo" không hiện. Chưa rõ đó là nhờ prompt mới hay do ngẫu nhiên.
- GM14 in "Hai thước xếp hạng khác nhau ở đây (**có**)" (ô `rankings_differ` kiểu bool): lời hơi lủng củng, chưa sửa.
- H08 "miền Tây": tool nhận tên vùng tiếng Anh; đề xuất tool nhận "miền Tây / Đông / Trung" (chưa làm, cần PM).
- Bộ N chạy 1 lần, chưa phải nghiệm thu B7.

**Hash bản cuối (SHA-256):** `evidence.py` `57d7115cddd978be513c93e9e9528e9eef1ee4fc1e3e180fa1f6ef07c36a225f` (gồm cả phần sửa của phiên
Claude khác); `service.py` `0440ae76a6b4731aa3cf353b5f7fadb36555e519642e0dcac31b9c0507673d50`; `tools.py`
`e52ad1c0a96f31ef1104b52e8b2f25b2d87dc4918c7f7c0a6f6063d15ff9dff1`; `charts.py` `f3b03aa00e72712b129ff2615c59507e0076f26cddea406c8b919ed0a1b7b4cb`;
`contracts.py` `c60224f8e7ea638d92aaf943adf0435c6836b7a39bd1c3e47ffd5836bb40cba4`; `metric_catalog.py`
`a9a61523f2b4f78d72a5cc92e2c06da3925029a6ae298b4fe3531084b82f5127`; `views/ai_explain.py`
`eb1ffdd38daefd39d83d30627389536b6dd2527c80e257053238b5ad8380346b`; `test_ai_chuoi_nam_ghi_chu.py`
`24e0fdbcdd4ae3baada344b1637e07a3d9fe089370c1357abe91eda86015da7a`. Bản lượt 5 trước khi sửa lưu ở
`warehouse/reviews/ai_gd2_20261015/truoc_luot6/`.

**Commit:** theo yêu cầu PM, code commit từng file (50 commit, `9f54cab` → `153630d` trên `app/myuyen`), gồm cả code RV01–RV12 và
B2b / B3 / B6 chưa commit từ 2026-10-15. Code đã commit nhưng chưa được Codex kiểm (§9.10, §9.11).
