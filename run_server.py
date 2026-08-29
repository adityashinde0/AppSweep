"""
Server runner script for JP-001 Duplicate Application Manager.
"""

from __future__ import annotations

import os
import sys
import uvicorn

# Ensure UTF-8 output on Windows terminal
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def main() -> None:
    """Run FastAPI development server with uvicorn."""
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() in ("true", "1", "yes")

    print("=" * 80)
    print("       JP-001 Duplicate Application Manager Server Starting")
    print(f"       [+] Web Dashboard        : http://{host}:{port}")
    print(f"       [+] API Docs (Swagger)   : http://{host}:{port}/docs")
    print("=" * 80)

    uvicorn.run("api.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
