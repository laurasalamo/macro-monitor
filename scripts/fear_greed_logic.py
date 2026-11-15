"""Fear & Greed index: seven market-sentiment indicators scored 0-100 and averaged.

The indicator set and rating bands follow CNN's published Fear & Greed
methodology. CNN's own numbers aren't available to automated clients, so each
indicator is recomputed here from free data (Yahoo Finance + FRED). Three
of CNN's inputs (NYSE new highs/lows, McClellan volume, CBOE put/call) have no
free daily source and use proxies, flagged with `proxy` below.

Scoring: each indicator's raw signal is oriented so higher = greedier, then
scored as its percentile rank within its own trailing ~2-year window
(0 = most fearful reading of the window, 100 = greediest). The index is the
plain average of the seven scores.
"""

from bisect import bisect_left, bisect_right
from datetime import date, timedelta

WINDOW = 504      # trailing trading days used to score a reading (~2 years)
MIN_WINDOW = 252  # need at least ~1 year of readings before scoring
CHART_DAYS = 252  # ~1 year of raw history per indicator for the small charts

# CNN's bands, applied to the rounded 0-100 score.
BANDS = [(25, "Extreme Fear"), (45, "Fear"), (56, "Neutral"), (76, "Greed"), (101, "Extreme Greed")]

# Yahoo tickers this module needs (fetch_data.py fetches them).
TICKERS = {
    "spx": "^GSPC",
    "vix": "^VIX",
    "vix3m": "^VIX3M",
    "rsp": "RSP",
    "spy": "SPY",
    "tlt": "TLT",
}

INDICATORS = [
    {
        "key": "momentum",
        "label": "Market Momentum",
        "measures": "S&P 500 vs its 125-day moving average. Trading well above the average signals greed; below it, fear.",
        "proxy": None,
        "unit": "%",
    },
    {
        "key": "strength",
        "label": "Stock Price Strength",
        "measures": "Where the equal-weight S&P 500 (RSP) sits in its 52-week range: near the high = greed, near the low = fear.",
        "proxy": "CNN uses NYSE 52-week highs vs lows, which has no free daily source.",
        "unit": "%",
    },
    {
        "key": "breadth",
        "label": "Stock Price Breadth",
        "measures": "Equal-weight vs cap-weight S&P 500 (RSP/SPY) relative to its 50-day average. The average stock keeping up = broad participation = greed.",
        "proxy": "CNN uses the McClellan Volume Summation Index, which has no free daily source.",
        "unit": "%",
    },
    {
        "key": "options",
        "label": "Put and Call Options",
        "measures": "VIX ÷ VIX3M, 5-day average. Short-term protection costing more than longer-term (ratio above 1) = hedging demand = fear.",
        "proxy": "CNN uses the CBOE 5-day put/call ratio, which has no free daily source.",
        "unit": "",
    },
    {
        "key": "volatility",
        "label": "Market Volatility",
        "measures": "VIX vs its 50-day moving average. Rising volatility signals fear.",
        "proxy": None,
        "unit": "%",
    },
    {
        "key": "safe_haven",
        "label": "Safe Haven Demand",
        "measures": "20-day return of stocks (SPY) minus long Treasuries (TLT). Stocks outperforming bonds = greed.",
        "proxy": None,
        "unit": "pp",
    },
    {
        "key": "junk",
        "label": "Junk Bond Demand",
        "measures": "High-yield minus investment-grade spread (ICE BofA OAS). A narrow gap means investors take more credit risk = greed.",
        "proxy": None,
        "unit": "pp",
    },
]


def rating(score):
    if score is None:
        return None
    s = round(score)
    for upper, label in BANDS:
        if s < upper:
            return label
    return BANDS[-1][1]


def align(series, base_dates, max_gap_days=5):
    """Values of a sorted (date, value) series on each base date, carrying the
    last value forward up to max_gap_days calendar days (else None)."""
    out, j, last = [], 0, None
    for d in base_dates:
        while j < len(series) and series[j][0] <= d:
            last = series[j]
            j += 1
        if last and (date.fromisoformat(d) - date.fromisoformat(last[0])).days <= max_gap_days:
            out.append(last[1])
        else:
            out.append(None)
    return out


def sma(values, n):
    out = []
    for i in range(len(values)):
        window = values[max(0, i - n + 1): i + 1]
        if len(window) < n or any(x is None for x in window):
            out.append(None)
        else:
            out.append(sum(window) / n)
    return out


def rolling_min_max(values, n):
    lo, hi = [], []
    for i in range(len(values)):
        window = [x for x in values[max(0, i - n + 1): i + 1] if x is not None]
        ok = i >= n - 1 and len(window) == n
        lo.append(min(window) if ok else None)
        hi.append(max(window) if ok else None)
    return lo, hi


def _op(fn, *cols):
    return [None if any(c is None for c in row) else fn(*row) for row in zip(*cols)]


def lag(values, n):
    return [None] * n + values[:-n] if n else list(values)


def percentile_scores(values, window=WINDOW, min_window=MIN_WINDOW):
    """0-100 percentile rank of each value within the trailing window of
    non-missing values (inclusive). Ties count half."""
    out = []
    for i, v in enumerate(values):
        if v is None:
            out.append(None)
            continue
        past = sorted(x for x in values[max(0, i - window + 1): i + 1] if x is not None)
        n = len(past)
        if n < min_window:
            out.append(None)
            continue
        below = bisect_left(past, v)
        equal = bisect_right(past, v) - below - 1  # excluding itself
        out.append(100.0 * (below + 0.5 * equal) / (n - 1))
    return out


