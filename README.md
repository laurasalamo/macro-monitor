# Macro Monitor

A personal, free-to-run macro-economics dashboard, inspired by alphamarkettools.com/macro.
Static site (no backend) + a Python script that pulls data from FRED (and Yahoo Finance for gold and ETF prices),
refreshed automatically once a day via GitHub Actions.

## Sections

Regime Dashboard (7 indicators rated bullish / neutral / bearish, thresholds in
`scripts/regime_logic.py`; click a card for its full FRED history), Credit Spreads, Inflation Expectations (incl. 5Y TIPS yield), Liquidity &
Financial Conditions, Yield Curve Shape, Growth & Labor Market, Cross-Asset, Treasury Spreads,
Momentum Composite (ETF ranking).

## One-time setup

1. **Get a free FRED API key**: https://fred.stlouisfed.org/docs/api/api_key.html (instant signup).
2. **Local env**: `cp .env.example .env` and paste your key in as `FRED_API_KEY=...`.
3. **Install Python deps**:
   ```
   pip install -r scripts/requirements.txt
   ```
4. **Run the fetch script** to generate `data/data.json`:
   ```
   python scripts/fetch_data.py
   ```
   Watch the console output — it logs each series as it's fetched, and prints warnings for
   any series that failed (e.g. a bad ID or a temporary FRED outage) without stopping the run.
5. **Serve the site locally**:
   ```
   python -m http.server 8000
   ```
   Open http://localhost:8000 and check each section renders with real numbers and charts.

## Deploying (GitHub Pages + GitHub Actions)

1. Create a GitHub repo and push this project to it.
2. In the repo settings, add a secret named `FRED_API_KEY` (Settings → Secrets and variables →
   Actions → New repository secret).
3. Enable GitHub Pages: Settings → Pages → Source: "Deploy from a branch" → Branch: `main` / `/ (root)`.
4. Manually trigger the workflow once to generate the first `data/data.json`: Actions tab →
   "Update Macro Data" → Run workflow.
5. After it completes and pushes, your Pages URL will show the live dashboard. It refreshes
   automatically every day (`.github/workflows/update-data.yml`, ~8-9am US Eastern).

## Project layout

```
index.html, css/, js/       frontend (no build step, Chart.js via CDN)
scripts/                    Python fetch pipeline
  series_config.py          metric -> FRED series ID mapping (single source of truth)
  fred_client.py            FRED REST API wrapper
  gold_client.py            Yahoo Finance fetch via yfinance (gold, GC=F)
  transforms.py             YoY / MoM-change / diff / staleness helpers
  regime_logic.py           rule-based regime classification
  fetch_data.py             orchestrator - run this to refresh data/*.json
data/data.json, meta.json   generated output the frontend reads
.github/workflows/          daily cron that runs fetch_data.py and commits the result
```

## Customizing

- Add/swap a metric: edit `scripts/series_config.py` (fetch side) and `js/config.js`
  (display side) - both are simple config, not code changes.
- Adjust regime thresholds or lookback windows: named constants at the top of
  `scripts/regime_logic.py`.
- Adjust staleness thresholds: `STALE_THRESHOLD_DAYS` in `scripts/series_config.py`.

## Momentum Composite

A cross-sectional ranking of ~30 ETFs (broad market, sectors, themes, regions, commodities),
scored 0-100 and re-ranked on every run:

- **Trend (45%)** - a blend of 1M/3M/6M/12M returns, weighted toward the intermediate term.
- **Acceleration (15%)** - the current 3-month return vs. the 3-month return as of 3 months ago
  (is momentum speeding up or fading?).
- **Proximity to 52-week high (25%)** - how close the price is to its trailing-year high.
- **Low volatility (15%)** - inverse of trailing 3-month annualized volatility.

Each raw signal is converted to a 0-100 percentile rank *within that day's universe* before
being weighted into the composite - so the score is a relative ranking ("leader vs. laggard
today"), not an absolute forecast. Prices/volume come from Yahoo Finance (via yfinance, same free source as gold),
so the same "directionally accurate, not tick-perfect" caveat applies.

This is an original, fully transparent scoring method inspired by the general shape of
commercial momentum-ranking dashboards, not a reproduction of any specific provider's
undisclosed formula - treat it as one lens, not investment advice.

- Add/remove ETFs: edit `UNIVERSE` in `scripts/momentum_config.py`.
- Adjust weights or lookback windows: named constants at the top of the same file.

## Notes on data sources

- Everything except Gold comes from FRED, an official, free source.
- Gold (USD/oz) isn't on FRED, so it's pulled from Yahoo Finance (COMEX futures, GC=F) via yfinance - no API key needed,
  but it's a less "official" source than FRED, so treat it as directionally accurate rather
  than tick-perfect.
- The "Broad Dollar Index" card uses FRED's `DTWEXBGS` (trade-weighted broad dollar index),
  which tracks the same direction as the headline ICE DXY but isn't constructed identically,
  so the number won't exactly match "DXY ~100" style headlines.
