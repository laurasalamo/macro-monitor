"""Tests for scripts/momentum_logic.py and the invariants in momentum_config.py."""

import math
import statistics

import pytest

import momentum_config as cfg
import momentum_logic as mom

N_DAYS = 300  # > cfg.MIN_HISTORY_DAYS


def closes_from_log_returns(log_returns, start=100.0):
    closes = [start]
    for r in log_returns:
        closes.append(closes[-1] * math.exp(r))
    return closes


def noise(i, amp):
    """Period-3 zero-sum return noise (+a, +a, -2a). Every lookback in
    momentum_config (21/63/126/252) is a multiple of 3, so the noise adds
    volatility without biasing any horizon return or the acceleration signal."""
    return (amp, amp, -2 * amp)[i % 3]


def ticker_data(closes, volume=1_000_000):
    return {"closes": closes, "volumes": [volume] * len(closes)}


# ---------------------------------------------------------------- config

def test_composite_weights_sum_to_one():
    total = cfg.WEIGHT_TREND + cfg.WEIGHT_ACCEL + cfg.WEIGHT_MAXPROX + cfg.WEIGHT_LOWVOL
    assert total == pytest.approx(1.0)


def test_trend_blend_sums_to_one():
    assert sum(cfg.TREND_BLEND.values()) == pytest.approx(1.0)
    assert set(cfg.TREND_BLEND) == {"1m", "3m", "6m", "12m"}


def test_min_history_covers_lookbacks():
    assert cfg.MIN_HISTORY_DAYS > cfg.LB_12M
    assert cfg.MIN_HISTORY_DAYS > 2 * cfg.LB_3M  # acceleration lookback
    assert cfg.LB_1M < cfg.LB_3M < cfg.LB_6M < cfg.LB_12M


def test_universe_tickers_unique():
    tickers = [t for t, _, _ in cfg.UNIVERSE]
    assert len(tickers) == len(set(tickers))


# ---------------------------------------------------------------- trading_return

def test_trading_return():
    closes = [100.0, 105.0, 110.0, 121.0]
    assert mom.trading_return(closes, 1) == pytest.approx(10.0)
    assert mom.trading_return(closes, 3) == pytest.approx(21.0)


def test_trading_return_insufficient_history():
    assert mom.trading_return([100.0, 110.0], 2) is None
    assert mom.trading_return([], 1) is None


def test_trading_return_zero_base():
    assert mom.trading_return([0.0, 10.0], 1) is None


# ---------------------------------------------------------------- realized vol

def test_realized_vol_constant_prices_is_zero():
    assert mom.realized_vol_annualized([50.0] * 10, 5) == 0.0


def test_realized_vol_matches_hand_calc():
    closes = [100.0, 110.0, 99.0, 108.9]
    rets = [math.log(110 / 100), math.log(99 / 110), math.log(108.9 / 99)]
    expected = statistics.pstdev(rets) * math.sqrt(252) * 100
    assert mom.realized_vol_annualized(closes, 3) == pytest.approx(expected)


def test_realized_vol_uses_only_trailing_window():
    # Wild early moves must not affect a window covering only the calm tail.
    closes = [100.0, 300.0, 50.0] + [100.0] * 6
    assert mom.realized_vol_annualized(closes, 5) == 0.0


def test_realized_vol_insufficient_history():
    assert mom.realized_vol_annualized([100.0, 101.0], 2) is None
    # Only one usable return -> None
    assert mom.realized_vol_annualized([100.0, 101.0], 1) is None


# ---------------------------------------------------------------- distance from high

def test_distance_from_high():
    assert mom.distance_from_high([80.0, 100.0, 90.0], 3) == pytest.approx(-10.0)
    assert mom.distance_from_high([80.0, 90.0, 100.0], 3) == 0.0


def test_distance_from_high_window_excludes_old_peak():
    closes = [200.0, 90.0, 100.0, 95.0]
    assert mom.distance_from_high(closes, 3) == pytest.approx(-5.0)


def test_distance_from_high_short_history_uses_all():
    assert mom.distance_from_high([100.0, 50.0], 10) == pytest.approx(-50.0)


# ---------------------------------------------------------------- relative volume

def test_relative_volume():
    volumes = [100.0] * 8 + [200.0, 200.0]
    # recent 2 avg = 200, base 10 avg = 120
    assert mom.relative_volume(volumes, 2, 10) == pytest.approx(200 / 120)


