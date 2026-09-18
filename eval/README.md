# Quy ước Dev Set và Sealed Eval Set

`dev_set.json` là bộ duy nhất được dùng để viết hoặc điều chỉnh guardrail, retrieval terms, routing rules và policy. `eval_set.json` là bộ đánh giá sealed: chỉ chạy khi release hoặc trước checkpoint để ghi nhận số đo. `golden_set.json` được giữ nguyên như snapshot 30 case ban đầu để đối chiếu lịch sử; runner và UI không đọc file backup này.

> Không được sửa rules dựa trên kết quả `eval_set`. Nếu một case sealed thất bại, ghi nhận nguyên nhân trong `run_results.md`; chỉ điều chỉnh giải pháp khi có bằng chứng độc lập (nguồn BTC mới, lỗi kiến trúc tái hiện được, hoặc phản hồi người dùng), rồi đánh giá lại ở một lần chạy release mới.

## Cách chạy

```bash
# Phát triển hằng ngày: chỉ Dev Set
python eval/run_eval.py --dataset dev --offline

# Đo release: mặc định là Sealed Eval Set
python eval/run_eval.py

# Báo cáo đầy đủ 30 case, chỉ dùng để tổng hợp checkpoint
python eval/run_eval.py --dataset all

# Đo khả năng tổng quát hóa wording mới, không thay đổi Dev/Sealed Set
python eval/run_eval.py --dataset paraphrase --offline --report eval/paraphrase_results.md --json-output eval/paraphrase_results.json

# Chỉ chạy sau khi đã khóa rules: holdout wording độc lập, không sửa theo kết quả
python eval/run_eval.py --dataset paraphrase_holdout --offline --report eval/paraphrase_holdout_results.md --json-output eval/paraphrase_holdout_results.json
```

## Phân bổ

| Category | Dev Set (15) | Sealed Eval Set (15) |
|---|---|---|
| `layer_1_no_ground_truth` | TC_01, TC_25 | TC_02 |
| `layer_2_ambiguity` | TC_03, TC_05 | TC_04, TC_29 |
| `layer_3_out_of_scope` | TC_06, TC_08, TC_27 | TC_07, TC_24 |
| `layer_4_domain_conflict` | TC_09 | TC_10, TC_28 |
| `happy_path` | TC_11, TC_12, TC_14, TC_16, TC_18, TC_20 | TC_13, TC_15, TC_17, TC_19, TC_23, TC_26 |
| `adversarial_edge_case` | TC_21 | TC_22, TC_30 |
| **Nguồn `real_chatlog`** | **8** | **8** |

Cả hai bộ đều phủ đủ 6/6 category. Hai intent trùng trong tập gốc đã được đặt khác bộ: `query_deadline_lab2` (TC_11 Dev / TC_10 Eval) và `query_deadline_team_formation` (TC_12 Dev / TC_13 Eval).

## Paraphrase Test

`paraphrase_set.json` có 30 câu mới (6 case cho mỗi nhóm `slang`, `verbose`, `implied`, `typo`, `boundary`). Mỗi case tham chiếu một case gốc qua `reference_case`, nhưng không lặp wording gốc. Đây là phép đo khả năng retrieval và decision engine tổng quát hóa, không phải tập để vá từng keyword. Kết quả được ghi tại `paraphrase_results.md` và `paraphrase_results.json`; mọi case FAIL phải được giữ lại như evidence của gap thực tế.

## Holdout wording sau khi khóa rules

`paraphrase_holdout_set.json` gồm 20 câu chưa xuất hiện trong Golden Set hoặc Paraphrase Set (4 case cho mỗi nhóm wording). Chỉ chạy sau khi chốt rules ở một mốc release. Không được thay đổi guardrail, retrieval, decision, policy hoặc dữ liệu nguồn theo kết quả holdout của chính lần chạy đó; mọi lỗi phải được ghi lại để xem xét ở một chu kỳ phát triển tiếp theo, với bằng chứng độc lập.

## Content Accuracy

`content_contracts.json` là hợp đồng fact độc lập với Golden Set. Với mỗi case `answered` có Ground Truth và không thuộc coverage gap đã công bố, runner yêu cầu reply chứa các fact nguồn bắt buộc (ví dụ mốc giờ, ngày, lệnh hoặc nền tảng). Chỉ trỏ đúng citation không đủ để PASS. `Content Accuracy` có mẫu số riêng trong báo cáo vì clarification, handoff, reject và các coverage gap được chấm bằng action/safety thay vì fact trả lời.

## Nhật ký đo sau thay đổi kiến trúc

Sau khi bổ sung semantic frame dữ liệu (`topic`, `operation`), Dev Set đã được chạy để kiểm tra hồi quy và đạt **15/15** ở chế độ `offline_local_rules`. Các report Dev cục bộ không version để tránh đưa artifact thay đổi theo từng lần develop vào bản bàn giao. `eval_set` và `paraphrase_holdout_set` không được chạy lại trong cùng chu kỳ phát triển này; báo cáo holdout 8/20 trước thay đổi vẫn được giữ nguyên để phân biệt baseline với phép đo release tiếp theo.
