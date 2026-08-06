"""Leboncoin mail — AudiTT wrapper around scrapekit (car filters + year)."""

from __future__ import annotations

from datetime import datetime, timezone

import _bootstrap

_bootstrap.ensure_scrapekit()

from scrapekit.scrapers.leboncoin_mail import LeboncoinMailScraper as _KitMailScraper

from config import (
    IMAP_EMAIL_ACCOUNT,
    IMAP_EMAIL_PASSWORD,
    IMAP_MAILBOX,
    IMAP_MAX_EMAILS,
    IMAP_PORT,
    IMAP_SERVER,
)
from utils.filters import extract_year, listing_matches_car_filters


def _car_match(title, prix, *, link="", description="", **kwargs):
    return listing_matches_car_filters(
        title,
        prix,
        link=link,
        description=description,
        year_min=kwargs.get("year_min"),
        year_max=kwargs.get("year_max"),
        engines=kwargs.get("engines"),
        price_max=kwargs.get("price_max"),
    )


class LeboncoinMailScraper(_KitMailScraper):
    def __init__(self, *args, site_key="leboncoin", **kwargs):
        from site_registry import SITE_SPECS

        seen_path = (SITE_SPECS.get(site_key) or {}).get("seen_path")
        super().__init__(
            *args,
            site_key=site_key,
            seen_path=seen_path,
            match_fn=_car_match,
            imap_account=IMAP_EMAIL_ACCOUNT,
            imap_password=IMAP_EMAIL_PASSWORD,
            imap_server=IMAP_SERVER,
            imap_port=IMAP_PORT,
            imap_mailbox=IMAP_MAILBOX,
            imap_max_emails=IMAP_MAX_EMAILS,
            **kwargs,
        )

    def fetch_listings(self):
        results = super().fetch_listings()
        now = datetime.now(timezone.utc).isoformat()
        for item in results:
            item.setdefault("year", extract_year(item.get("titre") or ""))
            item.setdefault("found_at", now)
        return results
