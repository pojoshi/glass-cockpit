"""Entry point for `glass-cockpit serve`."""

import os
import sys


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] != "serve":
        print("usage: glass-cockpit serve", file=sys.stderr)
        raise SystemExit(2)
    import uvicorn

    from .api import create_app_from_env

    app = create_app_from_env()
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8001)))


if __name__ == "__main__":
    main()
