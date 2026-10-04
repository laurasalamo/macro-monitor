"""Deterministic macro regime classification.

Each indicator is rated bullish / neutral / bearish against the bands in
THRESHOLDS, and the headline regime comes from the net score (bullish count
minus bearish count). All thresholds are named constants so they're easy to
tune later without touching the classification logic itself.
"""

BULLISH, NEUTRAL, BEARISH = "bullish", "neutral", "bearish"
STATES = [BULLISH, NEUTRAL, BEARISH]

# Per indicator: inclusive (low, high) bands, None = unbounded. The bullish band
# is checked first, then neutral; anything outside both is bearish. Bands are
# inclusive, so a value exactly on a cutoff gets the better state.
THRESHOLDS = {
    "gdp_growth":   {BULLISH: (2.0, None),   NEUTRAL: (1.0, None)},
    # Two-sided: below 1% is bearish too (deflation risk).
    "cpi_yoy":      {BULLISH: (1.0, 3.0),    NEUTRAL: (1.0, 4.0)},
    "unemployment": {BULLISH: (None, 4.0),   NEUTRAL: (None, 5.0)},
    "payrolls_mom": {BULLISH: (150.0, None), NEUTRAL: (0.0, None)},
    "spread_10y2y": {BULLISH: (0.5, None),   NEUTRAL: (0.0, None)},
    "spread_2y3m":  {BULLISH: (0.5, None),   NEUTRAL: (0.0, None)},
    "claims_4wk":   {BULLISH: (None, 250.0), NEUTRAL: (None, 300.0)},
}

# Human-readable version of THRESHOLDS, shown in the chart pop-ups. Keep in sync.
RULE_TEXT = {
    "gdp_growth":   "Bullish ≥ 2.0% · Neutral 1.0–2.0% · Bearish < 1.0%",
    "cpi_yoy":      "Bullish 1.0–3.0% · Neutral 3.0–4.0% · Bearish > 4.0% or < 1.0%",
    "unemployment": "Bullish ≤ 4.0% · Neutral 4.0–5.0% · Bearish > 5.0%",
    "payrolls_mom": "Bullish ≥ +150K · Neutral 0 to +150K · Bearish < 0",
    "spread_10y2y": "Bullish ≥ +0.50pp · Neutral 0 to +0.50pp · Bearish < 0 (inverted)",
    "spread_2y3m":  "Bullish ≥ +0.50pp · Neutral 0 to +0.50pp · Bearish < 0 (inverted)",
    "claims_4wk":   "Bullish ≤ 250K · Neutral 250–300K · Bearish > 300K",
}

# Values are rated after rounding to the precision the cards display, so a card
# never shows a number that looks like it's on the other side of a cutoff.
DISPLAY_DECIMALS = {
    "gdp_growth": 1,
    "cpi_yoy": 1,
    "unemployment": 1,
    "payrolls_mom": 0,
    "spread_10y2y": 2,
    "spread_2y3m": 2,
    "claims_4wk": 0,
}

INDICATORS = list(THRESHOLDS)

NET_SCORE_THRESHOLD = 3  # net >= +3 -> Bullish, net <= -3 -> Bearish
TRAILING_MONTHS = 36

REGIME_LABELS = ["Bullish", "Neutral", "Bearish"]


def _in_band(value, band):
    low, high = band
    return (low is None or value >= low) and (high is None or value <= high)


def rate(key, value):
    """bullish / neutral / bearish for one indicator, or None if value is missing."""
    if value is None:
        return None
    value = round(value, DISPLAY_DECIMALS[key])
    bands = THRESHOLDS[key]
    if _in_band(value, bands[BULLISH]):
        return BULLISH
    if _in_band(value, bands[NEUTRAL]):
        return NEUTRAL
    return BEARISH


def state_counts(values):
    """values: dict of indicator key -> latest value (missing keys/None are skipped).
    Returns {"bullish": n, "neutral": n, "bearish": n}."""
    counts = {s: 0 for s in STATES}
    for key in INDICATORS:
        state = rate(key, values.get(key))
        if state:
            counts[state] += 1
    return counts


def classify(counts):
    """Headline label from state counts, by net score (bullish - bearish)."""
    net = counts[BULLISH] - counts[BEARISH]
    if net >= NET_SCORE_THRESHOLD:
        return "Bullish"
    if net <= -NET_SCORE_THRESHOLD:
        return "Bearish"
    return "Neutral"


def value_as_of(series, year_month):
    """Last value in an ascending [(date, value)] series dated in or before year_month ("YYYY-MM")."""
    latest = None
    for d, v in series:
        if d[:7] > year_month:
            break
        latest = v
    return latest


def monthly_labels(series_by_key, months):
    """Classify each month using every indicator's latest observation up to it.
    series_by_key: indicator key -> ascending [(date, value)].
    Returns [(month, label, state_counts)]."""
    out = []
    for ym in months:
        values = {k: value_as_of(s, ym) for k, s in series_by_key.items()}
        counts = state_counts(values)
        out.append((ym, classify(counts), counts))
    return out


def trailing_regime_counts(labelled_months):
    """labelled_months: iterable of (month, label, ...). Returns a dict of label -> month count."""
    counts = {label: 0 for label in REGIME_LABELS}
    for _, label, *_ in labelled_months:
        counts[label] += 1
    return counts
