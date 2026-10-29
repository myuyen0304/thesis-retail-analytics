# Phân quyền theo role

**Trạng thái: PM duyệt 2026-10-29, đã triển khai trên nhánh `phan-quyen/myuyen`.** PM chốt phạm vi (2026-10-27): làm cả tài
liệu lẫn triển khai; app có đăng nhập; role nào thấy đúng thứ role đó quan tâm; khách xem được PS1–PS5 kèm khung "AI diễn
giải" nhưng không dùng AI agent và AI dự báo. Ngày 2026-10-29 PM chốt thêm: hệ thống phải an toàn như với dữ liệu thật (§7);
tài khoản là username + mật khẩu do admin tạo, lưu ở Postgres riêng của app trên Neon, bỏ đăng nhập Google (§5).

## 1. Hiện trạng

Quyền hiện chỉ cấp cho **danh tính kỹ thuật**, chưa có khái niệm người dùng nghiệp vụ:

| Danh tính | Dùng ở đâu | Quyền hiện có |
|---|---|---|
| writer SP `retail-pipeline-writer` | pipeline Airflow | tạo schema `r_<id>_*`, ghi bảng, ghi `retail_control`, cấp quyền đọc (`MANAGE` trên catalog `retail_lab`) |
| `retail-web-ro` | app public (Streamlit Cloud) | `SELECT` từng bảng trong `app_read_relations` của bản active, cấp ở stage validate (`reader_grants`, `scripts/pipeline/cli.py`) |
| `retail-ai-ro` | chat AI | `SELECT` từng bảng trong `ai_readonly_relations` + `retail_control.state`; guard `_check_dbx_identity` (`apps/retail_app/dwh/guarded.py`) khóa chat nếu thấy quyền thừa |
| tài khoản PM | workspace, Airflow admin | admin |

App `apps/retail_app/app.py` hiện có 9 trang. Ai có link cũng thấy hết, và đổi được backend ở thanh bên.

## 2. Stakeholder và thứ họ quan tâm

| Role | Ai | Quan tâm gì |
|---|---|---|
| **Khách** | không đăng nhập (không cần tài khoản); gồm cả hội đồng/GVHD | xem sản phẩm: tổng quan, 5 problem statement, dự báo |
| **Quản lý** | ban điều hành và chủ sở hữu KPI K1–K9 (`docs/problem_statement.md`): giám đốc kinh doanh, marketing, tài chính, vận hành, CRM, quản lý giá/danh mục | KPI, dự báo, và hỏi "vì sao" bằng chat |
| **DA/BI** | người phân tích, người làm báo cáo, BA | đi sâu từng PS, bằng chứng SQL, chất lượng dữ liệu, query thẳng vào kho |
| **Data engineer** | 2 thành viên nhóm | pipeline, lịch chạy, backend, rollback |
| **Admin** | PM | tạo tài khoản và gán role, cấp quyền Databricks, quyết rollback |

BA duyệt đề xuất auto mapping (`docs/tien_hoa_schema.md` §5b) qua PR trên repo, không qua app.

## 3. Ma trận quyền

### 3.1 Trong app

| Trang / chức năng | Khách | Quản lý | DA/BI | Data engineer | Admin |
|---|---|---|---|---|---|
| Tổng quan | ✓ | ✓ | ✓ | ✓ | ✓ |
| PS1–PS5, kèm khung AI diễn giải | ✓ | ✓ | ✓ | ✓ | ✓ |
| Dự báo (biểu đồ, không gọi LLM) | ✓ | ✓ | ✓ | ✓ | ✓ |
| Hỏi dữ liệu (AI): agent, hỏi dự báo, giải thích dự báo | – | ✓ | ✓ | ✓ | ✓ |
| Sức khỏe dữ liệu | – | – | ✓ | ✓ | ✓ |
| Đổi backend ở thanh bên | – | – | – | ✓ | ✓ |
| Trang Phân quyền (tạo/khóa tài khoản, đổi role, đặt lại mật khẩu, nhật ký, ma trận) | – | – | – | – | ✓ |
| Đổi mật khẩu của chính mình | – | ✓ | ✓ | ✓ | ✓ |
| Cột mức **Công khai** (§7), gồm tên nhân viên bán hàng, tên shipper | ✓ | ✓ | ✓ | ✓ | ✓ |
| Cột mức **Nội bộ** (§7) | – | ✓ | ✓ | ✓ | ✓ |
| Cột mức **Liên hệ** (§7), gồm SĐT shipper | – | che bớt số | ✓ | ✓ | ✓ |
| Cột mức **Cấm** (§7): hôn nhân, học vấn của nhân viên và shipper | – | – | – | – | – |
| Trang mở mặc định | Tổng quan | Tổng quan | PS1 | Sức khỏe dữ liệu | Sức khỏe dữ liệu |

