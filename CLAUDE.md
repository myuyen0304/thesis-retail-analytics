# CLAUDE.md — hướng dẫn cho Claude Code

File này được commit vào repo, nên Claude Code trên **máy của cả hai thành viên** đều đọc được.
Đọc hết trước khi làm bất cứ việc gì trong repo này.

“Trước khi làm việc, đọc mục Chọn skill theo việc trong docs/agent_workflows.md; dùng tập skill nhỏ nhất đủ cho yêu cầu.”

Khi được giao xây **AI Explain/chat PS1–PS5**, dùng `retail-ai-explain` và đọc
[`docs/ai_explain_plan.md`](docs/ai_explain_plan.md), nhất là §0 và §11–§14.
Bắt đầu từ hợp đồng câu hỏi → metric/grain/kỳ/bộ lọc → query → kết quả đối chứng (AI0),
rồi kiểm công cụ query độc lập với LLM (AI1). Chỉ mở câu hỏi mà backend đã kiểm chứng hỗ trợ;
không bỏ ngầm bộ lọc, không lấy số từ trí nhớ hoặc coi phân rã số học là nguyên nhân.
Kiểm quyền chỉ đọc, phiên bản dữ liệu và bằng chứng trước khi nối API. Quy ước còn chờ BA chốt
phải giữ nhãn đề xuất; nghiệm thu app không tự biến mọi quy ước thành đã chốt.

---

## 0. Ngôn ngữ

**Viết tiếng Việt** — markdown cell trong notebook, tài liệu `.md`, comment giải thích, và cả
phần trả lời người dùng. Toàn bộ project hiện tại là tiếng Việt; nếu chèn tiếng Anh vào thì
tài liệu sẽ thành nửa nọ nửa kia. Tên biến / tên cột / tên file giữ nguyên tiếng Anh.

---

## 1. Bài toán

Datathon 2026 Round 1 (đề tài khóa luận). Dự báo `Revenue` và `COGS` **theo ngày**:

| | Khoảng thời gian | Số ngày |
|---|---|---|
| Lịch sử (train) | 2012-07-04 → 2022-12-31 | 3.833 ngày, **không thiếu ngày nào** |
| Vùng dự báo (test) | 2023-01-01 → 2024-07-01 | 548 ngày |

Nộp bài: file dạng `data/sample_submission.csv` — cột `Date, Revenue, COGS`.

**Hướng đã chốt ngày 2026-09-27** (PM/BA, xem `docs/dwh_roadmap.md`): trục chính của khóa luận là **DWH phục vụ
5 problem statement doanh thu** (`docs/star_schema.md`). Các bước tiếp theo, theo thứ tự:
- app phân tích bằng code;
- production trên **Databricks** (đổi ngày 2026-10-05, xem dưới);
- Kafka.

**Đổi ngày 2026-10-05 (PM chốt):** **Databricks là đích production**, gồm DWH, app phân tích và chat AI Explain;
không còn là "lab". Snowflake thôi là bước mặc định; các script Snowflake đã viết giữ nguyên, chưa chạy cloud.
Cách làm: dev và test ở local (DuckDB/PostgreSQL) trước, đạt rồi mới deploy lên Databricks. Chi tiết: `docs/dwh_roadmap.md`.

Dự báo/SHAP là **phần mở rộng riêng**, không còn là bước mặc định. Power BI không bắt buộc.
Các kết luận về dữ liệu ở §5 vẫn đúng và vẫn dùng khi làm phần dự báo.

---

## 2. Data KHÔNG nằm trong git

Thư mục `data/` bị gitignore (126MB). **Trước khi chạy bất kỳ notebook nào, phải có `data/` ở root repo** —
tải từ link Google Drive ghi trong `README.md`.

Nếu gặp `FileNotFoundError: data/orders.csv` → không phải lỗi code, mà là chưa tải data.
Báo cho người dùng biết và dẫn họ về `README.md`, đừng đi sửa đường dẫn trong notebook.

