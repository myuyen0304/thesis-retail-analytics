# Giao việc: trang Duyệt và trang Gửi báo đúng khi yêu cầu không còn là bản đang xem

Soạn ngày 2026-11-05, sau nghiệm thu auto mapping local (`docs/giao_viec_auto_mapping_local.md` §9). Claude soạn phiếu; PM bảo Claude tự code nên phần này không có lớp rà độc lập của người khác.

## 0. Vì sao cần

Sau rollback, yêu cầu `shipments_realistic.csv` vẫn ghi "Đã cập nhật" và bảng JSON vẫn hiện `dim_shipper` 80, trong khi bản đang xem không có shipper. PM đọc trang lúc đó dễ tưởng đã chạy xong.

Nguyên nhân: `nhap_runner.summary` (`apps/retail_app/ui/nhap_runner.py:701`) đọc `published.context.json` của yêu cầu và không so với `active`; rollback (`nhap_runner.py:684`) không đổi trạng thái yêu cầu. Số trong kho không sai, chỉ phần hiển thị thiếu.

## 1. Phạm vi

Chỉ thêm phần đối chiếu chỉ đọc và thông báo trên hai trang.

**Không làm:**
- Không đổi trạng thái, luật chuyển trạng thái, `lich_su`, `revision` của yêu cầu. "Đã cập nhật" và nút "Chạy lại để kiểm" giữ nguyên.
- Không đổi kết quả của `summary` và logic rollback, publish.
- Không sửa `scripts/ingest/source_contract.py`, `scripts/ingest/extensions/*.yml`, `retail_dbt/`, `scripts/pipeline/`.
- Không commit, không push.

Worktree `D:\retail-analytics-am`, nhánh `auto-mapping/myuyen`. Python: `D:/retail-analytics/.venv/Scripts/python.exe`.

## 2. Thiết kế

Thêm vào `nhap_runner.py` hai hàm chỉ đọc:

- `active_extensions(store)`: trả `(active_id, tập_tên_mở_rộng)`. Chưa có `active` thì trả `(None, set())`. Dùng lại cách đọc và cách kiểm context của `_extensions_for_run` (`nhap_runner.py:231–238`) bằng cách tách phần chung ra; không viết cách đọc thứ hai. Dữ liệu hỏng thì để lỗi như chỗ cũ.
- `published_release(store, record)`: đọc `release_id` trong `chay/published.context.json` của yêu cầu; chưa có file thì trả `None`.

### Trang Duyệt (`views/duyet_du_lieu.py`, ngay trước dòng 171)

Chỉ khi `trang_thai == 'da_cong_bo'`. `X` là `published_release`, `Y` là `active_id`, cả hai lấy 8 ký tự đầu.

| Điều kiện | Hiển thị |
|---|---|
| `X == Y` | Không thêm gì |
| `X != Y`, nguồn của yêu cầu có trong bản đang xem | `st.info`: "Số dưới đây là của bản X. Bản đang xem là Y, vẫn có nguồn này." |
| `X != Y`, nguồn của yêu cầu không có trong bản đang xem | `st.warning`: "Số dưới đây là của bản X, không phải bản đang xem (Y). Nguồn này hiện không có trong bản đang xem." |
| `Y` là `None`, `X` có giá trị | `st.warning`: "Kho chưa có bản đang xem." |
| `X` là `None` | Không thêm gì |
| Đọc lỗi | `st.warning`: "Chưa đối chiếu được với bản đang xem."; trang vẫn hiện phần còn lại |

"Nguồn của yêu cầu" là `record.get('ten_mo_rong')`. Thông báo phải đứng trên dòng `thong_bao`, vì dòng này có thể còn ghi "Không có gì mới, bỏ qua" của lượt trước.

### Trang Gửi (`views/gui_du_lieu.py:95`)

Vai trò Quản lý không xem mã bản. Với dòng `da_cong_bo`:

| Điều kiện | Hiển thị |
|---|---|
| Nguồn có trong bản đang xem | `st.success('Đã cập nhật dữ liệu')` như cũ |
| Nguồn không có trong bản đang xem | `st.info('Dữ liệu này đã từng được cập nhật nhưng hiện không nằm trong bản đang dùng.')` |
| Đọc lỗi | `st.info('Đã xử lý xong; đội dữ liệu đang kiểm tra trạng thái hiện tại.')` |

Đọc `active_extensions` **một lần** cho mỗi lần vẽ danh sách, không đọc lại theo từng dòng.

## 3. Test bắt buộc

Thêm vào `apps/retail_app/tests/test_nhap_du_lieu.py`, và theo mẫu test trang sẵn có cho phần giao diện:

1. Yêu cầu có bản đúng là `active`: không có thông báo thêm.
2. Sau rollback về bản không có nguồn: Duyệt hiện cảnh báo, Gửi hiện câu `st.info`, không còn "Đã cập nhật dữ liệu".
3. Yêu cầu 1 sau khi yêu cầu 2 công bố: `X != Y`, nguồn vẫn có trong active nên Duyệt hiện `st.info`, Gửi vẫn `st.success`.
4. Rollback về bản của yêu cầu 1: yêu cầu 1 không còn thông báo, yêu cầu 2 có cảnh báo.
5. Cùng một yêu cầu có hai bản, rollback về bản cũ của chính nó: `X != Y`, nguồn vẫn có trong active nên Duyệt hiện `st.info`.
6. Chưa có `active`; thiếu `published.context.json`; `state.json` hỏng; context của active hỏng hoặc không khớp `release_id`: không vỡ trang, đúng câu ở §2.
7. Trạng thái `da_kiem`, `dang_chay`, `loi`: không có thông báo mới.
8. Hai hàm mới không ghi gì: hash mọi file trong kho thử giữ nguyên trước và sau khi gọi.
9. Sau khi tách phần chung, các test `test_b4_*`, `test_b6_*` và `summary` giữ nguyên, không sửa kỳ vọng.

