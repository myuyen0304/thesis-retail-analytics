# Giao việc T1: đường tự động cho dữ liệu nhập (gửi file → tự duyệt → tự chạy → tự công bố khi đủ điều kiện)

Soạn ngày 2026-10-31. PM duyệt thiết kế [thiet_ke_duong_tu_dong.md](thiet_ke_duong_tu_dong.md) cùng ngày; Claude soạn phiếu. GPT code
§3–§5; Claude rà độc lập trước khi commit theo 5 bước rà ở đầu [giao_viec_theo_so_do.md](giao_viec_theo_so_do.md). Chưa đạt thì
Claude ghi phát hiện vào §9, GPT sửa tiếp. Nghiệm thu thủ công §6 do PM chạy.

**Bắt đầu khi:** phiếu nhập UI ([giao_viec_nhap_du_lieu_ui.md](giao_viec_nhap_du_lieu_ui.md)) qua nghiệm thu §6 của nó. Phiếu này xây
trên luồng tay đã nghiệm thu, không thay nó.

Đọc trước:
- `AGENTS.md`, `CLAUDE.md`, `docs/agent_workflows.md`; skill `retail-analytics-engineering`, `developing-with-streamlit`;
- [thiet_ke_duong_tu_dong.md](thiet_ke_duong_tu_dong.md) (toàn bộ; §0 là quyết định PM, không đổi);
- [giao_viec_nhap_du_lieu_ui.md](giao_viec_nhap_du_lieu_ui.md) §2 (môi trường, ràng buộc), §3 (thiết kế luồng tay), §9 (N1–N5: các
  lỗi khóa/worker đã sửa — đừng tái phạm);
- [tien_hoa_schema.md](tien_hoa_schema.md) §4 (phân loại thay đổi: thêm cột là "cộng thêm", thiếu/đổi tên/đổi kiểu là "phá").

## 0. Phiếu này nằm ở đâu

- Luồng hiện tại: Quản lý gửi → máy đề xuất → **DE sửa cột, bấm Duyệt** → **DE bấm Chạy** → **Admin bấm Công bố**. Nghiệm thu
  2026-10-31 cho thấy: `orders_enriched` đã có hợp đồng duyệt sẵn (`scripts/ingest/extensions/orders_enriched.yml`) mà DE vẫn phải
  sửa tay 3 cột; quên sửa thì lượt chạy ~7 phút rồi mới bị `validate` chặn.
- PM muốn: file của nguồn **đã có hợp đồng** đi hết luồng **không ai bấm**; người chỉ xử lý ngoại lệ. Mọi cổng kiểm giữ nguyên.
- Vẫn **chỉ xử lý trên app local + DuckDB**. PM đổi 2026-11-01: hai trang bật cứng mọi nơi, bỏ cờ `RETAIL_APP_NHAP_DU_LIEU` (§3.12); trên Streamlit Cloud
  chúng chỉ hiện thông báo. Không ghi gì lên Databricks, không Airflow. Bản production là lát T2 riêng (thiết kế §8); **không làm gì cho T2 trong phiếu này**.

## 1. Luồng đích và giới hạn

```
Gửi file → auto mapping → phân loại (§3.2)
   ├─ tu_dong  → tự duyệt theo hợp đồng hiện hành (§3.3) → hàng đợi (§3.5) → prepare/forecast/build/validate → tự công bố (§3.6)
   │                └─ có cột mới → đề xuất nâng hợp đồng cho DE (§3.4), không chặn luồng
   └─ can_nguoi → cho_duyet như hiện nay, kèm danh sách lý do (ngôn ngữ nghiệp vụ cho Quản lý, kỹ thuật cho DE)
Lỗi ở cổng nào → loi, không công bố; DE "Duyệt lại" được (N6, §3.7).
```

Không làm: sinh model dbt tự động; cho cột mới lên mart khi chưa có người duyệt; chạy song song hai lượt; đổi ngưỡng cách ly; đổi luồng
tay (DE vẫn duyệt/chạy/công bố tay được với yêu cầu `can_nguoi`); đợt giao dịch kỳ mới (thuộc D1–D6).

## 2. Môi trường và ràng buộc