Lý do từng ô:
- **Khách thấy PS1–PS5 và AI diễn giải.** Đây là sản phẩm chính của khóa luận; hội đồng phải xem được mà không cần tài khoản.
- **Khách không có trang chat.** Chat cho hỏi tự do, gọi LLM nhiều lượt và có tool dự báo. Đây là phần tốn chi phí và dễ bị
  lạm dụng nhất.
- **Sức khỏe dữ liệu chỉ từ DA/BI trở lên.** Trang này phục vụ người cần tin hay không tin con số; quản lý chỉ cần biết số đã
  qua kiểm (dòng nguồn ở cuối mỗi trang đã ghi bản dữ liệu).
- **Đổi backend chỉ dành cho kỹ thuật.** Người dùng nghiệp vụ luôn đọc backend mặc định của bản deploy.
- **Tên nhân viên và tên shipper hiện cho mọi role, kể cả khách** (PM chốt 2026-10-29). **SĐT shipper không hiện cho khách**,
  quản lý thấy số đã che, từ DA/BI thấy đủ (PM chốt 2026-10-29, theo chuẩn dữ liệu thật ở §7; thu hẹp quyết định 2026-10-28 ở
  `docs/tien_hoa_schema.md` §10 mục 3). Hôn nhân và học vấn không lên app với bất kỳ role nào.
- **Trang mới phải khai báo vào ma trận này** (`PAGES_BY_ROLE` trong `ui/roles.py`). Trang chưa khai báo thì không role nào
  thấy. Lát 5 auto mapping thêm trang hay khung về nhân viên/shipper thì cập nhật bảng trên cùng lúc.

### 3.2 Trên Databricks (catalog `retail_lab`)

| Tài nguyên | Khách / Quản lý | DA/BI (group `retail-phan-tich`) | Data engineer (group `retail-ky-su`) | Admin |
|---|---|---|---|---|
| `r_<active>_marts`, `r_<active>_reporting` | – (đọc qua app) | `USE SCHEMA`, `SELECT` | `USE SCHEMA`, `SELECT` | toàn quyền |
| `r_<active>_raw`, `_staging`, `_intermediate` (gồm bảng mở rộng có hôn nhân, học vấn; xem dưới bảng) | – | – | `USE SCHEMA`, `SELECT` | toàn quyền |
| `retail_control.state`, `retail_control.run_history` | – | – | `SELECT` | toàn quyền |
| Ghi bất kỳ schema production | – | – | – (chỉ writer SP qua pipeline) | qua pipeline |
| SQL warehouse | – | `CAN USE` | `CAN USE` | `CAN MANAGE` |

Câu GRANT cho một bản active `<id>` (script `scripts/ops/phan_quyen_nhom.py` sẽ in ra, PM duyệt rồi tự chạy sau mỗi lần
publish; tên group sẽ chốt sau khi kiểm bản Free tạo được group):

```sql
grant use catalog on catalog retail_lab to `retail-phan-tich`;
grant use schema, select on schema retail_lab.r_<id>_marts to `retail-phan-tich`;
grant use schema, select on schema retail_lab.r_<id>_reporting to `retail-phan-tich`;

grant use catalog on catalog retail_lab to `retail-ky-su`;
grant use schema, select on schema retail_lab.r_<id>_raw to `retail-ky-su`;
-- … tương tự _staging, _intermediate, _marts, _reporting
grant use schema on schema retail_lab.retail_control to `retail-ky-su`;
grant select on table retail_lab.retail_control.state to `retail-ky-su`;
grant select on table retail_lab.retail_control.run_history to `retail-ky-su`;
```

**Data engineer và cột nhạy cảm (PM chốt 2026-10-29).** Raw và staging của phần mở rộng (`stg_orders_enriched`, bảng shipper)
còn giữ tình trạng hôn nhân và học vấn. Group `retail-ky-su` được đọc cả hai tầng này, có ghi nhật ký truy cập (§7.4), vì:
- data engineer cần raw/staging để dò lỗi nạp và mapping, nhất là khi có nguồn mới;
- hai thành viên nhóm vốn đã có file CSV gốc trên máy (`data/`), nên chặn trên Databricks không giảm được ai thấy dữ liệu;
- cấp theo từng bảng để loại bảng mở rộng thì danh sách đổi theo mỗi nguồn mới, dễ sót; che cột (column mask) phải gắn vào
  pipeline vì mỗi bản tạo lại bảng, đổi `code_version`.

