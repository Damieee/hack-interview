# Backend – FastAPI

## Setup

```bash
cd backend
uv sync  # optional; installs dependencies declared in pyproject.toml
```

Environment variables are defined once at the repo root (`../.env`). Copy `.env.example` → `.env` and fill in your OpenAI keys before running the server.

## Run

```bash
uv run fastapi_app -- --host 0.0.0.0 --port 8000
```

The API will be available on <http://localhost:8000>. When deployed via Docker, the root `.env` should be supplied using `--env-file`.
