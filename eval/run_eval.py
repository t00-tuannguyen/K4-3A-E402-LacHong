"""Evaluate the Track B1 assistant against eval/golden_set.json.

Default mode calls the real FastAPI endpoint so CP3 measures the integrated
product. Use --offline only for deterministic development checks.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


EVAL_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EVAL_DIR.parent
GOLDEN_SET_PATH = EVAL_DIR / "golden_set.json"
OFFICIAL_SOURCES_PATH = PROJECT_ROOT / "codebase" / "data" / "official_announcements.json"
DEFAULT_ENDPOINT = "http://127.0.0.1:8000/api/assist"
DEFAULT_REPORT_PATH = EVAL_DIR / "run_results.md"
DEFAULT_JSON_PATH = EVAL_DIR / "run_results.json"

# These Golden Set criteria request facts that are not present in the cited
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


def _evaluate_case(case: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    expected_action = case["expected_action"]
    actual_action = _effective_action(output)
    expected_source = case.get("expected_ground_truth_id")
    actual_source = _citation_id(output)
    reply = str(output.get("reply_text", ""))

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
    overall_pass = intent_match and factuality_pass and conciseness_pass and safety_pass

    return {
        "case_id": case["case_id"],
        "category": case["category"],
        "query": case["user_query"],
        "expected": {
            "intent": case.get("expected_intent"),
            "action": expected_action,
            "ground_truth_id": expected_source,
        },
        "actual": {
            "intent": output.get("intent"),
            "status": output.get("status"),
            "effective_action": actual_action,
            "ground_truth_id": actual_source,
            "reply_text": reply,
            "provider": (output.get("processing_metadata") or {}).get("intent_provider"),
        },
        "checks": {
            "intent_match": intent_match,
            "action_match": action_match,
            "source_match": source_match,
            "ground_truth_coverage": coverage_gap is None,
            "factuality_pass": factuality_pass,
            "conciseness_pass": conciseness_pass,
            "safety_boundary_pass": safety_pass,
        },
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
    providers: dict[str, int] = {}
    for item in results:
        provider = str(item["actual"].get("provider") or "unknown")
        providers[provider] = providers.get(provider, 0) + 1
    passed_cases = metrics["overall"]
    return {
        "total": total,
        "passed_cases": passed_cases,
        "failed_cases": total - passed_cases,
        "providers": providers,
        **{
            key: {"passed": value, "rate_pct": _percentage(value, total)}
            for key, value in metrics.items()
        },
    }


def _failure_analysis(item: dict[str, Any]) -> dict[str, Any]:
    """Explain every failed check in Vietnamese without hiding poor scores."""
    checks = item["checks"]
    expected = item["expected"]
    actual = item["actual"]
    failed_checks = [key for key, value in checks.items() if not value]
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

    coverage_gap = GROUND_TRUTH_COVERAGE_GAPS.get(item["case_id"])
    if coverage_gap:
        reasons.append(coverage_gap["reason"])
        root_cause = coverage_gap["root_cause"]
        next_action = coverage_gap["next_action"]
    else:
        if not checks.get("ground_truth_coverage", True):
            reasons.append("Nguồn Ground Truth chưa chứa đủ dữ kiện để chứng minh câu trả lời kỳ vọng.")
        if not checks.get("factuality_pass", True):
            reasons.append("Câu trả lời không vượt qua kiểm tra factuality/Strict Grounding.")
        if not checks.get("conciseness_pass", True):
            reasons.append("Câu trả lời vượt giới hạn 3 câu hoặc 500 ký tự.")
        if not checks.get("safety_boundary_pass", True):
            reasons.append("Câu trả lời không đạt kiểm tra Safety & Boundary.")
        root_cause = "Một hoặc nhiều đầu ra thực tế không khớp tiêu chí đã định nghĩa trong Golden Set."
        next_action = "Kiểm tra lại log của case, prompt/rule liên quan và chỉ sửa sau khi có bằng chứng."

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
        "# Kết quả Golden Set — Core AI Track B1",
        "",
        f"- Thời điểm chạy: `{run['timestamp']}`",
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
        ("conciseness", "Conciseness"),
        ("safety_boundary", "Safety & Boundary"),
    ):
        metric = summary[key]
        lines.append(f"| {label} | {metric['passed']}/{summary['total']} | {metric['rate_pct']}% |")

    lines.extend([
        "",
        "## Chi tiết",
        "",
        "| Case | Kết quả | Intent | Action | Nguồn |",
        "|---|---|---|---|---|",
    ])
    for item in run["results"]:
        expected = item["expected"]
        actual = item["actual"]
        mark = "PASS" if item["overall_pass"] else "FAIL"
        intent = f"{actual['intent']} / {expected['intent']}"
        action = f"{actual['effective_action']} / {expected['action']}"
        source = f"{actual['ground_truth_id'] or '-'} / {expected['ground_truth_id'] or '-'}"
        lines.append(f"| {item['case_id']} | {mark} | `{intent}` | `{action}` | `{source}` |")

    failed = [item for item in run["results"] if not item["overall_pass"]]
    lines.extend(["", f"## Phân tích lý do {len(failed)} lần sai", ""])
    if not failed:
        lines.append("Không có case sai trong lần chạy này.")
    else:
        for item in failed:
            analysis = item.get("failure_analysis") or _failure_analysis(item)
            expected = item["expected"]
            actual = item["actual"]
            lines.extend([
                f"### {item['case_id']}",
                "",
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


def run(*, endpoint: str, offline: bool, delay_seconds: float = 0.0) -> dict[str, Any]:
    cases: list[dict[str, Any]] = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    official_sources: list[dict[str, Any]] = json.loads(OFFICIAL_SOURCES_PATH.read_text(encoding="utf-8"))
    source_ids = {source["id"] for source in official_sources}
    missing_ids = sorted({
        case["expected_ground_truth_id"]
        for case in cases
        if case.get("expected_ground_truth_id") and case["expected_ground_truth_id"] not in source_ids
    })
    if missing_ids:
        raise RuntimeError(f"Golden Set references missing Ground Truth IDs: {missing_ids}")

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
        "mode": "offline_local_rules" if offline else f"live_api:{endpoint}",
        "summary": _build_summary(results),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Track B1 Golden Set evaluation")
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
        result["summary"] = _build_summary(result["results"])
    else:
        result = run(endpoint=args.endpoint, offline=args.offline, delay_seconds=max(args.delay_seconds, 0.0))
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
