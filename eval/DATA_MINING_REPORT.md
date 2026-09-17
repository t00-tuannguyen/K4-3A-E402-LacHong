# BÁO CÁO KHAI THÁC DỮ LIỆU TIN NHẮN (DATA MINING REPORT)
> **Dự án:** Trợ lý Học viên Discord (Track B1 — Grounded Logistics & Intent-Aware Assistant with TA Handoff)  
> **Người thực hiện:** Trần Phạm Thái Vũ (Mã HV: `2A202602695`) — Role: Data & Evaluation Lead  
> **Nguồn dữ liệu:** `data/discord-pack/k4_messages.csv` (12/09 – 14/09/2026)  
> **Tiêu chuẩn đáp ứng:** Bằng chứng định lượng Chuẩn B (Rubric R1 — 6/6 điểm)

---

## 1. TỔNG QUAN DỮ LIỆU ĐỊNH LƯỢNG

Dữ liệu được trích xuất và phân tích tự động từ 1.092 tin nhắn thuộc hai server Discord của khóa 4:

| Chỉ số | Giá trị | Tỷ lệ (%) | Ý nghĩa |
|---|---|---|---|
| **Tổng số tin nhắn** | 1.092 tin | 100% | Toàn bộ dữ liệu 3 ngày onboarding |
| **Tin nhắn của học viên / người** (`is_bot = False`) | 779 tin | 71.3% | Nhu cầu thực tế của cộng đồng học viên |
| **Tin nhắn của bot trợ lý** (`is_bot = True`) | 313 tin | 28.7% | Tần suất phản hồi của bot hiện tại |
| **Độ dài trung bình tin nhắn học viên** | 78.0 ký tự | — | Câu hỏi thường ngắn gọn, cộc lốc |
| **Độ dài trung bình phản hồi của bot** | 486.5 ký tự | — | **Bot dài gấp 6.23 lần câu hỏi học viên** |

---

## 2. PHÂN TÍCH NHU CẦU LOGISTICS & THỦ TỤC CỦA HỌC VIÊN

Khai thác trên 779 tin nhắn không phải bot:

1. **Đếm hẹp (Strict Keyword Matching):**
   - Lọc regex không phân biệt hoa thường: `deadline|hạn nộp|nộp bài|điểm danh`.
   - Kết quả: **54/779 tin (6.93%)** trực tiếp chứa các từ khóa này.
2. **Đếm rộng (Logistics & Course Procedures):**
   - Lọc regex mở rộng: `deadline|hạn|nộp|mấy giờ|giờ nào|submit|điểm danh|ticket|gia hạn|onboarding|phoenix|đổi tên|lập team|ghép đội`.
   - Câu hỏi trực tiếp về deadline / nộp bài / ghép đội: **87/779 tin (11.17%)**.
   - Câu hỏi về thủ tục, quy chế, ticket và công cụ khóa học: **213/779 tin (27.34%)**.

> **Kết luận:** Hơn 27% nhu cầu trao đổi của học viên trong giai đoạn đầu xoay quanh các vấn đề thủ tục hành chính, hạn nộp bài tập và vận hành khóa học.

---

## 3. BẰNG CHỨNG THỰC TẾ: 3 KIỂU LỖI NGHIÊM TRỌNG CỦA BOT CŨ

Dưới đây là các trích dẫn nguyên văn từ `k4_messages.csv` chứng minh 3 lỗi cốt lõi:

### Lỗi 1: Lệch Ý định hỏi (Intent Mismatch)
* **Trường hợp 1 (Case `M84993` $\to$ `M57630`):**
  - **Thời gian:** 12/09/2026 12:51 | Người hỏi: `D8411`
  - **Học viên hỏi (`M84993`):** `[@BOT] check xem t đã nộp bài codelab chưa`
  - **Bot trả lời (`M57630`):** `Bài Lab trên lớp sẽ được chấm sau khi hết deadline thường là 23:59 cùng ngày nhé`
  - **Phân tích lỗi:** Học viên hỏi **trạng thái nộp bài cá nhân**, nhưng bot lại trả lời về **thời điểm chấm bài**. Bot hoàn toàn hiểu sai intent, trả lời lạc đề và không giải quyết được nhu cầu của học viên.
* **Trường hợp 2 (Case `M75012` $\to$ `M77155`):**
  - **Thời gian:** 13/09/2026 00:15 | Người hỏi: `D6014`
  - **Học viên hỏi (`M75012`):** `[@BOT] nộp lab muộn trừ bao nhiêu điểm`
  - **Bot trả lời (`M77155`):** `Nộp daily muộn hơn 10h sáng vẫn ghi nhận nhưng không tính +XP nhé`
  - **Phân tích lỗi:** Học viên hỏi về **quy chế nộp bài Lab muộn**, nhưng bot lại trả lời về **quy định nộp Daily Standup**. Sự lệch intent này có thể dẫn đến việc học viên chủ quan tưởng nộp lab muộn chỉ mất XP thay vì bị 0 điểm.

