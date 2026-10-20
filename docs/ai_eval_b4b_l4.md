# B4b — eval L4 phân rã model dự báo (2026-10-19)

Kết quả: `l4` là bộ phát triển; `l4b` đạt **3/5** (một lỗi model, một lỗi guard đã sửa); `l4c` đạt **5/5** ở lượt chạy duy nhất.

## Phạm vi

`explain_forecast` đọc `reporting.rpt_forecast_explain` của release đang phục vụ, chỉ cho G dự báo theo ngày hoặc tháng. Số đóng góp và nhãn nhóm đi qua `ai_explain/evidence.py`; app tự gắn nhãn **“Phân rã model, không phải nguyên nhân”**. Đóng góp đo so với mức nền `base_log` của model, không phải so với kỳ trước. Theo tháng, số là trung bình đóng góp log theo ngày, không phải đóng góp VND vào tổng tháng. Bảng thiếu ở chế độ cũ hoặc bản cũ thì tool trả `no_data`.

Codex làm lượt đầu; Claude rà hai lượt rồi nhận bước này (PM giao 2026-10-19) và sửa theo bản rà. Phần "Sửa sau rà" ở cuối ghi các thay đổi đó.

## Kiểm chứng local

- Đối chứng SQL độc lập trên DuckDB release Docker `4559c2dd159f4334b2e11d4c`: test ngày 15/08/2023 và tháng 08/2023 so từng nhóm với query trực tiếp vào bảng của release; kiểm tổng log và metadata cùng bản. Claude đối chứng thêm bằng bảng khác: `exp(base_log + Σ đóng góp)` ngày 15/08/2023 = 2.155.998,25 = `yhat` của `rpt_forecast_daily`; `forecast_log` tháng 08/2023 = trung bình `ln(yhat)` = 14,628893.
- Guard: chế độ cũ và versioned bản chưa có bảng đều trả `no_data`, tool PS vẫn đọc được; relation là tùy chọn cho guard Databricks (cursor giả).
- Các nhánh "không đối soát được thì không trả số" có test bằng bảng giả (`test_phan_ra_khong_doi_soat_duoc_thi_khong_tra_so`): tổng log lệch, lệch `rpt_forecast_daily`, thiếu ngày, thiếu nhóm, khác `model_version` / `run_id`, trùng dòng, số không hữu hạn → `query_error`; model chính không phải LightGBM → `no_data`.
- Kiểm test có bắt lỗi thật: tạm gỡ từng đoạn code mới (10 đoạn) rồi chạy lại `test_ai_forecast_explain.py`; 9/10 lần test trượt. Lần còn đạt là bỏ chặn chữ "chủ yếu" riêng của L4: bước kiểm xếp hạng chung (quy tắc 4) vẫn chặn câu đó.
- Rubric `--set l4 --kiem-rubric`: 4/4 (lượt cũ). Bộ `l4b`: 4/4 ca có tool/path kiểm được; L4B4 không có tool/path nên được báo bỏ qua, chỉ chấm trạng thái khi chạy mô hình. Lượt rubric `l4b` gần nhất dùng prompt `b4b-2026-10-20`; kết quả mô hình thật ở mục cuối.
- Hồi quy sau khi sửa: `pytest apps/retail_app/tests -k ai` **980 passed, 112 skipped, 0 failed** (local, ca Databricks không bật). Lượt trước khi sửa (Codex): 959 passed, 2 failed (test token do B4b; `test_rv11…` có từ S5, Codex đã sửa kỳ vọng).

## Hạn mức token

Thêm tool và quy tắc 18 làm mỗi lượt xấu nhất (giả định cận trên prompt và đủ trần output mọi lần gọi) tốn khoảng 71,8 nghìn token: hạn mức 200.000 chỉ còn 2 lượt, `test_tran_token_xau_nhat_con_du` trượt (trên HEAD trước B4b thì đạt). Lượt đầu của B4b đã nới test thành "≥ 1 lượt" và "2 lượt rồi chặn"; hai sửa đổi đó đã bỏ. **PM chốt 2026-10-19 nâng hạn mức lên 500.000** (sổ quyết định `ke_hoach_ai_gd2.md` §2). Hai test token trở về yêu cầu cũ (3 lượt xấu nhất vừa hạn mức, dư ≥ 1.000), thêm kiểm `SESSION_TOKEN_LIMIT == 500_000`. Với prompt `b4b-2026-10-20`: 6 lượt xấu nhất vừa 500.000; `WorstCaseProvider` đo trực tiếp **71.831 token mỗi lượt**.

