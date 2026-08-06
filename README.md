# AudiTT — annonces Audi TT (vente)

Dashboard Cloudflare Pages + scrape cron GitHub Actions (1×/jour).

Moteur partagé : [`palascal/scrapekit`](https://github.com/palascal/scrapekit) (Leboncoin IMAP, Playwright, store, runner).  
UI, filtres année/moteur et sites auto restent dans ce repo.

## Secrets GitHub (mêmes valeurs que saxbot pour IMAP / Cloudflare)

`IMAP_EMAIL_ACCOUNT`, `IMAP_EMAIL_PASSWORD`, `IMAP_SERVER`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

## Sites

| Site | Où ça tourne | Note |
|------|----------------|------|
| AutoScout24 | GitHub Actions | OK depuis le cloud |
| ParuVendu | GitHub Actions | OK depuis le cloud |
| Leboncoin | GitHub Actions / local | Alertes e-mail → IMAP (pas de scrape web) |
| La Centrale | **PC local** | DataDome bloque les IP datacenter |

## Anti-bot (1 scrape / jour)

Leboncoin lit les **alertes mail** (IMAP), comme saxbot — plus de DataDome. Pour La Centrale, **une IP box/fibre** reste nécessaire.

1. **Cloud (automatique)** — cron quotidien `06:00 UTC` : AutoScout24 + ParuVendu + Leboncoin mail (`AUDIT_SKIP_RESIDENTIAL=1` saute La Centrale).
2. **Maison (recommandé pour La Centrale)** — Task Scheduler une fois par jour :

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\coincoin\Documents\AudiTT\scripts\run_daily_local.ps1
```

Le script utilise un profil Chrome persistant (`data/browser_profile`) pour La Centrale, puis pousse les listings dans Cloudflare KV.

Pour Leboncoin : crée une alerte e-mail sur leboncoin.fr (Audi TT 2006–2010) vers la même boîte que `IMAP_EMAIL_ACCOUNT`.

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

Secrets GitHub : `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, et pour Leboncoin `IMAP_EMAIL_ACCOUNT` / `IMAP_EMAIL_PASSWORD` / `IMAP_SERVER`.
Telegram : `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`.
