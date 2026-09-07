"""FastAPI backend for the dashboard. Grows via dashboard/tasks.
Run: uv run uvicorn dashboard.backend.main:app --reload --port 8000
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from dashboard.backend.chat_service import ai_dashboard_reply, build_dashboard_context, local_dashboard_reply
from dashboard.backend.symbol_snapshot import selected_symbol_snapshot
from tradinglab.backtester import run_backtest
from tradinglab.data_feed import DataFeed
from tradinglab.indicators import sma
from tradinglab.metrics import max_drawdown, sharpe, total_return
from tradinglab.simulator import PortfolioSimulator
from tradinglab.strategies.mpt import inverse_vol_weights
from tradinglab.strategies.sma import sma_crossover_weights

load_dotenv()

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
MODEL_COMPARE_PATH = Path("dashboard/data/model_compare.json")
RL_EQUITY_PATH = Path("dashboard/data/rl_equity.json")
QAGENT_PATH = Path("dashboard/data/qagent.json")

app = FastAPI(title="Younit-style trading dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=2_000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2_000)
    scope: str = Field(default="core", pattern="^(core|full)$")
    history: list[ChatMessage] = Field(default_factory=list, max_length=12)


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


@app.get("/compare")
def model_compare():
    if not MODEL_COMPARE_PATH.exists():
        raise HTTPException(status_code=404, detail="Model comparison data not found")
    return json.loads(MODEL_COMPARE_PATH.read_text(encoding="utf-8"))


def stored_curve(path: Path, portfolio_key: str, benchmark_key: str):
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{path.stem} data not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    portfolio = data.get(portfolio_key)
    benchmark = data.get(benchmark_key)
    if not portfolio or not benchmark:
        raise HTTPException(status_code=422, detail=f"Invalid {path.stem} data")
    length = min(len(portfolio), len(benchmark))
    dates = full_market_feed.dates[-length:]
    return {
        "dates": dates.strftime("%Y-%m-%d").tolist(),
        "portfolio": [float(value) * 1000 for value in portfolio[-length:]],
        "benchmark": [float(value) * 1000 for value in benchmark[-length:]],
    }


@app.get("/rl")
def rl_equity():
    result = stored_curve(RL_EQUITY_PATH, "agent", "benchmark")
    returns = np.zeros(len(result["portfolio"]))
    returns[1:] = np.asarray(result["portfolio"][1:]) / np.asarray(result["portfolio"][:-1]) - 1
    result["metrics"] = {
        "total_return": round(total_return(returns), 3),
        "sharpe": round(sharpe(returns), 3),
        "max_drawdown": round(max_drawdown(returns), 3),
    }
    return result


@lru_cache(maxsize=1)
def run_mpt_backtest():
    simulator = PortfolioSimulator(full_market_feed, benchmark="egx30", commission=SMA_COMMISSION)
    return run_backtest(simulator, strategy=inverse_vol_weights, lookback=30)


@app.get("/leaderboard")
def leaderboard():
    sma_result = run_sma_backtest("full", "egx30")
    mpt_result = run_mpt_backtest()
    rl_result = rl_equity()
    length = min(len(rl_result["dates"]), len(sma_result["dates"]))
    dates = sma_result["dates"][-length:]
    curves = {
        "sma": (sma_result["portfolio"][-length:] * 1000).tolist(),
        "mpt": (mpt_result["portfolio"][-length:] * 1000).tolist(),
        "agent": rl_result["portfolio"][-length:],
        "benchmark": (sma_result["benchmark"][-length:] * 1000).tolist(),
    }
    return {"dates": dates.strftime("%Y-%m-%d").tolist(), "curves": curves}


@app.get("/allocations")
def allocations():
    observation = np.expand_dims(full_market_feed.returns[-30:], axis=-1).transpose(1, 0, 2)
    weights = inverse_vol_weights(observation)
    return {
        "source": "latest inverse-volatility allocation (RL weights were not exported)",
        "weights": {symbol: round(float(weight), 4) for symbol, weight in zip(full_market_feed.symbols, weights)},
    }


@app.get("/qagent")
def qagent():
    return stored_curve(QAGENT_PATH, "portfolio", "benchmark")


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


@app.get("/snapshot/{symbol}")
def snapshot(symbol: str, scope: str = "core"):
    """Latest OHLCV snapshot for the symbol currently selected in the dashboard."""
    return selected_symbol_snapshot(symbol, feed_for_scope(scope).symbols)


@app.post("/chat")
def chat(request: ChatRequest):
    """Answer dashboard questions using current server-side backtest data."""
    context = build_dashboard_context(
        scope=request.scope,
        sma_metrics=metrics(request.scope),
        fixed_dollar=tiktok_backtest(),
        signals=tiktok_signals()["signals"],
    )
    history = [message.model_dump() for message in request.history]
    ai_reply = ai_dashboard_reply(request.message, history, context)
    return {
        "reply": ai_reply[0] if ai_reply else local_dashboard_reply(request.message, context),
        "provider": ai_reply[1] if ai_reply else "dashboard",
    }


# Serve the frontend from the same origin as the API.  Opening index.html directly
# works in some browsers, but serving it here avoids file-origin and CORS issues.
# Keep this mount last so the API routes above always take precedence.
app.mount(
    "/",
    StaticFiles(directory="dashboard/frontend", html=True),
    name="dashboard",
)
