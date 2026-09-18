"""Data-driven policy mapping, response composition and grounding checks."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import yaml

from codebase.core_ai.decision import Decision, DecisionEngine
from codebase.core_ai.retrieval import RetrievalResult, fold_text


TIME_RE = re.compile(r"\b(?:[01]?\d|2[0-3])(?::|h)[0-5]\d\b")
DATE_RE = re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b")
URL_RE = re.compile(r"https?://[^\s)]+|\b(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s)]*)?", re.I)


def citation_for(source: dict[str, Any]) -> dict[str, Any]:
    """Citations always expose the source's original, verbatim content."""
    return {
        "ground_truth_id": source["id"],
        "message_id": source["source_msg_id"],
        "channel": source["source_channel"],
        "quote": source["content"],
        "url": source.get("url"),
        "source_type": source.get("source_type", "official_ground_truth_fixture"),
        "verified": bool(source.get("verified", True)),
        "published_at": source.get("posted_at"),
    }


def _factual_tokens(value: str) -> set[str]:
    folded = fold_text(value)
    return {
        token.lower().rstrip(".,")
        for pattern in (TIME_RE, DATE_RE, URL_RE)
        for token in pattern.findall(folded)
    }


def verify_grounding(reply: str, sources: list[dict[str, Any]]) -> tuple[str, bool]:
    """Ensure every date/time/link in a grounded reply exists in its sources."""
    reply_tokens = _factual_tokens(reply)
    if not reply_tokens:
        return reply, True
    source_text = " ".join(
        f"{source.get('content', '')} {source.get('key_entities', {})}"
        for source in sources
    )
    supported_tokens = _factual_tokens(source_text)
    if reply_tokens.issubset(supported_tokens):
        return reply, True
    if sources:
        # Safe fallback required by Strict Grounding: no paraphrased factual data.
        return " ".join(str(source["content"]) for source in sources), False
    return (
        "Mình chưa có nguồn chính thức chứa dữ kiện cần thiết nên không thể trả lời chắc chắn.",
        False,
    )


class PolicyEngine:
    def __init__(self, config_path: Path, decision_engine: DecisionEngine) -> None:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        self.policies = payload.get("policies", {})
        self.decision_engine = decision_engine

    @staticmethod
    def _select_sources(
        decision: Decision,
        source_by_id: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [source_by_id[source_id] for source_id in decision.source_ids if source_id in source_by_id]

    def _resolve_intent(
        self,
        policy: dict[str, Any],
        decision: Decision,
        sources: list[dict[str, Any]],
        message: str,
    ) -> str:
        field_intent = policy.get("intent_by_requested_field", {}).get(decision.requested_field)
        if field_intent:
            return str(field_intent)
        if policy.get("intent_from") == "source_route" and sources:
            route = self.decision_engine.route_for_source(sources[0], message)
            return str(route.get("intent", "unknown"))
        if decision.missing_slot:
            intent = policy.get("intent_by_missing_slot", {}).get(decision.missing_slot)
            if intent:
                return str(intent)
        intent = policy.get("intent_by_subject", {}).get(decision.subject)
        return str(intent or policy.get("intent", "unknown"))

    def _compose(
        self,
        policy: dict[str, Any],
        decision: Decision,
        sources: list[dict[str, Any]],
        message: str,
    ) -> str:
        composer = policy.get("composer", "static")
        if composer == "source_field" and sources:
            source = sources[0]
            fields = source.get("field_availability", {})
            field = fields.get(decision.requested_field, {}) if isinstance(fields, dict) else {}
            if isinstance(field, dict) and field.get("state") == "known" and field.get("response"):
                return str(field["response"])
            route = self.decision_engine.route_for_source(source, message)
            return str(route.get("reply_prefix", "")) + str(source["content"])
        if composer == "grounded_false_premise" and sources:
            source = sources[0]
            return (
                "Tin đồn hoặc giả định trong câu hỏi không phải nguồn chính thức. "
                f"Theo thông báo {source['source_msg_id']} tại {source['source_channel']}: "
                f"{source['content']}"
            )
        if composer == "field_not_published" and sources:
            source = sources[0]
            field_labels = policy.get("field_labels", {})
            field_label = str(field_labels.get(decision.requested_field, "thông tin này"))
            scope = str(source.get("key_entities", {}).get("scope", source.get("title", "nội dung này")))
            return (
                f"Thông báo chính thức chưa công bố {field_label} cho {scope}. "
                "Mình không thể tự tạo hoặc suy đoán thông tin chưa được công bố."
            )
        if composer in {"missing_slot", "no_ground_truth", "outside_authority"}:
            templates = policy.get("templates", {})
            key = decision.missing_slot if composer == "missing_slot" else decision.subject
            return str(templates.get(key, policy.get("template", "Mình cần thêm thông tin để trả lời.")))
        return str(policy.get("template", "Mình chưa có câu trả lời phù hợp."))

    def apply(
        self,
        decision: Decision,
        *,
        message: str,
        source_by_id: dict[str, dict[str, Any]],
        confidence: float,
        provider: str,
        retrieval: list[RetrievalResult],
        rule_agreement: bool | None,
        guardrail_rule: str | None = None,
    ) -> dict[str, Any]:
        policy_key = f"{decision.action}:{decision.reason_code}"
        policy = self.policies.get(policy_key)
        if not policy:
            decision = Decision("handoff", (), "unknown", "unsupported")
            policy_key = "handoff:unsupported"
            policy = self.policies[policy_key]

        sources = self._select_sources(decision, source_by_id)
        reply = self._compose(policy, decision, sources, message)
        reply, grounding_verified = verify_grounding(reply, sources)
        options = policy.get("options", [])
        if decision.missing_slot:
            options = policy.get("options_by_missing_slot", {}).get(decision.missing_slot, options)

        return {
            "intent": self._resolve_intent(policy, decision, sources, message),
            "status": str(policy["status"]),
            "confidence_score": round(max(0.0, min(1.0, confidence)), 3),
            "reply_text": reply,
            "source_citation": citation_for(sources[0]) if sources else None,
            "interactive_elements": {
                "type": str(policy.get("interactive_type", "none")),
                "options": options,
            },
            "handoff_metadata": {
                "need_ta": bool(policy.get("need_ta", False)),
                "reason": policy.get("handoff_reason"),
            },
            "processing_metadata": {
                "intent_provider": provider,
                "decision": decision.as_dict(),
                "policy_key": policy_key,
                "guardrail_rule": guardrail_rule,
                "rule_agreement": rule_agreement,
                "requested_field": decision.requested_field,
                "semantic_frame": self.decision_engine.semantic_frame(message),
                "grounding_verified": grounding_verified,
                "retrieval": [
                    {
                        "source_id": item.source_id,
                        "score": round(item.score, 4),
                        "bm25_score": round(item.bm25_score, 4),
                        "embedding_score": round(item.embedding_score, 4),
                    }
                    for item in retrieval
                ],
            },
        }
