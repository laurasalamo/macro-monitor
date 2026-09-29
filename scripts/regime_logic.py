"""Deterministic macro regime classification.

All thresholds are named constants so they're easy to tune later without
touching the classification logic itself.
"""

CURVE_INVERSION_THRESHOLD = 0.0     # 10Y-2Y below this = inverted
CURVE_EXPANSION_THRESHOLD = 0.25    # pp — "meaningfully positive," not just noise near zero
TREND_LOOKBACK_QUARTERS = 4
TRAILING_MONTHS = 36

REGIME_LABELS = ["Expansion", "Slowdown", "Late Cycle", "Contraction", "Neutral"]


def classify(gdp_growth, gdp_trailing_avg, curve_10y2y):
    """Rule-based regime label. Rules are evaluated top to bottom; first match wins.

    gdp_growth: latest quarterly real GDP growth, annualized (%)
    gdp_trailing_avg: trailing 4-quarter average of the same (%)
    curve_10y2y: latest 10Y-2Y Treasury spread (pp)
    """
    if gdp_growth is None or curve_10y2y is None:
        return "Neutral"

    if gdp_growth < 0:
        return "Contraction"

    if curve_10y2y < CURVE_INVERSION_THRESHOLD:
        return "Late Cycle"

    if gdp_trailing_avg is not None and gdp_growth < gdp_trailing_avg:
        return "Slowdown"

    if gdp_trailing_avg is not None and gdp_growth >= gdp_trailing_avg and curve_10y2y >= CURVE_EXPANSION_THRESHOLD:
        return "Expansion"

    return "Neutral"


def trailing_average(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def bullish_scorecard(spread_10y2y, spread_2y3m, gdp_growth, unemployment_3mo_change, payrolls_mom, cpi_yoy):
    """Six independent binary checks; returns (count_true, total)."""
    checks = [
        spread_10y2y is not None and spread_10y2y > 0,
        spread_2y3m is not None and spread_2y3m > 0,
        gdp_growth is not None and gdp_growth > 0,
        unemployment_3mo_change is not None and unemployment_3mo_change <= 0,
        payrolls_mom is not None and payrolls_mom > 0,
        cpi_yoy is not None and cpi_yoy <= 3.0,
    ]
    return sum(1 for c in checks if c), len(checks)


def trailing_36mo_regime_counts(monthly_points):
    """monthly_points: iterable of (month_str, gdp_growth, gdp_trailing_avg, curve_10y2y).
    Returns a dict of label -> month count."""
    counts = {label: 0 for label in REGIME_LABELS}
    for _, gdp_growth, gdp_trailing_avg, curve in monthly_points:
        label = classify(gdp_growth, gdp_trailing_avg, curve)
        counts[label] += 1
    return counts
