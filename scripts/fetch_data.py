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
    CHART_HISTORY_KEYS,
    FRED_SERIES,
    HISTORY_YEARS,
    REGIME_HISTORY_DAILY_YEARS,
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

        return {
            "latest": round(latest, 4) if latest is not None else None,
            "delta": round(delta, 4) if delta is not None else None,
            "as_of": as_of,
            "stale": stale,
            "days_since": days_since,
            "unit": unit,
            "history": [[d, round(v, 4)] for d, v in series],
        }
    except Exception as e:  # keep going on a single bad series
        warnings.append(f"{key} ({fred_id}): {e}")
        return None


def fetch_gold(warnings):
    try:
        series = get_gold_series()
        latest, delta, as_of = tx.latest_and_delta(series)
        days_since, stale = tx.staleness(as_of, "daily", STALE_THRESHOLD_DAYS)
        return {
            "latest": round(latest, 2) if latest is not None else None,
            "delta": round(delta, 2) if delta is not None else None,
            "as_of": as_of,
            "stale": stale,
            "days_since": days_since,
            "unit": "$",
            "history": [[d, round(v, 2)] for d, v in series],
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
        return {
            "latest": round(latest, 4) if latest is not None else None,
            "delta": round(delta, 4) if delta is not None else None,
            "as_of": as_of,
            "stale": stale,
            "days_since": days_since,
            "unit": "pp",
            "history": [[d, round(v, 4)] for d, v in spread],
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


def without_history(metric):
    if not metric:
        return metric
    return {k: v for k, v in metric.items() if k != "history"}


def with_trimmed_history(metric, years):
    if not metric:
        return metric
    start = years_ago_iso(years)
    return {**metric, "history": [p for p in metric["history"] if p[0] >= start]}


def build_regime_section(metrics):
    series_by_key = {
        k: (metrics.get(k) or {}).get("history", []) for k in regime.INDICATORS
    }
    latest_values = {k: (metrics.get(k) or {}).get("latest") for k in regime.INDICATORS}
    counts = regime.state_counts(latest_values)

    # Trailing 36-month history: one classification per calendar month, each
    # indicator taking its latest observation dated in or before that month.
    all_months = {d[:7] for s in series_by_key.values() for d, _ in s}
    months = sorted(all_months)[-regime.TRAILING_MONTHS:]
    monthly = regime.monthly_labels(series_by_key, months)

    cards = {}
    for k in regime.INDICATORS:
        m = without_history(metrics.get(k))
        if m:
            m = {
                **m,
                "state": regime.rate(k, m["latest"]),
                "decimals": regime.DISPLAY_DECIMALS[k],
                "rule": regime.RULE_TEXT[k],
            }
        cards[k] = m

    return {
        "current_label": regime.classify(counts),
        "counts": counts,
        "total": len(regime.INDICATORS),
        "trailing_36mo_counts": regime.trailing_regime_counts(monthly),
        "snapshot_cards": cards,
    }


def fetch_recessions(api_key, warnings):
    try:
        return tx.recession_ranges(tx.parse_observations(get_series("USREC", api_key)))
    except Exception as e:
        warnings.append(f"recessions (USREC): {e}")
        return []


def build_regime_history(metrics, recessions):
    """Full history of each regime indicator for the pop-up charts. Old daily
    data is thinned to weekly; the weekly claims print rides along with the
    4-week average so the claims chart can show both."""
    cutoff = years_ago_iso(REGIME_HISTORY_DAILY_YEARS)
    keys = regime.INDICATORS + ["initial_claims"]
    series = {}
    for k in keys:
        hist = (metrics.get(k) or {}).get("history", [])
        if k == "initial_claims":
            hist = [(d, v / 1000) for d, v in hist]  # raw claims -> thousands
        series[k] = [[d, round(v, 3)] for d, v in tx.thin_to_weekly_before(hist, cutoff)]
    return {"recessions": recessions, "series": series}


def empty_sections(output):
    """Names of top-level sections with no usable data at all (every metric None,
    no rows, etc.). Individual missing series are fine; a fully blank panel is not."""
    empty = []
    for name, section in output.items():
        if name == "generated_at_utc":
            continue
        if name == "momentum":
            has_data = bool(section.get("rows"))
        elif name == "yield_curve":
            has_data = bool(section.get("current"))
        elif name == "regime":
            # current_label falls back to "Neutral" with no inputs, so check the cards
            has_data = any(section.get("snapshot_cards", {}).values())
        else:
            # metric dicts are None on failure; payrolls_by_category is [] on failure
            has_data = any(section.values())
        if not has_data:
            empty.append(name)
    return empty


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

    print("Fetching NBER recession dates (USREC)...")
    recessions = fetch_recessions(api_key, warnings)

    regime_section = build_regime_section(metrics)
    regime_history = build_regime_history(metrics, recessions)

    # History is only needed in data.json for charted metrics; drop it
    # everywhere else to keep the daily-committed file small.
    metrics = {
        k: with_trimmed_history(m, HISTORY_YEARS.get(k, HISTORY_YEARS["default"]))
        if k in CHART_HISTORY_KEYS else without_history(m)
        for k, m in metrics.items()
    }

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

    # Refuse to write a blank panel: exit nonzero before touching data/ so the
    # workflow fails, skips the commit, and the previous good data stays live.
    empty = empty_sections(output)
    if empty:
        for w in warnings:
            print(f"  WARN: {w}", file=sys.stderr)
        print(f"ERROR: section(s) came back empty: {', '.join(empty)}", file=sys.stderr)
        print("Not writing data/data.json; previous data left in place.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "data.json"), "w") as f:
        json.dump(output, f, separators=(",", ":"))

    with open(os.path.join(DATA_DIR, "regime_history.json"), "w") as f:
        json.dump(regime_history, f, separators=(",", ":"))

    with open(os.path.join(DATA_DIR, "meta.json"), "w") as f:
        json.dump({"generated_at_utc": output["generated_at_utc"], "warnings": warnings}, f, indent=2)

    if warnings:
        print(f"\n{len(warnings)} warning(s):", file=sys.stderr)
        for w in warnings:
            print(f"  WARN: {w}", file=sys.stderr)

    print(f"\nWrote data/data.json, data/regime_history.json and data/meta.json at {output['generated_at_utc']}")


if __name__ == "__main__":
    main()
