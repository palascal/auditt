import importlib
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from results_store import (
    item_matches_active_filters,
    merge_new_listings,
    purge_invalid_site_links,
    purge_sold_and_dead,
    write_scrape_report,
)
from runtime_config import load_runtime_config, save_runtime_config
from site_registry import SITE_SPECS, apply_custom_sites, site_labels
from utils.seen import commit_seen
from utils.telegram import send_telegram_message

MAX_WORKERS = 3


def load_scraper(path, **kwargs):
    module_name, class_name = path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)(**kwargs)


def _scrape_one(site: str, spec: dict, jobs: list) -> dict:
    label = spec.get("label", site)
    out = {
        "site": site,
        "label": label,
        "jobs": len(jobs),
        "results": 0,
        "inserted": 0,
        "telegram": 0,
        "stats": {},
        "error": None,
        "new_items": [],
    }
    if not jobs:
        return out
    try:
        kwargs = {
            "site_key": site,
            "query_jobs": jobs,
            "headless": True,
        }
        scraper = load_scraper(spec["scraper"], **kwargs)
        results = scraper.fetch_listings() or []
        out["results"] = len(results)
        out["stats"] = dict(getattr(scraper, "stats", {}) or {})
        inserted_items = merge_new_listings(site, label, results)
        out["inserted"] = len(inserted_items)
        out["new_items"] = inserted_items
        pending = list(getattr(scraper, "pending_seen", []) or [])
        seen_path = spec.get("seen_path")
        if seen_path and pending:
            commit_seen(seen_path, pending)
    except Exception as e:
        out["error"] = str(e)
        traceback.print_exc()
    return out


def run():
    print("\n⚙️  Chargement config Audi TT…")
    cfg = load_runtime_config(site_labels())
    apply_custom_sites(cfg.get("custom_sites") or [])

    import config as config_mod

    config_mod.FILTERS["year_min"] = int(cfg.get("year_min") or 2006)
    config_mod.FILTERS["year_max"] = int(cfg.get("year_max") or 2010)
    config_mod.FILTERS["engines"] = list(cfg.get("engines") or [])
    config_mod.FILTERS["price_max"] = float(cfg.get("price_max") or 25000)

    print(
        f"   Années: {config_mod.FILTERS['year_min']}–{config_mod.FILTERS['year_max']}"
    )
    print(f"   Motorisations: {', '.join(config_mod.FILTERS['engines']) or '(toutes)'}")
    print(f"   Prix max: {int(config_mod.FILTERS['price_max'])} €")

    try:
        save_runtime_config(cfg)
    except Exception as e:
        print(f"   (snapshot local skip: {e})")

    from url_generator import generate_site_batches

    batches = generate_site_batches(cfg)
    work = []
    for site, spec in SITE_SPECS.items():
        jobs = batches.get(site, [])
        label = spec.get("label", site)
        print(f"\n🚀 Queue {label}: {len(jobs)} recherche(s)")
        if not jobs:
            print("   (aucun job — skip)")
            continue
        work.append((site, spec, jobs))

    site_reports = []
    total_telegram = 0
    total_inserted = 0

    print(f"\n🧵 Parallel scrape ({min(MAX_WORKERS, max(1, len(work)))} workers)…")
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, max(1, len(work)))) as pool:
        futures = {
            pool.submit(_scrape_one, site, spec, jobs): site
            for site, spec, jobs in work
        }
        for fut in as_completed(futures):
            site = futures[fut]
            try:
                report = fut.result()
            except Exception as e:
                report = {
                    "site": site,
                    "label": SITE_SPECS.get(site, {}).get("label", site),
                    "error": str(e),
                    "inserted": 0,
                    "new_items": [],
                    "stats": {},
                }
            site_reports.append(report)
            label = report.get("label", site)
            if report.get("error"):
                print(f"⚠️ Erreur {label}: {report['error']}")
                continue
            print(
                f"✅ {label}: {report.get('results', 0)} scrapées / "
                f"{report.get('inserted', 0)} ajoutées | stats={report.get('stats')}"
            )
            for item in report.get("new_items") or []:
                if not item_matches_active_filters(item):
                    continue
                year = item.get("year") or ""
                message = (
                    f"🆕 <b>{label}</b>\n"
                    f"📌 {item.get('titre', 'Audi TT')}\n"
                    f"📅 {year} · 💰 {item.get('prix', 'N/A')}\n"
                    f"🔗 {item.get('lien', '')}"
                )
                send_telegram_message(message)
                total_telegram += 1
            total_inserted += int(report.get("inserted") or 0)

    print("\n🧹 Purge vendus / liens morts…")
    purge = purge_sold_and_dead(max_head_checks=40)
    print(f"   {purge}")
    invalid = purge_invalid_site_links()
    print(f"   invalid_links: {invalid}")

    write_scrape_report(
        {
            "total_inserted": total_inserted,
            "total_telegram": total_telegram,
            "year_min": config_mod.FILTERS.get("year_min"),
            "year_max": config_mod.FILTERS.get("year_max"),
            "engines": config_mod.FILTERS.get("engines"),
            "purge": purge,
            "sites": [
                {
                    "site": r.get("site"),
                    "label": r.get("label"),
                    "jobs": r.get("jobs"),
                    "results": r.get("results"),
                    "inserted": r.get("inserted"),
                    "stats": r.get("stats"),
                    "error": r.get("error"),
                }
                for r in sorted(site_reports, key=lambda x: x.get("site") or "")
            ],
        }
    )

    print(
        f"🏁 Terminé: {total_inserted} ajoutées au dashboard, "
        f"{total_telegram} alertes Telegram."
    )


if __name__ == "__main__":
    run()
