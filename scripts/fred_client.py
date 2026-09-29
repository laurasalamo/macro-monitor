"""Thin wrapper around the FRED (Federal Reserve Economic Data) REST API.

Docs: https://fred.stlouisfed.org/docs/api/fred/series_observations.html
Free API key: https://fred.stlouisfed.org/docs/api/api_key.html
"""

import time

import requests

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"


class FredError(Exception):
    pass


def get_series(series_id, api_key, observation_start=None, retries=3, backoff_seconds=1.5):
    """Fetch all observations for a FRED series. Returns the raw list of
    {"date": ..., "value": ...} dicts as returned by the API."""
    if not api_key:
        raise FredError("FRED_API_KEY is not set")

    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
    }
    if observation_start:
        params["observation_start"] = observation_start

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(FRED_BASE, params=params, timeout=15)
            if resp.status_code != 200:
                raise FredError(f"{series_id}: HTTP {resp.status_code} - {resp.text[:200]}")
            payload = resp.json()
            observations = payload.get("observations")
            if observations is None:
                raise FredError(f"{series_id}: malformed response, no 'observations' key")
            return observations
        except (requests.RequestException, FredError, ValueError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(backoff_seconds ** attempt)

    raise FredError(f"Failed to fetch {series_id} after {retries} attempts: {last_err}")
