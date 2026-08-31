from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def _load_local_price_data(tickers):
    repo_root = Path(__file__).resolve().parents[2]
    search_roots = [repo_root / "data" / "egx", repo_root / "data", repo_root / "mean-reversion-backtest" / "data"]
    frames = {}

    for ticker in tickers:
        ticker_name = str(ticker).upper()
        for root in search_roots:
            path = root / f"{ticker_name}.csv"
            if not path.exists():
                continue

            df = pd.read_csv(path)
            date_col = next((c for c in ["Date", "date"] if c in df.columns), None)
            if date_col is None:
                continue
            close_col = next((c for c in ["Price", "Adj Close", "Adj Close*", "Close", "close"] if c in df.columns), None)
            if close_col is None:
                continue

            df = df[[date_col, close_col]].dropna().copy()
            df[date_col] = pd.to_datetime(df[date_col])
            df[close_col] = pd.to_numeric(df[close_col].astype(str).str.replace(",", "", regex=False), errors="coerce")
            df = df.dropna(subset=[close_col]).sort_values(date_col).set_index(date_col)
            frames[ticker_name] = df[close_col]
            break
        else:
            return None

    if not frames:
        return None
    return pd.concat(frames, axis=1)


def fetch_data(tickers, start_date, end_date):
    try:
        import yfinance as yf

        data = yf.download(tickers, start=start_date, end=end_date, progress=False, auto_adjust=False)
        if isinstance(data.columns, pd.MultiIndex):
            if "Adj Close" in data.columns:
                close = data["Adj Close"]
            else:
                close = data["Close"]
        else:
            close = data
        return close
    except ModuleNotFoundError:
        local = _load_local_price_data(tickers)
        if local is not None:
            local = local.loc[(local.index >= pd.Timestamp(start_date)) & (local.index <= pd.Timestamp(end_date) if end_date is not None else True)]
            return local
        raise ModuleNotFoundError(
            "No market data source is available. Install yfinance or use tickers present in the repo's local CSV files under data/egx/."
        )


def _weekly_signal_frame(prices: pd.DataFrame, drop_threshold: float, rise_threshold: float) -> pd.DataFrame:
    weekly_prices = prices.resample("W-FRI").ffill()
    weekly_returns = weekly_prices.pct_change().fillna(0.0) * 100.0
    signal_map: Dict[str, List[str]] = {}
    for ticker in prices.columns:
        labels = []
        for value in weekly_returns[ticker].tolist():
            if value <= -drop_threshold:
                labels.append("LONG")
            elif value >= rise_threshold:
                labels.append("SHORT")
            else:
                labels.append("HOLD")
        signal_map[ticker] = labels
    signals = pd.DataFrame(signal_map, index=weekly_returns.index)
    return signals


def _execution_price(price: float, side: str, slippage_bps: float) -> float:
    slippage = slippage_bps / 10000.0
    if side == "LONG":
        return float(price * (1 + slippage))
    if side == "SHORT":
        return float(price * (1 - slippage))
    return float(price)


def _annualized_return(equity_curve: pd.Series) -> float:
    if len(equity_curve) < 2:
        return 0.0
    start = equity_curve.iloc[0]
    end = equity_curve.iloc[-1]
    if start <= 0 or end <= 0:
        return 0.0
    years = max(len(equity_curve) / 252.0, 1e-9)
    return float((end / start) ** (1.0 / years) - 1.0)


def _sharpe_ratio(returns: pd.Series) -> float:
    if len(returns) < 2:
        return 0.0
    std = returns.std(ddof=1)
    if std == 0 or np.isnan(std):
        return 0.0
    return float(returns.mean() / std * np.sqrt(252))


def _sortino_ratio(returns: pd.Series) -> float:
    if len(returns) < 2:
        return 0.0
    downside = returns[returns < 0]
    downside_std = downside.std(ddof=1)
    if downside_std == 0 or np.isnan(downside_std):
        return 0.0
    return float(returns.mean() / downside_std * np.sqrt(252))


def _max_drawdown(equity_curve: pd.Series) -> float:
    if equity_curve.empty:
        return 0.0
    running_max = equity_curve.cummax()
    drawdown = 1.0 - (equity_curve / running_max)
    return float(drawdown.max())


def _calmar_ratio(equity_curve: pd.Series) -> float:
    max_dd = _max_drawdown(equity_curve)
    if max_dd == 0:
        return 0.0
    return float(_annualized_return(equity_curve) / max_dd)


