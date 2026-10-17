"""Command-line entry point for the AI Software Factory control plane."""
import argparse

from .core import serve


def main() -> None:
    """Start the API/control room, or run the disposable deterministic demo."""
    parser = argparse.ArgumentParser(description="AI Software Factory control plane")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--database", default="data/factory.sqlite3")
    parser.add_argument(
        "--web",
        action="store_true",
        help="Serve the responsive control room and JSON API from the same origin.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run a zero-cost dry run in a temporary database; no AI or shell execution.",
    )
    args = parser.parse_args()

    # Demo mode is isolated from the configured database so a learning run does
    # not create sample projects or jobs in the user's normal factory records.
    if args.demo:
        from .demo import main as run_demo
        run_demo()
    elif args.web:
        from .webapp import serve_web
        serve_web(args.host, args.port, args.database)
    else:
        serve(args.host, args.port, args.database)


if __name__ == "__main__":
    main()
