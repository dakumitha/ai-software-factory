"""Command-line entry point."""
import argparse
from .core import serve


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Software Factory control plane")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--database", default="data/factory.sqlite3")
    args = parser.parse_args()
    serve(args.host, args.port, args.database)


if __name__ == "__main__":
    main()
