# syntax=docker/dockerfile:1

### Frontend build
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend

# Install pnpm
RUN corepack enable

COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend ./
RUN pnpm build

### Backend image
FROM python:3.12-slim AS backend

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FRONTEND_DIST=/app/frontend_dist

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml backend/README.md backend/uv.lock /app/backend/
COPY backend/app /app/backend/app
COPY backend/fastapi_app.py /app/backend/fastapi_app.py
COPY backend/.env.example /app/backend/.env.example

RUN pip install --upgrade pip && pip install uv
RUN cd /app/backend && uv sync --frozen --no-dev

COPY --from=frontend-builder /frontend/dist ${FRONTEND_DIST}

WORKDIR /app/backend
EXPOSE 8000

CMD ["uv", "run", "fastapi_app.py", "--host", "0.0.0.0", "--port", "8000"]
