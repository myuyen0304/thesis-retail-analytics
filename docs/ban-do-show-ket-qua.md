# Bản đồ trình bày — slide nào show kết quả nào

> Dùng kèm [`Data-Cleaning-Slides.pptx`](../Data-Cleaning-Slides.pptx) và
> [`Data-Cleaning.ipynb`](../Data-Cleaning.ipynb).
> Mỗi khi giảng viên nói *"cho xem kết quả"*, tra bảng này để biết mở đúng chỗ.

---

## 0. Chuẩn bị trước khi vào phòng

**Mở sẵn hai cửa sổ, chuyển qua lại bằng `Alt + Tab`:**

| Cửa sổ | Nội dung |
|---|---|
| 1 | PowerPoint — `Data-Cleaning-Slides.pptx`, chế độ trình chiếu |
| 2 | VS Code — `Data-Cleaning.ipynb`, đã chạy sẵn |

**Chạy `Restart & Run All` một lần TRƯỚC buổi báo cáo**, rồi để nguyên đó. Lý do: ô `In [1]`
nạp gần 3 triệu dòng. Nếu giảng viên yêu cầu chạy lại một ô mà nhân (kernel) chưa có dữ liệu
thì sẽ báo lỗi tên biến. Chạy sẵn từ đầu thì lúc đó chỉ cần `Ctrl + Enter` là ô nào cũng
chạy lại được ngay.

**Phương án dự phòng:** nếu máy phòng học không mở được Jupyter, mở
[`Data-Cleaning.html`](../Data-Cleaning.html) bằng trình duyệt — nội dung y hệt, đã kèm sẵn
mọi kết quả, không cần cài gì.

---

## 1. Bảng tra nhanh

Số `In [n]` chính là số hiện bên trái mỗi ô code trong notebook.

| Slide | Nội dung slide | Mở gì | Chỉ vào con số nào |
|:--:|---|---|---|
| 1 | Trang bìa | — | Không cần show |
| 2 | Bộ dữ liệu đầu vào | `In [1]` | `14 bang \| 2,960,736 dong \| 96 cot` |
| 3 | Bronze → Silver → Gold | Cửa sổ thư mục | Hai thư mục `data/` và `data_clean/` nằm cạnh nhau |
| 4 | 17 cảnh báo | `Dictionary-va-ERD.ipynb` | Phần cảnh báo chất lượng của **bước trước** |
| 5 | Tám nhóm thao tác | Cuộn notebook từ trên xuống | Tám tiêu đề `Bước 1` … `Bước 8` |
| 6 | ★ Khóa thay thế | `In [3]` | `bi trung: 16` → `duy nhat: True` |
| 7 | Hằng số / dư thừa / suy diễn | `In [4]` `In [5]` `In [6]` | Ba danh sách cột bị loại |
| 8 | ★ Giá trị thiếu có ngữ nghĩa | `In [7]` | `Dien 40 o trong … thanh nhan ALL` |
| 9 | ★ signup_date | `In [8]` | `Truoc: 73.8 %` → `Sau: 0 %` |
| 10 | SKU chết | `In [9]` | Giá trung vị `37,21` so với `5.505,13` |
| 11 | Quy tắc quyết định | `data_clean/_nhat_ky_lam_sach.csv` | Cột `Thao tac` — thấy đủ 4 loại quyết định |
| 12 | Kết quả | `In [12]` | `TONG COT : 96 -> 84 (-12)` |
| 13 | ★★ Hai bất biến | `In [10]` và `In [11]` | `0 mo coi` · `sai so = 0.0` |
| 14 | Phương pháp | [`lam-sach-du-lieu.md`](lam-sach-du-lieu.md) | Mục 3 — căn cứ từng thao tác |
| 15 | Kết luận | `In [13]` | `Tong so thao tac: 22` |

---

## 2. Bốn chỗ đáng dừng lâu

Bốn ô dưới đây là nơi ăn điểm. Ba slide còn lại nói nhanh cũng được.

### `In [10]` + `In [11]` — hai bất biến

> **Đây là chỗ quan trọng nhất cả bài. Nếu chỉ được show một thứ, show cái này.**

Kết quả trên màn hình:

```
TONG: 4,054,768 ban ghi | 0 mo coi
```
```
Revenue: sai so tuyet doi lon nhat = 0.0
COGS   : sai so tuyet doi lon nhat = 0.0
So ngay khop chinh xac: 3833 / 3833
```

**Cách nói:**

> *"Em làm sạch xong thì phải chứng minh là không phá vỡ gì. Em đặt trước hai đại lượng
> buộc phải giữ nguyên. Thứ nhất là toàn vẹn tham chiếu — chạy lại vẫn 0 bản ghi mồ côi
> trên 4 triệu bản ghi. Thứ hai là biến mục tiêu — em dựng lại sales.csv từ dữ liệu đã làm
> sạch, sai số vẫn bằng 0 trên cả 3.833 ngày. Nghĩa là em không làm hỏng cái đang đi dự báo."*

`In [10]` còn in ra bảng 12 dòng, mỗi dòng một khóa ngoại, cột `Mo coi` toàn số 0. Nếu
giảng viên muốn xem chi tiết thì chỉ vào bảng đó.

