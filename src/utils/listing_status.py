"""Sold listing detection — re-export from scrapekit."""

from __future__ import annotations

import _bootstrap

_bootstrap.ensure_scrapekit()

from scrapekit.listing_status import is_sold_listing  # noqa: E402,F401

__all__ = ["is_sold_listing"]
