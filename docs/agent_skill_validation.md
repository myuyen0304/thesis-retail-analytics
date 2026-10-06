# Kết quả kiểm chứng bộ skill

Ngày: **2026-09-29**. Phạm vi: sáu skill source, sáu bản Claude, script đồng bộ, tài liệu và thử tư vấn chỉ đọc. Không chạy lại app/dbt, không thay đổi dữ liệu, không deploy cloud hay xây runtime chat.

## Kiểm tra cấu trúc và script

| Kiểm tra | Kết quả |
|---|---|
| `skill-creator/scripts/quick_validate.py`, UTF-8 | 6/6 source hợp lệ |
| `scripts/skills/validate_skills.py` | 6 source + 6 bản Claude hợp lệ; link nội bộ tồn tại; đồng bộ khớp |
| `scripts/skills/sync_skills.py --check` | PASS, không ghi file |
| `pytest scripts/skills/tests -q --tb=short` | **16 passed, 1 skipped** |
| Bảo toàn `AGENTS.md` | SHA-256 trước/sau giống nhau: `E8243A8D5F05D0D633D2423929E396BE6CC608F3DDC8D07009D1AC4B079BAE2E` |

Các test script đã kiểm: check không ghi; sync lần đầu và chạy lại không thay file; cập nhật nguồn; sửa tay ở đích chặn toàn bộ mutation; bảo toàn skill ngoài danh sách; xóa reference đã nghỉ đúng ownership; file lạ; source thiếu; CRLF/LF; manifest trống/path traversal; file bị thay bằng thư mục. Test symlink bỏ qua vì tài khoản Windows không có quyền tạo symlink; không coi là đã kiểm runtime nhánh này.

Pytest lần đầu trong sandbox bị chặn tạo thư mục tạm. Đã chạy ngoài sandbox sau cấp quyền. Phép so sánh trong test cập nhật nguồn được sửa để đúng quy tắc LF/CRLF của script; các test cuối cùng đạt kết quả trên.

## Codex CLI: hành vi chỉ đọc

Client `codex-cli 0.156.1`; phiên ephemeral, sandbox read-only. Sau lỗi khởi tạo app-server bị từ chối quyền trong sandbox ngoài, phép thử được chạy lại với quyền khởi tạo client và vẫn giữ sandbox read-only cho agent con.

[Bằng chứng JSON](references/skill-evaluations/2026-09-29-codex.json) lưu prompt thực tế, output 12 ca, hash 14 file skill, thread ID và phạm vi kiểm. Log đã được kiểm: các command là đọc/tìm file; không có build, SQL, deploy hoặc sửa repo. Không lưu raw trace chứa toàn bộ ngữ cảnh máy cá nhân vào repository.

| Ca | Nhận xét sau đọc output | Kết quả tư vấn |
|---|---|---|
| M1/M2 | Tìm AOV có sẵn; phân biệt doanh thu tuyệt đối với tỷ lệ; làm rõ R/G, NULL và vùng khách | PASS |
| D1/D2 | Phân biệt EDA dùng G với phân tích R; giữ raw, không suy diễn nhân quả hoặc xóa outlier để đẹp | PASS |
| E1/E2 | Distinct khách đúng tập; nhận ra fan-out và mất dòng khi join bridge, không dùng DISTINCT che lỗi | PASS |
| B1/B2 | Tái dùng reporting; từ chối chia tỷ lệ ngày từ tổng năm, đề xuất detail và test filter | PASS |
| A1/A2 | Query chỉ đọc có evidence; không khẳng định marketing là nguyên nhân, không forecast/UPDATE ngoài phạm vi | PASS |
| P1/P2 | Lab DWH/KPI riêng; không đồng nhất compile với parity; identity bền vững cho replay | PASS |

**Giới hạn:** 12 câu được đưa cùng một phiên để kiểm tư vấn và lựa chọn skill theo từng câu, không phải 12 lần routing độc lập. Agent đọc cả sáu skill vì batch gồm cả sáu lĩnh vực. Chưa kiểm negative routing bằng phiên riêng hoặc cú pháp gọi skill trực tiếp. Chưa đo chất lượng code, tính đúng SQL thực thi, triển khai cloud hay chất lượng runtime AI chat. Không dùng 12/12 này làm cam kết mọi yêu cầu tương lai đều đúng.

## Claude Code

