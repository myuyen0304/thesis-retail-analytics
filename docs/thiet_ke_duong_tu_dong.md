# Thiết kế: đường tự động cho dữ liệu nhập (không người bấm khi đủ điều kiện)

Trạng thái: §0–§7 (lát T1, local) **PM duyệt 2026-10-31**, phiếu GPT ở [giao_viec_duong_tu_dong.md](giao_viec_duong_tu_dong.md),
chưa giao. §8 (lát T2, production): **PM duyệt quy trình 2026-11-02**; phiếu GPT soạn sau khi T1 merge.
Số có dấu † là số khảo sát sơ bộ; mọi khẳng định khác dẫn `file:dòng`.

## 0. Yêu cầu và quyết định

- **PM 2026-10-31:** "cho data đi qua pipeline mà không có người đụng vào". Lý do: lượt nghiệm thu §6 phiếu nhập UI phải sửa tay 3 cột
  (`sales_employee_name`, `years_experience`, `comment`) dù `orders_enriched` đã có hợp đồng duyệt sẵn
  (`scripts/ingest/extensions/orders_enriched.yml`); quên sửa thì lượt chạy 7 phút rồi mới bị `validate` chặn.
- Thiết kế này **đảo một phần** quy tắc "DE luôn duyệt" của lát 1 và phiếu nhập UI (`giao_viec_nhap_du_lieu_ui.md` §3, §10): người
  chỉ còn xử lý **ngoại lệ**. Mọi cổng kiểm (cách ly, test dbt, `validate`) giữ nguyên.
- **PM chốt 2026-10-31:**
  1. **Nguồn hoàn toàn mới:** lần đầu DE duyệt; hợp đồng đó được lưu, các lần gửi sau đi đường tự động.
  2. **Kích hoạt:** ngay khi gửi file; đang có lượt khác chạy thì xếp hàng.
  3. **File có thêm cột mới:** vẫn tự chạy phần đã có trong hợp đồng; cột mới chưa vào kho, sinh đề xuất nâng hợp đồng cho DE;
     duyệt xong chạy lại để nạp bù. Thiếu cột bắt buộc, đổi tên cột bắt buộc, đổi kiểu thì luôn dừng chờ DE. Cột thêm qua nâng hợp đồng không bắt buộc, trừ cột đã lên mart (PM chốt 2026-11-02).
  4. **Công bố:** validate đạt thì **tự công bố** với lượt do hệ thống khởi động; lượt do người bấm chạy lại dừng chờ Admin (Claude sửa 2026-11-02, phiếu T1 §3.6); nhật ký ghi `he_thong`; Admin rollback được.

## 1. Luồng

```
Gửi file → auto mapping → phân loại (§2)
   ├─ tự động   → tự duyệt theo hợp đồng hiện hành → xếp hàng chạy → prepare/forecast/build/validate → tự công bố
   │                  └─ cột mới? → thêm "đề xuất nâng hợp đồng" cho DE (không chặn luồng)
   └─ cần người → Chờ duyệt, kèm danh sách lý do vì sao không tự đi được
Lỗi ở bất kỳ cổng nào → Lỗi khi chạy (DE xem), không công bố.
```

## 2. Phân loại: khi nào tự động, khi nào cần người

Hàm phân loại thuần (không I/O) nhận đề xuất auto mapping + hợp đồng hiện hành, trả `tu_dong | can_nguoi` và danh sách lý do.

| Tình huống | Kết quả | Lý do |
|---|---|---|
| Nguồn chưa có hợp đồng hiện hành | cần người | quyết định nghiệp vụ lần đầu (PM chốt 1) |
| Auto mapping không chắc nguồn (dưới ngưỡng điểm/khoảng cách, `auto_mapping.py:65–68`) | cần người | không biết file thuộc nguồn nào |
| Cột khớp hợp đồng (thứ tự có thể khác) | **tự động** | |
| Có thêm cột mới | **tự động**, cột mới = `bo` | PM chốt 3; cột mới chưa ra ngoài nên an toàn PII |
| Thiếu cột hoặc đổi tên cột bắt buộc | cần người | thay đổi phá hợp đồng |
| Thiếu cột thêm qua nâng hợp đồng (silver, bỏ) | tự động | cột không bắt buộc (PM chốt 2026-11-02); bản dữ liệu mới không có cột đó |
| Cột có trong hợp đồng mà kiểu dữ liệu không còn ép được (đề xuất báo `khong_ep_duoc` > 0) | cần người | đổi kiểu |
| Khóa trùng mà khác nội dung (`xung_dot_khoa.id_trung_khac_noi_dung > 0`) | cần người | như `epd.json` |
| Nguồn chưa có model dbt | cần người (Chờ model dbt) | như hiện nay |

