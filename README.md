# AKKO Portfolio Instagram Benchmark

Local Streamlit dashboard that scrapes 4 public AKKO brand Instagram accounts daily via `instaloader`, stores post and follower data in SQLite, and produces head-to-head benchmark scores (Content Velocity, Engagement Quality, Growth Momentum) with rule-based recommendations. No API tokens, no login, no external services.

## Install

```bash
pip install -r requirements.txt
```

## Seed the database

```bash
python scraper.py
```

## Launch the dashboard

```bash
streamlit run dashboard.py
```

## Daily refresh

When the Streamlit app is running, `apscheduler` triggers a scrape automatically at 04:00 Africa/Casablanca time.

For OS-level cron (when the app is not running), add to crontab (`crontab -e`):

```
0 4 * * * cd /path/to/akko-ig-dash && python scraper.py >> logs/cron.log 2>&1
```

## Notes

- **Rate limits**: if scrapes fail with `TooManyRequestsException`, pause for 24 hours and consider switching to every-other-day scraping.
- **Growth Momentum score**: requires 14+ days of accumulated daily snapshots. The radar chart shows 2 axes until that threshold is reached.
- **Out of scope by design**: reach, impressions, saves, shares, story metrics, audience demographics. These require the Meta Graph API. Export from Meta Business Suite manually if needed.
