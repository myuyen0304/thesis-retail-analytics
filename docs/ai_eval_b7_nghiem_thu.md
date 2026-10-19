# B7: router chọn level và nghiệm thu AI4

Soạn ngày 2026-10-18 (bước S1 trong [giao_viec_theo_so_do.md](giao_viec_theo_so_do.md); prompt
[giao_viec_agent_gd2.md](giao_viec_agent_gd2.md) §3.7). Agent đang có: L1 query, L2 `show_chart` và nút mở trang,
L3 `get_forecast` / `get_forecast_backtest`. L4 và RAG chưa làm, không nằm trong bộ này.

Báo cáo tách bốn loại kết quả, không gộp với nhau:
- test không gọi LLM (provider giả);
- phát lại log chat thật cũ;
- eval với LLM thật trên local DuckDB (3 lần);
- eval với LLM thật trên Databricks production (1 lần).

Kết quả mock không được tính là kết quả live.

## 1. Đã làm

**Router.** Router là một mục trong system prompt (`apps/retail_app/ai_explain/service.py`), không có lượt gọi LLM
phân loại riêng. Mục "CHỌN TOOL (router)" gồm ba dòng, mỗi dòng trỏ về quy tắc chi tiết đã có:
- số thực tế tới 2022 → tool số liệu lịch sử; dự báo, so model → quy tắc 16; vẽ → quy tắc 17;
- câu trộn thực tế và dự báo → gọi tool cho từng phần, trả lời theo quy tắc 16;
- ngoài phạm vi → `unsupported`; mơ hồ → quy tắc 2; tiếp nối → quy tắc 9.

S7 và S8 sẽ thêm mỗi tool mới một dòng vào mục này. Quy tắc 16 đổi câu trộn thành "hai câu riêng, mỗi số ghi kỳ và
nhãn riêng; R thực tế khác tập đơn với G dự báo nên không đặt cạnh nhau".

**Phiên bản.** `PROMPT_VERSION` = `b7-2026-10-18` (trước `b6-2026-10-17b`). `CATALOG_VERSION` giữ `b6-2026-10-17`
(catalog không đổi), `TOOL_VERSION` giữ `v1.7`.

**Trần token ra mỗi lần gọi.** `MAX_OUTPUT_TOKENS` hạ từ 1.536 xuống 1.408.
- Lý do: test `test_tran_token_xau_nhat_con_du` đòi 3 câu xấu nhất vẫn vừa hạn mức 200 nghìn token một phiên (PM chốt),
  còn dư ít nhất 1.000 token. Trước B7 chỉ còn dư 1.547 token. Thêm mục router làm vượt hạn mức; hạ trần thì còn dư
  1.307 token.
- Căn cứ: 1.368 lượt live tới 2026-10-17 dùng tối đa 1.116 token ra cho **cả một lượt**.
- Hệ quả cho S7 và S8: mỗi tool mới thêm schema và một dòng router, nên gần như không còn chỗ. Hai bước đó phải tính
  lại hạn mức này.

**`evidence.py` (bước kiểm câu trả lời của app).**
1. *Luật rv12f (Codex, commit `946f507`) chặn mọi câu hỏi trộn có chữ "dự báo".* Ví dụ "G thực tế tháng 12/2021 và
   G dự báo tháng 12/2023" bị ép về `no_data`, vì 12/2021 nằm ngoài vùng dự báo. Đã sửa hẹp: chỉ kỳ nằm ngoài **cả**
   dữ liệu thực tế (trước 2012-07-04) lẫn vùng dự báo (sau 2024-07-01) mới tính là thiếu số. Kỳ đã qua có số thực tế
   thì được trả bằng số thực tế (quy tắc 16). Năm 2025 vẫn bị ép `no_data` như trước.
2. *Nhãn "thực tế" do app gắn.* Khi câu trả lời có cả số dự báo lẫn số thực tế, mọi số thực tế mang nhãn "(… thực tế,
   kỳ)". Trước đây chỉ số dự báo luôn có nhãn; số thực tế có thể không có nhãn nếu câu văn đã gọi tên.
3. *Chặn câu trộn sai.* Bị chặn:
   - số thực tế và số dự báo trong cùng một câu;
   - câu so số dự báo với số thực tế: có chữ so sánh hay chênh không bị phủ định, kèm cả chữ "dự báo" và "thực tế",
     hoặc câu có số dự báo mà so với một năm thực tế (2012–2022).

   Không có tool nào tính chênh lệch dự báo − thực tế, nên app không kiểm được phép so này.

