# Databricks lab: DWH và KPI

## Mục đích và nguồn triển khai

Chạy cùng snapshot và hợp đồng nghiệp vụ của local; không xây production song song, không yêu cầu host app/chat trong lab. `archive/databricks/` chỉ tham khảo ý tưởng Bronze/Silver và identity; kiểm file thực tế trước khi tái sử dụng, không suy ra trạng thái từ README archive.

## Các bước khi được giao triển khai lab

1. Nếu có skill `databricks-core`, đọc trước thao tác CLI/auth; dùng skill chuyên biệt cho bundles/jobs/UC khi cần. Kiểm CLI/version, workspace edition, quyền và compute hiện có. Không suy đoán tài khoản Free Edition có mọi tính năng. Chọn profile đúng workspace với người dùng nếu chưa được chỉ định; giữ lựa chọn cho phiên làm việc.
2. Dùng môi trường dependency riêng khi adapter không tương thích với môi trường local. Kiểm hỗ trợ `dbt-databricks`/dbt thực tế; thêm target khi có thông tin connection. Profile dùng env/OAuth theo tài liệu hiện hành, không lưu token trong Git.
3. Upload snapshot version riêng vào landing được phép. Manifest ghi 14 nguồn của snapshot hiện tại, hash và thứ tự record; CSV có record nhiều dòng phải bảo toàn logical record identity. Không dùng thứ tự đọc Spark hay monotonically_increasing_id thay thứ tự nguồn.
4. Đưa raw vào Delta với source identity, rồi chạy cùng lớp staging/intermediate/marts/reporting. Kiểm macro dispatch rounding, cast/decimal, date, case và NULL; thêm nhánh Databricks chỉ nơi cần. Không đổi tên Silver thành tiêu chí nghiệp vụ thay grain.
5. Deploy/run trong namespace lab riêng; giữ version kết quả để gate/parity xong mới công bố. Ghi run/update IDs thật; chạy lại snapshot để chứng minh không nhân dòng.
6. Đối chiếu marts theo key và KPI PS1–PS5 với local. Kiểm từng kỳ/nhóm, distinct và tolerance có giải thích. Nếu loại compute không chạy được bước nào, ghi giới hạn và đưa phương án khả thi để chốt, không tự nâng gói/tạo compute lớn.

## Nguồn kỹ thuật

- [dbt Core trên Databricks](https://docs.databricks.com/aws/en/partners/prep/dbt)
- [Chỉ mục tài liệu Databricks](https://docs.databricks.com/llms.txt)

Chọn tài liệu đúng cloud/workspace tại lúc thực hiện; các liên kết không chứng minh môi trường người dùng đã sẵn sàng.
