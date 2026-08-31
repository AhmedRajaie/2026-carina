"""FastAPI backend for the Week 1 dashboard."""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from tradinglab.backtester import run_backtest
from tradinglab.data_feed import DataFeed
from tradinglab.indicators import sma
from tradinglab.metrics import max_drawdown, sharpe, total_return
from tradinglab.simulator import PortfolioSimulator
from tradinglab.strategies.sma import sma_crossover_weights

app = FastAPI(title="Younit-style trading dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYMBOLS = ["COMI", "HRHO", "TMGH", "SWDY", "FWRY"]
FEED = DataFeed.from_dir(PROJECT_ROOT / "data" / "egx", symbols=SYMBOLS)


@app.get("/health")
def health():
    return {"status": "ok"}


def symbol_index(symbol: str) -> int:
    normalized = symbol.upper()
    if normalized not in FEED.symbols:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")
    return FEED.symbols.index(normalized)


def serialized_dates():
    return [date.strftime("%Y-%m-%d") for date in FEED.dates]


@app.get("/universe")
def universe():
    return FEED.symbols


@app.get("/prices/{symbol}")
def prices(symbol: str):
    index = symbol_index(symbol)
    return {
        "dates": serialized_dates(),
        "close": [float(value) for value in FEED.close[:, index]],
    }


@app.get("/indicators/{symbol}")
def indicators(symbol: str, window: int = Query(default=20, ge=1, le=FEED.n_days)):
    index = symbol_index(symbol)
    values = sma(FEED.close[:, index], window)
    return {
        "dates": serialized_dates(),
        "sma": [None if math.isnan(value) else float(value) for value in values],
    }


@lru_cache(maxsize=1)
def _run_week1_backtest():
    simulator = PortfolioSimulator(
        FEED,
        benchmark="egx30",
        egx30_path=str(PROJECT_ROOT / "data" / "egx30.csv"),
    )
    return run_backtest(
        simulator,
        lambda observation: sma_crossover_weights(observation, 9, 20),
        lookback=30,
    )


@app.get("/backtest")
def backtest():
    result = _run_week1_backtest()
    return {
        "dates": [date.strftime("%Y-%m-%d") for date in result["dates"]],
        "portfolio": [float(value * 1000) for value in result["portfolio"]],
        "benchmark": [float(value * 1000) for value in result["benchmark"]],
    }


@app.get("/metrics")
def metrics():
    returns = _run_week1_backtest()["portfolio_returns"]
    return {
        "total_return": round(total_return(returns), 3),
        "sharpe": round(sharpe(returns), 3),
        "max_drawdown": round(max_drawdown(returns), 3),
    }
