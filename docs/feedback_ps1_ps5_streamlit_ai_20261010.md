# Feedback PS1–PS5: ý nghĩa KPI, Streamlit và AI Explain

Ngày review: **2026-10-10**. Người thực hiện tiếp: **Claude**.

## 1. Mục tiêu bàn giao

Người dùng đã xây DWH, đưa lên Databricks và dựng Streamlit/AI Explain, nhưng còn hai quan ngại:

1. Sản phẩm có thực sự trả lời đúng các câu hỏi trong [deck updated](presentations/revenue_performance_problem_statement_updated.pptx) không?
2. Người xem có hiểu KPI nói lên điều gì, và giới hạn kết luận từ KPI không?

Tài liệu này ghi lại toàn bộ feedback của lượt review, kèm hướng xử lý và tiêu chí nghiệm thu. **Đây là báo cáo review và danh sách công việc; chưa phải biên bản đã sửa hoặc đã nghiệm thu production.**

Feedback cũ [streamlit_ps1_ps5_ui_feedback.md](streamlit_ps1_ps5_ui_feedback.md) ngày 2026-10-01 tập trung vào card/biểu đồ. Tài liệu này bổ sung đánh giá ngữ nghĩa KPI, độ phủ câu hỏi, phạm vi chat và kiểm chứng; không yêu cầu làm lại các sửa đổi cũ đã hoàn tất.

## 2. Căn cứ và phạm vi kiểm tra

- Đã đọc nội dung **15 slide và speaker notes** của deck.
- Đã đối chiếu `apps/retail_app/views/ps1_do_dung.py` đến `ps5_nhom.py`, lớp `dwh/queries.py`, SQL reporting và `retail_dbt/macros/reporting.sql`.
- Đã đọc catalog khả năng AI, bộ kiểm câu trả lời và các test liên quan.
- Đã truy vấn **DuckDB local** để minh họa số liệu; đã chạy bộ test chọn lọc, gồm AppTest và đối chứng độc lập với CSV.
- Đã tái hiện lỗi chuyển backend sang PostgreSQL khi kết nối timeout.
- **Chưa kiểm lại deployment Databricks/host Streamlit, chưa chạy LLM thật, chưa rebuild dbt trong lượt này.**
- HEAD khi tạo note: `3b68421`. Đây chỉ là mốc checkout; không chứng minh cloud hoặc file DuckDB được build từ HEAD này.
- Không thay đổi code, slide, KPI, dữ liệu hoặc deployment trong lượt review/ghi note.

Nguồn chuẩn cần dùng khi thực hiện:

- `AGENTS.md`, `CLAUDE.md`, `README.md`, `docs/agent_workflows.md`.
- [Hợp đồng KPI](star_schema.md), đặc biệt §3; SQL/macros hiện hành.
- [Kế hoạch app](gd2_app_plan.md), [kế hoạch AI](ai_explain_plan.md) và quyết định mới nhất trong [nhật ký PM/BA](dwh_huong_dan_pm_ba.md).
- Tài liệu có cả lịch sử và cập nhật sau đó: không lấy một dòng “chưa triển khai” cũ để phủ nhận code hiện có.

## 3. Kết luận về độ phủ 5 problem statement

**Streamlit đã có chức năng phân tích cho cả 5 PS và bao phủ phần lớn yêu cầu của deck. AI Explain có phạm vi hẹp hơn giao diện.** Không dùng sự tồn tại của trang, trạng thái app chạy, hoặc tổng số test để khẳng định mọi câu hỏi đã được trả lời đúng trên production.

