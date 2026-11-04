# Giao việc T1: đường tự động cho dữ liệu nhập (gửi file → tự duyệt → tự chạy → tự công bố khi đủ điều kiện)

Soạn ngày 2026-10-31. PM duyệt thiết kế [thiet_ke_duong_tu_dong.md](thiet_ke_duong_tu_dong.md) cùng ngày; Claude soạn phiếu. GPT code
§3–§5; Claude rà độc lập trước khi commit theo 5 bước rà ở đầu [giao_viec_theo_so_do.md](giao_viec_theo_so_do.md). Chưa đạt thì
Claude ghi phát hiện vào §9, GPT sửa tiếp. Nghiệm thu thủ công §6 do PM chạy.

**Bắt đầu khi:** phiếu nhập UI ([giao_viec_nhap_du_lieu_ui.md](giao_viec_nhap_du_lieu_ui.md)) qua nghiệm thu §6 của nó. Phiếu này xây
trên luồng tay đã nghiệm thu, không thay nó.

Đọc trước:
- `AGENTS.md`, `CLAUDE.md`, `docs/agent_workflows.md`; skill `retail-platform-validation` (ingestion, publish gate), `retail-bi-product` (hai trang, trạng thái lỗi); `developing-with-streamlit` nếu công cụ của bạn có (skill này không nằm trong repo);
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
| `chua_ro_nguon` | `nguon.de_xuat` bằng `chua_ro` (dưới ngưỡng điểm/khoảng cách, `auto_mapping.py:64–68`), hoặc thiếu/rỗng |
| `chua_co_hop_dong` | `ung_vien` rỗng: nguồn này chưa có hợp đồng hiện hành nào (nguồn mới, lần đầu DE duyệt) |
| `thieu_cot` | có ứng viên nhưng **mọi** ứng viên đều có `cot_thieu` khác rỗng (file thiếu hoặc đổi tên cột **bắt buộc** của hợp đồng; cột `tuy_chon: true` không tính, §3.4); lý do liệt kê cột thiếu của ứng viên ít thiếu nhất, vd "File thiếu cột `comment` so với hợp đồng `orders_enriched` v1" |
| `nhieu_hop_dong` | hơn một ứng viên có `cot_thieu` rỗng |
| `doi_kieu` | cột loại `khop` có `khong_ep_duoc > 0` |
| `xung_dot_khoa` | `xung_dot_khoa.id_trung_khac_noi_dung > 0` hoặc `xung_dot_khoa.da_kiem` không phải `true` |
| `tham_chieu_thieu` | `tham_chieu_thieu` khác rỗng |
| `chua_co_model` | có đúng một ứng viên đủ cột và `co_model` sai. Không báo mã này ở ca `thieu_cot`, `chua_co_hop_dong`, vì lúc đó chưa biết file thuộc hợp đồng nào (Claude sửa 2026-11-02, T1-8) |

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
  mới** dùng lại đúng file đã tải lên của yêu cầu nguồn (sao chép vào `data/ui_nhap/<id_moi>/`, kiểm sha256 bằng nhau), ghi
  `nap_bu_tu: <id nguồn>`, rồi đi đường tự động với v<N+1>, không có nút bấm thêm. Mọi yêu cầu cũ không đổi (bất biến). **Mục này thắng
  thiết kế cũ "nút chạy lại yêu cầu cũ"; thiết kế §3.3 đã sửa theo (Claude chốt 2026-11-02).**
- **Yêu cầu nguồn của nạp bù** = yêu cầu đã công bố **ra đúng bản đang `active`** trong `state.json` (so `release_id` trong `chay/published.context.json` của yêu cầu với `payload.active`), không phải yêu cầu sinh ra
  đề xuất, vì mỗi lượt nạp thay toàn bộ phần mở rộng bằng file của lượt: nạp lại file khác bản đang phục vụ sẽ làm lùi dữ liệu. Khi chưa rollback, đây chính là yêu cầu đã công bố gần nhất. Nếu không tìm được yêu cầu đó, hoặc
  file của nó không có đủ các cột mới: **không tạo yêu cầu nạp bù**, vẫn ghi `v<N+1>`, trang Duyệt báo "Cột mới có hiệu lực từ lần gửi sau" và lý do. (Claude sửa 2026-11-02 sau lượt rà 1: bản cũ "đã công bố gần nhất" công bố lại đúng file Admin vừa rollback.)
- Đang có lượt chạy hoặc hàng đợi khác rỗng → **từ chối duyệt nâng hợp đồng trước khi ghi `v<N+1>`**, báo "Chờ lượt đang chạy xong rồi duyệt". Lý do: nạp bù xếp sau file mới hơn đang đợi sẽ đè lại bằng file cũ.
- "Silver" của phần mở rộng = file `orders_enriched.parquet` trong snapshot (`warehouse/pipeline/ui-nhap/snapshots/<snapshot_id>/`):
  prepare ghi mọi cột `khoa_noi`/`nap` (`extension_contract.loaded_columns`, `extension_contract.py:81–84`); `stg_orders_enriched.sql`
  chọn cột tường minh nên cột mới không đi tiếp. Không cần sửa `retail_dbt/` cho cột mới ở silver.
- Cột mới chỉ lên mart khi model dbt có cột đó; chưa có thì cổng `validate_extension_visibility` xử lý như hiện nay (cột `mart` không
  có trong mart → lỗi). Hợp đồng bất biến, không có đường hạ `mart` về `silver`, nên `upgrade_contract` **từ chối** ghi `v<N+1>` khi có cột `mart` mà model chưa có; form mặc định `silver`. (Claude sửa 2026-11-02: cảnh báo cũ không kịp hiện, xem T1-4 ở §9.)
  "Model có cột" nghĩa là cột là **đầu ra của một model trong `retail_dbt/models/marts/`** có `extension_enabled('<ten>')`, không phải tên đó xuất hiện đâu đó trong file SQL. Không xác định được thì coi là chưa có (T1-12).
- **Thứ tự nâng hợp đồng (Claude sửa 2026-11-02, T1-13):** kiểm bận, kiểm cột, tìm và kiểm file nguồn → ghi nhật ký → ghi `v<N+1>` → tạo yêu cầu nạp bù. Lỗi trước khi ghi `v<N+1>`: báo lỗi, giữ v<N>. Lỗi sau khi đã ghi: không ném lỗi như thể chưa làm gì; ghi thông báo "Cột mới có hiệu lực từ lần gửi sau" kèm lý do.
- **Cột thêm qua nâng hợp đồng không bắt buộc (PM chốt 2026-11-02, T1-18):**
  - `upgrade_contract` ghi `tuy_chon: true` cho cột `silver` và cột `bo`. Cột gốc của v1 và cột `mart` vẫn bắt buộc; cột `mart` bắt buộc vì model dbt đọc nó, file thiếu thì lượt `build` hỏng.
  - `ung_vien` không tính cột `tuy_chon` vào `cot_thieu`. File thiếu cột đó vẫn `tu_dong`; `hop_dong_cua_luot` bỏ cột khỏi hợp đồng của lượt như hiện nay.
  - `phan_loai` trả thêm `cot_tuy_chon_thieu`; trang Gửi và Duyệt báo "File không có cột `<ten>`; bản dữ liệu này sẽ không có cột đó".
  - Mỗi lượt thay toàn bộ phần mở rộng, nên công bố file thiếu cột thì snapshot mới không có cột đó; snapshot cũ giữ nguyên. File sau có lại cột thì nạp bình thường, không cần duyệt lại.
  - Đổi tên cột tùy chọn được xử lý như thiếu cột đó và có cột mới: vẫn tự chạy, có đề xuất nâng hợp đồng cho tên mới.
- DE từ chối nâng hợp đồng → ghi lý do; cột mới tiếp tục bị `bo` ở các lần gửi sau (vẫn tự động), mục đề xuất không hiện lại cho
  đúng tập cột đó.

### 3.5 Hàng đợi

- `warehouse/ui_nhap/hang_doi/`: mỗi mục một file `<thời điểm>_<id>.json`, FIFO theo tên. Thêm/lấy dưới khóa `dispatch` hiện có, thử lấy khóa tối đa 10 giây như `worker_slot`. **Ngoại lệ duy nhất (Claude sửa 2026-11-02, T1-5):** hết 10 giây vẫn bận thì vẫn thêm mục bằng `atomic_json` với tên duy nhất, ngoài khóa, và bỏ bước khởi động; trang hoặc worker kế sẽ chạy nó. Lấy và xóa mục luôn dưới khóa. Một mục hỏng không được chặn cả hàng đợi. **Lỗi vĩnh viễn** (file yêu cầu không còn, JSON hỏng, thiếu trường, chưa có model dbt): bỏ mục, ghi nhật ký, chạy tiếp mục sau. **Lỗi tạm thời** (tranh chấp file, khóa của yêu cầu đang bận): thử lại tại chỗ tối đa 10 giây như `retry_lock`; vẫn lỗi thì giữ mục, dừng lượt khởi động này để giữ đúng FIFO, trang hoặc worker kế sẽ chạy tiếp. Phân biệt bằng loại ngoại lệ, không dựa vào nội dung thông báo. (Claude sửa 2026-11-03, T1-20; câu cũ "hoặc đọc không được" của Claude quá rộng.) `OSError` khác cũng là lỗi tạm thời, không được ném lên trang. Riêng khi không tạo được tiến trình: yêu cầu đã thành `loi` nên bỏ mục đó, ghi nhật ký và **dừng lượt khởi động này**; mục sau giữ nguyên thứ tự và chạy ở lần kích hoạt kế. Không chạy ngay mục sau, vì khi máy đang thiếu bộ nhớ cả hàng đợi sẽ thành `loi` dây chuyền. Xóa mục hàng đợi cũng phải chịu được việc file đang mở. (Claude thêm 2026-11-03, T1-24, T1-25; bản sửa §3.5 trước của Claude chưa nói tới hai ca này.) **Chỉ thử lại lỗi xảy ra trước khi `_start_locked` ghi bất cứ thứ gì** (đọc mục, đọc yêu cầu, vào `store.locked`). Từ lần ghi đầu tiên trở đi (nhật ký, marker, `dang_chay`), lỗi nào cũng không thử lại và **dừng lượt**, không chạy mục sau; yêu cầu không được kẹt `dang_chay` khi đã mất marker. (Claude sửa 2026-11-03, T1-26, T1-27; câu "`OSError` khác cũng là lỗi tạm thời" của Claude chưa nói tới việc thử lại sau khi đã ghi.)
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

