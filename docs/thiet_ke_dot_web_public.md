# Thiết kế: đợt dữ liệu 2023 trên web public (2024 hoãn tới sau 12/12)

Soạn ngày 2026-11-07, Claude. Trạng thái: **PM đã chốt mọi quyết định ngày 2026-11-07** (§0). L1 đã commit; phiếu L2, L3 soạn ngày 2026-11-09.
Nền: [thiet_ke_nap_ky_moi.md](thiet_ke_nap_ky_moi.md) (B′, D1–D5) và `thiet_ke_duong_tu_dong.md` §8 (T2, nhánh `docs/thiet-ke-b-tam-thoi`).
Các vị trí `file:dòng` đã đọc trong worktree `D:\retail-analytics-nap` (HEAD `610123b` cộng phần D5a/D5a-1 chưa commit). Số gắn † là số chưa kiểm.

## 0. Quyết định

| # | Quyết định | Ai, ngày |
|---|---|---|
| Q1 | Đích là demo **product** trên web public, không demo local | PM 2026-11-07 |
| Q2 | **Gỡ R2.** Chỉ cho dựng image một lần, trong cửa sổ bảo trì (§11) | PM 2026-11-07 |
| Q3 | Đợt nằm trong `retail_lab`, đi qua con trỏ `dashboard` (B′). `thiet_ke_nap_ky_moi.md` §4.8 (catalog demo) và `thiet_ke_duong_tu_dong.md` §8.7 dòng 3 và §8.10 mục 10 hết hiệu lực | PM 2026-11-07, chọn (i) |
| Q4 | Con trỏ dashboard dùng chung: khách cũng thấy đợt, kèm băng rôn. Chỉ bật trong khung demo (§7.5) | PM 2026-11-07 |
| Q5 | 2024 là đủ năm. Bản có đợt 2024 không có bảng dự báo | PM 2026-11-07 |
| Q6 | Sổ đợt: đợt chỉ vào sổ khi `dat-dashboard` đạt. "Trả dashboard" không xóa sổ; muốn bỏ đợt thì DE xóa có chủ đích | PM 2026-11-07 |
| Q7 | Đợt đúng hợp đồng thì tự chạy tới validate, không có bước DE duyệt; cổng người là Admin công bố | PM 2026-11-07 |
| Q8 | Không bắt gửi 3 file master (`customers`, `products`, `geography`); code đã cho phép (§4) | PM 2026-11-07 |
| Q9 | Bản tổng hợp chỉ cấp quyền đọc cho `retail-web-ro`, không cho `retail-ai-ro` (§7.2). Làm trong L2, trước cửa sổ bảo trì | PM 2026-11-07 |
| Q10 | Bộ phần mở rộng của đợt lấy đúng theo bản `active` (§5 bước 3) | PM 2026-11-07 |
| Q11 | Mốc 1 không gồm luồng một file mở rộng trên web (§1) | PM 2026-11-07 |
| Q12 | **Demo 12/12 chỉ gồm đợt 2023.** Bỏ Mốc 2. Đợt 2024 (Q5, §8 phần chuỗi, §9, phiếu L3 + L4) hoãn tới sau 12/12. Hai lỗi chữ tách sang phiếu L3a | PM 2026-11-09 |
| Q13 | Tổng duyệt chạy trọn luồng từ giao diện (§11). Một đợt gồm nhiều bảng, **mỗi bảng đúng một file**; không làm phần ghép một bảng từ nhiều file | PM 2026-11-09 |

## 1. Kịch bản và phạm vi

**Mốc 1 (khoảng 2026-11-24).**
1. `chushop` (Quản lý) gửi bộ file 2023 trên web public.
2. Hệ thống tự kiểm và chạy tới validate trên Databricks.
3. Admin bấm "Công bố lên dashboard".
4. Trong khoảng 5 phút, PS1–PS5 và Tổng quan hiện 2023, có băng rôn.
5. Trang Dự báo và chat vẫn đọc số thật (`active`).

**Mốc 2: bỏ (Q12).** Đợt 2024 vào hướng phát triển của báo cáo. Hệ thống hiện từ chối đợt kết thúc từ 2024-07-01 trở đi (`du_bao_dot.py:44–45`), nên demo chỉ chứng minh được một lần nối.

**Ngoài phạm vi:**
- file 155 MB;
- học lại dự báo (D4);
- chat theo kỳ có đợt (D6);
- luồng một file mở rộng của §8: thiết kế cũ vẫn giữ nguyên, nhưng không thuộc Mốc 1. Tài liệu này chỉ dùng chung hạ tầng (Volume, DAG dò).

## 2. Luồng đầu–cuối

```
Web public (Streamlit Cloud, chỉ giữ khóa retail-nhap-writer)
  │ chushop: Gửi → loại "Đợt dữ liệu" → 12 file → ghi file + sự kiện lên Volume
  ▼
nhap_du_lieu_do (Airflow, 5 phút/lần, chỉ Files API, không đánh thức warehouse)
  │ thấy đợt mới → tải về, kiểm sha256 → dot.classify → ghi kết quả
  │ đạt → kiểm chỗ quota → trigger retail_dot_pipeline (conf: request_id, chuỗi đợt, du_bao_tu)
  ▼
retail_dot_pipeline (target databricks): prepare → forecast(dùng lại | không có) → build → validate, DỪNG
  │ ghi sự kiện "da_kiem" + release_id lên Volume
  ▼
Web: Admin bấm "Công bố lên dashboard" → sự kiện lệnh lên Volume
  ▼
nhap_du_lieu_do: cli dat-dashboard --target databricks → ghi sổ đợt → ghi sự kiện kết quả
  ▼
PS1–PS5 đọc con trỏ dashboard (common.py:28); Dự báo + chat đọc active
```

