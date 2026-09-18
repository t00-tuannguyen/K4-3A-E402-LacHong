"""Structured decision contract and deterministic offline decision engine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import yaml

from codebase.core_ai.normalization import TextNormalizer
from codebase.core_ai.retrieval import RetrievalResult, fold_text


ACTIONS = ("answer", "clarify", "handoff", "reject")
REASON_CODES = (
    "greeting",
    "grounded",
    "grounded_false_premise",
    "missing_specific_policy",
    "missing_subject",
    "source_context_missing",
    "decision_disagreement",
    "no_ground_truth",
    "conflicting_sources",
    "unverified_claim",
    "unsupported",
    "invalid_source_selection",
    "outside_authority",
    "prompt_injection",
    "field_not_published",
)


@dataclass(frozen=True)
class Decision:
    action: str
    source_ids: tuple[str, ...]
    subject: str
    reason_code: str
    missing_slot: str | None = None
    requested_field: str = "unknown"

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "source_ids": list(self.source_ids),
            "subject": self.subject,
            "reason_code": self.reason_code,
            "missing_slot": self.missing_slot,
            "requested_field": self.requested_field,
        }

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "Decision":
        required = {"action", "source_ids", "subject", "reason_code", "missing_slot"}
        allowed = required | {"requested_field"}
        if not isinstance(payload, dict) or not required.issubset(payload) or set(payload) - allowed:
            raise ValueError("decision must contain the five required contract fields only")
        action = str(payload["action"])
        reason_code = str(payload["reason_code"])
        source_ids = payload["source_ids"]
        if action not in ACTIONS:
            raise ValueError(f"unsupported action: {action}")
        if reason_code not in REASON_CODES:
            raise ValueError(f"unsupported reason_code: {reason_code}")
        if not isinstance(source_ids, list) or not all(isinstance(item, str) for item in source_ids):
            raise ValueError("source_ids must be a list of strings")
        missing_slot = payload["missing_slot"]
        if missing_slot is not None and not isinstance(missing_slot, str):
            raise ValueError("missing_slot must be a string or null")
        return cls(
            action=action,
            source_ids=tuple(source_ids),
            subject=str(payload["subject"]),
            reason_code=reason_code,
            missing_slot=missing_slot,
            requested_field=str(payload.get("requested_field", "unknown")),
        )


def decision_schema(allowed_source_ids: list[str]) -> dict[str, Any]:
    source_schema: dict[str, Any] = {"type": "string"}
    if allowed_source_ids:
        source_schema["enum"] = allowed_source_ids
    return {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": list(ACTIONS)},
            "source_ids": {"type": "array", "items": source_schema},
            "subject": {"type": "string"},
            "reason_code": {"type": "string", "enum": list(REASON_CODES)},
            "missing_slot": {"type": "string", "nullable": True},
            "requested_field": {"type": "string"},
        },
        "required": [
            "action", "source_ids", "subject", "reason_code", "missing_slot",
            "requested_field",
        ],
    }


class DecisionEngine:
    """Generate a policy-ready decision without embedding domain branches in the orchestrator."""

    def __init__(self, config_path: Path, *, normalizer: TextNormalizer | None = None) -> None:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        self.config = payload
        self.normalizer = normalizer
        retrieval_config = payload.get("retrieval", {})
        self.top_k = int(retrieval_config.get("top_k", 3))
        self.minimum_score = float(retrieval_config.get("minimum_score", 0.30))
        self.rules = sorted(
            payload.get("rules", []),
            key=lambda rule: int(rule.get("priority", 0)),
            reverse=True,
        )
        self.field_rules = sorted(
            payload.get("field_rules", []),
            key=lambda rule: int(rule.get("priority", 0)),
            reverse=True,
        )
        # Topics and operations are configured as reusable semantic slots.
        # They let a rule describe an intent such as “asking where to submit”
        # without coupling the Python pipeline to a particular Lab or test
        # wording.  The same slot can be reused by several policies.
        raw_slots = payload.get("semantic_slots", {})
        self.semantic_slots = {
            str(slot_name): sorted(
                profiles if isinstance(profiles, list) else [],
                key=lambda profile: int(profile.get("priority", 0)),
                reverse=True,
            )
            for slot_name, profiles in raw_slots.items()
            if isinstance(slot_name, str)
        }
        self.authoritative_reason_codes = {
            str(reason) for reason in payload.get("authoritative_reason_codes", [])
        }

    @staticmethod
    def _contains(text: str, term: str) -> bool:
        needle = fold_text(term).strip()
        if not needle:
            return False
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", text))

    def _normalize(self, value: str) -> str:
        return self.normalizer.normalize(value) if self.normalizer else fold_text(value)

    def _contains_any(self, text: str, terms: list[str]) -> bool:
        return any(self._contains(text, term) for term in terms)

    def _named_source_count(self, text: str) -> int:
        return sum(
            self._contains_any(text, group)
            for group in self.config.get("official_source_groups", [])
        )

    def _is_rumour(self, text: str) -> bool:
        if self._contains_any(text, self.config.get("rumour_markers", [])):
            return True
        return bool(re.search(r"\bban\s+\S+\s+(?:bao|noi)\b", text))

    def _is_false_premise(self, text: str, *, explicit_conflict: bool) -> bool:
        if explicit_conflict:
            return False
        if self._is_rumour(text) or self._contains_any(
            text, self.config.get("deadline_change_markers", [])
        ):
            return True
        # A neutral confirmation such as "Có phải hạn Lab 2 là 23:59?" is not
        # a false premise.  An assumption becomes one only when it also claims
        # that an official fact was negated, removed or replaced.
        return self._contains_any(
            text, self.config.get("assumption_markers", [])
        ) and self._contains_any(
            text, self.config.get("claim_challenge_markers", [])
        )

    def requested_field(self, message: str) -> str:
        """Resolve the requested fact type from declarative field rules."""
        text = self._normalize(message)
        for rule in self.field_rules:
            if self._match_text(text, rule.get("match", {})):
                return str(rule["field"])

        return self._claim_type(text)

    def _claim_type(self, text: str) -> str:
        deadline_changes = self.config.get("deadline_change_markers", [])
        if self._contains_any(text, deadline_changes):
            return "deadline"
        for claim_type, terms in self.config.get("claim_types", {}).items():
            if self._contains_any(text, terms):
                return str(claim_type)
        return "generic"

    def route_for_source(self, source: dict[str, Any], message: str) -> dict[str, Any]:
        text = self._normalize(message)
        for route in source.get("routing_rules", []):
            if self._match_text(text, route):
                return {**source.get("default_route", {}), **route}
        return dict(source.get("default_route", {"intent": "unknown", "subject": "unknown"}))

    def _source_is_identified(self, source: dict[str, Any], text: str) -> bool:
        return self._contains_any(text, source.get("subject_terms", []))

    @staticmethod
    def _field_availability(source: dict[str, Any], requested_field: str) -> dict[str, Any]:
        fields = source.get("field_availability", {})
        candidate = fields.get(requested_field, {}) if isinstance(fields, dict) else {}
        return candidate if isinstance(candidate, dict) else {}

    @staticmethod
    def _field_state(field: dict[str, Any]) -> str:
        return str(field.get("state", "unknown"))

    def is_authoritative(self, decision: Decision) -> bool:
        return decision.reason_code in self.authoritative_reason_codes

    def _identified_result(
        self,
        text: str,
        retrieval: list[RetrievalResult],
    ) -> RetrievalResult | None:
        """Return the best explicitly named source anywhere in retrieved top-k."""
        return next(
            (
                result
                for result in retrieval
                if self._source_is_identified(result.source, text)
            ),
            None,
        )

    def _match_text(self, text: str, match: dict[str, Any]) -> bool:
        any_terms = match.get("any_terms", [])
        if any_terms and not self._contains_any(text, any_terms):
            return False
        all_terms = match.get("all_terms", [])
        if all_terms and not all(self._contains(text, term) for term in all_terms):
            return False
        if any(self._contains(text, term) for term in match.get("none_terms", [])):
            return False
        for group in match.get("all_groups", []):
            if not self._contains_any(text, group):
                return False
        regex_any = match.get("regex_any", [])
        if regex_any and not any(re.search(pattern, text) for pattern in regex_any):
            return False
        return True

    def _semantic_frame(self, text: str) -> dict[str, str]:
        """Extract declared topic/operation slots from a normalized message.

        This is deliberately a small configuration interpreter, not a list of
        domain branches. A new topic is a profile in YAML, and decision rules
        consume its slot value through ``all_slots``/``any_slots``.
        """
        frame: dict[str, str] = {}
        for slot_name, profiles in self.semantic_slots.items():
            for profile in profiles:
                if self._match_text(text, profile.get("match", {})):
                    frame[slot_name] = str(profile["value"])
                    break
        return frame

    def semantic_frame(self, message: str) -> dict[str, str]:
        """Expose the data-derived frame for diagnostics and regression tests."""
        return self._semantic_frame(self._normalize(message))

    @staticmethod
    def _slot_value_matches(actual: str | None, expected: Any) -> bool:
        allowed = expected if isinstance(expected, list) else [expected]
        return actual is not None and str(actual) in {str(value) for value in allowed}

    def _match_slots(self, frame: dict[str, str], match: dict[str, Any]) -> bool:
        for slot_name, expected in match.get("all_slots", {}).items():
            if not self._slot_value_matches(frame.get(str(slot_name)), expected):
                return False
        any_slots = match.get("any_slots", {})
        if any_slots and not any(
            self._slot_value_matches(frame.get(str(slot_name)), expected)
            for slot_name, expected in any_slots.items()
        ):
            return False
        for slot_name, expected in match.get("none_slots", {}).items():
            if self._slot_value_matches(frame.get(str(slot_name)), expected):
                return False
        return True

    def _features(self, text: str, retrieval: list[RetrievalResult]) -> dict[str, bool]:
        rumour = self._is_rumour(text)
        named_sources = self._named_source_count(text)
        # Both `18h` and `18:00` are Vietnamese time forms. They must count
        # equally when two official sources report incompatible times.
        distinct_times = set(re.findall(r"\b(?:[01]?\d|2[0-3])(?::[0-5]\d|h(?:[0-5]\d)?)\b", text))
        distinct_dates = set(re.findall(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", text))
        disagreement = (
            len(distinct_times) >= 2
            or len(distinct_dates) >= 2
            or self._contains_any(text, self.config.get("disagreement_markers", []))
        )
        identified_source = self._identified_result(text, retrieval) is not None
        return {
            "rumour": rumour,
            "multiple_sources": named_sources >= 2,
            "explicit_conflict": not rumour and named_sources >= 2 and disagreement,
            "identified_source": identified_source,
        }

    def _rule_matches(
        self,
        text: str,
        match: dict[str, Any],
        features: dict[str, bool],
        frame: dict[str, str],
        top_score: float,
    ) -> bool:
        if not self._match_text(text, match):
            return False
        if not self._match_slots(frame, match):
            return False
        if any(not features.get(name, False) for name in match.get("all_features", [])):
            return False
        if any(features.get(name, False) for name in match.get("none_features", [])):
            return False
        if top_score < float(match.get("min_retrieval_score", 0.0)):
            return False
        if top_score > float(match.get("max_retrieval_score", 1.0)):
            return False
        return True

    def _decision_from_rule(
        self,
        rule: dict[str, Any],
        retrieval: list[RetrievalResult],
        text: str,
        requested_field: str,
    ) -> Decision:
        payload = rule["decision"]
        source_ids = payload.get("source_ids", [])
        if payload.get("source_from_retrieval") and retrieval:
            selected = self._identified_result(text, retrieval) or retrieval[0]
            source_ids = [selected.source_id]
        return Decision(
            action=str(payload["action"]),
            source_ids=tuple(map(str, source_ids)),
            subject=str(payload.get("subject", "unknown")),
            reason_code=str(payload["reason_code"]),
            missing_slot=payload.get("missing_slot"),
            requested_field=str(payload.get("requested_field", requested_field)),
        )

    def local_decision(self, message: str, retrieval: list[RetrievalResult]) -> Decision:
        text = self._normalize(message)
        requested_field = self.requested_field(message)
        top_score = retrieval[0].score if retrieval else 0.0
        features = self._features(text, retrieval)
        frame = self._semantic_frame(text)

        high_priority_rules = [rule for rule in self.rules if int(rule.get("priority", 0)) >= 80]
        remaining_rules = [rule for rule in self.rules if int(rule.get("priority", 0)) < 80]

        for rule in high_priority_rules:
            if self._rule_matches(text, rule.get("match", {}), features, frame, top_score):
                return self._decision_from_rule(rule, retrieval, text, requested_field)

        false_premise = self._is_false_premise(
            text,
            explicit_conflict=features["explicit_conflict"],
        )
        if false_premise:
            claim_type = requested_field
            identified_result = self._identified_result(text, retrieval)
            if identified_result:
                source = identified_result.source
                field = self._field_availability(source, requested_field)
                if self._field_state(field) == "known" or claim_type in source.get("claim_coverage", []):
                    route = self.route_for_source(source, message)
                    return Decision(
                        action="answer",
                        source_ids=(identified_result.source_id,),
                        subject=str(route.get("subject", claim_type)),
                        reason_code="grounded_false_premise",
                        requested_field=requested_field,
                    )
            if claim_type == "deadline" and not features["identified_source"]:
                return Decision(
                    action="clarify",
                    source_ids=(),
                    subject="deadline",
                    reason_code="missing_subject",
                    missing_slot="assignment",
                    requested_field=requested_field,
                )
            return Decision(
                action="handoff",
                source_ids=(),
                subject=claim_type,
                reason_code="unverified_claim",
                requested_field=requested_field,
            )

        for rule in remaining_rules:
            if self._rule_matches(text, rule.get("match", {}), features, frame, top_score):
                return self._decision_from_rule(rule, retrieval, text, requested_field)

        identified_result = self._identified_result(text, retrieval)
        if identified_result and identified_result.score >= self.minimum_score:
            source = identified_result.source
            field = self._field_availability(source, requested_field)
            state = self._field_state(field)
            if state == "requires_context":
                return Decision(
                    action="clarify",
                    source_ids=(identified_result.source_id,),
                    subject=str(source.get("default_route", {}).get("subject", "unknown")),
                    reason_code="missing_subject",
                    missing_slot=str(field.get("context_slot", requested_field)),
                    requested_field=requested_field,
                )
            if state == "not_published":
                return Decision(
                    action="answer",
                    source_ids=(identified_result.source_id,),
                    subject=str(source.get("default_route", {}).get("subject", "unknown")),
                    reason_code="field_not_published",
                    requested_field=requested_field,
                )
            route = self.route_for_source(source, message)
            action = str(route.get("action", "answer"))
            reason_code = str(route.get("reason_code", "grounded"))
            return Decision(
                action=action,
                source_ids=(identified_result.source_id,),
                subject=str(route.get("subject", source.get("default_route", {}).get("subject", "unknown"))),
                reason_code=reason_code,
                missing_slot=route.get("missing_slot"),
                requested_field=requested_field,
            )

        return Decision(
            action="handoff",
            source_ids=(),
            subject="unknown",
            reason_code="unsupported",
            requested_field=requested_field,
        )

    @staticmethod
    def decisions_agree(left: Decision, right: Decision) -> bool:
        if left.action != right.action:
            return False
        if left.source_ids or right.source_ids:
            same_source = bool(set(left.source_ids) & set(right.source_ids))
            safety_reasons = {
                "grounded_false_premise", "conflicting_sources", "no_ground_truth",
                "unverified_claim", "outside_authority",
            }
            if (left.reason_code in safety_reasons or right.reason_code in safety_reasons):
                return same_source and left.reason_code == right.reason_code
            return same_source
        return left.reason_code == right.reason_code or left.action in {"clarify", "reject"}
