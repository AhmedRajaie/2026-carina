"""FastAPI backend for the dashboard. Grows via dashboard/tasks/.
Run: uv run uvicorn dashboard.backend.main:app --reload --port 8000
"""
import math

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from tradinglab.data_feed import DataFeed
from tradinglab.indicators import sma
from tradinglab.simulator import PortfolioSimulator
from tradinglab.backtester import run_backtest
from tradinglab.strategies.sma import sma_crossover_weights
from tradinglab.metrics import total_return, sharpe, max_drawdown

app = FastAPI(title="Younit-style trading dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

feed = DataFeed.from_dir("data/egx", symbols=["COMI", "HRHO", "TMGH", "SWDY", "FWRY"])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/universe")
def universe():
    return feed.symbols


@app.get("/prices/{symbol}")
def prices(symbol: str):
    if symbol not in feed.symbols:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    idx = feed.symbols.index(symbol)
    dates = [d.strftime("%Y-%m-%d") for d in feed.dates]
    close = feed.close[:, idx].tolist()

    return {"dates": dates, "close": close}


@app.get("/indicators/{symbol}")
def indicators(symbol: str, window: int = 20):
    if symbol not in feed.symbols:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    idx = feed.symbols.index(symbol)
    dates = [d.strftime("%Y-%m-%d") for d in feed.dates]
    close = feed.close[:, idx]

    sma_values = sma(close, window)
    sma_clean = [None if (v is None or math.isnan(v)) else float(v) for v in sma_values]

    return {"dates": dates, "sma": sma_clean}


@app.get("/backtest")
def backtest():
    simulator = PortfolioSimulator(feed, benchmark="egx30")
    result = run_backtest(simulator, sma_crossover_weights, lookback=30)
    dates = [d.strftime("%Y-%m-%d") for d in result["dates"]]
    portfolio = [v * 1000 for v in result["portfolio"]]
    benchmark = [v * 1000 for v in result["benchmark"]]

    return {"dates": dates, "portfolio": portfolio, "benchmark": benchmark}


@app.get("/metrics")
def metrics():
    simulator = PortfolioSimulator(feed, benchmark="egx30")
    result = run_backtest(simulator, sma_crossover_weights, lookback=30)

    # Convert equity curve back to per-period returns
    equity = np.array(result["portfolio"])
    returns = np.diff(equity) / equity[:-1]

    return {
        "total_return": round(total_return(returns), 3),
        "sharpe": round(sharpe(returns), 3),
        "max_drawdown": round(max_drawdown(returns), 3),
    }