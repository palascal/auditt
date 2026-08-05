"""Diagnose car listing pages: status, title, link counts, sample hrefs."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from playwright.sync_api import sync_playwright

from url_generator import build_search_url

CFG = {
    "year_min": 2006,
    "year_max": 2010,
    "price_max": 25000,
    "engines": ["1.8_tfsi", "2.0_tfsi", "2.0_tdi", "3.2_v6", "tts", "ttrs"],
}

SITES = {
    "lacentrale": "/auto-occasion-annonce-",
    "leboncoin": "/ad/voitures/",
    "autoscout24": "/annonces/",
    "paruvendu": "/a/voiture/",
}

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def main() -> None:
    out_dir = Path(__file__).resolve().parents[1] / "data"
    out_dir.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=UA,
            locale="fr-FR",
            timezone_id="Europe/Paris",
            viewport={"width": 1440, "height": 900},
            extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9"},
        )
        page = context.new_page()

        for builder, substr in SITES.items():
            url = build_search_url(builder, CFG)
            print("\n===", builder, "===")
            print(url)
            status = None
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=60000)
                status = resp.status if resp else None
                page.wait_for_timeout(3500)
                for label in ("Tout accepter", "Accepter", "Accept all", "J'accepte"):
                    try:
                        btn = page.get_by_role("button", name=re.compile(label, re.I))
                        if btn.count():
                            btn.first.click(timeout=1500)
                            page.wait_for_timeout(800)
                    except Exception:
                        pass
                page.wait_for_timeout(2000)
            except Exception as e:
                print("NAV ERROR", e)
                continue

            title = page.title()
            body = page.inner_text("body")[:500].replace("\n", " | ")
            hrefs = page.eval_on_selector_all(
                "a[href]",
                "els => [...new Set(els.map(e => e.getAttribute('href')||'').filter(Boolean))]",
            )
            matched = [h for h in hrefs if substr in h]
            print("status", status, "title", title[:80])
            print("body", body[:300])
            print("total_links", len(hrefs), "matched", len(matched), "substr", substr)
            for h in matched[:8]:
                print("  ", h[:140])
            # Also try alternate substrings
            for alt in (
                "annonce",
                "/voiture",
                "/auto-",
                "offers/",
                "/ad/",
                "detail",
                "listing",
            ):
                n = sum(1 for h in hrefs if alt in h.lower())
                if n:
                    print(f"  alt[{alt}]={n}")
            html_path = out_dir / f"probe_{builder}.html"
            html_path.write_text(page.content(), encoding="utf-8")
            print("saved", html_path.name)

        browser.close()


if __name__ == "__main__":
    main()
