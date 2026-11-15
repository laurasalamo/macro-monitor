"""Daily closes for the S&P 500 constituents via Yahoo Finance, in one bulk
yfinance download (~500 tickers, a few seconds)."""

import yfinance as yf


class BreadthFetchError(Exception):
    pass


def get_closes(tickers, period="5y"):
    """Returns (dates, columns, priced): ISO trading dates, one close list per
    ticker aligned to them (None where missing), and how many tickers had any data."""
    try:
        df = yf.download(tickers, period=period, interval="1d", auto_adjust=True,
                         progress=False, threads=True)["Close"]
    except Exception as e:
        raise BreadthFetchError(f"Yahoo bulk download failed: {e}")
    if df is None or df.empty:
        raise BreadthFetchError("Yahoo bulk download returned no rows")

    df = df.dropna(how="all")
    dates = [ts.strftime("%Y-%m-%d") for ts in df.index]
    columns, priced = [], 0
    for t in df.columns:
        col = [None if v != v else float(v) for v in df[t].tolist()]  # NaN -> None
        if any(v is not None for v in col):
            priced += 1
        columns.append(col)
    return dates, columns, priced
