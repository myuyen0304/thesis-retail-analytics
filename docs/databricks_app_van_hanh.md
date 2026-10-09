# Vận hành app `retail-analytics` trên Databricks — tự bật lại khi app dừng

Tài liệu cho PM tự xử lý khi mở link app mà gặp màn hình **"App Not Available"**, không cần nhờ người khác.
Phần lớn trường hợp chỉ cần **bật lại** (mục 2). Không phải sửa code, không phải tạo lại khóa.
App này chỉ người đăng nhập workspace mới xem được; bản public (ai cũng xem) chạy trên Streamlit Community Cloud,
xem `docs/streamlit_cloud_deploy.md`.

| | |
|---|---|
| Link app | https://retail-analytics-7474650611714585.aws.databricksapps.com |
| Tên app | `retail-analytics` |
| Profile CLI | `retail-dev` |
| Gói code trên workspace | thư mục `retail-analytics-app` trong thư mục Users của tài khoản PM (đường dẫn đầy đủ xem ở bước 3) |
| SQL warehouse | `95d9f64890e29b5f` (tự bật khi app truy vấn, không cần bật tay) |

## 1. Vì sao app tự dừng

Workspace đang dùng **bản Free**. Bản này tự tắt app trong hai trường hợp:

- app đã chạy đủ **24 giờ** kể từ lần bật gần nhất;
- tài khoản chạm **giới hạn sử dụng** của bản Free. Khi đó Databricks ghi *"App compute was stopped due to workspace
  or account status"*. Lần đầu gặp: 2026-10-07 lúc 12:20 UTC, khoảng 6,5 giờ sau khi deploy.

Cả hai trường hợp đều **không phải lỗi app**. Code, khóa DeepSeek và quyền đọc kho vẫn nguyên.
Sau khi dừng, app có thể **mất bản deploy đang chạy**: trạng thái báo *"App has not been deployed yet"*.
Gói code trên workspace vẫn còn, chỉ cần deploy lại từ đó (bước 3).

## 2. Cách nhanh nhất: bấm trên giao diện Databricks

1. Đăng nhập workspace Databricks, vào **Compute → tab Apps** (hoặc mục **Apps** ở thanh bên trái), bấm `retail-analytics`.
2. Nếu trạng thái là *Stopped*, bấm **Start**. Đợi 2–5 phút.
3. Nếu sau khi Start trang app vẫn báo chưa deploy (*"not been deployed"*), bấm **Deploy**. Ô đường dẫn nguồn để
   nguyên thư mục `.../retail-analytics-app` đã điền sẵn (đây là gói cũ), rồi xác nhận.
4. Khi trạng thái là **Running**, mở link app. **Lần mở đầu có thể chậm khoảng 1 phút** vì SQL warehouse đang khởi động.

Giao diện Databricks có thể đổi tên nút theo phiên bản; nếu không thấy nút, dùng cách ở mục 3.

## 3. Cách bằng dòng lệnh (PowerShell hoặc Git Bash)

Chạy trong terminal ở bất kỳ thư mục nào. Không có lệnh nào dưới đây in khóa hay mật khẩu.

**Bước 1 — xem trạng thái:**

```
databricks apps get retail-analytics --profile retail-dev
```

Đọc ba trường trong kết quả:

| Trường | Bình thường | Đang hỏng |
|---|---|---|
| `compute_status.state` | `ACTIVE` | `STOPPED` → làm bước 2 |
| `app_status.state` | `RUNNING` | `UNAVAILABLE` |
| `active_deployment` | có `deployment_id`, `status.state` = `SUCCEEDED` | `null` → làm bước 3 |

**Bước 2 — bật compute:**

```
databricks apps start retail-analytics --profile retail-dev
```

Lệnh chờ tới khi compute bật xong (vài phút). Thường lệnh này **tự deploy lại gói cũ**. Chạy lại bước 1:
nếu `app_status.state` = `RUNNING` thì xong, sang bước 5.

