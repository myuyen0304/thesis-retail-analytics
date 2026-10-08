# Đưa app lên Streamlit Community Cloud (bản public, ai cũng xem được)

PM chọn ngày 2026-10-08. Vì **Databricks Apps không cho mở công khai** (người xem phải đăng nhập workspace), giao diện
Streamlit chạy trên **Streamlit Community Cloud** (miễn phí). **Dữ liệu vẫn đọc từ kho Databricks production**
(catalog `retail_lab`), đúng quyết định 2026-10-05: chỉ chỗ đặt giao diện đổi, kho và số liệu không đổi.

```
Người xem (không cần đăng nhập)
   │
   ▼
Streamlit Community Cloud ── chạy apps/retail_app/app.py, lấy code từ GitHub
   │   các trang ──► SP retail-web-ro  (chỉ SELECT 21 bảng reporting) ──┐
   │   chat AI   ──► SP retail-ai-ro   (chỉ SELECT 14 bảng, guard kiểm) ─┼──► SQL warehouse Databricks ► retail_lab
   │   chat AI   ──► API DeepSeek (khóa riêng cho bản public)            │
```

## 1. Đã chuẩn bị sẵn (dev làm 2026-10-08)

| Việc | Kết quả |
|---|---|
| SP mới `retail-web-ro` cho các trang | application id `f1e26aa2-0daf-4aaf-987f-b6cbf55d07e1`; quyền kiểm lại: SELECT đúng 21 bảng + USE `retail_lab`/`reporting`, không gì thêm |
| Quyền được cấp lại sau mỗi lần build kho | hook `retail_dbt/macros/ai_readonly_grants.sql` (env `RETAIL_WEB_DBX_PRINCIPAL`) |
| Thư viện | `apps/retail_app/requirements.txt` (cùng thư mục với `app.py` nên Streamlit Cloud đọc file này, không đọc file ở root) |
| Nội dung Secrets | file **`.env.streamlit_cloud.local`** ở root repo trên máy PM (Git ignore). Còn thiếu đúng 1 dòng: khóa DeepSeek |
| Chạy thử kiểu Streamlit Cloud trên máy | không file `.env`, không profile CLI, chỉ biến môi trường từ Secrets: 8/8 trang mở được; chat C01 ra số, câu năm 2024 → không có dữ liệu, câu dự báo 2023 → không hỗ trợ |

Code app **không phải sửa**: Streamlit Cloud đổi các dòng trong Secrets thành biến môi trường, và app vốn đọc cấu hình từ
biến môi trường.

## 2. Các bước PM tự làm

### Bước 1 — tạo khóa DeepSeek riêng cho bản public

1. Vào trang quản lý API của DeepSeek, tạo khóa mới, đặt tên dễ nhận (vd. `streamlit-public`).
2. Nên nạp **ít tiền** vào tài khoản dùng cho khóa này: app public thì ai cũng hỏi chat được, mỗi câu tốn tiền thật.
   Bị lạm dụng thì thu hồi riêng khóa này, Databricks và máy local không ảnh hưởng.
3. Mở file `.env.streamlit_cloud.local` (root repo) bằng VS Code, dán khóa vào dòng cuối, giữa hai dấu ngoặc kép:
   `RETAIL_AI_API_KEY = "sk-..."`. Lưu file. **Không gửi khóa hay nội dung file này vào chat.**

### Bước 2 — đăng nhập Streamlit Community Cloud

1. Vào https://share.streamlit.io, chọn **Continue with GitHub**, đăng nhập tài khoản GitHub sở hữu repo
   `myuyen0304/thesis-retail-analytics`.
2. Khi được hỏi quyền, **cho phép truy cập repo private**. Streamlit tạo một khóa chỉ-đọc vào repo để lấy code.
   Bản miễn phí chỉ cho **1 app** lấy từ repo private.

### Bước 3 — tạo app

1. Bấm **Create app** → chọn deploy từ GitHub (*"Deploy a public app from GitHub"* / *"Yup, I have an app"*).
2. Điền:

   | Ô | Giá trị |
   |---|---|
   | Repository | `myuyen0304/thesis-retail-analytics` |
   | Branch | `app/myuyen` (nhánh có code đã kiểm; sau khi merge PR có thể deploy lại từ `main`) |
   | Main file path | `apps/retail_app/app.py` |
   | App URL | tên tùy chọn, vd. `retail-analytics-ps` → link sẽ là `https://retail-analytics-ps.streamlit.app` |

3. Mở **Advanced settings**:
   - **Python version: 3.11** — bộ thư viện đã chạy test trên 3.11. Đổi Python sau khi deploy phải xóa app rồi deploy lại.
   - **Secrets:** mở `.env.streamlit_cloud.local`, chép **toàn bộ** nội dung (kể cả dòng khóa vừa điền), dán vào ô Secrets.
4. Bấm **Save** rồi **Deploy**. Lần đầu cài thư viện mất khoảng 3–5 phút. Xem tiến trình ở nút **Manage app**
   (góc dưới bên phải trang app).

