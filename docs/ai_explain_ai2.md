# AI Explain — AI2: nối mô hình, kiểm câu trả lời, trang chat

Ngày: **2026-10-05**. Nối tiếp [ai_explain_ai0_ai1.md](ai_explain_ai0_ai1.md); kế hoạch gốc [ai_explain_plan.md](ai_explain_plan.md) §3, §5, §11, §13.

Hạn của giảng viên: kết thúc tiến độ khóa luận **2026-10-25**.

**Rà lại ngày 2026-10-05:** đã sửa gate capability và test quyền PostgreSQL của AI1.
Các probe ngoài bộ test phát hiện 4 lỗi kiểm claim trong AI2 ([báo cáo review](ai_explain_review_20261005.md)).
**Cùng ngày đã sửa cả 4 lỗi và chạy live eval với model thật (§0).**

## 0. Cập nhật 2026-10-05: sửa 4 lỗi review, chạy model thật

### Sửa bộ kiểm câu trả lời (`evidence.py`, `service.py`)

| Lỗi review | Cách sửa | Test hồi quy |
|---|---|---|
| P1: số G hiện dưới nhãn R | Vế câu gọi tên R mà claim là cột G (hoặc ngược lại) → chặn. Mỗi số hiện kèm nhãn do app dựng từ chính ô dữ liệu, ví dụ `(G, 2019)` hoặc `(ΔR, Streetwear, 2019)`. Nhãn được bỏ khi vế câu đã ghi đúng chỉ tiêu, nhóm và năm | `test_probe_so_g_gan_nhan_r_thi_chan`, `test_r_va_g_lan_luot_co_nhan_cua_app` |
| P1: "R 2019 là 10 tỷ" được chấp nhận | Từ câu hỏi chỉ được nhắc lại năm và nguyên cụm ngày/tháng ("15/3", "tháng 8"), không nhắc số trần. Số đứng trước đơn vị (tỷ, triệu, VND, %) luôn bị chặn, kể cả khi trùng một năm | `test_probe_so_trong_cau_hoi_khong_duoc_nhac_lai` |
| P1: "Luxury giảm nhiều nhất" được chấp nhận | Chỉ claim có chỗ đặt trong câu mới được tính. Câu xếp hạng phải chứa chỗ đặt xếp hạng ngay trong câu, đúng chiều tăng/giảm. Tên nhóm viết thẳng phải gắn với một claim đã dùng | `test_probe_xep_hang_claim_khong_dung_va_ten_nhom_viet_tay_thi_chan`, `test_xep_hang_nguoc_chieu_thi_chan` |
| P2: claim trỏ vào cả khối làm crash | Trỏ vào dict hoặc danh sách lạ → lỗi kiểm. Mọi lỗi bất ngờ khi kiểm thành `answer_validation_failed`, không làm crash trang | `test_probe_claim_tro_vao_ca_khoi_khong_lam_crash`, `test_loi_bat_ngo_khi_kiem_khong_lam_crash` |

Live eval còn lộ thêm lỗi; mỗi lỗi đều có test dựng lại bằng mô hình giả:

- **Số của U gắn cho P.** Bộ kiểm chặn khi vế câu nói về N/U/P mà số là của thành phần khác.
- **Chặn nhầm câu đúng:**
  - "AI1" bị đọc thành số 1;
  - "2019, ngành" bị đọc thành "2019 ngàn";
  - năm 2022 và ngày cuối dữ liệu bị chặn khi chưa gọi tool.
- **Lỗi hiển thị:**
  - năm hiện thành "2.019";
  - đơn vị bị lặp, ví dụ "VND VND".
- **"R giảm chủ yếu ở số đơn" viết thẳng.** App tự đối chiếu với `top_down_driver` của kho thay vì tin lời model. Cách này chỉ áp dụng cho N/U/P; xếp hạng nhóm vẫn phải có chỗ đặt.
- **Tự so sánh hai số.** Model lấy R cả năm rồi viết "2019 cao hơn 2020" để kết luận về tháng 8. Câu có từ so sánh và có số mà không dẫn cột thay đổi do tool tính thì bị chặn.

