"""Pure functions for turning raw FRED observations into chart/card-ready series."""

from datetime import date


def parse_observations(raw_observations):
    """raw_observations: list of {"date": "YYYY-MM-DD", "value": "1.23"|"."} from FRED.
    Returns sorted list of (date_str, float), dropping FRED's "." missing markers."""
    out = []
    for obs in raw_observations:
        v = obs.get("value")
        if v is None or v == ".":
            continue
        try:
            out.append((obs["date"], float(v)))
        except (TypeError, ValueError):
            continue
    out.sort(key=lambda p: p[0])
    return out


def apply_level(series, scale=1.0):
    if scale == 1.0:
        return list(series)
    return [(d, v * scale) for d, v in series]


def apply_yoy(series):
    """Year-over-year % change vs. the same date one year earlier (monthly series).

    Matched by date rather than 12 observations back, so a missing month (FRED
    ".") doesn't shift the following year's values onto the wrong base month.
    """
    by_date = dict(series)
    out = []
    for d, v in series:
        v_prev = by_date.get(f"{int(d[:4]) - 1}{d[4:]}")
        if not v_prev:  # no base observation, or a zero base
            continue
        out.append((d, (v / v_prev - 1.0) * 100.0))
    return out


def apply_mom_change(series, scale=1.0):
    """Change vs. the previous observation."""
    out = []
    for i in range(1, len(series)):
        d, v = series[i]
        _, v_prev = series[i - 1]
        out.append((d, (v - v_prev) * scale))
    return out


def diff_series(series_a, series_b):
    """Pointwise a - b, aligned by exact date (inner join)."""
    map_b = dict(series_b)
    out = []
    for d, v in series_a:
        if d in map_b:
            out.append((d, v - map_b[d]))
    return out


def quarterly_mean(series):
    """Average of a monthly series per calendar quarter, keyed by the quarter's
    first day (the date FRED gives quarterly series). Partial quarters are skipped."""
    by_quarter = {}
    for d, v in series:
        q_month = (int(d[5:7]) - 1) // 3 * 3 + 1
        by_quarter.setdefault(f"{d[:4]}-{q_month:02d}-01", []).append(v)
    return [(q, sum(vs) / len(vs)) for q, vs in sorted(by_quarter.items()) if len(vs) == 3]


def divide_by_saving_complement(series, saving_rate):
    """value / (1 - saving rate %), aligned by exact date (inner join)."""
    rates = dict(saving_rate)
    return [(d, v / (1 - rates[d] / 100)) for d, v in series if d in rates and rates[d] < 100]


def latest_and_delta(series):
    """Return (latest_value, delta_vs_prior_observation, as_of_date)."""
    if not series:
        return None, None, None
    if len(series) == 1:
        return series[-1][1], None, series[-1][0]
    _, prev_val = series[-2]
    latest_date, latest_val = series[-1]
    return latest_val, latest_val - prev_val, latest_date


def staleness(as_of_date_str, frequency, threshold_days_by_freq):
    """Returns (days_since, is_stale)."""
    if as_of_date_str is None:
        return None, True
    as_of = date.fromisoformat(as_of_date_str)
    days_since = (date.today() - as_of).days
    threshold = threshold_days_by_freq.get(frequency, 10)
    return days_since, days_since > threshold


def trim_history(series, start_date_str):
    return [(d, v) for d, v in series if d >= start_date_str]


def nearest_point(series, target_date_str):
    """Return the (date, value) pair whose date is closest to target_date_str."""
    if not series:
        return None
    target = date.fromisoformat(target_date_str)
    return min(series, key=lambda p: abs((date.fromisoformat(p[0]) - target).days))


def thin_to_weekly_before(series, cutoff_date_str):
    """Keep every observation from cutoff_date_str on; before it, keep only the
    last observation of each ISO week. Shrinks decades of daily data for charts."""
    out = []
    for d, v in series:
        if d < cutoff_date_str and out and out[-1][0] < cutoff_date_str:
            if date.fromisoformat(d).isocalendar()[:2] == date.fromisoformat(out[-1][0]).isocalendar()[:2]:
                out[-1] = (d, v)
                continue
        out.append((d, v))
    return out


def recession_ranges(series):
    """series: ascending [(date, 0|1)] recession indicator (e.g. FRED USREC).
    Returns [[first_date, last_date], ...] for each run of 1s."""
    ranges = []
    for d, v in series:
        if v >= 1:
            if ranges and ranges[-1][2]:
                ranges[-1][1] = d
            else:
                ranges.append([d, d, True])
        elif ranges:
            ranges[-1][2] = False
    return [[start, end] for start, end, _ in ranges]
