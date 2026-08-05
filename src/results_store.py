"""Persist scraped listings for the GitHub Pages dashboard."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

from config import LISTINGS_JSON_PATH, ROOT
from utils.filters import dedupe_fingerprint, listing_matches_filters
from utils.listing_status import is_sold_listing

REPORT_PATH = ROOT / "docs" / "data" / "scrape_report.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_listings() -> list[dict]:
    path = LISTINGS_JSON_PATH
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data["items"]
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _save_listings(items: list[dict]) -> None:
    path = LISTINGS_JSON_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    items = [
        it
        for it in items
        if not is_sold_listing(
            it.get("titre", ""),
            it.get("prix", ""),
            it.get("description", ""),
        )
    ]
    payload = {
        "updated_at": _now_iso(),
        "count": len(items),
        "items": items,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def merge_new_listings(site: str, label: str, results: list[dict]) -> list[dict]:
    """
    Merge newly scraped items into docs/data/listings.json.
    Returns the list of newly inserted items (not updates).
    Cross-site near-duplicates (same title+price bucket) are skipped.
    """
    items = _load_listings()
    by_link = {it.get("lien"): it for it in items if it.get("lien")}
    fingerprints = {
        dedupe_fingerprint(it.get("titre"), it.get("prix")) for it in items
    }
    inserted: list[dict] = []
    for raw in results:
        lien = (raw.get("lien") or "").strip()
        if not lien:
            continue
        if is_sold_listing(
            raw.get("titre", ""),
            raw.get("prix", ""),
            raw.get("description", ""),
        ):
            if lien in by_link:
                items = [it for it in items if it.get("lien") != lien]
                by_link.pop(lien, None)
            continue
        if lien in by_link:
            existing = by_link[lien]
            if not existing.get("image") and raw.get("image"):
                existing["image"] = raw["image"]
            if not existing.get("description") and raw.get("description"):
                existing["description"] = raw["description"]
            continue
        fp = dedupe_fingerprint(raw.get("titre"), raw.get("prix"))
        if fp in fingerprints and "?" not in fp:
            continue
        entry = {
            "id": lien,
            "site": site,
            "site_label": label,
            "titre": raw.get("titre") or "Audi TT",
            "prix": raw.get("prix") or "N/A",
            "lien": lien,
            "image": raw.get("image") or "",
            "description": (raw.get("description") or "")[:400],
            "year": raw.get("year"),
            "posted_at": raw.get("posted_at") or "",
            "found_at": raw.get("found_at") or _now_iso(),
        }
        if not entry["posted_at"]:
            # Fallback: show discovery date on the card
            entry["posted_at"] = entry["found_at"][:10]
        items.append(entry)
        by_link[lien] = entry
        fingerprints.add(fp)
        inserted.append(entry)

    items.sort(key=lambda x: x.get("found_at") or "", reverse=True)
    _save_listings(items)
    return inserted


def purge_sold_and_dead(max_head_checks: int = 40) -> dict:
    """Remove sold listings; optionally drop links that return 404/410."""
    items = _load_listings()
    before = len(items)
    kept = []
    removed_sold = 0
    removed_dead = 0
    checked = 0
    for it in items:
        if is_sold_listing(
            it.get("titre", ""),
            it.get("prix", ""),
            it.get("description", ""),
        ):
            removed_sold += 1
            continue
        lien = (it.get("lien") or "").strip()
        if lien and checked < max_head_checks:
            checked += 1
            try:
                host = urlparse(lien).netloc
                # Skip heavy marketplace checks that often block HEAD
                if host and not any(
                    x in host for x in ("ebay.", "reverb.", "soundsmarket.")
                ):
                    r = requests.head(
                        lien,
                        timeout=8,
                        allow_redirects=True,
                        headers={"User-Agent": "AudiTT-purge/1.0"},
                    )
                    if r.status_code in {404, 410, 451}:
                        removed_dead += 1
                        continue
            except Exception:
                pass
        kept.append(it)
    if len(kept) != before:
        _save_listings(kept)
    return {
        "before": before,
        "after": len(kept),
        "removed_sold": removed_sold,
        "removed_dead": removed_dead,
        "checked": checked,
    }


def write_scrape_report(report: dict) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report = {**report, "updated_at": _now_iso()}
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


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

    items = _load_listings()
    before = len(items)
    kept = []
    removed = 0
    for it in items:
        site = it.get("site") or ""
        lien = (it.get("lien") or "").strip()
        spec = SITE_SPECS.get(site) or {}
        link_re = spec.get("link_regex")
        ok = True
        if site == "paruvendu":
            if not link_re or not lien or not re.search(link_re, lien):
                ok = False
        if ok:
            kept.append(it)
        else:
            removed += 1
    if removed:
        _save_listings(kept)
    return {"before": before, "after": len(kept), "removed_invalid": removed}