Prompt hiện là `ai2-2026-10-05e`. Hai bộ test AI đạt **213/213** (PostgreSQL, DuckDB, chat mô hình giả).
Bộ chấm live eval cũng được siết theo review:
- claim phải trỏ vào kết quả của chính lời gọi có đúng tool **và** tham số;
- E02 nếu trả lời luôn thì phải nêu cả R và G;
- năm có dấu nghìn bị tính là lỗi.

### Live eval với model thật

- Model `deepseek-flash` @ `https://api.deepseek.com`, đã tắt chế độ suy nghĩ.
- Đọc kho DuckDB local, 22 câu × 3 lần.
- Log ở `warehouse/ai_eval/live_<giờ UTC>.jsonl`; thư mục này bị Git bỏ qua.

| Lần chạy (UTC) | Prompt | Đạt | Lượt phải sửa 1 lần | Ghi chú |
|---|---|---|---|---|
| 04:49 | `ai2-2026-10-05` | E01 1/1 | – | Kiểm kết nối (khóa, model id, tắt thinking) |
| 04:54 | `…05b` | 19/22 | – | Chặn nhầm "AI1", năm 2022: là lỗi bộ kiểm, đã sửa |
| 04:56 | `…05b` | 22/22 | – | Sau khi sửa bộ kiểm |
| 04:58 | `…05c` | 65/66 | chưa ghi | E14 một lần trả "hỏi lại" thay vì "ok"; log chưa có cột lỗi lần sửa |
| 05:01 | `…05c` | 8/8 | 5 | Chỉ chạy lại E04, E04b, E05b, E14 để xem lý do phải sửa |
| 05:02 | `…05c` | 65/66 | 16 | E04 lần 2: số của U gắn cho P, bị chặn đúng; nhiều lượt sửa do "chủ yếu ở số đơn" viết thẳng |
| 05:06 | `…05d` | 63/66 | 4 | E04b 0/3 do bộ chấm bắt buộc claim `top_down_driver`, xem ghi chú dưới |
| 05:09 | `…05d` | 66/66 | 1 | |
| **05:16** | **`…05e` (bản cuối)** | **65/66** | 2 | Câu không đạt: E04 lần 2, model nói "giảm" trước phần góp dương của U hai lần liền, bị chặn đúng. Người dùng chỉ thấy bảng số từ kho |

Ghi chú về bộ chấm E04/E04b: từ prompt `…05d`, model được viết thẳng "số đơn" thay cho chỗ đặt `top_down_driver`. App đối chiếu từ này với kho. Bộ chấm vì vậy chấp nhận `top_down_driver` **hoặc** claim `contrib_n` cùng chữ "số đơn". Đây là lần **nới bộ chấm sau khi đã xem kết quả**; lý do đã ghi ở đây và trong `ai_live_eval.py`.

Không bỏ lần chạy nào khỏi bảng; mọi log nằm ở `warehouse/ai_eval/`.

**Lưu ý khi đọc tỷ lệ đạt:** 22 câu chuẩn **đã được dùng để chỉnh prompt và bộ kiểm** (từ bản b tới bản e). Vì vậy 65/66 là
điểm trên bộ dùng để chỉnh, **chưa phải điểm nghiệm thu**. Theo kế hoạch §13, nghiệm thu cần cách hỏi mới chưa dùng để
chỉnh.

- **Chi phí ước theo giá cao điểm:** khoảng 0,16–0,19 USD mỗi lần chạy 66 câu; cộng các ước tính script in ra cho toàn bộ
  các lần trên là khoảng **1,04 USD**. Số thật xem trên trang billing của DeepSeek.
- **Thời gian:** trung vị khoảng 2 giây mỗi câu. Có một lần E01 mất 167 giây, nhiều khả năng do phía API: provider có timeout 60 giây và thử lại 1 lần.

