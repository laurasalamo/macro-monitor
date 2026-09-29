"""ETF universe and scoring weights for the Momentum Composite ranking.

Single source of truth: add/remove a row in UNIVERSE to change what appears
in the table. `stooq_symbol` follows Stooq's convention for US-listed
tickers (lowercase + ".us" suffix) - the same free, unauthenticated CSV
source already used for gold in gold_client.py.

This scoring approach (trend / acceleration / proximity-to-high /
low-volatility, cross-sectionally percentile-ranked into a 0-100 score) is
an independent re-derivation inspired by the general shape of commercial
momentum-ranking tools, not a reproduction of any specific provider's
undisclosed formula.
"""

UNIVERSE = [
    ("SPY",  "S&P 500",                "spy.us"),
    ("QQQ",  "Nasdaq 100",             "qqq.us"),
    ("VTI",  "Total US Market",        "vti.us"),
    ("DIA",  "Dow Jones",              "dia.us"),
    ("XLK",  "Technology",             "xlk.us"),
    ("XLV",  "Health Care",            "xlv.us"),
    ("XLE",  "Energy",                 "xle.us"),
    ("XLF",  "Financials",             "xlf.us"),
    ("XLI",  "Industrials",            "xli.us"),
    ("XLY",  "Consumer Discretionary", "xly.us"),
    ("XLP",  "Consumer Staples",       "xlp.us"),
    ("XLB",  "Materials",              "xlb.us"),
    ("XLU",  "Utilities",              "xlu.us"),
    ("XLC",  "Communication Services", "xlc.us"),
    ("XLRE", "Real Estate",            "xlre.us"),
    ("CIBR", "Cybersecurity",          "cibr.us"),
    ("SKYY", "Cloud Computing",        "skyy.us"),
    ("WCLD", "Cloud / SaaS",           "wcld.us"),
    ("ARKK", "Innovation",             "arkk.us"),
    ("AIQ",  "Artificial Intelligence","aiq.us"),
    ("MAGS", "Magnificent Seven",      "mags.us"),
    ("EFA",  "Developed ex-US",        "efa.us"),
    ("VGK",  "Europe",                 "vgk.us"),
    ("EWJ",  "Japan",                  "ewj.us"),
    ("EEM",  "Emerging Markets",       "eem.us"),
    ("DBC",  "Broad Commodities",      "dbc.us"),
    ("DBB",  "Base Metals",            "dbb.us"),
    ("DBA",  "Agriculture",            "dba.us"),
    ("USO",  "Crude Oil",              "uso.us"),
    ("GLD",  "Gold",                   "gld.us"),
]

# Cross-sectional composite weights - must sum to 1.0.
WEIGHT_TREND = 0.45
WEIGHT_ACCEL = 0.15
WEIGHT_MAXPROX = 0.25
WEIGHT_LOWVOL = 0.15

# Trading-day lookbacks (no weekends/holidays in the series, so these are
# real trading days, not calendar days).
LB_1M, LB_3M, LB_6M, LB_12M = 21, 63, 126, 252
LB_HIGH = 252  # ~52 weeks, for distance-from-high
LB_VOL = 63    # trailing window for realized volatility
RVOL_RECENT, RVOL_BASE = 5, 63  # relative volume = recent avg vol / base avg vol

# Blend of horizon returns into the single "trend" raw signal, weighted
# toward the intermediate term.
TREND_BLEND = {"1m": 0.10, "3m": 0.30, "6m": 0.35, "12m": 0.25}

# Need at least this many trading days of history to score a ticker
# (must exceed LB_12M so the 12M return and the acceleration lookback
# both have data).
MIN_HISTORY_DAYS = 260
