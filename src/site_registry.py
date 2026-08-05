"""Registry of car listing sites for Audi TT searches."""

from config import DATA_DIR

# French auto classifieds + marketplaces.
# Note: lacentrale / leboncoin use DataDome — often 403 from datacenter IPs (GitHub Actions).
SITE_SPECS = {
    "autoscout24": {
        "kind": "marketplace",
        "scraper": "scrapers.car_listing_scraper.CarListingScraper",
        "seen_path": DATA_DIR / "seen_autoscout24.json",
        "label": "AutoScout24",
        "base_url": "https://www.autoscout24.fr",
        "url_builder": "autoscout24",
        "link_substr": "/offres/",
        "link_substrs": ["/offres/"],
        "link_exclude": ["/offres/dealer", "/offres/seller"],
        "wait_selector": "script[type='application/ld+json']",
        "price_regex": r"\d[\d\s.,]*\s*€|€\s?\d[\d.,]*",
        "parse_jsonld": True,
    },
    "paruvendu": {
        "kind": "marketplace",
        "scraper": "scrapers.car_listing_scraper.CarListingScraper",
        "seen_path": DATA_DIR / "seen_paruvendu.json",
        "label": "ParuVendu",
        "base_url": "https://www.paruvendu.fr",
        "url_builder": "paruvendu",
        # Real ads use voiture-occasion paths with city; category pages are excluded below.
        "link_substr": "/a/voiture-occasion/audi/tt/",
        "link_substrs": ["/a/voiture-occasion/audi/tt/"],
        "link_exclude": [],
        "wait_selector": "a[href*='/a/voiture-occasion/audi/tt/']",
        "price_regex": r"\d[\d\s.,]*\s*€|€\s?\d[\d.,]*",
    },
    "lacentrale": {
        "kind": "marketplace",
        "scraper": "scrapers.car_listing_scraper.CarListingScraper",
        "seen_path": DATA_DIR / "seen_lacentrale.json",
        "label": "La Centrale",
        "base_url": "https://www.lacentrale.fr",
        "url_builder": "lacentrale",
        "link_substr": "/auto-occasion-annonce-",
        "link_substrs": ["/auto-occasion-annonce-", "/listing"],
        "wait_selector": "a[href*='auto-occasion-annonce']",
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
        "link_substrs": ["/ad/voitures/", "/voitures/"],
        "wait_selector": "a[href*='/ad/voitures/']",
        "price_regex": r"\d[\d\s.,]*\s*€|€\s?\d[\d.,]*",
    },
}


def site_labels() -> dict[str, str]:
    return {k: v.get("label", k) for k, v in SITE_SPECS.items()}


def apply_custom_sites(custom_sites) -> None:
    """No-op for AudiTT (fixed car sources). Kept for runtime_config compat."""
    return