- Lượt của yêu cầu `duong: 'tu_dong'` **do `he_thong` khởi động** (`nguoi_chay == 'he_thong'`) tới `da_kiem` → worker công bố ngay, người `he_thong`. Lượt do người bấm "Chạy"/"Chạy lại để kiểm" dừng ở `da_kiem` chờ Admin, kể cả yêu cầu `tu_dong` (Claude sửa 2026-11-02, T1-2).
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
  hiện lại đề xuất cho cùng tập cột. Thêm ba ca của yêu cầu nguồn: đề xuất sinh từ yêu cầu A nhưng yêu cầu B công bố sau → nạp bù dùng file của B;
  file của B không có cột mới → không tạo yêu cầu, v2 vẫn ghi, có thông báo; chưa có yêu cầu nào công bố → như vậy.
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
2b. Sau bước 2, `chushop` gửi lại file 2022 **gốc, không có `bonus`** → vẫn "Tự động" và tự công bố; trang báo file không có cột `bonus`. Claude kiểm parquet của lượt đó không có `bonus`, mart vẫn đủ 36.004 đơn có nhân viên. (PM chốt 2026-11-02.)
3. Gửi file thiếu cột `comment` (Claude tạo) → "Chờ đội dữ liệu", lý do có "thiếu cột `comment`", không có `bonus` vì cột này không bắt buộc (PM chốt 2026-11-02); gửi `epd.json` → "Chờ đội dữ liệu",
   lý do xung đột khóa hoặc chưa có hợp đồng; cả hai không tự chạy. Với yêu cầu thiếu cột, `de1` mở bảng duyệt cột: bấm đúp ô
   Kiểu thấy danh sách `string / integer / date / double`, không gõ chữ được (§3.11).
4. Gửi hai lần liền nhau **file có `bonus` của bước 2** → chạy lần lượt, không ai bấm; trang Gửi hiện yêu cầu thứ hai "Đang xếp hàng (thứ 1)" (thứ tự tính trong hàng đợi, không tính lượt đang chạy).
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

**Lượt 1, 2026-11-02: Chưa đạt.** Lõi đường tự động chạy đúng, nhưng nút Rollback không dùng được, DE có đường công bố thay Admin, và nạp bù có thể làm lùi dữ liệu.

**Đã kiểm và đúng (không cần sửa):**
- Chạy lại: 82 test của phiếu đều đạt.
- File thật qua `auto_mapping.propose`:
  - `demo_2022/orders_enriched.csv` và bản đổi tên file → `tu_dong`.
  - Thêm `bonus` → `tu_dong`, `cot_moi=['bonus']`.
  - Thiếu hoặc đổi tên `comment` → `thieu_cot`, đúng tên cột.
  - `epd.json`, `tf.json`, `eprom.json`, `shipments_realistic.csv` → `can_nguoi`.
  - Cả header viết hoa → phân loại `tu_dong` nhưng `load` từ chối; code đưa về `can_nguoi`, đúng hướng an toàn.
- Hợp đồng của lượt qua `prepare` thật 36.004 dòng (gốc, thêm cột, đảo thứ tự); `bonus` không có trong parquet; `thuc_the`, `khoa_noi`, `nguong_cach_ly` giữ nguyên.
- Worker thật trên bản sao, CLI giả: 3 yêu cầu chạy đúng FIFO, không chồng stage, người thao tác là `he_thong`, nhật ký rơi về `nhat_ky_cho.jsonl` khi không có Neon. Giết worker giữa chừng: yêu cầu thành `loi`, mục kế chạy khi có người mở trang.
- Hồi quy: trên cùng bản sao kho local cũ và cùng `data/`, `test_roles`, `test_smoke`, `test_khong_hardcode`, `test_ban_phuc_vu` ra 79 đạt, 3 skip ở cả T1 và bản trước T1.
- Test rộng `apps/retail_app/tests` + `scripts` không có kho: T1 789 đạt, 578 trượt, 607 skip; không test nào từ đạt thành trượt so với bản trước T1. Đối chứng này yếu hơn: bản trước T1 chạy thiếu cả `data/` (598 trượt/lỗi). Các test trượt ở `test_roles` giống hệt thông báo ở hai bản và đạt khi có kho. Các file test còn lại chưa chạy với kho.

**Chưa kiểm được ở lượt này:** `roles.store()` trong worker với Neon thật (§6 bước 6); pipeline đầy đủ (§6).

| Mã | Mức | Phát hiện (Claude đã chạy thử, trừ chỗ ghi khác) | Việc cho GPT |
|---|---|---|---|
| T1-1 | **Cao** | Rollback chết ở cả hai đầu. `rollback_options` (`nhap_runner.py:402`) đọc `state.releases`, trong khi file thật là `payload.releases` (`state.py:57`, thử trên `warehouse/pipeline/ui-nhap/state.json` ra rỗng), nên form không hiện bản nào. `rollback_command` (`:393`) thiếu `--run-id`, CLI thoát với "cần --run-id" (`cli.py:534`). Test chỉ kiểm `--target`, `--root` | Đọc `payload`. Thêm `--run-id` dạng `ui-rollback-<utc>` hợp `[a-zA-Z0-9_-]{1,100}`. Test chạy CLI thật trên `state.json` tạm có hai bản `ready`, kiểm `active` đổi thật. **Claude không xác định được hết các điều kiện `checked`/`verify_consumers` trên DuckDB; nếu CLI còn lỗi khác, báo lại** |
| T1-2 | **Cao** | DE công bố thay Admin và làm lùi dữ liệu. Yêu cầu `duong: tu_dong` ở `da_cong_bo` hoặc `loi`, DE bấm "Chạy lại để kiểm"/"Chạy" → worker tự công bố (`nhap_runner.py:339`). PM đã chốt công bố tay chỉ Admin; file cũ chạy lại sẽ thay bản đang phục vụ. Thử: kết quả `da_cong_bo`, người cuối `he_thong` | Chỉ tự công bố khi `duong == 'tu_dong'` **và** `nguoi_chay == 'he_thong'`. Lượt do người bấm dừng ở `da_kiem` chờ Admin. Test cả hai trạng thái đầu |
| T1-3 | **Cao** | Nạp bù làm lùi dữ liệu trong hai ca, **do phiếu của Claude thiếu quy tắc, không phải GPT làm sai** (đã sửa §3.4). (a) Admin rollback từ B về A rồi DE duyệt nâng hợp đồng → nạp bù dùng file B vừa bị rollback và tự công bố. (b) File C mới hơn đang đợi → nạp bù từ B xếp sau C, cuối cùng đè lại bằng B | Làm theo §3.4 mới: nguồn là yêu cầu ra đúng `payload.active`; đang chạy hoặc hàng đợi khác rỗng thì từ chối trước khi ghi `v<N+1>`. Test hai ca |
| T1-4 | **Cao** | Chọn `mart` cho cột chưa có model thì mọi lượt sau hỏng. Cảnh báo ở `duyet_du_lieu.py:212` không kịp hiện (Claude đọc code, không thử trên UI): `data_editor` nằm trong form nên chỉ đổi lúc bấm Duyệt, và `upgrade_contract` + `st.rerun()` chạy ngay sau đó. `upgrade_contract` vẫn ghi v2 (đã thử). Hợp đồng bất biến, nên mỗi file sau chạy ~7 phút† rồi trượt `validate`, không có đường hạ về `silver` | Theo §3.4 mới: `upgrade_contract` kiểm `has_dbt_column` và ném lỗi trước khi ghi, nêu tên cột. Test: v1 giữ nguyên |
| T1-5 | Trung bình | Gửi file trúng lúc khóa `dispatch` đang bận thì yêu cầu bị bỏ rơi. `enqueue` (`nhap_runner.py:265`) ném `ValueError` sau khi đã tự duyệt: `da_duyet`, không có mục hàng đợi, không gì khởi động lại; người gửi thấy lỗi "phiên khác đang xử lý" | Thử lấy khóa tối đa 10 giây như `worker_slot`. Vẫn bận thì vẫn ghi mục hàng đợi (tên duy nhất, `atomic_json`), chỉ bỏ bước khởi động; trang hoặc worker kế sẽ chạy nó. Test giữ khóa lúc `submit` |
| T1-6 | Trung bình | Worker xong đúng lúc `dispatch` bận thì mục kế nằm im tới khi có người mở trang (`nhap_runner.py:304–307` nuốt lỗi). Trái mục tiêu "không ai bấm" | Thử lại như T1-5. Test giữ khóa lúc worker kết thúc |
| T1-7 | Trung bình | `log_event` (`nhap_store.py:291`) ném `PermissionError` khi `nhat_ky_cho` bận: một lỗi ghi nhật ký có thể biến lượt công bố thành `loi`. `sync_events` giữ khóa suốt lúc gọi Neon nên càng dễ trúng; trang Duyệt chỉ bắt `ValueError` (`duyet_du_lieu.py:27`) | Thử lại lấy khóa. `sync_events` đọc xong nhả khóa rồi mới gọi Neon, ghi lại phần còn lại dưới khóa. Trang bắt cả `OSError`. Test giữ khóa |
| T1-8 | Trung bình | Lý do sai cho Quản lý. File thiếu cột ra thêm "Nguồn này chưa có mô hình báo cáo" (`nhap_store.py:183` cho `model=False` khi không có ứng viên đủ cột), dù `orders_enriched` có model. Đã thấy trên file thật | `chua_co_model` chỉ xét khi có đúng một ứng viên đủ cột; `phan_loai` không báo mã này ở ca `thieu_cot`, `chua_co_hop_dong`. Test: thiếu cột chỉ còn `thieu_cot` |
| T1-9 | Trung bình | Test yếu: Claude thử 58 đột biến, **26 lọt** (32 bắt được, gồm 5 đột biến cùng loại GPT đã báo). Có ca §5 đòi rõ mà chưa có: `hop_dong_cua_luot` "tương đương" (bỏ `thuc_the`, đổi `nguong_cach_ly`, giữ `file` cũ đều lọt), `he_thong` không dùng tên người gửi | Thêm test cho danh sách lọt bên dưới. Đột biến nào tương đương thật thì ghi lý do vào báo cáo |
| T1-10 | Thấp | `queue_position` (`nhap_runner.py:180`) ném `FileNotFoundError` nếu mục vừa bị xóa sau khi liệt kê: lỗi đỏ trên trang Gửi/Duyệt khi tới lượt | Bỏ qua file biến mất. Test |
| T1-11 | Thấp | `auto_approve` chỉ xét `phan_loai.ket_qua` (`nhap_store.py:213`): sau Duyệt lại, `ket_qua` vẫn `tu_dong` trong khi `duong` là `tay`. Hiện không có đường gọi, nhưng §3.3 đòi chặn. `approve` sau Duyệt lại giữ `hop_dong`, `cot_moi` cũ nên trang Duyệt vẫn ghi "Hợp đồng v1" cho lượt chạy tay (Claude đọc code) | Xét thêm `duong`. `approve` bỏ `hop_dong`, `cot_moi` khỏi record. Test |

