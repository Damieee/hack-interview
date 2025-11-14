# Web App (React + FastAPI)

This folder contains a new full-stack version of the AI interview assistant.

## Project layout

```
web_app/
├── backend/        # FastAPI service (uv-compatible)
└── frontend/       # React + TypeScript UI powered by Vite
```

## Requirements

- Python 3.10+ with [uv](https://docs.astral.sh/uv/) installed
- Node.js 18+ with [pnpm](https://pnpm.io/) installed
- An OpenAI API key (`OPENAI_API_KEY`)

## Backend

```bash
cd web_app/backend
cp .env.example .env  # fill in OPENAI_API_KEY and optional defaults
uv run fastapi_app
```

The API is exposed on `http://localhost:8000`.

## Frontend

```bash
cd web_app/frontend
pnpm install
pnpm dev
```

By default the UI expects the backend at `http://localhost:8000` (override with `VITE_API_URL`).

