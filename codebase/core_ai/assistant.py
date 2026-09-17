"""Grounded response router for the Discord assistant.

An LLM is used only to classify intent. This module writes every grounded fact
and citation from codebase/data/official_announcements.json, preventing the
model from inventing information when an official source is missing.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import unicodedata
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
OFFICIAL_SOURCES_PATH = PROJECT_ROOT / "codebase" / "data" / "official_announcements.json"
RAW_SOURCES: list[dict[str, Any]] = json.loads(OFFICIAL_SOURCES_PATH.read_text(encoding="utf-8"))
SYSTEM_PROMPT = (CONFIG_DIR / "system_prompt.md").read_text(encoding="utf-8")

# Search phrases are routing metadata, not new facts. Every returned fact still
# comes verbatim from the corresponding official announcement below.
SOURCE_ALIASES: dict[str, tuple[str, ...]] = {
    "ANN_01": (
        "onboarding", "ghép đội", "ghep doi", "tìm đồng đội", "tim dong doi",
        "thành lập team", "thanh lap team", "chung team",
        "khác lớp lab", "khac lop lab", "khác lớp", "khac lop",
    ),
    "ANN_02": (
        "đổi tên", "doi ten", "tên discord", "ten discord", "cú pháp", "cu phap",
        "điểm danh ws", "diem danh ws", "workshop",
    ),
    "ANN_03": ("lab 1", "lab01", "lab 01", "codelab"),
    "ANN_04": ("lab 2", "lab02", "lab 02", "cvat"),
    "ANN_05": ("daily standup", "standup", "daily"),
    "ANN_06": (
        "ticket", "giấy tờ", "giay to", "hỗ trợ", "ho tro", "phoenix",
        "tài khoản", "tai khoan", "nộp muộn", "nop muon", "gia hạn", "gia han",
    ),
    "ANN_07": (
        "điểm cộng onboarding", "diem cong onboarding", "điểm xp", "diem xp",
        "bảng xếp hạng", "bang xep hang", "leaderboard", "rank",
    ),
}

SOURCES: list[dict[str, Any]] = [
    {
        **source,
        "aliases": SOURCE_ALIASES.get(source["id"], ()),
        "facts": source.get("key_entities", {}),
        "quote": source["content"],
        "channel": source["source_channel"],
        "published_at": source["posted_at"],
        "source_type": "official_ground_truth_fixture",
        "verified": True,
        "url": None,
    }
    for source in RAW_SOURCES
]

GROUNDING_CONTEXT = json.dumps(
    [
        {
            "id": source["id"],
            "title": source["title"],
            "content": source["content"],
            "key_entities": source["key_entities"],
        }
        for source in RAW_SOURCES
    ],
    ensure_ascii=False,
)
# Low-latency model with generous quota for CP3 intent classification.
DEFAULT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_9ROUTER_MODEL = "cx/deepseek-chat"
LOGGER = logging.getLogger(__name__)
PROCESSING_PROVIDER: ContextVar[str] = ContextVar("processing_provider", default="local_rules")
INTENTS = (
    "greeting", "query_deadline", "query_submission_location",
    "query_late_policy", "query_submission_status", "query_attendance",
    "request_extension", "report_conflict", "unknown",
)

CLASSIFICATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": list(INTENTS),
        },
        "subject": {"type": "string"},
        "is_ambiguous": {"type": "boolean"},
        "needs_human": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["intent", "subject", "is_ambiguous", "needs_human", "reason"],
}

CLARIFICATION_OPTIONS = [
    {"label": "Lab 01 Codelab", "value": "Hạn nộp Lab 01 Codelab là khi nào?"},
    {"label": "Lab 02 CVAT", "value": "Hạn nộp Lab 02 CVAT là khi nào?"},
    {"label": "Ghép đội tự do", "value": "Hạn ghép đội tự do là khi nào?"},
]

# Phrases that mark user input as hearsay / unverified rumor.
# These MUST NOT trigger report_conflict — they are NOT an official source.
RUMOR_PHRASES = (
    "nghe bảo", "nghe bao", "hình như", "hinh nhu",
    "bạn bảo", "ban bao", "ai đó nói", "ai do noi",
    "có người nói", "co nguoi noi", "nghe nói", "nghe noi",
    "bạn em nói", "ban em noi", "mình nghe", "minh nghe",
)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFD", str(value).lower())
    return "".join(char for char in normalized if not unicodedata.combining(char)).replace("đ", "d")


def _has(text: str, *terms: str) -> bool:
    normalized = _fold(text)
    return any(_fold(term) in normalized for term in terms)


def _source_for(text: str) -> dict[str, Any] | None:
    normalized = _fold(text)
    winner: tuple[int, dict[str, Any]] | None = None
    for source in SOURCES:
        matches = [alias for alias in source["aliases"] if _fold(alias) in normalized]
        if matches:
            candidate = (max(map(len, matches)), source)
            if winner is None or candidate[0] > winner[0]:
                winner = candidate
    return winner[1] if winner else None


def _source_by_id(source_id: str) -> dict[str, Any]:
    return next(source for source in SOURCES if source["id"] == source_id)


def _citation(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "ground_truth_id": source["id"],
        "message_id": source["source_msg_id"],
        "channel": source["channel"],
        "quote": source["quote"],
        "url": source.get("url"),
        "source_type": source.get("source_type", "unknown"),
        "verified": bool(source.get("verified", False)),
        "published_at": source.get("published_at"),
    }


def _response(
    *, intent: str, status: str, confidence: float, reply: str,
    source: dict[str, Any] | None = None, interactive_type: str = "none",
    options: list[dict[str, str]] | None = None, need_ta: bool = False,
    reason: str | None = None,
) -> dict[str, Any]:
    """Build the shared CP2 response contract in one fixed shape."""
    return {
        "intent": intent,
        "status": status,
        "confidence_score": confidence,
        "reply_text": reply,
        "source_citation": _citation(source) if source else None,
        "interactive_elements": {"type": interactive_type, "options": options or []},
        "handoff_metadata": {"need_ta": need_ta, "reason": reason},
        "processing_metadata": {"intent_provider": PROCESSING_PROVIDER.get()},
    }


# ---------------------------------------------------------------------------
# Intent classification pipeline
# ---------------------------------------------------------------------------

def _guardrail_intent(text: str) -> str | None:
    """Deterministic decisions that must never depend on an LLM guess.

    RUMOR GUARD (Fix Prompt 8):
    Phrases like "nghe bảo", "hình như" indicate hearsay from a peer — NOT
    an official channel. They must never escalate to report_conflict; instead
    we route to query_deadline so the backend re-affirms the Ground Truth.
    """
    # Rumor / hearsay guard — re-route to deadline lookup, never conflict
    if _has(text, *RUMOR_PHRASES):
        return "query_deadline"
    if _has(text, "email") and _has(text, "discord"):
        return "report_conflict"
    if _has(text, "điểm danh", "diem danh"):
        return "query_attendance"
    if _has(text, "đã nộp", "da nop", "check xem", "check hộ", "trạng thái nộp", "trang thai nop"):
        return "query_submission_status"
    if _has(text, "gia hạn", "gia han", "nộp muộn", "nop muon"):
        if _has(text, "cho em", "cho tôi", "cho t", "xin", "giúp em", "giup em"):
            return "request_extension"
    return None


def _local_intent(text: str) -> str:
    """Conservative offline fallback used if Gemini is unavailable."""
    if guardrail := _guardrail_intent(text):
        return guardrail
    if _has(
        text, "gia hạn", "gia han", "nộp muộn", "nop muon", "muộn", "muon",
        "phạt", "phat", "trừ bao nhiêu", "tru bao nhieu", "trừ điểm", "tru diem",
    ):
        return "query_late_policy"
    if _has(text, "nộp ở đâu", "nop o dau", "cách nộp", "cach nop") or (_has(text, "nộp", "nop") and _has(text, "ở đâu", "o dau")):
        return "query_submission_location"
    if _has(text, "hạn", "han", "deadline", "due"):
        return "query_deadline"
    if _has(text, "xin chào", "chào", "hello") or re.search(r"\bhi\b", _fold(text)):
        return "greeting"
    return "unknown"


def _gemini_classification(message_text: str) -> dict[str, Any]:
    """Call Gemini's REST endpoint only for a structured classification."""
    # Google AI Studio examples commonly use either name; accept both locally.
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        LOGGER.warning("gemini_call_skipped reason=missing_api_key")
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY is not configured")

    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    call_id = uuid.uuid4().hex[:12]
    started_at = time.perf_counter()
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": (
            f"{SYSTEM_PROMPT}\n\n"
            "KHO GROUND TRUTH CHÍNH THỨC (chỉ dùng để nhận diện subject; "
            "backend sẽ tự lấy dữ kiện và citation):\n"
            f"{GROUNDING_CONTEXT}"
        )}]},
        "contents": [{"role": "user", "parts": [{"text": message_text}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": CLASSIFICATION_SCHEMA,
        },
    }
    request = Request(
        endpoint, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )
    LOGGER.info(
        "gemini_call_started call_id=%s model=%s timeout_seconds=25",
        call_id, model,
    )
    try:
        with urlopen(request, timeout=25) as http_response:
            status_code = getattr(http_response, "status", 200)
            body = json.load(http_response)
    except HTTPError as error:
        LOGGER.warning(
            "gemini_call_failed call_id=%s model=%s status_code=%s duration_ms=%d error=http_error",
            call_id, model, error.code, round((time.perf_counter() - started_at) * 1000),
        )
        raise RuntimeError(f"Gemini returned HTTP {error.code}") from error
    except URLError as error:
        LOGGER.warning(
            "gemini_call_failed call_id=%s model=%s status_code=unavailable duration_ms=%d error=connection_error",
            call_id, model, round((time.perf_counter() - started_at) * 1000),
        )
        raise RuntimeError("Gemini connection failed") from error
    except TimeoutError as error:
        LOGGER.warning(
            "gemini_call_failed call_id=%s model=%s status_code=timeout duration_ms=%d error=timeout",
            call_id, model, round((time.perf_counter() - started_at) * 1000),
        )
        raise RuntimeError("Gemini request timed out") from error
    except json.JSONDecodeError as error:
        LOGGER.warning(
            "gemini_call_failed call_id=%s model=%s status_code=%s duration_ms=%d error=invalid_http_json",
            call_id, model, status_code, round((time.perf_counter() - started_at) * 1000),
        )
        raise RuntimeError("Gemini returned an invalid HTTP JSON response") from error

    try:
        result = json.loads(body["candidates"][0]["content"]["parts"][0]["text"])
    except (IndexError, KeyError, TypeError, json.JSONDecodeError) as error:
        LOGGER.warning(
            "gemini_call_failed call_id=%s model=%s status_code=%s duration_ms=%d error=invalid_classification_json",
            call_id, model, status_code, round((time.perf_counter() - started_at) * 1000),
        )
        raise RuntimeError("Gemini returned no valid JSON classification") from error
    if not isinstance(result, dict) or not all(field in result for field in CLASSIFICATION_SCHEMA["required"]):
        LOGGER.warning(
            "gemini_call_failed call_id=%s model=%s status_code=%s duration_ms=%d error=contract_violation",
            call_id, model, status_code, round((time.perf_counter() - started_at) * 1000),
        )
        raise RuntimeError("Gemini classification violates the contract")
    if result["intent"] not in INTENTS:
        LOGGER.warning(
            "gemini_call_failed call_id=%s model=%s status_code=%s duration_ms=%d error=unsupported_intent",
            call_id, model, status_code, round((time.perf_counter() - started_at) * 1000),
        )
        raise RuntimeError("Gemini returned an unsupported intent")
    if not isinstance(result["subject"], str) or not isinstance(result["reason"], str):
        LOGGER.warning(
            "gemini_call_failed call_id=%s model=%s status_code=%s duration_ms=%d error=invalid_text_fields",
            call_id, model, status_code, round((time.perf_counter() - started_at) * 1000),
        )
        raise RuntimeError("Gemini returned invalid text fields")
    if not isinstance(result["is_ambiguous"], bool) or not isinstance(result["needs_human"], bool):
        LOGGER.warning(
            "gemini_call_failed call_id=%s model=%s status_code=%s duration_ms=%d error=invalid_boolean_fields",
            call_id, model, status_code, round((time.perf_counter() - started_at) * 1000),
        )
        raise RuntimeError("Gemini returned invalid boolean fields")
    LOGGER.info(
        "gemini_call_succeeded call_id=%s model=%s status_code=%s duration_ms=%d intent=%s",
        call_id, model, status_code, round((time.perf_counter() - started_at) * 1000), result["intent"],
    )
    return result


def _first_env(*names: str) -> str | None:
    return next((value for name in names if (value := os.getenv(name))), None)


def _9router_classification(message_text: str) -> dict[str, Any]:
    """Call a 9router/OpenAI-compatible chat-completions endpoint."""
    api_key = _first_env("NINEROUTER_API_KEY", "NINE_ROUTER_API_KEY", "OPENAI_API_KEY")
    base_url = _first_env("NINEROUTER_BASE_URL", "NINE_ROUTER_BASE_URL", "OPENAI_BASE_URL")
    if not api_key or not base_url:
        LOGGER.warning("9router_call_skipped reason=missing_api_key_or_base_url")
        raise RuntimeError("NINEROUTER_API_KEY and NINEROUTER_BASE_URL are required")

    model = _first_env("NINEROUTER_MODEL", "NINE_ROUTER_MODEL", "OPENAI_MODEL") or DEFAULT_9ROUTER_MODEL
    call_id = uuid.uuid4().hex[:12]
    started_at = time.perf_counter()
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    instructions = (
        f"{SYSTEM_PROMPT}\n\n"
        "KHO GROUND TRUTH CHÍNH THỨC (chỉ dùng để nhận diện subject; "
        "backend sẽ tự lấy dữ kiện và citation):\n"
        f"{GROUNDING_CONTEXT}\n\n"
        "Chỉ trả về một JSON object theo đúng schema đã yêu cầu, không dùng markdown."
    )
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": message_text},
        ],
    }
    request = Request(
        endpoint, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    LOGGER.info("9router_call_started call_id=%s model=%s timeout_seconds=25", call_id, model)
    try:
        with urlopen(request, timeout=25) as http_response:
            status_code = getattr(http_response, "status", 200)
            body = json.load(http_response)
    except HTTPError as error:
        LOGGER.warning(
            "9router_call_failed call_id=%s model=%s status_code=%s duration_ms=%d error=http_error",
            call_id, model, error.code, round((time.perf_counter() - started_at) * 1000),
        )
        raise RuntimeError(f"9router returned HTTP {error.code}") from error
    except (URLError, TimeoutError) as error:
        LOGGER.warning(
            "9router_call_failed call_id=%s model=%s status_code=unavailable duration_ms=%d error=connection_error",
            call_id, model, round((time.perf_counter() - started_at) * 1000),
        )
        raise RuntimeError("9router connection failed") from error
    except json.JSONDecodeError as error:
        LOGGER.warning(
            "9router_call_failed call_id=%s model=%s status_code=%s duration_ms=%d error=invalid_http_json",
            call_id, model, status_code, round((time.perf_counter() - started_at) * 1000),
        )
        raise RuntimeError("9router returned an invalid HTTP JSON response") from error

    try:
        content = body["choices"][0]["message"]["content"]
        result = json.loads(content)
    except (IndexError, KeyError, TypeError, json.JSONDecodeError) as error:
        LOGGER.warning(
            "9router_call_failed call_id=%s model=%s status_code=%s duration_ms=%d error=invalid_classification_json",
            call_id, model, status_code, round((time.perf_counter() - started_at) * 1000),
        )
        raise RuntimeError("9router returned no valid JSON classification") from error
    if not isinstance(result, dict) or not all(field in result for field in CLASSIFICATION_SCHEMA["required"]):
        raise RuntimeError("9router classification violates the contract")
    if result["intent"] not in INTENTS or not isinstance(result["subject"], str) or not isinstance(result["reason"], str):
        raise RuntimeError("9router classification violates the contract")
    if not isinstance(result["is_ambiguous"], bool) or not isinstance(result["needs_human"], bool):
        raise RuntimeError("9router classification violates the contract")
    LOGGER.info(
        "9router_call_succeeded call_id=%s model=%s status_code=%s duration_ms=%d intent=%s",
        call_id, model, status_code, round((time.perf_counter() - started_at) * 1000), result["intent"],
    )
    return result


def _classify(text: str, use_gemini: bool) -> tuple[str, str]:
    if guardrail := _guardrail_intent(text):
        LOGGER.info("Intent enforced by local guardrail: %s", guardrail)
        return guardrail, "local_guardrail"
    if use_gemini:
        try:
            provider = os.getenv("LLM_PROVIDER", "gemini").lower()
            if provider in {"9router", "openai_compatible"}:
                intent = str(_9router_classification(text).get("intent", "unknown"))
            elif provider == "gemini":
                intent = str(_gemini_classification(text).get("intent", "unknown"))
            else:
                raise RuntimeError(f"Unsupported LLM_PROVIDER: {provider}")
            LOGGER.info("intent_routed provider=%s intent=%s", provider, intent)
            return intent, provider
        except RuntimeError as error:
            # Do not log prompt text or secrets; only disclose the safe fallback.
            LOGGER.warning("intent_fallback provider=local_rules reason=%s", error)
    return _local_intent(text), "local_rules"


def _grounded_intent(source: dict[str, Any], text: str) -> str:
    """Return the product-facing intent after a source has been selected."""
    source_id = source["id"]
    if source_id == "ANN_01":
        if _has(text, "khác lớp", "khac lop", "chung team"):
            return "query_cross_class_team_policy"
        if _has(text, "không đủ", "khong du", "giải tán", "giai tan"):
            return "query_team_formation_policy"
        return "query_deadline_team_formation"
    if source_id == "ANN_02":
        return "query_attendance_workshop" if _has(text, "điểm danh", "diem danh", "workshop", " ws") else "query_naming_convention"
    if source_id == "ANN_03":
        return "query_deadline_lab1"
    if source_id == "ANN_04":
        if _has(text, "bỏ qua", "bo qua", "ignore previous", "chỉ thị trước", "chi thi truoc"):
            return "adversarial_prompt_injection"
        return "query_deadline_lab2"
    if source_id == "ANN_05":
        if _has(text, "báo hết hạn", "bao het han", "bot bảo", "bot bao"):
            return "resolve_daily_standup_conflict"
        return "query_daily_standup_deadline"
    if source_id == "ANN_06":
        return "troubleshoot_phoenix_login" if _has(text, "phoenix", "đăng nhập", "dang nhap") else "query_support_channel"
    if source_id == "ANN_07":
        return "query_onboarding_points_vs_xp" if _has(text, "onboarding") else "query_xp_leaderboard_command"
    return "unknown"


# ---------------------------------------------------------------------------
# Layer 1 — Pre-dispatch predicates & handlers
# (text-pattern based, evaluated before intent classification matters)
# ---------------------------------------------------------------------------

def _is_adversarial(text: str) -> bool:
    return _has(text, "tôi là admin", "toi la admin", "đóng vai", "dong vai",
                "trưởng ban tổ chức", "truong ban to chuc")


def _handle_adversarial(text: str) -> dict[str, Any]:
    adversarial_intent = (
        "adversarial_fake_admin"
        if _has(text, "tôi là admin", "toi la admin")
        else "adversarial_roleplay_jailbreak"
    )
    return _response(
        intent=adversarial_intent, status="rejected", confidence=0.99,
        reply="Mình không thể nhận vai BTC hoặc thay đổi điểm danh, kết quả học tập hay deadline. "
              "Mình chỉ tra cứu thông tin đã có trong thông báo chính thức.",
        need_ta=True, reason="outside_authority",
    )


def _is_conflict(text: str) -> bool:
    """True only when BOTH sides of a conflict are official channels.

    IMPORTANT: Hearsay ('nghe bảo', 'hình như') is NOT an official channel.
    RUMOR_PHRASES are already intercepted by _guardrail_intent() → query_deadline,
    so any rumor-bearing message never reaches this predicate.
    """
    return _has(text, "email") and _has(text, "discord")


def _handle_conflict(text: str) -> dict[str, Any]:
    conflict_source = _source_for(text)
    return _response(
        intent="resolve_deadline_conflict", status="ta_handoff", confidence=0.95,
        reply="⚠️ Mình ghi nhận có mâu thuẫn giữa email và thông báo Discord chính thức. "
              "Bạn nên nộp theo mốc sớm hơn nếu còn kịp; mình sẽ chuyển TA xác minh thông báo chính thức.",
        source=conflict_source,
        interactive_type="button_handoff",
        options=[{"label": "🔴 Chuyển cho TA hỗ trợ", "action": "trigger_ta_handoff"}],
        need_ta=True, reason="conflicting_official_sources",
    )


def _is_daily_conflict(text: str) -> bool:
    return _has(text, "daily standup", "standup") and _has(
        text, "báo hết hạn", "bao het han", "bot bảo", "bot bao"
    )


def _handle_daily_conflict(text: str) -> dict[str, Any]:
    source = _source_by_id("ANN_05")
    return _response(
        intent="resolve_daily_standup_conflict", status="ta_handoff", confidence=0.98,
        reply=source["content"] + " Nếu hệ thống hiển thị khác quy định này, mình sẽ chuyển TA kiểm tra.",
        source=source,
        interactive_type="button_handoff",
        options=[{"label": "🔴 Chuyển cho TA hỗ trợ", "action": "trigger_ta_handoff"}],
        need_ta=True, reason="conflicting_sources",
    )


def _is_event_location(text: str) -> bool:
    return _has(text, "lịch thi", "lich thi") and _has(text, "phòng", "phong")


def _handle_event_location(text: str) -> dict[str, Any]:
    return _response(
        intent="query_event_location_unannounced", status="ta_handoff", confidence=0.98,
        reply="Kho thông báo chính thức chưa có địa điểm phòng thi Hackathon. "
              "Mình không suy đoán; bạn hãy theo dõi #thong-bao-chung hoặc chuyển TA hỗ trợ.",
        interactive_type="button_handoff",
        options=[{"label": "🔴 Chuyển cho TA hỗ trợ", "action": "trigger_ta_handoff"}],
        need_ta=True, reason="no_official_ground_truth",
    )


def _is_room_booking(text: str) -> bool:
    return _has(text, "book phòng", "book phong", "mượn phòng", "muon phong",
                "phòng riêng", "phong rieng")


def _handle_room_booking(text: str) -> dict[str, Any]:
    return _response(
        intent="query_offline_room_booking", status="ta_handoff", confidence=0.98,
        reply="Kho thông báo chính thức chưa có quy định về việc đặt phòng họp nhóm. "
              "Mình không tự phỏng đoán và sẽ chuyển TA xác nhận.",
        interactive_type="button_handoff",
        options=[{"label": "🔴 Chuyển cho TA hỗ trợ", "action": "trigger_ta_handoff"}],
        need_ta=True, reason="no_official_ground_truth",
    )


def _is_delete_submission(text: str) -> bool:
    return _has(text, "xoá", "xóa", "xoa", "delete") and _has(text, "bài nộp", "bai nop", "vlearn")


def _handle_delete_submission(text: str) -> dict[str, Any]:
    source = _source_by_id("ANN_04")
    return _response(
        intent="request_delete_submission", status="rejected", confidence=0.99,
        reply="Mình không có quyền xóa hoặc thay đổi bài nộp trên VLearn. "
              "Nếu không thể tự nộp lại khi còn hạn, bạn hãy dùng /ticket create tại #ticket-support để TA xử lý.",
        source=source,
        interactive_type="button_ticket",
        options=[{"label": "Mở hướng dẫn /ticket create", "action": "show_ticket_help"}],
        need_ta=True, reason="outside_authority",
    )


def _is_phoenix_issue(text: str) -> bool:
    return _has(text, "phoenix") and _has(
        text, "chưa vào", "chua vao", "không vào", "khong vao", "lỗi", "loi"
    )


def _handle_phoenix_issue(text: str) -> dict[str, Any]:
    source = _source_by_id("ANN_06")
    return _response(
        intent="troubleshoot_phoenix_login", status="rejected", confidence=0.99,
        reply="Mình không thể can thiệp tài khoản Phoenix. " + source["content"],
        source=source,
        interactive_type="button_ticket",
        options=[{"label": "Mở hướng dẫn /ticket create", "action": "show_ticket_help"}],
        need_ta=True, reason="outside_authority",
    )


# Ordered list of (predicate, handler) pairs evaluated top-to-bottom.
# The first matching predicate short-circuits the rest.
_PRE_DISPATCH: list[tuple[Callable[[str], bool], Callable[[str], dict[str, Any]]]] = [
    (_is_adversarial,       _handle_adversarial),
    (_is_daily_conflict,    _handle_daily_conflict),   # before _is_conflict to avoid ANN_05 false positive
    (_is_conflict,          _handle_conflict),
    (_is_event_location,    _handle_event_location),
    (_is_room_booking,      _handle_room_booking),
    (_is_delete_submission, _handle_delete_submission),
    (_is_phoenix_issue,     _handle_phoenix_issue),
]


# ---------------------------------------------------------------------------
# Layer 3 — Intent dispatch handlers
# ---------------------------------------------------------------------------

def _handle_attendance(text: str) -> dict[str, Any]:
    attendance_source = _source_by_id("ANN_02")
    if _has(text, "check", "sửa", "sua", "ghi nhận", "ghi nhan", "hộ em", "ho em"):
        return _response(
            intent="request_modify_attendance", status="rejected", confidence=0.99,
            reply="Mình không có quyền kiểm tra hoặc sửa dữ liệu điểm danh. "
                  "Bạn hãy liên hệ Lab Coach của buổi học hoặc mở ticket để được hỗ trợ.",
            source=attendance_source,
            interactive_type="button_ticket",
            options=[{"label": "Mở hướng dẫn /ticket create", "action": "show_ticket_help"}],
            need_ta=True, reason="outside_authority",
        )
    return _response(
        intent="query_attendance_workshop", status="clarification_needed", confidence=0.95,
        reply=attendance_source["content"] + " Bạn đang hỏi điểm danh workshop nào?",
        source=attendance_source,
        interactive_type="chips",
        options=[{"label": "Liên hệ Lab Coach", "value": "Tôi cần liên hệ Lab Coach về điểm danh"}],
    )


def _handle_submission_status(text: str) -> dict[str, Any]:
    """Partial Fulfillment fix (Prompt 10 — Multi-Intent Dropout).

    When the user asks BOTH about a deadline AND submission status in one message,
    the previous implementation silently dropped the deadline answer and only
    returned the out-of-scope rejection. Now we:
      1. Check whether the message also contains a deadline query.
      2. If yes, prepend the grounded deadline answer before the rejection notice.
         Prioritise the lab-specific source (ANN_03/ANN_04) over generic sources
         so "lab 2 + VLearn" does not accidentally resolve to ANN_06.
      3. Return status='partial_rejected' so the eval suite can assert both parts.
    """
    has_deadline_query = _has(
        text, "hạn", "han", "deadline", "khi nào", "khi nao", "bao giờ", "bao gio",
        "mấy giờ", "may gio", "ngày nào", "ngay nao",
    )

    deadline_source: dict[str, Any] | None = None
    if has_deadline_query:
        # Prefer a lab-specific source when the message names a specific lab,
        # to avoid ANN_06 (support channel) winning via "tai khoan"/"vlearn" aliases.
        if _has(text, "lab 2", "lab02", "lab 02", "cvat"):
            deadline_source = _source_by_id("ANN_04")
        elif _has(text, "lab 1", "lab01", "lab 01", "codelab"):
            deadline_source = _source_by_id("ANN_03")
        else:
            deadline_source = _source_for(text)

    prefix = (deadline_source["content"] + "\n\n") if deadline_source else ""
    status = "partial_rejected" if prefix else "rejected"

    return _response(
        intent="check_personal_submission_status", status=status, confidence=0.99,
        reply=(
            prefix
            + "Mình không có quyền xem trạng thái bài nộp cá nhân. "
              "Bạn hãy tự kiểm tra trên VLearn; nếu dữ liệu có vấn đề, "
              "dùng /ticket create tại #ticket-support."
        ),
        source=deadline_source,
        interactive_type="button_ticket",
        options=[{"label": "Mở hướng dẫn /ticket create", "action": "show_ticket_help"}],
        need_ta=True, reason="outside_authority",
    )


def _handle_extension(text: str) -> dict[str, Any]:
    support_source = _source_by_id("ANN_06")
    return _response(
        intent="request_deadline_extension", status="rejected", confidence=0.99,
        reply="Mình không có thẩm quyền duyệt gia hạn. " + support_source["content"],
        source=support_source,
        interactive_type="button_ticket",
        options=[{"label": "Mở hướng dẫn /ticket create", "action": "show_ticket_help"}],
        need_ta=True, reason="outside_authority",
    )


def _handle_greeting(text: str) -> dict[str, Any]:
    return _response(
        intent="greeting", status="answered", confidence=0.98,
        reply="Chào bạn! Mình hỗ trợ tra cứu hạn nộp, cách nộp bài và thủ tục K4 từ thông báo chính thức.",
    )


def _handle_late_policy(text: str) -> dict[str, Any]:
    if _has(text, "lab", "trừ bao nhiêu", "tru bao nhieu", "phạt", "phat"):
        support_source = _source_by_id("ANN_06")
        return _response(
            intent="query_late_submission_penalty", status="answered", confidence=0.98,
            reply="Kho thông báo hiện chưa có barem trừ điểm cụ thể cho Lab nộp muộn. " + support_source["content"],
            source=support_source,
            interactive_type="button_ticket",
            options=[{"label": "Mở hướng dẫn /ticket create", "action": "show_ticket_help"}],
            need_ta=True, reason="missing_specific_policy",
        )
    return _handle_source_lookup(text, "query_late_policy")


def _handle_source_lookup(text: str, intent: str) -> dict[str, Any]:
    """Attempt to resolve the query against the Ground Truth store."""
    # Lab 4 guard — no official announcement exists yet
    if re.search(r"\blab\s*0?4\b", _fold(text)):
        return _response(
            intent="query_deadline_unannounced", status="ta_handoff", confidence=0.98,
            reply="Hiện BTC chưa công bố thông tin chính thức cho Lab 4. "
                  "Để tránh suy đoán sai, mình không tự đưa ra deadline.",
            interactive_type="button_handoff",
            options=[{"label": "🔴 Chuyển cho TA hỗ trợ", "action": "trigger_ta_handoff"}],
            need_ta=True, reason="no_official_ground_truth",
        )

    source = _source_for(text)

    # Ambiguous submission location
    if source is None and _has(
        text, "link nộp", "link nop", "nộp bài ở đâu", "nop bai o dau", "nộp ở đâu", "nop o dau"
    ):
        clarification_intent = "query_submission_link_ambiguous" if _has(text, "link") else "query_submission_place_ambiguous"
        return _response(
            intent=clarification_intent, status="clarification_needed", confidence=0.98,
            reply="Bạn cần link nộp Lab 01, Lab 02 hay Daily Standup? "
                  "Hãy chọn nội dung để mình đối chiếu đúng thông báo.",
            interactive_type="chips",
            options=[
                {"label": "Lab 01 Codelab", "value": "Nộp Lab 01 Codelab ở đâu?"},
                {"label": "Lab 02 CVAT", "value": "Nộp Lab 02 CVAT ở đâu?"},
                {"label": "Daily Standup", "value": "Nộp Daily Standup ở đâu?"},
            ],
        )

    # Ambiguous deadline / location (no source matched, intent is generic)
    if source is None and intent in {"query_deadline", "query_submission_location"}:
        clarification_intent = (
            "query_submission_place_ambiguous"
            if intent == "query_submission_location"
            else "query_deadline_ambiguous"
        )
        return _response(
            intent=clarification_intent, status="clarification_needed", confidence=0.95,
            reply="Bạn đang cần tra cứu nội dung nào? "
                  "Hãy chọn nhanh bên dưới để mình đối chiếu thông báo chính thức.",
            interactive_type="chips",
            options=CLARIFICATION_OPTIONS,
        )

    # Source found — return grounded answer
    if source:
        grounded_intent = _grounded_intent(source, text)
        reply = source["content"]
        if grounded_intent == "query_cross_class_team_policy":
            reply = (
                "Thông báo hiện chỉ xác nhận quy trình và hạn ghép đội trên Phoenix; "
                "chưa nêu rõ việc ghép team khác lớp. " + reply
            )
        elif grounded_intent == "query_onboarding_points_vs_xp":
            reply = (
                "Thông báo hiện chỉ xác nhận cách tra cứu XP, "
                "chưa có căn cứ để kết luận điểm onboarding có quy đổi sang XP hay không. " + reply
            )
        return _response(
            intent=grounded_intent, status="answered", confidence=0.99,
            reply=reply, source=source,
        )

    return _handle_unknown(text)


def _handle_unknown(text: str) -> dict[str, Any]:
    return _response(
        intent="unknown", status="ta_handoff", confidence=0.7,
        reply="Mình chưa có căn cứ chính thức để trả lời câu này. Bạn có muốn chuyển TA hỗ trợ không?",
        interactive_type="button_handoff",
        options=[{"label": "🔴 Chuyển cho TA hỗ trợ", "action": "trigger_ta_handoff"}],
        need_ta=True, reason="unsupported_or_no_ground_truth",
    )


# Intent → handler mapping.
# Intents not listed here fall through to _handle_source_lookup() which
# attempts a Ground Truth source match before finally calling _handle_unknown().
# NOTE: "unknown" is intentionally NOT listed here — it must fall through to
# _handle_source_lookup() so that queries like "Ghep doi khac lop" (classified
# as "unknown" by local_rules) can still be resolved via alias matching.
INTENT_HANDLERS: dict[str, Callable[[str], dict[str, Any]]] = {
    "greeting":                _handle_greeting,
    "query_attendance":        _handle_attendance,
    "query_submission_status": _handle_submission_status,
    "request_extension":       _handle_extension,
    "query_late_policy":       _handle_late_policy,
    "report_conflict":         _handle_conflict,       # LLM-classified conflict (not pre-dispatch)
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def answer(request: dict[str, Any], *, use_gemini: bool = True) -> dict[str, Any]:
    """Return a safe CP2 contract object for an API/UI request.

    Processing layers
    -----------------
    0. Empty-input guard.
    1. Pre-dispatch guards — text-pattern checks that override intent (adversarial,
       daily standup conflict, official-channel conflict, room booking, etc.).
    2. Intent classification — guardrail → LLM → local keyword fallback.
    3. Intent dispatch table — maps classified intent to a dedicated handler.
       Intents not in the table fall through to source-lookup / unknown.
    """
    PROCESSING_PROVIDER.set("local_rules")
    text = str(request.get("message_text", "")).strip()

    # Layer 0 — empty input
    if not text:
        return _response(
            intent="unknown", status="clarification_needed", confidence=1,
            reply="Bạn hãy nhập câu hỏi về hạn nộp, cách nộp bài hoặc thủ tục K4 nhé.",
        )

    # Layer 1 — pre-dispatch text-pattern guards (short-circuit on first match)
    for predicate, handler in _PRE_DISPATCH:
        if predicate(text):
            return handler(text)

    # Layer 2 — classify intent
    intent, provider = _classify(text, use_gemini)
    PROCESSING_PROVIDER.set(provider)

    # Layer 3 — intent dispatch
    handler_fn = INTENT_HANDLERS.get(intent)
    if handler_fn:
        return handler_fn(text)

    # Layer 3 fallback — source lookup → clarification → unknown
    return _handle_source_lookup(text, intent)