Sau khi tự duyệt, các cổng chạy như cũ: cách ly vượt 1%, test dbt, `validate` lỗi → Lỗi khi chạy, không công bố.

## 3. Thiết kế chi tiết

### 3.1 Kho hợp đồng đã duyệt

- `warehouse/ui_nhap/hop_dong_da_duyet/<ten_mo_rong>/v<N>.yml` + `hien_hanh.json` (phiên bản hiện hành, sha256, người duyệt, ngày,
  yêu cầu gốc). Ghi nguyên tử, không sửa phiên bản cũ.
- **Gieo sẵn** v1 của `orders_enriched` từ `scripts/ingest/extensions/orders_enriched.yml` (hợp đồng đã review trong Git).
- Lần DE duyệt đầu cho nguồn mới → ghi v1; duyệt đề xuất nâng hợp đồng → ghi v(N+1).

### 3.2 Hợp đồng của lượt

- Tự duyệt = chép hợp đồng hiện hành vào `hop_dong/` của yêu cầu, **header theo đúng file** (prepare kiểm header cả thứ tự,
  `extension_prepare.py:51–54`), cột mới thêm với `xu_ly: bo`, `ly_do: "cột mới, chờ duyệt nâng hợp đồng"`.
- Nhờ vậy cơ chế kiểm `hop_dong_sha256` và cách ly hiện có giữ nguyên, không thêm nhánh riêng cho đường tự động.

### 3.3 Đề xuất nâng hợp đồng (cột mới)

- Khi có cột mới: tạo mục "Nâng hợp đồng `<ten>` v(N+1)" trên trang Duyệt, chỉ gồm cột mới (thống kê, nghi PII, mẫu) theo luật mặc
  định hiện có (PII → silver).
- DE duyệt → kho hợp đồng lên v(N+1) → **tự tạo yêu cầu mới** để nạp bù, dùng lại file của yêu cầu đã công bố ra đúng bản đang `active` của nguồn đó; đang có lượt chạy hoặc hàng đợi thì từ chối duyệt nâng, chưa ghi v(N+1) (Claude sửa 2026-11-02, phiếu T1 §3.4) (file
  gốc vẫn lưu ở `data/ui_nhap/<id>/`), đi đường tự động với hợp đồng mới; yêu cầu cũ giữ nguyên. File đó không có đủ cột mới hoặc chưa có
  yêu cầu đã công bố thì không nạp bù, cột mới có hiệu lực từ lần gửi sau. Sửa 2026-11-02, thay cho "nút chạy lại yêu cầu cũ"; chi tiết ở
  phiếu T1 §3.4.
- Cột thêm qua nâng hợp đồng không bắt buộc, trừ cột `mart` vì model dbt đọc cột đó (PM chốt 2026-11-02, phiếu T1 §3.4).
- Cột mới cần model dbt mới mới lên mart; chưa có model thì cột chỉ ở silver, và chọn `mart` cho cột đó bị từ chối ngay lúc duyệt nâng (Claude sửa 2026-11-02, phiếu T1 §3.4).

### 3.4 Chuỗi tự động và hàng đợi

- `submit` → phân loại → nếu `tu_dong`: chuyển `cho_duyet → da_duyet` với người thao tác `he_thong`, rồi đưa vào hàng đợi.
- **Hàng đợi** `warehouse/ui_nhap/hang_doi/` (FIFO, một file mỗi mục): hiện `start` từ chối khi bận (`nhap_runner.py:173–176`);
  worker chạy xong thì lấy mục kế tiếp. Một lượt chạy tại một thời điểm như hiện nay.
- `da_kiem` của yêu cầu đi đường tự động → worker tự gọi công bố (`nhap_runner.publish`) với `he_thong`.
- Trang Gửi của Quản lý hiện thêm "Tự động" / "Chờ đội dữ liệu" và lý do (ngôn ngữ nghiệp vụ).

### 3.5 Nhật ký và rollback

- Mọi bước tự động ghi nhật ký truy cập với người `he_thong` kèm id yêu cầu. Worker chạy ngoài phiên Streamlit: **phải kiểm** worker
  đọc được cấu hình Neon (`roles.store()`, `roles.py:125–131`) — không được thì ghi nhật ký vào file cục bộ và đồng bộ khi app mở.
- Rollback: CLI đã có `rollback` (`scripts/pipeline/cli.py:515, 536–563`); thêm nút **Rollback** cho Admin trên trang Duyệt cho root
  `ui-nhap` nếu chưa có.

### 3.6 Hai sửa nhỏ đi kèm (phát hiện khi nghiệm thu 2026-10-31)

