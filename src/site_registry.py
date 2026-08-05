"""Registry of car listing sites for Audi TT searches."""

from pathlib import Path

from config import DATA_DIR

# French auto classifieds + marketplaces.
SITE_SPECS = {
    "lacentrale": {
        "kind": "marketplace",
        "scraper": "scrapers.car_listing_scraper.CarListingScraper",
        "seen_path": DATA_DIR / "seen_lacentrale.json",
        "label": "La Centrale",
        "base_url": "https://www.lacentrale.fr",
        "url_builder": "lacentrale",
        "link_substr": "/auto-occasion-annonce-",
        "wait_selector": "a[href*='/auto-occasion-annonce-']",
        "price_regex": r"\d[\d\s.,]*\s*€|€\s?\d[\d.,]*",
    },
    "leboncoin": {
        "kind": "marketplace",
        "scraper": "scrapers.car_listing_scraper.CarListingScraper",
        "seen_path": DATA_DIR / "seen_leboncoin.json",
        "label": "Leboncoin",
        "base_url": "https://www.leboncoin.fr",
        "url_builder": "leboncoin",
        "link_substr": "/ad/voitures/",
        "wait_selector": "a[href*='/ad/voitures/']",
        "price_regex": r"\d[\d\s.,]*\s*€|€\s?\d[\d.,]*",
    },
    "autoscout24": {
        "kind": "marketplace",
        "scraper": "scrapers.car_listing_scraper.CarListingScraper",
        "seen_path": DATA_DIR / "seen_autoscout24.json",
        "label": "AutoScout24",
        "base_url": "https://www.autoscout24.fr",
        "url_builder": "autoscout24",
        "link_substr": "/annonces/",
        "wait_selector": "a[href*='/annonces/']",
        "price_regex": r"\d[\d\s.,]*\s*€|€\s?\d[\d.,]*",
    },
    "paruvendu": {
        "kind": "marketplace",
        "scraper": "scrapers.car_listing_scraper.CarListingScraper",
        "seen_path": DATA_DIR / "seen_paruvendu.json",
        "label": "ParuVendu",
        "base_url": "https://www.paruvendu.fr",
        "url_builder": "paruvendu",
        "link_substr": "/a/voiture/",
        "wait_selector": "a[href*='/a/voiture/']",
        "price_regex": r"\d[\d\s.,]*\s*€|€\s?\d[\d.,]*",
    },
}


def site_labels() -> dict[str, str]:
    return {k: v.get("label", k) for k, v in SITE_SPECS.items()}


def apply_custom_sites(custom_sites) -> None:
    """No-op for AudiTT (fixed car sources). Kept for runtime_config compat."""
    return