def test_relative_volume_insufficient_or_zero():
    assert mom.relative_volume([1.0] * 4, 2, 5) is None
    assert mom.relative_volume([0.0] * 5, 2, 5) is None


# ---------------------------------------------------------------- percentile_ranks

def test_percentile_ranks_spread_0_to_100():
    ranks = mom.percentile_ranks([("a", 3.0), ("b", 1.0), ("c", 2.0), ("d", 10.0), ("e", -5.0)])
    assert ranks == pytest.approx({"e": 0.0, "b": 25.0, "c": 50.0, "a": 75.0, "d": 100.0})


def test_percentile_ranks_ties_share_average_rank():
    ranks = mom.percentile_ranks([("a", 1.0), ("b", 2.0), ("c", 2.0), ("d", 3.0)])
    # positions 0,1,2,3 over n-1=3 -> b,c share (1+2)/2 = 1.5 -> 50
    assert ranks == pytest.approx({"a": 0.0, "b": 50.0, "c": 50.0, "d": 100.0})


def test_percentile_ranks_all_equal():
    ranks = mom.percentile_ranks([("a", 5.0), ("b", 5.0), ("c", 5.0)])
    assert ranks == pytest.approx({"a": 50.0, "b": 50.0, "c": 50.0})


def test_percentile_ranks_none_excluded():
    ranks = mom.percentile_ranks([("a", None), ("b", 1.0), ("c", 2.0)])
    assert ranks == pytest.approx({"b": 0.0, "c": 100.0})


def test_percentile_ranks_single_and_empty():
    assert mom.percentile_ranks([("a", 42.0)]) == {"a": 50.0}
    assert mom.percentile_ranks([]) == {}
    assert mom.percentile_ranks([("a", None)]) == {}


# ---------------------------------------------------------------- build_rankings

def _leader():
    # Accelerating uptrend, smooth -> top trend, top accel, at 52w high, lowest vol.
    return closes_from_log_returns([0.0005 + 0.00001 * i for i in range(N_DAYS)])


def _middle():
    # Steady uptrend with mild noise; the last return (i=299, 299 % 3 == 2) is
    # the down leg, so it sits just below its 52-week high.
    return closes_from_log_returns(
        [0.0008 + noise(i, 0.005) for i in range(N_DAYS)]
    )


def _laggard():
    # Accelerating downtrend with big noise -> worst on every component.
    return closes_from_log_returns(
        [-0.0005 - 0.00001 * i + noise(i, 0.02) for i in range(N_DAYS)]
    )


@pytest.fixture
def universe():
    return {
        "LEAD": ticker_data(_leader()),
        "MID": ticker_data(_middle()),
        "LAG": ticker_data(_laggard()),
    }


def test_build_rankings_ordering_and_extremes(universe):
    rows = mom.build_rankings(universe)
    assert [r["ticker"] for r in rows] == ["LEAD", "MID", "LAG"]
    assert [r["rank"] for r in rows] == [1, 2, 3]

    lead, mid, lag = rows
    # Leader dominates every component -> 100 everywhere; laggard -> 0 everywhere.
    assert (lead["tend"], lead["acel"], lead["max"], lead["vol"], lead["score"]) == (100, 100, 100, 100, 100)
    assert (lag["tend"], lag["acel"], lag["max"], lag["vol"], lag["score"]) == (0, 0, 0, 0, 0)
    assert (mid["tend"], mid["acel"], mid["max"], mid["vol"], mid["score"]) == (50, 50, 50, 50, 50)


def test_build_rankings_row_fields(universe):
    rows = mom.build_rankings(universe)
    expected_keys = {
        "ticker", "score", "tend", "acel", "max", "vol",
        "ret_1m", "ret_3m", "ret_6m", "ret_12m", "from_high", "rvol", "rank",
    }
    for r in rows:
        assert set(r) == expected_keys
        for k in ("score", "tend", "acel", "max", "vol"):
            assert 0 <= r[k] <= 100
        assert r["from_high"] <= 0
        assert r["rvol"] == pytest.approx(1.0)  # constant synthetic volume

    lead = rows[0]
    closes = universe["LEAD"]["closes"]
    assert lead["ret_1m"] == round(mom.trading_return(closes, cfg.LB_1M), 1)
    assert lead["ret_12m"] == round(mom.trading_return(closes, cfg.LB_12M), 1)
    assert lead["from_high"] == 0.0


