"""Generic listing scraper — AudiTT thin wrapper around scrapekit."""

from __future__ import annotations

import _bootstrap

_bootstrap.ensure_scrapekit()

from scrapekit.scrapers.generic_listing import GenericListingScraper as _KitGeneric

from config import DATA_DIR
from site_registry import SITE_SPECS
from utils.filters import listing_matches_filters


class GenericListingScraper(_KitGeneric):
    def __init__(self, site_key: str, query_jobs=None, **kwargs):
        # daily/full mode (max_results, scroll, early-stop) from scrapekit.scrape_mode
        super().__init__(
            site_key,
            query_jobs=query_jobs,
            site_specs=SITE_SPECS,
            match_fn=listing_matches_filters,
            data_dir=DATA_DIR,
            browser_profile_env=(
                "AUDIT_BROWSER_PROFILE",
                "SCRAPEKIT_BROWSER_PROFILE",
            ),
            allow_unknown_price=True,
            price_min=500,
            price_max_band=200_000,
            **kwargs,
        )
