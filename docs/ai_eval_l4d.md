# S9b — Câu trả lời L4 gọn cho người đọc nghiệp vụ (`l4d`)

**Trạng thái 2026-10-21:** đã chạy đúng một lượt model thật trên release DuckDB local `4559c2dd159f4334b2e11d4c` sau lượt vá chữ cuối. Giữ nguyên câu và rubric `l4d`; kết quả ở phần dưới. Chưa lên public/Databricks, chưa commit; không đụng `deploy/`, dbt hoặc dữ liệu `rpt_forecast_explain`.

## Hợp đồng trình bày hiện hành

`explain_forecast` vẫn đọc cùng release, đối soát 10 nhóm và tính `pct_vs_base = (exp(contribution_log) − 1) × 100`. `rank` xếp theo độ lớn tuyệt đối của đóng góp log trên tất cả nhóm; `rank_dir` xếp trong từng chiều âm/dương. Cùng độ lớn thì hòa theo `feature_label`, rồi `feature_group`. Bảng giả ngày 01/05/2024 có mùa vụ `+84,4%`, chế độ sau 2018 `−30,9%`, đầu/cuối tháng `+33,6%`, lịch Urban Blowout `+1,46%`; sáu nhóm còn lại có độ lớn dưới `1%`, lớn nhất `0,846%`. Đây là số từ bảng giả để thử guard, không phải kết quả release thật.

Khi hỏi “vì sao cao/thấp”, prompt cho tối đa ba nhóm có số. Câu có “chủ yếu/mạnh nhất/lớn nhất” và nêu chiều phải dẫn đúng top-k theo `rank_dir` của chiều ấy; không nêu chiều thì đối chiếu `rank`. Không cho một câu xếp hạng vừa kéo lên vừa kéo xuống. Mỗi `%` là tác động khi xét riêng một nhóm so với mức nền; các hệ số nhân với nhau, không cộng các `%`. Câu phủ định việc cộng được giữ nguyên nghĩa.

`derived.small_groups` có `n`, `threshold_pct = 1.0`, `max_abs_pct`. Cách nói ngắn là “{n} nhóm có ảnh hưởng dưới {threshold_pct} mỗi nhóm”. “Dưới” phải trỏ vào ngưỡng, không trỏ vào giá trị lớn nhất rồi làm tròn thành `0,8%` khi thực tế có nhóm `0,846%`. `max_abs_pct` chỉ dùng với “tối đa”, “không quá” hoặc “lớn nhất trong đó”; app in ba chữ số thập phân để bảng giả hiện `0,846%`. Chỉ nói “còn lại” hoặc “nhóm khác” khi các nhóm đã dẫn số trong câu trả lời bao phủ mọi nhóm có `|pct_vs_base| ≥ threshold_pct`; nếu thiếu thì dùng cách nói ngắn ở trên. Guard nhận ra cả câu có dấu phẩy giữa “nhóm còn lại/khác” và “mỗi nhóm dưới”. Các câu liệt kê tên và số từng nhóm vẫn được kiểm và được qua khi đủ nhóm lớn.

Lượt 4 kiểm thêm vế không có chỗ đặt số như “các nhóm/yếu tố/biến/thành phần khác/còn lại”. Guard đối chiếu các nhóm lớn đã dẫn số trên toàn câu trả lời, dùng cùng logic với câu có chỗ đặt; có hơn một kết quả `explain_forecast` thì chặn vì không xác định được nguồn của vế. Câu không thuộc phân rã (“các kỳ khác”, “model khác”) và câu từ chối nhân quả không bị bắt nhầm trong test.

App chỉ bỏ ngoặc sau số phân rã khi vế câu nêu đúng `feature_label`, có “mức nền” và câu trả lời có đúng kỳ. Nếu vế đã nói “so với mức nền” mà còn cần nhãn, nhãn chỉ là `(<kỳ>)`; trường hợp khác là `(so với mức nền, <kỳ>)`. Nhãn “Phân rã model, không phải nguyên nhân”, guard nhân quả, COGS và kỳ tiếp tục áp dụng. Nhóm chế độ sau 2018 tác động lên mức nền ở mọi tháng, không riêng tháng được hỏi.

## Bộ `l4d` đã chốt trước lượt model

L4D1 vẫn hỏi tháng 08/2023 thấp, tối đa ba nhóm có số và 700 ký tự; hai path bắt buộc là `%` của lịch Urban Blowout và chế độ sau 2018. `small_groups` là tùy chọn trong prompt, đã bỏ hai path nhóm nhỏ khỏi rubric bắt buộc. L4D2 vẫn hỏi ngày 01/05/2024 cao; test `FakeProvider` chứng minh câu dùng top hai nhóm dương và cách nói “nhóm có ảnh hưởng dưới ngưỡng” đạt rubric L4D2. L4D3 hỏi đủ 10 nhóm; L4D4–L4D5 là bẫy cộng `%` và nhân quả thực tế. Không sửa các bộ đã chạy `l4`, `l4b`, `l4c`, `rag`, `b7`.

