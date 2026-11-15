import pytest

import breadth_logic as b


def test_zone_thresholds():
    assert b.zone(None) is None
    assert b.zone(19.9) == "High risk"
    assert b.zone(20) == "Risk"
    assert b.zone(24.9) == "Risk"
    assert b.zone(25) == "Normal"


def test_pct_above_sma_counts_only_full_windows():
    dates = ["d1", "d2", "d3", "d4"]
    up = [1.0, 2.0, 3.0, 4.0]      # above its 2-day average from d2 on
    down = [4.0, 3.0, 2.0, 1.0]    # below
    out = b.pct_above_sma(dates, [up, down], n=2, min_coverage=1.0)
    assert out == [("d2", 50.0), ("d3", 50.0), ("d4", 50.0)]


def test_pct_above_sma_gap_restarts_average_and_coverage_filter():
    dates = ["d1", "d2", "d3", "d4", "d5"]
    a = [1.0, 2.0, None, 3.0, 4.0]
    c = [1.0, 2.0, 3.0, 4.0, 5.0]
    out = dict(b.pct_above_sma(dates, [a, c], n=2, min_coverage=1.0))
    # d3/d4: `a` has no full window after its gap, so coverage is 1/2 -> dropped
    assert set(out) == {"d2", "d5"}
    out_half = dict(b.pct_above_sma(dates, [a, c], n=2, min_coverage=0.5))
    assert out_half["d3"] == 100.0 and out_half["d4"] == 100.0


def test_pct_above_sma_rolling_sum_matches_naive():
    closes = [10, 11, 9, 12, 13, 8, 7, 15, 14, 16]
    dates = [f"d{i}" for i in range(len(closes))]
    out = dict(b.pct_above_sma(dates, [[float(c) for c in closes]], n=3, min_coverage=1.0))
    for i in range(2, len(closes)):
        avg = sum(closes[i - 2:i + 1]) / 3
        assert out[f"d{i}"] == (100.0 if closes[i] > avg else 0.0)


def test_build_breadth_summary():
    series = [(f"2026-{m:02d}-{d:02d}", float(v))
              for (m, d), v in zip([(m, d) for m in range(1, 12) for d in (1, 15)], range(10, 98, 4))]
    out = b.build_breadth(series, 503, 500)
    assert out["as_of"] == series[-1][0]
    assert out["latest"] == series[-1][1]
    assert out["delta"] == pytest.approx(4.0)
    assert out["zone"] == "Normal"
    assert out["low_52w"] == 10.0
    assert out["days_below_risk_1y"] == 4  # 10, 14, 18, 22
    assert [c["label"] for c in out["compare"]] == ["1 week ago", "1 month ago", "3 months ago"]
    assert b.build_breadth([], 503, 0) is None


def test_constituents_file():
    tickers = b.load_constituents()
    assert len(tickers) >= 490
    assert len(set(tickers)) == len(tickers)
    assert all("." not in t for t in tickers)  # Yahoo uses BRK-B, not BRK.B