Mọi lần ghi registry vẫn do Airflow làm (§8.1 T2). Web không gọi CLI trên cloud.

## 3. Lưu trữ trên Volume

Volume `retail_lab.nhap_du_lieu.kho`, PM tạo ngày 2026-11-04. Cách chống ghi đè giữ như §8.2 T2: ghi `overwrite=false`, mỗi sự kiện mang mã ngẫu nhiên, ghi lỗi thì đọc lại để biết mình thắng hay thua.

```
/Volumes/retail_lab/nhap_du_lieu/kho/
  yeu_cau/<id>/yeu_cau.json              ← loai: "dot", người gửi, danh sách file + sha256 + kích thước
  yeu_cau/<id>/file/<ten_file>
  yeu_cau/<id>/su_kien/<000001>.json     ← chỉ thêm, không sửa
  lenh/<000001>.json                     ← lệnh dashboard: dat {release_id, request_id} | tra; kết quả là sự kiện kế tiếp
  so_dot/<000001>.json                   ← sổ đợt, chỉ thêm: vao_so {ma_dot, request_id, release_id, file+sha256} | bo {ma_dot, ly_do}
```

**Trạng thái của yêu cầu loại đợt** là kết quả phát lại sự kiện. Dùng một bảng `TRANSITIONS_DOT` riêng, không nhét vào bảng của luồng một file (`apps/retail_app/ui/nhap_store.py:17–23`):

| Từ | Sang | Ai ghi |
|---|---|---|
| `da_gui` | `dang_kiem`, `loi_file` | Airflow |
| `dang_kiem` | `cho_chay`, `sai_hop_dong` (mã D2-*), `het_cho` (quota) | Airflow |
| `het_cho` | `cho_chay` | Airflow, sau khi đã dọn quota |
| `cho_chay` | `dang_chay` | Airflow |
| `dang_chay` | `da_kiem` (kèm `release_id`), `loi` | Airflow |
| `loi` | `cho_chay` (DE bấm chạy lại), `huy` | web (DE) |
| `da_kiem` | `tren_dashboard` | Airflow, sau khi lệnh `dat` đạt |
| `tren_dashboard` | `da_tra` | Airflow, khi có lệnh trả hoặc khi bản khác thay chỗ |
| `da_tra` | `tren_dashboard` | Airflow, khi Admin bật lại cùng bản (§7.5). Thêm ngày 2026-11-09, khi soạn phiếu L2 |

`sai_hop_dong`, `loi_file`, `huy` là trạng thái cuối. Muốn sửa thì gửi yêu cầu mới.

"Chờ đưa lên dashboard" **không phải sự kiện**. Trạng thái này suy ra khi có lệnh `dat` đang chờ trỏ tới yêu cầu, nên Admin chỉ ghi đúng một file lệnh. Lệnh lỗi thì yêu cầu vẫn ở `da_kiem`. Chỉnh ngày 2026-11-07, khi soạn phiếu L1.

## 4. Trang Gửi và Duyệt (app)

- **Gửi** (`apps/retail_app/views/gui_du_lieu.py:27`): thêm lựa chọn loại "Đợt dữ liệu" với `accept_multiple_files=True`, nhận `csv` và `json`, mỗi file tối đa 200 MB (`nhap_store.py:16`).
  - **Không đòi file master.** `dot.classify` chỉ bắt đủ 9 bảng giao dịch (`scripts/ingest/dot.py:15–16`, `:117–118`). File master nếu có gửi phải giống hệt từng byte, khác thì báo lỗi `D2-master` (`dot.py:52`, `:100–104`).
  - Đợt 2023 không kèm master: 12 file, khoảng 19,4 MB (đo bằng `ls` trên `data_demo/dot_2023`). Kèm master thì 15 file, khoảng 28 MB.
  - Chỉ kiểm nhẹ trên web: tên file không trùng; có `orders*.csv`; sha256. Phân loại đầy đủ chạy trong Airflow, vì nó cần duckdb mà `apps/retail_app/requirements.txt` không có (§8.8 mục 5 T2).
- **Duyệt** (`apps/retail_app/views/duyet_du_lieu.py:288–319`): khối dashboard hiện đọc registry local qua `dashboard_state` (`apps/retail_app/ui/nhap_runner.py:784–794`).
  - Trên cloud, dùng một nhánh `dashboard_state` mới, đọc registry qua SQL bằng `retail-web-ro`, cùng cách `releases.resolve` (`apps/retail_app/dwh/releases.py:84–102`).
  - Nút "Công bố lên dashboard" và "Trả dashboard" trên cloud **chỉ ghi lệnh vào `lenh/`**. Khi có lệnh chưa có kết quả, trang hiện "Đang chờ Airflow (tối đa khoảng 5 phút)" và khóa cả hai nút.
  - Nhánh local (subprocess, `nhap_runner.py:797–818`) giữ nguyên.
