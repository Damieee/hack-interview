# Backend – FastAPI

## Setup

```bash
cd web_app/backend
uv sync  # optional, installs dependencies declared in pyproject.toml
```

Create a `.env` file based on `.env.example` and set `OPENAI_API_KEY`.

## Run

```bash
uv run fastapi_app
```

The API will be available on http://localhost:8000.
