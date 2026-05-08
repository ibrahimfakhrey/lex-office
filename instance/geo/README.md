# GeoIP DB for market detection

This directory holds the offline IP-to-country DB used by `app/utils/market.py`
to silently detect EG vs SA visitors.

## Current file
`dbip-country-lite.mmdb` — committed to the repo so the app works on every
deploy without external setup. ~8 MB unpacked, ~99% accurate at country level.

## Attribution (required by license)
This product includes IP-to-Country data created by **DB-IP.com** and
distributed under the **Creative Commons Attribution 4.0** license.

Source: <https://db-ip.com/db/download/ip-to-country-lite>

## Refresh schedule
DB-IP rebuilds the lite DB monthly. To pick up new IP ranges:

```sh
cd instance/geo
curl -fsSL -o dbip-country-lite.mmdb.gz \
  "https://download.db-ip.com/free/dbip-country-lite-$(date +%Y-%m).mmdb.gz"
gunzip -f dbip-country-lite.mmdb.gz
git add dbip-country-lite.mmdb
git commit -m "chore: refresh GeoIP DB"
```

A monthly cron is fine but not required — country-level IP allocations are
stable enough that running this every 3-6 months is sufficient.

## What happens without the DB
The app starts fine. Detection falls through to:
1. `CF-IPCountry` header (if Cloudflare is in front)
2. `Accept-Language` (`ar-SA` / `ar-EG`)
3. Default market (`eg`)

The reader is opened lazily on first lookup, so dropping a new file in does
not require a restart beyond a worker reload.
