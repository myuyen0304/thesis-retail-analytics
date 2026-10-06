# Feedback card và biểu đồ Streamlit PS1–PS5

Ngày soạn: **2026-10-01**. Người thực hiện tiếp: **Claude**.

## 1. Mục tiêu và căn cứ

Hoàn thiện cách trình bày để người xem đọc đúng chỉ số, kỳ so sánh và phần đóng góp ngay trên card/biểu đồ.

Nguồn nghiệp vụ: [revenue_performance_problem_statement_updated.pptx](presentations/revenue_performance_problem_statement_updated.pptx), gồm nội dung và ghi chú của 15 slide.

Căn cứ review:

- Code trong `apps/retail_app/views/`, `ui/` và truy vấn `dwh/`; kiểm lại các vị trí feedback ngày 2026-10-01.
- Ảnh trong `docs/screenshots/streamlit/` chụp ngày 2026-09-28 và 2026-09-29. Ảnh là bằng chứng bố cục tại thời điểm chụp; đối chiếu code mới trước khi sửa.
- Đợt verify ngày 2026-09-30: **141 test PASS** trên PostgreSQL/DuckDB; đối soát độc lập các KPI chính với CSV khớp. Đây là kết quả trước khi thực hiện feedback, không thay cho kiểm thử sau sửa.
- Đã xem ảnh có sẵn; chưa nghiệm thu bố cục phiên bản mới bằng trình duyệt trực tiếp.

Kết luận review: loại biểu đồ nhìn chung phù hợp với cả 5 PS. Trọng tâm đợt này là nhãn, đơn vị, cách nhấn mạnh và khả năng so sánh trực quan.

Claude dùng `retail-bi-product` trong `.agents/skills/` và `developing-with-streamlit`, đọc quy ước repo cùng phần cập nhật mới nhất của `docs/gd2_app_plan.md` trước khi thực hiện.

## 2. Thứ tự thực hiện

| Thứ tự | Mục | Kết quả cần đạt |
|---|---|---|
| 1 | F01 — Card PS4 | Phân biệt mức doanh thu R với thay đổi ΔR |
| 2 | F02 — Card PS2 | Đọc ngay được CAGR là tốc độ trung bình năm |
| 3 | F03 — Card PS5 | Nhóm nổi bật đi kèm số tiền và phần đóng góp |
| 4 | F04 — Heatmap PS3 | Cùng giá trị chỉ số tháng có cùng màu giữa hai biểu đồ |

Các mục F01–F04 là checklist thực hiện chính. Các đề xuất ở §4 là tùy chọn; cân nhắc sau khi hoàn tất checklist chính, tránh làm trang dài thêm khi chưa có lợi ích rõ.

## 3. Checklist thực hiện chính

### F01 — PS4: card đang ghi R nhưng hiển thị ΔR

**File:** `apps/retail_app/views/ps4_don_mon_gia.py`, card `kpi(c0, 'Doanh thu R', ...)`.

**Hiện trạng:** nhãn `Doanh thu R`, số lớn lấy từ `row['delta_r']`. Ví dụ năm 2019 hiển thị `−554,9`. Đơn vị triệu và giải thích đã có ở ngoài card, nhưng nhãn riêng của card vẫn dễ làm người đọc hiểu là doanh thu âm.

**Thực hiện:**

- Đổi nhãn ngắn thành **Thay đổi R** hoặc **Chênh doanh thu**.
- Đơn vị triệu và kỳ đầu → cuối phải nhìn thấy ngay cạnh hàng card. Có thể giữ đơn vị ở tiêu đề chung để số không bị cắt khi có bốn card trên một hàng.
- Giữ ba card N/U/P thể hiện đóng góp bằng tiền. Dòng % phải ghi rõ là tăng trưởng của chính yếu tố; các % này không cộng thành % tăng trưởng R.
- Với kỳ giai đoạn, giữ giải thích: số tiền là cộng đóng góp từng năm, còn % là so năm cuối với năm đầu.

