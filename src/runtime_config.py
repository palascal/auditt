"""Load runtime scrape config (year, engines, price, sites).

Priority:
1. AUDIT_CONFIG_URL (HTTP JSON) — dashboard API on Cloudflare
2. docs/data/scrape_config.json
3. Built-in defaults
"""

from __future__ import annotations

import json
import os
import urllib.request
from copy import deepcopy
from pathlib import Path

from config import ENGINE_OPTIONS, FILTERS, ROOT

CONFIG_PATH = ROOT / "docs" / "data" / "scrape_config.json"
DEFAULT_CONFIG_URL = os.getenv(
    "AUDIT_CONFIG_URL", "https://auditt.pages.dev/api/config"
)


def _default_config(site_keys_labels: dict[str, str] | None = None) -> dict:
    sites = {}
    if site_keys_labels:
        for key, label in site_keys_labels.items():
            sites[key] = {"enabled": True, "label": label}
    return {
        "version": 1,
        "year_min": int(FILTERS.get("year_min", 2006)),
        "year_max": int(FILTERS.get("year_max", 2010)),
        "engines": list(FILTERS.get("engines") or [e["id"] for e in ENGINE_OPTIONS]),
        "price_max": float(FILTERS.get("price_max", 25000)),
        "sites": sites,
        "custom_sites": [],
    }


def _fetch_remote(url: str) -> dict | None:
    if not url:
        return None
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "auditt-scraper/1.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, dict) and ("year_min" in data or "engines" in data):
                print(f"   ⚙️ Config distante OK ({url})")
                return data
    except Exception as e:
        print(f"   ⚙️ Config distante indisponible ({url}): {e}")
    return None


def _load_file() -> dict | None:
    if not CONFIG_PATH.exists():
        return None
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            print(f"   ⚙️ Config locale: {CONFIG_PATH}")
            return data
    except Exception as e:
        print(f"   ⚙️ Config locale illisible: {e}")
    return None


def load_runtime_config(site_keys_labels: dict[str, str] | None = None) -> dict:
    remote = _fetch_remote(DEFAULT_CONFIG_URL)
    local = _load_file()
    base = _default_config(site_keys_labels)
    chosen = remote or local or base
    if site_keys_labels:
        sites = chosen.setdefault("sites", {})
        for key, label in site_keys_labels.items():
            if key not in sites:
                sites[key] = {"enabled": True, "label": label}
            else:
                sites[key].setdefault("label", label)
                sites[key].setdefault("enabled", True)
    chosen.setdefault("year_min", base["year_min"])
    chosen.setdefault("year_max", base["year_max"])
    chosen.setdefault("engines", deepcopy(base["engines"]))
    chosen.setdefault("price_max", base["price_max"])
    chosen.setdefault("custom_sites", [])
    # Drop leftover sax filters if present
    chosen.pop("filters", None)
    chosen.pop("include_mouthpieces", None)
    chosen.pop("include_ligatures", None)
    chosen.pop("filter_mode", None)
    return chosen


def save_runtime_config(data: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def enabled_site_keys(cfg: dict) -> set[str]:
    sites = cfg.get("sites") or {}
    return {k for k, v in sites.items() if (v or {}).get("enabled", True)}


def filter_rows_from_config(cfg: dict) -> list[dict]:
    """Compat shim — returns a synthetic row for logging."""
    return [
        {
            "keywords": ["audi", "tt"],
            "price_max": float(cfg.get("price_max") or 25000),
            "year_min": int(cfg.get("year_min") or 2006),
            "year_max": int(cfg.get("year_max") or 2010),
            "engines": list(cfg.get("engines") or []),
        }
    ]
