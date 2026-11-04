# Giao việc D1: sinh bộ file 2023 cùng dạng `student_data`

Soạn ngày 2026-11-02, cập nhật 2026-11-04 theo quyết định "B tạm thời" của PM. PM chốt phạm vi 2026-11-02. GPT code §3–§5; Claude rà và tự chạy kiểm độc lập trước khi commit, chưa đạt thì ghi §9 để GPT sửa.
Thiết kế gốc: `docs/thiet_ke_nap_ky_moi.md` §0, §4.1 (bản mới nhất ở nhánh `docs/thiet-ke-b-tam-thoi`, worktree `D:/retail-analytics-nhap`). Phiếu này đã chép đủ luật, không cần đọc thêm để code.

Đọc trước: `AGENTS.md`, `CLAUDE.md` §1, §5, `docs/agent_workflows.md`; `scripts/ingest/source_contract.py`, `scripts/ingest/auto_mapping.py` (hàm `propose`), `scripts/ingest/extensions/orders_enriched.yml`.

## 0. Vì sao cần

- Dữ liệu thật dừng ở 2022-12-31. Cả bộ `student_data` thầy gửi cũng vậy: `orders_enriched` tới 2022-12-31, `shipments_realistic` tới 2022-12-29.
- PM cần một bộ cùng dạng bộ của thầy nhưng là năm 2023, để thử: nạp năm mới kèm cột mới và JSON thì auto mapping và dashboard xử lý ra sao.
- **Đây là dữ liệu tổng hợp, chỉ để demo.** Không dùng cho kết luận nào trong báo cáo, không bao giờ vào `data/` gốc hay git. Lát sau mới nạp vào kho; D1 không nạp vào đâu.

## 1. Phạm vi

**Làm:** một script sinh bộ file và test. **Không làm** (lát sau):

- không sửa `prepare`, `snapshot`, `auto_mapping`, hợp đồng trong `scripts/ingest/extensions/`, dbt, app;
- không nạp bộ này vào kho nào;
- không tạo hợp đồng cho `tf.json`, không thêm luật miền.

## 2. Môi trường và ràng buộc

- Worktree `D:/retail-analytics-nap`, nhánh `nap-ky/myuyen` (Claude đã đưa lên `origin/main` `fe1f65c`, có T1). Python `D:/retail-analytics/.venv/Scripts/python.exe`. **Không commit, không push.**
- Laptop PM ít RAM: dùng DuckDB với `threads=2`, `memory_limit='2GB'`, không nạp cả bảng vào pandas. Mọi bước ghi phải có thứ tự rõ ràng (`ORDER BY` hoặc ghi qua `csv` của Python) để nhiều luồng không làm lệch byte.
- **Chỉ tạo/sửa 3 chỗ:** `scripts/demo/sinh_dot_2023.py`, `scripts/demo/tests/test_sinh_dot_2023.py`, thêm một dòng `data_demo/` vào `.gitignore`; ngoài ra chỉ điền §9 của phiếu này.
  `scripts/demo` nằm ngoài băm `code_version` (`scripts/pipeline/cli.py:30–40`), nên không phải dựng lại image. Sửa file khác là sai phạm vi.
- Không kết nối Databricks, Neon hay Airflow.
- Dữ liệu đầu vào **chỉ đọc**. Worktree không có `data/`, nên chạy thật bằng tham số:
  `--student D:/retail-analytics-nhap/data/student_data --goc D:/retail-analytics/data`. Test dùng dữ liệu nhỏ tự dựng, không đọc `data/` thật.
- Không in tên, số điện thoại nhân viên hay shipper ra log.

## 3. Dòng lệnh

```text
python scripts/demo/sinh_dot_2023.py --student <thu muc> --goc <thu muc> [--ra data_demo/dot_2023] [--kiem data_demo/dot_2023_kiem] [--seed 2023]
```

- `--ra` chứa đúng các file "stakeholder gửi". `--kiem` chứa đồ đối chứng, không gửi lên hệ thống.
- **Từ chối chạy** (mã thoát khác 0, không ghi gì) khi `--ra` hoặc `--kiem` nằm trong một thư mục tên `data` hoặc `warehouse`, hoặc đã có file.
- Ghi vào thư mục tạm rồi đổi tên khi xong và kiểm đạt, để không bao giờ để lại bộ dở.
- Cùng seed, cùng đầu vào phải ra **đúng từng byte**, cả `--ra` lẫn `--kiem`. Vì vậy `manifest.json` không có thời gian chạy và không có đường dẫn tuyệt đối; đầu vào nhận diện bằng tên file và sha256.

## 4. Luật sinh

**Đọc và ghi mọi cột dạng chuỗi nguyên văn, không ép kiểu số.** Chỉ đổi đúng các cột nêu dưới đây. Giữ thứ tự cột, BOM và kiểu xuống dòng của từng file như bản của thầy (`orders_enriched.csv` có BOM).