- **N6:** yêu cầu "Lỗi khi chạy" do quyết định duyệt sai không sửa lại được (`nhap_store.py:23`, `loi → dang_chay` duy nhất); thêm
  `loi → cho_duyet` ("Duyệt lại", DE/Admin, ghi lý do vào lịch sử).
- **Gợi ý kiểu số:** cột mới mà 100% giá trị ép được sang integer thì đề xuất `integer` kèm lý do (hiện mặc định luôn `string`,
  `approval.py:26`); chỉ là gợi ý cho lần duyệt đầu.

## 4. Ràng buộc

- **T1** chỉ xử lý trên app local + DuckDB; trên Streamlit Cloud hai trang chỉ hiện thông báo (phiếu T1 §3.12), không chạm Databricks.
  Bản production (Streamlit Cloud + Databricks + Airflow) là lát **T2**, xem §8.
- **Không cột nào tự lên mart nếu chưa có người duyệt ít nhất một lần** (hợp đồng hiện hành hoặc đề xuất nâng hợp đồng).
- Nguồn lõi (đợt kỳ mới, [thiet_ke_nap_ky_moi.md](thiet_ke_nap_ky_moi.md)) giữ ngưỡng cách ly 0; đợt khớp hợp đồng nguồn lõi cũng đi
  được đường tự động.
- Không đổi số, test hay hành vi của bản gốc khi không có yêu cầu nhập.

## 5. Tiêu chí nghiệm thu

1. Gửi `orders_enriched` (file 2022) → **không ai bấm gì** → trạng thái tới "Đã cập nhật"; kho `ui-nhap` có bản `active`;
   `dim_sales_employee` 200 dòng, 36.004 đơn có nhân viên†, 0 dòng cách ly; `sales_employee_name` ở mart, `comment` ở silver.
2. Gửi file thêm một cột `bonus` → vẫn tự công bố, `bonus` không có trong kho; có mục "Nâng hợp đồng v2"; DE duyệt + nạp bù → `bonus`
   có ở silver.
3. Gửi file thiếu cột bắt buộc / đổi kiểu / `epd.json` / nguồn chưa có hợp đồng → dừng ở Chờ duyệt với lý do đúng.
4. Gửi hai file liền nhau → chạy lần lượt, không lượt nào bị từ chối vì bận.
5. Lượt tự động lỗi ở `validate` → Lỗi khi chạy, không công bố; DE "Duyệt lại" được (N6).
6. Nhật ký có đủ các bước của `he_thong`; Admin rollback về bản trước được.
7. Toàn bộ test hiện có đạt; không có yêu cầu nhập thì số và hành vi của bản gốc không đổi.

## 6. Thứ tự làm

Một lát **T1** (phiếu GPT riêng, Claude rà), tách từ `nhap-ui/myuyen` **sau khi** phiếu nhập UI qua nghiệm thu §6, **trước** D1 của
nạp kỳ mới (đợt kỳ mới dùng lại đường tự động).

## 7. Câu hỏi còn mở

1. Nghiệm thu §6 của phiếu nhập UI: vẫn chạy bản tay hiện tại (sửa 3 cột) cho đủ, rồi mới làm T1? (Đề xuất: có — T1 dựa trên luồng
   tay đã nghiệm thu.)

## 8. Lên production (T2) — PM duyệt quy trình 2026-11-02

**PM 2026-11-01:** đường nhập dữ liệu sau này **phải lên production**: Streamlit Cloud, Databricks, Airflow.
**PM 2026-11-02:** chấp nhận có khâu người duyệt, không cần tự động 100%; Claude phác thảo, rà, kiểm thử; GPT viết code. T1 vẫn làm
local trước. Phiếu T2 chỉ soạn **sau khi T1 merge**, vì T2 dùng lại `contract_registry`, `tu_dong.phan_loai`, `hop_dong_cua_luot`.
Số có † chưa kiểm trên hệ thống thật; bước S0 (§8.9) kiểm các điểm này.

### 8.1 Luồng

```
Streamlit Cloud (chỉ giao diện, không chạy stage nào)
   │ Gửi file: ghi file + sự kiện vào Volume
   ▼
Airflow DAG mới nhap_du_lieu_do (5 phút một lần, chỉ gọi Files API, không đánh thức warehouse)
   │ thấy yêu cầu mới → chép file về container → auto mapping → phân loại (§2)
   ├─ tu_dong  → hợp đồng của lượt
   └─ can_nguoi → ★ DE duyệt trên web → hợp đồng của lượt
   ▼
retail_batch_pipeline (lượt có request_id): prepare → forecast → build → validate, DỪNG
   ▼
★ Admin bấm Công bố trên web → sự kiện vào Volume → Airflow chạy cli publish
   ▼
Dashboard đổi số
```