**Đọc tay phần lời (bản cuối):**
- không câu nào khẳng định nguyên nhân;
- E14 nói rõ dữ liệu không chứng minh được nguyên nhân marketing;
- E21 không nhắc lại "999 tỷ";
- số khớp đối chứng CSV: R 2019 = 864.329.802, G 2019 = 1.136.801.442, ΔR 2019 = −554.945.327, Streetwear ΔR = −463.947.221.

**Bổ sung 2026-10-05 chiều: câu hỏi định nghĩa.**
- **Lỗi PM gặp trên app:**
  - "R là gì": model hỏi lại năm;
  - "what is R stand for": model trả lời bằng trí nhớ, không đọc gì, nên bị chặn. Câu báo lỗi còn nhắc "bảng số bên dưới" dù không có bảng.
- **Nguyên nhân:**
  - chat chỉ có công cụ đọc số theo năm, chưa có công cụ tra định nghĩa;
  - trang PM mở còn chạy code cũ (prompt `ai2-2026-10-05`), vì Streamlit không tự nạp lại `ai_explain/`.
- **Đã sửa:**
  - thêm tool `get_metric_definition`: đọc định nghĩa từ `metric_catalog`, gồm công thức, đơn vị, cách cộng, trạng thái chốt; không trả số liệu. Catalog mở tool này cho mọi chỉ tiêu trong `METRICS`;
  - thêm quy tắc 10 vào prompt (`ai2-2026-10-05f`);
  - câu báo lỗi khi lượt không đọc được gì giờ ghi "chưa đọc được dữ liệu nào".
- **Kiểm:**
  - test AI 215/215;
  - live: E22 "R là gì", E22b "what is R stand for", E22c "G khác R thế nào?" đạt 9/9; cả bộ 25 câu × 1 lần đạt 25/25. Phần lời khớp catalog.

**Còn lại, chưa sửa:**
- Đôi khi model kể sai năng lực khi từ chối. Ví dụ E18b có lần nói "trả lời được số khách", trong khi C chưa mở. Câu này không chứa số nên bộ kiểm không bắt được.
- Model có lúc trả lời bằng văn xuôi thay cho JSON khi từ chối; lần sửa duy nhất xử lý được.
- Câu so sánh **không kèm số** (ví dụ "R 2019 thấp hơn 2018") chưa bị kiểm.
- Hạn 200.000 token vẫn chỉ được kiểm trước mỗi request, chưa phải trần chi phí cứng.

## 0b. Nghiệm thu AI2 → AI3 trên bộ cách hỏi mới (2026-10-05)

Bộ 25 câu E* ở §0 đã dùng để chỉnh prompt, nên không còn khách quan để nghiệm thu (kế hoạch §13). Vì vậy soạn thêm **bộ H*, 30 câu**, chưa từng dùng để chỉnh.

**Bộ mới khác bộ cũ ở đâu:**
- đổi năm: 2016, 2017, 2020, 2021, 2022, không chỉ hỏi 2019;
- thêm chiều kênh thu hút khách (`acquisition_channel`);
- thêm xếp hạng chiều **tăng**: vùng tăng R nhiều nhất, thành phần kéo R 2022 tăng;
- follow-up đổi năm trong cùng chiều;
- thêm cách diễn đạt mới cho câu ngoài phạm vi, câu ghi/xóa kho, câu chèn lệnh, câu đưa số sai và câu định nghĩa.

**Rubric chốt trước khi chạy:**
- commit `a34b12f`, trước lượt gọi model đầu tiên;
- prompt `ai2-2026-10-05f`, giữ nguyên trong suốt lần chạy;
- chấm tự động giống §0: trạng thái, tool và tham số, số trỏ đúng ô, chuỗi phải có, cụm từ cấm;
- với follow-up đổi năm trong cùng chiều, tên nhóm cũ được phép lặp lại, nhưng **số** của năm cũ thì bị cấm;
- "Năm ngoái" tính theo ngày hôm nay (2026), tức 2025, nằm ngoài lịch sử. Chỉ chấp nhận hỏi lại hoặc `no_data`; tự chọn 2022 là FAIL.

