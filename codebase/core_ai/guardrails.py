"""Declarative pre-LLM guardrails loaded from YAML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import yaml

from codebase.core_ai.normalization import TextNormalizer
from codebase.core_ai.retrieval import fold_text


@dataclass(frozen=True)
class GuardrailDecision:
    action: str
    source_ids: tuple[str, ...]
    subject: str
    reason_code: str
    missing_slot: str | None
    rule_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "source_ids": list(self.source_ids),
            "subject": self.subject,
            "reason_code": self.reason_code,
            "missing_slot": self.missing_slot,
        }


class GuardrailEngine:
    """Evaluate generic match operators; domain phrases remain in YAML."""

    def __init__(self, config_path: Path, *, normalizer: TextNormalizer | None = None) -> None:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        rules = payload.get("rules", [])
        if not isinstance(rules, list):
            raise ValueError("guardrails.yaml must contain a rules list")
        self.rules = sorted(rules, key=lambda rule: int(rule.get("priority", 0)), reverse=True)
        self.normalizer = normalizer

    @staticmethod
    def _contains(text: str, term: str) -> bool:
        needle = fold_text(term).strip()
        if not needle:
            return False
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", text))

    def _matches(self, text: str, match: dict[str, Any]) -> bool:
        any_terms = match.get("any_terms", [])
        if any_terms and not any(self._contains(text, term) for term in any_terms):
            return False

        all_terms = match.get("all_terms", [])
        if all_terms and not all(self._contains(text, term) for term in all_terms):
            return False

        none_terms = match.get("none_terms", [])
        if any(self._contains(text, term) for term in none_terms):
            return False

        for group in match.get("all_groups", []):
            if not any(self._contains(text, term) for term in group):
                return False

        regex_any = match.get("regex_any", [])
        if regex_any and not any(re.search(pattern, text) for pattern in regex_any):
            return False
        return True

    def evaluate(self, message: str) -> GuardrailDecision | None:
        normalized = self.normalizer.normalize(message) if self.normalizer else fold_text(message)
        for rule in self.rules:
            if not self._matches(normalized, rule.get("match", {})):
                continue
            decision = rule["decision"]
            return GuardrailDecision(
                action=str(decision["action"]),
                source_ids=tuple(map(str, decision.get("source_ids", []))),
                subject=str(decision.get("subject", "unknown")),
                reason_code=str(decision["reason_code"]),
                missing_slot=(
                    str(decision["missing_slot"])
                    if decision.get("missing_slot") is not None else None
                ),
                rule_id=str(rule["id"]),
            )
        return None