**26 đột biến lọt (T1-9):**
- `phan_loai`: bỏ kiểm `da_kiem`; chọn ứng viên thiếu nhiều nhất thay vì ít nhất.
- `hop_dong_cua_luot`: giữ `file` cũ; `thuc_the=[]`; đổi `nguong_cach_ly`; `duyet_boi` không phải `he_thong`.
- Kho hợp đồng: `vN.yml` ghi đè được (`xb`→`wb`); bỏ kiểm sha lúc đọc; `ung_vien` không lọc theo nguồn.
- `auto_approve`: bỏ kiểm phiên bản hợp đồng; ghi tên người gửi thay `he_thong`; bỏ `extension_contract.load` trước khi lưu.
- `approve`: duyệt tay cho tên đã có hợp đồng vẫn ghi đè hiện hành; lần đầu không ghi v1.
- Nâng hợp đồng: bỏ kiểm sha file nạp bù (có hai lớp kiểm, có thể tương đương); bỏ kiểm "đúng các cột mới"; bỏ kiểm phiên bản đã đổi.
- Runner: `enqueue` nhận yêu cầu tay; `start` bỏ kiểm hàng đợi; `_kick_locked` chạy mục hết `da_duyet`; hàng đợi LIFO; công bố lỗi không về `loi`; `rollback` bỏ kiểm hàng đợi; `rollback_options` có cả bản `active`.
- Gợi ý kiểu: bỏ điều kiện PII (test hiện chỉ dùng số điện thoại có số 0 đầu, nên quy tắc số 0 đỡ thay); `default_decisions` bỏ `kieu_goi_y`.

Phép thử của Claude: `C:\Users\Win\AppData\Local\Temp\claude\D--retail-analytics\a77be869-4ff6-44d6-a768-5c3ad202cec8\scratchpad\t1_probe.py` (11 test viết theo hành vi đúng, hiện đều trượt; đọc để hiểu ca lỗi, viết test của phiếu vào repo). Không chạy pipeline đầy đủ, không commit. Sửa xong báo lại số test; Claude chạy lại đúng các phép thử này và bộ đột biến.

**Lượt 2, 2026-11-02: Chưa đạt, còn ít việc.** T1-1…T1-11 đã sửa đúng. Còn một lỗi nặng sót lại từ T1-4 và vài lỗi nhỏ hơn.

**Đã kiểm và đúng (không cần sửa):**
- Chạy lại: 129 test của ba file đều đạt; 11/11 phép thử lượt 1 của Claude đạt (`t1_probe.py`; phép F1 đổi theo chữ ký `rollback_command(release_id, run_id)`, chấp nhận).
- Rollback: CLI thật chạy trên bản sao `warehouse/pipeline/ui-nhap`, bản ghi thật `e099b42b…`, qua `checked` + `verify_consumers`, mã thoát 0, có dòng lịch sử. Vì kho thật chỉ có một bản nên phép này khôi phục về chính bản đang active; đổi `active` thật giữa hai bản do test của GPT phủ trên DuckDB tạm, và §6 bước 5 sẽ kiểm trên kho thật.
- Worker thật, CLI giả: 3 yêu cầu đúng FIFO, 18 giây, tối đa 1 stage cùng lúc, người thao tác `he_thong`; giết worker → `loi`, mục kế chạy khi có người mở trang.
- File thật: phân loại như lượt 1. `prepare` thật 36.004 dòng (gốc, thêm cột, đảo thứ tự, `Comment`), `bonus` không vào parquet.
- Hồi quy trên cùng bản sao kho và `data/`: `test_roles`, `test_smoke`, `test_khong_hardcode`, `test_ban_phuc_vu` ra 79 đạt, 3 skip ở cả T1 và bản trước T1.
- 26 đột biến lọt ở lượt 1 nay đều bị bắt (Claude chạy lại độc lập, khớp báo cáo của GPT).

**Chưa kiểm được ở lượt này:** `roles.store()` trong worker với Neon thật; pipeline đầy đủ; thao tác thật trên giao diện (§6). Bộ test rộng `apps/retail_app/tests` + `scripts` của lượt 2 bị hệ thống dừng vì máy thiếu RAM, chưa có kết quả; không dùng số của lượt 1 thay cho lượt này.

| Mã | Mức | Phát hiện (Claude đã chạy thử, trừ chỗ ghi khác) | Việc cho GPT |
|---|---|---|---|
| T1-12 | **Cao** | Cổng chặn `mart` của T1-4 nhận nhầm. `has_dbt_column` (`approval.py:66`) chỉ tìm tên cột trong toàn bộ file SQL có `extension_enabled`, kể cả staging, Jinja, từ khóa. Trên model thật ra True với `source`, `raw`, `id`, `select`, `integer`, `clean`, `marital_status`, trong khi mart thật không có các cột này. Thử `upgrade_contract` với `source` chọn `mart`: ghi v2. Đọc `cli.py:183–186`: mỗi lượt sau trượt `validate` vì thiếu cột mart, tức đúng hậu quả của T1-4, không có đường hạ về `silver`. Test hiện đều thay hàm này bằng hàm giả: đột biến "luôn đúng" và "bỏ marker" đều lọt | Theo §3.4 mới. Gợi ý cách làm (Claude đã thử bản phác thảo này khớp đủ danh sách dưới): chỉ xét `models/marts/` có marker; bỏ Jinja và chú thích; cột phải là đầu ra (`as <cột>` hoặc đứng riêng một dòng trong danh sách select); tên trùng từ khóa SQL hoặc tên kiểu thì coi là chưa có. Cách làm tùy GPT, **danh sách sau mới là tiêu chí**. Test trên model thật của repo: **đúng** với `sales_employee_id`, `sales_employee_name`, `sales_employee_sk`, `years_experience` (4 cột có thật trong mart); **sai** với `bonus`, `source`, `raw`, `id`, `clean`, `select`, `integer`, `comment`, `marital_status`, `education_level` |
| T1-13 | Trung bình | `v<N+1>` ghi xong rồi mới kiểm file nguồn và ghi nhật ký (`nhap_store.py:454–475`). Thử: file nguồn sai sha → DE thấy lỗi nhưng v2 đã ghi; Neon lỗi → DE thấy lỗi, v2 đã ghi mà nhật ký không có dòng nào. Bấm lại thì báo "Phiên bản đã đổi", không còn đường nạp bù | Theo thứ tự §3.4 mới. Test hai ca: lỗi trước khi ghi giữ v1. Lỗi khi tạo nạp bù sau khi ghi: có thông báo, không ném lỗi |
| T1-14 | Trung bình | Mục hàng đợi trỏ tới yêu cầu đã bị xóa làm **kẹt cả hàng đợi**. Thử: `recover_queue` ném `FileNotFoundError` mỗi lần, mục không bị bỏ, `busy_reason` báo "Đang có 1 yêu cầu" mãi nên `start` (`nhap_runner.py:238–240`) bị chặn theo. Trang Gửi chỉ bắt `ValueError` (`gui_du_lieu.py:24`) nên đọc code thấy cả trang sẽ lỗi đỏ. Xảy ra khi dọn tay dữ liệu thử | Theo §3.5 mới. Bắt thêm `OSError` ở trang Gửi. Test: mục hỏng đứng đầu, mục sau vẫn chạy |
| T1-15 | Trung bình | Test còn yếu: Claude thử 95 đột biến (gồm đột biến mới cho phần vừa sửa), **14 lọt**. Quan trọng nhất: bỏ giữ `dispatch` khi nâng hợp đồng; `rollback` bỏ kiểm đang chạy; nạp bù xếp cả yêu cầu cần người; hai đột biến `has_dbt_column` ở T1-12 | Thêm test cho danh sách bên dưới. Đột biến tương đương thật thì ghi lý do vào báo cáo |
| T1-16 | Thấp | Nâng hợp đồng lâu hơn 10 giây thì file mới C ghi hàng đợi ngoài khóa rồi nạp bù xếp sau C, dữ liệu lùi về file cũ. Thử bằng `propose` giả 11 giây. File thật 36.004 dòng mất 3,5 giây nên khó trúng; chưa đo file gần 200 MB | Kiểm lại hàng đợi ngay trước khi xếp nạp bù; có mục mới thì không xếp, báo "Cột mới có hiệu lực từ lần gửi sau" |
| T1-18 | **Đổi thiết kế** | PM chốt 2026-11-02: cột thêm qua nâng hợp đồng không bắt buộc. Hiện `ung_vien` tính mọi cột trong `header`, nên sau v2 file thiếu `bonus` ra `thieu_cot`. Đây không phải lỗi của GPT, phiếu cũ viết như vậy. Claude thử trên bản sao: hợp đồng v2 có `bonus` silver, qua `hop_dong_cua_luot` + `load` + `prepare` thật 36.004 dòng, 0 cách ly, file thiếu và file có `bonus` đều chạy được; parquet có `bonus` đúng theo file. Vậy `prepare` không phải sửa | Làm theo §3.4 mới. Test: file thiếu `bonus` silver → `tu_dong`, có `cot_tuy_chon_thieu`; thiếu cột `bo` → `tu_dong`; thiếu cột `mart` hoặc cột v1 → `thieu_cot`; file có lại `bonus` → parquet có cột, không có `cot_moi`. Không sửa `extension_prepare.py` |
| T1-17 | Thấp | `recover_queue` ở đầu trang Gửi/Duyệt chờ khóa tới 10 giây (đo được 10,0 giây). Khóa bận suốt lúc Admin công bố hoặc rollback, nên mọi lần tải trang của người khác đứng 10 giây | Trang gọi không chờ, bận thì bỏ qua; worker vẫn chờ. Test |

**14 đột biến lọt (T1-15), Claude phân loại sơ bộ:**
- Cần test: `upgrade_contract` không giữ `dispatch`; `rollback` bỏ kiểm đang chạy; `rollback_options` bỏ lọc `ready`; `rollback_command` bỏ kiểm `release_id`; nạp bù trả mã cả khi yêu cầu không ở `da_duyet`; `has_dbt_column` luôn đúng; `has_dbt_column` bỏ marker.
- Nên có test, rẻ: tự công bố bỏ điều kiện `duong` (lượt `he_thong` với `duong: tay` phải dừng ở `da_kiem`); `approve` không đặt `duong='tay'`; từ chối `mart` áp cả cột `bo`.
- Có thể tương đương, GPT xem và ghi lý do: chọn `min` thay `max` khi nhiều yêu cầu ra cùng bản `active`; bỏ nhánh `if not active`; giữ `hop_dong_sha256` cũ trước khi ghi (đọc lại sẽ tính lại sha); `sync_events` bỏ kiểm đổi đầu file (đã có khóa `nhat_ky_dong_bo`).