### 4.1 Ánh xạ ngày

Duyệt 365 ngày của 2023 theo thứ tự, dùng `random.Random(seed)`, chọn năm mẫu cho từng ngày, cùng tháng và cùng ngày:

- 30/01–01/03 và 30/07–02/09: chỉ chọn trong **2019, 2021**. Đây là cửa sổ của Rural Special và Urban Blowout, hai khuyến mãi chỉ có ở năm lẻ†, và 2023 là năm lẻ. († khảo sát `promotions.csv` ngày 2026-11-02, chưa có cell; riêng Urban Blowout có ở CLAUDE.md §5 điểm 6.)
- Ngày còn lại: chọn trong 2019–2022.

`lech` của một ngày = ngày 2023 − ngày mẫu, tính bằng số ngày. Ghi `anh_xa_ngay.csv` (`ngay_2023, ngay_mau, lech`).

### 4.2 Đơn và bảng con

Lấy toàn bộ đơn của các ngày mẫu trong `orders_enriched.csv`. Thứ tự dòng: theo ngày 2023, trong cùng ngày giữ thứ tự file gốc. Trong mọi bảng con, giữ thứ tự tương đối của dòng cùng đơn, vì staging dựng số dòng theo thứ tự nguồn.

| File | Đổi gì |
|---|---|
| `orders_enriched.csv` | `order_id` mới nối tiếp max gốc theo thứ tự dòng; `order_date` + `lech`; thêm cột cuối `loyalty_tier` |
| `order_items.csv` | `order_id` mới; `promo_id`, `promo_id_2` theo §4.3; ô rỗng giữ rỗng |
| `payments.csv` | `order_id` mới |
| `shipments_realistic.csv` | `order_id` mới; `ship_date`, `delivery_date` + `lech`. `join_date` **không đổi** vì là ảnh chụp hiện tại của shipper |
| `returns.csv` | `return_id` mới nối tiếp max gốc, giữ dạng `RET-000001`; `order_id` mới; `return_date` + `lech` |
| `reviews.csv` | `review_id` mới nối tiếp max gốc, giữ dạng `REV-0000001`; `order_id` mới; `review_date` + `lech` |

- **`loyalty_tier`:** cột hoàn toàn mới, ngoài hợp đồng đã duyệt. Giá trị `Bronze`, `Silver`, `Gold`, `Platinum`, lấy từ băm ổn định của `customer_id` (sha256, không dùng `hash()` của Python), nên cùng khách luôn cùng hạng và không có ô rỗng.
- Thuộc tính nhân viên chép nguyên văn. Đổi `years_experience` sẽ bị R6 cách ly ở lát sau.
- Ngày rỗng giữ rỗng. Ngày lệch ra 2024 là đúng.

### 4.3 Khuyến mãi

- Mỗi cặp (`promo_id` gốc, `lech`) có ít nhất một dòng hàng đã chọn dùng (qua `promo_id` hoặc `promo_id_2`) thành **một dòng** trong `promotions.csv`. Cặp không dòng hàng nào dùng thì không sinh.
- `promo_id` mới `PROMO-0051` trở đi, theo thứ tự (`start_date` mới, `promo_id` gốc). `start_date`, `end_date` + `lech`.
- `promo_name` = tên gốc bỏ năm cuối + ` 2023 mau <năm trong tên gốc>`, ví dụ `Urban Blowout 2023 mau 2021`. **Phải giữ tiền tố** `Urban Blowout` vì `assert_urban_blowout_matches_promotions.sql` tìm theo `like 'Urban Blowout%'`.
- `start_date` có thể rơi vào 2022 (đợt cuối năm mượn cho tháng 1). Đúng thiết kế, không sửa. Các cột khác chép nguyên văn.

### 4.4 Tồn kho và lượt truy cập

- `inventory.csv`: mỗi tháng 2023 chọn một năm mẫu (tháng 2, tháng 8 chỉ 2019, 2021; dùng cùng `Random` sau khi xong §4.1). Lấy các dòng có `snapshot_date` trong tháng đó; `snapshot_date` thành ngày cuối tháng 2023; `year` = `2023`, `month` = tháng giữ nguyên dạng nguồn.
- `web_traffic.csv`: dòng của ngày mẫu, `date` = ngày 2023. Đúng 365 dòng.

### 4.5 File JSON và file không đổi

- `tf.json`: mảng 365 đối tượng cùng 7 khóa, lấy từ `web_traffic.csv` 2023 vừa sinh. Số giữ kiểu số JSON. `traffic_source` khác rỗng thêm hậu tố ` Variant nnnn` (`nnnn` theo thứ tự dòng). **Cấy đúng 3 giá trị**, chọn bằng `Random`, ba ngày khác nhau: `date = "not_a_date"`, `sessions = "N/A"`, `sessions = -100`.
  3/365 = 0,82%, dưới ngưỡng 1%. Ghi vào `gia_tri_cay` của manifest.
