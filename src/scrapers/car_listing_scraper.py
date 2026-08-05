"""Playwright scraper for French Audi TT car classifieds."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from urllib.parse import unquote, urljoin

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

_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['fr-FR', 'fr', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = { runtime: {} };
"""


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


def _title_from_slug(path: str) -> str:
    slug = unquote(path.rstrip("/").split("/")[-1])
    slug = re.sub(r"-cat_.*$", "", slug, flags=re.I)
    slug = re.sub(r"-[0-9a-f]{8}-[0-9a-f-]{27,}$", "", slug, flags=re.I)
    words = [w for w in slug.replace("_", "-").split("-") if w]
    title = " ".join(words)
    return re.sub(r"\s+", " ", title).strip().title()[:180] or "Audi TT"


def _decode_json_url(u: str) -> str:
    try:
        return u.encode("utf-8").decode("unicode_escape")
    except Exception:
        return u


def _extract_jsonld_offers(html: str, base_url: str) -> list[dict]:
    """Pull listing URLs (and optional names) from JSON-LD ItemList blocks."""
    out = []
    seen = set()
    for raw in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        flags=re.I | re.S,
    ):
        text = raw.strip()
        if "ItemList" not in text and "offres" not in text and "ListItem" not in text:
            continue
        try:
            data = json.loads(text)
        except Exception:
            # Sometimes multiple objects / loose JSON
            continue
        nodes = data if isinstance(data, list) else [data]
        if isinstance(data, dict) and "@graph" in data:
            nodes = data["@graph"]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            main = node.get("mainEntity") if isinstance(node.get("mainEntity"), dict) else node
            elements = []
            if isinstance(main, dict) and main.get("@type") == "ItemList":
                elements = main.get("itemListElement") or []
            elif node.get("@type") == "ItemList":
                elements = node.get("itemListElement") or []
            for el in elements:
                if not isinstance(el, dict):
                    continue
                url = el.get("url") or ""
                if isinstance(el.get("item"), dict):
                    url = url or el["item"].get("url") or ""
                    name = el["item"].get("name")
                else:
                    name = el.get("name")
                if not url:
                    continue
                url = _decode_json_url(str(url))
                if url.startswith("/"):
                    url = urljoin(base_url, url)
                if url in seen:
                    continue
                seen.add(url)
                out.append({"lien": url, "titre": name or _title_from_slug(url)})
    # Fallback: raw /offres/ paths in HTML (escaped or plain)
    for m in re.finditer(r"(/offres/audi-tt[^\"'\\s<]+)", html, flags=re.I):
        path = _decode_json_url(m.group(1)).split("\\u002F")
        # handle unicode_escape remnants
        path_s = m.group(1)
        path_s = path_s.encode().decode("unicode_escape") if "\\u" in path_s else path_s
        path_s = path_s.split('"')[0].split("'")[0]
        url = urljoin(base_url, path_s)
        if url not in seen and "/offres/" in url:
            seen.add(url)
            out.append({"lien": url, "titre": _title_from_slug(url)})
    return out


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
        self.stats = {
            "seen": 0,
            "filter": 0,
            "price": 0,
            "sold": 0,
            "skip": 0,
            "ok": 0,
            "blocked": 0,
        }

    def _normalize_link(self, href: str) -> str | None:
        if not href:
            return None
        href = href.split("#")[0]
        base = self.spec.get("base_url") or ""
        if href.startswith("/"):
            href = urljoin(base + "/", href.lstrip("/"))
        substrs = self.spec.get("link_substrs") or [self.spec.get("link_substr") or ""]
        substrs = [s for s in substrs if s]
        if substrs and not any(s in href for s in substrs):
            return None
        excludes = self.spec.get("link_exclude") or []
        if any(x in href for x in excludes):
            return None
        link_re = self.spec.get("link_regex")
        if link_re and not re.search(link_re, href):
            return None
        if not href.startswith("http"):
            return None
        return href.split("?")[0]

    def _dismiss_cookies(self, page) -> None:
        for label in (
            "Tout accepter",
            "Accepter tout",
            "Accept all",
            "Accepter",
            "J'accepte",
            "Agree",
            "OK",
        ):
            try:
                btn = page.get_by_role("button", name=re.compile(label, re.I))
                if btn.count():
                    btn.first.click(timeout=1500)
                    page.wait_for_timeout(500)
            except Exception:
                pass

    def _page_blocked(self, page, status: int | None) -> bool:
        if status in {403, 429, 503}:
            return True
        try:
            title = (page.title() or "").lower()
            body = (page.inner_text("body") or "")[:800].lower()
        except Exception:
            return status == 403
        needles = (
            "datadome",
            "captcha",
            "access denied",
            "unusual traffic",
            "vérifiez que vous êtes",
            "please verify",
            "just a moment",
            "cf-browser-verification",
        )
        blob = title + " " + body
        return any(n in blob for n in needles)

    def fetch_listings(self):
        seen = self._load_seen()
        results = []
        link_substrs = self.spec.get("link_substrs") or [self.spec.get("link_substr") or ""]
        link_substrs = [s for s in link_substrs if s]
        wait_sel = self.spec.get("wait_selector") or (
            f"a[href*='{link_substrs[0]}']" if link_substrs else "a[href]"
        )

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                user_agent=_DEFAULT_UA,
                locale="fr-FR",
                timezone_id="Europe/Paris",
                viewport={"width": 1440, "height": 900},
                extra_http_headers={
                    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
                    "Upgrade-Insecure-Requests": "1",
                },
            )
            context.add_init_script(_STEALTH_JS)
            page = context.new_page()

            for job in self._jobs:
                url = job.get("url")
                if not url:
                    continue
                price_max = float(job.get("price_max") or float("inf"))
                year_min = job.get("year_min")
                year_max = job.get("year_max")
                engines = job.get("engines")
                status = None
                try:
                    resp = page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    status = resp.status if resp else None
                    page.wait_for_timeout(2500)
                    self._dismiss_cookies(page)
                    page.wait_for_timeout(1500)
                    try:
                        page.wait_for_selector(wait_sel, timeout=10000)
                    except Exception:
                        pass
                except Exception as e:
                    print(f"   ⚠️ {self.spec.get('label')}: navigation {e}")
                    continue

                if self._page_blocked(page, status):
                    self.stats["blocked"] += 1
                    print(
                        f"   🚫 {self.spec.get('label')}: bloqué anti-bot "
                        f"(HTTP {status}) — DataDome/Captcha"
                    )
                    continue

                candidates: list[dict] = []

                # 1) JSON-LD / regex offers (AutoScout24 etc.)
                if self.spec.get("parse_jsonld"):
                    try:
                        html = page.content()
                        for raw in _extract_jsonld_offers(
                            html, self.spec.get("base_url") or url
                        ):
                            link = self._normalize_link(raw["lien"])
                            if link:
                                candidates.append(
                                    {
                                        "lien": link,
                                        "titre": raw.get("titre") or _title_from_slug(link),
                                        "card_text": raw.get("titre") or "",
                                        "image": "",
                                        "prix": "N/A",
                                    }
                                )
                    except Exception as e:
                        print(f"   ⚠️ JSON-LD parse: {e}")

                # 2) DOM anchors
                anchors = []
                for substr in link_substrs:
                    anchors.extend(page.query_selector_all(f"a[href*='{substr}']"))
                seen_hrefs = set(c["lien"] for c in candidates)
                for a in anchors:
                    try:
                        href = a.get_attribute("href") or ""
                        link = self._normalize_link(href)
                        if not link or link in seen_hrefs:
                            continue
                        seen_hrefs.add(link)
                        card = a
                        for _ in range(4):
                            parent = card.evaluate_handle(
                                "el => el.closest('article, li, div[class*=\"List\"], div[class*=\"item\"]')"
                            )
                            try:
                                card = parent.as_element() or card
                            except Exception:
                                break
                        card_text = ""
                        try:
                            card_text = card.inner_text(timeout=800) if card else ""
                        except Exception:
                            try:
                                card_text = a.inner_text()
                            except Exception:
                                card_text = ""
                        title = (card_text or "").strip().split("\n")[0].strip()
                        if len(title) < 5:
                            title = (
                                a.get_attribute("title")
                                or a.inner_text()
                                or _title_from_slug(link)
                            ).strip()
                        title = re.sub(r"\s+", " ", title)[:180]
                        prix = _best_price(card_text)
                        candidates.append(
                            {
                                "lien": link,
                                "titre": title,
                                "card_text": card_text,
                                "image": _best_image(card) if card else "",
                                "prix": prix,
                            }
                        )
                    except Exception:
                        self.stats["skip"] += 1

                for cand in candidates:
                    if len(results) >= self.max_results:
                        break
                    link = cand["lien"]
                    if link in seen:
                        self.stats["seen"] += 1
                        continue
                    title = cand.get("titre") or _title_from_slug(link)
                    card_text = cand.get("card_text") or title
                    prix = cand.get("prix") or _best_price(card_text)
                    if prix == "N/A":
                        # Price often embedded in AutoScout slug? keep N/A
                        pass
                    posted = extract_posted_date(card_text)
                    year = extract_year(card_text) or extract_year(title) or extract_year(link)
                    item = {
                        "id": link,
                        "site": self.site_key,
                        "site_label": self.spec.get("label", self.site_key),
                        "titre": title,
                        "prix": prix,
                        "lien": link,
                        "image": cand.get("image") or "",
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
                    if prix != "N/A" and not price_within_max_eur(prix, price_max):
                        self.stats["price"] += 1
                        continue
                    results.append(item)
                    self.pending_seen.append(link)
                    self.stats["ok"] += 1

            browser.close()

        print(
            f"   OK {self.spec.get('label')}: {self.stats['ok']} ok "
            f"(seen={self.stats['seen']} filter={self.stats['filter']} "
            f"blocked={self.stats['blocked']})"
        )
        return results

    def _load_seen(self):
        return load_seen(self.cache_file)