**Script eval** (`scripts/ops/ai_live_eval.py`):
- bộ `b7` (`ACCEPT_B7`);
- tham số `labels`: chữ nhãn do app gắn phải có trong câu trả lời;
- cột `links` trong log: nút mở trang do app dựng, để đọc tay phần L2;
- `_release_meta` ghi được bản dữ liệu khi chạy Databricks (lấy từ bằng chứng của một lần đọc thật qua SP AI).

Mã băm của các bộ cũ không đổi (`gm`, `v`, `n` khớp log 2026-10-17).

## 2. Kiểm không gọi LLM

| Kiểm | Kết quả |
|---|---|
| `tests/test_ai_router.py` (mới, 20 test, provider giả) | 20/20 đạt |
| Cả bộ `pytest apps/retail_app/tests/test_ai_*.py -k "not postgres"` (chạy lại trên code cuối) | 722 đạt, 83 bỏ qua, 0 trượt. Cả 83 test bỏ qua là test Databricks trong `test_ai_databricks.py`, chỉ chạy khi đặt `RETAIL_TEST_DATABRICKS=1`; test PostgreSQL bị loại bằng `-k` |
| Phát lại 1.335 lượt live cũ (raw_final + tham số tool) qua `evidence.py` bản commit và bản B7 | 0 lượt đổi trạng thái; 4 lượt đổi chữ, chỉ vì có thêm nhãn "(G thực tế, 3/2022)" |

Test provider giả **không chứng minh router chọn đúng tool**: mô hình thật mới chọn tool. Các test này chứng minh app
giữ luật ở từng nhánh khi mô hình đã chọn: L1, L2 kèm nút mở trang, L3, câu trộn (6 kiểu trả lời sai đều bị chặn, câu
phủ định không bị chặn nhầm), ngoài phạm vi, mơ hồ, tiếp nối. Router chọn đúng hay không đo bằng bộ held-out ở §3–§5.

Script phát lại (bản cũ và bản mới chạy cùng vòng lặp với
`warehouse/reviews/ai_gd2_20261015/claude_rv12b_phat_lai.py`) nằm ở thư mục tạm của phiên, không commit.

## 3. Bộ held-out `b7`: chốt trước lượt gọi đầu

| Mục | Giá trị |
|---|---|
| Mã băm bộ câu | `721a9fed30c20b7d` (ghi ở `ke_hoach_ai_gd2.md` §8 trước lượt gọi đầu) |
| Số câu | 24 (K01–K24): L1 mỗi PS một câu, L2 hai câu vẽ, L3 năm câu, bốn câu trộn, ba câu ngoài phạm vi, hai câu mơ hồ, ba câu tiếp nối |
| Rubric (`--kiem-rubric`, không gọi mô hình) | 24/24 trên local DuckDB versioned |
| Mô hình / prompt / catalog / tool | `deepseek-flash`, `b7-2026-10-18`, `b6-2026-10-17`, `v1.7` |

Câu và kỳ đều mới so với các bộ trước, `tests/` (kể cả `test_ai_router.py`) và `scripts/review/`. Số dự báo không ghi vào
tiêu chí chấm máy, vì bản dữ liệu train lại thì số đổi; S9 chạy lại bộ này trên bản cuối. Số thực tế dùng để chấm
(G năm 2022 = 1.169.748.832 VND) tính thẳng từ `data/sales.csv` bằng pandas, không qua tool. Câu hỏi, tiêu chí chấm máy
và tiêu chí đọc tay đầy đủ ở `ACCEPT_B7`.

Sau khi chốt, không sửa câu, tiêu chí hay prompt. Không có lượt chạy lại sau sửa trên bộ này.

## 4. Kết quả trên local DuckDB (3 lần)

| Mục | Giá trị |
|---|---|
| Log | `warehouse/ai_eval/live_20261018T121444Z_b7_29516.jsonl` (Git ignore) |
| Bản dữ liệu | `fc14b8a2f5a24ff99a434d7c` (run `b3b-01`, snapshot `5bd9a84aaf73`, model dự báo `a78d5b07d43c`), chế độ versioned |
| Code | `d695b9fc717ea960` (chưa commit) |
| Token | vào 1.827.014, ra 20.567; **ước** 0,57 USD (giá cao điểm, chỉ ước) |
| Cận trên prompt | 167 lần gọi, 0 lần token thật vượt cận trên |
| Chấm máy | **67/72** |
| Đọc tay theo tiêu chí ghi trước | **66/72** |
| Đạt cả hai | **64/72** |

## 5. Kết quả trên Databricks production (1 lần)

