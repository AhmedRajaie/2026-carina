"""FastAPI backend for the dashboard. Grows via dashboard/tasks.
Run: uv run uvicorn dashboard.backend.main:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
from tradinglab.backtester import run_backtest
from tradinglab.data_feed import DataFeed
from tradinglab.indicators import sma
from tradinglab.metrics import max_drawdown, sharpe, total_return
from tradinglab.simulator import PortfolioSimulator
from tradinglab.strategies.sma import sma_crossover_weights

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
        raise HTTPException(status_code=404, detail="Unknown symbol")

    symbol_index = feed.symbols.index(symbol)
    return {
        "dates": [date.strftime("%Y-%m-%d") for date in feed.dates],
        "close": feed.close[:, symbol_index].tolist(),
    }


@app.get("/indicators/{symbol}")
def indicators(symbol: str, window: int = 20):
    if symbol not in feed.symbols:
        raise HTTPException(status_code=404, detail="Unknown symbol")

    symbol_index = feed.symbols.index(symbol)
    values = sma(feed.close[:, symbol_index], window)
    return {
        "dates": [date.strftime("%Y-%m-%d") for date in feed.dates],
        "sma": [value if np.isfinite(value) else None for value in values],
    }


@app.get("/backtest")
def backtest():
    simulator = PortfolioSimulator(feed, benchmark="egx30")
    result = run_backtest(simulator, sma_crossover_weights, lookback=30)
    return {
        "dates": [date.strftime("%Y-%m-%d") for date in result["dates"]],
        "portfolio": (result["portfolio"] * 1000).tolist(),
        "benchmark": (result["benchmark"] * 1000).tolist(),
    }


@app.get("/metrics")
def metrics():
    simulator = PortfolioSimulator(feed, benchmark="egx30")
    result = run_backtest(simulator, sma_crossover_weights, lookback=30)
    returns = result["portfolio_returns"]
    return {
        "total_return": round(total_return(returns), 3),
        "sharpe": round(sharpe(returns), 3),
        "max_drawdown": round(max_drawdown(returns), 3),
    }
