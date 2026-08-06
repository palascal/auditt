"""Registry of car listing sites for Audi TT searches."""

from config import DATA_DIR

# French auto classifieds + marketplaces.
# Leboncoin + La Centrale: alertes e-mail → IMAP (pas de scrape web / DataDome).
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
        # Real ads: /a/voiture-occasion/audi/tt/1287878109A1KVVOAUTT
        "link_substr": "/a/voiture-occasion/audi/tt/",
        "link_substrs": ["/a/voiture-occasion/audi/tt/"],
        "link_regex": r"/a/voiture-occasion/audi/tt/\d{7,}[A-Za-z0-9]+/?$",
        "link_exclude": [],
        "wait_selector": "a[href*='/a/voiture-occasion/audi/tt/']",
        "price_regex": r"\d[\d\s.,]*\s*€|€\s?\d[\d.,]*",
    },
    "lacentrale": {
        # Alertes e-mail → IMAP (comme Leboncoin)
        "kind": "mail",
        "scraper": "scrapers.lacentrale_mail_scraper.LacentraleMailScraper",
        "seen_path": DATA_DIR / "seen_lacentrale.json",
        "label": "La Centrale",
        "base_url": "https://www.lacentrale.fr",
    },
    "leboncoin": {
        # Alertes e-mail → IMAP (Gmail, etc.) — pas de scrape web / DataDome
        "kind": "mail",
        "scraper": "scrapers.leboncoin_mail_scraper.LeboncoinMailScraper",
        "seen_path": DATA_DIR / "seen_leboncoin.json",
        "label": "Leboncoin",
        "base_url": "https://www.leboncoin.fr",
    },
}

def site_labels() -> dict[str, str]:
    return {k: v.get("label", k) for k, v in SITE_SPECS.items()}


def apply_custom_sites(custom_sites) -> None:
    """No-op for AudiTT (fixed car sources). Kept for runtime_config compat."""
    return