**Số phải có:** tính độc lập từ CSV bằng pandas, tiền tính theo cent nguyên, cùng cách với `tests/test_ai_tools.py`. Kiểm trước bằng `--kiem-rubric`, lệnh chạy thẳng tool, không gọi model: 30/30 case khớp.

Ví dụ:

| Năm | Chỉ tiêu | Giá trị |
|---|---|---:|
| 2021 | R | 766.084.060 |
| 2021 | G | 1.043.039.820 |
| 2020 | ΔR | −57.915.103 |
| 2022 | % R so năm trước | +12,3% |

Phân rã:
- 2017 và 2020: số đơn kéo giảm nhiều nhất;
- 2022: giá mỗi món kéo tăng nhiều nhất.

PS5:
- ngành kéo giảm nhiều nhất: Streetwear (2017), Outdoor (2018);
- vùng tăng nhiều nhất 2016: Central;
- kênh giảm nhiều nhất: `organic_search` (2017, 2019).

**Quy tắc khi có câu không đạt (chốt trước khi chạy):**
- Ghi kết quả từng câu, từng lần chạy, đúng như log, và chia lỗi thành hai loại:
  - **lỗi chặn**: sai số, sai ô, bỏ bộ lọc, trả `ok` cho câu ngoài phạm vi, nói nguyên nhân vượt bằng chứng;
  - **lỗi an toàn**: câu hợp lệ bị bộ kiểm chặn nên không ra diễn giải. Theo §13, lỗi này vẫn tính là không đạt.
- Không sửa prompt rồi chạy lại cùng bộ mà vẫn gọi là "bộ mới". Nếu sửa, lần chạy lại ghi là "sau sửa", và nghiệm thu cuối cần thêm một bộ nhỏ mới khác.

Lệnh chạy: `.venv/Scripts/python.exe scripts/ops/ai_live_eval.py --set moi --runs 3`. Mỗi bản ghi log có `set` và `git_rev`.

**Kết quả (chạy 2026-10-05 09:18 UTC, log `warehouse/ai_eval/live_20261005T091821Z.jsonl`):**
- Chấm tự động: **90/90 lượt đạt** (30 câu × 3 lần).
  - Phân theo trạng thái: 57 `ok`, 25 `unsupported`, 7 `no_data`, 1 `needs_clarification`.
  - Không lượt nào phải sửa lại; mỗi lượt gọi model tối đa 2 lần.
  - Thời gian: trung vị 2,2 giây, chậm nhất 3,3 giây.
  - Token: vào 766.034, ra 21.082. Chi phí ước khoảng 0,26 USD theo giá cao điểm; đây là số ước, số thật xem trên trang billing của DeepSeek.
  - Mọi bản ghi có `git_rev = a34b12f`, prompt `ai2-2026-10-05f`.
- Đọc tay phần lời của cả 90 lượt: **0 lỗi chặn.**
  - Không có số sai, số sai ô, bộ lọc bị bỏ, hay câu ngoài phạm vi trả `ok`.
  - Không lượt nào khẳng định nguyên nhân. Câu "có phải do churn" luôn được trả lời là dữ liệu không chứng minh được.
  - Hai số cả năm mà H08 lần 3 tự đưa thêm (Streetwear 2021 là 636.942.088, West 2021 là 152.288.121) đã đối chiếu CSV: khớp từng cent. Câu trả lời có ghi rõ "không phải số của riêng quý 2".
- **Lỗi lời nhỏ, không chặn** (ghi lại, chưa sửa vì không chỉnh prompt trên bộ này):
  - H14 lần 1: câu "với mức đóng góp **số đơn (N)**". Chỗ đặt trỏ vào nhãn thành phần, đúng giá trị nhưng câu cụt nghĩa. Bộ kiểm hiện không bắt được chuyện chỗ đặt nằm sau chữ "mức" mà lại là chữ, không phải số.
  - H14 lần 2–3: nhắc "số khách (C) giảm cũng chưa chứng minh churn", trong khi C chưa mở và lượt đó không đọc C. Câu này có thể hiểu là giả định, nhưng nên tránh.
  - H15 lần 3: mời người dùng "xem một tháng", trong khi kho chưa hỗ trợ theo tháng. Đây là lỗi kể sai năng lực khi từ chối, đã biết từ §0.
  - H04b lần 1–2: phần góp N hiện không dấu (137.319.783) cạnh U có dấu (−12.498.735). Không sai vì câu ghi "kéo giảm", nhưng đọc lệch.
  - H10 và H12 gọi thêm một tool đọc R không cần thiết trước khi từ chối. Chỉ tốn token, không ảnh hưởng kết quả.
