"""Tests for scripts/regime_logic.py."""

import pytest

import regime_logic as regime


# ---------------------------------------------------------------- classify

@pytest.mark.parametrize(
    "gdp,avg,curve,expected",
    [
        # Clear-cut cases for each label
        (3.0, 2.0, 1.00, "Expansion"),      # growth above trend, steep curve
        (1.0, 2.5, 0.80, "Slowdown"),       # growth below trend, positive curve
        (2.5, 2.0, -0.40, "Late Cycle"),    # positive growth, inverted curve
        (-1.5, 2.0, 1.00, "Contraction"),   # negative growth
        (2.5, 2.0, 0.10, "Neutral"),        # above trend but curve only barely positive
    ],
)
def test_classify_clear_cut(gdp, avg, curve, expected):
    assert regime.classify(gdp, avg, curve) == expected


def test_classify_contraction_wins_over_inversion():
    # Rules are first-match; negative growth beats an inverted curve.
    assert regime.classify(-0.1, 2.0, -1.0) == "Contraction"


def test_classify_late_cycle_wins_over_slowdown():
    assert regime.classify(0.5, 3.0, -0.2) == "Late Cycle"


@pytest.mark.parametrize(
    "gdp,avg,curve",
    [(None, 2.0, 1.0), (2.0, 2.0, None), (None, None, None)],
)
def test_classify_missing_growth_or_curve_is_neutral(gdp, avg, curve):
    assert regime.classify(gdp, avg, curve) == "Neutral"


def test_classify_missing_trailing_avg():
    # Without a trend reference, neither Slowdown nor Expansion can fire...
    assert regime.classify(3.0, None, 1.0) == "Neutral"
    # ...but Contraction and Late Cycle don't need it.
    assert regime.classify(-1.0, None, 1.0) == "Contraction"
    assert regime.classify(1.0, None, -0.5) == "Late Cycle"


def test_classify_boundaries():
    # Zero growth is not a contraction.
    assert regime.classify(0.0, 0.0, 1.0) == "Expansion"
    # Curve exactly at 0 is not inverted.
    assert regime.classify(2.0, 1.0, regime.CURVE_INVERSION_THRESHOLD) == "Neutral"
    # Curve exactly at the expansion threshold qualifies (>=).
    assert regime.classify(2.0, 1.0, regime.CURVE_EXPANSION_THRESHOLD) == "Expansion"
    assert regime.classify(2.0, 1.0, regime.CURVE_EXPANSION_THRESHOLD - 1e-9) == "Neutral"
    # Growth equal to trend is not a slowdown (>= for Expansion).
    assert regime.classify(2.0, 2.0, 1.0) == "Expansion"
    assert regime.classify(2.0 - 1e-9, 2.0, 1.0) == "Slowdown"


def test_classify_always_returns_known_label():
    values = [None, -2.0, 0.0, 0.1, 2.0, 5.0]
    curves = [None, -1.0, 0.0, 0.1, 0.25, 2.0]
    for g in values:
        for a in values:
            for c in curves:
                assert regime.classify(g, a, c) in regime.REGIME_LABELS


# ---------------------------------------------------------------- trailing_average

def test_trailing_average():
    assert regime.trailing_average([1.0, 2.0, 3.0, 6.0]) == pytest.approx(3.0)


def test_trailing_average_ignores_none():
    assert regime.trailing_average([None, 2.0, None, 4.0]) == pytest.approx(3.0)


def test_trailing_average_all_missing():
    assert regime.trailing_average([]) is None
    assert regime.trailing_average([None, None]) is None


# ---------------------------------------------------------------- bullish_scorecard

def test_bullish_scorecard_all_bullish():
    assert regime.bullish_scorecard(1.0, 0.5, 2.0, -0.1, 150.0, 2.5) == (6, 6)


def test_bullish_scorecard_all_bearish():
    assert regime.bullish_scorecard(-0.5, -0.2, -1.0, 0.3, -20.0, 5.0) == (0, 6)


def test_bullish_scorecard_all_missing_counts_as_not_bullish():
    assert regime.bullish_scorecard(None, None, None, None, None, None) == (0, 6)


def test_bullish_scorecard_boundaries():
    # Strict > 0 for spreads/GDP/payrolls; <= for unemployment change and CPI.
    assert regime.bullish_scorecard(0.0, 0.0, 0.0, 0.0, 0.0, 3.0) == (2, 6)
    assert regime.bullish_scorecard(None, None, None, 0.01, None, 3.01) == (0, 6)


# ---------------------------------------------------------------- regime counts

def test_trailing_36mo_regime_counts():
    points = [
        ("2024-01", 3.0, 2.0, 1.0),     # Expansion
        ("2024-02", 3.0, 2.0, 1.0),     # Expansion
        ("2024-03", 1.0, 2.0, 1.0),     # Slowdown
        ("2024-04", 1.0, 2.0, -0.5),    # Late Cycle
        ("2024-05", -1.0, 2.0, 1.0),    # Contraction
        ("2024-06", None, None, 1.0),   # Neutral (missing GDP)
    ]
    counts = regime.trailing_36mo_regime_counts(points)
    assert counts == {
        "Expansion": 2,
        "Slowdown": 1,
        "Late Cycle": 1,
        "Contraction": 1,
        "Neutral": 1,
    }
    assert sum(counts.values()) == len(points)


def test_trailing_36mo_regime_counts_empty_has_all_labels_zeroed():
    assert regime.trailing_36mo_regime_counts([]) == {label: 0 for label in regime.REGIME_LABELS}
