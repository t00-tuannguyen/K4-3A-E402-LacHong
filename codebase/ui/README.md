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

The UI sends `POST /api/v1/agent/message`. It does not call Gemini or Discord directly, and no secret belongs in this directory.

## CP3 demo path

1. Start in mock mode and click each of the five scenario buttons.
2. Show the source citation for Lab 02.
3. Show clarification chips, then click `Lab 02 CVAT`.
4. Show the handoff button and confirmation toast.
5. Switch to API mode once the backend is ready and record the 30-second real-AI call.

## Checks

```bash
npm run lint
npm run test
npm run build
```