- Worktree và nhánh: Claude tạo nhánh `tu-dong/myuyen` tách từ `nhap-ui/myuyen` (sau khi phiếu nhập UI qua §6), worktree riêng hoặc
  dùng lại `D:/retail-analytics-nhap` — Claude báo trước khi GPT bắt đầu. Python `D:/retail-analytics/.venv/Scripts/python.exe`,
  thư mục làm việc là root worktree. **Không commit, không push.**
- Giữ nguyên mọi ràng buộc ở phiếu nhập UI §2, trừ cờ (đã bỏ, §3.12): root `warehouse/pipeline/ui-nhap` và `--target duckdb` viết cứng; file tải lên là dữ
  liệu không tin cậy; mọi thứ sinh ra nằm trong thư mục đã gitignore; **không ghi vào `scripts/ingest/extensions/`** (chỉ đọc file đó
  để gieo hợp đồng, §3.1); không tạo bảng mới trên Neon.
- Người thao tác của bước tự động là **`he_thong`** (một chuỗi cố định, không phải tài khoản đăng nhập được). Không được dùng tên của
  người gửi cho bước duyệt/chạy/công bố tự động.
- RAM: GPT chạy test, không chạy lượt pipeline đầy đủ; lượt đầy đủ ở §6 do PM chạy.
- Để lát T2 sau này chỉ phải thay chỗ lưu: phân loại (§3.2), hợp đồng của lượt (§3.3) và phần lõi công bố (§3.6) là **hàm thuần**,
  không tự đọc/ghi đĩa. Mọi đường dẫn đĩa mới (kho hợp đồng, hàng đợi, nhật ký chờ) đi qua `contract_registry` / `nhap_store`, không rải
  trong view hay runner. Không viết adapter cloud nào.

## 3. Thiết kế

### 3.1 Kho hợp đồng đã duyệt

Module mới `scripts/ingest/contract_registry.py` (tên tương đương được), thư mục `warehouse/ui_nhap/hop_dong_da_duyet/<ten>/`:
- `v<N>.yml`: hợp đồng đầy đủ, qua được `extension_contract.load`; **không sửa** sau khi ghi.
- `hien_hanh.json`: `{phien_ban, sha256, duyet_boi, ngay_duyet, nguon_goc}`; `nguon_goc` ∈ {`repo:<đường dẫn>`, `yeu_cau:<id>`,
  `nang_hop_dong:<id>`}. Ghi nguyên tử (`atomic_json`) dưới `writer_lock` của thư mục đó.
- **Gieo:** khi đọc mà `<ten>` chưa có trong kho nhưng có `scripts/ingest/extensions/<ten>.yml` → ghi v1 từ file repo (`nguon_goc:
  repo:...`). Chỉ đọc file repo, không bao giờ ghi lại.
- **Lần duyệt tay đầu** của một tên chưa có trong kho (luồng tay hiện tại, `nhap_store.approve`) → ghi v1 (`nguon_goc: yeu_cau:<id>`).
  Duyệt tay cho tên đã có hợp đồng thì **không** đổi hợp đồng hiện hành (đổi hợp đồng chỉ qua §3.4) — ghi rõ trên trang Duyệt.
- Hàm `ung_vien(de_xuat) -> list[(ten, phien_ban, doc, cot_thieu)]`: mọi hợp đồng hiện hành có
  `khoa_noi.nguon == de_xuat['nguon']['de_xuat']`; `cot_thieu` = cột trong `header` của hợp đồng mà file không có (so theo
  `normalize`). Tên file **không** dùng để chọn (file năm sau có thể tên khác).

### 3.2 Phân loại

Hàm thuần `scripts/ingest/tu_dong.py: phan_loai(de_xuat, ung_vien, co_model) -> {'ket_qua': 'tu_dong'|'can_nguoi', 'ten', 'phien_ban',
'cot_moi': [...], 'ly_do': [{'ma', 'nghiep_vu', 'ky_thuat'}]}`. Không I/O; mọi dữ kiện truyền vào. `can_nguoi` khi **bất kỳ** điều
nào sau đây:

| Mã | Điều kiện (trên đề xuất `auto_mapping.propose`) |
|---|---|
| `chua_ro_nguon` | `nguon.de_xuat` rỗng (dưới ngưỡng điểm/khoảng cách, `auto_mapping.py:65–68`) |
| `chua_co_hop_dong` | `ung_vien` rỗng: nguồn này chưa có hợp đồng hiện hành nào (nguồn mới, lần đầu DE duyệt) |
| `thieu_cot` | có ứng viên nhưng **mọi** ứng viên đều có `cot_thieu` khác rỗng (file thiếu hoặc đổi tên cột của hợp đồng); lý do liệt kê cột thiếu của ứng viên ít thiếu nhất, vd "File thiếu cột `comment` so với hợp đồng `orders_enriched` v1" |
| `nhieu_hop_dong` | hơn một ứng viên có `cot_thieu` rỗng |
| `doi_kieu` | cột loại `khop` có `khong_ep_duoc > 0` |
| `xung_dot_khoa` | `xung_dot_khoa.id_trung_khac_noi_dung > 0` hoặc `xung_dot_khoa.da_kiem` không phải `true` |
| `tham_chieu_thieu` | `tham_chieu_thieu` khác rỗng |
| `chua_co_model` | `co_model` sai |

Ngược lại (đúng một ứng viên có `cot_thieu` rỗng) → `tu_dong`; `cot_moi` = cột có trong file mà không có trong `header` hợp đồng. Cột `nap` của hợp đồng mà giá trị không ép
được kiểu thì **không** xét ở đây: cổng cách ly R5 (`extension_prepare.py`, ngưỡng 1%) bắt lúc chạy.

### 3.3 Tự duyệt (hợp đồng của lượt)

Hàm thuần `hop_dong_cua_luot(hop_dong_hien_hanh, header_file, file_rel, phien_ban, ngay) -> dict`:
- `header` = **đúng header của file** (prepare kiểm header cả thứ tự, `extension_prepare.py:51–54`); `cot` sắp theo header đó, giữ
  nguyên quyết định từng cột của hợp đồng hiện hành;
- mỗi cột mới thêm `{ten, xu_ly: bo, ly_do: 'cột mới, chờ duyệt nâng hợp đồng', trang_thai: da_duyet}`;
- `file` = `ui_nhap/<id>/<ten_file>`; `duyet_boi` = `he_thong (hợp đồng <ten> v<N>, sha256 <8 ký tự đầu>)`; `ngay_duyet` = lúc tự
  duyệt; các trường khác (`khoa_noi`, `thuc_the`, `nguong_cach_ly`, …) giữ nguyên;
- đầu ra phải qua `extension_contract.load`. Không qua → yêu cầu thành `can_nguoi` với lý do `hop_dong_khong_hop_le` (không bao giờ
  chạy với hợp đồng hỏng).

`RequestStore`: thêm hàm tự duyệt **không qua `actor()`** (không có phiên đăng nhập của DE), ghi `cho_duyet → da_duyet` với người
`he_thong`, ghi file hợp đồng cùng cách `approve` hiện tại (`nhap_store.py:168–176`: kiểm trên bản tạm rồi `os.replace`), lưu vào
record: `duong: 'tu_dong'`, `hop_dong: {ten, phien_ban, sha256}`, `cot_moi`. Hàm này chỉ được gọi từ `submit` sau phân loại; có test
khẳng định không đường nào khác gọi được nó với yêu cầu `can_nguoi`.

`submit` (`nhap_store.py:143–154`): sau `write_proposal` → gieo/đọc kho hợp đồng → `phan_loai` → `tu_dong`: tự duyệt rồi đưa vào hàng
đợi (§3.5); `can_nguoi`: `cho_duyet` như hiện nay, lưu `ly_do` vào record.

### 3.4 Đề xuất nâng hợp đồng (cột mới)

- Yêu cầu tự động có `cot_moi` khác rỗng → trang Duyệt có mục **"Nâng hợp đồng `<ten>` v<N> → v<N+1>"**, chỉ gồm các cột mới, mặc
  định theo `approval.default_decisions` (PII → `silver`), DE sửa như form duyệt hiện tại.