- **Chọn lớp lưu:** đĩa cho local, Volume cho cloud. Chọn theo cấu hình, không theo việc có khóa hay không.
  - Khóa `retail-nhap-writer` đặt trong Streamlit Secrets; hiện mới ở `~/.retail-secrets/nhap_writer.env` (§8.5 T2).
  - Quyền vẫn kiểm trong app: chỉ Quản lý gửi, chỉ Admin công bố hoặc trả, DE chạy lại (`nhap_store.actor`). Giới hạn đã nêu ở §8.5 T2: Airflow không biết người bấm là ai.

## 5. DAG dò `nhap_du_lieu_do` (mới)

Lịch 5 phút, `max_active_runs=1`, tạm dừng khi tạo. Chỉ dùng Files API của Volume, cộng `tables.list` để đếm chỗ quota.

1. **Đợt mới** (`da_gui`):
   - tải file về `warehouse/pipeline/docker/nhap/<id>/` và so sha256 với `yeu_cau.json`. Thư mục này nằm trong mount đã ghi được `./warehouse/pipeline` (`docker-compose.airflow.yml:22`), nên **không cần đổi compose**;
   - chạy `dot.classify_all(chuỗi)` (`dot.py:122`), với chuỗi = các đợt đang có trong sổ, theo thứ tự, cộng đợt mới. Ghi `cho_chay` hoặc `sai_hop_dong` kèm mã lỗi;
   - bước này chỉ bắt được các mã của `dot.classify` (D2-missing, D2-master, D2-format…) và D2-7 (đợt trùng, gồm cả đợt đang chờ công bố). D2-1 (trùng khóa, `dot.py:157–158`), D2-2 (ngày không nằm sau mốc cắt, `:161`), D2-3 (thiếu đơn ở một ngày nào đó, `:163–165`) nằm trong `check_batch` của `prepare`, nên ra `loi` kèm mã, chưa tạo schema `r_`. Chỉnh ngày 2026-11-09, khi soạn phiếu L2.
2. **Kiểm chỗ:** đếm bảng của `retail_lab` qua `tables.list` (§8.6 T2). Còn dưới 100 + 83 chỗ thì ghi `het_cho`, không trigger. Ngày 2026-11-07, số đếm bằng đúng quota (246).
3. **Trigger** `retail_dot_pipeline` với conf `{request_id, dots: [đường dẫn theo thứ tự], du_bao_tu: <active>}`.
   - Phần mở rộng của đợt lấy **đúng bộ của bản `active`**, đọc từ manifest của bản đó. Không ghi cứng `orders_enriched` + `shipments_realistic` như DAG local (`deploy/airflow/dags/retail_dot_pipeline.py:1`). Lý do: `du_bao_dot._kiem_khop` đòi sales của phần gốc bằng sales bản nguồn (`scripts/pipeline/du_bao_dot.py:120`)†.
4. **Theo dõi lượt:** khi DAG run xong, đọc `context.json` của lượt để lấy `release_id` và ghi `da_kiem` hoặc `loi`.
5. **Lệnh dashboard:**
   - `dat`: chạy `cli dat-dashboard --target databricks --release-id <rid> --xac-nhan-tong-hop`, rồi ghi `vao_so` vào sổ đợt (chỉ khi lệnh đạt), rồi ghi kết quả.
   - `tra`: chạy `cli tra-dashboard --target databricks`; sổ đợt giữ nguyên (Q6).
   - Khóa `writer.lock` đang bận thì để lần dò sau.
6. **Chống chạy chồng:** mọi task gọi CLI của `retail_batch_pipeline` và `retail_dot_pipeline` dùng chung một Airflow pool `retail_writer` một chỗ. Lệnh dashboard không dùng pool mà dựa vào `writer.lock` (CLI thoát mã 75 khi bận), vì nếu chờ pool thì DAG dò đứng theo suốt lúc dựng đợt (chỉnh ngày 2026-11-09). `writer.lock` chỉ giữ từng stage (`giao_viec_don_ban_cu.md` G4), nên nếu không có pool, lượt 08:00 và lượt đợt có thể đan xen trên laptop.

Đối soát: sổ đợt ghi sau `dat-dashboard`, hai bước không nguyên tử. Kết quả lệnh ghi **sau cùng**, nên máy tắt giữa chừng thì lệnh vẫn chờ và lần dò sau chạy lại; mỗi bước tự kiểm trước khi ghi. Không so với registry mỗi lần dò như bản đầu, vì làm vậy phải gửi SQL và đánh thức warehouse (chỉnh ngày 2026-11-09).

## 6. Chạy đợt trên Databricks (pipeline)

Các chỗ đang chặn, phải đổi:

| Chỗ | Hiện tại | Đổi |
|---|---|---|
| `scripts/pipeline/cli.py:340–341`, `:440–441`, `:588–589` | Từ chối `--dot` khi target là databricks | Cho phép |
| `du_bao_dot.py:78` | `Registry(root)` chỉ đọc file local | Target databricks thì đọc registry SQL |
| `du_bao_dot.py:84–85` | Bản nguồn phải là bản DuckDB | Bản nguồn cùng target với lượt đợt |
| `du_bao_dot.py:135–136` | "Bản có đợt chỉ chạy local" | Bỏ chặn |
| `retail_dot_pipeline.py:26`, `:30` | Ghi cứng `--target duckdb`, `--dot /opt/retail/data_demo/<name>` | Nhận `target`, `dots[]` (đường dẫn dưới `warehouse/pipeline/docker/nhap/`), `extensions` từ conf; giữ việc không có stage publish (`:16–17`) |

