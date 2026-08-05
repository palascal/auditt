"""
Generic Playwright listing scraper driven by site_registry SITE_SPECS.

Collects product/ad links from SERP or catalog pages, extracts title/price from
card text, dedupes via seen_*.json, optionally applies FILTERS keyword/price rules.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from urllib.parse import unquote

from playwright.sync_api import sync_playwright

from config import FILTERS
from scrapers.base_scraper import BaseScraper
from site_registry import SITE_SPECS
from utils.filters import listing_matches_filters
from utils.listing_status import is_sold_listing
from utils.price import price_within_max_eur
from utils.seen import load_seen
from utils.text_norm import is_ligature_listing, is_mouthpiece_listing

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _price_to_float(prix_str: str) -> float | None:
    if not prix_str:
        return None
    raw = prix_str.replace("\xa0", " ").strip()
    cleaned = re.sub(r"[^\d.,\s]", "", raw)
    cleaned = re.sub(r"\s+", "", cleaned)  # 1 950,00 → 1950,00
    if not cleaned:
        return None
    # European: 3.053,95 → dot thousands, comma decimals
    if re.search(r"\d\.\d{3},\d{2}$", cleaned) or (
        "," in cleaned and "." in cleaned and cleaned.rfind(",") > cleaned.rfind(".")
    ):
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif re.search(r"^\d{1,3}(,\d{3})+(\.\d+)?$", cleaned):
        # US thousands: 1,900 or 1,900.00
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


def _best_price(card_text: str, text: str, price_re: re.Pattern) -> str:
    """Pick the most plausible price match (prefer last real amount)."""
    blob = f"{card_text or ''} {text or ''}"
    windows = [blob[-120:], blob]
    matches: list[str] = []
    for window in windows:
        preferred = re.findall(
            r"(?:\$|£)\s?\d{1,3}(?:,\d{3})+(?:\.\d{2})?"  # $1,900.00
            r"|(?:\$|£)\s?\d+\.\d{2}"
            r"|€\s?\d{1,3}(?:\.\d{3})+(?:,\d{2})?"  # EU: €3.053,95
            r"|€\s?\d{1,3}(?:,\d{3})+(?:\.\d{2})?"  # €1,900.00
            r"|€\s?\d+[.,]\d{2}(?!\d)"  # €19.99 / €19,99 (not prefix of 1,900)
            r"|(?<!\d)\d(?:[ \u00a0]\d{3})+[.,]\d{2}\s*€"  # 1 950,00 €
            r"|(?<!\d)\d{1,2}(?:[ \u00a0]\d{3})+\s*€"  # 11 500 €
            r"|(?<=\s)\d{3,5}[.,]\d{2}\s*€"  # 650,00 €
            r"|(?<![\d.,])\d{3,5}\s*€",  # 2949 €
            window,
        )
        matches = [m.strip() for m in preferred if re.search(r"\d", m)]
        if matches:
            break
    if not matches:
        matches = [m.group(0).strip() for m in price_re.finditer(blob)]
        matches = [m for m in matches if re.search(r"\d", m)]
    if not matches:
        return "N/A"
    scored = []
    for i, m in enumerate(matches):
        val = _price_to_float(m)
        if val is not None and 80 <= val <= 40_000:
            scored.append((val, i, m))
    if scored:
        mx = max(v for v, _, _ in scored)
        near = [(v, i, m) for v, i, m in scored if v >= mx * 0.85]
        # Prefer the last near-max price (sale price after "was" price)
        near.sort(key=lambda x: x[1])
        return near[-1][2]
    # Fallback: last raw match with a digit
    return matches[-1]


def _price_within_max(prix_str: str, price_max: float) -> bool:
    return price_within_max_eur(prix_str, price_max)


def _matches_filters(title: str, prix_str: str, keywords: list[str] | None, price_max: float) -> bool:
    return listing_matches_filters(title, prix_str, keywords, price_max)


class GenericListingScraper(BaseScraper):
    def __init__(
        self,
        site_key: str,
        query_jobs=None,
        url=None,
        profile_path=None,
        headless=True,
        max_results=60,
        **_kwargs,
    ):
        if site_key not in SITE_SPECS:
            raise ValueError(f"Unknown site_key: {site_key}")
        self.site_key = site_key
        self.spec = SITE_SPECS[site_key]
        if query_jobs is not None:
            self._jobs = list(query_jobs)
        elif url:
            self._jobs = [{"url": url, "price_max": float("inf"), "keywords": None}]
        else:
            self._jobs = []
        self.headless = headless
        self.max_results = max_results
        self.cache_file = str(self.spec["seen_path"])
        self.pending_seen: list[str] = []
        self.stats = {
            "seen": 0,
            "filter": 0,
            "price": 0,
            "sold": 0,
            "skip": 0,
            "ok": 0,
        }

    def _load_seen(self):
        return load_seen(self.cache_file)

    def _normalize_link(self, href: str) -> str | None:
        if not href:
            return None
        substr = self.spec["link_substr"]
        if substr not in href:
            return None
        for excl in self.spec.get("link_exclude") or []:
            if excl in href:
                return None
        if href.startswith("//"):
            href = "https:" + href
        elif href.startswith("/"):
            href = self.spec["base_url"].rstrip("/") + href
        href = href.split("#")[0].split("?")[0].rstrip("/")
        # Collapse www. for stable ids
        href = re.sub(r"://www\.", "://", href)
        # Optional: require a regex on the final URL (e.g. product id pattern)
        link_re = self.spec.get("link_regex")
        if link_re and not re.search(link_re, href, re.I):
            return None
        return href

    def _item_id(self, link: str) -> str:
        return link

    def fetch_listings(self):
        results = []
        if not self._jobs:
            return results

        seen = self._load_seen()
        link_substr = self.spec["link_substr"]
        wait_sel = self.spec.get("wait_selector") or f"a[href*='{link_substr}']"
        price_re = re.compile(self.spec.get("price_regex") or r"[\d.,]+", re.I)
        label = self.spec.get("label", self.site_key)

        with sync_playwright() as p:
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
                locale="fr-FR" if self.site_key == "reverb" else "en-US",
                viewport={"width": 1365, "height": 900},
                ignore_https_errors=True,
            )
            page = ctx.new_page()
            page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )
            try:
                for j_idx, job in enumerate(self._jobs, start=1):
                    url = job["url"]
                    price_max = float(job.get("price_max", float("inf")))
                    keywords = job.get("keywords")
                    if "apply_filters" in job:
                        apply_filters = bool(job["apply_filters"])
                    else:
                        apply_filters = bool(self.spec.get("require_keywords"))
                    print(f"  → [{label}] {j_idx}/{len(self._jobs)}: {url[:100]}...")

                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=90_000)
                    except Exception as e:
                        print(f"   ⚠️ goto: {e}")
                        continue

                    time.sleep(2)
                    try:
                        page.wait_for_load_state("networkidle", timeout=15_000)
                    except Exception:
                        pass
                    # Dismiss common cookie / consent banners that block content
                    for sel in (
                        "button:has-text('Accept all')",
                        "button:has-text('Accept All')",
                        "button:has-text('Accept')",
                        "button:has-text('Tout accepter')",
                        "button:has-text('Agree')",
                        "button:has-text('I agree')",
                        "#onetrust-accept-btn-handler",
                        ".fc-cta-consent",
                        ".cc-btn.cc-dismiss",
                        "[aria-label='Accept cookies']",
                        "#shopify-pc__banner button",
                    ):
                        try:
                            btn = page.locator(sel).first
                            if btn.count() and btn.is_visible(timeout=1500):
                                btn.click(timeout=2000)
                                time.sleep(1.5)
                                break
                        except Exception:
                            continue
                    # Lazy-loaded catalogs (e.g. Saxquest)
                    for _ in range(6):
                        try:
                            page.mouse.wheel(0, 2200)
                        except Exception:
                            break
                        time.sleep(0.55)
                    try:
                        page.wait_for_selector(wait_sel, timeout=45_000)
                    except Exception:
                        # Still try to scrape whatever links are present
                        print(f"   ⚠️ Timeout wait ({wait_sel}) — tentative d'extraction quand même")
                        print(f"   [diag] title={page.title()!r} url={page.url}")

                    # Collect candidates via JS for robustness.
                    # Prefer tight product cards over huge page ancestors.
                    candidates = page.evaluate(
                        """(substr) => {
                          const byKey = new Map();
                          const cardSel = [
                            '.store-item', '.grid-product__wrap-inner', '.grid-product',
                            'article', 'li.product', '.product',
                            '.card', '.grid__item', '.product-item', '.product-card',
                            '.s-item', '[data-product]', '.collection-product',
                            '.woocommerce-LoopProduct-link', '.product-wrapper',
                            '.listing-item', '.ad-list-item'
                          ].join(', ');

                          const score = (c) => {
                            let s = 0;
                            const t = c.text || '';
                            const ct = c.cardText || '';
                            if (t.length >= 8) s += 12;
                            if (c.fromCard) s += 20;
                            if (/(\\$|€|£)\\s?\\d|[\\d.,]+\\s?(€|EUR|USD|GBP)/i.test(ct)) s += 10;
                            if (ct.length > 15 && ct.length < 350) s += 15;
                            else if (ct.length >= 350) s -= 12;
                            if (/<img|javascript:/i.test(t)) s -= 20;
                            if (/^(NEW!|€\\d|\\$\\d)/i.test(t)) s -= 8;
                            return s;
                          };

                          const tightRoot = (a) => {
                            const card = a.closest(cardSel);
                            if (card) return { root: card, fromCard: true };
                            let best = a.parentElement;
                            let el = a.parentElement;
                            for (let i = 0; i < 8 && el; i++) {
                              const t = (el.innerText || '').trim().replace(/\\s+/g, ' ');
                              const prices = t.match(/(\\$|€|£)\\s?[\\d.,]+|[\\d.,]+\\s*€/g) || [];
                              if (t.length > 25 && t.length < 420) {
                                best = el;
                                if (prices.length === 1) break;
                              }
                              if (t.length > 800) break;
                              el = el.parentElement;
                            }
                            return { root: best || a.parentElement, fromCard: false };
                          };

                          for (const a of document.querySelectorAll('a[href]')) {
                            const href = a.getAttribute('href') || '';
                            if (!href.includes(substr)) continue;
                            const abs = (a.href || href).split('?')[0].split('#')[0]
                              .replace(/[/]$/, '').replace('://www.', '://');
                            const key = abs;
                            const { root, fromCard } = tightRoot(a);
                            const linkText = (a.innerText || a.textContent || '')
                              .trim().replace(/\\s+/g, ' ');
                            const titleEl = root && root.querySelector(
                              '.store-item-title, .product-title, .product__title, .product-name, .grid-product__title, .listing-title, h2, h3, .title'
                            );
                            let titleText = titleEl
                              ? (titleEl.innerText || titleEl.textContent || '').trim().replace(/\\s+/g, ' ')
                              : '';
                            if (titleText.length > 180) titleText = titleText.slice(0, 180);
                            const img = (root && root.querySelector('img')) || a.querySelector('img');
                            const image = img
                              ? (img.currentSrc || img.src || img.getAttribute('data-src')
                                 || img.getAttribute('data-lazy-src') || '')
                              : '';
                            const imgAlt = img ? (img.alt || '').trim() : '';
                            let cardText = root
                              ? (root.innerText || root.textContent || '').trim().replace(/\\s+/g, ' ')
                              : linkText;
                            if (cardText.length > 450) cardText = cardText.slice(0, 450);
                            // Prefer real title; avoid badge-only link text like "NEW!" / "€82 off"
                            let text = titleText || '';
                            if (!text && linkText && linkText.length >= 12
                                && !/^(NEW!|Sold Out|€[\\d.,]+ off|\\$[\\d.,]+ off)$/i.test(linkText)) {
                              text = linkText;
                            }
                            if (!text) text = imgAlt || '';
                            const cand = { href, text, cardText, image, fromCard };
                            const prev = byKey.get(key);
                            if (!prev || score(cand) > score(prev)) byKey.set(key, cand);
                          }
                          return Array.from(byKey.values());
                        }""",
                        link_substr,
                    )

                    print(f"   Liens bruts: {len(candidates)}")
                    added = 0
                    n_seen = n_filter = n_price = n_sold = n_skip = 0
                    for entry in candidates:
                        if added >= self.max_results:
                            break
                        link = self._normalize_link(entry.get("href", ""))
                        if not link:
                            n_skip += 1
                            continue
                        item_id = self._item_id(link)
                        if item_id in seen:
                            n_seen += 1
                            continue

                        text = (entry.get("text") or "").strip()
                        card_text = (entry.get("cardText") or text).strip()
                        # Strip leading rating / badge noise (Audiofanzine "0 PRO …")
                        text = re.sub(
                            r"^(?:\d+\s+)+(?:PRO\s+)?", "", text, flags=re.I
                        ).strip()
                        title = text[:160] if text else f"Annonce {label}"
                        if title.lower().startswith("<img") or "class=" in title[:40]:
                            title = f"Annonce {label}"
                        # Skip obvious nav noise / empty image-only anchors
                        if len(title) < 8 or title.lower().startswith("annonce "):
                            # Last chance: derive title from slug in URL
                            slug = unquote(link.rsplit("/", 1)[-1])
                            slug = re.sub(r"\.html?$", "", slug, flags=re.I)
                            slug = re.sub(r"-P\d+$", "", slug, flags=re.I)
                            slug = re.sub(r"-p\d+$", "", slug, flags=re.I)
                            slug = re.sub(r"^\d+-", "", slug)
                            slug_title = slug.replace("-", " ").strip()
                            if len(slug_title) >= 8:
                                title = slug_title[:160]
                            else:
                                n_skip += 1
                                continue

                        exclude_words = [
                            w.lower() for w in (self.spec.get("title_exclude") or [])
                        ]
                        hay = f"{title} {link} {card_text}".lower()
                        if exclude_words and any(w in hay for w in exclude_words):
                            n_skip += 1
                            continue

                        prix = _best_price(card_text, text, price_re)

                        if apply_filters and not _matches_filters(
                            title, prix, keywords, price_max
                        ):
                            n_filter += 1
                            continue

                        if keywords is not None and not apply_filters:
                            if not _matches_filters(title, prix, keywords, price_max):
                                n_filter += 1
                                continue

                        # Category catalogs (no brand keywords): still enforce price ceiling
                        if job.get("price_only") and price_max < float("inf"):
                            if not _price_within_max(prix, price_max):
                                n_price += 1
                                continue

                        # Description: up to ~3 short lines from card text without title/price
                        desc = card_text or text
                        if title and desc.lower().startswith(title.lower()):
                            desc = desc[len(title) :].strip()
                        if prix and prix in desc:
                            desc = desc.replace(prix, "").strip()
                        desc = re.sub(
                            r"\b(Add to Cart|Add to Wishlist|Quick View|Buy Now|NEW!)\b",
                            "",
                            desc,
                            flags=re.I,
                        )
                        desc = re.sub(r"\s+", " ", desc).strip()[:280]

                        if is_sold_listing(title, prix, desc, card_text):
                            n_sold += 1
                            continue

                        if not FILTERS.get("include_mouthpieces") and is_mouthpiece_listing(
                            title, desc, card_text, link
                        ):
                            n_skip += 1
                            continue

                        if not FILTERS.get("include_ligatures") and is_ligature_listing(
                            title, desc, card_text, link
                        ):
                            n_skip += 1
                            continue

                        image = (entry.get("image") or "").strip()
                        if image.startswith("//"):
                            image = "https:" + image

                        seen.add(item_id)
                        self.pending_seen.append(item_id)
                        results.append(
                            {
                                "titre": title,
                                "prix": prix or "N/A",
                                "lien": link,
                                "image": image,
                                "description": desc,
                            }
                        )
                        added += 1
                        self.stats["ok"] += 1
                        print(f"   [{added}] {title[:55]}… | {prix}")

                    self.stats["seen"] += n_seen
                    self.stats["filter"] += n_filter
                    self.stats["price"] += n_price
                    self.stats["sold"] += n_sold
                    self.stats["skip"] += n_skip
                    if added == 0 and candidates:
                        print(
                            f"   (skip: déjà vus={n_seen}, filtre={n_filter}, "
                            f"prix={n_price}, vendu={n_sold}, autre={n_skip})"
                        )
            finally:
                ctx.close()
                browser.close()
                # Seen persisted by main.py after successful listings merge

        print(f"\n✅ {label}: {len(results)} nouvelles annonces")
        return results
