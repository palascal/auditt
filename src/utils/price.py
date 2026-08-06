"""Price parsing — scrapekit core; AudiTT keeps unknown prices."""

from __future__ import annotations

import _bootstrap

_bootstrap.ensure_scrapekit()

from scrapekit.price import (  # noqa: E402,F401
    detect_currency,
    parse_price_eur,
    to_eur,
)
from scrapekit.price import price_within_max_eur as _price_within_max_eur


def price_within_max_eur(prix_str: str | None, price_max_eur: float) -> bool:
    # Unknown price (JSON-LD without amount): keep if SERP already price-capped
    return _price_within_max_eur(prix_str, price_max_eur, allow_unknown=True)


__all__ = [
    "detect_currency",
    "parse_price_eur",
    "to_eur",
    "price_within_max_eur",
]
