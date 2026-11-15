import pytest

import breadth_indicators as bi


def test_ema_and_sma_and_cumsum():
    assert bi.ema([10, None, 20], 0.5) == [10, None, 15.0]
    assert bi.sma([1, 2, 3, None, 5], 2) == [None, 1.5, 2.5, None, 4.0]
    assert bi.cumsum([1, None, 2], start=10) == [11, None, 13]


def _days(n):
    return [f"2026-01-{i + 1:02d}" for i in range(n)]


def test_daily_counts_advances_declines_and_volume():
    dates = _days(3)
    close = [[1.0, 2.0, 1.0], [5.0, 4.0, 4.0]]
    volume = [[0, 100, 300], [0, 50, 70]]
    c = bi.daily_counts(dates, close, close, close, volume, min_coverage=1.0)
    assert c["adv"] == [None, 1, 0]
    assert c["dec"] == [None, 1, 1]      # day 3: second stock unchanged
    assert c["up_vol"] == [None, 100, 0]
    assert c["down_vol"] == [None, 50, 300]


def test_daily_counts_coverage_drops_thin_days():
    dates = _days(3)
    close = [[1.0, 2.0, 3.0], [1.0, None, 3.0]]
    vol = [[1, 1, 1], [1, 1, 1]]
    c = bi.daily_counts(dates, close, close, close, vol, min_coverage=0.9)
    assert c["adv"] == [None, None, None]  # stock 2 can't be compared on days 2 or 3


def test_new_highs_and_lows(monkeypatch):
    monkeypatch.setattr(bi, "HL_DAYS", 3)
    dates = _days(5)
    up = [1.0, 2.0, 3.0, 2.5, 4.0]
    down = [5.0, 4.0, 3.0, 3.5, 2.0]
    vol = [[1] * 5, [1] * 5]
    c = bi.daily_counts(dates, [up, down], [up, down], [up, down], vol, min_coverage=1.0)
    assert c["nh"] == [None, None, 1, 0, 1]
    assert c["nl"] == [None, None, 1, 0, 1]


def test_new_high_window_drops_old_peak(monkeypatch):
    monkeypatch.setattr(bi, "HL_DAYS", 3)
    s = [10.0, 1.0, 2.0, 3.0]
    c = bi.daily_counts(_days(4), [s], [s], [s], [[1] * 4], min_coverage=1.0)
    assert c["nh"] == [None, None, 0, 1]  # the 10 has left the window by day 4


def _synthetic(n=400, stocks=10):
    dates = [f"d{i:04d}" for i in range(n)]
    close = [[100 + (i * (s + 1) % 7) + i * 0.05 for i in range(n)] for s in range(stocks)]
    vol = [[1000.0] * n for _ in range(stocks)]
    return dates, close, vol


def test_build_indicators_shape():
    dates, close, vol = _synthetic()
    counts = bi.daily_counts(dates, close, close, close, vol)
    out = bi.build_indicators(dates, counts, index_closes=[4000.0 + i for i in range(len(dates))])
    assert out["as_of"] == dates[-1]
    assert [i["key"] for i in out["indicators"]] == bi.ORDER
    for ind in out["indicators"]:
        assert ind["theory"] and ind["interpretation"] and ind["latest_text"]
        assert ind["lines"] and all(line["data"] for line in ind["lines"])
    ad = out["indicators"][0]
    assert ad["lines"][-1]["axis"] == "y2"


def test_mcclellan_is_zero_for_constant_breadth():
    n = 120
    dates = [f"d{i:04d}" for i in range(n)]
    counts = {
        "adv": [None] + [60] * (n - 1), "dec": [None] + [40] * (n - 1),
        "issues": [None] + [100] * (n - 1),
        "up_vol": [None] + [1.0] * (n - 1), "down_vol": [None] + [1.0] * (n - 1),
        "nh": [None] * n, "nl": [None] * n,
        "pct_above": {m: [None] * n for m in bi.MA_SET},
    }
    out = bi.build_indicators(dates, counts)
    mcc = next(i for i in out["indicators"] if i["key"] == "mcclellan")
    assert mcc["latest"] == pytest.approx(0.0)
    adn = next(i for i in out["indicators"] if i["key"] == "adn")
    assert adn["latest"] == pytest.approx(200.0)  # (60-40)/100*1000


def test_summation_equals_running_total_of_oscillator():
    n = 300
    dates = [f"d{i:04d}" for i in range(n)]
    adv = [None] + [50 + (i * 37 % 41) for i in range(1, n)]
    dec = [None] + [100 - a for a in adv[1:]]
    counts = {
        "adv": adv, "dec": dec, "issues": [None] + [100] * (n - 1),
        "up_vol": [None] + [1.0] * (n - 1), "down_vol": [None] + [1.0] * (n - 1),
        "nh": [None] * n, "nl": [None] * n, "pct_above": {m: [None] * n for m in bi.MA_SET},
    }
    out = {i["key"]: i for i in bi.build_indicators(dates, counts)["indicators"]}
    osc = [v for _, v in out["mcclellan"]["lines"][0]["data"]]
    rasi = [v for _, v in out["summation"]["lines"][0]["data"]]
    # day-to-day change of RASI is the oscillator (up to rounding)
    for k in range(1, len(rasi)):
        assert rasi[k] - rasi[k - 1] == pytest.approx(osc[k], abs=0.2)
