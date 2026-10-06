# Kiểm trang BI

- Kiểm tiêu đề/câu hỏi, nhãn/đơn vị, kỳ lọc, legend, ordering và chart phù hợp câu hỏi; không tự ghi VND khi nguồn chưa xác nhận đơn vị.
- Với biến động, phân biệt chênh tiền, phần trăm và điểm phần trăm. Mẫu số 0 hiển thị không áp dụng, không thành 0% hoặc infinity.
- Bao phủ loading, empty, query error và stale snapshot; giữ lỗi connection có hướng xử lý, không hiện credentials.
- Với filter/drill-down, giữ nguyên context kỳ/chiều; đối soát về số reporting ở cùng grain. Không cho người dùng chọn filter mà query bỏ qua.
- Không vẽ quan hệ nhân quả từ phân rã số học. PS5 hiển thị từng chiều riêng, không cộng category/region/channel.
- Kiểm số app lấy bằng đối chứng DWH và kiểm rendering bằng AppTest. Test app=reporting không tự chứng minh nguồn đúng; cần gate dbt/nguồn.
- Chỉ chạy backend có cấu hình phù hợp, ghi backend bị thiếu; không giả PASS khi app chỉ hiện thông báo lỗi.
- App local dùng Streamlit hiện tại; Snowflake hosting, Databricks hosting và đăng nhập không tự thuộc phạm vi sửa trang.
