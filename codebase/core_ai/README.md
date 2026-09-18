# Core AI — kiến trúc quyết định có grounding

`POST /api/assist` giữ nguyên contract với frontend, nhưng phần xử lý bên trong đi qua sáu tầng độc lập:

1. **Guardrail trước LLM** — `guardrails.py` đọc `config/guardrails.yaml`; prompt injection, giả mạo quyền hạn và yêu cầu sửa dữ liệu bị chặn trước khi gọi API.
2. **Hybrid retrieval** — `retrieval.py` kết hợp BM25 trên tiếng Việt bỏ dấu với vector đặc trưng băm ổn định. Dữ liệu truy xuất nằm trong `codebase/data/official_announcements.json`.
3. **Structured decision** — `decision.py` buộc LLM trả sáu trường `action`, `source_ids`, `subject`, `requested_field`, `reason_code`, `missing_slot`. Fallback cục bộ tạo semantic frame từ YAML (`topic`, `operation`) trước khi áp dụng policy, nên câu dài/gián tiếp được định tuyến theo thao tác và đối tượng thay vì theo một câu keyword. `requested_field` phân biệt deadline, nơi nộp, link nộp và chính sách nộp muộn; `source_ids` ngoài top-k bị từ chối.
4. **Policy table** — `policy.py` ánh xạ `(action, reason_code)` từ `config/policies.yaml` sang status API, intent, nút bấm, handoff và kiểu soạn câu trả lời.
5. **Soạn và kiểm chứng** — citation được dựng từ bản ghi nguồn, không lấy từ nội dung LLM. Mọi ngày, giờ và URL trong câu trả lời phải xuất hiện trong nguồn đã chọn; nếu không, hệ thống quay về nguyên văn nguồn.
6. **Confidence và đồng thuận** — confidence kết hợp điểm retrieval với mức đồng thuận giữa quyết định luật cục bộ và LLM. Bất đồng không được chọn đại: hệ thống yêu cầu làm rõ; nguồn ngoài top-k được chuyển TA.

## Ranh giới giữa code và dữ liệu

- Thêm hoặc cập nhật thông báo: sửa `codebase/data/official_announcements.json`, gồm nội dung nguồn, metadata định tuyến như `retrieval_terms`, `subject_terms`, `claim_coverage`, `default_route`, và `field_availability`. Field có thể là `known`, `not_published`, `unknown` hoặc `requires_context`.
- Thêm luật an toàn: sửa `config/guardrails.yaml`.
- Thêm luật fallback/feature quyết định: sửa `config/decision_rules.yaml`, gồm `semantic_slots` và `rules`; không thêm nhánh nghiệp vụ vào `assistant.py`.
- Đổi cách hiển thị một kết quả: sửa `config/policies.yaml`.
- Đổi hợp đồng quyết định của LLM: sửa `config/system_prompt.md` cùng schema/test tương ứng.

Không cần thêm chuỗi alias hay nhánh nghiệp vụ theo từng thông báo vào `assistant.py`.

## Chạy và kiểm tra

```powershell
python -m uvicorn codebase.core_ai.server:app --host 127.0.0.1 --port 8000
python -m unittest discover -s tests -p "test_*.py"
python eval/run_eval.py --offline
```

Chế độ offline dùng cùng guardrail, retrieval, policy và verifier, chỉ thay bước gọi LLM bằng decision engine cục bộ để kiểm thử lặp lại được.