Không cần đổi:
- `runtime.ingest` duyệt chung `manifest['sources']` (`scripts/pipeline/runtime.py:38–59`);
- `dbt_build` truyền `bien_dot` cho cả hai target.

**Validate trên cloud.** `validate_data` so từng relation của marts/reporting trên cloud với bản DuckDB dựng cùng lượt (`cli.py:120–155`). Cách so này dùng chung cho bản có đợt, nhưng chưa chạy lần nào với đợt†. Lượt databricks cũng dựng bản DuckDB, nên tốn RAM laptop như lượt 08:00.

**Dự báo cho đợt:** `du_bao_tu` = bản `active` trên cloud. Dự báo được chép lại từ thư mục lượt của bản nguồn trên laptop, có kiểm hash (`du_bao_dot.py:69–72`, `:130–`). Bản `active` mới dựng sau khi lên image (§11) có thư mục đó trong `warehouse/pipeline/docker/runs/`†.

## 7. Con trỏ dashboard trên cloud

### 7.1 CLI

- `cli.py:610–611`: bỏ chặn `a.target != 'duckdb'`. Target databricks dùng `Registry(root, cloud.query)` và `verify_consumers(record, registry, cloud)`, giống `tra-dashboard` (`cli.py:629–`).
- `Registry.publish_dashboard` và `clear_dashboard` đã có CAS qua SQL (`scripts/pipeline/state.py:83–93`, `:123–149`), không cần đổi.

### 7.2 Quyền đọc của bản tổng hợp

`verify_consumers` trên cloud cấp quyền và thử đọc bằng **cả** `retail-web-ro` lẫn `retail-ai-ro` trên schema của bản (`cli.py:228–268`). `allowed_versions` nhận mọi bản trong `releases` (`releases.py:123–129`). Vì vậy, sau validate, tài khoản AI **đọc được về mặt quyền** schema tổng hợp. Thứ giữ chat ở `active` chỉ là cách pin trong code (`apps/retail_app/ui/common.py:28`), D5a đã test.

- **Làm cứng (Q9, PM chốt):** khi `co_du_lieu_tong_hop`, `verify_consumers` chỉ cấp quyền và thử đọc bằng `retail-web-ro`. Phần này chạm vào phần băm, nên làm trong L2, trước lần dựng image duy nhất.
  - Test phải chứng minh hai điều: tài khoản AI không nhận câu `GRANT` nào trên schema tổng hợp, và guard của chat vẫn đạt với bản `active`.
- Phải kiểm guard (`apps/retail_app/dwh/guarded.py:345–372`) không coi quyền của bản tổng hợp là quyền thừa, cả khi có lẫn không có phần làm cứng†.

### 7.3 Web public

- App public đang chạy `app/myuyen` bản `af4c7f7`, chưa có T1, D5a hay băng rôn. Code `nap-ky` phải lên `app/myuyen` trước khi dựng image (§11 bước 1).
- D5a đã xử lý trường hợp registry không có `dashboard`, nên app mới đọc registry hiện tại vẫn ra số y như cũ†. Bước 1 của §11 sẽ kiểm việc này.

### 7.4 Trang Dự báo

Trang này đọc `active`, nên số không đổi. Chữ ghi cứng (`apps/retail_app/views/du_bao.py:26`, `:157–158`, `:209`, `:250–260`) vẫn đúng với `active`. Thêm một dòng ghi chú khi hai con trỏ khác nhau, kiểu "Dashboard đang hiện dữ liệu tổng hợp có đợt; dự báo ở đây dựa trên số thật", theo mẫu ở trang AI (`common.py:191–193`).

### 7.4b Khung AI trên trang PS (PM chốt 2026-11-07)

Khi dashboard đang hiện bản có đợt, khung AI vẫn chạy với lựa chọn theo năm, nếu năm đó ≤ năm cuối của bản `active`. Khung AI chỉ ẩn khi lựa chọn chạm tới dữ liệu đợt, hoặc khi lựa chọn là cả chuỗi, kỳ hay giai đoạn. Lý do: các bảng theo năm khớp từng dòng giữa hai bản cho mọi năm ≤ 2022, còn bảng theo giai đoạn hay kỳ thì lệch (Claude đo trên `d3-thu`). Chi tiết ở phiếu L1 §3.9.

### 7.5 Vận hành (Q4)

Chỉ bật con trỏ trong khung demo: Mốc 1, buổi gặp thầy, buổi tập trước 12/12, ngày 12/12. Xong thì Admin bấm "Trả dashboard". Mỗi lần bật hoặc trả mất tối đa khoảng 5 phút, cộng thời gian dựng nếu có. Băng rôn tổng hợp đã có ở các trang PS (D5a).

## 8. Sổ đợt và chuỗi 2023 → 2024

Q12: demo chỉ có đợt 2023. Sổ đợt vẫn dùng như dưới; các dòng về D24 là cho phần làm sau 12/12.