Khác T1: T1 local tự công bố (§0 quyết định 4). **Production luôn dừng ở validate.** Phân loại tự động vẫn giữ: nguồn đã có hợp đồng
không cần DE duyệt lại, nhưng lần công bố lúc nào cũng có người bấm.

| Thành phần T1 (local) | T2 (production) |
|---|---|
| `RequestStore` trên đĩa, `data/ui_nhap/` | Volume (§8.2). Ổ đĩa Streamlit Cloud bị xóa khi app khởi động lại |
| Hàng đợi file | `max_active_runs=1` của DAG (`deploy/airflow/dags/retail_batch_pipeline.py:40`) |
| Worker nền của app | Task Airflow. Mọi lần ghi registry do Airflow làm, vì CLI quy định một writer (`scripts/pipeline/cli.py:3`) |
| Kho hợp đồng trên đĩa | Volume, truyền qua `--extension-dir` (`cli.py:521–530`); không đổi `code_version`, nên duyệt hợp đồng không cần dựng lại image |
| Nhật ký `he_thong` ghi Neon | Sự kiện trên Volume là nguồn; trang Duyệt đồng bộ lên Neon theo cơ chế `nhat_ky_cho` của T1. Airflow không giữ khóa Neon |

Phần giữ nguyên từ T1: phân loại, hợp đồng của lượt, nâng hợp đồng, N6, gợi ý kiểu số. T2 chỉ thay chỗ lưu và người chạy.

### 8.2 Chỗ lưu: Volume thay cho bảng Delta

Đổi so với phác thảo 2026-11-01 (bảng Delta): dùng file để web và Airflow **không phải đánh thức warehouse** chỉ để xem trạng thái.
Warehouse tự dừng sau 10 phút rảnh, nên dò 5 phút một lần qua SQL sẽ giữ nó chạy suốt ngày.

```
/Volumes/retail_lab/nhap_du_lieu/kho/
  yeu_cau/<id>/file/<ten_file>
  yeu_cau/<id>/su_kien/<000001>.json     ← chỉ thêm, không sửa
  yeu_cau/<id>/de_xuat/…  hop_dong/<ten>.yml
  hop_dong_da_duyet/<ten>/v<N>.yml  hien_hanh.json
  hieu_luc.json                          ← bộ phần mở rộng đang chạy trên production (§8.4)
```

- **Trạng thái = phát lại sự kiện**, kiểm chuyển trạng thái bằng `TRANSITIONS` hiện có (`apps/retail_app/ui/nhap_store.py:19–25`).
- **Chống ghi đè:** ghi sự kiện số kế tiếp bằng Files API `overwrite=false`; hai người bấm cùng lúc thì người sau nhận lỗi và tải lại.
  Cách này thay cho `revision` + `writer_lock`, vốn không dùng được trên Volume. Hành vi này cần S0 kiểm†.
- **Giới hạn file:** giữ 200 MB (`nhap_store.py:18`). `orders_enriched.csv` thật là 155 MB; Streamlit Cloud cho RAM 690 MB–2,7 GB
  (tài liệu Streamlit, tháng 2/2024), nên file lớn có thể làm app hết bộ nhớ†.
- **Tách lưu trữ khỏi import:** view không được import `auto_mapping`/`duckdb`. Trang gọi một lớp lưu trữ (đĩa cho local, Volume cho
  cloud); đề xuất chỉ chạy trong Airflow. Phần an toàn khi mở trang trên cloud làm ở T1 (phiếu T1 §3.12).

### 8.3 DAG

- **`nhap_du_lieu_do` (mới):** lịch 5 phút, `max_active_runs=1`, tạm dừng khi tạo. Không chạm registry, trừ bước publish dưới đây.
  - Yêu cầu mới → kiểm `sha256` file → chép về `data/ui_nhap/<id>/` → `auto_mapping.propose` → `phan_loai` → ghi đề xuất và sự kiện.
  - Đã có hợp đồng của lượt → trigger `retail_batch_pipeline` kèm `request_id`.
  - Có sự kiện `yeu_cau_cong_bo` hợp lệ → `cli publish --run-id <run> --target databricks` dưới `writer.lock` của CLI. Khóa bận thì để lần dò sau.
- **`retail_batch_pipeline`:** thêm tham số `request_id` (null cho lượt lịch). Có `request_id` thì bỏ qua `publish_release` và truyền
  `--extension-dir`. Hiện DAG chỉ có `target`, `snapshot_id`, `force`, `extensions` (`retail_batch_pipeline.py:47–52`).
