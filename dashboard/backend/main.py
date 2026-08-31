"""FastAPI backend for the dashboard. Grows via dashboard/tasks.
Run: uv run uvicorn dashboard.backend.main:app --reload --port 8000
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from tradinglab.backtester import run_backtest
from tradinglab.data_feed import DataFeed
from tradinglab.indicators import sma
from tradinglab.metrics import max_drawdown, sharpe, total_return
from tradinglab.simulator import PortfolioSimulator
from tradinglab.strategies.sma import sma_crossover_weights

CORE_SYMBOLS = ["COMI", "HRHO", "TMGH", "SWDY", "FWRY"]
SMA_COMMISSION = 0.005
TIKTOK_LOOKBACK = 5
TIKTOK_BUY_THRESHOLD = -0.05
TIKTOK_SELL_THRESHOLD = 0.10
TIKTOK_BUY_AMOUNT = 5.0
TIKTOK_SELL_AMOUNT = 10.0
TIKTOK_INITIAL_CASH = 1000.0
TIKTOK_COMMISSION = 0.005

feed = DataFeed.from_dir("data/egx", symbols=CORE_SYMBOLS)
full_market_feed = DataFeed.from_dir("data/egx")
FEATURES_PATH = Path("dashboard/data/features.json")

app = FastAPI(title="Younit-style trading dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def feed_for_scope(scope: str) -> DataFeed:
    if scope == "core":
        return feed
    if scope == "full":
        return full_market_feed
    raise HTTPException(status_code=400, detail="Scope must be 'core' or 'full'")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/universe")
def universe(scope: str = "core"):
    return feed_for_scope(scope).symbols


@app.get("/prices/{symbol}")
def prices(symbol: str, scope: str = "core"):
    selected_feed = feed_for_scope(scope)
    if symbol not in selected_feed.symbols:
        raise HTTPException(status_code=404, detail="Unknown symbol")

    asset = selected_feed.symbols.index(symbol)
    return {
        "dates": selected_feed.dates.strftime("%Y-%m-%d").tolist(),
        "close": selected_feed.close[:, asset].tolist(),
    }


@app.get("/indicators/{symbol}")
def indicators(symbol: str, window: int = 20, scope: str = "core"):
    selected_feed = feed_for_scope(scope)
    if symbol not in selected_feed.symbols:
        raise HTTPException(status_code=404, detail="Unknown symbol")
    if window < 1:
        raise HTTPException(status_code=400, detail="Window must be positive")

    asset = selected_feed.symbols.index(symbol)
    values = sma(selected_feed.close[:, asset], window)
    return {
        "dates": selected_feed.dates.strftime("%Y-%m-%d").tolist(),
        "sma": [None if value != value else float(value) for value in values],
    }


@lru_cache(maxsize=4)
def run_sma_backtest(scope: str = "core", benchmark: str = "egx30"):
    selected_feed = feed_for_scope(scope)
    if benchmark not in {"egx30", "equal_weight"}:
        raise HTTPException(
            status_code=400,
            detail="Benchmark must be 'egx30' or 'equal_weight'",
        )
    simulator = PortfolioSimulator(
        selected_feed,
        benchmark=benchmark,
        commission=SMA_COMMISSION,
    )
    return run_backtest(simulator, strategy=sma_crossover_weights, lookback=30)


@app.get("/backtest")
def backtest(scope: str = "core", benchmark: str = "egx30"):
    result = run_sma_backtest(scope, benchmark)
    return {
        "dates": result["dates"].strftime("%Y-%m-%d").tolist(),
        "portfolio": (result["portfolio"] * 1000).tolist(),
        "benchmark": (result["benchmark"] * 1000).tolist(),
        "commission": SMA_COMMISSION,
    }


@app.get("/metrics")
def metrics(scope: str = "core"):
    result = run_sma_backtest(scope)
    returns = result["portfolio_returns"]
    held = result["weights"]
    previous = np.vstack([np.zeros((1, held.shape[1])), held[:-1]])
    turnover = np.abs(held - previous).sum(axis=1) / 2.0
    previous_equity = np.concatenate([[1000.0], result["portfolio"][:-1] * 1000.0])
    return {
        "total_return": round(total_return(returns), 3),
        "sharpe": round(sharpe(returns), 3),
        "max_drawdown": round(max_drawdown(returns), 3),
        "final_equity": round(float(result["portfolio"][-1] * 1000.0), 2),
        "fees_paid": round(float(np.sum(previous_equity * SMA_COMMISSION * turnover)), 2),
        "activity": int(np.count_nonzero(turnover > 1e-12)),
    }


@app.get("/features")
def features():
    return json.loads(FEATURES_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=32)
def run_tiktok_strategy(
    lookback: int = TIKTOK_LOOKBACK,
    buy_threshold: float = TIKTOK_BUY_THRESHOLD,
    sell_threshold: float = TIKTOK_SELL_THRESHOLD,
    buy_amount: float = TIKTOK_BUY_AMOUNT,
    sell_amount: float = TIKTOK_SELL_AMOUNT,
    initial_cash: float = TIKTOK_INITIAL_CASH,
    commission: float = TIKTOK_COMMISSION,
):
    """Backtest fixed-dollar weekly-move orders across the full market."""
    market = full_market_feed
    weekly_returns = np.full_like(market.close, np.nan, dtype=float)
    weekly_returns[lookback:] = market.close[lookback:] / market.close[:-lookback] - 1.0

    buy_signal = np.zeros_like(market.close, dtype=bool)
    sell_signal = np.zeros_like(market.close, dtype=bool)
    buy_signal[1:] = weekly_returns[:-1] <= buy_threshold
    sell_signal[1:] = weekly_returns[:-1] >= sell_threshold

    cash = initial_cash
    shares = np.zeros(market.n_assets, dtype=float)
    equity = np.empty(market.n_days, dtype=float)
    cash_history = np.empty(market.n_days, dtype=float)
    fees_paid = 0.0
    buy_trades = 0
    sell_trades = 0

    for day in range(market.n_days):
        prices = market.close[day]

        for asset in np.flatnonzero(sell_signal[day]):
            gross = min(sell_amount, shares[asset] * prices[asset])
            if gross <= 0:
                continue
            fee = gross * commission
            shares[asset] -= gross / prices[asset]
            cash += gross - fee
            fees_paid += fee
            sell_trades += 1

        buy_assets = np.flatnonzero(buy_signal[day])
        if len(buy_assets):
            gross_each = min(buy_amount, cash / (len(buy_assets) * (1.0 + commission)))
            for asset in buy_assets:
                if gross_each <= 0:
                    break
                fee = gross_each * commission
                shares[asset] += gross_each / prices[asset]
                cash -= gross_each + fee
                fees_paid += fee
                buy_trades += 1

        cash = max(cash, 0.0)
        cash_history[day] = cash
        equity[day] = cash + np.dot(shares, prices)

    benchmark = initial_cash * np.cumprod(1.0 + market.returns.mean(axis=1))
    strategy_returns = np.zeros_like(equity)
    strategy_returns[1:] = equity[1:] / equity[:-1] - 1.0

    return {
        "equity": equity,
        "cash": cash_history,
        "benchmark": benchmark,
        "strategy_returns": strategy_returns,
        "fees_paid": fees_paid,
        "buy_trades": buy_trades,
        "sell_trades": sell_trades,
        "shares": shares,
        "weekly_returns": weekly_returns,
    }


@app.get("/tiktok-backtest")
def tiktok_backtest(
    lookback: Annotated[int, Query(ge=1, le=252)] = TIKTOK_LOOKBACK,
    buy_threshold: Annotated[float, Query(le=0)] = TIKTOK_BUY_THRESHOLD,
    sell_threshold: Annotated[float, Query(ge=0)] = TIKTOK_SELL_THRESHOLD,
    buy_amount: Annotated[float, Query(gt=0)] = TIKTOK_BUY_AMOUNT,
    sell_amount: Annotated[float, Query(gt=0)] = TIKTOK_SELL_AMOUNT,
    initial_cash: Annotated[float, Query(gt=0)] = TIKTOK_INITIAL_CASH,
    commission: Annotated[float, Query(ge=0, le=1)] = TIKTOK_COMMISSION,
):
    result = run_tiktok_strategy(
        lookback,
        buy_threshold,
        sell_threshold,
        buy_amount,
        sell_amount,
        initial_cash,
        commission,
    )
    returns = result["strategy_returns"]
    return {
        "dates": full_market_feed.dates.strftime("%Y-%m-%d").tolist(),
        "portfolio": result["equity"].tolist(),
        "cash": result["cash"].tolist(),
        "benchmark": result["benchmark"].tolist(),
        "symbols": full_market_feed.symbols,
        "parameters": {
            "lookback": lookback,
            "buy_threshold": buy_threshold,
            "sell_threshold": sell_threshold,
            "buy_amount": buy_amount,
            "sell_amount": sell_amount,
            "initial_cash": initial_cash,
            "commission": commission,
        },
        "metrics": {
            "final_equity": round(float(result["equity"][-1]), 2),
            "total_return": round(total_return(returns), 3),
            "sharpe": round(sharpe(returns), 3),
            "max_drawdown": round(max_drawdown(returns), 3),
            "fees_paid": round(float(result["fees_paid"]), 2),
            "buy_trades": result["buy_trades"],
            "sell_trades": result["sell_trades"],
        },
    }


@app.get("/tiktok-signals")
def tiktok_signals(
    lookback: Annotated[int, Query(ge=1, le=252)] = TIKTOK_LOOKBACK,
    buy_threshold: Annotated[float, Query(le=0)] = TIKTOK_BUY_THRESHOLD,
    sell_threshold: Annotated[float, Query(ge=0)] = TIKTOK_SELL_THRESHOLD,
    buy_amount: Annotated[float, Query(gt=0)] = TIKTOK_BUY_AMOUNT,
    sell_amount: Annotated[float, Query(gt=0)] = TIKTOK_SELL_AMOUNT,
    initial_cash: Annotated[float, Query(gt=0)] = TIKTOK_INITIAL_CASH,
    commission: Annotated[float, Query(ge=0, le=1)] = TIKTOK_COMMISSION,
):
    result = run_tiktok_strategy(
        lookback,
        buy_threshold,
        sell_threshold,
        buy_amount,
        sell_amount,
        initial_cash,
        commission,
    )
    latest_returns = result["weekly_returns"][-1]
    latest_prices = full_market_feed.close[-1]
    holding_values = result["shares"] * latest_prices
    rows = []
    for asset, symbol in enumerate(full_market_feed.symbols):
        weekly_return = float(latest_returns[asset])
        if weekly_return <= buy_threshold:
            signal = "BUY"
        elif weekly_return >= sell_threshold:
            signal = "SELL"
        else:
            signal = "HOLD"
        rows.append(
            {
                "symbol": symbol,
                "weekly_return": weekly_return,
                "signal": signal,
                "close": round(float(latest_prices[asset]), 3),
                "holding_value": round(float(holding_values[asset]), 2),
            }
        )
    return {
        "as_of": full_market_feed.dates[-1].strftime("%Y-%m-%d"),
        "signals": rows,
    }


# TASK_07+ : add later dashboard endpoints here.