Phép thử của Claude: `C:\Users\Win\AppData\Local\Temp\claude\D--retail-analytics\a77be869-4ff6-44d6-a768-5c3ad202cec8\scratchpad\t2_probe.py` (8 ca, hiện đều trượt) và `t2_that.py` cùng thư mục. Đọc để hiểu ca lỗi, viết test của phiếu vào repo. Không chạy pipeline đầy đủ, không commit. Sửa xong báo lại số test; Claude chạy lại các phép thử và bộ đột biến.

**Lượt 3, 2026-11-02: Chưa đạt, không còn lỗi Cao.** T1-12…T1-18 đã sửa đúng. Còn hai lỗi Trung bình về độ bền của hàng đợi trên Windows và hai lỗi Thấp.

**Đã kiểm và đúng (không cần sửa):**
- Worker thật, CLI giả, chạy lại 5 lần khi máy còn khoảng 4,4 GB RAM: cả 5 lần đều 3/3 `da_cong_bo`, 14–15 giây, không còn `loi`; giết worker thì yêu cầu thành `loi`, mục kế chạy khi có người mở trang.
- Hồi quy trên cùng bản sao kho và `data/`: `test_roles`, `test_smoke`, `test_khong_hardcode`, `test_ban_phuc_vu` ra 79 đạt, 3 skip ở cả T1 và bản trước T1.
- 188 test của ba file đạt; 19/19 phép thử của Claude đạt (11 ca lượt 1, 8 ca lượt 2 trước đó trượt).
- `has_dbt_column` trên model thật: đúng 4 cột mart, sai cả 10 tên trong tiêu chí, thêm `left`, `e`, `s`, `o`, `customer_id`, `order_date` cũng sai.
- Chuỗi thật `t3_flow.py` trên thư mục tạm, `propose` + kho hợp đồng + `upgrade_contract` + `prepare` thật 36.004 dòng, 0 cách ly:
  - File có `bonus` với v1: `tu_dong`, `cot_moi=['bonus']`, parquet không có `bonus`.
  - DE duyệt `bonus` silver: v2, `tuy_chon: true`, nạp bù từ đúng yêu cầu nguồn, parquet có `bonus`.
  - File gốc không có `bonus`: `tu_dong`, `cot_tuy_chon_thieu=['bonus']`, parquet không có `bonus`. Gửi lại file có `bonus`: nạp lại, không cần duyệt.
  - Thiếu `comment`: chỉ báo thiếu `comment`. Đổi tên `bonus` thành `thuong`: `tu_dong`, có đề xuất cột mới, báo thiếu `bonus`. Chọn `mart` cho `thuong`: bị chặn, giữ v2.
- Đột biến có mục tiêu: 42 đột biến (12 trong 14 đột biến lọt lượt 2, cộng 30 mới; 2 đột biến `has_dbt_column` cũ được thay bằng bản nhắm vào code mới), 34 bắt được, 1 không áp được vì đoạn code đã viết lại (GPT báo đã có test riêng), 7 lọt. Claude chấp nhận 6/7:
  - Tương đương: giữ `hop_dong_sha256` cũ (`load` luôn tính lại, đúng như GPT nêu); báo cả cột bắt buộc ở `cot_tuy_chon_thieu` (đã `complete` thì không thiếu cột bắt buộc); `recover_queue` đổi mặc định (mọi nơi gọi đều truyền rõ).
  - Có lớp đỡ: bỏ `reserved`, bỏ `depth == 0` ở `select`, bỏ `depth == 0` ở dấu phẩy.
  - Còn lại thiếu test: xem T1-22.

**Chưa kiểm được ở lượt này:** bộ test rộng `apps/retail_app/tests` + `scripts` chưa chạy trên code lượt 3; PM sẽ chạy ngoài Claude Code sau khi GPT sửa xong. `roles.store()` với Neon thật; pipeline đầy đủ; giao diện thật (§6).

| Mã | Mức | Phát hiện (Claude đã chạy thử, trừ chỗ ghi khác) | Việc cho GPT |
|---|---|---|---|
| T1-19 | Trung bình | Trên Windows, `os.replace` thất bại khi có tiến trình đang mở file đích. `atomic_json` (`scripts/pipeline/state.py:46`) không thử lại, nên ghi `yeu_cau.json` trùng lúc có người đọc sẽ ném `PermissionError`. **Đã chứng minh cơ chế:** `t3_doc_giua.py` giữ file mở lúc khởi động → yêu cầu kẹt `da_duyet`, mục hàng đợi mất. Phép này giữ file mở có chủ đích, còn lần đọc thật chỉ rất ngắn, nên chưa đo được tần suất ngoài thực tế. **Chưa chứng minh đây là nguyên nhân của lần trượt:** một lần `t1_e2e.py` cho `['da_cong_bo', 'loi', 'da_cong_bo']` khi máy còn khoảng 1,6 GB RAM, thư mục tạm đã xóa nên không đọc được thông báo lỗi. Dấu vết (4 dòng `nhap_xep_hang`) cho thấy lỗi nằm trong khối khởi động của `_start_locked`; có thể do `PermissionError` hoặc do không tạo được tiến trình vì thiếu RAM. Chạy lại 5 lần với khoảng 4,4 GB RAM không gặp lại. Lần đó hệ thống vẫn an toàn: yêu cầu báo `loi`, mục sau chạy tiếp, không công bố sai. Đọc code: nếu rơi vào bước ghi sau `publish` thành công (`_publish_core`), dữ liệu đã công bố nhưng yêu cầu ghi `loi` | Sửa ở một chỗ: `atomic_json` thử lại tối đa 10 giây, **chỉ khi `os.name == 'nt'` và là `PermissionError` có `winerror` 5 hoặc 32**, để Airflow/Databricks trên Linux không đổi hành vi. Báo riêng số test của `scripts/pipeline/tests`. Đọc `yeu_cau.json`, `state.json`, mục hàng đợi trong `nhap_store`/`nhap_runner` cũng thử lại `PermissionError`. Test: luồng phụ giữ file mở 1 giây lúc `save` → ghi được, yêu cầu chạy tiếp. Lỗi ghi sau khi CLI `publish` thành công: thông báo nói rõ đã công bố nhưng chưa ghi được trạng thái. `scripts/pipeline` nằm trong băm `code_version`, nhưng T1 đã đổi `scripts/ingest` và `apps/` cũng trong băm; image đang đóng băng nên lịch 08:00 không đổi |
| T1-20 | Trung bình | `_kick_locked` bỏ hẳn mục cả khi lỗi chỉ tạm thời, **do câu "hoặc đọc không được" trong §3.5 của Claude quá rộng, GPT làm đúng theo phiếu** (đã sửa §3.5). Phép thử `t3_probe.py`: `PermissionError` một lần lúc đọc yêu cầu → mục mất, yêu cầu nằm `da_duyet` không ai chạy (test A). Khóa riêng của yêu cầu đang bận → như vậy (test B). `store.locked` đổi khóa bận thành `ValueError`, cùng loại với "chưa có model dbt", nên hiện chưa phân biệt được hai ca | Theo §3.5 mới. Tách loại ngoại lệ để phân biệt tạm thời và vĩnh viễn (có thể thêm lớp con của `ValueError` để nơi gọi cũ không đổi). Test: lỗi tạm thời một lần → thử lại và chạy được; lỗi kéo dài → mục còn, thứ tự giữ nguyên, mục sau không chạy trước; giữ test mục hỏng của T1-14 |
| T1-21 | Thấp | Nạp bù bị hủy vì có mục mới xen vào (T1-16) vẫn để lại yêu cầu nạp bù `da_duyet` (`t3_probe.py` test E). DE bấm Chạy là dựng file cũ; lượt đó dừng chờ Admin nên chưa lùi dữ liệu nếu Admin không công bố | Kiểm hàng đợi thêm một lần trước `self.create`, giảm khe hở. Trang Duyệt ghi rõ "Yêu cầu nạp bù đã bị hủy, không chạy" nếu yêu cầu `nap_bu_tu` còn `da_duyet` mà không có mục hàng đợi |
| T1-22 | Thấp | Đột biến bỏ `extension_contract.load` trước khi ghi lọt: `registry.write` vẫn chặn, nhưng khi đó nhật ký đã có dòng nâng hợp đồng mà v2 không được ghi | Test: `kieu` sai → `ValueError`, giữ v1, không có dòng nhật ký |