| Mục | Giá trị |
|---|---|
| Log | `warehouse/ai_eval/live_20261018T123512Z_b7_28388.jsonl` |
| Bản dữ liệu | `b25b3e471bae45768a79e4a2` (run `de80c263dce23aec44d70c44`, snapshot `5bd9a84aaf73`); mọi lần đọc tool trong log đều ghi bản này |
| Quyền đọc | SP chỉ đọc của AI (OAuth M2M), như chat bản public; không ghi gì lên cloud. PM duyệt profile `retail-dev`, nhưng đường chat không đọc profile: guard luôn xác thực bằng SP AI (`RETAIL_AI_DBX_CLIENT_ID` / `_SECRET` trong `.env.ai.local`); `.env.databricks.local` chỉ cấp host và warehouse |
| Code | `53700d6a734f3f16` (khác bản local chỉ ở `_release_meta` của script eval; code chat giống hệt) |
| Token | vào 612.725, ra 6.985; **ước** 0,19 USD |
| Chấm máy | **22/24** |
| Đọc tay | **22/24** |
| Đạt cả hai | **21/24** |

Số đọc từ Databricks khớp số local ở mọi câu, trừ hai số dự báo lệch rất nhỏ (ARIMA tháng 10/2023: 57.703.545 so với
57.703.552 VND; điểm ngày của model chính: 576.790 so với 577.160). Lý do: hai bản dữ liệu do hai lần train khác nhau tạo
ra (image Docker Python 3.12 so với local). Nhật ký §8 đã ghi mức lệch tới 1,03% giữa các bản này.

## 6. Từng câu

Ký hiệu "máy / tay" là số lượt đạt chấm máy / đọc tay. Cột local là 3 lượt, cột Databricks là 1 lượt.

| Câu | Nhánh | Local máy / tay | Databricks máy / tay | Nhận xét |
|---|---|---|---|---|
| K01 tỷ trọng đơn trả / G 2017 | L1 PS1 | 3/3 · 3/3 | 1 · 1 | 5,5%, có nhãn "đơn trả / G, 2017" |
| K02 R giảm tổng cộng 2016–2018 | L1 PS2 | 0/3 · 0/3 | 0 · 0 | **Router chọn sai tool** (xem §7) |
| K03 tháng thấp nhất trong năm | L1 PS3 | 3/3 · 3/3 | 1 · 1 | Tháng 12, cả 4 giai đoạn, có ghi chú cách gom năm chờ BA chốt |
| K04 phân rã N/U/P 2015 | L1 PS4 | 3/3 · 3/3 | 1 · 1 | Nói rõ phân rã số học, không phải nguyên nhân. Có câu "mức tăng này nhỏ so với quy mô R" là nhận xét không có số |
| K05 vùng kéo giảm nhiều nhất 2021 | L1 PS5 | 3/3 · 3/3 | 1 · 1 | West; câu "không phải nguyên nhân" nằm ở ghi chú app |
| K06 "Thế còn chia theo kênh?" | tiếp nối | 3/3 · 3/3 | 1 · 1 | Giữ R và năm 2021, gọi lại tool theo kênh |
| K07 vẽ đóng góp ngành 2017 | L2 | 3/3 · 3/3 | 1 · 1 | Biểu đồ 4 điểm từ kết quả tool của lượt; nút mở PS5 · ngành hàng, năm 2017 |
| K08 vẽ điểm ngày các model | L2 | 3/3 · 1/3 | 1 · 1 | Biểu đồ 15 điểm, nút mở trang Dự báo. 2 lượt local không nói điểm ngày là thước chọn model |
| K09 dự báo G 10/2023 | L3 | 3/3 · 3/3 | 1 · 1 | Nhãn dự báo G, sai số tháng điển hình |
| K10 COGS/G dự báo 4/2024 | L3 | 3/3 · 3/3 | 1 · 1 | Dẫn tỷ lệ do tool tính, không tự chia |
| K11 tổng cả vùng dự báo | L3 | 3/3 · 3/3 | 1 · 1 | Gọi là "cả kỳ 2023-01-01 → 2024-07-01", không gọi là tổng hai năm |
| K12 thắng mốc sàn cả 3 fold | L3 | 3/3 · 3/3 | 1 · 1 | Có số; nói backtest 2020–2022 và điểm thắng là lạc quan |
| K13 dự báo bằng ARIMA | L3 | 3/3 · 3/3 | 1 · 1 | Ghi "không phải model chính", không thay bằng model chính |
| K14 G 2022 thực tế, G 2023 dự báo | trộn | 3/3 · 3/3 | 1 · 1 | Hai câu riêng, nhãn "G thực tế" / "dự báo G"; không cộng, không so |
| K15 R thực tế 4/2022, dự báo 4/2023 | trộn | 3/3 · 3/3 | 1 · 1 | Nói rõ dự báo là G, không phải R; không so |
| K16 dự báo 9/2023 cao hơn 9/2022 bao nhiêu % | trộn | 3/3 · 3/3 | 1 · 1 | Không tính %; hai câu riêng. Cả 4 lượt đều phải sửa một lần: 3 lượt lần đầu gộp hai số chung một câu và guard mới chặn đúng; 1 lượt bị chặn nhầm (xem §7). Lần sửa đều đạt |
| K17 cộng G 2021 thực tế với G 2024 dự báo | trộn | 3/3 · 2/3 | 1 · 0 | Không cộng. Một lượt local và lượt Databricks ra khuôn dẫn số của app, gọi chính các số được hỏi là "không phải số bạn hỏi" (xem §7) |
| K18 tồn kho | ngoài phạm vi | 3/3 · 3/3 | 1 · 1 | `unsupported`, không đưa số thay thế |
| K19 sửa số dự báo | ngoài phạm vi | 3/3 · 3/3 | 1 · 1 | Không ghi, không nhắc lại con số người hỏi |
| K20 giá đối thủ | ngoài phạm vi | 3/3 · 3/3 | 1 · 1 | Nói dữ liệu không chứng minh nguyên nhân |
| K21 "Doanh thu năm 2016 thế nào?" | mơ hồ | 1/3 · 3/3 | 0 · 1 | Nêu cả R và G có nhãn. Máy trượt vì mô hình gọi R và G thành hai lần thay cho `R_and_G` (xem §7) |
| K22 "Dự báo tháng 4 là bao nhiêu?" | mơ hồ | 3/3 · 3/3 | 1 · 1 | Đạt theo tiêu chí đã ghi (số có ghi rõ năm), nhưng cả 4 lượt **tự chọn 2023** mà không hỏi lại hay nhắc 4/2024 |
| K23 "Còn tháng 5/2024?" | tiếp nối | 3/3 · 3/3 | 1 · 1 | Giữ G dự báo, đổi kỳ |
| K24 "Vậy giá vốn dự báo của năm đó?" | tiếp nối | 3/3 · 3/3 | 1 · 1 | Hiểu "năm đó" là 2023 (năm dự báo), nhãn dự báo COGS |

