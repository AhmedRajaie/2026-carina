"""FastAPI backend for the dashboard. Grows via dashboard/tasks/.
Run: uv run uvicorn dashboard.backend.main:app --reload --port 8000
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import numpy as np

from tradinglab.indicators import sma
from tradinglab.data_feed import DataFeed
from tradinglab.simulator import PortfolioSimulator
from tradinglab.backtester import run_backtest
from tradinglab.strategies.sma import sma_crossover_weights
from tradinglab.metrics import total_return, sharpe, max_drawdown


feed = DataFeed.from_dir("data/egx")

app = FastAPI(title="Younit-style trading dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


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


@app.get("/market")
def market():
    return {
        "dates": [date.strftime("%Y-%m-%d") for date in feed.dates],
        "close": feed.close.mean(axis=1).tolist(),
    }


@app.get("/indicators/{symbol}")
def indicators(symbol: str, window: int = 20):
    if symbol not in feed.symbols:
        raise HTTPException(status_code=404, detail="Unknown symbol")

    symbol_index = feed.symbols.index(symbol)
    values = sma(feed.close[:, symbol_index], window)
    return {
        "dates": [date.strftime("%Y-%m-%d") for date in feed.dates],
        "sma": [None if np.isnan(value) else float(value) for value in values],
    }


@app.get("/indicators/full_market")
def market_indicators(window: int = 20):
    values = sma(feed.close.mean(axis=1), window)
    return {
        "dates": [date.strftime("%Y-%m-%d") for date in feed.dates],
        "sma": [None if np.isnan(value) else float(value) for value in values],
    }


@app.get("/backtest")
def backtest():
    result = run_strategy_backtest()
    return {
        "dates": [date.strftime("%Y-%m-%d") for date in result["dates"]],
        "portfolio": result["portfolio"].tolist(),
        "benchmark": result["benchmark"].tolist(),
    }


def run_strategy_backtest():
    simulator = PortfolioSimulator(
        feed,
        benchmark="equal_balance",
        commission=0.005,
        initial_capital=1000.0,
    )
    return run_backtest(simulator, sma_crossover_weights, lookback=30)


@app.get("/metrics")
def metrics():
    result = run_strategy_backtest()
    returns = result["portfolio_returns"]
    return {
        "total_return": round(total_return(returns), 3),
        "sharpe": round(sharpe(returns), 3),
        "max_drawdown": round(max_drawdown(returns), 3),
    }
