"""Ensure scrapekit is importable (installed package, sibling repo, or CI checkout)."""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_scrapekit() -> Path | None:
    try:
        import scrapekit  # noqa: F401

        return Path(scrapekit.__file__).resolve().parent.parent
    except ImportError:
        pass

    here = Path(__file__).resolve()
    documents = here.parents[2]
    candidates = [
        documents / "scrapekit",
        here.parents[1] / "scrapekit",  # CI: actions/checkout path: scrapekit
        here.parents[1] / "packages" / "scrapekit",
    ]
    for kit in candidates:
        if kit.is_dir() and (kit / "scrapekit").is_dir():
            s = str(kit)
            if s not in sys.path:
                sys.path.insert(0, s)
            return kit
    return None
