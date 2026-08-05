from pathlib import Path
import re

for name in ("autoscout24", "paruvendu", "lacentrale", "leboncoin"):
    p = Path(rf"C:\Users\coincoin\Documents\AudiTT\data\probe_{name}.html")
    if not p.exists():
        print(name, "missing")
        continue
    html = p.read_text(encoding="utf-8", errors="ignore")
    hrefs = re.findall(r'href="([^"]+)"', html)
    print("\n==", name, "links", len(hrefs), "html", len(html))
    interesting = []
    for h in hrefs:
        hl = h.lower()
        if any(x in hl for x in ("/offres/", "/annonces/", "/ad/", "annonce", "/a/voiture", "/auto-occasion", "detail")):
            if h not in interesting:
                interesting.append(h)
    print("interesting", len(interesting))
    for h in interesting[:15]:
        print(" ", h[:150])
    # status clues
    for needle in ("403", "captcha", "datadome", "cloudflare", "Access Denied", "Just a moment"):
        if needle.lower() in html.lower():
            print(" clue:", needle)
