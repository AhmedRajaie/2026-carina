"""
data_feed.py — loads the committed EGX CSVs and aligns them into matrices.

This is the single source of truth for prices in the whole program. Everything
downstream (indicators, backtester, RL env) reads from a DataFeed, so the shape
and alignment of the data is decided here, once.

Schema of each CSV (data/egx/<SYMBOL>.csv):
    date,open,high,low,close,volume

We build on 'close'. If a CSV also has an 'adj_close' column we prefer it
automatically, so regenerating the data with auto_adjust=True later just works.

Design choice — common date intersection:
    Stocks list at different times (FWRY IPO'd in 2019, others in 2015). A
    portfolio needs every asset present on every day, so we keep only the dates
    that ALL symbols share. Simple and deterministic. The "real" alternative is
    to keep full history and mask not-yet-listed assets, which we deliberately
    skip to keep the mental model clean.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class DataFeed:
    """Aligned price/volume data for a universe of symbols.

    Attributes:
        symbols: list of symbol names, fixed order used everywhere downstream.
        dates:   DatetimeIndex, length T, shared by every symbol.
        close:   ndarray (T, n_assets), price used for returns and signals.
        volume:  ndarray (T, n_assets), used as a liquidity filter.
        returns: ndarray (T, n_assets), simple close-to-close returns.
                 Row 0 is 0.0 (no prior day to compare against).
    """

    symbols: list[str]
    dates: pd.DatetimeIndex
    close: np.ndarray
    volume: np.ndarray
    returns: np.ndarray

    @property
    def n_assets(self) -> int:
        return len(self.symbols)

    @property
    def n_days(self) -> int:
        return len(self.dates)

    @classmethod
    def from_dir(cls, data_dir: str | Path, symbols: list[str] | None = None) -> "DataFeed":
        """Load every <SYMBOL>.csv in data_dir and align on shared dates."""
        data_dir = Path(data_dir)
        files = sorted(data_dir.glob("*.csv"))
        if symbols is not None:
            files = [data_dir / f"{s}.csv" for s in symbols]

        frames: dict[str, pd.DataFrame] = {}
        for f in files:
            df = pd.read_csv(f, parse_dates=["date"]).set_index("date").sort_index()
            price_col = "adj_close" if "adj_close" in df.columns else "close"
            frames[f.stem] = df[[price_col, "volume"]].rename(
                columns={price_col: "close"}
            )

        syms = list(frames.keys())

        # Intersection of all date indexes -> every asset present every day.
        common = None
        for df in frames.values():
            common = df.index if common is None else common.intersection(df.index)
        common = common.sort_values()

        close = np.column_stack([frames[s].loc[common, "close"].to_numpy() for s in syms])
        volume = np.column_stack([frames[s].loc[common, "volume"].to_numpy() for s in syms])

        # Simple returns; first row has no predecessor so we set it to 0.
        returns = np.zeros_like(close)
        returns[1:] = close[1:] / close[:-1] - 1.0

        return cls(symbols=syms, dates=common, close=close, volume=volume, returns=returns)


def load_egx30_returns(csv_path: str | Path, dates: pd.DatetimeIndex) -> np.ndarray | None:
    """Load a real EGX30 series (investing.com format) aligned to `dates`.

    investing.com export looks like:  Date, Price, Open, High, Low, Vol., Change %
    with M/D/YYYY dates in DESCENDING order and comma thousands ("53,931.92").

    Returns a per-day return array aligned to `dates`, or None if the file's
    coverage doesn't overlap enough (e.g. the short sample). When None, callers
    fall back to the equal-weight benchmark.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        return None

    df = pd.read_csv(csv_path)
    df = df.dropna(subset=["Date"])
    df["date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y")
    df["price"] = df["Price"].str.replace(",", "", regex=False).astype(float)
    df = df.set_index("date").sort_index()["price"]

    # Align onto the universe calendar; forward-fill small holiday gaps.
    aligned = df.reindex(dates).ffill()
    if aligned.isna().mean() > 0.5:  # <50% coverage -> not usable as benchmark
        return None

    price = aligned.to_numpy()
    rets = np.zeros_like(price)
    rets[1:] = price[1:] / price[:-1] - 1.0
    rets = np.nan_to_num(rets)  # any leading NaNs (pre-coverage) -> 0
    return rets
