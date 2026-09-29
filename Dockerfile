# syntax=docker/dockerfile:1

# 1. Build the React chat UI.
FROM node:22-alpine AS web
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

# 2. Python API that also serves the built UI.
FROM python:3.13-slim AS app
COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev
COPY services ./services
COPY policies ./policies
COPY fixtures ./fixtures
COPY --from=web /web/dist ./apps/web/dist
ENV PATH="/app/.venv/bin:$PATH" \
    FIXTURES_DIR=/app/fixtures \
    POLICIES_DIR=/app/policies \
    WEB_DIST_DIR=/app/apps/web/dist \
    DATABASE_PATH=/data/sessions.sqlite3
RUN useradd --create-home --uid 10001 app && mkdir -p /data && chown app /data
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2).status == 200 else 1)"
CMD ["sh", "-c", "uvicorn app.main:create_app --factory --app-dir services/api --host 0.0.0.0 --port ${PORT:-8000}"]
