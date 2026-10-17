# Kiểm lại AI GĐ2, RV12 và đường chạy local/cloud — 17/10/2026

Phạm vi: code và test app local, phát lại câu trả lời của model thật, tool/chat đọc Databricks, và đường truy cập ẩn danh của Streamlit Community Cloud. Kiểm tại checkout `app/myuyen`, HEAD `532b240`; các sửa của Codex ở `evidence.py` và `test_ai_forecast.py` đang nằm trong working tree, **chưa commit hoặc deploy**. Không gộp kết quả ở đây với bằng chứng rằng bản public đang chạy code mới.

## 1. RV12: lỗi tái hiện và sửa

- Câu hỏi đồng thời hỏi dự báo năm 2025 và xin tháng 08/2023 làm mốc tham khảo. Trước sửa, status `ok` cho phép câu “Số này là dự báo năm 2025” ngay sau số tháng 08/2023. Probe độc lập ghi `status=ok`, `wrong_visible=True`, `validation_errors=[]`.
- Nhánh khác `ok` cũng từng bỏ khuôn vì câu hỏi đã tự nêu tháng 08/2023. `reference_refs` nay nhận biết câu có cả kỳ thiếu số lẫn kỳ tham khảo; app dựng câu ngoài vùng và dòng số tham khảo từ bằng chứng. `_coverage_line` chỉ gọi kỳ thiếu số là ngoài vùng.
- Với câu hỏi hỗn hợp có một kỳ **nằm hẳn ngoài** vùng dự báo và một kỳ **giao với** vùng dự báo, `ok` bị từ chối, yêu cầu model trả `no_data`. Điều này tránh việc câu sau gán lại số tham khảo cho kỳ thiếu số. Câu chỉ hỏi một kỳ hoặc năm 2024 có dự báo một phần vẫn theo luật cũ.
- `_said` ưu tiên kỳ ghi ngay sau placeholder thứ hai trong câu “{c1} cho tháng 01/2023 và {c2} cho tháng 02/2023”, sửa ca GM10 bị chặn nhầm.

**Bằng chứng sau sửa:** `test_ai_forecast.py` **258/258**, probe RV12 cũ **231/231**, probe hai kỳ: ba câu `no_data` hiện khuôn đúng kỳ và câu `ok` gán sai bị chặn. Test mới cũng khóa đường sửa `ok` → `no_data` khi số tham khảo là năm 2024 chỉ có dự báo một phần. Ba câu chạy DeepSeek thật đều `no_data` với số tham khảo tháng 08/2023 đúng nhãn; hai câu cần một lượt sửa status, một câu trả đúng ngay. Log: `warehouse/reviews/rv12_live_new_20261017.json`. Các probe nằm trong `warehouse/reviews/` (ignored).

**Giới hạn:** quy tắc status mới giải quyết câu hỏi có kỳ thiếu số và kỳ tham khảo. Nó không chứng minh mọi cách diễn đạt RV12 của model đều an toàn. Bộ 231 ca cũ không chứa chính câu hỗn hợp mới; ca mới được khóa riêng trong `test_ai_forecast.py`. Nhánh `ok` đơn kỳ với số tham khảo đúng nhãn vẫn giữ theo quyết định §9.10 của biên bản trước.

## 2. Hồi quy local và model thật

| Phép kiểm | Kết quả | Giới hạn |
|---|---:|---|
| `pytest -q apps/retail_app` | **884 passed, 110 skipped, 0 failed** | Chạy trên bản trước thay đổi nhỏ cuối cùng từ “kỳ nằm trọn trong vùng” sang “kỳ giao vùng”. 110 ca cloud skip theo cấu hình mặc định. |
| `pytest -q apps/retail_app/tests/test_ai_forecast.py` | **258 passed** | Chạy lại sau thay đổi cuối cùng. |
| Probe RV12 §9.10 | **231/231** | Provider giả, trước thay đổi nhỏ cuối cùng. |
| DeepSeek GM | **14/15** lần đầu; GM10 **3/3** sau sửa | Lần đầu GM10 bị chặn nhầm; 14 ca còn lại chưa phát lại sau sửa. |
| DeepSeek V | **6/7** theo tiêu chí máy cũ | V03, V05 có câu và biểu đồ/ghi chú đúng; V06 dùng biểu đồ chuỗi R 10 năm mới nên rubric cũ đòi tool cũ và chấm trượt. |
| DeepSeek N | **5/5** | Mỗi câu một lượt, chưa đủ để đo tính ổn định. |
| DeepSeek G07 | **3/3** | Model không dẫn số kỳ khác trong ba lượt, nên chưa thử khuôn RV12. |
| DeepSeek RV12 hai kỳ | **3/3** trả `no_data` | Chạy trước thay đổi nhỏ cuối cùng; các câu này đã thuộc điều kiện cũ lẫn mới. |