Ràng buộc đi kèm: hai cột này không ra khỏi staging (không lên mart, app, chat, RAG), và không role nào khác được đọc raw/staging.
Nếu có data engineer ngoài nhóm hai người thì chuyển sang cấp theo từng bảng, bỏ bảng mở rộng.

Group được cấp **theo schema** (một lệnh phủ mọi bảng trong bản). SP của app và chat vẫn cấp **theo bảng** như cũ, vì guard
quyền thừa cần danh sách bảng chính xác. Group không chứa SP nên không làm guard khóa chat; sẽ kiểm lại sau khi cấp.

### 3.3 Airflow

Airflow chạy Docker local, đăng nhập một tài khoản `admin` (PM và data engineer). Không mở cho role khác.

## 4. Nguyên tắc

1. Cấp theo **group**, không cấp cho cá nhân.
2. **Không bao giờ** cấp cho `account users` hay `_workspace_users_*` trên `retail_lab`. Ngày 2026-10-25 cấp `SELECT` cho
   `account users` đã khóa mọi câu chat (guard thấy SP AI có quyền thừa qua group này).
3. Người dùng nghiệp vụ chỉ chạm lớp reporting, qua app.
4. Cột cá nhân xử lý theo mức nhạy cảm ở §7: tên nhân viên bán hàng và tên shipper là Công khai; SĐT shipper là Liên hệ;
   tình trạng hôn nhân và trình độ học vấn (nhân viên, shipper) là Cấm, **không** lên mart, app, chat hay RAG.
5. `retail_control` chỉ writer ghi; SP AI chỉ đọc `state`; `run_history` không cấp cho SP reader.
6. Tài khoản nằm trong DB tài khoản của bản deploy, không commit vào repo. Mật khẩu chỉ lưu dạng băm; không màn hình, log hay
   nhật ký nào hiện mật khẩu hoặc hash. Chuỗi kết nối DB chỉ nằm trong secrets.
7. **Fail closed:** lỗi đọc cấu hình, DB tài khoản không kết nối được, chưa đăng nhập, tài khoản bị khóa, còn mật khẩu tạm →
   role khách. Bản public đã cấu hình đăng nhập thì biến môi trường không nâng quyền được.

## 5. Cách triển khai trong app

**Tài khoản (PM chốt 2026-10-29).** Username + mật khẩu do admin tạo, như hệ thống backend thông thường (ví dụ role Data
engineer có `de1`, `de2`…, thêm được bất cứ lúc nào). Bỏ đăng nhập Google.
- Lưu ở **Postgres riêng của app**, schema `app_auth` (bảng `users`, `audit`): bản public dùng **Neon** (gói free), local dùng
  Postgres Docker. Đây chỉ là DB cho phần backend của app; **DWH vẫn chỉ ở Databricks**. Code: `apps/retail_app/ui/auth_store.py`.
  Chuỗi kết nối: secrets `[app_db] url = "postgresql://..."` hoặc biến môi trường `RETAIL_APP_DB_URL`.
- Mật khẩu băm scrypt (thư viện chuẩn Python), salt riêng từng tài khoản; tối thiểu 10 ký tự, không chứa tên đăng nhập.
- Đăng nhập sai báo cùng một câu dù sai tên hay sai mật khẩu. Sai 5 lần liên tiếp → khóa 15 phút (lưu trong DB).
- Admin tạo tài khoản trên trang Phân quyền: app sinh mật khẩu tạm, hiện **một lần**; người dùng phải đổi ở lần đăng nhập đầu
  (trước đó là khách). Admin đổi role, khóa / mở khóa, đặt lại mật khẩu (sinh mật khẩu tạm mới). Admin không tự khóa hay tự hạ
  role của chính mình, và không khóa được admin cuối cùng.
- Admin đầu tiên (hoặc admin quên mật khẩu): `scripts/ops/tao_admin.py --username <tên> [--local] [--dat-lai]`, PM tự chạy ở máy,
  nhập mật khẩu qua `getpass`.
- Phiên đăng nhập chỉ nằm trên server (`session_state`): chuyển trang vẫn giữ, **tải lại trang (F5) phải đăng nhập lại**.
  Mỗi 30 giây app đọc lại tài khoản từ DB, nên khóa hay đổi role có hiệu lực ngay ở lượt bấm kế tiếp.

`apps/retail_app/ui/roles.py` xác định role:
- có DB tài khoản: đã đăng nhập → role của tài khoản; chưa đăng nhập, bị khóa, còn mật khẩu tạm, DB lỗi → khách;
- không có DB tài khoản (chạy local để dev): đọc `RETAIL_APP_ROLE`, mặc định khách.

