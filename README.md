# AudiTT — annonces Audi TT (vente)

Dashboard Cloudflare Pages + scrape cron GitHub Actions.

## Sites

- [La Centrale](https://www.lacentrale.fr)
- [Leboncoin](https://www.leboncoin.fr) (voitures)
- [AutoScout24](https://www.autoscout24.fr)
- [ParuVendu](https://www.paruvendu.fr)

## Config

Année (curseur min/max), motorisations 2006–2010 (1.8 TFSI, 2.0 TFSI, 2.0 TDI, 3.2 V6, TTS, TT RS), prix max, sites on/off.

## Local

```bash
cd src
python main.py
```

Ouvre `docs/index.html` ou déploie Pages.

## Deploy

```bash
npx wrangler pages deploy docs --project-name=auditt
```

Secrets GitHub : `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`.
Telegram désactivé tant que tu n’ajoutes pas un bot **dédié** AudiTT (`TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`).
