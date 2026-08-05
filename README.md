# AudiTT — annonces Audi TT (vente)

Dashboard Cloudflare Pages + scrape cron GitHub Actions (1×/jour).

## Sites

| Site | Où ça tourne | Note |
|------|----------------|------|
| AutoScout24 | GitHub Actions | OK depuis le cloud |
| ParuVendu | GitHub Actions | OK depuis le cloud |
| La Centrale | **PC local** | DataDome bloque les IP datacenter |
| Leboncoin | **PC local** | idem |

## Anti-bot (1 scrape / jour)

Pas besoin de flooder ni de proxy payant : **une IP box/fibre** passe bien mieux que GitHub Actions.

1. **Cloud (automatique)** — cron quotidien `06:00 UTC` : AutoScout24 + ParuVendu uniquement (`AUDIT_SKIP_RESIDENTIAL=1`).
2. **Maison (recommandé pour La Centrale / Leboncoin)** — Task Scheduler une fois par jour :

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\coincoin\Documents\AudiTT\scripts\run_daily_local.ps1
```

Le script utilise un profil Chrome persistant (`data/browser_profile`) puis pousse les listings dans Cloudflare KV.

Alternative plus lourde : proxy résidentiel payant branché sur Actions — inutile si le PC tourne déjà 1×/jour.

## Config

Année (curseur min/max), motorisations 2006–2010 (1.8 TFSI, 2.0 TFSI, 2.0 TDI, 3.2 V6, TTS, TT RS), prix max, sites on/off.

## Local manuel

```bash
cd src
python main.py
```

## Deploy

```bash
npx wrangler pages deploy docs --project-name=auditt
```

Secrets GitHub : `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`.
Telegram désactivé tant que tu n’ajoutes pas un bot **dédié** AudiTT (`TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`).
