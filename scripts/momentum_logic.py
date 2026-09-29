"""Cross-sectional ETF momentum scoring.

Each ticker gets four raw signals (trend, acceleration, proximity to its
52-week high, realized volatility), which are converted to 0-100
percentile ranks *within the universe being scored* and combined into a
single 0-100 composite via the weights in momentum_config.py. Percentile
ranking (rather than an absolute scale) is what makes the score a relative
ranking tool - "leader vs. laggard within today's universe" - not a
prediction of future returns.
"""

import math
import statistics

from momentum_config import (
    LB_1M,
    LB_3M,
    LB_6M,
    LB_12M,
    LB_HIGH,
    LB_VOL,
    MIN_HISTORY_DAYS,
    RVOL_BASE,
    RVOL_RECENT,
    TREND_BLEND,
    WEIGHT_ACCEL,
    WEIGHT_LOWVOL,
    WEIGHT_MAXPROX,
    WEIGHT_TREND,
)


def trading_return(closes, n):
    """% return over the trailing n trading days, or None if not enough history."""
    if len(closes) <= n:
        return None
    prev = closes[-1 - n]
    if prev == 0:
        return None
    return (closes[-1] / prev - 1) * 100


def realized_vol_annualized(closes, n):
    """Annualized stdev of daily log returns over the trailing n days, as a %."""
    if len(closes) <= n:
        return None
    window = closes[-(n + 1):]
    log_rets = [
        math.log(window[i] / window[i - 1])
        for i in range(1, len(window))
        if window[i - 1] > 0 and window[i] > 0
    ]
    if len(log_rets) < 2:
        return None
    return statistics.pstdev(log_rets) * math.sqrt(252) * 100


def distance_from_high(closes, n):
    """% distance of the latest close from the trailing n-day high (<= 0)."""
    window = closes[-n:] if len(closes) >= n else closes
    high = max(window)
    if high == 0:
        return None
    return (closes[-1] / high - 1) * 100


def relative_volume(volumes, recent, base):
    """Recent average volume / longer-run average volume, as a multiple."""
    if len(volumes) < base:
        return None
    recent_avg = statistics.mean(volumes[-recent:])
    base_avg = statistics.mean(volumes[-base:])
    if base_avg == 0:
        return None
    return recent_avg / base_avg


def percentile_ranks(pairs):
    """pairs: iterable of (key, value_or_None). Returns {key: pct 0-100} for
    keys with a non-None value; ties share the averaged rank."""
    pairs = [(k, v) for k, v in pairs if v is not None]
    n = len(pairs)
    if n == 0:
        return {}
    if n == 1:
        return {pairs[0][0]: 50.0}

    sorted_pairs = sorted(pairs, key=lambda kv: kv[1])
    ranks = {}
    i = 0
    while i < n:
        j = i
        while j + 1 < n and sorted_pairs[j + 1][1] == sorted_pairs[i][1]:
            j += 1
        avg_rank = (i + j) / 2
        pct = avg_rank / (n - 1) * 100
        for k in range(i, j + 1):
            ranks[sorted_pairs[k][0]] = pct
        i = j + 1
    return ranks


def build_rankings(price_data):
    """price_data: {ticker: {"closes": [ascending...], "volumes": [ascending...]}}

    Returns a list of row dicts sorted by composite score descending, each
    with a 1-based `rank`. Tickers with insufficient history, or a None in
    any of the four scored components, are dropped.
    """
    raw = {}
    for ticker, d in price_data.items():
        closes, volumes = d["closes"], d["volumes"]
        if len(closes) < MIN_HISTORY_DAYS:
            continue

        ret_1m = trading_return(closes, LB_1M)
        ret_3m = trading_return(closes, LB_3M)
        ret_6m = trading_return(closes, LB_6M)
        ret_12m = trading_return(closes, LB_12M)

        trend_raw = None
        if None not in (ret_1m, ret_3m, ret_6m, ret_12m):
            trend_raw = (
                TREND_BLEND["1m"] * ret_1m
                + TREND_BLEND["3m"] * ret_3m
                + TREND_BLEND["6m"] * ret_6m
                + TREND_BLEND["12m"] * ret_12m
            )

        # Acceleration: current 3M return vs. the 3M return as of 3 months ago.
        accel_raw = None
        if len(closes) > 2 * LB_3M:
            prev_3m = trading_return(closes[:-LB_3M], LB_3M)
            if ret_3m is not None and prev_3m is not None:
                accel_raw = ret_3m - prev_3m

        max_raw = distance_from_high(closes, LB_HIGH)
        vol_raw = realized_vol_annualized(closes, LB_VOL)
        rvol = relative_volume(volumes, RVOL_RECENT, RVOL_BASE)

        raw[ticker] = {
            "ret_1m": ret_1m, "ret_3m": ret_3m, "ret_6m": ret_6m, "ret_12m": ret_12m,
            "trend_raw": trend_raw, "accel_raw": accel_raw, "max_raw": max_raw,
            "vol_raw": vol_raw, "rvol": rvol,
        }

    trend_pct = percentile_ranks([(t, v["trend_raw"]) for t, v in raw.items()])
    accel_pct = percentile_ranks([(t, v["accel_raw"]) for t, v in raw.items()])
    max_pct = percentile_ranks([(t, v["max_raw"]) for t, v in raw.items()])
    # Lower volatility should score higher, so rank on the negated raw value.
    lowvol_pct = percentile_ranks(
        [(t, -v["vol_raw"] if v["vol_raw"] is not None else None) for t, v in raw.items()]
    )

    rows = []
    for ticker, v in raw.items():
        tend, acel, mx, vol = (
            trend_pct.get(ticker), accel_pct.get(ticker), max_pct.get(ticker), lowvol_pct.get(ticker)
        )
        if None in (tend, acel, mx, vol):
            continue
        score = WEIGHT_TREND * tend + WEIGHT_ACCEL * acel + WEIGHT_MAXPROX * mx + WEIGHT_LOWVOL * vol
        rows.append({
            "ticker": ticker,
            "score": round(score),
            "tend": round(tend),
            "acel": round(acel),
            "max": round(mx),
            "vol": round(vol),
            "ret_1m": round(v["ret_1m"], 1) if v["ret_1m"] is not None else None,
            "ret_3m": round(v["ret_3m"], 1) if v["ret_3m"] is not None else None,
            "ret_6m": round(v["ret_6m"], 1) if v["ret_6m"] is not None else None,
            "ret_12m": round(v["ret_12m"], 1) if v["ret_12m"] is not None else None,
            "from_high": round(v["max_raw"], 1) if v["max_raw"] is not None else None,
            "rvol": round(v["rvol"], 1) if v["rvol"] is not None else None,
        })

    rows.sort(key=lambda r: r["score"], reverse=True)
    for i, r in enumerate(rows, start=1):
        r["rank"] = i
    return rows
