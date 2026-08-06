"""Base scraper ABC — re-export from scrapekit."""

from __future__ import annotations

import _bootstrap

_bootstrap.ensure_scrapekit()

from scrapekit.base import BaseScraper  # noqa: E402,F401

__all__ = ["BaseScraper"]