def test_build_rankings_composite_uses_config_weights():
    # Build a universe where tickers win on different components so that the
    # composite actually depends on the weights.
    # A: strongest trend but volatile. B: calm but flat. C: in between.
    data = {
        "A": ticker_data(closes_from_log_returns(
            [0.003 + noise(i, 0.03) for i in range(N_DAYS)])),
        "B": ticker_data(closes_from_log_returns([0.0 for _ in range(N_DAYS)])),
        "C": ticker_data(closes_from_log_returns(
            [0.001 + noise(i, 0.01) for i in range(N_DAYS)])),
        "D": ticker_data(closes_from_log_returns(
            [-0.001 + 0.00001 * i + noise(i, 0.002) for i in range(N_DAYS)])),
    }
    rows = mom.build_rankings(data)
    assert len(rows) == 4
    for r in rows:
        weighted = (cfg.WEIGHT_TREND * r["tend"] + cfg.WEIGHT_ACCEL * r["acel"]
                    + cfg.WEIGHT_MAXPROX * r["max"] + cfg.WEIGHT_LOWVOL * r["vol"])
        # Components are rounded individually, so allow a 1-point slack.
        assert abs(r["score"] - weighted) <= 1
        assert 0 <= r["score"] <= 100
    scores = [r["score"] for r in rows]
    assert scores == sorted(scores, reverse=True)
    # Lowest volatility (flat) ticker gets the top low-vol percentile.
    by_ticker = {r["ticker"]: r for r in rows}
    assert by_ticker["B"]["vol"] == 100
    assert by_ticker["A"]["vol"] == 0
    assert by_ticker["A"]["tend"] == 100


def test_build_rankings_drops_short_history(universe):
    universe["SHORT"] = ticker_data(_leader()[: cfg.MIN_HISTORY_DAYS - 1])
    rows = mom.build_rankings(universe)
    assert "SHORT" not in {r["ticker"] for r in rows}
    assert len(rows) == 3


def test_build_rankings_exact_min_history_is_scored():
    data = {
        "X": ticker_data(_leader()[: cfg.MIN_HISTORY_DAYS]),
        "Y": ticker_data(_laggard()[: cfg.MIN_HISTORY_DAYS]),
    }
    rows = mom.build_rankings(data)
    assert [r["ticker"] for r in rows] == ["X", "Y"]


def test_build_rankings_single_ticker_scores_50():
    rows = mom.build_rankings({"ONLY": ticker_data(_middle())})
    assert len(rows) == 1
    r = rows[0]
    assert (r["score"], r["tend"], r["acel"], r["max"], r["vol"], r["rank"]) == (50, 50, 50, 50, 50, 1)


def test_build_rankings_empty():
    assert mom.build_rankings({}) == []


def test_build_rankings_short_volume_history_yields_none_rvol(universe):
    # rvol is informational only: too few volume points -> None, ticker still scored.
    universe["LEAD"]["volumes"] = [1.0] * (cfg.RVOL_BASE - 1)
    rows = mom.build_rankings(universe)
    lead = next(r for r in rows if r["ticker"] == "LEAD")
    assert lead["rvol"] is None
    assert lead["rank"] == 1


def test_build_rankings_drops_ticker_with_unscorable_component(universe):
    # A zero close 12M back makes the 12M return None -> no trend -> dropped.
    closes = _middle()
    closes[-1 - cfg.LB_12M] = 0.0
    universe["BROKEN"] = ticker_data(closes)
    rows = mom.build_rankings(universe)
    assert "BROKEN" not in {r["ticker"] for r in rows}
    assert [r["rank"] for r in rows] == [1, 2, 3]


def test_build_rankings_is_relative_not_absolute():
    # Adding a stronger ticker pushes the former leader's score down.
    alone = mom.build_rankings({"LEAD": ticker_data(_leader()), "LAG": ticker_data(_laggard())})
    assert alone[0]["ticker"] == "LEAD" and alone[0]["score"] == 100

    super_leader = closes_from_log_returns([0.002 + 0.00002 * i for i in range(N_DAYS)])
    with_super = mom.build_rankings({
        "LEAD": ticker_data(_leader()),
        "LAG": ticker_data(_laggard()),
        "SUPER": ticker_data(super_leader),
    })
    by_ticker = {r["ticker"]: r for r in with_super}
    assert with_super[0]["ticker"] == "SUPER"
    assert by_ticker["LEAD"]["score"] < 100
    assert by_ticker["LEAD"]["tend"] == 50
