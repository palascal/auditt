"""AudiTT scrape entrypoint — product config + scrapekit runner."""

from __future__ import annotations

from functools import partial

import _bootstrap

_bootstrap.ensure_scrapekit()

from scrapekit.runner import run_parallel, scrape_one

from results_store import (
    item_matches_active_filters,
    merge_new_listings,
    purge_invalid_site_links,
    purge_sold_and_dead,
    write_scrape_report,
)
from runtime_config import load_runtime_config, save_runtime_config
from site_registry import SITE_SPECS, apply_custom_sites, site_labels
from utils.telegram import send_telegram_message

MAX_WORKERS = 3


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

    scrape_fn = partial(scrape_one, merge_fn=merge_new_listings)
    site_reports = run_parallel(
        work, max_workers=MAX_WORKERS, scrape_fn=scrape_fn, site_specs=SITE_SPECS
    )

    total_telegram = 0
    total_inserted = 0
    for report in site_reports:
        label = report.get("label", report.get("site"))
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
