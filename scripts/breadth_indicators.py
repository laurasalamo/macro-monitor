"""Classic market-breadth indicators computed from the S&P 500 members' daily
OHLCV (Yahoo Finance): A/D line, net advances, McClellan Oscillator,
Summation Index / RASI, new highs & lows, % above moving averages, High-Low
Index and up-volume share.

The originals are published for the NYSE (all ~2,800 issues), but free daily
NYSE advance/decline data doesn't exist, so the same formulas run on the 500
S&P members instead. Ratio-adjusted versions (per 1,000 issues) make the
levels roughly comparable to the NYSE conventions.
"""

from collections import deque

MIN_COVERAGE = 0.9   # need 90% of members with a close today and yesterday
HL_DAYS = 252        # 52-week window for new highs / lows
AD_MA_DAYS = 100     # moving average drawn on the A/D line
SMOOTH_DAYS = 10     # short average for noisy daily series
MA_SET = (20, 50, 200)


# ------------------------------------------------------------------ helpers

def ema(values, alpha):
    """Exponential average with smoothing factor alpha; None passes through
    and the average resumes from the last value."""
    out, cur = [], None
    for v in values:
        if v is not None:
            cur = v if cur is None else cur + alpha * (v - cur)
        out.append(cur if v is not None else None)
    return out


def sma(values, n):
    out, window = [], []
    for v in values:
        if v is None:
            out.append(None)
            continue
        window.append(v)
        if len(window) > n:
            window.pop(0)
        out.append(sum(window) / n if len(window) == n else None)
    return out


def cumsum(values, start=0.0):
    out, total = [], start
    for v in values:
        if v is None:
            out.append(None)
            continue
        total += v
        out.append(total)
    return out


def _r(v, nd=2):
    return None if v is None else round(v, nd)


def _series(dates, values, nd=2):
    return [[d, round(v, nd)] for d, v in zip(dates, values) if v is not None]


# ------------------------------------------------------------------ daily counts

def daily_counts(dates, close, high, low, volume, min_coverage=MIN_COVERAGE):
    """Per-day breadth counts across all stocks. close/high/low/volume are lists
    of per-stock columns aligned to dates (None where missing). Days where
    fewer than min_coverage of the stocks can be compared are None."""
    n_days, universe = len(dates), len(close)
    adv = [0] * n_days
    dec = [0] * n_days
    seen = [0] * n_days
    up_vol = [0.0] * n_days
    down_vol = [0.0] * n_days
    nh = [0] * n_days
    nl = [0] * n_days
    hl_seen = [0] * n_days
    above = {n: [0] * n_days for n in MA_SET}
    ma_seen = {n: [0] * n_days for n in MA_SET}

    for s in range(universe):
        c, h, lo, vol = close[s], high[s], low[s], volume[s]
        sums = {n: 0.0 for n in MA_SET}
        lens = {n: 0 for n in MA_SET}
        # Monotonic deques of (index, value) give the rolling 52-week max/min in O(1).
        hi_q, lo_q, run_start = deque(), deque(), 0
        for i in range(n_days):
            ci = c[i]
            # advances / declines and volume
            if i and ci is not None and c[i - 1] is not None:
                seen[i] += 1
                v = vol[i] or 0.0
                if ci > c[i - 1]:
                    adv[i] += 1
                    up_vol[i] += v
                elif ci < c[i - 1]:
                    dec[i] += 1
                    down_vol[i] += v
            # moving averages (a gap restarts them)
            for n in MA_SET:
                if ci is None:
                    sums[n], lens[n] = 0.0, 0
                    continue
                sums[n] += ci
                lens[n] += 1
                if lens[n] > n:
                    sums[n] -= c[i - n]
                    lens[n] = n
                if lens[n] == n:
                    ma_seen[n][i] += 1
                    if ci > sums[n] / n:
                        above[n][i] += 1
            # 52-week highs / lows on intraday high & low
            hi_v = h[i] if h[i] is not None else ci
            lo_v = lo[i] if lo[i] is not None else ci
            if hi_v is None or lo_v is None:
                hi_q.clear()
                lo_q.clear()
                run_start = i + 1  # a gap restarts the 52-week window
                continue
            while hi_q and hi_q[-1][1] <= hi_v:
                hi_q.pop()
            hi_q.append((i, hi_v))
            while lo_q and lo_q[-1][1] >= lo_v:
                lo_q.pop()
            lo_q.append((i, lo_v))
            while hi_q[0][0] <= i - HL_DAYS:
                hi_q.popleft()
            while lo_q[0][0] <= i - HL_DAYS:
                lo_q.popleft()
            if i - run_start + 1 >= HL_DAYS:
                hl_seen[i] += 1
                if hi_q[0][0] == i:  # today is the highest of the window (ties count)
                    nh[i] += 1
                if lo_q[0][0] == i:
                    nl[i] += 1

    need = min_coverage * universe
    ok = [seen[i] >= need and seen[i] > 0 for i in range(n_days)]
    hl_ok = [hl_seen[i] >= need for i in range(n_days)]
    return {
        "adv": [adv[i] if ok[i] else None for i in range(n_days)],
        "dec": [dec[i] if ok[i] else None for i in range(n_days)],
        "issues": [seen[i] if ok[i] else None for i in range(n_days)],
        "up_vol": [up_vol[i] if ok[i] else None for i in range(n_days)],
        "down_vol": [down_vol[i] if ok[i] else None for i in range(n_days)],
        "nh": [nh[i] if hl_ok[i] else None for i in range(n_days)],
        "nl": [nl[i] if hl_ok[i] else None for i in range(n_days)],
        "pct_above": {
            n: [100.0 * above[n][i] / ma_seen[n][i] if ma_seen[n][i] >= need else None for i in range(n_days)]
            for n in MA_SET
        },
    }


