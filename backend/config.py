"""Configuration loader.

This project primarily reads configuration from environment variables.

We optionally load a top-level `.env` file (project root) if present.

Important: `telegram_service.py` and other services read with `os.environ.get(...)`.
So `.env` must be loaded into environment variables before importing those modules.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv_if_present(dotenv_path: str | None = None) -> None:
    """Load key/value pairs from a `.env` file into os.environ.

    Format supported:
      KEY=VALUE
    Comments supported via leading '#'.
    Quotes are not required.

    No third-party packages are used.
    """
    if dotenv_path is None:
        root = Path(__file__).resolve().parents[1]  # .../trade-yantra/backend -> .../trade-yantra
        dotenv_path = str(root / ".env")

    p = Path(dotenv_path)
    if not p.exists():
        return

    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if "=" not in s:
                continue
            k, v = s.split("=", 1)
            k = k.strip()
            v = v.strip()

            # Remove surrounding quotes if present
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]

            # Only set if not already present
            os.environ.setdefault(k, v)
    except Exception:
        # Never hard-fail boot due to dotenv parsing issues.
        return