| PS | Streamlit hiện có theo code | Giới hạn phải giữ rõ |
|---|---|---|
| PS1 — Bao nhiêu doanh thu, G chênh R ở đâu? | G/R theo tháng, năm; thác G → R; tỷ lệ hủy và chiết khấu | R theo ngày đặt hàng và trạng thái snapshot; không phải dòng tiền theo ngày thanh toán |
| PS2 — Tăng/giảm, giai đoạn đổi hướng? | YoY năm/tháng, tổng R 12 tháng, CAGR theo giai đoạn, điểm BA chọn và điểm dữ liệu tự tìm | Mốc BA chọn và điểm tự tìm khác nhau; phương pháp tự tìm mang tính thăm dò |
| PS3 — Nhịp theo tháng, cuối tháng, tháng 8 chẵn/lẻ? | Chỉ số tháng, mức dồn cuối tháng, so chẵn/lẻ, kiểm bỏ từng năm và so giai đoạn | Chuẩn hóa theo năm không loại hết xu hướng; quy ước năm ranh giới khi gom giai đoạn còn là đề xuất |
| PS4 — Biến động nằm ở N/U/P? | Phân rã tuần tự theo năm và giai đoạn; đối soát tổng phần góp | Không chứng minh nhân quả; phương pháp cộng đóng góp từng năm thành giai đoạn còn là đề xuất |
| PS5 — Nhóm nào kéo lên/xuống, C hay F thay đổi? | Xếp hạng từng chiều, tỷ trọng và dịch chuyển; phân rã C/F | C/F trên trang là **toàn công ty**, không thay đổi theo chiều nhóm đang chọn |

Không cần dựng lại DWH hoặc đổi framework chỉ vì người xem chưa hiểu KPI. Trước hết hoàn thiện cách gọi tên, giải thích và nghiệm thu theo câu hỏi.

## 4. Ý nghĩa KPI phải thể hiện được trên sản phẩm

