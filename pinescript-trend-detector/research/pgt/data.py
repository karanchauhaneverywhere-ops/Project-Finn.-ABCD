"""Data loading, plus a synthetic generator for smoke-testing the harness."""

from __future__ import annotations

import numpy as np
import pandas as pd

REQUIRED = ("open", "high", "low", "close")


def load_csv(path: str, time_col: str | None = None) -> pd.DataFrame:
    """Load an OHLC(V) CSV.

    Tolerant about column naming and case, because exports differ by source.
    TradingView: right-click the chart → Export chart data. Most data vendors
    and broker APIs produce something compatible.
    """
    df = pd.read_csv(path)
    lower = {c.lower().strip(): c for c in df.columns}

    if time_col is None:
        for candidate in ("time", "date", "datetime", "timestamp"):
            if candidate in lower:
                time_col = lower[candidate]
                break

    missing = [c for c in REQUIRED if c not in lower]
    if missing:
        raise ValueError(
            f"CSV is missing required column(s): {missing}. "
            f"Found: {list(df.columns)}"
        )

    if time_col is not None:
        df[time_col] = pd.to_datetime(df[time_col], errors="coerce", format="mixed")
        df = df.dropna(subset=[time_col]).set_index(time_col)

    df = df.rename(columns={lower[c]: c for c in REQUIRED if c in lower})
    df = df.sort_index()
    return df.dropna(subset=list(REQUIRED))


def synthetic(n: int = 1500, seed: int = 7) -> pd.DataFrame:
    """Generate OHLC with alternating trending and ranging regimes.

    This exists ONLY to verify the harness runs end to end and that the
    analyses respond to conditions they are supposed to detect. It is not
    market data, it has none of the properties that make real markets hard,
    and no conclusion about the strategy should ever be drawn from it.
    """
    rng = np.random.default_rng(seed)
    price = 100.0
    closes = []
    regime_len = 150
    for i in range(n):
        block = (i // regime_len) % 2
        drift = 0.0016 if block == 0 else 0.0
        # Trending blocks alternate direction so both sides get exercised.
        if block == 0 and (i // regime_len) % 4 == 2:
            drift = -0.0016
        price *= 1.0 + drift + rng.normal(0, 0.008)
        closes.append(price)

    close = np.array(closes)
    noise = np.abs(rng.normal(0, 0.004, n)) * close
    high = close + noise
    low = close - noise
    open_ = np.concatenate([[close[0]], close[:-1]])

    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close}, index=idx
    )
