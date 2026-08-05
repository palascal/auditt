"""
eBay scraper: SERP links a[href*='/itm/'] + title/price from result cards,
with optional item-page enrichment for image/description.
"""

from __future__ import annotations

import json
import os
import re
import time

from playwright.sync_api import sync_playwright

from config import FILTERS, SEEN_EBAY_PATH
from scrapers.base_scraper import BaseScraper
from scrapers.generic_listing_scraper import _price_to_float
from utils.filters import listing_matches_filters
from utils.listing_status import is_sold_listing
from utils.price import price_within_max_eur
from utils.seen import load_seen
from utils.text_norm import is_mouthpiece_listing

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _normalize_item_url(href: str):
    if not href or "/itm/" not in href:
        return None
    if href.startswith("//"):
        href = "https:" + href
    elif href.startswith("/"):
        href = "https://www.ebay.com" + href
    # Keep ebay.com / ebay.fr host as returned
    if href.startswith("/"):
        href = "https://www.ebay.com" + href
    return href.split("?")[0].rstrip("/")


class EbayScraper(BaseScraper):
    def __init__(
        self,
        query_jobs=None,
        url=None,
        price_max=float("inf"),
        profile_path=None,
        headless=True,
        max_results=40,
    ):
        if query_jobs is not None:
            self._jobs = list(query_jobs)
        elif url:
            self._jobs = [{"url": url, "price_max": price_max}]
        else:
            self._jobs = []
        self.profile = profile_path
        self.headless = headless
        self.max_results = max_results
        self.cache_file = str(SEEN_EBAY_PATH)
        self.pending_seen: list[str] = []
        self.stats = {
            "seen": 0,
            "filter": 0,
            "price": 0,
            "sold": 0,
            "skip": 0,
            "ok": 0,
            "retries": 0,
        }

    def _load_seen(self):
        return load_seen(self.cache_file)

    def _extract_id(self, url):
        match = re.search(r"/itm/(\d+)", url)
        return match.group(1) if match else None

    def _price_ok(self, prix_str, price_max):
        return price_within_max_eur(prix_str, price_max)

    def _fetch_item_details(self, context, lien: str) -> tuple[str, str, str, str]:
        """Fiche produit: titre, prix, image, courte description."""
        titre, prix, image, description = "", "", "", ""
        page = context.new_page()
        try:
            page.goto(lien, wait_until="domcontentloaded", timeout=45_000)
            time.sleep(0.8)
            page.wait_for_selector(
                "h1.x-item-title__mainTitle, h1#itemTitle, h1",
                timeout=15_000,
            )
            for sel in (
                "h1.x-item-title__mainTitle span.ux-textspans",
                "h1.x-item-title__mainTitle",
                "h1#itemTitle",
                "h1",
            ):
                t = page.locator(sel).first
                if t.count():
                    titre = t.inner_text().strip()
                    if titre:
                        break
            for sel in (
                "div.x-price-primary span.ux-textspans",
                "div.x-price-primary",
                '[itemprop="price"]',
                "#prcIsum",
                ".x-bin-price__content",
            ):
                p = page.locator(sel).first
                if p.count():
                    prix = p.inner_text().strip()
                    if _price_to_float(prix) is not None:
                        break
            img = page.locator(
                "img[data-zoom-src], .ux-image-carousel-item img, #icImg, img[itemprop='image']"
            ).first
            if img.count():
                image = (
                    img.get_attribute("data-zoom-src")
                    or img.get_attribute("src")
                    or ""
                ).strip()
            desc_loc = page.locator(
                "#ds_div, .x-item-description, [data-testid='x-item-description']"
            ).first
            if desc_loc.count():
                description = re.sub(r"\s+", " ", desc_loc.inner_text().strip())[:280]
        except Exception:
            pass
        finally:
            page.close()
        return titre, prix, image, description

    def _log_page_diag(self, page, label: str) -> None:
        try:
            title = page.title()
        except Exception:
            title = "?"
        print(f"   [diag {label}] title={title!r} url={page.url}")

    def _collect_serp_cards(self, page) -> list[dict]:
        """Title/price/link from result cards — avoids opening every item when possible."""
        return page.evaluate(
            """() => {
              const out = [];
              const seen = new Set();
              const cards = document.querySelectorAll(
                'li.s-item, .s-item, li[data-viewport], .srp-results li'
              );
              const push = (href, title, price, image) => {
                if (!href || !href.includes('/itm/')) return;
                const key = href.split('?')[0];
                if (seen.has(key)) return;
                seen.add(key);
                out.push({
                  href: key,
                  title: (title || '').trim().replace(/\\s+/g, ' ').slice(0, 160),
                  price: (price || '').trim().replace(/\\s+/g, ' '),
                  image: (image || '').trim(),
                });
              };
              for (const card of cards) {
                const a = card.querySelector("a[href*='/itm/']");
                if (!a) continue;
                const titleEl = card.querySelector(
                  '.s-item__title, .s-card__title, [role="heading"], h3'
                );
                let title = titleEl ? (titleEl.innerText || titleEl.textContent || '') : '';
                if (/shop on ebay/i.test(title)) continue;
                const priceEl = card.querySelector(
                  '.s-item__price, .s-card__price, [class*="price"]'
                );
                const img = card.querySelector('img');
                push(
                  a.href || a.getAttribute('href') || '',
                  title || (a.innerText || ''),
                  priceEl ? (priceEl.innerText || '') : '',
                  img ? (img.currentSrc || img.src || '') : ''
                );
              }
              if (!out.length) {
                for (const a of document.querySelectorAll("a[href*='/itm/']")) {
                  push(a.href || '', a.innerText || '', '', '');
                }
              }
              return out;
            }"""
        )

    def fetch_listings(self):
        results = []
        if not self._jobs:
            return results

        seen_ids = self._load_seen()
        keywords_all = []

        with sync_playwright() as p:
            browser = None
            ctx = None
            try:
                if self.profile:
                    ctx = p.chromium.launch_persistent_context(
                        self.profile,
                        headless=self.headless,
                        channel="chrome",
                        args=["--start-maximized"],
                    )
                    list_page = ctx.pages[0] if ctx.pages else ctx.new_page()
                else:
                    browser = p.chromium.launch(
                        headless=self.headless,
                        args=[
                            "--disable-dev-shm-usage",
                            "--no-sandbox",
                            "--disable-blink-features=AutomationControlled",
                        ],
                    )
                    ctx = browser.new_context(
                        user_agent=_DEFAULT_UA,
                        locale="en-US",
                        viewport={"width": 1365, "height": 900},
                        ignore_https_errors=True,
                    )
                    list_page = ctx.new_page()
                    list_page.add_init_script(
                        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                    )
                    # Warm-up reduces first-hit Error Page on Actions
                    try:
                        list_page.goto(
                            "https://www.ebay.com/",
                            wait_until="domcontentloaded",
                            timeout=45_000,
                        )
                        time.sleep(1.5)
                    except Exception:
                        pass

                for j_idx, job in enumerate(self._jobs, start=1):
                    url = job["url"]
                    price_max = float(job.get("price_max", float("inf")))
                    keywords = job.get("keywords") or []
                    keywords_all = keywords
                    print(f"  → Recherche {j_idx}/{len(self._jobs)}: {url[:90]}...")

                    cards = []
                    for attempt in range(1, 4):
                        try:
                            list_page.goto(
                                url, wait_until="domcontentloaded", timeout=90_000
                            )
                        except Exception as e:
                            print(f"   ⚠️ goto eBay ({attempt}/3): {e}")
                            self.stats["retries"] += 1
                            time.sleep(1.5 * attempt)
                            continue

                        print("   Attente liens /itm/…")
                        time.sleep(2)
                        for _ in range(3):
                            try:
                                list_page.mouse.wheel(0, 1800)
                            except Exception:
                                break
                            time.sleep(0.4)
                        try:
                            list_page.wait_for_selector(
                                "a[href*='/itm/']", timeout=45_000
                            )
                        except Exception:
                            title = ""
                            try:
                                title = list_page.title()
                            except Exception:
                                pass
                            if "error" in title.lower() or attempt < 3:
                                print(
                                    f"   ⚠️ SERP bloquée/vide ({attempt}/3) title={title!r}"
                                )
                                self.stats["retries"] += 1
                                # Warm-up again then retry
                                try:
                                    list_page.goto(
                                        "https://www.ebay.com/",
                                        wait_until="domcontentloaded",
                                        timeout=30_000,
                                    )
                                    time.sleep(1.2)
                                except Exception:
                                    pass
                                continue
                            print(
                                "   ⚠️ Timeout: aucun lien /itm/ (captcha, blocage, page vide)"
                            )
                            self._log_page_diag(list_page, "timeout serp")
                            break

                        cards = self._collect_serp_cards(list_page)
                        if cards:
                            break
                        self.stats["retries"] += 1
                        print(f"   ⚠️ 0 cartes SERP ({attempt}/3) — retry")
                        time.sleep(1.5)

                    print(f"   Cartes SERP: {len(cards)}")
                    if not cards:
                        continue

                    added_job = 0
                    consecutive_seen = 0
                    for idx, card in enumerate(cards, start=1):
                        if added_job >= self.max_results:
                            break
                        lien = _normalize_item_url(card.get("href") or "")
                        if not lien:
                            continue
                        item_id = self._extract_id(lien)
                        if not item_id:
                            continue
                        if item_id in seen_ids:
                            consecutive_seen += 1
                            self.stats["seen"] += 1
                            if consecutive_seen >= 12:
                                print("   ⛔ Beaucoup déjà vus → fin de ce flux")
                                break
                            continue
                        consecutive_seen = 0

                        titre = (card.get("title") or "").strip()
                        titre = re.sub(
                            r"\s*Opens in a new window or tab\s*",
                            " ",
                            titre,
                            flags=re.I,
                        ).strip()
                        titre = re.sub(r"^NEW LISTING\s*", "", titre, flags=re.I).strip()
                        prix = (card.get("price") or "").strip()
                        image = (card.get("image") or "").strip()
                        description = ""

                        if not titre or not prix or _price_to_float(prix) is None:
                            t2, p2, img2, d2 = self._fetch_item_details(ctx, lien)
                            titre = titre or t2
                            if p2 and _price_to_float(p2) is not None:
                                prix = p2
                            image = image or img2
                            description = d2

                        if is_sold_listing(titre, prix, description):
                            self.stats["sold"] += 1
                            continue

                        if not listing_matches_filters(
                            titre,
                            prix,
                            keywords or None,
                            price_max,
                            description=description,
                            link=lien,
                        ):
                            self.stats["filter"] += 1
                            continue

                        if not titre and not prix:
                            print(
                                f"   [{idx}] Fiche incomplète (pas de titre/prix) — skip"
                            )
                            self.stats["skip"] += 1
                            continue

                        print(f"   [{idx}] {(titre or 'Sans titre')[:55]}… | {prix or 'N/A'}")

                        seen_ids.add(item_id)
                        self.pending_seen.append(item_id)
                        results.append(
                            {
                                "titre": titre or "Annonce eBay",
                                "prix": prix or "N/A",
                                "lien": lien,
                                "image": image,
                                "description": description,
                            }
                        )
                        added_job += 1
                        self.stats["ok"] += 1

            finally:
                if ctx:
                    try:
                        ctx.close()
                    except Exception:
                        pass
                if browser:
                    try:
                        browser.close()
                    except Exception:
                        pass
                # Seen committed by main after merge

        print(f"\n✅ eBay: {len(results)} nouvelles annonces")
        return results