**Nghiệm thu:**

- [ ] Năm 2019: ΔR `−554,9` triệu, đóng góp N `−572,4`, U `+2,6`, P `+14,9` triệu; chỉ đổi cách trình bày.
- [ ] Người xem phân biệt được số lớn bằng tiền với dòng % mà không cần mở tooltip.
- [ ] Thẻ còn đọc đủ nhãn, số và đơn vị khi mở sidebar ở kích thước màn hình demo.
- [ ] Kiểm cả một năm và một giai đoạn; cập nhật kiểm tra nhãn trong `tests/test_m4.py`.

### F02 — PS2: đưa ý nghĩa CAGR lên hàng card

**File:** `apps/retail_app/views/ps2_xu_huong.py`, vòng lặp card theo `phase`.

**Hiện trạng:** card ghi tên giai đoạn và phần trăm, còn chữ CAGR nằm trong tooltip. Ví dụ `+8,75%` của A có thể bị hiểu là tăng tổng giai đoạn, trong khi đó là tăng trưởng trung bình năm.

**Thực hiện:**

- Ghi rõ **CAGR — tăng trưởng trung bình năm** ở tiêu đề hàng card hoặc ghi CAGR trên từng card.
- Hiển thị đơn vị `%/năm` ở vị trí nhìn thấy được; giữ rõ khoảng năm.
- Nếu bổ sung mức thay đổi cả giai đoạn, ghi nhãn riêng **Tổng thay đổi** và lấy từ `total_change_rate`.
- Giữ nhãn ngắn; không nhét toàn bộ giải thích vào bốn card.

**Nghiệm thu:**

- [ ] A 2013–2016: người xem phân biệt `+8,75%/năm` với mức tăng cả giai đoạn khoảng `+28,6%`.
- [ ] C 2018–2019: CAGR trùng tăng trưởng một năm; nhãn vẫn nhất quán.
- [ ] Mọi số lấy từ reporting, không hardcode ví dụ trong feedback.
- [ ] Cập nhật `tests/test_m2.py` và chụp lại hàng card.

### F03 — PS5: card nhóm phải trả lời thêm “bao nhiêu?”

**File:** `apps/retail_app/views/ps5_nhom.py`, hai card tăng nhiều nhất/giảm nhiều nhất.

**Hiện trạng:** card chỉ hiện tên nhóm; số tiền nằm trong tooltip và biểu đồ phía dưới. Người xem chưa đọc được ngay độ lớn đóng góp từ hàng card.

**Thực hiện:**

- Hiện **tên nhóm + ΔR bằng tiền**; có thể chia thành nhãn, số lớn và dòng phụ để tránh cắt chữ.
- Dòng phụ ghi `% đóng góp vào mức đổi tổng` từ `contribution_to_delta`, khi có thể diễn giải được.
- Ví dụ bố cục cho năm 2019: `Nhóm kéo giảm mạnh nhất` → `Streetwear` → `−463,9 triệu · 83,6% mức giảm toàn công ty`. Đây là minh họa nội dung, không bắt buộc ghép thành một dòng dài.
- Giữ trạng thái **Không có nhóm tăng/giảm** khi phù hợp với dữ liệu; không đổi một nhóm giảm ít thành nhóm tăng.
- Tổng ΔR bằng 0: ghi không xác định cho % đóng góp. Khi `delta_r_is_small` là true: ưu tiên số tiền, ghi rõ % không ổn định hoặc ẩn % trên card.
- Giữ dấu của % đóng góp khi âm hoặc trên 100%; không giới hạn vào 0–100%.

**Nghiệm thu:**

