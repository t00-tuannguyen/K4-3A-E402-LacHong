"""Six-stage grounded decision pipeline for the Discord assistant.

Pipeline:
    YAML guardrails -> hybrid retrieval -> structured LLM decision ->
    YAML policy -> grounded composition/verification -> confidence.

The LLM never writes citations and cannot select a source outside retrieval's
top-k set. Every date, time and URL in a grounded reply is verified against
the selected official announcements before the API response is returned.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid

from codebase.core_ai.decision import Decision, DecisionEngine, decision_schema
from codebase.core_ai.guardrails import GuardrailEngine
from codebase.core_ai.normalization import TextNormalizer
from codebase.core_ai.policy import PolicyEngine
from codebase.core_ai.retrieval import HybridRetriever, RetrievalResult


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
OFFICIAL_SOURCES_PATH = PROJECT_ROOT / "codebase" / "data" / "official_announcements.json"
RAW_SOURCES: list[dict[str, Any]] = json.loads(OFFICIAL_SOURCES_PATH.read_text(encoding="utf-8"))
SOURCES: list[dict[str, Any]] = [
    {
        **source,
        "source_type": source.get("source_type", "official_ground_truth_fixture"),
        "verified": bool(source.get("verified", True)),
        "url": source.get("url"),
    }
    for source in RAW_SOURCES
]
SOURCE_BY_ID = {str(source["id"]): source for source in SOURCES}
SYSTEM_PROMPT = (CONFIG_DIR / "system_prompt.md").read_text(encoding="utf-8")

DEFAULT_MODEL = "gemini-3.5-flash-lite"
LOGGER = logging.getLogger(__name__)

NORMALIZER = TextNormalizer(CONFIG_DIR / "language_normalization.yaml")
RETRIEVER = HybridRetriever(SOURCES, normalizer=NORMALIZER)
DECISION_ENGINE = DecisionEngine(CONFIG_DIR / "decision_rules.yaml", normalizer=NORMALIZER)
GUARDRAIL_ENGINE = GuardrailEngine(CONFIG_DIR / "guardrails.yaml", normalizer=NORMALIZER)
POLICY_ENGINE = PolicyEngine(CONFIG_DIR / "policies.yaml", DECISION_ENGINE)


class SourceSelectionError(RuntimeError):
    """Raised when a model attempts to cite outside the retrieved top-k."""


def _first_env(*names: str) -> str | None:
    return next((value for name in names if (value := os.getenv(name))), None)


def _retrieval_for(message_text: str) -> list[RetrievalResult]:
    return RETRIEVER.search(message_text, top_k=DECISION_ENGINE.top_k)


def _decision_instructions(retrieval: list[RetrievalResult]) -> str:
    records = [result.prompt_record() for result in retrieval]
    allowed_ids = [result.source_id for result in retrieval]
    return (
        f"{SYSTEM_PROMPT}\n\n"
        "TOP-K OFFICIAL SOURCES (the only source_ids you may select):\n"
        f"{json.dumps(records, ensure_ascii=False)}\n\n"
        f"ALLOWED_SOURCE_IDS={json.dumps(allowed_ids, ensure_ascii=False)}\n"
        "Return only the structured decision JSON. Never write the final answer."
    )


def _validate_source_selection(
    decision: Decision,
    retrieval: list[RetrievalResult],
) -> Decision:
    allowed = {result.source_id for result in retrieval}
    selected = set(decision.source_ids)
    if not selected.issubset(allowed):
        raise SourceSelectionError(
            f"model selected source outside top-k: {sorted(selected - allowed)}"
        )
    if decision.action == "answer" and decision.reason_code.startswith("grounded") and not selected:
        raise SourceSelectionError("grounded answer requires a retrieved source")
    return decision


def _gemini_classification(
    message_text: str,
    retrieval: list[RetrievalResult] | None = None,
) -> dict[str, Any]:
    """Ask Gemini for a structured decision constrained to retrieved sources."""
    retrieval = retrieval if retrieval is not None else _retrieval_for(message_text)
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        LOGGER.warning("gemini_call_skipped reason=missing_api_key")
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY is not configured")

    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    call_id = uuid.uuid4().hex[:12]
    started_at = time.perf_counter()
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": _decision_instructions(retrieval)}]},
        "contents": [{"role": "user", "parts": [{"text": message_text}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": decision_schema([result.source_id for result in retrieval]),
        },
    }
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )
    LOGGER.info(
        "gemini_call_started call_id=%s model=%s top_k=%d timeout_seconds=25",
        call_id,
        model,
        len(retrieval),
    )
    try:
        with urlopen(request, timeout=25) as http_response:
            status_code = getattr(http_response, "status", 200)
            body = json.load(http_response)
    except HTTPError as error:
        LOGGER.warning(
            "gemini_call_failed call_id=%s model=%s status_code=%s duration_ms=%d error=http_error",
            call_id,
            model,
            error.code,
            round((time.perf_counter() - started_at) * 1000),
        )
        raise RuntimeError(f"Gemini returned HTTP {error.code}") from error
    except URLError as error:
        LOGGER.warning(
            "gemini_call_failed call_id=%s model=%s status_code=unavailable duration_ms=%d error=connection_error",
            call_id,
            model,
            round((time.perf_counter() - started_at) * 1000),
        )
        raise RuntimeError("Gemini connection failed") from error
    except TimeoutError as error:
        LOGGER.warning(
            "gemini_call_failed call_id=%s model=%s status_code=timeout duration_ms=%d error=timeout",
            call_id,
            model,
            round((time.perf_counter() - started_at) * 1000),
        )
        raise RuntimeError("Gemini request timed out") from error
    except json.JSONDecodeError as error:
        LOGGER.warning(
            "gemini_call_failed call_id=%s model=%s status_code=%s duration_ms=%d error=invalid_http_json",
            call_id,
            model,
            status_code,
            round((time.perf_counter() - started_at) * 1000),
        )
        raise RuntimeError("Gemini returned invalid HTTP JSON") from error

    try:
        raw_decision = json.loads(body["candidates"][0]["content"]["parts"][0]["text"])
        decision = Decision.from_mapping(raw_decision)
        _validate_source_selection(decision, retrieval)
    except SourceSelectionError:
        raise
    except (IndexError, KeyError, TypeError, json.JSONDecodeError, ValueError) as error:
        LOGGER.warning(
            "gemini_call_failed call_id=%s model=%s status_code=%s duration_ms=%d error=invalid_decision",
            call_id,
            model,
            status_code,
            round((time.perf_counter() - started_at) * 1000),
        )
        raise RuntimeError("Gemini returned no valid structured decision") from error

    LOGGER.info(
        "gemini_call_succeeded call_id=%s model=%s status_code=%s duration_ms=%d action=%s reason_code=%s",
        call_id,
        model,
        status_code,
        round((time.perf_counter() - started_at) * 1000),
        decision.action,
        decision.reason_code,
    )
    return decision.as_dict()


def _selected_retrieval_confidence(
    decision: Decision,
    retrieval: list[RetrievalResult],
) -> float:
    scores = [item.score for item in retrieval if item.source_id in decision.source_ids]
    return max(scores, default=0.0)


def _confidence(
    decision: Decision,
    retrieval: list[RetrievalResult],
    *,
    provider: str,
    agreement: bool | None,
    authoritative_policy: bool = False,
) -> float:
    if provider == "local_guardrail":
        return 0.99
    if agreement is False and not authoritative_policy:
        return 0.45
    retrieval_score = _selected_retrieval_confidence(decision, retrieval)
    if authoritative_policy:
        base = 0.82
    else:
        base = 0.62 if provider == "local_rules" else 0.72 + (0.10 if agreement else 0.0)
    if decision.action in {"clarify", "reject"} and not decision.source_ids:
        base = max(base, 0.90)
    return min(0.99, base + 0.25 * retrieval_score)


def _llm_decision(
    message: str,
    retrieval: list[RetrievalResult],
) -> tuple[Decision, str]:
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider == "gemini":
        payload = _gemini_classification(message, retrieval)
    else:
        raise RuntimeError(f"Unsupported LLM_PROVIDER: {provider}")
    decision = Decision.from_mapping(payload)
    _validate_source_selection(decision, retrieval)
    LOGGER.info(
        "intent_routed provider=%s action=%s reason_code=%s",
        provider,
        decision.action,
        decision.reason_code,
    )
    return decision, provider


def answer(request: dict[str, Any], *, use_gemini: bool = True) -> dict[str, Any]:
    """Run the six-stage pipeline and return the stable frontend contract."""
    message = str(request.get("message_text", "")).strip()
    if not message:
        decision = Decision("clarify", (), "unknown", "missing_subject", "question")
        return POLICY_ENGINE.apply(
            decision,
            message=message,
            source_by_id=SOURCE_BY_ID,
            confidence=1.0,
            provider="local_validation",
            retrieval=[],
            rule_agreement=None,
        )

    guardrail = GUARDRAIL_ENGINE.evaluate(message)
    if guardrail:
        decision = Decision.from_mapping(guardrail.as_dict())
        LOGGER.info("guardrail_matched rule_id=%s action=%s", guardrail.rule_id, decision.action)
        return POLICY_ENGINE.apply(
            decision,
            message=message,
            source_by_id=SOURCE_BY_ID,
            confidence=0.99,
            provider="local_guardrail",
            retrieval=[],
            rule_agreement=True,
            guardrail_rule=guardrail.rule_id,
        )

    retrieval = _retrieval_for(message)
    local_decision = DECISION_ENGINE.local_decision(message, retrieval)
    decision = local_decision
    provider = "local_rules"
    agreement: bool | None = None
    authoritative_policy = False

    if use_gemini:
        configured_provider = os.getenv("LLM_PROVIDER", "gemini").lower()
        try:
            model_decision, provider = _llm_decision(message, retrieval)
            agreement = DECISION_ENGINE.decisions_agree(local_decision, model_decision)
            if DECISION_ENGINE.is_authoritative(local_decision):
                # A declarative policy backed by explicit source coverage or a
                # safety rule must not be downgraded to a generic question by
                # an LLM disagreement.  The outcome is already safe: it is a
                # targeted clarification, handoff, or documented absence.
                authoritative_policy = True
                if not agreement:
                    LOGGER.warning(
                        "policy_preserved provider=%s local_reason=%s model_action=%s",
                        provider,
                        local_decision.reason_code,
                        model_decision.action,
                    )
                decision = local_decision
            elif agreement:
                # The model is a semantic vote; canonical subject/missing-slot
                # values still come from the declarative local policy. This
                # prevents harmless wording differences from selecting a
                # missing policy template or malformed UI options.
                decision = local_decision
            else:
                LOGGER.warning(
                    "decision_disagreement provider=%s local_action=%s model_action=%s",
                    provider,
                    local_decision.action,
                    model_decision.action,
                )
                decision = Decision("clarify", (), "unknown", "decision_disagreement", "question")
        except SourceSelectionError as error:
            provider = f"{configured_provider}_guarded"
            LOGGER.warning("decision_rejected provider=%s reason=%s", provider, error)
            decision = Decision("handoff", (), "unknown", "invalid_source_selection")
            agreement = False
        except RuntimeError as error:
            LOGGER.warning("intent_fallback provider=local_rules reason=%s", error)
            provider = "local_rules"
            decision = local_decision

    confidence = _confidence(
        decision,
        retrieval,
        provider=provider,
        agreement=agreement,
        authoritative_policy=authoritative_policy,
    )
    return POLICY_ENGINE.apply(
        decision,
        message=message,
        source_by_id=SOURCE_BY_ID,
        confidence=confidence,
        provider=provider,
        retrieval=retrieval,
        rule_agreement=agreement,
    )
