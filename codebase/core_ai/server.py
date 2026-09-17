"""FastAPI adapter for the Core AI service.

Run from the project root:
    python -m uvicorn codebase.core_ai.server:app --reload
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from codebase.core_ai.assistant import DEFAULT_MODEL, answer


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def _configure_logging() -> None:
    """Make Core AI call logs visible without changing Uvicorn's own logging."""
    level_name = os.getenv("CORE_AI_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logger = logging.getLogger("codebase.core_ai")
    logger.setLevel(level)
    logger.propagate = False
    if not any(getattr(handler, "_core_ai_handler", False) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler._core_ai_handler = True  # type: ignore[attr-defined]
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        ))
        logger.addHandler(handler)


_configure_logging()

app = FastAPI(title="LacHong Core AI", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # The CP3 UI is a local static HTML file.
    allow_credentials=False,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


class AssistRequest(BaseModel):
    user_id: str | None = None
    channel_id: str | None = None
    message_text: str = Field(max_length=10_000)
    timestamp: str | None = None


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "lac-hong-core-ai",
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
        "model": os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
    }


@app.post("/api/assist")
def assist(request: AssistRequest) -> dict[str, Any]:
    return answer(request.model_dump())
