"""Gold price history via Yahoo Finance (yfinance, no API key required).

FRED doesn't carry a gold spot series, so this is the one non-FRED source
in the project besides the momentum ETFs. Uses COMEX gold futures (GC=F)
as the proxy for spot.
"""

import yfinance as yf

GOLD_TICKER = "GC=F"


class GoldFetchError(Exception):
    pass


def get_gold_series():
    """Returns a sorted list of (date_str, close_price) tuples."""
    try:
        df = yf.Ticker(GOLD_TICKER).history(period="10y", interval="1d")
    except Exception as e:
        raise GoldFetchError(f"Yahoo gold fetch failed: {e}")

    if df is None or df.empty or "Close" not in df:
        raise GoldFetchError("Yahoo gold fetch returned no usable rows")

    out = [
        (ts.strftime("%Y-%m-%d"), float(c))
        for ts, c in df["Close"].items()
        if c == c  # skip NaN
    ]
    if not out:
        raise GoldFetchError("Yahoo gold fetch returned no usable rows")

    out.sort(key=lambda p: p[0])
    return out