- **Mount:** hiện `./data` chỉ đọc (`docker-compose.airflow.yml:21`), mà `prepare` đọc file theo `Path(data) / doc['file']`
  (`scripts/ingest/extension_prepare.py:47`). Thêm mount ghi `./data/ui_nhap:/opt/retail/data/ui_nhap`; 14 nguồn gốc vẫn chỉ đọc.
- **Giới hạn đã chấp nhận:** laptop tắt thì không dò, file chờ tới khi bật lại.

### 8.4 Bộ phần mở rộng đang hiệu lực (ba bẫy phải đóng)

Bẫy của P7 sẽ lặp lại với mỗi nguồn mới nếu lịch chỉ đọc biến môi trường (`retail_batch_pipeline.py:13–18`). `hieu_luc.json` ghi
`{ten: {yeu_cau, phien_ban, hop_dong_sha256, csv_sha256}}` và chỉ đổi khi publish thành công.

1. **Lượt lịch 08:00** đọc `hieu_luc.json`, chép đúng file và hợp đồng đó về, rồi `prepare`. Cùng file, cùng hợp đồng cho cùng
   `snapshot_id` (`scripts/pipeline/snapshot.py:67–70`, `scripts/ingest/extension_contract.py:87–89`), nên `bo_qua`. Thiếu hoặc đọc lỗi
   `hieu_luc.json` thì **dừng lượt**, không suy ra "không có phần mở rộng" như biến trống hiện nay. Lúc chuyển đổi, gieo `orders_enriched`
   từ hợp đồng repo.
2. **Lượt nhập nguồn mới** phải gộp cả bộ đang hiệu lực. Chỉ truyền nguồn mới thì lần publish sẽ làm mất các nguồn cũ, đúng bẫy của P7.
3. **Gửi lại đúng file** không được dựng bản mới. `hop_dong_sha256` băm nguyên văn file hợp đồng (`extension_contract.py:77`), mà hợp đồng
   của lượt chứa `file: ui_nhap/<id>/…` và `ngay_duyet` (phiếu T1 §3.3), nên mỗi yêu cầu ra `snapshot_id` khác và tốn thêm khoảng 83 bảng.
   Vì vậy `nhap_du_lieu_do` so `csv_sha256` + phiên bản hợp đồng với `hieu_luc.json`; trùng thì báo "Không có gì mới", không trigger.

`validate` vẫn là cổng cuối. Publish xong mới cập nhật `hieu_luc.json`; hai bước này không nguyên tử, nên lần dò kế tiếp đối soát với
`active` của registry và ghi lại nếu lệch.

### 8.5 Quyền và tài khoản (PM làm)

- **Volume** `retail_lab.nhap_du_lieu.kho`: PM tạo schema và volume bằng tài khoản của PM.
- **Service principal mới `retail-nhap-writer`** cho web: chỉ `USE CATALOG`, `USE SCHEMA nhap_du_lieu`, `READ VOLUME`, `WRITE VOLUME`
  trên đúng volume đó. Khóa để trong Streamlit Secrets.
- **Không bao giờ cấp cho `account users`:** ngày 2026-10-25, một lệnh như vậy đã khóa mọi câu chat.
- **Không gộp quyền này vào `retail-web-ro`:** guard kiểm quyền thừa của tài khoản đọc (`apps/retail_app/dwh/guarded.py:345–372`).
- **`retail-pipeline-writer`** cần đọc và ghi volume này.
- **Giới hạn chưa giải quyết:** web giữ khóa ghi, nên quyền Quản lý/DE/Admin chỉ được kiểm trong code app (`nhap_store.actor`). Airflow
  kiểm được tính hợp lệ của chuỗi sự kiện, không kiểm được người bấm là ai. Đủ cho khóa luận; ghi rõ khi bảo vệ.
- **File tải lên có thể chứa dữ liệu cá nhân** (tên, số điện thoại). Volume chỉ cấp cho hai tài khoản trên; `retail-web-ro` không đọc được.

### 8.6 Script dọn bản cũ (làm trước T2)

Mỗi bản có mở rộng chiếm **83 bảng** (P5, 2026-11-02). Catalog đang có 245 bảng, tức chỉ còn chỗ cho khoảng 3 bản†, chưa tính catalog demo
dùng chung quota. Bảng đã xóa còn bị tính thêm một thời gian: lần 10-29 tới ≤3 ngày, lần 11-01 khoảng 9 giờ.

- **Mặc định chỉ in** danh sách và lệnh; thực hiện cần cờ riêng và mã bản gõ đầy đủ. Lệnh xóa do PM chạy.
- **Không bao giờ xóa:** `active`, đích rollback được chỉ định, bản của lượt đang dở. Kiểm lại ngay trong script lúc chạy.
  Ngày 2026-11-01 Claude đề xuất nhầm `5d32a104` (đích rollback P8), nên quy tắc này phải nằm trong code.
