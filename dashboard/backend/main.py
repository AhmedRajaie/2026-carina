"""FastAPI backend for the dashboard. Grows via dashboard/tasks/.
Run: uv run uvicorn dashboard.backend.main:app --reload --port 8000
"""
import math
from pathlib import Path

import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from tradinglab.data_feed import DataFeed
from tradinglab.indicators import sma, rsi as calc_rsi
from tradinglab.features import features_at
from tradinglab.simulator import PortfolioSimulator
from tradinglab.backtester import run_backtest
from tradinglab.strategies.sma import sma_crossover_weights
from tradinglab.strategies.dip_buy import DipBuyStrategy
from tradinglab.metrics import total_return, sharpe, max_drawdown
from tradinglab.models import MLP, LSTMRegressor

app = FastAPI(title="Younit-style trading dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

feed = DataFeed.from_dir("data/egx")  # loads all 34 symbols automatically

# Load trained models
BACKEND_DIR = Path(__file__).parent
MLP_PATH = BACKEND_DIR / "mlp_model.pt"
LSTM_PATH = BACKEND_DIR / "lstm_model.pt"

mlp_model = None
lstm_model = None

if MLP_PATH.exists():
    mlp_model = MLP(9, hidden=32)  # 9 features
    mlp_model.load_state_dict(torch.load(MLP_PATH, map_location="cpu"))
    mlp_model.eval()

if LSTM_PATH.exists():
    lstm_model = LSTMRegressor(9, hidden=32)  # 9 features
    lstm_model.load_state_dict(torch.load(LSTM_PATH, map_location="cpu"))
    lstm_model.eval()


class MLPStrategyRebalance10:
    """MLP strategy — rebalance every 10 days."""
    def __init__(self, model, feed, top_k=5):
        self.model = model
        self.feed = feed
        self.top_k = top_k
        self.day_count = 0
        self.current_weights = None
    
    def __call__(self, observation):
        self.day_count += 1
        
        if self.day_count % 10 == 1:
            n_assets = observation.shape[0]
            with torch.no_grad():
                X_torch = torch.as_tensor(observation, dtype=torch.float32)
                predictions = self.model(X_torch).numpy()
            
            top_indices = np.argsort(predictions)[-self.top_k:]
            weights = np.zeros(n_assets)
            weights[top_indices] = 1.0 / self.top_k
            self.current_weights = weights
        
        return self.current_weights if self.current_weights is not None else np.zeros(34)


class LSTMStrategyRebalance10:
    """LSTM strategy — rebalance every 10 days."""
    def __init__(self, model, feed, top_k=5, seq_len=30):
        self.model = model
        self.feed = feed
        self.top_k = top_k
        self.seq_len = seq_len
        self.day_count = 0
        self.current_weights = None
    
    def __call__(self, observation):
        self.day_count += 1
        
        if self.day_count % 10 == 1:
            n_assets = observation.shape[0]
            seq_window = observation[:, -self.seq_len:, :]
            
            with torch.no_grad():
                X_torch = torch.as_tensor(seq_window, dtype=torch.float32)
                predictions = self.model(X_torch).numpy()
            
            top_indices = np.argsort(predictions)[-self.top_k:]
            weights = np.zeros(n_assets)
            weights[top_indices] = 1.0 / self.top_k
            self.current_weights = weights
        
        return self.current_weights if self.current_weights is not None else np.zeros(34)


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


@app.get("/indicators/{symbol}/rsi")
def indicator_rsi(symbol: str, window: int = 14):
    if symbol not in feed.symbols:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")

    idx = feed.symbols.index(symbol)
    dates = [d.strftime("%Y-%m-%d") for d in feed.dates]
    close = feed.close[:, idx]

    rsi_values = calc_rsi(close, window)
    rsi_clean = [None if math.isnan(v) else round(float(v), 2) for v in rsi_values]

    return {"dates": dates, "rsi": rsi_clean}


@app.get("/signals")
def signals():
    """Live signals for every asset based on the last available day."""
    last_day = feed.n_days - 2          # -2 so we have a valid next-day return
    obs_day  = last_day

    # Pre-compute RSI for all assets (last value)
    rsi_today = []
    for i in range(feed.n_assets):
        r = calc_rsi(feed.close[:, i], 14)
        val = r[obs_day]
        rsi_today.append(None if math.isnan(val) else round(float(val), 1))

    # SMA signal: fast > slow = uptrend
    sma_signals = []
    for i in range(feed.n_assets):
        close = feed.close[:, i]
        fast = sma(close, 9)
        slow = sma(close, 20)
        fv, sv = fast[obs_day], slow[obs_day]
        if math.isnan(fv) or math.isnan(sv):
            sma_signals.append("—")
        else:
            sma_signals.append("BUY" if fv > sv else "CASH")

    # Dip-buy signal: today's return <= -5%
    today_ret = feed.returns[obs_day]
    dip_signals = ["BUY" if r <= -0.05 else "HOLD" for r in today_ret]

    date_str = feed.dates[obs_day].strftime("%Y-%m-%d")

    rows = []
    for i, sym in enumerate(feed.symbols):
        ret = feed.returns[obs_day, i]
        rows.append({
            "symbol":     sym,
            "date":       date_str,
            "return_pct": round(float(ret) * 100, 2),
            "rsi":        rsi_today[i],
            "sma_signal": sma_signals[i],
            "dip_signal": dip_signals[i],
        })

    return rows


COMMISSION = 0.005  # 50 bps per unit of turnover


def _run_both_benchmarks():
    """Run the SMA crossover backtest once per benchmark and return all curves."""
    sim_egx30 = PortfolioSimulator(feed, benchmark="egx30", commission=COMMISSION)
    result = run_backtest(sim_egx30, sma_crossover_weights, lookback=30)

    sim_eq = PortfolioSimulator(feed, benchmark="equal_weight", commission=COMMISSION)
    result_eq = run_backtest(sim_eq, sma_crossover_weights, lookback=30)

    return result, result_eq


@app.get("/backtest")
def backtest():
    result, result_eq = _run_both_benchmarks()
    dates = [d.strftime("%Y-%m-%d") for d in result["dates"]]
    portfolio       = [v * 1000 for v in result["portfolio"]]
    benchmark_egx30 = [v * 1000 for v in result["benchmark"]]
    benchmark_eq    = [v * 1000 for v in result_eq["benchmark"]]

    return {
        "dates": dates,
        "portfolio": portfolio,
        "benchmark_egx30": benchmark_egx30,
        "benchmark_equal": benchmark_eq,
    }


@app.get("/backtest/dip")
def backtest_dip():
    """Dip-buy strategy: buy on -5% drop, sell at +10% gain."""
    strategy = DipBuyStrategy(dip_threshold=-0.05, take_profit=0.10)
    sim = PortfolioSimulator(feed, benchmark="egx30", commission=COMMISSION)
    result = run_backtest(sim, strategy, lookback=1)

    sim_eq = PortfolioSimulator(feed, benchmark="equal_weight", commission=COMMISSION)
    strategy_eq = DipBuyStrategy(dip_threshold=-0.05, take_profit=0.10)
    result_eq = run_backtest(sim_eq, strategy_eq, lookback=1)

    dates = [d.strftime("%Y-%m-%d") for d in result["dates"]]
    return {
        "dates": dates,
        "portfolio":       [v * 1000 for v in result["portfolio"]],
        "benchmark_egx30": [v * 1000 for v in result["benchmark"]],
        "benchmark_equal": [v * 1000 for v in result_eq["benchmark"]],
    }


@app.get("/backtest/mlp")
def backtest_mlp():
    """MLP strategy — 10-day rebalance."""
    if mlp_model is None:
        raise HTTPException(status_code=503, detail="MLP model not loaded")
    
    split_day = int(feed.n_days * 0.7)
    strategy = MLPStrategyRebalance10(mlp_model, feed, top_k=5)
    sim = PortfolioSimulator(feed, benchmark="egx30", commission=COMMISSION)
    result = run_backtest(sim, strategy, lookback=30, start=split_day)
    
    sim_eq = PortfolioSimulator(feed, benchmark="equal_weight", commission=COMMISSION)
    strategy_eq = MLPStrategyRebalance10(mlp_model, feed, top_k=5)
    result_eq = run_backtest(sim_eq, strategy_eq, lookback=30, start=split_day)
    
    dates = [d.strftime("%Y-%m-%d") for d in result["dates"]]
    return {
        "dates": dates,
        "portfolio":       [v * 1000 for v in result["portfolio"]],
        "benchmark_egx30": [v * 1000 for v in result["benchmark"]],
        "benchmark_equal": [v * 1000 for v in result_eq["benchmark"]],
    }


@app.get("/backtest/lstm")
def backtest_lstm():
    """LSTM strategy — 10-day rebalance."""
    if lstm_model is None:
        raise HTTPException(status_code=503, detail="LSTM model not loaded")
    
    split_day = int(feed.n_days * 0.7)
    strategy = LSTMStrategyRebalance10(lstm_model, feed, top_k=5, seq_len=30)
    sim = PortfolioSimulator(feed, benchmark="egx30", commission=COMMISSION)
    result = run_backtest(sim, strategy, lookback=30, start=split_day)
    
    sim_eq = PortfolioSimulator(feed, benchmark="equal_weight", commission=COMMISSION)
    strategy_eq = LSTMStrategyRebalance10(lstm_model, feed, top_k=5, seq_len=30)
    result_eq = run_backtest(sim_eq, strategy_eq, lookback=30, start=split_day)
    
    dates = [d.strftime("%Y-%m-%d") for d in result["dates"]]
    return {
        "dates": dates,
        "portfolio":       [v * 1000 for v in result["portfolio"]],
        "benchmark_egx30": [v * 1000 for v in result["benchmark"]],
        "benchmark_equal": [v * 1000 for v in result_eq["benchmark"]],
    }


@app.get("/leaderboard")
def leaderboard():
    """Run all strategies and return a ranked comparison table."""
    strategies = [
        {"key": "sma",   "name": "SMA Crossover",       "lookback": 30,
         "factory": lambda: sma_crossover_weights},
        {"key": "dip",   "name": "Dip-Buy (−5% / +10%)", "lookback": 1,
         "factory": lambda: DipBuyStrategy(dip_threshold=-0.05, take_profit=0.10)},
    ]
    
    # Add MLP if model loaded
    if mlp_model is not None:
        strategies.append({
            "key": "mlp",
            "name": "MLP (10-day rebalance)",
            "lookback": 30,
            "factory": lambda: MLPStrategyRebalance10(mlp_model, feed, top_k=5),
            "start": int(feed.n_days * 0.7)
        })
    
    # Add LSTM if model loaded
    if lstm_model is not None:
        strategies.append({
            "key": "lstm",
            "name": "LSTM (10-day rebalance)",
            "lookback": 30,
            "factory": lambda: LSTMStrategyRebalance10(lstm_model, feed, top_k=5, seq_len=30),
            "start": int(feed.n_days * 0.7)
        })

    rows = []
    for s in strategies:
        sim    = PortfolioSimulator(feed, benchmark="egx30", commission=COMMISSION)
        start_day = s.get("start", None)
        result = run_backtest(sim, s["factory"](), lookback=s["lookback"], start=start_day)

        equity  = np.array(result["portfolio"])
        rets    = np.diff(equity) / equity[:-1]
        final   = round(float(equity[-1]) * 1000, 1)

        rows.append({
            "name":         s["name"],
            "final_value":  final,
            "total_return": round(total_return(rets), 3),
            "sharpe":       round(sharpe(rets), 3),
            "max_drawdown": round(max_drawdown(rets), 3),
        })

    # Rank by Sharpe (highest = best)
    rows.sort(key=lambda r: r["sharpe"], reverse=True)
    for i, row in enumerate(rows):
        row["rank"] = i + 1

    return rows


@app.get("/metrics")
def metrics(strategy: str = "sma"):
    """Return metrics for the selected strategy. ?strategy=sma or ?strategy=dip or ?strategy=mlp or ?strategy=lstm"""
    sim = PortfolioSimulator(feed, benchmark="egx30", commission=COMMISSION)
    
    if strategy == "dip":
        strat = DipBuyStrategy(dip_threshold=-0.05, take_profit=0.10)
        result = run_backtest(sim, strat, lookback=1)
    elif strategy == "mlp":
        if mlp_model is None:
            raise HTTPException(status_code=503, detail="MLP model not loaded")
        split_day = int(feed.n_days * 0.7)
        strat = MLPStrategyRebalance10(mlp_model, feed, top_k=5)
        result = run_backtest(sim, strat, lookback=30, start=split_day)
    elif strategy == "lstm":
        if lstm_model is None:
            raise HTTPException(status_code=503, detail="LSTM model not loaded")
        split_day = int(feed.n_days * 0.7)
        strat = LSTMStrategyRebalance10(lstm_model, feed, top_k=5, seq_len=30)
        result = run_backtest(sim, strat, lookback=30, start=split_day)
    else:  # sma
        result = run_backtest(sim, sma_crossover_weights, lookback=30)

    equity = np.array(result["portfolio"])
    returns = np.diff(equity) / equity[:-1]

    return {
        "total_return": round(total_return(returns), 3),
        "sharpe":       round(sharpe(returns), 3),
        "max_drawdown": round(max_drawdown(returns), 3),
        "commission":   COMMISSION,
    }