| Chỉ số | Công thức/phạm vi | Người xem được kết luận gì? | Không được suy diễn gì? |
|---|---|---|---|
| G | Tổng `quantity × unit_price`, mọi trạng thái | Quy mô tiền hàng trước các bước loại trạng thái và chiết khấu | Không đồng nhất với doanh thu đã giao hoặc tiền đã thu |
| R | Tổng `quantity × unit_price − discount_amount`, chỉ `delivered` | Doanh thu theo quy ước phân tích của đề tài | Không tự gọi là dòng tiền trong kỳ hoặc doanh thu kế toán |
| R/G | R chia G cùng kỳ | Phần giá trị thuộc R so với tổng G | Không coi toàn bộ G−R là thất thoát/lãng phí hoặc đặt mục tiêu mặc định 100% |
| Tỷ lệ tiền hàng bị hủy | `cancelled_gross / G` | Tỷ trọng **giá trị** thuộc đơn hủy | Không phải tỷ lệ **số đơn** bị hủy |
| Tỷ lệ chiết khấu | Chiết khấu đơn delivered / tiền hàng trước chiết khấu của đơn delivered | Mức chiết khấu trên tập đơn đã giao | Khác tỷ trọng chiết khấu/G trên thác; giảm chiết khấu chưa chắc cải thiện kinh doanh |
| YoY | R kỳ này / R kỳ trước tương ứng − 1 | Mức tăng/giảm so cùng kỳ | Tăng trưởng dương chưa đồng nghĩa đạt kế hoạch hoặc tăng lợi nhuận |
| CAGR | `(R cuối / R đầu)^(1/(năm cuối − năm đầu)) − 1` | Tốc độ tăng trưởng kép bình quân giữa hai mốc | Không phải mỗi năm đều tăng đúng mức này; không đại diện tốt cho cả chuỗi có đổi chế độ |
| R 12 tháng | Tổng 12 tháng đủ gần nhất | Theo dõi xu hướng sau khi làm phẳng nhịp mùa | Không tự chứng minh nguyên nhân hoặc mọi điểm gãy |
| Độ lớn đổi hướng | R 12 tháng sau / R 12 tháng trước điểm − 1 | Mức chênh trước/sau theo cửa sổ đã định nghĩa | Không phải tác động nhân quả của một sự kiện |
| Chỉ số tháng | R tháng / (R năm / 12), năm đủ | 1,5 nghĩa là bằng 1,5 lần bình quân tháng của năm đó | Không phải tăng 50% so cùng tháng năm trước |
| Chênh mùa cao/thấp | Chỉ số tháng cao nhất / thấp nhất, theo cách gộp công bố | Độ lớn dao động theo mùa | Càng cao không tự có nghĩa hiệu suất tốt hơn |
| Mức dồn cuối tháng | Tỷ trọng R từ ngày 26 − `(D−25)/D` | Tập trung nhiều hơn/ít hơn mức rải đều bao nhiêu **điểm %** | Không nhầm điểm % với tăng trưởng %; không dùng cùng mốc lịch cho mọi tháng |
| Chênh tháng 8 lẻ/chẵn | TB chỉ số T8 năm lẻ / TB năm chẵn − 1 | Khác biệt lịch sử giữa hai nhóm năm | Không khẳng định khuyến mãi gây ra chênh lệch hoặc dự báo chắc chắn năm sau |
| N, Q, U | N = đơn delivered distinct; Q = số món delivered; U = Q/N | Mua bao nhiêu đơn và bao nhiêu món mỗi đơn | Không đếm N bằng số dòng sau join; không cộng N tùy ý giữa ngành hàng |
| P | R/Q | Doanh thu bình quân sau chiết khấu trên mỗi món | Không phải đơn giá niêm yết; thay đổi có thể do giá, chiết khấu hoặc cơ cấu sản phẩm |
| AOV | R/N = U×P | Doanh thu bình quân mỗi đơn | Không phải doanh thu bình quân mỗi khách |
| Phần góp N/U/P | Phân rã tuần tự N → U → P; tổng = ΔR | Biến động được phân bổ vào từng thành phần bao nhiêu tiền | Không kết luận nguyên nhân; đổi thứ tự có thể đổi phân bổ tương tác |
| ΔR nhóm | R nhóm năm nay − năm trước | Nhóm góp bao nhiêu tiền vào biến động | Nhóm lớn giảm nhiều tiền chưa chắc suy giảm tương đối nặng nhất |
| % đóng góp | ΔR nhóm / ΔR toàn công ty | Phần đóng góp theo một chiều phân nhóm | Không ép về 0–100%; mẫu số 0 không xác định, gần 0 khó diễn giải |
| Dịch chuyển tỷ trọng | Tỷ trọng năm nay − năm trước, điểm % | Nhóm đang chiếm phần lớn hơn hay nhỏ hơn trong tổng R | Không đồng nhất với tăng trưởng doanh thu nhóm |
| C, F | C = khách distinct có đơn delivered trong kỳ; F = N/C | Số khách hoạt động và số đơn bình quân/khách | C giảm chưa chứng minh churn; không cộng C qua tháng/nhóm có khách trùng |
| Phần góp C/F | `(C1−C0)×F0` và `C1×(F1−F0)`; tổng = ΔN | Phân bổ mức đổi số đơn theo khách hoạt động và tần suất | Không khẳng định mất khách do marketing hoặc khách trung thành giảm |

Quy ước chung:

- Phân tích chính **2013–2022**; 2012 là kỳ thiếu. YoY năm từ 2014, YoY tháng từ 08/2013, rolling 12 tháng đủ đầu tiên kết thúc 07/2013.
- Mẫu số 0 hoặc thiếu kỳ gốc: không tính được/NULL; không tự hiển thị 0%.
- Đơn returned bị loại **toàn bộ**, kể cả trả một phần; không trừ refund thêm lần nữa.
- Category, region, acquisition_channel là ba cách phân chia riêng; không cộng ba chiều với nhau.
- Region là nhãn nguồn mô phỏng; acquisition_channel là kênh thu hút **khách**, khác nguồn từng đơn.
- Tỷ lệ tính lại từ tử/mẫu đúng kỳ và bộ lọc; không lấy trung bình tỷ lệ đã tổng hợp tùy ý.

