"""Build scrape jobs for Audi TT car sites from runtime config."""

from __future__ import annotations

from urllib.parse import quote, quote_plus, urlencode

from runtime_config import enabled_site_keys, load_runtime_config
from site_registry import SITE_SPECS, apply_custom_sites, site_labels


def _years(cfg: dict) -> tuple[int, int]:
    ymin = int(cfg.get("year_min") or 2006)
    ymax = int(cfg.get("year_max") or 2010)
    if ymin > ymax:
        ymin, ymax = ymax, ymin
    return ymin, ymax


def _price_max(cfg: dict) -> float:
    try:
        return float(cfg.get("price_max") or 25000)
    except (TypeError, ValueError):
        return 25000.0


def _engines(cfg: dict) -> list[str]:
    engines = cfg.get("engines")
    if isinstance(engines, list) and engines:
        return [str(e) for e in engines]
    return []


def build_search_url(builder: str, cfg: dict) -> str:
    ymin, ymax = _years(cfg)
    if builder == "lacentrale":
        # AUDI:TT commercial name filter + year range
        params = {
            "makesModelsCommercialNames": "AUDI:TT",
            "yearMin": str(ymin),
            "yearMax": str(ymax),
            "sortBy": "FIRST_ONLINE_DESC",
        }
        pmax = _price_max(cfg)
        if pmax < float("inf"):
            params["priceMax"] = str(int(pmax))
        return "https://www.lacentrale.fr/listing?" + urlencode(params)

    if builder == "leboncoin":
        params = {
            "category": "2",
            "text": "audi tt",
            "u_car_brand": "AUDI",
            "u_car_model": "TT",
            "regdate": f"min_{ymin}_max_{ymax}",
            "owner_type": "all",
            "sort": "time",
            "order": "desc",
        }
        pmax = _price_max(cfg)
        if pmax < float("inf"):
            params["price"] = f"min-max_{int(pmax)}"
        return "https://www.leboncoin.fr/recherche?" + urlencode(params)

    if builder == "autoscout24":
        params = {
            "fregfrom": str(ymin),
            "fregto": str(ymax),
            "atype": "C",
            "cy": "F",
            "desc": "1",
            "sort": "age",
            "ustate": "N,U",
        }
        pmax = _price_max(cfg)
        if pmax < float("inf"):
            params["priceto"] = str(int(pmax))
        return "https://www.autoscout24.fr/lst/audi/tt?" + urlencode(params)

    if builder == "paruvendu":
        # Text search with year hints; site structure varies
        q = quote(f"audi tt {ymin} {ymax}")
        return (
            "https://www.paruvendu.fr/a/voiture/audi/tt"
            f"?prixmax={int(_price_max(cfg))}&annee1={ymin}&annee2={ymax}&q={q}"
        )

    raise ValueError(f"Unknown car url builder: {builder}")


def generate_site_batches(runtime_cfg: dict | None = None):
    """Returns {site_key: [job, ...]} — one search URL per enabled site."""
    cfg = runtime_cfg or load_runtime_config(site_labels())
    apply_custom_sites(cfg.get("custom_sites") or [])
    enabled = enabled_site_keys(cfg)
    ymin, ymax = _years(cfg)
    engines = _engines(cfg)
    price_max = _price_max(cfg)

    out = {}
    for site, spec in SITE_SPECS.items():
        if site not in enabled:
            print(f"   ⏸️  {spec.get('label', site)} désactivé (config)")
            out[site] = []
            continue
        builder = spec.get("url_builder")
        url = build_search_url(builder, cfg)
        out[site] = [
            {
                "url": url,
                "price_max": price_max,
                "keywords": ["audi", "tt"],
                "year_min": ymin,
                "year_max": ymax,
                "engines": engines,
                "apply_filters": True,
            }
        ]
        print(f"   🔎 {spec.get('label', site)}: {url}")
    return out