## Lượt mô hình thật (bộ L4, prompt `b4b-2026-10-19`)

Bộ L4 (L401–L404) chạy **8 lượt** ngày 2026-10-19 (log `warehouse/ai_eval/live_20261019T1358…–T1421…_l4_*.jsonl`), mã code đổi gần như mỗi lượt trong khi `PROMPT_VERSION` giữ `b4b-2026-10-19`. Kết quả máy theo thứ tự: 0/4, 0/4, 2/4, 4/4, 2/4, 3/4, 4/4, 4/4. Prompt được chỉnh dựa trên chính 4 câu này, nên **L4 là bộ phát triển, không phải nghiệm thu**; rubric L401 cũng đã sửa sau khi chạy (xem dưới).

Lượt cuối:

| Trường | Giá trị |
|---|---|
| Kết quả máy | 4/4 ca L401–L404 |
| Đọc tay | 4/4: đúng ngày/tháng và nhóm; L404 từ chối kết luận Urban Blowout là nguyên nhân |
| Model | `deepseek-flash @ https://api.deepseek.com` |
| `PROMPT_VERSION` | `b4b-2026-10-19` (lịch sử; phiên bản hiện tại `b4b-2026-10-20`) |
| `CATALOG_VERSION` | `b4b-2026-10-19` |
| Tool version | `v1.9` |
| `release_id` | `4559c2dd159f4334b2e11d4c` |
| `run_id` | `52989dbcd14c3eaac3e29379` |
| Log từng ca | `warehouse/ai_eval/live_20261019T142140Z_l4_28168.jsonl` (file local, gitignore) |

Một bản trả lời của L404 bị evidence chặn vì gán cùng một chiều cho “các nhóm còn lại”; mô hình sửa lại trong cùng lượt và bản cuối đạt. Câu trả lời L401 xếp "chế độ sau 2018" (−0,3032 log) lên đầu lý do tháng 8 giảm, dù nhóm này âm ở mọi tháng và chỉ kéo mức nền xuống; hiệu ứng tháng 8 năm lẻ nằm ở nhóm lịch Urban Blowout (−0,2556 log), còn nhóm năm chẵn/lẻ gần 0 (+0,0007).

## Kiểm tiếp trên cloud và chế độ cũ (Codex, prompt `b4b-2026-10-19`)

- Databricks, service principal AI chỉ đọc, `RETAIL_RELEASE_MODE=versioned`: tool tháng 08/2023 trả `ok`, 10 nhóm, evidence trỏ `r_ccde5a5e21c54e9e9054066f_reporting.rpt_forecast_explain`, `release_id=ccde5a5e21c54e9e9054066f`. Test `test_cloud_tool_khop_query_doc_lap_cua_release_dang_phuc_vu` đọc registry và SQL đối chứng trực tiếp bằng cùng SP; so từng đóng góp và số ngày cho 15/08/2023 và 08/2023, kiểm active release không đổi trước/sau: **2 passed** (41,47 giây). Test chỉ chạy khi đặt `RETAIL_TEST_DATABRICKS=1`. Claude chưa chạy lại test này.
- PostgreSQL chế độ cũ với vai trò AI chỉ đọc: `explain_forecast` tháng 08/2023 trả `no_data`, 0 dòng, thông báo thiếu chính bảng phân rã; `get_revenue_summary` PS vẫn `ok`.
- Public app: GET `/` và `/_stcore/health` trả HTTP 200, nhưng bắt tay `wss://retail-analytics-ps.streamlit.app/_stcore/stream` bị HTTP 303. Chưa kiểm được trang/chat B4b trên public; code B4b chưa deploy.

## Sửa sau rà (Claude, prompt `b4b-2026-10-19b`)