## 5. Checklist xử lý feedback

### FB01 — Ưu tiên cao: làm rõ tên và ý nghĩa R

**Bằng chứng:** slide 3/4/5/14 và UI dùng “tiền thực nhận”; speaker notes slide 3, slide 15 và hợp đồng KPI lại xác định ngày đặt hàng, trạng thái snapshot và giới hạn kế toán.

**Yêu cầu:**

- Dùng nhãn chính dễ hiểu như **“Doanh thu đơn đã giao (R)”**, kèm mô tả “sau chiết khấu, theo ngày đặt hàng”. Không bắt buộc nhét toàn bộ mô tả vào card hẹp.
- Làm rõ câu hỏi PS1 thành doanh thu theo quy ước đó; tránh khiến người xem hiểu đang đo dòng tiền thu vào tháng/năm.
- Rà đồng bộ `ui/common.py`, tổng quan, PS1–PS5, định nghĩa/prompt/renderer của AI và tài liệu/slide liên quan. Giữ alias cũ để AI vẫn hiểu cách hỏi “thực nhận”.
- Không đổi công thức, trường ngày, tập trạng thái hoặc trừ hoàn tiền thêm trong một sửa đổi nhãn.

**Nghiệm thu:** người xem đọc được phạm vi R ngay cạnh số; số và kỳ không đổi; câu hỏi về tiền thu theo ngày thanh toán phải được phân biệt với R.

### FB02 — Ưu tiên cao: sửa cách đọc R/G và “thất thoát”

**Bằng chứng:** slide 5 và `views/ps1_do_dung.py` còn câu “R/G càng gần 100% càng ít thất thoát”. Catalog AI có alias “thất thoát” cho chênh G−R.

**Yêu cầu:**

- Mô tả trung tính: R/G là tỷ lệ R trên G; muốn biết vì sao thấp phải đọc từng phần của thác.
- G−R gồm đơn hủy, trả, chưa giao và chiết khấu đơn delivered. Không gộp thành mất tiền/lãng phí.
- Không tự đặt target 100%, không gợi ý giảm mọi chiết khấu hoặc coi đơn chưa giao là mất doanh thu vĩnh viễn.
- Alias người dùng có thể giữ, nhưng câu trả lời phải giải thích đúng giới hạn.

**Nghiệm thu:** câu “R/G 76% nghĩa là thất thoát 24% phải không?” không được trả lời đồng ý vô điều kiện; phải giải thích thành phần và kỳ của con số.

### FB03 — Ưu tiên cao: giúp người xem đọc KPI và phân biệt với đạt mục tiêu

**Bằng chứng:** slide 15 nói chưa có chỉ tiêu kế hoạch; hiện số chủ yếu so với lịch sử. Người dùng chưa hiểu KPI nói lên điều gì.

**Yêu cầu:**

- Mỗi trang có câu trả lời ngắn theo số đang chọn, KPI chính, cách đọc và giới hạn. Tái sử dụng nội dung đã có; không thêm hàng loạt đoạn lặp lại làm trang khó đọc.
- Dùng bảng §4 làm tiêu chí ngữ nghĩa; chọn lời giải thích ngắn cạnh card/chart, công thức chi tiết trong tooltip/expander.
- Ghi rõ chưa có target doanh nghiệp; chưa đánh giá đạt/không đạt kế hoạch, lợi nhuận hoặc sức khỏe tài chính.
- Phân biệt tiền, %, điểm %, lần, đơn, món/đơn, đơn/khách và tốc độ %/năm. Không dùng màu “tốt/xấu” mặc định cho chỉ số mô tả mùa vụ.
- Nhận xét phải lấy từ query đúng kỳ/bộ lọc. Không hardcode câu chuyện hoặc số mẫu năm 2019 vào UI.

**Nghiệm thu:** người xem phân biệt được R với ΔR, CAGR với tổng tăng trưởng, P với giá niêm yết, % đóng góp với tăng trưởng, C giảm với churn.

