"""Price parsing and EUR-normalized comparisons."""

from __future__ import annotations

import os
import re

# Approximate mid-market rates (override via env AUDIT_USD_EUR / AUDIT_GBP_EUR)
_USD_EUR = float(os.getenv("AUDIT_USD_EUR", "0.92"))
_GBP_EUR = float(os.getenv("AUDIT_GBP_EUR", "1.17"))


def _price_to_float(prix_str: str) -> float | None:
    if not prix_str:
        return None
    raw = prix_str.replace("\xa0", " ").strip()
    cleaned = re.sub(r"[^\d.,\s]", "", raw)
    cleaned = re.sub(r"\s+", "", cleaned)
    if not cleaned:
        return None
    if re.search(r"\d\.\d{3},\d{2}$", cleaned) or (
        "," in cleaned and "." in cleaned and cleaned.rfind(",") > cleaned.rfind(".")
    ):
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif re.search(r"^\d{1,3}(,\d{3})+(\.\d+)?$", cleaned):
        cleaned = cleaned.replace(",", "")
    elif "," in cleaned and "." not in cleaned:
        if re.search(r",\d{2}$", cleaned):
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    parts = re.findall(r"\d+(?:\.\d+)?", cleaned)
    if not parts:
        return None
    try:
        return float(parts[-1])
    except ValueError:
        return None


def detect_currency(prix_str: str | None) -> str:
    """Return EUR, USD, or GBP (default EUR when unmarked EU-style amounts)."""
    s = (prix_str or "").lower().replace("\xa0", " ")
    if "£" in s or "gbp" in s:
        return "GBP"
    if "$" in s or "usd" in s or "us$" in s:
        return "USD"
    if "€" in s or "eur" in s:
        return "EUR"
    return "EUR"


def to_eur(amount: float, currency: str) -> float:
    cur = (currency or "EUR").upper()
    if cur == "USD":
        return amount * _USD_EUR
    if cur == "GBP":
        return amount * _GBP_EUR
    return amount


def parse_price_eur(prix_str: str | None) -> float | None:
    """Parse a price string and convert to EUR for filter ceilings."""
    val = _price_to_float(prix_str or "")
    if val is None:
        return None
    return to_eur(val, detect_currency(prix_str))


def price_within_max_eur(prix_str: str | None, price_max_eur: float) -> bool:
    if price_max_eur >= float("inf"):
        return True
    eur = parse_price_eur(prix_str)
    if eur is None:
        # Unknown price (JSON-LD slug without amount): keep if SERP already price-capped
        return True
    return eur <= price_max_eur