## 4. Lệnh chạy

```
D:/retail-analytics/.venv/Scripts/python.exe -m pytest apps/retail_app/tests/test_nhap_du_lieu.py apps/retail_app/tests/test_nhap_tu_dong.py -q
```

Không chạy pipeline thật, không chạy chung `apps` và `scripts` trong một lệnh.

## 5. Nghiệm thu

**Claude rà:** đọc code, làm hỏng từng điều kiện ở §2 để xem test có bắt được không, chạy lại các test trên.

**PM thử trên app (không tốn lượt pipeline, mỗi rollback vài giây):**
1. Admin rollback về bản có `orders_enriched.csv`. Trang Duyệt của yêu cầu `shipments` phải có cảnh báo; yêu cầu `orders_enriched` không có. Trang Gửi của `shipments` không còn "Đã cập nhật dữ liệu".
2. Admin rollback về bản mới nhất có `shipments_realistic.csv`. Cảnh báo ở `shipments` biến mất nếu đúng bản đó; kho trở lại 200 nhân viên, 80 shipper.

**Lưu ý:** thư mục `apps/retail_app` nằm trong `code_version`, nên sau khi sửa, bấm "Chạy lại để kiểm" sẽ chạy thật thay vì "Không có gì mới, bỏ qua". Đây là hành vi đúng.

## 6. Câu chưa chắc thì hỏi

Dừng và hỏi nếu phải đổi trạng thái yêu cầu, đổi `summary`, hoặc thêm bước ghi file để làm được việc này.

## 7. Kết quả (Claude code và tự kiểm, 2026-11-06)

**File đổi:** `apps/retail_app/ui/nhap_runner.py`, `views/duyet_du_lieu.py`, `views/gui_du_lieu.py`, `tests/test_nhap_du_lieu.py`, `tests/test_nhap_theo_doi.py`. File cuối là sửa sau lần PM thử 1, ghi ở cuối mục này.

**Thêm ngoài §2:**
- `doi_chieu_ban` và `nguon_dang_dung` trong `nhap_runner.py`, để logic §2 nằm một chỗ và test được không cần giao diện.
- Trang Duyệt: danh sách bản khôi phục đọc lỗi thì hiện cảnh báo. Trước đây `state.json` hỏng làm vỡ cả trang, trái §3 mục 6. Logic rollback không đổi.

**Trường hợp §2 chưa nói:** trang Gửi khi kho chưa có bản đang xem vẫn giữ "Đã cập nhật dữ liệu", vì không có bản nào để so. Giữ vậy để `test_nhap_theo_doi` không phải đổi kỳ vọng.

**Đã kiểm:** `test_nhap_du_lieu`, `test_nhap_tu_dong`, `test_nhap_theo_doi`, `test_extension_grants`: 326 đạt. 14 đột biến: test bắt 13, ca còn lại lộ ra thiếu test nên đã bổ sung và bắt được.

**PM thử trên app theo §5 (2026-11-06, lần 2, sau khi sửa lỗi ở dưới): đạt.**
- **Bước 1, rollback về `a52ba6b5`:**
  - thông báo đúng bản, ô xác nhận bỏ tick;
  - trang Duyệt của `shipments_realistic` có cảnh báo vàng "Số dưới đây là của bản 67a380a8, không phải bản đang xem (a52ba6b5)…";
  - trang Gửi ghi "Dữ liệu này đã từng được cập nhật nhưng hiện không nằm trong bản đang dùng.";
  - Claude kiểm kho: 200 nhân viên, không có `dim_shipper`.
- **Bước 2, về `67a380a8`:**
  - cảnh báo biến mất;
  - trang Gửi hiện lại "Đã cập nhật dữ liệu";
  - Claude kiểm kho: 200 nhân viên, 80 shipper.
- **Ghi nhận, chưa sửa:** tiêu đề khung trên trang Gửi vẫn ghi trạng thái "Đã cập nhật" của yêu cầu, theo đúng §2.

**PM thử lần 1 (2026-11-06) lộ lỗi cũ của khối Rollback, đã sửa:**
- **Lỗi:** sau một lần rollback thành công, trang không chạy lại. Trạng thái yêu cầu, cảnh báo và danh sách bản vẫn là số đọc *trước* rollback, và ô xác nhận vẫn tick. PM bấm Rollback thêm một lần nên kho đổi tiếp (22:02:49 về `a52ba6b5`, 22:03:38 về `67a380a8`); danh sách lúc đó thiếu `a52ba6b5`, vì nó là bản đang xem khi trang được vẽ.
- **Sửa ở `views/duyet_du_lieu.py`:**
  - rollback đạt thì ghi thông báo vào `session_state` rồi `st.rerun()`;
  - form mang khóa mới sau mỗi lần rollback, nên ô xác nhận về chưa tick;
  - thông báo ghi 8 ký tự đầu của bản.
- **Test:** `test_rollback_widget_sends_full_id` (`tests/test_nhap_theo_doi.py`) thêm kiểm: sau rollback có thông báo đúng bản, ô xác nhận bỏ tick, bấm lại không đổi bản. Test này trượt trên code cũ.
- **Kết quả:** bốn file test 326 đạt.