- `eprom.json`: giữ 1.000 bản ghi, id, thứ tự và mọi giá trị lạ (`'twenty percent'`, `'30%%'`, id dính khoảng trắng). `start_date`, `end_date` cộng cùng số năm sao cho `start_date` rơi vào 2023. Ngày không đọc được hoặc `start_date` có năm ≥ 2023 thì giữ nguyên. 29/02 về 28/02.
- `epd.json`, `customers.csv`, `products.csv`, `geography.csv`: chép **nguyên byte**.
- **Không sinh** `orders.csv`, `shipments.csv`, `sales.csv`, `sample_submission.csv`, đúng như zip của thầy. Không dùng các file `data/orders.csv`, `data/shipments.csv` làm đầu vào.

### 4.6 Thư mục `--kiem`

- `anh_xa_ngay.csv` (§4.1).
- `sales_doi_chung.csv` (`Date, Revenue, COGS`): tính từ **bộ vừa sinh** theo CLAUDE.md §5 điểm 1: `Revenue(d) = Σ quantity × unit_price`, `COGS(d) = Σ quantity × cogs` của `products`, mọi trạng thái đơn, không trừ `discount_amount`, làm tròn 2 chữ số như `sales.csv`. Tính bằng DECIMAL, không dùng float.
- `manifest.json`: `co_du_lieu_tong_hop: true`, `seed`, sha256 từng file đầu vào, từng file đầu ra (số dòng, sha256, khoảng ngày), `gia_tri_cay`, kết quả §5.

## 5. Kiểm trong script và trong test

Script tự chạy các kiểm K1–K8 trên bộ vừa sinh, sai là dừng và không đổi tên thư mục tạm.

| Mã | Kiểm |
|---|---|
| K1 | Header từng file đúng bản của thầy, kể cả thứ tự; riêng `orders_enriched` thêm đúng một cột cuối `loyalty_tier` |
| K2 | `order_id`, `return_id`, `review_id`, `promo_id` mới không trùng trong bộ và không trùng bản gốc |
| K3 | Mọi `order_date`, `ship_date`, `delivery_date`, `return_date`, `review_date`, `snapshot_date` và `date` của `web_traffic` > 2022-12-31. **Không** áp cho `promotions.start_date` |
| K4 | Khóa ngoại: mọi `order_id` con có trong `orders_enriched`; `product_id`, `customer_id`, `zip` có trong master; `promo_id`, `promo_id_2` có trong `promotions.csv` |
| K5 | **Đối chứng độc lập:** mỗi ngày 2023, `sales_doi_chung` = dòng của ngày mẫu trong `<goc>/sales.csv`, khớp đúng 2 chữ số. `sales.csv` không được dùng để sinh dữ liệu |
| K6 | Mọi dòng hàng dùng khuyến mãi có `order_date` trong `[start_date, end_date]`, xét cả `promo_id` và `promo_id_2` |
| K7 | `ship_date` ≥ `order_date` như bản gốc; số dòng mỗi bảng con = số dòng của các đơn mẫu tương ứng (không mất, không thừa) |
| K8 | `tf.json` đúng 365 bản ghi, đúng 3 giá trị cấy; `epd.json` và 3 file master trùng sha256 với đầu vào |

Test (pytest, dữ liệu nhỏ tự dựng) phải có thêm:

- **tất định:** hai lần cùng seed giống từng byte; seed khác cho ánh xạ khác;
- **cửa sổ năm lẻ:** mọi ngày trong hai cửa sổ có năm mẫu lẻ;
- **ca biên ngày:** đơn mẫu 2020-01-15 (lệch 1.096) và 2020-03-15 (lệch 1.095) ra đúng ngày 2023;
- **cặp khuyến mãi:** cùng `promo_id` ở hai `lech` khác nhau ra hai dòng; đợt cuối năm mượn cho tháng 1 có `start_date` trong 2022;
- **mỗi kiểm K2–K8 phải bắt được lỗi:** làm hỏng dữ liệu một chỗ thì đúng kiểm đó báo. Một kiểm không có ca hỏng thì coi như chưa kiểm;
- **an toàn đường dẫn:** `--ra` trong `data/` hoặc thư mục đã có file bị từ chối, không ghi gì;
- **giữ nguyên văn:** ô `0.10`, `1e3` hay chuỗi có khoảng trắng đi qua không bị đổi; BOM được giữ.

## 6. Chạy thật và báo cáo

GPT chạy một lần với tham số §2, seed mặc định, ghi vào `data_demo/` của worktree, rồi báo vào §9:

1. Lệnh đã chạy, thời gian chạy, kết quả pytest (`scripts/demo/tests`, `scripts/ingest/tests`, `scripts/pipeline/tests`), lưu ý nếu có skip.
2. Bảng số dòng và khoảng ngày từng file; tổng đơn 2023 (kỳ vọng trong khoảng 34.000–42.000, vì các năm mẫu có 34.525–41.601 đơn); số khuyến mãi mới; tổng G và COGS của 2023 kèm cảnh báo đây là số tổng hợp.
3. Kết quả chạy `auto_mapping.propose(duong_dan, data_dir='D:/retail-analytics/data')` trên `orders_enriched.csv`, `shipments_realistic.csv`, `tf.json`, `epd.json`, `eprom.json` của bộ mới, chỉ để xem, không sửa `auto_mapping`. Phải truyền `data_dir` vì worktree không có `data/`:
   - `loyalty_tier` có được nhận là cột mới không;
   - từng file được nhận về nguồn nào, có khác bản của thầy không.

   `order_id` 2023 không trùng mã nào trong `orders` gốc, nên phần khớp theo khóa có thể cho kết quả khác bản của thầy. Đây là thông tin cho lát D2, không phải lỗi của D1: ghi lại nguyên văn, đừng tự xử lý.

## 7. Claude sẽ tự kiểm

Claude không tin riêng kết quả test của GPT và sẽ:

- chạy lại script với seed khác, so `sha256` hai lần cùng seed;
- viết truy vấn độc lập đối chiếu K4–K7 trên bộ thật;
- làm hỏng từng kiểm (bỏ bước kiểm trong code) xem test có trượt không;
- kiểm `git status`: chỉ có đúng 3 chỗ ở §2, không có gì trong `data/` hay `data_demo/` bị đưa vào git.

## 8. Câu chưa chắc thì hỏi

Gặp điều trái với dữ liệu thật (ví dụ header khác phiếu, ngày mẫu không có đơn) thì dừng và báo, không tự đoán. Số khảo sát đã có (từ bản của thầy): `order_id` max 834.397; 2019–2022 không có ngày nào thiếu đơn; 206 dòng có `promo_id_2`†.

## 9. Báo cáo của GPT và kết quả rà

*(GPT điền phần báo cáo, Claude ghi kết quả rà.)*

### Báo cáo GPT — D1, ngày 2026-11-04

**Đã triển khai và sinh bộ demo; chưa thể kết luận toàn bộ hồi quy đạt.** Làm tại `D:/retail-analytics-nap`, nhánh `nap-ky/myuyen`. Chỉ tạo `scripts/demo/sinh_dot_2023.py`, `scripts/demo/tests/test_sinh_dot_2023.py`, thêm đúng dòng `data_demo/` vào `.gitignore`, và điền phần báo cáo này. Không stage, commit, push, kết nối cloud hay nạp dữ liệu vào kho.

Script dùng DuckDB 2 luồng, giới hạn 2GB, đọc CSV dưới dạng chuỗi và ghi có thứ tự; không dùng pandas. Sinh trong thư mục tạm, chỉ công bố khi K1–K8 đạt. Manifest không chứa thời gian chạy hoặc đường dẫn tuyệt đối. Test dùng dữ liệu nhỏ tự dựng, gồm so từng byte của hai lần cùng seed, seed khác, ngày nhuận, cửa sổ năm lẻ, cặp khuyến mãi, giữ nguyên văn/BOM, đường dẫn bị cấm và ca làm hỏng từng kiểm K1–K8.

#### Lệnh và kết quả kiểm thử

Chạy từ root worktree:

```powershell
& D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider scripts/demo/tests scripts/ingest/tests scripts/pipeline/tests -q --tb=short -rs --junitxml=C:/Users/Win/AppData/Local/Temp/d1_tests.xml
```

Thời gian 55,20 giây, exit code 1. Không cộng các lượt chạy lặp vào số test dưới đây:

| Nhóm | Đạt | Trượt | Lỗi thiết lập | Bỏ qua |
|---|---:|---:|---:|---:|
| `scripts/demo/tests` | 21 | 0 | 0 | 0 |
| `scripts/ingest/tests` | 146 | 1 | 6 | 17 |
| `scripts/pipeline/tests` | 99 | 0 | 0 | 2 |
| **Tổng** | **266** | **1** | **6** | **19** |

- `test_nhap_approval.py::test_epd_notebook` trượt vì thiếu `data/student_data/epd.json`.
- Sáu lỗi thiết lập trong cùng file do thiếu `data/student_data/orders_enriched.csv`: `test_orders_no_conflict`, `test_pii_defaults`, `test_contract_equivalent` và ba ca `test_load_rejects_decisions`.
- 17 ca ingest bỏ qua do thiếu `student_data`/file tham chiếu; 2 ca pipeline bỏ qua do thiếu snapshot `5bd9a84aaf73` và bản dữ liệu pipeline đã công bố.
- Không chép dữ liệu vào worktree hoặc sửa test hồi quy ngoài phạm vi để xử lý các điều kiện môi trường này. XML kết quả nằm ở đường dẫn trong lệnh trên.

#### Chạy trên dữ liệu thật để sinh bộ tổng hợp