- **Sửa registry bằng cách bỏ mục, không đổi `status`.** `allowed_versions` duyệt mọi mục và ném lỗi nếu có mục không `ready` (`apps/retail_app/dwh/releases.py:116–122, 23`), nên đổi `status` có thể
  khóa chat public. Xóa schema trước, bỏ mục sau; chuyển mục sang khóa `da_xoa`. Hiện `cfe19211`, `b25b3e47`, `ccde5a5e` đã xóa schema nhưng còn `ready` (đọc 2026-11-02). Phiếu: `giao_viec_don_ban_cu.md`.
- **Chặn trước khi dựng:** `nhap_du_lieu_do` không trigger khi không đủ chỗ cho một bản (còn dưới 100 bảng), và báo lý do trên trang Duyệt.

### 8.7 Đưa code lên

- `code_version` băm `apps/retail_app`, `scripts/ingest`, `scripts/pipeline`, `retail_dbt/…` (`cli.py:30–40`). Image đầu tiên mang code T1/T2
  sẽ khiến lượt lịch kế tiếp **dựng và publish một bản mới**, dù dữ liệu không đổi. Quy trình: tạm dừng DAG → dựng image → chạy tới validate
  → PM duyệt publish → bỏ tạm dừng, như lát 4.
- Vì `apps/retail_app` nằm trong băm, sửa chỉ giao diện cũng đổi `code_version`. Gom các lần đưa code, tránh mỗi lần tốn 83 bảng.
- Chạy thử đầu cuối ở **catalog demo** trước ([thiet_ke_nap_ky_moi.md](thiet_ke_nap_ky_moi.md) §4.8), rồi mới đổi sang `retail_lab`.

### 8.8 Cổng bắt buộc trước khi làm T2

1. T1 qua nghiệm thu local.
2. ~~P5 chạy lại đạt, rồi P6 công bố trên cloud đạt.~~ **Xong 2026-11-02:** bản `dbb80f56` đang phục vụ, P9 đạt (PM kiểm web và chat). Còn P7.
3. Script dọn bản cũ (§8.6), cũng là điều kiện mở đóng băng image.
4. **Dữ liệu synthetic không bao giờ vào `retail_lab`.** PM đổi 2026-11-01: đợt synthetic 2023 được lên Databricks, nhưng chỉ ở catalog demo riêng
   ([thiet_ke_nap_ky_moi.md](thiet_ke_nap_ky_moi.md) §4.8). Chặn bằng code: yêu cầu có cờ synthetic mà catalog là `retail_lab` thì từ chối.
5. Hai trang Gửi/Duyệt bật cứng mọi nơi và bỏ cờ `RETAIL_APP_NHAP_DU_LIEU` (PM đổi 2026-11-01). Làm ở T1 (phiếu T1 §3.12), vì hiện mở
   trang trên cloud có thể lỗi: view import `nhap_store` → `auto_mapping` → `duckdb`, mà `apps/retail_app/requirements.txt` không có duckdb.

### 8.9 S0: kiểm trước khi soạn phiếu T2 (Claude chạy, PM tạo tài khoản)

| Kiểm | Vì sao |
|---|---|
| Files API `overwrite=false` trả lỗi khi file đã có, kể cả hai lần ghi gần nhau | Cơ chế chống ghi đè §8.2 dựa vào đây |
| Service principal chỉ có quyền volume ghi được, không đọc được bảng nào | Giới hạn §8.5 |
| Liệt kê volume không làm warehouse chạy lại | Lý do bỏ bảng Delta §8.2 |
| Tải 155 MB từ Streamlit Cloud lên volume không làm app hết bộ nhớ | Giới hạn §8.2 |
| Đọc được quota bằng tài khoản pipeline | Điều kiện chặn §8.6 |

Một mục không đạt thì sửa thiết kế trước khi soạn phiếu, không để GPT phát hiện giữa chừng.

### 8.10 Tiêu chí nghiệm thu T2

Chạy ở catalog demo trước, rồi lặp mục 1 và 2 trên `retail_lab`.
1. Gửi `orders_enriched.csv` trên web public → không ai bấm gì cho tới "Đã kiểm tra" → chưa đổi `active`, web vẫn đọc bản cũ.
2. Admin bấm Công bố → `active` đổi, `hieu_luc.json` khớp, số các trang PS không đổi.
3. Gửi lại đúng file → "Không có gì mới", không tạo schema `r_` mới.
4. Lượt lịch 08:00 sau đó → `bo_qua`.
5. Gửi file thiếu cột hoặc `epd.json` → dừng chờ DE, đúng lý do; không tạo schema `r_` mới.
6. Cột mới `bonus` → tự chạy tới validate, `bonus` không vào kho; DE duyệt nâng hợp đồng → nạp bù, `bonus` ở silver, không lên mart.
7. Hai người bấm cùng lúc → người sau được yêu cầu tải lại; chuỗi sự kiện không hỏng.
8. Laptop tắt lúc gửi → file nằm trên volume; bật lại thì chạy tiếp.
9. Tài khoản `retail-nhap-writer` không đọc được bảng nào; `retail-web-ro` không đọc được volume.
10. Yêu cầu synthetic trên `retail_lab` bị từ chối.