**Bước 3 — chỉ khi vẫn chưa có bản deploy: deploy lại gói cũ.**
Lấy đường dẫn gói từ các lần deploy trước (cột `source_code_path`):

```
databricks apps list-deployments retail-analytics --profile retail-dev
```

Rồi deploy từ đúng đường dẫn đó:

```
databricks apps deploy retail-analytics --source-code-path <source_code_path ở trên> --profile retail-dev
```

Trong **Git Bash** phải thêm `MSYS_NO_PATHCONV=1` ở đầu lệnh, nếu không Git Bash sẽ đổi `/Workspace/...` thành đường dẫn Windows.
PowerShell không cần.

**Bước 4 — (không bắt buộc) xác nhận đúng bản code.** Gói ghi mã commit trong file `BUILD_REVISION`:

```
databricks workspace export <source_code_path>/apps/retail_app/BUILD_REVISION --profile retail-dev
```

Kết quả là mã commit đã deploy (ví dụ `fdb8681`). Có đuôi `+dirty` nghĩa là gói dựng từ code chưa commit — báo dev.

**Bước 5 — xem log khởi động:**

```
databricks apps logs retail-analytics --profile retail-dev
```

Thấy dòng `Uvicorn server started on 0.0.0.0:8000` là app đã lên. Dòng `[BUILD] ERROR: pip's dependency resolver ...`
là cảnh báo xung đột gói có sẵn của nền tảng, xuất hiện ở mọi lần deploy, app vẫn chạy bình thường.

## 4. Gặp lỗi khác thì làm gì

| Hiện tượng | Nguyên nhân thường gặp | Xử lý |
|---|---|---|
| Lệnh CLI báo lỗi đăng nhập / token hết hạn | phiên đăng nhập CLI hết hạn | `databricks auth login --profile retail-dev`, đăng nhập trên trình duyệt rồi chạy lại lệnh |
| `apps start` báo lỗi quota / account status | tài khoản Free đã hết giới hạn trong ngày | đợi sang ngày hôm sau rồi Start lại; không có cách vượt trên bản Free |
| Deploy `FAILED` | gói lỗi hoặc thư viện không cài được | xem `apps logs`, chụp phần `[BUILD]` gửi dev; **không** sửa file trên workspace bằng tay |
| App mở được nhưng trang báo lỗi đọc kho | warehouse chưa bật xong, hoặc kho đang dựng lại | đợi 1–2 phút rồi tải lại trang; vẫn lỗi thì gửi dev log |
| Chat báo lỗi gọi model | khóa DeepSeek hết hạn/hết tiền, hoặc app bị chặn gọi ra ngoài | xem `apps logs`: `AuthenticationError` = khóa; `APIConnectionError`/timeout = mạng. Gửi dev |

## 5. Trước buổi demo

1. Trước giờ demo ít nhất **30 phút**: chạy bước 1 ở mục 3; nếu không `RUNNING` thì bật lại theo mục 2 hoặc 3.
2. Mở link app, bấm qua Tổng quan một lượt để warehouse khởi động sẵn; hỏi thử chat một câu (ví dụ
   "CAGR của giai đoạn 2016→2018 là bao nhiêu?").
3. Nhớ: app sẽ tự dừng lại sau tối đa 24 giờ, hoặc sớm hơn nếu chạm giới hạn của bản Free.

## 6. Khi nào KHÔNG tự làm được

Mục 2–3 chỉ **bật lại bản code đã deploy**. Muốn đưa **code mới** lên app thì phải dựng lại gói
(`scripts/databricks/build_app_bundle.py`), tải lên workspace và chạy test trước — đây là việc của dev, theo quy trình
"test local đạt rồi mới deploy" (`docs/dwh_roadmap.md`). Nhật ký các lần deploy: `docs/ai_explain_nhat_ky.md`.
