import argparse

from app.main import create_app


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="Run Interview Assistant API server.")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to.")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to.")
    parser.add_argument("--reload", action="store_true", help="Enable reload (dev only).")
    args = parser.parse_args()

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