**Không bao giờ commit file trong `data/`**, kể cả file nhỏ, kể cả `submission.csv`.

14 file nguồn: `customers`, `geography`, `products`, `promotions`, `orders`, `order_items`,
`payments`, `shipments`, `returns`, `reviews`, `inventory`, `web_traffic`, `sales`, `sample_submission`.
(`data/submission.csv` là **output** do `notebooks/04_forecasting/baseline.ipynb` sinh ra, không phải data nguồn.)

---

## 3. Bản đồ file

| File | Vai trò |
|---|---|
| `notebooks/01_exploration/eda.ipynb` | Tìm **cấu trúc sinh dữ liệu** — không xây model. Nguồn của 8 kết luận ở §5. |
| `notebooks/02_design/data_model.ipynb` | Kiểm chứng từng quyết định thiết kế trong `docs/star_schema.md`. |
| `notebooks/02_design/normalization.ipynb` | Kiểm chứng từng phụ thuộc hàm (FD) trong `docs/normalized_schema.md`. |
| `notebooks/04_forecasting/baseline.ipynb` | Baseline đơn giản (seasonal average + trend). **Có lỗi đã biết** — xem §6. |
| `docs/star_schema.md` | Thiết kế dimensional model (star schema) + ERD mermaid. |
| `docs/normalized_schema.md` | Thiết kế quan hệ chuẩn hóa 1NF→3NF (19 bảng). §9 so sánh hai mô hình. |
| `docs/` | Tài liệu business, EDA, data dictionary, schema và defense. |

### Convention quan trọng: `.md` là diễn giải, notebook là chứng minh

Mỗi khẳng định trong file `.md` đều có **một cell chạy lại được** trong notebook tương ứng.
Đây là cặp đôi cố ý — khi sửa một bên phải sửa bên kia. Đừng thêm khẳng định vào `.md`
mà không có cell chứng minh, và đừng xoá cell chứng minh mà giữ khẳng định.

---

## 4. Quy ước code

Cả 3 notebook phân tích đều mở đầu giống nhau — giữ nguyên idiom này khi viết thêm:

```python
import pandas as pd, numpy as np
import warnings; warnings.filterwarnings('ignore')
pd.set_option('display.width', 220); pd.set_option('display.max_columns', 60)

DATA = 'data'
R = lambda f, **k: pd.read_csv(f'{DATA}/{f}', low_memory=False, **k)
```

Đường dẫn data luôn tương đối từ root repo (`'data'`), không dùng đường dẫn tuyệt đối kiểu `D:\...`.
Notebook nằm trong `notebooks/<nhóm>/` (cây thư mục: `README.md`) nhưng **vẫn chạy với thư mục làm việc = root repo**
(`.vscode/settings.json` đặt `jupyter.notebookFileRoot`). Vì vậy giữ `DATA = 'data'`, đừng đổi thành `'../../data'`.
Script trong `scripts/` cũng chạy từ root: `.venv/Scripts/python.exe scripts/<nhóm>/<file>.py`.

---

## 5. Những gì ĐÃ kết luận — đừng dò lại từ đầu

Tám điểm dưới đây đã được chứng minh: **điểm 1–6 từ `notebooks/01_exploration/eda.ipynb`** (đúng 5 phát hiện chính nêu ở cell đầu,
tách điểm 3 thành hai vì mùa vụ-theo-tháng và ngày-trong-tháng là hai tín hiệu riêng),
**điểm 7 từ `notebooks/01_exploration/eda.ipynb` §6**, **điểm 8 từ `notebooks/02_design/data_model.ipynb` §3**.
Phép reconcile ở điểm 1 rất tốn thời gian chạy; **không cần làm lại**. Nếu định nói ngược lại
bất kỳ điểm nào, phải chỉ ra cell nào sai trước.