Client `2.1.284`. Phép thử dùng plan mode, chỉ cho phép Read/Glob/Grep/Skill, không dùng MCP server và không lưu phiên. Lần đầu trong sandbox trả `API Error: Connection refused — a firewall or proxy may be blocking it (ECONNREFUSED)`.

Lần thử lại ngoài sandbox hoàn thành (session `347839ef-3690-445d-926d-f9e7d05f93c3`, khoảng 199 giây, không có permission denial). [Output lần đầu](references/skill-evaluations/2026-09-29-claude.json) giữ nguyên cả những kết luận sai để có thể review.

- 9/12 ca đạt yêu cầu tư vấn và chọn skill chính đúng.
- **D1 cần sửa:** agent suy diễn phải hỏi chủ notebook ngay cả khi chỉ lập phương án/tạo notebook độc lập, dù README không chỉ định chủ.
- **B2 cần sửa:** phát hiện lỗi nội suy số ngày đúng nhưng đọc bảng đề xuất cũ để hỏi lại quyết định M6 đã được sửa/chốt sau đó.
- **P1 cần sửa:** nói không tìm thấy archive và không có profile mà chưa kiểm chứng đủ; archive thực tế có trong checkout. Tìm mặc định có thể bỏ qua file do Git ignore/exclude.

Đã chỉnh hẹp ba skill DA/BI/platform: không chặn công việc độc lập vì thiếu chủ notebook; đọc correction mới nhất thay một dòng grep lịch sử; kiểm đường dẫn trực tiếp và không khẳng định trạng thái profile từ memory. Đã đồng bộ lại và kiểm cấu trúc. Ba ca được thử lại bằng phiên mới sau sửa; kết quả được ghi ở phần hồi quy bên dưới.

## Hồi quy sau sửa hướng dẫn

Phạm vi thử lại: D1, B2, P1 trên Claude Code, vẫn chỉ đọc và không đưa oracle. Các JSON lần đầu chứa hash bản trước sửa; báo cáo hồi quy lưu hash bản sau sửa riêng. Không ghi đè bằng chứng lỗi ban đầu.

[Bằng chứng hồi quy](references/skill-evaluations/2026-09-29-claude-regression.json): session `932e84c0-703d-4c15-840d-0b1e90b6b60b`, khoảng 131 giây, không có permission denial.

| Ca | Kết quả sau sửa |
|---|---|
| D1 | Không còn chặn việc lập phương án vì thiếu chủ notebook; đề xuất đối chứng CSV, kiểm R/G và không báo số chưa chạy |
| B2 | Nhận ra M6 đã được chốt và có thứ tự nghiệm thu; không còn lấy đề xuất cũ “có thể bỏ” làm quyết định mới |
| P1 | Đọc trực tiếp README archive; xác nhận file tồn tại; profile/auth/compute chưa kiểm được ghi đúng là chưa kiểm, không tin hook lịch sử |

Ba lỗi mục tiêu đã được xử lý trong tư vấn. Riêng D1 có câu “myuyen giữ notebook nên không vướng quyền sở hữu”: phép thử không xác minh người đang sửa là myuyen. **Không dùng câu đó làm quyền sửa notebook**; khi triển khai thật vẫn áp dụng quy tắc phối hợp chủ notebook trong skill/README. Phép thử này chỉ yêu cầu lập phương án, không thực hiện sửa file.

Chưa kiểm isolated negative routing hoặc explicit invocation trên cả hai công cụ. Claude lưu final response và metadata, không có trace từng tool trong artifact này; danh sách `sources_read` là khai báo của client, được đối chiếu các nhận định trọng yếu với file thật. Chưa có bằng chứng runtime app/chat/cloud từ các phép thử skill.

## Cách chạy lại

```powershell
.venv/Scripts/python.exe -X utf8 scripts/skills/validate_skills.py
.venv/Scripts/python.exe -X utf8 scripts/skills/sync_skills.py --check
.venv/Scripts/python.exe -m pytest scripts/skills/tests -q --tb=short
```

Để kiểm hành vi sâu hơn, dùng [bộ tình huống](agent_skill_evaluations.md), mỗi ca một phiên chỉ đọc, không đưa cột đáp án cho agent. Chỉ cần chạy lại ca chịu ảnh hưởng khi sửa skill; không phải chạy dbt/cloud chỉ vì đổi Markdown.

Tài liệu roadmap và kế hoạch app đã được bổ sung hướng mới, giữ lịch sử cũ. Các artifact bàn giao chưa commit/push; `docs/` đang bị local Git exclude nên cần stage đích danh khi muốn chia sẻ.
