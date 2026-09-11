# Kịch bản thuyết trình — Bài toán D2

> Dùng kèm [`D2-Slides.pptx`](../D2-Slides.pptx) (23 slide).
> Tổng thời lượng khi nói đủ: **18 phút 30 giây**.
>
> Phần *Lời nói* là văn nói, đọc trôi được. Phần *Thao tác* là ghi chú cho người trình bày, không đọc lên.

---

<!-- muc-luc -->
## Mục lục

- [Cách dùng](#cách-dùng)
- [Bản rút gọn 15 phút](#bản-rút-gọn-15-phút)
- [Kịch bản từng slide](#kịch-bản-từng-slide)
  - [Slide 1 · Bìa](#slide-1--bìa)
  - [Slide 2 · Nội dung — bốn phần](#slide-2--nội-dung--bốn-phần)
  - [Slide 3 · Bài toán lớn](#slide-3--bài-toán-lớn)
  - [Slide 4 · Trục phân rã ba tầng](#slide-4--trục-phân-rã-ba-tầng)
  - [Slide 5 · Cây sáu bài toán nhỏ](#slide-5--cây-sáu-bài-toán-nhỏ)
  - [Slide 6 · BTN1 — trạng thái tập khách](#slide-6--btn1--trạng-thái-tập-khách)
  - [Slide 7 · BTN2 — mất khách hay mua thưa](#slide-7--btn2--mất-khách-hay-mua-thưa)
  - [Slide 8 · BTN3 — rổ cạn hay kích hoạt hỏng](#slide-8--btn3--rổ-cạn-hay-kích-hoạt-hỏng)
  - [Slide 9 · BTN4 — mô hình Cox](#slide-9--btn4--mô-hình-cox)
  - [Slide 10 · Đường Kaplan–Meier](#slide-10--đường-kaplanmeier)
  - [Slide 11 · Phát hiện chính](#slide-11--phát-hiện-chính)
  - [Slide 12 · Chín giả thuyết](#slide-12--chín-giả-thuyết)
  - [Slide 13 · Bộ chỉ số](#slide-13--bộ-chỉ-số)
  - [Slide 14 · Kiểm chứng số liệu](#slide-14--kiểm-chứng-số-liệu)
  - [Slide 15 · Tự phản biện — tổng quan](#slide-15--tự-phản-biện--tổng-quan)
  - [Slide 16 · Tám chỗ lệch](#slide-16--tám-chỗ-lệch)
  - [Slide 17 · B21 — dữ liệu mô phỏng](#slide-17--b21--dữ-liệu-mô-phỏng)
  - [Slide 18 · B11 — cohort hay thời kỳ](#slide-18--b11--cohort-hay-thời-kỳ)
  - [Slide 19 · B17 — cỡ hiệu ứng](#slide-19--b17--cỡ-hiệu-ứng)
  - [Slide 20 · Kết luận nào còn đứng](#slide-20--kết-luận-nào-còn-đứng)
  - [Slide 21 · Việc chưa xong](#slide-21--việc-chưa-xong)
  - [Slide 22 · Nối sang chương mô hình](#slide-22--nối-sang-chương-mô-hình)
  - [Slide 23 · Kết](#slide-23--kết)
- [Câu hỏi dự kiến và cách trả lời](#câu-hỏi-dự-kiến-và-cách-trả-lời)
- [Bốn điều cần nhớ](#bốn-điều-cần-nhớ)

---
<!-- muc-luc -->

## Cách dùng

Kịch bản này đã được nhúng sẵn vào phần **ghi chú người trình bày** của từng slide trong `D2-Slides.pptx`. Khi trình chiếu, bật **Presenter View** (PowerPoint: `Slide Show` → tick `Use Presenter View`, hoặc `Alt + F5`) là thấy ngay lời nói của slide đang chiếu.

Không học thuộc. Đọc kỹ hai lần, nhớ **ý** và **con số**, còn câu chữ cứ để tự nhiên. Riêng bốn chỗ nên nói gần đúng nguyên văn vì chúng được cân nhắc từng chữ: slide 3 (chỗ lệch mốc), slide 11 (đổi khuyến nghị), slide 17 (bằng không) và slide 23 (câu kết).

## Bản rút gọn 15 phút

Nếu thời gian chỉ có 15 phút, bỏ bốn slide sau — chúng bổ trợ chứ không mang kết luận riêng:

| Bỏ slide | Vì sao bỏ được |
|---|---|
| 4 · Trục phân rã ba tầng | Slide 5 đã thể hiện cùng ý qua cây bài toán |
| 10 · Kaplan–Meier | Hình minh hoạ; slide 11 và 19 mới mang kết luận |
| 16 · Tám chỗ lệch | Slide 15 đã nêu con số 8; B1, B15 đã nói tại chỗ |
| 20 · Kết luận nào còn đứng | Giữ lại làm **câu trả lời dự phòng** khi bị hỏi |

Còn lại **15 phút 30 giây** — vừa đủ 15 phút kể cả nhịp dừng.

---

## Kịch bản từng slide

### Slide 1 · Bìa

`25 giây`

> Kính thưa hội đồng. Em là [họ tên], mã số sinh viên [MSSV]. Đề tài khóa luận của em là dự báo doanh thu và giá vốn hàng bán theo ngày.

> Hôm nay em xin trình bày bài toán D2 — xói mòn nền khách hàng. Đây là bài toán phân tích đứng trước chương mô hình dự báo, và kết quả của nó sẽ đặt ra một ràng buộc cho chương đó.

> Dữ liệu là thương mại điện tử thời trang, 121.930 khách hàng, gần 647.000 đơn, trải hơn mười năm rưỡi.

**Thao tác:**

- Đứng thẳng, nhìn hội đồng, chưa cần bấm slide vội.

---

### Slide 2 · Nội dung — bốn phần

`30 giây`

> Bài của em có bốn phần.

> Phần một, em đặt bài toán và trình bày cách phân rã. Phần hai là kết quả — sáu bài toán nhỏ, toàn bộ số liệu chạy trực tiếp trên dữ liệu gốc. Phần ba là bộ chỉ số để đo và theo dõi.

> Và phần bốn — phần em muốn nhấn mạnh — em tự phản biện chính tài liệu của mình, 31 mục, và tìm ra tám chỗ sai.

**Thao tác:**

- Câu cuối nói chậm lại. Đây là câu định hình cả buổi.

---

### Slide 3 · Bài toán lớn

`60 giây`

> Xuất phát điểm là một quan sát đơn giản. So với đỉnh năm 2016, doanh thu năm 2022 mất 44,4%.

> Nhưng khi tách ra thì thấy giá trị mỗi đơn không hề giảm — AOV còn tăng 27%. Cái mất là số đơn, giảm 56,2%.

> Đến đây nhiều phân tích dừng lại và kết luận "số đơn giảm". Em cho rằng dừng ở đó mới chỉ mô tả được triệu chứng, vì số đơn không tự sinh ra — đơn hàng là do khách hàng đặt. Nên câu hỏi thật phải là: nền khách hàng xói mòn ở khâu nào, cơ chế gì gây ra, và can thiệp nào giữ lại được.

> Khối cam phía dưới em xin nói luôn: bản tài liệu cũ của em ghép doanh thu âm 44,4% tính từ 2016 với AOV cộng 50,7% tính từ 2013 — hai mốc khác nhau trong cùng một câu. Em phát hiện ra khi dựng slide này và đã đưa cả ba số về cùng mốc 2016.

**Thao tác:**

- Chỉ tay vào khối cam khi nói đoạn cuối.
- Chủ động nhận lỗi ngay slide đầu tiên — nó đặt tông cho cả phần sau.

---

### Slide 4 · Trục phân rã ba tầng

`55 giây`

> Để tìm chỗ hỏng, em phân rã doanh thu thành một tích. Doanh thu bằng số đơn nhân AOV. Số đơn bằng khách hoạt động nhân tần suất. Khách hoạt động bằng khách mới cộng khách giữ lại.

> Sáu bài toán nhỏ của em bám đúng từng thành phần trong phép nhân này, chứ không gom theo chủ đề — nên chúng chia hết không gian nguyên nhân theo định nghĩa.

> Nhưng em phải nói rõ một chỗ. Bản đầu em viết là "phủ kín nguyên nhân". Khi tự kiểm ở mục A9 thì thấy nói vậy là quá lời: AOV không bài toán nhỏ nào phụ trách, và nhánh "giành lại khách cũ" — chiếm 52,9% khách hoạt động năm 2022 — bị gộp chìm vào "khách giữ lại". Đúng ra phải nói là phủ kín theo số học, chưa phủ kín theo trách nhiệm phân tích.

**Thao tác:**

- Đọc khối công thức bằng cách chỉ tay theo từng dòng, đừng đọc từng ký tự.

---

### Slide 5 · Cây sáu bài toán nhỏ

`50 giây`

> Đây là sáu bài toán nhỏ và tiến độ. Bốn bài đã có kết quả, em sẽ đi qua ngay sau đây.

> Hai bài còn treo, và em xin nhấn mạnh: treo vì hai lý do hoàn toàn khác nhau.

> BTN5 treo vì em chưa làm — công cụ có sẵn, kiểm định điểm gãy bằng Chow test là làm được ngay với dữ liệu hiện có. Còn BTN6 treo vì bộ dữ liệu không có bảng chi phí marketing — đây là giới hạn dữ liệu, không phải thiếu công.

> Em nghĩ phân biệt này quan trọng nên ghi rõ chứ không gộp chung thành "chưa xong".

**Thao tác:**

- Nếu bị hỏi "sao không tự tạo dữ liệu chi phí" → trả lời: bịa dữ liệu để có kết quả là điều em không làm.

---

### Slide 6 · BTN1 — trạng thái tập khách

`45 giây`

> BTN1 trả lời câu hỏi: tập khách hiện đang ở đâu.

> Danh sách có 121.930 người, chia ba trạng thái. 31.684 người đăng ký rồi chưa từng mua. 65.493 người từng mua nhưng đã ngưng. 24.753 người còn mua trong năm 2022. Ba số cộng lại đúng bằng tổng — không ai rơi ra ngoài, không ai bị đếm hai lần.

> Nhưng ở mục B15 em phát hiện một lỗi. Chỉ số Me1 tính trên bộ lọc live — tức là loại đơn huỷ — còn Me8a tính trên ALL, tức giữ đơn huỷ. Hai bộ lọc khác nhau mà không ghi nhãn, nên cộng lại ra 98,26% chứ không phải 100%. Nhóm khách chỉ có đơn huỷ bị rơi mất. Con số nhất quán là 27,73%.

**Thao tác:**

- Nhấn "ba số cộng lại đúng bằng tổng" — đây là phép kiểm, không phải con số trang trí.

---

### Slide 7 · BTN2 — mất khách hay mua thưa

`45 giây`

> BTN2 hỏi: mất khách, hay người ở lại mua thưa đi.

> Phân rã cho thấy 72,2% mức giảm số đơn là do ít khách hơn, 45,2% là do mua thưa hơn, và phần dôi ra bị số hạng tương tác kéo lại 17,4%. Hai sự cố xảy ra đồng thời và nhân lên nhau — nên sửa một trong hai là không đủ.

> Ở mục B6 em tự kiểm và thấy: tầng này em dùng phân rã số học, còn tầng BTN3 dùng phân rã logarit. Tính lại BTN2 bằng logarit thì ra 63,8 và 36,2. Thứ tự không đổi nên giả thuyết H1 vẫn đứng, nhưng tài liệu phải khai báo rõ đang dùng phương pháp nào chứ không để lẫn.

---

### Slide 8 · BTN3 — rổ cạn hay kích hoạt hỏng

`60 giây`

> BTN3 là chỗ dễ kết luận sai nhất trong cả bài.

> File customers.csv là một danh sách đóng 121.930 người — không có ai mới được thêm vào. Nghĩa là rổ khách chưa mua chỉ có thể co lại theo thời gian. Nếu chỉ nhìn "khách mới giảm" thì ta trộn lẫn hiệu ứng cơ học đó với tín hiệu thật.

> Em dùng phân rã logarit để tách đôi. Kết quả: 36,4% mức giảm là do rổ cạn, còn 63,6% là do tỷ lệ hút sụp. Tỷ lệ hút rơi từ 24,09% xuống 3,78%.

> Ở mục B1 em phát hiện con số trong tài liệu — 26,9 và 73,1 — là sai. Vòng lặp tính Pool gán giá trị trước khi trừ và bắt đầu từ năm 2013, làm rơi mất toàn bộ cohort 2012. Tính lại đúng là 36,4 và 63,6. Kết luận không đổi — tỷ lệ hút vẫn là nguyên nhân chính — nhưng rổ cạn nặng hơn tài liệu thừa nhận gần 10 điểm phần trăm.

**Thao tác:**

- Nếu hội đồng hỏi "sao phải dùng logarit" → vì logarit biến tích thành tổng, nên hai nguyên nhân cộng lại đúng bằng tổng, không có số hạng tương tác.

---

### Slide 9 · BTN4 — mô hình Cox

`60 giây`

> BTN4 là trọng tâm: cơ chế xảy ra ở đơn hàng đầu tiên. Em dùng mô hình Cox proportional hazards trên 84.566 khách, 74,1% có sự kiện quay lại, thời gian trung vị 312 ngày.

> Cách đọc bảng: HR nhỏ hơn 1 nghĩa là quay lại chậm hơn. Biến mạnh nhất là cohort_year — 0,7478, tức mỗi năm gia nhập muộn hơn thì khả năng quay lại chậm hơn khoảng 25%. Biến promo_first chỉ 0,948. Còn giao hàng chậm và trả hàng có p bằng 0,303 và 0,161 — không có tín hiệu.

> Ở mục A8 em tự kiểm và phải nói thật: concordance chỉ 0,653. Đoán mò hoàn toàn là 0,50. Mô hình hơn đoán mò 15 điểm — đủ để nói về cơ chế và thứ tự quan trọng của các biến, nhưng em không gọi đây là mô hình dự đoán.

**Thao tác:**

- Câu "em không gọi đây là mô hình dự đoán" nên nói dứt khoát — nó chặn trước một câu hỏi khó.

---

### Slide 10 · Đường Kaplan–Meier

`40 giây`

> Đây là hình minh hoạ. Trục dọc là tỷ lệ khách chưa quay lại, nên đường thấp hơn nghĩa là quay lại nhiều hơn.

> Tại mốc một năm, hai nhóm chênh nhau 10 điểm phần trăm, và log-rank có ý nghĩa thống kê.

> Nhưng khoảng cách thô này đã gồm cả hiệu ứng cohort trong đó. Slide sau em tách ra.

**Thao tác:**

- Chỉ vào mũi tên "Chênh 10.0 điểm % tại 1 năm" trên hình.

---

### Slide 11 · Phát hiện chính

`80 giây`

> Đây là phần em coi là đóng góp riêng của khóa luận.

> Nhìn thô: khách có khuyến mãi ở đơn đầu mua 4,59 đơn trọn đời, khách không khuyến mãi mua 7,56 đơn — ít hơn 39,2%. Nếu dừng ở đây thì khuyến nghị hiển nhiên sẽ là "cắt ngân sách khuyến mãi ngay".

> Nhưng khi đưa vào mô hình Cox và kiểm soát năm cohort, danh mục hàng và giá trị đơn đầu, thì hiệu ứng còn lại chỉ HR bằng 0,948 — chậm hơn khoảng 5,2%.

> Nghĩa là gần như toàn bộ khoảng cách 39,2% kia không phải do khuyến mãi gây ra, mà do khách có khuyến mãi tập trung ở các cohort muộn — mà cohort muộn thì vốn đã kém hơn.

> Em muốn nhấn ý này: nếu dừng ở phân tích mô tả, khuyến nghị sẽ là cắt khuyến mãi — một quyết định sai, xuất phát từ việc nhầm tương quan với nhân quả. Bước đi từ mô tả sang cơ chế ở đây không phải làm cho đẹp bài. Nó đổi hẳn khuyến nghị.

**Thao tác:**

- Slide quan trọng nhất phần II. Nói chậm, dừng một nhịp sau câu "39,2%" và sau câu "5,2%".
- Dùng tay chỉ từ ô đỏ sang ô xanh khi nói "nhưng khi kiểm soát".

---

### Slide 12 · Chín giả thuyết

`50 giây`

> Đây là chín giả thuyết em đặt ra. Em ghi cả những cái bị bác bỏ, vì bác bỏ cũng là kết quả chứ không phải thất bại.

> H1 đến H3 được ủng hộ. H4 bị bác bỏ — em sẽ nói ở phần sau. H5 và H6 chỉ ủng hộ yếu. H7 đúng nhưng nhỏ hơn em tưởng rất nhiều.

> H8 và H9 ban đầu em ghi là "sai" — tức giao hàng và trả hàng không ảnh hưởng đến giữ chân. Sau khi tự phản biện em phải đổi thành "kết quả rỗng, không diễn giải được". Lý do em xin trình bày ở slide 17.

**Thao tác:**

- Đừng đọc hết chín dòng. Chỉ nêu nhóm và dừng lại ở H8, H9.

---

### Slide 13 · Bộ chỉ số

`45 giây`

> Bộ chỉ số gồm 13 measure, 13 metric và 7 KPI, nối với nhau bằng ma trận truy vết — để mỗi bài toán nhỏ đều truy xuống được một KPI có ngưỡng và có hành động.

> Ba chỗ em đã sửa so với bản đầu: Me8 bị lỗi grain, tử số trộn hai nhóm khách khác nhau. K2 đặt mục tiêu tăng trưởng trên một rổ chỉ có thể co lại — bất khả thi về mặt cấu trúc. Và K7 em thêm vào làm guardrail để chặn chi phí.

> Nhưng B8 và B19 cho thấy vẫn còn ba chỗ hỏng. K7 vi phạm ngưỡng của chính nó ngay ngày ban hành — thực tế đang ở 30,57% trong khi ngưỡng đặt là dưới 30%. K1 đòi tăng 2,86 lần. Và K5 phải 36 tháng mới đo được, quá trễ để lái.

---

### Slide 14 · Kiểm chứng số liệu

`50 giây`

> Về kiểm chứng, nguyên tắc của em là phải đi bằng đường khác. Chạy lại cùng một script không chứng minh gì cả — nó chỉ chứng minh code chạy hai lần ra cùng kết quả.

> Em có sáu phép kiểm. Nhưng ở mục B10 em tự kiểm và phát hiện ba trong năm phép là hằng đúng — chúng không thể vỡ dù số liệu có sai.

> Nặng nhất là phép mà tài liệu cũ gọi là "mạnh nhất" — hai đường phân rã độc lập gặp nhau. Thực ra nó yếu nhất, vì hai đường dùng chung dữ liệu đầu vào nên buộc phải gặp.

> Hai phép thật sự có thể vỡ là đối chiếu sales.csv và đối chiếu payment_value — và cả hai đều khớp.

**Thao tác:**

- Đây là slide dễ ăn điểm: nó cho thấy em hiểu thế nào là một phép kiểm có giá trị.

---

### Slide 15 · Tự phản biện — tổng quan

`45 giây`

> Sang phần bốn.

> Sau khi hoàn thành tài liệu, em tự kiểm 31 mục. Mỗi mục một script riêng, chạy lại trực tiếp trên dữ liệu gốc — em không tin lại kết quả cũ của chính mình.

> Kết quả: 13 mục xác nhận tài liệu đúng, 10 mục đúng nhưng nói quá nên phải thu hẹp, và 8 mục lệch phải sửa.

> Nguyên tắc em đặt ra: mỗi con số phải kèm bảng nguồn, cột, bộ lọc và grain. Khi lệch so với tài liệu thì ghi thẳng chữ LỆCH, không làm tròn cho khớp. Khi không xác định được thì viết "chưa xác định được" kèm lý do, không đoán.

---

### Slide 16 · Tám chỗ lệch

`45 giây`

> Đây là tám chỗ lệch. B1 và B15 em đã nói ở trên.

> Ba chỗ nữa đáng chú ý. B7: em giả định cohort_year có tác động tuyến tính, kiểm định tỷ số hợp lý bác bỏ giả định đó với p bằng 8,2 nhân 10 mũ trừ 16 — dạng tuyến tính hỏng từ năm 2020.

> B9: giả thuyết H4 của em bị bác bỏ. Mô phỏng cho kết quả cộng 0,68% trong khi thực tế là âm 38,60%.

> Và B20: trường signup_date hỏng, em xác nhận là không sửa được, nên không dùng nó làm căn cứ định lượng.

> Cả tám chỗ đều đã có đề xuất câu chữ cụ thể để sửa.

---

### Slide 17 · B21 — dữ liệu mô phỏng

`70 giây`

> Đây là phát hiện em cho là nặng nhất, và nó thay đổi cách đọc mấy kết quả trước đó.

> Bộ dữ liệu này là mô phỏng. Em kiểm từng trường bằng một tương quan lẽ ra phải tồn tại trong dữ liệu thật. Bốn trường không qua được.

> Nặng nhất là cặp reviews và returns. Có 111.369 đơn có đánh giá. 36.062 đơn có trả hàng. Trên tổng 646.945 đơn. Số đơn có cả hai là... không. Bằng không.

> Nếu hai việc này độc lập với nhau thì kỳ vọng phải có khoảng 6.208 đơn. Quan sát 0 trên kỳ vọng 6.208 — xác suất xảy ra ngẫu nhiên là thực tế bằng không. Bộ sinh dữ liệu đã gán review và trả hàng vào hai tập rời nhau.

> Hệ quả là em không thể kiểm được câu hỏi hiển nhiên nhất: đơn bị trả hàng có rating thấp hơn không. Đây không phải kết quả rỗng — đây là dữ liệu không tồn tại.

> Tương tự, delivery_days ở ba vùng là 4,499 — 4,499 — 4,500 trên hơn nửa triệu đơn, p bằng 0,985. Trong thực tế vùng xa luôn giao chậm hơn.

> Vì vậy H8 và H9 phải đổi cách diễn giải: kết quả rỗng ở đây nói về bộ sinh dữ liệu, không nói về doanh nghiệp, và em không rút ra khuyến nghị nào từ đó.

**Thao tác:**

- Dừng hẳn một nhịp sau chữ "Bằng không." Đây là khoảnh khắc mạnh nhất của bài.
- Nếu bị hỏi "vậy cả luận văn còn giá trị gì" → chuyển ngay sang slide 20.

---

### Slide 18 · B11 — cohort hay thời kỳ

`55 giây`

> Mục B11 đánh thẳng vào kết luận trọng tâm của em. HR của cohort_year là 0,7478 — nhưng đó là hiệu ứng cohort, hay hiệu ứng thời kỳ?

> Phân biệt này đổi hẳn khuyến nghị. Nếu là cohort thì phải sửa khâu thu nạp. Nếu là thời kỳ thì phải đi tìm cú sốc năm 2019.

> Em kiểm bằng cách nhìn riêng cohort 2013 — một nhóm cố định, không ai vào, không ai ra. Họ rơi từ 61,2% xuống 46,0%, và rơi đúng vào năm 2019. Chuyện xảy ra với người đã ở sẵn trong hệ thống thì không thể là hiệu ứng cohort.

> Thêm nữa, khi em đưa biến thời kỳ vào mô hình thì HR lật từ 0,74 thành 1,16.

> Kết luận là cả hai, và tài liệu cũ chỉ nói một nửa. Đây là bài toán Age–Period–Cohort kinh điển: ba trục cộng tuyến hoàn hảo, không tách được nếu không có ràng buộc thêm. Em khai báo giới hạn này chứ không giả vờ là tách được.

---

### Slide 19 · B17 — cỡ hiệu ứng

`50 giây`

> Mục B17 là về cỡ hiệu ứng. Biến promo_first có p nhỏ hơn 0,001 — chắc chắn có tín hiệu. Nhưng quy ra số người thật thì hiệu ứng chỉ 1,4 điểm phần trăm, tức 367 người trên 26.759 khách có khuyến mãi.

> Trong khi cohort_year đổi 35,4 điểm — mạnh hơn 25,8 lần.

> Em nêu điều này vì với 84.566 quan sát thì gần như mọi biến đều sẽ có p nhỏ hơn 0,001. p-value chỉ trả lời "có khác 0 hay không", nó không trả lời "có đáng để làm gì hay không".

> Một can thiệp đổi được 367 người thì không xứng với một chương trình khuyến mãi toàn hệ thống.

**Thao tác:**

- Đây là slide chứng tỏ hiểu thống kê chứ không chỉ biết chạy thư viện.

---

### Slide 20 · Kết luận nào còn đứng

`40 giây`

> Tổng kết phần phản biện. Em chia kết luận theo cái mà nó dựa vào.

> Bên trái là những kết luận dựa trên cấu trúc thời gian và việc đếm đơn, đếm khách — bộ sinh dữ liệu phải có quy luật mới tạo ra được, nên những kết luận này đứng vững.

> Bên phải là những chỗ dựa vào một trường có thể ngẫu nhiên, hoặc dựa vào phép kiểm hằng đúng — những chỗ này phải viết lại.

> Quy tắc em rút ra: kết quả rỗng trên một trường nghi ngẫu nhiên thì nói về bộ sinh dữ liệu, không nói về doanh nghiệp, và không được chuyển thành khuyến nghị thực hành.

**Thao tác:**

- Đây là câu trả lời cho "dữ liệu giả thì phân tích còn ý nghĩa gì".

---

### Slide 21 · Việc chưa xong

`40 giây`

> Việc chưa xong em đã nói ở đầu. Còn ba điều em xin chủ động nói trước khi hội đồng hỏi.

> Thứ nhất, promo_first là tương quan đã kiểm soát, không phải nhân quả. Matching chỉ cân bằng được biến đã quan sát, còn khách nhạy giá tự chọn vào nhóm khuyến mãi theo những đặc điểm em không quan sát được.

> Thứ hai, H6 chỉ dựa trên ba điểm dữ liệu. Đủ để nói chưa thấy dấu hiệu tiếp tục rơi, chưa đủ để khẳng định là chế độ ổn định.

> Thứ ba, signup_date hỏng nặng — 73,8% đơn được đặt trước ngày đăng ký. Em chỉ dùng nó để bác bỏ khung "thu nạp hỏng", không dùng làm căn cứ định lượng.

**Thao tác:**

- Nói ba điều này TRƯỚC khi bị hỏi thì nó là sự cẩn trọng. Nói sau khi bị hỏi thì nó là biện minh.

---

### Slide 22 · Nối sang chương mô hình

`45 giây`

> Cuối cùng, bài toán này nối sang chương mô hình như thế nào.

> Cấu trúc khách hàng giải thích ba chế độ mà mô hình dự báo phải xử lý: 2014 đến 2018 là chế độ cao, 2019 là điểm gãy, 2020 đến 2022 thấp và đi ngang.

> Hệ quả cụ thể: nếu ngoại suy xu hướng đơn thuần thì mô hình sẽ dự đoán 2023–2024 tiếp tục giảm. Nhưng cấu trúc khách hàng nói là đi ngang quanh mức 2022.

> Em định lượng được ràng buộc đó: doanh thu năm trong khoảng 1,16 đến 1,23 tỷ, và nền khách lặp lại có khoảng tin cậy 95% từ 22.028 đến 23.422 người. Đây là giả định thứ tư của chương mô hình, bổ sung cho ba quyết định kỹ thuật đã có.

**Thao tác:**

- Slide này chứng minh bài toán D2 không phải một chương rời — nó có đầu ra dùng được.

---

### Slide 23 · Kết

`25 giây`

> Em xin kết.

> Nếu hội đồng hỏi em "chứng minh số của em đúng đi", câu trả lời của em là: em không chứng minh từng số riêng lẻ. Em thiết kế để các số buộc phải khớp nhau — nếu một số sai thì phép kiểm chéo sẽ vỡ.

> Và khi em tự kiểm 31 mục, tám chỗ đã vỡ thật. Em sửa cả tám, và đây là chúng.

> Em xin hết phần trình bày. Kính mời hội đồng đặt câu hỏi.

**Thao tác:**

- Nói câu cuối rồi dừng hẳn. Đừng nói thêm gì.

---

## Câu hỏi dự kiến và cách trả lời

Trả lời **ngắn trước, giải thích sau**. Câu đầu tiên phải là câu trả lời, không phải phần dẫn.

**1. Cohort là gì? Em xác định nó bằng cách nào?**

> Cohort là nhóm khách được gom theo năm họ đặt đơn hàng đầu tiên. Trường này **không có sẵn** trong dữ liệu — em tự tính bằng `min(order_date)` theo `customer_id`, trên bộ lọc `live`. Cohort 2012 và 2013 cộng lại chiếm 69,5% nền khách năm 2022.

**2. Vì sao bảng so sánh bắt đầu từ 2013 mà không phải 2012?**

> Vì dữ liệu 2012 chỉ bắt đầu từ 04/07, phủ 49,5% của năm — so sánh với một năm đủ 12 tháng là khập khiễng. Em có kiểm lại: **bỏ 2012 làm các con số đẹp hơn**, chứ không xấu đi. Nên đây không phải chọn mốc có lợi. Mục A7 ghi rõ điều này.

**3. Concordance chỉ 0,65 thì tin mô hình Cox thế nào được?**

> Em không dùng nó để dự đoán từng khách. Em dùng nó để **xếp hạng độ mạnh** của các cơ chế — và cho mục đích đó thì hệ số hồi quy cùng khoảng tin cậy mới là thứ quan trọng, không phải concordance. Em cũng đã kiểm giả định bằng Schoenfeld residuals và báo cáo cả hai biến vi phạm.

**4. Propensity score matching có biến kết quả thành nhân quả không?**

> **Không.** Cân bằng có đạt — SMD giảm từ 0,393 xuống 0,012 — nhưng chỉ trên các biến em quan sát được. Khách nhạy giá tự chọn vào nhóm khuyến mãi theo những đặc điểm không có trong dữ liệu. Em ghi rõ đây là tương quan đã kiểm soát.

**5. Dữ liệu là mô phỏng thì phân tích còn ý nghĩa gì?**

> Em chia kết luận làm hai nhóm (slide 20). Nhóm dựa trên **cấu trúc thời gian và đếm đơn, đếm khách** thì bộ sinh phải có quy luật mới tạo ra được — nhóm này đứng vững. Nhóm dựa trên một trường có thể gán ngẫu nhiên thì em **đã loại khỏi khuyến nghị**. Chính vì câu hỏi này mà em làm mục B21.

**6. Vậy khuyến nghị cuối cùng có phải là cắt khuyến mãi không?**

> **Không.** Tín hiệu thô nói giảm 39,2%, nhưng sau khi kiểm soát cohort thì cỡ hiệu ứng thật chỉ 1,4 điểm phần trăm — tương đương **367 người** trên 26.759. Không xứng với một chương trình toàn hệ thống. Đòn bẩy thật nằm ở chất lượng cohort, mạnh hơn 25,8 lần.

**7. Làm sao em biết vòng lặp tính Pool bị sai?**

> Em viết lại phép tính bằng một **công thức đóng** rồi đối chiếu với vòng lặp cũ. Hai cách lệch nhau đúng bằng quy mô cohort 2012 — đó là dấu hiệu chỉ thẳng vào lỗi. Nguyên tắc là kiểm bằng đường khác chứ không chạy lại cùng một đường.

**8. Ba con số "khách hoạt động" khác nhau — 22.999, 24.696, 24.753 — là sao?**

> Mục A10 tách nguyên nhân: **97% mức chênh là do bộ lọc** `live` và `ALL`, chỉ 3% là do cửa sổ thời gian (năm dương lịch so với recency 365 ngày). Tài liệu cũ dùng lẫn ba con số mà không ghi nhãn — đây là chỗ phải sửa.

**9. Sao không làm BTN6 — ngân sách nên đi đâu?**

> Vì bộ dữ liệu **không có bảng chi phí marketing**, không có chi phí theo kênh cũng không có theo kỳ. Không có mẫu số thì không tính được hiệu quả chi tiêu. Đây là giới hạn dữ liệu; em chọn ghi rõ chứ không bịa số để có kết quả.

**10. Nếu hội đồng chỉ ra một lỗi mới thì em xử lý thế nào?**

> Em ghi nhận và kiểm lại theo đúng quy trình đã dùng cho 31 mục: viết một script riêng, chạy trực tiếp trên `data/`, kèm bảng nguồn và bộ lọc. Nếu lệch thì em ghi LỆCH và sửa, như đã làm với tám mục kia.

---

## Bốn điều cần nhớ

1. **Không đọc slide.** Slide là chỗ hội đồng nhìn, lời nói là chỗ hội đồng nghe. Hai thứ phải bổ sung nhau chứ không lặp lại nhau.
2. **Nhận lỗi trước khi bị chỉ ra.** Tám chỗ lệch là điểm mạnh của bài — nhưng chỉ khi mình nói trước. Bị hỏi rồi mới nhận thì thành điểm yếu.
3. **Không biết thì nói không biết.** Kèm theo: "em sẽ kiểm lại bằng cách nào". Đoán một con số trước hội đồng là rủi ro lớn nhất của cả buổi.
4. **Phân biệt "chưa làm" với "không làm được".** BTN5 là chưa làm. BTN6 là dữ liệu không có. Hai cái đó khác nhau và hội đồng đánh giá khác nhau.
