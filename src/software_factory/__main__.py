"""Command-line entry point."""
import argparse

from .core import serve


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Software Factory control plane")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--database", default="data/factory.sqlite3")
    parser.add_argument(
        "--web",
        action="store_true",
        help="Serve the responsive control room and JSON API from the same origin.",
    )
    args = parser.parse_args()
    if args.web:
        from .webapp import serve_web
        serve_web(args.host, args.port, args.database)
    else:
        serve(args.host, args.port, args.database)


if __name__ == "__main__":
    main()
