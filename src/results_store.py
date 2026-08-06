"""Persist scraped listings for the GitHub Pages dashboard."""

from __future__ import annotations

import _bootstrap

_bootstrap.ensure_scrapekit()

from scrapekit.store import (
    merge_new_listings as _merge,
    purge_sold_and_dead as _purge,
    write_scrape_report as _write_report,
)

from config import LISTINGS_JSON_PATH, ROOT
from utils.filters import dedupe_fingerprint, listing_matches_filters

REPORT_PATH = ROOT / "docs" / "data" / "scrape_report.json"


def _postprocess_entry(entry: dict, raw: dict) -> None:
    if not entry.get("posted_at"):
        found = entry.get("found_at") or ""
        entry["posted_at"] = found[:10] if found else ""


def merge_new_listings(site: str, label: str, results: list[dict]) -> list[dict]:
    return _merge(
        LISTINGS_JSON_PATH,
        site,
        label,
        results,
        dedupe_fingerprint=dedupe_fingerprint,
        default_title="Audi TT",
        extra_fields=("year", "posted_at"),
        postprocess_entry=_postprocess_entry,
    )


def purge_sold_and_dead(max_head_checks: int = 40) -> dict:
    return _purge(
        LISTINGS_JSON_PATH,
        max_head_checks=max_head_checks,
        user_agent="AudiTT-purge/1.0",
        skip_hosts=("ebay.", "reverb.", "soundsmarket."),
    )


def write_scrape_report(report: dict) -> None:
    _write_report(REPORT_PATH, report)


def item_matches_active_filters(item: dict) -> bool:
    from config import FILTERS

    return listing_matches_filters(
        item.get("titre") or "",
        item.get("prix") or "",
        description=item.get("description") or "",
        link=item.get("lien") or "",
        year_min=FILTERS.get("year_min"),
        year_max=FILTERS.get("year_max"),
        engines=FILTERS.get("engines"),
        price_max=FILTERS.get("price_max"),
    )


def purge_invalid_site_links() -> dict:
    """Drop facet/geo pages wrongly saved as ads (esp. ParuVendu)."""
    import re

    from site_registry import SITE_SPECS
    from scrapekit.store import load_listings, save_listings

    items = load_listings(LISTINGS_JSON_PATH)
    before = len(items)
    kept = []
    removed = 0
    for it in items:
        site = it.get("site") or ""
        lien = (it.get("lien") or "").strip()
        spec = SITE_SPECS.get(site) or {}
        link_re = spec.get("link_regex")
        if link_re and lien and not re.search(link_re, lien):
            removed += 1
            continue
        kept.append(it)
    if removed:
        save_listings(LISTINGS_JSON_PATH, kept)
    return {"before": before, "after": len(kept), "removed": removed}