Phần còn lại:
- `app.py` chỉ đưa vào `st.navigation` những trang role được xem. Trang không có trong danh sách thì mở thẳng URL cũng không
  vào được.
- Trang mới trong `views/` phải khai báo ở `roles.PAGES` và `PAGES_BY_ROLE`; test `test_moi_trang_deu_khai_bao`
  (`apps/retail_app/tests/test_roles.py`) đỏ nếu quên. Lát 5 auto mapping gặp test này đỏ là đúng, không phải lỗi vặt.
- Admin có ô **"Xem như role"** ở thanh bên: app hiện đúng như role được chọn (menu, radio backend, cột), để kiểm hoặc demo
  từng role chỉ với một tài khoản. Ô này chỉ hạ quyền, chỉ có tác dụng trong phiên của admin; role khác không thấy ô và
  không nâng quyền được bằng nó. Nhật ký §7.4 ghi cả role thật (`role`) lẫn role đang xem (`xem_nhu`).
- Che cột theo mức và ghi nhật ký: trang hiện cột cá nhân phải đi qua `roles.view_frame(df, levels, page)`.
- Câu GRANT cho group: `scripts/ops/phan_quyen_nhom.py --release <id> [--bo-ban-cu <id cũ>]` (chỉ in, PM tự chạy).

**Thứ tự bật đăng nhập trên bản public** (Streamlit Cloud, deploy từ nhánh `app/myuyen`):
1. Tạo project Neon (gói free; region gần máy chủ Streamlit Cloud, AWS US East), chép chuỗi kết nối (có `sslmode=require`).
2. Tạo admin đầu tiên: đặt `$env:RETAIL_APP_DB_URL` bằng chuỗi đó rồi chạy `scripts/ops/tao_admin.py --username <tên>`.
3. Streamlit Cloud → Settings → Secrets: dán `[app_db]` + `url = "..."` ở **cuối** file (dòng đặt dưới một bảng TOML sẽ thuộc
   bảng đó), Save.
4. Rồi mới merge vào `app/myuyen` và push. Push trước khi có `[app_db]` thì mọi người, kể cả PM, chỉ có quyền khách (fail
   closed): mất trang chat, Sức khỏe dữ liệu và radio backend cho tới khi điền secrets.
5. **Không** đặt `RETAIL_APP_ROLE` trong secrets của bản public: Streamlit Cloud đưa khóa gốc của secrets thành biến môi
   trường, nên khi thiếu `[app_db]` mọi người xem sẽ nhận role đó.
6. Kiểm live: chưa đăng nhập vẫn xem PS1–PS5 kèm AI diễn giải; admin đăng nhập → tạo `de1` → `de1` đăng nhập, bị bắt đổi mật
   khẩu → thấy đúng menu Data engineer; sai mật khẩu 5 lần → bị khóa; F5 → về khách.

## 6. Giới hạn (ghi khi bảo vệ)

- Tới hết lần triển khai đầu, mọi role trong app đều đọc kho qua cùng một SP `retail-web-ro`, nên phân quyền trong app là **ở
  tầng giao diện**. Chấp nhận được vì lúc đó app chỉ chứa số đã tổng hợp, chưa có cột cá nhân. Khi lát 5 đưa cột mức Nội bộ trở
  lên vào app, phải có chặn ở tầng dữ liệu (§7.2) trước khi publish.
- Khách vẫn gọi được LLM qua khung AI diễn giải trên PS1–PS5. PM chấp nhận chi phí này để hội đồng xem được; chưa có giới hạn
  số lượt.
- Quyền group theo schema của từng bản, nên sau mỗi lần publish phải cấp lại (chạy script). Chưa gắn vào pipeline, để không
  đổi `code_version` và hành vi stage validate.
- Databricks Free Edition: cần kiểm tạo group được không trước khi cấp.
- Đăng nhập tự làm trong Streamlit không đặt được cookie an toàn (HttpOnly) như đăng nhập OIDC, nên phiên chỉ nằm trên server:
  tải lại trang là phải đăng nhập lại (PM chấp nhận 2026-10-29). Chưa có "quên mật khẩu" tự phục vụ: admin đặt lại.
- Ai biết một tên đăng nhập có thể cố tình nhập sai để tài khoản đó bị khóa 15 phút (đánh đổi của việc chặn dò mật khẩu).
  Admin mở ngay bằng Khóa → Mở khóa hoặc Đặt lại mật khẩu; admin tự bị khóa thì chạy `scripts/ops/tao_admin.py --dat-lai`.
