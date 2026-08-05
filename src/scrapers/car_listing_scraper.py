"""Playwright scraper for French Audi TT car classifieds."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

from scrapers.base_scraper import BaseScraper
from site_registry import SITE_SPECS
from utils.filters import (
    extract_posted_date,
    extract_year,
    listing_matches_car_filters,
)
from utils.listing_status import is_sold_listing
from utils.price import price_within_max_eur
from utils.seen import load_seen

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _price_to_float(prix_str: str) -> float | None:
    if not prix_str:
        return None
    raw = prix_str.replace("\xa0", " ").strip()
    cleaned = re.sub(r"[^\d.,\s]", "", raw)
    cleaned = re.sub(r"\s+", "", cleaned)
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned and cleaned.rfind(",") > cleaned.rfind("."):
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned and "." not in cleaned:
        cleaned = cleaned.replace(",", ".") if re.search(r",\d{2}$", cleaned) else cleaned.replace(",", "")
    try:
        return float(re.findall(r"\d+(?:\.\d+)?", cleaned)[-1])
    except (IndexError, ValueError):
        return None


def _best_price(blob: str) -> str:
    matches = re.findall(
        r"(?<!\d)\d(?:[\s\u00a0]\d{3})+(?:[.,]\d{2})?\s*€"
        r"|(?<!\d)\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{2})?\s*€"
        r"|(?<!\d)\d{3,6}\s*€"
        r"|€\s?\d[\d\s.,]*",
        blob or "",
    )
    scored = []
    for i, m in enumerate(matches):
        val = _price_to_float(m)
        if val is not None and 500 <= val <= 200_000:
            scored.append((val, i, m.strip()))
    if scored:
        return scored[-1][2]
    return matches[-1].strip() if matches else "N/A"


def _best_image(card) -> str:
    try:
        for sel in ("img[src]", "img[data-src]", "img[srcset]"):
            img = card.query_selector(sel)
            if not img:
                continue
            src = img.get_attribute("src") or img.get_attribute("data-src") or ""
            if not src and img.get_attribute("srcset"):
                src = (img.get_attribute("srcset") or "").split(",")[0].strip().split(" ")[0]
            if src and src.startswith("http") and "data:image" not in src:
                return src
            if src and src.startswith("//"):
                return "https:" + src
    except Exception:
        pass
    return ""


class CarListingScraper(BaseScraper):
    def __init__(
        self,
        site_key: str,
        query_jobs=None,
        url=None,
        headless=True,
        max_results=50,
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
        self.stats = {"seen": 0, "filter": 0, "price": 0, "sold": 0, "skip": 0, "ok": 0}

    def _normalize_link(self, href: str) -> str | None:
        if not href:
            return None
        href = href.split("#")[0].split("?")[0]
        base = self.spec.get("base_url") or ""
        if href.startswith("/"):
            href = urljoin(base + "/", href.lstrip("/"))
        substr = self.spec.get("link_substr") or ""
        if substr and substr not in href:
            return None
        if not href.startswith("http"):
            return None
        return href

    def fetch_listings(self):
        seen = self._load_seen()
        results = []
        price_re = re.compile(self.spec.get("price_regex") or r"\d+\s*€")
        link_substr = self.spec.get("link_substr") or ""
        wait_sel = self.spec.get("wait_selector") or f"a[href*='{link_substr}']"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent=_DEFAULT_UA,
                locale="fr-FR",
                viewport={"width": 1400, "height": 900},
            )
            page = context.new_page()

            for job in self._jobs:
                url = job.get("url")
                if not url:
                    continue
                price_max = float(job.get("price_max") or float("inf"))
                year_min = job.get("year_min")
                year_max = job.get("year_max")
                engines = job.get("engines")
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(1800)
                    try:
                        page.wait_for_selector(wait_sel, timeout=12000)
                    except Exception:
                        pass
                    # Cookie banners
                    for label in ("Accepter", "Tout accepter", "Accept", "J'accepte"):
                        try:
                            btn = page.get_by_role("button", name=re.compile(label, re.I))
                            if btn.count():
                                btn.first.click(timeout=1500)
                                page.wait_for_timeout(400)
                        except Exception:
                            pass
                except Exception as e:
                    print(f"   ⚠️ {self.spec.get('label')}: navigation {e}")
                    continue

                anchors = page.query_selector_all(f"a[href*='{link_substr}']")
                seen_hrefs = set()
                for a in anchors:
                    if len(results) >= self.max_results:
                        break
                    try:
                        href = a.get_attribute("href") or ""
                        link = self._normalize_link(href)
                        if not link or link in seen_hrefs:
                            continue
                        seen_hrefs.add(link)
                        if link in seen:
                            self.stats["seen"] += 1
                            continue

                        card = a
                        for _ in range(4):
                            parent = card.evaluate_handle("el => el.closest('article, li, div')")
                            try:
                                card = parent.as_element() or card
                            except Exception:
                                break
                        card_text = ""
                        try:
                            card_text = card.inner_text(timeout=1000) if card else ""
                        except Exception:
                            card_text = a.inner_text() if a else ""

                        title = (card_text or "").strip().split("\n")[0].strip()
                        if len(title) < 5:
                            title = (a.get_attribute("title") or a.inner_text() or "Audi TT").strip()
                        title = re.sub(r"\s+", " ", title)[:180]

                        prix = _best_price(card_text)
                        if prix == "N/A":
                            m = price_re.search(card_text or "")
                            prix = m.group(0).strip() if m else "N/A"

                        posted = extract_posted_date(card_text)
                        year = extract_year(card_text) or extract_year(title)
                        image = _best_image(card) if card else ""

                        item = {
                            "id": link,
                            "site": self.site_key,
                            "site_label": self.spec.get("label", self.site_key),
                            "titre": title,
                            "prix": prix,
                            "lien": link,
                            "image": image,
                            "description": "",
                            "year": year,
                            "posted_at": posted,
                            "found_at": datetime.now(timezone.utc).isoformat(),
                        }

                        if is_sold_listing(title, prix, card_text):
                            self.stats["sold"] += 1
                            continue
                        if not listing_matches_car_filters(
                            title,
                            prix,
                            description=card_text,
                            link=link,
                            year_min=year_min,
                            year_max=year_max,
                            engines=engines,
                            price_max=price_max,
                        ):
                            self.stats["filter"] += 1
                            continue
                        if not price_within_max_eur(prix, price_max):
                            self.stats["price"] += 1
                            continue

                        results.append(item)
                        self.pending_seen.append(link)
                        self.stats["ok"] += 1
                    except Exception:
                        self.stats["skip"] += 1
                        continue

            browser.close()

        print(
            f"   ✅ {self.spec.get('label')}: {self.stats['ok']} ok "
            f"(seen={self.stats['seen']} filter={self.stats['filter']})"
        )
        return results

    def _load_seen(self):
        return load_seen(self.cache_file)
