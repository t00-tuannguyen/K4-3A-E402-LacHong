# Codebase Guide

## Scope

This repository is a coursework prototype for a grounded Discord logistics assistant. The product answers only from the controlled official-announcement fixture, asks for clarification when an entity is missing, and routes unsafe or unsupported requests to human support.

## Directory map

| Path | Responsibility |
|---|---|
| `core_ai/assistant.py` | Intent classification, deterministic guardrails, grounding, and `AgentResponse` construction. |
| `core_ai/server.py` | FastAPI HTTP adapter: `/health`, `/api/assist`, `/api/sources`, `/api/evaluation/cases`. |
| `data/official_announcements.json` | Public, mock official announcement archive used for citations. |
| `ui/` | React/Vite Discord-style client. Read `ui/README.md` before changing UI behavior. |
| `../eval/golden_set.json` | The backend-owned 30-case evaluation set. |
| `../eval/run_eval.py` | Canonical full evaluation runner and report writer. |

## Run locally

From the repository root:

```bash
python -m uvicorn codebase.core_ai.server:app --reload
```

In another terminal:

```bash
cd codebase/ui
npm run dev
```

## API ownership

The frontend sends learner requests only to `POST /api/assist`. Backend-owned source data and evaluation cases are exposed through GET endpoints. Do not copy the Golden Set into a second frontend fixture; load it from `/api/evaluation/cases` in API mode.

## Safety invariants

1. Never invent a deadline, room, policy, URL, or citation.
2. A grounded answer must cite a record from `official_announcements.json`.
3. Personal records, attendance edits, extensions, and submission changes remain outside the assistant's authority. Direct the learner to `/ticket create` instead.
4. A conflict or missing ground truth must produce a human-handoff path, not an invented answer.
5. The UI must not contain API keys, Discord tokens, learner data, or direct calls to LLM providers.
6. A UI handoff is currently a controlled mock interaction. Do not claim that it creates a real Discord thread, sends a webhook, or notifies a real TA.

## LLM boundary

The LLM is used for intent classification when configured. The backend owns grounding, source selection, response text templates, and final safety decisions. Treat LLM output as untrusted classification data; do not turn it into a citation or a new fact.

## Verification

```bash
# UI
cd codebase/ui
npm run lint
npm run test
npm run build

# Backend endpoint contract
cd ../..
python3 -m unittest discover -s tests -p 'test_server.py'

# Full quality measurement
python eval/run_eval.py
```

Run the full evaluation only when a deliberate backend/LLM measurement is intended. It can call the configured model provider in live mode.
