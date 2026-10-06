# Statement chốt scope khóa luận

**Trình bày giảng viên hướng dẫn · 07/09/2026 · bản 1**

Tài liệu này chốt lại phạm vi khóa luận sau khi toàn bộ số liệu nền được tính lại trực tiếp
trên dữ liệu gốc (714.669 dòng `order_items`, đối chiếu chéo `payments` và `sales.csv`).
Kết quả kiểm chứng làm thay đổi trọng tâm đề tài, nên em xin trình bày lại từ đầu.

---

## 1. Đề nghị điều chỉnh tên đề tài

**Tên hiện tại:** *Xây dựng hệ thống hỗ trợ ra quyết định kinh doanh cho doanh nghiệp thời trang
thương mại điện tử dựa trên Retail Data Warehouse*

**Vì sao xin đổi.** Tên hiện tại đặt trọng tâm ở việc *xây hệ thống*. Nhưng sau khi kiểm chứng
dữ liệu, phần có giá trị nghiên cứu không nằm ở kiến trúc kho dữ liệu — đó là công việc kỹ thuật
đã có lời giải chuẩn — mà nằm ở một câu hỏi kinh tế chưa trả lời được trên bộ dữ liệu này.
Kho dữ liệu vẫn được xây, nhưng đúng vai trò của nó: **hạ tầng phục vụ phân tích**, không phải
đóng góp khoa học.

**Hai phương án tên đề xuất** (đều giữ lại nền tảng kỹ thuật để không lệch quá xa tên cũ):

1. *Đo lường tác động gia tăng của chương trình khuyến mãi đến lợi nhuận doanh nghiệp thời trang
   thương mại điện tử: tiếp cận phản thực trên nền Retail Data Warehouse*
2. *Đánh giá hiệu quả kinh tế của khuyến mãi trong thương mại điện tử thời trang bằng phương pháp
   phản thực trên Modern Data Stack*

---

## 2. Problem statement

**Bản một câu (dùng cho slide):**

> Doanh nghiệp cho đi khoảng một phần ba giá trị đơn hàng trên 38% số đơn để đổi lấy mức tăng
> sản lượng một chữ số, và hiện không có cơ sở nào để biết khoản chi đó lời hay lỗ.

**Bản chuẩn (phần Đặt vấn đề):**

> **Bối cảnh.** Doanh nghiệp thời trang thương mại điện tử, 646.945 đơn hàng giai đoạn
> 2012–2022, doanh thu suy giảm với CAGR −3,80%/năm.
>
> **Quan sát mâu thuẫn.** Khuyến mãi được áp lên 38,4% số đơn với độ sâu chiết khấu thực
> 31,6%. Ở mức đó, 69,8% đơn có khuyến mãi được bán dưới giá vốn. Đổi lại, ngày có chiến dịch
> chỉ nhiều hơn 8,5% số đơn và giỏ hàng chỉ nhiều hơn 1,4% sản phẩm.
>
> **Quyết định đang bị kẹt.** Bộ phận tăng trưởng quyết định độ sâu chiết khấu mỗi quý và đánh
> giá hiệu quả bằng mức tăng doanh thu quan sát được trong kỳ chiến dịch — một đại lượng **luôn
> dương**, vì đơn có khuyến mãi tự chọn chính nó vào nhóm được đo.
>
> **Khoảng trống tri thức.** Chưa tồn tại đường cơ sở phản thực trả lời câu hỏi *"nếu không chạy
> chiến dịch thì doanh thu là bao nhiêu"*. Không có nó thì không phân biệt được ba cơ chế có hàm ý
> chính sách trái ngược nhau: **tăng trưởng thật**, **trợ giá cho phần cầu vốn đã có**, và **kéo
> cầu tương lai về hiện tại**.
>
> **Hệ quả nếu không giải.** Doanh nghiệp tiếp tục chi một phần ba giá trị đơn hàng trên gần 40%
> số đơn, trong khi lập luận biện minh duy nhất — *"khách kéo về bằng khuyến mãi có vòng đời tốt
> hơn"* — đã được kiểm tra và **không đứng vững** (mục 6).

