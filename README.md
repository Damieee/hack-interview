# AI Interview Assistant – Monorepo

This repository bundles the React/Vite frontend and FastAPI backend for the interview prep tool.

```
├── backend/   # FastAPI + OpenAI logic (Python, uv)
└── frontend/  # React + TypeScript UI (Vite + pnpm)
```

## Prerequisites

1. `python 3.10+` with [`uv`](https://docs.astral.sh/uv/) installed.
2. `node 18+` with [`pnpm`](https://pnpm.io/) (`corepack enable pnpm`).
3. **Single root env file**: copy `.env.example` → `.env` (in the repo root) and set:
   - Backend keys: `OPENAI_API_KEY`, `DEFAULT_MODEL`, `VISION_MODEL`, etc.
   - Frontend keys: `VITE_API_URL` (and any future `VITE_*` values).

## Running locally

### Backend
```bash
cd backend
uv run fastapi_app -- --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
pnpm install
pnpm dev -- --host 0.0.0.0 --port 5173
```

> The frontend automatically reads `VITE_*` values from the root `.env`, so no per-folder env files are needed.

## Docker deployment

Builds the frontend, installs backend deps via `uv`, serves both from one image:

```bash
docker build -t interview-assistant .
docker run --env-file ./.env -p 8000:8000 interview-assistant
```

The container exposes:

- API routes at `http://host:8000/api/...`
- Frontend SPA at `http://host:8000/`

## Access from your phone

1. Start backend/fronted (or the Docker container) with `--host 0.0.0.0`.
2. Ensure your phone is on the same network.
3. Open `http://<machine-ip>:5173` (or `:8000` if using Docker) to use the UI. Camera, screenshot, and webcam capture all work from mobile browsers.

## Useful commands

```bash
# Frontend production build
cd frontend && pnpm run build

# Backend bytecode check
cd backend && uv run python -m compileall app

# Optional lint (if ruff installed)
cd backend && uv run ruff check app
```

The new Dockerfile is ready for cloud platforms that accept container images; supply secrets via runtime env vars, never bake them into the image.
