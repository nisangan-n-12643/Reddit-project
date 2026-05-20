# Reddit Scout

Hourly bot that scans tech subreddits for discussion-worthy threads and posts them to a Zoho Cliq channel.

## What it does

- Polls 19 subreddits (`r/msp`, `r/sysadmin`, `r/aws`, `r/docker`, `r/cybersecurity`, …) once an hour via Reddit's public JSON API.
- Scores each new post against keyword/title-pattern rules tuned from your participation history (MSP tooling, M365/Azure, backup/DR, networking, security, Docker/Hyper-V, automation).
- Posts qualifying threads to Zoho Cliq as: `🧵 <link>` + a 2-line topic summary.
- Deduplicates via `state/seen.json` (14-day TTL), committed back to the repo by GitHub Actions.

## Setup

### 1. Create the Zoho Cliq webhook

1. In Cliq, open the target channel/group → **•••** → **Integrations** → **Incoming Webhooks**.
2. Name it `Reddit Scout`, save, copy the webhook URL.

### 2. Push this folder to a new private GitHub repo (in your org)

```bash
cd /Users/nisan-12643/Documents/reddit/reddit-scout
git init -b main
git add .
git commit -m "Initial: Reddit Scout"
git remote add origin git@github.com:<your-org>/reddit-scout.git
git push -u origin main
```

### 3. Add the webhook as a repo secret

GitHub → repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:
- Name: `ZOHO_CLIQ_WEBHOOK_URL`
- Value: (paste the Cliq webhook URL)

### 4. Enable Actions

GitHub → **Actions** tab → enable workflows. The schedule (`cron: '0 * * * *'`) will run hourly. You can also trigger manually via **Run workflow** on the `Reddit Scout` workflow.

## Local testing

```bash
cd /Users/nisan-12643/Documents/reddit/reddit-scout
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Dry run — prints matches, posts nothing
DRY_RUN=1 LOOKBACK_MINUTES=360 python scout.py

# Real run
export ZOHO_CLIQ_WEBHOOK_URL='https://cliq.zoho.com/...'
python scout.py
```

## Tuning

- **Subreddits**: edit `SUBREDDITS` in `filters.py`.
- **Keywords / title patterns / exclusions**: edit `TOPIC_KEYWORDS`, `TITLE_PATTERNS`, `EXCLUDE_PATTERNS` in `filters.py`.
- **Strictness**: bump `MIN_SCORE` in `scout.py` (default `2`) up to `3` for fewer/higher-quality hits.
- **Frequency**: change the `cron` in `.github/workflows/scout.yml`.

## Files

| Path | Purpose |
|---|---|
| `scout.py` | Main entry point. |
| `filters.py` | Subreddit list + scoring rules. |
| `state/seen.json` | Posted-thread dedup store. |
| `.github/workflows/scout.yml` | Hourly GitHub Actions cron. |
| `.env.example` | Local env template. |
