# Gate chất lượng theo thay đổi

## Chọn test có ý nghĩa

| Thay đổi | Kiểm bắt buộc theo rủi ro |
|---|---|
| Grain/key/join | Unique key, FK, số dòng trước/sau join, bảo toàn measure; ví dụ đơn có nhiều dòng cùng product |
| R/G | Đối soát từng kỳ/tập lọc với CSV độc lập; returned không bị trừ refund lần hai |
| Tỷ lệ/distinct | Tính lại tử/mẫu, khách lặp qua tháng/category, mẫu số 0 và nhóm rỗng |
| PS4/PS5 | Thứ tự phân rã theo hợp đồng, tổng đóng góp khớp delta; ba chiều PS5 là ba lát cắt |
| Backend | Types/precision, rounding, NULL, case, date và identity; so khóa/row trước KPI |
| Incremental | Chạy lại không thêm trùng; update/late event sửa đúng partition/kỳ; kết quả khớp full rebuild |

Số test, số dòng và tổng snapshot chỉ là bằng chứng của lần chạy cụ thể, không phải tiêu chí bất biến cho dữ liệu mới. Không cập nhật expected để che regression.

## Bằng chứng bàn giao

Ghi code revision hoặc hash các file đổi khi checkout dirty, manifest snapshot, target/database/schema, thời gian/lệnh chạy và artifact chất lượng. So sánh bảng như multiset theo key, không phụ thuộc thứ tự SELECT. Kiểm count/duplicate/null trước tổng tiền.

Tiền/số đếm dùng exact comparison sau chuẩn hóa kiểu theo hợp đồng; float-derived metric chỉ dùng tolerance được giải thích cho từng cột. Không làm tròn toàn bộ để che sai khác. Tổng toàn kỳ khớp không thay thế đối soát từng tháng/nhóm và grain.

Khi sửa logic rủi ro cao, thử một lỗi có chủ đích trong fixture/bản sao để chứng minh test bắt sai, không sửa dữ liệu hay database đang phục vụ app.
