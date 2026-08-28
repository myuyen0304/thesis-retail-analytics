# EDA — Câu chuyện dữ liệu và giá trị kinh doanh

> Phân tích khám phá bộ dữ liệu thương mại điện tử thời trang 2012–2022.
> Mọi con số đều tính trực tiếp từ dữ liệu gốc.
>
> Liên quan: [data-dictionary.md](data-dictionary.md) · [erd.svg](erd.svg) ·
> [quy-trinh-kiem-dinh.md](quy-trinh-kiem-dinh.md)
>
> **Đơn vị tiền:** dữ liệu là mô phỏng, đơn vị tiền tệ không xác định — ký hiệu *đvtt*.
> Doanh thu gộp 11 năm là **16,43 tỷ đvtt**. Mọi giá trị tuyệt đối chỉ nên dùng để so sánh
> tương đối; kết luận nên dựa trên **tỷ lệ và thứ hạng**.

---

## Mở đầu — Một doanh nghiệp mất gần một nửa doanh thu

Nhìn vào doanh thu 11 năm, câu chuyện có vẻ đơn giản và buồn:

| Năm | Doanh thu (tỷ) | Tăng trưởng | Biên LN gộp |
|---:|---:|---:|---:|
| 2013 | 1,66 | — | 11,54% |
| 2014 | 1,87 | +12,95% | 15,88% |
| 2015 | 1,89 | +0,97% | 11,88% |
| **2016** | **2,10** | **+11,36%** | 15,40% |
| 2017 | 1,91 | −9,19% | 11,34% |
| 2018 | 1,85 | −3,19% | 16,64% |
| **2019** | **1,14** | **−38,56%** | 11,58% |
| 2020 | 1,05 | −7,24% | 15,97% |
| 2021 | 1,04 | −1,09% | 9,77% |
| 2022 | 1,17 | +12,15% | 12,77% |

Doanh nghiệp đạt đỉnh năm 2016 với 2,10 tỷ, rồi rơi xuống 1,04 tỷ năm 2021 — **mất 50,5%**.
Năm 2022 mới hồi phục nhẹ.

Câu hỏi tự nhiên: **doanh nghiệp đã mất gì?** Khách mua ít tiền hơn mỗi lần, hay ít khách mua hơn?

---

## Chương 1 — Không phải khách chi ít đi, mà là ít người mua

Tách doanh thu thành hai thành phần cho ra kết quả **ngược với trực giác**:

| Năm | Số đơn hàng | Giá trị đơn TB |
|---:|---:|---:|
| 2013 | 76.849 | 21.564 |
| 2016 | 82.247 | 25.589 |
| 2019 | 41.601 | 27.326 |
| 2022 | **36.004** | **32.489** |

**Giá trị mỗi đơn hàng tăng đều đặn — từ 21.564 lên 32.489, tức +50,7%.** Khách hàng còn lại chi
nhiều tiền hơn bao giờ hết.

Nhưng **số đơn hàng sụp từ 82.247 xuống 36.004, mất 56,2%**.

> **Kết luận chương 1:** đây không phải khủng hoảng về sức mua. Đây là khủng hoảng về **số lượng khách
> giao dịch**. Doanh nghiệp không mất khả năng bán đắt — nó mất khả năng bán được cho nhiều người.

Phát hiện này thay đổi hoàn toàn hướng điều tra. Nếu chỉ nhìn doanh thu tổng, người ta dễ kết luận
"thị trường suy thoái, sức mua giảm" và đi giải bài toán sai.

---

## Chương 2 — Người vào cửa hàng vẫn đông, nhưng không ai mua

Nếu ít đơn hàng, liệu có phải vì ít người ghé thăm website? Dữ liệu lưu lượng cho câu trả lời **ngược
lại hoàn toàn**:

| Năm | Phiên truy cập TB/ngày | Đơn hàng TB/ngày | Tỷ lệ chuyển đổi |
|---:|---:|---:|---:|
| 2013 | 18.635 | 211 | **1,17%** |
| 2016 | 22.960 | 225 | 1,01% |
| 2018 | 25.795 | 190 | 0,72% |
| 2019 | 27.370 | 114 | 0,43% |
| 2022 | **30.311** | **99** | **0,33%** |

Đọc bảng này theo chiều dọc:

- **Lưu lượng truy cập tăng 62,7%** — từ 18.635 lên 30.311 phiên mỗi ngày
- **Số đơn hàng giảm 53,1%** — từ 211 xuống 99 đơn mỗi ngày
- **Tỷ lệ chuyển đổi sụp 71,8%** — từ 1,17% xuống 0,33%