Log model thật nằm trong `warehouse/ai_eval/live_20261017T*_*.jsonl` và `warehouse/reviews/rv12_live_new_20261017.json`. Test giả chứng minh bộ kiểm và hiển thị với đầu vào đã biết; lượt live chứng minh model đã tạo ba câu được xử lý đúng, không phải chứng minh mọi câu tương lai.

## 3. Databricks: đã kiểm đọc thật

- `retail-dev` xác thực được. Databricks App `retail-analytics` ở trạng thái **STOPPED**; đây là app compute khác với website Streamlit Community Cloud.
- Service principal AI đọc được release đang active `cfe19211211e420abdfcabb3`. Schema legacy `retail_lab.reporting` không có `rpt_forecast_daily`; bảng forecast nằm trong schema reporting của release versioned. Kiểm theo `retail_control.state`, không theo schema legacy.
- Đã chạy **83 ca cloud** so sánh tool với DuckDB trước hai commit guard cuối ngày: tất cả đạt. Probe cuối ngày gọi `service.run_turn` bằng provider giả trên backend Databricks sau sửa guard: `get_forecast(G, tháng 08/2023)` trả `ok`, câu chat hiện **74.151.832 VND**, không có `GuardError`. Probe: `warehouse/reviews/cloud_chat_smoke_20261017.py`.
- Số G tháng 08/2023 và 15 dòng backtest kiểm trực tiếp bằng tool là bằng nhau giữa local và cloud. `model_version` khác (`a78d5b07d43c` local, `3ac33fc83143` cloud), vì hai release khác nhau; không gọi đây là đồng nhất toàn bộ metadata.

## 4. Website public: còn chặn nghiệm thu

- URL `https://retail-analytics-ps.streamlit.app/` trả HTML shell 200, nhưng kết nối ẩn danh tới `/_stcore/stream` bị **HTTP 303** chuyển sang `share.streamlit.io/-/auth/app`. Kiểm lại cuối ngày vẫn như vậy. Theo đường ẩn danh, chưa vào được phiên Streamlit, nên không thể nghiệm thu UI/chat, source commit đang deploy, hay DeepSeek public.
- Tài liệu `streamlit_cloud_deploy.md` mô tả bước phải đặt Sharing = “This app is public and searchable”; cần người có quyền app kiểm tra setting này, sau đó mở cửa sổ ẩn danh và xác nhận WebSocket kết nối, trang PS1–PS5 và chat thật. Nếu chủ ý để private, sửa lại mô tả “public, ai cũng xem được”.
- `200` ở `/` hoặc `/_stcore/health` chỉ chứng minh lớp HTTP trả lời, **không chứng minh app đã chạy**. Không có hành động đổi sharing, redeploy hoặc sửa tài nguyên cloud trong lượt kiểm này.

## 5. Việc còn lại để nghiệm thu

1. Chủ app Streamlit xác nhận chế độ chia sẻ theo mục tiêu public, mở thử ẩn danh và cung cấp log/runtime nếu còn redirect. Chỉ sau đó mới kiểm được bản deploy thật và chat public.
2. Sau khi đưa code sửa RV12 lên nhánh đang deploy, đối chiếu commit chạy trên Streamlit Cloud và phát lại ba câu RV12 hai kỳ qua giao diện public. Code local chưa có hiệu lực trên public.
3. Cập nhật rubric V06 thành phiên bản mới nếu muốn chấm biểu đồ chuỗi R 10 năm; giữ kết quả bộ V cũ để so sánh lịch sử.

Các kết quả trong tài liệu này là ảnh chụp tại 17/10/2026; trạng thái app, quyền và release cloud có thể đổi sau thời điểm kiểm.