- Đợt mới luôn nối sau **các đợt trong sổ**, theo thứ tự `vao_so`. Đợt 2024 tự thành chuỗi gốc + 2023 + 2024, dựng lại trong một lần `prepare`. `dot.prepare` lấy lại mốc cắt sau mỗi đợt (`dot.py:211–230`).
- Lúc chạy, file của đợt cũ tải lại từ Volume và so sha256 với sổ. Thư mục local chỉ là bộ đệm.
- `cli.py:369–372` bắt chạy lại cùng `run_id` phải cùng danh sách `--dot`. Danh sách lấy từ sổ nên ổn định.
- `hieu_luc.json` (§8.4 T2) không ghi đợt. Lượt 08:00 chỉ ghi `active` (`state.py:104–120`), nên không làm mất đợt.
- Sau khi D24 lên dashboard, bản D23 xóa được để lấy lại quota: chuỗi dựng từ file trên Volume, không cần bản D23. Nhưng sau đó "quay lại chỉ 2023" phải dựng lại.
- DE bỏ một đợt khỏi sổ (sự kiện `bo`) chỉ ảnh hưởng lần dựng sau, không đổi con trỏ đang bật.

## 9. Đợt 2024

**Hoãn tới sau 12/12 (Q12).** Toàn bộ §9 giữ làm tài liệu cho phần làm sau, không thuộc cửa sổ bảo trì.

### 9.1 Bộ sinh dữ liệu

File `scripts/demo/sinh_dot_2023.py` nằm ngoài phần băm, nên sửa sau khi dựng image vẫn được. Các chỗ phải sửa:
- năm 2023 ghi cứng ở `:78–80`, `:156`, `:191–195`, `:233–242` → tham số `--nam`;
- `:80` `target.replace(year=…)` lỗi ở 2024-02-29 khi năm mẫu không nhuận → chọn năm mẫu nhuận cho ngày 29/2, hoặc lấy ngày 28/2;
- `:79` dùng cửa sổ khuyến mãi năm lẻ, mà 2024 là năm chẵn → trong hai cửa sổ Urban Blowout chỉ lấy mẫu từ năm chẵn (CLAUDE.md §5 điểm 6);
- `:116`, `:127` chỉ lấy mã lớn nhất từ dữ liệu gốc → tính cả mã của các đợt trong sổ, nếu không D2-1 sẽ chặn;
- `dot.py:163–165` đòi đơn ở đủ 366 ngày.

### 9.2 dbt: nới dải ngày, chỉ khi có đợt

Điều kiện bất biến: **không có đợt thì build y hệt**, kể cả số dòng.

| Chỗ | Hiện tại | Khi `co_dot` |
|---|---|---|
| `retail_dbt/models/marts/dim_date.sql:1,5` | `integers(4566)`, 2012-01-01 → 2024-07-01 | Dừng ở `greatest(2024-07-01, cuối tháng của ngày lớn nhất trong mọi cột ngày)`. Không dừng ở `last_actual_date` như bản đầu: ngày trả hàng, đánh giá của đợt vượt sang đầu năm sau (bộ 2023 tới 2024-02-06), và khóa ngoại tới `dim_date` sẽ trượt (chỉnh ngày 2026-11-09, phiếu L3 §3.4) |
| `retail_dbt/models/marts/_marts.yml:9` | Mô tả dải cố định | Ghi theo điều kiện |
| `retail_dbt/tests/assert_row_counts.sql:3` | `dim_date` = 4566 | Theo dải ở trên |
| `retail_dbt/tests/assert_row_counts.sql:6` | `fact_daily_sales` = 4381 | Số ngày thực tế + số ngày dự báo. 2023: 4.198 + 183 = 4.381; 2024: 4.564 + 0 |
| `retail_dbt/tests/assert_rpt_calendar.sql:45` | `full_date < '2024-07-01'` | Theo dải |
| `retail_dbt/models/reporting/_forecast.yml:14` | Mô tả 2023-01-01 → 2024-07-01 | Chỉ sửa mô tả |

Kỳ phân tích đã tự chạy theo dữ liệu nhờ `ky_cuoi()` (`retail_dbt/models/reporting/rpt_revenue_total.sql:5–9`). Với 2024, kỳ sẽ tự ra `2013-2024`; `period_label` (`common.py:264–271`) không cần sửa. Chỉ còn hai chú thích cũ: `rpt_driver_period.sql:2` và `apps/retail_app/views/ps4_don_mon_gia.py:30`. `assert_ky_dot.sql` viết chung theo `last_actual_date`, nên với 2024 sẽ đạt sau khi nới `dim_date`†.

### 9.3 Bản có đợt không có bảng dự báo (Q5)

Khi ngày thực tế cuối ≥ `LICH_CUOI` (`du_bao_dot.py:20`, 2024-07-01), lượt đợt chạy chế độ **không dự báo**:
- `du_bao_dot.ky_cua_ban` không dừng ở `:44–45` nữa, chỉ báo "không dự báo";
- stage `forecast` ghi `stage = 'forecasted'` kèm `khong_du_bao: true`, không chép gì. `cli.py:448–452` và `:468–471` nhận trạng thái này;
- `bien_dbt` (`du_bao_dot.py:59–63`) không truyền `forecast_path`. `rpt_forecast_*` tắt theo `forecast_path` và vốn là bảng tùy chọn (`retail_dbt/dbt_project.yml:46–50`), nên app không đòi;
- `fact_daily_sales.sql:19–20`: không còn dòng dự báo, đúng theo thiết kế;
- `du_bao_dot.py:125–126` ("Không còn ngày dự báo nào") không còn được gọi tới trong chế độ này.