> **Kết luận chương 2:** bộ phận marketing đang làm tốt việc kéo người vào. Vấn đề nằm **sau khi họ vào
> rồi**. Cứ 1.000 người ghé thăm năm 2013 thì 12 người mua; năm 2022 chỉ còn 3 người.

Đây là insight có giá trị kinh doanh cao nhất trong toàn bộ phân tích, vì nó **chỉ đúng chỗ cần sửa**.
Đổ thêm tiền vào quảng cáo để kéo traffic sẽ lãng phí — traffic vốn đã tăng. Vấn đề là chuyển đổi.

---

## Chương 3 — Thủ phạm: giá đã tăng 54%

Vì sao giá trị đơn hàng tăng? Có hai khả năng: khách mua nhiều món hơn, hoặc giá cao hơn. Dữ liệu loại
bỏ khả năng thứ nhất:

| Năm | Giá bán TB/sản phẩm | Số lượng TB/dòng | Số dòng hàng/đơn |
|---:|---:|---:|---:|
| 2012 | 4.459 | 4,49 | 1,155 |
| 2016 | 5.131 | 4,51 | 1,105 |
| 2019 | 5.628 | 4,51 | 1,080 |
| 2022 | **6.854** | 4,49 | **1,057** |

- **Số lượng mỗi dòng hàng đứng yên tuyệt đối** ở mức 4,49–4,51 suốt 11 năm
- **Số dòng hàng mỗi đơn thậm chí giảm nhẹ** từ 1,155 xuống 1,057
- **Giá bán trung bình tăng 53,7%** — từ 4.459 lên 6.854

> **Kết luận chương 3:** toàn bộ mức tăng giá trị đơn hàng đến từ **tăng giá**, không phải khách mua
> nhiều hơn. Ngược lại, giỏ hàng còn nhỏ đi.

Ghép ba chương lại thành một chuỗi nhân quả hoàn chỉnh:

```
Giá tăng 54%  →  Tỷ lệ chuyển đổi sụp 72%  →  Số đơn giảm 56%  →  Doanh thu mất 44%
                        ↑
        (lưu lượng truy cập vẫn tăng 63%, nên không phải do thiếu khách quan tâm)
```

Đây là kịch bản kinh điển: doanh nghiệp bù đắp doanh thu suy giảm bằng cách nâng giá, việc nâng giá lại
đẩy thêm khách đi, tạo thành vòng xoáy. Giá cao hơn khiến mỗi đơn có giá trị lớn hơn, nên nhìn vào chỉ
số giá trị đơn hàng trung bình thì thấy "tốt lên" — che mất vấn đề thật.

---

## Chương 4 — Cú sụp 2019 không chừa một ai

Năm 2019 doanh thu mất 38,56% chỉ trong một năm. Nếu do một dòng sản phẩm hỏng hoặc một kênh bán bị
mất, ta sẽ thấy mức giảm tập trung. Nhưng dữ liệu cho thấy điều ngược lại:

**Theo danh mục sản phẩm (2018 → 2019):**

| Danh mục | Tăng trưởng |
|---|---:|
| GenZ | −55,4% |
| Streetwear | −39,3% |
| Casual | −38,2% |
| Outdoor | −28,4% |

**Theo kênh bán (2018 → 2019):**

| Kênh | Tăng trưởng |
|---|---:|
| email_campaign | −41,0% |
| social_media | −39,9% |
| referral | −39,1% |
| organic_search | −37,7% |
| direct | −37,4% |
| paid_search | −37,3% |

Sáu kênh giảm trong khoảng rất hẹp **−37,3% đến −41,0%**. Bốn danh mục cũng giảm đồng loạt.

> **Kết luận chương 4:** mức giảm đồng đều đến mức này loại trừ nguyên nhân cục bộ. Không phải một kênh
> quảng cáo bị cắt, cũng không phải một dòng sản phẩm hết hàng. Đây là **cú sốc toàn hệ thống** — thay
> đổi chính sách giá, mất nguồn cung, hoặc đối thủ mới chiếm thị phần.

Về mặt mô hình dự báo, điểm gãy này rất quan trọng: **ước lượng xu hướng trên toàn bộ 2013–2022 sẽ cho
kết quả sai lệch**, vì trung bình hóa qua một điểm đứt. Mức nền 2020–2022 là căn cứ hợp lý hơn.

---

## Chương 5 — Cứ 100 đồng ghi nhận thì 17 đồng bốc hơi

Doanh thu gộp 11 năm là 16,43 tỷ đvtt. Nhưng không phải toàn bộ số đó về túi doanh nghiệp:

| Khoản thất thoát | Giá trị (tỷ đvtt) | % doanh thu gộp |
|---|---:|---:|
| Đơn bị hủy | 1,52 | **9,23%** |
| Đơn bị trả lại | 0,91 | 5,52% |
| Giảm giá khuyến mại | 0,75 | 4,56% |
| *(Tiền hoàn trả thực tế)* | *0,51* | *3,11%* |
| **Doanh thu thực sự giữ lại** | **13,65** | **83,10%** |

Khoản lớn nhất là **hủy đơn: 9,23%**, gấp gần ba lần tổn thất do trả hàng. Đây là loại thất thoát rẻ
nhất để khắc phục — đơn bị hủy chưa tốn chi phí giao vận, chỉ tốn chi phí thu hút khách.

> **Hàm ý kinh doanh:** giảm tỷ lệ hủy đơn từ 9,23% xuống 5% sẽ thu về khoảng **695 triệu** trong cùng
> khoảng thời gian — nhiều hơn toàn bộ ngân sách giảm giá 11 năm cộng lại.

Cần lưu ý một đặc điểm kế toán quan trọng đã phát hiện khi lập từ điển dữ liệu: **biến `Revenue` trong
dữ liệu tính gộp cả đơn đã hủy và đơn bị trả lại**. Nghĩa là con số doanh thu công bố cao hơn doanh thu
thực nhận khoảng 17%. Khi diễn giải kết quả dự báo, phải nói rõ đang dự báo *giá trị đặt hàng*, không
phải *doanh thu ghi nhận theo chuẩn kế toán*.

---

## Chương 6 — Hai phần ba danh mục sản phẩm chưa từng bán được món nào

| Chỉ tiêu | Kết quả |
|---|---:|
| Tổng số mã sản phẩm | 2.412 |
| Từng phát sinh giao dịch | 1.598 (66,3%) |
| **Chưa từng bán được** | **814 (33,7%)** |
| Top 10% mã bán chạy đóng góp | **65,4%** doanh thu |
| Top 20% mã bán chạy đóng góp | **81,8%** doanh thu |
| 50% mã yếu nhất đóng góp | **3,0%** doanh thu |

Phân bố này còn cực đoan hơn quy luật Pareto 80/20 thông thường: chỉ **10%** số mã đã tạo ra **65%**
doanh thu.

**Cơ cấu theo danh mục cho thấy một nghịch lý:**

| Danh mục | Tỷ trọng doanh thu | Biên lợi nhuận gộp |
|---|---:|---:|
| Streetwear | **79,92%** | **13,24%** |
| Outdoor | 15,18% | 16,37% |
| Casual | 2,80% | 11,75% |
| GenZ | 2,09% | **19,13%** |

> **Nghịch lý:** danh mục bán chạy nhất lại là danh mục **biên lợi nhuận gần thấp nhất**. Còn `GenZ` có
> biên cao nhất 19,13% thì chỉ chiếm 2,09% doanh thu.

Đây là lý do biên lợi nhuận gộp toàn hệ thống chỉ đạt **13,8%**, dù biên lý thuyết trung vị của danh mục
sản phẩm là 19,78%. Doanh nghiệp đang dồn lực bán thứ ít lời nhất.

**Hàm ý:** dịch chuyển 10 điểm phần trăm doanh thu từ `Streetwear` sang `GenZ` sẽ nâng biên lợi nhuận
gộp thêm khoảng 0,6 điểm phần trăm — tương đương **99 triệu** lợi nhuận tăng thêm trên tổng doanh thu 11
năm, mà không cần bán thêm một đồng doanh thu nào.

---

## Chương 7 — Khuyến mại không tạo ra doanh thu

Doanh nghiệp chạy 50 chương trình khuyến mại, phủ **1.707 trên 3.833 ngày (44,5%)**, chi 750 triệu tiền
giảm giá. Câu hỏi: có hiệu quả không?

**So sánh thô:**

| Loại ngày | Doanh thu TB/ngày |
|---|---:|
| Ngày có khuyến mại | 3.990.789 |
| Ngày không khuyến mại | 4.524.083 |
| **Chênh lệch** | **−11,8%** |

Ngày có khuyến mại doanh thu lại **thấp hơn**. Nhưng so sánh này chưa công bằng, vì khuyến mại có thể
rơi vào mùa thấp điểm. Nên em so sánh **trong cùng tháng** để loại bỏ ảnh hưởng mùa vụ:

| Tháng | Chênh lệch ngày có KM |
|---:|---:|
| 3 | +67,1% |
| 1 | +28,5% |
| 10 | +13,1% |
| 6 | +9,8% |
| 2 | +1,8% |
| 11 | −10,5% |
| 9 | −13,1% |
| 7 | −20,6% |
| 4 | −27,0% |
| 8 | −29,7% |
| 12 | −34,7% |

Kết quả **lẫn lộn**: 5 tháng dương, 6 tháng âm, biên độ dao động rất rộng.

Kiểm chứng thêm ở mức dòng hàng:

| Chỉ tiêu | Có khuyến mại | Không khuyến mại |
|---|---:|---:|
| Số lượng TB mỗi dòng | **4,49** | **4,50** |
| Giá trị gộp TB mỗi dòng | 19.671 | 25.083 |

> **Kết luận chương 7:** **không tìm thấy bằng chứng khuyến mại làm tăng doanh thu.** Số lượng mua trung
> bình giống hệt nhau (4,49 so với 4,50) — khuyến mại không khiến khách mua nhiều hơn. Và khuyến mại
> đang gắn vào những dòng hàng vốn có giá trị thấp hơn.

Em dùng từ *"không tìm thấy bằng chứng"* thay vì *"khuyến mại phản tác dụng"*, vì phân tích này không
kiểm soát được các yếu tố khác. Nhưng với 750 triệu đã chi, việc **không chứng minh được hiệu quả** đã đủ
là một cảnh báo đáng để doanh nghiệp thiết kế thử nghiệm A/B nghiêm túc trước khi tiếp tục.

---

## Chương 8 — Giao hàng nhanh không làm giảm trả hàng

Giả thuyết thông thường: giao càng lâu, khách càng dễ đổi ý và trả hàng. Dữ liệu bác bỏ:

| Tổng thời gian từ đặt đến nhận | Tỷ lệ bị trả | Số đơn |
|---:|---:|---:|
| 2 ngày | 6,21% | 23.670 |
| 4 ngày | 6,41% | 70.824 |
| 6 ngày | 6,46% | 94.223 |
| 8 ngày | 6,36% | 70.466 |
| 10 ngày | 6,08% | 23.502 |

Tỷ lệ trả hàng dao động trong khoảng rất hẹp **6,08%–6,51%**, không có xu hướng tăng theo thời gian
giao. Đơn giao trong 2 ngày bị trả gần bằng đơn giao trong 10 ngày.

> **Hàm ý kinh doanh:** đầu tư rút ngắn thời gian giao hàng sẽ **không** làm giảm tỷ lệ trả hàng. Nếu
> muốn giảm trả hàng, phải tấn công vào nguyên nhân khác — mà lý do trả hàng phổ biến nhất là
> **`wrong_size`** (sai kích cỡ). Cải thiện bảng hướng dẫn chọn size, ảnh chụp sản phẩm và mô tả sẽ
> hiệu quả hơn nhiều so với đầu tư vào logistics.

---

## Chương 9 — Tin tốt: khách đã mua thì khá trung thành

Giữa bức tranh ảm đạm, tệp khách hàng lại là điểm sáng:

| Nhóm khách | Số lượng | Tỷ lệ |
|---|---:|---:|
| Mua đúng 1 lần | 22.358 | 24,8% |
| Mua 2–4 lần | 27.028 | 29,9% |
| **Mua từ 5 lần trở lên** | **40.860** | **45,3%** |

**45,3% khách từng mua đã quay lại từ 5 lần trở lên** (40.860 trên 90.246) — tỷ lệ mua lại rất cao so với mặt bằng thương mại điện tử.
Top 20% khách hàng đóng góp **60,6%** doanh thu.

Nhưng cũng có khoảng trống lớn: **31.684 khách hàng (26,0%) đã đăng ký tài khoản nhưng chưa từng mua**.

> **Hàm ý:** doanh nghiệp giữ chân tốt nhưng chuyển đổi kém — khớp hoàn toàn với phát hiện ở chương 2.
> Ai đã vượt qua được lần mua đầu tiên thì ở lại lâu dài. Vấn đề nằm ở **rào cản lần mua đầu**, và nhóm
> 31.684 khách đã đăng ký mà chưa mua chính là tệp dễ khai thác nhất.

---

## Chương 10 — Mùa vụ ngược quy luật ngành

| Tháng | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Chỉ số | 0,60 | 0,81 | 1,15 | **1,52** | **1,53** | **1,50** | 1,09 | 1,04 | 0,89 | 0,77 | 0,61 | **0,59** |