def raw_signals(dates, closes, spreads):
    """Raw indicator values on each base date, plus the lines charted per
    indicator. `closes` maps TICKERS keys -> aligned close lists; `spreads`
    maps "hy"/"ig" -> aligned OAS lists. Returns (raw, greed_sign, lines)."""
    spx, vix, vix3m = closes["spx"], closes["vix"], closes["vix3m"]
    rsp, spy, tlt = closes["rsp"], closes["spy"], closes["tlt"]

    spx_ma = sma(spx, 125)
    momentum = _op(lambda p, m: (p / m - 1) * 100, spx, spx_ma)

    lo, hi = rolling_min_max(rsp, 252)
    strength = _op(lambda p, l, h: (p - l) / (h - l) * 100 if h > l else 50.0, rsp, lo, hi)

    ratio = _op(lambda a, b: a / b, rsp, spy)
    ratio_ma = sma(ratio, 50)
    breadth = _op(lambda r, m: (r / m - 1) * 100, ratio, ratio_ma)

    term = _op(lambda a, b: a / b, vix, vix3m)
    options = sma(term, 5)

    vix_ma = sma(vix, 50)
    volatility = _op(lambda v, m: (v / m - 1) * 100, vix, vix_ma)

    safe_haven = _op(lambda s, s0, t, t0: ((s / s0) - (t / t0)) * 100, spy, lag(spy, 20), tlt, lag(tlt, 20))

    junk = _op(lambda h, i: h - i, spreads["hy"], spreads["ig"])

    raw = {
        "momentum": momentum, "strength": strength, "breadth": breadth, "options": options,
        "volatility": volatility, "safe_haven": safe_haven, "junk": junk,
    }
    # +1: higher raw = greed; -1: higher raw = fear.
    sign = {"momentum": 1, "strength": 1, "breadth": 1, "options": -1,
            "volatility": -1, "safe_haven": 1, "junk": -1}
    lines = {
        "momentum": [("S&P 500", spx), ("125-day average", spx_ma)],
        "strength": [("RSP position in 52-week range (%)", strength)],
        "breadth": [("RSP/SPY vs 50-day average (%)", breadth)],
        "options": [("VIX ÷ VIX3M, 5-day avg", options)],
        "volatility": [("VIX", vix), ("50-day average", vix_ma)],
        "safe_haven": [("Stocks minus bonds, 20-day return (pp)", safe_haven)],
        "junk": [("HY minus IG spread (pp)", junk)],
    }
    return raw, sign, lines


def _value_text(key, v):
    if v is None:
        return "—"
    if key == "momentum":
        return f"S&P 500 is {abs(v):.1f}% {'above' if v >= 0 else 'below'} its 125-day average"
    if key == "strength":
        return f"RSP is at {v:.0f}% of its 52-week range"
    if key == "breadth":
        return f"RSP/SPY is {abs(v):.2f}% {'above' if v >= 0 else 'below'} its 50-day average"
    if key == "options":
        return f"VIX/VIX3M ratio {v:.3f} ({'inverted, stressed' if v > 1 else 'normal contango'})"
    if key == "volatility":
        return f"VIX is {abs(v):.1f}% {'above' if v >= 0 else 'below'} its 50-day average"
    if key == "safe_haven":
        return f"Stocks {'beat' if v >= 0 else 'trailed'} bonds by {abs(v):.1f}pp over 20 days"
    if key == "junk":
        return f"HY spread is {v:.2f}pp over IG"
    return f"{v:.2f}"


def _value_on_or_before(history, target_iso):
    best = None
    for d, v in history:
        if d <= target_iso:
            best = (d, v)
        else:
            break
    return best


def build_fear_greed(dates, closes, spreads):
    """dates: base trading dates (S&P 500 calendar); closes/spreads: aligned lists."""
    raw, sign, lines = raw_signals(dates, closes, spreads)

    scores = {}
    for key, values in raw.items():
        oriented = [None if v is None else sign[key] * v for v in values]
        scores[key] = percentile_scores(oriented)

    keys = [ind["key"] for ind in INDICATORS]
    composite = []
    for i, d in enumerate(dates):
        row = [scores[k][i] for k in keys]
        if all(s is not None for s in row):
            composite.append((d, sum(row) / len(row)))
    if not composite:
        return None

    as_of, score = composite[-1]
    last = date.fromisoformat(as_of)

    def snap(days=None, label=""):
        if days is None:  # previous close = the reading before the latest
            point = composite[-2] if len(composite) > 1 else None
        else:
            point = _value_on_or_before(composite, (last - timedelta(days=days)).isoformat())
        if not point:
            return None
        return {"label": label, "date": point[0], "score": round(point[1]), "rating": rating(point[1])}

    indicators = []
    cutoff = max(0, len(dates) - CHART_DAYS)
    for ind in INDICATORS:
        k = ind["key"]
        idx = max((i for i, s in enumerate(scores[k]) if s is not None), default=None)
        cur = scores[k][idx] if idx is not None else None
        raw_v = raw[k][idx] if idx is not None else None
        indicators.append({
            **ind,
            "score": round(cur) if cur is not None else None,
            "rating": rating(cur),
            "as_of": dates[idx] if idx is not None else None,
            "value": round(raw_v, 4) if raw_v is not None else None,
            "value_text": _value_text(k, raw_v),
            "lines": [
                {"label": label, "data": [[dates[i], round(vals[i], 4)]
                                          for i in range(cutoff, len(dates)) if vals[i] is not None]}
                for label, vals in lines[k]
            ],
        })

    return {
        "as_of": as_of,
        "score": round(score),
        "rating": rating(score),
        "compare": [c for c in (snap(None, "Previous close"), snap(7, "1 week ago"),
                                snap(30, "1 month ago"), snap(365, "1 year ago")) if c],
        "history": [[d, round(v, 1)] for d, v in composite],
        "indicators": indicators,
        "bands": [[upper, label] for upper, label in BANDS],
    }
