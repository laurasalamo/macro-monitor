"""Daily OHLCV for the S&P 500 constituents via Yahoo Finance, in one bulk
yfinance download (~500 tickers, a few seconds)."""

import yfinance as yf


class BreadthFetchError(Exception):
    pass


FIELDS = {"close": "Close", "high": "High", "low": "Low", "volume": "Volume"}


def _column(series):
    return [None if v != v else float(v) for v in series.tolist()]  # NaN -> None


def get_ohlcv(tickers, period="5y"):
    """Returns (dates, fields, priced): ISO trading dates; fields maps close/
    high/low/volume -> {ticker: list aligned to dates, None where missing};
    and how many tickers had any close."""
    try:
        df = yf.download(tickers, period=period, interval="1d", auto_adjust=True,
                         progress=False, threads=True, group_by="column")
    except Exception as e:
        raise BreadthFetchError(f"Yahoo bulk download failed: {e}")
    if df is None or df.empty:
        raise BreadthFetchError("Yahoo bulk download returned no rows")

    df = df.dropna(how="all")
    dates = [ts.strftime("%Y-%m-%d") for ts in df.index]
    fields = {}
    for key, name in FIELDS.items():
        block = df[name]
        fields[key] = {t: _column(block[t]) if t in block.columns else [None] * len(dates) for t in tickers}
    priced = sum(1 for t in tickers if any(v is not None for v in fields["close"][t]))
    return dates, fields, priced


def get_closes(tickers, period="5y"):
    """Closes only: (dates, columns in ticker order, priced)."""
    dates, fields, priced = get_ohlcv(tickers, period)
    return dates, [fields["close"][t] for t in tickers], priced