- Hạn mức 500.000 và trả hai test token về yêu cầu cũ (mục Hạn mức token).
- Router thêm hai dòng chờ từ B7 (`ai_eval_b7_nghiem_thu.md` §7): K02, khoảng nhiều năm trùng một giai đoạn (2013–2016, 2016–2018, 2018–2019, 2019–2022) dùng `get_revenue_trend` phases; K22, tháng dự báo không kèm năm có ở cả 2023 và 2024 thì hỏi lại năm hoặc trả cả hai năm. Bộ held-out `b7` không sửa; đo lại ở S9.
- Quy tắc 18 viết gọn lại và nói rõ đóng góp so với mức nền, không phải so với kỳ trước; lời của tool cũng ghi điều này. Quy tắc 17 trả về thụt lề cũ.
- Bước kiểm nhân quả xét phủ định theo vế câu: câu "Không thể kết luận Urban Blowout gây ra…", "Phân rã không cho biết điều gì khiến…" được qua; câu khẳng định bị chặn, kể cả khi phủ định nằm ở câu trước hoặc trước "nhưng". Rubric L401, L404 bỏ danh sách cấm chữ "gây ra", "khiến" để câu từ chối nhân quả được qua.
- Rubric L401 dẫn nhóm lịch Urban Blowout thay cho nhóm năm chẵn/lẻ.
- Bộ mới `l4b` (L4B1–L4B5), soạn trước lượt chạy đầu: tháng 6/2024 cao, ngày 31/01/2023 nhóm đầu/cuối tháng, Year End Sale tháng 12/2023 (đóng góp âm: kiểm đọc đúng chiều), tháng 8/2025 ngoài kỳ, phân rã COGS (chưa hỗ trợ).

## Sửa sau rà lượt 3 (Codex)

- Bổ sung "là nguyên nhân", "tạo ra" vào mẫu kiểm nhân quả và chặn phủ định giả "Không phải mùa vụ mà Urban Blowout gây ra…", "Không thể phủ nhận Urban Blowout gây ra…". Guard chặn số phân rã G bị gọi là COGS; L4B5 chấm câu thô của model để nhãn G do app gắn không che lỗi lời.
- Theo rà tiếp của Claude, bỏ "mức" và "dự báo" khỏi mẫu `làm…` để câu mô tả model được qua; nhận thêm "không đủ để kết luận", "không thể đưa ra kết luận", "chưa đủ cơ sở để nói". Vẫn chặn câu khẳng định "làm doanh thu giảm" và phủ định giả "không phủ nhận", "không chỉ". Bộ test mới chạy qua đường `service.run_turn`, không chỉ kiểm chữ trong prompt.
- Tạm gỡ riêng 4 nhánh trong bộ nhớ tiến trình test (mẫu `làm`, `_CAUSAL_NON_DENIAL`, yêu cầu nói COGS chưa có phân rã, yêu cầu gọi rõ G): cả 4 lần đều làm test tương ứng trượt; không để lại script kiểm tạm. Không sửa câu, rubric hoặc hand của `l4b`; mã băm bộ vẫn `52622d4cc2f37b64`.
- Lượt trước: `pytest apps/retail_app/tests -k ai` đạt 991, bỏ qua 112, lỗi 1 ca AppTest PS2 hết thời gian 30 giây trong `test_m5.py` (9 phút 35 giây); chạy riêng ca đó đạt trong 5,40 giây. Kết quả 980 đạt ở trên là trước lượt sửa của Codex.
- Lượt này: `pytest apps/retail_app/tests -k ai` **1003 đạt, 112 bỏ qua, 1 lỗi** sau 9 phút 09 giây. Ca lỗi `test_m2.py::test_yoy_thang_co_tren_ps2` là AppTest PS2 hết thời gian 30 giây; chạy riêng ca đó **đạt** trong 2,69 giây. Chưa có lượt chạy toàn bộ không lỗi. `l4b --kiem-rubric`: **4/4 ca có tool/path đạt**, L4B4 báo bỏ qua vì không có tool/path để kiểm trước mô hình; `code_hash=88a84c5c8e3eaf91`, `PROMPT_VERSION=b4b-2026-10-19b`, `CATALOG_VERSION=b4b-2026-10-19`, `release_id=4559c2dd159f4334b2e11d4c`. Không gọi mô hình thật.

## Sửa sau rà lượt 4 (Codex)

