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
**PM 2026-11-04:** làm D1–D5 trước ([thiet_ke_nap_ky_moi.md](thiet_ke_nap_ky_moi.md) §0), T2 sau nếu còn kịp. Bỏ catalog demo; các chỗ dưới đây nhắc catalog demo phải đọc lại khi soạn phiếu T2.

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
  Cách này thay cho `revision` + `writer_lock`, vốn không dùng được trên Volume. S0 xác nhận luôn chỉ một người ghi được (§8.9).
  **Không dựa vào loại lỗi:** khi ghi đua, người thua thường gặp `TypeError` của SDK thay vì `AlreadyExists`. Mỗi sự kiện mang một mã
  ngẫu nhiên; ghi lỗi kiểu gì cũng đọc lại file đó, mã khớp là mình đã ghi được, khác là người khác đã ghi.
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

- **Volume** `retail_lab.nhap_du_lieu.kho`: PM tạo schema và volume bằng tài khoản của PM. **Đã tạo 2026-11-04.**
- **Service principal mới `retail-nhap-writer`** cho web: chỉ `USE CATALOG`, `USE SCHEMA nhap_du_lieu`, `READ VOLUME`, `WRITE VOLUME`
  trên đúng volume đó. Khóa để trong Streamlit Secrets. **Đã tạo và cấp quyền 2026-11-04;** khóa hết hạn 2027-05-03, tạm để ngoài repo ở
  `~/.retail-secrets/nhap_writer.env`, chưa đưa vào Streamlit Secrets.
- **Giới hạn đã biết:** nhóm `users` có `CAN_USE` trên warehouse, nên tài khoản này có thể gửi SQL và đánh thức warehouse nếu lộ khóa, dù không
  đọc được bảng nào. **PM chấp nhận 2026-11-04:** `retail-web-ro` không có tên riêng trong danh sách quyền của warehouse, nên thu quyền
  của nhóm `users` có thể làm hỏng web public.
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
  **Đổi sau S0:** đọc quota cần quyền account admin, không cấp cho tài khoản pipeline. Thay bằng đếm bảng qua `tables.list` của `retail_lab` và
  catalog demo, không cần warehouse. Ngày 2026-11-04 số đếm khớp quota (245 + 1 ở `dbacademy` = 246), nhưng số đếm không thấy bảng đã xóa còn bị
  tính quota, nên đây chỉ là chặn sớm; lỗi quota lúc dựng vẫn phải báo rõ. Tài khoản pipeline có liệt kê được hay không sẽ kiểm khi làm T2†.

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
4. ~~Dữ liệu synthetic không bao giờ vào `retail_lab`.~~ **PM đổi 2026-11-04:** bản có đợt tổng hợp được dựng trong `retail_lab`, chỉ công bố lúc demo khi Admin xác nhận
   riêng, sau đó rollback ([thiet_ke_nap_ky_moi.md](thiet_ke_nap_ky_moi.md) §0). Chặn bằng code: lượt tự động không được công bố bản có cờ tổng hợp.
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

**Kết quả 2026-11-04** (script tạm của Claude, tài khoản `retail-nhap-writer`, SDK 0.117.0; file thử đã xóa hết, script chưa vào repo):

| Kiểm | Kết quả | Hệ quả |
|---|---|---|
| Chống ghi đè | **Đạt.** Ghi trùng tuần tự báo `AlreadyExists`, nội dung giữ nguyên. Ghi đua 35 vòng (30 vòng 2 người, 5 vòng 5 người): vòng nào cũng đúng 1 người thắng, nội dung khớp người thắng | Người thua thường gặp `TypeError: object of type '_io.BytesIO' has no len()`, do SDK lỗi khi phân tích phản hồi của server. Đổi §8.2 |
| Quyền | **Đạt.** Tài khoản chỉ thấy schema `nhap_du_lieu` và `information_schema`; không có quyền trên schema và bảng bản `active`; bị chặn ở hai volume `pipeline_landing`. `retail-web-ro`, `retail-ai-ro` không có quyền trên volume | Không thử `SELECT`, để tránh đánh thức warehouse. Thêm giới hạn ở §8.5 |
| Warehouse | **Đạt.** 5 lần liệt kê và ghi file, sau 60 giây vẫn `STOPPED`, 0 câu SQL | Giữ thiết kế Volume |
| File 155 MB | **Chưa xong.** Từ laptop: tải lên 117 giây, RAM từ 112 lên đỉnh 441 MB (thêm 329 MB), `sha256` khớp | Phải thử trên Streamlit Cloud; số laptop không thay được |
| Đọc quota | **Không đạt.** Tài khoản này bị từ chối vì không phải account admin; `retail-pipeline-writer` cũng không đọc được (`giao_viec_don_ban_cu.md`) | Đổi §8.6 |

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