def _compute_risk_metrics(equity_curve: pd.Series) -> Dict[str, float]:
    log_returns = equity_curve.pct_change().fillna(0.0)
    sharpe = _sharpe_ratio(log_returns)
    sortino = _sortino_ratio(log_returns)
    max_dd = _max_drawdown(equity_curve)
    calmar = _calmar_ratio(equity_curve)
    total_return = float((equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1.0) if equity_curve.iloc[0] else 0.0
    return {
        "total_return": total_return,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_dd,
        "calmar": calmar,
    }


def _compute_turnover_and_holding(trade_log: List[dict]) -> Dict[str, float]:
    if not trade_log:
        return {"average_holding_period_days": 0.0, "turnover_rate": 0.0}

    holding_periods = [trade["holding_period_days"] for trade in trade_log if "holding_period_days" in trade]
    notional_turnover = sum(float(trade["notional"]) for trade in trade_log)
    average_notional = max(sum(float(trade["notional"]) for trade in trade_log) / max(len(trade_log), 1), 1.0)
    average_hold = float(np.mean(holding_periods)) if holding_periods else 0.0
    turnover = float(notional_turnover / average_notional) if average_notional else 0.0
    return {"average_holding_period_days": average_hold, "turnover_rate": turnover}


def _daily_equity_curve_from_trades(prices: pd.DataFrame, trade_log: List[dict], initial_capital: float) -> pd.Series:
    equity_curve = pd.Series(index=prices.index, dtype=float)
    open_positions: Dict[str, Dict[str, float]] = {}
    cash = float(initial_capital)
    net_equity = float(initial_capital)

    for date, row in prices.iterrows():
        # close any positions that hit the exit condition
        for ticker in list(open_positions):
            pos = open_positions[ticker]
            current_price = row[ticker]
            should_exit = False
            if pos["side"] == 1 and current_price <= pos["entry_week_open"]:
                should_exit = True
            elif pos["side"] == -1 and current_price >= pos["entry_week_open"]:
                should_exit = True
            elif (date - pos["entry_date"]).days >= pos["hold_period_days"]:
                should_exit = True

            if should_exit:
                close_price = _execution_price(current_price, "SHORT" if pos["side"] == 1 else "LONG", pos["slippage_bps"])
                shares = pos["shares"]
                commission = abs(shares) * pos["commission_per_share"]
                if pos["side"] == 1:
                    cash += close_price * shares - commission
                else:
                    cash -= close_price * shares + commission
                pnl = (close_price * shares * pos["side"]) - (pos["entry_price"] * shares * pos["side"])
                trade_log.append(
                    {
                        "ticker": ticker,
                        "side": pos["side"],
                        "entry_date": pos["entry_date"],
                        "exit_date": date,
                        "holding_period_days": (date - pos["entry_date"]).days,
                        "notional": abs(pos["shares"] * pos["entry_price"]),
                        "pnl": float(pnl),
                    }
                )
                del open_positions[ticker]

        # add new signals for this date if a weekly decision is due
        weekly_index = pd.DatetimeIndex([date]).intersection(prices.resample("W-FRI").ffill().index)
        if len(weekly_index) > 0:
            weekly_dates = prices.resample("W-FRI").ffill().index
            if date in weekly_dates:
                weekly_returns = prices.resample("W-FRI").ffill().pct_change().fillna(0.0) * 100.0
                for ticker in prices.columns:
                    if ticker in open_positions:
                        continue
                    signal = "HOLD"
                    current_return = weekly_returns.loc[date, ticker]
                    if current_return <= -drop_threshold:
                        signal = "LONG"
                    elif current_return >= rise_threshold:
                        signal = "SHORT"
                    if signal == "HOLD":
                        continue
                    if len(open_positions) >= max_positions:
                        continue
                    max_trade_notional = capital * max_capital_allocation
                    total_open_notional = sum(abs(pos["shares"] * prices.loc[date, ticker]) for pos in open_positions.values())
                    if total_open_notional + max_trade_notional > max_positions * max_trade_notional:
                        continue
                    side = signal
                    entry_price = _execution_price(float(row[ticker]), side, slippage_bps)
                    entry_week_open = prices.loc[date - pd.Timedelta(days=7):date].iloc[0][ticker] if date - pd.Timedelta(days=7) >= prices.index[0] else row[ticker]
                    shares = max_trade_notional / entry_price
                    commission = abs(shares) * trade_cost_per_share
                    if side == "LONG":
                        cash -= max_trade_notional + commission
                    else:
                        cash += max_trade_notional - commission
                    open_positions[ticker] = {
                        "side": 1 if side == "LONG" else -1,
                        "shares": shares,
                        "entry_price": entry_price,
                        "entry_week_open": entry_week_open,
                        "entry_date": date,
                        "hold_period_days": hold_period_days,
                        "slippage_bps": slippage_bps,
                        "commission_per_share": trade_cost_per_share,
                    }

        net_equity = cash + sum(pos["side"] * pos["shares"] * row[ticker] for ticker, pos in open_positions.items())
        equity_curve.loc[date] = net_equity

    return equity_curve


def _plot_equity_and_drawdown(equity_curve: pd.Series, title: str = "Portfolio Equity and Rolling Drawdown"):
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    axes[0].plot(equity_curve.index, equity_curve.values, label="Equity")
    axes[0].set_title(title)
    axes[0].set_ylabel("Portfolio Value")
    axes[0].legend()

    running_peak = equity_curve.cummax()
    drawdown = 1.0 - (equity_curve / running_peak)
    axes[1].plot(equity_curve.index, drawdown.values, color="tab:red", label="Drawdown")
    axes[1].axhline(0, color="black", linewidth=0.8, alpha=0.4)
    axes[1].set_ylabel("Drawdown")
    axes[1].set_xlabel("Date")
    axes[1].legend()
    fig.tight_layout()
    plt.show()


def run_backtest(
    prices: pd.DataFrame,
    drop_threshold: float = 5.0,
    rise_threshold: float = 10.0,
    hold_period_days: int = 5,
    max_positions: int = 3,
    max_capital_allocation: float = 0.20,
    capital: float = 100000.0,
    trade_cost_per_share: float = 0.005,
    slippage_bps: float = 10.0,
    verbose: bool = True,
):
    prices = prices.sort_index().copy()
    equity_curve = pd.Series(index=prices.index, dtype=float)
    trade_log: List[dict] = []
    cash = float(capital)
    open_positions: Dict[str, Dict[str, float]] = {}

    for date, row in prices.iterrows():
        # close open positions first to honour exit rules
        for ticker in list(open_positions):
            pos = open_positions[ticker]
            current_price = float(row[ticker])
            should_exit = False
            if pos["side"] == 1 and current_price <= pos["entry_week_open"]:
                should_exit = True
            elif pos["side"] == -1 and current_price >= pos["entry_week_open"]:
                should_exit = True
            elif (date - pos["entry_date"]).days >= pos["hold_period_days"]:
                should_exit = True
            if should_exit:
                exit_price = _execution_price(current_price, "SHORT" if pos["side"] == 1 else "LONG", pos["slippage_bps"])
                shares = pos["shares"]
                commission = abs(shares) * pos["commission_per_share"]
                if pos["side"] == 1:
                    cash += exit_price * shares - commission
                else:
                    cash -= exit_price * shares + commission
                pnl = (exit_price * shares * pos["side"]) - (pos["entry_price"] * shares * pos["side"])
                trade_log.append(
                    {
                        "ticker": ticker,
                        "side": pos["side"],
                        "entry_date": pos["entry_date"],
                        "exit_date": date,
                        "holding_period_days": (date - pos["entry_date"]).days,
                        "notional": float(abs(shares * pos["entry_price"])),
                        "pnl": float(pnl),
                    }
                )
                del open_positions[ticker]

        weekly_returns = prices.resample("W-FRI").ffill().pct_change().fillna(0.0) * 100.0
        decision_date = date
        if decision_date in weekly_returns.index:
            for ticker in prices.columns:
                if ticker in open_positions:
                    continue
                if len(open_positions) >= max_positions:
                    continue
                current_return = float(weekly_returns.loc[decision_date, ticker])
                signal = "HOLD"
                if current_return <= -drop_threshold:
                    signal = "LONG"
                elif current_return >= rise_threshold:
                    signal = "SHORT"
                if signal == "HOLD":
                    continue

                trade_notional = min(capital * max_capital_allocation, capital * max_capital_allocation)
                total_open_notional = sum(abs(pos["shares"] * prices.loc[date, ticker]) for pos in open_positions.values())
                if total_open_notional + trade_notional > capital * max_capital_allocation * max_positions:
                    continue

                entry_price = _execution_price(float(row[ticker]), signal, slippage_bps)
                week_open = prices.loc[date - pd.Timedelta(days=7):date].iloc[0][ticker]
                shares = trade_notional / entry_price
                commission = abs(shares) * trade_cost_per_share
                if signal == "LONG":
                    cash -= trade_notional + commission
                else:
                    cash += trade_notional - commission
                open_positions[ticker] = {
                    "side": 1 if signal == "LONG" else -1,
                    "shares": shares,
                    "entry_price": entry_price,
                    "entry_week_open": float(week_open),
                    "entry_date": date,
                    "hold_period_days": hold_period_days,
                    "slippage_bps": slippage_bps,
                    "commission_per_share": trade_cost_per_share,
                }

        equity_value = cash + sum(pos["side"] * pos["shares"] * float(row[ticker]) for ticker, pos in open_positions.items())
        equity_curve.loc[date] = equity_value

    equity_curve = equity_curve.ffill().bfill()
    equity_curve.name = "equity_curve"
    metrics = _compute_risk_metrics(equity_curve)
    metrics.update(_compute_turnover_and_holding(trade_log))
    metrics["avg_trade_pnl"] = float(np.mean([t["pnl"] for t in trade_log]) if trade_log else 0.0)
    result = {
        "equity_curve": equity_curve,
        "metrics": metrics,
        "trades": trade_log,
    }

    if verbose:
        print("\n=== Mean Reversion Backtest ===")
        print(f"Total return        : {metrics['total_return']:.2%}")
        print(f"Sharpe ratio        : {metrics['sharpe']:.3f}")
        print(f"Sortino ratio       : {metrics['sortino']:.3f}")
        print(f"Max drawdown        : {metrics['max_drawdown']:.2%}")
        print(f"Calmar ratio        : {metrics['calmar']:.3f}")
        print(f"Avg holding period  : {metrics['average_holding_period_days']:.1f} days")
        print(f"Turnover rate       : {metrics['turnover_rate']:.3f}")
        print(f"Trades completed    : {len(trade_log)}")
        _plot_equity_and_drawdown(equity_curve)

    return result


def walk_forward_test(
    prices: pd.DataFrame,
    candidate_drop_thresholds: List[float],
    candidate_rise_thresholds: List[float],
    candidate_hold_periods: List[int],
    max_positions: int = 3,
    max_capital_allocation: float = 0.20,
    capital: float = 100000.0,
    trade_cost_per_share: float = 0.005,
    slippage_bps: float = 10.0,
):
    train_cutoff = int(len(prices) * 0.7)
    train_prices = prices.iloc[:train_cutoff]
    validation_prices = prices.iloc[train_cutoff:]

    best = None
    for drop in candidate_drop_thresholds:
        for rise in candidate_rise_thresholds:
            for hold in candidate_hold_periods:
                train_result = run_backtest(
                    train_prices,
                    drop_threshold=drop,
                    rise_threshold=rise,
                    hold_period_days=hold,
                    max_positions=max_positions,
                    max_capital_allocation=max_capital_allocation,
                    capital=capital,
                    trade_cost_per_share=trade_cost_per_share,
                    slippage_bps=slippage_bps,
                    verbose=False,
                )
                score = train_result["metrics"]["sharpe"]
                if best is None or score > best["score"]:
                    best = {
                        "score": score,
                        "drop_threshold": drop,
                        "rise_threshold": rise,
                        "hold_period_days": hold,
                    }

    selected = best
    train_metrics = run_backtest(
        train_prices,
        drop_threshold=selected["drop_threshold"],
        rise_threshold=selected["rise_threshold"],
        hold_period_days=selected["hold_period_days"],
        max_positions=max_positions,
        max_capital_allocation=max_capital_allocation,
        capital=capital,
        trade_cost_per_share=trade_cost_per_share,
        slippage_bps=slippage_bps,
        verbose=False,
    )["metrics"]
    validation_metrics = run_backtest(
        validation_prices,
        drop_threshold=selected["drop_threshold"],
        rise_threshold=selected["rise_threshold"],
        hold_period_days=selected["hold_period_days"],
        max_positions=max_positions,
        max_capital_allocation=max_capital_allocation,
        capital=capital,
        trade_cost_per_share=trade_cost_per_share,
        slippage_bps=slippage_bps,
        verbose=False,
    )["metrics"]

    return {
        "best_params": {
            "drop_threshold": selected["drop_threshold"],
            "rise_threshold": selected["rise_threshold"],
            "hold_period_days": selected["hold_period_days"],
        },
        "train_metrics": train_metrics,
        "validation_metrics": validation_metrics,
    }


def parameter_sensitivity_analysis(
    prices: pd.DataFrame,
    candidate_drop_thresholds: List[float],
    candidate_rise_thresholds: List[float],
    candidate_hold_periods: List[int],
    max_positions: int = 3,
    max_capital_allocation: float = 0.20,
    capital: float = 100000.0,
    trade_cost_per_share: float = 0.005,
    slippage_bps: float = 10.0,
):
    runs = []
    for drop in candidate_drop_thresholds:
        for rise in candidate_rise_thresholds:
            for hold in candidate_hold_periods:
                result = run_backtest(
                    prices,
                    drop_threshold=drop,
                    rise_threshold=rise,
                    hold_period_days=hold,
                    max_positions=max_positions,
                    max_capital_allocation=max_capital_allocation,
                    capital=capital,
                    trade_cost_per_share=trade_cost_per_share,
                    slippage_bps=slippage_bps,
                    verbose=False,
                )
                run_summary = {"drop_threshold": drop, "rise_threshold": rise, "hold_period_days": hold}
                run_summary.update(result["metrics"])
                runs.append(run_summary)
    return pd.DataFrame(runs).sort_values("sharpe", ascending=False).reset_index(drop=True)


def run_period_robustness_check(
    prices: pd.DataFrame,
    periods: List[tuple[str, str, str]],
    drop_threshold: float = 5.0,
    rise_threshold: float = 10.0,
    hold_period_days: int = 5,
    max_positions: int = 3,
    max_capital_allocation: float = 0.20,
    capital: float = 100000.0,
    trade_cost_per_share: float = 0.005,
    slippage_bps: float = 10.0,
):
    rows = []
    for label, start, end in periods:
        mask = (prices.index >= start) & (prices.index <= end)
        subset = prices.loc[mask].copy()
        if subset.empty:
            continue
        result = run_backtest(
            subset,
            drop_threshold=drop_threshold,
            rise_threshold=rise_threshold,
            hold_period_days=hold_period_days,
            max_positions=max_positions,
            max_capital_allocation=max_capital_allocation,
            capital=capital,
            trade_cost_per_share=trade_cost_per_share,
            slippage_bps=slippage_bps,
            verbose=False,
        )
        row = {"period": label, "start": start, "end": end}
        row.update(result["metrics"])
        rows.append(row)
    return pd.DataFrame(rows)


def backtest(tickers, start_date, end_date, drop_threshold=5, rise_threshold=10, long_notionals=5, short_notionals=10):
    prices = fetch_data(tickers, start_date, end_date)
    return run_backtest(
        prices,
        drop_threshold=drop_threshold,
        rise_threshold=rise_threshold,
        hold_period_days=5,
        max_positions=3,
        max_capital_allocation=0.2,
        capital=100000.0,
        trade_cost_per_share=0.005,
        slippage_bps=10.0,
        verbose=False,
    )


if __name__ == "__main__":
    universe = ["AAPL", "MSFT", "GOOGL", "AMZN"]
    prices = fetch_data(universe, "2015-01-01", "2024-12-31")
    summary = run_backtest(
        prices,
        drop_threshold=5.0,
        rise_threshold=10.0,
        hold_period_days=5,
        max_positions=3,
        max_capital_allocation=0.20,
        capital=100000.0,
        trade_cost_per_share=0.005,
        slippage_bps=10.0,
    )
    print("\nWalk-forward test:")
    print(walk_forward_test(
        prices,
        candidate_drop_thresholds=[3.0, 5.0, 7.0],
        candidate_rise_thresholds=[6.0, 10.0, 12.0],
        candidate_hold_periods=[3, 5, 7],
        max_positions=3,
        max_capital_allocation=0.20,
        capital=100000.0,
        trade_cost_per_share=0.005,
        slippage_bps=10.0,
    ))
    print("\nSensitivity analysis:")
    print(parameter_sensitivity_analysis(
        prices,
        candidate_drop_thresholds=[3.0, 5.0, 7.0],
        candidate_rise_thresholds=[6.0, 10.0, 12.0],
        candidate_hold_periods=[3, 5, 7],
        max_positions=3,
        max_capital_allocation=0.20,
        capital=100000.0,
        trade_cost_per_share=0.005,
        slippage_bps=10.0,
    ).head())