```powershell
& D:/retail-analytics/.venv/Scripts/python.exe -B scripts/demo/sinh_dot_2023.py --student D:/retail-analytics-nhap/data/student_data --goc D:/retail-analytics/data
```

Lượt hoàn tất dùng seed mặc định 2023, mất **12,145 giây**, exit code 0: `Đã sinh bộ tổng hợp 2023: 38088 đơn; K1–K8 đạt.` K5 đối chiếu đủ 365 ngày, khớp đúng hai chữ số với ngày mẫu trong `sales.csv`; file sales gốc chỉ phục vụ đối chứng.

Trước lượt thành công có một lượt thất bại sau 23,074 giây: K5 bắt lỗi triển khai làm tròn `cogs` trước khi cộng; đồng thời console không in được tiếng Việt theo encoding mặc định. Đã sửa tính DECIMAL giữ phần thập phân đến tổng ngày, thêm dữ liệu test `cogs=0.104` để bắt lỗi này và đặt stdout UTF-8. Lượt thất bại không để lại hai thư mục kết quả. Đây là lỗi triển khai đã sửa, không phải mâu thuẫn dữ liệu nguồn.

Kết quả nằm trong `data_demo/dot_2023/` (15 file gửi) và `data_demo/dot_2023_kiem/` (2 CSV đối chứng và manifest). Số dòng không tính header; khoảng ngày dưới đây chỉ xét giá trị ngày đọc được.

| File gửi | Số dòng | Khoảng ngày |
|---|---:|---|
| `orders_enriched.csv` | 38.088 | order_date: 2023-01-01 → 2023-12-31 |
| `order_items.csv` | 40.676 | — |
| `payments.csv` | 38.088 | — |
| `shipments_realistic.csv` | 32.960 | ship_date: 2023-01-01 → 2024-01-03; delivery_date: 2023-01-03 → 2024-01-10; join_date giữ nguyên: 2018-01-12 → 2026-03-17 |
| `returns.csv` | 2.258 | return_date: 2023-01-14 → 2024-01-28 |
| `reviews.csv` | 6.379 | review_date: 2023-01-05 → 2024-02-06 |
| `promotions.csv` | 21 | start_date: 2022-11-18 → 2023-11-18; end_date: 2023-01-02 → 2024-01-02 |
| `inventory.csv` | 5.593 | snapshot_date: 2023-01-31 → 2023-12-31 |
| `web_traffic.csv` | 365 | date: 2023-01-01 → 2023-12-31 |
| `tf.json` | 365 | date hợp lệ: 2023-01-01 → 2023-12-31; một giá trị ngày không hợp lệ |
| `eprom.json` | 1.000 | start_date: 2023-01-30 → 2026-12-31; end_date: 2023-03-01 → 2026-01-01 |
| `epd.json` | 1.000 | —; chép nguyên byte |
| `customers.csv` | 121.930 | signup_date giữ nguyên: 2012-01-17 → 2022-12-31 |
| `products.csv` | 2.412 | —; chép nguyên byte |
| `geography.csv` | 39.948 | —; chép nguyên byte |

| File kiểm | Số dòng | Khoảng ngày |
|---|---:|---|
| `anh_xa_ngay.csv` | 365 | ngày đích: 2023-01-01 → 2023-12-31; ngày mẫu: 2019-01-06 → 2022-12-26 |
| `sales_doi_chung.csv` | 365 | Date: 2023-01-01 → 2023-12-31 |
| `manifest.json` | 1 đối tượng | Có số dòng, khoảng ngày và SHA-256 của 15 file gửi, 2 CSV kiểm; hash của 16 file đầu vào; seed, giá trị cấy và K1–K8 |

**38.088 đơn** nằm trong khoảng kỳ vọng; có **21 khuyến mãi mới**. Tổng các ngày trong `sales_doi_chung.csv`: **G = 1.108.842.415,88; COGS = 992.869.698,28**. Đây hoàn toàn là số tổng hợp để demo, không dùng kết luận nghiệp vụ; G tính mọi trạng thái, trước chiết khấu.

Ba giá trị cấy: dòng 104/ngày 2023-04-14 có `date="not_a_date"`; dòng 30/ngày 2023-01-30 có `sessions="N/A"`; dòng 354/ngày 2023-12-20 có `sessions=-100`. Các ngày sau 2023 trong `eprom` và `join_date` được giữ theo §4.5/§4.2, không tự sửa dữ liệu lạ. Bốn file chép nguyên byte đều khớp SHA-256 với đầu vào.

#### Kết quả `auto_mapping.propose` — chỉ đọc, phục vụ D2

Đã gọi `auto_mapping.propose(path, data_dir='D:/retail-analytics/data')` cho cả bản của thầy và bản demo của 5 file. Không sửa mã `auto_mapping`, không ghi đề xuất hoặc tạo hợp đồng. Helper kiểm trong thư mục tạm giới hạn kết nối đọc DuckDB còn 2 luồng/2GB ngay trong tiến trình kiểm. Bằng chứng đã lọc không chứa tên/số điện thoại nhân viên: `C:/Users/Win/AppData/Local/Temp/d1_mapping.json`.

