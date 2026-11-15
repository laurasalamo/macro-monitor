# Macro Monitor: where we left off

_Last updated: 2026-11-15. Last pushed commit: `89a9d27`._

- **Live site:** https://laurasalamo.github.io/macro-monitor/
- **Repo:** `laurasalamo/macro-monitor`. Use the **laurasalamo** GitHub account, not gynelab. Check with `gh api user -q .login` before pushing.
- **Working rule:** Claude always asks before pushing.

## What the project is

Macro Monitor is a personal, free-to-run macro-economics dashboard. It's a static GitHub Pages site with no build step.

- **Data:** Python scripts in `scripts/` pull data from FRED and Yahoo Finance and write `data/*.json`.
- **Daily refresh:** `.github/workflows/update-data.yml` refreshes the data every day and commits it.
- **Front end:**
  - `js/config.js` defines the sections.
  - The renderers are in `js/app.js`, `js/breadth.js` and `js/charts.js`.
  - Charts use Chart.js 4.4.4.
- **Cache-busting:** `index.html` loads its files with `?v=YYYYMMDD-N`, currently `20261115-7`. Increase N whenever JS or CSS changes.

## Sections built so far (all live)

1. Macro series from FRED, plus the regime logic.
2. Momentum ETFs.
3. Fear & Greed.
   - We compute it ourselves, because CNN's endpoint returns HTTP 418 to scripts.
   - Each indicator has a "View larger chart" button.
4. Market Breadth: % of S&P 500 stocks above their 20-day average, in the style of TradingView's MMTW. The code is in `scripts/breadth_logic.py`.
5. Breadth Indicators, in `scripts/breadth_indicators.py` and `js/breadth.js`:
   - A/D line
   - ADn line
   - McClellan Oscillator
   - Summation Index / RASI
   - New 52-week highs & lows
   - % above the 20/50/200-day averages, with legend buttons to show or hide each line
   - % within 5% of 52-week highs & lows
   - Volume ratios

## Most recent work (commit 89a9d27)

The breadth charts and texts now follow **amplitudmercado.com**. It's an independent Spanish site built on NYSE data; the NYSE does not run it. Your reference screenshots came from that site.

- **ADn:** a 21-day stochastic of the A/D line, smoothed with a 7-day EMA. Levels at 80 / 50 / 20.
- **% above moving averages:** levels at 60 (strong), 50, 40 (weak) and 10 (extreme oversold). A rise of more than 75 points in under 50 days counts as a "thrust".
- **% within 5% of highs/lows:** levels at 30% and 40%. The site's levels are for all NYSE stocks; for the S&P 500, about 45% is the equivalent.
- **Volume ratios:** up ÷ down and down ÷ up. A line at 9 marks rare, strong days.
- **McClellan:** ±50 levels. **Summation/RASI:** ±500 levels, with ±1,000 as extreme.
- **Theory / How to read it:** the text is an English paraphrase of amplitudmercado's help text.
- **Known difference:** our universe is the 500 current S&P stocks, not all NYSE stocks, so our values differ from the site's. For example, on 2026-11-15 our ADn was 86 and the site's was 52. The shapes over time are similar.

## Open items / ideas

- [ ] Look at the **% Above Moving Averages** chart (four level labels) and the **Volume Ratios** chart (line at 9) on the live site. Check that the labels don't overlap or look cramped. Nobody has checked this yet.
- [ ] Optional: we use today's S&P 500 list for the whole history, which adds survivorship bias. A list of historical members would fix it.

## How to work on it locally

```bash
cd ~/Documents/Trial
python3 -m venv .venv && . .venv/bin/activate
pip install -r scripts/requirements.txt -r scripts/requirements-dev.txt
set -a && . ./.env && set +a      # FRED API key
python -m pytest -q tests         # 147 tests should pass
python scripts/fetch_data.py      # regenerates data/*.json
python3 -m http.server 8765       # then open http://localhost:8765
```

- If `data/meta.json` shows a warning like "breadth: only N/503 tickers priced", Yahoo didn't return every stock. Wait a little and run the fetch again.
- `.env` is gitignored. Never commit it.

## Push routine (after you approve)

1. Run `gh api user -q .login`. It must print `laurasalamo`.
2. Run `git fetch` and `git log HEAD..origin/main`, and pull first if there are new commits from the daily data bot.
3. Commit and push to `main`.
4. Wait for the `pages-build-deployment` run, then check the live site.

## To resume with Claude

Open Claude Code in `~/Documents/Trial` and say something like: _"Read HANDOFF.md and let's continue."_