---

### Lỗi 2: Thiếu Nguồn / Mâu thuẫn thông tin (Hallucination / Lack of Ground Truth)
* **Trường hợp 3 (Case `M82163` $\to$ `M73469`):**
  - **Thời gian:** 14/09/2026 19:35 | Người hỏi: `D6944`
  - **Học viên phản ánh (`M82163`):** `[@BOT] cái daly-standup sao m ghi là hết hôm nay nhưng nộp bài thì m kêu hết hạn.`
  - **Bot trả lời (`M73469`):** `Khung giờ nộp daily hàng ngày là từ 0h-10h sáng nhé. Nộp muộn vẫn được ghi nhận nhưng không +XP`
  - **Phân tích lỗi:** Bot trước đó cung cấp thông tin không nhất quán ("hết hôm nay" vs "hết hạn lúc 10h sáng"), khiến học viên bị lỡ khung giờ nộp bài và bức xúc phản ánh.

---

### Lỗi 3: Thiếu Cơ chế Handoff TA & Từ chối ngoài thẩm quyền (Lack of TA Handoff)
* **Trường hợp 4 (Case `M88027`):**
  - **Thời gian:** 13/09/2026 00:08 | Người hỏi: `D3115`
  - **Học viên kêu cứu (`M88027`):** `cho em hỏi Lab2 có được extend thời gian submit thêm không v ạ? Em lỡ nộp muộn 1 phút không submit bài được ạ`
  - **Thực tế:** Không có phản hồi nào kịp thời từ bot hoặc hệ thống tự động kết nối TA, đẩy học viên vào trạng thái hoang mang và nguy cơ mất điểm toàn bộ bài lab.
* **Trường hợp 5 (Case `M03059`):**
  - **Thời gian:** 12/09/2026 10:21 | Người hỏi: `D8756`
  - **Học viên hỏi (`M03059`):** `Em đang cần hỗ trợ về vấn đề giấy tờ gấp thì em liên lạc đến bộ phận nào ạ`
  - **Kỳ vọng:** Cần hướng dẫn ngay lệnh `/ticket create` tại `#ticket-support`, tránh để học viên chờ đợi.

---

## 4. CÁC CÂU HỎI THỰC TẾ KHÁC DÙNG LÀM TEST FIXTURES

| Mã tin | Thời gian | Người hỏi | Nội dung câu hỏi trích từ dataset | Nhóm phân loại |
|---|---|---|---|---|
| `M33002` | 13/09 12:01 | `D4594` | `Hạn tìm đồng đội đến bao giờ thế mọi người ơi!!!` | Happy Path (Ghép đội) |
| `M19124` | 13/09 00:25 | `D6331` | `a ơi sao deadline ghép đội tự do end sớm vậy a?` | Happy Path (Deadline ghép đội) |
| `M56777` | 12/09 20:54 | `D4616` | `[@BOT] hạn thành lập team là ngày nào? team không đủ 4 người có bị giải tán không` | Happy Path + Quy chế team |
| `M47011` | 12/09 09:39 | BTC | `@everyone ... mọi người vui lòng đổi tên theo cú pháp: Mã Nhóm - Họ và tên - 5 số cuối mã sinh viên` | Ground Truth: Cú pháp tên |
| `M49744` | 12/09 18:02 | BTC | `Thời hạn hoàn thành và ghép đội tự do đến 21:00 13/9 ... cách tạo ticket: command /ticket create tại kênh [link:discord.com]` | Ground Truth: Onboarding & Ticket |
| `M69081` | 12/09 12:04 | `D7722` | `có điểm danh ws không ạ` | Mơ hồ / Thiếu thực thể |
| `M77476` | 12/09 13:59 | `D4616` | `[@BOT] xem bảng xếp hạng điểm XP kiểu gì` | Happy Path (Lệnh bot) |

---

## 5. PHƯƠNG PHÁP ĐẾM & GIỚI HẠN DỮ LIỆU

- **Phương pháp đếm:**
  1. Sử dụng thư viện `pandas` đọc trực tiếp file CSV nguyên gốc `k4_messages.csv`.
  2. Lọc tập con người dùng: `df[df['is_bot'] == False]`.
  3. Quét regex theo danh sách từ khóa chuỗi hóa bằng dấu pipe `|`.
  4. Phân tích liên kết hội thoại thông qua trường `reply_to` liên kết `msg_id`.
- **Giới hạn dữ liệu:**
  - Dữ liệu thu thập trong 3 ngày đầu (onboarding), tập trung vào các thắc mắc thủ tục ban đầu.
  - Các tin nhắn riêng (DM) và lệnh slash ẩn không nằm trong bộ dữ liệu crawl công khai.

