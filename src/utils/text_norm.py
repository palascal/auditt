"""Normalize text — re-export from scrapekit."""

from __future__ import annotations

import _bootstrap

_bootstrap.ensure_scrapekit()

from scrapekit.text import (  # noqa: E402,F401
    fold_text,
    is_ligature_listing,
    is_mouthpiece_listing,
    keywords_match,
)
