"""Evaluate the Track B1 assistant against a development or sealed eval set.

Default mode calls the real FastAPI endpoint so CP3 measures the integrated
product against the sealed ``eval_set.json``. Use ``--dataset dev --offline``
for deterministic development checks.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


EVAL_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVAL_DIR.parent
DATASET_PATHS = {
    "dev": EVAL_DIR / "dev_set.json",
    "eval": EVAL_DIR / "eval_set.json",
    "paraphrase": EVAL_DIR / "paraphrase_set.json",
    "paraphrase_holdout": EVAL_DIR / "paraphrase_holdout_set.json",
}
OFFICIAL_SOURCES_PATH = PROJECT_ROOT / "codebase" / "data" / "official_announcements.json"
CONTENT_CONTRACTS_PATH = EVAL_DIR / "content_contracts.json"
DEFAULT_ENDPOINT = "http://127.0.0.1:8000/api/assist"
DEFAULT_REPORT_PATH = EVAL_DIR / "run_results.md"
DEFAULT_JSON_PATH = EVAL_DIR / "run_results.json"

# These evaluation criteria request facts that are not present in the cited
# official announcement. They remain visible as failures until Data/Evaluation
# either supplies a verified source or narrows the expected answer.
GROUND_TRUTH_COVERAGE_GAPS = {
    "TC_23": {
        "reason": (
            "ANN_07 chỉ hướng dẫn lệnh xem XP và bảng xếp hạng; nguồn không xác nhận "
            "điểm onboarding trên lớp có được quy đổi thành XP hay không."
        ),
        "root_cause": (
            "Golden Set kỳ vọng một kết luận nằm ngoài dữ kiện của thông báo chính thức hiện có. "
            "Theo Strict Grounding, trợ lý không được tự suy đoán quan hệ giữa hai loại điểm."
        ),
        "next_action": (
            "Data & Evaluation Lead cần bổ sung thông báo BTC đã xác minh về quy đổi điểm, "
            "hoặc sửa expected answer thành yêu cầu chuyển TA khi chưa có nguồn."
        ),
    },
    "TC_26": {
        "reason": (
            "ANN_01 nêu thời hạn và quy trình lập đội nhưng không nói sinh viên khác lớp lab "
            "có được chung một đội hay không."
        ),
        "root_cause": (
            "Golden Set kỳ vọng chính sách ghép đội liên lớp trong khi Ground Truth hiện tại "
            "không chứa quy định đó. Trả lời có/không sẽ là bịa dữ kiện."
        ),
        "next_action": (
            "Data & Evaluation Lead cần bổ sung thông báo BTC đã xác minh về ghép đội liên lớp, "
            "hoặc đổi expected answer thành clarification/TA handoff."
        ),
    },
}


def _load_content_contracts() -> dict[str, dict[str, Any]]:
    """Load positive source-fact contracts without mutating frozen Golden data."""
    payload = json.loads(CONTENT_CONTRACTS_PATH.read_text(encoding="utf-8"))
    contracts = payload.get("cases", {})
    if not isinstance(contracts, dict):
        raise RuntimeError("content_contracts.json must contain a cases object")
    return {str(case_id): contract for case_id, contract in contracts.items()}


CONTENT_CONTRACTS = _load_content_contracts()


def _load_dataset(dataset: str) -> list[dict[str, Any]]:
    """Load an explicit dataset without silently falling back to another set."""
    selected = ("dev", "eval") if dataset == "all" else (dataset,)
    cases: list[dict[str, Any]] = []
    for name in selected:
        try:
            path = DATASET_PATHS[name]
        except KeyError as error:
            raise ValueError(f"Unknown dataset: {dataset}") from error
        cases.extend(json.loads(path.read_text(encoding="utf-8")))

    case_ids = [case.get("case_id") for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise RuntimeError(f"Dataset '{dataset}' contains duplicate case_id values")
    return cases


def _effective_action(output: dict[str, Any]) -> str:
    status = str(output.get("status", "error"))
    reason = (output.get("handoff_metadata") or {}).get("reason")
    if status == "rejected":
        return "out_of_scope"
    if status == "ta_handoff" and reason == "conflicting_sources":
        return "domain_conflict"
    return status


def _citation_id(output: dict[str, Any]) -> str | None:
    citation = output.get("source_citation") or {}
    return citation.get("ground_truth_id")


def _call_endpoint(endpoint: str, query: str, case_id: str) -> dict[str, Any]:
    payload = {
        "user_id": "golden-set-evaluator",
        "channel_id": "hoi-dap-lab",
        "message_text": query,
        "timestamp": datetime.now().astimezone().isoformat(),
    }
    request = Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "X-Eval-Case": case_id},
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"API returned HTTP {error.code}") from error
    except URLError as error:
        raise RuntimeError("Cannot connect to Core AI API") from error


def _call_offline(query: str) -> dict[str, Any]:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from codebase.core_ai.assistant import answer

    return answer({"message_text": query}, use_gemini=False)


def _sentence_count(text: str) -> int:
    return len([part for part in re.split(r"[.!?]+(?:\s+|$)", text.strip()) if part.strip()])


def _fold_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", str(value).lower())
    return "".join(char for char in normalized if not unicodedata.combining(char)).replace("đ", "d")


def _content_contract_for(case: dict[str, Any]) -> dict[str, Any] | None:
    # Paraphrase sets inherit a fact contract from their Golden reference;
    # this keeps content accuracy independent of wording variations.
    contract_key = str(case.get("reference_case") or case["case_id"])
    contract = CONTENT_CONTRACTS.get(contract_key)
    return contract if isinstance(contract, dict) else None


def _content_accuracy(case: dict[str, Any], reply: str) -> dict[str, Any]:
    contract = _content_contract_for(case)
    if not contract:
        return {
            "scored": False,
            "passed": True,
            "contract_key": None,
            "missing_fact_groups": [],
        }

    folded_reply = _fold_text(reply)
    groups = contract.get("source_fact_groups", [])
    missing = [
        alternatives
        for alternatives in groups
        if not any(_fold_text(term) in folded_reply for term in alternatives)
    ]
    return {
        "scored": True,
        "passed": not missing,
        "contract_key": str(case.get("reference_case") or case["case_id"]),
        "missing_fact_groups": missing,
    }


def _evaluate_case(case: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    expected_action = case["expected_action"]
    actual_action = _effective_action(output)
    expected_source = case.get("expected_ground_truth_id")
    actual_source = _citation_id(output)
    reply = str(output.get("reply_text", ""))
    processing = output.get("processing_metadata") or {}
    content_accuracy = _content_accuracy(case, reply)

    action_match = actual_action == expected_action
    source_match = expected_source is None or actual_source == expected_source
    intent_match = output.get("intent") == case.get("expected_intent")
    coverage_gap = GROUND_TRUTH_COVERAGE_GAPS.get(case["case_id"])

    # A no-source case must not invent a concrete date/time. TC_20 is allowed
    # to cite the official ticket process while explicitly stating no penalty
    # rubric exists.
    has_concrete_datetime = bool(re.search(
        r"\b(?:[01]?\d|2[0-3])[:h][0-5]\d\b|\b\d{1,2}/\d{1,2}/\d{4}\b",
        reply,
        flags=re.IGNORECASE,
    ))
    no_source_is_safe = not has_concrete_datetime or case["case_id"] == "TC_20"
    factuality_pass = (source_match if expected_source else no_source_is_safe) and coverage_gap is None

    sentence_count = _sentence_count(reply)
    conciseness_pass = sentence_count <= 3 and len(reply) <= 500
    safety_pass = action_match and source_match
    overall_pass = (
        intent_match
        and factuality_pass
        and content_accuracy["passed"]
        and conciseness_pass
        and safety_pass
    )

    return {
        "case_id": case["case_id"],
        # The paraphrase protocol groups by wording variation rather than the
        # Golden Set's risk category. Preserve either label in the report.
        "category": case.get("category", case.get("paraphrase_type", "uncategorized")),
        "reference_case": case.get("reference_case"),
        "paraphrase_type": case.get("paraphrase_type"),
        "query": case["user_query"],
        "expected": {
            "intent": case.get("expected_intent"),
            "action": expected_action,
            "ground_truth_id": expected_source,
            "content_contract_key": content_accuracy["contract_key"],
        },
        "actual": {
            "intent": output.get("intent"),
            "status": output.get("status"),
            "effective_action": actual_action,
            "ground_truth_id": actual_source,
            "reply_text": reply,
            "provider": processing.get("intent_provider"),
            "decision": processing.get("decision"),
            "retrieval": processing.get("retrieval", []),
        },
        "checks": {
            "intent_match": intent_match,
            "action_match": action_match,
            "source_match": source_match,
            "ground_truth_coverage": coverage_gap is None,
            "factuality_pass": factuality_pass,
            "content_accuracy_scored": content_accuracy["scored"],
            "content_accuracy_pass": content_accuracy["passed"],
            "conciseness_pass": conciseness_pass,
            "safety_boundary_pass": safety_pass,
        },
        "content_accuracy": content_accuracy,
        "overall_pass": overall_pass,
        "coverage_warning": coverage_gap["reason"] if coverage_gap else None,
    }


def _percentage(passed: int, total: int) -> float:
    return round((passed / total * 100) if total else 0.0, 2)


def _build_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    metrics = {
        "overall": sum(item["overall_pass"] for item in results),
        "intent": sum(item["checks"]["intent_match"] for item in results),
        "action": sum(item["checks"]["action_match"] for item in results),
        "source": sum(item["checks"]["source_match"] for item in results),
        "ground_truth_coverage": sum(item["checks"]["ground_truth_coverage"] for item in results),
        "factuality": sum(item["checks"]["factuality_pass"] for item in results),
        "conciseness": sum(item["checks"]["conciseness_pass"] for item in results),
        "safety_boundary": sum(item["checks"]["safety_boundary_pass"] for item in results),
    }
    content_scored = [
        item for item in results
        if item["checks"].get("content_accuracy_scored", False)
    ]
    content_passed = sum(
        item["checks"].get("content_accuracy_pass", True)
        for item in content_scored
    )
    providers: dict[str, int] = {}
    for item in results:
        provider = str(item["actual"].get("provider") or "unknown")
        providers[provider] = providers.get(provider, 0) + 1
    passed_cases = metrics["overall"]
    summary = {
        "total": total,
        "passed_cases": passed_cases,
        "failed_cases": total - passed_cases,
        "providers": providers,
        **{
            key: {"passed": value, "rate_pct": _percentage(value, total)}
            for key, value in metrics.items()
        },
    }
    summary["content_accuracy"] = {
        "passed": content_passed,
        "total": len(content_scored),
        "rate_pct": _percentage(content_passed, len(content_scored)) if content_scored else None,
    }
    return summary


def _failure_analysis(item: dict[str, Any]) -> dict[str, Any]:
    """Explain every failed check in Vietnamese without hiding poor scores."""
    checks = item["checks"]
    expected = item["expected"]
    actual = item["actual"]
    failed_checks = [
        key for key, value in checks.items()
        if not value and key != "content_accuracy_scored"
    ]
    reasons: list[str] = []

    if not checks.get("intent_match", True):
        reasons.append(
            f"Phân loại sai intent: nhận `{actual.get('intent')}`, "
            f"kỳ vọng `{expected.get('intent')}`."
        )
    if not checks.get("action_match", True):
        reasons.append(
            f"Chọn sai hành động: nhận `{actual.get('effective_action')}`, "
            f"kỳ vọng `{expected.get('action')}`."
        )
    if not checks.get("source_match", True):
        reasons.append(
            f"Dẫn sai nguồn: nhận `{actual.get('ground_truth_id') or '-'}`, "
            f"kỳ vọng `{expected.get('ground_truth_id') or '-'}`."
        )
    if not checks.get("content_accuracy_pass", True):
        missing_groups = (item.get("content_accuracy") or {}).get("missing_fact_groups", [])
        reasons.append(
            "Reply chưa chứa các fact nguồn bắt buộc: "
            + ", ".join(" / ".join(group) for group in missing_groups)
            + "."
        )

    coverage_gap = GROUND_TRUTH_COVERAGE_GAPS.get(item["case_id"])
    if coverage_gap:
        reasons.append(coverage_gap["reason"])
        root_cause = coverage_gap["root_cause"]
        next_action = coverage_gap["next_action"]
    else:
        retrieved_ids = {
            str(item.get("source_id"))
            for item in actual.get("retrieval", [])
            if item.get("source_id")
        }
        expected_source = expected.get("ground_truth_id")
        if expected_source and expected_source not in retrieved_ids:
            reasons.append(
                f"Retrieval gap: top-k không chứa Ground Truth kỳ vọng `{expected_source}`."
            )
            root_cause = (
                "Câu diễn đạt mới không truy xuất được nguồn chính thức cần thiết; "
                "đây là gap retrieval cần được xác minh bằng nhiều wording độc lập."
            )
            next_action = (
                "Kiểm tra normalize không dấu, BM25/embedding score và subject_terms của nguồn; "
                "không thêm keyword chỉ để chữa riêng case này."
            )
        elif not checks.get("content_accuracy_pass", True):
            root_cause = (
                "Gap Content Accuracy: routing/citation có thể đúng nhưng reply chưa nêu đủ "
                "fact mà nguồn chính thức và hợp đồng đánh giá yêu cầu."
            )
            next_action = (
                "Rà soát composer/policy theo requested_field và fact contract; "
                "không thêm dữ kiện ngoài source để làm case pass."
            )
        elif not checks.get("action_match", True):
            reasons.append("Decision/guardrail chọn action khác hành vi kỳ vọng dù dữ kiện đã có hoặc không cần nguồn.")
            root_cause = (
                "Gap routing: retrieval có thể đã đủ, nhưng policy, guardrail hoặc quyết định cục bộ "
                "chưa tổng quát hóa được ý định của câu hỏi."
            )
            next_action = (
                "Nhóm các FAIL có cùng cấu trúc ngữ nghĩa trước khi điều chỉnh luật khai báo hoặc prompt; "
                "không vá theo từng câu."
            )
        elif not checks.get("intent_match", True):
            reasons.append("Action an toàn nhưng ánh xạ intent chưa đúng nhãn canonical.")
            root_cause = "Gap chuẩn hóa intent/routing sau retrieval."
            next_action = "Rà soát source routing rules và policy intent mapping theo nhóm wording, không theo case đơn lẻ."
        elif not checks.get("ground_truth_coverage", True):
            reasons.append("Nguồn Ground Truth chưa chứa đủ dữ kiện để chứng minh câu trả lời kỳ vọng.")
            root_cause = "Nguồn Ground Truth chưa chứa đủ dữ kiện để chứng minh câu trả lời kỳ vọng."
            next_action = "Bổ sung nguồn BTC đã xác minh hoặc điều chỉnh kỳ vọng theo Strict Grounding."
        else:
            root_cause = "Một hoặc nhiều đầu ra thực tế không khớp tiêu chí đã định nghĩa trong bộ đánh giá."
            next_action = "Kiểm tra lại log của case, prompt/rule liên quan và chỉ sửa sau khi có bằng chứng."
        if not checks.get("factuality_pass", True):
            reasons.append("Câu trả lời không vượt qua kiểm tra factuality/Strict Grounding.")
        if not checks.get("content_accuracy_pass", True):
            reasons.append("Câu trả lời không vượt qua kiểm tra Content Accuracy.")
        if not checks.get("conciseness_pass", True):
            reasons.append("Câu trả lời vượt giới hạn 3 câu hoặc 500 ký tự.")
        if not checks.get("safety_boundary_pass", True):
            reasons.append("Câu trả lời không đạt kiểm tra Safety & Boundary.")
    return {
        "failed_checks": failed_checks,
        "reasons": reasons,
        "root_cause": root_cause,
        "next_action": next_action,
    }


def _write_markdown(run: dict[str, Any], path: Path) -> None:
    summary = run["summary"]
    total = summary["total"]
    passed = summary.get("passed_cases", summary["overall"]["passed"])
    failed_count = summary.get("failed_cases", total - passed)
    lines = [
        "# Kết quả bộ đánh giá — Core AI Track B1",
        "",
        f"- Thời điểm chạy: `{run['timestamp']}`",
        f"- Dataset: `{run.get('dataset', 'legacy')}`",
        f"- Chế độ: `{run['mode']}`",
        f"- Intent provider: `{json.dumps(summary['providers'], ensure_ascii=False)}`",
        "",
        "## Tổng quan kết quả thật",
        "",
        "| Số lượt thử | Số lần đúng | Số lần sai | Tỷ lệ đúng |",
        "|---:|---:|---:|---:|",
        f"| **{total}** | **{passed}** | **{failed_count}** | **{summary['overall']['rate_pct']}%** |",
        "",
        "> Báo cáo giữ nguyên số đo thực tế: case sai không bị ẩn, đổi thành PASS hoặc loại khỏi mẫu.",
        "> Không được sửa rules dựa trên kết quả `eval_set`; chỉ dùng `dev_set` để phát triển rules và retrieval.",
        "",
        "## Chỉ số",
        "",
        "| Chỉ số | Đạt | Tỷ lệ |",
        "|---|---:|---:|",
    ]
    for key, label in (
        ("intent", "Intent khớp"),
        ("action", "Action khớp"),
        ("source", "Ground Truth khớp"),
        ("ground_truth_coverage", "Ground Truth đủ dữ kiện"),
        ("factuality", "Factuality"),
        ("content_accuracy", "Content Accuracy (fact nguồn)"),
        ("conciseness", "Conciseness"),
        ("safety_boundary", "Safety & Boundary"),
    ):
        metric = summary[key]
        denominator = metric.get("total", summary["total"])
        rate = f"{metric['rate_pct']}%" if metric["rate_pct"] is not None else "N/A"
        lines.append(f"| {label} | {metric['passed']}/{denominator} | {rate} |")

    groups: dict[str, list[dict[str, Any]]] = {}
    for item in run["results"]:
        group = str(item.get("paraphrase_type") or item.get("category") or "uncategorized")
        groups.setdefault(group, []).append(item)
    if any(item.get("paraphrase_type") for item in run["results"]):
        lines.extend([
            "",
            "## Kết quả theo nhóm wording",
            "",
            "| Nhóm | Số thử | PASS | FAIL | Tỷ lệ đúng |",
            "|---|---:|---:|---:|---:|",
        ])
        for group, items in groups.items():
            group_passed = sum(item["overall_pass"] for item in items)
            lines.append(
                f"| `{group}` | {len(items)} | {group_passed} | {len(items) - group_passed} | "
                f"{_percentage(group_passed, len(items))}% |"
            )

    lines.extend([
        "",
        "## Chi tiết",
        "",
        "| Case | Kết quả | Intent | Action | Nguồn | Content fact |",
        "|---|---|---|---|---|---|",
    ])
    for item in run["results"]:
        expected = item["expected"]
        actual = item["actual"]
        mark = "PASS" if item["overall_pass"] else "FAIL"
        intent = f"{actual['intent']} / {expected['intent']}"
        action = f"{actual['effective_action']} / {expected['action']}"
        source = f"{actual['ground_truth_id'] or '-'} / {expected['ground_truth_id'] or '-'}"
        content = "N/A"
        if item["checks"].get("content_accuracy_scored", False):
            content = "PASS" if item["checks"].get("content_accuracy_pass", False) else "FAIL"
        case_label = item["case_id"]
        if item.get("paraphrase_type"):
            case_label += f" ({item['paraphrase_type']} / {item.get('reference_case')})"
        lines.append(f"| {case_label} | {mark} | `{intent}` | `{action}` | `{source}` | {content} |")

    failed = [item for item in run["results"] if not item["overall_pass"]]
    lines.extend(["", f"## Phân tích lý do {len(failed)} lần sai", ""])
    if not failed:
        lines.append("Không có case sai trong lần chạy này.")
    else:
        gap_counts: dict[str, int] = {}
        for item in failed:
            analysis = item.get("failure_analysis") or _failure_analysis(item)
            root_cause = str(analysis["root_cause"])
            gap_counts[root_cause] = gap_counts.get(root_cause, 0) + 1
        lines.extend([
            "| Nhóm gap | Số case FAIL |",
            "|---|---:|",
        ])
        lines.extend(f"| {cause} | {count} |" for cause, count in gap_counts.items())
        lines.append("")
        for item in failed:
            analysis = item.get("failure_analysis") or _failure_analysis(item)
            expected = item["expected"]
            actual = item["actual"]
            lines.extend([
                f"### {item['case_id']}",
                "",
                *(
                    [f"- Paraphrase: `{item['paraphrase_type']}` · tham chiếu `{item['reference_case']}`."]
                    if item.get("paraphrase_type") else []
                ),
                f"- Câu hỏi thử: {item['query']}",
                (
                    f"- Kỳ vọng: intent `{expected.get('intent')}`, action `{expected.get('action')}`, "
                    f"nguồn `{expected.get('ground_truth_id') or '-'}`."
                ),
                (
                    f"- Thực tế: intent `{actual.get('intent')}`, action `{actual.get('effective_action')}`, "
                    f"nguồn `{actual.get('ground_truth_id') or '-'}`."
                ),
                f"- Chỉ số không đạt: `{', '.join(analysis['failed_checks'])}`.",
                "- Lý do sai:",
            ])
            lines.extend(f"  - {reason}" for reason in analysis["reasons"])
            lines.extend([
                f"- Nguyên nhân gốc: {analysis['root_cause']}",
                f"- Hướng xử lý: {analysis['next_action']}",
                "",
            ])

    while lines and not lines[-1]:
        lines.pop()
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(*, endpoint: str, offline: bool, dataset: str = "eval", delay_seconds: float = 0.0) -> dict[str, Any]:
    cases = _load_dataset(dataset)
    official_sources: list[dict[str, Any]] = json.loads(OFFICIAL_SOURCES_PATH.read_text(encoding="utf-8"))
    source_ids = {source["id"] for source in official_sources}
    missing_ids = sorted({
        case["expected_ground_truth_id"]
        for case in cases
        if case.get("expected_ground_truth_id") and case["expected_ground_truth_id"] not in source_ids
    })
    if missing_ids:
        raise RuntimeError(f"Dataset '{dataset}' references missing Ground Truth IDs: {missing_ids}")

    results: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        try:
            output = _call_offline(case["user_query"]) if offline else _call_endpoint(
                endpoint, case["user_query"], case["case_id"]
            )
        except RuntimeError as error:
            output = {
                "intent": "error",
                "status": "error",
                "reply_text": str(error),
                "source_citation": None,
                "handoff_metadata": {"need_ta": False, "reason": "evaluation_error"},
                "processing_metadata": {"intent_provider": "error"},
            }
        evaluated = _evaluate_case(case, output)
        results.append(evaluated)
        print(f"{case['case_id']}: {'PASS' if evaluated['overall_pass'] else 'FAIL'}")
        if not offline and delay_seconds > 0 and index < len(cases) - 1:
            time.sleep(delay_seconds)

    return {
        "timestamp": datetime.now().astimezone().isoformat(),
        "dataset": dataset,
        "mode": "offline_local_rules" if offline else f"live_api:{endpoint}",
        "summary": _build_summary(results),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Track B1 development or sealed evaluation")
    parser.add_argument(
        "--dataset",
        choices=("dev", "eval", "all", "paraphrase", "paraphrase_holdout"),
        default="eval",
        help="Dataset to run; default is the sealed eval_set.json. 'all' means dev + eval only.",
    )
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--offline", action="store_true", help="Call Core AI directly without HTTP/Gemini")
    parser.add_argument("--delay-seconds", type=float, default=0.0, help="Pause between live API cases to respect RPM quota")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_PATH)
    parser.add_argument(
        "--render-existing",
        type=Path,
        help="Regenerate reports from an existing JSON run without calling the API again",
    )
    args = parser.parse_args()

    if args.render_existing:
        result = json.loads(args.render_existing.read_text(encoding="utf-8"))
        result.setdefault("dataset", "legacy")
        result["summary"] = _build_summary(result["results"])
    else:
        result = run(
            endpoint=args.endpoint,
            offline=args.offline,
            dataset=args.dataset,
            delay_seconds=max(args.delay_seconds, 0.0),
        )
    for item in result["results"]:
        item["failure_analysis"] = _failure_analysis(item) if not item["overall_pass"] else None
    args.json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(result, args.report)
    summary = result["summary"]
    print(f"Overall: {summary['overall']['passed']}/{summary['total']} ({summary['overall']['rate_pct']}%)")
    print(f"Markdown: {args.report}")
    print(f"JSON: {args.json_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
