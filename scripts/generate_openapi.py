"""Deterministically generate the OpenAPI contract from the FastAPI app.

Usage:
    python scripts/generate_openapi.py

Drift check (CI):
    python scripts/generate_openapi.py && git diff --exit-code contracts/openapi/backend-v1.json
"""

from __future__ import annotations

import json
import pathlib

from backend.app import create_app
from backend.config import Settings

OUTPUT = pathlib.Path("contracts/openapi/backend-v1.json")


def main() -> None:
    app = create_app(Settings(storage_backend="memory", event_broker="memory"))
    spec = app.openapi()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