| File | Nguồn bản thầy | Nguồn demo | Điểm bản thầy → demo |
|---|---|---|---|
| `orders_enriched.csv` | orders | orders | 0.8462 → 0.8397 |
| `shipments_realistic.csv` | shipments | shipments | 0.7776 → 0.7776 |
| `tf.json` | web_traffic | web_traffic | 0.9654 → 0.9654 |
| `epd.json` | products | products | 0.8182 → 0.8182 |
| `eprom.json` | promotions | promotions | 0.9767 → 0.9767 |

`loyalty_tier` nằm trong `schema_diff.cot_them`; được đề xuất `thuoc_tinh_le`, kiểu `string`, `nghi_pii=false`, 4 giá trị khác nhau và 0 ô rỗng trên 38.088 dòng. Nguồn nhận diện không đổi ở cả 5 file.

Các bộ số dưới đây giữ nguyên giá trị trả về, theo thứ tự khóa **`khop_dung_1`, `khop_va_cung_id`, `id_trung_nguon`, `id_trung_khac_noi_dung`, `danh_lai_khoa`**; mọi kết quả có `da_kiem=true`:

| File / khóa | Bản thầy | Demo |
|---|---|---|
| orders / order_id | 646749, 646749, 646945, 0, 0 | 0, 0, 0, 0, 0 |
| shipments / order_id | 521367, 521367, 566067, 0, 0 | 0, 0, 0, 0, 0 |
| tf / date | 0, 0, 998, 998, 0 | 0, 0, 0, 0, 0 |
| epd / product_id | 995, 0, 998, 998, 993 | 995, 0, 998, 998, 993 |
| eprom / promo_id | 217, 0, 0, 0, 217 | 0, 0, 0, 0, 0 |

Đây là thông tin cho D2, chưa xử lý khác biệt khớp khóa và chưa nạp bộ demo vào hệ thống.

#### Khác phiếu và phần còn chờ

Không thay đổi luật sinh hoặc mở rộng phạm vi. Có chạy lại lệnh sinh sau khi lượt đầu bị K5 chặn để hoàn tất bộ kết quả đúng. Hồi quy còn 1 trượt, 6 lỗi thiết lập và 19 bỏ qua do điều kiện dữ liệu nêu trên, không ghi là đạt. Tính tất định đã được kiểm trên fixture; kiểm độc lập trên bộ thật/seed khác và rà đột biến thuộc lượt Claude ở §7, chưa nhận là đã thực hiện. Không chạy pipeline đầy đủ, không sửa hợp đồng hay mã nạp.

### Kết quả rà của Claude — lượt 1, ngày 2026-11-04

**Chưa đạt. Dữ liệu sinh ra đúng; bộ test chưa đủ theo luật §5 "một kiểm không có ca hỏng thì coi như chưa kiểm".** Chỉ cần thêm test. Code rà tại sha256 `6060ac2c…3c43` của `sinh_dot_2023.py`; nếu file này không đổi thì không phải sinh lại `data_demo/`.

**Đã đạt, Claude tự chạy:**

- Tất định trên dữ liệu thật: seed 2023 chạy hai lần, cả 18 file trùng sha256 với nhau và với bản GPT. Seed 777 ra 37.306 đơn, K1–K8 đạt.
- Kiểm độc lập bằng Python thuần, không dùng code của GPT hay DuckDB, đạt hết ở cả seed 2023 và 777: ánh xạ ngày, từng ô giữ nguyên văn, thứ tự dòng trong từng đơn của 5 bảng con, K3–K7, 21 khuyến mãi, tồn kho, lượt truy cập, 3 giá trị cấy, `eprom.json` so theo token gốc, BOM và kiểu xuống dòng, manifest.
- G và COGS tự tính bằng `Decimal` khớp `sales_doi_chung` và dòng ngày mẫu trong `sales.csv` ở cả 365 ngày. Tổng G và COGS khớp báo cáo GPT. COGS/Revenue tháng 8/2023 là 1,388 (seed 777: 1,368), đúng tính chất năm lẻ.
- Dòng lệnh từ chối `--ra` trong `data/` và thư mục đã có file: mã thoát 1, không ghi gì.
- `git status` đúng 3 chỗ ở §2 cộng phiếu này; `data_demo/` bị `.gitignore` chặn.

**Làm hỏng từng mệnh đề (trên bản sao, không sửa code GPT):** lượt trong Claude Code bị hệ thống dừng ở ca 21/27 vì máy thiếu RAM; PM chạy lại đủ 27 ca ngoài Claude Code, log `C:/Users/Win/d1_kiem/ket_qua.log`. 10 ca bị bắt, **17 ca sống sót**:

| Kiểm | Test hiện không phát hiện khi bỏ phần này |
|---|---|
| K1 | BOM và kiểu xuống dòng |
| K2 | mã rỗng; **trùng bản gốc**; toàn bộ `returns`, `reviews`, `promotions` |
| K3 | mọi cột ngày ngoài `reviews.review_date` |
| K4 | `product_id`, `customer_id`, `zip`; `promo_id`, `promo_id_2` |
| K5 | `sales_doi_chung` lệch bộ vừa sinh |
| K6 | `promo_id_2` |
| K7 | **`ship_date` ≥ `order_date`** |
| K8 | số dòng và số ngày cấy; **đúng giá trị cấy**; kiểu số của `tf.json`; sha256 file chép |
| Luật §4.2 | thứ tự dòng trong cùng đơn; thứ tự đơn trong cùng ngày |
| Luật §4.5 | `eprom` có `start_date` từ 2023 phải giữ nguyên |

**GPT cần làm (chỉ sửa `scripts/demo/tests/test_sinh_dot_2023.py`):**

1. Thêm ca hỏng cho từng dòng K1–K8 ở bảng trên, mỗi ca khớp đúng mã kiểm. K1→K8 chạy lần lượt nên ca hỏng không được chạm kiểm đứng trước; ví dụ ca K7 phải dùng đơn đủ muộn để `ship_date` mới vẫn sau 2022-12-31, không thì K3 báo trước.
2. Thêm test cho hai dòng luật: đơn nhiều dòng hàng ra đúng thứ tự dòng như nguồn; các đơn cùng ngày giữ thứ tự file gốc; `eprom` có `start_date` từ 2023 không đổi.
3. Không sửa `sinh_dot_2023.py`. Nếu buộc phải sửa thì báo lý do và sinh lại `data_demo/`.

**Hồi quy (PM chạy cùng lượt, ngoài Claude Code):**

- `scripts/ingest/tests`: 146 đạt, 1 trượt, 6 lỗi, 17 bỏ qua; `scripts/pipeline/tests`: 99 đạt, 2 bỏ qua. Trùng số GPT báo.
- `test_nhap_approval.py` chạy lại với thư mục làm việc `D:/retail-analytics-nhap` (có đủ `data/`): 12 ca đều đạt. Vậy 1 trượt và 6 lỗi ở trên do worktree thiếu dữ liệu, không do D1.
- Các ca bỏ qua của `test_auto_mapping.py` và 2 ca pipeline vẫn chưa chạy: chúng tìm dữ liệu theo root worktree hoặc snapshot trong `warehouse/`.
- `auto_mapping.propose` trên bộ demo: nguồn, điểm, các số khớp khóa của 5 file và `loyalty_tier` là cột mới, đều trùng báo cáo GPT.

**Ghi cho phiếu D2 (không phải lỗi D1):**

- `order_id` 2023 không trùng mã gốc nên phần khớp theo khóa của `orders` và `shipments` về 0; cần xem cách nhận diện đợt khi không có khóa trùng.
- Tháng 8 lấy mẫu cả 2019 và 2021 nên bộ có 2 dòng `Urban Blowout 2023 mau …`. `assert_urban_blowout_matches_promotions.sql` chỉ xét tới 2022-12-31; tìm trong `retail_dbt` chưa thấy nơi nào đòi `promo_name` duy nhất, nhưng phải chứng minh bằng build thật ở D2.

### Báo cáo GPT — sửa theo lượt rà 1, ngày 2026-11-04

Đã làm mục **GPT cần làm**, chỉ sửa `scripts/demo/tests/test_sinh_dot_2023.py` và điền báo cáo này. Bổ sung **43 ca**, nâng bộ demo từ 21 lên **64 ca**. Tất cả dữ liệu kiểm được tự dựng trong thư mục tạm; không đọc dữ liệu thật trong test.

| Phần bổ sung | Ca kiểm mới |
|---|---|
| K1 | Bỏ BOM; đổi LF thành CRLF. Mỗi ca phải báo đúng K1. |
| K2 | Mã rỗng, trùng trong bộ và trùng bản gốc cho từng bảng orders, returns, reviews, promotions: 12 ca, đúng K2. |
| K3 | Ngày không sau 2022-12-31 ở cả 7 cột thuộc orders, shipments, returns, reviews, inventory, web_traffic; đúng K3. |
| K4 | Thiếu master cho product_id, customer_id, zip, promo_id và promo_id_2; đúng K4. |
| K5 | Chỉ đổi unit_price trong bộ vừa sinh, giữ nguyên cả sales gốc lẫn sales đối chứng; phải báo K5 do tổng tính lại lệch. |
| K6 | Thêm mã khuyến mãi tồn tại nhưng hết hiệu lực, chỉ gán qua promo_id_2; promo_id thứ nhất vẫn hợp lệ; đúng K6. |
| K7 | Chọn đơn từ tháng 6, đưa ship_date về trước order_date một ngày nhưng vẫn sau 2022-12-31; đúng K7, không bị K3 chặn trước. |
| K8 | Thừa dòng JSON; thừa mục cấy; hai mục cấy cùng ngày; sai giá trị cấy dù thân JSON khớp metadata; đổi int thành float có cùng giá trị; đổi byte từng file chép (epd và 3 master) mà không đổi khóa/số liệu. Tổng 9 ca, đúng K8. |
| Thứ tự dòng hàng | So chuỗi quantity của từng đơn với nguồn qua ánh xạ ngày, đồng thời yêu cầu fixture thực sự có đơn nhiều dòng với giá trị khác nhau. |
| Thứ tự đơn cùng ngày | Đặt đơn mã 9999 trước đơn mã nhỏ hơn trong nguồn; kiểm thứ tự dấu nhận biết và mã mới nối tiếp trong đầu ra. |
| eprom từ 2023 | Ba ca start_date năm 2023, năm nhuận 2024 và năm 2026; so toàn bộ bản ghi, gồm end_date và giá trị lạ, phải giữ nguyên. |