1. **`sales.csv` tái tạo được CHÍNH XÁC** từ `order_items × orders × products`:
   `Revenue(d) = Σ quantity × unit_price`, **KHÔNG trừ `discount_amount`**;
   `COGS(d) = Σ quantity × cogs`. Đã dò qua mọi tổ hợp filter, đây là công thức duy nhất khớp.
   → Target là **hàm xác định** của dữ liệu giao dịch, nên mọi bảng con đều là nguồn feature hợp lệ.
   → Revenue tách được thành: `N_đơn(d) × (units/đơn) × giá_TB_mỗi_unit(d)`.

2. **Đứt gãy cấu trúc cuối 2018** — doanh thu rơi ~40% rồi đi ngang. Chuỗi KHÔNG có một xu hướng duy nhất.

3. **Mùa vụ theo tháng rất mạnh và ổn định** — đỉnh T4–T6, đáy T12–T1.

4. **Hiệu ứng ngày-trong-tháng rất lớn** — dốc tăng dần về cuối tháng. Đây là tín hiệu baseline bỏ sót nhiều nhất.

5. **Thứ trong tuần gần như vô nghĩa** (R² = 0,008) — baseline bỏ qua nó là đúng.

6. **Tháng 8 có chu kỳ 2 năm rất mạnh**: năm **lẻ** có siêu khuyến mãi *"Urban Blowout"*
   làm doanh thu **−37%** và **COGS > Revenue** (tỷ lệ ~1,36).
   → **2023 là năm lẻ, và tháng 8/2023 nằm trong vùng dự báo.** Bỏ qua điểm này là hỏng bài.

7. **`COGS/Revenue` nên mô hình hoá như một TỶ LỆ**, không phải hai mức độc lập.

8. **Toàn vẹn tham chiếu hoàn hảo** — 0 orphan trên 14 quan hệ. Đây là bài *khôi phục cấu trúc*,
   không phải bài *làm sạch dữ liệu*. Đừng viết code xử lý orphan/missing FK.

### Ràng buộc chi phối mọi lựa chọn feature

**Mọi bảng phụ đều dừng ở 2022-12-31.** Không bảng nào phủ vùng dự báo 2023–2024.
→ Feature ngoại sinh dùng được cho dự báo phải là biến **suy ra từ lịch** (calendar-derived):
tháng, ngày-trong-tháng, năm chẵn/lẻ, khoảng cách tới cuối tháng, cờ mùa khuyến mãi...
Không thể dùng trực tiếp `web_traffic`, `inventory`, `reviews`... ở thời điểm tương lai.

---

## 6. Cảnh báo về `notebooks/04_forecasting/baseline.ipynb`

`notebooks/04_forecasting/baseline.ipynb` ước lượng tăng trưởng bằng **trung bình nhân gộp 2013–2022 (−3,8%/năm)** rồi ngoại suy.
**Con số này đã biết là sai** vì nó gộp hai chế độ khác nhau qua đứt gãy 2018.

Giữ notebook này làm **mốc so sánh**, đừng xây model mới lên trên nó.

---

## 7. Git flow của nhóm

Repo: `myuyen0304/thesis-retail-analytics` (**Private**). Team 2 người.

- `main` = giai đoạn **khám phá + hiểu data + thiết kế ERD**, đã ổn định, luôn chạy được.
  Việc tiếp theo (preprocessing, feature engineering, model) làm trên **nhánh riêng** rồi PR về `main`.
- Đặt tên nhánh: `<loại>/<tên người>` — vd `eda/myuyen`, `preprocess/myuyen`, `model/<tên bạn>`, `docs/erd-fix`.
- **Luôn `git checkout main && git pull` trước khi tạo nhánh mới.**
- Merge vào `main` qua Pull Request, người kia review.
- `git add` **từng file cụ thể**, không `git add -A` (dễ lỡ tay kéo file rác vào).

### Quy ước commit message

- **Không thêm dòng `Co-Authored-By: Claude ...`** vào cuối commit message. Mặc định của
  Claude Code là có; ở repo này thì bỏ. Đây là khóa luận, log phải là tác giả người thật.
