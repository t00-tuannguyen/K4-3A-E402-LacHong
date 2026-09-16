# SƠ ĐỒ LUỒNG HOẠT ĐỘNG — TRỢ LÝ HỌC VIÊN DISCORD (CP2)
> **Dự án:** Trợ lý Học viên Discord (Track B1) — Nhóm LacHong (Lớp 3A)  
> **Tác giả:** Trần Phạm Thái Vũ (Mã HV: `2A202602695`) — Data & Evaluation Lead  

---

## 1. SƠ ĐỒ LUỒNG TỔNG THỂ (MERMAID FLOWCHART)

```mermaid
flowchart TD
    Start(["Học viên gửi câu hỏi trên Discord"]) --> P1["1. Nhận diện Ý định (Intent Classification)"]
    
    P1 -->|"Chào hỏi / Chitchat ngắn"| R0["Chào ngắn gọn + Nêu rõ phạm vi hỗ trợ (HAX G1)"]
    P1 -->|"Ngoài thẩm quyền (Điểm danh cá nhân / Xin gia hạn)"| R3["[Đường 5 - Out of Scope]<br>Từ chối lịch sự theo quy chế (HAX G11)<br>+ Hướng dẫn gõ /ticket create"]
    
    P1 -->|"Hỏi về Deadline / Quy chế / Codelab"| P2{"2. Độ rõ của câu hỏi (Entity Detection)"}
    
    P2 -->|"Mơ hồ / Thiếu tên Lab / Lớp"| R2["[Đường 2 - Ambiguity / Low-confidence]<br>Hỏi lại 1 câu duy nhất (HAX G10)<br>+ Hiện nút bấm gợi ý (Chips)"]
    
    P2 -->|"Rõ ràng (Đủ Lab, Level, Nội dung)"| P3{"3. Kiểm tra nguồn thông báo chính thức (Grounding)"}
    
    P3 -->|"Có trong thông báo ghim / Kênh chính thức"| R1["[Đường 1 - Happy Path]<br>Trả lời ngắn gọn ≤3 câu<br>+ Trích dẫn link thông báo nguồn (HAX G2)"]
    
    P3 -->|"Chưa có thông báo / Không có căn cứ"| R4["[Đường 3 - No Ground Truth]<br>Báo 'BTC chưa công bố chính thức'<br>+ Nút bấm [🔴 Chuyển cho TA]"]
    
    P3 -->|"Phát hiện 2 nguồn thông báo mâu thuẫn"| R5["[Đường 6 - Domain Conflict]<br>Cảnh báo có sự lệch thông tin<br>+ Gắn tag @TA xác minh khẩn cấp"]

    R2 -.->|"Học viên bấm chọn Lab"| P3
    R4 -.->|"Học viên bấm chuyển TA"| Handoff["Tự động tạo Thread tag @TA kèm trích dẫn"]
```

---

## 2. TÓM TẮT CÁC ĐIỂM DỪNG TƯƠNG TÁC (INTERACTION NODES)

| Nút xử lý | Ý nghĩa nghiệp vụ | Nguyên tắc HAX/PAIR áp dụng |
|---|---|---|
| **R0 (Chào hỏi)** | Phản hồi chào mừng và nêu rõ giới hạn: chỉ hỗ trợ tra cứu deadline & quy chế nộp bài chính thức. | **HAX G1** (Làm rõ hệ thống làm được gì) |
| **R1 (Happy Path)** | Trả lời ngắn gọn $\le$ 3 câu, luôn kèm theo khối Embed dẫn chứng link thông báo ghim. | **HAX G2** (Làm rõ hệ thống làm tốt đến đâu) |
| **R2 (Mơ hồ)** | Không tự suy đoán bừa bãi; hỏi lại 1 câu duy nhất kèm các chips lựa chọn (`Lab 01`, `Lab 02`, `Ghép đội`). | **HAX G10** (Thu hẹp phạm vi khi không chắc) |
| **R3 (Ngoài quyền)** | Từ chối lịch sự do giới hạn quyền truy cập dữ liệu cá nhân; hướng dẫn học viên gõ `/ticket create`. | **HAX G11** (Giải thích lý do từ chối) |
| **R4 (Chưa công bố)** | Báo rõ "BTC chưa công bố thông tin chính thức", hiển thị nút `[🔴 Chuyển cho TA hỗ trợ]`. | **PAIR** (Errors & Graceful Failure) |
| **R5 (Xung đột nguồn)** | Nhận diện mâu thuẫn giữa các kênh (Email vs Discord), cảnh báo học viên và gắn cờ ưu tiên cho TA. | **Đặc thù domain** (Conflict Handling) |
