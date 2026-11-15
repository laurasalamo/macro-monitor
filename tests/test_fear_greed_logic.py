from datetime import date, timedelta

import pytest

import fear_greed_logic as fg


def test_rating_bands():
    assert fg.rating(0) == "Extreme Fear"
    assert fg.rating(24.4) == "Extreme Fear"
    assert fg.rating(25) == "Fear"
    assert fg.rating(44) == "Fear"
    assert fg.rating(45) == "Neutral"
    assert fg.rating(55) == "Neutral"
    assert fg.rating(56) == "Greed"
    assert fg.rating(75) == "Greed"
    assert fg.rating(76) == "Extreme Greed"
    assert fg.rating(100) == "Extreme Greed"
    assert fg.rating(None) is None


def test_align_carries_forward_within_gap():
    series = [("2026-01-02", 1.0), ("2026-01-05", 2.0)]
    base = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-06", "2026-01-20"]
    assert fg.align(series, base) == [None, 1.0, 1.0, 2.0, None]


def test_sma():
    assert fg.sma([1, 2, 3, 4], 2) == [None, 1.5, 2.5, 3.5]
    assert fg.sma([1, None, 3, 4], 2) == [None, None, None, 3.5]


def test_percentile_scores_extremes_and_ties():
    s = fg.percentile_scores([1, 2, 3, 4, 5], window=5, min_window=3)
    assert s[:2] == [None, None]
    assert s[2] == 100.0 and s[4] == 100.0
    assert fg.percentile_scores([5, 4, 3], window=3, min_window=3)[2] == 0.0
    assert fg.percentile_scores([2, 2, 2], window=3, min_window=3)[2] == 50.0


def test_percentile_scores_window_is_trailing():
    # The early low value drops out of a 3-wide window.
    s = fg.percentile_scores([0, 10, 5, 6], window=3, min_window=3)
    assert s[3] == pytest.approx(50.0)


def _synthetic(n, trend):
    start = date(2020, 1, 1)
    dates = [(start + timedelta(days=i)).isoformat() for i in range(n)]
    up = [100 * (1 + trend) ** i for i in range(n)]
    closes = {
        "spx": up, "rsp": up, "spy": [100.0] * n, "tlt": [100.0] * n,
        "vix": [20.0 - 5 * trend * i / n * 100 for i in range(n)], "vix3m": [21.0] * n,
    }
    spreads = {"hy": [4.0 - trend * i for i in range(n)], "ig": [1.0] * n}
    return dates, closes, spreads


def test_build_fear_greed_shape():
    dates, closes, spreads = _synthetic(700, 0.001)
    out = fg.build_fear_greed(dates, closes, spreads)
    assert out is not None
    assert out["as_of"] == dates[-1]
    assert 0 <= out["score"] <= 100
    assert out["rating"] == fg.rating(out["score"])
    assert [i["key"] for i in out["indicators"]] == [i["key"] for i in fg.INDICATORS]
    assert out["history"][-1][0] == dates[-1]
    labels = [c["label"] for c in out["compare"]]
    assert labels[0] == "Previous close"
    for ind in out["indicators"]:
        assert len(ind["lines"][0]["data"]) <= fg.CHART_DAYS


def test_narrowing_spreads_read_greedy():
    dates, closes, spreads = _synthetic(700, 0.001)
    out = fg.build_fear_greed(dates, closes, spreads)
    junk = next(i for i in out["indicators"] if i["key"] == "junk")
    assert junk["score"] == 100


def test_sudden_selloff_reads_fearful():
    dates, closes, spreads = _synthetic(700, 0.001)
    n = len(dates)
    crash = [p * (0.97 ** max(0, i - (n - 15))) for i, p in enumerate(closes["spx"])]
    closes = {**closes, "spx": crash, "rsp": crash}
    closes["vix"] = closes["vix"][:-15] + [40.0] * 15
    out = fg.build_fear_greed(dates, closes, spreads)
    by_key = {i["key"]: i for i in out["indicators"]}
    for key in ("momentum", "strength", "volatility"):
        assert by_key[key]["score"] <= 10, key


def test_build_fear_greed_needs_history():
    dates, closes, spreads = _synthetic(200, 0.001)
    assert fg.build_fear_greed(dates, closes, spreads) is None
