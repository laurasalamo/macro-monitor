"""Tests for scripts/transforms.py using small hand-computed inputs."""

from datetime import date

import pytest

import transforms as tx
from series_config import STALE_THRESHOLD_DAYS


def monthly(values, year=2020):
    """[(YYYY-MM-01, v), ...] for consecutive months starting Jan `year`."""
    out = []
    for i, v in enumerate(values):
        y, m = year + i // 12, i % 12 + 1
        out.append((f"{y:04d}-{m:02d}-01", v))
    return out


# ---------------------------------------------------------------- parse

def test_parse_observations_drops_missing_and_sorts():
    raw = [
        {"date": "2024-03-01", "value": "3.5"},
        {"date": "2024-01-01", "value": "1.25"},
        {"date": "2024-02-01", "value": "."},      # FRED missing marker
        {"date": "2024-04-01", "value": None},
        {"date": "2024-05-01", "value": "abc"},    # unparseable
        {"date": "2024-06-01"},                    # no value key
        {"date": "2023-12-01", "value": "-0.5"},
    ]
    assert tx.parse_observations(raw) == [
        ("2023-12-01", -0.5),
        ("2024-01-01", 1.25),
        ("2024-03-01", 3.5),
    ]


def test_parse_observations_empty():
    assert tx.parse_observations([]) == []


# ---------------------------------------------------------------- level

def test_apply_level_identity_returns_copy():
    s = [("2024-01-01", 1.0), ("2024-01-02", 2.0)]
    out = tx.apply_level(s)
    assert out == s
    assert out is not s


def test_apply_level_scales():
    s = [("2024-01-01", 1500.0), ("2024-01-02", -250.0)]
    assert tx.apply_level(s, scale=0.001) == pytest.approx(
        [("2024-01-01", 1.5), ("2024-01-02", -0.25)]
    )


# ---------------------------------------------------------------- yoy

def test_apply_yoy_matches_12_observations_back():
    # 100 for the first year, then 110, 105, 90 -> +10%, +5%, -10%
    s = monthly([100.0] * 12 + [110.0, 105.0, 90.0])
    out = tx.apply_yoy(s)
    assert [d for d, _ in out] == ["2021-01-01", "2021-02-01", "2021-03-01"]
    assert [v for _, v in out] == pytest.approx([10.0, 5.0, -10.0])


def test_apply_yoy_short_series_is_empty():
    assert tx.apply_yoy(monthly([100.0] * 12)) == []
    assert tx.apply_yoy([]) == []


def test_apply_yoy_with_missing_month_uses_same_calendar_month():
    # 2020: Jan..Dec = 100..111; 2021: Jan..Dec = 110..121 -> every true YoY is +10% of
    # the base month, i.e. (110+k)/(100+k)-1. Drop Jul 2020 as FRED '.' would.
    raw = [{"date": d, "value": str(v)} for d, v in monthly([100.0 + k for k in range(12)] +
                                                            [110.0 + k for k in range(12)])]
    raw = [o for o in raw if o["date"] != "2020-07-01"]
    out = dict(tx.apply_yoy(tx.parse_observations(raw)))
    # Feb 2021 compares to Feb 2020 (111 / 101 - 1 = +9.90%), not to Jan 2020 as a
    # "12 observations back" match would. Jan 2021 keeps its value; Jul 2021 has no base.
    assert out["2021-02-01"] == pytest.approx((111.0 / 101.0 - 1) * 100)
    assert out["2021-01-01"] == pytest.approx(10.0)
    assert "2021-07-01" not in out


def test_apply_yoy_skips_zero_base():
    s = monthly([0.0] + [100.0] * 11 + [50.0, 120.0])
    out = tx.apply_yoy(s)
    # Jan 2021 is dropped (base 0), Feb 2021 is +20%.
    assert out == [("2021-02-01", pytest.approx(20.0))]


# ---------------------------------------------------------------- mom change