---

## 3. Bằng chứng vấn đề có thật — đã tính lại trên dữ liệu gốc

| Phát biểu | Giá trị đo được | Trạng thái |
|---|---|---|
| Tỷ lệ đơn có khuyến mãi | 38,36% | đã kiểm chứng |
| Độ sâu chiết khấu thực (trung vị) | 31,6% | đã kiểm chứng |
| Tỷ lệ đơn khuyến mãi bán dưới giá vốn | 69,8% | đã kiểm chứng |
| Sản lượng tăng thêm ngày có chiến dịch | +8,5% đơn · +1,4% sản phẩm/đơn | đã kiểm chứng, **chưa kiểm soát mùa vụ** |
| COGS/Revenue quý 3 các năm lẻ | 1,036 (năm chẵn 0,846) | đã kiểm chứng — **tổng hợp cả quý**, chưa tách riêng theo từng chiến dịch |

**Cơ chế giải thích.** Chiết khấu được áp **hai lớp**: một lần vào `unit_price`
(`unit_price = price × (1 − d)`), một lần nữa vào `discount_amount`
(`d × quantity × unit_price`), cho độ sâu thực `1 − (1 − d)²`. Báo cáo chỉ đọc lớp thứ hai
nên báo thiếu khoảng 2,6 lần. Đây là phát hiện làm thay đổi công thức của bốn chỉ số trong bài.

> **Về mức độ tin cậy.** Công thức hai lớp ở trên là **cấu trúc sinh dữ liệu được tái dựng**,
> không phải một trường có sẵn trong schema. Căn cứ để tin: `sales.csv` khớp tới từng đồng với
> `Σ(quantity × unit_price)`, và tỷ số `unit_price / price` khớp đúng `1 − discount_value` ở cả
> sáu chiến dịch. Toàn bộ mức hiệu chỉnh 2,6 lần đứng trên phép đối chiếu này, nên em xin nêu rõ
> để thầy/cô kiểm tra trước.

---

## 4. Câu hỏi nghiên cứu và giả thuyết then chốt

**RQ trung tâm.** Trong cửa sổ chiến dịch, bao nhiêu phần doanh thu là **gia tăng thật** so với
đường cơ sở phản thực, và lợi nhuận gia tăng đó có bù được chi phí chiết khấu không?

**H2′ — giả thuyết then chốt**

- **H₀:** Promo Profit ROI ≥ 1,0 — lợi nhuận gia tăng bù được chi phí chiết khấu.
- **H₁:** ROI < 1,0 — chương trình khuyến mãi phá hủy giá trị ròng.
- **Kiểm định:** dựng baseline phản thực bằng mô hình *calendar-only* huấn luyện **chỉ trên các
  kỳ không có chiến dịch**, dự báo vào cửa sổ chiến dịch; incremental = thực tế − baseline;
  khoảng tin cậy bằng block bootstrap.
- **Quy tắc quyết định:** chỉ kết luận khi baseline đạt WAPE ≤ 18% (vượt seasonal naive ≥ 30%;
  naive hiện ở 24,9–26,1%). Nếu ROI < 1,0 với CI không chứa 1,0 → khuyến nghị thu hẹp chương
  trình, và câu hỏi chuyển thành *tìm độ sâu chiết khấu tối ưu* thay vì bỏ hẳn.

**H3 — giả thuyết phụ, phục vụ khuyến nghị chính sách.** Tồn tại ngưỡng chiết khấu `d*` mà trên
đó lợi nhuận đóng góp đổi dấu. Dải quan sát: p5 = 18,1% · p50 = 31,6% · p95 = 50,5%.

---

## 5. Phạm vi — một bài toán gốc, sáu nhánh