- DE duyệt → ghi `v<N+1>` vào kho (§3.1, `nguon_goc: nang_hop_dong:<id>`), qua `extension_contract.load` trước khi ghi → **tạo yêu cầu
  mới** dùng lại đúng file đã tải lên của yêu cầu gốc (sao chép vào `data/ui_nhap/<id_moi>/`, kiểm sha256 bằng nhau), ghi
  `nap_bu_tu: <id gốc>`, rồi đi đường tự động với v<N+1>. Yêu cầu gốc không đổi (bất biến).
- "Silver" của phần mở rộng = file `orders_enriched.parquet` trong snapshot (`warehouse/pipeline/ui-nhap/snapshots/<snapshot_id>/`):
  prepare ghi mọi cột `khoa_noi`/`nap` (`extension_contract.loaded_columns`, `extension_contract.py:81–84`); `stg_orders_enriched.sql`
  chọn cột tường minh nên cột mới không đi tiếp. Không cần sửa `retail_dbt/` cho cột mới ở silver.
- Cột mới chỉ lên mart khi model dbt có cột đó; chưa có thì cổng `validate_extension_visibility` xử lý như hiện nay (cột `mart` không
  có trong mart → lỗi). Vì vậy form nâng hợp đồng **cảnh báo** khi DE chọn `mart` cho cột model chưa có, và mặc định `silver`.
- DE từ chối nâng hợp đồng → ghi lý do; cột mới tiếp tục bị `bo` ở các lần gửi sau (vẫn tự động), mục đề xuất không hiện lại cho
  đúng tập cột đó.

### 3.5 Hàng đợi

- `warehouse/ui_nhap/hang_doi/`: mỗi mục một file `<thời điểm>_<id>.json`, FIFO theo tên. Thêm/lấy dưới khóa `dispatch` hiện có.
- Một lượt tại một thời điểm (giữ `worker_slot`, `dispatch_lock`, `active.json`, `writer.lock` như hiện tại — đọc kỹ N1, N5 ở §9 phiếu
  nhập UI trước khi sửa `nhap_runner`).
- Sau khi đưa vào hàng đợi và khi worker xong một lượt: nếu không bận thì khởi động mục đầu hàng đợi với người `he_thong` (hàm khởi
  động nội bộ dùng chung với `start`, không qua `actor()`). Worker có thể xử lý tiếp mục kế trong cùng tiến trình hoặc sinh worker mới;
  chọn một cách, ghi lý do trong báo cáo.
- **Phục hồi:** trang Duyệt và trang Gửi khi tải mà hàng đợi khác rỗng và không bận (sau đối soát worker chết như hiện tại) → khởi
  động mục đầu. Mục mà yêu cầu không còn `da_duyet` thì bỏ khỏi hàng đợi, ghi lý do.
- Nút "Chạy" tay của DE: hàng đợi khác rỗng thì khóa, ghi "Đang có N yêu cầu tự động trong hàng đợi".
- Trang Gửi: yêu cầu trong hàng đợi hiện "Đang xếp hàng (thứ k)".

### 3.6 Tự công bố

- Lượt của yêu cầu `duong: 'tu_dong'` tới `da_kiem` → worker công bố ngay, người `he_thong`.
- **Bẫy:** `nhap_runner.publish` (`nhap_runner.py:265–280`) gọi `actor('cong_bo')` và `_busy_reason_locked`; gọi từ worker sẽ thấy
  chính khóa worker của mình là "bận" và không có phiên đăng nhập. Tách phần lõi (kiểm `da_kiem` → stage `publish` → `da_cong_bo`)
  thành hàm nội bộ dùng chung: `publish` (Admin, giữ nguyên kiểm quyền và kiểm bận) và worker (đang giữ slot, không kiểm bận lại).
- Công bố lỗi → `loi` với thông báo, không thử lại tự động.
- Admin: thêm nút **Rollback** trên trang Duyệt cho root `ui-nhap` (gọi CLI `rollback` hiện có, `scripts/pipeline/cli.py:515,
  536–563`, `--target duckdb --root warehouse/pipeline/ui-nhap`), chỉ `admin`, hỏi xác nhận, ghi nhật ký. Lệnh sinh ra phải qua cùng
  hàm thuần kiểu `lenh` (test không bao giờ chứa `databricks`/`pipeline/docker`).

### 3.7 N6: Duyệt lại yêu cầu lỗi

