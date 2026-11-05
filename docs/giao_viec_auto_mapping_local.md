# Giao việc: hoàn thiện auto mapping ở local (đề xuất đủ 5 file, thêm file thứ hai chạy trọn đường)

Soạn ngày 2026-11-05. PM chốt ưu tiên và phạm vi cùng ngày, sau khi thầy hướng dẫn cho biết auto mapping được chạy ở local.
**PM đã duyệt phạm vi và chốt §10; sẵn sàng giao GPT.** Claude soạn phiếu và rà độc lập; GPT viết code; PM chạy nghiệm thu trên trình duyệt.

Số gắn † là số Claude đo bằng script ngày 2026-11-05, chưa có cell notebook. Không dùng số † cho kết luận báo cáo khi chưa có cell.

Đọc trước:
- `AGENTS.md`, `CLAUDE.md`, `docs/agent_workflows.md`;
- `docs/tien_hoa_schema.md` §5b (bảng nghiệm thu), §6.1, §7, §10 câu 3;
- `docs/giao_viec_auto_mapping_lat1.md` §9, `docs/giao_viec_auto_mapping_lat3.md` (mẫu dbt cho phần mở rộng), `docs/giao_viec_duong_tu_dong.md` §3 và §9 (lỗi khóa, worker đã sửa, đừng tái phạm).

## 0. Vì sao cần

| File | Đề xuất hiện nay so với §5b | Hiện đi tới đâu |
|---|---|---|
| `orders_enriched.csv` | Đủ các ý đã kiểm | Tự chạy tới công bố |
| `shipments_realistic.csv` | Đủ các ý đã kiểm | Dừng, chưa có hợp đồng và model |
| `eprom.json` | Thiếu đề xuất `promotions_ext` | Dừng chờ người |
| `epd.json` | Có số đếm, chưa có bảng ánh xạ, chưa tách dòng không khớp | Dừng chờ người, đúng ý đồ |
| `tf.json` | Thấy 998 ngày trùng, chưa báo hậu tố `Variant`, chưa liệt kê giá trị lạ | Dừng chờ người |

Phiếu lát 1 đã gác các phần này cho "lát sau" nhưng chưa lát nào làm. Phiếu này làm hai việc: **Phần A** cho đề xuất đủ bảng §5b trên cả 5 file; **Phần B** cho `shipments_realistic` đi trọn đường, để chứng minh hệ thống không chỉ viết riêng cho một file.

## 1. Phạm vi

**Làm Phần A trước, dừng, báo cáo, chờ Claude rà đạt rồi mới làm Phần B.** Phần A đã đạt ngày 2026-11-05, xem §9 mục "Claude rà Phần A".

**Không làm:**
- nạp thật `eprom`, `epd`, `tf`: ba file này dừng ở chờ người là kết quả đúng;
- áp dụng luật sửa, tự sửa giá trị, tự chọn hợp đồng: máy chỉ đề xuất (§5b "Máy không bao giờ tự làm");
- F5 giữ đăng nhập (phiếu riêng, vì đụng đăng nhập của bản public);
- T2, Databricks, Airflow, Streamlit Cloud, dựng lại image;
- metric, trang, chat theo shipper (giống lát 5 đã bỏ: auto mapping chỉ tới data engineering);
- thu nhỏ 14 nguồn lõi.

## 2. Môi trường và ràng buộc

- Worktree `D:/retail-analytics-am`, nhánh `auto-mapping/myuyen` từ `origin/main` `fe1f65c`. Python: `D:/retail-analytics/.venv/Scripts/python.exe`. Đã có `data/` (gồm `student_data`, không có `ui_nhap`) và `warehouse/dbt.duckdb`, nên test có dữ liệu chạy được, kho nhập bắt đầu sạch.
- **Không sửa `scripts/pipeline/cli.py`, `scripts/pipeline/snapshot.py`, `scripts/ingest/extension_prepare.py`:** D2 đang sửa ba file này ở nhánh khác. Nếu cần sửa mới làm được thì dừng, ghi §8, hỏi.
- **Không sửa `scripts/ingest/extensions/orders_enriched.yml`, `scripts/ingest/source_contract.py`:** hash nằm trong `snapshot_id`, hợp đồng lõi không đổi.
- Không commit, không stage, không push. Không kết nối cloud. Không in tên, số điện thoại, tuổi, giới tính của nhân viên hay shipper ra log, báo cáo, test output; báo cáo cho Claude chỉ ghi số đếm và tên cột.
- `data/`, `warehouse/`, `.streamlit/secrets.toml` đã gitignore, không vào git.
- Chạy `apps` và `scripts` trong hai lệnh pytest riêng (trùng tên `conftest`).

## 3. Phần A: đề xuất đủ bảng §5b

Chỉ sửa `scripts/ingest/auto_mapping.py`, `scripts/ingest/approval.py` (riêng `tom_tat_nghiep_vu`) và test. Tất cả là **khóa mới trong `propose`, mặc định rỗng**. `phien_ban` của đề xuất giữ 1; nơi đọc dùng `.get`, để đề xuất cũ vẫn mở được.

**Không đổi:** `score_sources`, `phan_loai`, `default_decisions`, `hop_dong_tu_de_xuat`, các khóa đang có. `orders_enriched` phải vẫn ra `tu_dong`; không khóa mới nào được chuyển thành quyết định hay đi vào hợp đồng.

### A1. Bảng ánh xạ khóa

Thêm vào `xung_dot_khoa` khi `da_kiem` đúng:
- `id_rong`: số dòng khóa rỗng;
- `id_trung_trong_file`: số khóa khác rỗng dư, tức `count(khóa) - count(distinct khóa)`;
- `khong_khop`: số dòng không khớp đúng 1 bản ghi nguồn theo thuộc tính;
- `anh_xa`: danh sách `{id_trong_file, id_nguon}` của các dòng **khớp đúng 1** mà id khác id nguồn (`is distinct from`, nên gồm cả id rỗng), sắp theo `id_nguon` rồi `id_trong_file`. Rỗng khi không có dòng nào. Tất cả ở trạng thái đề xuất.

Dùng lại phép so của `key_conflicts`, không viết phép so thứ hai. `render_report` thêm một mục: số dòng và 5 dòng đầu; bản đủ nằm trong YAML.

### A2. Đề xuất nguồn mở rộng cho master data

Thêm khóa `nguon_mo_rong_de_xuat` (mặc định `None`). Chỉ xét `promotions`, `products`, `customers`. Điều kiện đủ cả ba:
1. `xung_dot_khoa.da_kiem` đúng và `id_trung_nguon = 0`;
2. file có ít nhất một dòng có khóa khác rỗng;
3. đếm được số dòng bảng con tham chiếu tới id của file và số đó **bằng 0**; lớn hơn 0 thì không đề xuất. Đếm qua hằng số viết tay:

```python
THAM_CHIEU_CON = {'promotions': [('order_items', 'promo_id'), ('order_items', 'promo_id_2')],
                  'products': [('order_items', 'product_id'), ('inventory', 'product_id')],
                  'customers': [('orders', 'customer_id')]}
```

Kết quả: `{ten: '<nguồn>_ext', hien_thi: 'silver', id_chung_nguon, dong_con_tham_chieu, ban_ghi_giong_nguon, trang_thai: 'de_xuat'}`, trong đó `ban_ghi_giong_nguon` lấy từ `danh_lai_khoa`. Thiếu file bảng con thì **không** coi là 0: ghi tên vào `tham_chieu_thieu` và để `None`.

### A3. Giá trị lạ

Thêm khóa `gia_tri_la`, danh sách theo cột, **chỉ các cột `loai = khop`**, bỏ cột không có gì:
- `khong_ep_duoc`: số dòng và tối đa `SAMPLE_LIMIT` giá trị, sắp theo tần suất giảm dần rồi giá trị;
- với cột kiểu `integer`, `double`, `decimal(...)`, khi có file tham chiếu cùng tên nguồn:
  - `so_am`: số dòng âm, chỉ khi giá trị nhỏ nhất của tham chiếu không âm;
  - `vuot_nguong`: số dòng lớn hơn `GIA_TRI_LA_HE_SO = 10` lần giá trị lớn nhất của tham chiếu; ghi cả ngưỡng đã dùng.

Không có tham chiếu thì ghi `chua_kiem_mien: true`, không ghi 0. Chỉ báo, không sửa, không loại dòng. Không đổi `khong_ep_duoc` đang có trên từng cột, vì `phan_loai` đọc khóa đó.

### A4. Luật sửa ứng viên

Thêm khóa `luat_sua_ung_vien`. Với cột `khop` kiểu chuỗi, tìm mẫu đuôi `<khoảng trắng><một từ chữ><khoảng trắng><chữ số>` bằng regex tổng quát, **không viết chữ `Variant` vào code**. Gom theo từ. Đề xuất khi:
- ít nhất `LUAT_SUA_TY_LE = 0.9` số dòng khác rỗng có cùng từ đuôi; và
- sau khi bỏ đuôi, ít nhất `LUAT_SUA_KHOP = 0.99` số dòng đó có giá trị thuộc cột cùng tên của file tham chiếu.

Kết quả: `{cot, mau, so_dong, tong_khac_rong, khop_sau_khi_bo, trang_thai: 'de_xuat', da_ap_dung: false}`. Điều kiện thứ hai để tránh nhận nhầm tên có sẵn đuôi năm. **Không code nào được đọc khóa này để biến đổi dữ liệu.**

### A5. Báo cáo

`render_report` thêm mục cho A1–A4. Mọi giá trị từ file phải qua `_md`. `tom_tat_nghiep_vu` thêm tối đa hai dòng lời thường cho chủ shop, không chữ kỹ thuật, ví dụ "Có 5 giá trị không đọc được hoặc bất thường; đội dữ liệu sẽ kiểm tra." và "Dữ liệu này có mã riêng, nên đề xuất lưu tách, không trộn với khuyến mãi đang có." Không hiển thị giá trị lạ cho chủ shop.