Phải kiểm Tổng quan và các trang PS với bản có 0 dòng dự báo†.

## 10. Quota

**Đếm ngày 2026-11-07** (Claude, `tables.list` qua profile `retail-dev`; quota đọc bằng `resource-quotas get-quota`: 246/500):

| Mục | Bảng + view | Vai trò (registry đọc ngày 2026-11-02) |
|---|---|---|
| `dbb80f5674af47fe9c98f796` | 83 | `active` |
| `5d32a10432ad4e338975a23a` | 80 | đích rollback |
| `03ad08c0ddbf4ce1848a1447` | 80 | `ready`, chờ PM quyết (`giao_viec_don_ban_cu.md` §6 bước 6) |
| `retail_control` | 2 | registry |
| `dbacademy.default` | 1 | không phải của project, để nguyên |
| **Tổng** | **246** | khớp quota; không có schema mồ côi |

Từ 2026-11-02 tới nay không có lượt nào publish: các lượt 08:00 từ 11-02 tới 11-06 đều `skipped`; lượt 11-07 lỗi ở `prepare` (§12).

**Lịch dọn.** Bảng đã xóa vẫn bị tính quota khoảng 7 ngày (ghi nhận từ sự cố 2026-10-28†).

| Hạn | Việc | Quota sau đó† |
|---|---|---|
| Trước 2026-11-13 | Xóa `03ad08c0` | ~166 từ khoảng 11-20 |
| ~11-21 | Dựng image, publish N | ~249 |
| Ngay khi N chạy ổn 1–2 lượt 08:00 (khoảng 11-22) | Đặt đích rollback = `dbb80f56`, xóa `5d32a104` | vẫn ~249, vì bảng đã xóa còn bị tính |
| 11-24 | D23 | ~332 |
| Khoảng 11-29 | Hết thời gian tính trễ của `5d32a104` | ~252 |

Nếu xóa `5d32a104` trễ, quota đỉnh lên khoảng 410†. Mốc ở hàng 3 là mốc chặn.

**Phải sửa trước lần dọn thứ hai:** `scripts/ops/don_ban_cu.py` (ba5ff85) không biết con trỏ `dashboard`. Thêm luật **G8: không xóa bản mà `dashboard` trỏ tới**, và hiện vai trò `dashboard` trong báo cáo. File này nằm ngoài phần băm (`cli.py:30–40`), nên không cần dựng image. Lần xóa `03ad08c0` không cần G8, vì trên cloud chưa có con trỏ `dashboard`.

**Lệnh (PM chạy, theo `giao_viec_don_ban_cu.md` §6):** dùng hàm `don` ở `giao_viec_don_ban_cu.md:117–121`.
1. `don` → báo cáo chỉ đọc. Kỳ vọng như bảng trên. Gửi Claude rà.
2. `don --xoa 03ad08c0ddbf4ce1848a1447` → chỉ in kế hoạch.
3. `don --xoa 03ad08c0ddbf4ce1848a1447 --thuc-hien` → xóa thật.
4. Mở web public, xem trang PS và hỏi một câu chat.

Script cần SQL warehouse để đọc registry, quét view (G6) và ghi CAS. Ngày 2026-11-07, script không chạy được vì warehouse không khởi động (§12). **Không lách bằng `databricks schemas delete`**, vì làm vậy bỏ qua luật G1–G7 và không sửa registry.

## 11. Đưa code lên (gỡ R2): cửa sổ bảo trì duy nhất

Lý do phải làm có kiểm soát: DAG production **tự publish** (`deploy/airflow/dags/retail_batch_pipeline.py:71`, `prepare >> … >> publish`). Image mới đổi `code_version`, nên lượt kế tiếp sẽ dựng và publish ngay mà không ai xem.

**Điều kiện vào cửa sổ:**
- L1, L2, L3a (§14) đã merge (chỉnh ngày 2026-11-09 theo Q12). L5 làm sau cửa sổ cũng được;
- D5a đã commit;
- `nap-ky/myuyen` đã merge vào `main`. Hiện nhánh chứa đủ `origin/main` và đi trước 74 commit;
- quota còn ít nhất 183 chỗ (100 + 83);
- app thử dưới đây đã đạt.

**App thử trước cửa sổ (PM chốt 2026-11-09).** Code mới chưa từng chạy trên Streamlit Cloud, nên phải thử mà không đụng web đang chạy. PM làm sau khi L1, L2, L3a đã merge, đủ thời gian sửa trước cửa sổ:
1. Tạo app Streamlit Cloud thứ hai, chạy từ `main` tại đúng commit sẽ đưa lên `app/myuyen`. App đang chạy trên `app/myuyen` giữ nguyên.
2. Chép secrets từ app đang chạy, **không thêm khóa `RETAIL_NHAP_*`**. `RETAIL_NHAP_DOT` mặc định là `tat`, nên app thử không ghi vào Volume.
3. Kiểm:
   - app mở được, không lỗi thiếu thư viện hay thiếu biến môi trường;
   - vẫn hiện bản `dbb80f56`, không có băng rôn;
   - số PS1 khớp web đang chạy;
   - một câu chat đúng.
4. Xóa app thử sau khi kiểm xong, và không chia sẻ link trong lúc thử vì app đọc dữ liệu thật.

