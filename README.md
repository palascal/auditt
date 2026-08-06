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
| Leboncoin | GitHub Actions | Alertes e-mail → IMAP |
| La Centrale | GitHub Actions | Alertes e-mail → IMAP |

## Anti-bot

Leboncoin et La Centrale passent par **alertes mail (IMAP)** — plus de DataDome. AutoScout24 / ParuVendu tournent aussi en cloud.

1. **Cloud (automatique)** — cron quotidien `06:00 UTC` : les 4 sources (`AUDIT_SKIP_RESIDENTIAL` ne saute plus La Centrale).
2. **Maison (optionnel)** — Task Scheduler si tu veux tout relancer en local :

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\coincoin\Documents\AudiTT\scripts\run_daily_local.ps1
```

Ou les deux apps : `scrapekit\scripts\run_both_local.ps1`

Pour Leboncoin / La Centrale : crée une alerte e-mail sur le site → même boîte que `IMAP_EMAIL_ACCOUNT`.

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