Phép thử của Claude, cùng thư mục `C:\Users\Win\AppData\Local\Temp\claude\D--retail-analytics\a77be869-4ff6-44d6-a768-5c3ad202cec8\scratchpad\`: `t3_doc_giua.py`, `t3_probe.py` (3/5 ca trượt: A, B, E), `t3_flow.py`, `t1_e2e.py`. Chỉ đọc, không sửa. Không chạy pipeline đầy đủ, không commit. Sửa xong báo lại số test; Claude chạy lại, trong đó chạy `t1_e2e.py` nhiều lần vì lỗi tranh chấp không xảy ra mỗi lần.

**Lượt 4, 2026-11-03: Chưa đạt, không còn lỗi Cao.** T1-19…T1-22 đã sửa đúng. Phép thử mới của Claude phát hiện hai lỗi Trung bình và một lỗi Thấp, chủ yếu ở các nhánh lỗi; đường chạy bình thường vẫn đúng.

**Đã kiểm và đúng (không cần sửa):**
- Claude tự chạy lại 217 test của bốn file `test_state_io`, `test_tu_dong`, `test_nhap_tu_dong`, `test_nhap_du_lieu`: 217 đạt.
- Phép thử lượt 1–3: 23/24 đạt. Ca còn lại là `t3_probe.py` test E, do phép thử của Claude đòi nghiêm hơn phiếu (đòi đổi trạng thái). GPT làm đúng T1-21: giữ `da_duyet`, cảnh báo, chặn Chạy; Claude đã kiểm bằng `t4_probe.py` test `e2`.
- `t3_doc_giua.py`: giữ file mở lúc khởi động, yêu cầu còn `da_duyet`, mục hàng đợi còn; trước đây mục bị mất.
- Chuỗi thật `t3_flow.py`, `prepare` thật 36.004 dòng, 0 cách ly: kết quả như lượt 3.
- Worker thật, CLI giả, chạy 6 lần: cả 6 lần nhật ký có đủ 3 lần công bố, không có dòng xếp hàng thừa; lần in đủ cho thấy 3/3 `da_cong_bo`, đúng FIFO, 15 giây, mỗi lúc một stage. Giết worker: yêu cầu thành `loi`, mục sau chạy khi mở trang.
- Hồi quy trên bản sao kho (`test_roles`, `test_smoke`, `test_khong_hardcode`, `test_ban_phuc_vu`): 79 đạt, 3 skip ở cả T1 và bản trước T1.
- Claude tự chạy `scripts`, gồm phần `state.py` dùng chung với pipeline: 301 đạt, 3 skip; riêng `scripts/pipeline/tests` 99 đạt, 2 skip; khớp số GPT báo.
- Đọc code, chưa chạy: sau `PublishedStateError` yêu cầu giữ `da_kiem`; Admin bấm Công bố lại thì CLI trả về ngữ cảnh `published` có sẵn (`cli.py:405`) nên yêu cầu thành `da_cong_bo`.
- GPT đổi kỳ vọng `test_atomic_failure_keeps_previous` từ `ValueError` sang `OSError`: chấp nhận, vì test vẫn kiểm file cũ nguyên vẹn.
- Đột biến độc lập: 23 đột biến ngoài 7 đột biến GPT đã báo, 16 bắt được, 7 lọt. Claude chấp nhận 4/7: `rj_khong_doi_loai` và `kick_filebusy_van_thu_lai` có hạn 10 giây đỡ; `lock_nuot_moi_oserror` chỉ đổi lỗi đĩa thành "đang bận" và vẫn giữ mục; `cb_khong_ghi_log` vẫn còn thông báo trong yêu cầu. Ba đột biến còn lại thuộc T1-23.

**Chưa kiểm được ở lượt này:** toàn bộ `apps/retail_app/tests` (chạy sau lượt 5, vì T1-23…T1-25 chỉ đổi `apps/retail_app/ui` và `views`); `roles.store()` với Neon thật; pipeline đầy đủ; giao diện thật (§6).

| Mã | Mức | Phát hiện (Claude đã chạy thử) | Việc cho GPT |
|---|---|---|---|
| T1-23 | Trung bình | `cancelled_backfill` chỉ xét `nap_bu_tu`, `da_duyet` và không có trong hàng đợi. Chuỗi thật `t4_probe.py` test `f3`: nạp bù chạy lỗi → Duyệt lại → DE duyệt tay → yêu cầu `da_duyet`, `duong='tay'`, vẫn giữ `nap_bu_tu`, nên bị coi là "đã bị hủy" và khóa Chạy vĩnh viễn, cả trang lẫn `start`. Yêu cầu không có đường ra. Ba đột biến lọt cùng chỗ: bỏ kiểm trạng thái, bỏ kiểm hàng đợi, trang không khóa nút | Thêm điều kiện `duong == 'tu_dong'`; giữ `nap_bu_tu` để truy vết. Test: chuỗi trên chạy được; nạp bù `loi` không bị coi là hủy; nạp bù còn trong hàng đợi không bị coi là hủy; trang khóa nút Chạy khi đã hủy thật |
| T1-24 | Trung bình | Hồi quy do bản sửa T1-20: `_kick_locked` không còn bắt `OSError` khác `PermissionError`, `FileNotFoundError`. **Phiếu của Claude lại thiếu ca này ở §3.5, nay đã sửa.** Phép thử của Claude: `Popen` ném `WinError 1455` (thiếu bộ nhớ) → yêu cầu đầu thành `loi`, ngoại lệ thoát khỏi `recover_queue`, cả hai mục còn trong hàng đợi, không có dòng nhật ký bỏ mục; đọc code: worker nuốt lỗi này. `t4_probe.py` test `h2`: `enqueue` ném lên trang Gửi dù file đã nhận. Test `i`: lỗi đọc `EIO` cũng ném ra | Theo §3.5 mới. Bắt `FileNotFoundError` trước như lỗi vĩnh viễn; `OSError` còn lại vào nhánh tạm thời. Lỗi khởi động worker phải phân biệt bằng loại ngoại lệ riêng, không để lẫn vào nhánh tạm thời: yêu cầu `loi`, bỏ mục, ghi nhật ký, dừng lượt, không ném lên trang; thao tác `start` thủ công vẫn báo lỗi cho DE. Test: `h` (mục sau giữ `da_duyet`, lần `recover_queue` kế chạy mục đó), `h2`, `i` đạt; giữ test FIFO của T1-20 |
| T1-25 | Thấp | `path.unlink` trong `_kick_locked` không thử lại. `t4_probe.py` test `g`, `g2`: mục đang được mở lúc xóa → `PermissionError` thoát ra dù worker đã khởi động. Đọc code: ở đường nâng hợp đồng, người dùng sẽ thấy "Cột mới có hiệu lực từ lần gửi sau" trong khi nạp bù đang chạy. Mục thừa được dọn ở lượt sau nên không chạy trùng | Xóa mục thử lại tối đa 10 giây như `atomic_json`, chỉ cho lỗi file đang mở; hết hạn thì ghi nhật ký, không ném. Test: `g`, `g2` đạt; đang mở 1 giây thì mục được xóa |

Ghi cho T2, không sửa ở lượt này: `read_json` thử lại `PermissionError` trên mọi hệ điều hành, nên trên Linux lỗi quyền thật sẽ chờ 10 giây rồi mới báo.

Phép thử của Claude, cùng thư mục `C:\Users\Win\AppData\Local\Temp\claude\D--retail-analytics\a77be869-4ff6-44d6-a768-5c3ad202cec8\scratchpad\`: `t4_probe.py` (viết theo hành vi đúng; `f`, `f2`, `f3`, `g`, `g2`, `h`, `h2`, `i` đang trượt, `e2` đạt), `t1_e2e.py`. `t3_probe.py` test E không còn là tiêu chí, `e2` thay nó; đừng đổi T1-21 để test E đạt. Chỉ đọc, không sửa. Không chạy pipeline đầy đủ, không commit. Sửa xong báo lại số test; Claude chạy lại, kèm đột biến cho phần vừa sửa.

**Lượt 5, 2026-11-03: Chưa đạt, không còn lỗi Cao.** T1-23…T1-25 đã sửa đúng. Phép thử mới phát hiện hai lỗi ở nhánh lỗi: một Trung bình, một Thấp. Đường chạy bình thường vẫn đúng.

**Đã kiểm và đúng (không cần sửa):**
- Claude tự chạy lại bốn file `test_state_io`, `test_tu_dong`, `test_nhap_tu_dong`, `test_nhap_du_lieu`: 240 đạt. Riêng hai file UI 187 đạt, khớp số GPT.
- `t4_probe.py`: 9/9 đạt, gồm chuỗi nạp bù lỗi → Duyệt lại → duyệt tay → Chạy (`f3`), lỗi tạo tiến trình dừng lượt và giữ mục sau (`h`), không ném lên trang Gửi (`h2`), lỗi đọc `EIO` (`i`), xóa mục khi file đang mở (`g`, `g2`).
- `t5_probe.py`: lỗi tạo tiến trình dạng `FileNotFoundError`, `MemoryError`, `PermissionError` đều dừng lượt đúng; `id` hỏng (`a:b?`, 300 ký tự, `../x`, `con`, `None`, `123`) đều bị bỏ, mục sau chạy; giữ `active.json` mở từ lúc ghi marker thì lượt dừng sau khoảng 10 giây, một dòng `nhap_chay` (test `g`).
- Worker thật, CLI giả, 4 lần chạy, mỗi lần Claude đọc một phần kết quả. Một lần đọc kịch bản gửi liền nhau: 3/3 `da_cong_bo`, 16 giây, đúng FIFO, mỗi lúc một stage, nhật ký đủ 3/3/3 dòng. Ba lần đọc kịch bản giết worker: yêu cầu thành `loi`, mục sau chạy khi mở trang và công bố được.
- Đột biến độc lập: 18 đột biến, 14 bắt được, 4 lọt. Claude chấp nhận 2: `mat_file_chua_xoa_van_chay` và `hong_chua_xoa_van_chay` (mục hỏng chưa xóa được thì chạy tiếp mục sau không làm sai thứ tự mục tốt; lượt sau dọn). `io_khong_het_han` thuộc T1-26: hạn 10 giây là thứ giới hạn thời gian giữ `dispatch`, vì `atomic_json` có thể tốn 10 giây mỗi lần thử. `spawn_luon_workerstart` thuộc T1-27.
- `scripts/` không đổi ở lượt này theo thời gian sửa file, nên Claude không chạy lại; số 301 đạt 3 bỏ qua là của lượt 4 và báo cáo GPT.

**Claude chấp nhận, không yêu cầu sửa:** `log_event` chỉ ném khi ghi cả file nhật ký dự phòng cũng lỗi (`t5_probe.py` test `b`). Khi đó trang Gửi có thể báo lỗi dù file đã nhận, không mất dữ liệu, không sai trạng thái. Không làm thêm nhánh cho ca này.

**Chưa kiểm được ở lượt này:** toàn bộ `apps/retail_app/tests` (chạy sau lượt 6); `roles.store()` với Neon thật; pipeline đầy đủ; giao diện thật (§6).

| Mã | Mức | Phát hiện (Claude đã chạy thử) | Việc cho GPT |
|---|---|---|---|
| T1-26 | Trung bình | Hồi quy do bản sửa T1-24, **câu trong §3.5 của Claude chưa nói tới ca này.** `_kick_locked` thử lại cả `_start_locked`, kể cả khi hàm đã ghi. Ba hậu quả đã chạy thử trong `t5_probe.py`: test `a`: ghi marker lỗi kéo dài (đĩa đầy) → **96 dòng `nhap_chay` trong 10 giây cho một lần không chạy**, mỗi dòng một lượt ghi Neon, mỗi lần mở trang lặp lại. Test `d`: tạo tiến trình lỗi đúng lúc `active.json` đang mở → lần thử lại đọc được `dang_chay`, bỏ mục rồi khởi động luôn mục sau, có dòng `nhap_chay` giả cho mục sau, trái quy tắc dừng lượt của T1-24. Test `h`: `Popen` đã thành công nhưng ghi PID lỗi → bỏ mục, tạo thêm worker cho mục sau ngay trong lượt | Theo §3.5 mới: chỉ thử lại lỗi trước lần ghi đầu tiên của `_start_locked`; từ lần ghi đầu tiên, không thử lại và dừng lượt. Chuyển dòng nhật ký xuống dưới marker thôi thì chưa đủ. Vẫn giữ FIFO, không ném lên trang. Test: `a`, `d`, `h` đạt; `g` vẫn đạt (dưới 15 giây, một dòng `nhap_chay`); giữ test của T1-20, T1-24 |
| T1-27 | Thấp | `_start_locked`, nhánh tạo tiến trình lỗi: xóa `active.json` trước rồi mới ghi `loi`. `t5_probe.py` test `e`: nếu ghi `loi` cũng thất bại thì yêu cầu kẹt `dang_chay`, không worker, không marker, mục hàng đợi đã bỏ. Không có đường ra, vì chỉ worker hoặc marker mới đưa được yêu cầu ra khỏi `dang_chay`. Cần hai lỗi cùng lúc nên hiếm. Đột biến `spawn_luon_workerstart` lọt: chưa có test phân biệt lỗi trước và sau khi `Popen` thành công | Đổi thứ tự: ghi `loi` trước; ghi được thì mới xóa marker, xóa lỗi cũng không ném; ghi không được thì giữ marker để `_active_busy` đối soát ở lượt kế. Khi `process is None` luôn ném `WorkerStartError`. Test: `e` đạt; lỗi sau khi `Popen` thành công không thành `WorkerStartError` |

Phép thử của Claude, cùng thư mục `C:\Users\Win\AppData\Local\Temp\claude\D--retail-analytics\a77be869-4ff6-44d6-a768-5c3ad202cec8\scratchpad\`: `t5_probe.py` (`a`, `d`, `e`, `h` đang trượt, `g` đạt; test `b` trượt nhưng không phải tiêu chí), `t4_probe.py`, `t1_e2e.py`. Chỉ đọc, không sửa. Chỉ sửa `apps/retail_app/ui/nhap_runner.py` và test của nó; không đổi thiết kế, không thêm nhánh ngoài hai mã trên. Không chạy pipeline đầy đủ, không commit.

**Lượt 6, 2026-11-03: Đạt phần rà code, chưa xong nghiệm thu.** T1-26, T1-27 đã sửa đúng; không có lỗi mới phải sửa. Còn phải chạy toàn bộ `apps/retail_app/tests` rồi §6.

**Đã kiểm và đúng:**
- Claude tự chạy lại bốn file `test_state_io`, `test_tu_dong`, `test_nhap_tu_dong`, `test_nhap_du_lieu`: 261 đạt. Riêng hai file UI 208 đạt, khớp số GPT.
- `t4_probe.py`, `t5_probe.py`: 23 ca tiêu chí đạt, gồm `a`, `d`, `e`, `g`, `h`. Ba biến thể test `b` vẫn trượt, đúng phần Claude đã chấp nhận ở lượt 5.
- Phép thử lượt 1–3: 23/24 đạt; ca còn lại là `t3_probe.py` test E, đã bỏ khỏi tiêu chí từ lượt 4.
- Worker thật, CLI giả: 3/3 `da_cong_bo`, 15 giây, đúng FIFO, mỗi lúc một stage, nhật ký 3/3/3 dòng; giết worker thì yêu cầu thành `loi`, mục sau chạy khi mở trang và công bố được.
- Đột biến độc lập: 12/12 bắt được, gồm `spawn_luon_workerstart` và `io_khong_het_han` đã lọt ở lượt 5.
- `scripts/` không đổi ở lượt này theo thời gian sửa file, nên Claude không chạy lại; số 301 đạt 3 bỏ qua là của lượt 4 và báo cáo GPT.

**Claude chấp nhận, không yêu cầu sửa:**
- Ghi marker lỗi kéo dài: mỗi lượt kích hoạt còn một dòng `nhap_chay` dù chưa chạy, vì nhật ký ghi trước marker. Đúng giới hạn §3.5; từ 96 dòng xuống một dòng.
- `log_event` ném khi cả file nhật ký dự phòng cũng lỗi (test `b`), như lượt 5.
- Đọc code, chưa chạy: mục hàng đợi bị giữ mở gần 10 giây lúc xóa thì `dispatch` bị giữ gần bằng hạn chờ của worker, worker có thể báo `loi`. Trạng thái vẫn đúng và gửi lại được; lần đọc thật chỉ tính bằng mili giây.

**Bộ test rộng (PM chạy 2026-11-03, Claude so từng test):** `apps/retail_app/tests` ra 667 đạt, 578 trượt, 604 bỏ qua; so với bản trước T1 và lần chạy T1 trước đó, không có test nào mới hỏng. Các lỗi trượt xem theo nhóm do worktree không có `warehouse/dbt.duckdb`. Vì lỗi này có thể che lỗi thật ở test giao diện, Claude chạy lại `test_roles`, `test_smoke`, `test_khong_hardcode`, `test_ban_phuc_vu` trên bản sao kho: 79 đạt, 3 bỏ qua ở cả T1 và bản trước T1, không khác nhau.

**Thử trước file §6, phân loại thật trên thư mục tạm:** file 2022 gốc và file có `bonus` ra `tu_dong`; file thiếu `comment` ra `can_nguoi`, lý do `thieu_cot`; `epd.json` ra `can_nguoi`, lý do `chua_co_hop_dong`, `doi_kieu`, `xung_dot_khoa`.

**Chưa kiểm được:** `roles.store()` với Neon thật; pipeline đầy đủ; giao diện thật (§6).

**Nghiệm thu §6, đang làm từ 2026-11-03 (PM thao tác, Claude kiểm kho):**
- Bước 1 đạt: `da_cong_bo`, các bước do `he_thong`, hợp đồng v1, 0 dòng cách ly, `dim_sales_employee` 200, 36.004 đơn có nhân viên; `sales_employee_name` ở mart, `comment` ở `stg_orders_enriched`.
- Bước 2 đạt về dữ liệu: lượt đầu `orders_enriched.parquet` không có `bonus`; DE duyệt v2; nạp bù tự chạy và công bố, parquet có `bonus` đủ 36.004 dòng; không có `bonus` ở schema nào của release.
- Bước 2b đạt về dữ liệu: file gốc vẫn tự động trên hợp đồng v2, trang báo file không có cột `bonus`, 0 dòng cách ly; parquet không có `bonus`; mart đủ 36.004 đơn có nhân viên, `dim_sales_employee` 200; `active` là bản của lượt này.
- Bước 3 đạt: file thiếu `comment` và `epd.json` dừng ở `cho_duyet`, đường tay, không tạo lượt chạy; lý do đúng, không nhắc `bonus`. Ô Kiểu là danh sách `string / integer / date / double`; PM thử trên bảng duyệt của `epd.json`, cùng đoạn code với yêu cầu thiếu cột.
- Bước 4 đạt về dữ liệu: hai lần gửi cách nhau 11 giây; lần hai hiện "Đang xếp hàng (thứ 1)"; lần một công bố 16:19:41, lần hai bắt đầu 16:19:43 và công bố 16:23:18, không chồng stage, không ai bấm; hợp đồng v2, 0 dòng cách ly, parquet có `bonus`, mart đủ 36.004 đơn có nhân viên, không có `bonus` trong release. Forecast dao động 2 phút 52 giây đến khoảng 6 phút 30 giây giữa các lượt. PM chụp lúc 17:02 nên ảnh chưa cho biết trang có tự chuyển hay không.
- Bước 5 đạt: Admin rollback về `c2a66dd7`, `state.json` đổi `active` lúc 17:11:15, vẫn 7 bản, `history.jsonl` có dòng `rollback`.
- Bước 6 đạt, lần đầu kiểm trên Neon thật: nhật ký trang Phân quyền có `nhap_gui` của `chushop`, `nhap_tu_duyet`, `nhap_xep_hang`, `nhap_chay`, `nhap_cong_bo` của `he_thong`, `nhap_rollback` của Admin; không còn `nhat_ky_cho.jsonl`. Cột giờ là UTC.
- Bước 7 đạt, là giả lập: mở `app.py` đầy đủ với `duckdb` và `yaml` bị chặn, PS đọc Postgres local thay Databricks, role Quản lý, DE, Admin. Hai trang chỉ hiện thông báo, không có ô tải file, không chạm kho nhập; Tổng quan, PS1–PS5, Dự báo, trang chat mở không lỗi. Chưa thử trên Streamlit Cloud thật, chưa gửi câu hỏi chat.
- **Kết luận §6: dữ liệu, thứ tự, nhật ký và rollback đạt. Còn T1-28…T1-32 về giao diện.** Sau khi sửa, Claude rà lại, PM thử lại một lượt thật không F5 rồi mới hỏi commit.

| Mã | Mức | Phát hiện | Việc cho GPT (sau khi xong §6) |
|---|---|---|---|
| T1-28 | Trung bình | Trang đứng ở "Đã kiểm tra" và "Đang có một lượt nhập dữ liệu…" dù đã công bố (ảnh PM 13:39, kho `da_cong_bo` từ 13:35:14). Đọc code: khoảng 8 giây giữa `da_kiem` và `da_cong_bo`, `running_status` chỉ làm mới khi `dang_chay`. Trang Gửi cũng dính: ảnh PM 14:52:51 vẫn "Đã kiểm tra" khi chưa tải lại, kho `da_cong_bo` từ 14:52:08. F5 lại làm mất đăng nhập (`docs/phan_quyen.md` §5, PM chấp nhận 2026-10-29) nên không phải cách xem kết quả cho chủ shop | Cả hai trang: thay cách làm mới theo từng yêu cầu bằng **một vòng dò 5 giây cho cả trang**, chạy khi còn yêu cầu **đang dở**: `dang_chay`; còn trong hàng đợi; hoặc `da_kiem` của đường tự động do `he_thong` chạy (khoảng chờ công bố). Dò thấy trạng thái hoặc danh sách yêu cầu đổi thì tải lại cả trang một lần, không làm mất đăng nhập. Hết yêu cầu đang dở thì ngừng dò. **PM chốt 2026-11-03 khi GPT hỏi (phiếu tự mâu thuẫn giữa "ngừng dò" và "nạp bù mới tự hiện", Claude viết thiếu):** riêng trang Gửi dò tiếp khi còn cột chờ DE quyết định, chỉ đọc, không đổi thì không tải lại; trang Duyệt giữ điều kiện ngừng cũ. `da_kiem` của đường tay (chờ Admin) không tính là đang dở. `da_kiem` tự động mà không còn worker (`busy_reason` rỗng) cũng ngừng dò và hiện đúng "Đã kiểm tra" để Admin xử lý, không dò mãi. Trong khoảng chờ công bố, trang Gửi hiện "Đang xử lý", không hiện "Đã kiểm tra". Test: `dang_chay` → `da_kiem` → `da_cong_bo` tự ra "Đã cập nhật"; yêu cầu đang xếp hàng tự chuyển khi tới lượt; yêu cầu nạp bù mới tự hiện; đường tay không dò; worker chết ở `da_kiem` thì ngừng dò. PM kiểm lại bằng một lượt thật, không F5 |
| T1-29 | Trung bình | Chủ shop không biết cột mới đã được duyệt chưa. Yêu cầu có `cot_moi` hiện mãi câu "cột mới chờ đội dữ liệu duyệt", kể cả sau khi DE duyệt (ảnh PM 14:40, duyệt khoảng 14:17) hoặc từ chối. Yêu cầu nạp bù chỉ ghi "Nạp bù sau nâng hợp đồng", không nói cột nào. Phiếu §3 mới nói câu chờ duyệt, thiếu trạng thái sau đó: **Claude viết thiếu** | Câu trên trang Gửi đi theo trạng thái hợp đồng: chờ duyệt; đã duyệt (nêu tên cột, phiên bản, yêu cầu nạp bù); không nhận (nêu lý do). Yêu cầu nạp bù nêu tên cột. Không lộ đường dẫn, sha, log. Test: ba trạng thái |
| T1-30 | Thấp | Trang Gửi không báo hiệu khi lượt chạy xong; chủ shop phải tự để ý màn hình. PM đồng ý thêm 2026-11-03, **không làm dịch vụ email** | Trang Gửi đang mở thấy trạng thái yêu cầu đổi sang "Đã cập nhật" hoặc "Lỗi" thì hiện thông báo nổi (`st.toast`) kèm tên file, mỗi lần đổi một lần, tải lại trang không hiện lại. Đặt cùng chỗ làm mới của T1-28. Test: đổi trạng thái có một thông báo; không đổi thì không có |
| T1-31 | Thấp | Trang Gửi dùng chữ kỹ thuật với chủ shop: "Đang chạy forecast", "Đã cập nhật bản dữ liệu local". PM đồng ý đổi 2026-11-03 | Chỉ trang Gửi: "Đang xử lý (bước N/4)" theo thứ tự `STAGES`; "Đã cập nhật dữ liệu". Trang Duyệt của DE giữ tên stage. Test: trang Gửi không còn tên stage, không còn chữ "local" |
| T1-32 | Thấp | Ô chọn bản ở mục Rollback chỉ hiện mã, xếp theo mã (`rollback_options`), không có giờ hay file, nên Admin không biết đâu là bản trước (ảnh PM 17:07). Rollback nhầm bản khó nhận ra | Mỗi dòng hiện giờ công bố, tên file, mã yêu cầu, phiên bản hợp đồng và mã ngắn; xếp mới nhất lên đầu, không gồm bản đang dùng. Bản không tra được yêu cầu vẫn hiện được. Test: thứ tự theo thời gian, giá trị gửi đi vẫn là mã đầy đủ |

**Lượt 7 (GPT sửa T1-28…T1-32), Claude rà 2026-11-03: chưa đạt, còn T1-33…T1-39.**

- Tự chạy lại ba file UI: `231 passed`, khớp báo cáo GPT. Đột biến độc lập 39, bắt được 36. Một cái lọt là tương đương (`awaiting_publish` bỏ kiểm `duong`): `da_kiem` chỉ sinh từ lượt chạy, mà `_start_locked` luôn ghi đè `nguoi_chay`, nên không có `tay` do `he_thong` chạy. Thực chất 36/38; hai cái còn lại ghi ở T1-39. Probe cũ `t4`, `t5` tiêu chí a, d, e, g, h: 23 đạt, không hồi quy.
- Đọc kho thật của PM, chỉ đọc: câu trạng thái cột và danh sách rollback ra đúng, `bonus` đã duyệt v2 kèm mã nạp bù, không còn gì đang dò.
- T1-28…T1-32 đúng trong phạm vi phiếu. Các lỗi dưới đây nằm ngoài các ca phiếu nêu; probe tự viết của Claude trượt, trừ T1-38 đọc từ kho thật và T1-39 từ đột biến.
- **Chưa làm ở lượt này, để sau khi sửa:** toàn bộ `apps/retail_app/tests`, e2e, PM thử một lượt thật không F5. Vòng dò thật trên trình duyệt chưa ai kiểm; AppTest không chạy bộ đếm 5 giây và không thấy chữ đang gõ dở trong form. Lượt PM thử phải có thêm một việc: DE đang gõ lý do hoặc sửa bảng cột của yêu cầu A thì yêu cầu B đổi trạng thái, xem chữ đang gõ còn không.

| Mã | Mức | Phát hiện | Việc cho GPT |
|---|---|---|---|
| T1-33 | Trung bình | Trang Duyệt: ô chọn yêu cầu nhảy về yêu cầu mới nhất mỗi khi một yêu cầu đổi trạng thái hoặc có yêu cầu mới, vì nhãn nằm trong định danh widget. Từ khi có vòng dò, việc này tự xảy ra lúc DE đang điền form của yêu cầu khác, nên mất phần chưa bấm Duyệt. Probe: chọn yêu cầu cũ, yêu cầu kia đổi sang `da_kiem`, trang chạy lại thì giá trị đổi | Cho `st.selectbox` một `key` cố định (Streamlit 1.64 lấy `key` làm định danh chính) **và bỏ trạng thái khỏi nhãn**, chỉ còn tên file, người gửi, mã yêu cầu; trạng thái đã có ở dòng "Trạng thái" bên dưới. Lý do: trình duyệt gửi lại giá trị theo chữ của nhãn cũ, nên nhãn của chính yêu cầu đang chọn đổi thì có thể mất lựa chọn, mà AppTest không tái hiện được. Test AppTest: giữ lựa chọn khi yêu cầu khác đổi trạng thái, khi chính yêu cầu đang chọn đổi trạng thái, khi có yêu cầu mới; nhãn không đổi khi trạng thái đổi |
| T1-34 | Trung bình | Trang Duyệt: "Đang chạy forecast · N giây" và log đứng im giữa hai bước, vì snapshot không đổi nên không tải lại. Bước forecast dài khoảng 6 phút nên trông như treo. Bản trước T1-28 có fragment riêng làm mới mỗi 5 giây: **hồi quy** do cách viết "một vòng dò" của phiếu | Không thêm bộ đếm thứ hai. Trên trang Duyệt, gọi `monitor_page` đúng ở chỗ hiện trạng thái chạy, truyền vào một hàm vẽ; khi yêu cầu đang chọn là `dang_chay` thì `running_status(record)` được gọi **bên trong fragment**, đọc lại yêu cầu mới nhất, không viết vào placeholder ngoài fragment. Không tải lại cả trang. Trang Gửi không hiện số giây và log. Test: thời gian đổi thì số giây trong fragment đổi, không có `rerun`, và chỉ có một phần tử hiện trạng thái |
| T1-35 | Trung bình | Đề xuất cột của yêu cầu cũ phiên bản bị treo. Hai yêu cầu cùng v1 có cột khác nhau, DE duyệt một cái thành v2. `pending_upgrades` không còn đưa yêu cầu kia cho DE, nhưng `pending_columns` vẫn là chờ. Trang Gửi báo "chờ đội dữ liệu duyệt" mãi, dò mãi, mà không ai duyệt được. Probe: "Cột thuong_them chờ đội dữ liệu duyệt" sau khi đã lên v2 | Ba hàm đang dùng ba luật: `pending_upgrades` kiểm phiên bản và khớp từ chối theo đúng tập cột; `pending_columns` không kiểm phiên bản và coi cột nào từng bị từ chối là xong; `column_notice` khớp từ chối theo đúng tập. Viết **một hàm duy nhất** trả về chờ / đã duyệt v{n} / không nhận / hết hạn, ba hàm kia cùng dùng. Hết hạn thì trang Gửi báo: "Hợp đồng đã lên v{n}, cột {tên} chưa được xét. Gửi lại file để đề xuất.", chỉ nêu cột chưa có trong hợp đồng, và không dò. Test: hai đề xuất cùng phiên bản; đề xuất nhiều cột được duyệt một phần ở bản khác; đề xuất có tập cột là tập con của tập đã từ chối thì DE thấy, trang Gửi báo chờ và có dò |
| T1-36 | Trung bình | Worker chết khi còn mục trong hàng đợi: `page_busy` trả `True` vì có hàng đợi, snapshot không đổi, trang không tải lại nên `recover_queue` không chạy. Trang hiện "Đang xử lý" và hàng đợi đứng yên đến khi có người bấm. Hiếm, nhưng là đúng việc T1-28 muốn bỏ. Không có hàng đợi thì đúng, vì `busy` đổi | Đưa trạng thái worker còn sống vào snapshot, tách khỏi hàng đợi, để worker chết làm snapshot đổi và trang tải lại một lần. Vòng dò vẫn chỉ đọc. Test: PID chết, còn hàng đợi thì có `rerun`, sau đó yêu cầu thành `loi` và mục kế chạy |
| T1-37 | Thấp | `page_busy` kiểm `exists()` rồi mới đọc `active.json`. Worker xóa marker đúng lúc đó thì `FileNotFoundError` nổ ra trang chủ shop. Cửa sổ rất hẹp, nhưng giờ đọc mỗi 5 giây | Hết file thì không bận. Lỗi đọc khác (`OSError`, `ValueError`) thì coi là còn bận, không nổ ra trang. Test: xóa giữa chừng; file bận |
| T1-38 | Thấp | Nhãn rollback hiện giờ thô UTC: `2026-11-03T09:23:18.464138+00:00`, lệch 7 giờ với giờ PM làm việc, dễ chọn nhầm bản | Hiện `YYYY-MM-DD HH:MM` giờ Việt Nam. Dùng `timezone(timedelta(hours=7))`, không dùng `ZoneInfo` vì Windows có thể thiếu `tzdata`. Vẫn sắp xếp theo giá trị gốc. Test: chuỗi hiển thị đúng và thứ tự không đổi |
| T1-39 | Thấp | Hai đột biến lọt: toast chạy cả trên trang Duyệt; nhãn rollback lấy lần công bố sớm nhất thay vì muộn nhất | Thêm test: trang Duyệt không có toast; yêu cầu công bố hai lần lấy giờ muộn nhất |

**Lượt 8 (GPT sửa T1-33…T1-39), Claude rà 2026-11-03: đạt phần rà code, còn nghiệm thu trên trình duyệt.**

- Tự chạy lại ba file UI: `246 passed`. Probe tự viết của lượt 7 đạt 5 ca; ca số giây viết theo cách cũ nên bỏ, đã có đột biến `ve_bo_goi`, `ve_khong_truyen` thay thế.
- Đột biến độc lập phần mới 26, bắt 20. Sáu cái lọt: `ve_tu_snapshot_cu` tương đương (đến chỗ vẽ thì `current == snapshot`); `gui_co_ve` do Claude tự chèn mã, không phản ánh rủi ro thật; bốn cái còn lại là thiếu test, gom ở T1-40. Đột biến cũ chạy lại: chỉ còn cái tương đương đã ghi ở lượt 7; bảy cái không còn áp được vì mã đã gộp, phần đó do bộ mới phủ.
- Probe cũ không hồi quy: `t4` đạt, `t5` ngoài tiêu chí b đã loại đạt, `t1`–`t3` 23/24 (ca đã bị thay thế từ trước). Worker thật: ba yêu cầu công bố tuần tự; giết worker thì mở trang đối soát thành `loi` và mục kế chạy tới công bố.
- Kho thật của PM, chỉ đọc: câu trạng thái cột đúng; danh sách rollback hiện giờ Việt Nam, mới nhất lên đầu.
- **Còn lại:** toàn bộ `apps/retail_app/tests` so với `t6_rong_t1.xml`, rồi PM thử trên trình duyệt không F5. Fragment 5 giây, giữ chữ đang gõ và lựa chọn khi nhãn đổi chỉ kiểm được ở đó.

| Mã | Mức | Phát hiện | Việc cho GPT |
|---|---|---|---|
| T1-40 | Thấp | Mã đúng, nhưng bốn hành vi không có test giữ: đang xem yêu cầu không chạy mà yêu cầu khác đang chạy thì không vẽ phần chạy của yêu cầu kia; cột đã từ chối vẫn báo "không nhận" sau khi hợp đồng lên bản khác; yêu cầu đã chuyển đường tay (`duong='tay'`, còn `cot_moi`) không vào danh sách nâng hợp đồng; yêu cầu duyệt ở v2 vẫn báo v2 và mã nạp bù khi hợp đồng đã lên v3 | Chỉ thêm test, không sửa mã. Gộp vào lượt sửa sau nghiệm thu trình duyệt để khỏi rà hai lần |

**Nghiệm thu trình duyệt (PM thử 2026-11-03, không F5; Claude đối chiếu ảnh với kho): chưa đạt.**

- Test rộng `apps/retail_app/tests`: 578 trượt, 705 đạt, 604 bỏ qua. Không test nào đổi trạng thái so với `t6_rong_t1.xml`; so với mốc trước T1 chỉ 3 test đổi, đều tốt lên. Phần `scripts` ingest, pipeline, forecast: 285 đạt, 2 bỏ qua. Các test trượt sẵn và bị bỏ qua không kiểm được T1; cần chạy lại trên máy có `warehouse/dbt.duckdb` trước khi merge.
- Đạt: bước 1, bước 2 (PM xác nhận giữ chữ đang gõ, ô sửa và lựa chọn), bước 5 (đúng giờ Việt Nam; bản đang active không có trong danh sách là đúng thiết kế).
- Bước 3, dữ liệu đúng: yêu cầu `bc81f9` lên hợp đồng v3, yêu cầu nạp bù `d6f97e` công bố lúc 20:50 giờ Việt Nam, active `be1f310f` thuộc `d6f97e`. Parquet `orders_enriched` của snapshot lượt đầu không có `hoa_hong`; của snapshot nạp bù có đủ 36.004 dòng, tổng 270.030.000, khớp file. Marts và reporting không có cột này, đúng với lựa chọn silver.
- **Bước 3, giao diện sai:** trang Gửi đứng ở trạng thái cũ. Ảnh 20:42:38 còn "Đã gửi" và 20:44:41 còn "Có hiệu lực từ lần gửi sau", trong khi kho đã chuyển `dang_chay` từ 20:42:31. Tái dựng trên kho thật, chỉ đọc: khi yêu cầu con ở `da_gui`, `cho_duyet` hoặc `da_duyet` chưa vào hàng đợi thì `pending=False`, `waiting_columns=False`, nên `run_every=None`.
- Bước 4 đạt (PM làm lại lúc 21:01): từ chối lúc 21:03:16, trang Gửi đổi câu sang "Không nhận cột muc_uu_tien: Chưa cần cột này" khi file đang chạy; yêu cầu `88f0e1` công bố lúc 21:10, active `788e2850`, hợp đồng giữ v3; parquet có 36.004 dòng, không có `muc_uu_tien`. Ở bước 4 cột hết chờ nhưng yêu cầu đang chạy nên vòng dò không tắt.
- PM xác nhận đã bấm chuyển menu ở trang Gửi khoảng 20:45 trong bước 3, khớp với nguyên nhân của T1-41.
- Thông báo nổi: ảnh 21:10:36 có "orders_enriched_uu_tien.csv: Đã cập nhật", 14 giây sau khi công bố. Chưa xác nhận trên trình duyệt là chỉ hiện một lần; kiểm ở lần thử lại bước 3.
- Ghi nhận, chưa giao sửa: khi trạng thái đổi, mục yêu cầu đang mở tự thu lại vì nhãn có chứa trạng thái. Trạng thái mới vẫn đọc được trên nhãn.

| Mã | Mức | Phát hiện | Việc cho GPT |
|---|---|---|---|
| T1-41 | Cao | Sau khi DE duyệt nâng hợp đồng, trang Gửi có thể ngừng dò vĩnh viễn: cột đã hết chờ, còn yêu cầu nạp bù chưa vào hàng đợi trong khoảng 12 giây nên chưa tính là `pending`. Lần dò rơi vào khoảng đó sẽ tắt vòng dò, trang đứng tới khi người dùng chuyển menu | `pending` tính mọi yêu cầu `da_gui`, và `da_duyet`, `cho_duyet` có `duong='tu_dong'` (PM chốt 2026-11-03: `create` ghi `da_gui` trước khi có `nap_bu_tu`, nên không lọc được `da_gui` theo hai trường này). Không tính `cho_duyet` đường tay, để trang không dò mãi. Thêm test theo từng trạng thái: gồm yêu cầu con ở từng trạng thái trên, kiểm vòng dò vẫn chạy và đổi được khi yêu cầu con sang `dang_chay`; ca đường tay kiểm vòng dò tắt |
| T1-42 | Thấp | Trong vài giây đầu của yêu cầu nạp bù, yêu cầu con hiện "Chờ đội dữ liệu" và yêu cầu mẹ hiện "Có hiệu lực từ lần gửi sau", cả hai đều sai vì `duong`, `hop_dong` chưa được ghi | Yêu cầu `da_gui` chưa có `duong` không được ghi "Chờ đội dữ liệu". Câu của yêu cầu mẹ phải nhận yêu cầu con theo `nap_bu_tu == record['id']` kể cả khi con chưa có `hop_dong`. Có test cho cả hai |
| T1-43 | Thấp | Trang Duyệt ghi "Có thể tải lại trang" trong khi F5 hiện làm mất đăng nhập, và trang đã tự cập nhật | Bỏ vế này ở `views/duyet_du_lieu.py:33`, sửa test liên quan nếu có |

**Lượt 9 (GPT sửa T1-40…T1-43), Claude rà 2026-11-03: đạt phần code, còn thử lại trên trình duyệt.**

- Tự chạy lại ba file UI: `267 passed`. Đột biến độc lập 16, bắt 15, gồm cả bốn cái lọt ở lượt 8.
- Tái dựng tình huống T1-41 trên kho thật, chỉ đọc: cả ba trạng thái trước đây tắt vòng dò nay còn dò; kho thật hiện `pending=False` nên trang không dò mãi.

| Mã | Mức | Phát hiện | Việc cho GPT |
|---|---|---|---|
| T1-44 | Thấp | Đột biến `do_da_gui_chi_co_nap_bu` lọt: không test nào giữ ca `da_gui` chưa có cả `nap_bu_tu` lẫn `duong`, đúng khoảng mà PM chọn dò mọi `da_gui` | Chỉ thêm test ca này, không sửa mã. Gộp với lượt sửa sau khi thử lại |
| T1-45 | Thấp | T1-42 mới sửa trang Gửi; `views/duyet_du_lieu.py:59` vẫn ghi "Chờ đội dữ liệu" cho yêu cầu `da_gui` chưa có `duong` | Sửa cùng cách ở trang Duyệt, có test. Gộp với lượt sửa sau khi thử lại |

**PM thử lại bước 3 (2026-11-03, `orders_enriched_ma_kho.csv`, không F5, không bấm gì ở trang Gửi sau khi DE duyệt): T1-41 đạt.**

- Yêu cầu `9bb139` công bố 23:23:49; DE duyệt, yêu cầu nạp bù `81fdad` tạo lúc 23:26:52, chạy từ 23:27:06, công bố 23:34:37. Ảnh 23:27:33 trang Gửi đã hiện yêu cầu nạp bù ở "bước 2/4". PM xác nhận không bấm gì.
- Hợp đồng lên v4. Parquet của snapshot nạp bù có `ma_kho` đủ 36.004 dòng, tổng 108.010, khớp file; snapshot lượt đầu không có cột này. Marts và reporting không có `ma_kho`, đúng với lựa chọn silver. Sau khi xong: `pending=False`, `waiting_columns=False`.
- Thông báo nổi: PM xác nhận lượt đầu hiện một lần. Lượt nạp bù chờ PM xác nhận.
- Test có `dbt.duckdb` (`t9_rong_co_dbt.xml`): 1008 đạt, 297 trượt, 603 bỏ qua; `test_roles`, `test_smoke` không còn test trượt. Chạy tám file có test trượt theo cùng thứ tự trên mã trước và sau T1: cùng 140 trượt, 296 đạt, 180 bỏ qua, không test nào khác. Đối chứng toàn bộ trên mã trước T1 (`t9_doi_chung_rong.xml`): 796 đạt, 298 trượt, 604 bỏ qua. Trong các test có ở cả hai lần, chỉ 2 test đổi trạng thái, đều tốt lên; không test nào từ đạt thành trượt. `test_ai_tools` cùng 158 trượt, 37 đạt. Hai test mất là `test_pages_feature_off`, đúng quyết định bật cứng; 212 test mới đều đạt. Vậy T1 không gây hồi quy ở đây. 297 test trượt là tồn tại từ trước, nguyên nhân chưa điều tra, ngoài phạm vi T1.

**Lượt 10 (GPT sửa T1-44, T1-45), Claude rà 2026-11-04: đạt. Hết việc sửa của T1.**

- Tự chạy lại ba file UI: `269 passed`; `test_roles` chạy riêng: `43 passed`. Đột biến 5, bắt 4; cái lọt (`duyet_da_gui_co_duong`) không có tác động thực tế vì yêu cầu `da_gui` chưa từng có `duong`.
- Chạy gộp `apps` với `scripts` trong một lệnh: 21 lỗi, đều ở `test_roles` với `module 'conftest' has no attribute`, do `import conftest` trúng `scripts/ingest/tests/conftest.py`. Đây là đặc điểm của cách chạy, không phải T1; chạy tách hai thư mục thì không gặp.

## 10. Câu hỏi PM chốt trước khi giao

Đã chốt ở [thiet_ke_duong_tu_dong.md](thiet_ke_duong_tu_dong.md) §0 (2026-10-31): nguồn mới lần đầu DE duyệt; chạy ngay khi gửi, xếp
hàng khi bận; cột mới vẫn tự chạy, chờ nâng hợp đồng; validate đạt thì tự công bố. Không còn câu mở.