# ------------------------------------------------------------------ indicator text

TEXT = {
    "ad_line": {
        "label": "A/D Line",
        "theory": "The advance/decline line is the best-known breadth indicator and the simplest to compute: each day, take the number of stocks that rose, subtract the number that fell, and add the result to the previous day's value. Every stock counts the same, whatever its size.",
        "interpretation": "Because it isn't cap-weighted, the A/D line shows whether a move is broad or carried by a few giants. Watch for divergences: if the index makes new highs while the A/D line falls, most stocks are no longer participating and the advance is fragile. It is a warning, not a timing signal: divergences can last for months.",
        "unit": "",
    },
    "adn": {
        "label": "Net Advances (ADn)",
        "theory": "Daily advances minus declines, ratio-adjusted: (advances − declines) ÷ (advances + declines) × 1,000. Normalizing by the number of stocks traded makes readings comparable over time and across markets. It is the raw input to the McClellan Oscillator and the Summation Index.",
        "interpretation": "Each bar is one day's breadth. Readings above +800 or below −800 mean nearly every stock moved the same way (a thrust day). Strings of positive bars confirm a healthy rally; heavy negative days clustered together often mark capitulation near lows.",
        "unit": "",
    },
    "summation": {
        "label": "Summation Index & RASI",
        "theory": "The McClellan Summation Index is the running total of the McClellan Oscillator. The ratio-adjusted version (RASI) uses the ratio-adjusted oscillator, so it doesn't depend on how many stocks are counted. Both turn short-term breadth swings into a medium-term trend.",
        "interpretation": "Rising = breadth is improving, falling = deteriorating; the direction matters more than the level. On RASI, crossing above 0 is a bullish sign, above +500 the market is overbought (often a sign of strong momentum early in a rally), and below −500 it is oversold, where major lows tend to form.",
        "unit": "",
    },
    "mcclellan": {
        "label": "McClellan Oscillator",
        "theory": "The difference between a 19-day and a 39-day exponential average (10% and 5% smoothing) of ratio-adjusted net advances. It measures the short-term momentum of breadth, much like MACD does for prices.",
        "interpretation": "Above zero, advancing stocks dominate; below zero, decliners do. Readings above +70 are overbought and below −70 oversold; beyond ±100 they are extreme. Zero crossings and divergences against the index (e.g. a new index low with a higher oscillator low) are the classic signals.",
        "unit": "",
    },
    "new_highs_lows": {
        "label": "New Highs & Lows",
        "theory": "The number of stocks hitting a new 52-week high (green, up) and a new 52-week low (red, down) each day, based on intraday highs and lows. The line is the net (highs − lows), averaged over 10 days.",
        "interpretation": "In a healthy uptrend new highs clearly outnumber new lows. Rising new lows while the index is near its highs is a sign of internal weakness. A spike in new lows usually comes with sell-offs, and its fading tends to signal that the selling is exhausted.",
        "unit": "",
    },
    "pct_above_ma": {
        "label": "% Above Moving Averages",
        "theory": "The percentage of stocks closing above their own 20-day (short term), 50-day (medium term) and 200-day (long term) moving averages.",
        "interpretation": "Above 50% the majority of stocks are in an uptrend for that time frame. Readings above 80% are overbought and below 20% oversold, especially on the 20- and 50-day lines. When the index rises while these percentages fall, fewer stocks are carrying the move. The 200-day line describes the long-term health of the market.",
        "unit": "%",
    },
    "pct_highs_lows": {
        "label": "% at Highs vs Lows",
        "theory": "The High-Low Index: new 52-week highs as a percentage of new highs plus new lows, NH ÷ (NH + NL) × 100, averaged over 10 days. Days with no new highs or lows don't change the average.",
        "interpretation": "Above 50% more stocks are making new highs than new lows; below 50%, the reverse. Above 70% indicates a strong uptrend, below 30% a strong downtrend. A move from below 30% to above 50% often confirms that a correction has ended.",
        "unit": "%",
    },
    "volume": {
        "label": "Volume",
        "theory": "The share of total volume traded in advancing stocks: up volume ÷ (up volume + down volume) × 100. It weighs breadth by how much money is moving, not just by how many stocks.",
        "interpretation": "Days above 90% (90% up days) show heavy, broad buying; days below 10% (90% down days) show panic selling. Clusters of 90% down days often precede lows, and a 90% up day after a decline is a classic sign that buyers are returning. The 10-day average shows the trend of buying pressure.",
        "unit": "%",
    },
}

