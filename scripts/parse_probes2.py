from pathlib import Path
import re
import json

as24 = Path(r"C:\Users\coincoin\Documents\AudiTT\data\probe_autoscout24.html").read_text(encoding="utf-8", errors="ignore")
print("offres count", as24.lower().count("/offres/"))
# JSON-LD urls
for m in re.finditer(r'"url"\s*:\s*"([^"]+)"', as24):
    u = m.group(1).encode().decode("unicode_escape")
    if "offres" in u or "offre" in u:
        print("jsonld", u[:160])

# article cards
for pat in [r'href="(/offres/[^"]+)"', r'href="(https://www\.autoscout24\.fr/offres/[^"]+)"', r'data-item-id="([^"]+)"']:
    found = re.findall(pat, as24)
    print(pat, len(found), found[:5])

pv = Path(r"C:\Users\coincoin\Documents\AudiTT\data\probe_paruvendu.html").read_text(encoding="utf-8", errors="ignore")
print("\nparuvendu samples with digits:")
hrefs = re.findall(r'href="([^"]+)"', pv)
ads = [h for h in hrefs if re.search(r"\d{5,}", h) and "voiture" in h.lower()]
print("ads", len(ads))
for h in ads[:20]:
    print(h[:160])
# other patterns
for h in hrefs:
    if "tt" in h.lower() and ("annonce" in h.lower() or "occasion" in h.lower() or re.search(r"-\d{6,}", h)):
        print("cand", h[:160])