### Bước 4 — mở công khai

App lấy từ repo private **mặc định là private**. Vào **Settings → Sharing**, ở *Who can view this app* chọn
**This app is public and searchable**. Sau đó mở link bằng cửa sổ ẩn danh để chắc là không cần đăng nhập.

### Bước 5 — kiểm nhanh (smoke)

1. Thanh bên hiện nguồn **Databricks (cloud, production)**, không có lựa chọn khác.
2. Tổng quan có đủ **11 năm (2012–2022)**. Lần mở đầu có thể chậm khoảng 20–60 giây vì SQL warehouse khởi động.
3. Bấm qua PS1–PS5 và Sức khỏe dữ liệu: không trang nào báo lỗi đỏ.
4. Chat hỏi 3 câu:
   - "CAGR của giai đoạn 2016→2018 là bao nhiêu?" → có số (−6,4%/năm);
   - "Doanh thu thực nhận năm 2024 là bao nhiêu?" → báo không có dữ liệu;
   - "Dự đoán giúp R năm 2023 sẽ là bao nhiêu?" → báo không hỗ trợ.

### Bước 6 — tắt app trên Databricks (PM đã đồng ý 2026-10-08)

Khi bản Streamlit chạy ổn, tắt compute app Databricks để không tốn quota bản Free (ngày 2026-10-07 app Databricks
chạy liên tục và chính nó bị tắt vì *workspace or account status*):

```
databricks apps stop retail-analytics --profile retail-dev
```

Lệnh chỉ dừng compute, **không xóa** app; bật lại theo `docs/databricks_app_van_hanh.md`.

## 3. Vận hành hằng ngày

| Tình huống | Điều xảy ra | Xử lý |
|---|---|---|
| Không ai mở app một thời gian | Streamlit cho app **ngủ** (diễn đàn Streamlit báo khoảng 12 giờ không có lượt xem; Streamlit không công bố con số chính thức) | người xem bấm **Yes, get this app back up**, đợi khoảng 1 phút. Trước demo: tự mở trước 10–15 phút |
| Warehouse Databricks đang tắt | câu đầu chậm 20–60 giây (đo 21,8 giây ngày 2026-10-06) | đợi, rồi tải lại trang; các trang giữ kết quả 10 phút nên lượt sau nhanh |
| Databricks Free chạm giới hạn sử dụng | trang báo lỗi đọc kho; không có cách vượt trên bản Free | đợi hôm sau; xem `docs/databricks_app_van_hanh.md` mục 4 |
| Push code mới lên nhánh đang deploy | Streamlit **tự deploy lại** sau vài phút | chỉ push lên nhánh này khi test local đã đạt (quy trình `docs/dwh_roadmap.md`) |
| Chat báo lỗi gọi model | khóa DeepSeek hết tiền hoặc bị thu hồi | nạp tiền hoặc tạo khóa mới, sửa dòng `RETAIL_AI_API_KEY` trong **Settings → Secrets** (app tự khởi động lại) |
| Thấy lượng gọi DeepSeek tăng bất thường | có người lạm dụng chat | thu hồi khóa `streamlit-public` trên trang DeepSeek; chat báo lỗi, các trang vẫn chạy |
| Trang báo lỗi xác thực Databricks | secret của SP hết hạn | xem mục 4 |

Nhật ký lỗi của app: **Manage app** → tab log. Chụp phần lỗi gửi dev; không chép Secrets vào ảnh chụp.

## 4. Hạn của secret và đổi secret

| Secret | Dùng cho | Hết hạn |
|---|---|---|
| OAuth secret của `retail-web-ro` | các trang | **2027-01-06** |
| OAuth secret của `retail-ai-ro` | chat AI | **2027-01-04** |
| Khóa DeepSeek `streamlit-public` | chat AI | theo DeepSeek |

Gần hạn (hoặc nghi file `.env.streamlit_cloud.local` bị lộ): nhờ dev tạo OAuth secret mới cho SP tương ứng
(cách làm giống lúc tạo, secret đi thẳng vào file, không in ra), rồi PM sửa dòng tương ứng trong **Settings → Secrets**
của Streamlit Cloud. Secret cũ thu hồi sau khi app chạy được với secret mới.

## 5. Giới hạn phải nói rõ khi demo

- Bản public phụ thuộc **bản Free của cả hai nền tảng**: Streamlit có thể cho app ngủ, Databricks có thể tạm chặn khi
  chạm giới hạn. Không cam kết luôn sẵn sàng 100%.
- Chat công khai: ai cũng hỏi được, tốn tiền DeepSeek theo số câu. Chat chỉ đọc 14 bảng tổng hợp đã kiểm, không đọc
  dữ liệu khách hàng; số liệu mọi người xem được là số tổng hợp của dataset Datathon.
- Streamlit giữ một khóa chỉ-đọc vào repo private để lấy code.