| Nhánh | Vai trò trong khóa luận |
|---|---|
| **N2 — Khuyến mãi có tạo đơn gia tăng không?** | **Chương phân tích trung tâm.** Counterfactual baseline + DiD + spline tìm `d*` |
| N1 — Chốt định nghĩa doanh thu | **Hạ tầng**, làm trước tiên. Không phải chương phân tích riêng |
| N3 — Vòng đời khách khuyến mãi | Kiểm tra lập luận *"đầu tư giữ chân"*. Kaplan–Meier + PSM |
| N5 — Kênh nào mang về khách khuyến mãi | Khuyến nghị hành động. So sánh first-touch / last-touch |
| N4 — Hết hàng có phải nguyên nhân? | **Đã loại.** Case study lỗi nhị phân hóa chỉ số |
| N6 — Lưu lượng web có giải thích được không? | **Đã loại.** Hai chuỗi độc lập (tương quan sai phân +0,0105) |

**Mạch trình bày:** N1 chốt định nghĩa → **N2 là chương nhân quả trung tâm** → N3 kiểm tra lập
luận giữ chân → N5 khuyến nghị hành động. N4 và N6 giữ lại như hai nhánh **bị loại có bằng
chứng** — năng lực loại bỏ giả thuyết cũng là một kết quả nghiên cứu.

---

## 6. Những gì em đã tự bác bỏ

Em xin báo cáo cả phần sai, vì nó ảnh hưởng tới các con số đã trình bày trước đây:

1. **"Biên lợi nhuận co từ 22% xuống 14% trong 9 năm"** — sai. Biên dao động 9,8–16,6% theo chu
   kỳ năm chẵn/lẻ, bám cường độ khuyến mãi; 2022 (12,8%) còn **cao hơn** 2013 (11,5%). Con số 22%
   là artefact của năm 2012 chỉ có nửa năm và không chạy chiến dịch nào.
2. **"Khách khuyến mãi có số đơn trọn đời thấp hơn 39%"** — **rút lại**. Đây là nghịch lý Simpson:
   `promotions.csv` chỉ bắt đầu từ 2013, nên 22.068 khách cohort 2012 bị gán nhãn non-promo *theo
   cấu trúc dữ liệu* và có 10,5 năm tích lũy đơn. Bỏ cohort 2012 ra, khoảng cách còn −3,6%.
3. **"Traffic tăng, engagement không giảm"** — ngược lại. Số đơn trên 1.000 phiên rơi từ 11,30
   xuống 3,25 (−71%).

---

## 7. Hạn chế đã biết, xin nêu trước

- **Không có kỳ đối chứng sạch.** Lịch khuyến mãi phủ 46,7% số ngày 2013–2022; tháng 9 và tháng 12
  phủ 100%. Vì vậy baseline bắt buộc phải là *calendar-only*, không thể lấy "kỳ không promo" làm
  đối chứng trực tiếp.
- **Chỉ có sáu mức chiết khấu rời rạc** ứng với sáu chiến dịch → khoảng tin cậy của `d*` sẽ rộng;
  nếu CI vượt ra ngoài dải quan sát thì không ngoại suy.
- **Không có dữ liệu chi phí marketing** → mọi so sánh ROI giữa kênh chỉ là so sánh tương đối.
- **Cỡ mẫu DiD nhỏ** (n = 40 quý) → báo cáo khoảng tin cậy, không chỉ p-value.
- **Dữ liệu là synthetic** (VinDatathon 2026) và đơn vị tiền không xác định → ưu tiên tỷ lệ và
  thứ hạng hơn giá trị tuyệt đối.
- **Trạng thái chứng minh.** Các con số trên hiện tái lập được bằng `scripts/verify/verify_problem_to_kpi.py`.
  Theo quy ước của repo, mỗi khẳng định phải có một cell notebook sở hữu nó — phần này em đang
  chuyển sang notebook.

---

## 8. Xin ý kiến thầy/cô ba điểm

1. **Tên đề tài** — em xin điều chỉnh tên theo một trong hai phương án ở mục 1. Thầy/cô thấy
   phương án nào sát hơn với định hướng của bộ môn?
2. **Độ sâu phương pháp nhân quả** — DiD cộng counterfactual baseline đã đủ cho khóa luận ở bậc
   này chưa, hay cần bổ sung synthetic control / propensity score matching?
3. **Hai nhánh bị loại (N4, N6)** — nên giữ trong luận văn như bằng chứng về quá trình sàng lọc
   giả thuyết, hay cắt bớt để tập trung?
