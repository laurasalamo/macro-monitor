#!/usr/bin/env python3
"""Fetch all Macro Monitor data from FRED (+ Yahoo Finance for gold and ETFs) and write
data/data.json + data/meta.json for the static frontend to consume.

Run locally:
    FRED_API_KEY=your_key python scripts/fetch_data.py
or with a .env file next to this script containing FRED_API_KEY=...
"""

import json
import os
import sys
from datetime import date, datetime, timezone

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import momentum_logic as mom
import regime_logic as regime
import transforms as tx
from fred_client import FredError, get_series
from gold_client import GoldFetchError, get_gold_series
from momentum_client import MomentumFetchError, get_ohlcv_series
from momentum_config import UNIVERSE as MOMENTUM_UNIVERSE
from series_config import (
    FRED_SERIES,
    HISTORY_YEARS,
    SCALE,
    STALE_THRESHOLD_DAYS,
    YIELD_CURVE_TENORS,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")


def years_ago_iso(years):
    today = date.today()
    try:
        return today.replace(year=today.year - years).isoformat()
    except ValueError:
        # Feb 29 on a non-leap target year
        return today.replace(month=2, day=28, year=today.year - years).isoformat()


def build_metric(key, cfg, api_key, warnings):
    fred_id, transform, unit, frequency = cfg
    scale = SCALE.get(key, 1.0)
    try:
        raw = get_series(fred_id, api_key)
        parsed = tx.parse_observations(raw)

        if transform == "level":
            series = tx.apply_level(parsed, scale=scale)
        elif transform == "yoy":
            series = tx.apply_yoy(parsed)
        elif transform == "mom_change":
            series = tx.apply_mom_change(parsed, scale=scale)
        else:
            raise ValueError(f"Unknown transform '{transform}' for {key}")

        if not series:
            warnings.append(f"{key} ({fred_id}): no data after transform")
            return None

        latest, delta, as_of = tx.latest_and_delta(series)
        days_since, stale = tx.staleness(as_of, frequency, STALE_THRESHOLD_DAYS)

        years = HISTORY_YEARS.get(key, HISTORY_YEARS["default"])
        history = tx.trim_history(series, years_ago_iso(years))

        return {
            "latest": round(latest, 4) if latest is not None else None,
            "delta": round(delta, 4) if delta is not None else None,
            "as_of": as_of,
            "stale": stale,
            "days_since": days_since,
            "unit": unit,
            "history": [[d, round(v, 4)] for d, v in history],
        }
    except Exception as e:  # keep going on a single bad series
        warnings.append(f"{key} ({fred_id}): {e}")
        return None


def fetch_gold(warnings):
    try:
        series = get_gold_series()
        latest, delta, as_of = tx.latest_and_delta(series)
        days_since, stale = tx.staleness(as_of, "daily", STALE_THRESHOLD_DAYS)
        history = tx.trim_history(series, years_ago_iso(HISTORY_YEARS["default"]))
        return {
            "latest": round(latest, 2) if latest is not None else None,
            "delta": round(delta, 2) if delta is not None else None,
            "as_of": as_of,
            "stale": stale,
            "days_since": days_since,
            "unit": "$",
            "history": [[d, round(v, 2)] for d, v in history],
        }
    except GoldFetchError as e:
        warnings.append(f"gold (yahoo): {e}")
        return None


def fetch_yield_curve(api_key, warnings):
    current, one_year_ago = [], []
    target = years_ago_iso(1)
    for label, fred_id in YIELD_CURVE_TENORS:
        try:
            parsed = tx.parse_observations(get_series(fred_id, api_key))
            if not parsed:
                continue
            current.append([label, parsed[-1][1]])
            past = tx.nearest_point(parsed, target)
            if past:
                one_year_ago.append([label, past[1]])
        except Exception as e:
            warnings.append(f"yield_curve {label} ({fred_id}): {e}")
    return current, one_year_ago


def fetch_spread_2y3m(api_key, warnings):
    try:
        s2 = tx.apply_level(tx.parse_observations(get_series("DGS2", api_key)))
        s3 = tx.apply_level(tx.parse_observations(get_series("DGS3MO", api_key)))
        spread = tx.diff_series(s2, s3)
        if not spread:
            warnings.append("spread_2y3m: no overlapping dates between DGS2 and DGS3MO")
            return None
        latest, delta, as_of = tx.latest_and_delta(spread)
        days_since, stale = tx.staleness(as_of, "daily", STALE_THRESHOLD_DAYS)
        history = tx.trim_history(spread, years_ago_iso(HISTORY_YEARS["default"]))
        return {
            "latest": round(latest, 4) if latest is not None else None,
            "delta": round(delta, 4) if delta is not None else None,
            "as_of": as_of,
            "stale": stale,
            "days_since": days_since,
            "unit": "pp",
            "history": [[d, round(v, 4)] for d, v in history],
        }
    except Exception as e:
        warnings.append(f"spread_2y3m: {e}")
        return None


def fetch_momentum(warnings):
    price_data = {}
    labels = {}
    ok = 0
    for ticker, label, symbol in MOMENTUM_UNIVERSE:
        labels[ticker] = label
        try:
            series = get_ohlcv_series(symbol)
            price_data[ticker] = {
                "closes": [c for _, c, _ in series],
                "volumes": [v for _, _, v in series],
            }
            ok += 1
        except MomentumFetchError as e:
            warnings.append(f"momentum {ticker} ({symbol}): {e}")
    print(f"  -> fetched {ok}/{len(MOMENTUM_UNIVERSE)} tickers from Yahoo Finance")

    rows = mom.build_rankings(price_data)
    for r in rows:
        r["label"] = labels.get(r["ticker"], r["ticker"])
    if not rows:
        warnings.append("momentum: no tickers had enough history to score")
    print(f"  -> scored {len(rows)} tickers")

    return {
        "as_of": date.today().isoformat(),
        "weights": {"trend": 45, "accel": 15, "max": 25, "vol": 15},
        "rows": rows,
    }


def build_regime_section(metrics):
    gdp_hist = (metrics.get("gdp_growth") or {}).get("history", [])
    curve_hist = (metrics.get("spread_10y2y") or {}).get("history", [])
    unemployment_hist = (metrics.get("unemployment") or {}).get("history", [])

    latest_gdp = gdp_hist[-1][1] if gdp_hist else None
    trailing_avg_gdp = regime.trailing_average(
        [v for _, v in gdp_hist[-regime.TREND_LOOKBACK_QUARTERS:]]
    ) if gdp_hist else None
    latest_curve = curve_hist[-1][1] if curve_hist else None
    current_label = regime.classify(latest_gdp, trailing_avg_gdp, latest_curve)

    unemployment_3mo_change = None
    if len(unemployment_hist) >= 4:
        unemployment_3mo_change = unemployment_hist[-1][1] - unemployment_hist[-4][1]

    bullish_count, bullish_total = regime.bullish_scorecard(
        (metrics.get("spread_10y2y") or {}).get("latest"),
        (metrics.get("spread_2y3m") or {}).get("latest"),
        latest_gdp,
        unemployment_3mo_change,
        (metrics.get("payrolls_mom") or {}).get("latest"),
        (metrics.get("cpi_yoy") or {}).get("latest"),
    )

    # Trailing 36-month regime history: one classification per calendar month,
    # holding the latest-known GDP quarter constant across the months within it.
    curve_by_month = {}
    for d, v in curve_hist:
        curve_by_month[d[:7]] = v  # series is ascending, so this keeps the month's last value
    months = sorted(curve_by_month.keys())[-regime.TRAILING_MONTHS:]

    monthly_points = []
    for ym in months:
        gdp_values_to_date = [v for d, v in gdp_hist if d[:7] <= ym]
        g = gdp_values_to_date[-1] if gdp_values_to_date else None
        trailing = regime.trailing_average(
            gdp_values_to_date[-regime.TREND_LOOKBACK_QUARTERS:]
        ) if gdp_values_to_date else None
        monthly_points.append((ym, g, trailing, curve_by_month[ym]))

    trailing_counts = regime.trailing_36mo_regime_counts(monthly_points)

    return {
        "current_label": current_label,
        "bullish_count": bullish_count,
        "bullish_total": bullish_total,
        "trailing_36mo_counts": trailing_counts,
        "snapshot_cards": {
            "gdp_growth": metrics.get("gdp_growth"),
            "cpi_yoy": metrics.get("cpi_yoy"),
            "unemployment": metrics.get("unemployment"),
            "payrolls_mom": metrics.get("payrolls_mom"),
            "spread_10y2y": metrics.get("spread_10y2y"),
            "spread_2y3m": metrics.get("spread_2y3m"),
        },
    }


def main():
    load_dotenv()
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        print("ERROR: FRED_API_KEY is not set. Copy .env.example to .env and fill it in,", file=sys.stderr)
        print("or export FRED_API_KEY before running. Sign up free at:", file=sys.stderr)
        print("https://fred.stlouisfed.org/docs/api/api_key.html", file=sys.stderr)
        sys.exit(1)

    warnings = []
    metrics = {}
    for key, cfg in FRED_SERIES.items():
        print(f"Fetching {key} ({cfg[0]})...")
        result = build_metric(key, cfg, api_key, warnings)
        metrics[key] = result
        if result:
            print(f"  -> {result['as_of']}: {result['latest']} (stale={result['stale']})")

    print("Fetching gold (Yahoo Finance)...")
    metrics["gold"] = fetch_gold(warnings)

    print("Fetching yield curve shape...")
    curve_current, curve_1y_ago = fetch_yield_curve(api_key, warnings)

    print("Computing 2Y-3M spread (no premade FRED series)...")
    metrics["spread_2y3m"] = fetch_spread_2y3m(api_key, warnings)

    print(f"Fetching Momentum Composite universe ({len(MOMENTUM_UNIVERSE)} ETFs via Yahoo Finance)...")
    momentum_section = fetch_momentum(warnings)

    payroll_keys = ["payrolls_mom", "payrolls_private", "payrolls_goods", "payrolls_service", "payrolls_govt"]
    payroll_labels = {
        "payrolls_mom": "Total Nonfarm",
        "payrolls_private": "Private",
        "payrolls_goods": "Goods-Producing",
        "payrolls_service": "Service-Providing",
        "payrolls_govt": "Government",
    }
    payrolls_by_category = [
        {"label": payroll_labels[k], "value": metrics[k]["latest"]}
        for k in payroll_keys
        if metrics.get(k) and metrics[k]["latest"] is not None
    ]

    regime_section = build_regime_section(metrics)

    output = {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "regime": regime_section,
        "credit_spreads": {
            "hy_oas": metrics.get("hy_oas"),
            "ig_oas": metrics.get("ig_oas"),
            "em_corp_oas": metrics.get("em_corp_oas"),
        },
        "inflation": {
            "breakeven_5y": metrics.get("breakeven_5y"),
            "breakeven_10y": metrics.get("breakeven_10y"),
            "forward_5y5y": metrics.get("forward_5y5y"),
            "real_10y": metrics.get("real_10y"),
            "tips_5y": metrics.get("tips_5y"),
            "core_pce_yoy": metrics.get("core_pce_yoy"),
        },
        "liquidity": {
            "nfci": metrics.get("nfci"),
            "fed_assets": metrics.get("fed_assets"),
            "rrp": metrics.get("rrp"),
            "m2": metrics.get("m2"),
        },
        "yield_curve": {
            "current": curve_current,
            "one_year_ago": curve_1y_ago,
        },
        "growth_labor": {
            "gdp_growth": metrics.get("gdp_growth"),
            "cpi_yoy": metrics.get("cpi_yoy"),
            "saving_rate": metrics.get("saving_rate"),
            "fed_funds": metrics.get("fed_funds"),
            "unemployment": metrics.get("unemployment"),
            "payrolls_by_category": payrolls_by_category,
            "initial_claims": metrics.get("initial_claims"),
            "participation": metrics.get("participation"),
        },
        "cross_asset": {
            "vix": metrics.get("vix"),
            "gold": metrics.get("gold"),
            "wti": metrics.get("wti"),
            "dxy": metrics.get("dxy"),
            "eurusd": metrics.get("eurusd"),
            "usdjpy": metrics.get("usdjpy"),
        },
        "treasury_spreads": {
            "y2": metrics.get("y2"),
            "m3": metrics.get("m3"),
            "y10": metrics.get("y10"),
            "spread_2y3m": metrics.get("spread_2y3m"),
            "spread_10y2y": metrics.get("spread_10y2y"),
        },
        "momentum": momentum_section,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "data.json"), "w") as f:
        json.dump(output, f, indent=2)

    with open(os.path.join(DATA_DIR, "meta.json"), "w") as f:
        json.dump({"generated_at_utc": output["generated_at_utc"], "warnings": warnings}, f, indent=2)

    if warnings:
        print(f"\n{len(warnings)} warning(s):", file=sys.stderr)
        for w in warnings:
            print(f"  WARN: {w}", file=sys.stderr)

    print(f"\nWrote data/data.json and data/meta.json at {output['generated_at_utc']}")


if __name__ == "__main__":
    main()