### A6. Kết quả phải ra trên file thật (†)

| File | Kỳ vọng |
|---|---|
| `tf.json` | Luật sửa `traffic_source`: `so_dong` 998, `tong_khac_rong` 999, `khop_sau_khi_bo` 998 (sau trim; sửa 2026-11-05, xem §9). Giá trị lạ: `date` 2 (`2026-99-99`, `not_a_date`); `sessions` không ép được 1 (`N/A`), âm 1, vượt ngưỡng 1 (`999999999`); `unique_visitors` không ép được 1 (`unknown`), âm 1. Không đề xuất `web_traffic_ext` |
| `epd.json` | `id_rong` 2, `id_trung_trong_file` 1, `khop_dung_1` 995, `khong_khop` 5, `anh_xa` 995 dòng. Giá trị lạ `price`: không ép được 1 (`N/A`), âm 1, vượt ngưỡng 1. Không đề xuất `products_ext` (998 id trùng nguồn) |
| `eprom.json` | `nguon_mo_rong_de_xuat.ten` = `promotions_ext`, `id_chung_nguon` 0, `dong_con_tham_chieu` 0, `ban_ghi_giong_nguon` 217. Giá trị lạ `discount_value`: không ép được 2 (`twenty percent`, `30%%`), âm 1. `nguon.de_xuat` vẫn là `promotions` |
| `orders_enriched.csv`, `shipments_realistic.csv` | `phan_loai` như cũ: `tu_dong`, `can_nguoi` với `chua_co_hop_dong`. Không có `nguon_mo_rong_de_xuat`, `anh_xa` rỗng. Báo cáo số dòng `gia_tri_la`, `luat_sua_ung_vien` nếu có, kèm giải thích |

217 là dòng thật: Claude đối chiếu độc lập ngoài `auto_mapping`, 217 dòng `eprom` giống đúng một khuyến mãi trên mọi thuộc tính, chỉ khác id. Nếu ra khác bảng này, **dừng và báo**, không tự đổi kỳ vọng.

### A7. Test Phần A

Thêm vào `scripts/ingest/tests/test_auto_mapping.py`. Fixture nhỏ, **số viết tay**, không tính bằng chính hàm đang test:
- mỗi mục A1–A4 có một ca đúng và ca âm: A2 thiếu file bảng con, có một id trùng nguồn, có một dòng con tham chiếu, nguồn ngoài ba nguồn; A3 không có tham chiếu, tham chiếu có sẵn số âm, đúng bằng ngưỡng và vừa vượt ngưỡng; A4 từ đuôi khác `Variant` vẫn nhận, đuôi năm mà sau khi bỏ không khớp tham chiếu thì không nhận, 89% không nhận, 90% nhận;
- test tích hợp bảng A6, bỏ qua có lý do nếu thiếu `data/student_data`;
- `default_decisions`, `hop_dong_tu_de_xuat`, `phan_loai` không đổi kết quả khi đề xuất có đủ khóa mới; đề xuất kiểu cũ không có khóa mới vẫn đọc và render được;
- nội dung độc trong file (`|`, `<`, xuống dòng) không phá báo cáo Markdown;
- `tom_tat_nghiep_vu` không chứa giá trị lạ.

## 4. Phần B: `shipments_realistic` đi trọn đường

Chỉ bắt đầu sau khi Phần A đạt.

### B1. File thử

Đã có `data/student_data/demo_2022/shipments_realistic.csv`† (30.211 dòng, 5,4 MB): lọc theo đúng các đơn trong `demo_2022/orders_enriched.csv`. Không sinh lại, không sửa.

### B2. Hợp đồng `scripts/ingest/extensions/shipments_realistic.yml`

`header` đúng thứ tự file đầy đủ, `file: student_data/shipments_realistic.csv`, `khoa_noi: {cot: order_id, nguon: shipments, cot_nguon: order_id}`, `nguong_cach_ly: 0.01`. Kiểu viết rõ trong hợp đồng, không lấy từ `default_decisions` (hàm này chỉ gợi ý `integer` hoặc `string`, và ép cột nghi PII về `string`):

| Cột | `xu_ly` | `kieu` | `hien_thi` |
|---|---|---|---|
| `order_id` | `khoa_noi` | `integer` | |
| `ship_date`, `delivery_date`, `shipping_fee` | `doi_chieu_loi` | | |
| `shipper_id`, `shipper_company`, `shipper_vehicle`, `working_shift`, `shipper_name`, `shipper_phone`, `city`, `region`, `district` | `nap` | `string` | `mart` |
| `shipper_experience_years`, `average_delivery_time` | `nap` | `integer` | `mart` |
| `shipper_rating`, `delivery_success_rate` | `nap` | `double` | `mart` |
| `join_date` | `nap` | `date` | `mart` |
| `shipper_gender`, `shipper_marital_status`, `shipper_education` | `nap` | `string` | `silver` |
| `shipper_age` | `nap` | `integer` | `silver` |

`duoc_rong` theo số rỗng đo được (Claude đo 0 ô rỗng trên cả hai file†, nên mọi cột đều không được rỗng); báo cáo số đó. `thuc_the`: `shipper`, khóa `shipper_id`, 17 thuộc tính. `duyet_boi: PM (myuyen0304)`, `ngay_duyet: '2026-11-05'`. Lượt trên **file đầy đủ** và file nhỏ đều phải 0 dòng cách ly; nếu không, dừng và báo, không nới kiểu.

### B3. dbt

Theo đúng mẫu lát 3, bật bằng `extension_enabled('shipments_realistic')`:
- `stg_shipments_realistic`, thêm nguồn vào `_sources.yml`, mô tả vào `_extensions.yml`;
- `dim_shipper`: Type 1, một dòng mỗi `shipper_id`, `shipper_sk` đánh số theo `shipper_id`. Mô tả phải ghi: thuộc tính là ảnh chụp hiện tại, `join_date` sau `ship_date` ở 91,73% dòng file đầy đủ và 53,18% dòng file nhỏ†, không phân tích "kinh nghiệm shipper lúc giao"; `city`, `region`, `district` là của shipper, không phải của đơn;
- `fact_order` thêm `shipper_sk`, được rỗng, left join qua `stg_shipments_realistic`, đặt trong khối `{% if %}` để lúc tắt SQL biên dịch **không đổi**;
- test dbt độc lập với cách đánh số: khóa thay thế, khóa tự nhiên, phụ thuộc hàm 17 thuộc tính, số shipper, mỗi đơn tối đa một shipper, số dòng `fact_order` không đổi, `shipper_sk` đúng theo nguồn;
- `assert_rpt_health.sql:66,68`: bỏ cố định `14 + (1 if orders_enriched)`, đếm theo số phần mở rộng đang bật, kể cả khi bật cả hai. Kiểm `apps/retail_app/tests/test_databricks.py` đang đếm nguồn theo cách nào; đừng để nó sai với 16 nguồn. Khối kiểm này chỉ biên dịch khi `target.type` là `postgres` hoặc `databricks`, nên lượt DuckDB không chứng minh được nó: viết test riêng cho biểu thức đếm và ghi rõ trong báo cáo là khối đó chưa chạy thật.

Cổng `validate_extension_visibility` chỉ kiểm tên cột trên toàn schema mart, mà `city`, `region`, `district` đã có ở `dim_geography`, nên cổng này **không** chứng minh chúng có trong `dim_shipper`. Test dbt phải kiểm trực tiếp cột của `dim_shipper`.

### B4. Một lượt chạy giữ cả bộ đang hiệu lực

Hiện `nhap_runner.lenh` chỉ truyền một `--extension`, nên công bố `shipments` sẽ làm mất `dim_sales_employee` khỏi bản đang phục vụ. Áp lại quy tắc PM đã duyệt ở `docs/thiet_ke_duong_tu_dong.md` §8.4 mục 2 (lượt nhập nguồn mới phải gộp cả bộ đang hiệu lực), mức local:

- **Tập phần mở rộng của lượt = tập của bản `active` ∪ {phần của yêu cầu này}.** Tính lúc bắt đầu lượt trong `_start_locked`, không tính lúc duyệt, vì hàng đợi có thể làm `active` đổi. Ghi vào yêu cầu (`mo_rong_chay`); `_stage` của đúng lượt đó dùng giá trị đã ghi. **Sửa 2026-11-05 (Claude, xem B6 ở §9):** lượt mới của cùng yêu cầu phải tính lại, không dùng lại bộ của lượt trước.
- Hợp đồng của phần còn lại **chép từ `extension_dir` của bản `active`**, không lấy bản mới nhất trong registry, vào `hop_dong/` của yêu cầu. Phần trùng tên thì hợp đồng của yêu cầu thắng. File dữ liệu giữ nguyên đường dẫn trong hợp đồng đó.
- **Dừng với lỗi rõ, `active` giữ nguyên** nếu context của `active` không đọc được, thiếu hợp đồng hoặc thiếu file. Không âm thầm bỏ phần mở rộng.
- Áp dụng cả cho đường tự động, đường tay, chạy lại và nạp bù (`upgrade_contract`).
- `active` chưa có thì chỉ phần của yêu cầu, như hiện nay.
- `lenh` nhận danh sách tên, kiểm từng tên theo regex hiện có; thứ tự xác định.
- `summary` không gắn cứng `orders_enriched`: phần nào đang bật thì có số của phần đó (`dim_shipper`, số đơn có shipper). Sửa dòng thông báo `views/duyet_du_lieu.py:20`.

### B5. Test Phần B