Trượt thì sửa rồi thử lại, chưa vào cửa sổ. Cách này chỉ kiểm code mới với bản đang chạy, không kiểm phần đọc và ghi Volume; phần đó thuộc tổng duyệt dưới đây.

**Tổng duyệt đợt 2023 trên cloud trước cửa sổ (PM chốt 2026-11-09, Q13).** Upload thật trên Streamlit Cloud chưa từng chạy, và đường `--dot` target `databricks` mới kiểm bằng cloud giả. Lỗi lộ ra sau cửa sổ thì phần băm đã đóng băng. PM chạy một lượt thật từ giao diện theo script Claude viết:
1. Dựng image thử `retail-airflow:thu-l2` từ `git archive` của commit có L1, L2, L3a. Chạy một bộ Airflow thử riêng: compose project khác, metadata riêng, cổng khác, `RETAIL_PIPELINE_SCHEDULE_ENABLED=false`, và mount cùng `warehouse/pipeline` với Airflow đang chạy để dùng chung `writer.lock`, `state.json`, `snapshots`. `retail_batch_pipeline` trên Airflow đang chạy giữ nguyên. **Image thử bỏ hẳn file DAG `retail_batch_pipeline.py`** vì DAG đó tự publish; bộ thử chỉ có `nhap_du_lieu_do` và `retail_dot_pipeline`. Không chạy qua mốc 08:00. Script: `scripts/ops/tong_duyet.ps1`.
2. Tạo một app Streamlit Cloud tạm từ commit đó, thêm `RETAIL_NHAP_DOT=volume`, khóa `RETAIL_NHAP_DBX_*` của `retail-nhap-writer`, và `RETAIL_NHAP_VOLUME` trỏ vào thư mục riêng `/Volumes/retail_lab/nhap_du_lieu/kho/tong_duyet`. Airflow thử dùng đúng thư mục này. **Không dùng thư mục gốc của `kho`:** cùng bộ file có cùng mã đợt, đợt ở `da_kiem` không hủy được, nên lượt thật sẽ bị D2-7.
3. PM đăng nhập bằng tài khoản `quan_ly`, không dùng Admin, upload 15 file của `data_demo/dot_2023`. Luồng phải tự đi: `da_gui` → `dang_kiem` → `cho_chay` → `dang_chay` → `da_kiem`.
4. Tới `da_kiem` thì tắt `nhap_du_lieu_do` ngay. **Không bấm đưa lên dashboard, không chạy `publish`, không `dat-dashboard`:** lệnh `dat` trong thư mục thử vẫn đổi con trỏ `dashboard` thật. `active` và `dashboard` không đổi. Nhật ký audit trên Neon sẽ có thêm dòng của lượt thử.
5. Claude kiểm số dòng, G/COGS so với đối chứng của bộ sinh, quyền `retail-web-ro` có và `retail-ai-ro` không có trên bản này.
6. Dọn bằng `don --xoa <bản tổng duyệt> --thuc-hien` trước cửa sổ, để trang Duyệt không hiện bản này trong danh sách chọn. Bản này không phải `active`, đích rollback hay `dashboard`, nên luật G1–G3 và G8 không chặn. Xóa thêm app tạm, thư mục `tong_duyet`, và bộ Airflow thử (cả volume metadata của nó).

Lượt này không kiểm được bước `dat-dashboard` và image chính thức; hai phần đó vẫn kiểm ở lượt thật sau cửa sổ (§14, L2).

Lượt này tốn khoảng 83 chỗ quota, vẫn bị tính khoảng 7 ngày sau khi xóa†. **Xóa bản tổng duyệt trước khoảng 11-16** để hết bị tính trước 11-24: đỉnh ở Mốc 1 khoảng 332† (N 83, `dbb80f56` 83, `5d32a104` còn tính 80, D23 83, khác 3). Trễ hơn thì đỉnh khoảng 415†, và một lần chạy lại D23 có thể lên gần 500†. Số chưa kiểm lại. Trượt thì sửa rồi dựng lại image thử, chưa vào cửa sổ.

Sau cửa sổ, **đóng băng** `retail_dbt/*`, `scripts/{pipeline,ingest,parity,forecast}` và `apps/retail_app` tới 12/12. `scripts/demo` và `scripts/ops` vẫn sửa được.

1. Gắn tag commit hiện tại của `app/myuyen` để có đường quay lại. Đưa code app lên `app/myuyen`, Reboot. Kiểm web vẫn hiện bản `dbb80f56`, số PS1 khớp `assert_rpt_total.sql`, một câu chat đúng.
2. Gắn tag image cũ: `docker tag retail-airflow:local retail-airflow:truoc-r2`.
3. Tạm dừng `retail_batch_pipeline` trên giao diện Airflow.
4. Dựng image từ `git archive` của đúng commit đã merge (không dựng từ worktree đang có file của agent khác).
5. Chạy tay các stage `prepare`, `forecast`, `build`, `validate` bằng `docker exec … python -m scripts.pipeline.cli <stage> --run-id <id> --target databricks --root warehouse/pipeline/docker --extension orders_enriched`. Không trigger DAG, vì trigger sẽ tự publish.
6. PM kiểm số so với `dbb80f56`:
   - G/COGS theo ngày (validate đã so);
   - vài số dự báo trong chat, vì dự báo được học lại†.