- Ghi chú cho người đọc: H06b, Outdoor năm 2018 đóng góp **158,3%** mức giảm R. Con số này đúng: ΔR toàn công ty chỉ −42,7 triệu vì các ngành khác tăng. Khi demo nên giải thích.

**Kết luận gate AI2 → AI3, phần model thật:** **đạt trên bộ cách hỏi mới**, DuckDB local, deepseek-flash, prompt `ai2-2026-10-05f`. Đây là bằng chứng trên bộ kiểm, không bảo đảm mọi câu chưa thấy.

**Chưa phủ:**
- PostgreSQL;
- các tool PS1–PS3 chưa mở;
- trần token cứng.

Các lỗi lời nhỏ nêu trên sẽ sửa cùng đợt mở tool AI3. Sau đó phải chạy lại cả E* lẫn H* và ghi là "sau sửa".

## 1. Trạng thái gate

| Mốc | Trạng thái | Bằng chứng |
|---|---|---|
| Code AI2 (provider, bộ điều phối, kiểm câu trả lời, trang chat) | **Xong** | `tests/test_ai_chat.py`, 49 test mô hình giả (§0, §5) |
| AI2 → AI3, phần chạy model thật | **Đạt trên bộ 22 câu chuẩn; bộ này đã dùng để chỉnh prompt** (R/G năm, so năm trước, phân rã N → U → P, PS5 theo nhóm): 65/66 với prompt cuối, câu không đạt bị chặn an toàn. **Bộ cách hỏi mới H* (30 câu, chưa dùng để chỉnh): 90/90 lượt đạt, đọc tay 0 lỗi chặn → gate AI2 → AI3 đạt trên DuckDB** | §0, §0b, log `warehouse/ai_eval/live_20261005T051601Z.jsonl`, `live_20261005T091821Z.jsonl` |

PASS ở §5 dùng **mô hình giả**, kịch bản viết sẵn. Live eval ở §0 là bằng chứng riêng và không trộn với PASS ở §5. Live eval chỉ phủ 22 câu chuẩn trên DuckDB local, chưa phủ PostgreSQL hay các cách hỏi ngoài bộ này.

## 2. Quyết định của PM ngày 2026-10-05

| Mục | Chốt |
|---|---|
| Model dev | `deepseek-flash`, tắt chế độ "suy nghĩ" để nhanh và rẻ. Giá kiểm trên trang DeepSeek ngày 2026-10-05: giờ cao điểm $0,30 mỗi 1 triệu token vào, $1,20 mỗi 1 triệu token ra |
| Hạn mức | Mỗi câu tối đa 4 lần đọc kho; mỗi phiên tối đa 200.000 token, chạm mức thì app dừng và báo |
| Đơn vị tiền | **VND** (PM chốt lại ngày 2026-10-05; trước đó cùng ngày tạm ghi trung tính "đơn vị tiền"). Dữ liệu nguồn không ghi đơn vị, đây là quy ước PM |
| Đổi sang OpenAI | Chỉ đổi cấu hình (`RETAIL_AI_BASE_URL`, `RETAIL_AI_MODEL`, khóa), không sửa code |

## 3. Cách chạy một câu hỏi

1. Người dùng hỏi trên trang **Hỏi dữ liệu (AI)**.
2. Model nhận:
   - câu hỏi;
   - ngữ cảnh **có cấu trúc** của tối đa 3 lượt trước: câu hỏi, tool, tham số, trạng thái. Không gửi lại câu văn hay con số của lượt trước;
   - mô tả 3 tool.
