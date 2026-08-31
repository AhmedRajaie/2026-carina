# backtest.py

import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
from src.strategy import mean_reversion_strategy

# Configurable parameters
TICKER_UNIVERSE = ['AAPL', 'MSFT', 'GOOGL']  # Example tickers
LONG_THRESHOLD = -0.05  # 5% drop
SHORT_THRESHOLD = 0.10  # 10% rise
LONG_POSITION_SIZE = 5  # Fixed notional for long positions
SHORT_POSITION_SIZE = 10  # Fixed notional for short positions

def fetch_data(tickers):
    data = {}
    for ticker in tickers:
        data[ticker] = yf.download(ticker, start='2020-01-01', end='2023-01-01')['Adj Close']
    return pd.DataFrame(data)

def main():
    # Fetch historical data
    price_data = fetch_data(TICKER_UNIVERSE)

    # Run the mean-reversion strategy
    results = mean_reversion_strategy(price_data, LONG_THRESHOLD, SHORT_THRESHOLD, LONG_POSITION_SIZE, SHORT_POSITION_SIZE)

    # Output performance statistics
    print("Total Return:", results['total_return'])
    print("Win Rate (%):", results['win_rate'])
    print("Longest Streak of Consecutive Losing Days:", results['longest_losing_streak'])
    print("Monthly P&L Table:\n", results['monthly_pnl'])
    
    # Plot equity curve
    plt.figure(figsize=(12, 6))
    plt.plot(results['equity_curve'], label='Equity Curve')
    plt.title('Equity Curve')
    plt.xlabel('Date')
    plt.ylabel('Equity')
    plt.legend()
    plt.show()

if __name__ == "__main__":
    main()