- [ ] Năm 2019, ngành hàng: Streetwear `−463,9 triệu`, khoảng `83,6%` mức giảm tổng; không có ngành hàng tăng.
- [ ] Chuyển năm và cả ba chiều thì tên nhóm, số tiền và phạm vi dòng phụ cùng đổi.
- [ ] Năm có ΔR tổng rất nhỏ, như 2015, không làm % lớn bất thường trở thành thông tin nổi bật thiếu cảnh báo.
- [ ] Phần C/F bên dưới tiếp tục ghi rõ **toàn công ty**; bộ chọn chiều phía trên chỉ tác động phần phân nhóm.
- [ ] Cập nhật `tests/test_m4.py`; kiểm thêm trạng thái không có nhóm tăng/giảm và mẫu số 0 bằng kiểm tra có ý nghĩa nếu chưa có.

### F04 — PS3: thống nhất thang màu chỉ số tháng

**File:** `apps/retail_app/views/ps3_nhip_lich.py`, heatmap tháng × năm và tháng × giai đoạn.

**Hiện trạng:** cả hai dùng `domainMid=1` nhưng chưa có miền màu chung; mỗi biểu đồ tự lấy khoảng dữ liệu và đang ẩn legend. Cường độ màu vì vậy chưa được bảo đảm tương đương giữa hai biểu đồ. Khoảng dữ liệu hiện tại khá gần nhau, nên đây là cải thiện khả năng so sánh.

**Thực hiện:**

- Dùng cùng miền màu, điểm giữa 1 và bảng màu cho **hai heatmap của `month_index`**. Xác định miền chung từ cả hai tập dữ liệu hoặc dùng một cấu hình chung bao phủ dữ liệu.
- Hiện chú giải định lượng: `1 = mức trung bình tháng trong năm/giai đoạn`; ghi rõ hai mẫu số tương ứng khi giải thích.
- Giữ nhãn số trong ô, tooltip và độ tương phản chữ.
- Heatmap mức dồn cuối tháng dùng thang riêng theo **điểm %**, trung tâm 0. Không dùng chung thang với chỉ số tháng.

**Nghiệm thu:**

- [ ] Cùng một giá trị `month_index` ánh xạ ra cùng màu ở hai heatmap.
- [ ] Chú giải nhìn rõ; chữ trong ô đọc được trên nền đậm và nhạt.
- [ ] Không có giá trị bị bão hòa màu do miền cấu hình bỏ sót cực trị.
- [ ] Chỉ số, phân nhóm giai đoạn và các kết quả kiểm độ ổn định giữ đúng nguồn reporting.

## 4. Đề xuất tùy chọn theo từng PS

| PS | Phần nên giữ | Có thể cải thiện thêm |
|---|---|---|
| PS1 | Card R/G; thác G→R; chuỗi G/R; tỷ lệ hủy và chiết khấu | Ưu tiên R về thứ tự/nhấn mạnh. Chỉ rút gọn tiền thành tỷ/triệu nếu thật sự khó đọc; luôn giữ số đầy đủ để đối chiếu. Biểu đồ G–R theo năm đã có tại Tổng quan, không ghi thành thiếu yêu cầu. |
| PS2 | Đường R 12 tháng, nền giai đoạn, cột YoY | Bổ sung chú giải trực quan ngắn cho mốc BA và đỉnh/đáy dữ liệu tự tìm. Kiểm nhãn ở vùng nhiều mốc có chồng nhau không. |
| PS3 | Ba card tương ứng ba nhịp, heatmap, cột tháng 8 | Sắp card cùng thứ tự các phần bên dưới: mùa vụ → cuối tháng → tháng 8. Nếu đổi thì cập nhật test thứ tự tương ứng. |
| PS4 | Thác đóng góp; cột chồng âm/dương và điểm ΔR theo năm | Nếu cần đọc phần U/P nhỏ, bổ sung chế độ xem thanh đóng góp quanh 0. Giữ bảng số và trục đầy đủ của thác; tránh cắt trục để phóng đại đóng góp. |
| PS5 | Thanh ngang xếp hạng, đường tỷ trọng, thác C/F | Đường tỷ trọng cho thấy cơ cấu tốt nhưng nhóm nhỏ khó nhìn. Có thể thêm chế độ xem **dịch chuyển tỷ trọng của năm chọn**, dùng thanh quanh 0 và cột `share_shift_pp` có sẵn. Chỉ bổ sung nếu giúp trả lời câu hỏi nhanh hơn. |