- Không `active`; `active` có `orders_enriched` rồi chạy `shipments`; gửi lại cùng tên thì hợp đồng yêu cầu thắng; sau rollback thì lấy theo bản rollback; `active` đổi giữa lúc duyệt và lúc chạy; thiếu hợp đồng, thiếu file: báo lỗi, không chạy tiếp, không đổi registry; chạy lại dùng đúng `mo_rong_chay`.
- Worker thật trên fixture: công bố `orders_enriched` rồi `shipments`, bản cuối có cả `dim_sales_employee` và `dim_shipper`.
- Phân loại: file shipments đủ cột ra `tu_dong`; thiếu cột ra `can_nguoi` với `thieu_cot`; `epd`, `tf`, `eprom` vẫn `can_nguoi`.

## 5. Lệnh chạy

Chạy tại root worktree, tuần tự:

```powershell
& D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider scripts/ingest/tests -q --tb=short -rs
& D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider scripts/pipeline/tests -q --tb=short -rs
& D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider apps/retail_app/tests/test_nhap_du_lieu.py apps/retail_app/tests/test_nhap_theo_doi.py apps/retail_app/tests/test_nhap_tu_dong.py apps/retail_app/tests/test_extension_grants.py -q --tb=short -rs
```

Phần B thêm một lượt CLI, root riêng, không publish:

```powershell
& D:/retail-analytics/.venv/Scripts/python.exe -B -m scripts.pipeline.cli prepare --run-id am-b --root warehouse/pipeline/am-b --extension orders_enriched --extension shipments_realistic
& D:/retail-analytics/.venv/Scripts/python.exe -B -m scripts.pipeline.cli forecast --run-id am-b --root warehouse/pipeline/am-b
& D:/retail-analytics/.venv/Scripts/python.exe -B -m scripts.pipeline.cli build --run-id am-b --root warehouse/pipeline/am-b
& D:/retail-analytics/.venv/Scripts/python.exe -B -m scripts.pipeline.cli validate --run-id am-b --root warehouse/pipeline/am-b
```

Hai hợp đồng trong repo trỏ tới **file đầy đủ**, nên lượt này kiểm cả yêu cầu 0 dòng cách ly ở B2. `forecast` mất khoảng 6 phút theo lần đo 2026-10-31†. Nặng thì ghi "chưa chạy" ở báo cáo để PM chạy; bị dừng vì thiếu RAM thì đừng tự chạy lại.

## 6. Nghiệm thu do PM chạy, sau khi Phần B đạt