### 8.11 Câu hỏi chờ PM

1. ~~Ai bấm Công bố trên production?~~ **PM chốt 2026-11-02: giữ Admin**, DE không được công bố; đúng code hiện tại (`nhap_store.py:40`).
   Rollback cũng chỉ Admin.

**PM duyệt 2026-11-02:** production dừng ở validate, người bấm công bố; giữ Airflow trên laptop, không chuyển Databricks Job. Cho nhập trên app public: đã chốt
2026-11-01. Không còn câu mở cho T2.

### 8.12 Cập nhật 2026-11-11: làm T2 trên nền luồng đợt (PM duyệt 2026-11-11: chọn (b) + tự đưa lên dashboard như local)

PM chọn 2026-11-11 làm T2 trước ngày bảo vệ 12/12. Luồng đợt ([thiet_ke_dot_web_public.md](thiet_ke_dot_web_public.md)) đã dựng xong nhiều phần
§8.1–§8.9 cần, nên T2 chỉ còn phần riêng của "một file lạ cột".

**Đã có, dùng lại nguyên:**

| Phần | Ở đâu |
|---|---|
| Volume `kho`, sự kiện `overwrite=false`, phát lại trạng thái | `apps/retail_app/ui/kho_dot.py`, `trang_thai_dot.py` |
| Tài khoản `retail-nhap-writer` chỉ ghi volume (S0 đã kiểm) | thiết kế đợt §8.5 |
| DAG dò 5 phút, chỉ Files API, kiểm chỗ quota trước khi trigger | `deploy/airflow/dags/nhap_du_lieu_do.py`, `scripts/ops/nhap_do.py` |
| DAG chạy tới validate, **không có stage publish** | `deploy/airflow/dags/retail_dot_pipeline.py:16–17` |
| Con trỏ `dashboard`, lệnh đưa lên/trả, trang tự cập nhật (B1) | `nhap_do._process_command`, `ui/theo_doi_dot.py` |
| Dọn bản cũ có luật G, dọn kho | `scripts/ops/don_ban_cu.py`, `scripts/ops/don_kho_dot.py` |
| Đề xuất, phân loại, hợp đồng của lượt, nâng hợp đồng | `scripts/ingest/auto_mapping.py`, `tu_dong.py` (T1) |

**Còn thiếu:**
1. Loại yêu cầu `mot_file` trên Volume. Hiện `nhap_do._requests` chỉ nhận `loai == 'dot'` (`nhap_do.py:48`), DAG đợt chỉ nhận mã `_dot`
   (`retail_dot_pipeline.py:33–34`) và bắt buộc có ít nhất một đợt (dòng 20–21).
2. `nhap_do` chạy `auto_mapping.propose` + `tu_dong.phan_loai` cho yêu cầu `mot_file`, ghi đề xuất và sự kiện `tu_dong`/`can_nguoi` lên Volume.
3. Kho hợp đồng đã duyệt trên Volume (`hop_dong_da_duyet/`), chép về container rồi truyền `--extension-dir`; không đổi `code_version`.
4. Trang Duyệt trên cloud: xem đề xuất, chỉnh, duyệt, từ chối, nâng mẫu (ghi sự kiện, không chạy gì trong app).
5. Trang Gửi trên cloud nhận một file lạ cột, bên cạnh đợt.

**Đề xuất đổi so với §8.1, §8.3, §8.4 (PM quyết):**

- **Q-T2-1. Công bố trên cloud.**
  - (a) Theo §8.1: Admin bấm Công bố thì đổi `active`; cần `hieu_luc.json` và **sửa lượt 08:00** (`retail_batch_pipeline`) đọc file này (§8.4).
  - (b) **Claude đề xuất:** dùng lại con trỏ `dashboard` như luồng đợt. Bản có phần mở rộng mới dừng ở "Đã kiểm tra"; Admin bấm "Đưa lên dashboard"
    rồi "Trả". `active` và lượt 08:00 **không đổi**, nên không cần `hieu_luc.json`, không đụng DAG chạy hằng ngày.
    Lý do: phần mở rộng chỉ vào silver, không đổi số PS1–PS5 (§8.10 mục 2, 6), nên (a) không cho thấy gì thêm trên dashboard mà lại thêm rủi ro
    cho lượt 08:00 (bẫy P7). Đánh đổi: báo cáo phải ghi "bản đưa lên dashboard", không ghi "bản đang dùng"; đợt và một file dùng chung một
    con trỏ, mỗi lúc chỉ một bản trên dashboard; bản đợt dựng sau không mang phần mở rộng của bản một file (vì lấy phần mở rộng theo `active`, `nhap_do.py:376`).
