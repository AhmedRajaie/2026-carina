"""Read one symbol's latest OHLCV snapshot from the dashboard's source CSVs."""

from pathlib import Path

import pandas as pd
from fastapi import HTTPException


DATA_DIR = Path("data/egx")


def selected_symbol_snapshot(symbol: str, allowed_symbols: list[str]) -> dict:
    """Return the latest recorded bar and close-to-close movement for a symbol."""
    if symbol not in allowed_symbols:
        raise HTTPException(status_code=404, detail="Unknown symbol")

    path = DATA_DIR / f"{symbol}.csv"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Market data not found")

    frame = pd.read_csv(path, parse_dates=["date"]).sort_values("date").dropna(
        subset=["open", "high", "low", "close"]
    )
    if len(frame) < 2:
        raise HTTPException(status_code=404, detail="Not enough market data for snapshot")

    latest = frame.iloc[-1]
    previous = frame.iloc[-2]
    close = float(latest["close"])
    previous_close = float(previous["close"])
    change = close - previous_close

    return {
        "symbol": symbol,
        "price": round(close, 3),
        "change": round(change, 3),
        "change_percent": round(change / previous_close * 100, 3) if previous_close else 0.0,
        "open": round(float(latest["open"]), 3),
        "high": round(float(latest["high"]), 3),
        "low": round(float(latest["low"]), 3),
        "previous_close": round(previous_close, 3),
        "volume": int(latest["volume"]) if pd.notna(latest["volume"]) else 0,
        "market_status": "Historical close",
        "last_updated": latest["date"].strftime("%Y-%m-%d"),
    }
