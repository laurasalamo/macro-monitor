"""Market breadth: percentage of S&P 500 stocks closing above their 20-day
simple moving average (the S&P 500 version of TradingView's MMTW / S5TW).

Below RISK_LEVEL the market is entering a risk area; below HIGH_RISK_LEVEL
it is deeper in it. These are display thresholds, not a trading rule.
"""

import os
from datetime import date, timedelta

MA_DAYS = 20
RISK_LEVEL = 25
HIGH_RISK_LEVEL = 20
MIN_COVERAGE = 0.9  # need at least 90% of the list priced on a day to report it

CONSTITUENTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sp500_constituents.txt")


def load_constituents(path=CONSTITUENTS_FILE):
    with open(path) as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def zone(value):
    if value is None:
        return None
    if value < HIGH_RISK_LEVEL:
        return "High risk"
    if value < RISK_LEVEL:
        return "Risk"
    return "Normal"


def pct_above_sma(dates, columns, n=MA_DAYS, min_coverage=MIN_COVERAGE):
    """dates: trading dates; columns: one close list per stock, aligned to
    dates (None where missing). Returns [(date, pct)] for each date where at
    least min_coverage of the stocks have a close and a full n-day average."""
    universe = len(columns)
    if not universe:
        return []
    above = [0] * len(dates)
    valid = [0] * len(dates)
    for closes in columns:
        window_sum, window_len = 0.0, 0
        for i, c in enumerate(closes):
            if c is None:
                window_sum, window_len = 0.0, 0  # a gap restarts the average
                continue
            window_sum += c
            window_len += 1
            if window_len > n:
                window_sum -= closes[i - n]
                window_len = n
            if window_len == n:
                valid[i] += 1
                if c > window_sum / n:
                    above[i] += 1
    return [
        (d, 100.0 * above[i] / valid[i])
        for i, d in enumerate(dates)
        if valid[i] and valid[i] >= min_coverage * universe
    ]


def _on_or_before(series, target_iso):
    best = None
    for d, v in series:
        if d > target_iso:
            break
        best = (d, v)
    return best


def build_breadth(series, universe, priced):
    """series: [(date, pct)] from pct_above_sma. Returns the data.json section."""
    if not series:
        return None
    as_of, latest = series[-1]
    last = date.fromisoformat(as_of)
    prev = series[-2][1] if len(series) > 1 else None

    def back(days, label):
        p = _on_or_before(series, (last - timedelta(days=days)).isoformat())
        return {"label": label, "date": p[0], "value": round(p[1], 1), "zone": zone(p[1])} if p else None

    year = [v for d, v in series if d > (last - timedelta(days=365)).isoformat()]
    return {
        "as_of": as_of,
        "latest": round(latest, 1),
        "delta": round(latest - prev, 1) if prev is not None else None,
        "zone": zone(latest),
        "compare": [c for c in (back(7, "1 week ago"), back(30, "1 month ago"), back(91, "3 months ago")) if c],
        "low_52w": round(min(year), 1),
        "high_52w": round(max(year), 1),
        "days_below_risk_1y": sum(1 for v in year if v < RISK_LEVEL),
        "universe": universe,
        "priced": priced,
        "ma_days": MA_DAYS,
        "risk_level": RISK_LEVEL,
        "high_risk_level": HIGH_RISK_LEVEL,
        "history": [[d, round(v, 1)] for d, v in series],
    }
