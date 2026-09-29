"""Daily OHLCV history for US-listed ETFs via Yahoo Finance (yfinance, no
API key required). Symbols in momentum_config are Stooq-style (legacy) ("spy.us");
they are converted to Yahoo tickers ("SPY") here.
"""

import yfinance as yf


class MomentumFetchError(Exception):
    pass


def _to_yahoo(symbol):
    return symbol.removesuffix(".us").upper()


def get_ohlcv_series(symbol):
    """Returns a sorted list of (date_str, close, volume) tuples."""
    ticker = _to_yahoo(symbol)
    try:
        df = yf.Ticker(ticker).history(period="10y", interval="1d", auto_adjust=True)
    except Exception as e:
        raise MomentumFetchError(f"Yahoo fetch failed for {ticker}: {e}")

    if df is None or df.empty or "Close" not in df or "Volume" not in df:
        raise MomentumFetchError(f"Yahoo fetch for {ticker} returned no usable rows")

    out = []
    for ts, row in df.iterrows():
        close, volume = row["Close"], row["Volume"]
        if close != close or volume != volume:  # NaN
            continue
        out.append((ts.strftime("%Y-%m-%d"), float(close), float(volume)))

    if not out:
        raise MomentumFetchError(f"Yahoo fetch for {ticker} returned no usable rows")

    out.sort(key=lambda p: p[0])
    return out
