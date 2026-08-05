from pathlib import Path
import re

pv = Path(r"C:\Users\coincoin\Documents\AudiTT\data\probe_paruvendu.html").read_text(encoding="utf-8", errors="ignore")
# look for price + title patterns
for pat in [
    r'href="([^"]*annonce[^"]*)"',
    r'href="([^"]*-\d{7,}[^"]*)"',
    r'data-id="([^"]+)"',
    r'idAnnonce["\s:=]+(\d+)',
    r'/a/[^"]+\d{6,}',
]:
    found = re.findall(pat, pv, flags=re.I)
    print(pat, len(found), found[:8])

# dump snippets around euro prices
for m in re.finditer(r'.{80}\d[\d\s]{2,}\s*€.{80}', pv):
    print("PRICECTX", m.group(0).replace("\n"," ")[:200])
    break

# check for empty results message
for needle in ("Aucune annonce", "0 annonce", "pas d'annonce", "résultat", "Resultats", "résultats"):
    if needle.lower() in pv.lower():
        idx = pv.lower().find(needle.lower())
        print("MSG", needle, pv[idx:idx+120].replace("\n"," "))
