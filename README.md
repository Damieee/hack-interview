# AI Interview Assistant – Monorepo

This repository hosts the full-stack version of the interview prep tool:

```
├── backend/   # FastAPI + OpenAI inference layer (Python / uv)
└── frontend/  # React + TypeScript UI (Vite + pnpm)
```

## Prerequisites (local dev)

- Python 3.10+ with [uv](https://docs.astral.sh/uv/) enabled (`pip install uv`)
- Node.js 18+ with [pnpm](https://pnpm.io/) (`corepack enable pnpm`)
- OpenAI API key in `backend/.env` (copy from `.env.example`)

### Backend

```bash
cd backend
cp .env.example .env   # fill in OPENAI_API_KEY, DEFAULT_MODEL, etc.
uv run fastapi_app -- --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev -- --host 0.0.0.0 --port 5173
```

Set `VITE_API_URL` in `frontend/.env` if the backend runs on a different host/IP.

## Docker Deployments

A single container can build the React app, bundle it with the FastAPI backend, and serve both:

```bash
# From the repo root
docker build -t interview-assistant .

# Provide secrets via --env-file (never bake real .env into the image)
docker run --env-file backend/.env -p 8000:8000 interview-assistant
```

The Docker image:

- Builds the frontend via pnpm and copies the static assets into the image.
- Installs backend dependencies with `uv sync`.
- Serves the API on `0.0.0.0:8000`.
- Exposes the built frontend at `/` (the API routes remain under `/api/...`).

> ⚠️ Remember to use a production-grade `.env` when running in the cloud (e.g., `OPENAI_API_KEY`, `VISION_MODEL`, custom CORS origins).

## Access from Mobile

1. Run both services (or the Docker container) with `--host 0.0.0.0`.
2. Ensure your phone is on the same network.
3. Visit `http://<machine-ip>:5173` (or the exposed port) from your phone’s browser.
4. The camera, screenshot, and webcam workflows will upload to the backend automatically.

## Useful Commands

```bash
# Frontend QA build
cd frontend && pnpm run build

# Backend type check / bytecode compile
cd backend && uv run python -m compileall app

# Lint via ruff (if installed)
cd backend && uv run ruff check app
```

Enjoy the upgraded workflow! The Dockerfile is now the single artifact required for most cloud platforms that accept container images. *** End Patch```} ***!