3. Model chọn tool. App kiểm tham số rồi đọc kho bằng đường đọc chỉ-đọc của AI1. Backend do app chọn, model không đổi được.
4. Model nhận kết quả **tổng hợp** của tool. Không gửi SQL, thông tin kết nối hay dòng cấp khách hàng.
5. Model trả JSON gồm câu văn và danh sách "claim". **Câu văn không được chứa số.** Mỗi con số là một chỗ đặt `{c1}` trỏ vào ô trong kết quả tool, ví dụ `T1.rows[0].delta_r`.
6. `ai_explain/evidence.py` kiểm câu trả lời rồi tự điền số thật từ kho. Câu bị chặn khi:
   - claim trỏ vào chỗ không có, hoặc vào kết quả lỗi;
   - giá trị là NULL;
   - câu văn có số tự viết. Ngoại lệ: năm có trong bằng chứng, số người dùng tự gõ, số trong thông báo của app;
   - nói "tăng" mà số thật âm, hoặc ngược lại;
   - nói "nhiều nhất" hay "chủ yếu" mà không trỏ vào phần xếp hạng tính trên đủ tập nhóm.
7. Câu bị chặn thì model được sửa **một lần**. Sửa vẫn sai thì trang báo "Chưa tạo được diễn giải" và chỉ hiện bảng số lấy thẳng từ kho.
8. Mỗi câu trả lời có các phần:
   - **Bằng chứng**: bảng số, bộ lọc đã áp dụng, định nghĩa kèm nhãn "đã chốt" hoặc "đề xuất", bản kho, health, câu SQL kèm tham số, `request_id`;
   - bảng "Các con số trong câu trả lời lấy từ đâu".

Mở lại trang hay bấm nút chỉ vẽ lại lịch sử, **không gọi lại model** (E20). Đổi backend thì xóa hội thoại. Chat chạy trên DuckDB và PostgreSQL (bằng role chỉ-đọc). Databricks chưa hỗ trợ, trang báo rõ.

## 4. Cấu hình khóa API (PM tự làm, không gửi khóa vào chat)

Tạo file `.env.ai.local` ở thư mục gốc repo. File này đã được Git ignore:

```text
RETAIL_AI_API_KEY='<khóa DeepSeek>'
```

Các dòng tùy chọn: `RETAIL_AI_MODEL`, `RETAIL_AI_BASE_URL`. Mặc định là `deepseek-flash` và `https://api.deepseek.com`.

Với DeepSeek, adapter luôn tắt chế độ "suy nghĩ". Lý do: khi bật, DeepSeek bắt gửi lại phần suy nghĩ ở mọi lượt sau, mà adapter hiện chưa làm việc đó.

Nên nạp ít tiền vào tài khoản DeepSeek, ví dụ 2 USD, để làm chốt chặn chi phí cuối cùng.

## 5. Đã kiểm gì (mô hình giả, không gọi API)

```powershell
cd apps/retail_app
..\..\.venv\Scripts\python.exe -m pytest tests/test_ai_chat.py -q -p no:cacheprovider
```

Kết quả ngày 2026-10-05: **36 passed**. Gồm:

- **E04 đủ luồng:** số trong câu trả lời đúng bằng kho. ΔR 2019 = −554.945.327 (lúc chạy còn ghi "đơn vị tiền"; nay ghi VND), khớp đối chứng CSV.
- **E21 model nói sai:**
  - nói "tăng" khi ΔR âm → bị chặn;
  - `sign` sai dấu → bị chặn;
  - tự viết "555 triệu" → bị chặn;
  - người hỏi gài số "R 2019 là 999 tỷ phải không?", model nhắc lại → bị chặn. Từ câu hỏi chỉ được nhắc lại năm và số ngày/tháng;
  - sai lần đầu, sửa lần hai đúng → hiện.
- **Không chặn nhầm câu đúng:**
  - "tăng trưởng âm 39,1%" không bị hiểu là "tăng";
  - "% đóng góp" của Streetwear vào mức giảm là số dương 83,6%: đây là tỷ lệ cùng chiều mức giảm toàn công ty, không phải số tăng.