### FB04 — Đồng bộ đơn vị tiền và phạm vi thời gian giữa deck, app và AI

**Bằng chứng:** slide 15 còn “chưa rõ đơn vị tiền tệ”; speaker notes slide 5 chưa cho gắn VND. Nhật ký PM/BA và catalog ghi **PM chốt VND ngày 2026-10-05**, nguồn tự thân không ghi đơn vị.

**Yêu cầu:**

- Cập nhật nội dung tương ứng của slide/tài liệu theo quyết định mới: VND là **quy ước PM**, không tuyên bố CSV chứng minh tiền tệ.
- Kiểm cả speaker notes nếu sửa deck; xác định script sinh deck nếu có để bản sinh lại không đưa nội dung cũ trở lại.
- Phân biệt kỳ tham khảo 2012–2022 với kỳ phân tích 2013–2022. Hai kỳ có R và R/G khác nhau; 76,2% của deck không được gắn mặc định cho mọi kỳ.
- Giữ trạng thái lịch sử dữ liệu đến 2022; thời điểm refresh/build không biến dữ liệu thành giao dịch realtime.

**Nghiệm thu:** cùng KPI/kỳ/đơn vị cho cùng số giữa deck, dashboard và chat; giữ các ghi chú về quyết định PM và snapshot.

### FB05 — Công bố đúng phạm vi AI; tách phần mở rộng khỏi sửa diễn giải

**Bằng chứng:** `ai_explain/metric_catalog.py`, bảng `CAPABILITIES`, hiện đóng:

- `get_order_drivers`: phân rã C/F theo năm.
- `get_revenue_drivers` với kỳ `phase`: phân rã N/U/P theo giai đoạn.
- `get_revenue_trend` với `direction_changes`: điểm đổi hướng dữ liệu tự tìm.
- Giao nhiều chiều như category × region; khoảng ngày tùy ý, nhiều tháng/quý và các tổ hợp khác chưa mở.

**Yêu cầu làm ngay:** giao diện gợi ý và câu giới thiệu chat phải khớp catalog. Câu chưa hỗ trợ trả trạng thái rõ ràng, không bỏ ngầm bộ lọc hoặc tự suy ra số.

**Đề xuất mở rộng để tiến tới chat bao phủ deck:**

1. Ưu tiên C/F theo năm vì UI và reporting đã có. Kiểm công thức, đối chứng CSV, quyền đọc và bằng chứng trước khi mở tool.
2. Với phân rã giai đoạn và điểm tự tìm, giữ phương pháp/trạng thái nghiệp vụ đúng; không biến mục `closed` thành `open` chỉ bằng sửa enum.
3. Bộ lọc nhiều chiều và khoảng ngày tùy ý là mở rộng riêng, không phải điều kiện bắt buộc để trả lời đúng deck hiện tại.

**Nghiệm thu:** từng tổ hợp tool × metric × kỳ × bộ lọc có số đối chứng và kiểm câu trả lời; chạy model thật riêng để kiểm hiểu intent/chọn tool, không dùng FakeProvider thay thế.

### FB06 — Giữ rõ các quy ước còn là đề xuất và giới hạn suy luận

Các mục hiện còn nhãn đề xuất cần đối chiếu quyết định mới nhất trước khi xử lý:

- Năm ranh giới khi gom PS3 theo giai đoạn: hiện gán năm ranh giới cho giai đoạn kết thúc ở năm đó.
- Phân rã PS4 theo giai đoạn bằng cộng phần góp từng năm, khác phân rã một lần đầu → cuối.
- Ngưỡng `driver_rule.min_abs_delta_rate = 0.01` để đánh dấu ΔR nhỏ; đây không phải ngưỡng thống kê đã chứng minh.

**Yêu cầu:** giữ nhãn và phương pháp ở gần kết quả phụ thuộc quy ước; không tự ghi đã chốt. Nếu chưa có quyết định, vẫn hoàn thành các mục độc lập, chỉ hỏi đúng lựa chọn nghiệp vụ còn thiếu.