## 7. Chưa đạt: nguyên nhân, đề xuất, và phần đã sửa sau nghiệm thu

Không sửa rồi chạy lại trên chính bộ này để báo là đạt. Sửa xong phải đo bằng bộ câu mới.

**Sau nghiệm thu (S1b, PM chốt 2026-10-18):**
- Sửa phía app cho K17, K16, K08. Commit ghi khi PM commit.
- Điểm AI4 ở §4–§5 giữ nguyên, không chấm lại bộ `b7`. Phần sửa được đo lại ở S9: chạy lại bộ `b7` cùng mã băm, ghi
  thành dòng hồi quy dù kết quả thế nào.
- K02, K22 (dòng router) để tới S7 và thêm khi tăng `PROMPT_VERSION`. K21 sửa rubric ở bộ eval sau.

| Câu | Lỗi của | Nguyên nhân | Đề xuất | Sau nghiệm thu |
|---|---|---|---|---|
| K02 | Router (prompt) | "Từ 2016 đến 2018" là khoảng năm trùng ranh giới giai đoạn B. Mô hình hiểu là chuỗi năm (`get_revenue_summary` + đổi so năm trước) và không tìm ra `get_revenue_trend` phases, nơi có sẵn % đổi cả giai đoạn. Câu trả lời trung thực (không tự cộng) nhưng không trả lời được | Thêm vào dòng router: khoảng nhiều năm trùng ranh giới giai đoạn (2013–2016, 2016–2018, 2018–2019, 2019–2022) thì dùng `get_revenue_trend` phases; khoảng khác thì nói chưa có tổng khoảng | Chưa sửa; ghi vào hàng S7 của `giao_viec_theo_so_do.md` |
| K17 | App (khuôn dẫn số) | Khi trả `unsupported` mà có dẫn số, khuôn rv12f coi 2021 là "ngoài vùng dự báo" và xếp số G thực tế 2021 vào mục "Số tham khảo, không phải số bạn hỏi", dù đó chính là số được hỏi. Gốc: `reference_refs` coi một số là "tham khảo" khi nó không khớp **mọi** kỳ trong câu hỏi, nên câu hỏi hai kỳ luôn bật khuôn dù đủ số cả hai kỳ | Áp cùng ngoại lệ cho khuôn: kỳ có số thực tế không bị gọi là "ngoài vùng dự báo", và số đúng kỳ được hỏi không xếp vào mục tham khảo. Phải phát lại log live cũ trước khi nhận | **Đã sửa (S1b).** (1) Khuôn chỉ bật khi có kỳ được hỏi thiếu số, kỳ là khoảng, hoặc có số của kỳ khác. (2) Kỳ đã có số thực tế không bị gọi là "ngoài vùng dự báo". (3) Số đúng kỳ, đúng loại nằm ở mục riêng "Số đúng kỳ trong câu hỏi"; vẫn giữ mục tham khảo khi câu hỏi xin "mốc tham khảo" (rv12f) hoặc lọc theo nhóm (B03). Test: `test_ai_router.py::test_k17_*` |
| K21 | Rubric chấm máy, một phần tool | `R_and_G` kèm `compare_prior_year` trả `unsupported`, nên mô hình gọi R và G riêng. Câu trả lời đúng tiêu chí đọc tay, nhưng rubric chỉ nhận lời gọi `R_and_G` | Bộ sau cho rubric nhận cả hai lời gọi R và G; cân nhắc cho `R_and_G` hỗ trợ so năm trước | Chưa sửa; sửa rubric ở bộ eval sau |
| K08 | Prompt (nhẹ) | 2/3 lượt local không nói điểm ngày là thước chọn model khi vẽ điểm ngày | App tự gắn ghi chú "điểm ngày kết hợp là thước chọn model" khi trả số của `get_forecast_backtest`, như ghi chú MAPE tháng đã có | **Đã sửa (S1b).** `tools.SELECTION_NOTE` in dưới mọi câu trả lời dẫn `get_forecast_backtest`; `TOOL_VERSION` `v1.8`; prompt không đổi. Test: `test_k08_*` |
| K22 | Router (prompt) | Tháng không kèm năm có ở cả 2023 và 2024; mô hình tự chọn 2023, có ghi rõ năm | Dòng router "mơ hồ" nêu ví dụ này: hỏi lại năm, hoặc trả cả hai năm | Chưa sửa; ghi vào hàng S7 |
| K16 (lần đầu) | App (chặn nhầm nhẹ) | Câu từ chối "Không thể trả lời bằng phần trăm chênh lệch…" bị coi là câu so sánh, vì cửa sổ phủ định chỉ xét 3 chữ trước chữ "chênh". Mô hình sửa lại đạt ở lần thứ hai | Mở cửa sổ phủ định tới đầu vế câu; thêm test cho câu này | **Đã sửa (S1b).** Phủ định tính từ đầu vế câu, hoặc trong 3 chữ ngay trước. Phủ định nằm trước "nhưng / còn…" không tính, nên câu "không phải R, nhưng cao hơn thực tế" giờ bị chặn; trước khi sửa câu này lọt. Test: `test_k16_*` |

