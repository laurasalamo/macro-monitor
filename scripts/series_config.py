"""Single source of truth: metric key -> FRED series configuration.

Each entry is (fred_id, transform, unit, frequency).

transform is one of:
  "level"      - use the raw value as-is (optionally scaled, see SCALE below)
  "yoy"        - year-over-year % change, computed 12 observations back (monthly series)
  "mom_change" - change vs. the previous observation (for level-in-units series like payrolls)

frequency drives the staleness threshold (see STALE_THRESHOLD_DAYS) and is one of
"daily", "weekly", "monthly", "quarterly".
"""

FRED_SERIES = {
    "gdp_growth":       ("A191RL1Q225SBEA", "level",      "%",  "quarterly"),
    "cpi_yoy":          ("CPIAUCSL",        "yoy",        "%",  "monthly"),
    "core_pce_yoy":     ("PCEPILFE",        "yoy",        "%",  "monthly"),
    "unemployment":     ("UNRATE",          "level",      "%",  "monthly"),
    "payrolls_mom":     ("PAYEMS",          "mom_change", "K",  "monthly"),
    "payrolls_private": ("USPRIV",          "mom_change", "K",  "monthly"),
    "payrolls_goods":   ("USGOOD",          "mom_change", "K",  "monthly"),
    "payrolls_service": ("SRVPRD",          "mom_change", "K",  "monthly"),
    "payrolls_govt":    ("USGOVT",          "mom_change", "K",  "monthly"),
    "saving_rate":      ("PSAVERT",         "level",      "%",  "monthly"),
    "fed_funds":        ("DFF",             "level",      "%",  "daily"),
    "initial_claims":   ("ICSA",            "level",      "K",  "weekly"),
    "participation":    ("CIVPART",         "level",      "%",  "monthly"),

    "spread_10y2y":     ("T10Y2Y",          "level",      "pp", "daily"),
    "y2":               ("DGS2",            "level",      "%",  "daily"),
    "m3":               ("DGS3MO",          "level",      "%",  "daily"),
    "y10":              ("DGS10",           "level",      "%",  "daily"),

    "hy_oas":           ("BAMLH0A0HYM2",    "level",      "pp", "daily"),
    "ig_oas":           ("BAMLC0A0CM",      "level",      "pp", "daily"),
    "em_corp_oas":      ("BAMLEMCBPIOAS",   "level",      "pp", "daily"),

    "breakeven_5y":     ("T5YIE",           "level",      "%",  "daily"),
    "breakeven_10y":    ("T10YIE",          "level",      "%",  "daily"),
    "forward_5y5y":     ("T5YIFR",          "level",      "%",  "daily"),
    "real_10y":         ("DFII10",          "level",      "%",  "daily"),
    "tips_5y":          ("DFII5",           "level",      "%",  "daily"),

    "nfci":             ("NFCI",            "level",      "",   "weekly"),
    "fed_assets":       ("WALCL",           "level",      "T$", "weekly"),
    "rrp":              ("RRPONTSYD",       "level",      "T$", "daily"),
    "m2":               ("M2SL",            "level",      "T$", "monthly"),

    "vix":              ("VIXCLS",          "level",      "",   "daily"),
    "wti":              ("DCOILWTICO",      "level",      "$",  "daily"),
    "dxy":              ("DTWEXBGS",        "level",      "",   "daily"),
    "eurusd":           ("DEXUSEU",         "level",      "$",  "daily"),
    "usdjpy":           ("DEXJPUS",         "level",      "¥",  "daily"),
}

# Raw-value scale factors applied before display, so figures read like the
# example dashboard (e.g. Fed balance sheet in trillions, not millions).
SCALE = {
    "fed_assets": 1e-6,  # millions of $ -> trillions of $
    "m2": 1e-3,          # billions of $ -> trillions of $
    "rrp": 1e-3,         # billions of $ -> trillions of $
}

# Tenor points for the yield-curve-shape snapshot (current vs. 1 year ago).
YIELD_CURVE_TENORS = [
    ("1M", "DGS1MO"), ("3M", "DGS3MO"), ("6M", "DGS6MO"), ("1Y", "DGS1"),
    ("2Y", "DGS2"), ("3Y", "DGS3"), ("5Y", "DGS5"), ("7Y", "DGS7"),
    ("10Y", "DGS10"), ("20Y", "DGS20"), ("30Y", "DGS30"),
]

# Staleness thresholds (days since latest observation) by release frequency.
# FRED dates monthly/quarterly observations to the *start* of the period, and
# releases lag the period by weeks, so the latest August CPI (released mid-Sep)
# is already ~60 days "old". Thresholds allow for that lag plus a margin.
STALE_THRESHOLD_DAYS = {
    "daily": 5,
    "weekly": 14,
    "monthly": 70,
    "quarterly": 210,
}

# Metrics whose history is written to data.json because js/config.js charts
# them. Every other metric ships only latest/delta/as_of (history is still
# fetched and used in-memory, e.g. for the regime calculation). Keep in sync
# with the `chart.series` paths in js/config.js.
CHART_HISTORY_KEYS = {
    "hy_oas", "ig_oas", "em_corp_oas",
    "breakeven_5y", "breakeven_10y", "forward_5y5y", "tips_5y",
    "nfci",
    "unemployment",
    "y10", "y2",
}

# Years of history to keep per metric (default 5, override per key).
HISTORY_YEARS = {
    "default": 5,
    "unemployment": 2,
}