- Thêm chuyển `loi → cho_duyet` (`nhap_store.py:23`), chỉ DE/Admin qua `actor('duyet')`, bắt buộc ghi lý do, ghi nhật ký
  `nhap_duyet_lai`. Duyệt lại xong đi luồng tay như hiện nay (hợp đồng mới ghi đè `hop_dong/<ten>.yml` của yêu cầu, `lan_chay` tiếp
  tục tăng, `run_id` không trùng).
- Yêu cầu `duong: 'tu_dong'` sau khi Duyệt lại thành luồng tay (`duong: 'tay'`): không tự công bố nữa.

### 3.8 Gợi ý kiểu số cho lần duyệt đầu

- `auto_mapping.column_profile` (`auto_mapping.py:72–85`) thêm `kieu_goi_y`: `integer` khi **mọi** giá trị khác rỗng ép được sang
  integer **và** không giá trị nào có số 0 đứng đầu (trừ chính "0") **và** cột không nghi PII; ngược lại `string`. Giữ các trường cũ.
- `approval.default_decisions` (`approval.py:26`) dùng `kieu_goi_y` cho cột `nap` mới thay cho `string` cố định. Báo cáo mapping ghi lý
  do ("100% giá trị là số nguyên").
- Với `orders_enriched.csv`: `years_experience` → `integer`; `sales_employee_id`, `comment` → `string`.

### 3.9 Nhật ký

- Sự kiện mới: `nhap_tu_duyet`, `nhap_xep_hang`, `nhap_chay` (người `he_thong`), `nhap_cong_bo` (người `he_thong`), `nhap_nang_hop_dong`,
  `nhap_duyet_lai`, `nhap_rollback`; `detail` có `id`, `ten`, `phien_ban` hợp đồng khi có.
- Bước chạy trong worker (ngoài phiên Streamlit): **phải kiểm** `roles.store()` dùng được trong worker (`roles.db_url`,
  `roles.py:98–107`, đọc `RETAIL_APP_DB_URL` hoặc `st.secrets`). Không dùng được → ghi dòng vào
  `warehouse/ui_nhap/nhat_ky_cho.jsonl` (nguyên tử theo dòng); trang Duyệt khi tải đẩy các dòng này lên Neon rồi xóa dòng đã đẩy,
  và hiện "N dòng nhật ký chờ đồng bộ" khi còn. Ghi rõ trong báo cáo cách nào đã chạy được trên máy.

### 3.10 Giao diện