Lệnh chạy tại root `D:/retail-analytics-nap`, nhánh `nap-ky/myuyen`:

```powershell
& D:/retail-analytics/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider scripts/demo/tests/test_sinh_dot_2023.py -q --tb=short --junitxml=C:/Users/Win/AppData/Local/Temp/d1_review1_tests.xml
```

**Kết quả: 64 đạt, 0 trượt, 0 lỗi, 0 bỏ qua; 133,62 giây; exit code 0.** Các ca hỏng yêu cầu `CheckError` khớp mã K tương ứng, không chỉ chấp nhận một lỗi bất kỳ.

SHA-256 `sinh_dot_2023.py` trước và sau lượt sửa đều là `6060ac2cabb43a59ae50796cb982e2e595d40653efe0d735f106da35a603c43a`, trùng bản Claude đã rà. Không sửa script sinh, không sinh lại `data_demo/`, không chạy lại auto mapping, ingest/pipeline hoặc 27 đột biến của PM. Kết quả hồi quy trước đó giữ nguyên lịch sử, không tính là đã chạy lại trong lượt này. Các test mới phủ các mệnh đề lọt ở bảng rà; chưa tuyên bố kết quả chạy lại bộ đột biến.

`git diff --check` không báo lỗi whitespace; không stage/commit/push. Không thay đổi thiết kế, không có điểm làm khác yêu cầu lượt rà 1.

### Kết quả rà của Claude — lượt 2, ngày 2026-11-04

**Đạt theo §5 và §7, còn 2 khoảng trống đã ghi, chờ PM quyết định có bổ sung không.** Rà tại sha256 `6060ac2c…3c43` (`sinh_dot_2023.py`) và `74e40115…8e8b` (test). PM chạy ngoài Claude Code, log `C:/Users/Win/d1_kiem/ket_qua.log`.

- Làm hỏng từng mệnh đề, 32 ca: bộ gốc 64 ca đạt. **27 ca của lượt 1 đều bị bắt.** Trong 5 ca chi tiết Claude thêm ở lượt này, 3 ca bị bắt, 2 ca sống sót (bảng dưới).
- Hồi quy không đổi so với lượt 1: `scripts/ingest/tests` 146 đạt, 1 trượt, 6 lỗi, 17 bỏ qua; `scripts/pipeline/tests` 99 đạt, 2 bỏ qua. `test_nhap_approval.py` với đủ dữ liệu: 12/12 đạt.
- `auto_mapping.propose` trên bộ demo trùng lượt 1. `data_demo/dot_2023` khớp sha256 trong manifest, không sinh lại.
- `git status`: `M .gitignore`, `?? docs/giao_viec_sinh_dot_2023.md`, `?? scripts/demo/`; không có gì staged; `data_demo/` bị `.gitignore` chặn.

| Khoảng trống | Bộ test chưa phát hiện | Vì sao chưa chặn D1 |
|---|---|---|
| K6 | bỏ riêng phần xét `promo_id`, chỉ còn `promo_id_2` | Kiểm độc lập trên dữ liệu thật (seed 2023, 777): mọi dòng dùng khuyến mãi đều trong hiệu lực, xét cả hai cột |
| K7 | kiểm số dòng chỉ còn `payments`, bỏ 4 bảng con khác | Kiểm độc lập trên dữ liệu thật: số dòng và thứ tự cả 5 bảng con đúng |

Cả hai là độ phủ của test, không phải lỗi dữ liệu hay lỗi logic: code hiện vẫn kiểm đủ. Rủi ro chỉ xuất hiện nếu sau này sửa `sinh_dot_2023.py`; khi đó phải thêm 2 ca này trước.

**Chưa chạy, không tính là đạt:** 17 ca ingest và 2 ca pipeline bị bỏ qua vì thiếu `data/student_data` trong worktree hoặc snapshot trong `warehouse/`.