set_hash 91dc665bee6ba872: thay thế trước lượt model, chưa từng chạy.

**Bộ đã chạy:** `set_hash=274256c85faab608`, `code_hash=614e7310d6f06fd2`, `TOOL_VERSION=v2.2`, `PROMPT_VERSION=b5b-2026-10-20`, catalog `b5b-2026-10-20b`. Lịch sử trước lượt model: B5b lượt 3 `code_hash=7377229e5c35cb07`; B5b lượt 2 `code_hash=f918632736cadcb0`; B5b lượt 1 `code_hash=3daf9037a77e9997`, B5b bản đầu `code_hash=34526eb05944721e`; sau vá chữ lượt 4 `code_hash=6fc83204a9f2bde6`; lượt 3 `code_hash=68fd11e2d6156767`; lượt 2 `code_hash=580efb753b1479eb`; lượt 1 `TOOL_VERSION=v2.1`, `PROMPT_VERSION=s9b-2026-10-20`, `code_hash=63c3bd231c728e3e`. Phiên bản prompt S9b trước B5b là `s9b-2026-10-20b`.

B5b lượt 3 chỉ sửa guard định nghĩa và bộ `b5b_paraphrase` chưa chạy (`set_hash=102639f13ed4a1b0`). **Câu/rubric `l4d` giữ nguyên**; `set_hash=274256c85faab608`. Bốn file test AI: **267 đạt, 2 bỏ qua**. Phát lại đúng release `4559c2dd159f4334b2e11d4c`: không ca nào bị guard định nghĩa mới chặn; bốn ca `l4` cũ từng `ok` bị guard phân rã chặn như trước. Xem [báo cáo B5b lượt 3](ai_eval_b5_rag.md#b5b-lượt-3--câu-hỏi-số-câu-nối-tiếp-và-phát-lại-đủ-trạng-thái) và [bảng phát lại đầy đủ](ai_eval_b5b3_replay.csv).

B5b lượt 4 là lượt sửa code cuối: guard câu nối tiếp chỉ kế thừa mã khi có từ chỉ chỉ số và không ép định nghĩa nếu đang hỏi số. **Không đổi câu/rubric `l4d`** (`set_hash=274256c85faab608`) hay `b5b_paraphrase` (`set_hash=102639f13ed4a1b0`); `code_hash=614e7310d6f06fd2`. Bốn file test AI: **274 đạt, 2 bỏ qua**. Xem [báo cáo B5b lượt 4](ai_eval_b5_rag.md#b5b-lượt-4--vá-câu-nối-tiếp-cuối).

B5b lượt 2 chỉ sửa guard định nghĩa, alias và nguồn AOV; **không đổi câu/rubric `l4d`**. `set_hash` vẫn `274256c85faab608`; bốn file test AI đạt **255**, bỏ qua **2**. Phát lại `l4b/l4c` cùng release không chặn thêm ca từng `ok`; các log phát triển `l4` cũ có bốn ca bị guard L4 chặn. Xem [báo cáo B5b lượt 2](ai_eval_b5_rag.md#b5b-lượt-2--sửa-chặn-nhầm-trước-lượt-model) và [danh sách phát lại](ai_eval_b5b2_replay.md).

B5b sửa catalog AOV và guard câu hỏi định nghĩa sau khi Claude phát hiện lỗi trên app Databricks; đây là sửa định nghĩa chung, không đổi câu/rubric `l4d` hay quy tắc trình bày L4. `set_hash` giữ nguyên; mã băm code đổi vì catalog, validator, prompt và bộ eval mới. Bốn file test AI được chọn: **232 đạt, 2 bỏ qua**; phát lại hai log B5/RAG cũ: 10 `raw_final`, không ca từng `ok` nào bị chặn. Xem [báo cáo B5/RAG](ai_eval_b5_rag.md) để biết giới hạn và bằng chứng riêng của B5b.

Kiểm lại lượt 3 với đủ ba test riêng cho “nhóm khác” thiếu nhóm lớn, “nhóm khác” đã nêu đủ nhóm lớn và “nhóm có ảnh hưởng dưới” ở ngày: `set_hash` giữ `274256c85faab608`; mã băm code lúc đó vẫn là `68fd11e2d6156767` vì test bổ sung không thuộc tập file tính mã băm code.

## Kiểm chứng dev

Bảng này lưu kết quả các lượt S9b và B5b trước lượt 2; số test và mã băm code hiện hành đã cập nhật ở trên.

| Việc | Kết quả |
|---|---|
| Bốn file `test_ai_forecast_explain.py`, `test_ai_chat.py`, `test_ai_router.py`, `test_ai_knowledge.py` | **232 đạt, 2 bỏ qua** sau B5b (cloud opt-in); chỉ chạy bốn file này |
| Bảng giả `FakeProvider` tháng 08/2023 và ngày 01/05/2024 | Câu đúng đạt; câu có dấu phẩy, ngưỡng sai, “còn lại/nhóm khác” thiếu nhóm lớn, xếp hạng sai chiều và tổng `%` bị chặn; câu tháng 08/2023 dẫn đủ ba nhóm lớn rồi nói “nhóm khác” đạt; câu ngày dùng “nhóm có ảnh hưởng dưới” đạt; câu phủ định phép cộng và nhãn hiển thị chính xác đạt |
| Gỡ thử năm guard, chạy test mục tiêu, khôi phục từng byte | Năm lần test mục tiêu đều trượt: nhóm nhỏ có dấu phẩy, ngưỡng, “còn lại” đủ nhóm, `rank_dir`, ngoại lệ phủ định. SHA-256 của `evidence.py` sau mỗi lần khôi phục bằng bản trước thử (`fd366c7dc658f9c8703328910066d27d6f96431dd87b23daf07c35ca8f1a1057`) |
| Gỡ thử guard “nhóm khác” lượt 3, chạy test chặn, khôi phục từng byte | Test chặn trượt đúng kỳ vọng; SHA-256 của `evidence.py` trước và sau khôi phục đều là `937a867181a453512caf6ba0764ee54cdf9d125a1a8d7d5e2ae50b79d7e808ae` |
| Gỡ thử nhánh vế “khác/còn lại” không số lượt 4, chạy ba ca chặn, khôi phục từng byte | **3 trượt** đúng kỳ vọng vì cả ba câu lại ra `ok`; SHA-256 của `evidence.py` trước và sau khôi phục đều là `9671c741e21287a6df5fb5e35114a2de5fb5a7050281eaeb81a296df5b74dc5c` |
| Phát lại `raw_final` từ log `l4b/l4c` bằng validator lượt 4 trên cùng release | 10 ca; **0 ca từng `ok` nay bị chặn**. L4B1 vẫn có lỗi xếp hạng, L4B5 `raw_final` cuối qua kiểm, các ca khác giữ trạng thái. Đây là phát lại local, không phải lượt model mới |
| `--set l4d --kiem-rubric` trên release trên | **3/3** ca có tool/path đạt; L4D4–L4D5 không có tool/path bắt buộc nên chưa được rubric kiểm |

Lệnh rubric: đặt `RETAIL_RELEASE_MODE=versioned`, `RETAIL_RELEASE_STATE=warehouse/pipeline/docker/state.json`, `PYTHONIOENCODING=utf-8`; chạy `.venv/Scripts/python.exe scripts/ops/ai_live_eval.py --set l4d --kiem-rubric`.

Rubric trước model chỉ kiểm tool/path của ba ca đầu. Một lượt model thật đã chạy sau khi Claude rà; log, điểm và nhận xét đọc tay nằm dưới đây. Chưa có bằng chứng câu trả lời ngắn trên public hay Databricks. Giới hạn phân rã COGS/SARIMAX và các lỗ guard đã ghi trong [báo cáo B4b](ai_eval_b4b_l4.md) vẫn cần theo dõi.

## Kết quả model thật — một lượt 2026-10-21

[Log `live_20261021T000620Z_l4d_11304.jsonl`](../warehouse/ai_eval/live_20261021T000620Z_l4d_11304.jsonl): **4/5 chấm máy**; `code_hash=614e7310d6f06fd2`, `set_hash=274256c85faab608`, release `4559c2dd159f4334b2e11d4c`. Đây là lượt model thật duy nhất của bộ `l4d`; giữ nguyên log và điểm, không chạy lại.

Claude đọc tay: **L4D1, L4D2, L4D5 tốt**. **L4D4 đạt máy** nhưng viết “Rural Special kéo xuống 0,0%” rồi lại tính nhóm đó trong “7 nhóm dưới 1%”, gây đếm trùng trong cách trình bày. **L4D3 trượt `du_10_nhom`**: câu hỏi yêu cầu “theo từng nhóm” nhưng câu trả lời vẫn rút gọn thành ba nhóm có số và một dòng gộp bảy nhóm nhỏ, chưa trình bày đủ 10 nhóm riêng.

**Giới hạn sau lượt model:** L4D3 chưa đáp ứng yêu cầu liệt kê từng nhóm; L4D4 có lỗi diễn đạt nhóm nhỏ dù rubric máy cho qua. Theo quyết định của PM rằng lượt 4 là lượt sửa code cuối, ghi nhận hai lỗi này và không vá thêm code hay bộ câu sau khi xem kết quả. Prompt mục 18 đã có dòng “Chỉ khi hỏi ‘theo nhóm biến’/‘từng nhóm’ mới nêu đủ các nhóm”; L4D3 trượt vì model không làm theo dòng này, không phải prompt thiếu quy tắc. PM chốt ngày 2026-10-21 giữ L4D3 là giới hạn: câu hỏi nghiệp vụ “vì sao cao/thấp” (L4D1/L4D2) đạt, bảy nhóm bị gộp đều dưới 1% mỗi nhóm.
