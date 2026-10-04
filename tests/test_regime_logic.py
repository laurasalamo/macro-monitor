"""Tests for scripts/regime_logic.py."""

import pytest

import regime_logic as regime
from regime_logic import BEARISH, BULLISH, NEUTRAL


# ---------------------------------------------------------------- rate

@pytest.mark.parametrize(
    "key,value,expected",
    [
        ("gdp_growth", 2.5, BULLISH),
        ("gdp_growth", 1.5, NEUTRAL),
        ("gdp_growth", 0.5, BEARISH),
        ("gdp_growth", -1.0, BEARISH),
        ("cpi_yoy", 2.0, BULLISH),
        ("cpi_yoy", 3.4, NEUTRAL),
        ("cpi_yoy", 4.5, BEARISH),
        ("cpi_yoy", 0.5, BEARISH),        # deflation risk
        ("cpi_yoy", -0.5, BEARISH),
        ("unemployment", 3.6, BULLISH),
        ("unemployment", 4.2, NEUTRAL),
        ("unemployment", 5.5, BEARISH),
        ("payrolls_mom", 200.0, BULLISH),
        ("payrolls_mom", 29.0, NEUTRAL),
        ("payrolls_mom", -50.0, BEARISH),
        ("spread_10y2y", 0.75, BULLISH),
        ("spread_10y2y", 0.45, NEUTRAL),
        ("spread_10y2y", -0.30, BEARISH),
        ("spread_2y3m", 0.61, BULLISH),
        ("spread_2y3m", 0.10, NEUTRAL),
        ("spread_2y3m", -0.10, BEARISH),
        ("claims_4wk", 220.0, BULLISH),
        ("claims_4wk", 275.0, NEUTRAL),
        ("claims_4wk", 340.0, BEARISH),
    ],
)
def test_rate(key, value, expected):
    assert regime.rate(key, value) == expected


@pytest.mark.parametrize(
    "key,value,expected",
    [
        # A value exactly on a cutoff gets the better state.
        ("gdp_growth", 2.0, BULLISH),
        ("gdp_growth", 1.0, NEUTRAL),
        ("cpi_yoy", 3.0, BULLISH),
        ("cpi_yoy", 1.0, BULLISH),
        ("cpi_yoy", 4.0, NEUTRAL),
        ("unemployment", 4.0, BULLISH),
        ("unemployment", 5.0, NEUTRAL),
        ("payrolls_mom", 150.0, BULLISH),
        ("payrolls_mom", 0.0, NEUTRAL),
        ("spread_10y2y", 0.5, BULLISH),
        ("spread_10y2y", 0.0, NEUTRAL),
        ("claims_4wk", 250.0, BULLISH),
        ("claims_4wk", 300.0, NEUTRAL),
    ],
)
def test_rate_boundaries(key, value, expected):
    assert regime.rate(key, value) == expected


def test_rate_uses_displayed_precision():
    # 3.04% CPI displays as "3.0%", so it must rate as the 3.0 it shows.
    assert regime.rate("cpi_yoy", 3.04) == BULLISH
    assert regime.rate("cpi_yoy", 3.06) == NEUTRAL
    # 250.4K claims displays as "250K".
    assert regime.rate("claims_4wk", 250.4) == BULLISH


def test_rate_missing_is_none():
    assert regime.rate("gdp_growth", None) is None


def test_every_indicator_has_rule_text_and_decimals():
    assert set(regime.RULE_TEXT) == set(regime.INDICATORS)
    assert set(regime.DISPLAY_DECIMALS) == set(regime.INDICATORS)


# ---------------------------------------------------------------- state_counts / classify

def test_state_counts_screenshot_example_plus_claims():
    values = {
        "gdp_growth": 2.2, "cpi_yoy": 3.4, "unemployment": 4.2, "payrolls_mom": 29.0,
        "spread_10y2y": 0.45, "spread_2y3m": 0.61, "claims_4wk": 270.0,
    }
    counts = regime.state_counts(values)
    assert counts == {BULLISH: 2, NEUTRAL: 5, BEARISH: 0}
    assert regime.classify(counts) == "Neutral"


def test_state_counts_skips_missing():
    counts = regime.state_counts({"gdp_growth": 3.0, "cpi_yoy": None})
    assert counts == {BULLISH: 1, NEUTRAL: 0, BEARISH: 0}


@pytest.mark.parametrize(
    "bull,neut,bear,expected",
    [
        (3, 4, 0, "Bullish"),   # net +3 is on the cutoff
        (2, 5, 0, "Neutral"),
        (4, 1, 2, "Neutral"),   # net +2
        (5, 0, 2, "Bullish"),
        (0, 4, 3, "Bearish"),
        (1, 2, 4, "Bearish"),
        (1, 3, 3, "Neutral"),   # net -2
        (0, 0, 0, "Neutral"),
    ],
)
def test_classify_net_score(bull, neut, bear, expected):
    assert regime.classify({BULLISH: bull, NEUTRAL: neut, BEARISH: bear}) == expected


# ---------------------------------------------------------------- history

def test_value_as_of():
    series = [("2024-01-01", 1.0), ("2024-04-01", 2.0), ("2024-07-01", 3.0)]
    assert regime.value_as_of(series, "2023-12") is None
    assert regime.value_as_of(series, "2024-01") == 1.0
    assert regime.value_as_of(series, "2024-06") == 2.0
    assert regime.value_as_of(series, "2025-01") == 3.0


def test_monthly_labels_carry_forward_latest_observation():
    bull_values = {
        "gdp_growth": 3.0, "cpi_yoy": 2.0, "unemployment": 3.5, "payrolls_mom": 200.0,
        "spread_10y2y": 1.0, "spread_2y3m": 1.0, "claims_4wk": 200.0,
    }
    series_by_key = {k: [("2024-01-01", v)] for k, v in bull_values.items()}
    # GDP turns negative and the curve inverts in March; claims spike in April.
    series_by_key["gdp_growth"].append(("2024-03-01", -1.0))
    series_by_key["spread_10y2y"].append(("2024-03-15", -0.2))
    series_by_key["spread_2y3m"].append(("2024-03-15", -0.2))
    series_by_key["claims_4wk"].append(("2024-04-06", 350.0))
    series_by_key["payrolls_mom"].append(("2024-04-01", -20.0))

    monthly = regime.monthly_labels(series_by_key, ["2024-01", "2024-02", "2024-03", "2024-04"])
    assert [(ym, label) for ym, label, _ in monthly] == [
        ("2024-01", "Bullish"),   # 7 bullish
        ("2024-02", "Bullish"),
        ("2024-03", "Neutral"),   # 4 bullish, 3 bearish
        ("2024-04", "Bearish"),   # 2 bullish, 5 bearish
    ]
    assert monthly[3][2] == {BULLISH: 2, NEUTRAL: 0, BEARISH: 5}


def test_trailing_regime_counts():
    labelled = [("2024-01", "Bullish", {}), ("2024-02", "Bullish", {}), ("2024-03", "Bearish", {})]
    assert regime.trailing_regime_counts(labelled) == {"Bullish": 2, "Neutral": 0, "Bearish": 1}


def test_trailing_regime_counts_empty_has_all_labels_zeroed():
    assert regime.trailing_regime_counts([]) == {label: 0 for label in regime.REGIME_LABELS}
