# LacHong Discord Assistant UI

React prototype for CP3. It runs with deterministic mock responses by default and can connect to a backend implementing the JSON contract in `FLOW_CP2.MD`.

## Run locally

```bash
cd codebase/ui
cp .env.example .env
npm install
npm run dev
```

No API key is required in mock mode.

## Connect a backend

Set the following values in `.env`:

```env
VITE_API_MODE=api
VITE_API_BASE_URL=http://localhost:8000
```

The UI sends `POST /api/assist`, fetches the official-source archive from `GET /api/sources`, and loads the team-only Golden Set from `GET /api/evaluation/cases`. It does not call Gemini or Discord directly, and no secret belongs in this directory.

## Golden Set evaluation panel

In API mode, open **Agent Inspector** from the channel header. The panel lets the team select a group or a case, then run one case or all 30 cases sequentially through the backend. It compares the returned intent, effective action, and citation ID against `eval/golden_set.json`.

This is a review tool, separate from the learner-facing chat. The canonical full evaluation remains `python eval/run_eval.py`; it additionally checks factuality, conciseness, and safety boundaries and writes the report artifacts.

## CP3 demo path

1. Start in mock mode and click each of the five scenario buttons.
2. Show the source citation for Lab 02.
3. Show clarification chips, then click `Lab 02 CVAT`.
4. Show the handoff button and confirmation toast.
5. Start the Core AI service from the repository root with `python -m uvicorn codebase.core_ai.server:app --reload`.
6. Switch to API mode and record the 30-second real-AI call. The UI uses the backend response and backend source archive; it has no production citations hardcoded in API mode.

## Checks

```bash
npm run lint
npm run test
npm run build
```
