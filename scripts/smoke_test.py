"""Quick reachability check for Audi TT search pages."""

from __future__ import annotations

import sys
from urllib.request import Request, urlopen

URLS = [
    "https://www.lacentrale.fr/listing?makesModelsCommercialNames=AUDI%3ATT&yearMin=2006&yearMax=2010",
    "https://www.leboncoin.fr/recherche?category=2&text=audi%20tt",
    "https://www.autoscout24.fr/lst/audi/tt?fregfrom=2006&fregto=2010",
    "https://www.paruvendu.fr/a/voiture/audi/tt",
]


def main() -> int:
    ok = 0
    for url in URLS:
        try:
            req = Request(url, headers={"User-Agent": "auditt-smoke/1.0"})
            with urlopen(req, timeout=20) as resp:
                code = getattr(resp, "status", 200)
                print(f"OK {code} {url}")
                ok += 1
        except Exception as e:
            print(f"FAIL {url}: {e}")
    print(f"{ok}/{len(URLS)} reachable")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