Doanh thu đạt đỉnh **tháng 4–6** (cao hơn trung bình 50%) và chạm đáy **tháng 11–1** (thấp hơn 40%).
Biên độ giữa tháng cao nhất và thấp nhất là **2,60 lần**.

Điều này **ngược với quy luật bán lẻ thời trang thông thường**, vốn đạt đỉnh vào mùa mua sắm cuối năm.

Về mặt dự báo, đây là thành phần mạnh nhất của chuỗi — mùa vụ chiếm ưu thế hơn cả xu hướng. Mô hình bắt
được mùa vụ tháng sẽ giải thích được phần lớn biến động.

---

## Tổng hợp — Năm khuyến nghị theo thứ tự ưu tiên

| # | Khuyến nghị | Căn cứ | Giá trị ước tính |
|---:|---|---|---|
| 1 | **Điều tra và khắc phục tỷ lệ chuyển đổi** thay vì đổ tiền vào quảng cáo | CVR sụp 72% trong khi traffic tăng 63% | Khôi phục CVR về 0,7% sẽ gấp đôi số đơn |
| 2 | **Xem lại chính sách giá** | Giá tăng 54%, giỏ hàng nhỏ đi, khách rời bỏ | Nguyên nhân gốc của chuỗi suy giảm |
| 3 | **Giảm tỷ lệ hủy đơn** từ 9,23% | Khoản thất thoát lớn nhất, rẻ nhất để sửa | ~695 triệu nếu giảm về 5% |
| 4 | **Tái cơ cấu danh mục** sang nhóm biên cao | Streetwear 80% doanh thu nhưng biên chỉ 13,24% | ~99 triệu lợi nhuận nếu dịch 10 điểm % |
| 5 | **Dừng khuyến mại đại trà, chuyển sang thử nghiệm có đối chứng** | Không có bằng chứng hiệu quả, đã chi 750 triệu | Tiết kiệm ngân sách giảm giá |

Hai việc **không nên** làm, vì dữ liệu cho thấy sẽ lãng phí:

- **Đầu tư tăng lưu lượng truy cập** — lưu lượng đã tăng 63% mà đơn hàng vẫn giảm
- **Đầu tư rút ngắn thời gian giao hàng để giảm trả hàng** — tỷ lệ trả hàng không phụ thuộc thời gian giao

---

## Hàm ý cho bài toán dự báo

Phân tích này định hướng ba quyết định mô hình hóa:

1. **Không huấn luyện trên toàn bộ 2013–2022.** Điểm gãy 2019 khiến việc ước lượng xu hướng trên toàn
   chuỗi bị sai lệch. Mức nền 2020–2022 phản ánh đúng trạng thái hiện tại hơn.
2. **Ưu tiên mô hình hóa mùa vụ tháng.** Biên độ 2,60 lần khiến đây là thành phần giải thích mạnh nhất,
   mạnh hơn cả xu hướng.
3. **Dự báo `Revenue` rồi suy ra `COGS` qua biên lợi nhuận**, thay vì dự báo hai chuỗi độc lập. Hai
   chuỗi có hệ số tương quan 0,976, và cách làm này đảm bảo `COGS` không bao giờ vượt `Revenue`.

---

## Giới hạn của phân tích

Cần nêu rõ để tránh diễn giải quá đà:

**Về bản chất dữ liệu.** Nhiều dấu hiệu cho thấy đây là **dữ liệu mô phỏng** chứ không phải dữ liệu vận
hành thực: toàn vẹn tham chiếu tuyệt đối trên 4,8 triệu bản ghi, số lượng mua phân bố đều gần như hoàn
hảo trên 8 mức, các trần cứng về thời gian giao vận, không có một dòng hàng nào vừa được đánh giá vừa bị
trả lại, và mùa vụ ngược quy luật ngành. Các khuyến nghị kinh doanh ở trên vì vậy mang **giá trị minh
họa phương pháp phân tích**, không nên áp dụng trực tiếp cho một doanh nghiệp thật.

**Về quan hệ nhân quả.** Phân tích chỉ ra tương quan giữa tăng giá và sụt giảm chuyển đổi, nhưng dữ liệu
quan sát không đủ để khẳng định nhân quả. Muốn kết luận chắc chắn phải có thử nghiệm có đối chứng.

**Về `signup_date`.** Do 73,8% đơn hàng có ngày đặt trước ngày đăng ký tài khoản, mọi phân tích theo
đoàn hệ đăng ký đều không thực hiện được. Phần phân tích khách hàng ở chương 9 vì vậy dựa trên số lần
mua thực tế, không dựa trên ngày đăng ký.