---

### `In [3]` — khóa thay thế

Kết quả trên màn hình:

```
So cap (order_id, product_id) bi trung: 16
Da them khoa thay the order_item_id — duy nhat: True
```

Bên dưới là 3 dòng đầu của bảng, **cột `order_item_id` nằm ngoài cùng bên trái** — cho thấy
cột mới đã được thêm thật.

**Cách nói:**

> *"Bảng này có 16 cặp bị trùng nên không có khóa hợp lệ. Nối bảng bằng cặp đó sẽ nhân dòng
> và làm doanh thu phồng lên, mà chương trình không hề báo lỗi. Em thêm khóa thay thế,
> kiểm tra lại thì duy nhất — True."*

---

### `In [8]` — signup_date

Kết quả trên màn hình:

```
Truoc khi sua:  73.8 % don dat TRUOC ngay dang ky
Sau khi sua:  0 % (theo dinh nghia, first_order_date <= moi don cua khach)
Khach da tung mua: 90,246 / 121,930
```

Đây là kiểu **trước / sau trên cùng một phép đo** — dễ thuyết phục nhất. Bên dưới là bảng
`customers` đã có cột `first_order_date` và `da_tung_mua`, không còn `signup_date`.

**Cách nói:**

> *"73,8% đơn đặt trước ngày đăng ký — bất khả thi. Em thay bằng ngày mua đầu tiên tính từ
> bảng orders. Đo lại cùng phép đo đó thì còn 0%."*

---

### `In [9]` — SKU chết

Kết quả trên màn hình:

```
SKU chua tung ban: 814 / 2412 = 33.7 %
Gia trung vi theo nhom:
da_tung_ban
0      37.21
1    5505.13
```

> **Hai con số này chưa có trên slide — nhưng là bằng chứng mạnh nhất của bước 8.**
> Sản phẩm chưa bán bao giờ có giá trung vị **37,21**, sản phẩm đã bán là **5.505,13** —
> chênh nhau gần **150 lần**.

**Cách nói:**

> *"Không phải em đoán 814 sản phẩm này bất thường. Giá trung vị của chúng là 37, trong khi
> nhóm đã bán là 5.505 — chênh gần 150 lần. Để lẫn vào thì mọi thống kê về giá đều lệch.
> Nhưng em không xóa, vì bảng inventory vẫn tham chiếu tới chúng — xóa là tạo ra bản ghi
> mồ côi. Em đánh dấu bằng cờ để lọc khi cần."*

---

## 3. Nếu giảng viên bảo "chạy lại cho tôi xem"

**Đừng bấm `Restart & Run All`** — ô `In [1]` nạp 3 triệu dòng, ngồi chờ trước mặt giảng
viên rất mất thế.

Thay vào đó, với notebook đã chạy sẵn từ trước buổi báo cáo:

1. Bấm vào ô muốn chạy lại
2. `Ctrl + Enter`
3. Kết quả hiện ra ngay, vì dữ liệu đã nằm sẵn trong nhân

Hai ô an toàn nhất để chạy lại tại chỗ: **`In [10]`** và **`In [11]`** — chỉ vài giây, và
chính là hai phép kiểm chứng đáng khoe nhất.

> Nếu ô nào báo lỗi `NameError`, nghĩa là nhân đã bị khởi động lại. Lúc đó nói thẳng:
> *"nhân bị reset, để em chạy lại từ đầu"*, rồi `Restart & Run All` — kết quả cũ vẫn còn
> trong file HTML nếu cần đối chiếu.

---

## 4. Bốn câu hỏi khó và chỗ show tương ứng

| Câu hỏi | Mở gì | Trả lời |
|---|---|---|
| *"Căn cứ nào để xóa cột?"* | `_nhat_ky_lam_sach.csv` | Cột `Can cu` — mỗi thao tác một dòng lý do |
| *"Sao không dùng thư viện tự động?"* | `In [7]` | Thư viện không biết ô trống nghĩa là *áp dụng mọi danh mục* |
| *"Sao chưa xử lý ngoại lai?"* | Slide 3 | Đó là việc của lớp Gold, không phải Silver |
| *"Chắc gì làm sạch xong vẫn đúng?"* | `In [10]` `In [11]` | Hai bất biến |

---

## 5. Thứ tự thao tác gọn nhất

Nếu chỉ có 10 phút, đi đúng mạch này:

1. **Slide 2** → nhảy sang `In [1]` — *"đây là quy mô thật"*
2. **Slide 4** → nói nguyên tắc, không cần mở gì
3. **Slide 6** → `In [3]` — lỗi nguy hiểm nhất
4. **Slide 8** → `In [7]` — chỗ dễ sai nhất
5. **Slide 9** → `In [8]` — trước 73,8% / sau 0%
6. **Slide 12** → `In [12]` — 96 → 84, không mất dòng
7. **Slide 13** → `In [10]` `In [11]` — **kết bài ở đây**

Bốn lần chuyển sang notebook là đủ. Chuyển nhiều quá sẽ đứt mạch nói.
