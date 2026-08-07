# AudiTT — scrape local (surtout La Centrale / IP box).
# Logique commune: scrapekit/scripts/run_local_project.ps1
# Pour lancer les deux apps: scrapekit/scripts/run_both_local.ps1
#
# Planifier: Task Scheduler → ce script 1x/jour, ou run_both_local.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Shared = Join-Path (Split-Path -Parent $Root) "scrapekit\scripts\run_local_project.ps1"
if (-not (Test-Path $Shared)) {
  throw "scrapekit introuvable: $Shared — clone github.com/palascal/scrapekit next to this repo"
}

& $Shared `
  -AppRoot $Root `
  -KvNamespaceId "f97d5c9cb30b4b45a064af57102f396a" `
  -BrowserProfileEnv "AUDIT_BROWSER_PROFILE" `
  -SkipResidentialEnv "AUDIT_SKIP_RESIDENTIAL" `
  -Label "AudiTT"
