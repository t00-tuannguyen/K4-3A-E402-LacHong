# Audit nguồn gốc retrieval metadata

`retrieval_terms_audit.json` phân loại **từng phần tử** trong hai field `retrieval_terms` và `subject_terms` của mỗi thông báo BTC.

Lịch sử Git cho thấy commit `68395ab` chỉ chứa thông báo và `key_entities`; metadata retrieval hiện tại được bổ sung trong worktree chưa commit. Vì vậy audit không suy đoán tác giả hay động cơ lịch sử. Nó dùng các nhãn bằng chứng sau:

- `source_attested`: có trong title/content/key_entities chính thức;
- `source_derived`: diễn đạt lại chính xác từ nguồn;
- `normalization_alias`: biến thể chính tả, số thứ tự hoặc cách nói học viên của khái niệm có nguồn;
- `evaluation_motivated_unverified`: không có căn cứ trong nguồn; có liên hệ với scenario routing/evaluation và cần Data & Evaluation Lead xác nhận.

Term mang nhãn `evaluation_motivated_unverified` không được dùng làm Ground Truth. Nó được giữ trong metadata hiện tại để tránh thay đổi hành vi sản phẩm trong audit này, nhưng phải được review: chuyển thành alias dùng chung, xác minh bằng thông báo BTC mới, hoặc loại bỏ trong một thay đổi tách biệt có đo lại Dev/Sealed Eval.