Nếu thu gọn trang bằng expander, ưu tiên thu bảng chi tiết và giải thích kỹ thuật. Giữ kỳ phân tích, đơn vị, thông điệp chính và giới hạn thiết yếu gần biểu đồ.

## 5. Hợp đồng dữ liệu khi sửa giao diện

- Card và biểu đồ tiếp tục đọc lớp `dwh/queries.py` và `reporting.rpt_*`. Các số ví dụ trong file này là mốc đối chiếu, không phải giá trị để gõ vào UI.
- Định dạng và ánh xạ màu là trách nhiệm UI. Metric mới hoặc thay đổi công thức cần quay về model/reporting và kiểm chứng riêng.
- Giữ quy ước R/G, order_date, kỳ 2013–2022, YoY năm từ 2014, loại returned và đơn vị tiền tệ chưa xác định theo deck.
- Giữ grain hiện có: tháng/năm cho chuỗi; một kỳ cho phân rã; một chiều × nhóm × năm cho PS5. N/C phải là distinct ở đúng grain; không cộng distinct giữa các nhóm hoặc các tháng.
- Đợt feedback này tập trung trình bày. Tiếp tục dùng các quy ước giai đoạn đang áp dụng và ghi rõ chúng; không tự đổi định nghĩa khi chỉnh card.
- Dùng thành phần Streamlit có sẵn; cân nhắc độ dài tên nhóm và bố cục khi sidebar đang mở.

## 6. Kiểm tra và bàn giao

Sau khi sửa, chạy các test bị ảnh hưởng và smoke test. Với F01–F04:

```powershell
.venv/Scripts/python.exe -m pytest apps/retail_app/tests/test_m2.py apps/retail_app/tests/test_m3.py apps/retail_app/tests/test_m4.py apps/retail_app/tests/test_smoke.py -q
```

Nếu sửa thành phần chung hoặc thêm đề xuất PS1, mở rộng kiểm tra sang trang bị ảnh hưởng. Báo đúng backend đã chạy; lỗi kết nối không được ghi thành PASS.

Checklist bàn giao:

- [ ] Ghi rõ F01–F04 đã làm, mục tùy chọn nào được thực hiện và lý do.
- [ ] Test giữ kiểm tra giá trị/kỳ/phạm vi; thay đổi nhãn thì cập nhật kỳ vọng phù hợp, không bỏ kiểm tra số để làm test xanh.
- [ ] Có ảnh mới cho các trang thay đổi, kèm backend, kỳ và chiều đang chọn.
- [ ] Kiểm ở màn hình demo; nên thử thêm chiều rộng 1280 px với sidebar mở. Xác nhận card không cắt nhãn/số và chart không chồng nhãn.
- [ ] Nếu chưa kiểm trình duyệt, ghi rõ chỉ mới kiểm AppTest; test PASS chưa chứng minh bố cục dễ đọc.
- [ ] Liệt kê file đã sửa, lệnh test, kết quả và giới hạn còn lại trong báo cáo trả người dùng.

**Trạng thái khi tạo file:** đây là feedback bàn giao; chưa áp dụng các chỉnh sửa giao diện trong checklist.

**Cập nhật 2026-10-01:** dev đã làm F01–F04; chưa làm mục tùy chọn ở §4. Chi tiết, ảnh và kết quả kiểm ghi ở `dwh_huong_dan_pm_ba.md` §9, mục "2026-10-01: Sửa thẻ và bảng nhiệt PS2–PS5 theo feedback". Ô nghiệm thu để PM tự đánh dấu.