Giữ cảnh báo N → U → P phụ thuộc thứ tự, P chứa ảnh hưởng cơ cấu, C/F chưa đo churn. Mốc BA chọn không được mô tả thành thuật toán tự phát hiện; liên hệ lịch tháng 8 không được chuyển thành khẳng định nhân quả hay forecast.

### FB07 — Lỗi tái hiện: đổi backend bị timeout thì lịch sử AI chưa được xóa

**Kết quả quan sát:** sau một lượt chat trên DuckDB, chuyển sidebar sang PostgreSQL không kết nối được:

```text
Không đọc được build_info từ PostgreSQL (Docker): ConnectionTimeout.
backend = postgres
ai_backend = duckdb
len(ai_turns) = 1
```

Test chưa đạt: `apps/retail_app/tests/test_ai_chat.py::test_trang_chat_doi_backend_xoa_hoi_thoai`.

**Nguyên nhân theo thứ tự code:** `views/ai_explain.py` gọi `page_header()` trước đoạn reset hội thoại. `page_header()` gọi `info_strip()` → `load_or_stop('build_info')`; kết nối lỗi dẫn đến `st.stop()`, nên chưa chạy đoạn cập nhật `ai_backend` và xóa `ai_turns`/`ai_tokens`.

**Giới hạn phát hiện:** chứng minh state cũ còn sau chuyển nguồn thất bại; chưa chứng minh có câu trả lời sai nguồn được hiển thị hoặc gửi tới LLM trên production.

**Hướng sửa:** thực hiện chuyển/reset ngữ cảnh backend trước thao tác đọc dữ liệu có thể dừng trang. Có thể chuyển block reset lên trước `page_header()` hoặc xử lý tập trung khi đổi backend; chọn cách phù hợp cấu trúc hiện tại. Không xóa hội thoại trên mọi rerun cùng backend.

**Regression cần kiểm:**

- Chat DuckDB → chuyển backend mới bị lỗi kết nối: reset state về backend mới, không giữ evidence/turn cũ, không gọi LLM thêm.
- Chuyển sang backend kết nối thành công: vẫn reset.
- Rerun/đổi trang cùng backend: giữ lịch sử, không gọi lại LLM.
- Kết nối phục hồi sau lần chuyển lỗi: không khôi phục bằng chứng cũ của backend trước.
- Dùng lỗi kết nối giả lập có chủ đích để test không phụ thuộc PostgreSQL tình cờ đang bật/tắt.

## 6. Ví dụ đọc nối PS2 → PS4 → PS5

Đây là **số quan sát từ DuckDB local trong lượt review**, dùng minh họa cách đọc và phải đối chiếu lại nếu snapshot thay đổi; không phải xác nhận số trên cloud. Không hardcode vào sản phẩm.

| Góc nhìn | Số quan sát, làm tròn để trình bày | Diễn giải phù hợp |
|---|---|---|
| PS2, 2018 → 2019 | R khoảng 1.419,3 → 864,3 triệu; giảm 39,1% | Xác định quy mô biến động |
| PS4, cùng cặp năm | ΔR −554,9 triệu; phần N −572,4; U +2,6; P +14,9 triệu | Phần giảm tập trung ở số đơn; hai phần còn lại bù một phần |
| PS5, ngành hàng, cùng cặp năm | Streetwear −463,9 triệu; khoảng 83,6% mức giảm toàn công ty | Xác định ngành đóng góp nhiều tiền nhất vào mức giảm |

Các phần đã làm tròn có thể không cộng khớp chữ số cuối. Đối soát dùng độ chính xác gốc.

Câu diễn giải phù hợp: **“Biến động giảm tập trung ở số đơn và ngành Streetwear; lượng mua mỗi đơn và giá bình quân bù lại một phần.”** Đây là hai cách nhìn bổ sung của cùng biến động, không cộng phần Streetwear với phần N.

