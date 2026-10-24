# Crimson Calculus

**Online demo:** https://crimson-calculus.onrender.com

The online demo is open without a website login. No Python installation is needed.

Roulette Odds, Strategy & Risk. Compare betting systems under session limits, follow the next wager, practice with virtual money, and ask Vivienne for help. The numerical calculator uses fixed probability rules; the AI explains results and can request controlled settings changes. No real bets are placed.

## Online demo

The shared demo is publicly accessible. The first visit after inactivity can take a minute to wake the free server. This repository contains app source, bundled artwork/data and software tests. Class reports and saved AI/session/diagnostic evidence are kept separately.

## Run locally

Requires Python 3.11 or newer. From this folder:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python setup_check.py
python app.py
```

Open http://127.0.0.1:8069. The calculator and practice modes work without an AI key. Vivienne uses `PORTKEY_API_KEY`, with an optional `OPENAI_API_KEY` fallback. The app loads `.env` from its own folder first and then the parent folder, without overriding existing process environment values. `.env.example` lists empty placeholders. Never commit actual credentials.

After setup, Mac users can double-click `Start Crimson Calculus.command`. Run automated Python checks with `python -m unittest discover -s tests -v`.

## Render Free deployment

Connect this private GitHub repository in Render using New → Blueprint. The supplied `render.yaml` declares one **Free** Python web service and no paid storage/database. Its build command installs requirements; `gunicorn -c gunicorn.conf.py wsgi:server` runs the production server, and `/health` is its health probe.

Set `PORTKEY_API_KEY` using Render’s secret Environment settings. The blueprint sets `CRIMSON_PUBLIC_DEMO=1`, so visitors can open the website without a password. Anyone with the link can use Vivienne within the shared AI limits. The API key stays server-side. To restore the optional website login, set `CRIMSON_PUBLIC_DEMO=0`; the existing generated `CRIMSON_DEMO_PASSWORD` and username `guest` then apply. Always use the HTTPS live URL.

`CRIMSON_HOSTED_DEMO=1` selects the small-server profile: one process, serialized large calculations, smaller caches, at most 600 loss-plus-target chips and 500 maximum-wager chips, and lower compute/memory search limits. Skipped bet families are shown in notices; supported searches are computed completely. Without this flag, the local app retains its larger limits.

Vivienne’s online allowance is shared: 30 messages per rolling 24 hours plus existing token, per-minute and tool limits. Render Free can sleep after 15 minutes without traffic and take about a minute to wake. Its temporary server files—including usage records—can reset after sleep/restarts. The allowance is therefore **not a durable spending cap**; monitor the provider account and restore the optional login if needed. Browser autosaves remain in each visitor’s browser.

Hosting can be free while AI-provider usage is billed separately. Official references: https://render.com/docs/free and https://render.com/docs/deploy-flask.
