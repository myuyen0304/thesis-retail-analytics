# Hỏi đáp: nhập dữ liệu trên web và auto mapping

Ghi chú hỏi đáp của PM, soạn 2026-10-31. Tài liệu đi kèm: [giao_viec_nhap_du_lieu_ui.md](giao_viec_nhap_du_lieu_ui.md) (phiếu
nhập UI), [thiet_ke_nap_ky_moi.md](thiet_ke_nap_ky_moi.md) (nạp kỳ mới), [tien_hoa_schema.md](tien_hoa_schema.md) (thiết kế
tiến hóa schema). Ví dụ dùng file `orders_enriched` (khóa `order_id`).

---

## 1. Có đảm bảo khóa chính (PK) không bị trùng trong DWH không?

**Có.** Trùng khóa bị chặn ở 4 lớp, từ lúc đề xuất ánh xạ tới lúc công bố. Không lớp nào tự "sửa" hay tự chọn bản thay người.

| Lớp | Lúc nào | Kiểm gì | Gặp vi phạm thì sao |
|---|---|---|---|
| 0. Đề xuất | Auto mapping, trước khi DE duyệt (`auto_mapping.key_conflicts`) | Bao nhiêu khóa của file trùng khóa đã có trong kho, bao nhiêu trùng mà khác nội dung | DE thấy ngay trong báo cáo. Vd. `epd.json`: 998 id trùng `products` nhưng khác tên/giá → từ chối; `orders_enriched`: 0 id trùng khác nội dung |
| 1. Cách ly lúc nạp | Stage `prepare` (`scripts/ingest/extension_prepare.py:72–103`) | **R1** khóa rỗng/sai kiểu; **R2** trùng khóa ngay trong file; **R3** khóa không có trong nguồn lõi (đơn "mồ côi"); **R4** cột trùng tên với kho mà giá trị khác; **R6** cùng một nhân viên mà thuộc tính mâu thuẫn | Dòng vi phạm vào cách ly. R2 loại **mọi bản trùng**, không giữ bản đầu. Vượt **1%** số dòng → dừng cả lượt |
| 2. Test dbt | Stage `build` | `fact_order.order_id` `unique` + `not_null` (`retail_dbt/models/marts/*.yml:82–83`); `assert_sales_employee` (khóa thay thế và mã nhân viên không trùng); `assert_order_sales_employee` (mỗi đơn tối đa một nhân viên) | Test lỗi → `validate` lỗi → **không công bố được** |
| 3. Cách nạp | Mỗi lượt chạy | Build lại kho từ đầu theo `release_id`, không cộng dồn | Chạy lại cùng một file hai lần cũng không nhân đôi dòng |

**Ví dụ:** file có 2 dòng cùng `order_id = 1001` → cả 2 dòng vào cách ly với lý do `R2_trung_khoa`; phần còn lại vẫn chạy nếu số
dòng lỗi dưới 1%; DE xem file cách ly trong "Báo cáo kỹ thuật đầy đủ".

**14 nguồn lõi** (orders, order_items, …): chặt hơn, ngưỡng **0** (`scripts/pipeline/contract.py`): một dòng sai khóa là dừng cả
lượt, vì doanh thu G/COGS phải khớp đúng `sales`.

**Đợt năm mới** (lát D2, chưa làm): thêm luật khóa của đợt không trùng bản gốc và không trùng trong đợt, ngưỡng 0
([thiet_ke_nap_ky_moi.md](thiet_ke_nap_ky_moi.md) §4.3).

---

## 2. DE bấm Duyệt rồi luồng làm gì tiếp, Quản lý thấy dữ liệu đã nạp ở đâu?

### Luồng sau khi duyệt

| Bước | Ai | Trang | Việc | Trạng thái sau bước |
|---|---|---|---|---|
| 1. Gửi | Quản lý (chủ shop) | Gửi dữ liệu | Tải file CSV/JSON ≤ 200 MB; hệ thống chạy auto mapping và sinh đề xuất | Chờ duyệt (hoặc Lỗi đề xuất) |
| 2. Duyệt | DE | Duyệt dữ liệu | Xem đề xuất, chỉnh từng cột (đưa vào mart/silver/bỏ, kiểu, được rỗng); bấm Duyệt → ghi hợp đồng | Đã duyệt (hoặc Chờ model dbt nếu nguồn chưa có model) |
| 3. Chạy | DE | Duyệt dữ liệu | Bấm Chạy → worker chạy nền 4 stage: **prepare** (chụp snapshot, cách ly dòng lỗi) → **forecast** (dự báo, ~6 phút†) → **build** (dbt dựng kho + test) → **validate** (đối soát G/COGS, kiểm test) | Đang chạy → Đã kiểm (hoặc Lỗi khi chạy) |
| 4. Công bố | **Chỉ Admin** | Duyệt dữ liệu | Bấm Công bố bản đã kiểm (`views/duyet_du_lieu.py:124`) | Đã công bố |

Công bố ở đây cập nhật **kho nhập dữ liệu local** (`warehouse/pipeline/ui-nhap`); kho báo cáo app đang đọc giữ nguyên cấu hình
(`views/duyet_du_lieu.py:15`). Chỉ chạy ở app local + DuckDB, không chạy trên Streamlit Cloud.

### Quản lý thấy ở đâu

- **Trang Gửi dữ liệu:** danh sách yêu cầu của mình, mỗi yêu cầu có trạng thái (Chờ duyệt, Đang chạy, Đã công bố, Từ chối kèm lý
  do…) và **tóm tắt nghiệp vụ** dễ đọc (`tom_tat_nghiep_vu`), không có chi tiết kỹ thuật.
- **Số liệu các trang PS không đổi khi nạp `orders_enriched`:** file này chỉ thêm **chiều nhân viên bán hàng** cho đơn đã có, không
  thêm hay sửa doanh thu. G/COGS vẫn như cũ (đó cũng là điều cổng `validate` kiểm).
- **Muốn thấy dữ liệu nhân viên vừa nạp:** chạy app ở chế độ versioned trỏ vào registry `ui-nhap` (`RETAIL_RELEASE_MODE=versioned`,
  `RETAIL_RELEASE_STATE=warehouse/pipeline/ui-nhap/state.json`) — **chưa thử thật**, là một bước trong nghiệm thu §6. Trang PS hiện
  chưa có biểu đồ theo nhân viên (lát 5 đã bỏ, phạm vi auto mapping chỉ cho DE).
- **Muốn dashboard đổi số khi nạp dữ liệu năm mới:** cần các lát D1–D5 ([thiet_ke_nap_ky_moi.md](thiet_ke_nap_ky_moi.md)).

† Số đo một lần trên laptop (lượt nghiệm thu 2026-10-31, log 16:10:42 → 16:16:43), chưa phải số đo lặp lại.
