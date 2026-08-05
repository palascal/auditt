"""Car listing filters: Audi TT + year range + selected engines + price."""

from __future__ import annotations

import re

from config import ENGINE_OPTIONS, FILTERS
from utils.price import price_within_max_eur
from utils.text_norm import fold_text


def _engine_catalog() -> dict[str, dict]:
    return {e["id"]: e for e in ENGINE_OPTIONS}


def extract_year(text: str) -> int | None:
    """Best-effort model/registration year from title/card text."""
    blob = text or ""
    years = [int(y) for y in re.findall(r"\b(19\d{2}|20[0-2]\d)\b", blob)]
    years = [y for y in years if 1998 <= y <= 2026]
    if not years:
        return None
    # Prefer years in typical TT Mk2 window when several appear (mileage vs year)
    preferred = [y for y in years if 2006 <= y <= 2014]
    return preferred[0] if preferred else years[0]


def extract_posted_date(text: str) -> str:
    """Return a short human date string if present on the card."""
    blob = text or ""
    m = re.search(
        r"\b(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})\b",
        blob,
    )
    if m:
        return m.group(1)
    m = re.search(
        r"\b(aujourd'?hui|hier|il y a \d+\s*(?:min|h|jours?|semaines?))\b",
        blob,
        re.I,
    )
    if m:
        return m.group(1)
    return ""


def is_audi_tt(title: str, description: str = "", link: str = "") -> bool:
    blob = fold_text(f"{title} {description} {link}")
    if "audi" not in blob and "/audi/" not in blob and "audi:" not in blob:
        # Accept TT-only if link path is clearly audi/tt
        if "tt" in blob and ("/tt" in blob or "modele=tt" in blob or "model=tt" in blob):
            return True
        return False
    # Reject TT Roadster naming edge cases? Keep all TT.
    if re.search(r"\btt\b", blob) or "audi tt" in blob or "/tt" in blob:
        # Exclude non-car clutter
        if any(x in blob for x in ("jouet", "miniature", "maquette", "poster", "casque", "piece detachee")):
            return False
        return True
    return False


def engine_matches(text: str, selected_ids: list[str] | None) -> bool:
    """If no engines selected, accept all. Else OR across selected patterns."""
    ids = list(selected_ids or [])
    if not ids:
        return True
    blob = fold_text(text)
    catalog = _engine_catalog()
    for eid in ids:
        spec = catalog.get(eid)
        if not spec:
            continue
        for pat in spec.get("patterns") or []:
            if fold_text(pat) in blob:
                return True
        # label match
        if fold_text(spec.get("label") or "") in blob:
            return True
    # If title has no engine hint, keep listing (sites already filtered by model/year)
    has_any_engine_hint = False
    for spec in catalog.values():
        for pat in spec.get("patterns") or []:
            if fold_text(pat) in blob:
                has_any_engine_hint = True
                break
    if not has_any_engine_hint:
        return True
    return False


def year_in_range(year: int | None, year_min: int, year_max: int) -> bool:
    if year is None:
        # Keep when site URL already constrained years but card omitted year
        return True
    return year_min <= year <= year_max


def listing_matches_car_filters(
    title: str,
    prix_str: str,
    *,
    description: str = "",
    link: str = "",
    year_min: int | None = None,
    year_max: int | None = None,
    engines: list[str] | None = None,
    price_max: float | None = None,
) -> bool:
    ymin = int(year_min if year_min is not None else FILTERS.get("year_min", 2006))
    ymax = int(year_max if year_max is not None else FILTERS.get("year_max", 2010))
    if ymin > ymax:
        ymin, ymax = ymax, ymin
    pmax = float(price_max if price_max is not None else FILTERS.get("price_max", 25000))
    eng = engines if engines is not None else list(FILTERS.get("engines") or [])

    blob = f"{title} {description}"
    if not is_audi_tt(title, description, link):
        return False
    year = extract_year(blob)
    if not year_in_range(year, ymin, ymax):
        return False
    if not engine_matches(blob, eng):
        return False
    return price_within_max_eur(prix_str, pmax)


# Keep name used by older imports
def listing_matches_filters(title, prix_str, keywords=None, price_max=float("inf"), **kwargs):
    return listing_matches_car_filters(
        title,
        prix_str,
        description=kwargs.get("description", ""),
        link=kwargs.get("link", ""),
        price_max=price_max if price_max != float("inf") else None,
        year_min=kwargs.get("year_min"),
        year_max=kwargs.get("year_max"),
        engines=kwargs.get("engines"),
    )


def dedupe_fingerprint(title: str | None, prix_str: str | None) -> str:
    from utils.price import parse_price_eur

    t = fold_text(title)
    t = re.sub(r"\b(vends?|vend|occasion|audi|tt|coupe|roadster)\b", " ", t)
    t = re.sub(r"\s+", " ", t).strip()[:120]
    eur = parse_price_eur(prix_str)
    bucket = f"{int(round(eur / 100.0) * 100)}" if eur is not None else "?"
    return f"{t}|{bucket}"
