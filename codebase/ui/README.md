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

Use `VITE_API_MODE=mock` for deterministic UI work. Use the following values to connect the local backend:

```env
VITE_API_MODE=api
VITE_API_BASE_URL=http://localhost:8000
```

## Backend contract

| UI operation | Endpoint | Notes |
|---|---|---|
| Send learner message | `POST /api/assist` | Receives an `AgentResponse`; UI validates its shape before rendering. |
| Open source archive | `GET /api/sources` | Sources appear in `#nguon-chinh-thuc`. |
| Load Golden Set | `GET /api/evaluation/cases` | Available only in API mode; reads the backend-owned 30-case set. |

The request and response TypeScript contracts live in `src/types.ts`. Keep backend and frontend changes compatible with those types.

## Product behavior

- Learner messages display an editable `@Trợ lý` mention. The UI removes that display mention before sending `message_text` to the backend.
- A cited answer can open `#nguon-chinh-thuc` and highlight the mock official announcement.
- Clarification chips send a follow-up learner question.
- A TA handoff adds a reply-style assistant message that quotes and links back to the original learner question. It is a local demo interaction; it does not create a Discord thread or webhook.
- Out-of-scope requests show `/ticket create` guidance. They do not modify learner records or deadlines.

## Golden Set panel

The collapsible **Evaluation** bar sits above the composer. It uses the six categories from `eval/golden_set.json`, with Vietnamese display labels only:

1. Có nguồn / trả lời được
2. Chưa có thông báo chính thức
3. Cần làm rõ câu hỏi
4. Ngoài quyền hỗ trợ
5. Mâu thuẫn nguồn
6. Bẫy an toàn / prompt injection

Selecting a case and clicking **Đưa vào chat** only prefills the composer. A presenter then presses Enter or Gửi, so the visible chat follows the same path as a learner message. **Tự chạy cả 30** is the separate batch-review action.

The UI quick-check compares intent, effective action, and cited source ID. The canonical evaluation remains `python eval/run_eval.py`, which also evaluates factuality, conciseness, and safety boundaries.

## Checks

```bash
npm run lint
npm run test
npm run build
```