- Neon gói free tự ngủ khi không ai dùng: lần đăng nhập đầu sau khi ngủ chậm khoảng 1 giây. Khách không bị ảnh hưởng (không
  cần DB tài khoản để xem).
- App public mở không cần đăng nhập, nên ai có link cũng thấy tên nhân viên và tên shipper (khi lát 5 đưa lên). PM chấp nhận
  (2026-10-29). `student_data` hiện là dữ liệu giả lập do giảng viên giao; hệ thống vẫn áp chuẩn dữ liệu thật ở §7.
- Không dựng lại image Airflow có code phân quyền trước khi lát 4 auto mapping publish xong: sửa `apps/retail_app` đổi
  `code_version`, pipeline sẽ build thêm một bộ khoảng 80 bảng trong khi catalog đang vượt quota 500 bảng (2026-10-28).

## 7. Chuẩn dữ liệu thật

PM chốt 2026-10-29: dữ liệu hiện có (kể cả `student_data` giảng viên giao) là giả lập, nhưng hệ thống phải an toàn như khi chạy
dữ liệu thật. Vì vậy không có "chế độ demo" nới lỏng: bản demo trước hội đồng áp đúng các quy tắc dưới đây.

### 7.1 Mức nhạy cảm của cột

Mỗi cột đưa lên mart/app được gán một mức. BA gán khi duyệt đề xuất auto mapping (`docs/tien_hoa_schema.md` §5b), mở rộng từ cờ
"nghi PII" của bước phân loại. Ma trận §3.1 cấp quyền theo mức, nên nguồn mới không cần sửa code phân quyền.

| Mức | Nghĩa | Hiện có |
|---|---|---|
| Công khai | ai có link cũng xem được | số tổng hợp; tên nhân viên bán hàng, tên shipper (PM chốt) |
| Nội bộ | chỉ người đã đăng nhập, từ Quản lý | (chưa có cột nào) |
| Liên hệ | thông tin liên lạc cá nhân: khách không thấy, Quản lý thấy bản che bớt, từ DA/BI thấy đủ | SĐT shipper |
| Cấm | không rời raw/staging: không lên mart, app, chat, RAG | hôn nhân, học vấn của nhân viên và shipper |

Cột chưa gán mức coi như **Cấm** (fail closed).

### 7.2 Chặn ở tầng dữ liệu

Phân quyền ở giao diện không đủ cho dữ liệu thật: lỗi giao diện là lộ. Từ lát 5:
- cột mức Nội bộ và Liên hệ nằm ở bảng reporting riêng (ví dụ `rpt_*_pii`), không trộn với bảng số tổng hợp;
- `retail-web-ro` (phiên khách) **không** có quyền đọc bảng đó; phiên đã đăng nhập đủ role đọc bằng một SP thứ hai;
- `verify_consumers` kiểm thêm chiều âm: `retail-web-ro` đọc bảng `*_pii` phải bị từ chối, giống test quyền đọc âm của lát 4.

### 7.3 LLM không thấy định danh

Chat và khung AI diễn giải chỉ gửi mã nhân viên/mã shipper cho LLM, kể cả cột mức Công khai. App thay mã bằng tên khi hiển thị,
theo quyền của người xem. Cột mức Liên hệ và Cấm không bao giờ vào ngữ cảnh LLM hay kho RAG.

### 7.4 Nhật ký truy cập

Ghi lại mỗi lần xem dữ liệu mức Nội bộ trở lên trong app (tài khoản, thời điểm, trang, mức), và mỗi lần data engineer đọc
raw/staging (lấy từ audit log của Databricks, `system.access.audit`, nếu bản Free có). Nhật ký không chứa giá trị của cột cá
nhân. Trong app ghi vào `app_auth.audit` (cùng đăng nhập đúng/sai, khóa, tạo/sửa tài khoản; trang Phân quyền hiện 50 dòng gần
nhất) và stderr của bản deploy.

### 7.5 Làm khi nào

| Việc | Thuộc |
|---|---|
| Đăng nhập, role, ma trận trang, radio backend, trang Phân quyền | lần triển khai đầu (§5) |
| Hàm che theo mức (§7.1), nhật ký truy cập trong app (§7.4) | lần triển khai đầu; chưa có cột cá nhân nên kiểm bằng test |
| Bảng `*_pii`, SP thứ hai, test quyền âm (§7.2); gửi mã cho LLM (§7.3); gán mức khi duyệt mapping (§7.1) | lát 5 auto mapping: phải ghi vào phiếu giao lát 5 |
