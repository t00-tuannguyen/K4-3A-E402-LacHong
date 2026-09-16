### NỘI DUNG BẰNG CHỨNG (EVIDENCE) CHO CANVAS CP1:
- Đối tượng (Job Executor): Học viên K4 đang làm lab và hoàn thiện thủ tục khoá học.
- Nỗi đau (Pain): Khi tra cứu hạn nộp lab và quy chế, học viên nhận câu trả lời dông dài gấp 6.2 lần từ bot (trung bình 486 ký tự), bot trả lời sai lệch intent (hỏi phạt nộp lab muộn nhưng bot trả lời quy chế daily standup - msg M75012), hoặc không biết thông tin nhưng không kết nối TA, dẫn đến học viên bị muộn hạn nộp bài (msg M88027).
- Bằng chứng định lượng (Chuẩn B):
  + Khai thác 779 tin nhắn học viên trong file k4_messages.csv: 87 tin nhắn (11.2%) trực tiếp hỏi về deadline và nộp bài; 213 tin nhắn (27.3%) hỏi về thủ tục/quy chế.
  + Đã trích xuất 7 ví dụ nguyên văn có mã msg_id chứng minh rõ 3 lỗi: Lệch intent, Hallucination/Thiếu nguồn, và Thiếu cơ chế Handoff TA.
  + Phương pháp đếm: Lọc Regex theo bộ từ khoá quy chế/deadline và phân tích cây phản hồi reply_to giữa học viên và Bot.
  # CHECKPOINT 1 — CANVAS DỰ ÁN

**Dự án:** Trợ lý Học viên Discord  
**Nhóm:** LacHong · **Lớp:** 3A · **Phòng:** E402 · **Cụm:** C2  
**Đội trưởng:** Nguyễn Tiến Tuân · **Mã học viên:** 2A202602595  
**Repo GitHub công khai:** https://github.com/t00-tuannguyen/K4-3A-E402-LacHong

| Mục | Nội dung |
|---|---|
| **1. Track** | **B1 — Cải tiến Trợ lý Discord:** trả lời câu hỏi về thủ tục và hạn nộp dựa trên nguồn chính thức, hiểu đúng ý định hỏi và hướng dẫn chuyển TA khi cần. |
| **2. Người dùng** | Học viên K4 cần biết hạn nộp, cách nộp bài hoặc cách kiểm tra điểm danh để hoàn thành đúng yêu cầu của khóa học. |
| **3. Vấn đề** | Học viên hỏi thông tin hoặc trạng thái cụ thể nhưng có lúc bot trả lời hướng dẫn chung, chưa giải quyết đúng câu hỏi. Học viên phải hỏi lại hoặc tìm người hỗ trợ; thông tin về hạn nộp chưa rõ có thể khiến họ bỏ lỡ việc cần làm. |
| **4. Bằng chứng ban đầu** | Trong **1.092 tin nhắn**, có **779 tin không phải bot**; **54/779 tin (6,9%)** chứa ít nhất một cụm “deadline”, “hạn nộp”, “nộp bài”, “điểm danh”. Case **M84993 → M57630**: người dùng hỏi đã nộp codelab chưa, bot trả lời về thời điểm chấm bài thay vì trạng thái nộp. Case **M82163**: người dùng phản ánh bot nói còn hạn trong ngày nhưng khi nộp lại báo hết hạn. |
| **5. Lát cắt một câu** | Học viên K4 hỏi một vấn đề về thủ tục khóa học, AI đối chiếu ý định hỏi với thông báo chính thức để chọn trả lời có dẫn nguồn, hỏi rõ thêm hoặc hướng dẫn chuyển TA, giúp học viên biết bước tiếp theo cần làm. |
| **6. Mức tự động hóa và lý do** | **Conditional:** tự trả lời ngắn gọn khi nguồn rõ và đủ; hỏi lại khi thiếu tên bài hoặc lớp; báo rõ khi nguồn mâu thuẫn và hướng dẫn chuyển TA. Không tự xác nhận trạng thái nộp bài, sửa điểm danh hay gia hạn khi không có quyền truy cập. Sai thông tin có thể ảnh hưởng việc nộp bài và điểm của học viên nên không được tự đoán. |
| **7. Người dùng thử và phân công** | **Willing users dự kiến:** **Nguyễn Hồng Thái — `2A202602894`** — đã xác nhận.<br><br>**Lê Duy Quân — `2A202602731`** — đã xác nhận.<br><br>**Nguyễn Mạnh Cường — `2A202602650`** — đã xác nhận.<br><br>Cả ba đều là người ngoài nhóm và có thể dùng thử prototype ở CP5.<br><br>**Phân công:** Nguyễn Tiến Tuân (2A202602595) — đội trưởng, spec và nộp checkpoint; Trần Phạm Thái Vũ (2A202602695) — mining dữ liệu, golden set và đánh giá; Vũ Duy Điệp (2A202602429) — nguồn chính thức, prompt và AI backend; Võ Phú Hãn (2A202602628) — giao diện, thử nghiệm người dùng và video demo. |

**Cách đếm bằng chứng:** Đọc `k4_messages.csv`, lọc `is_bot=False`, tìm không phân biệt hoa/thường bốn cụm từ nêu trên; mỗi tin chỉ tính một lần. Đây là số tin khớp từ khóa, **không phải số câu hỏi đã phân loại hay tỷ lệ bot trả lời sai**. Tin không phải bot có thể bao gồm cả TA/BTC.

**Giới hạn bằng chứng:** M82163 là phản ánh của người dùng, chưa đủ để kết luận deadline nào đúng. Nhóm sẽ đối chiếu thông báo chính thức và tiếp tục rà dữ liệu trước khi chốt spec.