# Checklist bằng chứng phân tích

- Nêu câu hỏi và định nghĩa metric trước bảng số. Kỳ chính của PS1–PS5, kỳ thiếu và rolling window lấy từ hợp đồng trong `docs/star_schema.md`.
- Ghi file nguồn/version, hash khi cần tái lập, bộ lọc, grain và cardinality join. Giữ raw bất biến.
- Phân biệt kiểm nội bộ giữa fact dẫn xuất với kiểm độc lập từ CSV. Hai model dùng chung công thức sai vẫn có thể khớp nhau.
- Mỗi cell có nhận xét hữu ích về kết quả vừa chạy; không hardcode lời kết luận trái output. Không cần lặp lại boilerplate cho cell chỉ cấu hình.
- Tách ba mức: số quan sát được; phân rã số học theo công thức; giả thuyết business cần dữ liệu bổ sung. Không dùng “do”, “gây ra” nếu chưa có thiết kế xác định nhân quả.
- Khi thấy dữ liệu trái kết luận lịch sử, chỉ ra nguồn/cell và khác biệt snapshot; kiểm trước khi sửa định nghĩa.
- Không khẳng định đơn vị tiền, khu vực giao hàng hoặc trạng thái lịch sử nếu nguồn chỉ có nhãn/snapshot hiện tại.
- Kết thúc bằng câu trả lời cho câu hỏi, bằng chứng chính, điều chưa kết luận được và cách kiểm tiếp có mục đích.
