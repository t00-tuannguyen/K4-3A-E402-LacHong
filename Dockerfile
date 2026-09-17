# Single-service deploy: build the React UI, then serve it and the API from FastAPI.
FROM node:22-alpine AS ui
WORKDIR /ui
COPY codebase/ui/package.json codebase/ui/package-lock.json ./
RUN npm ci
COPY codebase/ui/ ./
# Same-origin API: the UI calls /api/* on the host that served it.
ENV VITE_API_MODE=api VITE_API_BASE_URL=""
RUN npx vite build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY codebase/ codebase/
COPY config/ config/
COPY eval/golden_set.json eval/golden_set.json
COPY --from=ui /ui/dist codebase/ui/dist
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["sh", "-c", "uvicorn codebase.core_ai.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