def test_apply_mom_change():
    s = monthly([100.0, 103.0, 101.5])
    assert tx.apply_mom_change(s) == [
        ("2020-02-01", pytest.approx(3.0)),
        ("2020-03-01", pytest.approx(-1.5)),
    ]


def test_apply_mom_change_with_scale():
    # e.g. payrolls in thousands -> millions
    s = monthly([150000.0, 150250.0])
    assert tx.apply_mom_change(s, scale=0.001) == [("2020-02-01", pytest.approx(0.25))]


def test_apply_mom_change_too_short():
    assert tx.apply_mom_change(monthly([1.0])) == []
    assert tx.apply_mom_change([]) == []


# ---------------------------------------------------------------- diff

def test_diff_series_inner_join_on_date():
    a = [("2024-01-01", 4.0), ("2024-01-02", 4.5), ("2024-01-03", 4.25)]
    b = [("2024-01-01", 3.75), ("2024-01-03", 4.5), ("2024-01-04", 1.0)]
    assert tx.diff_series(a, b) == [
        ("2024-01-01", pytest.approx(0.25)),
        ("2024-01-03", pytest.approx(-0.25)),
    ]


def test_diff_series_no_overlap():
    assert tx.diff_series([("2024-01-01", 1.0)], [("2024-01-02", 1.0)]) == []


# ---------------------------------------------------------------- latest/delta

def test_latest_and_delta():
    s = [("2024-01-01", 2.0), ("2024-02-01", 2.5), ("2024-03-01", 2.25)]
    latest, delta, as_of = tx.latest_and_delta(s)
    assert latest == 2.25
    assert delta == pytest.approx(-0.25)
    assert as_of == "2024-03-01"


def test_latest_and_delta_single_point():
    assert tx.latest_and_delta([("2024-01-01", 7.0)]) == (7.0, None, "2024-01-01")


def test_latest_and_delta_empty():
    assert tx.latest_and_delta([]) == (None, None, None)


# ---------------------------------------------------------------- staleness

FIXED_TODAY = date(2026, 9, 30)


class _FixedDate(date):
    @classmethod
    def today(cls):
        return cls(FIXED_TODAY.year, FIXED_TODAY.month, FIXED_TODAY.day)


@pytest.fixture
def frozen_today(monkeypatch):
    monkeypatch.setattr(tx, "date", _FixedDate)
    return FIXED_TODAY


THRESHOLDS = {"daily": 5, "weekly": 14, "monthly": 70, "quarterly": 210}


def _days_ago(n):
    return date.fromordinal(FIXED_TODAY.toordinal() - n).isoformat()


@pytest.mark.parametrize("freq,threshold", sorted(THRESHOLDS.items()))
def test_staleness_boundary_is_strictly_greater_than(frozen_today, freq, threshold):
    # Exactly at the threshold -> still fresh; one day over -> stale.
    assert tx.staleness(_days_ago(threshold), freq, THRESHOLDS) == (threshold, False)
    assert tx.staleness(_days_ago(threshold + 1), freq, THRESHOLDS) == (threshold + 1, True)


def test_staleness_today_is_fresh(frozen_today):
    assert tx.staleness(FIXED_TODAY.isoformat(), "daily", THRESHOLDS) == (0, False)


def test_staleness_unknown_frequency_defaults_to_10_days(frozen_today):
    assert tx.staleness(_days_ago(10), "annual", THRESHOLDS) == (10, False)
    assert tx.staleness(_days_ago(11), "annual", THRESHOLDS) == (11, True)
    assert tx.staleness(_days_ago(11), "daily", {}) == (11, True)


def test_staleness_none_date_is_stale(frozen_today):
    assert tx.staleness(None, "daily", THRESHOLDS) == (None, True)


def test_staleness_future_date_is_not_stale(frozen_today):
    days, stale = tx.staleness("2026-10-05", "daily", THRESHOLDS)
    assert days == -5
    assert stale is False


