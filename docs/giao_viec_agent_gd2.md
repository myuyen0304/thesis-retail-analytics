# Giao việc phần AI GĐ2 cho agent (sổ tay của PM)

Soạn ngày 2026-10-15 (vai Head of AI), sau khi B2b xong ở local. Dùng cho Claude Code và Codex.
Trạng thái từng bước và quyết định đã chốt: [ke_hoach_ai_gd2.md](ke_hoach_ai_gd2.md) §2, §4, §8. File này chỉ giữ **cách giao việc**.

---

## 1. Năm nguyên tắc giao việc

1. **Mỗi phiên một bước.** Mở phiên mới cho mỗi bước (B3a, B3b…). Phiên mới tự đọc `CLAUDE.md` → `ke_hoach_ai_gd2.md`, nên không cần kể lại lịch sử.
2. **Gọi đúng skill.** Claude Code: `/tên-skill <yêu cầu>`. Codex: `$tên-skill <yêu cầu>`. Chọn skill theo bảng ở §2.
3. **Prompt có đủ bốn phần:** việc cần làm, điều đã chốt không được đổi, điều không được làm, và "xong khi". Mẫu ở §3 đã có đủ.
4. **Agent hỏi thì chỉ trả lời câu hỏi nghiệp vụ.** Câu hỏi kỹ thuật (file nào, đặt tên gì) agent phải tự tìm trong repo. Agent đòi đổi luật chọn model, đổi target hay đổi thước đo: đó là quyết định của PM; trả lời rồi ghi vào sổ quyết định §2.
5. **Nghiệm thu bằng bằng chứng, không bằng câu văn.** Dùng checklist ở §4 trước khi coi một bước là xong.

## 2. Thứ tự các bước còn lại

| Thứ tự | Bước | Skill | Ngày gợi ý | Phụ thuộc |
|---|---|---|---|---|
| 1 | B3a: tool chat `get_forecast` | `retail-ai-explain` | 10-16 → 10-17 | B2b (xong local) |
| 2 | B3b: trang Dự báo | `retail-bi-product` | 10-17 → 10-18 | B2b; làm song song B3a được nếu khác người/khác file |
| 3 | B3c: eval G* (live) | `retail-ai-explain` | 10-19 | B3a |
| 4 | B6: `show_chart` | `retail-ai-explain` | 10-20 | B3a |
| 5 | B4: `explain_forecast` (Could) | `retail-forecasting` rồi `retail-ai-explain` | 10-21 nếu kịp | B3a |
| 6 | Báo cáo research, chương thực nghiệm | `retail-forecasting` | 10-21 → 10-22 | B2a |
| 7 | B7: router + nghiệm thu AI4 | `retail-ai-explain` | 10-22 → 10-23 | B3, B6 |
| — | Lên cloud (Docker, writer SP, app public) | `retail-platform-validation` | chỉ sau khi PM quyết | Quyết định "đường cho app public" ở `ke_hoach_ai_gd2.md` §2 |

Trễ thì cắt từ dưới lên: B4 → B6. Không cắt B3a, B3c, B7.

## 3. Prompt dán sẵn

Thay `/` bằng `$` khi dùng Codex. Mỗi prompt dán vào một phiên mới.

### 3.1 B3a: tool chat `get_forecast`

