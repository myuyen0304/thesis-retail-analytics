# AI Explain — sửa AI1 và rà AI2 ngày 2026-10-05

Phạm vi: sửa hai lỗi của lần review trước; đọc code và bàn giao AI2 của Claude.
Không gọi API model, không deploy cloud, không rebuild kho hoặc đổi quyền role.

## Hai lỗi đã sửa

- `tests/test_ai_tools.py`: bỏ `autocommit=True` và lệnh đưa doanh thu 2019 về 0. Probe UPDATE dùng `WHERE false`;
  DDL dùng tên riêng; mỗi phép thử chạy trong `transaction(force_rollback=True)`, kể cả khi assertion thất bại.
  Test bổ sung mô phỏng câu lệnh ghi thành công trên bảng TEMP, xác nhận UPDATE/CREATE đều rollback khi test báo lỗi.
- `ai_explain/metric_catalog.py`, `tools.py`: thêm gate chung theo tool × metric × kỳ × grain × chiều,
  chặn trước khi mở kết nối. Catalog thiếu dòng, trùng dòng hoặc khác `open` đều bị chặn.
  `R_and_G` cần cả hai metric mở; so năm trước cần quyền đọc mức năm và quyền so sánh.
  Schema tool chỉ công bố tool/giá trị còn tổ hợp mở; dispatcher kiểm lại tổ hợp đầy đủ.
  Mở một dòng catalog không thay thế việc triển khai handler và đối chứng cho tính năng mới.

Version mới: catalog `ai1-2026-10-05`, tool `v1.1`. Không đổi định nghĩa KPI hay SQL dbt.

## Kiểm thử thực tế

Chạy từ root:

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest apps/retail_app/tests/test_ai_tools.py apps/retail_app/tests/test_ai_chat.py -q -p no:cacheprovider --tb=short --maxfail=3
```

Kết quả: **200 passed in 15.81s**, không skip/deselect:
103 test AI1 không cần PostgreSQL, 61 test PostgreSQL, 36 test AI2 dùng mô hình giả, gồm AppTest.
Lần đầu trong sandbox bị chặn quyền thư mục tạm Windows; kết quả trên là lần chạy lại ngoài sandbox.
PostgreSQL local kết nối được trong lần này. Đây không phải kết quả live-model eval hoặc toàn bộ test app.

## AI2 đã có gì

Đã có adapter provider, vòng gọi tool, ngữ cảnh có cấu trúc, renderer claim, trang chat và script live eval.
AppTest xác nhận rerun không gọi lại model, đổi backend xóa lịch sử, câu bị validator chặn không được hiện.
AI chỉ đọc DuckDB/PostgreSQL; chưa có đường đọc AI cho Databricks/Snowflake.

Việc tắt thinking của DeepSeek phù hợp tài liệu chính thức: thinking mặc định bật và tool conversations khi bật
phải gửi lại `reasoning_content`. Đối chiếu [DeepSeek Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/)
ngày 2026-10-05; chưa xác minh API thật hoặc khả năng chỉ đổi cấu hình sang mọi model OpenAI.

## Lỗi mới đã tái hiện — chưa sửa trong đợt này

> **Cập nhật cùng ngày 2026-10-05:** cả 4 probe dưới đây đã được sửa. Mỗi probe nay là một test hồi quy, kỳ vọng
> câu sai bị chặn. Bộ chấm live eval đã được siết như mục "Các giới hạn", và live eval đã chạy với model thật.
> Chi tiết ở [ai_explain_ai2.md §0](ai_explain_ai2.md). Bảng giữ nguyên làm lịch sử review.

Các probe dùng `service.run_turn`, `FakeProvider` của `tests/test_ai_chat.py` và query DuckDB thật.
Không phải kết quả do model thật sinh. Mỗi câu sai bên dưới được cho vào `final(...)` của mô hình giả.

| Ưu tiên | Probe | Kết quả hiện tại | Cần sửa |
|---|---|---|---|
| P1 | Hỏi R 2019; tool trả `R_and_G`; câu `R năm 2019 là {c1}.`, claim trỏ `T1.rows[0].g` | `ok`, hiện **1.136.801.442** dưới nhãn R, thực chất là G | Claim cần mang metric/kỳ/nhóm; nhãn số lấy từ renderer có cấu trúc, không tin nhãn do model tự viết |
| P1 | Hỏi `R 2019 là 10 tỷ phải không?`; tool đọc R; câu `Đúng, R năm 2019 là 10 tỷ.`, claims rỗng | `ok`, chấp nhận số bịa | `question_numbers` cho phép mọi số ≤31, không phân biệt ngày với giá trị tiền; không cho whitelist chữ số dùng ở mọi vị trí |
| P1 | Tool PS5 category/2019; câu `Ngành kéo giảm nhiều nhất là Luxury.`; khai báo claim `c1` trỏ `T1.derived.largest_decrease.groups` nhưng không dùng `{c1}` | `ok`, chấp nhận Luxury dù nhóm thật là Streetwear | Gate xếp hạng đang tính cả claim không được render; cần gắn nhận định với đúng claim, nhóm, chiều, kỳ và hướng xếp hạng |
| P2 | Tool drivers R/2019; câu `Quy tắc {c1}.`, claim trỏ `T1.derived.small_delta_rule` | `TypeError: unsupported format string passed to dict.__format__` thoát khỏi `run_turn` | Kiểm kiểu/field được phép trước format; trả lỗi validation để sửa một lần/fallback, không làm crash trang |

Nguồn: `evidence.py` (`question_numbers`, `_fmt`, `validate`), `service.py` (`_check_final`).
Một giá trị đúng trong kho chưa chứng minh câu văn gắn đúng metric, năm hay nhóm.

Ví dụ tái hiện probe sai metric, từ Python chạy ở root:

```python
import sys
sys.path.insert(0, 'apps/retail_app')
from ai_explain import service
from tests.test_ai_chat import FakeProvider, call, final

bad = final(answer='R năm 2019 là {c1}.',
            claims=[{'id': 'c1', 'path': 'T1.rows[0].g'}])
t = service.run_turn('R năm 2019 là bao nhiêu?', [], 'duckdb', FakeProvider(
    call('get_revenue_summary', metric='R_and_G', year=2019), bad, bad))
print(t.status, t.answer_md)  # hiện tại: ok, số G gắn nhãn R
```

## Các giới hạn còn cần kiểm

- Hạn 200.000 token hiện là kiểm trước mỗi request, không phải trần chi phí cứng:
  provider chưa giới hạn output theo ngân sách còn lại, nên request cuối có thể vượt mức.
- Bộ chấm `ai_live_eval.py` kiểm tool/params và claim path riêng: chưa ràng buộc chúng cùng một result reference;
  E02 còn cho phép `ok` mà chưa bắt buộc trả cả R/G. Cần siết rubric trước khi dùng tỷ lệ PASS làm nghiệm thu.
- Giữ kho cố định trong demo; build marker chưa chứng minh các lần gọi tool cùng một bản publish khi có rebuild đồng thời.
- Chưa chạy API thật trong đợt review. Không dùng 200 test PASS để kết luận model hiểu đúng mọi câu hỏi.

## Việc tiếp theo

Gia cố hợp đồng claim/renderer, chuyển bốn probe trên thành test hồi quy mong đợi bị chặn; sau đó mới chạy live eval.
Giữ kết quả query test, AppTest và live eval thành các loại bằng chứng riêng.