def test_staleness_real_config_monthly_release_lag(frozen_today):
    # series_config comment: August CPI (dated 2026-08-01) released mid-Sep is
    # ~60 days "old" at end of Sep and must not be flagged stale.
    days, stale = tx.staleness("2026-08-01", "monthly", STALE_THRESHOLD_DAYS)
    assert days == 60
    assert stale is False


def test_stale_threshold_config_covers_known_frequencies():
    assert set(STALE_THRESHOLD_DAYS) >= {"daily", "weekly", "monthly", "quarterly"}
    assert (STALE_THRESHOLD_DAYS["daily"] < STALE_THRESHOLD_DAYS["weekly"]
            < STALE_THRESHOLD_DAYS["monthly"] < STALE_THRESHOLD_DAYS["quarterly"])


# ---------------------------------------------------------------- trim / nearest

def test_trim_history_inclusive_start():
    s = monthly([1.0, 2.0, 3.0, 4.0])
    assert tx.trim_history(s, "2020-03-01") == [("2020-03-01", 3.0), ("2020-04-01", 4.0)]
    assert tx.trim_history(s, "2021-01-01") == []
    assert tx.trim_history(s, "1900-01-01") == s


def test_nearest_point():
    s = [("2024-01-01", 1.0), ("2024-01-10", 2.0), ("2024-02-01", 3.0)]
    assert tx.nearest_point(s, "2024-01-08") == ("2024-01-10", 2.0)
    assert tx.nearest_point(s, "2023-06-01") == ("2024-01-01", 1.0)
    assert tx.nearest_point(s, "2025-01-01") == ("2024-02-01", 3.0)
    assert tx.nearest_point(s, "2024-01-10") == ("2024-01-10", 2.0)


def test_nearest_point_tie_picks_earlier():
    # 2024-01-05 is 4 days from both neighbours; min() keeps the first.
    s = [("2024-01-01", 1.0), ("2024-01-09", 2.0)]
    assert tx.nearest_point(s, "2024-01-05") == ("2024-01-01", 1.0)


def test_nearest_point_empty():
    assert tx.nearest_point([], "2024-01-01") is None


# ---------------------------------------------------------------- thinning / recessions

def test_thin_to_weekly_before_keeps_last_day_of_each_old_week():
    # 2024-01-01 is a Monday; 01-08 starts the next ISO week.
    s = [("2024-01-01", 1.0), ("2024-01-03", 2.0), ("2024-01-05", 3.0),
         ("2024-01-08", 4.0), ("2024-01-09", 5.0),
         ("2024-01-15", 6.0), ("2024-01-16", 7.0)]
    assert tx.thin_to_weekly_before(s, "2024-01-15") == [
        ("2024-01-05", 3.0), ("2024-01-09", 5.0),
        ("2024-01-15", 6.0), ("2024-01-16", 7.0),
    ]


def test_thin_to_weekly_before_cutoff_week_straddle():
    # Points on either side of the cutoff in the same week are both kept.
    s = [("2024-01-08", 1.0), ("2024-01-10", 2.0), ("2024-01-11", 3.0)]
    assert tx.thin_to_weekly_before(s, "2024-01-11") == [("2024-01-10", 2.0), ("2024-01-11", 3.0)]


def test_thin_to_weekly_before_empty():
    assert tx.thin_to_weekly_before([], "2024-01-01") == []


def test_recession_ranges():
    s = monthly([0, 1, 1, 0, 0, 1, 0, 1])
    assert tx.recession_ranges(s) == [
        ["2020-02-01", "2020-03-01"],
        ["2020-06-01", "2020-06-01"],
        ["2020-08-01", "2020-08-01"],
    ]


def test_recession_ranges_none():
    assert tx.recession_ranges(monthly([0, 0])) == []
    assert tx.recession_ranges([]) == []