- **Ngắn gọn** — một dòng tiêu đề mô tả việc đã làm, không cần body trừ khi thật sự cần giải thích.
- Viết **tiếng Việt không dấu** cho commit message (khác với `.md` và notebook ở §0 — chỗ đó có dấu).
  Cả log hiện tại đang theo lối này, thêm dấu vào sẽ lệch với phần còn lại. Ký hiệu `§` thì dùng được.

### Hai quy tắc bắt buộc với notebook

1. **Một notebook một chủ.** Hai người sửa cùng một `.ipynb` sẽ tạo conflict trong JSON
   mà git không merge được và file hỏng luôn. Ai giữ file nào ghi trong `README.md`.
2. **Không commit khi notebook đang chạy dở.** Chạy hết → save → rồi mới commit.

Nếu người dùng nhờ commit/push: chỉ commit đúng file liên quan tới việc vừa làm, và luôn
`git status` xác nhận không có gì trong `data/` bị staged trước khi commit.

---

## 8. Ghi nhớ giữa các session

Claude Code **không nhớ** session trước. Mỗi lần mở là đọc lại từ đầu: file này, `README.md`,
`docs/`, git log. Nên chỗ nào cần nhớ lâu thì phải **viết ra file**, đừng nói miệng trong chat.

### Cái gì viết vào đâu

| Loại | Chỗ đúng | Lý do |
|---|---|---|
| Kết luận về data, quyết định thiết kế, hướng đã chốt / đã loại | `CLAUDE.md` (§5) hoặc `docs/` | Commit vào repo → cả hai thành viên và Claude trên cả hai máy đều đọc được |
| Đang làm dở tới đâu, sở thích cách làm việc, link riêng | memory của Claude Code | Nằm ở máy từng người, **không** commit, **không** đồng bộ giữa hai người |

Memory là bộ nhớ **cá nhân, cục bộ**. Đừng để kết luận quan trọng của khóa luận chỉ nằm ở đó —
người kia sẽ không thấy, và mất máy là mất luôn.

### Chỉ thị cho Claude

- Kết thúc một việc mà rút ra được kết luận đáng giữ → **tự ghi lại, không cần hỏi**.
  Phân luồng: thứ riêng của người dùng (đang làm dở tới đâu, cách làm việc, link riêng) → memory;
  kết luận thuộc về project → `CLAUDE.md`/`docs/`, **nhưng chỉ khi đã có cell chứng minh** trong
  notebook tương ứng (§3). Chưa có cell thì để tạm ở memory và ghi rõ "chưa chứng minh" —
  tuyệt đối không thêm khẳng định trần vào §5.
- Mỗi lần sửa `CLAUDE.md`/`docs/` phải **nói ra trong câu trả lời**. Đây là file commit chung;
  sửa lặng lẽ sẽ thành diff lạ trong PR của người kia (§7).
- Mỗi memory **một file một ý**, kèm một dòng trỏ trong `MEMORY.md`. Không nhét nội dung vào `MEMORY.md`.
- Trước khi ghi, kiểm tra đã có file nào nói cùng chuyện chưa — **sửa file cũ**, đừng tạo bản trùng.
- **Đừng ghi** thứ repo đã có sẵn: cấu trúc thư mục, lịch sử git, nội dung chính `CLAUDE.md`.
- Ngày tháng ghi tuyệt đối (`2026-09-07`), không ghi "hôm qua", "tuần trước".

Muốn lưu nhanh một ý thì **nói thẳng ra**: *"nhớ giúp mình: ..."* — Claude sẽ tự ghi vào memory
hoặc `CLAUDE.md` theo phân luồng ở trên. (Phím tắt `#` đầu dòng: đã thử ngày 2026-09-07 trên bản
Claude Code nhóm đang dùng, **không có tác dụng** — tin nhắn đi thẳng vào hội thoại, không ghi file nào.)