- Trang Gửi (Quản lý): mỗi yêu cầu hiện **"Tự động"** hoặc **"Chờ đội dữ liệu"** + lý do nghiệp vụ (vd "File có thêm cột `bonus` —
  phần đã có vẫn được cập nhật, cột mới chờ đội dữ liệu duyệt"). Không lộ đường dẫn, sha, log.
- Trang Duyệt (DE/Admin): nhãn đường đi, phiên bản hợp đồng đã dùng, lý do `can_nguoi` (kỹ thuật), mục nâng hợp đồng, hàng đợi, nút
  Duyệt lại (N6), Rollback (Admin).

### 3.11 Ô "Kiểu" thành danh sách chọn (PM phát hiện khi nghiệm thu 2026-11-01)

- Hiện ô Kiểu trong bảng duyệt cột là ô gõ chữ tự do (`views/duyet_du_lieu.py:74`, `TextColumn`). Bấm đúp không có lựa chọn; gõ sai
  (vd `int`, `Integer`) thì phải tới lúc `extension_contract.load` mới báo lỗi.
- Sửa: đưa danh sách kiểu hợp lệ thành **một hằng** trong `scripts/ingest/extension_contract.py` (hiện viết cứng trong biểu thức ở
  `extension_contract.py:61`: `string`, `integer`, `date`, `double`). Biểu thức kiểm ở dòng 61 dùng hằng đó. Ô Kiểu đổi thành
  `SelectboxColumn('Kiểu', options=<hằng đó>, required=True)`.
- Không đổi hành vi kiểm: hợp đồng có kiểu ngoài danh sách vẫn bị `load` từ chối như cũ. Áp cho cả màn duyệt nâng hợp đồng (§3.4)
  nếu dùng chung bảng.

### 3.12 Bật cứng hai trang, an toàn trên Streamlit Cloud (PM đổi 2026-11-01)

- **Bỏ cờ:** bỏ kiểm `RETAIL_APP_NHAP_DU_LIEU` ở `apps/retail_app/ui/roles.py:63`; ma trận quyền dùng thẳng `_PAGE_CHOICES`, người có quyền thấy
  hai trang ở mọi nơi. Sửa các test đang đặt cờ (`apps/retail_app/tests/test_nhap_du_lieu.py:36, 149, 423`).
- **Lỗi phải chặn:** `views/gui_du_lieu.py:4–5` và `views/duyet_du_lieu.py:6–8` import ở đầu file; chuỗi `nhap_store` → `scripts.ingest.auto_mapping`
  → `import duckdb`, và `nhap_runner` → `nhap_store`. `apps/retail_app/requirements.txt` cố ý không có duckdb. Bỏ cờ mà không sửa thì mở trang trên
  cloud có thể lỗi ngay, hoặc lỗi cả app nếu import xảy ra lúc dựng menu.
- **Sửa:** `nhap_store.py` và `nhap_runner.py` chỉ import `auto_mapping`/`duckdb` trong hàm cần dùng. Thêm một hàm kiểm môi trường (ví dụ
  `nhap_kha_dung()`: có duckdb **và** có `data/` với đủ 14 nguồn). Hai view gọi hàm này trước mọi thao tác.
- **Khi không khả dụng** (Streamlit Cloud): trang vẫn hiện, chỉ có thông báo "Chức năng nhập dữ liệu trên bản web đang được phát triển. Hiện chạy ở
  bản nội bộ." Không có ô tải file, không có nút, không đọc/ghi đĩa, không tạo thư mục, không gọi Databricks.
- **Vẫn kiểm quyền như cũ:** không có quyền thì báo lỗi quyền trước thông báo trên.
- **Thư viện khác:** `nhap_store.py:12` và `duyet_du_lieu.py:5` import `yaml`, mà `requirements.txt` không ghi `pyyaml`. Kiểm mọi import của hai view và hai module trên một
  môi trường cài **đúng** `apps/retail_app/requirements.txt`; thiếu thì chuyển vào trong hàm, không thêm duckdb vào file đó.

## 4. Yêu cầu theo file

| File | Việc |
|---|---|
| `scripts/ingest/contract_registry.py` (mới) | §3.1 |
| `scripts/ingest/tu_dong.py` (mới) | `phan_loai` §3.2, `hop_dong_cua_luot` §3.3 |
| `scripts/ingest/auto_mapping.py` | `kieu_goi_y` §3.8; không đổi các mục cũ |
| `scripts/ingest/approval.py` | dùng `kieu_goi_y` §3.8 |
| `apps/retail_app/ui/nhap_store.py` | `submit` phân loại, tự duyệt, `loi → cho_duyet`, nâng hợp đồng tạo yêu cầu nạp bù |
| `apps/retail_app/ui/nhap_runner.py` | hàng đợi, khởi động `he_thong`, tự công bố, tách lõi `publish`, rollback |
| `apps/retail_app/views/gui_du_lieu.py`, `duyet_du_lieu.py` | §3.10; ô Kiểu thành danh sách chọn §3.11; thông báo khi không khả dụng §3.12 |
| `apps/retail_app/ui/roles.py` | bỏ cờ §3.12; không đổi gì khác |
| `scripts/ingest/extension_contract.py` | chỉ tách hằng kiểu hợp lệ §3.11; không đổi gì khác |
| test tương ứng | §5 |

Không sửa: `retail_dbt/`, `scripts/ingest/extensions/`, `scripts/pipeline/` (trừ khi cần đọc; CLI `rollback` đã có), `deploy/`,
`docker-compose.airflow.yml`, trang PS, chat, `docs/`.

## 5. Kiểm

Chạy được trong worktree, không cần Databricks, không chạy pipeline đầy đủ (giả lập CLI bằng script tạm như phiếu nhập UI):
- **registry:** gieo v1 từ repo đúng một lần, không ghi vào `scripts/ingest/extensions/`; v1 không bị sửa khi có v2; `hien_hanh.json`
  ghi nguyên tử; `ung_vien` chọn theo nguồn + header, không theo tên file (đổi tên file vẫn ra cùng ứng viên).
- **phan_loai:** mỗi mã ở §3.2 có ít nhất một test ra `can_nguoi` đúng mã; file khớp → `tu_dong`; file thêm cột → `tu_dong` +
  `cot_moi`; file thiếu một cột / đổi tên một cột → `thieu_cot` kèm đúng tên cột thiếu (không phải `chua_co_hop_dong`); nguồn chưa
  có hợp đồng nào → `chua_co_hop_dong`; `epd.json` → `can_nguoi` (`xung_dot_khoa` hoặc `chua_co_hop_dong`).
- **hop_dong_cua_luot:** với `orders_enriched.csv` ra hợp đồng **tương đương** `scripts/ingest/extensions/orders_enriched.yml` (cùng
  `cot`, `thuc_the`, `khoa_noi`, `nguong_cach_ly`; khác `file`, `duyet_boi`, `ngay_duyet`); header đảo thứ tự cột → `header` theo file,
  quyết định từng cột không đổi; thêm cột → cột đó `bo`; kết quả luôn qua `extension_contract.load`.
- **store/runner:** gửi file khớp → không cần phiên DE vẫn tới `da_duyet` + có mục hàng đợi; hai yêu cầu liền nhau → chạy lần lượt,
  không yêu cầu nào bị từ chối vì bận; worker chết giữa chừng → `loi` (như N1) và hàng đợi vẫn đi tiếp; `da_kiem` của yêu cầu tự
  động → `da_cong_bo` với `he_thong`; của yêu cầu tay → giữ `da_kiem`; `publish` của Admin vẫn kiểm quyền và kiểm bận như cũ; `loi →
  cho_duyet` chỉ DE/Admin, bắt buộc lý do; hàm tự duyệt không gọi được cho yêu cầu `can_nguoi`.
- **nâng hợp đồng:** duyệt → v2 trong kho, yêu cầu nạp bù mới cùng sha256 file, đi đường tự động với v2; từ chối → lần gửi sau không
  hiện lại đề xuất cho cùng tập cột.
- **kieu_goi_y:** `years_experience` → integer; cột số có số 0 đầu (vd mã zip "01234", số điện thoại) → string; cột nghi PII → string.
- **ô Kiểu (§3.11):** tùy chọn của ô Kiểu đúng bằng hằng trong `extension_contract`; hợp đồng có kiểu `int` vẫn bị `load` từ chối.
- **an toàn trên cloud (§3.12):** chạy trong môi trường **không có duckdb** (chặn import, ví dụ `sys.modules['duckdb'] = None` trong subprocess): import được
  `ui.roles`, `ui.nhap_store`, `ui.nhap_runner`; chạy `AppTest` cho cả hai view với vai `quan_ly`, `ky_su`, `admin` → không exception, có thông báo, không có ô tải file
  hay nút, không tạo file/thư mục nào. Thiếu `data/` nhưng có duckdb cũng ra thông báo. Không đặt cờ thì người có quyền vẫn thấy hai trang trong menu.
- **rollback:** lệnh sinh ra có `--target duckdb` và root `ui-nhap`, không chứa `databricks`/`pipeline/docker`; chỉ Admin.
- **Thử vô hiệu (mutation):** sửa tạm từng chỗ và ghi test nào trượt: bỏ điều kiện `xung_dot_khoa`; chọn ứng viên theo tên file; bỏ
  `bo` cho cột mới (cột mới thành `nap`); tự công bố cả yêu cầu tay; bỏ kiểm `actor` ở `publish` của Admin; worker không lấy mục
  hàng đợi kế; đưa lại `import auto_mapping` lên đầu `nhap_store.py`. Công cụ thử để ở thư mục tạm, không đưa vào repo.
- Toàn bộ test hiện có đạt như trước (ghi số đạt/trượt/skip); test của phiếu nhập UI đạt nguyên.

## 6. Nghiệm thu thủ công (PM chạy, sau khi §5 đạt và Claude rà xong)

Từ PowerShell, root worktree (không còn cờ, §3.12). Dùng file 2022 cho nhanh: `data\student_data\demo_2022\orders_enriched.csv`.

1. `chushop` gửi file 2022 → **không ai bấm gì** → trang Gửi lần lượt hiện "Tự động" → "Đang chạy" → "Đã cập nhật" (~7 phút†).
   Trang Duyệt: hợp đồng `orders_enriched` v1 (`repo:`), 0 dòng cách ly, `dim_sales_employee` 200, 36.004 đơn có nhân viên;
   `sales_employee_name` ở mart, `comment` ở silver; `warehouse/pipeline/ui-nhap/state.json` có `active`.
2. Claude tạo file thử từ file 2022 thêm cột `bonus` (để trong `data/student_data/demo_2022/`, gitignore). `chushop` gửi → vẫn tự công
   bố; `bonus` không có trong kho; trang Duyệt có "Nâng hợp đồng v1 → v2". `de1` duyệt `bonus` (silver) → yêu cầu nạp bù tự chạy và
   công bố. Claude kiểm: lượt đầu, `orders_enriched.parquet` của snapshot **không** có cột `bonus`; lượt nạp bù, parquet đó **có**
   `bonus`, còn mọi bảng trong `r_<release_id>_marts` / `_reporting` không có.
3. Gửi file thiếu cột `comment` (Claude tạo) → "Chờ đội dữ liệu", lý do "thiếu cột `comment`"; gửi `epd.json` → "Chờ đội dữ liệu",
   lý do xung đột khóa hoặc chưa có hợp đồng; cả hai không tự chạy. Với yêu cầu thiếu cột, `de1` mở bảng duyệt cột: bấm đúp ô
   Kiểu thấy danh sách `string / integer / date / double`, không gõ chữ được (§3.11).
4. Gửi hai file 2022 liền nhau → chạy lần lượt, trang Gửi hiện "Đang xếp hàng (thứ 2)".
5. Admin Rollback về bản trước → `state.json` đổi `active`; nhật ký có dòng rollback.
6. Trang Phân quyền → nhật ký có các bước của `he_thong` (hoặc trang Duyệt báo dòng chờ đồng bộ rồi đẩy lên được).
7. Bản Cloud giả lập: Claude chạy app trong môi trường không có duckdb → hai trang hiện thông báo, không có ô tải file, các trang PS và chat bình thường.

## 7. Báo cáo của GPT khi xong (PM dán cho Claude rà)

- Danh sách file tạo/sửa; với file đã có trong Git, tóm tắt từng chỗ đổi.
- Số đạt/trượt/skip của §5; kết quả thử vô hiệu (sửa gì, test nào trượt).
- Cách worker xử lý hàng đợi (cùng tiến trình hay worker mới) và vì sao; sơ đồ khóa (dispatch, worker, `active.json`, `writer.lock`)
  sau khi sửa.
- Nhật ký trong worker ghi được lên Neon hay phải qua `nhat_ky_cho.jsonl`; đã thử thế nào.
- Chỗ làm khác phiếu (nếu có) và vì sao; lỗi thấy ngoài phạm vi.

## 8. Không giao GPT

- §6 nghiệm thu: PM chạy, Claude tạo file thử (bước 2–3) và đọc kết quả.
- Commit, push, PR: Claude làm sau khi rà, theo lệnh PM. Docs (`tien_hoa_schema.md`, `phan_quyen.md` qua phiên phân quyền, kịch bản
  demo): Claude cập nhật sau nghiệm thu, hỏi PM trước.
- Đưa code lên Streamlit Cloud: Claude kiểm bản giả lập không duckdb trước, PM duyệt rồi mới merge vào nhánh deploy. Code đổi `apps/retail_app`, `scripts/ingest`
  nên chịu chung quy tắc đóng băng image như phiếu nhập UI §8 (thiết kế §8.7).

## 9. Rà của Claude (Claude ghi, GPT đọc để sửa)

| Lượt | Ngày | Kết quả | Phát hiện | Việc cho GPT |
|---|---|---|---|---|

## 10. Câu hỏi PM chốt trước khi giao

Đã chốt ở [thiet_ke_duong_tu_dong.md](thiet_ke_duong_tu_dong.md) §0 (2026-10-31): nguồn mới lần đầu DE duyệt; chạy ngay khi gửi, xếp
hàng khi bận; cột mới vẫn tự chạy, chờ nâng hợp đồng; validate đạt thì tự công bố. Không còn câu mở.