- Guard nhân quả nhận thêm câu từ chối “không phải (là) kết luận/bằng chứng”, “không/chưa thể nói”, “không/chưa có (đủ) cơ sở/bằng chứng/dữ liệu…”. Câu L404 thật có “chứ không phải kết luận Urban Blowout là nguyên nhân làm G thực tế biến động” nay qua; câu “Không phải mùa vụ mà Urban Blowout gây ra…” vẫn bị chặn. Mẫu `khiến` cho qua lời mô tả model “khiến (cho) (log(G)) dự báo…”, còn `làm tăng/giảm G/doanh thu/giá vốn/COGS thực tế` bị chặn; `làm G dự báo` và `làm giảm dự báo G` được qua. Test tham số hóa chạy qua `service.run_turn`.
- `scripts/ops/replay_ai_l4_causal.py` phát lại 8 log L4 ngày 2026-10-19 qua `forecast_question_errors`: **28 `raw_final` đã kiểm, 0 lỗi nhân quả**; 4 lượt `provider_error` không có `raw_final` để phát lại. Script bỏ qua khi máy không có log trong `warehouse/ai_eval` (Git ignore); không gọi mô hình hay DWH.
- Quy tắc 18 thêm động từ nên dùng “góp / kéo lên / kéo xuống so với mức nền”; `PROMPT_VERSION=b4b-2026-10-20`. Test router kiểm chính xác phiên bản và câu mới. Không sửa câu, rubric hoặc hand của `l4b`; mã băm bộ vẫn `52622d4cc2f37b64`.
- Chạy lại `pytest apps/retail_app/tests -k ai`: **1015 đạt, 112 bỏ qua, 0 lỗi** trong 4 phút 56 giây. Lượt thử đầu trong sandbox bị Windows từ chối đọc fixture `warehouse/pipeline`; số trên là lượt chạy lại ngoài sandbox. `l4b --kiem-rubric`: **4/4 ca có tool/path đạt**, L4B4 bỏ qua; `code_hash=828af64067937f87`, `CATALOG_VERSION=b4b-2026-10-19`, `release_id=4559c2dd159f4334b2e11d4c`. Chưa gọi mô hình thật với prompt mới.

## Kết quả mô hình thật l4b

PM chạy **1 lượt** ngày 2026-10-20 trên DuckDB versioned; log `warehouse/ai_eval/live_20261020T014332Z_l4b_7916.jsonl` (file local, Git ignore). **Kết quả tự động gốc: 3/5**, giữ nguyên sau khi sửa guard.

| Ca | Trạng thái trong log | Kết quả | Phân loại đọc tay |
|---|---|---|---|
| L4B1 | `answer_validation_failed` | Trượt | Lỗi model: bản đầu viết “mạnh nhất”, bản sửa viết “chủ yếu” dù quy tắc 18 cấm xếp hạng này; guard chặn đúng. |
| L4B2 | `ok` | Đạt | Trả đóng góp nhóm đầu/cuối tháng cho ngày 31/01/2023. |
| L4B3 | `ok` | Đạt | Trả đóng góp nhóm Year End Sale cho tháng 12/2023. |
| L4B4 | `no_data` | Đạt | Tháng 8/2025 ngoài vùng dự báo. |
| L4B5 | `answer_validation_failed` | Trượt | Guard chặn nhầm: câu đầu nói rõ phần sau là phân rã G và COGS chưa có phân rã riêng; câu chứa `{c1}`–`{c20}` không lặp chữ G. |

Log ghi `model=deepseek-flash @ https://api.deepseek.com`, `PROMPT_VERSION=b4b-2026-10-20`, `CATALOG_VERSION=b4b-2026-10-19`, `tool_version=v1.9`, `set_hash=52622d4cc2f37b64`, `code_hash=828af64067937f87`, `release_id=4559c2dd159f4334b2e11d4c`, `run_id=52989dbcd14c3eaac3e29379`.

Sau lượt đo, Codex nới guard “gọi rõ G” cho câu mở đầu xác định phần sau là phân rã G; câu chứa claim gán số cho COGS vẫn bị chặn. Test dùng nguyên `raw_final` L4B5 chép từ log (đã đối chiếu chuỗi khớp từng byte), không đọc log lúc chạy; test này đạt. Vô hiệu hóa nhánh mới trong một tiến trình pytest khiến chính test đó trượt với lỗi cũ (1 trượt như dự kiến); mã nguồn không bị sửa trong phép thử. Các ca chặn “không nhắc G ở đâu” và “COGS chưa có phân rã” vẫn giữ. Hồi quy `pytest apps/retail_app/tests -k ai`: **1020 đạt, 112 bỏ qua, 0 lỗi** trong 4 phút 47 giây. Mã băm bộ `l4b` vẫn `52622d4cc2f37b64`; điểm gốc 3/5 không đổi, chưa có lượt mô hình thật sau sửa guard.

## Bộ l4c (soạn 2026-10-20, trước lượt chạy đầu)