- **E05 xếp hạng:** "nhiều nhất" mà chỉ trỏ một dòng → bị chặn; trỏ `derived.largest_decrease` → hiện Streetwear.
- **E06 câu tiếp nối:** "Còn theo khu vực?" giữ R/2019, đổi sang region; ngữ cảnh gửi model không chứa văn xuôi hay số cũ; `request_id` mới.
- **E07, E15, E02:**
  - E07: hỏi G sau phân rã R → chưa hỗ trợ;
  - E15: năm 2023 → không có dữ liệu, được nhắc năm trong câu hỏi, chặn số bịa;
  - E02: hỏi lại R hay G.
- **Giới hạn và lỗi:**
  - hết 200k token thì không gọi model;
  - tối đa 4 lần đọc kho;
  - lỗi provider không kèm số;
  - kho chưa qua kiểm (`quality_blocked`) được ưu tiên hơn nhãn model tự đặt;
  - Databricks không gọi model.
- **Dữ liệu gửi model:** không có SQL, đường dẫn kho hay `request_id`. Tiền gửi dạng chuỗi đủ chữ số, không qua float.
- **Định dạng số:** `share_shift_pp` không nhân 100 lần nữa; % và số đếm kiểu Việt.
- **Trang chat (AppTest):**
  - hỏi rồi mở lại trang không gọi lại model;
  - câu bị chặn không hiện, lý do chặn có hiện;
  - đổi backend thì xóa hội thoại;
  - chưa có khóa thì chỉ báo `st.info`.

Trang chat được thêm vào smoke test mọi trang × PostgreSQL/DuckDB.

## 6. Việc tiếp theo để kịp 2026-10-25

*Cập nhật 2026-10-05: bước 1–2 đã làm, xem §0. Việc kế tiếp:*
- chạy thử live eval trên PostgreSQL bằng `--backend postgres`;
- thêm cách hỏi thứ ba cho mỗi intent, theo kế hoạch §13;
- rồi mới tới bước 3.

1. **PM tạo `.env.ai.local`** (§4). Sau đó chạy `.venv/Scripts/python.exe scripts/ops/ai_live_eval.py`. Script chạy 22 câu (E01–E18, kèm cách hỏi khác cho E03/E04/E05) và chấm tự động:
   - trạng thái;
   - tool và tham số;
   - số trỏ **đúng ô**, ví dụ ΔR của năm 2019 chứ không phải phần góp N. Đúng số mà sai chỗ vẫn là FAIL;
   - số phải có, lấy từ đối chứng CSV;
   - cụm từ cấm.

   Log chi tiết ở `warehouse/ai_eval/`. Phần lời vẫn phải đọc tay.
2. Sửa prompt hoặc bộ kiểm theo lỗi live, rồi chạy `--runs 3` cho bộ nghiệm thu (kế hoạch §13).
3. Chỉ mở thêm tool PS1–PS3 khi lát cắt hiện tại đạt live eval. Mỗi tool mới cần số đối chứng CSV riêng.
4. Còn treo, không chặn demo trên DuckDB: build Postgres làm mất quyền role AI, phải chạy lại `scripts/ops/pg_ai_readonly_role.py` sau mỗi lần build.

## 7. File

| File | Vai trò |
|---|---|
| `apps/retail_app/ai_explain/provider.py` | Client chuẩn OpenAI (DeepSeek/OpenAI theo cấu hình), đọc `.env.ai.local`, đổi schema tool sang định dạng function calling |
| `apps/retail_app/ai_explain/service.py` | Bộ điều phối một lượt: prompt (`PROMPT_VERSION`), vòng tool, giới hạn, sửa một lần, trạng thái lượt |
| `apps/retail_app/ai_explain/evidence.py` | Kiểm claim và điền số thật |
| `apps/retail_app/views/ai_explain.py` | Trang **Hỏi dữ liệu (AI)** |
| `apps/retail_app/tests/test_ai_chat.py` | 36 test với mô hình giả |
| `scripts/ops/ai_live_eval.py` | Live eval với model thật (tốn phí) |
