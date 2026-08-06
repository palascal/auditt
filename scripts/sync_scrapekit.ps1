# Optional: refresh a local packages/scrapekit mirror from Documents/scrapekit.
# CI installs from https://github.com/palascal/scrapekit — this is only for offline/dev.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Src = Join-Path (Split-Path -Parent $Root) "scrapekit"
$Dest = Join-Path $Root "packages\scrapekit"
if (-not (Test-Path $Src)) { throw "scrapekit not found at $Src — clone github.com/palascal/scrapekit next to this repo" }
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
robocopy $Src $Dest /E /XD .git __pycache__ .github /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
Write-Host "Synced $Src -> $Dest (optional local vendor)"
