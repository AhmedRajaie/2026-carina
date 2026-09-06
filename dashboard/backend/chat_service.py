"""Context construction and safe responses for the dashboard chat assistant."""

import os
from typing import Any


DISCLAIMER = (
    "This is educational dashboard information, not personalised financial advice. "
    "It cannot predict returns or guarantee profits."
)


def _money(value: float) -> str:
    return f"${value:,.2f}"


def build_dashboard_context(*, scope: str, sma_metrics: dict[str, Any], fixed_dollar: dict[str, Any], signals: list[dict[str, Any]]) -> dict[str, Any]:
    """Return only the current dashboard facts a chat response may use."""
    metrics = fixed_dollar["metrics"]
    parameters = fixed_dollar["parameters"]
    positions = sorted(
        ({"symbol": row["symbol"], "value": row["holding_value"], "signal": row["signal"]} for row in signals if row["holding_value"] > 0),
        key=lambda row: row["value"], reverse=True,
    )
    return {
        "scope": scope,
        "sma": sma_metrics,
        "fixed_dollar": {
            "initial_cash": parameters["initial_cash"], "final_equity": metrics["final_equity"],
            "profit_loss": round(metrics["final_equity"] - parameters["initial_cash"], 2),
            "total_return": metrics["total_return"], "sharpe": metrics["sharpe"],
            "max_drawdown": metrics["max_drawdown"], "fees_paid": metrics["fees_paid"],
            "cash": round(fixed_dollar["cash"][-1], 2), "buy_trades": metrics["buy_trades"],
            "sell_trades": metrics["sell_trades"], "positions": positions,
        },
    }


def local_dashboard_reply(message: str, context: dict[str, Any]) -> str:
    """Provide useful live-data answers when no external AI key is configured."""
    question = message.lower()
    strategy = context["fixed_dollar"]
    pnl = strategy["profit_loss"]
    pnl_label = "gain" if pnl >= 0 else "loss"
    if any(term in question for term in ("position", "holding", "own")):
        positions = strategy["positions"]
        if not positions:
            return "The fixed-dollar strategy currently has no open positions. " + DISCLAIMER
        details = ", ".join(f"{item['symbol']} ({_money(item['value'])}, {item['signal']})" for item in positions[:6])
        return f"Current fixed-dollar positions: {details}. " + DISCLAIMER
    if any(term in question for term in ("p&l", "pnl", "profit", "loss")):
        return f"The fixed-dollar strategy's P&L is {_money(pnl)} ({pnl_label}) from {_money(strategy['initial_cash'])} starting cash. Its current equity is {_money(strategy['final_equity'])}. {DISCLAIMER}"
    if any(term in question for term in ("balance", "cash", "account", "equity")):
        return f"The fixed-dollar account shows {_money(strategy['final_equity'])} total equity, including {_money(strategy['cash'])} cash. {DISCLAIMER}"
    if any(term in question for term in ("history", "trade", "order")):
        total = strategy["buy_trades"] + strategy["sell_trades"]
        return f"The fixed-dollar backtest recorded {total:,} orders: {strategy['buy_trades']:,} buys and {strategy['sell_trades']:,} sells, with {_money(strategy['fees_paid'])} in simulated commission. {DISCLAIMER}"
    if any(term in question for term in ("sharpe", "drawdown", "metric", "explain")):
        return f"The fixed-dollar strategy has a Sharpe ratio of {strategy['sharpe']:.3f} and a maximum drawdown of {strategy['max_drawdown'] * 100:.1f}%. Sharpe compares return with volatility; maximum drawdown is the largest peak-to-trough decline. {DISCLAIMER}"
    return f"The fixed-dollar strategy is at {_money(strategy['final_equity'])}, a {strategy['total_return'] * 100:.1f}% return and {_money(pnl)} {pnl_label}. Ask about performance, balance, positions, trading history, or a metric. {DISCLAIMER}"


def ai_dashboard_reply(message: str, history: list[dict[str, str]], context: dict[str, Any]) -> tuple[str, str] | None:
    """Use a server-side AI provider only when its key is configured."""
    gemini_key = os.environ.get("GEMINI_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    if not gemini_key and not openai_key:
        return None
    try:
        from openai import OpenAI

        instructions = "You are the Trading Dashboard assistant. Answer only from the supplied dashboard context; say when data is unavailable. Be concise and explain metrics plainly. Do not give personalised investment advice, trading instructions, guarantees, or promises of profit. End with this exact disclaimer: " + DISCLAIMER
        transcript = history[-8:] + [{"role": "user", "content": message}]
        prompt = f"Dashboard context (authoritative): {context}\n\nConversation: {transcript}\n\nAnswer the latest user message."
        if gemini_key:
            client = OpenAI(api_key=gemini_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
            response = client.chat.completions.create(
                model=os.environ.get("GEMINI_MODEL", "gemini-flash-latest"),
                messages=[{"role": "system", "content": instructions}, {"role": "user", "content": prompt}],
                max_tokens=700,
            )
            text = response.choices[0].message.content
            return (text.strip(), "gemini") if text else None
        response = OpenAI(api_key=openai_key).responses.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-5-mini"), instructions=instructions,
            input=prompt, store=False,
        )
        return (response.output_text.strip(), "openai") if response.output_text.strip() else None
    except Exception:
        return None
