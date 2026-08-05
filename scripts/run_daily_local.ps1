# AudiTT — scrape quotidien depuis ton PC (IP résidentielle).
# Contourne DataDome sur La Centrale / Leboncoin sans flooder (1x/jour).
#
# Prérequis: Python 3.11+, pip install -r requirements.txt, playwright install chromium
#
# Planifier: Task Scheduler Windows → déclencher ce script tous les jours ~8h.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$env:PYTHONUNBUFFERED = "1"
$env:PYTHONIOENCODING = "utf-8"
# Ne PAS skipper les sites résidentiels
Remove-Item Env:AUDIT_SKIP_RESIDENTIAL -ErrorAction SilentlyContinue
$env:AUDIT_BROWSER_PROFILE = Join-Path $Root "data\browser_profile"

Write-Host "AudiTT local scrape (profile=$env:AUDIT_BROWSER_PROFILE)"
Set-Location (Join-Path $Root "src")
python -u main.py

# Publier listings vers KV Cloudflare si wrangler est dispo
Set-Location $Root
if (Get-Command npx -ErrorAction SilentlyContinue) {
  Write-Host "Publish listings to Cloudflare KV..."
  npx --yes wrangler@3 kv key put --namespace-id=f97d5c9cb30b4b45a064af57102f396a listings_v1 --path=docs/data/listings.json
} else {
  Write-Host "npx/wrangler absent — commit/push docs/data/listings.json a la main ou via git."
}
