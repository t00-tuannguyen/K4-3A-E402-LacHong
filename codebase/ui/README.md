# LacHong Discord Assistant UI

## Purpose

React/Vite client for the Track B1 demo. It renders a Discord-like learner chat and connects only to the local Core AI HTTP API. It never calls Gemini, 9router, Discord, or any secret-bearing service directly.

## Run

```bash
cd codebase/ui
cp .env.example .env
npm install
npm run dev
```

The frontend always connects to the Core AI backend. Configure its base URL when it is not running at the default `http://localhost:8000`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Backend contract

| UI operation | Endpoint | Notes |
|---|---|---|
| Send learner message | `POST /api/assist` | Receives an `AgentResponse`; UI validates its shape before rendering. |
| Open source archive | `GET /api/sources` | Sources appear in `#nguon-chinh-thuc`. |
| Load Dev Set | `GET /api/evaluation/cases` | Available only in API mode; reads the backend-owned 15-case development set. The sealed Eval Set is never sent to the browser. |

The request and response TypeScript contracts live in `src/types.ts`. Keep backend and frontend changes compatible with those types.

## Product behavior

- Learner messages display an editable `@Trợ lý` mention. The UI removes that display mention before sending `message_text` to the backend.
- A cited answer can open `#nguon-chinh-thuc` and highlight the corresponding official-source fixture loaded from the backend.
- Clarification chips send a follow-up learner question.
- A TA handoff adds a reply-style assistant message that quotes and links back to the original learner question. It is a local demo interaction; it does not create a Discord thread or webhook.
- Out-of-scope requests show `/ticket create` guidance. They do not modify learner records or deadlines.

## Development-set panel

The collapsible **Evaluation** bar sits above the composer. It uses the six categories from `eval/dev_set.json`, with Vietnamese display labels only:

1. Có nguồn / trả lời được
2. Chưa có thông báo chính thức
3. Cần làm rõ câu hỏi
4. Ngoài quyền hỗ trợ
5. Mâu thuẫn nguồn
6. Bẫy an toàn / prompt injection

Selecting a case and clicking **Đưa vào chat** only prefills the composer. A presenter then presses Enter or Gửi, so the visible chat follows the same path as a learner message. The batch-review action runs only the 15 development cases; the sealed set is evaluated by the Python runner outside the browser.

The UI quick-check compares intent, effective action, and cited source ID. The canonical release evaluation remains `python eval/run_eval.py` (sealed set by default), which also evaluates factuality, conciseness, and safety boundaries. Do not modify rules from its sealed results.

## Checks

```bash
npm run lint
npm run test
npm run build
```