```text
/retail-ai-explain Làm B3a trong docs/ke_hoach_ai_gd2.md: tool chat get_forecast đọc reporting.rpt_forecast_daily
và reporting.rpt_forecast_backtest của bản dữ liệu đang phục vụ (chế độ versioned, local DuckDB, release đang active).

Đọc trước: docs/ke_hoach_ai_gd2.md §2 và §8; docs/hop_dong_du_bao.md §7–§8; docs/chon_model_du_bao.md §6.1;
.agents/skills/retail-ai-explain/references/agent_levels.md (dòng L3 và mục "Bẫy khi thêm tool đọc relation mới").

Đã chốt, không đổi:
- Mặc định trả số của ứng viên is_primary; lý do chọn lấy từ selection_step và rpt_forecast_backtest, không tự đặt.
  Ứng viên khác chỉ khi người dùng hỏi, ghi rõ "không phải model chính".
- Mọi số dự báo kèm: chữ "dự báo", "G – doanh thu gộp, gồm cả đơn hủy", khoảng 80%, model_version, trained_through.
- Chỉ mở kỳ 2023-01-01 → 2024-07-01. Hỏi ngoài kỳ thì trả phần trong kỳ và nói rõ phần thiếu.
- Câu "model nào chính xác nhất" trả cả điểm ngày (thước chọn) lẫn sai số tổng tháng, kể cả khi hai thước xếp hạng khác nhau.
  Nói rõ đó là sai số backtest 2020–2022.

Bẫy đã biết, phải xử lý và có test:
- rpt_forecast_* chỉ có trong bản dữ liệu của pipeline; build thường (chế độ cũ, Postgres, bản public) không có hai bảng này.
  Thêm vào ALLOWED_RELATIONS / ai_readonly_relations không được làm guard khóa chat ở chế độ cũ.
  Kho chưa có thì tool trả trạng thái trung thực, không lấy số nguồn khác thay vào.
- Rollback về bản dựng trước B2b (6f8654fb4b4348c483a78b64) không có hai bảng này: báo rõ giới hạn hoặc xử lý.

Không làm: commit; deploy hay đổi cấu hình app public/Databricks; sửa luật chọn hay code trong scripts/forecast/.

Xong khi: test tool so kết quả với query đối chứng độc lập (không gọi LLM) đạt; test guard ở cả chế độ cũ và versioned đạt;
có bộ eval G* offline theo bảng "Eval bổ sung" của agent_levels.md. Ghi một dòng nhật ký vào ke_hoach_ai_gd2.md §8,
một mục bàn giao vào docs/dwh_huong_dan_pm_ba.md §9, và giải thích cho PM bằng lời đời thường.
```

### 3.2 B3b: trang Dự báo

```text
/retail-bi-product Làm B3b trong docs/ke_hoach_ai_gd2.md: trang Streamlit "Dự báo" đọc rpt_forecast_daily và
rpt_forecast_backtest của bản dữ liệu đang phục vụ (local DuckDB, chế độ versioned).

Đọc trước: docs/ke_hoach_ai_gd2.md §2, §8; docs/hop_dong_du_bao.md §2.2, §6–§8.

Trang cần có:
- G và COGS thực tế 2021–2022 nối với dự báo 2023-01-01 → 2024-07-01 của ứng viên chính, khoảng 80% theo ngày;
- bảng tổng tháng, tháng 07/2024 ghi là tháng thiếu (1 ngày); không hiển thị khoảng tháng (Q7), thay bằng "sai số tháng điển hình" từ backtest;
- bảng so sánh ứng viên từ rpt_forecast_backtest (điểm ngày, MAPE G tháng), đánh dấu ứng viên chính và bước luật đã chọn;
- nhãn: "dự báo", "G – doanh thu gộp, gồm cả đơn hủy" (thống nhất với metric_catalog.py), model_version, trained_through,
  và câu "sai số backtest 2020–2022, không phải độ chính xác 2023–2024".

Không trộn số dự báo vào trang PS1–PS5. Không so G dự báo với R thực tế. Kho chưa có (chế độ cũ) thì trang báo trạng thái, không lỗi.
Không làm: commit; deploy; sửa scripts/forecast/ hay dbt.

Xong khi: AppTest trang đạt ở cả chế độ cũ (báo chưa có dự báo) và versioned (có số); số tổng tháng trên trang khớp query đối chứng.
Ghi nhật ký §8, mục bàn giao PM, kèm hướng dẫn xem trang.
```

### 3.3 B3c: eval G* chạy với LLM thật

```text
/retail-ai-explain Làm B3c: chạy bộ eval G* cho get_forecast với LLM thật trên local (chế độ versioned).
Dùng bộ câu mới, không dùng lại câu đã dùng để phát triển. Theo docs chat_evaluation của skill:
ghi model, prompt, catalog, release_id cho mỗi lần chạy; kết quả mock không được ghi là live.
Báo cáo theo nhóm câu: đúng nhãn dự báo, từ chối ngoài kỳ, không nhầm thực tế/dự báo, giải thích việc chọn model bằng dữ liệu.
Câu nào trượt thì ghi nguyên nhân, đề xuất sửa, chưa sửa khi PM chưa xem. Không commit.
```

### 3.4 B6: biểu đồ trong chat

```text
/retail-ai-explain Làm B6 trong docs/ke_hoach_ai_gd2.md: tool show_chart vẽ biểu đồ ngay trong chat từ đúng kết quả tool
đã chạy trong lượt đó (L1 hoặc get_forecast). Luật: dòng L2 trong agent_levels.md. Không vẽ số không có trong evidence.
Biểu đồ dự báo giữ nhãn dự báo và khoảng 80%. Xong khi có test chứng minh biểu đồ dùng đúng dữ liệu evidence và eval vài câu "vẽ…".
Không commit, không deploy.
```

