# Sổ tay lệnh Databricks

Các lệnh CLI dùng thường xuyên cho app **Databricks Apps** `retail-analytics` và kho dữ liệu trên Databricks.
Ghi ngày 2026-10-21, CLI v1.4.0. Hướng dẫn vận hành từng bước (bật lại app, trước buổi demo) nằm ở
[`databricks_app_van_hanh.md`](databricks_app_van_hanh.md); file này chỉ là bảng tra lệnh.

Chạy trong **PowerShell** ở root repo `D:\retail-analytics`. Đặt biến một lần cho cả cửa sổ để lệnh ngắn,
dán không bị cắt dòng:

```powershell
$p   = 'retail-dev'                 # profile Databricks (PM chọn); luôn ghi --profile, không để CLI tự chọn
$app = 'retail-analytics'
$ws  = '/Workspace/Users/uyenuyen9780@gmail.com'
```

Dùng **Git Bash** thì thêm `MSYS_NO_PATHCONV=1` ở đầu lệnh có đường dẫn `/Workspace/...`, nếu không Git Bash đổi
đường dẫn đó thành đường dẫn Windows.

## 1. Đăng nhập

| Việc | Lệnh |
|---|---|
| Xem các profile đã có | `databricks auth profiles` |
| Đăng nhập lại khi token hết hạn | `databricks auth login --profile $p` |
| Kiểm đang đăng nhập bằng ai | `databricks current-user me --profile $p` |

`apps logs` cần đăng nhập OAuth; báo `does not support OAuth tokens` thì chạy lại `auth login`.

## 2. Trạng thái app

| Việc | Lệnh |
|---|---|
| Xem trạng thái app và compute | `databricks apps get $app --profile $p` |
| Chỉ in mấy dòng cần đọc | xem khối dưới bảng |
| Danh sách các lần deploy (thư mục gói, thành công/thất bại) | `databricks apps list-deployments $app --profile $p` |
| Log khởi động / lỗi | `databricks apps logs $app --profile $p` |

```powershell
databricks apps get $app --profile $p -o json | ConvertFrom-Json |
  % { "app=$($_.app_status.state) | compute=$($_.compute_status.state) - $($_.compute_status.message) | goi=$($_.active_deployment.source_code_path)" }
```

Đọc kết quả:

| Thấy | Nghĩa |
|---|---|
| `app=RUNNING`, `compute=ACTIVE` | App đang chạy |
| `compute=STOPPED` | Compute tắt, phải `apps start` trước khi deploy |
| `compute_status.message` có “workspace or account status” | Tài khoản Free hết giới hạn trong ngày; đợi sang hôm sau |
| Log có `Uvicorn server started on 0.0.0.0:8000` | App đã lên |
| Log có `[BUILD] ERROR: pip's dependency resolver ...` | Cảnh báo có ở mọi lần deploy, bỏ qua |

## 3. Bật / tắt app

| Việc | Lệnh |
|---|---|
| Bật compute (thường tự deploy lại gói cũ, chờ vài phút) | `databricks apps start $app --profile $p` |
| Tắt compute (tiết kiệm hạn mức Free) | `databricks apps stop $app --profile $p` |

App tự dừng sau tối đa 24 giờ, hoặc sớm hơn khi chạm giới hạn bản Free.

## 4. Deploy code mới lên app

Mỗi bản code đưa vào **một thư mục workspace mới** (ví dụ `retail-analytics-app-s9`, `retail-analytics-app-s9b`)
để còn quay lại gói cũ. Chỉ deploy code **đã commit** và đã test local đạt.

```powershell
$dst = "$ws/retail-analytics-app-<ten-dot>"      # đổi <ten-dot>, ví dụ s9b

# 1) dựng gói từ code đang checkout vào build/databricks_app/ (không chép .env*, data/, warehouse/)
.venv/Scripts/python.exe scripts/databricks/build_app_bundle.py

# 2) tải gói lên workspace
databricks workspace import-dir build/databricks_app $dst --profile $p

# 3) compute phải đang chạy (xem mục 2); nếu STOPPED thì bật trước
databricks apps start $app --profile $p

# 4) deploy gói mới
databricks apps deploy $app --source-code-path $dst --profile $p

# 5) kiểm đúng bản: ra mã commit; có đuôi +dirty nghĩa là gói dựng từ code chưa commit
databricks workspace export "$dst/apps/retail_app/BUILD_REVISION" --profile $p

# 6) xem log khởi động
databricks apps logs $app --profile $p
```

Lỗi `Cannot deploy app ... as it is not in RUNNING state` nghĩa là compute đang tắt: làm bước 3 rồi deploy lại.

## 5. Quay lại gói cũ

```powershell
databricks apps list-deployments $app --profile $p      # lấy source_code_path của gói muốn quay lại
databricks apps deploy $app --source-code-path <source_code_path> --profile $p
```

## 6. Xem file trên workspace

| Việc | Lệnh |
|---|---|
| Liệt kê thư mục | `databricks workspace list $ws --profile $p` |
| In một file | `databricks workspace export "<đường dẫn file>" --profile $p` |

Không sửa file trong gói trên workspace bằng tay; sửa code trong repo rồi deploy gói mới (mục 4).

## 7. Quyền đọc kho cho SP của app

Trang của app đọc kho bằng **service principal (SP) riêng của app**; chat đọc bằng SP AI. Pipeline chỉ cấp quyền
cho SP bản public và SP chat, nên **sau mỗi lần publish bản dữ liệu MỚI** phải cấp lại quyền đọc bản active cho SP
của app. Deploy lại code mà không publish bản dữ liệu mới thì không cần.

```powershell
# lấy client id của SP app
databricks apps get $app --profile $p -o json | ConvertFrom-Json | % { $_.service_principal_client_id }

# in các câu GRANT sẽ chạy (chưa cấp gì)
.venv/Scripts/python.exe -m scripts.databricks.cap_quyen_sp_app --client <client_id>

# cấp thật
.venv/Scripts/python.exe -m scripts.databricks.cap_quyen_sp_app --client <client_id> --thuc-hien

# kiểm quyền thực tế của SP trên một bảng
databricks grants get-effective table <catalog>.<schema>.<bảng> --principal <client_id> --profile $p
```

Script đọc danh tính writer từ `.env.airflow.local` và không in secret. Dấu hiệu quên bước này: app mở được nhưng
trang báo lỗi đọc kho, trong khi chat vẫn trả lời bình thường.

## 8. Lỗi hay gặp

| Hiện tượng | Nguyên nhân | Xử lý |
|---|---|---|
| CLI báo lỗi đăng nhập / token hết hạn | phiên đăng nhập hết hạn | `databricks auth login --profile $p` |
| `apps start` báo quota / account status | hết giới hạn Free trong ngày | đợi sang hôm sau |
| `Cannot deploy app ... not in RUNNING state` | compute đang tắt | `apps start` rồi deploy lại |
| Deploy `FAILED` | gói lỗi hoặc thư viện không cài được | `apps logs`, đọc phần `[BUILD]` |
| Trang báo lỗi đọc kho | warehouse chưa bật xong, hoặc SP app chưa có quyền bản mới | đợi 1–2 phút; vẫn lỗi thì làm mục 7 |
| Chat báo lỗi gọi model | khóa DeepSeek hết hạn/hết tiền, hoặc bị chặn gọi ra ngoài | `apps logs`: `AuthenticationError` = khóa, `APIConnectionError` = mạng |
| `BUILD_REVISION` có đuôi `+dirty` | gói dựng từ code chưa commit | commit rồi dựng lại gói |
