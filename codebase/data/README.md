# KHO DỮ LIỆU NGUỒN CHÍNH THỨC (OFFICIAL GROUND TRUTH FIXTURES)

## 1. File `official_announcements.json` là gì và tại sao lại xuất hiện ở đây?

File [`official_announcements.json`](./official_announcements.json) là **kho thông báo ghim chính thức của Ban tổ chức (BTC)** được chuẩn hóa dưới dạng JSON có cấu trúc, đóng vai trò là **Nguồn sự thật duy nhất (Single Source of Truth / Ground Truth)** cho giải pháp Trợ lý Discord (Track B1).

### Lý do xuất hiện trong thư mục `codebase/data/`:
1. **Phục vụ cơ chế Strict Grounding cho Người 3 (Core AI & Prompt Engineer):**
   - Đề bài Track B1 và nguyên tắc thiết kế trong `SPEC.md §4` yêu cầu: *AI chỉ được phép trả lời dựa trên các thông báo chính thức đã được ghim, tuyệt đối không được tự suy đoán ngày giờ (Zero Hallucination).*
   - Backend lập chỉ mục tập fixtures này, truy xuất top-k bằng BM25 trên chữ bỏ dấu kết hợp vector đặc trưng, rồi chỉ gửi các nguồn top-k vào context quyết định của Gemini. Toàn bộ kho không bị nhúng vào mọi prompt; backend vẫn là lớp duy nhất được phép lấy dữ kiện và citation để trả lời.
2. **Phục vụ cơ chế hiển thị trích dẫn nguồn cho Người 4 (Prototype UI Lead):**
   - Theo nguyên tắc **HAX G2** (Làm rõ hệ thống làm tốt đến đâu), bot phải hiển thị kèm khối Embed trích dẫn: Tên kênh (`#thong-bao-chung`, `#thong-bao-lop-hoc`), Mã tin nhắn nguồn (`M49744`, `M16114`, `M47011`...), và mốc thời gian đăng.
   - Giao diện chat mock của Người 4 cần nạp file này để render thông tin dẫn chứng chính xác khi người dùng click xem nguồn.
3. **Tuân thủ tuyệt đối Quy định Bảo mật dữ liệu của Ban tổ chức:**
   - Quy định của Hackathon nghiêm cấm commit dataset thật `data/discord-pack/k4_messages.csv` (1.092 tin) lên repo công khai.
   - Do đó, file này **CHỈ chọn lọc 7 thông báo mang tính chất thông tin chung của BTC** (deadline, quy định nộp bài, cú pháp đổi tên hiển thị, lệnh bot), hoàn toàn **KHÔNG chứa bất kỳ tin nhắn cá nhân, thông tin học viên hay dữ liệu nhạy cảm nào**.

---

## 2. Cấu trúc một thông báo mẫu trong file:

```json
{
  "id": "ANN_04",
  "title": "Thông báo chuẩn bị và hạn nộp Lab 02 CVAT",
  "source_channel": "#thong-bao-lop-hoc",
  "source_msg_id": "M16114",
  "posted_at": "2026-09-13 11:21",
  "author": "BTC",
  "content": "Bài tập Lab 02 sử dụng công cụ CVAT. Hạn nộp bài tập Lab 02 là 23:59 ngày 16/09/2026 trên hệ thống VLearn.",
  "key_entities": {
    "deadline": "23:59 16/09/2026",
    "tool": "CVAT",
    "platform": "VLearn (vlearn.dev)",
    "scope": "Lab 02 CVAT"
  }
}
```

## Audit retrieval metadata

`retrieval_terms_audit.json` phân loại từng `retrieval_terms` và `subject_terms` theo bằng chứng nguồn. Xem `RETRIEVAL_TERMS_AUDIT.md` trước khi thêm hoặc giữ một term không xuất hiện trong thông báo BTC; metadata không phải Ground Truth và không được dùng để tạo fact trong reply.