### 3.5 B4: giải thích dự báo (Could)

```text
/retail-forecasting Làm phần dữ liệu của B4: thêm vào stage dự báo bảng đóng góp SHAP theo ngày cho LightGBM
(ứng viên chính) và theo nhóm biến (mùa vụ, đầu/cuối tháng, từng đợt khuyến mãi, chế độ, năm chẵn/lẻ),
ghi thành reporting.rpt_forecast_explain trong bản dữ liệu, có test cộng đóng góp về đúng dự báo.
Code trong scripts/forecast/; notebook gọi cùng module và có cell chứng minh. Nhãn "phân rã model, không phải nguyên nhân".
Không đổi ứng viên, tham số hay luật chọn. Không commit.
```
Sau đó giao tiếp cho `/retail-ai-explain` phần tool `explain_forecast`, theo dòng L4 của `agent_levels.md`.

### 3.6 Báo cáo research, chương thực nghiệm

```text
/retail-forecasting Viết nháp chương thực nghiệm của báo cáo research theo khung docs/ke_hoach_ai_gd2.md §7
(RQ1–RQ4), thành file docs/bao_cao_research_thuc_nghiem.md. Mỗi con số phải trỏ tới mục và cell của
notebooks/04_forecasting/so_sanh_model.ipynb. Nêu đủ giới hạn ở §7.2 (điểm thắng lạc quan, biến chọn sau EDA,
không có số thực 2023–2024, khác lời giải tham khảo). Không trích paper từ trí nhớ: chỗ cần nguồn ghi "cần nguồn".
Không chạy lại model, không đổi notebook. Không commit.
```

### 3.7 B7: router và nghiệm thu AI4

```text
/retail-ai-explain Làm B7 trong docs/ke_hoach_ai_gd2.md: prompt router chọn level (L1 query, L2 biểu đồ, L3 dự báo,
L4 giải thích nếu có). Câu trộn quá khứ và tương lai tách hai phần, mỗi phần có nhãn riêng.
Chạy bộ held-out mới với LLM thật trên local, rồi viết báo cáo AI4 (đã đạt, chưa đạt, giới hạn).
Ghi đủ phiên bản model, prompt, catalog, release_id. Không commit, không deploy.
```

### 3.8 Lên cloud (chỉ khi PM đã quyết)

```text
/retail-platform-validation PM đã chốt [ghi lựa chọn và ngày]. Làm theo docs/automation_batch.md:
(1) build lại image Airflow (đã thêm thư viện dự báo, chưa kiểm), chạy DAG local tới publish, so điểm từng ứng viên
với notebook vì image dùng Python 3.12; (2) nếu PM đã tạo writer SP: chạy pipeline target databricks, kiểm parity,
quyền reader và rollback; (3) chuyển app public sang versioned đúng 5 bước, dừng ngay khi chat báo lỗi quyền.
Mỗi bước báo riêng compile/deploy/run/parity/publish. Hỏi PM trước bước (3).
```

## 4. Nghiệm thu khi agent báo "xong"

Hỏi agent năm câu. Thiếu câu nào thì chưa coi là xong.

1. **Đã chạy gì, trên backend nào?** Local DuckDB, Postgres hay Databricks. "Chưa chạy" phải được ghi là chưa chạy.
2. **Test nào đạt, test nào chưa chạy?** Test tool không gọi LLM tách khỏi eval LLM; kết quả mock không được gọi là live.
3. **Số trên giao diện hoặc trong chat có khớp query đối chứng không?** Chỉ cho xem một con số cụ thể.
4. **Đã sửa file nào, có đụng file chung không?** `CLAUDE.md`, `docs/`, `requirements.txt`, skill. File chung phải được nói ra.
5. **Nhật ký và bàn giao đã ghi chưa?** Một dòng ở `ke_hoach_ai_gd2.md` §8, một mục ở `dwh_huong_dan_pm_ba.md` §9.

Muốn commit thì nói rõ: "commit file code của bước này" hoặc "commit cả docs". Agent không tự commit.

## 5. Câu "phanh" dùng khi agent đi quá phạm vi

- "Dừng. Bước này không gồm [X]. Ghi [X] vào phần 'Còn mở' rồi làm tiếp phần đã giao."
- "Không đổi luật chọn / ứng viên / thước đo. Nếu thấy cần đổi thì viết đề xuất, chờ PM chốt."
- "Không deploy, không đổi cấu hình app public khi PM chưa chốt."
- "Không dựng Kafka, không làm gì với Kaggle."