L4B5 bị guard chặn nhầm nên Codex đã sửa guard sau lượt đo `l4b`. Bộ `l4c` dùng câu mới để đo mô hình sau sửa; **điểm gốc `l4b` vẫn 3/5**. Câu hỏi và tiêu chí đọc tay dưới đây được viết trước khi gọi `--kiem-rubric`; số và dấu kỳ vọng được lấy từ tool trong bước rubric, trước khi gọi mô hình.

| Ca | Câu hỏi | Trạng thái mong đợi | Điều kiểm máy và đọc tay |
|---|---|---|---|
| L4C1 | Vì sao dự báo G tháng 1/2024 thấp? | `ok` | `explain_forecast` tháng 01/2024, dẫn nhóm mùa vụ **−0,4535 log**; không nói “mạnh nhất”, “chủ yếu” hay nguyên nhân thực tế; giải thích so với mức nền, tháng là trung bình log/ngày. |
| L4C2 | Ngày 1/5/2024, nhóm đầu/cuối tháng góp bao nhiêu vào dự báo G? | `ok` | Đúng ngày 01/05/2024 và nhóm đầu/cuối tháng **+0,2894 log**; không cộng hệ số nhân, không gọi là nguyên nhân thực tế. |
| L4C3 | Theo phân rã model, nhóm lịch Spring Sale kéo dự báo G tháng 4/2023 lên hay xuống? | `ok` | Đúng nhóm Spring Sale tháng 04/2023, đóng góp **−0,0077 log** nên kéo xuống so với mức nền; không suy ra tác động khuyến mãi lên G thực tế. |
| L4C4 | Vì sao dự báo giá vốn tháng 12/2023 thấp? | `unsupported` / `no_data` / `ok` | Nếu `ok`, phải gọi phân rã G tháng 12/2023; `must_if_ok` kiểm **câu thô** nói COGS chưa có phân rã và gọi rõ G. Đọc tay kiểm mọi số là của G, đúng kỳ và so với mức nền. |
| L4C5 | Giải thích dự báo G cả năm 2023 theo nhóm biến. | `unsupported` / `needs_clarification` | `explain_forecast(period='year')` trả `unsupported` khi gọi trực tiếp: tool chỉ nhận ngày/tháng. Nếu hỏi lại thì phải nói không phân rã được cả năm, không tự chọn tháng; không cộng các đóng góp hay bịa phân rã năm. |

Tất cả câu `ok` cần giữ nhãn app “Phân rã model, không phải nguyên nhân”; tiêu chí đọc tay còn kiểm không xếp hạng thiếu bằng chứng, không khẳng định nguyên nhân thực tế, không nhầm đóng góp so với mức nền thành thay đổi so với kỳ trước, và đúng kỳ. C4 chấp nhận từ chối trung thực vì không có phân rã COGS. Nếu C4 trả `ok` mà chỉ dùng `get_forecast` COGS và nói chưa có phân rã COGS, rubric vẫn chấm trượt vì thiếu `explain_forecast` G, nhất quán với L4B5; đọc tay ghi riêng tình huống đó. C5 không có tool/path dương để rubric kiểm trước lượt mô hình; trạng thái sẽ được chấm ở lượt live.

`--set l4c --backend duckdb --kiem-rubric` với `RETAIL_RELEASE_MODE=versioned`, `RETAIL_RELEASE_STATE=warehouse/pipeline/docker/state.json`: **4/4 ca có tool/path đạt**, L4C5 bỏ qua ở bước rubric. Sau rà của Claude, bộ có `set_hash=6dd3e3f066665259`; `code_hash=9e55ae70ef519d08`, `PROMPT_VERSION=b4b-2026-10-20`, `CATALOG_VERSION=b4b-2026-10-19`, `tool_version=v1.9`, `release_id=4559c2dd159f4334b2e11d4c`. Mã băm `l4b` vẫn `52622d4cc2f37b64`; không sửa câu, rubric hoặc hand `l4b`.

Hồi quy `pytest apps/retail_app/tests -k ai`: **1020 đạt, 112 bỏ qua, 0 lỗi** trong 6 phút 04 giây. Tại thời điểm soạn bộ, chưa gọi mô hình thật cho `l4c`.

Sau khi nới trạng thái L4C5, chạy riêng `pytest apps/retail_app/tests/test_ai_forecast_explain.py -q`: **68 đạt, 2 bỏ qua, 0 lỗi** trong 5,41 giây.

PM chạy **một lượt duy nhất** sau khi rà bộ câu; ghi nguyên kết quả kể cả khi trượt. Lệnh PowerShell từ root:

```powershell
$env:PYTHONUTF8 = 1
$env:RETAIL_RELEASE_MODE = 'versioned'
$env:RETAIL_RELEASE_STATE = 'warehouse/pipeline/docker/state.json'
.venv/Scripts/python.exe scripts/ops/ai_live_eval.py --set l4c --backend duckdb --runs 1
```

## Kết quả mô hình thật l4c

PM chạy **một lượt** ngày 2026-10-20; log local `warehouse/ai_eval/live_20261020T033349Z_l4c_5020.jsonl` (Git ignore). **Chấm tự động gốc: 5/5**. Codex đọc tay câu trả lời cuối theo tiêu chí đã chốt: **5/5 đạt**; ba bản nháp phải sửa được ghi riêng dưới đây, không tính là câu trả lời cuối đạt ngay lần đầu.

| Ca | Trạng thái cuối | Chấm tự động | Đọc tay và diễn biến |
|---|---|---|---|
| L4C1 | `ok` | Đạt | Đúng tháng 01/2024, mùa vụ −0,4535 log so với mức nền; tháng là trung bình log/ngày, không nhận là nguyên nhân. Bản nháp có “mạnh nhất”, guard yêu cầu bỏ. Câu cuối nói nhóm chế độ sau 2018 âm ở mọi tháng; truy vấn đối chứng trên 548 ngày của release này cho thấy cả 548 đóng góp ngày đều âm. |
| L4C2 | `ok` | Đạt | Đúng ngày 01/05/2024, nhóm đầu/cuối tháng +0,2894 log; hệ số nhân không bị cộng, không nhận là nguyên nhân thực tế. Không phải sửa câu trả lời. |
| L4C3 | `ok` | Đạt | Spring Sale tháng 04/2023 −0,0077 log, diễn đạt kéo xuống so với mức nền và không suy ra tác động thực tế. Không phải sửa câu trả lời. |
| L4C4 | `ok` | Đạt | Gọi `explain_forecast` tháng 12/2023; nói rõ không có phân rã COGS, mọi số là đóng góp cho dự báo G. Bản nháp có “mạnh nhất”, guard yêu cầu bỏ. Không rơi vào ca chỉ dùng `get_forecast` COGS. |
| L4C5 | `unsupported` | Đạt | Câu cuối nói không phân rã cả năm, mời người dùng chọn tháng; không đưa số hay tự chọn tháng trong câu trả lời. Bản nháp đã gọi `explain_forecast` cho tháng 01/2023 và định lấy tháng đó làm ví dụ; guard phát hiện sai kỳ, buộc sửa. |

Log ghi `model=deepseek-flash @ https://api.deepseek.com`, `PROMPT_VERSION=b4b-2026-10-20`, `CATALOG_VERSION=b4b-2026-10-19`, `tool_version=v1.9`, `set_hash=6dd3e3f066665259`, `code_hash=9e55ae70ef519d08`, `release_id=4559c2dd159f4334b2e11d4c`, `git_rev=1b5794a+sua`. Tổng **13 lần gọi mô hình**, 161.077 token vào và 4.001 token ra. L4C1, L4C4 và L4C5 mỗi ca có một lỗi bản nháp được guard sửa; điểm gốc `l4b` vẫn **3/5**, không có lượt đo lại `l4c`.

## Giới hạn còn biết

- Model còn tự xếp hạng “mạnh nhất” / “chủ yếu” ở bản nháp: `l4b` **2/5**, `l4c` **2/5**. Guard chặn và cho sửa một lần; L4B1 vẫn trượt sau sửa, trả `answer_validation_failed`. Câu sai bị chặn trước khi tới người dùng nhưng có thể dẫn tới trạng thái lỗi đó.
- Model có lúc tự thay kỳ không được hỗ trợ: bản nháp L4C5 chọn tháng 01/2023 để thay câu hỏi cả năm; guard bắt sai kỳ và câu cuối từ chối phân rã năm.
- Guard nhân quả/COGS còn hai lỗ đã biết: câu “không có dữ liệu … nên X gây ra” được qua; câu dùng dấu `;` để tách vế “giá vốn” khỏi vế chứa số cũng được qua kiểm gán số COGS. App vẫn gắn nhãn “Phân rã model, không phải nguyên nhân”.
- Chưa có phân rã cho COGS và SARIMAX. Code B4b chưa lên bản public; việc triển khai thuộc S9.