7. `publish`, rồi bật lại DAG. Lượt 08:00 kế tiếp phải ra `bo_qua`.

**Rollback:** chỉ trả con trỏ về `dbb80f56` thì lượt 08:00 sẽ dựng lại bản mới, vì `code_version` lệch. Phải trả cả image (`retail-airflow:truoc-r2`) hoặc tạm dừng DAG cho tới khi sửa xong. Web lỗi ở bước 1 thì đưa `app/myuyen` về commit đã gắn tag rồi Reboot.

Claude sẽ viết lệnh đầy đủ thành một script cho PM chạy ngoài Claude Code.

## 12. Rủi ro

| Rủi ro | Bằng chứng | Cách đỡ |
|---|---|---|
| Warehouse không khởi động | 2026-11-07: lượt 08:00 lỗi `RequestError` ở `prepare` (`warehouse/pipeline/docker/runs/5382a026…/failure.json`, 01:04 UTC). Lệnh của Claude bị `BAD_REQUEST: Cannot create the resource, please try again later`. Warehouse `STOPPED`. Nghi là giới hạn của bản Free† (`docs/databricks_app_van_hanh.md:103`) | Tập đủ kịch bản trước 12/12 ít nhất 1 ngày. Ngày demo: bật dashboard từ sớm. Phương án lùi: video hoặc ảnh chụp từ buổi tập |
| Laptop tắt thì không dò | §8.3 T2 | Demo trên máy đang chạy Docker |
| Quota tính trễ khoảng 7 ngày | §10 | Lịch dọn ở §10; kiểm chỗ trước khi trigger (§5 bước 2) |
| RAM laptop khi dựng đồng thời | Pipeline từng bị giết vì thiếu RAM | Pool `retail_writer` (§5 bước 6); không chạy pipeline trong Claude Code |
| Khách thấy số tổng hợp | Q4 | Băng rôn, chỉ bật trong khung demo (§7.5) |

## 13. Nghiệm thu

**Mốc 1**
1. `chushop` gửi 12 file 2023 trên web public → trong khoảng 5 phút ra "Đang chạy", và không ai phải bấm gì cho tới khi ra "Đã kiểm tra". `active` không đổi; web vẫn hiện số thật.
2. Gửi lại đúng bộ đó → báo D2-7 hoặc "đã có", không tạo schema `r_` mới.
3. Bộ thiếu `orders` → `sai_hop_dong` đúng mã D2-missing, không tạo schema `r_` mới.
4. Admin bấm "Công bố lên dashboard" → trong khoảng 5 phút PS1–PS5 hiện kỳ có 2023, kèm băng rôn. Tài khoản khách cũng thấy như vậy. Trang Dự báo có dòng ghi chú; một câu chat về 2022 vẫn đúng số `active`.
5. Lượt 08:00 hôm sau → `bo_qua`, con trỏ dashboard còn nguyên.
6. "Trả dashboard" → PS về số thật; sổ đợt vẫn còn 2023.
7. `retail-nhap-writer` không đọc được bảng nào; `retail-web-ro` không đọc được Volume.

**Buổi tập** (trước 12/12 ít nhất 1 ngày): chạy lại mục 4 của Mốc 1 trên web public, rồi trả dashboard.

## 14. Lát làm (mỗi lát một phiếu GPT, Claude rà)

| Lát | Nội dung | Phần băm? | Kiểm |
|---|---|---|---|
| L0 | Dọn `03ad08c0` (PM); commit D5a; merge `nap-ky` vào `main` | không | §10 |
| L1 | Lớp lưu Volume, loại yêu cầu "đợt" ở trang Gửi, trạng thái ở trang Duyệt, nút dashboard ghi lệnh (§3, §4, §7.3, §7.4) | có | test với Volume giả; S0 đã chứng minh `overwrite=false` |
| L2 | DAG `nhap_du_lieu_do`, `--dot` trên databricks, DAG `retail_dot_pipeline` theo conf, pool, quyền chỉ cho web (§5, §6, §7.1, §7.2) | có | cloud giả, cộng một lượt thật sau cửa sổ |
| L3a | Ba chỗ sửa chữ (`giao_viec_l3a_sua_chu.md`) | có | test local |
| L3, L4 | Đợt 2024: hoãn tới sau 12/12 (Q12), không làm ở đợt này | | |
| L5 | G8 cho `don_ban_cu.py` (§10). Hạn trước lần xóa `5d32a104` khoảng 11-22 | không | cloud giả |
| — | App thử trên Streamlit Cloud (§11), sau khi L1, L2, L3a đã merge | không | PM chạy |
| — | Cửa sổ bảo trì (§11), sau L1, L2, L3a và app thử | | PM chạy |

L5 làm sau cửa sổ cũng được. Thời gian mỗi lát chưa ước†. Nếu L1, L2, L3a chưa xong trước khoảng 11-21 thì Mốc 1 trễ theo.

## 15. Câu còn mở

Không còn câu nào. PM chốt ngày 2026-11-07 theo đề xuất của Claude, xem Q7–Q11 ở §0. Phần "auto mapping trên web public" thể hiện qua phân loại đợt (`khop_loi`, `loi_kem_cot_them`).

Việc kế:
1. PM dọn `03ad08c0` khi warehouse chạy lại (§10).
2. GPT làm L3a (L1, L2 đã đạt); L5 làm sau cũng được.
