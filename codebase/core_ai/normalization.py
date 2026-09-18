"""Data-driven normalization for Vietnamese learner messages.

The canonicalizer is deliberately shared by guardrails, retrieval and routing
so a shorthand is not recognised in one layer and lost in another. It only
normalizes common language forms declared in YAML; it never supplies facts or
chooses an answer.
"""

from __future__ import annotations

from pathlib import Path
import re
import unicodedata

import yaml


def fold_text(value: str) -> str:
    """Return a lower-case, accent-insensitive representation."""
    normalized = unicodedata.normalize("NFD", str(value).lower())
    return "".join(char for char in normalized if not unicodedata.combining(char)).replace("đ", "d")


class TextNormalizer:
    """Apply reusable, boundary-safe canonical aliases from a YAML file."""

    def __init__(self, config_path: Path | None = None) -> None:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path else {}
        aliases = (payload or {}).get("aliases", [])
        replacements: list[tuple[str, str]] = []
        for alias in aliases:
            if not isinstance(alias, dict) or not alias.get("canonical"):
                continue
            canonical = fold_text(str(alias["canonical"])).strip()
            for variant in alias.get("variants", []):
                normalized_variant = fold_text(str(variant)).strip()
                if normalized_variant and normalized_variant != canonical:
                    replacements.append((normalized_variant, canonical))
        # Longer phrases first prevents a short alias from consuming a longer one.
        self.replacements = sorted(replacements, key=lambda item: len(item[0]), reverse=True)

    def normalize(self, value: str) -> str:
        text = fold_text(value)
        for variant, canonical in self.replacements:
            text = re.sub(
                rf"(?<![a-z0-9]){re.escape(variant)}(?![a-z0-9])",
                canonical,
                text,
            )
        return text