PM chép `secrets.toml` từ `D:\retail-analytics-nhap\.streamlit\` sang worktree mới, chạy app local, không F5:
1. Gửi `demo_2022/orders_enriched.csv` → tự chạy → công bố → có 200 nhân viên.
2. Gửi `demo_2022/shipments_realistic.csv` → tự chạy → công bố → có 80 shipper, nhân viên vẫn còn 200.
3. Gửi `epd.json`, `tf.json`, `eprom.json` → dừng ở chờ đội dữ liệu; trang Duyệt hiện đúng bảng A6; không tạo lượt chạy.
4. Rollback về bản sau bước 1 → không còn shipper, nhân viên vẫn còn.
5. Số G, COGS không đổi qua các bước (cổng `validate` đạt).

## 7. Claude sẽ tự kiểm

- **Không hồi quy, so từng byte với `fe1f65c`:** snapshot 14 nguồn `5bd9a84aaf73`, snapshot `orders_enriched` `47e7cbe765d9` giữ nguyên. Chỉ bật `orders_enriched` thì SQL biên dịch và số ở marts giống hệt, trừ siêu dữ liệu build.
- Tính lại bảng A6 bằng DuckDB, không qua `auto_mapping`.
- Đọc parquet và mart của lượt B bằng script độc lập: 80 shipper, số đơn có shipper, phụ thuộc hàm, không cột `silver` nào trên mart, `dim_shipper` có đúng cột hợp đồng.
- Làm hỏng từng mệnh đề (A1–A4, B4, hằng số `THAM_CHIEU_CON` từng dòng, ngưỡng); đột biến nào sống thì coi như chưa kiểm.
- Không dùng test của GPT làm bằng chứng duy nhất. Không tin số báo cáo khi chưa chạy lại.

## 8. Câu chưa chắc thì hỏi

Dừng và ghi vào §9, đừng đoán, nếu: số thật khác bảng A6; hợp đồng làm cách ly dòng; cần sửa file cấm ở §2; `snapshot_id` đổi khi tắt phần mở rộng.

## 9. Báo cáo của GPT và kết quả rà

### GPT — dừng vì số thật khác A6, ngày 2026-11-05

**Phần A chưa hoàn tất. Đã dừng triển khai theo chỉ thị của PM và §8; chưa làm Phần B. Không sửa số kỳ vọng hoặc dữ liệu.**

Worktree `D:/retail-analytics-am`, nhánh `auto-mapping/myuyen`. Đọc hết phiếu trước khi sửa. Khi bắt đầu, `docs/tien_hoa_schema.md` đã có thay đổi và phiếu này chưa được Git theo dõi; giữ nguyên thay đổi tài liệu có sẵn.

**Điểm chặn: `tf.json`, luật hậu tố của `traffic_source`.**

| Số đếm | Kỳ vọng A6 | Đo trên file của worktree |
|---|---:|---:|
| Tổng dòng file | 1000 | 1000 |
| `so_dong` có hậu tố | 997 | **998** |
| `tong_khac_rong` | 1000 | **999** |
| `khop_sau_khi_bo` | 997 | **998** |
| Dòng rỗng ở traffic_source | — | **1** |

Đã xác nhận chênh lệch bằng **hai cách**: bản nháp `propose` dùng DuckDB; và Python chuẩn `json`/`csv`/`re`, không import code repo. Cách độc lập đọc `tf.json`, trim giá trị traffic_source, đếm khác rỗng, tìm hậu tố bằng regex tổng quát `\s+([^\W\d_]+)\s+[0-9]+$`, rồi so giá trị sau bỏ hậu tố với tập traffic_source trong `data/web_traffic.csv`. Hai cách cùng ra **998 / 999 / 998**. Chỉ in số đếm và hash; không in dữ liệu nhân viên/shipper.

SHA256 file đã đo `data/student_data/tf.json`: `44b8a6749f8961cc2a4a1c2e49440bf64d25fe3ce6863484b135ec015a694e19`.

**Các số đã đo trước khi nhận kết quả chặn** (chạy trong cùng lượt đọc ba JSON, chỉ là bằng chứng kỹ thuật bằng script, chưa có cell notebook):

- tf: date không ép được 2; sessions không ép được 1, âm 1, vượt ngưỡng 1, ngưỡng 509470; unique_visitors không ép được 1, âm 1. Không có nguồn mở rộng được đề xuất trong bản nháp.
- epd: id_rong 2, id_trung_trong_file 1, khop_dung_1 995, khong_khop 5, anh_xa 995; id_trung_nguon 998. Khóa cũ danh_lai_khoa vẫn 993 (không tính hai id rỗng như định nghĩa cũ). price không ép được 1, âm 1, vượt ngưỡng 1 (ngưỡng 409500.0).
- eprom: nguồn promotions, 1000 dòng; id_trung_nguon 0, danh_lai_khoa 217; discount_value không ép được 2 và âm 1. **Chưa triển khai A2**, nên chưa nhận là đạt đề xuất promotions_ext.
- Chưa đo các khóa mới trên orders_enriched/shipments_realistic; không nhận là đã đạt toàn bộ A6.

**Một điểm cần chốt riêng ở A2/A7, đã gửi câu hỏi trước khi viết A2:** A2 mục 3 yêu cầu “đếm được số dòng bảng con tham chiếu”, không nêu số phải bằng 0; A7 gọi trường hợp “có một dòng con tham chiếu” là ca âm. Cần xác nhận số > 0 có chặn đề xuất *_ext hay chỉ ghi số vào đề xuất. Chưa tự chọn cách hiểu.

**Thay đổi nháp đang để lại, chưa nghiệm thu:**

- `scripts/ingest/auto_mapping.py`: A1 dùng lại cùng phép so thuộc tính, giữ bảng kết quả tạm để lấy số đếm cũ và ánh xạ mới, gồm id rỗng bằng `is distinct from`; A3 bằng chứng không ép được/âm/vượt ngưỡng trên cột khớp; A4 regex hậu tố tổng quát và đối chứng tham chiếu, không áp dụng sửa; A5 các mục báo cáo mới có escape. `nguon_mo_rong_de_xuat` mới chỉ có giá trị mặc định None; A2 chưa làm.
- `scripts/ingest/approval.py`: chỉ thêm trong `tom_tat_nghiep_vu` tối đa hai câu tóm tắt bằng số đếm, không đưa giá trị lạ ra cho chủ shop.
- Phiếu này: chỉ điền §9.

Không sửa score_sources, phan_loai, default_decisions, hop_dong_tu_de_xuat. Không sửa năm file cấm ở §2; `git diff --exit-code -- scripts/pipeline/cli.py scripts/pipeline/snapshot.py scripts/ingest/extension_prepare.py scripts/ingest/extensions/orders_enriched.yml scripts/ingest/source_contract.py` exit 0. Không sửa data, không đọc secrets, không stage/commit/push, không kết nối cloud.

**Lệnh và kiểm đã chạy:** các phép đo dùng `& D:/retail-analytics/.venv/Scripts/python.exe -B -` với script truyền qua stdin tại root worktree. Lượt đo code cũ trên ba JSON exit 0; lượt đo nháp đầu gặp ParserException do bí danh SQL `overlaps`, đã đổi bí danh nội bộ thành `overlap_count`; lượt đo nháp sau và phép đo độc lập đều exit 0. Khi thấy số khác A6, chỉ kiểm lại số bằng cách độc lập và ghi báo cáo, không triển khai thêm. `git diff --check` đạt, không có file staged.

**Pytest: chưa chạy; chưa thêm A7 do dừng ở điểm chặn dữ liệu. Không có số test đạt/trượt/bỏ qua để công bố.** Ba lệnh §5, kiểm hồi quy các quyết định/hợp đồng, tích hợp đủ năm file và Phần B đều chưa chạy. Cần PM/Claude xác nhận đúng bản dữ liệu hoặc sửa bảng A6, đồng thời chốt A2, trước khi tiếp tục. Không tự đổi kỳ vọng 997/1000/997.

### Claude trả lời điểm chặn, ngày 2026-11-05

**GPT dừng đúng; bảng A6 của Claude sai, không phải code.**

- **`tf.json`: đúng là 998 / 999 / 998.** Claude đo lại bằng Python thuần trên cùng file (sha256 `44b8a674…`), kết quả khớp GPT. Lỗi của Claude: phép đếm 997 không trim, nên bỏ sót một dòng có khoảng trắng hai đầu; và `tong_khac_rong` 1000 chưa từng được đo, vì có một dòng rỗng. Dự án luôn trim giá trị, nên 998 là số đúng. Hai dòng không có hậu tố là dòng rỗng và `N/A`. Đã sửa A6.
- **Bổ sung A6 theo số GPT đo, Claude đã đo lại:** `epd.price` âm 1, vượt ngưỡng 1; `eprom.discount_value` âm 1. Các số khác GPT báo đều khớp bảng.
- **A2/A7:** số dòng con lớn hơn 0 thì **không** đề xuất `*_ext`. Các id này không có trong nguồn mà đã có giao dịch dùng, nên không phải dữ liệu tách riêng được; để người xử lý. Đã sửa A2 mục 3. Đây là việc phiếu ghi thiếu, §5b đã ghi kỳ vọng 0 dòng `order_items`.

Các thay đổi nháp của GPT giữ nguyên để làm tiếp. Chưa rà code nháp.

**Ghi chú, không thuộc phạm vi GPT:** `tien_hoa_schema.md` dòng "997/1.000" là số của cell notebook không trim, vẫn đúng với cell đó; luật sửa trong code dùng số sau trim.

### GPT — hoàn tất Phần A sau khi chốt điểm chặn, ngày 2026-11-05

**Đã hoàn tất Phần A; dừng để Claude rà, chưa làm Phần B.** Đọc lại toàn bộ phiếu, đặc biệt A2 mục 3, A6 và mục trả lời điểm chặn của Claude. Giữ các thay đổi nháp; sử dụng số tf đã chốt **998/999/998** và điều kiện số dòng con **bằng 0**. Không tự sửa kỳ vọng.

**Phạm vi thay đổi:**

- `scripts/ingest/auto_mapping.py`: hoàn tất A1–A5. A1 dùng chung kết quả so thuộc tính của `key_conflicts` cho số đếm cũ và bảng ánh xạ mới, không viết phép so khác. A2 thêm `THAM_CHIEU_CON` đúng năm đường tham chiếu đã chốt; chỉ đề xuất master tách riêng khi đủ điều kiện. Thiếu tham chiếu thì ghi `tham_chieu_thieu`, không nhận là 0. Một dòng con có nhiều khóa cùng trỏ tới file chỉ đếm một lần. A3 chỉ kiểm cột khớp; mẫu sắp theo tần suất giảm dần rồi giá trị, giới hạn SAMPLE_LIMIT; thiếu tham chiếu ghi chưa kiểm miền. A4 regex tổng quát, gom theo từ hậu tố, dùng hai ngưỡng đã chốt; không sửa dữ liệu. A5 thêm các mục bằng chứng, bảng ánh xạ chỉ hiện năm dòng đầu; giá trị từ file qua `_md`.
- `scripts/ingest/approval.py`: chỉ bổ sung `tom_tat_nghiep_vu`, tối đa hai câu bằng số đếm/lời thường; không hiển thị giá trị lạ cho chủ shop.
- `scripts/ingest/tests/test_auto_mapping.py`: **46 ca mới** cho A1–A7; cả file hiện có 80 ca (34 cũ + 46 mới).
- Phiếu này: chỉ thêm báo cáo vào §9. `docs/tien_hoa_schema.md` đã sửa trước khi giao, GPT không đụng tới.

Giữ `phien_ban=1`; khóa mới có giá trị mặc định rỗng, nơi đọc dùng `.get`. Không sửa `score_sources`, `phan_loai`, `default_decisions`, `hop_dong_tu_de_xuat`. Đã so AST của ba hàm đầu/cuối thuộc các file đang sửa với HEAD: `score_sources`, `default_decisions`, `hop_dong_tu_de_xuat` giống nguyên; file `tu_dong.py` không có diff. Các test cũng so kết quả phân loại, quyết định và hợp đồng khi thêm đủ bằng chứng mới với đề xuất cũ.

**Các ca kiểm chính của A7:**

- A1: id rỗng, id dư trong file, khớp đúng một nguồn, khớp nhiều nguồn, không khớp; ánh xạ có id rỗng, đúng thứ tự; giữ dung sai số của phép so cũ, không ánh xạ dòng đã cùng id.
- A2: ca đạt cho cả promotions/products/customers; riêng từng đường trong năm đường tham chiếu đều có ca thiếu file và ca có dòng con tham chiếu; id trùng nguồn, chưa kiểm khóa, toàn id rỗng, nguồn ngoài ba nguồn đều không đề xuất; thiếu bảng con được đưa vào đề xuất tổng qua `tham_chieu_thieu`.
- A3: integer/double/decimal; không tham chiếu, tham chiếu có số âm; bằng ngưỡng không báo, vượt ngưỡng báo; mẫu đủ kiểm thứ tự tần suất và giới hạn năm giá trị; cột không khớp bị bỏ qua; cột sạch không có mục, ngày sai được báo.
- A4: từ hậu tố khác tên trong file thật; 89% không nhận, 90% nhận; khớp sau bỏ đuôi 98% không nhận, 99% nhận; đuôi năm mà bỏ đi không khớp nguồn thì không nhận; hai từ đuôi chia thành hai nhóm không gộp để vượt ngưỡng; không nhận hậu tố chỉ gồm số, cột số, cột không khớp, file rỗng giá trị hoặc thiếu tham chiếu. Kiểm dữ liệu đầu vào không đổi.
- A5: đề xuất cũ vẫn render/tóm tắt được; thêm đủ khóa mới không đổi quyết định/hợp đồng/phân loại; ký tự `|`, `<`, xuống dòng trong bằng chứng mới được escape; chỉ hiện năm dòng ánh xạ; tóm tắt không chứa giá trị lạ và chỉ thêm tối đa hai câu.
- A6: test tích hợp cả năm file thật, số kỳ vọng viết tay theo bảng đã sửa; kiểm phân loại và hash đầu vào trước/sau. Không có ca tích hợp bị bỏ qua ở worktree này.

**Ba lệnh §5 đã chạy tuần tự tại root worktree**, apps và scripts tách riêng. Chỉ thêm `--junitxml` để giữ bằng chứng kết quả:

```powershell
& D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider scripts/ingest/tests -q --tb=short -rs --junitxml=C:/Users/Win/AppData/Local/Temp/am_a_ingest.xml
& D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider scripts/pipeline/tests -q --tb=short -rs --junitxml=C:/Users/Win/AppData/Local/Temp/am_a_pipeline.xml
& D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider apps/retail_app/tests/test_nhap_du_lieu.py apps/retail_app/tests/test_nhap_theo_doi.py apps/retail_app/tests/test_nhap_tu_dong.py apps/retail_app/tests/test_extension_grants.py -q --tb=short -rs --junitxml=C:/Users/Win/AppData/Local/Temp/am_a_ui.xml
```

| Bộ test | Đạt | Trượt/lỗi | Bỏ qua | Thời gian | Exit |
|---|---:|---:|---:|---:|---:|
| scripts/ingest/tests | 216 | 0 | 0 | 196,81 giây | 0 |
| scripts/pipeline/tests | 99 | 0 | 2 | 21,44 giây | 0 |
| Bốn file test nhập UI/quyền ở §5 | 284 | 0 | 0 | 101,33 giây | 0 |

Hai skip pipeline: `test_contract.py:58` chưa có snapshot `5bd9a84aaf73` trong `warehouse/pipeline/snapshots`; `test_pipeline.py:361` chưa có bản dữ liệu do pipeline publish. Không dựng snapshot hoặc publish để bỏ hai skip này. Lượt thử trước đó trên riêng `test_auto_mapping.py` đạt 75 ca trong 117,91 giây; sau đó thêm năm ca biên và chạy hồi quy ingest cuối đủ 80 ca của file. Không cộng các lượt chạy lặp vào bảng.

**Đối chiếu số thật A6: đạt bảng đã sửa.** Các số dưới đây là số đo local bằng script/test, chưa có cell notebook mới; không dùng làm kết luận nghiệp vụ.

| File | Kết quả đo |
|---|---|
| tf.json | 1000 dòng; traffic_source: 998 dòng có hậu tố, 999 khác rỗng, 998 khớp sau bỏ. date không ép được 2; sessions không ép được 1, âm 1, vượt ngưỡng 1 (ngưỡng 509470); unique_visitors không ép được 1, âm 1. Không có web_traffic_ext. |
| epd.json | 1000 dòng; id_rong 2, id_trung_trong_file 1, khop_dung_1 995, khong_khop 5, anh_xa 995, id_trung_nguon 998. price không ép được 1, âm 1, vượt ngưỡng 1 (ngưỡng 409500.0). Không có products_ext. Khóa cũ danh_lai_khoa vẫn 993. |
| eprom.json | 1000 dòng; nguồn vẫn promotions; đề xuất promotions_ext ở silver, trạng thái de_xuat; id_chung_nguon 0, dong_con_tham_chieu 0, ban_ghi_giong_nguon 217. discount_value không ép được 2, âm 1. |
| orders_enriched.csv | 646945 dòng; nguồn orders; phân loại tu_dong. Không đề xuất nguồn mở rộng mới, anh_xa rỗng; gia_tri_la 0 mục/0 dòng, luat_sua_ung_vien 0 mục/0 dòng. |
| shipments_realistic.csv | 566067 dòng; nguồn shipments; can_nguoi với chua_co_hop_dong. Không đề xuất nguồn mở rộng mới, anh_xa rỗng; gia_tri_la 0 mục/0 dòng, luat_sua_ung_vien 0 mục/0 dòng. |

Hai CSV không có bằng chứng A3/A4 vì các cột lõi khớp tham chiếu không vi phạm kiểu/miền đang kiểm và không có hậu tố chuỗi đủ điều kiện. Các cột nhân viên/shipper thêm ngoài lõi không được A3/A4 xét, đúng giới hạn chỉ cột `khop`; không suy kết luận toàn bộ dữ liệu sạch từ hai danh sách rỗng. Đã đọc lại riêng hai file để ghi số đếm này, chỉ in số đếm và tên cột, không in thông tin cá nhân.

**Giới hạn và kiểm phạm vi:** `git diff --check` đạt; năm file cấm ở §2 không có diff; không có file staged. Không sửa dữ liệu, hợp đồng lõi, dbt, app hoặc cách đăng nhập; không kết nối cloud, không chạy các stage CLI của Phần B. Chưa chạy bộ đột biến độc lập hoặc đối chiếu snapshot/SQL biên dịch từng byte với fe1f65c của Claude ở §7; không nhận các phần đó là đã đạt. Không thay đổi luật ngoài phần phiếu đã chốt; không còn điểm chặn A2/A6. Đã ghi §9 và dừng ở Phần A, không stage, không commit, không push.

### Claude rà Phần A, ngày 2026-11-05

**Kết luận: code Phần A đạt, không phát hiện lỗi. Còn 8 khoảng trống test, GPT thêm rồi sang Phần B, không cần dừng chờ rà riêng.** Bản đã rà (12 ký tự đầu sha256): `auto_mapping.py` `c2b5a8791874`, `approval.py` `e4ac5883c3a6`.

Claude tự chạy, không dùng số của GPT:

| Kiểm | Kết quả |
|---|---|
| Bảng A6, tính bằng `json` và DuckDB, không import code repo | Khớp hết với `propose` trên `tf`, `epd`, `eprom`. Các cột số còn lại không có giá trị lạ, đúng với báo cáo |
| Ba lệnh §5 | Ingest 216 đạt; pipeline 99 đạt, 2 bỏ qua (thiếu snapshot và bản publish local); UI nhập 284 đạt |
| Phân loại `orders_enriched`, `shipments_realistic` | Như cũ theo test tích hợp A6, cả hai không có `nguon_mo_rong_de_xuat`, `anh_xa` rỗng |
| Thời gian `propose`† | `eprom` 0,9 giây; `epd` 0,1; `tf` 0,2; bản nhỏ `orders_enriched` 4,4, `shipments_realistic` 4,5; bản đầy đủ 31,1 và 23,9 |
| Không vào đường dữ liệu | Nhập `snapshot`, `extension_prepare`, `contract` không kéo theo `auto_mapping`, `approval`. Ngoài `approval.tom_tat_nghiep_vu`, không code nào đọc các khóa mới. So từng byte snapshot để tới Phần B |
| Ca biên ngoài test | Id `099` với dòng con `99`, dòng con có khoảng trắng, từ đuôi có dấu tiếng Việt, gọi `key_conflicts` hai lần, YAML khứ hồi, tên cột độc hại: đều đúng |
| Đột biến | 73 đột biến, chạy cả không và có dữ liệu thật: bắt 64, sống 9. Một đột biến tương đương (`[0-9]*`: giá trị đã trim nên không khớp được), **8 là khoảng trống test** |

**GPT thêm test viết tay cho 8 khoảng trống, không sửa code Phần A:**

1. `id_trung_khac_noi_dung` không được đếm dòng không trùng id: file có một dòng id mới phải ra 0.
2. A2: file id `099`, dòng con `99` với khóa `integer` thì không đề xuất (hiện đúng, chưa có test).
3. A2: bảng con có file nhưng thiếu cột thì trả `None` và ghi tên bảng vào `tham_chieu_thieu`.
4. A3: tham chiếu có cột nhưng toàn rỗng thì có `chua_kiem_mien: true`.
5. A4: từ đuôi có dấu tiếng Việt vẫn nhận.
6. A4: file tham chiếu thiếu cột thì bỏ qua, không lỗi.
7. và 8. `tom_tat_nghiep_vu` cộng đủ cả `so_am` lẫn `vuot_nguong`: viết số tay, ví dụ `tf.json` ra "Có 7 giá trị".

**Giới hạn đã biết, chưa sửa:** khi giá trị lớn nhất của tham chiếu là 0 hoặc âm, `vuot_nguong` báo cả giá trị bình thường. Chỉ là báo cáo, không ảnh hưởng quyết định, và không xảy ra trên 5 file. Tiêu đề `khong_khop` trên file đơn hàng và giao hàng gồm cả dòng khớp nhiều bản ghi (bản đầy đủ `shipments_realistic` là 44.700†, dù mọi id đều khớp), nên phải đọc cùng `id_trung_khac_noi_dung`.

**Claude tiền kiểm số Phần B†, đã sửa B2, B3:** 22 cột, 0 ô rỗng, 0 giá trị không ép được theo kiểu B2, 0 `order_id` trùng, 80 shipper, 17 thuộc tính phụ thuộc hàm đúng, trên cả file đầy đủ và file nhỏ; mọi `order_id` đều có trong `shipments.csv`. `join_date` sau `ship_date`: **91,73% trên file đầy đủ, 53,18% trên file nhỏ**, nên không viết test theo 92% trên file nhỏ.

### GPT — bổ sung test Phần A và triển khai Phần B, ngày 2026-11-05

**Đã bổ sung tám ca theo phần rà của Claude, triển khai Phần B và chạy lại đủ ba lệnh pytest §5. Dừng tại đây; không stage, commit, push. Lượt CLI nặng Phần B: chưa chạy, theo chỉ thị của PM.** Worktree `D:/retail-analytics-am`, nhánh `auto-mapping/myuyen`.

**Phần A chỉ thêm test, không sửa code.** Hash SHA256 giữ đúng bản Claude đã rà: `auto_mapping.py` bắt đầu `c2b5a8791874`, `approval.py` bắt đầu `e4ac5883c3a6`. Tám ca mới trong `scripts/ingest/tests/test_auto_mapping.py` kiểm: id mới không bị đếm thành id trùng khác nội dung; id `099` có con `99`; bảng con có file nhưng thiếu cột; tham chiếu số toàn rỗng; hậu tố tiếng Việt; tham chiếu chuỗi thiếu cột; tóm tắt cộng số âm và vượt ngưỡng (hai ca số kỳ vọng viết tay). Không áp dụng luật sửa hay đổi quyết định của Phần A.

**Các file tạo/sửa trong lượt này:**

- `scripts/ingest/extensions/shipments_realistic.yml` (mới): đúng thứ tự 22 cột, kiểu/hiển thị B2 đã sửa; 17 thuộc tính của thực thể shipper; mọi cột không được rỗng; PM duyệt ngày 2026-11-05. `scripts/ingest/tests/test_shipments_realistic.py` (mới, 7 ca) kiểm hợp đồng, dữ liệu thật và phân loại; `test_auto_mapping.py` thêm tám ca nêu trên.
- `retail_dbt/models/staging/stg_shipments_realistic.sql`, `retail_dbt/models/marts/dim_shipper.sql` (mới): staging giữ cả thuộc tính silver, dim Type 1 chỉ đưa các cột mart đã duyệt; khóa thay thế đánh theo shipper_id. `_sources.yml` thêm nguồn; `_extensions.yml` mô tả ảnh chụp hiện tại, giới hạn join_date và địa lý của shipper đúng B3.
- `retail_dbt/models/marts/fact_order.sql`: left join có điều kiện, thêm shipper_sk được rỗng. Khi tắt shipments, SQL sau render giữ nguyên từng ký tự so với `fe1f65c`, kiểm cả lõi và chỉ bật orders_enriched.
- `retail_dbt/tests/assert_shipments_realistic.sql`, `assert_shipper.sql`, `assert_order_shipper.sql` (mới): bảo toàn dòng, khóa, đủ 17 phụ thuộc hàm, số shipper, mỗi đơn tối đa một shipper, số đơn không đổi, đối chiếu shipper của từng đơn với nguồn trực tiếp. Phép so thuộc tính truy cập trực tiếp `dim_shipper.city/region/district`, nên không thể được che bởi cột cùng tên ở dim_geography.
- `retail_dbt/tests/assert_rpt_health.sql`: đếm tập phần mở rộng đang bật và đưa cả hai nguồn vào đối chiếu log. `scripts/pipeline/tests/test_shipments_dbt.py` (mới, 43 ca) chạy SQL model/test trên DuckDB nhỏ, kiểm ca hỏng từng thuộc tính và các lỗi khóa/join, cột trực tiếp trên dim, SQL tắt không đổi, biểu thức 14/15/16 nguồn cho hai nhánh target. Test không phụ thuộc giá trị cụ thể của shipper_sk: đổi đồng bộ khóa dim/fact vẫn đạt.
- `apps/retail_app/ui/nhap_runner.py`: `_start_locked` chốt `mo_rong_chay` từ active tại lúc bắt đầu; chép nguyên byte hợp đồng phần còn lại từ extension_dir của active, giữ nguyên đường dẫn file, hợp đồng của yêu cầu thắng nếu trùng tên. `_stage` và chạy lại dùng bộ đã ghi. Thiếu context/hợp đồng/file thì dừng trước khi tạo worker, báo lỗi, không sửa registry. `lenh` kiểm từng tên, sắp thứ tự xác định, truyền nhiều `--extension`. `summary` đọc các phần đang bật, bổ sung dim_shipper và số đơn có shipper. Import YAML được trì hoãn tới lúc chuẩn bị local để giữ khả năng tải app web không có YAML/DuckDB.
- `apps/retail_app/ui/nhap_store.py`: cho phép `da_duyet → loi` và `da_cong_bo → loi` để biểu diễn lỗi chuẩn bị bộ active trước khi tạo worker; yêu cầu đang lỗi giữ trạng thái và cập nhật thông báo. Không thay cách đăng nhập. `views/duyet_du_lieu.py` cập nhật thông báo hai phần đã có model.
- `apps/retail_app/tests/test_nhap_du_lieu.py`, `test_nhap_tu_dong.py`, `test_extension_grants.py`: thêm 17 ca cho giữ bộ active, cùng tên, rollback, active đổi sau duyệt, chạy lại, lỗi thiếu đầu vào không đổi registry/không tạo worker, tên không hợp lệ, summary hai phần, worker subprocess nối tiếp và đếm 16 nguồn. Cập nhật kỳ vọng ma trận trạng thái cho lỗi chuẩn bị nêu trên. `test_databricks.py` đã đếm nguồn động theo các hợp đồng trong repo, không cần sửa; hai ca nguồn mới xác nhận nó chấp nhận shipments riêng và cả hai phần.
- Phiếu này: chỉ thêm báo cáo vào §9. Giữ nguyên sửa có sẵn ở `docs/tien_hoa_schema.md`.

**Kiểm B2 bằng dữ liệu thật, chỉ đọc nguồn, đầu ra trong tmp_path:**

| File | Dòng | Ô rỗng | Dòng cách ly qua extension_prepare | Shipper phân biệt trong phần nhận |
|---|---:|---:|---:|---:|
| student_data/shipments_realistic.csv | 566067 | 0 | 0 | 80 |
| student_data/demo_2022/shipments_realistic.csv | 30211 | 0 | 0 | 80 |

Không sinh lại hay sửa file nhỏ. Không in giá trị cá nhân; chỉ số đếm và tên cột. Đây là bằng chứng kỹ thuật từ test local, chưa có cell notebook mới. Phân loại file nhỏ đủ cột: `tu_dong`; bỏ shipper_rating bắt buộc: `can_nguoi`, `thieu_cot`. Khi registry có cả hai hợp đồng, epd/tf/eprom vẫn `can_nguoi` do chưa có hợp đồng tương ứng. Bộ tích hợp A6 cũ tiếp tục đạt.

**B5 worker:** test tạo bản sao cô lập trong tmp_path, chạy hai worker subprocess và khóa OS thật, công bố vào Registry local thật của fixture: orders_enriched trước, shipments_realistic sau. Bản cuối có một nhân viên, hai shipper và bốn đơn của fixture; context ghi đủ hai phần. CLI trong phép thử là CLI giả, không forecast; stage build chạy SQL model thật qua render Jinja trên DuckDB nhỏ, stage validate chạy ba SQL test shipments. Đây không phải bằng chứng đã chạy CLI thật trên toàn dữ liệu hay nghiệm thu 200 nhân viên/80 shipper của §6.

**Ba lệnh §5 đã chạy tuần tự tại root worktree, apps và scripts tách riêng** (chỉ thêm JUnit XML để lưu kết quả):

```powershell
& D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider scripts/ingest/tests -q --tb=short -rs --junitxml=C:/Users/Win/AppData/Local/Temp/am_b_ingest.xml
& D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider scripts/pipeline/tests -q --tb=short -rs --junitxml=C:/Users/Win/AppData/Local/Temp/am_b_pipeline.xml
& D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider apps/retail_app/tests/test_nhap_du_lieu.py apps/retail_app/tests/test_nhap_theo_doi.py apps/retail_app/tests/test_nhap_tu_dong.py apps/retail_app/tests/test_extension_grants.py -q --tb=short -rs --junitxml=C:/Users/Win/AppData/Local/Temp/am_b_ui.xml
```

| Bộ test cuối | Đạt | Trượt/lỗi | Bỏ qua | Thời gian | Exit |
|---|---:|---:|---:|---:|---:|
| scripts/ingest/tests | 231 | 0 | 0 | 105,18 giây | 0 |
| scripts/pipeline/tests | 142 | 0 | 2 | 12,35 giây | 0 |
| Bốn file UI nhập/quyền §5 | 301 | 0 | 0 | 108,00 giây | 0 |

Hai skip không đổi: `test_contract.py:58` thiếu snapshot `5bd9a84aaf73`; `test_pipeline.py:361` chưa có bản publish local. Không dựng snapshot hay publish dữ liệu thật để bỏ skip. Không cộng các lần chạy thử vào bảng cuối. Lượt UI thử trước có 4 ca trượt: hai kỳ vọng trạng thái cũ, fixture worker thiếu file SQL test, import YAML quá sớm; đã xử lý và hồi quy cuối đạt. Lượt thử B2 ban đầu lỗi thứ tự bind tham số COPY và fixture phân loại chưa gọi registry; đã sửa test, không nới kiểu hợp đồng.

**Biên dịch dbt DuckDB:** đã chạy `dbt.exe compile --project-dir retail_dbt --profiles-dir retail_dbt --target duckdb --no-partial-parse --select stg_shipments_realistic dim_shipper fact_order assert_shipments_realistic assert_shipper assert_order_shipper`, truyền vars bật cả hai phần và snapshot_path giả, dùng DB/target/log trong `C:/Users/Win/AppData/Local/Temp/am_b_compile_wrps1emv`. `target/run_results.json` ghi **25/25 node success** (gồm test được dbt chọn gián tiếp); không build. Script bọc bị exit 1 khi in log tiếng Việt qua cp1252 sau khi dbt đã ghi đủ artifact; đã đọc lại `output.txt` và run_results để xác nhận, không nhận exit 1 của script bọc là exit 0. SQL biên dịch nằm dưới `target/compiled/retail_dbt/` của thư mục đó.

**Phần chưa chạy và khác biệt cần người rà biết:**

- Bốn stage CLI thật `prepare/forecast/build/validate` của am-b: **chưa chạy**, PM chạy theo yêu cầu mới nhất. Nghiệm thu trình duyệt §6 và đối soát toàn bộ snapshot/SQL/marts từng byte của Claude §7: chưa chạy.
- Khối health dành cho PostgreSQL/Databricks: **chưa chạy thật**. Tám ca chỉ render nhánh target và chạy biểu thức đếm bằng DuckDB fixture; không phải chứng nhận backend đó đạt.
- Worker B5 là worker thật với CLI fixture như mô tả; không gọi CLI thật, không train dự báo. Các kiểm B2 gọi riêng extension_prepare thật trên cả hai file, không thay thế lượt CLI đầy đủ.
- Bổ sung hai chuyển trạng thái lỗi trước khởi động để thực hiện B4; không thêm đường nhập hay đổi quyết định nghiệp vụ. `lenh` vẫn nhận tên đơn để tương thích lời gọi cũ, đồng thời nhận danh sách. Context active có phần khác nhưng thiếu extension_dir thì dừng báo lỗi, không tự lấy hợp đồng mới nhất.
- Không sửa code Phần A hoặc năm file cấm ở §2; diff các file cấm rỗng. `git diff --check` đạt; không có file staged. Không đọc secrets, không kết nối cloud, không chạy Airflow/Docker, không sửa dữ liệu. Không commit/push. Đã ghi §9 và dừng để Claude/PM rà.

### Claude rà Phần B, ngày 2026-11-05

**Kết luận: chưa đạt. Có một lỗi làm mất dữ liệu ở B4, gốc là câu Claude viết sai trong phiếu; GPT làm đúng phiếu.** Phần còn lại đọc không thấy lỗi, nhưng còn khoảng trống test và chưa có lượt chạy thật.

**Lỗi, đã tái hiện trên bản sao (`C:\Users\Win\am_kiem\tai_hien_b4.py`, 3 ca đều trượt).** Phiếu ghi "mọi lần chạy tiếp theo dùng đúng giá trị đã ghi", nên `_extensions_for_run` dùng lại `mo_rong_chay` cũ ở lượt mới:

| Tình huống | Kết quả hiện tại | Hậu quả |
|---|---|---|
| `orders_enriched` đã công bố, sau đó `shipments_realistic` công bố; bấm "Chạy lại để kiểm" yêu cầu đầu | Lượt mới chỉ có `orders_enriched` | Công bố thì mất `dim_shipper` |
| Yêu cầu lỗi, trong lúc đó phần khác công bố; bấm "Chạy" lại | Lượt mới thiếu phần vừa công bố | Công bố thì mất phần đó |
| Yêu cầu lỗi, trong lúc đó rollback bỏ một phần; bấm "Chạy" lại | Lượt mới vẫn còn phần đã rollback | Công bố thì phần đó quay lại |

Cổng `expected_active` không chặn được vì mỗi lượt mới ghi lại giá trị này lúc `prepare`. Công bố lệch bản giữa hai lượt đang chờ (`da_kiem`) thì cổng đó có chặn, không cần sửa.

**B6. GPT sửa:**

1. Mỗi lượt mới (`lan_chay` tăng) tính lại bộ từ `active` lúc bắt đầu, kể cả đi từ `loi` và `da_cong_bo`. `mo_rong_chay` chỉ khóa cho các stage của đúng lượt đó.
2. Hợp đồng theo lượt: `chay/<run_id>/hop_dong/` gồm hợp đồng của yêu cầu (chép nguyên byte từ `hop_dong/`) và phần còn lại lấy từ `extension_dir` của `active`. `_stage` truyền đúng thư mục này. Không ghi thêm gì vào `hop_dong/`. Lý do: `extension_dir` trong context của bản đã công bố trỏ tới thư mục được truyền; dùng chung một thư mục thì lượt sau ghi đè, rollback rồi gộp sẽ lấy nhầm hợp đồng.
3. Dừng và báo trong §9 nếu việc đổi thư mục làm `snapshot_id` đổi, hoặc có code khác đọc `chay/` mà bị ảnh hưởng.

**Test cho B6:** ba ca ở bảng trên; thư mục hợp đồng của lượt cũ giữ nguyên từng byte sau lượt mới; "Chạy lại để kiểm" trên yêu cầu đang là một phần của `active` ra đúng tập và đúng byte hợp đồng của `active`; sửa `test_b4_start_unions_active_and_freezes_for_retry` theo quy tắc mới.

**Đột biến, chạy trên bản sao, không sửa worktree:**

| Nhóm | Số đột biến | Bắt | Sống |
|---|---:|---:|---:|
| 9 ca sống của Phần A | 9 | 8 | 1, đột biến tương đương đã biết. Tám khoảng trống Phần A đã đóng |
| B4 `nhap_runner`, `nhap_store` | 25 | 17 | 8 |
| B3 SQL | 38 | 21 | 17 |
| B2 hợp đồng | 13 | 10 | 3 (lượt không dữ liệu; lượt có dữ liệu chưa xong, xem dưới) |

**GPT thêm test viết tay cho các đột biến sống, không sửa dbt, không sửa hợp đồng:**

- B4: context `active` sai `release_id`; sai `target`; `extensions` không phải danh sách; `active` không có phần mở rộng và không có `extension_dir` thì vẫn chạy được với phần của yêu cầu; chạy từ `loi` gặp lỗi chuẩn bị thì `thong_bao` được cập nhật. Hai đột biến `bo kiem own`, `chep lai khi frozen` sẽ mất theo B6; `bo kiem extension_dir` là tương đương vì `Path(None)` cũng ra cùng lỗi.
- B3: ca hỏng cho `so_dong`, `don_mo_coi`, `so_thu_tu` và dòng thiếu ở một phía của `thuoc_tinh`; sửa **giá trị** từng cột trong 13 thuộc tính của `dim_shipper` thì `assert_shipper` phải ra `thuoc_tinh` (hiện 10 cột không có ca nào; `city`, `region`, `district` chỉ bị bắt do xóa cột, chưa có ca sửa giá trị); kiểm kiểu `shipper_rating`, `delivery_success_rate` là double, `join_date` là date, hai cột số nguyên là integer; `shipper_sk` tăng theo thứ tự `shipper_id`.
- B2: kiểm `nguong_cach_ly == 0.01`, `file == 'student_data/shipments_realistic.csv'` và đủ 17 thuộc tính, không phụ thuộc có dữ liệu hay không.
- `test_b3_disabled_fact_sql_unchanged` gọi `git show fe1f65c`: chuyển sang `pytest.skip` khi không đọc được commit, để bản sao không có lịch sử không trượt oan.

**Giới hạn của lượt rà này:**

- Lượt đột biến bị hệ thống dừng vì máy thiếu RAM, ở bước B2 có dữ liệu. Claude không tự chạy lại. Các số ở bảng là phần đã xong.
- Nhóm B4 chạy trên bản sao, bỏ 8 test trang vì chúng trượt trên bản sao ở ổ C dù đạt trên worktree. Các test này không kiểm logic B4.
- **Chưa làm, để sau B6, PM chạy ngoài Claude Code:** ba lệnh §5 do Claude kiểm lại, so SQL biên dịch với `fe1f65c`, bốn stage CLI thật `am-b`, so `snapshot_id` `5bd9a84aaf73` và `47e7cbe765d9`, đọc mart độc lập, nghiệm thu §6.
- Khối đếm nguồn của `assert_rpt_health` chỉ biên dịch trên Postgres và Databricks, nên phần này vẫn chưa chạy thật. Trước khi lên Databricks phải kiểm thêm, cùng cú pháp `having` không có `group by` trong `assert_shipments_realistic.sql`.

**Việc của GPT:** làm B6 và các test trên, chạy lại ba lệnh §5, ghi báo cáo vào §9, dừng. Không chạy CLI nặng, không commit, không push. Hash `auto_mapping.py`, `approval.py` phải giữ nguyên.

### GPT báo cáo B6 sau «Claude rà Phần B» — 2026-11-05

**Đã làm B6 và các test được giao; chạy lại đủ ba lệnh §5.** Worktree `D:/retail-analytics-am`, nhánh `auto-mapping/myuyen`. Không stage, commit, push. CLI nặng Phần B: **chưa chạy**, để PM chạy.

**Thay đổi lượt này:**

- `apps/retail_app/ui/nhap_runner.py`: mỗi lượt mới đọc lại tập extension từ context của `active`, hợp với extension của yêu cầu; không dùng `mo_rong_chay` cũ khi chạy lại từ `loi` hoặc `da_cong_bo`. Các stage của cùng lượt dùng bộ đã ghi.
- Hợp đồng được đọc/kiểm trước khi khởi động; sau khi ghi số lượt mới, chép vào `chay/<run_id>/hop_dong/` bằng tạo mới, không ghi đè. Hợp đồng riêng của yêu cầu lấy nguyên byte từ `hop_dong/`, hợp đồng khác lấy nguyên byte từ `active.extension_dir`. `_stage` truyền thư mục của đúng lượt. Không ghi thêm vào `hop_dong/`; không thay hợp đồng của lượt cũ hoặc của active. Lỗi chép khiến lượt lỗi, lần thử sau dùng run_id mới.
- `test_nhap_du_lieu.py`: sửa ca khóa bộ cũ thành tính lại khi retry; kiểm cả ba đường tay/tự động/nạp bù sau rollback. Thêm ca chạy lại từ lỗi và đã công bố khi active có phần mới, kiểm đúng tập và byte hợp đồng, thư mục yêu cầu/active/lượt trước bất biến, active đổi giữa các stage không đổi bộ của lượt đang chạy. Thêm context sai release_id/target/kiểu extensions, active lõi thiếu extension_dir, cập nhật thong_bao khi đang lỗi.
- `test_nhap_tu_dong.py`: bổ sung hợp đồng trỏ tới file fixture đã tạo cho các yêu cầu giả và driver worker; sửa mock duyệt lại nạp bù để trỏ đúng file yêu cầu. Không thay điều kiện nghiệm thu UI.
- `scripts/pipeline/tests/test_shipments_dbt.py`: thêm ca hỏng so_dong/don_mo_coi/so_thu_tu, thiếu dòng ở từng phía đối soát thuoc_tinh; đổi giá trị lần lượt cả 13 thuộc tính mart; kiểm kiểu ở cả staging và dimension; kiểm shipper_sk theo shipper_id. Test so SQL với `fe1f65c` bỏ qua có lý do nếu không đọc được commit.
- `scripts/ingest/tests/test_shipments_realistic.py`: kiểm độc lập dữ liệu cho ngưỡng 0.01, đường dẫn file và đúng tập 17 thuộc tính, không chỉ đếm số thuộc tính.
- `scripts/pipeline/tests/test_nhap_extension_dir.py`: fixture prepare nhỏ xác nhận chỉ đổi thư mục hợp đồng sang `chay/<run_id>/hop_dong/` thì snapshot_id không đổi và context ghi đường dẫn mới. Không chạy forecast/build/validate trên dữ liệu đầy đủ.

**Điểm chặn B6.3:** không phát hiện trên phạm vi đã kiểm. Test snapshot_id trên fixture đạt. Các chỗ đọc `chay/` trong runner/store/trang Duyệt dùng đường dẫn log và context cụ thể; các đường dẫn đó giữ nguyên, bộ test UI đạt. Chưa đối chiếu snapshot thật `5bd9a84aaf73` / `47e7cbe765d9`; phần đó vẫn thuộc lượt CLI nặng của PM.

**Kiểm thử cuối, chạy tuần tự tại root worktree:**

```powershell
& D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider scripts/ingest/tests -q --tb=short -rs --junitxml=C:/Users/Win/AppData/Local/Temp/am_b6_ingest.xml
& D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider scripts/pipeline/tests -q --tb=short -rs --junitxml=C:/Users/Win/AppData/Local/Temp/am_b6_pipeline.xml
& D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider apps/retail_app/tests/test_nhap_du_lieu.py apps/retail_app/tests/test_nhap_theo_doi.py apps/retail_app/tests/test_nhap_tu_dong.py apps/retail_app/tests/test_extension_grants.py -q --tb=short -rs --junitxml=C:/Users/Win/AppData/Local/Temp/am_b6_ui.xml
```

| Bộ test | Đạt | Trượt/lỗi | Bỏ qua | Thời gian |
|---|---:|---:|---:|---:|
| scripts/ingest/tests | 231 | 0 | 0 | 120.30 s |
| scripts/pipeline/tests | 167 | 0 | 2 | 15.46 s |
| Bốn file UI ở §5 | 307 | 0 | 0 | 132.46 s |

Hai skip pipeline: chưa có snapshot `5bd9a84aaf73` ở `warehouse/pipeline/snapshots`; chưa có bản dữ liệu do pipeline publish. Không tính các lượt chạy lại vào số đạt trên. Lượt tập trung trước đó có lỗi quyền thư mục tmp trong sandbox; chạy lại ngoài sandbox đạt. Một test UI nạp bù trượt do mock hợp đồng trỏ file không tồn tại; đã sửa mock, kiểm lại ca riêng và cả bộ UI đều đạt.

**Phạm vi giữ nguyên và khác phiếu:** không có thay đổi ngoài yêu cầu B6/test/báo cáo. Đối chiếu SHA-256 trước/sau của 119 file dbt, hợp đồng và code được bảo vệ: không file nào đổi. `auto_mapping.py` vẫn `c2b5a87918744aadc35a93b95479f543aab4fb9da28ebd69110a3e1d59ebbd29`; `approval.py` vẫn `e4ac5883c3a647af2ef7169b85253650857b35b79a8236fb73a60c500b69ab76`. Giữ các thay đổi Phần A/B có sẵn, không sửa chúng trong lượt này. Quy tắc thư mục theo B6 §9 thay câu cũ dùng chung thư mục ở B4. Không chạy lại chiến dịch đột biến; thêm test viết tay theo danh sách. Hai đột biến gắn với nhánh frozen cũ không còn áp dụng; `bo kiem extension_dir` vẫn tương đương trong ca thiếu thư mục vì `Path(None)` cũng bị chuyển thành cùng lỗi chuẩn bị. Không kết nối cloud, không chạy CLI nặng hoặc nghiệm thu §6. **Dừng tại đây.**

### Claude rà B6, ngày 2026-11-05

**Kết luận: code B6 đạt, không cần GPT làm thêm. Chờ lượt kiểm thật do PM chạy (`C:\Users\Win\am_kiem\chay_b.py`).** Bản đã rà chốt hash ở `C:\Users\Win\am_kiem\ban_ra_b6.json`, 22 file; `auto_mapping.py`, `approval.py` giữ đúng hash.

| Kiểm | Kết quả |
|---|---|
| 3 ca tái hiện lỗi mất dữ liệu | Đều đúng: chạy lại từ đã công bố và từ lỗi có đủ hai phần; sau rollback chỉ còn phần của bản rollback |
| Đột biến `nhap_runner`, `nhap_store` | 23 đột biến: bắt 22, sống 1 |
| Đột biến SQL còn sống từ lượt trước | 20 đột biến: bắt 18, sống 2 |
| Đột biến hợp đồng còn sống | 3 đột biến: bắt cả 3 |
| SQL biên dịch, không phần mở rộng, so `fe1f65c` | 215 file, trùng hết sau khi che giờ build `built_at_utc` |

**Ba đột biến sống, không giao GPT thêm:**

- `B6 bo kiem list`: chuỗi hay số vẫn bị chặn ở bước sau; riêng từ điển sẽ được lấy khóa làm tên. `context.json` do CLI ghi luôn là danh sách nên ca này không xảy ra trên đường thật; phép kiểm chỉ là phòng thủ.
- `B3 test full outer`: dòng thiếu một phía vẫn bị bắt bởi các phép so `is distinct from`. Tương đương về hành vi.
- `B3 dim sk theo ten`: test yếu thật vì trong fixture thứ tự tên trùng thứ tự id. Chỉ ảnh hưởng cách đánh số, không đổi số liệu. `chay_b.py` kiểm trực tiếp `shipper_sk` theo `shipper_id` trên kho thật.

**Giới hạn:** nhóm `nhap_runner` chỉ chạy `test_nhap_du_lieu.py` trên bản sao, bỏ 8 test trang. Ba lệnh §5, so SQL khi bật `orders_enriched`, `snapshot_id` thật, bốn stage CLI và đọc mart chưa chạy, nằm trong `chay_b.py`. So số mart lúc chỉ bật `orders_enriched` với `fe1f65c` không làm trực tiếp vì tốn thêm một lượt build: suy ra từ cùng `snapshot_id` và cùng SQL biên dịch.

### Lượt kiểm thật do PM chạy, ngày 2026-11-05

**Kết luận: đạt, 0 mục sai.** PM chạy `chay_b.py` ngoài Claude Code, root `warehouse/pipeline/am-b-1105-1744`, không publish; Claude đọc `ket_qua_b.log` và `run_results.json`.

| Kiểm | Kết quả |
|---|---|
| Code đúng bản đã rà | 22 file giữ nguyên hash |
| Ba lệnh §5 | Ingest 231 đạt; pipeline 167 đạt, 2 bỏ qua (thiếu snapshot và bản publish trong `warehouse/pipeline`, không phải hồi quy); UI 307 đạt |
| SQL biên dịch so `fe1f65c` | Không phần mở rộng 215 file, chỉ `orders_enriched` 221 file: trùng hết, đã che giờ build |
| `snapshot_id` | 14 nguồn `5bd9a84aaf73`, `orders_enriched` `47e7cbe765d9`: giữ nguyên. Hai phần mở rộng: `086effe8607b` |
| Cách ly trên file đầy đủ | `orders_enriched` 0, `shipments_realistic` 0 |
| Bốn stage CLI thật† | prepare 24 giây, forecast 178 giây, build 23 giây, validate 2 giây, đều exit 0 |
| dbt | 236 node: 169 test đạt, 67 model, seed, hook thành công, gồm `assert_shipments_realistic`, `assert_shipper`, `assert_order_shipper`, `assert_rpt_deck_numbers`, `assert_rpt_total` |
| Đọc kho độc lập | `dim_shipper` 80 dòng, đúng cột hợp đồng, `shipper_sk` tăng theo `shipper_id`; `dim_sales_employee` 200 dòng; không cột silver nào ở mart, reporting |
| Đơn và shipper | `fact_order` 646.945 dòng bằng số đơn nguồn; 566.067 đơn có shipper; so với CSV lệch 0, thiếu 0; 17 thuộc tính phụ thuộc hàm đúng |
| G, COGS | 3.833 ngày khớp `sales.csv`, lệch 0 |

**Vẫn chưa chứng minh:** khối đếm nguồn của `assert_rpt_health` trên Postgres và Databricks (DuckDB không chạy khối này). Số mart lúc chỉ bật `orders_enriched` chưa so trực tiếp, suy ra từ cùng `snapshot_id` và cùng SQL. Còn nghiệm thu §6 trên app.

### Nghiệm thu trên app do PM chạy, ngày 2026-11-05

**Kết luận: đạt cả 8 bước theo §6.** PM thao tác trên app local bằng ba tài khoản theo vai trò: `chushop` (Quản lý), `minh` (Data engineer), `uyen` (Admin). Claude đọc kho `warehouse/pipeline/ui-nhap` bằng script ngoài repo. Cả 3 lượt chạy thật cùng `code_version` `1eb465cbba32`; 22 file code giữ nguyên hash so với bản đã rà. Chữ trên màn hình ở bước 1–7 do PM xác nhận, chưa có ảnh; bước 8 có ảnh và nhật ký truy cập.

| Bước | Vai trò | Kết quả |
|---|---|---|
| 1. Gửi `orders_enriched.csv` | Quản lý | Hệ thống tự duyệt, tự công bố `a52ba6b5`: 200 nhân viên, 36.004 đơn có nhân viên, cách ly 0 |
| 2. Gửi `shipments_realistic.csv` | Quản lý | Tự công bố `033dce10`: 200 nhân viên, 80 shipper, 30.211 đơn có shipper, cách ly 0 và 0 |
| 3–5. Gửi `tf.json`, `epd.json`, `eprom.json` | Quản lý | Cả 3 ở `cho_duyet`, không có lượt chạy; kho không đổi |
| 6. Chạy lại khi không có gì mới | Data engineer | `bo_qua`, thông báo "Không có gì mới, bỏ qua", không đăng ký bản mới |
| 7. Rollback về bản sau bước 1 | Admin | `033dce10` → `a52ba6b5`: 200 nhân viên, không còn shipper. PM xác nhận Data engineer không thấy mục Rollback |
| 8a. Chạy lại sau rollback | Data engineer | `67a380a8` dừng ở `da_kiem`, có đủ 200 và 80, không có nút Công bố. Kho không đổi suốt 27 phút giữa `validate` và `publish` |
| 8b. Công bố | Admin | `67a380a8` thành bản đang xem: 200 nhân viên, 36.004 đơn; 80 shipper, 30.211 đơn |

Doanh thu G và COGS ở `a52ba6b5`, `033dce10`, `67a380a8` đều khớp `sales.csv`, lệch 0 trên 3.833 ngày. Nhật ký truy cập ghi đúng người: `minh` với `nhap_chay`, `uyen` với `nhap_rollback` và `nhap_cong_bo`.

**Thời gian trên app:** mỗi lượt 7 phút 40 đến 7 phút 57; riêng forecast 6 phút 31 đến 6 phút 42, so với 178 giây ở lượt `chay_b.py`. Chưa rõ vì sao chậm hơn.

**Phát hiện, chưa sửa:** sau rollback, yêu cầu đã bị thay thế vẫn ở "Đã cập nhật" và bảng JSON vẫn hiện số của lượt cũ (80 shipper), trong khi bản đang xem không có shipper. Nguyên nhân theo code: `nhap_runner.summary` đọc `published.context.json` của yêu cầu, không so với `active`, và rollback không đổi trạng thái yêu cầu. Số trong kho không sai, chỉ phần hiển thị dễ gây hiểu nhầm. Phần này đọc từ code, chưa có ảnh chụp đúng lúc đó.

**Giới hạn:** chạy trên file `demo_2022` đã thu nhỏ, chỉ dùng local. Năm trang PS đọc kho báo cáo riêng nên không đổi số, đúng thiết kế hiện tại; chưa chạy trên Databricks.

## 10. PM đã chốt trước khi giao

1. **Lượt nhập giữ cả bộ đang hiệu lực (B4).** Đã duyệt ở mức nguyên tắc tại thiết kế §8.4 mục 2 cho production; phiếu áp lại cho local. Không có quy tắc này thì công bố shipments làm mất chiều nhân viên.
2. **`shipper_gender`, `shipper_age` để `silver` (PM chốt 2026-11-05).** Đổi so với câu chữ cũ của `tien_hoa_schema.md` §10 câu 3, đã ghi bổ sung ở đó. Cổng `validate_extension_visibility` sẽ chặn nếu hai cột này xuất hiện ở mart hoặc reporting. **`shipper_name`, `shipper_phone` vẫn lên mart** theo quyết định PM ngày 2026-10-28.