ORDER = ["ad_line", "adn", "summation", "mcclellan", "new_highs_lows", "pct_above_ma", "pct_highs_lows", "volume"]


# ------------------------------------------------------------------ build

def build_indicators(dates, counts, index_closes=None, index_name="S&P 500"):
    """Returns {as_of, indicators: [{key, label, theory, interpretation, unit,
    latest, latest_text, lines, refs}]} for the breadth explorer."""
    adv, dec = counts["adv"], counts["dec"]
    ok_idx = [i for i, a in enumerate(adv) if a is not None]
    if not ok_idx:
        return None
    first = ok_idx[0]
    d = dates[first:]

    def cut(values):
        return values[first:]

    net = cut([None if a is None else a - b for a, b in zip(adv, dec)])
    rana = cut([None if a is None or (a + b) == 0 else (a - b) / (a + b) * 1000 for a, b in zip(adv, dec)])
    ad_line = cumsum(net)
    ad_ma = sma(ad_line, AD_MA_DAYS)
    fast, slow = ema(rana, 0.1), ema(rana, 0.05)
    raw_fast, raw_slow = ema(net, 0.1), ema(net, 0.05)
    osc = [None if a is None else a - b for a, b in zip(fast, slow)]
    # Summation = running total of the oscillator (S_t = S_t-1 + osc_t). With
    # 10%/5% EMAs that sum telescopes to 19*slow - 9*fast plus a constant set by
    # the first day of data; the closed form drops that arbitrary offset.
    rasi = [None if f is None else 19 * s_ - 9 * f for f, s_ in zip(fast, slow)]
    summ = [None if f is None else 19 * s_ - 9 * f for f, s_ in zip(raw_fast, raw_slow)]

    nh, nl = cut(counts["nh"]), cut(counts["nl"])
    net_hl = sma([None if h is None else h - l for h, l in zip(nh, nl)], SMOOTH_DAYS)
    hl_pct_daily, last_pct = [], None
    for h, l in zip(nh, nl):
        if h is None:
            hl_pct_daily.append(None)
            continue
        if h + l:
            last_pct = 100.0 * h / (h + l)
        hl_pct_daily.append(last_pct)  # no highs or lows today: carry the last ratio
    hl_index = sma(hl_pct_daily, SMOOTH_DAYS)

    up, down = cut(counts["up_vol"]), cut(counts["down_vol"])
    up_pct = [None if u is None or (u + v) == 0 else 100.0 * u / (u + v) for u, v in zip(up, down)]
    up_pct_ma = sma(up_pct, SMOOTH_DAYS)

    pct = {n: cut(counts["pct_above"][n]) for n in MA_SET}

    index_line = []
    if index_closes:
        index_line = [[dt, round(v, 2)] for dt, v in zip(d, cut(index_closes)) if v is not None]

    def last(values):
        for v in reversed(values):
            if v is not None:
                return v
        return None

    built = {
        "ad_line": {
            "lines": [
                {"label": "A/D line", "type": "line", "data": _series(d, ad_line, 0)},
                {"label": f"{AD_MA_DAYS}-day average", "type": "line", "dash": True, "data": _series(d, ad_ma, 1)},
            ] + ([{"label": index_name, "type": "area", "axis": "y2", "data": index_line}] if index_line else []),
            "refs": [],
            "latest": last(ad_line),
            "latest_text": (lambda v, m: f"{v:,.0f} ({'above' if m is not None and v >= m else 'below'} its {AD_MA_DAYS}-day average)")(last(ad_line), last(ad_ma)),
        },
        "adn": {
            "lines": [
                {"label": "Net advances (ratio-adjusted)", "type": "bar", "sign_colors": True, "data": _series(d, rana, 1)},
                {"label": f"{SMOOTH_DAYS}-day average", "type": "line", "data": _series(d, sma(rana, SMOOTH_DAYS), 1)},
            ],
            "refs": [0],
            "latest": last(rana),
            "latest_text": f"{last(rana):+.0f} ({adv[-1] if adv[-1] is not None else '—'} up, {dec[-1] if dec[-1] is not None else '—'} down)",
        },
        "summation": {
            "lines": [
                {"label": "RASI (ratio-adjusted)", "type": "line", "data": _series(d, rasi, 1)},
                {"label": "Summation Index", "type": "line", "data": _series(d, summ, 1)},
            ],
            "refs": [0, 500, -500],
            "latest": last(rasi),
            "latest_text": f"RASI {last(rasi):+,.0f}",
        },
        "mcclellan": {
            "lines": [
                {"label": "McClellan Oscillator", "type": "bar", "sign_colors": True, "data": _series(d, osc, 1)},
            ],
            "refs": [0, 70, -70],
            "latest": last(osc),
            "latest_text": f"{last(osc):+.1f}",
        },
        "new_highs_lows": {
            "lines": [
                {"label": "New 52-week highs", "type": "bar", "color": "up", "data": _series(d, nh, 0)},
                {"label": "New 52-week lows", "type": "bar", "color": "down", "data": _series(d, [None if v is None else -v for v in nl], 0)},
                {"label": f"Net highs − lows, {SMOOTH_DAYS}-day avg", "type": "line", "data": _series(d, net_hl, 1)},
            ],
            "refs": [0],
            "latest": last(nh),
            "latest_text": f"{last(nh) if last(nh) is not None else '—'} highs / {last(nl) if last(nl) is not None else '—'} lows",
        },
        "pct_above_ma": {
            "lines": [
                {"label": f"Above {n}-day average", "type": "line", "data": _series(d, pct[n], 1)} for n in MA_SET
            ],
            "refs": [50, 80, 20],
            "range": [0, 100],
            "latest": last(pct[50]),
            "latest_text": " · ".join(f"{n}d {last(pct[n]):.0f}%" for n in MA_SET if last(pct[n]) is not None),
        },
        "pct_highs_lows": {
            "lines": [
                {"label": f"High-Low Index ({SMOOTH_DAYS}-day avg)", "type": "line", "data": _series(d, hl_index, 1)},
            ],
            "refs": [50, 70, 30],
            "range": [0, 100],
            "latest": last(hl_index),
            "latest_text": f"{last(hl_index):.0f}%" if last(hl_index) is not None else "—",
        },
        "volume": {
            "lines": [
                {"label": "Up volume share", "type": "bar", "color": "neutral", "extreme": [10, 90], "data": _series(d, up_pct, 1)},
                {"label": f"{SMOOTH_DAYS}-day average", "type": "line", "data": _series(d, up_pct_ma, 1)},
            ],
            "refs": [50, 90, 10],
            "range": [0, 100],
            "latest": last(up_pct),
            "latest_text": f"{last(up_pct):.0f}% of volume in rising stocks" if last(up_pct) is not None else "—",
        },
    }

    indicators = []
    for key in ORDER:
        item = {"key": key, **TEXT[key], **built[key]}
        item["latest"] = _r(item["latest"], 1)
        indicators.append(item)
    return {"as_of": d[-1], "index_name": index_name, "indicators": indicators}
