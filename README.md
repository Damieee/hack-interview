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

# expose to your phone on the same Wi-Fi
pnpm dev -- --host 0.0.0.0 --port 5173
```

By default the UI expects the backend at `http://localhost:8000` (override with `VITE_API_URL`).

### Accessing from your phone

1. Ensure your computer and phone are on the same network.
2. Run the backend with a public host:
   ```bash
   cd web_app/backend
   uv run fastapi_app -- --host 0.0.0.0 --port 8000
   ```
3. Start the frontend with `pnpm dev -- --host 0.0.0.0 --port 5173`.
4. On your phone, open `http://<your-computer-ip>:5173` and set
   `VITE_API_URL=http://<your-computer-ip>:8000` in `web_app/frontend/.env`
   before starting the dev server.