- **Q-T2-2. Tự đưa lên dashboard (PM chốt 2026-11-11, đổi §8.1 "luôn có người bấm" cho riêng con trỏ `dashboard`).** Giống local:
  yêu cầu đi đường `tu_dong` kiểm đạt thì Airflow tự ghi lệnh `dat` (người ghi `airflow`), như Admin bấm. Đường `can_nguoi` sau khi DE duyệt
  và kiểm đạt thì chờ Admin bấm. Ba luật:
  1. Chỉ tự đưa khi con trỏ `dashboard` đang trống; đang có bản khác (vd đợt 2023) thì dừng ở "Đã kiểm tra", báo lý do, chờ Admin.
  2. `validate` vẫn là cổng: không đạt thì không ghi lệnh.
  3. `active` và lượt 08:00 không bao giờ đổi theo đường này; Admin "Trả" là về bản đang dùng.
  Báo cáo ghi: local tự công bố (đổi bản đang dùng), cloud tự đưa lên dashboard (không đổi bản đang dùng).
- **Q-T2-3. DAG chạy.** Với (b), dùng lại `retail_dot_pipeline`, thêm tham số `extension_dir`, cho phép danh sách đợt trống và mã `_mot`.
  `retail_batch_pipeline` giữ nguyên. Với (a), làm theo §8.3.

**Tiêu chí nghiệm thu, thay §8.10 khi chọn (b):** mục 3, 4, 5, 7, 8, 9 giữ nguyên. Mục 1: gửi file đúng mẫu đã duyệt nhưng chưa có trong bản đang dùng
(ứng viên `shipments_realistic`, cần kiểm file), dashboard đang trống, thì không ai bấm gì mà bản tự lên dashboard; `active` không đổi.
Mục 1b: cùng file nhưng dashboard đang có bản khác thì dừng ở "Đã kiểm tra", có lý do. Mục 2: số PS1–PS5
không đổi, bảng silver của phần mở rộng có trong bản đó; Admin trả dashboard thì về như cũ.
Mục 6 trên cloud: DE duyệt nâng mẫu → **gửi lại file** thì `bonus` vào silver (không nạp bù tự động như local). Đường `tay` tự vào hàng sau khi
DE duyệt, không có nút "Chạy" như local. Mục 10 bỏ (PM Q3 2026-11-07 cho dữ liệu đợt vào `retail_lab`).

**S0 (§8.9):** bốn mục đã đạt khi làm luồng đợt (ghi đè, quyền tài khoản, liệt kê không đánh thức warehouse, đếm bảng thay quota). Còn mục tải file
155 MB từ Streamlit Cloud: chọn file demo nhỏ hơn, hoặc PM thử trên app tạm trước khi soạn phiếu.

**Thứ tự:**
1. Mốc 1 (đợt 2023) xong và dọn.
2. PM duyệt §8.12.
3. Claude soạn phiếu, GPT code (backend `nhap_do` + DAG, rồi hai trang).
4. Claude rà, nghiệm thu local.
5. Tổng duyệt trên app tạm với thư mục Volume riêng.
6. Cửa sổ bảo trì lần 2: code đổi `apps/retail_app`, `scripts/ingest`, nên `code_version` đổi và phải dựng lại bản như 11-11.
7. Sửa báo cáo Word.

Mỗi lượt nghiệm thu dựng một bản khoảng 83 bảng; dọn bằng `don_ban_cu` giữa các lượt và chạy bước `quota` trước mỗi lượt. Bảng đã xóa còn bị tính thêm vài ngày (§8.6).
Vì vậy phần lớn tiêu chí nghiệm thu bằng test và chạy local; trên cloud chỉ **tối đa 3 lượt dựng** (mục 1 tự lên dashboard, mục 6 hai lượt), mỗi lượt
xóa bản cũ trước. Tổng duyệt dùng chung registry production: lệnh tự đưa lên dashboard sẽ đổi dashboard của web public cho tới khi Admin trả.
Dọn sau nghiệm thu thêm `hop_dong_da_duyet/` (`don_kho_dot.py --ca-hop-dong`), nếu không hợp đồng thử sẽ đổi cách phân loại về sau.