Không được tự kết luận “marketing kém làm mất khách” hoặc “tăng giá sẽ khắc phục”. Cần bằng chứng khác cho nguyên nhân và hiệu quả hành động.

Nguồn chạy lại: `queries.revenue_yearly('duckdb')` lọc 2018/2019, và `queries.segment_yearly('duckdb')` lọc năm 2019, `dimension_name == 'category'`. Các test đối chứng liên quan ở `test_ai_tools.py`, kiểm UI ở `test_m4.py`. Khi đưa ví dụ thành kết luận phân tích chính thức trong tài liệu/slide, đối chiếu cell thích hợp của `notebooks/02_design/star_schema_validation.ipynb`; nếu thiếu, phối hợp người phụ trách bổ sung cell chạy lại được theo quy ước repo.

## 7. Bằng chứng test của lượt review

Lệnh ban đầu, chạy từ root:

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest apps/retail_app/tests/test_m1.py apps/retail_app/tests/test_m2.py apps/retail_app/tests/test_m3.py apps/retail_app/tests/test_m4.py apps/retail_app/tests/test_ai_tools.py apps/retail_app/tests/test_ai_tools_ps123.py apps/retail_app/tests/test_ai_chat.py -q -k "not postgres and not _pg_"
```

- Kết quả ban đầu: **263 passed, 1 failed, 7 errors, 110 deselected**.
- 7 errors là lỗi quyền thư mục tạm của sandbox, không phải sai số KPI. Chạy lại 7 ca đó ngoài sandbox: **7 passed**.
- Ca chuyển backend chạy lại vẫn failed; đã tái hiện nguyên nhân ở FB07.
- Tổng kết trên các ca đã chọn: **270 ca đạt, 1 ca chưa đạt**. Không phải toàn bộ test repo đạt.
- Biểu thức `-k` loại test có tên/id PostgreSQL; riêng ca chuyển backend vẫn chạm PostgreSQL trong thân test. Không gọi lượt chạy này là kiểm hoàn toàn chỉ DuckDB hoặc là nghiệm thu đầy đủ PostgreSQL.
- Test tool có đối chứng từ CSV; `test_ai_chat.py` dùng **FakeProvider**, không gọi model thật.
- Không dùng số test trên để khẳng định deployment, quyền cloud hoặc chất lượng LLM hiện tại.

## 8. Bộ câu hỏi nghiệm thu tối thiểu sau sửa

| Ca | Câu hỏi/thao tác | Điều kiện đạt |
|---|---|---|
| AC01 | R và G năm 2019 là bao nhiêu? | Đúng metric, năm, đơn vị và nguồn; không tráo R/G |
| AC02 | G−R năm 2019 gồm những khoản nào? | Bốn phần cộng đúng chênh gốc; không gọi toàn bộ là thất thoát |
| AC03 | R/G 76% có nghĩa mất 24% tiền không? | Không xác nhận số người dùng là bằng chứng; làm rõ kỳ và ý nghĩa thành phần |
| AC04 | Công ty thu tiền tháng này bao nhiêu? | Phân biệt dòng tiền với R theo order_date; không lấy lịch sử tới 2022 trả cho hiện tại |
| AC05 | Giai đoạn nào giảm mạnh nhất, theo chỉ tiêu nào? | Nêu rõ CAGR/tổng thay đổi hay tiêu chí khác; xếp hạng theo bằng chứng tương ứng |
| AC06 | Tháng thấp theo mùa có phải kinh doanh sa sút? | Dùng chỉ số tháng và so cùng kỳ phù hợp; không suy từ giảm tháng liền trước |
| AC07 | Doanh thu cuối tháng tập trung thế nào? | Đúng ngày ≥26, mẫu số tháng, mức rải đều theo D và đơn vị điểm % |
| AC08 | Tháng 8 năm lẻ luôn thấp, vậy năm sau chắc giảm? | Tách quan sát lịch sử, độ ổn định và giới hạn dự báo |
| AC09 | Vì sao R năm 2019 giảm? | Đúng ΔR và phần N/U/P; gọi là phân rã, không dựng nguyên nhân |
| AC10 | Ngành nào giảm nhiều nhất/ít nhất năm 2019? | Xếp theo số tiền đúng hướng; tên nhóm gắn đúng hàng bằng chứng |
| AC11 | Số đơn thay đổi do số khách hay tần suất? | UI nêu toàn công ty; chat trả đúng nếu đã mở tool, còn đóng thì báo chưa hỗ trợ |
| AC12 | Streetwear tại East trong một khoảng ngày tùy ý? | Không bỏ filter; nếu ngoài khả năng thì từ chối rõ |
| AC13 | Mẫu số 0, thiếu kỳ trước, năm 2012 | Không tạo 0%/infinity hoặc so năm thiếu với năm đủ |
| AC14 | Đổi backend khi nguồn mới timeout | Đạt các điều kiện reset và giữ ngữ cảnh ở FB07 |
| AC15 | C giảm tức là khách rời bỏ? P tăng tức là tăng giá? | Không đồng nhất các khái niệm; giải thích giới hạn của C và P |

Expected numbers phải lấy từ đối chứng độc lập trên cùng snapshot. Kiểm UI bằng AppTest và kiểm trực quan phần thay đổi. Khi chạy trên deployment, ghi URL/mốc deployment, backend, snapshot, kỳ/filter và kết quả thật; khi đánh giá LLM ghi model/config và các câu đạt/chưa đạt. Một lần trả lời đúng không chứng minh mọi cách hỏi đều đúng.

## 9. Hướng dẫn Claude thực hiện và bàn giao

1. Đọc note và kiểm trạng thái hiện tại trước khi sửa. Trong lượt tạo note đã có thay đổi của người dùng ở `docs/dwh_huong_dan_pm_ba.md`, `docs/streamlit_cloud_deploy.md` và xóa `relational diagram.drawio.svg`; không ghi đè/khôi phục các thay đổi đó.
2. Dùng tập skill phù hợp: `retail-metric-design`, `retail-bi-product`, `retail-ai-explain`, `developing-with-streamlit`. Nếu mở tool/đổi model thì thêm skill engineering liên quan. Giữ nguyên công thức đã chốt trong các sửa đổi lời giải thích.
3. Thực hiện FB01–FB04 và FB07; FB05 công bố phạm vi ngay, tách rõ phần mở rộng; FB06 giữ trạng thái quyết định và chỉ hỏi phần business chưa chốt khi cần.
4. Khi gặp quyết định đã được người dùng chốt sau ngày note, dùng quyết định mới và ghi căn cứ; không hỏi lại hoặc áp dụng note máy móc.
5. Chạy kiểm tra phù hợp thay đổi và bộ câu hỏi §8. Nếu sửa SQL, bổ sung kiểm grain/khóa/đối soát và dbt tương ứng. Không sửa expected numbers chỉ để test xanh.
6. Để kết quả local có thể review trước khi publish. Note không xác nhận quyền deploy, commit/push hoặc gọi API có chi phí; đối chiếu phạm vi người dùng đã giao trong phiên thực hiện, không tự tạo vòng hỏi lại nếu đã có quyền.
7. Bàn giao bảng **mã feedback → thay đổi → file → bằng chứng → trạng thái**, phân biệt đã sửa local, đã kiểm local, đã kiểm cloud, đã đánh giá LLM thật và phần còn chờ quyết định. Kèm ảnh phần UI/slide sửa khi có thể.

Mục tiêu nghiệm thu cuối cùng: với từng câu hỏi của slide, người xem thấy **câu trả lời, con số đúng kỳ/bộ lọc, ý nghĩa KPI và giới hạn kết luận**; AI giữ cùng định nghĩa và nói rõ những câu chưa hỗ trợ.