## 8. Giới hạn

- Bộ held-out nhỏ: 24 câu × 3 lượt local + 1 lượt production. Một câu đạt không chứng minh mọi cách hỏi đều đúng.
- Bản local `fc14b8a2…` khác bản production `b25b3e47…` (hai lần train). Production chỉ chạy 1 lượt, theo lệnh PM.
- Phần đọc tay do chính phiên đã viết router làm, nên có thể thiên vị. Nên cho Codex đọc lại `answer_md` trong hai log.
- Nút mở trang (L2) chỉ được đọc tay qua cột `links` trong log, chưa có chấm máy và chưa bấm thử trên app.
- Chưa có trong bộ này: kho dự báo rỗng, cũ hoặc chưa được cấp quyền. Các tình huống này có test không gọi LLM ở
  `test_ai_forecast.py` (bản dựng trước B2b), nhưng chưa có eval live.
- L4 (giải thích dự báo) và RAG chưa làm (S5, S7, S8). Mỗi tool mới cần nhóm eval riêng, không dùng lại bộ `b7`.

## 9. Chi phí API

| Lượt | Token vào | Token ra | Ước (giá cao điểm `deepseek-flash`, kiểm 2026-10-05) |
|---|---|---|---|
| Local, 3 lần | 1.827.014 | 20.567 | 0,57 USD |
| Databricks, 1 lần | 612.725 | 6.985 | 0,19 USD |
| Tổng | 2.439.739 | 27.552 | **khoảng 0,77 USD** (PM duyệt tới khoảng 1,35 USD) |

Số thật xem trên trang billing của DeepSeek. Lượt Databricks còn tốn thêm quota SQL warehouse (24 câu, mỗi câu 1–3 lần
đọc), chưa đo riêng.
